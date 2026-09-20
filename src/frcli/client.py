"""FineReport HTTP API 客户端"""

import json
import re
import html
import ssl
import os
from typing import Optional, Any
from pathlib import Path
import httpx
from .config import ServerConfig
from .auth import TokenManager
from .exceptions import (
    FrcliError, AuthError, ConnectionError,
    ReportNotFoundError, ExportError, ApiError
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


_HTML_ERROR_MSG = re.compile(r'id="(detail-message|simple-message)"[^>]*>(.*?)</div>', re.S)

# 平台出错页里的本地化 key，翻成人话（detail-message 为空时只剩它们）
_LOCALE_TEXT = {
    "Fine-Dec_No_Privilege_Access_Page": "当前账号无此接口权限（该接口需管理员）",
    "Fine-Dec_Default_Error_Tip": "平台返回错误页（无详细信息，通常是对象不存在）",
}


def _unwrap_json(resp: httpx.Response, what: str) -> Any:
    """解析决策平台 JSON 响应，出错时抛出平台给的真实原因。

    平台对参数错/无权限/方法不符一律返回 **200 + HTML 出错页**（不是 JSON），
    原因写在 `detail-message` 里（如 `Required String parameter 'keyword' is not
    present`、`Fine-Dec_No_Privilege_Access_Page`、`Unrecognized field "count"
    (8 known properties: ...)`）。直接当数据用会静默拿到错误页，所以这里翻译成异常。
    """
    if "json" in resp.headers.get("content-type", ""):
        return resp.json()
    reason = ""
    for match in _HTML_ERROR_MSG.finditer(resp.text):
        text = html.unescape(re.sub(r"<[^>]+>", "", match.group(2))).strip()
        if text and (match.group(1) == "detail-message" or not reason):
            reason = text
        if match.group(1) == "detail-message" and text:
            break
    reason = _LOCALE_TEXT.get(reason, reason)
    if reason:
        raise ApiError(f"{what}失败: {reason}")
    raise ApiError(f"{what}失败: HTTP {resp.status_code}，响应不是 JSON")


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

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        """带认证的请求方法：认证失效（401/403 或 302→CAS）自动重登一次"""
        self._ensure_auth()
        try:
            resp = self._http.request(method, path, **kwargs)
        except httpx.RequestError as e:
            raise ConnectionError(f"请求失败: {e}")

        if _is_auth_failure(resp):
            self._authenticated = False
            self.token_mgr.invalidate()
            self._http.cookies.clear()  # 丢掉服务端已失效的会话 cookie
            token = self.token_mgr.login(self._http)
            self._http.headers["Authorization"] = f"Bearer {token}"
            self._authenticated = True
            self.relogged = True
            try:
                resp = self._http.request(method, path, **kwargs)
            except httpx.RequestError as e:
                raise ConnectionError(f"请求失败: {e}")
            if _is_auth_failure(resp):
                raise AuthError(f"认证失败: 重新登录后仍被重定向到登录页 (HTTP {resp.status_code})")

        return resp

    def _get(self, path: str, **kwargs) -> httpx.Response:
        return self._request("GET", path, **kwargs)

    def _post(self, path: str, **kwargs) -> httpx.Response:
        return self._request("POST", path, **kwargs)

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
        try:
            resp = self._http.get(export_url, params=request_params)
        except httpx.RequestError as e:
            raise ConnectionError(f"导出请求失败: {e}")

        if resp.status_code != 200:
            raise ExportError(f"导出失败: HTTP {resp.status_code}")

        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(resp.content)
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
        if "Oops" in content or "找不到数据连接" in content:
            return {"path": report_path, "name": report_path.split("/")[-1], "error": "无法读取报表定义"}
        info = {"path": report_path, "name": report_path.split("/")[-1], "datasets": [], "parameters": []}
        dataset_matches = re.findall(r'<TableData\s+name="([^"]+)"', content)
        info["datasets"] = [name.replace("&amp;", "&") for name in dataset_matches]
        param_matches = re.findall(r'<Attributes name="([^"]+)"/>', content)
        info["parameters"] = list(set(param_matches))
        return info

    def get_report_datasets(self, report_path: str) -> list[dict]:
        """获取报表的数据集定义"""
        self._ensure_auth()
        import re
        url = f"{self.config.workspace}/decision/view/report"
        resp = self._get(url, params={"reportlet": report_path.lstrip("/"), "format": "cpt"})
        if resp.status_code != 200:
            raise ReportNotFoundError(f"无法读取报表: {report_path}")
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
            datasets.append({"name": name, "parameters": params, "sql": sql})
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
        """下载报表模板"""
        self._ensure_auth()
        url = f"{self.config.workspace}/decision/view/report"
        resp = self._get(url, params={"reportlet": remote_path.lstrip("/"), "format": "cpt"})
        if resp.status_code != 200:
            raise ReportNotFoundError(f"下载失败: {remote_path}")
        if "Oops" in resp.text or "error" in resp.text.lower():
            raise ReportNotFoundError(f"下载失败（无权限或文件不存在）: {remote_path}")
        if local_path is None:
            local_path = remote_path.split("/")[-1]
        output = Path(local_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        with open(output, "wb") as f:
            f.write(resp.content)
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
        if resp.status_code == 200:
            data = resp.json()
            return data.get("data", "")
        return ""

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
        """获取单条调度日志的详情（节点树，逐节点状态与错误，用于定位失败原因）"""
        self._ensure_auth()
        url = f"{self.config.workspace}/decision/v10/schedule/task/log/details"
        resp = self._get(url, params={"taskLogId": task_log_id})
        return _unwrap_json(resp, "读取调度日志详情").get("data") or {}

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
        """当前账号有权限的模板树（`GET /decision/v10/report/templates/all/authentication`）"""
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
