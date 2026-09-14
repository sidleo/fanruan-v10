"""FineReport HTTP API 客户端"""

import json
import ssl
import os
from typing import Optional, Any
from pathlib import Path
import httpx
from .config import ServerConfig
from .auth import TokenManager
from .exceptions import (
    FrcliError, AuthError, ConnectionError,
    ReportNotFoundError, ExportError
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
        """带认证的请求方法"""
        self._ensure_auth()
        try:
            resp = self._http.request(method, path, **kwargs)
        except httpx.RequestError as e:
            raise ConnectionError(f"请求失败: {e}")

        if resp.status_code == 401 or resp.status_code == 403:
            self._authenticated = False
            self.token_mgr.invalidate()
            token = self.token_mgr.login(self._http)
            self._http.headers["Authorization"] = f"Bearer {token}"
            self._authenticated = True
            resp = self._http.request(method, path, **kwargs)

        return resp

    def _get(self, path: str, **kwargs) -> httpx.Response:
        return self._request("GET", path, **kwargs)

    def _post(self, path: str, **kwargs) -> httpx.Response:
        return self._request("POST", path, **kwargs)

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

    def list_reports(self, directory: str = "/") -> list[dict]:
        """列出指定目录下的报表文件"""
        self._ensure_auth()
        url = f"{self.config.workspace}/decision/v10/templates/all"
        try:
            resp = self._get(url)
            if resp.status_code == 200:
                data = resp.json()
                templates = data.get("data", [])
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
            return []
        except Exception:
            return []

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
        """列出所有定时任务名称"""
        self._ensure_auth()
        url = f"{self.config.workspace}/decision/v10/schedule/task/names"
        try:
            resp = self._get(url)
            if resp.status_code == 200:
                data = resp.json()
                names = data.get("data", [])
                return [{"name": name} for name in names]
            return []
        except Exception:
            return []

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

    def delete_schedule(self, task_id: str) -> bool:
        """删除定时任务"""
        self._ensure_auth()
        url = f"{self.config.workspace}/decision/v10/schedule/task/deletes"
        resp = self._post(url, json={"ids": [task_id]})
        return resp.status_code == 200

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
