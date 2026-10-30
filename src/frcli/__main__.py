"""支持 python -m frcli 执行"""

import os
import sys


def _drop_cwd_from_sys_path() -> None:
    """把运行目录从 sys.path 移除，避免 cwd 里与标准库/依赖同名的 .py 抢占导入。

    典型：`cd /tmp && frcli ...` 时 /tmp/inspect.py 会让 `import click` 命中它
    （click 内部 `import inspect`），CLI 启动即 Traceback。`python -m frcli`
    的 sys.path[0] 是 ''（Python 3.10）或 cwd 绝对路径（3.11+），本函数在导入 click
    之前把它们去掉；CLI 不需要从 cwd 导入任何模块，正常用法不受影响。
    """
    try:
        cwd = os.path.realpath(os.getcwd())
    except OSError:
        cwd = None
    kept = []
    for entry in sys.path:
        if entry in ("", "."):
            continue
        if cwd is not None:
            try:
                if os.path.realpath(entry) == cwd:
                    continue
            except OSError:
                pass
        kept.append(entry)
    sys.path[:] = kept


_drop_cwd_from_sys_path()

from frcli.cli import main  # noqa: E402  （必须先清理 sys.path 再导入 click）

if __name__ == "__main__":
    main()
