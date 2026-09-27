"""`references/cpt-patterns.md` 配方集的离线回归测试（不联网）。

本文件由**独立复现者**根据真机逐格验收结果补写，钉住配方集里"能被离线判定"的契约，
并把复现过程中发现的三个坑做成回归：

1. **§0 规则 2 / §5 坐标**：`report table --at A<n> --header` 之后数据行是 `A<n+1>`。
   §5 配方把带 `--ds-filter` 的过滤列挂在 C3（表头行），真机导出的该列与表数据**错开一行**
   （表头被合并 A3:A4、数据行落到 5/6），挂 C4 才对 —— 这条坐标契约在此钉住。
2. **§1 组内小计**：小计靠 `--expand-left` 的显式左父格 + `SummaryGrouper/SumFunction`；
   父格展开几次小计出现几次（父格是"分组"还是"列表"决定每组一行还是每行一行）。
3. **§2 交叉表**：值格必须与列维度**同列**；总计行走 `=SUM(<值格>)` 公式；角标文本由 CLI
   原样写入（含反斜杠不做转义处理 —— 但服务端渲染会吃掉单个反斜杠，见验证报告）。

真机证据（xlsx/csv 双通道逐格）见 `docs/验证/cpt配方复现报告.md`；本文件不联网。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from frcli import cptxml, reportops                          # noqa: E402

FUNC = cptxml.FUNCTION_GROUPER
SUMMARY = cptxml.SUMMARY_GROUPER

DATASET = ("<TableDataMap><TableData name=\"ds1\" class=\"com.fr.data.impl.DBTableData\">"
           "<Parameters/><Attributes share=\"true\" maxMemRowCount=\"-1\"/>"
           "<Connection class=\"com.fr.data.impl.NameDatabaseConnection\"><DatabaseName>"
           "<![CDATA[demo_conn]]></DatabaseName></Connection>"
           "<Query><![CDATA[select 'SC04' center,'张三' sales,100 amt]]></Query>"
           "<PageQuery><![CDATA[]]></PageQuery></TableData></TableDataMap>")


def make_template():
    return cptxml.empty_skeleton().replace("<TableDataMap/>", DATASET)


def cells(text):
    return {c["a1"]: c for c in cptxml.cells(text)}


# ---------------------------------------------------------------------------
# 1. §0 规则 2 / §5 坐标：表头行 vs 数据行
# ---------------------------------------------------------------------------
def test_header_mode_data_row_is_one_below_header():
    """`--at A3 --header` ⇒ 表头在 A3，数据行在 A4（配方集 §0 规则 2）。"""
    text, _ = reportops.plan_table(make_template(), dataset="ds1", at="A3",
                                   columns=["center", "amt"], header=True)
    c = cells(text)
    assert c["A3"]["text"] == "center" and c["B3"]["text"] == "amt"
    assert c["A3"]["binding"] is None and c["B3"]["binding"] is None
    assert c["A4"]["binding"] == "ds1.center" and c["B4"]["binding"] == "ds1.amt"
    assert "A4" not in (c["A3"].get("binding"),)


def test_filter_column_must_sit_on_data_row_not_header_row():
    """§5 的过滤列要挂数据行：挂 C4 与表同排；挂 C3（表头行）会另起一条扩展区。"""
    text, _ = reportops.plan_table(make_template(), dataset="ds1", at="A3",
                                   columns=["center", "amt"], header=True)
    good, _ = reportops.plan_cell(text, "C4", binding="ds1.amt", ds_mode="list",
                                  expand="v", ds_filter="$$$ >= $min_amt")
    bad, _ = reportops.plan_cell(text, "C3", binding="ds1.amt", ds_mode="list",
                                 expand="v", ds_filter="$$$ >= $min_amt")
    # 正确写法：C4 与 A4/B4 同一行（同一扩展行）
    assert cells(good)["C4"]["expand"] == "v"
    assert cells(good)["A4"]["expand"] == "v"
    # 错误写法：C3 与表头同格（A3 是静态文本，无扩展方向），两条扩展区不在同一行
    assert cells(bad)["C3"]["ds_filter"]["kind"] == "formula"
    assert cells(bad)["A3"]["expand"] == "none"


# ---------------------------------------------------------------------------
# 2. §1 分组维度 + 组内小计
# ---------------------------------------------------------------------------
def test_table_mode_group_vs_list_grouper():
    """§1：维度列必须「分组」模式；`report table` 默认是 list（显式 --mode group 才分组）。"""
    grouped, _ = reportops.plan_table(make_template(), dataset="ds1", at="A2",
                                      columns=["center", "amt"], header=True, mode="group")
    assert cells(grouped)["A3"]["ds_mode"] == "group"
    listed, _ = reportops.plan_table(make_template(), dataset="ds1", at="A2",
                                     columns=["center", "amt"], header=True)
    assert cells(listed)["A3"]["ds_mode"] == "list"
    assert FUNC in cptxml.rg_xml("group", None)
    assert 'divideMode="1"' in cptxml.rg_xml("list", None)


def test_subtotal_cell_hangs_on_explicit_left_parent():
    """§1：小计行靠 `<Expand leftParentDefault="false" left="A3"/>` 挂到分组上。"""
    text, _ = reportops.plan_table(make_template(), dataset="ds1", at="A2",
                                   columns=["center", "amt"], header=True, mode="group")
    text, _ = reportops.plan_cell(text, "A4", value="小计", expand_left="A3")
    text, _ = reportops.plan_cell(text, "C4", binding="ds1.amt", ds_mode="summary",
                                  ds_fn="sum", expand="none", expand_left="A3")
    assert '<Expand leftParentDefault="false" left="A3"/>' in text
    summary_cell = cptxml.find_cell(text, "C4")
    assert summary_cell["ds_mode"] == "summary"
    assert summary_cell["ds_fn"] == "SumFunction"
    assert SUMMARY in text and "SumFunction" in text


def test_grand_total_formula_stays_on_detail_first_row():
    """§1：总计行公式按第一条明细的行号写（区间由服务端自动伸展）。"""
    text, _ = reportops.plan_table(make_template(), dataset="ds1", at="A2",
                                   columns=["center", "amt"], header=True, mode="group")
    text, _ = reportops.plan_cell(text, "B5", formula="=SUM(B3)")
    assert cptxml.find_cell(text, "B5")["formula"] == "=SUM(B3)"
    assert cptxml.find_cell(text, "B3")["binding"] == "ds1.amt"


# ---------------------------------------------------------------------------
# 3. §2 交叉表：值格同列 / 总计公式 / 角标原样
# ---------------------------------------------------------------------------
def test_crosstab_value_cell_shares_column_with_col_dimension():
    """§2 坑 1：值格必须与列维度同列（表头行的列维度格 `+h`，数据行同列才是值格）。"""
    text, _ = reportops.plan_crosstab(make_template(), dataset="ds1", at="A3",
                                      rows=["dist", "sales"], cols=["prod"],
                                      values=["amt"], total_row=True, total_col=True)
    c = cells(text)
    col_dim = [a for a, v in c.items() if v.get("expand") == "h"]
    assert col_dim == ["C3"]
    # 值格与列维度同列（C），行维度各占 A/B
    assert c["C4"]["binding"] == "ds1.amt" and c["C4"]["expand"] == "none"
    assert c["A4"]["binding"] == "ds1.dist" and c["A4"]["expand"] == "v"
    assert c["B4"]["binding"] == "ds1.sales" and c["B4"]["expand"] == "v"
    # 行汇总列在列维度右边一列，走 SummaryGrouper
    assert c["D4"]["ds_mode"] == "summary" and c["D4"]["ds_fn"] == "SumFunction"
    # 总计行是公式（官方写法 =SUM(值格)）
    assert c["C5"]["formula"] == "=SUM(C4)" and c["D5"]["formula"] == "=SUM(D4)"
    assert c["A5"]["text"] == "总计："


def test_crosstab_agg_sum_switches_value_cell_to_summary_grouper():
    """§2 坑 2：`--agg sum` 把值格从分组换成汇总（真机副作用：缺失组合变 0）。"""
    text, _ = reportops.plan_crosstab(make_template(), dataset="ds1", at="A3",
                                      rows=["dist"], cols=["prod"], values=["amt"],
                                      agg="sum")
    assert cells(text)["B4"]["ds_mode"] == "summary"
    assert cells(text)["B4"]["ds_fn"] == "SumFunction"


def test_crosstab_corner_label_kept_verbatim_by_cli():
    """§2 角标：CLI 原样写入（反斜杠不转义）—— 服务端渲染才吃反斜杠，见验证报告。"""
    label = "地区\\销售员/产品"
    text, _ = reportops.plan_crosstab(make_template(), dataset="ds1", at="A3",
                                      rows=["dist"], cols=["prod"], values=["amt"],
                                      labels=[label])
    assert cptxml.find_cell(text, "A3")["text"] == label


def test_set_value_keeps_backslash_verbatim():
    """`report cell --set-value` 不做转义处理（服务端才把 `\\` 当转义，实测整格变空）。"""
    text, _ = reportops.plan_cell(make_template(), "E1", value="C:\\data\\file")
    assert cptxml.find_cell(text, "E1")["text"] == "C:\\data\\file"
    text2, _ = reportops.plan_cell(text, "E2", value="a\\b")
    assert cptxml.find_cell(text2, "E2")["text"] == "a\\b"


# ---------------------------------------------------------------------------
# 4. §3 条件属性：规则顺序 = 优先级
# ---------------------------------------------------------------------------
def test_highlight_rule_order_is_priority_order():
    """§3 坑 2：写在后面的规则优先级更高（宽规则要放第一条）。"""
    text, _ = reportops.plan_cell(make_template(), "C3", binding="ds1.amt", expand="v")
    text, _ = reportops.plan_highlight(
        text, "C3",
        rules=["ROW()%2=0:bg=#F2F2F2",
               "v<100:bg=#C6EFCE,fg=#006100",
               "v>300:bg=#FFC7CE,fg=#9C0006,bold"])
    cell = cptxml.find_cell(text, "C3")
    assert cell["hl_count"] == 3
    specs = [cptxml.condition_spec(h["condition"]) for h in cell["highlights"]]
    assert specs == ["formula:ROW()%2=0", "v<100", "v>300"]
    acts = [cptxml.highlight_action_spec(a) for a in cell["highlights"][2]["actions"]]
    # fg 必须并进字体动作（单独一条 Foreground 会被 FRFont 覆盖，实测踩过）
    assert "bg=#FFC7CE" in acts
    font_act = [a for a in acts if "fg=" in a]
    assert len(font_act) == 1 and "bold" in font_act[0] and "fg=#9C0006" in font_act[0]


def test_hide_row_action_is_empty_row_height():
    """§3 坑 4：`rowheight=0` 写成空的 `RowHeightHighlightAction`（`<RowHeight>` 只在 >0 时写）。"""
    act = cptxml.highlight_action_xml("rowheight=0")[0]
    assert "RowHeightHighlightAction" in act and "<RowHeight" not in act
