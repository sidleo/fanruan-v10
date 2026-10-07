"""frcli export 命令组 - 报表导出"""

import json
import click
import yaml
from pathlib import Path
from ..config import load_config
from ..client import FineReportClient
from ..output import output_data, success, error
from ..exceptions import ExportError


def get_client(instance_name=None) -> FineReportClient:
    """获取配置好的客户端"""
    config = load_config(instance_name)
    return FineReportClient(config)


@click.group("export")
def export_group():
    """导出报表为各种格式"""
    pass


@export_group.command("pdf")
@click.argument("report_path")
@click.option("-o", "--output", help="输出文件路径")
@click.option("--params", type=str, help='JSON 格式的报表参数，如 \'{"date":"2024-01-01"}\'')
@click.option("-i", "--instance", help="FineReport 实例名")
def export_pdf(report_path, output, params, instance):
    """导出报表为 PDF"""
    output = output or f"{report_path.split('/')[-1].rsplit('.', 1)[0]}.pdf"
    params_dict = json.loads(params) if params else {}

    try:
        client = get_client(instance)
        with client:
            result = client.export_report(report_path, "pdf", output, params_dict)
            success({
                "action": "export",
                "format": "pdf",
                "report": report_path,
                "file": result,
                # 连接层错误自动重发了几次（只对 GET 生效）——链路抖动时可观测，正常为 0
                "net_retries": client.net_retries,
            })
    except Exception as e:
        error(e)


@export_group.command("excel")
@click.argument("report_path")
@click.option("-o", "--output", help="输出文件路径")
@click.option("--params", type=str, help='JSON 格式的报表参数')
@click.option("-i", "--instance", help="FineReport 实例名")
def export_excel(report_path, output, params, instance):
    """导出报表为 Excel"""
    output = output or f"{report_path.split('/')[-1].rsplit('.', 1)[0]}.xlsx"
    params_dict = json.loads(params) if params else {}

    try:
        client = get_client(instance)
        with client:
            result = client.export_report(report_path, "excel", output, params_dict)
            success({
                "action": "export",
                "format": "excel",
                "report": report_path,
                "file": result,
                # 连接层错误自动重发了几次（只对 GET 生效）——链路抖动时可观测，正常为 0
                "net_retries": client.net_retries,
            })
    except Exception as e:
        error(e)


@export_group.command("word")
@click.argument("report_path")
@click.option("-o", "--output", help="输出文件路径")
@click.option("--params", type=str, help='JSON 格式的报表参数')
@click.option("-i", "--instance", help="FineReport 实例名")
def export_word(report_path, output, params, instance):
    """导出报表为 Word（⚠️ 服务端实际返回 RTF，产物落盘为 .rtf）"""
    output = output or f"{report_path.split('/')[-1].rsplit('.', 1)[0]}.rtf"
    params_dict = json.loads(params) if params else {}

    try:
        client = get_client(instance)
        with client:
            result = client.export_report(report_path, "word", output, params_dict)
            success({
                "action": "export",
                "format": "word",
                "report": report_path,
                "file": result,
                # 连接层错误自动重发了几次（只对 GET 生效）——链路抖动时可观测，正常为 0
                "net_retries": client.net_retries,
            })
    except Exception as e:
        error(e)


@export_group.command("image")
@click.argument("report_path")
@click.option("-o", "--output", help="输出文件路径")
@click.option("--params", type=str, help='JSON 格式的报表参数')
@click.option("-i", "--instance", help="FineReport 实例名")
def export_image(report_path, output, params, instance):
    """导出报表为图片"""
    output = output or f"{report_path.split('/')[-1].rsplit('.', 1)[0]}.png"
    params_dict = json.loads(params) if params else {}

    try:
        client = get_client(instance)
        with client:
            result = client.export_report(report_path, "image", output, params_dict)
            success({
                "action": "export",
                "format": "image",
                "report": report_path,
                "file": result,
                # 连接层错误自动重发了几次（只对 GET 生效）——链路抖动时可观测，正常为 0
                "net_retries": client.net_retries,
            })
    except Exception as e:
        error(e)


@export_group.command("csv")
@click.argument("report_path")
@click.option("-o", "--output", help="输出文件路径")
@click.option("--params", type=str, help='JSON 格式的报表参数')
@click.option("-i", "--instance", help="FineReport 实例名")
def export_csv(report_path, output, params, instance):
    """导出报表为 CSV"""
    output = output or f"{report_path.split('/')[-1].rsplit('.', 1)[0]}.csv"
    params_dict = json.loads(params) if params else {}

    try:
        client = get_client(instance)
        with client:
            result = client.export_report(report_path, "csv", output, params_dict)
            success({
                "action": "export",
                "format": "csv",
                "report": report_path,
                "file": result,
                # 连接层错误自动重发了几次（只对 GET 生效）——链路抖动时可观测，正常为 0
                "net_retries": client.net_retries,
            })
    except Exception as e:
        error(e)


@export_group.command("batch")
@click.argument("manifest_path", type=click.Path(exists=True))
@click.option("-i", "--instance", help="FineReport 实例名")
def export_batch(manifest_path, instance):
    """批量导出（从 manifest.yaml 读取配置）

    manifest 格式:
    reports:
      - path: //doc//report1.cpt
        format: pdf
        output: ./out/report1.pdf
        params: {date: "2024-01-01"}

    **参数矩阵**：`params` 里给**列表**，就逐值各导一份；`output` 用 `{参数名}` 占位区分文件名：

    \b
    reports:
      - path: demo_group/demo_user/sales_monthly.cpt
        format: excel
        output: ./out/monthly_review_{edate}.xlsx
        params: {edate: ["20260430", "20260531", "20260630"]}
    """
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = yaml.safe_load(f)
    except Exception as e:
        error(ExportError(f"读取 manifest 失败: {e}"))
        return

    reports = manifest.get("reports", [])
    if not reports:
        error(ExportError("manifest 中未定义任何报表"))
        return

    results = []
    errors_list = []
    warnings_list = []

    # 参数矩阵展开：某个参数给了列表 → 该报表按每个取值各导一份
    jobs = []
    for i, item in enumerate(reports):
        params = item.get("params", {}) or {}
        keys = [k for k, v in params.items() if isinstance(v, list)]
        if not keys:
            jobs.append((i, item, params))
            continue
        # 空列表不是"没有矩阵"，而是"这一条一个任务都展开不出来"——静默丢报表比报错危险
        # （实测：total=0 / manifest_reports=1 / exit 0，用户以为跑完了）。
        empty_keys = [k for k in keys if not params[k]]
        if empty_keys:
            error(ExportError(
                f"manifest 第 {i + 1} 条报表({item.get('path') or '?'})的参数 "
                f"{', '.join(empty_keys)} 是空列表，展开后没有任何导出任务；"
                "请至少填一个取值，或删掉该参数"))
            return
        import itertools
        for combo in itertools.product(*[params[k] for k in keys]):
            one = dict(params)
            one.update(dict(zip(keys, combo)))
            jobs.append((i, item, one))

    seen_outputs = {}
    warned_outputs = set()

    client = get_client(instance)
    with client:
        for i, item, params in jobs:
            report_path = item.get("path")
            format = item.get("format", "pdf")
            output = item.get("output", f"export_{i}.{format}")
            # `{参数名}` 占位 → 换成本次取值，区分同名产物
            for k, v in params.items():
                output = output.replace("{" + k + "}", str(v))

            # 多条任务落到同一路径 = 后写的覆盖先写的（多半是 output 漏了占位）
            if output in seen_outputs:
                if output not in warned_outputs:
                    warned_outputs.add(output)
                    warnings_list.append(
                        f"输出路径冲突: {output} 被多条任务共用，后写的会覆盖先写的"
                        "——检查 output 的 {参数名} 占位是否覆盖了所有矩阵参数")
            else:
                seen_outputs[output] = i

            try:
                result = client.export_report(report_path, format, output, params)
                # 参数矩阵下同一报表会有多份产物：每条都带本次 params 与落盘路径，
                # 否则失败条目只能靠文件 mtime 猜是哪一项（实测踩过）。
                results.append({
                    "report": report_path,
                    "format": format,
                    "params": params,
                    "output": output,
                    "file": result,
                    "status": "ok",
                })
            except Exception as e:
                errors_list.append({
                    "report": report_path,
                    "format": format,
                    "params": params,
                    "output": output,
                    "status": "error",
                    "error": str(e),
                })

    success({
        "action": "batch_export",
        # total 是**展开后**的任务数（参数矩阵会放大）；manifest 条数另给 manifest_reports，
        # 否则 total=1 而 success+failed=6 这种账对不上（实测踩过）。
        "total": len(jobs),
        "manifest_reports": len(reports),
        "success": len(results),
        "failed": len(errors_list),
        "net_retries": client.net_retries,
        "warnings": warnings_list,
        "results": results,
        "errors": errors_list,
    })
