# cpt 数据设置（分组 / 列表 / 汇总）验证报告 —— 附 P9 根因裁决

> 验证人：`dsverifier`（独立验证者，与实现者 `dsauthor`、裁决人 Lead 分离）
> 日期：2026-09-27　版本：fanruan_v10 0.7.0　靶子：`report table/cell` 新增的数据设置能力 + P9
> 写范围：本目录（`docs/验证/**`）与 `tests/`；**全程未改 `src/frcli/`**
> 服务器写操作**只**发生在 `demo_group/demo_user/skill测试/`；本地语料（1602 个 .cpt）**只读**

---

## 0. 一句话裁决

> **P9 = 我们写错了 .cpt**：数据设置漏写 `<RG>`，服务端缺省按「分组」处理（相同值合并、数值列去重），
> 合计随去重后的行集走 → 静默算错（实测 70，SQL 真值 110），**与导出格式无关**
> （96 组可比的 xlsx/csv 配对逐格全等，0 处不一致）。
> 旧证据里那条「xlsx 合计 = 某一行值 / 时对时错」**另外还叠了一层读法错误**：
> 合计行*写在*模板第 4 行，渲染后落在第 6 行，当时按模板坐标读了第 4 行（那是第 2 条明细）。

**责任划分**：我们 100% / 平台 0%。平台侧唯一可议的是"缺省值不显式"这一设计（缺 `<RG>` 悄悄当分组），
但那是记录在案的契约行为，不是缺陷。

---

## 1. 方法与边界

### 1.1 对照件的造法：手写 XML，不依赖命令默认值

```bash
R="demo_group/demo_user/skill测试/dsv_base3.cpt"
frcli report new "$R" --apply                                   # 骨架
frcli report dataset "$R" --add ds4 --conn demo_conn \
  --sql "select 'A' k,10 amt union all select 'A',10 union all select 'A',20
         union all select 'B',10 union all select 'B',30 union all select 'B',30" --apply
frcli report table "$R" --dataset ds4 --at A2 --columns k,amt --header \
  --labels "键,金额" --expand v --apply
frcli report cell "$R" --at A4 --set-value "合计" --apply
frcli report cell "$R" --at B4 --set-formula "=SUM(B3)" --apply
frcli report download "$R" -o base3.cpt                          # 取字节
# ↓ 之后只在本地按列替换数据格的 <O> 块（gen3.py），再 upload --force
```

数据集刻意选**分组键有重复、数值列也有重复**（`10,10,20 / 10,30,30`），
这样「分组去重」与「列表原样」的结果**必然不同**，无法蒙混过关。

### 1.2 唯一变量

`b3_none` 与 `b3_func` 两件模板的字节 diff **只有两行**：

```
53a54  > <RG class="com.fr.report.cell.cellattr.core.group.FunctionGrouper"/>
62a64  > <RG class="com.fr.report.cell.cellattr.core.group.FunctionGrouper"/>
```

其余（数据集、版面、样式、`<Expand dir="0"/>`、合计行公式）逐字节相同。

### 1.3 读法

每个变体 **导出 3 轮**，每轮同时导 **xlsx（openpyxl 逐格）** 与 **csv（逐行）**；
另有对抗件单独 3 轮。共 **36 个变体 × 3 轮**（详见 §7 证据文件）。

---

## 2. P9 根因裁决

### 2.1 服务端契约（我自己反编译复核，非采信他人结论）

`com.fr.report.cell.cellattr.core.group.DSColumn`（`fine-report-engine-10.0.jar`）：

```java
public RecordGrouper getGrouper() {           // javap -c 实测
    if (this.grouper == null)
        this.grouper = new FunctionGrouper();  // ← <RG> 缺失 → 默认 FunctionGrouper
    return this.grouper;
}
```

`FunctionGrouper.<init>` 里 `divideMode = 0`，而常量 `GROUPING_MODE=0 / LIST_MODE=1 / CONTINUUM_MODE=2`
（`RecordGrouper.XML_TAG = "RG"`，`NONE_MODE = -1`）。**⇒ 不写 `<RG>` = 分组，不是列表。**

jar 里**不存在** `ListGrouper` 这个类；「列表」是 `FunctionGrouper` 的 `LIST_MODE`（`<Attr divideMode="1"/>`）。
语料交叉验证：1602 个模板、5696 个 `DSColumn` 格中，`FunctionGrouper` 4660 处、`SummaryGrouper` 266 处、
**`ListGrouper` 0 处** —— 与反编译一致。

### 2.2 服务端对照实验（同数据集 / 同版面 / 只改 `<RG>`）

数据集：`('A',10)('A',10)('A',20)('B',10)('B',30)('B',30)`，**SQL 真值 = 110**。

| 变体 | 数据设置 | 渲染结果（xlsx 逐格） | 合计 |
|---|---|---|---|
| `b3_none` | **无 `<RG>`** | `A/10`, `''/20`, `B/10`, `''/30`（**4 行**） | **70** ❌ |
| `b3_func` | `<RG …FunctionGrouper/>` | **与上一行逐格相同** | **70** ❌ |
| `b3_list` | `<RG …FunctionGrouper><Attr divideMode="1"/></RG>` | `A/10 A/10 A/20 B/10 B/30 B/30`（6 行） | **110** ✅ |
| `b3_sum` | k=分组，amt=`SummaryGrouper`+`SumFunction` | `A/40`, `B/70` | 110 ✅ |
| `b3_sum_count` | k=`CountFunction`，amt=`SumFunction` | `6`, `110` | 110 ✅ |

- **P0 ≡ P1 独立复现**：字节不同、输出逐格相同 ⇒ 「无 `<RG>` = 分组」成立（3/3 轮稳定）。
- **真正的问题形态是"静默算错"**：缺 `<RG>` 时合计 70，而真值 110 —— 因为分组把 `A` 的 `10,10`
  与 `B` 的 `30,30` 塌缩了。**3/3 轮 100% 复现**，且错值看起来完全合理（就是去重后可见行的和）。
- **分组 = 相同值合并展开**：4 行（`A` 只出现一次、第 2 行键为空），证实用户的语义描述。
- **汇总 = 按分组键把数值加起来**：`A/40 = 10+10+20`、`B/70 = 10+30+30` ✅ 名副其实。

### 2.3 旧证据「xlsx 合计 = 某一行值」的真相：读法错误

旧记录的版面（`cpt创作验证报告.md` §10.1 / §10.7）：表头第 2 行、数据第 3 行、**合计行写在 A4/C4**。
数据纵向扩展 3 行 ⇒ 渲染后数据占 3~5 行，**合计被顶到第 6 行**。

对同一份字节做两种读法（`o_none.cpt`，100/200/300，合计 `=SUM(C3)`）：

| 时间点 | `ws['C4']`（模板坐标） | 合计行（按内容找） | csv 合计行 |
|---|---|---|---|
| T0 刚上传 ×3 | **200.0** | 600.0 | 600 |
| T1 做过 3 次 `report cell` 编辑后 ×3 | **200.0** | 600.0 | 600 |

- `ws['C4']` **恒等于第 2 条明细**（200）——旧记录里的 `C4=200.0`、`C4=2345.6`（v_r2 的中间行）正是它；
- 合计行**恒等于真值**（600）；
- **两种读法各自都是稳定的**，编辑前后无变化 ⇒ 旧记录里 `4567.7 → 2345.6 → 4567.7` 的"时对时错"
  只能是**两种读法混用**（按坐标读一次、按内容读一次），不是平台按小时改数。
- 这也解释了为什么"只验一次等于没验"——验的人自己换了尺子。

### 2.4 「与导出格式无关」的量化证据

把全部对照件的 xlsx 与 csv 归一化后逐格比对：

```
可比的 xlsx/csv 配对: 96，逐格全等: 96，不等: 0，导出失败跳过: 12
```

**96/96 全等，0 处不一致。** 连同 §2.2、§4 的所有变体 ⇒
「xlsx 聚合引擎单独出错」这个归因**被证伪**，应予撤回（AGENTS.md 已改）。

### 2.5 最小复现步骤（P9）

```bash
# 1) 造一个「绑定数据集列但不写 <RG>」的单元格（老 report table 的产物就是这样）
#    其余一切正常：数据集有重复值、合计行用 =SUM(B3)
# 2) 导出并逐格读回
frcli export excel "$R" -o /tmp/x.xlsx ; frcli export csv "$R" -o /tmp/x.csv
python3 -c "import openpyxl;ws=openpyxl.load_workbook('/tmp/x.xlsx').active
print([[c.value for c in r] for r in ws.iter_rows()])"
# 期望 6 行明细 + 合计 110；实测 4 行明细 + 合计 70 ← 静默算错
# 3) 修：给该格补 <RG>（列表就写 <Attr divideMode="1"/>），或直接 report table --mode list
```

---

## 3. 三形态是否名副其实 → **是**（服务端逐格判定）

| 形态 | XML | 语义验证 | 判据 |
|---|---|---|---|
| 列表 | `<RG …FunctionGrouper><Attr divideMode="1"/></RG>` | **所有记录展开、不去重不聚合** ✅ | 6 行（含重复的 `A/10`、`B/30`） |
| 分组 | `<RG …FunctionGrouper/>` | **相同值合并展开** ✅ | 4 行（`A` 组内 `10` 合并、`B` 组内 `30` 合并） |
| 汇总 | `<RG …SummaryGrouper><FN>…SumFunction</FN></RG>` | **按分组键把数值加起来** ✅ | `A/40 = 10+10+20`、`B/70 = 10+30+30` |

补充实测：
- **`MonoGrouper` = 列表语义**（`a_mono`：3 行不合并）→ CLI 把它读成 `list` 是对的。
- **`divideMode=2`（连续分组）= 只合并「相邻」相同值**（`b4_*`，数据集 `10,20,10`，
  即重复值**不相邻**）：分组 2 行、合计 **30**；连续分组 3 行、合计 **40**（= 真值）。
  与 `references/cpt-features.md` §1.1 的声称一致，CLI 报 `continuum` 正确。
  这也是"静默算错"的第二个独立样本。
- **汇总函数换名有效**：`CountFunction` → `6`；`AverageFunction` → 文本列得 0、数值列得均值。

---

## 4. 命令路径验证（dsauthor 落地后）

### 4.1 端到端（`report new/dataset/table/cell` → 导出逐格）

| 命令 | 输出 | 合计 |
|---|---|---|
| `report table --at A2 --columns k,amt`（**默认 = list**） | 6 行全展开 | **110** ✅ |
| `report table … --mode group` | 4 行（`A/10,''/20,B/10,''/30`） | 70 |
| `report table … --mode summary --group-by k --fn sum` | `A/40`, `B/70` | 110 ✅ |

⇒ 命令默认值（list）产出的就是**用户要的"所有记录展开"**，且合计与 SQL 真值一致。
`--mode summary` 的聚合口径与数据源一致（40/70 逐项可验算）。

### 4.2 本地语义校验（写错就地报错，全部实测）

| 输入 | 结果 |
|---|---|
| `report cell --set-ds-mode list --fn sum` | ⛔ `--fn 只在 --mode summary 时有意义（当前 --mode list）；分组/列表本身就是「不聚合」的语义` |
| `report table --mode group --fn sum` | ⛔ 同上（group 版） |
| `report table --mode list --group-by k` | ⛔ `--group-by 只在 --mode summary 时有意义（当前 --mode list）：group/list 模式下每一列都是同一形态` |
| `--mode summary --group-by k,amt`（覆盖全部列） | ⛔ `--group-by 覆盖了全部列，没有列会被汇总；少给一个分组列，或去掉 --mode summary` |
| `--group-by nope` | ⛔ `--group-by 的列 nope 不在 --columns 里（--columns: k, amt）` |
| `--fn bogus` | ⛔ click 层拒绝：`'bogus' is not one of 'sum','count','avg','max','min','none'` |
| `--at C1 --bind nope.k` | ⛔ `单元格绑定的数据集 'nope' 不在模板里；现有: ds5（先用 report dataset --add 建）` |
| `--set-value x --set-ds-mode list` | ⛔ `--set-ds-mode/--fn 只对绑定数据集列的单元格有意义`（离线回归） |

### 4.3 读：`report cell --list` 如实报出形态

| 模板里的写法 | CLI 报告 |
|---|---|
| 无 `<RG>`（残缺） | `mode=group`，`ds_mode_explicit=false` ✅（不谎报成 list） |
| `FunctionGrouper` | `group` |
| `divideMode="1"` | `list` |
| `SummaryGrouper`+`SumFunction` | `summary` / `SumFunction` |
| **旧包名** `com.fr.report.cellElement.core.FunctionGrouper` | `group` ✅ |
| **旧包名** `…cellElement.core.SummaryGrouper` | `summary` ✅ |
| 旧标签 `<GC>` | `group` ✅ |
| 不存在的 `…group.ListGrouper` | `unknown` ✅（不谎报） |

### 4.4 legacy 包名的服务端行为（附：读要认老包名是对的）

`<RG class="com.fr.report.cellElement.core.FunctionGrouper"/>`（V10 jar 里**没有这个类**）
服务端**照常按分组渲染**：3 行、`A` 合并、合计 600 —— 与显式新包名形态逐格一致。
⇒ 「读的时候要同时认老包名」不是猜测，是**服务端真实行为**；只认新包名会把老模板的设置有读成"没有"。

---

## 5. 对抗矩阵：静默出坏模板

手写 XML → `report upload`（即文档 §4 XML 速查 / §3 download-edit-upload 引导的路径；
`report upload` 现在只有良构性校验，语义零校验 = 旧问题 P10）。

| # | 用例 | 结果 | 级 |
|---|---|---|---|
| A1 | **错的 `<FN>` 类名**（`<FN>…NotAFunction</FN>`） | **静默出坏数据**：不报错、不抛异常，只渲染最后一行 `B/丙/300`、合计 **300**（真值 600），3/3 稳定 | 🔴 |
| A2 | **不存在的 `<RG>` 类名**（`…group.ListGrouper`） | 导出报错（`export excel` 魔数门拦住，坏产物改名 `.bad`）；服务端 `TemplateFileNotFoundException`。**但 `export csv` 会把 HTML 出错页写成 .csv**（csv 无魔数可校验） | 🟠 |
| A3 | `SummaryGrouper`+`SumFunction` 用在**文本列**上 | **静默出 0**（`0, 0, 600`），不报错 | 🟠 |
| A4 | `<RG>` 与 `<Condition class="…ListCondition"/>` **并存** | 结果 = 分组（`Condition` 不改变 grouper 语义）；只写 `Condition` 不写 `<RG>` 也是分组 | 🟡 |
| A5 | `divideMode="2"`（连续分组） | 正常渲染；CLI 读成 `continuum`，不与 group 混淆 | ✅ |
| A6 | `<Expand extendable="1|2|3"/>` | **服务端抛 `NumberFormatException: For input string: "1|2|3"` → 出错页**（带不带 `dir` 都一样）。`extendable` 要的是**整数**位掩码 | 🔴 |
| A7 | `<Expand dir="0" extendable="3"/>` | 正常渲染，方向不变（纵向） | ✅ |
| A8 | `<Expand extendable="3"/>`（**无 `dir`**） | **不产生扩展**：整列被拼成一格（`A,B` / `10,20,30`）；方向只由 `dir` 决定 | 🟠 |
| A9 | `<Expand/>`（不扩展，列表形态） | 整列被**逗号拼成一格**：`A,A,A,B,B,B` / `10,10,20,10,30,30`（合计 110 仍对） | 🟠 |
| A10 | `<Expand/>`（不扩展，分组形态） | 先去重再拼接：`A,B` / `10,20,30`（合计 60） | 🟠 |

> A9/A10 是"多个值被逗号拼成一格"坑的**双形态**证据：拼接前的去重与否，取决于数据设置。
> A6 是对既有认知的**修正**：`extendable="1|2|3"` 不是"写了不生效"，而是**直接 500**。

---

## 6. 过程性发现（会污染结论的环境坑）

| # | 现象 | 后果 | 级 |
|---|---|---|---|
| E1 | **长批量导出中途认证失效** → `导出失败: HTTP 302`，`export` 不自动重登重试 | 5 个变体整批"无输出"，看起来像**模板坏了**（我第一轮矩阵的假阴性就是这么来的）；紧接着的下一条命令会静默 `relogin`，更迷惑 | 🟠 **已修，见 §11.2** |
| E2 | `export csv` 无魔数门 | 服务端出错时把 HTML 出错页**当 csv 落盘**；xlsx 有 `PK` 门所以拦得住 | 🟠 **已修，见 §11.1** |
| E3 | 实测统计口径 | 全部导出共 **108** 次，其中 **12** 次因 E1/E2 失败被跳过（其余 96 组 xlsx/csv 全等） | — |

---

## 7. 证据文件

| 文件 | 内容 |
|---|---|
| `docs/验证/证据/ds验证/matrix_core.json` | 语义/P9 对照：10 变体 × 3 轮 × (xlsx+csv) |
| `docs/验证/证据/ds验证/matrix_b3.json` | 重复值数据集 8 变体 × 3 轮（P0–P3 + Expand 坑） |
| `docs/验证/证据/ds验证/matrix_b3b.json` | `extendable` 整数/非法值对照 |
| `docs/验证/证据/ds验证/matrix_adversarial.json` | 对抗矩阵 8 变体 × 3 轮 |
| `docs/验证/证据/ds验证/cmdpath.json` | 命令路径端到端（list/group/summary）逐格输出 |
| `docs/验证/证据/ds验证/matrix_continuum.json` | 分组 vs 连续分组（`10,20,10`） |
| `docs/验证/证据/ds验证/p9read.json` | 两种读法 × 编辑前后各 3 次 |
| `docs/验证/证据/ds验证/*.py` | 全部复现脚本（造件 / 跑矩阵 / P9 读法 / 命令路径） |

---

## 8. 问题清单（本轮）

| # | 级 | 问题 | 证据 | 建议 |
|---|---|---|---|---|
| V1 | ✅ 已闭环 | P9 根因 = 缺 `<RG>` 被当分组；与导出格式无关 | §2.1–2.4 | AGENTS.md 已改（本轮复核：措辞已按实测修正） |
| V2 | ✅ 已闭环 | 旧「xlsx 合计=某行值 / 时对时错」= 读法错误 | §2.3 | 已在 AGENTS.md「早期误判（已撤回）」写明 |
| V3 | ⚪ 已知局限 | **错 `<FN>` 类名静默出坏数据**（A1） | §5 | **命令路径已有硬校验**（`--fn` 只收 6 个已知函数，写错就地报错）；**手写 XML → `report upload` 仍只做良构校验 + warning 不硬拦** —— 按 P10 既定口径记为**已知局限**，不列为待修（要补的话见建议：`<RG class>` 与 `<FN>` 都是纯字节可判） |
| V4 | 🔴 待修 | **`extendable` 必须写整数**，`1\|2\|3` 直接 500（A6） | §5 | 文档明确「`extendable` = 整数位掩码，不写 `dir` 不产生扩展」；CLI 若将来暴露该属性要校验 |
| V5 | ✅ 已修已复验 | `export csv` 无魔数门，HTML 出错页照写（E2/A2） | §11.1 | Lead 在 `client.py` 加 csv/text 守门 → 实测两个出错页模板均被拒（坏产物改名 `.bad`），正常 csv 照常写出 |
| V6 | ✅ 已修已复验 | 批量导出撞 302 不重试，表现像"模板坏了"（E1） | §11.2 | `export_report` 改走 `_request`（含自动重登） → 实测带对照通过 |
| V7 | 🟠 待修 | `SummaryGrouper` 用在文本列静默出 0（A3） | §5 | 服务端行为，只能靠文档提醒/`report cell --list` 复核 |
| V8 | 🟡 记录 | `<Expand/>` 逗号拼接（A8–A10）：一格塞进整列值 | §5 | 文档补"不扩展 = 拼接"，并说明列表/分组拼接结果不同 |

---

## 9. 离线回归

新增 `tests/test_ds_mode.py`（**34 条，全绿**）：守 P9 根因与三形态契约。

- 缺 `<RG>` ⇒ `cells()` 报 `group` 且 `ds_mode_explicit=false`（不谎报成 list）；
- `o_xml(binding=…)` **永不省略 `<RG>`**；三形态 XML 片段逐字节断言 + 读写往返；
- 旧包名 / 旧标签 `<GC>` / `MonoGrouper` / `IndexGrouper` / `divideMode=2` 全部认得出；
- 未知 Grouper → `unknown`（不静默当成已知形态）；
- `plan_table` 默认 `--mode list`；`--fn` 只配 summary；`--group-by` 仅 summary 有意义且不能覆盖全部列；
- `expand_xml` 三方向契约。

全套：`PYTHONPATH=src pytest tests/ -q` → **376 passed, 2 failed**，2 个失败是 AGENTS.md 记录在案的
`test_config.py` 历史遗留（实测环境有真实 `~/.frcli/config.yaml`），与本轮无关。

---

## 10. 安全边界与清理

- 服务器写操作**全部**在 `demo_group/demo_user/skill测试/`；`report upload` 的目标名一律带 `dsv_`/`dsv/` 前缀便于回收。
- 本地语料 **只读**（只用 `grep`/`open(...,'r')`）；未改 `src/frcli/`；未创建/修改/运行任何定时任务。
- **本轮产物已全部删除**：39 个 `dsv_*` 文件 + `dsv/` 子目录（`report delete`，进回收站可恢复）。
  删除后目录只留 `_目录说明.txt`、团队样例（`golden.cpt`/`t4_report.cpt`/`t4_table.cpt`）
  与 `dsauthor` 的 `dsmode/`（**非本轮产物，未触碰**）。

---

## 11. 第二轮复验：Lead 修的两条缺口（独立实测）

> 两条都在 `src/frcli/client.py`，我**没改代码**，只做验证。两条都配了**对照**，
> 因为"看起来好了"最可能的解释是"我的测试没真的触发那个错误"。

### 11.1 `export csv` 出错页守门 —— ✅ 复验通过

判据：csv/text 没有魔数可比，退化为"像不像 HTML 页"（`<!doctype` / `<html` / `Dec-Waiting_In_Line`）。

| 用例 | 期望 | 实测 |
|---|---|---|
| `export csv` 打**已知出错页模板**（`<RG>` 类名不存在） | 拒绝，且**不**留下 .csv | ⛔ `导出产物是平台出错页，不是报表: …/guard.csv；坏产物已改名保留在 …/guard.csv.bad`；目录里只有 `.bad`（3682 B，开头 `<doctype html>`） |
| 同上换另一张出错页模板（`extendable` 非法值） | 同上 | ⛔ 同上（3564 B `.bad`） |
| **阳性对照**：正常模板的 `export csv` | 必须照常写出 | ✅ `status: ok`，内容 `,,` / `键,名称,金额` / `A,甲,100` |

阳性对照是必需的：否则"拒绝一切 csv"也能让前两行变绿。

### 11.2 `export_report` 撞 302 自动重登 —— ✅ 复验通过（带对照）

模拟"缓存未过期但服务端已失效"：内存 token 换 `bogus.invalid.token`、`expires_at` 放到未来，
**不动共享的 `~/.frcli/tokens/yh.json`**（避免影响并行工作的队友）。

| 步骤 | 实测 |
|---|---|
| **对照**：绕过 `_request` 直接 `GET`（同样垃圾 token） | **HTTP 302**（CAS 登录页）⇒ 证实该状态**确实是**认证失败，测试有效 |
| 正式：同一状态下 `export_report(...)` | ✅ 导出成功，**用时 0.7 s**（内部 302 → invalidate → 重新登录 → 重试） |
| 重登后 token | 已换新（不再等于 `bogus.invalid.token`） |

⇒ 前一版「长批量导出跑到一半 5 个变体假阴性」的那类误判不会再出现；
`export` 的错误文案也不再只给一个 `HTTP 302`（认证失效有独立分支与提示）。
