---
name: fanruan-v10
description: "使用 frcli 命令行工具操作 FineReport V10 报表服务器（帆软决策平台）。覆盖 10 个命令组：server(多实例配置) / report(模板目录·参数·数据集SQL·服务器数据集·模板上传覆盖删除·**本地Demo检索与设计画像 local-examples/local-profile/local-inspect**·**模板从零创作 new/cell/dataset/param/style/table/crosstab/highlight/page/chart/widget/link**) / export(PDF·Excel·Word·图片·CSV·批量) / attach(附件上传下载) / system(版本·健康·模块·权限·登录策略) / **inspect(运行时巡检·模板性能分析·各环节/单元格耗时)** / entry(平台条目·消息) / user(用户·部门·岗位) / schedule(定时任务·执行记录·日志节点树) / rpc(远程设计RPC·只读白名单·写需--yes)。触发词：FineReport、帆软、**本地Demo/样例学习/设计画像/报表选型/信息层级/版式设计/视觉技巧/图表选型/交互设计**、**运行时巡检/模板性能分析/runtime-inspection/性能瓶颈**、报表导出、.cpt、决策平台、定时任务、服务器数据集、数据集字段、**数据集预览**、**函数检索/公式检查/动态默认值**、执行记录、附件、改模板、上传模板、覆盖模板、**画图/图表/柱状图/折线图/饼图、交叉表、条件属性/标红/热力图、参数面板/控件、钻取/超链接、组内小计/占比/同比/环比/累计、页眉页脚/页码/重复标题行**。通过远程设计通道可直接写服务端模板（report upload/delete）或**从零创作报表**（report new/table/cell/dataset，见 references/cpt-authoring.md），不再需要 Designer。导出会真实触发服务端报表计算，产物必须校验魔数并调大超时。"
metadata:
  version: 0.11.2
  requires:
    bins: ["frcli"]
  cliHelp: "frcli --help"
---

# fanruan_v10 Skill（frcli · FineReport V10）

用 `frcli` 操作 FineReport V10 决策平台：浏览模板目录、读数据集 SQL、导出报表、管理定时任务；
也可以从本地 Demo 批量提炼 CPT 的报表选型、信息层级、版面、视觉、交互与图表手法。
所有功能通过 `frcli <命令组> <命令>` 调用，`<命令> --help` 查看参数。

## 1. 何时使用

- 导出帆软报表（PDF / Excel / Word / 图片 / CSV），含按日期等参数批量导出
- 查看报表的数据集定义与 SQL（口径溯源、找报表参数）
- 查/改/跑 FineReport 定时任务（调度、执行历史）
- 定位「报表里这个数怎么来的」
- **函数检索、公式检查与动态默认值**：`report functions/formula-check` 离线查函数与基础语法；
  参数默认昨天/月初等公式用 `report param --set-formula` 或 `report widget --default-formula`。
  使用前读 **`references/formulas.md`**，确认函数类别、参数顺序与使用上下文。
- **改已有模板**：`report upload` 覆盖 / `report delete` 删除；
  `report edit` 定点改**数据集 SQL / 连接 / 参数**（§6.7）；改**单元格**用 `report cell`（§6.14）
- **从零创作模板**：`report new / dataset / table / cell / param / style` 造出一张能取数的报表
  —— 五步上手与语法速查见 **`references/cpt-authoring.md`**；纯文本+公式+取数表+参数+样式都能写
- **从本地 Demo 学习设计技巧**：`report local-profile` 批量找同类样板并输出设计画像，
  `report local-inspect --design/--cells` 查看单份模板和具体格号；选型矩阵、信息层级、视觉/交互规则、
  代表样例和验收流程见 **`references/cpt-design-from-examples.md`**

不适合：**画复杂版面**（图表控件、填报控件、复杂表头嵌套、决策报表 .frm 的组件布局）——
这些仍然建议在 Designer 里做。本 CLI 能做的是「单元格网格 + 数据集绑定 + 扩展 + 样式 + 参数」
这一层，覆盖绝大多数**取数类报表**。

### CPT 结构检查与行列编辑（0.11.0 起）

删除/插入行列、区域复制移动和设计前先读 **`references/cpt-structure.md`**。
用 `report validate/refs` 检查和定位依赖，再用 `report row/column/range` 的 dry-run 预览；
不要让 Agent 手算坐标或全篇替换列字母。可确定的结构和引用由 CLI 联动，歧义明确阻断。
模板编辑命令均支持 `--local`；本地执行使用 `--apply -o NEW.cpt`，不读实例或联网。
聚合 CPT 的网格操作使用 `--sheet S --block N`，每块独立坐标。

## 2. 前置条件

`report functions/formula-check` 完全离线，不需要配置或启动实例。

仅检索、画像或检查本地 CPT 示例时，使用 `report local-examples/local-profile/local-inspect`，
不需要配置或启动实例。聚合块和单元格检查见 `references/cpt-local-examples.md`；从样例学习报表设计见
`references/cpt-design-from-examples.md`。

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
├── report                          报表模板（决策平台目录树）
│   ├── functions [NAME] [--keyword K] [--category C] [-f json|table]
│   │                                          离线函数目录：名称/签名/用途/来源，不执行公式
│   ├── formula-check EXPR [--context cell|parameter|widget] [--param NAME …]
│   │                                          离线基础语法检查，未知/插件函数只提示
│   ├── validate TARGET [--local] [--sheet S] [--block N]   结构、依赖和覆盖检查，不执行模板
│   ├── refs TARGET [--local] [--sheet S] [--block N] [--at A1]   引用/被引用关系
│   ├── row TARGET --delete 3:5 … | --insert-before 3 [--count N] | --at 3:5 --height N|--hide
│   ├── column TARGET --delete C:E … | --insert-before C [--count N] | --at C:E --width N|--hide
│   ├── range TARGET --at A1:C5 --copy-to E1|--move-to E1|--clear|--merge|--unmerge|--style N
│   │           [--local] [--sheet S] [--block N] [--apply] [-o NEW.cpt] [--any-path]
│   │           新增及现有模板编辑命令均支持 --local；默认 dry-run；详见 cpt-structure.md
│   ├── local-examples DIRECTORY [--keyword K] [--contains TEXT] [-n 30]  离线查找本地 CPT
│   ├── local-profile DIRECTORY [--keyword K] [--contains TEXT] [--tag T] [-n 20]
│   │                                                                     批量画像：原型/技术/图表/代表样例
│   ├── local-inspect FILE [--sheet S] [--block N] [--cells] [--design] [--sql] [-n 100]
│   │                                                                     离线检查；聚合块独立坐标
│   ├── list [DIRECTORY] [--keyword K] [--type cpt]   列目录；⚠️ 目录要具体，`/` = 全量（实测 3873 条）
│   │                                              `--keyword/--type` 走**服务端筛选**，别拉全量再本地筛
│   ├── info REPORT [-f]                     报表信息：数据集名清单 + 参数清单
│   ├── paras REPORT [-f json|table]         报表参数定义（官方接口，含派生参数公式）
│   ├── datasets REPORT [-f json|table] [--sql]   数据集名/参数/完整 SQL（--sql 不截断）
│   ├── preview REPORT --dataset NAME [--params JSON] [--rows N] [-f json|table]
│   │                                          预览 SQL 数据集（服务端真实执行、只取前 N 行，不写模板；见 §6.25）
│   ├── download REPORT [-o LOCAL]           下载模板**原始字节**（走远程设计通道，与 upload 同源）
│   ├── serverdatasets [-f]                  服务器数据集清单（平台级，实测 113 个）
│   ├── columns DATASET [-f]                 服务器数据集的字段清单（列名/列类型）
│   ├── authed [--keyword K]                 模板「认证(authentication)」配置路由（⚠️ 实测恒返回
│   │                                          `[]`，**不是**权限树；枚举有权限报表用 `list`，见 §6.6）
│   ├── upload LOCAL REMOTE [--force]        🔴 上传/覆盖服务端模板（远程设计通道，见 §6.7）
│   │                                          写前占锁+自动备份到 ~/.frcli/backups/，写后回读校验 SHA256
│   ├── delete REPORT --force                🔴 删除服务端模板（移入回收站，可恢复）
│   ├── ws-list [PATH]                       服务端远程工作区目录树（reportlets 下就是模板目录）
│   ├── fonts REPORT [-f]                    体检：模板用到但服务端**缺失**的字体（空 = 没问题）
│   ├── versions REPORT [-n 20] [-f]         模板的远程设计提交历史（版本号/提交人/时间，🟢 只读）
│   ├── image REPORT [-o FILE] [--form]      服务端直接渲染成 PNG（🟢 只读，不走 REST 导出）
│   │                                          .cpt 走 exportWorkBookAsImageData；.frm 加 --form
│   ├── edit REPORT [--list] [--dataset D] [--sql S | --sql-file F | --replace OLD=NEW …]
│   │              [--connection C] [--param P --default V|--default-formula EXPR]
│   │              [--apply] [--any-path]       结构化改模板（见 §6.7、references/formulas.md）
│   │              ⚠️ **默认 dry-run 只打印 diff**；`--apply` 才写，且必须先设 $FRCLI_WRITE_SCOPE
│   │                 或加 --any-path（不设范围 = 拒绝，见 §4 安全约束）
│   ├── new REMOTE [--sheet NAME] [--from TEMPLATE] [--output FILE] [--force]   从零建空白模板（见 §6.14）
│   ├── cell REMOTE --list [-f table]                     只读列单元格：A1/值/公式/绑定/扩展/样式
│   │        [--at B3 --set-value|--set-formula|--bind ds.col|--expand v|h|none|
│   │         --style N|--num-format FMT|--bold|--bg C|--align X|--border|--merge A1:C1|--clear|
│   │         --ds-result EXPR|--ds-filter EXPR|--expand-left A3|--expand-up B1|--show-html]
│   │        [--sheet S] [--apply] [--any-path]           改单元格（默认 dry-run；地址用 A1 记法）
│   ├── dataset REMOTE --list [--full]                    只读列数据集（读**模板字节**，非 format=cpt）
│   │        --add NAME --conn C --sql S|--sql-file F [--param p=v …] [--page-sql S]
│   │        --set-sql NAME --sql S [--param p=v …] | --remove NAME   [--apply] [--any-path]
│   ├── param REMOTE --list | --add p=v … | --set-default p=v … | --remove p … [--apply]
│   │        | --set-formula p=EXPR …                      模板参数；显式区分静态值与公式默认值
│   ├── style REMOTE --list | --add [--xml-file F | --num-format FMT --bold --bg C --align X --border]
│   │                                                     样式表（数字格式/粗体/底色/边框），加完用 --style N 绑
│   ├── table REMOTE --dataset ds --at A1 --columns a,b,c [--header] [--labels "x,y,z"]
│   │          [--expand v|h|none] [--mode list|group|summary] [--fn sum] [--group-by x,y]
│   │          [--widths 12,16] [--style N] [--header-style N] [--sheet S] [--apply] [--any-path]
│   │                                                     一次生成整张取数表（表头+逐列绑定+扩展）
│   ├── crosstab REMOTE --dataset ds --at A3 --row a,b --col c --value v
│   │          [--agg sum|count|avg|max|min] [--total-row] [--total-col] [--no-header]
│   │          [--label S] [--value-labels x,y] [--style N] [--header-style N] [--widths W] [--sheet S]
│   │                                                     交叉表/动态列（行×列×值，列数随数据自动增长）
│   ├── highlight REMOTE --at D3|A3:D3 --rule '条件:动作' [--rule …] | --clear | --list
│   │          [--sheet S] [--apply] [--any-path]          条件属性：阈值标红/热力图/隔行变色/隐藏整行
│   │          条件 `v>100`（值比较）或 `ROW()%2=0`（公式）；动作 bg=/fg=/bold/size=/font=/
│   │          rowheight=0(隐藏整行)/value=/border；**规则按顺序生效，后面的覆盖前面的**
│   ├── page REMOTE --list | --header-height N --footer-height N --freeze 列,行
│   │          --repeat-rows 3,4 | --no-repeat-rows 3,4
│   │          --repeat-header-rows 1:1 | --repeat-footer-rows a:b | --repeat-header-cols c:d
│   │          --header-text S | --footer-text S [--footer-formula] [--footer-position x]
│   │          --page-freeze on|off [--sheet S]          分页设置（重复标题行/页眉页脚页码/冻结）
│   ├── chart REMOTE --at A1 --dataset ds --type column|line|pie|ring --category C
│   │          [--series S] --value V [--fn sum] [--title T] [--show-title] [--cs N] [--rs N] [--sheet S]
│   │          | --list                                  图表（VanChart；导出 xlsx 是嵌入图片）
│   ├── widget REMOTE --param p --type combo|date|text|check|number [--options "a,b"]
│   │          [--default v|--default-formula EXPR] [--label L] [--x/--y/--width/--height] | --list
│   │                                                     参数面板控件（**控件名=参数名** 才联动）
│   └── link REMOTE --at A3 --to 报表路径|URL [--type reportlet|web|javascript]
│              [--param k=v …] [--frame _self|_blank] [--sheet S] | --clear | --list
│                                                        单元格超链接/钻取（纯预览态交互）
│    ⚠️ 上面 12 条创作命令**默认 dry-run**，`--apply` 才写；语法与配方见 references/cpt-authoring.md、
│       **references/cpt-patterns.md**（第一辑 8 类）、**references/cpt-patterns2.md**（第二辑：
│       图表/参数控件/钻取/层次坐标/分页，含"写错的对照"）
├── export                          报表导出（真实触发服务端计算）
│   ├── pdf|excel|word|image|csv REPORT [-o FILE] [--params JSON] [-i]
│   │        缺省输出名派生自报表名：.pdf / .xlsx / .rtf(word 实际是 RTF) / .png / .csv
│   └── batch MANIFEST.yaml [-i]             批量导出（YAML 清单，逐条汇总成败）
├── attach                          服务器附件（落附件缓存，**不动报表目录**）
│   ├── upload LOCAL [--name NAME]           上传本地文件 → 返回 attach_id
│   └── remove ATTACH_ID                     删除附件（传完记得清理）
├── system                          系统与平台信息（🟢 只读）
│   ├── version [-f]                         服务端版本 + 各模块 jar 版本
│   ├── health [-f]                          系统健康状态
│   ├── modules [--keyword K]                决策平台模块树
│   ├── authority                            权限开关（分级授权/报表编辑/调度…）
│   └── login-policy                         登录配置 + 密码策略 + 密码到期提醒
├── inspect                         运行时巡检/模板性能分析（插件 com.fr.plugin.ins）
│   ├── status [-f]                         插件状态：检测点是否生效（🟢 只读）
│   └── run REPORT [--op page|view] [--params JSON] [--timeout S] [--raw] [-f]
│                                           巡检一张模板：**内部触发计算 + 轮询结果**，
│                                           调用方不用 sleep / 猜等待时间（见 §6.22）
│                                           ⚠️ 会真实执行一次模板；op 只允许 page/view
│                                           ⚠️ 默认剔除 meta.para（工号/组织）；--raw 才原样输出
├── entry                           平台条目与消息（🟢 只读）
│   │   ⚠️ 条目树 id 是 UUID，与 report 的报表目录树（id = 文件路径）是两套
│   ├── list [--page P] [-n N] [--keyword K] 条目分页列表
│   ├── roots [-f]                           条目根节点
│   ├── all [-f]                             全量条目
│   └── messages [--unread] [-n N]           平台消息（未读/全部）
├── user                            用户与组织（🟢 只读）
│   ├── list [-f]                            当前账号可见用户（工号+姓名，非全量目录）
│   ├── me                                   当前登录账号信息（工号/姓名/角色）
│   ├── departments [--keyword K]            部门树（本账号实测为空）
│   └── posts [--keyword K]                  岗位列表（实测 39 条）
├── schedule                        定时任务（生产调度，写操作危险）
    ├── list [-f]                            仅返回任务名
    ├── tasks [--page P] [-n N] [--all]      任务列表**含 taskId**（--all = listAll，只含**本人创建**任务；
    │                                         全部任务名用 `schedule list`；非 --all 时下一页会 stderr 提示 hasNext）
    ├── get TASK_NAME|TASK_ID [-f]           任务详情（也接受 UUID taskId；UUID 反查只覆盖本人创建任务）
    ├── exists TASK_NAME                     按准确名字判断任务是否存在
    ├── create CONFIG.yaml                   从 YAML 建任务（YAML 怎么来见 §6.11）
    ├── update TASK_NAME [-d DESC] [-t TEMPLATE]  改描述/模板路径（名字须**精确匹配**）
    │                                          ⚠️ 平台 PUT 会重置任务状态为启用；本命令会保留原暂停态；
    │                                             taskState 非 0/1（如 2=已结束）拒绝自动改；--template 先校验路径存在（见 §6.26）
    ├── pause TASK_NAME                      暂停任务（只切状态，taskState 1，不删任务；名字须精确匹配）
    ├── resume TASK_NAME                     恢复任务运行（taskState 0；名字须精确匹配）
    ├── delete TASK_ID                       ⚠️ 参数是 UUID `id`，不是任务名（body 为裸数组，见 §6.6）
    ├── run TASK_NAME                        ⚠️ 立即在生产执行该调度
    ├── executing [-f]                       当前正在执行的任务
    ├── history [TASK_NAME] [-n N] [-f]      执行历史（**按时间升序**，-n N = 最早 N 条；
    │                                         要最新一条把 -n 调大后取末尾，或 schedule record --all）
    ├── record TASK_NAME [--page P] [-n N] [--all]  某任务的执行记录+结果（含 detailMessage/runType）
    │                                          ⚠️ 平台返回顺序不可靠；已按 time 倒序，--all 翻全量后整体倒序
    ├── records [--page P] [-n N]            全平台执行记录（total 十万级）
    ├── log TASK_LOG_ID [-f]                 单条日志详情节点树（哪一步失败、错误内容）
    │                                        ⚠️ TASK_LOG_ID 必须是 history 返回的 id（<任务名>_same_fire_<时间戳>），
    │                                           record/records 的 uuid/id 是执行记录 id，传错报「对象不存在」
    └── setting                              调度全局设置（消息开关/日志清理）
└── rpc                             远程设计 RPC 网关（高级；🟢 只读白名单 / 🔴 写需 --yes）
    ├── services [--local]                  服务类清单（--local 列本地白名单）
    ├── methods CLASS [--local]             某服务类的方法签名
    └── call CLASS METHOD --args JSON [--yes]   调用（默认只读白名单，写方法需确认 + 写范围）
```

**报表路径写法**（本服务器的真实约定，实测）：

```
demo_group/demo_user/dept_a/dept_b/sales_daily.cpt
```

相对路径、带 `.cpt`、**不带前导 `/`**、**不用 `//doc//`**。路径直接取自 `report list <目录>` 返回的 `path` 字段。

## 4. 安全约束

| 等级 | 命令 | 说明 |
|------|------|------|
| 🟢 只读 | `report validate/refs`、`server list/test`、`report local-examples/local-profile/local-inspect/list/info/paras/datasets/preview/download/serverdatasets/columns/authed/fonts/versions/image`、`report cell --list`、`report dataset --list`、`report param --list`、`report style --list`、`report highlight --list`、`report page --list`、`report chart --list`、`report widget --list`、`report link --list`、`schedule list/tasks/get/exists/executing/history/record/records/log/setting`、`system *`、`entry *`、`user *` | 直接执行 |
| 🟡 计算 | `export *`、`export batch` | 数据只读，但服务端真实跑报表（复杂报表 50s+，批量可达数十分钟）；批量前说明规模 |
| 🟠 本地写 | `server add/remove/set-default` | 只改实测环境 `~/.frcli/config.yaml` 与 token 缓存 |
| 🧱 写范围（**默认拒绝**） | 环境变量 `FRCLI_WRITE_SCOPE=<目录>`，或命令行 `--any-path` | **没设范围又没 `--any-path` → 写命令直接拒绝**（沉默 ≠ 不限制）。设了范围则 `report upload/delete/edit/new/cell/dataset/param/style/table --apply`/`rpc` 写调用只允许落在该目录下，含 `..` 穿越、兄弟目录（`<scope>.tmp`、`<scope>x`）一律拦截 |
| 🟠 服务端写（轻） | `attach upload/remove` | 只往**服务器附件缓存**写/删文件，不碰报表目录与调度；upload 会在服务端留文件，用完 `remove` 清理 |
| 🔴 危险 | `schedule create/update/delete/run/pause/resume` | 直接改/跑**生产调度**：`run` 会立刻执行并推送下游（飞书/FTP/邮件），`delete` 不可逆；`pause/resume` 改变任务启用状态（影响后续定时触发），`update --template` 改任务指向的模板 —— 都先备份 `schedule get` 并向用户确认影响范围 |
| 🔴 危险 | `report row/column/range --apply`（远端） | 会改变模板结构和后续计算；执行前必须确认目标模板及影响范围，先审阅 dry-run。沿用写范围、占锁、覆盖备份、快照复核和回读校验。歧义引用不能强制绕过；`--local` 只写指定新文件 |
| 🔴 危险 | `report upload` / `report delete` | 直接改**生产模板文件**：影响所有看这张报表的人。upload 覆盖需 `--force`（自动备份原文件）；delete 移入回收站可恢复，但需 `--force`；**目标是目录时必须再加 `--recursive`**（不加直接拒绝） |
| 🟠 服务端写（模板创作） | `report new` / `cell` / `dataset` / `param` / `style` / `table`（**默认 dry-run，`--apply` 才写**） | 与 `report edit --apply` 同一道写范围守门 + 占锁 + 备份 + 回读 SHA256；新建/改动只应落在你被授权的目录 |

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
frcli report preview "demo_group/demo_user/dept_a/dept_b/sales_daily.cpt" --dataset ds1 \
    --params '{"edate":"20260228"}' --rows 20 -f table   # 等价 Designer 右键数据集「预览」（只读）

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
frcli schedule history "demo_user_销售_示例概览by月_飞书" -n 5      # 升序返回，最后一条才是最新；返回 id = logId
frcli schedule record "demo_task_超时明细" --all -n 20             # 执行记录+结果（翻全量、按 time 倒序）
frcli schedule pause  "demo_任务名"                                # 暂停（只切状态，不删任务）
frcli schedule update "demo_任务名" --template "demo_group/…/新模板.cpt"   # 改任务指向的模板（保留暂停态）
frcli schedule resume "demo_任务名"                                # 恢复运行
frcli schedule log "demo_task_超时明细_same_fire_1000000000000"   # 日志节点树：哪一步失败
#   写操作（🔴 先确认）：create / update / delete <UUID> / run <任务名>

# 6.1) 新建任务：拿现成任务当模板（配方与坑见 §6.11）
frcli schedule get "参照任务名" -f json > src.json
python3 - <<'PY'
import json, uuid, yaml
d = json.load(open("src.json"))
for k in ["id", "nextFireTime", "preFireTime", "editable", "taskState", "originTaskId"]:
    d.pop(k, None)
d["taskName"] = "新任务名"                  # 保持与参照任务同命名风格
d["creator"] = "00000000"                   # 建任务时带上创建人（PUT 改不掉），别留空
d["scheduleOutput"]["baseName"] = "新文件名#~_${FORMAT(NOW(), \"yyyyMMdd_HH\")}~#"
so = d["scheduleOutput"]                    # ⚠️ 必须重置输出 id，否则 create 报 detached entity
so["id"] = str(uuid.uuid4())
for a in so["outputActionList"]:
    a["id"] = str(uuid.uuid4()); a["outputId"] = so["id"]
yaml.safe_dump(d, open("new.yaml", "w"), allow_unicode=True, sort_keys=False)
PY
frcli schedule create new.yaml
frcli schedule run "新任务名"

# 7) 切换实例（多环境）
frcli -i dev report list "某目录"        # 顶层 -i 现在对所有子命令生效（0.6.0 前被静默忽略！）
frcli report list "某目录" -i dev         # 子命令级 -i，优先级更高
export FRCLI_INSTANCE=dev                 # 也可以用环境变量钉住实例
frcli -i nosuch report list "某目录"      # 实例不存在 → 直接 CONFIG_ERROR，绝不会回落到默认实例

# 7.5) 改服务端模板（🔴 先确认影响范围；走远程设计通道）
frcli report ws-list "demo_group/demo_user"                  # 看服务端真实路径（只读）
frcli report download "demo_group/demo_user/临时/a.cpt" -o a.cpt   # 拉下来
#   ……本地改 a.cpt（XML：<Query>/<DatabaseName>/<TableData>…）……
#   ⚠️ 写命令默认拒绝：先限定范围，或对本次目标显式 --any-path
export FRCLI_WRITE_SCOPE="demo_group/demo_user/临时"      # 推荐：限定范围
frcli report upload a.cpt "demo_group/demo_user/临时/a.cpt" --force
#   → 自动占锁 + 备份原文件到 ~/.frcli/backups/ + 回读 SHA256 校验
frcli report delete "demo_group/demo_user/临时/a.cpt" --force    # 移入回收站

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

⚠️ **HTTP 502/503/504 是平台网关/上游超时，不是模板坏了**（2026-10-22 真实会话：服务端初始化/繁忙时并发导出两条大报表，
两条都报 `导出来败: HTTP 504`，同时 `system health` 的模块 detail 是 `module Initializing`）。
0.10.14 起错误信息会提示：先 `frcli server test` / `system health` 看平台状态；单条稍后重试通常即成功；批量导出降低并发；
**不要改报表参数**。（其它非 200 状态仍只报 `导出失败: HTTP <code>`。）

**必须校验魔数**（0.6.0 起 `export` 已内置 `assert_export_magic`，不符直接报错）：

| 格式 | 文件头 | 备注 |
|------|--------|------|
| xlsx（excel） | `PK\x03\x04` | |
| **word** | `{\rtf1`（`7b5c72746631`） | ⚠️ 帆软 `format=word` 出的是 **RTF 不是 docx**，落盘默认名是 `.rtf`；按 `PK` 校验会把好文件判成坏文件 |
| pdf | `%PDF` | |
| png（image） | `\x89PNG` | |
| csv（text） | 无魔数 | 靠内容判断 |
| 出错页 | HTML，含 `出错页面` / `Oops!!!` / `detail-message` | 200 + HTML，不看魔数会当成功 |
| 出错页（另一模板族） | HTML，首字节就是 `<!doctype html>`，含 `class="detail-message"` / `class="simple-message"` | **没有**「出错页面」字样，只有一个「很抱歉…」+ 具体原因，见下 |
| **排队页** | HTML，含 `Dec-Waiting_In_Line` | 并发/限流时的「排队中」页，**无 title 无 detail-message**，2KB 左右；重试一次通常即成功，批量导出要降并发（0.6.0 起 `export` 会识别并报错） |

出错页的 `detail-message` 是 html 实体编码的**具体报错**（错误代码 + 原始 SQL），解码后可直接定位坏数据集。
⚠️ 该文本有**单引号**（`id='detail-message'`）和双引号两种写法，解析要都认（0.6.0 前只认双引号，单引号页会退化成
「响应不是 JSON」这种没用的提示）。

`export image` 报 `错误代码:11100023 导出图片过大，请减少导出的内容`：平台对单张 PNG 有尺寸/内容上限，
不是 CLI 故障；改用 `export pdf`/`export excel`，或减少列数/拆 sheet 后再出图。

⚠️ **选择器也有两种写法**，两种都要认（0.10.7 起按 `(?:id|class)=` 匹配）：
老语料是 `<div id="detail-message">错误代码:11300002 …</div>`；2026-10 实测的**内存保护页**只有 class：

```html
<div class="simple-message">非常抱歉，无法查看该页面</div>
<div class="detail-message">很抱歉，数据量过大触发保护机制，请减少查询数据量。若您是管理员，可于智能运维-内存管理-模板限制中更改此项限制。</div>
```

这个模板族**没有**「出错页面」字样 ⇒ 出错页判据是「**开头是 HTML 形态**（`_looks_like_html_head`）**且** 命中
结构标记/特征串」，**不是**"64KB 窗口里出现过特征串"（后者会把合法 CSV 的备注列误判成坏产物，0.10.3 实测事故）。

⚠️ 平台原因提取是**整页读**：出错页判据只用头部 64KB，但 `detail-message` 里可能嵌着整段原始 SQL，
出错页实测 126KB（2026-10 真实会话，某复杂报表导出）——0.10.12 起对 HTML 出错页按需读全（上限 8MB）；
更早版本只读 64KB，长 SQL 页面会丢失平台原因（只报「导出产物是平台出错页」）。

撞上内存保护页时，`EXPORT_ERROR` 会带出平台原文**并附可执行建议**（`extype=simple` 不解除该保护）：

```
导出产物是平台出错页，不是报表: out/big.xlsx；平台原因: 很抱歉，数据量过大触发保护机制，请减少查询数据量。若您是管理员，可于智能运维-内存管理-模板限制中更改此项限制。；
平台内存保护（数据量过大触发保护机制）：先在 SQL/参数上缩小查询数据量、或分批导出；`--params '{"extype":"simple"}'` **不解除**该保护；管理员可在 智能运维-内存管理-模板限制 中调整上限
```

0.10.3 起 `EXPORT_ERROR` **把平台原文带出来**，不必自己去解 `.bad` 文件（`detail-message` 实测落在 4KB 级页面的后半段，
只看前 512B 会漏掉）：

```
导出产物是平台出错页，不是报表: out/review.csv；平台原因: 错误代码:11300002 行高列宽超出页面大小设置；
该错误码实测为宽表/大行高超出分页导出的页面设置所致，加 `--params '{"extype":"simple"}'` 改原样导出后重试；
坏产物已改名保留在 out/review.csv.bad
```

`detail-message` 为空时退到 `simple-message` 的本地化 key 再翻成人话（与 `_unwrap_json` 同一口径）。

### 6.2 默认 30s 超时，复杂报表必然超时（导出与 REST 读取都吃它）

实测同一张报表：默认超时 → `导出请求失败: The read operation timed out`；`FRCLI_TIMEOUT=300` → 50s 成功导出 225KB xlsx。

**REST 读取命令同样吃这个默认值**：`report info / datasets / paras` 走服务端解析模板（含数据集校验），
复杂模板**冷启动**实测 50s 级，同一命令紧接着重跑约 18s（服务端已缓存）——即默认 30s 下第一次必然打空。
⇒ **复杂报表动手前先设 `FRCLI_TIMEOUT=300`（批量 600）**，导出与读取都适用，不要等失败再重试。

**例外：远程设计通道（含读模板字节与改模板）超时变量是 `FRCLI_RD_TIMEOUT`（默认 300s），调 `FRCLI_TIMEOUT` 对它无效**。
`report download / upload / delete / cell / dataset / table / crosstab / image / sheet` 等走远程设计 RPC 的命令都算；`report new` 仅在 `--from <服务端模板>` / `--apply` 时才走远程设计（默认是本地 dry-run）。
报错形如 `远程设计请求失败: timed out（…用 FRCLI_RD_TIMEOUT=600 …）`，按提示调这个变量。

### 6.3 参数只传驱动参数

模板里的 `${edate}` `${sdate_mtd}` 等派生参数无需手算，FineReport 根据驱动参数自动推导。
从 `report datasets` 的 SQL 里找 `${...}` 出现的主参数（通常是 `edate`/`sdate`），只传它 + `extype=simple`。

### 6.4 空数组 `[]` = 认证失效（**未必过期**）

token 缓存 `~/.frcli/tokens/<instance>.json`（默认 24h）。`schedule list` / `report list` 返回 `[]` 而服务器确有数据时，先怀疑认证，而不是「服务器没有数据」。
⚠️ 例外：`report authed` 的 `[]` 与认证无关（该路由恒空，见 §6.6）。

**本地 `expires_at` 还在未来也会失效**（实测：缓存远未过期，列表全返回 `[]`，换新 token 立刻正常）。本服务器失效 token 的真实表现是 **302 重定向到 CAS 登录页**（`https://sso.example.com/cas/login?...`），**不是 401** —— 只判 401/403 会漏掉。

0.1.1 起 `_request` 已识别 302→CAS：自动清缓存重登一次并重试；重登后仍被踢回登录页才报 `AUTH_FAILED`。仍可手动兜底：

```bash
rm -f ~/.frcli/tokens/*.json    # 下次调用自动重登
```

### 6.5 `report datasets` 读不到定义 = 该报表数据集本身报错

`report datasets/info/download` 走 `format=cpt` 取模板定义，服务端会校验数据集。数据集配置错误时返回 0 条 / `无法读取报表定义` —— 这不是 CLI 故障，而是**这张报表当前就是坏的**（导出也必然拿到出错页面）。

另一种常见形态：表还在但**列被重建/缺失**，报 `Could not resolve column/field reference: 'xxx'`，报文自带整段原始 SQL。
数据集 SQL 引用了临时镜像/旧结构表时，先核对真实表列（`olap sql desc`），再改绑正式表；要批量找哪些模板引用了
这张表，用平台元数据反查报表 SQL（内部表与查法见本地知识库），不要逐个 `report datasets` 试。

### 6.6 命令名与参数的真实语义

- `schedule get/run/update` 收的是**任务名**；`schedule delete` 收的是 **UUID `id`**（先 `schedule get` 拿），且请求体是**裸数组** `["<id>"]`。传错会报 `任务不存在` 或删不动。
- `schedule get` 内部是**模糊搜索取第一条**，任务名需与 `schedule list` 完全一致，避免误命中。
- 报告类命令的模板路径是**位置参数**：`report info <路径>`（不要写 `--path`）；`report datasets` **没有 `--name` 过滤**
  （输出全部数据集，要单看某个就 `--sql` 后本地筛/直接读 JSON 的 `name` 字段）；`schedule` **没有 `runs` 子命令**
  ——查执行记录用 `schedule record`/`records`（2026-10 三个真实会话各踩一次，属参数猜错，命令签名见本文件命令树）。
- `report list <目录>` 结果里会**包含该目录自身**一条（`is_directory: true`），属正常实现，过滤掉即可。
- `report list /` 会返回**整个服务器**的文件树（数千条，随平台增长；实测 2026-10 约 3.9k），不要用 `/` 当"顶层"。
- `-f/--format` 是**子命令**选项，必须写在子命令后面：`frcli report list -f json`；写成 `frcli -f json report list`
  会报 `Error: No such option: -f`（2026-10-29 真实会话踩过一次，不是命令缺失）。
- ⚠️ `report authed` **不是**「当前账号有权限的模板树」：它读的是模板**认证(authentication)配置**路由
  （`GET /decision/v10/report/templates/all/authentication`），实测该路由**恒返回 `[]`**（HTTP 200 的原始响应就是
  `{"data":[]}`，`keyword/type/id/pid` 多种参数形态同样为空）——**空数组不代表账号没权限**，别拿它判断
  「我有哪些报表」。要看有权限的模板树用 `report list`（平台已按权限过滤；实测 2026-10 约 3.9k 条）。
  结果为空时 0.10.6 起会在 **stderr** 打一行提示（stdout 仍是合法 JSON，管道解析不受影响）。
- `schedule history [任务名]` 是 **taskName 精确匹配**：任务近几天没有日志就静默返回 `[]`，不代表 CLI 坏了（不传名字才看全局日志）。
- ⚠️ **`schedule log` 的参数是 `schedule history` 返回的 `id`**（形如 `<任务名>_same_fire_<时间戳>`）。
  `schedule record` / `schedule records` 里的 `uuid` / `id` 是**执行记录 id**，传进 `log` 平台会报「对象不存在」
  （detail-message 为空，只剩 `Fine-Dec_Default_Error_Tip`）。要定位某次失败：先 `schedule record <任务名>` 看
  `detailMessage`/最近记录，再 `schedule history <任务名>` 取最新 `id` 去 `log`；0.10.15 起传错会直接给这个提示。
- ⚠️ `schedule history -n N` 返回的是**按时间升序**的前 N 条 —— `-n 1` 给的是**最早**那条，不是最新。取最新要么放大 `-n` 后取最后一条，要么用 `schedule record`。
- ⚠️ `schedule record` 的服务端**分页内顺序不保证按时间**（实测同一页出现 10-02、10-01、10-23 混排）：CLI 单页也按 `time` 倒序输出；要跨页取最新记录加 `--all`（翻全量后整体倒序）。
- ⚠️ 平台 `task/search` 是**子串模糊搜索**且取第一条：`get` 传前缀/错字会命中别的任务（会 stderr 警告）；`update/pause/resume/run` 这类写命令要求**任务名精确匹配**，不匹配直接拒绝。
- ⚠️ `schedule tasks --all`（`task/listAll/2`）只含**本人创建**的任务（实测 397 vs 名单 1155）：要全部任务名用 `schedule list`；`get/pause/resume/update` 接受 taskId，但 UUID 反查同样只覆盖本人任务。
- `server test` 0.1.1 起**真实发一次认证请求**（返回 `http_status` + `relogin`）——此前只查本地缓存，缓存 token 已失效时照样报 ok（假阳性）。

### 6.7 改模板内容 = 远程设计通道（0.5.0 起已实现，别再找 REST）

**结论**：REST 确实没有写模板内容的接口（569 条路由全查过），但决策平台另有一条
「远程设计」通道，Power 足够，已复刻进 `frcli report upload/delete`。

- 通道：`POST {workspace}/decision/remote/design/check|verify|channel`。
  `/channel` 是一个**通用反射 RPC 网关**：body 里给「声明类名 + 方法名 + 参数类型 + 参数」，
  服务端 `WorkspaceServerInvoker` 直接 `Class.forName(...).getDeclaredMethod(...).invoke(...)`。
  可调用的服务清单：`POST /decision/remote/design/service`（本服务器 28 个），其中
  - `com.fr.workspace.resource.WorkResource` = 服务端 `WEB-INF` 远程文件系统
    （readFully/exist/length/list/write/delete/rename/createDirectory…）
  - `com.fr.workspace.server.lock.TplOperator` = 模板锁与删除
    （readAndLockFile/closeAndFreeFile/delete，delete 是**移入回收站**不是物理删）
- 报文不是 JSON：`gzip( Java 对象流(InvocationPack) + Java 对象流(HashMap metadata) )`；
  参数各自是 `Java 对象流(mark="JDK") + Java 对象流(value)`。
  Python 侧实现在 `src/frcli/jser.py`（手写 Java 序列化），与帆软原件逐字节一致（见
  `tests/test_remotedesign.py` 里固化的 Designer 原报文）。
- 密码要加密后再发 `/verify`：`/check` 返回 `transmissionEncryption`（0=RSA 1=SM2 2=AES 3=SM4）
  与 `frontSeed`/`frontSM4Key`；AES = `AES/ECB/PKCS5Padding`、key = frontSeed 前 16 字节补零，
  SM4 = `SM4/ECB` + ISO7816 填充（0x80 补零）、key = frontSM4Key（32 位 hex）。
  纯 Python 实现在 `src/frcli/rdcrypto.py`，与 `SecurityToolbox` 输出逐字节一致。
- **权限**：路径含 `reportlets` 时查该账号的「远程设计」授权目录；不含则完全不校验。
  ⚠️ 无权限时 `write` **静默不写也不报错** → 写完必须回读校验（`upload` 已内置 SHA256 比对）。
- 路径：远程工作区根 = 服务端 `WEB-INF`。平台展示路径 `A/B/x.cpt` 对应
  `reportlets/A/B/x.cpt`（`report upload` 会自动补 `reportlets/` 前缀）。
- 覆盖已有模板前 `TplOperator.readAndLockFile` 先占锁：**别人 Designer 里开着就拒绝写**
  （避免互相覆盖）；`upload` 会把原文件备份到 `~/.frcli/backups/`；写完 `closeAndFreeFile` 释放。
- 实测（2026-09，fr.example.com）：新建 .cpt → 回读 SHA256 一致 → **决策平台模板树立即出现
  该模板、`report info` 能解析出数据集清单**；覆盖、删除（回收站）均通过。
- 上传后平台侧缓存：服务端按文件 mtime 失效模板缓存，实测无需额外刷新动作。
- 协议原文与「换版本后怎么复核」见 `references/remotedesign.md`（含用Designer jar
  生成参照报文、逐字节比对的脚本）。
- **28 个服务的全量签名**（150 个方法 + 只读/写/deny 判定 + 所在 jar）：`references/remote-services.md`。
  用 `frcli rpc services` 看线上清单，`frcli rpc methods <类>` 看签名。
- **cpt XML 结构速查**（`WorkBook`/`TableData`/`Query`/`DatabaseName` 层级与可改点、
  定点替换为什么不能用 ElementTree）：`references/cpt-xml.md`。

#### 路径口径：三种服务收的路径**不一样**（写错不报错，只返回空）

| 服务 / 入口 | 收什么 | 例 |
|---|---|---|
| `WorkResource` / `TplOperator`（`report upload/delete/download/ws-list`、`rpc call` 的读写删锁） | **工作区路径** | `reportlets/demo_group/demo_user/x.cpt` |
| `VcsOperator` / `TemplateExportOperator` / `TemplateChecker`（`report versions/image/fonts`） | **展示路径** | `demo_group/demo_user/x.cpt` |
| REST（`report list/info/datasets/paras`、`export`） | **展示路径** | 同上 |

前缀写错**不会报错**：工作区路径少 `reportlets/` → 空目录 / `false` / 0 字节；
展示路径多 `reportlets/` → 空列表。`rpc call` 遇到这种情况会回一句 `hint` 指路口径。
⚠️ `report versions` / `rpc call VcsOperator getVersions` 传错前缀时**静默返回 `[]`**，
别当成「这张报表没有历史版本」。即使路径正确，它只覆盖**远程设计通道/CLI 写入**产生的提交历史：
直接在服务器 Designer 保存的模板可能一直为空，不能用来判断「模板是否最新」——判断新鲜度看导出数据日期或本机文件 mtime（`report info` 不含版本/时间字段）。

#### 改模板内容不必再整文件替换：`report edit`

```
report edit REPORT [--list]
              [--dataset D] [--sql S | --sql-file F | --replace OLD=NEW …]
              [--connection C] [--param P --default V] [--apply]
```

拉模板（远程设计通道）→ **结构化改 XML**（`cptxml.set_text` 定点替换，只动目标元素的
字节区间，其余逐字节保留；不是正则、也不是 ElementTree 往返）→ 打印 diff。
**默认 dry-run**；`--apply` 才写，写前过 `assert_in_write_scope`（**fail-closed**：
没设 `$FRCLI_WRITE_SCOPE` 就必须 `--any-path`）+ `assert_template_bytes`，
写时占锁 + 备份 + 回读校验。

实测（2026-09，测试目录副本）：`FRCLI_WRITE_SCOPE=reportlets/demo_group/demo_user/skill测试 \
frcli report edit …/x.cpt --dataset xs --replace "'20251013'='20251101'" --apply`
→ `verified: true`、备份落 `~/.frcli/backups/`、改后 SQL 区间前后字节与原文完全一致，
且 `report datasets --sql` 能读到新日期。

#### ⚠️ `format=cpt` 不是模板文件字节（0.5.1 前 `report download` 的坑）

`GET /decision/view/report?reportlet=X&format=cpt` 返回的是**另一种序列化**，不是服务器上那个 .cpt：

| 来源 | 根元素 | 同一张模板实测 |
|------|--------|----------------|
| 远程设计通道 `readFully`（= 服务器上的文件） | `<WorkBook>` | 4510 B |
| `format=cpt` | `<TableDataMap>`（缺 `<WorkBook>`/`<StyleList>`） | 6362 B |

两者 SHA256 不同。拿 `format=cpt` 的产物 `report upload --force` 会**把模板写坏**，而且
写后回读校验还是通过的（写进去的确实是那份 stub）——静默毁报表（0.5.1 前 `report download`
就是走这个端点，所以 `download → 改 → upload` 是条毁数据的流程）。

现在的守门：
- `report download` 改走远程设计通道，落盘字节与服务器**逐字节相同**（要该路径有远程设计授权）
- `report upload` 默认断言「前 600 字节含 `<WorkBook>`」，否则拒绝写入（`--allow-format` 才放行）
- 要数据集定义/ SQL 用 `report datasets`（它本来就走 `format=cpt` 并解析 `<TableData>`）

<details><summary>历史结论（已作废，保留备查）</summary>

- `report upload` / `report delete` 旧版是空壳（`'FineReportClient' object has no attribute ...`）。
- `TemplateBean` / `FileBean` 只有元数据字段（id/pId/text/path/description/showType/parameters…），
  没有内容字段；`ReportEntryService.addTemplates()` 只写条目记录；目录管理类写接口
  （`PUT /v10/template/{id}`、`POST /v10/{directoryId}/templates`、`PUT /v10/file/{id}`、
  `PUT /v10/entry(s)`、`POST /v10/dataset/upload`）对普通分析账号一律
  `Fine-Dec_No_Privilege_Access_Page`。
- 此前误判「远程设计载荷 SM4 加密、抓包拿不到明文、不建议复刻」：加密只作用于**密码字段**，
  `/channel` 的 RPC 载荷是 gzip + Java 序列化，可完整复刻。
</details>

### 6.8 底层 API（需要扩展 / 直连调试时）

认证 `POST {workspace}/decision/login`（JSON `{username,password}` → `data.accessToken`，**必须保留登录返回的 cookies**，否则被重定向到 CAS）；`workspace` 默认 `/webroot`。

| 功能 | 端点 | 方法 |
|------|------|------|
| 模板文件树 | `/decision/v10/templates/all[?keyword=&fileTypes[]=]` | GET |
| 模板定义 / 导出 | `/decision/view/report?reportlet=<path>&format=cpt|<pdf/excel/...>` | GET |
| 任务名列表 | `/decision/v10/schedule/task/names` | GET |
| 任务搜索/详情 | `/decision/v10/schedule/task/search` | POST `{taskName}` |
| 任务增/改 | `/decision/v10/schedule/task` | POST / PUT（PUT 体必须含 `id`；POST 建任务时带上 `creator` 才会写创建人） |
| 任务删除 | `/decision/v10/schedule/task/deletes` | POST **裸数组** `["<id>"]`（传 `{ids:[...]}` 会被拒；0.4.2 起 client 按裸数组发并校验返回值） |
| 立即执行 | `/decision/v10/schedule/task/{id}/once` | POST |
| 执行历史（只有 id） | `/decision/v10/schedule/task/log/info` | POST `{taskName}` |
| 执行记录 + 结果 | `/decision/v10/schedule/record/search` | POST `{taskName,page,perPage}` |
| 日志详情节点树 | `/decision/v10/schedule/task/log/details?taskLogId=<id>` | GET |
| 报表参数（官方） | `/decision/v10/report/template/paras?path=<path>` | GET |
| 远程设计握手 | `/decision/remote/design/check` | POST（返回 frontSeed/frontSM4Key/transmissionEncryption） |
| 远程设计取 token | `/decision/remote/design/verify` | POST 表单 `username` + **加密后**的 `password` |
| 远程设计 RPC | `/decision/remote/design/channel` | POST，body = gzip + Java 序列化 Invocation |
| 远程设计服务清单 | `/decision/remote/design/service` | POST 表单 `username`+`password` |
| 远程设计许可/版本 | `/decision/remote/design/vt`、`/version`、`/branch` | POST |
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

### 6.10 `format=cpt` 的响应字节不稳定，别用整体 hash 判断"模板有没有被改"

同一模板连续两次取定义，SHA256 就不同（实测 3 次三个值）。逐行 diff 后差异**只有 1 行**：

```
<![CDATA[org.apache.catalina.core.ApplicationMappingImpl@72d48284]]></O>
<![CDATA[org.apache.catalina.core.ApplicationMappingImpl@268f721c]]></O>
```

这是容器对象的 identity hash，每次请求都变（长度相同，所以文件大小看着不变）。

**判据**：要比对模板是否被改动，用**结构化比对** —— `<TableData name>` / `<Query>` / `<DatabaseName>` 的哈希，
不要用整文件 SHA256。`report download` 拿来 diff 时同理，先剔除这类易变行。

### 6.11 `schedule create` 的 YAML 怎么来（不重置输出 id 必失败）

平台的定时任务是一个嵌套对象（`triggerGroup` / `scheduleOutput` / `taskParameter` / `outputStr` …），
没有独立的建任务接口文档，**最省事的做法是拿一个现成任务当模板**：

```bash
frcli schedule get "参照任务名" -f json > src.json     # 完整详情
# 去掉只读字段：id / nextFireTime / preFireTime / editable / taskState / originTaskId
# 改：taskName、templatePath、taskDescription、scheduleOutput.baseName、taskParameter.param 的值
# 可选建议：creator（建任务时带上创建人；PUT 改不掉 creator，留空会让按创建人过滤的平台页面看不到）
# ⚠️ 必须重置：scheduleOutput.id、outputActionList[].id、outputActionList[].outputId
frcli schedule create new.yaml
```

- **不重置输出 id 的报错**（实测）：`detached entity passed to persist: com.fr.schedule.base.entity.ScheduleOutputEntity`
  —— 服务端把沿用源任务的 `ScheduleOutputEntity.id` 当新实体 persist，直接 200 + HTML 出错页。
  重置成新 UUID 后同一个 YAML 立刻建成功。
- **`taskState` 必须改成枚举整数**（实测 2026-10-28）：从 `schedule get` 原样复制的是对象 `{"value":0}`，
  create 会报 `Cannot deserialize instance of com.fr.schedule.base.type.TaskState out of START_OBJECT token`
  （200 + HTML 出错页）。0.10.24 起 CLI 会**自动规范化**：`taskState` 对象/数字串/布尔按语义归一成 0/1，
  其它值（如 2=已结束）直接报错而不是静默改成启用；同时自动剥离 `id`/`nextFireTime`/`preFireTime`/`editable`/`originTaskId`。
  手工载荷建议按此清理。
- `update`（PUT）只改了描述/参数这类字段时是安全的：PUT 会保留未动的字段（实测改 `taskParameter` 后
  `baseName` / `triggerGroup` / `outputActionList` 原样保留）；但它改不掉 `creator`。
- `create` 也支持「只执行一次」这类配置：`triggerGroup.triggers` 里 `triggerType:"1"` + `startType/endType:1`，
  建完 `taskState.value` 会是 `2`（已完成）。

### 6.12 自定义类输出（FeishuPushPlus10V2 等）的日志是**异步**写的

任务日志节点树里，`模板计算` / `导出cpr` / `导出pdf` 跑完就有，但**自定义类那一步（`自定义类附件处理`）
要等约 5 分钟才出现**——它包含导出 xlsx → 上传云空间 → 群发链接。实测同一任务：

| 运行 logTime | 前三个节点 | 自定义类附件处理（结束时间） |
|---|---|---|
| 14:35:49 | 14:36:23 / 14:36:29 / 14:36:34 | 14:40:47 |
| 14:45:16 | 14:45:46 / 14:45:52 / 14:45:57 | 14:50:10 |

所以**别因为当场看不到那一步就判定「任务没配自定义类 / 模板没生效」**：要么等几分钟重读 `schedule log`，
要么直接查推送结果（如帆软平台的 `system/weixin/推送日志.cpt`）。

### 6.13 「参数默认填什么」看 `report paras`，不是看参照任务

`frcli report paras <模板>` 返回的是**模板里存的默认参数值**（含类型 `Formula` / `String`），
建任务时「参数默认」就该用它——照抄参照任务的参数值可能错（参照任务的参数是它自己那份模板的默认值）。

例：`示例报表A.cpt` 的默认 `sdate` 是 **String `20260924`**（模板正文也写着「累计时间从20260924开始」），
而 `示例报表B.cpt` 的默认 `sdate` 是 **Formula 月首**。两张模板的参数名一样，值不能互抄。

### 6.14 从零创作模板（0.8.0 起）：`report new/cell/dataset/param/style/table/crosstab/highlight/page`

不用 Designer 也能造报表：**cpt 就是 XML**，`report new` 给骨架，其余命令按 A1 记法改。
完整语法、配方与验证方法见 **`references/cpt-authoring.md`**（那张表要照着它抄）。要点：

| 要记住的 | 真相（都实测过） |
|---|---|
| **数据设置（头号坑）** | 每个数据集列格都带 `<RG>`：**`--mode list`(默认)=原样展开 / `group`=相同值合并 / `summary`=按组聚合**。**不写 `<RG>` 服务端按「分组」处理**（去重、静默改数）→ 见 §6.15 |
| 扩展方向 | **`dir="0"` = 纵向、`dir="1"` = 横向**（写反不报错，只是表格长歪）→ `--expand v/h`；`--expand none` 时多值会被**逗号拼成一格** |
| 参数两套写法 | **数据集 SQL 只认 `${x}`；单元格公式只认 `$x`**；写错都不报错（`${x}` 会原样渲染出这 6 个字符） |
| 参数默认值 | **数据集 `<Parameters>` 与模板参数声明两处都要写**；没默认值时用户不带参数打开就是空白（导出照成功）→ CLI 给 warning |
| 验收 | **「导出成功」几乎没有验收价值**：列名/公式/样式索引写错，服务端一律照收、导出合法 xlsx（内容是空）→ 必须 openpyxl 逐格读回 |
| 本地已拦 | `dsName` 不存在、公式 `=1+`/括号不配对、`--style` 越界、数据集名空、残缺 XML（上传前良构校验）、**`--fn` 配非 summary / `--group-by` 配非 summary / 对值单元格设数据设置**；列名无法离线核对 → 出 note 提示 |
| 数字格式 | `<Style>` 里的 `<Format class="com.fr.base.CoreDecimalFormat"><![CDATA[#,##0]]>`；`report style --add --num-format` 或 `report cell --num-format` 一步生成 |
| 行列尺寸 | 列宽值 ÷ 280800 = 导出列宽（字符）；行高值 ÷ 44200 ≈ 行高（磅）；`FRFont size` 单位 **1/8 磅**（72=9磅） |
| 对齐码 | `horizontal_alignment`：**0=居中 / 2=左 / 4=右**（奇数被忽略，和直觉相反） |

```bash
export FRCLI_WRITE_SCOPE="demo_group/demo_user/临时"
R="demo_group/demo_user/临时/demo.cpt"
frcli report new "$R" --apply                       # 空白模板（2050B，自带可渲染骨架）
frcli report dataset "$R" --add ds1 --conn demo_conn \
    --sql "select 'A' code,1 cnt union all select 'B',2" --param topn=10 --apply
frcli report table "$R" --dataset ds1 --at A2 --columns code,cnt --header --apply
frcli report cell "$R" --at A1 --set-formula '="TOP" + $topn' --merge A1:C1 --apply
frcli report cell "$R" --list -f table              # 只读核对结构（含 ds_mode/ds_fn）
FRCLI_TIMEOUT=300 frcli export excel "$R" -o /tmp/demo.xlsx   # 再逐格读回才算验收
```

想按组出汇总（`地区/销售员/销量`）：

```bash
frcli report table "$R" --dataset ds1 --at A2 --columns 地区,销售员,销量 \
    --mode summary --group-by 地区,销售员 --fn sum --header --apply
# → 地区/销售员 = 分组（相同值合并），销量 = 汇总（自动 <Expand/>，不再按行扩展）
frcli report cell "$R" --at D2 --set-ds-mode list --apply      # 改已有格的数据设置
```

多 sheet 模板要给 **`--sheet 表名`**（缺省第一张；`--widths` 跟着 `--sheet` 走，列宽定位规则见 §6.20）：

```bash
frcli report table "$R" --sheet 明细表 --dataset ds1 --at A2 --columns code,cnt --header --apply
# sheet 名写错 → 报出全部现有 sheet 名（先 `report sheet --list` 看有哪些），不写盘
```

`report table` 会**整格改写**目标区域 —— 要留标题行就 `--at A2`（先写表再写 A1 会把表头盖掉）。
骨架也可以从现成模板裁：`report new "$R" --from <某张现成模板.cpt> --apply`（保留版面/样式表，清空内容）。

### 6.15 ⚠️ 缺 `<RG>` 的单元格 = 服务端按「分组」处理（会静默去重，合计对不上）

**这是我们的 bug，不是平台问题（2026-09 实测闭环）。**

**早期两条结论都已撤回**：① "xlsx 的聚合/合计值会静默出错" —— 不存在，实测 26 个变体 × 3 轮
**xlsx 与 csv 逐格全等，从无分歧**；② "同一模板不同时段导出 `4567.7 → 2345.6 → 4567.7`" ——
那是**读错行**（合计行渲染在数据之后的第 6 行，当时按模板坐标读了第 4 行）。

**真因**：`com.fr.report.cell.cellattr.core.group.DSColumn.getGrouper()` 在 `<RG>` 缺失时惰性返回
`new FunctionGrouper()`，而其 `divideMode` 初值 `0` = **分组** ⇒ 单元格被当作「分组」：
相同值合并、**数值列被去重**。明细 `10,10,20,10,30,30` 求和 = **110**（SQL 真值），
缺 `<RG>` 时塌缩成 `10,20,10,30`、合计 = **70** —— **3/3 轮稳定复现的静默算错**。

对照实验（同一数据集 `('A',10)('A',10)('A',20)('B',10)('B',30)('B',30)`，**只改 `<RG>`**，
`demo_group/demo_user/skill测试/dsmode/`）：

| 形态 | xlsx 逐格读回 |
|---|---|
| **无 `<RG>`** | `A/10, ''/20, B/10, ''/30`（4 行） |
| `<RG class="…FunctionGrouper"/>`（分组＝缺省） | **与"无 `<RG>`"逐格相同** ← 根因的直接证据 |
| `<RG class="…FunctionGrouper"><Attr divideMode="1"/></RG>`（列表） | 6 行全展开 |
| `<RG class="…SummaryGrouper"><FN>…SumFunction</FN></RG>`（汇总） | `A/40, B/70`（按组聚合） |

- 对策：① 写模板时 `<RG>` **必须显式写** —— `report table` 已改为默认 `--mode list`；
  ② 有默认值的字段，"标签不在"**不等于**"设置没有"，默认值未必是你要的那个；
  ③ **含合计/聚合的报表仍建议 xlsx × csv 双通道对**（通用戒律，与归因无关）；
  ④ 更稳的是把合计交给 `--mode summary` 或 SQL（`union all select '合计', sum(...)`）
- **复杂效果（分组小计/交叉表/条件属性/多数据集/参数联动/日期维度/公式实战）**：
  见 **`references/cpt-patterns.md`** —— 8 类配方，每条都有「XML 片段 + 等价 CLI + 逐格实测 + 坑」。
  三个最容易静默错的：① 同行的 `C3` 只是本行，整列合计要写 `C3[!0]`；
  ② 交叉表的**值格必须与列维度同列**，否则列维度消失、值被逗号拼成 `100,200`；
  ③ 条件属性里 `fg=` 与 `bold` 写同一条规则时字色会被 `FRFont` 覆盖（CLI 已自动并入）。
- 完整模型与语料普查见 `references/cpt-features.md` 与 `docs/探索/cpt服务端模型-逆向.md`；
  创作侧写法见 `references/cpt-authoring.md` §4.7 / §6.1


### 6.18 第二辑（图表/控件/钻取/分页）的验收通道与静默错

⚠ **判成败别只看管道后的 stdout**：**错误 JSON 走 stderr、成功走 stdout**，所以 `frcli … | jq` 会把错误吞掉（验证者本轮中过一次招）。要判成败看 **exit code**，或把 stderr 一起收（`2>&1`）。

**验收通道别用错**（用错通道 = 假阴性）：
行内数据 → **xlsx 逐格读回**；**图表** → `report image` 或 `export pdf` 出图看（**xlsx 里是嵌入图片
`xl/media/image1.png`，逐格读回永远是 0 个非空格**）；**页眉页脚/页码/重复标题行/分页** →
**`export pdf` + pdfium 出图看**（`report image` 不渲染分页结果）；**冻结** → 导出态本来就无差异，
只验 XML 往返 + 预览页。

| 静默错 | 真相 | 正确做法 |
|---|---|---|
| 图表分类列名写错 | `status: ok`、导出正常，**图照画但完全错**（无分类标签、各系列塌成一根柱、Y 轴刻度也变） | 列名必须逐格核对；`report chart --list` 能读回绑定 |
| 参数控件名 ≠ 参数名（含大小写） | 控件存在、`--list` 显示它，**不报错**；但**联动与否导出通道验不了**（控件名正确时默认导出同样是模板默认值） | 控件名必须与模板参数/SQL 里 `${同名}` 一致；**联动只能在预览页点一下验** |
| 超链接写成 `<HighlightList><Highlight><HighlightAction class="…HyperlinkHighlightAction">`（无 `<Condition>`） | **整张模板渲染成平台出错页**（xlsx/pdf 都是 3430B 出错页、**没有 detail-message**） | 用单元格级 `<NameJavaScriptGroup>`（`report link` 生成的就是它，语料 260 处都这样） |
| `<Footer>` 放错父节点（`<Report>` 下而不是 `<ReportAttrSet>` 内）/ `footerHeight="0"` | 导出正常、页脚**不出现**，不报错 | `<Header>/<Footer>` 与 `<ReportSettings>` 同级；高度必须 >0（CLI 会自动补 20 磅并提示） |
| 用 `report image` 验页脚/重复标题行 | 假阴性（image 是版面流） | 走 PDF + pdfium；重复标题行还要**先把表头加高**再比页数（矮表头只差 258B） |

其它硬事实：`SORT(C3)` 是**降序**（FR 英文/繁体帮助写升序是错的，实测 4/3/2/1）；`MOM/PROPORTION`
是语法糖（`MOM(A,B) ≡ IF(&A>1, B/B[A:-1], 0)`）；`!0` 是一个词法记号；**超链接在导出产物里什么都不留**
（xlsx 无 `<hyperlink>`、pdf 无 `/URI`）。

### 6.16 复杂报表的四个「静默错」（0.8.0 实测，逐格证据见 `references/cpt-patterns.md`）

| 现象 | 真相 | 正确做法 |
|---|---|---|
| 占比列每行都是 100% | 同一行里的 `C3` 只是**本行那一格**，`=C3/SUM(C3)` 分子分母相同 | 整列合计写 **`SUM(C3[!0])`**（`[!0]` = 该格扩展出的全部格子） |
| 交叉表值列变成 `100,200` 一串 | **值格没和列维度同列**（列维度就消失了，值只剩行父格） | 值格写在**表头行列维度那一列**的数据行；用 `report crosstab` 生成即可 |
| 条件属性的字色不生效 | `FRFontHighlightAction` 写的是**整个 FRFont**，会覆盖同一条规则里的 `ForegroundHighlightAction` | `fg=` 别和 `bold/size/font` 同规则手写；CLI 已自动把字色并进 `<FRFont foreground=…>` |
| `=SUM(SLICEARRAY(B3[!0],1,SEQ()))` 每行都得整列合计 | `SEQ()` 直接写进公式里不按行求值 | 先用一格写 `=SEQ()`，累计写 **`=SUM(SLICEARRAY(B3[!0],1,D3))`** |

配套两条：
- **函数名和求值上下文分别核对**：先用 `report functions NAME` 查基线，再用 `formula-check` 查基础语法。
  `RANK(value,array,order)` 是内置函数；某条 `RANK(B3,B3[!0])` 失败不能推断所有 RANK 都不可用。
  插件名称需另行核实，报表排名可选择 `SORT` 或在 SQL 中计算。详见 `references/formulas.md`。
  `report datasets` 的 `no function found: X` 是运行期解析错误，不是全部公式已正确求值的证明。
- **条件属性隐藏整行** = `--rule 'v<100:rowheight=0'`（服务端 `RowHeight` 行高 0），
  导出 xlsx 里那一行**整行消失**（不是行高变 0），抄官方 `doc/Primary/DetailReport/条件属性实现折叠树.cpt`。

### 6.17 分页、重复标题与页眉页脚

- **每页重复标题行**用 `report page --repeat-header-rows 起始:结束`，写入
  `<ReportPageAttr><HR F="起始" T="结束"/></ReportPageAttr>`。范围是 **0 基闭区间**，
  `0:0` 表示 Excel 第 1 行；表尾行、标题列和表尾列分别用
  `--repeat-footer-rows`、`--repeat-header-cols`、`--repeat-footer-cols`，范围记法相同。
- **页眉页脚内容可写**：`--header-text` / `--footer-text`；公式配合
  `--header-formula` / `--footer-formula`，页码变量为 `$$page_number` / `$$totalPage_number`。
  高度用 `--header-height` / `--footer-height`，单位是磅。
- `--repeat-rows` / `--no-repeat-rows` 修改单元格级 `CellPageAttr repeat`，使用 **1 基行号**，
  与报表级重复标题范围分开。该属性缺省为 true，不能据此判断是否配置了每页重复表头。
- `--freeze 列数,行数` 与 `--page-freeze on|off` 用于预览态冻结；在预览页滚动验收。
  页眉页脚、页码和重复标题通过 **PDF 分页结果**验收，`report image` 不能代替这一检查。

```bash
# 本地预览：第 1 行每页重复，并写页眉
frcli report page input.cpt --local --repeat-header-rows 0:0 \
  --header-text 日报 --header-height 20
# 写入新文件，再回读设置
frcli report page input.cpt --local --repeat-header-rows 0:0 \
  --header-text 日报 --header-height 20 --apply -o output.cpt
frcli report page output.cpt --local --list
```

完整配方、XML 与验收案例见 [配方二 W5](references/cpt-patterns2.md#w5-分页--重复标题行--页眉页脚页码--冻结)。


### 6.19b 批量导出支持「参数矩阵」（一个模板 × 多组参数 → 多份文件）

`export batch` 的 manifest 里，`params` 给**列表**就逐值各导一份；`output` 用 `{参数名}` 占位区分文件名：

```yaml
reports:
  - path: demo_group/demo_user/sales_monthly.cpt
    format: excel
    output: ./out/monthly_review_{edate}.xlsx
    params: {edate: ["20260430", "20260531", "20260630"]}
```

```bash
frcli export batch ./manifest.yaml     # → monthly_review_20260430.xlsx / _20260531.xlsx / _20260630.xlsx
```

实测：3 个月末各出一份，且每份内容里的 `$edate` 各自替换正确（`日期:20260430` / `0531` / `0630`）。
**注意**：单元格里引用参数要写 **`$edate`（公式）**，`${edate}` 只在**数据集 SQL** 里替换。

每条 `results`/`errors` 都带本次 **`params` 与 `output`**（`{参数名}` 已展开），失败条目因此能直接定位到是哪一项 ——
旧版错误条目只有 `report/format/error`，同一报表的多组参数失败时两条文案一模一样，只能靠文件 mtime 猜。
`total` 是**展开后**的任务数，manifest 条数看 `manifest_reports`（旧版 `total` 用 manifest 条数，
参数矩阵下会出现 `total:1` 而 `success+failed:6` 这种对不上的账）。

两个边界（0.10.3 起）：`params` 里给了**空列表** ⇒ 直接报 `EXPORT_ERROR` 并指明是哪个参数（旧版会静默丢掉这条报表，
`total: 0` + exit 0，看着像跑完了）；多条任务展开出**同一个 output 路径** ⇒ 顶层 `warnings` 数组给一条提示
（后写的会覆盖先写的，多半是 `output` 漏了 `{参数名}` 占位）。

### 6.19c 连接失败分三类：超时 / 被对端重置 / 本机代理（提示各不相同）

```
导出请求失败: The read operation timed out（当前超时 30.0s；复杂报表属正常，用 `FRCLI_TIMEOUT=600 frcli ...` 调大后原样重试，不要先怀疑报表或改参数）
导出请求失败: [Errno 54] Connection reset by peer（连接被对端重置/断开，这不是超时——调大 FRCLI_TIMEOUT 无效。同一命令原样重试通常即成功…）
请求失败: 503 Service Unavailable（本机 HTTP 代理链路故障：httpx.ProxyError 表示失败发生在「代理这一跳」…）
```

- **超时**：服务端还在算 → 调大 `FRCLI_TIMEOUT` 后原样重试。
- **被对端重置/断开**（`Connection reset by peer` / `broken pipe` / `RemoteProtocolError`）：服务端渲染大报表耗时较长时偶发掐断，
  **原样重试即成功**（实测：单条连试 3 次全被 reset，随后同一命令成功；批量 6 条里 2 条被 reset，单独重试即成功）。
  调大超时无效 —— 旧文案把 reset 归进"超时类"，用户按提示把 900→1200→1800 照样被 reset。
- **本机代理故障**（`httpx.ProxyError`；或 5xx 响应带 `Proxy-Status` 头）：失败发生在**代理这一跳**，不是平台，
  也不是超时。先查代理/VPN 链路与节点，`frcli server test` 也走同一代理、只能复核。
  CLI **不会自动绕过用户代理**；确要绕过请自己在 `NO_PROXY` 里排除平台地址。
  只认 `Proxy-Status`（RFC 9209）—— `Via` 平台侧网关也会加，拿它判定会把平台自身 5xx 误报成本机代理故障。

自动重试（0.10.3 起）：**只对幂等 GET/HEAD 重试 1 次**（POST/PUT/DELETE 不重试 —— 写操作重放有风险），
**超时与代理故障都不重试**（代理链路故障非瞬时，重发没有收益）。
重发次数记在客户端 `net_retries`，`export` / `export batch` / `server test` 的输出里可读（正常为 0）。

**远程设计通道同样分这三类**（`远程设计请求失败: …`）：超时提示指向 `FRCLI_RD_TIMEOUT`（不是 `FRCLI_TIMEOUT`），
被对端重置同样「原样重试」，代理故障同样点明「代理这一跳」（0.10.9 起；此前 RD 跳只返回裸异常原文）。

分类逻辑在 `src/frcli/neterr.py`（单一真源），**登录失败（`登录请求失败: …`）同样按这三类报**：
无 token 缓存时失败落在登录这一跳，不共用分类就会裸报 `503 Service Unavailable`，看不出是代理还是超时；
登录响应若是 **5xx + `Proxy-Status`** 也按代理故障报，不再是干巴巴的 `登录失败: HTTP 503`。
登录是 POST、链路故障通常也不是瞬时问题，**不自动重试**。

### 6.22 运行时巡检（`frcli inspect`）：内部触发计算 + 轮询，不让 agent 猜时间

`frcli inspect run` 对接平台的「模板性能分析」插件（`com.fr.plugin.ins`）：真实执行一次模板，
给出整体耗时、各环节计数/耗时与逐单元格耗时，用来定位慢模板/慢单元格。

**调用方只发一条命令**，等待逻辑全部在 CLI 内部（退避轮询，不让 agent 自己 `sleep` 猜结果好了没）：

```bash
FRCLI_TIMEOUT=300 frcli inspect run "demo_group/demo_user/x.cpt"               # 分页预览（page）
FRCLI_TIMEOUT=300 frcli inspect run "demo_group/demo_user/x.cpt" --op view     # 分析预览，含 db fetch
frcli inspect run "…/x.cpt" --params '{"edate":"20260131"}' --timeout 120      # 带模板参数 + 等待上限
frcli inspect status                                                          # 插件状态（只读）
```

**平台链路**（排查插件/接口问题时看；CLI 已封装）：

1. `GET …/decision/plugin/inspect/x/run?viewlet=<模板>&op=page|view` → 预览页壳，含
   `window.Nx.sid`（巡检会话）与 `sessionID=<模板会话>`；
2. `GET …/decision/view/report?op=page_content&sessionID=<模板会话>&pn=1` → **真正触发模板计算**；
3. 轮询 `GET …/decision/plugin/inspect/x/report/<巡检sid>` → `Nx.result = JSON.parse('<JS 转义串>')`。

坑：

- **只调第 1 步永远拿不到结果**：巡检会话停在 PREPARED，结果页报「检测未被触发」——必须第 2 步让模板真算一次。
- 结果里 `meta.para` 带**工号、组织、会话参数**；命令默认剔除（只给 `meta.date`），`--raw` 才原样输出。
- `op` 只允许 `page` / `view`；`write`/`write_plus` 是**填报写操作**，不开放。
- `--params` 只放**模板参数**；`op` / `viewlet` 是保留键，不会被 `--params` 覆盖（防止参数名撞车绕过白名单）。
- 模板计算本身受 `FRCLI_TIMEOUT`（默认 30s）；等待结果上限是 `FRCLI_INSPECT_TIMEOUT`（默认 60s）。
- 模板路径不存在时平台 `run` 返回 **200 + 空响应**（异常被吞、只进服务端日志）；命令会提示先用 `report info/list` 确认路径。
- 插件未安装/未启用时端点 404 或返回错误页；`inspect status` 的 `status` 码：
  `0` 正常 / `1` 部分检测点未生效 / `2` 关键点未生效 / `-1` 获取中 / `-2` 未知。

**结果怎么读（2026-10 实测，最容易被误读）**：

- `cell` 里某格的 `total` **包含「等待数据集返回」的墙钟时间**：触发取数的那一格，`total` ≈ `extra["db fetch"][数据集].cost`
  （实测 116,294ms vs 116,291ms）。看到「某格很慢」先别改 cpt —— 先看 `db fetch`，否则会把取数等待当成渲染开销，做一轮无效优化。
- `template-cost` = 总耗时；`Σ db fetch cost` = 取数；**差值才是渲染**。取数占大头就先优化 SQL（impala profile：`yh_bigdata olap sql history/profile`）。
- **数据集缓存开着时取数 0ms**（`db fetch` 全 0），性能数字假快；测性能前必须先关数据集缓存（`share`/`StrategyConfig`，frcli 无开关，需改 cpt XML）。
- `op=page` 没有 `db fetch`，要看取数耗时用 `--op view`。

### 6.22b 巡检 `db fetch` 里的 SQL 被平台截断为 500 字符

`inspect` 结果 `extra['db fetch'][数据集].sql` **只给前 500 个字符**（平台插件截断，不是 CLI 截；
实测 2026-10-24 有会话据此误判「SQL 没更新/上传没生效」，白查一轮）。核对完整 SQL 用
`report datasets <模板> --sql` 或 `report download` 读模板字节；命令检测到 500 字符会在 stderr 提示。

### 6.23 大报表性能排查：先分「取数 vs 渲染」，再谈 cpt 优化（别把取数等待当渲染）

大报表优化最常见的白干一轮：**没确认耗时归属就去改 cpt 公式/条件属性/合并/扩展**。实测（10 万级单元格的树形报表）
cpt 层改动（删公式、删过滤、去合并、去横向扩展）**全部无改善**，因为耗时是取数等待（`db fetch` 占 95%+）。

排查顺序：

1. **关数据集缓存再测**（否则取数 0ms 假快）。
2. 单 sheet 跑 `inspect run --op view --raw`：看 `template-cost`、`extra.db fetch`、`cell` 最大格。
   `cell 最大格 total ≈ db fetch cost` ⇒ 取数主导；差值才是渲染。
3. 取数主导 → 查 SQL：`yh_bigdata olap sql history -e impala` 拿 query_id → `olap sql profile` 取 impala profile →
   看扫描行数/字节、CPU、动态过滤到达时间、最大 cardinality；常见优化：把维度列内联进大 CTE 再聚合（避免亿行二次 join）、
   核实条件聚合是否扫了不需要的日期区间、维表提取为共享 CTE（通常只有几个百分点）。
4. **先查白算**：`dim_flag` 等维度档位是否全被使用（v7 93s 里 76% 白算在两个没用档位；砍档位 146s→22.7s，拆分不解决白算）。
5. 渲染确实占大头，再做 cpt 对照实验（一次只改一项，缓存关闭，配对测 3 轮取中位数；集群抖动极大）。
6. **拆分兜底**：按 sheet 拆成单 cpt，单次导出必须低于平台切断点（实测 ~443s，超时被掐断、exit 3）；拆分后仍受取数支配。
7. 验收：导出 xlsx 逐格对比基准（行/列/值，浮点容差 1e-9）；性能数字用配对中位数，不用单次值。

### 6.24 并发导出：0.10.16 起登录已跨进程串行（仍偶发链路 reset / 网关 504）

**0.10.16 起**：同一实例的多个 `frcli` 进程共用一把**实例级文件锁**（`~/.frcli/tokens/<实例>.json.lock`）：
缓存失效时只有第一个进程真正登录，其余进程等锁后复用同一份 token；认证失效重登前也会先看缓存里有没有
别的进程刚刷好的新 token。所以并发导出**不再因「各自登录、互相覆盖缓存」报 `AUTH_FAILED … 302`**。
等待锁上限 `FRCLI_AUTH_LOCK_TIMEOUT`（默认 30s；超时报错会指名这个变量）；token 缓存改为「临时文件 + 原子替换」。

仍要注意（与认证无关）：

- 并发导出仍可能偶发 `CONNECTION_ERROR … Server disconnected`（链路重置，原样重试即成功）与大报表网关 504
  （见 §6.1）；**批量导出仍建议串行**，主要是降低平台/网关压力，不是为了绕认证。
- 确认并发故障：串行重试成功 + `relogin: false` ⇒ 不是账号/权限问题。
- 0.10.15 及更早没有这把锁：并发导出会撞认证冲突，旧版只能串行或独立 `FRCLI_CONFIG`。
- 锁超时的错误码是 `AUTH_LOCK_TIMEOUT`（不是 `AUTH_FAILED`）；调 `FRCLI_AUTH_LOCK_TIMEOUT` 可加长等待。

### 6.19c0 会话巡检工具（`tools/scan_sessions.py`）

扫 `~/.dsh/sessions` 里**与本技能相关**的会话（只认真的调用过 `frcli` 的），列出用户诉求（⚠ 标记抱怨/纠正）与 frcli 调用的报错片段，用于找优化点。
`--date YYYY-MM-DD` / `--days N` / `--all` / `--json`；默认扫昨天。
按**记录时间戳**切窗口（会话会跨天延续，按文件 mtime 会漏）。

### 6.19d 模板被锁（`TplLockedException`）：最常见原因是**设计器开着那个文件**

写入走"占锁 → 写 → 释放"（`readAndLockFile` / `closeAndFreeFile`）。被锁住时报：

```
模板被锁，写不进去：<path>
**最可能的原因：有人在 FineReport 设计器里正开着这个模板**（很可能是你自己）。
   → 在设计器里关闭该模板（或退出设计器）后重试即可，锁随那个会话释放。
```

要点：
- **本工具无法跨会话解锁**。实测从另一个会话调 `closeAndFreeFile` / `userOut` / `userIn`
  都**返回 `true` 但锁仍在** —— 别被这类"成功"返回值误导。
- **已自动重试**：普通并发竞争会重试 3 次（约 5s）再报错；自动化里可设
  **`FRCLI_WAIT_LOCK=60`** 继续轮询等待（适合"等对方关掉设计器"）。
- **强杀客户端会留锁**：`Ctrl-C` / `timeout`（SIGINT/SIGTERM）时本工具会自动释放占着的锁；
  **`kill -9`（SIGKILL）无法捕获** → 锁留在服务端，同账号新会话也解不开，只能等超时或换文件名。
- 被锁时想继续干活：先把结果传到**新文件名**（如 `xxxV2.cpt`）绕过，等释放后再覆盖。

### 6.20 工作簿 sheet 管理：`report sheet`

`frcli report sheet <模板> --list | --add 名 [--clone-from 名] | --rename 旧 新 | --remove 名`
（默认 dry-run，`--apply` 才写）。`--add` **克隆已有 sheet 的版面骨架**（纸张/列宽都在里面）但清空单元格 —— 加「口径说明」页这类需求不用再手工拼 `<Report>` 块。

`--sheet 名` 也是 `report cell/highlight/table/crosstab/page/chart/link` 的**写入目标选择器**（多 sheet 模板用），
缺省写第一张；名字不存在一律报出全部现有 sheet 名，不静默落到第一张。
（唯一例外：`--widths` 走 `<ColumnWidth>`，不给 `--sheet` 时按**全文第一份存在的** `<ColumnWidth>` 定位 ——
正常模板每张 sheet 都有一份，第一张缺这个元素时才会落到后面那张；目标 sheet 没有真元素时报错，
不会误写单元格文本里的字面 XML。）

**「口径说明」页的内容规范**（业务向）见 `references/cpt-patterns2.md` §W3.7：
每个指标写全「统计范围 / 计算逻辑 / 数据来源与更新时点」；范围要写**可判定的语义**
（写「大区不为空」而不是「全部门店」）；不出现表名/字段名/SQL；指标口径改了说明页同批改。

### 6.21 启动器三坑（递归 / cwd / JSONDecodeError）

见 `AGENTS.md` 同名条目：`run.py` 递归护栏、启动器**不改 cwd**（否则相对路径写错地方）、平台出错页冒充 JSON 时不漏 `Expecting value`。

### 6.19 条件属性的两个静默坑（2026-09 由另一个会话暴露，均已修）

| 坑 | 症状 | 判据/对策 |
|---|---|---|
| **`bold` 不带 `size` → 字号 0** | `FRFontHighlightAction` 写的是**整个 FRFont**；缺 `size` 时服务端按 **0 号字**处理 ⇒ **值还在 xlsx 里但整行看不见**（实测 `font.size = 0.0`） | CLI 已修：无显式 `size` 时**继承目标格样式字号**、退 9 磅。**验收必须同时读 `font.size`**，只看值会误判正常 |
| **`--rule` 是「设置」不是「追加」** | 第二次调用**整表替换**该格原有规则（静默、无 warning、导出照样 ok）。真实事故：先设「隔行底色+负数标红」，最后一版只写「合计行加粗」，两条被无声冲掉 | CLI 已修：替换旧规则时给 warning（含条数）。要保留就写进**同一次调用的多个 `--rule`**（顺序即优先级） |

另外两条实战经验：
- **数据行样式作用到所有展开行** —— 给模板行套「加粗」= 每行都加粗 ⇒ **加粗只能用条件属性**（`ROW()=3` / 值条件 / 名单公式）。
- **`--at A3:B5` 只认已存在的格**：`report table` 只造**模板行**（A3/B3），展开出的 A4/B4 不存在 ⇒ CLI 会 warning「已跳过」。
  这是正常的：**规则挂在模板行上，展开行继承**，别为了"覆盖所有行"去写整片区域。

### 6.25 数据集预览：走远程设计 RPC，不是 REST `/v10/dataset/preview`

Designer 右键数据集「预览」的能力已封装成 `frcli report preview`：

```bash
frcli report preview "demo_group/demo_user/.../rpt.cpt" --dataset ds1 \
    --params '{"edate":"20260228"}' --rows 20 -f table
```

**机制**（`src/frcli/dataset_preview.py`）：远程设计通道调
`com.fr.data.operator.DataOperatorProvider.previewTableData(TableData, Map, int)`，服务端用
`EmbeddedTableData.embedify` 真实执行数据集查询，返回列名/列类型/前 N 行。参数是 Java 对象，
所以用一份**由平台自身 `ObjectOutputStream` 生成的 `DBTableData` 序列化骨架**，运行时只替换
连接名/SQL 两个字符串（Java 序列化自描述，改长度前缀即可）；**不写模板、不落临时文件**。
REST 的 `POST /v10/dataset/preview` 是**服务器数据集**的管理员接口，实测普通账号回
`Fine-Dec_Default_Error_Tip`，不要拿它做模板数据集预览。

**参数语义**：数据集 SQL 里的 `${x}` 是**文本替换**（与平台一致）。`--params` 没给全时 CLI
**直接报错并列出缺的参数名** —— 服务端缺参数会静默替换成空串，跑出空结果/错 SQL 才报错，更难查。
`report datasets` 只返回参数名不返回默认值，带参数据集必须显式传 `--params`。

**限制**：
- 只支持 SQL 数据集（有 `<DatabaseName>` + `<Query>`）；服务器数据集/存储过程/内建数据集请在
  Designer 或 `report serverdatasets/columns` 看。
- `-f table` 是给人看的：列数 >12 自动改用纵向布局（列清单 + 每行 `序号. 列名 = 值`）；`--rows` 很大时
  输出会很长，拿数据请用 `-f json`（或减小 `--rows`）。
- `--rows` 1–1000（默认 100），服务端只取前 N 行；预览会真实执行 SQL，复杂数据集可能几十秒到几分钟。
  预览是**两跳**：先 `report datasets`（REST，吃 `FRCLI_TIMEOUT`，默认 30s，复杂模板会先在这里超时），
  再远程设计 RPC（吃 `FRCLI_RD_TIMEOUT`，默认 300s）—— 两个都要按需调大。
- 返回的单元格统一为字符串（类型在 `columns[].type` 里）；`null` 与空串都显示为空串。
- 需要账号有远程设计权限（与 `report download/upload` 同一通道）；连接不存在报
  `错误代码:31300013 找不到数据连接:<name>`，SQL 报错带 `11300001` + 平台原文。
- 骨架是**平台 10.0.0 的 Java 序列化结构**（SUID/字段固定）。若平台大版本升级后预览报
  `InvalidClassException`，说明服务端类结构变了：需要重新生成骨架（`dataset_preview._TABLE_DATA_SKELETON`），
  不是 SQL/连接问题。
- `--params` 的 `null` 按空串替换；布尔等非字符串值用 Python `str()`（`True`/`False`），SQL 里要 `'true'` 请直接传字符串。

### 6.26 改定时任务的模板路径：先 pause，再 update --template，最后 resume

平台**没有**"改任务模板"的 REST 字段语义文档，但实测可行且必须按顺序做：

```bash
frcli schedule get "demo_任务名" -f json > /tmp/task_backup.json   # 先备份整个任务
frcli schedule pause "demo_任务名"                                 # 暂停（生产变更，先停再改）
frcli schedule update "demo_任务名" --template "demo_group/…/新模板.cpt"
frcli schedule resume "demo_任务名"                                # 验证无误后恢复
frcli schedule run "demo_任务名"                                   # 可选：用真实任务参数试跑一次
```

**平台语义（2026-10-24 真机对照）**：

- `taskState.value`：**0 = 启用，1 = 暂停**。
- 切状态接口是 `POST /decision/v10/schedule/task/{id}/state`，但它是**切换**不是设置：
  body 里的 `value` 被忽略，每次调用把状态取反。CLI 的 `pause/resume` 会先读状态、按需切一次、再回读校验
  （重复调用是幂等的，不会来回切）。
- `PUT /decision/v10/schedule/task` **会重置任务状态为启用**：所以改完模板/描述后，若原来是暂停，
  必须再切回暂停（`schedule update` 已自动处理并在输出里给 `paused_state_restored`）。
- `PUT` 的请求体里**必须带 `creator`**：实测剔除 `creator` 后平台会把创建人落库为空
  （`update_schedule` 已改为回传；命令层再校验 before/after，被清空直接报错）。
- `PUT` 里 `taskState` 传对象 `{"value":1}` 会报 `Cannot deserialize TaskState out of START_OBJECT`；
  传数字也会被忽略——状态只能走上面那个切换接口。
- 任务搜索 `task/search` 只认**任务名**（且是子串模糊搜索）；传 taskId 会静默返回 `{}`。`schedule get` 会自动用
  `task/listAll` 反查出任务名（该列表只含**本人创建**任务；其它命令仍以任务名为准，`delete` 才用 UUID）。
- 实测还存在 **taskState=2**（抽样 7/40，nextFireTime 为空、疑似已结束/停止）：切状态接口对 2 的语义未知，
  `pause/resume` 直接拒绝；`update` 也拒绝（PUT 会把状态重置为 0，可能把已结束任务静默重新启用）。
- `--template` 会先用 `templates/all` 校验路径存在（只认 cpt、排除目录）：平台接受任意路径并回 `success`，不校验会把任务静默指向坏模板/目录。
- `update` 的 PUT 后回读失败（按 id/名字都读不到）不会误报 creator：报「更新已提交但回读失败、状态未知」；
  若原为暂停会尽力恢复一次。恢复暂停失败时报当前实际状态并给出人工 `schedule pause` 命令。

### 6.27 报表数值对账：先对齐用户看的是哪一页/哪一区，再用加权平均不变量定位混口径

真实会话（折价日报，10-26）：用户报「大区折价占比都比全国小很多」。先在 MTD 页用最新导出与 SQL 验算，15.91% 完全一致——但用户看的是**昨日页**；真正的 bug 在昨日页大区占比区：分子绑 `sales_qty_zj_td`（数量）、分母绑 `sales_amt_td`（金额），数量÷金额只有 1% 量级；MTD 页是金额÷金额（正确）。别先用「数据没问题/你的预期不对」结案。

对账顺序：

1. **先对齐口径轴**：用户看的是哪个 sheet（昨日/MTD）、哪一区域（汇总/大区/自营联营）、哪组参数日期、哪份文件（旧导出 mtime）。把截图数值先与导出文件逐项对上，再谈对错。
2. **占比类先验不变量**：各分组按分母加权平均必须等于总体（本次各大区加权 15.92% ≈ 全国 15.91% 通过；某组 1% 而总体 19% ⇒ 几乎必然是分子分母混口径/引用错列）。
3. **读模板绑定，不要猜导出值**：`report download` 后解析 `<C c= r=>` 的 `columnName`/公式，比较同一指标在不同 sheet/区域的绑定是否同口径（数量列、金额列混用是本次真因）。
4. 修绑定用 `report cell --at ... --bind ... --apply`（模板被设计器占用会报锁，先让用户关 Designer）；**改绑口径必须同步改表头文字**（本次 O4/P4 表头仍写「销售量」、实际绑金额）。
5. 改数据集 SQL：先独立 SQL 对拍，再 `report dataset --set-sql`，改后回读 + 导出核对；`select *` 的 CTE 里重命名同名列会被 Impala 拒（`duplicated inline view column alias`），要显式列；显式列会改变 TOP-N 商品池，结果有 0.0x% 级变动要主动向用户说明。
6. **改单个指标口径时只动目标指标**：同一数据集/SQL 里其它指标（尤其毛利率等派生比率）保持原口径；真实会话（10-29）用户指出「毛利率不应该发生变化」——agent 把新口径的过滤条件连带套到了毛利率。改完用基线导出**逐指标对拍**：除目标指标外全部应一致，比率类还要确认分母没有被连带替换。

### 6.28 从「含同名 .py 的目录」运行 frcli：cwd 会遮蔽标准库

真实会话（10-27、10-30 两次）：`cd /tmp && frcli export ...` / `cd /tmp && frcli schedule record ...` 启动即抛 Traceback ——
`click/core.py` 里 `import inspect` 命中了 `/tmp/inspect.py`（别的任务留下的临时脚本），Python 把 cwd 放进 `sys.path` 最前，
当前目录里与标准库/依赖同名的 `.py` 会抢先命中。0.11.2 起 `python -m frcli`（含 PATH 里的 `frcli` shim）会在导入 click 前
把运行目录从 `sys.path` 移除，这类启动 Traceback 不再出现；`python -m frcli.cli` 等非标准入口仍可能踩到。
注意有下限：若被遮蔽的是**解释器启动阶段**就要导入的模块（`types.py`/`re.py`/`traceback.py`/`enum.py` 等），
Python 启动即失败，任何入口层修复都救不了——这类临时脚本必须改名或换目录；临时脚本仍建议放 `/tmp/<任务名>/` 并清理。

- 现象：任何 frcli 命令都崩；Traceback 从 site-packages（`click/core.py`）跳进**当前目录**的同名文件。
- 处理：换到干净目录运行（仓库根/家目录），或重命名、删除 cwd 里的 `inspect.py` / `json.py` / `types.py` / `click.py` 等。
- 预防：临时脚本不要用标准库模块名；集中放 `/tmp/<任务名>/` 子目录，用完清理。

### 6.29 本地 Demo：检索、设计画像、提炼设计技巧与聚合块检查

本地 `reportlets` 内的 CPT 可离线检索和解析，不读取实例配置，也不启动服务。设计任务按下面走：

```bash
# 1. 找模板：路径关键词或 XML 原文
frcli report local-examples "<reportlets目录>" --keyword 分栏
frcli report local-examples "<reportlets目录>" --contains PolyWorkSheet -n 30

# 2. 找同类代表样板：--tag 可传原型或技术标签
frcli report local-profile "<reportlets目录>" --tag grouped-table -n 10
frcli report local-profile "<reportlets目录>" --keyword 销售 --tag chart-linkage -n 10

# 3. 读完整设计画像与具体格号
frcli report local-inspect "<reportlets目录>/<样例>.cpt" --design
frcli report local-inspect "<reportlets目录>/<样例>.cpt" --sheet "<sheet名>" --cells -n 200
frcli report local-inspect "<reportlets目录>/<样例>.cpt" --sheet "<sheet名>" --block 2 --cells

# 4. 本地模板看数据集 SQL（不触发服务端校验；大模板比线上 datasets 快）
frcli report local-inspect "<reportlets目录>/<样例>.cpt" --sql
```

画像覆盖：`archetype/archetypes`（明细、分组、交叉、图表分析、主从、驾驶舱、填报、聚合、静态版面）、
`layout`、`data`、`visual`、`interaction`、`charts` 与 `study_points`。`local-profile` 同时返回
`archetypes`、`techniques`、`chart_types` 分布和 `design_lessons`；样例按 `study_score` 排序，
按标签检索时先要求目标结构完整，再优先规模小、附带控件/脚本/多 sheet 较少、容易逐格复盘的样板；
目标技术出现足够次数后不再无限加分，超大综合模板不会仅因能力多而排在最前。
`score_semantics` 明确该分数只是检索排序分，不是设计质量分；`matched`/`truncated` 与
`skipped_count` 用来判断是否查全。

用户问“这张报表应怎样设计/选什么图表/如何组织页面”时，不要只返回文件列表：

1. 先确认决策、读者、数据粒度、交互和交付渠道；读
   `references/cpt-design-from-examples.md` 的原型选择矩阵。
2. 选 3–5 个同类样板：基准、信息增强、高密度、交互、目标渠道各一份；高复杂度样例不天然更合适。
3. 用 `--design` 比较整份结构，用 `--cells` 对照分组/扩展/汇总、样式索引、条件属性个数等结构信息（数字格式/链接/图表的具体实现需读该格 XML 或导出对照，别只看画像下结论）。
4. 提炼 3–7 条可复用规则，并明确哪些业务字段、SQL、参数、品牌和特例阈值不复制。
5. 映射到 `report new/dataset/param/table/cell/style/crosstab/highlight/page/chart/widget/link`；
   具体配方查 `cpt-patterns.md` / `cpt-patterns2.md`。
6. 结构回读、数据对账、预览交互和导出产物分别验收；XML 画像不能代替任何一项。

**线上大模板读取慢的离线快路径**：`report datasets --sql` 由服务端全量解析模板，数 MB / 几十个数据集的
模板实测 **10 分钟级甚至超时**（2026-10-29 真实会话：1.8MB 模板等了 11 分钟只能 kill；`report info` 也超时）。
先 `report download "<模板>" -o /tmp/x.cpt` 拿模板原始字节，再 `report local-inspect /tmp/x.cpt --sql`
离线看 `<TableData>/<Query>` 里的 SQL——不触发服务端校验，秒级返回；只想看数据集名时
`report edit "<模板>" --list`（读模板字节）也很快。不要反复调大 `FRCLI_TIMEOUT` 重试或据此判定平台不可用。

`PolyWorkSheet` 的 `Block` 有各自的单元格和坐标，两个块都可以有 `A1`；普通 `report cell/table`
网格命令在未明确块时拒绝操作，避免误报为零格。0.11.0 起 `cell/table/crosstab/highlight/page/chart/link`
可用 `--sheet S --block N` 操作已支持的网格块，`row/column/range` 也按块执行。
跨块引用、非网格块及未覆盖结构明确拒绝。远端模板可先 `report download` 到本地检查。
示例的结构只证明 XML 写法；渲染、交互和导出效果仍需在合适的环境验证。
检索和聚合块细节见 `references/cpt-local-examples.md`；设计选型、视觉、交互、渠道和验收规则见
`references/cpt-design-from-examples.md`。

### 6.30 定时任务「首次运行」与推送配置：`schedule run` 与页面 ▶ 是同一个接口

真实会话（10-28）：用户担心「之前用 frcli 首次运行任务，导致后续配不了推送群」，要求只用浏览器点 ▶。实测对照确认：
网页 ▶ 与 `frcli schedule run` 都调用 `POST /decision/v10/schedule/task/{taskId}/once`，**不修改任务配置**；
推送管理里的文件行由**任务成功跑完**自动登记，与触发方式无关。首次运行后到「推送管理」按文件名找到行再配群即可。

- 任务没跑过 → 推送管理里搜不到文件名（正常，不是配置失败）；首次运行会先推兜底群 `[推送]未分类报表群`，配好群后改推目标群。
- 推送管理页面每页只显示 10 条、翻页按钮可能不可用 → 「搜不到」先排除分页/加载/筛选，不要判定行没生成。
- 配群操作：群配置格**点两下**才出下拉箭头；选完群**直接点提交**（点空白会清空选择）；提示登录失效需重登后重配。
- 用户对工具路径有疑虑时，先给证据（接口对比/执行记录）再决定用哪种触发方式；`schedule run` 本身不会破坏推送链路。

### 6.31 经营分析平台的 cpt 不要用 frcli 读：无接口权限，改用元数据表反查

**经营分析平台**（与决策平台是两套实例）的模板与决策平台实例不互通：`report datasets` 报
「当前账号无此接口权限（该接口需管理员）」、`report download` 报 `REPORT_NOT_FOUND`、`report list` 看不到目录——
**都不是 CLI 故障**。查这类模板的取数口径改用平台元数据反查模板 SQL（内部表名/字段与查询模板
见本地知识库，不在本仓库记录）；目标模板当天记录为空时查同目录姊妹模板。
0.10.23 起 `report list`/`report ws-list` 空结果会在 stderr 提示「可能无权限」，`report datasets/download`
撞权限/找不到时也会提示改用元数据表；别把空结果当成「报表不存在」。

### 6.32 函数检索、基础语法与公式默认值

以下能力从 frcli / skill **0.10.26** 起提供，两者使用相同版本号。

`report functions` 随包提供 180 个实现类和 3 个数据集方法的目录；`report formula-check`
检查单双引号、转义与括号配对，并提示未知函数和上下文依赖。两条命令均离线运行，
不加载实例，不执行公式；返回 `runtime_verified: false`。当前实例的插件和自定义函数另行核对。

动态默认值使用 `report param --set-formula p=EXPR`、`report widget --default-formula EXPR`，
或 `report edit --dataset D --param p --default-formula EXPR`。静态值与公式互斥，
`--default` 即使以 `=` 开头也保持文本。🔴 加 `--apply` 写入前仍须确认目标影响并满足写范围。
模板参数、数据集参数和控件默认值属于不同作用域；控件命令默认同时更新同名模板参数。
函数选择、完整命令与验收步骤见 **`references/formulas.md`**。

## 7. 故障排查

| 现象 | 处理 |
|------|------|
| `frcli: command not found` | 按 `references/install.md` 自举：`python <base>/references/run.py <命令>` 或 `cd <base>/src && python -m frcli <命令>`（零安装） |
| `这是聚合报表（PolyWorkSheet）` | 先用 `report local-inspect TEMPLATE.cpt --cells` 确认块序号与类型；0.11.0 起支持网格块的编辑命令须明确 `--sheet S --block N`（N 为 1 基序号）。支持命令及非网格块、跨块引用等边界见 §6.29 与 [结构编辑手册](references/cpt-structure.md) |
| `导出产物魔数不符` / `导出被服务端排队` | 服务端返回的是出错页或 `Dec-Waiting_In_Line` 排队页；重试一次通常即成功，批量要降并发（§6.1） |
| `读取报表数据集 xxx失败: 错误代码:11300001 数据集 [y] 配置错误…` | 该模板里有坏数据集，平台原文已给出**坏数据集名 + SQL 报错**；这是报表本身的问题，不是 CLI 故障（§6.5） |
| 导出 `status: ok` 但文件打不开 | 内容其实是 HTML 出错页面：核对魔数，报错里已带平台原文的 `detail-message`（§6.1） |
| `导出产物是平台出错页…平台原因: 错误代码:11300002…` | 宽表走默认分页导出所致：加 `--params '{"extype":"simple"}'` 改原样导出后重试（§6.1） |
| `导出产物是平台出错页…平台原因: 很抱歉，数据量过大触发保护机制…` | **平台内存保护**（不是格式问题）：先缩小查询数据量/分批导出；`extype=simple` **不解除**该保护；管理员可在 智能运维-内存管理-模板限制 调整上限（§6.1） |
| `…The read operation timed out`（导出、或 `report info/datasets/paras` 读模板） | 设 `FRCLI_TIMEOUT=300`（批量 600）重跑；复杂模板冷启动 50s 级，读取也会打空（§6.2） |
| `远程设计请求失败: …`（`report upload/delete/download/cell/table/…`、`report new --from/--apply` 等走远程设计的命令） | 超时用 **`FRCLI_RD_TIMEOUT`**（默认 300，不是 `FRCLI_TIMEOUT`）；被对端重置原样重试；代理故障查代理链路（§6.2 / §6.19c） |
| `No such command 'x'` / `No such option: --y` | 命令树以 `frcli --help` 与 `<命令组> --help` 为准。常见误猜：顶层没有 `record`（用 `schedule record`）、没有 `help`（用 `--help`）；`system info` 不存在（用 `system version` / `system health`）；**报表路径是位置参数**，不是 `--path` |
| `请求失败: …Connection reset by peer` / `broken pipe` | **不是超时**：原样重试即成功（批量里失败的那几条单独重试）；调大超时变量无效（§6.19c） |
| `请求失败: 503 Service Unavailable（…本机 HTTP 代理链路故障…）` | 失败在**本机 HTTP 代理这一跳**（`httpx.ProxyError`），不是平台故障：查代理/VPN 与节点；`server test` 走同一代理，只能复核（§6.19c） |
| `schedule list` / `report list` 返回 `[]` | 认证失效（可能未过期）：0.1.1 起自动重登一次；仍为空则手动 `rm -f ~/.frcli/tokens/*.json`（§6.4） |
| `server test` 报 ok 但列表全 `[]` | 旧版假阳性（只查本地缓存，真发请求）；`relogin: true` 表示这回检测到失效并重登过（§6.6） |
| `未配置任何 FineReport 实例` | `frcli server add ... --set-default` |
| `实例 'x' 不存在` | `frcli server list` 看可用实例；配置搜索顺序：`$FRCLI_CONFIG` → `~/.frcli/config.yaml` → `./.frcli.yaml` |
| 登录时卡住不动 | `server add` 没带 `-p`，改为带密码重建实例 |
| `report datasets` 返回 `[]` | 该报表数据集在服务端报错，报表本身是坏的（§6.5） |
| `本地内容不像 cpt 模板（前 600 字节没有 <WorkBook>）` | 你手里的文件来自 `format=cpt`（旧 `report download`）而不是模板本体；重新用 `report download` 取，别加 `--allow-format` 硬写（§6.7） |
| `download 报「不在账号的远程设计授权目录内」` | 新 `report download` 走远程设计通道，需要该路径的远程设计授权；服务端对无授权路径返回 **0 字节**而不是报错（§6.7） |
| `Upload 后回读不一致` | 该路径不在账号的远程设计授权目录内，服务端**静默跳过写入**；找管理员加授权，或换有权限的目录（§6.7） |
| `TplLockedException` / 写模板报锁 | 模板正被别的 Designer 打开（占锁中）；让对方关掉或等锁过期（§6.7） |
| `任务不存在: xxx` | `schedule get/run/update` 用准确任务名（先 `schedule list`） |
| `schedule delete` 删不掉 | 传 UUID `id` 而非任务名（§6.6）；0.4.2 起会按裸数组删并校验，旧版报 `deleted: true` 也可能是假成功 |
| `schedule create` 报 `detached entity passed to persist: ScheduleOutputEntity` | YAML 沿用了源任务的 `scheduleOutput.id`/输出 action id，换成新 UUID（§6.11） |
| 任务跑完日志缺「自定义类附件处理」 | 那一步是异步的，约 5 分钟后才写日志，别据此判定配置没生效（§6.12） |
| `schedule update` 报「任务名不完全匹配」/「模板不存在」/ 状态非 0/1 | 平台 task/search 是子串模糊搜索→写命令要求精确任务名；`--template` 先校验路径存在；taskState 2（已结束）拒绝自动改（§6.26） |
| `schedule pause/update/resume` 后状态不对 | 平台切状态接口是**切换**（每次取反）且 PUT 会重置为启用；`schedule update` 已保留原暂停态，`pause/resume` 幂等。详见 §6.26 |
| `schedule history -n 1` 拿到的不是最新一次 | 返回按时间**升序**，`-n 1` 是最早那条；放大 `-n` 取最后一条，或改用 `schedule record`（§6.6） |
| `report preview` 报「数据集 SQL 缺少参数」/「找不到数据连接」/`11300001`/`InvalidClassException` | 分别是：`--params` 没给全（CLI 会列出缺的名字）、连接名失效、SQL 报错（带平台原文）、预览骨架与平台版本不兼容（§6.25） |
| `report paras` 返回 `[]` | 该报表没有参数 **或路径不存在**（平台对不存在的路径也返回空）；先用 `report list <目录>` 核对路径 |
| `API_ERROR: Required String parameter ...` / `请求方法不支持` / `无此接口权限` | 直接调底层接口时的平台原文，按提示补参数/换方法/换账号（§6.9） |
| `API_ERROR: 平台返回错误页（无详细信息）` | 多为对象不存在：`schedule log` 的 logId 必须来自 `schedule history <任务名>`（`<任务名>_same_fire_<时间戳>`），record/records 的 uuid/id 不能用；过期则用 history 重新取（§6.6） |
| `AUTH_FAILED: 重新登录后仍被重定向到登录页` | 密码错、账号被锁或无权限；检查 `~/.frcli/config.yaml` 里的密码与网络 |
| 请求被重定向到 CAS / 返回登录页 HTML | token 失效：CLI 自动重登一次；仍失败检查密码或网络（§6.4） |
| 对比 .cpt 整体 hash 发现「模板被改了」 | `format=cpt` 响应字节不稳定（内嵌容器 identity hash），改用结构化比对（§6.10） |
| HTTPS 证书校验 | 客户端默认 `CERT_NONE` + legacy renegotiation，自签证书可直接用；`FRCLI_CA_CERT` 指向 CA 文件（当前实现下不改变校验行为） |

> 命令清单以 `frcli <命令组> --help` 为准；本文件与 CLI 不一致时，先以 `--help` 为准并回写本文件。
