"""图表 / 参数面板控件 / 超链接 / 层次坐标 / 分页的离线回归测试。

覆盖：
1. 图表：`<O t="CC">` 单元格结构、三种数据定义形态（多系列 / 单系列空 seriesName / 单张饼空 CategoryName）、
   标题缺省写 `TitleVisible=false`（否则服务端给默认标题）
2. 控件：`<ParameterUI>` 面板结构、控件名=参数名、CustomDictionary 选项、默认值读写往返
3. 超链接：**单元格级 `<NameJavaScriptGroup>`**（正确形态）与条件属性形态（会炸的那条）都要能生成/解析
4. 分页：`<HR F T/>` 重复标题行、`<Header>/<Footer>` 必须落在 `<ReportAttrSet>` 内、页码公式

真机验收（逐格/逐像素）见 `references/cpt-patterns2.md`；本文件**不联网**。
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from frcli import chartxml, cptxml, reportops                # noqa: E402
from frcli.exceptions import ApiError                        # noqa: E402

DATASET = ("<TableDataMap><TableData name=\"ds1\" class=\"com.fr.data.impl.DBTableData\">"
           "<Parameters/><Attributes share=\"true\" maxMemRowCount=\"-1\"/>"
           "<Connection class=\"com.fr.data.impl.NameDatabaseConnection\"><DatabaseName>"
           "<![CDATA[demo_conn]]></DatabaseName></Connection>"
           "<Query><![CDATA[select '东区' cat,'A' series,1 val]]></Query>"
           "<PageQuery><![CDATA[]]></PageQuery></TableData></TableDataMap>")


def make_template():
    return cptxml.empty_skeleton().replace("<TableDataMap/>", DATASET)


# ---------------------------------------------------------------------------
# 1. 图表
# ---------------------------------------------------------------------------
def test_chart_cell_shape_and_data_definition_modes():
    cell = chartxml.chart_cell_xml("column", "ds1", "cat", series="series", value="val")
    assert '<O t="CC">' in cell and "<ChartDefinition>" in cell
    assert "com.fr.plugin.chart.column.VanChartColumnPlot" in cell
    # 饼图带 wrapperName（前端渲染器名），柱形裁剪版没有也能出图（实测）
    assert 'wrapperName="RosePieChart"' in chartxml.chart_cell_xml(
        "pie", "ds1", "cat", value="val")
    assert 'seriesName="series"' in cell and '<CategoryName value="cat"/>' in cell
    # 单系列：seriesName 必须留空（写成分类列会变成"每个分类一个系列"）
    single = chartxml.chart_cell_xml("column", "ds1", "cat", value="val")
    assert 'seriesName=""' in single and '<CategoryName value="cat"/>' in single
    # 单张饼：官方写法是 CategoryName 为空
    pie = chartxml.chart_cell_xml("pie", "ds1", "cat", value="val")
    assert 'seriesName="cat"' in pie and '<CategoryName value=""/>' in pie


def test_chart_title_default_is_hidden():
    hidden = chartxml.chart_cell_xml("line", "ds1", "cat", value="val")
    assert 'TitleVisible value="false"' in hidden
    shown = chartxml.chart_cell_xml("line", "ds1", "cat", value="val", title="销量")
    assert "<![CDATA[销量]]></O>" in shown and 'TitleVisible value="true"' in shown


def test_chart_type_and_fn_validation():
    assert chartxml.check_chart_type("柱形图") == "column"
    with pytest.raises(ApiError):
        chartxml.check_chart_type("radar")
    with pytest.raises(ApiError):
        chartxml.check_chart_fn("median")
    with pytest.raises(ApiError):
        chartxml.chart_cell_xml("column", "ds1", "cat")          # 缺 --value


def test_plan_chart_inserts_and_lists():
    text, changes = reportops.plan_chart(make_template(), at="A1", dataset="ds1", kind="column",
                                         category="cat", series="series", value="val", fn="sum")
    assert changes[0]["kind"] == "chart.insert" and changes[0]["type"] == "column"
    cells = {c["a1"]: c for c in cptxml.cells(text)}
    assert cells["A1"]["kind"] == "other"
    charts = reportops.template_charts_offline(text) if hasattr(
        reportops, "template_charts_offline") else None
    assert charts is None or charts[0]["type"] == "column"
    assert chartxml.detect_type(text) == "column"
    assert chartxml.parse_definition(text) == {
        "class": "OneValueCDDefinition", "series": "series", "value": "val",
        "function": "SumFunction", "dataset": "ds1", "category": "cat"}


def test_plan_chart_rejects_occupied_cell_and_missing_dataset():
    text, _ = reportops.plan_cell(make_template(), "A1", value="占位")
    with pytest.raises(ApiError):
        reportops.plan_chart(text, at="A1", dataset="ds1", category="cat", value="val")
    with pytest.raises(ApiError):
        reportops.plan_chart(make_template(), at="A1", dataset="nope", category="cat",
                             value="val")


# ---------------------------------------------------------------------------
# 2. 参数面板控件
# ---------------------------------------------------------------------------
def test_widget_panel_and_roundtrip():
    text = make_template()
    text, changes = reportops.plan_widget(text, "area", kind="combo",
                                          options=["华东", "华南"], default="华东")
    assert cptxml.panel_element(text) is not None
    items = cptxml.panel_widgets(text)
    assert items[0]["param"] == "area" and items[0]["class"] == "ComboBox"
    assert items[0]["options"] == ["华东=华东", "华南=华南"]
    assert items[0]["default"] == "华东"
    assert [p["name"] for p in cptxml.template_parameters(text)] == ["area"]
    assert any(c["kind"] == "widget.set" for c in changes)


def test_widget_same_name_replaces_and_date_type():
    text = make_template()
    text, _ = reportops.plan_widget(text, "d1", kind="date", default="2026-09-01")
    text, changes = reportops.plan_widget(text, "d1", kind="date", default="2026-10-01")
    assert changes[0]["how"] == "default-updated"
    assert len(cptxml.panel_widgets(text)) == 1          # 同名不重复
    assert cptxml.panel_widgets(text)[0]["default"] == "2026-10-01"


def test_widget_type_validation():
    with pytest.raises(ApiError):
        cptxml.check_widget_type("slider")
    with pytest.raises(ApiError):
        reportops.plan_widget(make_template(), "p", kind="slider")


# ---------------------------------------------------------------------------
# 3. 超链接
# ---------------------------------------------------------------------------
def test_link_written_as_cell_level_group():
    text = make_template()
    text, _ = reportops.plan_cell(text, "A3", value="东区")
    text, changes = reportops.plan_link(text, at="A3", to="目标.cpt",
                                        params=[("center", "=$A3"), ("flag", "1")])
    cell = cptxml.find_cell(text, "A3")
    assert cell["links"] and cell["links"][0]["class"] == "ReportletHyperlink"
    assert cell["links"][0]["target"] == "目标.cpt"
    assert cell["links"][0]["params"] == [{"name": "center", "value": "=$A3"},
                                          {"name": "flag", "value": "1"}]
    # 正确形态是 <C> 的直接子元素；条件属性形态（会渲染出错页）不能混进来
    seg = text[cell["element"].open_start:cell["element"].close_end]
    assert "<NameJavaScriptGroup>" in seg and "HighlightList" not in seg
    assert changes[0]["kind"] == "link.set"


def test_link_clear_keeps_highlights():
    text = make_template()
    text, _ = reportops.plan_cell(text, "A3", value="x")
    text, _ = reportops.plan_highlight(text, "A3", rules=["v>1:bg=#FFC7CE"])
    text, _ = reportops.plan_link(text, at="A3", to="目标.cpt")
    text, _ = reportops.plan_link(text, at="A3", clear=True)
    cell = cptxml.find_cell(text, "A3")
    assert not cell["links"] and cell["hl_count"] == 1     # 条件属性保留


def test_link_web_and_errors():
    text = make_template()
    text, _ = reportops.plan_cell(text, "A1", value="x")
    text, _ = reportops.plan_link(text, at="A1", kind="web", to="https://x.y", frame="_blank")
    assert cptxml.find_cell(text, "A1")["links"][0]["target"] == "https://x.y"
    with pytest.raises(ApiError):
        reportops.plan_link(text, at="A1", kind="reportlet", to="")      # 缺目标
    with pytest.raises(ApiError):
        reportops.plan_link(text, at="Z9", to="x.cpt")                   # 没有格子
    assert "HyperlinkHighlightAction" in cptxml.hyperlink_action_xml(
        "reportlet", "x.cpt")                                            # 对照形态仍可生成


# ---------------------------------------------------------------------------
# 4. 分页 / 页眉页脚
# ---------------------------------------------------------------------------
def test_repeat_header_rows():
    text, changes = reportops.plan_page(make_template(), repeat_header_rows="1:2")
    assert cptxml.page_regions(text)["HR"] == (1, 2)
    assert changes[0]["kind"] == "page.repeat-hr"
    text, _ = reportops.plan_page(text, repeat_header_rows="none")
    assert cptxml.page_regions(text)["HR"] is None
    with pytest.raises(ApiError):
        reportops.plan_page(text, repeat_header_rows="3:1")
    with pytest.raises(ApiError):
        reportops.plan_page(text, repeat_header_rows="x:y")


def test_header_footer_with_page_number():
    text, changes = reportops.plan_page(
        make_template(), footer_text='"第 " + $$page_number + " 页"', footer_formula=True,
        footer_height=20)
    assert any(c["kind"] == "page.footer" for c in changes)
    info = cptxml.page_settings(text)
    assert info["footer_height_pt"] == 20.0
    assert info["footer"] == ['center:"第 " + $$page_number + " 页"']
    # `<Footer>` 必须在 `<ReportAttrSet>` 内（放错父节点会被静默忽略）
    seg = text[text.find("<ReportAttrSet>"):text.find("</ReportAttrSet>")]
    assert "<Footer reportPageType=\"0\">" in seg
    # 页脚内容存在但高度为 0 时，CLI 会自动补一个可用高度
    text2, changes2 = reportops.plan_page(make_template(), footer_text="X")
    assert cptxml.page_settings(text2)["footer_height_pt"] == 20.0
    assert any("不渲染" in (c.get("note") or "") for c in changes2)


def test_page_freeze_flag():
    text, _ = reportops.plan_page(make_template(), page_freeze="on")
    assert cptxml.page_regions(text)["page_freeze"] == (True, True)
    text, _ = reportops.plan_page(text, page_freeze="off")
    assert cptxml.page_regions(text)["page_freeze"] == (False, False)
