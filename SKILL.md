---
name: fanruan-v10
version: 0.4.1
description: "使用 frcli 命令行工具操作 FineReport V10 报表服务器（帆软决策平台）。覆盖 8 个命令组：server(多实例配置) / report(模板目录·参数·数据集SQL·服务器数据集) / export(PDF·Excel·Word·图片·CSV·批量) / attach(附件上传下载) / system(版本·健康·模块·权限·登录策略) / entry(平台条目·消息) / user(用户·部门·岗位) / schedule(定时任务·执行记录·日志节点树)。触发词：FineReport、帆软、报表导出、.cpt、决策平台、定时任务、服务器数据集、数据集字段、执行记录、附件。导出会真实触发服务端报表计算，产物必须校验魔数并调大超时。"
metadata:
  requires:
    bins: ["frcli"]
  cliHelp: "frcli --help"
---

# fanruan_v10 Skill（frcli · FineReport V10）

用 `frcli` 操作 FineReport V10 决策平台：浏览模板目录、读数据集 SQL、导出报表、管理定时任务。
所有功能通过 `frcli <命令组> <命令>` 调用，`<命令> --help` 查看参数。

## 1. 何时使用

- 导出帆软报表（PDF / Excel / Word / 图片 / CSV），含按日期等参数批量导出
- 查看报表的数据集定义与 SQL（口径溯源、找报表参数）
- 查/改/跑 FineReport 定时任务（调度、执行历史）
- 定位「报表里这个数怎么来的」

不适合：改报表模板本身（.cpt 设计）——服务器无 Web API，走决策平台网页。

## 2. 前置条件

1. 配置实例（密码会明文写入 `~/.frcli/config.yaml`）：

   ```bash
   frcli server add yh --url https://<服务器> -u <工号> -p '<密码>' --set-default
   ```

   ⚠️ `server add` 不传 `-p` 时登录会**交互式提示密码**，非交互环境下会挂住 —— agent 必须带 `-p`。

2. 验证：`frcli server test`

> 平时直接用 `frcli`。**仅当**报 `command not found` 才进入自检+自举：见 §6，或直接读 `references/install.md`（skill 内置 Python 源码，可离线自举，跨 Windows/macOS/Linux）。

## 3. 命令树

```
frcli [--version] [-i INSTANCE] [-v]

├── server                          实例管理（配置存 ~/.frcli/config.yaml）
│   ├── list [-f json|table]                 实例列表（含默认标记）
│   ├── add NAME --url URL -u USER [-p PASS] [-w /webroot] [--set-default]
│   ├── remove NAME                          删实例并清其 token 缓存
│   ├── set-default NAME
│   └── test [NAME]                          连接 + 登录校验
│
├── report                          报表模板（决策平台目录树）
│   ├── list [DIRECTORY] [--keyword K] [--type cpt]   列目录；⚠️ 目录要具体，`/` = 全量（实测 3873 条）
│   │                                              `--keyword/--type` 走**服务端筛选**，别拉全量再本地筛
│   ├── info REPORT [-f]                     报表信息：数据集名清单 + 参数清单
│   ├── paras REPORT [-f json|table]         报表参数定义（官方接口，含派生参数公式）
│   ├── datasets REPORT [-f json|table] [--sql]   数据集名/参数/完整 SQL（--sql 不截断）
│   ├── download REPORT [-o LOCAL]           下载 .cpt 模板（实测 3.4MB XML）
│   ├── serverdatasets [-f]                  服务器数据集清单（平台级，实测 113 个）
│   ├── columns DATASET [-f]                 服务器数据集的字段清单（列名/列类型）
│   ├── authed [--keyword K]                 当前账号有权限的模板树
│   ├── upload LOCAL REMOTE                  ❌ 未实现（服务器无写模板内容的 REST 接口，见 §6.7）
│   └── delete REPORT                        ❌ 未实现（同上）
│
├── export                          报表导出（真实触发服务端计算）
│   ├── pdf|excel|word|image|csv REPORT [-o FILE] [--params JSON] [-i]
│   │        缺省输出名派生自报表名：.pdf / .xlsx / .docx / .png / .csv
│   └── batch MANIFEST.yaml [-i]             批量导出（YAML 清单，逐条汇总成败）
│
├── attach                          服务器附件（落附件缓存，**不动报表目录**）
│   ├── upload LOCAL [--name NAME]           上传本地文件 → 返回 attach_id
│   └── remove ATTACH_ID                     删除附件（传完记得清理）
│
├── system                          系统与平台信息（🟢 只读）
│   ├── version [-f]                         服务端版本 + 各模块 jar 版本
│   ├── health [-f]                          系统健康状态
│   ├── modules [--keyword K]                决策平台模块树
│   ├── authority                            权限开关（分级授权/报表编辑/调度…）
│   └── login-policy                         登录配置 + 密码策略 + 密码到期提醒
│
├── entry                           平台条目与消息（🟢 只读）
│   │   ⚠️ 条目树 id 是 UUID，与 report 的报表目录树（id = 文件路径）是两套
│   ├── list [--page P] [-n N] [--keyword K] 条目分页列表
│   ├── roots [-f]                           条目根节点
│   ├── all [-f]                             全量条目
│   └── messages [--unread] [-n N]           平台消息（未读/全部）
│
├── user                            用户与组织（🟢 只读）
│   ├── list [-f]                            当前账号可见用户（工号+姓名，非全量目录）
│   ├── me                                   当前登录账号信息（工号/姓名/角色）
│   ├── departments [--keyword K]            部门树（本账号实测为空）
│   └── posts [--keyword K]                  岗位列表（实测 39 条）
│
└── schedule                        定时任务（生产调度，写操作危险）
    ├── list [-f]                            仅返回任务名
    ├── tasks [--page P] [-n N] [--all]      任务列表**含 taskId**（--all = listAll 全量）
    ├── get TASK_NAME [-f]                   任务详情（拿 UUID `id` 用）
    ├── exists TASK_NAME                     按准确名字判断任务是否存在
    ├── create CONFIG.yaml                   从 YAML 建任务
    ├── update TASK_NAME [-d DESC]           更新（内部先按名查到 id）
    ├── delete TASK_ID                       ⚠️ 参数是 UUID `id`，不是任务名
    ├── run TASK_NAME                        ⚠️ 立即在生产执行该调度
    ├── executing [-f]                       当前正在执行的任务
    ├── history [TASK_NAME] [-n N] [-f]      执行历史（不传名字=最近全局日志，取 logId 用）
    ├── record TASK_NAME [--page P] [-n N]   某任务的执行记录+结果（含 detailMessage/runType）
    ├── records [--page P] [-n N]            全平台执行记录（total 十万级）
    ├── log TASK_LOG_ID [-f]                 单条日志详情节点树（哪一步失败、错误内容）
    └── setting                              调度全局设置（消息开关/日志清理）
```

**报表路径写法**（本服务器的真实约定，实测）：

```
demo_group/demo_user/dept_a/dept_b/sales_daily.cpt
```

相对路径、带 `.cpt`、**不带前导 `/`**、**不用 `//doc//`**。路径直接取自 `report list <目录>` 返回的 `path` 字段。

## 4. 安全约束

| 等级 | 命令 | 说明 |
|------|------|------|
| 🟢 只读 | `server list/test`、`report list/info/paras/datasets/download/serverdatasets/columns/authed`、`schedule list/tasks/get/exists/executing/history/record/records/log/setting`、`system *`、`entry *`、`user *` | 直接执行 |
| 🟡 计算 | `export *`、`export batch` | 数据只读，但服务端真实跑报表（复杂报表 50s+，批量可达数十分钟）；批量前说明规模 |
| 🟠 本地写 | `server add/remove/set-default` | 只改实测环境 `~/.frcli/config.yaml` 与 token 缓存 |
| 🟠 服务端写（轻） | `attach upload/remove` | 只往**服务器附件缓存**写/删文件，不碰报表目录与调度；upload 会在服务端留文件，用完 `remove` 清理 |
| 🔴 危险 | `schedule create/update/delete/run` | 直接改/跑**生产调度**：`run` 会立刻执行并推送下游（飞书/FTP/邮件），`delete` 不可逆 |

agent 默认直接执行只读；🟡 批量前说明；🔴 必须先向用户确认影响范围再执行。

## 5. 常见任务

```bash
# 0) 配置与连通性
frcli server list
frcli server test

# 1) 找报表（目录必须具体，避免 `/` 拉全量）
frcli report list "demo_group/demo_user/dept_a/dept_b" -f table

# 2) 摸清参数与取数口径（agent 做分析前的最有价值一步）
frcli report info "demo_group/demo_user/dept_a/dept_b/sales_daily.cpt"
frcli report paras "demo_group/demo_user/dept_a/dept_b/sales_daily.cpt"    # 官方参数接口：含派生参数公式
frcli report datasets "demo_group/demo_user/dept_a/dept_b/sales_daily.cpt" --sql -f table

# 3) 导出（只传驱动参数，其余由模板/全局参数自动派生；复杂报表务必调大超时）
FRCLI_TIMEOUT=300 frcli export excel "demo_group/demo_user/dept_a/dept_b/sales_daily.cpt" \
    -o /tmp/sales_daily_20260731.xlsx \
    --params '{"edate":"20260731","extype":"simple"}'
#   edate 为驱动参数（yyyyMMdd）；extype=simple 可绕开部分模板分页报错

# 4) 校验产物（必做，否则会把 HTML 出错页面当 Excel 交出去）
python3 -c "print('OK' if open('/tmp/sales_daily_20260731.xlsx','rb').read(4)==b'PK\x03\x04' else '坏文件')"

# 5) 批量导出
#   manifest.yaml:
#     reports:
#       - path: demo_group/demo_user/dept_a/dept_b/sales_daily.cpt
#         format: excel
#         output: ./out/sales_daily_20260731.xlsx
#         params: {edate: "20260731", extype: simple}
FRCLI_TIMEOUT=600 frcli export batch manifest.yaml

# 6) 定时任务（读）
frcli schedule list -f table
frcli schedule get "demo_user_销售_示例概览by月_飞书"        # 拿 UUID id
frcli schedule history "demo_user_销售_示例概览by月_飞书" -n 5      # 返回 id = logId
frcli schedule record "demo_task_超时明细" -n 20                  # 执行记录+结果（total 分页）
frcli schedule log "demo_task_超时明细_same_fire_1000000000000"   # 日志节点树：哪一步失败
#   写操作（🔴 先确认）：create / update / delete <UUID> / run <任务名>

# 7) 切换实例（多环境）
frcli -i dev report list "某目录"

# 8) 附件（服务器附件缓存，非报表目录）
frcli attach upload /tmp/说明.docx --name 说明.docx   # → 返回 attach_id
frcli attach remove default1789441975426_Olw7l        # 用完清理

# 9) 系统 / 平台信息（只读）
frcli system version            # 服务端版本（本服务器 10.0.19）+ 各模块 jar
frcli system health
frcli system authority          # 权限开关
frcli system login-policy       # 登录配置 + 密码策略
frcli entry messages --unread   # 平台未读消息
frcli user me                   # 我是谁（工号/姓名/角色）
frcli report serverdatasets -f table          # 服务器数据集清单
frcli report columns 22shop_beijing -f table  # 数据集字段

# 10) 调度增强（只读）
frcli schedule tasks --all -f table      # 全量任务（含 taskId）
frcli schedule exists "demo_task_超时明细"
frcli schedule executing                 # 正在跑的
frcli schedule records -n 20             # 全平台执行记录
frcli schedule setting
```

输出与退出码：`-f json`（默认，agent 友好）/ `-f table`；退出码 `0` 成功、`1` 业务错误、`2` 配置错误、`3` 连接错误。

## 6. 关键坑点（均已实测）

### 6.1 导出「成功」不等于拿到报表

`frcli export` 只看 HTTP 状态码，而 FineReport 出错时仍返回 **200 + HTML 出错页面**，CLI 会照写文件并报 `status: ok`。
典型触发：数据集 SQL 报错（如 `错误代码:11300001 数据集 [xxx] 配置错误 [ImpalaJDBCDriver] Could not resolve column/field reference`）、缺必填参数。

**必须校验魔数**：

| 格式 | 文件头 |
|------|--------|
| xlsx / docx | `PK\x03\x04` |
| pdf | `%PDF` |
| png | `\x89PNG` |
| 失败 | HTML，含 `<title>出错页面</title>` / `Oops!!!` |

出错页面里的 `detail-message` 是 html 实体编码的**具体报错**（错误代码 + 原始 SQL），解码后可直接定位坏数据集。

### 6.2 默认 30s 超时，复杂报表必然超时

实测同一张报表：默认超时 → `导出请求失败: The read operation timed out`；`FRCLI_TIMEOUT=300` → 50s 成功导出 225KB xlsx。
**导出前先设 `FRCLI_TIMEOUT=300`（批量 600）**，不要等失败再重试。

### 6.3 参数只传驱动参数

模板里的 `${edate}` `${sdate_mtd}` 等派生参数无需手算，FineReport 根据驱动参数自动推导。
从 `report datasets` 的 SQL 里找 `${...}` 出现的主参数（通常是 `edate`/`sdate`），只传它 + `extype=simple`。

### 6.4 空数组 `[]` = 认证失效（**未必过期**）

token 缓存 `~/.frcli/tokens/<instance>.json`（默认 24h）。`schedule list` / `report list` 返回 `[]` 而服务器确有数据时，先怀疑认证，而不是「服务器没有数据」。

**本地 `expires_at` 还在未来也会失效**（实测：缓存远未过期，列表全返回 `[]`，换新 token 立刻正常）。本服务器失效 token 的真实表现是 **302 重定向到 CAS 登录页**（`https://sso.example.com/cas/login?...`），**不是 401** —— 只判 401/403 会漏掉。

0.1.1 起 `_request` 已识别 302→CAS：自动清缓存重登一次并重试；重登后仍被踢回登录页才报 `AUTH_FAILED`。仍可手动兜底：

```bash
rm -f ~/.frcli/tokens/*.json    # 下次调用自动重登
```

### 6.5 `report datasets` 读不到定义 = 该报表数据集本身报错

`report datasets/info/download` 走 `format=cpt` 取模板定义，服务端会校验数据集。数据集配置错误时返回 0 条 / `无法读取报表定义` —— 这不是 CLI 故障，而是**这张报表当前就是坏的**（导出也必然拿到出错页面）。

### 6.6 命令名与参数的真实语义

- `schedule get/run/update` 收的是**任务名**；`schedule delete` 收的是 **UUID `id`**（先 `schedule get` 拿）。传错会报 `任务不存在` 或删不动。
- `schedule get` 内部是**模糊搜索取第一条**，任务名需与 `schedule list` 完全一致，避免误命中。
- `report list <目录>` 结果里会**包含该目录自身**一条（`is_directory: true`），属正常实现，过滤掉即可。
- `report list /` 会返回**整个服务器**的文件树（实测 3870 条），不要用 `/` 当"顶层"。
- `schedule history [任务名]` 是 **taskName 精确匹配**：任务近几天没有日志就静默返回 `[]`，不代表 CLI 坏了（不传名字才看全局日志）。
- `server test` 0.1.1 起**真实发一次认证请求**（返回 `http_status` + `relogin`）——此前只查本地缓存，缓存 token 已失效时照样报 ok（假阳性）。

### 6.7 改模板内容：REST 没有通道（已实测，别在这上面浪费时间）

- `report upload` / `report delete` → `'FineReportClient' object has no attribute ...`：CLI 有入口但 client 无实现。
- **服务器侧确实没有"写模板内容"的 REST 接口**（2026-09 实测 + 反编译确认）：
  - `TemplateBean` / `FileBean` 只有元数据字段（id/pId/text/path/description/showType/parameters…），**没有内容字段**；
  - `ReportEntryService.addTemplates()` 只写条目记录，无落盘调用；
  - 569 条路由里没有任何接口接收 .cpt 字节。
- 目录管理类写接口（`PUT /v10/template/{id}`、`POST /v10/{directoryId}/templates`、`PUT /v10/file/{id}`、`POST /v10/{pId}/directory`、`PUT /v10/entry(s)`、`POST /v10/dataset/upload`）对普通分析账号一律 `Fine-Dec_No_Privilege_Access_Page`。
- Designer 存模板走 `/decision/remote/design/service`（28 个内部 RPC 服务：`TplOperator`/`CommitHelper`/`EditLockOperator`/`EncryptOperator`…），载荷 **SM4 加密**（`/remote/design/check` 返回 `transmissionEncryption:2` + `frontSM4Key`/`frontSeed`）→ 抓包也拿不到明文，不建议复刻。
- **唯一可用的服务端写操作是附件**（`attach upload/remove`，见 §3/§4）。
- 结论：批量改模板内容 = `report download` 拉 .cpt（XML）→ 本地改 `<Query>` / `<DatabaseName>` → 在 Designer 里导入。
- `frcli query ...` → 不存在（旧 README 遗留）；要看 SQL 用 `report datasets`。

### 6.10 `format=cpt` 的响应字节不稳定，别用整体 hash 判断"模板有没有被改"

同一模板连续两次取定义，SHA256 就不同（实测 3 次三个值）。逐行 diff 后差异**只有 1 行**：

```
<![CDATA[org.apache.catalina.core.ApplicationMappingImpl@72d48284]]></O>
<![CDATA[org.apache.catalina.core.ApplicationMappingImpl@268f721c]]></O>
```

这是容器对象的 identity hash，每次请求都变（长度相同，所以文件大小看着不变）。

**判据**：要比对模板是否被改动，用**结构化比对** —— `<TableData name>` / `<Query>` / `<DatabaseName>` 的哈希，
不要用整文件 SHA256。`report download` 拿来 diff 时同理，先剔除这类易变行。

### 6.8 底层 API（需要扩展 / 直连调试时）

认证 `POST {workspace}/decision/login`（JSON `{username,password}` → `data.accessToken`，**必须保留登录返回的 cookies**，否则被重定向到 CAS）；`workspace` 默认 `/webroot`。

| 功能 | 端点 | 方法 |
|------|------|------|
| 模板文件树 | `/decision/v10/templates/all[?keyword=&fileTypes[]=]` | GET |
| 模板定义 / 导出 | `/decision/view/report?reportlet=<path>&format=cpt|<pdf/excel/...>` | GET |
| 任务名列表 | `/decision/v10/schedule/task/names` | GET |
| 任务搜索/详情 | `/decision/v10/schedule/task/search` | POST `{taskName}` |
| 任务增/改 | `/decision/v10/schedule/task` | POST / PUT（PUT 体必须含 `id`） |
| 任务删除 | `/decision/v10/schedule/task/deletes` | POST `{ids:[...]}` |
| 立即执行 | `/decision/v10/schedule/task/{id}/once` | POST |
| 执行历史（只有 id） | `/decision/v10/schedule/task/log/info` | POST `{taskName}` |
| 执行记录 + 结果 | `/decision/v10/schedule/record/search` | POST `{taskName,page,perPage}` |
| 日志详情节点树 | `/decision/v10/schedule/task/log/details?taskLogId=<id>` | GET |
| 报表参数（官方） | `/decision/v10/report/template/paras?path=<path>` | GET |
| 服务端版本 | `/decision/system/version` | GET |
| 任务全量（带 taskId） | `/decision/v10/schedule/task/listAll/2` | GET |
| 任务分页（带 taskId） | `/decision/v10/schedule/task/list/2?page=&count=` | GET |
| 任务是否存在 | `/decision/v10/schedule/task/{name}/exists` | GET |
| 执行中 / 忙碌度 | `/decision/v10/schedule/executing`、`/info/executing` | GET |
| 全平台执行记录 | `/decision/v10/schedule/record/list?page=&perPage=` | GET |
| 调度全局设置 | `/decision/v10/schedule/setting` | GET |
| 系统版本 / 健康 | `/decision/system/version`、`/decision/system/health` | GET |
| 平台模块 / 权限开关 | `/decision/v10/decision/modules`、`/decision/v10/authority/config` | GET |
| 登录配置 / 密码策略 | `/decision/login/config`、`/decision/login/password/strategy`、`/password/waring/time` | GET |
| 平台条目 | `/decision/v10/entries?page=&count=&keyword=`、`/entry/roots`、`/entries/all` | GET |
| 平台消息 | `/decision/v10/message/unread`、`/message/list?page=&count=` | GET |
| 用户 / 组织 | `POST /decision/v10/users`、`/decision/v10/user/account`、`/departments`、`/posts` | POST / GET |
| 服务器数据集 | `/decision/v10/serverdatasets`、`/decision/v10/{ds}/datasetcolumns` | GET |
| 附件上传 / 删除 | `/decision/v10/attach/upload`（multipart 字段 `file` + `filename`/`width`/`height`/`isHolder`）、`/decision/v10/attach/remove/{attachId}` | POST / DELETE |

`follow_redirects=False` 是必需的，否则 Authorization 头会被丢掉。`/decision/login/*`（登录/配置/密码策略）**不带 `v10` 前缀**。

### 6.9 出错页 `detail-message` 是排障与挖接口的入口

除导出（§6.1）外，**任意 `/decision` 接口**出错都返回 **200 + HTML 出错页**，原因写在 `detail-message` 里：

- `Required String parameter 'keyword' is not present` → 缺哪个参数直接告诉你
- `Request method 'GET' not supported` → 方法不对
- `Could not read JSON: Unrecognized field "count" (8 known properties: "taskName","logTime",...,"perPage","page"])` → **字段名写错时把合法字段全列出来**（`schedule record` 就是这么试通的）
- `Fine-Dec_No_Privilege_Access_Page` → 当前账号无该接口权限（管理类接口）
- `detail-message` 为空、只剩 `simple-message = Fine-Dec_Default_Error_Tip` → 通常是对象不存在（如 logId 已过期/被清理）

CLI 已翻成异常：`API_ERROR` + 平台原文（`_unwrap_json`）。要挖更多接口：控制器在
`fine-decision-10.0.jar` / `fine-decision-report-10.0.jar` / `fine-schedule-10.0.jar`，用 Spring
`@RequestMapping`（shade 成 `com.fr.third.springframework...`），`javap -v -p <class>` 反解。

实测服务端 bug：`POST /v10/schedule/task/log/search` 抛 `QueryConditionImpl cannot be cast to TaskLogRestriction`，该版本不可用 —— 用 `log/info` + `log/details` 代替。

## 7. 故障排查

| 现象 | 处理 |
|------|------|
| `frcli: command not found` | 按 `references/install.md` 自举：`python <base>/references/run.py <命令>` 或 `cd <base>/src && python -m frcli <命令>`（零安装） |
| 导出 `status: ok` 但文件打不开 | 内容其实是 HTML 出错页面：核对魔数，解码页面里的 `detail-message` 定位坏数据集（§6.1） |
| `导出请求失败: The read operation timed out` | 设 `FRCLI_TIMEOUT=300`（批量 600）重跑（§6.2） |
| `schedule list` / `report list` 返回 `[]` | 认证失效（可能未过期）：0.1.1 起自动重登一次；仍为空则手动 `rm -f ~/.frcli/tokens/*.json`（§6.4） |
| `server test` 报 ok 但列表全 `[]` | 旧版假阳性（只查本地缓存，真发请求）；`relogin: true` 表示这回检测到失效并重登过（§6.6） |
| `未配置任何 FineReport 实例` | `frcli server add ... --set-default` |
| `实例 'x' 不存在` | `frcli server list` 看可用实例；配置搜索顺序：`$FRCLI_CONFIG` → `~/.frcli/config.yaml` → `./.frcli.yaml` |
| 登录时卡住不动 | `server add` 没带 `-p`，改为带密码重建实例 |
| `report datasets` 返回 `[]` | 该报表数据集在服务端报错，报表本身是坏的（§6.5） |
| `'FineReportClient' object has no attribute 'upload_report'` | `report upload/delete` 未实现；**服务器也没有写模板内容的 REST 接口**（§6.7），改模板走 Designer |
| `任务不存在: xxx` | `schedule get/run/update` 用准确任务名（先 `schedule list`） |
| `schedule delete` 删不掉 | 传 UUID `id` 而非任务名（§6.6） |
| `report paras` 返回 `[]` | 该报表没有参数 **或路径不存在**（平台对不存在的路径也返回空）；先用 `report list <目录>` 核对路径 |
| `API_ERROR: Required String parameter ...` / `请求方法不支持` / `无此接口权限` | 直接调底层接口时的平台原文，按提示补参数/换方法/换账号（§6.9） |
| `API_ERROR: 平台返回错误页（无详细信息）` | 多为对象不存在：`schedule log` 的 logId 已过期或被清理，用 `schedule history` 重新取（§6.9） |
| `AUTH_FAILED: 重新登录后仍被重定向到登录页` | 密码错、账号被锁或无权限；检查 `~/.frcli/config.yaml` 里的密码与网络 |
| 请求被重定向到 CAS / 返回登录页 HTML | token 失效：CLI 自动重登一次；仍失败检查密码或网络（§6.4） |
| 对比 .cpt 整体 hash 发现「模板被改了」 | `format=cpt` 响应字节不稳定（内嵌容器 identity hash），改用结构化比对（§6.10） |
| HTTPS 证书校验 | 客户端默认 `CERT_NONE` + legacy renegotiation，自签证书可直接用；`FRCLI_CA_CERT` 指向 CA 文件（当前实现下不改变校验行为） |

> 命令清单以 `frcli <命令组> --help` 为准；本文件与 CLI 不一致时，先以 `--help` 为准并回写本文件。
