"""远程设计 RPC 网关的受控调用层（`frcli rpc` 的后端）。

`POST /decision/remote/design/channel` 是个**通用反射网关**：给它「类名 + 方法名 +
参数类型」就执行（`WorkspaceServerInvoker` → `Class.forName(...).getDeclaredMethod(...)`
→ 从 `FineObjectPool` 取实例 invoke）。除 token 外**没有逐路径鉴权**，所以安全边界
必须由客户端自己扛：

* `read`  —— 只读白名单，直接放行；
* `write` —— 必须 `--yes`，且**每个路径参数**都要落在写范围内（见 `check_write_scope`）；
* `deny`  —— 平台配置写 / 权限写 / 密钥读取，任何情况下都拒绝。

写范围由 `remotedesign.assert_in_write_scope` 唯一判定，且是 **fail-closed** 的：
设了 `$FRCLI_WRITE_SCOPE` 就只允许落在该目录下；没设则拒绝（`$FRCLI_ALLOW_ANY_PATH`
可显式放行本次调用）。**写方法若没有可编码的路径参数，一律拒绝**（无法验证范围 = 不放行）。
"""

import os
from pathlib import Path

from . import jser
from .rpc_services import SERVICES
from .remotedesign import ALLOW_ANY_ENV, assert_in_write_scope
from .exceptions import ApiError

READ = "read"
WRITE = "write"
DENY = "deny"

#: 团队测试目录（0.6.0 起**不是**「默认写范围」：未设范围一律拒绝，见
#: `remotedesign.assert_in_write_scope`）。这里只作为文档与测试用的基准目录。
DEFAULT_WRITE_SCOPE = "reportlets/demo_group/demo_user/skill测试"

#: 每个服务的默认策略 + 逐方法覆盖。没列出的方法按服务默认值处理。
POLICY = {
    "com.fr.analysis.cloud.solid.SolidRecordExecutor": {
        "*": DENY,
        "getRecordTask": READ,
        "checkRecordTaskExist": READ,
    },
    "com.fr.base.io.FileAssistUtilsOperator": {"*": DENY, "moveToTrash": WRITE},
    "com.fr.base.operator.common.CommonOperator": {
        "*": DENY,
        "getLicenseName": READ, "hasPluginServiceStarted": READ,
        "getSharePath": READ, "getPluginStatus": READ,
        "getDefaultSolutionTip": READ, "getWebRootPath": READ,
        "readPathSvgFiles": READ, "fileLocked": READ, "getAppName": READ,
        "getContextName": READ, "getDesignerVersion": READ, "isWarDeploy": READ,
        "loadREUFile": READ, "unlockTemplate": WRITE,
    },
    "com.fr.base.operator.org.OrganizationOperator": {
        "*": DENY, "getRoleGroup": READ, "getConnectionGroup": READ, "canAccess": READ,
    },
    "com.fr.base.rpc.encrypt.EncryptOperator": {"*": DENY},
    "com.fr.cluster.engine.rpc.remote.ClusterOperator": {"*": READ},
    "com.fr.config.dao.CommitHelper": {"*": DENY},
    "com.fr.config.dao.DataFetcher": {"*": DENY, "getConfig": READ},
    "com.fr.data.operator.DataOperatorProvider": {"*": READ},
    "com.fr.esd.core.remote.ESDConfigEventOperator": {"*": DENY},
    "com.fr.file.filetree.FileNodes": {"*": READ},
    "com.fr.form.share.ShareComponentOperator": {
        "*": DENY, "getSharePath": READ, "cacheComponents": WRITE,
    },
    "com.fr.form.share.ShareEmbeddedConverter": {"*": DENY,
                                                 "convertToEmbeddedTableData": READ},
    "com.fr.plugin.cloud.analytics.collect.rpc.RPCDataCollector": {"*": DENY},
    "com.fr.plugin.weixin.server.rpc.WeiXinRPCOperator": {"*": DENY, "getAgents": READ},
    "com.fr.security.encryption.storage.StorageTransfer": {
        "*": DENY, "getCurrentEncryptionMode": READ,
    },
    "com.fr.workspace.engine.client.heartbeart.WorkspaceHeartbeat": {
        "*": DENY, "getInterval": READ,
    },
    "com.fr.workspace.resource.WorkResource": {
        "*": WRITE,
        "readFully": READ, "openStream": READ, "exist": READ, "list": READ,
        "isDirectory": READ, "lastModified": READ, "length": READ,
    },
    "com.fr.workspace.server.authority.AuthorityOperator": {
        "*": DENY,
        "getAuthorities": READ, "getCustomRoleAuthorities": READ,
        "getUserAuthorities": READ, "hasAuthority": READ,
        "findWithTotalCount": READ,
    },
    "com.fr.workspace.server.authority.decision.DecisionOperator": {
        "*": DENY, "getMembers": READ, "getCustoms": READ,
        "getUserIdByName": READ, "isRoot": READ,
    },
    "com.fr.workspace.server.check.TemplateChecker": {"*": DENY, "checkFont": READ},
    "com.fr.workspace.server.check.VersionInfoOperator": {"*": READ},
    "com.fr.workspace.server.connection.DBConnectAuth": {"*": READ},
    "com.fr.workspace.server.exporter.TemplateExportOperator": {
        "*": DENY, "export": READ, "exportFormAsImageData": READ,
        "exportWorkBookAsImageData": READ, "imageToByteData": READ,
        "byteDataToImage": READ,
    },
    "com.fr.workspace.server.lock.TplOperator": {"*": WRITE},
    "com.fr.workspace.server.lock.editlock.EditLockOperator": {
        "*": DENY, "isLocked": READ, "lock": WRITE, "unlock": WRITE,
    },
    "com.fr.workspace.server.socket.SocketInfoOperator": {"*": READ},
    "com.fr.workspace.server.vcs.VcsOperator": {
        "*": DENY,
        "getVersions": READ, "getFilterVersions": READ,
        "getFileVersionByIndexAndUsername": READ, "getFileVersionByIndex": READ,
        "getFileVersion": READ, "getFileOfFileVersion": READ, "getFileOfCurrent": READ,
    },
}

#: 写方法里哪些参数是「路径」（远程工作区路径，会被范围守门检查）
WRITE_PATH_ARGS = {
    ("com.fr.workspace.resource.WorkResource", "write"): (0,),
    ("com.fr.workspace.resource.WorkResource", "createFile"): (0,),
    ("com.fr.workspace.resource.WorkResource", "createDirectory"): (0,),
    ("com.fr.workspace.resource.WorkResource", "delete"): (0,),
    ("com.fr.workspace.resource.WorkResource", "rename"): (0, 1),
    ("com.fr.workspace.resource.WorkResource", "save"): (0, 1),
    ("com.fr.workspace.server.lock.TplOperator", "readAndLockFile"): (0,),
    ("com.fr.workspace.server.lock.TplOperator", "closeAndFreeFile"): (0,),
    ("com.fr.workspace.server.lock.TplOperator", "rename"): (0, 1),
    ("com.fr.workspace.server.lock.TplOperator", "saveAs"): (0,),
    ("com.fr.workspace.server.lock.TplOperator", "delete"): (0,),
    ("com.fr.workspace.server.lock.TplOperator", "userOut"): (0,),
    ("com.fr.workspace.server.lock.TplOperator", "userIn"): (0,),
    ("com.fr.base.operator.common.CommonOperator", "unlockTemplate"): (0,),
    ("com.fr.base.io.FileAssistUtilsOperator", "moveToTrash"): (0,),
}


# ---------------------------------------------------------------------------
# 服务 / 方法查询
# ---------------------------------------------------------------------------
def service_names():
    return sorted(SERVICES)


def get_service(class_name: str):
    svc = SERVICES.get(class_name)
    if svc is None:
        hint = [c for c in SERVICE_ALIASES if c.endswith("." + class_name)]
        raise ApiError(
            f"未知服务 {class_name}；用 `frcli rpc services` 看清单"
            + (f"，是否想写 {hint[0]}？" if hint else ""))
    return svc


#: 允许用短名（去包名的类名）指代服务
SERVICE_ALIASES = {c: c for c in SERVICES}


def resolve_service(name: str) -> str:
    if name in SERVICES:
        return name
    matches = [c for c in SERVICES if c.rsplit(".", 1)[-1] == name]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise ApiError(f"服务短名 {name} 有歧义，候选: {matches}")
    raise ApiError(f"未知服务 {name}；`frcli rpc services` 看清单，"
                   "或 `frcli rpc services --local` 离线查看")


def method_policy(class_name: str, method: str) -> str:
    table = POLICY.get(class_name, {"*": DENY})
    return table.get(method, table.get("*", DENY))


def find_methods(class_name: str, method: str):
    return [m for m in get_service(class_name).methods if m.name == method] \
        if method else list(get_service(class_name).methods)


def resolve_method(class_name: str, method: str, sig: str = None, arity: int = None):
    """按名字（+可选签名 / 参数个数）定位唯一方法。

    重载消歧顺序：`--sig` 显式类型 > `--arg` 个数唯一匹配 > 报错列出候选
    （`WorkResource.list` 有 (String) 与 (String, Filter) 两个重载，按个数即可分开）。
    """
    cands = find_methods(class_name, method)
    if not cands:
        names = sorted({m.name for m in get_service(class_name).methods})
        raise ApiError(f"{class_name} 没有方法 {method}；可用: {', '.join(names)}")
    if sig:
        want = [jser.normalize_param_type(p) for p in sig.split(",") if p.strip()]
        cands = [m for m in cands if [jser.normalize_param_type(p) for p in m.params] == want]
        if not cands:
            raise ApiError(f"{class_name}.{method} 没有签名 ({', '.join(want)}) 的重载")
    if len(cands) > 1 and arity is not None:
        by_arity = [m for m in cands if len(m.params) == arity]
        if len(by_arity) == 1:
            return by_arity[0]
    if len(cands) > 1:
        sigs = " | ".join(format_params(m) for m in cands)
        raise ApiError(f"{class_name}.{method} 有 {len(cands)} 个重载，用 --sig 指定一个："
                       f"{sigs}")
    return cands[0]


def format_params(m) -> str:
    return "(" + ", ".join(m.params) + ")"


def format_signature(m) -> str:
    kind = "default " if "d" in m.flags else ("static " if "s" in m.flags else "")
    return f"{kind}{m.returns} {m.name}{format_params(m)}"


def signature_id(m) -> str:
    return ",".join(m.params)


# ---------------------------------------------------------------------------
# 参数编码
# ---------------------------------------------------------------------------
def parse_arg(spec: str, declared: str):
    """解析一个 `--arg`。

    两种写法：`TYPE=VALUE`（显式类型）与 `VALUE`（按签名推断）。
    `byte[]` 的值是**本地文件路径**（写方法用 `@path` 也可以）。
    """
    type_name, value = declared, spec
    head, sep, tail = spec.partition("=")
    if sep and jser.is_scalar_type(head.strip()) and head.strip() == declared:
        value = tail
    elif sep and jser.is_scalar_type(head.strip()):
        type_name = jser.normalize_param_type(head.strip())
        value = tail

    if type_name == "byte[]":
        path = value[1:] if value.startswith("@") else value
        p = Path(path)
        if not p.is_file():
            raise ApiError(f"byte[] 参数需要本地文件路径，读不到: {path}")
        return p.read_bytes()
    if value.strip() == "null":
        if type_name in jser.PRIMITIVE_NAMES:
            raise ApiError(f"{type_name} 是基本类型，不能传 null")
        return None
    return value


# ---------------------------------------------------------------------------
# 写范围守门
# ---------------------------------------------------------------------------
def check_write_scope(class_name: str, method: str, args, any_path: bool = False):
    """写方法放行前检查：每个路径参数都要落在写范围内。

    判定只有一份（`remotedesign.assert_in_write_scope`），且 fail-closed：
    没设 `$FRCLI_WRITE_SCOPE` 又没 `$FRCLI_ALLOW_ANY_PATH` → 拒绝。
    没有路径参数 → 也拒绝（无法验证范围）。
    `any_path=True`（`--any-path`）等价于设 `$FRCLI_ALLOW_ANY_PATH`，只放行本次调用。
    """
    if any_path:
        os.environ[ALLOW_ANY_ENV] = "1"
    idxs = WRITE_PATH_ARGS.get((class_name, method), ())
    if not idxs:
        raise ApiError(
            f"{class_name}.{method} 是写语义但没有可检查的路径参数，"
            "无法验证写范围 → 拒绝。用 `frcli report upload/delete` 走已审计的路径。")
    if len(idxs) > len(args):
        raise ApiError(f"{class_name}.{method} 参数个数与签名不符")
    for i in idxs:
        path = args[i]
        if not isinstance(path, str) or not path.strip():
            raise ApiError(f"{class_name}.{method} 第 {i + 1} 个参数不是合法路径: {path!r}")
        # 与 report upload/delete 共用同一个沙箱判定：$FRCLI_WRITE_SCOPE 未设时
        # 不再兜底成某个写死的个人目录（那是把团队约定焊进产品），直接 fail-closed。
        assert_in_write_scope(path)


def in_scope(path: str, scope: str) -> bool:
    """⚠️ 已废弃的薄封装：仅为兼容旧测试保留，内部走同一个沙箱判定。

    不要在这里加 `.tmp` 剥离之类的"口径对齐" —— 服务端鉴权会剥 `.tmp`，但
    **落点判定不能剥**：`<scope>.tmp` 是 scope 的兄弟节点，剥了就成了"域内"。
    """
    try:
        assert_in_write_scope(path, scope)
        return True
    except ApiError:
        return False


# ---------------------------------------------------------------------------
# 返回值 → JSON
# ---------------------------------------------------------------------------
_THROWABLE_HINT = ("Exception", "Error", "Throwable")


def is_throwable(obj) -> bool:
    return isinstance(obj, jser.JObject) and any(
        k in obj.class_name for k in _THROWABLE_HINT)


def simplify(value, depth: int = 0, seen=None):
    """把 JObject/JArray 结果翻成 JSON 友好的结构（带环检测）。"""
    if depth > 12:
        return "<深度截断>"
    seen = seen if seen is not None else set()
    if isinstance(value, jser.JArray):
        if value.class_name == "[B":
            raw = bytes(b & 0xFF for b in value)
            return {"__bytes__": len(raw)}
        return [simplify(v, depth + 1, seen) for v in value]
    if not isinstance(value, jser.JObject):
        return value
    if id(value) in seen:
        return "<循环引用>"
    seen = seen | {id(value)}
    cls = value.class_name
    if "__enum__" in value.fields:
        ev = value.fields["__enum__"]
        name = ev.fields.get("__enum__") if isinstance(ev, jser.JObject) else ev
        return f"{cls}.{name}"
    if is_throwable(value):
        return {"__exception__": _exception_text(value, 0)}
    if cls == "java.lang.String":
        return value.fields.get("value")
    if set(value.fields) == {"value"} and cls.startswith("java.lang."):
        return value.fields["value"]
    if cls.endswith("JSONArray"):
        return simplify(value.fields.get("list"), depth + 1, seen)
    if cls in ("java.util.ArrayList", "java.util.LinkedList", "java.util.Vector"):
        return simplify(value.custom or [], depth + 1, seen)
    if cls.endswith("HashSet"):
        # HashSet.writeObject 把内部 map **摊平**写：blockdata(容量/负载/大小) + 各元素，
        # 不是嵌套的 HashMap 对象。早期版本按嵌套解，导致非空集合被读成 [] ——
        # `checkFont` 因此会把「缺字体」误报成「没问题」。
        return [simplify(x, depth + 1, seen) for x in (value.custom or [])]
    if cls == "java.util.HashMap":
        items = value.custom or {}
        return {_key(k, depth + 1, seen): simplify(v, depth + 1, seen)
                for k, v in items.items()}
    if cls.startswith("java.util.Collections$Unmodifiable"):
        return simplify(value.fields.get("c") or value.fields.get("m"), depth + 1, seen)
    if cls.endswith("$ValuesView") or cls.endswith("$KeySet") or cls.endswith("$EntrySet"):
        return simplify(value.fields.get("map"), depth + 1, seen)
    out = {"__class__": cls}
    out.update({k: simplify(v, depth + 1, seen) for k, v in value.fields.items()
                if k != "cause"})
    if value.custom:
        out["__custom__"] = simplify(value.custom, depth + 1, seen)
    return out


def _key(k, depth, seen):
    s = simplify(k, depth, seen)
    return s if isinstance(s, (str, int, float, bool)) else str(s)


def _exception_text(obj, depth=0) -> str:
    if not isinstance(obj, jser.JObject) or depth > 5:
        return str(obj)
    msg = obj.fields.get("detailMessage") or obj.fields.get("message")
    out = f"{obj.class_name}: {msg}" if msg else obj.class_name
    cause = obj.fields.get("cause")
    if isinstance(cause, jser.JObject) and cause is not obj:
        out += f"  (cause: {_exception_text(cause, depth + 1)})"
    return out


def decode_result(value):
    """结果 → (json 值, 展示用类型说明)。"""
    return simplify(value), type(value).__name__ if value is not None else "void"


# ---------------------------------------------------------------------------
# 真实调用
# ---------------------------------------------------------------------------
def prepared_args(m, raw_args):
    """`--arg` 列表 → [(声明类型, 值)]（真正的编码交给 build_call）。"""
    if len(raw_args) != len(m.params):
        raise ApiError(f"需要 {len(m.params)} 个参数{format_params(m)}，"
                       f"给了 {len(raw_args)} 个"
                       + (f"；示例：{' '.join('--arg ' + _example(p) for p in m.params)}"
                          if m.params else ""))
    return [(declared, parse_arg(spec, declared))
            for spec, declared in zip(raw_args, m.params)]


def _example(type_name: str) -> str:
    if type_name == "byte[]":
        return "/path/to/local.bin"
    if type_name == "java.lang.String":
        return "reportlets/xxx.cpt"
    return "1" if type_name in jser.PRIMITIVE_NAMES else "value"


def invoke(config, class_name: str, m, pairs):
    """发一次调用，返回 `RpcResult`。"""
    from .remotedesign import RemoteDesignSession
    with RemoteDesignSession(config) as s:
        s.check()
        return s.call_result(class_name, m.name, pairs)


def rpc_error_hint(class_name: str, m, message: str) -> str:
    """把服务端异常翻成可执行的下一步建议。"""
    if "NoSuchMethodException" in message:
        return (f"线上 {class_name} 没有这个方法签名 —— 安装包内的 jar 是 10.0.19 的副本，"
                "线上类版本可能不同；用 `frcli rpc methods` 看本地清单，"
                "再试同名的其他重载（`--sig`）。")
    if "NoSuchMethodError" in message or "AbstractMethodError" in message:
        return "线上类版本与安装包内的 jar 不一致，换 `frcli rpc services` 里的其他服务试。"
    if "IllegalAccess" in message:
        return "服务端拒绝访问该成员（多半不是接口方法），别硬试。"
    return ""


def live_services(config):
    """线上 `/decision/remote/design/service` 返回的服务类清单。"""
    from .remotedesign import RemoteDesignSession
    with RemoteDesignSession(config) as s:
        s.check()
        return s.services()


# ---------------------------------------------------------------------------
# 路径口径提示 / 字节结果
# ---------------------------------------------------------------------------
#: 这些服务收**工作区路径**（要 `reportlets/` 前缀）
WORKSPACE_PATH_SERVICES = {
    "com.fr.workspace.resource.WorkResource",
    "com.fr.workspace.server.lock.TplOperator",
}
#: 这些服务收**展示路径**（`report list` 给的 path，不能带前缀）
DISPLAY_PATH_SERVICES = {
    "com.fr.workspace.server.vcs.VcsOperator",
    "com.fr.workspace.server.exporter.TemplateExportOperator",
    "com.fr.workspace.server.check.TemplateChecker",
}
WORKSPACE_ROOTS = ("reportlets", "assets", "config", "lib", "plugins", "classes",
                   "resources")


def path_hint(class_name: str, pairs) -> str:
    """路径口径提醒 —— 传错前缀不会报错，只会返回空/false，最容易被当成「没权限」。"""
    strings = [v for _t, v in pairs if isinstance(v, str) and v.strip()]
    if not strings:
        return ""
    if class_name in WORKSPACE_PATH_SERVICES:
        bad = [s for s in strings if not s.lstrip("/").startswith(WORKSPACE_ROOTS)]
        if bad:
            return (f"{class_name} 收**工作区路径**，需要 `reportlets/` 等前缀："
                    f"你传的是 {bad[0]!r}。`report list` 给的是展示路径，"
                    "拼上 `reportlets/` 再试（前缀写错不会报错，只会返回空/False）。")
    if class_name in DISPLAY_PATH_SERVICES:
        bad = [s for s in strings if s.lstrip("/").startswith("reportlets/")]
        if bad:
            return (f"{class_name} 收**展示路径**（`report list` 给的原样），"
                    f"不能带 `reportlets/` 前缀：你传的是 {bad[0]!r}。去掉前缀再试"
                    "（带前缀不会报错，只会返回空）。")
    return ""


_MAGICS = ((b"\x89PNG\r\n\x1a\n", "png"), (b"%PDF", "pdf"), (b"PK\x03\x04", "zip"),
           (b"{\\rtf", "rtf"))


def raw_bytes(value):
    """`[B` 结果 → bytes；不是字节数组时返回 None。"""
    if isinstance(value, jser.JArray) and value.class_name == "[B":
        return bytes(b & 0xFF for b in value)
    return None


def describe_bytes(data: bytes, path: str) -> dict:
    """落盘后的描述：路径 / 大小 / sha256 / 识别出的格式。"""
    import hashlib
    fmt = next((name for magic, name in _MAGICS if data.startswith(magic)), None)
    return {"file": path, "size": len(data), "format": fmt,
            "sha256": hashlib.sha256(data).hexdigest()}
