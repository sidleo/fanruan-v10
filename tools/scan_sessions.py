#!/usr/bin/env python3
"""扫 DSH 会话，挑出与 fanruan-v10 / frcli 相关的痕迹，产出**优化线索**清单。

用法:
    tools/scan_sessions.py                 # 默认扫「昨天」
    tools/scan_sessions.py --date 2026-09-30
    tools/scan_sessions.py --days 3        # 最近 3 天
    tools/scan_sessions.py --all           # 全部会话（慢）
    tools/scan_sessions.py --json          # 机器可读

会话存储：`~/.dsh/sessions/<cwd 编码>/<session-id>/session.v4.jsonl.zstd`（zstd 压缩的 JSONL）。
本脚本靠 `zstd -dc` 解压（系统有该命令），只用标准库。

它**只收集证据**，不做判断也不改任何东西 —— 优化前必须人工/agent 复核并实测验证。
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import os
import pathlib
import re
import subprocess
import sys

SESSIONS = pathlib.Path("~/.dsh/sessions").expanduser()

#: 「真的调用了 frcli」——只认命令行里跑 frcli / python -m frcli。
#: ⚠ 不要用宽泛的「提到帆软就算」：wiki 检索结果里满是帆软词条，
#: 那样每个搜过知识库的会话都会被算进来，报错区全是知识库正文（实测噪音极大）。
CALL = re.compile(r"\bfrcli\b|python3?\s+-m\s+frcli|references/frcli|references/run\.py", re.I)

#: frcli 自己的报错特征（用于给结果定责）
FRCLI_ERR = re.compile(
    r"EXPORT_ERROR|CONNECTION_ERROR|API_ERROR|AUTH_ERROR|远程设计 RPC|TplLocked"
    r"|导出产物是平台出错页|FRCLI_TIMEOUT|read operation timed out|fine-.*error", re.I)

#: 报错/异常信号（用于挑「值得优化」的点）
ERR = re.compile(
    r'"status":\s*"error"|"code":\s*"(?:API_ERROR|EXPORT_ERROR|CONNECTION_ERROR|AUTH_ERROR|UNKNOWN)"'
    r"|Traceback|\bError\b:|Exception|timed out|command not found|does not exist"
    r"|无法|失败|超时|被锁",
)

#: 用户在抱怨/纠正的信号（往往是真痛点）
COMPLAINT = re.compile(
    r"不对|错了|不是|为什|怎么|应该|重新|又|还是|没生效|没实现|好像没|你是不是|我不"
    r"|值得优化|有问题|不准确|对不上|漏了",
)


def ts(rec: dict):
    """记录时间（毫秒 → datetime；取不到返回 None）。"""
    t = rec.get("time")
    if not isinstance(t, (int, float)):
        return None
    try:
        return dt.datetime.fromtimestamp(t / 1000 if t > 1e11 else t)
    except (OSError, ValueError):
        return None


def iter_sessions():
    for f in SESSIONS.rglob("session.v4.jsonl.zstd"):
        try:
            yield f, dt.datetime.fromtimestamp(f.stat().st_mtime)
        except OSError:
            continue


def read_session(path: pathlib.Path) -> list[dict]:
    """解压并逐行解析；坏行跳过（会话文件可能被截断）。"""
    try:
        raw = subprocess.run(["zstd", "-dc", str(path)], capture_output=True, timeout=120).stdout
    except Exception:
        return []
    rows = []
    for line in raw.split(b"\n"):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows


def _texts(obj, kinds=("text",), depth=0):
    out = []
    if depth > 6:
        return out
    if isinstance(obj, dict):
        if obj.get("type") in kinds and isinstance(obj.get("text"), str):
            out.append(obj["text"])
        for v in obj.values():
            out += _texts(v, kinds, depth + 1)
    elif isinstance(obj, list):
        for x in obj:
            out += _texts(x, kinds, depth + 1)
    return out


def scan(rows: list[dict]) -> dict:
    user_msgs, frcli_cmds, errors = [], [], []
    frcli_call_ids: set[str] = set()
    results: dict[str, str] = {}

    for r in rows:
        t = r.get("type")
        data = r.get("data") or {}
        if t == "user/message":
            txt = " ".join(_texts(data)).strip()
            # 跳过系统注入的消息（runtime context / 任务结束通知等）
            if txt and not txt.startswith(("Current runtime", "<system-reminder", "Time sampled",
                                           "background job", "This is an automatically")):
                user_msgs.append(txt.replace("\n", " ")[:300])
        elif t == "tool/call":
            args = data.get("arguments")
            if isinstance(args, str) and CALL.search(args):
                frcli_call_ids.add((data.get("callId") or "").split("|")[0])
                frcli_cmds.append(args.replace("\\n", " ")[:300])
        elif t == "tool/result":
            # ⚠ 两处坑，都会让配对全失败（实测：报错片段恒为 0，漏掉全部真实报错）：
            #   ① 结果侧的 toolCallId **嵌在 `data.message` 里**，不在顶层；
            #   ② id 形如 `call_xx|<session-uuid>` —— 两边都带后缀，直接比原串即可，
            #      但要防某一侧没有后缀，所以统一切掉 `|` 之后的部分。
            msg = data.get("message") or {}
            raw_id = (data.get("toolCallId") or msg.get("toolCallId")
                      or data.get("callId") or (msg.get("source") or {}).get("callId") or "")
            cid = str(raw_id).split("|")[0]
            blob = json.dumps(data, ensure_ascii=False)
            results[cid] = blob

    # 报错**只取 frcli 调用对应的结果**（否则会把知识库正文、别的工具的报错混进来）
    for cid in frcli_call_ids:
        blob = results.get(cid)
        if not blob:
            continue
        if not (ERR.search(blob) or FRCLI_ERR.search(blob)):
            continue
        for m in FRCLI_ERR.finditer(blob):
            errors.append(blob[max(0, m.start() - 140):m.start() + 200].replace("\\n", " "))
        if not FRCLI_ERR.search(blob):
            for m in ERR.finditer(blob):
                errors.append(blob[max(0, m.start() - 140):m.start() + 200].replace("\\n", " "))
                break
    return {"user_msgs": user_msgs, "frcli_cmds": frcli_cmds, "errors": errors}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--date", help="只扫这一天（YYYY-MM-DD）；缺省=昨天")
    ap.add_argument("--days", type=int, help="扫最近 N 天（含今天）")
    ap.add_argument("--all", action="store_true", help="扫全部会话")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--max-errors", type=int, default=12)
    args = ap.parse_args()

    if args.all:
        lo = None
    elif args.days:
        lo = dt.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - dt.timedelta(days=args.days - 1)
    else:
        day = (dt.date.fromisoformat(args.date) if args.date
               else dt.date.today() - dt.timedelta(days=1))
        lo = dt.datetime.combine(day, dt.time.min)
    hi = lo + dt.timedelta(days=1) if (lo and not args.days) else None

    # ⚠ 必须按**记录里的时间戳**切窗口，不能按文件 mtime：
    # 会话会跨天延续（实测：09-30 跑的会话，文件 mtime 是 10-01 —— 被会话后续活动刷新）。
    # 文件 mtime 只用来做廉价预筛（往前多留几天，避免漏掉长时间挂着的会话）。
    pre = (lo - dt.timedelta(days=7)) if lo else None
    picked = [(f, m) for f, m in iter_sessions() if pre is None or m >= pre]
    picked.sort(key=lambda x: x[1])

    report = []
    for f, mtime in picked:
        all_rows = read_session(f)
        if not all_rows:
            continue
        rows = all_rows
        if lo is not None:
            rows = [r for r in rows if (t := ts(r)) and lo <= t and (hi is None or t < hi)]
        if not rows:
            continue                     # 该窗口内没有活动
        res = scan(rows)
        if not res["frcli_cmds"]:
            continue                     # 没真的调用过 frcli → 与本 skill 无关，跳过
        cwd = next((r.get("cwd") for r in all_rows if r.get("cwd")), "?")
        report.append({"file": str(f), "cwd": cwd, "records": len(rows), **res})

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    if not report:
        print("（该时间段内没有与本 skill 相关的会话）")
        return 0

    print(f"# 会话扫描：{len(report)} 个相关会话"
          f"（{lo:%Y-%m-%d} 起）" if lo else f"# 会话扫描：{len(report)} 个相关会话（全部）")
    for s in report:
        print(f"\n## {pathlib.Path(s['file']).parent.name}")
        print(f"   cwd: {s['cwd']}   记录: {s['records']}"
              f"   frcli 调用: {len(s['frcli_cmds'])}   报错片段: {len(s['errors'])}")
        if s["user_msgs"]:
            print("   ── 用户诉求（可能含痛点）──")
            for m in s["user_msgs"][:20]:
                flag = "  ⚠" if COMPLAINT.search(m) else "   "
                print(f"   {flag} {m[:220]}")
        if s["errors"]:
            print("   ── 报错（去重后前几条）──")
            seen = set()
            for e in s["errors"][:args.max_errors]:
                key = e[:80]
                if key in seen:
                    continue
                seen.add(key)
                print(f"      {e[:260]}")
    print("\n> 下一步：把上面的报错/痛点逐条**复现验证**，确认是本 skill 的问题再改；"
          "改完回归测试 + 打包 + 推送（见 AGENTS.md 与 docs/发布与脱敏.md）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
