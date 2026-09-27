"""图表（VanChart）单元格的最小 XML 模板（从官方语料裁剪 + 真机渲染验证）。

出处：官方模板 `demo/chart/basic/折线图.cpt`（折线）、
`doc/Advanced/Chart/ColumnChart/圆角属性和柱子宽度自定义柱形图.cpt`（柱形）、
`demo/chart/basic/饼图.cpt` / `环形图.cpt`（饼/环）。
裁剪规则：删掉图例/坐标轴/数据表/缩放/条件属性/提示框样式等可选子树（共 11 个标签），
只留 `Chart`/`GI`/`ChartAttr`/`Plot`/`ChartDefinition` —— 实测 1.6~1.9KB 就能正常出图。
**`__CHARTDEF__` / `__TITLE__` 由 `chart_cell_xml()` 填**。
"""

import re

from .exceptions import ApiError


#: 图表类型 → (XML 模板, 官方样例里的 cs/rs)
CHART_TEMPLATES = {
    "column": {"cs": 9, "rs": 20, "xml": (
        "<O t=\"CC\">\n"
        "<LayoutAttr selectedIndex=\"0\"/>\n"
        "<Chart name=\"默认\" chartClass=\"com.fr.plugin.chart.vanchart.VanChart\">\n"
        "<Chart class=\"com.fr.plugin.chart.vanchart.VanChart\">\n"
        "<GI>\n"
        "<AttrBackground>\n"
        "<Background name=\"NullBackground\"/>\n"
        "<Attr shadow=\"false\"/>\n"
        "</AttrBackground>\n"
        "<AttrBorder>\n"
        "<Attr lineStyle=\"0\" isRoundBorder=\"false\" roundRadius=\"0\"/>\n"
        "<newColor borderColor=\"-1118482\"/>\n"
        "</AttrBorder>\n"
        "<AttrAlpha>\n"
        "<Attr alpha=\"1.0\"/>\n"
        "</AttrAlpha>\n"
        "</GI>\n"
        "<ChartAttr isJSDraw=\"true\" isStyleGlobal=\"false\"/>\n"
        "__TITLE__\n"
        "<Plot class=\"com.fr.plugin.chart.column.VanChartColumnPlot\">\n"
        "<GI>\n"
        "<AttrBackground>\n"
        "<Background name=\"NullBackground\"/>\n"
        "<Attr shadow=\"false\"/>\n"
        "</AttrBackground>\n"
        "<AttrBorder>\n"
        "<Attr lineStyle=\"0\" isRoundBorder=\"false\" roundRadius=\"0\"/>\n"
        "<newColor/>\n"
        "</AttrBorder>\n"
        "<AttrAlpha>\n"
        "<Attr alpha=\"1.0\"/>\n"
        "</AttrAlpha>\n"
        "</GI>\n"
        "<Attr isNullValueBreak=\"true\" autoRefreshPerSecond=\"0\" seriesDragEnable=\"false\" plotStyle=\"4\" combinedSize=\"50.0\"/>\n"  # noqa: E501
        "<VanChartPlotAttr isAxisRotation=\"false\"/>\n"
        "<VanChartColumnPlotAttr seriesOverlapPercent=\"20.0\" categoryIntervalPercent=\"20.0\" fixedWidth=\"true\" columnWidth=\"20\" filledWithImage=\"false\" isBar=\"false\"/>\n"  # noqa: E501
        "</Plot>\n"
        "<DataProcessor class=\"com.fr.base.chart.chartdata.model.NormalDataModel\"/>\n"
        "__CHARTDEF__\n"
        "</Chart>\n"
        "<refreshMoreLabel>\n"
        "<TextAttr>\n"
        "<Attr alignText=\"0\">\n"
        "<FRFont name=\"Microsoft YaHei\" style=\"0\" size=\"72\"/>\n"
        "</Attr>\n"
        "</TextAttr>\n"
        "<attr moreLabel=\"true\" plusColor=\"-11349576\" minusColor=\"-741051\"/>\n"
        "</refreshMoreLabel>\n"
        "</Chart>\n"
        "</O>\n"
        "<PrivilegeControl/>\n"
        "<Expand/>\n"
    )},
    "line": {"cs": 9, "rs": 19, "xml": (
        "<O t=\"CC\">\n"
        "<LayoutAttr selectedIndex=\"0\"/>\n"
        "<Chart name=\"默认\" chartClass=\"com.fr.plugin.chart.vanchart.VanChart\">\n"
        "<Chart class=\"com.fr.plugin.chart.vanchart.VanChart\" wrapperName=\"VanChartWrapper\" requiredJS=\"/com/fr/web/core/js/d3.js,/com/fr/web/core/js/vancharts-all.js,/com/fr/web/core/js/VanChartWrapper.js,\" chartImagePath=\"\">\n"  # noqa: E501
        "<GI>\n"
        "<AttrBackground>\n"
        "<Background name=\"NullBackground\"/>\n"
        "<Attr shadow=\"false\"/>\n"
        "</AttrBackground>\n"
        "<AttrBorder>\n"
        "<Attr lineStyle=\"0\" isRoundBorder=\"false\" roundRadius=\"0\"/>\n"
        "<newColor borderColor=\"-1118482\"/>\n"
        "</AttrBorder>\n"
        "<AttrAlpha>\n"
        "<Attr alpha=\"1.0\"/>\n"
        "</AttrAlpha>\n"
        "</GI>\n"
        "<ChartAttr isJSDraw=\"true\" isStyleGlobal=\"false\"/>\n"
        "__TITLE__\n"
        "<Plot class=\"com.fr.plugin.chart.line.VanChartLinePlot\">\n"
        "<GI>\n"
        "<AttrBackground>\n"
        "<Background name=\"NullBackground\"/>\n"
        "<Attr shadow=\"false\"/>\n"
        "</AttrBackground>\n"
        "<AttrBorder>\n"
        "<Attr lineStyle=\"0\" isRoundBorder=\"false\" roundRadius=\"0\"/>\n"
        "<newColor/>\n"
        "</AttrBorder>\n"
        "<AttrAlpha>\n"
        "<Attr alpha=\"1.0\"/>\n"
        "</AttrAlpha>\n"
        "</GI>\n"
        "<Attr isNullValueBreak=\"true\" autoRefreshPerSecond=\"0\" seriesDragEnable=\"false\" plotStyle=\"4\" combinedSize=\"50.0\"/>\n"  # noqa: E501
        "</Plot>\n"
        "__CHARTDEF__\n"
        "</Chart>\n"
        "</Chart>\n"
        "</O>\n"
        "<PrivilegeControl/>\n"
        "<Expand/>\n"
    )},
    "pie": {"cs": 7, "rs": 17, "xml": (
        "<O t=\"CC\">\n"
        "<LayoutAttr selectedIndex=\"0\"/>\n"
        "<Chart name=\"默认\" chartClass=\"com.fr.plugin.chart.vanchart.VanChart\">\n"
        "<Chart class=\"com.fr.plugin.chart.vanchart.VanChart\" wrapperName=\"RosePieChart\" requiredJS=\"/com/fr/web/core/js/d3.js,/com/fr/web/core/js/vancharts-all.js,/com/fr/web/core/js/RosePieChart.js,\" chartImagePath=\"\">\n"  # noqa: E501
        "<GI>\n"
        "<AttrBackground>\n"
        "<Background name=\"NullBackground\"/>\n"
        "<Attr shadow=\"false\"/>\n"
        "</AttrBackground>\n"
        "<AttrBorder>\n"
        "<Attr lineStyle=\"0\" isRoundBorder=\"false\" roundRadius=\"0\"/>\n"
        "<newColor borderColor=\"-1118482\"/>\n"
        "</AttrBorder>\n"
        "<AttrAlpha>\n"
        "<Attr alpha=\"1.0\"/>\n"
        "</AttrAlpha>\n"
        "</GI>\n"
        "<ChartAttr isJSDraw=\"true\" isStyleGlobal=\"false\"/>\n"
        "__TITLE__\n"
        "<Plot class=\"com.fr.plugin.chart.PiePlot4VanChart\">\n"
        "<GI>\n"
        "<AttrBackground>\n"
        "<Background name=\"NullBackground\"/>\n"
        "<Attr shadow=\"false\"/>\n"
        "</AttrBackground>\n"
        "<AttrBorder>\n"
        "<Attr lineStyle=\"0\" isRoundBorder=\"false\" roundRadius=\"0\"/>\n"
        "<newColor borderColor=\"-1118482\"/>\n"
        "</AttrBorder>\n"
        "<AttrAlpha>\n"
        "<Attr alpha=\"1.0\"/>\n"
        "</AttrAlpha>\n"
        "</GI>\n"
        "<Attr isNullValueBreak=\"true\" autoRefreshPerSecond=\"0\" seriesDragEnable=\"false\" plotStyle=\"4\" combinedSize=\"50.0\"/>\n"  # noqa: E501
        "<VanChartPlotAttr monitorRefresh=\"false\"/>\n"
        "<PieAttr4VanChart roseType=\"normal\" startAngle=\"0.0\" endAngle=\"360.0\" innerRadius=\"0.0\" supportRotation=\"false\">\n"  # noqa: E501
        "<AttrBorder>\n"
        "<Attr lineStyle=\"1\" isRoundBorder=\"false\" roundRadius=\"0\"/>\n"
        "<newColor borderColor=\"-1\"/>\n"
        "</AttrBorder>\n"
        "</PieAttr4VanChart>\n"
        "</Plot>\n"
        "__CHARTDEF__\n"
        "</Chart>\n"
        "</Chart>\n"
        "</O>\n"
        "<PrivilegeControl/>\n"
        "<Expand/>\n"
    )},
    "ring": {"cs": 7, "rs": 17, "xml": (
        "<O t=\"CC\">\n"
        "<LayoutAttr selectedIndex=\"0\"/>\n"
        "<Chart name=\"默认\" chartClass=\"com.fr.plugin.chart.vanchart.VanChart\">\n"
        "<Chart class=\"com.fr.plugin.chart.vanchart.VanChart\" wrapperName=\"RosePieChart\" requiredJS=\"/com/fr/web/core/js/d3.js,/com/fr/web/core/js/vancharts-all.js,/com/fr/web/core/js/RosePieChart.js,\" chartImagePath=\"\">\n"  # noqa: E501
        "<GI>\n"
        "<AttrBackground>\n"
        "<Background name=\"NullBackground\"/>\n"
        "<Attr shadow=\"false\"/>\n"
        "</AttrBackground>\n"
        "<AttrBorder>\n"
        "<Attr lineStyle=\"0\" isRoundBorder=\"false\" roundRadius=\"0\"/>\n"
        "<newColor borderColor=\"-1118482\"/>\n"
        "</AttrBorder>\n"
        "<AttrAlpha>\n"
        "<Attr alpha=\"1.0\"/>\n"
        "</AttrAlpha>\n"
        "</GI>\n"
        "<ChartAttr isJSDraw=\"true\" isStyleGlobal=\"false\"/>\n"
        "__TITLE__\n"
        "<Plot class=\"com.fr.plugin.chart.PiePlot4VanChart\">\n"
        "<GI>\n"
        "<AttrBackground>\n"
        "<Background name=\"NullBackground\"/>\n"
        "<Attr shadow=\"false\"/>\n"
        "</AttrBackground>\n"
        "<AttrBorder>\n"
        "<Attr lineStyle=\"0\" isRoundBorder=\"false\" roundRadius=\"0\"/>\n"
        "<newColor borderColor=\"-1118482\"/>\n"
        "</AttrBorder>\n"
        "<AttrAlpha>\n"
        "<Attr alpha=\"1.0\"/>\n"
        "</AttrAlpha>\n"
        "</GI>\n"
        "<Attr isNullValueBreak=\"true\" autoRefreshPerSecond=\"0\" seriesDragEnable=\"false\" plotStyle=\"4\" combinedSize=\"50.0\"/>\n"  # noqa: E501
        "<PieAttr4VanChart roseType=\"normal\" startAngle=\"0.0\" endAngle=\"360.0\" innerRadius=\"65.0\" supportRotation=\"false\">\n"  # noqa: E501
        "<AttrBorder>\n"
        "<Attr lineStyle=\"1\" isRoundBorder=\"false\" roundRadius=\"0\"/>\n"
        "<newColor borderColor=\"-1\"/>\n"
        "</AttrBorder>\n"
        "</PieAttr4VanChart>\n"
        "</Plot>\n"
        "__CHARTDEF__\n"
        "</Chart>\n"
        "</Chart>\n"
        "</O>\n"
        "<PrivilegeControl/>\n"
        "<Expand/>\n"
    )},
}


#: 图表类型别名 → 模板键
CHART_TYPES = {
    "column": "column", "bar": "column", "柱形图": "column", "柱状图": "column",
    "line": "line", "折线图": "line",
    "pie": "pie", "饼图": "pie",
    "ring": "ring", "环形图": "ring", "donut": "ring",
}

#: 聚合函数（`OneValueCDDefinition@function`）—— 与 `<RG>` 的 `<FN>` 同一套类
CHART_FUNCTIONS = {
    "sum": "SumFunction", "count": "CountFunction", "avg": "AverageFunction",
    "max": "MaxFunction", "min": "MinFunction", "none": "NoneFunction",
}
FUNCTION_PKG = "com.fr.data.util.function"

#: `<TitleVisible>` 缺省值与写法（`Title4VanChart > Title`）
_TITLE_XML = """<Title4VanChart>
<Title>
<GI>
<AttrBackground>
<Background name="NullBackground"/>
<Attr shadow="false"/>
</AttrBackground>
<AttrBorder>
<Attr lineStyle="0" isRoundBorder="false" roundRadius="0"/>
<newColor borderColor="-6908266"/>
</AttrBorder>
<AttrAlpha>
<Attr alpha="1.0"/>
</AttrAlpha>
</GI>
<O>
<![CDATA[%s]]></O>
<TextAttr>
<Attr alignText="0">
<FRFont name="微软雅黑" style="1" size="128" foreground="-13421773"/>
</Attr>
</TextAttr>
<TitleVisible value="%s" position="0"/>
</Title>
<Attr4VanChart useHtml="false" floating="false" x="0.0" y="0.0" limitSize="false" maxHeight="15.0"/>
</Title4VanChart>"""


def check_chart_type(kind: str) -> str:
    key = CHART_TYPES.get(str(kind or "").strip().lower())
    if key is None:
        raise ApiError(f"--type 只能是 {' / '.join(sorted(set(CHART_TYPES)))}，收到 {kind!r}")
    return key


def check_chart_fn(fn: str) -> str:
    raw = str(fn or "sum").strip().lower()
    base = CHART_FUNCTIONS.get(raw)
    if base is None:
        base = raw.rsplit(".", 1)[-1]
        if base not in CHART_FUNCTIONS.values():
            raise ApiError(f"--fn 只能是 {' / '.join(CHART_FUNCTIONS)}，收到 {fn!r}")
    return base


def chart_definition_xml(dataset: str, category: str, series: str = None,
                         value: str = None, fn: str = "sum", kind_key: str = "column") -> str:
    """`<ChartDefinition>`：图表的数据源绑定。

    单系列（饼图/环形图）用 `OneValueCDDefinition`：`seriesName` = 扇区列、
    `CategoryName` = 分类列、`valueName` = 值列、`function` = 聚合函数。
    多系列（柱形/折线）用 `SeriesCDDefinition`：`seriesName` = 系列列（图例）。
    """
    if not category:
        raise ApiError("图表必须给 --category（分类轴列）")
    if not value:
        raise ApiError("图表必须给 --value（数值列）")
    fn_cls = check_chart_fn(fn)
    if series:
        # 多系列：seriesName = 系列列（图例）、CategoryName = 分类轴列
        series_name, cat_name = series, category
    elif kind_key in ("pie", "ring"):
        # 单张饼：官方样例就是 seriesName = 扇区列 + CategoryName **空**
        series_name, cat_name = category, ""
    else:
        # 单系列柱/折：seriesName **留空**、CategoryName = 分类轴列（实测能得到正常的单系列图；
        # 若把 seriesName 也写成分类列，会变成"每个分类自成一个系列"、图例是分类名、X 轴重复）
        series_name, cat_name = "", category
    tag = "OneValueCDDefinition"
    head = (f'<{tag} seriesName="{series_name}" valueName="{value}" '
            f'function="{FUNCTION_PKG}.{fn_cls}">')
    cat_el = ('<CategoryName value=""/>' if not cat_name
              else f'<CategoryName value="{cat_name}"/>')
    return "\n".join([
        "<ChartDefinition>", head,
        '<Top topCate="-1" topValue="-1" isDiscardOtherCate="false" '
        'isDiscardOtherSeries="false" isDiscardNullCate="false" isDiscardNullSeries="false"/>',
        '<TableData class="com.fr.data.impl.NameTableData">',
        "<Name>", f"<![CDATA[{dataset}]]></Name>", "</TableData>",
        cat_el,
        f"</{tag}>", "</ChartDefinition>"])


def chart_cell_xml(kind: str, dataset: str, category: str, series: str = None,
                   value: str = None, fn: str = "sum", title: str = None,
                   c: int = 0, r: int = 0, cs: int = None, rs: int = None,
                   sheet_style=None) -> str:
    """一个完整的图表单元格 `<C>`（图表是 `CellElementList` 里的一个格子）。

    * `title=None`（缺省）⇒ 写 `TitleVisible=false` 的标题块 —— **不写标题块服务端会给
      默认标题「新建图表标题」**（实测：裁剪后没写 Title4VanChart，图上仍出现这行字）。
    * `cs`/`rs` 决定图表占几列几行（官方样例 9×19 ~ 9×20）。
    """
    key = check_chart_type(kind)
    tpl = CHART_TEMPLATES[key]
    body = tpl["xml"]
    body = body.replace("__CHARTDEF__", chart_definition_xml(
        dataset, category, series, value, fn, key))
    shown = "true" if title else "false"
    body = body.replace("__TITLE__", _TITLE_XML % (title or "", shown))
    attrs = f'c="{c}" r="{r}"'
    cs = tpl["cs"] if cs is None else cs
    rs = tpl["rs"] if rs is None else rs
    if cs and int(cs) > 1:
        attrs += f' cs="{int(cs)}"'
    if rs and int(rs) > 1:
        attrs += f' rs="{int(rs)}"'
    if sheet_style is not None:
        attrs += f' s="{sheet_style}"'
    return f"<C {attrs}>\n{body}</C>"


def detect_type(raw: str) -> str:
    """从一段 `<C>` 原文里认出图表类型（给 `report chart --list` 用）。"""
    if "VanChartColumnPlot" in raw:
        return "column"
    if "VanChartLinePlot" in raw:
        return "line"
    if "PiePlot4VanChart" in raw:
        return "ring" if "Doughnut" in raw or "环形" in raw else "pie"
    return "unknown"


def parse_definition(raw: str) -> dict:
    """读 `<ChartDefinition>`：数据集 / 系列列 / 分类列 / 值列 / 聚合函数。"""
    m = re.search(r"<ChartDefinition>(.*?)</ChartDefinition>", raw, re.S)
    if not m:
        return {}
    seg = m.group(1)
    head = re.search(r"<(OneValueCDDefinition|SeriesCDDefinition|MoreNameCDDefinition)"
                     r'([^>]*)>', seg)
    attrs = head.group(2) if head else ""
    ds = re.search(r"<Name>\s*<!\[CDATA\[([^\]]*)\]\]>", seg)
    cat = re.search(r'<CategoryName value="([^"]*)"', seg)
    return {
        "class": head.group(1) if head else None,
        "series": (re.search(r'seriesName="([^"]*)"', attrs) or [None, None])[1],
        "value": (re.search(r'valueName="([^"]*)"', attrs) or [None, None])[1],
        "function": ((re.search(r'function="([^"]*)"', attrs) or [None, None])[1] or "").rsplit(".", 1)[-1],  # noqa: E501
        "dataset": ds.group(1).strip() if ds else None,
        "category": cat.group(1) if cat else None,
    }
