"""N1 回归：出错页/排队页可能以 HTML 注释、XML 声明/PI 开头，形态判定必须先剥掉前导标记。

背景（0.10.2 → 本轮）：`_looks_like_html_head()` 若只去 BOM/空白再看开头，
则 `<!-- generated -->\\n<!DOCTYPE html>…出错页面…` 这类产物**不算 HTML 形态** ⇒
`assert_export_magic` 放行、`export_report` 照写文件 —— 用户拿到一份"成功的 CSV"，
内容其实是平台的出错页（静默交付坏产物，比误杀更危险）。
修法：先剥掉前导**注释（可连续多个）/XML 声明 PI/空白/BOM**，再判 `<!doctype`/`<html`。

全离线：只构造产物文件，不打网络。
"""
from __future__ import annotations

import pytest

from frcli.client import assert_export_magic
from frcli.exceptions import ExportError

#: 合法 CSV：特征串在第 201 行备注里（offset 远超 512B）
LEGAL_CSV = ("\n".join(f"{i},ok" for i in range(1, 200))
             + "\n201,备注含出错页面Oops\n").encode("utf-8")

ERR_BODY = ('<div id="detail-message">错误代码:11300002 行高列宽超出页面大小设置</div>'
            "</body></html>").encode("utf-8")


def _write(tmp_path, data: bytes, name="out.csv"):
    p = tmp_path / name
    p.write_bytes(data)
    return p


def _expect_rejected(tmp_path, data: bytes, name: str):
    p = _write(tmp_path, data, name)
    with pytest.raises(ExportError) as ei:
        assert_export_magic(p, "csv")
    return str(ei.value)


# ---------------- ① 合法产物必须放行（护栏） ----------------

def test_legal_csv_with_marker_still_passes(tmp_path):
    """合法 CSV 含「出错页面」字样（offset>512B）必须放行 —— 前导标记剥离不得反过来误杀。"""
    offset = LEGAL_CSV.find("出错页面".encode("utf-8"))
    assert offset > 512, f"装置没把特征串推到 512B 之后（offset={offset}）"
    assert_export_magic(_write(tmp_path, LEGAL_CSV), "csv")


def test_legal_csv_with_leading_comment_passes(tmp_path):
    """合法 CSV 以注释行开头时仍要放行（剥离逻辑别把数据行也吃掉）。"""
    data = b"<!-- exported by tool -->\n" + LEGAL_CSV
    assert_export_magic(_write(tmp_path, data), "csv")


# ---------------- ②③④ 出错页三种前缀形态必须拦 ----------------

def test_error_page_with_leading_html_comment_is_rejected(tmp_path):
    """② `<!-- comment -->\\n<!DOCTYPE html>…出错页面…` 必须拦（中间态会静默放行）。"""
    data = b"<!-- generated -->\n<!DOCTYPE html>\n<html><body>" + ERR_BODY
    msg = _expect_rejected(tmp_path, data, "comment.csv")
    assert "出错页" in msg


def test_error_page_with_leading_xml_declaration_is_rejected(tmp_path):
    """③ 前导 XML 声明（`<?xml …?>`）后跟 `<!DOCTYPE` 必须拦。"""
    data = (b'<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE html>\n<html><body>'
            + ERR_BODY)
    msg = _expect_rejected(tmp_path, data, "xmldecl.csv")
    assert "出错页" in msg


def test_error_page_with_consecutive_leading_comments_is_rejected(tmp_path):
    """②的加强：**连续多个**注释都要剥掉（正则要能吃掉整串，不是只吃一个）。"""
    data = b"<!-- a -->\n<!-- b -->\n<!-- c -->\n<!doctype html>\n<html><body>" + ERR_BODY
    _expect_rejected(tmp_path, data, "comments.csv")


def test_error_page_with_bom_whitespace_and_upper_case_doctype_is_rejected(tmp_path):
    """④ BOM+空白+大写 `<!DOCTYPE` 必须拦。"""
    data = b"\xef\xbb\xbf \n\t<!DOCTYPE html>\n<html><body>" + ERR_BODY
    _expect_rejected(tmp_path, data, "bom.csv")


def test_error_page_with_bom_whitespace_and_upper_case_html_tag_is_rejected(tmp_path):
    """④的另一形态：BOM+空白+大写 `<HTML>`。"""
    data = b"\xef\xbb\xbf\n  <HTML><body>" + ERR_BODY
    _expect_rejected(tmp_path, data, "bom2.csv")


def test_error_page_with_leading_comment_and_oops_marker_is_rejected(tmp_path):
    """特征串是 `Oops!!!`（没有「出错页面」）时，同样要被前缀剥离后的判定拦住。"""
    data = b"<!-- c -->\n<html><body>Oops!!!</body></html>"
    _expect_rejected(tmp_path, data, "oops.csv")


def test_error_page_with_pi_prefix_is_rejected(tmp_path):
    """处理指令（非 xml 声明的 PI）也算前导标记。"""
    data = b'<?xml-stylesheet href="x.css"?>\n<!DOCTYPE html>\n<html><body>' + ERR_BODY
    _expect_rejected(tmp_path, data, "pi.csv")


# ---------------- 其它格式与护栏 ----------------

def test_xlsx_error_page_with_leading_comment_rejected(tmp_path):
    """xlsx 路径：出错页带注释前缀时按魔数不符拦（不能当 xlsx 交付）。"""
    p = _write(tmp_path, b"<!-- c -->\n<!DOCTYPE html>\n<html><body>" + ERR_BODY, "x.xlsx")
    with pytest.raises(ExportError) as ei:
        assert_export_magic(p, "excel")
    assert "魔数" in str(ei.value)


def test_plain_text_without_markers_still_passes(tmp_path):
    """护栏：普通文本（无 HTML 形态）不得被误拦。"""
    p = _write(tmp_path, b"1,ok\n2,ok\n3,ok\n", "plain.csv")
    assert_export_magic(p, "csv")
