"""CPT 的一次性结构索引、引用词法分析和离线诊断。

索引保留 cptxml.Element 的原文区间，不用 XML 序列化器回写。公式只识别有明确
边界的引用 token，字符串、参数和数据集字段不参与坐标替换。未知运行时行为
显式列入 unsupported，不能把静态检查冒充执行结果。
"""

from collections import defaultdict
from dataclasses import dataclass, field
from html import unescape
import re
from xml.etree import ElementTree

from . import cptxml
from .exceptions import ApiError, TemplateValidationError


_ADDRESS = r"(?P<ca>\$?)(?P<col>[A-Za-z]{1,3})(?P<ra>\$?)(?P<row>[1-9][0-9]*)"
_REFERENCE = re.compile(
    r"(?:(?P<sheet>'(?:[^']|'')+'|[^\W\d]\w*)(?P<sep>[!~]))?" + _ADDRESS)
_DYNAMIC = re.compile(r"(?i)(?<![\w.])(EVAL|INDIRECT|OFFSET)\s*\(")
_EXCEL_ADDRESS = re.compile(r"(?<![\w.$])(?:\$?[A-Za-z]{1,3}\$[1-9][0-9]*|\${2,}[A-Za-z]{1,3}[1-9][0-9]*)(?!\w)")
FORMULA_TAGS = {"Formula", "SortFormula", "Result", "FC"}
SAFE_JS = {"ReportletHyperlink", "WebHyperlink", "EmailHyperlink", "HyperlinkGroup"}
LITERAL_TAGS = {"O", "Attributes", "Query", "PageQuery", "DatabaseName", "Name", "Text", "Title",
                "Content", "Description", "Label", "String", "Format", "Value", "PWTitle"}


class GridScope(str):
    """给既有网格命令传递 block，仍按 sheet 字符串输出 JSON。"""

    def __new__(cls, sheet, block):
        value = super().__new__(cls, sheet or "")
        value.sheet, value.block = sheet, block
        return value


@dataclass(frozen=True)
class Address:
    col: int
    row: int
    sheet: str = None
    prefix: str = ""
    value_position: bool = False

    def render(self, col=None, row=None, prefix=None):
        c = self.col if col is None else col
        r = self.row if row is None else row
        if c < 0 or c > 18277 or r < 0:
            raise ApiError("坐标变换结果越界（列 A..ZZZ，行号从 1 起）")
        return ((self.prefix if prefix is None else prefix)
                + ("$" if self.value_position else "") + cptxml.col_letters(c) + str(r + 1))


@dataclass(frozen=True)
class FormulaRef:
    start: int
    end: int
    first: Address
    last: Address = None
    separator: str = ":"
    ambiguous_dataset: bool = False

    def render(self, first, last=None):
        return first if self.last is None else first + self.separator + last


def _address(match):
    raw = match.group("sheet")
    sheet = raw[1:-1].replace("''", "'") if raw and raw.startswith("'") else raw
    prefix = (raw + match.group("sep")) if raw else ""
    col, row = cptxml.parse_a1(match.group("col") + match.group("row"))
    return Address(col, row, sheet, prefix, bool(match.group("ca")))


def _dataset_regions(expression):
    """数据集方法的参数域；裸字段名与格号可能同形，不能盲目重写。"""
    code = code_without_strings(expression)
    regions = []
    for call in re.finditer(r"(?i)\b\w+\.(?:select|group|value)\s*\(", code):
        start, first_end, depth = call.end(), None, 1
        for end in range(start, len(code)):
            ch = code[end]
            if ch in "([{":
                depth += 1
            elif ch in ")]}":
                depth -= 1
                if depth == 0:
                    regions.append((start, end, first_end if first_end is not None else end))
                    break
            elif ch == "," and depth == 1 and first_end is None:
                first_end = end
    return code, regions


def formula_refs(expression):
    """识别普通/跨 sheet/区域/层次表达式内引用，保留每个 token 的原始区间。"""
    out, i = [], 0
    code, dataset_regions = _dataset_regions(expression)
    while i < len(expression):
        previous = expression[i - 1] if i else ""
        match = _REFERENCE.match(expression, i)
        if match and not (previous and (previous.isalnum() or previous in "_.$")):
            end = match.end()
            if match.group("ra"):
                i = end
                continue
            following = expression[end:end + 1]
            tail = expression[end:].lstrip()
            if not (following and (following.isalnum() or following == "_")) and not tail.startswith("("):
                first, last, separator = _address(match), None, ":"
                colon = re.match(r"\s*:\s*", expression[end:])
                if colon:
                    second = _REFERENCE.match(expression, end + colon.end())
                    if second and not second.group("ra") and not (expression[second.end():second.end() + 1] or " ").isalnum():
                        last = _address(second)
                        separator = expression[end:second.start()]
                        end = second.end()
                ambiguous = False
                if not first.sheet and not first.value_position and last is None:
                    region = next((r for r in dataset_regions if r[0] <= i < r[1]), None)
                    if region:
                        first_arg = code[region[0]:region[2]].strip()
                        raw = expression[i:end]
                        argument_start = max(region[0], code.rfind(",", region[0], i) + 1)
                        field_left = (not code[argument_start:i].strip()
                                      and re.match(r"\s*(?:==|!=|>=|<=|=|>|<)", code[end:]))
                        if first_arg == raw or field_left:
                            i = end
                            continue
                        ambiguous = True
                out.append(FormulaRef(i, end, first, last, separator, ambiguous))
                i = end
                continue
        if expression[i] in "\"'":
            quote = expression[i]
            i += 1
            while i < len(expression):
                ch = expression[i]
                i += 1
                if ch == "\\":
                    i += 1
                elif ch == quote:
                    if i < len(expression) and expression[i] == quote:
                        i += 1
                    else:
                        break
            continue
        i += 1
    return out


def code_without_strings(expression):
    """仅供动态函数诊断，不用于重写；保留 quoted-sheet 引用。"""
    from .formulas import mask_strings
    try:
        return mask_strings(expression)
    except ApiError:
        return expression


@dataclass
class Cell:
    element: object
    grid: object
    col: int
    row: int
    cs: int
    rs: int
    expand: object = None

    @property
    def at(self):
        return cptxml.format_a1(self.col, self.row)

    @property
    def rect(self):
        return self.col, self.row, self.col + self.cs - 1, self.row + self.rs - 1


@dataclass
class Grid:
    sheet: str
    block: int
    element: object
    cells_element: object
    cells: list = field(default_factory=list)

    @property
    def key(self):
        return self.sheet, self.block


@dataclass
class Surface:
    element: object
    expression: str
    grid: object = None
    cell: object = None
    attr: str = None
    kind: str = "formula"
    refs: list = field(default_factory=list)
    implicit: bool = False

    def location(self):
        return {"sheet": self.grid.sheet if self.grid else None,
                "block": self.grid.block if self.grid else None,
                "at": self.cell.at if self.cell else None,
                "tag": self.element.name, "attribute": self.attr}


class DocumentIndex:
    """每个快照只扫描一次；所有节点查找基于父子索引和区间。"""

    def __init__(self, text, parsed_root=None):
        self.text = text
        try:
            root = parsed_root if parsed_root is not None else ElementTree.fromstring(text)
        except (ElementTree.ParseError, ValueError) as exc:
            raise TemplateValidationError("CPT XML 无法解析", [
                {"severity": "error", "code": "invalid_xml", "message": str(exc)}]) from exc
        if root.tag != "WorkBook":
            raise TemplateValidationError("不是完整 CPT 模板", [
                {"severity": "error", "code": "invalid_root", "message": "根元素必须是 WorkBook"}])
        self.elements = sorted(cptxml.scan(text), key=lambda e: e.open_start)
        self.children, self.parent, self.by_name = defaultdict(list), {}, defaultdict(list)
        stack = []
        for el in self.elements:
            while stack and el.open_start >= stack[-1].close_end:
                stack.pop()
            if stack:
                self.parent[el] = stack[-1]
                self.children[stack[-1]].append(el)
            self.by_name[el.name].append(el)
            if not el.empty:
                stack.append(el)
        self.grids, self.surfaces, self.unsupported, self.diagnostics = [], [], [], []
        self.cell_for, self.grid_for = {}, {}
        self.parameter_names = {unescape(a.attrs.get("name", ""))
                                for p in self.by_name["Parameter"] for a in self.direct(p, "Attributes")}
        self.sheet_elements = [e for e in self.by_name["Report"] if self.parent.get(e) is self.elements[0]]
        self.sheet_names = [unescape(e.attrs.get("name", "")) for e in self.sheet_elements]
        for sheet in self.sheet_elements:
            name = unescape(sheet.attrs.get("name", ""))
            if sheet.attrs.get("class", "").endswith("PolyWorkSheet"):
                for number, block in enumerate(self.direct(sheet, "Block"), 1):
                    container = self.child(block, "CellElementList")
                    if container is not None:
                        self.grids.append(Grid(name, number, block, container))
                    else:
                        self.unsupported.append({"code": "non_grid_block", "sheet": name,
                                                 "block": number, "tag": "Block"})
            else:
                self.grids.append(Grid(name, None, sheet, self.child(sheet, "CellElementList")))
        for grid in self.grids:
            for el in self.descendants(grid.element):
                self.grid_for[el] = grid
            if grid.cells_element:
                for el in self.direct(grid.cells_element, "C"):
                    try:
                        col, row = int(el.attrs.get("c", "0")), int(el.attrs.get("r", "0"))
                        cs, rs = int(el.attrs.get("cs", "1")), int(el.attrs.get("rs", "1"))
                        if min(col, row) < 0 or col > 18277 or min(cs, rs) < 1:
                            raise ValueError("坐标或合并跨度越界")
                    except ValueError as exc:
                        self.diagnostics.append({"severity": "error", "code": "invalid_cell",
                                                 "sheet": grid.sheet, "block": grid.block,
                                                 "message": str(exc)})
                        continue
                    cell = Cell(el, grid, col, row, cs, rs, self.child(el, "Expand"))
                    grid.cells.append(cell)
                    for node in self.descendants(el):
                        self.cell_for[node] = cell
        self._surfaces()
        self._implicit_parents()
        self._validate()

    def direct(self, parent, name):
        return [e for e in self.children.get(parent, ()) if e.name == name]

    def child(self, parent, name):
        return next(iter(self.direct(parent, name)), None)

    def descendants(self, parent):
        pending = [parent]
        while pending:
            node = pending.pop()
            yield node
            pending.extend(reversed(self.children.get(node, ())))

    def value(self, element):
        return unescape(element.text(self.text)) if "<![CDATA[" not in element.content(self.text) else element.text(self.text)

    def select(self, sheet=None, block=None):
        if sheet is None:
            if len(self.sheet_names) != 1:
                raise ApiError("多 sheet 模板必须明确 --sheet；可用: " + ", ".join(self.sheet_names))
            sheet = self.sheet_names[0]
        matches = [g for g in self.grids if g.sheet == sheet and g.block == block]
        if len(matches) != 1:
            raise ApiError(f"无法唯一定位网格 sheet={sheet!r}, block={block!r}；聚合报表必须明确 --block")
        return matches[0]

    def add_surface(self, element, expression, attr=None, kind="formula", implicit=False, cell=None):
        surface = Surface(element, expression, self.grid_for.get(element),
                          cell or self.cell_for.get(element), attr, kind,
                          formula_refs(expression), implicit)
        self.surfaces.append(surface)
        if any(a.value_position and a.render(prefix="").lstrip("$") in self.parameter_names
               for ref in surface.refs for a in (ref.first, ref.last) if a):
            self.unsupported.append({"code": "ambiguous_parameter_reference", **surface.location(),
                                     "expression": expression,
                                     "message": "同名参数与 $Cell 引用无法区分，不自动重写"})
        if any(ref.ambiguous_dataset for ref in surface.refs):
            self.unsupported.append({"code": "ambiguous_dataset_reference", **surface.location(),
                                     "expression": expression,
                                     "message": "数据集方法中的裸名称可能是字段或单元格；需明确引用语义"})
        if _EXCEL_ADDRESS.search(code_without_strings(expression)):
            self.unsupported.append({"code": "excel_style_address", **surface.location(),
                                     "expression": expression,
                                     "message": "Excel 的行列锁定写法未确证为 FineReport 单元格引用；不自动重写"})
        if any(a.prefix.endswith("~") for ref in surface.refs for a in (ref.first, ref.last) if a):
            self.unsupported.append({"code": "unknown_qualified_reference", **surface.location(),
                                     "expression": expression})
        if not implicit and _DYNAMIC.search(code_without_strings(expression)):
            self.unsupported.append({"code": "dynamic_reference", **surface.location(),
                                     "expression": expression})
        if kind == "formula":
            from .formulas import _CALL, FUNCTIONS, _DATASET_METHODS
            for match in _CALL.finditer(code_without_strings(expression)):
                name = match.group(1).upper()
                key = "DATASET." + name.rsplit(".", 1)[1] if "." in name and name.rsplit(".", 1)[1] in _DATASET_METHODS else name
                if key not in FUNCTIONS:
                    self.unsupported.append({"code": "unknown_function", **surface.location(), "function": name})
        return surface

    def _surfaces(self):
        payloads = set()
        for el in self.elements:
            if (el.name == "O" and el.attrs.get("t") == "Formula" or
                                   el.attrs.get("class", "").rsplit(".", 1)[-1] in ("Formula", "BaseFormula", "ResultFormula")):
                value = self.child(el, "Attributes")
                if value is not None:
                    payloads.add(value)
            elif el.name in FORMULA_TAGS and not self.children.get(el):
                payloads.add(el)
            if el.name == "Expand":
                for key in ("left", "up"):
                    value = unescape(el.attrs.get(key, ""))
                    if value and value.lower() not in ("none", "null"):
                        surface = self.add_surface(el, value, key, "parent")
                        if len(surface.refs) != 1 or surface.refs[0].last is not None:
                            self.unsupported.append({"code": "unknown_parent", **surface.location(), "expression": value})
            if el.name in ("ColumnRow", "FixCell"):
                keys = ("column", "row") if el.name == "ColumnRow" else ("col", "row")
                try:
                    c, r = (int(el.attrs[k]) for k in keys)
                    if min(c, r) >= 0:
                        self.add_surface(el, cptxml.format_a1(c, r), keys, "coordinate")
                    elif (c, r) != (-1, -1):
                        raise ValueError("部分坐标为负")
                except (KeyError, ValueError) as exc:
                    self.unsupported.append({"code": "unknown_coordinate", **self.location(el), "message": str(exc)})
            cls = el.attrs.get("class", "").rsplit(".", 1)[-1]
            full_class = el.attrs.get("class", "")
            metadata_only = (el.name == "TemplateCloudInfoAttrMark" and
                             full_class == "com.fr.plugin.cloud.analytics.attr.TemplateInfoAttrMark")
            if full_class and not metadata_only and (not full_class.startswith(("com.fr.", "java.")) and "." in full_class
                               or full_class.startswith("com.fr.plugin.") and not full_class.startswith("com.fr.plugin.chart.")):
                self.unsupported.append({"code": "plugin_structure", **self.location(el), "class": full_class})
            known_coordinates = {"C", "ColumnRow", "FixCell", "FrozenColumnRow", "HR", "FR", "HC", "FC", "UPFCR", "WorkSheetAttr"}
            suspicious_keys = {"ref", "cell", "cellName", "columnRow", "startCell", "endCell", "rowIndex", "columnIndex", "c", "r", "col", "row"}
            if el.name not in known_coordinates and suspicious_keys.intersection(el.attrs):
                self.unsupported.append({"code": "unregistered_coordinate_attributes", **self.location(el)})
            if (not self.children.get(el) and el.name not in LITERAL_TAGS | FORMULA_TAGS
                    and el.name not in known_coordinates and self.value(el).strip()
                    and formula_refs(self.value(el))):
                self.unsupported.append({"code": "unregistered_reference_surface", **self.location(el)})
            if el.name in ("JavaScript", "Script", "JavaScriptImpl") and cls not in SAFE_JS:
                self.unsupported.append({"code": "script", **self.location(el), "class": cls})
            if el.name == "FloatElementList" and self.children.get(el):
                self.unsupported.append({"code": "floating_elements", **self.location(el)})
            if el.name == "O" and (el.attrs.get("class") or el.attrs.get("t")):
                token = el.attrs.get("class") or el.attrs.get("t")
                if (el.attrs.get("t") not in ("DSColumn", "Formula", "CC", "I", "D", "S", "B", "Date", "Integer", "Double", "String", "Boolean")
                        and not any(part in token for part in ("Formula", "Chart", "Image", "java.lang.", "java.util.Date"))):
                    self.unsupported.append({"code": "unknown_value_type", **self.location(el), "class": token})
        for el in sorted(payloads, key=lambda e: e.open_start):
            self.add_surface(el, self.value(el))

    def location(self, el):
        grid, cell = self.grid_for.get(el), self.cell_for.get(el)
        return {"sheet": grid.sheet if grid else None, "block": grid.block if grid else None,
                "at": cell.at if cell else None, "tag": el.name}

    def _implicit_parents(self):
        # SheetUtils.calculateDefaultParent 的两个扫描方向：上父格来自横向扩展，
        # 左父格来自纵向扩展。合并跨度参与覆盖；显式“无父格”会形成扫描屏障。
        for grid in self.grids:
            for side, direction, coordinate, span, order in (
                    ("up", "1", "col", "cs", lambda c: (c.row, c.col)),
                    ("left", "0", "row", "rs", lambda c: (c.col, c.row))):
                pool = {}
                for cell in sorted(grid.cells, key=order):
                    exp = cell.expand
                    start = getattr(cell, coordinate)
                    width = getattr(cell, span)
                    if width > 100000:
                        self.unsupported.append({"code": "large_implicit_span", "sheet": grid.sheet,
                                                 "block": grid.block, "at": cell.at})
                        continue
                    covered = range(start, start + width)
                    explicit = exp is not None and (exp.attrs.get(side) or
                                                     exp.attrs.get(side + "ParentDefault") == "false")
                    if not explicit:
                        parent = next((pool[n] for n in covered if n in pool and pool[n] is not cell), None)
                        if parent:
                            self.add_surface(exp or cell.element, parent.at, side, "implicit-parent", True, cell)
                    if exp is not None and exp.attrs.get("dir") == direction:
                        pool.update((n, cell) for n in covered)
                    elif explicit and not exp.attrs.get(side):
                        for n in covered:
                            pool.pop(n, None)

    def _validate(self):
        if not self.sheet_names:
            self.diagnostics.append({"severity": "error", "code": "missing_sheet", "message": "模板没有 Report 工作表"})
        if len(set(self.sheet_names)) != len(self.sheet_names):
            self.diagnostics.append({"severity": "error", "code": "duplicate_sheet", "message": "sheet 名不唯一"})
        styles = len(self.direct(self.child(self.elements[0], "StyleList"), "Style"))
        datasets = {unescape(e.attrs.get("name", "")) for e in self.by_name["TableData"]
                    if self.parent.get(e) and self.parent[e].name == "TableDataMap"}
        for grid in self.grids:
            occupied = set()
            merged = []
            for cell in grid.cells:
                loc = {"sheet": grid.sheet, "block": grid.block, "at": cell.at}
                if (cell.col, cell.row) in occupied:
                    self.diagnostics.append({"severity": "error", "code": "duplicate_cell", **loc,
                                             "message": "同一网格有重复坐标"})
                occupied.add((cell.col, cell.row))
                style = cell.element.attrs.get("s")
                if style is not None and (not style.isdigit() or int(style) >= styles):
                    self.diagnostics.append({"severity": "error", "code": "invalid_style", **loc,
                                             "message": f"样式索引 {style} 不存在"})
                if cell.cs > 1 or cell.rs > 1:
                    merged.append(cell)
            # 扫描线只比较行区间有交集的合并区域，不遍历整个稀疏网格。
            active = []
            for cell in sorted(merged, key=lambda c: c.row):
                active = [a for a in active if a.rect[3] >= cell.row]
                for other in active:
                    if rectangles_intersect(cell.rect, other.rect):
                        self.diagnostics.append({"severity": "error", "code": "overlapping_merge",
                                                 "sheet": grid.sheet, "block": grid.block,
                                                 "at": cell.at, "message": f"合并区域与 {other.at} 重叠"})
                active.append(cell)
        for el in self.by_name["O"]:
            if el.attrs.get("t") == "DSColumn":
                attrs = self.child(el, "Attributes")
                name = unescape(attrs.attrs.get("dsName", attrs.attrs.get("dbName", ""))) if attrs else ""
                if name not in datasets:
                    self.diagnostics.append({"severity": "error", "code": "missing_dataset", **self.location(el),
                                             "message": f"绑定的数据集 {name!r} 不存在"})
        parent_edges = defaultdict(dict)
        for surface in self.surfaces:
            if surface.kind == "formula":
                from .formulas import check_formula
                if surface.expression.strip():
                    try:
                        check_formula(surface.expression)
                    except ApiError as exc:
                        self.diagnostics.append({"severity": "error", "code": "invalid_formula",
                                                 **surface.location(), "message": str(exc)})
            for ref in surface.refs:
                if ref.first.sheet is not None and any(g.sheet == ref.first.sheet and g.block is not None for g in self.grids):
                    self.unsupported.append({"code": "aggregate_reference_scope", **surface.location(),
                                             "expression": surface.expression})
                for addr in (ref.first, ref.last):
                    if addr and addr.sheet is not None and addr.sheet not in self.sheet_names:
                        self.diagnostics.append({"severity": "error", "code": "missing_reference_sheet",
                                                 **surface.location(), "message": f"引用的 sheet {addr.sheet!r} 不存在"})
                if surface.kind in ("parent", "implicit-parent") and surface.cell and not ref.first.sheet:
                    parent_edges[(*surface.grid.key, surface.attr)].setdefault((surface.cell.col, surface.cell.row), []).append(
                        (ref.first.col, ref.first.row))
        for key, edges in parent_edges.items():
            complete = set()
            for start in edges:
                visiting, stack = set(), [(start, False)]
                while stack:
                    node, leaving = stack.pop()
                    if leaving:
                        visiting.discard(node)
                        complete.add(node)
                    elif node in visiting:
                        self.diagnostics.append({"severity": "error", "code": "parent_cycle", "sheet": key[0],
                                                 "block": key[1], "at": cptxml.format_a1(*node),
                                                 "message": "扩展父格存在循环依赖"})
                        break
                    elif node not in complete:
                        visiting.add(node)
                        stack.append((node, True))
                        stack.extend((n, False) for n in edges.get(node, ()))

    def report(self):
        return {"validation_level": "structural", "runtime_verified": False,
                "can_apply": not any(d["severity"] == "error" for d in self.diagnostics),
                "diagnostics": self.diagnostics, "unsupported": self.unsupported,
                "coverage_complete": not self.unsupported,
                "coordinate_transform_ready": not self.unsupported and not self.diagnostics,
                "sheets": self.sheet_names, "grids": [
                    {"sheet": g.sheet, "block": g.block, "cell_count": len(g.cells)} for g in self.grids],
                "reference_count": sum(len(s.refs) for s in self.surfaces)}

    def references(self, sheet=None, block=None, at=None):
        selected = self.select(sheet, block) if sheet is not None or block is not None or at else None
        point = cptxml.parse_a1(at) if at else None
        rows = []
        for surface in self.surfaces:
            for ref in surface.refs:
                target_sheet = ref.first.sheet or (surface.grid.sheet if surface.grid else None)
                target_block = surface.grid.block if surface.grid and not ref.first.sheet else None
                end = ref.last or ref.first
                incoming = (selected and target_sheet == selected.sheet and target_block == selected.block
                            and (point is None or in_rect(point, (ref.first.col, ref.first.row, end.col, end.row))))
                outgoing = (selected is None or surface.grid is selected) and (
                    point is None or surface.cell and (surface.cell.col, surface.cell.row) == point)
                if incoming or outgoing:
                    rows.append({"owner": surface.location(), "kind": surface.kind,
                                 "expression": surface.expression, "reference": surface.expression[ref.start:ref.end],
                                 "target_sheet": target_sheet, "target_block": target_block,
                                 "target": ref.first.render(prefix=""),
                                 "target_end": ref.last.render(prefix="") if ref.last else None,
                                 "incoming": bool(incoming), "outgoing": bool(outgoing)})
        return {**self.report(), "references": rows, "count": len(rows)}


def in_rect(point, rect):
    return rect[0] <= point[0] <= rect[2] and rect[1] <= point[1] <= rect[3]


def rectangles_intersect(a, b):
    return max(a[0], b[0]) <= min(a[2], b[2]) and max(a[1], b[1]) <= min(a[3], b[3])


def assert_valid(index):
    errors = [d for d in index.diagnostics if d["severity"] == "error"]
    if errors:
        raise TemplateValidationError("模板结构校验未通过", errors, unsupported=index.unsupported)
