"""`references/cpt-patterns2.md`（第二辑）的离线回归测试（不联网）。

本文件由**独立复现者**在第二辑真机复验后补写，只钉"能被离线判定"的契约与坑，
与作者自带的 `tests/test_chart_link_widget.py`（XML 往返为主）互补，不重复其断言。

钉住三件事（都来自真机复现发现的文档问题，见 `docs/验证/cpt第二辑复现报告.md`）：

1. **W2 参数控件的 `--default` 会顺手补模板参数声明** —— 这正是文档"控件名 ≠ 参数名 ⇒ 不联动"
   那条对照实验跑出相反结果的原因：`--param AREA --default 华南` 会额外声明一个 `AREA` 参数，
   导出取到的是 `华南` 而不是模板原有的 `华东`（真机实测）。服务端参数名**大小写不敏感**
   （`--params '{"AREA":...}'` 能覆盖 `area`），所以两个只在大小写上不同的声明还会互相干扰。
2. **W1 图表的列名本地不校验**：`report chart` 本地只查「数据集是否存在」「目标格是否为空」，
   `--category/--series/--value` 原样写进 XML ⇒ 列名写错时服务端照样出图（错图）。
   将来若加了本地校验，此测试会失败并提醒同步文档。
3. **W5 `--repeat-header-rows 1:1` 与 `--at A2 --header` 是配套坐标**：表头行落在 0 基第 1 行，
   重复区间必须写 `1:1`；写错行号（表头在第 1 行却重复第 2 行）会让 600pt 的行参与重复，
   服务端报 `11300002 行高列宽超出页面大小`（真机实测，不是静默）。
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
           "<Query><![CDATA[select '东区' cat,'A' series,100 val]]></Query>"
           "<PageQuery><![CDATA[]]></PageQuery></TableData></TableDataMap>")


def make_template():
    return cptxml.empty_skeleton().replace("<TableDataMap/>", DATASET)


def param_names(text):
    return [p["name"] for p in cptxml.template_parameters(text)]


def with_data_cell():
    text, _ = reportops.plan_table(make_template(), dataset="ds1", at="A2",
                                   columns=["cat", "val"], header=True)
    return text


# ---------------------------------------------------------------------------
# 1. W2：控件 --default 自动补参数声明（大小写不同的重名声明是可能的）
# ---------------------------------------------------------------------------
def test_widget_default_auto_declares_param():
    """没有 `area` 参数时，`plan_widget(..., default=...)` 会自己补一条参数声明。"""
    text, _ = reportops.plan_widget(make_template(), "area", kind="combo",
                                    options=["华东", "华南"], default="华东")
    assert param_names(text) == ["area"]
    assert cptxml.panel_widgets(text)[0]["param"] == "area"


def test_widget_default_can_create_case_variant_duplicate():
    """模板已有 `area` 时再建 `AREA` 控件并给 `--default` ⇒ 两条声明并存（真机导出取新值）。"""
    text = with_data_cell()
    text, _ = reportops.plan_param(text, add=["area=华东"])          # 先声明 area=华东
    assert param_names(text) == ["area"], param_names(text)
    text, _ = reportops.plan_widget(text, "AREA", kind="combo",
                                    options=["华东", "华南"], default="华南")
    names = param_names(text)
    assert "area" in names and "AREA" in names, names
    assert cptxml.panel_widgets(text)[0]["param"] == "AREA"


def test_widget_declare_false_leaves_params_untouched():
    """`declare=False`（CLI 的 `--no-declare`）不动模板参数 —— 才是"控件名不匹配"的正确构造。"""
    text = with_data_cell()
    before = param_names(text)
    text2, _ = reportops.plan_widget(text, "AREA", kind="combo", options=["华东"],
                                     declare=False)
    assert param_names(text2) == before          # 没有多出 AREA
    assert cptxml.panel_widgets(text2)[0]["param"] == "AREA"


# ---------------------------------------------------------------------------
# 2. W1：图表列名本地不校验（静默错的前提）
# ---------------------------------------------------------------------------
def test_chart_does_not_validate_column_names_locally():
    """`--category NOSUCH` 本地不报错，列名原样进 XML ⇒ 服务端照画出错图。"""
    text, _ = reportops.plan_chart(with_data_cell(), at="A1", dataset="ds1", kind="column",
                                   category="NOSUCH", series="series", value="val")
    assert "NOSUCH" in text
    assert chartxml.parse_definition(text)["category"] == "NOSUCH"


def test_chart_validates_only_dataset_and_occupied_cell():
    """本地只拦这两样：数据集不存在、目标格已有内容。"""
    with pytest.raises(ApiError):
        reportops.plan_chart(with_data_cell(), at="A1", dataset="nosuchds", kind="column",
                             category="cat", value="val")
    occupied, _ = reportops.plan_cell(make_template(), "A1", value="占位")
    with pytest.raises(ApiError):
        reportops.plan_chart(occupied, at="A1", dataset="ds1", kind="column",
                             category="cat", value="val")


# ---------------------------------------------------------------------------
# 3. W5：重复标题行的区间必须对准表头所在的 0 基行号
# ---------------------------------------------------------------------------
def test_repeat_header_rows_must_match_header_row_index():
    """`--at A2 --header` ⇒ 表头在 0 基第 1 行；重复区间写 `1:1`。"""
    text = with_data_cell()
    cells = {c["a1"]: c for c in cptxml.cells(text)}
    assert cells["A2"]["text"] == "cat" and cells["A2"]["binding"] is None      # 表头
    assert cells["A3"]["binding"] == "ds1.cat"                                 # 数据
    header_row_index = 1                                                       # A2 → 0 基 1
    text2, _ = reportops.plan_page(text, repeat_header_rows=f"{header_row_index}:"
                                                             f"{header_row_index}")
    assert cptxml.page_regions(text2)["HR"] == (1, 1)
    text3, _ = reportops.plan_page(text, repeat_header_rows="none")
    assert cptxml.page_regions(text3)["HR"] is None
