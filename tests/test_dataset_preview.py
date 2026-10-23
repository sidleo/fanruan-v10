"""数据集预览（report preview）的离线回归。

固定样本由平台自身的 `XMLEncodeUtils.encodeBytesAsString`（ASCII85+deflate）生成：
- T1：短行，末组 4 字符（验证平台解码器「终止符参与末组运算」的怪癖）；
- T2：6 行、>72 字符（验证自动折行 + CDATA 的 `]` -> `]A` 转义 + 末组解码）。
"""
from __future__ import annotations

import base64
import zlib

import pytest

from frcli import dataset_preview as D
from frcli.exceptions import ApiError

T1_TEXT = base64.b64decode("QTEJQgkyCkEyCUMJMw==").decode()      # A1\tB\t2\nA2\tC\t3
T1_ENC = 'F#;s"i\\]Y81u`W>1^3p~'

T2_TEXT = base64.b64decode(
    "aXRlbS0wLTAxMjM0NTY3ODlhYmNkZWZnaGlqa2xtbm9wCXZhbHVlXTAKaXRlbS0xLTAxMjM0NTY3ODlhYmNkZWZnaGlqa2xtbm9wCXZhbHVlXTEKaXRlbS0yLTAxMjM0NTY3ODlhYmNkZWZnaGlqa2xtbm9wCXZhbHVlXTIKaXRlbS0zLTAxMjM0NTY3ODlhYmNkZWZnaGlqa2xtbm9wCXZhbHVlXTMKaXRlbS00LTAxMjM0NTY3ODlhYmNkZWZnaGlqa2xtbm9wCXZhbHVlXTQKaXRlbS01LTAxMjM0NTY3ODlhYmNkZWZnaGlqa2xtbm9wCXZhbHVlXTU="
).decode()
T2_ENC = ("b:H60eMY]20JkOC0f:brYY7__:.\\/QccF>QcH4>S0AnBSbUH8G2;lU[WAGm%dL`/$Lp0JrLe"
          "\n;0o.ZGT$9aIdVJZ(COXO7d_~")


def _escaped(enc: str) -> str:
    """模拟平台 XML writer 的 cdataEncode：把 `]` 写成 `]A`。"""
    return enc.replace("]", "]A")


def test_ascii85_short_final_group():
    # ascii85 只解到「压缩字节」这一层；再 raw-deflate 才回到行文本
    assert zlib.decompress(D.ascii85_decode(T1_ENC), -15) == T1_TEXT.encode()


def test_ascii85_z_group_matches_platform_encoder():
    # 平台 Ascii85OutputStream 对「4 个零字节」写 `z`；fixtures 由该编码器直接生成
    assert D.ascii85_decode("z~") == b"\x00\x00\x00\x00"
    assert D.ascii85_decode("z!<N~") == b"\x00\x00\x00\x00\x01\x02"
    assert D.ascii85_decode("zz~") == b"\x00" * 8


def test_ascii85_wrapped_and_escaped():
    # 平台写 XML 时先折行、再把 `]` 转义；解码器必须先反 cdata 转义再解 ASCII85
    assert D.decode_row_text(_escaped(T2_ENC)) == [line.split("\t") for line in T2_TEXT.split("\n")]


def test_decode_row_text_matches_raw_text():
    rows = D.decode_row_text(_escaped(T2_ENC))
    assert len(rows) == 6
    assert rows[0] == ["item-0-0123456789abcdefghijklmnop", "value]0"]
    assert rows[5][1] == "value]5"


def test_cdata_decode_reverses_platform_escape():
    assert D._cdata_decode("n]Auf5") == "n]uf5"
    assert D._cdata_decode("no-escape") == "no-escape"


def test_parse_preview_xml_builds_columns_and_rows():
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<TableData xmlVersion="20211223" releaseVersion="10.0.0" '
        'class="com.fr.data.impl.EmbeddedTableData">\n'
        "<Parameters/>\n"
        "<DSName>\n<![CDATA[]]></DSName>\n"
        "<ColumnNames>\n<![CDATA[a,,.,,b]]></ColumnNames>\n"
        "<ColumnTypes>\n<![CDATA[java.lang.String,java.lang.Long]]></ColumnTypes>\n"
        '<RowData ColumnTypes="java.lang.String,java.lang.Long">\n'
        "<![CDATA[" + _escaped(T1_ENC) + "\n]]></RowData>\n"
        "</TableData>\n"
    )
    result = D.parse_preview_xml(xml)
    assert result["columns"] == [
        {"name": "a", "type": "java.lang.String"},
        {"name": "b", "type": "java.lang.Long"},
    ]
    assert result["rows"] == [["A1", "B", "2"], ["A2", "C", "3"]]


def test_parse_preview_xml_without_rowdata_is_empty():
    xml = (
        '<TableData class="com.fr.data.impl.EmbeddedTableData">'
        "<ColumnNames><![CDATA[only]]></ColumnNames>"
        "<ColumnTypes><![CDATA[java.lang.String]]></ColumnTypes>"
        "</TableData>"
    )
    result = D.parse_preview_xml(xml)
    assert result["columns"] == [{"name": "only", "type": "java.lang.String"}]
    assert result["rows"] == []


def test_build_table_data_blob_patches_conn_and_sql():
    blob = D.build_table_data_blob("conn-x", "select 1")
    assert b"@@FRCLI_CONN@@" not in blob
    assert b"@@FRCLI_SQL@@" not in blob
    assert b"conn-x" in blob
    assert b"select 1" in blob
    assert blob.startswith(b"\xac\xed\x00\x05")


def test_build_table_data_blob_handles_long_sql():
    sql = "select " + ",".join(str(i) for i in range(500)) + " from t"
    blob = D.build_table_data_blob("conn", sql)
    assert sql.encode() in blob


def test_build_table_data_blob_uses_modified_utf8_for_supplementary_chars():
    # Java 序列化字符串用 modified UTF-8（emoji 是代理对，标准 UTF-8 的 4 字节会被服务端读坏）
    sql = "select '😀'"
    blob = D.build_table_data_blob("conn", sql)
    assert sql.encode("utf-8") not in blob      # 标准 UTF-8 的 4 字节形式
    assert b"\xed\xa0\xbd\xed\xb8\x80" in blob  # 😀 的 modified UTF-8（代理对 CESU-8）


def test_table_data_blob_roundtrips_through_java_serialization():
    from frcli import jser

    blob = D.build_table_data_blob("conn-x", "select 1")
    reader = jser.JavaReader(blob)
    reader.raw(4)
    obj = reader.read_object()
    assert obj.class_name == "com.fr.data.impl.DBTableData"
    # database = ObjConf.t -> NameDatabaseConnection.name(SimConf).t
    db = obj.fields["database"].fields["t"]
    assert db.fields["name"].fields["t"] == "conn-x"
    assert obj.fields["query"].fields["t"] == "select 1"


def test_parse_serialized_preview_rejects_non_xml_payload():
    with pytest.raises(ApiError, match="没有返回值"):
        D.parse_serialized_preview(None, b"<TableData/>")
    with pytest.raises(ApiError, match="空载荷"):
        D.parse_serialized_preview("mark", b"")
    with pytest.raises(ApiError, match="非 XML 载荷"):
        D.parse_serialized_preview("mark", b"\x01\x02not xml")


def test_parse_serialized_preview_parses_xml():
    xml = ('<TableData class="com.fr.data.impl.EmbeddedTableData">'
           "<ColumnNames><![CDATA[a]]></ColumnNames>"
           "<ColumnTypes><![CDATA[java.lang.String]]></ColumnTypes>"
           "</TableData>").encode()
    result = D.parse_serialized_preview("mark", xml)
    assert result["columns"] == [{"name": "a", "type": "java.lang.String"}]
    assert result["rows"] == []


def test_build_table_data_blob_requires_connection():
    with pytest.raises(ApiError, match="连接名"):
        D.build_table_data_blob("  ", "select 1")


def test_substitute_params_replaces_all_occurrences():
    sql = "where sdt between '${sdate}' and '${edate}' or x = '${sdate}'"
    out = D.substitute_params(sql, {"sdate": "20260101", "edate": "20260131"})
    assert "${" not in out
    assert out.count("20260101") == 2
    assert "20260131" in out


def test_substitute_params_missing_param_raises_with_name():
    with pytest.raises(ApiError, match="edate"):
        D.substitute_params("select '${sdate}', '${edate}'", {"sdate": "x"})


def test_substitute_params_none_becomes_empty_string():
    assert D.substitute_params("select '${x}'", {"x": None}) == "select ''"


def test_substitute_params_without_placeholders_is_noop():
    assert D.substitute_params("select 1", {}) == "select 1"


def _fake_client(datasets):
    client = D.__dict__  # noqa: F841  (占位，避免误用)
    from frcli.client import FineReportClient

    c = FineReportClient.__new__(FineReportClient)
    c.get_report_datasets = lambda path: datasets  # type: ignore[method-assign]
    return c


def test_client_preview_rejects_non_sql_dataset():
    c = _fake_client([{"name": "ds1", "parameters": [], "sql": "", "connection": ""}])
    with pytest.raises(ApiError, match="不是 SQL 数据集"):
        c.preview_report_dataset("demo/a.cpt", "ds1")


def test_client_preview_lists_available_datasets_when_missing():
    c = _fake_client([{"name": "ds1", "parameters": [], "sql": "select 1", "connection": "c"}])
    with pytest.raises(ApiError, match="ds1"):
        c.preview_report_dataset("demo/a.cpt", "nope")


def test_client_preview_surfaces_missing_params_before_remote_call():
    c = _fake_client([{"name": "ds1", "parameters": ["sdate"], "sql": "select '${sdate}'", "connection": "c"}])
    with pytest.raises(ApiError, match="sdate"):
        c.preview_report_dataset("demo/a.cpt", "ds1")


class _FakePreviewClient:
    def __init__(self, result):
        self.result = result

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def preview_report_dataset(self, report_path, dataset_name, params=None, rows=100):
        return self.result


def _run_preview_table(monkeypatch, columns, rows):
    from click.testing import CliRunner

    from frcli.commands import report as report_cmd

    result = {
        "columns": [{"name": c, "type": "java.lang.String"} for c in columns],
        "rows": rows,
        "report": "demo_group/demo_user/rpt.cpt",
        "dataset": "ds1",
        "connection": "demo_conn",
        "rows_requested": len(rows),
    }
    monkeypatch.setattr(report_cmd, "get_client", lambda instance: _FakePreviewClient(result))
    return CliRunner().invoke(
        report_cmd.report_group,
        ["preview", "demo_group/demo_user/rpt.cpt", "--dataset", "ds1", "-f", "table"],
    )


def test_cli_table_does_not_parse_rich_markup_in_values(monkeypatch):
    # 数据里的 [red]/[y]/[/] 必须原样显示；rich 直接吃 str 会丢字符甚至 MarkupError 退出
    res = _run_preview_table(
        monkeypatch, ["a", "b"],
        [["[red]x", "x[y]z"], ["[/]", "[b]"]],
    )
    assert res.exit_code == 0, res.output
    assert "[red]x" in res.output
    assert "x[y]z" in res.output
    assert "[/]" in res.output
    assert "[b]" in res.output


def test_cli_table_wide_layout_shows_values(monkeypatch):
    # 34 列横排在 80 宽终端会被压成 0 宽；宽表必须走纵向布局，值要能看到
    cols = [f"c{i}" for i in range(1, 35)]
    rows = [[f"v{i}" for i in range(1, 35)]]
    res = _run_preview_table(monkeypatch, cols, rows)
    assert res.exit_code == 0, res.output
    assert "宽表用纵向布局" in res.output
    assert "1. c1 = v1" in res.output
    assert "34. c34 = v34" in res.output
