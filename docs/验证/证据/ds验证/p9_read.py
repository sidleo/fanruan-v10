"""P9 读法实验：同一份模板字节，两种读法在三个时间点各测 3 次。

读法①「模板坐标」= openpyxl ws['C4']（合计行**写**在模板的第 4 行）
读法②「按内容」  = 找首列 == '合计' 的那一行
版面：表头第 2 行 / 数据第 3 行(纵向扩展 3 行) / 合计第 4 行 → 渲染后数据占 3~5 行、合计落第 6 行。
"""
import json, os, subprocess, sys, csv as csvmod, pathlib, time
import openpyxl

ROOT = "~/yh_user/Project/fanruan_v10"
D = "demo_group/demo_user/skill测试"
PY = os.path.expanduser("<venv>/bin/python")
ENV = {**os.environ, "PYTHONPATH": "src", "FRCLI_TIMEOUT": "300", "FRCLI_WRITE_SCOPE": D}
OUT = pathlib.Path("/tmp/dsv")


def frcli(*a, check=True):
    p = subprocess.run([PY, "-m", "frcli", *a], cwd=ROOT, env=ENV, capture_output=True, text=True, timeout=900)
    if check and p.returncode:
        raise RuntimeError(p.stdout[-500:] + p.stderr[-500:])
    return p


def measure(tag, remote, reps=3):
    out = []
    for i in range(reps):
        x = OUT / f"p9_{tag}_{i}.xlsx"; c = OUT / f"p9_{tag}_{i}.csv"
        r1 = frcli("export", "excel", remote, "-o", str(x), check=False)
        frcli("export", "csv", remote, "-o", str(c), check=False)
        row = {"tag": tag, "xlsx_rc": r1.returncode}
        try:
            ws = openpyxl.load_workbook(x).active
            row["ws_C4(模板坐标)"] = ws["C4"].value
            row["ws_C6"] = ws["C6"].value
            grid = [[cc.value for cc in r] for r in ws.iter_rows()]
            row["合计行"] = next((r for r in grid if r and str(r[0]).strip() == "合计"), None)
        except Exception as e:
            row["xlsx_err"] = str(e)[:80]
        try:
            with open(c, encoding="utf-8", errors="replace") as f:
                cr = [r for r in csvmod.reader(f) if any(v.strip() for v in r)]
            row["csv_合计行"] = next((r for r in cr if r and r[0].strip() == "合计"), None)
        except Exception as e:
            row["csv_err"] = str(e)[:80]
        out.append(row)
    return out


remote = f"{D}/dsv_p9read.cpt"
frcli("report", "upload", "/tmp/dsv/o_none.cpt", remote, "--force")
res = []
res += measure("T0-刚上传", remote)
print(json.dumps(res, ensure_ascii=False, indent=1))
# T1: 做若干 report cell 编辑（复刻旧证据里 T2「做过若干 report cell 编辑后」）
frcli("report", "cell", remote, "--at", "A3", "--bold", "--apply")
frcli("report", "cell", remote, "--at", "B3", "--num-format", "#,##0.00", "--apply")
frcli("report", "cell", remote, "--at", "C3", "--align", "right", "--apply")
res += measure("T1-编辑后", remote)
print(json.dumps(res[-1:], ensure_ascii=False, indent=1))
OUT.joinpath("p9read.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
