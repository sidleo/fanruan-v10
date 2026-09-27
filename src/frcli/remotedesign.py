"""FineReport 远程设计（Remote Design）通道 —— 服务端模板读写。

这是决策平台唯一能**写入 .cpt 模板内容**的通道：Designer 的「远程设计」不是
REST，而是把服务端的 WEB-INF 目录当成远程文件系统，走一条自带 RPC：

  1. `POST {ws}/decision/remote/design/check`
     → `{"data":{"transmissionEncryption":2,"frontSeed":"...","frontSM4Key":"..."}}`
        `transmissionEncryption`：0=RSA 1=SM2 2=AES 3=SM4（决定密码怎么加密）
  2. `POST {ws}/decision/remote/design/verify`  （表单 username + 加密后的 password）
     → `{"data":"<JWT>"}`；JWT 的 subject 就是用户名，同时登记进 loginStatus
  3. `POST {ws}/decision/remote/design/channel`  （body = 序列化后的 Invocation）
     → 服务端 `WorkspaceServerInvoker.handleMessage()`：
       `Class.forName(declareClassName).getDeclaredMethod(methodName, paramTypes)`
       → 从 FineObjectPool 的 serverPool 取实例反射调用 → 回一个序列化 Result

  可调用的服务清单见 `POST /decision/remote/design/service`（本服务器实测 28 个），
  与模板文件相关的是：
    * `com.fr.workspace.resource.WorkResource`
      readFully/exist/length/list/write/delete/rename/createDirectory/...
    * `com.fr.workspace.server.lock.TplOperator`
      readAndLockFile/closeAndFreeFile/rename/saveAs/delete/userIn/userOut

权限（服务端 `ServerWorkResource`）：路径含 `reportlets` 时查该账号的远程设计授权
目录（`RemoteDesignAuthHelper.hasAuthority`），不含则直接放行；`write` 无权限时
**静默不写**（不抛错），所以每次写完必须回读校验。
"""

import gzip
import hashlib
import os
import posixpath
import ssl
import time
import uuid
from pathlib import Path
from xml.etree import ElementTree as ET

import httpx

from . import jser
from .jser import JObject
from .rdcrypto import encrypt_password
from .exceptions import ApiError, AuthError, ConnectionError

WORKSPACE_SERVICE = "com.fr.workspace.resource.WorkResource"
TPL_OPERATOR = "com.fr.workspace.server.lock.TplOperator"


# ---------------------------------------------------------------------------
# Invocation 载荷构造 / Result 解析（对应 InvocationSerializer / ResultSerializer）
# ---------------------------------------------------------------------------
def build_call(class_name, method_name, args, metadata) -> bytes:
    """args: [(type, value)]；type 支持 jser 里的标量类型（String / byte[] / int …）。"""
    param_types = [jser.normalize_param_type(t) for t, _ in args]
    blobs = [jser.encode_param(t, v) for t, v in args]

    w = jser.JavaWriter()
    w.raw(jser.STREAM_MAGIC + jser.STREAM_VERSION)

    def body():
        w.string(class_name)
        w.string(method_name)
        w.array(jser.DESC_CLASS_ARR,
                [(lambda n=n: w.cls(n, jser.PARAM_TYPE_DESC[n])) for n in param_types])
        w.array(jser.DESC_BYTE_ARR_ARR,
                [(lambda b=b: w.primitive_array(jser.DESC_BYTE_ARR, b, len(b)))
                 for b in blobs])

    w.object(jser.DESC_INVOCATION_PACK, body)

    keys = list(metadata.keys())
    order = [k for _, k in jser.hashmap_order(keys)]

    def map_body():
        # HashMap.writeObject()：先写 loadFactor/threshold，再把 capacity/size
        # 与键值对按 block data 写出（对象会把块数据刷成独立的 TC_BLOCKDATA）
        w.raw(jser.struct.pack(">f", 0.75))
        w.i4(12)
        w.blockdata(jser.struct.pack(">ii", 16, len(keys)))
        for k in order:
            w.string(k)
            w.string(metadata[k])
        w.u1(jser.TC_ENDBLOCKDATA)

    w.object(jser.DESC_HASHMAP, map_body)
    return gzip.compress(bytes(w.buf), mtime=0)


class RpcResult:
    def __init__(self, value, exception):
        self.value = value
        self.exception = exception

    @property
    def ok(self):
        return self.exception is None


def _throwable_message(obj, depth: int = 0) -> str:
    # Throwable 的 cause 未初始化时指向自己 → 必须防自引用递归
    if not isinstance(obj, JObject) or depth > 5:
        return str(obj)
    msg = obj.fields.get("detailMessage") or obj.fields.get("message")
    out = f"{obj.class_name}: {msg}" if msg else obj.class_name
    cause = obj.fields.get("cause")
    if isinstance(cause, JObject) and cause is not obj:
        out += f"  (cause: {_throwable_message(cause, depth + 1)})"
    return out


def parse_response(body: bytes) -> RpcResult:
    r = jser.JavaReader(gzip.decompress(body))
    r.raw(4)
    marker = r.read_object()
    if not isinstance(marker, JObject):
        raise ApiError(f"远程设计返回了非预期对象: {marker!r}")
    obj_bytes = marker.fields["objectBytes"]
    if isinstance(obj_bytes, jser.JArray):
        obj_bytes = bytes(v & 0xFF for v in obj_bytes)
    exc = marker.fields.get("exception")
    value = None
    if obj_bytes:
        value = jser.read_marked_value(bytes(obj_bytes))[1]
    if isinstance(exc, JObject):
        exc = _throwable_message(exc)
    return RpcResult(value, exc)


def _client(base_url: str, timeout: float) -> httpx.Client:
    kwargs = {"base_url": base_url, "timeout": timeout, "follow_redirects": False}
    if base_url.lower().startswith("https"):
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        if hasattr(ssl, "OP_LEGACY_SERVER_CONNECT"):
            ctx.options |= ssl.OP_LEGACY_SERVER_CONNECT
        try:
            ctx.set_ciphers("DEFAULT:@SECLEVEL=1")
        except ssl.SSLError:
            pass
        kwargs["verify"] = ctx
    return httpx.Client(**kwargs)


class RemoteDesignSession:
    """一次远程设计会话：握手 → 取 token → 走 channel 调服务端 RPC。"""

    def __init__(self, config, client_id: str = None):
        self.config = config
        self.workspace = (config.workspace or "/webroot").rstrip("/")
        self.base = f"{self.workspace}/decision/remote/design"
        timeout = float(os.environ.get("FRCLI_RD_TIMEOUT", "300"))
        self._http = _client(config.url.rstrip("/"), timeout)
        self.client_id = client_id or f"frcli-{uuid.uuid4()}"
        self.token = None
        self._check = None

    # -- 生命周期 -----------------------------------------------------------
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def close(self):
        self._http.close()

    def _post(self, path, **kwargs):
        try:
            return self._http.post(path, **kwargs)
        except httpx.RequestError as e:
            raise ConnectionError(f"远程设计请求失败: {e}")

    @staticmethod
    def _unwrap(resp, what):
        try:
            body = resp.json()
        except Exception:
            raise ApiError(f"{what} 失败: HTTP {resp.status_code}，非 JSON 响应 "
                           f"{resp.text[:200]}")
        if body.get("errorCode"):
            raise ApiError(f"{what} 失败: [{body['errorCode']}] {body.get('errorMsg')}")
        return body.get("data")

    def check(self) -> dict:
        """握手：拿服务端传输加密参数。"""
        resp = self._post(f"{self.base}/check")
        data = self._unwrap(resp, "远程设计握手 /check")
        if not data:
            raise ApiError("服务端未开放远程设计（/check 无 data）")
        self._check = data
        return data

    def login(self) -> str:
        """取远程设计 JWT。需要账号具备远程设计权限（或超管）。"""
        if self.token:
            return self.token
        chk = self._check or self.check()
        if not self.config.password:
            raise AuthError("远程设计需要密码：请用 `frcli server add ... -p <密码>` 配置")
        enc = encrypt_password(self.config.password, chk["transmissionEncryption"],
                               chk.get("frontSeed", ""), chk.get("frontSM4Key", ""))
        resp = self._post(f"{self.base}/verify",
                          data={"username": self.config.username, "password": enc})
        data = self._unwrap(resp, "远程设计认证 /verify")
        if not data:
            raise AuthError("远程设计认证未返回 token")
        self.token = data
        return data

    def services(self):
        """服务端暴露的 RPC 服务类清单。"""
        chk = self._check or self.check()
        enc = encrypt_password(self.config.password, chk["transmissionEncryption"],
                               chk.get("frontSeed", ""), chk.get("frontSM4Key", ""))
        resp = self._post(f"{self.base}/service",
                          data={"username": self.config.username, "password": enc})
        return self._unwrap(resp, "远程设计服务清单 /service")

    # -- RPC ---------------------------------------------------------------
    def call_result(self, service: str, method: str, args) -> "RpcResult":
        """发一次 channel 调用，返回原始 `RpcResult`（不抛服务端异常）。"""
        token = self.login()
        meta = {"username": self.config.username, "id": self.client_id,
                "token": token, "encryptVersion": "encryptVersion"}
        resp = self._post(f"{self.base}/channel", content=build_call(service, method, args, meta),
                          headers={"Content-Type": "application/octet-stream"})
        if resp.status_code != 200:
            raise ConnectionError(f"远程设计 channel 失败: HTTP {resp.status_code}")
        return parse_response(resp.content)

    def call(self, service: str, method: str, args):
        res = self.call_result(service, method, args)
        if res.exception:
            raise ApiError(f"远程设计 RPC {method} 失败: {res.exception}")
        return _unwrap_value(res.value)

    # -- 文件操作（WorkResource）-------------------------------------------
    def list(self, path: str = ""):
        return self.call(WORKSPACE_SERVICE, "list", [("java.lang.String", path)])

    def exist(self, path: str) -> bool:
        return _as_bool(self.call(WORKSPACE_SERVICE, "exist", [("java.lang.String", path)]))

    def is_directory(self, path: str) -> bool:
        return _as_bool(self.call(WORKSPACE_SERVICE, "isDirectory",
                                  [("java.lang.String", path)]))

    def length(self, path: str) -> int:
        return _as_int(self.call(WORKSPACE_SERVICE, "length", [("java.lang.String", path)]))

    def read(self, path: str) -> bytes:
        return self.call(WORKSPACE_SERVICE, "readFully", [("java.lang.String", path)])

    def write(self, path: str, data: bytes):
        self.call(WORKSPACE_SERVICE, "write",
                  [("java.lang.String", path), ("byte[]", data)])

    def mkdir(self, path: str) -> bool:
        return _as_bool(self.call(WORKSPACE_SERVICE, "createDirectory",
                                  [("java.lang.String", path)]))

    def mkdirs(self, path: str):
        parts = [p for p in path.strip("/").split("/") if p]
        for i in range(1, len(parts) + 1):
            sub = "/".join(parts[:i])
            if not self.exist(sub):
                self.mkdir(sub)

    # -- 模板锁（TplOperator）：占用中的模板不要盲写 -------------------------
    def lock(self, path: str) -> bytes:
        """readAndLockFile：返回服务端现有内容并加锁；被别人锁住会报错。"""
        return self.call(TPL_OPERATOR, "readAndLockFile", [("java.lang.String", path)])

    def unlock(self, path: str):
        self.call(TPL_OPERATOR, "closeAndFreeFile", [("java.lang.String", path)])

    def delete(self, path: str) -> bool:
        """TplOperator.delete：移入回收站（可恢复）。"""
        return _as_bool(self.call(TPL_OPERATOR, "delete", [("java.lang.String", path)]))


def _unwrap_value(v):
    if isinstance(v, jser.JArray):
        if v.class_name == "[B":
            return bytes(b & 0xFF for b in v)
        return [_unwrap_value(x) for x in v]
    return v


def _as_bool(v) -> bool:
    if isinstance(v, JObject):
        return bool(v.fields.get("value"))
    return bool(v)


def _as_int(v) -> int:
    if isinstance(v, JObject):
        return int(v.fields.get("value"))
    return int(v)


def normalize_report_path(path: str) -> str:
    """把平台展示路径（`report list` 的 path）转成远程工作区路径。

    平台展示：`demo_group/demo_user/dept_a/dept_b/sales_daily.cpt`
    工作区：  `reportlets/demo_group/demo_user/dept_a/dept_b/sales_daily.cpt`
    """
    p = path.strip().lstrip("/")
    if p.startswith("reportlets/") or p == "reportlets":
        return p
    return f"reportlets/{p}"


# ---------------------------------------------------------------------------
# 高层操作：上传 / 删除
# ---------------------------------------------------------------------------
BACKUP_DIR = Path.home() / ".frcli" / "backups"


def _sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _save_backup(remote: str, content: bytes) -> str:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    flat = remote.replace("/", "__")
    path = BACKUP_DIR / f"{ts}__{flat}"
    path.write_bytes(content)
    return str(path)


WORKBOOK_MARK = b"<WorkBook"

#: 写操作沙箱：设了这个环境变量后，upload/delete 只允许落在它下面的路径。
#: 给「agent 跑测试」这类场景用 —— 把 agent 的手脚限定在一个目录里，而不是靠它自觉。
#: 不设 = 不限制（人自己用时的默认行为）。
WRITE_SCOPE_ENV = "FRCLI_WRITE_SCOPE"

#: 显式放开写范围的逃生口（`--any-path` 会为本次调用设它）。
#: 设计取舍：**沉默不等于不限制** —— 没设范围就直接拒绝，而不是默认放行。
#: 2026-09 踩过：agent 在没设 `FRCLI_WRITE_SCOPE` 的 shell 里跑 `report edit --apply`，
#: 真的把别人的生产模板写掉了（靠自动备份才逐字节还原）。写模板会影响所有看这张报表的人，
#: 所以「要不要写、写到哪」必须是一次显式决定。
ALLOW_ANY_ENV = "FRCLI_ALLOW_ANY_PATH"


def _norm(path: str) -> str:
    """归一化到工作区路径并解析 `..`（服务端 `FilenameUtils.standard` 也会做，必须同口径）。"""
    return posixpath.normpath(normalize_report_path(path))


def assert_in_write_scope(remote_path: str, scope: str = None):
    """落点必须在 scope 之内，否则抛错。

    scope 取值优先级：显式参数 > `$FRCLI_WRITE_SCOPE`；两者都没有时：
      * 设了 `$FRCLI_ALLOW_ANY_PATH`（`--any-path`）→ 放行（使用者对目标负全责）
      * 否则 → **拒绝**。沉默不代表可以随便写。

    这是**唯一**的沙箱判定实现 —— 别再写第二份（曾出现过 rpc.py 里另写一份、
    且多剥了一个 `.tmp` 后缀，导致 `<scope>.tmp` 这个**兄弟节点**被判成域内放行）。
    """
    scope = (scope or "").strip() or os.environ.get(WRITE_SCOPE_ENV, "").strip()
    if not scope:
        if os.environ.get(ALLOW_ANY_ENV, "").strip().lower() in ("1", "true", "yes"):
            return
        raise ApiError(
            "写操作未指定范围，已拒绝（沉默不等于不限制）。二选一：\n"
            f"  · 限定范围：export {WRITE_SCOPE_ENV}=\"<目录>\" 后再执行\n"
            "  · 确认要写这个目标：命令行加 --any-path（本次调用生效）\n"
            f"目标：{remote_path}")
    scope_n = _norm(scope).rstrip("/")
    target = _norm(remote_path)
    if target != scope_n and not target.startswith(scope_n + "/"):
        raise ApiError(
            f"写操作被 {WRITE_SCOPE_ENV} 限制在 {scope_n}/ 之内，已拒绝：{target}")


def assert_template_bytes(data: bytes, allow_format: bool = False):
    """挡住「把非模板序列化写回 .cpt」这条毁报表的路径。

    `GET /decision/view/report?format=cpt` 返回的**不是**模板文件字节，而是另一种序列化
    （根元素 `<TableDataMap>`，缺 `<WorkBook>`/`<StyleList>`）。若把它的产物 upload 回去，
    服务端会照写，回读校验还一致（因为写的确实是那份 stub）→ 静默毁模板。
    实测抽样：可读模板的根元素全是 `<WorkBook>`。

    两道关（都是**本地**判定，解析失败一个字节都不发）：
      1. 前 600 字节里有 `<WorkBook>`（挡 format=cpt 提取物）
      2. 整篇是**良构 XML**（挡残缺内容 —— 服务端对坏 XML 照收，渲染成空表，
         `verified: true` 是回读比对，不代表内容能被解析）

    `allow_format=True` **两道关一起跳过**：它表达的是"我确知自己在传什么"，
    此时再只跳第一道就会留下"能传非 WorkBook 但必须良构 XML"的死角 ——
    实测连一份纯文本 `_目录说明.txt` 都传不上去，只能套一层 `<note><![CDATA[…]]>` 糊过去。
    """
    if not allow_format:
        if WORKBOOK_MARK not in data[:600]:
            raise ApiError(
                "本地内容不像 cpt 模板（前 600 字节没有 <WorkBook>），已拒绝写入。"
                "常见原因：文件来自 `format=cpt` 端点/旧版 report download，那是数据集定义提取物"
                "（根元素 <TableDataMap>），不是模板字节，写回去会毁掉模板。"
                "确知自己在做什么时再加 --allow-format。")
    if allow_format:
        return
    try:
        ET.fromstring(data)
    except ET.ParseError as e:
        raise ApiError(
            f"内容不是良构 XML（{e}），已拒绝写入。服务端对残缺 XML 照收不误、"
            "渲染成空表且回读校验通过，所以这一关必须在这里拦。")
    except (ValueError, UnicodeDecodeError) as e:
        raise ApiError(f"内容不是可解析的 XML 文本（{e}），已拒绝写入。")


def upload_template(config, local_file: str, remote_path: str, force: bool = False,
                    allow_format: bool = False) -> dict:
    """把本地模板写到服务端（远程设计通道）。

    覆盖已有模板时必须 `force=True`；写前先 `readAndLockFile` 占锁（被他人占用会
    直接报错），并把服务端原文件备份到 `~/.frcli/backups/`；写后回读校验 SHA256
    —— 因为无授权时服务端是**静默不写**，不看回读会误报成功。
    """
    remote = normalize_report_path(remote_path)
    assert_in_write_scope(remote)      # ⚠️ 必须在任何网络调用之前
    data = Path(local_file).read_bytes()
    assert_template_bytes(data, allow_format)
    result = {
        "action": "upload",
        "local": str(Path(local_file).resolve()),
        "remote": remote,
        "size": len(data),
        "sha256": _sha256(data),
    }
    with RemoteDesignSession(config) as s:
        s.check()
        exists = s.exist(remote)
        if exists and not force:
            raise ApiError(
                f"服务端已存在 {remote}（{s.length(remote)} 字节），"
                "确认要覆盖再加 --force")
        result["overwritten"] = exists
        locked = False
        if exists:
            current = s.lock(remote)          # 被其他 Designer 锁住 → 这里直接抛错
            locked = True
            result["backup"] = _save_backup(remote, current)
            result["previous_sha256"] = _sha256(current)
        try:
            if not exists:
                parent = remote.rsplit("/", 1)[0] if "/" in remote else ""
                if parent:
                    s.mkdirs(parent)
            s.write(remote, data)
        finally:
            if locked:
                try:
                    s.unlock(remote)
                except Exception:
                    pass
        back = s.read(remote)
        if _sha256(back) != _sha256(data):
            raise ApiError(
                f"写入后回读不一致（服务端 {len(back)} 字节 / 本地 {len(data)} 字节）："
                "多半是该路径不在账号的远程设计授权目录内，服务端静默跳过了写入")
        result["verified"] = True
        result["server_size"] = len(back)
    return result


def delete_template(config, remote_path: str, force: bool = False,
                    recursive: bool = False) -> dict:
    """删除服务端模板（TplOperator.delete → 移入回收站，可恢复）。

    ⚠️ 这个服务对**目录**也照删（整个目录进回收站），所以先判类型：
    目标是目录时必须显式 `recursive=True`（命令行 `--recursive`）。
    """
    remote = normalize_report_path(remote_path)
    assert_in_write_scope(remote)
    if not force:
        raise ApiError(f"删除服务端模板需要显式确认：加 --force（目标 {remote}）")
    with RemoteDesignSession(config) as s:
        s.check()
        if not s.exist(remote):
            raise ApiError(f"服务端不存在: {remote}")
        is_dir = s.is_directory(remote)
        if is_dir and not recursive:
            raise ApiError(
                f"{remote} 是一个**目录**：删除会把整个目录（含里面全部模板）移入回收站。"
                "确认要这么做就再加 --recursive。")
        size = s.length(remote)
        ok = s.delete(remote)
        result = {"action": "delete", "remote": remote, "size": size,
                  "deleted": bool(ok), "trash": bool(ok),
                  "deleted_directory": bool(is_dir)}
        if not ok:
            raise ApiError(f"删除失败（模板可能被 Designer 锁定中）: {remote}")
        if s.exist(remote):
            raise ApiError(f"删除后文件仍存在: {remote}")
        result["verified"] = True
    return result


def workspace_list(config, path: str = "") -> dict:
    """列出服务端远程工作区目录（`reportlets` 下就是模板目录）。"""
    with RemoteDesignSession(config) as s:
        s.check()
        target = path.strip().lstrip("/")
        if target and not target.startswith(("reportlets", "assets", "resources",
                                             "config", "lib", "plugins", "classes")):
            target = normalize_report_path(target)
        entries = []
        for name in s.list(target):
            child = f"{target}/{name}" if target else name
            entries.append({
                "name": name,
                "path": child,
                "is_directory": s.is_directory(child),
            })
        return {"action": "ws-list", "path": target or "/", "count": len(entries),
                "entries": sorted(entries, key=lambda e: (not e["is_directory"], e["name"]))}
