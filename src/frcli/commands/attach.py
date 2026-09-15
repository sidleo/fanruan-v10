"""frcli attach 命令组 - 服务器附件（附件缓存，非报表目录）"""

import click
from ..config import load_config
from ..client import FineReportClient
from ..output import success, error


def get_client(instance_name=None) -> FineReportClient:
    """获取配置好的客户端"""
    config = load_config(instance_name)
    return FineReportClient(config)


@click.group("attach")
def attach_group():
    """管理服务器附件（落在附件缓存，不动报表目录）"""
    pass


@attach_group.command("upload")
@click.argument("local_path", type=click.Path(exists=True, dir_okay=False))
@click.option("--name", "filename", help="服务器上的文件名（默认取本地文件名）")
@click.option("-i", "--instance", help="FineReport 实例名")
def upload_attach_cmd(local_path, filename, instance):
    """上传本地文件到服务器附件缓存，返回 attach_id"""
    try:
        client = get_client(instance)
        with client:
            info = client.upload_attach(local_path, filename)
            success({
                "action": "attach_upload",
                "file": local_path,
                **info,
            })
    except Exception as e:
        error(e)


@attach_group.command("remove")
@click.argument("attach_id")
@click.option("-i", "--instance", help="FineReport 实例名")
def remove_attach_cmd(attach_id, instance):
    """按 attach_id 删除服务器附件"""
    try:
        client = get_client(instance)
        with client:
            client.remove_attach(attach_id)
            success({
                "action": "attach_remove",
                "attach_id": attach_id,
            })
    except Exception as e:
        error(e)
