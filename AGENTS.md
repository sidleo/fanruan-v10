# 项目协作规范

本文件适用于本目录及子目录。项目用途、安装和使用入口见 [README.md](README.md)，Agent 操作契约见 [SKILL.md](SKILL.md)。

## 修改边界

- CLI 唯一源码是 `src/frcli/`；skill 与 CLI 同源，直接修改这里，无需维护或同步源码副本。只修改本次需求涉及的文件。
- 新增能力沿现有入口实现：HTTP 接口放 `client.py`，远程设计通道放 `remotedesign.py`，模板修改放 `reportops.py` / `cptxml.py`，本地示例分析放 `local_cpt.py`，命令放 `commands/` 并在 `cli.py` 注册。
- 每个动作提供固定命令和明确参数，让使用者按命令操作；除 `--params` 报表参数外，不要求 Agent 拼 URL 或构造 JSON 请求体。输出沿用 `output.py`，异常沿用 `exceptions.py`。
- 命令增删或参数语义变化时同步 `SKILL.md` 和 README；新增危险操作必须在 `SKILL.md`「安全约束」标 🔴，写清执行前确认要求。通用坑点归入 `SKILL.md` §6 或对应专题文档，此处只保留行动规则和阅读入口。
- 发布版本时保持 `src/frcli/__init__.py` 的 `__version__`、`pyproject.toml` 的 `version`、`SKILL.md` 的 `metadata.version` 一致。skill frontmatter 的 `name` 必须是 `fanruan-v10`，符合 `^[a-z0-9]+(-[a-z0-9]+)*$`；目录名仍为 `fanruan_v10`。
- `AGENTS.md` 保持实际文件，现有 `CLAUDE.md`、`CODEBUDDY.md` 保持相对软链接指向它。

## 操作与信息边界

- 日常验证使用只读命令：`server list/test`、报表查询与下载、`inspect status`、调度查询、`system` / `entry` / `user` 查询。`export`、`report image`、`report preview`、`inspect run` 会触发服务端计算；批量导出必须先说明规模并取得用户确认。
- 生产调度的 `create/update/delete/run/pause/resume` 必须先确认影响群、时间和范围，并用 `schedule get` 备份；改后核对 `creator`、调度表达式、输出类、模板路径和启停状态。`run` 会真实执行并可能推送下游。
- `report upload/delete`、所有模板修改的 `--apply`、`rpc` 写调用只可作用于用户明确授权的目标。覆盖或删除已有模板前先 `report download` 备份并说明影响；实验使用新建临时模板，按「创建 → 回读比对 → 删除」完成清理，不拿现有模板试写。
- 模板写范围统一使用 `remotedesign.assert_in_write_scope`，在任何网络请求前检查。未设 `FRCLI_WRITE_SCOPE` 默认拒绝；`--any-path` 是用户对本次目标的显式放行，不能代替授权。路径归一化后同时拦截 `..` 穿越和兄弟目录越界。
- 保持写前占锁、覆盖备份、写后回读校验。遇 `TplLockedException` 先确认设计器是否开着目标模板，正常关闭并释放；不硬抢锁或用强杀客户端解决锁冲突。`rpc` 保持只读白名单、写方法确认及路径检查、`deny` 方法拒绝执行。
- `attach upload` 属服务端写，只在明确授权对象上测试，用完必须 `attach remove`。附件缓存与模板目录是不同资源，不能用附件上传代替模板上传。
- 仓库按可公开内容维护：账号、密码、token、真实连接信息、机器路径、组织与生产资产标识均不得写入。示例使用 `demo_group/...`、`demo_conn`、`reports.example.com` 等占位值；真实配置与 token 留在 `~/.frcli/`。
- 写文档或记录新发现前按 [内容落点判定](docs/内容落点判定.md) 归类：能力契约进仓库，环境与业务事实进 llm-wiki，自动化任务绑定、实例配置和黑名单留在机器本地。涉及实际环境或资产时，先查知识库对应条目与 Pitfall。

## 开发与验证

命令均在项目根目录、已具备依赖的 Python 3.10+ 环境执行；安装步骤见 [README.md](README.md)。测试放 `tests/test_*.py`，使用 pytest；建议保持现有代码风格：四空格缩进、`snake_case` 函数与变量、中文命令帮助。

```bash
# 直接检查当前源码，避免 PATH 中其他安装副本干扰
PYTHONPATH=src python -m frcli --version
PYTHONPATH=src python -m frcli --help
PYTHONPATH=src python -m frcli report --help

# Python 行为变更完成针对性回归后，执行现有完整测试
PYTHONPATH=src python -m pytest tests/ -q

git diff --check
```

- 改命令时检查对应命令组和子命令的 `--help`。代码修复须验证失败边界与预期行为；测试隔离本机配置、token 和网络，使用临时路径或模拟客户端。
- Python 行为变更交付前测试须为 `0 failed`，说明跳过项。涉及平台接口的变更或发布，还需至少一条获准的只读命令实测；需要真实写操作时遵循上面的授权与临时对象规则。
- 纯文档修改按源码核对命令、配置、相对链接和代码围栏，并执行空白检查；不为验证文档擅自安装依赖、连接生产、运行导出、发布或修改机器状态。
- XML 对照实验先证明替换确实发生：使用 `re.subn` 等检查命中次数，断言目标片段及输入差异，写后从服务端回读，再比较产物。

## 修改相关模块前保持这些契约

| 修改内容 | 必须保留的行为 |
| --- | --- |
| 认证与请求 | 保留登录 cookies，使用 `follow_redirects=False`；同时识别 401/403 与 CAS 重定向。登录/刷新保留实例级文件锁、锁内缓存复查和原子落盘；认证或连接失败不能吞成空列表。 |
| 平台响应 | 新接口统一走 `_unwrap_json()` 解析平台错误；HTTP 200 也可能是 HTML 出错页。写接口须校验平台返回值或回读，`schedule delete` 发送裸数组。接口路径以源码和已有路由文档为依据。 |
| 传输错误 | REST 与登录复用 `neterr.py`；远程设计提示使用 `FRCLI_RD_TIMEOUT`。只对幂等 GET/HEAD 的连接断开有界重试一次；超时、代理故障及登录 POST 不自动重试，不自动绕过用户代理。代理 5xx 按 `Proxy-Status` 判定。 |
| 导出 | 保留文件魔数、HTML 出错页和排队页校验。HTML 判定先识别文档开头，避免误杀含错误字样的合法 CSV；识别 `id/class="detail-message"`，提取原因时支持长出错页。Word 实际是 RTF。批量结果保留展开任务数、参数、输出路径、失败明细及路径冲突提示。 |
| 模板字节 | 用远程设计通道取得可回传的 `<WorkBook>` 原始字节；`format=cpt` 是数据集定义提取物，不能拿它覆盖模板。结构化比较定义，避免用其整体 hash 判断模板是否变化。 |
| 模板修改 | 默认 dry-run，`--apply` 才写；相同请求返回 `status: ok`、`changed: false` 且不发写请求。复用等价样式；显式写数据设置 `<RG>`，核对目标 sheet、列名、扩展父格与条件属性。聚合报表按 `Block` 区分坐标，普通网格命令明确拒绝不支持的聚合块。 |
| 调度 | `get` 的模糊匹配不能用于变更：写命令要求精确名。保留 PUT 时的 `creator` 和原暂停态；拒绝自动修改非 0/1 状态。创建时清理只读字段、归一 `taskState` 并重置输出 UUID；更新模板先校验路径存在。 |
| 启动器 | 保留递归护栏与调用者 cwd；PATH 包装指向 `references/frcli`。同版本不同路径不重复提示版本差异。临时脚本避免 `inspect.py` 等会遮蔽标准库的名称。 |

## 按任务读取专题

仅在处理对应任务前读取所需材料：

| 任务 | 先读 |
| --- | --- |
| 安装、自举、PATH 与跨平台启动 | [安装手册](references/install.md)；启动器实现见 `references/run.py`、`references/frcli`。 |
| 接口扩展、远程设计与 RPC | [REST 路由清单](docs/探索/REST路由清单.md)、[远程设计协议](references/remotedesign.md)、[RPC 服务清单](references/remote-services.md)；模板数据集预览另读 `SKILL.md` §6.25 与 `dataset_preview.py`。 |
| 模板创作与 XML 调整 | [创作手册](references/cpt-authoring.md)、[XML 速查](references/cpt-xml.md)、[配方一](references/cpt-patterns.md)、[配方二与验收通道](references/cpt-patterns2.md)。条件属性、数据设置、分页规则查 `SKILL.md` §6.14–6.19；结构校验不能代替渲染与导出验收。 |
| 本地示例与聚合报表 | [本地示例检查](references/cpt-local-examples.md)、[从示例提炼设计](references/cpt-design-from-examples.md)。 |
| 数值对账或性能排查 | `SKILL.md` §6.22–6.28 与 [验证报告](docs/验证/cpt创作验证报告.md)：先对齐 sheet/区域/参数/文件版本，比率检查加权平均，数字比较设容差；性能先分取数与渲染，测试前关缓存。巡检 SQL 截断不能证明线上 SQL 未更新。 |
| 调度创建、换模板或日志排查 | `SKILL.md` §6.6、§6.11、§6.12、§6.26：`history` 升序，`log` 使用其返回的 id；执行记录 UUID 不能作 logId，自定义类日志可能延迟写入。 |
| 会话巡检 | 先读 `tools/scan_sessions.py`；`python tools/scan_sessions.py` 默认扫昨天，支持 `--date` / `--days`，读取 DSH 会话需 `zstd`。先复核证据与验证结论，再改代码；台账写入 [巡检日志](docs/巡检日志.md)，仅记录脱敏计数、结论、版本与提交号。 |
| 打包或发布 | 先读 [发布与脱敏流程](docs/发布与脱敏.md)，按下面的门禁执行。 |

## 发布与交付

- 打包前扫工作树、现有包内文本和 Git 历史；黑名单使用仓库外文件或 `FRCLI_REDACT_BLACKLIST`，缺失时拒绝打包。压缩包须解包检查，历史也要覆盖其中的压缩内容；黑名单零命中仍需人工确认新出现的真实标识。
- 在项目根目录执行 `tools/build_skill.sh --check` → `tools/build_skill.sh` → `tools/build_skill.sh --check`；最后一次检查必须覆盖新生成的包。产物为 `dist/fanruan-v10.skill`，该文件由 `.gitignore` 特例放行，是可跟踪交付物，其余构建产物不入库。
- 发布前核对三处版本、skill frontmatter、源码与自举入口、完整测试、只读实测、文档、软链接及脱敏结果；按内容落点约定核对知识库中的版本提示。
- 提交说明建议沿用现有「版本号：变更摘要」或清楚的中文摘要，不强制推断 Conventional Commits。交付说明列明修改内容、实际执行的验证、跳过项和剩余限制；未执行的检查不能写成通过。
