# 函数检索、公式检查与动态默认值

适用版本：frcli / fanruan-v10 skill ≥ **0.10.26**。

写公式前先用 `report functions NAME` 确认 FineReport 名称和签名，再用
`report formula-check EXPR` 检查基础语法。两条命令都离线运行，无需实例配置。

## 1. 目录范围与证据

随包目录含 183 条记录：`fine-core-10.0.jar` 的 167 个大写函数实现类、
`fine-report-engine-10.0.jar` 的 13 个大写函数实现类，以及官方文档中的 3 个数据集方法。
分类、中文简要用途和提示由本项目整理；不分发厂商帮助正文或反编译源码。

来源分工：

| 来源 | 用途 |
| --- | --- |
| `com.fr.function.*` 实现类 | 核对函数名称和实现存在性 |
| `DefaultNameSpace.getMethod/getClassName` | 核对名称大小写处理、配置/插件查找与默认实现类查找 |
| `fine-third-10.0.jar!com/fr/i18n/function/core_zh.properties` | 核对随包调用签名 |
| `FRLexer.mSTRING_LITERAL_DSQ/mSTRING_LITERAL_SSQ/mESC` | 核对单双引号与反斜杠转义 |
| [设计器函数汇总](https://help.fanruan.com/finereport10.0/doc-view-3930.html) | 官方分类与使用入口 |
| [函数计算格式](https://help.fanruan.com/finereport10.0/doc-view-253.html) | 公式组合与文本表达式 |
| [数据集函数](https://help.fanruan.com/finereport10.0/doc-view-850.html) | `dataset.select/group/value` 与上下文限制 |
| [其他函数](https://help.fanruan.com/finereport10.0/doc-view-810.html) | `RANK`、`QUERY` 等函数的参数语义 |

目录是补丁版本的静态基线。实现存在、公式可解析、报表正确求值是三个不同的结论。
当前实例的插件、自定义函数和安全限制需要另行核对；未收录名称只提示。
`signature` 是速查写法，未列举所有可选形式；未核实的签名返回 `null`，不按类名猜参数。
`evidence`、`implementation`、`source_jar`、`help_key` 标明单条记录的依据。

## 2. 查询与检查

```bash
frcli report functions RANK
frcli report functions --keyword 日期 -f table
frcli report functions --category hierarchy -f table
frcli report functions DATASET.VALUE
frcli report formula-check '=SUM(B3[!0])+RANK(B3,B3[!0],0)'
frcli report formula-check '=FORMAT(TODAY()-1,"yyyyMMdd")' --context parameter
frcli report formula-check '=IF($topn>0,SUM(ds.select(金额)),0)' --param topn
```

分类名：`math`、`trigonometry`、`text`、`datetime`、`logic`、`array`、`dataset`、
`report`、`hierarchy`、`other`。JSON 返回分类中文名、检索结果及来源；表格输出用于浏览。

检查会识别单双引号、反斜杠转义和括号 `()` / `[]` / `{}` 配对，忽略字符串中的函数名，
并提示未知名称、报表上下文依赖和参数面板的数据集方法限制。
`--param` 可重复，用于指定本次已声明的参数；未给时不检查参数声明。
`syntax: basic-checks-passed` 只表示这些基础检查通过。检查不建立完整语法树，不验证函数
参数数量/类型、数据集列名、父格关系、权限或结果，也不执行 `SQL/EVAL/QUERY`。

`report cell --set-formula` 使用相同的基础语法检查。未收录函数会产生 warning，
合法的插件公式仍可进入 dry-run；真正写入沿用 `--apply` 的授权与写范围检查。

## 3. 选择正确的公式

| 需求 | 写法或选择 | 注意事项 |
| --- | --- | --- |
| 格内引用模板参数 | `$edate` | SQL 中的 `${edate}` 是另一种替换位置 |
| 日期格式化 | `FORMAT(TODATE($edate,"yyyyMMdd"),"yyyy-MM-dd")` | 不套用其他软件的 `DATEFORMAT` 名称 |
| 空值兜底 | `NVL(value,0)` / `IF(ISNULL(value),0,value)` | 空字符串处理按目标数据验收 |
| 数组逐项运算 | `MAPARRAY([2,4],item*2)` | `MAP` 用于数据集查找；两者用途不同 |
| 数组去重计数 | `COUNT(UNIQUEARRAY(B3[!0]))` | 先确定扩展范围，再核对空值规则 |
| 数值数组排名 | `RANK(value,array,0)` | `0` 降序，非零升序；不要从一个失败的报表表达式推断函数不存在 |
| 报表扩展区域排名 | `SORT(B3)` / `SORT(B3,false)` | 默认降序，`false` 升序；先核对扩展与父格 |
| 环比增长率 | `MOM(A3,B3)-1` | `MOM` 本身是比值；首期、零分母与分组边界需另行处理 |
| 数据集条件取列 | `ds.select(金额,数量>0)` | 得到数组后可再套 `SUM`；参数面板不支持此类方法 |
| 数据集取一个值 | `ds.value(row,column)` | 普通 `VALUE(ds,column,row)` 的顺序不同 |
| 文本 JSON 查询 | `QUERY(text,"$.amount")` | 查询脚本依赖目标运行时；检查命令不运行脚本 |

层次坐标、累计、跨层累计和横向扩展详见 [配方二](cpt-patterns2.md)。
汇总数据设置的 `--fn sum/count/...`
控制 `<RG>/<FN>`，与单元格公式函数是两个入口。

## 4. 公式默认值

静态默认值保持字面量语义，公式使用显式参数：

```bash
# 模板参数：默认昨天，省略前导 = 也可；可重复设置多个参数
frcli report param demo_group/demo_user/demo.cpt \
    --set-formula 'edate=FORMAT(TODAY()-1,"yyyyMMdd")' \
    --set-formula 'sdate=FORMAT(DATEINMONTH(TODATE($edate,"yyyyMMdd"),1),"yyyyMMdd")'

# 控件与同名模板参数同时写公式默认值
frcli report widget demo_group/demo_user/demo.cpt --param edate --type text \
    --default-formula 'FORMAT(TODAY()-1,"yyyyMMdd")'

# 只修改指定数据集自己的参数默认值
frcli report edit demo_group/demo_user/demo.cpt --dataset ds --param edate \
    --default-formula 'FORMAT(TODAY()-1,"yyyyMMdd")'
```

以上均为 dry-run。🔴 用户明确授权目标、确认影响并满足 `FRCLI_WRITE_SCOPE` 后，
加 `--apply` 才写；覆盖仍走占锁、备份和回读校验。相同默认值再次设置成功返回
`changed: false`，不发送写请求。

`--set-formula NAME=EXPR` 添加或更新模板参数；`--set-default NAME=VALUE` 将它设为静态值。
同一个参数不能在一次调用中同时设置静态值与公式。`--default` 和 `--default-formula`
同样互斥，静态值即使以 `=` 开头也保持文本。

`report param` 只改模板参数，`report edit --dataset` 只改目标数据集参数；这两个命令不会
自动覆盖参数面板。`report widget --default-formula` 默认同时更新控件与模板参数，
`--no-declare` 时只更新控件。控件命令会替换同名控件，编辑已有控件时应明确其类型、
选项、尺寸和位置。

公式写成 `<O t="XMLable" class="com.fr.base.Formula"><Attributes>…</Attributes></O>`。
`report param --list`、`report widget --list` 用 `default_type: formula|value` 区分；
默认值正文仍保留在 `default`。同名数据集参数、模板参数和控件按结构定位，不全局替换。

## 5. 验收与补丁版本核对

先检查 dry-run 中的目标作用域、`default_type` 和 diff。运行期验收需在用户授权的模板上，
分别用默认参数与显式日期参数预览/导出，逐格核对日期和数值。批量导出需先确认规模。
本地结构往返测试或函数实现类的独立调用不能代替这一步。

升级 FineReport 后，在用户提供的安装目录中只读核对这两个 jar 的
`com/fr/function/[A-Z][A-Z0-9_]*.class` 清单，并检查插件与函数配置。
用 JDK 的 `javap -c -p` 查上述类方法；随包帮助在 `fine-third-10.0.jar` 中。
更新目录时保留来源和未核实签名的空值，再运行 `tests/test_formulas.py` 与完整测试。
