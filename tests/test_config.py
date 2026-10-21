"""配置模块测试"""

import pytest
from frcli.config import load_full_config, list_instances


def _isolate_config(tmp_path, monkeypatch):
    """把配置查找路径彻底隔离：不落回本机真实 `~/.frcli/config.yaml`。

    `load_full_config()` 走的是 `CONFIG_SEARCH_PATHS`（`_find_config_file()`），
    只改 `DEFAULT_CONFIG_PATH` 不生效 —— 实测环境有真实配置文件时会读到真实例。
    """
    import frcli.config as config_mod

    monkeypatch.setattr(config_mod, "CONFIG_SEARCH_PATHS", [])
    monkeypatch.setattr(config_mod, "DEFAULT_CONFIG_PATH", tmp_path / "config.yaml")
    monkeypatch.delenv("FRCLI_CONFIG", raising=False)


def test_load_empty_config(tmp_path, monkeypatch):
    """测试加载空配置"""
    _isolate_config(tmp_path, monkeypatch)
    result = load_full_config()
    assert result["instances"] == {}


def test_list_instances_empty(tmp_path, monkeypatch):
    """测试列出空实例"""
    _isolate_config(tmp_path, monkeypatch)
    assert list_instances() == []
