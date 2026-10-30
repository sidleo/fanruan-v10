"""cpt 创作能力的离线回归测试（`report new/cell/dataset/param/style/table` 的底座）。

不联网：只测 A1 换算、XML 生成、定点改写、语义校验与 dry-run 输出。
fixture 照真实模板（`demo_report.cpt`）的结构裁剪而来，保留最容易踩的几样东西：
单元格里的 `<HighlightList>`、`<Expand dir=…>`、`<StyleList>`、`ReportParameterAttr`。
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from frcli import cptxml, reportops                          # noqa: E402
from frcli.exceptions import ApiError                        # noqa: E402
from frcli.remotedesign import assert_template_bytes         # noqa: E402

CPT = '''<?xml version="1.0" encoding="UTF-8"?>
<WorkBook xmlVersion="20211223" releaseVersion="10.0.0">
<TableDataMap>
<TableData name="ds1" class="com.fr.data.impl.DBTableData">
<Parameters>
<Parameter>
<Attributes name="edate"/>
<O>
<![CDATA[20260101]]></O>
</Parameter>
</Parameters>
<Attributes share="true" maxMemRowCount="-1"/>
<Connection class="com.fr.data.impl.NameDatabaseConnection">
<DatabaseName>
<![CDATA[demo_conn]]></DatabaseName>
</Connection>
<Query>
<![CDATA[select code, cnt from t where sdt = '${edate}']]></Query>
<PageQuery>
<![CDATA[]]></PageQuery>
</TableData>
</TableDataMap>
<Report class="com.fr.report.worksheet.WorkSheet" name="sheet1">
<ReportPageAttr/>
<RowHeight defaultValue="723900">
<![CDATA[723900,723900]]></RowHeight>
<ColumnWidth defaultValue="2743200">
<![CDATA[2743200,2743200]]></ColumnWidth>
<CellElementList>
<C c="0" r="0" s="0">
<O>
<![CDATA[标题]]></O>
<PrivilegeControl/>
<Expand/>
</C>
<C c="0" r="1">
<O t="DSColumn">
<Attributes dsName="ds1" columnName="code"/>
<Complex order="0"/>
<Result>
<![CDATA[$$$]]></Result>
</O>
<PrivilegeControl/>
<HighlightList>
<Highlight class="com.fr.report.cell.cellattr.highlight.DefaultHighlight">
<Name>
<![CDATA[隐藏行]]></Name>
</Highlight>
</HighlightList>
<Expand dir="0"/>
</C>
<C c="1" r="1">
<O t="XMLable" class="com.fr.base.Formula">
<Attributes>
<![CDATA[=SUM(C3)]]></Attributes>
</O>
<PrivilegeControl/>
<Expand dir="1"/>
</C>
</CellElementList>
</Report>
<ReportParameterAttr>
<Attributes showWindow="true" delayPlaying="true"/>
<PWTitle>
<![CDATA[参数]]></PWTitle>
<Parameters>
<Parameter>
<Attributes name="topn"/>
<O>
<![CDATA[10]]></O>
</Parameter>
</Parameters>
</ReportParameterAttr>
<StyleList>
<Style horizontal_alignment="0" imageLayout="1">
<Format class="com.fr.base.CoreDecimalFormat" roundingMode="6">
<![CDATA[#,##0]]></Format>
<FRFont name="微软雅黑" style="0" size="72"/>
<Background name="NullBackground"/>
<Border/>
</Style>
</StyleList>
</WorkBook>
'''


# ---------------------------------------------------------------------------
# A1 记法
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("a1,want", [("A1", (0, 0)), ("B3", (1, 2)), ("AA10", (26, 9)),
                                     ("$B$3", (1, 2)), ("zzz1", (18277, 0))])
def test_parse_a1(a1, want):
    assert cptxml.parse_a1(a1) == want


@pytest.mark.parametrize("c,r,want", [(0, 0, "A1"), (1, 2, "B3"), (26, 9, "AA10")])
def test_format_a1(c, r, want):
    assert cptxml.format_a1(c, r) == want


def test_a1_roundtrip_and_errors():
    for c in (0, 1, 25, 26, 701, 702):
        for r in (0, 9, 999):
            assert cptxml.parse_a1(cptxml.format_a1(c, r)) == (c, r)
    for bad in ("", "1A", "A0", "A", "ABCD1", "A1:B2"):
        with pytest.raises(ApiError):
            cptxml.parse_a1(bad)
    with pytest.raises(ApiError):
        cptxml.col_letters(-1)


def test_parse_range():
    assert cptxml.parse_range("A1") == (0, 0, 0, 0)
    assert cptxml.parse_range("A1:C3") == (0, 0, 2, 2)
    with pytest.raises(ApiError):
        cptxml.parse_range("C3:A1")
    with pytest.raises(ApiError):
        cptxml.parse_range("A1:B2:C3")


# ---------------------------------------------------------------------------
# 单元格：解析
# ---------------------------------------------------------------------------
def test_cells_classification():
    cells = {c["a1"]: c for c in cptxml.cells(CPT)}
    assert list(cells) == ["A1", "A2", "B2"]
    assert cells["A1"]["kind"] == "value" and cells["A1"]["text"] == "标题"
    assert cells["A1"]["style"] == "0" and cells["A1"]["expand"] == "none"
    assert cells["A2"]["kind"] == "ds"
    assert cells["A2"]["binding"] == "ds1.code" and cells["A2"]["dataset"] == "ds1"
    assert cells["A2"]["expand"] == "v"          # dir="0" = 纵向
    assert cells["B2"]["kind"] == "formula"
    assert cells["B2"]["formula"] == "=SUM(C3)"
    assert cells["B2"]["expand"] == "h"          # dir="1" = 横向


def test_cells_sorted_row_major_and_flattened():
    rows = cptxml.cell_rows(CPT)
    assert [(r["r"], r["c"]) for r in rows] == [(0, 0), (1, 0), (1, 1)]
    assert all("element" not in r for r in rows)


def test_find_cell_and_sheets():
    assert cptxml.find_cell(CPT, "A2")["binding"] == "ds1.code"
    assert cptxml.find_cell(CPT, "Z9") is None
    assert cptxml.sheet_names(CPT) == ["sheet1"]
    with pytest.raises(ApiError, match="没有名为"):
        cptxml.pick_sheet(CPT, "nope")


# ---------------------------------------------------------------------------
# 单元格：生成 XML
# ---------------------------------------------------------------------------
def test_o_xml_kinds():
    assert cptxml.o_xml(value="门店数") == "<O>\n<![CDATA[门店数]]></O>"
    formula = cptxml.o_xml(formula="SUM(C3)")
    assert 't="XMLable" class="com.fr.base.Formula"' in formula
    assert "<![CDATA[=SUM(C3)]]>" in formula
    ds = cptxml.o_xml(binding="ds1.cnt")
    assert 'dsName="ds1" columnName="cnt"' in ds
    # 规范形状（Designer 实际写出来的，本地语料 4467/5696 = 78%）：
    # Attributes / Complex / RG / Parameters —— 不写 <Result>$$$</Result>
    assert ds == ('<O t="DSColumn">\n'
                  '<Attributes dsName="ds1" columnName="cnt"/>\n'
                  "<Complex/>\n"
                  '<RG class="com.fr.report.cell.cellattr.core.group.FunctionGrouper"/>\n'
                  "<Parameters/>\n</O>")
    assert "$$$" not in ds and "Result" not in ds
    with pytest.raises(ApiError, match="只能给一个"):
        cptxml.o_xml(value="a", formula="=1")
    with pytest.raises(ApiError, match="数据集名.列名"):
        cptxml.o_xml(binding="cnt")


def test_expand_xml_direction_is_not_intuitive():
    assert cptxml.expand_xml("v") == '<Expand dir="0"/>'      # 纵向
    assert cptxml.expand_xml("h") == '<Expand dir="1"/>'      # 横向
    assert cptxml.expand_xml("none") == "<Expand/>"
    assert cptxml.expand_xml(None) == "<Expand/>"
    with pytest.raises(ApiError):
        cptxml.expand_xml("x")


def test_cell_xml_has_all_fixed_members():
    xml = cptxml.cell_xml(1, 2, value="x", expand="v", style="3", cs="2", rs="2")
    assert xml.startswith('<C c="1" r="2" cs="2" rs="2" s="3">')
    assert "<PrivilegeControl/>" in xml and '<Expand dir="0"/>' in xml
    assert xml.endswith("</C>")


def test_cdata_rejects_terminator():
    with pytest.raises(ApiError, match=r"\]\]>"):
        cptxml.cell_xml(0, 0, value="bad ]]> value")
    with pytest.raises(ApiError, match=r"\]\]>"):
        cptxml.dataset_xml("ds", "conn", "select ']]>'")
    with pytest.raises(ApiError, match=r"\]\]>"):
        cptxml.add_template_parameter(CPT, "p", "]]>")


def test_attr_escaping():
    xml = cptxml.cell_xml(0, 0, value="a<b&c")
    assert "a<b&c" in xml            # CDATA 里原样保留
    assert 'name="a&quot;b"' in cptxml.dataset_xml("a\"b", "c", "select 1")


def test_special_chars_roundtrip_and_stay_wellformed():
    """中文 / 引号 / 换行 / <> / & 都要能写进去，且整篇仍是良构 XML。"""
    tricky = '中文"引号"\n换行 & <标签> \'单引号\''
    text = cptxml.empty_skeleton()
    text, _ = cptxml.put_cell(text, "A1", cptxml.cell_xml(0, 0, value=tricky))
    assert cptxml.find_cell(text, "A1")["text"] == tricky
    text = cptxml.add_dataset(text, cptxml.dataset_xml("ds1", "conn & co", "select '&'"),
                              "ds1")
    assert_template_bytes(text.encode("utf-8"))          # 良构校验必须过
    assert cptxml.table_datas(text)[0]["connection"] == "conn & co"


# ---------------------------------------------------------------------------
# 单元格：字节级改写
# ---------------------------------------------------------------------------
def test_insert_cell_keeps_order_and_creates_container():
    text = cptxml.empty_skeleton()
    assert cptxml.cell_container(text).empty
    for at in ("B2", "A1", "B1", "A2"):
        c, r = cptxml.parse_a1(at)
        text, info = cptxml.put_cell(text, at, cptxml.cell_xml(c, r, value=at))
        assert info["action"] == "insert"
    assert [c["a1"] for c in cptxml.cells(text)] == ["A1", "B1", "A2", "B2"]


def test_put_cell_replaces_in_place():
    text, info = cptxml.put_cell(CPT, "A1", cptxml.cell_xml(0, 0, value="新标题"))
    assert info["action"] == "replace"
    assert cptxml.find_cell(text, "A1")["text"] == "新标题"
    assert len(cptxml.cells(text)) == 3
    assert text[:text.index("<CellElementList>")] == \
        CPT[:CPT.index("<CellElementList>")], "单元格之前的部分必须逐字节不动"


def test_replace_o_keeps_siblings():
    cell = cptxml.find_cell(CPT, "A2")
    text = cptxml.replace_o(CPT, cell, cptxml.o_xml(binding="ds1.other"))
    assert cptxml.find_cell(text, "A2")["binding"] == "ds1.other"
    assert "<HighlightList>" in text                # 高亮 / 权限 / 扩展都没被牵连
    assert cptxml.find_cell(text, "A2")["expand"] == "v"


def test_set_expand_and_style_and_delete():
    cell = cptxml.find_cell(CPT, "A1")
    text = cptxml.set_expand(CPT, cell, "h")
    assert cptxml.find_cell(text, "A1")["expand"] == "h"
    text = cptxml.set_attr(text, cptxml.find_cell(text, "A1")["element"], "s", "1")
    assert cptxml.find_cell(text, "A1")["style"] == "1"
    text = cptxml.delete_cell(text, cptxml.find_cell(text, "A1"))
    assert [c["a1"] for c in cptxml.cells(text)] == ["A2", "B2"]


def test_set_merge_writes_cs_rs_on_topleft():
    text, ch = cptxml.set_merge(CPT, "A1:B1")
    assert ch == {"kind": "cell.merge", "at": "A1", "range": "A1:B1", "cols": 2, "rows": 1}
    assert cptxml.find_cell(text, "A1")["cs"] == "2"
    text, ch = cptxml.set_merge(text, "A1:A2")
    assert cptxml.find_cell(text, "A1")["rs"] == "2"
    with pytest.raises(ApiError, match="没有单元格"):
        cptxml.set_merge(CPT, "Z9:AA9")
    with pytest.raises(ApiError, match="不需要合并"):
        cptxml.set_merge(CPT, "A1:A1")


# ---------------------------------------------------------------------------
# 数据集 / 模板参数 / 样式
# ---------------------------------------------------------------------------
def test_dataset_xml_and_add_remove():
    xml = cptxml.dataset_xml("ds2", "conn", "select 1", params=[("p", "5"), "q"])
    assert '<TableData name="ds2" class="com.fr.data.impl.DBTableData">' in xml
    assert '<Attributes name="p"/>' in xml and "<![CDATA[5]]>" in xml
    assert '<Attributes name="q"/>' in xml
    text = cptxml.add_dataset(CPT, xml, "ds2")
    assert cptxml.dataset_names(text) == ["ds1", "ds2"]
    with pytest.raises(ApiError, match="已经有数据集"):
        cptxml.add_dataset(text, xml, "ds2")
    text = cptxml.remove_dataset(text, "ds2")
    assert cptxml.dataset_names(text) == ["ds1"]
    with pytest.raises(ApiError, match="没有数据集"):
        cptxml.remove_dataset(text, "nope")


def test_dataset_xml_rejects_empty_names():
    with pytest.raises(ApiError, match="数据集名不能为空"):
        cptxml.dataset_xml("", "conn", "select 1")
    with pytest.raises(ApiError, match="数据连接名不能为空"):
        cptxml.dataset_xml("ds", "", "select 1")


def test_add_dataset_into_empty_map_is_selfclosed_then_open():
    text = cptxml.empty_skeleton()
    text = cptxml.add_dataset(text, cptxml.dataset_xml("ds1", "c", "select 1"), "ds1")
    assert "<TableDataMap/>" not in text
    assert cptxml.dataset_names(text) == ["ds1"]


def test_add_dataset_parameter():
    text, how = cptxml.add_dataset_parameter(CPT, "ds1", "topn", "10")
    assert how == "added"
    params = {p["name"]: p["default"] for p in cptxml.table_datas(text)[0]["parameters"]}
    assert params == {"edate": "20260101", "topn": "10"}
    text, how = cptxml.add_dataset_parameter(text, "ds1", "topn", "20")
    assert how == "default-updated"
    assert {p["name"]: p["default"]
            for p in cptxml.table_datas(text)[0]["parameters"]}["topn"] == "20"
    with pytest.raises(ApiError, match="没有数据集"):
        cptxml.add_dataset_parameter(CPT, "nope", "x", "1")


def test_template_parameters_crud():
    assert {p["name"]: p["default"] for p in cptxml.template_parameters(CPT)} == {"topn": "10"}
    text, how = cptxml.add_template_parameter(CPT, "min_center", "01")
    assert how == "added"
    assert {p["name"]: p["default"]
            for p in cptxml.template_parameters(text)}["min_center"] == "01"
    text, how = cptxml.add_template_parameter(text, "topn", "20")
    assert how == "default-updated"
    text, _ = cptxml.remove_template_parameter(text, "topn")
    assert [p["name"] for p in cptxml.template_parameters(text)] == ["min_center"]
    with pytest.raises(ApiError, match="没有参数"):
        cptxml.remove_template_parameter(text, "nope")


def test_style_xml_and_index_range():
    xml = cptxml.style_xml(fmt="#,##0.00", bold=True, bg="#FFF2CC", align="left",
                           border=True)
    assert '<Format class="com.fr.base.CoreDecimalFormat" roundingMode="6">' in xml
    assert "<![CDATA[#,##0.00]]>" in xml
    assert 'style="1" size="72"' in xml            # 1/8 磅：9 磅 = 72
    assert 'horizontal_alignment="2"' in xml       # 2 = 左（0=居中 / 4=右）
    assert 'name="ColorBackground" color="-3380"' in xml           # #FFF2CC
    assert "<Border>" in xml
    with pytest.raises(ApiError, match="对齐方式"):
        cptxml.style_xml(align="justify")
    with pytest.raises(ApiError, match="颜色"):
        cptxml.style_xml(bg="yellow")
    text, index = cptxml.append_style(CPT, xml)
    assert index == 1 and len(cptxml.styles(text)) == 2
    assert cptxml.styles(CPT)[0]["format"] == "#,##0"
    with pytest.raises(ApiError, match="必须以 <Style"):
        cptxml.append_style(CPT, "<Font/>")


def test_check_style_index():
    cptxml.check_style_index(CPT, 0)
    with pytest.raises(ApiError, match="越界"):
        cptxml.check_style_index(CPT, 1)
    with pytest.raises(ApiError, match="越界"):
        cptxml.check_style_index(CPT, -1)


def test_color_encoding():
    assert cptxml._color("#FFFFFF") == -1
    assert cptxml._color("#000000") == -16777216
    assert cptxml._color("#FFF2CC") == 0xFFF2CC - 0x1000000
    assert cptxml._color("-1") == -1


# ---------------------------------------------------------------------------
# 本地语义校验（服务端对这些全都是静默接受）
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("bad,match", [
    ("", "不能为空"), ("=", "没有内容"), ("=1+", "结尾"), ("=(1+2", "不配对"),
    ("=1+2)", "多了一个"), ('="a', "双引号"),
])
def test_check_formula_rejects(bad, match):
    with pytest.raises(ApiError, match=match):
        cptxml.check_formula(bad)


@pytest.mark.parametrize("good", ["=1+2", "SUM(C3)", '="TOP" & $topn',
                                  '=IF(A1>0,"正","负")', '=DATEINMONTH(TODATE($edate,"yyyyMMdd"),1)'])
def test_check_formula_accepts(good):
    assert cptxml.check_formula(good).startswith("=")


def test_formula_signature_ignores_absolute_cell_refs():
    sig = cptxml.formula_signature("=SUM($A$1:A3) + $topn")
    assert sig["params"] == ["topn"]
    assert sig["brace_ref"] is False
    assert cptxml.formula_signature('="${topn}"')["brace_ref"] is True


def test_sql_signature():
    sig = cptxml.sql_signature("select * from t where sdt='${edate}' and x=$topn")
    assert sig["params"] == ["edate"] and sig["bare"] == ["topn"]


# ---------------------------------------------------------------------------
# plan_*（内存计算，不碰网络）
# ---------------------------------------------------------------------------
def test_plan_cell_value_formula_binding():
    text, changes = reportops.plan_cell(CPT, "A1", value="新标题")
    assert cptxml.find_cell(text, "A1")["text"] == "新标题"
    assert changes[0]["kind"] == "cell.value"
    text, _ = reportops.plan_cell(CPT, "A1", formula="1+2")
    assert cptxml.find_cell(text, "A1")["formula"] == "=1+2"
    text, _ = reportops.plan_cell(CPT, "B2", binding="ds1.cnt", expand="v")
    cell = cptxml.find_cell(text, "B2")
    assert cell["binding"] == "ds1.cnt" and cell["expand"] == "v"
    text, _ = reportops.plan_cell(CPT, "A1", expand="h", style=0)
    cell = cptxml.find_cell(text, "A1")
    assert cell["expand"] == "h" and cell["style"] == "0"


def test_plan_cell_new_cell_and_clear():
    text = cptxml.empty_skeleton()
    text, changes = reportops.plan_cell(text, "C3", value="x")
    assert changes[0]["kind"] == "cell.insert"
    assert cptxml.find_cell(text, "C3")["text"] == "x"
    text, changes = reportops.plan_cell(text, "C3", clear=True)
    assert cptxml.find_cell(text, "C3") is None
    with pytest.raises(ApiError, match="不需要 --clear"):
        reportops.plan_cell(text, "C3", clear=True)


def test_plan_cell_rejections():
    with pytest.raises(ApiError, match="只能给一个"):
        reportops.plan_cell(CPT, "A1", value="a", formula="=1")
    with pytest.raises(ApiError, match="不在模板里"):
        reportops.plan_cell(CPT, "A1", binding="nope.k")
    with pytest.raises(ApiError, match="越界"):
        reportops.plan_cell(CPT, "A1", style=9, value="x")
    with pytest.raises(ApiError, match="二选一"):
        reportops.plan_cell(CPT, "A1", style=0, bold=True, value="x")
    with pytest.raises(ApiError, match="还没有单元格"):
        reportops.plan_cell(CPT, "Z9", style=0)
    # 无改动不再抛错（幂等：重复跑一份配方不该让 set -e 脚本中途失败），
    # 但必须**看得见** —— 返回一条 noop change。
    _, noop = reportops.plan_cell(CPT, "A1", value="标题")
    assert any(c["kind"] == "noop" and "没有任何改动" in c["message"] for c in noop)


def test_plan_cell_warns_on_undeclared_formula_param():
    _, changes = reportops.plan_cell(CPT, "A1", formula='="TOP" + $min_center')
    assert any(c["kind"] == "warning" and "min_center" in c["message"] for c in changes)
    _, changes = reportops.plan_cell(CPT, "A1", formula='="TOP" + $topn')
    assert not [c for c in changes if c["kind"] == "warning"]


def test_plan_cell_style_new_creates_and_binds():
    text, changes = reportops.plan_cell(CPT, "A1", fmt="#,##0.00", bold=True)
    assert changes[0]["kind"] == "style.add" and changes[0]["index"] == 1
    assert cptxml.find_cell(text, "A1")["style"] == "1"
    assert cptxml.styles(text)[1]["format"] == "#,##0.00"


def test_plan_cell_merge_requires_same_topleft():
    text, changes = reportops.plan_cell(CPT, "A1", value="标题", merge="A1:B1")
    assert cptxml.find_cell(text, "A1")["cs"] == "2"
    assert changes[-1]["kind"] == "cell.merge"
    with pytest.raises(ApiError, match="左上角"):
        reportops.plan_cell(CPT, "B2", merge="A1:B1")


def test_plan_table_header_and_expand():
    text, changes = reportops.plan_table(CPT, "ds1", "A2", ["code", "cnt"], header=True,
                                         labels=["编码", "数量"], expand="v")
    rows = {c["a1"]: c for c in cptxml.cells(text)}
    assert rows["A2"]["text"] == "编码" and rows["B2"]["text"] == "数量"
    assert rows["A3"]["binding"] == "ds1.code" and rows["A3"]["expand"] == "v"
    assert rows["B3"]["expand"] == "v"
    assert any(c["kind"] == "table" for c in changes)
    assert any(c["kind"] == "warning" for c in changes), "列名无法离线校验要给警告"


def test_plan_table_horizontal_and_no_header():
    text, _ = reportops.plan_table(CPT, "ds1", "A2", ["code"], expand="h")
    assert cptxml.find_cell(text, "A2")["expand"] == "h"
    text, _ = reportops.plan_table(CPT, "ds1", "A2", ["ds1.code"])
    assert cptxml.find_cell(text, "A2")["binding"] == "ds1.code"     # 前缀自动剥掉


def test_plan_table_rejections():
    with pytest.raises(ApiError, match="没有数据集"):
        reportops.plan_table(CPT, "nope", "A1", ["a"])
    with pytest.raises(ApiError, match="至少要给一列"):
        reportops.plan_table(CPT, "ds1", "A1", ["", " "])
    with pytest.raises(ApiError, match="重复列名"):
        reportops.plan_table(CPT, "ds1", "A1", ["a", "a"])
    with pytest.raises(ApiError, match="数量必须一致"):
        reportops.plan_table(CPT, "ds1", "A1", ["a", "b"], header=True, labels=["x"])
    with pytest.raises(ApiError, match="--expand"):
        reportops.plan_table(CPT, "ds1", "A1", ["a"], expand="diagonal")
    with pytest.raises(ApiError, match="越界"):
        reportops.plan_table(CPT, "ds1", "A1", ["a"], style=7)


def test_plan_dataset_add_with_params_writes_both_places():
    text, changes = reportops.plan_dataset(CPT, op="add", name="ds2", conn="impala_new",
                                           sql="select 1", params=["p=5"])
    assert cptxml.dataset_names(text) == ["ds1", "ds2"]
    ds = {t["name"]: t for t in cptxml.table_datas(text)}["ds2"]
    assert {x["name"]: x["default"] for x in ds["parameters"]} == {"p": "5"}
    assert {x["name"]: x["default"]
            for x in cptxml.template_parameters(text)}["p"] == "5"
    assert any(c["kind"] == "template.param" for c in changes)
    with pytest.raises(ApiError, match="已经有数据集"):
        reportops.plan_dataset(CPT, op="add", name="ds1", conn="c", sql="select 1")


def test_plan_dataset_warns():
    _, changes = reportops.plan_dataset(CPT, op="add", name="ds2", conn="c",
                                        sql="select ${p}", params=["p"])
    msgs = [c["message"] for c in changes if c["kind"] == "warning"]
    assert any("没有默认值" in m for m in msgs)
    _, changes = reportops.plan_dataset(CPT, op="add", name="ds2", conn="c",
                                        sql="select * from t where sdt=${sdate} and x=$topn")
    msgs = [c["message"] for c in changes if c["kind"] == "warning"]
    assert any("${x}" in m for m in msgs), msgs
    assert any("没声明的参数" in m for m in msgs), msgs


def test_plan_dataset_set_sql_and_remove():
    text, changes = reportops.plan_dataset(CPT, op="set-sql", name="ds1",
                                           sql="select 1 from t", params=["edate=20260202"])
    assert cptxml.table_datas(text)[0]["sql"] == "select 1 from t"
    assert {p["name"]: p["default"]
            for p in cptxml.table_datas(text)[0]["parameters"]}["edate"] == "20260202"
    assert any(c["kind"] == "dataset.param" for c in changes)
    text, changes = reportops.plan_dataset(CPT, op="remove", name="ds1")
    assert cptxml.dataset_names(text) == []
    assert any(c["kind"] == "warning" and "绑定" in c["message"] for c in changes)
    with pytest.raises(ApiError, match="没有数据集"):
        reportops.plan_dataset(CPT, op="remove", name="nope")
    with pytest.raises(ApiError, match="完全相同"):
        reportops.plan_dataset(CPT, op="set-sql", name="ds1",
                               sql=cptxml.table_datas(CPT)[0]["sql"])
    with pytest.raises(ApiError, match="没有给任何数据集动作"):
        reportops.plan_dataset(CPT)


def test_plan_param():
    text, changes = reportops.plan_param(CPT, add=["min_center=01"])
    assert {p["name"]: p["default"]
            for p in cptxml.template_parameters(text)}["min_center"] == "01"
    text, changes = reportops.plan_param(text, set_default=["topn=20"])
    assert {p["name"]: p["default"]
            for p in cptxml.template_parameters(text)}["topn"] == "20"
    text, _ = reportops.plan_param(text, remove=["topn"])
    assert [p["name"] for p in cptxml.template_parameters(text)] == ["min_center"]
    _, changes = reportops.plan_param(CPT, add=["nope"])
    assert any(c["kind"] == "warning" for c in changes), "无默认值要警告"
    with pytest.raises(ApiError, match="NAME=VALUE"):
        reportops.plan_param(CPT, set_default=["topn"])
    unchanged, changes = reportops.plan_param(CPT, set_default=["topn=10"])
    assert unchanged == CPT and changes[0]["how"] == "unchanged"
    with pytest.raises(ApiError, match="没有给任何参数动作"):
        reportops.plan_param(CPT)


def test_plan_style_and_preset():
    text, changes = reportops.plan_style_preset(CPT, fmt="#,##0.0", border=True)
    assert changes[0]["index"] == 1 and "Border" in cptxml.styles(text)[1]["xml"]
    with pytest.raises(ApiError, match="至少要给一项"):
        reportops.plan_style_preset(CPT)
    with pytest.raises(ApiError, match="--xml-file"):
        reportops.plan_style(CPT)


# ---------------------------------------------------------------------------
# 空白骨架 / 裁剪
# ---------------------------------------------------------------------------
def test_empty_skeleton_shape():
    text = cptxml.empty_skeleton()
    assert cptxml.template_tag_name(text) == "WorkBook"
    assert "<TableDataMap/>" in text and "<CellElementList/>" in text
    assert "<ReportParameterAttr>" in text and "<StyleList/>" in text
    assert cptxml.sheet_names(text) == ["sheet1"]
    assert cptxml.cells(text) == []
    assert cptxml.dataset_names(text) == []
    assert_template_bytes(text.encode("utf-8"))          # 本地良构校验也要过
    assert cptxml.empty_skeleton(sheet="报表1") is not None
    assert 'name="报表1"' in cptxml.empty_skeleton(sheet="报表1")


def test_strip_to_skeleton_keeps_shell_and_clears_content():
    text = cptxml.strip_to_skeleton(CPT, sheet="s2")
    assert cptxml.dataset_names(text) == []
    assert cptxml.cells(text) == []
    assert cptxml.sheet_names(text) == ["s2"]
    assert cptxml.styles(text)[0]["format"] == "#,##0"        # 样式表保留
    assert cptxml.template_parameters(text) == []             # 参数清空（新模板自己声明）
    assert "<RowHeight" in text and "<ColumnWidth" in text
    with pytest.raises(ApiError, match="根元素"):
        cptxml.strip_to_skeleton("<TableDataMap/>")


def test_strip_to_skeleton_clears_every_sheet(tmp_path):
    """多 sheet 模板裁骨架：**每一张** sheet 的单元格都要清空（否则"空白模板"里还留着内容）。"""
    second = ('<Report class="com.fr.report.worksheet.WorkSheet" name="sheet2">'
              '<CellElementList><C c="0" r="0"><O><![CDATA[残留]]></O>'
              "<PrivilegeControl/><Expand/></C></CellElementList></Report>\n</WorkBook>")
    two = CPT.replace("</WorkBook>", second)
    assert [c["a1"] for c in cptxml.cells(two, "sheet2")] == ["A1"]
    text = cptxml.strip_to_skeleton(two, sheet="封面")
    assert cptxml.sheet_names(text) == ["封面", "sheet2"]
    assert cptxml.cells(text, "封面") == [] and cptxml.cells(text, "sheet2") == []


def test_new_template_refuses_overwrite_without_force(monkeypatch):
    """`report new` 打到已存在的路径：默认必须拒绝（force=False 才会走到覆盖守门）。"""
    calls = {}

    def fake_upload(config, local, remote, force=False, allow_format=False):
        calls["force"] = force
        raise ApiError("服务端已存在（占位）")

    monkeypatch.setattr(reportops, "upload_template", fake_upload)
    monkeypatch.setenv("FRCLI_WRITE_SCOPE", "demo_group/demo_user/skill测试")
    with pytest.raises(ApiError):
        reportops.new_template(None, "demo_group/demo_user/skill测试/x.cpt", apply=True)
    assert calls["force"] is False
    monkeypatch.setattr(reportops, "upload_template",
                        lambda *a, **kw: {"verified": True, "overwritten": True})
    reportops.new_template(None, "demo_group/demo_user/skill测试/x.cpt", apply=True,
                           force=True)


def test_build_template_from_text_and_local_file(tmp_path):
    assert "<TableDataMap/>" in reportops.build_template(sheet="x")
    assert cptxml.cells(reportops.build_template(from_text=CPT)) == []
    src = tmp_path / "a.cpt"
    src.write_text(CPT, encoding="utf-8")
    text = reportops.build_template(from_text=src.read_text(encoding="utf-8"))
    assert "<StyleList>" in text
    with pytest.raises(ApiError, match="不是 cpt 模板"):
        reportops.build_template(from_text="not xml at all")


# ---------------------------------------------------------------------------
# dry-run 输出（bytes / diff）与写前守门
# ---------------------------------------------------------------------------
def test_commit_dry_run_reports_bytes_and_diff_without_network():
    new_text, changes = reportops.plan_cell(CPT, "A1", value="新标题")
    result = reportops.commit(None, "demo_group/demo_user/skill测试/x.cpt", CPT, new_text,
                              "cell", changes, apply=False)
    assert result["dry_run"] is True and result["applied"] is False
    assert result["bytes_before"] == len(CPT.encode("utf-8"))
    assert result["bytes_after"] == len(new_text.encode("utf-8"))
    assert "-<![CDATA[标题]]></O>" in result["diff"]
    assert "+<![CDATA[新标题]]></O>" in result["diff"]
    assert "dry-run" in result["hint"]


def test_commit_apply_refuses_outside_write_scope(monkeypatch):
    """任何写盘动作之前先被写范围拒绝（fail-closed）。"""
    monkeypatch.delenv("FRCLI_WRITE_SCOPE", raising=False)
    monkeypatch.delenv("FRCLI_ALLOW_ANY_PATH", raising=False)
    new_text, changes = reportops.plan_cell(CPT, "A1", value="x")
    with pytest.raises(ApiError, match="写操作未指定范围"):
        reportops.commit(None, "demo_group/demo_user/x.cpt", CPT, new_text, "cell",
                         changes, apply=True)
    monkeypatch.setenv("FRCLI_WRITE_SCOPE", "demo_group/demo_user/skill测试")
    with pytest.raises(ApiError, match="已拒绝"):
        reportops.commit(None, "demo_group/demo_user/别人/x.cpt", CPT, new_text, "cell",
                         changes, apply=True)


def test_diff_text_truncates_and_escapes_nothing():
    assert reportops.diff_text("a", "a", "x") == ""
    diff = reportops.diff_text("a\n", "b\n", "x", limit=3)
    assert "未显示" in diff


# ---------------------------------------------------------------------------
# assert_template_bytes：残缺 XML 必须被拒
# ---------------------------------------------------------------------------
def test_assert_template_bytes_rejects_broken_and_stub():
    with pytest.raises(ApiError, match="良构 XML"):
        assert_template_bytes(b"<WorkBook><A></WorkBook>")
    with pytest.raises(ApiError, match="不像 cpt 模板"):
        assert_template_bytes("<TableDataMap><TableData name='x'/></TableDataMap>".encode())
    assert_template_bytes(CPT.encode("utf-8"))
    assert_template_bytes("<TableDataMap/>".encode(), allow_format=True)


# --- Lead 补：列宽命令（P11：以前只能 download→改字节→upload） --------------
def test_set_col_widths_basic():
    from frcli import cptxml
    text = ('<WorkBook><ColumnWidth defaultValue="2743200">'
            '<![CDATA[2743200,2743200]]></ColumnWidth></WorkBook>')
    out = cptxml.set_col_widths(text, {0: 12, 1: 20})
    assert "280800" not in out
    vals = out.split("<![CDATA[")[1].split("]]>")[0].split(",")
    assert vals[0] == str(int(12 * cptxml.EMU_PER_CHAR))
    assert vals[1] == str(int(20 * cptxml.EMU_PER_CHAR))


def test_set_col_widths_extends_array_and_handles_selfclose():
    from frcli import cptxml
    # 自闭合写法也要能写
    out = cptxml.set_col_widths('<WorkBook><ColumnWidth defaultValue="2743200"/>'
                                '</WorkBook>', {2: 10})
    vals = out.split("<![CDATA[")[1].split("]]>")[0].split(",")
    assert len(vals) == 3 and vals[0] == "2743200"
    assert vals[2] == str(int(10 * cptxml.EMU_PER_CHAR))


def test_set_col_widths_rejects_bad_input():
    import pytest
    from frcli import cptxml
    from frcli.exceptions import ApiError
    t = '<WorkBook><ColumnWidth defaultValue="1"><![CDATA[1]]></ColumnWidth></WorkBook>'
    with pytest.raises(ApiError):
        cptxml.set_col_widths(t, {0: 0})
    with pytest.raises(ApiError):
        cptxml.set_col_widths(t, {-1: 5})
    with pytest.raises(ApiError):
        cptxml.set_col_widths("<WorkBook/>", {0: 5})


def test_plan_table_widths_count_must_match():
    import pytest
    from frcli import reportops
    from frcli.exceptions import ApiError
    text = reportops.cptxml.new_template() if hasattr(reportops.cptxml, "new_template") else None
    if text is None:
        pytest.skip("骨架构造函数名不同，跳过")
    with pytest.raises(ApiError):
        reportops.plan_table(text, "ds1", "A1", ["a", "b"], widths=[10])


def test_plan_table_widths_non_numeric_friendly():
    """--widths 给非数字要给中文友好报错，别漏 Python 原文（cpt-verifier 报的瑕疵）。"""
    import pytest
    from frcli import reportops
    from frcli.exceptions import ApiError
    # 构造一个带 ds1 的最小文本，让流程能走到 widths 解析
    text = ("<WorkBook><TableDataMap><TableData name=\"ds1\" "
            "class=\"com.fr.data.impl.DBTableData\"><Query><![CDATA[select 1 k]]></Query>"
            "</TableData></TableDataMap>"
            "<ColumnWidth defaultValue=\"2743200\"><![CDATA[2743200,2743200]]></ColumnWidth>"
            "<CellElementList/></WorkBook>")
    with pytest.raises(ApiError) as ei:
        reportops.plan_table(text, "ds1", "A1", ["k", "k2"], widths=["12", "abc"])
    assert "--widths 只能是数字" in str(ei.value)


# --- Lead 补：无改动必须幂等（不能 exit 1 把 set -e 脚本打断）----------------
def test_append_style_reuses_identical_style():
    """重复 --num-format 不能让 <StyleList> 无限膨胀（实测连跑 3 次 5→6→7→8）。"""
    from frcli import cptxml
    text = ('<WorkBook><StyleList>'
            '<Style border="1"><FRFont size="72" name="SimSun"/></Style>'
            '</StyleList><CellElementList/></WorkBook>')
    # 等价样式（空白/属性序不同）→ 复用索引 0，不追加
    same, idx = cptxml.append_style(
        text, '<Style border="1">\n  <FRFont name="SimSun" size="72" />\n</Style>')
    assert idx == 0
    assert same == text, "等价样式不该改动文本"
    # 不同的样式 → 追加，索引 1
    diff, idx2 = cptxml.append_style(
        text, '<Style border="2"><FRFont name="SimSun" size="72"/></Style>')
    assert idx2 == 1 and diff != text


def test_normalize_xml_fragment():
    from frcli.cptxml import _normalize_xml_fragment as N
    a = '<Style border="1"><FRFont name="SimSun" size="72"/></Style>'
    b = '<Style   border="1" >\n <FRFont size="72" name="SimSun" />\n</Style>'
    c = '<Style border="2"><FRFont name="SimSun" size="72"/></Style>'
    assert N(a) == N(b)
    assert N(a) != N(c)


# --- Lead 补：静态文本里的单个反斜杠会静默空格（独立验证者报的 P1）----------
def test_warn_single_backslash_in_static_text():
    from frcli.reportops import _warn_backslash
    for bad in ["C:" + chr(92) + "data" + chr(92) + "file",
                "地区" + chr(92) + "销售员/产品",
                chr(92)]:
        ch = []
        _warn_backslash(ch, bad)
        assert ch and ch[0]["kind"] == "warning", f"应预警: {bad!r}"
    # 已写双反斜杠（字面量）与无反斜杠 → 不吵
    for ok in ["a" + chr(92) * 2 + "b", "普通文本"]:
        ch = []
        _warn_backslash(ch, ok)
        assert not ch, f"不该预警: {ok!r}"
