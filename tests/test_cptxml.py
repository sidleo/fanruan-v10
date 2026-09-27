"""cpt 结构化编辑的离线回归测试（`frcli report edit` 的底座）。

fixture 照真实模板的结构裁剪而来（WorkBook / TableDataMap / TableData / Parameters /
Connection / Query / PageQuery / Report），并特意放了三样最容易踩的东西：
单元格里的同名 `<Parameters>`（考验「按位置限定」）、XML 注释、含 `>` 的属性值。
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from frcli import cptxml                                    # noqa: E402
from frcli.exceptions import ApiError                       # noqa: E402
from frcli.reportops import plan_edit, to_display_path, to_workspace_path  # noqa: E402

CPT = '''<?xml version="1.0" encoding="UTF-8"?>
<!-- 模板说明：这份 fixture 用于回归测试 -->
<WorkBook xmlVersion="20211223" releaseVersion="10.0.0">
<TableDataMap>
<TableData name="xs" class="com.fr.data.impl.DBTableData">
<Parameters>
<Parameter>
<Attributes name="date"/>
<O>
<![CDATA[]]></O>
</Parameter>
<Parameter>
<Attributes name="zs"/>
<O>
<![CDATA[all]]></O>
</Parameter>
</Parameters>
<Attributes share="true" maxMemRowCount="-1"/>
<Connection class="com.fr.data.impl.NameDatabaseConnection">
<DatabaseName>
<![CDATA[impala_new]]></DatabaseName>
</Connection>
<Query>
<![CDATA[
select sdt, sum(amt) amt from t
where sdt between '${date}' and '20251116'   -- 硬编码结束日期
group by sdt]]>
</Query>
<PageQuery>
<![CDATA[]]>
</PageQuery>
</TableData>
<TableData name="kl" class="com.fr.data.impl.DBTableData">
<Parameters>
<Parameter>
<Attributes name="date"/>
<O>
<![CDATA[]]></O>
</Parameter>
</Parameters>
<Attributes maxMemRowCount="-1"/>
<Connection class="com.fr.data.impl.NameDatabaseConnection">
<DatabaseName><![CDATA[impala_new]]></DatabaseName>
</Connection>
<Query>
<![CDATA[
select sdt, sum(kl) kl from t2 where sdt='20251116']]>
</Query>
</TableData>
</TableDataMap>
<Report class="com.fr.report.worksheet.WorkSheet" name="sheet1">
<ReportPageAttr/>
<CellElementList>
<C c="0" r="0">
<O>
<Parameters>
<Parameter><Attributes name="cell_p"/><O><![CDATA[1]]></O></Parameter>
</Parameters>
</O>
</C>
</CellElementList>
</Report>
<StyleList/>
</WorkBook>
'''


# ---------------------------------------------------------------------------
# 扫描
# ---------------------------------------------------------------------------
def test_template_tag_name_skips_declaration_and_comment():
    assert cptxml.template_tag_name(CPT) == "WorkBook"
    assert cptxml.template_tag_name("<?xml version='1.0'?><Foo/>") == "Foo"


def test_scan_paths_and_nesting():
    els = {e.tag_path: e for e in cptxml.scan(CPT)}
    assert ("WorkBook",) in els
    assert ("WorkBook", "TableDataMap") in els
    assert ("WorkBook", "TableDataMap", "TableData") in els
    assert ("WorkBook", "TableDataMap", "TableData", "Parameters", "Parameter") in els
    assert ("WorkBook", "Report", "CellElementList", "C", "O", "Parameters",
            "Parameter") in els
    # 空元素也要被扫到，且 start == end 区间长度一致
    empty = cptxml.find(CPT, "ReportPageAttr")
    assert len(empty) == 1 and empty[0].empty and empty[0].content(CPT) == ""


def test_scan_survives_gt_in_attribute_and_comments():
    text = '<A><B x="a>b"><C/></B><!-- <D> 注释里的假标签 --></A>'
    names = [e.name for e in cptxml.scan(text)]      # scan 是「闭合顺序」
    assert names == ["C", "B", "A"]
    assert cptxml.find(text, "B")[0].attrs["x"] == "a>b"


# ---------------------------------------------------------------------------
# 定点替换
# ---------------------------------------------------------------------------
def test_set_text_preserves_everything_else():
    el = cptxml.find(CPT, "Query")[0]
    new = cptxml.set_text(CPT, el, "\nselect 1\n")
    # 目标元素之前逐字节相同；之后整段原样保留；CDATA 包裹与缩进风格不变
    assert new[:el.content_start] == CPT[:el.content_start]
    assert new.endswith(CPT[el.content_end:])
    assert "<![CDATA[\nselect 1\n]]>" in new
    assert cptxml.find(new, "Query")[0].text(new) == "\nselect 1\n"


def test_set_text_keeps_cdata_and_rejects_terminator():
    el = cptxml.find(CPT, "Query")[0]
    with pytest.raises(ApiError):
        cptxml.set_text(CPT, el, "select ']]>'")
    doc = '<A><B><![CDATA[x]]></B></A>'
    b = cptxml.find(doc, "B")[0]
    assert cptxml.set_text(doc, b, "y") == '<A><B><![CDATA[y]]></B></A>'


def test_set_text_escapes_when_no_cdata():
    doc = "<A><B>old</B></A>"
    b = cptxml.find(doc, "B")[0]
    assert cptxml.set_text(doc, b, "a<b&c") == "<A><B>a&lt;b&amp;c</B></A>"
    assert cptxml.set_text(doc, b, "plain") == "<A><B>plain</B></A>"


def test_comments_and_style_survive_edit():
    el = cptxml.find(CPT, "Query")[0]
    new = cptxml.set_text(CPT, el, "\nselect 2\n")
    assert "<!-- 模板说明：这份 fixture 用于回归测试 -->" in new
    assert new.endswith("<StyleList/>\n</WorkBook>\n")


# ---------------------------------------------------------------------------
# 语义层
# ---------------------------------------------------------------------------
def test_table_datas_reads_per_dataset():
    tds = {d["name"]: d for d in cptxml.table_datas(CPT)}
    assert list(tds) == ["xs", "kl"]
    assert tds["xs"]["connection"] == "impala_new"
    assert tds["xs"]["class"] == "com.fr.data.impl.DBTableData"
    assert "硬编码结束日期" in tds["xs"]["sql"]
    assert tds["kl"]["sql"].strip() == "select sdt, sum(kl) kl from t2 where sdt='20251116'"


def test_parameters_are_positionally_scoped():
    """回归：只按 tag_path 匹配会把别的数据集（和单元格里的）参数也算进来。"""
    tds = {d["name"]: d for d in cptxml.table_datas(CPT)}
    assert [p["name"] for p in tds["xs"]["parameters"]] == ["date", "zs"]
    assert [p["name"] for p in tds["kl"]["parameters"]] == ["date"]
    defaults = {p["name"]: p["default"] for p in tds["xs"]["parameters"]}
    assert defaults == {"date": "", "zs": "all"}


def test_sql_parameter_refs():
    assert cptxml.sql_parameter_refs(CPT) == ["date"]


def test_summarize_shape():
    info = cptxml.summarize(CPT)
    assert info["root"] == "WorkBook"
    assert [d["name"] for d in info["datasets"]] == ["xs", "kl"]
    assert info["sql_parameter_refs"] == ["date"]


# ---------------------------------------------------------------------------
# plan_edit
# ---------------------------------------------------------------------------
def test_plan_edit_replace_is_scoped_to_one_dataset():
    new, changes = plan_edit(CPT, dataset="kl", replace=["20251116=20251201"])
    tds = {d["name"]: d for d in cptxml.table_datas(new)}
    assert "20251201" in tds["kl"]["sql"]
    assert "20251116" in tds["xs"]["sql"], "别的数据集的 SQL 不能被改到"
    assert changes[0]["kind"] == "dataset.sql"
    assert changes[0]["replacements"] == [{"old": "20251116", "new": "20251201",
                                           "count": 1}]
    assert "-" in changes[0]["diff"] and "+" in changes[0]["diff"]


def test_plan_edit_replace_does_not_touch_report_cells():
    new, _ = plan_edit(CPT, dataset="xs", replace=["'20251116'='20251231'"])
    # 单元格里的 XML 结构一字不动
    assert new[new.index("</TableDataMap>"):] == CPT[CPT.index("</TableDataMap>"):]


def test_plan_edit_errors():
    with pytest.raises(ApiError, match="没有数据集"):
        plan_edit(CPT, dataset="nope", replace=["a=b"])
    with pytest.raises(ApiError, match="没出现"):
        plan_edit(CPT, dataset="kl", replace=["不存在的东西=x"])
    with pytest.raises(ApiError, match="完全相同"):
        plan_edit(CPT, dataset="kl", sql=cptxml.table_datas(CPT)[1]["sql"])
    with pytest.raises(ApiError, match="--replace 要写成"):
        plan_edit(CPT, dataset="kl", replace=["没有等号"])
    with pytest.raises(ApiError, match="只能给一个"):
        plan_edit(CPT, dataset="kl", sql="x", sql_file="y")
    with pytest.raises(ApiError, match="没有参数"):
        plan_edit(CPT, dataset="kl", param="nope", default="1")
    with pytest.raises(ApiError, match="同时给"):
        plan_edit(CPT, dataset="kl", param="date")
    with pytest.raises(ApiError, match="没有给任何编辑动作"):
        plan_edit(CPT, dataset="kl")


def test_plan_edit_param_default():
    new, changes = plan_edit(CPT, dataset="xs", param="date", default="20251201")
    tds = {d["name"]: d for d in cptxml.table_datas(new)}
    defaults = {p["name"]: p["default"] for p in tds["xs"]["parameters"]}
    assert defaults["date"] == "20251201"
    assert defaults["zs"] == "all"
    assert changes[0]["kind"] == "dataset.parameter"
    assert changes[0]["before"] == "" and changes[0]["after"] == "20251201"
    # 另一个数据集不受影响
    assert {p["name"]: p["default"]
            for p in tds["kl"]["parameters"]}["date"] == ""


def test_plan_edit_connection():
    doc = CPT.replace("<![CDATA[impala_new]]>", "<![CDATA[impala_old]]>", 1)
    new, changes = plan_edit(doc, dataset="xs", connection="impala_new2")
    tds = {d["name"]: d for d in cptxml.table_datas(new)}
    assert tds["xs"]["connection"] == "impala_new2"
    assert tds["kl"]["connection"] == "impala_new"     # 第二个数据集没被连坐
    assert changes[0]["kind"] == "dataset.connection"
    with pytest.raises(ApiError, match="本来就是"):
        plan_edit(CPT, dataset="kl", connection="impala_new")


def test_plan_edit_sql_replacement_is_byte_minimal():
    """整段 --sql 替换：除该 <Query> 内容外，整篇字节一致。"""
    tds = {d["name"]: d for d in cptxml.table_datas(CPT)}
    el = tds["kl"]["sql_element"]
    new, _ = plan_edit(CPT, dataset="kl", sql="select 1")
    assert new[:el.content_start] == CPT[:el.content_start]
    assert "<![CDATA[select 1]]>" in new
    assert new.endswith(CPT[el.content_end:])
    assert cptxml.table_datas(new)[1]["sql"] == "select 1"


# ---------------------------------------------------------------------------
# 路径口径
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("given,want", [
    ("reportlets/a/b.cpt", "a/b.cpt"),
    ("/a/b.cpt", "a/b.cpt"),
    ("a/b.cpt", "a/b.cpt"),
])
def test_display_path(given, want):
    assert to_display_path(given) == want


@pytest.mark.parametrize("given,want", [
    ("a/b.cpt", "reportlets/a/b.cpt"),
    ("reportlets/a/b.cpt", "reportlets/a/b.cpt"),
    ("/reportlets/a/b.cpt", "reportlets/a/b.cpt"),
])
def test_workspace_path(given, want):
    assert to_workspace_path(given) == want
