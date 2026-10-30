#!/usr/bin/env bash
# 打包 skill：把当前工作树打成 dist/fanruan-v10.skill（zip，根目录 fanruan-v10/）
#
# 用法：
#   tools/build_skill.sh              # 复扫 → 打包
#   tools/build_skill.sh --check      # 只复扫，不打也不写
#
# ⚠️ 本仓库必须保持"脱敏"状态（只写能力、不写环境）。真实值与黑名单**不放在仓库里**：
#    黑名单从 `$FRCLI_REDACT_BLACKLIST`（一条 grep -E 正则）或 `~/.frcli/redact-blacklist.txt`
#    读取；两者都没有就**拒绝运行**（fail-closed）。处置见 docs/发布与脱敏.md。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

load_blacklist() {
    if [ -n "${FRCLI_REDACT_BLACKLIST:-}" ]; then
        printf '%s' "$FRCLI_REDACT_BLACKLIST"; return 0
    fi
    local f="${HOME}/.frcli/redact-blacklist.txt"
    if [ -f "$f" ]; then
        grep -v '^[[:space:]]*#' "$f" | grep -v '^[[:space:]]*$' | paste -sd'|' -
        return 0
    fi
    echo "❌ 找不到黑名单：既没设 \$FRCLI_REDACT_BLACKLIST，也没有 $f" >&2
    echo "   黑名单 = 需要脱敏的真实值（姓名/工号/域名/组织/真实报表名/环境路径），一条一行的正则。" >&2
    echo "   为什么放在仓库外：本仓库对外发布，不能包含这些值本身。" >&2
    return 1
}

check() {
    local bl; bl="$(load_blacklist)" || return 1
    local bad=0 n rc=0 scanned=0

    # ⚠️ 先把黑名单正则本身验一遍：下面每处 count 都带 `|| true`（0 命中时 grep 退出码 1 会
    # 被 set -e 放大成静默中断）。但 `|| true` 会把 grep 的**用法错误**（退出码 2，如正则括号不平衡）
    # 一并吞掉 ⇒ 门禁变成"静默放行"（实测 `FRCLI_REDACT_BLACKLIST='[' …--check` 报 ✅ 全 0 且 exit 0，
    # 与"黑名单缺失即 fail-closed"的设计相反）。所以：不可编译的正则必须明确报错并非 0 退出。
    grep -E "$bl" /dev/null >/dev/null 2>&1 || rc=$?
    if [ "$rc" -gt 1 ]; then
        echo "❌ 黑名单正则无法编译（grep 退出码 ${rc}）—— 拒绝继续，避免把「扫不动」当成「扫干净」：" >&2
        echo "   $bl" >&2
        return 1
    fi

    echo "—— ① 工作树文本 ——"
    # ⚠️ 末尾的 `|| true` 不能省：`set -euo pipefail` 下，0 命中时 grep 退出码是 1，
    # pipefail 让整条管线失败 ⇒ 赋值命令触发 set -e 直接退出，门禁只打了表头就"结束"
    # （既没有命中数、也没扫②③、也没结论 —— 2026-10 实测：exit=1、stdout 只有这行）。
    n=$(grep -rIoE "$bl" . \
          --exclude-dir=.git --exclude-dir=__pycache__ --exclude-dir=.pytest_cache \
          --exclude-dir=dist --exclude-dir=node_modules 2>/dev/null | wc -l | tr -d ' ' || true)
    echo "   命中 $n"; if [ "$n" != "0" ]; then bad=1;
        grep -rIlE "$bl" . --exclude-dir=.git --exclude-dir=dist 2>/dev/null | sed 's/^/     /' | head -5
    fi
    scanned=$((scanned + 1))

    if [ -f dist/fanruan-v10.skill ]; then
        echo "—— ② 包内文本（zip 要解开扫：grep 扫不到压缩内容）——"
        local tmp; tmp=$(mktemp -d)
        # 包损坏时必须**明确失败并清理临时目录**：老写法被 set -e 直接打断 → exit 9、③ 不扫、
        # mktemp 目录留在 TMPDIR 里（实测）。方向虽安全（非 0），但报错不可读、且脏了磁盘。
        if ! unzip -q dist/fanruan-v10.skill -d "$tmp"; then
            echo "❌ dist/fanruan-v10.skill 无法解开（zip 损坏？）—— ③ 历史未扫；先修包再发布" >&2
            rm -rf "$tmp"
            return 1
        fi
        n=$(grep -rIoE "$bl" "$tmp" 2>/dev/null | wc -l | tr -d ' ' || true)
        echo "   命中 $n"; [ "$n" != "0" ] && bad=1
        rm -rf "$tmp"
        scanned=$((scanned + 1))
    else
        echo "—— ② 包内文本 ——"
        echo "   （dist/fanruan-v10.skill 不存在，② 未扫；打包后请再跑一次 --check，那次 ② 扫的就是新包）"
    fi

    echo "—— ③ git 历史（仓库一旦公开，每条提交都可见）——"
    # 同一类坑：循环体里 `grep -c` 0 命中时退出码 1，会让 while 子壳带非 0 退出，
    # 再被 pipefail + set -e 放大成整段静默中断 ⇒ 每轮末尾兜底 `|| true`（计数仍照常打印）。
    n=$(git rev-list --all --objects 2>/dev/null | awk '{print $1}' | sort -u | while read -r h; do
          [ "$(git cat-file -t "$h" 2>/dev/null)" = blob ] && git cat-file blob "$h" 2>/dev/null | grep -cE "$bl" || true
        done | awk '{s+=$1} END {print s+0}')
    echo "   命中 $n"; [ "$n" != "0" ] && bad=1
    scanned=$((scanned + 1))

    if [ "$bad" != "0" ]; then
        echo
        echo "❌ 有敏感信息，**不要打包/不要推**：按 docs/发布与脱敏.md 处理（含历史重写）。"
        return 1
    fi
    echo
    # 结论行按**实际扫了几处**说：② 在 dist 无包时不执行，写死"三处"会让人以为包也扫过了。
    if [ "$scanned" = "3" ]; then
        echo "✅ 三处复扫全 0"
    else
        echo "✅ 已扫 ${scanned} 处，全部 0 命中（② 未执行：dist 无包 —— 打包后请再跑一次 --check）"
    fi
}

if [ "${1:-}" = "--check" ]; then check; exit $?; fi

check || exit 1

echo "—— 打包 ——"
TMP=$(mktemp -d)
mkdir -p "$TMP/fanruan-v10"
for p in SKILL.md README.md AGENTS.md pyproject.toml .gitignore src tests references docs tools; do
    [ -e "$p" ] && cp -R "$p" "$TMP/fanruan-v10/"
done
mkdir -p dist
rm -f dist/fanruan-v10.skill
# Python 会为中文等非 ASCII 文件名设置 UTF-8 标志；本机 zip 未标记时，安装器会按 CP437 解出乱码。
python3 - "$TMP" "$ROOT/dist/fanruan-v10.skill" <<'PY'
from pathlib import Path
import sys
import zipfile

staging = Path(sys.argv[1])
with zipfile.ZipFile(sys.argv[2], "w", compression=zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(staging.rglob("*")):
        relative = path.relative_to(staging)
        if not path.is_file():
            continue
        if any(part in {"__pycache__", ".pytest_cache"} or part.endswith(".egg-info")
               for part in relative.parts):
            continue
        if path.suffix == ".pyc" or path.name == ".DS_Store":
            continue
        archive.write(path, relative.as_posix())
PY
rm -rf "$TMP"

VER=$(grep -m1 '__version__' src/frcli/__init__.py | cut -d'"' -f2)
SIZE=$(stat -f%z dist/fanruan-v10.skill 2>/dev/null || stat -c%s dist/fanruan-v10.skill)
echo "✅ dist/fanruan-v10.skill  ${SIZE} B  v$VER"
# ⚠️ 顺序陷阱：`check` 在打包**之前**跑，② 扫的是上一次留下的旧包。要证明"即将推送的包"干净，
#    打包后必须**再跑一次** `--check`（此时 ② 才扫到刚生成的这个包）。
echo "   下一步：tools/build_skill.sh --check（复扫新包）→ git add dist/fanruan-v10.skill && git commit && git push"
