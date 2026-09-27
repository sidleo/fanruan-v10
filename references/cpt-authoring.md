# cpt 模板创作手册（agent 照着抄就能造报表）

> 面向**不会 XML 的 agent**：想知道「造一张取数表」怎么做，从 §1 的五步开始抄；
> 想知道某个字段什么意思，查 §4 语法速查；踩到怪现象，查 §7 坑点。
> 所有片段都在本服务器实测过（2026-09，FineReport V10），命令输出是真跑出来的。

## 0. 三条先记住的事

0. **数据集列格必须带 `<RG>`（数据设置）** —— 选了 `group`/`list`/`summary` 才有正确结果；
   **不写 `<RG>` 服务端按「分组」处理**（数值列被去重、合计对不上，且不报错）。
   `report table` 默认 `--mode list`（记录原样展开）。详见 §4.7 / §6.1。
1. **能在服务端写模板的只有远程设计通道** —— `report new/cell/dataset/param/style/table` 都是它的封装。
   写命令**默认 dry-run**（打印 diff + `bytes_before/bytes_after`），加 `--apply` 才写。
2. **写操作默认拒绝**：先 `export FRCLI_WRITE_SCOPE="<你被授权的目录>"`，否则一律拒绝（fail-closed）。
3. **「导出成功」不是验收**。写错列名、写错公式、参数没值、样式索引越界，服务端**全部照收不误**，
   导出一份看起来正常的 Excel（内容是空的）。唯一可信的验收是 **openpyxl 逐格读回**（§6）。

## 1. 五步造一张取数表（最短路径，直接抄）

```bash
# 0) 限定写范围（一次 export，之后每条命令都生效）
export FRCLI_WRITE_SCOPE="demo_group/demo_user/skill测试"
R="demo_group/demo_user/skill测试/demo.cpt"

# 1) 建空白模板（自带骨架，可渲染）
frcli report new "$R" --apply

# 2) 加数据集（名字/SQL/参数；参数默认值会同时写进数据集和模板参数）
frcli report dataset "$R" --add ds1 --conn demo_conn \
  --sql "select 'SC04' code,'华西' name,376 cnt union all select 'SC03','华南',335" \
  --param topn=10 --apply

# 3) 一次生成整张表（表头 + 逐列绑定 + 扩展 + 数据设置）
#    从 A2 开始 —— 把 A1 留给标题（report table 会整格改写目标区域，见 §7.6）
#    默认 --mode list（记录原样展开，不去重）；要分组/汇总见 §4.7
frcli report table "$R" --dataset ds1 --at A2 --columns code,name,cnt \
  --header --labels "中心编码,中心名称,门店数" --apply

# 4) 标题（公式引用参数）+ 横向合并 A1:C1
frcli report cell "$R" --at A1 --set-formula '="门店数 TOP" + $topn' --merge A1:C1 --apply

# 5) 验收（必做）
frcli export excel "$R" -o /tmp/demo.xlsx
python3 -c "
import openpyxl; ws=openpyxl.load_workbook('/tmp/demo.xlsx').active
print([str(m) for m in ws.merged_cells.ranges])
for r in ws.iter_rows(max_row=8,max_col=4): print([c.value for c in r])"
```

**实测输出**（本手册作者跑的，模板 `t4_report.cpt`）：

```
合并: ['A1:C1']
['支持中心门店数 TOP10', None, None, None]      ← $topn 取模板参数默认值 10
['中心编码', '中心名称', '门店数', None]
['SC04', '华西', 376.0, None]
...
A2 bold=True fill=00FFF2CC                      ← 表头样式生效
C3 number_format = '#,##0'                      ← 数字格式生效
```

> 想造**复杂**报表（分组小计 / 交叉表 / 条件属性 / 多数据集 / 参数联动 / 日期维度 / 公式实战）？
> 直接看 **`references/cpt-patterns.md`** —— 每条配方都有完整命令与逐格实测结果，不用从这五步自己推。

传参覆盖：`frcli export excel "$R" --params '{"topn":3}'` → 标题变 `TOP3`
（上面的示例 SQL 是字面量 `union all`，没有 `${…}`；真实报表里 SQL 的 `${x}` 会一起跟着变 ——
**SQL 看 `${x}`，公式看 `$x`**，见 §7.1）。

## 2. 命令速查

| 想做什么 | 命令 | 只读/写 |
|---|---|---|
| 建空白模板 | `report new REMOTE [--sheet NAME] [--from TEMPLATE] [--output FILE] [--apply] [--force]` | 写 |
| 看有哪些单元格 | `report cell REMOTE --list [--sheet S] [-f table]`（含 `ds_mode`/`ds_fn`） | 🟢 只读 |
| 改一格 | `report cell REMOTE --at B3 --set-value/-set-formula/-bind/--set-ds-mode/--fn/--expand/--style/--num-format/--merge/--clear [--apply]` | 写 |
| 看数据集 | `report dataset REMOTE --list [--full]` | 🟢 只读 |
| 加/改/删数据集 | `report dataset REMOTE --add NAME --conn C --sql S [--param p=v]` / `--set-sql NAME --sql S` / `--remove NAME` `[--apply]` | 写 |
| 看模板参数 | `report param REMOTE --list` | 🟢 只读 |
| 加/改参数 | `report param REMOTE --add p=v` / `--set-default p=v` / `--remove p` `[--apply]` | 写 |
| 看样式表 | `report style REMOTE --list` | 🟢 只读 |
| 加样式 | `report style REMOTE --add --num-format "#,##0.00" --bold --bg '#FFF2CC' --align center --border` `[--apply]` | 写 |
| 一次生成整张表 | `report table REMOTE --dataset ds --at A1 --columns a,b,c [--mode list\|group\|summary] [--fn sum] [--group-by x,y] [--header] [--labels "x,y,z"] [--expand v]` `[--apply]` | 写 |
| **造交叉表/动态列** | `report crosstab REMOTE --dataset ds --at A3 --row a,b --col c --value v [--agg sum] [--total-row] [--total-col]` `[--apply]` | 写 |
| **写条件属性** | `report highlight REMOTE --at D3\|A3:D3 --rule '条件:动作' [--rule …] \| --clear \| --list` `[--apply]` | 写 |
| **分页设置** | `report page REMOTE --list \| --header-height N --footer-height N --freeze 列,行 --no-repeat-rows 3` `[--apply]` | 写 |

- `--at` / `--merge` 一律用 **A1 记法**（`B3`、`AA10`、`A1:C1`），不用 c/r 数字。
- 写命令的 `-f table` 打**可读 diff**（`-` 旧 / `+` 新 + `bytes: 2050 → 2492`）；默认 `-f json` 给结构化结果。
- ⚠ warning / ℹ 提示**同时打到 stderr**（stdout 的 JSON 不受影响）：这两类说的都是「服务端不报错、
  但结果是错的」的静默坏法（列名写错、参数没默认值、SQL 裸 `$x`…），别把 stderr 当噪音忽略。
- 所有写命令都吃 `--any-path`（确认写这个目标、绕过范围限制），**别习惯性加它**。
- `report dataset`（单数）读的是**模板字节**；`report datasets`（复数）走 REST `format=cpt`，
  数据集本身坏掉时后者直接报错 —— 排查优先用单数那条。

## 3. 取骨架的两种方式

```bash
frcli report new "$R" --apply                        # 内置骨架（2050B，<TableDataMap/> + 空单元格）
frcli report new "$R" --from "demo_group/…/某张现成模板.cpt" --apply   # 裁出现成模板的版面外壳
frcli report new "$R" --output /tmp/r.cpt            # 只生成本地文件，不联网写
```

`--from` 保留：页边距 / 行高列宽 / `<StyleList>`（样式索引跟着走）/ 打印设置 / sheet 结构；
清空：**每一张 sheet 的单元格**、全部数据集、模板参数声明。骨架默认 sheet 名 `sheet1`，用 `--sheet` 改名。

实测（`--from demo_report.cpt --sheet 我的表`）：5 张 sheet 全部 0 格、19 个样式完整保留
—— 想复用某张报表的配色/字号/数字格式，这是最快的路子。

## 4. XML 速查（要手写片段时看这节）

```xml
<WorkBook xmlVersion="20211223" releaseVersion="10.0.0">
  <TableDataMap/>                                  ← 数据集（0..N 个 TableData）
  <Report class="com.fr.report.worksheet.WorkSheet" name="sheet1">
    <RowHeight defaultValue="723900">CDATA:逐行高度</RowHeight>
    <ColumnWidth defaultValue="2743200">CDATA:逐列宽度</ColumnWidth>
    <CellElementList>                              ← 单元格
      <C c="列" r="行" [cs="跨列"] [rs="跨行"] s="样式索引"> … </C>
    </CellElementList>
  </Report>
  <ReportParameterAttr><Parameters>模板参数</Parameters></ReportParameterAttr>
  <StyleList>样式表</StyleList>
</WorkBook>
```

`c`/`r` 从 **0** 开始（`B3` = `c="1" r="2"`），单元格按 (行, 列) 顺序排列。

### 4.1 单元格的三种值（`<O>`）

```xml
<!-- 静态文本 -->
<C c="0" r="0"><O><![CDATA[门店数]]></O><PrivilegeControl/><Expand/></C>

<!-- 公式（t="XMLable" + class="com.fr.base.Formula"；正文以 = 开头） -->
<C c="1" r="1"><O t="XMLable" class="com.fr.base.Formula">
<Attributes><![CDATA[=SUM(C3:C9)]]></Attributes></O><PrivilegeControl/><Expand/></C>

<!-- 数据集列（t="DSColumn"）—— 必须带 <RG>（数据设置），见 §4.7 -->
<C c="0" r="1"><O t="DSColumn">
<Attributes dsName="ds1" columnName="code"/><Complex/>
<RG class="com.fr.report.cell.cellattr.core.group.FunctionGrouper"/><Parameters/>
</O><PrivilegeControl/><Expand dir="0"/></C>

<!-- 数值常量（排序/比较用得上） -->
<C c="2" r="0"><O t="I"><![CDATA[0]]></O><PrivilegeControl/><Expand/></C>
```

`<PrivilegeControl/>` 与 `<Expand/>` 是固定成员；**`<PrivilegeControl/>` 缺失不影响渲染**
（cpt-verifier 实测），但 CLI 生成的格子一律带上。

**数据集列的规范形状**（Designer 实际写出来的，本地 1602 个官方模板里 4467/5696 = **78%** 逐字节一致）：

```
<Attributes …/> → <Complex/> → <RG …/> → <Parameters/>
```

`<Result>$$$</Result>` **默认不写**（只有 5% 的老模板带它，值是原值时可省）。
**`<RG>` 不能省** —— 省了服务端按「分组」处理，见 §4.7 与 §6.1。

### 4.2 扩展方向（最容易记反）

| 想要的效果 | 写法 | CLI |
|---|---|---|
| 纵向铺开（一列变多行，维度列/明细表） | `<Expand dir="0"/>` | `--expand v` |
| 横向铺开（一行变多列，日期/指标列） | `<Expand dir="1"/>` | `--expand h` |
| 不扩展 | `<Expand/>` | `--expand none` |

**实测交叉验证**：
- `doc/Primary/GroupReport/纵向分组报表.cpt`（纵向分组报表）里维度格用 `<Expand dir="0"/>`，汇总格用 `<Expand/>`；
  语料里 `dir="1"` 出现在 产品类型/日期/月份/季度/年份 这些**交叉表列头**上。
- 8 张单格对照件实测：`dir="0"` → 6 行竖排；`dir="1"` → 1 行 6 列；`<Expand/>` → **1 格**。

写反**不报错**，只是表格长歪（数据横着排成一行，其余列消失）。

⚠️ **`<Expand/>`（不扩展）时多个值会被逗号拼成一格**：实测同一列 6 个值
`10,10,20,10,30,30` 全被拼成字符串 `"10,10,20,10,30,30"` 写进一格 —— 导出成功、看着"有数据"，
其实版面已经错了。**绑了数据列就不要用 `--expand none`**，除非你确实要"多值拼一格"。

`<Expand>` 还有 `extendable/multiNumber/isCover/left/up/leftParentDefault/upParentDefault/order`
与子元素 `<SortFormula>`；单独写 `extendable` 实测不改变扩展方向（**确切作用待验证**）。

### 4.3 数据集

```xml
<TableDataMap>
<TableData name="ds1" class="com.fr.data.impl.DBTableData">
<Parameters>
<Parameter><Attributes name="min_center"/><O><![CDATA[01]]></O></Parameter>  <!-- 默认值写在 O -->
</Parameters>
<Attributes share="true" maxMemRowCount="-1"/>
<Connection class="com.fr.data.impl.NameDatabaseConnection">
<DatabaseName><![CDATA[demo_conn]]></DatabaseName>
</Connection>
<Query><![CDATA[select … where code >= '${min_center}']]></Query>
<PageQuery><![CDATA[]]></PageQuery>
</TableData>
</TableDataMap>
```

连接名 = 模板 XML 里 `<DatabaseName>` 的字面量，**用 `frcli report datasets <已有模板>` 查**
（输出新增了 `connection` 字段/「连接」列，如 `demo_conn`）。

> ⚠️ 两个坑：① `frcli report serverdatasets` 列的是**服务器数据集**（113 条），**里面没有数据库连接名**，
> 拿它查会以为连接不存在；② `--conn` 填错**当场不报错**，要等查询期才失败 —— 写数据集前务必先核对。

### 4.4 模板参数（决定 `$x` 能不能解析）

```xml
<ReportParameterAttr>
<Attributes showWindow="true" delayPlaying="true" windowPosition="1" align="0" useParamsTemplate="true" currentIndex="0"/>
<PWTitle><![CDATA[参数]]></PWTitle>
<Parameters>
<Parameter><Attributes name="topn"/><O><![CDATA[10]]></O></Parameter>
<Parameter><Attributes name="min_center"/><O><![CDATA[01]]></O></Parameter>
</Parameters>
</ReportParameterAttr>
```

**参数必须给默认值，而且两处都要写**：数据集 `<Parameters>` 的 `<O>`（管 SQL 的 `${x}`）
+ `ReportParameterAttr` 的声明（管公式的 `$x`）。CLI 的 `report dataset --add --param p=v`
与 `report param --add p=v` 会自动两处都写。

### 4.5 样式与数字格式

```xml
<StyleList>
<Style horizontal_alignment="0" imageLayout="1">        <!-- 0=居中 2=左 4=右（奇数被忽略） -->
<Format class="com.fr.base.CoreDecimalFormat" roundingMode="6"><![CDATA[#,##0.00]]></Format>
<FRFont name="微软雅黑" style="1" size="72" foreground="-16777216"/>   <!-- style 1=粗体；size 单位 1/8 磅(72=9磅) -->
<Background name="ColorBackground" color="-3380"/>     <!-- #FFF2CC → -3380；不填色用 <Background name="NullBackground"/> -->
<Border><Top style="1"/><Bottom style="1"/><Left style="1"/><Right style="1"/></Border>
</Style>
</StyleList>
```

- 第 n 个 `<Style>` 由单元格 `s="n"` 引用（**0 起**）；`s=` 越界**不报错**，只是样式静默丢失
  （CLI 会本地拦：`--style` 越界直接报错）。
- 颜色是 24 位色补码：`#FFFFFF → -1`、`#000000 → -16777216`、`#EEEEEE → -1118482`。
- `<FRFont>` **总是显式写 `name`**：缺 `name` 时 `frcli report fonts` 会误报缺字体 `Default`。
- 常用数字格式：`#,##0`、`#,##0.0`、`0.00`、`#0%`、`#0.0%`。
- 不想手写 XML 就用 `report style --add --num-format … --bold --bg '#FFF2CC' --align center --border`，
  再加 `report cell --at B2 --style <新增的索引>`。
- ⚠️ `report cell --at B2 --num-format "#,##0"` 是**新建一个样式并绑上去**（不是改现有样式的格式），
  所以反复对同一格用不同 `--num-format`，`<StyleList>` 会一次多一条 —— 这是有意为之（避免改样式影响别的格）。

### 4.6 行列尺寸

```xml
<RowHeight defaultValue="723900"><![CDATA[900000,723900,723900]]></RowHeight>
<ColumnWidth defaultValue="2743200"><![CDATA[2743200,5486400,2743200]]></ColumnWidth>
```

**写进去的办法**：`report table … --widths 12,16,14`（字符数，与 `--columns` 一一对应）。

```bash
frcli report table "$R" --dataset ds1 --at A2 --columns code,name,cnt --header --widths 12,16,10 --apply
```

实测生效：导出后 `ws.column_dimensions['A'].width == 12.0`。
非表格场景（要给任意列设宽）才需要 download → 改 `<ColumnWidth>` 字节 → upload。

实测换算（导出 xlsx 用 openpyxl 读回）：

| XML 值 | 导出结果 | 关系 |
|---|---|---|
| `ColumnWidth` 2743200 | 列宽 9.76953125（字符） | **值 ÷ 280800 = 列宽字符数** |
| `RowHeight` 723900 | 行高 16.35（磅） | **值 ÷ 44200 ≈ 行高磅数** |

数组**不是边界**：只写了 22 列/50 行也能渲染出更多行列（越界部分用 `defaultValue`），不用为长表格补数组。

## 4.7 数据设置（分组 / 列表 / 汇总）—— **头号坑在这**

数据集列格除了"绑哪一列"，还有一维叫**数据设置**，写在 `<RG>` 里
（`RecordGrouper`，`XML_TAG = "RG"`）。**它决定这一格拿到数之后怎么分组/聚合。**

### 三形态

| `--mode` | 界面语义 | XML | 效果（实测） |
|---|---|---|---|
| **`list`**（CLI 默认） | 列表 | `<RG class="com.fr.report.cell.cellattr.core.group.FunctionGrouper"><Attr divideMode="1"/></RG>` | 记录**原样逐条**展开，不去重、不聚合 |
| `group` | 分组 | `<RG class="…FunctionGrouper"/>`（自闭合） | 相同值**合并成一组**；数值列会被**去重** |
| `summary` | 汇总 | `<RG class="…SummaryGrouper"><FN><![CDATA[com.fr.data.util.function.SumFunction]]></FN></RG>` | 按组**聚合**成一个值 |

`--fn` 六选一（**只在 `--mode summary` 时有意义**，写错本地报错）：
`sum` / `count` / `avg` / `max` / `min` / `none`（`none` = 不聚合、取原值）。

### ⚠️ 头号坑：**不写 `<RG>` 服务端按「分组」处理**

`DSColumn.getGrouper()` 在 `<RG>` 缺失时惰性返回 `new FunctionGrouper()`，
其 `divideMode` 初值 `0` = **分组**。所以缺 `<RG>` 与写 `<RG class="…FunctionGrouper"/>`
**逐格结果完全一样**（实测）。后果是数值列被**静默去重**，合计与"按明细算"对不上，
而且**随数据重复模式变化** —— 这就是 §6.1 那条"合计时对时错"的真因（我们的 bug，不是平台）。

### 默认 `--mode list`，什么时候必须换

| 你要的效果 | 用哪个 | 判据 |
|---|---|---|
| "我绑了一列，把记录列出来" | `list`（默认） | 数值列可能重复 ⇒ 用 `group` 会被去重 |
| 左侧维度列相同值合并成一组 | `group` | 只有**确定这一列的值天然是分组键**（地区/品类/编码）时才用 |
| 要合计/计数/平均/最大/最小 | `summary` + `--fn` | 数值列**必须**用这个；`group` 不聚合 |
| 一个汇总行（总计） | `summary` 不给 `--group-by` | 所有列都汇总 → 单行 |

**为什么默认是 `list` 而不是 `group`**：`group` 恰是服务端的隐式缺省，也是
"我没设置所以是原样"这个直觉的反面 —— 用它当默认会静默改数。`list` 才是"原样展开"。

### 怎么用

```bash
# 明细（默认 list，不写 --mode 也是它）
frcli report table "$R" --dataset ds1 --at A2 --columns code,name,cnt --header --apply

# 分组：相同值合并（谨慎用，数值列会被去重）
frcli report table "$R" --dataset ds1 --at A2 --columns 地区,销售员 --mode group --apply

# 分组汇总：地区/销售员 保持分组，销量 汇总(sum)
frcli report table "$R" --dataset ds1 --at A2 --columns 地区,销售员,销量 \
    --mode summary --group-by 地区,销售员 --fn sum --header --apply

# 改**已有**单元格的数据设置（不动内容/样式/扩展）
frcli report cell "$R" --at C3 --set-ds-mode list --apply
frcli report cell "$R" --at D3 --set-ds-mode summary --fn avg --apply
```

- `--mode summary` 时**汇总格自动用 `<Expand/>`（不扩展）**：一个汇总值就是一行，
  再按行扩展没有意义 —— 这也是 `doc/Primary/GroupReport/纵向分组报表.cpt` 的真实做法
  （维度格 `dir="0"`、汇总格 `<Expand/>`）。分组格的扩展方向仍吃 `--expand`。
- **只改绑定会保留原数据设置**（`--at C3 --bind ds1.x`）：否则会把老模板的列表/汇总悄悄改成分组。
- **读**兼容 legacy 包名 `com.fr.report.cellElement.core.*`（1602 个官方模板里有 343+42 处是老包名）。
- `report cell --list` 会显示每格的 `ds_mode` / `ds_fn`。

### 本地会拦的语义错误

| 写法 | 报错 |
|---|---|
| `--mode group --fn sum` / `--mode list --fn max` | `--fn 只在 --mode summary 时有意义` |
| `--fn sum` 但不给 `--set-ds-mode` | `--fn 要跟 --set-ds-mode summary 一起用` |
| `--mode list --group-by x` | `--group-by 只在 --mode summary 时有意义` |
| `--group-by` 的列不在 `--columns` 里 | 报出是哪几列 |
| `--group-by` 覆盖了全部列 | `没有列会被汇总` |
| 对值/公式单元格 `--set-ds-mode` | `不是数据集列单元格（值/公式单元格没有数据设置）` |

### 拦不住的（只能给 warning）

创作命令**只硬拦能在离线确证的东西**（`dsName` 不存在、`s=` 越界、公式语法、XML 良构、
`--fn` 与 `--mode` 搭不搭）。下面两条离线判不出来，所以只出 ⚠ warning + 文档兜底，
**它们的正确性只能靠"导出后逐格读回"来保证**：

| 拦不住的 | 服务端表现 | 唯一判据 |
|---|---|---|
| **列名写错**（要连库才知道有哪些列） | 上传 ok + 导出 ok，**空列** | 导出后逐格读回 |
| **`summary` 用在文本列上** | 导出 ok，**汇总值是 `0`**（dsverifier 实测） | 导出后逐格读回 |

⚠️ 这两条合起来就是"**导出成功几乎等于没验收**"的论据：**凡是有默认值/有外部依赖的设置，
一律导出逐格核对**（§6）。

完整的 Grouper 类表、汇总函数表、语料频次与「我要 X 效果 → 怎么写」对照表见
**`references/cpt-features.md`**。

## 4.8 合计行 / 公式列（两个最常用配方）

```bash
# 公式列：在数据区右边加一列，逐行求值（会跟着扩展走）
frcli report cell "$R" --at D2 --set-formula '=C2/B2' --num-format '#0.0%' --apply

# 合计行：放在数据区**下面一行**，用固定区间聚合
frcli report cell "$R" --at A8 --set-value '合计' --apply
frcli report cell "$R" --at C8 --set-formula '=SUM(C3:C7)' --apply
```

**更稳的"合计"是数据设置，不是 `=SUM()`**：

```bash
# 按组汇总（服务端算好的值，不受扩展区影响）
frcli report table "$R" --dataset ds1 --at A2 --columns 地区,销量 \
    --mode summary --group-by 地区 --fn sum --header --apply
```

实测两条要点：
- **合计行会自动随扩展下移**：数据区从 3 行扩成 6 行时，写在数据区下方的合计行会跟着往下排，
  不用手工改位置（模板 `t4_report.cpt` 实测）。
- **公式列是逐行公式**（`=C3/B3` 这种），不受下面 §6.1 那个"聚合对不上"的影响；
  **跨扩展区的聚合**（`=SUM(C3:C7)`）才要用双通道对合计。

## 5. 合并单元格

合并信息写在**左上角那个 `<C>`** 上：`cs` = 跨几列，`rs` = 跨几行（不写 = 1）。

```xml
<C c="0" r="0" cs="2" s="0">…</C>      <!-- A1:B1 合并 -->
```

CLI：`report cell "$R" --at A1 --set-value "标题" --merge A1:B1 --apply`
（`--merge` 的左上角必须与 `--at` 一致，因为合并信息只存在左上角格）。

## 5.9 导出时的一个常见坑：`11300002` 行高列宽超出页面大小

模板排版偏大时（列宽/行高总和超过纸张），`export excel` 默认走**分页导出**，会报
`错误代码:11300002 行高列宽超出页面大小设置`，产物是 HTML 出错页（CLI 会拦下并报魔数不符）。
加 `--params '{"extype":"simple"}'` 改**原样导出**即可：

```bash
frcli export excel "$R" -o /tmp/x.xlsx --params '{"extype":"simple"}'
```

## 6. 验收（每次都做，别省）

```bash
frcli export excel "$R" -o /tmp/x.xlsx
python3 - <<'PY'
import openpyxl
ws = openpyxl.load_workbook("/tmp/x.xlsx").active
print("merged:", [str(m) for m in ws.merged_cells.ranges])       # 合并区域
print("dims:", ws.dimensions)                                     # 行数够不够
for r in ws.iter_rows(max_row=8, max_col=4):
    print([c.value for c in r])                                   # 逐格内容
print("A2 bold:", ws["A2"].font.bold, ws["A2"].fill.fgColor.rgb)  # 样式
print("C3 fmt:", ws["C3"].number_format)                          # 数字格式
PY
```

### 6.1 ⚠️ 合计对不上 = 你没写数据设置（`<RG>`），不是平台问题

**2026-09 实测闭环。早期两条结论都已撤回**：① "xlsx 聚合引擎静默出错" —— 不存在；
② "同一模板不同时段导出 `4567.7 → 2345.6 → 4567.7`" —— 那是**读错行**：合计行渲染在数据之后的第 6 行，
当时按模板坐标读了第 4 行（第 2 条明细）。实测 26 个变体 × 3 轮：**xlsx 与 csv 逐格全等，从无分歧**。

**真因**：**缺 `<RG>` 的单元格，服务端按「分组」处理**（`DSColumn.getGrouper()` null →
`new FunctionGrouper()`，`divideMode` 初值 0）。分组会把**数值列去重**：

> 明细 `10,10,20,10,30,30` 求和 = **110**（SQL 真值），
> 缺 `<RG>` 时单元格塌缩成 `10,20,10,30`，合计 = **70** —— **3/3 轮稳定复现的静默算错**。

对照实验（同一数据集 `('A',10)('A',10)('A',20)('B',10)('B',30)('B',30)`，**只改 `<RG>`**）：

| 形态 | xlsx 逐格读回 | csv |
|---|---|---|
| **无 `<RG>`** | `A/10, ''/20, B/10, ''/30`（4 行） | 同 |
| `<RG class="…FunctionGrouper"/>`（分组＝缺省） | **与"无 `<RG>`"逐格相同** ← 根因的直接证据 | 同 |
| `<RG class="…FunctionGrouper"><Attr divideMode="1"/></RG>`（列表） | 6 行全展开 | 同 |
| `<RG class="…SummaryGrouper"><FN>…SumFunction</FN></RG>`（汇总） | `A/40, B/70` | 同 |

真机模板在 `demo_group/demo_user/skill测试/dsmode/{P0_no_rg,P1_group,P2_list,P3_summary}.cpt`。

规矩：
1. **写模板时 `<RG>` 必须显式写** —— `report table` 默认 `--mode list`，不会留空；
   手写 XML / `report upload` 时自己保证（`report cell --list` 能核对 `ds_mode`）。
2. **有默认值的字段，"标签不在"不等于"设置没有"** —— 见 `cpt-features.md` §0 的默认值表。
3. **含 `=SUM(...)`/`=COUNT(...)`/比率列的报表，合计仍建议用两条通道对**
   （`export excel` 与 `export csv`/`report image`）：这条是通用戒律，与上面的归因无关，
   它能抓住"数据源本身变了""参数没传对"等其他静默坏法。
4. **最稳的做法：把合计交给数据设置或 SQL** ——
   `--mode summary --group-by <维度> --fn sum`（服务端算好的聚合值），
   或 `union all select '合计', sum(...)`。逐行公式（`=D3/C3`）不受影响。

---

回到"每次都要做"的两条收尾：
- **别用「导出成功」当验收**：上面那些静默坏法导出的都是合法 xlsx。
- 数字格比对要给**容差**（实测同一模板两次导出有 ~4.5e-12 的相对抖动），字符串格可以全等。
- 版面判断看 `ws.dimensions` + 非空格数，不要逐个比样式对象。
- 只读结构核对用 `frcli report cell "$R" --list -f table`（A1/值/公式/绑定/扩展/样式一屏看完）。

## 7. 坑点（每条都是实测的静默失败）

### 7.1 `${x}` 与 `$x` 是两个世界

| 位置 | 唯一正确写法 | 写错的后果 |
|---|---|---|
| 数据集 SQL | `${x}` | 写 `$x` 会把 `$x` 字面量送进 SQL（SQL 报错或条件恒假） |
| 单元格公式 | `$x` | 写 `${x}` 会原样渲染出这 6 个字符 |

两者**都不报错**。CLI 会在写 SQL/公式时本地警告。

### 7.2 参数「既没传值、又没默认值」→ 静默空字符串

`--params` 传了值就一定绑得上（不声明也能绑）；**声明的作用是提供默认值**。
没默认值时用户不带参数打开就是一片空白，导出照样成功。
CLI 对没给默认值的 `--param` 会出 warning。

### 7.3 参数落在 SQL 的语法敏感位置 → `report info/datasets` 报错

`… limit ${topn}` 这种写法，在 REST `format=cpt` 通道（不带默认值）会被替换成 `limit`，
SQL 直接语法错 → `report datasets` / `report info` 报「数据集配置错误」；而 `export`（带默认值）正常。
**优先把参数放在带引号的字符串位置**（`where code >= '${min_center}'`），或在调用时始终传参。

### 7.4 服务端对这些错误全都「照收不误」

> ⚠️ **适用范围**：下面"CLI 现在"这一列说的是**创作命令路径**
> （`report new/cell/dataset/param/style/table --apply`）。
> **`report upload` 只做 XML 良构校验**（+ 根元素必须是 `<WorkBook>`），
> 手写 XML 直接 upload 时，`dsName` 错 / `s=` 越界 / 空数据集名这类**语义问题不会拦**，
> 只会 stderr 提示。**所以手写 XML 请优先走 `report cell/dataset/style` 命令，或 upload 后逐格导出核对。**

| 你写错了什么 | 服务端表现 | 创作命令路径 |
|---|---|---|
| `dsName` 指向不存在的数据集 | 上传 ok + 导出 ok，格子空 | ✅ 本地报错 |
| `columnName` 列名写错 | 上传 ok + 导出 ok，**空列** | ⚠️ 无法离线核对（要连库）→ 出 warning |
| 公式 `=1+` / 括号不配对 | 上传 ok + 导出 ok，格子空 | ✅ 本地报错 |
| 数据集名给空 | 上传 ok + 导出 ok | ✅ 本地报错 |
| `s=` 越界 | 上传 ok + 导出 ok，样式丢失 | ✅ 本地报错 |
| 参数没值又没默认值 | 上传 ok + 导出 ok，内容是空 | ⚠️ warning |
| 残缺 XML | 上传 ok（回读校验还通过）→ 渲染空表 | ✅ `assert_template_bytes` 本地良构校验拦住（**upload 也有效**）|

### 7.5 CDATA 里不能出现 `]]>`

新内容含 `]]>` 时 CLI 直接报错（不会悄悄写出坏 XML）。文本里要写这个序列只能拆开或改写。

### 7.6 `report table` 会**整格替换**目标区域

`report table --at A1 --header` 会改写 A1.. 那几行。先写标题再生成表 → 标题被覆盖。
正确顺序：**先 `report table --at A2`（留 A1 给标题）**，再写 A1。

### 7.7 扩展方向写反不报错

见 §4.2。判断办法：导出后看行数（纵向 = 行变多）还是列数（横向 = 列变多）。
顺带：`--expand none` 时多个值会被**逗号拼成一格**（`"10,10,20,10,30,30"`），也不报错。

### 7.8 `report info` 的 `parameters` 与模板参数不是一回事

`report info.parameters` 现在会并上官方 `template/paras`（含 `tcmd` 之类派生参数），
但**「模板里声明了哪些参数、默认值是多少」要看 `report param --list`**（读模板字节，最准）。

### 7.9 数据集列格没写 `<RG>` = 服务端按「分组」去重（**最贵的一条**）

见 §4.7 与 §6.1。速记：

| 你写的 | 服务端当成 | 后果 |
|---|---|---|
| 没有 `<RG>` | **分组**（`divideMode=0`） | 相同值合并、数值列去重；合计与明细对不上 |
| `<RG class="…FunctionGrouper"/>` | 分组 | 同上（**与"没写"逐格相同**，实测） |
| `<RG …><Attr divideMode="1"/></RG>` | 列表 | 记录原样展开 |
| `<RG class="…SummaryGrouper"><FN>…</FN></RG>` | 汇总 | 按组聚合成一个值 |

判据：`report cell "$R" --list` 看每格的 `ds_mode`；老模板两种包名都要认
（`com.fr.report.cellElement.core.*` 是老写法，1602 个官方模板里有 385 处）。

## 8. 相关文档

- **`references/cpt-patterns.md`** —— **8 类复杂报表配方集**（分组小计 / 交叉表 / 条件属性 /
  多数据集 / 参数联动 / 日期维度 / 分页 / 公式实战）：每条都有 XML 片段 + 等价 CLI + **逐格实测导出** + 坑
- `references/cpt-features.md` —— **语料普查**：`<RG>`/`<FN>`/`<Condition>`/`<Highlight>`/`<Expand>`/`<C>` 的
  频次、真实片段、默认值表，以及「我要 X 效果 → XML 怎么写」对照表
- `references/cpt-xml.md` —— cpt 结构与**定点**字节读取（`report edit` 的底座，含改 SQL 的姿势）
- `references/remotedesign.md` —— 远程设计 RPC 协议（换 FineReport 版本后要重新核对报文时看）
- `SKILL.md` §3 命令树 / §4 安全约束 / §6.7 改模板内容 / §6.15 数据设置那条坑 / §6.16 复杂报表四个静默错
- `docs/探索/cpt服务端模型-逆向.md` —— 反编译得到的服务端模型（每条带类/方法出处）
