"""数据模型"""

from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path


@dataclass
class ServerConfig:
    """FineReport 服务器配置"""
    name: str
    url: str
    username: str
    password: Optional[str] = None
    workspace: str = "/webroot"
    token_file: Optional[Path] = None

    def __post_init__(self):
        if self.token_file is None:
            self.token_file = Path.home() / ".frcli" / "tokens" / f"{self.name}.json"


@dataclass
class TokenCache:
    """Token 缓存"""
    instance: str
    token: str
    expires_at: float
    created_at: float
    cookies: dict = field(default_factory=dict)


@dataclass
class ReportInfo:
    """报表文件信息"""
    name: str
    path: str
    is_directory: bool = False
    size: Optional[int] = None
    modified: Optional[str] = None
