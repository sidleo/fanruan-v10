"""JWT token 认证管理（跨进程安全：同一实例的多进程只登录一次）

为什么需要跨进程锁：`frcli` 批量导出常被并发调用（多个进程），它们共用
`~/.frcli/tokens/<实例>.json`。两个进程同时发现缓存失效 → 同时登录 → 互相覆盖 token 缓存，
其中一个拿到被覆盖的 token，再撞上 CAS 302，表现为 `AUTH_FAILED: 重新登录后仍被重定向到登录页`。
解决：登录/刷新走同一把实例级文件锁，并在锁内二次检查缓存（另一个进程刚刷新过就直接复用）。
"""

import errno
import json
import math
import os
import random
import threading
import time
import getpass
from pathlib import Path
from typing import Optional
from .models import ServerConfig, TokenCache
from .exceptions import AuthError, AuthLockTimeoutError, ConnectionError
from .neterr import PROXY_HINT, is_proxy_5xx, is_transport_error, net_hint


TOKEN_CACHE_DIR = Path.home() / ".frcli" / "tokens"

#: 等待实例登录锁的超时秒数（多进程排队；正常登录 <2s，30s 足够）。可用环境变量覆盖。
AUTH_LOCK_TIMEOUT_ENV = "FRCLI_AUTH_LOCK_TIMEOUT"
AUTH_LOCK_TIMEOUT_DEFAULT = 30.0


# 同一进程内多线程也要串行：flock 的语义是「文件描述符/进程」级，某些系统上同进程
# 两个线程各自 open 后未必互斥；CLI 主路径是单线程，但 API 使用者可能并发调用。
_THREAD_LOCKS: dict[str, threading.Lock] = {}
_THREAD_LOCKS_GUARD = threading.Lock()


def _thread_lock_for(path: str) -> threading.Lock:
    with _THREAD_LOCKS_GUARD:
        lock = _THREAD_LOCKS.get(path)
        if lock is None:
            lock = threading.Lock()
            _THREAD_LOCKS[path] = lock
        return lock


class _InstanceLock:
    """实例级跨进程互斥锁（POSIX flock / Windows msvcrt.locking）。

    锁文件放在 token 缓存旁边（`<token_file>.lock`）；进程崩溃时由操作系统释放，不会留死锁。
    """

    def __init__(self, path: Path, timeout: float):
        self.path = Path(path)
        self.timeout = max(0.0, float(timeout))
        self._fd: Optional[int] = None
        self._thread_lock: Optional[threading.Lock] = None

    def __enter__(self):
        # 先拿进程内线程锁（同进程多线程互斥），再拿跨进程文件锁
        thread_lock = _thread_lock_for(str(self.path.resolve()))
        if not thread_lock.acquire(timeout=self.timeout):
            raise AuthLockTimeoutError(
                f"等待登录锁超时（{self.timeout:g}s）：{self.path}。"
                "本进程内已有线程在登录同一个实例；稍后重试，"
                f"或调大 {AUTH_LOCK_TIMEOUT_ENV}")
        self._thread_lock = thread_lock
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o600)
        except Exception:
            self._release_thread_lock()
            raise
        if os.name == "nt" and os.fstat(fd).st_size == 0:
            # Windows 的 msvcrt.locking 需要锁定区域内确有字节
            os.write(fd, b"\0")
        deadline = time.monotonic() + self.timeout
        while True:
            try:
                if os.name == "nt":
                    import msvcrt

                    os.lseek(fd, 0, os.SEEK_SET)
                    msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                self._fd = fd
                return self
            except OSError as e:
                if e.errno not in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                    os.close(fd)
                    self._release_thread_lock()
                    raise
                if time.monotonic() >= deadline:
                    os.close(fd)
                    self._release_thread_lock()
                    raise AuthLockTimeoutError(
                        f"等待登录锁超时（{self.timeout:g}s）：{self.path}。"
                        "另一个 frcli 进程正在登录同一个实例；稍后重试，"
                        f"或调大 {AUTH_LOCK_TIMEOUT_ENV}")
                time.sleep(0.05 + random.random() * 0.1)

    def _release_thread_lock(self):
        if self._thread_lock is not None:
            self._thread_lock.release()
            self._thread_lock = None

    def __exit__(self, *exc_info):
        try:
            if self._fd is not None:
                fd, self._fd = self._fd, None
                try:
                    if os.name == "nt":
                        import msvcrt

                        os.lseek(fd, 0, os.SEEK_SET)
                        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                    else:
                        import fcntl

                        fcntl.flock(fd, fcntl.LOCK_UN)
                finally:
                    os.close(fd)
        finally:
            self._release_thread_lock()


class TokenManager:
    """JWT token 管理：获取、缓存、刷新"""

    def __init__(self, config: ServerConfig):
        self.config = config
        self._token: Optional[str] = None
        self._expires_at: float = 0
        self._cookies: dict = {}

    # ---------- 缓存读取 ----------

    def get_valid_token(self) -> Optional[str]:
        """获取有效的 token（内存优先，其次文件缓存；都没有返回 None，由调用方决定是否登录）"""
        # 内存缓存有效
        if self._token and time.time() < self._expires_at:
            return self._token

        cached = self._load_cached_token()
        if cached and time.time() < cached.expires_at:
            self._adopt(cached)
            return self._token
        return None

    def get_cookies(self) -> dict:
        """获取缓存的 cookies"""
        return self._cookies

    # ---------- 跨进程安全入口 ----------

    @property
    def _token_file(self) -> Path:
        return Path(self.config.token_file)

    @property
    def _lock_file(self) -> Path:
        return self._token_file.with_name(self._token_file.name + ".lock")

    def _lock_timeout(self) -> float:
        raw = os.environ.get(AUTH_LOCK_TIMEOUT_ENV)
        if not raw:
            return AUTH_LOCK_TIMEOUT_DEFAULT
        try:
            value = float(raw)
        except ValueError:
            return AUTH_LOCK_TIMEOUT_DEFAULT
        # inf/NaN 会让 threading.Lock.acquire(timeout=…) 抛 OverflowError/ValueError；
        # 负数/非有限值统一回落到默认值（不要试图用 inf 表示"永远等"）。
        if not math.isfinite(value) or value < 0:
            return AUTH_LOCK_TIMEOUT_DEFAULT
        # `threading.Lock.acquire(timeout=1e12)` 在 macOS 上会 OverflowError（time_t 越界）→ 上限夹到 1h
        return min(value, 3600.0)

    def _lock(self) -> _InstanceLock:
        return _InstanceLock(self._lock_file, self._lock_timeout())

    def refresh_token(self, http_client) -> str:
        """确保拿到 token（缓存有效直接复用；否则在锁内二次检查，仍无效才登录）。

        这是 CLI 的默认入口：多进程同时启动时，只有第一个进程真正登录，
        其余进程等锁、拿到同一份新 token，避免并发登录互相作废。
        """
        with self._lock():
            cached = self.get_valid_token()
            if cached:
                return cached
            return self._do_login(http_client)

    def reauthenticate(self, http_client, invalid_token: Optional[str] = None) -> str:
        """认证失效后重新认证：锁内先看缓存里有没有**别的进程刚刷好的新 token**。

        如果缓存 token 与失效的那个不同，直接复用（避免多个进程连环重登、互相作废）；
        否则清缓存后登录一次。
        """
        with self._lock():
            cached = self._load_cached_token()
            if cached and time.time() < cached.expires_at and cached.token != invalid_token:
                self._adopt(cached)
                return cached.token
            self._discard_cached()
            return self._do_login(http_client)

    def login(self, http_client) -> str:
        """显式登录（同样串行化，避免与并发进程的刷新互相覆盖）"""
        with self._lock():
            return self._do_login(http_client)

    def invalidate(self):
        """清除 token（登出时调用；加锁避免删掉别的进程刚写入的新 token）"""
        self._token = None
        self._expires_at = 0
        self._cookies = {}
        with self._lock():
            self._discard_cached()

    # ---------- 内部实现 ----------

    def _adopt(self, cached: TokenCache):
        self._token = cached.token
        self._expires_at = cached.expires_at
        self._cookies = cached.cookies or {}

    def _discard_cached(self):
        token_file = self._token_file
        if token_file.exists():
            try:
                token_file.unlink()
            except OSError:
                pass

    def _do_login(self, http_client) -> str:
        """真正发登录请求并写缓存（调用方必须已持有实例锁）"""
        password = self.config.password
        if not password:
            password = getpass.getpass(f"请输入 {self.config.username} 的密码: ")

        try:
            # FineReport 登录端点 (v10 决策平台)
            login_url = f"{self.config.workspace}/decision/login"
            resp = http_client.post(
                login_url,
                json={
                    "username": self.config.username,
                    "password": password,
                },
                headers={"Content-Type": "application/json"},
            )

            if resp.status_code != 200:
                # 响应型代理指纹（5xx + `Proxy-Status`）与请求跳同一判定：登录这一跳也要说清
                # 是代理故障，否则只报 "登录失败: HTTP 503"，用户仍看不出断在哪一跳。
                if is_proxy_5xx(resp):
                    raise ConnectionError(
                        f"登录请求失败: HTTP {resp.status_code}{PROXY_HINT}")
                raise AuthError(f"登录失败: HTTP {resp.status_code}")

            # 从响应体获取 token
            data = resp.json()
            token = data.get("data", {}).get("accessToken")

            if not token:
                # 尝试其他字段
                token = data.get("accessToken") or data.get("token")

            if not token:
                raise AuthError("登录失败: 未获取到认证 token")

            # 保存 cookies 到 http_client 和内存
            cookies = {}
            for name, value in resp.cookies.items():
                http_client.cookies.set(name, value)
                cookies[name] = value

            # 缓存 token (默认 24 小时有效)
            self._token = token
            self._expires_at = time.time() + 86400
            self._cookies = cookies
            self._save_cached_token(token, self._expires_at, cookies)

            return token

        except AuthError:
            raise
        except ConnectionError:
            raise  # 上面按代理指纹抛出的，文案已完整，别被下面再套一层前缀
        except Exception as e:
            # 登录这一跳与请求那一跳是同一条链路：传输层错误共用 neterr 的分类文案。
            # 不给 login 加自动重试 —— 它是 POST，且代理/链路故障通常不是瞬时问题。
            hint = net_hint(e) if is_transport_error(e) else str(e)
            raise ConnectionError(f"登录请求失败: {hint}")

    def _load_cached_token(self) -> Optional[TokenCache]:
        """从文件加载缓存的 token（写侧是原子替换，读侧不会读到半个 JSON）"""
        token_file = self._token_file
        if not token_file.exists():
            return None
        try:
            with open(token_file, "r") as f:
                data = json.load(f)
            return TokenCache(
                instance=data["instance"],
                token=data["token"],
                expires_at=data["expires_at"],
                created_at=data["created_at"],
                cookies=data.get("cookies", {}),
            )
        except (KeyError, json.JSONDecodeError, OSError):
            return None

    def _save_cached_token(self, token: str, expires_at: float, cookies: dict = None):
        """保存 token 到文件缓存（临时文件 + 原子替换，防止别的进程读到半个 JSON）"""
        TOKEN_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        token_file = self._token_file
        data = {
            "instance": self.config.name,
            "token": token,
            "expires_at": expires_at,
            "created_at": time.time(),
            "cookies": cookies or {},
        }
        tmp = token_file.with_name(
            token_file.name
            + f".tmp{os.getpid()}.{threading.get_ident()}.{random.randrange(1 << 32):08x}")
        try:
            with open(tmp, "w") as f:
                json.dump(data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.chmod(tmp, 0o600)
            os.replace(tmp, token_file)
        finally:
            try:
                tmp.unlink()
            except OSError:
                pass
