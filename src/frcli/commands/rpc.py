"""frcli rpc 命令组 —— 远程设计 RPC 网关（通用反射调用，受控）。"""

import click

from ..config import load_config
from ..output import output_data, success, error
from .. import rpc as R


@click.group("rpc")
def rpc_group():
    """远程设计 RPC 网关（🟢 只读白名单 / 🔴 写需 --yes）

    决策平台 `/decision/remote/design/channel` 是个通用反射网关：给类名+方法名+
    参数就能在服务端执行。`rpc services` 列可调服务，`rpc methods` 看签名，
    `rpc call` 受控调用（写方法必须 --yes 且路径落在写范围内）。
    """
    pass


@rpc_group.command("services")
@click.option("--local", is_flag=True, help="用随包的离线清单（不联网）")
@click.option("-f", "--format", "fmt", type=click.Choice(["json", "table"]), default="json")
@click.option("-i", "--instance", help="FineReport 实例名")
def services_cmd(local, fmt, instance):
    """列出服务端可调服务（线上 /service；--local 用离线清单）"""
    try:
        if local:
            rows = [{"service": c, "jar": R.SERVICES[c].jar,
                     "methods": len(R.SERVICES[c].methods),
                     "source": "local"} for c in R.service_names()]
            output_data(rows if fmt == "table" else
                        {"source": "local", "count": len(rows), "services": rows},
                        format=fmt, title="RPC 服务（本地清单）")
            return
        config = load_config(instance)
        live = R.live_services(config)
        live_set = set(live)
        rows = [{"service": c, "methods": len(R.SERVICES[c].methods) if c in R.SERVICES else 0,
                 "in_local": c in R.SERVICES, "source": "live"} for c in sorted(live_set)]
        for c in R.service_names():
            if c not in live_set:
                rows.append({"service": c, "methods": len(R.SERVICES[c].methods),
                             "in_local": True, "source": "local-only"})
        data = {"source": "live", "count": len(live), "services": rows}
        if fmt == "table":
            output_data(rows, format="table", title=f"RPC 服务（线上 {len(live)} 个）")
        else:
            output_data(data, format="json")
    except Exception as e:
        error(e)


@rpc_group.command("methods")
@click.argument("service")
@click.option("--keyword", help="按方法名过滤")
@click.option("-f", "--format", "fmt", type=click.Choice(["json", "table"]), default="json")
def methods_cmd(service, keyword, fmt):
    """列出某服务的全部方法签名（本地反解清单，不联网）"""
    try:
        full = R.resolve_service(service)
        svc = R.get_service(full)
        rows = []
        for m in svc.methods:
            if keyword and keyword not in m.name:
                continue
            rows.append({
                "method": m.name,
                "returns": m.returns,
                "params": ", ".join(m.params),
                "signature": R.format_signature(m),
                "sig": R.signature_id(m),
                "policy": R.method_policy(full, m.name),
            })
        if fmt == "table":
            output_data([{"policy": r["policy"], "signature": r["signature"]} for r in rows],
                        format="table", title=f"{full}（{len(rows)} 个方法）")
        else:
            output_data({"service": full, "kind": svc.kind, "jar": svc.jar,
                         "count": len(rows), "methods": rows}, format="json")
    except Exception as e:
        error(e)


@rpc_group.command("call")
@click.argument("service")
@click.argument("method")
@click.option("--arg", "args", multiple=True,
              help="参数：`VALUE`（按签名推断类型）或 `TYPE=VALUE`；byte[] 传本地文件路径")
@click.option("--sig", help="重载消歧：逗号分隔的参数类型，如 java.lang.String,int")
@click.option("--out", type=click.Path(dir_okay=False, writable=True),
              help="字节结果（byte[]）落盘路径；不给则只回大小/摘要")
@click.option("--yes", is_flag=True, help="🔴 确认执行写语义方法（且路径必须在写范围内）")
@click.option("--any-path", is_flag=True,
              help="🔴 确认写这个目标而不限范围（本次调用生效；没有它就必须先设 "
                   "$FRCLI_WRITE_SCOPE，否则拒绝）")
@click.option("-f", "--format", "fmt", type=click.Choice(["json", "table"]), default="json")
@click.option("-i", "--instance", help="FineReport 实例名")
def call_cmd(service, method, args, sig, out, yes, any_path, fmt, instance):
    """受控调用一个服务端方法

    默认只放行**只读白名单**（`rpc methods` 的 policy 列）。写方法必须 `--yes`，
    且每个路径参数都要落在写范围内（`FRCLI_WRITE_SCOPE`，默认团队测试目录）。
    返回 byte[] 的方法（导出/出图）用 `--out` 落盘，否则只能看到大小。
    """
    try:
        full = R.resolve_service(service)
        m = R.resolve_method(full, method, sig, arity=len(args))
        policy = R.method_policy(full, m.name)
        if policy == R.DENY:
            from ..exceptions import ApiError
            raise ApiError(
                f"{full}.{m.name} 属平台配置/权限/密钥类写操作，"
                "本工具在任何情况下都不放行（只读查询请换其他方法）")
        pairs = R.prepared_args(m, list(args))
        if policy == R.WRITE:
            if not yes:
                from ..exceptions import ApiError
                raise ApiError(
                    f"{full}.{m.name} 是写语义方法，确认执行请加 --yes，"
                    "并先限定写范围：export FRCLI_WRITE_SCOPE=\"<目录>\"；"
                    "确实要写这个目标就 export FRCLI_ALLOW_ANY_PATH=1（本次调用生效）")
            R.check_write_scope(full, m.name, [v for _t, v in pairs], any_path)
        config = load_config(instance)
        res = R.invoke(config, full, m, pairs)
        call_info = {"service": full, "method": m.name,
                     "signature": R.format_signature(m), "policy": policy}
        if res.exception:
            from ..exceptions import ApiError
            hint = R.rpc_error_hint(full, m, str(res.exception))
            raise ApiError(f"RPC 调用失败: {res.exception}" + (f"\n提示: {hint}" if hint else ""))
        hint = R.path_hint(full, pairs)

        # byte[] 结果：落盘才拿得到本体（否则只有大小）
        blob = R.raw_bytes(res.value)
        if blob is not None:
            info = {"call": call_info, "result_type": "byte[]", "size": len(blob)}
            if out:
                info.update(R.describe_bytes(blob, _write_bytes(out, blob)))
            else:
                info["hint"] = "这是字节结果，加 --out <文件> 才能落盘拿到本体"
            if hint:
                info["hint"] = (info.get("hint", "") + " " + hint).strip()
            success(info)
            return

        value, kind = R.decode_result(res.value)
        if fmt == "table" and isinstance(value, list):
            output_data([v if isinstance(v, dict) else {"value": v} for v in value],
                        format="table", title=f"{m.name}{R.format_params(m)}")
            return
        payload = {"call": call_info, "result_type": kind, "result": value}
        if hint:
            payload["hint"] = hint
        success(payload)
    except Exception as e:
        error(e)


def _write_bytes(path: str, data: bytes) -> str:
    from pathlib import Path
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    return str(p)
