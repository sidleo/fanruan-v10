"""运行时巡检（inspect）离线回归测试。

真实链路由 3 跳组成：run（页壳：巡检 sid + 模板 sessionID）→ page_content（触发真实计算）
→ 轮询 report（`Nx.result = JSON.parse('<JS 转义字符串>')`）。这些测试不需要连服务器，
用假的 `_request` 覆盖：页壳解析 / JS 转义解码 / 内部轮询与超时 / 错误映射 / 默认脱敏。
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import httpx
import pytest

import frcli.client as client_module
from frcli.client import (
    FineReportClient,
    INSPECTION_STATUS_TEXT,
    decode_inspection_result,
)
from frcli.commands.inspect import _shape_result, _table_rows
from frcli.exceptions import InspectionError

SHELL = (
    "<!DOCTYPE html><html><head><title>x</title></head><body>"
    '<script>window.Nx = window.Nx || {};window.Nx.sid="'
    "6f1c2d3e-4b5a-6978-8c9d-0e1f2a3b4c5d"
    '";</script>'
    '<script src="/webroot/decision/view/report?op=widget&sessionID='
    "9a8b7c6d-5e4f-4321-9abc-def012345678"
    '"></script></body></html>'
)


def _js_string_literal(payload: dict) -> str:
    """把 dict 写成平台结果页里的 JS 单引号字符串（含 `\\/`、`\\'` 等真实转义）。"""
    text = json.dumps(payload, ensure_ascii=False)
    text = text.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')
    return text.replace("/", "\\/")


def _report_page(payload: dict) -> str:
    return ("<html><body><script>Nx.result = JSON.parse('"
            + _js_string_literal(payload) + "');</script></body></html>")


SAMPLE = {
    "meta": {
        "date": 1761000000000,
        "path": "demo_group/demo_user/x.cpt",
        "para": {"FR_USERNAME": "12345678", "FINE_ROLE": ["A", "B"], "VIEWLET": "demo_group/demo_user/x.cpt"},
    },
    "extra": {
        "base": {"template-cost": 37},
        "extra": {"default set relationship": 2},
        "db fetch": [{"cost": 12}],
    },
    "cell": {"A1": {"total": 3, "formula": 1}, "B2": {"total": 9, "group": 4}},
}


def _resp(status: int = 200, text: str = "", content_type: str = "text/html") -> httpx.Response:
    return httpx.Response(status, text=text, headers={"content-type": content_type})


def _make_client(monkeypatch, responses: list):
    """构造一个只走假 `_request` 的 client；记录每次调用。"""
    client = FineReportClient.__new__(FineReportClient)
    client.config = SimpleNamespace(workspace="/webroot")
    client.net_retries = 0
    calls = []

    def fake_request(method, url, **kwargs):
        calls.append((method, url, kwargs.get("params")))
        if not responses:
            raise AssertionError(f"意外的多余请求: {method} {url}")
        return responses.pop(0)

    monkeypatch.setattr(client, "_ensure_auth", lambda: None)
    monkeypatch.setattr(client, "_request", fake_request)
    return client, calls


def test_decode_js_parse_with_js_escapes():
    payload = {"meta": {"path": "a/b"}, "extra": {"base": {"template-cost": 5}}, "cell": {"A1": {"total": 1}},
               "note": "中文\n第二行"}
    got = decode_inspection_result(_report_page(payload))
    assert got["meta"]["path"] == "a/b"
    assert got["note"] == "中文\n第二行"


def test_decode_direct_json_fallback():
    page = '<script>Nx.result = {"extra": {"base": {"template-cost": 7}}, "cell": {}};</script>'
    assert decode_inspection_result(page)["extra"]["base"]["template-cost"] == 7


def test_decode_error_page_or_unfinished_returns_none():
    assert decode_inspection_result("<html>检测未被触发</html>") is None
    with pytest.raises(InspectionError, match="未闭合"):
        decode_inspection_result("<script>Nx.result = JSON.parse('{\"a\":1}</script>")


def test_run_inspection_happy_path(monkeypatch):
    responses = [_resp(text=SHELL), _resp(text="<html>content</html>"), _resp(text=_report_page(SAMPLE))]
    client, calls = _make_client(monkeypatch, responses)
    out = client.run_inspection("demo_group/demo_user/x.cpt")
    assert out["extra"]["base"]["template-cost"] == 37
    # 三跳顺序：run → page_content（带模板 sessionID）→ report（带巡检 sid）
    assert [c[1] for c in calls] == [
        "/webroot/decision/plugin/inspect/x/run",
        "/webroot/decision/view/report",
        "/webroot/decision/plugin/inspect/x/report/6f1c2d3e-4b5a-6978-8c9d-0e1f2a3b4c5d",
    ]
    assert calls[0][2]["viewlet"] == "demo_group/demo_user/x.cpt"
    assert calls[1][2] == {"op": "page_content",
                           "sessionID": "9a8b7c6d-5e4f-4321-9abc-def012345678", "pn": 1}


def test_run_inspection_polls_until_ready(monkeypatch):
    waiting = "<html><p>检测未被触发，请首先预览模版完成触发</p></html>"
    responses = [_resp(text=SHELL), _resp(text="<html>content</html>"),
                 _resp(text=waiting), _resp(text=waiting), _resp(text=_report_page(SAMPLE))]
    client, calls = _make_client(monkeypatch, responses)
    sleeps = []
    monkeypatch.setattr(client_module.time, "sleep", lambda s: sleeps.append(s))
    out = client.run_inspection("demo_group/demo_user/x.cpt", op="view")
    assert out["extra"]["base"]["template-cost"] == 37
    # 内部自己等（退避），调用方不需要猜时间
    assert len(sleeps) == 2 and 0 < sleeps[0] <= 1 and 0 < sleeps[1] <= 1
    assert calls[0][2]["op"] == "view"


def test_run_inspection_timeout_reports_untriggered_hint(monkeypatch):
    waiting = "<html><p>检测未被触发，请首先预览模版完成触发</p></html>"
    responses = [_resp(text=SHELL), _resp(text="<html>content</html>"), _resp(text=waiting)]
    client, _ = _make_client(monkeypatch, responses)
    monkeypatch.setattr(client_module.time, "sleep", lambda s: None)
    with pytest.raises(InspectionError) as ei:
        client.run_inspection("demo_group/demo_user/x.cpt", timeout=0)
    msg = str(ei.value)
    assert "等待超时" in msg and "检测未被触发" in msg


def test_params_cannot_override_reserved_keys(monkeypatch):
    """--params 是模板参数，不能覆盖保留键 op/viewlet（否则可绕过只读白名单）。"""
    responses = [_resp(text=SHELL), _resp(text="<html>content</html>"), _resp(text=_report_page(SAMPLE))]
    client, calls = _make_client(monkeypatch, responses)
    client.run_inspection("demo_group/demo_user/x.cpt", op="page",
                          params={"op": "write_plus", "viewlet": "other.cpt", "edate": "2024-01-01"})
    assert calls[0][2]["op"] == "page"
    assert calls[0][2]["viewlet"] == "demo_group/demo_user/x.cpt"
    assert calls[0][2]["edate"] == "2024-01-01"


@pytest.mark.parametrize("bad_timeout", [float("nan"), float("inf"), float("-inf"), -5])
def test_nonfinite_or_negative_timeout_does_not_hang(monkeypatch, bad_timeout):
    """NaN/inf/负数等待上限不能变成死循环：先 poll 一次，然后按超时返回。"""
    waiting = "<html><p>检测未被触发，请首先预览模版完成触发</p></html>"
    responses = [_resp(text=SHELL), _resp(text="<html>content</html>"), _resp(text=waiting)]
    client, _ = _make_client(monkeypatch, responses)
    monkeypatch.setattr(client_module.time, "sleep", lambda s: None)
    with pytest.raises(InspectionError, match="等待超时"):
        client.run_inspection("demo_group/demo_user/x.cpt", timeout=bad_timeout)


def test_run_inspection_404_gives_plugin_hint(monkeypatch):
    responses = [_resp(404, text="<html>404</html>")]
    client, _ = _make_client(monkeypatch, responses)
    with pytest.raises(InspectionError, match="插件未安装"):
        client.run_inspection("demo_group/demo_user/x.cpt")


def test_decode_empty_json_parse_is_not_ready():
    assert decode_inspection_result("<script>Nx.result = JSON.parse('');</script>") is None


def test_decode_non_object_result_raises():
    page = "<script>Nx.result = JSON.parse('[1,2]');</script>"
    with pytest.raises(InspectionError, match="不是 JSON 对象"):
        decode_inspection_result(page)


def test_table_rows_include_db_fetch():
    shaped = _shape_result(SAMPLE, "demo_group/demo_user/x.cpt", "view", 120)
    rows = _table_rows(shaped)
    items = {r["item"]: r["value"] for r in rows}
    assert items["db fetch"] == 1


def test_run_inspection_rejects_write_ops():
    client = FineReportClient.__new__(FineReportClient)
    client.config = SimpleNamespace(workspace="/webroot")
    with pytest.raises(InspectionError, match="write"):
        client.run_inspection("demo_group/demo_user/x.cpt", op="write")


def test_run_inspection_empty_body_hints_path(monkeypatch):
    responses = [_resp(text="")]
    client, _ = _make_client(monkeypatch, responses)
    with pytest.raises(InspectionError, match="空响应"):
        client.run_inspection("demo_group/demo_user/not_exist.cpt")


def test_run_inspection_merges_template_params(monkeypatch):
    responses = [_resp(text=SHELL), _resp(text="<html>content</html>"), _resp(text=_report_page(SAMPLE))]
    client, calls = _make_client(monkeypatch, responses)
    client.run_inspection("demo_group/demo_user/x.cpt", params={"edate": "2024-01-01"})
    assert calls[0][2]["edate"] == "2024-01-01"
    assert calls[0][2]["viewlet"] == "demo_group/demo_user/x.cpt"


def test_run_inspection_missing_sid_gives_plugin_hint(monkeypatch):
    responses = [_resp(text="<html>没有权限</html>")]
    client, _ = _make_client(monkeypatch, responses)
    with pytest.raises(InspectionError, match="插件未启用"):
        client.run_inspection("demo_group/demo_user/x.cpt")


def test_cli_rejects_write_op():
    from click.testing import CliRunner

    from frcli.cli import main

    result = CliRunner().invoke(main, ["inspect", "run", "demo_group/demo_user/x.cpt", "--op", "write"])
    assert result.exit_code == 2
    assert "Invalid value for '--op'" in result.output


def test_cli_rejects_nonfinite_timeout():
    from click.testing import CliRunner

    from frcli.cli import main

    result = CliRunner().invoke(
        main, ["inspect", "run", "demo_group/demo_user/x.cpt", "--timeout", "nan"])
    assert result.exit_code == 1
    assert "INSPECTION_ERROR" in result.output
    assert "有限秒数" in result.output


def test_cli_invalid_params_message():
    from click.testing import CliRunner

    from frcli.cli import main

    result = CliRunner().invoke(
        main, ["inspect", "run", "demo_group/demo_user/x.cpt", "--params", "not-json"])
    assert result.exit_code == 1
    assert "INSPECTION_ERROR" in result.output
    assert "不是合法 JSON" in result.output


def test_status_ok(monkeypatch):
    body = json.dumps({"data": {"status": "0", "expectEntrance": ["a"], "expectMethods": ["b"]}})
    responses = [_resp(text=body, content_type="application/json")]
    client, calls = _make_client(monkeypatch, responses)
    data = client.get_inspection_status()
    assert data["status"] == "0" and INSPECTION_STATUS_TEXT["0"].startswith("正常")
    assert calls[0][1] == "/webroot/decision/plugin/inspect/status/get"


def test_status_404_plugin_hint(monkeypatch):
    responses = [_resp(404, text="<html>404</html>")]
    client, _ = _make_client(monkeypatch, responses)
    with pytest.raises(InspectionError, match="插件未安装"):
        client.get_inspection_status()


def test_status_plugin_unavailable(monkeypatch):
    responses = [_resp(text="<html><div id='detail-message'>Fine-Dec_No_Privilege_Access_Page</div></html>")]
    client, _ = _make_client(monkeypatch, responses)
    with pytest.raises(InspectionError, match="插件不可用"):
        client.get_inspection_status()


def test_shape_result_strips_personal_meta():
    shaped = _shape_result(SAMPLE, "demo_group/demo_user/x.cpt", "page", 120)
    dumped = json.dumps(shaped, ensure_ascii=False)
    assert "FR_USERNAME" not in dumped and "FINE_ROLE" not in dumped
    assert shaped["template_cost_ms"] == 37 and shaped["cells"] == 2
    # 原始 JSON 里有，--raw 才输出
    assert SAMPLE["meta"]["para"]["FR_USERNAME"] == "12345678"


def test_table_rows_include_overall_and_slow_cells():
    shaped = _shape_result(SAMPLE, "demo_group/demo_user/x.cpt", "page", 120)
    rows = _table_rows(shaped)
    items = {r["item"]: r["value"] for r in rows}
    assert items["template-cost (ms)"] == 37 and items["cells"] == 2
    assert any(k.startswith("cell B2") and v == 9 for k, v in items.items())
