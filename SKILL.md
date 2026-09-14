---
name: fanruan_v10
version: 0.1.0
description: "使用 frcli 命令行工具操作 FineReport V10 报表服务器（帆软决策平台）。覆盖 server(多实例配置) / report(模板目录·下载·数据集SQL) / export(PDF·Excel·Word·图片·CSV·批量) / schedule(定时任务) 4 个命令组。触发词：FineReport、帆软、报表导出、.cpt、决策平台、定时任务。导出会真实触发服务端报表计算，产物必须校验魔数并调大超时。"
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
│   ├── list [DIRECTORY] [-f json|table]     列目录；⚠️ 目录要具体，`/` = 全量（实测 3870 条）
│   ├── info REPORT [-f]                     报表信息：数据集名清单 + 参数清单
│   ├── datasets REPORT [-f json|table] [--sql]   数据集名/参数/完整 SQL（--sql 不截断）
│   ├── download REPORT [-o LOCAL]           下载 .cpt 模板（实测 3.4MB XML）
│   ├── upload LOCAL REMOTE                  ❌ 未实现（client 无该方法）
│   └── delete REPORT                        ❌ 未实现（client 无该方法）
│
├── export                          报表导出（真实触发服务端计算）
│   ├── pdf|excel|word|image|csv REPORT [-o FILE] [--params JSON] [-i]
│   │        缺省输出名派生自报表名：.pdf / .xlsx / .docx / .png / .csv
│   └── batch MANIFEST.yaml [-i]             批量导出（YAML 清单，逐条汇总成败）
│
└── schedule                        定时任务（生产调度，写操作危险）
    ├── list [-f]                            仅返回任务名
    ├── get TASK_NAME [-f]                   任务详情（拿 UUID `id` 用）
    ├── create CONFIG.yaml                   从 YAML 建任务
    ├── update TASK_NAME [-d DESC]           更新（内部先按名查到 id）
    ├── delete TASK_ID                       ⚠️ 参数是 UUID `id`，不是任务名
    ├── run TASK_NAME                        ⚠️ 立即在生产执行该调度
    └── history [TASK_NAME] [-n N] [-f]      执行历史（不传名字=最近全局日志）
```

**报表路径写法**（本服务器的真实约定，实测）：

```
demo_group/demo_user/dept_a/dept_b/sales_daily.cpt
```

相对路径、带 `.cpt`、**不带前导 `/`**、**不用 `//doc//`**。路径直接取自 `report list <目录>` 返回的 `path` 字段。

## 4. 安全约束

| 等级 | 命令 | 说明 |
|------|------|------|
| 🟢 只读 | `server list/test`、`report list/info/datasets/download`、`schedule list/get/history` | 直接执行 |
| 🟡 计算 | `export *`、`export batch` | 数据只读，但服务端真实跑报表（复杂报表 50s+，批量可达数十分钟）；批量前说明规模 |
| 🟠 本地写 | `server add/remove/set-default` | 只改实测环境 `~/.frcli/config.yaml` 与 token 缓存 |
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
frcli schedule history "demo_user_销售_示例概览by月_飞书" -n 5
#   写操作（🔴 先确认）：create / update / delete <UUID> / run <任务名>

# 7) 切换实例（多环境）
frcli -i dev report list "某目录"
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

### 6.4 空数组 `[]` 多半是 token 缓存过期

token 缓存 `~/.frcli/tokens/<instance>.json`（默认 24h）。`schedule list` / `report list` 返回 `[]` 而服务器确有数据时：

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

### 6.7 未实现 / 已废弃的命令

- `report upload` / `report delete` → `'FineReportClient' object has no attribute ...`：CLI 有入口但 client 无实现，服务器也不支持 Web API 改模板，改模板请走决策平台网页。
- `frcli query ...` → 不存在（旧 README 遗留）；要看 SQL 用 `report datasets`。

### 6.8 底层 API（需要扩展 / 直连调试时）

认证 `POST {workspace}/decision/login`（JSON `{username,password}` → `data.accessToken`，**必须保留登录返回的 cookies**，否则被重定向到 CAS）；`workspace` 默认 `/webroot`。

| 功能 | 端点 | 方法 |
|------|------|------|
| 模板文件树 | `/decision/v10/templates/all` | GET |
| 模板定义 / 导出 | `/decision/view/report?reportlet=<path>&format=cpt|<pdf/excel/...>` | GET |
| 任务名列表 | `/decision/v10/schedule/task/names` | GET |
| 任务搜索/详情 | `/decision/v10/schedule/task/search` | POST `{taskName}` |
| 任务增/改 | `/decision/v10/schedule/task` | POST / PUT（PUT 体必须含 `id`） |
| 任务删除 | `/decision/v10/schedule/task/deletes` | POST `{ids:[...]}` |
| 立即执行 | `/decision/v10/schedule/task/{id}/once` | POST |
| 执行历史 | `/decision/v10/schedule/task/log/info` | POST |

`follow_redirects=False` 是必需的，否则 Authorization 头会被丢掉。

## 7. 故障排查

| 现象 | 处理 |
|------|------|
| `frcli: command not found` | 按 `references/install.md` 自举：`python <base>/references/run.py <命令>` 或 `cd <base>/src && python -m frcli <命令>`（零安装） |
| 导出 `status: ok` 但文件打不开 | 内容其实是 HTML 出错页面：核对魔数，解码页面里的 `detail-message` 定位坏数据集（§6.1） |
| `导出请求失败: The read operation timed out` | 设 `FRCLI_TIMEOUT=300`（批量 600）重跑（§6.2） |
| `schedule list` / `report list` 返回 `[]` | 清 token 缓存 `rm -f ~/.frcli/tokens/*.json`（§6.4） |
| `未配置任何 FineReport 实例` | `frcli server add ... --set-default` |
| `实例 'x' 不存在` | `frcli server list` 看可用实例；配置搜索顺序：`$FRCLI_CONFIG` → `~/.frcli/config.yaml` → `./.frcli.yaml` |
| 登录时卡住不动 | `server add` 没带 `-p`，改为带密码重建实例 |
| `report datasets` 返回 `[]` | 该报表数据集在服务端报错，报表本身是坏的（§6.5） |
| `'FineReportClient' object has no attribute 'upload_report'` | `report upload/delete` 未实现，走决策平台网页（§6.7） |
| `任务不存在: xxx` | `schedule get/run/update` 用准确任务名（先 `schedule list`） |
| `schedule delete` 删不掉 | 传 UUID `id` 而非任务名（§6.6） |
| 请求被重定向到 CAS / 返回登录页 HTML | token 失效，清缓存重试；仍失败检查密码或网络 |
| HTTPS 证书校验 | 客户端默认 `CERT_NONE` + legacy renegotiation，自签证书可直接用；`FRCLI_CA_CERT` 指向 CA 文件（当前实现下不改变校验行为） |

> 命令清单以 `frcli <命令组> --help` 为准；本文件与 CLI 不一致时，先以 `--help` 为准并回写本文件。
