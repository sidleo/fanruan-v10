"""通用数据设置补丁器：给定 base.cpt 与 {列名: 数据设置} 生成变体。

只替换数据单元格的 <O> 块，其余字节完全不动。
"""
import pathlib

RG = "com.fr.report.cell.cellattr.core.group."
FN = "com.fr.data.util.function."
LIST_COND = '<Condition class="com.fr.data.condition.ListCondition"/>\n'


def o_block(ds, col, kind, order=None):
    extra = {
        # 数据设置 → XML 片段
        "none": "",
        "list": f'<RG class="{RG}FunctionGrouper">\n<Attr divideMode="1"/>\n</RG>\n',
        "func": f'<RG class="{RG}FunctionGrouper"/>\n',
        "mono": f'<RG class="{RG}MonoGrouper"/>\n',
        "sum": f'<RG class="{RG}SummaryGrouper">\n<FN>\n<![CDATA[{FN}SumFunction]]></FN>\n</RG>\n',
        "count": f'<RG class="{RG}SummaryGrouper">\n<FN>\n<![CDATA[{FN}CountFunction]]></FN>\n</RG>\n',
        "avg": f'<RG class="{RG}SummaryGrouper">\n<FN>\n<![CDATA[{FN}AverageFunction]]></FN>\n</RG>\n',
        "condonly": LIST_COND,
        "condfunc": LIST_COND + f'<RG class="{RG}FunctionGrouper"/>\n',
        "badfn": f'<RG class="{RG}SummaryGrouper">\n<FN>\n<![CDATA[{FN}NotAFunction]]></FN>\n</RG>\n',
        "badrg": f'<RG class="{RG}ListGrouper"/>\n',
        "legacy": '<RG class="com.fr.report.cellElement.core.FunctionGrouper"/>\n',
        "empty_rg": '<RG/>\n',
    }[kind]
    return (f'<O t="DSColumn">\n<Attributes dsName="{ds}" columnName="{col}"/>\n'
            f'<Complex/>\n{extra}'
            '<Result>\n<![CDATA[$$$]]></Result>\n<Parameters/>\n</O>')


def patch(base, ds, setting, out):
    import re
    d = pathlib.Path(base).read_text(encoding="utf-8")
    for col, kind in setting.items():
        rx = re.compile(
            r'<O t="DSColumn">\n<Attributes dsName="' + re.escape(ds) +
            r'" columnName="' + re.escape(col) + r'"/>.*?</O>', re.S)
        hits = rx.findall(d)
        assert len(hits) == 1, (base, col, len(hits))
        d = rx.sub(lambda m: o_block(ds, col, kind), d, count=1)
    p = pathlib.Path(out)
    p.write_text(d, encoding="utf-8")
    return p


# ---- 语义对照（base2: k 为分组键(有重复), amt 为数值）----
SEM = {
    "s_list":  {"k": "list", "amt": "list"},
    "s_group": {"k": "func", "amt": "sum"},
    "s_sum":   {"k": "count", "amt": "sum"},
    "s_none":  {"k": "none", "amt": "none"},
}
# ---- 叶列重复值塌缩（dup: amt 有重复 100,100,300）----
DUP = {
    "d_none": {"k": "none", "n": "none", "amt": "none"},
    "d_list": {"k": "list", "n": "list", "amt": "list"},
}
# ---- 对抗（base: 三列全同一种写法）----
ADV = {
    "a_badfn":    {"k": "badfn", "n": "badfn", "amt": "badfn"},
    "a_badrg":    {"k": "badrg", "n": "badrg", "amt": "badrg"},
    "a_legacy":   {"k": "legacy", "n": "legacy", "amt": "legacy"},
    "a_condonly": {"k": "condonly", "n": "condonly", "amt": "condonly"},
    "a_condfunc": {"k": "condfunc", "n": "condfunc", "amt": "condfunc"},
    "a_mono":     {"k": "mono", "n": "mono", "amt": "mono"},
    "a_sum":      {"k": "sum", "n": "sum", "amt": "sum"},
    "a_avg":      {"k": "avg", "n": "avg", "amt": "avg"},
}

GROUPS = [
    ("/tmp/dsv/base2.cpt", "ds2", SEM, "/tmp/dsv/"),
    ("/tmp/dsv/dup.cpt", "ds3", DUP, "/tmp/dsv/"),
    ("/tmp/dsv/base.cpt", "ds1", ADV, "/tmp/dsv/"),
]

if __name__ == "__main__":
    for base, ds, table, out in GROUPS:
        for name, setting in table.items():
            p = patch(base, ds, setting, out + name + ".cpt")
            print(f"{p}  {len(p.read_text(encoding='utf-8'))}")
