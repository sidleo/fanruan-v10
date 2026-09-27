# cpt 特性普查（1602 个官方模板语料 + 服务端 jar 反编译 + 真机对照件）

> 回答三个问题：**这个标签/属性是什么意思**、**它出现的频次有多主流**、**我要 X 效果该怎么写**。
> 读法：先看 §0 的通用教训，要写数据设置直接跳 §1，要查某个标签跳 §3–§7，要"照着抄"看 §8。

## 取证范围与复现方法

| 来源 | 是什么 | 怎么复现 |
|---|---|---|
| 官方语料 | `<FineReport 安装目录>/webapps/webroot/WEB-INF/reportlets/` 下 **1602 个 .cpt**（demo + doc） | 直接 `grep` / 写脚本扫（**只读**） |
| 服务端契约 | `fine-report-engine-10.0.jar` 里 `com.fr.report.*` / `com.fr.data.*` 的 `readXML/writeXML` 与字段初值 | `unzip` 出 class → `java -jar <开发工作目录>/tools/cfr.jar <class>` |
| 真机对照件 | 服务器 `demo_group/demo_user/skill测试/dsmode/` 下 12 张**只改一个变量**的模板 | 见 §1.4、§3.2 的实测表 |

**所有频次都是 .cpt 语料里 `<标签` 的出现次数**（同一模板多处会重复计数），不是"多少个模板"。
推断而无实测的条目一律标 **待验证**。

## 0. 通用教训：这个格式里"标签不在" ≠ "设置没有"

FineReport 的 XML 是**省略默认值**风格的：`writeXML` 只写"与字段初值不同"的部分。
于是**缺省值就是真正生效的值**，而它经常不是你要的那个：

| 元素 | 不写时的实际语义 | 教训 |
|---|---|---|
| `<RG>` | **分组**（`DSColumn.getGrouper()` 惰性 `new FunctionGrouper()`，divideMode 初值 0） | 不写 ≠ "没设置"，而是"按分组去重" |
| `<Expand>` | **不扩展**（且多值会被逗号拼成一格，见 §3.2） | 不写 ≠ "自动铺开" |
| `<Complex>` | order=0（不排序） | |
| `<Condition>` | 无过滤（condition=null） | |
| `<Result>` | 用本列原值（等价 `$$$`） | 可省 |

**动手规矩**：有默认值的字段，要么显式写对，要么先查本文件的默认值列确认可接受；
写完**必须导出逐格读回**（`references/cpt-authoring.md` §6），"导出成功"什么都证明不了。

---

## 0.1 每条的可信度标记（**先看这个再信内容**）

本文件的每条都按下面的等级标注，**只有一个来源的不要当"双保险"用**：

| 标记 | 含义 | 能直接信吗 |
|---|---|---|
| 🟢 **实测** | 在本服务器上真跑过，有导出物/逐格读回/服务端返回为证 | 能 |
| 🔵 **jar 出处** | 反编译 `fine-*.jar` 得到，文中给了类名 + 方法/行号 | 能（换 FineReport 版本要重核） |
| 🟡 **语料统计** | 1602 个官方 .cpt 里数出来的频次/写法，**只说明"官方这么写"，不说明"服务端这么解释"** | 当写法参考，别当语义定论 |
| 🔴 **推测待验证** | 没实测、没 jar 出处，靠类名/常识推的 | **别直接用**，先验证 |
| ⚪ **已证伪** | 曾经写过、后来被推翻 | 只看修正后的结论 |

**为什么要有这一栏**：本项目已经栽过三次"把推测当结论"——
`t="CC"` 被当成"跨列占位"（实为图表单元格）、`<Condition>` 被当成"列表模式标记"（实为过滤条件）、
xlsx 合计被当成"平台静默出错"（实为我们没写 `<RG>`）。**留错描述比留空更危险。**

---

## 1. 数据设置 `<RG>`（最重要的一节）

> 可信度：`<RG>` 三形态的**渲染结果** 🟢 实测（§1.4 四张对照件，xlsx/csv 双通道）；类名、`divideMode` 取值、`<FN>` 写法、缺省语义 🔵 `DSColumn`/`FunctionGrouper`/`SummaryGrouper` 反编译；各类频次 🟡 语料统计；`MonoGrouper`/`IndexGrouper` 的类存在 🔵 但**语料 0 次**，其 XML 写法是从 `writeXML` 读出来的（🔴 未实测渲染）。


`<RG>` = `RecordGrouper`（`XML_TAG = "RG"`），是 `<O t="DSColumn">` 的子元素，
决定"这一格拿到数之后怎么分组/聚合"。**它只对数据集列有定义**（值/公式单元格没有数据设置）。

### 1.1 三形态 + 全部 Grouper 类（语料频次）

| 界面语义 | 类（`<RG class="…">`） | 写出来的 XML | 语料频次 |
|---|---|---|---|
| **分组**（= 缺省） | `com.fr.report.cell.cellattr.core.group.FunctionGrouper` divideMode 0 | `<RG class="…FunctionGrouper"/>`（自闭合） | **4904** |
| **列表** | 同上，divideMode 1 | `<RG class="…FunctionGrouper"><Attr divideMode="1"/></RG>` | 283 |
| **连续分组**（**只合并相邻**的相同值） | 同上，divideMode 2 | `<RG class="…FunctionGrouper"><Attr divideMode="2"/></RG>` | 3 |
| **自定义分组** | 同上，`isCustom` + 公式 | `<RG class="…FunctionGrouper"><Custom isCustom="true"/><FC><![CDATA[公式]]></FC></RG>` | — |
| **汇总** | `com.fr.report.cell.cellattr.core.group.SummaryGrouper` | `<RG class="…SummaryGrouper"><FN><![CDATA[com.fr.data.util.function.SumFunction]]></FN></RG>` | 393 |
| 自定义 | `com.fr.report.cell.cellattr.core.group.CustomGrouper` | 语料里出现的独立类形态 | 8 |
| 一条记录一组（也是列表） | `…MonoGrouper` | `<RG class="…MonoGrouper"/>` | **0**（可用，语料没人用） |
| 取第 N 条 | `…IndexGrouper` | `<RG class="…IndexGrouper"><Attr index="0"/></RG>` | **0** |

⚠️ **legacy 包名**：老模板里同一个类写成 `com.fr.report.cellElement.core.FunctionGrouper`（343 处）、
`…SummaryGrouper`（42 处）、`…CustomGrouper`（2 处）。**写入只用新包名，读取必须两种都认** ——
只认新包名会把老模板的数据设置读成"没有"，而"没有"在服务端等于分组，改一格就把它的设置改坏了。

⚠️ `<RG>` 缺省（自闭合）**不是**"没设置"：`FunctionGrouper.writeXML` 在 `divideMode==0` 时**故意不写** `<Attr>`。

**divideMode 三档的语义已逐格实测**（dsverifier，2026-09，重复值**不相邻**的数据集 `10,20,10`）：

| 形态 | 行数 | 合计 |
|---|---|---|
| `divideMode=0` 分组 | 2 行（`A/10`, `''/20` —— **不相邻的 10 也被合并**） | **30** |
| `divideMode=2` 连续分组 | 3 行（`A/10`, `''/20`, `''/10` —— **只合并相邻**） | **40**（= 真值） |

⇒ "分组"是全量去重合并，"连续分组"只合并相邻相同值 —— 又一个"选错档位就静默算错"的样本。

### 1.2 汇总函数 `<FN>`（`com.fr.data.util.function.*`）

`<FN>` 的内容是**类全名**（`writeXML` = `startTAG("FN").textNode(function.getClass().getName())`）。
该包**共 13 个 class**（反编译实测）：`DataFunction`(接口) / `AbstractDataFunction` / `DataFunctionUtils`
三个是基础设施，可实例化的函数 **10 个** —— 其中 7 个是标量聚合，3 个是数据集族（`DataSetFunction` 及其
子类 `TableDataSetFunction` / `CurrentContextDataSetFunction`）。

| CLI `--fn` | 类 | 语料频次 |
|---|---|---|
| `sum` | `SumFunction` | 340 |
| `count` | `CountFunction` | 47 |
| `avg` | `AverageFunction` | 2 |
| `max` | `MaxFunction` | 2 |
| `min` | `MinFunction` | 2 |
| `none` | `NoneFunction`（不聚合，取原值） | **0** |

其余：`DateFunction` 语料 0 次（语义**待验证**）；`DataSetFunction` 族**不是标量聚合**，CLI 一律本地报错、
不暴露。`<FN>` **只出现在 SummaryGrouper 里**（语料 FN 393 = SummaryGrouper 393，一一对应）——
所以**不能**用 `<FN>` 来判断分组/列表。

### 1.3 `DSColumn` 的完整子元素契约（`DSColumn.readXML` / `writeXML`）

```
Attributes → Condition → Complex → RG → SortFormula → Comparator → SelectCount → Result → Parameters
```
（另有 legacy `<GC>` 与 `<RG>` 同义；`Object|O` 子元素等价于 `Result`）

| 子元素 | 作用 | 读 | 写 |
|---|---|---|---|
| `<Attributes dsName columnName>` | 绑定数据集列（`dbName` 是 legacy 别名） | ✅ | ✅ |
| `<Condition class="…">` | **数据过滤**（与数据设置正交，见 §4） | ✅ | 只读展示 |
| `<Complex order= reselect=>` | 排序 / 重选 | ✅ | 只读展示 |
| **`<RG>`** | **数据设置** | ✅ 兼容 legacy | ✅ |
| `<SortFormula>` | 自定义排序公式 | ✅ | 只读展示 |
| `<Comparator>` | 自定义比较器 | 只读 | — |
| `<SelectCount>` | 取前 N / 后 N / 奇偶行 | 只读 | — |
| `<Result>` | 本列值再套一层表达式（`$$$` = 原值） | ✅ | 默认不写 |
| `<Parameters>` | 该列自己的参数 | — | 空占位 |

**规范形状**（Designer 实际写出来的，语料 4467/5696 = **78%** 逐字节一致）：

```xml
<O t="DSColumn">
<Attributes dsName="ds1" columnName="销量"/>
<Complex/>
<RG class="com.fr.report.cell.cellattr.core.group.FunctionGrouper"/>
<Parameters/>
</O>
```

**`<Result>` 默认不写**（5696 个 DSColumn 里只有 708 个带它）。它只在需要表达式时才写，
语料里真实用过：`$$$/1000`(24)、`=$$$`(14)、`ROUND($$$,0)`(6)、`$$$/1000*-1`(4)、
`if($$$,"已付","未付")`(3)、`seq()`(3)、`货主城市+$$$`(3)。

### 1.4 三形态的**真机实测**（同版面只改 `<RG>`）

数据集（6 条，含重复键与重复值）：`('A',10) ('A',10) ('A',20) ('B',10) ('B',30) ('B',30)`
版面：`A1/B1` 表头、`A2=ds1.grp`、`B2=ds1.v`，两格都 `<Expand dir="0"/>`。
**服务器**：`demo_group/demo_user/skill测试/dsmode/{P0_no_rg,P1_group,P2_list,P3_summary}.cpt`
（生成脚本见本节末）。`export excel` 与 `export csv` **两条通道逐格完全一致**：

| 模板 | `<RG>` | xlsx 逐格读回 |
|---|---|---|
| `P0_no_rg` | **没有 `<RG>`** | `[['grp','v'],['A',10],['',20],['B',10],['',30]]` |
| `P1_group` | `<RG class="…FunctionGrouper"/>` | **`[['grp','v'],['A',10],['',20],['B',10],['',30]]`** ← 与 P0 逐格相同 |
| `P2_list` | `<Attr divideMode="1"/>` | `[['grp','v'],['A',10],['A',10],['A',20],['B',10],['B',30],['B',30]]`（6 行） |
| `P3_summary` | `grp` 分组 + `v` 汇总(sum)、`Expand none` | `[['grp','v'],['A',40],['B',70]]` |

**结论（P9 根因的直接证据）**：`P0 ≡ P1` ⇒ **不写 `<RG>` 服务端就是按分组处理**。
`P1` 只剩 4 行、`v` 列去重成 `10,20,10,30`（求和 **70**），而明细 6 行求和是 **110**（SQL 真值）——
**"合计对不上"就是这么来的：稳定复现的静默算错（3/3 轮），不是"时对时错"。**

> 早期把这条记成"xlsx 聚合引擎静默出错（xlsx 与 csv 不一致）"，**已撤回**：实测 26 个变体 × 3 轮
> xlsx 与 csv **逐格全等**；当时看到的"不一致"是**读错行**（合计行渲染在数据之后的第 6 行，
> 却按模板坐标读了第 4 行）。本次四张对照件同样 xlsx ≡ csv。

三条必须记住的判据：

1. **绑了一列就想"原样列出来" ⇒ 必须写 `list`**（`group` 会静默去重，这是服务端的缺省）。
2. **要合计/计数/平均 ⇒ 只写 `summary` + `<FN>`**，别指望 `group` 顺手帮你聚合（它只是分组）。
3. **老模板里 `<RG>` 可能缺失**（那就是分组），改它的其它属性时要按"分组"理解，别当"没设置"。

⚠️ 第 4 条（同样静默）：**`SummaryGrouper` 用在文本列上会得到 `0`**，不报错、导出照成功
（dsverifier 实测）。汇总列必须是数值列；列类型离线查不到（要连库），所以 CLI 在
`--mode summary` 与 `--set-ds-mode summary` 时都出一句 warning，导出后必须核对汇总值。

生成对照件的脚本（可复现，`sys.path` 指向本仓库 `src`）：

```python
from frcli import cptxml as x
SQL = ("select 'A' grp,10 v union all select 'A',10 union all select 'A',20 "
       "union all select 'B',10 union all select 'B',30 union all select 'B',30")
t = x.empty_skeleton()
t = x.add_dataset(t, x.dataset_xml("ds1", "demo_conn", SQL), "ds1")
t = x.put_cell(t, "A2", x.cell_xml(0, 1, binding="ds1.grp", expand="v", ds_mode="list"))[0]
t = x.put_cell(t, "B2", x.cell_xml(1, 1, binding="ds1.v", expand="v", ds_mode="list"))[0]
```

---

## 2. 单元格值 `<O>`：全部 `t`/`class` 组合

`t=` 的解析链（🔵 **jar 出处，已完整走通**）：
`<O t="X">` → `GeneralXMLTools.readObject`（`GeneralXMLTools:301-308`，取 `t` 属性）
→ `GeneralXMLTools.Object_Tokenizer`，**实际实例由 `EngineModule.start():99` 装入**
= `new ReportXMLUtils.ReportObjectTokenizer()`（`EngineModule.startXMLReadObjectTokenizer():149`）
→ 先走 `BaseObjectTokenizer.tokenizerObject`（标量/公式/图片）
→ 未命中再走 `ReportXMLUtils.tokenizeDetailObject`（`ReportXMLUtils:119` 起：`CC`/`CP`/`DSColumn`/`SubReport`/`RichText`/…）。

| 写法 | 含义 | 语料频次 | 可信度 |
|---|---|---|---|
| `<O><![CDATA[文本]]></O>` | 静态文本 | 18797 | 🔵 `BaseObjectTokenizer.isString():106` |
| `<O t="DSColumn">…</O>` | 数据集列（唯一有 `<RG>` 的类型） | 5696 | 🔵 `ReportXMLUtils.tokenizeDetailObject:137` |
| `<O t="Formula" class="Formula"><Attributes>…</Attributes></O>` | 公式（老写法） | 2924 | 🔵 `BaseObjectTokenizer:72` |
| `<O t="XMLable" class="com.fr.base.Formula"><Attributes>…</Attributes></O>` | 公式（新写法，CLI 用这个） | 2765 | 🔵 `BaseObjectTokenizer:99`（按 `class` 属性 newInstance） |
| `<O t="I"><![CDATA[0]]></O>` | 整数 | 2100 | 🔵 `BaseObjectTokenizer:48`（FR 自己把 `Integer` 拼成 **`Inteter`**，两种都认） |
| `<O t="CC">` | **图表单元格**（`ChartCollection`） | 672 | 🔵 `ReportXMLUtils.tokenizeDetailObject:120` → `StableFactory.createXmlObject("CC")`；注册在 `ChartModule.init()` |
| `<O t="D">` | 小数 | 620 | 🔵 `BaseObjectTokenizer:42`（`D`/`Double`） |
| `<O t="BigDecimal">` / `t="BigInteger"` | 高精度数 | 341 / 10 | 🔵 `BaseObjectTokenizer:57,60` |
| `<O t="Date">` | 日期 | 71 | 🔵 `BaseObjectTokenizer:63` |
| `<O t="B">` | 布尔 | 20 | 🔵 `BaseObjectTokenizer:45`（`B`/`Boolean`） |
| `<O t="RichText">` | 富文本 | 18 | 🔵 `ReportXMLUtils.tokenizeDetailObject:152`（"`<RichChar styleIndex=>` 逐段样式"这半句是 🟡 语料观察） |
| `<O t="Image">` / `t="XMLable" class="com.fr.general.ImageWithSuffix"` | 图片 | 202 / 14 | 🔵 `BaseObjectTokenizer:81`；`ImageWithSuffix` 走 `XMLable`+`class` 分支 |
| `<O t="SubReport">` | 子报表 | 6 | 🔵 `ReportXMLUtils.tokenizeDetailObject:142` |

> **2026-09 修正（`t="CC"`）**：早期把它记成"跨列/占位（合并区内的续格）"——那是 ⚪ **已证伪的推测**。
> 语料 672 处 `<O t="CC">` **全部**含 `<Chart>`、零例外；真相见 `docs/探索/图表与控件模型.md` §A.1。

**写侧的 `t=` 从哪来**（🔵）：`GeneralXMLTools.writeObject:310-326` → `Object_XML_Writer_Finder.as(object)`
→ `ObjectXMLWriter.type()`（写 `t`）与 `.className()`（写 `class`）；
`BaseObjectXMLWriterFinder.as()`（`BaseObjectXMLWriterFinder:23-72`）按 Java 类型分派
`NULL/BOOLEAN/INTEGER/LONG/DOUBLE/FLOAT/BIGI/BIGD/DATE/IMAGE/FARRAY/FORMULA/…`。

`<PrivilegeControl/>` 与 `<Expand>` 是 `<C>` 的固定成员，缺了**不影响渲染**（🟢 实测，cpt-verifier），
但 CLI 生成的格子一律带上。

---

## 3. 扩展 `<Expand>`（`com.fr.report.cell.cellattr.CellExpandAttr`）

> 可信度：`dir` 的语义与三种取值 🟢 实测（8 张对照件，§3.2）；属性清单与缺省值 🔵 `CellExpandAttr.readXML/writeXML`；`extendable`/`isCover` **🔴 推测待验证**（语料 0 次，单格实测看不出作用）。


### 3.1 契约

| 属性 | 缺省 | 语义 |
|---|---|---|
| `dir` | **2 = 不扩展** | 0=纵向扩展 / 1=横向扩展 / 2=不扩展（3 = 待验证） |
| `extendable` | 0 | 0=Both / 1=… / 2=… / 3=…  **待验证**（见 §3.2 实测） |
| `isCover` | false | 待验证 |
| `multiNumber` | -1 | 扩展倍数 |
| `order` | 0 | 扩展后排序（与子元素 `<SortFormula>` 配对） |
| `leftParentDefault` | true | false 时用 `left` 指定左父格 |
| `upParentDefault` | true | false 时用 `up` 指定上父格 |
| 子元素 `<SortFormula>` | — | 扩展后排序公式 |

### 3.2 真机实测（8 张对照件，同一数据集、单格、只改 `<Expand>`）

| 写法 | 导出结果 | 结论 |
|---|---|---|
| `<Expand dir="0"/>` | 6 行竖排 `10,10,20,10,30,30` | **纵向扩展** |
| `<Expand dir="1"/>` | 1 行 6 列 | **横向扩展** |
| `<Expand/>` | **1 格 `"10,10,20,10,30,30"`** | **不扩展，多值被逗号拼成一格** |
| `<Expand extendable="1"/>` | 与 `<Expand/>` 完全一样 | **单格测不出它的作用**（待验证） |
| `<Expand extendable="2"/>` / `="3"` | 同上 | 同上 |
| `<Expand dir="0" multiNumber="2"/>` | 与 `dir="0"` 一样 | 纵向时无差异 |
| `<Expand dir="0" isCover="true"/>` | 与 `dir="0"` 一样 | 无差异 |

关于 `extendable`：**它单独写不改变扩展方向**（实测），语料里 **0 次**出现，
`CellExpandAttr` 的常量名是 `Both_EXTENDABLE=0 / Vertical=1 / Horizontal=2 / None=3` ——
与 `dir` 的 0/1/2 明显不是同一套语义。它多半只在**有父格**时才起作用（"允许被哪个方向的父格扩展"），
**本文件不给结论，标「待验证」**；要用它请先造带父子格的对照件实测。

⚠️ **新坑（静默）**：`<Expand/>` 的格里如果有多个值，会被**逗号拼成一个字符串**
（`"10,10,20,10,30,30"`）写进一格 —— 导出成功、看着"有数据"，其实版面已经错了。
数据列绑了 `<Expand/>` 就是这个后果。

语料频次：无属性 36685、`dir="0"` 5143、`dir="1"` 200，其余是 `left/leftParentDefault/up/upParentDefault/order/multiNumber`
的组合（最多的一种 `left + leftParentDefault` 507 次）。

---

## 4. 过滤与条件 `<Condition>`（5 个类）—— **与数据设置正交**

> 可信度："`<Condition>` 是过滤条件、与数据设置正交" 🔵 `DSColumn.readXML` + `dsmode` 共存证据（🟢 见 §1.4）；五个类的名字与频次 🟡 语料统计；各类的**语义描述**多为 🔴 推测（从类名推的），只有 `ListCondition` 空元素 = 不过滤是 🔵。


`<Condition>` 在 `DSColumn` 里被读成 `this.condition`，作用是**过滤行**
（`condition.evalTableData(dataModel, rows, col, calculator)`），**不是**"列表模式"。
同一个类族还被 `<Highlight>`（条件属性）、图表 `ConditionAttr`、填报 `DMLConfig` 复用。

| 类 | 语义 | 语料频次 | 真实片段 |
|---|---|---|---|
| `com.fr.data.condition.ListCondition` | 条件列表（多条件 and/or），空 = 不过滤 | 1163 | `<Condition class="com.fr.data.condition.ListCondition"/>` |
| `com.fr.data.condition.CommonCondition` | 单条件（列 与 值/别的列 比较） | 1079 | `<Condition class="com.fr.data.condition.CommonCondition"><CNUMBER><![CDATA[1]]></CNUMBER><CNAME><![CDATA[销售员]]></CNAME><Compare op="0"><SimpleDSColumn dsName="ds1" columnName="销售员"/></Compare></Condition>` |
| `com.fr.data.condition.FormulaCondition` | 公式为真 | 1429 | `<Condition class="com.fr.data.condition.FormulaCondition"><Formula><![CDATA[len($$$) = 0]]></Formula></Condition>` |
| `com.fr.data.condition.ObjectCondition` | 与常量比较（条件属性最常用） | 848 | `<Condition class="com.fr.data.condition.ObjectCondition"><Compare op="2"><O t="I"><![CDATA[100]]></O></Compare></Condition>` |
| `com.fr.chart.chartattr.ChartCommonCondition` | 图表专用 | 50 | — |

`<Condition>` 内可嵌 `<JoinCondition join="0">`（语料 1083 处）做关联/多条件组合。

**出现位置分布**（用位置归因，别只按标签名找）：
`C/O` 下 433+540+18（数据设置区的过滤）、`C/HighlightList/Highlight` 下 1262+404+375（条件属性）、
`Chart/Plot/ConditionCollection/...` 下 300+（图表）、`ReportWriteAttr/*/DMLConfig` 下 217（填报）。

---

## 5. 条件属性 `<Highlight>`

> 可信度：结构与子元素频次 🟡 语料统计；动作类名（`ForegroundHighlightAction` 等）是从语料片段里读出来的 🟡；**各动作的渲染效果未实测**（🔴 待验证）。


```xml
<HighlightList>
<Highlight class="com.fr.report.cell.cellattr.highlight.DefaultHighlight">
<Name><![CDATA[条件属性1]]></Name>
<Condition class="com.fr.data.condition.ObjectCondition">
<Compare op="2"><O t="I"><![CDATA[100]]></O></Compare>
</Condition>
<HighlightAction class="com.fr.report.cell.cellattr.highlight.ForegroundHighlightAction">
<Foreground color="-65536"/>
</HighlightAction>
</Highlight>
</HighlightList>
```

- `<Highlight>` 的 `class` 语料里 2036 处是 `…cellattr.highlight.DefaultHighlight`，
  14 处是老的 `com.fr.report.highlight.DefaultHighlight`（读要兼容）。
- 一个 `<Highlight>` 可以挂 **1–3 个** `<HighlightAction>`（语料 1161+366+347 是单 action，
  108+38+17 是两个，另有 2 个是三个）。
- `<HighlightAction>` 的子元素分布：`O`(764，动作是公式) / `Background`(479) / `FRFont`(225) /
  `Foreground`(194) / `Scope`+`Background`(109) / `Border`(69) / `P`(41) / `NameJavaScriptGroup`(12) /
  `Widget`(2) / `MyAlign`(2) / `RowHeight`(1)。
- 三个条件类的分工（语料）：公式条件 1262、对象条件 404、条件列表 375。

---

## 6. 排序 / 选取 / 结果

> 可信度：`Complex@order` ≠ 0 时排序 🔵 `DSColumn.dealwith_sort:171`；`Result` 的 `$$$` = 本列原值 🔵 `DSColumn.shouldCCGroupByResult()`；`SortFormula` 公式示例 🟡 语料；`SelectCount` 的具体语义 🔴 待验证。


| 元素 | 作用 | 语料频次 | 真实片段 |
|---|---|---|---|
| `<Complex order="1" reselect="true"/>` | `order`≠0 时按 `SortFormula`（或本值）排序；`reselect`=重选 | 无属性 5356 / `reselect` 13 / `order=2` 11 / `order=1` 9 | — |
| `<SortFormula><![CDATA[…]]></SortFormula>` | 排序依据；不带 `=` 时当作公式求值 | 72（DSColumn 内） | `if($b==1,$$$,-$$$)`、`=D3`、`INDEX(FR,"B","D","A","C","E")` |
| `<SelectCount>` | 取前 N / 后 N / 奇偶行（`FilterTypeEnum`） | 语料 20 处组合里出现 | — |
| `<Result><![CDATA[$$$]]></Result>` | 本列值再过一层表达式 | 708 | 见 §1.3 |

---

## 7. `<C>` 与它的子元素

> 可信度：属性组合与子元素顺序 🟡 语料统计（1602 个模板全覆盖，样本足够大）；`c`/`r` 从 0 起 🟢 实测；`CellGUIAttr`/`CellPageAttr`/`Present` 等**未生成也未实测**，只知它们会出现（🔴 语义待验证）。


### 7.1 属性（语料全部组合，只有这 5 个键）

| 组合 | 频次 | 说明 |
|---|---|---|
| `c r s` | 36259 | 最常见 |
| `c cs r s` | 5556 | 横向合并 |
| `c r` | 2640 | 无样式 |
| `c cs r rs s` | 679 | 双向合并 |
| `c cs r rs` | 451 | |
| `c r rs s` | 446 | 纵向合并 |
| `c cs r` / `c r rs` | 87 / 4 | |

缺省即省略：`cs`=1、`rs`=1、`s`=无样式。`c`/`r` 从 **0** 起（`B3` = `c="1" r="2"`）。

### 7.2 子元素顺序（语料实测，`<Expand>` 永远最后）

```
O → PrivilegeControl → NameJavaScriptGroup → CellGUIAttr → CellPageAttr
  → Widget → HighlightList → Present → CellInsertPolicy → Expand
```

只有"实际用到的才出现"。最常见的几种：

| 子元素序列 | 频次 |
|---|---|
| `O, PrivilegeControl, Expand` | 16909 |
| `PrivilegeControl, Expand` | 15831 |
| `PrivilegeControl` | 2752 |
| `O, PrivilegeControl, Widget, Expand` | 2555 |
| `O, Expand` | 1786 |
| `O, PrivilegeControl, CellGUIAttr, CellPageAttr, Expand` | 1095 |
| `O, PrivilegeControl, HighlightList, Expand` | 639 |

`CellGUIAttr`(printContent/showAsDefault/adjustmode)、`CellPageAttr`(pageBeforeRow 等)、
`CellInsertPolicy`、`Present`、`Widget`（填报控件）本 CLI 暂不生成，但**读的时候不能把它们当成异常**。

---

## 8. 「我要 X 效果 → XML 该怎么写」（照抄表）

| 我要的效果 | XML 关键写法 | CLI |
|---|---|---|
| 一列记录原样展开（明细） | `<RG class="…FunctionGrouper"><Attr divideMode="1"/></RG>` | `report table … --mode list`（默认） |
| 相同值合并成一组 | `<RG class="…FunctionGrouper"/>` | `report table … --mode group` |
| 按组求和 | `<RG class="…SummaryGrouper"><FN><![CDATA[…SumFunction]]></FN></RG>` | `report table … --mode summary --group-by <维度列> --fn sum` |
| 按组计数/平均/最大/最小 | 同上换 `CountFunction`/`AverageFunction`/`MaxFunction`/`MinFunction` | `--fn count/avg/max/min` |
| 不聚合，但显式声明 | `<FN><![CDATA[…NoneFunction]]></FN>` | `--fn none` |
| 相邻相同值才合并（连续） | `<Attr divideMode="2"/>` | 手写 XML（CLI 不生成） |
| 一条记录一组 | `<RG class="…MonoGrouper"/>` | 手写（等价 effect 用 list） |
| 取第 N 条 | `<RG class="…IndexGrouper"><Attr index="0"/></RG>` | 手写 |
| 一列变多行（纵向铺开） | `<Expand dir="0"/>` | `--expand v` |
| 一行变多列（横向铺开） | `<Expand dir="1"/>` | `--expand h` |
| 不扩展 | `<Expand/>` | `--expand none` |
| 这一格过滤掉部分行 | `<Condition class="com.fr.data.condition.FormulaCondition"><Formula><![CDATA[…]]></Formula></Condition>` | 手写 |
| 值超阈值变红 | `<HighlightList><Highlight class="…DefaultHighlight"><Condition class="…ObjectCondition">…</Condition><HighlightAction class="…ForegroundHighlightAction"><Foreground color="-65536"/></HighlightAction></Highlight></HighlightList>` | 手写 |
| 按某列排序 | `<Complex order="1"/><SortFormula><![CDATA[列名]]></SortFormula>` | 手写 |
| 本列值再套个表达式 | `<Result><![CDATA[ROUND($$$,0)]]></Result>` | 手写 |
| 跨列合并 | `<C c="0" r="0" cs="2">` | `report cell --at A1 --merge A1:B1` |

---

## 9. 语料频次总表（.cpt，1602 个文件）

| 标签 | 次数 | | 标签 | 次数 |
|---|---|---|---|---|
| `<C` | 46159 | | `<Highlight` | 2050 |
| `<Expand` | 43315 | | `<RowHeight` | 1694 |
| `<O` | 34393 | | `<ColumnWidth` | 1693 |
| `<Attributes` | 16810 | | `<JoinCondition` | 1083 |
| `<Complex` | 5696 | | `<Result` | 708 |
| `<RG` | 5606 | | `<FN` | 393 |
| `<Condition` | 4569 | | `<SortFormula` | 72 |
| `<Parameter` | 2317 | | | |

---

## 10. 相关文档

- `references/cpt-authoring.md` —— 怎么造模板（命令 + 配方 + 验收）
- `references/cpt-xml.md` —— 定点字节读写（`report edit` 的底座）
- `docs/探索/cpt服务端模型-逆向.md` —— 反编译得到的服务端模型（类/方法出处）
