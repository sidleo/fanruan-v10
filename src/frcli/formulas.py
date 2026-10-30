"""FineReport 公式的离线检查；不执行公式，也不连接报表或数据库。"""

import difflib
import re

from .exceptions import ApiError
from .function_catalog import CATEGORIES, FUNCTIONS, SOURCES


_TAIL_BAD = set("+-*/^&<>=,(|\\")
_CALL = re.compile(r"(?<![\w.$])([\w\u4e00-\u9fff]+(?:\.[\w\u4e00-\u9fff]+)*)\s*\(")
_PARAM = re.compile(r"\$(?![A-Za-z]{1,3}\$?\d)([A-Za-z_]\w*)")
_DATASET_METHODS = {"SELECT", "GROUP", "VALUE"}
BOUNDARY = "仅离线核对基础语法和随包函数目录；未执行公式，不能证明当前实例的插件、数据、扩展或渲染结果。"


def mask_strings(expr: str) -> str:
    """保留长度与坐标，屏蔽单双引号字符串；识别反斜杠和成对引号。"""
    chars = list(expr)
    quote, i = None, 0
    while i < len(expr):
        ch = expr[i]
        if quote:
            chars[i] = " "
            if ch == "\\":
                if i + 1 < len(expr):
                    chars[i + 1] = " "
                i += 2
                continue
            if ch == quote:
                if i + 1 < len(expr) and expr[i + 1] == quote:
                    chars[i + 1] = " "
                    i += 2
                    continue
                quote = None
        elif ch in ("'", '"'):
            quote = ch
            chars[i] = " "
        i += 1
    if quote:
        label = "单引号" if quote == "'" else "双引号"
        raise ApiError(f"公式里的{label}没有闭合")
    return "".join(chars)


def check_formula(expr: str) -> str:
    """只拒绝能离线确定的残缺公式；不以静态目录限制插件函数。"""
    e = (expr or "").strip()
    if not e:
        raise ApiError("公式不能为空")
    if not e.startswith("="):
        e = "=" + e
    body = e[1:].strip()
    if not body:
        raise ApiError("公式只有 `=`，没有内容")
    code = mask_strings(body)
    stack = []
    pairs = {")": "(", "]": "[", "}": "{"}
    for ch in code:
        if ch in "([{":
            stack.append(ch)
        elif ch in pairs:
            if not stack:
                raise ApiError(f"公式括号不配对：多了一个 `{ch}`")
            if stack[-1] != pairs[ch]:
                raise ApiError(f"公式括号不配对：`{stack[-1]}` 与 `{ch}` 不匹配")
            stack.pop()
    if stack:
        raise ApiError(f"公式括号不配对：有 `{stack[-1]}` 没闭合")
    if code[-1] in _TAIL_BAD:
        raise ApiError(f"公式以 `{body[-1]}` 结尾，写完整再提交"
                       "（服务端会静默渲染成空白，不报错）")
    return e


def functions(name=None, keyword=None, category=None) -> dict:
    """函数名称精确查询，或按分类、关键词检索；目录不是运行时白名单。"""
    if category and category not in CATEGORIES:
        raise ApiError(f"未知函数分类 {category!r}；可用: {', '.join(CATEGORIES)}")
    rows = list(FUNCTIONS.values())
    if name:
        key = name.strip().upper()
        if key not in FUNCTIONS:
            hints = difflib.get_close_matches(key, FUNCTIONS, n=3, cutoff=0.65)
            raise ApiError(f"随包目录未收录函数 {name!r}，不代表实例没有此插件/自定义函数"
                           + (f"；相近名称: {', '.join(hints)}" if hints else ""))
        rows = [FUNCTIONS[key]]
    if category:
        rows = [r for r in rows if r["category"] == category]
    if keyword:
        term = keyword.casefold()
        rows = [r for r in rows if term in " ".join(
            str(r.get(k) or "") for k in ("name", "summary", "signature", "category")
        ).casefold()]
    return {"status": "ok", "action": "functions", "catalog_size": len(FUNCTIONS),
            "count": len(rows), "functions": rows, "categories": CATEGORIES,
            "sources": SOURCES, "runtime_verified": False, "boundary": BOUNDARY}


def analyze_formula(expr: str, context="cell", declared_params=None) -> dict:
    """基础语法、函数名、上下文提示；未知函数只提示，不冒充完整语法解析器。"""
    if context not in ("cell", "parameter", "widget"):
        raise ApiError("公式上下文只能是 cell / parameter / widget")
    formula = check_formula(expr)
    code = mask_strings(formula)
    calls, unknown, warnings = [], [], []
    for name in dict.fromkeys(m.group(1).upper() for m in _CALL.finditer(code)):
        key = name
        if "." in name and name.rsplit(".", 1)[1] in _DATASET_METHODS:
            key = "DATASET." + name.rsplit(".", 1)[1]
        info = FUNCTIONS.get(key)
        calls.append({"name": name, "catalog_name": key if info else None,
                      "category": info["category"] if info else None})
        if info is None:
            unknown.append(name)
            candidates = difflib.get_close_matches(name, FUNCTIONS, n=2, cutoff=0.65)
            warnings.append({"code": "unknown_function", "function": name,
                             "suggestions": candidates,
                             "message": f"随包目录未收录 {name}；请核对拼写，或确认目标实例已安装对应插件/自定义函数。"})
        elif info["category"] in ("hierarchy", "report", "dataset"):
            warnings.append({"code": "requires_context", "function": name,
                             "message": f"{name} 依赖报表/数据集上下文，必须在目标 sheet、参数及扩展关系下验收。"})
        if key.startswith("DATASET.") and context == "widget":
            warnings.append({"code": "unsupported_widget_dataset", "function": name,
                             "message": "官方文档说明参数面板不支持数据集方法；请用合适的参数联动或数据字典。"})
        if key in ("EVAL", "QUERY", "SQL"):
            warnings.append({"code": "runtime_expression", "function": name,
                             "message": f"{name} 的表达式、脚本或连接内容未执行，离线检查无法验证其结果。"})
    params = list(dict.fromkeys(_PARAM.findall(code)))
    if "${" in code:
        warnings.append({"code": "sql_parameter_syntax",
                         "message": "单元格/参数公式引用参数使用 $x；${x} 是数据集 SQL 中的替换写法。"})
    if declared_params is not None:
        declared = {p.casefold() for p in declared_params}
        missing = [p for p in params if p.casefold() not in declared]
        if missing:
            warnings.append({"code": "undeclared_parameters", "parameters": missing,
                             "message": "请声明参数或在预览/导出时传值；内置会话变量需按目标实例核实。"})
    return {"status": "ok", "action": "formula-check", "formula": formula,
            "context": context, "syntax": "basic-checks-passed", "calls": calls,
            "parameters": params, "unknown_functions": unknown, "warnings": warnings,
            "runtime_verified": False, "boundary": BOUNDARY}
