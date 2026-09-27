# 复杂报表配方集 · 第二辑（图表 / 参数控件 / 钻取 / 层次坐标 / 分页）

> 与 `references/cpt-patterns.md`（第一辑：分组小计·交叉表·条件属性·多数据集·参数过滤·日期·公式）互补，
> **本辑只收第一辑没碰过的能力**。每条都满足：**真机建出来 → 导出 → 逐格/逐像素读回 → 记录**。
> 样例在服务器 `demo_group/demo_user/skill测试/patterns/`（2026-09，FineReport V10）。
> 服务端模型出处：`docs/探索/图表与控件模型.md`（dsauthor 只读逆向）、
> `docs/探索/cpt服务端模型-逆向.md` §5.8/§5.9（Lead）。

> ⚠️ **照抄配方前先改 `$B`**：本辑与第一辑的 `$B` 都指向**团队样例目录** `…/skill测试/patterns/`，
> 照抄 `report new "$B/xxx.cpt"` 会试图往样例目录写（不带 `--force` 会被响亮拒绝，**带 `--force` 就覆盖样例了**）。
> **请把 `$B` 改到你自己的目录**（如 `…/skill测试/mydir`）。
> 另：`report list` **只返回模板**，看 `_目录说明.txt` 这种非模板文件要用 `report ws-list`。

## 0. 三条验收方法论（本辑最值钱的部分，先看这里）

### 0.1 不同特性要走**不同的验收通道**（用错通道会得到假阴性）

| 特性 | 正确通道 | 用错的后果 |
|---|---|---|
| 行内数据（值/公式/合计/条件属性） | **xlsx 逐格读回**（openpyxl）+ csv 双通道 | —— |
| **图表** | `report image`(PNG) **或** `export pdf` + 出图看；xlsx 里是**嵌入图片**（`xl/media/image1.png`），**逐格读回永远是 0 个非空格** | 只读 xlsx → 以为"图表没生成" |
| **页眉页脚 / 页码 / 重复标题行 / 分页** | **`export pdf` + pdfium 出图看**（`report image` **不渲染分页结果**，它输出版面流 → 假阴性） | 用 image 验页脚 → 永远看不到 |
| **冻结行列** | 只能验 XML 往返 + 预览页交互；**导出态本来就无差异** | 记成"功能没生效/未确证" |

出图看（实测环境已装纯 Python 光栅化器，无系统依赖）：

```bash
python -m pip install pypdfium2          # 已装：<venv>/bin/python
<venv>/bin/python - <<'PY'
import pypdfium2 as pdfium
pdf = pdfium.PdfDocument('/tmp/x.pdf')
print("pages:", len(pdf))
im = pdf[len(pdf)-1].render(scale=2.0).to_pil()
im.crop((0, im.height-120, im.width, im.height-10)).save('/tmp/footer.png')   # 只看页脚区
PY
```

### 0.2 验"占位型"设置：**先把占位放大**，否则拿不到信号

重复标题行这类设置，表头矮的时候两版 PDF **只差 258 字节**、页数一样（看起来"没生效"）。
把表头行加高到 200~600pt 再比页数，信号立刻出来（实测 3 页 → 7 页，见 §W5）。

### 0.3 改 XML 做对照实验：**注入必须断言成功**

`str.replace` / 正则**不匹配就静默什么都不做**，你比的是两份相同文件却会得出"这个字段没用"。
规矩：`re.subn(...)` 断言 `n == 1`；改完**从服务端回读**确认目标串在；先证明两份输入真的不同（比 SHA256），再比输出。
本辑作者就因此浪费了一轮（`<HR/>` 注入没匹配上，PDF 逐字节相同）。

---

## W1. 图表（柱形 / 折线 / 饼 / 环形）

**效果**：单元格里放一张 VanChart，数据源 = 数据集（分类列 / 系列列 / 数值列 + 聚合函数）。

**样例**：`patterns/chart_column.cpt`、`chart_line.cpt`、`chart_pie.cpt`、`chart_err_col.cpt`（静默错对照）

**一条命令**（真实跑过；默认 dry-run）

```bash
R="$B/chart_column.cpt"
frcli report new "$R" --apply
frcli report dataset "$R" --add ds1 --conn demo_conn \
  --sql "select '东区' cat,'A' series,100 val union all select '东区','B',200
         union all select '西区','A',300 union all select '西区','B',400" --apply
# 多系列柱形图（图例 = series 列，X 轴 = cat 列）
frcli report chart "$R" --at A1 --dataset ds1 --type column \
  --category cat --series series --value val --fn sum --title "各区域 A/B 销量" --show-title --apply
# 折线：--type line    单张饼：--type pie --category cat --value val（不给 --series）
# 环形：--type ring    只读回看：frcli report chart "$R" --list
```

**XML 结构**（三层包装，`<O t="CC">` = **图表单元格**，不是"跨列占位"）

```xml
<C c="0" r="0" cs="9" rs="20">                     <!-- 图表占 9 列 × 20 行 -->
<O t="CC">
<LayoutAttr selectedIndex="0"/>
<Chart name="默认" chartClass="com.fr.plugin.chart.vanchart.VanChart">
<Chart class="com.fr.plugin.chart.vanchart.VanChart">
<GI>…</GI><ChartAttr isJSDraw="true" isStyleGlobal="false"/>
<Title4VanChart>…<O><![CDATA[标题]]></O><TitleVisible value="true"/>…</Title4VanChart>
<Plot class="com.fr.plugin.chart.column.VanChartColumnPlot">…</Plot>
<ChartDefinition>
<OneValueCDDefinition seriesName="series" valueName="val"
    function="com.fr.data.util.function.SumFunction">
<Top topCate="-1" topValue="-1" …/>
<TableData class="com.fr.data.impl.NameTableData"><Name><![CDATA[ds1]]></Name></TableData>
<CategoryName value="cat"/>
</OneValueCDDefinition>
</ChartDefinition>
</Chart></Chart></O>
<PrivilegeControl/><Expand/></C>
```

**实测（`report image` 出图逐像素看）**

| 类型 | 命令 | 结果 |
|---|---|---|
| 柱形（多系列） | `--type column --category cat --series series --value val` | 东区 100/200、西区 300/400，图例 A/B ✓ 与数据逐值一致 |
| 折线 | `--type line …` | 两条折线 100→300、200→400 ✓ |
| 饼（单张） | `--type pie --category cat --value val`（不给 series） | 一张饼：东区 300 / 西区 700（= 30%/70%）+ 图例 ✓ |
| 饼（每分类一张） | `--type pie --category cat --series series --value val` | 两张饼（东区、西区），扇区按 series ✓ |
| 环形 | `--type ring …` | 同上，中间挖空 ✓ |

**关键语义（都是实测，不是猜）**

1. **系列语义**：`--series` 给了 ⇒ `seriesName`=系列列（图例）+ `CategoryName`=分类列；**不给** ⇒
   柱/折用 `seriesName=""`（空）+ `CategoryName`=分类列 = **正常的单系列图**；
   饼/环用 `seriesName`=扇区列 + `CategoryName`=**空** = 单张饼（官方 `饼图.cpt` 就是 `<CategoryName value=""/>`）。
2. ⚠ **把 `seriesName` 也写成分类列**（我第一版）⇒ 每个分类自成一个系列：图例变成分类名、X 轴重复、柱子只剩 N 根（实测图）。
3. **不写标题块 ⇒ 服务端给默认标题「新建图表标题」**（裁剪掉 `<Title4VanChart>` 后图上真出现这行字）。
   CLI 缺省写 `TitleVisible="false"` 的空标题块；`--title X --show-title` 才显示。
4. **`cs`/`rs` 决定图表占多大**（官方样例：柱 9×20、折 9×19、饼/环 7×17）；`report chart --at` 要落在**空格子**上。
5. **图型 = `<Plot class>`**（`VanChartColumnPlot` / `VanChartLinePlot` / `PiePlot4VanChart`），
   `wrapperName`+`requiredJS` 决定前端渲染器（`VanChartWrapper` / `RosePieChart`），**没有类型码**。
6. **模板可以从官方语料裁到很小**：删掉图例/坐标轴/数据表/缩放/条件属性/提示框样式等 11 个子树，
   只留 `Chart/GI/ChartAttr/Plot/ChartDefinition` —— 实测照样出图（CLI 内置的就是这个裁剪版）。
   实测尺寸：**模板体 1.2~1.5KB；加上 `<ChartDefinition>` 与标题块后完整单元格 2.2~2.5KB**
   （对应官方原样 6.9~10.7KB）。
7. **`--type` 收的别名**：`column`/`bar`/`柱形图`/`柱状图`、`line`/`折线图`、`pie`/`饼图`、
   `ring`/`donut`/`环形图`（`report chart` 的报错信息会自己列出全部取值）。

**🔴 写错的对照（静默错）**

| 写法 | 服务端 | 结果 |
|---|---|---|
| `--category NOSUCH`（列名不存在） | `status: ok`，导出正常 | **图照画但完全错**：X 轴没有分类标签、A/B 各自塌成一根柱（400 / 600 = 系列合计）、Y 轴刻度也跟着变 —— 不报错、不空白，最容易蒙混过关 |
| 数据集名不存在 | **本地直接报错**（`--dataset` 会在模板字节里查） | 明确报错 ✅ |
| 分类列名写对、**值列是纯非数字文本** | `status: ok` | 图能出但值塌成 0/空。⚠ 限定：**数字样字符串（`'100'`）照样正常聚合**（验证者实测），只有**纯非数字文本**才塌 |
| `--at` 落在已有内容的格子上 | 本地直接报错 | 明确报错 ✅ |

---

## W2. 参数面板控件（下拉 / 日期）

**效果**：给模板加正经的参数面板（下拉框 + 日期控件），控件驱动模板参数。

**样例**：`patterns/w2_widget.cpt`（下拉+日期）、`w2_widget_errname.cpt`（静默错对照）

完整可复现（**四步都要**：数据集 → 表 → 参数 → 控件；漏掉前三步只会得到"有面板没数据"的空报表，
实测 dims `A1:B3` 全空而 `status: ok`）：

```bash
R="$B/w2_widget.cpt"
frcli report new "$R" --apply
frcli report dataset "$R" --add ds1 --conn demo_conn \
  --sql "select * from (select '华东' area,100 amt union all select '华南',200
         union all select '华北',300) t where area = '\${area}'" --param area=华东 --apply
frcli report table "$R" --dataset ds1 --at A2 --columns area,amt --header --labels "地区,金额" --apply
frcli report widget "$R" --param area --type combo --options 华东,华南,华北 --default 华东 --apply
frcli report widget "$R" --param d1   --type date  --default 2026-09-01 --x 200 --apply
frcli report widget "$R" --list -f table          # 只读回看
frcli export excel "$R" -o /tmp/w2.xlsx                             # → 华东/100
frcli export excel "$R" -o /tmp/w2b.xlsx --params '{"area":"华南"}'   # → 华南/200
```

**XML 契约**（面板是 **WorkBook 级**节点，排在 `<ReportParameterAttr>` 之后）

```xml
<ParameterUI class="com.fr.form.main.parameter.FormParameterUI">
<Parameters/>
<Layout class="com.fr.form.ui.container.WParameterLayout">
<WidgetName name="para"/><WidgetAttr description=""><PrivilegeControl/></WidgetAttr>
<Margin top="0" left="0" bottom="0" right="0"/><Border>…</Border>
<Background name="ColorBackground" color="-526086"/>
<LCAttr vgap="0" hgap="0" compInterval="0"/>
<Widget class="com.fr.form.ui.container.WAbsoluteLayout$BoundsWidget">
<InnerWidget class="com.fr.form.ui.ComboBox">
<WidgetName name="area"/>                  <!-- ★ 控件名 = 参数名，绑定就靠这个 -->
<LabelName name="area:"/>
<WidgetAttr description=""><PrivilegeControl/></WidgetAttr>
<Dictionary class="com.fr.data.impl.CustomDictionary">
<CustomDictAttr><Dict key="华东" value="华东"/>…</CustomDictAttr>
</Dictionary>
<widgetValue><O><![CDATA[华东]]></O></widgetValue>
</InnerWidget>
<BoundsAttr x="30" y="20" width="120" height="21"/>
</Widget>
</Layout></ParameterUI>
```

- **控件类**：`ComboBox`(下拉) / `DateEditor`(日期) / `TextEditor` / `ComboCheckBox`(下拉多选) / `NumberEditor`
- **字典**：`CustomDictionary`（手工选项，最可控）/ `DatabaseDictionary` / `TableDataDictionary` / `FormulaDictionary`
- **绑定证据（jar）**：`com.fr.form.main.parameter.FormParameterUI:260` `getWidgetByName(parameter.getName())`
  ⇒ **`<WidgetName name="X">` 的 X 就是要驱动的模板参数名**

**实测**

```
report widget --list → count=2
  area: ComboBox    options=[华东=华东,华南=华南,华北=华北]  default=华东
  d1:   DateEditor  default=2026-09-01
导出（默认）        → 华东/100
导出 --params '{"area":"华南"}' → 华南/200      ← 参数仍然生效（面板不挡参数）
```

**🔴 写错的对照**：**控件名 ≠ 参数名**（样例 `w2_widget_errname.cpt` 就是这么建的）

```bash
R2="$B/w2_widget_errname.cpt"      # ⚠️ 必须定义，否则 $R2 为空会被写范围守门拒绝
# 模板参数叫 area，控件名却写成 AREA；--no-declare 很关键 ——
# 不加它 --default 会给模板**补出一个 AREA 参数**（于是默认导出变成 华南，与"不联动"混在一起）
frcli report widget "$R2" --param AREA --type combo --options 华东,华南 --default 华南 \
    --no-declare --apply
# → status: ok；report widget --list 显示 AREA=华南；模板参数仍只有 area（未被污染）
```

⚠ **这条的"症状"不能用导出值判**（验证者指出）：**导出通道根本不走参数面板** ——
控件名对（`area`）或错（`AREA`），**默认导出都是 `华东/100`**（那是模板参数默认值）。
所以实测只确证两点：① 写错**不报错**（`status: ok`、面板 XML 正常写入）；
② **"控件是否联动"只能在预览页点一下验**（名字对 ⇒ 选华南变 华南/200；写成 `AREA` ⇒ 选了不生效）。
本辑验的是「XML 与官方样例同构 + 参数仍生效」，**联动本身未在导出通道确证**。

ℹ️ **服务端参数名大小写不敏感**（验证者实测）：`--params '{"AREA":"华南"}'` 能覆盖已声明的 `area`；
`area` 与 `AREA` 两份声明并存时**后声明的那份胜**；两个都传 → **无行返回**。
⇒ 规范：**参数名统一小写，别用"大小写不同"去构造对照**（结果不可解释）。

---

## W3. 钻取超链接（跳转另一张报表并传参）

**样例**：`patterns/w3_link.cpt`

```bash
# 钻取：把本行的中心传给目标报表
frcli report link "$R" --at A3 --to "demo_group/demo_user/skill测试/patterns/r1_group_subtotal.cpt" \
    --param center='=$A3' --param flag=1 --apply
# 网页链接
frcli report link "$R" --at A2 --type web --to "https://www.fanruan.com" --frame _blank --apply
frcli report link "$R" --list -f table
```

**正确形态：`<NameJavaScriptGroup>` 是 `<C>` 的直接子元素**（语料 260 处都这样）

```xml
<C c="0" r="2">
<O t="DSColumn">…</O>
<PrivilegeControl/>
<NameJavaScriptGroup>
<NameJavaScript name="超链接1">
<JavaScript class="com.fr.js.ReportletHyperlink">
<JavaScript class="com.fr.js.ReportletHyperlink">      <!-- 同名嵌套一层，Designer 就这么写 -->
<Parameters>
<Parameter><Attributes name="center"/>
<O t="Formula" class="Formula"><Attributes><![CDATA[=$A3]]></Attributes></O></Parameter>
<Parameter><Attributes name="flag"/><O><![CDATA[1]]></O></Parameter>
</Parameters>
<TargetFrame><![CDATA[_self]]></TargetFrame>
<Features width="600" height="400"/>
<ReportletName showPI="true"><![CDATA[目标报表路径]]></ReportletName>
</JavaScript></JavaScript></NameJavaScript>
</NameJavaScriptGroup>
<Expand/></C>
```

- 类型：`com.fr.js.ReportletHyperlink`（报表钻取，260 处）/ `WebHyperlink`（网页，34 处）/ `JavaScriptImpl`（脚本）
- 参数值可以是常量 `<O>`，也可以是公式 `<O t="Formula" class="Formula">`（`=$A3` 把本行值传过去）

**🔴 写错的对照（不是静默，是整页炸）**

| 写法 | 服务端 |
|---|---|
| `<HighlightList><Highlight><HighlightAction class="…HyperlinkHighlightAction">`（**不带 `<Condition>`**） | **平台出错页**：`export` 报 `EXPORT_ERROR`，xlsx/pdf 都是 3430B 出错页、**没有 detail-message**（最难查的一种）。改成单元格级 `<NameJavaScriptGroup>` 立刻正常 |
| 同形态但**带** `<Condition>`（条件属性超链接） | **已确证**（见 §8）：导出正常（excel 4337B / pdf 35170B，1 页），**同样没有任何链接痕迹**；与不带 Condition 的唯一区别是**不会炸** |

**导出态结论（实测）**：`export excel` 与 `export pdf` **都不保留链接** ——
xlsx 的 `xl/worksheets/sheet1.xml` 里 `<hyperlink>` 0 处、PDF 里 `/URI` `/Annots` `/Link` 全 0。
⇒ **超链接是纯预览态交互**；验收读模板（`report link --list`）而不是读导出产物。

---

## W4. 层次坐标进阶（环比 / 同比 / 跨组 / 全集）

**样例**：`patterns/w4_coord.cpt`（数据：东区 2024=100、2025=150；西区 2024=200、2025=100）
版面：A3=地区(group,v)、B3=年份(list,v)、C3=金额(list,v)，公式列挂在数据行。

**四种坐标的语义（逐格实测，行 3-6 = 上面四行数据）**

| 写法 | 含义 | 实测值（行 3/4/5/6） |
|---|---|---|
| `C3[B3:-1]` | **上一行**（沿 B3 的层次往前 1） | `#DIV/0!` / 0.5 / `#DIV/0!` / -0.5 ⇒ 环比 150/100-1、100/200-1 ✓ **跨组时不越界**（每组首行是 DIV/0） |
| `C3[A3:-1]` | **上一组同位置**（沿 A3 的层次） | `#DIV/0!` / `#DIV/0!` / 1.0 / -0.333 ⇒ 200/100-1、100/150-1 ✓ |
| `C3[A3:-1]`（直接取值） | 同上，取上一组的值 | 100 / 150（后两行）✓ |
| `C3[B3:1]` | **本组第一行**（不是"下一行"！） | 100 / 100 / 200 / 200 |
| `C3[!0]` | 该格**扩展出来的全部格子**（全集） | `SUM`=550；`=C3/SUM(C3[!0])` = 18.2%/27.3%/36.4%/18.2% ✓ |
| `SUM(C3[B3:-1])` | 层次坐标可套在函数里 | 0 / 100 / 0 / 200 |

### W4.1 层次坐标函数（语法糖，实测确认升降序）

`com.fr.function.AbstractHAFunction`（`getType()==Function.HA`）里 7 个函数都是**语法糖**：
子类 `initFormula(args)` 把自己重写成方括号公式再求值（出处见 `docs/探索/层次坐标语法集.md`）。
实测（数据 100/150/200/250，合计 700，同日 `doc/Advanced/Coordinate/` 的口径）：

| 函数 | 语义 | 实测值（4 行） |
|---|---|---|
| `SORT(C3)` | 排名 **降序** | 4 / 3 / 2 / 1 ← **实测裁定**（FR 帮助里默认升降序的说法不一致；安装包只有中文帮助，**未逐语言核对**，一律以实测为准） |
| `SORT(C3,false)` | 排名 升序 | 1 / 2 / 3 / 4 |
| `MOM(B3,C3)` ≡ `IF(&B3>1, C3/C3[B3:-1], 0)` | 环比（组内首行给 0） | 0 / 1.5 / 0 / 1.25 |
| `PROPORTION(C3)` ≡ `C3/SUM(C3[!0])` | 占比 | 14.3% / 21.4% / 28.6% / 35.7% |
| `count(C3[!0;!0]A{C3 > $C3})+1` | 总排名（等价 `SORT`） | 4 / 3 / 2 / 1 |
| `C3[A3:-1,B3:+0]` | **同比**（上一组 + 同一子位置 = 上一年同月） | 西区两行拿到 100 / 150 |
| `K4[B4:-1]A + C4` | 年内累计（官方财务表写法） | 与 §W4 的 `SLICEARRAY` 累计等价 |

⚠ **末尾的 `A`**（`C4[B4:-1]A`）语义未查清（dsauthor 🔴），但**语料一律带 A**、FR 帮助不带 →
**照抄语料**。`!0` 是**一个词法记号**（`FRLexer.mALLL()` 连匹配 `!`+`0`），不是"`!` 运算符 + 0"。
⚠ **`&A3` 在第 1 行**会让 `[A3:-1]` 取到空值 —— 语料的兜底写法是 `IF(&B4>1, …, '--')`（实测 `#DIV/0!` 也是同一处）。

**配方**

```bash
# 环比（上一行）
frcli report cell "$R" --at D3 --set-formula '=C3/C3[B3:-1]-1' --num-format '#0.0%' --apply
# 同比（上一组同位置）
frcli report cell "$R" --at E3 --set-formula '=C3/C3[A3:-1]-1' --num-format '#0.0%' --apply
# 占比（全集）
frcli report cell "$R" --at H3 --set-formula '=C3/SUM(C3[!0])' --num-format '#0.0%' --apply
```

**🔴 写错的对照**

| 写法 | 结果 |
|---|---|
| `C3[C3:-1]`（拿**数值列自己**当层次维度） | **静默空**（不报错、不显示、无 #NAME?） |
| `C3/B3[-1]`（坐标写在分母、且省略维度名） | **静默空** |
| 用错维度：该用 `[A3:-1]`（同比）却写 `[B3:-1]`（环比） | **数值看似正常**（0.5 / -0.5 都是"像样"的百分比）⇒ 最危险的一类静默错，必须手算核对 |
| 跨组首行 | 显示 `#DIV/0!`（显式错误值，不是静默） |

> 与第一辑的呼应：**组内排名 `RANK` 在本安装求值失败**（渲染 `#NAME?`），
> 所以"排名/累计"仍按第一辑的 `SEQ()`+`SLICEARRAY` 写法；层次坐标负责"跨行/跨组取值"。

---

## W5. 分页 · 重复标题行 · 页眉页脚页码 · 冻结

**样例**：`patterns/w5_hdr.cpt`（120 行明细 + 加高表头）、`r7_page.cpt`（80 行）

**① 每页重复标题行 = 报表级 `<ReportPageAttr><HR F="起" T="止"/></ReportPageAttr>`**（0 基闭区间）

⚠ **行号是 0 基（Excel 行号 = F/T + 1），且必须与表头实际所在行一致**。
指错行**不是静默**：实测版面错位时导出直接报 `11300002 行高列宽超出页面大小`（响亮报错，属于好事）。

```bash
frcli report page "$R" --repeat-header-rows 1:1 --apply    # 第 1 行每页重复（Excel 第 2 行 = 表头）
frcli report page "$R" --repeat-footer-rows 118:119 --apply
frcli report page "$R" --repeat-header-cols 0:0 --apply
```

**实测（重复 Lead 的方法：先把表头加高）**

| 版本 | PDF |
|---|---|
| 表头 200pt、无 `<HR>` | 3 页 / 41765B |
| 表头 200pt、`<HR F="1" T="1"/>` | 3 页 / 41859B（**信号很弱，容易误判"没生效"**） |
| **表头 600pt**、无 `<HR>` | 3 页 / 41802B |
| **表头 600pt**、`<HR F="1" T="1"/>` | **7 页** / 50987B ← 重复表头把内容挤到后面页 |

**② 页眉页脚 + 页码**（`<Header>`/`<Footer>` 在 `<ReportAttrSet>` 内、与 `<ReportSettings>` **同级**）

```bash
frcli report page "$R" --footer-text '"第 " + $$page_number + " 页 / 共 " + $$totalPage_number + " 页"' \
    --footer-formula --footer-height 20 --apply
frcli report page "$R" --header-text "日报" --header-height 20 --apply
```

```xml
<ReportAttrSet>
<ReportSettings headerHeight="885500" footerHeight="885500"><PaperSetting/>…</ReportSettings>
<Footer reportPageType="0"><Background name="NullBackground"/><LeftList/>
<CenterList>
<HFElement className="com.fr.base.headerfooter.FormulaHFElement">
<FRFont name="SimSun" style="0" size="72"/>
<Formula content='"第 " + $$page_number + " 页 / 共 " + $$totalPage_number + " 页"' text="0"/>
</HFElement>
</CenterList><RightList/></Footer>
</ReportAttrSet>
```

**实测（pdfium 出图，看最后一页页脚区）**：`第 7 页 / 共 7 页` **真的印在页脚居中** ✓
（页码变量 `$$page_number` / `$$totalPage_number`；HFElement 家族 9 类，语料实际只用 `FormulaHFElement`）

**③ 冻结（两处，别混）**

| XML | 作用 | 可验性 |
|---|---|---|
| `<ReportSettings><FrozenColumnRow columnrow="1,0"/></ReportSettings>` | 冻结分界位置 | XML 往返可验 |
| `<ReportPageAttr><UPFCR COLUMN="true" ROW="true"/></ReportPageAttr>`（`report page --page-freeze on`） | 是否启用页面冻结 | 同上 |

> **冻结是预览态滚动交互，导出产物不会有可见差异** —— "导出看不出效果"**不是 bug**，
> 别再记成"未确证"；判据就是 XML 往返 + 预览页看。

**🔴 写错的对照（三条全静默）**

| 写法 | 结果 |
|---|---|
| `footerHeight="0"`（缺省）却写了 `<Footer>` 内容 | **页脚根本不渲染**，不报错（CLI 检测到 0 会自动补 20 磅并记一条 note） |
| `<Header>/<Footer>` 放到 `<Report>` 下（而不是 `<ReportAttrSet>` 内） | 导出正常、页脚不出现 —— 又被静默忽略 |
| 用 `report image` 验页脚/重复标题行 | **假阴性**（image 是版面流，不分页） |

---

## 6. 命令速查（本辑新增）

| 想做什么 | 命令 |
|---|---|
| 插图表 | `report chart REMOTE --at A1 --dataset ds --type column\|bar\|line\|pie\|ring\|donut（中文别名：柱形图/折线图/饼图/环形图）--category COL [--series COL] --value COL [--fn sum] [--title T] [--show-title] [--cs N --rs N] [--apply]` |
| 看图表 | `report chart REMOTE --list` |
| 参数面板控件 | `report widget REMOTE --param p --type combo\|date\|text\|check\|number [--options "a,b"] [--default v] [--label L] [--x/--y/--width/--height] [--apply]` |
| 看控件 | `report widget REMOTE --list` |
| 超链接/钻取 | `report link REMOTE --at A3 --to 报表路径\|URL [--type reportlet\|web\|javascript] [--param k=v …] [--frame _self\|_blank] [--clear] [--apply]` |
| 看超链接 | `report link REMOTE --list` |
| 重复标题行/表尾 | `report page REMOTE --repeat-header-rows 1:1 --repeat-footer-rows a:b --repeat-header-cols c:d [--apply]` |
| 页眉页脚页码 | `report page REMOTE --footer-text '"第 " + $$page_number + " 页"' --footer-formula --footer-height 20 [--apply]` |
| 页面冻结 | `report page REMOTE --page-freeze on [--apply]` |

只读核对：`report chart --list` / `report widget --list` / `report link --list` / `report page --list`（都不联网写）。

## 7. 样例清单（`patterns/` 目录，与第一辑共用）

| 文件 | 演示 | 关键实测 |
|---|---|---|
| `chart_column.cpt` `chart_line.cpt` `chart_pie.cpt` | 柱形（多系列）/ 折线 / 单张饼 | 100/200/300/400；饼 30%/70% |
| `chart_err_col.cpt` | 静默错：分类列名不存在 | 图变形（400/600，无分类标签）但 `status: ok` |
| `w2_widget.cpt` | 下拉 + 日期控件 | 华东→华南 参数联动 ✓ |
| `w2_widget_errname.cpt` | 静默错：控件名 ≠ 参数名 | 控件存在、**不报错**；**联动与否导出通道验不了**（控件名正确时默认导出同样是模板默认值）⇒ 只能在预览页验 |
| `w3_link.cpt` | 钻取（报表跳转）+ 网页链接 | 模板里可读；xlsx/pdf 无链接痕迹 |
| `w4_coord.cpt` | 层次坐标 8 种写法 | 见 §W4 表 |
| `w4b_funcs.cpt` | HA 函数（SORT/MOM/PROPORTION/同比/总排名） | 见 §W4.1 表 |
| `w5_hdr.cpt` | 120 行 + 加高表头 + `<HR F/T>` + 页脚页码 | 3 页 → 7 页；页脚"第 7 页 / 共 7 页" |

## 8. 未确证 / 待办（诚实清单）

- **参数面板控件的渲染**：只能预览页看；本辑只验了 XML 同构 + 参数仍生效（导出通道）。
- **条件属性形态的超链接**（`HyperlinkHighlightAction` + `<Condition>`）：**已确证**（验证者实测）——
  带 Condition 时导出正常（excel 4337B / pdf 35170B / 1 页），**导出里同样没有任何链接痕迹**；
  不带 Condition 精确复现 3430B 出错页 + `detail-message` 为空。⇒ 两种形态导出都无痕迹，**区别只在带 Condition 不会炸**。
- **图表在 xlsx 里是嵌入图片**（`xl/media/image1.png`）：图片与页面上看到的是否逐像素一致未比对。
- **`<Embed>`**（416 个模板）：dsauthor 已确认是**工具栏位置标记**（`ToolBars/ToolBarManager/Location`），
  与"嵌入内容"无关 —— 本辑未再展开。
- **`<SubReport>` 主子报表**（3 个模板）：罕见，未做。

## 9. 相关文档

- `references/cpt-patterns.md` —— 第一辑（分组小计/交叉表/条件属性/多数据集/参数过滤/日期/公式）
- `docs/探索/图表与控件模型.md` —— 图表与控件的服务端模型（dsauthor 逆向：`<O t="CC">`、`Chart/Plot/ChartDefinition`、`<Widget>` 三类用途、Dictionary 家族）
- `docs/探索/cpt服务端模型-逆向.md` §5.8/§5.9 —— 分页/重复标题行/页眉页脚页码/冻结（Lead 实测）
- `references/cpt-authoring.md` —— 五步造报表与命令语法（本辑的前提）
