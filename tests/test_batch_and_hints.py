"""学自 2026-09 两个会话：批量参数矩阵 / 超时提示 / 版本提示噪音。"""
from __future__ import annotations

import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent


def test_batch_manifest_expands_param_matrix(tmp_path):
    """manifest 里 params 给列表 → 逐值各导一份，output 的 {参数名} 换成该值。"""
    src = (ROOT / "src" / "frcli" / "commands" / "export.py").read_text(encoding="utf-8")
    assert "itertools.product" in src, "缺少参数矩阵展开"
    assert 'output.replace("{" + k + "}", str(v))' in src, "缺少 {参数名} 占位替换"


def test_net_hint_mentions_timeout_env():
    """连接/超时失败要告诉用户「调大 FRCLI_TIMEOUT」，别让人反复怀疑报表。"""
    from frcli.client import _net_hint
    import httpx
    msg = _net_hint(httpx.ReadTimeout("The read operation timed out"))
    assert "FRCLI_TIMEOUT" in msg and "timed out" in msg
    # 非超时也要给可操作建议
    assert "FRCLI_TIMEOUT" in _net_hint(httpx.ConnectError("boom"))


def test_version_hint_compares_version_not_path():
    """版本提示按**版本号**比对。

    同机常有多份 skill 副本（项目仓库 + ~/.agents/skills 安装态），路径必然不同、
    版本相同 —— 早期按路径比对导致每条命令都打两行提示（实测污染几十条输出）。
    """
    src = (ROOT / "references" / "run.py").read_text(encoding="utf-8")
    assert "_version_of" in src, "缺少版本读取"
    assert "是另一个版本" in src, "提示应按版本差异触发"
    assert "当前 PATH 中的 frcli 来自" not in src, "旧的高噪音提示应已移除"
