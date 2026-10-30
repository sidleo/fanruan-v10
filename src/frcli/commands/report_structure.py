"""CPT 结构检查、引用查询与坐标变换的固定命令。"""

import click

from .. import cptmodel, cpttransform, reportops
from ..output import error, output_data


def _options(write=False):
    def decorate(function):
        options = [click.argument("target"),
                   click.option("--local", is_flag=True, help="本地 CPT；不读取实例或联网"),
                   click.option("--sheet", help="准确的 sheet 名，多 sheet 结构操作必给"),
                   click.option("--block", type=click.IntRange(min=1), help="聚合块的 1 基序号"),
                   click.option("-f", "--format", "fmt", type=click.Choice(["json", "table"]), default="json"),
                   click.option("-i", "--instance", help="实例名")]
        if write:
            options += [click.option("--apply", is_flag=True, help="执行变更；默认仅预览"),
                        click.option("-o", "--output", type=click.Path(dir_okay=False), help="本地执行时写入的新文件"),
                        click.option("--any-path", is_flag=True, help="显式放行本次已授权远端目标")]
        for option in reversed(options):
            function = option(function)
        return function
    return decorate


def _read(target, local, instance, apply=False, any_path=False, output=None):
    from .report import _template_config, assert_write_scope
    if apply and not local:
        assert_write_scope(target, any_path)
    config = _template_config(instance, target, local, output)
    text = reportops.read_template(config, target).decode("utf-8")
    return config, text


def _perform(target, local, instance, sheet, block, apply, any_path, output, fmt, planner, **kwargs):
    from .report import _out_plan
    try:
        config, text = _read(target, local, instance, apply, any_path, output)
        new_text, changes, extra = planner(text, sheet=sheet, block=block, **kwargs)
        result = reportops.commit(config, target, text, new_text, extra.pop("action", "structure"),
                                  changes, apply=apply, extra=extra)
        _out_plan(result, fmt)
    except Exception as exc:
        error(exc)


def register(group):
    @group.command("validate")
    @_options()
    def validate(target, local, sheet, block, fmt, instance):
        """离线结构与引用检查；不能代替运行时预览、取数和导出验收。"""
        try:
            _, text = _read(target, local, instance)
            index = cptmodel.DocumentIndex(text)
            if sheet is not None or block is not None:
                index.select(sheet, block)
            cptmodel.assert_valid(index)
            output_data({"status": "ok", "action": "validate", **index.report()}, fmt)
        except Exception as exc:
            error(exc)

    @group.command("refs")
    @_options()
    @click.option("--at", help="A1 格号；同时查询该格发出和接收的引用")
    def refs(target, local, sheet, block, at, fmt, instance):
        """列出公式、父格与各公式载体的引用和被引用关系。"""
        try:
            _, text = _read(target, local, instance)
            output_data({"status": "ok", "action": "refs",
                         **cptmodel.DocumentIndex(text).references(sheet, block, at)}, fmt)
        except Exception as exc:
            error(exc)

    def axis_command(axis):
        @_options(write=True)
        @click.option("--delete", multiple=True, help="源坐标下的范围；可重复，例如 3:5 或 C:E")
        @click.option("--insert-before", help="在源坐标前插入，例如 3 或 C")
        @click.option("--count", default=1, type=click.IntRange(1, 100000), show_default=True)
        @click.option("--at", help="设置尺寸/隐藏的行列范围")
        @click.option("--height" if axis == "row" else "--width", "size", type=float,
                      help="行高（磅）" if axis == "row" else "列宽（字符）")
        @click.option("--hide", is_flag=True, help="将 --at 范围的尺寸设置为 0，不删除数据")
        def command(target, local, instance, sheet, block, apply, any_path, output, fmt,
                    delete, insert_before, count, at, size, hide):
            if hide and size is not None:
                error(click.UsageError("--hide 与尺寸选项不能同时给"))
            _perform(target, local, instance, sheet, block, apply, any_path, output, fmt,
                     cpttransform.plan_axis, axis=axis, delete=delete, insert_before=insert_before,
                     count=count, at=at, size=size, hide=hide)
        command.__doc__ = "删除/插入" + ("行" if axis == "row" else "列") + "并联动引用；默认预览，冲突阻止写入。"
        group.command(axis)(command)

    axis_command("row")
    axis_command("column")

    @group.command("range")
    @_options(write=True)
    @click.option("--at", required=True, help="源区域，例如 A1:C5")
    @click.option("--copy-to", help="复制目标左上角")
    @click.option("--move-to", help="移动目标左上角，同时更新外部引用")
    @click.option("--clear", is_flag=True, help="清空内容，保留坐标、样式、合并和扩展")
    @click.option("--merge", is_flag=True, help="合并；其他非空格会阻止合并")
    @click.option("--unmerge", is_flag=True, help="拆分完整包含的合并区域")
    @click.option("--style", type=click.IntRange(min=0), help="区域样式索引")
    def range_command(target, local, instance, sheet, block, apply, any_path, output, fmt,
                      at, copy_to, move_to, clear, merge, unmerge, style):
        """区域复制/移动/清空/合并/拆分/样式；不支持的结构明确报错。"""
        _perform(target, local, instance, sheet, block, apply, any_path, output, fmt,
                 cpttransform.plan_range, at=at, copy_to=copy_to, move_to=move_to,
                 clear=clear, merge=merge, unmerge=unmerge, style=style)
