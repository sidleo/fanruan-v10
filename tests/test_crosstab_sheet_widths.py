"""`report crosstab --sheet <第二张> --widths …`：列宽必须落在**目标 sheet**（离线回归）。

背景：`report crosstab` 早就有 `--sheet`，格子写进了目标 sheet，但列宽走
`cptxml.set_col_widths(...)` 时没带 `sheet` ⇒ **列宽静默落第一张 sheet**（不报错，
导出时才发现列宽不对）。同一缺陷族的另一半 `report table --widths` 见
`tests/test_table_sheet.py`。

守三件事：
1. 指定第二张：第二张前两列宽度按 `--widths` 变、第一张**逐字节不变**；
2. 不给 `--sheet`：列宽仍落第一张、第二张逐字节不变（与改前一致）；
3. sheet 名不存在 / 该 sheet 没有 `<ColumnWidth>`：明确 `ApiError`，不产出半成品文本。

模板是脱敏占位符（sheet1/sheet2/ds1/conn1），**不联网**。
"""

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from frcli import cptxml                                       # noqa: E402
from frcli.exceptions import ApiError                          # noqa: E402
from frcli.reportops import plan_crosstab                     # noqa: E402

SHEET1 = "sheet1"
SHEET2 = "sheet2"
DATASET = "ds1"
EMU = cptxml.EMU_PER_CHAR                                      # 每字符 EMU（实测常量）
DEFAULT_EMU = 2743200                                          # 骨架默认列宽

TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<WorkBook xmlVersion="20211223" releaseVersion="10.0.0">
<TableDataMap><TableData name="ds1" class="com.fr.data.impl.DBTableData">
<Parameters/><Attributes share="true" maxMemRowCount="-1"/>
<Connection class="com.fr.data.impl.NameDatabaseConnection"><DatabaseName><![CDATA[conn1]]></DatabaseName></Connection>
<Query><![CDATA[select 1 a, 2 b, 3 v]]></Query><PageQuery><![CDATA[]]></PageQuery>
</TableData></TableDataMap>
<StyleList/>
<Report class="com.fr.report.worksheet.WorkSheet" name="sheet1">
<ReportPageAttr><HR/><FR/><HC/><FC/></ReportPageAttr>
<RowHeight defaultValue="723900"><![CDATA[723900]]></RowHeight>
<ColumnWidth defaultValue="2743200"><![CDATA[2743200,2743200,2743200]]></ColumnWidth>
<CellElementList>
<C c="0" r="0"><O><![CDATA[SENTINEL_SHEET1]]></O><PrivilegeControl/><Expand/></C>
</CellElementList>
</Report>
<Report class="com.fr.report.worksheet.WorkSheet" name="sheet2">
<ReportPageAttr><HR/><FR/><HC/><FC/></ReportPageAttr>
<RowHeight defaultValue="723900"><![CDATA[723900]]></RowHeight>
<ColumnWidth defaultValue="2743200"><![CDATA[2743200,2743200,2743200]]></ColumnWidth>
<CellElementList>
</CellElementList>
</Report>
</WorkBook>
"""

WIDTHS = [12, 16]


def sheet_block(text: str, name: str) -> str:
    for el in cptxml.sheet_elements(text):
        if el.attrs.get("name") == name:
            return text[el.open_start:el.close_end]
    raise AssertionError(f"模板里没有 sheet {name!r}；现有 {cptxml.sheet_names(text)}")


def col_widths(text: str, name: str):
    m = re.search(r"<ColumnWidth[^>]*>\s*<!\[CDATA\[(.*?)\]\]>", sheet_block(text, name), re.S)
    assert m, f"{name} 里没有 <ColumnWidth> CDATA"
    return [int(x) for x in m.group(1).split(",") if x.strip()]


def cells_of(text: str, sheet: str):
    return [c["a1"] for c in cptxml.cells(text, sheet)]


def plan(sheet=None):
    kw = {"sheet": sheet} if sheet is not None else {}
    return plan_crosstab(TEMPLATE, dataset=DATASET, at="A3", rows=["a"], cols=["b"],
                         values=["v"], agg="sum", widths=WIDTHS, **kw)


# ---------------------------------------------------------------------------
# 1. 指定第二张 sheet：列宽与格子都进第二张，第一张逐字节不变
# ---------------------------------------------------------------------------
def test_crosstab_widths_land_in_named_sheet():
    first_before = sheet_block(TEMPLATE, SHEET1)
    new_text, _ = plan(SHEET2)
    assert sheet_block(new_text, SHEET1) == first_before, "第一张 sheet 必须逐字节不变"
    assert col_widths(new_text, SHEET2)[:2] == [w * EMU for w in WIDTHS], \
        "列宽落在第一张（= 未按 --sheet 定位）"
    assert col_widths(new_text, SHEET1)[:2] == [DEFAULT_EMU, DEFAULT_EMU], "第一张列宽不得被改"
    assert cells_of(new_text, SHEET2)[:2] == ["A3", "B3"], "格子也要在第二张 sheet"
    assert cells_of(new_text, SHEET1) == ["A1"], "第一张只应有哨兵格"


def test_crosstab_first_sheet_name_explicit_matches_default_placement():
    new_text, _ = plan(SHEET1)
    assert col_widths(new_text, SHEET1)[:2] == [w * EMU for w in WIDTHS]
    assert sheet_block(new_text, SHEET2) == sheet_block(TEMPLATE, SHEET2)


# ---------------------------------------------------------------------------
# 2. 不指定 sheet：与改前一致（列宽落第一张，第二张不变）
# ---------------------------------------------------------------------------
def test_crosstab_default_keeps_widths_on_first_sheet():
    new_text, _ = plan()
    assert col_widths(new_text, SHEET1)[:2] == [w * EMU for w in WIDTHS]
    assert sheet_block(new_text, SHEET2) == sheet_block(TEMPLATE, SHEET2), \
        "不给 --sheet 时第二张必须逐字节不变"
    assert cells_of(new_text, SHEET1)[:2] == ["A1", "A3"]


# ---------------------------------------------------------------------------
# 3. 目标不存在 / 没有 ColumnWidth：明确报错、不产出半成品
# ---------------------------------------------------------------------------
def test_crosstab_unknown_sheet_raises_with_existing_names():
    with pytest.raises(ApiError) as ei:
        plan("no_such_sheet")
    msg = str(ei.value)
    assert "no_such_sheet" in msg and SHEET1 in msg and SHEET2 in msg
    assert col_widths(TEMPLATE, SHEET1)[:2] == [DEFAULT_EMU, DEFAULT_EMU]


def test_set_col_widths_reports_sheet_without_columnwidth():
    """目标 sheet 没有 `<ColumnWidth>` 时，报错要点名是哪个 sheet（不是含糊的"模板里"）。"""
    el = next(e for e in cptxml.sheet_elements(TEMPLATE) if e.attrs.get("name") == SHEET2)
    block, n = re.subn(r"<ColumnWidth[^>]*>\s*<!\[CDATA\[.*?\]\]></ColumnWidth>\n",
                       "", TEMPLATE[el.open_start:el.close_end], count=1)
    assert n == 1, "测试自身构造失败：没删掉 sheet2 的 ColumnWidth"
    text = TEMPLATE[:el.open_start] + block + TEMPLATE[el.close_end:]
    assert "<ColumnWidth" not in sheet_block(text, SHEET2)
    with pytest.raises(ApiError) as ei:
        cptxml.set_col_widths(text, {0: 12}, sheet=SHEET2)
    assert SHEET2 in str(ei.value) and "ColumnWidth" in str(ei.value)
