"""S3 回归：`export batch` 的两个边界（空列表参数 / 多条任务撞同一输出路径）。

背景（本轮新引入的静默风险）：
- 参数矩阵 `params` 给**空列表**时，旧逻辑静默丢报表：`total: 0`、无 error、exit 0 ——
  看着像"跑完了"，实际一份没导。
- 多条任务展开出**同一个 output 路径**时，后写的覆盖先写的，全程无提示
  （多半是 `output` 漏了 `{参数名}` 占位）。

全离线：`get_client` 换成假客户端，不打网络、不落真实产物。
"""
from __future__ import annotations

import json
from pathlib import Path

import yaml
from click.testing import CliRunner

from frcli.commands import export as export_cmd
from frcli.exceptions import ExportError


class FakeClient:
    def __init__(self):
        self.net_retries = 0

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def export_report(self, report_path, format, output, params=None):
        p = Path(output)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"PK\x03\x04stub")
        return str(p.resolve())


def _run(tmp_path, monkeypatch, manifest: dict):
    mf = tmp_path / "manifest.yaml"
    mf.write_text(yaml.safe_dump(manifest, allow_unicode=True), encoding="utf-8")
    monkeypatch.setattr(export_cmd, "get_client", lambda instance=None: FakeClient())
    return CliRunner().invoke(export_cmd.export_group, ["batch", str(mf)])


def _manifest(out_dir: Path, params: dict, name: str = "sample_rpt") -> dict:
    return {"reports": [{
        "path": f"demo_group/demo_user/{name}.cpt",
        "format": "excel",
        "output": str(out_dir / "out_{edate}.xlsx"),
        "params": params,
    }]}


def test_empty_param_list_is_explicit_error_not_silent(tmp_path, monkeypatch):
    """空列表参数 → 明确 EXPORT_ERROR、退出码 1、点名是哪个参数（不静默丢报表）。"""
    res = _run(tmp_path, monkeypatch, _manifest(tmp_path / "out", {"edate": []}))

    assert res.exit_code == 1, f"静默成功是最危险的结果: exit={res.exit_code}, out={res.output[:120]}"
    body = json.loads(res.output)
    assert body["status"] == "error"
    assert body["error"]["code"] == "EXPORT_ERROR"
    msg = body["error"]["message"]
    assert "edate" in msg, f"没点名是哪个参数: {msg}"
    assert "空列表" in msg or "没有任何导出任务" in msg, f"没说清原因: {msg}"


def test_empty_param_list_message_names_report(tmp_path, monkeypatch):
    """报错要点到 manifest 第几条 / 哪张报表，便于回查 manifest。"""
    res = _run(tmp_path, monkeypatch,
               _manifest(tmp_path / "out", {"edate": []}, name="matrix_rpt"))
    msg = json.loads(res.output)["error"]["message"]
    assert "matrix_rpt.cpt" in msg, f"没指向具体报表: {msg}"


def test_nonempty_matrix_still_exports(tmp_path, monkeypatch):
    """对照：正常矩阵不受影响（别把空列表检查写成"有列表就报错"）。"""
    res = _run(tmp_path, monkeypatch,
               _manifest(tmp_path / "out", {"edate": ["20260430", "20260531"]}))

    assert res.exit_code == 0, res.output
    body = json.loads(res.output)
    assert body["total"] == 2 and body["success"] == 2
    # 护栏：不该有噪声 warning（字段不存在也算"没有噪声"，故用 not ... get）
    assert not body.get("warnings")


def test_same_output_path_emits_warning(tmp_path, monkeypatch):
    """多条任务撞同一输出路径 → 顶层 warnings 非空且点名该路径。"""
    same = tmp_path / "same.xlsx"
    res = _run(tmp_path, monkeypatch, {"reports": [{
        "path": "demo_group/demo_user/sample_rpt.cpt",
        "format": "excel",
        "output": str(same),                      # 故意不带 {参数名} 占位
        "params": {"edate": ["20260430", "20260531"]},
    }]})

    assert res.exit_code == 0, res.output
    body = json.loads(res.output)
    warnings = body.get("warnings") or []
    assert warnings, "同 output 覆盖是静默数据损失，必须有 warnings"
    assert any(str(same) in w for w in warnings), f"warning 没点名冲突路径: {warnings}"


def test_distinct_outputs_do_not_warn(tmp_path, monkeypatch):
    """对照：路径各不相同就不该有噪声 warning。"""
    res = _run(tmp_path, monkeypatch, _manifest(tmp_path / "out",
                                                {"edate": ["20260430", "20260531"]}))
    assert not json.loads(res.output).get("warnings")


def test_single_job_no_warning(tmp_path, monkeypatch):
    """对照：只有一个任务时没有"冲突"可言。"""
    res = _run(tmp_path, monkeypatch, _manifest(tmp_path / "out", {}))
    assert res.exit_code == 0, res.output
    assert not json.loads(res.output).get("warnings")


def test_empty_list_error_is_export_error_type():
    """空列表用的是 ExportError（code 稳定为 EXPORT_ERROR，便于下游按码分支）。"""
    assert ExportError.code == "EXPORT_ERROR"
