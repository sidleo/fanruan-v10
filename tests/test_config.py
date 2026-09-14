"""配置模块测试"""

import pytest
from pathlib import Path
from frcli.config import load_full_config, list_instances
from frcli.exceptions import ConfigError


def test_load_empty_config(tmp_path):
    """测试加载空配置"""
    import frcli.config as config_mod
    original = config_mod.DEFAULT_CONFIG_PATH
    config_mod.DEFAULT_CONFIG_PATH = tmp_path / "config.yaml"

    try:
        result = load_full_config()
        assert result["instances"] == {}
    finally:
        config_mod.DEFAULT_CONFIG_PATH = original


def test_list_instances_empty(tmp_path):
    """测试列出空实例"""
    import frcli.config as config_mod
    original = config_mod.DEFAULT_CONFIG_PATH
    config_mod.DEFAULT_CONFIG_PATH = tmp_path / "config.yaml"

    try:
        instances = list_instances()
        assert instances == []
    finally:
        config_mod.DEFAULT_CONFIG_PATH = original
