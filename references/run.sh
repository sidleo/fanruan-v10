#!/usr/bin/env bash
# frcli Unix 便捷入口 (macOS / Linux)。
# 逻辑与 references/run.py 一致: 先直接执行, 找不到才回退 skill 内置源码。
# Windows 请使用 references/run.py (python run.py <args>), .sh 在 Windows 不可用。
#
# 用法: run.sh <frcli 参数...>

# 方式 1: 直接调用 PATH 中的命令 (正常环境零开销)
if command -v frcli >/dev/null 2>&1; then
  exec frcli "$@"
fi

# 方式 2: 回退 skill 内置源码 (不依赖 PATH / HOME / 安装位置)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="$(cd "$SCRIPT_DIR/.." && pwd)/src"

if [ ! -f "$SRC_DIR/frcli/cli.py" ]; then
  echo "frcli 不可用: PATH 中无该命令, 且 skill 内置源码缺失。" >&2
  echo "请按 references/install.md 自举安装。" >&2
  exit 127
fi

# 找一个带依赖 (click/httpx/pyyaml/rich) 的 Python 解释器
pick_python() {
  local cand
  for cand in \
    "$(command -v python3 2>/dev/null)" \
    "$(command -v python 2>/dev/null)" \
    "/Library/Frameworks/Python.framework/Versions/Current/bin/python3" \
    "/usr/local/bin/python3" \
    "/opt/homebrew/bin/python3" \
    "/usr/bin/python3"; do
    [ -z "$cand" ] && continue
    if "$cand" -c "import importlib.util; raise SystemExit(0 if all(importlib.util.find_spec(m) for m in ['click','httpx','yaml','rich']) else 1)" >/dev/null 2>&1; then
      echo "$cand"
      return 0
    fi
  done
  return 1
}

PY="$(pick_python)"
if [ -z "$PY" ]; then
  echo "frcli 不可用: 未找到带依赖(click/httpx/pyyaml/rich)的 Python。" >&2
  echo "请按 references/install.md 自举安装 (pip install -e 或安装依赖后重试)。" >&2
  exit 127
fi

cd "$SRC_DIR" && PYTHONPATH="$SRC_DIR${PYTHONPATH:+:$SRC_DIR:$PYTHONPATH}" exec "$PY" -m frcli "$@"
