"""frcli inspect 命令组 - 运行时巡检（模板性能分析插件 com.fr.plugin.ins）

链路：run → 用 view/report?op=page_content 触发真实计算 → 内部轮询结果。
命令内部自己等待（退避轮询），调用方不需要 sleep / 猜时间。
"""

import json
import math
import time

import click

from ..config import load_config
from ..client import FineReportClient, INSPECTION_STATUS_TEXT
from ..output import output_data, error
from ..exceptions import InspectionError

#: 只允许这两种预览类型：write / write_plus 是填报写操作，巡检命令不开放
INSPECTION_OPS = ("page", "view")


def get_client(instance_name=None) -> FineReportClient:
    """获取配置好的客户端"""
    config = load_config(instance_name)
    return FineReportClient(config)


def _shape_result(result: dict, report_path: str, op: str, elapsed_ms: int) -> dict:
    """把完整巡检 JSON 收成命令输出：默认剔除 `meta.para`（含工号/组织/会话参数）。"""
    meta = result.get("meta") or {}
    extra = result.get("extra") or {}
    base = extra.get("base") or {}
    cells = result.get("cell") or {}
    shaped = {
        "template": report_path,
        "op": op,
        "elapsed_ms": elapsed_ms,
        "template_cost_ms": base.get("template-cost"),
        "cells": len(cells),
        "extra": extra.get("extra") or {},
        "cell": cells,
    }
    if extra.get("db fetch") is not None:
        shaped["db_fetch"] = extra.get("db fetch")
    if meta.get("date") is not None:
        shaped["inspection_date"] = meta.get("date")
    return shaped


def _db_fetch_sql_truncated(result: dict) -> bool:
    """巡检结果的 db fetch SQL 由插件截断为 500 字符（实测 2026-10-24）。

    这是平台侧行为，不是 CLI 截的；千万别拿它判断“服务器上是不是旧 SQL/上传没生效”，
    要被核对完整 SQL 请用 `report datasets <模板>`（或 report download 读模板字节）。
    """
    db_fetch = (result.get("extra") or {}).get("db fetch") or {}
    for item in db_fetch.values():
        sql = item.get("sql") if isinstance(item, dict) else None
        if isinstance(sql, str) and len(sql) >= 500:
            return True
    return False


def _table_rows(result: dict) -> list:
    """表格视图：整体耗时 + 各环节 + 最慢的单元格。"""
    extra = result.get("extra") or {}
    cells = result.get("cell") or {}
    rows = [
        {"item": "template", "value": result.get("template")},
        {"item": "op", "value": result.get("op")},
        {"item": "elapsed_ms", "value": result.get("elapsed_ms")},
        {"item": "template-cost (ms)", "value": result.get("template_cost_ms")},
        {"item": "cells", "value": result.get("cells")},
    ]
    for key, value in (extra.get("extra") or {}).items():
        rows.append({"item": key, "value": value})
    db_fetch = result.get("db_fetch")
    if db_fetch:
        rows.append({"item": "db fetch", "value": len(db_fetch)})
    slowest = sorted(
        ((cell, (data or {}).get("total", 0)) for cell, data in cells.items()),
        key=lambda x: -x[1],
    )[:10]
    for cell, total in slowest:
        rows.append({"item": f"cell {cell} total", "value": total})
    return rows


@click.group("inspect")
def inspect_group():
    """运行时巡检（模板性能分析）：真实执行一次模板，输出各环节/单元格耗时"""
    pass


@inspect_group.command("status")
@click.option("-f", "--format", "fmt", type=click.Choice(["json", "table"]), default="json")
@click.option("-i", "--instance", help="FineReport 实例名")
def status_cmd(fmt, instance):
    """巡检插件状态（检测点是否生效，只读）"""
    try:
        client = get_client(instance)
        with client:
            data = client.get_inspection_status()
        code = str(data.get("status", ""))
        out = {
            "status": code,
            "status_text": INSPECTION_STATUS_TEXT.get(code, "未知状态"),
            "expect_entrance": data.get("expectEntrance") or [],
            "expect_methods": data.get("expectMethods") or [],
        }
        if fmt == "table":
            output_data(
                [{"item": k, "value": v} for k, v in out.items()],
                format="table", title="巡检插件状态")
        else:
            output_data(out, format="json")
    except Exception as e:
        error(e)


@inspect_group.command("run")
@click.argument("report_path")
@click.option("--op", type=click.Choice(list(INSPECTION_OPS)), default="page",
              show_default=True, help="page=分页预览；view=分析预览（含数据源取数耗时）")
@click.option("--params", type=str,
              help='模板参数 JSON，如 \'{"date":"2024-01-01"}\'（发起巡检时带上）')
@click.option("--timeout", type=float, default=None,
              help="等待巡检结果上限秒数（缺省 FRCLI_INSPECT_TIMEOUT=60；模板计算受 FRCLI_TIMEOUT 约束）")
@click.option("--raw", is_flag=True,
              help="原样输出巡检 JSON（含 meta.para：工号/组织/会话参数；默认剔除）")
@click.option("-f", "--format", "fmt", type=click.Choice(["json", "table"]), default="json")
@click.option("-i", "--instance", help="FineReport 实例名")
def run_cmd(report_path, op, params, timeout, raw, fmt, instance):
    """对一张模板做运行时巡检（会真实执行一次模板计算）

    \b
    示例:
      frcli inspect status
      frcli inspect run "demo_group/demo_user/x.cpt"
      frcli inspect run "demo_group/demo_user/x.cpt" --op view --params '{"edate":"2024-01-01"}'
    """
    if op not in INSPECTION_OPS:
        error(InspectionError(
            f"不支持的巡检类型: {op}（只允许 page / view；write / write_plus 会触发填报写操作）"))
        return
    if timeout is not None and (not math.isfinite(timeout) or timeout < 0):
        error(InspectionError(f"--timeout 必须是 >=0 的有限秒数（收到 {timeout!r}）"))
        return
    try:
        try:
            params_dict = json.loads(params) if params else {}
        except ValueError as e:
            raise InspectionError(f"--params 不是合法 JSON: {e}") from e
        started = time.monotonic()
        client = get_client(instance)
        with client:
            result = client.run_inspection(
                report_path, op=op, params=params_dict, timeout=timeout)
        elapsed_ms = int((time.monotonic() - started) * 1000)
        if _db_fetch_sql_truncated(result):
            click.echo(
                "⚠️ 巡检结果里 db fetch 的 sql 字段被平台截断为 500 字符（非 CLI 截断）："
                "不要用它核对 SQL 内容或判断上传是否生效；完整 SQL 用 `report datasets <模板>`"
                "（或 report download 读模板字节）。", err=True)
        if raw:
            out = result
        else:
            out = _shape_result(result, report_path, op, elapsed_ms)
        if fmt == "table" and not raw:
            output_data(_table_rows(out), format="table", title="巡检结果")
        else:
            output_data(out, format=fmt)
    except Exception as e:
        error(e)
