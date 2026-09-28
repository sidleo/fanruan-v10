#!/usr/bin/env python3
"""frcli 跨平台启动器（Windows / macOS / Linux 通用）。

用途:
  fanruan_v10 skill 内置源码的零安装执行入口。无论 `frcli` 命令是否已安装、
  是否在 PATH 中, 都可以用本脚本启动:
      python run.py <frcli 参数...>

执行逻辑（先直接执行, 找不到才自举）:
  1. 若 `frcli` 命令在 PATH 中 -> 直接调用它 (正常环境零开销);
  2. 否则回退到本 skill 内置源码: 将 <skill base>/src 加入 PYTHONPATH,
     以 `python -m frcli` 方式运行 (不依赖 PATH / HOME / 安装位置);
  3. 当前 Python 缺依赖 (click/httpx/yaml/rich) 时, 自动探测其他 Python 解释器;
  4. 自举成功后尝试在可写的 PATH 目录建 `frcli` 软链 -> references/frcli shim,
     之后直接敲 `frcli` 即可 (建链失败不影响本次执行);
  5. 仍失败 -> 给出 references/install.md 的指引。

依赖: click、httpx、pyyaml、rich。
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

# 本文件位于 <skill base>/references/run.py
SKILL_BASE = Path(__file__).resolve().parent.parent
SRC_DIR = SKILL_BASE / "src"
SHIM = SKILL_BASE / "references" / "frcli"
DEPS = ("click", "httpx", "yaml", "rich")

# 候选 Python 解释器: 当前进程 + 常见安装位置 (按优先级)
_PY_CANDIDATES = [
    sys.executable,
    "python3",
    "python",
    "/Library/Frameworks/Python.framework/Versions/Current/bin/python3",
    "/usr/local/bin/python3",
    "/opt/homebrew/bin/python3",
    "/usr/bin/python3",
    "py",  # Windows: Python Launcher
]

# 建链时跳过系统级目录（通常无写权限）
_SKIP_PREFIXES = ("/usr/bin", "/bin", "/usr/sbin", "/sbin", "/usr/local/sbin")


def _has_deps(python: str) -> bool:
    """探测某个 Python 解释器是否具备所需依赖。"""
    code = (
        "import importlib.util; "
        f"raise SystemExit(0 if all(importlib.util.find_spec(m) for m in {DEPS!r}) else 1)"
    )
    try:
        return (
            subprocess.call(
                [python, "-c", code],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            == 0
        )
    except OSError:
        return False


def _find_python_with_deps() -> str | None:
    """探测带依赖的 Python: 当前进程优先, 其次常见安装位置。"""
    seen: set[str] = set()
    for cand in _PY_CANDIDATES:
        resolved = shutil.which(cand) or cand
        if resolved in seen:
            continue
        seen.add(resolved)
        if _has_deps(resolved):
            return resolved
    return None


#: 递归护栏：方式 1 会把控制权交给 PATH 里的 `frcli`。如果那个 `frcli` 恰好是
#: **指向本文件的 shim**（历史上有人这么装），就会 run.py → shim → run.py → … 无限自我复制
#: （2026-09 实测：1600+ 个 Python 进程链式繁殖，机器被拖死，只能反复 pkill -9）。
#: 所以进入方式 1 前打一个环境标记；嵌套进来的 run.py 看到标记就跳过方式 1。
_ENV_DEPTH = "FRCLI_RUNPY_DEPTH"
_MAX_DEPTH = 3


def _run_direct(args: list[str]) -> int | None:
    """方式 1: 直接调用 PATH 中的 frcli 命令。找不到/怀疑递归时返回 None。"""
    depth = int(os.environ.get(_ENV_DEPTH, "0") or "0")
    if depth >= 1:
        # 已经在 run.py 的调用链里了：PATH 里的 frcli 很可能又指回本文件 -> 不碰方式 1
        return None
    exe = shutil.which("frcli")
    if not exe:
        return None
    # 再兜一层：解析软链后若就是本文件（或本 skill 的 run.py），直接不做方式 1
    try:
        real = os.path.realpath(exe)
    except OSError:
        real = exe
    if os.path.realpath(__file__) == real:
        return None
    if real.endswith(os.sep + "run.py") and str(SKILL_BASE) in real:
        return None
    env = dict(os.environ)
    env[_ENV_DEPTH] = str(depth + 1)
    if depth + 1 > _MAX_DEPTH:
        print(f"frcli 启动器递归过深（{depth + 1} 层），已中止；"
              f"检查 PATH 里的 frcli 是否指向 {__file__}", file=sys.stderr)
        return 127
    return subprocess.call([exe, *args], env=env)


def _run_src_module(args: list[str]) -> int | None:
    """方式 2: 用 skill 内置源码以 python -m frcli 方式运行。"""
    if not (SRC_DIR / "frcli" / "cli.py").is_file():
        return None
    python = _find_python_with_deps()
    if not python:
        return None
    env = dict(os.environ)
    # 把 src 放到最前, 保证 import 命中 skill 内置源码
    env["PYTHONPATH"] = str(SRC_DIR) + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.call(
        [python, "-m", "frcli", *args],
        env=env,
        # ⚠ 不要改 cwd：`-m frcli` 靠 PYTHONPATH 就能解析，而传 cwd=SRC_DIR 会把
        # 用户的**相对路径参数**（`-o out.xlsx`、`report upload x.cpt`）解析到 skill 源码目录 ——
        # 实测：从 /tmp 跑 `export -o relout.xlsx`，文件落在了 <skill>/src/ 下（静默写错地方）。
    )


def _ensure_symlink() -> None:
    """自举成功后, 在 PATH 中建 frcli 软链 -> references/frcli shim。

    同时做软链自愈: 已有 frcli 软链但指向的不是当前 skill 的 shim（旧路径/失效路径）
    时重建指向当前 skill, 保证 skill 搬家后自动切到新代码。失败静默跳过。
    """
    try:
        if not SHIM.is_file():
            return
        for d in os.environ.get("PATH", "").split(os.pathsep):
            if not d:
                continue
            d = os.path.expanduser(d)
            if d.startswith(_SKIP_PREFIXES) or not os.path.isdir(d):
                continue
            target = os.path.join(d, "frcli")
            if os.path.lexists(target):
                try:
                    cur = os.readlink(target)
                    if Path(cur).resolve() == SHIM.resolve():
                        return  # 已指向当前 skill
                except OSError:
                    return  # 真实文件（非软链）, 不动它
            if not os.access(d, os.W_OK):
                continue
            try:
                if os.path.lexists(target):
                    os.remove(target)
                os.symlink(str(SHIM), target)
                return
            except OSError:
                continue  # 权限/平台失败, 试下一个目录
    except Exception:
        pass  # 建链失败不致命


def _check_version_consistency() -> None:
    """若 PATH 中的 frcli 来自其他安装(pip/别的 skill 副本), 提示来源与内置版本。仅提示。"""
    try:
        exe = shutil.which("frcli")
        if not exe:
            return
        if os.path.islink(exe):
            try:
                if Path(os.readlink(exe)).resolve() == SHIM.resolve():
                    return  # 用的就是本 skill 源码
            except OSError:
                pass
        init = SRC_DIR / "frcli" / "__init__.py"
        ver = "?"
        if init.is_file():
            for line in init.read_text(encoding="utf-8").splitlines():
                if line.strip().startswith("__version__"):
                    ver = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
        print(f"[fanruan_v10] 当前 PATH 中的 frcli 来自: {exe}", file=sys.stderr)
        print(
            f"[fanruan_v10] 本 skill 内置源码版本: {ver}（如需用本版本请重建软链/重装）",
            file=sys.stderr,
        )
    except Exception:
        pass


def main() -> int:
    args = sys.argv[1:]
    code = _run_direct(args)
    if code is not None:
        _check_version_consistency()
        return code

    code = _run_src_module(args)
    if code is not None:
        _ensure_symlink()
        return code

    print(
        "frcli 不可用: PATH 中无该命令, 且未找到带依赖(click/httpx/pyyaml/rich)的 Python。\n"
        "请按 references/install.md 自举安装 (pip install -e 或安装依赖后重试)。",
        file=sys.stderr,
    )
    return 127


if __name__ == "__main__":
    sys.exit(main())
