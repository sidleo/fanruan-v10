"""回归：导出撞平台网关 5xx（502/503/504）时，错误信息必须可操作（降并发/重试），不能只给状态码。"""
from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest

from frcli.client import FineReportClient
from frcli.exceptions import ExportError


def _make_client(monkeypatch, status: int):
    client = FineReportClient.__new__(FineReportClient)
    client.config = SimpleNamespace(workspace="/webroot")
    client.net_retries = 0
    monkeypatch.setattr(client, "_ensure_auth", lambda: None)
    monkeypatch.setattr(client, "_request", lambda *a, **k: httpx.Response(status, text="<html>gateway</html>"))
    return client


@pytest.mark.parametrize("status", [502, 503, 504])
def test_gateway_5xx_export_message_has_actionable_hint(tmp_path, monkeypatch, status):
    client = _make_client(monkeypatch, status)
    with pytest.raises(ExportError) as ei:
        client.export_report("demo_group/demo_user/x.cpt", "excel", str(tmp_path / "x.xlsx"))
    msg = str(ei.value)
    assert f"HTTP {status}" in msg
    assert "降低并发" in msg and "重试" in msg
    assert "不要改报表参数" in msg


def test_other_http_error_keeps_plain_message(tmp_path, monkeypatch):
    """非网关 5xx 不加误导性提示（普通 HTTP 错误保持原样）。"""
    client = _make_client(monkeypatch, 500)
    with pytest.raises(ExportError) as ei:
        client.export_report("demo_group/demo_user/x.cpt", "excel", str(tmp_path / "x.xlsx"))
    assert str(ei.value) == "导出失败: HTTP 500"
