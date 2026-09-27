# 决策平台 REST 可达性实测（普通分析账号视角）

> 生成方式：先反解全部路由（见 [REST路由清单](REST路由清单.md)），再**逐条真调**，
> 并利用平台出错页里的 `Required <type> parameter '<name>' is not present` **自动补参数重试**。
> 所有探测都是 GET 只读；带副作用嫌疑的路径（refresh/flush/clear/remove/kill/update/set）一律未探测。

## 结论

| 类别 | 数量 | 说明 |
|------|------|------|
| 反解出的路由条目 | 961 | 已剔除 `fine-third`（第三方库自带控制器）；`{version}` 归一为 `v10` |
| 纯 GET（只读候选） | 410 | |
| frcli 已覆盖 | 84 | 见 SKILL.md §6.8 |
| **本账号真能调通的「新」只读端点** | **15** | 见下表 |
| 明确 `No_Privilege`（需管理员） | 25 | 见文末 |

**关键判断**：REST 这条线对本账号基本挖到底了 —— 剩下的要么需管理员，要么价值很低。
真正还有空间的是**远程设计 RPC 通道**（28 个服务类，除 token 外没有逐路径鉴权），见 SKILL.md §6.7。

## 新发现且可用的只读端点

| 端点 | 必带参数 | 实测返回 |
|------|----------|----------|
| `/v10/config/connection/list` | — | 数据连接 **4** 条（name/type/driver…），可用于取数溯源 |
| `/v10/schedule/record/list` | `page` `perPage` | 全平台执行记录，`total=117683`（与 frcli 的 `schedule record` 不同端点） |
| `/v10/schedule/info/executing` | — | 调度 worker 忙闲明细（`BusyWorker list count 100 busy list size 0`） |
| `/v10/schedule/setting` | — | 调度全局设置 7 项 |
| `/v10/roles` | `page` `count` | 角色清单（本账号可见 3 个） |
| `/v10/user/roles` | — | 我的角色（customRoles UUID 列表） |
| `/v10/departments/list` | `page` `count` `keyword` | 部门分页查询 |
| `/v10/departments/tree`、`/v10/departments/posts/tree` | — | 本账号实测为空 `[]` |
| `/v10/posts`、`/v10/deposts` | — | 岗位 39 条 / 部门角色树 |
| `/v10/entry/tree`、`/v10/directory` | `keyword` | 条目树 / 目录节点（与 `/entries` 另一套分页接口） |
| `/v10/homepages`、`/v10/favorite/entry/list` | — | 首页 / 我的收藏 |
| `/v10/message/list` | — | 消息（分页体） |
| `/v10/log/config` | — | 日志配置 14 项（level/open/autoCleanTime…） |
| `/v10/config/login`、`/v10/config/password/strategy`、`/v10/config/basic/param` | — | 登录 / 密码策略 / 基础参数 |
| `/v10/migration/status`、`/v10/encryption/status` | — | 迁移、加密状态 |

> 自动补参数这件事本身可复用：调用任何 `/decision/v10/*` 报错时，先读出错页
> `detail-message`，里面会直接告诉你缺哪个参数（`Required int parameter 'page' is not present`），
> 补上再试即可 —— 比翻前端 JS 快得多。

## 明确不可达（`Fine-Dec_No_Privilege_Access_Page`，需管理员）

`/v10/dataset`、`/v10/dataset/files`、`/v10/dataset/file/verification`、
`/v10/config/connection/lic/info`、`/v10/config/connection/pool/info`、
`/v10/drivers/list`、`/v10/drivers/simple/list`、`/v10/template/visit`、`/v10/template/auth/config`、
`/v10/user/departments`、`/v10/superuser/list`、`/v10/warning/preview*`、`/v10/security/*`、
`/v10/register/*`、`/v10/plugin/installation`、`/v10/cluster/info`、`/v10/backup/config`、
`/v10/config/email`、`/v10/config/cache`、`/v10/user/infos`、`/v10/i18n/list`、
`/v10/execute/log/type`、`/v10/user/config`

例外：`/v10/collect/solid` 报的是 `JWT String argument cannot be null or empty.`（不是权限问题，
是该接口要另带 JWT），未继续深挖。

## 复现

```bash
# 路由清单（需 javap）：输出 /tmp/routes.json → 整理成 REST路由清单.md
python3 <开发工作目录>/route_dump.py && python3 <开发工作目录>/route_report.py
# 只读可达性探测（只发 GET）
PYTHONPATH=src python3 <开发工作目录>/probe_readonly_routes.py
# 自动补必填参数重试
PYTHONPATH=src python3 <开发工作目录>/probe_required_params.py
```
