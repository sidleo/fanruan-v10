"""平台出错页的**元素文本**形式（`<div class="detail-message">…</div>`）也要给出平台原因。

背景（2026-10-16 真实会话 + 真机复现）：用户导出大报表撞平台「数据量过大」保护页，
页面是 `<div class="simple-message">非常抱歉…</div>` +
`<div class="detail-message">很抱歉，数据量过大触发保护机制…</div>`（**元素文本**形式）。
旧实现只认 `id="detail-message"`（标记属性形式），且出错页识别依赖 `出错页面`/`Oops!!!`
字面串 ⇒ 二进制导出落到「魔数不符」通用文案，平台给的可执行指令（减少数据量 / 管理员改模板限制）
被丢掉，用户会去怀疑格式与封装。

守五件事（全部离线、脱敏；页面用等价结构自造）：
1. 元素文本形式（`class="detail-message"` / 只有 `class="simple-message"`）能取到 reason；
2. 标记属性形式（`id="detail-message"`）仍优先，11300002 那类（带错误码/SQL）不回归；
3. xlsx/pdf 在这种页上走**「平台出错页」分支**并带原因（不是"魔数不符"通用文案）；
4. 合法 CSV（正文含「出错页面」字样的好产物）不被误杀；
5. 空/纯空白 message ⇒ 视为无，不产生空 `；平台原因: ` 尾巴。
"""
from __future__ import annotations

import pytest

from frcli.client import (_export_error_page_suffix, _html_error_reason,
                          assert_export_magic)
from frcli.exceptions import ExportError

#: 平台保护页的原文（平台 UI 文案，非用户数据）
PROTECT_REASON = "很抱歉，数据量过大触发保护机制，请减少查询数据量。"

#: 真机 2026-10-17 抓到的保护页结构（1885B）：首字节 HTML + class 形式的 simple/detail
PROTECT_PAGE = f"""<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <title></title>
    <style>
        .main div {{ text-align: center; }}
        .simple-message {{ font-weight: 500; font-size: 28px; color: #3685f2; }}
        .detail-message {{ font-size: 16px; color: #ff4949; }}
        .solution {{ font-size: 16px; color: #ff4949; }}
    </style>
</head>
<body>
<a href="/webroot/decision/login" class="login"></a>
<div class="main">
    <div>
        <div class="simple-message">
            非常抱歉，无法查看该页面
        </div>
        <div class="detail-message">
            {PROTECT_REASON}
        </div>
        <div class="solution">
        </div>
    </div>
</div>
</body>
</html>
"""

#: 只有 simple-message（元素文本），detail-message 缺失/为空时的兜底
SIMPLE_ONLY_PAGE = ('<!doctype html>\n<html>\n<head><title></title></head>\n<body>\n'
                    '<div class="main">\n'
                    '<div class="simple-message">平台维护中，请稍后再试</div>\n'
                    '</div>\n</body>\n</html>\n')

#: 只有 simple-message，且内容是本地化 key（要翻成人话）
SIMPLE_LOCALE_PAGE = ('<!doctype html>\n<html>\n<head><title></title></head>\n<body>\n'
                      '<div class="simple-message">Fine-Dec_No_Privilege_Access_Page</div>\n'
                      '</body>\n</html>\n')

#: 标记属性形式（旧）：带错误码与原始 SQL —— 必须继续优先，11300002 建议不回归
ATTR_PAGE = ('<!DOCTYPE html>\n<html>\n<head><title>出错页面</title></head>\n<body>\n'
             '<div id="simple-message">非常抱歉，无法查看该页面</div>\n'
             "<div id='detail-message' style=\"display:none\">"
             '错误代码:11300002 行高列宽超出页面大小设置；原始 SQL: select 1</div>\n'
             '</body>\n</html>\n')

#: 两种 message 都是空白 ⇒ 视为没有原因
BLANK_MSG_PAGE = ('<!doctype html>\n<html>\n<head><title></title></head>\n<body>\n'
                  '<div class="simple-message">   </div>\n'
                  '<div class="detail-message">\n\n  </div>\n'
                  '</body>\n</html>\n')

#: 合法 CSV：特征串出现在第 201 行备注里（offset 远超 512B）
LEGAL_CSV = ("\n".join(f"{i},ok" for i in range(1, 200)) + "\n201,备注含出错页面Oops\n").encode()


def _write(tmp_path, data: bytes, name: str):
    p = tmp_path / name
    p.write_bytes(data)
    return p


# ---------------------------------------------------------------------------
# 1. 元素文本形式
# ---------------------------------------------------------------------------
def test_element_text_detail_message_reason():
    assert _html_error_reason(PROTECT_PAGE) == PROTECT_REASON
    suffix = _export_error_page_suffix(PROTECT_PAGE.encode("utf-8"))
    assert suffix.startswith(f"；平台原因: {PROTECT_REASON}")


def test_memory_protection_reason_gets_actionable_advice():
    """撞内存保护页时，除平台原文外还要给可执行建议。

    平台原文只说"数据量过大触发保护机制，请减少查询数据量"；用户还需要知道
    「怎么做」（缩小/分批）与「什么不管用」（`extype=simple` **不解除**该保护）。
    """
    suffix = _export_error_page_suffix(PROTECT_PAGE.encode("utf-8"))
    assert "分批" in suffix or "缩小" in suffix, f"应给「怎么做」：{suffix}"
    assert "模板限制" in suffix or "内存管理" in suffix, f"应给管理员处置入口：{suffix}"
    assert "不解除" in suffix and "extype" in suffix, f"应说明 extype=simple 不解除：{suffix}"


def test_element_text_simple_message_only_plain_text():
    assert _html_error_reason(SIMPLE_ONLY_PAGE) == "平台维护中，请稍后再试"


def test_element_text_simple_message_locale_key_is_mapped():
    assert _html_error_reason(SIMPLE_LOCALE_PAGE) == "当前账号无此接口权限（该接口需管理员）"


def test_element_text_detail_message_wins_over_simple():
    """同一页里 simple 与 detail 都有 ⇒ 取 detail（平台原因比"无法查看该页面"具体）。"""
    assert _html_error_reason(PROTECT_PAGE) == PROTECT_REASON
    assert "无法查看该页面" not in _html_error_reason(PROTECT_PAGE)


# ---------------------------------------------------------------------------
# 2. 标记属性形式仍优先（11300002 不回归）
# ---------------------------------------------------------------------------
def test_marker_attribute_form_still_preferred_and_advice_kept():
    reason = _html_error_reason(ATTR_PAGE)
    assert "11300002" in reason and "原始 SQL" in reason
    suffix = _export_error_page_suffix(ATTR_PAGE.encode("utf-8"))
    assert "11300002" in suffix and "extype" in suffix, "11300002 的可执行建议不能丢"


def test_marker_attribute_form_has_priority_over_element_text():
    """两种形式同时出现（属性在前/在后都要）→ 仍取属性形式里的错误码与 SQL。"""
    both_attr_first = ATTR_PAGE.replace(
        '<div id="simple-message">非常抱歉，无法查看该页面</div>',
        f'<div class="simple-message">非常抱歉，无法查看该页面</div>\n'
        f'<div class="detail-message">{PROTECT_REASON}</div>')
    assert "11300002" in _html_error_reason(both_attr_first)


# ---------------------------------------------------------------------------
# 3. 二进制格式：这种页要走「平台出错页」分支并带原因
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("fmt,name", [("excel", "out.xlsx"), ("pdf", "out.pdf")])
def test_binary_formats_report_platform_error_page_with_reason(tmp_path, fmt, name):
    p = _write(tmp_path, PROTECT_PAGE.encode("utf-8"), name)
    with pytest.raises(ExportError) as ei:
        assert_export_magic(p, fmt)
    msg = str(ei.value)
    assert "平台出错页" in msg, f"应走「平台出错页」分支，实际：{msg}"
    assert PROTECT_REASON in msg, f"平台原因必须带出，实际：{msg}"
    assert "魔数不符" not in msg, f"不该再落到通用文案，实际：{msg}"


# ---------------------------------------------------------------------------
# 4. 合法 CSV 不被误杀
# ---------------------------------------------------------------------------
def test_legal_csv_with_marker_is_not_rejected(tmp_path):
    assert LEGAL_CSV.find("出错页面".encode("utf-8")) > 512, "装置自检：特征串应在 512B 之后"
    p = _write(tmp_path, LEGAL_CSV, "legal.csv")
    assert_export_magic(p, "csv")           # 不抛异常即通过


# ---------------------------------------------------------------------------
# 5. 空/纯空白 message：不产生空尾巴
# ---------------------------------------------------------------------------
def test_blank_message_yields_no_reason_and_no_empty_tail():
    assert _html_error_reason(BLANK_MSG_PAGE) == ""
    assert _export_error_page_suffix(BLANK_MSG_PAGE.encode("utf-8")) == ""


def test_blank_message_error_page_has_no_empty_tail(tmp_path):
    """即使判定成出错页，也不能出现 `；平台原因: `（后面什么都没有）这种空尾巴。"""
    p = _write(tmp_path, BLANK_MSG_PAGE.encode("utf-8"), "blank.xlsx")
    with pytest.raises(ExportError) as ei:
        assert_export_magic(p, "excel")
    msg = str(ei.value)
    assert "平台原因:" not in msg, f"空原因不得拼尾巴：{msg}"
    assert not msg.rstrip().endswith("；"), msg
