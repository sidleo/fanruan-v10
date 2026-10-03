"""会话巡检器的两个真实缺陷（2026-10 用标准答案测出来的）。"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("scan_sessions", ROOT / "tools" / "scan_sessions.py")
ss = importlib.util.module_from_spec(spec)
sys.modules["scan_sessions"] = ss
spec.loader.exec_module(ss)


def test_matches_all_session_file_naming_schemes():
    """会话文件有**三种命名**（session / session.v3 / session.v4）。

    只匹配 v4 会漏掉 76% 的会话 —— 实测漏掉两个真的用过 frcli 的会话（它们是 v3）。
    """
    src = (ROOT / "tools" / "scan_sessions.py").read_text(encoding="utf-8")
    assert 'rglob("session*.jsonl.zstd")' in src, "必须按通配匹配所有版本"
    assert 'rglob("session.v4.jsonl.zstd")' not in src, "不能只匹配 v4"


def test_call_regex_is_specific_to_this_skill():
    """`references/run.py` 单独出现**不算** —— yh-bigdata 用同样的启动器结构，
    宽判据会把它的会话误报成 fanruan-v10 的使用（精确度测试抓到一批）。"""
    # 别的 skill：不算
    assert not ss.CALL.search('python3 ".../.agents/skills/yh-bigdata/references/run.py" olap sql query')
    assert not ss.CALL.search('cat ~/.agents/skills/yh-bigdata/references/frcli')
    # 本 skill：三种入口都算
    assert ss.CALL.search("frcli report list /x")
    assert ss.CALL.search("python3 -m frcli export excel x.cpt")
    assert ss.CALL.search('python3 "~/.agents/skills/fanruan-v10/references/frcli" --version')
    assert ss.CALL.search('python3 /p/fanruan_v10/references/run.py --version')


def test_windows_filter_uses_record_time_not_file_mtime():
    """按**记录时间戳**切窗口：会话跨天延续，按文件 mtime 会漏（实测扫「昨天」得 0 个）。"""
    src = (ROOT / "tools" / "scan_sessions.py").read_text(encoding="utf-8")
    assert "def ts(rec" in src
    assert "按文件 mtime" in src, "应保留这条教训的注释"


def test_help_text_is_not_counted_as_error():
    """`frcli --help` 的命令列表里有「rpc 远程设计 RPC 网关（…）」。

    早期 FRCLI_ERR 只写 `远程设计 RPC` → help 文本被当成报错（2026-10-01 巡检抓到）。
    必须要求**错误形态**（如「远程设计 RPC xxx 失败」）。
    """
    help_text = "  rpc       远程设计 RPC 网关（🟢 只读白名单 / 🔴 写需 --yes）"
    assert not ss.FRCLI_ERR.search(help_text), "help 文本不该算报错"
    assert ss.FRCLI_ERR.search('远程设计 RPC readAndLockFile 失败: TplLockedException'), "真错误要认出来"
    assert ss.FRCLI_ERR.search('"code": "EXPORT_ERROR"')
    assert ss.FRCLI_ERR.search("导出产物是平台出错页，不是报表: x.xlsx")


def test_maintenance_sessions_are_labelled():
    """cwd 在本 skill 仓库里的会话是我们自己在维护它 —— 要标注，别当用户问题。"""
    assert "MAINT_DIRS" in (ROOT / "tools" / "scan_sessions.py").read_text(encoding="utf-8")
    assert any("Project/fanruan_v10" in d for d in ss.MAINT_DIRS)


def test_error_matching_uses_rendered_text_not_json_dump():
    """报错匹配必须在**实际渲染文本**上做。

    拿 `json.dumps(...)` 整块 JSON 去匹配时，内层引号会被转义成 `\\"`，
    于是 `"status": "error"` / `"code": "API_ERROR"` 这类**带引号的模式永远匹配不上**
    （2026-10-03 实测：一次批量里 9 次失败，扫描器却报「0 条报错」）。
    """
    src = (ROOT / "tools" / "scan_sessions.py").read_text(encoding="utf-8")
    assert 'c.get("text")' in src, "结果要取 content 里的 text"
    assert "results[cid] = body" in src
    # 带引号的模式必须能匹配**渲染文本**
    assert ss.ERR.search('{"status": "error", "error": {"code": "API_ERROR"}}')
    assert ss.FRCLI_ERR.search('{"status": "error", "error": {"code": "API_ERROR"}}')
