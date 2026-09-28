"""学自另一会话（2026-09）的三条：启动器递归 / cwd / sheet 能力。"""
from __future__ import annotations

import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent


# ① 启动器不能把 cwd 改到 skill 源码目录（否则用户相对路径参数全部落错地方）
@pytest.mark.parametrize("f", ["references/frcli", "references/run.py"])
def test_launcher_does_not_change_cwd(f):
    src = (ROOT / f).read_text(encoding="utf-8")
    assert "cwd=str(SRC_DIR)" not in src, \
        f"{f} 又改成 cwd=SRC_DIR 了：用户 `-o out.xlsx` 会被写到 skill 源码目录"


# ② run.py 必须有递归护栏（PATH 里的 frcli 若指回 run.py，会无限自我复制）
def test_runpy_has_recursion_guard():
    src = (ROOT / "references" / "run.py").read_text(encoding="utf-8")
    assert "FRCLI_RUNPY_DEPTH" in src, "缺少递归环境标记"
    assert "realpath(__file__) == real" in src, "缺少自指检测"
    assert "_MAX_DEPTH" in src, "缺少深度上限"


# ③ sheet 增删改（离线）
def _tpl():
    from frcli import cptxml
    return ('<WorkBook><StyleList/>'
            '<Report class="com.fr.report.worksheet.WorkSheet" name="sheet1">'
            '<ColumnWidth defaultValue="2743200"><![CDATA[2743200,5486400]]></ColumnWidth>'
            '<CellElementList><C c="0" r="0"><O><![CDATA[x]]></O><Expand/></C>'
            '</CellElementList></Report></WorkBook>')


def test_add_sheet_clones_layout_and_clears_cells():
    from frcli import cptxml
    t = _tpl()
    t2, name = cptxml.add_sheet(t, "口径说明")
    assert name == "口径说明"
    assert cptxml.sheet_names(t2) == ["sheet1", "口径说明"]
    # 新 sheet 要保留版面（列宽），但单元格清空
    new_block = t2.split('name="口径说明"')[1]
    assert "ColumnWidth" in new_block, "新 sheet 应克隆原版面（纸张/列宽）"
    assert new_block.count("<C ") == 0, "新 sheet 的单元格必须清空"


def test_add_sheet_rejects_duplicate_and_keeps_last_sheet():
    from frcli import cptxml
    from frcli.exceptions import ApiError
    t = _tpl()
    with pytest.raises(ApiError):
        cptxml.add_sheet(t, "sheet1")                 # 重名
    with pytest.raises(ApiError):
        cptxml.remove_sheet(t, "sheet1")              # 不能删最后一张
    t2, _ = cptxml.add_sheet(t, "s2")
    assert cptxml.sheet_names(cptxml.remove_sheet(t2, "s2")) == ["sheet1"]
    assert cptxml.sheet_names(cptxml.rename_sheet(t2, "s2", "s3")) == ["sheet1", "s3"]


def test_plan_sheet_list_is_readonly():
    from frcli import reportops
    t = _tpl()
    out, ch = reportops.plan_sheet(t, "list")
    assert out == t and ch[0]["kind"] == "sheet.list" and ch[0]["sheets"] == ["sheet1"]
