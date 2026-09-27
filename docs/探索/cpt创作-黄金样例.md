# cpt 创作黄金样例（Lead 实测，可直接照抄）

> 结论先行：**.cpt 就是 XML，徒手能写出可渲染的报表**。本文给出一张"像样"的报表
> （标题+参数+表头样式+取数表+数字格式+公式合计）的完整写法与实测结果，
> 以及三条只有实测才能发现的语法规则。

## 实测产物

`demo_group/demo_user/skill测试/golden.cpt`（3878 字节，全部手写），导出 xlsx：

```
A1: 支持中心门店数 TOP10（编码 ≥ 01）        ← 合并 A1:C1，公式引用参数
A2: 中心编码   B2: 中心名称   C2: 门店数      ← 表头（加粗+底色+边框）
A3: SC04       B3: 华西       C3: 376
A4: SC03       B4: 华南       C4: 335
A5: SC02       B5: 华东       C5: 238
A6: SC01       B6: 华北       C6: 148
A7: SC05       B7: 华中       C7: 122
A8: SC99       B8: 创新       C8: 58
A9: 合计       B9: 6(公式)     C9: 1277(公式)
```

传参覆盖（`--params '{"topn":3,"min_center":"SC03"}'`）后：

```
A1: 支持中心门店数 TOP3（编码 ≥ SC03）       ← SQL 与标题**同时**跟着变
A3..A5: SC04/SC03/SC05，B9 合计=3
```

## 文件骨架

```
<WorkBook xmlVersion="20211223" releaseVersion="10.0.0">
  <TableDataMap>          数据集（0..N 个）
  <Report class="com.fr.report.worksheet.Work" name="sheet1">
    <ReportPageAttr>      打印相关
    <RowHeight defaultValue="723900">CDATA: 逐行高度（EMU，逗号分隔）
    <ColumnWidth defaultValue="2743200">CDATA: 逐列宽度
    <CellElementList>     单元格（核心）
    <ReportAttrSet>       纸张/页眉页脚
  <ReportParameterAttr>   模板参数（决定 $x 能否在单元格里解析）
  <StyleList>             样式表，被单元格 s= 索引
</WorkBook>
```

**取骨架的最省事做法**：拿一张能导出成功的现有模板，把 `<TableDataMap>` 与
`<CellElementList>` 清空即可（其余外壳原样保留）。

## 单元格

```xml
<C c="0" r="0" cs="2" s="0">…</C>     <!-- c=列 r=行（0 起） cs=横向合并 rs=纵向合并 s=样式索引 -->
```

`<C>` 内三个固定成员：值对象 `<O>`、`<PrivilegeControl/>`（**不能省**）、扩展 `<Expand/>`。

| 用途 | 写法 |
|------|------|
| 静态文本 | `<O><![CDATA[门店数]]></O>` |
| 公式 | `<O t="XMLable" class="com.fr.base.Formula"><Attributes><![CDATA[=SUM(C3)]]></Attributes></O>` |
| 数据集列 | `<O t="DSColumn"><Attributes dsName="ds1" columnName="shop_cnt"/><Complex order="0"/><Result><![CDATA[$$$]]></Result></O>` |
| 数值常量 | `<O t="I"><![CDATA[0]]></O>` |

## ⚠️ 三条只有实测才会发现（务必遵守）

1. **扩展方向：`dir="0"` = 纵向，`dir="1"` = 横向**（直觉容易记反）。
   交叉验证：真实模板里日期列 `sdt` 用 `dir="1"`（横向铺开），维度列 `bd_name` 用 `dir="0"`（纵向铺开）。
   写反了不报错，只是**表格长歪**（数据横向排成一行、其余列消失）。
2. **`${x}` 与 `$x` 是两个世界**：
   - `${x}` 只在**数据集 SQL** 里被替换；
   - 单元格公式里的参数要写 `$x`。
3. **参数「既没传值、又没默认值」→ 静默求值成空字符串**（不报错、导出成功、Excel 里就是空白）。
   这是本项目见过最阴的坑：agent 自测时总会带 `--params`，所以永远测不出来；用户不带参数打开才发现一片空白。
   **规避办法：每个参数都要给默认值**，且**两处都要写** ——
   - 数据集 `<Parameters>` 里的 `<O>`（供 SQL 的 `${x}` 用）
   - `ReportParameterAttr > Parameters` 的声明（供单元格公式的 `$x` 用；实测只写数据集那处，单元格仍拿不到默认值）

   > 实测边界（cpt-verifier 逐格验证）：`--params` **传了值就会绑上，不管有没有声明**；
   > `ReportParameterAttr` 里声明的唯一作用是**提供默认值**。所以"必须声明"只在"默认值"这一层成立，
   > 不是渲染的必要条件。

```xml

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

声明后：`--params '{"topn":3}'` 会**同时**作用于 SQL 的 `${topn}` 与公式的 `$topn`；
不带 `--params` 时用这里的默认值。

## 数据集

```xml
<TableDataMap>
<TableData name="ds1" class="com.fr.data.impl.DBTableData">
<Parameters>
<Parameter><Attributes name="min_center"/><O><![CDATA[01]]></O></Parameter>   <!-- 默认值写在 O 里 -->
</Parameters>
<Attributes share="true" maxMemRowCount="-1"/>
<Connection class="com.fr.data.impl.NameDatabaseConnection">
<DatabaseName><![CDATA[demo_conn]]></DatabaseName>
</Connection>
<Query><![CDATA[select … where c >= '${min_center}' limit ${topn}]]></Query>
<PageQuery><![CDATA[]]></PageQuery>
</TableData>
</TableDataMap>
```

## 样式

`<StyleList>` 里第 n 个 `<Style>` 由单元格 `s="n"` 引用（0 起）。

```xml
<Style horizontal_alignment="1" imageLayout="1">      <!-- 0=左 1=中 2=右 -->
<Format class="com.fr.base.CoreDecimalFormat" roundingMode="6"><![CDATA[#,##0]]></Format>
<FRFont name="微软雅黑" style="1" size="72" foreground="-16777216"/>  <!-- 0 常规 1 加粗 2 斜体 3 粗斜；size 单位 1/8 磅(72=9磅) -->
<Background name="ColorBackground" color="-1703900"/>               <!-- 或 NullBackground -->
<Border><Top style="1"/><Bottom style="1"/><Left style="1"/><Right style="1"/></Border>
</Style>
```

常用数字格式（实测取自真实模板）：`#,##0`、`#,##0.0`、`#0.0%`、`#0%`、`#,##0.0pp`。

## 行列尺寸

```xml
<RowHeight defaultValue="723900"><![CDATA[900000,723900,723900,723900]]></RowHeight>
<ColumnWidth defaultValue="2743200"><![CDATA[2743200,5486400,2743200]]></ColumnWidth>
```

单位是 EMU（1 px = 9525 EMU）：`723900`≈76px 行高、`2743200`≈288px 列宽。

## 验证方法（每次改完必做）

```bash
export FRCLI_WRITE_SCOPE="demo_group/demo_user/skill测试"
frcli report upload /tmp/x.cpt "demo_group/demo_user/skill测试/x.cpt" --force
frcli export excel "demo_group/demo_user/skill测试/x.cpt" -o /tmp/x.xlsx
python3 -c "
import openpyxl; ws=openpyxl.load_workbook('/tmp/x.xlsx').active
for r in ws.iter_rows(max_row=12,max_col=4): print([c.value for c in r])"
```

**只看"导出成功"不算验证** —— 必须逐格读回内容。写歪了（扩展方向反、参数空、样式索引越界）
都能导出成一份"看起来正常"的 Excel。
