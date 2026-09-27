# 远程设计 RPC 服务清单（28 个 · 全量签名）

> 决策平台 `/decision/remote/design/channel` 是**通用反射网关**：给「类名 + 方法名 + 参数类型」
> 就在服务端执行（`Class.forName(...).getDeclaredMethod(...)` → `FineObjectPool` 取实例 invoke）。
> 可调类清单来自 `POST /decision/remote/design/service`（本服务器实测 28 个），
> 方法签名取自实测环境 FineReport 安装包的 `javap -p`（服务端同版本 10.0.19）。

| 项 | 值 |
|---|---|
| 服务类数 | 28 |
| 方法总数 | 150 |
| 签名来源 | `<FineReport 安装目录>` 的 jar |
| 生成时间 | 2026-09-27 17:59:46 |
| 重新生成 | `FINEREPORT_HOME=<安装目录> python -m frcli.rpc_catalog` |
| 调用入口 | `frcli rpc services` / `frcli rpc methods <类>` / `frcli rpc call <类> <方法> --arg ...` |

「可直接调」= 只读且参数全是标量类型（`rpc call` 现在就能调）。

**策略分布**（`rpc methods` 的 policy 列）：🟢 read 91 · 🔴 write 18 · ⛔ deny 41。deny 是**永远拒绝**（平台配置写/权限写/密钥读），加 `--yes` 也不放行。

## 0. 用之前先看三条

1. **路径口径**：`WorkResource` / `TplOperator` / `VcsOperator` 收的是**工作区路径**，
   即 `reportlets/demo_group/demo_user/xxx.cpt`；`report list` 给的是展示路径
   （`demo_group/demo_user/xxx.cpt`，**没有** `reportlets/` 前缀）。用错前缀不会报错，
   只会返回空目录或空字节 —— 这是最容易误判「没权限」的地方。
2. **写范围**：写语义方法必须 `--yes`，且每个路径参数都要落在写范围内
   （`$FRCLI_WRITE_SCOPE`，未设时默认 `reportlets/demo_group/demo_user/skill测试`）。
   没有可检查路径参数的写方法**一律拒绝**（无法验证范围 = 不放行）。
3. **线上类版本可能与安装包内的 jar 不同**：实测 `CommonOperator.getContextName()` 在安装包内的 jar 里有、
   线上没有 → 调它返回 `java.lang.NoSuchMethodException: ...getContextName()`。
   看到这个异常就是版本差异，不是调用姿势错。

## 1. 服务总览

| 服务类 | jar | 类型 | 方法 | 可直接调 | 一句话用途 |
|---|---|---|---|---|---|
| `com.fr.analysis.cloud.solid.SolidRecordExecutor` | `WEB-INF/lib/fine-core-10.0.jar` | interface | 10 | 2 | 云端分析「固化记录」执行器：维护需固化的报表任务与本地固化文件。 |
| `com.fr.base.io.FileAssistUtilsOperator` | `WEB-INF/lib/fine-core-10.0.jar` | interface | 1 | 0 | 文件回收站助手（把文件移入回收站，可恢复）。 |
| `com.fr.base.operator.common.CommonOperator` | `WEB-INF/lib/fine-core-10.0.jar` | interface | 20 | 13 | 服务端通用信息 + 插件运维：许可证名、webroot 路径、上下文名、插件状态、模板是否被锁；另有插件服务启停/编译 Java/REU 安装（一律 deny）。 |
| `com.fr.base.operator.org.OrganizationOperator` | `WEB-INF/lib/fine-core-10.0.jar` | interface | 3 | 3 | 组织维度清单：角色组、数据连接组，以及 `canAccess(path)` 判断当前账号能否访问某路径。 |
| `com.fr.base.rpc.encrypt.EncryptOperator` | `WEB-INF/lib/fine-report-engine-10.0.jar` | interface | 1 | 0 | 读 RPC 传输密钥 —— **永远 deny**。 |
| `com.fr.cluster.engine.rpc.remote.ClusterOperator` | `WEB-INF/lib/fine-core-10.0.jar` | interface | 1 | 1 | `isCluster()`：是否集群部署。 |
| `com.fr.config.dao.CommitHelper` | `WEB-INF/lib/fine-core-10.0.jar` | interface | 1 | 0 | 提交平台配置变更 —— **永远 deny**（本工具绝不写平台配置）。 |
| `com.fr.config.dao.DataFetcher` | `WEB-INF/lib/fine-core-10.0.jar` | interface | 1 | 0 | 按实体类读平台配置（`getConfig(Class,String)`）。参数是 `Class` 对象，当前编码器不支持 → 实际不可调。 |
| `com.fr.data.operator.DataOperatorProvider` | `WEB-INF/lib/fine-core-10.0.jar` | interface | 18 | 3 | 数据集/数据连接侧能力：建连测试、表结构·字段·存储过程元数据、数据集预览。可调 `getColumns(连接名, schema, 表名)`、`getProcedureText`、`getStoreProcedureDeclarationParameters`（纯字符串）；其余都需要 `Connection`/`TableData` 对象参数 → 当前不可调。 |
| `com.fr.esd.core.remote.ESDConfigEventOperator` | `plugins/plugin-com.fr.plugin.esd-1.8.4/fr-plugin-esd-1.8.4.jar` | interface | 2 | 0 | 触发决策平台事件总线 —— **永远 deny**。 |
| `com.fr.file.filetree.FileNodes` | `WEB-INF/lib/fine-core-10.0.jar` | interface | 11 | 4 | 模板文件树（结构化 `FileNode[]`，含类型信息，比 `WorkResource.list` 丰富）。可调 `getSupportedTypes()` / `list(String)` / `list(String, boolean)` / `listWebRootFile(String)`；其余重载要 `FileExtension` 对象。 |
| `com.fr.form.share.ShareComponentOperator` | `WEB-INF/lib/fine-report-engine-10.0.jar` | interface | 4 | 1 | 共享组件库（复用组件）：`getSharePath` 只读；安装/删除组件 deny。 |
| `com.fr.form.share.ShareEmbeddedConverter` | `WEB-INF/lib/fine-report-engine-10.0.jar` | interface | 1 | 0 | 把共享数据集转成内嵌 `TableData`（要对象参数，不可调）。 |
| `com.fr.plugin.cloud.analytics.collect.rpc.RPCDataCollector` | `WEB-INF/plugins/plugin-com.fr.plugin.cloud.analytics.v10-2.14.0.20230222/fr-plugin-cloud-analytics-2.14.0.20230222.jar` | interface | 1 | 0 | 云端分析数据上报 —— **永远 deny**。 |
| `com.fr.plugin.weixin.server.rpc.WeiXinRPCOperator` | `plugins/plugin-com.fr.plugin.weixin-10.5.20/fr-plugin-weixin-10.5.20.jar` | interface | 1 | 1 | `getAgents()`：移动端/微信集成里配置的应用代理清单。 |
| `com.fr.security.encryption.storage.StorageTransfer` | `WEB-INF/lib/fine-core-10.0.jar` | interface | 7 | 1 | 平台存储加解密（数据连接密码等敏感字段）。只放行 `getCurrentEncryptionMode`；`encrypt/decrypt/getCurrentSecurityKeys` **永远 deny**。 |
| `com.fr.workspace.engine.client.heartbeart.WorkspaceHeartbeat` | `WEB-INF/lib/fine-core-10.0.jar` | interface | 5 | 1 | 远程设计心跳：`getInterval()` 只读；start/stop/beat/close deny。 |
| `com.fr.workspace.resource.WorkResource` | `WEB-INF/lib/fine-core-10.0.jar` | interface | 14 | 7 | **核心**：服务端 WEB-INF 远程文件系统。读 `readFully`/`list`/`exist`/`length`/`lastModified`/`isDirectory`/`openStream`；写 `write`/`createFile`/`createDirectory`/`delete`/`rename`/`save`。 |
| `com.fr.workspace.server.authority.AuthorityOperator` | `WEB-INF/lib/fine-report-engine-10.0.jar` | interface | 7 | 5 | 远程设计授权：当前账号授权目录 `getUserAuthorities()`、`hasAuthority(path)`、`findWithTotalCount(QueryCondition)`（要对象参数）；`updateAuthorities` deny。 |
| `com.fr.workspace.server.authority.decision.DecisionOperator` | `WEB-INF/lib/fine-report-engine-10.0.jar` | interface | 6 | 6 | 远程设计成员与自定义角色：`getMembers`/`getCustoms`（两两重载，分页版要 int）、`getUserIdByName`、`isRoot`。 |
| `com.fr.workspace.server.check.TemplateChecker` | `WEB-INF/lib/fine-report-engine-10.0.jar` | interface | 1 | 1 | `checkFont(path)`：模板里用到但服务端缺失的字体（返回 Set，空集 = 没问题）。 |
| `com.fr.workspace.server.check.VersionInfoOperator` | `WEB-INF/lib/fine-report-engine-10.0.jar` | interface | 1 | 1 | `getFullBuildNO()`：服务端完整构建号（比 `system version` 的 jarTime 更细）。 |
| `com.fr.workspace.server.connection.DBConnectAuth` | `WEB-INF/lib/fine-report-engine-10.0.jar` | interface | 1 | 1 | `getNoAuthConnections()`：当前账号无权限的数据连接名单。 |
| `com.fr.workspace.server.exporter.TemplateExportOperator` | `WEB-INF/lib/fine-report-engine-10.0.jar` | interface | 5 | 3 | 服务端导出：`exportWorkBookAsImageData(path)` / `exportFormAsImageData(path)` 直接返回图片字节（默认方法，实测可调）；`export(...)` 要 `ExporterKey`/`OutputStream` 对象。 |
| `com.fr.workspace.server.lock.TplOperator` | `WEB-INF/lib/fine-report-engine-10.0.jar` | interface | 7 | 0 | 模板编辑锁与保存：`readAndLockFile`（占锁并返回现有内容）、`closeAndFreeFile`、`saveAs`、`rename`、`delete`（移入回收站）、`userIn`/`userOut`。全部写语义，受写范围守门。 |
| `com.fr.workspace.server.lock.editlock.EditLockOperator` | `WEB-INF/lib/fine-report-engine-10.0.jar` | interface | 3 | 0 | 单元格级编辑锁，参数是 `LockItem` 对象 → 当前不可调。 |
| `com.fr.workspace.server.socket.SocketInfoOperator` | `WEB-INF/lib/fine-report-engine-10.0.jar` | interface | 1 | 1 | `getPort()`：节点端口清单。 |
| `com.fr.workspace.server.vcs.VcsOperator` | `WEB-INF/lib/fine-report-engine-10.0.jar` | interface | 16 | 6 | **模板版本库**：`getVersions(path)` 历史版本、`getFileOfFileVersion(path, idx)` 取指定版本内容、`getFileOfCurrent(path)` 服务端当前版本缓存路径、（要 Date/对象参数的另说）。提交/回滚/删版本 **永远 deny**。 |

## 2. 逐服务完整签名

### `com.fr.analysis.cloud.solid.SolidRecordExecutor`

- **jar**：`webapps/webroot/WEB-INF/lib/fine-core-10.0.jar`　**类型**：interface　**方法**：10
- **用途**：云端分析「固化记录」执行器：维护需固化的报表任务与本地固化文件。

| 策略 | 签名 |
|---|---|
| ⛔ deny | `java.lang.String feedBackTask(java.lang.String)` |
| ⛔ deny | `void saveByManual(java.lang.String)` |
| ⛔ deny | `void deleteSolidFile()` |
| ⛔ deny | `void unlockSolidFile()` |
| ⛔ deny | `void restart()` |
| ⛔ deny | `void clean()` |
| ⛔ deny | `void addRecordTask(com.fr.analysis.cloud.solid.SolidRecordTask)` |
| ⛔ deny | `void removeRecordTask(java.lang.String)` |
| 🟢 read | `boolean checkRecordTaskExist(java.lang.String)` |
| 🟢 read | `java.util.Collection<com.fr.analysis.cloud.solid.SolidRecordTask> getRecordTask()` |

### `com.fr.base.io.FileAssistUtilsOperator`

- **jar**：`webapps/webroot/WEB-INF/lib/fine-core-10.0.jar`　**类型**：interface　**方法**：1
- **用途**：文件回收站助手（把文件移入回收站，可恢复）。

| 策略 | 签名 |
|---|---|
| 🔴 write | `boolean moveToTrash(java.lang.String)` |

### `com.fr.base.operator.common.CommonOperator`

- **jar**：`webapps/webroot/WEB-INF/lib/fine-core-10.0.jar`　**类型**：interface　**方法**：20
- **用途**：服务端通用信息 + 插件运维：许可证名、webroot 路径、上下文名、插件状态、模板是否被锁；另有插件服务启停/编译 Java/REU 安装（一律 deny）。

| 策略 | 签名 |
|---|---|
| ⛔ deny | `java.lang.String pluginServiceAction(java.lang.String, java.lang.String)` |
| ⛔ deny | `void pluginServiceStart(java.lang.String)` |
| ⛔ deny | `com.fr.stable.JavaCompileInfo compile(java.lang.String)` |
| 🟢 read | `java.lang.String getLicenseName()` |
| 🟢 read | `boolean hasPluginServiceStarted(java.lang.String)` |
| 🟢 read | `java.lang.String[] loadREUFile()` |
| ⛔ deny | `boolean installREUFile(java.io.File)` |
| ⛔ deny | `boolean removeREUFilesByName(java.lang.String)` |
| 🟢 read | `java.lang.String getSharePath()` |
| 🟢 read | `com.fr.json.JSONArray getPluginStatus()` |
| 🟢 read | `java.lang.String getDefaultSolutionTip()` |
| 🟢 read | `java.lang.String getWebRootPath()` |
| ⛔ deny | `boolean writeSvgFile(com.fr.stable.SvgProvider)` |
| 🟢 read | `java.lang.String[] readPathSvgFiles(java.lang.String)` |
| 🔴 write | `void unlockTemplate(java.lang.String)` |
| 🟢 read | `boolean fileLocked(java.lang.String)` |
| 🟢 read | `java.lang.String getAppName()` |
| 🟢 read | `java.lang.String getContextName()` |
| 🟢 read | `java.lang.String getDesignerVersion()` |
| 🟢 read | `boolean isWarDeploy()` |

### `com.fr.base.operator.org.OrganizationOperator`

- **jar**：`webapps/webroot/WEB-INF/lib/fine-core-10.0.jar`　**类型**：interface　**方法**：3
- **用途**：组织维度清单：角色组、数据连接组，以及 `canAccess(path)` 判断当前账号能否访问某路径。

| 策略 | 签名 |
|---|---|
| 🟢 read | `java.lang.String[] getRoleGroup()` |
| 🟢 read | `java.lang.String[] getConnectionGroup()` |
| 🟢 read | `boolean canAccess(java.lang.String)` |

### `com.fr.base.rpc.encrypt.EncryptOperator`

- **jar**：`webapps/webroot/WEB-INF/lib/fine-report-engine-10.0.jar`　**类型**：interface　**方法**：1
- **用途**：读 RPC 传输密钥 —— **永远 deny**。

| 策略 | 签名 |
|---|---|
| ⛔ deny | `java.lang.String readKey()` |

### `com.fr.cluster.engine.rpc.remote.ClusterOperator`

- **jar**：`webapps/webroot/WEB-INF/lib/fine-core-10.0.jar`　**类型**：interface　**方法**：1
- **用途**：`isCluster()`：是否集群部署。

| 策略 | 签名 |
|---|---|
| 🟢 read | `boolean isCluster()` |

### `com.fr.config.dao.CommitHelper`

- **jar**：`webapps/webroot/WEB-INF/lib/fine-core-10.0.jar`　**类型**：interface　**方法**：1
- **用途**：提交平台配置变更 —— **永远 deny**（本工具绝不写平台配置）。

| 策略 | 签名 |
|---|---|
| ⛔ deny | `boolean commit(java.util.List)` |

### `com.fr.config.dao.DataFetcher`

- **jar**：`webapps/webroot/WEB-INF/lib/fine-core-10.0.jar`　**类型**：interface　**方法**：1
- **用途**：按实体类读平台配置（`getConfig(Class,String)`）。参数是 `Class` 对象，当前编码器不支持 → 实际不可调。

| 策略 | 签名 |
|---|---|
| 🟢 read | `java.util.List<T> getConfig(java.lang.Class, java.lang.String)` |

### `com.fr.data.operator.DataOperatorProvider`

- **jar**：`webapps/webroot/WEB-INF/lib/fine-core-10.0.jar`　**类型**：interface　**方法**：18
- **用途**：数据集/数据连接侧能力：建连测试、表结构·字段·存储过程元数据、数据集预览。可调 `getColumns(连接名, schema, 表名)`、`getProcedureText`、`getStoreProcedureDeclarationParameters`（纯字符串）；其余都需要 `Connection`/`TableData` 对象参数 → 当前不可调。

| 策略 | 签名 |
|---|---|
| 🟢 read | `boolean testConnection(com.fr.data.impl.Connection)` |
| 🟢 read | `void validateConnectionSettings(com.fr.data.impl.Connection)` |
| 🟢 read | `void testConnectionWithException(com.fr.data.impl.Connection)` |
| 🟢 read | `java.lang.String[] getTableSchema(com.fr.data.impl.Connection)` |
| 🟢 read | `java.lang.String[] getTableSummary(com.fr.data.impl.Connection, java.lang.String...)` |
| 🟢 read | `java.util.List<com.fr.data.core.db.TableProcedure[]> getProcedures(com.fr.data.impl.Connection, java.lang.String[], boolean, boolean)` |
| 🟢 read | `com.fr.data.core.db.TableProcedure[] getTableProcedure(com.fr.data.impl.Connection, java.lang.String, java.lang.String)` |
| 🟢 read | `com.fr.data.impl.EmbeddedTableData previewTableData(com.fr.base.TableData, java.util.Map, int)` |
| 🟢 read | `com.fr.base.TableData previewTableData(com.fr.base.TableData, java.util.Map, int, int, java.lang.String[], int[])` |
| 🟢 read | `com.fr.stable.ParameterProvider[] getTableDataParameters(com.fr.base.TableData)` |
| 🟢 read | `com.fr.stable.ParameterProvider[] getStoreProcedureParameters(com.fr.data.impl.storeproc.StoreProcedure)` |
| 🟢 read | `com.fr.data.impl.EmbeddedTableData previewTableData(com.fr.data.TableDataSource, java.lang.Object, java.util.Map, int)` |
| 🟢 read | `com.fr.data.impl.EmbeddedTableData previewTableData(com.fr.data.TableDataSource, java.lang.Object, java.util.Map, int, int, java.lang.String[], int[])` |
| 🟢 read | `java.lang.String[] getColumns(java.lang.String, java.lang.String, java.lang.String)` |
| 🟢 read | `java.lang.String getProcedureText(java.lang.String, java.lang.String)` |
| 🟢 read | `com.fr.base.StoreProcedureParameter[] getStoreProcedureDeclarationParameters(java.lang.String, java.lang.String, java.lang.String)` |
| 🟢 read | `com.fr.data.impl.storeproc.ProcedureDataModel[] previewProcedureDataModel(com.fr.data.impl.storeproc.StoreProcedure, java.util.Map, int)` |
| 🟢 read | `com.fr.data.core.db.dialect.base.key.check.DataBaseDetail getDataBaseDetail(com.fr.data.impl.Connection, boolean)` |

### `com.fr.esd.core.remote.ESDConfigEventOperator`

- **jar**：`plugins/plugin-com.fr.plugin.esd-1.8.4/fr-plugin-esd-1.8.4.jar`　**类型**：interface　**方法**：2
- **用途**：触发决策平台事件总线 —— **永远 deny**。

| 策略 | 签名 |
|---|---|
| ⛔ deny | `void fire(java.lang.String, byte[])` |
| ⛔ deny | `void fire(com.fr.esd.event.StrategyEvent, com.fr.esd.event.DSMapping...)` |

### `com.fr.file.filetree.FileNodes`

- **jar**：`webapps/webroot/WEB-INF/lib/fine-core-10.0.jar`　**类型**：interface　**方法**：11
- **用途**：模板文件树（结构化 `FileNode[]`，含类型信息，比 `WorkResource.list` 丰富）。可调 `getSupportedTypes()` / `list(String)` / `list(String, boolean)` / `listWebRootFile(String)`；其余重载要 `FileExtension` 对象。

| 策略 | 签名 |
|---|---|
| 🟢 read | `java.lang.String[] getSupportedTypes()` |
| 🟢 read | `com.fr.file.filetree.FileNode[] list(java.lang.String)` |
| 🟢 read | `com.fr.file.filetree.FileNode[] list(java.lang.String, boolean)` |
| 🟢 read | `com.fr.file.filetree.FileNode[] listWebRootFile(java.lang.String)` |
| 🟢 read | `com.fr.file.filetree.FileNode[] list(java.lang.String, com.fr.base.extension.FileExtension)` |
| 🟢 read | `com.fr.file.filetree.FileNode[] list(java.lang.String, com.fr.base.extension.FileExtension[])` |
| 🟢 read | `com.fr.file.filetree.FileNode[] list(java.lang.String, com.fr.base.extension.FileExtension, boolean)` |
| 🟢 read | `com.fr.file.filetree.FileNode[] list(java.lang.String, com.fr.base.extension.FileExtension[], boolean)` |
| 🟢 read | `com.fr.file.filetree.FileNode[] list(java.lang.String, com.fr.base.extension.FileExtension[], boolean, boolean)` |
| 🟢 read | `com.fr.file.filetree.FileNode[] filterFiles(java.lang.String, java.lang.String, com.fr.base.extension.FileExtension[], boolean)` |
| 🟢 read | `com.fr.file.filetree.FileNode[] filterFiles(java.lang.String, java.lang.String, com.fr.base.extension.FileExtension[], boolean, boolean)` |

### `com.fr.form.share.ShareComponentOperator`

- **jar**：`webapps/webroot/WEB-INF/lib/fine-report-engine-10.0.jar`　**类型**：interface　**方法**：4
- **用途**：共享组件库（复用组件）：`getSharePath` 只读；安装/删除组件 deny。

| 策略 | 签名 |
|---|---|
| 🔴 write | `java.lang.String[] cacheComponents(com.fr.form.share.Group)` |
| ⛔ deny | `boolean installComponent(com.fr.form.share.Group, java.lang.String, byte[])` |
| ⛔ deny | `boolean removeComponent(com.fr.form.share.Group, java.lang.String)` |
| 🟢 read | `java.lang.String getSharePath()` |

### `com.fr.form.share.ShareEmbeddedConverter`

- **jar**：`webapps/webroot/WEB-INF/lib/fine-report-engine-10.0.jar`　**类型**：interface　**方法**：1
- **用途**：把共享数据集转成内嵌 `TableData`（要对象参数，不可调）。

| 策略 | 签名 |
|---|---|
| 🟢 read | `java.util.Map<java.lang.String, com.fr.base.TableData> convertToEmbeddedTableData(com.fr.data.TableDataSource, java.util.Map)` |

### `com.fr.plugin.cloud.analytics.collect.rpc.RPCDataCollector`

- **jar**：`webapps/webroot/WEB-INF/plugins/plugin-com.fr.plugin.cloud.analytics.v10-2.14.0.20230222/fr-plugin-cloud-analytics-2.14.0.20230222.jar`　**类型**：interface　**方法**：1
- **用途**：云端分析数据上报 —— **永远 deny**。

| 策略 | 签名 |
|---|---|
| ⛔ deny | `void submit(T)` |

### `com.fr.plugin.weixin.server.rpc.WeiXinRPCOperator`

- **jar**：`plugins/plugin-com.fr.plugin.weixin-10.5.20/fr-plugin-weixin-10.5.20.jar`　**类型**：interface　**方法**：1
- **用途**：`getAgents()`：移动端/微信集成里配置的应用代理清单。

| 策略 | 签名 |
|---|---|
| 🟢 read | `java.util.List<? extends com.fr.plugin.mobile.base.oa.bean.BaseAgent<?>> getAgents()` |

### `com.fr.security.encryption.storage.StorageTransfer`

- **jar**：`webapps/webroot/WEB-INF/lib/fine-core-10.0.jar`　**类型**：interface　**方法**：7
- **用途**：平台存储加解密（数据连接密码等敏感字段）。只放行 `getCurrentEncryptionMode`；`encrypt/decrypt/getCurrentSecurityKeys` **永远 deny**。

| 策略 | 签名 |
|---|---|
| ⛔ deny | `java.lang.String encrypt(java.lang.String)` |
| ⛔ deny | `java.lang.String decrypt(java.lang.String)` |
| ⛔ deny | `java.lang.String encrypt(java.lang.String, java.lang.String)` |
| ⛔ deny | `java.lang.String decrypt(java.lang.String, java.lang.String)` |
| ⛔ deny | `void setCurrentEncryptionMode(com.fr.security.encryption.mode.EncryptionMode)` |
| 🟢 read | `com.fr.security.encryption.mode.EncryptionMode getCurrentEncryptionMode()` |
| ⛔ deny | `com.fr.security.encryption.storage.keys.SecurityKeys getCurrentSecurityKeys()` |

### `com.fr.workspace.engine.client.heartbeart.WorkspaceHeartbeat`

- **jar**：`webapps/webroot/WEB-INF/lib/fine-core-10.0.jar`　**类型**：interface　**方法**：5
- **用途**：远程设计心跳：`getInterval()` 只读；start/stop/beat/close deny。

| 策略 | 签名 |
|---|---|
| ⛔ deny | `void start()` |
| ⛔ deny | `void stop()` |
| 🟢 read | `int getInterval()` |
| ⛔ deny | `void beat(com.fr.workspace.connect.WorkspaceConnection)` |
| ⛔ deny | `void close(com.fr.workspace.connect.WorkspaceConnection)` |

### `com.fr.workspace.resource.WorkResource`

- **jar**：`webapps/webroot/WEB-INF/lib/fine-core-10.0.jar`　**类型**：interface　**方法**：14
- **用途**：**核心**：服务端 WEB-INF 远程文件系统。读 `readFully`/`list`/`exist`/`length`/`lastModified`/`isDirectory`/`openStream`；写 `write`/`createFile`/`createDirectory`/`delete`/`rename`/`save`。

| 策略 | 签名 |
|---|---|
| 🟢 read | `byte[] readFully(java.lang.String)` |
| 🟢 read | `java.io.InputStream openStream(java.lang.String)` |
| 🔴 write | `void write(java.lang.String, byte[])` |
| 🔴 write | `boolean createFile(java.lang.String)` |
| 🔴 write | `boolean createDirectory(java.lang.String)` |
| 🔴 write | `boolean delete(java.lang.String)` |
| 🔴 write | `boolean rename(java.lang.String, java.lang.String)` |
| 🟢 read | `boolean exist(java.lang.String)` |
| 🟢 read | `java.lang.String[] list(java.lang.String)` |
| 🟢 read | `java.lang.String[] list(java.lang.String, com.fr.stable.Filter)` |
| 🟢 read | `boolean isDirectory(java.lang.String)` |
| 🟢 read | `long lastModified(java.lang.String)` |
| 🟢 read | `long length(java.lang.String)` |
| 🔴 write | `default void save(java.lang.String, java.lang.String, byte[])` |

### `com.fr.workspace.server.authority.AuthorityOperator`

- **jar**：`webapps/webroot/WEB-INF/lib/fine-report-engine-10.0.jar`　**类型**：interface　**方法**：7
- **用途**：远程设计授权：当前账号授权目录 `getUserAuthorities()`、`hasAuthority(path)`、`findWithTotalCount(QueryCondition)`（要对象参数）；`updateAuthorities` deny。

| 策略 | 签名 |
|---|---|
| 🟢 read | `com.fr.report.DesignAuthority[] getAuthorities(java.lang.String)` |
| 🟢 read | `com.fr.report.DesignAuthority[] getCustomRoleAuthorities()` |
| 🟢 read | `com.fr.report.DesignAuthority[] getUserAuthorities()` |
| 🟢 read | `boolean hasAuthority(java.lang.String)` |
| 🟢 read | `com.fr.report.DesignAuthority[] getAuthorities()` |
| ⛔ deny | `boolean updateAuthorities(com.fr.report.DesignAuthority[])` |
| 🟢 read | `com.fr.stable.query.data.DataList<com.fr.report.data.RemoteDesignAuthority> findWithTotalCount(com.fr.stable.query.condition.QueryCondition)` |

### `com.fr.workspace.server.authority.decision.DecisionOperator`

- **jar**：`webapps/webroot/WEB-INF/lib/fine-report-engine-10.0.jar`　**类型**：interface　**方法**：6
- **用途**：远程设计成员与自定义角色：`getMembers`/`getCustoms`（两两重载，分页版要 int）、`getUserIdByName`、`isRoot`。

| 策略 | 签名 |
|---|---|
| 🟢 read | `java.util.Collection<com.fr.workspace.server.authority.RemoteDesignMember> getMembers(java.lang.String, java.lang.String)` |
| 🟢 read | `java.util.Collection<com.fr.workspace.server.authority.RemoteDesignMember> getMembers(java.lang.String, java.lang.String, int, int)` |
| 🟢 read | `java.util.Collection<com.fr.workspace.server.authority.RemoteDesignMember> getCustoms(java.lang.String, java.lang.String)` |
| 🟢 read | `java.util.Collection<com.fr.workspace.server.authority.RemoteDesignMember> getCustoms(java.lang.String, java.lang.String, int, int)` |
| 🟢 read | `java.lang.String getUserIdByName(java.lang.String)` |
| 🟢 read | `boolean isRoot(java.lang.String)` |

### `com.fr.workspace.server.check.TemplateChecker`

- **jar**：`webapps/webroot/WEB-INF/lib/fine-report-engine-10.0.jar`　**类型**：interface　**方法**：1
- **用途**：`checkFont(path)`：模板里用到但服务端缺失的字体（返回 Set，空集 = 没问题）。

| 策略 | 签名 |
|---|---|
| 🟢 read | `java.util.Set<java.lang.String> checkFont(java.lang.String)` |

### `com.fr.workspace.server.check.VersionInfoOperator`

- **jar**：`webapps/webroot/WEB-INF/lib/fine-report-engine-10.0.jar`　**类型**：interface　**方法**：1
- **用途**：`getFullBuildNO()`：服务端完整构建号（比 `system version` 的 jarTime 更细）。

| 策略 | 签名 |
|---|---|
| 🟢 read | `java.lang.String getFullBuildNO()` |

### `com.fr.workspace.server.connection.DBConnectAuth`

- **jar**：`webapps/webroot/WEB-INF/lib/fine-report-engine-10.0.jar`　**类型**：interface　**方法**：1
- **用途**：`getNoAuthConnections()`：当前账号无权限的数据连接名单。

| 策略 | 签名 |
|---|---|
| 🟢 read | `java.util.Collection<java.lang.String> getNoAuthConnections()` |

### `com.fr.workspace.server.exporter.TemplateExportOperator`

- **jar**：`webapps/webroot/WEB-INF/lib/fine-report-engine-10.0.jar`　**类型**：interface　**方法**：5
- **用途**：服务端导出：`exportWorkBookAsImageData(path)` / `exportFormAsImageData(path)` 直接返回图片字节（默认方法，实测可调）；`export(...)` 要 `ExporterKey`/`OutputStream` 对象。

| 策略 | 签名 |
|---|---|
| 🟢 read | `byte[] export(com.fr.io.exporter.ExporterKey, com.fr.io.exporter.DesignExportType, java.io.OutputStream, java.lang.String, java.util.Map)` |
| 🟢 read | `default byte[] exportFormAsImageData(java.lang.String)` |
| 🟢 read | `default byte[] exportWorkBookAsImageData(java.lang.String)` |
| 🟢 read | `static byte[] imageToByteData(java.awt.image.BufferedImage)` |
| 🟢 read | `static java.awt.image.BufferedImage byteDataToImage(byte[])` |

### `com.fr.workspace.server.lock.TplOperator`

- **jar**：`webapps/webroot/WEB-INF/lib/fine-report-engine-10.0.jar`　**类型**：interface　**方法**：7
- **用途**：模板编辑锁与保存：`readAndLockFile`（占锁并返回现有内容）、`closeAndFreeFile`、`saveAs`、`rename`、`delete`（移入回收站）、`userIn`/`userOut`。全部写语义，受写范围守门。

| 策略 | 签名 |
|---|---|
| 🔴 write | `byte[] readAndLockFile(java.lang.String)` |
| 🔴 write | `boolean closeAndFreeFile(java.lang.String)` |
| 🔴 write | `boolean rename(java.lang.String, java.lang.String)` |
| 🔴 write | `boolean saveAs(java.lang.String)` |
| 🔴 write | `boolean delete(java.lang.String)` |
| 🔴 write | `boolean userOut(java.lang.String)` |
| 🔴 write | `boolean userIn(java.lang.String)` |

### `com.fr.workspace.server.lock.editlock.EditLockOperator`

- **jar**：`webapps/webroot/WEB-INF/lib/fine-report-engine-10.0.jar`　**类型**：interface　**方法**：3
- **用途**：单元格级编辑锁，参数是 `LockItem` 对象 → 当前不可调。

| 策略 | 签名 |
|---|---|
| 🔴 write | `boolean lock(com.fr.report.LockItem)` |
| 🔴 write | `boolean unlock(com.fr.report.LockItem)` |
| 🟢 read | `boolean isLocked(com.fr.report.LockItem)` |

### `com.fr.workspace.server.socket.SocketInfoOperator`

- **jar**：`webapps/webroot/WEB-INF/lib/fine-report-engine-10.0.jar`　**类型**：interface　**方法**：1
- **用途**：`getPort()`：节点端口清单。

| 策略 | 签名 |
|---|---|
| 🟢 read | `java.lang.Integer[] getPort()` |

### `com.fr.workspace.server.vcs.VcsOperator`

- **jar**：`webapps/webroot/WEB-INF/lib/fine-report-engine-10.0.jar`　**类型**：interface　**方法**：16
- **用途**：**模板版本库**：`getVersions(path)` 历史版本、`getFileOfFileVersion(path, idx)` 取指定版本内容、`getFileOfCurrent(path)` 服务端当前版本缓存路径、（要 Date/对象参数的另说）。提交/回滚/删版本 **永远 deny**。

| 策略 | 签名 |
|---|---|
| 🟢 read | `java.util.List<com.fr.report.entity.VcsEntity> getVersions(java.lang.String)` |
| 🟢 read | `java.util.List<com.fr.report.entity.VcsEntity> getFilterVersions(java.lang.String, java.util.Date, java.util.Date, java.lang.String)` |
| 🟢 read | `com.fr.report.entity.VcsEntity getFileVersionByIndexAndUsername(java.lang.String, java.lang.String, int)` |
| 🟢 read | `com.fr.report.entity.VcsEntity getFileVersionByIndex(java.lang.String, int)` |
| 🟢 read | `com.fr.report.entity.VcsEntity getFileVersion(java.lang.String, int)` |
| ⛔ deny | `void updateVersion(com.fr.report.entity.VcsEntity)` |
| ⛔ deny | `com.fr.report.entity.VcsEntity saveVersion(java.lang.String, java.lang.String, java.lang.String)` |
| ⛔ deny | `com.fr.report.entity.VcsEntity saveVersion(java.lang.String, java.lang.String, java.lang.String, int)` |
| ⛔ deny | `com.fr.report.entity.VcsEntity saveVersionFromCache(java.lang.String, java.lang.String, java.lang.String, int)` |
| ⛔ deny | `void rollbackTo(com.fr.report.entity.VcsEntity)` |
| 🟢 read | `java.lang.String getFileOfFileVersion(java.lang.String, int)` |
| 🟢 read | `java.lang.String getFileOfCurrent(java.lang.String)` |
| ⛔ deny | `void deleteVersion(java.lang.String, int)` |
| ⛔ deny | `void moveVscFolder()` |
| ⛔ deny | `boolean gc()` |
| ⛔ deny | `long immediatelyGc()` |

## 3. 现在就能 `rpc call` 的只读方法（无需任何对象参数）

```bash
frcli rpc call SolidRecordExecutor checkRecordTaskExist --arg "<工作区路径或名字>"
frcli rpc call SolidRecordExecutor getRecordTask
frcli rpc call CommonOperator getLicenseName
frcli rpc call CommonOperator hasPluginServiceStarted --arg "<工作区路径或名字>"
frcli rpc call CommonOperator loadREUFile
frcli rpc call CommonOperator getSharePath
frcli rpc call CommonOperator getPluginStatus
frcli rpc call CommonOperator getDefaultSolutionTip
frcli rpc call CommonOperator getWebRootPath
frcli rpc call CommonOperator readPathSvgFiles --arg "<工作区路径或名字>"
frcli rpc call CommonOperator fileLocked --arg "<工作区路径或名字>"
frcli rpc call CommonOperator getAppName
frcli rpc call CommonOperator getContextName
frcli rpc call CommonOperator getDesignerVersion
frcli rpc call CommonOperator isWarDeploy
frcli rpc call OrganizationOperator getRoleGroup
frcli rpc call OrganizationOperator getConnectionGroup
frcli rpc call OrganizationOperator canAccess --arg "<工作区路径或名字>"
frcli rpc call ClusterOperator isCluster
frcli rpc call DataOperatorProvider getColumns --arg "<工作区路径或名字>" --arg "<工作区路径或名字>" --arg "<工作区路径或名字>"
frcli rpc call DataOperatorProvider getProcedureText --arg "<工作区路径或名字>" --arg "<工作区路径或名字>"
frcli rpc call DataOperatorProvider getStoreProcedureDeclarationParameters --arg "<工作区路径或名字>" --arg "<工作区路径或名字>" --arg "<工作区路径或名字>"
frcli rpc call FileNodes getSupportedTypes
frcli rpc call FileNodes list --arg "<工作区路径或名字>"
frcli rpc call FileNodes list --arg "<工作区路径或名字>" --arg <boolean>
frcli rpc call FileNodes listWebRootFile --arg "<工作区路径或名字>"
frcli rpc call ShareComponentOperator getSharePath
frcli rpc call WeiXinRPCOperator getAgents
frcli rpc call StorageTransfer getCurrentEncryptionMode
frcli rpc call WorkspaceHeartbeat getInterval
frcli rpc call WorkResource readFully --arg "<工作区路径或名字>"
frcli rpc call WorkResource openStream --arg "<工作区路径或名字>"
frcli rpc call WorkResource exist --arg "<工作区路径或名字>"
frcli rpc call WorkResource list --arg "<工作区路径或名字>"
frcli rpc call WorkResource isDirectory --arg "<工作区路径或名字>"
frcli rpc call WorkResource lastModified --arg "<工作区路径或名字>"
frcli rpc call WorkResource length --arg "<工作区路径或名字>"
frcli rpc call AuthorityOperator getAuthorities --arg "<工作区路径或名字>"
frcli rpc call AuthorityOperator getCustomRoleAuthorities
frcli rpc call AuthorityOperator getUserAuthorities
frcli rpc call AuthorityOperator hasAuthority --arg "<工作区路径或名字>"
frcli rpc call AuthorityOperator getAuthorities
frcli rpc call DecisionOperator getMembers --arg "<工作区路径或名字>" --arg "<工作区路径或名字>"
frcli rpc call DecisionOperator getMembers --arg "<工作区路径或名字>" --arg "<工作区路径或名字>" --arg <int> --arg <int>
frcli rpc call DecisionOperator getCustoms --arg "<工作区路径或名字>" --arg "<工作区路径或名字>"
frcli rpc call DecisionOperator getCustoms --arg "<工作区路径或名字>" --arg "<工作区路径或名字>" --arg <int> --arg <int>
frcli rpc call DecisionOperator getUserIdByName --arg "<工作区路径或名字>"
frcli rpc call DecisionOperator isRoot --arg "<工作区路径或名字>"
frcli rpc call TemplateChecker checkFont --arg "<工作区路径或名字>"
frcli rpc call VersionInfoOperator getFullBuildNO
frcli rpc call DBConnectAuth getNoAuthConnections
frcli rpc call TemplateExportOperator exportFormAsImageData --arg "<工作区路径或名字>"
frcli rpc call TemplateExportOperator exportWorkBookAsImageData --arg "<工作区路径或名字>"
frcli rpc call TemplateExportOperator byteDataToImage --arg <byte[]>
frcli rpc call SocketInfoOperator getPort
frcli rpc call VcsOperator getVersions --arg "<工作区路径或名字>"
frcli rpc call VcsOperator getFileVersionByIndexAndUsername --arg "<工作区路径或名字>" --arg "<工作区路径或名字>" --arg <int>
frcli rpc call VcsOperator getFileVersionByIndex --arg "<工作区路径或名字>" --arg <int>
frcli rpc call VcsOperator getFileVersion --arg "<工作区路径或名字>" --arg <int>
frcli rpc call VcsOperator getFileOfFileVersion --arg "<工作区路径或名字>" --arg <int>
frcli rpc call VcsOperator getFileOfCurrent --arg "<工作区路径或名字>"
```

## 4. 挖到的三块「新能力」（T2 会封装成固定命令）

| 能力 | 方法 | 说明 |
|---|---|---|
| 模板版本历史 | `VcsOperator.getVersions(path)` / `getFileOfFileVersion(path, idx)` / `getFileOfCurrent(path)` | 服务端有 VCS 缓存（实测 `assets/vcs/cache/reportlets/...`），可看历史版本列表并取某一版内容。**只读**，提交/回滚/删版本永远 deny。 |
| 模板体检 | `TemplateChecker.checkFont(path)` | 返回模板用到但服务端缺失的字体集合。 |
| 服务端导出 | `TemplateExportOperator.exportWorkBookAsImageData(path)` | 默认方法，直接返回图片字节；与 `export image` 走 REST 是不同的实现路径。 |
| 远程设计授权自省 | `AuthorityOperator.getUserAuthorities()` / `hasAuthority(path)` | 直接问服务端「我能写哪些目录」，比试探式写入安全得多。 |
| 数据连接排障 | `DBConnectAuth.getNoAuthConnections()` / `OrganizationOperator.getConnectionGroup()` | 无权限的连接名单 / 全部连接组名。 |

## 5. 换 FineReport 版本后怎么复核

1. 拉线上清单：`frcli rpc services`（对照本文件 §1 的 28 个类，多一个少一个都会显式列出）。
2. 重新生成本地签名：`FINEREPORT_HOME=<安装目录> python -m frcli.rpc_catalog`。
3. 抽查签名是否与 `javap -p -cp <webroot>/WEB-INF/lib/*.jar <类>` 一致
   （`tests/test_rpc.py::test_generated_catalog_matches_javap_when_available` 会自动做这件事）。
4. 逐类试调最便宜的一个只读方法（如 `getLicenseName` / `isCluster` / `getInterval`），
   出现 `NoSuchMethodException` 说明该类的线上版本与安装包内的 jar 不同 —— 以**线上**为准。

## 6. 服务端权限语义（为什么写操作必须客户端自己守门）

`com.fr.workspace.server.ServerWorkResource` 的写方法前面才有 `RemoteDesignHelper.access(path)`：

```java
if (path.endsWith(".tmp")) path = path[:-4];
return !path.contains("reportlets") || checkAuth(path);   // checkAuth = 该账号的远程设计授权目录
```

- 路径**含 `reportlets`** → 查账号授权目录；**不含** → 直接放行；
- 不满足时 `write` **静默返回**（不抛异常、不写盘）→ 写完必须回读比对；
- `/channel` 网关本身**没有逐路径鉴权**（除 token 外），任意服务类都能反射调用 →
  平台配置写、权限写、密钥读这些「不是模板文件」的危险面，只能靠 `frcli` 的 deny 名单挡住。

## 7. 已知局限（明确不修，别当 bug）

1. **写守门是启发式的**：`assert_template_bytes` 只查前 600 字节有没有 `<WorkBook`，
   注释里出现该字符串也会放行。真正的边界是 `$FRCLI_WRITE_SCOPE` 沙箱 + 服务端授权，
   不在这里过度工程化。
2. **没有「模板体检」**：`TemplateChecker` 接口只有 `checkFont(String)` 一个方法
   （`javap -p` 证实），不存在坏数据集/缺参数预警之类的 `check()`。字体体检用
   `frcli report fonts`。
3. **非标量参数编不出来**：`Connection` / `TableData` / `LockItem` / `Class` 这类对象参数
   需要构造完整 Java 对象，`rpc call` 明确报错。受影响的方法在 §1 的「可直接调」列里
   已经扣掉（如 `DataOperatorProvider` 18 个方法只有 3 个能调）。
4. **签名是安装包内的 jar 的快照**：方法签名来自 FineReport 10.0.19 的 jar，
   **不是线上真值**。线上类版本可能不同 —— 实测 `CommonOperator.getContextName()`
   安装包内的 jar 里有、线上没有（`NoSuchMethodException`）。以线上试调结果为准。
5. **`getFileOfFileVersion` 拿不到历史版本内容**：实测只返回 VCS 缓存路径
   （`assets/vcs/cache/<展示路径>`，内容 = **当前**版本），历史版本的正文取不出来。
   `getVersions` / `getFileVersionByIndex` 的**元数据**（版本号/提交人/时间/commitCode）是准的。
