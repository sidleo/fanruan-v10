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


@schedule_group.command("tasks")
@click.option("--page", default=1, help="页码（从 1 开始）")
@click.option("--count", "-n", default=20, help="每页条数")
@click.option("--all", "all_tasks", is_flag=True, help="取全量（listAll，不分页）")
@click.option("--privilege", default=2, help="权限视角（2=全部可见，实测）")
@click.option("-f", "--format", "fmt", type=click.Choice(["json", "table"]), default="json")
@click.option("-i", "--instance", help="FineReport 实例名")
def tasks_schedule(page, count, all_tasks, privilege, fmt, instance):
    """任务列表（含 taskId，比 `schedule list` 只给名字更全）"""
    try:
        client = get_client(instance)
        with client:
            data = client.list_schedule_tasks(page, count, all_tasks, privilege)
            output_data(data, format=fmt, title="定时任务（含 taskId）")
    except Exception as e:
        error(e)


@schedule_group.command("exists")
@click.argument("task_name")
@click.option("-i", "--instance", help="FineReport 实例名")
def exists_schedule(task_name, instance):
    """按准确任务名判断任务是否存在"""
    try:
        client = get_client(instance)
        with client:
            exists = client.schedule_task_exists(task_name)
            success({"action": "schedule_exists", "task_name": task_name, "exists": exists})
    except Exception as e:
        error(e)


@schedule_group.command("executing")
@click.option("-f", "--format", "fmt", type=click.Choice(["json", "table"]), default="json")
@click.option("-i", "--instance", help="FineReport 实例名")
def executing_cmd(fmt, instance):
    """当前正在执行的调度任务"""
    try:
        client = get_client(instance)
        with client:
            output_data(client.get_executing_tasks(), format=fmt, title="执行中")
    except Exception as e:
        error(e)


@schedule_group.command("records")
@click.option("--page", default=1, help="页码")
@click.option("--limit", "-n", default=20, help="每页条数")
@click.option("-f", "--format", "fmt", type=click.Choice(["json", "table"]), default="json")
@click.option("-i", "--instance", help="FineReport 实例名")
def records_cmd(page, limit, fmt, instance):
    """全平台执行记录（分页，total 十万级；某任务的用 `schedule record`更合适）"""
    try:
        client = get_client(instance)
        with client:
            output_data(client.list_all_schedule_records(page, limit), format=fmt,
                        title="全平台执行记录")
    except Exception as e:
        error(e)


@schedule_group.command("setting")
@click.option("-i", "--instance", help="FineReport 实例名")
def setting_cmd(instance):
    """调度全局设置（短信/邮件/平台消息开关、日志清理时间）"""
    try:
        client = get_client(instance)
        with client:
            output_data(client.get_schedule_settings(), format="json")
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


@schedule_group.command("record")
@click.argument("task_name")
@click.option("--page", default=1, help="页码（从 1 开始）")
@click.option("--limit", "-n", default=20, help="每页条数")
@click.option("-f", "--format", "fmt", type=click.Choice(["json", "table"]), default="json")
@click.option("-i", "--instance", help="FineReport 实例名")
def record_schedule(task_name, page, limit, fmt, instance):
    """查看某任务的执行记录（含运行结果与错误信息）"""
    try:
        client = get_client(instance)
        with client:
            data = client.search_schedule_records(task_name, page, limit)
            output_data(data, format=fmt, title=f"执行记录: {task_name}")
    except Exception as e:
        error(e)


@schedule_group.command("log")
@click.argument("task_log_id")
@click.option("-f", "--format", "fmt", type=click.Choice(["json", "table"]), default="json")
@click.option("-i", "--instance", help="FineReport 实例名")
def log_detail(task_log_id, fmt, instance):
    """查看单条调度日志详情（节点树，定位失败原因）；log_id 取自 `schedule history`"""
    try:
        client = get_client(instance)
        with client:
            data = client.get_schedule_log_detail(task_log_id)
            output_data(data, format=fmt, title=f"调度日志: {task_log_id}")
    except Exception as e:
        error(e)
