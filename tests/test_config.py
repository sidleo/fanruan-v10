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


def test_explicit_instance_error_says_explicit_not_default(tmp_path, monkeypatch):
    """回归（2026-11-19 真实会话）：`frcli -i push-v10` 传错实例名时，报「默认实例」会误导排查。"""
    import frcli.config as config_mod
    from frcli.config import load_config
    from frcli.exceptions import ConfigError

    cfg = tmp_path / "config.yaml"
    cfg.write_text("default: 推送v10\ninstances:\n  推送v10:\n    url: https://x\n"
                   "    username: u\n    password: p\n", encoding="utf-8")
    monkeypatch.setattr(config_mod, "CONFIG_SEARCH_PATHS", [lambda: cfg])
    monkeypatch.delenv("FRCLI_INSTANCE", raising=False)

    monkeypatch.setattr(config_mod, "CLI_INSTANCE", "push-v10")
    with pytest.raises(ConfigError) as ei:
        load_config()
    assert "指定实例 'push-v10' 不存在" in str(ei.value)

    # 没显式指定、默认实例名写错时仍说「默认实例」
    monkeypatch.setattr(config_mod, "CLI_INSTANCE", None)
    with pytest.raises(ConfigError) as ei2:
        load_config("typo-name")
    assert "实例 'typo-name' 不存在" in str(ei2.value)
