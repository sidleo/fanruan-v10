"""frcli system 命令组 - 系统与平台信息（全部只读）"""

import click
from ..config import load_config
from ..client import FineReportClient
from ..output import output_data, error


def get_client(instance_name=None) -> FineReportClient:
    """获取配置好的客户端"""
    config = load_config(instance_name)
    return FineReportClient(config)


@click.group("system")
def system_group():
    """查看系统与平台信息（只读）"""
    pass


@system_group.command("version")
@click.option("-f", "--format", "fmt", type=click.Choice(["json", "table"]), default="json")
@click.option("-i", "--instance", help="FineReport 实例名")
def version_cmd(fmt, instance):
    """服务端版本与各模块 jar 版本"""
    try:
        client = get_client(instance)
        with client:
            output_data(client.get_server_version(), format=fmt, title="服务端版本")
    except Exception as e:
        error(e)


@system_group.command("health")
@click.option("-f", "--format", "fmt", type=click.Choice(["json", "table"]), default="json")
@click.option("-i", "--instance", help="FineReport 实例名")
def health_cmd(fmt, instance):
    """系统健康状态"""
    try:
        client = get_client(instance)
        with client:
            output_data(client.get_server_health(), format=fmt, title="系统健康")
    except Exception as e:
        error(e)


@system_group.command("modules")
@click.option("--keyword", help="按关键词过滤模块")
@click.option("-f", "--format", "fmt", type=click.Choice(["json", "table"]), default="json")
@click.option("-i", "--instance", help="FineReport 实例名")
def modules_cmd(keyword, fmt, instance):
    """决策平台模块树"""
    try:
        client = get_client(instance)
        with client:
            output_data(client.get_decision_modules(keyword), format=fmt, title="平台模块")
    except Exception as e:
        error(e)


@system_group.command("authority")
@click.option("-i", "--instance", help="FineReport 实例名")
def authority_cmd(instance):
    """权限开关（分级授权 / 报表编辑 / 数据连接 / 调度）"""
    try:
        client = get_client(instance)
        with client:
            output_data(client.get_authority_config(), format="json")
    except Exception as e:
        error(e)


@system_group.command("login-policy")
@click.option("-i", "--instance", help="FineReport 实例名")
def login_policy_cmd(instance):
    """登录配置 + 密码策略 + 密码到期提醒"""
    try:
        client = get_client(instance)
        with client:
            output_data({
                "login": client.get_login_config(),
                "passwordStrategy": client.get_password_strategy(),
                "passwordWarningDays": client.get_password_warning_time(),
            }, format="json")
    except Exception as e:
        error(e)
