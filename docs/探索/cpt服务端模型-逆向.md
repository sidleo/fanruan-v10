# .cpt 服务端模型（从 `<FineReport 安装目录>` 的 jar 逆向）

> 本文件是**服务端语义的权威来源**：每条都标了类与方法出处，不是从语料猜的。
> 语料普查（用到了什么）见 `references/cpt-features.md`；两边的交集才是"能安全写什么"。

## 0. 一句话结论（P9 根因）

`com.fr.report.cell.cellattr.core.group.DSColumn`：

```java
public RecordGrouper getGrouper() {
    if (this.grouper == null) {
        this.grouper = new FunctionGrouper();   // ← 没有 <RG> 时的缺省 = FunctionGrouper
    }
    return this.grouper;
}
```
`FunctionGrouper.divideMode` 字段初值 `0`，常量 `GROUPING_MODE=0 / LIST_MODE=1 / CONTINUUM_MODE=2`。

⇒ **单元格不写 `<RG>` = 按「分组」处理**（相同值合并展开），既不是列表也不是汇总。
这正是"合计值对不上、且随数据重复模式时对时错"的机制 —— **是我们的 bug，不是平台问题**。

## 1. 单元格 `<C>`

`com.fr.report.cell.AbstractCellElement:382-385`（全部**属性**，缺省即省略）：

| 属性 | 默认 | 含义 |
|---|---|---|
| `c` | 0 | 列（0 起） |
| `r` | 0 | 行（0 起） |
| `cs` | 1 | 横向合并列数（colspan） |
| `rs` | 1 | 纵向合并行数（rowspan） |
| `s` | — | `<StyleList>` 里的样式下标（0 起） |

`<C>` 的子元素：`<O>`（值）、`<PrivilegeControl/>`、`<Expand>` 或 `<CellExpandAttr>`、`<HighlightList>`。

## 2. 值对象 `<O>`

`<O t="…">` 的 `t` 决定类：无 `t` = 纯文本；`t="XMLable"` + `class="com.fr.base.Formula"` = 公式；
`t="DSColumn"` = 数据集列；`t="I"` = 整型常量（语料里 `com.fr.data.condition.ObjectCondition` 的比较值也用）。

### `DSColumn` 的完整子元素契约（`com.fr.report.cell.cellattr.core.group.DSColumn.readXML`）

| 子元素 | 作用 |
|---|---|
| `<Attributes dsName=… columnName=… />` | 数据集名 + 列名（旧字段 `dbName` 同义） |
| `<Condition class="…">` | 数据过滤/关联条件 |
| `<Complex order="n" reselect="bool"/>` | 扩展顺序与是否重选 |
| `<Result><![CDATA[$$$]]></Result>` | 值表达式，`$$$` = 本列原值；可写 `FORMAT($$$,…)` 等。**可省略**：语料 5696 个 DSColumn 里只有 708 个写了 Result，Designer 默认不写 |
| `<SortFormula>` | 排序依据（分组常用，如 `bd_id`） |
| `<Comparator>` | 自定义比较器 |
| `<SelectCount>` | 取前 N 条 |
| **`<RG>`** | **数据设置（分组/列表/汇总）—— 见 §3；缺失即分组** |
| `<Parameters>` | 单元格级参数 |
| `<Object>`/`<O>` | 等价于 `Result`（公式形式） |

## 3. 数据设置 `<RG>`（`RecordGrouper.XML_TAG = "RG"`）

| 界面语义 | 类 | 写出来的 XML |
|---|---|---|
| **分组**（＝缺省） | `FunctionGrouper` divideMode=0 | `<RG class="com.fr.report.cell.cellattr.core.group.FunctionGrouper"/>` |
| **列表** | `FunctionGrouper` divideMode=1 | `<RG class="…FunctionGrouper"><Attr divideMode="1"/></RG>`（**语料实测 283 处，这是列表的唯一真实写法**） |
| **连续** | `FunctionGrouper` divideMode=2 | `<Attr divideMode="2"/>` |
| **列表（另一种）** | `MonoGrouper` | `<RG class="…MonoGrouper"/>`（`doGroup` 一条记录一个 Group；语料里 0 次，可用但罕见） |
| **汇总** | `SummaryGrouper` | `<RG class="…SummaryGrouper"><FN>com.fr.data.util.function.SumFunction</FN></RG>` |
| 取第 N 条 | `IndexGrouper` | `<RG class="…IndexGrouper"><Attr index="n"/></RG>` |
| 自定义 | `CustomGrouper` | `<Custom isCustom="true"/><FC>公式</FC>`（与 FunctionGrouper 同族） |

`FunctionGrouper.writeXML` 在 `divideMode==0` 时**不写** `<Attr>` —— 所以"分组"看上去就是个自闭合标签。

> ⚠️ **勘误（2026-09-27，dsauthor 实测推翻，我原先写错了）**：
> `<Condition class="com.fr.data.condition.ListCondition">` **不是**"列表模式"的标记！
> `DSColumn.readXML` 把它读进 `this.condition`，在 `dealwith_condition_group_sort_select_result` 里
> 是**先按它过滤行**，属于**数据过滤条件**，与数据设置**正交**。证据：语料里 `<Condition>` 与
> `FunctionGrouper`(261) / `SummaryGrouper`(65) **共存**（若是模式标记不可能与汇总共存），且
> `<Condition>` 家族 5 个类还被 `Highlight`、图表、填报复用。
> **列表模式的唯一真实写法就是 `divideMode="1"`。**

**`<FN>` 里写的是函数类的全名**（`SummaryGrouper.writeXML`：`startTAG("FN").textNode(function.getClass().getName())`）。
`com.fr.data.util.function.*` 共 14 个类，可作标量聚合的 6 个：
`SumFunction` / `CountFunction` / `AverageFunction` / `MaxFunction` / `MinFunction` / `NoneFunction`。
其余（`DataSetFunction` / `TableDataSetFunction` / `CurrentContextDataSetFunction` / `DateFunction`）语义不同，不要当聚合暴露。

⚠️ **legacy 包名**：本地 1602 个模板里有 325 处写的是旧包名
`com.fr.report.cellElement.core.FunctionGrouper`。**写只用新包名，读必须两种都认**。

## 4. 扩展 `<Expand>`（`com.fr.report.cell.cellattr.CellExpandAttr`）

### 4.0 实测闭环（网络 E1：同数据集、单格，8 个对照件）

数据集 6 条 `('A',10)('A',10)('A',20)('B',10)('B',30)('B',30)`，只改写法：

| 写法 | 导出结果 |
|---|---|
| `<Expand dir="0"/>` | 6 行竖排 → **纵向** |
| `<Expand dir="1"/>` | 1 行 6 列 → **横向** |
| `<Expand/>`（dir 缺省 2） | **1 格，值被逗号拼成 `10,10,20,10,30,30`** → 不扩展 |
| `<Expand extendable="N"/>`（不给 dir，N 为**整数** 1/2/3） | 与 `<Expand/>` **完全一致** → `extendable` **单独写不改变方向** |
| `<Expand extendable="1\|2\|3"/>`（**字面量**，非法） | 服务端 `NumberFormatException: For input string: "1\|2\|3"` → **出错页** |
| `<Expand dir="0" multiNumber="2"/>` / `isCover="true"` | 与 `dir="0"` 无差异 |

⚠️ **两个静默坑**：
1. `dir` 缺省（`<Expand/>`）= **不扩展**，而"不扩展的格里多个值会被逗号拼成一格"——
   导出看着"有数据"，实际是一串拼接值。
2. `extendable` 不是方向开关，别指望它。**且它必须是整数**（位掩码），写成 `"1|2|3"` 这种
   "枚举的枚举"字面量会让服务端抛 `NumberFormatException` 渲染出错页 —— 本文件早先的 `1|2|3` 只是我表示
   "取值为 1 或 2 或 3" 的简写，**不是可写进 XML 的内容**。

### 4.1 属性契约

| 属性 | 默认 | 含义 |
|---|---|---|
| `dir` | **2** | 扩展方向：**0=纵向、1=横向、2=不扩展** |
| `extendable` | 0 | 0=Both、1=纵向可扩、2=横向可扩、3=不可扩 |
| `isCover` | false | 扩展是否覆盖 |
| `multiNumber` | −1 | 倍数 |
| `order` | 0 | 顺序 |
| `leftParentDefault` | true | 左父格是否默认 |
| `left` | — | 左父格（如 `O2`） |
| `upParentDefault` | true | 上父格是否默认 |
| `up` | — | 上父格 |
| 子元素 `<SortFormula>` | — | 扩展排序 |

`writeXML` **省略一切默认值** ⇒ `<Expand/>` = 不扩展；`<Expand dir="0"/>` = 纵向；`<Expand dir="1"/>` = 横向。
与实测完全一致（`dir` 记反不报错，只是表格长歪）。

## 5. 其余

- **数据集** `<TableData name class="com.fr.data.impl.DBTableData">`：`<Parameters>`（参数与默认值）、
  `<Attributes share maxMemRowCount>`、`<Connection class="…NameDatabaseConnection"><DatabaseName>`、
  `<Query>`（SQL，参数写 `${名字}`）、`<PageQuery>`。
- **模板参数** `<ReportParameterAttr><Parameters>`：决定单元格公式里的 `$名字` 能否解析；
  `--params` 传了值就绑上，声明的唯一作用是**提供默认值**；无值又无默认 → **静默空字符串**。
- **样式** `<StyleList>` 第 n 条被 `s="n"` 引用；`<Format class="com.fr.base.CoreDecimalFormat" roundingMode="6">` 管数字格式。

## 5.5 规范形状（语料实测，Designer 实际写出来的）

```
<C c=".." r=".." s="..">
<O t="DSColumn">
<Attributes dsName=".." columnName=".."/>
<Complex/>
<RG class="com.fr.report.cell.cellattr.core.group.FunctionGrouper"/>   ← 或 SummaryGrouper+FN / divideMode=1
<Parameters/>
</O>
<PrivilegeControl/>
<Expand/>
</C>
```
语料 4467/5696（78%）的 DSColumn 就是这个形状。**我们早期生成的形态两头都不对**：
多了 `<Result>$$$</Result>`（Designer 默认不写）、少了 `<RG>`（于是被服务端按"分组"解释）。

## 5.6 交叉表（实测跑通，2026-09-27）

**交叉表不需要显式父子格** —— 引擎自动把「最近的上方扩展格」当**上父格**、「左侧扩展格」当**左父格**，
两者的交叉积就是交叉表。四类格（官方 `demo/NewbieGuide/交叉报表.cpt` 的真实结构）：

| 角色 | 值对象 | 数据设置 | `<Expand>` |
|---|---|---|---|
| 列维度（可多层） | `DSColumn` | `FunctionGrouper` | **`dir="1"`** |
| 行维度（可多层） | `DSColumn` | `FunctionGrouper` | **`dir="0"`** |
| **交叉值格** | `DSColumn` | **`FunctionGrouper`（不是汇总！）** | `<Expand/>`（不写方向，隐式继承上/左父格） |
| 汇总列/行 | `DSColumn` | `SummaryGrouper` + `<FN>…SumFunction</FN>` | `<Expand/>` |
| 公共总计行 | `Formula` | — | `=SUM(C4)`（列总计自动按列走） |

**实测**（`skill测试/cross.cpt` 与 `cross4.cpt`，数据为字面量 union）：
- 列维度 2 个产品 → 5 列；换成 4 个产品 → **自动变 7 列**，版面自动撑开
- 缺失的 (行,列) 组合**留空格**，不串位、不补 0（稀疏矩阵正确）
- 行汇总 = 逐行之和、列总计 = 逐列之和、总计 = 全部之和（`4050 = 550+750+1250+1500`）全部逐格核对通过
- xlsx 与 csv 一致

**高效套路**：**拿官方模板当脚手架**。1602 个官方 cpt 里几乎每种效果都有现成样例
（`demo/NewbieGuide/交叉报表.cpt`、`doc/Advanced/...`），换掉 `<DatabaseName>` 与 `<Query>` 即可复用，
比从零试错快得多。

## 5.6.0 生产规模实测（2026-09-27）

在授权测试目录用**真实生产数据**建了一张多级交叉表 `cross_real.cpt`：
**行 = 销售大区 × 销售渠道（两层纵向），列 = 部类（横向），值 = `sum(restore_sales_amt)`，`sdt='20260926'`**。

导出 xlsx 逐格读回（294 行 × 10 列）：

| 校验项 | 结果 |
|---|---|
| 数据行数 | 290 行（大区×渠道 组合自动展开） |
| 动态列 | **7 个部类列自动生成**（+ 1 个汇总列） |
| 行内「明细之和 == 行汇总」 | **290/290 全部一致**（0 处不符） |
| 列总计之和 == 表尾总计 | ✅ 精确相等 `154,116,593.45` |
| 稀疏格 | 缺失组合留空，不串位、不补 0 |

⚠️ **动态列的顺序 = 数据首次出现顺序，不是排序**（实测列序 `12,13,11,10,98,14,15`）。

**列序控制已实测闭环**（独立验证者，2026-09-27）：
- `<Complex order="1" reselect="true"/>` —— 单独写即按**本格值升序**排
- 再加 `<SortFormula><![CDATA[if($$$="B",1,if($$$="A",2,3))]]></SortFormula>`
  （位置：`<RG>` 之后、`<Parameters>` 之前）→ 实测列序 **B, A, C** 生效，且值与标签**不串位**
- 后续 `report cell` 写操作**不会抹掉** `SortFormula`
- CLI 目前**不暴露**该开关（只能 download → 改 XML → upload）

可用模板片段：`docs/验证/证据/配方复现/§2-SortFormula-可用的模板片段.cpt`

**这套流程本身就是一条可复用的"报表级 SQL 探针"**：拿 CLI 建一张单格绑定的模板 → 导出 → 读回，
就能在**没有 SQL 客户端**的情况下借报表引擎查数（本次用它探出最新可用分区 `20260926`）。

## 5.6.1 空数据边界（实测）

**0 行数据不会让报表崩**，普通报表与交叉表都一样：**版面、表头、合并区域全部保留**，数据区空白。

| 场景 | 导出结果 |
|---|---|
| 普通报表 0 行 | 维度 `A1:B2`：表头 `k,v` 在，数据行空 |
| 交叉表 0 行 | 维度 `A1:D5`：标题/表头/总计行都在，列维度为空，**汇总格 = `0`**，总计 = `0` |

⚠️ **注意汇总格在无数据时是 `0` 而不是空** —— 业务上若期望"无数据留空"，这里会显示 0，容易误读。

⚠️⚠️ **排查空数据的教训**：我第一次测出"0 行数据导出失败（平台出错页）"，实际是我的 SQL 本身非法
（`select 'A' k,1 v where 1=0` **缺 `from`** → Impala `ParseException`）。
**判据**：这类问题先跑 `report datasets <模板>` —— 数据集配置错误会带出平台原文与出错 SQL 位置；
`report datasets` 干净而导出失败，才说明是渲染层问题。**先验证实验本身，再下结论。**

## 5.7 条件属性 `<Highlight>`

```xml
<Highlight class="com.fr.report.cell.cellattr.highlight.DefaultHighlight">
<Name><![CDATA[条件属性3]]></Name>
<Condition class="com.fr.data.condition.ListCondition">
<JoinCondition join="0">
<Condition class="com.fr.data.condition.ObjectCondition">
<Compare op="3"><O t="D"><![CDATA[0.5]]></O></Compare>
</Condition>
</JoinCondition>
</Condition>
<HighlightAction class="com.fr.report.cell.cellattr.highlight.BackgroundHighlightAction">…</HighlightAction>
</Highlight>
```

**`Compare.op` 取值表**（`com.fr.data.core.Compare` 的常量，权威）：

| op | 含义 | op | 含义 |
|---|---|---|---|
| 0 | `=` | 8 | 以…结束 |
| 1 | `≠` | 9 | 不以…结束 |
| 2 | `>` | 10 | 包含 |
| 3 | `≥` | 11 | 不包含 |
| 4 | `<` | 12 | IN |
| 5 | `≤` | 13 | NOT IN |
| 6 | 以…开始 | 14 | 为空 |
| 7 | 不以…开始 | 15 | 不为空 |

**条件类**：`ObjectCondition`（值比较）/ `FormulaCondition`（公式）/ `ListCondition`（多条件组合，内嵌 `JoinCondition join="0"`）
**动作类**（语料频次）：`ValueHighlightAction`(764) / `BackgroundHighlightAction`(588) / `RowHeightHighlightAction`(284) /
`FRFontHighlightAction`(225) / `ForegroundHighlightAction`(194) / `BorderHighlightAction`(69) /
`PageHighlightAction`(41) / `ColWidthHighlightAction`(32) / `HyperlinkHighlightAction`(12)

> 语料里 `FormulaCondition` 出现最多（1405）—— 实际报表大量用公式做条件（如 `$$$>0`、`ROW()%2=0` 隔行变色）。
> 样例见官方 `热力图.cpt`（三段背景色：<0.5 / 0.5~0.7 / ≥0.7）。

## 5.8 分页与重复标题行（实测闭环，2026-09-27）

### 5.8.1 每页重复标题行 = **报表级 `<ReportPageAttr><HR/></ReportPageAttr>`**，不是单元格属性

`com.fr.page.stable.ReportPageAttr` 存 **4 组重复区间**（`FT` 对，缺省 `(-1,-1)` = 关闭）：

```xml
<ReportPageAttr>
<HR F="1" T="1"/>     <!-- 重复标题行：第 F..T 行每页重复（0 基行号） -->
<FR F=".." T=".."/>   <!-- 重复表尾行 -->
<HC F=".." T=".."/>   <!-- 重复标题列 -->
<FC F=".." T=".."/>   <!-- 重复表尾列 -->
<UPFCR COLUMN="true" ROW="true"/>   <!-- 页面冻结列/行 -->
</ReportPageAttr>
```
读取：`ReportPageAttr.readXML` —— 属性名就是 **`F`（from）/ `T`（to）**，缺省 `-1`；
写出：`writeXML` 仅在 `>= 0` 时才写属性 ⇒ 语料里 `<HR/>` 自闭合 = 不重复。
分页引擎在 `PaginateReportPageGenerator.paginate_according_to_repeat` 里用
`getRepeatHeaderRowFrom/To` 决定每页补哪些行（`RepeatRowHelper`）。

**实测证据**（120 行明细、表头行人为加高到 200pt，其余完全一致）：

| 版本 | PDF 页数 |
|---|---|
| 无 `<HR>` | **6 页** |
| `<HR F="1" T="1"/>` | **7 页**（+2552 字节） |

表头矮的时候看不出来（都是 6 页，只差 258 字节）—— **验这类设置必须放大它的占位**，否则得不到信号。

**并且做了视觉确证**（PDF 光栅化后看图）：带 `<HR F="1" T="1"/>` 的第 2 页**顶部真的重复出现了表头**
（`REPEATHDR 门店编码 / REPEATHDR 名称`），不带的那版第 2 页直接是数据行。数值证据（6→7 页）+ 视觉证据双确认。

> ⚠️ 这一条我第一次做的时候**替换 `<HR/>` 静默失败了**（正则没匹配上、又没断言），于是得到"6 页、页 2 无表头"的假结论 ——
> 差点把已经验对的东西推翻。**注入/替换 XML 做实验时，替换后必须断言真的改到了**（`re.subn` 的计数、或断言目标串存在）。

### 5.8.2 ⚠️ `<CellPageAttr repeat>` **不是**"重复标题行"

`CellPageAttr` 的 `value` 是位掩码（缺省 **63**）：bit0–3 = 行/列前后强制分页（置位=不分页）、
**bit4 = `repeat`**、bit5 = `breakOnPaginate`。缺省 63 ⇒ `isRepeat()` **本来就是 true**，
`writeXML` 只在为 false 时写 `repeat="false"`（语料里 `repeat="false"` **0 次**）。
所以"没写 `CellPageAttr` 也不重复标题行"与它无关 —— **别拿它当重复标题行的开关**。

`<CellPageAttr/>` 的真正用途是**强制分页**：真机语料里出现的是
`<CellPageAttr pageAfterRow="true"/>`(23) / `pageBeforeRow="true"`(20) / `breakOnPaginate="false"`(51)。

**`<C>` 子元素规范顺序**（语料 2015 个含 CellPageAttr 的样本统计，读取是顺序敏感的）：
```
<O> → <PrivilegeControl/> → <CellGUIAttr/> → <CellPageAttr/> → [CellInsertPolicy | HighlightList] → <Expand>
```

### 5.8.3 冻结（两处，别混）

| XML | 类 | 作用 |
|---|---|---|
| `<ReportSettings><FrozenColumnRow columnrow="c,r"/></ReportSettings>` | `ReportSettings.writeFrozenColumnRow` | 冻结分界位置 |
| `<ReportPageAttr><UPFCR COLUMN="true" ROW="true"/></ReportPageAttr>` | `ReportPageAttr.usePageFrozenColumn/Row` | 是否启用页面冻结 |

⚠️ **冻结是预览态滚动交互**，导出产物里不会有可见差异 —— "导出看不出效果"**不是 bug**，判据只能是
XML 往返 + 平台预览页。

## 5.9 页眉页脚 / 页码（实测闭环，2026-09-27 + 看图验证）

### 结构（`<Header>`/`<Footer>` 是 `<ReportAttrSet>` 里与 `<ReportSettings>` **同级**的兄弟）

```xml
<ReportAttrSet>
<ReportSettings headerHeight="0" footerHeight="600000">   <!-- ⚠️ 高度必须 >0，语料默认 "0" = 不渲染 -->
<PaperSetting/>
<Background name="ColorBackground" color="-1"/>
</ReportSettings>
<Footer reportPageType="0">
<Background name="NullBackground"/>
<LeftList/>
<CenterList>
<HFElement className="com.fr.base.headerfooter.FormulaHFElement">
<FRFont name="SimSun" style="0" size="72"/>
<Formula content='"第 " + $$page_number + " 页 / 共 " + $$totalPage_number + " 页"' text="0"/>
</HFElement>
</CenterList>
<RightList/>
</Footer>
</ReportAttrSet>
```
- **内容分三栏**：`<LeftList/>` / `<CenterList>` / `<RightList/>`（空的就自闭合）
- **页码变量：`$$page_number`（当前页）、`$$totalPage_number`（总页数）**
- `<Header reportPageType="0">` 同理（把 `Footer` 换成 `Header`）

### `HFElement` 家族（`com.fr.base.headerfooter`，9 类）

| 类 | 用途 |
|---|---|
| `TextHFElement` | 纯文本 |
| **`FormulaHFElement`** | 公式（**语料里唯一实际用到的**，页码也走它） |
| `DateHFElement` / `TimeHFElement` | 日期 / 时间 |
| `ImageHFElement` | 图片 |
| `NewLineHFElement` | 换行 |
| `PageNumberHFElement` / `NumberOfPageHFElement` | 页码 / 总页数（`PageNumberHFElement extends TextHFElement`；语料 0 次，都用公式） |
| `ParameterHFElement` | 参数 |

### ⚠️ 两个坑

1. **`footerHeight="0"`（缺省）⇒ 页面根本不渲染页脚** —— 写了 `<Footer>` 也没用，且**不报错**。
2. **`<Header>`/`<Footer>` 放错父节点会被静默忽略**：我第一次把块塞在 `</ReportPageAttr>` 之后（挂在 `<Report>` 下），
   导出正常、页脚没出现。

### 🔎 顺带建立的验证回路：**PDF 可视化**

`report image` **不渲染页眉页脚**（它输出的是版面流，不是分页结果），所以这类"只在分页产物里生效"的特性
**必须看 PDF**。做法：

```bash
<venv>/bin/pip install pypdfium2            # 自带 pdfium，无需系统依赖
python -c "import pypdfium2 as pdfium; pdf=pdfium.PdfDocument('/tmp/x.pdf'); \
           print(len(pdf)); pdf[0].render(scale=1.6).to_pil().save('/tmp/p1.png')"
```
然后把 PNG 裁到关心的区域**看图**。本次据此确认 `FOOTERMARKER-1/1` 真的渲染在页面底部居中。

## 6. 怎么用这份文件

- 写模板前先查 §3/§4 的**缺省值**：凡是"缺了会被服务端按某个默认解释"的，**必须显式写**（`<RG>` 就是血的教训）。
- 读别人的模板时同样按这张表判断，**不要用"标签在不在"当"设置有没有"**（缺省是隐式的）。
- 改命令实现时优先信这份文件（有类/方法出处），语料频次只作参考。
