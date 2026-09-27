"""生成数据设置对照件：从 CLI 造的 base.cpt（残缺形态）出发，只改数据单元格的 <O> 块。

同一数据集 / 同一版面 / 同一合计行，唯一变量 = 数据设置（<Condition>/<RG>）。
"""
import re, pathlib, sys

SRC = pathlib.Path("/tmp/dsv/base.cpt")
OUT = pathlib.Path("/tmp/dsv")
NEW = '<Complex order="0"/>\n'

FN_SUM = "com.fr.data.util.function.SumFunction"
RG = "com.fr.report.cell.cellattr.core.group."

LIST_COND = '<Condition class="com.fr.data.condition.ListCondition"/>\n'


def o_variant(kind, col, name):
    """返回该数据单元格 <O> 块（kind 决定数据设置），其余与 CLI 输出逐字节一致。"""
    head = f'<O t="DSColumn">\n<Attributes dsName="ds1" columnName="{col}"/>\n'
    tail = '<Result>\n<![CDATA[$$$]]></Result>\n</O>'
    mid = '<Complex order="0"/>\n'
    extra = ""
    if kind == "none":            # A 旧形态：无 Condition / 无 RG
        pass
    elif kind == "func":          # B 分组（divideMode 缺省 = 0 = GROUPING_MODE）
        extra = f'<RG class="{RG}FunctionGrouper"/>\n'
    elif kind == "list":          # C 列表（LIST_MODE = 1）
        extra = f'<RG class="{RG}FunctionGrouper">\n<Attr divideMode="1"/>\n</RG>\n'
    elif kind == "mono":          # D MonoGrouper
        extra = f'<RG class="{RG}MonoGrouper"/>\n'
    elif kind == "sum":           # E 汇总 SUM
        extra = f'<RG class="{RG}SummaryGrouper">\n<FN>\n<![CDATA[{FN_SUM}]]></FN>\n</RG>\n'
    elif kind == "cond_only":     # 只有列表过滤条件、仍无 RG
        extra = LIST_COND
    elif kind == "cond_func":     # 列表条件 + 分组（语料里最常见的"分组"写法）
        extra = LIST_COND + f'<RG class="{RG}FunctionGrouper"/>\n'
    elif kind == "badfn":         # 对抗：错的 FN 类名
        extra = (f'<RG class="{RG}SummaryGrouper">\n<FN>\n'
                 f'<![CDATA[com.fr.data.util.function.NotAFunction]]></FN>\n</RG>\n')
    elif kind == "badrg":         # 对抗：不存在的 RG 类名
        extra = f'<RG class="{RG}ListGrouper"/>\n'
    elif kind == "listgroup":     # 对抗：列表 mode + 汇总 FN 冲突
        extra = (f'<RG class="{RG}FunctionGrouper">\n<Attr divideMode="1"/>\n</RG>\n'
                 f'<RG class="{RG}SummaryGrouper">\n<FN>\n<![CDATA[{FN_SUM}]]></FN>\n</RG>\n')
    elif kind == "legacy_func":   # 对抗：旧包名（V10 jar 里已无该类）
        extra = '<RG class="com.fr.report.cellElement.core.FunctionGrouper"/>\n'
    else:
        raise SystemExit(f"unknown kind {kind}")
    return head + mid + extra + tail


def build(kind, cols=("k", "n", "amt")):
    d = SRC.read_text(encoding="utf-8")
    for col in cols:
        old = (f'<O t="DSColumn">\n<Attributes dsName="ds1" columnName="{col}"/>\n'
               '<Complex order="0"/>\n<Result>\n<![CDATA[$$$]]></Result>\n</O>')
        assert d.count(old) == 1, (kind, col, d.count(old))
        d = d.replace(old, o_variant(kind, col, col))
    p = OUT / f"v_{kind}.cpt"
    p.write_text(d, encoding="utf-8")
    return p


if __name__ == "__main__":
    kinds = sys.argv[1:] or ["none", "func", "list", "mono", "sum"]
    for k in kinds:
        print(build(k), len(build(k).read_text(encoding='utf-8')))
