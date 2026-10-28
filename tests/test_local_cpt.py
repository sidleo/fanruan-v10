"""本地示例查找、普通报表与聚合报表的只读检查。"""

import json

import pytest
from click.testing import CliRunner

from frcli import cptxml, local_cpt, reportops
from frcli.commands import report as report_cmd
from frcli.exceptions import ApiError


CPT = """<?xml version="1.0" encoding="UTF-8"?>
<WorkBook>
  <TableDataMap><TableData name="ds1" class="example.EmbeddedTableData"/></TableDataMap>
  <Report class="com.fr.report.worksheet.WorkSheet" name="普通">
    <WorkSheetAttr direction="0" maxRowOrColumn="20"/>
    <FloatElementList><Float><O>标题</O></Float></FloatElementList>
    <CellElementList>
      <C c="0" r="0" cs="2"><O>示例标题</O><Expand/></C>
      <C c="0" r="1"><O t="DSColumn"><Attributes dsName="ds1" columnName="amount"/>
        <RG class="x.FunctionGrouper"><Attr divideMode="1"/></RG></O><Expand dir="0"/></C>
      <C c="1" r="1"><O t="Formula" class="Formula"><Attributes><![CDATA[=SUM(A2)]]></Attributes></O><Expand/></C>
    </CellElementList>
  </Report>
  <Report class="com.fr.report.poly.PolyWorkSheet" name="聚合">
    <Block class="com.fr.report.poly.PolyECBlock"><CellElementList>
      <C c="0" r="0"><O>第一区</O><Expand/></C>
      <C c="1" r="0"><O t="DSColumn"><Attributes dsName="ds1" columnName="id"/>
        <RG class="x.FunctionGrouper"/></O><Expand dir="0"/></C>
    </CellElementList><PECBAttr blockName="block1" x="100" y="200" width="300" height="400"/></Block>
    <Block class="com.fr.report.poly.PolyECBlock"><CellElementList>
      <C c="0" r="0"><O>第二区</O><Expand/></C>
    </CellElementList><PECBAttr blockName="block2" x="500" y="600" width="700" height="800"/></Block>
  </Report>
</WorkBook>
"""


def test_search_reports_all_matches_even_when_output_is_limited(tmp_path):
    (tmp_path / "demo").mkdir()
    (tmp_path / "demo" / "中文示例.cpt").write_text(CPT, encoding="utf-8")
    (tmp_path / "demo" / "普通示例.CPT").write_text(CPT, encoding="utf-8")
    (tmp_path / "demo" / "other.frm").write_text(CPT, encoding="utf-8")
    result = local_cpt.find_examples(tmp_path, keyword="示例", contains="PolyWorkSheet", limit=1)
    assert (result["matched"], result["returned"], result["truncated"]) == (2, 1, True)
    assert result["files"][0].endswith(".cpt") or result["files"][0].endswith(".CPT")
    assert result["skipped_count"] == 0


def test_search_surfaces_invalid_utf8_and_does_not_follow_file_symlinks(tmp_path):
    (tmp_path / "bad.cpt").write_bytes(b"\xff")
    (tmp_path / "good.cpt").write_text(CPT, encoding="utf-8")
    (tmp_path / "alias.cpt").symlink_to(tmp_path / "good.cpt")
    result = local_cpt.find_examples(tmp_path, contains="WorkBook")
    assert result["files"] == ["good.cpt"]
    assert result["skipped_count"] == 2
    assert {item["path"] for item in result["skipped"]} == {"alias.cpt", "bad.cpt"}


def test_inspect_normal_sheet_reports_layout_and_real_cell_semantics(tmp_path):
    source = tmp_path / "test.cpt"
    source.write_text(CPT, encoding="utf-8")
    before = source.read_bytes()
    result = local_cpt.inspect_template(source, include_cells=True, limit=1)
    assert result["datasets"] == [{"name": "ds1", "class": "example.EmbeddedTableData"}]
    assert result["sheets"][0]["worksheet_attributes"]["direction"] == "0"
    assert result["sheets"][0]["floating_elements"] == 1
    assert (result["cell_count"], result["returned"], result["truncated"]) == (3, 1, True)
    assert result["cells"][0]["a1"] == "A1"
    assert result["cells"][0]["text"] == "示例标题"
    assert source.read_bytes() == before
    full = local_cpt.inspect_template(source, include_cells=True)
    assert full["cells"][1]["binding"] == "ds1.amount"
    assert full["cells"][1]["ds_mode"] == "list"
    assert full["cells"][1]["expand"] == "v"
    assert full["cells"][2]["kind"] == "formula"
    assert full["cells"][2]["formula"] == "=SUM(A2)"


def test_poly_cells_keep_block_identity_and_selection(tmp_path):
    source = tmp_path / "poly.cpt"
    source.write_text(CPT, encoding="utf-8")
    result = local_cpt.inspect_template(source, sheet="聚合", include_cells=True)
    assert result["cell_count"] == 3
    assert [(b["name"], b["cell_count"]) for b in result["sheets"][1]["blocks"]] == [
        ("block1", 2), ("block2", 1)]
    assert result["sheets"][1]["blocks"][0]["bounds"]["x"] == "100"
    assert [(c["block_index"], c["a1"], c["text"]) for c in result["cells"]
            if c["a1"] == "A1"] == [(1, "A1", "第一区"), (2, "A1", "第二区")]
    selected = local_cpt.inspect_template(source, sheet="聚合", block=2, include_cells=True)
    assert selected["cell_count"] == 1
    assert selected["cells"][0]["block_name"] == "block2"
    with pytest.raises(ApiError, match="没有第 3 个聚合块"):
        local_cpt.inspect_template(source, sheet="聚合", block=3)


def test_invalid_cpt_and_missing_sheet_are_not_reported_as_empty(tmp_path):
    source = tmp_path / "invalid.cpt"
    source.write_text("<WorkBook><Report>", encoding="utf-8")
    with pytest.raises(ApiError, match="无法读取或解析"):
        local_cpt.inspect_template(source)
    source.write_text("<TableDataMap/>", encoding="utf-8")
    with pytest.raises(ApiError, match="不是 CPT 模板"):
        local_cpt.inspect_template(source)
    source.write_text(CPT, encoding="utf-8")
    with pytest.raises(ApiError, match="不存在或名称不唯一"):
        local_cpt.inspect_template(source, sheet="不存在")


def test_multibyte_encoding_declaration_is_not_a_fatal_scan_error(tmp_path):
    """XML 声明写 GBK/未知编码（内容仍是 UTF-8）时，扫描与单文件检查都应能解析。

    回归：ElementTree 直接吃 bytes 会对多字节编码声明抛 ValueError、未知编码抛 LookupError，
    旧实现整目录扫描 exit 1（code=UNKNOWN），而不是把个别文件记进 skipped。
    """
    (tmp_path / "good.cpt").write_text(CPT, encoding="utf-8")
    (tmp_path / "declared_gbk.cpt").write_text(
        CPT.replace('encoding="UTF-8"', 'encoding="GBK"', 1), encoding="utf-8")
    (tmp_path / "declared_unknown.cpt").write_text(
        CPT.replace('encoding="UTF-8"', 'encoding="X-UNKNOWN"', 1), encoding="utf-8")

    result = local_cpt.profile_examples(str(tmp_path))
    assert result["scanned"] == 3
    assert result["valid"] == 3
    assert result["skipped_count"] == 0
    # 单文件检查同样不应报 UNKNOWN
    inspected = local_cpt.inspect_template(str(tmp_path / "declared_gbk.cpt"))
    assert inspected["file"].endswith("declared_gbk.cpt")


def test_gbk_encoded_bytes_are_skipped_not_fatal(tmp_path):
    """真正 GBK 编码的文件读不成 UTF-8 → 记进 skipped，不影响同目录其它文件。"""
    (tmp_path / "ok.cpt").write_text(CPT, encoding="utf-8")
    (tmp_path / "gbk.cpt").write_bytes(CPT.encode("gbk"))

    result = local_cpt.profile_examples(str(tmp_path))
    assert result["scanned"] == 2
    assert result["valid"] == 1
    assert result["skipped_count"] == 1
    assert "valid_semantics" in result


def test_dataset_remove_on_poly_report_skips_dangling_warning_without_failing():
    """回归：聚合报表删数据集时，悬空绑定告警不能因为普通网格守卫而让操作失败。"""
    from frcli import reportops

    text = cptxml.empty_skeleton("sheet1").replace(
        "<TableDataMap/>",
        '<TableDataMap><TableData name="ds1" class="example.EmbeddedTableData"/></TableDataMap>',
        1)
    poly = text.replace(
        '<Report class="com.fr.report.worksheet.WorkSheet" name="sheet1">',
        '<Report class="com.fr.report.poly.PolyWorkSheet" name="聚合">'
        '<Block class="com.fr.report.poly.PolyECBlock"><CellElementList>'
        '<C c="0" r="0"><O t="DSColumn"><Attributes dsName="ds1" columnName="id"/></O></C>'
        '</CellElementList></Block>', 1)
    new_text, changes = reportops.plan_dataset(poly, op="remove", name="ds1")
    assert any(c["kind"] == "dataset.remove" for c in changes)
    assert 'TableData name="ds1"' not in new_text
    # 悬空绑定告警在聚合报表上被跳过，但不应出现「普通网格不支持」错误
    assert not any(c["kind"] == "error" for c in changes)


def test_poly_regular_grid_reader_and_editor_fail_closed():
    with pytest.raises(ApiError, match="聚合报表"):
        cptxml.cell_rows(CPT, "聚合")
    with pytest.raises(ApiError, match="聚合报表"):
        reportops.plan_cell(CPT, at="A1", sheet="聚合", value="修改")
    assert cptxml.cell_rows(CPT, "普通")[0]["text"] == "示例标题"


def test_local_commands_expand_tilde_paths(tmp_path, monkeypatch):
    """回归：Click 不展开 ~，Path 不能带 exists=True，否则 "~/..." 直接 exit 2。"""
    home = tmp_path / "home"
    (home / "demo").mkdir(parents=True)
    (home / "demo" / "a.cpt").write_text(CPT, encoding="utf-8")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))  # Windows 兼容

    res = CliRunner().invoke(report_cmd.report_group, ["local-examples", "~/demo"])
    assert res.exit_code == 0, res.output
    assert "a.cpt" in res.output

    res = CliRunner().invoke(report_cmd.report_group, ["local-inspect", "~/demo/a.cpt"])
    assert res.exit_code == 0, res.output


def test_offline_cli_never_loads_instance_configuration(tmp_path, monkeypatch):
    source = tmp_path / "test.cpt"
    source.write_text(CPT, encoding="utf-8")

    def unexpected(*args, **kwargs):
        raise AssertionError("离线命令不能读取实例配置或联网")

    monkeypatch.setattr(report_cmd, "load_config", unexpected)
    monkeypatch.setattr(report_cmd, "get_client", unexpected)
    runner = CliRunner()
    found = runner.invoke(report_cmd.report_group, ["local-examples", str(tmp_path),
                                                   "--contains", "PolyWorkSheet"])
    assert found.exit_code == 0, found.output
    assert json.loads(found.output)["matched"] == 1
    profiled = runner.invoke(report_cmd.report_group, [
        "local-profile", str(tmp_path), "--tag", "multi-block"])
    assert profiled.exit_code == 0, profiled.output
    assert json.loads(profiled.output)["matched"] == 1
    inspected = runner.invoke(report_cmd.report_group, [
        "local-inspect", str(source), "--sheet", "聚合", "--cells", "--design"])
    assert inspected.exit_code == 0, inspected.output
    inspected_data = json.loads(inspected.output)
    assert inspected_data["cell_count"] == 3
    assert "aggregate-layout" in inspected_data["design"]["archetypes"]


DESIGN_CPT = """<?xml version="1.0" encoding="UTF-8"?>
<WorkBook>
  <TableDataMap>
    <TableData name="ds1" class="com.fr.data.impl.DBTableData"/>
    <TableData name="ds2" class="com.fr.data.impl.DBTableData"/>
  </TableDataMap>
  <Report class="com.fr.report.worksheet.WorkSheet" name="分析">
    <WorkSheetAttr indexsToCopy="1" maxRowOrColumn="4"/>
    <FloatElementList><Float><O>说明</O></Float></FloatElementList>
    <CellElementList>
      <C c="0" r="0" cs="2" s="0"><O>标题</O>
        <JavaScript class="com.fr.js.ReportletHyperlink"/>
        <HighlightList><Highlight class="com.fr.report.cell.cellattr.highlight.DefaultHighlight">
          <HighlightAction class="com.fr.report.cell.cellattr.highlight.FRFontHighlightAction">
            <FRFont name="Arial" style="1" size="64" foreground="-65536"/>
          </HighlightAction>
        </Highlight></HighlightList>
      </C>
      <C c="0" r="1" s="1"><O t="DSColumn">
        <Attributes dsName="ds1" columnName="category"/>
        <RG class="com.fr.report.cell.cellattr.core.group.FunctionGrouper"><Attr divideMode="1"/></RG>
      </O><Expand dir="0"/></C>
      <C c="1" r="1" s="1"><O t="DSColumn">
        <Attributes dsName="ds1" columnName="month"/>
        <RG class="com.fr.report.cell.cellattr.core.group.FunctionGrouper"/>
      </O><Expand dir="1"/></C>
      <C c="2" r="1" s="1"><O t="DSColumn">
        <Attributes dsName="ds2" columnName="amount"/>
        <RG class="com.fr.report.cell.cellattr.core.group.SummaryGrouper"><FN>SumFunction</FN></RG>
      </O><Expand/></C>
    </CellElementList>
    <Chart name="饼图" chartClass="com.fr.plugin.chart.vanchart.VanChart">
      <Plot class="com.fr.plugin.chart.pie.PiePlot4VanChart"/>
    </Chart>
    <Widget class="com.fr.form.ui.TextEditor"/>
    <Widget class="com.fr.data.impl.BuiltInSQLSubmiter"/>
  </Report>
  <StyleList>
    <Style horizontal_alignment="2"><FRFont name="Arial" size="96" foreground="-16777216"/>
      <Background name="ColorBackground" color="-3380"/><Format>#,##0.00</Format>
      <Border><Bottom style="1"/></Border></Style>
    <Style horizontal_alignment="4"><FRFont name="Arial" size="72" foreground="-65536"/>
      <Background name="ColorBackground" color="-1"/><Border/></Style>
  </StyleList>
</WorkBook>
"""


def test_design_profile_extracts_layout_data_visual_interaction_and_charts(tmp_path):
    source = tmp_path / "design.cpt"
    source.write_text(DESIGN_CPT, encoding="utf-8")
    result = local_cpt.inspect_template(source, include_design=True)
    design = result["design"]
    assert design["archetype"] == "form"
    assert {"form", "crosstab", "master-detail", "chart-analysis"} <= set(design["archetypes"])
    assert {"form-entry", "split-columns", "floating-layout", "crosstab",
            "multi-dataset", "conditional-formatting", "linked-report",
            "number-formatting", "chart-pie"} <= set(design["techniques"])
    assert design["chart_types"] == ["饼图"]
    signals = design["signals"]
    assert signals["layout"]["floating_elements"] == 1
    assert signals["data"]["datasets"] == 2
    assert (signals["data"]["vertical_expand_cells"],
            signals["data"]["horizontal_expand_cells"]) == (1, 1)
    assert signals["visual"]["background_colors"][0] == {"value": "#FFF2CC", "count": 1}
    assert signals["visual"]["font_sizes_pt"] == [9.0, 12.0]
    assert signals["interaction"]["reportlet_links"] == 1


def test_chart_types_ignore_vanchart_attr_nodes_and_use_plot_class(tmp_path):
    """回归：<Attr4VanChartScatter> 这种通用属性节点不能把地图误判成散点图。"""
    text = """<?xml version="1.0" encoding="UTF-8"?>
<WorkBook>
  <Report class="com.fr.report.worksheet.WorkSheet" name="sheet1">
    <CellElementList><C c="0" r="0"><O>图</O></C></CellElementList>
    <Chart name="默认" chartClass="com.fr.plugin.chart.vanchart.VanChart">
      <Plot class="com.fr.plugin.chart.map.VanChartMapPlot"/>
      <Legend4VanChart><Attr4VanChartScatter><Type rangeLegendType="1"/></Attr4VanChartScatter>
      </Legend4VanChart>
    </Chart>
  </Report>
</WorkBook>
"""
    source = tmp_path / "map.cpt"
    source.write_text(text, encoding="utf-8")
    design = local_cpt.inspect_template(source, include_design=True)["design"]
    assert design["chart_types"] == ["地图"]


def test_chart_types_do_not_confuse_heatmap_treemap_with_map(tmp_path):
    """回归：HeatMap/TreeMap 类名同时含 map，不能被更通用的 map 吞掉。"""
    for filename, plot_class, expected in [
            ("tree.cpt", "com.fr.plugin.chart.treemap.VanChartTreeMapPlot", "树图"),
            ("heat.cpt", "com.fr.plugin.chart.heatmap.VanChartHeatMapPlot", "热力图"),
            ("map.cpt", "com.fr.plugin.chart.map.VanChartMapPlot", "地图")]:
        text = ('<?xml version="1.0" encoding="UTF-8"?><WorkBook>'
                '<Report class="com.fr.report.worksheet.WorkSheet" name="sheet1">'
                '<CellElementList><C c="0" r="0"><O>图</O></C></CellElementList>'
                '<Chart name="默认" chartClass="com.fr.plugin.chart.vanchart.VanChart">'
                f'<Plot class="{plot_class}"/></Chart></Report></WorkBook>')
        source = tmp_path / filename
        source.write_text(text, encoding="utf-8")
        design = local_cpt.inspect_template(source, include_design=True)["design"]
        assert design["chart_types"] == [expected], (filename, design["chart_types"])


def test_chart_types_read_combined_vanchartplot_children(tmp_path):
    """组合图（帕累托/柱形+面积等）的各系列在 <VanChartPlot> 子元素里。"""
    text = ('<?xml version="1.0" encoding="UTF-8"?><WorkBook>'
            '<Report class="com.fr.report.worksheet.WorkSheet" name="sheet1">'
            '<CellElementList><C c="0" r="0"><O>图</O></C></CellElementList>'
            '<Chart name="默认" chartClass="com.fr.plugin.chart.vanchart.VanChart">'
            '<Plot class="com.fr.plugin.chart.custom.VanChartCustomPlot"/>'
            '<VanChartPlot class="com.fr.plugin.chart.column.VanChartColumnPlot"/>'
            '<VanChartPlot class="com.fr.plugin.chart.line.VanChartLinePlot"/>'
            '</Chart></Report></WorkBook>')
    source = tmp_path / "combo.cpt"
    source.write_text(text, encoding="utf-8")
    design = local_cpt.inspect_template(source, include_design=True)["design"]
    assert design["chart_types"] == ["柱形图", "折线图"]


def test_chart_types_fall_back_to_chart_class_when_no_plot(tmp_path):
    """轮播图等旧式模板只有 <Chart chartClass="...ColumnMainTypeChart">，没有 Plot。"""
    text = ('<?xml version="1.0" encoding="UTF-8"?><WorkBook>'
            '<Report class="com.fr.report.worksheet.WorkSheet" name="sheet1">'
            '<CellElementList><C c="0" r="0"><O>图</O></C></CellElementList>'
            '<Chart name="默认" chartClass="com.fr.plugin.chart.pie.PieMainTypeChart">'
            '</Chart></Report></WorkBook>')
    source = tmp_path / "carousel.cpt"
    source.write_text(text, encoding="utf-8")
    design = local_cpt.inspect_template(source, include_design=True)["design"]
    assert design["chart_types"] == ["饼图"]


def test_chart_types_recognize_scatter_plot(tmp_path):
    text = ('<?xml version="1.0" encoding="UTF-8"?><WorkBook>'
            '<Report class="com.fr.report.worksheet.WorkSheet" name="sheet1">'
            '<CellElementList><C c="0" r="0"><O>图</O></C></CellElementList>'
            '<Chart name="默认" chartClass="com.fr.plugin.chart.vanchart.VanChart">'
            '<Plot class="com.fr.plugin.chart.scatter.VanChartScatterPlot"/>'
            '</Chart></Report></WorkBook>')
    source = tmp_path / "scatter.cpt"
    source.write_text(text, encoding="utf-8")
    design = local_cpt.inspect_template(source, include_design=True)["design"]
    assert design["chart_types"] == ["散点图"]


def test_unreferenced_styles_do_not_fake_color_coding(tmp_path):
    """没有单元格引用样式时，模板里存在的背景色不应被算成 color-coding。"""
    text = """<?xml version="1.0" encoding="UTF-8"?>
<WorkBook>
  <Report class="com.fr.report.worksheet.WorkSheet" name="sheet1">
    <CellElementList><C c="0" r="0"><O>纯文本</O></C></CellElementList>
  </Report>
  <StyleList><Style><Background name="ColorBackground" color="-3380"/></Style></StyleList>
</WorkBook>
"""
    source = tmp_path / "plain_style.cpt"
    source.write_text(text, encoding="utf-8")
    design = local_cpt.inspect_template(source, include_design=True)["design"]
    assert "color-coding" not in design["techniques"]


def test_local_profile_aggregates_corpus_and_filters_by_design_tag(tmp_path, monkeypatch):
    (tmp_path / "design.cpt").write_text(DESIGN_CPT, encoding="utf-8")
    (tmp_path / "plain.cpt").write_text(CPT, encoding="utf-8")
    (tmp_path / "broken.cpt").write_text("<WorkBook>", encoding="utf-8")
    all_items = local_cpt.profile_examples(tmp_path)
    assert (all_items["scanned"], all_items["valid"], all_items["matched"]) == (3, 2, 2)
    assert all_items["skipped_count"] == 1
    assert all_items["archetypes"]["form"] == 1
    assert all_items["techniques"]["crosstab"] == 1
    assert all_items["chart_types"]["饼图"] == 1
    assert any(item["technique"] == "crosstab" and item["guidance"]
               for item in all_items["design_lessons"])
    filtered = local_cpt.profile_examples(tmp_path, tag="crosstab", limit=1)
    assert filtered["matched"] == filtered["returned"] == 1
    assert filtered["samples"][0]["file"] == "design.cpt"
    assert filtered["samples"][0]["study_points"][0].startswith("交叉表")
    assert filtered["samples"][0]["study_score"] >= 1000
    assert "排序分" in filtered["score_semantics"]
    unfiltered_scores = [item["study_score"] for item in all_items["samples"]]
    assert unfiltered_scores == sorted(unfiltered_scores, reverse=True)


def test_tag_ranking_prefers_focused_baseline_over_incidental_huge_template():
    base = {"archetypes": ["crosstab"], "archetype": "crosstab",
            "techniques": ["crosstab"], "metrics": {
                "cells": 12, "charts": 0, "links": 0, "datasets": 1,
                "styles": 2, "sheets": 1, "vertical_expand": 2,
                "horizontal_expand": 1, "groups": 3, "data_bindings": 3,
            }}
    huge = {"archetypes": ["crosstab", "detail-table"], "archetype": "crosstab",
            "techniques": ["crosstab", "detail-grid", "chart", "formula-calculations",
                           "conditional-formatting", "multi-dataset"],
            "metrics": {
                "cells": 1001, "charts": 20, "links": 40, "datasets": 18,
                "styles": 82, "sheets": 13, "vertical_expand": 36,
                "horizontal_expand": 8, "groups": 60, "data_bindings": 122,
                "widgets": 12, "absolute_nodes": 30, "javascript": 8,
            }}
    assert local_cpt._learning_score(base, "crosstab") > \
        local_cpt._learning_score(huge, "crosstab")
    assert local_cpt._learning_score(huge) > 0


def test_tag_focus_saturates_after_enough_signal():
    enough = {"metrics": {"conditional_formats": 6, "highlight_cells": 20}}
    excessive = {"metrics": {"conditional_formats": 600, "highlight_cells": 2000}}
    assert local_cpt._tag_focus(enough, "conditional-formatting") == \
        local_cpt._tag_focus(excessive, "conditional-formatting")
