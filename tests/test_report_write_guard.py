"""模板写命令的写范围守门（回归：`report edit --apply` 曾直接写进生产模板）。

语义（0.6.0 起，**fail-closed**）：没设 `$FRCLI_WRITE_SCOPE` 就直接拒绝，`--any-path`
才放行 —— 沉默不代表可以随便写。2026-09 实测踩过：没设范围时 `report edit --apply`
把 `demo_group/other_user/legacy_rpt.cpt` 写掉了（靠 `upload_template` 的自动备份逐字节还原）。

历史沿革（避免以后有人"修回去"）：最初实现是「env 未设 = 不限制」；出事后先改成
「命令层兜底成团队测试目录」；最终定为 fail-closed —— 把某个人的目录焊进产品默认值
同样是错的，正确做法是让「写到哪」永远是一次显式决定。
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from frcli.commands.report import assert_write_scope                 # noqa: E402
from frcli.exceptions import ApiError                                # noqa: E402

TEAM_DIR = "reportlets/demo_group/demo_user/skill测试"


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("FRCLI_WRITE_SCOPE", raising=False)
    monkeypatch.delenv("FRCLI_ALLOW_ANY_PATH", raising=False)


def test_no_scope_no_flag_is_rejected():
    """最重要的一条：什么都没设时必须拒绝，而不是放行。"""
    for path in (TEAM_DIR, TEAM_DIR + "/x.cpt", "报表目录/别人的报表.cpt"):
        with pytest.raises(ApiError) as ei:
            assert_write_scope(path)
        assert "未指定范围" in str(ei.value)


def test_any_path_flag_allows(monkeypatch):
    assert assert_write_scope("报表目录/别人的报表.cpt", any_path=True) == "报表目录/别人的报表.cpt"
    assert os.environ.get("FRCLI_ALLOW_ANY_PATH") == "1"


@pytest.mark.parametrize("path", [
    TEAM_DIR,
    TEAM_DIR + "/x.cpt",
    TEAM_DIR + "/子目录/x.cpt",
    "demo_group/demo_user/skill测试/x.cpt",          # 展示路径口径也会被归一化
])
def test_in_scope_allowed_when_scoped(monkeypatch, path):
    monkeypatch.setenv("FRCLI_WRITE_SCOPE", TEAM_DIR)
    assert assert_write_scope(path) == path


@pytest.mark.parametrize("path", [
    "报表目录/别人的报表.cpt",
    "demo_group/other_user/legacy_rpt.cpt",                  # 现实名案例
    "reportlets/demo_group/other_user/legacy_rpt.cpt",
    "reportlets/demo_group/demo_user/skill测试_evil/x.cpt",
    "reportlets/demo_group/demo_user/skill测试/../../other_user/x.cpt",
    "reportlets/demo_group/demo_user/skill测试.tmp",
    "reportlets",
])
def test_out_of_scope_rejected(monkeypatch, path):
    monkeypatch.setenv("FRCLI_WRITE_SCOPE", TEAM_DIR)
    with pytest.raises(ApiError):
        assert_write_scope(path)


def test_env_var_scope_is_honoured(monkeypatch):
    monkeypatch.setenv("FRCLI_WRITE_SCOPE", "reportlets/另一个目录")
    assert_write_scope("reportlets/另一个目录/a.cpt")
    with pytest.raises(ApiError):
        assert_write_scope(TEAM_DIR + "/a.cpt")


def test_error_message_tells_how_to_override():
    with pytest.raises(ApiError) as ei:
        assert_write_scope("platform/别的目录/a.cpt")
    msg = str(ei.value)
    assert "FRCLI_WRITE_SCOPE" in msg and "--any-path" in msg


# ---------------------------------------------------------------------------
# 三条写入口都要接上 --any-path（回归：只有 upload/delete 接过，edit 漏了）
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("cmd", ["upload", "delete", "edit"])
def test_write_commands_expose_any_path(cmd):
    from frcli.cli import main
    names = {p.name for p in main.commands["report"].commands[cmd].params}
    assert "any_path" in names or "any-path" in names


def test_report_edit_apply_is_refused_without_scope(monkeypatch):
    """CLI 层：没范围、没 --any-path 时 `report edit --apply` 必须拒绝，
    且拒绝发生在读配置/联网之前（这里故意不配任何实例）。"""
    from click.testing import CliRunner
    from frcli.cli import main
    monkeypatch.delenv("FRCLI_WRITE_SCOPE", raising=False)
    monkeypatch.delenv("FRCLI_ALLOW_ANY_PATH", raising=False)
    monkeypatch.setenv("FRCLI_CONFIG", "/nonexistent/frcli-config.yaml")
    res = CliRunner().invoke(main, [
        "report", "edit", "demo_group/other_user/legacy_rpt.cpt",
        "--dataset", "xs", "--replace", "'a'='b'", "--apply"])
    assert res.exit_code == 1, res.output
    assert "未指定范围" in res.output or "已拒绝" in res.output
    assert "FRCLI_WRITE_SCOPE" in res.output or "--any-path" in res.output


@pytest.mark.parametrize("cmd", ["rpc"])
def test_rpc_group_exposes_any_path(cmd):
    """`rpc call` 也是写入口，必须和 report 三条一样有 --any-path
    （否则 fail-closed 的提示语会指一个不存在的选项）。"""
    from frcli.cli import main
    names = {p.name for p in main.commands[cmd].commands["call"].params}
    assert "any_path" in names or "any-path" in names


def test_rpc_check_write_scope_any_path(monkeypatch):
    """--any-path 只放行本次调用，不改全局语义。"""
    from frcli import rpc as R
    monkeypatch.delenv("FRCLI_WRITE_SCOPE", raising=False)
    monkeypatch.delenv("FRCLI_ALLOW_ANY_PATH", raising=False)
    spec = ("com.fr.workspace.resource.WorkResource", "write")
    with pytest.raises(ApiError):
        R.check_write_scope(*spec, ["reportlets/别的目录/a.cpt", b"x"])
    R.check_write_scope(*spec, ["reportlets/别的目录/a.cpt", b"x"], any_path=True)
