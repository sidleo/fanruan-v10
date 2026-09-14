"""frcli schedule 命令组 - 定时任务管理"""

import json
import click
import yaml
from pathlib import Path
from ..config import load_config
from ..client import FineReportClient
from ..output import output_data, success, error
from ..exceptions import ScheduleError


def get_client(instance_name=None) -> FineReportClient:
    """获取配置好的客户端"""
    config = load_config(instance_name)
    return FineReportClient(config)


@click.group("schedule")
def schedule_group():
    """管理定时任务"""
    pass


@schedule_group.command("list")
@click.option("-f", "--format", "fmt", type=click.Choice(["json", "table"]), default="json")
@click.option("-i", "--instance", help="FineReport 实例名")
def list_schedules(fmt, instance):
    """列出所有定时任务"""
    try:
        client = get_client(instance)
        with client:
            data = client.list_schedules()
            output_data(data, format=fmt, title="定时任务列表")
    except Exception as e:
        error(e)


@schedule_group.command("get")
@click.argument("task_id")
@click.option("-f", "--format", "fmt", type=click.Choice(["json", "table"]), default="json")
@click.option("-i", "--instance", help="FineReport 实例名")
def get_schedule(task_id, fmt, instance):
    """查看定时任务详情"""
    try:
        client = get_client(instance)
        with client:
            data = client.get_schedule(task_id)
            output_data(data, format=fmt, title=f"定时任务: {task_id}")
    except Exception as e:
        error(e)


@schedule_group.command("create")
@click.argument("config_path", type=click.Path(exists=True))
@click.option("-i", "--instance", help="FineReport 实例名")
def create_schedule(config_path, instance):
    """从配置文件创建定时任务"""
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        client = get_client(instance)
        with client:
            task_id = client.create_schedule(config)
            success({
                "action": "create_schedule",
                "task_id": task_id,
                "config": config_path,
            })
    except Exception as e:
        error(e)


@schedule_group.command("delete")
@click.argument("task_id")
@click.option("-i", "--instance", help="FineReport 实例名")
def delete_schedule(task_id, instance):
    """删除定时任务"""
    try:
        client = get_client(instance)
        with client:
            result = client.delete_schedule(task_id)
            success({
                "action": "delete_schedule",
                "task_id": task_id,
                "deleted": result,
            })
    except Exception as e:
        error(e)


@schedule_group.command("run")
@click.argument("task_name")
@click.option("-i", "--instance", help="FineReport 实例名")
def run_schedule(task_name, instance):
    """立即执行定时任务"""
    try:
        client = get_client(instance)
        with client:
            # 先获取任务 ID
            task = client.get_schedule(task_name)
            if not task:
                error(Exception(f"任务不存在: {task_name}"))
                return
            task_id = task.get("id")
            result = client.execute_schedule(task_id)
            success({
                "action": "execute_schedule",
                "task_name": task_name,
                "task_id": task_id,
                "result": result,
            })
    except Exception as e:
        error(e)


@schedule_group.command("update")
@click.argument("task_name")
@click.option("--description", "-d", help="更新任务描述")
@click.option("-i", "--instance", help="FineReport 实例名")
def update_schedule(task_name, description, instance):
    """更新定时任务"""
    try:
        client = get_client(instance)
        with client:
            # 先获取任务详情
            task = client.get_schedule(task_name)
            if not task:
                error(Exception(f"任务不存在: {task_name}"))
                return

            # 更新字段
            if description:
                task["taskDescription"] = description

            task_id = task.get("id")
            result = client.update_schedule(task_id, task)
            success({
                "action": "update_schedule",
                "task_name": task_name,
                "task_id": task_id,
                "updated": result,
            })
    except Exception as e:
        error(e)


@schedule_group.command("history")
@click.argument("task_name", required=False)
@click.option("--limit", "-n", default=10, help="返回的历史记录数量")
@click.option("-f", "--format", "fmt", type=click.Choice(["json", "table"]), default="json")
@click.option("-i", "--instance", help="FineReport 实例名")
def history_schedule(task_name, limit, fmt, instance):
    """查看定时任务执行历史"""
    try:
        client = get_client(instance)
        with client:
            data = client.get_schedule_history(task_name, limit)
            title = f"执行历史: {task_name}" if task_name else "执行历史"
            output_data(data, format=fmt, title=title)
    except Exception as e:
        error(e)
