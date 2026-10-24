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


UUID_RE = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"


def _is_uuid(value: str) -> bool:
    import re
    return bool(re.fullmatch(UUID_RE, (value or "").strip()))


def _not_found_hint(value: str) -> str:
    """命令参数可能是任务名、也可能被误传成 taskId（两者不同接口）。"""
    if _is_uuid(value):
        return (f"任务不存在: {value}（看起来是 taskId；get/pause/resume/update 也接受 taskId，"
                "但 UUID 反查只用**本人创建**的任务列表；非本人任务请用完整任务名。"
                "delete 收 id，其它命令收任务名）")
    return f"任务不存在: {value}（用 `schedule list` / `schedule tasks --all` 查任务名）"


def _resolve_write_task(client, task_name: str) -> dict:
    """写命令先按名/ID 取任务，并校验**精确匹配**。

    平台 `task/search` 是子串模糊搜索且取第一条：传「名字前缀」/打错一个字都可能命中
    另一个任务，直接 PUT/切状态会误改别人的任务（实测共享前缀的两个任务会命中其中之一）。
    """
    task = client.get_schedule(task_name)
    if not task:
        raise ScheduleError(_not_found_hint(task_name))
    actual = task.get("taskName") or ""
    if not _is_uuid(task_name) and actual.strip() != task_name.strip():
        raise ScheduleError(
            f"任务名不完全匹配：输入 {task_name!r} 命中 {actual!r}；写操作只接受完整任务名"
            "（可用 `schedule list` 核对全名）")
    return task


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
            if not data:
                error(ScheduleError(_not_found_hint(task_id)))
                return
            actual = data.get("taskName")
            if not _is_uuid(task_id) and actual and actual.strip() != task_id.strip():
                click.echo(
                    f"⚠️ task/search 是子串模糊搜索：输入 {task_id!r} 命中 {actual!r}；"
                    "get 已按第一条返回，写操作请用完整任务名。", err=True)
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
            # 先获取任务 ID（写操作：要求名字精确匹配，避免模糊命中别人的任务）
            task = _resolve_write_task(client, task_name)
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


@schedule_group.command("pause")
@click.argument("task_name")
@click.option("-i", "--instance", help="FineReport 实例名")
def pause_schedule(task_name, instance):
    """暂停定时任务（只切状态，不删任务；taskState 1=暂停；名字须精确匹配）"""
    try:
        client = get_client(instance)
        with client:
            try:
                task = _resolve_write_task(client, task_name)
                out = client.set_schedule_state(task.get("taskName"), paused=True)
            except ScheduleError:
                raise
            except Exception as e:
                if "任务不存在" in str(e):
                    raise ScheduleError(_not_found_hint(task_name)) from e
                raise
            out["status"] = "ok"
            success(out)
    except Exception as e:
        error(e)


@schedule_group.command("resume")
@click.argument("task_name")
@click.option("-i", "--instance", help="FineReport 实例名")
def resume_schedule(task_name, instance):
    """恢复定时任务运行（taskState 0=启用；名字须精确匹配）"""
    try:
        client = get_client(instance)
        with client:
            try:
                task = _resolve_write_task(client, task_name)
                out = client.set_schedule_state(task.get("taskName"), paused=False)
            except ScheduleError:
                raise
            except Exception as e:
                if "任务不存在" in str(e):
                    raise ScheduleError(_not_found_hint(task_name)) from e
                raise
            out["status"] = "ok"
            success(out)
    except Exception as e:
        error(e)


@schedule_group.command("update")
@click.argument("task_name")
@click.option("--description", "-d", help="更新任务描述（taskDescription）")
@click.option("--template", "-t", help="更新任务模板路径（templatePath）")
@click.option("-i", "--instance", help="FineReport 实例名")
def update_schedule(task_name, description, template, instance):
    """更新定时任务（描述 / 模板路径）

    \b
    ⚠️ 平台 PUT 会**重置任务状态为启用**（实测 2026-10-24）：本命令会先记下原状态，
    更新后若原来是暂停则自动切回暂停，并在输出里回报 before/after。
    ⚠️ 改生产任务模板属生产变更：先备份任务配置（`schedule get`），或先 `schedule pause`。
    \b
    示例:
      frcli schedule pause "demo_task"
      frcli schedule update "demo_task" --template "demo_group/demo_user/新模板.cpt"
      frcli schedule resume "demo_task"
    """
    if not description and not template:
        error(ScheduleError("至少要给 --description 或 --template 之一"))
        return
    try:
        client = get_client(instance)
        with client:
            task = _resolve_write_task(client, task_name)

            before = {
                "templatePath": task.get("templatePath"),
                "taskDescription": task.get("taskDescription"),
                "taskState": (task.get("taskState") or {}).get("value"),
                "creator": task.get("creator"),
            }
            # 状态不是 0/1（实测存在 2，疑似已结束/停止）：PUT 会把状态重置为启用，
            # 可能把已结束任务静默重新启用，所以拒绝自动改，交给人工。
            if before["taskState"] not in (0, 1):
                raise ScheduleError(
                    f"任务当前状态为 {before['taskState']!r}（不是 0/1；2 疑似已结束/停止）。"
                    "PUT 会重置任务状态为启用，可能误重启已结束任务，拒绝自动更新；"
                    "请先在平台核对/处理该任务")
            # 模板路径先校验存在：平台接受任意路径（实测不存在也 200 success），
            # 不校验会把任务静默指向坏模板、下次运行才失败。
            if template and not client.report_exists(template):
                raise ScheduleError(
                    f"模板不存在: {template}（可用 `report list <目录>` 核对；"
                    "确实要指向新文件请先 `report upload` 上传）")

            if template:
                task["templatePath"] = template
            if description:
                task["taskDescription"] = description

            task_id = task.get("id")
            result = client.update_schedule(task_id, task)
            if not result:
                raise ScheduleError(
                    "平台未确认更新（PUT 返回非 success）；任务可能未改，"
                    "请用 `schedule get` 回读核对后再重试")

            # 回读：先按 id，再退化为按任务名（本人任务列表里可能查不到 id）
            after_task = client.get_schedule(task_id) or client.get_schedule(task_name)
            if not after_task:
                # 最坏情况：PUT 已提交、平台还重置了状态。原来暂停的尽力恢复一次。
                if before["taskState"] == 1:
                    try:
                        client.set_schedule_state(task_name, paused=True)
                    except Exception:
                        pass
                raise ScheduleError(
                    "更新已提交，但回读失败（按 task_id 与任务名都读不到）。任务当前状态未知；"
                    "请用 `schedule get <任务名>` 人工核对（若原为暂停，确认是否需要重新 pause）")

            after = {
                "templatePath": after_task.get("templatePath"),
                "taskDescription": after_task.get("taskDescription"),
                "taskState": (after_task.get("taskState") or {}).get("value"),
                "creator": after_task.get("creator"),
            }
            # PUT 会重置状态为启用：保留调用前的暂停状态（启用则保持启用）
            restored = False
            if before["taskState"] == 1 and after["taskState"] == 0:
                try:
                    client.set_schedule_state(task_id, paused=True)
                    restored = True
                except Exception as e:
                    actual = None
                    try:
                        actual = (client.get_schedule(task_name).get("taskState") or {}).get("value")
                    except Exception:
                        pass
                    raise ScheduleError(
                        f"任务已更新，但恢复暂停失败（{e}）；任务当前状态={actual!r}（原为暂停）。"
                        f"请立即人工执行：frcli schedule pause {task_name!r}") from e
                after_task = client.get_schedule(task_id) or client.get_schedule(task_name)
                after["taskState"] = (after_task.get("taskState") or {}).get("value")
            # creator 不允许被清空（client 已随 PUT 回传；这里只做校验，不静默成功）
            if before["creator"] and not after["creator"]:
                raise ScheduleError(
                    f"更新后 creator 被清空（before={before['creator']!r}），"
                    "平台行为异常；请从备份恢复或改用 GUI 改这一项")
            success({
                "action": "update_schedule",
                "task_name": task_name,
                "task_id": task_id,
                "updated": result,
                "before": before,
                "after": after,
                "paused_state_restored": restored,
            })
    except Exception as e:
        error(e)


@schedule_group.command("tasks")
@click.option("--page", default=1, help="页码（从 1 开始）")
@click.option("--count", "-n", default=20, help="每页条数")
@click.option("--all", "all_tasks", is_flag=True, help="取本人创建任务全量（task/listAll/2，不分页；全部任务名用 schedule list）")
@click.option("--privilege", default=2, help="平台权限视角参数（实测 2；listAll 仅返回本人创建任务）")
@click.option("-f", "--format", "fmt", type=click.Choice(["json", "table"]), default="json")
@click.option("-i", "--instance", help="FineReport 实例名")
def tasks_schedule(page, count, all_tasks, privilege, fmt, instance):
    """任务列表（含 taskId，比 `schedule list` 只给名字更全）"""
    try:
        client = get_client(instance)
        with client:
            data = client.list_schedule_tasks(page, count, all_tasks, privilege)
            if not all_tasks and isinstance(data, dict) and data.get("hasNext"):
                click.echo(
                    "⚠️ 这一页还有下一页（hasNext=true，默认每页 20 条）；"
                    "`--all` 取本人创建任务全量，翻页用 `--page`；全部任务名用 `schedule list`。", err=True)
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
            if isinstance(data, list) and limit and len(data) == limit:
                click.echo(
                    f"⚠️ history 按时间升序，这里是**最早** {limit} 条；要最新一条请把 -n 调大后取末尾，"
                    "或用 `schedule record --all`（按 time 倒序）。", err=True)
            title = f"执行历史: {task_name}" if task_name else "执行历史"
            output_data(data, format=fmt, title=title)
    except Exception as e:
        error(e)


@schedule_group.command("record")
@click.argument("task_name")
@click.option("--page", default=1, help="页码（从 1 开始）")
@click.option("--limit", "-n", default=20, help="每页条数")
@click.option("--all", "all_records", is_flag=True,
              help="翻完所有页后按 time 倒序（要「最近几次」用这个）")
@click.option("-f", "--format", "fmt", type=click.Choice(["json", "table"]), default="json")
@click.option("-i", "--instance", help="FineReport 实例名")
def record_schedule(task_name, page, limit, all_records, fmt, instance):
    """查看某任务的执行记录（含运行结果与错误信息）

    ⚠️ 平台返回顺序**不保证按时间**（分页内可能混排）；输出已按 time 倒序。
    要看跨页的最新记录，加 --all（会翻页并整体倒序）。
    """
    try:
        client = get_client(instance)
        with client:
            data = client.search_schedule_records(task_name, page, limit, all_records=all_records)
            if not all_records and data.get("total", 0) > len(data.get("items", [])):
                click.echo(
                    "⚠️ 只查了当前页并按 time 倒序；要跨页取最新记录请加 `--all`"
                    "（翻全量后整体倒序，记录多时较慢）。", err=True)
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
