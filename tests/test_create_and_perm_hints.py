"""schedule create 载荷规范化 + report 权限/空列表提示的回归（学自 2026-10-28 真实会话）。"""
from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from click.testing import CliRunner

from frcli.client import (
    FineReportClient,
    _taskstate_object_hint,
    normalize_create_config,
)
from frcli.commands import report as report_cmd
from frcli.exceptions import ApiError, ReportNotFoundError
from frcli.models import ServerConfig

BASE = "/webroot/decision/v10"


def _mock_client(handler):
    import tempfile

    config = ServerConfig(
        name="test",
        url="http://localhost:8705",
        username="admin",
        password="pwd",
        token_file=Path(tempfile.mkdtemp(prefix="frcli-create-")) / "test.json",
    )
    client = FineReportClient(config)
    client._http.close()
    client._http = httpx.Client(
        base_url="http://localhost:8705",
        transport=httpx.MockTransport(handler),
        follow_redirects=False,
    )
    client.token_mgr.get_valid_token = lambda: "stale-token"
    client.token_mgr._save_cached_token = lambda *a, **k: None
    return client


# ---------------------------------------------------------------- create 规范化

def test_normalize_create_config_taskstate_object_and_readonly():
    cfg = {
        "taskName": "t",
        "taskState": {"value": 1},
        "nextFireTime": "x",
        "preFireTime": "y",
        "editable": True,
        "originTaskId": "z",
    }
    out = normalize_create_config(cfg)
    assert out["taskState"] == 1
    for key in ("nextFireTime", "preFireTime", "editable", "originTaskId"):
        assert key not in out
    # 不改调用方传入的 dict
    assert cfg["taskState"] == {"value": 1}
    assert "nextFireTime" in cfg


@pytest.mark.parametrize(
    "bad,expected",
    [({"value": "1"}, 1), ({"value": None}, 0), ("paused", 0), (None, 0), (True, 0), ([1], 0)],
)
def test_normalize_create_config_taskstate_bad_types(bad, expected):
    assert normalize_create_config({"taskState": bad})["taskState"] == expected


def test_create_schedule_posts_normalized_payload():
    seen = {}

    def handler(request):
        assert request.url.path == BASE + "/schedule/task"
        seen["json"] = json.loads(request.content)
        return httpx.Response(200, json={"data": "success"})

    client = _mock_client(handler)
    result = client.create_schedule(
        {"taskName": "t", "taskState": {"value": 0}, "nextFireTime": "x"})
    assert result == "success"
    assert seen["json"]["taskState"] == 0
    assert "nextFireTime" not in seen["json"]


def test_create_schedule_taskstate_error_adds_actionable_hint():
    def handler(request):
        body = (
            '<html><body><div class="detail-message">创建定时任务失败: '
            "Cannot deserialize instance of `com.fr.schedule.base.type.TaskState` out of "
            "START_OBJECT token</div></body></html>"
        )
        return httpx.Response(200, text=body, headers={"content-type": "text/html"})

    client = _mock_client(handler)
    with pytest.raises(ApiError) as ei:
        client.create_schedule({"taskName": "t"})
    message = str(ei.value)
    assert "taskState" in message and "0（启用）" in message


def test_taskstate_object_hint_ignores_other_errors():
    assert _taskstate_object_hint("其他错误") == ""


# ---------------------------------------------------------------- report 提示

class _FakeClient:
    def __init__(self):
        self.reports = []
        self.raise_on_datasets = None
        self.raise_on_download = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def list_reports(self, *args, **kwargs):
        return self.reports

    def get_report_datasets(self, *args, **kwargs):
        if self.raise_on_datasets:
            raise self.raise_on_datasets
        return []

    def download_report(self, *args, **kwargs):
        if self.raise_on_download:
            raise self.raise_on_download
        return "/tmp/x.cpt"


def test_report_list_empty_prints_permission_hint(monkeypatch):
    fake = _FakeClient()
    monkeypatch.setattr(report_cmd, "get_client", lambda inst=None: fake)
    res = CliRunner().invoke(report_cmd.report_group, ["list", "some/dir"])
    assert "无该目录权限" in res.stderr and "报表不存在" in res.stderr


def test_report_datasets_permission_error_prints_hint(monkeypatch):
    fake = _FakeClient()
    fake.raise_on_datasets = ApiError(
        "读取报表数据集 x 失败: 当前账号无此接口权限（该接口需管理员）")
    monkeypatch.setattr(report_cmd, "get_client", lambda inst=None: fake)
    res = CliRunner().invoke(report_cmd.report_group, ["datasets", "some_dir/x.cpt"])
    assert "平台元数据表" in res.stderr


def test_report_download_not_found_prints_hint(monkeypatch):
    fake = _FakeClient()
    fake.raise_on_download = ReportNotFoundError(
        "下载失败（服务端无此文件，或该路径不在账号的远程设计授权目录内）: reportlets/x.cpt")
    monkeypatch.setattr(report_cmd, "get_client", lambda inst=None: fake)
    res = CliRunner().invoke(
        report_cmd.report_group, ["download", "x.cpt", "-o", "/tmp/y.cpt"])
    assert "平台元数据表" in res.stderr


def test_ws_list_empty_prints_hint(monkeypatch):
    monkeypatch.setattr(report_cmd, "load_config", lambda inst=None: None)
    monkeypatch.setattr(
        report_cmd, "workspace_list",
        lambda cfg, path: {"action": "ws-list", "path": path or "/", "count": 0, "entries": []})
    res = CliRunner().invoke(report_cmd.report_group, ["ws-list", "nope"])
    assert "路径不存在" in res.stderr
