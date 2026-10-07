"""C2 回归：导出产物是平台出错页时，`EXPORT_ERROR` 必须带出平台原因。

背景（实测）：旧文案只有「导出产物是平台出错页，不是报表: <path>」，当事人必须自己
打开 `.bad` 产物才知道平台说的是 `11300002 行高列宽超出页面大小设置`。
两个易漏点：① `detail-message` 属性有双引号/单引号两种写法；② 出错页是 4KB 级的，
`detail-message` 常落在前 512 字节**之后**，只读 512B 会漏。

全离线：只构造产物文件，不打网络。
"""
from __future__ import annotations

import httpx
import pytest

from frcli.client import assert_export_magic, _unwrap_json
from frcli.exceptions import ApiError, ExportError


def _error_page(reason: str, *, quote: str = '"', pad: int = 0,
                simple: str = "Fine-Dec_Default_Error_Tip") -> bytes:
    """合成一份平台出错页（形态照实测：title 出错页面 + simple/detail-message）。"""
    filler = "<!-- " + ("x" * pad) + " -->\n" if pad else ""
    html = (
        "<!DOCTYPE html>\n<html>\n<head>\n<meta charset=\"utf-8\">\n"
        "<title>出错页面</title>\n</head>\n<body>\n" + filler +
        f'<div id="simple-message">{simple}</div>\n'
        f"<div id={quote}detail-message{quote} style=\"display:none\">{reason}</div>\n"
        "</body>\n</html>\n"
    )
    return html.encode("utf-8")


REASON = ("com.fr.engine.CalculationException: 数据集[ds_placeholder]执行失败："
          "错误代码:11300002 行高列宽超出页面大小设置")


def _write(tmp_path, data: bytes, name="out.xlsx"):
    p = tmp_path / name
    p.write_bytes(data)
    return p


def test_export_error_carries_platform_reason(tmp_path):
    """出错页 → EXPORT_ERROR 文案里要能看到平台原文（含错误代码）。"""
    p = _write(tmp_path, _error_page(REASON))

    with pytest.raises(ExportError) as ei:
        assert_export_magic(p, "excel")

    msg = str(ei.value)
    assert "11300002" in msg, f"文案没带出平台原因: {msg}"
    assert "行高列宽超出页面大小设置" in msg


def test_export_error_advises_extype_simple_for_11300002(tmp_path):
    """11300002 是「宽表分页导出」问题 → 必须给出可执行建议。"""
    p = _write(tmp_path, _error_page(REASON))

    with pytest.raises(ExportError) as ei:
        assert_export_magic(p, "excel")

    msg = str(ei.value)
    assert "extype" in msg and "simple" in msg, f"缺 extype=simple 的可执行建议: {msg}"


def test_reason_read_beyond_first_512_bytes(tmp_path):
    """出错页 detail-message 在 512 字节之后时仍要读到（老的截断风险）。"""
    p = _write(tmp_path, _error_page(REASON, pad=600))
    data = p.read_bytes()

    offset = data.find(b"11300002")
    assert offset > 512, f"装置没把原因推到 512B 之后（offset={offset}），本用例证明不了截断风险"

    with pytest.raises(ExportError) as ei:
        assert_export_magic(p, "excel")
    assert "11300002" in str(ei.value), "只读了前 512 字节 → 平台原因丢失"


def test_single_quoted_detail_message_attribute(tmp_path):
    """`id='detail-message'` 单引号写法同样要认。"""
    p = _write(tmp_path, _error_page(REASON, quote="'"))

    with pytest.raises(ExportError) as ei:
        assert_export_magic(p, "excel")
    assert "11300002" in str(ei.value)


def test_html_entities_in_reason_are_decoded(tmp_path):
    """detail-message 里的 HTML 实体要解码后给出。"""
    p = _write(tmp_path, _error_page("数据集[ds_placeholder]失败 &amp; 原因: a &lt; b"))

    with pytest.raises(ExportError) as ei:
        assert_export_magic(p, "excel")
    msg = str(ei.value)
    assert "a < b" in msg and "&lt;" not in msg


def test_empty_detail_message_falls_back_to_simple_message(tmp_path):
    """detail-message 为空 → 退到 simple-message 的本地化兜底文案，不能一片空白。"""
    page = ("<!DOCTYPE html>\n<html>\n<head><title>出错页面</title></head>\n<body>\n"
            '<div id="simple-message">Fine-Dec_Default_Error_Tip</div>\n'
            '<div id="detail-message" style="display:none"></div>\n'
            "</body>\n</html>\n").encode("utf-8")
    p = _write(tmp_path, page)

    with pytest.raises(ExportError) as ei:
        assert_export_magic(p, "excel")
    msg = str(ei.value)
    assert "出错页" in msg
    assert "对象不存在" in msg or "平台返回错误页" in msg, f"兜底文案缺失: {msg}"


def test_other_error_code_gets_no_extype_advice(tmp_path):
    """不是 11300002 就别乱给 extype 建议（避免误导）。"""
    p = _write(tmp_path, _error_page("错误代码:99999999 合成错误"))

    with pytest.raises(ExportError) as ei:
        assert_export_magic(p, "excel")
    msg = str(ei.value)
    assert "99999999" in msg
    assert "extype" not in msg


def test_csv_error_page_also_carries_reason(tmp_path):
    """csv 没有魔数，退化为"像不像 HTML"判定——同样要带平台原因。"""
    p = _write(tmp_path, _error_page(REASON), name="out.csv")

    with pytest.raises(ExportError) as ei:
        assert_export_magic(p, "csv")
    assert "11300002" in str(ei.value)


def test_broken_magic_without_error_page_still_raises(tmp_path):
    """非出错页的坏产物照旧要拦（别把修复做成放宽校验）。"""
    p = _write(tmp_path, b"not-a-workbook-at-all", name="out.xlsx")

    with pytest.raises(ExportError) as ei:
        assert_export_magic(p, "excel")
    assert "魔数" in str(ei.value)


def test_valid_magic_still_passes(tmp_path):
    """好产物不得被误拦。"""
    p = _write(tmp_path, b"PK\x03\x04" + b"\x00" * 40)
    assert_export_magic(p, "excel")


def test_interface_path_and_export_path_share_reason(tmp_path):
    """同一份出错页：接口路径（_unwrap_json）与产物路径（assert_export_magic）都要读出原因。

    这条是"共用同一个抽取 helper"的**行为**判据（不绑实现名）。
    """
    page = _error_page(REASON)
    p = _write(tmp_path, page)

    with pytest.raises(ExportError) as ei:
        assert_export_magic(p, "excel")
    export_msg = str(ei.value)

    resp = httpx.Response(200, content=page,
                          headers={"content-type": "text/html; charset=utf-8"})
    with pytest.raises(ApiError) as ei2:
        _unwrap_json(resp, "列出报表")
    api_msg = str(ei2.value)

    for msg in (export_msg, api_msg):
        assert "11300002" in msg and "行高列宽超出页面大小设置" in msg
