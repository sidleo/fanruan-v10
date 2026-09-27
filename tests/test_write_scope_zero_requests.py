"""写范围守门的**端到端零请求**回归（cpt-verifier 验证轮新增）。

与 `tests/test_report_write_guard.py` 的分工：
  * 那边测的是判定函数 `assert_write_scope()` 本身（单元级）；
  * 这里测的是**整条命令路径**：范围外的目标必须在**任何网络请求发出之前**就被拒，
    且范围**内**的目标必须真的走到网络层（否则说明哨兵接错了缝，测试会假绿）。

⚠️ 接缝选哪个（实测踩过，写在这里防止后人重踩）：
  `report upload/delete/edit --apply` 走的是 `remotedesign.RemoteDesignClient`，
  它**自带一个 `httpx.Client`**，与 `FineReportClient._request`（REST 通道）是两条路。
  只 patch `FineReportClient._request` 会漏掉远程设计通道 —— 表现为「范围内」用例
  静默通过、却真的把模板写到了服务器上。必须 patch `httpx.Client.request` 才能覆盖两条通道。
"""

import sys
from pathlib import Path

import httpx
import pytest
from click.testing import CliRunner

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from frcli.cli import main                                          # noqa: E402

SCOPE = "demo_group/demo_user/skill测试"

#: 真实事故目标 + 各种"看起来像域内"的绕过写法
OUT_OF_SCOPE = [
    "demo_group/other_user/legacy_rpt.cpt",
    "demo_group/demo_user/skill测试_evil/x.cpt",           # 兄弟目录
    "demo_group/demo_user/skill测试x/x.cpt",               # 前缀兄弟
    "demo_group/demo_user/skill测试/../other_user/x.cpt",       # 穿越
    "reportlets/demo_group/demo_user/skill测试/../../other_user/x.cpt",
]


@pytest.fixture
def sentinel(monkeypatch):
    """把 http 层换成记录器：任何真实请求都会记录并让用例失败。"""
    calls = []

    def fake_request(self, method, url, *a, **kw):
        calls.append((method, str(url)))
        raise AssertionError(f"哨兵拦截：不该发出的请求 {method} {url}")

    monkeypatch.setattr(httpx.Client, "request", fake_request)
    return calls


def _invoke(args, env=None):
    import os
    for k in ("FRCLI_WRITE_SCOPE", "FRCLI_ALLOW_ANY_PATH"):
        os.environ.pop(k, None)
    return CliRunner().invoke(main, args, env={"FRCLI_TIMEOUT": "5", **(env or {})})


@pytest.mark.parametrize("target", OUT_OF_SCOPE)
@pytest.mark.parametrize("argv", [
    ["report", "upload", "x.cpt", "{t}"],
    ["report", "delete", "{t}", "--force"],
    ["report", "edit", "{t}", "--dataset", "ds1", "--sql", "select 1", "--apply"],
])
def test_out_of_scope_never_touches_network(sentinel, argv, target, tmp_path):
    """没设范围时，范围外目标必须本地拒绝且**零请求**（fail-closed）。"""
    local = tmp_path / "x.cpt"
    local.write_bytes(b"<WorkBook/>")
    args = [a.replace("{t}", target) for a in argv]
    args = [str(local) if a == "x.cpt" else a for a in args]
    res = _invoke(args)
    assert res.exit_code != 0
    assert sentinel == [], f"拒绝之前发了请求：{sentinel}"
    assert "未指定范围" in res.output


@pytest.mark.parametrize("target", OUT_OF_SCOPE)
def test_scoped_run_still_blocks_outside(sentinel, target, tmp_path):
    local = tmp_path / "x.cpt"
    local.write_bytes(b"<WorkBook/>")
    res = _invoke(["report", "upload", str(local), target], env={"FRCLI_WRITE_SCOPE": SCOPE})
    assert res.exit_code != 0
    assert sentinel == [], f"拒绝之前发了请求：{sentinel}"
    assert "限制在" in res.output


def test_in_scope_reaches_network(sentinel, tmp_path):
    """范围**内**必须真的走到网络层 —— 这条是哨兵自身的接线自检。

    少了它，「零请求」可能是 patch 接错缝造成的假绿（本文件头注释记的正是这个坑）。
    """
    local = tmp_path / "x.cpt"
    local.write_bytes(b"<WorkBook/>")
    res = _invoke(["report", "upload", str(local), SCOPE + "/x.cpt"],
                  env={"FRCLI_WRITE_SCOPE": SCOPE})
    assert sentinel, "范围内没有发出任何请求：哨兵接缝选错了（应为 httpx.Client.request）"
    assert res.exit_code != 0        # 哨兵抛错，命令在这里被叫停


def test_rpc_write_out_of_scope_is_denied_before_network(sentinel):
    res = _invoke([
        "rpc", "call", "com.fr.workspace.resource.WorkResource", "write",
        "--arg", "reportlets/demo_group/other_user/legacy_rpt.cpt",
        "--arg", "/tmp/x.cpt", "--yes",
    ], env={"FRCLI_WRITE_SCOPE": SCOPE})
    assert res.exit_code != 0
    assert sentinel == []


# ---------------------------------------------------------------------------
# 上传前的内容守门：良构性（cpt-verifier 发现 P1 后新增的第二道门）
#
# 背景（实测）：`<WorkBook>` 前缀检查**挡不住残缺 XML** —— 服务端对坏 XML 照收不误、
# 渲染成空表，而写后 SHA256 回读校验依然 `verified: true`（回读比的是"写进去的字节"，
# 不代表内容能被服务端解析）。所以必须在本地再加一道良构性判定。
# ---------------------------------------------------------------------------

import pytest as _pytest                                            # noqa: E402

from frcli.exceptions import ApiError                               # noqa: E402
from frcli.remotedesign import assert_template_bytes                # noqa: E402


@pytest.mark.parametrize("payload,label", [
    (b"<WorkBook><TableDataMap/></WorkBook>", "正常最小模板"),
    (b"<!-- <WorkBook --><x/>", "注释里带标记但良构"),
])
def test_wellformed_template_bytes_pass(payload, label):
    """良构内容必须放行 —— 防"加了良构门之后误杀正常模板"。"""
    assert_template_bytes(payload)


@pytest.mark.parametrize("payload,label", [
    (b"<WorkBook><CellElementList><C></WorkBook>", "标签不匹配"),
    (b"<WorkBook><O><![CDATA[a]]>b]]></O></WorkBook>", "CDATA 里含 ]]>（= 残缺 XML）"),
    (b"<WorkBook>\x00\x00</WorkBook>", "NUL 字节"),
    (b"<WorkBook>", "未闭合"),
    (b"A" * 700 + b"<WorkBook><x/></WorkBook>", "标记不在前 600 字节"),
])
def test_non_wellformed_template_bytes_rejected(payload, label):
    """残缺内容必须在**本地**被拒（一个字节都不发）。"""
    with _pytest.raises(ApiError):
        assert_template_bytes(payload)
