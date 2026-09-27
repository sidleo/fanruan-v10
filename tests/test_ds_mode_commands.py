"""数据设置（`<RG>` 分组/列表/汇总）的离线回归测试。

覆盖三件事：
1. 生成的 XML 形状与服务端契约一致（分组自闭合 / 列表 `divideMode="1"` / 汇总 `<FN>`）
2. 读的兼容性：legacy 包名 `com.fr.report.cellElement.core.*`、`<GC>` 同义标签
3. 语义校验：写错就地报错（`--fn` 配非 summary、`--group-by` 配非 summary 等）

真机对照（导出 xlsx 逐格读回）见 `references/cpt-features.md` §1.4；本文件**不联网**。
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from frcli import cptxml, reportops                          # noqa: E402
from frcli.exceptions import ApiError                        # noqa: E402

GROUP = cptxml.FUNCTION_GROUPER
SUMMARY = cptxml.SUMMARY_GROUPER
LEGACY = cptxml.GROUPER_LEGACY_PKG

DATASET = ("<TableDataMap><TableData name=\"ds1\" class=\"com.fr.data.impl.DBTableData\">"
           "<Parameters/><Attributes share=\"true\" maxMemRowCount=\"-1\"/>"
           "<Connection class=\"com.fr.data.impl.NameDatabaseConnection\"><DatabaseName>"
           "<![CDATA[demo_conn]]></DatabaseName></Connection>"
           "<Query><![CDATA[select 1 grp, 2 v]]></Query><PageQuery><![CDATA[]]></PageQuery>"
           "</TableData></TableDataMap>")


def make_template():
    """一张最小可编辑 cpt（只带 ds1，无单元格）。"""
    return cptxml.empty_skeleton().replace("<TableDataMap/>", DATASET)


# ---------------------------------------------------------------------------
# 1. 生成的 XML 形状
# ---------------------------------------------------------------------------
def test_rg_xml_three_shapes():
    assert cptxml.rg_xml("group") == f'<RG class="{GROUP}"/>'
    assert cptxml.rg_xml("list") == f'<RG class="{GROUP}">\n<Attr divideMode="1"/>\n</RG>'
    summary = cptxml.rg_xml("summary", "sum")
    assert summary == (f'<RG class="{SUMMARY}">\n<FN>\n'
                       "<![CDATA[com.fr.data.util.function.SumFunction]]></FN>\n</RG>")
    assert "CountFunction" in cptxml.rg_xml("summary", "count")
    assert "AverageFunction" in cptxml.rg_xml("summary", "avg")
    assert "NoneFunction" in cptxml.rg_xml("summary", "none")


def test_rg_xml_rejects_bad_mode_and_fn():
    with pytest.raises(ApiError, match="--mode 只能是"):
        cptxml.rg_xml("分组模式")
    with pytest.raises(ApiError, match="--fn 只能是"):
        cptxml.rg_xml("summary", "median")
    with pytest.raises(ApiError, match="只在 --mode summary"):
        cptxml.rg_xml("group", "sum")
    with pytest.raises(ApiError, match="只在 --mode summary"):
        cptxml.rg_xml("list", "count")


def test_o_xml_default_mode_is_group_and_always_writes_rg():
    """缺 `<RG>` 在服务端等于分组 —— 但我们**永远显式写出来**，不留隐式。"""
    ds = cptxml.o_xml(binding="ds1.v")
    assert ds.count("<RG ") == 1
    assert f'<RG class="{GROUP}"/>' in ds
    assert ds.index("<Complex/>") < ds.index("<RG ") < ds.index("<Parameters/>")
    assert cptxml.o_xml(binding="ds1.v", ds_mode="list") != ds


def test_o_xml_rejects_ds_mode_on_value_or_formula():
    with pytest.raises(ApiError, match="只对绑定数据集列"):
        cptxml.o_xml(value="x", ds_mode="summary")
    with pytest.raises(ApiError, match="只对绑定数据集列"):
        cptxml.o_xml(formula="=1", ds_mode="list")


@pytest.mark.parametrize("mode,fn,needle", [
    ("group", None, f'<RG class="{GROUP}"/>'),
    ("list", None, '<Attr divideMode="1"/>'),
    ("summary", "sum", "SumFunction"),
    ("summary", "max", "MaxFunction"),
])
def test_cell_xml_carries_data_setting(mode, fn, needle):
    xml = cptxml.cell_xml(0, 1, binding="ds1.v", expand="v", ds_mode=mode, ds_fn=fn)
    assert needle in xml


# ---------------------------------------------------------------------------
# 2. 读：round-trip 与 legacy 兼容
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("mode,fn,expect_fn", [
    ("group", None, None),
    ("list", None, None),
    ("summary", "sum", "SumFunction"),
    ("summary", "count", "CountFunction"),
])
def test_parse_rg_round_trip(mode, fn, expect_fn):
    text = make_template()
    text = cptxml.put_cell(text, "A1",
                           cptxml.cell_xml(0, 0, binding="ds1.v", ds_mode=mode, ds_fn=fn))[0]
    cell = cptxml.find_cell(text, "A1")
    assert cell["ds_mode"] == mode
    assert cell["ds_fn"] == expect_fn
    assert cell["ds_mode_explicit"] is True


def test_parse_rg_missing_means_group():
    """没有 `<RG>` 的历史模板：服务端按分组处理，CLI 也必须这么读。"""
    text = make_template()
    text = cptxml.put_cell(text, "A1", '<C c="0" r="0">\n<O t="DSColumn">\n'
                           '<Attributes dsName="ds1" columnName="v"/>\n<Complex/>\n'
                           "</O>\n<PrivilegeControl/>\n<Expand/>\n</C>")[0]
    cell = cptxml.find_cell(text, "A1")
    assert cell["ds_mode"] == "group"
    assert cell["ds_mode_explicit"] is False


def test_parse_rg_accepts_legacy_package_names():
    """老模板包名 `com.fr.report.cellElement.core.*`（官方语料 385 处）不能被读成"没有"。"""
    text = make_template()
    for i, (mode, fn) in enumerate([("group", None), ("list", None), ("summary", "sum")]):
        text = cptxml.put_cell(
            text, cptxml.format_a1(i, 0),
            cptxml.cell_xml(i, 0, binding="ds1.v", ds_mode=mode, ds_fn=fn))[0]
    text = text.replace(f'class="{GROUP}"', f'class="{LEGACY}.FunctionGrouper"')
    text = text.replace(f'class="{SUMMARY}"', f'class="{LEGACY}.SummaryGrouper"')
    got = {c["a1"]: (c["ds_mode"], c["ds_fn"]) for c in cptxml.cell_rows(text)}
    assert got["A1"] == ("group", None)
    assert got["B1"] == ("list", None)
    assert got["C1"] == ("summary", "SumFunction")


def test_parse_rg_continuum_and_unknown_classes():
    text = make_template()
    text = cptxml.put_cell(text, "A1", '<C c="0" r="0">\n<O t="DSColumn">\n'
                           '<Attributes dsName="ds1" columnName="v"/>\n<Complex/>\n'
                           f'<RG class="{GROUP}">\n<Attr divideMode="2"/>\n</RG>\n'
                           "</O>\n<PrivilegeControl/>\n<Expand/>\n</C>")[0]
    assert cptxml.find_cell(text, "A1")["ds_mode"] == "continuum"


def test_set_grouper_inserts_in_contract_order():
    """没有 `<RG>` 的老格：插入位置必须严格在 `Complex` 之后。"""
    text = make_template()
    text = cptxml.put_cell(text, "A1", '<C c="0" r="0">\n<O t="DSColumn">\n'
                           '<Attributes dsName="ds1" columnName="v"/>\n<Complex/>\n'
                           "<Result>\n<![CDATA[$$$]]></Result>\n<Parameters/>\n</O>\n"
                           "<PrivilegeControl/>\n<Expand/>\n</C>")[0]
    new_text = cptxml.set_grouper(text, cptxml.find_cell(text, "A1"), "list")
    o = new_text[new_text.index('<O t="DSColumn">'):new_text.index("</O>")]
    assert o.index("<Complex/>") < o.index('<RG class=') < o.index("<Result>")
    assert '<Attr divideMode="1"/>' in o
    assert cptxml.find_cell(new_text, "A1")["ds_mode"] == "list"


def test_set_grouper_replaces_existing_rg():
    text = make_template()
    text = cptxml.put_cell(text, "A1",
                           cptxml.cell_xml(0, 0, binding="ds1.v", ds_mode="summary",
                                           ds_fn="sum"))[0]
    new_text = cptxml.set_grouper(text, cptxml.find_cell(text, "A1"), "list")
    assert new_text.count("<RG ") == 1
    assert "SummaryGrouper" not in new_text
    assert cptxml.find_cell(new_text, "A1")["ds_mode"] == "list"


def test_set_grouper_rejects_non_ds_cell():
    text = make_template()
    text = cptxml.put_cell(text, "A1", cptxml.cell_xml(0, 0, value="标题"))[0]
    with pytest.raises(ApiError, match="不是数据集列单元格"):
        cptxml.set_grouper(text, cptxml.find_cell(text, "A1"), "list")


def test_summary_fn_token_maps_class_names():
    assert cptxml.summary_fn_token("SumFunction") == "sum"
    assert cptxml.summary_fn_token("com.fr.data.util.function.CountFunction") == "count"
    assert cptxml.summary_fn_token("DateFunction") is None
    assert cptxml.summary_fn_token(None) is None


# ---------------------------------------------------------------------------
# 3. report table 的 --mode
# ---------------------------------------------------------------------------
def test_plan_table_default_mode_is_list():
    text, changes = reportops.plan_table(make_template(), "ds1", "A2", ["grp", "v"])
    tbl = [c for c in changes if c["kind"] == "table"][0]
    assert tbl["mode"] == "list" and tbl["fn"] is None
    for a1 in ("A2", "B2"):
        assert cptxml.find_cell(text, a1)["ds_mode"] == "list"
    assert '<Attr divideMode="1"/>' in text
    assert "$$$" not in text                       # 规范形状不带 <Result>


def test_plan_table_group_mode():
    text, _ = reportops.plan_table(make_template(), "ds1", "A2", ["grp", "v"], mode="group")
    for a1 in ("A2", "B2"):
        assert cptxml.find_cell(text, a1)["ds_mode"] == "group"
    assert "<Attr divideMode" not in text


def test_plan_table_summary_splits_dims_and_aggs():
    text, changes = reportops.plan_table(make_template(), "ds1", "A2",
                                         ["grp", "sub", "v"], mode="summary",
                                         fn="sum", group_by=["grp", "sub"])
    assert cptxml.find_cell(text, "A2")["ds_mode"] == "group"
    assert cptxml.find_cell(text, "B2")["ds_mode"] == "group"
    v = cptxml.find_cell(text, "C2")
    assert v["ds_mode"] == "summary" and v["ds_fn"] == "SumFunction"
    # 汇总格不扩展；分组格吃 --expand
    assert v["expand"] == "none"
    assert cptxml.find_cell(text, "A2")["expand"] == "v"
    assert [c for c in changes if c["kind"] == "table"][0]["fn"] == "sum"


def test_plan_table_summary_all_columns_is_a_total_row():
    text, _ = reportops.plan_table(make_template(), "ds1", "A2", ["grp", "v"],
                                   mode="summary", fn="count")
    assert cptxml.find_cell(text, "A2")["ds_mode"] == "summary"
    assert cptxml.find_cell(text, "B2")["ds_fn"] == "CountFunction"


@pytest.mark.parametrize("kwargs,match", [
    (dict(mode="group", fn="sum"), "只在 --mode summary"),
    (dict(mode="list", fn="max"), "只在 --mode summary"),
    (dict(mode="list", group_by=["grp"]), "只在 --mode summary"),
    (dict(mode="summary", group_by=["nope"]), "不在 --columns"),
    (dict(mode="summary", group_by=["grp", "grp"]), "重复列名"),
    (dict(mode="summary", group_by=["grp", "v"]), "覆盖了全部列"),
    (dict(mode="nope"), "--mode 只能是"),
])
def test_plan_table_semantic_errors(kwargs, match):
    with pytest.raises(ApiError, match=match):
        reportops.plan_table(make_template(), "ds1", "A2", ["grp", "v"], **kwargs)


def test_plan_table_bad_fn_name():
    with pytest.raises(ApiError, match="--fn 只能是"):
        reportops.plan_table(make_template(), "ds1", "A2", ["grp", "v"],
                             mode="summary", fn="median")


def test_plan_table_header_cells_have_no_data_setting():
    text, _ = reportops.plan_table(make_template(), "ds1", "A2", ["grp", "v"],
                                   header=True, mode="list")
    head = cptxml.find_cell(text, "A2")
    assert head["kind"] == "value" and head["ds_mode"] is None
    assert cptxml.find_cell(text, "A3")["ds_mode"] == "list"


# ---------------------------------------------------------------------------
# 4. report cell 的 --set-ds-mode
# ---------------------------------------------------------------------------
def test_plan_cell_set_ds_mode_keeps_content_and_expand():
    text, _ = reportops.plan_table(make_template(), "ds1", "A2", ["v"], mode="list")
    new_text, changes = reportops.plan_cell(text, "A2", ds_mode="summary", ds_fn="avg")
    cell = cptxml.find_cell(new_text, "A2")
    assert (cell["binding"], cell["expand"], cell["ds_mode"], cell["ds_fn"]) == \
        ("ds1.v", "v", "summary", "AverageFunction")
    assert changes[0]["kind"] == "cell.ds-mode"
    assert changes[0]["before"] == "list" and changes[0]["after"] == "summary"


def test_plan_cell_set_ds_mode_is_idempotent():
    """重复设成同一数据设置：不报错、不改字节、但要看得见"什么都没改"。"""
    text, _ = reportops.plan_table(make_template(), "ds1", "A2", ["v"], mode="list")
    new_text, changes = reportops.plan_cell(text, "A2", ds_mode="list")
    assert new_text == text, "幂等：不该改动任何字节"
    assert any(c["kind"] == "noop" for c in changes)


def test_plan_cell_bind_preserves_existing_ds_mode():
    """只改绑定不能把这一格的数据设置悄悄重置成分组。"""
    text, _ = reportops.plan_table(make_template(), "ds1", "A2", ["v"], mode="summary")
    cell = cptxml.find_cell(text, "A2")
    assert cell["ds_mode"] == "summary"
    new_text, changes = reportops.plan_cell(text, "A2", binding="ds1.grp")
    cell = cptxml.find_cell(new_text, "A2")
    assert cell["binding"] == "ds1.grp"
    assert cell["ds_mode"] == "summary" and cell["ds_fn"] == "SumFunction"
    assert changes[0]["ds_mode"] == "summary" and changes[0]["ds_fn"] == "sum"


def test_plan_cell_bind_preserves_list_mode():
    text, _ = reportops.plan_table(make_template(), "ds1", "A2", ["v"], mode="list")
    new_text, _ = reportops.plan_cell(text, "A2", binding="ds1.grp")
    assert cptxml.find_cell(new_text, "A2")["ds_mode"] == "list"


def test_plan_cell_fn_without_mode_errors():
    text, _ = reportops.plan_table(make_template(), "ds1", "A2", ["v"], mode="list")
    with pytest.raises(ApiError, match="要跟 --set-ds-mode summary 一起用"):
        reportops.plan_cell(text, "A2", ds_fn="sum")


def test_plan_cell_fn_with_non_summary_mode_errors():
    text, _ = reportops.plan_table(make_template(), "ds1", "A2", ["v"], mode="list")
    with pytest.raises(ApiError, match="只在 --mode summary"):
        reportops.plan_cell(text, "A2", ds_mode="group", ds_fn="sum")


def test_plan_cell_set_ds_mode_on_value_cell_errors():
    text = make_template()
    text = cptxml.put_cell(text, "A1", cptxml.cell_xml(0, 0, value="标题"))[0]
    with pytest.raises(ApiError, match="不是数据集列单元格"):
        reportops.plan_cell(text, "A1", ds_mode="list")


def test_plan_cell_unknown_summary_fn_on_rebind_errors():
    """老模板里 CLI 不认识的汇总函数（如 DateFunction）：改绑定时给人话报错。"""
    text = make_template()
    text = cptxml.put_cell(text, "A1", cptxml.cell_xml(0, 0, binding="ds1.v",
                                                       ds_mode="summary", ds_fn="min"))[0]
    text = text.replace("MinFunction", "DateFunction")
    with pytest.raises(ApiError, match="CLI 不认识它"):
        reportops.plan_cell(text, "A1", binding="ds1.grp")


# ---------------------------------------------------------------------------
# 5. 拦不住的静默坏法至少要有 warning
# ---------------------------------------------------------------------------
def test_summary_mode_warns_about_text_columns():
    """`SummaryGrouper` 用在文本列上服务端会静默得到 0（列类型离线查不到）。"""
    _, changes = reportops.plan_table(make_template(), "ds1", "A2", ["grp", "v"],
                                      mode="summary", group_by=["grp"], fn="sum")
    msgs = [c["message"] for c in changes if c["kind"] == "warning"]
    assert any("数值列" in m and "v" in m for m in msgs)


def test_list_and_group_modes_have_no_summary_warning():
    for mode in ("list", "group"):
        _, changes = reportops.plan_table(make_template(), "ds1", "A2", ["grp", "v"],
                                          mode=mode)
        assert not any("数值列" in c.get("message", "") for c in changes)


def test_set_ds_mode_summary_warns():
    text, _ = reportops.plan_table(make_template(), "ds1", "A2", ["v"], mode="list")
    _, changes = reportops.plan_cell(text, "A2", ds_mode="summary", ds_fn="sum")
    assert any("数值列" in c.get("message", "") for c in changes)
