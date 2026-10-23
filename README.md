# fanruan_v10

FineReport V10（帆软决策平台）CLI 工具 **`frcli`** 与其 agent skill **`fanruan-v10`** 的同一份源码仓库 —— skill 与 CLI 同源，`src/frcli/` 是唯一源码，不存在副本同步问题（结构仿 `yh-bigdata`）。

- **Skill 名**：`fanruan-v10`（入口 `SKILL.md`；**必须小写字母/数字/连字符**，带下划线会被宿主静默丢弃）
- **命令**：`frcli`
- **源码**：`src/frcli/`
- **版本**：0.10.16（0.9.0 起：`crosstab`/`highlight`/`page` + `cpt-patterns.md`；0.10.0 起：`chart`/`widget`/`link` + `cpt-patterns2.md`；0.10.13 起：`inspect` 运行时巡检/模板性能分析；0.10.14 起：导出撞 502/503/504 网关超时给出可操作提示；0.10.15 起：`schedule log` 传错 logId 来源给出来源提示；0.10.16 起：并发导出登录跨进程串行（实例级文件锁））

## 安装 / 自举

```bash
pip install -e .                 # 开发安装（src 布局）
frcli --version

# 或零安装直跑（未装/不在 PATH 时）
cd src && python -m frcli --version
python references/run.py --version        # 跨平台启动器
```

完整自举手册见 `references/install.md`。

## 快速开始

```bash
# 1. 配置实例（密码明文落在 ~/.frcli/config.yaml；agent 必须带 -p，否则交互式提示会卡住）
frcli server add yh --url https://<服务器> -u <工号> -p '<密码>' --set-default
frcli server test

# 2. 找报表（目录要具体；`/` 会拉全量，数千条，随时间增长）
frcli report list "demo_group/demo_user/dept_a/dept_b" -f table

# 3. 看参数与取数口径
frcli report paras "demo_group/demo_user/dept_a/dept_b/sales_daily.cpt"   # 官方参数接口（含派生参数公式）
frcli report datasets "demo_group/demo_user/dept_a/dept_b/sales_daily.cpt" --sql -f table

# 4. 导出（只传驱动参数；复杂报表务必调大超时）
FRCLI_TIMEOUT=300 frcli export excel "demo_group/demo_user/dept_a/dept_b/sales_daily.cpt" \
    -o /tmp/sales_daily_20260731.xlsx --params '{"edate":"20260731","extype":"simple"}'

# 5. 校验产物（必做：导出「成功」也可能是 HTML 出错页面）
python3 -c "print('OK' if open('/tmp/sales_daily_20260731.xlsx','rb').read(4)==b'PK\x03\x04' else '坏文件')"

# 6. 批量导出
#   manifest.yaml:
#     reports:
#       - path: demo_group/demo_user/dept_a/dept_b/sales_daily.cpt
#         format: excel
#         output: ./out/sales_daily_20260731.xlsx
#         params: {edate: "20260731", extype: simple}
FRCLI_TIMEOUT=600 frcli export batch manifest.yaml

# 7. 定时任务（读）
frcli schedule list -f table
frcli schedule get "demo_user_销售_示例概览by月_飞书"        # 拿 UUID id
frcli schedule history "demo_user_销售_示例概览by月_飞书" -n 5      # 升序返回，最后一条才是最新；返回 id 即 logId
frcli schedule record "demo_task_超时明细" -n 20                  # 执行记录 + 结果（分页，带 total）
frcli schedule log "demo_task_超时明细_same_fire_1000000000000"   # 日志节点树，定位哪一步失败
#   ⚠️ log 的参数是 history 返回的 id（<任务名>_same_fire_<ts>）；record/records 的 uuid/id 是执行记录 id，不能用

# 7.1 定时任务（写，🔴 先确认）：create / update / delete <UUID> / run <任务名>
#   新建任务：用 schedule get 派生 YAML（去掉只读字段 + 换 taskName/baseName + 重置 scheduleOutput.id
#   与 outputActionList 的 id/outputId，建议带上 creator），再 frcli schedule create new.yaml
#   —— 细节与「detached entity」坑见 SKILL.md §6.11
#   delete 的参数是 UUID（不是任务名）；body 为裸数组，0.4.2 起返回值会被校验

# 7.2 改服务端模板内容（🔴 生产写，先确认影响范围）
#   平台 REST 没有写模板内容的接口；frcli 走 Designer 的「远程设计」通道（见 SKILL.md §6.7）
frcli report ws-list "demo_group/demo_user"                    # 看服务端真实目录（只读）
frcli report download "demo_group/demo_user/临时/a.cpt" -o a.cpt   # 取回模板原始字节（与服务器逐字节相同）
#   ……本地改 a.cpt……
frcli report upload a.cpt "demo_group/demo_user/临时/a.cpt" --force
#   写前自动占锁（别人 Designer 开着则拒绝）+ 备份原文件到 ~/.frcli/backups/ + 回读 SHA256 校验
frcli report delete "demo_group/demo_user/临时/a.cpt" --force      # 移入回收站，可恢复

# 7.3) 写范围：0.6.0 起**默认拒绝** —— 没设范围就必须显式 --any-path
export FRCLI_WRITE_SCOPE="demo_group/demo_user/临时"   # 推荐：限定范围
#   之后 report upload / delete / edit --apply 越界（含 ../ 穿越、兄弟目录）一律拒绝
#   单次放行：frcli report upload a.cpt "别的目录/a.cpt" --force --any-path

# 7.4) 从零创作模板（0.8.0 起）：new / cell / dataset / param / style / table
#      + crosstab（交叉表/动态列） / highlight（条件属性） / page（分页设置）
#   全部默认 dry-run（打印可读 diff + bytes_before/after），加 --apply 才写；
#   语法与配方见 references/cpt-authoring.md；**8 类复杂报表配方见 references/cpt-patterns.md**
#   （分组小计/交叉表/条件属性/多数据集/参数联动/日期维度/分页/公式实战，每条都有逐格实测证据）
R="demo_group/demo_user/临时/demo.cpt"
frcli report new "$R" --apply                       # 空白模板（自带可渲染骨架）
frcli report dataset "$R" --add ds1 --conn demo_conn \
    --sql "select 'A' code,1 cnt union all select 'B',2" --param topn=10 --apply
frcli report table "$R" --dataset ds1 --at A2 --columns code,cnt --header --apply
#   数据设置（<RG>）默认 list（记录原样展开）；不写 <RG> 服务端按「分组」去重、会静默改数
frcli report table "$R" --dataset ds1 --at A4 --columns 地区,销售员,销量 \
    --mode summary --group-by 地区,销售员 --fn sum --header --apply
frcli report table "$R" --sheet 明细表 --dataset ds1 --at A2 --columns code,cnt --apply
#   多 sheet 模板用 --sheet 选写入目标（缺省第一张；cell/highlight/table/crosstab/page/chart/link 都吃它）
frcli report cell "$R" --at D3 --set-ds-mode list --apply
frcli report cell "$R" --at A1 --set-formula '="TOP" + $topn' --merge A1:C1 --apply
frcli report cell "$R" --list -f table              # 只读：A1/值/公式/绑定/ds_mode/扩展/样式
frcli report style "$R" --add --num-format "#,##0" --bold --border --apply
frcli report param "$R" --add topn=10 --apply       # 模板参数（公式里的 $x 靠它给默认值）

# 7.4.1) 三类复杂效果（各自一条命令）
frcli report chart "$R" --at A1 --dataset ds1 --type column --category 地区 --series 产品 \
    --value 销量 --fn sum --title "销量对比" --show-title --apply   # 图表（导出 xlsx 是嵌入图片）
frcli report widget "$R" --param 地区 --type combo --options 华东,华南 --default 华东 --apply
frcli report link "$R" --at A3 --to "别的报表.cpt" --param center='=$A3' --apply  # 钻取（预览态）
frcli report crosstab "$R" --dataset ds1 --at A3 --row 地区 --col 产品 --value 销量 \
    --agg sum --total-row --total-col --apply       # 交叉表：列数随数据自动增长
frcli report highlight "$R" --at C3 --rule 'v>1000:bg=#FFC7CE,fg=#9C0006,bold' \
    --rule 'ROW()%2=0:bg=#F2F2F2' --apply           # 条件属性（规则按顺序生效，后覆盖前）
frcli report highlight "$R" --at C3 --list          # 只读回看规则
frcli report page "$R" --freeze 1,0 --header-height 30 --apply
frcli report cell "$R" --at A3 --bind ds1.d --ds-result "FORMAT(TODATE(\$\$\$,'yyyyMMdd'),'yyyy年MM月')" --apply
frcli report cell "$R" --at A4 --set-formula "=SUM(C3)" --expand-left A3 --apply   # 组内小计挂父格
#   验收必须逐格读回（写错列名/公式/样式索引，服务端照样导出"成功"）

# 8. 附件（服务器附件缓存，非报表目录）
frcli attach upload /tmp/说明.docx --name 说明.docx   # → 返回 attach_id
frcli attach remove default1789441975426_Olw7l        # 用完清理
```

## 运行时巡检（模板性能分析）

> 结果解读：`cell` 的耗时**包含等待数据集取数**（触发取数那格 ≈ `extra.db fetch`）；取数 vs 渲染怎么拆、性能排查顺序见 SKILL §6.22/§6.23。

```bash
frcli inspect status                     # 插件状态：检测点是否生效（只读）
# 真实执行一次模板，输出整体/环节/单元格耗时；等待由 CLI 内部完成（退避轮询），不用自己 sleep
FRCLI_TIMEOUT=300 frcli inspect run "demo_group/demo_user/dept_a/dept_b/sales_daily.cpt" --op page
FRCLI_TIMEOUT=300 frcli inspect run "…/sales_daily.cpt" --op view --params '{"edate":"20260131"}'
```

`run` 默认输出会剔除 `meta.para`（工号/组织/会话参数），`--raw` 才原样输出；`op` 只允许 `page` / `view`（`write` 是填报写操作）。

## 命令组概览

| 命令组 | 用途 | 主要命令 |
|--------|------|----------|
| `server` | 多实例配置 | `list` / `add` / `remove` / `set-default` / `test` |
| `report` | 报表模板 | `list` / `info` / `paras` / `datasets` / `download` / `serverdatasets` / `columns` / `authed`（模板认证配置路由，非权限树，见下）/ `upload`🔴 / `delete`🔴 / `ws-list` / `fonts` / `versions` / `image` / `edit` / **创作**：`new` / `cell` / `dataset` / `param` / `style` / `table` |
| `export` | 报表导出 | `pdf` / `excel` / `word` / `image` / `csv` / `batch` |
| `attach` | 服务器附件 | `upload` / `remove`（附件缓存，不动报表目录） |
| `system` | 系统与平台信息 | `version` / `health` / `modules` / `authority` / `login-policy` |
| `inspect` | 运行时巡检（模板性能分析，真实执行一次模板） | `status` / `run`（`--op page\|view`，内部等待结果） |
| `entry` | 平台条目与消息 | `list` / `roots` / `all` / `messages` |
| `user` | 用户与组织 | `list` / `me` / `departments` / `posts` |
| `schedule` | 定时任务 | `list` / `tasks` / `get` / `exists` / `executing` / `create` / `update` / `delete` / `run` / `history` / `record` / `records` / `log` / `setting` |

> ⚠️ `report authed` **不是**「当前账号有权限的模板树」：它读的是模板**认证(authentication)配置**路由
> （`/decision/v10/report/templates/all/authentication`），实测**恒返回 `[]`**（HTTP 200 的原始响应即 `{"data":[]}`），
> 与账号有没有权限无关。枚举有权限的模板树用 `report list`（平台已按权限过滤）；空结果的提示打在 **stderr**，stdout 仍是合法 JSON。

完整命令树、参数语义与安全分级见 **`SKILL.md`**；`frcli <命令组> --help` 是最终事实来源。

全局选项：`-i/--instance NAME` 指定实例，`-v/--verbose`，`--version`。多数查询命令支持 `-f json|table`（默认 json）。

## 输出与退出码

CLI 输出为 JSON（`-f table` 为表格），便于 agent 解析：

```json
{"status": "ok", "action": "export", "format": "excel", "report": "...", "file": "/path/to/report.xlsx", "net_retries": 0}
```

`net_retries` 是连接层错误自动重发的次数（只对幂等 GET 生效，正常为 0）。
`export batch` 的 `results`/`errors` 每条带本次 `params` 与已展开的 `output`；`total` 是**展开后**的任务数（manifest 条数见 `manifest_reports`）。
`export batch` 另有顶层 `warnings` 数组（正常为 `[]`）：多条任务展开出同一个 `output` 路径时提示会互相覆盖（多半是 `output` 漏了 `{参数名}` 占位）。
参数矩阵的 `params` 给了**空列表**时，`export batch` 直接报 `EXPORT_ERROR` 并点名是哪个参数（exit 1），不会静默跳过该报表。

错误输出到 stderr：`{"status": "error", "error": {"code": "AUTH_FAILED", "message": "..."}}`

退出码：`0` 成功、`1` 业务错误、`2` 配置错误、`3` 连接错误。

## 配置与认证

- 配置搜索顺序：`$FRCLI_CONFIG` → `~/.frcli/config.yaml` → `./.frcli.yaml`
- token 缓存：`~/.frcli/tokens/<实例>.json`（默认 24h；认证失效——401/403 **或 302→CAS 登录页**——自动清缓存重登一次）
- 环境变量：`FRCLI_TIMEOUT`（秒，默认 30；覆盖 REST 导出与 `report info/datasets/paras` 等读模板命令）、`FRCLI_RD_TIMEOUT`（秒，默认 300；覆盖走远程设计通道的命令：`report download`、`report image`、改模板类 `upload/delete/new/cell/...`；`FRCLI_TIMEOUT` 对它无效）、`FRCLI_INSPECT_TIMEOUT`（秒，默认 60；`inspect run` 等待巡检结果上限，模板计算本身仍受 `FRCLI_TIMEOUT` 约束）、`FRCLI_AUTH_LOCK_TIMEOUT`（秒，默认 30；并发进程等待同一实例登录锁的上限）、`FRCLI_CA_CERT`（CA 证书路径）、`FRCLI_CONFIG`

```yaml
default: yh
instances:
  yh:
    url: "https://<服务器>"
    username: "00000000"
    password: "xxx"          # 明文存储
    workspace: "/webroot"
```

## 目录结构

```
fanruan_v10/
├── SKILL.md              # agent 入口：命令树 / 安全分级 / 实测坑点 / 故障排查
├── README.md             # 本文件（人类可读）
├── AGENTS.md             # 开发规范（CLAUDE.md / CODEBUDDY.md 为软链）
├── pyproject.toml        # 打包定义（src 布局）
├── src/frcli/            # CLI 唯一源码
├── references/
│   ├── install.md        # 自检 + 自举手册
│   ├── cpt-authoring.md  # 模板创作手册（命令 + XML 语法 + 配方 + 坑点）
│   ├── cpt-patterns.md   # 第一辑：8 类复杂报表配方（分组小计/交叉表/条件属性/多数据集/参数/日期/公式）
│   ├── cpt-patterns2.md  # 第二辑：图表/参数控件/钻取超链接/层次坐标/分页（含"写错的对照"与验收通道矩阵）
│   ├── cpt-features.md   # cpt 语料普查（1602 个官方模板频次 + 片段 + 默认值 + 对照表）
│   ├── cpt-xml.md        # cpt 结构速查（定点字节读写）
│   ├── remotedesign.md   # 远程设计 RPC 协议（写模板的底层）+ 复核手册
│   ├── run.py            # 跨平台启动器（自举 + 软链自愈 + 版本提示）
│   ├── run.sh            # Unix 便捷入口
│   └── frcli             # 软链 shim（PATH 中的 frcli 指向它）
└── tests/                # pytest
```

## 已知限制

- 0.8.0 起可**从零创作**模板（`report new/cell/dataset/param/style/table` +
  `crosstab` 交叉表 / `highlight` 条件属性 / `page` 分页设置，见 `references/cpt-authoring.md`
  与 `references/cpt-patterns.md`）；0.5.0 起 `report upload` / `report delete` 走远程设计通道。仍有的限制：
  - 单元格支持值/公式/数据集列/合并/样式/扩展/条件属性/`<Result>` 表达式/HTML 渲染；
    图表、填报控件、页眉页脚**内容**仍需 Designer（`report page` 只读写高度与冻结列）
  - 「每页重复标题行」= 报表级 `<ReportPageAttr><HR F="起" T="止"/></ReportPageAttr>`
    （`report page --repeat-header-rows 1:1`；实测加高表头后 PDF 3 页 → 7 页）；
    页眉页脚页码用 `report page --footer-text '"第 " + $$page_number + " 页"' --footer-formula`
  - 组内排名 `RANK()` 在本安装求值失败（渲染 `#NAME?`）→ 排名写在 SQL 里；
    `ACCSUM`/`COUNTD`/`DATEFORMAT` 等函数名不存在（写了整张模板渲染不出来）
  - 列名无法离线核对（要连库才知道）：写错不报错、只会渲染出空列，验收必须逐格读回
  - 账号必须被授予「远程设计」权限且覆盖目标目录；无权限时服务端**静默跳过写入**，靠回读校验兜底
  - 模板被其他 Designer 打开（占锁）时拒绝覆盖
  - `delete` 是移入服务端回收站，不是物理删除
- 无 `query` 命令（早期 README 遗留）：要看数据集 SQL 用 `report datasets`
- 导出遇到报表侧错误（数据集 SQL 报错、缺参数）时返回 HTML 出错页面且 HTTP 200，CLI 仍报 `status: ok` —— 必须校验文件魔数
- 认证失效不返回 401，而是 302 到 CAS 登录页；`schedule list` / `report list` 的 `[]` 优先怀疑认证（0.1.1 起自动重登并复验，仍失败才报 `AUTH_FAILED`）
