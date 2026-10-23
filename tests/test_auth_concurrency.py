"""回归：多进程并发登录的 token 缓存竞争（并发导出报 AUTH_FAILED 302 的根因）。

守护点：
1. 同一实例的多个进程同时刷新 token 时，只允许一个真正登录，其余复用同一份缓存；
2. 认证失效后重登前先看缓存里有没有别的进程刚刷好的新 token（有就直接复用）；
3. 登录锁可超时且错误信息可操作；token 缓存文件写入原子（不会读到半个 JSON）。
"""
from __future__ import annotations

import json
import multiprocessing as mp
import os
import threading
import time
from pathlib import Path

import pytest

from frcli.auth import AUTH_LOCK_TIMEOUT_ENV, TokenManager, _InstanceLock
from frcli.exceptions import AuthError
from frcli.models import ServerConfig


class _Cookies(dict):
    def set(self, name, value):
        self[name] = value


class _Resp:
    def __init__(self, token: str, status_code: int = 200):
        self.status_code = status_code
        self.cookies = _Cookies()
        self._token = token

    def json(self):
        return {"data": {"accessToken": self._token}}


class _FakeHTTP:
    """假 HTTP client：每发一次登录请求就记一行到 login_log（用于数登录次数）。"""

    def __init__(self, login_log: str | None = None):
        self.cookies = _Cookies()
        self.login_log = Path(login_log) if login_log else None
        self.logins = 0

    def post(self, url, json=None, headers=None):
        self.logins += 1
        token = f"tok-{os.getpid()}-{self.logins}-{time.monotonic_ns()}"
        if self.login_log is not None:
            with open(self.login_log, "a", encoding="utf-8") as f:
                f.write(token + "\n")
        return _Resp(token)


def _manager(token_file: Path) -> TokenManager:
    cfg = ServerConfig(name="itest", url="http://127.0.0.1:1", username="u",
                       password="p", token_file=Path(token_file))
    return TokenManager(cfg)


# ---------- 跨进程 worker（spawn 需要模块级函数） ----------

def _refresh_worker(token_file: str, login_log: str, barrier, queue):
    from frcli.auth import TokenManager
    from frcli.models import ServerConfig

    cfg = ServerConfig(name="itest", url="http://127.0.0.1:1", username="u",
                       password="p", token_file=Path(token_file))
    fake = _FakeHTTP(login_log)
    barrier.wait(20)
    token = TokenManager(cfg).refresh_token(fake)
    queue.put(token)


def _hold_lock_worker(lock_path: str, ready, done):
    from frcli.auth import _InstanceLock

    with _InstanceLock(Path(lock_path), timeout=10):
        ready.set()
        time.sleep(1.5)
    done.set()


# ---------- 测试 ----------

def _login_count(login_log: Path) -> int:
    if not login_log.exists():
        return 0
    return len([ln for ln in login_log.read_text().splitlines() if ln.strip()])


def test_refresh_token_reuses_valid_cache(tmp_path):
    token_file = tmp_path / "itest.json"
    manager = _manager(token_file)
    first = _FakeHTTP()
    assert manager.refresh_token(first).startswith("tok-")
    assert first.logins == 1

    # 新进程（新 TokenManager）直接复用缓存，不再登录
    second = _FakeHTTP()
    token = _manager(token_file).refresh_token(second)
    assert token == manager.get_valid_token()
    assert second.logins == 0
    # 缓存文件是完整 JSON（原子写）
    data = json.loads(token_file.read_text())
    assert data["token"] == token


def test_reauthenticate_adopts_token_written_by_other_process(tmp_path):
    token_file = tmp_path / "itest.json"
    _manager(token_file).refresh_token(_FakeHTTP())  # 另一个进程先登录写入缓存

    manager = _manager(token_file)
    manager._token = "stale-token"          # 模拟旧进程内存里还有失效 token
    manager._expires_at = time.time() + 86400
    fake = _FakeHTTP()
    token = manager.reauthenticate(fake, invalid_token="stale-token")
    assert fake.logins == 0                 # 直接复用新缓存，不重登
    assert token == json.loads(token_file.read_text())["token"]


def test_reauthenticate_logs_in_when_cached_token_is_the_invalid_one(tmp_path):
    token_file = tmp_path / "itest.json"
    first = _manager(token_file)
    first.refresh_token(_FakeHTTP())        # 缓存里就是那个失效 token
    fake = _FakeHTTP()
    token = first.reauthenticate(fake, invalid_token=first.get_valid_token())
    assert fake.logins == 1
    assert first._token == token


def test_cross_process_only_one_login(tmp_path):
    """3 个进程同时刷新：只允许 1 次登录，三个进程拿到同一个 token。"""
    ctx = mp.get_context("spawn")
    token_file = tmp_path / "itest.json"
    login_log = tmp_path / "logins.txt"
    barrier = ctx.Barrier(3)
    queue = ctx.Queue()
    procs = [
        ctx.Process(target=_refresh_worker,
                    args=(str(token_file), str(login_log), barrier, queue))
        for _ in range(3)
    ]
    for p in procs:
        p.start()
    tokens = [queue.get(timeout=60) for _ in procs]
    for p in procs:
        p.join(timeout=60)
        assert p.exitcode == 0

    assert len(set(tokens)) == 1, tokens
    assert _login_count(login_log) == 1, login_log.read_text()
    assert json.loads(token_file.read_text())["token"] == tokens[0]
    # 锁文件存在但不应残留临时文件
    assert not list(tmp_path.glob("*.tmp*"))


def test_lock_timeout_has_actionable_error(tmp_path, monkeypatch):
    """另一个进程持锁超过超时：报 AuthError，文案指向 FRCLI_AUTH_LOCK_TIMEOUT。"""
    ctx = mp.get_context("spawn")
    lock_path = tmp_path / "itest.json.lock"
    ready, done = ctx.Event(), ctx.Event()
    holder = ctx.Process(target=_hold_lock_worker, args=(str(lock_path), ready, done))
    holder.start()
    try:
        assert ready.wait(30)
        monkeypatch.setenv(AUTH_LOCK_TIMEOUT_ENV, "0.2")
        manager = _manager(tmp_path / "itest.json")
        with pytest.raises(AuthError, match="等待登录锁超时"):
            manager.refresh_token(_FakeHTTP())
    finally:
        holder.join(timeout=30)
    assert done.is_set()


def test_same_instance_threads_reuse_cache(tmp_path):
    """同进程多线程：缓存有效时全部复用，不触发登录。"""
    token_file = tmp_path / "itest.json"
    token = _manager(token_file).refresh_token(_FakeHTTP())
    results, logins = [], []

    def worker():
        fake = _FakeHTTP()
        results.append(_manager(token_file).refresh_token(fake))
        logins.append(fake.logins)

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert results == [token] * 4
    assert sum(logins) == 0


def test_same_process_threads_with_empty_cache_single_login(tmp_path):
    """同进程多线程 + 空缓存：也只允许 1 次登录（线程锁 + 文件锁双保险）。"""
    import threading as _threading

    token_file = tmp_path / "itest.json"
    barrier = _threading.Barrier(4)
    results, logins = [], []
    lock = _threading.Lock()

    def worker():
        fake = _FakeHTTP()
        barrier.wait(20)
        tok = _manager(token_file).refresh_token(fake)
        with lock:
            results.append(tok)
            logins.append(fake.logins)

    threads = [_threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    assert len(set(results)) == 1, results
    assert sum(logins) == 1, logins


def test_lock_timeout_does_not_leak_thread_lock(tmp_path, monkeypatch):
    """锁超时报错后必须释放进程内线程锁：同进程下一次调用不能被永久阻塞。"""
    ctx = mp.get_context("spawn")
    lock_path = tmp_path / "itest.json.lock"
    ready, done = ctx.Event(), ctx.Event()
    holder = ctx.Process(target=_hold_lock_worker, args=(str(lock_path), ready, done))
    holder.start()
    try:
        assert ready.wait(30)
        monkeypatch.setenv(AUTH_LOCK_TIMEOUT_ENV, "0.2")
        manager = _manager(tmp_path / "itest.json")
        with pytest.raises(AuthError, match="等待登录锁超时"):
            manager.refresh_token(_FakeHTTP())
    finally:
        holder.join(timeout=30)
    # 持锁进程已退出：线程锁若泄漏，这里会一直阻塞（用线程超时守护）
    done_evt = threading.Event()

    def retry():
        manager.refresh_token(_FakeHTTP())
        done_evt.set()

    t = threading.Thread(target=retry, daemon=True)
    t.start()
    assert done_evt.wait(10), "锁超时后线程锁泄漏，同进程后续登录被永久阻塞"


@pytest.mark.parametrize("bad", ["nan", "inf", "-inf", "-1", "abc"])
def test_lock_timeout_env_falls_back(tmp_path, monkeypatch, bad):
    monkeypatch.setenv(AUTH_LOCK_TIMEOUT_ENV, bad)
    assert _manager(tmp_path / "itest.json")._lock_timeout() == 30.0


@pytest.mark.parametrize("raw,expected", [("600", 600.0), ("1e12", 3600.0)])
def test_lock_timeout_env_is_clamped_to_1h(tmp_path, monkeypatch, raw, expected):
    """有限超大值也要夹上限：threading.Lock.acquire(timeout=1e12) 会 OverflowError。"""
    monkeypatch.setenv(AUTH_LOCK_TIMEOUT_ENV, raw)
    assert _manager(tmp_path / "itest.json")._lock_timeout() == expected
