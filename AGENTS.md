# fanruan_v10 —— Skill + frcli CLI 开发规范

> 本文件通过 AGENTS.md 叠加机制在本目录及子目录生效。
> 本目录**既是 `fanruan_v10` skill 的分发体，也是 `frcli` CLI 的产品源码仓库**（同源同仓，结构仿 `yh-bigdata`）。

## 项目定位

`fanruan_v10` skill 封装 `frcli` —— 与 FineReport V10 决策平台交互的 CLI（server / report / export / attach / system / entry / user / schedule 8 个命令组）。
目标是让 agent 不构造 JSON、不猜接口路径，只调固定命令。

- CLI 源码（唯一来源）：`src/frcli/`；skill 入口：`SKILL.md`；打包：`pyproject.toml`（src 布局）
- **不存在源码副本**，改 `src/frcli/` 即同时改了 CLI 与 skill，无需任何同步步骤（旧的两份副本布局已废弃）
- 仓库/目录名是 `fanruan_v10`，但 **skill frontmatter 名必须是 `fanruan-v10`**：宿主（DSH 等）只接受 `^[a-z0-9]+(-[a-z0-9]+)*$`，带下划线会被**静默丢弃**（不报错、不加载），2026-09 实测踩过

## 设计原则

1. **固定命令**：每个动作一条命令，agent 不拼 URL、不写 JSON body（除 `--params` 报表参数）
2. **只读优先**：浏览/读 SQL/查历史都是只读；导出是「只读数据 + 服务端计算」；改生产调度是危险操作
3. **自包含自举**：命令不在 PATH 时，用内置源码零安装跑起来（`references/install.md`）
4. **产物必须可验证**：导出结果一律校验魔数，绝不把 HTML 出错页面当报表交付

## 目录结构

```
fanruan_v10/
├── SKILL.md              # agent 入口（frontmatter: name/version/description/metadata）
├── README.md             # 人类可读说明
├── AGENTS.md             # 本文件
├── CLAUDE.md             # -> AGENTS.md（软链，相对路径）
├── CODEBUDDY.md          # -> AGENTS.md（软链，相对路径）
├── pyproject.toml        # 打包定义（src 布局）
├── src/frcli/            # CLI 唯一源码
│   ├── cli.py            # Click 命令组注册入口
│   ├── client.py         # FineReportClient：HTTP API 封装、导出、模板、定时任务
│   ├── auth.py           # TokenManager：登录、token 缓存、cookies 保留
│   ├── config.py         # 多实例配置（~/.frcli/config.yaml）
│   ├── output.py         # JSON / table 输出、成功与错误封装
│   ├── remotedesign.py   # 远程设计通道：服务端模板读写（report upload/delete 的后端）
│   ├── jser.py           # 手写 Java 对象序列化（远程设计 RPC 载荷/应答编解码）
│   ├── rdcrypto.py       # 纯 Python AES-ECB / SM4-ECB（握手密码加密，零依赖）
│   └── commands/         # server / report / export / attach / system / entry / user / schedule
├── references/
│   ├── install.md        # 自检 + 自举手册
│   ├── remotedesign.md   # 远程设计 RPC 协议说明 + 用 Designer jar 复核报文的脚本
│   ├── run.py            # 跨平台启动器（自举 + 软链自愈 + 版本提示）
│   ├── run.sh            # Unix 便捷入口
│   └── frcli             # 软链 shim
└── tests/                # pytest
```

## FineReport API 关键路径

认证：`POST {workspace}/decision/login`（JSON body `username` / `password`）→ 响应 `{"data": {"accessToken": "..."}}`

后续请求：`Authorization: Bearer <token>` + **保留登录返回的 cookies**，否则请求会被重定向到 CAS。

**`follow_redirects=False` 是必需的**，否则 Authorization 头会丢失。

已验证端点：

| 功能 | 端点 | 方法 |
|------|------|------|
| 模板文件树 | `/decision/v10/templates/all[?keyword=&fileTypes[]=]` | GET |
| 数据集定义 / 模板下载 | `/decision/view/report?reportlet=<path>&format=cpt` | GET |
| 报表导出 | `/decision/view/report?reportlet=<path>&format=pdf\|excel\|word\|image\|csv` | GET |
| 报表参数（官方） | `/decision/v10/report/template/paras?path=<path>` | GET |
| 服务端版本 / 健康 | `/decision/system/version`、`/decision/system/health` | GET |
| 定时任务列表 | `/decision/v10/schedule/task/names` | GET |
| 定时任务全量（带 taskId） | `/decision/v10/schedule/task/listAll/2` | GET |
| 定时任务搜索 | `/decision/v10/schedule/task/search` | POST `{taskName}` |
| 创建 / 更新任务 | `/decision/v10/schedule/task` | POST / PUT（PUT 体必须含 `id`；POST 带 `creator` 才写创建人） |
| 删除任务 | `/decision/v10/schedule/task/deletes` | POST **裸数组** `["<id>"]`（传 `{ids:[...]}` 会被拒） |
| 立即执行 | `/decision/v10/schedule/task/{id}/once` | POST |
| 执行历史（只有 id） | `/decision/v10/schedule/task/log/info` | POST `{taskName}` |
| 执行记录 + 结果 | `/decision/v10/schedule/record/search` | POST `{taskName,page,perPage}` |
| 日志详情节点树 | `/decision/v10/schedule/task/log/details?taskLogId=<id>` | GET |
| 附件上传 / 删除 | `/decision/v10/attach/upload`（multipart 字段 `file`）、`/decision/v10/attach/remove/{attachId}` | POST / DELETE |
| 系统版本 / 健康 / 模块 / 权限 | `/decision/system/version`、`/decision/system/health`、`/decision/v10/decision/modules`、`/decision/v10/authority/config` | GET |
| 登录配置 / 密码策略 | `/decision/login/config`、`/decision/login/password/strategy`、`/decision/login/password/waring/time` | GET |
| 平台条目 / 消息 | `/decision/v10/entries?page=&count=&keyword=`、`/entry/roots`、`/entries/all`、`/message/unread`、`/message/list` | GET |
| 用户 / 组织 | `POST /decision/v10/users`（GET 版本服务端报错）、`/decision/v10/user/account`、`/departments`、`/posts` | POST / GET |
| 服务器数据集 | `/decision/v10/serverdatasets`、`/decision/v10/{ds}/datasetcolumns` | GET |
| 调度增强 | `/decision/v10/schedule/task/list/{pt}?page=&count=`、`/task/{name}/exists`、`/executing`、`/record/list?page=&perPage=`、`/setting` | GET |
| 远程设计握手 | `/decision/remote/design/check` | POST（返回 frontSeed/frontSM4Key/transmissionEncryption） |
| 远程设计取 token | `/decision/remote/design/verify` | POST 表单 `username` + **加密后**的 `password` |
| 远程设计 RPC（写模板） | `/decision/remote/design/channel` | POST，body = gzip + Java 序列化的 Invocation |
| 远程设计服务清单 | `/decision/remote/design/service` | POST 表单 `username`+`password` |

不可用：`dataset preview`（需管理员权限）；
`POST /v10/schedule/task/log/search`（服务端 ClassCastException，该版本坏）。
登录/配置类 `/decision/login/*` **不带 `v10` 前缀**。

> 完整路由表（569 条 / 80 控制器）可由实测环境 Designer 安装包反解：控制器在
> `<FineReport 安装目录>/webapps/webroot/WEB-INF/lib/fine-decision-10.0.jar`（+ `-report`、`-schedule`），
> 用 Spring `@RequestMapping`（shade 为 `com.fr.third.springframework...`），`javap -v -p <class>` 读注解即可。

## 开发黄金流程

| 步骤 | 动作 |
|------|------|
| 改 | 编辑 `src/frcli/`（client.py 加方法 → commands/ 加子命令 → 更新 `SKILL.md`） |
| 装 | `pip install -e .`（本目录，editable，改完即生效） |
| 测 | `frcli --help` → 命令组 `--help` → 单条**只读**命令实测；`python -m pytest tests/` |
| 记 | 命令增删改同步 `SKILL.md` + `README.md`；新坑点写进 SKILL.md §6 与本文「实测坑点」 |

版本号三处保持一致：`src/frcli/__init__.py` 的 `__version__`、`pyproject.toml` 的 `version`、`SKILL.md` front-matter 的 `version`。

## 行为约束

- **测试只用只读命令**：`server list/test`、`report list/info/paras/datasets/download/serverdatasets/columns/authed`、
  `schedule list/tasks/get/exists/executing/history/record/records/log/setting`、`system *`、`entry *`、`user *`。
  导出会真实触发服务端计算，批量导出 / `schedule run|delete` 必须先向用户确认。
  `attach upload` 属**服务端写**（落附件缓存），只在用户明确授权的对象上测，测完必须 `attach remove` 清理。
  `report upload` / `report delete` / `report edit --apply` 直接改**生产模板文件**（影响所有看这张报表的人），
  同样只在用户明确授权的对象上测；验证用**新建临时文件 → 回读比对 → 删除**，绝不拿现有模板做实验。
  **写范围 0.6.0 起默认拒绝**：没设 `FRCLI_WRITE_SCOPE` 就必须 `--any-path` 才写（沉默 ≠ 不限制）。
  2026-09 事故：agent 在没设范围的 shell 里跑 `report edit --apply`，写出了团队目录
  （`demo_group/other_user/legacy_rpt.cpt`），靠 `upload_template` 的自动备份才逐字节还原。
- **不写入任何账号、密码、token、连接信息**到本目录（配置在 `~/.frcli/`，属机器本地状态，不进仓库）。
- **⚠️ 本仓库必须保持"脱敏"状态（可能公开）**：
  · **只写能力，不写环境** —— 不对具体机器、路径、账号、公司、组织、生产报表做说明
    （安装路径写 `<FineReport 安装目录>`、虚拟环境写 `<venv>`、目录写 `demo_group/...` 这类占位符）。
    **环境与个人事实属于知识库（llm-wiki），不属于本仓库。**
  · **打包产物在 `dist/fanruan-v10.skill`**（`dist/` 已被 gitignore，属本地产物）；
    打包前必须过一遍黑名单复扫（人/工号/域名/组织/真实报表名），**工作树与历史都要扫**。
  · 2026-09 教训：曾有一个手工打的 0.4.2 包长期留在 `dist/`（未脱敏、且版本过期），已删除；
    也曾在仓库历史里留下真实标识符（10 个提交），靠重写历史才清掉。
- **新增危险操作**：在 `SKILL.md`「安全约束」标 🔴，并要求执行前向用户确认。
- **不要顺手改无关代码**：只动与本次需求相关的文件。

## 实测坑点速查

### 导出「成功」可能是 HTML 出错页面

`export` 只看 HTTP 状态码；FineReport 出错时返回 **200 + HTML 出错页面**，CLI 照写文件并报 `status: ok`。
判据：xlsx = `PK\x03\x04`、pdf = `%PDF`、png = `\x89PNG`、**word 是 RTF（`{\rtf1`，不是 docx 的 PK）**；
失败形态有**两种**且都不带 title：出错页（含 `出错页面` / `Oops!!!` / `detail-message`）与
**排队页**（`Dec-Waiting_In_Line`，约 2KB，重试一次即成功）。`export` 0.6.0 起内置魔数校验。
出错页的 `detail-message` 属性有单引号/双引号两种写法，解析要都认。
页面 `detail-message`（HTML 实体编码）里有具体错误代码与原始 SQL，解码即可定位坏数据集。

### 出错页 `detail-message` 是通用诊断/挖接口入口（**不限导出**）

任意 `/decision` 接口参数错/方法错/无权限，都是 **200 + HTML 出错页**，`detail-message` 写明原因：
`Required String parameter 'x' is not present`（缺参数名）、`Request method 'GET' not supported`、
`Fine-Dec_No_Privilege_Access_Page`（需管理员）、以及**字段名写错时列出全部合法字段**
（`Unrecognized field "count" (8 known properties: "taskName",...,"perPage","page")` —— `schedule record` 就是这么试通的）。
`detail-message` 为空时只剩 `simple-message = Fine-Dec_Default_Error_Tip` → 多为对象不存在（logId 过期/被清理）。
`client._unwrap_json()` 已把它翻成 `API_ERROR` + 平台原文，新接口一律走它，别再 `resp.json()` 裸解析。

### 写接口的返回值必须校验，不能只看 HTTP 200

`schedule delete` 老实现发 `{"ids":[...]}`（平台要**裸数组** `["<id>"]`）→ 平台回 200 + HTML 出错页
（`Cannot deserialize instance of [Ljava.lang.String; out of START_OBJECT`），而 `return resp.status_code == 200`
照样报 `deleted: true / status: ok`，任务其实还在（2026-09 实测复现）。**规律**：本平台出错一律 200，
所以写操作要么解析 `data == "success"`，要么走 `_unwrap_json()` 让它抛错。

### `schedule create` 必须重置输出 id，否则 detached entity

从 `schedule get` 派生 YAML 建任务时，若沿用源任务的 `scheduleOutput.id` / `outputActionList[].id`，
服务端报 `detached entity passed to persist: com.fr.schedule.base.entity.ScheduleOutputEntity`（200 + HTML 出错页）。
换成新 UUID 即可；`creator` 只在创建时能写入（PUT 改不掉）。

### 自定义类输出的日志节点是异步写的

`自定义类附件处理`（FeishuPushPlus10V2 等）在任务跑完约 5 分钟后才写进日志节点树；
当场只看到 `模板计算/导出cpr/导出pdf` 属正常，别据此判定任务配置没生效。

### `schedule history` 是升序（`-n 1` = 最早一条）

要最新记录用 `schedule record`（倒序）或放大 `-n` 后取最后一条。

### 默认 30s 超时，复杂报表必然超时

同一张报表默认超时 → `导出请求失败: The read operation timed out`；`FRCLI_TIMEOUT=300` → 50s 成功导出 225KB xlsx。
超时由环境变量 `FRCLI_TIMEOUT` 控制（`client.py` 读取）。

### 报表路径约定

`demo_group/demo_user/dept_a/dept_b/sales_daily.cpt` —— 相对路径、带 `.cpt`、无前导 `/`、不用 `//doc//`。
路径取自 `report list <目录>` 的 `path` 字段。

### 参数只传驱动参数

模板 `${edate}` 等派生参数由服务端推导，只传驱动参数 + `extype=simple` 即可（`extype=simple` 可绕开部分模板分页报错）。

### schedule 的参数语义

`get/run/update` 收任务**名**，`delete` 收 UUID **id**（先 `schedule get` 拿）；`get` 内部是模糊搜索取第一条。

### `report datasets` 读不到定义 = 该报表数据集本身报错

`report datasets/info/download` 走 `format=cpt` 取模板定义，服务端会校验数据集。数据集配置错误时返回 0 条 / `无法读取报表定义` —— 不是 CLI 故障，而是这张报表当前就是坏的（导出也必然拿到出错页面）。

### 改模板内容 = 远程设计通道（0.5.0 起已实现；REST 确实没通道，但别再只盯着 REST）

- **REST 侧确实没有写模板内容的接口**：`TemplateBean` / `FileBean` 只有元数据字段（id/pId/text/path/description/showType/parameters…），
  `ReportEntryService.addTemplates()` 只写条目记录，569 条路由里没有任何接口接收 .cpt 字节。
- 两棵树要分清：**报表目录树**（`/v10/templates/all`，id = 文件路径）vs **平台条目树**（`/v10/entries`，id = UUID）。
  目录管理类写接口（`PUT /v10/template/{id}`、`POST /v10/{directoryId}/templates`、`PUT /v10/file/{id}`、
  `POST /v10/{pId}/directory`、`PUT /v10/entry(s)`、`POST /v10/dataset/upload`、`POST /v10/data/transference/import`）
  对普通分析账号一律 `Fine-Dec_No_Privilege_Access_Page`；路径型 id 还额外 400/405（无法作为单段路径参数路由）。
- **可用的写法是 Designer 的「远程设计」通道**：`/decision/remote/design/{check,verify,channel,service}`。
  `/channel` 是通用反射 RPC 网关（给类名+方法名+参数类型即执行），`WorkResource` 就是服务端 `WEB-INF` 远程文件系统，
  足以读写 .cpt。载荷 = `gzip(Java 对象流)`，**只有密码字段加密**（AES/SM4，`/check` 返回参数），RPC 载荷不加密。
  Python 复刻在 `src/frcli/{jser,rdcrypto,remotedesign}.py`，与帆软原件逐字节一致（`tests/test_remotedesign.py`）。
- **权限**：路径含 `reportlets` 时查账号的远程设计授权目录，不含则不校验；**无权限时 `write` 静默不写也不报错** →
  写后必须回读校验（`report upload` 已内置 SHA256 比对）。覆盖前 `readAndLockFile` 占锁，被他人占用则拒绝写。
- 附件（`POST /v10/attach/upload`）仍只是附件缓存，**没有任何接口把 attachId 绑成模板**，与改模板无关。

### `format=cpt` 不是模板文件字节（拿它回传会毁模板）

`GET /decision/view/report?reportlet=X&format=cpt` 返回的是**另一种序列化**：根元素 `<TableDataMap>`，
缺 `<WorkBook>`/`<StyleList>`；同一模板实测 通道 4510B vs format=cpt 6362B，SHA256 不同。
`report download` 0.5.1 起改走远程设计通道（与 upload 同源）；`report upload` 默认断言前 600 字节
含 `<WorkBook>`，否则拒绝（`--allow-format` 才放行）。数据集定义用 `report datasets`。
反面教材：照旧文档做 `download → 改 → upload --force`，会把 stub 写回生产模板，且回读校验通过（假阳性）。

### 改 XML 做实验：**替换/注入必须断言成功**，否则得到假结论

做"改一个字段看效果"的对照实验时，`str.replace` / 正则**不匹配就静默什么都不做**，
于是你比较的是两份**完全相同**的文件，却会得出"这个字段没用"的结论。本项目真实发生过两次：
① 删配方空操作时正则删多了建表行；② 注入 `<HR F="T"/>` 时正则没匹配上（`<HR/>` 与 `<HR />` 空白不同），
得到"6 页、第 2 页无表头"，差点推翻一个**已经验对**的结论。

**规矩**：用 `re.subn` 并断言 `n == 1`；改完**从服务端回读**确认目标串在；
对照实验要**先证明两份输入真的不同**（比 SHA256 或比关键片段），再比输出。

同类：**"没生效"要先排除自己的表达式/阈值写错**（我们踩过：标红阈值 `v>0.2` 高于数据最大值；
标题用 `${sdate}` 而非 `$sdate`；SQL 缺 `from`；列名写错）。

### 写命令的"无改动"必须幂等（别用 exit 1 表达"什么都没改"）

写命令（`report cell/dataset/table/...`）在目标已是请求状态时，返回 `status: ok` + `changed: false`
+ `note`，**不报错也不发写请求**。2026-09 由独立验证者发现：原先抛 `ApiError` 会 exit 1，
而配方集 §1 里恰好有两步是这种空操作 → **任何 `set -e` 的复现脚本都会在中途断掉**，
且文档声称"逐条真跑过"与实际不符。判据：确认改没改看 `changed` 字段。

配套：`--num-format/--bold/--bg` 这类"造样式"的选项先**复用等价样式**（归一化 XML 比对），
否则反复跑会让 `<StyleList>` 无限膨胀（修复前实测 5→6→7→8），幂等性也无从谈起。

### 模板锁：设计器开着文件是最常见原因；强杀客户端会留**解不开**的锁

写入是"占锁 → 写 → 释放"（`TplOperator.readAndLockFile` / `closeAndFreeFile`）。被锁住时：

- **最常见：有人在设计器里开着该模板**（2026-09 实测确认，用户自己开着）→ 关掉即释放。
- **本工具无法跨会话解锁**：实测从另一会话调 `closeAndFreeFile` / `userOut` / `userIn`
  都返回 `true` 而锁**仍在** —— 这类"成功"返回值会把人带沟里（那个会话里 `fileLocked` 报 false 却写不进去）。
- **强杀客户端（SIGKILL）留下的锁，同账号新会话当场解不开，但会自己超时释放**
  （本项目实验：`p.kill()` 掉的进程，锁持续约半小时后自动消失；走 SIGTERM 的对照组**当场**就释放了）。
  ⇒ 已实现：会话登记 `_locked` 集合 + `release_locks()` + `install_lock_guard()`
  （`atexit` + SIGINT/SIGTERM），CLI 入口自动挂上。
- **策略**：普通竞争自动重试 3 次（~5s）；`FRCLI_WAIT_LOCK=<秒>` 加长轮询等待；
  被锁时先把结果传到新文件名（`xxxV2.cpt`）绕过，别干等。

### 版本提示噪音 / PATH 里的 frcli 该指向谁（2026-09 两个会话）

- **`~/.local/bin/frcli`（或任何 PATH 里的 `frcli`）要指向 `references/frcli`，不要指向 `references/run.py`** ——
  run.py 会 `shutil.which("frcli")` 再调回来；PATH 首位若是它自己，就是递归（见下条）。
- **版本提示按版本号比对，不按路径**：同机常有多份 skill 副本（项目仓库 + `~/.agents/skills` 安装态），
  路径必然不同而版本相同。早期按路径比对 ⇒ **每条命令都往 stderr 打两行**，
  实测把一个会话的几十条命令输出全污染了。现在只有**版本真的不同**才提示。
- 本机 `~/.local/bin/frcli` 曾经就是指向 run.py 的 87 字节 shim（递归风暴的地雷），已改指 `references/frcli`。

### 启动器三坑：无限自我复制 / 改 cwd / 报 JSONDecodeError 原文（2026-09 学自另一会话）

| 坑 | 症状 | 处置 |
|---|---|---|
| **`run.py` 与 PATH 里的 `frcli` 互相调用** | 若 PATH 的 `frcli` 是指向 `run.py` 的 shim，就 `run.py → which(frcli) → shim → run.py → …` **无限自我复制**（实测 1600+ 进程、`fork: Resource temporarily unavailable`，只能反复 `pkill -9`） | `run.py` 已加护栏：环境标记 `FRCLI_RUNPY_DEPTH` + 解析软链自指检测 + 深度上限；命中就跳过"方式 1"改用内置源码 |
| **启动器改 cwd 到 skill 源码目录** | `references/frcli` 与 `run.py` 原传 `cwd=str(SRC_DIR)` ⇒ 用户的**相对路径参数**全部落错地方：实测从 `/tmp` 跑 `export -o relout.xlsx`，文件写进了 `<skill>/src/`（静默）；`report upload x.cpt` 则报 `File does not exist` | 两处 `cwd` 已删除（`-m frcli` 靠 PYTHONPATH 即可解析） |
| **平台出错页冒充 JSON** | 平台对"任务配置缺字段"等回 200 + HTML，而 `create_schedule` 裸 `resp.json()` ⇒ 抛 `Expecting value: line 1 column 1 (char 0)` + `code=UNKNOWN`，看不出真正原因 | `_unwrap_json` 已加固（content-type 声明 JSON 也兜住 `ValueError` 并按出错页解析）；`create_schedule` 改走 `_unwrap_json` |

### 条件属性：`bold` 会把字号写成 0（整行看不见），`--rule` 是替换不是追加

**另一个会话（2026-09）用本 skill 时踩到，都是我们工具的坑，已修**：

1. **`bold` 不带 `size` → 字号 0**。`FRFontHighlightAction` 写的是**整个 FRFont**，
   缺 `size` 时服务端按 **0 号字** 处理：值还在 xlsx 里、**整行不可见**。
   实测 `--rule 'v>0:bold'` → 导出 `font.size = 0.0`。
   → 已修：无显式 `size` 时**继承目标格样式字号**，取不到退 9 磅。
   **验收判据**：条件属性不能只看值，必须同时读 `font.size`（或出图看）。
2. **`--rule` 是"设置"不是"追加"**：第二次调用会**整表替换**该格原有规则（静默）。
   真实事故：先设「隔行底色 + 负数标红」，最后一版只写「合计行加粗」，两条被无声冲掉、导出照样 ok。
   → 已修：替换旧规则时给出 warning（含条数）。要保留就写进**同一次调用的多个 `--rule`**。
3. **数据行样式作用到所有展开行**：给模板行套加粗 = 每行都加粗 ⇒ **加粗只能用条件属性**。
4. **`report style --add --size-pt 12` 曾被拒**（校验把 size 排除在"至少给一项"外）⇒ 建不出只改字号的样式。已修。

### 缺 `<RG>` 的单元格 = 服务端按「分组」处理（会静默去重，合计对不上）

**早期误判（已撤回）**：最初记成"xlsx 合计 = 某一行值（错）而 csv 对"，还记过"同一模板不同时段导出
`4567.7 → 2345.6 → 4567.7`"。**两件都是读法错误** —— 合计行渲染在数据之后的第 6 行，而当时按**模板坐标**读了
第 4 行（那是第 2 条明细）。实测 26 个变体 × 3 轮：**xlsx 与 csv 逐格全等，从无分歧**，与导出格式无关。

**真因（2026-09 实测闭环，不是平台 bug）**：`DSColumn.getGrouper()` 在 `<RG>` 缺失时惰性返回
`new FunctionGrouper()`（`divideMode` 初值 0 = 分组）⇒ **单元格被当作「分组」**，相同值合并、数值列被去重。
对照实验（同数据集 `('A',10)('A',10)('A',20)('B',10)('B',30)('B',30)`，只改 `<RG>`）：

| 形态 | 结果 |
|---|---|
| 无 `<RG>` | `A/10, ''/20, B/10, ''/30`（4 行） |
| `<RG class="…FunctionGrouper"/>`（分组，缺省） | **与"无 `<RG>`" 逐格相同** ← 根因的直接证据 |
| `<RG class="…FunctionGrouper"><Attr divideMode="1"/></RG>`（列表） | 6 行全展开 |
| `<RG class="…SummaryGrouper"><FN>…SumFunction</FN></RG>`（汇总） | `A/40, B/70`（按组聚合） |

**真正的问题形态是"静默算错"，不是"时对时错"**：缺 `<RG>` 时合计 = **70**，而 SQL 真值 = **110**
（`10+10+20+10+30+30`）——因为分组去重把 `A` 的 `10,10` 与 `B` 的 `30,30` 塌缩了。**3/3 轮稳定复现**。

**规矩**：写 .cpt 时 `<RG>` **必须显式写**（`report table` 默认已改为 `--mode list`）；
凡是有默认值的字段，默认值未必是你要的那个 —— **"标签在不在"不等于"设置有没有"**。
完整模型见 `docs/探索/cpt服务端模型-逆向.md`。

### 导出产物逐格 diff 有浮点抖动（别期望全等）

同一张模板、同样参数，**前后两次导出**用 openpyxl 逐格比对，会有上百个数字格"不同"——
但最大相对误差只有 **4.5e-12**（服务端聚合/舍入的抖动），没有一处超过 1e-6。
所以「改了一格，验证只有那一格变了」**不能直接全等比较**，否则被假阳性淹没。正确判据：

1. 按单元格类型分离（字符串格 / 数字格）
2. 字符串格可以全等比；数字格给容差（1e-9 足够）
3. 版面用 `dims` + 非空格数比，不要比逐格样式对象

这条是 `format=cpt` 字节不稳定（下面那条）在**导出值**上的版本，来源见 `docs/验证/cpt创作验证报告.md`。

### `format=cpt` 响应字节不稳定（别用整体 hash 判断模板是否被改）

同一模板连续两次取定义，SHA256 就不同；逐行 diff 只差 1 行容器对象 identity hash：

```
<![CDATA[org.apache.catalina.core.ApplicationMappingImpl@72d48284]]></O>
<![CDATA[org.apache.catalina.core.ApplicationMappingImpl@268f721c]]></O>
```

长度相同 → 文件大小看着没变，最容易误判"模板被改了"。
**判据**：比 `<TableData name>` / `<Query>` / `<DatabaseName>` 的结构化哈希，不要比整文件 SHA256。

### `report list /` 返回全量

`directory="/"` 时不做过滤，返回整个服务器文件树（实测 3870 条）；`report list <目录>` 结果里含该目录自身一条。

### token 缓存与认证失效（**不等于 401**）

`~/.frcli/tokens/<实例>.json`，24h TTL。本服务器失效 token 的真实表现是 **302 重定向到 CAS 登录页**（`https://sso.example.com/cas/login?...`），不是 401 —— 只判 401/403 会漏，`_is_auth_failure()` 必须同时认 CAS 重定向。

**缓存未过期也会失效**：实测 `expires_at` 还在未来，`report list` / `schedule list` 全返回 `[]`，换新 token 立刻正常。旧版 `server test` 只调 `_ensure_auth()`（不真发请求），这种状态下照样报 ok（假阳性）。0.1.1 起：`_request` 撞上认证失效自动清缓存重登一次；`test_connection()` 真发一次请求并回报 `relogin`；列表命令不再 `except Exception: return []`（认证/连接错误照常抛出）。

### `schedule history` 是精确匹配

`history [任务名]` 按 taskName 精确匹配，任务近几天无日志即静默 `[]`（要全局日志就不传名字）；`[]` 不等于 CLI 故障。

### SSL

`client.py` 固定 `CERT_NONE` + `check_hostname=False` + legacy renegotiation，自签证书可直接用；`FRCLI_CA_CERT` 只做 `load_verify_locations`，在当前 `verify_mode` 下不改变校验行为。

## 交付自检清单

| 类别 | 检查项 |
|------|--------|
| 结构 | `SKILL.md` frontmatter 完整（name/version/description/metadata.requires.bins）；**`name` 必须是 `fanruan-v10`**（匹配 `^[a-z0-9]+(-[a-z0-9]+)*$`，否则宿主静默不加载） |
| 自举 | `python references/run.py --version` 与 `cd src && python -m frcli --version` 均可用 |
| 一致性 | 三处版本号一致（`__init__.py` / `pyproject.toml` / `SKILL.md`） |
| 软链 | `ls -l CLAUDE.md CODEBUDDY.md` 显示 `-> AGENTS.md`，且 AGENTS.md 不是软链 |
| 测试 | `python -m pytest tests/` 无新增失败；至少 1 条只读命令真实跑通。**历史遗留**：`test_config.py` 的 `test_load_empty_config` / `test_list_instances_empty` 在固定失败 —— 它们只 patch 了 `config.DEFAULT_CONFIG_PATH`，而 `load_full_config()` 走 `CONFIG_SEARCH_PATHS` 会落回真实 `~/.frcli/config.yaml`（实测环境有 `yh` 实例），与本次搬迁无关 |
| 文档 | 命令增删改已同步 `SKILL.md` + `README.md`；坑点有实测依据 |
| 安全 | 无账号/密码/token 入库；危险操作在 SKILL.md 标 🔴 |
