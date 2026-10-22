"""回归：带长 SQL 的平台出错页（>64KB）也必须带出 `detail-message` 平台原因。

背景（2026-10-21 真实用户会话）：某复杂报表导出撞 Impala 列名错误，平台返回 **126KB** 的出错页，
`detail-message` 里嵌着整段原始 SQL。旧实现只读头部 64KB 去提取原因，等不到 `</div>` ⇒
报错只剩「导出产物是平台出错页」，平台原因（错误代码:11300001 …）整条丢失，用户只能自己解 `.bad`。
"""
from __future__ import annotations

import pytest

from frcli.client import assert_export_magic
from frcli.exceptions import ExportError


def _long_error_page(reason: str, filler: int = 120_000) -> str:
    """构造 detail-message 关闭标签落在 64KB 之后的出错页。"""
    return (
        "<!doctype html>\n<html><head><title>出错页面</title></head><body>"
        "<div id='wrapper'><div id='detail'>"
        f"<div id='detail-message'><p>{reason}"
        + ("A" * filler)
        + "</p></div></div></div></body></html>"
    )


def test_long_error_page_xlsx_keeps_platform_reason(tmp_path):
    reason = "错误代码:11300001 数据集 [演示集] 配置错误: Could not resolve column/field reference: 'demo_col'"
    p = tmp_path / "r.xlsx"
    p.write_text(_long_error_page(reason), encoding="utf-8")
    assert p.stat().st_size > 64 * 1024  # 前提：闭合标签在 64KB 之外
    with pytest.raises(ExportError) as ei:
        assert_export_magic(p, "xlsx")
    msg = str(ei.value)
    assert "平台原因" in msg, msg
    assert "11300001" in msg, msg


def test_long_error_page_csv_keeps_platform_reason(tmp_path):
    """csv/text 分支：HTML 形态但无「出错页/class 标记」头（走 html_form 分支，非二进制出错页分支）。"""
    reason = "错误代码:11300002 行高列宽超出页面大小设置"
    page = ("<!doctype html>\n<html><head><title>下载</title></head><body>"
            f"<div id='detail-message'><p>{reason}" + ("A" * 120_000) + "</p></div></body></html>")
    p = tmp_path / "r.csv"
    p.write_text(page, encoding="utf-8")
    assert p.stat().st_size > 64 * 1024
    with pytest.raises(ExportError) as ei:
        assert_export_magic(p, "csv")
    msg = str(ei.value)
    assert "平台原因" in msg, msg
    assert "11300002" in msg, msg


def test_short_error_page_still_works(tmp_path):
    """短页面（<64KB）行为不变，防止修复引入回归。"""
    p = tmp_path / "s.xlsx"
    p.write_text("<!doctype html><html><body><div class='detail-message'>"
                 "很抱歉，数据量过大触发保护机制</div></body></html>", encoding="utf-8")
    with pytest.raises(ExportError) as ei:
        assert_export_magic(p, "xlsx")
    assert "平台原因" in str(ei.value)


def test_normal_xlsx_not_affected(tmp_path):
    """正常 xlsx（PK 魔数）不能因为读全文件逻辑被误判。"""
    p = tmp_path / "ok.xlsx"
    p.write_bytes(b"PK\x03\x04" + b"\x00" * 4096)
    assert_export_magic(p, "excel")  # 生产经 FORMAT_MAP 传的也是 "excel"，覆盖魔数分支
