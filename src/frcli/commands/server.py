"""frcli server 命令组 - 实例管理"""

import click
from ..config import (
    load_config, list_instances, get_default_instance,
    save_instance, remove_instance, set_default_instance
)
from ..client import FineReportClient
from ..output import output_data, success, error
from ..exceptions import ConfigError


@click.group("server")
def server_group():
    """管理 FineReport 服务器实例"""
    pass


@server_group.command("list")
@click.option("--format", "-f", "fmt", type=click.Choice(["json", "table"]), default="json")
def list_cmd(fmt):
    """列出所有已配置的实例"""
    instances = list_instances()
    default = get_default_instance()

    if not instances:
        click.echo("未配置任何实例。使用 `frcli server add` 添加。")
        return

    data = [{"name": name, "default": name == default} for name in instances]
    output_data(data, format=fmt, title="FineReport 实例列表")


@server_group.command("add")
@click.argument("name")
@click.option("--url", required=True, help="FineReport 服务器地址 (如 http://localhost:8705)")
@click.option("--username", "-u", required=True, help="用户名")
@click.option("--password", "-p", help="密码 (不指定则交互输入)")
@click.option("--workspace", "-w", default="/webroot", help="工作空间路径")
@click.option("--set-default", is_flag=True, help="设为默认实例")
def add_cmd(name, url, username, password, workspace, set_default):
    """添加新的 FineReport 实例"""
    try:
        save_instance(name, url, username, password, workspace, set_default)
        success({
            "action": "add_instance",
            "instance": name,
            "url": url,
            "username": username,
            "set_default": set_default,
        })
    except Exception as e:
        error(e)


@server_group.command("remove")
@click.argument("name")
def remove_cmd(name):
    """删除实例配置"""
    try:
        remove_instance(name)
        success({"action": "remove_instance", "instance": name})
    except Exception as e:
        error(e)


@server_group.command("set-default")
@click.argument("name")
def set_default_cmd(name):
    """设置默认实例"""
    try:
        set_default_instance(name)
        success({"action": "set_default", "instance": name})
    except Exception as e:
        error(e)


@server_group.command("test")
@click.argument("name", required=False)
@click.option("--format", "-f", "fmt", type=click.Choice(["json", "table"]), default="json")
def test_cmd(name, fmt):
    """测试连接并返回认证状态"""
    try:
        config = load_config(name)
        client = FineReportClient(config)
        with client:
            # 尝试认证
            client._ensure_auth()
            success({
                "action": "test_connection",
                "instance": config.name,
                "url": config.url,
                "username": config.username,
                "status": "connected",
            })
    except Exception as e:
        error(e)
