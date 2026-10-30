"""模板级操作：字体体检 / 历史版本 / 服务端出图 / 结构化编辑闭环。

这一层把「远程设计通道」的散装 RPC 调用拼成 agent 能直接用的动作。三条路径口径要分清
（踩过才知道，见 `references/remote-services.md` §0）：

| 服务 | 收什么路径 | 例 |
|---|---|---|
| `WorkResource` / `TplOperator` | **工作区路径** | `reportlets/demo_group/demo_user/x.cpt` |
| `VcsOperator` / `TemplateExportOperator` / `TemplateChecker` | **展示路径** | `demo_group/demo_user/x.cpt` |

写操作一律先过 `assert_in_write_scope`（`$FRCLI_WRITE_SCOPE`，未设时用默认团队目录），
再走 `upload_template` 的「占锁 → 备份 → 写 → 回读校验」。
"""

import datetime
import difflib
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from . import chartxml, cptxml, formulas
from .config import load_config
from .exceptions import ApiError
from .remotedesign import (RemoteDesignSession, _unwrap_value, assert_in_write_scope,
                           assert_template_bytes, normalize_report_path, upload_template)

FONT_CHECKER = "com.fr.workspace.server.check.TemplateChecker"
VCS = "com.fr.workspace.server.vcs.VcsOperator"
EXPORTER = "com.fr.workspace.server.exporter.TemplateExportOperator"


@dataclass
class LocalTemplate:
    """显式的离线目标，不含实例、凭据或网络客户端。"""

    path: str
    output: str = None


def _target_path(config, path):
    return str(Path(config.path).expanduser().resolve()) if isinstance(config, LocalTemplate) else to_workspace_path(path)


def _local_commit(config, before_text, new_text, result, apply):
    if not apply or before_text == new_text:
        return result
    if not config.output:
        raise ApiError("本地 --apply 必须给 -o RESULT.cpt，写入新文件")
    source = Path(config.path).expanduser().resolve()
    raw_output = Path(config.output).expanduser()
    output = raw_output.resolve()
    if output == source and source.exists():
        raise ApiError("本地编辑不能覆盖源模板，请给不同的 -o 路径")
    if raw_output.is_symlink() or output.exists():
        raise ApiError("本地输出已存在，拒绝覆盖，请使用新的 -o 路径")
    if before_text and (not source.exists() or source.read_bytes() != before_text.encode("utf-8")):
        raise ApiError("源模板在读取后已变化，已取消本地写入")
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".frcli-", suffix=".cpt", dir=output.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(new_text.encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
        # link 是原子的不覆盖创建；不会把并发产生的输出文件替换掉。
        os.link(name, output)
    except FileExistsError as exc:
        raise ApiError("本地输出已被其他操作创建，拒绝覆盖") from exc
    finally:
        Path(name).unlink(missing_ok=True)
    verified = output.read_bytes() == new_text.encode("utf-8")
    if not verified:
        raise ApiError("本地写后回读不一致")
    result.update({"applied": True, "local": str(output), "upload": {"verified": True},
                   "sha256": _sha(output.read_bytes())})
    return result


def to_display_path(path: str) -> str:
    """工作区路径 → 展示路径（`VcsOperator` / 导出 / 字体体检要这个）。"""
    p = normalize_report_path(path)
    return p[len("reportlets/"):] if p.startswith("reportlets/") else p


def to_workspace_path(path: str) -> str:
    return normalize_report_path(path)


# ---------------------------------------------------------------------------
# 只读：字体体检 / 历史版本 / 出图
# ---------------------------------------------------------------------------
def template_fonts(config, report_path: str) -> dict:
    """`TemplateChecker.checkFont`：模板用到但服务端**缺失**的字体（空 = 没问题）。"""
    display = to_display_path(report_path)
    with RemoteDesignSession(config) as s:
        s.check()
        res = s.call_result(FONT_CHECKER, "checkFont", [("java.lang.String", display)])
    if res.exception:
        raise ApiError(f"字体体检失败: {res.exception}")
    missing = _string_list(_unwrap_value(res.value))
    return {
        "action": "fonts",
        "report": display,
        "missing_fonts": missing,
        "ok": not missing,
        "note": "空列表 = 模板用到的字体服务端都有；非空时导出可能字体替换",
    }


def template_versions(config, report_path: str, limit: int = 20) -> dict:
    """`VcsOperator.getVersions`：远程设计的提交历史（**只读**）。

    注意路径用**展示路径**：带 `reportlets/` 前缀时服务端返回空列表（实测）。
    """
    display = to_display_path(report_path)
    with RemoteDesignSession(config) as s:
        s.check()
        res = s.call_result(VCS, "getVersions", [("java.lang.String", display)])
        if res.exception:
            raise ApiError(f"读版本历史失败: {res.exception}")
        raw = res.value
        items = _list_items(raw)
        versions = []
        for i, ent in enumerate(items[:limit]):
            row = _vcs_entity(ent)
            # getFileVersionByIndex 的 index 是「按时间倒序的第几条」，与上面顺序一致
            row["index"] = i
            versions.append(row)
    return {"action": "versions", "report": display, "count": len(items),
            "versions": versions,
            "note": "空列表有两种可能：该模板从未走远程设计保存过，或路径没传展示路径"}


def _vcs_entity(ent):
    f = getattr(ent, "fields", {}) or {}
    return {
        "version": f.get("version"),
        "username": f.get("username"),
        "time": _timestamp(f.get("time")),
        "commit_code": f.get("commitCode"),
        "commit_msg": f.get("commitMsg") or "",
        "id": f.get("id"),
        "filename": f.get("filename"),
    }


def _timestamp(obj):
    """`java.sql.Timestamp`：毫秒在父类 `java.util.Date` 的 writeObject 数据里。"""
    if obj is None:
        return None
    for cls, _items, raw in getattr(obj, "custom_chain", []) or []:
        if cls == "java.util.Date" and len(raw) >= 8:
            millis = int.from_bytes(raw[:8], "big", signed=True)
            return datetime.datetime.fromtimestamp(millis / 1000).strftime("%Y-%m-%d %H:%M:%S")
    return None


def template_image(config, report_path: str, form: bool = False) -> tuple:
    """`TemplateExportOperator.export*AsImageData`：服务端直接出图，返回 (bytes, meta)。

    用**展示路径**；`.cpt` 走 `exportWorkBookAsImageData`，`.frm`（决策报表）走
    `exportFormAsImageData`（对 .cpt 调它只会得到 68 字节空图）。
    """
    display = to_display_path(report_path)
    method = "exportFormAsImageData" if form else "exportWorkBookAsImageData"
    with RemoteDesignSession(config) as s:
        s.check()
        res = s.call_result(EXPORTER, method, [("java.lang.String", display)])
    if res.exception:
        raise ApiError(f"服务端出图失败: {res.exception}")
    data = _unwrap_value(res.value)
    if not isinstance(data, (bytes, bytearray)):
        raise ApiError(f"服务端出图返回了非字节内容: {type(data).__name__}")
    data = bytes(data)
    return data, {"action": "image", "report": display, "method": method, "size": len(data)}


# ---------------------------------------------------------------------------
# 读模板（必须走远程设计通道，不能用 format=cpt）
# ---------------------------------------------------------------------------
def read_template(config, report_path: str) -> bytes:
    """读服务端**模板文件本身**的字节。

    ⚠️ 不要用 `GET /decision/view/report?format=cpt`：那返回的是数据集定义提取物
    （根元素 `<TableDataMap>`），不是模板字节；照它改完写回去会毁模板。
    """
    if isinstance(config, LocalTemplate):
        try:
            data = Path(config.path).expanduser().read_bytes()
            from .cptmodel import DocumentIndex
            DocumentIndex(data.decode("utf-8"))
            return data
        except (OSError, UnicodeError) as exc:
            raise ApiError(f"无法读取 UTF-8 本地 CPT: {exc}") from exc
    remote = _target_path(config, report_path)
    with RemoteDesignSession(config) as s:
        s.check()
        if not s.exist(remote):
            raise ApiError(f"服务端不存在: {remote}")
        size = s.length(remote)
        data = s.read(remote)
    if not data:
        raise ApiError(f"读到 0 字节: {remote}（该路径可能不在当前账号的远程设计授权目录内）")
    if len(data) != size:
        raise ApiError(f"读取不完整: 期望 {size} 字节，实得 {len(data)}")
    assert_template_bytes(data)
    if cptxml.template_tag_name(data.decode("utf-8", "replace")) != cptxml.WORKBOOK_TAG:
        raise ApiError(f"根元素不是 <{cptxml.WORKBOOK_TAG}>，拒绝按模板处理: {remote}")
    return data


# ---------------------------------------------------------------------------
# 结构化编辑
# ---------------------------------------------------------------------------
def plan_edit(text: str, dataset: str = None, sql: str = None, sql_file: str = None,
              replace=(), connection: str = None, param: str = None, default: str = None,
              default_formula: str = None):
    """在内存里算出编辑后的文本与变更清单（不碰网络）。"""
    changes = []
    new_text = text
    if default is not None and default_formula is not None:
        raise ApiError("--default 与 --default-formula 只能给一个")
    tds = {t["name"]: t for t in cptxml.table_datas(text)}
    if dataset and dataset not in tds:
        raise ApiError(f"模板里没有数据集 {dataset}；现有: {', '.join(tds) or '(无)'}")
    target = tds.get(dataset) if dataset else None

    if sql is not None and sql_file:
        raise ApiError("--sql 与 --sql-file 只能给一个")
    if sql_file:
        sql = Path(sql_file).read_text(encoding="utf-8")
    if (sql is not None or replace or connection) and target is None:
        raise ApiError("改数据集需要 --dataset <名字>（用 `report edit <报表> --list` 看有哪些）")

    if sql is not None:
        if target["sql_element"] is None:
            raise ApiError(f"数据集 {dataset} 没有 <Query> 元素，无法改 SQL")
        if target["sql"] == sql:
            raise ApiError(f"数据集 {dataset} 的 SQL 与给定内容完全相同，无需修改")
        new_text = cptxml.set_text(new_text, target["sql_element"], sql)
        changes.append({"kind": "dataset.sql", "dataset": dataset,
                        "mode": "replace-all",
                        "diff": _text_diff(target["sql"], sql, f"{dataset}.sql")})
    elif replace:
        if target is None or target["sql_element"] is None:
            raise ApiError(f"数据集 {dataset} 没有 <Query> 元素，无法替换")
        cur, repl = target["sql"], []
        for item in replace:
            old, sep, new = item.partition("=")
            if not sep or not old:
                raise ApiError(f"--replace 要写成 OLD=NEW，收到 {item!r}")
            n = cur.count(old)
            if n == 0:
                raise ApiError(f"--replace 的 {old!r} 在数据集 {dataset} 的 SQL 里没出现")
            cur = cur.replace(old, new)
            repl.append({"old": old, "new": new, "count": n})
        new_text = cptxml.set_text(new_text, target["sql_element"], cur)
        changes.append({"kind": "dataset.sql", "dataset": dataset, "mode": "substring",
                        "replacements": repl,
                        "diff": _text_diff(target["sql"], cur, f"{dataset}.sql")})

    if connection is not None:
        target = next((t for t in cptxml.table_datas(new_text) if t["name"] == dataset), None)
        el = target["connection_element"]
        if el is None:
            raise ApiError(f"数据集 {dataset} 没有 <Connection>/<DatabaseName> 元素")
        before = target["connection"]
        if before == connection:
            raise ApiError(f"数据集 {dataset} 的连接本来就是 {connection!r}，无需修改")
        new_text = cptxml.set_text(new_text, el, connection)
        changes.append({"kind": "dataset.connection", "dataset": dataset,
                        "before": before, "after": connection})

    if param is not None or default is not None or default_formula is not None:
        if param is None or (default is None and default_formula is None):
            raise ApiError("改参数默认值要同时给 --param <名字> 与 --default <值> 或 --default-formula <公式>")
        target = next((t for t in cptxml.table_datas(new_text) if t["name"] == dataset), None)
        if target is None:
            raise ApiError("改数据集参数需要 --dataset <名字>")
        hit = [p for p in target["parameters"] if p["name"] == param]
        if not hit:
            names = [p["name"] for p in target["parameters"]]
            raise ApiError(f"数据集 {dataset} 没有参数 {param}；现有: {', '.join(names) or '(无)'}")
        before = hit[0]["default"]
        new_text, how = cptxml.set_default_value(new_text, hit[0]["element"],
                                                default, default_formula)
        changes.append({"kind": "dataset.parameter", "dataset": dataset, "param": param,
                        "before": before, "after": (cptxml.check_formula(default_formula)
                                                      if default_formula is not None else default),
                        "default_type": "formula" if default_formula is not None else "value",
                        "how": how})

    if not changes:
        raise ApiError("没有给任何编辑动作（--sql / --replace / --connection / --param+--default）")
    return new_text, changes


def edit_template(config, report_path: str, apply: bool = False, **kwargs) -> dict:
    """拉模板 → 结构化改 → （--apply 时）上传 + 回读校验。默认只 dry-run。"""
    if apply and not isinstance(config, LocalTemplate):
        _scope(report_path)
    data = read_template(config, report_path)
    text = data.decode("utf-8")
    new_text, changes = plan_edit(text, **kwargs)
    return commit(config, report_path, text, new_text, "edit", changes, apply=apply)


def _text_diff(before: str, after: str, label: str) -> str:
    if before == after:
        return ""
    lines = difflib.unified_diff(before.splitlines(), after.splitlines(),
                                 fromfile=f"{label} (before)", tofile=f"{label} (after)",
                                 lineterm="", n=1)
    return "\n".join(lines)


def _string_list(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(x) for x in value]
    items = getattr(value, "custom", None)
    if items:
        out = []
        for x in items:
            if hasattr(x, "custom") and x.custom:
                out.extend(str(k) for k in x.custom)
            else:
                out.append(str(x))
        return out
    return []


def _list_items(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return list(getattr(value, "custom", None) or [])


def template_summary(config, report_path: str) -> dict:
    """`--list`：从**真实模板字节**列出数据集/连接/参数/SQL 里的 `${}` 引用。"""
    data = read_template(config, report_path)
    info = cptxml.summarize(data.decode("utf-8"))
    info.update({"action": "edit-list", "report": _target_path(config, report_path),
                 "sha256_before": _sha(data)})
    return info


def _sha(data: bytes) -> str:
    import hashlib
    return hashlib.sha256(data).hexdigest()


def load_instance(instance=None):
    return load_config(instance)


# ===========================================================================
# 模板创作（report new / cell / dataset / param / style / table）
# ===========================================================================
#: 统一的写范围判定（与 upload/delete/edit 同一份实现，fail-closed）
def _scope(remote: str):
    assert_in_write_scope(remote)


def diff_text(before: str, after: str, label: str, limit: int = 200) -> str:
    """可读的统一 diff（`-` 旧 / `+` 新），超长截断。"""
    if before == after:
        return ""
    lines = list(difflib.unified_diff(before.splitlines(), after.splitlines(),
                                      fromfile=f"{label} (before)",
                                      tofile=f"{label} (after)", lineterm="", n=2))
    if len(lines) > limit:
        lines = lines[:limit] + [f"... 另有 {len(lines) - limit} 行 diff 未显示"]
    return "\n".join(lines)


def commit(config, report_path: str, before_text: str, new_text: str, action: str,
           changes, apply: bool = False, extra: dict = None, force: bool = True) -> dict:
    """dry-run 打印 diff / `--apply` 才写服务端（写前守门 + 写后回读校验）。

    写路径与 `report edit` 完全一致：占锁 → 备份 → 写 → 回读 SHA256 比对。
    """
    from .cptmodel import DocumentIndex, assert_valid
    index = DocumentIndex(new_text)
    assert_valid(index)
    validation = index.report()
    remote = _target_path(config, report_path)
    result = {
        "action": action,
        "remote": remote,
        "applied": False,
        "dry_run": not apply,
        "bytes_before": len((before_text or "").encode("utf-8")),
        "bytes_after": len(new_text.encode("utf-8")),
        "changes": changes,
        "diff": diff_text(before_text or "", new_text, os.path.basename(remote)),
        **validation,
    }
    if extra:
        result.update(extra)
    unchanged = (before_text or "") == new_text
    result["changed"] = not unchanged
    if unchanged:
        result["note"] = "内容无变化（已经是目标状态），未发起写请求"
    if not apply:
        result["hint"] = "以上为 dry-run，未写服务端；确认无误加 --apply"
        return result
    if unchanged:
        # 幂等：不为了"什么都没改"去写一次服务端（省一次往返 + 一次备份）
        result["applied"] = False
        result["dry_run"] = False
        return result
    if isinstance(config, LocalTemplate):
        return _local_commit(config, before_text or "", new_text, result, apply)
    _scope(remote)                                  # 双保险：网络调用前先判定
    data = new_text.encode("utf-8")
    assert_template_bytes(data)                     # 根元素必须是 <WorkBook>
    tmp = Path(tempfile.mkstemp(prefix="frcli-new-", suffix=".cpt")[1])
    try:
        tmp.write_bytes(data)
        optimistic = {"expected_sha256": _sha((before_text or "").encode("utf-8"))} if before_text else {}
        up = upload_template(config, str(tmp), remote, force=force, **optimistic)
    finally:
        tmp.unlink(missing_ok=True)
    result.update({"applied": True, "dry_run": False, "upload": up})
    return result


def _cell_brief(cell: dict) -> dict:
    return {k: cell.get(k) for k in ("a1", "kind", "text", "formula", "binding",
                                     "ds_mode", "ds_fn",
                                     "expand", "style", "cs", "rs") if cell.get(k) is not None}


# ---------------------------------------------------------------------------
# report new
# ---------------------------------------------------------------------------
def build_template(sheet: str = None, from_text: str = None, template_id: str = None) -> str:
    """空白模板：自带骨架，或把 `--from` 那张模板裁成骨架（保留版面/样式外壳）。"""
    if from_text is None:
        return cptxml.empty_skeleton(sheet or "sheet1", template_id=template_id)
    if cptxml.template_tag_name(from_text) != cptxml.WORKBOOK_TAG:
        raise ApiError("--from 的内容根元素不是 <WorkBook>，不是 cpt 模板")
    return cptxml.strip_to_skeleton(from_text, sheet=sheet, template_id=template_id)


def new_template(config, report_path: str, sheet: str = None, from_path: str = None,
                 apply: bool = False, output: str = None, template_id: str = None,
                 force: bool = False) -> dict:
    """`report new`：从骨架（或 `--from` 模板）生成一个新的空白 cpt。

    目标已存在时**默认拒绝**（`force=False` 会走到 `upload_template` 的覆盖守门），
    要覆盖得显式 `--force` —— 否则一次手滑就把别人的模板换成空骨架。"""
    if apply and not isinstance(config, LocalTemplate):
        _scope(report_path)
    from_text = None
    if from_path:
        if isinstance(config, LocalTemplate):
            from_path = str(Path(from_path).expanduser())
            if not Path(from_path).is_file():
                raise ApiError("--local 的 --from 必须是存在的本地模板文件")
        if os.path.isfile(from_path):
            from_text = Path(from_path).read_text(encoding="utf-8")
        else:
            from_text = read_template(config, from_path).decode("utf-8")
    new_text = build_template(sheet=sheet, from_text=from_text, template_id=template_id)
    if output and not isinstance(config, LocalTemplate):
        p = Path(output)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(new_text, encoding="utf-8")
    result = commit(config, report_path, "", new_text, "new", changes=[
        {"kind": "template.create", "sheet": sheet or "sheet1",
         "from": from_path or "(内置骨架)", "bytes": len(new_text.encode("utf-8"))}],
        apply=apply, force=force)
    if output and not isinstance(config, LocalTemplate):
        result["local"] = str(Path(output).resolve())
    return result


# ---------------------------------------------------------------------------
# report cell
# ---------------------------------------------------------------------------
def plan_cell(text: str, at: str, sheet: str = None, value: str = None, formula: str = None,
              binding: str = None, expand: str = None, style=None, fmt: str = None,
              bold: bool = False, bg: str = None, align: str = None, border: bool = False,
              clear: bool = False, merge: str = None, ds_mode: str = None, ds_fn: str = None,
              ds_result: str = None, ds_filter: str = None, expand_left: str = None,
              expand_up: str = None, show_html: bool = False, tooltip: str = None):
    """改一个单元格（内存计算，不碰网络）。A1 记法：`--at B3`。"""
    changes = []
    new_text = text
    if clear:
        cell = cptxml.find_cell(new_text, at, sheet)
        if cell is None:
            raise ApiError(f"{at} 没有单元格，不需要 --clear")
        new_text = cptxml.delete_cell(new_text, cell)
        changes.append({"kind": "cell.clear", "at": cell["a1"], "before": _cell_brief(cell)})
        return new_text, changes

    given = [x is not None for x in (value, formula, binding)]
    if sum(given) > 1:
        raise ApiError("--set-value / --set-formula / --bind 只能给一个")
    if ds_mode is not None:
        cptxml.check_ds_mode(ds_mode, ds_fn)         # 本地语义校验（写错就地报错）
    if ds_fn is not None and ds_mode is None:
        raise ApiError("--fn 要跟 --set-ds-mode summary 一起用"
                       "（只改汇总函数也得写 --set-ds-mode summary）")
    if (ds_result is not None or ds_filter is not None) and binding is None:
        cell0 = cptxml.find_cell(new_text, at, sheet)
        if cell0 is None or cell0.get("kind") != "ds":
            raise ApiError("--ds-result / --ds-filter 只对数据集列单元格有意义"
                           "（跟 --bind 数据集.列 一起用）")
    style_new = any([fmt, bold, bg, align, border])
    if style is not None and style_new:
        raise ApiError("--style N 与新建样式（--format/--bold/--bg/--align/--border）二选一")

    cell = cptxml.find_cell(new_text, at, sheet)
    new_style = None if style is None else str(style)
    if style is not None:
        cptxml.check_style_index(new_text, style)
    if formula is not None:
        formula = cptxml.check_formula(formula)
    if style_new:
        xml = cptxml.style_xml(fmt=fmt, bold=bold, bg=bg, align=align, border=border)
        new_text, idx = cptxml.append_style(new_text, xml)
        new_style = str(idx)
        changes.append({"kind": "style.add", "index": idx, "format": fmt,
                        "bold": bool(bold), "bg": bg, "align": align, "border": bool(border)})
        cell = cptxml.find_cell(new_text, at, sheet)

    c, r = cptxml.parse_a1(at)
    if cell is None:
        if not any(given):
            raise ApiError(f"{at} 还没有单元格：新建要给内容（--set-value / --set-formula / "
                           "--bind 数据集.列）")
        if binding is not None:
            _assert_dataset(new_text, binding)
        snippet = cptxml.cell_xml(c, r, value=value, formula=formula, binding=binding,
                                  expand=expand, style=new_style,
                                  ds_mode=ds_mode, ds_fn=ds_fn,
                                  ds_result=ds_result, ds_filter=ds_filter,
                                  left=expand_left, up=expand_up)
        new_text, _info = cptxml.put_cell(new_text, at, snippet, sheet)
        changes.append({"kind": "cell.insert", "at": at,
                        "content": value if value is not None else (formula or binding),
                        "ds_mode": (ds_mode or "group") if binding is not None else None,
                        "ds_fn": ds_fn if binding is not None else None,
                        "expand": expand or "none", "style": new_style})
    else:
        new_text = _rewrite_existing_cell(new_text, at, sheet, cell, changes,
                                          value=value, formula=formula, binding=binding,
                                          expand=expand, new_style=new_style,
                                          ds_mode=ds_mode, ds_fn=ds_fn,
                                          expand_left=expand_left, expand_up=expand_up)
    if ds_result is not None or ds_filter is not None:
        cell = cptxml.find_cell(new_text, at, sheet)
        if ds_filter is not None:
            new_text = cptxml.set_ds_filter(new_text, cell, ds_filter)
            changes.append({"kind": "cell.ds_filter", "at": at, "filter": ds_filter or None})
        if ds_result is not None:
            new_text = cptxml.set_ds_result(new_text, cell, ds_result)
            changes.append({"kind": "cell.ds_result", "at": at, "result": ds_result or None})
    if show_html or tooltip is not None:
        cell = cptxml.find_cell(new_text, at, sheet)
        new_text = cptxml.set_cell_gui(new_text, cell, show_as_html=show_html or None,
                                       tooltip=tooltip)
        changes.append({"kind": "cell.gui", "at": at, "show_as_html": bool(show_html),
                        "tooltip": tooltip})
    if merge:
        c1, r1 = cptxml.parse_range(merge)[:2]
        if (c1, r1) != cptxml.parse_a1(at):
            raise ApiError(f"--merge {merge} 的左上角必须是 --at {at}（合并信息存在左上角格）")
        new_text, ch = cptxml.set_merge(new_text, merge, sheet)
        changes.append(ch)
    if formula is not None:
        _warn_formula(changes, new_text, formula)
    if value is not None:
        _warn_backslash(changes, value)
    if binding is not None:
        _note_column(changes, new_text, binding)
    if changes and (cptxml.find_cell(new_text, at, sheet) or {}).get("ds_mode") == "summary":
        _warn_summary_column(changes, None)
    if not changes:
        # 幂等：请求的状态已经成立，不报错、也不发无用写请求。
        # 以前这里抛错（exit 1），会让 `set -e` 的复现/构建脚本在中途断掉 ——
        # 重复执行一份配方是正常操作，不该失败；但必须**看得见**"什么都没改"。
        changes.append({"kind": "noop", "at": at,
                        "message": "已经是目标状态，没有任何改动"})
    return new_text, changes


def _rewrite_existing_cell(text, at, sheet, cell, changes, value=None, formula=None,
                           binding=None, expand=None, new_style=None, ds_mode=None,
                           ds_fn=None, expand_left=None, expand_up=None):
    if binding is not None and ds_mode is None:
        # 只改绑定：**保留**这一格原来的数据设置（否则会把它的列表/汇总悄悄改成分组）
        ds_mode = cell.get("ds_mode")
        ds_fn = None
        if ds_mode == "summary":
            ds_fn = cptxml.summary_fn_token(cell.get("ds_fn"))
            if ds_fn is None and cell.get("ds_fn"):
                raise ApiError(
                    f"{at} 原本用汇总函数 {cell['ds_fn']}，CLI 不认识它；"
                    f"改绑定时请显式给 --set-ds-mode summary --fn "
                    f"{' / '.join(cptxml.SUMMARY_FUNCTIONS)}")
        if ds_mode in (None, "unknown"):
            ds_mode = None
    o_rewritten = False
    if value is not None or formula is not None or binding is not None:
        if binding is not None:
            _assert_dataset(text, binding)
        before = _cell_brief(cell)
        old = before.get("text") or before.get("formula") or before.get("binding")
        after = value if value is not None else (formula or binding)
        mode_changed = binding is not None and (
            cell.get("ds_mode") != ds_mode
            or cptxml.summary_fn_token(cell.get("ds_fn")) != ds_fn)
        if old != after or mode_changed:
            text = cptxml.replace_o(text, cell, cptxml.o_xml(value=value, formula=formula,
                                                             binding=binding, ds_mode=ds_mode,
                                                             ds_fn=ds_fn))
            cell = cptxml.find_cell(text, at, sheet)
            change = {"kind": "cell.value", "at": at, "before": old, "after": after}
            if binding is not None:
                change["ds_mode"] = ds_mode
                if ds_fn:
                    change["ds_fn"] = ds_fn
            changes.append(change)
            o_rewritten = True
        elif not any([binding, expand, new_style, ds_mode]):
            return text                      # 内容本来就一样：不记变更，也不重写
    if ds_mode is not None and not o_rewritten:
        # 只改数据设置：换掉 <RG>，单元格内容/样式/扩展一律不动
        before_mode, before_fn = cell.get("ds_mode"), cell.get("ds_fn")
        if before_mode != ds_mode or before_fn != ds_fn:
            text = cptxml.set_grouper(text, cell, ds_mode, ds_fn)
            cell = cptxml.find_cell(text, at, sheet)
            change = {"kind": "cell.ds-mode", "at": at, "before": before_mode,
                      "after": ds_mode}
            if before_fn:
                change["before_fn"] = before_fn
            if ds_fn:
                change["after_fn"] = ds_fn
            changes.append(change)
    if expand is not None:
        if cell["expand"] != expand:
            before = cell["expand"]
            text = cptxml.set_expand(text, cell, expand)
            cell = cptxml.find_cell(text, at, sheet)
            changes.append({"kind": "cell.expand", "at": at, "before": before,
                            "after": expand})
    if expand_left is not None or expand_up is not None:
        left = (expand_left or cell.get("expand_left") or "").upper() or None
        up = (expand_up or cell.get("expand_up") or "").upper() or None
        cur = (cell.get("expand") or "none")
        if (cell.get("expand_left"), cell.get("expand_up")) != (left, up):
            text = cptxml.set_expand(text, cell, cur, left=left, up=up)
            cell = cptxml.find_cell(text, at, sheet)
            changes.append({"kind": "cell.expand-parent", "at": at,
                            "left": left, "up": up})
    if new_style is not None:
        before = cell["style"]
        if str(before) != str(new_style):
            text = cptxml.set_attr(text, cell["element"], "s", new_style)
            changes.append({"kind": "cell.style", "at": at, "before": before,
                            "after": new_style})
    return text


def _assert_dataset(text: str, binding: str):
    ds = binding.partition(".")[0]
    names = cptxml.dataset_names(text)
    if ds not in names:
        raise ApiError(f"单元格绑定的数据集 {ds!r} 不在模板里；现有: "
                       f"{', '.join(names) or '(无)'}（先用 `report dataset --add` 建）")


def _warn_backslash(changes, value: str):
    r"""静态文本里的反斜杠由**服务端**当转义处理（CLI 原样写进 XML），实测三种坏法：

    `a\tb`→TAB ｜ `a\b`→`a?` ｜ `地区\销售员` / `C:\data\file` / 单独 `\` → **整格渲染成空**。
    转义本身有合法用途（`\t` 就是 TAB），所以只能 warning，不能硬拦。
    """
    BS = chr(92)          # 反斜杠；用 chr 写，避免本文件被转义层级绕晕
    if not value or BS not in value:
        return
    if BS * 2 in value:   # 已经写了双反斜杠 = 字面量，没问题
        return
    changes.append({"kind": "warning",
                    "message": "静态文本里有**单个反斜杠**：服务端会当转义处理（`" + BS + r"t`→TAB），"
                               "而未知转义（如 `" + BS + r"s`、`C:" + BS + r"data`）会让"
                               "**整格渲染成空**且不报错。要字面反斜杠请写两个"
                               "（`" + BS * 2 + "`）。写完务必读回那一格。"})


def _warn_formula(changes, text: str, formula: str):
    """公式里参数的两种静默坏法（实测：都不报错）。"""
    sig = cptxml.formula_signature(formula)
    if sig["brace_ref"]:
        changes.append({"kind": "warning",
                        "message": "单元格公式里的参数要写 `$x`；写 `${x}` 会把这几个字符原样"
                                   "渲染出来（数据集 SQL 才用 `${x}`）"})
    declared = {p["name"] for p in cptxml.template_parameters(text)}
    missing = [n for n in sig["params"] if n not in declared]
    if missing:
        changes.append({"kind": "warning",
                        "message": f"公式引用了没声明默认值的参数 {', '.join(missing)}："
                                   "不传 --params 时会静默变成空字符串（导出照成功）。"
                                   f"补：`report param <报表> --add {missing[0]}=<默认值>`"})
    for warning in formulas.analyze_formula(formula)["warnings"]:
        if warning["code"] == "unknown_function":
            changes.append({"kind": "warning", **warning})


def _note_column(changes, text: str, binding: str):
    """列名没法离线核对（要连库），但写错会静默出空列 —— 至少给个 warning。"""
    changes.append({"kind": "warning",
                    "message": f"列名 {binding.partition('.')[2]!r} 无法离线校验（要连库才知道）："
                               "写错不会报错，只会渲染出空列；导出后请核对一下"})


def _warn_summary_column(changes, columns):
    """汇总用错列类型是静默的：文本列上做 sum/count 会得到 0，不报错。

    列类型离线查不到（要连库），所以只能在写的时候提一句，让调用方导出后核对。
    """
    what = f"（{'、'.join(columns)}）" if columns else ""
    changes.append({"kind": "warning",
                    "message": f"汇总列{what}必须是**数值列**：文本列上做 sum/avg 服务端会静默"
                               "得到 0（不报错）；列类型无法离线校验，导出后请核对汇总值"})


def template_cells(config, report_path: str, sheet: str = None) -> dict:
    """`report cell --list`：从模板字节列出单元格（A1 / 值 / 公式 / 绑定 / 扩展 / 样式）。"""
    text = read_template(config, report_path).decode("utf-8")
    rows = cptxml.cell_rows(text, sheet)
    counts = {}
    for row in rows:
        counts[row["kind"]] = counts.get(row["kind"], 0) + 1
    return {"action": "cell-list", "report": _target_path(config, report_path),
            "sheet": sheet or (cptxml.sheet_names(text) or [""])[0],
            "sheets": cptxml.sheet_names(text),
            "count": len(rows), "kinds": counts, "cells": rows,
            "datasets": cptxml.dataset_names(text),
            "parameters": [p["name"] for p in cptxml.template_parameters(text)]}


def edit_cell(config, report_path: str, apply: bool = False, sheet: str = None, **kwargs) -> dict:
    """`report cell`（写）：拉模板 → 改一格 → dry-run diff / --apply 写回。"""
    if apply and not isinstance(config, LocalTemplate):
        _scope(report_path)
    text = read_template(config, report_path).decode("utf-8")
    new_text, changes = plan_cell(text, sheet=sheet, **kwargs)
    return commit(config, report_path, text, new_text, "cell", changes, apply=apply)


# ---------------------------------------------------------------------------
# report dataset
# ---------------------------------------------------------------------------
def plan_dataset(text: str, op: str = None, name: str = None, conn: str = None,
                 sql: str = None, sql_file: str = None, params=(), page_sql: str = "",
                 share: bool = True, template_params: bool = True):
    """增 / 改 SQL / 删数据集（内存计算，不碰网络）。`op` ∈ add / set-sql / remove。

    `--param p=v` **两处都写**：数据集 `<Parameters>`（`${p}` 用）与模板参数
    `ReportParameterAttr`（单元格公式 `$p` 用）。没给默认值的参数会额外报警告 ——
    实测：参数「既没传值、又没默认值」时静默求值成空字符串，导出照成功，
    用户不带参数打开就是空白（最难查的一种坏法）。
    """
    if sql_file:
        sql = Path(sql_file).read_text(encoding="utf-8")
    changes, new_text = [], text
    if op == "remove":
        new_text = cptxml.remove_dataset(new_text, name)
        changes.append({"kind": "dataset.remove", "name": name})
        # 悬空绑定只是告警；聚合报表（PolyWorkSheet）没有普通网格，cptxml.cells()
        # 会 fail closed 抛错，这里跳过告警而不是让删数据集失败（保持 HEAD 语义）。
        try:
            dangling = [c["a1"] for c in cptxml.cells(new_text) if c.get("dataset") == name]
        except ApiError as exc:
            if "聚合报表" not in str(exc):
                raise
            dangling = []
        if dangling:
            changes.append({"kind": "warning",
                            "message": f"仍有 {len(dangling)} 个单元格绑定 {name}"
                                       f"（{', '.join(dangling[:8])}），导出会报错"})
        return new_text, changes

    if op == "add":
        pairs = [param_pair(p) for p in params]
        new_text = cptxml.add_dataset(
            new_text, cptxml.dataset_xml(name, conn or "", sql or "", params=pairs,
                                         page_sql=page_sql, share=share), name)
        changes.append({"kind": "dataset.add", "name": name, "connection": conn,
                        "sql_chars": len((sql or "").strip()),
                        "parameters": [p for p, _ in pairs]})
        if template_params:
            for pname, pdef in pairs:
                new_text, how = cptxml.add_template_parameter(new_text, pname, pdef)
                if how != "unchanged":
                    changes.append({"kind": "template.param", "name": pname,
                                    "default": pdef, "how": how})
        _warn_no_default(changes, pairs)
        _check_sql(changes, new_text, sql or "", name)
        return new_text, changes

    if op == "set-sql":
        target = _dataset(text, name) if name else _one_dataset(text, "--set-sql 要指明数据集名")
        new_text, changes = _replace_sql(text, target, sql, changes)
        pairs = [param_pair(p) for p in params]
        for pname, pdef in pairs:
            new_text, how = cptxml.add_dataset_parameter(new_text, target["name"], pname,
                                                         pdef)
            changes.append({"kind": "dataset.param", "name": pname, "default": pdef,
                            "how": how})
            if template_params:
                new_text, how2 = cptxml.add_template_parameter(new_text, pname, pdef)
                if how2 != "unchanged":
                    changes.append({"kind": "template.param", "name": pname,
                                    "default": pdef, "how": how2})
        _warn_no_default(changes, pairs)
        _check_sql(changes, new_text, sql, target["name"])
        return new_text, changes
    raise ApiError("没有给任何数据集动作（--add NAME / --set-sql NAME / --remove NAME）")


def _check_sql(changes, text: str, sql: str, dataset: str = None):
    """数据集 SQL 里参数的两种静默坏法（实测都不报错）。"""
    sig = cptxml.sql_signature(sql)
    if sig["bare"]:
        changes.append({"kind": "warning",
                        "message": "数据集 SQL 里的参数必须写 `${x}`；裸 `$x` 会被当成字面量"
                                   f"送进 SQL（{'、'.join(sig['bare'][:5])}）"})
    declared = set()
    if dataset:
        hit = [t for t in cptxml.table_datas(text) if t["name"] == dataset]
        if hit:
            declared = {p["name"] for p in hit[0]["parameters"]}
    missing = [n for n in sig["params"] if n not in declared]
    if missing:
        changes.append({"kind": "warning",
                        "message": f"SQL 引用了数据集里没声明的参数 {'、'.join(missing)}："
                                   "不传值时会被替换成空字符串，可能让整条 SQL 语法错"
                                   "（`report datasets` 会报「数据集配置错误」）。"
                                   "用 --param " + f"{missing[0]}=<默认值> 补上"})
    unknown = [n for n in list(declared) if n not in sig["params"]]
    if dataset and unknown:
        changes.append({"kind": "note",
                        "message": f"数据集还声明了 SQL 里没用到的参数：{'、'.join(unknown)}"})


def _warn_no_default(changes, pairs):
    blank = [p for p, d in pairs if not d]
    if blank:
        changes.append({"kind": "warning",
                        "message": f"参数 {', '.join(blank)} 没有默认值：用户不带参数打开时"
                                   "会静默变成空字符串（不报错），建议给 --param "
                                   f"{blank[0]}=<默认值>"})


def param_pair(item):
    """`date` 或 `date=20260101` → (名字, 默认值)。"""
    name, sep, default = str(item).partition("=")
    return name.strip(), (default if sep else "")


def _dataset(text: str, name: str):
    hit = [t for t in cptxml.table_datas(text) if t["name"] == name]
    if not hit:
        raise ApiError(f"模板里没有数据集 {name!r}；现有: "
                       f"{', '.join(cptxml.dataset_names(text)) or '(无)'}")
    return hit[0]


def _one_dataset(text: str, what: str):
    all_ds = cptxml.table_datas(text)
    if len(all_ds) == 1:
        return all_ds[0]
    raise ApiError(f"{what}：模板有 {len(all_ds)} 个数据集，必须指明名字"
                   f"（{', '.join(t['name'] for t in all_ds) or '无'}）")


def _replace_sql(text, target, new_sql, changes):
    if target["sql_element"] is None:
        raise ApiError(f"数据集 {target['name']} 没有 <Query> 元素，无法改 SQL")
    if target["sql"] == new_sql:
        raise ApiError(f"数据集 {target['name']} 的 SQL 与给定内容完全相同，无需修改")
    new_text = cptxml.set_text(text, target["sql_element"], new_sql)
    changes.append({"kind": "dataset.sql", "name": target["name"], "mode": "replace-all",
                    "diff": _text_diff(target["sql"], new_sql, f"{target['name']}.sql")})
    return new_text, changes


def edit_dataset(config, report_path: str, apply: bool = False, **kwargs) -> dict:
    if apply and not isinstance(config, LocalTemplate):
        _scope(report_path)
    text = read_template(config, report_path).decode("utf-8")
    new_text, changes = plan_dataset(text, **kwargs)
    return commit(config, report_path, text, new_text, "dataset", changes, apply=apply)


def template_datasets(config, report_path: str, sql: bool = False) -> dict:
    """`report dataset --list`：从**模板字节**读数据集（不是 `format=cpt` 提取物）。"""
    text = read_template(config, report_path).decode("utf-8")
    tds = cptxml.table_datas(text)
    return {"action": "dataset-list", "report": _target_path(config, report_path),
            "count": len(tds), "datasets": [
                {"name": t["name"], "class": t["class"].rsplit(".", 1)[-1],
                 "connection": t["connection"],
                 "parameters": {p["name"]: p["default"] for p in t["parameters"]},
                 "sql": (t["sql"] or "").strip() if sql else None,
                 "sql_chars": len((t["sql"] or "").strip())} for t in tds],
            "template_parameters": {p["name"]: p["default"]
                                    for p in cptxml.template_parameters(text)}}


# ---------------------------------------------------------------------------
# report param（模板参数；决定 `$x` 能不能在单元格公式里解析）
# ---------------------------------------------------------------------------
def plan_param(text: str, add=(), remove=(), set_default=(), set_formula=()):
    """模板参数（`ReportParameterAttr > Parameters`）的增删改（内存计算）。"""
    changes, new_text = [], text
    static_names = {param_pair(item)[0].casefold() for item in (*add, *set_default)}
    formula_pairs = []
    for item in set_formula:
        name, sep, formula = str(item).partition("=")
        name = name.strip()
        if not sep or not name:
            raise ApiError(f"--set-formula 要写成 NAME=EXPR，收到 {item!r}")
        if name.casefold() in static_names:
            raise ApiError(f"参数 {name} 的静态默认值与公式默认值不能同时设置")
        formula_pairs.append((name, cptxml.check_formula(formula)))
    for item in remove:
        new_text, _ = cptxml.remove_template_parameter(new_text, item)
        changes.append({"kind": "param.remove", "name": item})
    for item in add:
        name, default = param_pair(item)
        new_text, how = cptxml.add_template_parameter(new_text, name, default)
        changes.append({"kind": "param.add", "name": name, "default": default, "how": how})
        _warn_no_default(changes, [(name, default)])
    for item in set_default:
        name, sep, default = str(item).partition("=")
        if not sep:
            raise ApiError(f"--set-default 要写成 NAME=VALUE，收到 {item!r}")
        new_text, how = cptxml.add_template_parameter(new_text, name, default)
        changes.append({"kind": "param.default", "name": name, "default": default, "how": how})
    for name, formula in formula_pairs:
        new_text, how = cptxml.add_template_parameter(new_text, name, formula=formula)
        changes.append({"kind": "param.formula", "name": name, "default": formula,
                        "default_type": "formula", "how": how})
    for _, formula in formula_pairs:
        _warn_formula(changes, new_text, formula)
    if not changes:
        raise ApiError("没有给任何参数动作（--add / --remove / --set-default / --set-formula）")
    return new_text, changes


def edit_param(config, report_path: str, apply: bool = False, **kwargs) -> dict:
    if apply and not isinstance(config, LocalTemplate):
        _scope(report_path)
    text = read_template(config, report_path).decode("utf-8")
    new_text, changes = plan_param(text, **kwargs)
    return commit(config, report_path, text, new_text, "param", changes, apply=apply)


def template_params(config, report_path: str) -> dict:
    text = read_template(config, report_path).decode("utf-8")
    params = cptxml.template_parameters(text)
    return {"action": "param-list", "report": _target_path(config, report_path),
            "count": len(params),
            "parameters": [{k: p[k] for k in ("name", "default", "default_type")} for p in params],
            "datasets": cptxml.dataset_names(text),
            "note": "单元格公式里 `$名字` 解析的就是这里的声明（同名参数会被 --params 覆盖）；"
                    "数据集 SQL 里的 `${名字}` 看数据集自己的 <Parameters>"}


# ---------------------------------------------------------------------------
# report style（样式表；数字格式 / 粗体 / 底色 / 边框）
# ---------------------------------------------------------------------------
def plan_style(text: str, xml_file: str = None, xml: str = None):
    if xml_file:
        xml = Path(xml_file).read_text(encoding="utf-8")
    if not xml:
        raise ApiError("要加样式必须给 --xml-file（或内置参数生成）")
    new_text, index = cptxml.append_style(text, xml)
    return new_text, [{"kind": "style.add", "index": index,
                       "bytes": len(xml.encode("utf-8")),
                       "preview": xml.strip().splitlines()[0][:80]}]


def plan_style_preset(text: str, fmt: str = None, bold: bool = False, bg: str = None,
                      align: str = None, border: bool = False, size_pt: float = None):
    # ⚠ `--size-pt` 也要算"给了一项"：以前它默认 9 且被排除在校验外，
    # 于是「只改字号」的样式根本建不出来（报"至少要给一项"）。
    if not any([fmt, bold, bg, align, border, size_pt]):
        raise ApiError("新建样式至少要给一项：--format / --bold / --bg / --align / --border / --size-pt")
    xml = cptxml.style_xml(fmt=fmt, bold=bold, bg=bg, align=align, border=border,
                           size_pt=size_pt or 9)
    new_text, index = cptxml.append_style(text, xml)
    return new_text, [{"kind": "style.add", "index": index, "format": fmt,
                       "bold": bool(bold), "bg": bg, "align": align,
                       "border": bool(border), "size_pt": size_pt or 9}]


def edit_style(config, report_path: str, apply: bool = False, preset=False, **kwargs) -> dict:
    if apply and not isinstance(config, LocalTemplate):
        _scope(report_path)
    text = read_template(config, report_path).decode("utf-8")
    new_text, changes = (plan_style_preset(text, **kwargs) if preset
                         else plan_style(text, **kwargs))
    return commit(config, report_path, text, new_text, "style", changes, apply=apply)


def plan_sheet(text: str, action: str, name: str = None, new_name: str = None,
               clone_from: str = None):
    """sheet 增删改（内存计算）。action: list / add / rename / remove"""
    before = cptxml.sheet_names(text)
    if action == "list":
        return text, [{"kind": "sheet.list", "sheets": before}]
    if action == "add":
        text, added = cptxml.add_sheet(text, name, clone_from=clone_from)
        return text, [{"kind": "sheet.add", "name": added, "clone_from": clone_from or before[0],
                       "sheets": cptxml.sheet_names(text)}]
    if action == "rename":
        from .cpttransform import plan_sheet as transform_sheet
        text, _changes, _validation = transform_sheet(text, name, new_name=new_name)
        return text, [{"kind": "sheet.rename", "from": name, "to": new_name,
                       "sheets": cptxml.sheet_names(text)}]
    if action == "remove":
        from .cpttransform import plan_sheet as transform_sheet
        text, _changes, _validation = transform_sheet(text, name, remove=True)
        return text, [{"kind": "sheet.remove", "name": name, "sheets": cptxml.sheet_names(text)}]
    raise ApiError(f"不认识的 sheet 操作 {action!r}")


def edit_sheet(config, report_path: str, apply: bool = False, action: str = None, **kwargs) -> dict:
    if apply and not isinstance(config, LocalTemplate):
        _scope(report_path)
    text = read_template(config, report_path).decode("utf-8")
    new_text, changes = plan_sheet(text, action, **kwargs)
    return commit(config, report_path, text, new_text, "sheet", changes, apply=apply)


def template_styles(config, report_path: str) -> dict:
    text = read_template(config, report_path).decode("utf-8")
    items = cptxml.styles(text)
    return {"action": "style-list", "report": _target_path(config, report_path),
            "count": len(items),
            "styles": [{k: v for k, v in s.items() if k != "xml"} for s in items],
            "note": "单元格 `s=\"n\"` 引用的就是这个列表的第 n 个（0 起）"}


# ---------------------------------------------------------------------------
# report table（一次生成整张取数表）
# ---------------------------------------------------------------------------
def plan_table(text: str, dataset: str, at: str, columns, header: bool = False,
               labels=None, expand: str = "v", style=None, header_style=None,
               widths=None, mode: str = "list", fn: str = None, group_by=None,
               sheet: str = None):
    """在 `--at` 处生成「表头 + 逐列绑定 + 扩展 + 数据设置」的整张表（内存计算）。

    `--mode` 三选一（**默认 list**，见 cpt-features.md §1 为什么不是 group）：
    - `list`：每列都是列表（`<Attr divideMode="1"/>`）——记录原样展开，不合并、不聚合
    - `group`：每列都是分组（`FunctionGrouper` 自闭合）——相同值合并
    - `summary`：`--group-by` 的列保持分组，其余列汇总（`--fn`，默认 sum）；
      汇总格自动用 `<Expand/>`（一个汇总值不扩展），分组格用 `--expand`

    `sheet` 指定写哪一张 sheet（多 sheet 模板）；不给 = 第一张（与历史行为一致）。
    sheet 名不存在时由 `cptxml.pick_sheet` 报出全部现有 sheet 名。
    """
    _dataset(text, dataset)
    cols = [str(c).strip() for c in columns]
    cols = [c.partition(".")[2] if c.partition(".")[0] == dataset else c for c in cols]
    cols = [c for c in cols if c]
    if not cols:
        raise ApiError("--columns 至少要给一列（逗号分隔，如 k,val）")
    if len(set(cols)) != len(cols):
        raise ApiError(f"--columns 里有重复列名: {', '.join(cols)}")
    if expand not in ("v", "h", "none"):
        raise ApiError(f"--expand 只能是 v(纵向) / h(横向) / none，收到 {expand!r}")
    mode = cptxml.check_ds_mode(mode, fn)
    dims = [str(x).strip() for x in (group_by or []) if str(x).strip()]
    if dims and mode != "summary":
        raise ApiError(f"--group-by 只在 --mode summary 时有意义（当前 --mode {mode}）："
                       "group/list 模式下每一列都是同一形态")
    if len(set(dims)) != len(dims):
        raise ApiError(f"--group-by 里有重复列名: {', '.join(dims)}")
    unknown = [d for d in dims if d not in cols]
    if unknown:
        raise ApiError(f"--group-by 的列 {', '.join(unknown)} 不在 --columns 里"
                       f"（--columns: {', '.join(cols)}）")
    if dims and len(dims) == len(cols):
        raise ApiError("--group-by 覆盖了全部列，没有列会被汇总；少给一个分组列，"
                       "或去掉 --mode summary")
    if fn is not None:
        cptxml.check_summary_fn(fn)                  # 非法函数名就地报错
    if labels:
        labels = [str(x).strip() for x in labels]
        if len(labels) != len(cols):
            raise ApiError(f"--labels 给了 {len(labels)} 个，--columns 有 {len(cols)} 列，"
                           "数量必须一致")
    c0, r0 = cptxml.parse_a1(at)
    if widths:
        try:
            widths = [float(x) for x in widths]
        except (TypeError, ValueError) as e:
            raise ApiError(
                f"--widths 只能是数字（列宽字符数，逗号分隔），收到 {widths!r}：{e}") from e
        if len(widths) != len(cols):
            raise ApiError(f"--widths 给了 {len(widths)} 个，--columns 有 {len(cols)} 列，"
                           "数量必须一致")
    cptxml.check_style_index(text, style)
    cptxml.check_style_index(text, header_style, "--header-style")
    row = r0 + (1 if header else 0)
    changes, new_text = [], text
    for i, col in enumerate(cols):
        if header:
            new_text, _ = cptxml.put_cell(
                new_text, cptxml.format_a1(c0 + i, r0),
                cptxml.cell_xml(c0 + i, r0, value=(labels[i] if labels else col),
                                style=header_style), sheet)
        if mode == "summary":
            col_mode = "group" if col in dims else "summary"
        else:
            col_mode = mode
        # 汇总格不扩展（一个汇总值就是一行）；分组/列表格才吃 --expand
        col_expand = "none" if col_mode == "summary" else expand
        new_text, info = cptxml.put_cell(
            new_text, cptxml.format_a1(c0 + i, row),
            cptxml.cell_xml(c0 + i, row, binding=f"{dataset}.{col}", expand=col_expand,
                            style=style, ds_mode=col_mode,
                            ds_fn=(fn or "sum") if col_mode == "summary" else None), sheet)
        change = {"kind": f"cell.{info['action']}", "at": cptxml.format_a1(c0 + i, row),
                  "binding": f"{dataset}.{col}", "expand": col_expand,
                  "ds_mode": col_mode}
        if col_mode == "summary":
            change["ds_fn"] = fn or "sum"
        changes.append(change)
    if header:
        changes.insert(0, {"kind": "table.header", "at": at, "columns": len(cols),
                           "labels": labels or cols})
    changes.append({"kind": "table", "dataset": dataset, "at": at, "columns": cols,
                    "header": bool(header), "expand": expand, "mode": mode,
                    "group_by": dims or None, "fn": (fn or "sum") if mode == "summary" else None})
    changes.append({"kind": "warning",
                    "message": f"列名（{'、'.join(cols)}）不做离线校验（要连库才知道）：写错不会"
                               "报错，只会渲染出空列；导出后请核对"})
    if mode == "summary":
        _warn_summary_column(changes, [c for c in cols if c not in dims])
    if widths:
        new_text = cptxml.set_col_widths(new_text,
                                         {c0 + i: w for i, w in enumerate(widths)},
                                         sheet=sheet)
        changes.append({"kind": "col_width",
                        "cols": [cptxml.format_a1(c0 + i, 0).rstrip("0123456789")
                                 for i in range(len(widths))],
                        "chars": widths})
    return new_text, changes


def edit_table(config, report_path: str, apply: bool = False, **kwargs) -> dict:
    if apply and not isinstance(config, LocalTemplate):
        _scope(report_path)
    text = read_template(config, report_path).decode("utf-8")
    new_text, changes = plan_table(text, **kwargs)
    return commit(config, report_path, text, new_text, "table", changes, apply=apply)


# ---------------------------------------------------------------------------
# 条件属性 `<Highlight>`（report highlight）
# ---------------------------------------------------------------------------
def _expand_targets(at: str, sheet: str = None):
    """`--at` 支持单格 `D3` 或区域 `A3:D3`（整行条件属性就这么写）。"""
    c1, r1, c2, r2 = cptxml.parse_range(at)
    return [cptxml.format_a1(c, r) for r in range(r1, r2 + 1) for c in range(c1, c2 + 1)]


def plan_highlight(text: str, at: str, sheet: str = None, rules=(), clear: bool = False):
    """给一个/一片单元格写条件属性（内存计算）。

    rules: `[(条件, 动作, 名字)]`，条件见 `cptxml.condition_xml`（`v>100` / 公式），
    动作见 `cptxml.highlight_action_xml`（`bg=#FFC7CE,bold` 这种）。
    """
    changes = []
    targets = _expand_targets(at, sheet)
    if not targets:
        raise ApiError(f"--at 至少要给一个格子，收到 {at!r}")
    if clear:
        hit = []
        for a1 in targets:
            cell = cptxml.find_cell(text, a1, sheet)
            if cell is None or not cell.get("hl_count"):
                continue
            text = cptxml.set_highlight_list(text, cell, "")
            hit.append(a1)
        if not hit:
            raise ApiError(f"{at} 上本来就没有条件属性，不需要 --clear")
        changes.append({"kind": "highlight.clear", "at": hit})
        return text, changes
    if not rules:
        raise ApiError("没有给 --rule（例：--rule 'v>100:bg=#FFC7CE,fg=#9C0006'）")
    norm = []
    for i, rule in enumerate(rules):
        if isinstance(rule, str):
            cond, _, act = rule.partition(":")
            name = f"条件属性{i + 1}"
        else:
            cond, act, name = rule
            name = name or f"条件属性{i + 1}"
        if not cond.strip() or not act.strip():
            raise ApiError(f"--rule 要写成 `条件:动作`，收到 {rule!r}")
        cptxml.condition_xml(cond)                   # 提前触发本地校验
        cptxml.highlight_action_xml(act)
        norm.append((cond, act, name))
    # 字体动作继承目标格现有字号：FRFont 是整体替换，不带 size 会变 0 号字（整行看不见）
    inherit = None
    for a1 in targets:
        cell = cptxml.find_cell(text, a1, sheet)
        if cell is not None:
            inherit = cptxml.cell_font_size(text, cell, sheet)
            if inherit:
                break
    snippet = cptxml.highlight_list_xml(norm, inherit_size=inherit)
    missing = []
    dropped = 0
    for a1 in targets:
        cell = cptxml.find_cell(text, a1, sheet)
        if cell is None:
            missing.append(a1)
            continue
        dropped += cell.get("hl_count") or 0
        text = cptxml.set_highlight_list(text, cell, snippet)
    if len(missing) == len(targets):
        raise ApiError(f"{at} 里没有单元格：条件属性只能挂在已有单元格上"
                       "（先用 report cell / report table 造出格子）")
    changes.append({"kind": "highlight.set", "at": targets, "rules": [
        {"when": c, "then": a, "name": n} for c, a, n in norm]})
    if missing:
        changes.append({"kind": "warning",
                        "message": f"{at} 里这些格子还不存在，已跳过: {', '.join(missing)}"})
    if dropped:
        # `--rule` 的语义是**设置**（整表替换），不是追加 —— 静默冲掉旧规则会让人以为"两条都在"
        changes.append({"kind": "warning",
                        "message": f"⚠ 这些格子上原有的 {dropped} 条条件属性被**整表替换**掉了"
                                   "（`--rule` 是设置语义，不是追加）。要保留旧规则就把它们"
                                   "写进同一次调用的多个 `--rule`，顺序即优先级。"})
    return text, changes


def edit_highlight(config, report_path: str, apply: bool = False, **kwargs) -> dict:
    if apply and not isinstance(config, LocalTemplate):
        _scope(report_path)
    text = read_template(config, report_path).decode("utf-8")
    new_text, changes = plan_highlight(text, **kwargs)
    return commit(config, report_path, text, new_text, "highlight", changes, apply=apply)


def template_highlights(config, report_path: str, at: str = None, sheet: str = None) -> dict:
    """`report highlight --list`：列出模板里的条件属性（不联网写）。"""
    text = read_template(config, report_path).decode("utf-8")
    out = []
    for cell in cptxml.cells(text, sheet):
        if at:
            targets = _expand_targets(at, sheet)
            if cell["a1"] not in targets:
                continue
        if not cell["hl_count"]:
            continue
        out.append({"at": cell["a1"], "kind": cell["kind"],
                    "binding": cell["binding"], "value": cell.get("text"),
                    "formula": cell.get("formula"),
                    "highlights": [{"name": h["name"],
                                    "when": cptxml.condition_spec(h["condition"]),
                                    "then": [cptxml.highlight_action_spec(a)
                                             for a in h["actions"]]}
                                   for h in cell["highlights"]]})
    return {"action": "highlight-list", "report": _target_path(config, report_path),
            "sheet": sheet or (cptxml.sheet_names(text) or [""])[0],
            "count": len(out), "cells": out}


# ---------------------------------------------------------------------------
# 参数面板控件（report widget）
# ---------------------------------------------------------------------------
def plan_widget(text: str, param: str, kind: str = "combo", options=(), default: str = None,
                label: str = None, x: int = 30, y: int = 20, width: int = 120,
                height: int = 21, declare: bool = True, default_formula: str = None):
    """给模板加一个参数面板控件（`<ParameterUI>` + `<Widget>`，内存计算）。

    控件名 = 参数名（服务端 `getWidgetByName(parameter.getName())` 就是这么找的），
    所以 `--param p` 必须与模板参数（以及 SQL 里的 `${p}`）同名才联动。
    """
    cptxml.check_widget_type(kind)
    if default is not None and default_formula is not None:
        raise ApiError("--default 与 --default-formula 只能给一个")
    if default_formula is not None:
        default_formula = cptxml.check_formula(default_formula)
    changes = []
    if declare:
        names = [p["name"] for p in cptxml.template_parameters(text)]
        if param not in names:
            text, how = cptxml.add_template_parameter(text, param, default=default,
                                                      formula=default_formula)
            changes.append({"kind": "param.add", "param": param,
                            "default": default_formula if default_formula is not None else (default or ""),
                            "how": how})
        elif default is not None or default_formula is not None:
            text, how = cptxml.add_template_parameter(text, param, default=default,
                                                      formula=default_formula)
            changes.append({"kind": "param.default", "param": param,
                            "default": default_formula if default_formula is not None else default,
                            "how": how})
    text, info = cptxml.add_panel_widget(text, param, kind=kind, options=options,
                                         default=default, label=label, x=x, y=y,
                                         width=width, height=height, default_formula=default_formula)
    changes.append({"kind": "widget.set", **info})
    if default_formula is not None:
        _warn_formula(changes, text, default_formula)
        for warning in formulas.analyze_formula(default_formula, context="widget")["warnings"]:
            if warning["code"] == "unsupported_widget_dataset":
                changes.append({"kind": "warning", **warning})
    changes.append({"kind": "warning",
                    "message": "参数面板是**预览态 UI**：导出通道只验证「参数仍生效」，"
                               "控件是否渲染要打开预览页看；XML 结构已与官方样例逐节点对齐"})
    return text, changes


def edit_widget(config, report_path: str, apply: bool = False, **kwargs) -> dict:
    if apply and not isinstance(config, LocalTemplate):
        _scope(report_path)
    text = read_template(config, report_path).decode("utf-8")
    new_text, changes = plan_widget(text, **kwargs)
    return commit(config, report_path, text, new_text, "widget", changes, apply=apply)


def template_widgets(config, report_path: str) -> dict:
    """`report widget --list`：列出参数面板控件。"""
    text = read_template(config, report_path).decode("utf-8")
    return {"action": "widget-list", "report": _target_path(config, report_path),
            "has_panel": cptxml.panel_element(text) is not None,
            "count": len(cptxml.panel_widgets(text)),
            "widgets": cptxml.panel_widgets(text),
            "parameters": [p["name"] for p in cptxml.template_parameters(text)]}


# ---------------------------------------------------------------------------
# 超链接（report link）
# ---------------------------------------------------------------------------
def plan_link(text: str, at: str, to: str = None, kind: str = "reportlet", params=(),
              frame: str = "_self", name: str = "超链接1", clear: bool = False,
              sheet: str = None):
    """给单元格挂/摘超链接（`HyperlinkHighlightAction`，内存计算）。

    已有条件属性时**追加**一条无条件 `<Highlight>`（不覆盖原有高亮）；`--clear` 只摘超链接。
    """
    changes = []
    targets = _expand_targets(at, sheet)
    hit = []
    for a1 in targets:
        cell = cptxml.find_cell(text, a1, sheet)
        if cell is None:
            continue
        links = cell.get("links") or []
        if clear:
            if not links:
                continue
            # 单元格级 `<NameJavaScriptGroup>` 与条件属性形态都要摘掉（偏移会变，逐条重扫）
            while True:
                removed = False
                cur = cptxml.find_cell(text, a1, sheet)
                for grp in cptxml._sub_elements(text, cur["element"],
                                                "NameJavaScriptGroup", path=()):
                    text = cptxml.delete_cell_child(text, grp)
                    removed = True
                    break
                if not removed:
                    for hl_el in cptxml._sub_elements(text, cur["element"], "HighlightList",
                                                      path=()):
                        for one in cptxml._sub_elements(text, hl_el, "Highlight", path=()):
                            if "HyperlinkHighlightAction" in text[one.open_start:one.close_end]:
                                text = cptxml.delete_cell_child(text, one)
                                removed = True
                                break
                        if removed:
                            break
                if not removed:
                    break
            cur = cptxml.find_cell(text, a1, sheet)
            for hl_el in cptxml._sub_elements(text, cur["element"], "HighlightList", path=()):
                if "<Highlight " not in text[hl_el.open_end:hl_el.close_start]:
                    text = cptxml.delete_cell_child(text, hl_el)
            hit.append(a1)
            continue
        snippet = cptxml.hyperlink_group_xml(kind, to or "", params=params, frame=frame,
                                             name=name)
        text = cptxml.set_cell_child(text, cell, "NameJavaScriptGroup", snippet,
                                     cptxml.CELL_CHILD_ORDER)
        hit.append(a1)
    if not hit:
        raise ApiError(f"{at} 里没有可挂超链接的单元格"
                       if not clear else f"{at} 上本来就没有超链接")
    changes.append({"kind": "link.clear" if clear else "link.set", "at": hit,
                    "type": kind, "target": to, "params": [list(p) for p in params],
                    "frame": frame})
    changes.append({"kind": "note",
                    "message": "超链接是**纯预览态交互**：导出 xlsx/pdf **零痕迹**"
                               "（实测 sheet1.xml 无 <hyperlink>、pdf 无 /URI|/Annots），"
                               "验收只能读模板：`report link --list`"})
    return text, changes


def edit_link(config, report_path: str, apply: bool = False, **kwargs) -> dict:
    if apply and not isinstance(config, LocalTemplate):
        _scope(report_path)
    text = read_template(config, report_path).decode("utf-8")
    new_text, changes = plan_link(text, **kwargs)
    return commit(config, report_path, text, new_text, "link", changes, apply=apply)


def template_links(config, report_path: str, at: str = None, sheet: str = None) -> dict:
    """`report link --list`：列出模板里的超链接。"""
    text = read_template(config, report_path).decode("utf-8")
    out = []
    for cell in cptxml.cells(text, sheet):
        if not cell.get("links"):
            continue
        if at and cell["a1"] not in _expand_targets(at, sheet):
            continue
        out.append({"at": cell["a1"], "value": cell.get("text"), "binding": cell.get("binding"),
                    "links": cell["links"]})
    return {"action": "link-list", "report": _target_path(config, report_path),
            "sheet": sheet or (cptxml.sheet_names(text) or [""])[0],
            "count": len(out), "cells": out}


# ---------------------------------------------------------------------------
# 图表（report chart）
# ---------------------------------------------------------------------------
def plan_chart(text: str, at: str, dataset: str, kind: str = "column", category: str = None,
               series: str = None, value: str = None, fn: str = "sum", title: str = None,
               show_title: bool = False, cs: int = None, rs: int = None, sheet: str = None):
    """在 `at` 处插入一个图表单元格（`<O t="CC">` + VanChart，内存计算）。

    图表是 `CellElementList` 里的**一个格子**（用 `cs`/`rs` 占多列多行），数据源 =
    `<ChartDefinition>` 绑到数据集列。类型见 `chartxml.CHART_TYPES`。
    `title` 不给且 `show_title=False` ⇒ 写 `TitleVisible=false` 的空标题块
    （**不写标题块服务端会给默认标题「新建图表标题」**，实测）。
    """
    _dataset(text, dataset)
    key = chartxml.check_chart_type(kind)
    if not category:
        raise ApiError("图表要 --category 分类轴列（饼图=扇区列）")
    if not value:
        raise ApiError("图表要 --value 数值列")
    chartxml.check_chart_fn(fn)
    c, r = cptxml.parse_a1(at)
    existing = cptxml.find_cell(text, at, sheet)
    if existing is not None and existing.get("kind") != "empty":
        raise ApiError(f"{at} 已经有内容（{existing.get('kind')}）；图表要占一整片区域，"
                       "换一个空格子（或用 report cell --clear 先清掉）")
    snippet = chartxml.chart_cell_xml(key, dataset, category, series=series, value=value,
                                      fn=fn, title=title if show_title else None,
                                      c=c, r=r, cs=cs, rs=rs)
    new_text, info = cptxml.put_cell(text, at, snippet, sheet)
    changes = [{"kind": "chart.insert" if info["action"] == "insert" else "chart.replace",
                "at": at, "type": key, "dataset": dataset, "category": category,
                "series": series, "value": value, "fn": fn, "cs": cs, "rs": rs,
                "title": title if show_title else None}]
    changes.append({"kind": "warning",
                    "message": "列名（category/series/value）不做离线校验（要连库才知道）：写错不报错，"
                               "只会画出空图/错图；必须 export image 或 pdf 看图验收"})
    return new_text, changes


def edit_chart(config, report_path: str, apply: bool = False, **kwargs) -> dict:
    if apply and not isinstance(config, LocalTemplate):
        _scope(report_path)
    text = read_template(config, report_path).decode("utf-8")
    new_text, changes = plan_chart(text, **kwargs)
    return commit(config, report_path, text, new_text, "chart", changes, apply=apply)


def template_charts(config, report_path: str, sheet: str = None) -> dict:
    """`report chart --list`：列出模板里的图表（类型/数据源/列绑定）。"""
    text = read_template(config, report_path).decode("utf-8")
    out = []
    for cell in cptxml.cells(text, sheet):
        el = cell["element"]
        raw = text[el.open_start:el.close_end]
        if "<ChartDefinition>" not in raw:
            continue
        out.append({"at": cell["a1"],
                    "type": chartxml.detect_type(raw),
                    "definition": chartxml.parse_definition(raw)})
    return {"action": "chart-list", "report": _target_path(config, report_path),
            "sheet": sheet or (cptxml.sheet_names(text) or [""])[0],
            "count": len(out), "charts": out}


# ---------------------------------------------------------------------------
# 分页设置（report page）
# ---------------------------------------------------------------------------
def plan_page(text: str, sheet: str = None, header_height: float = None,
              footer_height: float = None, freeze: str = None, repeat_rows=None,
              no_repeat_rows=None, repeat_header_rows=None, repeat_footer_rows=None,
              repeat_header_cols=None, repeat_footer_cols=None, page_freeze=None,
              header_text=None, footer_text=None, header_position: str = "center",
              footer_position: str = "center", header_formula: bool = False,
              footer_formula: bool = False):
    """写报表级分页设置 + 单元格级 `CellPageAttr`（内存计算）。

    `--repeat-header-rows 1:1` → `<ReportPageAttr><HR F="1" T="1"/></ReportPageAttr>`
    （0 基、闭区间；**这才是"每页重复标题行"**，实测 120 行报表 PDF 6 页 → 7 页）。
    """
    changes = []
    text, ch = cptxml.set_page_settings(text, sheet, header_height_pt=header_height,
                                        footer_height_pt=footer_height, frozen=freeze)
    changes += ch
    for spec, key in ((repeat_header_rows, "HR"), (repeat_footer_rows, "FR"),
                      (repeat_header_cols, "HC"), (repeat_footer_cols, "FC")):
        if spec is None:
            continue
        text, ch = cptxml.set_repeat_region(text, key, spec, sheet)
        changes.append(ch)
    if page_freeze is not None:
        text, ch = cptxml.set_page_freeze(text, page_freeze, sheet)
        changes.append(ch)
    if header_text is not None:
        txt = header_text if (header_formula or header_text.startswith("=")) else f'"{header_text}"'
        text, ch = cptxml.set_header_footer(text, "header", header_position, txt, sheet=sheet)
        changes += ch if isinstance(ch, list) else [ch]
    if footer_text is not None:
        txt = footer_text if (footer_formula or footer_text.startswith("=")) else f'"{footer_text}"'
        text, ch = cptxml.set_header_footer(text, "footer", footer_position, txt, sheet=sheet)
        changes += ch if isinstance(ch, list) else [ch]
    for spec, flag in ((repeat_rows, True), (no_repeat_rows, False)):
        if not spec:
            continue
        rows = [int(x) for x in str(spec).replace(" ", "").split(",") if x]
        hit = 0
        for r in rows:
            if r < 1:
                raise ApiError(f"--repeat-rows/--no-repeat-rows 用**Excel 行号**（从 1 起），收到 {r}")
            for cell in cptxml.cells(text, sheet):
                if cell["r"] == r - 1:
                    text = cptxml.set_cell_page_attr(text, cell, repeat=flag)
                    hit += 1
        if not hit:
            raise ApiError(f"第 {rows} 行没有任何单元格，改不了分页属性")
        changes.append({"kind": "page.repeat", "rows": rows, "repeat": flag, "cells": hit})
    if not changes:
        raise ApiError("没有给任何分页动作（--header-height / --footer-height / --freeze / "
                       "--repeat-rows / --no-repeat-rows / --repeat-header-rows / "
                       "--header-text / --footer-text / --page-freeze 等）")
    changes.append({"kind": "note",
                    "message": "`<CellPageAttr repeat>` **缺省就是 true**（服务端字段初值 63 全位）："
                               "「没写」= 允许重复，只有 `repeat=\"false\"` 才是关闭；"
                               "每页重复标题用 --repeat-header-rows/--repeat-header-cols（0 基闭区间）；"
                               "页眉页脚内容用 --header-text/--footer-text 写入"})
    return text, changes


def edit_page(config, report_path: str, apply: bool = False, **kwargs) -> dict:
    if apply and not isinstance(config, LocalTemplate):
        _scope(report_path)
    text = read_template(config, report_path).decode("utf-8")
    new_text, changes = plan_page(text, **kwargs)
    return commit(config, report_path, text, new_text, "page", changes, apply=apply)


def template_page(config, report_path: str, sheet: str = None) -> dict:
    """`report page --list`：读分页设置（不联网写）。"""
    text = read_template(config, report_path).decode("utf-8")
    info = cptxml.page_settings(text, sheet)
    rows = {}
    for cell in cptxml.cells(text, sheet):
        spec = cptxml.cell_page_attr_spec(text, cell)
        if spec.get("present") or not spec.get("repeat", True):
            rows.setdefault(cell["r"] + 1, []).append(spec)
    return {"action": "page-list", "report": _target_path(config, report_path),
            "sheet": sheet or (cptxml.sheet_names(text) or [""])[0],
            "settings": info,
            "cells_with_page_attr": {str(k): v for k, v in sorted(rows.items())}}


# ---------------------------------------------------------------------------
# 交叉表（report crosstab）
# ---------------------------------------------------------------------------
#: 交叉表四类格（Lead 实测闭环，出处 docs/探索/cpt服务端模型-逆向.md §5.6）
CROSSTAB_NOTE = ("交叉表不需要显式父子格：引擎自动把「最近的上方扩展格」当列父格、"
                 "「左侧扩展格」当行父格，交叉积就出来了")


def plan_crosstab(text: str, dataset: str, at: str, rows, cols, values,
                  agg: str = None, total_row: bool = False, total_col: bool = False,
                  header: bool = True, labels=None, value_labels=None,
                  style=None, header_style=None, widths=None, total_label: str = "总计：",
                  sheet: str = None):
    """在 `--at` 处生成一张交叉表（行维度纵向 × 列维度横向 × 值汇总）。

    版面（照官方 `demo/NewbieGuide/交叉报表.cpt` 的形态，Lead 已实测跑通）：

        | 角标(A:B合并)      | 列维度(横向扩展) | 汇总列 |
        | 行维度1 | 行维度2 | 值格(交叉点)     | 汇总值 |
        | 总计：(合并行维度) |          | 列总计公式 |

    四类格的关键写法（**值格不能放在列维度右边，否则列维度和行维度不会交叉** —— 实测踩过）：
      ① 列维度：`FunctionGrouper` + `<Expand dir="1"/>`（写在**表头行**，决定有几个列）
      ② 行维度：`FunctionGrouper` + `<Expand dir="0"/>`
      ③ 值格  ：与列维度**同一列**、在数据行，`<Expand/>`（不写方向 ⇒ 隐式继承上/左父格 = 交叉点）
      ④ 汇总列：`SummaryGrouper` + `<FN>` + `<Expand/>`（一行一个值，在列维度右边一列）
    `--agg` 只影响**值格**的 Grouper：不给 = `FunctionGrouper`（官方做法）；
    给了 = `SummaryGrouper`+`<FN>`（同一交叉点多条记录时按它聚合）。
    """
    _dataset(text, dataset)
    rows = [str(x).strip() for x in rows if str(x).strip()]
    cols = [str(x).strip() for x in cols if str(x).strip()]
    values = [str(x).strip() for x in values if str(x).strip()]
    if not rows:
        raise ApiError("--row 至少要给一个行维度列")
    if not cols:
        raise ApiError("--col 至少要给一个列维度列")
    if not values:
        raise ApiError("--value 至少要给一个数值列")
    if len(values) > 1:
        raise ApiError(
            "一次只支持一个 --value 指标：多指标在交叉表里要靠「值格竖排 + 行维度 rs 合并」"
            "手工叠加，CLI 不猜这个版面；请先造单指标交叉表，再按 cpt-patterns.md 手工加第二个值格"
            f"（收到: {', '.join(values)}）")
    dims = rows + cols
    dup = [d for d in set(dims + values) if (dims + values).count(d) > 1]
    if dup:
        raise ApiError(f"行/列/值里有重复列名: {', '.join(sorted(dup))}")
    if agg is not None:
        cptxml.check_summary_fn(agg)
    if value_labels and len(value_labels) != len(values):
        raise ApiError(f"--value-labels 给了 {len(value_labels)} 个，--value 有 {len(values)} 个")
    if widths:
        try:
            widths = [float(x) for x in widths]
        except (TypeError, ValueError) as e:
            raise ApiError(f"--widths 只能是数字，收到 {widths!r}：{e}") from e
    cptxml.check_style_index(text, style)
    cptxml.check_style_index(text, header_style)

    c0, r0 = cptxml.parse_a1(at)
    hdr = r0
    data = r0 + 1 if header else r0
    nv = len(values)
    tot = data + nv if total_row else None
    ncol = len(rows) + 1 + (1 if total_col else 0)
    vcol = c0 + len(rows)                      # 值格与列维度同列
    changes, new_text = [], text

    def put(a1, **kw):
        nonlocal new_text
        c, r = cptxml.parse_a1(a1)
        new_text, _ = cptxml.put_cell(new_text, a1, cptxml.cell_xml(c, r, **kw), sheet)

    # ① 列维度（表头行的横向扩展格）
    for i, col in enumerate(cols):
        if header:
            put(cptxml.format_a1(c0 + len(rows) + i, hdr), binding=f"{dataset}.{col}",
                expand="h", style=header_style, ds_mode="group")
    # 角标（占住行维度那几列）
    if header:
        corner = labels[0] if labels else " \\ ".join(["/".join(rows), "/".join(cols)])
        put(cptxml.format_a1(c0, hdr), value=corner, style=header_style)
        if len(rows) > 1:
            new_text, _ = cptxml.set_merge(
                new_text, f"{cptxml.format_a1(c0, hdr)}:"
                          f"{cptxml.format_a1(c0 + len(rows) - 1, hdr)}", sheet)
    # ② 行维度（纵向扩展；多指标时跨 rs 行合并）
    for i, col in enumerate(rows):
        put(cptxml.format_a1(c0 + i, data), binding=f"{dataset}.{col}", expand="v",
            style=style, ds_mode="group", rs=(nv if nv > 1 else None))
    # ③ 值格：**与列维度同列**（表头行那一格就是列维度，别在这里写值列名 —— 会把它覆盖掉，
    #    实测踩过：覆盖后列维度消失，值格只剩行父格，导出成 "100,200" 逗号拼接）
    for i, col in enumerate(values):
        put(cptxml.format_a1(vcol, data + i), binding=f"{dataset}.{col}", expand="none",
            style=style, ds_mode=("summary" if agg else "group"),
            ds_fn=agg if agg else None)
    # ④ 汇总列（列维度右边一列；按行汇总）
    if total_col:
        tcol = vcol + len(cols)
        if header:
            put(cptxml.format_a1(tcol, hdr),
                value=(value_labels[-1] if value_labels else f"{values[0]}汇总"),
                style=header_style)
        for i in range(nv):
            put(cptxml.format_a1(tcol, data + i), binding=f"{dataset}.{values[i]}",
                expand="none", style=style, ds_mode="summary", ds_fn=agg or "sum")
    # 总计行：官方写法是逐列公式 `=SUM(<值格首行>)`（区间自动伸展，列总计按列走）
    if total_row:
        put(cptxml.format_a1(c0, tot), value=total_label, style=style)
        if len(rows) > 1:
            new_text, _ = cptxml.set_merge(
                new_text, f"{cptxml.format_a1(c0, tot)}:"
                          f"{cptxml.format_a1(c0 + len(rows) - 1, tot)}", sheet)
        for i, col in enumerate(cols):
            c = c0 + len(rows) + i
            put(cptxml.format_a1(c, tot), formula=f"=SUM({cptxml.format_a1(c, data)})",
                style=style)
        for i in range(nv):
            put(cptxml.format_a1(vcol, tot),
                formula=f"=SUM({cptxml.format_a1(vcol, data + i)})", style=style)
        if total_col:
            put(cptxml.format_a1(vcol + len(cols), tot),
                formula=f"=SUM({cptxml.format_a1(vcol + len(cols), data)})", style=style)

    if widths:
        new_text = cptxml.set_col_widths(new_text,
                                         {c0 + i: w for i, w in enumerate(widths)},
                                         sheet=sheet)
    changes.append({"kind": "crosstab", "dataset": dataset, "at": at,
                    "row": rows, "col": cols, "value": values, "agg": agg,
                    "total_row": bool(total_row), "total_col": bool(total_col),
                    "layout": {"corner": cptxml.format_a1(c0, hdr),
                               "col_dim": cptxml.format_a1(vcol, hdr),
                               "row_dim": cptxml.format_a1(c0, data),
                               "value": [cptxml.format_a1(vcol, data + i)
                                         for i in range(nv)],
                               "total_row": tot, "cols": ncol}})
    changes.append({"kind": "note", "message": CROSSTAB_NOTE})
    if not agg:
        changes.append({"kind": "warning",
                        "message": "值格用的是分组(FunctionGrouper)：**同一个(行,列)交叉点若有多条"
                                   "记录，相同值会被去重**。要按交叉点聚合请加 `--agg sum`"})
    changes.append({"kind": "warning",
                    "message": f"列名（{'、'.join(dims + values)}）不做离线校验（要连库才知道）："
                               "写错不会报错，只会渲染出空列；导出后请逐格核对"})
    return new_text, changes


def edit_crosstab(config, report_path: str, apply: bool = False, **kwargs) -> dict:
    if apply and not isinstance(config, LocalTemplate):
        _scope(report_path)
    text = read_template(config, report_path).decode("utf-8")
    new_text, changes = plan_crosstab(text, **kwargs)
    return commit(config, report_path, text, new_text, "crosstab", changes, apply=apply)
