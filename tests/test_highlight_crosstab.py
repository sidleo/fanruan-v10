"""条件属性 `<Highlight>` / 交叉表 / 分页设置的离线回归测试。

覆盖三件事：
1. 条件属性：条件类选择（`v>100` → ObjectCondition+Compare op=2，其余走 FormulaCondition）、
   动作类（背景/字色/字体/行高=隐藏）、**fg 必须并进 FRFont**（否则被覆盖，实测踩过）
2. 交叉表：四类格的 Grouper/Expand 形态、**值格必须与列维度同列**（否则列维度消失）
3. 分页设置：`ReportSettings headerHeight` 的 FU 换算、`FrozenColumnRow`、
   `CellPageAttr repeat` 的**反向缺省**（缺省 true，只有 `repeat="false"` 才是关闭）

真机对照（导出 xlsx/png 逐格读回）见 `references/cpt-patterns.md`；本文件**不联网**。
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from frcli import cptxml, reportops                          # noqa: E402
from frcli.exceptions import ApiError                        # noqa: E402

FUNC = cptxml.FUNCTION_GROUPER
SUMMARY = cptxml.SUMMARY_GROUPER

DATASET = ("<TableDataMap><TableData name=\"ds1\" class=\"com.fr.data.impl.DBTableData\">"
           "<Parameters/><Attributes share=\"true\" maxMemRowCount=\"-1\"/>"
           "<Connection class=\"com.fr.data.impl.NameDatabaseConnection\"><DatabaseName>"
           "<![CDATA[demo_conn]]></DatabaseName></Connection>"
           "<Query><![CDATA[select '东区' dist,'A' prod,1 amt]]></Query>"
           "<PageQuery><![CDATA[]]></PageQuery></TableData></TableDataMap>")


def make_template():
    return cptxml.empty_skeleton().replace("<TableDataMap/>", DATASET)


# ---------------------------------------------------------------------------
# 1. 条件属性：条件与动作的 XML 形状
# ---------------------------------------------------------------------------
def test_value_condition_uses_compare_op():
    xml = cptxml.condition_xml("v>100")
    assert cptxml.CONDITION_CLASSES["object"] in xml
    assert '<Compare op="2">' in xml and "<![CDATA[100]]></O>" in xml
    assert cptxml.condition_xml("v>=0.7").count('<Compare op="3">') == 1
    assert cptxml.condition_xml('v!="-"').count('<Compare op="1">') == 1
    # 空值/非空：Compare 不带值
    assert "<Compare op=\"14\"/>" in cptxml.condition_xml("v==null")


def test_formula_condition_for_everything_else():
    xml = cptxml.condition_xml("ROW()%2=0")
    assert cptxml.CONDITION_CLASSES["formula"] in xml
    assert "<![CDATA[ROW()%2=0]]>" in xml
    assert "FormulaCondition" in cptxml.condition_xml("$B3>1000")
    # 前导 = 会被去掉（服务端 `<Formula>` 里不带 =）
    assert "<![CDATA[ROW()%2=0]]>" in cptxml.condition_xml("=ROW()%2=0")
    with pytest.raises(ApiError):
        cptxml.condition_xml("")


def test_fg_is_merged_into_frfont_not_a_separate_action():
    """`bg=…,fg=…,bold` 必须只出 FRFont+foreground —— 单独一条 Foreground 会被 FRFont 覆盖。"""
    acts = cptxml.highlight_action_xml("bg=#FFC7CE,fg=#9C0006,bold")
    assert len(acts) == 2, acts
    assert "BackgroundHighlightAction" in acts[0]
    assert "FRFontHighlightAction" in acts[1]
    assert 'foreground="-6553594"' in acts[1]        # #9C0006
    assert "ForegroundHighlightAction" not in "\n".join(acts)
    # 只要字色、没有字体动作时才走 ForegroundHighlightAction
    plain = cptxml.highlight_action_xml("fg=#006100")
    assert len(plain) == 1 and "ForegroundHighlightAction" in plain[0]


def test_row_height_zero_means_empty_action():
    """整行隐藏 = `RowHeightHighlightAction` **空元素**（`<RowHeight i>` 只在 >0 时才写）。"""
    zero = cptxml.highlight_action_xml("rowheight=0")[0]
    assert 'RowHeightHighlightAction">' in zero and "<RowHeight" not in zero
    twenty = cptxml.highlight_action_xml("rowheight=20")[0]          # 默认单位=磅
    assert f'<RowHeight i="{20 * cptxml.FU_PER_POINT}"/>' in twenty
    pt20 = cptxml.highlight_action_xml("rowheight=20pt")[0]
    assert f'<RowHeight i="{20 * cptxml.FU_PER_POINT}"/>' in pt20
    assert '<RowHeight i="720000"/>' in cptxml.highlight_action_xml("rowheight=720000fu")[0]


def test_unknown_action_is_rejected():
    with pytest.raises(ApiError):
        cptxml.highlight_action_xml("bar=1")
    with pytest.raises(ApiError):
        cptxml.highlight_action_xml("")


def _with_cells():
    """先造出 A3/B3/C3 三个数据格（条件属性只能挂在已有单元格上）。"""
    text = make_template()
    for a1 in ("A3", "B3", "C3"):
        text, _ = reportops.plan_cell(text, a1, binding="ds1.amt", expand="v")
    return text


def test_highlight_roundtrip_list_and_parse():
    text = _with_cells()
    text, _ = reportops.plan_highlight(
        text, "C3", rules=["v>300:bg=#FFC7CE,fg=#9C0006,bold",
                           "ROW()%2=0:bg=#F2F2F2"])
    cell = cptxml.find_cell(text, "C3")
    assert cell["hl_count"] == 2
    specs = [(cptxml.condition_spec(h["condition"]),
              [cptxml.highlight_action_spec(a) for a in h["actions"]])
             for h in cell["highlights"]]
    assert specs[0][0] == "v>300"
    assert specs[1][0] == "formula:ROW()%2=0"
    assert "bg=#FFC7CE" in specs[0][1]


def test_highlight_clear_and_range_and_missing_cells():
    text = _with_cells()
    text, _ = reportops.plan_highlight(text, "A3:B3", rules=["ROW()%2=0:bg=#F2F2F2"])
    assert cptxml.find_cell(text, "A3")["hl_count"] == 1
    assert cptxml.find_cell(text, "B3")["hl_count"] == 1
    text, changes = reportops.plan_highlight(text, "A3:B3", clear=True)
    assert cptxml.find_cell(text, "A3")["hl_count"] == 0
    assert changes[0]["kind"] == "highlight.clear"
    with pytest.raises(ApiError):
        reportops.plan_highlight(text, "A3", clear=True)        # 已经没有了
    with pytest.raises(ApiError):
        reportops.plan_highlight(make_template(), "Z9", rules=["v>1:bg=#000000"])


def test_highlight_keeps_cell_content_and_expand():
    text = make_template()
    text, _ = reportops.plan_cell(text, "C3", binding="ds1.amt", expand="v")
    before = cptxml.find_cell(text, "C3")
    text, _ = reportops.plan_highlight(text, "C3", rules=["v>1:bg=#FFC7CE"])
    after = cptxml.find_cell(text, "C3")
    assert after["binding"] == before["binding"] and after["expand"] == "v"
    assert after["ds_mode"] == "group" and after["hl_count"] == 1


# ---------------------------------------------------------------------------
# 2. DSColumn 的 `<Result>` / `<Condition>`
# ---------------------------------------------------------------------------
def test_ds_result_and_filter_child_order():
    text = make_template()
    text, _ = reportops.plan_cell(text, "A3", binding="ds1.dt", ds_mode="list", expand="v",
                                  ds_result="FORMAT(TODATE($$$,'yyyyMMdd'),'yyyy年MM月')",
                                  ds_filter="$$$ > 0")
    o = text[text.find('<O t="DSColumn">'):text.find("</O>") + 4]
    order = [o.find(t) for t in ("<Attributes", "<Condition", "<Complex", "<RG", "<Result",
                                 "<Parameters")]
    assert order == sorted(order), o
    cell = cptxml.find_cell(text, "A3")
    assert cell["ds_result"].startswith("FORMAT(") and cell["ds_filter"]["kind"] == "formula"
    # 清空
    text, _ = reportops.plan_cell(text, "A3", binding="ds1.dt", ds_mode="list", expand="v",
                                  ds_result="", ds_filter="")
    cell = cptxml.find_cell(text, "A3")
    assert cell["ds_result"] is None and cell["ds_filter"] is None


def test_ds_result_rejected_on_value_cell():
    text = make_template()
    text, _ = reportops.plan_cell(text, "A3", value="x")
    with pytest.raises(ApiError):
        reportops.plan_cell(text, "A3", ds_result="$$$/2")


# ---------------------------------------------------------------------------
# 3. 交叉表
# ---------------------------------------------------------------------------
def test_crosstab_layout_and_groupers():
    text, changes = reportops.plan_crosstab(
        make_template(), dataset="ds1", at="A3", rows=["dist"], cols=["prod"],
        values=["amt"], agg=None, total_row=True, total_col=True)
    cells = {c["a1"]: c for c in cptxml.cells(text)}
    # 表头行 = A3（角标）/ B3（列维度，横向扩展）；数据行 = 4；总计行 = 5
    assert cells["A4"]["binding"] == "ds1.dist" and cells["A4"]["expand"] == "v"
    assert cells["B3"]["binding"] == "ds1.prod" and cells["B3"]["expand"] == "h"
    # 值格与列维度**同列**、在数据行：这是交叉积能出来的关键
    assert cells["B4"]["binding"] == "ds1.amt" and cells["B4"]["expand"] == "none"
    assert cells["B4"]["ds_mode"] == "group"
    # 汇总列在列维度右边
    assert cells["C4"]["ds_mode"] == "summary" and cells["C4"]["ds_fn"] == "SumFunction"
    # 总计行走公式（官方写法 =SUM(B4)）
    assert cells["B5"]["formula"] == "=SUM(B4)"
    assert cells["A5"]["text"] == "总计："
    assert changes[0]["kind"] == "crosstab" and changes[0]["layout"]["value"] == ["B4"]


def test_crosstab_agg_switches_value_grouper():
    text, changes = reportops.plan_crosstab(
        make_template(), dataset="ds1", at="A3", rows=["dist"], cols=["prod"],
        values=["amt"], agg="sum")
    cell = cptxml.find_cell(text, "B4")
    assert cell["ds_mode"] == "summary" and cell["ds_fn"] == "SumFunction"
    assert any(ch["kind"] == "note" for ch in changes)


def test_crosstab_rejects_bad_input():
    with pytest.raises(ApiError):     # 多指标不猜版面
        reportops.plan_crosstab(make_template(), dataset="ds1", at="A3", rows=["dist"],
                                cols=["prod"], values=["amt", "amt2"])
    with pytest.raises(ApiError):
        reportops.plan_crosstab(make_template(), dataset="ds1", at="A3", rows=["dist"],
                                cols=["prod"], values=["dist"])
    with pytest.raises(ApiError):     # 数据集不存在
        reportops.plan_crosstab(make_template(), dataset="nope", at="A3", rows=["dist"],
                                cols=["prod"], values=["amt"])
    with pytest.raises(ApiError):     # 空行维度
        reportops.plan_crosstab(make_template(), dataset="ds1", at="A3", rows=[],
                                cols=["prod"], values=["amt"])


# ---------------------------------------------------------------------------
# 4. 分页设置
# ---------------------------------------------------------------------------
def test_page_settings_fu_and_freeze():
    text, changes = reportops.plan_page(make_template(), header_height=30, footer_height=12,
                                        freeze="1,0")
    info = cptxml.page_settings(text)
    assert info["header_height_pt"] == 30.0 and info["footer_height_pt"] == 12.0
    assert info["frozen"] == "1,0"
    raw = text[text.find("<ReportSettings"):text.find("<PaperSetting")]
    assert f'headerHeight="{30 * cptxml.FU_PER_POINT}"' in raw
    assert "<FrozenColumnRow columnrow=\"1,0\"/>" in text
    # 清除冻结
    text, _ = reportops.plan_page(text, freeze="none")
    assert cptxml.page_settings(text)["frozen"] is None
    assert [c["kind"] for c in changes][:2] == ["page.header-height", "page.footer-height"]


def test_cell_page_attr_repeat_is_inverted_default():
    text = make_template()
    text, _ = reportops.plan_cell(text, "A3", value="表头")
    assert cptxml.cell_page_attr_spec(text, cptxml.find_cell(text, "A3"))["repeat"] is True
    text, changes = reportops.plan_page(text, no_repeat_rows="3")
    cell = cptxml.find_cell(text, "A3")
    assert cptxml.cell_page_attr_spec(text, cell)["repeat"] is False
    assert '<CellPageAttr repeat="false"/>' in text
    assert changes[0]["kind"] == "page.repeat" and changes[0]["cells"] >= 1
    with pytest.raises(ApiError):
        reportops.plan_page(text, no_repeat_rows="99")
    with pytest.raises(ApiError):
        reportops.plan_page(text)


def test_page_list_reads_settings():
    text, _ = reportops.plan_page(make_template(), header_height=20)
    info = cptxml.page_settings(text)
    assert info["header_height_pt"] == 20.0 and info["header"] == [] and info["footer"] == []


# --- 学自另一个会话的两个静默坏法（2026-09）-----------------------------------
def test_bold_action_always_writes_size():
    """`bold` 不带 size 会让 FRFont 变成 **0 号字**（值还在、整行看不见）。

    实测：`--rule 'v>0:bold'` 导出 xlsx 的 font.size = 0.0。修法是继承目标格样式字号。
    """
    from frcli import cptxml
    def act(spec, **kw):
        return "".join(cptxml.highlight_action_xml(spec, **kw))

    assert 'size="' in act("bold"), "字体动作必须带 size，否则服务端按 0 号字处理"
    assert 'size="72"' in act("bold"), "无继承时应退到 9 磅（72 = 9×8）"
    assert 'size="96"' in act("bold,size=12")          # 指定了就用指定的
    assert 'size="120"' in act("bold", inherit_size=120)  # 继承优先
    assert "FRFont" not in act("bg=#FFC7CE")            # 纯背景动作不该凭空带字体


def test_cell_font_size_reads_style():
    from frcli import cptxml
    t = cptxml.empty_skeleton() if hasattr(cptxml, "empty_skeleton") else None
    if t is None:
        import pytest
        pytest.skip("骨架构造函数名不同")
    xml = ('<WorkBook><StyleList>'
           '<Style><FRFont name="SimSun" style="0" size="96"/></Style>'
           '</StyleList>'
           '<Report class="com.fr.report.worksheet.WorkSheet" name="sheet1">'
           '<CellElementList>'
           '<C c="0" r="0" s="0"><O><![CDATA[x]]></O><Expand/></C>'
           '</CellElementList></Report></WorkBook>')
    cell = cptxml.find_cell(xml, "A1")
    assert cptxml.cell_font_size(xml, cell) == 96


# --- 学自另一个会话（2026-09）：只改字号也要能建样式 ---------------------------
def test_style_preset_accepts_size_only():
    """`--add --size-pt 12` 曾被拒（"至少要给一项"把 size 排除在外）→ 建不出只改字号的样式。"""
    from frcli import reportops
    from frcli.exceptions import ApiError
    tpl = ('<WorkBook><StyleList/></StyleList>'
           '<Report class="com.fr.report.worksheet.WorkSheet" name="s"><CellElementList/>'
           '</Report></WorkBook>').replace("</StyleList></StyleList>", "</StyleList>")
    text, ch = reportops.plan_style_preset(tpl, size_pt=12)
    assert ch[0]["kind"] == "style.add" and ch[0]["size_pt"] == 12
    assert 'size="96"' in text, "12 磅应写成 96（1/8 磅单位）"
    # 一项都不给仍要报错
    import pytest
    with pytest.raises(ApiError):
        reportops.plan_style_preset(tpl)
