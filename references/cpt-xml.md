# cpt 模板 XML 结构速查

> **要造模板（而不是改 SQL）看 `references/cpt-authoring.md`** —— 那里有命令、
> 配方（静态/公式/取数表/参数/合并/样式）与「怎么验证它对」。
> 本文件讲的是**定点字节读写**这一层（`report edit` 的底座）。

> 取证来源：服务端真实模板（`report download` 走远程设计通道取回的**原始字节**，
> 不是 `format=cpt` 的数据集定义提取物）。层级与元素名均来自实测样本，不是推测。
> 对应的代码：`src/frcli/cptxml.py`（扫描/定点替换）+ `src/frcli/reportops.py`（编辑闭环）。

## 1. 顶层骨架

```xml
<?xml version="1.0" encoding="UTF-8"?>
<WorkBook xmlVersion="20211223" releaseVersion="10.0.0">
  <TableDataMap>                       ← 数据集定义（可以改 SQL / 连接 / 参数默认值）
    <TableData name="ds1" class="com.fr.data.impl.DBTableData"> … </TableData>
    <TableData name="ds2" class="com.fr.data.impl.DBTableData"> … </TableData>
  </TableDataMap>
  <Report class="com.fr.report.worksheet.WorkSheet" name="sheet1">   ← 版面/单元格（本 CLI 不动）
    <ReportPageAttr>…</ReportPageAttr>
    <CellElementList><C c="0" r="0">…</C></CellElementList>
  </Report>
  <StyleList>…</StyleList>
</WorkBook>
```

**根元素必须是 `<WorkBook>`。** `GET /decision/view/report?reportlet=X&format=cpt` 返回的是
另一种序列化（根元素 `<TableDataMap>`，缺 `<WorkBook>`/`<StyleList>`），拿它写回模板会毁报表 ——
`assert_template_bytes()` 就是拦这个的。

## 2. `<TableData>` 内部

```xml
<TableData name="xs" class="com.fr.data.impl.DBTableData">
  <Parameters>                                  ← 数据集参数（SQL 里用 ${name} 引用）
    <Parameter>
      <Attributes name="date"/>                ← 参数名（空元素）
      <O><![CDATA[]]></O>                      ← 默认值；空 CDATA = 没有默认值
    </Parameter>
  </Parameters>
  <Attributes share="true" maxMemRowCount="-1"/>
  <Connection class="com.fr.data.impl.NameDatabaseConnection">
    <DatabaseName>
      <![CDATA[demo_conn]]>          ← 数据连接名（平台里配置的那个名字）
    </DatabaseName>
  </Connection>
  <Query>                                      ← 主 SQL（CDATA 包裹，原样多行）
    <![CDATA[
select … where sdt between '${date}' and '20251116'
    ]]>
  </Query>
  <PageQuery><![CDATA[]]></PageQuery>          ← 分页查询（多数模板为空）
</TableData>
```

| 元素 | 含义 | `report edit` 支持 |
|---|---|---|
| `TableData/@name` | 数据集名（`report datasets` 里的「名称」） | 定位用 |
| `TableData/@class` | 数据集类型实现类，`DBTableData` = 数据库查询 | 只读展示 |
| `Parameters/Parameter/Attributes/@name` | 数据集参数名 | `--param` |
| `Parameters/Parameter/O` | 参数默认值 | `--default` |
| `Connection/DatabaseName` | 数据连接名 | `--connection` |
| `Query` | 主 SQL | `--sql` / `--sql-file` / `--replace` |
| `PageQuery` | 分页 SQL | 暂不支持（一般空） |

其他 `class` 值（如 `com.fr.data.impl.EmbeddedTableData` 内嵌表、`StoreProcedure` 存储过程）
结构不同，`--list` 会照实显示，改之前先看一眼。

## 3. 三个易踩的坑

1. **同名元素到处都是**。`<Parameters>` 在单元格元素（`Report/CellElementList/C/O`）、
   `ReportParameterAttr/ParameterUI` 里也有；多个 `<TableData>` 的标签路径完全相同。
   **只按标签名/路径匹配会把别的数据集的参数算进来**（踩过：每个数据集都报出全部参数）。
   必须按**位置区间**限定在目标元素的字节范围内查找 —— `cptxml._sub_elements()` 就是这个。
2. **不要用 ElementTree 往返**。`parse` → `tostring` 会丢注释、改自闭合写法
   （`<Parameters/>` → `<Parameters />`）、把 CDATA 变成转义文本，几 MB 的模板整篇重排，
   diff 没法看，还可能踩到服务端不认的写法。
   `cptxml.set_text()` 是**定点替换**：只改目标元素的字节区间，其余逐字节保留
   （实测：改一个 `<Query>` 后，元素区间前后与原文件完全一致）。
3. **`]]>` 不能出现在 CDATA 里**。新写的内容含 `]]>` 时 `set_text` 直接报错，
   不会悄悄写出一个坏 XML。没有 CDATA 包裹的元素会自动转义 `& < >`。

## 4. 改模板的正确姿势

```bash
# 1) 先看有什么（从真实模板字节读，不写服务端）
frcli report edit demo_group/demo_user/skill测试/x.cpt --list

# 2) dry-run：只打印 SQL 前后对照
frcli report edit …/x.cpt --dataset xs --replace "'20251013'='20251101'"

# 3) 确认 diff 无误再写（写范围守门 + 占锁 + 备份 + 回读校验 SHA256）
frcli report edit …/x.cpt --dataset xs --replace "'20251013'='20251101'" --apply
```

写路径的口径（**三种服务收的路径不一样，这是最容易白试半天的地方**）：

| 服务 | 收什么 | 例 |
|---|---|---|
| `WorkResource` / `TplOperator`（读、写、删、锁） | **工作区路径** | `reportlets/demo_group/demo_user/x.cpt` |
| `VcsOperator` / `TemplateExportOperator` / `TemplateChecker` | **展示路径** | `demo_group/demo_user/x.cpt` |
| REST（`report list/info/datasets`、`export`） | **展示路径** | `demo_group/demo_user/x.cpt` |

前缀写错**不会报错**：工作区路径少 `reportlets/` 会返回空目录 / `false` / 0 字节，
展示路径多 `reportlets/` 会返回空列表。`frcli rpc call` 会在这种情况下回一句 `hint` 指路。

## 5. 验证改动真的生效

| 判据 | 命令 | 说明 |
|---|---|---|
| 模板字节确实变了 | `report edit` 的回读校验（`upload.verified`） | 写后 SHA256 比对，防「无授权静默不写」 |
| 平台侧读到的是新内容 | `report datasets … --sql` | 走 `format=cpt`，服务端重新解析模板后可看到新 SQL |
| 版面/单元格没被牵连 | 改前改后比 `<Report>` / `<StyleList>` 段字节 | `report edit` 只替换目标元素的字节区间，其余原样（`tests/test_cptxml.py` 断言了这一点） |

⚠️ **别用导出图判断「版面有没有被牵连」**：改了 SQL 数据就变了，图自然会变。
要判断的话比 `<Report>` 段的字节，或者用 `report image` 比一张**数据不变**的模板。

`report edit` 只动 `<TableDataMap>` 里的指定元素；`<Report>`（版面、单元格、样式）不在编辑范围内。

## 6. 改版面：删列 / 合并数 / 条件格式（2026-10 实测）

「清空单元格内容」≠「删除列」。真删列后列号整体左移，必须同步改三处，否则版面错位或公式错引用：

1. 删目标列的 `<C>` 节点（整列无 `<C>` 时只删绑定/清内容）；
2. **改所有公式引用**：被删列右侧的列字母全部左移；行内公式（如 `=if(S5=0,"-",R5/S5)`）逐格重映射；
3. **改合并数**：区域合并 `cs`/`rs` 按删掉列数缩减（如折价率区 `cs=10→6`、组内 `cs=5→3`）；
4. **列宽数组长度同步**（删 4 列 → 37 项变 33 项）。

条件属性（`<HighlightList>`）注意：

- 多个 `<Highlight>` **并列**生效，不是「与」；「值 < 0.75 且不是 `-`」要用一个条件表达，不能加一条「不等于 `-`」去否决前一条。
- 推荐 `ListCondition` + 两个 `JoinCondition join="0"`（与）+ `ObjectCondition`（`op="1"` 不等于）：设计器可视化、按当前格相对引用，
  **删列后不用重映射**；`FormulaCondition` 写死 `$T7` 则必须随列位改。

验收：XML 良构 → `report upload`（回读 SHA256）→ 导出 xlsx → 与改前导出逐格比对（数据不变）+ 按值统计标红数量。
⚠️ 读导出 xlsx 不要按固定列号（大区展开/合并会让列号与模板列字母不一致），按表头名定位。
