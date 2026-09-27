# cpt 配方集 · 第二辑（`references/cpt-patterns2.md`）独立复现报告

> ⚠️ 本文提到的证据图片/产物已从仓库移除（服务端渲染带个人水印与真实数据）；重建方法见 `docs/验证/证据/README.md`。


> **复现者**：`patternverifier`（独立验证者）。**未读 `src/frcli/` 源码、未询问作者**；
> 只照 `references/cpt-patterns2.md` + `SKILL.md` 的命令语法重建，服务端产物逐格 / 逐像素读回。
> **产物**：全部新建在 `demo_group/demo_user/skill测试/repro3/`（写范围内），未触碰 `patterns/`（含 `verify/`）；
> 收尾已清空 `repro3/`，重建命令都在本报告各节。
>
> **基准**：`src` 指纹 `c645b1d8a5c22f928e98ea5a23635e4041e57e66203261b8acb782e0333cfeb0`
> （`cat src/frcli/*.py src/frcli/commands/*.py | shasum -a 256`），`__version__ 0.9.0`，
> `pytest tests/` = **429 passed / 2 历史失败 / 1 skipped**（+ 本轮新增 6 条 → 435 passed）。
> ⚠️ Lead 给的 `d499f45e…` 是 21:34 的快照，之后 `cptlab` 又改了 3 个文件；**以本报告指纹为准**（Lead 已确认）。
>
> **工具**：`pypdfium2`（PDF 光栅化）+ `PIL`（裁剪/拼图）——分页类特性一律出图看；
> 图表一律 `report image`(PNG) 或 `export pdf` 出图看，**不用 xlsx 逐格**（理由见 §1.2）。
> **纪律**：改 XML 做对照一律 `re.subn` 断言 `n == 1` + 服务端回读确认；拿不到预期结果先跑
> `frcli report datasets <模板>` 区分 SQL/数据集问题与渲染问题（本轮装置自检见 §7）。

---

## 0. 复现结果总表

| 配方 | 复现结果 | 关键产物 | 严重级 |
|---|---|---|---|
| **W1 图表**（柱/折/饼/环形） | ✅ **可复制**（出图逐值一致）；doc 的静默错对照全部复现 | 柱形图、饼图、折线图、错列名对照图 | 🟡 两处结论过宽（见 P3/P4） |
| W1 的「xlsx 是嵌入图片」判据 | ✅ **独立证实**（`xl/media/image1.png` + 非空格 0） | `W1-图表在xlsx里是嵌入图片.xlsx` | — |
| **W2 参数控件** | ⚠️ 正面路径可复制；**doc 的静默错对照按配方抄得到相反结果** | 见 §2 | 🟠 P1 / 🔴 P2 |
| **W3 钻取超链接** | ✅ **可复制**（含"整页炸"的写错形态）；**并闭合了 doc 的 1 条"未确证"** | 3430B 出错页、withcond 导出 | 🟡 P6 |
| **W4 层次坐标** | ✅ **可复制**（8 种写法逐值一致） | `W4-层次坐标8写法.xlsx` | 🟡 P7（数字张冠李戴） |
| W4.1 HA 函数 + **`SORT` 升降序** | ✅ **裁决：`SORT(C3)` 降序**（4/3/2/1）；`SORT(C3,false)` 升序 | `W4.1-HA函数-SORT降序.xlsx` | 🟡 P8（"官方帮助"不可核实） |
| **W5 分页/重复标题行/页脚/冻结** | ✅ **可复制**（3 页 → 7 页；**出图证实第 2 页顶部真有表头**） | PDF + 出图 + 页脚截图 | 🟡 P9（HR 行号配套关系没写） |
| W5 的两条静默错对照 | ✅ 复现（`footerHeight=0`、`<Footer>` 放错父节点 ⇒ 均不渲染） | 字节级证据：49784B = 49784B | — |
| `doc_rerun.sh` | ❌ **不存在**（repo/服务器/家目录都没有，Lead 已确认作者留在自己临时目录）⇒ 按"自己照 §W1–§W5 抄一遍"复核 | — | 🟠 P10 |

---

## 1. W1 图表

### 1.1 照配方复现（可复制 ✅）

```bash
frcli report new "$R" --apply
frcli report dataset "$R" --add ds1 --conn demo_conn --sql "select '东区' cat,'A' series,100 val …" --apply
frcli report chart "$R" --at A1 --dataset ds1 --type column \
  --category cat --series series --value val --fn sum --title "各区域 A/B 销量" --show-title --apply
```
- `report chart --list` 回读：`OneValueCDDefinition{series=series, value=val, function=SumFunction, dataset=ds1, category=cat}` ✅ 与 doc 的 XML 契约一致。
- 生成的图表单元格：`<C c="0" r="0" cs="9" rs="20">` + `<O t="CC">` ✅（柱形 9×20 与 doc 一致）。
- **出图逐值核对**（`report image`，1586×2244；人工看图 + 裁剪）：
  标题「各区域 A/B 销量」、Y 轴 0–500、**东区 100(蓝)/200(绿)、西区 300(蓝)/400(绿)**、图例 **A/B** —— 与 doc 表逐值一致 ✅
  （证据：`docs/验证/证据/第二辑复现/W1-柱形图-出图.png`）
- 其它图型（同一次会话内出图）：折线 = 两条线 100→300 / 200→400 ✅；
  **饼（不给 `--series`）= 一张饼，图例 东区/西区（≈30%/70%，即 300/700）** ✅；
  **饼（给 `--series`）= 两张饼（东区、西区），扇区按 series** ✅（证据：`W1-折线饼图对照montage.png`）。
  ⚠️ `--type ring` 本轮未单独出图（未复现，不阻塞）。

### 1.2 「xlsx 里是嵌入图片、逐格永远是 0 非空格」——**独立证实 ✅**

```
zip 内条目: xl/drawings/drawing1.xml, xl/drawings/_rels/drawing1.xml.rels, xl/media/image1.png(25877B)
openpyxl: dims A1:I20 | 非空格数 = 0 | ws._images = 1
```
⇒ doc §0.1 的"通道表"成立，这是本辑最有价值的验收陷阱（只读 xlsx 会误判"图表没生成"）。

### 1.3 静默错对照（全部复现 ✅）

| 写法 | 我的实测 | doc | 结论 |
|---|---|---|---|
| `--category NOSUCH` | `status: ok` 且出图；**X 轴无分类标签**、A/B 各一根柱 **400(蓝)/600(绿)**、Y 轴变 0–700 | 一字不差 | ✅ 最危险的静默错成立（证据 `W1-写错列名category-NOSUCH-静默错图.png`） |
| `--dataset nosuchds` | 本地报错 `模板里没有数据集 'nosuchds'；现有: ds1` | 本地直接报错 | ✅ |
| `--at` 落在已有内容格 | 本地直接报错 | 本地直接报错 | ✅ |
| 值列 = **非数字文本**（'abc'/'xyz'） | 图能出、**柱子全 0**、Y 轴 0–100 | 值全 0/空 | ✅ |
| 值列 = **数字样字符串**（'100'/'200'） | **聚合照常正确**（100/200/300/400） | doc 未区分 | 🟡 P3：doc 那句要加限定（只有非数字文本才塌成 0） |
| 不写 `--title` | CLI 写空文本 + `<TitleVisible value="false"/>`（图上无标题） | 同 | ✅ |
| **删掉 `<Title4VanChart>` 整块** | 图上真出现 **「新建图表标题」** | 同 | ✅（证据 `W1-删掉Title块-默认标题.png`） |

---

## 2. W2 参数控件（本辑最严重的一节）

### 2.1 正面路径（可复制 ✅，但配方不完整）

doc §W2 只给了两条 `report widget` 命令，**没有**数据集 / 取数表 / 参数声明这三步。照它逐条抄（新模板）得到的是一张
**"有面板、无数据"的空报表**：`report widget --list` count=2（ComboBox + DateEditor ✓）、`report param --list` 显示
`area` 参数被自动补声明 ✓，但导出 `dims A1:B3` 全空、`status: ok` ⇒ **🟠 P4 文档缺口**。

我自己补上三步（`where area = '${area}'` + 表 + 控件）后与 doc 的实测值一致：

```
默认导出          → A1='区域 = 华东'，数据行 ['华东', 100]
--params {"area":"华南"} → A1='区域 = 华南'，数据行 ['华南', 200]
report widget --list → count=2：area=ComboBox(options 华东/华南/华北, default 华东)、d1=DateEditor(2026-09-01)
```

### 2.2 🔴 doc 的静默错对照：按配方抄得到**相反结果**

doc 原文：
```
report widget --param AREA --type combo --default 华南   # 模板参数叫 area
→ status: ok，widget --list 显示 AREA=华南
→ 导出仍是 华东（模板参数默认值）：控件完全不联动，**不报错**
```
我照抄（模板里只有 `area=华东`）：

| 命令 | `report param --list` | 导出 |
|---|---|---|
| `--param AREA --default 华南` | **两个参数：`area=华东` + `AREA=华南`** | **`华南/200`** ← 与 doc 说的 `华东` 相反 |
| `--param AREA --no-declare`（不给 `--default`） | 只有 `area=华东` | `华东/100` |

- **根因**：`--default` 会给模板参数**补声明**（CLI 自己的帮助也写了"同时给模板参数补默认值"，且有 `--no-declare` 可关），
  于是凭空多出一个 `AREA=华南`；而**服务端参数名大小写不敏感**，这个 `AREA` 直接影响了 SQL 里的 `${area}`。
- **doc 的样例 `patterns/w2_widget_errname.cpt` 我查了**：模板参数只有 `area=华东`、控件名 `AREA`
  —— 相当于 `--no-declare` 建的，所以它的导出确实是 `华东/100`。⇒ **配方与样例不一致**（按配方抄 ≠ 样例）。

### 2.3 🔴 更根本：「控件不联动」在导出通道里**证明不了**

| 模板 | 默认导出 |
|---|---|
| 控件名**正确**（`w2_widget.cpt` / 我的 w2_full） | `华东/100` |
| 控件名**不匹配**（`w2_widget_errname.cpt`） | `华东/100` |

⇒ "导出仍是华东"这条证据**对错两种命名都成立**（导出不经过参数面板，没有交互），因此证明不了联动与否；
而 doc §W2 自己又写了"面板控件渲染要在预览页看" —— 两处自相矛盾。**建议**：删掉这条 🔴 对照，或改写成
"**预览页可验、导出通道不可验**；接口层只能验『控件名 = 参数名』这条 XML 约束"。

### 2.4 新发现（建议写进文档）：**服务端参数名大小写不敏感**

| 场景（模板：`area=华东`，SQL `${area}`） | 实测 |
|---|---|
| 传 `--params '{"area":"华北"}'` | 华北 ✅ |
| 传 `--params '{"AREA":"华北"}'`（**大写**） | **华北 ✅ 生效** |
| 模板里同时存在 `area=华东` 与 `AREA=华南`，不传参 | 取 **华南** |
| 同时传 `{"area":"华北","AREA":"西北"}` | **无行返回**（后者胜，值落不到数据里） |

⇒ 文档应写：**参数名统一小写**；**不要用大小写不同的名字构造"不联动"对照**；同名不同大小写会互相干扰。

---

## 3. W3 钻取超链接

### 3.1 正确形态（可复制 ✅）

```bash
frcli report link "$R" --at A3 --to "…/patterns/r1_group_subtotal.cpt" --param center='=$A3' --param flag=1 --apply
frcli report link "$R" --at A2 --type web --to "https://www.fanruan.com" --frame _blank --apply
```
`report link --list` → count=2：`A2=WebHyperlink(_blank)`、`A3=ReportletHyperlink`（带参数）✅；
形态是 `<C>` 的直接子元素 `<NameJavaScriptGroup>`（不在 `HighlightList` 里）✅。

**导出态（doc 结论成立）**：xlsx `xl/worksheets/sheet1.xml` 里 `<hyperlink>` **0 处**、
openpyxl `A2.hyperlink = A3.hyperlink = None`；PDF `/URI` `/Annots` `/Link` **全 0** ⇒ 纯预览态交互 ✅。
> 🟡 **P6**：但 CLI 自己的 `report link --help` 写的是"导出产物里只保留链接属性（xlsx 的 hyperlink / pdf 的链接注释）"
> —— **与实测相反**，会让验收者按错误判据去 xlsx 里找链接。建议改 help 文案。

### 3.2 写错形态（复现 ✅，与 doc 精确一致）

按官方语料的真实形态（`com.fr.report.cell.cellattr.highlight.HyperlinkHighlightAction` + `<NameJavaScriptGroup>` 子节点）
注入到单元格的 `<HighlightList>` 里，**但不带 `<Condition>`**：

| 变体 | 结果 |
|---|---|
| **不带 `<Condition>`** | **excel 与 pdf 都整页炸**：`EXPORT_ERROR`，出错页 **3430B**、`<div id='detail-message'>` **内容为空** ✅ 与 doc 一字不差 |
| **带 `<Condition>`**（doc §8 标"未验"） | **导出正常**（excel 4337B / pdf 35170B、1 页）；且**导出里同样没有任何链接痕迹**（`<hyperlink>`=0、`/URI`=0） |

⇒ **闭合 doc §8「条件属性形态的超链接未验」**：该形态可导出、不炸，但同样是**预览态交互**，导出验收不到。

---

## 4. W4 层次坐标

数据：`东区 2024=100 / 2025=150 / 西区 2024=200 / 2025=100`（版面 A3=地区 group、B3=年份 list、C3=金额 list）。

### 4.1 八种写法逐值一致 ✅（xlsx 与 csv 双通道）

| 写法 | doc | 我的实测（行 3/4/5/6） |
|---|---|---|
| `=C3/C3[B3:-1]-1` | `#DIV/0!` / 0.5 / `#DIV/0!` / -0.5 | ✅ 同（csv 里 `#DIV/0!` 显示为 `∞`） |
| `=C3/C3[A3:-1]-1` | `#DIV/0!` / `#DIV/0!` / 1.0 / -0.333 | ✅ 同 |
| `=C3[A3:-1]` | 100 / 150（后两行） | ✅ `None/None/100/150` |
| `=C3[B3:1]` | 100/100/200/200 | ✅ 同 |
| `=SUM(C3[!0])` | 550 | ✅ 四行都 550 |
| `=C3/SUM(C3[!0])` | 18.2/27.3/36.4/18.2% | ✅ 0.1818/0.2727/0.3636/0.1818 |
| `=SUM(C3[B3:-1])` | 0/100/0/200 | ✅ 同 |

写错对照 ✅：`=C3[C3:-1]` 与 `=C3/B3[-1]` 都是**静默空**（`None`，不报错、无 `#NAME?`）。

### 4.2 W4.1 HA 函数 ✅ + `SORT` 升降序**裁决：降序**

数据 100/150/200/250（合计 700）：

| 函数 | doc | 我的实测（4 行） |
|---|---|---|
| `=SORT(C3)` | 4/3/2/1（**降序**） | ✅ **4/3/2/1** |
| `=SORT(C3,false)` | 1/2/3/4 | ✅ 1/2/3/4 |
| `=MOM(B3,C3)` | 0 / 1.5 / 0 / 1.25 | ✅ 同 |
| `=PROPORTION(C3)` | 14.3/21.4/28.6/35.7% | ✅ 同 |
| `=count(C3[!0;!0]A{C3 > $C3})+1` | 4/3/2/1 | ✅ 同 |
| `=C3[A3:-1,B3:+0]`（同比） | 西区两行拿到 100/150 | ✅ 同 |

⇒ **`SORT(C3)` 默认降序**，与 doc 的真机结论一致 ✅。
🟡 **P8**：doc 顺带写的"FR 英文与繁体帮助写升序"我**无法核实** —— 实测环境 FineReport 安装包的
`webapps/webroot/help` 只有 demo 页、没有函数帮助；`web_search` 本轮不可用（额度）。建议文档只保留
"实测降序 + 可复现命令"，不要把未复核的帮助文案当结论引用。

### 4.3 🟡 P7：写错对照里的**数字张冠李戴**

doc 的 🔴 表写：「用错维度：该用 `[A3:-1]` 却写 `[B3:-1]` → 数值看似正常（**1.0 / -0.333**）」。
实测：**`1.0 / -0.333` 是 `[A3:-1]`（正确写法）的值**；`[B3:-1]` 的值是 **0.5 / -0.5**（行级环比，组首行 `#DIV/0!`）。
⇒ 结论（"两者都像样、最危险"）成立，但**举例数字归错了式子**，建议对调/改成两组数字都列。

---

## 5. W5 分页 · 重复标题行 · 页眉页脚 · 冻结

### 5.1 重复标题行：3 页 → 7 页 ✅ + **出图证实第 2 页顶部真有表头**

自建 120 行明细 + 表头行加高到 600pt（XML 注入 `<RowHeight>` 第 2 元素 = 26565000 FU，
`re.subn` 断言 `n==1`、上传后**服务端回读确认 = 26565000**）：

| 版本 | PDF |
|---|---|
| 无 `<HR>` | **3 页 / 40639B** |
| `<HR F="1" T="1"/>`（`--repeat-header-rows 1:1`） | **7 页 / 49784B** |
| 作者样例 `patterns/w5_hdr.cpt`（同版面） | **7 页 / 57618B**（它另带 20pt 页脚） |

⇒ doc 的"信号很弱 → 放大表头后 3→7 页"完全复现 ✅。
**我补了 doc 没做的一步**：pdfium 出图看页面顶部 ——

- **有 HR**：第 1 页顶部 = 「编号 | 金额」，**第 2 页顶部 = 「编号 | 金额」（表头真的重复了）** ✅
- **无 HR**（对照）：第 2 页顶部**直接是数据 19…43**，没有表头 ✅

（证据：`W5-重复标题行-第2页顶部有表头.png`、`W5-有HR-7页.pdf`、`W5-无HR-3页.pdf`）

### 5.2 页脚 + 页码 ✅（出图）

`report page --footer-text '"第 " + $$page_number + " 页 / 共 " + $$totalPage_number + " 页"' --footer-formula --footer-height 20`
→ `page --list` 回读 `footer_height_pt=20.0` + 公式 ✅；导出 7 页 56325B；
pdfium 出图看最后一页底部：**「第 7 页 / 共 7 页」真的印在页脚居中** ✅。

### 5.3 两条静默错对照 ✅（**字节级**证据）

| 变体 | 页数/字节 | 结论 |
|---|---|---|
| 正常带页脚 | 7 页 / **56325B** | 页脚渲染 |
| `footerHeight="0"`（Footer 内容仍在） | 7 页 / **49784B** | **与"完全没有页脚"的基线字节完全相同** ⇒ 静默不渲染 ✅ |
| `<Footer>` 挪到 `<Report>` 下（不在 `<ReportAttrSet>` 内，注入后断言 `Footer 仍在 ReportAttrSet 内? False`） | 7 页 / **49784B** | 同样静默 ✅ |

### 5.4 `report image` 负对照 ✅

`report image` 产出 **1586 × 15708** 的单张长图（120 行全部铺开）⇒ **是版面流、不分页**，
用它验页脚/重复标题行必然假阴性 ✅ doc 结论成立。

### 5.5 冻结 ✅（像素级）

`report page --freeze 1,0 --page-freeze on` → `--list` 回读 `frozen=1,0` ✅；
导出前后 PDF **页数相同、7 页逐页渲染差异像素 = 0**（501832 像素/页，`bbox=None`）⇒
"导出态无可视差异"成立 ✅（文件字节不同只是元数据/时间戳）。

### 5.6 🟡 P9：`--repeat-header-rows` 的区间必须**对准表头所在的 0 基行号**

我自己第一版用 `--at A1 --header`（表头在 0 基第 0 行）却下 `--repeat-header-rows 1:1`（重复第 1 行），
得到 **导出失败：`11300002 行高列宽超出页面大小设置 出错对象: 行`**（不是静默，是明确报错；`extype=simple` 也绕不过）。
改成 doc/作者的版面（`--at A2 --header`，表头在 0 基第 1 行）+ `1:1` 后立刻复现 3→7 页。
⇒ doc 的 `--repeat-header-rows 1:1` 与"表头在 Excel 第 2 行"是**配套**的，建议在 §W5 补一句坐标依赖
（顺便说明了 `HR` 是 **0 基闭区间**）。

---

## 6. 问题清单（按严重级）

| # | 级别 | 问题 | 证据 | 建议改法 |
|---|---|---|---|---|
| P1 | 🟠 | **§W2 的 🔴 静默错对照按配方抄得到相反结果**（doc 说导出仍 `华东`，实测 `华南`）—— 根因是 `--default` 顺手补了 `AREA=华南` 声明；**配方与样例不一致** | §2.2 表 | 改配方：要么加 `--no-declare`（并说明样例就是这么建的），要么删掉这条对照 |
| P2 | 🔴 | **§W2 那条对照的证据支撑不了结论**：控件名对不对，默认导出都是 `华东/100`（导出不走参数面板），"导出仍是华东"证明不了联动 | §2.3 表 | 改成"预览页可验、导出通道不可验"，并把判据换成 XML 约束（`WidgetName == 参数名`） |
| P3 | 🟡 | §W1"值列写成文本列 ⇒ 值全 0/空"**过宽**：数字样字符串照样正常聚合 | §1.3 | 改成"**非数字**文本才塌成 0" |
| P4 | 🟠 | **§W2 配方缺数据集 / 取数表 / 参数三步**，照抄得到"有面板、无数据"的空报表（`status: ok`） | §2.1 | 补三段命令（doc 的实测值本来就是含数据的） |
| P5 | ℹ️ | **新发现：服务端参数名大小写不敏感**（`--params {"AREA":…}` 能覆盖 `area`；两条大小写不同的声明并存时后者胜；两个都传 → 无行） | §2.4 | 写进 §W2：参数名统一小写；别用大小写做对照 |
| P6 | 🟡 | `report link --help` 说"导出产物里只保留链接属性（xlsx hyperlink / pdf 链接注释）"，**与实测相反**（导出 0 痕迹） | §3.1 | 改 help 文案（会误导验收判据） |
| P7 | 🟡 | §W4 写错对照的数字**张冠李戴**：`1.0/-0.333` 是 `[A3:-1]` 的值，`[B3:-1]` 是 `0.5/-0.5` | §4.3 | 对调或两组都列 |
| P8 | 🟡 | §W4.1 引用"FR 英文/繁体帮助写升序"——**无法核实**（安装包无函数帮助；web_search 不可用） | §4.2 | 只留实测结论 + 复现命令，不引用未复核的帮助文案 |
| P9 | 🟡 | §W5 的 `--repeat-header-rows 1:1` 未写明"必须与表头所在 0 基行号配套"；写错会 `11300002`（明确报错） | §5.6 | 补一句坐标依赖 + 说明 `HR` 是 0 基闭区间 |
| P10 | 🟠 | **`doc_rerun.sh` 不存在**（repo/服务器/家目录均无）⇒ doc 声称的"照文档逐条重跑"不可复核 | §0 总表 | 落到 repo（`tests/` 或 `tools/`）后再引用 |
| P11 | 🟡 | §W1 说图表可裁到"1.6~1.9KB"，实测 CLI 内置的图表单元格 **2.2~2.5KB**（柱 2572B / 饼 2541B / 折线 2230B） | §1.1 | 改成实测区间 |
| P12 | 🟡 | §6 命令速查里 `--type` 只写 `column\|line\|pie\|ring`，实际支持 `bar/column/donut/line/pie/ring` + 中文别名 | §1.3 | 补全（本地报错里就列着） |
| P13 | 🟡 | **错误 JSON 走 stderr、成功 JSON 走 stdout** ⇒ `cmd \| jq` 会把错误整个吞掉（我本轮就因此先得到"空输出"） | §7 | 写进 SKILL.md（退出码 1 + 错误在 stderr） |

---

## 7. 装置自检记录（我自己踩的两次）

| # | 现象 | 自检动作 | 真因 |
|---|---|---|---|
| 1 | W5 重复标题行"复现不出 7 页"，反而报错 | 下载**作者样例**看它的 `<RowHeight>`/`<Cell>` 坐标 | **我的版面不对**：`--at A1 --header`（表头在第 1 行）配 `HR=1:1`（重复第 2 行）⇒ `11300002`；改成 `--at A2 --header` 立刻复现 3→7 页 |
| 2 | W3 写错形态"应该整页炸却导出成功" | 去官方语料找 `HyperlinkHighlightAction` 的**真实形态** | 我最初写的是 `com.fr.js.HyperlinkHighlightAction`（**类名不对**）+ 错子节点 ⇒ 被服务端静默忽略；换成正确的全限定类名 + `<NameJavaScriptGroup>` 后**精确复现 3430B 出错页** |
| 3 | 多个命令"没有任何输出" | 分开看 stdout/stderr | 我自己用 `2>/dev/null` 把**错误 JSON（走 stderr）**吞了 ⇒ P13 |

---

## 8. 证据与可复现命令

- 证据目录：`docs/验证/证据/第二辑复现/`（12 个文件：图表出图/对照图、嵌入图片 xlsx、W4 两张 xlsx、
  W5 两份 PDF + 两张出图、W3 3430B 出错页 HTML、默认标题出图）
- 本轮新增离线回归：`tests/test_patterns2_repro.py`（6 条，全绿）——钉住
  ① `--default` 会补参数声明（W2 根因）② `--no-declare` 不动参数 ③ 图表列名本地不校验（静默错前提）
  ④ 本地只拦"数据集不存在/格子被占" ⑤ `--repeat-header-rows` 必须对准表头的 0 基行号。
  全量 `pytest tests/` = **435 passed / 2 历史失败 / 1 skipped**。
- 服务器收尾：`repro3/`（本轮全部复现模板）已整目录删除；`patterns/`（含 `verify/`）**一字未动**。
- `src/frcli/` **未做任何改动**。

### 复现用到的关键命令（照抄即可重建）

```bash
export PATH="/opt/homebrew/bin:$HOME/.local/bin:$PATH"
export FRCLI_WRITE_SCOPE="demo_group/demo_user/skill测试"; export FRCLI_TIMEOUT=300
F() { PYTHONPATH=src <venv>/bin/python -m frcli "$@"; }
# W1
F report chart "$R" --at A1 --dataset ds1 --type column --category cat --series series --value val --fn sum --show-title --apply
F export image "$R" -o /tmp/x.png          # 图表必须看图；xlsx 里是嵌入图片、逐格 0 非空格
# W3
F report link "$R" --at A3 --to "…/r1_group_subtotal.cpt" --param center='=$A3' --apply
# W4
F report cell "$R" --at D3 --set-formula '=C3/C3[B3:-1]-1' --num-format '#0.0%' --apply
F report cell "$R" --at E3 --set-formula '=SORT(C3)' --apply          # 实测降序
# W5
F report page "$R" --repeat-header-rows 1:1 --apply                   # 表头必须在 0 基第 1 行
F report page "$R" --footer-text '"第 " + $$page_number + " 页 / 共 " + $$totalPage_number + " 页"' --footer-formula --footer-height 20 --apply
<venv>/bin/python -c "import pypdfium2 as p; d=p.PdfDocument('/tmp/x.pdf'); print(len(d)); d[len(d)-1].render(scale=2).to_pil().crop((0,0,1200,300)).save('/tmp/top.png')"
```

---

## 9. §复验（P1–P13 修完后，仅验改动项）

**基准**：`src` 指纹 `5bf10045caf0fec5096c362b01b48521b5ad97dd1408f65c17a296440066cc6b`
（`cat src/frcli/*.py src/frcli/commands/*.py | shasum -a 256`）、`0.9.0`、
`pytest tests/` = **435 passed / 2 历史失败 / 1 skipped** ✅ 与 Lead 给的一致。

| 条目 | 复验做法 | 真实结果 | 结论 |
|---|---|---|---|
| **P1** W2 配方与样例不一致 | 照**新版 §W2** 的 🔴 段逐条抄：`report widget "$R2" --param AREA … --default 华南 --no-declare --apply` | `report param --list` = **只有 `area=华东`**（不再凭空多出 `AREA`）；`widget --list` = `AREA`；默认导出 `华东/100` | ✅ 改对了 |
| — （反证） | 去掉 `--no-declare` 再跑 | 模板参数变成 `area=华东` + **`AREA=华南`** | ✅ 文档对成因的解释成立 |
| **P4** W2 缺三步 | 照新版 §W2 **四步**逐条抄（dataset `where area='${area}'` → table `--at A2` → widget area → widget d1） | 5 条命令全 ok；`widget --list` count=2（ComboBox 华东 / DateEditor 2026-09-01）；`datasets` 干净；**默认导出 `华东/100`、`--params '{"area":"华南"}'` → `华南/200`** | ✅ 与文档实测值逐字一致 |
| **P2** 证据证明不了结论 | 通读新版 §W2 | 已改成"**导出通道根本不走参数面板**，控件名对/错默认导出都是 `华东/100`"，只确证"写错不报错 + 联动只能预览页验" | ✅ 不再有拿导出值当联动判据的表述（**但 SKILL.md §6.18 表格里还残留一处，见下**） |
| **P5** 大小写不敏感 | 对照 §W2 新增规范段 | 与我的实测一致（后声明者胜、两个都传无行返回、"参数名统一小写"） | ✅ |
| **P3** 值列结论过宽 | 读 §W1 静默错表 | 已限定"**纯非数字文本**才塌成 0/空；数字样字符串（`'100'`）照样正常聚合" | ✅ |
| **P6** `link --help` 相反 | `frcli report link --help` | 现在是"**纯预览态交互**：`export excel/pdf` 都不保留任何链接痕迹（`<hyperlink>` 0、`/URI` `/Annots` `/Link` 全 0）⇒ 验收读模板 `report link --list`" | ✅ 与实测一致 |
| **P7** W4 数字张冠李戴 | 读 §W4 写错对照行 | 已改成"该用 `[A3:-1]`（同比）却写 `[B3:-1]`（环比）→ **0.5 / -0.5**" | ✅ |
| **P8** SORT 帮助说法 | 读 §W4.1 | 已删"英文/繁体帮助写升序"，改成"**实测裁定**…安装包只有中文帮助，**未逐语言核对**，一律以实测为准" | ✅ |
| **P9** HR 行号配套 | 读 §W5 ① | 已写"行号是 **0 基**（Excel 行号 = F/T + 1），且必须与表头实际所在行一致；指错行**不是静默**：报 `11300002 行高列宽超出页面大小`" | ✅ 与我的踩坑一致 |
| **P11** 图表体积 | 与我实测对照 | doc 改成"模板体 1.2~1.5KB / **完整单元格 2.2~2.5KB**"。我的实测：柱 **2572B**、饼 **2541B**、折线 **2230B**（2.18~2.51KB）⇒ 区间基本吻合，折线略低于 2.2（0.02KB） | ✅ 可接受 |
| **P12** `--type` 别名 | 读 §W1 第 7 条 | 已补 `column/bar/柱形图/柱状图`、`line/折线图`、`pie/饼图`、`ring/donut/环形图` | ✅ 与 CLI 报错列出的取值一致 |
| §8 超链接带 `<Condition>` | 读 §8 | 已从"未确证"改为"**已确证**（验证者实测）" | ✅ |
| **P13** stderr | 读 `SKILL.md §6.18` | 新增"⚠ 判成败别只看管道后的 stdout：**错误 JSON 走 stderr、成功走 stdout**，`frcli … \| jq` 会吞掉错误" | ✅ |

### 9.1 `tools/doc_rerun.sh`（新增，4511B）

| 检查 | 做法 | 结果 |
|---|---|---|
| **幂等** | `bash tools/doc_rerun.sh` **连跑两次** | 两次都 `DOC-RERUN-OK`、exit 0（单次 34.8s / 4 张验证件重写） ✅ |
| 产物是否**真有内容**（幂等 ≠ 空跑） | 读 `/tmp/cptlab/verify_*` | `verify_w4.xlsx`：`#DIV/0! / 0.5 / #DIV/0! / -0.5`（环比）+ `1.0 / -0.333`（同比）+ 占比 18.2/27.3/36.4/18.2% ✅；`verify_w2.xlsx`（传 `area=华南`）= `华南/200` ✅；`verify_chart.png` 92648B（与我自建柱形图**逐字节同尺寸**）✅；`verify_w5.pdf` 1 页 ✅ |
| 输出目录写死 `/tmp/cptlab/` 是否会导致换机器跑不通 | 导出到**不存在**的目录实测 | 失败假设**被证伪**：CLI 会自动创建父目录（`-o /tmp/不存在/x.png` 仍成功写出 92648B）⇒ 可移植 ✅ |
| 脚本自身约束 | 读脚本 | `set -e`、要求 `FRCLI_WRITE_SCOPE`、`report new --force`、产物落 `patterns/verify/`（写范围内）✅ |

⇒ **"照文档重跑"这条证据现在可复核了** ✅（脚本在仓库、幂等、产物有内容）。

### 9.2 `patterns/_目录说明.txt`（用 `report ws-list` + RPC `readFully` 读）

内容与实际一致（样例清单、`verify/` 说明、脚本位置、连跑两次结论都对得上）✅。
⚠️ 唯一措辞问题：`w2_widget_errname.cpt` 那行写"控件名 AREA ≠ 参数 area → **不联动、不报错**"
—— 与 P2 同类的**导出通道证明不了的**表述（导出看不出联动与否），建议补"（联动只能在预览页验）"。

### 9.3 本轮新发现（3 条，都不阻塞冻结）

| # | 级别 | 问题 | 建议 |
|---|---|---|---|
| Q1 | 🟡 | **`SKILL.md §6.18` 的静默错表里仍有 P2 同类表述**：`参数控件名 ≠ 参数名 → 导出仍用模板参数默认值（完全不联动、不报错）`。导出值证明不了联动（正确的控件名在导出里同样是默认值） | 按新版 §W2 的措辞改一句："写错不报错；联动只能在预览页验，导出通道看不出来" |
| Q2 | 🟡 | `cpt-patterns2.md` §W2 的 🔴 代码块用 `frcli report widget "$R2" …`，但**全文没有 `R2=` 的定义** ⇒ 照抄时 `$R2` 为空，命令被写范围守门拒绝（`已拒绝：reportlets`，exit 1 —— 安全但跑不通） | 补一行 `R2="$B/w2_widget_errname.cpt"` |
| Q3 | ℹ️ | 两处小提示：① 我一开始用 `report list` 找 `_目录说明.txt` 得到"不存在"，**其实 `report list` 只返回模板**（要 `report ws-list` 才列原始文件）；② 配方里的 `$B` 指向团队样例目录 `patterns/`，照抄 `report new "$B/xxx.cpt"` 会试图写样例目录（`report new` 不带 `--force` 会**响亮拒绝**，`--force` 才会覆盖）—— 建议配方用独立目录 | 可写进 §0/§W 的开头提示 |

**§复验结论：P1–P13 全部改对且经实测复核；`doc_rerun.sh` 幂等、产物有效、可移植。**
新发现 3 条均为措辞/可用性小问题（Q1 是 P2 的同类残留，建议顺手改），**不阻塞 bump 0.10.0 与冻结**。

### 9.4 Q1–Q3 复验 + 冻结基准（最终）

**冻结基准**：`0.10.0`（四处一致：`__init__.py` / `pyproject.toml` / `SKILL.md` / `README.md` ✅）、
`src` 指纹 `5568338bedb2ce8f065c05cdf5a28bcbf648bbf1a1c6b6e3a514ea3834438736`、
`pytest tests/` = **435 passed / 2 历史失败 / 1 skipped** ✅；
`py_compile src/frcli/cptxml.py` + `import frcli.cli` 均 OK ✅（防 lint 清理留下的语法问题）。

| 条目 | 复验做法 | 结果 |
|---|---|---|
| **Q1** `SKILL.md §6.18` | 读第 652 行 | 已改成「控件存在、`--list` 显示它，**不报错**；但**联动与否导出通道验不了**（控件名正确时默认导出同样是模板默认值）」+「联动只能在预览页点一下验」 ⇒ 不再有用导出值推联动的表述 ✅ |
| **Q2** §W2 🔴 代码块 | 代码块已补 `R2="$B/w2_widget_errname.cpt"`；**照抄一遍**（按 Q3 新提示把 `$B` 换到自己的目录、先把样例复制过去） | `widget status=ok`、**exit 0**（不再被写范围守门拒绝）；`widget --list` = `AREA`(ComboBox,默认华南)；**模板参数仍只有 `area=华东`（未被污染）** ⇒ 与代码块注释逐字一致 ✅ |
| **Q3** 开头提示块 | 读开头 | 已写明「照抄前先改 `$B`」（指向团队样例目录、`--force` 会覆盖样例）+「`report list` 只返回模板，看 `_目录说明.txt` 用 `report ws-list`」✅ 与我的发现一致 |
| **回归** `cptxml.py`（`report link` 读 `<NameJavaScriptGroup>` 那段） | `report link --list` 读作者样例 `patterns/w3_link.cpt` | `count: 2`：A2 = `WebHyperlink` → `https://www.fanruan.com`、`_blank`；A3 = `ReportletHyperlink` → `…/r1_group_subtotal.cpt`，参数 `center=$A3`、`flag=1` ⇒ **与重构前我读到的完全一致** ✅ |

**这一轮又发现 2 处文本残留（Q4/Q5，都只改文字、不动 `src`，指纹不受影响）**：

| # | 级别 | 位置 | 问题 |
|---|---|---|---|
| Q4 | 🟡 | `cpt-patterns2.md` **§W3 写错对照表**（line 264） | 发现时仍写「…**本辑未验**；要用请先小样试」，而同一文件 **§8（line 433）已改成「已确证」** ⇒ 自相矛盾。**→ ✅ 已修复并复验**：line 264 改为「已确证（见 §8）：导出正常（excel 4337B / pdf 35170B，1 页），同样没有任何链接痕迹；与不带 Condition 的唯一区别是不会炸」，与 §8 逐项对齐 |
| Q5 | 🟡 | ① `cpt-patterns2.md` **§8 样例表**（line 424）；② 服务器 `patterns/_目录说明.txt`（line 27） | 两处仍是 **P2/Q1 同款表述**（拿导出值当联动判据）。**→ ✅ 已修复并复验**：① line 424 改为「控件存在、不报错；联动与否导出通道验不了（控件名正确时默认导出同样是模板默认值）⇒ 只能在预览页验」；② 服务器说明文件同改，复验者从服务端回读确认（新 sha `3fc51970647d7cf7`、3205B）。全库 grep 仅剩 `:202` 一处**说明性注释**，已判定为非残留 |

**过程留痕（Lead 自述，照实记录）**：冻结前 Lead 用脚本降 `cptxml.py` 缩进时**连续降了两次**，
把该文件写成 `IndentationError`、全队 10 个 collection error，重读源码后一次修对。
连同早前的「正则删多了建表行」「raw 字符串双引号提前闭合」，**这是同一轮里第三次"脚本改文件"翻车**。
⇒ 建议固化为纪律：**改文本/代码一律小步改 + 立刻 `py_compile` / `import` 自检**（本轮我每次都这么做，
包括 3 次 XML 注入的 `re.subn` 断言 `n==1` + 服务端回读）。

---

## 10. Lead 处置记录（冻结前补记）

**问题状态终局**：本报告 **P1–P13 + Q1–Q5 全部「已修复并复验」**，无遗留项。

| 分组 | 处置 |
|---|---|
| P1–P13（第二辑文档缺陷） | `cptlab` 逐条修改 `references/cpt-patterns2.md` + `SKILL.md §6.18` + `report link --help` 文案；复验者逐条照抄重跑确认（含 P4 四步配方得到 `华东/100 → 华南/200`、P1 `--no-declare` 反证、`doc_rerun.sh` 连跑两次 `DOC-RERUN-OK`） |
| Q1–Q3（复验中新发现） | Lead 直接改（`SKILL.md` 措辞、`cpt-patterns2.md` 补 `R2=` 定义、开头加「照抄前先改 `$B`」提示）；复验者照抄 §W2 🔴 段确认 `exit 0` 且模板参数未被污染 |
| Q4–Q5（本轮又发现的文本残留） | Lead 改（含服务器 `_目录说明.txt` 纯文本重传）；复验者从服务端回读确认 |
| 回归 | `report link --list` 读 `patterns/w3_link.cpt` → `count: 2`（A2 `WebHyperlink` / A3 `ReportletHyperlink` + `center=$A3`），与重构前**逐字段一致** |

**冻结快照**：版本 `0.10.0`（四处一致）｜`src` 指纹 `5568338bedb2ce8f065c05cdf5a28bcbf648bbf1`｜
`pytest 435 passed / 2 历史失败 / 1 skipped`｜仓库与安装态 skill `diff -rq` 一致。
lint 剩 2 处 `E127`（缩进风格，与基线既有的 E128 同类，**明确不修**，避免为风格重跑回归）。
