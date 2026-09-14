"""JWT token 认证管理"""

import json
import time
import getpass
from pathlib import Path
from typing import Optional
from .models import ServerConfig, TokenCache
from .exceptions import AuthError, ConnectionError


TOKEN_CACHE_DIR = Path.home() / ".frcli" / "tokens"


class TokenManager:
    """JWT token 管理：获取、缓存、刷新"""

    def __init__(self, config: ServerConfig):
        self.config = config
        self._token: Optional[str] = None
        self._expires_at: float = 0
        self._cookies: dict = {}

    def get_valid_token(self) -> Optional[str]:
        """获取有效的 token，必要时从缓存或服务器获取"""
        # 内存缓存有效
        if self._token and time.time() < self._expires_at:
            return self._token

        # 尝试从文件缓存加载
        cached = self._load_cached_token()
        if cached and time.time() < cached.expires_at:
            self._token = cached.token
            self._expires_at = cached.expires_at
            self._cookies = cached.cookies
            return self._token

        # 需要登录
        return None

    def get_cookies(self) -> dict:
        """获取缓存的 cookies"""
        return self._cookies

    def login(self, http_client) -> str:
        """登录获取新 token"""
        password = self.config.password
        if not password:
            password = getpass.getpass(f"请输入 {self.config.username} 的密码: ")

        try:
            # FineReport 登录端点 (v10 决策平台)
            login_url = f"{self.config.workspace}/decision/login"
            resp = http_client.post(
                login_url,
                json={
                    "username": self.config.username,
                    "password": password,
                },
                headers={"Content-Type": "application/json"},
            )

            if resp.status_code != 200:
                raise AuthError(f"登录失败: HTTP {resp.status_code}")

            # 从响应体获取 token
            data = resp.json()
            token = data.get("data", {}).get("accessToken")

            if not token:
                # 尝试其他字段
                token = data.get("accessToken") or data.get("token")

            if not token:
                raise AuthError("登录失败: 未获取到认证 token")

            # 保存 cookies 到 http_client 和内存
            cookies = {}
            for name, value in resp.cookies.items():
                http_client.cookies.set(name, value)
                cookies[name] = value

            # 缓存 token (默认 24 小时有效)
            self._token = token
            self._expires_at = time.time() + 86400
            self._cookies = cookies
            self._save_cached_token(token, self._expires_at, cookies)

            return token

        except AuthError:
            raise
        except Exception as e:
            raise ConnectionError(f"登录请求失败: {e}")

    def invalidate(self):
        """清除 token（登出时调用）"""
        self._token = None
        self._expires_at = 0
        token_file = self.config.token_file
        if token_file and token_file.exists():
            token_file.unlink()

    def _load_cached_token(self) -> Optional[TokenCache]:
        """从文件加载缓存的 token"""
        token_file = self.config.token_file
        if not token_file or not token_file.exists():
            return None
        try:
            with open(token_file, "r") as f:
                data = json.load(f)
            return TokenCache(
                instance=data["instance"],
                token=data["token"],
                expires_at=data["expires_at"],
                created_at=data["created_at"],
                cookies=data.get("cookies", {}),
            )
        except (KeyError, json.JSONDecodeError):
            return None

    def _save_cached_token(self, token: str, expires_at: float, cookies: dict = None):
        """保存 token 到文件缓存"""
        TOKEN_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        token_file = self.config.token_file
        if not token_file:
            return
        data = {
            "instance": self.config.name,
            "token": token,
            "expires_at": expires_at,
            "created_at": time.time(),
            "cookies": cookies or {},
        }
        with open(token_file, "w") as f:
            json.dump(data, f, indent=2)
