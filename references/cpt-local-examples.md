# 从本地 CPT 示例查找、画像并提炼设计技巧

适用：已有 FineReport 安装包或其他本地 `.cpt` 样例，要查找并研究版面、公式、分组、扩展、
视觉、交互、图表或报表选型。
这些命令直接读取本地文件，不连接实例，不修改样例。`<reportlets目录>` 替换成实际示例目录。

## 查找和检查

```bash
frcli report local-examples "<reportlets目录>" --keyword 分栏
frcli report local-examples "<reportlets目录>" --contains PolyWorkSheet -n 30
frcli report local-profile "<reportlets目录>" --tag dashboard -n 10
frcli report local-profile "<reportlets目录>" --keyword 销售 --tag crosstab -n 10
frcli report local-inspect "<reportlets目录>/demo/basic/聚合报表.cpt"
frcli report local-inspect "<reportlets目录>/demo/basic/聚合报表.cpt" --design
frcli report local-inspect "<reportlets目录>/demo/basic/聚合报表.cpt" --cells -n 100
frcli report local-inspect "<reportlets目录>/demo/basic/聚合报表.cpt" --sheet sheet1 --block 2 --cells
```

`--keyword` 匹配相对路径、不区分大小写；`--contains` 是区分大小写的 UTF-8 XML 原文匹配，
不是语义搜索。`matched` 是全部匹配数；`truncated` 表示只返回前 `-n` 条；`skipped_count`
包含读取失败和不跟随的符号链接，排查其 `skipped` 后再判断是否查全。
用 `--contains` 时 `valid` 只统计「命中该串且能解析」的文件（会明显小于 `scanned`），
不要把它当目录里的有效模板总数。
`local-inspect` 只接受完整 `WorkBook` XML；`format=cpt` 返回的 `TableDataMap` 不是模板原件。
远端报表先用 `report download` 获取原件，不要将示例覆盖回服务端。

检查结果列出所有 sheet 的类型、数据集名称、单元格数、分栏属性与浮动元素数。`--cells`
另外返回当前选定 sheet 或 block 的前 `-n` 格：坐标、值/公式、数据集列、数据设置、扩展、
合并宽高与条件属性数量；`cell_count` 是选定范围总数，`truncated` 提示未列完。
默认第一张 sheet；用 `--sheet` 指定其他页。文件无效、sheet 不存在或块序号错误时直接报错。

## 批量画像：先找同类，再选代表样板

`local-profile` 扫描目录后返回整库的原型分布（`archetypes`）、设计技术分布（`techniques`）、
图表类型分布、`design_lessons` 和代表样例。`--tag` 可以匹配原型或技术标签，例如 `form`、`dashboard`、
`grouped-table`、`crosstab`、`chart-linkage`、`conditional-formatting`、`split-columns`。
`design_lessons` 把已识别手法映射成可执行的设计提示，并附命中样例数，便于先建立整库视野。
图表类型从 `<Plot>`/`<VanChartPlot>` 的类名识别；组合图会返回多个类型（如柱形+折线）。
结构框架图、智慧树图等插件/特殊图不在标准图表类型表内，`chart_types` 可能为空，需结合 `--design` 的其它信号判断。
`--tag` 只认英文标签 key（如 `crosstab`、`chart-pie`、`conditional-formatting`），
中文类型名（如 `chart-柱形图`）匹配不到。

样例按 `study_score` 排序；它只表示目标标签命中、目标结构完整度和样板聚焦度，不是设计质量评分。
按标签检索时，先要求目标结构完整，再优先规模小、附带控件/脚本/多 sheet 较少的样板；目标技术达到
学习所需数量后不再无限加分，单纯命中原型的聚焦样板会排在“恰好也包含该结构”的超大综合模板之前。
输出中的 `score_semantics` 也标明这一边界；仍应比较多种样板。
通常选择 3–5 个同类样例：一个基准样板、一个信息增强样板、一个高密度样板、一个交互样板和一个
最接近目标渠道的样板。然后用 `local-inspect --design` 读取整份画像，用 `--cells` 定位具体格号。

单份画像的 `design` 分区：

| 分区 | 内容 |
|---|---|
| `archetype` / `archetypes` | 明细、分组、交叉、图表分析、主从、驾驶舱、填报、聚合或静态版面 |
| `layout` | sheet、聚合 Block、浮动元素、分栏、冻结区、绝对布局 |
| `data` | 数据集、参数、绑定、公式、扩展方向、分组/列表/汇总和合并 |
| `visual` | 字体、字号、颜色、数字格式、对齐、边框和条件属性 |
| `interaction` | 控件、提交、超链接、图表联动和 JavaScript |
| `charts` | 图表数量、类型、标签和提示 |

批量画像适合寻找设计参考；报表该选哪种原型、怎样组织信息层级，用
`cpt-design-from-examples.md` 的选择矩阵和工作流判断。

## 聚合报表：每个区块都有自己的网格

官方样例 `doc/Advanced/多表头报表.cpt` 的 `Report` 是 `PolyWorkSheet`，其直接子元素包含
两个 `Block`，各自内含 `CellElementList` 和 `PECBAttr`。一次结构检查得到 25 + 154 = 179 格；
两个区块各有一个 `A1`。`PECBAttr` 的 `blockName`、`x/y/width/height` 定义分别保存于各块。
        注意 `report page/highlight/link/chart --list` 这类基于普通网格的只读命令遇到聚合报表
        也会明确报错（fail closed），请用 `local-inspect` 按块查看。

- `--cells` 每行带 `block_index` 和 `block_name`；`--block 2` 的序号是工作表中块的 1 基顺序。
- `bounds` 为模板中原始坐标值，不应当成全表单元格坐标；未知块类型若无 `CellElementList`，
  `has_cell_list` 为 false，零格仅表示没有识别到该列表。
- 普通 `report cell/table` 网格命令不能安全处理聚合块；遇到聚合工作表应停止普通网格修改。
  需要创作或修改聚合报表时使用 Designer，并在目标预览及导出通道验收。

## 分栏与浮动元素：先比原始结构，再做效果验证

`demo/basic/行分栏.cpt` 的普通工作表有 `WorkSheetAttr`，其中 `direction="0"`；
`doc/Advanced/列分栏.cpt` 的对应字段为 `direction="1"`。这些示例还带 `start`、`end`、
`indexsToCopy` 或 `maxRowOrColumn` 等属性，具体值与版面相关。`local-inspect` 原样列出这些属性，
可用来定位参考样例；不能仅凭 XML 就推断所有参数的含义或保证分页效果。

`doc/Advanced/总标题式卡片分栏.cpt` 同时含 `FloatElementList` 和 `WorkSheetAttr`。
浮动元素不属于 `CellElementList`，应结合 `floating_elements` 与单元格数量分析，不能把
单元格数当成全部可见内容。若需还原视觉效果，在 Designer 预览并按目标通道验收。

## 公式与证据边界

官方示例既有 `<O t="Formula" class="Formula">`，也有
`<O t="XMLable" class="com.fr.base.Formula">`；两者都识别为公式。单元格不显式写 `<RG>`
时的分组默认行为及验证配方见 `cpt-features.md` 与 `cpt-patterns.md`。

结构扫描只说明模板文件写了什么，不证明运行时公式、数据连接、参数联动或导出效果正确。
复用前先核对数据集、参数与适用版本；验证变化时按 `cpt-patterns2.md` 的验收通道选择方法执行。

## 完整学习路径

1. 用 `local-examples` 按路径或 XML 原文查找，或用 `local-profile` 按原型/技术标签找同类。
2. 用 `local-profile` 比较 3–5 个代表样例的原型、技术、图表和规模。
3. 用 `local-inspect --design` 看整份模板画像，用 `--cells` 看实现手法所在的格号。
4. 按 `cpt-design-from-examples.md` 提炼信息层级、数据语义、视觉、交互和渠道规则。
5. 用 `cpt-authoring.md` 的命令实施，具体配方查 `cpt-patterns.md` 与 `cpt-patterns2.md`。
6. 预览验交互，导出验分页和格式，独立对账验数据；结构画像不能代替这些验收。
