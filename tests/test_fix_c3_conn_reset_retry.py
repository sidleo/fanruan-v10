"""C3 回归：连接被对端重置（≠超时）的行为与文案。

背景（实测）：批量导出里偶发 `Connection reset by peer`，旧实现把它归进"超时类"提示
（「必要时 FRCLI_TIMEOUT=600 调大重试」），用户把 900→1200→1800 照样被 reset；
而这类错误**原样重试即成功**，旧实现却一次也不重试。

本文件用**本地裸 socket 服务端**制造真实 RST（SO_LINGER 0），走真实 client 代码路径。
全离线：只连 127.0.0.1。
"""
from __future__ import annotations

import json
import os
import socket
import struct
import threading
import time
from pathlib import Path

import httpx
import pytest

from frcli.client import FineReportClient, _net_hint
from frcli.exceptions import AuthError
from frcli.exceptions import ConnectionError as FrConnError
from frcli.models import ServerConfig

OK_BODY = json.dumps({"data": []}).encode()


class LocalServer:
    """裸 socket 服务端：`reset_first` 首次请求 RST，`reset_always` 每次都 RST。

    记录 ``requests``（方法+路径）与 ``conns``，用于断言"到底重试了几次"。
    """

    def __init__(self, mode: str):
        assert mode in ("reset_first", "reset_always", "hang", "ok")
        self.mode = mode
        self.requests: list[tuple[str, str]] = []
        self.conns = 0
        self._sock = socket.socket()
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(8)
        self.port = self._sock.getsockname()[1]
        threading.Thread(target=self._accept, daemon=True).start()

    def _accept(self):
        while True:
            try:
                conn, _ = self._sock.accept()
            except OSError:
                return
            self.conns += 1
            threading.Thread(target=self._handle, args=(conn,), daemon=True).start()

    def _handle(self, conn):
        try:
            head = b""
            while b"\r\n\r\n" not in head and len(head) < 65536:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                head += chunk
            if not head:
                conn.close()
                return
            line = head.split(b"\r\n", 1)[0].decode("latin-1")
            parts = line.split(" ")
            self.requests.append((parts[0], parts[1]))

            n = len(self.requests)
            if self.mode == "reset_always" or (self.mode == "reset_first" and n == 1):
                self._rst(conn)
                return
            if self.mode == "hang":
                time.sleep(30)
                conn.close()
                return
            conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
                         b"Content-Length: " + str(len(OK_BODY)).encode() +
                         b"\r\nConnection: close\r\n\r\n" + OK_BODY)
            conn.close()
        except OSError:
            pass

    @staticmethod
    def _rst(conn):
        try:
            conn.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
        except OSError:
            pass
        try:
            conn.close()
        except OSError:
            pass

    def stop(self):
        try:
            self._sock.close()
        except OSError:
            pass


def make_client(port: int, tmp_path: Path, timeout: str = "3.0") -> FineReportClient:
    """构造客户端并**预置 token 缓存**，避免 RST 打在登录请求上而测错对象。"""
    os.environ["FRCLI_TIMEOUT"] = timeout
    tok = tmp_path / "tok.json"
    tok.write_text(json.dumps({
        "instance": "stub", "token": "stub-token",
        "expires_at": time.time() + 3600, "created_at": time.time(), "cookies": {},
    }), encoding="utf-8")
    cfg = ServerConfig(name="stub", url=f"http://127.0.0.1:{port}",
                       username="stub_user", password="stub_pass",
                       workspace="/webroot", token_file=tok)
    return FineReportClient(cfg)


@pytest.fixture
def server_factory():
    made = []

    def make(mode):
        srv = LocalServer(mode)
        made.append(srv)
        return srv

    yield make
    for srv in made:
        srv.stop()


@pytest.fixture(autouse=True)
def _restore_timeout():
    old = os.environ.get("FRCLI_TIMEOUT")
    yield
    if old is None:
        os.environ.pop("FRCLI_TIMEOUT", None)
    else:
        os.environ["FRCLI_TIMEOUT"] = old


def test_get_retries_once_and_succeeds(server_factory, tmp_path):
    """GET 撞 RST → 自动重试 1 次后成功（实测"原样重试即成功"）。"""
    srv = server_factory("reset_first")
    client = make_client(srv.port, tmp_path)
    try:
        resp = client._get("/webroot/decision/view/report")
        assert resp.status_code == 200
        time.sleep(0.2)
        assert len(srv.requests) == 2, f"应恰好重试 1 次: {srv.requests}"
        assert client.net_retries == 1
    finally:
        client.close()


def test_get_gives_up_after_one_retry(server_factory, tmp_path):
    """重试是**有界**的：连续被 reset 只试 2 次就抛错，不做无限重试。"""
    srv = server_factory("reset_always")
    client = make_client(srv.port, tmp_path)
    try:
        with pytest.raises(FrConnError):
            client._get("/webroot/decision/view/report")
        time.sleep(0.2)
        assert len(srv.requests) == 2, f"应恰好 2 次（1 次 + 1 次重试）: {srv.requests}"
        assert client.net_retries == 1
    finally:
        client.close()


def test_post_never_retries_on_reset(server_factory, tmp_path):
    """POST 一律不重试 —— 写操作重放有被执行两次的风险。"""
    srv = server_factory("reset_always")
    client = make_client(srv.port, tmp_path)
    try:
        with pytest.raises(FrConnError):
            client._post("/webroot/decision/v10/schedule/task")
        time.sleep(0.2)
        assert len(srv.requests) == 1, f"POST 被重放了: {srv.requests}"
        assert client.net_retries == 0
    finally:
        client.close()


def test_timeout_is_not_retried(server_factory, tmp_path):
    """超时不重试：服务端还在算，重发只是把等待翻倍。"""
    srv = server_factory("hang")
    client = make_client(srv.port, tmp_path, timeout="1.0")
    try:
        t0 = time.time()
        with pytest.raises(FrConnError):
            client._get("/webroot/decision/view/report")
        assert time.time() - t0 < 5, "超时后仍在等待 → 疑似重试了"
        time.sleep(0.2)
        assert len(srv.requests) == 1, f"超时被重试了: {srv.requests}"
        assert client.net_retries == 0
    finally:
        client.close()


def test_auth_failure_loop_is_not_retried_by_net_policy(tmp_path):
    """认证失效走"重登 1 次"的老路径，不叠加连接层重试（GET 恰 2 次）。"""
    calls = []

    def handler(request):
        calls.append((request.method, request.url.path))
        if request.url.path.endswith("/decision/login"):
            return httpx.Response(200, json={"data": {"accessToken": "stub"}})
        return httpx.Response(302, headers={"location": "https://sso.example.com/cas/login"})

    client = make_client(1, tmp_path)
    client._http.close()
    client._http = httpx.Client(base_url="http://127.0.0.1:1", timeout=3,
                                follow_redirects=False,
                                transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(AuthError):
            client._get("/webroot/decision/view/report")
        gets = [c for c in calls if c[0] == "GET"]
        assert len(gets) == 2, f"GET 应为 2 次（首次 + 重登后），实际 {calls}"
        assert client.net_retries == 0
    finally:
        client.close()


def test_reset_hint_does_not_prescribe_larger_timeout():
    """连接被重置的提示不得再教人"调大 FRCLI_TIMEOUT"（实测无效、误导）。"""
    msg = _net_hint(httpx.RemoteProtocolError("Server disconnected without sending a response."))
    assert "原样重试" in msg or "重试" in msg
    assert "FRCLI_TIMEOUT=600" not in msg, f"仍把 reset 当超时处理: {msg}"


def test_reset_hint_matches_reset_by_peer_wording():
    """真实报错原文 `[Errno 54] Connection reset by peer`（ConnectError）同样要归入 reset 类。"""
    msg = _net_hint(httpx.ConnectError("[Errno 54] Connection reset by peer"))
    assert "FRCLI_TIMEOUT=600" not in msg, f"仍把 reset 当超时处理: {msg}"


def test_timeout_hint_still_recommends_larger_timeout():
    """对照组：真超时仍要给出调大超时的可操作建议（别把两类一起改坏）。"""
    msg = _net_hint(httpx.ReadTimeout("The read operation timed out"))
    assert "FRCLI_TIMEOUT=600" in msg
