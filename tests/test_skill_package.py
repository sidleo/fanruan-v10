"""发布包在标准安装器中保留中文路径和文档内容。"""

import os
from pathlib import Path
import shutil
import subprocess
import zipfile


def test_package_extracts_chinese_documentation_and_omits_cache(tmp_path):
    root = Path(__file__).resolve().parents[1]
    tools = tmp_path / "tools"
    tools.mkdir()
    shutil.copy2(root / "tools/build_skill.sh", tools / "build_skill.sh")
    source = tmp_path / "src/frcli"
    source.mkdir(parents=True)
    (source / "__init__.py").write_text('__version__ = "0.0.0"\n')
    cache = source / "__pycache__"
    cache.mkdir()
    (cache / "stale.pyc").write_bytes(b"cache")
    (tmp_path / "README.md").write_text("[中文文档](docs/验证/结构说明.md)\n")
    document = tmp_path / "docs/验证/结构说明.md"
    document.parent.mkdir(parents=True)
    document.write_text("# 结构检查\n\n每个区块使用独立坐标。\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)

    result = subprocess.run(
        ["bash", "tools/build_skill.sh"], cwd=tmp_path, text=True, capture_output=True,
        env={**os.environ, "FRCLI_REDACT_BLACKLIST": "REDACTION_TEST_SENTINEL"},
    )
    assert result.returncode == 0, result.stdout + result.stderr
    with zipfile.ZipFile(tmp_path / "dist/fanruan-v10.skill") as archive:
        entry = archive.getinfo("fanruan-v10/docs/验证/结构说明.md")
        assert entry.flag_bits & 0x800
        assert not any("__pycache__" in name for name in archive.namelist())
        destination = tmp_path / "installed"
        archive.extractall(destination)
    assert (destination / "fanruan-v10/docs/验证/结构说明.md").read_bytes() == document.read_bytes()
