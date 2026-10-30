# CPT 结构编辑：逆向依据与验收

适用：frcli 0.11.0，FineReport V10。测试使用固定数值模板和独立的获准临时目录。
研究原件、反编译输出及带水印的导出物不进入仓库。

## 1. Evidence → Finding → Implementation

| 证据 | 已确认的行为 | CLI 的处理 |
|---|---|---|
| `DeleteColumnAction` / `DeleteRowAction` 调用 `ElementCase.removeColumn/removeRow` | Designer 使用引擎的结构变换，不只是删除 XML 节点 | 行列操作先生成完整坐标映射，再联动已识别结构 |
| `RemoveColumnMOD.mod_fm_statement` → `ScriptUtils.moveColumn` → `Calculator.onAddDeleteColumnOrRow` | 删除 B 列时 `B1 → A1`、`C1 → B1`；删除目标本身也被改指相邻坐标 | 存活内容仍指向被删坐标时阻止变更，提供具体依赖 |
| 同一公开引擎算法输入 `$C3`、`&C3` | `$C3` 保持原样，`&C3 → &B3` | 已识别的 `$Cell` 坐标随存活的逻辑目标移动；不把 `$` 当 Excel 的单轴锁定 |
| 同一算法输入 `C3[B3:-1]`、`C3[!0]` | 分别得到 `B3[A3:-1]`、`B3[!0;!0]` | 更新层次表达式中的坐标，保留索引和其他原文 |
| `SheetUtils.calculateDefaultParent` | 上父格跟随横向扩展；左父格跟随纵向扩展；合并跨度和显式无父格参与扫描 | 索引默认父格，变换前后检查等价性；不推断新的业务父格 |
| 官方样例中的 `ColumnRow` / `FixCell` | 条件比较、填报配置、行操作控件也保存独立坐标 | 注册结构化坐标载体，与公式使用同一映射 |

这些是调用链与底层算法证据，不宣称完成所有 Designer 界面操作的复现。
所证明的改进是明确的删除冲突检测、更多引用载体和严格的未支持诊断，不能据此宣称全面替代 Designer。

## 2. 公开接口对照的复现

设置 `FINEREPORT_HOME` 为合法安装包位置，输出目录由使用者创建：

```bash
CPT_ORACLE_CP="$FINEREPORT_HOME/lib/*:$FINEREPORT_HOME/webapps/webroot/WEB-INF/lib/*"
mkdir -p /tmp/cpt-oracle
javac -cp "$CPT_ORACLE_CP" -d /tmp/cpt-oracle tools/CptOracleProbe.java
java -Djava.awt.headless=true -cp "/tmp/cpt-oracle:$CPT_ORACLE_CP" CptOracleProbe \
  'B1' 'C1' '$C3' '&C3' 'C3[B3:-1]' 'C3[!0]' '"C3"+C3'
```

该工具仅调用公开算法，不改变安装包、许可证或客户端配置。它是开发对照工具，CLI 不依赖它。

不能直接套用 Excel 的 `$A$1` / `A$1` 语义。固定常量样例中 `$B$2*2` 和 `$B2*2` 均曾返回 0，
说明没有相应层次上下文时不能拿预期 40 做坐标验收。此结果不是 Designer 删列缺陷的证据。
正式数值验收使用有独立含义的 `A2+B2`、`SUM(B2[!0])*2`、`C2+1`。
`$Cell` 的语义参考 [官方操作符说明](https://help.fanruan.com/finereport10.0/doc-view-249.html)，
绝对/相对层次位置参考 [官方层次坐标](https://help.fanruan.com/finereport10.0/doc-view-339.html)。

## 3. 固定数值模板的真实导出

数据源只有常量公式 `10`、`20`，不查询数据库。每个样例上传后重新下载，与本地字节比较；
导出 XLSX 后读工作表 XML 和数值缓存，不以文件魔数或 `status: ok` 代替验收。

| 场景 | 核对单元格 | 导出数值 | 标题合并 |
|---|---|---|---|
| 基线 | C2 / D2 / H2 | 30 / 40 / 31 | A1:D1 |
| B 前插入两列 | E2 / F2 / J2 | 30 / 40 / 31 | A1:F1 |
| 删除新插入的 B 列 | D2 / E2 / I2 | 30 / 40 / 31 | A1:E1 |
| A2:D2 复制到 A4 | C4 / D4 / H2 | 30 / 40 / 31 | A1:D1 |
| A2:D2 移动到 F4 | H4 / I4 / H2 | 30 / 40 / 31 | A1:D1 |

五个样例最终全部满足数值、合并和原文件回读要求。PNG 已检查文件格式并打开查看，包含预期标题与数值；
宽表超出打印宽度时，合成图片会包含横向分页，不能把图片的纵向拼接位置误判成模板行号。
样例模板与空测试目录已按本次授权清理。

## 4. 回归与验证边界

离线测试覆盖：普通/跨页/层次引用、字符串与参数区分、多段删除、范围收缩、合并主格、
显式与默认父格、结构化坐标、区域重叠和冲突、未知插件与动态公式、本地无配置/无网络、
输出不覆盖、写范围零请求、占锁后快照变化及解锁。

静态测试与导出测试分别证明不同层次的行为；本次没有为全部图表、控件、自定义脚本和填报业务做运行时验收。
聚合块独立坐标已离线验证；跨块语义、非网格块、浮动对象及未知插件明确阻断。
含 `$Cell` 的复制尚未确证，返回 `copy_value_position`；`$A$1` 等 Excel 写法不会被当成已确证引用自动改写。
复杂默认父格循环和特殊布局不自动“修好”，需要具体样例补充处理器与回归。

完整命令和边界见 [结构编辑手册](../../references/cpt-structure.md)。
