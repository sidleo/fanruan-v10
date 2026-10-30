# fanruan_v10

`fanruan_v10` 提供与 FineReport V10 决策平台交互的命令行工具 **`frcli`**，以及供 Agent 使用的 **`fanruan-v10` skill**。它把报表查找、参数与 SQL 读取、导出、模板创作、运行时巡检和调度管理封装成命令，输出 JSON、表格或本地文件。

CLI 与 skill 同源：`src/frcli/` 是唯一源码，[SKILL.md](SKILL.md) 是 skill 入口。目录名保留 `fanruan_v10`，skill 名使用 `fanruan-v10`；协作与修改要求见 [AGENTS.md](AGENTS.md)。

## 能力与命令入口

当前源码注册了 10 个命令组。下表列出主要入口，完整参数以 `frcli <命令组> --help` 和子命令 `--help` 为准。

| 命令组 | 主要用途与入口 |
| --- | --- |
| `server` | 本地多实例配置：`list`、`add`、`remove`、`set-default`、`test`。 |
| `report` | 查询模板、参数、数据集和 SQL；`functions/formula-check` 离线函数检索与检查；`preview` 数据集预览、`download` 原始模板、`upload/delete`、工作表与单元格编辑、表格/交叉表/图表/控件创作；`local-*` 离线示例分析。 |
| `export` | 导出 `pdf`、`excel`、`word`、`image`、`csv`，或按清单 `batch` 导出。 |
| `attach` | `upload/remove` 管理服务器附件缓存。 |
| `system` | 查询 `version`、`health`、`modules`、`authority`、`login-policy`。 |
| `inspect` | `status` 查询性能分析插件，`run` 计算模板并取得环节与单元格耗时。 |
| `entry` | 查询平台条目与消息：`list`、`roots`、`all`、`messages`。 |
| `user` | 查询当前用户、用户列表、部门和岗位。 |
| `schedule` | 任务清单、配置、执行记录与日志，以及创建、更新、暂停、恢复、执行和删除。 |
| `rpc` | 高级远程设计入口：`services`、`methods`、受只读白名单与写范围控制的 `call`。 |

服务端命令需要实例配置和对应权限；模板下载、编辑与数据集预览使用远程设计通道，另需远程设计权限。`report local-examples/local-profile/local-inspect` 和 `rpc services --local`、`rpc methods` 可离线运行。

## 安装与首次运行

需要 **Python 3.10+**。运行依赖由 [pyproject.toml](pyproject.toml) 声明：`click>=8.0`、`httpx>=0.25`、`pyyaml>=6.0`、`rich>=13.0`。

以下命令从项目根目录执行，示例采用 macOS/Linux shell：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
frcli --version
frcli --help
```

`--version` 应显示当前源码版本，`--help` 应列出上表命令组，均不需要连接服务器。Windows 可用 `.venv\Scripts\Activate.ps1` 激活环境。

已有运行依赖时，也可不安装本项目，直接运行仓库源码：

```bash
PYTHONPATH=src python -m frcli --version
PYTHONPATH=src python -m frcli --help
```

跨平台启动入口是 `python references/run.py <命令>`；Unix 便捷入口是 `references/run.sh <命令>`。启动器会寻找可用解释器，并可尝试创建或修复用户 PATH 中的命令软链。安装、自举与启动排查见 [安装手册](references/install.md)。

## 配置实例并读取报表

下面的服务器、账号、模板、数据集和日期参数均为示意，按目标实例替换。连接前需已有可用账号与访问权限。

```bash
# 在项目根目录、激活的 Python 环境中执行；配置保存在本机
frcli server add demo --url https://reports.example.com \
    -u demo_user -p '<密码>' --workspace /webroot --set-default
frcli server test demo

# 使用具体目录查找模板，再采用返回的 path
frcli -i demo report list "demo_group/demo_user" -f table

# 模板路径为相对路径，带 .cpt，不加前导 / 或 //doc//
sample_report="demo_group/demo_user/sales_daily.cpt"
FRCLI_TIMEOUT=300 frcli -i demo report paras "$sample_report"
FRCLI_TIMEOUT=300 frcli -i demo report datasets "$sample_report" --sql -f table
FRCLI_TIMEOUT=300 frcli -i demo report preview "$sample_report" \
    --dataset ds1 --params '{"edate":"20260131"}' --rows 20 -f table
```

`server test` 会真实请求平台并返回认证结果。`paras` 用来确认驱动参数与派生参数，`datasets --sql` 读取完整 SQL，`preview` 会执行数据集查询。仅传模板需要的驱动参数，其他参数由模板推导。

配置密码以明文保存在本机，调用时通过 `-p` 明确提供；不要将真实凭据写入仓库。报表列表按权限过滤，优先查询具体目录；`report list /` 会拉取全树。`report authed` 读取模板认证配置，用于枚举可见模板的入口是 `report list`。

## 离线检索与学习 CPT 示例

本地示例目录由使用者提供，无需实例配置：

```bash
frcli report local-examples "<reportlets目录>" --keyword 分栏
frcli report local-examples "<reportlets目录>" --contains PolyWorkSheet
frcli report local-profile "<reportlets目录>" --tag crosstab -n 10
frcli report local-inspect "<reportlets目录>/demo.cpt" --design --cells
frcli report local-inspect "<reportlets目录>/demo.cpt" --block 2 --cells
frcli report local-inspect "<reportlets目录>/demo.cpt" --sql          # 数据集 SQL/连接名（离线）
```

`local-profile` 汇总原型、技术、图表类型和代表样例，`local-inspect --design` 提供版面与交互画像，`--cells` 显示具体格号，`--sql` 离线解析数据集 SQL 与连接名（大模板比线上 `report datasets` 快）。聚合报表 `PolyWorkSheet` 的各个块拥有独立坐标；普通网格编辑不能直接用于这些聚合块。

结构分析需要结合实际渲染和导出验收。操作细节见 [本地示例检查](references/cpt-local-examples.md)，选型与设计方法见 [从示例提炼设计](references/cpt-design-from-examples.md)。

## 函数、公式与动态默认值

无需实例配置即可检索 FineReport 10 函数和检查基础语法：

```bash
frcli report functions RANK
frcli report functions --keyword 日期 -f table
frcli report functions --category hierarchy -f table
frcli report formula-check '=IF($topn>0,SUM(ds.select(金额)),0)' --param topn
```

目录含 180 个内置实现类和 3 个数据集方法的名称、简要用途、签名及来源；未核实的签名
显式留空。检查支持单双引号、反斜杠转义和括号配对，未知名称按插件/自定义函数提示。
检查不执行公式，也不证明当前实例能够正确求值。

动态默认值用显式参数，与静态文本区分，以下均为 dry-run：

```bash
frcli report param demo_group/demo_user/demo.cpt \
    --set-formula 'edate=FORMAT(TODAY()-1,"yyyyMMdd")'
frcli report widget demo_group/demo_user/demo.cpt --param edate --type text \
    --default-formula 'FORMAT(TODAY()-1,"yyyyMMdd")'
frcli report edit demo_group/demo_user/demo.cpt --dataset ds --param edate \
    --default-formula 'FORMAT(TODAY()-1,"yyyyMMdd")'
```

`param` 只改模板参数，`edit --dataset` 只改目标数据集参数；`widget` 默认同时更新控件
与同名模板参数。`--default` 和 `--default-formula` 互斥；`--apply` 沿用模板写范围、
占锁、备份和回读校验。`param/widget --list` 的 `default_type` 区分公式与静态值。
函数语义、来源边界和运行期验收见 [函数与公式](references/formulas.md)。

## 导出与模板创作

单次导出示例沿用上面的 `sample_report`，输出在项目根目录的 `out/`：

```bash
FRCLI_TIMEOUT=300 frcli -i demo export excel "$sample_report" \
    -o out/sales_daily_20260131.xlsx \
    --params '{"edate":"20260131","extype":"simple"}'
```

CLI 内置文件魔数、HTML 出错页和排队页校验；失败会给出平台原因，已落盘的坏产物会保留为 `.bad`。Word 导出的实际格式为 **RTF**，默认扩展名 `.rtf`。格式通过后，仍需核对数据日期、参数和关键单元格；`extype=simple` 可处理部分分页问题，不能解除平台内存保护。

批量导出会真实触发多次计算，执行前需确认规模。清单为 YAML，示意如下：

```yaml
reports:
  - path: demo_group/demo_user/sales_daily.cpt
    format: excel
    output: ./out/sales_daily_{edate}.xlsx
    params:
      edate: ["20260130", "20260131"]
      extype: simple
```

保存为 `manifest.yaml` 后执行 `FRCLI_TIMEOUT=600 frcli -i demo export batch manifest.yaml`。列表参数展开为参数矩阵；输出名应覆盖所有变化参数，避免覆盖文件。检查结果中的 `failed`、`errors` 与 `warnings`，批量顶层 `status: ok` 表示流程结束，可能仍有失败条目。

模板创作支持 `new/cell/dataset/param/style/table/crosstab/highlight/page/chart/widget/link/sheet` 等入口，多数修改命令默认 dry-run，确认差异并获得目标授权后加 `--apply` 才写。已有模板的编辑预览仍可能读取服务器。

写入前设置 `FRCLI_WRITE_SCOPE="demo_group/demo_user/sandbox"` 限定授权目录；未设范围默认拒绝写入。`--any-path` 显式放行单次目标，仍需取得操作授权。覆盖或删除已有模板前先下载备份；写入包含占锁、覆盖备份和回读校验。模板删除移入服务端回收站，目录删除另需 `--recursive`。

模板创作配方与验收要求见 [创作手册](references/cpt-authoring.md)、[配方一](references/cpt-patterns.md) 和 [配方二](references/cpt-patterns2.md)。动态参数默认值、复杂填报控件等场景仍需结合 XML 或 Designer；列名绑定和公式必须按实际渲染结果验证。

## 调度与性能排查

查询任务与最近执行记录：

```bash
frcli -i demo schedule list -f table
frcli -i demo schedule get "demo_task"
frcli -i demo schedule record "demo_task" -n 20
frcli -i demo schedule history "demo_task" -n 20
frcli -i demo schedule log "demo_task_same_fire_1000000000000"
```

`history` 按时间升序，`record` 按时间倒序；`log` 必须使用 `history` 返回的 id。`get` 支持任务名或 UUID，名称查询可能模糊匹配；变更命令要求精确任务名，`delete` 使用任务 UUID。`tasks --all` 对应本人创建的任务，全平台任务名用 `schedule list`。

创建、更新、暂停、恢复、删除和立即执行均影响生产调度，操作前确认影响范围并备份 `schedule get`。换模板按「备份 → pause → update --template → 验证导出 → 恢复预期状态」执行；`update` 保留原暂停状态与创建人，非 0/1 状态会拒绝自动修改。新建载荷与输出 UUID 处理见 [SKILL.md](SKILL.md) §6.11、§6.26。

```bash
frcli -i demo inspect status
FRCLI_TIMEOUT=300 frcli -i demo inspect run "$sample_report" --op page
```

`inspect run` 需要平台性能分析插件，会真实计算模板并在内部等待结果，无需自行 sleep；仅开放 `page/view`。默认剔除 `meta.para`，`--raw` 结果可能含敏感会话参数。单元格耗时包含等待数据集的时间，先结合 `db_fetch` 判断取数与渲染；性能测试前关闭缓存。插件中的 SQL 可能截断至 500 字符，核对完整 SQL 使用 `report datasets --sql`。

## 配置与输出约定

配置按 `$FRCLI_CONFIG` → `~/.frcli/config.yaml` → `./.frcli.yaml` 搜索；`server add/remove/set-default` 写入 `~/.frcli/config.yaml`。token 缓存在 `~/.frcli/tokens/<实例>.json`，覆盖模板的备份放在 `~/.frcli/backups/`。

指定实例优先级为子命令 `-i` → 顶层 `-i` → `FRCLI_INSTANCE` → 配置默认实例 → 首个实例。环境变量均为可选项：

| 变量 | 默认值与用途 |
| --- | --- |
| `FRCLI_CONFIG` | 未设；覆盖配置文件的优先读取路径。 |
| `FRCLI_INSTANCE` | 未设；显式选项之外的实例选择。 |
| `FRCLI_TIMEOUT` | `30` 秒；REST 请求与导出、模板定义读取的超时。 |
| `FRCLI_RD_TIMEOUT` | `300` 秒；远程设计请求超时，覆盖原始模板下载、编辑、出图和数据集预览的相应 RPC 请求。 |
| `FRCLI_INSPECT_TIMEOUT` | `60` 秒；等待巡检结果上限，模板计算仍受 `FRCLI_TIMEOUT` 约束。 |
| `FRCLI_AUTH_LOCK_TIMEOUT` | `30` 秒；并发进程等待同实例登录锁的上限。 |
| `FRCLI_WRITE_SCOPE` | 未设即拒绝模板写入；显式限定授权目录。 |
| `FRCLI_WAIT_LOCK` | `0` 秒额外等待；在基础锁重试之后延长等待窗口。 |
| `FRCLI_CA_CERT` | 未设；加载指定 CA 文件。当前 SSL 实现关闭证书与主机名验证，该变量不会开启严格校验。 |

查询默认输出 JSON，多数查询支持 `-f table`；操作结果带 `status`，错误 JSON 输出到 stderr。CLI 业务错误通常返回 `1`，配置错误为 `2`，连接错误为 `3`，Click 参数错误也可返回 `2`。模板无改动返回成功并带 `changed: false`；批量是否全部成功须检查 `failed`。

认证使用 token 与登录 cookies，遇认证失败会尝试清缓存重登一次；并发登录由实例级锁保护。超时按所属通道调整变量；连接 reset 可原样重试；本机代理故障检查代理或 VPN，CLI 不自动绕过代理；502/503/504 先检查平台健康并降低并发。具体判据见 [SKILL.md](SKILL.md) 的关键坑点与故障排查。

## 项目结构与开发

```text
fanruan_v10/
├── SKILL.md                 # skill 入口、命令树、安全分级和排障
├── AGENTS.md                # 协作规则；CLAUDE.md / CODEBUDDY.md 软链接到它
├── README.md                # 项目说明
├── pyproject.toml           # 依赖、版本、src 布局与 frcli 入口
├── src/frcli/
│   ├── cli.py               # Click 命令注册
│   ├── commands/            # 各命令组
│   ├── client.py            # REST、导出与运行时巡检
│   ├── auth.py / config.py  # 登录、缓存与多实例配置
│   ├── neterr.py            # 共用网络错误分类
│   ├── remotedesign.py      # 远程设计通道与模板读写保护
│   ├── reportops.py         # 模板修改编排
│   ├── cptxml.py / chartxml.py / local_cpt.py
│   └── dataset_preview.py / rpc.py / jser.py / rdcrypto.py
├── references/              # 安装、启动器、XML、创作配方与协议手册
├── docs/                    # 内容落点、发布脱敏、探索与验证证据、巡检台账
├── tests/                   # pytest 回归测试
└── tools/                   # 打包、会话扫描和文档配方复现脚本
```

开发验证在根目录运行，测试环境另需 pytest：

```bash
PYTHONPATH=src python -m frcli report --help
PYTHONPATH=src python -m pytest tests/ -q
git diff --check
```

单项测试可指定 `tests/test_*.py`；部分安装包校验依赖 `FINEREPORT_HOME`，缺少时会跳过。`tools/doc_rerun.sh` 会真实写服务端模板并导出，须先阅读脚本、配置授权范围，不能作为默认无副作用检查。

维护 DSH 会话问题可用 `python tools/scan_sessions.py --date YYYY-MM-DD`；需本机存在 DSH 会话及 `zstd`，不带日期默认扫描昨天。工具只收集线索，结论需复核，台账只保留脱敏信息。

分发产物为 `dist/fanruan-v10.skill`，该文件在 `.gitignore` 中单独放行。打包前准备仓库外脱敏黑名单，执行 `tools/build_skill.sh --check` → `tools/build_skill.sh` → `tools/build_skill.sh --check`，确保新包也通过检查。详细门禁见 [发布与脱敏](docs/发布与脱敏.md)，信息归属见 [内容落点判定](docs/内容落点判定.md)。

frcli 与 skill 共用版本号；发布时同步更新 `src/frcli/__init__.py::__version__`、
`pyproject.toml::project.version` 和 `SKILL.md::metadata.version`，再核对新包内三处版本与源码一致。
