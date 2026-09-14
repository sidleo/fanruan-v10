"""自定义异常"""


class FrcliError(Exception):
    """基础异常"""
    code = "UNKNOWN"
    details = None


class AuthError(FrcliError):
    """认证失败"""
    code = "AUTH_FAILED"


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
