# CPT 结构编辑与引用联动

适用：frcli ≥ 0.11.0。日常运行只需要 Python，不加载 Designer 或 Java。
`validate` 检查文件结构与可识别引用，不能证明取数、运行时扩展、插件或导出结果正确。

## 1. 固定操作路径

```bash
frcli report validate input.cpt --local
frcli report refs input.cpt --local --sheet 明细 --at D5

# 默认只预览；删除范围使用修改前坐标，可重复，相邻/重叠范围自动合并
frcli report column input.cpt --local --sheet 明细 --delete C:E --delete H
frcli report row input.cpt --local --sheet 明细 --delete 3:5
frcli report row input.cpt --local --sheet 明细 --insert-before 3 --count 2

# 显式执行，输出必须是新文件；输入和已有输出均不覆盖
frcli report column input.cpt --local --sheet 明细 --delete C:E --apply -o result.cpt
frcli report validate result.cpt --local
```

远端目标去掉 `--local`，使用展示路径；`--apply` 前须明确授权目标并设置 `FRCLI_WRITE_SCOPE`。
写前占锁后再次核对读取快照；模板被其他操作修改或删除时取消写入。随后执行备份、写入、回读校验。
本地 `--local` 不读取实例配置，不联网；默认预览也不会创建输出目录。

结构操作遇到多 sheet 必须明确 `--sheet`。聚合 CPT 还必须给 `--block N`（1 基序号），
各块独立坐标，两个块都可以有 `A1`。块没有网格时明确拒绝；跨块引用语义未确认时阻止变换。

## 2. 自动处理与阻断

| 内容 | 行列增删的行为 |
|---|---|
| 单元格与合并区域 | 更新位置和跨度；整块删除时删除对应节点 |
| 行高、列宽 | 同步显式数组；未显式配置的后续尺寸仍沿用默认值 |
| 公式 | 识别普通、区域、`sheet!A1` 和层次表达式内坐标，保留字符串与字段名 |
| 层次定位 | `$A1` 是 FineReport 的对应位置取值，结构增删跟随逻辑目标；不套用 Excel 行列锁定规则 |
| 父格 | 更新显式引用，检查自动父格在修改前后是否仍等价 |
| 条件属性、数据列公式、超链接参数 | 使用相同的公式引用处理器 |
| `ColumnRow` / `FixCell` | 更新已识别的零基结构化坐标，如条件比较、填报配置、行操作控件 |
| 冻结与重复标题区域 | 同步计数及起止坐标；整个重复区域删除时清除该区域 |
| 分栏 | 同步已识别的起止区域和复制标题索引 |

删除的目标仍被存活内容依赖时返回 `TEMPLATE_VALIDATION_ERROR`，包括引用位置、原表达式、
引用类型与原因。被一并删除的单元格内部依赖不阻断操作。引用空白格是合法的，不能因为没有 `<C>` 节点就认定引用无效。

区域部分被删除时可确定的引用范围会收缩；引用区域全部删除则阻断。
合并主格被删除、但合并区域和主格非空内容仍部分保留时，不能决定内容归属，阻断操作。
自动父格变化、动态引用、自定义函数、未注册插件或坐标结构同样阻断，`--apply` 不绕过这些检查。
数据集方法中的字段名即使形如 `A1`、`Q1` 也不当成格号改写；字段/单元格或参数/`$Cell` 名称存在歧义时阻断。

识别 `C3[B3:-1]`、`C3[!0]`、`C3[!0;!0]A{C3>$C3}` 中的坐标并保持其余语法。
`~` 是决策报表/FVS 的对象引用，本轮明确报告而不重写；跨 sheet 使用已验证的 `!`。
`$A$1`、`A$1` 等 Excel 写法不作为已确证的 CPT 引用，列入 `excel_style_address` 并阻止结构变换。
不能仅凭词法检查通过就认为它可求值。层次位置与 `$Cell` 的语义见
[官方操作符说明](https://help.fanruan.com/finereport10.0/doc-view-249.html)与
[层次坐标](https://help.fanruan.com/finereport10.0/doc-view-339.html)。

## 3. 区域编辑与尺寸

```bash
frcli report range input.cpt --local --sheet 明细 --at A1:C5 --copy-to E1
frcli report range input.cpt --local --sheet 明细 --at A1:C5 --move-to E1
frcli report range input.cpt --local --sheet 明细 --at A1:C5 --clear
frcli report range input.cpt --local --sheet 明细 --at A1:C1 --merge
frcli report range input.cpt --local --sheet 明细 --at A1:C1 --unmerge
frcli report range input.cpt --local --sheet 明细 --at A1:C5 --style 1
frcli report row input.cpt --local --sheet 明细 --at 3:5 --height 20
frcli report column input.cpt --local --sheet 明细 --at C:E --width 16
frcli report column input.cpt --local --sheet 明细 --at C:E --hide
```

- **复制**：保留源区域，已支持的单元格坐标按位移调整，层次索引常量保留。当前支持同一网格内复制。
  含 `$Cell` 的复制语义尚未确证，返回 `copy_value_position`，不猜是否锁定坐标。
- **移动**：同时更新指向源区域的外部引用，支持目标与源区域重叠的快照移动。
- 目标有其他单元格、复制重叠、切开合并区域，或移动将引用区域拆成不连续区域时拒绝。
- 复制涉及区域外父格或尚未支持的结构时拒绝，不猜新的依赖关系。
- **清空**：清空值对象，保留坐标、样式、合并、扩展及其他属性，与删除行列不同。
- 合并时其他非空格会阻断；拆分必须完整包含合并区域。区域样式会为稀疏空位建立样式格，一次最多 100000 格。
- `--hide` 将尺寸设为 0，保留数据。行高单位为磅，列宽单位为字符。

## 4. 现有设计命令

`edit/cell/dataset/param/style/sheet/table/crosstab/highlight/page/chart/widget/link/new`
都可使用 `--local`；已有编辑命令的其他参数保持原义。
本地执行使用 `--apply -o NEW.cpt`。`new --output` 原有用法仍可用；本地模式下使用 `--apply` 才生成文件。

`cell/table/crosstab/highlight/page/chart/link` 增加 `--block`，用于聚合报表中有网格的指定块；
块内未配置所需分页、尺寸等结构时明确报错，不借用另一个块的配置。
`sheet --rename/--remove` 检查并联动已识别的跨 sheet 引用，删除仍被引用的 sheet 会阻断。

修改结果共用结构检查：非法 XML、重复坐标、非法样式、确定的父格循环或不存在的数据集等问题会阻断写入。
未知结构在一般编辑结果中列入 `unsupported`；涉及坐标变换时必须先经过专用处理器验证。

## 5. 如何读取检查结果与验收

- `diagnostics`：结构错误及其位置；确定的错误使命令非零退出。
- `unsupported` / `coverage_complete`：尚不能可靠解释的内容；检查通过不表示覆盖完整。
- `coordinate_transform_ready`：静态检查是否具备完整的已知坐标变换覆盖；具体操作仍需预览。
- `reference_updates`：本次实际改写的表达式前后对照。
- `validation_level: structural` / `runtime_verified: false`：没有运行模板。

验收顺序：结构检查 → 引用与差异回读 → 固定数据下预览交互 → 目标导出物逐格对账。
写后 hash 校验只证明文件确实写入，不证明数值、扩展、图表或分页正确。
带合计/分组的模板应检查多个输出通道；不能把模板坐标直接当成导出后的坐标。

逆向对照的方法、实测行为和当前验证边界见 [CPT 结构编辑验证](../docs/验证/CPT结构编辑验证.md)。
