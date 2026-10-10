"""会话巡检器的两个真实缺陷（2026-10 用标准答案测出来的）。"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import sys

import pytest

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


# ---------------------------------------------------------------------------
# 路径形式调用（2026-10 漏报）：`/abs/path/frcli` / `~/…/frcli` / `./references/frcli`
# 背景：session-a73203 用绝对路径调了 14 次 frcli，旧 CALL 只认命令位上的裸 `frcli`，
# 整段会话被丢弃（`frcli 调用 0`）。
# ---------------------------------------------------------------------------
def _call_raw(tool: str, arguments: str, call_id: str = "call_1|sess"):
    """合成一条 `tool/call`：真实会话里 `data["arguments"]` 是 **JSON 文本**，
    shell 调用的命令行在它的 `command` 字段里，工具名在 `data["name"]`。"""
    return {"type": "tool/call",
            "data": {"name": tool, "callId": call_id, "arguments": arguments}}


def _call(command: str, call_id: str = "call_1|sess", tool: str = "bash", **extra):
    """shell 调用的常见形态（`arguments` = `{"command": …, ...}` 的 JSON 文本）。"""
    payload = {"command": command}
    payload.update(extra)
    return _call_raw(tool, json.dumps(payload, ensure_ascii=False), call_id)


def _shown(command: str):
    """扫描器会把 `\\n` 换成空格再截断，这里按同样规则比对。"""
    return command.replace("\\n", " ")[:300]


def _result(text: str, call_id: str = "call_1|sess"):
    return {"type": "tool/result", "data": {"message": {
        "toolCallId": call_id, "content": [{"type": "text", "text": text}]}}}


POSITIVE_CALLS = [
    "frcli report list /x",                                        # 裸命令
    "FRCLI_TIMEOUT=60 frcli report export excel x.cpt",            # 前置赋值
    "FRCLI_TIMEOUT=60 /abs/bin/frcli report export excel x.cpt",   # 前置赋值 + 绝对路径
    "env FRCLI_TIMEOUT=60 frcli server test",                      # env 前缀
    "env X=1 frcli report list /x",                                # env + 裸命令
    "/Users/x/.local/bin/frcli server test",                       # 绝对路径
    "~/.local/bin/frcli report list /x",                           # ~ 路径
    "cd /tmp/work && /abs/path/frcli report list /x",              # cd && 绝对路径
    "./references/frcli --version",                                # 仓库相对路径
    "python3 -m frcli --version",                                  # -m 模块形式
]

NEGATIVE_CALLS = [
    "grep -rn frcli src/",                                         # 检索词
    "ls -la /Users/x/.agents/skills/fanruan-v10/skills/frcli/",    # 目录名（不是调用）
    'const s = "frcli report list /x"',                            # JS 文本里提到
    "python3 /tmp/frcli_direct.py server test",                    # 包装脚本（frcli_ 后是 _）
    'python3 "/Users/x/.agents/skills/yh-bigdata/references/run.py" olap sql query',  # 别的 skill 的启动器
    "cat ~/.agents/skills/yh-bigdata/references/frcli",            # 别的 skill 的入口（读，不是跑）
    "echo 'frcli 是帆软的 CLI'",                                    # 纯提及
    "FRCLI_BIN=/opt/bin/frcli",                                    # 纯赋值（前缀不含 `=`，不算执行）
    "man frcli",                                                   # 命令是 man，不是 frcli
]


@pytest.mark.parametrize("arguments", POSITIVE_CALLS)
def test_path_form_calls_are_counted(arguments):
    assert ss.scan([_call(arguments)])["frcli_cmds"] == [_shown(arguments)]


@pytest.mark.parametrize("arguments", NEGATIVE_CALLS)
def test_mentions_and_other_skills_are_not_counted(arguments):
    assert ss.scan([_call(arguments)])["frcli_cmds"] == [], \
        f"假阳性：{arguments!r} 不是 frcli 调用"


def test_path_form_call_is_paired_with_its_error():
    """端到端：路径形式的 `tool/call` + 对应 `tool/result`（error）必须**配对**出报错。

    只修"计数"不修"配对"时，`frcli_cmds` 非空但 `errors` 为空 —— 这条用例盯的就是它。
    同时钉住"报错只取 frcli 调用的结果"：非 frcli 调用的报错不得混入。
    """
    rows = [
        _call("/Users/x/.local/bin/frcli report list /x", "call_7|sess"),
        _result('{"status": "error", "error": {"code": "API_ERROR", "message": "请求失败"}}',
                "call_7|sess"),
        _call("ls -la /tmp", "call_8|sess"),
        _result('{"status": "error", "error": {"code": "API_ERROR", "message": "无关报错"}}',
                "call_8|sess"),
    ]
    res = ss.scan(rows)
    assert res["frcli_cmds"] == ["/Users/x/.local/bin/frcli report list /x"]
    assert len(res["errors"]) == 1, f"报错配对应恰为 1 条（非 frcli 调用不得混入）：{res['errors']}"
    assert "API_ERROR" in res["errors"][0]


# ---------------------------------------------------------------------------
# 假阳性收口（2026-10 审查：41 例反例集 + 近 7 天真实数据测出三类）
# 契约（task-30）：
#   ① 只对 **shell 调用**（`data["name"] == "bash"`）的 `command` 字段做匹配 ——
#      `read` / `wiki_create` / `present` 这类工具的 args 里出现 `…/frcli/…` 只是**参数值**
#      （实测：一次 `read {"file_path":"…/.local/bin/frcli"}` 把会话的 14 次调用撑成 14+1）；
#   ② 路径前缀**不含引号** —— bash 里的 Python heredoc `Path("/x/src/frcli/tools")`
#      会在 `(` 处被当成命令位（实测：近 7 天调用数被这类 FP 撑到 375，HEAD 是 206）；
#   ③ `frcli` 后不得跟 `-`/`.`/词字符 —— `frcli-old` / `frcli.bak` / `frcli.sh` /
#      `frcli-report-…` 都不是本 CLI（`\b` 对 `-`/`.` 无效，所以必须用负向前瞻）。
# ---------------------------------------------------------------------------
NON_SHELL_TOOL_ARGS = [
    ("read", '{"file_path":"/Users/x/.local/bin/frcli","limit":40}'),
    ("wiki_create", '{"path":"demo/notes/frcli-report-abc","body":"x"}'),
    ("present", '{"files":[{"path":"/tmp/frcli/out.xlsx","description":"x"}]}'),
    # 文档正文里带命令示例（`&&` 提供命令位锚点）：引号排除拦不住，只有"按工具名过滤"能拦
    ("wiki_create", '{"path":"demo/x","body":"示例：cd /tmp && /abs/bin/frcli report list"}'),
]


@pytest.mark.parametrize("tool,arguments", NON_SHELL_TOOL_ARGS)
def test_non_shell_tool_args_are_not_counted(tool, arguments):
    """① 非 shell 工具的 args 里出现 frcli 路径 = 参数值，不是调用。"""
    assert ss.scan([_call_raw(tool, arguments)])["frcli_cmds"] == [], \
        f"假阳性：{tool} 的参数值被当成 frcli 调用"


def test_tool_without_command_field_is_not_counted():
    """反面：没有 `command` 字符串字段的 tool/call —— 哪怕 args 里有 `…/frcli/…` 路径，
    也不算调用（`read` 的 `file_path` / `wiki_create` 的 `path,body` / 字段名不叫 command 的都不是）。"""
    cases = [
        ("read", '{"file_path":"/abs/bin/frcli","limit":40}'),
        ("read", '{"file_path":"/x/src/frcli/tools","offset":1}'),
        ("wiki_create", '{"path":"demo/x","body":"示例：cd /tmp && /abs/bin/frcli report list"}'),
        ("run", '{"command_text":"cd /x && frcli report list"}'),      # 字段名不是 command
    ]
    for tool, args in cases:
        assert ss.scan([_call_raw(tool, args)])["frcli_cmds"] == [], \
            f"假阳性：{tool} 没有 command 字段却被当成调用：{args}"


# ---------------------------------------------------------------------------
# 判据（task-33 起）：**args 能解析出 `command` 字符串字段**就算候选，**不按工具名白名单**。
# 背景：白名单 `("bash","shell","sh")` 会**静默漏报**别的 shell 工具 —— 历史上出现过
# `ssh_exec` / `run` / `exec` 这类同样带 `command` 的调用（漏报 = 整个会话被丢弃）。
# 反过来，`read` 的 `file_path`、`wiki_create` 的 `path/body` 没有 `command` 字段，天然不误计。
# ---------------------------------------------------------------------------
COMMAND_FIELD_CALLS = [
    ("some_custom_tool", "/Users/x/.local/bin/frcli report list /x"),          # 非白名单工具名
    ("ssh_exec", "cd /x && frcli report list"),                                # 历史上真出现过
    ("run", "frcli server test"),
    ("exec", "FRCLI_TIMEOUT=60 /abs/bin/frcli report export excel x.cpt"),
    ("ssh_exec", "./references/frcli --version"),
]


@pytest.mark.parametrize("tool,command", COMMAND_FIELD_CALLS)
def test_any_tool_with_command_field_is_counted(tool, command):
    """工具名不在白名单里，只要 args 有 `command` 字符串字段就要计入（含 `&&` 链式形态）。"""
    args = json.dumps({"command": command}, ensure_ascii=False)
    assert ss.scan([_call_raw(tool, args)])["frcli_cmds"] == [_shown(command)], \
        f"漏报：{tool} 的 command 字段没被计入"


HEREDOC_ARGS = ('{"command":"python3 - <<\'PY\'\\nfrom pathlib import Path\\n'
                'print(Path(\\"/tmp/x/src/frcli/tools\\").exists())\\nPY"}')


def test_python_heredoc_path_is_not_counted():
    """② bash 命令里的 Python heredoc：`Path("/x/src/frcli/tools")` 不是执行 frcli。"""
    assert ss.scan([_call_raw("bash", HEREDOC_ARGS)])["frcli_cmds"] == [], \
        "假阳性：heredoc 里 `(` 后的带引号路径被当成命令位"


@pytest.mark.parametrize("command", [
    "/opt/bin/frcli-old report list /x",
    "frcli.bak --version",
    "./frcli.sh report list /x",
    "frcli-report-2026 export pdf x.cpt",
])
def test_suffixed_binaries_are_not_counted(command):
    """③ `frcli` 后接 `-`/`.` 的是别的可执行文件（`\\b` 拦不住，必须负向前瞻）。"""
    assert ss.scan([_call(command)])["frcli_cmds"] == [], \
        f"假阳性：{command!r} 不是本 CLI"


def test_bash_other_fields_are_not_counted():
    """只有 `command` 字段算数：description 里提到 frcli 不算。"""
    rows = [_call("ls -la /tmp", description="看看 /abs/bin/frcli 的用法")]
    assert ss.scan(rows)["frcli_cmds"] == []


def test_unnamed_record_contract():
    """无名记录（旧格式 / 单测构造）的契约（task-33 保留原行为，边界写在这里）：

    ① args 是 JSON 且有非空 `command` → 按 command 判定（计入）；
    ② args 是 JSON 但没有 `command`（或空串/非字符串）→ **不计入**；
    ③ args **不是 JSON** → 回落"拿原文匹配"（已知残留面：可能把"提到"算成调用；
       实测本机 26226 条 tool/call **全部带 name、0 条无名**，实际不可达）。

    ⚠ 别把 ③ 当成"应该修"就删掉：它是旧格式兼容路径，真实数据里不出现；
    要改的话得先确认无名记录真的存在（届时用 `zstd -dc` 抽查会话）。
    """
    rows = [
        _call_raw("", '{"command":"frcli report list"}', "c1|s"),
        _call_raw("", '{"file_path":"/abs/bin/frcli","limit":1}', "c2|s"),
        _call_raw("", "frcli server test", "c3|s"),
    ]
    assert ss.scan(rows)["frcli_cmds"] == ["frcli report list", "frcli server test"]
