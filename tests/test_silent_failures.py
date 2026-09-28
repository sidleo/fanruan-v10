"""针对「静默给错东西」这类缺陷的回归测试（Lead 修复，verifier 报的 S1-S4）。

这些都曾经**不报错但结果错**，所以每个用例都断言"必须报错/必须判对"，
而不是断言"能跑通"。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest                                                     # noqa: E402

from frcli.client import _HTML_ERROR_MSG, assert_export_magic      # noqa: E402
from frcli.exceptions import ExportError                           # noqa: E402
import frcli.config as config_mod                                  # noqa: E402


# --- S1：顶层 `frcli -i <实例>` 曾被静默忽略，回落到默认（可能是生产）实例 -----
def test_cli_instance_is_respected(tmp_path, monkeypatch):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(
        "default: prod\n"
        "instances:\n"
        "  prod:\n    url: https://prod.example\n    username: u\n    password: p\n"
        "  dev:\n    url: https://dev.example\n    username: u\n    password: p\n",
        encoding="utf-8")
    monkeypatch.setenv("FRCLI_CONFIG", str(cfg_file))
    try:
        assert config_mod.load_config().name == "prod"
        config_mod.set_cli_instance("dev")
        assert config_mod.load_config().name == "dev"          # 顶层 -i 生效
        with pytest.raises(config_mod.ConfigError):
            config_mod.set_cli_instance("nosuch")
            config_mod.load_config()                            # 绝不静默回落
    finally:
        config_mod.set_cli_instance(None)


def test_cli_instance_falls_back_to_env(tmp_path, monkeypatch):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(
        "default: prod\n"
        "instances:\n"
        "  prod:\n    url: https://p\n    username: u\n    password: p\n"
        "  dev:\n    url: https://d\n    username: u\n    password: p\n",
        encoding="utf-8")
    monkeypatch.setenv("FRCLI_CONFIG", str(cfg_file))
    monkeypatch.setenv("FRCLI_INSTANCE", "dev")
    config_mod.set_cli_instance(None)
    assert config_mod.load_config().name == "dev"


# --- S2：word 产物是 RTF，不是 docx ----------------------------------------
RTF = b"{\\rtf1\\ansi\\deff0 hello}"
ZIP = b"PK\x03\x04rest-of-xlsx"
ERR_PAGE = '<!DOCTYPE html><html><title>出错页面</title>'.encode("utf-8")


@pytest.mark.parametrize("fmt,head", [("excel", ZIP), ("pdf", b"%PDF-1.7 x"),
                                      ("image", b"\x89PNG\r\n"), ("word", RTF)])
def test_export_magic_accepts_correct_head(tmp_path, fmt, head):
    f = tmp_path / "out.bin"
    f.write_bytes(head)
    assert_export_magic(f, fmt)


def test_word_rejects_docx_pk(tmp_path):
    """按 docx 的 PK 去校验 word 会把好文件判成坏文件 —— 这里反过来钉住口径。"""
    f = tmp_path / "out.docx"
    f.write_bytes(ZIP)
    with pytest.raises(ExportError) as ei:
        assert_export_magic(f, "word")
    assert "rtf" in str(ei.value).lower()


def test_export_magic_rejects_error_page(tmp_path):
    f = tmp_path / "out.xlsx"
    f.write_bytes(ERR_PAGE)
    with pytest.raises(ExportError):
        assert_export_magic(f, "excel")


# --- S3：出错页 detail-message 的单引号写法 --------------------------------
def test_error_regex_matches_both_quote_styles():
    dq = '<div id="detail-message"><p>错误代码:11300001</p></div>'
    sq = "<div id='detail-message'><p>错误代码:11300004</p></div>"
    for html, want in ((dq, "11300001"), (sq, "11300004")):
        hits = [m.group(2) for m in _HTML_ERROR_MSG.finditer(html)]
        assert hits and want in hits[0]


# --- S4：排队页 Dec-Waiting_In_Line 必须被识别 ------------------------------
def test_waiting_page_detected_by_keyword():
    """导出侧用关键字判定排队页；这里钉住关键字本身没写错。"""
    from frcli.client import FineReportClient
    import inspect
    src = inspect.getsource(FineReportClient.export_report)
    assert "Dec-Waiting_In_Line" in src
    assert "排队" in src


def test_failed_export_renames_artifact(tmp_path, monkeypatch):
    """导出失败时坏产物不能留在原路径冒充报表（否则 agent 只看"文件在不在"会误用）。"""
    from frcli.client import FineReportClient
    from frcli.config import ServerConfig

    class FakeResp:
        status_code = 200
        headers = {"content-type": "text/html"}
        content = b'<!doctype html>\n<html><body>Oops!!!</body></html>'

    cfg = ServerConfig(name="t", url="https://x", username="u", password="p")
    c = FineReportClient(cfg)
    # export 现在走 _request（认证失效可自动重登），所以 patch 这两层，
    # 否则 _ensure_auth 会拿假 URL 去真登录（离线测试必须完全不出网）
    monkeypatch.setattr(c, "_ensure_auth", lambda: None)
    monkeypatch.setattr(c, "_request", lambda *a, **k: FakeResp())

    out = tmp_path / "broken.xlsx"
    with pytest.raises(ExportError) as ei:
        c.export_report("x.cpt", "excel", str(out))
    assert not out.exists()                       # 原路径必须不存在
    assert (tmp_path / "broken.xlsx.bad").exists()  # 证据保留在 .bad
    assert ".bad" in str(ei.value)


def test_report_info_surfaces_platform_detail(monkeypatch):
    """report info 遇到出错页必须带平台原文，不能只回一句"无法读取报表定义"。"""
    from frcli.client import FineReportClient
    from frcli.config import ServerConfig
    from frcli.exceptions import ApiError

    html = ("<!DOCTYPE html><html><div id='detail-message'>"
            "<p>错误代码:11300001 数据集 [ds_target] 配置错误</p></div></html>").encode("utf-8")

    class FakeResp:
        status_code = 200
        headers = {"content-type": "text/html"}
        text = html.decode("utf-8")
        content = html

    cfg = ServerConfig(name="t", url="https://x", username="u", password="p")
    c = FineReportClient(cfg)
    monkeypatch.setattr(c, "_ensure_auth", lambda: None)
    monkeypatch.setattr(c, "_get", lambda *a, **k: FakeResp())

    with pytest.raises(ApiError) as ei:
        c.get_report_info("a/b.cpt")
    assert "ds_target" in str(ei.value)


# --- csv/text 也要防出错页（实测 export csv 会把出错页写成 .csv）--------------
@pytest.mark.parametrize("payload,should_pass", [
    (b"col1,col2\n1,2\n", True),
    (b'<!DOCTYPE html><html><body>Oops!!!</body></html>', False),
    (b'<!doctype html><script>Dec-Waiting_In_Line</script>', False),
])
def test_csv_export_guard(tmp_path, payload, should_pass):
    f = tmp_path / "out.csv"
    f.write_bytes(payload)
    if should_pass:
        assert_export_magic(f, "text")
    else:
        with pytest.raises(ExportError):
            assert_export_magic(f, "text")


def test_export_report_goes_through_authed_request():
    """导出必须走 _request（认证失效自动重登），否则 302 会伪装成"模板坏了"。"""
    import inspect
    from frcli.client import FineReportClient
    src = inspect.getsource(FineReportClient.export_report)
    assert 'self._request("GET"' in src
    assert "self._http.get(export_url" not in src


# --- 学自另一会话：平台出错页冒充 JSON 时不能漏成 UNKNOWN ----------------------
@pytest.mark.parametrize("ctype", ["application/json", "text/html;charset=UTF-8"])
def test_html_error_page_never_leaks_jsondecodeerror(ctype):
    """`schedule create` 曾因裸 resp.json() 把出错页抛成
    `Expecting value: line 1 column 1 (char 0)` + code=UNKNOWN（看不出原因）。"""
    import httpx
    from frcli.client import _unwrap_json
    from frcli.exceptions import ApiError
    # 平台真实形态：<div id="detail-message">…</div>（正文是 HTML 实体编码的）
    html = ('<html><body>出错页面'
            '<div id="detail-message">Unrecognized field &quot;taskCondition&quot; '
            '(3 known properties: &quot;taskName&quot;,&quot;cron&quot;,&quot;id&quot;)'
            '</div></body></html>')
    r = httpx.Response(200, headers={"content-type": ctype}, text=html)
    with pytest.raises(ApiError) as ei:
        _unwrap_json(r, "创建定时任务")
    msg = str(ei.value)
    assert "Expecting value" not in msg, "不该把 JSONDecodeError 原文漏给用户"
    assert "Unrecognized field" in msg, "要带上平台原文"
