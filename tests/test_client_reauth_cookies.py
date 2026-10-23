"""回归：认证失效后采纳「别的进程刚刷好的 token」时，必须连 cookies 一起灌回 http client。

实测：本平台只带 Authorization、不带 cookies 的请求会 302 到 CAS，而且这次 302 会把该 token 一并吊销——
所以「采纳 token 但不带 cookies」比不采纳更糟：会把别的进程刚登好的 token 打死，引发连环重登。
"""
from __future__ import annotations

import json
import time
from pathlib import Path
import httpx

from frcli.auth import TokenManager
from frcli.client import FineReportClient
from frcli.models import ServerConfig


class _Cookies(dict):
    def set(self, name, value):
        self[name] = value


class _FakeHTTP:
    def __init__(self, responses):
        self.headers = {}
        self.cookies = _Cookies()
        self._responses = list(responses)
        self.calls = []

    def request(self, method, path, **kwargs):
        self.calls.append((method, path))
        return self._responses.pop(0)


def _client(tmp_path, responses):
    cfg = ServerConfig(name="itest", url="http://127.0.0.1:1", username="u",
                       password="p", token_file=tmp_path / "itest.json")
    client = FineReportClient.__new__(FineReportClient)
    client.config = cfg
    client.token_mgr = TokenManager(cfg)
    client._http = _FakeHTTP(responses)
    client._authenticated = True       # 跳过 _ensure_auth，直接走请求→认证失效→重登路径
    client.relogged = False
    client.net_retries = 0
    return client


def _cas_redirect() -> httpx.Response:
    return httpx.Response(302, headers={"location": "https://sso.example.com/cas/login?service=x"})


def test_reauth_adopting_other_process_token_also_applies_cookies(tmp_path):
    token_file = tmp_path / "itest.json"
    # 另一个进程已经写好新 token + cookies
    token_file.write_text(json.dumps({
        "instance": "itest", "token": "new-token",
        "expires_at": time.time() + 86400, "created_at": time.time(),
        "cookies": {"tenantId": "t1"},
    }))
    client = _client(tmp_path, [_cas_redirect(), httpx.Response(200, text="[]")])
    # 本进程内存里还是失效的旧 token（缓存里是别的进程的新 token）
    client.token_mgr._token = "stale-token"
    client.token_mgr._expires_at = time.time() + 86400
    client.token_mgr._cookies = {"tenantId": "old"}

    resp = client._get("/decision/v10/templates/all")

    assert resp.status_code == 200
    assert client.token_mgr.get_valid_token() == "new-token"      # 采纳了别人的 token
    assert client._http.headers["Authorization"] == "Bearer new-token"
    assert client._http.cookies.get("tenantId") == "t1"            # ← 关键：cookies 必须一起带上
    assert client.relogged is True
    assert len(client._http.calls) == 2                            # 302 后重试了一次
