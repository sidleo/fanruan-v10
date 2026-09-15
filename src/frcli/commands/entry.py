"""frcli entry 命令组 - 平台条目与消息（全部只读）

注意：这里的「条目」是**平台条目树**（目录/链接/首页，id 是 UUID），
与 `report list` 的**报表目录树**（id 是文件路径）是两套东西。
"""

import click
from ..config import load_config
from ..client import FineReportClient
from ..output import output_data, error


def get_client(instance_name=None) -> FineReportClient:
    """获取配置好的客户端"""
    config = load_config(instance_name)
    return FineReportClient(config)


@click.group("entry")
def entry_group():
    """查看平台条目与消息（只读）"""
    pass


@entry_group.command("list")
@click.option("--page", default=1, help="页码（从 1 开始）")
@click.option("--count", "-n", default=20, help="每页条数")
@click.option("--keyword", default="", help="按名称过滤")
@click.option("-f", "--format", "fmt", type=click.Choice(["json", "table"]), default="json")
@click.option("-i", "--instance", help="FineReport 实例名")
def list_cmd(page, count, keyword, fmt, instance):
    """平台条目分页列表（id 是 UUID）"""
    try:
        client = get_client(instance)
        with client:
            output_data(client.list_entries(page, count, keyword), format=fmt, title="平台条目")
    except Exception as e:
        error(e)


@entry_group.command("roots")
@click.option("-f", "--format", "fmt", type=click.Choice(["json", "table"]), default="json")
@click.option("-i", "--instance", help="FineReport 实例名")
def roots_cmd(fmt, instance):
    """条目根节点"""
    try:
        client = get_client(instance)
        with client:
            output_data(client.get_entry_roots(), format=fmt, title="条目根节点")
    except Exception as e:
        error(e)


@entry_group.command("all")
@click.option("-f", "--format", "fmt", type=click.Choice(["json", "table"]), default="json")
@click.option("-i", "--instance", help="FineReport 实例名")
def all_cmd(fmt, instance):
    """全量平台条目"""
    try:
        client = get_client(instance)
        with client:
            output_data(client.get_all_entries(), format=fmt, title="全量条目")
    except Exception as e:
        error(e)


@entry_group.command("messages")
@click.option("--unread", is_flag=True, help="只看未读")
@click.option("--page", default=1, help="页码")
@click.option("--count", "-n", default=20, help="每页条数")
@click.option("--keyword", default="", help="按关键词过滤")
@click.option("-f", "--format", "fmt", type=click.Choice(["json", "table"]), default="json")
@click.option("-i", "--instance", help="FineReport 实例名")
def messages_cmd(unread, page, count, keyword, fmt, instance):
    """平台消息（未读 / 全部）"""
    try:
        client = get_client(instance)
        with client:
            data = client.list_messages(unread, page, count, keyword)
            output_data(data, format=fmt, title="未读消息" if unread else "平台消息")
    except Exception as e:
        error(e)
