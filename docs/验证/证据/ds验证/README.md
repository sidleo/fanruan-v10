# 证据：数据设置（分组/列表/汇总）与 P9 裁决

配套报告：[`docs/验证/cpt数据设置验证报告.md`](../../cpt数据设置验证报告.md)（本轮 `dsverifier`）。

## JSON（原始测量结果，每变体 3 轮 × xlsx+csv）

| 文件 | 内容 |
|---|---|
| `matrix_core.json` | 语义与 P9 对照 10 变体：`base2`(命令默认) / `s_list` / `s_group` / `s_sum` / `s_none` / `o_none` / `o_func` / `o_list` / `d_none` / `d_list` |
| `matrix_b3.json` | 重复值数据集 8 变体（P0–P3 + `<Expand>` 坑）：`b3_none/func/list/sum/sum_count/expandnone/extonly/extdir` |
| `matrix_b3b.json` | `extendable` 整数（`3`）与无 `dir` 两种 |
| `matrix_adversarial.json` | 对抗 8 变体：错 `<FN>` / 不存在的 `<RG>` 类 / 旧包名 / `Condition` 组合 / `MonoGrouper` / 文本列汇总 |
| `cmdpath.json` | 命令路径端到端（`report table` 默认 / `--mode group` / `--mode summary --group-by --fn`）逐格 |
| `matrix_continuum.json` | `divideMode=0/2` 对照（数据集 `10,20,10`，重复值**不相邻**）：分组 2 行/30、连续分组 3 行/40 |
| `p9read.json` | P9 读法实验：`ws['C4']`（模板坐标）vs 合计行（按内容），编辑前后各 3 次 |

每个 rep 里：`xlsx` = openpyxl 逐格值、`csv` = csv 逐行值、`xlsx_rc/csv_rc` = 命令退出码、
`xlsx_msg/csv_msg` = 失败时的 CLI 原文（302 与出错页都在这里）。

## 脚本（可直接重跑；需 `<venv>` + `FRCLI_WRITE_SCOPE`）

| 文件 | 用途 |
|---|---|
| `gen.py` `gen2.py` `gen3.py` | 从 `report new/dataset/table/cell` 造出的 base 模板**按列替换 `<O>` / `<Expand>`**，生成对照件（手写 XML，不依赖命令默认值） |
| `run.py` | 上传 → 导 xlsx+csv（各 3 轮，撞 302/出错页自动重试并记录原文）→ 逐格读回 → 落 JSON。`DSV_JSON=xx.json` 改输出名 |
| `p9_read.py` | P9 读法实验（模板坐标 vs 内容；编辑前后） |
| `cmd_path.py` | 命令路径端到端 + 语义校验矩阵 |

> 重跑前先 `export FRCLI_WRITE_SCOPE="demo_group/demo_user/skill测试"`、`export FRCLI_TIMEOUT=300`；
> 脚本里的数据集是常量 SQL（`select 'A' k,10 amt union all …`），不依赖任何业务表。
> 重跑会在测试目录新建 `dsv_*` 模板 —— **跑完请 `report delete` 清理**（本轮已全部删除）。
