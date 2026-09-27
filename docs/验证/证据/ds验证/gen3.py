"""base3 变体：同数据集（含重复值）/ 同版面 / 只改数据设置 <RG> 与 <Expand>。

数据集 ds4 = ('A',10)('A',10)('A',20)('B',10)('B',30)('B',30)  ← 与 dsauthor 对照件同构，
但本文件是**手写 XML**（不依赖 report table 的默认值）。
"""
import pathlib, re

RG = "com.fr.report.cell.cellattr.core.group."
FN = "com.fr.data.util.function."
BASE = pathlib.Path("/tmp/dsv/base3.cpt")


def o_block(ds, col, kind):
    extra = {
        "none": "",
        "func": f'<RG class="{RG}FunctionGrouper"/>\n',
        "list": f'<RG class="{RG}FunctionGrouper">\n<Attr divideMode="1"/>\n</RG>\n',
        "sum": f'<RG class="{RG}SummaryGrouper">\n<FN>\n<![CDATA[{FN}SumFunction]]></FN>\n</RG>\n',
        "count": f'<RG class="{RG}SummaryGrouper">\n<FN>\n<![CDATA[{FN}CountFunction]]></FN>\n</RG>\n',
    }[kind]
    return (f'<O t="DSColumn">\n<Attributes dsName="{ds}" columnName="{col}"/>\n'
            f'<Complex/>\n{extra}<Parameters/>\n</O>')


EXPANDS = {"v": '<Expand dir="0"/>', "none": "<Expand/>",
           "extonly": '<Expand extendable="1|2|3"/>',
           "extdir": '<Expand dir="0" extendable="1|2|3"/>'}


def build(name, setting, expands):
    d = BASE.read_text(encoding="utf-8")
    for (c, r), kind in setting.items():
        rx = re.compile(rf'<C c="{c}" r="{r}">.*?</C>', re.S)
        m = rx.search(d)
        assert m, (c, r)
        col = {"0": "k", "1": "amt"}[str(c)]
        blk = m.group(0)
        blk = re.sub(r'<O t="DSColumn">.*?</O>', lambda _: o_block("ds4", col, kind), blk, flags=re.S)
        blk = re.sub(r'<Expand[^>]*/>', expands[str(c)], blk)
        d = d[:m.start()] + blk + d[m.end():]
    p = pathlib.Path("/tmp/dsv") / f"{name}.cpt"
    p.write_text(d, encoding="utf-8")
    return p


VARIANTS = {
    "b3_none":        ({(0, 2): "none", (1, 2): "none"}, {"0": EXPANDS["v"], "1": EXPANDS["v"]}),
    "b3_func":        ({(0, 2): "func", (1, 2): "func"}, {"0": EXPANDS["v"], "1": EXPANDS["v"]}),
    "b3_list":        ({(0, 2): "list", (1, 2): "list"}, {"0": EXPANDS["v"], "1": EXPANDS["v"]}),
    "b3_sum":         ({(0, 2): "func", (1, 2): "sum"},  {"0": EXPANDS["v"], "1": EXPANDS["none"]}),
    "b3_expandnone":  ({(0, 2): "list", (1, 2): "list"}, {"0": EXPANDS["none"], "1": EXPANDS["none"]}),
    "b3_extonly":     ({(0, 2): "func", (1, 2): "func"}, {"0": EXPANDS["extonly"], "1": EXPANDS["extonly"]}),
    "b3_extdir":      ({(0, 2): "func", (1, 2): "func"}, {"0": EXPANDS["extdir"], "1": EXPANDS["extdir"]}),
    "b3_sum_count":   ({(0, 2): "count", (1, 2): "sum"}, {"0": EXPANDS["none"], "1": EXPANDS["none"]}),
}

if __name__ == "__main__":
    for n, (s, e) in VARIANTS.items():
        print(build(n, s, e))
