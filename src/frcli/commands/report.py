"""frcli report 命令组 - 报表文件管理"""

import os
from pathlib import Path

import click

from ..config import load_config
from ..client import FineReportClient
from ..output import output_data, success, error
from ..remotedesign import (ALLOW_ANY_ENV, assert_in_write_scope, upload_template,
                            delete_template, workspace_list)
from .. import local_cpt, reportops

#: 写范围判定本身只有一份（`remotedesign.assert_in_write_scope`），语义是
#: **fail-closed**：没设 `$FRCLI_WRITE_SCOPE` 就拒绝，`--any-path` 才放行。
#: 2026-09 踩过：agent 在没设范围的 shell 里跑 `report edit --apply`，真的写出了
#: 团队目录（`demo_group/other_user/legacy_rpt.cpt`），靠自动备份才逐字节还原 ——
#: 所以这里绝不兜底成某个默认目录，只保证「判定在任何网络调用之前」。


def assert_write_scope(remote_path: str, any_path: bool = False) -> str:
    """所有模板写命令的统一入口。

    真正的判定只有一份（`remotedesign.assert_in_write_scope`），这里只负责：
    把 `--any-path` 转成环境变量，调用顺序固定在**任何网络调用之前**。
    """
    if any_path:
        os.environ[ALLOW_ANY_ENV] = "1"
    assert_in_write_scope(remote_path)
    return remote_path


def _write_image(path: str, data: bytes) -> str:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    return str(p)


def get_client(instance_name=None) -> FineReportClient:
    """获取配置好的客户端"""
    config = load_config(instance_name)
    return FineReportClient(config)


#: 「账号无权限/平台特有路径」类报错的统一提示（经营分析平台模板常见）。
_PLATFORM_READ_HINT = (
    "提示：这是「账号无权限」类错误，不是 CLI 故障。若目标是经营分析平台（另一套决策平台）的模板，"
    "frcli 通常读不了；查这类模板的取数口径请改用平台元数据表反查模板 SQL"
    "（内部表名与查法见本地知识库）；不要用 frcli 反复尝试。")


def _platform_read_error_hint(exc: Exception) -> None:
    """`report datasets/download` 撞权限/找不到时，在 stderr 给可操作的下一步。"""
    msg = str(exc)
    if any(k in msg for k in ("无此接口权限", "该接口需管理员", "远程设计授权目录")):
        click.echo(_PLATFORM_READ_HINT, err=True)


@click.group("report")
def report_group():
    """管理报表文件"""
    pass


def _expand_user_path(value):
    """展开 `~`：Click 的 Path 不做 shell 展开，用户写 "~/reportlets" 会原样找不到。

    ⚠️ 因此这三个 local-* 命令的 Path 参数**不能带 `exists=True`**：Click 会在
    回调前先校验，`~/...` 会直接 exit 2，根本到不了这里；存在性由 local_cpt
    内部（expanduser → resolve）判断并报 ApiError。
    """
    return os.path.expanduser(value) if value else value


@report_group.command("local-examples")
@click.argument("directory", type=click.Path(file_okay=False))
@click.option("--keyword", help="按示例相对路径过滤（不区分大小写）")
@click.option("--contains", help="按 CPT 的 UTF-8 XML 原文过滤（区分大小写）")
@click.option("-n", "--limit", type=click.IntRange(1, 1000), default=30,
              show_default=True, help="最多返回多少条；matched 是全部命中数")
def local_examples_cmd(directory, keyword, contains, limit):
    """只读查找本地 CPT 示例；不需要实例配置或联网。"""
    try:
        output_data(local_cpt.find_examples(_expand_user_path(directory), keyword, contains, limit))
    except Exception as e:
        error(e)


@report_group.command("local-profile")
@click.argument("directory", type=click.Path(file_okay=False))
@click.option("--keyword", help="按示例相对路径过滤（不区分大小写）")
@click.option("--contains", help="按 CPT 的 UTF-8 XML 原文过滤（区分大小写）")
@click.option("--tag", help="只返回含该设计标签或报表原型的样例，例如 crosstab")
@click.option("-n", "--limit", type=click.IntRange(1, 1000), default=20,
              show_default=True, help="最多返回多少个代表样例")
def local_profile_cmd(directory, keyword, contains, tag, limit):
    """只读扫描本地 CPT，提炼报表原型、设计技术和代表样例。"""
    try:
        output_data(local_cpt.profile_examples(_expand_user_path(directory), keyword, contains, tag, limit))
    except Exception as e:
        error(e)


@report_group.command("local-inspect")
@click.argument("file", type=click.Path(dir_okay=False))
@click.option("--sheet", help="选择工作表；默认第一张")
@click.option("--block", type=click.IntRange(min=1), help="聚合报表的区块序号，从 1 开始")
@click.option("--cells", is_flag=True, help="同时列出单元格、数据设置与扩展方向")
@click.option("--design", is_flag=True,
              help="输出整份模板的报表原型、版面、视觉、交互与图表画像")
@click.option("-n", "--limit", type=click.IntRange(1, 1000), default=100,
              show_default=True, help="--cells 最多返回多少格；cell_count 为选定范围的总数")
def local_inspect_cmd(file, sheet, block, cells, design, limit):
    """只读检查本地 CPT，聚合报表按区块显示独立坐标。"""
    try:
        output_data(local_cpt.inspect_template(
            _expand_user_path(file), sheet, block, cells, limit, design))
    except Exception as e:
        error(e)


@report_group.command("list")
@click.argument("directory", default="/")
@click.option("--keyword", help="服务端按名称/路径过滤（比拉全量再本地筛省事）")
@click.option("--type", "file_type", help="服务端按类型过滤，如 cpt / frm")
@click.option("-f", "--format", "fmt", type=click.Choice(["json", "table"]), default="json")
@click.option("-i", "--instance", help="FineReport 实例名")
def list_reports(directory, keyword, file_type, fmt, instance):
    """列出指定目录下的报表文件"""
    try:
        client = get_client(instance)
        with client:
            data = client.list_reports(directory, keyword=keyword, file_types=file_type)
            output_data(data, format=fmt, title=f"报表文件: {directory}")
            if isinstance(data, list) and not data:
                click.echo(
                    "提示：空列表可能是目录确实没有模板，或当前账号无该目录权限"
                    "（平台模板树只返回有权限的节点，无权限目录连名字都不返回）。"
                    "核对：`frcli report list <上级目录>` 或 `frcli report list /`；"
                    "不要据此判断「报表不存在」。", err=True)
    except Exception as e:
        error(e)


@report_group.command("serverdatasets")
@click.option("-f", "--format", "fmt", type=click.Choice(["json", "table"]), default="json")
@click.option("-i", "--instance", help="FineReport 实例名")
def serverdatasets_cmd(fmt, instance):
    """列出服务器数据集（平台级数据集，非模板内数据集）"""
    try:
        client = get_client(instance)
        with client:
            output_data(client.list_server_datasets(), format=fmt, title="服务器数据集")
    except Exception as e:
        error(e)


@report_group.command("columns")
@click.argument("dataset_name")
@click.option("-f", "--format", "fmt", type=click.Choice(["json", "table"]), default="json")
@click.option("-i", "--instance", help="FineReport 实例名")
def columns_cmd(dataset_name, fmt, instance):
    """查看服务器数据集的字段清单（列名/列类型）"""
    try:
        client = get_client(instance)
        with client:
            data = client.get_dataset_columns(dataset_name)
            output_data(data, format=fmt, title=f"数据集字段: {dataset_name}")
    except Exception as e:
        error(e)


@report_group.command("authed")
@click.option("--keyword", help="按关键词过滤")
@click.option("-f", "--format", "fmt", type=click.Choice(["json", "table"]), default="json")
@click.option("-i", "--instance", help="FineReport 实例名")
def authed_cmd(keyword, fmt, instance):
    """读模板「认证(authentication)配置」这条路由的原始返回

    走 `GET /decision/v10/report/templates/all/authentication` —— 这是模板认证配置路由，
    **不是**「当前账号有权限的模板树」。实测该路由恒返回 `[]`（HTTP 200 的原始响应就是
    `{"data":[]}`，`keyword/type/id/pid` 多种参数形态同样为空），**与账号有没有权限无关**。

    要看有权限的模板树用 `report list`（平台已按权限过滤），别拿本命令判断「我有哪些报表」。

    结果为空时在 stderr 打一行提示（stdout 仍是合法 JSON，可照常管道解析）。
    """
    try:
        client = get_client(instance)
        with client:
            data = client.get_authenticated_templates(keyword)
            output_data(data, format=fmt, title="模板认证路由返回")
            if not data:
                click.echo(
                    "提示：本路由（模板 authentication 配置）返回空 ≠ 无权限；"
                    "有权限的模板树见 `frcli report list`（平台已按权限过滤）。",
                    err=True)
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
@click.argument("local_path", type=click.Path(exists=True, dir_okay=False))
@click.argument("remote_path")
@click.option("--force", is_flag=True, help="覆盖服务端同名模板（不加则拒绝覆盖）")
@click.option("--allow-format", is_flag=True,
              help="跳过「根元素必须是 <WorkBook>」的守门（默认拒绝非模板内容）")
@click.option("--any-path", is_flag=True,
              help="确认要写这个目标（否则必须用 FRCLI_WRITE_SCOPE 限定范围）")
@click.option("-i", "--instance", help="FineReport 实例名")
def upload_report(local_path, remote_path, force, allow_format, any_path, instance):
    """上传/覆盖服务端模板（🔴 服务端写）

    走 Designer 的远程设计通道（REST 没有写模板内容的接口）。
    写前占锁 + 自动备份原文件到 ~/.frcli/backups/，写后回读校验 SHA256。
    """
    try:
        assert_write_scope(remote_path, any_path)   # 先挡在命令层，再进网络调用
        config = load_config(instance)
        success(upload_template(config, local_path, remote_path, force=force,
                                allow_format=allow_format))
    except Exception as e:
        error(e)


@report_group.command("delete")
@click.argument("report_path")
@click.option("--force", is_flag=True, help="必须显式确认（服务端模板移入回收站）")
@click.option("--recursive", is_flag=True,
              help="目标是**目录**时必须加（否则拒绝：整个目录会进回收站）")
@click.option("--any-path", is_flag=True,
              help="确认要删这个目标（否则必须用 FRCLI_WRITE_SCOPE 限定范围）")
@click.option("-i", "--instance", help="FineReport 实例名")
def delete_report(report_path, force, recursive, any_path, instance):
    """删除服务端模板（🔴 服务端写，移入回收站可恢复）

    ⚠️ 这个接口对目录也照删：目标是目录时不加 `--recursive` 会被拒绝。
    """
    try:
        assert_write_scope(report_path, any_path)
        config = load_config(instance)
        success(delete_template(config, report_path, force=force, recursive=recursive))
    except Exception as e:
        error(e)


@report_group.command("ws-list")
@click.argument("path", default="")
@click.option("-f", "--format", "fmt", type=click.Choice(["json", "table"]), default="json")
@click.option("-i", "--instance", help="FineReport 实例名")
def ws_list_cmd(path, fmt, instance):
    """列出服务端远程工作区目录（reportlets 下就是模板目录）"""
    try:
        config = load_config(instance)
        data = workspace_list(config, path)
        if data.get("count") == 0:
            click.echo(
                "提示：工作区为空有三种可能——路径不存在、目录确实为空，或账号对该远程设计目录无权限。"
                "用上一级路径核对；不要据此判断文件不存在。", err=True)
        if fmt == "table":
            output_data(data["entries"], format="table", title=f"工作区: {data['path']}")
        else:
            output_data(data, format="json")
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
        _platform_read_error_hint(e)
        error(e)


@report_group.command("paras")
@click.argument("report_path")
@click.option("-f", "--format", "fmt", type=click.Choice(["json", "table"]), default="json")
@click.option("-i", "--instance", help="FineReport 实例名")
def report_paras(report_path, fmt, instance):
    """查看报表参数定义（官方接口，含派生参数公式）"""
    try:
        client = get_client(instance)
        with client:
            data = client.get_report_paras(report_path)
            output_data(data, format=fmt, title=f"报表参数: {report_path}")
    except Exception as e:
        error(e)


@report_group.command("fonts")
@click.argument("report_path")
@click.option("-f", "--format", "fmt", type=click.Choice(["json", "table"]), default="json")
@click.option("-i", "--instance", help="FineReport 实例名")
def report_fonts(report_path, fmt, instance):
    """体检：模板用到但服务端缺失的字体（空 = 没问题）"""
    try:
        config = load_config(instance)
        data = reportops.template_fonts(config, report_path)
        output_data(data, format=fmt, title=f"字体体检: {report_path}")
    except Exception as e:
        error(e)


@report_group.command("sheet")
@click.argument("report_path")
@click.option("--list", "do_list", is_flag=True, help="只读列出所有 sheet")
@click.option("--add", "add_name", help="新增一张 sheet（克隆现有 sheet 的版面骨架）")
@click.option("--clone-from", help="克隆哪张 sheet 的版面（缺省第一张）")
@click.option("--rename", nargs=2, type=(str, str), metavar="旧名 新名", help="重命名 sheet")
@click.option("--remove", "remove_name", help="删除 sheet（不能删最后一张）")
@click.option("--apply", is_flag=True, help="🔴 真写服务端（默认只 dry-run 打印 diff）")
@click.option("--any-path", is_flag=True,
              help="确认写这个目标而不限范围（没有它就必须先设 $FRCLI_WRITE_SCOPE）")
@click.option("-f", "--format", "fmt", type=click.Choice(["json", "table"]), default="json")
@click.option("-i", "--instance", help="FineReport 实例名")
def report_sheet(report_path, do_list, add_name, clone_from, rename, remove_name,
                 apply, any_path, fmt, instance):
    """工作簿 sheet 管理（🟠 默认 dry-run）

    \b
    例：
      frcli report sheet …/r.cpt --list
      frcli report sheet …/r.cpt --add 口径说明 --apply
      frcli report sheet …/r.cpt --rename 口径说明 说明 --apply
      frcli report sheet …/r.cpt --remove 说明 --apply
    """
    try:
        if apply and not do_list:
            assert_write_scope(report_path, any_path)
        config = load_config(instance)
        if do_list:
            result = reportops.edit_sheet(config, report_path, apply=False, action="list")
        elif add_name:
            result = reportops.edit_sheet(config, report_path, apply=apply, action="add",
                                          name=add_name, clone_from=clone_from)
        elif rename:
            result = reportops.edit_sheet(config, report_path, apply=apply, action="rename",
                                          name=rename[0], new_name=rename[1])
        elif remove_name:
            result = reportops.edit_sheet(config, report_path, apply=apply, action="remove",
                                          name=remove_name)
        else:
            raise click.UsageError("要给 --list / --add / --rename / --remove 之一")
        _out_plan(result, fmt)
    except Exception as e:
        error(e)


@report_group.command("versions")
@click.argument("report_path")
@click.option("-n", "--limit", default=20, show_default=True, help="最多列多少条")
@click.option("-f", "--format", "fmt", type=click.Choice(["json", "table"]), default="json")
@click.option("-i", "--instance", help="FineReport 实例名")
def report_versions(report_path, limit, fmt, instance):
    """模板的远程设计提交历史（🟢 只读）"""
    try:
        config = load_config(instance)
        data = reportops.template_versions(config, report_path, limit)
        if fmt == "table":
            output_data(data["versions"], format="table",
                        title=f"版本历史: {data['report']}（{data['count']} 条）")
        else:
            output_data(data, format="json")
    except Exception as e:
        error(e)


@report_group.command("image")
@click.argument("report_path")
@click.option("-o", "--output", help="本地保存路径（缺省 <报表名>.png）")
@click.option("--form", is_flag=True, help="决策报表(.frm)用 exportFormAsImageData")
@click.option("-i", "--instance", help="FineReport 实例名")
def report_image(report_path, output, form, instance):
    """服务端直接把模板渲染成图片（🟢 只读，不走 REST 导出）

    `.cpt` 用 exportWorkBookAsImageData；`.frm` 决策报表加 --form。
    产物校验 PNG 魔数，绝不把出错页面当图片交付。
    """
    try:
        config = load_config(instance)
        data, meta = reportops.template_image(config, report_path, form=form)
        if not data.startswith(b"\x89PNG\r\n\x1a\n"):
            raise RuntimeError(f"返回内容不是 PNG（前 8 字节 {data[:8]!r}），已拒绝落盘")
        target = output or (Path(report_path).stem + ".png")
        meta["local"] = _write_image(target, data)
        success(meta)
    except Exception as e:
        error(e)


@report_group.command("edit")
@click.argument("report_path")
@click.option("--list", "list_only", is_flag=True,
              help="只列数据集/连接/参数（从真实模板字节读，不联网写）")
@click.option("--dataset", help="要改的数据集名（--list 可见）")
@click.option("--sql", help="整段替换该数据集的 SQL")
@click.option("--sql-file", type=click.Path(exists=True, dir_okay=False),
              help="从文件读新 SQL")
@click.option("--replace", multiple=True,
              help="在该数据集 SQL 内做字面替换，写 OLD=NEW，可重复")
@click.option("--connection", help="改该数据集的数据连接名（<DatabaseName>）")
@click.option("--param", help="要改默认值的数据集参数名")
@click.option("--default", help="参数新默认值（配合 --param）")
@click.option("--apply", is_flag=True, help="🔴 真写服务端（默认只 dry-run 打印 diff）")
@click.option("--any-path", is_flag=True,
              help="🔴 确认写这个目标而不限范围（本次调用生效；没有它就必须先设 "
                   "$FRCLI_WRITE_SCOPE，否则拒绝）")
@click.option("-f", "--format", "fmt", type=click.Choice(["json", "table"]), default="json")
@click.option("-i", "--instance", help="FineReport 实例名")
def report_edit(report_path, list_only, dataset, sql, sql_file, replace, connection,
                param, default, apply, any_path, fmt, instance):
    """结构化编辑服务端模板（默认 dry-run）

    拉模板 → 结构化改 XML（不是正则；除目标元素外字节原样保留）→ 打印 diff。
    加 --apply 才真写，写前过写范围守门、写时占锁+备份、写后回读校验 SHA256。

    \b
    例：
      frcli report edit demo_group/demo_user/skill测试/x.cpt --list
      frcli report edit …/x.cpt --dataset xs --replace "'20251013'='20251101'"
      frcli report edit …/x.cpt --dataset xs --sql-file new.sql --apply
    """
    try:
        # 守门放在最前：不依赖实例配置、也绝不依赖网络，任何情况下都先判定
        if apply:
            assert_write_scope(report_path, any_path)
        config = load_config(instance)
        if list_only:
            output_data(reportops.template_summary(config, report_path), format=fmt)
            return
        result = reportops.edit_template(
            config, report_path, apply=apply, dataset=dataset, sql=sql,
            sql_file=sql_file, replace=list(replace), connection=connection,
            param=param, default=default)
        if fmt == "table":
            for ch in result["changes"]:
                if ch.get("diff"):
                    click.echo(f"--- {ch['kind']} {ch.get('dataset', '')} ---")
                    click.echo(ch["diff"])
                else:
                    click.echo(f"{ch['kind']} {ch.get('dataset', '')}: "
                               f"{ch.get('before')!r} → {ch.get('after')!r}")
            click.echo("(dry-run，未写服务端)" if not result["applied"] else "(已写入)")
            return
        success(result)
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
                table.add_column("连接", style="magenta")
                table.add_column("SQL", style="white", max_width=60)

                for i, ds in enumerate(datasets, 1):
                    params = ", ".join(ds.get("parameters", []))
                    ds_sql = ds.get("sql", "")
                    if not sql and len(ds_sql) > 60:
                        ds_sql = ds_sql[:60] + "..."
                    table.add_row(str(i), ds.get("name", ""), params,
                                  ds.get("connection", ""), ds_sql)

                console.print(table)

                # 如果指定了 --sql，显示完整 SQL
                if sql:
                    for i, ds in enumerate(datasets, 1):
                        if ds.get("sql"):
                            console.print(f"\n[bold cyan]数据集 {i}: {ds['name']}[/]")
                            console.print(Panel(ds["sql"], title="SQL", border_style="blue"))
    except Exception as e:
        _platform_read_error_hint(e)
        error(e)


@report_group.command("preview")
@click.argument("report_path")
@click.option("--dataset", "dataset_name", required=True,
              help="模板里的数据集名（见 report datasets）")
@click.option("--params", help="数据集参数 JSON，如 '{\"edate\":\"2026-10-24\"}'")
@click.option("--rows", type=click.IntRange(1, 1000), default=100, show_default=True,
              help="最多预览行数")
@click.option("-f", "--format", "fmt", type=click.Choice(["json", "table"]), default="json")
@click.option("-i", "--instance", help="FineReport 实例名")
def report_preview(report_path, dataset_name, params, rows, fmt, instance):
    """预览 SQL 数据集（服务端真实执行查询，只取前 N 行；不写模板、不生成临时文件）

    等价于 Designer 里右键数据集 →「预览」。数据集 SQL 里的 `${x}` 按 --params 做文本替换，
    与平台语义一致；参数没给全时直接报错，不会静默替换成空串。
    """
    try:
        import json as _json

        from ..exceptions import ApiError

        parsed = {}
        if params:
            try:
                parsed = _json.loads(params)
            except ValueError as exc:
                raise ApiError(f"--params 不是合法 JSON: {exc}") from exc
            if not isinstance(parsed, dict):
                raise ApiError("--params 必须是 JSON 对象，如 '{\"edate\":\"2026-10-24\"}'")

        client = get_client(instance)
        with client:
            result = client.preview_report_dataset(
                report_path, dataset_name, params=parsed, rows=rows)

        if fmt == "json":
            output_data(result, format="json")
            return

        # 一律用 rich.text.Text 包裹动态内容：数据/列名里可能含 `[red]`、`[/]` 等文本，
        # 直接塞 str 会被 rich 当标记解析（丢字符，`[/]` 甚至抛 MarkupError 退出）。
        from ..output import console
        from rich.table import Table
        from rich.text import Text

        def _type_name(col):
            return col["type"].rsplit(".", 1)[-1] if col["type"] else ""

        columns = result["columns"]
        console.print(Text(f"数据集预览: {dataset_name}（{report_path}）"))
        rows_data = result["rows"]

        if len(columns) > 12:
            # 宽表不能横排：rich 在 80 列宽时会把 30+ 列压成 0 宽，表头和行值全部不可见
            # （agent/非 TTY 环境默认就这么宽）。改成列清单 + 每行纵向键值对。
            console.print(Text(f"列（{len(columns)} 个，宽表用纵向布局）:"))
            for i, col in enumerate(columns, 1):
                type_name = _type_name(col)
                suffix = f"  ({type_name})" if type_name else ""
                console.print(Text(f"  {i}. {col['name']}{suffix}"))
            for r_idx, row in enumerate(rows_data, 1):
                cells = [str(v) for v in row]
                if len(cells) < len(columns):
                    cells += [""] * (len(columns) - len(cells))
                console.print(Text(f"行 {r_idx}:"))
                for i, col in enumerate(columns, 1):
                    console.print(Text(f"    {i}. {col['name']} = {cells[i - 1]}"))
        else:
            table = Table()
            for col in columns:
                type_name = _type_name(col)
                header = Text(col["name"] + (f"\n{type_name}" if type_name else ""))
                table.add_column(header)
            for row in rows_data:
                cells = [str(v) for v in row]
                if len(cells) < len(columns):
                    cells += [""] * (len(columns) - len(cells))
                table.add_row(*[Text(c) for c in cells[:len(columns)]])
            console.print(table)

        console.print(Text(
            f"连接: {result['connection']} · 返回 {len(rows_data)} 行（请求上限 {rows}）",
            style="dim"))
    except Exception as e:
        error(e)


# ===========================================================================
# 模板创作：new / cell / dataset / param / style / table
# ---------------------------------------------------------------------------
# 约定（三组命令一致）：
#   * 地址用 **A1 记法**（`--at B3`），不用 c/r 数字
#   * 写命令**默认 dry-run**：打印 changes + 可读 diff + bytes_before/after，
#     加 `--apply` 才写；写前先过 `FRCLI_WRITE_SCOPE`（fail-closed）
# ===========================================================================
def _change_line(ch: dict) -> str:
    if ch.get("kind") == "warning":
        return f"⚠ {ch['message']}"
    if ch.get("kind") == "note":
        return f"ℹ {ch['message']}"
    skip = {"kind", "diff", "why"}
    body = ", ".join(f"{k}={v!r}" for k, v in ch.items() if k not in skip)
    return f"{ch['kind']}: {body}"


def _out_plan(result: dict, fmt: str):
    """写命令的统一输出：`-f table` 给人看（diff），json 给 agent 看（结构化）。

    ⚠ warning / ℹ note **同时打到 stderr**：这两类说的都是「服务端不会报错、
    但结果是错的」的静默坏法，只放在 stdout 的 JSON 里容易被只看 status 的调用方漏掉。
    """
    for ch in result["changes"]:
        if ch.get("kind") == "warning":
            click.echo(f"⚠ {ch['message']}", err=True)
        elif ch.get("kind") == "note":
            click.echo(f"ℹ {ch['message']}", err=True)
    if fmt != "table":
        success(result)
        return
    for ch in result["changes"]:
        if ch.get("diff"):
            click.echo(f"--- {ch['kind']} {ch.get('name', '')} ---")
            click.echo(ch["diff"])
        else:
            click.echo(_change_line(ch))
    if result.get("diff"):
        click.echo(result["diff"])
    click.echo(f"bytes: {result['bytes_before']} → {result['bytes_after']}")
    if result["dry_run"]:
        click.echo("(dry-run，未写服务端；确认无误加 --apply)")
    else:
        click.echo(f"(已写入 {result['remote']}，回读校验 "
                   f"{'ok' if result.get('upload', {}).get('verified') else '未确认'})")


@report_group.command("new")
@click.argument("report_path")
@click.option("--sheet", help="sheet 名（缺省 sheet1）")
@click.option("--from", "from_path",
              help="以某张模板为骨架（服务端路径或本地文件），保留其版面/样式外壳")
@click.option("--output", type=click.Path(dir_okay=False),
              help="同时把生成的模板写到本地文件（不联网）")
@click.option("--apply", is_flag=True, help="🔴 真写服务端（默认只 dry-run 打印骨架 diff）")
@click.option("--force", is_flag=True, help="服务端已存在同名模板时覆盖（默认拒绝）")
@click.option("--any-path", is_flag=True,
              help="确认写这个目标而不限范围（没有它就必须先设 $FRCLI_WRITE_SCOPE）")
@click.option("-f", "--format", "fmt", type=click.Choice(["json", "table"]), default="json")
@click.option("-i", "--instance", help="FineReport 实例名")
def report_new(report_path, sheet, from_path, output, apply, force, any_path, fmt, instance):
    """从零新建一个空白模板（🟠 默认只 dry-run）

    骨架 = `<TableDataMap/>` + 空 `<CellElementList>` + 保留版面外壳
    （页边距 / 行高列宽 / 模板参数 / 样式表）。`--from` 则拿现有模板裁出骨架。

    \b
    例：
      frcli report new demo_group/demo_user/skill测试/r.cpt --apply
      frcli report new …/r.cpt --from …/某张现成模板.cpt --apply
      frcli report new …/r.cpt --output /tmp/r.cpt          # 只生成本地文件
    """
    try:
        if apply:
            assert_write_scope(report_path, any_path)
        config = load_config(instance)
        _out_plan(reportops.new_template(config, report_path, sheet=sheet,
                                         from_path=from_path, apply=apply, output=output,
                                         force=force), fmt)
    except Exception as e:
        error(e)


@report_group.command("cell")
@click.argument("report_path")
@click.option("--list", "list_only", is_flag=True, help="只读列出单元格（不联网写）")
@click.option("--at", help="A1 记法，如 B3 / AA10")
@click.option("--sheet", help="sheet 名（多 sheet 时用）")
@click.option("--set-value", "value", help="写静态文本")
@click.option("--set-formula", "formula", help="写公式（可省前导 =，如 `=SUM(C3)`）")
@click.option("--bind", "binding", help="绑定数据集列，写 `数据集.列`，如 ds1.k")
@click.option("--set-ds-mode", "ds_mode",
              type=click.Choice(["group", "list", "summary"]),
              help="数据设置：group=分组(相同值合并) / list=列表(原样展开) / summary=汇总")
@click.option("--fn", "ds_fn", type=click.Choice(["sum", "count", "avg", "max", "min", "none"]),
              help="汇总函数（只能跟 --set-ds-mode summary 一起用；默认 sum）")
@click.option("--expand", type=click.Choice(["v", "h", "none"]),
              help="扩展方向：v=纵向(dir=0) / h=横向(dir=1) / none=不扩展")
@click.option("--style", type=int, help="引用已有样式索引（见 `report style --list`）")
@click.option("--num-format", help="数字格式：新建一个样式并绑定，如 #,##0.00 / #0.0%%")
@click.option("--bold", is_flag=True, help="配合 --num-format 等：新建粗体样式")
@click.option("--bg", help="底色 #RRGGBB（配合新建样式）")
@click.option("--align", type=click.Choice(["left", "center", "right"]), help="对齐")
@click.option("--border", is_flag=True, help="四边框（配合新建样式）")
@click.option("--merge", help="合并区域，如 A1:C1（合并信息写在左上角格，与 --at 一致）")
@click.option("--ds-result", help="数据集列的 <Result> 表达式（$$$ = 本列原值），"
                                  "如 \"FORMAT($$$,'yyyy-MM')\"；给空串=清除")
@click.option("--ds-filter", help="数据集列的行过滤公式（$$$ = 本列值），如 \"$$$>0\"；给空串=清除")
@click.option("--expand-left", help="显式左父格（A1 记法），如 A3 —— 组内小计行靠它挂到分组上")
@click.option("--expand-up", help="显式上父格（A1 记法），如 B1 —— 交叉表列头分组靠它")
@click.option("--show-html", is_flag=True,
              help="<CellGUIAttr showAsHTML=\"true\"/>：格子里的公式按 HTML 渲染（数据条/进度条）")
@click.option("--tooltip", help="单元格提示公式（写成公式，如 \"=FORMAT(C3,'0.0%')\"）")
@click.option("--clear", "clear_cell", is_flag=True, help="删掉该单元格")
@click.option("--apply", is_flag=True, help="🔴 真写服务端（默认只 dry-run 打印 diff）")
@click.option("--any-path", is_flag=True,
              help="确认写这个目标而不限范围（没有它就必须先设 $FRCLI_WRITE_SCOPE）")
@click.option("-f", "--format", "fmt", type=click.Choice(["json", "table"]), default="json")
@click.option("-i", "--instance", help="FineReport 实例名")
def report_cell(report_path, list_only, at, sheet, value, formula, binding, ds_mode, ds_fn,
                expand, style,
                num_format, bold, bg, align, border, merge, ds_result, ds_filter,
                expand_left, expand_up, show_html, tooltip, clear_cell, apply, any_path, fmt,
                instance):
    """看/改单个单元格（🟢 --list 只读；🟠 改默认 dry-run）

    \b
    例：
      frcli report cell …/r.cpt --list -f table
      frcli report cell …/r.cpt --at A1 --set-value "门店数" --apply
      frcli report cell …/r.cpt --at C3 --bind ds1.shop_cnt --expand v --apply
      frcli report cell …/r.cpt --at C3 --set-ds-mode list --apply
      frcli report cell …/r.cpt --at D3 --set-ds-mode summary --fn sum --apply
      frcli report cell …/r.cpt --at A1 --set-formula '="TOP" + $topn' --merge A1:C1 --apply
      frcli report cell …/r.cpt --at B2 --set-formula "=SUM(C3)" --num-format "#,##0" --apply
      frcli report cell …/r.cpt --at A3 --bind ds1.d --ds-result "FORMAT($$$,'yyyy-MM')" --apply
      frcli report cell …/r.cpt --at A4 --set-formula "=SUM(C3)" --expand-left A3 --apply
    """
    try:
        config = load_config(instance)
        if list_only:
            output_data(reportops.template_cells(config, report_path, sheet=sheet),
                        format=fmt)
            return
        if apply:
            assert_write_scope(report_path, any_path)
        if not at:
            raise click.UsageError("要给 --at A1（或用 --list 只看不改）")
        if not any([value is not None, formula is not None, binding is not None,
                    ds_mode, ds_fn, expand, style is not None, num_format, bold, bg, align,
                    border, merge, ds_result is not None, ds_filter is not None,
                    expand_left, expand_up, show_html, tooltip is not None, clear_cell]):
            raise click.UsageError("没有给任何动作（--set-value/--set-formula/--bind/"
                                   "--set-ds-mode/--expand/--style/--num-format/--merge/"
                                   "--ds-result/--ds-filter/--expand-left/--show-html/--clear）")
        result = reportops.edit_cell(config, report_path, apply=apply, sheet=sheet, at=at,
                                     value=value, formula=formula, binding=binding,
                                     ds_mode=ds_mode, ds_fn=ds_fn,
                                     expand=expand, style=style, fmt=num_format,
                                     bold=bold, bg=bg, align=align, border=border,
                                     merge=merge, clear=clear_cell,
                                     ds_result=ds_result, ds_filter=ds_filter,
                                     expand_left=expand_left, expand_up=expand_up,
                                     show_html=show_html, tooltip=tooltip)
        _out_plan(result, fmt)
    except Exception as e:
        error(e)


@report_group.command("highlight")
@click.argument("report_path")
@click.option("--list", "list_only", is_flag=True, help="只读列出条件属性（不联网写）")
@click.option("--at", help="A1 记法，如 D3；**支持区域** A3:D3（整行条件属性）")
@click.option("--rule", "rules", multiple=True,
              help="规则 `条件:动作`，可重复（顺序即优先级），如 "
                   "'v>1000:bg=#FF0000' / 'v>=0.7:bg=#63BE7B' / 'ROW()%2=0:bg=#F2F2F2' / "
                   "'v<0:rowheight=0'。条件以 `v`+比较符开头 = 值比较，其余当公式；"
                   "动作: bg=#RRGGBB / fg=#RRGGBB / bold / italic / size=N / font=名 / "
                   "rowheight=N(0=隐藏整行) / value=公式 / border")
@click.option("--clear", is_flag=True, help="清掉这些格子上的全部条件属性")
@click.option("--sheet", help="sheet 名（多 sheet 时用）")
@click.option("--apply", is_flag=True, help="🔴 真写服务端（默认只 dry-run 打印 diff）")
@click.option("--any-path", is_flag=True,
              help="确认写这个目标而不限范围（没有它就必须先设 $FRCLI_WRITE_SCOPE）")
@click.option("-f", "--format", "fmt", type=click.Choice(["json", "table"]), default="json")
@click.option("-i", "--instance", help="FineReport 实例名")
def report_highlight(report_path, list_only, at, rules, clear, sheet, apply, any_path, fmt,
                     instance):
    """条件属性 `<Highlight>`：阈值标红 / 热力图 / 隔行变色 / 隐藏整行（🟠 默认 dry-run）

    \b
    例：
      frcli report highlight …/r.cpt --at D3 --rule 'v>1000:bg=#FF0000,bold' --apply
      frcli report highlight …/r.cpt --at B3 --rule 'v>=0.7:bg=#63BE7B' \\
          --rule 'v>=0.5:bg=#FFEB84' --rule 'v<0.5:bg=#F8696B' --apply
      frcli report highlight …/r.cpt --at A3:D3 --rule 'ROW()%2=0:bg=#F2F2F2' --apply
      frcli report highlight …/r.cpt --at B3 --rule 'v<0:rowheight=0' --apply   # 整行隐藏
      frcli report highlight …/r.cpt --at A3:D9 --list -f table
    """
    try:
        config = load_config(instance)
        if list_only:
            output_data(reportops.template_highlights(config, report_path, at=at, sheet=sheet),
                        format=fmt)
            return
        if apply:
            assert_write_scope(report_path, any_path)
        if not at:
            raise click.UsageError("要给 --at A1（或用 --list 只看不改）")
        if not rules and not clear:
            raise click.UsageError("要给 --rule '条件:动作'（或用 --clear 清掉）")
        result = reportops.edit_highlight(config, report_path, apply=apply, at=at,
                                         sheet=sheet, rules=list(rules), clear=clear)
        _out_plan(result, fmt)
    except Exception as e:
        error(e)


@report_group.command("crosstab")
@click.argument("report_path")
@click.option("--dataset", required=True, help="数据集名（先 report dataset --add）")
@click.option("--at", required=True, help="左上角起点（A1 记法），表头/数据/总计从这里往下排")
@click.option("--row", "row_dims", required=True, help="行维度列，逗号分隔（纵向扩展）")
@click.option("--col", "col_dims", required=True, help="列维度列，逗号分隔（横向扩展）")
@click.option("--value", "values", required=True, help="值列，逗号分隔（行列交叉点上）")
@click.option("--agg", type=click.Choice(["sum", "count", "avg", "max", "min", "none"]),
              help="值格聚合方式；不给=分组(FunctionGrouper，官方做法，同一交叉点多记录会去重)")
@click.option("--total-row", is_flag=True, help="底部总计行（逐列公式 =SUM(值格首行)）")
@click.option("--total-col", is_flag=True, help="右侧行汇总列（SummaryGrouper）")
@click.option("--no-header", is_flag=True, help="不生成表头行")
@click.option("--label", "labels", help="角标文字（不给=自动 '行维度/列维度'）")
@click.option("--value-labels", help="值列的表头文字，逗号分隔")
@click.option("--style", type=int, help="数据行样式索引")
@click.option("--header-style", type=int, help="表头样式索引")
@click.option("--widths", help="列宽（字符数），逗号分隔")
@click.option("--sheet", help="sheet 名（多 sheet 时用）")
@click.option("--apply", is_flag=True, help="🔴 真写服务端（默认只 dry-run 打印 diff）")
@click.option("--any-path", is_flag=True,
              help="确认写这个目标而不限范围（没有它就必须先设 $FRCLI_WRITE_SCOPE）")
@click.option("-f", "--format", "fmt", type=click.Choice(["json", "table"]), default="json")
@click.option("-i", "--instance", help="FineReport 实例名")
def report_crosstab(report_path, dataset, at, row_dims, col_dims, values, agg, total_row,
                    total_col, no_header, labels, value_labels, style, header_style, widths,
                    sheet, apply, any_path, fmt, instance):
    """交叉表 / 动态列：行维度纵向 × 列维度横向 × 值汇总（🟠 默认 dry-run）

    列数随数据自动增长（列维度有几个值就几列），缺失的 (行,列) 组合留空格。
    不需要显式父子格：引擎自动把最近的上方扩展格当列父格、左侧扩展格当行父格。

    \b
    例：
      frcli report crosstab …/r.cpt --dataset ds1 --at A3 \\
          --row 地区,销售员 --col 产品 --value 销量 --agg sum \\
          --total-row --total-col --header-style 0 --apply
    """
    try:
        if apply:
            assert_write_scope(report_path, any_path)
        config = load_config(instance)
        result = reportops.edit_crosstab(
            config, report_path, apply=apply, dataset=dataset, at=at,
            rows=row_dims.split(","), cols=col_dims.split(","), values=values.split(","),
            agg=agg, total_row=total_row, total_col=total_col, header=not no_header,
            labels=[labels] if labels else None,
            value_labels=value_labels.split(",") if value_labels else None,
            style=style, header_style=header_style,
            widths=widths.split(",") if widths else None, sheet=sheet)
        _out_plan(result, fmt)
    except Exception as e:
        error(e)


@report_group.command("dataset")
@click.argument("report_path")
@click.option("--list", "list_only", is_flag=True, help="只读列出数据集（从模板字节读）")
@click.option("--full", is_flag=True, help="--list 时显示完整 SQL")
@click.option("--add", "add_name", help="新增数据集（给名字）")
@click.option("--conn", help="数据连接名（--add 必给，见 `report serverdatasets`）")
@click.option("--sql", "sql_text", help="SQL 正文（--add / --set-sql 用）")
@click.option("--sql-file", type=click.Path(exists=True, dir_okay=False), help="从文件读 SQL")
@click.option("--param", "params", multiple=True,
              help="数据集参数，写 名字 或 名字=默认值，可重复（--add 用）")
@click.option("--page-sql", default="", help="分页查询 SQL（一般留空）")
@click.option("--set-sql", "set_sql_name", help="整段替换某数据集的 SQL（给数据集名）")
@click.option("--remove", "remove_name", help="删掉某数据集（给名字）")
@click.option("--apply", is_flag=True, help="🔴 真写服务端（默认只 dry-run 打印 diff）")
@click.option("--any-path", is_flag=True,
              help="确认写这个目标而不限范围（没有它就必须先设 $FRCLI_WRITE_SCOPE）")
@click.option("-f", "--format", "fmt", type=click.Choice(["json", "table"]), default="json")
@click.option("-i", "--instance", help="FineReport 实例名")
def report_dataset(report_path, list_only, full, add_name, conn, sql_text, sql_file, params,
                   page_sql, set_sql_name, remove_name, apply, any_path, fmt, instance):
    """数据集增删改（🟢 --list 只读；🟠 写默认 dry-run）

    ⚠️ 与 `report datasets` 的区别：那条走 REST `format=cpt`（数据集坏时报错、可能读不到），
    这条走远程设计通道读**模板字节**，能读到 CLI 自己刚写的模板。

    \b
    例：
      frcli report dataset …/r.cpt --list --full
      frcli report dataset …/r.cpt --add ds1 --conn demo_conn \\
          --sql "select 'A' k, 1 v" --param min_center=01 --apply
      frcli report dataset …/r.cpt --set-sql ds1 --sql-file new.sql --apply
      frcli report dataset …/r.cpt --remove ds1 --apply
    """
    try:
        config = load_config(instance)
        if list_only:
            output_data(reportops.template_datasets(config, report_path, sql=full),
                        format=fmt)
            return
        if apply:
            assert_write_scope(report_path, any_path)
        given = [bool(add_name), bool(set_sql_name), bool(remove_name)]
        if sum(given) != 1:
            raise click.UsageError("--add / --set-sql / --remove 三选一（或用 --list 只看）")
        if add_name:
            if not conn:
                raise click.UsageError("--add 必须给 --conn 数据连接名")
            if sql_text is None and not sql_file:
                raise click.UsageError("--add 必须给 --sql 或 --sql-file")
            result = reportops.edit_dataset(config, report_path, apply=apply, op="add",
                                            name=add_name, conn=conn, sql=sql_text,
                                            sql_file=sql_file, params=params,
                                            page_sql=page_sql)
        elif set_sql_name:
            if sql_text is None and not sql_file:
                raise click.UsageError("--set-sql 必须给 --sql 或 --sql-file")
            result = reportops.edit_dataset(config, report_path, apply=apply, op="set-sql",
                                            name=set_sql_name, sql=sql_text,
                                            sql_file=sql_file, params=params)
        else:
            result = reportops.edit_dataset(config, report_path, apply=apply, op="remove",
                                            name=remove_name)
        _out_plan(result, fmt)
    except Exception as e:
        error(e)


@report_group.command("param")
@click.argument("report_path")
@click.option("--list", "list_only", is_flag=True, help="只读列出模板参数")
@click.option("--add", "adds", multiple=True,
              help="加模板参数：名字 或 名字=默认值（可重复）")
@click.option("--remove", "removes", multiple=True, help="删模板参数（可重复）")
@click.option("--set-default", "defaults", multiple=True,
              help="改默认值，写 名字=值（可重复）")
@click.option("--apply", is_flag=True, help="🔴 真写服务端（默认只 dry-run 打印 diff）")
@click.option("--any-path", is_flag=True,
              help="确认写这个目标而不限范围（没有它就必须先设 $FRCLI_WRITE_SCOPE）")
@click.option("-f", "--format", "fmt", type=click.Choice(["json", "table"]), default="json")
@click.option("-i", "--instance", help="FineReport 实例名")
def report_param(report_path, list_only, adds, removes, defaults, apply, any_path, fmt,
                 instance):
    """模板参数（决定单元格公式里的 `$名字` 能不能解析）

    ⚠️ 参数**必须给默认值**：既没传值又没默认值时静默变成空字符串（不报错、导出照成功），
    用户不带参数打开就是一片空白 —— 这种坏法最难查。

    \b
    例：
      frcli report param …/r.cpt --list
      frcli report param …/r.cpt --add topn=10 --add min_center=01 --apply
      frcli report param …/r.cpt --set-default topn=20 --apply
    """
    try:
        config = load_config(instance)
        if list_only:
            output_data(reportops.template_params(config, report_path), format=fmt)
            return
        if apply:
            assert_write_scope(report_path, any_path)
        result = reportops.edit_param(config, report_path, apply=apply, add=adds,
                                      remove=removes, set_default=defaults)
        _out_plan(result, fmt)
    except Exception as e:
        error(e)


@report_group.command("style")
@click.argument("report_path")
@click.option("--list", "list_only", is_flag=True, help="只读列出样式表（索引 / 数字格式…）")
@click.option("--add", "add_style", is_flag=True, help="追加一个样式到 <StyleList>")
@click.option("--xml-file", type=click.Path(exists=True, dir_okay=False),
              help="样式片段文件（`<Style>…</Style>`，从 references/cpt-authoring.md 抄）")
@click.option("--num-format", help="数字格式，如 #,##0.00 / #0.0%%")
@click.option("--bold", is_flag=True, help="粗体")
@click.option("--bg", help="底色 #RRGGBB")
@click.option("--align", type=click.Choice(["left", "center", "right"]), help="对齐")
@click.option("--border", is_flag=True, help="四边框")
@click.option("--size-pt", type=float, default=None, help="字号（磅）；只改字号也行")
@click.option("--apply", is_flag=True, help="🔴 真写服务端（默认只 dry-run 打印 diff）")
@click.option("--any-path", is_flag=True,
              help="确认写这个目标而不限范围（没有它就必须先设 $FRCLI_WRITE_SCOPE）")
@click.option("-f", "--format", "fmt", type=click.Choice(["json", "table"]), default="json")
@click.option("-i", "--instance", help="FineReport 实例名")
def report_style(report_path, list_only, add_style, xml_file, num_format, bold, bg, align,
                 border, size_pt, apply, any_path, fmt, instance):
    """样式表（数字格式 / 粗体 / 底色 / 边框），追加后用 `report cell --style N` 绑定

    \b
    例：
      frcli report style …/r.cpt --list
      frcli report style …/r.cpt --add --num-format "#,##0.00" --border --apply
      frcli report style …/r.cpt --add --xml-file style.xml --apply
    """
    try:
        config = load_config(instance)
        if list_only:
            output_data(reportops.template_styles(config, report_path), format=fmt)
            return
        if apply:
            assert_write_scope(report_path, any_path)
        if not add_style:
            raise click.UsageError("要给 --add（或用 --list 只看）")
        if xml_file:
            result = reportops.edit_style(config, report_path, apply=apply, xml_file=xml_file)
        else:
            result = reportops.edit_style(config, report_path, apply=apply, preset=True,
                                          fmt=num_format, bold=bold, bg=bg, align=align,
                                          border=border, size_pt=size_pt)
        _out_plan(result, fmt)
    except Exception as e:
        error(e)


@report_group.command("table")
@click.argument("report_path")
@click.option("--dataset", "dataset", required=True, help="数据集名（模板里已有的）")
@click.option("--at", required=True, help="表格左上角，A1 记法，如 A1")
@click.option("--columns", required=True, help="列名，逗号分隔，如 k,val")
@click.option("--mode", "mode", type=click.Choice(["group", "list", "summary"]),
              default="list", show_default=True,
              help="数据设置：list=列表(原样展开，默认) / group=分组(相同值合并) / "
                   "summary=汇总(配合 --group-by/--fn)")
@click.option("--fn", "ds_fn", type=click.Choice(["sum", "count", "avg", "max", "min", "none"]),
              help="汇总函数（只能跟 --mode summary 一起用；默认 sum）")
@click.option("--group-by", "group_by",
              help="--mode summary 时的分组列（逗号分隔），其余列做汇总；不给则全部汇总")
@click.option("--header", is_flag=True, help="带表头（表头文字默认用列名）")
@click.option("--labels", help="自定义表头文字，逗号分隔（隐含 --header）")
@click.option("--expand", type=click.Choice(["v", "h", "none"]), default="v",
              show_default=True, help="数据区扩展方向：v=纵向 / h=横向")
@click.option("--style", type=int, help="数据行样式索引")
@click.option("--header-style", type=int, help="表头样式索引")
@click.option("--widths", help="列宽（字符数），逗号分隔，与 --columns 一一对应，如 12,16,14")
@click.option("--sheet", help="sheet 名（多 sheet 时用）")
@click.option("--apply", is_flag=True, help="🔴 真写服务端（默认只 dry-run 打印 diff）")
@click.option("--any-path", is_flag=True,
              help="确认写这个目标而不限范围（没有它就必须先设 $FRCLI_WRITE_SCOPE）")
@click.option("-f", "--format", "fmt", type=click.Choice(["json", "table"]), default="json")
@click.option("-i", "--instance", help="FineReport 实例名")
def report_table(report_path, dataset, at, columns, mode, ds_fn, group_by, header, labels,
                 expand, style, header_style, widths, sheet, apply, any_path, fmt, instance):
    """一次生成整张取数表（表头 + 逐列绑定 + 扩展方向 + 数据设置，🟠 默认 dry-run）

    \b
    例：
      frcli report table …/r.cpt --dataset ds1 --at A1 --columns k,val --header --apply
      frcli report table …/r.cpt --dataset ds1 --at A2 --columns k,val --mode group --apply
      frcli report table …/r.cpt --dataset ds1 --at A2 --columns 地区,销售员,销量 \\
          --mode summary --group-by 地区,销售员 --fn sum --header --apply
      frcli report table …/r.cpt --sheet 明细表 --dataset ds1 --at A2 --columns k,val --apply
    """
    try:
        if apply:
            assert_write_scope(report_path, any_path)
        config = load_config(instance)
        label_list = [x for x in (labels or "").split(",")] if labels else None
        result = reportops.edit_table(config, report_path, apply=apply, dataset=dataset,
                                      at=at, columns=[c for c in columns.split(",")],
                                      header=header or bool(labels), labels=label_list,
                                      expand=expand, style=style,
                                      header_style=header_style,
                                      mode=mode, fn=ds_fn,
                                      group_by=[g for g in (group_by or "").split(",")],
                                      widths=[w for w in widths.split(",")] if widths else None,
                                      sheet=sheet)
        _out_plan(result, fmt)
    except Exception as e:
        error(e)


@report_group.command("page")
@click.argument("report_path")
@click.option("--list", "list_only", is_flag=True, help="只读列出分页设置（不联网写）")
@click.option("--header-height", type=float, help="页眉高度（磅）；页眉内容在 <Header>（本 CLI 只读）")
@click.option("--footer-height", type=float, help="页脚高度（磅）")
@click.option("--freeze", help="冻结列行，写 `列数,行数`（如 `1,0` = 冻结第 1 列）；`none` 清除")
@click.option("--repeat-rows", help="这些 Excel 行号（从 1 起，逗号分隔）允许跨页重复（= 缺省）")
@click.option("--no-repeat-rows", help="这些行**不**跨页重复（写 CellPageAttr repeat=\"false\"）")
@click.option("--repeat-header-rows", help="★每页重复标题行：`起始:结束`（0 基闭区间，如 1:1）")
@click.option("--repeat-footer-rows", help="每页重复表尾行（同上记法）")
@click.option("--repeat-header-cols", help="每页重复标题列（同上记法）")
@click.option("--repeat-footer-cols", help="每页重复表尾列（同上记法）")
@click.option("--page-freeze", type=click.Choice(["on", "off"]),
              help="页面冻结开关（UPFCR，预览态滚动；导出态无差异）")
@click.option("--header-text", help="页眉文字（自动加引号；--header-formula 时按公式）")
@click.option("--footer-text", help="页脚文字/公式；页码用 $$page_number / $$totalPage_number")
@click.option("--header-position", type=click.Choice(["left", "center", "right"]),
              default="center", show_default=True)
@click.option("--footer-position", type=click.Choice(["left", "center", "right"]),
              default="center", show_default=True)
@click.option("--header-formula", is_flag=True, help="--header-text 按公式写（不加引号）")
@click.option("--footer-formula", is_flag=True, help="--footer-text 按公式写（不加引号）")
@click.option("--sheet", help="sheet 名（多 sheet 时用）")
@click.option("--apply", is_flag=True, help="🔴 真写服务端（默认只 dry-run 打印 diff）")
@click.option("--any-path", is_flag=True,
              help="确认写这个目标而不限范围（没有它就必须先设 $FRCLI_WRITE_SCOPE）")
@click.option("-f", "--format", "fmt", type=click.Choice(["json", "table"]), default="json")
@click.option("-i", "--instance", help="FineReport 实例名")
def report_page(report_path, list_only, header_height, footer_height, freeze, repeat_rows,
                no_repeat_rows, repeat_header_rows, repeat_footer_rows, repeat_header_cols,
                repeat_footer_cols, page_freeze, header_text, footer_text, header_position,
                footer_position, header_formula, footer_formula, sheet, apply, any_path, fmt,
                instance):
    """分页设置：页眉页脚高度 / 冻结列 / 重复标题行（🟠 默认 dry-run）

    ⚠ `CellPageAttr repeat` **缺省就是 true**：服务端字段初值 63（全位），
    所以「没写」= 允许跨页重复，`repeat="false"` 才是关闭。

    \b
    例：
      frcli report page …/r.cpt --list -f table
      frcli report page …/r.cpt --freeze 1,0 --header-height 40 --apply
      frcli report page …/r.cpt --repeat-header-rows 1:1 --apply     # ★每页重复标题行
      frcli report page …/r.cpt --footer-text '"第 " + $$page_number + " 页"' \
          --footer-formula --footer-height 20 --apply                # 页脚页码
      frcli report page …/r.cpt --no-repeat-rows 3,4 --apply
    """
    try:
        config = load_config(instance)
        if list_only:
            output_data(reportops.template_page(config, report_path, sheet=sheet), format=fmt)
            return
        if apply:
            assert_write_scope(report_path, any_path)
        result = reportops.edit_page(config, report_path, apply=apply, sheet=sheet,
                                     header_height=header_height, footer_height=footer_height,
                                     freeze=freeze, repeat_rows=repeat_rows,
                                     no_repeat_rows=no_repeat_rows,
                                     repeat_header_rows=repeat_header_rows,
                                     repeat_footer_rows=repeat_footer_rows,
                                     repeat_header_cols=repeat_header_cols,
                                     repeat_footer_cols=repeat_footer_cols,
                                     page_freeze=page_freeze,
                                     header_text=header_text, footer_text=footer_text,
                                     header_position=header_position,
                                     footer_position=footer_position,
                                     header_formula=header_formula,
                                     footer_formula=footer_formula)
        _out_plan(result, fmt)
    except Exception as e:
        error(e)


@report_group.command("chart")
@click.argument("report_path")
@click.option("--list", "list_only", is_flag=True, help="只读列出模板里的图表")
@click.option("--at", help="图表左上角（A1 记法）；图表占 cs 列 × rs 行，必须是空格子")
@click.option("--dataset", help="数据集名（先 report dataset --add）")
@click.option("--type", "kind", default="column", show_default=True,
              help="column(柱形) / line(折线) / pie(饼) / ring(环形)")
@click.option("--category", help="分类轴列（饼图=扇区列）")
@click.option("--series", help="系列列（图例）；饼图给了就是\"每分类一张饼\"")
@click.option("--value", help="数值列")
@click.option("--fn", "chart_fn", default="sum", show_default=True,
              help="聚合函数：sum/count/avg/max/min/none")
@click.option("--title", help="图表标题")
@click.option("--show-title", is_flag=True, help="显式显示标题（不给 --title 时用默认标题）")
@click.option("--cs", type=int, help="占几列（缺省取官方样例：柱 9 / 折 9 / 饼环 7）")
@click.option("--rs", type=int, help="占几行（缺省取官方样例：柱 20 / 折 19 / 饼环 17）")
@click.option("--sheet", help="sheet 名（多 sheet 时用）")
@click.option("--apply", is_flag=True, help="🔴 真写服务端（默认只 dry-run 打印 diff）")
@click.option("--any-path", is_flag=True,
              help="确认写这个目标而不限范围（没有它就必须先设 $FRCLI_WRITE_SCOPE）")
@click.option("-f", "--format", "fmt", type=click.Choice(["json", "table"]), default="json")
@click.option("-i", "--instance", help="FineReport 实例名")
def report_chart(report_path, list_only, at, dataset, kind, category, series, value, chart_fn,
                 title, show_title, cs, rs, sheet, apply, any_path, fmt, instance):
    """在单元格里插图表（VanChart：柱形/折线/饼/环形，🟠 默认 dry-run）

    验收必须**看图**：`report image`(PNG) 或 `export pdf` —— 列名写错时不会报错，只会画出空图。

    \b
    例：
      frcli report chart …/r.cpt --at A1 --dataset ds1 --type column \
          --category 地区 --series 产品 --value 销量 --fn sum --title "销量对比" --apply
      frcli report chart …/r.cpt --at A1 --dataset ds1 --type pie --category 地区 --value 销量 --apply
      frcli report chart …/r.cpt --list -f table
    """
    try:
        config = load_config(instance)
        if list_only:
            output_data(reportops.template_charts(config, report_path, sheet=sheet), format=fmt)
            return
        if apply:
            assert_write_scope(report_path, any_path)
        if not at:
            raise click.UsageError("要给 --at A1（或用 --list 只看不改）")
        result = reportops.edit_chart(config, report_path, apply=apply, at=at, dataset=dataset,
                                      kind=kind, category=category, series=series, value=value,
                                      fn=chart_fn, title=title, show_title=show_title,
                                      cs=cs, rs=rs, sheet=sheet)
        _out_plan(result, fmt)
    except Exception as e:
        error(e)


@report_group.command("link")
@click.argument("report_path")
@click.option("--list", "list_only", is_flag=True, help="只读列出超链接")
@click.option("--at", help="A1 记法；支持区域 A3:A10（整列钻取）")
@click.option("--to", help="目标：报表路径（reportlet）/ URL（web）/ 脚本（javascript）")
@click.option("--type", "kind", default="reportlet", show_default=True,
              help="reportlet(网络报表钻取) / web(网页链接) / javascript")
@click.option("--param", "params", multiple=True,
              help="传给目标报表的参数 `名=值`，可重复；值以 `=` 开头当公式（如 `center=$A3`）")
@click.option("--frame", default="_self", show_default=True, help="打开方式 _self / _blank")
@click.option("--clear", is_flag=True, help="摘掉这些格子上的超链接")
@click.option("--sheet", help="sheet 名（多 sheet 时用）")
@click.option("--apply", is_flag=True, help="🔴 真写服务端（默认只 dry-run 打印 diff）")
@click.option("--any-path", is_flag=True,
              help="确认写这个目标而不限范围（没有它就必须先设 $FRCLI_WRITE_SCOPE）")
@click.option("-f", "--format", "fmt", type=click.Choice(["json", "table"]), default="json")
@click.option("-i", "--instance", help="FineReport 实例名")
def report_link(report_path, list_only, at, to, kind, params, frame, clear, sheet, apply,
                any_path, fmt, instance):
    """单元格超链接 / 钻取（🟠 默认 dry-run）

    超链接是**纯预览态交互**：实测 `export excel` / `export pdf` **都不保留任何链接痕迹**
    （xlsx 的 `sheet1.xml` 里 `<hyperlink>` 0 处、pdf 的 `/URI` `/Annots` `/Link` 全 0），
    点击跳转只能在预览页发生；⇒ **验收读模板**（`report link --list`），别去导出产物里找。

    \b
    例：
      frcli report link …/r.cpt --at A3 --to demo_group/demo_user/skill测试/patterns/r1_group_subtotal.cpt \
          --param center=$A3 --apply                     # 钻取：把本行中心传给目标报表
      frcli report link …/r.cpt --at A1 --type web --to https://www.fanruan.com \\
          --frame _blank --apply
      frcli report link …/r.cpt --list -f table
    """
    try:
        config = load_config(instance)
        if list_only:
            output_data(reportops.template_links(config, report_path, at=at, sheet=sheet),
                        format=fmt)
            return
        if apply:
            assert_write_scope(report_path, any_path)
        if not at:
            raise click.UsageError("要给 --at A1（或用 --list 只看不改）")
        pairs = []
        for item in params:
            k, _, v = item.partition("=")
            if not k:
                raise click.UsageError(f"--param 要写成 名=值，收到 {item!r}")
            pairs.append((k, v))
        result = reportops.edit_link(config, report_path, apply=apply, at=at, to=to, kind=kind,
                                     params=pairs, frame=frame, clear=clear, sheet=sheet)
        _out_plan(result, fmt)
    except Exception as e:
        error(e)


@report_group.command("widget")
@click.argument("report_path")
@click.option("--list", "list_only", is_flag=True, help="只读列出参数面板控件")
@click.option("--param", "param", help="参数名（须与模板参数 / SQL 里的 ${同名} 一致）")
@click.option("--type", "kind", default="combo", show_default=True,
              help="combo(下拉) / date(日期) / text(文本) / check(下拉多选) / number(数字)")
@click.option("--options", help="下拉选项，逗号分隔（key=value 或只给 key），如 华东,华南")
@click.option("--default", "default_value", help="控件默认值（同时给模板参数补默认值）")
@click.option("--label", help="控件标签（缺省 `参数名:`）")
@click.option("--x", type=int, default=30, show_default=True, help="面板坐标 x")
@click.option("--y", type=int, default=20, show_default=True, help="面板坐标 y")
@click.option("--width", type=int, default=120, show_default=True, help="控件宽")
@click.option("--height", type=int, default=21, show_default=True, help="控件高")
@click.option("--no-declare", is_flag=True, help="不要自动补模板参数声明")
@click.option("--apply", is_flag=True, help="🔴 真写服务端（默认只 dry-run 打印 diff）")
@click.option("--any-path", is_flag=True,
              help="确认写这个目标而不限范围（没有它就必须先设 $FRCLI_WRITE_SCOPE）")
@click.option("-f", "--format", "fmt", type=click.Choice(["json", "table"]), default="json")
@click.option("-i", "--instance", help="FineReport 实例名")
def report_widget(report_path, list_only, param, kind, options, default_value, label, x, y,
                  width, height, no_declare, apply, any_path, fmt, instance):
    """参数面板控件（下拉/日期/文本，🟠 默认 dry-run）

    **绑定靠"控件名 = 参数名"**（服务端 `getWidgetByName(parameter.getName())`）：
    `--param p` 必须与模板参数、以及 SQL 里的 `${p}` 同名，才会真正联动。

    \b
    例：
      frcli report widget …/r.cpt --param area --type combo --options 华东,华南 --default 华东 --apply
      frcli report widget …/r.cpt --param d1 --type date --default 2026-09-01 --apply
      frcli report widget …/r.cpt --list -f table
    """
    try:
        config = load_config(instance)
        if list_only:
            output_data(reportops.template_widgets(config, report_path), format=fmt)
            return
        if apply:
            assert_write_scope(report_path, any_path)
        if not param:
            raise click.UsageError("要给 --param 参数名（或用 --list 只看）")
        opts = [o for o in (options or "").split(",") if o]
        result = reportops.edit_widget(config, report_path, apply=apply, param=param, kind=kind,
                                       options=opts, default=default_value, label=label,
                                       x=x, y=y, width=width, height=height,
                                       declare=not no_declare)
        _out_plan(result, fmt)
    except Exception as e:
        error(e)
