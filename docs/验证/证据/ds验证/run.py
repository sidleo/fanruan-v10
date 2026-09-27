"""数据设置对照矩阵：每个变体 → 上传 → 导 xlsx + csv（各 3 轮）→ 逐格读回。

只做写操作于 $FRCLI_WRITE_SCOPE 内的测试目录；本地语料只读。
用法: PYTHONPATH=src <venv>/bin/python /tmp/dsv/run.py [kind...]
"""
import json, os, subprocess, sys, csv as csvmod, pathlib, time
import openpyxl

ROOT = "<本项目目录>"
D = "demo_group/demo_user/skill测试"
PY = os.path.expanduser("<venv>/bin/python")
ENV = {**os.environ, "PYTHONPATH": "src", "FRCLI_TIMEOUT": "300",
       "FRCLI_WRITE_SCOPE": D}
OUT = pathlib.Path("/tmp/dsv")


def frcli(*args, check=True):
    p = subprocess.run([PY, "-m", "frcli", *args], cwd=ROOT, env=ENV,
                       capture_output=True, text=True, timeout=900)
    if check and p.returncode != 0:
        raise RuntimeError(f"frcli {' '.join(args)} -> {p.returncode}\n{p.stdout[-800:]}\n{p.stderr[-800:]}")
    return p


def jout(p):
    try:
        return json.loads(p.stdout)
    except Exception:
        return {"_raw": p.stdout[-400:], "_err": p.stderr[-400:]}


def read_xlsx(path):
    ws = openpyxl.load_workbook(path).active
    rows = [[c.value for c in r] for r in ws.iter_rows()]
    return {"dims": ws.dimensions,
            "rows": [[v for v in r] for r in rows if any(v is not None for v in r)]}


def read_csv(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        return [r for r in csvmod.reader(f) if any(x.strip() for x in r)]


def total_of(grid):
    """找 '合计' 那一行的第 3 列；没有就 None。"""
    for r in grid:
        if r and str(r[0]).strip() == "合计":
            return r[2] if len(r) > 2 else None
    return None


def export(fmt, remote, out, tries=3):
    """导出并读回；302/排队页等瞬态失败重试，最终失败时留下 CLI 原文。"""
    last = None
    for t in range(tries):
        p = frcli("export", fmt, remote, "-o", str(out), check=False)
        msg = ""
        try:
            j = json.loads(p.stdout)
            msg = j.get("error", {}).get("message", "") if isinstance(j.get("error"), dict) else ""
        except Exception:
            msg = p.stdout[-200:]
        last = (p.returncode, msg, out.exists())
        if p.returncode == 0 and out.exists():
            return last
        time.sleep(2)
    return last


def run(kind, reps=3):
    local = OUT / f"{kind}.cpt"
    remote = f"{D}/dsv_{kind}.cpt"
    rec = {"kind": kind}
    p = frcli("report", "upload", str(local), remote, "--force")
    rec["upload"] = jout(p).get("verified", jout(p).get("status"))
    rec["reps"] = []
    for i in range(reps):
        x = OUT / f"{kind}.{i}.xlsx"; c = OUT / f"{kind}.{i}.csv"
        rc1, msg1, _ = export("excel", remote, x)
        rc2, msg2, _ = export("csv", remote, c)
        e = {"xlsx_rc": rc1, "csv_rc": rc2, "xlsx_msg": msg1, "csv_msg": msg2}
        try:
            xg = read_xlsx(x); e["xlsx_dims"] = xg["dims"]; e["xlsx"] = xg["rows"]
            e["xlsx_total"] = total_of(xg["rows"])
        except Exception as ex:
            e["xlsx_err"] = str(ex)[:200]
        try:
            cg = read_csv(c); e["csv"] = cg; e["csv_total"] = total_of(cg)
        except Exception as ex:
            e["csv_err"] = str(ex)[:200]
        rec["reps"].append(e)
    return rec


if __name__ == "__main__":
    kinds = sys.argv[1:] or ["none", "func", "list", "mono", "sum"]
    res = [run(k) for k in kinds]
    (OUT / os.environ.get("DSV_JSON", "matrix.json")).write_text(json.dumps(res, ensure_ascii=False, indent=1))
    for r in res:
        print("=" * 70)
        print(f"### {r['kind']}  upload={r['upload']}")
        for i, e in enumerate(r["reps"]):
            print(f"  rep{i}: xlsx_dims={e.get('xlsx_dims')} xlsx_total={e.get('xlsx_total')} "
                  f"csv_total={e.get('csv_total')} rc={e['xlsx_rc']}/{e['csv_rc']}")
            for row in e.get("xlsx", []):
                print("     X", row)
            if i == 0:
                for row in e.get("csv", []):
                    print("     C", row)
