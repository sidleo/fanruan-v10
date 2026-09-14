"""配置文件管理 - 支持多实例"""

import os
import yaml
from pathlib import Path
from typing import Optional
from .models import ServerConfig
from .exceptions import ConfigError


CONFIG_SEARCH_PATHS = [
    lambda: Path(os.environ.get("FRCLI_CONFIG", "")) if os.environ.get("FRCLI_CONFIG") else None,
    lambda: Path.home() / ".frcli" / "config.yaml",
    lambda: Path.cwd() / ".frcli.yaml",
]

CONFIG_DIR = Path.home() / ".frcli"
DEFAULT_CONFIG_PATH = CONFIG_DIR / "config.yaml"


def _find_config_file() -> Optional[Path]:
    """查找配置文件"""
    for path_factory in CONFIG_SEARCH_PATHS:
        path = path_factory()
        if path and path.exists():
            return path
    return None


def load_full_config() -> dict:
    """加载完整配置文件"""
    path = _find_config_file()
    if not path:
        return {"default": None, "instances": {}}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {"default": None, "instances": {}}


def load_config(name: str = None) -> ServerConfig:
    """加载指定实例的配置。name=None 时使用 default。"""
    config = load_full_config()
    instances = config.get("instances", {})

    if not instances:
        raise ConfigError("未配置任何 FineReport 实例。使用 `frcli server add` 添加实例。")

    if name is None:
        name = config.get("default")
        if not name:
            name = next(iter(instances))
        if name not in instances:
            raise ConfigError(f"默认实例 '{name}' 不存在。可用实例: {list(instances.keys())}")

    if name not in instances:
        raise ConfigError(f"实例 '{name}' 不存在。可用实例: {list(instances.keys())}")

    inst = instances[name]
    return ServerConfig(
        name=name,
        url=inst["url"],
        username=inst["username"],
        password=inst.get("password"),
        workspace=inst.get("workspace", "/webroot"),
    )


def list_instances() -> list[str]:
    """列出所有已配置的实例名称。"""
    config = load_full_config()
    return list(config.get("instances", {}).keys())


def get_default_instance() -> Optional[str]:
    """获取默认实例名"""
    config = load_full_config()
    return config.get("default")


def save_instance(name: str, url: str, username: str, password: str = None,
                  workspace: str = "/webroot", set_default: bool = False):
    """保存/更新实例配置"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    config = load_full_config()
    if "instances" not in config:
        config["instances"] = {}

    config["instances"][name] = {
        "url": url.rstrip("/"),
        "username": username,
        "workspace": workspace,
    }
    if password:
        config["instances"][name]["password"] = password

    if set_default or not config.get("default"):
        config["default"] = name

    with open(DEFAULT_CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False)


def remove_instance(name: str):
    """删除实例配置"""
    config = load_full_config()
    instances = config.get("instances", {})

    if name not in instances:
        raise ConfigError(f"实例 '{name}' 不存在")

    del instances[name]

    if config.get("default") == name:
        config["default"] = next(iter(instances), None)

    with open(DEFAULT_CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False)

    # 清理 token 缓存
    token_file = Path.home() / ".frcli" / "tokens" / f"{name}.json"
    if token_file.exists():
        token_file.unlink()


def set_default_instance(name: str):
    """设置默认实例"""
    config = load_full_config()
    instances = config.get("instances", {})

    if name not in instances:
        raise ConfigError(f"实例 '{name}' 不存在")

    config["default"] = name

    with open(DEFAULT_CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False)
