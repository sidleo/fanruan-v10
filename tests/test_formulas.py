"""函数检索、词法边界及公式默认值的回归；不访问本机配置和网络。"""

import json
import xml.etree.ElementTree as ET
from collections import Counter

import httpx
import pytest
from click.testing import CliRunner

from frcli import cptxml, formulas, reportops
from frcli.cli import main
from frcli.exceptions import ApiError
from frcli.function_catalog import FUNCTIONS


EXPR = '=FORMAT(TODAY()-1,"yyyyMMdd")'
TARGET = "demo_group/demo_user/formulas.cpt"


@pytest.fixture(autouse=True)
def isolate(monkeypatch, tmp_path):
    config = tmp_path / "config.yaml"
    config.write_text("default: demo\ninstances:\n  demo:\n    url: https://reports.example.com\n"
                      "    username: demo_user\n    password: demo_password\n", encoding="utf-8")
    monkeypatch.setenv("FRCLI_CONFIG", str(config))
    monkeypatch.delenv("FRCLI_INSTANCE", raising=False)
    monkeypatch.delenv("FRCLI_WRITE_SCOPE", raising=False)
    monkeypatch.delenv("FRCLI_ALLOW_ANY_PATH", raising=False)

    def no_network(*args, **kwargs):
        pytest.fail("离线回归不允许访问网络")

    monkeypatch.setattr(httpx.Client, "request", no_network)


def template():
    text = cptxml.empty_skeleton()
    text, _ = reportops.plan_dataset(text, op="add", name="ds", conn="demo_conn",
                                    sql="select '${edate}' as d", params=["edate=20261001"])
    text, _ = reportops.plan_dataset(text, op="add", name="other", conn="demo_conn",
                                    sql="select '${edate}' as d", params=["edate=20261001"])
    return text


def test_catalog_covers_implementation_inventory_and_dataset_methods():
    assert len(FUNCTIONS) == 183
    assert Counter(row["source_jar"] for row in FUNCTIONS.values()) == {
        "fine-core-10.0.jar": 167, "fine-report-engine-10.0.jar": 13, None: 3}
    assert all(row["category"] in formulas.CATEGORIES for row in FUNCTIONS.values())
    assert {"QUERY", "SUMPRECISE", "MAPARRAY", "RANK", "SORT", "DATASET.GROUP"} <= FUNCTIONS.keys()
    assert "ENNUMBER" in FUNCTIONS and "ENNUMER" not in FUNCTIONS
    assert FUNCTIONS["CIRCULAR"]["summary"] == "按前期单元格循环引用累计"
    assert FUNCTIONS["WRITEARRAY"]["signature"] == "WRITEARRAY(value1,value2,...)"
    assert FUNCTIONS["TOTEXT"]["signature"] == "TOTEXT(constantName)"
    assert all(row["signature"] for row in FUNCTIONS.values())


@pytest.mark.parametrize("expr", [
    "SUM([1,2])", "IF(1=1,'a)b','c')", '="a(b"',
    r'CONCATENATE("a\"(b","c")', r"='a\'b)'", '="a""(b"',
    "=SUM(B3[!0]{B3>$B3})", "=销量.group(地区,,false)",
    "=LET(a,1,b,2,a+b)", '=QUERY(\'{"a":[1,2]}\',"$.a[0]")',
])
def test_valid_quote_array_and_coordinate_syntax(expr):
    assert formulas.check_formula(expr).startswith("=")
    text, _ = reportops.plan_cell(cptxml.empty_skeleton(), "A1", formula=expr)
    assert cptxml.cells(text)[0]["formula"] == formulas.check_formula(expr)


@pytest.mark.parametrize("expr,match", [
    ("='abc", "单引号"), ('="abc', "双引号"), ("SUM([1,2)", "不匹配"),
    ("SUM(A1[!0)", "不匹配"), ("=A1[!0", "没闭合"), ("=1+", "结尾"),
    ("=1)", "多了一个"), ("=", "没有内容"), ("", "不能为空"),
])
def test_broken_formula_rejected(expr, match):
    with pytest.raises(ApiError, match=match):
        formulas.check_formula(expr)


def test_function_scan_ignores_literals_and_recognizes_dataset_context():
    out = formulas.analyze_formula("=IF($limit>0,SUM(销量.select(金额)), 'BOGUS($ghost)')",
                                   declared_params=["LIMIT"])
    assert [c["name"] for c in out["calls"]] == ["IF", "SUM", "销量.SELECT"]
    assert out["parameters"] == ["limit"]
    assert not out["unknown_functions"]
    assert not any(w["code"] == "undeclared_parameters" for w in out["warnings"])
    assert out["runtime_verified"] is False
    panel = formulas.analyze_formula("ds.select(#1)", context="widget")
    assert any(w["code"] == "unsupported_widget_dataset" for w in panel["warnings"])


def test_unknown_functions_are_advisory_including_template_write_plan():
    result = formulas.analyze_formula("=PluginFn(1)+SMU(2)")
    assert result["unknown_functions"] == ["PLUGINFN", "SMU"]
    text, changes = reportops.plan_cell(cptxml.empty_skeleton(), "A1", formula="=PluginFn(1)")
    assert cptxml.cells(text)[0]["formula"] == "=PluginFn(1)"
    assert any(c.get("code") == "unknown_function" for c in changes)


def test_parameter_formula_retypes_and_preserves_other_scopes():
    original = template()
    text, _ = reportops.plan_param(original, set_formula=["edate=" + EXPR])
    ET.fromstring(text)
    p = cptxml.template_parameters(text)[0]
    assert (p["default"], p["default_type"]) == (EXPR, "formula")
    assert '<O t="XMLable" class="com.fr.base.Formula">' in text
    for ds in cptxml.table_datas(text):
        assert ds["parameters"][0]["default"] == "20261001"
        assert ds["parameters"][0]["default_type"] == "value"
    again, changes = reportops.plan_param(text, set_formula=["edate=" + EXPR])
    assert again == text and changes[0]["how"] == "unchanged"
    literal, _ = reportops.plan_param(text, set_default=["edate=" + EXPR])
    p = cptxml.template_parameters(literal)[0]
    assert (p["default"], p["default_type"]) == (EXPR, "value")


def test_missing_default_element_is_added_and_legacy_formula_is_read():
    text = cptxml.empty_skeleton()
    text = cptxml.append_child(text, cptxml.parameter_attr_element(text),
        '<Parameters><Parameter><Attributes name="p"/></Parameter></Parameters>')
    assert cptxml.template_parameters(text)[0]["default"] == ""
    text, _ = cptxml.add_template_parameter(text, "p", formula="TODAY()")
    assert cptxml.template_parameters(text)[0]["default"] == "=TODAY()"
    legacy = text.replace('t="XMLable" class="com.fr.base.Formula"', 't="Formula" class="Formula"')
    assert cptxml.template_parameters(legacy)[0]["default_type"] == "formula"
    assert cptxml.add_template_parameter(legacy, "p", formula="TODAY()")[0] == legacy


def test_widget_formula_updates_template_and_control_without_touching_datasets():
    text = template()
    text, _ = reportops.plan_widget(text, "edate", kind="text", default_formula=EXPR)
    ET.fromstring(text)
    for item in (cptxml.template_parameters(text)[0], cptxml.panel_widgets(text)[0]):
        assert (item["default"], item["default_type"]) == (EXPR, "formula")
    assert cptxml.table_datas(text)[0]["parameters"][0]["default"] == "20261001"
    again, _ = reportops.plan_widget(text, "edate", kind="text", default_formula=EXPR)
    assert text == again
    changed, _ = reportops.plan_widget(text, "edate", kind="text", default="literal")
    assert cptxml.template_parameters(changed)[0]["default_type"] == "value"
    assert cptxml.panel_widgets(changed)[0]["default_type"] == "value"


def test_no_declare_keeps_template_parameter_as_is():
    text, _ = reportops.plan_widget(template(), "edate", kind="text", default_formula=EXPR,
                                    declare=False)
    assert cptxml.template_parameters(text)[0]["default"] == "20261001"
    assert cptxml.panel_widgets(text)[0]["default"] == EXPR


def test_dataset_formula_scope_and_offsets_after_sql_and_connection_edit():
    source = template()
    text, _ = reportops.plan_edit(source, dataset="ds", sql="select 12345 as d",
                                  connection="demo_conn_new", param="edate", default_formula=EXPR)
    ET.fromstring(text)
    ds, other = cptxml.table_datas(text)
    assert ds["connection"] == "demo_conn_new" and ds["sql"] == "select 12345 as d"
    assert (ds["parameters"][0]["default"], ds["parameters"][0]["default_type"]) == (EXPR, "formula")
    assert other["parameters"][0]["default"] == "20261001"
    assert cptxml.template_parameters(text)[0]["default"] == "20261001"
    again, _ = reportops.plan_edit(text, dataset="ds", param="edate", default_formula=EXPR)
    assert again == text


@pytest.mark.parametrize("command", [
    ["report", "functions", "rank"], ["report", "functions", "--keyword", "日期"],
    ["report", "functions", "--category", "hierarchy"],
    ["report", "formula-check", "=IF(1=1,'a)b',PluginFn(2))"],
])
def test_offline_commands_never_load_config(monkeypatch, command):
    import frcli.commands.report as report

    def no_config(*args, **kwargs):
        pytest.fail("函数检查不应加载实例配置")

    monkeypatch.setattr(report, "load_config", no_config)
    result = CliRunner().invoke(main, command)
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["runtime_verified"] is False


@pytest.mark.parametrize("command", [
    ["report", "functions", "DOES_NOT_EXIST"],
    ["report", "functions", "--category", "bad"],
    ["report", "formula-check", "SUM([1,2)"],
])
def test_offline_command_errors_are_nonzero(command):
    result = CliRunner().invoke(main, command)
    assert result.exit_code != 0
    assert json.loads(result.output)["status"] == "error"


@pytest.mark.parametrize("planner,kwargs", [
    (reportops.plan_param, {"set_formula": ["x=TODAY()"], "set_default": ["x=text"]}),
    (reportops.plan_widget, {"param": "x", "default_formula": EXPR, "default": ""}),
    (reportops.plan_edit, {"dataset": "ds", "param": "edate", "default": "", "default_formula": EXPR}),
])
def test_static_and_formula_defaults_are_mutually_exclusive(planner, kwargs):
    with pytest.raises(ApiError, match="只能给一个|不能同时设置"):
        planner(template(), **kwargs)


@pytest.mark.parametrize("args", [
    ["param", "--set-formula", "edate=TODAY()"],
    ["widget", "--param", "edate", "--default-formula", "TODAY()"],
    ["edit", "--dataset", "ds", "--param", "edate", "--default-formula", "TODAY()"],
])
def test_new_write_options_keep_zero_request_scope_guard(args):
    result = CliRunner().invoke(main, ["report", args[0], TARGET, *args[1:], "--apply"])
    assert result.exit_code != 0
    assert "未指定范围" in result.output


def test_same_dataset_formula_with_apply_does_not_upload(monkeypatch):
    text, _ = reportops.plan_edit(template(), dataset="ds", param="edate", default_formula=EXPR)
    monkeypatch.setattr(reportops, "read_template", lambda *args: text.encode())

    def fail_upload(*args, **kwargs):
        pytest.fail("相同公式不能发写请求")

    monkeypatch.setattr(reportops, "upload_template", fail_upload)
    result = reportops.edit_template(None, TARGET, apply=True, dataset="ds", param="edate",
                                     default_formula=EXPR)
    assert result["changed"] is False and result["applied"] is False


@pytest.mark.parametrize("args,scope", [
    (["param", "--set-formula", "edate=" + EXPR], "template"),
    (["widget", "--param", "edate", "--type", "text", "--default-formula", EXPR], "widget"),
    (["edit", "--dataset", "ds", "--param", "edate", "--default-formula", EXPR], "dataset"),
])
def test_new_options_reach_planner_in_dry_run(monkeypatch, args, scope):
    source = template()
    monkeypatch.setattr(reportops, "read_template", lambda *a: source.encode())
    result = CliRunner().invoke(main, ["report", args[0], TARGET, *args[1:]])
    assert result.exit_code == 0, result.output
    out = json.loads(result.stdout)
    assert out["status"] == "ok" and out["applied"] is False
    assert out["changed"] is True
    assert ("param.formula" if scope == "template" else
            "widget.set" if scope == "widget" else "dataset.parameter") in {
                c["kind"] for c in out["changes"]}
