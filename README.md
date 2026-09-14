# fanruan_v10

FineReport V10（帆软决策平台）CLI 工具 **`frcli`** 与其 agent skill **`fanruan_v10`** 的同一份源码仓库 —— skill 与 CLI 同源，`src/frcli/` 是唯一源码，不存在副本同步问题（结构仿 `yh-bigdata`）。

- **Skill 名**：`fanruan_v10`（入口 `SKILL.md`）
- **命令**：`frcli`
- **源码**：`src/frcli/`
- **版本**：0.1.0

## 安装 / 自举

```bash
pip install -e .                 # 开发安装（src 布局）
frcli --version

# 或零安装直跑（未装/不在 PATH 时）
cd src && python -m frcli --version
python references/run.py --version        # 跨平台启动器
```

完整自举手册见 `references/install.md`。

## 快速开始

```bash
# 1. 配置实例（密码明文落在 ~/.frcli/config.yaml；agent 必须带 -p，否则交互式提示会卡住）
frcli server add yh --url https://<服务器> -u <工号> -p '<密码>' --set-default
frcli server test

# 2. 找报表（目录要具体；`/` 会拉全量，实测 3870 条）
frcli report list "demo_group/demo_user/dept_a/dept_b" -f table

# 3. 看数据集与取数口径
frcli report datasets "demo_group/demo_user/dept_a/dept_b/sales_daily.cpt" --sql -f table

# 4. 导出（只传驱动参数；复杂报表务必调大超时）
FRCLI_TIMEOUT=300 frcli export excel "demo_group/demo_user/dept_a/dept_b/sales_daily.cpt" \
    -o /tmp/sales_daily_20260731.xlsx --params '{"edate":"20260731","extype":"simple"}'

# 5. 校验产物（必做：导出「成功」也可能是 HTML 出错页面）
python3 -c "print('OK' if open('/tmp/sales_daily_20260731.xlsx','rb').read(4)==b'PK\x03\x04' else '坏文件')"

# 6. 批量导出
#   manifest.yaml:
#     reports:
#       - path: demo_group/demo_user/dept_a/dept_b/sales_daily.cpt
#         format: excel
#         output: ./out/sales_daily_20260731.xlsx
#         params: {edate: "20260731", extype: simple}
FRCLI_TIMEOUT=600 frcli export batch manifest.yaml

# 7. 定时任务（读）
frcli schedule list -f table
frcli schedule get "demo_user_销售_示例概览by月_飞书"        # 拿 UUID id
frcli schedule history "demo_user_销售_示例概览by月_飞书" -n 5
```

## 命令组概览

| 命令组 | 用途 | 主要命令 |
|--------|------|----------|
| `server` | 多实例配置 | `list` / `add` / `remove` / `set-default` / `test` |
| `report` | 报表模板 | `list` / `info` / `datasets` / `download`（`upload` / `delete` 未实现） |
| `export` | 报表导出 | `pdf` / `excel` / `word` / `image` / `csv` / `batch` |
| `schedule` | 定时任务 | `list` / `get` / `create` / `update` / `delete` / `run` / `history` |

完整命令树、参数语义与安全分级见 **`SKILL.md`**；`frcli <命令组> --help` 是最终事实来源。

全局选项：`-i/--instance NAME` 指定实例，`-v/--verbose`，`--version`。多数查询命令支持 `-f json|table`（默认 json）。

## 输出与退出码

CLI 输出为 JSON（`-f table` 为表格），便于 agent 解析：

```json
{"status": "ok", "action": "export", "format": "excel", "report": "...", "file": "/path/to/report.xlsx"}
```

错误输出到 stderr：`{"status": "error", "error": {"code": "AUTH_FAILED", "message": "..."}}`

退出码：`0` 成功、`1` 业务错误、`2` 配置错误、`3` 连接错误。

## 配置与认证

- 配置搜索顺序：`$FRCLI_CONFIG` → `~/.frcli/config.yaml` → `./.frcli.yaml`
- token 缓存：`~/.frcli/tokens/<实例>.json`（默认 24h，401/403 自动重登）
- 环境变量：`FRCLI_TIMEOUT`（秒，默认 30，复杂报表导出调大）、`FRCLI_CA_CERT`（CA 证书路径）、`FRCLI_CONFIG`

```yaml
default: yh
instances:
  yh:
    url: "https://<服务器>"
    username: "00000000"
    password: "xxx"          # 明文存储
    workspace: "/webroot"
```

## 目录结构

```
fanruan_v10/
├── SKILL.md              # agent 入口：命令树 / 安全分级 / 实测坑点 / 故障排查
├── README.md             # 本文件（人类可读）
├── AGENTS.md             # 开发规范（CLAUDE.md / CODEBUDDY.md 为软链）
├── pyproject.toml        # 打包定义（src 布局）
├── src/frcli/            # CLI 唯一源码
├── references/
│   ├── install.md        # 自检 + 自举手册
│   ├── run.py            # 跨平台启动器（自举 + 软链自愈 + 版本提示）
│   ├── run.sh            # Unix 便捷入口
│   └── frcli             # 软链 shim（PATH 中的 frcli 指向它）
└── tests/                # pytest
```

## 已知限制

- `report upload` / `report delete`：CLI 有入口但未实现，服务器也不支持 Web API 改模板 —— 改模板走决策平台网页
- 无 `query` 命令（早期 README 遗留）：要看数据集 SQL 用 `report datasets`
- 导出遇到报表侧错误（数据集 SQL 报错、缺参数）时返回 HTML 出错页面且 HTTP 200，CLI 仍报 `status: ok` —— 必须校验文件魔数
