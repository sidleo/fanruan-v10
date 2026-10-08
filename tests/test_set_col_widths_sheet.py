"""`set_col_widths(sheet=…)` 必须按**元素边界**定位，不能被单元格 CDATA 里的字面 XML 骗到。

场景（0.10.4 审查 N1）：目标 sheet **没有**真的 `<ColumnWidth>`，但它的某个单元格文本里
含字面 `<ColumnWidth defaultValue="9"/>`（例如说明文案）。正则实现在该 sheet 范围内搜索时
会命中这段**文本**：把宽度写进单元格、并注入 `]]>`（CDATA 提前闭合 → 模板结构损坏），
且**不报错**，绕过了"该 sheet 没有 ColumnWidth 就报错"的契约。

守四件事：
1. 目标 sheet 无真 CW（只有字面文本）→ 明确 `ApiError`，**一个字节都不改**；
2. 目标 sheet 有真 CW（CDATA 写法）→ 正确改写，其它 sheet 逐字节不变；
3. 真 CW 是自闭合 `<ColumnWidth .../>` 写法 → 同样正确改写；
4. `default_chars` 取**目标 sheet 自己**的 defaultValue（不是第一张的）。

模板是全占位符（A/B/sheet 名、9/111111 等数字），**不联网**。
"""

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

EMU = cptxml.EMU_PER_CHAR
SHEET_A = "A"
SHEET_B = "B"
FAKE_LITERAL = '示例写法 <ColumnWidth defaultValue="9"/> 结束'
DATASET = "ds1"
RPT = "demo_group/demo_user/skill测试/placeholder.cpt"          # 脱敏占位符
SCOPE = "demo_group/demo_user/skill测试"                        # 脱敏占位符

CW_RE = re.compile(
    r"<ColumnWidth([^>]*?)(?:/>|>\s*(?:<!\[CDATA\[(.*?)\]\]>)?\s*</ColumnWidth>)", re.S)


def sheet_block(text: str, name: str) -> str:
    for el in cptxml.sheet_elements(text):
        if el.attrs.get("name") == name:
            return text[el.open_start:el.close_end]
    raise AssertionError(f"模板里没有 sheet {name!r}；现有 {cptxml.sheet_names(text)}")


def cw_of(text: str, name: str):
    """某 sheet 里第一份 `<ColumnWidth>` 的 (defaultValue, CDATA 数组)。"""
    m = CW_RE.search(sheet_block(text, name))
    assert m, f"sheet {name!r} 里没有 <ColumnWidth>"
    dv = re.search(r'defaultValue="(\d+)"', m.group(1))
    vals = [int(x) for x in (m.group(2) or "").split(",") if x.strip()]
    return (int(dv.group(1)) if dv else None), vals


def _sheet(name: str, cw_xml: str, cells: str) -> str:
    cw_line = f"{cw_xml}\n" if cw_xml else ""
    return ('<Report class="com.fr.report.worksheet.WorkSheet" name="' + name + '">\n'
            '<ReportPageAttr><HR/><FR/><HC/><FC/></ReportPageAttr>\n'
            '<RowHeight defaultValue="723900"><![CDATA[723900]]></RowHeight>\n'
            + cw_line +
            '<CellElementList>\n' + cells + '\n</CellElementList>\n'
            '</Report>\n')


def make_template(cw_a: str, cw_b: str, a_cell_text: str = "SENTINEL_A",
                  b_cell_text: str = FAKE_LITERAL) -> str:
    cells_a = f'<C c="0" r="0"><O><![CDATA[{a_cell_text}]]></O><PrivilegeControl/><Expand/></C>'
    cells_b = f'<C c="0" r="0"><O><![CDATA[{b_cell_text}]]></O><PrivilegeControl/><Expand/></C>'
    dataset = ('<TableDataMap><TableData name="ds1" class="com.fr.data.impl.DBTableData">'
               '<Parameters/><Attributes share="true" maxMemRowCount="-1"/>'
               '<Connection class="com.fr.data.impl.NameDatabaseConnection"><DatabaseName>'
               '<![CDATA[conn1]]></DatabaseName></Connection>'
               '<Query><![CDATA[select 1 a, 2 b]]></Query><PageQuery><![CDATA[]]></PageQuery>'
               '</TableData></TableDataMap>')
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<WorkBook xmlVersion="20211223" releaseVersion="10.0.0">\n'
            + dataset + '\n<StyleList/>\n'
            + _sheet("A", cw_a, cells_a) + _sheet("B", cw_b, cells_b) +
            '</WorkBook>\n')


CW_CDATA = '<ColumnWidth defaultValue="{}"><![CDATA[{}]]></ColumnWidth>'
CW_SELF = '<ColumnWidth defaultValue="{}"/>'


# ---------------------------------------------------------------------------
# 1. 目标 sheet 无真 CW：字面 XML 不算数 → 报错且零字节改动
# ---------------------------------------------------------------------------
def test_fake_literal_in_cell_is_not_a_columnwidth():
    text = make_template(CW_CDATA.format("111111", "111111"), "")
    pristine = str(text)                                  # 独立副本（比对"一个字节都不改"）
    block_before = sheet_block(text, SHEET_B)
    terminators_before = block_before.count("]]>")

    with pytest.raises(ApiError) as ei:
        cptxml.set_col_widths(text, {0: 12}, sheet=SHEET_B)
    msg = str(ei.value)
    assert SHEET_B in msg and "ColumnWidth" in str(ei.value), msg

    assert text == pristine, "报错路径不得改动输入"
    assert sheet_block(text, SHEET_B) == block_before
    assert sheet_block(text, SHEET_B).count("]]>") == terminators_before, \
        "CDATA 被提前闭合（旧实现会注入 ]]>）"
    assert FAKE_LITERAL in sheet_block(text, SHEET_B), "单元格里的字面 XML 必须原样保留"
    # 失败之后，同一个模板上对**有真 CW** 的 sheet 仍能正常改写
    out = cptxml.set_col_widths(text, {0: 12}, sheet=SHEET_A)
    assert cw_of(out, SHEET_A)[1][0] == 12 * EMU


# ---------------------------------------------------------------------------
# 2. 有真 CW（CDATA / 自闭合两种写法）：正确改写，其它 sheet 不动
# ---------------------------------------------------------------------------
def test_cdata_columnwidth_rewritten_other_sheet_untouched():
    text = make_template(CW_CDATA.format("111111", "111111"),
                         CW_CDATA.format("999999", "999999"))
    out = cptxml.set_col_widths(text, {0: 12}, sheet=SHEET_A)
    dv, vals = cw_of(out, SHEET_A)
    assert dv == 111111 and vals[0] == 12 * EMU
    assert sheet_block(out, SHEET_B) == sheet_block(text, SHEET_B), \
        "另一张 sheet 必须逐字节不变"


def test_selfclosing_columnwidth_rewritten_other_sheet_untouched():
    text = make_template(CW_SELF.format("222222"), CW_SELF.format("333333"))
    out = cptxml.set_col_widths(text, {0: 8, 1: 9}, sheet=SHEET_A)
    dv, vals = cw_of(out, SHEET_A)
    assert dv == 222222
    assert vals[:2] == [8 * EMU, 9 * EMU]
    assert sheet_block(out, SHEET_B) == sheet_block(text, SHEET_B)


# ---------------------------------------------------------------------------
# 3. default_chars 取目标 sheet 自己的 defaultValue
# ---------------------------------------------------------------------------
def test_default_chars_comes_from_target_sheet_own_default_value():
    text = make_template(CW_CDATA.format("111111", "111111"),
                         CW_CDATA.format("999999", "999999"))
    out = cptxml.set_col_widths(text, {0: 12}, default_chars=8, sheet=SHEET_B)
    dv_b, vals_b = cw_of(out, SHEET_B)
    assert dv_b == 8 * EMU, f"defaultValue 应取自目标 sheet 自己（999999 系），实际 {dv_b}"
    assert vals_b[0] == 12 * EMU
    assert sheet_block(out, SHEET_A) == sheet_block(text, SHEET_A), \
        "第一张 sheet 必须逐字节不变"


# ---------------------------------------------------------------------------
# 4. 命令路径：目标 sheet 无真 CW + 字面 XML ⇒ 报错、零写请求（"零字节改动"的可操作证据）
# ---------------------------------------------------------------------------
def test_cli_widths_with_fake_literal_never_reaches_commit(monkeypatch):
    text = make_template(CW_CDATA.format("111111", "111111"), "")
    commits, requests = [], []

    def spy_commit(*a, **kw):
        commits.append(kw)
        raise AssertionError("不该走到 commit")

    def spy_request(self, method, url, *a, **kw):
        requests.append((method, str(url)))
        raise AssertionError(f"哨兵拦截：不该发出的请求 {method} {url}")

    monkeypatch.setattr(report_cmd, "load_config", lambda instance=None: object())
    monkeypatch.setattr(reportops, "read_template", lambda config, path: text.encode("utf-8"))
    monkeypatch.setattr(reportops, "commit", spy_commit)
    monkeypatch.setattr(httpx.Client, "request", spy_request)
    res = CliRunner().invoke(report_cmd.report_group,
                             ["table", RPT, "--dataset", DATASET, "--at", "A2",
                              "--columns", "a,b", "--widths", "12,16",
                              "--sheet", SHEET_B, "--apply", "-f", "json"],
                             env={"FRCLI_TIMEOUT": "5", "FRCLI_WRITE_SCOPE": SCOPE})
    assert res.exit_code != 0, res.output
    assert SHEET_B in res.output and "ColumnWidth" in res.output
    assert commits == [], f"目标 sheet 无真 CW 却仍走到写路径：{commits}"
    assert requests == [], f"目标 sheet 无真 CW 却发了请求：{requests}"


# ---------------------------------------------------------------------------
# 5. 默认路径（sheet=None）同样按元素边界定位：第一个**有真 CW** 的 sheet
#    （0.10.4 收口；旧默认路径是全文正则，第一张的字面 XML 会被写坏）
# ---------------------------------------------------------------------------
def test_default_path_ignores_fake_literal_in_first_sheet():
    """A（第一张，无真 CW + 单元格含字面 XML）、B（第二张，有真 CW）：
    默认调用必须落到 B 的真元素；A **逐字节不变**（`]]>` 计数不变、字面文本原样）。"""
    text = make_template("", CW_CDATA.format("999999", "999999"), a_cell_text=FAKE_LITERAL)
    a_before = sheet_block(text, SHEET_A)
    terminators_before = a_before.count("]]>")
    assert FAKE_LITERAL in a_before

    out = cptxml.set_col_widths(text, {0: 12})

    assert sheet_block(out, SHEET_A) == a_before, "第一张（无真 CW）必须逐字节不变"
    assert sheet_block(out, SHEET_A).count("]]>") == terminators_before, \
        "默认路径把宽度写进了第一张的单元格文本（CDATA 被提前闭合）"
    assert FAKE_LITERAL in sheet_block(out, SHEET_A), "单元格里的字面 XML 必须原样保留"
    dv_b, vals_b = cw_of(out, SHEET_B)
    assert dv_b == 999999 and vals_b[0] == 12 * EMU, "默认路径应落到 B 的真元素"


def test_default_path_normal_two_sheet_changes_first_sheet_only():
    """正常模板（每张都有真 CW）：默认路径仍只改第一张（与 0.10.3 语义一致）。"""
    text = make_template(CW_CDATA.format("111111", "111111"),
                         CW_CDATA.format("999999", "999999"), b_cell_text="SENTINEL_B")
    out = cptxml.set_col_widths(text, {0: 12})
    dv_a, vals_a = cw_of(out, SHEET_A)
    assert dv_a == 111111 and vals_a[0] == 12 * EMU
    assert sheet_block(out, SHEET_B) == sheet_block(text, SHEET_B)


def test_default_path_without_report_uses_workbook_child():
    """简化 fixture（无 `<Report>`，CW 直接挂在 `<WorkBook>` 下）仍可用。

    保住 `tests/test_cptwrite.py::test_set_col_widths_basic` 与
    `::test_set_col_widths_extends_array_and_handles_selfclose` 的语义（CDATA / 自闭合两种写法）。
    """
    cdata = ('<WorkBook><ColumnWidth defaultValue="2743200">'
             '<![CDATA[2743200,2743200]]></ColumnWidth></WorkBook>')
    m = CW_RE.search(cptxml.set_col_widths(cdata, {0: 12, 1: 20}))
    vals = [int(x) for x in m.group(2).split(",") if x.strip()]
    assert vals == [12 * EMU, 20 * EMU]

    selfclose = '<WorkBook><ColumnWidth defaultValue="2743200"/></WorkBook>'
    m2 = CW_RE.search(cptxml.set_col_widths(selfclose, {2: 10}))
    vals2 = [int(x) for x in (m2.group(2) or "").split(",") if x.strip()]
    assert len(vals2) == 3 and vals2[0] == 2743200 and vals2[2] == 10 * EMU


def test_default_path_without_any_columnwidth_keeps_error_message():
    """一个真 CW 都没有（含无 `<Report>` 的简化模板）→ 报错文案与改前逐字一致。"""
    with pytest.raises(ApiError) as ei:
        cptxml.set_col_widths('<WorkBook><StyleList/></WorkBook>', {0: 12})
    assert str(ei.value) == "模板里没有 <ColumnWidth>，无法设置列宽"
