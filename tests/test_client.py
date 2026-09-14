"""客户端模块测试"""

import pytest
from frcli.models import ServerConfig
from frcli.client import FineReportClient


def test_client_init():
    """测试客户端初始化"""
    config = ServerConfig(
        name="test",
        url="http://localhost:8705",
        username="admin",
    )
    client = FineReportClient(config)
    assert client.base_url == "http://localhost:8705"
    client.close()


def test_client_context_manager():
    """测试上下文管理器"""
    config = ServerConfig(
        name="test",
        url="http://localhost:8705",
        username="admin",
    )
    with FineReportClient(config) as client:
        assert client is not None
