"""R1 回归：导出产物的「出错页」判定必须看**开头形态**，不能看"窗口里出现过"。

背景（本轮新引入的回归）：取 `detail-message` 的读取窗口从 512B 放宽到 64KB 后，
判据仍是"窗口里含「出错页面」/`Oops!!!`"⇒ 合法 CSV 的备注列写了这几个字就被误杀、
改名 `.bad`（0.10.2 的 512B 窗口看不到它，所以是老代码没有、新代码才有的行为）。
修法：`_looks_like_html_head()`（去 BOM/空白后以 `<!doctype`/`<html` 开头）**且** 含特征串。

全离线：只构造产物文件，不打网络。
"""
from __future__ import annotations

import pytest

from frcli.client import assert_export_magic
from frcli.exceptions import ExportError

#: 合法 CSV：特征串出现在第 201 行备注里（offset 远超 512B）——真实场景是报表里
#: 恰好有一列文本写了这几个字。
_CSV_ROWS = [f"{i},ok" for i in range(1, 200)]
LEGAL_CSV = ("\n".join(_CSV_ROWS) + "\n201,备注含出错页面Oops\n").encode("utf-8")


def _write(tmp_path, data: bytes, name: str):
    p = tmp_path / name
    p.write_bytes(data)
    return p


def test_legal_csv_with_marker_is_not_rejected(tmp_path):
    """合法 CSV 里出现「出错页面」字样（offset>512B）必须放行。"""
    # 装置自检：特征串真的落在 512B 之后，否则这条用例证明不了"窗口放宽引入的回归"
    offset = LEGAL_CSV.find("出错页面".encode("utf-8"))
    assert offset > 512, f"装置没把特征串推到 512B 之后（offset={offset}）"

    p = _write(tmp_path, LEGAL_CSV, "legal.csv")
    assert_export_magic(p, "csv")          # 不抛异常即通过


def test_legal_csv_marker_far_in_window_still_passes(tmp_path):
    """同上但把特征串推到更后面（64KB 窗口内）—— 仍在开头形态判据的保护下。"""
    data = ("\n".join(_CSV_ROWS) + "\n" + ("x" * 5000) + ",含出错页面\n").encode("utf-8")
    assert data.find("出错页面".encode("utf-8")) > 4096
    p = _write(tmp_path, data, "legal2.csv")
    assert_export_magic(p, "csv")


def test_real_error_page_still_rejected(tmp_path):
    """真出错页（`<!doctype` 开头 + 特征串）仍必须拦。"""
    page = ("<!DOCTYPE html>\n<html><head><title>出错页面</title></head><body>"
            '<div id="detail-message">错误代码:11300002 行高列宽超出页面大小设置</div>'
            "</body></html>").encode("utf-8")
    p = _write(tmp_path, page, "err.csv")

    with pytest.raises(ExportError) as ei:
        assert_export_magic(p, "csv")
    assert "出错页" in str(ei.value)
    assert "11300002" in str(ei.value), "出错页应带出平台原因"


def test_leading_bom_and_whitespace_html_is_still_error_page(tmp_path):
    """BOM/空白前缀不得让真出错页漏网（形态判定要先去 BOM/空白）。"""
    page = b"\xef\xbb\xbf\n  <!DOCTYPE html>\n<html><body>" \
           + "出错页面".encode("utf-8") + b"</body></html>"
    p = _write(tmp_path, page, "bom.csv")

    with pytest.raises(ExportError):
        assert_export_magic(p, "csv")


def test_queue_page_still_rejected(tmp_path):
    """排队页（`Dec-Waiting_In_Line`）仍必须拦。"""
    page = b"<!DOCTYPE html>\n<html><body>Dec-Waiting_In_Line</body></html>"
    p = _write(tmp_path, page, "queue.csv")
    with pytest.raises(ExportError):
        assert_export_magic(p, "csv")

    p2 = _write(tmp_path, page, "queue.xlsx")
    with pytest.raises(ExportError) as ei:
        assert_export_magic(p2, "excel")
    assert "魔数" in str(ei.value)


def test_broken_magic_still_rejected(tmp_path):
    """魔数不符仍要拦（修复只收紧出错页判据，没放宽魔数）。"""
    p = _write(tmp_path, b"not-a-workbook-at-all", "bad.xlsx")
    with pytest.raises(ExportError) as ei:
        assert_export_magic(p, "excel")
    assert "魔数" in str(ei.value)


def test_good_xlsx_still_passes(tmp_path):
    """好产物不得被误拦。"""
    p = _write(tmp_path, b"PK\x03\x04" + b"\x00" * 40, "good.xlsx")
    assert_export_magic(p, "excel")


def test_csv_starting_with_html_is_rejected(tmp_path):
    """csv/text 产物只要是 HTML 文档就拒收（没有魔数可比的兜底判据）。"""
    p = _write(tmp_path, b"<html><body>whatever, no marker string</body></html>", "page.csv")
    with pytest.raises(ExportError):
        assert_export_magic(p, "csv")
