"""传输层错误分类与提示（**中性模块**：client.py 与 auth.py 共用同一份文案）。

为什么单独成模块：`client.py` 依赖 `auth.py`（`TokenManager`），把提示逻辑留在 client.py 里
auth.py 就无法复用（反向 import 成环）。而「请求这一跳」与「登录这一跳」面对的是同一条链路，
**必须给出完全一致**的处置建议 —— 否则无 token 缓存时登录先失败，用户看到的还是裸报
`登录请求失败: 503 Service Unavailable`（看不出是代理/超时/被重置）。

只做**分类与文案**，不发请求、不重试、不改代理设置。
"""

import os

import httpx

#: 连接被对端中断（**不是超时**）的文本特征。实测 `[Errno 54] Connection reset by peer`
#: 曾被归进超时提示，用户照提示把 FRCLI_TIMEOUT 从 900 一路调到 1800，照样被 reset。
CONN_RESET_MARKERS = (
    "connection reset", "reset by peer", "broken pipe", "connection aborted",
    "server disconnected", "remote end closed", "connection was forcibly closed",
    "unexpected eof", "eof occurred",
)

#: 传输层失败发生在**本机 HTTP 代理这一跳**时的提示（`httpx.ProxyError`，或响应带 `Proxy-Status`）。
#: 5xx 是代理返回的，平台的会话/参数都没问题——旧文案把人引向"确认会话/调大超时"，看不出真正断点。
PROXY_HINT = (
    "（本机 HTTP 代理链路故障：httpx.ProxyError 抛错，或响应带 `Proxy-Status` 头，"
    "都表示失败发生在「代理这一跳」——代理拒绝了到平台的连接，或代理自身返回了 5xx。"
    "这不是平台返回的业务错误，也不是超时。"
    "排查顺序：(1) 代理/VPN 客户端是否在运行、节点是否需要切换；"
    "(2) `curl -I <平台地址>` 不走代理直连对照（同样失败即链路问题，平台本身可能正常）；"
    "(3) 确认代理可用后原样重试。不必改报表参数，也不必调大 FRCLI_TIMEOUT。"
    "`frcli server test` 也走同一代理，只能用来复核；"
    "如需绕过本机代理，请自行在 NO_PROXY 里排除平台地址后重试。）"
)


def is_transport_error(e: Exception) -> bool:
    """是不是 httpx 的传输层错误（连接/超时/代理/协议）。

    只给这类错误加网络处置提示：登录路径里同一段 `try` 还包着 `resp.json()` 与 token 落盘，
    那些失败（ValueError / OSError）不该被套上"调大超时/查代理"的话术。
    """
    return isinstance(e, httpx.RequestError)


def is_conn_reset(e: Exception, text: str) -> bool:
    """是不是「连接被对端重置/断开」——这类错误原样重试即可能成功，与超时无关。"""
    if isinstance(e, httpx.TimeoutException):
        return False
    low = text.lower()
    if any(marker in low for marker in CONN_RESET_MARKERS):
        return True
    return isinstance(e, (httpx.ReadError, httpx.WriteError, httpx.RemoteProtocolError))


def is_proxy_5xx(resp) -> bool:
    """5xx 响应是不是**代理返回**的（而不是平台的答复）。

    只看 `Proxy-Status` 响应头（RFC 9209：代理自报处理结果，返回 5xx 时必然带它）。
    ⚠️ 不认 `Via` —— 平台侧网关/中间层也常加 `Via`，用它判定会把平台自身 5xx 说成
    "本机代理链路故障"。**没有显式指纹就按平台 5xx 处理**，宁可少报也不误报。

    请求跳（`client._request`）与登录跳（`auth.TokenManager.login`）共用。
    """
    return resp.status_code >= 500 and bool(resp.headers.get("proxy-status"))


def net_hint(e: Exception, timeout_env: str = "FRCLI_TIMEOUT",
             timeout_default: str = "30.0") -> str:
    """网络类异常的**可操作**提示。

    默认超时 30s 对真实报表偏短（复杂模板实测要 300~900s），而这个报错原文只有
    `The read operation timed out`，看不出"只是超时、调大就行" —— 2026-09 两个会话
    都在这里反复试参数、怀疑报表有问题。所以直接把当前值与调法写进消息。

    三类要分开：**超时**（调大对应超时变量）、**连接被重置/断开**（原样重试，调超时无用）、
    **本机代理故障**（查代理/VPN 链路，与平台会话无关）。混成一句会把人带沟里。

    请求路径（`client._request`）与登录路径（`auth.TokenManager.login`）共用本函数，
    保证同一故障在两处给出同一份建议；**远程设计通道**（`remotedesign.py`）也走这里，
    但它的超时是独立变量（`timeout_env="FRCLI_RD_TIMEOUT"`、默认 300s）—— 用错变量会让人
    调 `FRCLI_TIMEOUT` 却毫无效果。
    """
    cur = os.environ.get(timeout_env, timeout_default)
    text = str(e)
    if isinstance(e, httpx.ProxyError):
        # 既有请求跳/登录跳的代理文案必须逐字符不变；只有 RD 等非默认超时变量才替换变量名
        hint = PROXY_HINT if timeout_env == "FRCLI_TIMEOUT" else PROXY_HINT.replace("FRCLI_TIMEOUT", timeout_env)
        return f"{text}{hint}"
    if isinstance(e, httpx.TimeoutException) or "timed out" in text.lower():
        return (f"{text}（当前超时 {cur}s；复杂报表属正常，用 `{timeout_env}=600 frcli ...` 调大后原样重试，"
                f"不要先怀疑报表或改参数）")
    if is_conn_reset(e, text):
        return (f"{text}（连接被对端重置/断开，这不是超时——调大 {timeout_env} 无效。"
                f"同一命令原样重试通常即成功（服务端渲染大报表耗时较长时偶发被掐断）；"
                f"批量导出里失败的那几条单独重试即可，先别改参数、也别怀疑报表。"
                f"反复出现再查链路：本机代理/VPN 是否稳定、服务端是否限连接数）")
    return (f"{text}（当前超时 {cur}s；若为连接类问题先 `frcli server test` 确认会话，"
            f"必要时 `{timeout_env}=600` 调大重试）")
