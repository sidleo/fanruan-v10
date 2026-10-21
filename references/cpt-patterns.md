# 复杂报表配方集（8 类配方 · 全部真机逐格验收）

> 这份文件的每一条都满足：**在服务器上建出来 → 导出 → 用 openpyxl 逐格读回 → 记录真值**。
> 命令都在 `demo_group/demo_user/skill测试/patterns/` 下真跑过（服务器 FineReport V10，2026-09）。
> 读法：要**抄配方**看 §1–§8；要**知道 CLI 能干什么**看 §9；要**避坑**看每节的「坑」和 §10。

## 0. 动手前先看这 6 条（都是这一轮踩出来的）

1. **先验证实验装置，再下结论。** 本轮三次"看起来是平台的问题"，其实都是实验自己坏了：
   ① 我把表头行当成数据行（`report table --at A3 --header` 后**数据从 A4 开始**，我却把条件属性挂在 A3）；
   ② union all 各分支列类型不一致（`'v01'` vs `7`）→ Impala `Incompatible return types`；
   ③ 用了不存在的函数名（`ACCSUM`/`DATEFORMAT`）→ 整张模板渲染不出来。
   **判据**：拿不到预期结果时，先跑 `frcli report datasets <模板>`；
   它报 `11300001 数据集配置错误` + 平台原文 + SQL 位置 ⇒ **问题在 SQL/公式**；
   它干净而导出仍失败 ⇒ 才是版面/渲染层的问题。
2. **`report table --at A<n> --header` 之后，数据行是 `A<n+1>`**；条件属性/公式/合计都要按**渲染后的坐标**挂，
   不是按你心里想的坐标。读回时也一样。
3. **`<RG>` 必须显式写**（`report table` 默认 `--mode list`）：不写 = 服务端按「分组」去重，数值列静默算错。
4. **「导出成功」不是验收**。凡是有默认值/依赖外部（列名、类型、函数名）的设置，导出后**逐格读回**；
   含合计/聚合的还要 **xlsx 与 csv 双通道对**。
5. **静态文本里的单个 `\` 会让整格静默变空**：`report cell --set-value` 把内容**原样**写进 XML，
   转义由服务端吃 —— 实测 `地区\销售员/产品`、`C:\data\file`、单独的 `\` **导出后整格是空的**，
   `a\tb` 变成 TAB、`a\b` 变成 `a?`。**要写反斜杠必须写两个**（`地区\\销售员/产品` → `地区\销售员/产品`）。
   数据集 SQL 里的字符串**不受影响**（`'a\b'` 码点原样）。⇒ 角标/路径这类文本，验收时**必须读回那一格**。
6. **官方模板当脚手架**：`<FineReport 安装目录>/webapps/webroot/WEB-INF/reportlets/` 下 1602 个官方 .cpt
   （只读）几乎每种效果都有现成样例 —— `grep` 找片段比从零猜快一个数量级。
   本轮 §2 的交叉表、§3 的隐藏行、§6 的日期公式都是从官方模板抄出来的。

复现环境：

```bash
export PATH="/opt/homebrew/bin:$HOME/.local/bin:$PATH"
export FRCLI_WRITE_SCOPE="demo_group/demo_user/skill测试"   # 写操作 fail-closed，必须先设
export FRCLI_TIMEOUT=300                                     # 默认 30s 对复杂报表必然超时（REST 导出/读数）
export FRCLI_RD_TIMEOUT=600                                   # 远程设计通道（改模板/report download 等）的超时，与 FRCLI_TIMEOUT 无关
cd <本项目目录>
frcli() { PYTHONPATH=src <venv>/bin/python -m frcli "$@"; }   # 或 pip install -e .
B="demo_group/demo_user/skill测试/patterns"                        # 本配方集的样例目录
```

逐格读回的通用工具（后文每节都用到）：

```bash
frcli export excel "$B/xx.cpt" -o /tmp/xx.xlsx
frcli export csv   "$B/xx.cpt" -o /tmp/xx.csv        # 有合计/聚合时必做
<venv>/bin/python - <<'PY'
import openpyxl
ws = openpyxl.load_workbook('/tmp/xx.xlsx').active
print("dims:", ws.dimensions, "merged:", [str(m) for m in ws.merged_cells.ranges])
for r in range(1, 12):
    print(r, [ws.cell(row=r, column=c).value for c in range(1, 6)])
PY
```

---

## 1. 分组报表 + 组内小计 + 总计 + 占比

**效果**：`中心 / 销售员 / 金额 / 占比` 明细按中心分组，每个中心下面一行「小计」，表尾一行「总计」，占比是行值 ÷ 全局合计。

**样例**：`patterns/r1_group_subtotal.cpt`（数据 5 行字面量 union all：SC04 100/200/300、SC03 400/500）

**配方（等价 CLI，逐条真跑过）**

```bash
R="$B/r1_group_subtotal.cpt"
frcli report new "$R" --apply
frcli report dataset "$R" --add ds1 --conn demo_conn \
  --sql "select 'SC04' center,'张三' sales,100 amt union all select 'SC04','李四',200
         union all select 'SC04','王五',300 union all select 'SC03','赵六',400
         union all select 'SC03','钱七',500" --apply
# 建表：表头 + 逐列绑定 + 纵向扩展。**这一步不能少** —— 少了它后面所有坐标都没格子可改，
# 且导出仍然 status:ok（静默出坏报表）。
# ⚠️ **必须 --mode group**：维度列在分组模式下"每个不同值展开一次"，
#    下面 --expand-left A3 的小计才会**每个分组一行**；用默认 list 会变成"每行一个小计"（见坑 0）。
frcli report table "$R" --dataset ds1 --at A2 --columns center,sales,amt \
  --header --labels "中心,销售员,金额" --mode group --apply
# 占比：**分母必须写 [ !0 ]**（见坑 1）
frcli report cell "$R" --at D3 --set-formula '=C3/SUM(C3[!0])' --num-format '#0.0%' --apply
# 组内小计：A4/C4 用**显式左父格 A3** 挂到分组上
frcli report cell "$R" --at A4 --set-value "小计" --expand-left A3 --apply
frcli report cell "$R" --at C4 --bind ds1.amt --set-ds-mode summary --fn sum \
  --expand none --expand-left A3 --apply
# 总计：公式写在数据区**下面**，区间会自动伸展
frcli report cell "$R" --at A5 --set-value "总计" --apply
frcli report cell "$R" --at C5 --set-formula '=SUM(C3)' --apply
```

**XML 关键片段**（`<Expand>` 的父格属性就是"小计行"的全部秘密）

```xml
<!-- 组内小计行：leftParentDefault="false" + left="A3" ⇒ 跟着 A3 的每个分组各来一行 -->
<C c="2" r="3">
<O t="DSColumn"><Attributes dsName="ds1" columnName="amt"/><Complex/>
<RG class="com.fr.report.cell.cellattr.core.group.SummaryGrouper">
<FN><![CDATA[com.fr.data.util.function.SumFunction]]></FN></RG><Parameters/></O>
<PrivilegeControl/>
<Expand leftParentDefault="false" left="A3"/>
</C>
```

**实测导出（xlsx 逐格读回，与 csv 逐格一致）**

```
merged: ['A3:A5', 'A7:A8']  dims: A2:D10
2  ['中心', '销售员', '金额', None]
3  ['SC04', '张三', 100.0, 0.0667]      ← 100/1500
4  [None,   '李四', 200.0, 0.1333]
5  [None,   '王五', 300.0, 0.2   ]
6  ['小计', None,   600.0, None  ]      ← 100+200+300
7  ['SC03', '赵六', 400.0, 0.2667]
8  [None,   '钱七', 500.0, 0.3333]
9  ['小计', None,   900.0, None  ]      ← 400+500
10 ['总计', None,  1500.0, None  ]      ← 600+900
```

**坑**

0. 🔴 **组内小计 = 维度列必须是「分组」模式，否则你会得到"每行一个小计"**（实测，两种都 `status: ok`、都不报错）：

   | 维度列模式 | 导出结果 |
   |---|---|
   | `--mode group` ✅ | `A3:A5` 合并（SC04 三行）、`A4=小计 600`、`A7:A8` 合并、`A9=小计 900`、`A10=总计 1500` |
   | 默认 `--mode list` ❌ | **无合并**；`SC04/张三/100`、`小计 100`、`SC04/李四/200`、`小计 200` … 小计跟着**每一行**走 |

   成因：`--expand-left A3` 让"小计行"挂到 A3 这个父格上；**父格展开几次，小计就出现几次**。
   分组模式下 A3 每个不同中心展开一次 → 小计每组一行；列表模式下 A3 每行展开一次 → 小计每行一行。

1. **同一行里的 `C3` 只是本行那一格**：`=C3/SUM(C3)` 得到 **100%（每一行都是）**，不报错。
   要"整列合计"必须写 `C3[!0]`（FineReport 的扩展集合语法），或引用数据区外的合计格。
2. **小计/总计行不会自己出现**：`summary` 数据设置只决定"怎么聚合"，**位置靠父格**。
   不写 `--expand-left` 时，汇总格只在整表末尾出现一次。
3. 合并是引擎自动做的（`A3:A5` = 明细行合并、`A7:A8` 同），不用手写 `--merge`。
4. 合计行会在数据区下方**自动下移**；模板里按第一条明细的行号写公式即可。

---

## 2. 交叉表 / 动态列（行维度 × 列维度 × 值）

**效果**：`地区 × 销售员` 纵向、`产品` 横向、值取 `amt`；列数随数据自动增长，缺失组合留空，右侧行汇总、底部列总计。

**样例**：`patterns/r2_crosstab.cpt`（2 产品基线）、`patterns/r2_crosstab_agg.cpt`（同交叉点多记录对照）

**机制**（Lead 实测 + 本轮复现）：**不需要显式父子格** —— 引擎自动把「最近的上方扩展格」当列父格、
「左侧扩展格」当行父格。四类格：

| 位置 | 内容 | XML 形态 |
|---|---|---|
| 表头行、列维度列 | 列维度（横向扩展） | `FunctionGrouper` + `<Expand dir="1"/>` |
| 数据行、行维度列 | 行维度（纵向扩展） | `FunctionGrouper` + `<Expand dir="0"/>` |
| **数据行、列维度同列** | **值格（交叉点）** | `FunctionGrouper` + `<Expand/>` |
| 数据行、列维度右边一列 | 行汇总 | `SummaryGrouper`+`<FN>SumFunction` + `<Expand/>` |
| 总计行 | 列总计 | 公式 `=SUM(<值格>)` |

**一条命令造出来**

```bash
frcli report crosstab "$B/r2_crosstab.cpt" --dataset ds1 --at A3 \
  --row dist,sales --col prod --value amt \
  --total-row --total-col --label "地区/销售员 · 产品" --apply
```

**实测导出（xlsx 逐格，csv 一致）**

```
dims: A3:E8   merged: ['A3:B3','A4:A5','A6:A7','A8:B8']
3  [None,  None,   'A',   'B',   'amt汇总']
4  ['东区','张三', 100.0, 200.0,  300.0 ]
5  [None,  '李四', 300.0, 400.0,  700.0 ]
6  ['西区','张三', 500.0, 600.0, 1100.0 ]
7  [None,  '李四', 700.0, 800.0, 1500.0 ]
8  ['总计：', None, 1600.0, 2000.0, 3600.0]
```

**动态列实测**：只把 SQL 里的产品从 2 个换成 4 个（A/B/C/D，并故意制造稀疏组合）：

```
3  [None,None,'A','B','C','D','amt汇总']
4  ['东区','张三',100,200,250,None, 550]
5  [None,'李四', 300,None,None,450, 750]
6  ['西区','张三',None,600,650,None,1250]
7  [None,'李四', 700,800,None,None,1500]
8  ['总计：',None,1100,1600,900,450,4050]
```

- 列数 5 → 7 自动撑开，**版面不用改**；
- 缺失的 (行,列) 组合**留空**，不串位、不补 0；
- 列总计按列汇总（A=100+300+700=1100 ✓）、行汇总按行（550 ✓）、总计 4050 = 逐行之和 ✓。

**坑（本轮的三个"静默错"都在这）**

1. **值格必须与列维度同列**。我第一版把值格放在列维度**右边**、又在数据行给列维度补了一格，
   结果列维度消失、值格只剩行父格，导出成 `100,200`（逗号拼接字符串）。
   判据：`report cell --list` 里**表头行那一格应该是 `ds.列 + h`**，数据行同一列才是值格。
2. **同一个 (行,列) 交叉点有多条记录时，默认（分组）会静默错**：

   | 模式 | 东区/张三 的 A 列（真值 100+50+50=200） | 缺失组合 | 总计 |
   |---|---|---|---|
   | 默认 `FunctionGrouper` | **`100,50`**（拼接字符串，去重） | 空 | **150**（错） |
   | `--agg sum`（SummaryGrouper） | **200** ✓ | **`0`**（不是空） | 270 ✓ |

   ⇒ 交叉表的正确姿势是 **让 SQL 先在 (行,列) 粒度上聚合**（`group by` 三个维度），
   这样默认模式就够了；`--agg sum` 能修数值，但会把空格变成 `0`（业务上"没有数据"和"0"是两回事）。
3. **动态列顺序 = 数据首次出现顺序，不是排序**（Lead 在生产数据上实测列序 `12,13,11,10,98,14,15`）。
   要固定/自定义列序用 `DSColumn` 的 `<SortFormula>` —— **已实测闭环，不是待验证**：
   `<Complex order="1" reselect="true"/>` 单独写即按本格值**升序**；
   再加 `<SortFormula><![CDATA[if($$$="B",1,if($$$="A",2,3))]]></SortFormula>`
   （位置：`<RG>` 之后、`<Parameters>` 之前）→ 实测列序 **B, A, C** 生效，值与标签**不串位**；
   后续 `report cell` 写操作**不会抹掉**它。
   ⚠️ CLI **未暴露**该开关（只能 download → 改 XML → upload）；
   完整记录与可用模板片段见 `docs/探索/cpt服务端模型-逆向.md` §5.6.0 与 `docs/验证/证据/配方复现/`。
4. **0 行数据**：版面与合并都保留，汇总格 = `0`（不是空）—— 与坑 2 的 `0` 同源。
5. 多指标（`--value a,b`）：本 CLI **明确拒绝**（不猜版面）；要多指标请手工加第二个值格（竖排 + 行维度 `rs` 合并）。

---

## 3. 条件属性 `<Highlight>`（阈值标红 / 热力图 / 隔行变色 / 隐藏整行）

**样例**：`patterns/r3_highlight.cpt`（标红+绿色+隔行）、`r3c_hide_row.cpt`（隐藏整行）、
`r3b_databar.cpt`（字符条/HTML 色块）

**一条命令一组规则**（规则**按顺序生效，后面的覆盖前面的** ⇒ 宽规则放前面、特例放后面）

```bash
# 阈值多段（热力图）：>300 红 / <100 绿，再叠一层隔行灰（放第一条，被后面的覆盖）
frcli report highlight "$B/r3_highlight.cpt" --at C3 \
  --rule 'ROW()%2=0:bg=#F2F2F2' \
  --rule 'v<100:bg=#C6EFCE,fg=#006100' \
  --rule 'v>300:bg=#FFC7CE,fg=#9C0006,bold' --apply
# 整行（作用于一片区域：A3:C3 一次挂三格）
frcli report highlight "$B/r3_highlight.cpt" --at A3:B3 --rule 'ROW()%2=0:bg=#F2F2F2' --apply
# 整行隐藏：行高 0
frcli report highlight "$B/r3c_hide_row.cpt" --at A4:B4 --rule 'v<100:rowheight=0' --apply
# 只读回看
frcli report highlight "$B/r3_highlight.cpt" --at C3 --list
```

**条件语法**：`v` + 比较符开头 = 值比较（`ObjectCondition`+`Compare`），其余一律当**公式**：

| 写法 | 生成 | 说明 |
|---|---|---|
| `v>300` / `v>=0.7` / `v!="-"` / `v==null` | `ObjectCondition` + `<Compare op="2/3/1/14">` | `op` 取值：0 `==`、1 `!=`、2 `>`、3 `>=`、4 `<`、5 `<=`、10 包含、12 in、14 为空、15 不为空 |
| `ROW()%2=0` / `$$$>0` / `$B3>1000` | `FormulaCondition` + `<Formula>` | 语料里最常用（1405 处）；`$$$` = 当前格值 |

**动作语法**：`bg=#RRGGBB` / `fg=#RRGGBB` / `bold` / `italic` / `size=12` / `font=宋体` /
`rowheight=0`（0=隐藏整行；`20`=20 磅；`720000fu`=服务端原始单位） / `value=公式` / `border`。

**实测导出（openpyxl 读 `fill.fgColor.rgb` / `font.color.rgb`，数据 100/350/500/80/260）**

```
3 C:100.0  bg=-      fg=-       bold=0     ← 100 不小于 100，无规则命中
4 C:350.0  bg=FFC7CE fg=9C0006  bold=1     ← >300 命中（且覆盖了同行的隔行灰）
4 A/B      bg=F2F2F2                        ← 隔行变色只挂在 A/B 列
5 C:500.0  bg=FFC7CE fg=9C0006  bold=1
6 C:80.0   bg=C6EFCE fg=006100  bold=0     ← <100 命中（覆盖隔行灰）
7 C:260.0  bg=-      fg=-       bold=0
```

**隐藏整行实测**：`r3c_hide_row.cpt` 数据 100/350/500/80/260，规则 `v<100:rowheight=0`，
导出 xlsx 里 **80 那一行整行消失**（行数 5 → 4，`dims` 从 A3:B8 变 A3:B7）—— 不是行高变 0，是**没有这一行**。

⚠️ **只对渲染通道生效**：行高是版面属性，所以 **xlsx / pdf / image 里那行没了，但 `export csv` 里数据还在**
（实测量例自身即如此：xlsx `A3:B7` 无 80，csv 仍有 `SC05,赵六,80` 那一行）。
双通道验收时这是**预期差异**，别当 bug；**"隐藏"不等于"过滤"**，要真过滤得用数据集 SQL 或 `<Condition>`。

**坑**

1. **`fg=` 与 `bold/size/font` 写进同一条规则时字色会丢**（实测：`bg=…,fg=…,bold` 导出后只剩加粗、无字色）。
   原因：`FRFontHighlightAction` 写的是**整个 FRFont**，会把单独一条 `ForegroundHighlightAction` 覆盖掉。
   ⇒ CLI 已内置修正：同时有字体动作时把字色并进 `<FRFont foreground=…>`；
   手写 XML 时**不要**同时写这两个动作。
2. **规则顺序 = 优先级（后覆盖前）**；隔行变色这类宽规则必须放第一条，否则会盖掉阈值颜色。
3. 条件属性挂在 `<C>` 的子元素 `HighlightList` 上，**位置在 `Widget` 之后、`Expand` 之前**；
   一个格子只有**一个** `HighlightList`，多条规则都塞在里面。反复对同一格 `--apply` 会**整体替换**（不是追加）。
4. **`RowHeightHighlightAction` 空元素 = 行高 0**（服务端 `writeXML` 只在行高 > 0 时才写 `<RowHeight i>`），
   所以"隐藏"在 XML 里看起来就是这个动作**没有子元素** —— 直接抄官方
   `doc/Primary/DetailReport/条件属性实现折叠树.cpt` 的写法。
5. **官方那套"图形化进度条"（HTML `<table>`）在本服务器的 image/xlsx 两个通道都渲染不出来**
   （`r3b_probe` 实测：`<table>` 出空白、`<div style=background-color>` 只出文本）。
   能用的替代是**字符条**（见下）或 `<font color>` 上色。

**数据条（在 image/png 里真的看得见、xlsx 里也有值）**

```bash
# 字符条：xlsx 与 png 都有（■/█ 直接是文本）
frcli report cell "$R" --at C4 --set-formula '=REPEAT("█", ROUND(B4*100/MAX(B4[!0])/10,0))' --apply
# 带色：xlsx 里标签被剥掉只剩字符；png 里是绿色的方块（showAsHTML 生效）
frcli report cell "$R" --at D4 --show-html \
  --set-formula '="<font color=#1F7A1F>" + REPEAT("■", ROUND(B4*100/MAX(B4[!0])/10,0)) + "</font>"' --apply
```

实测（金额 100/350/500/80/260，满格 10 块）：`C4 ∈ {██, ███████, ██████████, ██, █████}` ✓；
png 里 D 列是绿色方块、`<b>粗</b>普通` 渲染成**粗体"粗"** ⇒ `showAsHTML` 本身是好的，只是**表格/背景样式不支持**。

---

## 4. 多数据集关联取数（跨数据集取值）

**效果**：主表来自 `ds1`（中心维表），金额从 `ds2`（明细）里按中心取；`ds2` 里多出来的中心不出现。

**样例**：`patterns/r4_two_datasets.cpt`

**配方**

```bash
frcli report dataset "$R" --add ds1 --conn demo_conn \
  --sql "select 'SC04' center,'华西' name union all select 'SC03','华南' union all select 'SC05','华北'" --apply
frcli report dataset "$R" --add ds2 --conn demo_conn \
  --sql "select 'SC04' center,100 amt union all select 'SC04',200 union all select 'SC03',300
         union all select 'SC05',50 union all select 'SC09',999" --apply
frcli report table "$R" --dataset ds1 --at A2 --columns center,name --header --mode group --apply
frcli report cell "$R" --at C3 --set-formula '=SUM(ds2.select(amt, center=$A3))' --apply   # 跨数据集聚合
frcli report cell "$R" --at D3 --set-formula '=ds2.select(amt, center=$A3)' --apply        # 跨数据集明细
frcli report cell "$R" --at E3 --set-formula '=COUNT(ds2.select(amt, center=$A3))' --apply # 命中条数
```

**实测导出**

```
2 ['中心','名称','ds2汇总','ds2明细','ds2计数']
3 ['SC04','华西', 300.0, '100,200', 2.0]     ← ds2 里 SC04 有两条
4 ['SC03','华南', 300.0, 300.0,     1.0]
5 ['SC05','华北',  50.0,  50.0,     1.0]
   （ds2 里的 SC09 不出现 ⇒ 以 ds1 行为准，等价于 left join）
```

**坑**

1. **数据集函数只认 `select` / `group` / `value`**（语料频次 108/21/5）：
   `ds2.sum(...)` / `ds2.count(...)` **不存在**，写了不报错、结果是**空**。
   聚合要**套在外层**：`=SUM(ds2.select(amt, center=$A3))`、`=MAX(ds2.select(...))`、
   `=COUNT(UNIQUEARRAY(ds1.select(...)))` —— 这就是官方模板里的真实写法。
2. `ds2.select(...)` 命中多条时返回**数组**，直接放在单元格里会被拼成 `100,200`。
   要一行一条得用「分组」或让它落到合适的父格上。
3. **单元格级行过滤**用 `--ds-filter`（写 `DSColumn` 的 `<Condition class="…FormulaCondition">`），
   `$$$` 是本列值、可以引用模板参数；数据过滤与数据设置（`<RG>`）**正交**。
4. ⚠️ **`=SUM(ds2.select(amt, center=$A$3))` 写死绝对引用实测四行全 `0`**（不是"只取第一行"）——
   用**行内相对引用 `$A3`**：它跟着扩展走，每行取自己那一行的值。绝对引用在关联条件里等于"每行都去比一个
   不随行变化的键"，多数情况下匹配不上 ⇒ 静默得 0。

---

## 5. 参数联动过滤（模板参数 → SQL → 单元格 → 标题）

**效果**：参数 `min_amt` 一个值同时驱动 ① SQL 的 `${min_amt}`、② 单元格过滤条件 `$$$ >= $min_amt`、③ 标题文字 `="金额 >= " + $min_amt`。

**样例**：`patterns/r5_params.cpt`（⚠️ 该样例**没有**下面第 4 条的 `--ds-filter` 那一列，导出 dims 只有 `A1:B5`；
配方与样例在此处不一致，以配方为准）

```bash
# 参数默认值会同时写进【数据集 <Parameters>】和【模板参数声明】两处
frcli report dataset "$R" --add ds1 --conn demo_conn \
  --sql "select * from (select 'SC04' center,100 amt union all select 'SC03',300
         union all select 'SC05',50) t where amt >= \${min_amt}" --param min_amt=100 --apply
frcli report table "$R" --dataset ds1 --at A3 --columns center,amt --header --labels "中心,金额" --apply
frcli report cell "$R" --at A1 --set-formula '="金额 >= " + $min_amt' --merge A1:B1 --bold --bg '#D9E1F2' --apply
frcli report cell "$R" --at C4 --bind ds1.amt --set-ds-mode list --expand v \
  --ds-filter '$$$ >= $min_amt' --apply                       # 单元格过滤（数据集列的 <Condition>）
# ⚠️ 挂 **C4** 不是 C3：--at A3 --header 时 A3 是表头行，数据行在 A4。
#    挂 C3 会把列挤到 3/4 行、A/B 两列数据被推到 5/6 行、表头被拉伸合并（错位但 status: ok）。
```

**实测（默认 + 传参两次导出）**

```bash
frcli export excel "$R" -o /tmp/r5_default.xlsx                                  # min_amt=100（模板默认值）
frcli export excel "$R" -o /tmp/r5_p200.xlsx --params '{"min_amt":200}'          # 覆盖
```
```
默认:  A1='金额 >= 100'   A4=['SC04',100]  A5=['SC03',300]      ← SC05 50 被过滤
传参:  A1='金额 >= 200'   A4=['SC03',300]                        ← 只剩一条
```

**坑**

1. **`${x}` 与 `$x` 是两个世界**：SQL 里只能 `${x}`，单元格公式里只能 `$x`，写错**都不报错**
   （SQL 里写 `$x` 会把字面量送进 SQL；公式里写 `${x}` 会原样渲染出这 6 个字符）。CLI 会本地 warning。
2. **参数必须给默认值**（`--param p=v` 两处都写）。"没传值又没默认值" = **静默空字符串**，导出照样成功、内容全空。
3. 参数放在 SQL 的语法敏感位置（`limit ${n}`）会让 REST `format=cpt` 通道（不带默认值）报"数据集配置错误"，
   而 `export`（带默认值）正常 —— 尽量放在带引号的字符串位置，或调用时始终传参。
4. **导出时用 `--params '{"k":v}'` 传驱动参数即可**，派生参数由服务端推导；
   复杂版面报 `11300002 行高列宽超出页面大小` 时加 `--params '{"extype":"simple"}'` 走原样导出。
5. **验收必须"不带 `--params` 再导一次"**：确认默认值生效，否则用户打开就是空白。

---

## 6. 日期 / 时间维度（`<Result>` 表达式 + 日期函数）

**效果**：原始日期串 `20260901` 在一列上直接显示成 `2026年09月`（`<Result>` 表达式），
另两列做「月内第几周」「年内第几周」。

**样例**：`patterns/r6_date_dim.cpt`

```bash
frcli report cell "$R" --at A3 --bind ds1.d --set-ds-mode list --expand v \
  --ds-result "FORMAT(TODATE(\$\$\$,'yyyyMMdd'),'yyyy年MM月')" --apply
frcli report cell "$R" --at D3 --bind ds1.d --set-ds-mode list --expand v --apply      # 原值列，给公式引用
# 官方模板 doc/SpecialSubject/function/使用公式计算日期在当月中的第几周.cpt 的写法
frcli report cell "$R" --at E3 --set-formula \
  '=ROUNDUP((DAY(TODATE(D3,"yyyyMMdd")) + (IF(WEEKDAY(DATEINMONTH(TODATE(D3,"yyyyMMdd"),1))=0,7,
   WEEKDAY(DATEINMONTH(TODATE(D3,"yyyyMMdd"),1)))) - 1)/7,0)' --apply
frcli report cell "$R" --at F3 --set-formula '=WEEK(TODATE(D3,"yyyyMMdd"))' --apply
```

**实测导出**

```
2 ['年月(Result)','金额','原始日期','月内第几周(官方公式)','年内第几周']
3 ['2026年09月', 100.0, '20260901', 1.0, 35.0]
4 ['2026年09月', 150.0, '20260915', 3.0, 37.0]
5 ['2026年10月', 200.0, '20261001', 1.0, 39.0]
6 ['2026年10月',  80.0, '20261020', 4.0, 42.0]
```

**坑**

1. **`<Result>` 改变的是"这一格的取值"**，别的格引用它时拿到的是**转换后**的值。
   所以"原值要留给别人引用"就得单独留一列（本配方里是 D 列）。
2. **`<Result>` 默认不写**（语料 5696 个 DSColumn 里只有 708 个带），它只是"再套一层表达式"，不是数据设置 ——
   `<RG>` 该写还得写。
3. **函数名写错 = 整张模板渲染不出来**：`DATEFORMAT` 不存在 → `no function found: DATEFORMAT`。
   排查用 `frcli report datasets <模板>`（会直接给出坏函数名）。
   本安装里 **存在**的日期函数：`TODATE/FORMAT/WEEK/WEEKDAY/DATEINMONTH/DATEINWEEK/DATEINQUARTER/
   DATEINYEAR/DAY/MONTH/YEAR/DATEDIF/DATEDELTA/DATESUBDATE/TODAY/NOW`（`com/fr/function/*` 全表见 §8）。
4. `--ds-result` 表达式里 `$$$` = 本列原值；写 `=FOR...` 时前导 `=` 可有可无（服务端存的是不带 `=` 的表达式）。

---

## 7. 分页 / 页眉页脚 / 冻结 / 重复标题行（**含 2 条未确证**）

**样例**：`patterns/r7_page.cpt`（80 行多页）、`patterns/r7_wide_freeze.cpt`（16 列宽表）

```bash
frcli report page "$R" --list                                   # 读：页眉页脚高度/冻结/页眉页脚内容
frcli report page "$R" --header-height 30 --footer-height 20 --freeze 1,0 --apply
frcli report page "$R" --no-repeat-rows 3 --apply               # 第 3 行写 CellPageAttr repeat="false"
```

**XML 契约（都有类/方法出处）**

```xml
<ReportAttrSet>
<ReportSettings headerHeight="1328250" footerHeight="885500">   <!-- FU；FU_PER_POINT=44275 -->
<PaperSetting>…</PaperSetting>
<FrozenColumnRow columnrow="1,0"/>                              <!-- 冻结列行 -->
</ReportSettings>
<Header reportPageType="0"><Background name="NullBackground"/>
<LeftList/><CenterList/><RightList/></Header>                    <!-- 页眉内容容器（语料全是空） -->
<Footer reportPageType="0">…</Footer>
</ReportAttrSet>
```

- `ReportSettings`：`com.fr.report.stable.ReportSettings.writeXML` 写 `headerHeight/footerHeight`
  （`UNIT.toFU()`）与子元素 `<FrozenColumnRow columnrow=…>`（字段名 `writeFrozenColumnRow`）。
- `CellPageAttr`：`com.fr.report.cell.cellattr.CellPageAttr`，位掩码
  `pageAfterColumn/pageAfterRow/pageBeforeColumn/pageBeforeRow/repeat/breakOnPaginate`；
  **字段初值 63（全位）⇒ `repeat` 缺省就是 true，`writeXML` 只在 `!isRepeat()` 时写 `repeat="false"`**。

**实测（都是这一轮真跑的）**

| 项 | 结果 |
|---|---|
| `--header-height/--footer-height/--freeze` 写入 + 回读 | ✅ `report page --list` 读回 `30.0 / 12.0 / "1,0"` |
| PDF 产物是否受影响 | ✅ 有（`w_frozen.pdf` 43874B vs `w_plain.pdf` 41762B；均 4 页） |
| PDF **文本坐标**是否变化 | ❌ 没有（两份 PDF 文本项 48 个、x 坐标分布完全一致）⇒ **冻结列是否"每页重复"未确证** |
| `report image` 是否体现页眉高度/冻结 | ❌ 两次出图**逐字节相同**（image 通道忽略这两项） |
| 80 行报表默认是否重复表头 | ❌ **不重复**：image 里第 1 页到 C53 结束，第 2 页从 C54 直接开始，表头只出现一次 |
| `repeat="false"` 与不写的差异 | ❌ image 产物逐字节相同 ⇒ **`repeat` 不是"每页重复标题行"的开关** |

**结论（诚实版）**
- "每页重复标题行"在本版本**没找到生效的模板级写法**：语料 1602 个 .cpt 里 `repeat*` 属性 **0 处**，
  实测默认也不重复。要重复表头，现实的路线是把表头做进**页眉**（`<Header>` 的
  `LeftList/CenterList/RightList`）——**未确证**（本 CLI 只读该节点，不做写入）。
- 冻结列（`FrozenColumnRow`）**能写、能回读、PDF 产物有变化**，但"跨页重复左列"的效果
  **未确证**（缺 PDF 文本提取工具；实测环境无 `pdftotext`/`pypdf`）。
  复现实验的命令都在本节，谁有 PDF 文本工具可以接着判。
- 单元格分页控制 `pageBeforeRow/pageAfterRow` 的**写入**本 CLI 暂未暴露（`report page --list` 会读出来）。

---

## 8. 公式函数实战（组内序号 / 累计 / 环比 / 占比 / 去重计数）

**效果**：一列明细上同时算「占比、序号、累计、环比、去重计数、总额校验」。

**样例**：`patterns/r8_functions.cpt`（数据 100/200/300/50/50，合计 700）

```bash
frcli report cell "$R" --at C3 --set-formula '=B3/SUM(B3[!0])' --num-format '#0.0%' --apply
frcli report cell "$R" --at D3 --set-formula '=SEQ()' --apply
frcli report cell "$R" --at E3 --set-formula '=SUM(SLICEARRAY(B3[!0],1,D3))' --apply           # 累计
frcli report cell "$R" --at F3 --set-formula '=IF(D3=1,0,B3/SUM(SLICEARRAY(B3[!0],D3-1,D3-1))-1)' \
  --num-format '#0.0%' --apply                                                                  # 环比
frcli report cell "$R" --at G3 --set-formula '=COUNT(UNIQUEARRAY(A3[!0]))' --apply              # 去重计数
frcli report cell "$R" --at H3 --set-formula '=SUMPRECISE(B3[!0])' --apply                      # 总额
```

**实测导出（逐格）**

```
2 ['中心','金额','占比','序号','累计','环比','去重中心数','总额校验']
3 ['SC04',100.0, 14.3%,  1.0, 100.0,   0.0%, 3.0, 700]
4 ['SC04',200.0, 28.6%,  2.0, 300.0, 100.0%, 3.0, 700]
5 ['SC03',300.0, 42.9%,  3.0, 600.0,  50.0%, 3.0, 700]
6 ['SC05', 50.0,  7.1%,  4.0, 650.0, -83.3%, 3.0, 700]
7 ['SC05', 50.0,  7.1%,  5.0, 700.0,   0.0%, 3.0, 700]
```

**可用的关键函数（本安装 `com/fr/function/*` 实测）**

| 想做什么 | 写法 | 备注 |
|---|---|---|
| 整列合计 | `SUM(B3[!0])` | `[!0]` = 该格扩展出来的全部格子，**同行的 `B3` 只是本行** |
| 组内序号 | `SEQ()` | 在自己的格里按扩展顺序 1..N |
| 累计 | `SUM(SLICEARRAY(B3[!0],1,D3))` | `D3` 必须是**另一格**的 `SEQ()`（见坑 1） |
| 环比 | `=B3/SUM(SLICEARRAY(B3[!0],D3-1,D3-1))-1` | 用 `SLICEARRAY` 取上一行；首行用 `IF(D3=1,0,…)` |
| 去重计数 | `COUNT(UNIQUEARRAY(A3[!0]))` | 官方模板里的常见套法 |
| 取数组前 N / 第 N 个 | `SLICEARRAY(arr,1,2)` | 1 基、**闭区间**；`INDEX(arr,2)` **不是**数组下标（实测返回 `2`） |
| 高精度合计 | `SUMPRECISE(B3[!0])` | 与 `SUM` 结果一致（本例 700） |
| 中文/文本条 | `REPEAT("█", n)` | 见 §3 数据条 |

**坑**

1. **`SEQ()` 内联进公式"生不生效"取决于版面**：`=SUM(SLICEARRAY(B3[!0],1,SEQ()))` 实测（各 2 轮稳定）

   | 版面里有没有另一个 `SEQ()` 格 | 内联写法结果 |
   |---|---|
   | **有**（如 `D3=SEQ()`） | **700,700,700,700,700**（每行都是整列合计 —— 错） |
   | **没有** | **100,300,600,650,700**（正确累计） |

   同一条公式在两种版面上结果相反、**两边都不报错** ⇒ 别用内联写法。
   **唯一安全姿势**：单独一格 `=SEQ()`，公式里引用它：`=SUM(SLICEARRAY(B3[!0],1,D3))` → 100/300/600/650/700 ✓。
2. **`RANK` 在本安装里求不出值**：`=RANK(B3,B3[!0])` 渲染成 **`#NAME?`**（image 与 xlsx 都是），
   而 `report datasets` **不报错**（说明函数名注册了、求值失败）。`MAPARRAY` 做排名的尝试也失败（恒返回 1）。
   ⇒ **组内排名请写在 SQL 里**（`row_number() over (partition by …)`）。
3. **不存在的函数名**（`ACCSUM` / `CUMULATIVE` / `COUNTD` / `DATEFORMAT` / `DATETRUNC`）会让整张模板渲染不出来，
   `frcli report datasets` 直接报 `no function found: X` —— 这是最快的排查入口。
4. 公式引用的**数组语法不通用**：`B3[!0]` 只在这套引擎里有效，导出 xlsx 时遇到 `RANK(...B3[!0]...)`
   这类"服务端不计算、原样吐出"的函数会变成 Excel 的 `#NAME?`。
5. `SLICEARRAY` 的区间是**闭区间且 1 基**，但**返回的是数组**：一格直接写 `=SLICEARRAY(B3[!0],1,2)`
   渲染成**字符串 `100,200`**（不是数值 300）；要拿到 300 必须套聚合 `=SUM(SLICEARRAY(B3[!0],1,2))`。
   ⇒ 别把"函数返回什么"与"格子里显示什么"混为一谈。

---

## 9. CLI 能力速查（本轮新增）

| 想做什么 | 命令 | 说明 |
|---|---|---|
| 条件属性 | `report highlight REMOTE --at A3:D3 --rule '条件:动作' [--rule …] [--clear] [--apply]` | `--at` 支持区域；`--list` 只读 |
| 交叉表 | `report crosstab REMOTE --dataset ds --at A3 --row a,b --col c --value v [--agg sum] [--total-row] [--total-col] [--apply]` | 四类格自动生成；多 `--value` 明确拒绝 |
| 分页设置 | `report page REMOTE [--header-height N] [--footer-height N] [--freeze 列,行] [--repeat-rows n] [--no-repeat-rows n] [--list] [--apply]` | FU 换算内置（`44275 FU = 1 磅`） |
| 数据集列表达式 | `report cell REMOTE --at A3 --bind ds.d --ds-result "FORMAT(\$\$\$,'yyyy年MM月')"` | 写 `DSColumn` 的 `<Result>` |
| 单元格行过滤 | `report cell REMOTE --at C3 --bind ds.amt --ds-filter '$$$ >= $min_amt'` | 写 `<Condition class="…FormulaCondition">` |
| 显式父格 | `report cell REMOTE --at A4 --expand-left A3 [--expand-up B1]` | 组内小计 / 交叉表列头挂靠 |
| HTML 渲染 | `report cell REMOTE --at D4 --show-html [--tooltip "=公式"]` | 写 `<CellGUIAttr showAsHTML="true"/>` |

只读核对（每轮验收都要用）：

```bash
frcli report cell "$R" --list -f table        # A1/值/公式/绑定/扩展/数据设置/条件属性
frcli report highlight "$R" --list            # 条件属性规则（when/then）
frcli report page "$R" --list                 # 分页设置
frcli report datasets "$R"                    # 数据集健康（坏 SQL/坏函数第一入口）
```

---

## 10. 样例清单与复现脚本

服务器目录 `demo_group/demo_user/skill测试/patterns/`（`_目录说明.txt` 有同样一份说明）：

| 文件 | 演示什么 | 关键实测值 |
|---|---|---|
| `r1_group_subtotal.cpt` | 分组 + 组内小计 + 总计 + 占比 | 600 / 900 / 1500；占比 6.7%…33.3% |
| `r2_crosstab.cpt` | 交叉表（2 产品基线 + 动态列） | 100/200/300…；总计 1600/2000/3600 |
| `r2_crosstab_agg.cpt` | 同一交叉点多记录：默认 vs `--agg sum` | 默认 `100,50`/150（错）；sum 200/270 ✓ |
| `r3_highlight.cpt` | 阈值标红 + 绿色 + 隔行变色 | bg `FFC7CE`/`C6EFCE`/`F2F2F2`，fg `9C0006`/`006100` |
| `r3b_databar.cpt` | 数据条（字符条 + HTML 色块） | ██/███████/██████████ |
| `r3b_probe.cpt` | 数据条/公式探针（含 HTML table 失败对照） | `<table>` 空白、`<b>` 变粗体 |
| `r3c_hide_row.cpt` | 条件隐藏整行（`rowheight=0`） | 80 那一行整行消失（5 行 → 4 行） |
| `r4_two_datasets.cpt` | 多数据集关联取数 | 300/'100,200'/2；SC09 不出现 |
| `r5_params.cpt` | 参数联动（SQL + 过滤 + 标题） | 默认 100→100/300；传 200→只剩 300 |
| `r6_date_dim.cpt` | `<Result>` 日期维度 + 周计算 | 2026年09月；周 1/3/1/4；年内 35/37/39/42 |
| `r7_page.cpt` | 80 行多页（重复标题行对照） | 第 2 页无表头（默认 & repeat=false 逐字节同） |
| `r7_wide_freeze.cpt` | 16 列宽表 + 冻结列/页眉高度 | PDF 43874B vs 41762B；文本坐标不变 |
| `r8_functions.cpt` | 占比/序号/累计/环比/去重/总额 | 见 §8 逐格表 |

离线回归：`tests/test_highlight_crosstab.py`（条件属性 / 交叉表 / 分页设置的 XML 契约，不联网）。
真机验收：本文每节的"实测导出"就是证据，重跑一遍即可复现。

---

## 11. 相关文档

- `references/cpt-authoring.md` —— 五步造报表 + 命令语法（本文件是它的"复杂效果"续集）
- `references/cpt-features.md` —— 语料普查（`<RG>`/`<Highlight>`/`<Expand>` 频次与「我要 X 效果→XML」表）
- `docs/探索/cpt服务端模型-逆向.md` —— 服务端权威模型（`<C>`/`<O>`/`<RG>`/`<Expand>`/`<Highlight>` 契约与缺省值）
- `docs/验证/cpt创作验证报告.md` —— 逐轮验证记录与问题状态跟踪

---

## 12. 端到端集成示例：一张「像真实经分报表」的完整构建（Lead 实测）

前面 11 节是**单点配方**，这一节是**把它们串成一张真报表**的完整过程 —— 只用 CLI，数据来自生产 `dm` 表。
成品：`demo_group/demo_user/skill测试/lead_report.cpt`（标题 + 参数化日期 + 36 行大区明细 + 占比 + 阈值标红）。

```bash
R="demo_group/demo_user/skill测试/lead_report.cpt"
export FRCLI_WRITE_SCOPE="demo_group/demo_user/skill测试"

# ① 建模板 + 模板参数（默认值必给：无值又无默认 → 静默空字符串）
frcli report new "$R" --apply
frcli report param "$R" --add "sdate=20260901" --add "edate=20260926" --apply

# ② 数据集：参数写 ${x}（SQL 语法），日期区间过滤
frcli report dataset "$R" --add ds1 --conn demo_conn --sql "
select sales_dist_id dist, round(sum(restore_sales_amt),0) amt
from demo_db.demo_sale_dly
where sdt between '\${sdate}' and '\${edate}'
group by sales_dist_id order by amt desc" --apply

# ③ 标题（**公式**，单元格里参数写 $x 不是 ${x}）+ 表头 + 取数表
frcli report cell "$R" --at A1 --merge A1:C1 \
  --set-formula '="各大区销售额（" + $sdate + " ~ " + $edate + "）"' --apply
frcli report table "$R" --dataset ds1 --at A2 --columns dist,amt \
  --labels "大区,销售额" --header --apply

# ④ 占比列：分母必须写 [!0]（整列合计），写 C3/SUM(C3) 会每行 100%
frcli report cell "$R" --at C3 --set-formula '=B3/SUM(B3[!0])' --num-format '#0.0%' --apply
frcli report cell "$R" --at B3 --num-format '#,##0' --apply

# ⑤ 条件属性：占比 >10% 标红加粗
frcli report highlight "$R" --at C3:C40 --rule 'v>0.1:bg=#FFC7CE,fg=#9C0006,bold' --apply

# ⑥ 导出
frcli export excel "$R" -o /tmp/r.xlsx
frcli export pdf   "$R" -o /tmp/r.pdf
```

**逐格读回验收（实测）**

| 校验项 | 结果 |
|---|---|
| 标题 | `各大区销售额（20260901 ~ 20260926）` —— 参数正确展开 |
| 数据行 | 36 行真实大区（110000 = 5.77 亿 … 617000 = 1.67 万），按金额降序 |
| **占比合计** | **`1.000000`** —— `=B3/SUM(B3[!0])` 精确成立 |
| 条件属性 | 标红 **3 行** = 占比 >10% 的 **3 行**（16.34% / 13.09% / 12.06%），`bg=00FFC7CE` + `bold=True` |
| PDF | 141,957 B，魔数 `%PDF-` |

**这次踩到的两个坑（都是用法错，不是功能问题）**
1. **标题用 `${sdate}` 不展开** —— `${x}` 只在数据集 SQL 里替换，**单元格公式/文本要写 `$x`**。
   我第一版标题原样输出了 `${sdate}~ ${edate}`，导出成功、看着像"参数没生效"。
2. **条件属性阈值设成 `v>0.2`，而数据最大值只有 16.3%** → 一条都没命中，看起来像"条件属性没生效"。
   **验收条件属性时，阈值必须先按数据分布设计**（先用 `report image` 或读回数据确认存在命中行）。

> 教训与 §0 一致：**"没生效"要先排除自己的表达式/阈值写错**，再怀疑功能。
