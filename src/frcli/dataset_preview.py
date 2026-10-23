"""数据集预览（等价于 Designer 里右键数据集 →「预览」）。

原理：远程设计 RPC `com.fr.data.operator.DataOperatorProvider.previewTableData(TableData, Map, int)`
在服务端真实执行数据集查询并返回 `EmbeddedTableData`（列名/类型/行）。参数是 Java 对象，
所以这里用一份**由平台自身序列化产生的 DBTableData 骨架**（`DBTableData(NameDatabaseConnection, sql)`
的 JDK 序列化字节），运行时只替换其中的连接名/SQL 两个字符串（Java 序列化是自描述的，调整
长度前缀即可，不需要重新构造对象图）。

结果 XML 里 `<RowData>` 是 ASCII85(zipDeflate(行文本))：行以 `\\n` 分隔、列以 `\\t` 分隔，
null 写成空串；字符串里的 `\\t`/`\\n` 会被转义成 `&t;`/`&n;`。

限制（与 Designer 行为对齐）：
- 只支持**SQL 数据集**（有连接名 + SQL）；服务器数据集/存储过程/内建数据集不支持。
- 数据集 SQL 里的 `${x}` 是**文本替换**：这里在客户端按 `--params`（未给出的报错）替换后再执行，
  与平台在服务端替换语义一致；不要用预览命令执行有写副作用的 SQL。
"""

import base64
import re
import struct
import zlib

from . import jser
from .exceptions import ApiError

#: 平台 `DBTableData(new NameDatabaseConnection(conn), sql)` 的 JDK 序列化骨架
#: （FineReport 10.0.0；由平台自身 ObjectOutputStream 生成，两个标记串运行时替换）
_TABLE_DATA_SKELETON = base64.b64decode(
    "rO0ABXNyABxjb20uZnIuZGF0YS5pbXBsLkRCVGFibGVEYXRh/vfH5D6H+q4CAAZMABJkYXRhUXVl"
    "cnlQcm9jZXNzb3J0ABtMY29tL2ZyL2NvbmZpZy9ob2xkZXIvQ29uZjtMAAhkYXRhYmFzZXEAfgAB"
    "TAAObWF4TWVtUm93Q291bnRxAH4AAUwADHBhZ2VRdWVyeVNxbHEAfgABTAAFcXVlcnlxAH4AAUwA"
    "BXNoYXJlcQB+AAF4cgAmY29tLmZyLmRhdGEuQWJzdHJhY3RQYXJhbWV0ZXJUYWJsZURhdGFhYwLj"
    "C8eDegIAAUwACnBhcmFtZXRlcnN0ACpMY29tL2ZyL2NvbmZpZy9ob2xkZXIvaW1wbC94bWwvWG1s"
    "Q29sQ29uZjt4cgAdY29tLmZyLmJhc2UuQWJzdHJhY3RUYWJsZURhdGH6RJ5mCw8S2gIAAHhyAB1j"
    "b20uZnIuY29uZmlnLnV0aWxzLlVuaXF1ZUtlebJE/sovCG5MAgACTAACaWR0ABJMamF2YS9sYW5n"
    "L1N0cmluZztMAAluYW1lU3BhY2VxAH4ABnhwcHBzcgAoY29tLmZyLmNvbmZpZy5ob2xkZXIuaW1w"
    "bC54bWwuWG1sQ29sQ29uZm4RheOahDxpAgAAeHIALWNvbS5mci5jb25maWcuaG9sZGVyLkFic3Ry"
    "YWN0Q29sbGVjdGlvbkhvbGRlcuUvNBJ3TTRqAgAAeHIALWNvbS5mci5jb25maWcuaG9sZGVyLkFi"
    "c3RyYWN0TXVsdGlWYWx1ZUhvbGRlcqyY2Pu+U0PMAgAFWgAHb3JkZXJlZFoAB3dpdGhUYWdMAAtt"
    "aXNzaW5nS2V5c3QAD0xqYXZhL3V0aWwvU2V0O0wACW9yZGVyTGlzdHQAI0xjb20vZnIvY29uZmln"
    "L2hvbGRlci9pbXBsL0NvbENvbmY7TAAGeG1sVGFncQB+AAZ4cgAjY29tLmZyLmNvbmZpZy5ob2xk"
    "ZXIuQWJzdHJhY3RIb2xkZXIQWSMQGu0raAIAAloAD2lzSW50ZXJmYWNlVHlwZUwACWNsYXNzVHlw"
    "ZXQAEUxqYXZhL2xhbmcvQ2xhc3M7eHIAGWNvbS5mci5jb25maWcuaG9sZGVyLkNvbmbE8Y6eaAEc"
    "hgIADFoAD2hhc0RlZmF1bHRWYWx1ZVoAC2luaXRpYWxpemVkWgASdXBkYXRlV2hpbGVSZWFkaW5n"
    "WgAJdXBncmFkaW5nTAALY2FjaGVTdGF0dXN0ACJMY29tL2ZyL2NvbmZpZy9ob2xkZXIvQ2FjaGVT"
    "dGF0dXM7TAANaWdub3JlQ2xhc3Nlc3EAfgALTAADa2V5dAAhTGNvbS9mci9jb25maWcvaG9sZGVy"
    "L0NoZWNrZWRLZXk7TAAJbmFtZVNwYWNlcQB+AAZMAApwcm9jZXNzb3JzdAAQTGphdmEvdXRpbC9M"
    "aXN0O0wACHByb3BlcnR5cQB+AAZMAAF0dAASTGphdmEvbGFuZy9PYmplY3Q7TAALdXBncmFkYXRp"
    "b25xAH4AAXhwAAAAAHNyACBjb20uZnIuY29uZmlnLmhvbGRlci5DYWNoZVN0YXR1c9rpPsHlrzdZ"
    "AgACWgAHcGFkZGluZ1oACHJlc2lkZW50eHAAAHBwcHBwc3IAE2phdmEudXRpbC5BcnJheUxpc3R4"
    "gdIdmcdhnQMAAUkABHNpemV4cAAAAAB3BAAAAAB4cAFwAQBzcgARamF2YS51dGlsLkhhc2hTZXS6"
    "RIWVlri3NAMAAHhwdwwAAAAQP0AAAAAAAAB4c3IAIWNvbS5mci5jb25maWcuaG9sZGVyLmltcGwu"
    "Q29sQ29uZl7vpVlDn079AgABTAAJdmFsdWVUeXBlcQB+AA54cQB+AA8AAAAAc3EAfgAVAABwcHBw"
    "cHNxAH4AFwAAAAB3BAAAAAB4cHZyABBqYXZhLmxhbmcuU3RyaW5noPCkOHo7s0ICAAB4cHBzcgAl"
    "Y29tLmZyLmNvbmZpZy5ob2xkZXIuaW1wbC54bWwuWG1sQ29uZoqMbQsMZKG2AgAAeHIAL2NvbS5m"
    "ci5jb25maWcuaG9sZGVyLmltcGwueG1sLkFic3RyYWN0WG1sSG9sZGVyqDOF82MFERYCAAJaAAd3"
    "aXRoVGFnTAAGeG1sVGFncQB+AAZ4cQB+AA0AAAAAc3EAfgAVAABwcHBwcHBwAXAAcHNyACFjb20u"
    "ZnIuY29uZmlnLmhvbGRlci5pbXBsLk9iakNvbmZNLpWgtAu/RgIAAUwADGRlZmF1bHRWYWx1ZXEA"
    "fgATeHEAfgANAAAAAHNxAH4AFQAAcHBwcHBzcgAnY29tLmZyLmRhdGEuaW1wbC5OYW1lRGF0YWJh"
    "c2VDb25uZWN0aW9ul9GEQspvn/cCAAFMAARuYW1lcQB+AAF4cQB+AAVwcHNyACFjb20uZnIuY29u"
    "ZmlnLmhvbGRlci5pbXBsLlNpbUNvbmaW8F8OzGyLrgIAAloACXR5cGVBd2FyZUwABHR5cGVxAH4A"
    "DnhxAH4ADwAAAABzcQB+ABUAAHBwcHBwdAAOQEBGUkNMSV9DT05OQEBwAXEAfgAgcAFwcHNxAH4A"
    "KgAAAABzcQB+ABUAAHBwcHBwc3IAEWphdmEubGFuZy5JbnRlZ2VyEuKgpPeBhzgCAAFJAAV2YWx1"
    "ZXhyABBqYXZhLmxhbmcuTnVtYmVyhqyVHQuU4IsCAAB4cP////9wAXZxAH4AMHNxAH4AKgAAAABz"
    "cQB+ABUAAHBwcHBwdAAAcAFxAH4AIHNxAH4AKgAAAABzcQB+ABUAAHBwcHBwdAANQEBGUkNMSV9T"
    "UUxAQHABcQB+ACBzcQB+ACoAAAAAc3EAfgAVAABwcHBwcHNyABFqYXZhLmxhbmcuQm9vbGVhbs0g"
    "coDVnPruAgABWgAFdmFsdWV4cABwAXZxAH4APA=="
)

_CONN_MARKER = "@@FRCLI_CONN@@"
_SQL_MARKER = "@@FRCLI_SQL@@"

#: 参数类型描述（Class 对象在 Java 流里的形式：TC_CLASS + 该类型的 classdesc）
DESC_TABLEDATA = jser.ClassDesc("com.fr.base.TableData", -705472403553876738, 0x02, [])
DESC_MAP = jser.ClassDesc("java.util.Map", 0, 0x00, [])
DESC_INT = jser.ClassDesc("int", 0, 0x00, [])

#: 行数据编解码用到的分隔符/转义（服务端 RowDataHelper 的格式）
_COL_SEP = "\t"
_ROW_SEP = "\n"
_ESCAPES = (("&t;", "\t"), ("&n;", "\n"))


def _replace_java_string(blob: bytes, marker: str, value: str) -> bytes:
    """把 Java 序列化流里的一个字符串值替换成新值（自描述格式，调整长度前缀即可）。"""
    marker_b = jser._mutf8(marker)
    value_b = jser._mutf8(value)  # Java 序列化用 modified UTF-8（含 0x00 与代理对都与标准 UTF-8 不同）
    pattern = b"\x74" + struct.pack(">H", len(marker_b)) + marker_b  # 0x74 = TC_STRING
    count = blob.count(pattern)
    if count != 1:
        raise ApiError(f"数据集预览骨架损坏：标记 {marker} 出现 {count} 次（预期 1）")
    if len(value_b) > 0xFFFF:
        raise ApiError(f"数据集预览的 SQL/连接名过长：modified UTF-8 {len(value_b)} 字节，"
                        "超过 Java 序列化字符串上限 65535")
    return blob.replace(pattern, b"\x74" + struct.pack(">H", len(value_b)) + value_b)


def build_table_data_blob(connection: str, sql: str) -> bytes:
    """生成 `previewTableData` 第一个参数（DBTableData 对象）的序列化字节。"""
    if not connection or not connection.strip():
        raise ApiError("数据集预览需要连接名（模板数据集里的 <DatabaseName>），当前为空")
    blob = _replace_java_string(_TABLE_DATA_SKELETON, _CONN_MARKER, connection)
    return _replace_java_string(blob, _SQL_MARKER, sql)


def substitute_params(sql: str, params: dict) -> str:
    """把数据集 SQL 里的 `${name}` 按参数表做文本替换（与平台语义一致）。

    未提供的参数**直接报错**，不让它静默替换成空串（服务器上那样会得到空结果/跑错 SQL）。
    """
    used = []

    def repl(m):
        name = m.group(1)
        if name not in params:
            used.append(name)
            return m.group(0)
        value = params[name]
        return "" if value is None else str(value)

    out = re.sub(r"\$\{([^}]+)\}", repl, sql)
    if used:
        missing = sorted(set(used))
        raise ApiError("数据集 SQL 缺少参数：" + ", ".join(missing) + "（用 --params 传入）")
    return out


def ascii85_decode(text: str) -> bytes:
    """ASCII85 解码（镜像平台 `Ascii85InputStream` 的实现细节）。

    与标准 ASCII85 的差异（都是平台编码/解码器自身的行为）：
    1. 只跳过换行/回车/空格（换行是编码器每 72 字符自动折行）。
    2. `z` 表示一整组 4 个零字节（平台编码器会写它）。
    3. **末组**：平台解码器把终止符 `~` 留在组里参与运算，再补 `!`（=0），
       最后只输出「组内数据字符数 - 1」个字节。实现按此对齐，保证与平台解出的字节一致。
    """
    clean = "".join(c for c in text if c not in "\n\r ")
    if clean.endswith("~"):
        clean = clean[:-1]
    out = bytearray()
    group = []
    for ch in clean:
        if ch == "z" and not group:  # 平台解码器只在组首识别 z
            out += b"\x00\x00\x00\x00"
            continue
        group.append(ord(ch) - 33)
        if len(group) == 5:
            value = 0
            for x in group:
                value = value * 85 + x
            out += (value & 0xFFFFFFFF).to_bytes(4, "big")
            group = []
    if group:
        seq = group + [93] + [0] * (4 - len(group))
        value = 0
        for x in seq:
            value = value * 85 + x
        out += (value & 0xFFFFFFFF).to_bytes(4, "big")[: len(group) - 1]
    return bytes(out)


def _cdata_decode(text: str) -> str:
    """反向平台 `XMLEncodeUtils.cdataEncode`：CDATA 里的 `]` 写成 `]A`。"""
    return text.replace("]A", "]")


def decode_row_text(rowdata_cdata: str) -> list[list[str]]:
    """把 `<RowData>` 的 CDATA（ASCII85 + raw deflate + 行文本）解成二维数组。"""
    if not rowdata_cdata.strip():
        return []
    raw = zlib.decompress(ascii85_decode(_cdata_decode(rowdata_cdata)), -15)
    text = raw.decode("utf-8")
    if text == "":
        return []
    rows = []
    for line in text.split(_ROW_SEP):
        cells = line.split(_COL_SEP)
        for i, cell in enumerate(cells):
            for esc, raw_ch in _ESCAPES:
                if esc in cell:
                    cells[i] = cell.replace(esc, raw_ch)
        rows.append(cells)
    return rows


def _cdata(tag: str, xml: str) -> str:
    m = re.search(rf"<{tag}>(.*?)</{tag}>", xml, re.S)
    if not m:
        return ""
    inner = m.group(1).strip()
    c = re.match(r"<!\[CDATA\[(.*?)\]\]>", inner, re.S)
    return _cdata_decode(c.group(1) if c else inner)


def parse_preview_xml(xml: str) -> dict:
    """解析服务端返回的 EmbeddedTableData XML → {columns, types, rows}。"""
    names = _cdata("ColumnNames", xml)
    types = _cdata("ColumnTypes", xml)
    columns = names.split(",,.,,") if names else []
    type_list = types.split(",") if types else []
    rowdata = ""
    m = re.search(r"<RowData[^>]*>(.*?)</RowData>", xml, re.S)
    if m:
        c = re.search(r"<!\[CDATA\[(.*?)\]\]>", m.group(1), re.S)
        rowdata = _cdata_decode(c.group(1)) if c else ""
    return {
        "columns": [{"name": n, "type": t} for n, t in zip(columns, type_list)]
        or [{"name": n, "type": ""} for n in columns],
        "rows": decode_row_text(rowdata),
    }


def preview(session, connection: str, sql: str, rows: int = 100) -> dict:
    """走远程设计 RPC 预览一个 SQL 数据集；返回 {columns, rows}。"""
    if rows < 1:
        raise ApiError("--rows 必须 >= 1")
    params = [
        ("com.fr.base.TableData", DESC_TABLEDATA, _jdk_mark() + build_table_data_blob(connection, sql)),
        ("java.util.Map", DESC_MAP, _jdk_mark() + _empty_map_blob()),
        ("int", DESC_INT, jser.encode_param("int", int(rows))),
    ]
    mark, payload = session.call_serialized_payload(
        "com.fr.data.operator.DataOperatorProvider", "previewTableData", params)
    result = parse_serialized_preview(mark, payload)
    result["rows"] = result["rows"][: int(rows)]
    return result


def parse_serialized_preview(mark, payload: bytes) -> dict:
    """解析 previewTableData 的返回值（XML 序列化器：mark + XML 文本）。

    平台返回值异常时（mark 不是 XML 序列化器、payload 不是 XML）直接报错，
    不静默返回空表 —— 否则库升级/序列化器变更会被误读成「数据集没数据」。
    """
    if not mark:
        raise ApiError("数据集预览没有返回值（平台返回空对象）")
    if not payload:
        raise ApiError(f"数据集预览返回空载荷（mark={mark!r}）")
    head = payload[:64].lstrip()
    if not head.startswith((b"<?xml", b"<TableData")):
        raise ApiError(
            f"数据集预览返回了非 XML 载荷（mark={mark!r}），序列化器可能已变化；"
            f"payload 开头={payload[:80]!r}")
    text = payload.decode("utf-8", "replace")
    return parse_preview_xml(text)


def _jdk_mark() -> bytes:
    """SerializerSummary 的 JDK mark：Java 序列化头 + 字符串 "JDK"。"""
    w = jser.JavaWriter()
    w.raw(jser.STREAM_MAGIC + jser.STREAM_VERSION)
    w.string("JDK")
    return bytes(w.buf)


def _empty_map_blob() -> bytes:
    """空 java.util.HashMap 的序列化字节（HashMap 有自定义 writeObject：先写两个字段，
    再用 blockdata 写 capacity/size）。"""
    w = jser.JavaWriter()
    w.raw(jser.STREAM_MAGIC + jser.STREAM_VERSION)

    def body():
        w.raw(struct.pack(">f", 0.75))  # loadFactor
        w.i4(12)                       # threshold（默认 16 * 0.75）
        w.blockdata(struct.pack(">ii", 16, 0))  # capacity=16, size=0
        w.u1(jser.TC_ENDBLOCKDATA)

    w.object(jser.DESC_HASHMAP, body)
    return bytes(w.buf)
