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
    local bad=0 n

    echo "—— ① 工作树文本 ——"
    n=$(grep -rIoE "$bl" . \
          --exclude-dir=.git --exclude-dir=__pycache__ --exclude-dir=.pytest_cache \
          --exclude-dir=dist --exclude-dir=node_modules 2>/dev/null | wc -l | tr -d ' ')
    echo "   命中 $n"; if [ "$n" != "0" ]; then bad=1;
        grep -rIlE "$bl" . --exclude-dir=.git --exclude-dir=dist 2>/dev/null | sed 's/^/     /' | head -5
    fi

    if [ -f dist/fanruan-v10.skill ]; then
        echo "—— ② 包内文本（zip 要解开扫：grep 扫不到压缩内容）——"
        local tmp; tmp=$(mktemp -d)
        unzip -q dist/fanruan-v10.skill -d "$tmp"
        n=$(grep -rIoE "$bl" "$tmp" 2>/dev/null | wc -l | tr -d ' ')
        echo "   命中 $n"; [ "$n" != "0" ] && bad=1
        rm -rf "$tmp"
    fi

    echo "—— ③ git 历史（仓库一旦公开，每条提交都可见）——"
    n=$(git rev-list --all --objects 2>/dev/null | awk '{print $1}' | sort -u | while read -r h; do
          [ "$(git cat-file -t "$h" 2>/dev/null)" = blob ] && git cat-file blob "$h" 2>/dev/null | grep -cE "$bl"
        done | awk '{s+=$1} END {print s+0}')
    echo "   命中 $n"; [ "$n" != "0" ] && bad=1

    if [ "$bad" != "0" ]; then
        echo
        echo "❌ 有敏感信息，**不要打包/不要推**：按 docs/发布与脱敏.md 处理（含历史重写）。"
        return 1
    fi
    echo
    echo "✅ 三处复扫全 0"
}

if [ "${1:-}" = "--check" ]; then check; exit $?; fi

check || exit 1

echo "—— 打包 ——"
TMP=$(mktemp -d)
mkdir -p "$TMP/fanruan-v10"
for p in SKILL.md README.md AGENTS.md pyproject.toml .gitignore src tests references tools; do
    [ -e "$p" ] && cp -R "$p" "$TMP/fanruan-v10/"
done
mkdir -p dist
rm -f dist/fanruan-v10.skill
( cd "$TMP" && zip -qr "$ROOT/dist/fanruan-v10.skill" fanruan-v10 \
    -x "*/__pycache__/*" "*.pyc" "*.DS_Store" "*/.pytest_cache/*" "*/frcli.egg-info/*" )
rm -rf "$TMP"

VER=$(grep -m1 '__version__' src/frcli/__init__.py | cut -d'"' -f2)
SIZE=$(stat -f%z dist/fanruan-v10.skill 2>/dev/null || stat -c%s dist/fanruan-v10.skill)
echo "✅ dist/fanruan-v10.skill  ${SIZE} B  v$VER"
echo "   下一步：git add dist/fanruan-v10.skill && git commit && git push"
