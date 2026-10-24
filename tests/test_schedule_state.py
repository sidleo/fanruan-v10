"""定时任务暂停/恢复、改模板与执行记录排序的回归。

真机语义（2026-10-24 在平台实测）：
- `POST /schedule/task/{id}/state` 是**切换**接口：body 里的 value 被忽略，每次调用把
  taskState 取反（0=启用 1=暂停），所以客户端必须“先读、按需切一次、再回读”。
- `PUT /schedule/task` 会**重置 taskState 为 0**；且 creator 若不在请求体里会被平台清空。
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from click.testing import CliRunner

from frcli.client import FineReportClient
from frcli.commands import schedule as schedule_cmd
from frcli.exceptions import ApiError, ScheduleError
from frcli.models import ServerConfig

BASE = "/webroot/decision/v10"


def _mock_client(handler):
    import tempfile

    config = ServerConfig(
        name="test",
        url="http://localhost:8705",
        username="admin",
        password="pwd",
        token_file=Path(tempfile.mkdtemp(prefix="frcli-schedule-")) / "test.json",
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


def _task_data(task_id="tid-1", name="demo_task", state=0, creator="u1", template="demo/a.cpt"):
    return {
        "id": task_id,
        "taskName": name,
        "taskDescription": "old",
        "templatePath": template,
        "creator": creator,
        "taskState": {"value": state},
    }


def test_set_schedule_state_toggles_once_and_verifies():
    calls = {"state": 0, "posts": []}

    def handler(request):
        if request.url.path == f"{BASE}/schedule/task/search":
            return httpx.Response(200, json={"data": {"items": [_task_data(state=calls["state"])]}})
        if request.url.path == f"{BASE}/schedule/task/tid-1/state":
            calls["posts"].append(request.content)
            calls["state"] = 1 - calls["state"]  # 平台是“切换”
            return httpx.Response(200, json={"data": {"value": calls["state"]}})
        raise AssertionError(f"unexpected {request.method} {request.url.path}")

    client = _mock_client(handler)
    try:
        out = client.set_schedule_state("demo_task", paused=True)
    finally:
        client.close()
    assert out["changed"] is True and out["task_state"] == 1
    assert len(calls["posts"]) == 1
    assert b'"value":1' in calls["posts"][0].replace(b" ", b"")


def test_set_schedule_state_is_noop_when_already_paused():
    posts = []

    def handler(request):
        if request.url.path == f"{BASE}/schedule/task/search":
            return httpx.Response(200, json={"data": {"items": [_task_data(state=1)]}})
        if request.url.path.endswith("/state"):
            posts.append(1)
            return httpx.Response(200, json={"data": {"value": 0}})
        raise AssertionError(request.url.path)

    client = _mock_client(handler)
    try:
        out = client.set_schedule_state("demo_task", paused=True)
    finally:
        client.close()
    assert out["changed"] is False and out["task_state"] == 1
    assert posts == []  # 已经是暂停，不该再切


def test_set_schedule_state_raises_when_readback_mismatch():
    def handler(request):
        if request.url.path == f"{BASE}/schedule/task/search":
            return httpx.Response(200, json={"data": {"items": [_task_data(state=0)]}})
        if request.url.path.endswith("/state"):
            return httpx.Response(200, json={"data": {"value": 1}})
        raise AssertionError(request.url.path)

    # 切换接口返回 1，但回读仍是 0（模拟平台异步/失败）
    client = _mock_client(handler)
    client.get_schedule = lambda name: _task_data(state=0)
    try:
        with pytest.raises(ApiError, match="切换未生效"):
            client.set_schedule_state("demo_task", paused=True)
    finally:
        client.close()


def test_update_schedule_keeps_creator_and_strips_readonly():
    seen = {}

    def handler(request):
        assert request.method == "PUT"
        import json as _json
        seen["body"] = _json.loads(request.content)
        return httpx.Response(200, json={"data": "success"})

    client = _mock_client(handler)
    cfg = {
        "id": "tid-1", "taskName": "demo_task", "creator": "u1",
        "templatePath": "demo/b.cpt", "nextFireTime": "2026-01-01 00:00:00",
        "preFireTime": "2025-12-31", "editable": False, "taskState": {"value": 1},
        "originTaskId": "",
    }
    try:
        assert client.update_schedule("tid-1", cfg) is True
    finally:
        client.close()
    body = seen["body"]
    assert body["creator"] == "u1"  # 必须回传，否则平台清空
    assert "taskState" not in body and "nextFireTime" not in body
    assert body["id"] == "tid-1"


def test_get_schedule_resolves_task_id_via_list_all():
    def handler(request):
        if request.url.path == f"{BASE}/schedule/task/search":
            import json as _json
            name = _json.loads(request.content).get("taskName")
            if name == "demo_task":
                return httpx.Response(200, json={"data": {"items": [_task_data()]}})
            return httpx.Response(200, json={"data": {"items": []}})
        if request.url.path == f"{BASE}/schedule/task/listAll/2":
            return httpx.Response(200, json={"data": [
                {"taskName": "demo_task", "taskId": "tid-1", "id": None}]})
        raise AssertionError(request.url.path)

    client = _mock_client(handler)
    try:
        task = client.get_schedule("00000000-0000-0000-0000-000000000001")
    finally:
        client.close()
    assert task == {}  # 未知 id 不在 listAll 里


def test_get_schedule_by_known_task_id_resolves_name():
    def handler(request):
        if request.url.path == f"{BASE}/schedule/task/search":
            import json as _json
            name = _json.loads(request.content).get("taskName")
            if name == "demo_task":
                return httpx.Response(200, json={"data": {"items": [_task_data()]}})
            return httpx.Response(200, json={"data": {"items": []}})
        if request.url.path == f"{BASE}/schedule/task/listAll/2":
            return httpx.Response(200, json={"data": [
                {"taskName": "demo_task",
                 "taskId": "11111111-2222-3333-4444-555555555555", "id": None}]})
        raise AssertionError(request.url.path)

    client = _mock_client(handler)
    try:
        task = client.get_schedule("11111111-2222-3333-4444-555555555555")
    finally:
        client.close()
    assert task and task["taskName"] == "demo_task"


def test_search_schedule_records_all_records_sorts_by_time_desc():
    pages = {
        1: [{"time": 100, "logTime": "old"}, {"time": 300, "logTime": "new"}],
        2: [{"time": 200, "logTime": "mid"}],
    }

    def handler(request):
        import json as _json
        page = _json.loads(request.content)["page"]
        return httpx.Response(200, json={"data": {
            "total": 3, "page": page, "items": pages[page]}})

    client = _mock_client(handler)
    try:
        out = client.search_schedule_records("demo_task", per_page=2, all_records=True)
    finally:
        client.close()
    assert [x["time"] for x in out["items"]] == [300, 200, 100]
    assert out["total"] == 3


class _FakeTaskClient:
    def __init__(self, task=None, state=1):
        self.task = task or _task_data(state=state)
        self.state = state
        self.updates = []
        self.state_calls = []
        self.raise_not_found = False
        self.report_exists_result = True
        self.hide_after_update = False
        self.hide_id_after_update = False
        self.restore_fail = False
        self.after_creator = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_schedule(self, name):
        if self.raise_not_found:
            return {}
        if self.hide_after_update and self.updates:
            return {}
        if self.hide_id_after_update and self.updates and name == self.task.get("id"):
            return {}
        t = dict(self.task)
        t["taskState"] = {"value": self.state}
        return t

    def report_exists(self, path):
        return self.report_exists_result

    def update_schedule(self, task_id, cfg):
        self.updates.append(cfg)
        if getattr(self, "update_result", True) is False:
            return False
        self.task["templatePath"] = cfg.get("templatePath")
        self.task["taskDescription"] = cfg.get("taskDescription")
        if self.after_creator is not None:
            self.task["creator"] = self.after_creator
        self.state = 0  # 平台 PUT 会重置为启用
        return True

    def set_schedule_state(self, task_name, paused):
        if self.restore_fail:
            raise RuntimeError("state endpoint boom")
        self.state_calls.append(paused)
        self.state = 1 if paused else 0
        return {"action": "pause" if paused else "resume", "changed": True, "task_state": self.state}


def _patch_client(monkeypatch, fake):
    monkeypatch.setattr(schedule_cmd, "get_client", lambda instance: fake)


def test_cli_pause_and_resume(monkeypatch):
    fake = _FakeTaskClient(state=0)
    _patch_client(monkeypatch, fake)
    res = CliRunner().invoke(schedule_cmd.schedule_group, ["pause", "demo_task"])
    assert res.exit_code == 0, res.output
    assert '"action": "pause"' in res.output and '"task_state": 1' in res.output
    res = CliRunner().invoke(schedule_cmd.schedule_group, ["resume", "demo_task"])
    assert res.exit_code == 0, res.output
    assert '"action": "resume"' in res.output and '"task_state": 0' in res.output


def test_cli_update_template_preserves_paused_state(monkeypatch):
    fake = _FakeTaskClient(state=1)
    _patch_client(monkeypatch, fake)
    res = CliRunner().invoke(
        schedule_cmd.schedule_group,
        ["update", "demo_task", "--template", "demo/new.cpt"],
    )
    assert res.exit_code == 0, res.output
    assert fake.updates and fake.updates[0]["templatePath"] == "demo/new.cpt"
    assert fake.state_calls == [True]  # 原来暂停，PUT 后自动切回暂停
    assert '"paused_state_restored": true' in res.output
    assert '"taskState": 1' in res.output


def test_cli_update_requires_some_option(monkeypatch):
    _patch_client(monkeypatch, _FakeTaskClient())
    res = CliRunner().invoke(schedule_cmd.schedule_group, ["update", "demo_task"])
    assert res.exit_code == 1
    assert "--description 或 --template" in res.output


def test_cli_get_unknown_uuid_hints_task_name(monkeypatch):
    fake = _FakeTaskClient()
    fake.raise_not_found = True
    _patch_client(monkeypatch, fake)
    res = CliRunner().invoke(
        schedule_cmd.schedule_group,
        ["get", "11111111-2222-3333-4444-555555555555"])
    assert res.exit_code == 1
    assert "看起来是 taskId" in res.output and "任务名" in res.output


def test_cli_tasks_hints_has_next(monkeypatch):
    class C:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def list_schedule_tasks(self, *a, **k):
            return {"hasNext": True, "items": [{"taskName": "t1"}]}

    monkeypatch.setattr(schedule_cmd, "get_client", lambda instance: C())
    res = CliRunner().invoke(schedule_cmd.schedule_group, ["tasks"])
    assert res.exit_code == 0
    assert "hasNext" in res.stderr or "--all" in res.stderr


def test_cli_history_hints_ascending_and_limit(monkeypatch):
    class C:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def get_schedule_history(self, task_name, limit):
            return [_task_data() for _ in range(limit)]

    monkeypatch.setattr(schedule_cmd, "get_client", lambda instance: C())
    res = CliRunner().invoke(schedule_cmd.schedule_group, ["history", "demo_task", "-n", "3"])
    assert res.exit_code == 0
    assert "升序" in res.stderr and "最早" in res.stderr


def test_inspect_db_fetch_truncation_helper():
    from frcli.commands.inspect import _db_fetch_sql_truncated

    assert _db_fetch_sql_truncated({"extra": {"db fetch": {"ds1": {"sql": "x" * 500}}}})
    assert not _db_fetch_sql_truncated({"extra": {"db fetch": {"ds1": {"sql": "x" * 499}}}})
    assert not _db_fetch_sql_truncated({"extra": {}})


def test_update_schedule_rejects_platform_error_page():
    """PUT 返回 200 + HTML 出错页时不能报成功（平台错误一律 200）。"""
    def handler(request):
        return httpx.Response(200, text="<html><title></title><div id='detail-message'>bad body</div></html>")

    client = _mock_client(handler)
    cfg = {"id": "tid-1", "taskName": "demo_task", "creator": "u1", "templatePath": "demo/b.cpt"}
    try:
        with pytest.raises(ApiError):
            client.update_schedule("tid-1", cfg)
    finally:
        client.close()


def test_search_schedule_records_sort_tolerates_string_time():
    def handler(request):
        import json as _json
        page = _json.loads(request.content)["page"]
        items = {1: [{"time": "300"}, {"time": 100}], 2: [{"time": None}]}[page]
        return httpx.Response(200, json={"data": {"total": 3, "page": page, "items": items}})

    client = _mock_client(handler)
    try:
        out = client.search_schedule_records("demo_task", per_page=2, all_records=True)
    finally:
        client.close()
    assert [x.get("time") for x in out["items"]] == ["300", 100, None]


def test_cli_update_errors_when_platform_does_not_confirm(monkeypatch):
    fake = _FakeTaskClient(state=0)
    fake.update_result = False
    _patch_client(monkeypatch, fake)
    res = CliRunner().invoke(
        schedule_cmd.schedule_group,
        ["update", "demo_task", "--template", "demo/new.cpt"],
    )
    assert res.exit_code == 1
    assert "平台未确认更新" in res.output


# ---------- 验证者 findings 回归（F1/F2/F3/F4/F5/F10 + G1-G4） ----------

def test_cli_update_blocks_nonexistent_template(monkeypatch):
    """F5: 平台接受任意 templatePath；CLI 必须拦下不存在的模板路径。"""
    fake = _FakeTaskClient(state=1)
    fake.report_exists_result = False
    _patch_client(monkeypatch, fake)
    res = CliRunner().invoke(
        schedule_cmd.schedule_group, ["update", "demo_task", "--template", "demo/nope.cpt"])
    assert res.exit_code == 1
    assert "模板不存在" in res.output
    assert fake.updates == []  # 未发 PUT


def test_cli_update_requires_exact_task_name(monkeypatch):
    """F10: task/search 是子串模糊搜索，写操作必须要求名字精确匹配。"""
    fake = _FakeTaskClient(state=0)
    _patch_client(monkeypatch, fake)
    res = CliRunner().invoke(
        schedule_cmd.schedule_group, ["update", "demo", "--description", "x"])
    assert res.exit_code == 1
    assert "不完全匹配" in res.output
    assert fake.updates == []


def test_cli_update_refuses_unknown_task_state(monkeypatch):
    """F3: taskState 非 0/1（实测 2=已结束/停止）时拒绝 PUT，避免静默重启。"""
    fake = _FakeTaskClient(state=2)
    _patch_client(monkeypatch, fake)
    res = CliRunner().invoke(
        schedule_cmd.schedule_group, ["update", "demo_task", "--description", "x"])
    assert res.exit_code == 1
    assert "不是 0/1" in res.output and fake.updates == []


def test_cli_update_enabled_task_is_not_paused(monkeypatch):
    """G3: 原本启用的任务 update 后必须保持启用（不误暂停）。"""
    fake = _FakeTaskClient(state=0)
    _patch_client(monkeypatch, fake)
    res = CliRunner().invoke(
        schedule_cmd.schedule_group, ["update", "demo_task", "--description", "x"])
    assert res.exit_code == 0, res.output
    assert '"paused_state_restored": false' in res.output
    assert fake.state_calls == []
    assert fake.state == 0


def test_cli_update_readback_failure_is_not_reported_as_creator(monkeypatch):
    """F1: PUT 后回读失败不能误报「creator 被清空」，也不能静默。"""
    fake = _FakeTaskClient(state=1)
    fake.hide_after_update = True
    fake.restore_fail = True
    _patch_client(monkeypatch, fake)
    res = CliRunner().invoke(
        schedule_cmd.schedule_group, ["update", "demo_task", "--description", "x"])
    assert res.exit_code == 1
    assert "回读失败" in res.output and "creator 被清空" not in res.output


def test_cli_update_restore_pause_failure_reports_state(monkeypatch):
    """F2: 恢复暂停失败时错误信息要说明当前状态并给人工命令。"""
    fake = _FakeTaskClient(state=1)
    fake.restore_fail = True
    _patch_client(monkeypatch, fake)
    res = CliRunner().invoke(
        schedule_cmd.schedule_group, ["update", "demo_task", "--description", "x"])
    assert res.exit_code == 1
    assert "恢复暂停失败" in res.output and "schedule pause" in res.output


def test_cli_update_creator_clear_is_error(monkeypatch):
    """G2: 回读成功但 creator 被平台清空 → 必须报错，不能静默成功。"""
    fake = _FakeTaskClient(state=0)
    fake.after_creator = ""
    _patch_client(monkeypatch, fake)
    res = CliRunner().invoke(
        schedule_cmd.schedule_group, ["update", "demo_task", "--description", "x"])
    assert res.exit_code == 1
    assert "creator 被清空" in res.output


def test_cli_record_non_all_hint_and_sorted_page(monkeypatch):
    """F4/G1: 非 --all 也要按 time 倒序，并提示只有当前页。"""
    class C:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def search_schedule_records(self, task_name, page, limit, all_records=False):
            assert all_records is False
            return {"total": 5, "page": 1, "perPage": 2,
                    "items": [{"time": 300}, {"time": 100}]}

    monkeypatch.setattr(schedule_cmd, "get_client", lambda instance: C())
    res = CliRunner().invoke(schedule_cmd.schedule_group, ["record", "demo_task"])
    assert res.exit_code == 0
    assert "只查了当前页" in res.stderr


def test_client_record_page_sorted_even_without_all():
    def handler(request):
        import json as _json
        page = _json.loads(request.content)["page"]
        return httpx.Response(200, json={"data": {
            "total": 3, "page": page, "items": [{"time": 100}, {"time": 300}]}})

    client = _mock_client(handler)
    try:
        out = client.search_schedule_records("demo_task", per_page=2)
    finally:
        client.close()
    assert [x["time"] for x in out["items"]] == [300, 100]


def test_inspect_cli_stderr_hint_and_stdout_json(monkeypatch):
    """G4: inspect 的 500 字符提示只进 stderr，stdout 必须是合法 JSON。"""
    import json as _json
    from frcli.commands import inspect as inspect_cmd

    class C:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def run_inspection(self, report_path, op, params, timeout):
            return {
                "template": report_path, "op": op, "elapsed_ms": 1,
                "template_cost_ms": 1, "cells": {},
                "extra": {"extra": {}, "db fetch": {"ds1": {"sql": "x" * 500}}},
                "meta": {},
            }

    monkeypatch.setattr(inspect_cmd, "get_client", lambda instance: C())
    res = CliRunner().invoke(inspect_cmd.inspect_group, ["run", "demo/a.cpt"])
    assert res.exit_code == 0, res.output
    assert "截断" in res.stderr
    data = _json.loads(res.stdout)  # stdout 未被提示污染
    assert data["db_fetch"]["ds1"]["sql"].startswith("x")


def test_cli_pause_requires_exact_task_name(monkeypatch):
    """R2-1: pause 也要精确匹配，模糊名不能改任务。"""
    fake = _FakeTaskClient(state=0)
    _patch_client(monkeypatch, fake)
    res = CliRunner().invoke(schedule_cmd.schedule_group, ["pause", "demo"])
    assert res.exit_code == 1
    assert "不完全匹配" in res.output
    assert fake.state_calls == []


def test_cli_resume_requires_exact_task_name(monkeypatch):
    """R2-1: resume 也要精确匹配。"""
    fake = _FakeTaskClient(state=1)
    _patch_client(monkeypatch, fake)
    res = CliRunner().invoke(schedule_cmd.schedule_group, ["resume", "demo"])
    assert res.exit_code == 1
    assert "不完全匹配" in res.output
    assert fake.state_calls == []


def test_cli_update_readback_falls_back_to_name(monkeypatch):
    """G5/X1: 按 id 回读为空时应回退按任务名回读并成功完成。"""
    fake = _FakeTaskClient(state=0)
    fake.hide_id_after_update = True
    _patch_client(monkeypatch, fake)
    res = CliRunner().invoke(
        schedule_cmd.schedule_group, ["update", "demo_task", "--description", "x"])
    assert res.exit_code == 0, res.output
    assert '"updated": true' in res.output
    assert '"taskDescription": "x"' in res.output


def test_client_state_guard_rejects_unknown_state():
    """G6/X2: client 层遇到 taskState=2 必须拒绝切状态。"""
    def handler(request):
        if request.url.path == f"{BASE}/schedule/task/search":
            return httpx.Response(200, json={"data": {"items": [_task_data(state=2)]}})
        raise AssertionError(request.url.path)

    client = _mock_client(handler)
    try:
        with pytest.raises(ApiError, match="不是 0/1"):
            client.set_schedule_state("demo_task", paused=True)
    finally:
        client.close()


def test_get_schedule_uppercase_uuid_resolves():
    """G7/X3: 大写 UUID 也应能反查到任务。"""
    TID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

    def handler(request):
        if request.url.path == f"{BASE}/schedule/task/search":
            import json as _json
            name = _json.loads(request.content).get("taskName")
            if name == "demo_task":
                return httpx.Response(200, json={"data": {"items": [_task_data()]}})
            return httpx.Response(200, json={"data": {"items": []}})
        if request.url.path == f"{BASE}/schedule/task/listAll/2":
            return httpx.Response(200, json={"data": [
                {"taskName": "demo_task", "taskId": TID, "id": None}]})
        raise AssertionError(request.url.path)

    client = _mock_client(handler)
    try:
        task = client.get_schedule(TID.upper())
    finally:
        client.close()
    assert task and task["taskName"] == "demo_task"


def test_cli_get_fuzzy_warns(monkeypatch):
    """G8/X4: get 模糊命中不同任务名时应在 stderr 警告。"""
    fake = _FakeTaskClient(state=0)
    _patch_client(monkeypatch, fake)
    res = CliRunner().invoke(schedule_cmd.schedule_group, ["get", "demo"])
    assert res.exit_code == 0
    assert "子串模糊" in res.stderr


def test_client_report_exists_handles_dirs_and_files():
    """G9/X5: 目录不算模板；存在的 cpt 才算。"""
    TID_PATHS = ["demo/x.cpt", "demo/sub"]

    def handler(request):
        if request.url.path == f"{BASE}/templates/all":
            return httpx.Response(200, json={"data": [
                {"path": "demo/x.cpt", "text": "x.cpt", "isParent": False},
                {"path": "demo/sub", "text": "sub", "isParent": True},
            ]})
        raise AssertionError(request.url.path)

    client = _mock_client(handler)
    try:
        assert client.report_exists("demo/x.cpt") is True
        assert client.report_exists("demo/sub") is False  # 目录
        assert client.report_exists("demo/nope.cpt") is False
    finally:
        client.close()


def test_cli_update_readback_failure_attempts_pause_restore(monkeypatch):
    """G10/X6: 回读失败时，原暂停任务应尽力恢复一次暂停。"""
    fake = _FakeTaskClient(state=1)
    fake.hide_after_update = True
    _patch_client(monkeypatch, fake)
    res = CliRunner().invoke(
        schedule_cmd.schedule_group, ["update", "demo_task", "--description", "x"])
    assert res.exit_code == 1
    assert "回读失败" in res.output
    assert fake.state_calls == [True]  # 尝试过恢复暂停
