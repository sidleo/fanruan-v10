"""R3 / S1 / S2 回归：代理故障的三处边界（登录跳、重试集合、指纹判定）。

背景（本轮新引入 / 未覆盖）：
- R3：登录跳（`auth.TokenManager.login`）没有响应型代理指纹 ⇒ 无 token 缓存时裸报
  `登录失败: HTTP 503`，看不出断在代理这一跳。
- S1：`_send` 把 `httpx.ProxyError` 当"链路瞬时抖动"重试 ⇒ GET 对同一条坏代理打两次。
- S2：指纹同时认 `Proxy-Status` 与 `Via` ⇒ 平台网关带的 `Via` 会把平台自身 5xx 误报成代理故障。

全离线：MockTransport + 本地裸 socket，只连 127.0.0.1。
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import httpx
import pytest

from frcli.client import FineReportClient
from frcli.exceptions import AuthError
from frcli.exceptions import ConnectionError as FrConnError
from frcli.models import ServerConfig

LOGIN_PATH = "/webroot/decision/login"


def _client(tmp_path: Path, port: int = 1, transport=None, seed_token: bool = True):
    tok = tmp_path / "tok.json"
    if seed_token:
        tok.write_text(json.dumps({
            "instance": "stub", "token": "stub-token",
            "expires_at": time.time() + 3600, "created_at": time.time(), "cookies": {},
        }), encoding="utf-8")
    elif tok.exists():
        tok.unlink()
    cfg = ServerConfig(name="stub", url=f"http://127.0.0.1:{port}",
                       username="stub_user", password="stub_pass",
                       workspace="/webroot", token_file=tok)
    c = FineReportClient(cfg)
    if transport is not None:
        c._http.close()
        c._http = httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=3,
                               follow_redirects=False, transport=transport)
    return c


def _is_proxy_message(msg: str) -> bool:
    """判定文案是否在说"代理这一跳"。

    ⚠️ 不能用 `"代理" in msg` —— `非代理` 里也含 `代理`（子串陷阱，我第一版探针就栽在这）。
    这里认提示块的特征短语；调用方只在**抛异常**时用它。
    """
    return any(k in msg for k in ("ProxyError", "代理链路故障", "代理这一跳"))


# ==================== R3：登录跳 ====================

def test_login_5xx_with_proxy_status_is_reported_as_proxy(tmp_path):
    """登录回 503 + `Proxy-Status` → 按代理故障报（ConnectionError），且登录只发 1 次。"""
    calls = []

    def handler(request):
        calls.append(request.method)
        if request.url.path.endswith("/decision/login"):
            return httpx.Response(503, headers={"proxy-status": "error;detail=upstream_failed"})
        return httpx.Response(200, json={"data": []})

    c = _client(tmp_path, transport=httpx.MockTransport(handler), seed_token=False)
    try:
        with pytest.raises(FrConnError) as ei:
            c._get("/webroot/decision/v10/schedule/task/names")
        msg = str(ei.value)
        assert _is_proxy_message(msg), f"登录跳的 5xx 没点明代理: {msg}"
        assert "503" in msg, "应保留 HTTP 状态码"
        assert calls.count("POST") == 1, f"登录是 POST，链路故障不该重试: {calls}"
    finally:
        c.close()


def test_login_503_without_fingerprint_is_not_blamed_on_proxy(tmp_path):
    """无指纹的 503 不得说成代理（平台自身 5xx 会误报）。"""
    def handler(request):
        if request.url.path.endswith("/decision/login"):
            return httpx.Response(503, content=b"<html>503</html>")
        return httpx.Response(200, json={"data": []})

    c = _client(tmp_path, transport=httpx.MockTransport(handler), seed_token=False)
    try:
        with pytest.raises(AuthError) as ei:
            c._get("/webroot/decision/v10/schedule/task/names")
        assert not _is_proxy_message(str(ei.value)), str(ei.value)
        assert "503" in str(ei.value)
    finally:
        c.close()


def test_login_5xx_with_only_via_is_not_proxy(tmp_path):
    """仅 `Via`（平台网关常加）不算代理指纹 —— 登录跳同样不得误报。"""
    def handler(request):
        if request.url.path.endswith("/decision/login"):
            return httpx.Response(502, headers={"via": "1.1 platform-gateway"})
        return httpx.Response(200, json={"data": []})

    c = _client(tmp_path, transport=httpx.MockTransport(handler), seed_token=False)
    try:
        with pytest.raises(AuthError) as ei:
            c._get("/webroot/decision/v10/schedule/task/names")
        assert not _is_proxy_message(str(ei.value)), str(ei.value)
    finally:
        c.close()


# ==================== S1：重试集合 ====================

def test_get_proxy_error_is_not_retried(tmp_path):
    """GET + `httpx.ProxyError` 只发 1 次（代理链路故障不是瞬时抖动）。"""
    calls = []

    def handler(request):
        calls.append(request.method)
        raise httpx.ProxyError("503 Service Unavailable")

    c = _client(tmp_path, transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(FrConnError):
            c._get("/webroot/decision/view/report")
        assert len(calls) == 1, f"对坏代理打了 {len(calls)} 次，应只 1 次"
        assert c.net_retries == 0
    finally:
        c.close()


def test_get_conn_reset_is_still_retried_once(tmp_path):
    """对照：连接被重置仍要重试 1 次（别把重试一起改没）。"""
    calls = []

    def handler(request):
        calls.append(request.method)
        raise httpx.RemoteProtocolError("Server disconnected without sending a response.")

    c = _client(tmp_path, transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(FrConnError):
            c._get("/webroot/decision/view/report")
        assert len(calls) == 2, f"连接重置应重试 1 次: {len(calls)}"
        assert c.net_retries == 1
    finally:
        c.close()


def test_timeout_is_not_retried_either(tmp_path):
    """对照：超时也不重试。"""
    calls = []

    def handler(request):
        calls.append(request.method)
        raise httpx.ReadTimeout("timed out")

    c = _client(tmp_path, transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(FrConnError):
            c._get("/webroot/decision/view/report")
        assert len(calls) == 1
        assert c.net_retries == 0
    finally:
        c.close()


# ==================== S2：响应型指纹 ====================

def _judge_5xx(headers: dict, tmp_path, status: int = 503) -> str:
    """返回 'proxy' / 'plain'：该响应被判成代理故障，还是原样返回给调用方。"""
    c = _client(tmp_path, transport=httpx.MockTransport(
        lambda req: httpx.Response(status, headers=headers)))
    try:
        try:
            c._get("/webroot/decision/v10/schedule/task/names")
            return "plain"
        except FrConnError as e:
            return "proxy" if _is_proxy_message(str(e)) else "plain"
    finally:
        c.close()


def test_via_only_5xx_is_not_proxy(tmp_path):
    """仅 `Via` 的 5xx 不得判成代理（平台自身 5xx 会误报）。"""
    assert _judge_5xx({"via": "1.1 platform-gateway"}, tmp_path) == "plain"


def test_proxy_status_5xx_is_proxy(tmp_path):
    """`Proxy-Status` 的 5xx 必须判成代理。"""
    assert _judge_5xx({"proxy-status": "error"}, tmp_path) == "proxy"


def test_proxy_fingerprint_only_applies_to_5xx(tmp_path):
    """指纹只对 5xx 生效：4xx 即便带 `Proxy-Status` 也不当代理链路故障。"""
    assert _judge_5xx({"proxy-status": "error"}, tmp_path, status=404) == "plain"
    assert _judge_5xx({"proxy-status": "error"}, tmp_path, status=400) == "plain"
