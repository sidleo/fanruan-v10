"""基于原始快照的 CPT 行列、区域和 sheet 变换；不联网、不依赖 Java。"""

from bisect import bisect_left, bisect_right
from dataclasses import dataclass
import math
import re

from . import cptxml
from .cptmodel import (DocumentIndex, assert_valid, in_rect, rectangles_intersect)
from .exceptions import ApiError, TemplateValidationError


def conflict(code, message, **location):
    raise TemplateValidationError(message, [{"severity": "error", "code": code,
                                             "message": message, **location}])


class Patches:
    """合并同一标签上的属性改动，按原始区间从后向前应用，防止 offset 失效。"""

    def __init__(self, index):
        self.index, self.attributes, self.content = index, {}, {}
        self.replacements, self.insertions = [], {}

    def attr(self, element, key, value):
        value = str(value)
        if element.attrs.get(key) != value:
            self.attributes.setdefault(element, {})[key] = value

    def text(self, element, value):
        if self.index.value(element) != value:
            self.content[element] = value

    def remove(self, element):
        self.replacements.append((element.open_start, element.close_end, ""))

    def replace(self, element, value):
        self.replacements.append((element.open_start, element.close_end, value))

    def append(self, element, snippets):
        if not snippets:
            return
        if element.empty:
            raw = self.index.text[element.open_start:element.open_end]
            self.replace(element, raw[:-2] + ">" + snippets + "</" + element.name + ">")
        else:
            self.insertions[element.close_start] = self.insertions.get(element.close_start, "") + snippets

    def edits(self):
        roots = []
        for patch in sorted(self.replacements, key=lambda p: (p[0], -p[1])):
            if roots and patch[0] < roots[-1][1]:
                if patch[1] <= roots[-1][1]:
                    continue
                raise ApiError("内部变换区间重叠，拒绝输出")
            roots.append(patch)
        out = list(roots)
        text = self.index.text
        for el, changes in self.attributes.items():
            raw = text[el.open_start:el.open_end]
            for key, value in changes.items():
                raw = cptxml._rewrite_start_tag(raw, key, value)
            out.append((el.open_start, el.open_end, raw))
        for el, value in self.content.items():
            raw = text[el.content_start:el.content_end]
            span = cptxml._cdata_span(raw)
            if span:
                if "]]>" in value:
                    raise ApiError("新公式含 ]]>，不能安全写入 CDATA")
                replacement = raw[:span[0]] + value + raw[span[1]:]
            else:
                replacement = cptxml._escape_xml(value)
            out.append((el.content_start, el.content_end, replacement))
        out.extend((pos, pos, value) for pos, value in self.insertions.items())
        # 被整体删除/替换的元素内部不再应用引用补丁。
        filtered = []
        root_starts = [p[0] for p in roots]
        root_set = set(roots)
        for patch in out:
            pos = bisect_right(root_starts, patch[0]) - 1
            covered = pos >= 0 and roots[pos][0] <= patch[0] and patch[1] <= roots[pos][1]
            if not covered or patch in root_set:
                filtered.append(patch)
        return sorted(filtered, key=lambda p: (p[0], p[1]))

    def prepare(self):
        edits = self.edits()
        return [p[0] for p in edits], edits

    def apply(self, start=0, end=None, prepared=None):
        text = self.index.text
        end = len(text) if end is None else end
        starts, all_edits = prepared or self.prepare()
        edits = [p for p in all_edits[bisect_left(starts, start):bisect_right(starts, end)] if p[1] <= end]
        cursor, chunks = start, []
        for first, last, value in edits:
            if first < cursor:
                raise ApiError("内部补丁区间冲突，拒绝输出")
            chunks.extend((text[cursor:first], value))
            cursor = last
        chunks.append(text[cursor:end])
        return "".join(chunks)


@dataclass
class AxisMap:
    axis: str
    deleted: tuple = ()
    before: int = None
    count: int = 0

    def __post_init__(self):
        self.starts = [a for a, _ in self.deleted]
        self.totals = [0]
        for a, b in self.deleted:
            self.totals.append(self.totals[-1] + b - a + 1)

    def point(self, value):
        pos = bisect_right(self.starts, value) - 1
        if pos >= 0 and value <= self.deleted[pos][1]:
            return None
        shifted = value - self.totals[pos + 1]
        return shifted + (self.count if self.before is not None and value >= self.before else 0)

    def interval(self, first, last):
        if first > last:
            conflict("reversed_range", "区域引用的起止坐标颠倒")
        lo, hi = first, last
        for a, b in self.deleted:
            if a <= lo <= b:
                lo = b + 1
            if a <= hi <= b:
                hi = a - 1
        if lo > hi:
            return None
        return self.point(lo), self.point(hi)


def _axis_number(value, axis):
    raw = str(value).strip()
    if axis == "column":
        if not re.fullmatch(r"[A-Za-z]{1,3}", raw):
            raise ApiError("列范围必须用列字母，例如 C:E")
        return cptxml.parse_a1(raw + "1")[0]
    if not re.fullmatch(r"[1-9][0-9]*", raw):
        raise ApiError("行范围必须用从 1 起的行号，例如 3:5")
    return int(raw) - 1


def axis_ranges(specs, axis):
    spans = []
    for spec in specs:
        parts = str(spec).split(":")
        if len(parts) > 2:
            raise ApiError("行列范围只能写一个坐标或 起始:结束")
        a = _axis_number(parts[0], axis)
        b = _axis_number(parts[-1], axis)
        if b < a:
            raise ApiError("行列范围的结束不能小于起始")
        spans.append((a, b))
    merged = []
    for a, b in sorted(spans):
        if merged and a <= merged[-1][1] + 1:
            merged[-1] = (merged[-1][0], max(b, merged[-1][1]))
        else:
            merged.append((a, b))
    return tuple(merged)


def _known(index, grid, removed=()):
    blockers = []
    for item in index.unsupported:
        if item.get("sheet") is not None and (item["sheet"], item.get("block")) != grid.key:
            # 脚本/动态表达式仍可能引用其他 sheet，不能仅按所在 sheet 排除。
            if item["code"] not in ("script", "dynamic_reference"):
                continue
        if item.get("sheet") == grid.sheet and item.get("block") == grid.block and item.get("at"):
            if any(cptxml.format_a1(int(e.attrs.get("c", "0")), int(e.attrs.get("r", "0"))) == item["at"]
                   for e in removed):
                continue
        blockers.append({"severity": "error", **item,
                         "message": "不能证明该结构在坐标变换后仍正确；需要对应结构的专用处理器"})
    if blockers:
        raise TemplateValidationError("存在尚不能安全联动的结构，未生成修改", blockers,
                                      unsupported=index.unsupported)


def _target(surface, address, selected, inherited=None):
    sheet = address.sheet or inherited
    if sheet is not None:
        return selected.block is None and sheet == selected.sheet
    if surface.grid is None:
        conflict("ambiguous_formula_scope", "工作簿级未限定 sheet 的引用不能确定作用域", **surface.location())
    return surface.grid.key == selected.key


def _write_surface(patches, surface, value):
    if isinstance(surface.attr, tuple):
        c, r = cptxml.parse_a1(value)
        patches.attr(surface.element, surface.attr[0], c)
        patches.attr(surface.element, surface.attr[1], r)
    elif surface.attr:
        patches.attr(surface.element, surface.attr, value)
    else:
        patches.text(surface.element, value)


def _rewrite(surface, mapper):
    text, out, cursor = surface.expression, [], 0
    for ref in surface.refs:
        first, last = mapper(ref)
        value = ref.render(first, last)
        out.extend((text[cursor:ref.start], value))
        cursor = ref.end
    out.append(text[cursor:])
    return "".join(out)


def _axis_refs(index, patches, grid, mapping, removed):
    updates, errors = [], []
    for surface in index.surfaces:
        if surface.cell and surface.cell.element in removed:
            continue
        def mapper(ref):
            addrs = [ref.first] + ([ref.last] if ref.last else [])
            selected = [_target(surface, a, grid, ref.first.sheet) for a in addrs]
            if not any(selected):
                raw = surface.expression[ref.start:ref.end]
                if ref.last:
                    return raw.split(ref.separator, 1)
                return raw, None
            if len(set(selected)) > 1:
                conflict("mixed_scope_range", "区域的两个端点不属于同一坐标作用域", **surface.location())
            coords = [a.col if mapping.axis == "column" else a.row for a in addrs]
            values = mapping.interval(*coords) if ref.last else (mapping.point(coords[0]),)
            if values is None or any(v is None for v in values):
                conflict("deleted_reference", "存活内容仍依赖被删除的坐标", **surface.location(),
                         reference=surface.expression[ref.start:ref.end], kind=surface.kind)
            rendered = []
            for addr, previous, value in zip(addrs, coords, values):
                if previous == value:
                    rendered.append(addr.render())
                else:
                    rendered.append(addr.render(col=value) if mapping.axis == "column" else addr.render(row=value))
            # 无坐标变化时保留 token 的大小写与空白。
            if all(a == b for a, b in zip(coords, values)):
                raw = surface.expression[ref.start:ref.end]
                return raw.split(ref.separator, 1) if ref.last else (raw, None)
            return rendered if ref.last else (rendered[0], None)
        try:
            value = _rewrite(surface, mapper)
        except TemplateValidationError as exc:
            errors.extend(exc.details["diagnostics"])
            continue
        if value != surface.expression:
            updates.append({"owner": surface.location(), "kind": surface.kind,
                            "before": surface.expression, "after": value})
            if not surface.implicit:
                _write_surface(patches, surface, value)
    if errors:
        raise TemplateValidationError("存活内容仍依赖被删除或作用域不明确的坐标", errors)
    return updates


def _nonempty(index, cell):
    o = index.child(cell.element, "O")
    return (o is not None and bool(o.attrs or index.value(o).strip())
            or any(el.name not in ("O", "Expand", "PrivilegeControl") for el in index.children[cell.element]))


def _axis_settings(index, patches, grid, mapping):
    is_col = mapping.axis == "column"
    tag = "ColumnWidth" if is_col else "RowHeight"
    sizes = index.child(grid.element, tag)
    if sizes is not None and not sizes.empty:
        values = [v.strip() for v in index.value(sizes).strip().split(",") if v.strip()]
        new_values = [v for i, v in enumerate(values) if mapping.point(i) is not None]
        if mapping.before is not None and mapping.before < len(values):
            new_values[mapping.before:mapping.before] = [sizes.attrs.get("defaultValue", "0")] * mapping.count
        if values != new_values:
            patches.text(sizes, ",".join(new_values))
    for el in index.descendants(grid.element):
        if el.name in (("HC", "FC") if is_col else ("HR", "FR")) and "F" in el.attrs and "T" in el.attrs:
            span = mapping.interval(int(el.attrs["F"]), int(el.attrs["T"]))
            if span is None:
                patches.replace(el, "<" + el.name + "/>")
            else:
                patches.attr(el, "F", span[0])
                patches.attr(el, "T", span[1])
        elif el.name == "FrozenColumnRow" and "columnrow" in el.attrs:
            parts = el.attrs["columnrow"].split(",")
            if len(parts) != 2:
                conflict("unknown_frozen_region", "无法解释冻结区域", **index.location(el))
            position = 0 if is_col else 1
            count = int(parts[position])
            span = mapping.interval(0, count - 1) if count > 0 else None
            parts[position] = str(span[1] + 1 if span else 0)
            patches.attr(el, "columnrow", ",".join(parts))
        elif el.name == "WorkSheetAttr":
            direction = int(el.attrs.get("direction", "0"))
            primary = (direction == 1) if is_col else (direction == 0)
            keys = ("start", "end") if primary else ("oppoStart", "oppoEnd")
            if any(k in el.attrs for k in keys):
                if not all(k in el.attrs for k in keys):
                    conflict("unknown_split_region", "分栏范围缺少一个端点", **index.location(el))
                lo, hi = (int(el.attrs[k]) for k in keys)
                if lo >= 0 and hi >= lo:
                    span = mapping.interval(lo, hi)
                    for key, value in zip(keys, span or (-1, -1)):
                        patches.attr(el, key, value)
            if primary and el.attrs.get("indexsToCopy"):
                try:
                    values = [int(v) for v in el.attrs["indexsToCopy"].split(",") if v.strip()]
                except ValueError as exc:
                    raise ApiError("无法解释分栏复制标题索引") from exc
                patches.attr(el, "indexsToCopy", ",".join(str(mapping.point(v)) for v in values if mapping.point(v) is not None))
        elif el.name in ("RowPrivilegeControl", "ColumnPrivilegeControl") and (el.attrs or index.children.get(el)):
            conflict("privilege_coordinates", "行列权限含独立坐标，尚不能安全重排", **index.location(el))


def _finish(index, patches, action, changes, updates=()):
    text = patches.apply()
    after = DocumentIndex(text)
    assert_valid(after)
    return text, changes, {**after.report(), "action": action, "reference_updates": list(updates)}


def plan_axis(text, axis, sheet=None, block=None, delete=(), insert_before=None, count=1,
              at=None, size=None, hide=False):
    if axis not in ("row", "column"):
        raise ApiError("axis 只能是 row 或 column")
    index = DocumentIndex(text)
    assert_valid(index)
    grid = index.select(sheet, block)
    if sum((bool(delete), insert_before is not None, size is not None or hide)) != 1:
        raise ApiError("--delete / --insert-before / 尺寸操作必须三选一")
    if at is not None and size is None and not hide:
        raise ApiError("--at 只与尺寸/隐藏操作一起使用")
    if insert_before is None and count != 1:
        raise ApiError("--count 只与 --insert-before 一起使用")
    patches = Patches(index)
    if size is not None or hide:
        return _sizes(index, patches, grid, axis, at, 0 if hide else size)
    if not isinstance(count, int) or count < 1 or count > 100000:
        raise ApiError("--count 必须是 1..100000")
    mapping = AxisMap(axis, axis_ranges(delete, axis),
                      _axis_number(insert_before, axis) if insert_before is not None else None,
                      count if insert_before is not None else 0)
    removed, changes = set(), []
    for cell in grid.cells:
        first = cell.col if axis == "column" else cell.row
        last = first + (cell.cs if axis == "column" else cell.rs) - 1
        span = mapping.interval(first, last)
        if span is None:
            removed.add(cell.element)
            patches.remove(cell.element)
            continue
        if mapping.point(first) is None and _nonempty(index, cell):
            conflict("deleted_merge_anchor", "合并区域仍存在，但主格内容被删除，不能决定内容归属",
                     sheet=grid.sheet, block=grid.block, at=cell.at)
        position, extent = ("c", "cs") if axis == "column" else ("r", "rs")
        patches.attr(cell.element, position, span[0])
        if span[1] - span[0] + 1 != last - first + 1:
            patches.attr(cell.element, extent, span[1] - span[0] + 1)
    _known(index, grid, removed)
    updates = _axis_refs(index, patches, grid, mapping, removed)
    _axis_settings(index, patches, grid, mapping)
    changes.append({"kind": axis + (".delete" if delete else ".insert"), "sheet": grid.sheet,
                    "block": grid.block, "deleted_ranges_zero_based": mapping.deleted,
                    "insert_before_zero_based": mapping.before, "count": mapping.count,
                    "removed_cells": len(removed)})
    result = _finish(index, patches, axis, changes, updates)
    # 沿用自动父格的单元格，变换后必须仍指向同一个逻辑父格。
    _check_implicit(index, DocumentIndex(result[0]), grid, lambda c, r: (
        (mapping.point(c), r) if axis == "column" else (c, mapping.point(r))), removed)
    return result


def _sizes(index, patches, grid, axis, at, size):
    if at is None:
        raise ApiError("尺寸操作需要 --at 范围")
    if not math.isfinite(float(size)) or float(size) < 0:
        raise ApiError("行高/列宽必须是有限的非负数")
    spans = axis_ranges([at], axis)
    lo, hi = spans[0]
    if hi > 1000000:
        raise ApiError("显式尺寸数组最多支持到第 1000001 项")
    tag = "RowHeight" if axis == "row" else "ColumnWidth"
    el = index.child(grid.element, tag)
    if el is None:
        conflict("missing_dimensions", "网格缺少尺寸数组，不能确定默认尺寸", sheet=grid.sheet, block=grid.block)
    default = el.attrs.get("defaultValue", "723900" if axis == "row" else "2743200")
    values = [v.strip() for v in index.value(el).strip().split(",") if v.strip()]
    values.extend([default] * max(0, hi + 1 - len(values)))
    # 与现有导出验证口径一致：行高用磅，列宽用字符。
    unit = cptxml.FU_PER_POINT if axis == "row" else 280800
    values[lo:hi + 1] = [str(round(float(size) * unit))] * (hi - lo + 1)
    if el.empty:
        raw = index.text[el.open_start:el.open_end]
        patches.replace(el, raw[:-2] + "><![CDATA[" + ",".join(values) + "]]></" + tag + ">")
    else:
        patches.text(el, ",".join(values))
    return _finish(index, patches, axis + ".size", [{"kind": axis + ".size", "at": at, "size": size}])


def _check_implicit(before, after, grid, mapper, removed):
    expected = {}
    for surface in before.surfaces:
        if surface.grid is not grid or not surface.implicit or surface.cell.element in removed:
            continue
        own = mapper(surface.cell.col, surface.cell.row)
        target = mapper(surface.refs[0].first.col, surface.refs[0].first.row)
        expected[(own, surface.attr)] = target
    actual_grid = after.select(grid.sheet, grid.block)
    actual = {( (s.cell.col, s.cell.row), s.attr): (s.refs[0].first.col, s.refs[0].first.row)
              for s in after.surfaces if s.grid is actual_grid and s.implicit}
    for (own, side), target in expected.items():
        if actual.get((own, side)) != target:
            conflict("implicit_parent_changed", "变换改变了自动父格的含义，需要显式指定父格后再操作",
                     sheet=grid.sheet, block=grid.block, at=cptxml.format_a1(*own), side=side,
                     expected=cptxml.format_a1(*target) if None not in target else None)
    for (own, side), target in actual.items():
        if (own, side) not in expected:
            old_cell = next((c for c in grid.cells if mapper(c.col, c.row) == own and c.element not in removed), None)
            if old_cell:
                exp = old_cell.expand
                if exp is None or (not exp.attrs.get(side) and exp.attrs.get(side + "ParentDefault") != "false"):
                    conflict("implicit_parent_added", "变换产生新的自动父格，可能改变扩展结果",
                             sheet=grid.sheet, block=grid.block, at=cptxml.format_a1(*own), side=side)


def plan_range(text, at, sheet=None, block=None, copy_to=None, move_to=None,
               clear=False, merge=False, unmerge=False, style=None):
    index = DocumentIndex(text)
    assert_valid(index)
    grid = index.select(sheet, block)
    rect = cptxml.parse_range(at)
    choices = [copy_to is not None, move_to is not None, clear, merge, unmerge, style is not None]
    if sum(bool(c) for c in choices) != 1:
        raise ApiError("区域操作必须给且只给 copy-to / move-to / clear / merge / unmerge / style 之一")
    cells = [c for c in grid.cells if rectangles_intersect(c.rect, rect)]
    for cell in cells:
        if not (in_rect((cell.col, cell.row), rect) and in_rect((cell.rect[2], cell.rect[3]), rect)):
            conflict("partial_merge", "操作范围切开了合并区域", sheet=grid.sheet, block=grid.block, at=cell.at)
    patches = Patches(index)
    source = {c.element for c in cells}
    if style is not None:
        styles = index.direct(index.child(index.elements[0], "StyleList"), "Style")
        if style < 0 or style >= len(styles):
            raise ApiError("区域样式索引不存在")
        for cell in cells:
            patches.attr(cell.element, "s", style)
        # 稀疏区域的空格也要能设置样式，但避免无意生成超大文件。
        if (rect[2] - rect[0] + 1) * (rect[3] - rect[1] + 1) > 100000:
            raise ApiError("一次区域样式最多支持 100000 格")
        occupied = {(c.col, c.row) for c in cells}
        snippets = []
        for r in range(rect[1], rect[3] + 1):
            for c in range(rect[0], rect[2] + 1):
                if (c, r) not in occupied and not any(in_rect((c, r), x.rect) for x in cells if x.cs > 1 or x.rs > 1):
                    snippets.append(cptxml.cell_xml(c, r, value="", style=style))
        if snippets:
            if grid.cells_element is None:
                raise ApiError("网格缺少 CellElementList")
            patches.append(grid.cells_element, "".join(snippets))
        return _finish(index, patches, "range.style", [{"kind": "range.style", "at": at, "style": style}])
    if merge:
        anchor = next((c for c in cells if (c.col, c.row) == rect[:2]), None)
        if any(_nonempty(index, c) for c in cells if c is not anchor):
            conflict("merge_content_loss", "合并区域包含其他非空单元格", sheet=grid.sheet, block=grid.block, at=at)
        for cell in cells:
            if cell is not anchor:
                patches.remove(cell.element)
        cs, rs = rect[2] - rect[0] + 1, rect[3] - rect[1] + 1
        if anchor:
            patches.attr(anchor.element, "cs", cs)
            patches.attr(anchor.element, "rs", rs)
        elif grid.cells_element is not None:
            patches.append(grid.cells_element, cptxml.cell_xml(*rect[:2], value="", cs=cs, rs=rs))
        else:
            raise ApiError("网格缺少 CellElementList")
        return _finish(index, patches, "range.merge", [{"kind": "range.merge", "at": at}])
    if unmerge:
        for cell in cells:
            if cell.cs > 1:
                patches.attr(cell.element, "cs", 1)
            if cell.rs > 1:
                patches.attr(cell.element, "rs", 1)
        return _finish(index, patches, "range.unmerge", [{"kind": "range.unmerge", "at": at}])
    if clear:
        for cell in cells:
            # 清空内容保留格坐标、样式、合并与扩展；引用该格仍然合法。
            o = index.child(cell.element, "O")
            if o:
                patches.replace(o, "<O><![CDATA[]]></O>")
        return _finish(index, patches, "range.clear", [{"kind": "range.clear", "at": at}])
    destination = cptxml.parse_a1(copy_to or move_to)
    dc, dr = destination[0] - rect[0], destination[1] - rect[1]
    target_rect = tuple(v + (dc if i % 2 == 0 else dr) for i, v in enumerate(rect))
    if target_rect[2] > 18277:
        raise ApiError("目标区域越过 ZZZ 列")
    if dc == 0 and dr == 0:
        return _finish(index, patches, "range", [])
    _known(index, grid)
    if copy_to and rectangles_intersect(rect, target_rect):
        conflict("copy_overlap", "复制目标与源区域重叠", sheet=grid.sheet, block=grid.block, at=at)
    for cell in grid.cells:
        if rectangles_intersect(cell.rect, target_rect) and not (move_to and cell.element in source):
            conflict("occupied_destination", "目标区域已有单元格", sheet=grid.sheet, block=grid.block, at=cell.at)
    clones = Patches(index)
    for cell in cells:
        clones.attr(cell.element, "c", cell.col + dc)
        clones.attr(cell.element, "r", cell.row + dr)
    updates = []
    for surface in index.surfaces:
        inside = surface.cell is not None and surface.cell.element in source
        if not move_to and not inside:
            continue
        if copy_to and any(a.value_position for ref in surface.refs for a in (ref.first, ref.last) if a):
            conflict("copy_value_position", "复制含 $Cell 的位置取值公式尚未确证，不能套用 Excel 绝对引用规则", **surface.location())
        def mapper(ref):
            addrs = [ref.first] + ([ref.last] if ref.last else [])
            selected = [_target(surface, a, grid, ref.first.sheet) for a in addrs]
            if move_to and ref.last and all(selected):
                ref_rect = (addrs[0].col, addrs[0].row, addrs[1].col, addrs[1].row)
                if rectangles_intersect(ref_rect, rect) and not (in_rect(ref_rect[:2], rect) and in_rect(ref_rect[2:], rect)):
                    conflict("split_reference_range", "移动会把引用区域拆成不连续范围", **surface.location())
            output = []
            for addr, chosen in zip(addrs, selected):
                c, r = addr.col, addr.row
                if move_to:
                    if chosen and in_rect((c, r), rect):
                        c, r = c + dc, r + dr
                elif inside:
                    if surface.kind in ("parent", "implicit-parent", "coordinate"):
                        if not in_rect((c, r), rect):
                            conflict("external_copy_parent", "复制区域包含区域外父格，需要先明确复制后的父格", **surface.location())
                        c, r = c + dc, r + dr
                    else:
                        c += dc
                        r += dr
                output.append(addr.render(col=c, row=r))
            if all(value == addr.render() for value, addr in zip(output, addrs)):
                raw = surface.expression[ref.start:ref.end]
                return raw.split(ref.separator, 1) if ref.last else (raw, None)
            return output if ref.last else (output[0], None)
        value = _rewrite(surface, mapper)
        if value != surface.expression:
            updates.append({"owner": surface.location(), "kind": surface.kind, "before": surface.expression, "after": value})
            if not surface.implicit:
                _write_surface(clones if inside else patches, surface, value)
    if grid.cells_element is None:
        raise ApiError("网格缺少 CellElementList")
    prepared = clones.prepare()
    snippets = "".join(clones.apply(c.element.open_start, c.element.close_end, prepared) for c in cells)
    patches.append(grid.cells_element, snippets)
    if move_to:
        for cell in cells:
            patches.remove(cell.element)
    result = _finish(index, patches, "range.move" if move_to else "range.copy", [
        {"kind": "range.move" if move_to else "range.copy", "from": at,
         "to": move_to or copy_to, "cells": len(cells)}], updates)
    if move_to:
        _check_implicit(index, DocumentIndex(result[0]), grid,
                        lambda c, r: (c + dc, r + dr) if in_rect((c, r), rect) else (c, r), set())
    else:
        after = DocumentIndex(result[0])
        _check_implicit(index, after, grid, lambda c, r: (c, r), set())
        # 复制得到的隐式父格也必须跟随源区域中的同一逻辑父格。
        new_grid = after.select(grid.sheet, grid.block)
        implicit = {(s.cell.col, s.cell.row, s.attr): s for s in after.surfaces
                    if s.grid is new_grid and s.implicit}
        for s in index.surfaces:
            if s.implicit and s.cell and s.cell.element in source:
                actual = implicit.get((s.cell.col + dc, s.cell.row + dr, s.attr))
                expected = (s.refs[0].first.col + dc, s.refs[0].first.row + dr)
                if not actual or (actual.refs[0].first.col, actual.refs[0].first.row) != expected:
                    conflict("copied_implicit_parent", "复制后的自动父格与源区域不等价", **s.location())
    return result


def plan_sheet(text, name, new_name=None, remove=False):
    index = DocumentIndex(text)
    assert_valid(index)
    if index.sheet_names.count(name) != 1:
        raise ApiError(f"sheet {name!r} 不存在或不唯一")
    if remove and len(index.sheet_names) == 1:
        raise ApiError("不能删除最后一张 sheet")
    if not remove and (not (new_name or "").strip() or new_name in index.sheet_names and new_name != name):
        raise ApiError("新 sheet 名为空或已经存在")
    if not remove and new_name == name:
        return text, [], index.report()
    element = index.sheet_elements[index.sheet_names.index(name)]
    for g in index.grids:
        if g.sheet == name:
            _known(index, g)
    patches = Patches(index)
    if remove:
        patches.remove(element)
    else:
        patches.attr(element, "name", new_name)
    updates = []
    for surface in index.surfaces:
        if remove and element.open_start <= surface.element.open_start < element.close_end:
            continue
        def mapper(ref):
            result = []
            for addr in ([ref.first, ref.last] if ref.last else [ref.first]):
                if addr.sheet == name:
                    if remove:
                        conflict("deleted_sheet_reference", "存活内容引用了要删除的 sheet", **surface.location(), target_sheet=name)
                    quoted = "'" + new_name.replace("'", "''") + "'"
                    sep = addr.prefix[-1]
                    result.append(addr.render(prefix=quoted + sep))
                else:
                    result.append(addr.render())
            raw = surface.expression[ref.start:ref.end]
            if not any(a.sheet == name for a in ([ref.first, ref.last] if ref.last else [ref.first])):
                return raw.split(ref.separator, 1) if ref.last else (raw, None)
            return result if ref.last else (result[0], None)
        value = _rewrite(surface, mapper)
        if value != surface.expression and not surface.implicit:
            _write_surface(patches, surface, value)
            updates.append({"owner": surface.location(), "before": surface.expression, "after": value})
    return _finish(index, patches, "sheet", [{"kind": "sheet.remove" if remove else "sheet.rename",
                                               "name": name, "new_name": new_name}], updates)
