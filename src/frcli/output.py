"""输出格式化 - JSON/表格"""

import json
import csv
import io
import sys
import click
from typing import Any
from rich.console import Console
from rich.table import Table


console = Console()


def output_json(data: Any):
    """JSON 格式输出"""
    click.echo(json.dumps(data, ensure_ascii=False, indent=2))


def output_table(data: list[dict], title: str = None):
    """表格格式输出"""
    if not data:
        click.echo("(空)")
        return

    table = Table(title=title)
    # 使用第一行的 key 作为列名
    keys = list(data[0].keys())
    for key in keys:
        table.add_column(key, overflow="fold")

    for row in data:
        values = [str(row.get(k, "")) for k in keys]
        table.add_row(*values)

    console.print(table)


def output_csv(data: list[dict]):
    """CSV 格式输出"""
    if not data:
        return
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=data[0].keys())
    writer.writeheader()
    writer.writerows(data)
    click.echo(output.getvalue(), nl=False)


def output_data(data: Any, format: str = "json", title: str = None):
    """统一输出接口"""
    if format == "json":
        output_json(data)
    elif format == "table":
        if isinstance(data, list):
            output_table(data, title=title)
        else:
            output_json(data)
    elif format == "csv":
        if isinstance(data, list):
            output_csv(data)
        else:
            output_json(data)
    else:
        output_json(data)


def success(data: dict):
    """统一成功输出"""
    data["status"] = "ok"
    click.echo(json.dumps(data, ensure_ascii=False, indent=2))


def error(e: Exception):
    """统一错误输出到 stderr"""
    from .exceptions import FrcliError
    result = {
        "status": "error",
        "error": {
            "code": getattr(e, "code", "UNKNOWN"),
            "message": str(e),
            "details": getattr(e, "details", None),
        }
    }
    click.echo(json.dumps(result, ensure_ascii=False, indent=2), err=True)
    exit_code = 1
    if hasattr(e, "code"):
        code_map = {
            "CONFIG_ERROR": 2,
            "CONNECTION_ERROR": 3,
        }
        exit_code = code_map.get(e.code, 1)
    sys.exit(exit_code)
