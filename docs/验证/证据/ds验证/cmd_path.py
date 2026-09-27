"""命令路径端到端：report new/dataset/table/cell --mode … → 导出 xlsx+csv → 逐格读回。"""
import json, os, subprocess, sys, csv as csvmod, pathlib
import openpyxl

ROOT = "~/yh_user/Project/fanruan_v10"
D = "demo_group/demo_user/skill测试"
PY = os.path.expanduser("<venv>/bin/python")
ENV = {**os.environ, "PYTHONPATH": "src", "FRCLI_TIMEOUT": "300", "FRCLI_WRITE_SCOPE": D}
SQL = ("select 'A' k,10 amt union all select 'A',10 union all select 'A',20 "
       "union all select 'B',10 union all select 'B',30 union all select 'B',30")


def frcli(*a, check=True):
    p = subprocess.run([PY, "-m", "frcli", *a], cwd=ROOT, env=ENV, capture_output=True,
                       text=True, timeout=900)
    if check and p.returncode:
        return {"_rc": p.returncode, "_out": p.stdout[-300:], "_err": p.stderr[-300:]}
    try:
        return json.loads(p.stdout)
    except Exception:
        return {"_raw": p.stdout[-200:]}


def build(name, mode_args):
    r = f"{D}/{name}.cpt"
    frcli("report", "new", r, "--apply")
    frcli("report", "dataset", r, "--add", "ds5", "--conn", "demo_conn",
          "--sql", SQL, "--apply")
    frcli("report", "table", r, "--dataset", "ds5", "--at", "A2", "--columns", "k,amt",
          "--header", "--labels", "键,金额", *mode_args, "--apply")
    frcli("report", "cell", r, "--at", "A4", "--set-value", "合计", "--apply")
    frcli("report", "cell", r, "--at", "B4", "--set-formula", "=SUM(B3)", "--apply")
    return r


def read(r, tag):
    x = pathlib.Path(f"/tmp/dsv/cmd_{tag}.xlsx"); c = pathlib.Path(f"/tmp/dsv/cmd_{tag}.csv")
    frcli("export", "excel", r, "-o", str(x))
    frcli("export", "csv", r, "-o", str(c))
    ws = openpyxl.load_workbook(x).active
    grid = [[v for v in row] for row in
            ([cc.value for cc in rr] for rr in ws.iter_rows()) if any(v is not None for v in row)]
    with open(c) as f:
        cg = [row for row in csvmod.reader(f) if any(v.strip() for v in row)]
    return {"dims": ws.dimensions, "xlsx": grid, "csv": cg}


out = {}
for name, args in [("dsv/cmd_list", []),
                   ("dsv/cmd_group", ["--mode", "group"]),
                   ("dsv/cmd_summary", ["--mode", "summary", "--group-by", "k", "--fn", "sum"])]:
    tag = name.split("/")[1]
    r = build(name, args)
    out[tag] = read(r, tag)
    print("=" * 70)
    print("###", tag, "args:", args)
    print("   dims:", out[tag]["dims"])
    for row in out[tag]["xlsx"]:
        print("   X", row)
    for row in out[tag]["csv"]:
        print("   C", row)

# 命令路径语义校验（dry-run，无写操作）
print("=" * 70)
checks = {
    "--fn 配 list": ["report", "cell", f"{D}/dsv/cmd_list.cpt", "--at", "B3",
                     "--set-ds-mode", "list", "--fn", "sum"],
    "--fn 配 group": ["report", "table", f"{D}/dsv/cmd_list.cpt", "--dataset", "ds5",
                      "--at", "A2", "--columns", "k,amt", "--mode", "group", "--fn", "sum"],
    "--group-by 配 list": ["report", "table", f"{D}/dsv/cmd_list.cpt", "--dataset", "ds5",
                           "--at", "A2", "--columns", "k,amt", "--mode", "list",
                           "--group-by", "k"],
    "--fn bogus": ["report", "table", f"{D}/dsv/cmd_list.cpt", "--dataset", "ds5",
                   "--at", "A2", "--columns", "k,amt", "--mode", "summary",
                   "--group-by", "k", "--fn", "bogus"],
    "group-by 覆盖全部列": ["report", "table", f"{D}/dsv/cmd_list.cpt", "--dataset", "ds5",
                            "--at", "A2", "--columns", "k,amt", "--mode", "summary",
                            "--group-by", "k,amt"],
    "group-by 不在 columns": ["report", "table", f"{D}/dsv/cmd_list.cpt", "--dataset", "ds5",
                              "--at", "A2", "--columns", "k,amt", "--mode", "summary",
                              "--group-by", "nope"],
}
for label, args in checks.items():
    p = subprocess.run([PY, "-m", "frcli", *args], cwd=ROOT, env=ENV,
                       capture_output=True, text=True, timeout=120)
    msg = ""
    try:
        msg = json.loads(p.stdout)["error"]["message"]
    except Exception:
        msg = (p.stdout + p.stderr).strip().splitlines()[-1][:160]
    print(f"  [{label}] exit={p.returncode} -> {msg[:150]}")

pathlib.Path("/tmp/dsv/cmdpath.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
