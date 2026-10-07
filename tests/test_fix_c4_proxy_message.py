"""C4 回归：本机 HTTP 代理故障（httpx.ProxyError）的文案必须点明"代理这一跳"。

背景（真机实测）：本机系统代理返回 503 时，`server test` / `report list` 都报
`CONNECTION_ERROR: 请求失败: 503 Service Unavailable（…若为连接类问题先 frcli server test 确认会话…）`，
文案把人引向"会话/超时"，看不出失败发生在代理这一跳；而 `str(ProxyError)` 只有
`503 Service Unavailable`，光看文本也认不出是代理。

全离线：用本地 127.0.0.1 的假代理/假上游，不打真实网络。
"""
from __future__ import annotations

import json
import socket
import threading

import httpx
import pytest

from frcli.client import FineReportClient, _net_hint
from frcli.exceptions import ConnectionError as FrConnError
from frcli.models import ServerConfig

PROXY_HINT_KEYS = ("代理", "proxy")


def _client(tmp_path, base="http://127.0.0.1:1", transport=None):
    cfg = ServerConfig(name="stub", url=base, username="stub_user",
                       password="stub_pass", workspace="/webroot",
                       token_file=tmp_path / "tok.json")
    (tmp_path / "tok.json").write_text(json.dumps({
        "instance": "stub", "token": "stub-token",
        "expires_at": 4102444800, "created_at": 0, "cookies": {},
    }), encoding="utf-8")
    client = FineReportClient(cfg)
    if transport is not None:
        client._http.close()
        client._http = httpx.Client(base_url=base, timeout=3,
                                    follow_redirects=False, transport=transport)
    return client


def test_proxy_error_hint_names_the_proxy_hop():
    """ProxyError 的提示必须出现"代理"，且不再教人"先 server test 确认会话"。"""
    hint = _net_hint(httpx.ProxyError("503 Service Unavailable"))
    assert any(k in hint for k in ("代理", "proxy")), f"没点明代理这一跳: {hint}"
    assert "确认会话" not in hint, f"仍把代理故障引向会话问题: {hint}"
    assert "503" in hint, "应保留 httpx 原始信息（503 Service Unavailable）"


def test_proxy_error_raises_connection_error_via_request_path(tmp_path):
    """经真实 _request 代码路径：ProxyError → CONNECTION_ERROR（失败语义不变）。"""
    def handler(request):
        raise httpx.ProxyError("503 Service Unavailable")

    client = _client(tmp_path, transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(FrConnError) as ei:
            client._get("/webroot/decision/v10/schedule/task/names")
        assert ei.value.code == "CONNECTION_ERROR"
        assert "代理" in str(ei.value)
    finally:
        client.close()


def test_5xx_with_proxy_fingerprint_is_reported_as_proxy(tmp_path):
    """响应是 5xx 且带代理指纹（Proxy-Status/Via）→ 这是代理返回的，要说明。"""
    def handler(request):
        return httpx.Response(503, headers={"proxy-status": "error;detail=upstream_failed"})

    client = _client(tmp_path, transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(FrConnError) as ei:
            client._get("/webroot/decision/v10/schedule/task/names")
        assert "代理" in str(ei.value)
    finally:
        client.close()


def test_platform_5xx_without_proxy_fingerprint_is_not_blamed_on_proxy(tmp_path):
    """对照组：不带代理指纹的 5xx 不得说成代理问题（平台自身 502/503 会被误报）。"""
    def handler(request):
        return httpx.Response(503, headers={"content-type": "text/html"})

    client = _client(tmp_path, transport=httpx.MockTransport(handler))
    try:
        resp = client._get("/webroot/decision/v10/schedule/task/names")
        assert resp.status_code == 503
    finally:
        client.close()


def test_client_still_honors_env_proxy(tmp_path, monkeypatch):
    """不得自动绕过用户代理：设了 HTTP_PROXY 就必须走代理这一跳。

    判别方式：目标主机是不可解析的保留域名；若客户端"偷偷直连"，它会自己做 DNS 解析
    并失败，假代理收到 0 个请求 —— 断言假代理**收到**请求即证明没有绕过。
    """
    received: list[str] = []
    sock = socket.socket()
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", 0))
    sock.listen(4)
    port = sock.getsockname()[1]
    body = json.dumps({"data": []}).encode()

    def serve():
        while True:
            try:
                conn, _ = sock.accept()
            except OSError:
                return
            try:
                head = b""
                while b"\r\n\r\n" not in head:
                    chunk = conn.recv(4096)
                    if not chunk:
                        break
                    head += chunk
                if head:
                    received.append(head.split(b"\r\n", 1)[0].decode("latin-1"))
                    conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
                                 b"Content-Length: " + str(len(body)).encode() +
                                 b"\r\nConnection: close\r\n\r\n" + body)
            except OSError:
                pass
            finally:
                try:
                    conn.close()
                except OSError:
                    pass

    threading.Thread(target=serve, daemon=True).start()
    monkeypatch.setenv("HTTP_PROXY", f"http://127.0.0.1:{port}")
    monkeypatch.setenv("http_proxy", f"http://127.0.0.1:{port}")
    monkeypatch.delenv("NO_PROXY", raising=False)
    monkeypatch.delenv("no_proxy", raising=False)

    cfg = ServerConfig(name="stub", url="http://upstream.example.invalid",
                       username="stub_user", password="stub_pass",
                       workspace="/webroot", token_file=tmp_path / "tok.json")
    (tmp_path / "tok.json").write_text(json.dumps({
        "instance": "stub", "token": "stub-token",
        "expires_at": 4102444800, "created_at": 0, "cookies": {},
    }), encoding="utf-8")
    client = FineReportClient(cfg)
    try:
        try:
            client._get("/webroot/decision/v10/schedule/task/names")
        except Exception:  # noqa: BLE001  代理是否应答不影响本条断言
            pass
        assert received, ("客户端没有走 HTTP_PROXY —— 疑似被改成了自动绕过用户代理；"
                          "C4 只应改文案，不应改网络行为")
        assert received[0].split(" ")[1].startswith("http://upstream.example.invalid"), \
            f"代理收到的是非绝对 URI 请求行: {received[0]}"
    finally:
        client.close()
        sock.close()
