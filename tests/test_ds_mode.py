"""数据设置（分组 / 列表 / 汇总）的离线回归。

本文件守的是 2026-09 那次「P9」的根因：**缺 `<RG>` 的单元格，服务端按「分组」处理**
（`com.fr.report.cell.cellattr.core.group.DSColumn.getGrouper()` 在 null 时惰性返回
`new FunctionGrouper()`，而 `FunctionGrouper.divideMode` 初值 0 = `GROUPING_MODE`）。
即「标签不在」≠「设置没有」——所以写入侧必须**显式**写 `<RG>`，读取侧必须把
「没有 `<RG>`」如实报成*分组*而不是*列表*。

服务端侧的三形态实测见 `docs/验证/cpt数据设置验证报告.md`（本文件只覆盖离线可判定的部分）。
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from frcli import cptxml                                     # noqa: E402
from frcli.exceptions import ApiError                        # noqa: E402
from frcli.reportops import plan_table                       # noqa: E402

FG = "com.fr.report.cell.cellattr.core.group.FunctionGrouper"
SG = "com.fr.report.cell.cellattr.core.group.SummaryGrouper"
LEGACY_FG = "com.fr.report.cellElement.core.FunctionGrouper"
LEGACY_SG = "com.fr.report.cellElement.core.SummaryGrouper"

TEMPLATE = '''<?xml version="1.0" encoding="UTF-8"?>
<WorkBook xmlVersion="20211223" releaseVersion="10.0.0">
<TableDataMap><TableData name="ds1" class="com.fr.data.impl.DBTableData">
<Parameters/><Attributes share="true" maxMemRowCount="-1"/>
<Connection class="com.fr.data.impl.NameDatabaseConnection">
<DatabaseName><![CDATA[c1]]></DatabaseName></Connection>
<Query><![CDATA[select 1 k,2 v]]></Query><PageQuery><![CDATA[]]></PageQuery>
</TableData></TableDataMap>
<StyleList/>
<Report class="com.fr.report.WorkSheet" name="sheet1">
<ReportPageAttr><HR/><FR/><HC/><FC/></ReportPageAttr>
<RowHeight defaultValue="723900"><![CDATA[723900]]></RowHeight>
<ColumnWidth defaultValue="2743200"><![CDATA[2743200]]></ColumnWidth>
<CellElementList>
__CELLS__
</CellElementList>
</Report>
</WorkBook>
'''


def td(cell_xml: str) -> str:
    return TEMPLATE.replace("__CELLS__", cell_xml)


def only_ds(text):
    cells = [c for c in cptxml.cells(text) if c.get("kind") == "ds"]
    assert cells, "没有解析出数据集单元格"
    return cells[0]


# --------------------------------------------------------------------------
# 1. P9 根因：缺 `<RG>` = 分组（服务端语义），且写入侧绝不省略 `<RG>`
# --------------------------------------------------------------------------
def test_missing_rg_reports_group_not_list():
    """没有 `<RG>` 的单元格必须报「分组」——服务端就是这么处理的。

    这是 P9 的核心断言：早期 `report table` 不写 `<RG>`，于是每个数据格都成了
    「分组」（相同值合并、数值列去重），而不是用户以为的「列表」。
    """
    old = ('<C c="0" r="0">\n<O t="DSColumn">\n'
           '<Attributes dsName="ds1" columnName="k"/>\n<Complex order="0"/>\n'
           '<Result>\n<![CDATA[$$$]]></Result>\n</O>\n'
           '<PrivilegeControl/>\n<Expand dir="0"/>\n</C>')
    c = only_ds(td(old))
    assert c["ds_mode"] == "group"
    assert c["ds_mode_explicit"] is False      # 但要让调用方知道"这是缺省推断出来的"


def test_o_xml_always_writes_explicit_rg():
    """绑定数据集列时 `<RG>` 必须显式写出（默认 group 也要写）。"""
    for mode in ("group", "list", "summary"):
        x = cptxml.o_xml(binding="ds1.k", ds_mode=mode)
        assert "<RG " in x, f"{mode} 形态漏写了 <RG>"
        assert only_ds(td(f'<C c="0" r="0">\n{x}\n<PrivilegeControl/>\n<Expand dir="0"/>\n</C>'))[
            "ds_mode_explicit"] is True


# --------------------------------------------------------------------------
# 2. 三形态的 XML 契约 + 读写往返
# --------------------------------------------------------------------------
def test_three_modes_xml_contract():
    assert cptxml.rg_xml("group") == f'<RG class="{FG}"/>'
    assert cptxml.rg_xml("list") == f'<RG class="{FG}">\n<Attr divideMode="1"/>\n</RG>'
    assert cptxml.rg_xml("summary", "sum") == (
        f'<RG class="{SG}">\n<FN>\n'
        '<![CDATA[com.fr.data.util.function.SumFunction]]></FN>\n</RG>')


@pytest.mark.parametrize("mode,fn,expect_mode,expect_fn", [
    ("group", None, "group", None),
    ("list", None, "list", None),
    ("summary", "sum", "summary", "SumFunction"),
    ("summary", "count", "summary", "CountFunction"),
    ("summary", "avg", "summary", "AverageFunction"),
    ("summary", None, "summary", "SumFunction"),      # 汇总默认 sum
])
def test_mode_round_trip(mode, fn, expect_mode, expect_fn):
    """写出去的 XML 读回来必须是同一个形态（分组键名/函数名都要还原）。"""
    x = cptxml.o_xml(binding="ds1.k", ds_mode=mode, ds_fn=fn)
    c = only_ds(td(f'<C c="0" r="0">\n{x}\n<PrivilegeControl/>\n<Expand dir="0"/>\n</C>'))
    assert (c["ds_mode"], c["ds_fn"]) == (expect_mode, expect_fn)


def test_cell_xml_summary_does_not_expand_by_default_when_asked():
    """`cell_xml` 的扩展方向由调用方决定；汇总格一般写 `<Expand/>`。"""
    x = cptxml.cell_xml(0, 0, binding="ds1.v", expand="none", ds_mode="summary", ds_fn="sum")
    assert "<Expand/>" in x
    y = cptxml.cell_xml(0, 0, binding="ds1.v", expand="v", ds_mode="list")
    assert '<Expand dir="0"/>' in y


# --------------------------------------------------------------------------
# 3. 旧包名 / 旧标签：读的时候必须认（否则老模板会被读成"没有设置"）
# --------------------------------------------------------------------------
@pytest.mark.parametrize("cls,expect", [
    (LEGACY_FG, "group"),
    (LEGACY_SG, "summary"),
])
def test_legacy_package_names_are_recognized(cls, expect):
    x = (f'<C c="0" r="0">\n<O t="DSColumn">\n'
         f'<Attributes dsName="ds1" columnName="k"/>\n<Complex/>\n'
         f'<RG class="{cls}"/>\n<Parameters/>\n</O>\n'
         '<PrivilegeControl/>\n<Expand dir="0"/>\n</C>')
    c = only_ds(td(x))
    assert c["ds_mode"] == expect
    assert c["ds_mode_explicit"] is True


def test_legacy_divide_mode_read_inside_legacy_class():
    x = (f'<C c="0" r="0">\n<O t="DSColumn">\n'
         f'<Attributes dsName="ds1" columnName="k"/>\n<Complex/>\n'
         f'<RG class="{LEGACY_FG}">\n<Attr divideMode="1"/>\n</RG>\n</O>\n'
         '<PrivilegeControl/>\n<Expand dir="0"/>\n</C>')
    assert only_ds(td(x))["ds_mode"] == "list"


def test_legacy_gc_tag_is_recognized():
    """老模板里 `<RG>` 的同义标签是 `<GC>`。"""
    x = (f'<C c="0" r="0">\n<O t="DSColumn">\n'
         f'<Attributes dsName="ds1" columnName="k"/>\n<Complex/>\n'
         f'<GC class="{FG}"/>\n</O>\n'
         '<PrivilegeControl/>\n<Expand dir="0"/>\n</C>')
    assert only_ds(td(x))["ds_mode"] == "group"


@pytest.mark.parametrize("cls,expect", [
    ("com.fr.report.cell.cellattr.core.group.MonoGrouper", "list"),
    ("com.fr.report.cell.cellattr.core.group.IndexGrouper", "index"),
    ("com.fr.report.cell.cellattr.core.group.CustomGrouper", "custom"),
])
def test_other_groupers(cls, expect):
    x = (f'<C c="0" r="0">\n<O t="DSColumn">\n'
         f'<Attributes dsName="ds1" columnName="k"/>\n<Complex/>\n'
         f'<RG class="{cls}"/>\n</O>\n'
         '<PrivilegeControl/>\n<Expand dir="0"/>\n</C>')
    assert only_ds(td(x))["ds_mode"] == expect


def test_continuum_mode_is_known_and_not_confused_with_group():
    """divideMode=2 是「连续分组」，不能被当成普通分组。"""
    x = cptxml.rg_xml("group").replace("/>", '>\n<Attr divideMode="2"/>\n</RG>')
    c = only_ds(td(f'<C c="0" r="0">\n<O t="DSColumn">\n'
                   f'<Attributes dsName="ds1" columnName="k"/>\n<Complex/>\n{x}\n</O>\n'
                   '<PrivilegeControl/>\n<Expand dir="0"/>\n</C>'))
    assert c["ds_mode"] == "continuum"


def test_unknown_grouper_is_not_silently_reported_as_a_known_mode():
    """不存在的 Grouper 类名 → `unknown`（不谎报成分组/列表）。

    实测：这种模板导出会报错（`export csv` 甚至会把 HTML 出错页写成 .csv），
    所以绝不能把它读成某个正常形态后"照原样写回去"。
    """
    x = ('<C c="0" r="0">\n<O t="DSColumn">\n'
         '<Attributes dsName="ds1" columnName="k"/>\n<Complex/>\n'
         '<RG class="com.fr.report.cell.cellattr.core.group.ListGrouper"/>\n</O>\n'
         '<PrivilegeControl/>\n<Expand dir="0"/>\n</C>')
    assert only_ds(td(x))["ds_mode"] == "unknown"


# --------------------------------------------------------------------------
# 4. 本地语义校验：写错就地报错，不静默出坏模板
# --------------------------------------------------------------------------
def test_fn_is_only_meaningful_for_summary():
    with pytest.raises(ApiError, match="只在 --mode summary"):
        cptxml.check_ds_mode("list", "sum")
    with pytest.raises(ApiError, match="只在 --mode summary"):
        cptxml.rg_xml("group", "sum")
    assert cptxml.check_ds_mode("summary", "sum") == "summary"


def test_bad_mode_rejected():
    with pytest.raises(ApiError, match="只能是 group"):
        cptxml.check_ds_mode("bogus")


def test_bad_summary_fn_rejected():
    with pytest.raises(ApiError, match="--fn 只能是"):
        cptxml.check_summary_fn("NotAFunction")


def test_summary_fn_aliases():
    assert cptxml.check_summary_fn("total") == "SumFunction"
    assert cptxml.check_summary_fn("average") == "AverageFunction"


def test_ds_mode_on_value_cell_is_rejected():
    """值/公式单元格没有数据设置，给了就要报错（否则用户以为设置生效了）。"""
    with pytest.raises(ApiError, match="只对绑定数据集列"):
        cptxml.o_xml(value="合计", ds_mode="list")
    with pytest.raises(ApiError, match="只对绑定数据集列"):
        cptxml.o_xml(formula="=SUM(A1)", ds_fn="sum")


def test_binding_must_be_dataset_dot_column():
    with pytest.raises(ApiError, match="数据集名.列名"):
        cptxml.o_xml(binding="ds1")


@pytest.mark.parametrize("expand,expect", [
    ("v", '<Expand dir="0"/>'),
    ("h", '<Expand dir="1"/>'),
    ("none", "<Expand/>"),
])
def test_expand_xml(expand, expect):
    assert cptxml.expand_xml(expand) == expect


def test_bad_expand_rejected():
    with pytest.raises(ApiError, match="扩展方向"):
        cptxml.expand_xml("diagonal")


# --------------------------------------------------------------------------
# 5. report table 的默认形态：必须是列表（记录原样展开）
# --------------------------------------------------------------------------
def test_plan_table_default_mode_is_list():
    """`report table` 默认 `--mode list`：早期版本不写 `<RG>`（= 服务端分组）是 P9 的根因。"""
    text, changes = plan_table(TEMPLATE, "ds1", "A1", ["k", "v"], header=True)
    assert [c for c in changes if c["kind"] == "table"][0]["mode"] == "list"
    for c in (c for c in cptxml.cells(text) if c.get("kind") == "ds"):
        assert c["ds_mode"] == "list", "默认形态必须是列表"
        assert c["ds_mode_explicit"] is True, "必须显式写 <RG>"


def test_plan_table_summary_writes_group_for_group_by_columns():
    text, _ = plan_table(TEMPLATE, "ds1", "A1", ["k", "v"], group_by=["k"], mode="summary", fn="sum")
    modes = {c["binding"]: (c["ds_mode"], c["ds_fn"]) for c in cptxml.cells(text)
             if c.get("kind") == "ds"}
    assert modes["ds1.k"] == ("group", None)
    assert modes["ds1.v"] == ("summary", "SumFunction")


def test_plan_table_group_by_only_with_summary():
    with pytest.raises(ApiError, match="只在 --mode summary"):
        plan_table(TEMPLATE, "ds1", "A1", ["k", "v"], group_by=["k"], mode="list")


def test_plan_table_rejects_group_by_covering_all_columns():
    with pytest.raises(ApiError, match="没有列会被汇总"):
        plan_table(TEMPLATE, "ds1", "A1", ["k", "v"], group_by=["k", "v"], mode="summary")


def test_plan_table_rejects_unknown_or_duplicate_columns():
    with pytest.raises(ApiError, match="不在 --columns"):
        plan_table(TEMPLATE, "ds1", "A1", ["k", "v"], group_by=["nope"], mode="summary")
    with pytest.raises(ApiError, match="重复列名"):
        plan_table(TEMPLATE, "ds1", "A1", ["k", "k"])
