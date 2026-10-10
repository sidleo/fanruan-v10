"""`report authed` 空结果提示：stdout 不得被污染（离线回归，零网络）。

背景（2026-10 真实会话）：`report authed` 的帮助写「当前账号有权限的模板树」，但该端点
`GET /decision/v10/report/templates/all/authentication` 在本平台恒返回空数组，同账号
`report list /` 现场能取到**数千条**模板（量级随环境增长，别写死数字）⇒ agent 读完 `[]`
会误判成「这个账号没有权限」，进而绕路或放弃。

修法（task-26）：帮助/文档不再把它说成「授权清单」，并在**空结果**时往 stderr 打提示；
**stdout 保持合法 JSON** —— 下游 `frcli report authed | jq '.[0].path'` /
`json.loads($(...))` 必须照旧能跑。

本文件守的是**对外可观察**的契约，不绑实现细节（不关心提示由哪一行代码打印）：

1. 空结果：stdout 去掉首尾空白后**严格等于 `[]`**，提示绝不能混进 stdout；
2. 空结果：stderr 至少一行提示，且同时点到「没拿到数据」与「不是授权判定」；
3. 空结果：提示**不含**真实报表路径/账号等环境事实（本仓库可能公开）；
4. 非空结果：stderr **为空**（不得无差别打提示，否则提示退化成人人忽略的噪音）；
5. 帮助：**短帮助**（agent 真正会读的那一行）不得再自称授权清单；长帮助必须**明确否认**
   该误解并指出替代命令 `report list`——**允许**在否认句里出现旧措辞，禁止的是把它当事实陈述；
6. `-f table` 的表头标题同样不得自称「有权限的模板」（误导文案在输出层也存在）。

不联网：`get_client` 被换成假客户端，`get_authenticated_templates` 直接返回构造值 ——
本文件既不碰配置（`~/.frcli/`）也不发请求。
"""

import json
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from frcli.commands import report as report_cmd                 # noqa: E402

#: 旧帮助文案 —— 会被读成「本账号的授权清单」，是本次修正要清掉的误导表述。
#: 注意：**允许**它在「否认句」里出现（`**不是**「当前账号有权限的模板树」`）——
#: 明确指出误解比不提更有效，所以断言只禁止它作为**命令自身的描述**出现。
MISLEADING_PHRASE = "有权限的模板树"

#: 明确否认标记：帮助里必须至少有一处「否认」，否则等于换个说法继续误导。
NEGATIONS = ("不是", "不代表", "并非", "无关", "≠")

#: 提示必须同时覆盖两层意思，缺一层都拦不住误判：
#:   ① 没拿到数据（空/无/未返回…）  ② 这不是「有没有权限」的判定（路由/端点/接口/授权…）
EMPTY_WORDS = ("空", "无数据", "没有数据", "未返回", "不返回", "返回空", "0 条", "零条")
VERDICT_WORDS = ("权限", "授权", "路由", "端点", "接口", "认证")

#: 环境事实黑名单（提示是静态文案，不该带出任何具体环境/路径/账号）。
ENV_FACT_PATTERNS = ("://", ".cpt", "demo_group", "@", "C:\\", "/Users/", "/home/")

#: 假客户端返回的样本：脱敏占位符（仓库可能公开，不放真实报表名/路径）。
SAMPLE = [
    {"name": "placeholder_a.cpt", "path": "demo_group/demo_user/placeholder_a.cpt",
     "is_directory": False, "type": "cpt"},
    {"name": "placeholder_b.cpt", "path": "demo_group/demo_user/placeholder_b.cpt",
     "is_directory": False, "type": "cpt"},
]


class _FakeClient:
    """只实现 `authed` 这一跳需要的接口；不发任何请求。"""

    def __init__(self, data):
        self._data = data
        self.entered = 0

    def __enter__(self):
        self.entered += 1
        return self

    def __exit__(self, *exc):
        return False

    def get_authenticated_templates(self, keyword=None):
        return self._data


def _run(monkeypatch, data, argv=None):
    """跑 `report authed`，返回 (result, fake_client)。不联网、不读配置。"""
    fake = _FakeClient(data)
    monkeypatch.setattr(report_cmd, "get_client", lambda instance=None: fake)
    res = CliRunner().invoke(report_cmd.report_group, argv or ["authed"])
    return res, fake


def _nonempty_lines(text):
    return [ln for ln in text.splitlines() if ln.strip()]


# ---------------------------------------------------------------- 空结果：stdout 纯净

@pytest.mark.parametrize("fmt,expected_stdout", [("json", "[]"), ("table", "(空)")])
def test_empty_stdout_is_unchanged_by_the_hint(monkeypatch, fmt, expected_stdout):
    """提示只能走 stderr —— stdout 的既有形态逐字节不变（json 就是 `[]`）。"""
    res, fake = _run(monkeypatch, [], ["authed", "-f", fmt])

    assert res.exit_code == 0, res.output
    assert fake.entered == 1, "命令应只进出客户端一次"

    assert res.stdout.strip() == expected_stdout, (
        f"-f {fmt} 的 stdout 被污染（提示必须走 stderr）：{res.stdout!r}"
    )


def test_empty_json_stdout_survives_pipeline_parsing(monkeypatch):
    """管道回归：`report authed | jq` / `json.loads(...)` 照旧能解析。"""
    res, _ = _run(monkeypatch, [])

    assert json.loads(res.stdout) == [], "stdout 必须仍是合法 JSON 空数组"
    assert json.loads(res.stdout) == json.loads("[]")


# ---------------------------------------------------------------- 空结果：stderr 提示

def test_empty_result_hints_on_stderr(monkeypatch):
    """空结果必须给提示：否则唯一可见信号是 `[]`，agent 只能读成「无权限」。"""
    res, _ = _run(monkeypatch, [])

    assert res.exit_code == 0, res.output
    err = res.stderr
    assert err.strip(), (
        "空结果时 stderr 为空 ⇒ agent 会把 [] 误判成「本账号无权限」（这正是 task-26 要修的形态）"
    )
    assert any(w in err for w in EMPTY_WORDS), (
        f"提示没点明「没拿到数据」：{err!r}"
    )
    assert any(w in err for w in VERDICT_WORDS), (
        f"提示没点明「这不是授权判定」，仍拦不住误读：{err!r}"
    )


def test_empty_hint_is_one_line_and_desensitized(monkeypatch):
    """提示是**一行**静态文案，且不得带出任何具体环境事实（仓库可能公开）。"""
    res, _ = _run(monkeypatch, [])
    lines = _nonempty_lines(res.stderr)

    assert len(lines) == 1, f"空结果提示应为一行，实际 {len(lines)} 行：{res.stderr!r}"
    for pat in ENV_FACT_PATTERNS:
        assert pat not in res.stderr, (
            f"提示里出现了环境事实 {pat!r}（未脱敏）：{res.stderr!r}"
        )


# ---------------------------------------------------------------- 非空：不打提示

@pytest.mark.parametrize("argv", [["authed"], ["authed", "--keyword", "placeholder"]])
def test_nonempty_result_prints_no_hint(monkeypatch, argv):
    """有数据时 stderr 必须干净 —— 提示若天天出现就退化成噪音，没人会读。"""
    res, _ = _run(monkeypatch, SAMPLE, argv)

    assert res.exit_code == 0, res.output
    assert json.loads(res.stdout) == SAMPLE
    assert res.stderr == "", f"非空结果不得打提示，实际 stderr：{res.stderr!r}"


def test_nonempty_table_result_prints_no_hint(monkeypatch):
    """table 形态有数据时同样不打提示（提示只在空结果出现）。"""
    res, _ = _run(monkeypatch, SAMPLE, ["authed", "-f", "table"])

    assert res.exit_code == 0, res.output
    assert res.stdout.strip(), "table 形态应正常渲染出表格"
    assert res.stderr == "", f"非空结果不得打提示，实际 stderr：{res.stderr!r}"


def test_table_header_does_not_claim_authorized_tree(monkeypatch):
    """`-f table` 的表头标题同样不得自称「有权限的模板」。

    误导文案不只出现在帮助里：`-f table` 的标题原为「有权限的模板」，agent 读表格时
    同样会把它当成授权清单。**注意**：本条锁的是 task-26 已接受的标题改名
    （`有权限的模板` → `模板认证路由返回`，JSON 输出无 title 字段、结构未变）；
    若裁决为「越界、需回退」，应同步放开本条，并重新评估 req.4 在输出层是否仍成立。
    """
    res, _ = _run(monkeypatch, SAMPLE, ["authed", "-f", "table"])

    assert res.exit_code == 0, res.output
    assert "有权限的模板" not in res.stdout, (
        f"table 标题仍自称授权清单：{res.stdout!r}"
    )
    assert "模板认证" in res.stdout, f"table 标题应点明是认证配置路由：{res.stdout!r}"


# ---------------------------------------------------------------- 帮助文案不再误导

def test_short_help_no_longer_claims_authorized_tree():
    """命令自身的**一句话描述**不得再是「当前账号有权限的模板树」。

    agent 读 `--help` 的决定性一行就是这行短帮助（`Usage:` 下面第一段）；
    它若仍写成授权清单，全文再否认也会被这行盖过去。
    """
    cmd = report_cmd.report_group.commands["authed"]
    short = cmd.get_short_help_str()

    assert short.strip(), "短帮助不能为空"
    assert MISLEADING_PHRASE not in short, (
        f"命令短帮助仍在自称 {MISLEADING_PHRASE!r}：{short!r}"
    )


def test_help_explicitly_denies_the_misconception():
    """`--help` 必须**明确否认**「这是权限树」，并指出正确的替代命令。

    只说「读认证配置路由」不够 —— agent 看不出「所以它不能用来判断我有哪些报表」。
    """
    res = CliRunner().invoke(report_cmd.report_group, ["authed", "--help"])
    assert res.exit_code == 0, res.output
    text = res.stdout

    assert any(neg in text for neg in NEGATIONS), (
        f"帮助没有任何否认表述，误解没被点破：{text!r}"
    )
    assert "权限" in text, f"帮助没提「权限」，无法澄清 `[]` 与权限无关：{text!r}"
    assert "report list" in text, (
        f"帮助没给出替代命令（枚举有权限报表用 `report list`）：{text!r}"
    )
