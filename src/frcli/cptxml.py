"""cpt 模板 XML 的结构化读写 —— 只改目标元素，其余字节原样不动。

为什么不直接 `ElementTree.parse` → `tostring`：
cpt 是帆软自有序列化格式，通用 XML 往返会**丢注释、改自闭合写法、把 CDATA 变成转义文本**，
几 MB 的模板会整篇重排，既看不了 diff 也容易踩到服务端不认的写法。所以这里用带状态的
标记扫描器（正确处理注释 / CDATA / 处理指令 / 带引号的属性）定位目标元素的**精确字节区间**，
只替换那一段，其余字节逐字节保留。

结构（实测模板，`references/cpt-xml.md` 有完整层级）：

    <WorkBook>
      <TableDataMap>
        <TableData name="ds1" class="com.fr.data.impl.DBTableData">
          <Parameters>
            <Parameter><Attributes name="date"/><O><![CDATA[]]></O></Parameter>
          </Parameters>
          <Connection class="com.fr.data.impl.NameDatabaseConnection">
            <DatabaseName><![CDATA[conn]]></DatabaseName>
          </Connection>
          <Query><![CDATA[select ...]]></Query>
          <PageQuery><![CDATA[]]></PageQuery>
        </TableData>
      </TableDataMap>
      <Report class="com.fr.report.worksheet.WorkSheet" name="sheet1">…</Report>
      <StyleList>…</StyleList>
    </WorkBook>
"""

import re

from .exceptions import ApiError
from .formulas import check_formula

WORKBOOK_TAG = "WorkBook"


class Element:
    """一个元素的精确字节区间（offsets 均相对整篇文本）。"""

    __slots__ = ("name", "path", "attrs", "open_start", "open_end",
                 "content_start", "content_end", "close_start", "close_end", "empty")

    def __init__(self, name, path, attrs, open_start, open_end,
                 content_start, content_end, close_start, close_end, empty):
        self.name = name
        self.path = path                  # 不含自身的祖先链，如 ('WorkBook', 'TableDataMap')
        self.attrs = attrs
        self.open_start = open_start
        self.open_end = open_end          # 起始标签 `>` 之后
        self.content_start = content_start
        self.content_end = content_end
        self.close_start = close_start    # 结束标签 `<` 的位置（空元素等于 open_end）
        self.close_end = close_end
        self.empty = empty

    @property
    def tag_path(self):
        return self.path + (self.name,)

    def content(self, text: str) -> str:
        return text[self.content_start:self.content_end]

    def text(self, text: str) -> str:
        """元素文本（自动去掉 CDATA 包裹）。"""
        raw = self.content(text)
        span = _cdata_span(raw)
        return raw[span[0]:span[1]] if span else raw

    def __repr__(self):
        return f"<Element {'/'.join(self.tag_path)} @{self.open_start}>"


# ---------------------------------------------------------------------------
# 扫描
# ---------------------------------------------------------------------------
def _cdata_span(raw: str):
    """整段内容恰好是一段 CDATA 时返回 (起, 止)（不含包裹标记），否则 None。"""
    i = raw.find("<![CDATA[")
    if i < 0 or raw[:i].strip():
        return None
    j = raw.find("]]>", i)
    if j < 0 or raw[j + 3:].strip():
        return None
    return i + 9, j


def _scan_tags(text: str):
    """产出 (kind, start, end, raw)；kind ∈ open/close/empty/comment/cdata/pi/decl。"""
    i, n = 0, len(text)
    while i < n:
        lt = text.find("<", i)
        if lt < 0:
            return
        if text.startswith("<!--", lt):
            j = text.find("-->", lt + 4)
            j = n if j < 0 else j + 3
            yield ("comment", lt, j, text[lt:j])
        elif text.startswith("<![CDATA[", lt):
            j = text.find("]]>", lt + 9)
            j = n if j < 0 else j + 3
            yield ("cdata", lt, j, text[lt:j])
        elif text.startswith("<?", lt):
            j = text.find("?>", lt + 2)
            j = n if j < 0 else j + 2
            yield ("pi", lt, j, text[lt:j])
        elif text.startswith("<!", lt):
            j = text.find(">", lt + 2)
            j = n if j < 0 else j + 1
            yield ("decl", lt, j, text[lt:j])
        else:
            j = _tag_end(text, lt)
            if j < 0:
                return
            raw = text[lt:j]
            if raw.startswith("</"):
                kind = "close"
            elif raw.endswith("/>"):
                kind = "empty"
            else:
                kind = "open"
            yield (kind, lt, j, raw)
        i = j


def _tag_end(text: str, lt: int) -> int:
    """找标签的 `>`，跳过引号内的内容（属性值里可能有 `>`）。"""
    quote = None
    for k in range(lt + 1, len(text)):
        ch = text[k]
        if quote:
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch == ">":
            return k + 1
    return -1


def _parse_attrs(raw: str) -> dict:
    """`<Tag a="1" b='2'>` → {'a': '1', 'b': '2'}（保留原值，不做实体解码）。"""
    attrs, k, n = {}, len(raw), len(raw)
    # 跳过 `<name`
    k = 1
    while k < n and raw[k] not in " \t\r\n/>":
        k += 1
    while k < n:
        while k < n and raw[k] in " \t\r\n":
            k += 1
        if k >= n or raw[k] in "/>":
            break
        start = k
        while k < n and raw[k] not in "= \t\r\n/>":
            k += 1
        key = raw[start:k]
        while k < n and raw[k] in " \t\r\n":
            k += 1
        if k < n and raw[k] == "=":
            k += 1
            while k < n and raw[k] in " \t\r\n":
                k += 1
            if k < n and raw[k] in "\"'":
                q = raw[k]
                k += 1
                vstart = k
                while k < n and raw[k] != q:
                    k += 1
                attrs[key] = raw[vstart:k]
                k += 1
            else:
                vstart = k
                while k < n and raw[k] not in " \t\r\n/>":
                    k += 1
                attrs[key] = raw[vstart:k]
        else:
            attrs[key] = ""
    return attrs


def template_tag_name(text: str) -> str:
    """根元素名（跳过 XML 声明 / 注释 / DOCTYPE）。"""
    for kind, _s, _e, raw in _scan_tags(text):
        if kind in ("open", "empty"):
            return raw[1:].split()[0].rstrip("/>").strip()
        if kind == "close":
            return raw[2:].split()[0].strip()
    return ""


def scan(text: str):
    """按文档顺序产出所有元素（含空元素 / 自闭合）。"""
    stack, out = [], []
    for kind, start, end, raw in _scan_tags(text):
        if kind == "open":
            name = raw[1:].split()[0].rstrip("/>")
            stack.append([name, _parse_attrs(raw), start, end])
        elif kind == "empty":
            name = raw[1:].split()[0].rstrip("/>")
            path = tuple(s[0] for s in stack)
            out.append(Element(name, path, _parse_attrs(raw), start, end, end, end, end, end,
                               True))
        elif kind == "close":
            if not stack:
                continue
            name, attrs, ostart, oend = stack.pop()
            path = tuple(s[0] for s in stack)
            out.append(Element(name, path, attrs, ostart, oend, oend, start, start, end,
                               False))
    return out


def find(text: str, name: str, path=None, attrs: dict = None):
    """按标签名（+祖先路径 +属性）找元素。"""
    hits = []
    for el in scan(text):
        if el.name != name:
            continue
        if path is not None and el.path != tuple(path):
            continue
        if attrs and any(el.attrs.get(k) != v for k, v in attrs.items()):
            continue
        hits.append(el)
    return hits


# ---------------------------------------------------------------------------
# 定点替换
# ---------------------------------------------------------------------------
def set_text(text: str, el: Element, value: str) -> str:
    """替换元素内容，CDATA 包裹与前后空白原样保留。"""
    raw = text[el.content_start:el.content_end]
    span = _cdata_span(raw)
    if span and "]]>" in value:
        raise ApiError("新内容含 `]]>`，无法安全放进 CDATA 段")
    if span:
        new_raw = raw[:span[0]] + value + raw[span[1]:]
    else:
        new_raw = _escape_xml(value)
    return text[:el.content_start] + new_raw + text[el.content_end:]


def _escape_xml(value: str) -> str:
    return (value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


# ---------------------------------------------------------------------------
# cpt 语义层
# ---------------------------------------------------------------------------
def table_datas(text: str):
    """所有数据集：name / class / connection / sql / 各元素。"""
    out = []
    for td in find(text, "TableData", path=("WorkBook", "TableDataMap")):
        conn = _first_text(text, td, "Connection/DatabaseName")
        out.append({
            "name": td.attrs.get("name", ""),
            "class": td.attrs.get("class", ""),
            "connection": conn,
            # SQL 保留原始空白：这样 --replace 之后除被替换的子串外**逐字节相同**
            "sql": _raw_text(text, td, "Query"),
            "page_sql": _raw_text(text, td, "PageQuery"),
            "parameters": parameters_of(text, td),
            "element": td,
            "connection_element": _first_child(text, td, "Connection/DatabaseName"),
            "sql_element": _first_child(text, td, "Query"),
            "page_sql_element": _first_child(text, td, "PageQuery"),
        })
    return out


def parameters_of(text: str, td: Element):
    """某数据集声明的参数：name / default（`<O>` 的内容）/ 元素。

    ⚠️ 必须按**位置**限定在 td 的内容区里找：多个 `<TableData>` 的 tag_path 完全相同，
    只按路径匹配会把别的数据集的参数也算进来（每个数据集都报出全部参数）。
    """
    out = []
    for p in _sub_elements(text, td, "Parameter", path=("Parameters",)):
        attrs = _sub_elements(text, p, "Attributes")
        o = _sub_elements(text, p, "O")
        o_el = o[0] if o else None
        out.append({
            "name": attrs[0].attrs.get("name", "") if attrs else "",
            **default_value(text, o_el),
            "element": p,
            "default_element": o_el,
        })
    return out


def _sub_elements(text: str, parent: Element, name: str, path=None):
    """parent 内容区里的后代元素（偏移已换算成全文坐标）。"""
    seg = text[parent.open_end:parent.close_start]
    shift = parent.open_end
    out = []
    for el in find(seg, name, path=path):
        out.append(Element(el.name, el.path, el.attrs,
                           el.open_start + shift, el.open_end + shift,
                           el.content_start + shift, el.content_end + shift,
                           el.close_start + shift, el.close_end + shift, el.empty))
    return out


def _first_child(text: str, parent: Element, rel_path: str):
    """取 parent 下第一条匹配 rel_path 的后代（相对路径相对 parent 的内容区）。"""
    parts = rel_path.split("/")
    seg = text[parent.open_end:parent.close_start]
    hits = find(seg, parts[-1], path=tuple(parts[:-1]))
    if not hits:
        return None
    el = hits[0]
    shift = parent.open_end
    return Element(el.name, el.path, el.attrs, el.open_start + shift, el.open_end + shift,
                   el.content_start + shift, el.content_end + shift,
                   el.close_start + shift, el.close_end + shift, el.empty)


def _first_text(text: str, parent: Element, rel_path: str):
    el = _first_child(text, parent, rel_path)
    return el.text(text).strip() if el else None


def _raw_text(text: str, parent: Element, rel_path: str) -> str:
    """元素文本（去 CDATA 包裹，但**不**去空白），没有时返回空串。"""
    el = _first_child(text, parent, rel_path)
    return el.text(text) if el else ""


#: 数据集 SQL 里的参数引用写法
_PARAM_REF = re.compile(r"\$\{([A-Za-z_][\w.]*)\}")


def sql_parameter_refs(text: str):
    """数据集 SQL 里 `${name}` 引用到的参数名（去重保序）。"""
    names = []
    for td in table_datas(text):
        for m in _PARAM_REF.finditer(td["sql"] or ""):  # noqa: E501
            if m.group(1) not in names:
                names.append(m.group(1))
    return names


def summarize(text: str):
    """模板概览：根元素 / 数据集数 / 参数数（给 `--list` 用）。"""
    tds = table_datas(text)
    return {
        "root": template_tag_name(text),
        "bytes": len(text.encode("utf-8")),
        "datasets": [
            {"name": t["name"], "class": t["class"].rsplit(".", 1)[-1],
             "connection": t["connection"], "sql_chars": len((t["sql"] or "").strip()),
             "parameters": [p["name"] for p in t["parameters"]]}
            for t in tds
        ],
        "sql_parameter_refs": sql_parameter_refs(text),
    }


# ---------------------------------------------------------------------------
# A1 记法（agent 用 `B3`，不用 c/r 数字）
# ---------------------------------------------------------------------------
#: A1 单元格地址：字母列标 + 1 起行号（允许 `$B$3` 这种带绝对引用符的写法）
A1_RE = re.compile(r"^\$?([A-Za-z]{1,3})\$?([1-9][0-9]{0,5})$")


def col_index(letters: str) -> int:
    """`A`→0 / `Z`→25 / `AA`→26。"""
    n = 0
    for ch in letters.strip().upper():
        if not ("A" <= ch <= "Z"):
            raise ApiError(f"列标只能是字母: {letters!r}")
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def col_letters(index: int) -> str:
    """0→`A` / 25→`Z` / 26→`AA`。"""
    if index < 0:
        raise ApiError(f"列序号不能为负: {index}")
    out, n = "", index + 1
    while n:
        n, rem = divmod(n - 1, 26)
        out = chr(65 + rem) + out
    return out


def parse_a1(a1: str):
    """`B3` → (1, 2)：列、行都从 0 开始（内部 c/r 口径）。"""
    m = A1_RE.match(str(a1).strip())
    if not m:
        raise ApiError(f"{a1!r} 不是合法的 A1 单元格地址（应形如 A1 / B3 / AA10）")
    return col_index(m.group(1)), int(m.group(2)) - 1


def format_a1(c: int, r: int) -> str:
    """(1, 2) → `B3`。"""
    return f"{col_letters(c)}{r + 1}"


# ---------------------------------------------------------------------------
# 单元格：解析
# ---------------------------------------------------------------------------
EXPAND_CODES = {"none": None, "v": "0", "h": "1"}
EXPAND_NAMES = {"0": "v", "1": "h"}

DB_TABLE_DATA = "com.fr.data.impl.DBTableData"
FORMULA_CLASS = "com.fr.base.Formula"

# ---------------------------------------------------------------------------
# 数据设置（`<RG>` = RecordGrouper，`RecordGrouper.XML_TAG = "RG"`）
#
# 服务端契约（`com.fr.report.cell.cellattr.core.group.DSColumn`）：
#   getGrouper() 在 grouper == null 时返回 **new FunctionGrouper()**，而
#   FunctionGrouper.divideMode 初值 0（GROUPING_MODE）—— 所以**不写 `<RG>` 就是「分组」**，
#   不是「列表」。这是本项目踩过的最贵的静默坑（见 cpt-features.md §1）。
# ---------------------------------------------------------------------------
GROUPER_PKG = "com.fr.report.cell.cellattr.core.group"
GROUPER_LEGACY_PKG = "com.fr.report.cellElement.core"     # 老模板里的包名，只读要认
FUNCTION_GROUPER = GROUPER_PKG + ".FunctionGrouper"
SUMMARY_GROUPER = GROUPER_PKG + ".SummaryGrouper"
MONO_GROUPER = GROUPER_PKG + ".MonoGrouper"
INDEX_GROUPER = GROUPER_PKG + ".IndexGrouper"
CUSTOM_GROUPER = GROUPER_PKG + ".CustomGrouper"
FUNCTION_PKG = "com.fr.data.util.function"

#: `--mode` 的三个取值 → 实际写出的 Grouper（连续/自定义不进 CLI，只在读取时认出）
DS_MODES = {
    "group": FUNCTION_GROUPER,            # divideMode=0（缺省）
    "list": FUNCTION_GROUPER,             # divideMode=1
    "summary": SUMMARY_GROUPER,
}
DS_MODE_ALIASES = {
    "group": "group", "分组": "group", "grouping": "group",
    "list": "list", "列表": "list",
    "summary": "summary", "汇总": "summary",
}
#: 汇总函数（`<FN>` 里写的就是类全名）；NoneFunction = 不聚合（取原值）
SUMMARY_FUNCTIONS = {
    "sum": "SumFunction",
    "count": "CountFunction",
    "avg": "AverageFunction",
    "max": "MaxFunction",
    "min": "MinFunction",
    "none": "NoneFunction",
}
SUMMARY_FN_ALIASES = {"average": "avg", "mean": "avg", "total": "sum"}
SUMMARY_FN_BY_CLASS = {v: k for k, v in SUMMARY_FUNCTIONS.items()}
#: 只用于展示（`report cell --list`）
DS_MODE_LABELS = {"group": "分组", "list": "列表", "summary": "汇总",
                  "continuum": "连续分组", "custom": "自定义分组",
                  "index": "取第N条", "unknown": "未知"}


def check_ds_mode(mode, fn=None):
    """把 `--mode` 收敛成 group/list/summary，并做本地语义校验（写错就地报错）。"""
    key = DS_MODE_ALIASES.get(str(mode or "").strip().lower())
    if key is None:
        raise ApiError(f"--mode 只能是 group(分组) / list(列表) / summary(汇总)，收到 {mode!r}")
    if fn is not None and key != "summary":
        raise ApiError(f"--fn 只在 --mode summary 时有意义（当前 --mode {key}）；"
                       "分组/列表本身就是「不聚合」的语义")
    return key


def summary_fn_token(name):
    """汇总函数类名 → CLI 记号（`SumFunction` → `sum`）；不认识的返回 None。

    语料里 `<FN>` 只用过 5 个类（Sum/Count/Average/Max/Min），但类本身有 14 个；
    改一张带 `DateFunction` 的老模板时，这个函数让调用方给出人话的报错而不是崩掉。
    """
    if not name:
        return None
    base = str(name).strip().rsplit(".", 1)[-1]
    return SUMMARY_FN_BY_CLASS.get(base)


def check_summary_fn(fn):
    """汇总函数名 → `com.fr.data.util.function.*` 的类名。

    三种写法都收：CLI 记号（`sum`）/ 类名（`SumFunction`）/ 全限定类名。
    """
    raw = str(fn or "").strip()
    key = SUMMARY_FN_ALIASES.get(raw.lower(), raw.lower())
    if key in SUMMARY_FUNCTIONS:
        return SUMMARY_FUNCTIONS[key]
    base = raw.rsplit(".", 1)[-1]
    if base in SUMMARY_FN_BY_CLASS:
        return base
    raise ApiError(f"--fn 只能是 {' / '.join(SUMMARY_FUNCTIONS)}，收到 {fn!r}")


def rg_xml(mode, fn=None) -> str:
    """数据设置的 `<RG>` 片段（三形态；分组模式下 `<Attr>` 被省略，与服务端一致）。"""
    key = check_ds_mode(mode, fn)
    if key == "list":
        return (f'<RG class="{FUNCTION_GROUPER}">\n<Attr divideMode="1"/>\n</RG>')
    if key == "summary":
        return (f'<RG class="{SUMMARY_GROUPER}">\n<FN>\n'
                f"<![CDATA[{FUNCTION_PKG}.{check_summary_fn(fn or 'sum')}]]></FN>\n</RG>")
    return f'<RG class="{FUNCTION_GROUPER}"/>'


def parse_rg(text: str, o_el) -> dict:
    """读一个 `<O t="DSColumn">` 的 `<RG>`，返回 mode/fn/divide_mode/raw_class。

    读的时候**同时认老包名** `com.fr.report.cellElement.core.*`（本地 1602 个官方模板里
    有 343 处 FunctionGrouper / 42 处 SummaryGrouper 是这个老包名）—— 只认新包名会把老模板
    的数据设置读成"没有"，而"没有"在服务端等于分组，改一格就会把它的设置改坏。
    """
    out = {"mode": None, "fn": None, "divide_mode": None, "raw_class": None, "index": None}
    if o_el is None:
        return out
    hits = _sub_elements(text, o_el, "RG", path=())
    rg = hits[0] if hits else None
    if rg is None:                                   # legacy 同义标签 <GC>
        hits = _sub_elements(text, o_el, "GC", path=())
        rg = hits[0] if hits else None
    if rg is None:
        return out
    cls = rg.attrs.get("class", "")
    out["raw_class"] = cls or None
    base = cls.rsplit(".", 1)[-1]
    if base in ("FunctionGrouper", "CustomGrouper"):
        attr = _sub_elements(text, rg, "Attr", path=())
        div = attr[0].attrs.get("divideMode") if attr else None
        try:
            div = int(div) if div is not None else 0
        except ValueError:
            div = None
        out["divide_mode"] = div
        out["mode"] = {0: "group", 1: "list", 2: "continuum", None: "unknown"}.get(div, "unknown")
        if base == "CustomGrouper":
            out["mode"] = "custom"
    elif base == "SummaryGrouper":
        out["mode"] = "summary"
        fns = _sub_elements(text, rg, "FN", path=())
        if fns:
            out["fn"] = fns[0].text(text).strip().rsplit(".", 1)[-1] or None
    elif base == "MonoGrouper":
        out["mode"] = "list"
    elif base == "IndexGrouper":
        out["mode"] = "index"
        attr = _sub_elements(text, rg, "Attr", path=())
        out["index"] = attr[0].attrs.get("index") if attr else None
    else:
        out["mode"] = "unknown"
    return out


def set_grouper(text: str, cell: dict, mode, fn=None) -> str:
    """改**已有**单元格的数据设置：换掉 `<RG>`，没有就按契约顺序插进去。

    插入位置严格照 `DSColumn.writeXML` 的子元素顺序：
    `Attributes → Condition → Complex → RG → SortFormula → Comparator
    → SelectCount → Result → Parameters`
    """
    o = cell.get("o_element")
    if o is None or o.attrs.get("t") != "DSColumn":
        raise ApiError(f"{cell.get('a1', '?')} 不是数据集列单元格（值/公式单元格没有数据设置）")
    snippet = rg_xml(mode, fn)
    hits = _sub_elements(text, o, "RG", path=())
    if not hits:
        hits = _sub_elements(text, o, "GC", path=())
    if hits:
        rg = hits[0]
        return text[:rg.open_start] + snippet + text[rg.close_end:]
    for anchor in ("Complex", "Condition", "Attributes"):
        found = _sub_elements(text, o, anchor, path=())
        if found:
            el = found[0]
            return text[:el.close_end] + "\n" + snippet + text[el.close_end:]
    return text[:o.open_end] + "\n" + snippet + text[o.open_end:]


def sheet_elements(text: str):
    """模板里的所有 sheet（`<Report>`）。"""
    return find(text, "Report", path=("WorkBook",))


def sheet_names(text: str):
    return [el.attrs.get("name", "") for el in sheet_elements(text)]


def pick_sheet(text: str, sheet: str = None) -> Element:
    sheets = sheet_elements(text)
    if not sheets:
        raise ApiError("模板里没有 <Report> 元素，不是可编辑的 cpt 版面")
    if sheet is None:
        return sheets[0]
    for el in sheets:
        if el.attrs.get("name") == sheet:
            return el
    raise ApiError(f"模板里没有名为 {sheet!r} 的 sheet；现有: "
                   f"{', '.join(repr(n) for n in sheet_names(text)) or '(无)'}")


def cell_container(text: str, sheet: str = None):
    """某 sheet 的 `<CellElementList>`（可能不存在 / 是自闭合的）。"""
    report = pick_sheet(text, sheet)
    if report.attrs.get("class", "").rsplit(".", 1)[-1] == "PolyWorkSheet":
        raise ApiError("这是聚合报表（PolyWorkSheet），单元格分布在独立区块中；"
                       "report cell/table 等普通网格操作不支持该版面。"
                       "请先下载原始 CPT，再用 report local-inspect --cells 按区块查看")
    return _first_child(text, report, "CellElementList")


def _first_direct(text: str, parent: Element, name: str):
    hits = _sub_elements(text, parent, name, path=())
    return hits[0] if hits else None


def _expand_name(el) -> str:
    if el is None:
        return "none"
    return EXPAND_NAMES.get(el.attrs.get("dir", ""), "none")


def cells(text: str, sheet: str = None):
    """某 sheet 的全部单元格（按 r,c 排序），自动识别值/公式/数据集列。"""
    container = cell_container(text, sheet)
    if container is None:
        return []
    name = pick_sheet(text, sheet).attrs.get("name", "")
    out = [_cell_info(text, el, name) for el in _sub_elements(text, container, "C")]
    out.sort(key=lambda x: (x["r"], x["c"]))
    return out


def _cell_info(text: str, el: Element, sheet_name: str) -> dict:
    c = _int_attr(el, "c")
    r = _int_attr(el, "r")
    o = _first_direct(text, el, "O")
    expand_el = _first_direct(text, el, "Expand")
    info = {
        "a1": format_a1(c, r), "c": c, "r": r, "sheet": sheet_name,
        "kind": "empty", "text": None, "formula": None,
        "binding": None, "dataset": None, "column": None,
        # 数据设置：只有数据集列格才有；其余为 None（键恒定，消费方不用判存在）
        "ds_mode": None, "ds_fn": None, "ds_mode_explicit": False,
        "ds_result": None, "ds_filter": None,
        "expand": _expand_name(expand_el),
        "expand_element": expand_el,
        "expand_left": None, "expand_up": None,
        "highlights": [], "hl_count": 0,
        "style": el.attrs.get("s"), "cs": el.attrs.get("cs"), "rs": el.attrs.get("rs"),
        "element": el, "o_element": o,
    }
    if expand_el is not None:
        info["expand_left"] = expand_el.attrs.get("left")
        info["expand_up"] = expand_el.attrs.get("up")
    if o is not None:
        info.update(_classify_o(text, o))
    info["highlights"] = parse_highlights(text, el)
    info["hl_count"] = len(info["highlights"])
    info["links"] = parse_hyperlinks(text, el)
    return info


def _classify_o(text: str, o: Element) -> dict:
    cls = o.attrs.get("class", "")
    t = o.attrs.get("t", "")
    if t == "DSColumn":
        attrs = _first_direct(text, o, "Attributes")
        ds = attrs.attrs.get("dsName", "") if attrs else ""
        col = attrs.attrs.get("columnName", "") if attrs else ""
        rg = parse_rg(text, o)
        return {"kind": "ds", "dataset": ds, "column": col,
                "binding": f"{ds}.{col}" if ds or col else None,
                "ds_mode": rg["mode"] or "group",
                "ds_fn": rg["fn"],
                "ds_mode_explicit": rg["mode"] is not None,
                # `<Result>`（本列值再套一层表达式）与 `<Condition>`（本格行过滤）
                "ds_result": _ds_result_of(text, o),
                "ds_filter": _ds_filter_of(text, o)}
    # 官方示例同时存在旧式 t="Formula"/class="Formula" 和新版 XMLable 公式。
    if ((t == "Formula" and cls in ("", "Formula")) or
            cls == FORMULA_CLASS or cls.endswith("." + FORMULA_CLASS)):
        attrs = _first_direct(text, o, "Attributes")
        return {"kind": "formula",
                "formula": (attrs.text(text).strip() if attrs else "")}
    if t or cls:
        return {"kind": "other", "class": cls or t, "text": o.text(text).strip()}
    return {"kind": "value", "text": o.text(text)}


def _int_attr(el: Element, key: str) -> int:
    raw = (el.attrs.get(key) or "0").strip()
    try:
        return int(raw)
    except ValueError:
        raise ApiError(f"<{el.name}> 的 {key} 属性不是整数: {raw!r}")


def find_cell(text: str, at: str, sheet: str = None):
    """按 A1 地址取单元格，没有返回 None。"""
    c, r = parse_a1(at)
    for cell in cells(text, sheet):
        if cell["c"] == c and cell["r"] == r:
            return cell
    return None


def cell_rows(text: str, sheet: str = None):
    """给 `--list` 用的扁平行（去掉内部 Element 引用）。"""
    out = []
    for cell in cells(text, sheet):
        out.append({k: v for k, v in cell.items()
                    if k not in ("element", "o_element", "expand_element")})
    return out


# ---------------------------------------------------------------------------
# 单元格：生成 XML
# ---------------------------------------------------------------------------
def _escape_attr(value: str) -> str:
    return (str(value).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _cdata(value: str, what: str = "内容") -> str:
    value = "" if value is None else str(value)
    if "]]>" in value:
        raise ApiError(f"{what}含 `]]>`，无法安全放进 CDATA 段")
    return value


def o_xml(value: str = None, formula: str = None, binding: str = None,
          ds_mode: str = None, ds_fn: str = None,
          ds_result: str = None, ds_filter: str = None) -> str:
    """`<O>` 值对象：静态文本 / 公式 / 数据集列（三选一）。

    数据集列还要给**数据设置**（`ds_mode`）：分组 / 列表 / 汇总。缺省 `group` ——
    服务端对缺失 `<RG>` 的单元格就是按分组处理（`DSColumn.getGrouper()` null →
    `new FunctionGrouper()`，divideMode=0），所以绝不能省略。

    `ds_result` = `<Result>`（本列值再套一层表达式，`$$$` 是本列原值）；
    `ds_filter` = `<Condition>`（本格按公式过滤行）—— 都只对数据集列有意义，
    子元素顺序照 `DSColumn.readXML` 的契约：`Attributes → Condition → Complex → RG
    → … → Result → Parameters`。
    """
    given = [x for x in (value, formula, binding) if x is not None]
    if len(given) != 1:
        raise ApiError("单元格内容只能给一个：值 / 公式 / 数据集列")
    if value is not None or formula is not None:
        if ds_mode is not None or ds_fn is not None:
            raise ApiError("--set-ds-mode/--fn 只对绑定数据集列的单元格有意义"
                           "（值/公式单元格没有数据设置）")
        if ds_result is not None or ds_filter is not None:
            raise ApiError("--ds-result/--ds-filter 只对绑定数据集列的单元格有意义")
    if value is not None:
        return f"<O>\n<![CDATA[{_cdata(value, '单元格文本')}]]></O>"
    if formula is not None:
        f = formula if formula.startswith("=") else "=" + formula
        return ('<O t="XMLable" class="com.fr.base.Formula">\n<Attributes>\n'
                f"<![CDATA[{_cdata(f, '公式')}]]></Attributes>\n</O>")
    ds, _, col = binding.partition(".")
    if not ds or not col:
        raise ApiError(f"数据集列要写成 数据集名.列名，收到 {binding!r}")
    mode = check_ds_mode(ds_mode or "group", ds_fn)
    parts = ['<O t="DSColumn">',
             f'<Attributes dsName="{_escape_attr(ds)}" columnName="{_escape_attr(col)}"/>']
    if ds_filter is not None:
        parts.append(ds_filter_xml(ds_filter))
    parts.append("<Complex/>")
    parts.append(rg_xml(mode, ds_fn))
    if ds_result is not None:
        parts.append(result_xml(ds_result))
    parts.append("<Parameters/>")
    parts.append("</O>")
    return "\n".join(parts)


def expand_xml(expand: str = None, left: str = None, up: str = None) -> str:
    """扩展方向 + **父格**：`v`=纵向(dir=0) / `h`=横向(dir=1) / `none`=不扩展。

    `left`/`up` 显式指定左父格/上父格（`leftParentDefault="false"` 一起写），
    服务端就按"跟着这个父格重复"渲染 —— 组内小计行/交叉表列头靠它挂到分组上。
    出处：语料 `doc/Primary/DetailReport/条件属性实现折叠树.cpt` 真实写法
    `<Expand dir="0" leftParentDefault="false" left="A2"/>`；属性契约见
    `com.fr.report.cell.cellattr.CellExpandAttr`（`left`/`up`/`leftParentDefault`/`upParentDefault`）。
    """
    key = (expand or "none").strip().lower()
    if key not in EXPAND_CODES:
        raise ApiError(f"扩展方向只能是 v(纵向) / h(横向) / none，收到 {expand!r}")
    code = EXPAND_CODES[key]
    attrs = "" if code is None else f' dir="{code}"'
    if left:
        attrs += f' leftParentDefault="false" left="{_escape_attr(left.upper())}"'
    if up:
        attrs += f' upParentDefault="false" up="{_escape_attr(up.upper())}"'
    return "<Expand/>" if not attrs else f"<Expand{attrs}/>"


def cell_xml(c: int, r: int, value: str = None, formula: str = None, binding: str = None,
             expand: str = None, style=None, cs=None, rs=None, ds_mode: str = None,
             ds_fn: str = None, ds_result: str = None, ds_filter: str = None,
             left: str = None, up: str = None) -> str:
    """一个完整的 `<C>` 元素（新建单元格用；改已有单元格走 replace_o/set_style）。"""
    attrs = f'c="{c}" r="{r}"'
    if cs is not None:
        attrs += f' cs="{_escape_attr(cs)}"'
    if rs is not None:
        attrs += f' rs="{_escape_attr(rs)}"'
    if style is not None:
        attrs += f' s="{_escape_attr(style)}"'
    return (f"<C {attrs}>\n{o_xml(value, formula, binding, ds_mode, ds_fn, ds_result, ds_filter)}\n"
            f"<PrivilegeControl/>\n{expand_xml(expand, left, up)}\n</C>")


# ---------------------------------------------------------------------------
# 单元格：字节级改动
# ---------------------------------------------------------------------------
def set_content(text: str, el: Element, content: str) -> str:
    """整体替换元素内容；空内容会写成自闭合形式（Designer 的写法）。"""
    open_raw = text[el.open_start:el.open_end]
    if el.empty:
        if not content:
            return text
        inner = open_raw[:-2].rstrip() if open_raw.endswith("/>") else open_raw[:-1].rstrip()
        return (text[:el.open_start] + inner + ">" + content
                + f"</{el.name}>" + text[el.open_end:])
    if not content:
        if open_raw.endswith("/>"):
            return text
        return text[:el.open_start] + open_raw[:-1].rstrip() + "/>" + text[el.close_end:]
    return text[:el.content_start] + content + text[el.content_end:]


def append_child(text: str, parent: Element, snippet: str) -> str:
    """把 snippet 追加成 parent 的最后一个子元素（父元素自闭合时自动展开）。"""
    if parent.empty:
        return set_content(text, parent, snippet + "\n")
    return text[:parent.content_end] + snippet + "\n" + text[parent.content_end:]


_ATTR_RE_CACHE = {}


def set_attr(text: str, el: Element, key: str, value) -> str:
    """改元素起始标签上的一个属性（value=None 表示删除）。"""
    raw = text[el.open_start:el.open_end]
    new_raw = _rewrite_start_tag(raw, key, value)
    if new_raw == raw:
        return text
    return text[:el.open_start] + new_raw + text[el.open_end:]


def _rewrite_start_tag(raw: str, key: str, value) -> str:
    closing = "/>" if raw.endswith("/>") else ">"
    body = raw[:-len(closing)]
    pat = _ATTR_RE_CACHE.get(key)
    if pat is None:
        pat = _ATTR_RE_CACHE[key] = re.compile(
            r'(\s' + re.escape(key) + r'\s*=\s*)("(?:[^"]*)"|\'(?:[^\']*)\')')
    m = pat.search(body)
    if value is None:
        return (body[:m.start()] + body[m.end():] + closing) if m else raw
    new_attr = f' {key}="{_escape_attr(value)}"'
    if m:
        body = body[:m.start()] + new_attr + body[m.end():]
    else:
        body = body + new_attr
    return body + closing


def replace_o(text: str, cell: dict, new_o_xml: str) -> str:
    """只换单元格的 `<O>`（保留样式 / 权限 / 扩展 / 高亮等其它子元素）。"""
    c_el = cell["element"]
    o = cell["o_element"]
    if o is not None:
        return text[:o.open_start] + new_o_xml + text[o.close_end:]
    if c_el.empty:
        # 空单元格 `<C c="0" r="0"/>`：补出最小结构
        return set_content(text, c_el, f"\n{new_o_xml}\n<PrivilegeControl/>\n<Expand/>\n")
    return text[:c_el.content_start] + "\n" + new_o_xml + text[c_el.content_start:]


def set_expand(text: str, cell: dict, expand: str, left: str = None, up: str = None) -> str:
    el = cell["expand_element"]
    snippet = expand_xml(expand, left, up)
    if el is None:
        return append_child(text, cell["element"], snippet)
    if el.empty:
        return text[:el.open_start] + snippet + text[el.open_end:]
    return text[:el.open_start] + snippet + text[el.close_end:]


def delete_cell(text: str, cell: dict) -> str:
    """删掉整个 `<C>`（连同它后面那个换行，避免留空行）。"""
    el = cell["element"]
    end = el.close_end
    if text[end:end + 1] == "\n":
        end += 1
    return text[:el.open_start] + text[end:]


def insert_cell_xml(text: str, snippet: str, c: int, r: int, sheet: str = None) -> str:
    """按 (行, 列) 顺序插入一个新单元格（Designer 也是这个顺序）。"""
    sheet_el = pick_sheet(text, sheet)
    container = _first_child(text, sheet_el, "CellElementList")
    if container is None:
        raise ApiError("该 sheet 没有 <CellElementList>，无法插入单元格")
    if container.empty:
        return set_content(text, container, "\n" + snippet + "\n")
    for other in _sub_elements(text, container, "C"):
        oc, orow = _int_attr(other, "c"), _int_attr(other, "r")
        if (orow, oc) > (r, c):
            return text[:other.open_start] + snippet + "\n" + text[other.open_start:]
    return text[:container.content_end] + snippet + "\n" + text[container.content_end:]


def put_cell(text: str, at: str, snippet: str, sheet: str = None):
    """写入一个单元格：已存在则整格替换，不存在则按序插入。返回 (新文本, 变更)。"""
    c, r = parse_a1(at)
    old = find_cell(text, at, sheet)
    if old is None:
        return insert_cell_xml(text, snippet, c, r, sheet), {"action": "insert", "before": None}
    el = old["element"]
    return (text[:el.open_start] + snippet + text[el.close_end:],
            {"action": "replace", "before": text[el.open_start:el.close_end]})


def parse_range(spec: str):
    """`A1:C3` → (c1, r1, c2, r2)（左上 / 右下，0 基）。单格 `A1` 也接受。"""
    parts = str(spec).split(":")
    if len(parts) not in (1, 2):
        raise ApiError(f"区域要写成 A1:C3，收到 {spec!r}")
    c1, r1 = parse_a1(parts[0])
    c2, r2 = parse_a1(parts[-1])
    if c2 < c1 or r2 < r1:
        raise ApiError(f"区域要按「左上:右下」写，收到 {spec!r}")
    return c1, r1, c2, r2


def set_merge(text: str, spec: str, sheet: str = None) -> tuple:
    """合并单元格：把 `cs`/`rs` 写到区域左上角那个 `<C>` 上（FineReport 的存法）。"""
    c1, r1, c2, r2 = parse_range(spec)
    at = format_a1(c1, r1)
    cell = find_cell(text, at, sheet)
    if cell is None:
        raise ApiError(f"{at} 没有单元格：先写内容再合并（合并信息存在左上角格）")
    cs, rs = c2 - c1 + 1, r2 - r1 + 1
    if cs == 1 and rs == 1:
        raise ApiError(f"{spec} 只有一个格子，不需要合并")
    text = set_attr(text, cell["element"], "cs", str(cs) if cs > 1 else None)
    cell = find_cell(text, at, sheet)
    text = set_attr(text, cell["element"], "rs", str(rs) if rs > 1 else None)
    return text, {"kind": "cell.merge", "at": at, "range": spec.upper(),
                  "cols": cs, "rows": rs}


# ---------------------------------------------------------------------------
# 条件属性 `<Highlight>`（`<C>` 的子元素）
#
# 契约（`com.fr.report.cell.cellattr.highlight.AbstractHighlight/DefaultHighlight.readXML|writeXML`）：
#   `<Highlight class="…DefaultHighlight">` → `<Name>` → `<Condition class="…">` → 1..N 个
#   `<HighlightAction class="…">`（动作子元素的类各自决定写什么）。
#   条件用 `com.fr.data.condition.*`（与 DSColumn 过滤同族）；值比较走
#   `com.fr.data.core.Compare`（`op` 常量见下表）。
# 动作类全表来自 jar `com/fr/report/cell/cellattr/highlight/`（12 个可实例化），
# **没有 DataBar/数据条类** —— 数据条是「公式返回 HTML + CellGUIAttr showAsHTML」实现的，
# 见 `references/cpt-patterns.md` 的进度条配方。
# ---------------------------------------------------------------------------
HIGHLIGHT_CLASS = "com.fr.report.cell.cellattr.highlight.DefaultHighlight"
HIGHLIGHT_LEGACY_CLASSES = ("com.fr.report.highlight.DefaultHighlight",)
HIGHLIGHT_ACTION_PKG = "com.fr.report.cell.cellattr.highlight"
CONDITION_PKG = "com.fr.data.condition"

#: 条件类（`DataCoreXmlUtils.writeXMLCondition` 写出的就是这几种）
CONDITION_CLASSES = {
    "object": CONDITION_PKG + ".ObjectCondition",       # 当前值与常量比较
    "formula": CONDITION_PKG + ".FormulaCondition",     # 公式为真
    "list": CONDITION_PKG + ".ListCondition",           # 多个条件 and/or
    "common": CONDITION_PKG + ".CommonCondition",       # 列与列比较
}

#: `com.fr.data.core.Compare` 的 op 常量（反编译实测，勿改）
COMPARE_OPS = {
    "eq": 0, "ne": 1, "gt": 2, "ge": 3, "lt": 4, "le": 5,
    "start": 6, "notstart": 7, "end": 8, "notend": 9,
    "contain": 10, "notcontain": 11, "in": 12, "notin": 13,
    "null": 14, "notnull": 15,
}
COMPARE_ALIASES = {
    "==": "eq", "=": "eq", "!=": "ne", "<>": "ne", ">": "gt", ">=": "ge",
    "<": "lt", "<=": "le", "startswith": "start", "startwith": "start",
    "endswith": "end", "contains": "contain", "isnull": "null", "isnotnull": "notnull",
}
COMPARE_NAMES = {0: "==", 1: "!=", 2: ">", 3: ">=", 4: "<", 5: "<=",
                 6: "以…开始", 7: "不以…开始", 8: "以…结束", 9: "不以…结束",
                 10: "包含", 11: "不包含", 12: "in", 13: "not in",
                 14: "为空", 15: "不为空"}

#: `<HighlightAction class>` 类名 → CLI 记号（读的时候用；写只支持前 5 个）
HIGHLIGHT_ACTION_KINDS = {
    "BackgroundHighlightAction": "bg",
    "ForegroundHighlightAction": "fg",
    "FRFontHighlightAction": "font",
    "RowHeightHighlightAction": "rowheight",
    "ValueHighlightAction": "value",
    "BorderHighlightAction": "border",
    "ColWidthHighlightAction": "colwidth",
    "PaddingHighlightAction": "padding",
    "PageHighlightAction": "page",
    "PresentHighlightAction": "present",
    "HyperlinkHighlightAction": "hyperlink",
    "WidgetHighlightAction": "widget",
}

#: `ROW()%2=0`（隔行变色）这类条件在语料里是最常见写法（FormulaCondition 1405 处）
VALUE_COND_RE = re.compile(r"^\s*v\s*(==|>=|<=|!=|<>|>|<)\s*(.+?)\s*$", re.I)


def check_compare_op(op):
    """`>` / `gt` / `>=` … → `Compare.op` 整数。"""
    raw = str(op or "").strip().lower()
    key = COMPARE_ALIASES.get(raw, raw)
    if key not in COMPARE_OPS:
        names = " / ".join(sorted(set(COMPARE_OPS) - set(COMPARE_ALIASES)))
        aliases = " / ".join(sorted(COMPARE_ALIASES))
        raise ApiError(f"比较符只能是 {names} 或 {aliases}，收到 {op!r}")
    return COMPARE_OPS[key]


def _unquote(value: str) -> str:
    raw = str(value).strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
        return raw[1:-1]
    return raw


def object_condition_xml(op, value=None) -> str:
    """当前值 与 常量 比较（`ObjectCondition` + `<Compare>`）。

    Designer 写的比较值是**没有 `t` 属性的裸 `<O>`**（语料实测：`<Compare op="4"><O><![CDATA[0]]></O>`），
    `op=14/15`（为空 / 不为空）时不带值。
    """
    code = check_compare_op(op)
    if code in (14, 15):                     # 为空 / 不为空：Compare 不带值
        return (f'<Condition class="{CONDITION_CLASSES["object"]}">\n'
                f'<Compare op="{code}"/>\n</Condition>')
    body = f"\n<O>\n<![CDATA[{_cdata(_unquote(value), '条件值')}]]></O>"
    return (f'<Condition class="{CONDITION_CLASSES["object"]}">\n'
            f'<Compare op="{code}">{body}\n</Compare>\n</Condition>')


def formula_condition_xml(expr: str) -> str:
    """公式为真（`FormulaCondition`）；`$$$` = 当前单元格的值。"""
    raw = str(expr or "").strip()
    if raw.startswith("="):
        raw = raw[1:]
    if not raw:
        raise ApiError("条件公式不能为空")
    return (f'<Condition class="{CONDITION_CLASSES["formula"]}">\n'
            f"<Formula>\n<![CDATA[{_cdata(raw, '条件公式')}]]></Formula>\n</Condition>")


def list_condition_xml(conditions, join: str = "and") -> str:
    """多个条件组合（`ListCondition` + `<JoinCondition join="0|1">`，0=and / 1=or）。"""
    code = 1 if str(join).strip().lower() in ("or", "1") else 0
    parts = [f'<Condition class="{CONDITION_CLASSES["list"]}">']
    for cond in conditions:
        parts.append(f'<JoinCondition join="{code}">')
        parts.append(cond.strip())
        parts.append("</JoinCondition>")
    parts.append("</Condition>")
    return "\n".join(parts)


def condition_xml(spec: str) -> str:
    """CLI 条件语法：`v>100` / `v>=0.7` / `v!="-"` → 值比较；其余一律当**公式**。

    判据：以 `v` + 比较符开头才是值比较（`v` 就是"当前单元格的值"），
    所以 `ROW()%2=0`、`$B3>1000`、`len($$$)=0` 都会走公式条件。
    """
    raw = str(spec or "").strip()
    if not raw:
        raise ApiError("条件不能为空（例：`v>100` 或 `ROW()%2=0`）")
    m = VALUE_COND_RE.match(raw)
    if m:
        op, val = m.group(1), _unquote(m.group(2))
        if val.strip().lower() in ("null", "空", "isnull", ""):
            return object_condition_xml("null" if op in ("==", "=") else "notnull")
        return object_condition_xml(op, val)
    return formula_condition_xml(raw)


def highlight_action_xml(spec: str, inherit_size: int = None):
    """一条规则的动作串 → `<HighlightAction>` 片段列表。

    语法（逗号分隔，可任意组合）：
      `bg=#FFC7CE` `fg=#9C0006` `bold` `italic` `size=12` `font=宋体`
      `rowheight=0`（0 = 隐藏整行） `value=公式或空` `border`
    """
    out, font = [], {}
    fg_color = None
    for token in [t.strip() for t in str(spec or "").split(",") if t.strip()]:
        key, _, val = token.partition("=")
        key = key.strip().lower()
        val = val.strip()
        if key in ("bg", "background"):
            out.append(f'<HighlightAction class="{HIGHLIGHT_ACTION_PKG}.BackgroundHighlightAction">'
                       f'\n<Background name="ColorBackground" color="{_color(val)}"/>\n'
                       f"</HighlightAction>")
        elif key in ("fg", "foreground", "color"):
            fg_color = val
        elif key == "bold":
            font["style"] = font.get("style", 0) | 1
        elif key == "italic":
            font["style"] = font.get("style", 0) | 2
        elif key == "size":
            font["size"] = int(round(float(val) * 8))
        elif key == "font":
            font["name"] = val
        elif key in ("rowheight", "row-height", "height"):
            i = _row_height_fu(val)
            body = "" if i <= 0 else f'\n<RowHeight i="{i}"/>'
            out.append(f'<HighlightAction class="{HIGHLIGHT_ACTION_PKG}.RowHeightHighlightAction">'
                       f"{body}\n</HighlightAction>")
        elif key == "value":
            o = "<O>\n<![CDATA[]]></O>" if not val else (
                '<O t="XMLable" class="com.fr.base.Formula">\n<Attributes>\n'
                f"<![CDATA[{_cdata(val if val.startswith('=') else '=' + val, '动作公式')}]]>"
                "</Attributes>\n</O>")
            out.append(f'<HighlightAction class="{HIGHLIGHT_ACTION_PKG}.ValueHighlightAction">'
                       f"\n{o}\n</HighlightAction>")
        elif key == "border":
            out.append(f'<HighlightAction class="{HIGHLIGHT_ACTION_PKG}.BorderHighlightAction">'
                       f'\n<Border topLine="1" topColor="-16777216" bottomLine="1"'
                       f' bottomColor="-16777216" leftLine="1" leftColor="-16777216"'
                       f' rightLine="1" rightColor="-16777216"/>\n</HighlightAction>')
        else:
            raise ApiError(f"不认识的动作 {token!r}；可用: bg=#RRGGBB / fg=#RRGGBB / bold / "
                           "italic / size=N / font=名 / rowheight=N / value=公式 / border")
    if font:
        # ⚠ `FRFontHighlightAction` 写的是**整个 FRFont**，会把单独一条
        # `ForegroundHighlightAction` 设的字色**覆盖回默认**（2026-09 实测：同一规则里
        # `bg=…,fg=…,bold` 导出后字色丢失、只剩加粗）。所以只要同时有字体动作，
        # 字色就必须并进 `<FRFont foreground=…>`，不能再单出一条 Foreground 动作。
        #
        # ⚠⚠ **`size` 不能省**：FRFont 是整体替换，不带 size 时服务端按 **0 号字**处理 ——
        # 值还在 xlsx 里，但**整行看不见**（实测：`--rule 'v>0:bold'` → 导出 size=0.0）。
        # 所以没显式给 size 时继承目标格样式里的字号，再退到 9 磅。
        size = font.get("size") or inherit_size or 72
        attrs = f' name="{_escape_attr(font.get("name", "微软雅黑"))}"'
        attrs += f' style="{font.get("style", 0)}"'
        attrs += f' size="{int(size)}"'
        if fg_color:
            attrs += f' foreground="{_color(fg_color)}"'
        out.append(f'<HighlightAction class="{HIGHLIGHT_ACTION_PKG}.FRFontHighlightAction">'
                   f"\n<FRFont{attrs}/>\n</HighlightAction>")
    elif fg_color:
        out.append(f'<HighlightAction class="{HIGHLIGHT_ACTION_PKG}.ForegroundHighlightAction">'
                   f'\n<Foreground color="{_color(fg_color)}"/>\n</HighlightAction>')
    if not out:
        raise ApiError("规则里没有动作（至少给一个 bg=/fg=/bold/rowheight=…）")
    return out


#: FU ↔ 磅：`RowHeight` 的 `i` 与服务端 `UNIT.toFU()` 同单位（实测 723900 FU = 16.35 磅）
FU_PER_POINT = 44275


def _row_height_fu(value) -> int:
    """行高：`0`=隐藏；`20`/`20pt`=磅；`720000fu`=服务端原始 FU。"""
    raw = str(value).strip().lower()
    if raw.endswith("pt"):
        raw = raw[:-2].strip()
    if raw.endswith("fu"):
        raw = raw[:-2].strip()
        if re.fullmatch(r"-?\d+", raw):
            return int(raw)
        raise ApiError(f"FU 行高必须是整数，收到 {value!r}")
    try:
        return int(round(float(raw) * FU_PER_POINT))
    except ValueError as e:
        raise ApiError(f"行高要写成 `0`（隐藏）/ 磅数（如 20 或 20pt）/ FU（如 720000fu），"
                       f"收到 {value!r}") from e


def cell_font_size(text: str, cell, sheet: str = None) -> int:
    """目标格**当前**的字体字号（XML 单位 = 1/8 磅）；取不到返回 None。

    用于条件属性的字体动作继承 —— FRFont 是整体替换，不带 size 会变成 0 号字（整行不可见）。
    """
    if not cell:
        return None
    idx = cell.get("style")
    if idx is None:
        return None
    try:
        st = styles(text)[int(idx)]        # ⚠ 这里拿到的是字符串 '0'，不能直接当列表下标
    except (IndexError, TypeError, ValueError):
        return None
    m = re.search(r'<FRFont[^>]*\bsize="(\d+)"', st.get("xml") or "")
    return int(m.group(1)) if m else None


def highlight_xml(name: str, condition: str, actions) -> str:
    """一条 `<Highlight>`（条件 + 1..N 个动作）。"""
    acts = actions if isinstance(actions, str) else "\n".join(actions)
    parts = [f'<Highlight class="{HIGHLIGHT_CLASS}">']
    if name:
        parts.append(f"<Name>\n<![CDATA[{_cdata(name, '条件属性名')}]]></Name>")
    parts.append(condition.strip())
    parts.append(acts.strip())
    parts.append("</Highlight>")
    return "\n".join(parts)


def highlight_list_xml(rules, inherit_size: int = None) -> str:
    """一组规则 → `<HighlightList>`。rules = [(条件 spec, 动作 spec, 名字)]。"""
    items = [highlight_xml(name, condition_xml(cond),
                           highlight_action_xml(act, inherit_size=inherit_size))
             for cond, act, name in rules]
    return "<HighlightList>\n" + "\n".join(items) + "\n</HighlightList>"


def parse_condition(text: str, el) -> dict:
    """读一个 `<Condition>`（数据过滤 / 条件属性通用）。"""
    cls = el.attrs.get("class", "")
    base = cls.rsplit(".", 1)[-1] or "?"
    out = {"class": cls or None, "kind": {"ObjectCondition": "object",
                                          "FormulaCondition": "formula",
                                          "ListCondition": "list",
                                          "CommonCondition": "common"}.get(base, base)}
    formulas = _sub_elements(text, el, "Formula", path=())
    if formulas:
        out["formula"] = formulas[0].text(text).strip() or None
    if base == "ObjectCondition":
        cmps = _sub_elements(text, el, "Compare", path=())
        if cmps:
            out.update(_parse_compare(text, cmps[0]))
    elif base == "CommonCondition":
        cmps = _sub_elements(text, el, "Compare", path=())
        if cmps:
            out.update(_parse_compare(text, cmps[0]))
    elif base == "ListCondition":
        subs = []
        for jc in _sub_elements(text, el, "JoinCondition", path=()):
            inner = _sub_elements(text, jc, "Condition", path=())
            subs.append({"join": "or" if jc.attrs.get("join") == "1" else "and",
                         "condition": parse_condition(text, inner[0]) if inner else None})
        out["join_conditions"] = subs
    return out


def _parse_compare(text: str, el) -> dict:
    raw = el.attrs.get("op")
    try:
        code = int(raw) if raw is not None else None
    except ValueError:
        code = None
    vals = _sub_elements(text, el, "O", path=()) or _sub_elements(text, el, "Object", path=())
    return {"op": code, "op_name": COMPARE_NAMES.get(code), "value": vals[0].text(text).strip()
            if vals else None}


def condition_spec(cond: dict) -> str:
    """条件 dict → 人能读的 spec（`v>100` / `formula:…`）。"""
    if not cond:
        return ""
    if cond.get("kind") == "object":
        return f"v{cond.get('op_name') or '?'}{cond.get('value') or ''}"
    if cond.get("kind") == "formula":
        return f"formula:{cond.get('formula')}"
    if cond.get("kind") == "list":
        return " and ".join(f"({condition_spec((jc or {}).get('condition'))})"
                            for jc in cond.get("join_conditions") or [])
    return cond.get("class") or "?"


def _color_hex(value) -> str:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return str(value)
    return "#%06X" % (n & 0xFFFFFF)


def parse_highlights(text: str, cell_el) -> list:
    """读一个 `<C>` 上的全部条件属性（`--list` / 排查用）。"""
    out = []
    lists = _sub_elements(text, cell_el, "HighlightList", path=())
    hl_els = []
    for lst in lists:
        hl_els += _sub_elements(text, lst, "Highlight", path=())
    for hl in hl_els:
        item = {"name": None, "condition": None, "actions": [], "class": hl.attrs.get("class")}
        names = _sub_elements(text, hl, "Name", path=())
        if names:
            item["name"] = names[0].text(text).strip() or None
        conds = _sub_elements(text, hl, "Condition", path=())
        if conds:
            item["condition"] = parse_condition(text, conds[0])
        for act in _sub_elements(text, hl, "HighlightAction", path=()):
            item["actions"].append(_parse_highlight_action(text, act))
        out.append(item)
    return out


def _parse_highlight_action(text: str, act) -> dict:
    cls = act.attrs.get("class", "")
    base = cls.rsplit(".", 1)[-1] or "?"
    info = {"class": cls or None, "kind": HIGHLIGHT_ACTION_KINDS.get(base, base.lower())}
    if base == "BackgroundHighlightAction":
        bg = _sub_elements(text, act, "Background", path=())
        info["bg"] = _color_hex(bg[0].attrs.get("color")) if bg else None
    elif base == "ForegroundHighlightAction":
        fg = _sub_elements(text, act, "Foreground", path=())
        info["fg"] = _color_hex(fg[0].attrs.get("color")) if fg else None
    elif base == "FRFontHighlightAction":
        fs = _sub_elements(text, act, "FRFont", path=())
        if fs:
            f = fs[0]
            style = int(f.attrs.get("style") or 0)
            info.update({"font": f.attrs.get("name"), "bold": bool(style & 1),
                         "italic": bool(style & 2),
                         "size_pt": round(int(f.attrs.get("size") or 0) / 8, 2) or None,
                         "fg": (_color_hex(f.attrs["foreground"])
                                if f.attrs.get("foreground") else None)})
    elif base == "RowHeightHighlightAction":
        rh = _sub_elements(text, act, "RowHeight", path=())
        info["row_height"] = int(rh[0].attrs.get("i") or 0) if rh else 0
        info["hidden"] = info["row_height"] <= 0
    elif base == "ValueHighlightAction":
        os_ = _sub_elements(text, act, "O", path=())
        info["value"] = os_[0].text(text).strip() if os_ else None
    return info


def highlight_action_spec(act: dict) -> str:
    """动作 dict → `bg=#FFC7CE,bold` 这样的 spec（`--list` 用）。"""
    kind = act.get("kind")
    if kind == "bg":
        return f"bg={act.get('bg')}"
    if kind == "fg":
        return f"fg={act.get('fg')}"
    if kind == "font":
        bits = []
        if act.get("bold"):
            bits.append("bold")
        if act.get("italic"):
            bits.append("italic")
        if act.get("size_pt"):
            bits.append(f"size={act['size_pt']}")
        if act.get("fg"):
            bits.append(f"fg={act['fg']}")
        if act.get("font"):
            bits.append(f"font={act['font']}")
        return ",".join(bits) or "font"
    if kind == "rowheight":
        return "rowheight=0(隐藏)" if act.get("hidden") else f"rowheight={act.get('row_height')}"
    if kind == "value":
        return f"value={act.get('value') or ''}"
    return str(kind)


def set_cell_child(text: str, cell: dict, tag: str, snippet: str, order) -> str:
    """替换/插入/删除 `<C>` 的某个子元素（按契约顺序，`snippet` 为空即删除）。"""
    c_el = cell["element"]
    hits = _sub_elements(text, c_el, tag, path=())
    if hits:
        el = hits[0]
        if not snippet:
            return delete_cell_child(text, el)
        return text[:el.open_start] + snippet + text[el.close_end:]
    if not snippet:
        return text
    if c_el.empty:
        open_raw = text[c_el.open_start:c_el.open_end]
        inner = open_raw[:-2].rstrip() if open_raw.endswith("/>") else open_raw[:-1].rstrip()
        return (text[:c_el.open_start] + inner + ">\n" + snippet + "\n</" + c_el.name + ">"
                + text[c_el.open_end:])
    idx = order.index(tag) if tag in order else len(order)
    for child in order[idx + 1:]:
        found = _sub_elements(text, c_el, child, path=())
        if found:
            return text[:found[0].open_start] + snippet + "\n" + text[found[0].open_start:]
    return text[:c_el.content_end] + snippet + "\n" + text[c_el.content_end:]


def delete_cell_child(text: str, el) -> str:
    """删掉 `<C>` 的一个子元素（连它前后的空白一起收掉）。"""
    start, end = el.open_start, el.close_end
    while start > 0 and text[start - 1] in " \t":
        start -= 1
    if text[start:start + 1] == "\n":
        start += 1
    return text[:start] + text[end:]


# ---------------------------------------------------------------------------
# 超链接（`HyperlinkHighlightAction` + `com.fr.js.*Hyperlink`）
#
# 契约（语料 260 处 `com.fr.js.ReportletHyperlink` / 34 处 `WebHyperlink`）：
#   `<HighlightList><Highlight class="…DefaultHighlight"><NameJavaScriptGroup>
#      <NameJavaScript name="超链接1"><JavaScript class="com.fr.js.ReportletHyperlink">
#        <JavaScript class="com.fr.js.ReportletHyperlink">   ← 同名嵌套一层（Designer 就是这么写的）
#          <Parameters>…</Parameters><TargetFrame>_self</TargetFrame>
#          <Features width="600" height="400"/>
#          <ReportletName showPI="true">报表路径</ReportletName>
#        </JavaScript></JavaScript></NameJavaScript></NameJavaScriptGroup>`
#   参数值可以是常量 `<O><![CDATA[v]]></O>`，也可以是公式 `<O t="Formula" class="Formula">`。
# ---------------------------------------------------------------------------
HYPERLINK_PKG = "com.fr.js"
HYPERLINK_TYPES = {
    "reportlet": HYPERLINK_PKG + ".ReportletHyperlink",   # 跳转到另一张报表（钻取）
    "web": HYPERLINK_PKG + ".WebHyperlink",               # 打开网页
    "javascript": HYPERLINK_PKG + ".JavaScriptImpl",      # 执行 JS
}
HYPERLINK_LABELS = {"reportlet": "网络报表", "web": "网页链接", "javascript": "JavaScript"}


def check_hyperlink_type(kind):
    key = str(kind or "reportlet").strip().lower()
    if key not in HYPERLINK_TYPES:
        raise ApiError(f"超链接类型只能是 {' / '.join(HYPERLINK_TYPES)}，收到 {kind!r}")
    return key


def hyperlink_param_xml(name: str, value: str) -> str:
    """一个超链接参数；`value` 以 `=` 开头 ⇒ 写成公式（可引用单元格/参数）。"""
    raw = "" if value is None else str(value)
    if raw.startswith("="):
        o = ('<O t="Formula" class="Formula">\n<Attributes>\n'
             f"<![CDATA[{_cdata(raw, '超链接参数')}]]></Attributes>\n</O>")
    else:
        o = f"<O>\n<![CDATA[{_cdata(raw, '超链接参数')}]]></O>"
    return (f'<Parameter>\n<Attributes name="{_escape_attr(name)}"/>\n{o}\n</Parameter>')


def hyperlink_group_xml(kind: str, target: str, params=(), frame: str = "_self",
                        script: str = None, name: str = "超链接1",
                        inner_only: bool = False) -> str:
    """`<NameJavaScriptGroup>` —— **单元格级超链接的正确形态**（语料 260 处都是这样）。

    它是 `<C>` 的直接子元素（与 `<PrivilegeControl/>`/`<Expand/>` 同级），
    **不是** `<HighlightList><Highlight><HighlightAction>` 那套条件属性形态 ——
    实测后者（不带 `<Condition>` 时）会让整张模板渲染成**平台出错页**（HTTP 200，无 detail）。
    """
    key = check_hyperlink_type(kind)
    cls = HYPERLINK_TYPES[key]
    plist = "\n".join(hyperlink_param_xml(k, v) for k, v in params) if params else ""
    params_xml = f"<Parameters>\n{plist}\n</Parameters>" if plist else "<Parameters/>"
    if key == "reportlet":
        if not target:
            raise ApiError("网络报表跳转要 --to 目标报表路径（如 demo_group/…/明细.cpt）")
        tail = (f'<TargetFrame>\n<![CDATA[{frame}]]></TargetFrame>\n'
                '<Features width="600" height="400"/>\n'
                f'<ReportletName showPI="true">\n<![CDATA[{_cdata(target, "目标报表")}]]>'
                "</ReportletName>")
    elif key == "web":
        if not target:
            raise ApiError("网页链接要 --to URL")
        tail = (f'<TargetFrame>\n<![CDATA[{frame}]]></TargetFrame>\n'
                '<Features width="600" height="400"/>\n'
                f'<URL>\n<![CDATA[{_cdata(target, "URL")}]]></URL>')
    else:
        tail = f'<Content>\n<![CDATA[{_cdata(script or target, "脚本")}]]></Content>'
    inner = (f'<JavaScript class="{cls}">\n{params_xml}\n{tail}\n</JavaScript>')
    js = f'<JavaScript class="{cls}">\n{inner}\n</JavaScript>'
    nj = (f'<NameJavaScript name="{_escape_attr(name)}">\n{js}\n</NameJavaScript>')
    if inner_only:
        return nj
    return f"<NameJavaScriptGroup>\n{nj}\n</NameJavaScriptGroup>"


def hyperlink_action_xml(kind: str, target: str, params=(), frame: str = "_self",
                         script: str = None, name: str = "超链接1") -> str:
    """条件属性形态的 `<HighlightAction class="…HyperlinkHighlightAction">`。

    ⚠ 实测**会渲染成平台出错页**（不带 `<Condition>` 时），只作对照/兼容读取用；
    写超链接请用 `hyperlink_group_xml()`。
    """
    key = check_hyperlink_type(kind)
    cls = HYPERLINK_TYPES[key]
    plist = "\n".join(hyperlink_param_xml(k, v) for k, v in params) if params else ""
    params_xml = f"<Parameters>\n{plist}\n</Parameters>" if plist else "<Parameters/>"
    if key == "reportlet":
        if not target:
            raise ApiError("网络报表跳转要 --to 目标报表路径（如 demo_group/…/明细.cpt）")
        tail = (f'<TargetFrame>\n<![CDATA[{frame}]]></TargetFrame>\n'
                '<Features width="600" height="400"/>\n'
                f'<ReportletName showPI="true">\n<![CDATA[{_cdata(target, "目标报表")}]]>'
                "</ReportletName>")
    elif key == "web":
        if not target:
            raise ApiError("网页链接要 --to URL")
        tail = (f'<TargetFrame>\n<![CDATA[{frame}]]></TargetFrame>\n'
                '<Features width="600" height="400"/>\n'
                f'<URL>\n<![CDATA[{_cdata(target, "URL")}]]></URL>')
    else:
        tail = f'<Content>\n<![CDATA[{_cdata(script or target, "脚本")}]]></Content>'
    inner = (f'<JavaScript class="{cls}">\n{params_xml}\n{tail}\n</JavaScript>')
    return ("<HighlightAction class=\"com.fr.report.cell.cellattr.highlight."
            "HyperlinkHighlightAction\">\n<NameJavaScriptGroup>\n"
            f'<NameJavaScript name="{_escape_attr(name)}">\n'
            f'<JavaScript class="{cls}">\n{inner}\n</JavaScript>\n'
            "</NameJavaScript>\n</NameJavaScriptGroup>\n</HighlightAction>")


def parse_hyperlinks(text: str, cell_el) -> list:
    """读一个 `<C>` 上的超链接（类型/目标/参数/打开方式）。"""
    out = []
    groups = list(_sub_elements(text, cell_el, "NameJavaScriptGroup", path=()))
    for lst in _sub_elements(text, cell_el, "HighlightList", path=()):
        for hl in _sub_elements(text, lst, "Highlight", path=()):
            # ⚠ 条件属性形态：`NameJavaScriptGroup` 挂在 `<HighlightAction>` 下
            for act in _sub_elements(text, hl, "HighlightAction", path=()):
                groups += _sub_elements(text, act, "NameJavaScriptGroup", path=())
    for group in groups:
        for nj in _sub_elements(text, group, "NameJavaScript", path=()):
            js = _first_direct(text, nj, "JavaScript")
            inner = _first_direct(text, js, "JavaScript") if js is not None else None
            el = inner if inner is not None else js
            if el is None:
                continue
            cls = (js.attrs.get("class") or "").rsplit(".", 1)[-1]
            item = {"name": nj.attrs.get("name"), "class": cls,
                    "target": None, "params": [], "frame": None, "script": None}
            for tag, key in (("ReportletName", "target"), ("URL", "target"),
                             ("Content", "script"), ("TargetFrame", "frame")):
                found = _sub_elements(text, el, tag, path=())
                if found:
                    item[key] = found[0].text(text).strip()
            for p in _sub_elements(text, el, "Parameters", path=()):
                for one in _sub_elements(text, p, "Parameter", path=()):
                    at = _first_direct(text, one, "Attributes")
                    o = _first_direct(text, one, "O")
                    val = None
                    if o is not None:
                        inner = _first_direct(text, o, "Attributes")
                        val = (inner.text(text).strip() if inner is not None
                               else o.text(text).strip())
                    item["params"].append({
                        "name": at.attrs.get("name") if at is not None else None,
                        "value": val})
                out.append(item)
    return out


#: `<C>` 的子元素顺序（语料实测：`O → PrivilegeControl → NameJavaScriptGroup → CellGUIAttr
#: → CellPageAttr → Widget → HighlightList → Present → CellInsertPolicy → Expand`）
CELL_CHILD_ORDER = ("O", "PrivilegeControl", "NameJavaScriptGroup", "CellGUIAttr",
                    "CellPageAttr", "Widget", "HighlightList", "Present",
                    "CellInsertPolicy", "Expand")


def set_highlight_list(text: str, cell: dict, snippet: str) -> str:
    return set_cell_child(text, cell, "HighlightList", snippet, CELL_CHILD_ORDER)


def cell_gui_xml(show_as_html: bool = None, tooltip: str = None) -> str:
    """`<CellGUIAttr>`：单元格显示属性。

    `showAsHTML="true"` 是**数据条/进度条**的关键（格子里的公式返回 HTML 片段，
    服务端按 HTML 渲染）—— 出处：官方 `demo/basic/图形化显示进度条.cpt`。
    """
    attrs = ' showAsHTML="true"' if show_as_html else ""
    if tooltip:
        attrs += ' showAsDefault="true"'
        return (f"<CellGUIAttr{attrs}>\n<ToolTipText>\n"
                f"<![CDATA[{_cdata(tooltip, '提示公式')}]]></ToolTipText>\n</CellGUIAttr>")
    return f"<CellGUIAttr{attrs}/>"


def set_cell_gui(text: str, cell: dict, show_as_html: bool = None, tooltip: str = None) -> str:
    if show_as_html is None and tooltip is None:
        return set_cell_child(text, cell, "CellGUIAttr", "", CELL_CHILD_ORDER)
    return set_cell_child(text, cell, "CellGUIAttr",
                          cell_gui_xml(show_as_html, tooltip), CELL_CHILD_ORDER)


# ---------------------------------------------------------------------------
# DSColumn 的 `<Result>` / `<Condition>`（子元素顺序见 set_grouper 的注释）
# ---------------------------------------------------------------------------
DS_CHILD_ORDER = ("Attributes", "Condition", "Complex", "GC", "RG", "SortFormula",
                  "Comparator", "SelectCount", "Result", "Parameters")


def result_xml(expr: str) -> str:
    """`<Result>`：本列值再套一层表达式（`$$$` = 本列原值）。

    例：`FORMAT($$$,'yyyy-MM')`、`ROUND($$$,0)`、`$$$/1000`。
    """
    raw = str(expr or "").strip()
    if raw.startswith("="):
        raw = raw[1:]
    if not raw:
        raise ApiError("--ds-result 的表达式不能为空")
    return f"<Result>\n<![CDATA[{_cdata(raw, 'Result 表达式')}]]></Result>"


def ds_filter_xml(expr: str) -> str:
    """数据集列的**行过滤**（`<Condition class="…FormulaCondition">`，`$$$` = 本列值）。"""
    return formula_condition_xml(expr)


def _ds_child_of(text: str, o_el, name: str):
    hits = _sub_elements(text, o_el, name, path=())
    return hits[0] if hits else None


def _ds_result_of(text: str, o_el):
    el = _ds_child_of(text, o_el, "Result")
    if el is None:
        el = _ds_child_of(text, o_el, "Object") or _ds_child_of(text, o_el, "O")
    return el.text(text).strip() or None if el is not None else None


def _ds_filter_of(text: str, o_el):
    el = _ds_child_of(text, o_el, "Condition")
    return parse_condition(text, el) if el is not None else None


def set_ds_child(text: str, cell: dict, tag: str, snippet: str) -> str:
    """给 `<O t="DSColumn">` 增删 `Condition`/`Result`（按契约顺序插）。"""
    o = cell.get("o_element")
    if o is None or o.attrs.get("t") != "DSColumn":
        raise ApiError(f"{cell.get('a1', '?')} 不是数据集列单元格（--ds-result/--ds-filter "
                       "只对 `--bind 数据集.列` 的格子有意义）")
    hits = _sub_elements(text, o, tag, path=())
    if hits:
        if not snippet:
            return text[:hits[0].open_start] + text[hits[0].close_end:]
        return text[:hits[0].open_start] + snippet + text[hits[0].close_end:]
    if not snippet:
        return text
    idx = DS_CHILD_ORDER.index(tag) if tag in DS_CHILD_ORDER else len(DS_CHILD_ORDER)
    for child in DS_CHILD_ORDER[idx + 1:]:
        found = _sub_elements(text, o, child, path=())
        if found:
            return text[:found[0].open_start] + snippet + "\n" + text[found[0].open_start:]
    return text[:o.content_end] + snippet + "\n" + text[o.content_end:]


def set_ds_result(text: str, cell: dict, expr) -> str:
    return set_ds_child(text, cell, "Result", result_xml(expr) if expr else "")


def set_ds_filter(text: str, cell: dict, expr) -> str:
    snippet = ds_filter_xml(expr) if expr else ""
    return set_ds_child(text, cell, "Condition", snippet)


# ---------------------------------------------------------------------------
# 页眉页脚（`<Header>` / `<Footer>`，含页码）
#
# 契约（Lead 实测 + `docs/探索/cpt服务端模型-逆向.md` §5.8）：
#   `<Header>`/`<Footer>` 是 `<ReportAttrSet>` 里与 `<ReportSettings>` **同级**的兄弟
#   （放错父节点会被静默忽略）；内容分左/中/右三栏 `LeftList/CenterList/RightList`；
#   页码变量是 `$$page_number` / `$$totalPage_number`；**`headerHeight`/`footerHeight` 必须 > 0**，
#   否则写了也不渲染（静默）。HFElement 9 类里语料实际只用 Formula。
#   ⚠ `report image` **不渲染页眉页脚**（它输出版面流）—— 必须 export pdf 后用 pdfium 出图看。
# ---------------------------------------------------------------------------
HF_POSITIONS = {"left": "LeftList", "center": "CenterList", "right": "RightList"}


def header_footer_element(text: str, region: str = "footer", sheet: str = None):
    # ⚠ `<Header>`/`<Footer>` 在 `<ReportAttrSet>` 内（与 `<ReportSettings>` 同级），
    # 不是 `<Report>` 的直接子节点 —— 放错位置会被服务端**静默忽略**（Lead 实测）。
    tag = "Header" if str(region).lower().startswith("h") else "Footer"
    return _first_child(text, pick_sheet(text, sheet), f"ReportAttrSet/{tag}")


def header_footer_content(text: str, region: str = "footer", sheet: str = None) -> list:
    """读页眉/页脚内容（`位置:内容`）。"""
    el = header_footer_element(text, region, sheet)
    out = []
    if el is None:
        return out
    for pos, tag in HF_POSITIONS.items():
        for lst in _sub_elements(text, el, tag, path=()):
            for item in _sub_elements(text, lst, "HFElement", path=()):
                f = _first_direct(text, item, "Formula")
                content = (f.attrs.get("content") if f is not None
                           else item.text(text).strip())
                if content:
                    content = (content.replace("&quot;", '"').replace("&lt;", "<")
                               .replace("&gt;", ">").replace("&amp;", "&"))
                out.append({"position": pos, "class": item.attrs.get("className"),
                            "content": content})
    return out


def set_header_footer(text: str, region: str = "footer", position: str = "center",
                      content: str = None, height_pt: float = None, sheet: str = None):
    """写页眉/页脚内容（公式形式，页码用 `$$page_number` / `$$totalPage_number`）。

    `content=None` ⇒ 清空该栏；`height_pt` 给了就同时把 `headerHeight`/`footerHeight` 写成它
    （**高度为 0 时服务端根本不渲染页脚**，所以这一步不能省）。
    """
    key = str(position).lower()
    if key not in HF_POSITIONS:
        raise ApiError(f"位置只能是 {' / '.join(HF_POSITIONS)}，收到 {position!r}")
    is_head = str(region).lower().startswith("h")
    tag = "Header" if is_head else "Footer"
    attr = "headerHeight" if is_head else "footerHeight"
    st = report_settings(text, sheet)
    if st is None:
        raise ApiError("模板里没有 <ReportAttrSet>/<ReportSettings>")
    changes = []
    if height_pt is not None:
        text = set_attr(text, st, attr, str(int(round(float(height_pt) * FU_PER_POINT))))
        changes.append({"kind": f"page.{attr}", "pt": float(height_pt)})
    el = header_footer_element(text, region, sheet)
    if el is None:
        snippet = ("\n".join([f'<{tag} reportPageType="0">',
                              '<Background name="NullBackground"/>',
                              "<LeftList/>", "<CenterList/>", "<RightList/>", f"</{tag}>"]))
        st = report_settings(text, sheet)
        text = text[:st.close_end] + "\n" + snippet + text[st.close_end:]
        el = header_footer_element(text, region, sheet)
        if el is None:
            raise ApiError(f"插入 <{tag}> 失败（改 XML 注入必须断言成功，否则会得到假结论）")
    lst_tag = HF_POSITIONS[key]
    if content:
        if not is_head and height_pt is None:
            # 页脚高度为 0 = 不渲染：自动补一个可用的默认高度（并在变更里说明）
            cur = page_settings(text, sheet)["footer_height_pt"] or 0
            if cur <= 0:
                st = report_settings(text, sheet)
                text = set_attr(text, st, "footerHeight", str(int(round(20 * FU_PER_POINT))))
                changes.append({"kind": "page.footerHeight", "pt": 20.0,
                                "note": "页脚高度缺省 0 ⇒ 不渲染；已自动补 20 磅"})
                el = header_footer_element(text, region, sheet)
        if is_head:
            cur = page_settings(text, sheet)["header_height_pt"] or 0
            if cur <= 0:
                st = report_settings(text, sheet)
                text = set_attr(text, st, "headerHeight", str(int(round(20 * FU_PER_POINT))))
                changes.append({"kind": "page.headerHeight", "pt": 20.0,
                                "note": "页眉高度缺省 0 ⇒ 不渲染；已自动补 20 磅"})
                el = header_footer_element(text, region, sheet)
        hf = ("\n".join([
            '<HFElement className="com.fr.base.headerfooter.FormulaHFElement">',
            '<FRFont name="SimSun" style="0" size="72"/>',
            f'<Formula content=\'{_escape_attr(content)}\' text="0"/>',
            "</HFElement>"]))
        new_list = f"<{lst_tag}>\n{hf}\n</{lst_tag}>"
    else:
        new_list = f"<{lst_tag}/>"
    lists = _sub_elements(text, el, lst_tag, path=())
    if lists:
        text = text[:lists[0].open_start] + new_list + text[lists[0].close_end:]
    else:
        text = append_child(text, el, new_list)
    changes.append({"kind": f"page.{('header' if is_head else 'footer')}",
                    "position": key, "content": content})
    return text, changes


# ---------------------------------------------------------------------------
# 参数面板控件 `<ParameterUI>` / `<Widget>`（`report widget`）
#
# 契约（`docs/探索/图表与控件模型.md` §B + 语料对照）：
#   `<ParameterUI class="com.fr.form.main.parameter.FormParameterUI">` 是 **WorkBook 级**节点，
#   排在 `<ReportParameterAttr>` 之后；面板容器是
#   `<Layout class="com.fr.form.ui.container.WParameterLayout">`，控件一个个包在
#   `<Widget class="com.fr.form.ui.container.WAbsoluteLayout$BoundsWidget">` 里，
#   内层 `<InnerWidget class="com.fr.form.ui.ComboBox|DateEditor|TextEditor">`。
#   **绑定靠"控件名 = 参数名"**：`<InnerWidget><WidgetName name="X">` 的 X 就是要驱动的模板参数
#    （`com.fr.form.main.parameter.FormParameterUI:260` `getWidgetByName(parameter.getName())`）。
#   默认值写 `<widgetValue><O><![CDATA[…]]></O></widgetValue>`。
# ---------------------------------------------------------------------------
PANEL_CLASS = "com.fr.form.main.parameter.FormParameterUI"
LAYOUT_CLASS = "com.fr.form.ui.container.WParameterLayout"
BOUNDS_CLASS = "com.fr.form.ui.container.WAbsoluteLayout$BoundsWidget"
WIDGET_TYPES = {
    "combo": "com.fr.form.ui.ComboBox",        # 下拉框
    "date": "com.fr.form.ui.DateEditor",       # 日期控件
    "text": "com.fr.form.ui.TextEditor",       # 文本
    "check": "com.fr.form.ui.ComboCheckBox",   # 下拉多选
    "number": "com.fr.form.ui.NumberEditor",   # 数字
}
WIDGET_LABELS = {"combo": "下拉框", "date": "日期", "text": "文本",
                 "check": "下拉多选", "number": "数字"}


def check_widget_type(kind):
    key = str(kind or "combo").strip().lower()
    if key not in WIDGET_TYPES:
        raise ApiError(f"--type 只能是 {' / '.join(WIDGET_TYPES)}，收到 {kind!r}")
    return key


def widget_xml(param: str, kind: str = "combo", options=(), default: str = None,
               label: str = None, x: int = 30, y: int = 20, width: int = 120,
               height: int = 21, default_formula: str = None) -> str:
    """一个参数面板控件（`BoundsWidget` + `InnerWidget`）。"""
    key = check_widget_type(kind)
    cls = WIDGET_TYPES[key]
    body = [f'<Widget class="{BOUNDS_CLASS}">', f'<InnerWidget class="{cls}">',
            f'<WidgetName name="{_escape_attr(param)}"/>',
            f'<LabelName name="{_escape_attr(label or param + ":")}"/>',
            '<WidgetAttr description="">', '<PrivilegeControl/>', "</WidgetAttr>"]
    if key in ("combo", "check") and options:
        body.append('<Dictionary class="com.fr.data.impl.CustomDictionary">')
        body.append("<CustomDictAttr>")
        for opt in options:
            opt = str(opt)
            k, _, v = opt.partition("=")
            body.append(f'<Dict key="{_escape_attr(k)}" value="{_escape_attr(v or k)}"/>')
        body += ["</CustomDictAttr>", "</Dictionary>"]
    if default is not None and default_formula is not None:
        raise ApiError("--default 与 --default-formula 只能给一个")
    if default is not None or default_formula is not None:
        body += ["<widgetValue>", default_object_xml(default, default_formula),
                 "</widgetValue>"]
    body += ["</InnerWidget>", f'<BoundsAttr x="{int(x)}" y="{int(y)}" '
                              f'width="{int(width)}" height="{int(height)}"/>', "</Widget>"]
    return "\n".join(body)


def panel_element(text: str):
    return _first_child(text, find(text, WORKBOOK_TAG)[0], "ParameterUI")


def panel_widgets(text: str) -> list:
    """读参数面板里的控件（参数名 / 控件类 / 选项 / 默认值 / 位置）。"""
    out = []
    panel = panel_element(text)
    if panel is None:
        return out
    # ⚠ 控件挂在 `<Layout>` 下（不是 `<ParameterUI>` 的直接子元素）
    parents = _sub_elements(text, panel, "Layout", path=()) or [panel]
    widgets = []
    for par in parents:
        widgets += _sub_elements(text, par, "Widget", path=())
    for w in widgets:
        inner = _first_direct(text, w, "InnerWidget")
        if inner is None:
            continue
        name = _first_direct(text, inner, "WidgetName")
        bounds = _first_direct(text, w, "BoundsAttr")
        val = _first_direct(text, inner, "widgetValue")
        opts = []
        dic = _first_direct(text, inner, "Dictionary")
        if dic is not None:
            attr = _first_direct(text, dic, "CustomDictAttr")
            if attr is not None:
                opts = [f"{d.attrs.get('key')}={d.attrs.get('value')}"
                        for d in _sub_elements(text, attr, "Dict", path=())]
        o = _first_direct(text, val, "O") if val is not None else None
        defaults = default_value(text, o)
        if o is None and val is not None:
            defaults["default"] = val.text(text).strip()
        item = {"param": name.attrs.get("name") if name is not None else None,
                "class": inner.attrs.get("class", "").rsplit(".", 1)[-1],
                "options": opts, **defaults}
        if bounds is not None:
            item.update({k: bounds.attrs.get(k) for k in ("x", "y", "width", "height")})
        out.append(item)
    return out


def ensure_panel(text: str) -> str:
    """没有参数面板就建一个（放在 `<ReportParameterAttr>` 之后，与 Designer 一致）。"""
    if panel_element(text) is not None:
        return text
    rpa = _first_child(text, find(text, WORKBOOK_TAG)[0], "ReportParameterAttr")
    snippet = "\n".join([
        f'<ParameterUI class="{PANEL_CLASS}">', "<Parameters/>",
        f'<Layout class="{LAYOUT_CLASS}">',
        '<WidgetName name="para"/>', '<WidgetAttr description="">',
        "<PrivilegeControl/>", "</WidgetAttr>",
        '<Margin top="0" left="0" bottom="0" right="0"/>',
        '<Border>', '<border style="0" color="-723724" borderRadius="0" type="0" '
        'borderStyle="0"/>', '<Alpha alpha="1.0"/>', "</Border>",
        '<Background name="ColorBackground" color="-526086"/>',
        '<LCAttr vgap="0" hgap="0" compInterval="0"/>',
        "__WIDGETS__", "</Layout>", "</ParameterUI>"])
    if rpa is not None:
        return text[:rpa.close_end] + snippet + "\n" + text[rpa.close_end:]
    wb = find(text, WORKBOOK_TAG)[0]
    if wb.empty:
        return set_content(text, wb, snippet + "\n")
    return text[:wb.content_end] + snippet + "\n" + text[wb.content_end:]


def add_panel_widget(text: str, param: str, kind: str = "combo", options=(), default=None,
                     label: str = None, x: int = 30, y: int = 20, width: int = 120,
                     height: int = 21, default_formula: str = None):
    """往参数面板加/换一个控件（同名控件会被替换）。"""
    text = ensure_panel(text)
    panel = panel_element(text)
    snippet = widget_xml(param, kind, options, default, label, x, y, width, height,
                         default_formula=default_formula)
    layout = _first_child(text, panel, "Layout")
    existing = panel_widgets(text)
    for item in existing:
        if item["param"] == param:
            # 先删同名的旧控件，再追加（保持顺序简单可预测）
            for w in _sub_elements(text, layout, "Widget", path=()):
                inner = _first_direct(text, w, "InnerWidget")
                nm = _first_direct(text, inner, "WidgetName") if inner is not None else None
                if nm is not None and nm.attrs.get("name") == param:
                    if text[w.open_start:w.close_end] == snippet:
                        return text, {"param": param, "type": kind, "replaced": False,
                                      "options": list(options), "default": default,
                                      "default_formula": default_formula}
                    text = delete_cell_child(text, w)
                    break
            panel = panel_element(text)
            layout = _first_child(text, panel, "Layout")
            break
    if layout is None:
        raise ApiError("参数面板没有 <Layout>，无法加控件")
    text = append_child(text, layout, snippet)
    return text, {"param": param, "type": kind, "replaced": any(
        i["param"] == param for i in existing), "options": list(options), "default": default,
        "default_formula": default_formula}


# ---------------------------------------------------------------------------
# 报表级分页设置（`<ReportAttrSet>`）
#
# 契约（`com.fr.report.stable.ReportSettings.readAttr/readChildNode/writeXML`）：
#   `<ReportSettings headerHeight="FU" footerHeight="FU" ...>`，页眉页脚高度单位是
#   **FU**（`UNIT.toFU()`，`FU_PER_POINT` 换算）；**冻结列**写子元素
#   `<FrozenColumnRow columnrow="列,行"/>`（字段名就是 writeFrozenColumnRow）。
#   页眉页脚内容在**兄弟节点** `<Header reportPageType="0">/<Footer>` 里，各含
#   `LeftList/CenterList/RightList`（本 CLI 只读不写：语料里 1602 个模板的清一色是空列表）。
# 单元格级 `<CellPageAttr>`（`com.fr.report.cell.cellattr.CellPageAttr`）：
#   `pageBeforeRow/pageAfterRow/pageBeforeColumn/pageAfterColumn` = 分页控制；
#   `repeat` **缺省就是 true**（字段初值 63 = 全位），`writeXML` 只在 `!isRepeat()` 时写
#   `repeat="false"` ⇒ **"没写" = 允许重复**（"标签不在 ≠ 设置没有"的又一例）。
# ---------------------------------------------------------------------------
CELL_PAGE_ATTR_ORDER = ("pageAfterColumn", "pageAfterRow", "pageBeforeColumn", "pageBeforeRow",
                        "repeat", "breakOnPaginate")


def report_attr_set(text: str, sheet: str = None):
    return _first_child(text, pick_sheet(text, sheet), "ReportAttrSet")


def report_settings(text: str, sheet: str = None):
    return _first_child(text, pick_sheet(text, sheet), "ReportAttrSet/ReportSettings")


def page_settings(text: str, sheet: str = None) -> dict:
    """读分页设置（页眉页脚高度／冻结／纸张）。"""
    out = {"header_height_pt": None, "footer_height_pt": None, "frozen": None,
           "header": [], "footer": []}
    st = report_settings(text, sheet)
    if st is not None:
        pairs = (("headerHeight", "header_height_pt"),
                 ("footerHeight", "footer_height_pt"))
        for key, name in pairs:
            raw = st.attrs.get(key)
            if raw is not None:
                out[name] = round(int(raw) / FU_PER_POINT, 2)
        fr = _sub_elements(text, st, "FrozenColumnRow", path=())
        if fr:
            out["frozen"] = fr[0].attrs.get("columnrow")
    for region, key in (("header", "header"), ("footer", "footer")):
        out[key] = [f"{c['position']}:{c['content']}"
                    for c in header_footer_content(text, region, sheet)]
    return out


def set_page_settings(text: str, sheet: str = None, header_height_pt=None,
                      footer_height_pt=None, frozen=None):
    """写分页设置：页眉/页脚高度（磅）、冻结列行（`列数,行数`）。"""
    changes = []
    st = report_settings(text, sheet)
    if st is None:
        raise ApiError("模板里没有 <ReportAttrSet>/<ReportSettings>（不是可编辑的 cpt 版面）")
    if header_height_pt is not None:
        fu = int(round(float(header_height_pt) * FU_PER_POINT))
        text = set_attr(text, st, "headerHeight", str(fu))
        changes.append({"kind": "page.header-height", "pt": float(header_height_pt)})
        st = report_settings(text, sheet)
    if footer_height_pt is not None:
        fu = int(round(float(footer_height_pt) * FU_PER_POINT))
        text = set_attr(text, st, "footerHeight", str(fu))
        changes.append({"kind": "page.footer-height", "pt": float(footer_height_pt)})
        st = report_settings(text, sheet)
    if frozen is not None:
        snippet = "" if frozen in ("", "none", None) else (
            f'<FrozenColumnRow columnrow="{_escape_attr(frozen)}"/>')
        hits = _sub_elements(text, st, "FrozenColumnRow", path=())
        if hits:
            text = ((text[:hits[0].open_start] + snippet + text[hits[0].close_end:])
                    if snippet else (text[:hits[0].open_start] + text[hits[0].close_end:]))
        elif snippet:
            text = append_child(text, st, snippet)
        changes.append({"kind": "page.frozen-columnrow", "value": frozen or None})
    return text, changes


#: `<ReportPageAttr>` 的四个重复区域子元素（0 基、闭区间 F..T）
PAGE_REGION_TAGS = {"HR": "重复标题行", "FR": "重复表尾行",
                    "HC": "重复标题列", "FC": "重复表尾列"}


def report_page_attr(text: str, sheet: str = None):
    """`<ReportPageAttr>`（`com.fr.page.stable.ReportPageAttr`）：重复标题行/表尾 + 页面冻结。"""
    return _first_child(text, pick_sheet(text, sheet), "ReportPageAttr")


def page_regions(text: str, sheet: str = None) -> dict:
    """读四个重复区域 + 页面冻结开关（`UPFCR`）。"""
    out = {"HR": None, "FR": None, "HC": None, "FC": None, "page_freeze": None}
    el = report_page_attr(text, sheet)
    if el is None:
        return out
    for tag in PAGE_REGION_TAGS:
        hits = _sub_elements(text, el, tag, path=())
        if hits:
            f, t = hits[0].attrs.get("F"), hits[0].attrs.get("T")
            out[tag] = (int(f), int(t)) if f is not None and t is not None else None
    up = _sub_elements(text, el, "UPFCR", path=())
    if up:
        out["page_freeze"] = (up[0].attrs.get("COLUMN", "false").lower() == "true",
                              up[0].attrs.get("ROW", "false").lower() == "true")
    return out


def _parse_span(spec):
    """`1:2` / `1` / `none` → (F, T) 或 None（清空）。"""
    raw = str(spec).strip().lower()
    if raw in ("", "none", "off", "-"):
        return None
    parts = raw.replace("-", ":").split(":")
    try:
        f = int(parts[0])
        t = int(parts[1]) if len(parts) > 1 and parts[1] != "" else f
    except ValueError as e:
        raise ApiError(f"重复区域要写成 `起始:结束`（0 基闭区间，如 1:2），收到 {spec!r}") from e
    if f < 0 or t < f:
        raise ApiError(f"重复区域的起止不对：{spec!r}（要 0 <= 起始 <= 结束）")
    return f, t


def set_repeat_region(text: str, tag: str, spec, sheet: str = None):
    """写 `<HR F T/>`（或 FR/HC/FC）—— **这才是"每页重复标题行"**。

    出处：`com.fr.page.stable.ReportPageAttr.readXML`（属性名就是 `F`/`T`）+
    `PaginateReportPageGenerator.paginate_according_to_repeat`。语料里全是自闭合
    `<HR/>`（= 不重复），带属性的写法 Designer 里很少开。
    """
    if tag not in PAGE_REGION_TAGS:
        raise ApiError(f"未知的重复区域 {tag!r}")
    el = report_page_attr(text, sheet)
    if el is None:
        raise ApiError("模板里没有 <ReportPageAttr>，无法写重复标题行")
    span = _parse_span(spec)
    snippet = f"<{tag}/>" if span is None else f'<{tag} F="{span[0]}" T="{span[1]}"/>'
    hits = _sub_elements(text, el, tag, path=())
    if hits:
        text = text[:hits[0].open_start] + snippet + text[hits[0].close_end:]
    else:
        text = append_child(text, el, snippet)
    return text, {"kind": f"page.repeat-{tag.lower()}",
                  "region": PAGE_REGION_TAGS[tag], "from": span[0] if span else None,
                  "to": span[1] if span else None}


def set_page_freeze(text: str, value, sheet: str = None):
    """`<UPFCR COLUMN="true" ROW="true"/>` = **启用**页面冻结（预览态滚动交互；导出态无差异）。"""
    el = report_page_attr(text, sheet)
    if el is None:
        raise ApiError("模板里没有 <ReportPageAttr>，无法写页面冻结")
    on = str(value).strip().lower() not in ("", "none", "off", "false", "0")
    snippet = f'<UPFCR COLUMN="{"true" if on else "false"}" ROW="{"true" if on else "false"}"/>'
    hits = _sub_elements(text, el, "UPFCR", path=())
    if hits:
        text = text[:hits[0].open_start] + snippet + text[hits[0].close_end:]
    else:
        text = append_child(text, el, snippet)
    return text, {"kind": "page.freeze", "enabled": on}


def cell_page_attr_spec(text: str, cell: dict) -> dict:
    el = _first_direct(text, cell["element"], "CellPageAttr")
    if el is None:
        return {"present": False, "repeat": True}
    out = {"present": True, "repeat": el.attrs.get("repeat", "true") != "false"}
    for key in ("pageBeforeRow", "pageAfterRow", "pageBeforeColumn", "pageAfterColumn",
                "breakOnPaginate"):
        out[key] = el.attrs.get(key)
    return out


def set_cell_page_attr(text: str, cell: dict, repeat=None) -> str:
    """写单元格级 `<CellPageAttr>`（目前只支持 `repeat`）。

    服务端语义：**缺省 = 允许重复**（`CellPageAttr.value` 初值 63），
    `repeat="false"` 才是关闭 —— 所以"重复标题行"这件事是**默认开着**的。
    """
    if repeat is None:
        return text
    snippet = "<CellPageAttr/>" if repeat else '<CellPageAttr repeat="false"/>'
    return set_cell_child(text, cell, "CellPageAttr", snippet, CELL_CHILD_ORDER)


# ---------------------------------------------------------------------------
# 数据集：生成 / 增删
# ---------------------------------------------------------------------------
def dataset_xml(name: str, conn: str, sql: str, params=(), page_sql: str = "",
                share: bool = True) -> str:
    """一个 `<TableData>`（数据库数据集）。

    params: `["date"]` 或 `[("date", "20260101")]` —— 名 + 可选默认值（空 = 无默认值）。
    """
    if not name or not name.strip():
        raise ApiError("数据集名不能为空")
    if not conn or not conn.strip():
        raise ApiError("数据连接名不能为空（用 `frcli report serverdatasets` 看可用的）")
    out = [f'<TableData name="{_escape_attr(name)}" class="{DB_TABLE_DATA}">']
    plist = [_param_pair(p) for p in params]
    if plist:
        out.append("<Parameters>")
        for pname, pdef in plist:
            out += ["<Parameter>", f'<Attributes name="{_escape_attr(pname)}"/>',
                    "<O>", f"<![CDATA[{_cdata(pdef, '参数默认值')}]]></O>", "</Parameter>"]
        out.append("</Parameters>")
    else:
        out.append("<Parameters/>")
    share_attr = 'share="true" ' if share else ""
    out.append(f'<Attributes {share_attr}maxMemRowCount="-1"/>')
    out += ['<Connection class="com.fr.data.impl.NameDatabaseConnection">',
            "<DatabaseName>", f"<![CDATA[{_cdata(conn, '连接名')}]]></DatabaseName>",
            "</Connection>",
            "<Query>", f"<![CDATA[{_cdata(sql, 'SQL')}]]></Query>",
            "<PageQuery>", f"<![CDATA[{_cdata(page_sql, '分页 SQL')}]]></PageQuery>",
            "</TableData>"]
    return "\n".join(out)


def _param_pair(p):
    if isinstance(p, (tuple, list)):
        return str(p[0]), ("" if len(p) < 2 or p[1] is None else str(p[1]))
    name, sep, default = str(p).partition("=")
    return name.strip(), (default if sep else "")


def table_data_map(text: str) -> Element:
    el = _first_child(text, find(text, WORKBOOK_TAG)[0], "TableDataMap")
    if el is None:
        raise ApiError("模板里没有 <TableDataMap>，不是可编辑的 cpt")
    return el


def dataset_names(text: str):
    return [t["name"] for t in table_datas(text)]


def add_dataset(text: str, xml: str, name: str) -> str:
    if name in dataset_names(text):
        raise ApiError(f"模板里已经有数据集 {name!r}；改名或先 --remove")
    parent = table_data_map(text)
    if parent.empty:
        return set_content(text, parent, xml + "\n")
    return text[:parent.content_end] + xml + "\n" + text[parent.content_end:]


def remove_dataset(text: str, name: str) -> str:
    hit = [t for t in table_datas(text) if t["name"] == name]
    if not hit:
        raise ApiError(f"模板里没有数据集 {name!r}；现有: "
                       f"{', '.join(dataset_names(text)) or '(无)'}")
    el = hit[0]["element"]
    end = el.close_end
    if text[end:end + 1] == "\n":
        end += 1
    return text[:el.open_start] + text[end:]


# ---------------------------------------------------------------------------
# 样式
# ---------------------------------------------------------------------------
def styles(text: str):
    """`<StyleList>` 里的样式（索引就是单元格 `s=` 引用的值）。"""
    el = _first_child(text, find(text, WORKBOOK_TAG)[0], "StyleList")
    if el is None:
        return []
    out = []
    for i, st in enumerate(_sub_elements(text, el, "Style")):
        fmt = _first_direct(text, st, "Format")
        font = _first_direct(text, st, "FRFont")
        out.append({
            "index": i,
            "format": fmt.text(text).strip() if fmt else None,
            "font": (f"{font.attrs.get('name', '')} {font.attrs.get('size', '')}"
                     if font else None),
            "bold": (font.attrs.get("style", "0") not in ("", "0") if font else None),
            "align": st.attrs.get("horizontal_alignment"),
            "xml": text[st.open_start:st.close_end],
        })
    return out


def style_list_element(text: str) -> Element:
    el = _first_child(text, find(text, WORKBOOK_TAG)[0], "StyleList")
    if el is None:
        raise ApiError("模板里没有 <StyleList>")
    return el


def _normalize_xml_fragment(fragment: str) -> str:
    """把片段归一化成可比较的规范形式。

    本模块刻意不引入 ElementTree（重排序列化会动到原文件字节），所以归一化只做
    无风险的文本处理：标签间空白折叠、属性名排序。
    """
    t = re.sub(r">\s+<", "><", fragment.strip())
    t = re.sub(r"\s+", " ", t)

    def sort_attrs(m):
        name, body = m.group(1), m.group(2)
        attrs = re.findall(r'([\w:-]+)="([^"]*)"', body)
        attrs.sort()
        tail = "/>" if m.group(0).endswith("/>") else ">"
        return "<" + name + "".join(f' {k}="{v}"' for k, v in attrs) + tail

    return re.sub(r'<(\w+)((?:\s+[\w:-]+="[^"]*")*)\s*/?>', sort_attrs, t)


def append_style(text: str, style_xml: str) -> tuple:
    """往 `<StyleList>` 追加一个 `<Style>`，返回 (新文本, 新样式索引)。

    **先复用已有的等价样式**：`--num-format` 这类命令的语义是"造一个样式并绑上"，
    若每次调用都无条件追加，反复跑同一份配方会让 `<StyleList>` 无限膨胀
    （实测连跑 3 次：5 → 6 → 7 → 8 条），既撑肥模板又让"内容是否变化"永远为真、
    幂等失效。所以在追加前先按**归一化 XML** 找一个一模一样的，命中就复用它的索引。
    """
    snippet = style_xml.strip()
    if not re.match(r"^<Style[ >/]", snippet):
        raise ApiError("样式片段必须以 <Style ...> 开头")
    if not snippet.endswith("</Style>") and not snippet.endswith("/>"):
        raise ApiError("样式片段必须以 </Style> 结尾")
    target = _normalize_xml_fragment(snippet)
    if target:
        for st in styles(text):
            if _normalize_xml_fragment(st["xml"]) == target:
                return text, st["index"]
    parent = style_list_element(text)
    index = len(styles(text))
    return append_child(text, parent, snippet), index


# 样式片段的搭法（实测过的写法，见 references/cpt-authoring.md「样式与数字格式」）
BORDER_ALL = ('<Border>\n<Top style="1"/>\n<Bottom style="1"/>\n'
              '<Left style="1"/>\n<Right style="1"/>\n</Border>')
BORDER_NONE = "<Border/>"


def style_xml(fmt: str = None, bold: bool = False, size_pt: float = 9,
              fg: str = None, bg: str = None, align: str = None,
              border: bool = False, font: str = "微软雅黑") -> str:
    """生成一段 `<Style>`（数字格式 / 粗体 / 字号 / 字色 / 底色 / 对齐 / 四边框）。

    * `fmt`：Excel 风格数字格式（`#,##0` / `#0.0%` / `0.00` …），给 None 则不写 `<Format>`
    * `size_pt`：磅；XML 里存的是 1/8 磅（9 磅 → `72`）
    * `fg`/`bg`：`#RRGGBB`（`#808080` → `-8355712`，即 `0xRRGGBB - 0x1000000`）
    * `align`：`left` / `center` / `right`（`horizontal_alignment` 0/1/2）
    """
    parts = []
    if fmt:
        parts.append(f'<Format class="com.fr.base.CoreDecimalFormat" roundingMode="6">'
                     f"<![CDATA[{_cdata(fmt, '数字格式')}]]></Format>")
    fg_attr = f' foreground="{_color(fg)}"' if fg else ""
    parts.append(f'<FRFont name="{_escape_attr(font)}" style="{1 if bold else 0}" '
                 f'size="{int(round(float(size_pt) * 8))}"{fg_attr}/>')
    parts.append(f'<Background name="{"ColorBackground" if bg else "NullBackground"}"'
                 + (f' color="{_color(bg)}"' if bg else "") + "/>")
    parts.append(BORDER_ALL if border else BORDER_NONE)
    attrs = ""
    if align:
        if align not in ALIGN_CODES:
            raise ApiError(f"对齐方式只能是 {'/'.join(ALIGN_CODES)}，收到 {align!r}")
        attrs += f' horizontal_alignment="{ALIGN_CODES[align]}"'
    return f'<Style{attrs} imageLayout="1">\n' + "\n".join(parts) + "</Style>"


#: `<Style horizontal_alignment>`：0=居中 / 2=左 / 4=右（**奇数被忽略**，与直觉相反）
ALIGN_CODES = {"center": "0", "left": "2", "right": "4"}


def _color(value: str) -> int:
    """`#RRGGBB`（或 `RRGGBB` / 十进制）→ FineReport 的带符号整数颜色。

    白色 `#FFFFFF` → `-1`（补码），`#000000` → `-16777216`。
    """
    raw = str(value).strip()
    if re.fullmatch(r"#?[0-9A-Fa-f]{6}", raw):
        # FineReport 存的是 24 位色的补码：白 #FFFFFF → -1，黑 #000000 → -16777216，
        # 浅灰 #EEEEEE → -1118482（真实模板里就是这么存的）
        return int(raw.lstrip("#"), 16) - 0x1000000
    if re.fullmatch(r"-?\d+", raw):
        return int(raw)
    raise ApiError(f"颜色要写成 #RRGGBB 或十进制整数，收到 {value!r}")


# ---------------------------------------------------------------------------
# 模板参数（`ReportParameterAttr > Parameters`）
# ---------------------------------------------------------------------------
def parameter_attr_element(text: str) -> Element:
    el = _first_child(text, find(text, WORKBOOK_TAG)[0], "ReportParameterAttr")
    if el is None:
        raise ApiError("模板里没有 <ReportParameterAttr>，无法登记模板参数")
    return el


def template_parameters(text: str):
    """模板参数（单元格公式里 `$x` 用的是这些；只写在数据集里不够）。"""
    try:
        parent = parameter_attr_element(text)
    except ApiError:
        return []
    params_el = _first_direct(text, parent, "Parameters")
    if params_el is None:
        return []
    out = []
    for p in _sub_elements(text, params_el, "Parameter", path=()):
        attrs = _first_direct(text, p, "Attributes")
        o = _first_direct(text, p, "O")
        defaults = default_value(text, o)
        if o is None:
            defaults["default"] = ""
        out.append({"name": attrs.attrs.get("name", "") if attrs else "",
                    **defaults,
                    "element": p, "default_element": o})
    return out


def default_value(text: str, o: Element) -> dict:
    """还原默认值的类型；公式正文位于 O/Attributes，不能读取整段内部 XML。"""
    if o is None:
        return {"default": None, "default_type": "value"}
    info = _classify_o(text, o)
    formula = info.get("kind") == "formula"
    return {"default": info.get("formula") if formula else o.text(text),
            "default_type": "formula" if formula else "value"}


def default_object_xml(default: str = None, formula: str = None) -> str:
    """静态字面量与公式显式区分；以等号开头的静态值仍是文本。"""
    if default is not None and formula is not None:
        raise ApiError("静态默认值与公式默认值只能给一个")
    if formula is not None:
        return o_xml(formula=check_formula(formula))
    return o_xml(value=default or "")


def set_default_value(text: str, parent: Element, default: str = None,
                      formula: str = None) -> tuple:
    """只改目标父元素的直接 O 子节点，保留同名参数的其他作用域。"""
    snippet = default_object_xml(default, formula)
    desired = {"default": check_formula(formula) if formula is not None else (default or ""),
               "default_type": "formula" if formula is not None else "value"}
    o = _first_direct(text, parent, "O")
    if o is not None and default_value(text, o) == desired:
        return text, "unchanged"
    if o is None:
        return append_child(text, parent, snippet), "default-updated"
    return text[:o.open_start] + snippet + text[o.close_end:], "default-updated"


def add_template_parameter(text: str, name: str, default: str = None,
                           formula: str = None) -> tuple:
    """登记一个模板参数（已存在则只改默认值），返回 (新文本, 动作)。"""
    name = (name or "").strip()
    if not name:
        raise ApiError("模板参数名不能为空")
    exists = [p for p in template_parameters(text) if p["name"] == name]
    if exists:
        return set_default_value(text, exists[0]["element"], default, formula)
    snippet = ("<Parameter>\n"
               f'<Attributes name="{_escape_attr(name)}"/>\n'
               f"{default_object_xml(default, formula)}\n</Parameter>")
    parent = parameter_attr_element(text)
    params_el = _first_direct(text, parent, "Parameters")
    if params_el is None:
        return append_child(text, parent, f"<Parameters>\n{snippet}\n</Parameters>"), "added"
    return append_child(text, params_el, snippet), "added"


def remove_template_parameter(text: str, name: str) -> tuple:
    hit = [p for p in template_parameters(text) if p["name"] == name]
    if not hit:
        raise ApiError(f"模板里没有参数 {name!r}；现有: "
                       f"{', '.join(p['name'] for p in template_parameters(text)) or '(无)'}")
    el = hit[0]["element"]
    end = el.close_end
    if text[end:end + 1] == "\n":
        end += 1
    return text[:el.open_start] + text[end:], "removed"


# ---------------------------------------------------------------------------
# 本地语义校验（服务端对这些**全都静默接受**：坏 dsName / 坏公式 / 越界样式
# 照样上传成功、导出成功，只是内容是空的 —— 能查的必须在这里查掉）
# ---------------------------------------------------------------------------
#: 数据集 SQL 里的 `${x}` 与单元格公式里的 `$x` 是两套写法，写错都不报错
SQL_PARAM_REF = re.compile(r"\$\{([A-Za-z_][\w.]*)\}")
SQL_PARAM_BARE = re.compile(r"\$(?!\{)([A-Za-z_]\w*)")
#: 单元格公式里的 `$x`（排除 `$A1` / `$A$1` 这类单元格绝对引用）
FORMULA_PARAM_REF = re.compile(r"\$(?![A-Za-z]{1,3}\$?\d)([A-Za-z_]\w*)")

def formula_signature(expr: str):
    """公式的（半定量的）静态特征：引用的参数名、是否误写 `${x}`。"""
    text = expr or ""
    return {
        "params": list(dict.fromkeys(FORMULA_PARAM_REF.findall(text))),
        "brace_ref": "${" in text,
    }


def sql_signature(sql: str):
    """SQL 的静态特征：`${x}` 引用、误写的裸 `$x`。"""
    text = sql or ""
    return {
        "params": list(dict.fromkeys(SQL_PARAM_REF.findall(text))),
        "bare": list(dict.fromkeys(SQL_PARAM_BARE.findall(text))),
    }


def add_dataset_parameter(text: str, dataset: str, name: str, default: str = "") -> tuple:
    """给已有数据集补一个 `<Parameter>`（已存在则改默认值）。"""
    hit = [t for t in table_datas(text) if t["name"] == dataset]
    if not hit:
        raise ApiError(f"模板里没有数据集 {dataset!r}；现有: "
                       f"{', '.join(dataset_names(text)) or '(无)'}")
    td = hit[0]
    for p in td["parameters"]:
        if p["name"] == name:
            el = p["default_element"]
            if el is None or (p["default"] or "") == (default or ""):
                return text, "unchanged"
            return set_text(text, el, default or ""), "default-updated"
    snippet = ("<Parameter>\n"
               f'<Attributes name="{_escape_attr(name)}"/>\n'
               f"<O>\n<![CDATA[{_cdata(default, '参数默认值')}]]></O>\n</Parameter>")
    params_el = _first_child(text, td["element"], "Parameters")
    if params_el is None:
        el = td["element"]
        body = f"<Parameters>\n{snippet}\n</Parameters>\n"
        if el.empty:
            return set_content(text, el, body), "added"
        return text[:el.content_start] + body + text[el.content_start:], "added"
    if params_el.empty:
        return set_content(text, params_el, "\n" + snippet + "\n"), "added"
    return append_child(text, params_el, snippet), "added"


def check_style_index(text: str, style, what: str = "--style"):
    """`s=` 越界：服务端不报错，只是样式静默丢失（渲染出没样式的格子）。"""
    if style is None:
        return
    n = len(styles(text))
    i = int(style)
    if i < 0 or i >= n:
        raise ApiError(f"{what} 给的样式索引 {i} 越界：模板 <StyleList> 里只有 {n} 个样式"
                       f"（0..{n - 1}）。先用 `report style --add` 加一个，"
                       "或 `report style --list` 看现有的。")


# ---------------------------------------------------------------------------
# 空白模板骨架
# ---------------------------------------------------------------------------
#: 最少可渲染模板：`<TableDataMap/>` + 空 `<CellElementList>` + 版面外壳。
#: 实测（2026-09，本服务器）导出 xlsx/pdf 均不报错，见 tests/test_cptwrite.py 的离线断言。
SKELETON_TEMPLATE_ID = "6f0eb9f2-5fe3-47eb-9207-54fcf74fe73c"

SKELETON = "\n".join([
    "<?xml version=\"1.0\" encoding=\"UTF-8\"?>",
    "<WorkBook xmlVersion=\"20211223\" releaseVersion=\"10.0.0\">",
    "<TableDataMap/>",
    "<Report class=\"com.fr.report.worksheet.WorkSheet\" name=\"{sheet}\">",
    "<ReportPageAttr>",
    "<HR/>",
    "<FR/>",
    "<HC/>",
    "<FC/>",
    "</ReportPageAttr>",
    "<ColumnPrivilegeControl/>",
    "<RowPrivilegeControl/>",
    "<RowHeight defaultValue=\"723900\">",
    "<![CDATA[{row_heights}]]></RowHeight>",
    "<ColumnWidth defaultValue=\"2743200\">",
    "<![CDATA[{col_widths}]]></ColumnWidth>",
    "<CellElementList/>",
    "<ReportAttrSet>",
    "<ReportSettings headerHeight=\"0\" footerHeight=\"0\">",
    "<PaperSetting/>",
    "<Background name=\"ColorBackground\" color=\"-1\"/>",
    "</ReportSettings>",
    "</ReportAttrSet>",
    "<PrivilegeControl/>",
    "</Report>",
    "<ReportParameterAttr>",
    "<Attributes showWindow=\"true\" delayPlaying=\"true\""
    " windowPosition=\"1\" align=\"0\" useParamsTemplate=\"true\""
    " currentIndex=\"0\"/>",
    "<PWTitle>",
    "<![CDATA[参数]]></PWTitle>",
    "</ReportParameterAttr>",
    "<StyleList/>",
    "<DesignerVersion DesignerVersion=\"KAA\"/>",
    "<PreviewType PreviewType=\"0\"/>",
    "<StrategyConfigsAttr"
    " class=\"com.fr.esd.core.strategy.persistence.StrategyConfigsAttr\""
    " pluginID=\"com.fr.plugin.esd\" plugin-version=\"1.8.4\">",
    "<StrategyConfigs/>",
    "</StrategyConfigsAttr>",
    "<TemplateCloudInfoAttrMark"
    " class=\"com.fr.plugin.cloud.analytics.attr.TemplateInfoAttrMark\""
    " pluginID=\"com.fr.plugin.cloud.analytics.v10\""
    " plugin-version=\"2.14.0.20230222\">",
    "<TemplateCloudInfoAttrMark createTime=\"{create_time}\"/>",
    "</TemplateCloudInfoAttrMark>",
    "<TemplateIdAttMark class=\"com.fr.base.iofile.attr.TemplateIdAttrMark\">",
    "<TemplateIdAttMark TemplateId=\"{template_id}\"/>",
    "</TemplateIdAttMark>",
    "</WorkBook>",
]) + "\n"

ROW_HEIGHT = 723900
COL_WIDTH = 2743200
SKELETON_ROWS = 50
SKELETON_COLS = 22


def empty_skeleton(sheet: str = "sheet1", template_id: str = None,
                   create_time: int = None) -> str:
    """从零生成一个空白可渲染模板（`<TableDataMap/>` + 空 `<CellElementList>`）。"""
    import time as _time
    import uuid as _uuid
    return SKELETON.format(
        sheet=_escape_attr(sheet or "sheet1"),
        row_heights=",".join([str(ROW_HEIGHT)] * SKELETON_ROWS),
        col_widths=",".join([str(COL_WIDTH)] * SKELETON_COLS),
        create_time=create_time if create_time is not None else int(_time.time() * 1000),
        template_id=template_id or str(_uuid.uuid4()))


def strip_to_skeleton(text: str, sheet: str = None, template_id: str = None) -> str:
    """把一个真实模板裁成空白骨架：清空**所有 sheet** 的单元格 + `<TableDataMap>` +
    模板参数声明，版面外壳（页边距 / 行高列宽 / 样式表 / 打印设置 / 多 sheet 结构）原样保留。

    `sheet` 给的是**新模板第一个 sheet 的名字**：重名就选它，不重名就把第一个改名。
    """
    if template_tag_name(text) != WORKBOOK_TAG:
        raise ApiError(f"根元素不是 <{WORKBOOK_TAG}>，不能当模板骨架")
    root = find(text, WORKBOOK_TAG)
    tdm = _first_child(text, root[0], "TableDataMap")
    if tdm is None:
        raise ApiError("模板里没有 <TableDataMap>")
    text = set_content(text, tdm, "")
    for name in sheet_names(text):
        report = pick_sheet(text, name)
        cel = _first_child(text, report, "CellElementList")
        if cel is not None:
            text = set_content(text, cel, "")
    text = _set_sheet_name(text, sheet)
    text = _clear_template_parameters(text)
    return _set_template_id(text, template_id)


def _clear_template_parameters(text: str) -> str:
    """清空模板参数声明（骨架不继承源模板的参数；元素本身保留）。"""
    try:
        parent = parameter_attr_element(text)
    except ApiError:
        return text
    params_el = _first_direct(text, parent, "Parameters")
    if params_el is None:
        return text
    return set_content(text, params_el, "")


def _set_sheet_name(text: str, sheet: str) -> str:
    if not sheet:
        return text
    el = pick_sheet(text, None)
    return set_attr(text, el, "name", sheet)


def _set_template_id(text: str, template_id: str) -> str:
    if not template_id:
        return text
    hits = [el for el in find(text, "TemplateIdAttMark")
            if el.attrs.get("TemplateId")]
    if not hits:
        return text
    return set_attr(text, hits[0], "TemplateId", template_id)


# ---------------------------------------------------------------------------
# 列宽 / 行高（P11：以前只能 download → 改字节 → upload）
# ---------------------------------------------------------------------------
EMU_PER_CHAR = 280800     # 实测：ColumnWidth 值 ÷ 280800 = 导出后的列宽字符数


def set_col_widths(text: str, widths, default_chars: float = None, sheet: str = None):
    """改写 `<ColumnWidth>` 的 CDATA 数组。

    widths: {列下标(0起): 列宽字符数}；default_chars 给定时同时改 defaultValue。
    支持自闭合与带 CDATA 两种写法（真实模板两种都有）。
    `sheet` 给定时只改**该 sheet** 的 `<ColumnWidth>`（每张 sheet 各有一份，见 `add_sheet`）；
    两条路径都走**元素解析**（`<Report>` 的直接子元素），不认单元格文本里的字面 XML；
    不给 `sheet` 时取**第一个带它的 `<Report>`**（正常模板每张都有 ⇒ 第一张），
    没有 `<Report>` 的简化模板退到 `<WorkBook>` 的直接子元素。
    """
    import re as _re
    pat = _re.compile(r"<ColumnWidth([^>]*?)(?:/>|>\s*(?:<!\[CDATA\[(.*?)\]\]>)?\s*</ColumnWidth>)",
                      _re.S)
    if sheet is None:
        cw = None
        for holder in find(text, "Report") + find(text, WORKBOOK_TAG)[:1]:
            cw = _first_child(text, holder, "ColumnWidth")
            if cw is not None:
                break
    else:
        cw = _first_child(text, pick_sheet(text, sheet), "ColumnWidth")
    m = pat.match(text, cw.open_start, cw.close_end) if cw is not None else None
    if not m:
        where = "模板里" if sheet is None else f"sheet {sheet!r} 里"
        raise ApiError(f"{where}没有 <ColumnWidth>，无法设置列宽")
    attrs = m.group(1)
    cdata = (m.group(2) or "").strip()
    # defaultValue 保留原值（或按参数改）
    dv = _re.search(r'defaultValue="(\d+)"', attrs)
    dv = str(int(round(default_chars * EMU_PER_CHAR))) if default_chars else \
        (dv.group(1) if dv else str(COL_WIDTH))
    arr = [x for x in cdata.split(",") if x.strip()] or []
    size = max(len(arr), (max(widths) + 1) if widths else 0)
    arr = [x if x.strip() else str(dv) for x in arr] + [str(dv)] * (size - len(arr))
    for i, ch in widths.items():
        if i < 0:
            raise ApiError(f"列下标不能为负: {i}")
        if ch <= 0:
            raise ApiError(f"列宽必须是正数（单位=字符数）: {ch}")
        arr[i] = str(int(round(ch * EMU_PER_CHAR)))
    new = (f'<ColumnWidth defaultValue="{dv}">\n'
           f"<![CDATA[{','.join(arr)}]]></ColumnWidth>")
    return text[:m.start()] + new + text[m.end():]


# ---------------------------------------------------------------------------
# sheet（工作簿里的 `<Report class="WorkSheet">`）
# ---------------------------------------------------------------------------
def add_sheet(text: str, name: str, clone_from: str = None) -> tuple:
    """给模板追加一张 sheet，返回 (新文本, 新 sheet 名)。

    做法：**克隆已有 sheet 的骨架**（页面设置/行列尺寸/样式引用都在里面），只把
    `<CellElementList>` 清空、改掉 `name`。这样新 sheet 的纸张与列宽跟原表一致，
    不会出现"新 sheet 是空白 A4、原表是横向大纸张"的错配。

    2026-09 需求来源：另一个会话要给已有 .cpt 加一个「口径说明」页，当时只能
    手工把 `<Report>` 块拼进 XML —— 这里补上这条能力。
    """
    import re as _re
    name = (name or "").strip()
    if not name:
        raise ApiError("sheet 名不能为空")
    if name in sheet_names(text):
        raise ApiError(f"sheet {name!r} 已存在；现有: {', '.join(sheet_names(text))}")
    sheets = sheet_elements(text)
    if not sheets:
        raise ApiError("模板里没有 <Report> sheet，不是可编辑的 cpt 版面")
    src = None
    if clone_from:
        for el in sheets:
            if (el.attrs.get("name") or "").strip() == clone_from:
                src = el; break
        if src is None:
            raise ApiError(f"找不到要克隆的 sheet {clone_from!r}；现有: "
                           f"{', '.join(sheet_names(text))}")
    else:
        src = sheets[0]
    block = text[src.open_start:src.close_end]
    # 改 name（只在 `<Report ...>` 开标签上改，别碰单元格内容）
    m = _re.search(r"<Report\b[^>]*>", block)
    if not m:
        raise ApiError("克隆源里没找到 <Report> 开标签")
    head = m.group(0)
    if 'name="' in head:
        new_head = _re.sub(r'name="[^"]*"', f'name="{_escape_attr(name)}"', head, count=1)
    else:
        new_head = head[:-1] + f' name="{_escape_attr(name)}">'
    block = new_head + block[m.end():]
    # 清空单元格
    block = _re.sub(r"(<CellElementList\s*>).*?(</CellElementList>)",
                    r"\1\2", block, count=1, flags=_re.S)
    if "<CellElementList" not in block:
        block = block.replace("</Report>", "<CellElementList></CellElementList></Report>", 1)
    insert_at = sheets[-1].close_end
    return text[:insert_at] + "\n" + block + text[insert_at:], name


def remove_sheet(text: str, name: str) -> str:
    if len(sheet_names(text)) <= 1:
        raise ApiError("只剩一张 sheet，不能删（模板至少要有一张）")
    for el in sheet_elements(text):
        if (el.attrs.get("name") or "").strip() == name:
            return text[:el.open_start] + text[el.close_end:]
    raise ApiError(f"找不到 sheet {name!r}；现有: {', '.join(sheet_names(text))}")


def rename_sheet(text: str, old: str, new: str) -> str:
    import re as _re
    new = (new or "").strip()
    if not new:
        raise ApiError("新 sheet 名不能为空")
    if new in sheet_names(text):
        raise ApiError(f"sheet {new!r} 已存在")
    for el in sheet_elements(text):
        if (el.attrs.get("name") or "").strip() == old:
            block = text[el.open_start:el.close_end]
            m = _re.search(r"<Report\b[^>]*>", block)
            head = m.group(0)
            head2 = (_re.sub(r'name="[^"]*"', f'name="{_escape_attr(new)}"', head, count=1)
                     if 'name="' in head else head[:-1] + f' name="{_escape_attr(new)}">')
            return text[:el.open_start] + head2 + block[m.end():] + text[el.close_end:]
    raise ApiError(f"找不到 sheet {old!r}；现有: {', '.join(sheet_names(text))}")
