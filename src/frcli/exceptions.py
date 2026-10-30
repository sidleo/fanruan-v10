"""自定义异常"""


class FrcliError(Exception):
    """基础异常"""
    code = "UNKNOWN"
    details = None


class AuthError(FrcliError):
    """认证失败"""
    code = "AUTH_FAILED"


class AuthLockTimeoutError(AuthError):
    """等待实例登录锁超时（不是认证失败：另一个 frcli 进程正在登录同一实例）"""
    code = "AUTH_LOCK_TIMEOUT"


class ConfigError(FrcliError):
    """配置错误"""
    code = "CONFIG_ERROR"


class ReportNotFoundError(FrcliError):
    """报表不存在"""
    code = "REPORT_NOT_FOUND"


class ExportError(FrcliError):
    """导出失败"""
    code = "EXPORT_ERROR"


class QueryError(FrcliError):
    """查询失败"""
    code = "QUERY_ERROR"


class ScheduleError(FrcliError):
    """定时任务操作失败"""
    code = "SCHEDULE_ERROR"


class ConnectionError(FrcliError):
    """连接失败"""
    code = "CONNECTION_ERROR"


class ApiError(FrcliError):
    """决策平台接口返回错误（200 + HTML 出错页，原因在 detail-message）"""
    code = "API_ERROR"


class InspectionError(FrcliError):
    """运行时巡检（模板性能分析）失败：插件未启用、模板没跑起来、结果等待超时等"""
    code = "INSPECTION_ERROR"


class TemplateValidationError(FrcliError):
    """模板结构或引用存在不能安全自动处理的问题。"""

    code = "TEMPLATE_VALIDATION_ERROR"

    def __init__(self, message, diagnostics, **details):
        super().__init__(message)
        self.details = {"can_apply": False, "diagnostics": diagnostics, **details}
