"""`report table --sheet`：把整张贴到多 sheet 工作簿的**指定 sheet**（离线回归）。

背景（2026-10 真实会话）：`report table` 没有 `--sheet`，在多 sheet 模板上只能落到
第一张，agent 被 CLI 拒一次后只能绕路改别处。本文件守三条：

1. **指定第二张 sheet** → 表头与数据格落在第二张，第一张**逐字节不变**（对比前后 XML）；
2. **不给 `--sheet`** → 与改前 0.10.3 **完全一致**（文本 + `changes` 的基线哈希；第一张）；
3. **sheet 名不存在** → 明确 `ApiError`（含现有 sheet 清单）、exit 非 0、**零网络请求**
   （dry-run 的 `--apply` 也一样，不得半写）。

模板是脱敏占位符（sheet1/sheet2/ds1/conn1），**不联网**、不碰服务端。
基线哈希由 0.10.3 冻结副本（`/tmp` 冻结物，非仓库内容）实测得出。
"""

import hashlib
import json
import re
import sys
from pathlib import Path

import httpx
import pytest
from click.testing import CliRunner

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from frcli import cptxml, reportops                            # noqa: E402
from frcli.commands import report as report_cmd                # noqa: E402
from frcli.exceptions import ApiError                          # noqa: E402

SHEET1 = "sheet1"
SHEET2 = "sheet2"
DATASET = "ds1"
SENTINEL = "SENTINEL_SHEET1"
EMU = cptxml.EMU_PER_CHAR                                       # 每字符 EMU（实测常量）
RPT = "demo_group/demo_user/skill测试/placeholder.cpt"          # 脱敏占位符（在 SCOPE 之内）
SCOPE = "demo_group/demo_user/skill测试"                        # 脱敏占位符

TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<WorkBook xmlVersion="20211223" releaseVersion="10.0.0">
<TableDataMap><TableData name="ds1" class="com.fr.data.impl.DBTableData">
<Parameters/><Attributes share="true" maxMemRowCount="-1"/>
<Connection class="com.fr.data.impl.NameDatabaseConnection"><DatabaseName><![CDATA[conn1]]></DatabaseName></Connection>
<Query><![CDATA[select 1 a, 2 b]]></Query><PageQuery><![CDATA[]]></PageQuery>
</TableData></TableDataMap>
<StyleList/>
<Report class="com.fr.report.worksheet.WorkSheet" name="sheet1">
<ReportPageAttr><HR/><FR/><HC/><FC/></ReportPageAttr>
<RowHeight defaultValue="723900"><![CDATA[723900]]></RowHeight>
<ColumnWidth defaultValue="2743200"><![CDATA[2743200]]></ColumnWidth>
<CellElementList>
<C c="0" r="0"><O><![CDATA[SENTINEL_SHEET1]]></O><PrivilegeControl/><Expand/></C>
</CellElementList>
</Report>
<Report class="com.fr.report.worksheet.WorkSheet" name="sheet2">
<ReportPageAttr><HR/><FR/><HC/><FC/></ReportPageAttr>
<RowHeight defaultValue="723900"><![CDATA[723900]]></RowHeight>
<ColumnWidth defaultValue="2743200"><![CDATA[2743200]]></ColumnWidth>
<CellElementList>
</CellElementList>
</Report>
</WorkBook>
"""

#: 改前基线（0.10.3 冻结副本实测）：不给 `--sheet` 时的**整份 XML** 与 **changes**
GOLDEN_DEFAULT_TEXT_SHA = "93ffacfd6865996dfff9d8704f3ab162989229371b374cbe73ff469798cf9685"
GOLDEN_DEFAULT_CHANGES_SHA = "382f5604c8c867018fe92933d949401c840f7712880f01bc55462576ac2fe219"


def sheet_block(text: str, name: str) -> str:
    """某个 `<Report>` sheet 的原始字节块（含开闭标签），用于逐字节对比。"""
    for el in cptxml.sheet_elements(text):
        if el.attrs.get("name") == name:
            return text[el.open_start:el.close_end]
    raise AssertionError(f"模板里没有 sheet {name!r}；现有 {cptxml.sheet_names(text)}")


def cells_of(text: str, sheet: str) -> dict:
    return {c["a1"]: c for c in cptxml.cells(text, sheet)}


def col_widths(text: str, sheet: str):
    """某 sheet 的 `<ColumnWidth>` CDATA 数组（EMU）。"""
    m = re.search(r"<ColumnWidth[^>]*>\s*<!\[CDATA\[(.*?)\]\]>", sheet_block(text, sheet), re.S)
    assert m, f"sheet {sheet!r} 里没有 <ColumnWidth> CDATA"
    return [int(x) for x in m.group(1).split(",") if x.strip()]


def _no_network(monkeypatch):
    """哨兵：dry-run 期间任何真实请求都记录并让用例当场失败。"""
    calls = []

    def fake_request(self, method, url, *a, **kw):
        calls.append((method, str(url)))
        raise AssertionError(f"哨兵拦截：不该发出的请求 {method} {url}")

    monkeypatch.setattr(httpx.Client, "request", fake_request)
    return calls


def _invoke_cli(argv, monkeypatch, env=None):
    """CLI 级调用：只替换「读模板」这一跳，其余走真实命令路径（不联网）。"""
    monkeypatch.setattr(report_cmd, "load_config", lambda instance=None: object())
    monkeypatch.setattr(reportops, "read_template",
                        lambda config, path: TEMPLATE.encode("utf-8"))
    import os
    for k in ("FRCLI_WRITE_SCOPE", "FRCLI_ALLOW_ANY_PATH"):
        os.environ.pop(k, None)
    return CliRunner().invoke(report_cmd.report_group, argv,
                              env={"FRCLI_TIMEOUT": "5", **(env or {})})


def _json_out(res):
    """stdout 前面可能带 ⚠ 提示行（`report table` 的列名提醒，0.10.3 起既有），JSON 从 `{` 起。"""
    return json.loads(res.output[res.output.index("{"):])


def _spy_commit(monkeypatch):
    """记录 commit 被调用几次、要写的文本是什么 —— 比哨兵更直接地证明「写没写」。"""
    calls = []
    real_commit = reportops.commit

    def spy(config, report_path, before, after, action, changes, apply=False, **kw):
        calls.append({"path": report_path, "after": after, "apply": apply})
        return real_commit(config, report_path, before, after, action, changes,
                           apply=apply, **kw)

    monkeypatch.setattr(reportops, "commit", spy)
    return calls


# ---------------------------------------------------------------------------
# 1. 指定第二张 sheet：落点正确 + 第一张逐字节不变
# ---------------------------------------------------------------------------
def test_sheet_targets_second_sheet_and_leaves_first_byte_identical():
    first_before = sheet_block(TEMPLATE, SHEET1)
    second_before = sheet_block(TEMPLATE, SHEET2)
    assert first_before != second_before

    new_text, _ = reportops.plan_table(TEMPLATE, dataset=DATASET, at="A2",
                                       columns=["a", "b"], header=True, sheet=SHEET2)

    assert sheet_block(new_text, SHEET1) == first_before, "第一张 sheet 必须逐字节不变"
    assert sheet_block(new_text, SHEET2) != second_before, "第二张 sheet 必须被写入"
    cells2 = cells_of(new_text, SHEET2)
    assert cells2["A2"]["text"] == "a" and cells2["B2"]["text"] == "b"   # 表头在目标 sheet
    assert cells2["A3"]["binding"] == f"{DATASET}.a"
    assert cells2["B3"]["binding"] == f"{DATASET}.b"
    assert cells2["A3"]["ds_mode"] == "list"                            # 默认列表模式
    # 第一位 sheet 只剩哨兵格（没有倒着写回第一张）
    assert [c["a1"] for c in cptxml.cells(new_text, SHEET1)] == ["A1"]
    assert cells_of(new_text, SHEET1)["A1"]["text"] == SENTINEL


def test_first_sheet_name_explicit_is_equivalent_placement():
    """显式写第一张 sheet 名：落点必须与缺省一致（都在第一张）。"""
    new_text, _ = reportops.plan_table(TEMPLATE, dataset=DATASET, at="A2",
                                       columns=["a", "b"], header=True, sheet=SHEET1)
    assert [c["a1"] for c in cptxml.cells(new_text, SHEET1)] == ["A1", "A2", "B2", "A3", "B3"]
    assert cptxml.cells(new_text, SHEET2) == []


# ---------------------------------------------------------------------------
# 2. 不给 --sheet：与改前完全一致（基线哈希）
# ---------------------------------------------------------------------------
def test_default_sheet_behaviour_matches_pre_change_baseline():
    new_text, changes = reportops.plan_table(TEMPLATE, dataset=DATASET, at="A2",
                                             columns=["a", "b"], header=True)
    text_sha = hashlib.sha256(new_text.encode("utf-8")).hexdigest()
    changes_sha = hashlib.sha256(
        json.dumps(changes, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    assert text_sha == GOLDEN_DEFAULT_TEXT_SHA, \
        "不给 --sheet 的输出与 0.10.3 基线不一致（改前行为回归）"
    assert changes_sha == GOLDEN_DEFAULT_CHANGES_SHA, \
        "不给 --sheet 的 changes 与 0.10.3 基线不一致（改前行为回归）"
    # 落点仍在最前面的 sheet
    assert [c["a1"] for c in cptxml.cells(new_text, SHEET1)] == ["A1", "A2", "B2", "A3", "B3"]
    assert cptxml.cells(new_text, SHEET2) == []


# ---------------------------------------------------------------------------
# 3. sheet 不存在：明确报错、不写、零请求
# ---------------------------------------------------------------------------
def test_unknown_sheet_raises_with_existing_names():
    with pytest.raises(ApiError) as ei:
        reportops.plan_table(TEMPLATE, dataset=DATASET, at="A2", columns=["a", "b"],
                             sheet="no_such_sheet")
    msg = str(ei.value)
    assert "no_such_sheet" in msg
    assert SHEET1 in msg and SHEET2 in msg, f"报错要列出可选的 sheet：{msg}"
    # 输入文本没有被就地改动（两个 sheet 的字节块都不变）
    assert cptxml.sheet_names(TEMPLATE) == [SHEET1, SHEET2]
    assert sheet_block(TEMPLATE, SHEET2).count("<C ") == 0


def test_cli_unknown_sheet_fails_before_commit_and_without_any_request(monkeypatch):
    """`--apply` 也不许半写：sheet 名不存在时必须**在 commit 之前**失败，且零请求。"""
    net = _no_network(monkeypatch)
    commits = _spy_commit(monkeypatch)
    res = _invoke_cli(["table", RPT, "--dataset", DATASET, "--at", "A2",
                       "--columns", "a,b", "--sheet", "no_such_sheet",
                       "--apply", "-f", "json"],
                      monkeypatch, env={"FRCLI_WRITE_SCOPE": SCOPE})
    assert res.exit_code != 0, res.output
    assert "no_such_sheet" in res.output
    assert commits == [], f"目标 sheet 不存在却仍走到写路径：{commits}"
    assert net == [], f"目标 sheet 不存在却发了请求：{net}"


def test_cli_dry_run_with_sheet_makes_no_request(monkeypatch):
    net = _no_network(monkeypatch)
    res = _invoke_cli(["table", RPT, "--dataset", DATASET, "--at", "A2",
                       "--columns", "a,b", "--sheet", SHEET2, "-f", "json"], monkeypatch)
    assert res.exit_code == 0, res.output
    assert net == []
    data = _json_out(res)
    assert data["dry_run"] is True and data["applied"] is False


# ---------------------------------------------------------------------------
# 4. 接缝：CLI 的 `--sheet` 必须真的透传到 plan_table（0.10.3 漏的就是这一条）
# ---------------------------------------------------------------------------
def test_cli_sheet_option_lands_in_second_sheet(monkeypatch):
    """端到端（离线）：CLI 命令 → 要写的文本里，格子确实在第二张 sheet。"""
    commits = _spy_commit(monkeypatch)
    res = _invoke_cli(["table", RPT, "--dataset", DATASET, "--at", "A2",
                       "--columns", "a,b", "--sheet", SHEET2, "-f", "json"], monkeypatch)
    assert res.exit_code == 0, res.output
    assert len(commits) == 1, f"应恰好规划一次写入，实际 {len(commits)}"
    out = commits[0]["after"]
    assert sheet_block(out, SHEET1) == sheet_block(TEMPLATE, SHEET1), "第一张 sheet 必须不变"
    cells2 = cells_of(out, SHEET2)                                  # 无 --header ⇒ 数据格在 A2/B2
    assert cells2["A2"]["binding"] == f"{DATASET}.a"
    assert cells2["B2"]["binding"] == f"{DATASET}.b"


def test_cli_passes_sheet_option_through_to_plan_table(monkeypatch):
    seen = {}
    real_edit_table = reportops.edit_table

    def spy(config, report_path, apply=False, **kwargs):
        seen.update(kwargs)
        seen["_apply"] = apply
        return real_edit_table(config, report_path, apply=apply, **kwargs)

    monkeypatch.setattr(reportops, "edit_table", spy)
    res = _invoke_cli(["table", RPT, "--dataset", DATASET, "--at", "A2",
                       "--columns", "a,b", "--sheet", SHEET2, "-f", "json"], monkeypatch)
    assert res.exit_code == 0, res.output
    assert seen.get("sheet") == SHEET2, \
        f"CLI 没把 --sheet 透传下去（收到 {seen.get('sheet')!r}），格子会落错 sheet"
    assert seen.get("_apply") is False


# ---------------------------------------------------------------------------
# 5. `--widths` 也必须按 sheet 定位（与 crosstab 同族；0.10.4 审查发现表侧无守护）
#    变异对照：只删 `reportops.py` 里 plan_table 的 set_col_widths 那处 `sheet=sheet`，
#    若无这组用例，全量测试仍全绿（该回归会静默重演）。
# ---------------------------------------------------------------------------
def test_table_widths_land_in_named_sheet():
    first_before = sheet_block(TEMPLATE, SHEET1)
    new_text, _ = reportops.plan_table(TEMPLATE, dataset=DATASET, at="A2", columns=["a", "b"],
                                       header=True, widths=[12, 16], sheet=SHEET2)
    assert sheet_block(new_text, SHEET1) == first_before, "第一张 sheet 必须逐字节不变"
    assert col_widths(new_text, SHEET2)[:2] == [12 * EMU, 16 * EMU], \
        "列宽落到第一张了（plan_table 的 widths 未按 --sheet 定位）"
    assert col_widths(new_text, SHEET1) == col_widths(TEMPLATE, SHEET1), "第一张列宽不得被改"
    assert cells_of(new_text, SHEET2)["A3"]["binding"] == f"{DATASET}.a", "格子也要在第二张"


def test_table_default_widths_stay_on_first_sheet():
    """不给 `--sheet`：列宽仍落第一张、第二张逐字节不变（改前行为一致）。"""
    new_text, _ = reportops.plan_table(TEMPLATE, dataset=DATASET, at="A2", columns=["a", "b"],
                                       header=True, widths=[12, 16])
    assert col_widths(new_text, SHEET1)[:2] == [12 * EMU, 16 * EMU]
    assert sheet_block(new_text, SHEET2) == sheet_block(TEMPLATE, SHEET2)


def test_cli_widths_with_sheet_land_in_second_sheet(monkeypatch):
    """端到端（离线）：`--sheet` 与 `--widths` 一起给，列宽与格子都必须在第二张。"""
    commits = _spy_commit(monkeypatch)
    res = _invoke_cli(["table", RPT, "--dataset", DATASET, "--at", "A2",
                       "--columns", "a,b", "--widths", "12,16", "--sheet", SHEET2,
                       "-f", "json"], monkeypatch)
    assert res.exit_code == 0, res.output
    assert len(commits) == 1, f"应恰好规划一次写入，实际 {len(commits)}"
    out = commits[0]["after"]
    assert sheet_block(out, SHEET1) == sheet_block(TEMPLATE, SHEET1), "第一张 sheet 必须不变"
    assert col_widths(out, SHEET2)[:2] == [12 * EMU, 16 * EMU], \
        "CLI 的 --widths 没按 --sheet 落到第二张"
    assert cells_of(out, SHEET2)["A2"]["binding"] == f"{DATASET}.a"
    assert col_widths(out, SHEET1) == col_widths(TEMPLATE, SHEET1)
