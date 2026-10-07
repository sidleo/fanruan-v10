"""C1 回归：`export batch` 的失败条目必须能定位到"哪一项"。

背景（实测）：参数矩阵下同一报表出一批产物，旧版 `errors` 只有 report/format/error，
两条失败文案一字不差，只能靠文件 mtime 猜是哪个月份；`total` 又用 manifest 条数，
出现 `total:1` 而 `success+failed:3` 的账对不上。

全离线：`get_client` 被替换成假客户端，不打网络、不落真实产物。
"""
from __future__ import annotations

import json
from pathlib import Path

import yaml
from click.testing import CliRunner

from frcli.commands import export as export_cmd
from frcli.exceptions import ExportError


class FakeClient:
    """假客户端：按断言决定哪些 (params) 失败；不打网络。"""

    def __init__(self, fail_when=None):
        self.fail_when = fail_when or (lambda params: False)
        self.net_retries = 0
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def export_report(self, report_path, format, output, params=None):
        self.calls.append({"report": report_path, "format": format,
                           "output": output, "params": dict(params or {})})
        if self.fail_when(params or {}):
            raise ExportError("导出产物是平台出错页，不是报表（合成失败，供测试）")
        p = Path(output)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"PK\x03\x04stub")
        return str(p.resolve())


def _run(tmp_path, monkeypatch, manifest: dict) -> tuple[dict, FakeClient]:
    manifest_path = tmp_path / "manifest.yaml"
    manifest_path.write_text(yaml.safe_dump(manifest, allow_unicode=True), encoding="utf-8")
    holder = {}

    def fake_get_client(instance=None):
        holder["client"] = holder.get("client") or FakeClient(
            fail_when=lambda params: params.get("edate") in ("20260430", "20260630"))
        return holder["client"]

    monkeypatch.setattr(export_cmd, "get_client", fake_get_client)
    result = CliRunner().invoke(export_cmd.export_group, ["batch", str(manifest_path)])
    assert result.exit_code == 0, result.output
    return json.loads(result.output), holder["client"]


def _matrix(out_dir: Path) -> dict:
    return {"reports": [{
        "path": "demo_group/demo_user/matrix_rpt.cpt",
        "format": "excel",
        "output": str(out_dir / "matrix_{edate}.xlsx"),
        "params": {"edate": ["20260430", "20260531", "20260630"]},
    }]}


def _two_plain(out_dir: Path) -> dict:
    return {"reports": [
        {"path": "demo_group/demo_user/ok_rpt.cpt", "format": "excel",
         "output": str(out_dir / "ok.xlsx"), "params": {"edate": "20260531"}},
        {"path": "demo_group/demo_user/bad_rpt.cpt", "format": "excel",
         "output": str(out_dir / "bad.xlsx"), "params": {"edate": "20260430"}},
    ]}


def test_matrix_total_is_expanded_job_count(tmp_path, monkeypatch):
    """`total` 必须是**展开后**的任务数，manifest 条数另给 manifest_reports。"""
    data, _ = _run(tmp_path, monkeypatch, _matrix(tmp_path / "out"))

    assert data["total"] == 3, f"展开 3 个任务，total 却是 {data['total']}"
    assert data.get("manifest_reports") == 1
    assert data["total"] == data["success"] + data["failed"]


def test_matrix_errors_carry_params_and_output(tmp_path, monkeypatch):
    """失败条目必须自带本次 params 与展开后的 output —— 否则定位不到是哪一项。"""
    data, _ = _run(tmp_path, monkeypatch, _matrix(tmp_path / "out"))

    assert data["success"] == 1 and data["failed"] == 2
    assert len(data["errors"]) == 2
    for entry in data["errors"]:
        assert "params" in entry, f"errors 条目缺 params，无法定位: {entry}"
        assert "output" in entry, f"errors 条目缺 output，无法定位: {entry}"

    # 两条失败必须是**可区分**的：各自对应自己的 edate 取值
    assert {e["params"]["edate"] for e in data["errors"]} == {"20260430", "20260630"}
    assert sorted(Path(e["output"]).name for e in data["errors"]) == [
        "matrix_20260430.xlsx", "matrix_20260630.xlsx"]

    # 成功条目同样带 params/output（对照口径一致）
    assert data["results"][0]["params"]["edate"] == "20260531"
    assert Path(data["results"][0]["output"]).name == "matrix_20260531.xlsx"


def test_plain_manifest_entries_carry_own_params(tmp_path, monkeypatch):
    """普通 manifest（无矩阵）也要能看出是哪一条失败，且不串到兄弟条目的参数。"""
    data, _ = _run(tmp_path, monkeypatch, _two_plain(tmp_path / "out"))

    assert data["total"] == 2
    assert data.get("manifest_reports") == 2
    assert data["success"] == 1 and data["failed"] == 1

    err = data["errors"][0]
    assert err["report"] == "demo_group/demo_user/bad_rpt.cpt"
    assert err["params"] == {"edate": "20260430"}, "失败条目的 params 串成了别的条目"
    assert Path(err["output"]).name == "bad.xlsx"
    assert data["results"][0]["params"] == {"edate": "20260531"}


def test_batch_reports_net_retries_field(tmp_path, monkeypatch):
    """重试次数要可观测（无重试时为 0，不引入噪声字段缺失）。"""
    data, _ = _run(tmp_path, monkeypatch, _two_plain(tmp_path / "out"))
    assert data.get("net_retries") == 0
