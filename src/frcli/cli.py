"""frcli CLI 主入口"""

import click
from . import __version__
from .commands.server import server_group
from .commands.export import export_group
from .commands.schedule import schedule_group
from .commands.report import report_group
from .commands.attach import attach_group
from .commands.system import system_group
from .commands.entry import entry_group
from .commands.user import user_group


@click.group()
@click.version_option(version=__version__, prog_name="frcli")
@click.option("-i", "--instance", help="指定 FineReport 实例 (覆盖默认实例)")
@click.option("-v", "--verbose", is_flag=True, help="详细输出")
@click.pass_context
def main(ctx, instance, verbose):
    """frcli - FineReport CLI 工具

    让 agent 通过命令行与 FineReport 服务器交互。

    示例:
      frcli server list
      frcli export pdf //doc//report.cpt -o report.pdf
      frcli query run //doc//data.cpt --params '{"region":"华东"}'
      frcli report list /doc/
    """
    ctx.ensure_object(dict)
    ctx.obj["instance"] = instance
    ctx.obj["verbose"] = verbose


# 注册命令组
main.add_command(server_group)
main.add_command(export_group)
main.add_command(schedule_group)
main.add_command(report_group)
main.add_command(attach_group)
main.add_command(system_group)
main.add_command(entry_group)
main.add_command(user_group)


if __name__ == "__main__":
    main()
