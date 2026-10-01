"""模板锁（TplLockedException）的重试/等待/释放 —— 学自 2026-09 的会话。

那次会话被锁堵死：写不进、改名不行、删不掉，只能换新文件名上传。
真实原因（用户澄清）：**设计器里正开着那个模板**。
另一条是本项目实验发现的：**强杀客户端（SIGKILL）留下的锁，同账号新会话也解不开**。
"""
from __future__ import annotations

import pytest

from frcli.exceptions import ApiError
from frcli import remotedesign as rd


class _FakeSession:
    def __init__(self, fail_times=0):
        self.fail_times = fail_times
        self.calls = 0
        self.unlocked = []

    def lock(self, path):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise ApiError("远程设计 RPC readAndLockFile 失败: "
                           "com.fr.exception.TplLockedException: Fine-Engine_Remote_Design_Tpl_Locked")
        return b"<WorkBook/>"

    def unlock(self, path):
        self.unlocked.append(path)


def test_is_locked_error():
    assert rd._is_locked_error(ApiError("…TplLockedException: …"))
    assert not rd._is_locked_error(ApiError("别的问题"))


def test_lock_retries_then_succeeds(monkeypatch):
    """普通竞争：前两次被锁、第三次拿到 —— 不该直接失败。"""
    # ⚠ 不要把 time.sleep 打桩成空转：循环用**真实时钟**判 deadline，空转会导致死循环。
    # 正确做法是把重试间隔改小，让真实 sleep 很快走完。
    monkeypatch.setattr(rd, "_LOCK_RETRY_DELAYS", (0.001, 0.001, 0.001))
    s = _FakeSession(fail_times=2)
    data, tries = rd._lock_with_wait(s, "x.cpt")
    assert data == b"<WorkBook/>" and tries == 3


def test_lock_failure_message_is_actionable(monkeypatch):
    """一直被锁：错误信息要指出「设计器开着」为首要原因，并给出绕过办法。"""
    monkeypatch.setattr(rd, "_LOCK_RETRY_DELAYS", (0.001, 0.001, 0.001))
    monkeypatch.delenv("FRCLI_WAIT_LOCK", raising=False)
    s = _FakeSession(fail_times=99)
    with pytest.raises(ApiError) as ei:
        rd._lock_with_wait(s, "x.cpt")
    msg = str(ei.value)
    assert "设计器里正开着这个模板" in msg
    assert "FRCLI_WAIT_LOCK" in msg
    assert "xxxV2.cpt" in msg, "要给绕过办法"
    assert "跨会话" not in msg or "返回 true 但锁仍在" in msg


def test_release_locks_frees_tracked_paths():
    """close() 要释放本会话还占着的锁 —— 否则模板会被锁住。"""
    s = rd.RemoteDesignSession.__new__(rd.RemoteDesignSession)   # 不走 __init__（要联网）
    s._locked = {"a.cpt", "b.cpt"}
    s._http = type("H", (), {"close": lambda self: None})()
    calls = []
    s.call = lambda *a, **k: calls.append(a) or True
    rd.RemoteDesignSession._OPEN.add(s)
    s.close()
    assert calls, "应调用 closeAndFreeFile"
    assert not s._locked, "释放后不该还记着"
    assert s not in rd.RemoteDesignSession._OPEN


def test_cli_installs_lock_guard():
    """CLI 入口必须挂锁保护钩子（Ctrl-C / SIGTERM 时释放）。"""
    import pathlib
    cli = pathlib.Path(__file__).resolve().parent.parent / "src" / "frcli" / "cli.py"
    assert "install_lock_guard" in cli.read_text(encoding="utf-8")
