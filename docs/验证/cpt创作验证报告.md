# cpt 创作能力验证报告（第一轮 · 独立验证）

> ⚠️ 本文提到的证据图片/产物已从仓库移除（服务端渲染带个人水印与真实数据）；重建方法见 `docs/验证/证据/README.md`。


> 验证者：`cpt-verifier`（teammate）｜日期：2026-09-27｜仓库版本：fanruan-v10 0.6.0
> 服务器：fr.example.com（10.0.19）｜账号：00000000
> 测试目录（唯一允许写）：`demo_group/demo_user/skill测试`
>
> **身份设定**：本轮我把自己当成「只会读 `SKILL.md` + `references/` 的新 agent」。
> 凡是"文档没说清、只能翻源码/翻语料才懂"的地方，都算缺陷，不自己补脑。
> 所有"成功"都必须用 `openpyxl` **逐格读回**才算数 —— 只看 `status: ok` 一律不算。

---

## 0. 结论速览（TL;DR）

| 问题 | 结论 |
|---|---|
| **cpt 能手工从零创作吗？** | **能**。静态文本、公式、参数、数据集、纵向/横向扩展、样式、数字格式、合并、列宽、行高、xlsx/pdf/png 导出全部实测通过 |
| **文档够用吗？（第一轮时点）** | **不够**。`references/cpt-authoring.md` 当时**不存在**；`cpt-xml.md` 只讲 `<TableDataMap>`，明确写着「本 CLI 不动」单元格/样式；`SKILL.md` §1 甚至写着「**不适合：从零设计 .cpt 的版面与控件**」——与"创作能力"直接矛盾。单元格语法（`<C>/<O>/<Expand dir>/<StyleList>/ReportParameterAttr`）**零文档**，只能从语料反推 |
| **最危险的形态** | **静默产出"导出成功但内容错"的模板**，实测 6 类：`dsName` 错 / `columnName` 错 / 公式语法错 / 数据集名为空 / 未传值参数 / `s=` 越界。全部**上传无阻、导出 200 + 正常 xlsx 魔数**，逐格读回才发现是空的 |
| **`dir` 语义** | **已独立交叉验证**：`dir="0"`=纵向、`dir="1"`=横向。反了不报错，只是表横着长 → **无任何信号**，只能逐格读回 |
| **写范围守门** | **完好**。22 条零请求哨兵用例全过；范围外写命令在任何网络请求之前被本地拒绝（含 `..` 穿越、`<scope>.x` 兄弟目录、URL 编码） |
| **CLI 有没有本地校验？** | **几乎没有**。`report upload` 只查「前 600 字节含 `<WorkBook>`」；**残缺 XML 也照传**，直到导出才由魔数校验兜住（坏模板已落在服务器上） |

---

## 1. 方法与证据口径

- **构造方式（模拟新 agent）**：手写 XML，骨架取 `<开发工作目录>/corpus/TOP品店日均&门店数.cpt`，清空 `<TableDataMap>` 与 `<CellElementList>`，其余逐字节保留。
  构造器：`/tmp/verify/mk.py`（一次性脚本，未入库）。
- **落地**：`FRCLI_WRITE_SCOPE="demo_group/demo_user/skill测试"` + `report upload`（写后回读 SHA256 `verified: true`）。
- **验收**：`export excel` → `openpyxl` 逐格读 `value`/`number_format`/`font`/`fill`/`alignment`/`merged_cells`/`column_dimensions`/`row_dimensions`；
  版面另用 `export pdf`（查 `%PDF` + `/Catalog` + 页对象）与 `report image`（PNG，人眼复核）。
- **守门**：`httpx.Client.request` 换成"记录并抛错"的哨兵 → 断言"零请求"。

> ⚠️ **哨兵接缝本身就是个坑（我先踩了，写在这里给后人）**：
> `report upload/delete/edit --apply` 走 `remotedesign.RemoteDesignClient`，它**自带一个 `httpx.Client`**，
> 与 `FineReportClient._request`（REST 通道）是两条路。只 patch 后者 → 范围外用例照样"零请求"**假绿**，
> 而范围内用例会**真的写到服务器**（我第一版就因此误建了 `skill测试/x.cpt` 与子目录 `子/`，已清理）。
> 正确接缝 = `httpx.Client.request`。已固化成回归：`tests/test_write_scope_zero_requests.py`
> （含一条"范围内必须真的发出请求"的**接线自检**，专门防这种假绿）。

---

## 2. 逐项结果

### 2.1 给定事实复现（结论：**全部成立**）

| 输入 | 期望 | 实测（逐格） | 结论 |
|---|---|---|---|
| `skill测试/hello.cpt` | A1=`hello frcli`、A2=`3`、B2=`AB` | A1=`hello frcli`、B1=`第二格`、A2=`3.0`、B2=`AB` | ✅ |
| `skill测试/table2.cpt` | `key/val` 表头 + A/B/C 三行 | A1=`key`、B1=`val`；A2..A4=`A/B/C`，B2..B4=`1/2/3` | ✅ |

### 2.2 最小可渲染模板（结论：**可用**）

自建 `v2_min.cpt`（清空骨架 + 6 个单元格，无数据集）：静态文本、中文、`"双引号"`、`'单引号'`、`=1+2`、`="A"+"B"`、`FORMAT(TODATE(...))`。

```
A1=V2 最小模板   B1=中文 与 "双引号" 与 '单引号'
A2=line1line2    B2=3.0      B3? A3=AB   B3=MTD:20260115
```

- ✅ 引号/中文在 CDATA 内**无需转义**，原样入格。
- ⚠️ **单元格内换行被吃掉**：CDATA 里的 `\n` 导出成 `line1line2`（要换行得配 `wrap_text` 之类，文档未提）。
- ✅ 空模板（`<TableDataMap/>` + `<CellElementList/>`）完全合法，可作起点。

### 2.3 取数表（结论：**可用**）

自建 `v3_table.cpt`：数据集 `ds1`（纯字面量 SQL + 数据集参数 `${edate}`）、表头行、`DSColumn` 纵向扩展、公式列 `=B2*2`、样式、数字格式 `#,##0.00`，导出时传 `--params '{"edate":"20260115"}'`：

```
A1=品类 B1=数值 C1=数值x2 D1=日期          ← 表头（橙底 00FF9900 + 边框）
A2=A    B2=1    C2=2(PK=B2*2)  D2=20260115
A3=B    B3=2    C3=4           D3=20260115
A4=C    B4=3    C4=6           D4=20260115
```

- ✅ 数据集、参数、纵向扩展、**公式列随行扩展**（`=B2*2` 在每行各自求值）全部正确。
- ✅ 导出 `--params` 只传驱动参数即可（与 SKILL.md §6.3 一致）。

### 2.4 扩展方向 `dir`（结论：**可用，但无信号**）

**双路交叉验证，不依赖文档措辞：**

1. **真实模板反查**（`<开发工作目录>/corpus/demo_report.cpt`，670 个单元格）：`columnName="sdt"`（横向日期）全部是 `dir="1"`（c=9/14, r=1）；`columnName="bd_name"`（纵向维度）全部是 `dir="0"`（c=1/3, r=2..24）。样本统计：`dir="0"` 27 个、`dir="1"` 4 个。
2. **我自己造的两个最小模板**（同一份 3 行数据 `A/B/C`）：
   - `v4_h.cpt`（`dir="1"`）→ **A1,B1,C1**（横向）✅
   - `v4_v.cpt`（`dir="0"`）→ **A1,A2,A3**（纵向）✅

**`dir="0"`=纵向、`dir="1"`=横向，确认无误。**

> ❗ **写反的代价 = 零信号**：两个模板导出都 `status: ok`、都是合法 xlsx、无 warning。CLI 不校验、平台不报错，**唯一的发现手段是逐格读回**。
> 文档若要防这个坑，必须写成「验收动作」而不是「参数说明」。

### 2.5 版面能力（结论：**可用**，附三条实测换算）

`v6_layout.cpt`：合并标题 `cs="3"`、表头、两行数据、数字格式 `#,##0`、三列不同列宽。

xlsx 逐格 + 结构读回：

| 能力 | 写法 | 实测结果 | 结论 |
|---|---|---|---|
| 横向合并 | `<C c="0" r="0" cs="3">` | `merged A1:C1` | ✅ |
| 纵向合并 | `<C ... rs="2">` | `merged A2:A3` | ✅ |
| 列宽 | `<ColumnWidth>` CDATA 数组（EMU 风格） | **xlsx 列宽(字符) = 值 ÷ 280800**；600000/3000000/1200000 → 2.137/10.684/4.273，**精确线性** | ✅ |
| 行高 | `<RowHeight>` CDATA 数组 | 723900→16.35pt、1447800→32.75pt、2895600→65.55pt（≈线性，常数 ≈44200 单位/pt）；**窄列长文本会把行撑高**（16.35→28.45），想精确控制行高不可靠 | ⚠️ 可用但受内容影响 |
| 字号 | `<FRFont size="72">` | **单位 1/8 pt**：72→9pt、64→8pt | ✅ |
| 数字格式 | `<Style><Format class="com.fr.base.CoreDecimalFormat" roundingMode="6"><![CDATA[#,##0.00]]>` | B 列 `number_format='#,##0.00'`、渲染 `1,234,567` | ✅ |
| 颜色 | `<Background name="ColorBackground" color="-26368">` | `00FF9900`（橙） | ✅ |
| 水平对齐 | `<Style horizontal_alignment="N">` | **0=居中、2=左、4=右**；奇数（1/3/5）被忽略（导出里为 None） | ⚠️ **反直觉，文档必须写死这张表** |
| PDF | `export pdf` | 65KB、`%PDF-`、1 个 Page 对象、`/Catalog` 正常 | ✅ 版面不炸 |
| 服务端渲染 | `report image` | PNG 793×1122，**人眼复核：合并标题橙底、表头边框、数字千分位、列宽差异全部正确** | ✅ |

> 字体体检提醒：`<FRFont>` **不写 `name`** 会被 `report fonts` 判成缺字体 `Default`（`ok:false`）。要体检干净就显式写 `name="微软雅黑"` / `name="SimSun"`。

### 2.6 参数语义矩阵（**改写 Lead 的"已知事实 2"**）

Lead 原话：「参数未声明为模板参数时，`$x` 静默求值成空字符串」。**实测不成立**，我做了 4 组对照（每组都逐格读回）：

| 用例 | 模板参数声明 | `--params` | `$min_center` 渲染 | 结论 |
|---|---|---|---|---|
| `p1_decl` | ✅ topn=3, min_center=SC03 | `{"min_center":"SC09","topn":"7"}` | `SC09` / `7` | 传值覆盖默认 |
| `p2_undecl` | ❌ 完全没有 `<Parameters>` | 同上 | **`SC09` / `7`** | **没声明也照样绑定** |
| `p1_decl` | ✅ | 不传 | `SC03` / `3` | 声明提供默认值 |
| `p2_undecl` | ❌ | 不传 | **``（空字符串）** | **真正的坑在这** |

**修正后的规则（建议照此写入文档）：**

| 位置 | 正确写法 | 错误写法的后果 |
|---|---|---|
| 数据集 SQL | `${x}` | 写 `$x` → **原样字符串进 SQL**（实测 `select '$topn'` 渲染出字面量 `$topn`），不报错 |
| 单元格公式 | `$x` | 写 `${x}` → **原样字面量**（实测渲染出 `${min_center}` 六个字符），不报错 |
| 任意位置 | 参数必须有值 | **无值且无默认 → 静默空字符串**，导出成功、无 warning |

- **声明的唯一作用是提供默认值**（`ReportParameterAttr > Parameters`，形如 `<Parameter><Attributes name="topn"/><O><![CDATA[10]]></O></Parameter>`）。
- **最阴的组合**：agent 自测时总带 `--params`（测得出正确结果），用户不带参数打开就是空白 —— 属于"交付即坏"。
- **有无信号？** 几乎为零：`export` 无 warning；`report info` 的 `parameters` **恒为 `[]`（BUG，见问题 P2）**。
  唯一可用信号是 **`report paras`**：`p1_decl` 报出 `topn=3/min_center=SC03`，`p2_undecl` 只报平台自带的 `tcmd`。
  但它报不出"公式里引用了不存在的参数"，所以**最终验收仍然只有逐格读回**。
- 附带发现：每个模板都隐含一个平台参数 `tcmd`（`report paras` 里总会出现，`value: ""`）。

### 2.7 越界矩阵（哨兵法，结论：**守门完好**）

`FRCLI_WRITE_SCOPE="demo_group/demo_user/skill测试"`（或完全不设）下，目标取：

```
demo_group/other_user/legacy_rpt.cpt                    ← 历史事故目标
demo_group/demo_user/dept_a/dept_b/sales_daily.cpt
demo_group/demo_user/skill测试_evil/x.cpt        ← 兄弟目录
demo_group/demo_user/skill测试x/x.cpt            ← 前缀兄弟
demo_group/demo_user/skill测试/../other_user/x.cpt    ← .. 穿越
reportlets/…/skill测试/../../other_user/x.cpt
demo_group/other_user/..%2flegacy_rpt.cpt
```

对 `report upload` / `report delete --force` / `report edit --apply` / `rpc call … write` 四类写命令：

- **不设范围** → 全部 `exit=1`、**零请求**、报错含「未指定范围…二选一」（fail-closed ✅）
- **设了范围但目标在外** → 全部 `exit=1`、**零请求**、报错含「限制在 … 之内」（✅ 含 `..`、兄弟目录、URL 编码）
- **范围内** → 正常走到网络层（✅ 用哨兵自检证明，不是假绿）

固化为 `tests/test_write_scope_zero_requests.py`（22 条，全绿）。

### 2.8 对抗性测试（**本轮最大价值**）

11 个故意写坏的模板依次 `report upload` + `export excel`：

| 用例 | 上传 | 导出 | 逐格读回 | 判定 |
|---|---|---|---|---|
| `s="9"`（StyleList 为空） | ✅ ok | ✅ ok | 文本在，**样式静默丢失**（用默认样式） | 🔴 静默 |
| `s="1"`（只有 1 个样式，0-based 越界） | ✅ ok | ✅ ok | 同上，静默回退 | 🔴 静默 |
| `dsName="nope"`（不存在的数据集） | ✅ ok | ✅ ok | **空单元格** | 🔴 静默 |
| `columnName` 不在结果里 | ✅ ok | ✅ ok | **空单元格** | 🔴 静默 |
| 数据集名 `""` | ✅ ok | ✅ ok | **空单元格** | 🔴 静默 |
| 公式 `=1+` | ✅ ok | ✅ ok | **空单元格** | 🔴 静默 |
| 缺 `<PrivilegeControl/>` | ✅ ok | ✅ ok | 内容正常 | 🟢 可选元素，无需写 |
| 单元格越出 `<RowHeight>/<ColumnWidth>` 数组范围（数组 2×2，写在 `c=3 r=5`） | ✅ ok | ✅ ok | **D6 正常渲染**（数组只是"逐行/列覆盖值"，不是边界） | 🟢 无风险 |
| 同一行两个 `dir="1"`（疑似冲突） | ✅ ok | ✅ ok | 各自独立横向铺开（`A B 1 2`），不算冲突 | 🟢 |
| 重复坐标 `<C c="0" r="0">` 两次 | ✅ ok | ✅ ok | **后写覆盖前写**，前者消失，无提示 | 🟠 静默覆盖 |
| 两个同名 `<TableData name="ds1">` | ✅ ok | ✅ ok | 渲染用**最后一个**；`report datasets` 也只列最后一个（重复被隐藏） | 🟠 静默 |
| **残缺 XML（未闭合标签）** | ✅ **ok（照传）** | ❌ `EXPORT_ERROR 导出产物魔数不符…坏产物已改名保留` | — | 🟠 靠魔数兜住，但坏模板已落服务器 |

**关键判据**：`export` 的魔数校验（0.6.0 内置）**能**拦住"服务端解析不了"的模板（残缺 XML → HTML 出错页 → 拦下）；
但**拦不住**"服务端解析得了、语义是错的"模板 —— 后者导出一份**完全合法、内容为空/样式丢失**的 xlsx。
所以「导出成功」在创作场景里**几乎没有验收价值**，必须逐格读回。

### 2.9 编辑既有模板（结论：**可用**，但"改单元格"不支持）

- `report edit` 只作用于 `<TableDataMap>`（数据集 SQL/连接/参数默认值），**改不了单元格**（`cpt-xml.md` 明确写了，属实）。
- 编辑报错质量实测良好：
  - 数据集不存在 → `模板里没有数据集 nosuchds；现有: ds1`（点名现有数据集，可直接改对）✅
  - `--replace` 格式错 → `--replace 要写成 OLD=NEW，收到 'k]]>v'` ✅
- `]]>` 无法通过 `set_text` 悄悄写进 CDATA（`cptxml.set_text` 直接报错，`test_cptxml.py` 已固化）—— 这条防线成立。
- **端到端"改一格"验证（已做，用团队模板而非生产模板）**：

  | 步骤 | 命令 | 实测结果 |
  |---|---|---|
  | 1 取原件 | `report download …/table2.cpt -o t2_base.cpt` | SHA256 `6869328c…` |
  | 2 基线导出 | `export excel` | `A1=key`，dims `A1:B4` |
  | 3 只改一格 | 本地字节替换 `<![CDATA[key]]>` → `<![CDATA[品类]]>` | 文件长度 −1 字节 |
  | 4 覆盖上传 | `report upload --force` | `overwritten=true`、`verified=true`、**自动备份** |
  | 5 改后导出 + 逐格 diff | `export excel` | **只有 `A1: key→品类` 变了，其余 7 格全同，dims 不变** ✅ |
  | 6 还原 | 上传原件 → 再下载 | 下载 SHA256 = `6869328c…`（**逐字节还原**）✅；导出 A1 回到 `key` ✅ |
  | 7 备份核对 | `~/.frcli/backups/…table2.cpt` | SHA256 `6869328c…` = 原件 ✅ |

  结论：**「下载 → 本地改 → 覆盖上传 → 导出验收 → 还原」这条闭环完全可用，改动不外溢，备份可用于回滚。**

- **端到端"改一格"验证（真实生产模板的副本，Lead 已批准）**：目标
  `demo_group/demo_user/dept_a/demo_report.cpt`（**只读+复制**，原件全程零写操作，事后 SHA256 复核不变）。

  | 步骤 | 命令 | 实测结果 |
  |---|---|---|
  | 1 读原件 | `report download …/demo_report.cpt -o t8_orig.cpt` | 357372 B，SHA256 `b2fc0db0…` |
  | 2 复制进测试目录 | `report upload t8_orig.cpt …/skill测试/t8_copy.cpt` | `verified: true` |
  | 3 **修坏数据集**（副本的 `ds_target` 引用不存在的表） | `report edit --dataset "ds_target" --sql "select 1 as shop_id,…"` → `--apply` | dry-run diff 正确；`applied:true`、`upload.verified:true`、自动备份 ✅ |
  | 4 基线导出 | `export excel --params '{"extype":"simple"}'` | 97350 B xlsx，5 个 sheet |
  | 5 **只改一格** | 字节替换 `<![CDATA[【门店】]]>`→`<![CDATA[【门店】改]]>`（**全文唯一**，+1 字节） | `report upload --force` → `verified:true` |
  | 6 改后导出 + 全表逐格 diff | 同上 | **字符串差异恰好 1 个 = `说明!A1: 【门店】→【门店】改`**；版面 dims（`A1:AE20/AE44/AE86/AE86/A12`）与非空格数（578/1298/2436/2436/10）**完全一致** ✅ |
  | 7 原件核验 | 再 `report download` 生产原件 | SHA256 `b2fc0db0…` **未变**（确认没碰生产）✅ |
  | 8 清理 | `report delete …/t8_copy.cpt --force` | 副本已删，测试目录无残留 ✅ |

  ⚠️ **关键副产品（这条建议进文档）**：同一份数据渲染两次，**有 216 个数字格不同**，但最大相对误差只有 **4.5e-12**（Impala 聚合顺序/舍入导致的重算抖动），**>1e-6 的一个都没有**。
  所以「逐格 diff 断言只有预期处变了」**不能直接全量等值比较**，否则会被 216 个假阳性淹没。正确做法：
  ① 先按类型分离（字符串 vs 数值）；② 数值给容差（实测 1e-9 足够）；③ 版面按 `dimensions` + 非空格数比对。
  这与 SKILL.md §6.10「别用整体 hash 判断模板被改」是同一类陷阱的**导出值版本**。

- **顺带发现（生产侧现状，非本团队引入）**：
  1. `demo_group/demo_user/dept_a/demo_report.cpt` **当前是坏的**：数据集 `ds_target` 查
     `demo_db.demo_tmp_target`，服务端报 `Could not resolve table reference`（错误代码 11300001）。这正是 SKILL.md §6.5 描述的那类"报表自己坏了"。
  2. 修好数据集后仍报 `错误代码:11300002 行高列宽超出页面大小设置`，加 **`--params '{"extype":"simple"}'`** 才导出成功 —— SKILL.md §6.3 那句"`extype=simple` 可绕开部分模板分页报错"**实测有效**，建议在创作/导出章节明确写上（我一开始没想到，是回头翻 §6.3 才试通的）。
  3. **语料样本与线上版本不同**：`<开发工作目录>/corpus/demo_report.cpt` = 670 格 / `dir` 计数 {0:27, 1:4}；
     线上当前版 = **1113 格** / {0:50, 1:6}，列坐标也不同（`sdt` 在 c=9 vs c=10）。两版都验证了 `dir` 语义一致（`sdt`→`1`、`bd_name`→`0`）。
     若 T4 文档以该语料为"取证来源"，需注意它是**旧版**。

---

## 3. 问题清单（带严重级）

| # | 严重级 | 问题 | 证据 | 建议 |
|---|---|---|---|---|
| **P1** | 🔴 高 | **`report upload` 无任何结构校验**：残缺 XML 也照写服务器（`verified: true`），坏模板会在平台上服务给其他用户，直到导出才暴露 | `a_badxml.cpt`：upload `status:ok` → export 才 `EXPORT_ERROR` | 本地做**良构性校验**（`ET.fromstring` 一行，零成本零误报）。「是不是 WorkBook」与「是不是合法 XML」是两件事，现在只查了前者 |
| **P2** | 🔴 高 | **`report info` 的 `parameters` 恒为 `[]`**，但 `SKILL.md` §3 把它描述成「数据集名清单 + **参数清单**」→ agent 会据此误判「我的参数没生效」 | `p1_decl.cpt` 明明有 `topn/min_center`，`info.parameters=[]`；`report paras` 正确报出 `topn=3` | 二选一：修 `report info`，或把 SKILL.md 改成「参数清单看 `report paras`」（Lead 已转 T4） |
| **P3** | 🟠 中 | **`report delete` 对目录路径照删**：实测 `report delete "…/skill测试/子" --force` 直接返回 `deleted:true, size:4096`，没有任何"目标是目录"的提示 | 我用它清理自己误建的子目录（成功）；若手滑指向生产报表目录，整个目录对使用者"消失"（回收站可恢复） | 目标是目录时要求**二次确认标志**（如 `--recursive`），或在输出里显式标注 `deleted_directory: true` |
| **P4** | 🟠 中 | **6 类"语义坏模板"全部静默**（`dsName`/`columnName`/公式/空数据集名/参数无值/`s=` 越界）：上传 ok、导出 ok、合法 xlsx、内容为空或样式丢失 | §2.8 表格 | CLI 难以全知，但文档必须把**「逐格读回」写成强制验收步骤**，并给一份"必查清单" |
| **P5** | 🟠 中 | **`dir` 写反无信号**（只是表格横着长）；文档若无"怎么发现"，等于没防 | §2.4 | 文档写成验收动作：`openpyxl` 读 `max_row/max_column` 或比对首行/首列取值 |
| **P6** | 🟡 低 | **参数无值 → 静默空字符串**，且 agent 自测总带 `--params` 所以测不出来 | §2.6 | 创作命令（T4）为每个参数**落默认值**；文档加一条「不带 `--params` 再导一次」的验收 |
| **P7** | 🟡 低 | **重复坐标单元格 / 重名数据集**：后者连 `report datasets` 都只显示最后一个，重复完全不可见 | §2.8 | 文档列为禁忌；T4 的 `report new` 生成时可自查重名 |
| **P8** | 🟡 低 | 单元格内 `\n` 被吃掉；`horizontal_alignment` 取值反直觉（0=中/2=左/4=右，奇数被忽略）；`<FRFont>` 不写 `name` 会被 `report fonts` 判缺 `Default` | §2.2 / §2.5 | 全部写进 `references/cpt-authoring.md` 的速查表 |

---

## 4. 文档缺口（"照文档造报表"卡点实录）

**第一轮时点的客观状态**：`references/cpt-authoring.md` **不存在**；`references/cpt-xml.md`（115 行）只覆盖 `<TableDataMap>`，并在 §1 明确「本 CLI 不动」版面/单元格；`SKILL.md` §1 写「**不适合：从零设计 .cpt 的版面与控件**」。

按"只读文档"的路径，会依次卡在这些地方：

| # | 卡点 | 现状 | 需要补什么 |
|---|---|---|---|
| D1 | **骨架从哪来** | 文档没有"从零"的起点，`cpt-xml.md` 只描述已存在模板的结构 | 给一个**内置最小骨架**（或 `report new`），并说明清空 `<TableDataMap>/<CellElementList>` 即可用 |
| D2 | **单元格语法零文档** | `<C c= r= cs= rs= s=>` / `<O>` / `<O t="XMLable" class="com.fr.base.Formula">` / `<O t="DSColumn">` / `<Expand dir=>` 全部只能从语料反推 | 单元格元素速查表（含可选元素 `<PrivilegeControl/>`） |
| D3 | **坐标系与越界** | 未说明 `c`/`r` 是 0-based、以及越出 `RowHeight/ColumnWidth` 数组**不会**越界（我实测确认） | 明确"0-based + 数组非边界" |
| D4 | **样式怎么定义/引用** | `<StyleList>` 顺序即索引、`s=` 指向它、越界静默回退 —— 全无文档 | 索引语义 + 越界行为 |
| D5 | **参数怎么声明** | `ReportParameterAttr > Parameters` 一字未提（我是从 Lead 的样例反推的） | 声明位置 + 默认值 + 与数据集 `<Parameters>` 的区别 |
| D6 | **`$x` vs `${x}`** | 无文档 | 位置表（§2.6）+ "无值即空"的告警 |
| D7 | **列宽/行高/字号/对齐单位** | 无文档（本文 §2.5 给出了实测换算） | 换算表（列宽 ÷280800、行高 ≈÷44200、字号 1/8pt、对齐 0/2/4） |
| D8 | **验收怎么做** | 只有「导出校验魔数」，对创作场景不够 | 「逐格读回」的固定命令 + 必查项清单 |
| D9 | **SKILL.md 自相矛盾** | §1「不适合从零设计 .cpt 的版面与控件」 vs 新增创作能力 | 改写成"能到什么程度、不能到什么程度"（如：复杂图表/控件仍需 Designer） |

---

## 5. 新 agent 上手路径（第一轮实测可行版，6 步）

> 前提：`export FRCLI_WRITE_SCOPE="demo_group/demo_user/skill测试"`、`export FRCLI_TIMEOUT=300`（复杂报表）。

```bash
# 1) 拿骨架：清空 <TableDataMap> 与 <CellElementList>（其余逐字节保留）
#    skeleton = corpus 模板 经 re.sub 清空两个块（本报告用 <开发工作目录>/corpus/TOP品店日均&门店数.cpt）
#    （T4 落地后此步应变成一条命令：report new / report scaffold）

# 2) 写数据集（纯字面量 SQL 先跑通链路，避免依赖具体表）
#    <TableData name="ds1" class="com.fr.data.impl.DBTableData">
#      <Parameters/>  <Attributes share="true" maxMemRowCount="-1"/>
#      <Connection class="com.fr.data.impl.NameDatabaseConnection">
#        <DatabaseName><![CDATA[demo_conn]]></DatabaseName></Connection>
#      <Query><![CDATA[select ...]]></Query><PageQuery><![CDATA[]]></PageQuery></TableData>

# 3) 写单元格：文本 <O><![CDATA[字]]></O> / 公式 <O t="XMLable" class="com.fr.base.Formula">
#    取数 <O t="DSColumn"><Attributes dsName="ds1" columnName="k"/><Complex order="0"/>
#         <Result><![CDATA[$$$]]></Result></O>；扩展 <Expand dir="0"/>（0=纵向 1=横向）
#    样式引用 s="0"；合并 cs="3"（横向）/ rs="2"（纵向）

# 4) 声明参数（要默认值就写这里；不写则不带参时为空）
#    <ReportParameterAttr>…<Parameters>
#      <Parameter><Attributes name="edate"/><O><![CDATA[20260115]]></O></Parameter>
#    </Parameters></ReportParameterAttr>

# 5) 上传（写范围守门 + 占锁 + 备份 + 回读 SHA256）
frcli report upload /tmp/verify/v3_table.cpt "demo_group/demo_user/skill测试/v3_table.cpt"
#    → 必须看到 "verified": true

# 6) 验收：导出 → 逐格读回（**这一步不能省**，见 §2.8）
frcli export excel "demo_group/demo_user/skill测试/v3_table.cpt" -o /tmp/v3.xlsx \
    --params '{"edate":"20260115"}'
python3 -c "
import openpyxl; ws=openpyxl.load_workbook('/tmp/v3.xlsx').active
print(ws.dimensions, ws.merged_cells.ranges)
for row in ws.iter_rows(): print([(c.coordinate,c.value) for c in row if c.value is not None])"
#    再导一次**不带 --params**，确认默认值生效（否则用户打开就是空白）
```

**必查项（缺一不可）**：① `verified: true` ② 魔数（xlsx=`PK`/pdf=`%PDF`）③ 逐格值 ④ `max_row/max_column` 与扩展方向一致 ⑤ 不带 `--params` 再导一次 ⑥（可选）`report image` 人眼复核版面。

---

## 6. 交付物与清理

- 本报告：`docs/验证/cpt创作验证报告.md`
- 离线回归：`tests/test_write_scope_zero_requests.py`（22 条，全绿；含哨兵接线自检）
- 构造器与样本：`/tmp/verify/`（`mk.py`、各 `*.cpt`、`*.xlsx`，一次性，未入库）
- **测试目录已清干净**（我自己的 23 个测试产物全部 `report delete` 掉）：现只剩 `_目录说明.txt`、`golden.cpt`（Lead 样例）、
  `hello.cpt`/`table.cpt`/`table2.cpt`（本轮团队样本）、`t4_table.cpt`（cpt-author 样本）
  （`report ws-list` 复核 `count: 6`）。过程中误建的 `skill测试/子/` 与其内 `x.cpt` 已删除。
- 全程未触碰任何非本团队创建的模板/任务；除测试目录外**零写操作**；本轮**未创建/修改/运行任何定时任务**。

---

## 7. 验证装置本身的坑：哨兵接缝（单列，Lead 要求进 AGENTS.md 坑点）

**现象**：第一版越界哨兵 patch 的是 `FineReportClient._request`，结果出现**两处反常**：
① 范围外的用例"零请求"通过（看起来守门完美）；② **范围内**的用例 `exit=0` 且"零请求" —— 而后者的语义应该是"走到网络层"。

**根因**：`report upload/delete/edit --apply` 走的是 `remotedesign.RemoteDesignClient`，它**自带一个 `httpx.Client`**（`remotedesign.py:_client()`），
与 REST 通道的 `FineReportClient._request` 是**两条独立的路**。只 patch 后者 → 远程设计通道**完全没被拦**。

**后果（真实发生过）**：那次"范围内"用例**真的把模板写到了服务器**（我因此误建了 `skill测试/x.cpt` 与子目录 `skill测试/子/x.cpt`，已全部清理）。
也就是说：**一个接错缝的哨兵，会同时产生"假绿"和"真实副作用"**。

**正确接缝**：`httpx.Client.request`（`Client.get/post` 都经过它，REST 与远程设计两条通道一起覆盖）。

**固化的自检**（`tests/test_write_scope_zero_requests.py`）：
- 范围外 × 3 类写命令 × 5 种绕过路径 → `exit != 0` **且 `sentinel == []`**（零请求）
- **`test_in_scope_reaches_network`：范围内必须真的发出请求** —— 这条是**装置自检**，
  专门防"patch 接错缝导致的假绿"。没有它，上一条"零请求"毫无意义。

**推广**：任何"零副作用"断言（零请求 / 零写入 / 零删除）都必须配一条**阳性对照**，
证明"该发生的时候确实发生了"。否则断言的是"我的监测坏了"，不是"系统安全"。

---

## 8. 第二轮待办（等 T4 落地）

1. **只照 `references/cpt-authoring.md` + `SKILL.md` 造一张"像样"的报表**（不许看源码/语料）→ 逐条记录卡点（本文 §4 是第一轮的基线，第二轮要复测是否被 T4 覆盖）。
2. **对抗性复测**：T4 新命令是否把 §2.8 的 6 类静默错误变成**明确报错**（这是衡量 T4 价值的核心指标）。
3. **编辑既有模板端到端**：复制 `demo_report.cpt` → 改一个单元格 → 导出逐格确认"只有预期处变了"（需 Lead 确认可运行该副本）。
4. `report info` 参数清单（P2）是否已修。

---

## 9. 问题状态跟踪（滚动更新）

> 第一轮的结论按"发现当时"记录，不追改；这里只跟踪**当前是否已修**，第二轮做最终复验。

| # | 问题 | 当前状态 | 复验证据 |
|---|---|---|---|
| P1 | `report upload` 无结构校验（残缺 XML 照传） | ✅ **已修**（T4 落地） | 残缺 XML（mismatched tag）→ `⛔ 拒绝：内容不是良构 XML（mismatched tag: line 15, column 54），已拒绝写入…`；CDATA 含 `]]>` 同样被拒；对照文件（去掉 `]]>`）正常通过 → 拒绝是精确的，不误杀。已固化为 `tests/test_write_scope_zero_requests.py` 的 7 条良构性回归 |
| P2 | `report info` 的 `parameters` 恒为 `[]` | ✅ **已修**（T4 落地） | 声明了 `topn/min_center` 的模板现返回 `parameters: ["min_center","tcmd","topn"]` + 新字段 `parameters_from: "template/paras + 模板内 <Attributes>"`。注意 `tcmd` 是平台隐含参数，会一并列出（正常） |
| P3 | `report delete` 对目录照删 | ✅ **已修并复验**（第二轮） | 不带 `--recursive` → `⛔ …是一个**目录**：删除会把整个目录（含里面全部模板）移入回收站…`；带 `--recursive` → `deleted:true, deleted_directory:true`（自建临时目录实测，测完已删） |
| P4 | 8 类"语义坏模板"静默 | 🟡 **新命令路径已修；`report upload` 路径仍全静默** | 见 §10.2：Battery B（新命令）9/14 硬报错；Battery A（手写 XML + upload）8 类照旧静默 → 新增 P10 |
| P5 | `dir` 写反无信号 | ✅ **已被文档覆盖** | `cpt-authoring.md` §4.2 对照表 + §7.7 发现办法（看行数还是列数变多） |
| P6 | 参数无值 → 静默空 | ✅ **已被文档覆盖** | §7.2 写明「既没传值、又没默认值 → 静默空字符串」，且无默认值的 `--param` 出 stderr ⚠ |
| P7 | 重复坐标 / 重名数据集 | 🟡 文档未覆盖 | 新命令路径下也未拦（本轮实测仍静默接受） |
| P8 | 排版换算三条反直觉点 | ✅ **已被文档覆盖** | §4.5/§4.6（列宽 ÷280800、行高 ÷44200、字号 1/8 磅、对齐 0/2/4、颜色补码、`FRFont` 必须写 name） |
| **P9** | **xlsx 聚合值可静默出错（且随时间摆动）** | 🔴 **新发现（第二轮最重要）** | §10.5：同一时刻 xlsx 合计 = 200（错）vs CSV/PNG = 600（对）；同一模板字节在不同时段导出过 4567.7 / 2345.6 / 4567.7 |
| **P10** | 语义校验只在命令路径生效 | 🟠 新增 | §10.2 Battery A/B 对照 |
| **P11** | 列宽没有命令 | 🟠 新增 | §10.1.1 F1 |
| **P12** | 文档小瑕疵 4 处 | 🟡 新增 | §10.1.1 F2–F6 / §10.3 |

> 附带修复：`tests/test_download_and_write_guards.py::test_guard_is_a_heuristic_not_a_sandbox` 因 P1 新增的良构门而变红
> （旧载荷含 NUL 字节）。建议把载荷改成**良构**的 `b"<!-- <WorkBook --><x/>"`（实测仍放行，原测试意图"启发式而非沙箱"完整保留）。

---

# 第二轮：T4 落地后的复验（`references/cpt-authoring.md` + `report new/cell/dataset/param/style/table`）

> 方法：**只读 `references/cpt-authoring.md` + `SKILL.md`，不看源码、不抄 Lead 的黄金样例**。
> 卡住就停在那一步、记下来 —— 这份"卡点实录"本身就是 T4 是否达标的判据。

## 10.1 只照文档造一张"像样"报表（item 5）→ **可用**

按 `cpt-authoring.md` §1 五步 + §2 命令速查，一次没翻源码就造出来了：

| 需求（本轮验收项） | 用的命令 | 实测结果 |
|---|---|---|
| 建骨架 | `report new … --apply` | 2050 B 骨架，`applied:true` |
| 数据集 + 参数 | `report dataset --add ds_sales --conn demo_conn --sql "…" --param edate=20260115 --apply` | 两处默认值都写了；出 `ℹ 数据集还声明了 SQL 里没用到的参数：edate`（我故意留的，给公式用） |
| 表头样式 | `report style --add --bold --bg '#FFF2CC' --align center --border --apply` | `style.add index:0` |
| 表头 + 多列 + 纵向扩展 | `report table --at A2 --columns center_code,center_name,sales_amt,gp_amt --header --labels "中心编码,中心名称,销售额,毛利额" --header-style 0 --apply` | 表头 r2 + 数据 r3，`dir="0"`；出 `⚠ 列名不做离线校验（要连库）` |
| **公式列** | `report cell --at E3 --set-formula "=D3/C3" --num-format "#0.0%" --expand v --apply` | 每行各自求值 ✅ |
| 标题（参数 + 合并） | `report cell --at A1 --set-formula '="销售概览 " + $edate + "（含毛利率）"' --merge A1:E1 --bold --bg '#D9E1F2' --align center --apply` | `merged A1:E1` ✅ |
| 合计行 | `report cell --at A4/ C4/D4/E4 --set-value/--set-formula "=SUM(C3)" … --num-format "#,##0.00"` | 合计行自动随扩展下移到第 6 行 ✅ |
| 数字格式 / 右对齐 | `report cell --at C3 --num-format "#,##0.00" --align right` | `C3 fmt=#,##0.00, align=right` ✅ |
| **列宽** | —— | ❌ **文档化命令里没有**（见 10.4 D7 / 问题 P11） |

**逐格验收（openpyxl）**：

```
merged: ['A1:E1']   dims: A1:E6
['销售概览 20260115（含毛利率）', None, None, None, None]
['中心编码', '中心名称', '销售额', '毛利额', None]
['SC01', '华北', 1234.5, 321.2, 0.26018631024706357]
['SC02', '华南', 2345.6, 654.3, 0.27894781718963163]
['SC03', '华西', 987.6, 210.1, 0.2127379505872823]
['合计', None, 4567.7, 1185.6, 0.2595617050156534]     ← 注意：见 10.5，这个数字后来变过
A2 bold=True fill=00FFF2CC | A1 bold=True fill=00D9E1F2 | C3 fmt=#,##0.00 align=right
```

**服务端渲染复核**（`report image` → 人眼看）：标题/表头/三行数据/数字格式/列宽差异全部正确。

**结论：可用。** 除列宽外，任务要求的「表头 / 多列 / 样式 / 数字格式 / 参数 / 公式列」全部一次跑通，命令语义与文档一致，报错信息都指得出下一步。

### 10.1.1 照文档造报表时卡住的 6 处（含轻量级）

| # | 卡点 | 级别 | 说明 |
|---|---|---|---|
| F1 | **列宽没有任何命令** | 🟠 中 | `new/cell/style/table` 的 `--help` 全查过，无 width 选项；文档 §4.6 教了 XML 与换算公式（÷280800）却没给"怎么把它写进去"。我最后用 `download → 字节改 ColumnWidth → upload --force` 才设成（实测 A=12/B=16/C=14/D=14/E=10 精确生效）——**这条路径文档没写** |
| F2 | **合计行/聚合没有配方** | 🟠 中 | §4.1 只出现 `=SUM(C3:C9)` 这种**固定区间**示例；没有任何地方讲"合计行怎么写、放哪、会不会跟着扩展下移"。实测它**会自动下移**（写在 A4，3 行数据后落到第 6 行），这点文档完全没提，agent 很可能自己算位置或以为要写死区间 |
| F3 | §1 五步例子自相矛盾 | 🟡 低 | 步骤 2 的 SQL 里没有 `${min_center}`，但步骤 5 的文字说「`--params` 传 `min_center` 时 SQL 的 `${min_center}` 也跟着过滤」——例子与叙述对不上 |
| F4 | `ℹ 数据集还声明了 SQL 里没用到的参数：edate` | 🟡 低 | 提示本身**有用**（防手滑），但文档没解释这个提示的含义；我的用法是故意的（参数给公式用），看到提示会怀疑自己写错了 |
| F5 | `--num-format` 每次新建一个样式 | 🟡 低 | 连写 4 个格子 → StyleList 增长 4 次。文档 §4.5 只说 `--style N` 绑定已有样式，没说 `--num-format` 是"新建"语义，久了样式表会膨胀 |
| F6 | 公式列怎么随行扩展没有例子 | 🟡 低 | §4.1 的公式是 `=SUM(…)`（静态），没有"一行一个比率的公式列"示例。我是靠 `--set-formula` + `--expand v` 推出的 `=D3/C3`，实测可行 |

## 10.2 十二类"静默坏模板"复测（item 2）→ **新命令路径：好；`report upload` 路径：零校验**

同一批坏模板，走**两条不同路径**，结果完全不同：

**Battery A —— 手写 XML → `report upload`**（第一轮的原始路径）

| 用例 | 结果 |
|---|---|
| 残缺 XML（mismatched tag） | ⛔ 拒绝「内容不是良构 XML（mismatched tag: line 15, column 54）…」 |
| `dsName` 不存在 / `columnName` 错 / 数据集名空 / `s=` 越界 / 公式 `=1+` | ✅ **全部静默接受**（8 类） |
| 重复坐标 / 重名数据集 / 相邻列都 `dir="1"` / SQL 裸 `$x` / 公式 `${x}` | ✅ 静默接受 |

**Battery B —— 走新命令（`report cell/dataset/table`）**：14 项里 **9 项硬报错、3 项 stderr ⚠、2 项静默**（静默的两项正是 Lead 认定"已知局限"的列名与扩展冲突）。

| 用例 | 结果 |
|---|---|
| `--bind nope.k` | ⛔ 单元格绑定的数据集 'nope' 不在模板里；现有: ds1（先用 `report dataset --add` 建） |
| `--set-formula "=1+"` | ⛔ 公式以 `+` 结尾，写完整再提交（服务端会静默渲染成空白，不报错） |
| `--style 9`（越界） | ⛔ `--style` 给的样式索引 9 越界：模板 `<StyleList>` 里只有 0 个样式（0..-1） |
| `--bind ds1`（缺列名） | ⛔ 数据集列要写成 数据集名.列名 |
| `--at A0` / `--at 1A` | ⛔ `'A0'` / `'1A'` 不是合法的 A1 单元格地址（应形如 A1 / B3 / AA10） |
| `--merge B1:C1` 与 `--at A1` 不符 | ⛔ `--merge B1:C1` 的左上角必须是 `--at A1`（合并信息存在左上角格） |
| `--set-value "a]]>b"` | ⛔ 单元格文本含 `]]>`，无法安全放进 CDATA 段 |
| SQL 裸 `$x` | ⛔（同时 stderr ⚠）数据集 SQL 里的参数必须写 `${x}` |
| 公式写 `${x}` | ⛔（同时 stderr ⚠）单元格公式里的参数要写 `$x` |
| SQL 引用未声明参数 | ✅ + stderr ⚠ 不传值时会被替换成空字符串 |
| `--param` 无默认值 | ✅ + stderr ⚠ 用户不带参数打开时会静默变成空字符串 |
| 列名写错 / 扩展方向冲突 | ✅ + stderr ⚠（需连库 / 需语义，已知局限） |

**结论与建议**：
1. **新命令的校验质量很高** —— 报错都指名道姓并给出下一步，是这次 T4 最大的价值。
2. ⚠ **但校验只挂在命令路径上**：`report upload`（手写 XML，正是文档 §4 XML 速查 + §3 `--from`/download-edit-upload 所引导的路径）**只有 XML 良构这一道门**，语义问题一律放行。
3. 📌 文档 §7.4 那张表写「CLI 现在 ✅ 本地报错」，**没有限定适用范围**，读起来像是 CLI 整体都会拦 —— 建议补一句：「以上校验在 `report cell/dataset/param/style/table` 生成内容时生效；手写 XML 走 `report upload` 只有良构性校验」。
4. 📌 纵深防御建议（低成本）：`dsName` 是否存在、`s=` 是否越界、数据集名是否为空、公式是否以 `=` 开头、坐标是否重复 —— **这 5 条纯字节可判**，可以顺手套到 `report upload` 上（我第一轮已证明它们都能从模板字节里查出来，不需要连库）。

## 10.3 编辑既有模板副本（item 3，用新命令重做）→ **可用**

目标仍是生产模板 `demo_group/demo_user/dept_a/demo_report.cpt` 的**副本**（原件全程零写操作，事后 SHA256 `b2fc0db0…` 未变）：

| 步骤 | 命令 | 结果 |
|---|---|---|
| 复制 | `report upload t8_orig.cpt …/v_copy.cpt` | `verified:true` |
| 修坏数据集 | `report dataset … --set-sql "ds_target" --sql "select 1 as shop_id,…" --apply` | `applied:true, bytes 357272→357314` |
| 看结构 | `report cell … --list -f table` | 5 sheet / 1113 格，**1.17 s**，中文单元格与绑定一屏可读 |
| 改一格 | `report cell … --sheet 说明 --at A1 --set-value "【门店】改2" --apply` | `applied:true` ✅ `--sheet` 在 5 sheet 模板上正确命中 |
| 导出验收 | `export excel --params '{"extype":"simple"}'` | 5 sheet dims/非空格数与基线**完全一致**；**字符串差异恰好 1 个** = `说明!A1 【门店】→【门店】改2`；数字差异 200 个但最大相对误差 **4.32e-12**（>1e-6 的 0 个）✅ |

> 顺带：`extype=simple` 这一步**文档没提**——我第一轮是回头翻 SKILL.md §6.3 才试通的（不加会报 `11300002 行高列宽超出页面大小设置`）。建议在创作/导出章节写明。
> `report delete` 对刚导出完的模板曾失败一次（未打印原因），随后重试 3 次均成功 → 记为**一次性观察**，未复现，不作为缺陷。

## 10.4 §4 九条文档缺口逐条复测（T4 是否达标的判据）

| # | 第一轮缺口 | 第二轮结论 |
|---|---|---|
| D1 | 骨架从哪来 | ✅ **已覆盖** §1 步骤 1 + §3（内置骨架 / `--from` 裁外壳） |
| D2 | 单元格语法零文档 | ✅ **已覆盖** §4.1 四种 `<O>`（静态/公式/DSColumn/数值常量）+ §4 顶层结构 |
| D3 | 坐标系与越界 | ✅ **已覆盖** §4「`c`/`r` 从 0 开始（`B3` = `c=1 r=2`）」+ §4.6「数组不是边界」 |
| D4 | 样式怎么定义/引用 | ✅ **已覆盖** §4.5（索引 0 起、越界静默、颜色补码、`size` = 1/8 磅、常用格式） |
| D5 | 参数怎么声明 | ✅ **已覆盖** §4.4（两处都要写 + 谁管 SQL 谁管公式） |
| D6 | `$x` vs `${x}` | ✅ **已覆盖** §7.1 对照表 |
| D7 | 列宽/行高/字号/对齐单位 | 🟡 **文档覆盖了、能力没跟上**：§4.6 有 XML 与换算（÷280800、÷44200）、§4.5 有对齐 `0/2/4`，但**没有任何命令能设置列宽**（F1）。文档写的是"XML 怎么写"，读者拿不到"怎么把 XML 写进模板" |
| D8 | 验收怎么做 | ✅ **已覆盖** §6（openpyxl 逐格 + 数值容差 + dims/非空格数判版面）—— **但对聚合列不足，见 10.5** |
| D9 | SKILL.md 自相矛盾 | ✅ **已修**：§1 现在明确列「改已有模板 / **从零创作模板**」两条，"不适合"收窄为「图表控件/填报控件/复杂表头嵌套/.frm 组件布局」，与实际能力相符 |

**9 条里 8 条已达标，1 条（D7）是"文档到了、命令没到"。**

## 10.5 🔴 第二轮最重要的发现：xlsx 导出的**聚合值**可以是错的（CSV/PNG 正确）

**现象**：同一张模板、同一时刻、同一参数，**xlsx 里的合计是错的，CSV 与 PNG 里是对的**。

证据链（`g_shape.cpt`：3 行数据 100/200/300，合计 `=SUM(C3)`；模板自建后先导出两次都得到正确的 600）：

| 观测 | xlsx `C4`（合计） | CSV 尾部 | 服务端渲染 PNG |
|---|---|---|---|
| 建好后前 2 次导出 | **600.0** ✅ | — | — |
| 之后连续 12 次导出 | **200.0** ❌（= 中间那行的值） | `合计,,600,60,` ✅ | 图上是 **600** ✅ |

- 同一现象在另一张模板（`v_r2.cpt`，3 行 1234.5/2345.6/987.6）上表现为 `C4=2345.6`（= 中间行）而非 `4567.7`；D4 同样是中间行的值。
- **明细行永远是对的，只有聚合格错** → 逐格扫一遍很容易看成"数字都挺正常"。
- 但**引擎是对的**：`export csv` 与 `report image`（服务端渲染）都给 600 —— 图见 `证据/聚合行-服务端渲染显示600正确.png`。

### ⚠️ 收尾复核推翻了"字节决定论"：这个错值是**随时间摆动**的

我在写报告前做了最后一道复核，结果**推翻了上面那版的解释**，必须如实记下来：

| 时刻 | `v_r2.cpt` 的 xlsx 合计 | 期间有无写操作 |
|---|---|---|
| T1（刚建好） | **4567.7** ✅ | — |
| T2（做过若干 `report cell` 编辑后） | 2345.6 ❌，**连续 15+ 次导出、跨 ~8 分钟、含 3 个不同路径（含全新路径首次编译）都稳定错** | 无（只有导出/下载） |
| T3（又过了几分钟，写报告时复核） | **4567.7** ✅ | 无 |

- 同期新建的最小复现件 `v_agg_repro.cpt`（100/200/300）：xlsx 与 csv **都是 600**，无差异。
- 也就是说：**同一份模板字节，在不同时间段导出的合计值可以不同**（4567.7 → 2345.6 → 4567.7），我**无法按需复现**，也无法用模板内容解释。
- 已排除：模板字节差异、列宽注入、合计行相邻性（三种几何都对）、报表形状（同结构新建 → 正确）、"全新路径首次编译"（当时也是错值）。
- **剩下来最像的解释是服务端缓存/编译状态**（错值窗口内连"新路径"也错，说明缓存键很可能不是路径，而与数据集 SQL / 报表定义有关）。这条**留给 cpt-author / 平台侧深挖**，我不下结论。

**结论（修正版）**：**"聚合公式作用在扩展格上"时，xlsx 导出的合计值可能在一段时间内稳定地取到某一行，而不是合计；CSV 与 `report image` 同期是对的。** 它不必然发生、也无法按需触发，但对验收的破坏是确定的：
- 错值看起来完全合理（就是某一行真实的数）；
- 同一模板时对时错，**只验一次等于没验**；
- 文档 §6 指定的验收方法恰好是"导出 xlsx → 逐格读回"，**正好踩在这个坑上**。

**建议（高优先级）**：
1. 文档 §6 增加：**含聚合/合计/比率列的报表，必须用 `export csv`（或 `report image`）交叉验证合计行**；只有纯明细表才能只信 xlsx。
2. 更稳的配方：**合计交给 SQL**（`union all select '合计',sum(...)`）而不是单元格公式 —— 明细行由单元格算、合计由数据源算，可完全绕开这个坑。
3. 交付前**同一模板导出两次并比对合计**（xlsx + csv 各一次，成本几秒）。
4. 给 cpt-author 的排查线索：错值窗口内**连全新路径首次编译也错**（`g_A`/`g_B`/`g_shape2` 三个新路径都错）→ 缓存键大概率不是模板路径，优先查"与数据集 SQL/报表定义相关的服务端编译缓存"。

## 10.6 第二轮问题清单（新增）

| # | 严重级 | 问题 | 证据 | 建议 |
|---|---|---|---|---|
| **P9** | 🔴 高 | **xlsx 导出的聚合值可静默出错**（等于某一行），CSV/PNG 同期正确；**同一模板字节在不同时段得到不同值**，无法按需复现 | §10.5 | 文档加"聚合列必须 csv/png 交叉验证"；合计优先放 SQL；排查线索：错值窗口内**连全新路径首次编译也错** → 缓存键大概率与模板路径无关（留给 cpt-author/平台侧） |
| **P10** | 🟠 中 | **语义校验只挂在命令路径**：`report upload` 接手写 XML 时 8 类语义问题全部放行，而文档 §7.4 表格读起来像"CLI 整体会拦" | §10.2 Battery A/B | 文档补适用范围说明；把 5 条纯字节可判的校验（dsName/`s=`/空数据集名/公式 `=` 前缀/重复坐标）也加到 upload |
| **P11** | 🟠 中 | **列宽没有命令**：`new/cell/style/table` 均无 width 选项，文档 §4.6 只给了 XML 与换算，没给写进去的路径（实际要 download→改字节→upload） | F1 | 给 `report cell --col-width`/`report table --widths` 之一；或至少在 §4.6 写出 download→改→upload 的完整步骤 |
| **P12** | 🟡 低 | 文档 §1 五步例子与叙述不一致（`${min_center}` 不在示例 SQL 里）；合计行自动下移、`--num-format` 是新建样式、`extype=simple` 需求 均未写进文档 | F2/F3/F4/F5 + §10.3 | 交 cpt-author 修订 |

**已修复项复验**：P1 ✅（良构门，Battery A 唯一被拦的一类）、P2 ✅（`report info` 现报 `["min_center","tcmd","topn"]` + `parameters_from`）、**P3 ✅**（本轮实测：不带 `--recursive` 删目录 → `⛔ …是一个**目录**：删除会把整个目录（含里面全部模板）移入回收站。确认要这么做就再加 --recursive。`；带 `--recursive` → `deleted:true, deleted_directory:true`）。

## 10.7 新 agent 上手路径（0.7.0 版：从零到一张能导出正确数据的报表）

> 这是**本轮实测走通**的最短路径（§5 那份是第一轮手写 XML 时代的版本，已被本节取代）。
> 前提：`export FRCLI_WRITE_SCOPE="<你被授权的目录>"`、`export FRCLI_TIMEOUT=300`。

```bash
R="demo_group/demo_user/skill测试/我的报表.cpt"

# ① 建骨架（2050 B，自带可渲染结构）
frcli report new "$R" --apply

# ② 数据集 + 参数（参数默认值会同时写进数据集 <Parameters> 与模板参数两处）
frcli report dataset "$R" --add ds1 --conn demo_conn \
  --sql "select 'A' code,'甲' name,100 amt union all select 'B','乙',200" \
  --param edate=20260115 --apply
#   ⚠ SQL 里用 ${edate}；公式里用 $edate（两个世界，见文档 §7.1）

# ③ 表头 + 数据（A1 记法；--at A2 给上面的标题留位置；report table 会整格改写目标区域）
frcli report table "$R" --dataset ds1 --at A2 --columns code,name,amt \
  --header --labels "编码,名称,金额" --header-style 0 --apply

# ④ 标题（公式引用参数 + 合并）
frcli report cell "$R" --at A1 --set-formula '="销售概览 " + $edate' --merge A1:C1 \
  --bold --bg '#D9E1F2' --align center --apply

# ⑤ 公式列 / 数字格式 / 合计行
frcli report cell "$R" --at C3 --num-format "#,##0.00" --align right --apply
frcli report cell "$R" --at A4 --set-value "合计" --apply
frcli report cell "$R" --at C4 --set-formula "=SUM(C3)" --num-format "#,##0.00" --apply
#   ℹ 合计行会自动随扩展下移，不用自己算落点

# ⑥ 列宽（**目前只能这样**：没有命令，见 P11）
frcli report download "$R" -o /tmp/r.cpt
python3 -c "
import re;p='/tmp/r.cpt';d=open(p,encoding='utf-8').read()
w=[12,16,14]+[9.76953125]*19                      # 目标字符宽，换算见文档 §4.6
v=','.join(str(int(round(x*280800))) for x in w)
open(p,'w',encoding='utf-8').write(re.sub(r'(<ColumnWidth defaultValue=\"\d+\">\s*<!\[CDATA\[)[^\]]*',lambda m:m.group(1)+v,d,1))"
frcli report upload /tmp/r.cpt "$R" --force

# ⑦ 验收（**必做，且不能只做一次**）
frcli export excel "$R" -o /tmp/r.xlsx
frcli export csv   "$R" -o /tmp/r.csv        # ← 聚合/合计必须用 csv 对照（见 §10.5）
python3 -c "
import openpyxl;ws=openpyxl.load_workbook('/tmp/r.xlsx').active
print('merged:',[str(m) for m in ws.merged_cells.ranges]);print('dims:',ws.dimensions)
for r in ws.iter_rows(max_row=8,max_col=4):print([c.value for c in r])"
cat /tmp/r.csv                                # 两份合计必须一致
```

**步数**：6 条写命令 + 1 段列宽补丁 + 2 条导出 → **一张带参数/样式/公式列/合计的报表约 10 分钟**（其中卡时间的是列宽那步）。

**验收必查项（缺一不可）**：① 写命令回读 `verified: true`／`applied: true` ② xlsx 魔数 `PK` ③ 逐格值对得上 ④ `dims` 与扩展方向一致（纵向 = 行变多）⑤ **不带 `--params` 再导一次**，确认默认值生效（否则用户打开就是空白）⑥ **csv 与 xlsx 的合计一致** ⑦（可选）`report image` 人眼复核版面。

---

# 11. 定向复验（指纹 `8fe3d53b1de0f5301c5c466af98d64d5` · 0.7.0）

> Lead 在第二轮后改了 4 处（P11 实现 / P9 文档化 / P10 文档收口 / P12 补写），本轮只复验这 4 条。
> 环境核对：指纹 `8fe3d53b…` ✅ 与 Lead 给的一致；`frcli --version` = 0.7.0；`pytest tests/` = **301 passed / 2 failed（历史）/ 1 skipped**；
> 我那条 `tests/test_write_scope_zero_requests.py` = **29 passed** ✅

## 11.1 P11 `report table --widths` 端到端 → **✅ 可用，边界处理到位**

| 用例 | 结果 |
|---|---|
| `--widths 12,16,14`（3 列） | `applied:true`；导出实测 **A=12.0 / B=16.0 / C=14.0**（精确，无量化误差） |
| `--widths 12,16`（少一个） | ⛔ `--widths 给了 2 个，--columns 有 3 列，数量必须一致` |
| `--widths 12,16,14,20`（多一个） | ⛔ `--widths 给了 4 个，--columns 有 3 列，数量必须一致` |
| `--widths 12,0,14` | ⛔ `列宽必须是正数（单位=字符数）: 0.0` |
| `--widths 12,-1,14` | ⛔ `列宽必须是正数（单位=字符数）: -1.0` |
| `--widths 12,16.5,14`（小数） | ✅ 接受 |
| **24 列**（骨架默认只有 22 列宽）→ 自动补齐 | ✅ `applied:true`，下载复核 `ColumnWidth` 数组长度 = **24**，第 24 个 = `6739200`（= 24×280800，与 §4.6 的换算自洽） |

- 🟡 小瑕疵：`--widths 12,abc,14` 的报错是**裸 Python 异常文本** `could not convert string to float: 'abc'`，与其它同族报错（`列宽必须是正数…`）风格不一致。建议包一层成 `--widths 里的 'abc' 不是数字`。
- **P11 结论：关闭。** 文档 §2/§4.6 需补一句"CLI 现在也能设列宽：`report table --widths`"（我上一轮给的 download→改字节→upload 绕法已无必要，报告 §10.7 的 ⑥ 已过时）。

## 11.2 四条文档章节复读（照它做还会不会踩 P9 / P10）

| 章节 | 结论 |
|---|---|
| **§4.7 合计行/公式列配方** | ✅ **配方正确，我还替它补了一条更硬的证据**：文档用**固定区间** `=SUM(C3:C7)`，我担心"数据比区间长时会漏算"，于是实测 —— 6 行数据（1..6）配 `=SUM(B2:B6)`（只覆盖 5 行）→ 导出 **21**（= 全部 6 行之和，**区间会自动伸展**），且 xlsx 与 csv 一致。所以 §4.7 的写法安全，我原先的担心不成立。 |
| **§6.1 含合计/聚合必须交叉验证** | ✅ 准确、可执行：现象、杀伤力（明细对/合计错、错值合理、只验一次等于没验）、三条对策（双通道对 / 合计交给 SQL / 逐行公式不受影响）都写到了，且引用了 `v_r2` 的 4567.7→2345.6→4567.7 实测。**P9 按"平台已知局限 + 对策"收口，我认为可接受** —— 因为根因在服务端缓存且无法按需复现，CLI 层确实修不了。 |
| **§7.4 适用范围框** | ✅ **P10 收口到位**：明确写了「"CLI 现在"这一列指的是**创作命令路径**；`report upload` 只做 XML 良构（+ 根元素）校验，语义问题不拦」，并给了"手写 XML 优先走命令 / 或 upload 后逐格核对"的出路。读一遍不会再被误导。 |
| **§5.9 `11300002` → `extype=simple`** | ✅ 与我第二轮的实测一致（示例副本不加就报该错，加了就好），根因描述（排版超纸张 → 分页导出）合理。 |

- 🟡 **一处结构瑕疵**：`## 6` 里 §6.1 的收尾两条要点（「版面判断看 `ws.dimensions` + 非空格数…」「只读结构核对用 `report cell --list`」）现在被 §6.1 小节标题**隔到了聚合规则后面**，读起来像是"聚合规矩"的一部分（其实属"验收"通用要点）。建议把那两条挪回 §6 的序号列表里（即 §6.1 标题之前）。

## 11.3 SKILL.md §1 与 §6.15 → **发现 1 处事实错误 + 1 处编号错位**

| 位置 | 结论 |
|---|---|
| **§1「改已有模板」条目** | 🟠 **事实错误**：现在写「`report edit` 定点改**单元格**与 SQL」。实测 `report edit --at B3 …` → `Error: No such option '--at'`；它的 Options 只有 `--dataset/--sql/--replace/--connection/--param/--default`，且 `references/cpt-xml.md:119` 明确写「`<Report>`（版面、**单元格**、样式）不在编辑范围内」。**改单元格的命令是 `report cell`**。建议改成：「`report edit` 定点改数据集 SQL/连接/参数（§6.7）；改单元格用 `report cell`（§6.14）」。<br>（危害有限——`--at` 会直接报 Usage 错，属"响亮的失败"；但 §1 是入口章节，会把 agent 引到错的命令上。） |
| **§6.15 的位置** | 🟡 **编号错位**：`### 6.15` 被插在 **§6.1 与 §6.2 之间**，于是 §6 的顺序是 6.1 → **6.15** → 6.2 → 6.3 → … → 6.14 → §7。内容本身准确（现象/杀伤力/三对策与 §6.1 一致，两处交叉引用 `cpt-authoring.md §6.1` 与 `本报告 §10.5` 都有效），但顺序会让顺序阅读者以为跳号/漏节。建议整块移到 §6.14 之后、`## 7.` 之前。 |
| §1「不适合」收窄 | ✅ 与第二轮一致（图表控件/填报控件/复杂表头嵌套/.frm 组件布局），不再与创作能力矛盾。 |

## 11.3.1 Lead 处置记录（在本报告 §11 之后补记）

§11.1–§11.3 提的四处问题**均已修复**，本报告保留原始发现以便追溯：

| 报告项 | 处置 | 验证 |
|---|---|---|
| 11.1 `--widths 12,abc,14` 漏裸 Python 文本 | 已包一层，报 `--widths 只能是数字（列宽字符数，逗号分隔），收到 …` | `test_plan_table_widths_non_numeric_friendly` 固化 |
| 11.2 §6 结构（两条验收要点被 §6.1 隔开） | 已挪回 §6 末尾 | — |
| 11.3 SKILL.md §1「`report edit` 能改单元格」事实错误 | 已改为「`report edit` 定点改**数据集 SQL/连接/参数**；改**单元格**用 `report cell`」 | 见 SKILL.md §1 |
| 11.3 §6.15 编号错位（插在 6.1 与 6.2 之间） | 已整块挪到 §6.14 之后、§7 之前 | `grep -n '^### 6.1[45]\|^## 7'` 顺序为 6.14 → 6.15 → §7 |

§11.5 的处置建议已采纳：**两个 P9 证据件均已删除**；`_目录说明.txt` 已写明
「导出 xlsx 的聚合/合计值可能静默出错，验收请 xlsx × csv（或 `report image`）双通道对」。

**定稿指纹**：`637a5134b0ada767efd42945b8b20db4`（0.7.0），`pytest` 302 passed / 2 历史失败 / 1 skipped。

## 11.4 「零请求」哨兵回归

`tests/test_write_scope_zero_requests.py` = **29 passed**（含 7 条良构性回归 + 1 条"范围内必须真的发请求"的接线自检）✅

## 11.5 结论与两个 P9 证据件的处置建议

**四条复验全部完成**：P11 ✅ 关闭（附 1 条报错文案小瑕疵）；P9 ✅ 文档化到位（另替 §4.7 补证了"固定区间会自动伸展"）；P10 ✅ 按已知局限收口、不再误导；P12 ✅ 四项已补（另新发现 §1 事实错误 + §6.15 编号错位两条小问题）。

**`v_agg_repro.cpt` / `v_r2.cpt` 建议：删。** 理由：
1. 我复验时又各导了一次 —— **两件现在都导出正确且两通道一致**（`v_agg_repro` xlsx/csv 都是 600；`v_r2` csv=4567.7、xlsx 同值）。它们**当前不能复现 P9**，留着容易被后来人误读成"没问题了"或当成可用样例；
2. P9 的持久证据在**文字记录**里（本报告 §10.5 的时间线 + `docs/验证/证据/聚合行-服务端渲染显示600正确.png`），不依赖这两个模板；
3. 想再观测随时可重建：按报告 §10.7 的 6 条命令 10 秒就能造出等价的 `v_agg_repro`。
**若你更想留一个"哨兵"**：只留 `v_agg_repro.cpt`（2 KB 最小件），并在 `_目录说明.txt` 里注明"用于周期性观测 P9，正确值应为 600"。
