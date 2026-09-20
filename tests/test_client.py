"""客户端模块测试"""

import httpx
import pytest
from frcli.models import ServerConfig
from frcli.client import FineReportClient, _is_auth_failure, _unwrap_json
from frcli.exceptions import AuthError, ApiError


def test_client_init():
    """测试客户端初始化"""
    config = ServerConfig(
        name="test",
        url="http://localhost:8705",
        username="admin",
    )
    client = FineReportClient(config)
    assert client.base_url == "http://localhost:8705"
    client.close()


def test_client_context_manager():
    """测试上下文管理器"""
    config = ServerConfig(
        name="test",
        url="http://localhost:8705",
        username="admin",
    )
    with FineReportClient(config) as client:
        assert client is not None


def _mock_client(handler) -> FineReportClient:
    """构造一个用 MockTransport 的客户端，避免真实网络与落盘缓存"""
    config = ServerConfig(
        name="test",
        url="http://localhost:8705",
        username="admin",
        password="pwd",
    )
    client = FineReportClient(config)
    client._http.close()
    client._http = httpx.Client(
        base_url="http://localhost:8705",
        transport=httpx.MockTransport(handler),
        follow_redirects=False,
    )
    client.token_mgr.get_valid_token = lambda: "stale-token"
    client.token_mgr._save_cached_token = lambda *a, **k: None
    return client


def test_auth_failure_detects_cas_redirect():
    """本服务器失效 token 不用 401，而是 302 到 CAS 登录页（实测）"""
    assert _is_auth_failure(httpx.Response(401))
    assert _is_auth_failure(httpx.Response(403))
    assert _is_auth_failure(
        httpx.Response(302, headers={"location": "https://sso.example.com/cas/login?service=x"})
    )


def test_auth_failure_ignores_normal_responses():
    """普通响应（含非登录用途的重定向）不得误判为认证失效"""
    assert not _is_auth_failure(httpx.Response(200))
    assert not _is_auth_failure(
        httpx.Response(302, headers={"location": "https://fr.example.com/webroot/decision/home"})
    )


def test_list_reports_relogins_on_cas_redirect():
    """回归：缓存 token 失效时必须重登重试，而不是静默返回 []"""
    paths = []

    def handler(request):
        paths.append(request.url.path)
        if request.url.path.endswith("/decision/login"):
            return httpx.Response(200, json={"data": {"accessToken": "fresh-token"}})
        if request.url.path.endswith("/decision/v10/templates/all"):
            if paths.count("/webroot/decision/v10/templates/all") == 1:
                return httpx.Response(
                    302,
                    headers={"location": "https://sso.example.com/cas/login?service=x"},
                )
            return httpx.Response(
                200, json={"data": [{"path": "a/b.cpt", "text": "b.cpt", "isParent": False}]}
            )
        return httpx.Response(404)

    client = _mock_client(handler)
    try:
        reports = client.list_reports("/")
    finally:
        client.close()

    assert [r["name"] for r in reports] == ["b.cpt"]
    assert client.relogged is True
    assert "/webroot/decision/login" in paths


def test_list_schedules_raises_when_relogin_still_redirects():
    """重登后仍被踢回登录页：报错，不能伪装成空列表"""

    def handler(request):
        if request.url.path.endswith("/decision/login"):
            return httpx.Response(200, json={"data": {"accessToken": "fresh-token"}})
        return httpx.Response(
            302, headers={"location": "https://sso.example.com/cas/login?service=x"}
        )

    client = _mock_client(handler)
    try:
        with pytest.raises(AuthError):
            client.list_schedules()
    finally:
        client.close()


_HTML_ERR = (
    '<html><body><div class="simple-message" id="simple-message">Fine-Dec_Default_Error_Tip</div>'
    '<div class="detail-message" id="detail-message">{}</div></body></html>'
)


def test_unwrap_json_passes_json_through():
    assert _unwrap_json(httpx.Response(200, json={"data": [1]}), "测试") == {"data": [1]}


def test_unwrap_json_raises_with_platform_reason():
    """平台出错返回 200 + HTML 出错页，detail-message 才是真实原因"""
    resp = httpx.Response(
        200,
        headers={"content-type": "text/html;charset=UTF-8"},
        text=_HTML_ERR.format("Required String parameter &#39;keyword&#39; is not present"),
    )
    with pytest.raises(ApiError) as exc:
        _unwrap_json(resp, "读取报表参数")
    assert "keyword" in str(exc.value)
    assert exc.value.code == "API_ERROR"


def test_unwrap_json_translates_locale_key_when_detail_empty():
    """detail-message 为空时退到 simple-message 的本地化 key，并翻成人话"""
    resp = httpx.Response(
        200, headers={"content-type": "text/html;charset=UTF-8"}, text=_HTML_ERR.format("")
    )
    with pytest.raises(ApiError) as exc:
        _unwrap_json(resp, "读取调度日志详情")
    assert "Fine-Dec_Default_Error_Tip" not in str(exc.value)
    assert "错误页" in str(exc.value)


def test_get_report_paras_sends_path_param():
    seen = {}

    def handler(request):
        seen["path"] = request.url.params.get("path")
        return httpx.Response(200, json={"data": [{"name": "edate", "type": "Formula", "value": "x"}]})

    client = _mock_client(handler)
    try:
        paras = client.get_report_paras("/demo_group/某某/报表.cpt")
    finally:
        client.close()

    assert seen["path"] == "demo_group/某某/报表.cpt"  # 前导 / 被去掉
    assert paras == [{"name": "edate", "type": "Formula", "value": "x"}]


def test_search_schedule_records_shape_and_body():
    import json as _json

    seen = {}

    def handler(request):
        seen["body"] = _json.loads(request.content)
        return httpx.Response(
            200, json={"data": {"total": 67, "page": 2, "items": [{"taskName": "t"}]}}
        )

    client = _mock_client(handler)
    try:
        result = client.search_schedule_records("t", page=2, per_page=5)
    finally:
        client.close()

    assert seen["body"] == {"taskName": "t", "page": 2, "perPage": 5}
    assert result["total"] == 67 and result["page"] == 2 and result["perPage"] == 5
    assert result["items"] == [{"taskName": "t"}]


def test_upload_attach_posts_multipart_file_field(tmp_path):
    """附件上传：multipart 字段名必须是 file，且带 version/width/height/filename 参数"""
    seen = {}

    def handler(request):
        seen["method"] = request.method
        seen["params"] = dict(request.url.params)
        seen["body"] = request.content
        return httpx.Response(
            200, json={"attach_type": "other", "attach_id": "default1_x", "filename": "a.txt"}
        )

    local = tmp_path / "a.txt"
    local.write_bytes(b"hello-attach")
    client = _mock_client(handler)
    try:
        info = client.upload_attach(str(local))
    finally:
        client.close()

    assert seen["method"] == "POST"
    assert seen["params"]["version"] == "v10"
    assert seen["params"]["filename"] == "a.txt"
    assert seen["params"]["isHolder"] == "false"
    assert b'name="file"' in seen["body"]
    assert b"hello-attach" in seen["body"]
    assert info["attach_id"] == "default1_x"


def test_remove_attach_sends_delete():
    seen = {}

    def handler(request):
        seen["method"] = request.method
        seen["path"] = request.url.path
        return httpx.Response(200, json={"data": "success"})

    client = _mock_client(handler)
    try:
        assert client.remove_attach("abc_123") is True
    finally:
        client.close()

    assert seen["method"] == "DELETE"
    assert seen["path"].endswith("/decision/v10/attach/remove/abc_123")


def test_delete_schedule_posts_bare_id_array():
    """平台要裸数组 `["<id>"]`；传 {"ids": [...]} 会被拒且旧实现误报成功"""
    seen = {}

    def handler(request):
        seen["method"] = request.method
        seen["path"] = request.url.path
        seen["body"] = request.content.decode()
        return httpx.Response(200, json={"data": "success"})

    client = _mock_client(handler)
    try:
        assert client.delete_schedule("abcd-1234") is True
    finally:
        client.close()

    assert seen["method"] == "POST"
    assert seen["path"].endswith("/decision/v10/schedule/task/deletes")
    assert seen["body"] == '["abcd-1234"]'


def test_delete_schedule_raises_on_platform_error_page():
    """平台删除失败回 200 + HTML 出错页，必须抛错而不是返回 True"""

    def handler(request):
        return httpx.Response(
            200,
            headers={"content-type": "text/html;charset=UTF-8"},
            text=_HTML_ERR.format(
                "Could not read JSON: Cannot deserialize instance of "
                "`[Ljava.lang.String;` out of START_OBJECT token"
            ),
        )

    client = _mock_client(handler)
    try:
        with pytest.raises(ApiError) as exc:
            client.delete_schedule("abcd-1234")
    finally:
        client.close()

    assert "START_OBJECT" in str(exc.value)


# ---- 0.4.0 新增只读接口：逐一断言 URL 与方法（handler 只记录，不校验返回结构） ----

NEW_ENDPOINTS = [
    ("get_server_version", lambda c: c.get_server_version(), "/decision/system/version", "GET"),
    ("get_server_health", lambda c: c.get_server_health(), "/decision/system/health", "GET"),
    ("get_decision_modules", lambda c: c.get_decision_modules("kw"), "/decision/v10/decision/modules", "GET"),
    ("get_authority_config", lambda c: c.get_authority_config(), "/decision/v10/authority/config", "GET"),
    ("get_login_config", lambda c: c.get_login_config(), "/decision/login/config", "GET"),
    ("get_password_strategy", lambda c: c.get_password_strategy(), "/decision/login/password/strategy", "GET"),
    ("get_password_warning_time", lambda c: c.get_password_warning_time(), "/decision/login/password/waring/time", "GET"),
    ("list_entries", lambda c: c.list_entries(1, 5, "kw"), "/decision/v10/entries", "GET"),
    ("get_entry_roots", lambda c: c.get_entry_roots(), "/decision/v10/entry/roots", "GET"),
    ("get_all_entries", lambda c: c.get_all_entries(), "/decision/v10/entries/all", "GET"),
    ("list_messages", lambda c: c.list_messages(False, 1, 5, "kw"), "/decision/v10/message/list", "GET"),
    ("list_users", lambda c: c.list_users(), "/decision/v10/users", "POST"),
    ("get_current_user", lambda c: c.get_current_user(), "/decision/v10/user/account", "GET"),
    ("list_departments", lambda c: c.list_departments("kw"), "/decision/v10/departments", "GET"),
    ("list_posts", lambda c: c.list_posts("kw"), "/decision/v10/posts", "GET"),
    ("list_server_datasets", lambda c: c.list_server_datasets(), "/decision/v10/serverdatasets", "GET"),
    ("get_dataset_columns", lambda c: c.get_dataset_columns("ds1"), "/decision/v10/ds1/datasetcolumns", "GET"),
    ("get_authenticated_templates", lambda c: c.get_authenticated_templates(), "/decision/v10/report/templates/all/authentication", "GET"),
    ("list_schedule_tasks", lambda c: c.list_schedule_tasks(1, 5), "/decision/v10/schedule/task/list/2", "GET"),
    ("schedule_task_exists", lambda c: c.schedule_task_exists("t"), "/decision/v10/schedule/task/t/exists", "GET"),
    ("get_executing_tasks", lambda c: c.get_executing_tasks(), "/decision/v10/schedule/executing", "GET"),
    ("get_executing_info", lambda c: c.get_executing_info(), "/decision/v10/schedule/info/executing", "GET"),
    ("list_all_schedule_records", lambda c: c.list_all_schedule_records(1, 5), "/decision/v10/schedule/record/list", "GET"),
    ("get_schedule_settings", lambda c: c.get_schedule_settings(), "/decision/v10/schedule/setting", "GET"),
]


@pytest.mark.parametrize("name,call,path_part,http", NEW_ENDPOINTS, ids=[n for n, *_ in NEW_ENDPOINTS])
def test_new_readonly_endpoint_routing(name, call, path_part, http):
    """每个新接口都打对 URL 与 HTTP 方法（返回结构由各自解析逻辑兜底）"""
    seen = {}

    def handler(request):
        seen["method"] = request.method
        seen["path"] = request.url.path
        seen["params"] = dict(request.url.params)
        return httpx.Response(200, json={"data": {}})

    client = _mock_client(handler)
    try:
        call(client)
    finally:
        client.close()

    assert seen["method"] == http, name
    assert path_part in seen["path"], name


def test_list_reports_server_side_filters():
    """report list 的 keyword/type 必须走服务端参数（fileTypes[] 带方括号）"""
    seen = {}

    def handler(request):
        seen["params"] = dict(request.url.params)
        return httpx.Response(200, json={"data": []})

    client = _mock_client(handler)
    try:
        client.list_reports("/", keyword="烘焙", file_types="cpt")
    finally:
        client.close()

    assert seen["params"]["keyword"] == "烘焙"
    assert seen["params"]["fileTypes[]"] == "cpt"


def test_schedule_tasks_all_uses_listall():
    """--all 走 listAll（不分页），返回 {items}"""
    seen = {}

    def handler(request):
        seen["path"] = request.url.path
        return httpx.Response(200, json={"data": [{"taskName": "t", "taskId": "id1"}]})

    client = _mock_client(handler)
    try:
        result = client.list_schedule_tasks(all_tasks=True)
    finally:
        client.close()

    assert seen["path"].endswith("/decision/v10/schedule/task/listAll/2")
    assert result["items"][0]["taskId"] == "id1"
