# fanruan_v10 —— Skill + frcli CLI 开发规范

> 本文件通过 AGENTS.md 叠加机制在本目录及子目录生效。
> 本目录**既是 `fanruan_v10` skill 的分发体，也是 `frcli` CLI 的产品源码仓库**（同源同仓，结构仿 `yh-bigdata`）。

## 项目定位

`fanruan_v10` skill 封装 `frcli` —— 与 FineReport V10 决策平台交互的 CLI（server / report / export / schedule 4 个命令组）。
目标是让 agent 不构造 JSON、不猜接口路径，只调固定命令。

- CLI 源码（唯一来源）：`src/frcli/`；skill 入口：`SKILL.md`；打包：`pyproject.toml`（src 布局）
- **不存在源码副本**，改 `src/frcli/` 即同时改了 CLI 与 skill，无需任何同步步骤（旧的两份副本布局已废弃）

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
│   └── commands/         # server / report / export / schedule 命令组
├── references/
│   ├── install.md        # 自检 + 自举手册
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
| 模板文件树 | `/decision/v10/templates/all` | GET |
| 数据集定义 / 模板下载 | `/decision/view/report?reportlet=<path>&format=cpt` | GET |
| 报表导出 | `/decision/view/report?reportlet=<path>&format=pdf\|excel\|word\|image\|csv` | GET |
| 定时任务列表 | `/decision/v10/schedule/task/names` | GET |
| 定时任务搜索 | `/decision/v10/schedule/task/search` | POST `{taskName}` |
| 创建 / 更新任务 | `/decision/v10/schedule/task` | POST / PUT（PUT 体必须含 `id`） |
| 删除任务 | `/decision/v10/schedule/task/deletes` | POST `{ids: [...]}` |
| 立即执行 | `/decision/v10/schedule/task/{id}/once` | POST |
| 执行历史 | `/decision/v10/schedule/task/log/info` | POST |

不可用：`report upload` / `report delete`（服务器不支持 Web API 改模板）；`dataset preview`（需管理员权限）。

## 开发黄金流程

| 步骤 | 动作 |
|------|------|
| 改 | 编辑 `src/frcli/`（client.py 加方法 → commands/ 加子命令 → 更新 `SKILL.md`） |
| 装 | `pip install -e .`（本目录，editable，改完即生效） |
| 测 | `frcli --help` → 命令组 `--help` → 单条**只读**命令实测；`python -m pytest tests/` |
| 记 | 命令增删改同步 `SKILL.md` + `README.md`；新坑点写进 SKILL.md §6 与本文「实测坑点」 |

版本号三处保持一致：`src/frcli/__init__.py` 的 `__version__`、`pyproject.toml` 的 `version`、`SKILL.md` front-matter 的 `version`。

## 行为约束

- **测试只用只读命令**：`server list/test`、`report list/info/datasets/download`、`schedule list/get/history`。
  导出会真实触发服务端计算，批量导出 / `schedule run|delete` 必须先向用户确认。
- **不写入任何账号、密码、token、连接信息**到本目录（配置在 `~/.frcli/`，属机器本地状态，不进仓库）。
- **新增危险操作**：在 `SKILL.md`「安全约束」标 🔴，并要求执行前向用户确认。
- **不要顺手改无关代码**：只动与本次需求相关的文件。

## 实测坑点速查

### 导出「成功」可能是 HTML 出错页面

`export` 只看 HTTP 状态码；FineReport 出错时返回 **200 + HTML 出错页面**，CLI 照写文件并报 `status: ok`。
判据：xlsx/docx = `PK\x03\x04`、pdf = `%PDF`、png = `\x89PNG`；失败文件含 `<title>出错页面</title>` / `Oops!!!`。
页面 `detail-message`（HTML 实体编码）里有具体错误代码与原始 SQL，解码即可定位坏数据集。

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

### `report list /` 返回全量

`directory="/"` 时不做过滤，返回整个服务器文件树（实测 3870 条）；`report list <目录>` 结果里含该目录自身一条。

### token 缓存

`~/.frcli/tokens/<实例>.json`，24h TTL，401/403 自动失效重登；列表命令返回 `[]` 先清缓存。

### SSL

`client.py` 固定 `CERT_NONE` + `check_hostname=False` + legacy renegotiation，自签证书可直接用；`FRCLI_CA_CERT` 只做 `load_verify_locations`，在当前 `verify_mode` 下不改变校验行为。

## 交付自检清单

| 类别 | 检查项 |
|------|--------|
| 结构 | `SKILL.md` frontmatter 完整（name/version/description/metadata.requires.bins） |
| 自举 | `python references/run.py --version` 与 `cd src && python -m frcli --version` 均可用 |
| 一致性 | 三处版本号一致（`__init__.py` / `pyproject.toml` / `SKILL.md`） |
| 软链 | `ls -l CLAUDE.md CODEBUDDY.md` 显示 `-> AGENTS.md`，且 AGENTS.md 不是软链 |
| 测试 | `python -m pytest tests/` 无新增失败；至少 1 条只读命令真实跑通。**历史遗留**：`test_config.py` 的 `test_load_empty_config` / `test_list_instances_empty` 在实测环境固定失败 —— 它们只 patch 了 `config.DEFAULT_CONFIG_PATH`，而 `load_full_config()` 走 `CONFIG_SEARCH_PATHS` 会落回真实 `~/.frcli/config.yaml`（实测环境有 `yh` 实例），与本次搬迁无关 |
| 文档 | 命令增删改已同步 `SKILL.md` + `README.md`；坑点有实测依据 |
| 安全 | 无账号/密码/token 入库；危险操作在 SKILL.md 标 🔴 |
