"""回归：`schedule log` 传错 id 来源（record/records 的 uuid/id）时，错误信息必须指回 `schedule history`。"""
from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest

from frcli.client import FineReportClient
from frcli.exceptions import ApiError


def _make_client(monkeypatch, text: str, content_type: str = "text/html"):
    client = FineReportClient.__new__(FineReportClient)
    client.config = SimpleNamespace(workspace="/webroot")
    client._get = lambda path, **kw: httpx.Response(
        200, text=text, headers={"content-type": content_type})
    monkeypatch.setattr(client, "_ensure_auth", lambda: None)
    return client


def test_log_id_from_record_gives_history_hint(monkeypatch):
    """平台对「record 的 uuid 当 logId」回 200 + 默认错误页（对象不存在）。"""
    page = ("<html><body><div class='simple-message'>Fine-Dec_Default_Error_Tip</div></body></html>")
    client = _make_client(monkeypatch, page)
    with pytest.raises(ApiError) as ei:
        client.get_schedule_log_detail("da95ec40-9399-4983-ba54-1c107ff5cd36")
    msg = str(ei.value)
    assert "schedule history" in msg
    assert "same_fire" in msg
    assert "执行记录 id" in msg


def test_log_id_from_history_returns_nodes(monkeypatch):
    body = ('{"data": {"id": "demo_task_same_fire_123", "taskName": "demo_task",'
            ' "userNodes": [{"name": "通用结果", "status": 1, "children": []}]}}')
    client = _make_client(monkeypatch, body, content_type="application/json")
    data = client.get_schedule_log_detail("demo_task_same_fire_123")
    assert data["id"] == "demo_task_same_fire_123"
    assert data["userNodes"][0]["name"] == "通用结果"
