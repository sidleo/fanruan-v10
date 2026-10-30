"""`python -m frcli` 在含同名 .py 的目录（cwd 遮蔽标准库）仍能启动。"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _run_in_shadow_dir(tmp_path: Path, module_name: str):
    (tmp_path / f"{module_name}.py").write_text(
        'raise RuntimeError("cwd shadow: this file must not be imported")\n',
        encoding="utf-8",
    )
    env = dict(os.environ)
    env.pop("PYTHONSAFEPATH", None)  # 该变量也会把 cwd 移出 sys.path，会让本测试空过
    env["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, "-m", "frcli", "--version"],
        cwd=tmp_path, text=True, capture_output=True, env=env,
    )


@pytest.mark.parametrize("module_name", ["inspect", "json", "click"])
def test_cli_starts_even_if_cwd_shadows_stdlib_module(tmp_path, module_name):
    """回归（2026-10-30 真实会话）：cd /tmp 后 /tmp/inspect.py 让 import click 崩溃。"""
    result = _run_in_shadow_dir(tmp_path, module_name)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "frcli, version" in result.stdout
