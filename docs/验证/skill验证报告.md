# fanruan-v10 skill 验证报告（第一、二轮）

| 项 | 值 |
|---|---|
| 验证者 | `skill-verifier`（以「只会看 SKILL.md 的 agent」身份使用，不读源码先做一遍） |
| 日期 | 2026-09-27 |
| 被验证版本 | 0.5.0（验证中发现 2 条阻断，Lead 修为 0.5.1 后复验）；第二轮在 0.5.1 上验证 `rpc` 与 `report edit` |
| 仓库 revision | `709ed77`（工作树含未提交改动）。**第二轮收尾时**：`src/` 指纹 `0a1916157a8c3292`，`__version__ = 0.5.1`；冻结后以此指纹对比即可确认"验的就是冻结版" |
| 实例 | `yh` @ `https://fr.example.com`（账号 00000000） |
| 写操作范围 | **仅** `demo_group/demo_user/skill测试`（远端 `reportlets/demo_group/demo_user/skill测试`） |
| 回归测试 | `tests/test_download_and_write_guards.py`（44 例，离线）；第二轮收尾全量 `180 passed / 2 failed`（2 例为已知历史失败） |

> 计时说明：本报告分两轮写成。**第一轮**（§1–§6）针对 0.5.0/0.5.1 的 `report`/`export` 链路；**第二轮**（§8）针对新增的 `rpc` 命令组与 `report edit/versions/fonts/image`。`report check` 最终未落地（体检能力由 `report fonts` 承担）。

## 0. 结论摘要

**可用性：可用。** 8 个命令组里的核心链路（浏览 → 读口径 → 导出 → 改模板）真机跑通，"复制 cpt → 改 SQL → 上传 → 导出确认改动生效"这条端到端有硬证据（导出文件里出现了只可能来自新 SQL 的值）。

**安全性：修复后可用。** 验证中打出 **2 条阻断级**问题，都在第一轮内被 Lead 修掉并复验通过：

| # | 阻断问题 | 影响 | 状态 |
|---|---|---|---|
| B1 | `report download` 返回的不是模板字节（`format=cpt` 的 `<TableDataMap>`），而 SKILL.md 教的 `download → 改 → upload --force` 会把它写回生产模板，且回读 SHA256 一致 → `verified: true` **假阳性** | 静默毁生产报表，CLI 与魔数校验**都拦不住** | ✅ 0.5.1 修复（download 改走远程设计通道 + upload 加格式守门），已复验 |
| B2 | `FRCLI_WRITE_SCOPE` 只挂在 `delete_template`，**`upload_template` 没挂** | 沙箱形同虚设，而 upload 恰恰是唯一能覆盖生产模板的操作 | ✅ 已修（守门移到所有网络调用之前），已复验 |

剩余 4 条严重、5 条一般、3 条体验，均**不阻断使用**，见 §3。第二轮又打出 **1 条严重**（`rpc` 写沙箱 `.tmp` 一段逃逸 → 已修，见 §8）。

**同根因的第二次发作（真实事故，见 §8.5）**：写范围判定与文档口径不一致（代码「env 未设 = 不限制」vs 文档「写操作只能在 `skill测试` 内」），导致 `report edit --apply` 在没设范围的 shell 里**真的写掉了别人的生产模板**（靠自动备份还原，生产无残留）。语义已改为 fail-closed：不设范围且不给 `--any-path` → 拒绝。**B2 与这次事故是同一类根因：默认放行 + 判定实现有多份/与文档漂移。**

**"不误导人"这一项扣分。** 最典型的不是"命令跑不通"，而是**文档与实现不一致导致 agent 做错判断**：`frcli -i <实例>` 被静默忽略（以为在 dev、实际打默认实例）、`export word` 产物是 RTF 却叫 `.docx`（按 SKILL.md 魔数表会把好文件判成坏文件）、写范围"看着有其实没有"。

---

## 1. 验证纪律（怎么保证没碰别人的东西）

- 服务器**写**操作只发生在 `demo_group/demo_user/skill测试`；验证期间另设 `FRCLI_WRITE_SCOPE` 做技术强制。
- 只从别的目录**读**（`report list/info/paras/datasets/download`、通道 `readFully`）；把 cpt **复制**进测试目录后才动手。
- **越界写测试分两阶段**：先用哨兵（把 `RemoteDesignSession.check/_post` 换成抛异常，**不发任何请求**）确认守门在网络之前；确认后才用真 CLI 打越界路径。B2 未修前，我**拒绝**执行真发请求的越界 upload 测试（那时守门没生效，一测就是真写生产）。
- 未删除/修改/运行任何非本团队创建的 cpt 或定时任务。每轮结束 `ws-list` 复查：测试目录只剩原有的 `_目录说明.txt`。
- 唯一"注释掉"的导出对象是 `demo_group/demo_user/dept_a/dept_b/sales_daily.cpt`——先 `download` 到本地、**上传副本到测试目录**、只导出副本。原报表只读核对未变（14 个数据集仍可读）。

---

## 2. 逐条命令结果

### 2.1 `server`

| 命令 | 实际输出摘要 | 结论 |
|---|---|---|
| `server test` | `{"status":"ok","http_status":200,"relogin":false}` | 可用 |
| `frcli -i nosuch report list X` | **exit 0，返回 `yh`（默认实例）的数据** | **不可用（严重 S1）** |
| `frcli report list X -i nosuch` | `exit 2`，`CONFIG_ERROR: 实例 'nosuch' 不存在。可用实例: ['yh']` | 可用（诊断清晰） |

### 2.2 `report`（只读）

| 命令 | 实际输出摘要 | 结论 |
|---|---|---|
| `report list "…/skill测试"` | 返回目录自身一条 + 子项，结构正确 | 可用 |
| `report list <目录> -f table` | rich 表格，中文列名自动折行 | 可用（超长名字折行后略难读） |
| `report ws-list "demo_group/demo_user"` | 19 个条目、按目录优先排序 | 可用 |
| `report ws-list <不存在的目录>` | `{"count": 0, "entries": []}`，**status ok** | 难用（G3：与"空目录"无法区分） |
| `report ws-list <一个文件的路径>` | `{"count": 0, "entries": []}` | 难用（G3：没报"这不是目录"） |
| `report info <正常报表>` | 数据集名清单 + 参数清单 | 可用 |
| `report info <坏数据集报表>` | `{"path":…, "name":…, "error":"无法读取报表定义"}` | 可用（有 error 字段，能定位） |
| `report info <不存在的路径>` | `{"path":…, "datasets": [], "parameters": []}`，**status ok、无 error** | 难用（G3：与"报表没有数据集"无法区分） |
| `report paras <正常报表>` | 参数名/类型/值 | 可用 |
| `report paras <不存在的路径>` | `[]` | 难用（G3，但 SKILL.md §7 已声明此行为） |
| `report datasets <正常报表> --sql` | 名称/参数/完整 SQL | 可用 |
| `report datasets <坏数据集报表>` | `[]`（服务端其实回了 200 + HTML 出错页） | **难用（严重 S3：把 `detail-message` 里的"数据集 [X] 配置错误 + 驱动报错 + 原始 SQL"丢掉了）** |
| `report download <报表>`（0.5.0） | 落盘 6362B，根元素 `<TableDataMap>`，**不是模板** | **不可用（阻断 B1）** |
| `report download <报表>`（0.5.1） | 落盘 4510B，根元素 `<WorkBook>`，与通道 `readFully` 的 SHA256 **完全相同**（`c8f09176b7958fac…`） | 可用 |
| `report download <无权限/不存在路径>` | `REPORT_NOT_FOUND: 下载失败（服务端无此文件，或该路径不在账号的远程设计授权目录内）`，exit 1 | 可用（两可措辞是必要的：通道对两者都返回 0 字节） |
| `report download <坏数据集报表>`（0.5.0） | `REPORT_NOT_FOUND: 下载失败（无权限或文件不存在）`——**但文件确实存在**（187407B，可读） | 不可用（误导诊断；0.5.1 改走通道后自动消失，同一条命令现在成功取回 187407B） |

### 2.3 `report`（写）

| 命令 | 实际输出摘要 | 结论 |
|---|---|---|
| `report upload <新文件> <域内新路径>` | `{"overwritten": false, "verified": true, "server_size": 4510, "status":"ok"}` | 可用 |
| `report upload` 到**已存在**路径、不加 `--force` | exit 1，`服务端已存在 …（4510 字节），确认要覆盖再加 --force` | 可用（守门有效） |
| `report upload --force` | `{"overwritten": true, "backup": "~/.frcli/backups/20260927-175801__…", "previous_sha256": "9f2767ba…", "verified": true}` | 可用 |
| **备份内容校验** | 备份 498170B / sha `9f2767ba687ffc57` == 覆盖前服务端内容，**逐字节相同** | 可用 |
| 连传同一个文件两次 `--force` | 两次 sha 一致、`verified: true`、备份各新增一份（不覆盖旧备份） | 可用（幂等，且不丢历史备份） |
| `report upload` 传旧 `format=cpt` 产物 | exit 1，`本地内容不像 cpt 模板（前 600 字节没有 <WorkBook>）…`，**目录未被写入** | 可用（0.5.1 新增守门，正是 B1 的对策） |
| `report delete <域内文件>` | `{"deleted": true, "trash": true, "verified": true}` | 可用 |
| `report delete` 不加 `--force` | exit 1，`删除服务端模板需要显式确认：加 --force` | 可用 |
| `report delete` 再来一次 | exit 1，`服务端不存在: …` | 可用（幂等，报错清晰） |

### 2.4 `export`

| 命令 | 实际输出摘要 | 结论 |
|---|---|---|
| `export excel <测试目录副本>` | `status: ok`，223–225KB，`PK\x03\x04` | 可用 |
| `export pdf / image / csv` | `%PDF`(33368B) / `\x89PNG`(73677B) / 1B（空报表） | 可用 |
| `export word` | 默认落盘 **`.docx`**，内容却是 **RTF**（`{\rtf1\ansi…`，魔数 `7b5c72746631`） | **难用（严重 S2）** |
| `export excel <坏数据集报表>` | `status: ok`，落盘的是 HTML 出错页 | 已知坑（SKILL.md §6.1 已声明；`detail-message` 能读出"数据集 [ds_target] 配置错误…Could not resolve table reference: 'demo_db.demo_tmp_target'"） |
| `export excel <复杂报表>` / 平台限流时 | `status: ok`，落盘 **2102B 排队等待页**（`Dec-Waiting_In_Line`，**无** `<title>出错页面</title>`、**无** `detail-message`）；重试一次即成功（225457B `PK`） | 难用（严重 S4：SKILL.md §7 的两条判据都识别不出这个形态） |
| `export excel … --params '{bad json'` | 打印 **Python traceback**（`json.decoder.JSONDecodeError`），exit 1 | 难用（G2：不符合 SKILL.md 的 JSON 错误契约） |

### 2.5 其它命令组

`system/entry/user/schedule/attach` 本轮未逐一重跑（不在本轮范围）。仅确认 `frcli --help` 与各命令组注册正常（8 组 + 新增 `rpc`）。错误 JSON 一律走 **stderr**、stdout 为空（G1）。

---

## 3. 问题清单

### 阻断（0.5.1 已修，均已复验）

#### B1 `report download` 下载的不是模板 → 文档化的流程会毁生产报表，且回读校验假阳性 ✅已修
- **复现（0.5.0）**：`frcli report download "demo_group/demo_user/测试/TOP品店日均&门店数.cpt" -o a.cpt`
- **实际**：落盘 6362B，根元素 `<TableDataMap>`；服务端真实文件 4510B，根元素 `<WorkBook>`，含 `<StyleList>`/`<TemplateIdAttMark>`/`<Report>`。两者**不是同一份文件**（`client.download_report` 与 `get_report_datasets` 打的是同一个 `format=cpt` 端点）。
- **端到端后果实测**（只在测试目录内做）：把这份 stub 上传成 `skill测试/onboard-stub-*.cpt` → `upload` 报 `verified: true`、`report info` 的 `datasets` 变 `[]`、`export excel` 依然报 `status: ok` 并产出**魔数合法的空工作簿**（`sst count="0"`、无 worksheet）。即：**回读 SHA256 ✓、魔数 ✓、状态 ✓，三道自检全部假阳性**。
- **期望**：download 落盘字节 == 服务端文件字节。
- **影响面**：SKILL.md §5 步骤 7.5 的字面流程即可触发；`<Query>/<DatabaseName>/<TableData>` 这些提示在两份文件里都存在，诱骗性极强。
- **验证**：0.5.1 后 `download` 与通道 `readFully` 的 SHA256 完全相等；传入 stub 被守门拒绝。

#### B2 `FRCLI_WRITE_SCOPE` 未挂到 `upload_template` ✅已修
- **复现（修复前）**：`grep -rn assert_in_write_scope src/` → 只有 `remotedesign.py:431`（delete 内）与 `rpc.py:275`；`upload_template` 没有。
- **动态**（哨兵，未发请求）：`upload_template(cfg, f, "demo_group/demo_user/dept_a/dept_b/sales_daily.cpt", force=True)` → 越过守门直达网络层。
- **影响面**：团队协作期唯一的强制边界失效；"以为有沙箱"比"没有沙箱"更危险。
- **验证**：0.5.1 后 6 条越界路径（生产报表 / `../` 穿越 / `reportlets/超级管理员/` / 兄弟目录 `skill测试2` / 绝对路径 / `assets/`）全部本地拒绝（`ApiError`，exit 1），域内路径放行到网络层。

### 严重

#### S1 顶层 `-i <实例>` 被静默忽略，实际打的是默认实例　**✅ 已修并复验**
- **复现**：`frcli -i nosuch report list "demo_group/demo_user/skill测试"` → **exit 0**，返回 `yh` 的数据。
- **根因**：`cli.py` 的 group 级 `-i` 只写 `ctx.obj["instance"]`，**没有任何子命令读它**；每个子命令各自有 `-i`。
- **对照**：`frcli report list "…" -i nosuch` → exit 2 + `CONFIG_ERROR: 实例 'nosuch' 不存在。可用实例: ['yh']`（正确）。
- **影响面**：SKILL.md §5 第 7 条就是这么教的（`frcli -i dev report list "某目录"`）。多环境场景下，用户以为在 dev 上操作，实际打的是**默认实例**（很可能是生产）——只读查询给出错误结论，写操作直接改错环境。
- **期望**：顶层 `-i` 生效；或删掉顶层 `-i` 并把 SKILL.md 的示例改成子命令级形式。

#### S2 `export word` 产物是 RTF，文件却叫 `.docx` —— 按 SKILL.md 的魔数表会把好文件判成坏文件　**✅ 已修并复验**
（修复后：`EXPORT_MAGIC["word"] = (b"{\\rtf1", "rtf")`，默认落盘扩展名改 `.rtf`，`client.py:84 assert_export_magic` 在导出回写处统一校验）
- **复现**：`frcli export word "<测试目录副本>"` → `"file": "…/e2e-orig-175417.docx"`，前 20 字节 `7b5c727466315c616e7369…`（`{\rtf1\ansi`）。
- **冲突**：SKILL.md §6.1 魔数表写 `xlsx / docx = PK\x03\x04`，§5 也教 agent 用魔数判成败。agent 照做 → 把一份正常的 word 导出判成"出错页面"，触发无谓的排障；`export.py:80` 也硬编码了 `.docx` 后缀。
- **期望**：要么改名 `.rtf`/`.doc` 并在魔数表补 `{\rtf`，要么让服务端真出 docx。

#### S3 `report datasets/info` 吞掉 `format=cpt` 出错页里的诊断信息　**🟡 部分修复并复验**
- **复现**：`report datasets "demo_group/demo_user/临时/demo_report.cpt"` → `[]`（修复前）；同路径 `format=cpt` 原始响应是 **200 + HTML 出错页**，`detail-message` 写着 `错误代码:11300001 数据集 [ds_target] 配置错误[ImpalaJDBCDriver]… Could not resolve table reference: 'demo_db.demo_tmp_target'`。
- **路径澄清（重要，避免后人复现不到）**：Lead 曾按 `测试/demo_report.cpt` 复查并得到 `错误代码:11300004 没有找到模板文件`，据此认为该文件不存在。实测该文件在 **`临时/`** 下确实存在（`ws-list` 可见、`report list` 可见、通道 `exist=True len=215372`）。两个路径的报错不同，是两条不同的结论：
  ```
  临时/demo_report.cpt → 11300001 数据集 [ds_target] 配置错误 …      ← 本 S3 场景（文件在，数据集坏）
  测试/demo_report.cpt → 11300004 没有找到模板文件:reportlets/…/测试/…   ← 文件不在
  ```
  修复后（`report datasets` 直接抛平台原文）两条都实测复现过，均可用作回归样本。
- **关键点**：该模板里其实有 **2 个** 数据集（`销售`、`ds_target`），只因其中一个坏掉，**整个报表的 `datasets` 就变成 `[]`**——CLI 呈现为"这报表没有数据集"，与事实不符。
- **影响面**：SKILL.md §6.9 明确把 `detail-message` 当作排障主入口，但这条路径上的 CLI 没有用 `_unwrap_json()` 把它翻出来；agent 只能停在"读不到"，拿不到"哪个数据集、为什么错、原始 SQL 是什么"。
- **建议**：`get_report_datasets`/`get_report_info` 检测到 HTML 出错页时，把 `detail-message` 解出来放进 `error` 字段（或抛 `API_ERROR`）。修好后 `report download` 也应能取回这类模板（0.5.1 改走通道后这部分已经自然解决）。

#### S4 未文档化的导出失败形态：平台限流返回"排队等待页"　**✅ 已修并复验（离线判据 + 真机出错页）**
- **复现**：`FRCLI_TIMEOUT=900 frcli export excel "<测试目录副本>"` → `status: ok`，落盘 **2102B**，body 里是 `Dec-Waiting_In_Line` + 5 秒轮询脚本。
- **与文档的差异**：SKILL.md §6.1/§7 的判据是"含 `<title>出错页面</title>` / `Oops!!!`"以及"`detail-message` 里有原因"。这个页面 **title 为空、无 detail-message**，两条判据都不命中；只有魔数校验能发现它是坏的（这点文档是对的）。
- **实测**：同一命令**重试一次即成功**（225457B `PK`）。所以正确处置是"魔数不符就重试，别只当出错页排查"。
- **建议**：SKILL.md §6.1/§7 补一行"还有一种 2102B 排队页 `Dec-Waiting_In_Line`，重试即可"。

### 一般

| # | 问题 | 证据 | 建议 |
|---|---|---|---|
| G1 | 错误 JSON 只写 stderr，stdout 为空 | `frcli report download <不存在> 2>/dev/null` → 无输出，exit 1 | 文档写明"错误走 stderr"，或提供 `--json-errors` 统一到 stdout |
| G2 | `--params` 非法 JSON 抛原始 Python traceback | `--params '{bad json'` → `json.decoder.JSONDecodeError` 栈，exit 1 | 用 `error(...)` 包成 `API_ERROR`/`参数错误` |
| G3 | 不存在路径静默为空 | `report info <不存在>` → `{"datasets":[],"parameters":[]}` status ok；`ws-list <不存在>` → `count: 0` status ok | 路径不存在时报 `REPORT_NOT_FOUND`（`report paras` 的 `[]` 已在 §7 声明，可保留） |
| G4 | 格式守门是启发式 | `<WorkBook` 出现在前 600 字节的 **XML 注释**里即放行（已固化为测试） | **已知局限，不修**（Lead 决策）：守门挡的是「整份拿错序列化」这类常见事故，不防定向绕过；真正的边界是 `FRCLI_WRITE_SCOPE` + 服务端授权目录。故按"已知局限"记录，不算缺陷 |
| G5 | CLI 层不消解 `..` | `normalize_report_path("../x.cpt") == "reportlets/../x.cpt"` | 不可利用（实测服务端对越出根的路径直接抛 `IllegalArgumentException: [Resource] Path is required for Resource IO operation`，根内 `..` 不解析）；但要写进文档，别让人以为 CLI 做过消毒 |

### 体验

| # | 问题 |
|---|---|
| UX1 | 备份文件名把整条路径压平成一长串（`20260927-175801__reportlets__demo_group__demo_user__skill测试__demo-e2e-175737.cpt`），可读性差；内容可校验，功能上没问题 |
| UX2 | `report ws-list <path> -f table` 只打印 `entries`，把 `path`/`count` 丢了；json 模式才有 |
| UX3 | `report list -f table` 中文长文件名折行后列宽跳动，不如 json 好读（agent 默认 json 即可） |

---

## 4. 安全边界对抗测试矩阵

第一轮的做法：`export FRCLI_WRITE_SCOPE="demo_group/demo_user/skill测试"`（B2 修复后）——即"设了范围"这一档。
**第二轮收尾时写范围语义改成 fail-closed（三档：不设 → 拒绝 / 设了 → 限定该目录 / `--any-path` → 本次放行）**，三档的实测见 §8.5；下面的矩阵在"设了范围"这一档下依然完全成立。

**阶段一：哨兵（`RemoteDesignSession.check`/`_post` 换成抛异常，零网络请求）**

| 目标路径 | 期望 | 结果 |
|---|---|---|
| `demo_group/demo_user/dept_a/dept_b/sales_daily.cpt`（生产报表） | 拒绝 | ✅ 本地拒绝 |
| `demo_group/demo_user/skill测试/../dept_a/sales_daily.cpt`（`..` 穿越） | 拒绝 | ✅ 本地拒绝 |
| `reportlets/超级管理员/x.cpt` | 拒绝 | ✅ 本地拒绝 |
| `demo_group/demo_user/skill测试2/x.cpt`（前缀相近的兄弟目录） | 拒绝 | ✅ 本地拒绝 |
| `/demo_group/demo_user/dept_a/dept_b/sales_daily.cpt`（绝对路径） | 拒绝 | ✅ 本地拒绝 |
| `assets/evil.cpt` | 拒绝 | ✅ 本地拒绝 |
| `demo_group/demo_user/skill测试/ok.cpt`（域内） | 放行到网络层 | ✅ 放行 |

**阶段二：真 CLI（守门在网络之前，安全）**

| 命令 | 结果 |
|---|---|
| `report upload <cpt> <5 条越界路径> --force` | 5/5 `exit 1` + `写操作被 FRCLI_WRITE_SCOPE 限制在 reportlets/demo_group/demo_user/skill测试/ 之内，已拒绝：…` |
| `report delete <生产报表> --force` | `exit 1`，同一条守门消息 |
| `report info <生产报表>`（只读核对） | 14 个数据集仍可读，报表未被改动 |

**其它边界**

| 用例 | 结果 |
|---|---|
| 上传旧 `format=cpt` stub | ✅ 拒绝（格式守门），且 `ws-list` 确认目录未被写入 |
| `<WorkBook` 位于第 700 字节 | ✅ 拒绝 |
| `<WorkBook` 藏在注释里 | ⚠️ 放行（G4，已知启发式局限） |
| 空文件 / HTML 出错页 / gzip 垃圾 | ✅ 拒绝 |
| `--allow-format` 逃生口 | ✅ 按设计放行（要显式给） |
| 覆盖时备份是否等于原文件 | ✅ 逐字节相同（498170B / sha `9f2767ba687ffc57`） |
| `delete` 幂等 | ✅ 第二次 `服务端不存在` |
| `upload` 同内容重复 `--force` | ✅ 幂等，sha 一致，备份累加不覆盖 |

---

## 5. 新 agent 上手验证：照着 SKILL.md 从零做一遍

任务：**把一张 cpt 复制到测试目录 → 改 SQL → 上传 → 导出确认改动生效**。
身份约束：只读 SKILL.md（未先读源码）。执行时间：2026-09-27。

| 步骤 | SKILL.md 的说法 | 照着做的结果 |
|---|---|---|
| 0 环境 | §2「配置实例 → `frcli server test`」 | ✅ 已有 `yh` 实例，`server test` ok。**卡点**：§2 没写"怎么先看有没有实例"（`server list`），新 agent 可能重复 add |
| 1 找一张 cpt | §5-1 `report list <具体目录>` | ✅ 顺利 |
| 2 复制到测试目录 | §5-7.5 `report download <路径> -o a.cpt` | ❌ **0.5.0 下拿到的是 `<TableDataMap>` 不是模板（B1）**；上传前完全看不出来。0.5.1 修复后 ✅ |
| 2' 改用真模板 | — | 文档没给替代路径。我用通道 `readFully`（读源码才知道）拿到 4510B 真 `<WorkBook>`，**这一步是照 SKILL.md 做不到的** |
| 3 改 SQL | §5-7.5「本地改 a.cpt（XML：`<Query>`/`<DatabaseName>`/`<TableData>`…）」 | ⚠️ **说不清**：没说根元素是 `<WorkBook>`、`<Query>` 嵌在 `<TableData>` 里、一个模板可能有 14 个 `<TableData>`。我一次就改错了数据集（改了 `目标` 却用错列别名，导出无变化，白等一轮）。文档也没说"改完怎么验证改对了" |
| 4 上传 | §5-7.5 `report upload a.cpt <路径> --force` | ✅ 0.5.1 下 `verified: true` + 备份。**文档缺口**：没提"上传前先 `report datasets` 回读确认 SQL 真的落在服务端"——这是唯一能证明改动生效的低成本手段 |
| 5 导出确认 | §5-3/§5-4 导出 + 魔数校验 | ✅ 但踩到两件事：① 平台限流返回的**排队页**，SKILL.md 的判据识别不出（S4），重试即成功；② `export word` 的魔数表是错的（S2） |
| 6 清理 | — | **文档缺口**：§4 只要求 `attach` 用完清理；模板副本没有"测完删掉、并 `ws-list` 复查"这一条。建议补进 §5-7.5 |

**最终硬证据（"改完真的生效"）**——同一张模板的两个副本，同一套导出参数（`{"edate":"20260731","extype":"simple"}`）：

| 副本 | 服务端 SQL | 导出产物 | 单元格 | 关键字 |
|---|---|---|---|---|
| `bake-pristine-*.cpt` | 原样 | 225450B `PK\x03\x04` | 21019 | **无** `987654.32` |
| `demo-e2e-*.cpt` | `日目标`/`目标` 的聚合表达式改成常量 `cast(987654.32 as double)` | 225913B `PK\x03\x04` | 21019 | **D4 = `987654.32`**（同行 B4=`华北`、C4=`北京大区`） |

上传侧同步确认：`report datasets <副本>` 回读出的 `日目标`/`目标` SQL 里含 marker；`upload` 返回 `verified: true`、`previous_sha256` 与覆盖前一致；备份文件逐字节等于覆盖前内容。

**给 SKILL.md 的具体修改建议（按价值排序）**
1. §5-7.5 重写为四步带判据的流程：`download` →（可选）`report datasets --sql` 核对基线 → 改 SQL → `upload --force` → **`report datasets` 回读确认** → `export` → 魔数校验 → **`report delete --force` 清理 + `ws-list` 复查**。
2. §5-7.5 补一句模板结构：根元素 `<WorkBook>`；数据集在 `<TableData name="…">` → `<Query><![CDATA[SQL]]></Query>`；**改哪个数据集要先 `report datasets` 看名字**。
3. §6.1/§7 补"排队等待页"形态与"魔数不符先重试"。
4. §6.1 魔数表修正 word：实测是 `{\rtf`（`7b5c727466`），不是 `PK`。
5. §5 第 7 条 `frcli -i dev report list` 改写成子命令级 `-i`（S1）。
6. §2 补一句"先 `server list` 看有没有实例"。

> **第二轮补充**：建议 1 与 2 已被 `report edit` 大幅覆盖 —— `report edit --list` 直接把「根元素 / 数据集名 / 连接 / SQL 长度 / 参数」给全（正是建议 2 想要的结构可见性），`--dataset X --replace OLD=NEW` 的 dry-run diff 让"改哪个数据集、改成了什么"无需靠肉眼比对 XML；`--apply` 内部还会回读校验（`verified: true`）。**推荐把 §5-7.5 的主推流程从"手改 XML"改成 `report edit`**，把 `download`/`upload` 留作兜底。

---

## 6. 回归测试

新增 `tests/test_download_and_write_guards.py`（第一轮 **27 例**、第二轮扩到 **44 例**，全部离线），固化本轮踩到的坑：

| 分组 | 用例 |
|---|---|
| download 契约（防 B1 回归） | 只走通道、落盘字节与通道一致；`format=cpt` stub 被拒且不落盘；0 字节（无权限/不存在）报错不落空文件；`report datasets` 仍走 `format=cpt`（语义别混） |
| 格式守门边界 | `<WorkBook` 在第 700 字节 → 拒绝；注释里的 `<WorkBook` → 放行（固化 G4 已知局限）；空文件/HTML → 拒绝 |
| 备份 | 内容逐字节相同；文件名压平不造子目录；两次备份不互相覆盖 |
| 路径归一 | 前缀伪造 `reportletsX/` 被消解；`..` 不在 CLI 侧消解（固化 G5） |
| 写沙箱（防 B2 回归） | 4 条域内放行 + 6 条越界/穿越/兄弟目录/根目录拒绝；未设 = 不限制 |
| delete 守门顺序 | 未加 `--force` 时**不建立任何会话** |

第一轮收尾时全量：`PYTHONPATH=src python -m pytest tests/ -q` → **121 passed, 2 failed**（第二轮收尾时同口径为 **180 passed**）；2 例失败是已知历史遗留（`test_config.py::test_load_empty_config` / `test_list_instances_empty`，因实测环境存在真实 `~/.frcli/config.yaml` 而固定失败，与本轮无关）。`flake8` 对新文件无告警。

---

## 7. 未覆盖 / 无法验证的部分（诚实声明）

1. **`src/` 在验证期间被并行修改**：本轮验证期间 `feat-miner` 正在改 `jser.py`/新增 `rpc.py`，我实测遇到过一次**瞬时导入错误**（`ValueError: too many values to unpack (expected 3, got 4)`，`jser.py:705` 正在编辑），以及一次 `client.py:77` 的 `SyntaxError`（写 `b"<title>出错页面</title>"` 时非 ASCII 进了 bytes 字面量），两次都导致 CLI 短暂不可用、白跑一轮。**结论：本报告的所有结论只对 §7 记录的 revision 有效**；最终验收在**冻结的 revision** 上重跑。
2. **`report upload` 到无授权目录的行为**：需要真发写请求，按安全约束**未测**；从代码看此时会命中"回读不一致"报错（服务端静默不写），但这只是推理。
3. **`report check` 未落地**：原计划的"模板体检"命令不存在（`TemplateChecker` 只有 `checkFont`），能力由 `report fonts` 承担并已在 §8.3 验证。`rpc` 与 `report edit` 均已在 §8 验证。
4. **`schedule` 写操作、`attach upload`**：未做（危险/不在范围）。`schedule` 只读命令借用历史结论，本轮未复跑。
5. **`export batch`**：未做（会批量触发服务端计算）。
6. **`report list /` 全量（数千条，随时间增长）**：未复跑（避免无谓负载），沿用 SKILL.md 实测值。
7. **通道对无授权路径返回 0 字节**：这是 Lead 的抽样结论，我未独立复现（只复现了"无授权路径 `download` 报两可错误"这一现象）。
8. **排队页（`Dec-Waiting_In_Line`）未真机复现**：限流是瞬时的，只做了离线判据验证（§8.2 S4 行）。
9. **`rpc call` 的写方法未做真实成功写入**：越界全被拒（符合预期），域内成功写入未测 —— 模板写入统一走 `report upload`/`report edit` 已足够覆盖，`rpc` 直写没有额外验证价值。

## 8. 第二轮：`rpc` 命令组、`report edit` 与修复复验

本节覆盖：`rpc services/methods/call` 与写守门、`report edit`（含 `--list` / dry-run diff / `--apply` 端到端）、新增只读命令 `report versions/fonts/image`、以及第一轮 4 条严重问题与 `.tmp` 逃逸的修复复验。

唯一**未落地**的是原计划的 `report check`：`TemplateChecker` 实际只有 `checkFont`，所以"模板体检"改由 `report fonts` 承担（已在本节 8.3 验证）。因此本报告**没有**任何"待复验"的结论 —— 所有条目要么有实测输出，要么在 §7 明确列为未覆盖。

### 8.1 `rpc` 命令组

| 命令 | 实际输出摘要 | 结论 |
|---|---|---|
| `rpc services`（线上 `/service`） | `count: 28`，每项带 `methods` 数、`in_local` 标记 | 可用（与 SKILL.md §6.7「实测 28 个」一致） |
| `rpc services --local` | `count: 28`，带 `jar` 出处，不联网 | 可用 |
| `rpc methods <service>` | 方法签名 + `policy`（read/write/deny）+ `jar` 来源，**不联网** | 可用（离线反解清单，比线上多出签名信息） |
| `rpc call VersionInfoOperator getFullBuildNO` | `"Build#persist-2022.02.18.08.50.53.493"` | 可用（复现 Lead 结论 ✓） |
| `rpc call CommonOperator getLicenseName` | `"FanRuan.lic"` | 可用 |
| `rpc call WorkResource length <路径>` | `66`（`_目录说明.txt`） | 可用 |
| `rpc call WorkResource readFully <路径>` | `{"result_type":"JArray","result":{"__bytes__":66}}` | 可用但**拿不到字节本体**（无 `--out` 落盘选项）→ 体验项 |
| `rpc methods <不存在的服务>` | `未知服务 …；`frcli rpc services` 看清单，或 `frcli rpc services --local` 离线查看` | 可用（错误信息给了下一步动作） |
| `rpc call <服务> <不存在的方法>` | `没有方法 X；可用: compile, fileLocked, getAppName, …（20 个全列出）` | 可用 |
| `rpc call … exist`（0 个 / 2 个参数） | `需要 1 个参数(java.lang.String)，给了 N 个；示例：--arg reportlets/xxx.cpt` | 可用（带示例） |
| `--arg java.lang.String=<值>` | 显式类型可用 | 可用 |
| `rpc call EncryptOperator readKey` | `属平台配置/权限/密钥类写操作，本工具在任何情况下都不放行` | 可用（deny 策略生效） |
| `rpc call WorkResource write`（不带 `--yes`） | `是写语义方法，确认执行请加 --yes（写范围：…）` | 可用 |
| `rpc call WorkResource write --yes <越界路径>` | `写操作被 FRCLI_WRITE_SCOPE 限制在 … 之内，已拒绝` | 可用 |

**一个易踩的坑（体验）**：`exist`/`length` 等方法的路径参数**不做归一化**。
`rpc call WorkResource exist --arg "demo_group/demo_user/skill测试"` → `false`（因为工作区路径要带 `reportlets/` 前缀），而该目录明明是存在的。返回值本身没错，但 `false` 有两种含义（路径写法不对 vs 真的不存在），文档没提醒。

### 8.2 修复复验（5 条）

| # | 修复 | 复验方式与结果 |
|---|---|---|
| S1 | 顶层 `-i` 实例解析 | ✅ `frcli -i nosuch report list` → **exit 2** + `CONFIG_ERROR: 默认实例 'nosuch' 不存在。可用实例: ['yh']`（**不再回落**）；`frcli -i yh server test` → exit 0；新增 `FRCLI_INSTANCE=nosuch` → exit 2，且子命令 `-i yh` 能覆盖它 → exit 0。优先级 4 例全对 |
| S2 | word=RTF 魔数 + 扩展名 | ✅ 真机 5 格式导出：`word` 落盘 **`.rtf`**（`7b5c727466315c61`）、`excel` `.xlsx`（`504b0304`）、`pdf`（`255044462d312e37`）、`image` `.png`（`89504e470d0a1a0a`）、`csv` 均 `status: ok` 且通过新魔数守门 |
| S3 | `report datasets` 抛平台原文 | ✅ `临时/demo_report.cpt` → `API_ERROR` 带完整 `数据集 [ds_target] 配置错误 … Could not resolve table reference: 'demo_db.demo_tmp_target'` + 原始 SQL。**注意消息很长**（平台把整条 SQL 塞进来）。`report info` 仍只给 `"error": "无法读取报表定义"`（未带 detail）→ 剩余小缺口 |
| S4 | 排队页识别 | ✅ 离线：`assert_export_magic` 对排队页/出错页/格式不符分别抛 `ExportError`（已固化 7 例参数化测试）。真机：坏数据集副本导出 → **exit 1 + `EXPORT_ERROR`**，不再报 `status: ok`。⚠️ 排队页本身未能真机复现（限流是瞬时的），只做了离线判据验证 |
| 新 | `rpc` 写沙箱 `.tmp` 逃逸 | ✅ 修复后两条守门合并为同一份代码；离线 8 例口径完全一致；真机 `reportlets/…/skill测试.tmp` 与 `reportlets/…/skill测试x/x.cpt` 均本地拒绝 |

**残余小问题（已修）**：导出失败时坏产物原本留在磁盘上（实测 `/tmp/frv/r2/broken.xlsx` 35686B，是 HTML 出错页），只是 CLI 抛错、exit 1，agent 若只看"文件存在"仍可能误用。**✅ 已修并复验**：现在失败产物改名 `<原名>.bad`，错误信息带上 `.bad` 路径；实测原路径不存在、`.bad` 存在。

**`report info` 的同类缺口（已修）**：原先坏数据集报表 `report info` 只回 `"error": "无法读取报表定义"`，没有 detail。**✅ 已修并复验**：现在与 `report datasets` 同口径抛平台原文（`11300001 数据集 [ds_target] 配置错误 … Could not resolve table reference: 'demo_db.demo_tmp_target'` + 原始 SQL），正常报表不受影响。

### 8.3 第二轮新命令：`report edit` / `versions` / `fonts` / `image`

> `report check` 最终**没有落地**（`TemplateChecker` 只有 `checkFont`，体检能力改由 `report fonts` 承担），因此"模板体检"这条以 `fonts` 验证。

| 命令 | 实际输出摘要 | 结论 |
|---|---|---|
| `report edit <报表> --list` | `{"root":"WorkBook","bytes":215372,"datasets":[{"name":"销售","class":"DBTableData","connection":"demo_conn","sql_chars":6469,"parameters":["shops","edate"]},…],"sql_parameter_refs":[…],"sha256_before":"2ab1253f…"}` | **可用（优秀）**。这正是第一轮"新 agent 上手"里最缺的结构可见性：根元素、每个数据集的名字/连接/SQL 长度/参数、以及参数引用清单，一次给全 |
| `report edit … --dataset 日目标 --replace "OLD=NEW"`（dry-run） | `{"applied":false,"bytes_before":498170,"bytes_after":498174,"changes":[{"kind":"dataset.sql","dataset":"日目标","mode":"substring","replacements":[{"old":…,"new":…,"count":1}],"diff":"--- 日目标.sql (before)\n+++ …(after)\n@@ -2,3 +2,3 @@\n-    ,sum(sales_amt_target) sales_amt_target\n+    ,cast(987654.32 as double) sales_amt_target"}],"hint":"以上为 dry-run，未写服务端；确认无误加 --apply"}` | **可用（优秀）**：结构化 changes + 真实 unified diff（不是整文件 dump）、`bytes_before/after` 可核对、明确 hint。且**不是正则**：字节数正好 +4（字符串长度差），其余字节原样保留 |
| `report edit … --apply` | `applied:true` + 内嵌 `upload` 块：`overwritten:true, backup:…, previous_sha256:"9f2767ba…", verified:true` | 可用（复用 upload 的占锁/备份/回读，口径一致） |
| `report versions <报表>` | `count:1`，含 `commit_code`/`username`/`time`/`filename`，并附 `note`（空列表的两种含义） | 可用 |
| `report fonts <报表>` | `missing_fonts: []`, `ok: true`，附 `note`（非空时导出可能字体替换） | 可用 |
| `report image <报表> -o x.png` | `method: "exportWorkBookAsImageData"`, 17883B，`\x89PNG`；肉眼可见页面的"公司数据，仅限内部查看"水印 | 可用（服务端渲染，不走 REST 导出） |

**`report edit` 的真正端到端判据（本轮最强证据）**——用 `report edit` 改 SQL，再看导出是否真的变：

| 步骤 | 结果 |
|---|---|
| 1. `download` sales_daily → `upload` 副本进测试目录 | 498170B，`verified: true` |
| 2. `report edit <副本> --dataset 日目标 --replace "sum(sales_amt_target) sales_amt_target=cast(987654.32 as double) sales_amt_target"` dry-run | `bytes 498170 → 498174`，diff 只动那一行 |
| 3. 同上 `--apply` | `applied:true`，`previous_sha256` = 覆盖前 sha，`verified:true`，备份已落盘 |
| 4. `report datasets <副本>`（**走 REST，独立于远程通道**） | `日目标` SQL 含 `987654.32` ✅ |
| 5. `export excel <副本> --params '{"edate":"20260731","extype":"simple"}'` | 225187B `PK`，**含 `987654.32`**（D4 单元格） |
| 6. 对照：改动前的同模板副本 | 225450B `PK`，**不含** `987654.32`；cells 均为 21019 |
| 7. `report delete --force` 清理 | 测试目录复原 |

**结论：`report edit` 可用且好用** —— 改动经两条独立通道（远程设计 + REST）确认落到服务端，并且**导出产物里出现了只可能来自新 SQL 的值**。dry-run 的 diff 对 agent 来说完全够读，`--apply` 前的确认成本很低。

**`report edit` 的边界与错误信息（全部 dry-run，未写服务端）**

> **"dry-run 真的不写"的机器判据**（我独立复现）：对只读报表 `临时/demo_report.cpt` 取通道 SHA256 → 跑一次 `report edit --dataset 销售 --replace "edate'=edate'"`（不带 `--apply`）→ 再取 SHA256：
> `dry-run 前 2ab1253f657ba2ee` / `dry-run 后 2ab1253f657ba2ee`，**完全相同**；输出里同时有 `dry_run:true` + `applied:false` + `hint`。即"默认 dry-run"不是靠约定，是行为事实。

| 输入 | 实际输出 | 结论 |
|---|---|---|
| `--dataset 日目标`（该报表里没有这个数据集） | `模板里没有数据集 日目标；现有: 销售, ds_target` | 可用（直接给出正确名字） |
| `--dataset 销售 --replace "这段SQL里根本没有=xxxx"` | `--replace 的 '这段SQL里根本没有' 在数据集 销售 的 SQL 里没出现` | **可用（关键：匹配 0 次是报错，不是静默成功）** |
| `--replace "onlyold"`（缺 `=`） | `--replace 要写成 OLD=NEW，收到 'onlyold'` | 可用 |
| `--dataset 销售 --connection impala_other` | `{"kind":"dataset.connection","before":"demo_conn","after":"impala_other"}`，`bytes 215372→215365` | 可用（before/after 明确） |
| `--dataset 销售 --param 不存在的参数 --default x` | `数据集 销售 没有参数 不存在的参数；现有: shops, edate` | 可用 |
| `--dataset 销售 --param edate --default 20260101` | `{"kind":"dataset.parameter","param":"edate","before":"","after":"20260101"}` | 可用 |
| 裸调用（没有任何编辑动作） | `没有给任何编辑动作（--sql / --replace / --connection / --param+--default）` | 可用 |

错误信息质量整体很好：**每条都告诉你"哪里错了 + 现在有什么"**，不需要回头翻文档。

### 8.4 第二轮回归测试增量

`tests/test_download_and_write_guards.py` 从 27 例扩到 **44 例**，新增：

- `rpc` 写守门 8 例参数化（含 `<scope>.tmp` / `<scope>.tmp/x.cpt` / `<scope>x/x.cpt` 必须拒绝，`<scope>/a.cpt.tmp` 必须放行）——锁死 `.tmp` 逃逸；
- `check_write_scope` 无路径参数 → 拒绝；`deny` 策略不会被 `--yes` 绕过；
- `assert_export_magic` 7 例（排队页 / 出错页 / word=RTF / 各格式正例）。

全量：**180 passed / 2 failed**（同 §6 的两例历史遗留；Lead 按新写范围语义重写守门测试后为 195 passed）。

### 8.5 教训：闸门语义与文档不一致（与 B2 同根因）—— 一次真实事故

**事故**：`feat-miner` 验证 `report edit --apply` 守门时，在**没设 `FRCLI_WRITE_SCOPE`** 的 shell 里跑，**真的写掉了** `demo_group/other_user/legacy_rpt.cpt`（返回 `applied:true, verified:true`）。
**根因不是手误，是判定与文档不一致**：`assert_in_write_scope` 当时是「env 未设 = **不限制**」，而所有文档（SKILL.md / AGENTS.md / 本报告 §4）都写「服务器写操作**只能**在 `skill测试` 内」。两者从不同一条命令上看不出区别 —— 于是"以为有沙箱，其实没有"。
**恢复**：靠 `upload_template` 的自动备份逐字节还原（Lead 独立核验：SHA256 与主备份一致、注入值消失、原值在、`other_user/` 全目录只有该文件 mtime 变化）。**生产无残留改动。**

**这与 B2（`FRCLI_WRITE_SCOPE` 漏挂 `upload_template`）是同一类根因**，值得单独记一条：

> **判据：文档写的边界，与代码实际的判定，必须能被同一条命令同时验证。**
> 三条自检——
> 1. **默认值必须 fail-closed**：安全开关的"没配置"应当等于"拒绝"，而不是"不限制"（`沉默 ≠ 不限制`）。B2 与本次事故都是"默认放行"造成的。
> 2. **判定只能有一份实现**：`rpc.py` 曾经另写一份 `in_scope` 并多剥了 `.tmp`，导致 `<scope>.tmp`（沙箱的**兄弟节点**）被判成域内放行 —— 同一个概念两份实现必然漂移。
> 3. **验收要用"命令"而不是"读代码"**：主张"越界会被拦"时，必须有一条**真能跑**的越界命令输出为证；只看 `grep` 命中次数、只看文档措辞，都会自证成功（Lead 事后复盘：B2 当时正是靠"统计 `assert_in_write_scope` 出现次数 = 1"自证的）。

**新语义（0.6.0，fail-closed）与我的复验**（模式 3 按 Lead 要求**只用哨兵**，未真写）：

| 档 | 设置 | 目标 | 实测 |
|---|---|---|---|
| 1 | 什么都不设 | 团队目录内 / 生产报表 | ✅ 本地拒绝：`写操作未指定范围，已拒绝（沉默不等于不限制）。二选一： · 限定范围：export FRCLI_WRITE_SCOPE="<目录>" 后再执行 · 确认要写这个目标：命令行加 --any-path（本次调用生效）` |
| 2 | `FRCLI_WRITE_SCOPE=<测试目录>` | 域内 | → 到网络层（哨兵拦下，未发请求） |
| 2 | 同上 | 生产报表 / `临时/` / `<scope>.tmp` / `..` / 兄弟目录 / `assets/` / 绝对路径 | ✅ 全部本地拒绝 |
| 3 | `--any-path`（`FRCLI_ALLOW_ANY_PATH=1`） | 生产报表 | → 到网络层（**哨兵验证，未真写**）；`report upload --help` 可见 `--any-path` |

**对"上手体验"的正面影响**：模式 1 的报错把两条出路（限定范围 / 显式放开）都写在同一条消息里，agent 不需要翻文档就知道下一步 —— 这正是 §5 里"错误可诊断"该有的样子。

---

## 9. 冻结验收（0.6.0）

**验收指纹**：`src/` 指纹 `0dde652aeb8f7eed82a3583fb01907a3`（`cat src/frcli/*.py src/frcli/commands/*.py | shasum -a 256`），版本三处均 `0.6.0`，基线 commit `709ed77`。
（说明：Lead 先给的冻结指纹是 `2e72214dee11a57b6775e69dfcde20ff`；我据此启动了第①轮验收，期间 Lead 通知指纹因 3 处收尾改动变为 `0dde652a…`。**为保证"验的就是冻结版"，我把全部 5 项在新指纹上重跑了一遍**，下面结果均出自重跑。）

| # | 项目 | 结果 |
|---|---|---|
| 1 | 指纹/版本/自举/副本 | ✅ 指纹与 Lead 给的一致；`__init__.py`/`pyproject.toml`/`SKILL.md` 三处均 `0.6.0`；`references/run.py --version` → `0.6.0`；安装态副本与仓库 `diff -rq` **0 行** |
| 1 | `pytest tests/` | ✅ **201 passed / 2 failed**（两例为历史遗留，见 §6） |
| 1 | 我的 44 例离线测试 | ✅ 44 passed |
| 1 | `flake8 --max-line-length=100` | 我的测试文件 clean；`src/frcli/` 余 15 条，**逐文件与基线 commit `709ed77` 对比后条数完全相同**（client.py 8 / export.py 2 / schedule.py 3 / server.py 1 / output.py 1）→ 确认为既有问题，本次未新增 |
| 2 | 只读套件 37 条 | ✅ **37 通过 / 0 失败**（`server test`、`report list/ws-list/info/paras/datasets/--sql/serverdatasets/columns/authed/versions/fonts/edit --list/download`、`rpc services/--local/methods/call×4`、`system×5`、`entry×3`、`user×3`、`schedule×5`） |
| 3 | 端到端（`report edit` 路线） | ✅ `download`(498170B `<WorkBook>`) → `upload` 副本(`verified:true`) → `edit --list`(14 数据集) → dry-run diff(498170→498174) → `--apply`(`previous_sha256` 一致、备份落盘、`verified:true`) → `export excel` → **基线 225450B 无 marker / 改动后 225187B 含 `987654.32`（D4）** → `delete --force`(`deleted:true`) |
| 4 | 越界写三档 | ✅ 模式1（不设范围：域内 + 生产报表**都拒绝**，消息给出 `FRCLI_WRITE_SCOPE`/`--any-path` 两条出路）；模式2（设范围：生产报表 / `..` / `超级管理员` / 兄弟目录 `skill测试2` / `<scope>.tmp` / 绝对路径 / `assets/` **7/7 拒绝**，域内放行）；模式3（`--any-path`：**哨兵验证放行、零请求**） |
| 4 | `rpc call` 一致性 | ✅ `--any-path` 已暴露；离线语义 5 例全对（无 env 无 any-path → 拒绝含域内；设 scope → 域内放行/越界拒绝；any-path → 放行） |
| 5 | 测试目录复查 | ✅ `ws-list` → `count 1`，**只剩原有的 `_目录说明.txt`**（团队创建的 e2e 副本已清空） |

**附加安全核对**：源报表 `dept_a/dept_b/sales_daily.cpt` **未被污染** —— `日目标` SQL 仍是原文 `,sum(sales_amt_target) sales_amt_target`（无 marker），大小 498170B 不变。

**冻结验收期间观察到的两点（均非缺陷，供参考）**
1. **`report datasets` 对多数据集模板偶发失败**：同一条命令对 `sales_daily.cpt`（14 个数据集）在一次导出密集期返回**空 stdout**（错误走 stderr），**重试即成功**。根因是它走 `format=cpt`，服务端会校验**全部**数据集，上游瞬时报错就整体失败（与 §3-S3 同源）。偶发、非确定性，未见固定复现路径。
2. **`rpc.call` 的 `--any-path` 通过写 `os.environ` 实现**（`check_write_scope(..., any_path=True)` 会设置 `FRCLI_ALLOW_ANY_PATH=1`）。对"一条命令一个进程"的 CLI 无影响；若将来把 `rpc.py` 当库在同一进程里复用，这个环境变量会残留并放行后续调用 —— 建议改成参数透传而非改环境。

---

## 附：证据留存

- 端到端日志：`/tmp/frv/e2e.log`、`/tmp/frv/baseline.log`
- 产物：`/tmp/frv/base-final.xlsx`（pristine，225450B）、`/tmp/frv/mod4.xlsx`（marker，225913B，D4=987654.32）
- 服务端备份：`~/.frcli/backups/20260927-175801__…demo-e2e-175737.cpt`、`20260927-175937__…`（均为团队测试副本的历史版本）
- 测试目录复查：`report ws-list "demo_group/demo_user/skill测试"` → `count 1`，仅剩原有的 `_目录说明.txt`
