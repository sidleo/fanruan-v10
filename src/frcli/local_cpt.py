"""只读检索、检查并从本地 CPT 示例提炼设计特征，不依赖实例或网络。"""

import os
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree

from . import cptxml
from .exceptions import ApiError


_CHART_TYPES = (
    ("column", ("columnchart", "columnplot", "柱形")),
    ("bar", ("barchart", "barplot", "条形")),
    ("line", ("linechart", "lineplot", "折线")),
    ("pie", ("piechart", "pieplot", "饼图")),
    ("area", ("areachart", "areaplot", "面积图")),
    ("scatter", ("scatter", "散点")),
    ("bubble", ("bubble", "气泡")),
    ("radar", ("radar", "雷达")),
    ("gauge", ("gauge", "仪表盘")),
    ("map", ("mapplot", "mapchart", "地图")),
    ("gantt", ("gantt", "甘特")),
    ("funnel", ("funnel", "漏斗")),
    ("heatmap", ("heatmap", "heatplot", "热力")),
    ("treemap", ("treemap", "treeplot", "树图")),
    ("word-cloud", ("wordcloud", "词云")),
    ("stock", ("stock", "股价")),
)
_CHART_LABELS = {
    "column": "柱形图", "bar": "条形图", "line": "折线图", "pie": "饼图",
    "area": "面积图", "scatter": "散点图", "bubble": "气泡图", "radar": "雷达图",
    "gauge": "仪表盘", "map": "地图", "gantt": "甘特图", "funnel": "漏斗图",
    "heatmap": "热力图", "treemap": "树图", "word-cloud": "词云", "stock": "股价图",
}

_LESSONS = {
    "form-entry": "表单把录入、校验和提交放在同一业务任务里；实现时保留必填、校验、暂存和提交反馈。",
    "dashboard-layout": "驾驶舱先组织扫描层级和关键指标，再放置图表与钻取；避免把明细表原样搬到一屏。",
    "multi-sheet": "多 sheet 通常承担分主题或主从页面；先明确每页的唯一职责，再复用到自己的业务问题。",
    "multi-block": "聚合报表每个 Block 有独立坐标和 A1；逐块比较，不要把块坐标合并成一张网格。",
    "floating-layout": "浮动元素不进入单元格网格；阅读和复用时同时检查 CellElementList 与 FloatElementList。",
    "split-columns": "分栏把长序列折叠成多列；核对每列复制哪些标题行以及最大行列数，避免打印错位。",
    "crosstab": "交叉表用横纵两个扩展方向表达二维比较；优先控制维度基数，并给合计、排名和空值明确规则。",
    "group-subtotals": "分组表先展示层级，再在正确的父组位置放小计；汇总格与小计格不能承担同一语义。",
    "detail-grid": "明细表适合逐行核对和导出；固定列顺序、数字格式与条件高亮，减少横向扫读成本。",
    "multi-dataset": "多数据集先对齐粒度、时间口径和连接键；页面上的组合不能掩盖底层口径差异。",
    "formula-calculations": "公式层表达派生指标和版面位置；把业务口径落到公式前，先确认输入格与扩展后的引用含义。",
    "conditional-formatting": "条件属性用于异常和阈值扫描；颜色必须对应业务含义，不能只做装饰。",
    "linked-report": "钻取要保留当前筛选上下文、目标报表参数和返回路径；只有视觉跳转没有参数传递会得到错误明细。",
    "chart-linkage": "图表联动同时绑定数据字段和事件参数；实现后要验证点击、过滤、空数据和返回状态。",
    "frozen-report-area": "冻结区解决长表定位；要按屏幕、打印与移动端分别确认冻结边界。",
    "frozen-control-panel": "固定查询控件减少滚动后重复操作；仍要验证小屏是否挤压内容区。",
    "absolute-layout": "绝对布局适合表单和看板，但响应式能力弱；明确目标屏幕和最小宽度后再使用。",
    "custom-javascript": "自定义 JavaScript 是交互增强而非版面结构；核对默认状态、幂等、异常恢复和移动端降级。",
    "number-formatting": "数量、金额、比例和日期分别使用稳定的格式；先统一单位，再决定小数位和千分位。",
    "color-coding": "有限且语义稳定的配色能降低查找成本；标题、强调、告警和背景色不要共用同一含义。",
    "chart": "图表先表达一个主问题，再决定类型；同时检查标题、轴、图例、标签、提示和空数据状态。",
}


def _candidate_cpts(root, keyword=None):
    """枚举安全的 CPT 候选文件，不跟随目录或文件符号链接。"""
    candidates, problems = [], []

    def onerror(exc):
        problems.append({"path": str(exc.filename or root), "error": str(exc)})

    for parent, dirs, files in os.walk(root, followlinks=False, onerror=onerror):
        dirs.sort()
        for name in list(dirs):
            candidate = Path(parent) / name
            if candidate.is_symlink():
                problems.append({"path": str(candidate.relative_to(root)),
                                 "error": "符号链接目录未跟随"})
                dirs.remove(name)
        for name in sorted(files):
            if not name.lower().endswith(".cpt"):
                continue
            candidate = Path(parent) / name
            if candidate.is_symlink():
                problems.append({"path": str(candidate.relative_to(root)),
                                 "error": "符号链接文件未跟随"})
                continue
            relative = str(candidate.relative_to(root))
            if keyword and keyword.casefold() not in relative.casefold():
                continue
            candidates.append((relative, candidate))
    return sorted(candidates), problems


def find_examples(directory, keyword=None, contains=None, limit=30):
    """按相对路径及可选 XML 原文筛选 CPT，返回总命中数和有界结果。"""
    root = Path(directory).expanduser().resolve()
    if not root.is_dir():
        raise ApiError(f"示例目录不存在或不是目录: {root}")
    candidates, problems = _candidate_cpts(root, keyword)
    matches = []
    for relative, candidate in candidates:
        if contains is not None:
            try:
                if contains not in candidate.read_text(encoding="utf-8-sig"):
                    continue
            except (OSError, UnicodeError) as exc:
                problems.append({"path": relative, "error": str(exc)})
                continue
        matches.append(relative)
    return {"root": str(root), "matched": len(matches), "returned": min(len(matches), limit),
            "truncated": len(matches) > limit, "files": matches[:limit],
            "skipped_count": len(problems), "skipped": problems[:20]}


def _cell_elements(text, container):
    if container is None:
        return []
    return cptxml._sub_elements(text, container, "C", path=())


def _describe_sheet(text, report):
    """普通报表按整页、聚合报表按独立 Block 计数；坐标不跨块合并。"""
    report_class = report.attrs.get("class", "")
    name = report.attrs.get("name", "")
    poly = report_class.rsplit(".", 1)[-1] == "PolyWorkSheet"
    layout = cptxml._first_direct(text, report, "WorkSheetAttr")
    floating = cptxml._first_direct(text, report, "FloatElementList")
    # 只数 FloatElementList 的直接子元素，避免把其后代误计为多个浮动元素。
    float_count = sum(1 for e in cptxml.scan(floating.content(text)) if not e.path) \
        if floating else 0
    result = {"name": name, "class": report_class, "poly": poly,
              "worksheet_attributes": layout.attrs if layout else None,
              "floating_elements": float_count}
    blocks = []
    if poly:
        for index, block in enumerate(cptxml._sub_elements(text, report, "Block", path=()), 1):
            attr = cptxml._first_direct(text, block, "PECBAttr")
            attrs = attr.attrs if attr else {}
            cell_list = cptxml._first_direct(text, block, "CellElementList")
            blocks.append({"index": index, "name": attrs.get("blockName"),
                           "class": block.attrs.get("class", ""),
                           "bounds": {k: attrs[k] for k in ("x", "y", "width", "height")
                                      if k in attrs},
                           "has_cell_list": cell_list is not None,
                           "cell_count": len(_cell_elements(text, cell_list)),
                           "_container": cell_list})
        result["blocks"] = [{k: v for k, v in b.items() if k != "_container"} for b in blocks]
    else:
        container = cptxml._first_direct(text, report, "CellElementList")
        result["has_cell_list"] = container is not None
        blocks.append({"index": None, "name": None, "_container": container,
                       "cell_count": len(_cell_elements(text, container))})
        result["blocks"] = []
    result["cell_count"] = sum(b["cell_count"] for b in blocks)
    return result, blocks


def _base_class(value):
    return (value or "").rsplit(".", 1)[-1]


def _int_value(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _color_hex(value):
    try:
        return f"#{int(value) & 0xFFFFFF:06X}"
    except (TypeError, ValueError):
        return None


def _top(counter, limit=8):
    return [{"value": key, "count": count} for key, count in counter.most_common(limit)]


#: 图表类型元素：`<Plot>` 是单图；组合图把各系列放在 `<VanChartPlot>` 子元素里
#: （帕累托图/柱形图-面积图等），都要读，且组合图可以命中多个类型。
_CHART_ELEMENT_TAGS = ("Plot", "VanChartPlot")

#: 从类名识别类型的关键词，按「具体 → 通用」排序：Map 必须排在 HeatMap/TreeMap 之后，
#: 否则 `VanChartHeatMapPlot` 会被先命中为 Map。用子串匹配类名基类（如 VanChartTreeMapPlot）。
_CHART_TOKENS = (
    ("word-cloud", ("wordcloud",)),
    ("heatmap", ("heatmap",)),
    ("treemap", ("treemap",)),
    ("bubble", ("bubble",)),
    ("scatter", ("scatter",)),
    ("column", ("column",)),
    ("bar", ("bar",)),
    ("line", ("line",)),
    ("pie", ("pie",)),
    ("area", ("area",)),
    ("radar", ("radar",)),
    ("gauge", ("gauge",)),
    ("map", ("map",)),
    ("gantt", ("gantt",)),
    ("funnel", ("funnel",)),
    ("stock", ("stock",)),
)


def _chart_type_from_name(name: str):
    """从一个类名（基类）识别图表类型；识别不到返回 None。"""
    text = (name or "").casefold()
    for key, needles in _CHART_TOKENS:
        if any(needle in text for needle in needles):
            return key
    return None


def _chart_types(elements):
    """从图表元素识别图表类型。

    ⚠️ 只认真正的图表元素：语料里 `<Attr4VanChartScatter>` 这类通用属性节点
    名字里也带 chart/scatter（105 个模板里都有），按任意 tag/class 出现关键词判断会把
    地图等模板误报成散点图。
    规则：
    1. `<Plot>` / `<VanChartPlot>` 的 class 基名 → 类型（组合图可多个）；
    2. 没有任何 Plot 时，退回 `<Chart>` 的 `chartClass`/`class` 基名
       （轮播图等旧式模板只有 `<Chart chartClass="...ColumnMainTypeChart">`）。
    """
    found = set()
    chart_class_names = []
    for element in elements:
        tag = str(element.tag)
        if tag in _CHART_ELEMENT_TAGS:
            key = _chart_type_from_name(_base_class(element.get("class")))
            if key:
                found.add(key)
        elif tag == "Chart":
            chart_class_names.append(_base_class(element.get("chartClass")))
            chart_class_names.append(_base_class(element.get("class")))
    if not found:
        for name in chart_class_names:
            key = _chart_type_from_name(name)
            if key:
                found.add(key)
    return sorted(found)


def _style_profile(root, cells):
    style_list = root.find("StyleList")
    styles = [child for child in list(style_list) if child.tag == "Style"] \
        if style_list is not None else []
    used_ids = sorted({_int_value(cell.get("s"), -1) for cell in cells
                       if cell.get("s") not in (None, "")})
    selected = [styles[i] for i in used_ids if 0 <= i < len(styles)]
    # 没有单元格引用样式时**不要**回退到全部样式：否则模板里没被用到的背景色/字体
    # 会被统计成 color-coding 等信号（实测 49 个真实模板命中、39 个因此假报）。
    # 默认样式（未显式写 s）本来就不产生可靠的视觉证据。

    fonts, sizes, text_colors = Counter(), set(), Counter()
    backgrounds, formats, alignments = Counter(), Counter(), Counter()
    borders = 0
    for style in selected:
        align = style.get("horizontal_alignment")
        if align is not None:
            alignments[{0: "center", 2: "left", 4: "right"}.get(
                _int_value(align, -1), f"raw:{align}")] += 1
        font = style.find("FRFont")
        if font is not None:
            if font.get("name"):
                fonts[font.get("name")] += 1
            if font.get("size"):
                sizes.add(round(_int_value(font.get("size"), 0) / 8, 3))
            if font.get("foreground"):
                color = _color_hex(font.get("foreground"))
                if color:
                    text_colors[color] += 1
        background = style.find("Background")
        if background is not None and _base_class(background.get("name")) != "NullBackground":
            color = _color_hex(background.get("color"))
            if color:
                backgrounds[color] += 1
        fmt = style.find("Format")
        if fmt is not None and (fmt.text or "").strip():
            formats[(fmt.text or "").strip()] += 1
        border = style.find("Border")
        if border is not None and (list(border) or border.attrib):
            borders += 1
    return {
        "defined_styles": len(styles),
        "used_styles": len({i for i in used_ids if 0 <= i < len(styles)}),
        "fonts": _top(fonts),
        "font_sizes_pt": sorted(sizes),
        "text_colors": _top(text_colors),
        "background_colors": _top(backgrounds),
        "number_formats": _top(formats),
        "horizontal_alignment": dict(alignments),
        "styles_with_borders": borders,
    }


def _profile_tree(root, relative=None):
    """从已解析的 WorkBook 提炼一组保守、可复核的设计信号。"""
    elements = list(root.iter())
    parents = {id(child): parent for parent in elements for child in parent}
    reports = [e for e in elements if e.tag == "Report" and id(e) in parents
               and parents[id(e)].tag == "WorkBook"]
    cells = [e for e in elements if e.tag == "C" and id(e) in parents
             and parents[id(e)].tag == "CellElementList"]
    classes = Counter(_base_class(e.get("class")) for e in elements if e.get("class"))
    class_names = set(classes)
    tag_counts = Counter(str(e.tag) for e in elements)

    data_bindings = formulas = merged_cells = vertical_expand = horizontal_expand = 0
    group_cells = list_cells = summary_cells = custom_groups = 0
    highlight_cells = link_cells = 0
    for cell in cells:
        if _int_value(cell.get("cs"), 1) > 1 or _int_value(cell.get("rs"), 1) > 1:
            merged_cells += 1
        expand = cell.find("Expand")
        if expand is not None:
            if expand.get("dir") == "0":
                vertical_expand += 1
            elif expand.get("dir") == "1":
                horizontal_expand += 1
        if cell.find("HighlightList") is not None:
            highlight_cells += 1
        if any("Hyperlink" in _base_class(e.get("class")) for e in cell.iter()):
            link_cells += 1
        obj = cell.find("O")
        if obj is None:
            continue
        object_class = _base_class(obj.get("class"))
        if obj.get("t") == "DSColumn":
            data_bindings += 1
            rg = obj.find("RG")
            if rg is None:
                rg = obj.find("GC")
            rg_class = _base_class(rg.get("class")) if rg is not None else ""
            if rg_class == "SummaryGrouper":
                summary_cells += 1
            elif rg_class == "MonoGrouper":
                list_cells += 1
            elif rg_class == "CustomGrouper":
                custom_groups += 1
            elif rg_class in ("FunctionGrouper", ""):
                attr = rg.find("Attr") if rg is not None else None
                divide_mode = attr.get("divideMode", "0") if attr is not None else "0"
                if _int_value(divide_mode, 0) == 1:
                    list_cells += 1
                else:
                    group_cells += 1
            else:
                group_cells += 1
        elif obj.get("t") == "Formula" or object_class.endswith("Formula"):
            formulas += 1

    parameter_names = set()
    for attr in [e for e in elements if e.tag == "ReportParameterAttr"]:
        for parameter in attr.iter("Parameter"):
            name_el = parameter.find("./Attributes")
            if name_el is not None and name_el.get("name"):
                parameter_names.add(name_el.get("name"))

    dataset_elements = [e for e in elements if e.tag == "TableData"
                        and id(e) in parents and parents[id(e)].tag == "TableDataMap"]
    dataset_types = Counter(_base_class(e.get("class")) for e in dataset_elements)
    widget_classes = {_base_class(e.get("class")) for e in elements
                      if e.tag == "Widget" and e.get("class")}
    link_classes = [name for name in class_names if "Hyperlink" in name]
    link_count = sum(classes[name] for name in link_classes)
    javascript_count = sum(
        count for name, count in classes.items()
        if "JavaScript" in name and name not in ("JavaScriptImpl",))
    submit_classes = {name for name in class_names
                      if "Submit" in name or "SQLSubmiter" in name}
    write_submit_classes = {name for name in class_names
                            if "SQLSubmiter" in name or "BuiltInSQL" in name}
    form_input_classes = set(widget_classes) & {
        "TextEditor", "NumberEditor", "DateEditor", "ComboBox", "CheckBox", "RadioGroup",
        "TextArea", "PasswordEditor", "FileEditor",
    }
    chart_classes = [e for e in elements if e.get("chartClass")]
    chart_count = len(chart_classes)
    if not chart_count:
        chart_count = sum(1 for e in elements if "chart" in str(e.tag).casefold())
    chart_types = _chart_types(elements)
    float_lists = [e for e in elements if e.tag == "FloatElementList"]
    float_count = sum(len(list(e)) for e in float_lists)
    worksheet_attrs = [e for e in elements if e.tag == "WorkSheetAttr"]
    split_sheets = sum(1 for e in worksheet_attrs
                       if e.get("indexsToCopy") not in (None, "")
                       or e.get("maxRowOrColumn") not in (None, ""))
    poly_sheets = sum(1 for e in reports if _base_class(e.get("class")) == "PolyWorkSheet")
    blocks = sum(1 for e in elements if e.tag == "Block")
    absolute_layouts = sum(count for name, count in classes.items()
                           if name.startswith("WAbsoluteLayout") or name == "WParameterLayout")
    frozen_areas = tag_counts["FrozenColumnRow"]
    frozen_controls = tag_counts["FrozenWidgets"]
    hover_tags = tag_counts["AttrTooltip"] + tag_counts["AttrToolTipContent"]
    label_tags = tag_counts["AttrLabel"] + tag_counts["AttrLabelDetail"]
    chart_links = sum(count for name, count in classes.items()
                      if "ChartHyper" in name)
    reportlet_links = sum(count for name, count in classes.items()
                          if name == "ReportletHyperlink")

    style = _style_profile(root, cells)
    signals = {
        "layout": {
            "sheets": len(reports), "poly_sheets": poly_sheets, "blocks": blocks,
            "floating_elements": float_count, "split_sheets": split_sheets,
            "frozen_report_areas": frozen_areas, "frozen_control_panels": frozen_controls,
            "absolute_layout_nodes": absolute_layouts,
        },
        "data": {
            "datasets": len(dataset_elements),
            "dataset_types": dict(dataset_types),
            "parameters": len(parameter_names), "cells": len(cells),
            "data_bindings": data_bindings, "formulas": formulas,
            "vertical_expand_cells": vertical_expand,
            "horizontal_expand_cells": horizontal_expand,
            "group_cells": group_cells, "list_cells": list_cells,
            "summary_cells": summary_cells, "custom_group_cells": custom_groups,
            "merged_cells": merged_cells,
        },
        "visual": {
            **style,
            "top_level_styles": len([e for e in elements if e.tag == "Style"]),
            "conditional_formats": tag_counts["Highlight"],
            "cells_with_conditional_format": highlight_cells,
        },
        "interaction": {
            "widget_nodes": sum(1 for e in elements if e.tag == "Widget"),
            "widget_types": sorted(widget_classes),
            "form_input_types": sorted(form_input_classes),
            "submit_actions": sorted(submit_classes),
            "hyperlinks": link_count, "reportlet_links": reportlet_links,
            "chart_links": chart_links, "cells_with_links": link_cells,
            "javascript_nodes": javascript_count,
        },
        "charts": {
            "count": chart_count,
            "types": chart_types,
            "labels": label_tags, "tooltips": hover_tags,
        },
    }

    form = bool(write_submit_classes and form_input_classes)
    dashboard = bool(chart_count >= 3 and (link_count >= 2 or float_count >= 1)) \
        or "gauge" in chart_types
    crosstab = bool(horizontal_expand and vertical_expand and data_bindings >= 2)
    grouped = bool(group_cells or summary_cells or custom_groups)
    detail = bool(data_bindings and (list_cells or not grouped))
    archetypes = []
    if form:
        archetypes.append("form")
    if dashboard:
        archetypes.append("dashboard")
    if poly_sheets:
        archetypes.append("aggregate-layout")
    if reportlet_links or chart_links:
        archetypes.append("master-detail")
    if crosstab:
        archetypes.append("crosstab")
    if grouped and not crosstab:
        archetypes.append("grouped-table")
    if detail:
        archetypes.append("detail-table")
    if chart_count:
        archetypes.append("chart-analysis")
    if not archetypes:
        archetypes.append("static-layout")

    techniques = []
    def add_technique(name, condition):
        if condition and name not in techniques:
            techniques.append(name)

    add_technique("form-entry", form)
    add_technique("dashboard-layout", dashboard)
    add_technique("multi-sheet", len(reports) > 1)
    add_technique("multi-block", poly_sheets > 0)
    add_technique("floating-layout", float_count > 0)
    add_technique("split-columns", split_sheets > 0)
    add_technique("crosstab", crosstab)
    add_technique("group-subtotals", grouped)
    add_technique("detail-grid", detail)
    add_technique("multi-dataset", len(dataset_elements) > 1)
    add_technique("formula-calculations", formulas > 0)
    add_technique("conditional-formatting", tag_counts["Highlight"] > 0)
    add_technique("linked-report", link_count > 0)
    add_technique("chart-linkage", chart_links > 0)
    add_technique("frozen-report-area", frozen_areas > 0)
    add_technique("frozen-control-panel", frozen_controls > 0)
    add_technique("absolute-layout", absolute_layouts > 0)
    add_technique("custom-javascript", javascript_count > 0)
    add_technique("number-formatting", bool(style["number_formats"]))
    add_technique("color-coding", bool(style["background_colors"] or style["text_colors"]))
    add_technique("chart", chart_count > 0)
    for chart_type in chart_types:
        add_technique("chart-" + chart_type, True)

    return {
        "file": relative,
        "archetype": archetypes[0],
        "archetypes": archetypes,
        "techniques": techniques,
        "chart_types": [_CHART_LABELS.get(key, key) for key in chart_types],
        "signals": signals,
        "study_points": [_LESSONS[name] for name in techniques if name in _LESSONS][:8],
        "boundary": "画像来自 XML 结构；渲染、数据交互、打印和导出效果仍需预览或导出验收。",
    }


def _compact_profile(profile):
    signals = profile["signals"]
    return {
        "file": profile["file"], "archetype": profile["archetype"],
        "archetypes": profile["archetypes"], "techniques": profile["techniques"],
        "chart_types": profile["chart_types"],
        "metrics": {
            "sheets": signals["layout"]["sheets"], "cells": signals["data"]["cells"],
            "datasets": signals["data"]["datasets"], "parameters": signals["data"]["parameters"],
            "charts": signals["charts"]["count"], "links": signals["interaction"]["hyperlinks"],
            "styles": signals["visual"]["defined_styles"],
            "blocks": signals["layout"]["blocks"],
            "floating": signals["layout"]["floating_elements"],
            "split_sheets": signals["layout"]["split_sheets"],
            "frozen_areas": signals["layout"]["frozen_report_areas"],
            "frozen_controls": signals["layout"]["frozen_control_panels"],
            "absolute_nodes": signals["layout"]["absolute_layout_nodes"],
            "vertical_expand": signals["data"]["vertical_expand_cells"],
            "horizontal_expand": signals["data"]["horizontal_expand_cells"],
            "groups": signals["data"]["group_cells"],
            "lists": signals["data"]["list_cells"],
            "summaries": signals["data"]["summary_cells"],
            "data_bindings": signals["data"]["data_bindings"],
            "merged": signals["data"]["merged_cells"],
            "conditional_formats": signals["visual"]["conditional_formats"],
            "highlight_cells": signals["visual"]["cells_with_conditional_format"],
            "widgets": signals["interaction"]["widget_nodes"],
            "form_inputs": len(signals["interaction"]["form_input_types"]),
            "submit_actions": len(signals["interaction"]["submit_actions"]),
            "reportlet_links": signals["interaction"]["reportlet_links"],
            "chart_links": signals["interaction"]["chart_links"],
            "javascript": signals["interaction"]["javascript_nodes"],
        },
    }


def _tag_focus(profile, tag):
    """给目标手法本身加权，降低“顺带包含目标”的查询页或综合模板优先级。"""
    metrics = profile["metrics"]
    if tag in ("grouped-table", "group-subtotals"):
        vertical = metrics.get("vertical_expand", 0)
        groups = metrics.get("groups", 0)
        summaries = metrics.get("summaries", 0)
        bindings = metrics.get("data_bindings", 0)
        return ((300 if vertical else 0) + (300 if groups else 0)
                + (150 if summaries else 0)
                + min(vertical, 3) * 30 + min(groups, 3) * 40
                + min(summaries, 2) * 30 + min(bindings, 4) * 20)
    if tag == "crosstab":
        vertical = metrics.get("vertical_expand", 0)
        horizontal = metrics.get("horizontal_expand", 0)
        groups = metrics.get("groups", 0)
        bindings = metrics.get("data_bindings", 0)
        return ((500 if vertical and horizontal else 0)
                + (100 if vertical else 0) + (100 if horizontal else 0)
                + min(vertical, 3) * 20 + min(horizontal, 2) * 20
                + min(groups, 4) * 30 + min(bindings, 5) * 20)
    if tag in ("form", "form-entry"):
        bindings = min(metrics.get("data_bindings", 0), 20)
        return (min(metrics.get("form_inputs", 0), 8) * 10
                + min(metrics.get("submit_actions", 0), 4) * 25
                + bindings * 18 - min(metrics.get("javascript", 0), 8) * 5
                - (50 if not bindings else 0))
    if tag in ("dashboard", "dashboard-layout"):
        return ((300 if metrics.get("charts", 0) else 0)
                + min(metrics.get("charts", 0), 8) * 20
                + min(metrics.get("floating", 0), 8) * 10
                + min(metrics.get("links", 0), 8) * 10)
    if tag == "master-detail":
        return ((300 if metrics.get("reportlet_links", 0) or metrics.get("chart_links", 0) else 0)
                + min(metrics.get("reportlet_links", 0), 6) * 25
                + min(metrics.get("chart_links", 0), 6) * 30)
    if tag in ("detail-table", "detail-grid"):
        return ((300 if metrics.get("lists", 0) else 0)
                + min(metrics.get("lists", 0), 8) * 25
                + min(metrics.get("data_bindings", 0), 24) * 5)
    if tag in ("aggregate-layout", "multi-block"):
        return ((400 if metrics.get("blocks", 0) else 0)
                + min(metrics.get("blocks", 0), 8) * 50)
    if tag in ("chart-analysis", "chart"):
        return ((300 if metrics.get("charts", 0) else 0)
                + min(metrics.get("charts", 0), 8) * 25)
    if tag == "chart-linkage":
        return ((400 if metrics.get("chart_links", 0) else 0)
                + min(metrics.get("chart_links", 0), 4) * 50
                + (200 if metrics.get("data_bindings", 0) else 0))
    if tag == "split-columns":
        return ((400 if metrics.get("split_sheets", 0) else 0)
                + min(metrics.get("split_sheets", 0), 4) * 60)
    if tag == "conditional-formatting":
        return ((400 if metrics.get("conditional_formats", 0) else 0)
                + min(metrics.get("conditional_formats", 0), 6) * 30
                + min(metrics.get("highlight_cells", 0), 20) * 5)
    if tag == "frozen-report-area":
        return ((300 if metrics.get("frozen_areas", 0) else 0)
                + min(metrics.get("frozen_areas", 0), 2) * 60)
    if tag == "frozen-control-panel":
        return ((300 if metrics.get("frozen_controls", 0) else 0)
                + min(metrics.get("frozen_controls", 0), 2) * 60)
    if tag == "floating-layout":
        return ((300 if metrics.get("floating", 0) else 0)
                + min(metrics.get("floating", 0), 8) * 30)
    if tag == "custom-javascript":
        return ((300 if metrics.get("javascript", 0) else 0)
                + min(metrics.get("javascript", 0), 8) * 25)
    if tag == "linked-report":
        return ((300 if metrics.get("reportlet_links", 0) else 0)
                + min(metrics.get("reportlet_links", 0), 8) * 30)
    return 0


def _off_target_complexity(profile, tag):
    """基础结构类目标先看清楚骨架，综合功能不能替代目标技术本身。"""
    if tag not in {
        "grouped-table", "group-subtotals", "crosstab", "detail-table",
        "detail-grid", "aggregate-layout", "multi-block", "floating-layout",
        "split-columns", "frozen-report-area", "conditional-formatting",
        "number-formatting", "color-coding", "chart-analysis", "chart",
    }:
        return 0
    metrics = profile["metrics"]
    penalty = (min(metrics.get("widgets", 0), 20) * 20
               + min(metrics.get("absolute_nodes", 0), 20) * 12
               + min(metrics.get("javascript", 0), 20) * 15
               + max(metrics.get("sheets", 1) - 1, 0) * 80
               + max(metrics.get("datasets", 1) - 1, 0) * 20)
    if tag in {"grouped-table", "group-subtotals", "crosstab", "detail-table",
               "detail-grid", "chart-analysis", "chart"}:
        penalty += metrics.get("charts", 0) * 10
    return penalty


_TAG_LESSON_KEYS = {
    "grouped-table": "group-subtotals",
    "detail-table": "detail-grid",
    "chart-analysis": "chart",
    "aggregate-layout": "multi-block",
}


def _ordered_study_points(profile, tag=None):
    """按标签检索时先给目标手法，避免查询控件等附带能力抢占首个学习点。"""
    names = list(profile["techniques"])
    target = _TAG_LESSON_KEYS.get(tag, tag)
    if target in names:
        names.remove(target)
        names.insert(0, target)
    return [_LESSONS[name] for name in names if name in _LESSONS][:8]


def _learning_score(profile, tag=None):
    """给代表样例排序：目标优先，再兼顾信号完整度和可学习的聚焦度。"""
    metrics = profile["metrics"]
    cells = metrics.get("cells", 0)
    score = 0
    if not tag:
        score += min(len(profile["techniques"]), 16) * 12
        score += min(len(profile["archetypes"]), 5) * 6
        score += min(metrics.get("charts", 0), 6) * 8
        score += min(metrics.get("links", 0), 12) * 5
        score += min(metrics.get("datasets", 0), 4) * 4
        score += min(metrics.get("styles", 0), 20) * 2
        score += min(metrics.get("sheets", 0), 6) * 3
        # 超大综合模板能证明许多能力可以组合，但作为单一手法样板往往不够聚焦。
        score -= min(max(cells - 120, 0) // 8, 60)
    if tag:
        tag_key = tag.casefold()
        archetype_match = any(tag_key == item.casefold()
                              for item in profile["archetypes"])
        technique_match = any(tag_key == item.casefold()
                              for item in profile["techniques"])
        if archetype_match:
            score += 1000
            # 原型越单一，越容易直接看清该手法的骨架；仍是首原型时再加强。
            if len(profile["archetypes"]) == 1:
                score += 400
            elif profile["archetype"].casefold() == tag_key:
                score += 250
        elif technique_match:
            score += 1000
        score += _tag_focus(profile, tag_key)
        score -= _off_target_complexity(profile, tag_key)
        if len(profile["archetypes"]) == 1:
            score += 200
        # 目标结构已经命中后，用连续规模项选择容易逐格复盘的样板。
        if cells <= 40:
            score += 500 - max(cells - 6, 0) * 8
        elif cells <= 80:
            score += max(100, 220 - (cells - 40) * 4)
        elif cells <= 160:
            score += max(0, 60 - (cells - 80) // 4)
        else:
            score -= min((cells - 160) // 8, 500)
    return score


def profile_examples(directory, keyword=None, contains=None, tag=None, limit=20):
    """批量提炼本地 CPT 的设计画像、技术分布与代表样例。"""
    root = Path(directory).expanduser().resolve()
    if not root.is_dir():
        raise ApiError(f"示例目录不存在或不是目录: {root}")
    candidates, problems = _candidate_cpts(root, keyword)
    profiles = []
    valid = 0
    for relative, candidate in candidates:
        try:
            raw = candidate.read_bytes()
            # 先解码成 str 再解析：ElementTree 直接吃 bytes 时，XML 声明里的多字节编码
            # （GBK/GB2312/Big5/Shift_JIS…）会抛 ValueError("multi-byte encodings are
            # not supported")、未知编码抛 LookupError；两者都不在上面的 per-file except 里，
            # 会让整次目录扫描崩成 UNKNOWN（而不是把该文件记进 skipped）。
            text = raw.decode("utf-8-sig")
            if contains is not None and contains not in text:
                continue
            parsed = ElementTree.fromstring(text)
            if parsed.tag != "WorkBook":
                raise ApiError(f"根元素是 {parsed.tag!r}，不是 WorkBook")
        except (OSError, UnicodeError, ElementTree.ParseError, ApiError) as exc:
            problems.append({"path": relative, "error": str(exc)})
            continue
        valid += 1
        profiles.append(_compact_profile(_profile_tree(parsed, relative)))

    tag_key = tag.casefold() if tag else None
    matched = [profile for profile in profiles
               if tag_key is None or any(tag_key == item.casefold()
                                         for item in profile["techniques"] + profile["archetypes"])]
    archetypes = Counter(item for profile in profiles for item in profile["archetypes"])
    techniques = Counter(item for profile in profiles for item in profile["techniques"])
    chart_types = Counter(item for profile in profiles for item in profile["chart_types"])
    design_lessons = [
        {"technique": name, "examples": count, "guidance": _LESSONS[name]}
        for name, count in techniques.most_common() if name in _LESSONS
    ]
    ranked = []
    for item in matched:
        candidate = dict(item)
        candidate["study_score"] = _learning_score(candidate, tag_key)
        ranked.append(candidate)
    ranked.sort(key=lambda item: (-item["study_score"], item["file"].casefold()))

    samples = []
    for item in ranked[:limit]:
        sample = dict(item)
        sample["study_points"] = _ordered_study_points(item, tag_key)
        samples.append(sample)
    return {
        "root": str(root), "scanned": len(candidates), "valid": valid,
        "matched": len(matched), "returned": len(samples), "truncated": len(matched) > limit,
        "tag_filter": tag,
        "valid_semantics": "valid 是读取并解析成功（若给 --contains 还须命中该串）的文件数；"
                           "--contains 时会小于 scanned。",
        "archetypes": dict(archetypes.most_common()),
        "techniques": dict(techniques.most_common()),
        "chart_types": dict(chart_types.most_common()),
        "design_lessons": design_lessons,
        "samples": samples,
        "skipped_count": len(problems), "skipped": problems[:20],
        "score_semantics": "study_score 是标签检索排序分，不代表设计质量或线上可用性。",
        "boundary": "批量画像用于寻找设计参考，不证明样例数据、公式或渲染在当前实例可用。",
    }


def inspect_template(path, sheet=None, block=None, include_cells=False, limit=100,
                     include_design=False, include_sql=False):
    """检查一个本地 CPT；聚合报表的每个 Block 保留独立坐标。

    `include_sql=True` 时给每个数据集附带 `<Query>` 里的 SQL（去掉首尾空白）与连接名
    （`<Connection><DatabaseName>`，取不到回退 `<Connection>` 直接文本）。
    线上 `report datasets --sql` 由服务端全量解析，大模板可能分钟级；先 `report download`
    拿模板原始字节、再本地 `--sql` 是离线快路径（不触发服务端校验）。
    """
    source = Path(path).expanduser().resolve()
    try:
        raw = source.read_bytes()
        text = raw.decode("utf-8-sig")
        # 与 profile_examples 同理：用 str 解析，避免编码声明触发多字节编码错误。
        parsed = ElementTree.fromstring(text)
    except (OSError, UnicodeError, ElementTree.ParseError) as exc:
        raise ApiError(f"无法读取或解析本地 CPT: {source}: {exc}") from exc
    if parsed.tag != "WorkBook":
        raise ApiError(f"本地文件根元素是 {parsed.tag!r}，不是 CPT 模板的 WorkBook")

    reports = cptxml.sheet_elements(text)
    descriptions = [_describe_sheet(text, report) for report in reports]
    selected = None
    if sheet is not None:
        indexes = [i for i, (info, _) in enumerate(descriptions) if info["name"] == sheet]
        if len(indexes) != 1:
            raise ApiError(f"sheet {sheet!r} 不存在或名称不唯一；现有: "
                           f"{[info['name'] for info, _ in descriptions]}")
        selected = indexes[0]
    elif descriptions:
        selected = 0
    if selected is None:
        raise ApiError("模板没有 Report 工作表，不能检查版面")

    info, blocks = descriptions[selected]
    if block is not None:
        if not info["poly"] or block < 1 or block > len(blocks):
            raise ApiError(f"sheet {info['name']!r} 没有第 {block} 个聚合块")
        blocks = [blocks[block - 1]]

    datasets = []
    for node in parsed.findall("./TableDataMap/TableData"):
        item = {"name": node.get("name", ""), "class": node.get("class", "")}
        if include_sql:
            query = node.find("Query")
            sql = (query.text or "").strip() if query is not None else ""
            item["sql"] = sql or None
            # 真实 CPT 的连接名在 <Connection><DatabaseName>；直接 <Connection> 文本通常只有空白。
            database = node.find("Connection/DatabaseName")
            if database is None:
                database = node.find("Connection")
            name = (database.text or "").strip() if database is not None else ""
            item["connection"] = name or None
        datasets.append(item)
    result = {"file": str(source), "bytes": len(raw), "root": parsed.tag,
              "datasets": datasets, "sheets": [item[0] for item in descriptions],
              "selected_sheet": info["name"], "selected_block": block,
              "cell_count": sum(b["cell_count"] for b in blocks)}
    if include_cells:
        rows = []
        fields = ("a1", "kind", "text", "formula", "binding", "ds_mode",
                  "ds_mode_explicit", "ds_result", "ds_filter", "expand", "expand_left",
                  "expand_up", "style", "cs", "rs", "hl_count")
        for b in blocks:
            elements = _cell_elements(text, b["_container"])
            elements.sort(key=lambda el: (cptxml._int_attr(el, "r"),
                                          cptxml._int_attr(el, "c")))
            for element in elements:
                if len(rows) >= limit:
                    break
                cell = cptxml._cell_info(text, element, info["name"])
                row = {key: cell.get(key) for key in fields}
                if info["poly"]:
                    row = {"block_index": b["index"], "block_name": b["name"], **row}
                rows.append(row)
        result.update({"cells": rows, "returned": len(rows),
                       "truncated": result["cell_count"] > len(rows)})
    if include_design:
        result["design"] = _profile_tree(parsed, source.name)
    from .cptmodel import DocumentIndex
    result["validation"] = DocumentIndex(text, parsed_root=parsed).report()
    return result
