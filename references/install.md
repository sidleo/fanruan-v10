# frcli 自检 + 自举手册

> 适用场景：执行 `frcli` 报 `command not found`（或 agent 环境中无本地 shell 工具时无法直接调用命令）。
> 核心：**skill 自带完整 Python 源码**（`src/frcli/` + `pyproject.toml`），无需网络即可自举，与 PATH / 安装位置 / 操作系统无关。

## 0. 快速结论（三选一）

| 方式 | 命令 | 适用 | 是否需安装 |
|------|------|------|:---:|
| A. 直接调用 | `frcli <命令>` | 命令已在 PATH | 否 |
| B. 内置源码直跑（推荐） | `python -m frcli <命令>`（在 `<base>/src` 下） | 未入 PATH / 任何环境 | **否（零安装）** |
| C. 装进当前 Python 环境 | `pip install -e <base>` | 希望命令全局可用 | 是（离线可行） |

其中 `<base>` = 本 skill 的 base 目录（SKILL.md 的 `<skill_resources>` 中会注入，形如 `<安装位置>/fanruan_v10`，不同机器不同）。

Windows 用户注意：`.sh` 脚本无法直接运行，统一用 **`python run.py`** 或方式 B。

## 1. 自检（确认是否真的缺失）

```bash
command -v frcli && frcli --version
# 或（Windows / 无 shell 时）:
python -c "import shutil; print(shutil.which('frcli'))"
```

有输出 = 命令可用，直接用即可，无需自举。**注意**：`command -v` 命中的可能是 pip 装的旧副本，可用 `ls -l "$(command -v frcli)"` 看它是否指向本 skill 的 `references/frcli`。

## 2. 自举方式 B —— 内置源码直跑（最稳，零安装，跨平台）

```bash
cd <base>/src
python -m frcli --version        # 验证
python -m frcli server list
```

或使用配套启动器（等价，且不要求 cd）：

```bash
# Unix (macOS/Linux):
<base>/references/run.sh server list
# 跨平台 (Windows/macOS/Linux 通用):
python <base>/references/run.py server list
```

> 原理：`python -m frcli` 把 `src/` 当作包路径，绕开 PATH。只要求环境里有 Python 3.10+。

### 自动建软链（一次自举，之后直接可用）

`run.py` 在自举成功后，会**自动在 PATH 中可写的用户级目录**（如 `~/.local/bin`、`~/bin`）创建
`frcli` 软链，指向 `references/frcli` 独立 shim（非 run.py，无递归）。

- **第一次**：`python run.py <命令>` 自举执行 → 同时建好软链；
- **第二次起**：直接敲 `frcli <命令>` 即可，shell 命中软链，不再 `command not found`。

> 若建链失败（Windows 无 symlink 权限 / 目录只读），run.py 静默跳过，继续用 `python run.py` 即可，功能不受影响。

### 软链自愈 + 版本一致性（skill 更新后自动切到新代码）

`run.py` 每次运行时还会做两件事，保证不会无感知用旧代码：

1. **软链自愈**：若 PATH 中已有 `frcli` 软链，但指向的不是当前 skill 的 shim（旧路径 / 失效路径），自动重建指向当前 skill。
2. **版本提示**：若 `frcli` 来自其他安装（pip 装过、别的 skill 副本），`run.py` 会打印该命令的实际来源路径与当前 skill 内置源码版本，让 agent 判断是否在用旧版。仅提示，不阻断执行。

> 约定：skill 源码更新时同步 bump 版本号（`src/frcli/__init__.py` 的 `__version__` 与 `SKILL.md` front-matter 的 `version`）。

## 3. 自举方式 C —— pip 安装（装进当前 Python 环境）

```bash
pip install -e <base>          # editable 安装，改源码即生效
frcli --version                # 安装后验证
```

> 若 `pip install -e` 报缺依赖：
> ```bash
> pip install "click>=8.0" "httpx>=0.25" "pyyaml>=6.0" "rich>=13.0"
> ```
> （离线环境无法装依赖时，回退方式 B —— 前提是依赖已在 Python 环境中。）

## 4. 自举方式 D —— PYTHONPATH（最小侵入，不装包）

```bash
PYTHONPATH=<base>/src python -m frcli --version
# Windows (PowerShell):
# $env:PYTHONPATH = "<base>\src"; python -m frcli --version
```

## 5. 依赖核对

| 依赖 | 用途 | 缺失时 |
|------|------|--------|
| `click` | CLI 框架 | `pip install "click>=8.0"` |
| `httpx` | HTTP 客户端 | `pip install "httpx>=0.25"` |
| `pyyaml` | 读取 `~/.frcli/config.yaml` / batch manifest | `pip install "pyyaml>=6.0"` |
| `rich` | 表格输出（`-f table`） | `pip install "rich>=13.0"` |

自举完成后，**还需配置实例**（连接信息不随 skill 分发，每台机器各自配置）：

```bash
frcli server add yh --url https://<服务器> -u <工号> -p '<密码>' --set-default
frcli server test
```

配置落在 `~/.frcli/config.yaml`，token 缓存在 `~/.frcli/tokens/<实例>.json`。

## 6. 常见问题

| 现象 | 处理 |
|------|------|
| `python -m frcli` 报 `ModuleNotFoundError: No module named 'frcli'` | 未在 `<base>/src` 下执行，或 PYTHONPATH 没指对，检查第 2/4 节 |
| `pip install -e` 报构建错误 | 确认 Python ≥ 3.10；或改用方式 B（零安装） |
| Windows 上 `.sh` 无法运行 | 用 `python <base>/references/run.py`，不要用 run.sh |
| `frcli` 已装但不入 PATH | 方式 B 或 D 直接可用，无需改 PATH |
| 自举后所有命令返回 `[]` | 与本手册无关：token 缓存过期，`rm -f ~/.frcli/tokens/*.json` 后重试 |
| `未配置任何 FineReport 实例` | 见第 5 节，`frcli server add` 配置实例 |
| 命令跑起来但卡住不动 | `server add` 未带 `-p`，交互式输入密码被阻塞；改为带 `-p` 重建实例 |
| 想确认自己跑的是哪份代码 | `ls -l "$(command -v frcli)"`；本 skill 的应为软链指向 `<base>/references/frcli` |
