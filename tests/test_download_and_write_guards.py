"""本轮对抗验证固化的回归测试（全部离线，不联网）。

覆盖三块此前**实测踩到过**的坑，每块都对应一条真实故障：

1. `report download` 必须走远程设计通道取**模板原始字节**。
   历史故障：它和 `report datasets` 共用
   `GET /decision/view/report?format=cpt`，而该端点返回的是
   `<TableDataMap>`（数据集定义提取物，缺 `<WorkBook>`/`<StyleList>`）。
   照 SKILL.md 的 `download → 改 → upload --force` 做，会把 6KB stub 写回生产模板，
   而 CLI 回读 SHA256 一致 → `verified: true` **假阳性**，静默毁报表。

2. `assert_template_bytes` 的判据边界（前 600 字节含 `<WorkBook`）。

3. 写沙箱 `FRCLI_WRITE_SCOPE` 与 `normalize_report_path` 的路径归一语义。
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from frcli import remotedesign as rd                                    # noqa: E402
from frcli.client import FineReportClient                               # noqa: E402
from frcli.exceptions import ApiError, ReportNotFoundError              # noqa: E402
from frcli.models import ServerConfig                                   # noqa: E402
from frcli.remotedesign import (                                        # noqa: E402
    assert_in_write_scope,
    assert_template_bytes,
    normalize_report_path,
    WRITE_SCOPE_ENV,
)

WORKBOOK = (b'<?xml version="1.0" encoding="UTF-8"?>\n'
            b'<WorkBook xmlVersion="20211223" releaseVersion="10.0.0">\n'
            b'<TableDataMap/></WorkBook>')
FORMAT_CPT_STUB = (b'<?xml version="1.0" encoding="UTF-8"?>\n'
                   b'<TableDataMap xmlVersion="20211223" releaseVersion="10.0.0">\n'
                   b'<TableData name="x" class="com.fr.data.impl.DBTableData"/></TableDataMap>')


def _cfg() -> ServerConfig:
    return ServerConfig(name="t", url="https://example.invalid", username="u", password="p")


# ---------------------------------------------------------------------------
# 1) download 契约：只走通道，绝不碰 format=cpt
# ---------------------------------------------------------------------------
class _FakeSession:
    """替掉 RemoteDesignSession：记录读了哪个路径，返回预置字节。"""

    payload = WORKBOOK
    seen = []

    def __init__(self, config, client_id=None):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def close(self):
        pass

    def check(self):
        return {"transmissionEncryption": 2}

    def read(self, path):
        type(self).seen.append(path)
        return type(self).payload


@pytest.fixture
def no_rest(monkeypatch):
    """任何 REST 调用都视为失败 —— download 不该再用 format=cpt。"""
    def boom(self, *a, **k):
        raise AssertionError("download_report 不该发 REST 请求（尤其不能再用 format=cpt）")
    monkeypatch.setattr(FineReportClient, "_get", boom)
    monkeypatch.setattr(FineReportClient, "_request", boom)
    monkeypatch.setattr(FineReportClient, "_ensure_auth", lambda self: None)


def test_download_uses_channel_and_writes_exact_bytes(monkeypatch, tmp_path, no_rest):
    _FakeSession.seen = []
    monkeypatch.setattr(rd, "RemoteDesignSession", _FakeSession)

    out = tmp_path / "a.cpt"
    got = FineReportClient(_cfg()).download_report("demo_group/demo_user/测试/a.cpt", str(out))

    assert _FakeSession.seen == ["reportlets/demo_group/demo_user/测试/a.cpt"]
    assert Path(got).read_bytes() == WORKBOOK, "落盘字节必须与通道读回的字节逐字节一致"


def test_download_rejects_non_workbook_payload(monkeypatch, tmp_path, no_rest):
    """旧 format=cpt 产物（TableDataMap）必须被拒，绝不落盘。"""
    _FakeSession.payload = FORMAT_CPT_STUB
    monkeypatch.setattr(rd, "RemoteDesignSession", _FakeSession)
    out = tmp_path / "stub.cpt"
    with pytest.raises(ReportNotFoundError) as ei:
        FineReportClient(_cfg()).download_report("a/b.cpt", str(out))
    assert "WorkBook" in str(ei.value)
    assert not out.exists()


def test_download_reports_missing_or_unauthorized(monkeypatch, tmp_path, no_rest):
    """通道对无权限/不存在都返回 0 字节 → 必须报错，不能写出空文件。"""
    _FakeSession.payload = b""
    monkeypatch.setattr(rd, "RemoteDesignSession", _FakeSession)
    out = tmp_path / "empty.cpt"
    with pytest.raises(ReportNotFoundError):
        FineReportClient(_cfg()).download_report("a/b.cpt", str(out))
    assert not out.exists()


def test_datasets_still_reads_format_cpt(monkeypatch):
    """`report datasets` 仍走 format=cpt 解析 TableData —— 两边语义不要搞混。"""
    from frcli.client import FineReportClient as C
    calls = {}

    def fake_get(self, url, **kwargs):
        calls["url"] = url
        calls["params"] = kwargs.get("params")

        class R:
            status_code = 200
            headers = {"content-type": "text/xml;charset=UTF-8"}
            text = ('<TableDataMap><TableData name="ds1" class="x">'
                    '<Parameters><Parameter><Attributes name="sdate"/></Parameter></Parameters>'
                    '<Connection class="com.fr.data.impl.NameDatabaseConnection">'
                    '<DatabaseName><![CDATA[demo_conn]]></DatabaseName></Connection>'
                    '<Query><![CDATA[select 1 from t where d=\'${sdate}\']]></Query>'
                    '</TableData></TableDataMap>')
        return R()

    monkeypatch.setattr(C, "_get", fake_get)
    monkeypatch.setattr(C, "_ensure_auth", lambda self: None)
    data = C(_cfg()).get_report_datasets("a/b.cpt")
    assert calls["params"]["format"] == "cpt", "datasets 的语义就是 format=cpt 的提取物"
    assert data == [{"name": "ds1", "parameters": ["sdate"],
                     "sql": "select 1 from t where d='${sdate}'",
                     "connection": "demo_conn"}]


# ---------------------------------------------------------------------------
# 2) 格式守门判据边界
# ---------------------------------------------------------------------------
def test_guard_boundary_marker_after_600_bytes_is_rejected():
    """判据是「前 600 字节」，更靠后的 <WorkBook 不算数（实测 DESIGNER 模板都在最前面）。"""
    with pytest.raises(ApiError):
        assert_template_bytes(b"A" * 700 + b"<WorkBook>")


def test_guard_is_a_heuristic_not_a_sandbox():
    """已知局限：**良构**但非模板的 XML，只要前 600 字节里有 `<WorkBook` 也会放行。

    守门只防「照文档做错事」，不防「故意构造」。真正的边界是服务端授权目录
    + `FRCLI_WRITE_SCOPE`。

    但**残缺内容**不再是洞：`assert_template_bytes` 现在同时做 XML 良构校验
    （服务端对坏 XML 照收、渲染成空表、回读校验还通过，所以只能在这里拦）。
    """
    assert_template_bytes(b"<!-- <WorkBook --><Foo/>" + b" " * 5000)
    with pytest.raises(ApiError, match="良构 XML"):
        assert_template_bytes(b"<!-- <WorkBook -->" + b"\x00" * 5000)


def test_guard_rejects_empty_and_html():
    for bad in (b"", b"<html><title>err</title></html>"):
        with pytest.raises(ApiError):
            assert_template_bytes(bad)


# ---------------------------------------------------------------------------
# 3) 备份：内容必须等于覆盖前的内容
# ---------------------------------------------------------------------------
def test_save_backup_is_byte_identical(monkeypatch, tmp_path):
    monkeypatch.setattr(rd, "BACKUP_DIR", tmp_path / "backups")
    original = WORKBOOK * 3
    path = rd._save_backup("reportlets/a/b/c.cpt", original)
    assert Path(path).read_bytes() == original
    assert Path(path).parent == tmp_path / "backups"
    # 路径被压平，不会在备份目录里造子目录
    assert "/" not in Path(path).name


def test_save_backup_two_runs_dont_collide(monkeypatch, tmp_path):
    monkeypatch.setattr(rd, "BACKUP_DIR", tmp_path / "backups")
    p1 = rd._save_backup("reportlets/a/c.cpt", b"v1")
    p2 = rd._save_backup("reportlets/a/c.cpt", b"v2")
    assert p1 != p2 or Path(p2).read_bytes() == b"v2"


# ---------------------------------------------------------------------------
# 4) 路径归一 + 写沙箱
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("raw,expected", [
    ("a/b.cpt", "reportlets/a/b.cpt"),
    ("/a/b.cpt", "reportlets/a/b.cpt"),
    ("reportlets/a/b.cpt", "reportlets/a/b.cpt"),
    ("reportletsX/y.cpt", "reportlets/reportletsX/y.cpt"),   # 前缀伪造被消解
    ("", "reportlets/"),
])
def test_normalize_report_path(raw, expected):
    assert normalize_report_path(raw) == expected


def test_normalize_does_not_sanitize_dotdot():
    """CLI 不吞 `..`（归一交给服务端）；实测服务端会拒绝越出根，并在根内不解析 `..`。

    这里固化 CLI 侧语义，避免有人误以为 CLI 已经做过路径消毒。
    """
    assert normalize_report_path("../x.cpt") == "reportlets/../x.cpt"


SCOPE = "demo_group/demo_user/skill测试"


@pytest.mark.parametrize("path", [
    f"{SCOPE}/a.cpt",
    f"reportlets/{SCOPE}/sub/b.cpt",
    f"/{SCOPE}/a.cpt",
    f"{SCOPE}/./a.cpt",
])
def test_write_scope_allows_inside(monkeypatch, path):
    monkeypatch.setenv(WRITE_SCOPE_ENV, SCOPE)
    assert_in_write_scope(path)          # 不抛即通过


@pytest.mark.parametrize("path", [
    "demo_group/demo_user/dept_a/dept_b/sales_daily.cpt",
    f"{SCOPE}/../dept_a/sales_daily.cpt",
    "reportlets/超级管理员/x.cpt",
    f"{SCOPE}2/x.cpt",                   # 前缀相近的兄弟目录
    "reportlets",                        # 工作区根
    "",
])
def test_write_scope_blocks_outside(monkeypatch, path):
    monkeypatch.setenv(WRITE_SCOPE_ENV, SCOPE)
    with pytest.raises(ApiError):
        assert_in_write_scope(path)


def test_write_scope_unset_is_fail_closed(monkeypatch):
    """0.6.0 起：没设范围就直接拒绝（沉默 ≠ 不限制），--any-path 才放行。"""
    monkeypatch.delenv(WRITE_SCOPE_ENV, raising=False)
    monkeypatch.delenv("FRCLI_ALLOW_ANY_PATH", raising=False)
    with pytest.raises(ApiError):
        assert_in_write_scope("随便/哪里.cpt")
    monkeypatch.setenv("FRCLI_ALLOW_ANY_PATH", "1")
    assert_in_write_scope("随便/哪里.cpt")


# ---------------------------------------------------------------------------
# 5) delete 的 --force 必须在网络调用之前
# ---------------------------------------------------------------------------
def test_delete_needs_force_before_any_network(monkeypatch, tmp_path):
    calls = []

    class Boom:
        def __init__(self, *a, **k):
            calls.append("session")

        def __enter__(self):
            return self

        def __exit__(self, *e):
            return False

    monkeypatch.setattr(rd, "RemoteDesignSession", Boom)
    monkeypatch.delenv(WRITE_SCOPE_ENV, raising=False)
    monkeypatch.setenv("FRCLI_ALLOW_ANY_PATH", "1")   # 放行守门，专测 --force 判定
    with pytest.raises(ApiError) as ei:
        rd.delete_template(_cfg(), "a/b.cpt")
    assert "--force" in str(ei.value)
    assert calls == [], "未确认前不该建立任何会话/连接"


# ---------------------------------------------------------------------------
# 6) rpc 写守门：两条入口（report upload/delete 与 rpc call）口径必须一致
# ---------------------------------------------------------------------------
from frcli import rpc as R                                                # noqa: E402

RPC_WRITE = ("com.fr.workspace.resource.WorkResource", "write")


@pytest.mark.parametrize("path,allowed", [
    (f"{SCOPE}/a.cpt", True),
    (f"{SCOPE}/x/y.cpt", True),
    (f"{SCOPE}/a.cpt.tmp", True),          # 域内的 .tmp 仍应放行
    (f"{SCOPE}.tmp", False),               # scope 的**兄弟节点**，剥 .tmp 会误判为域内
    (f"{SCOPE}.tmp/x.cpt", False),
    (f"{SCOPE}x/y.cpt", False),            # 前缀相近但不是子目录
    (f"{SCOPE}/../dept_a/sales_daily.cpt", False),
    ("demo_group/demo_user/dept_a/dept_b/sales_daily.cpt", False),
])
def test_rpc_scope_matches_sandbox(path, allowed, monkeypatch):
    """回归：rpc.in_scope 曾经剥掉 `.tmp` 后缀，使 `<scope>.tmp`（沙箱的兄弟节点）被判为域内。

    修法是不镜像服务端的鉴权剥离 —— 落点判定不能剥。这里同时校验
    `in_scope` 与 `check_write_scope` 两个入口给出同一结论。
    """
    monkeypatch.setenv(WRITE_SCOPE_ENV, R.DEFAULT_WRITE_SCOPE)   # 0.6.0 起未设范围即拒绝
    assert R.in_scope(path, R.DEFAULT_WRITE_SCOPE) is allowed
    try:
        R.check_write_scope(*RPC_WRITE, [path])
        passed = True
    except ApiError:
        passed = False
    assert passed is allowed, path


def test_rpc_write_without_path_arg_is_denied(monkeypatch):
    """写语义方法若没有可检查的路径参数 → 一律拒绝（无法验证范围 = 不放行）。"""
    monkeypatch.delenv(WRITE_SCOPE_ENV, raising=False)
    with pytest.raises(ApiError) as ei:
        R.check_write_scope("com.fr.base.operator.common.CommonOperator", "unlockTemplate", [])
    assert "参数个数" in str(ei.value)


def test_rpc_deny_policy_is_never_allowed():
    """平台配置/权限/密钥类必须在策略层就是 deny（与是否 --yes 无关）。"""
    assert R.method_policy("com.fr.base.rpc.encrypt.EncryptOperator", "readKey") == R.DENY
    # 未列出的方法回落服务级默认值，同样不应意外变成 write/read
    default = R.method_policy("com.fr.base.rpc.encrypt.EncryptOperator", "不存在的离谱方法")
    assert default == R.DENY


# ---------------------------------------------------------------------------
# 7) 导出产物魔数（0.5.1 新增）：出错页 / 排队页 / word=RTF
# ---------------------------------------------------------------------------
from frcli.client import assert_export_magic                            # noqa: E402
from frcli.exceptions import ExportError                                 # noqa: E402

#: 平台限流时返回的排队页（实测 2102B：`title` 为空、**没有** detail-message，
#: 只有 `Dec-Waiting_In_Line` 和一段 5 秒轮询脚本）。§6.1 的旧判据识别不出它。
WAITING_PAGE = (b"<!DOCTYPE html><html><head><meta charset=\"utf-8\">"
                b"<title></title></head><body><span id=\"wait\">"
                b"Dec-Waiting_In_Line</span></body></html>")
ERROR_PAGE = ('<!DOCTYPE html><html><head><title>出错页面</title></head>'
              '<body><div id="detail-message">错误代码:11300001 数据集 [x] 配置错误'
              '</div></body></html>').encode("utf-8")


@pytest.mark.parametrize("payload,fmt,ok", [
    (b"PK\x03\x04\x14\x00\x08\x08", "excel", True),
    (b"%PDF-1.7\n", "pdf", True),
    (b"\x89PNG\r\n\x1a\n", "image", True),
    (b"{\\rtf1\\ansi\\ansicpg936", "word", True),      # 帆软 format=word 实际出 RTF
    (WAITING_PAGE, "excel", False),                    # 排队页：旧判据漏、魔数能拦
    (ERROR_PAGE, "excel", False),
    (b"{\\rtf1", "excel", False),                      # 格式对不上
])
def test_export_magic_gate(tmp_path, payload, fmt, ok):
    f = tmp_path / "out.bin"
    f.write_bytes(payload)
    if ok:
        assert_export_magic(f, fmt)
    else:
        with pytest.raises(ExportError):
            assert_export_magic(f, fmt)


# --- Lead 补：--allow-format 必须两道关一起跳（否则纯文本文件传不上去）--------
def test_allow_format_skips_both_guards():
    from frcli.remotedesign import assert_template_bytes
    from frcli.exceptions import ApiError
    plain = b"# \xe7\xba\xaf\xe6\x96\x87\xe6\x9c\xac\xe8\xaf\xb4\xe6\x98\x8e\nnot xml at all\n"
    # 默认：非模板内容必须拒绝
    with pytest.raises(ApiError):
        assert_template_bytes(plain)
    # --allow-format：表达"我确知在传什么"，两道关一起跳过
    assert_template_bytes(plain, allow_format=True)


def test_bad_xml_still_blocked_without_allow_format():
    """--allow-format 不能顺带放过残缺 XML：那道关的本职就是拦它。"""
    from frcli.remotedesign import assert_template_bytes
    from frcli.exceptions import ApiError
    with pytest.raises(ApiError) as ei:
        assert_template_bytes(b"<WorkBook><C></WorkBook>")
    assert "良构" in str(ei.value)
