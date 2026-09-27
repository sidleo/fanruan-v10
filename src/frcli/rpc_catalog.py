"""反解实测环境 FineReport 安装包里的远程设计服务签名 → 生成 `rpc_services.py`。

`/decision/remote/design/service` 只给出**类名清单**（28 个），方法签名得从服务端
对应的 jar 里取。服务端不可达（或只想本地查）时用这份离线清单，所以生成的
`src/frcli/rpc_services.py` 是随包分发的数据模块。

用法（换 FineReport 版本后重新生成）：

    FINEREPORT_HOME=<FineReport 安装目录> python -m frcli.rpc_catalog
    # 或指定服务清单文件（/service 的返回值，JSON 数组）
    python -m frcli.rpc_catalog --services live.json --home <FineReport 安装目录>

签名以 `javap -p` 为准，逐行解析（`parse_javap` 是纯函数，有离线回归测试）。
"""

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path

#: jar 搜索优先级：服务端运行时的 jar 优先于 Designer 侧
JAR_SEARCH_ORDER = (
    "webapps/webroot/WEB-INF/lib/",
    "webapps/webroot/WEB-INF/plugins/",
    "webapps/webroot/WEB-INF/classes/",
    "server/lib/",
    "plugins/",
    "lib/",
)

#: javap 里的修饰符（解析签名时要剥掉）
MODIFIERS = frozenset({
    "public", "protected", "private", "abstract", "static", "final", "default",
    "synchronized", "native", "strictfp", "transient", "volatile",
})

#: 修饰符 → 单字母标记，存进清单（a=abstract d=default s=static）
FLAG_LETTERS = {"abstract": "a", "default": "d", "static": "s"}

_JAVA_KEYWORDS = ("class", "interface", "enum")


def split_top_level(text: str, sep: str = ","):
    """按顶层分隔符切分（跳过 `<>` 与 `[]` 里的分隔符）。"""
    out, buf, depth = [], [], 0
    for ch in text:
        if ch in "<([":
            depth += 1
        elif ch in ">)]":
            depth -= 1
        if ch == sep and depth == 0:
            out.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    tail = "".join(buf).strip()
    if tail:
        out.append(tail)
    return out


def strip_type_params(prefix: str) -> str:
    """去掉泛型方法的 `<T extends X>` 前缀声明。"""
    p = prefix.strip()
    if not p.startswith("<"):
        return p
    depth = 0
    for i, ch in enumerate(p):
        if ch == "<":
            depth += 1
        elif ch == ">":
            depth -= 1
            if depth == 0:
                return p[i + 1:].strip()
    return p


def strip_modifiers(prefix: str):
    """从 `public abstract byte[]` 剥出 (modifiers, 返回类型)。"""
    mods, rest = [], prefix.strip()
    while True:
        m = re.match(r"^([a-z]+)\s+", rest)
        if not m or m.group(1) not in MODIFIERS:
            break
        mods.append(m.group(1))
        rest = rest[m.end():]
    return mods, rest.strip()


def parse_javap(text: str) -> dict:
    """解析 `javap -p` 输出 → {kind, name, methods, fields}。"""
    kind, name = None, None
    methods, fields = [], []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("Compiled from") or line.startswith("[STDERR]"):
            continue
        if line in ("{", "}"):
            continue
        if line.startswith(("static {};", "static {}")):
            continue
        if kind is None:
            m = re.match(r"^(?:public\s+|final\s+|abstract\s+)*"
                         r"(class|interface|enum)\s+([\w.$]+)", line)
            if m:
                kind, name = m.group(1), m.group(2)
                continue
        decl = line.rstrip(";").strip()
        if "(" in decl:
            methods.append(_parse_method(decl))
        else:
            fields.append(_parse_field(decl))
    return {"kind": kind, "name": name, "methods": methods, "fields": fields}


def _parse_method(decl: str) -> dict:
    head, _, tail = decl.partition("(")
    name = head.split()[-1] if head.split() else head
    prefix = head[:len(head) - len(name)]
    # javap 的写法是 `public abstract <T extends X> ReturnType name(...)`：
    # 先剥修饰符，再剥类型参数声明，剩下才是返回类型
    mods, rest = strip_modifiers(prefix)
    rest = strip_type_params(rest)
    mods2, returns = strip_modifiers(rest)
    mods += mods2
    params_text, throws = tail, []
    if ")" in tail:
        params_text, _, rest = tail.rpartition(")")
        if "throws" in rest:
            throws = [split_top_level(x)[0].strip()
                      for x in split_top_level(rest.split("throws", 1)[1])]
    params = [p for p in split_top_level(params_text) if p]
    params = [re.sub(r"\s*<.*>$", "", p) for p in params]   # 泛型擦除到 raw 类型
    flags = "".join(FLAG_LETTERS[m] for m in mods if m in FLAG_LETTERS)
    return {"name": name, "returns": returns or "void", "params": params,
            "throws": throws, "flags": flags}


def _parse_field(decl: str) -> dict:
    mods, rest = strip_modifiers(decl)
    m = re.match(r"^(.*?)\s+([\w$]+)$", rest)
    return {"name": m.group(2) if m else rest, "type": m.group(1) if m else rest,
            "modifiers": mods}


def discover_jars(home: Path):
    """按 JAR_SEARCH_ORDER 排序实测环境所有候选 jar（跳过备份目录）。"""
    jars = []
    for root, dirs, files in os.walk(home):
        if "backup" in root or "designerbackup" in root:
            continue
        for f in files:
            if f.endswith(".jar"):
                jars.append(Path(root) / f)
    order = {p: i for i, p in enumerate(JAR_SEARCH_ORDER)}

    def key(p: Path):
        rel = p.relative_to(home).as_posix()
        rank = len(JAR_SEARCH_ORDER)
        for pref, idx in order.items():
            if rel.startswith(pref):
                rank = idx
                break
        return (rank, rel)

    return sorted(set(jars), key=key)


def locate_class(class_name: str, jars):
    """找出承载某个类的 jar（按搜索顺序返回第一个命中的）。"""
    entry = class_name.replace(".", "/") + ".class"
    for jar in jars:
        try:
            with zipfile.ZipFile(jar) as z:
                if entry in z.namelist():
                    return jar
        except (zipfile.BadZipFile, OSError):
            continue
    return None


def javap_signatures(class_name: str, classpath: str) -> str:
    proc = subprocess.run(["javap", "-p", "-cp", classpath, class_name],
                          capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"javap 失败: {class_name}: {proc.stderr.strip()[:200]}")
    return proc.stdout


def build_catalog(services, home: Path, jars=None):
    jars = jars if jars is not None else discover_jars(home)
    cp = os.pathsep.join(str(j) for j in jars)
    catalog = {}
    for cls in services:
        jar = locate_class(cls, jars)
        if jar is None:
            catalog[cls] = {"jar": None, "kind": None, "methods": []}
            continue
        parsed = parse_javap(javap_signatures(cls, cp))
        catalog[cls] = {
            "jar": jar.relative_to(home).as_posix(),
            "kind": parsed["kind"],
            "methods": parsed["methods"],
        }
    return catalog


# ---------------------------------------------------------------------------
# 生成 rpc_services.py（保证每行 ≤ 100 列，flake8 干净）
# ---------------------------------------------------------------------------
def _wrap_items(items, indent: str, limit: int = 100):
    """把若干短串贪心铺成多行，每行不超过 limit 列。"""
    lines, cur = [], indent
    for i, it in enumerate(items):
        piece = it + ("," if i < len(items) - 1 else "")
        if cur != indent and len(cur) + 1 + len(piece) > limit:
            lines.append(cur)
            cur = indent + piece
        else:
            cur += (" " if cur != indent else "") + piece
    if cur != indent:
        lines.append(cur)
    return lines


def _render_tuple(items, indent: str, limit: int = 100):
    """渲染一个元组字面量；太长就逐元素换行。"""
    flat = "(" + ", ".join(items) + ("," if items else "") + ")"
    if len(indent) + len(flat) <= limit:
        return [indent + flat]
    return [indent + "("] + _wrap_items(items, indent + " " * 4, limit) + [indent + ")"]


def _fmt_method(m: dict, indent: str) -> str:
    name, ret, flags = repr(m["name"]), repr(m["returns"]), repr(m["flags"])
    params = [repr(p) for p in m["params"]]
    flat = "(" + ", ".join(params) + ("," if params else "") + ")"
    one = f"{indent}M({name}, {ret}, {flat}, {flags}),"
    if len(one) <= 100:
        return one
    arg_indent = indent + " " * 4
    body = _render_tuple(params, arg_indent, limit=99)   # 留 1 列给行尾逗号
    body[-1] += ","
    lines = [indent + "M(", arg_indent + name + ",", arg_indent + ret + ","]
    lines += body
    lines += [arg_indent + flags + ",", indent + "),"]
    return "\n".join(lines)


def _fmt_str(value: str, indent: str, limit: int = 100) -> str:
    """渲染字符串字面量；过长时用隐式拼接换行。"""
    one = f"{indent}{value!r},"
    if len(one) <= limit:
        return one
    room = limit - len(indent) - 2       # 首尾引号
    chunks = [value[i:i + room] for i in range(0, len(value), room)]
    out = [f"{indent}{chunks[0]!r}"]
    for c in chunks[1:]:
        out.append(f"{indent}{c!r}")
    out[-1] += ","
    return "\n".join(out)


def emit_module(catalog: dict, home: Path) -> str:
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    out = [
        '"""远程设计 RPC 服务签名清单（**由 `python -m frcli.rpc_catalog` 生成，勿手改**）。',
        "",
        f"来源：`{home}` 的 jar（javap -p），生成时间 {stamp}。",
        "服务类清单来自 `/decision/remote/design/service`；签名为该版本 jar 的反解结果。",
        '"""',
        "",
        "from typing import NamedTuple",
        "",
        "",
        f"GENERATED_AT = {stamp!r}",
        f"SOURCE_HOME = {str(home)!r}",
        "",
        "",
        "class M(NamedTuple):",
        '    """一个方法：名字 / 返回类型 / 参数类型 / 标记(a=abstract d=default s=static)。"""',
        "",
        "    name: str",
        "    returns: str",
        "    params: tuple",
        "    flags: str",
        "",
        "",
        "class Service(NamedTuple):",
        "    jar: str",
        "    kind: str",
        "    methods: tuple",
        "",
        "",
        "SERVICES = {",
    ]
    for cls in sorted(catalog):
        info = catalog[cls]
        out.append(f"    {cls!r}: Service(")
        out.append(_fmt_str(info["jar"] or "", " " * 8))
        out.append(f"        {info['kind']!r},")
        if not info["methods"]:
            out.append("        (),")
        else:
            out.append("        (")
            for m in info["methods"]:
                out.append(_fmt_method(m, " " * 12))
            out.append("        ),")
        out.append("    ),")
    out += ["}", ""]
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description="反解远程设计服务签名，生成 rpc_services.py")
    ap.add_argument("--home",
                    default=os.environ.get("FINEREPORT_HOME", ""),
                    help="FineReport 安装目录（取 $FINEREPORT_HOME；未设则必填）")
    ap.add_argument("--services", help="服务类清单 JSON（/service 的返回值）；缺省用内置清单")
    ap.add_argument("-o", "--output", help="输出文件；缺省覆盖 src/frcli/rpc_services.py")
    args = ap.parse_args(argv)

    home = Path(args.home)
    if not home.is_dir():
        print(f"找不到 FineReport 安装目录: {home}", file=sys.stderr)
        return 2
    if args.services:
        services = json.loads(Path(args.services).read_text(encoding="utf-8"))
        if isinstance(services, dict):
            services = services.get("data", services)
    else:
        services = list(DEFAULT_SERVICES)

    catalog = build_catalog(services, home)
    # 护栏：空清单/全无方法时**拒绝覆盖**。2026-09 实测踩过 —— 不设 --home 直接跑，
    # 会把 rpc_services.py 覆盖成「28 个服务、0 个方法」的残版（生成器不该能悄悄把产物清空）。
    total_methods = sum(len(v["methods"]) for v in catalog.values())
    if not catalog or total_methods == 0:
        print(f"❌ 生成的清单是空的（服务 {len(catalog)} 个、方法 {total_methods} 个），"
              f"已拒绝覆盖 {args.output or 'src/frcli/rpc_services.py'}。\n"
              f"   多半是 --home / $FINEREPORT_HOME 没指向真正的安装目录（当前: {home}）。",
              file=sys.stderr)
        return 3
    text = emit_module(catalog, home)
    target = Path(args.output) if args.output else Path(__file__).with_name("rpc_services.py")
    target.write_text(text, encoding="utf-8")
    missing = [c for c, v in catalog.items() if not v["jar"]]
    print(f"已写入 {target}：{len(catalog)} 个服务，"
          f"{sum(len(v['methods']) for v in catalog.values())} 个方法")
    if missing:
        print(f"⚠️ 安装包内的 jar 未找到这些类（清单里标 jar=null）: {missing}", file=sys.stderr)
    return 0


#: 线上 `/decision/remote/design/service` 实测返回的 28 个服务类
DEFAULT_SERVICES = (
    "com.fr.analysis.cloud.solid.SolidRecordExecutor",
    "com.fr.base.io.FileAssistUtilsOperator",
    "com.fr.base.operator.common.CommonOperator",
    "com.fr.base.operator.org.OrganizationOperator",
    "com.fr.base.rpc.encrypt.EncryptOperator",
    "com.fr.cluster.engine.rpc.remote.ClusterOperator",
    "com.fr.config.dao.CommitHelper",
    "com.fr.config.dao.DataFetcher",
    "com.fr.data.operator.DataOperatorProvider",
    "com.fr.esd.core.remote.ESDConfigEventOperator",
    "com.fr.file.filetree.FileNodes",
    "com.fr.form.share.ShareComponentOperator",
    "com.fr.form.share.ShareEmbeddedConverter",
    "com.fr.plugin.cloud.analytics.collect.rpc.RPCDataCollector",
    "com.fr.plugin.weixin.server.rpc.WeiXinRPCOperator",
    "com.fr.security.encryption.storage.StorageTransfer",
    "com.fr.workspace.engine.client.heartbeart.WorkspaceHeartbeat",
    "com.fr.workspace.resource.WorkResource",
    "com.fr.workspace.server.authority.AuthorityOperator",
    "com.fr.workspace.server.authority.decision.DecisionOperator",
    "com.fr.workspace.server.check.TemplateChecker",
    "com.fr.workspace.server.check.VersionInfoOperator",
    "com.fr.workspace.server.connection.DBConnectAuth",
    "com.fr.workspace.server.exporter.TemplateExportOperator",
    "com.fr.workspace.server.lock.TplOperator",
    "com.fr.workspace.server.lock.editlock.EditLockOperator",
    "com.fr.workspace.server.socket.SocketInfoOperator",
    "com.fr.workspace.server.vcs.VcsOperator",
)


if __name__ == "__main__":
    sys.exit(main())
