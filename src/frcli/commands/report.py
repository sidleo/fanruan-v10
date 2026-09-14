"""frcli report 命令组 - 报表文件管理"""

import click
from ..config import load_config
from ..client import FineReportClient
from ..output import output_data, success, error


def get_client(instance_name=None) -> FineReportClient:
    """获取配置好的客户端"""
    config = load_config(instance_name)
    return FineReportClient(config)


@click.group("report")
def report_group():
    """管理报表文件"""
    pass


@report_group.command("list")
@click.argument("directory", default="/")
@click.option("-f", "--format", "fmt", type=click.Choice(["json", "table"]), default="json")
@click.option("-i", "--instance", help="FineReport 实例名")
def list_reports(directory, fmt, instance):
    """列出指定目录下的报表文件"""
    try:
        client = get_client(instance)
        with client:
            data = client.list_reports(directory)
            output_data(data, format=fmt, title=f"报表文件: {directory}")
    except Exception as e:
        error(e)


@report_group.command("info")
@click.argument("report_path")
@click.option("-f", "--format", "fmt", type=click.Choice(["json", "table"]), default="json")
@click.option("-i", "--instance", help="FineReport 实例名")
def report_info(report_path, fmt, instance):
    """查看报表文件信息"""
    try:
        client = get_client(instance)
        with client:
            data = client.get_report_info(report_path)
            output_data(data, format=fmt, title=f"报表信息: {report_path}")
    except Exception as e:
        error(e)


@report_group.command("upload")
@click.argument("local_path", type=click.Path(exists=True))
@click.argument("remote_path")
@click.option("-i", "--instance", help="FineReport 实例名")
def upload_report(local_path, remote_path, instance):
    """上传报表模板"""
    try:
        client = get_client(instance)
        with client:
            result = client.upload_report(local_path, remote_path)
            success({
                "action": "upload",
                "local": local_path,
                "remote": remote_path,
                "success": result,
            })
    except Exception as e:
        error(e)


@report_group.command("delete")
@click.argument("report_path")
@click.option("-i", "--instance", help="FineReport 实例名")
def delete_report(report_path, instance):
    """删除报表文件"""
    try:
        client = get_client(instance)
        with client:
            result = client.delete_report(report_path)
            success({
                "action": "delete",
                "path": report_path,
                "deleted": result,
            })
    except Exception as e:
        error(e)


@report_group.command("download")
@click.argument("remote_path")
@click.option("-o", "--output", help="本地保存路径")
@click.option("-i", "--instance", help="FineReport 实例名")
def download_report(remote_path, output, instance):
    """下载报表模板"""
    try:
        client = get_client(instance)
        with client:
            result = client.download_report(remote_path, output)
            success({
                "action": "download",
                "remote": remote_path,
                "local": result,
            })
    except Exception as e:
        error(e)


@report_group.command("datasets")
@click.argument("report_path")
@click.option("-f", "--format", "fmt", type=click.Choice(["json", "table"]), default="json")
@click.option("--sql", is_flag=True, help="显示完整 SQL")
@click.option("-i", "--instance", help="FineReport 实例名")
def report_datasets(report_path, fmt, sql, instance):
    """查看报表的数据集定义（名称、参数、SQL）"""
    try:
        client = get_client(instance)
        with client:
            datasets = client.get_report_datasets(report_path)

            if fmt == "json":
                output_data(datasets, format="json")
            else:
                # 表格格式输出
                from ..output import console
                from rich.table import Table
                from rich.panel import Panel

                table = Table(title=f"数据集: {report_path}")
                table.add_column("序号", style="cyan", width=4)
                table.add_column("名称", style="green")
                table.add_column("参数", style="yellow")
                table.add_column("SQL", style="white", max_width=60)

                for i, ds in enumerate(datasets, 1):
                    params = ", ".join(ds.get("parameters", []))
                    ds_sql = ds.get("sql", "")
                    if not sql and len(ds_sql) > 60:
                        ds_sql = ds_sql[:60] + "..."
                    table.add_row(str(i), ds.get("name", ""), params, ds_sql)

                console.print(table)

                # 如果指定了 --sql，显示完整 SQL
                if sql:
                    for i, ds in enumerate(datasets, 1):
                        if ds.get("sql"):
                            console.print(f"\n[bold cyan]数据集 {i}: {ds['name']}[/]")
                            console.print(Panel(ds["sql"], title="SQL", border_style="blue"))
    except Exception as e:
        error(e)
