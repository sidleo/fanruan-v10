"""远程设计通道（RD）的传输失败必须走统一分类，超时变量必须是 FRCLI_RD_TIMEOUT。

背景（真实用户会话）：`frcli report image <复杂模板>` 撞到
`远程设计请求失败: Server disconnected without sending a response.` ——
同样是被对端重置，请求跳会提示「原样重试、调超时无效」，RD 跳却只给裸异常；
而 RD 的超时读的是 `FRCLI_RD_TIMEOUT`（默认 300s），不是 `FRCLI_TIMEOUT` ——
照旧文案调 `FRCLI_TIMEOUT` 对它毫无效果。RD 与请求跳共用 `neterr.net_hint`，
但必须把超时变量参数化成 RD 自己的。

全离线：假 http client 直接抛 httpx 异常，不打网络。
"""
from __future__ import annotations

import httpx
import pytest

from frcli.exceptions import ConnectionError as FrConnError
from frcli.neterr import net_hint
from frcli.remotedesign import RemoteDesignSession

RD = dict(timeout_env="FRCLI_RD_TIMEOUT", timeout_default="300")


class _FakeHttp:
    def __init__(self, exc):
        self.exc = exc

    def post(self, *args, **kwargs):
        raise self.exc


def _session(exc):
    sess = object.__new__(RemoteDesignSession)
    sess._http = _FakeHttp(exc)
    return sess


# -- net_hint：请求跳默认行为不变，RD 用对变量 ---------------------------------

def test_request_path_default_hint_unchanged(monkeypatch):
    """默认调用（请求跳）的文案仍是 FRCLI_TIMEOUT / 30.0s —— 不能因为参数化而改变。

    必须清掉开发机上可能 export 的 FRCLI_TIMEOUT，否则这条守卫会假红（仓库文档正好教人 export 它）。
    """
    monkeypatch.delenv("FRCLI_TIMEOUT", raising=False)
    hint = net_hint(httpx.ReadTimeout("timed out"))
    assert "用 `FRCLI_TIMEOUT=600 frcli ...` 调大" in hint
    assert "当前超时 30.0s" in hint


def test_request_path_proxy_hint_byte_identical():
    """请求跳的代理文案必须逐字符保留旧版（0.10.8）—— 参数化不得改动既有输出。"""
    hint = net_hint(httpx.ProxyError("503 Service Unavailable"))
    assert "不必改报表参数，也不必调大 FRCLI_TIMEOUT。" in hint, hint


def test_rd_timeout_hint_uses_rd_env(monkeypatch):
    """RD 超时提示必须指向 FRCLI_RD_TIMEOUT（默认 300s），而不是 FRCLI_TIMEOUT。"""
    monkeypatch.delenv("FRCLI_RD_TIMEOUT", raising=False)
    hint = net_hint(httpx.ReadTimeout("timed out"), **RD)
    assert "用 `FRCLI_RD_TIMEOUT=600 frcli ...` 调大" in hint, hint
    assert "当前超时 300s" in hint, hint
    assert "用 `FRCLI_TIMEOUT=600" not in hint, f"RD 提示里不该出现 FRCLI_TIMEOUT: {hint}"


def test_rd_timeout_hint_reads_current_rd_env(monkeypatch):
    """提示里的"当前超时"要读 RD 自己的环境变量。"""
    monkeypatch.setenv("FRCLI_RD_TIMEOUT", "450")
    hint = net_hint(httpx.ReadTimeout("timed out"), **RD)
    assert "当前超时 450s" in hint, hint


# -- net_hint：三分支在 RD 变量下都成立 ----------------------------------------

def test_rd_reset_hint_says_retry_not_timeout():
    hint = net_hint(
        httpx.RemoteProtocolError("Server disconnected without sending a response."), **RD)
    assert "连接被对端重置/断开" in hint, hint
    assert "原样重试" in hint, hint
    assert "调大 FRCLI_RD_TIMEOUT 无效" in hint, hint


def test_rd_proxy_hint_names_proxy_hop():
    hint = net_hint(httpx.ProxyError("503 Service Unavailable"), **RD)
    assert "代理这一跳" in hint, hint
    # 代理故障与超时无关，且 RD 跳的变量是 FRCLI_RD_TIMEOUT —— 不能再单体点名 FRCLI_TIMEOUT
    assert "FRCLI_TIMEOUT" not in hint, f"RD 代理提示仍在指错超时变量: {hint}"
    assert "FRCLI_RD_TIMEOUT。" in hint, hint


# -- remotedesign._post：真实调用点确实套上了分类 ------------------------------

def test_rd_post_timeout_message_is_actionable():
    with pytest.raises(FrConnError) as ei:
        _session(httpx.ReadTimeout("timed out"))._post("/decision/remote/design/check")
    msg = str(ei.value)
    assert "远程设计请求失败" in msg, msg
    assert "FRCLI_RD_TIMEOUT=600" in msg, msg


def test_rd_post_reset_message_is_actionable():
    with pytest.raises(FrConnError) as ei:
        _session(httpx.RemoteProtocolError(
            "Server disconnected without sending a response."))._post("/decision/remote/design/channel")
    msg = str(ei.value)
    assert "远程设计请求失败" in msg, msg
    assert "连接被对端重置/断开" in msg, msg
    assert "原样重试" in msg, msg


def test_rd_post_proxy_message_is_actionable():
    with pytest.raises(FrConnError) as ei:
        _session(httpx.ProxyError("503 Service Unavailable"))._post("/decision/remote/design/check")
    msg = str(ei.value)
    assert "代理这一跳" in msg, msg


# -- 变异守卫：默认值/兜底分支/会话超时常量必须同源 ------------------------------

def test_rd_post_default_timeout_is_300(monkeypatch):
    """`_post` 必须用 RD 默认 300s 生成提示（变异成 30.0 时本条会挂）。"""
    monkeypatch.delenv("FRCLI_RD_TIMEOUT", raising=False)
    with pytest.raises(FrConnError) as ei:
        _session(httpx.ReadTimeout("timed out"))._post("/decision/remote/design/check")
    assert "当前超时 300s" in str(ei.value), str(ei.value)


def test_rd_fallback_branch_uses_rd_env(monkeypatch):
    """非超时非重置的传输错误走兜底分支，也必须指向 FRCLI_RD_TIMEOUT（变异成硬编码会挂）。"""
    monkeypatch.delenv("FRCLI_RD_TIMEOUT", raising=False)
    hint = net_hint(httpx.ConnectError("boom"), **RD)
    assert "FRCLI_RD_TIMEOUT=600" in hint, hint
    assert "当前超时 300s" in hint, hint


def test_rd_session_default_timeout_matches_hint_default(monkeypatch):
    """`RemoteDesignSession` 的真实默认超时与提示里的默认值必须同源（都 300s）。

    必须清掉开发机上可能 export 的 FRCLI_RD_TIMEOUT，否则构造出的会话超时不是默认值。
    """
    monkeypatch.delenv("FRCLI_RD_TIMEOUT", raising=False)
    import types
    cfg = types.SimpleNamespace(url="http://127.0.0.1:1", workspace="/webroot")
    sess = RemoteDesignSession(cfg)
    try:
        assert sess._http.timeout.read == 300, sess._http.timeout
        assert sess._http.timeout.connect == 300, sess._http.timeout
    finally:
        sess.close()
