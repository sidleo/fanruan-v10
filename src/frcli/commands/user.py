"""frcli user 命令组 - 用户与组织（全部只读）

最有用的场景：调度记录里的 `creator` 是工号（如 12345678），
用 `frcli user get 12345678` 解析成姓名。
"""

import click
from ..config import load_config
from ..client import FineReportClient
from ..output import output_data, error


def get_client(instance_name=None) -> FineReportClient:
    """获取配置好的客户端"""
    config = load_config(instance_name)
    return FineReportClient(config)


@click.group("user")
def user_group():
    """查看用户与组织（只读）"""
    pass


@user_group.command("list")
@click.option("-f", "--format", "fmt", type=click.Choice(["json", "table"]), default="json")
@click.option("-i", "--instance", help="FineReport 实例名")
def list_cmd(fmt, instance):
    """用户列表（当前账号可见的用户：工号 + 姓名，非全量目录）"""
    try:
        client = get_client(instance)
        with client:
            output_data(client.list_users(), format=fmt, title="用户列表")
    except Exception as e:
        error(e)


@user_group.command("me")
@click.option("-i", "--instance", help="FineReport 实例名")
def me_cmd(instance):
    """当前登录账号的信息（工号/姓名/邮箱/手机/角色）"""
    try:
        client = get_client(instance)
        with client:
            output_data(client.get_current_user(), format="json")
    except Exception as e:
        error(e)


@user_group.command("departments")
@click.option("--keyword", default="", help="按关键词过滤")
@click.option("-f", "--format", "fmt", type=click.Choice(["json", "table"]), default="json")
@click.option("-i", "--instance", help="FineReport 实例名")
def departments_cmd(keyword, fmt, instance):
    """部门树"""
    try:
        client = get_client(instance)
        with client:
            output_data(client.list_departments(keyword), format=fmt, title="部门")
    except Exception as e:
        error(e)


@user_group.command("posts")
@click.option("--keyword", default="", help="按关键词过滤")
@click.option("-f", "--format", "fmt", type=click.Choice(["json", "table"]), default="json")
@click.option("-i", "--instance", help="FineReport 实例名")
def posts_cmd(keyword, fmt, instance):
    """岗位列表"""
    try:
        client = get_client(instance)
        with client:
            output_data(client.list_posts(keyword), format=fmt, title="岗位")
    except Exception as e:
        error(e)
