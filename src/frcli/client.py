"""FineReport HTTP API 客户端"""

import json
import re
import html
import ssl
import os
import math
import time
from typing import Optional, Any
from pathlib import Path
import httpx
from .config import ServerConfig
from .auth import TokenManager
# 传输层错误分类在 neterr.py（中性模块）：auth.py 的登录跳也要用同一份文案，
# 而 client 依赖 auth，反向 import 会成环。这里保留 `_net_hint`/`_PROXY_HINT` 名字以免调用点变动。
from .neterr import (
    PROXY_HINT as _PROXY_HINT,
    is_proxy_5xx,
    net_hint as _net_hint,
)
from .exceptions import (
    FrcliError, AuthError, ConnectionError,
    ReportNotFoundError, ExportError, ApiError, InspectionError
)


def _configure_ssl():
    """配置 SSL 以支持 legacy renegotiation"""
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    ctx.set_ciphers("DEFAULT:@SECLEVEL=1")
    ctx.options |= ssl.OP_LEGACY_SERVER_CONNECT

    # 加载自定义 CA 证书（如果存在）
    # 证书路径可通过环境变量 FRCLI_CA_CERT 指定
    ca_cert = os.environ.get("FRCLI_CA_CERT")
    if ca_cert and Path(ca_cert).exists():
        ctx.load_verify_locations(ca_cert)

    return ctx


_AUTH_REDIRECT_CODES = (301, 302, 303, 307, 308)


def _is_auth_failure(resp: httpx.Response) -> bool:
    """判断响应是否代表认证失效。

    本服务器对失效 token 不返回 401，而是 **302 重定向到 CAS 登录页**
    （`https://sso.example.com/cas/login?service=...`，实测）。必须识别，
    否则调用方会把「未登录」当成「没有数据」——列表命令静默返回 `[]`。
    """
    if resp.status_code in (401, 403):
        return True
    if resp.status_code in _AUTH_REDIRECT_CODES:
        location = resp.headers.get("location", "").lower()
        return "cas" in location or "login" in location
    return False


# 平台出错页里那段人话的两种**选择器**写法，两种都要认：
#   ① `id=` 选择器（老语料/fixture：`<div id="detail-message">错误代码:11300002 …原始 SQL…</div>`）；
#   ② `class=` 选择器（2026-10-16 实测的保护页只有 class：
#      `<div class="detail-message">很抱歉，数据量过大触发保护机制…</div>`）。
# 只认 `id=` 时新版页面读出来是空串，平台原因（含可执行指令）被整条丢掉。
# ⚠ 两遍扫描、**id 优先**：两种写法同时出现时仍取 id 那份（它带错误码与原始 SQL）。
_HTML_ERROR_MSG = re.compile(
    r"""id=["'](detail-message|simple-message)["'][^>]*>(.*?)</div>""", re.S | re.I)
_HTML_ERROR_MSG_CLASS = re.compile(
    r"""class=["'](detail-message|simple-message)["'][^>]*>(.*?)</div>""", re.S | re.I)

#: 平台出错页的**结构标记**（与 `出错页面`/`Oops!!!` 并列的出错页证据）。
#: ⚠ 只在**开头是 HTML 形态**（`_looks_like_html_head`）时才当证据，绝不单独用：
#: 合法 CSV 的备注列里完全可能出现「出错页面」这类字样（0.10.3 误杀事故）。
#: 本批新增的是**只有 `class=` 选择器**的保护页模板族（2026-10-16 实测）——它没有「出错页面」字样；
#: 老语料的 `id=` 页若不带「出错页面」则维持原判（走魔数分支，同样会带出平台原因），不在这里扩大改动面。
_HTML_ERROR_PAGE_MARKERS = (
    "出错页面".encode("utf-8"), b"oops!!!",
    b'class="detail-message"', b"class='detail-message'",
    b'class="simple-message"', b"class='simple-message'",
)

# 平台出错页里的本地化 key，翻成人话（detail-message 为空时只剩它们）
_LOCALE_TEXT = {
    "Fine-Dec_No_Privilege_Access_Page": "当前账号无此接口权限（该接口需管理员）",
    "Fine-Dec_Default_Error_Tip": "平台返回错误页（无详细信息，通常是对象不存在）",
}


def _reason_from(text: str, pat) -> str:
    """按一个选择器正则取平台原文：`detail-message` 优先，退到 `simple-message`；空白视为无。"""
    reason = ""
    for match in pat.finditer(text or ""):
        raw = html.unescape(re.sub(r"<[^>]+>", "", match.group(2))).strip()
        is_detail = match.group(1).lower() == "detail-message"
        if raw and (is_detail or not reason):
            reason = raw
        if is_detail and raw:
            break
    return reason


def _html_error_reason(text: str) -> str:
    """从平台 HTML 出错页里取出**平台原文**：优先 `detail-message`，空则退到 `simple-message`，再本地化。

    两种选择器写法都认（见 `_HTML_ERROR_MSG`）：老语料的 `id="detail-message"`，
    与 2026-10-16 实测保护页的 `class="detail-message"`（只有 class、没有 id）。
    **按「选择器族」排序，不是按 detail/simple**：先整页扫 `id=` 族（detail→simple），取不到才扫
    `class=` 族（detail→simple）—— 即 `id="simple-message"` 与 `class="detail-message"` 同页时取 id 那份。
    两种形式同时在页面上时仍取带错误码/原始 SQL 的那份，老行为不变。
    空白/纯标签内容视为无 —— 老版 detail 为空时退到 simple，别给用户一片空白。

    接口调用（`_unwrap_json`）与导出产物校验（`assert_export_magic`）共用同一口径 ——
    两边都得能回答"平台到底说了什么"，否则用户只能自己去解产物文件。
    """
    reason = (_reason_from(text, _HTML_ERROR_MSG)
              or _reason_from(text, _HTML_ERROR_MSG_CLASS))
    return _LOCALE_TEXT.get(reason, reason)


#: 导出产物的错误原因里出现这些关键词时，附上可执行的下一步（键 = 错误码**或**原因短语）。
#: 11300002：实测宽表走默认分页导出必撞（加 extype=simple 可解）。
#: 「数据量过大」保护页：2026-10-16 实测——**平台内存保护**，extype=simple 不解除，
#: 得减少查询数据量；管理员可在平台「智能运维-内存管理-模板限制」调上限。
_MEMORY_GUARD_ADVICE = ("平台内存保护（数据量过大触发保护机制）：先在 SQL/参数上缩小查询数据量、"
                        "或分批导出；`--params '{\"extype\":\"simple\"}'` **不解除**该保护；"
                        "管理员可在 智能运维-内存管理-模板限制 中调整上限")
_EXPORT_ERROR_CODE_ADVICE = {
    "11300002": "该错误码实测为宽表/大行高超出分页导出的页面设置所致，"
                "加 `--params '{\"extype\":\"simple\"}'` 改原样导出后重试",
    "数据量过大": _MEMORY_GUARD_ADVICE,
    "模板限制": _MEMORY_GUARD_ADVICE,          # 同一段平台文案的另一种措辞；按下面的 seen 去重
}


def _export_error_page_suffix(text: str) -> str:
    """产物里带得出平台原因时拼成 `；平台原因: …`（读不出来返回空串）。"""
    reason = _html_error_reason(text)
    if not reason:
        return ""
    suffix = f"；平台原因: {reason}"
    seen = set()
    for key, advice in _EXPORT_ERROR_CODE_ADVICE.items():
        if key in reason and advice not in seen:
            seen.add(advice)
            suffix += f"；{advice}"
    return suffix


#: 产物头部读多少字节：**只用于**判断形态与魔数（出错页/排队页/正常产物）。
#: 有界读取，避免把几十 MB 的报表整体载入内存。
_MAGIC_HEAD_BYTES = 65536

#: 提取平台原因时出错页最多读多少字节。
#: ⚠️ 不能复用 `_MAGIC_HEAD_BYTES`：`detail-message` 里可能嵌**整段原始 SQL**，页面实测可达
#: 126KB（2026-10 真实会话：复杂报表导出撞 Impala 列名错误），64KB 内等不到 `</div>` ⇒
#: 平台原因整条丢失，用户只能自己去解 `.bad`。出错页本身不会很大，8MB 上限足够兜底。
_ERROR_PAGE_READ_BYTES = 8 * 1024 * 1024


def _read_head(path: Path) -> bytes:
    with open(path, "rb") as f:
        return f.read(_MAGIC_HEAD_BYTES)


def _read_error_page_text(path: Path) -> str:
    """读出错页全文（有界 8MB）用于提取 `detail-message` 平台原因。"""
    try:
        with open(path, "rb") as f:
            data = f.read(_ERROR_PAGE_READ_BYTES)
    except OSError:
        return ""
    return data.decode("utf-8", "replace")


#: 导出产物的魔数（用于把"200 + 出错页/排队页"挡在交付之前）。
#: ⚠️ word 目标是 RTF（`{\\rtf1`），不是 docx 的 PK —— 实测帆软 `format=word` 出 RTF，
#: 按 docx 的 PK 去校验会把好文件判成坏文件。
EXPORT_MAGIC = {
    "excel": (b"PK\x03\x04", "xlsx/docx(zip)"),
    "pdf": (b"%PDF", "pdf"),
    "image": (b"\x89PNG", "png"),
    "word": (b"{\\rtf1", "rtf"),
}


def _looks_like_html(resp) -> bool:
    """响应是不是平台的 HTML 页面（出错页），而不是正常的 XML/JSON 数据。"""
    ctype = resp.headers.get("content-type", "").lower()
    if "html" in ctype:
        return True
    head = resp.text.lstrip()[:64].lower()
    return head.startswith("<!doctype") or head.startswith("<html")


#: 出错页/排队页可能以 HTML 注释（`<!-- generated by ... -->`，可连续多个）或
#: XML 声明/处理指令（`<?xml version="1.0"?>`）开头 —— 形态判定要先剥掉这些前导标记与空白/BOM。
_LEADING_MARKUP_JUNK = re.compile(rb"^(?:\s|\xef\xbb\xbf|<!--.*?-->|<\?.*?\?>)+", re.S)


def _looks_like_html_head(head: bytes) -> bool:
    """产物**开头**是不是 HTML 形态（剥掉前导注释/PI/空白/BOM 后以 `<!doctype`/`<html` 开头）。

    ⚠️ 判据必须是"开头"，不能是"64KB 里出现过特征串"：合法产物（csv 备注列、报表正文）
    完全可能包含「出错页面」「Oops!!!」这类字样 —— 实测 CSV 第 201 行的备注写成
    `201,出错页面Oops` 就被 0.10.3 误杀并改名 .bad（0.10.2 的 512B 窗口看不到它）。
    平台出错页/排队页都是完整 HTML 文档，实测坏产物首字节就是 `<!do`。

    也不能只看第一个字节：出错页可能以 **HTML 注释**或 **XML 声明/PI** 开头
    （实测这两种形态 0.10.2 能拦、只看首字节会漏），所以先剥掉前导标记再看开头。
    """
    stripped = _LEADING_MARKUP_JUNK.sub(b"", head, count=1).lower()
    return stripped.startswith(b"<!doctype") or stripped.startswith(b"<html")


def assert_export_magic(path, fr_format: str):
    """导出产物必须对得上魔数，否则抛错（绝不把 HTML 出错页/排队页当报表交付）。

    csv/text 没有魔数可比，退化为"像不像 HTML 页面"判定 —— 实测 `export csv` 撞上
    `<RG>` 类名不存在这类错误时，**会把出错页原样写成 .csv**，肉眼像一份空报表。

    报错必须带上平台出错页的 `detail-message`（如 `错误代码:11300002 …`）：只报"是出错页"
    的话，用户得自己打开 `.bad` 文件才知道原因。
    """
    head = _read_head(path)
    # 出错页证据 = **开头是 HTML 形态** 且 命中结构标记/特征串（见 _HTML_ERROR_PAGE_MARKERS）。
    # ⚠ 两道条件缺一不可：只认"窗口里出现过特征串"会误杀合法 CSV（0.10.3 实测事故）。
    html_form = _looks_like_html_head(head)
    if html_form and any(m in head.lower() for m in _HTML_ERROR_PAGE_MARKERS):
        raise ExportError(f"导出产物是平台出错页，不是报表: {path}"
                          f"{_export_error_page_suffix(_read_error_page_text(path))}")
    if fr_format in ("text", "csv"):
        # csv/text 里任何 HTML 文档都不是报表数据；`Dec-Waiting_In_Line` 是平台内部标识，
        # 保留兜底（真实排队页是 HTML，export_report 里还有一次全文判定）。
        if html_form or b"dec-waiting_in_line" in head.lower():
            page_text = _read_error_page_text(path) if html_form else head.decode("utf-8", "replace")
            raise ExportError(
                f"导出产物是 HTML 页面（出错页/排队页），不是报表数据: {path}"
                f"{_export_error_page_suffix(page_text)}")
        return
    want = EXPORT_MAGIC.get(fr_format)
    if want and not head.startswith(want[0]) and want[0] not in head[:8]:
        raise ExportError(
            f"导出产物魔数不符（期望 {want[1]}）: {path}，头部={head[:24]!r}。"
            "常见原因：服务端返回出错页/排队页，或该格式的实际封装与预期不同"
            + _export_error_page_suffix(
                _read_error_page_text(path) if html_form else head.decode("utf-8", "replace")))


def _unwrap_json(resp: httpx.Response, what: str) -> Any:
    """解析决策平台 JSON 响应，出错时抛出平台给的真实原因。

    平台对参数错/无权限/方法不符一律返回 **200 + HTML 出错页**（不是 JSON），
    原因写在 `detail-message` 里（如 `Required String parameter 'keyword' is not
    present`、`Fine-Dec_No_Privilege_Access_Page`、`Unrecognized field "count"
    (8 known properties: ...)`）。直接当数据用会静默拿到错误页，所以这里翻译成异常。
    """
    if "json" in resp.headers.get("content-type", ""):
        try:
            return resp.json()
        except ValueError:
            # content-type 声明是 JSON，正文却是平台的 HTML 出错页 —— 直接 .json() 会抛
            # `Expecting value: line 1 column 1 (char 0)`，被包成 code=UNKNOWN，看不出原因。
            # 落到下面按出错页解析，把平台原文抛出来。
            pass
    reason = _html_error_reason(resp.text)
    if reason:
        raise ApiError(f"{what}失败: {reason}")
    raise ApiError(f"{what}失败: HTTP {resp.status_code}，响应不是 JSON")


# ========== 运行时巡检（模板性能分析插件 com.fr.plugin.ins） ==========
# 平台链路（2026-10 真机实测，服务端 10.0.19 + fr-plugin-inspection 1.3.4）：
#   ① GET /decision/plugin/inspect/x/run?viewlet=<模板>&op=page|view
#      返回预览页壳，里面 window.Nx.sid="<巡检会话id>"、sessionID=<模板会话uuid>
#   ② GET /decision/view/report?op=page_content&sessionID=<模板会话uuid>&pn=1
#      **真正触发模板计算**；少了这步巡检会话永远停在 PREPARED（结果页报「检测未被触发」）
#   ③ 轮询 GET /decision/plugin/inspect/x/report/<巡检sid>
#      页面里 Nx.result = JSON.parse('<JS 转义字符串>')，解一层才是分析 JSON
# 只读边界：op 只允许 page / view；write / write_plus 会触发填报写操作，禁止开放。
INSPECTION_STATUS_TEXT = {
    "0": "正常，所有检测点均生效",
    "1": "警告，部分检测点未生效",
    "2": "错误，关键检测点未生效",
    "-1": "稍候，检测点状态获取中",
    "-2": "错误，未知检测点状态",
}
_INSPECTION_SID_RE = re.compile(r'window\.Nx\.sid\s*=\s*"([^"]+)"')
_INSPECTION_SESSION_RE = re.compile(r"sessionID=([0-9a-fA-F-]{36})")
_INSPECTION_RESULT_START = re.compile(r"Nx\.result\s*=\s*JSON\.parse\('")

#: JS 字符串里不合法但会被平台写出的转义（JSON.parse 的入参之前要先解掉）
_JS_SIMPLE_ESCAPES = {
    '"': '"', "'": "'", "\\": "\\", "/": "/",
    "n": "\n", "r": "\r", "t": "\t", "b": "\b", "f": "\f",
}


def _js_unescape(raw: str) -> str:
    """解一层 JS 字符串转义（`\\/`→`/`、`\\'`→`'`、`\\uXXXX`→字符…）。

    平台把分析结果塞进 `JSON.parse('…')`，里面会带 `\\/` 这类 JSON 不认的转义，
    直接 `json.loads` 会报 `Invalid \\escape`。
    """
    out = []
    i = 0
    n = len(raw)
    while i < n:
        ch = raw[i]
        if ch != "\\":
            out.append(ch)
            i += 1
            continue
        nxt = raw[i + 1] if i + 1 < n else ""
        if nxt == "u":
            code = raw[i + 2:i + 6]
            try:
                out.append(chr(int(code, 16)))
            except ValueError:
                raise InspectionError(f"巡检结果里出现非法 Unicode 转义: \\u{code}")
            i += 6
            continue
        out.append(_JS_SIMPLE_ESCAPES.get(nxt, nxt))
        i += 2
    return "".join(out)


def decode_inspection_result(page: str) -> Optional[dict]:
    """从巡检结果页解出分析 JSON；还没出结果/是错误页时返回 None。

    结果页有两种写法，都要认：
    ① 正常：`Nx.result = JSON.parse('<JS 转义字符串>')`（当前版本实测）
    ② 兜底：`Nx.result = {...};`（直接 JSON，防插件改版）
    """
    match = _INSPECTION_RESULT_START.search(page or "")
    raw = None
    if match:
        i = match.end()
        buf = []
        n = len(page)
        while i < n:
            ch = page[i]
            if ch == "\\":
                buf.append(page[i:i + 2])
                i += 2
                continue
            if ch == "'":
                raw = "".join(buf)
                break
            buf.append(ch)
            i += 1
        if raw is None:
            raise InspectionError("巡检结果页不完整（Nx.result 字符串未闭合）")
        if not raw.strip():
            return None  # JSON.parse('')：还没写结果，继续轮询
    else:
        direct = re.search(r"Nx\.result\s*=\s*(\{.*?\})\s*;", page or "", re.S)
        if not direct:
            return None
        try:
            return json.loads(direct.group(1))
        except ValueError:
            return None
    try:
        parsed = json.loads(_js_unescape(raw))
    except ValueError as e:
        raise InspectionError(f"巡检结果解析失败：Nx.result 不是合法 JSON（{e}）") from e
    if not isinstance(parsed, dict):
        raise InspectionError(
            f"巡检结果格式异常：Nx.result 不是 JSON 对象（拿到 {type(parsed).__name__}）")
    return parsed


class FineReportClient:
    """FineReport HTTP API 客户端"""

    def __init__(self, config: ServerConfig):
        self.config = config
        self.base_url = config.url.rstrip("/")
        self.token_mgr = TokenManager(config)

        is_https = self.base_url.lower().startswith("https")
        timeout = float(os.environ.get("FRCLI_TIMEOUT", "30.0"))
        http_kwargs = {
            "base_url": self.base_url,
            "timeout": timeout,
            "follow_redirects": False,
        }
        if is_https:
            http_kwargs["verify"] = _configure_ssl()

        self._http = httpx.Client(**http_kwargs)
        self._authenticated = False
        self.relogged = False  # 本次会话是否因认证失效而重登过
        self.net_retries = 0   # 本次会话因连接层错误自动重发的次数（幂等 GET 才有）

    def _ensure_auth(self):
        """确保已认证，必要时自动登录"""
        if self._authenticated:
            return

        token = self.token_mgr.get_valid_token()
        if token:
            self._http.headers["Authorization"] = f"Bearer {token}"
            for name, value in self.token_mgr.get_cookies().items():
                self._http.cookies.set(name, value)
            self._authenticated = True
        else:
            token = self.token_mgr.login(self._http)
            self._http.headers["Authorization"] = f"Bearer {token}"
            self._authenticated = True

    def _send(self, method: str, path: str, **kwargs) -> httpx.Response:
        """发一次请求；连接层错误时按策略重发。

        - **只重试幂等方法**（GET/HEAD）：POST/PUT/DELETE 重放有风险（写操作可能被执行两次）。
        - **只重试 1 次，且超时/代理故障都不重试**：超时说明服务端还在算，重发只是把等待翻倍；
          代理链路故障也不是瞬时抖动（与登录跳口径一致）。
        - 有界且可观测：重试次数记在 `net_retries`，命令输出里可读。
        """
        attempts = 2 if method.upper() in ("GET", "HEAD") else 1
        for attempt in range(attempts):
            try:
                return self._http.request(method, path, **kwargs)
            except httpx.RequestError as e:
                # 可重试的只有"链路瞬时抖动"类：超时不重试（服务端还在算，重发只是把等待翻倍），
                # 代理故障也不重试（代理链路故障非瞬时，与登录跳口径一致）。
                retryable = (attempt + 1 < attempts
                             and not isinstance(e, (httpx.TimeoutException, httpx.ProxyError)))
                if retryable:
                    self.net_retries += 1
                    continue
                raise ConnectionError(f"请求失败: {_net_hint(e)}")

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        """带认证的请求方法：认证失效（401/403 或 302→CAS）自动重登一次。

        连接层错误的重试策略见 `_send`；重登后的那次请求同样受该策略约束。
        """
        self._ensure_auth()
        resp = self._send(method, path, **kwargs)

        if _is_auth_failure(resp):
            self._authenticated = False
            self.token_mgr.invalidate()
            self._http.cookies.clear()  # 丢掉服务端已失效的会话 cookie
            token = self.token_mgr.login(self._http)
            self._http.headers["Authorization"] = f"Bearer {token}"
            self._authenticated = True
            self.relogged = True
            resp = self._send(method, path, **kwargs)
            if _is_auth_failure(resp):
                raise AuthError(f"认证失败: 重新登录后仍被重定向到登录页 (HTTP {resp.status_code})")

        # 5xx 且带 `Proxy-Status` 指纹 → 这是代理返回的，不是平台的答复。
        # 指纹判定在 neterr.is_proxy_5xx（只认 Proxy-Status；`Via` 太宽会误判平台网关）。
        if is_proxy_5xx(resp):
            raise ConnectionError(f"请求失败: HTTP {resp.status_code}{_PROXY_HINT}")

        return resp

    def _get(self, path: str, **kwargs) -> httpx.Response:
        return self._request("GET", path, **kwargs)

    def _post(self, path: str, **kwargs) -> httpx.Response:
        return self._request("POST", path, **kwargs)

    # ========== 运行时巡检（模板性能分析） ==========

    def get_inspection_status(self) -> dict:
        """巡检插件状态（`GET /decision/plugin/inspect/status/get`）：检测点是否生效。"""
        self._ensure_auth()
        url = f"{self.config.workspace}/decision/plugin/inspect/status/get"
        resp = self._request("GET", url)
        if resp.status_code == 404:
            raise InspectionError(
                "巡检插件未安装/未启用（com.fr.plugin.ins）：接口 /plugin/inspect/status/get 返回 404")
        try:
            data = _unwrap_json(resp, "读取巡检状态")
        except ApiError as e:
            raise InspectionError(f"巡检插件不可用（com.fr.plugin.ins）：{e}") from e
        return data.get("data") or {}

    def run_inspection(self, report_path: str, op: str = "page", params: dict = None,
                       timeout: float = None) -> dict:
        """运行时巡检（模板性能分析）：真实执行一次模板计算，**内部等待结果就绪**后返回。

        - `op`：`page`（分页预览）/ `view`（分析预览，含数据源取数耗时）；禁止 write/write_plus（会写填报）。
        - `params`：模板参数（同 `export --params`），在发起巡检时就带上。
        - `timeout`：等待结果上限秒数；缺省读 `FRCLI_INSPECT_TIMEOUT`（60s）。
          模板计算本身仍受 `FRCLI_TIMEOUT` 约束（复杂模板记得调大）。
        - 返回完整的分析 JSON（`meta`/`extra`/`cell`），其中 `meta.para` 含账号与组织，
          命令层默认剔除，只有 `--raw` 才原样输出。
        """
        if op not in ("page", "view"):
            raise InspectionError(
                f"不支持的巡检类型: {op}（只允许 page / view；write / write_plus 会触发填报写操作）")
        wait_seconds = timeout if timeout is not None else float(
            os.environ.get("FRCLI_INSPECT_TIMEOUT", "60"))
        # NaN / inf / 负数会让「剩余时间」判断永不成立 → 死等；统一夹成 0（= 先 poll 一次再报超时）
        if not math.isfinite(wait_seconds) or wait_seconds < 0:
            wait_seconds = 0.0
        self._ensure_auth()

        # `--params` 是模板参数，**不能覆盖保留键**（否则 param op=write_plus/viewlet=… 会绕过只读白名单）
        run_params = dict(params or {})
        run_params["viewlet"] = report_path
        run_params["op"] = op
        run_url = f"{self.config.workspace}/decision/plugin/inspect/x/run"
        resp = self._request("GET", run_url, params=run_params)
        if resp.status_code == 404:
            raise InspectionError(
                "巡检插件未安装/未启用（com.fr.plugin.ins）：接口 /plugin/inspect/x/run 返回 404")
        if resp.status_code != 200:
            raise InspectionError(f"巡检请求失败: HTTP {resp.status_code}")
        sid_match = _INSPECTION_SID_RE.search(resp.text)
        session_match = _INSPECTION_SESSION_RE.search(resp.text)
        if not sid_match or not session_match:
            if not (resp.text or "").strip():
                # 实测：模板路径不存在时 run 返回 200 + 空响应（异常被平台吞掉，只进服务端日志）
                raise InspectionError(
                    "巡检没有启动：服务端返回空响应（模板路径不存在 / 无模板权限 / 插件异常）。"
                    "先用 `frcli report info <模板>` 或 `frcli report list <目录>` 确认路径")
            reason = _html_error_reason(resp.text)
            hint = f"；平台原因: {reason}" if reason else ""
            raise InspectionError(
                "巡检没有启动：返回页里找不到巡检会话 id（插件未启用 / 模板不存在 / 无模板权限）" + hint)
        sid = sid_match.group(1)
        template_session = session_match.group(1)

        # ② 真正触发模板计算：缺这步巡检会话永远停在 PREPARED（结果页报「检测未被触发」）
        content_url = f"{self.config.workspace}/decision/view/report"
        content = self._request(
            "GET", content_url,
            params={"op": "page_content", "sessionID": template_session, "pn": 1})
        if content.status_code != 200:
            raise InspectionError(f"巡检触发模板计算失败: HTTP {content.status_code}")

        # ③ 轮询结果（内部退避，调用方不需要 sleep / 猜时间）
        # 等待预算只算「轮询等待」：模板计算时间归 FRCLI_TIMEOUT 管（文档口径一致）
        started = time.monotonic()
        report_url = f"{self.config.workspace}/decision/plugin/inspect/x/report/{sid}"
        delay = 0.2
        last_reason = "巡检结果尚未生成"
        while True:
            poll = self._request("GET", report_url)
            if poll.status_code != 200:
                raise InspectionError(f"读取巡检结果失败: HTTP {poll.status_code}")
            result = decode_inspection_result(poll.text)
            if result is not None:
                return result
            text = poll.text or ""
            if "检测未被触发" in text:
                last_reason = ("会话仍停在「检测未被触发」——模板计算没有跑起来"
                               "（缺参数 / 模板报错 / 权限不足 / 插件未就绪）")
            elif "尚未完成" in text or "未完成" in text:
                last_reason = "巡检结果尚未生成"
            else:
                reason = _html_error_reason(text)
                last_reason = f"巡检返回异常页{('：' + reason) if reason else ''}"[:300]
            # 先轮询再判超时：至少发一次请求（结果通常第一次就有），避免 0 超时误判
            remaining = wait_seconds - (time.monotonic() - started)
            if remaining <= 0:
                raise InspectionError(
                    f"巡检结果等待超时（{wait_seconds:g}s，可用 FRCLI_INSPECT_TIMEOUT 调大）"
                    f"：{last_reason}")
            time.sleep(min(delay, max(remaining, 0)))
            delay = min(delay * 1.6, 1.0)

    # ========== 连接测试 ==========

    def test_connection(self) -> dict:
        """真实发一次认证请求验证连通性。

        只调 `_ensure_auth()` 不算数：本地缓存的 token 可能「未过期但已被服务端
        作废」，那样测试会假阳性报 ok，而列表命令全返回 `[]`（实测坑点）。
        """
        self._ensure_auth()
        url = f"{self.config.workspace}/decision/v10/schedule/task/names"
        resp = self._request("GET", url)
        if resp.status_code != 200:
            raise ConnectionError(f"连接测试失败: HTTP {resp.status_code}")
        return {
            "status": "connected",
            "http_status": resp.status_code,
            "relogin": self.relogged,
            "net_retries": self.net_retries,
        }

    # ========== 报表导出 ==========

    FORMAT_MAP = {
        "pdf": "pdf", "excel": "excel", "xlsx": "excel", "xls": "excel",
        "word": "word", "docx": "word", "doc": "word",
        "image": "image", "png": "image", "jpg": "image", "jpeg": "image",
        "csv": "csv", "txt": "text", "svg": "svg",
    }

    def export_report(self, report_path: str, format: str, output: str, params: dict = None) -> str:
        """导出报表到文件"""
        self._ensure_auth()
        fr_format = self.FORMAT_MAP.get(format.lower(), format)
        request_params = {"reportlet": report_path, "format": fr_format}
        if params:
            request_params.update(params)

        export_url = f"{self.config.workspace}/decision/view/report"
        # 走 _request：认证失效（本平台是 302 → CAS，不是 401）时自动重登并重试一次。
        # 直接 self._http.get 会跳过这层，表现为"导出失败: HTTP 302"，看着极像"模板坏了"
        # —— 实测批量导出跑一半时踩到过，5 个变体因此假阴性。
        try:
            resp = self._request("GET", export_url, params=request_params)
        except httpx.RequestError as e:
            raise ConnectionError(f"导出请求失败: {_net_hint(e)}")

        if resp.status_code != 200:
            if resp.status_code in (502, 503, 504):
                raise ExportError(
                    f"导出失败: HTTP {resp.status_code}（平台网关/上游超时或不可用，常见于服务端初始化/繁忙、"
                    "大报表并发导出）。先 `frcli server test` / `system health` 看平台状态；"
                    "单条稍后重试通常即成功，批量导出请降低并发；不要改报表参数")
            raise ExportError(f"导出失败: HTTP {resp.status_code}")

        # 平台在并发/限流时返回「排队中」页面而不是报表：200 + 2KB 左右 HTML，
        # 没有 <title>出错页面</title> 也没有 detail-message，只看状态码会当成功。
        if b"Dec-Waiting_In_Line" in resp.content or b"Waiting_In_Line" in resp.content:
            raise ExportError(
                "导出被服务端排队（返回 Dec-Waiting_In_Line 排队页，不是报表）。"
                "稍后重试一次通常即成功；批量导出请降低并发。")

        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("wb") as f:
            f.write(resp.content)
        try:
            assert_export_magic(output_path, fr_format)
        except ExportError as e:
            # 坏产物别留在原地冒充报表：改名保留（既是证据，也避免 agent 拿错文件）
            bad = output_path.with_name(output_path.name + ".bad")
            try:
                output_path.replace(bad)
            except OSError:
                bad = output_path
            raise ExportError(f"{e}；坏产物已改名保留在 {bad}") from e
        return str(output_path.resolve())

    # ========== 报表文件管理 ==========

    def list_reports(self, directory: str = "/", keyword: str = None,
                     file_types: str = None) -> list[dict]:
        """列出指定目录下的报表文件

        `keyword` / `file_types` 走**服务端筛选**（如 `keyword=烘焙`、`file_types=cpt`），
        比拉全量（`/` 实测 3873 条）再本地过滤省得多。

        只把「无数据」当空结果；认证与连接错误照常抛出，
        避免把未登录静默伪装成空目录（见 `_is_auth_failure`）。
        """
        self._ensure_auth()
        url = f"{self.config.workspace}/decision/v10/templates/all"
        params = {}
        if keyword:
            params["keyword"] = keyword
        if file_types:
            params["fileTypes[]"] = file_types
        resp = self._get(url, params=params or None)
        templates = _unwrap_json(resp, "列出报表").get("data", [])
        dir_prefix = directory.strip("/")
        result = []
        for t in templates:
            path = t.get("path", "")
            name = t.get("text", "")
            is_parent = t.get("isParent", False)
            if not dir_prefix:
                result.append({"name": name, "path": path, "is_directory": is_parent, "type": "directory" if is_parent else "report"})
            else:
                if path.startswith(dir_prefix):
                    relative = path[len(dir_prefix):].lstrip("/")
                    if "/" not in relative or is_parent:
                        result.append({"name": name, "path": path, "is_directory": is_parent, "type": "directory" if is_parent else "report"})
        return result

    def get_report_info(self, report_path: str) -> dict:
        """获取报表文件信息"""
        self._ensure_auth()
        import re
        url = f"{self.config.workspace}/decision/view/report"
        resp = self._get(url, params={"reportlet": report_path.lstrip("/"), "format": "cpt"})
        if resp.status_code != 200:
            raise ReportNotFoundError(f"无法读取报表: {report_path}")
        content = resp.text
        if "json" not in resp.headers.get("content-type", "") and _looks_like_html(resp):
            # 与 report datasets 一致：把平台原文（哪个数据集坏了、为什么）透出来，
            # 而不是只回一句没用的"无法读取报表定义"。
            _unwrap_json(resp, f"读取报表信息 {report_path}")
        info = {"path": report_path, "name": report_path.split("/")[-1], "datasets": [], "parameters": []}
        dataset_matches = re.findall(r'<TableData\s+name="([^"]+)"', content)
        info["datasets"] = [name.replace("&amp;", "&") for name in dataset_matches]
        param_matches = re.findall(r'<Attributes name="([^"]+)"/>', content)
        info["parameters"] = list(set(param_matches))
        # 上面的正则只能扒到「数据集里声明过」的参数名；只在
        # `ReportParameterAttr > Parameters` 里声明的模板参数它看不到（实测：恒为 []）。
        # 官方 paras 接口才是权威口径，取到就并进来（取不到不影响 info 本身）。
        try:
            official = self.get_report_paras(report_path)
            names = [p.get("name") for p in official
                     if isinstance(p, dict) and p.get("name")]
        except Exception:
            names = []
        if names:
            info["parameters"] = sorted(set(info["parameters"]) | set(names))
            info["parameters_from"] = "template/paras + 模板内 <Attributes>"
        return info

    def get_report_datasets(self, report_path: str) -> list[dict]:
        """获取报表的数据集定义。

        取不到定义时**必须报平台原文**：服务端只要有一个数据集坏掉，就整份 `format=cpt`
        返回出错页（而不是缺那一条），静默化成空列表会让人误判成"这张报表没有数据集"。
        出错页 `detail-message` 里通常直接写着坏数据集的名字与原因。
        """
        self._ensure_auth()
        import re
        url = f"{self.config.workspace}/decision/view/report"
        resp = self._get(url, params={"reportlet": report_path.lstrip("/"), "format": "cpt"})
        if resp.status_code != 200:
            raise ReportNotFoundError(f"无法读取报表: {report_path}")
        # 正常返回是 XML（模板定义）；只有拿到 HTML 页面才是出错页，这时把
        # detail-message 原文抛出来（通常直接写着哪个数据集坏了、为什么）。
        if _looks_like_html(resp):
            _unwrap_json(resp, f"读取报表数据集 {report_path}")
        content = resp.text
        datasets = []
        tabledata_pattern = r'<TableData\s+name="([^"]+)"[^>]*>(.*?)</TableData>'
        for match in re.finditer(tabledata_pattern, content, re.DOTALL):
            name = match.group(1).replace("&amp;", "&")
            section = match.group(2)
            params = re.findall(r'<Attributes name="([^"]+)"/>', section)
            sql = ""
            sql_match = re.search(r'<Query>.*?<!\[CDATA\[(.*?)\]\]>.*?</Query>', section, re.DOTALL)
            if sql_match:
                sql = sql_match.group(1).strip()
            # 连接名：只存在于模板 XML 的 <DatabaseName> 里（serverdatasets 列的是"服务器数据集"，
            # 完全不含数据库连接名）。不暴露它，用户就没法知道该往 --conn 里填什么 ——
            # 而填错的连接名**不会当场报错**，要等到查询期才失败。
            conn = ""
            conn_match = re.search(r'<DatabaseName>\s*<!\[CDATA\[(.*?)\]\]>\s*</DatabaseName>',
                                   section, re.DOTALL)
            if conn_match:
                conn = conn_match.group(1).strip()
            datasets.append({"name": name, "parameters": params, "sql": sql, "connection": conn})
        return datasets

    def get_report_paras(self, report_path: str) -> list[dict]:
        """获取报表参数定义（名称/类型/公式）。

        走官方接口 `report/template/paras`，比从 .cpt 模板里正则扒 `<Attributes>`
        更权威：派生参数的公式也能拿到（如 `edate_wow_td = FORMAT(TODATE($edate,...)-7,...)`）。
        """
        self._ensure_auth()
        url = f"{self.config.workspace}/decision/v10/report/template/paras"
        resp = self._get(url, params={"path": report_path.lstrip("/")})
        return _unwrap_json(resp, "读取报表参数").get("data", [])

    def download_report(self, remote_path: str, local_path: str = None) -> str:
        """下载模板**原始字节**（走远程设计通道 `WorkResource.readFully`）。

        ⚠️ 不要改用 `GET /decision/view/report?format=cpt`：那个端点返回的是
        **另一种序列化**（根元素 `<TableDataMap>`，缺 `<WorkBook>`/`<StyleList>`），
        与服务器上的文件字节不同 —— 实测同一模板 通道 4510B vs format=cpt 6362B，
        SHA256 不同。拿它回传会把模板写坏，而且回读校验还会通过（假阳性）。
        数据集定义请用 `report datasets`。
        """
        from .remotedesign import RemoteDesignSession, normalize_report_path

        remote = normalize_report_path(remote_path)
        with RemoteDesignSession(self.config) as session:
            session.check()
            data = session.read(remote)
        if not data:
            raise ReportNotFoundError(
                f"下载失败（服务端无此文件，或该路径不在账号的远程设计授权目录内）: {remote}")
        if b"<WorkBook" not in data[:600]:
            raise ReportNotFoundError(
                f"取回的内容不是 cpt 模板（前 600 字节没有 <WorkBook>）: {remote}")
        if local_path is None:
            local_path = remote_path.split("/")[-1]
        output = Path(local_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("wb") as f:
            f.write(data)
        return str(output.resolve())

    # ========== 定时任务 ==========

    def list_schedules(self) -> list[dict]:
        """列出所有定时任务名称（认证/连接错误照常抛出，不伪装成空列表）"""
        self._ensure_auth()
        url = f"{self.config.workspace}/decision/v10/schedule/task/names"
        resp = self._get(url)
        if resp.status_code != 200:
            return []
        try:
            names = resp.json().get("data", [])
        except ValueError:
            return []
        return [{"name": name} for name in names]

    def get_schedule(self, task_name: str) -> dict:
        """获取定时任务详情"""
        self._ensure_auth()
        url = f"{self.config.workspace}/decision/v10/schedule/task/search"
        resp = self._post(url, json={"taskName": task_name})
        if resp.status_code == 200:
            data = resp.json()
            items = data.get("data", {}).get("items", [])
            if items:
                return items[0]
        return {}

    def create_schedule(self, config: dict) -> str:
        """创建定时任务"""
        self._ensure_auth()
        url = f"{self.config.workspace}/decision/v10/schedule/task"
        resp = self._post(url, json=config)
        # 用 _unwrap_json：平台对"任务配置缺字段"等一律回 200 + HTML 出错页，
        # 裸 resp.json() 只会抛 `Expecting value…`（code=UNKNOWN），看不出真正原因。
        return str((_unwrap_json(resp, "创建定时任务") or {}).get("data", ""))

    def update_schedule(self, task_id: str, config: dict) -> bool:
        """更新定时任务"""
        self._ensure_auth()
        url = f"{self.config.workspace}/decision/v10/schedule/task"
        # 确保包含 id 字段，并移除只读字段
        update_data = config.copy()
        update_data["id"] = task_id
        for field in ["nextFireTime", "preFireTime", "creator", "editable", "taskState", "originTaskId"]:
            update_data.pop(field, None)
        resp = self._http.request("PUT", url, json=update_data, headers={"Authorization": f"Bearer {self.token_mgr.get_valid_token()}", "Content-Type": "application/json"})
        return resp.status_code == 200

    def get_schedule_history(self, task_name: str = None, limit: int = 10) -> list[dict]:
        """获取定时任务执行历史"""
        self._ensure_auth()
        url = f"{self.config.workspace}/decision/v10/schedule/task/log/info"
        body = {}
        if task_name:
            body["taskName"] = task_name
        resp = self._post(url, json=body)
        if resp.status_code == 200:
            data = resp.json()
            items = data.get("data", {}).get("items", [])
            return items[:limit]
        return []

    def search_schedule_records(self, task_name: str, page: int = 1, per_page: int = 20) -> dict:
        """按任务名检索执行记录（比 history 多运行结果与错误信息）

        返回 `{total, page, perPage, items}`；items 每项含 logTime / runType /
        logType / detailMessage / filePath / creator / taskId。
        """
        self._ensure_auth()
        url = f"{self.config.workspace}/decision/v10/schedule/record/search"
        resp = self._post(url, json={"taskName": task_name, "page": page, "perPage": per_page})
        data = _unwrap_json(resp, "查询执行记录").get("data") or {}
        return {
            "total": data.get("total", 0),
            "page": data.get("page", page),
            "perPage": per_page,
            "items": data.get("items", []),
        }

    def get_schedule_log_detail(self, task_log_id: str) -> dict:
        """获取单条调度日志的详情（节点树，逐节点状态与错误，用于定位失败原因）

        ⚠️ `task_log_id` 必须是 `schedule history <任务名>` 返回的 `id`
        （形如 `<任务名>_same_fire_<时间戳>`）；`schedule record` / `schedule records`
        里的 `uuid` / `id` 是**执行记录 id**，直接传进来平台会报「对象不存在」。
        """
        self._ensure_auth()
        url = f"{self.config.workspace}/decision/v10/schedule/task/log/details"
        resp = self._get(url, params={"taskLogId": task_log_id})
        try:
            return _unwrap_json(resp, "读取调度日志详情").get("data") or {}
        except ApiError as e:
            if "对象不存在" in str(e):
                raise ApiError(
                    f"{e}。logId 必须来自 `frcli schedule history <任务名>` 返回的 `id`"
                    "（形如 `<任务名>_same_fire_<时间戳>`）；`schedule record` / `schedule records` 里的"
                    " uuid/id 是执行记录 id，不能用于日志详情——请先用任务名查 history 取最新 id 再 log"
                ) from e
            raise

    # ========== 系统 / 平台信息（只读） ==========

    def get_server_version(self) -> list[dict]:
        """服务端版本 + 各模块 jar 版本（`GET /decision/system/version`）"""
        self._ensure_auth()
        resp = self._get(f"{self.config.workspace}/decision/system/version")
        return _unwrap_json(resp, "读取服务端版本").get("data", [])

    def get_server_health(self) -> list[dict]:
        """系统健康状态（`GET /decision/system/health`）"""
        self._ensure_auth()
        resp = self._get(f"{self.config.workspace}/decision/system/health")
        return _unwrap_json(resp, "读取系统健康").get("data", [])

    def get_decision_modules(self, keyword: str = None) -> list[dict]:
        """决策平台模块树（`GET /decision/v10/decision/modules`）"""
        self._ensure_auth()
        params = {"keyword": keyword} if keyword else None
        resp = self._get(f"{self.config.workspace}/decision/v10/decision/modules", params=params)
        return _unwrap_json(resp, "读取平台模块").get("data", [])

    def get_authority_config(self) -> dict:
        """权限开关（gradeAuth / editReportAuth / scheduleAuth…）"""
        self._ensure_auth()
        resp = self._get(f"{self.config.workspace}/decision/v10/authority/config")
        return _unwrap_json(resp, "读取权限配置").get("data") or {}

    def get_login_config(self) -> dict:
        """登录配置（超时 / 单点登录 / 找回密码开关）"""
        self._ensure_auth()
        resp = self._get(f"{self.config.workspace}/decision/login/config")
        return _unwrap_json(resp, "读取登录配置").get("data") or {}

    def get_password_strategy(self) -> dict:
        """密码策略（历史校验 / 复杂度）"""
        self._ensure_auth()
        resp = self._get(f"{self.config.workspace}/decision/login/password/strategy")
        return _unwrap_json(resp, "读取密码策略").get("data") or {}

    def get_password_warning_time(self) -> int:
        """密码到期提醒时间（天，-1 表示不提醒）"""
        self._ensure_auth()
        resp = self._get(f"{self.config.workspace}/decision/login/password/waring/time")
        return _unwrap_json(resp, "读取密码提醒").get("data")

    # ========== 平台条目 / 消息（只读） ==========

    def list_entries(self, page: int = 1, count: int = 20, keyword: str = "") -> dict:
        """平台条目分页（`GET /decision/v10/entries`，id 是 UUID）"""
        self._ensure_auth()
        resp = self._get(f"{self.config.workspace}/decision/v10/entries",
                         params={"page": page, "count": count, "keyword": keyword})
        return _unwrap_json(resp, "读取平台条目").get("data") or {}

    def get_entry_roots(self) -> list[dict]:
        """条目根节点（`GET /decision/v10/entry/roots`）"""
        self._ensure_auth()
        resp = self._get(f"{self.config.workspace}/decision/v10/entry/roots")
        return _unwrap_json(resp, "读取条目根节点").get("data", [])

    def get_all_entries(self) -> list[dict]:
        """全量平台条目（`GET /decision/v10/entries/all`）"""
        self._ensure_auth()
        resp = self._get(f"{self.config.workspace}/decision/v10/entries/all")
        return _unwrap_json(resp, "读取全量条目").get("data", [])

    def list_messages(self, unread: bool = False, page: int = 1, count: int = 20,
                      keyword: str = "") -> dict:
        """平台消息（unread=True 只取未读）"""
        self._ensure_auth()
        if unread:
            resp = self._get(f"{self.config.workspace}/decision/v10/message/unread")
        else:
            resp = self._get(f"{self.config.workspace}/decision/v10/message/list",
                             params={"page": page, "count": count, "keyword": keyword})
        return _unwrap_json(resp, "读取平台消息").get("data") or {}

    # ========== 用户 / 组织（只读） ==========

    def list_users(self) -> dict:
        """用户列表（`POST /decision/v10/users`；GET 版本服务端报错，实测不可用）。

        平台只返回**当前账号可见的用户**（实测 6 条，含工号 `username` 与姓名 `realName`），
        不是全量目录；按 id 查单个用户（`GET /v10/user/{id}`）需管理员权限，本账号不可用。
        """
        self._ensure_auth()
        resp = self._post(f"{self.config.workspace}/decision/v10/users", json={})
        return _unwrap_json(resp, "读取用户列表").get("data") or {}

    def get_current_user(self) -> dict:
        """当前登录账号的信息（工号 / 姓名 / 邮箱 / 手机 / 角色 id）"""
        self._ensure_auth()
        resp = self._get(f"{self.config.workspace}/decision/v10/user/account")
        return _unwrap_json(resp, "读取当前用户").get("data") or {}

    def list_departments(self, keyword: str = "") -> list[dict]:
        """部门树（`GET /decision/v10/departments`）"""
        self._ensure_auth()
        resp = self._get(f"{self.config.workspace}/decision/v10/departments",
                         params={"keyword": keyword})
        return _unwrap_json(resp, "读取部门").get("data", [])

    def list_posts(self, keyword: str = "") -> list[dict]:
        """岗位列表（`GET /decision/v10/posts`）"""
        self._ensure_auth()
        resp = self._get(f"{self.config.workspace}/decision/v10/posts",
                         params={"keyword": keyword})
        return _unwrap_json(resp, "读取岗位").get("data", [])

    # ========== 服务器数据集元数据（只读） ==========

    def list_server_datasets(self) -> list[dict]:
        """服务器数据集清单（`GET /decision/v10/serverdatasets`）"""
        self._ensure_auth()
        resp = self._get(f"{self.config.workspace}/decision/v10/serverdatasets")
        return _unwrap_json(resp, "读取服务器数据集").get("data", [])

    def get_dataset_columns(self, dataset_name: str) -> list[dict]:
        """服务器数据集的字段清单（列名/列类型）"""
        self._ensure_auth()
        resp = self._get(f"{self.config.workspace}/decision/v10/{dataset_name}/datasetcolumns")
        return _unwrap_json(resp, "读取数据集字段").get("data", [])

    def get_authenticated_templates(self, keyword: str = None) -> list[dict]:
        """模板「认证(authentication)配置」路由的原始返回（`GET …/report/templates/all/authentication`）。

        这是模板认证配置路由，**不是**「当前账号有权限的模板树」：实测恒返回 `[]`（HTTP 200 的
        原始响应即 `{"data":[]}`），与权限无关；枚举有权限的模板树用 `list_reports()`。
        """
        self._ensure_auth()
        params = {"keyword": keyword} if keyword else None
        resp = self._get(
            f"{self.config.workspace}/decision/v10/report/templates/all/authentication",
            params=params)
        return _unwrap_json(resp, "读取有权限模板树").get("data", [])

    # ========== 调度增强（只读） ==========

    def list_schedule_tasks(self, page: int = 1, count: int = 20, all_tasks: bool = False,
                            privilege_type: int = 2) -> dict:
        """任务列表（带 taskId）。all_tasks=True 走 listAll（不分页，全量返回）。"""
        self._ensure_auth()
        base = f"{self.config.workspace}/decision/v10/schedule/task"
        if all_tasks:
            resp = self._get(f"{base}/listAll/{privilege_type}")
            return {"items": _unwrap_json(resp, "读取任务列表").get("data", [])}
        resp = self._get(f"{base}/list/{privilege_type}",
                         params={"page": page, "count": count})
        return _unwrap_json(resp, "读取任务列表").get("data") or {}

    def schedule_task_exists(self, task_name: str) -> bool:
        """任务是否存在（按准确任务名，`GET …/task/{name}/exists`）"""
        self._ensure_auth()
        resp = self._get(
            f"{self.config.workspace}/decision/v10/schedule/task/{task_name}/exists")
        return bool(_unwrap_json(resp, "查询任务是否存在").get("data"))

    def get_executing_tasks(self) -> list[dict]:
        """当前正在执行的调度任务"""
        self._ensure_auth()
        resp = self._get(f"{self.config.workspace}/decision/v10/schedule/executing")
        return _unwrap_json(resp, "读取执行中任务").get("data", [])

    def get_executing_info(self) -> str:
        """调度线程池忙碌情况（BusyWorker）"""
        self._ensure_auth()
        resp = self._get(f"{self.config.workspace}/decision/v10/schedule/info/executing")
        return _unwrap_json(resp, "读取调度忙碌信息").get("data")

    def list_all_schedule_records(self, page: int = 1, per_page: int = 20) -> dict:
        """全平台执行记录（分页，total 十万级）"""
        self._ensure_auth()
        resp = self._get(f"{self.config.workspace}/decision/v10/schedule/record/list",
                         params={"page": page, "perPage": per_page})
        data = _unwrap_json(resp, "读取执行记录").get("data") or {}
        return {"total": data.get("total", 0), "page": data.get("page", page),
                "perPage": per_page, "items": data.get("items", [])}

    def get_schedule_settings(self) -> dict:
        """调度全局设置（短信/邮件/平台消息开关、日志清理时间）"""
        self._ensure_auth()
        resp = self._get(f"{self.config.workspace}/decision/v10/schedule/setting")
        return _unwrap_json(resp, "读取调度设置").get("data") or {}

    # ========== 附件（服务器附件缓存，非报表目录） ==========

    def upload_attach(self, local_path: str, filename: str = None,
                      width: int = 0, height: int = 0) -> dict:
        """上传本地文件到服务器附件缓存，返回 `{attach_id, attach_type, filename}`。

        multipart 字段名固定为 `file`（实测）；`width`/`height` 供图片用，非图片传 0。
        上传物只落在附件缓存里，**不会进报表目录**（改模板内容仍无 REST 通道）。
        """
        self._ensure_auth()
        url = f"{self.config.workspace}/decision/v10/attach/upload"
        path = Path(local_path)
        with open(path, "rb") as fh:
            resp = self._post(
                url,
                params={"version": "v10", "width": width, "height": height,
                        "filename": filename or path.name, "isHolder": "false"},
                files={"file": (filename or path.name, fh)},
            )
        return _unwrap_json(resp, "上传附件")

    def remove_attach(self, attach_id: str) -> bool:
        """删除服务器上的附件（配合 upload 清理干净）"""
        self._ensure_auth()
        url = f"{self.config.workspace}/decision/v10/attach/remove/{attach_id}"
        resp = self._request("DELETE", url)
        _unwrap_json(resp, "删除附件")
        return True

    def delete_schedule(self, task_id: str) -> bool:
        """删除定时任务

        平台要的是**裸 JSON 数组** `["<id>"]`，不是 `{"ids": [...]}` —— 传对象会回
        200 + HTML 出错页（`Cannot deserialize instance of [Ljava.lang.String; out of
        START_OBJECT`）。旧实现只看 HTTP 状态码，把「没删掉」报成 `deleted: true`。
        这里按平台真实语义发裸数组，并用 `_unwrap_json` 校验，避免假成功。
        """
        self._ensure_auth()
        url = f"{self.config.workspace}/decision/v10/schedule/task/deletes"
        resp = self._post(url, json=[task_id])
        payload = _unwrap_json(resp, "删除定时任务")
        return str((payload or {}).get("data", "")).lower() == "success"

    def execute_schedule(self, task_id: str) -> dict:
        """立即执行定时任务"""
        self._ensure_auth()
        url = f"{self.config.workspace}/decision/v10/schedule/task/{task_id}/once"
        resp = self._post(url)
        if resp.status_code == 200:
            return resp.json()
        return {"error": "执行失败"}

    def close(self):
        self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
