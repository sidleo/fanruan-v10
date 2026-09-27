"""远程设计 RPC 服务签名清单（**由 `python -m frcli.rpc_catalog` 生成，勿手改**）。

来源：`<FineReport 安装目录>` 的 jar（javap -p），生成时间 2026-09-27 17:59:46。
服务类清单来自 `/decision/remote/design/service`；签名为该版本 jar 的反解结果。
"""

from typing import NamedTuple


GENERATED_AT = '2026-09-27 17:59:46'
SOURCE_HOME = '<FineReport 安装目录>'


class M(NamedTuple):
    """一个方法：名字 / 返回类型 / 参数类型 / 标记(a=abstract d=default s=static)。"""

    name: str
    returns: str
    params: tuple
    flags: str


class Service(NamedTuple):
    jar: str
    kind: str
    methods: tuple


SERVICES = {
    'com.fr.analysis.cloud.solid.SolidRecordExecutor': Service(
        'webapps/webroot/WEB-INF/lib/fine-core-10.0.jar',
        'interface',
        (
            M('feedBackTask', 'java.lang.String', ('java.lang.String',), 'a'),
            M('saveByManual', 'void', ('java.lang.String',), 'a'),
            M('deleteSolidFile', 'void', (), 'a'),
            M('unlockSolidFile', 'void', (), 'a'),
            M('restart', 'void', (), 'a'),
            M('clean', 'void', (), 'a'),
            M('addRecordTask', 'void', ('com.fr.analysis.cloud.solid.SolidRecordTask',), 'a'),
            M('removeRecordTask', 'void', ('java.lang.String',), 'a'),
            M('checkRecordTaskExist', 'boolean', ('java.lang.String',), 'a'),
            M(
                'getRecordTask',
                'java.util.Collection<com.fr.analysis.cloud.solid.SolidRecordTask>',
                (),
                'a',
            ),
        ),
    ),
    'com.fr.base.io.FileAssistUtilsOperator': Service(
        'webapps/webroot/WEB-INF/lib/fine-core-10.0.jar',
        'interface',
        (
            M('moveToTrash', 'boolean', ('java.lang.String',), 'a'),
        ),
    ),
    'com.fr.base.operator.common.CommonOperator': Service(
        'webapps/webroot/WEB-INF/lib/fine-core-10.0.jar',
        'interface',
        (
            M(
                'pluginServiceAction',
                'java.lang.String',
                ('java.lang.String', 'java.lang.String',),
                'a',
            ),
            M('pluginServiceStart', 'void', ('java.lang.String',), 'a'),
            M('compile', 'com.fr.stable.JavaCompileInfo', ('java.lang.String',), 'a'),
            M('getLicenseName', 'java.lang.String', (), 'a'),
            M('hasPluginServiceStarted', 'boolean', ('java.lang.String',), 'a'),
            M('loadREUFile', 'java.lang.String[]', (), 'a'),
            M('installREUFile', 'boolean', ('java.io.File',), 'a'),
            M('removeREUFilesByName', 'boolean', ('java.lang.String',), 'a'),
            M('getSharePath', 'java.lang.String', (), 'a'),
            M('getPluginStatus', 'com.fr.json.JSONArray', (), 'a'),
            M('getDefaultSolutionTip', 'java.lang.String', (), 'a'),
            M('getWebRootPath', 'java.lang.String', (), 'a'),
            M('writeSvgFile', 'boolean', ('com.fr.stable.SvgProvider',), 'a'),
            M('readPathSvgFiles', 'java.lang.String[]', ('java.lang.String',), 'a'),
            M('unlockTemplate', 'void', ('java.lang.String',), 'a'),
            M('fileLocked', 'boolean', ('java.lang.String',), 'a'),
            M('getAppName', 'java.lang.String', (), 'a'),
            M('getContextName', 'java.lang.String', (), 'a'),
            M('getDesignerVersion', 'java.lang.String', (), 'a'),
            M('isWarDeploy', 'boolean', (), 'a'),
        ),
    ),
    'com.fr.base.operator.org.OrganizationOperator': Service(
        'webapps/webroot/WEB-INF/lib/fine-core-10.0.jar',
        'interface',
        (
            M('getRoleGroup', 'java.lang.String[]', (), 'a'),
            M('getConnectionGroup', 'java.lang.String[]', (), 'a'),
            M('canAccess', 'boolean', ('java.lang.String',), 'a'),
        ),
    ),
    'com.fr.base.rpc.encrypt.EncryptOperator': Service(
        'webapps/webroot/WEB-INF/lib/fine-report-engine-10.0.jar',
        'interface',
        (
            M('readKey', 'java.lang.String', (), 'a'),
        ),
    ),
    'com.fr.cluster.engine.rpc.remote.ClusterOperator': Service(
        'webapps/webroot/WEB-INF/lib/fine-core-10.0.jar',
        'interface',
        (
            M('isCluster', 'boolean', (), 'a'),
        ),
    ),
    'com.fr.config.dao.CommitHelper': Service(
        'webapps/webroot/WEB-INF/lib/fine-core-10.0.jar',
        'interface',
        (
            M('commit', 'boolean', ('java.util.List',), 'a'),
        ),
    ),
    'com.fr.config.dao.DataFetcher': Service(
        'webapps/webroot/WEB-INF/lib/fine-core-10.0.jar',
        'interface',
        (
            M('getConfig', 'java.util.List<T>', ('java.lang.Class', 'java.lang.String',), 'a'),
        ),
    ),
    'com.fr.data.operator.DataOperatorProvider': Service(
        'webapps/webroot/WEB-INF/lib/fine-core-10.0.jar',
        'interface',
        (
            M('testConnection', 'boolean', ('com.fr.data.impl.Connection',), 'a'),
            M('validateConnectionSettings', 'void', ('com.fr.data.impl.Connection',), 'a'),
            M('testConnectionWithException', 'void', ('com.fr.data.impl.Connection',), 'a'),
            M('getTableSchema', 'java.lang.String[]', ('com.fr.data.impl.Connection',), 'a'),
            M(
                'getTableSummary',
                'java.lang.String[]',
                ('com.fr.data.impl.Connection', 'java.lang.String...',),
                'a',
            ),
            M(
                'getProcedures',
                'java.util.List<com.fr.data.core.db.TableProcedure[]>',
                ('com.fr.data.impl.Connection', 'java.lang.String[]', 'boolean', 'boolean',),
                'a',
            ),
            M(
                'getTableProcedure',
                'com.fr.data.core.db.TableProcedure[]',
                ('com.fr.data.impl.Connection', 'java.lang.String', 'java.lang.String',),
                'a',
            ),
            M(
                'previewTableData',
                'com.fr.data.impl.EmbeddedTableData',
                ('com.fr.base.TableData', 'java.util.Map', 'int',),
                'a',
            ),
            M(
                'previewTableData',
                'com.fr.base.TableData',
                (
                    'com.fr.base.TableData', 'java.util.Map', 'int', 'int', 'java.lang.String[]',
                    'int[]'
                ),
                'a',
            ),
            M(
                'getTableDataParameters',
                'com.fr.stable.ParameterProvider[]',
                ('com.fr.base.TableData',),
                'a',
            ),
            M(
                'getStoreProcedureParameters',
                'com.fr.stable.ParameterProvider[]',
                ('com.fr.data.impl.storeproc.StoreProcedure',),
                'a',
            ),
            M(
                'previewTableData',
                'com.fr.data.impl.EmbeddedTableData',
                ('com.fr.data.TableDataSource', 'java.lang.Object', 'java.util.Map', 'int',),
                'a',
            ),
            M(
                'previewTableData',
                'com.fr.data.impl.EmbeddedTableData',
                (
                    'com.fr.data.TableDataSource', 'java.lang.Object', 'java.util.Map', 'int',
                    'int', 'java.lang.String[]', 'int[]'
                ),
                'a',
            ),
            M(
                'getColumns',
                'java.lang.String[]',
                ('java.lang.String', 'java.lang.String', 'java.lang.String',),
                'a',
            ),
            M(
                'getProcedureText',
                'java.lang.String',
                ('java.lang.String', 'java.lang.String',),
                'a',
            ),
            M(
                'getStoreProcedureDeclarationParameters',
                'com.fr.base.StoreProcedureParameter[]',
                ('java.lang.String', 'java.lang.String', 'java.lang.String',),
                'a',
            ),
            M(
                'previewProcedureDataModel',
                'com.fr.data.impl.storeproc.ProcedureDataModel[]',
                ('com.fr.data.impl.storeproc.StoreProcedure', 'java.util.Map', 'int',),
                'a',
            ),
            M(
                'getDataBaseDetail',
                'com.fr.data.core.db.dialect.base.key.check.DataBaseDetail',
                ('com.fr.data.impl.Connection', 'boolean',),
                'a',
            ),
        ),
    ),
    'com.fr.esd.core.remote.ESDConfigEventOperator': Service(
        'plugins/plugin-com.fr.plugin.esd-1.8.4/fr-plugin-esd-1.8.4.jar',
        'interface',
        (
            M('fire', 'void', ('java.lang.String', 'byte[]',), 'a'),
            M(
                'fire',
                'void',
                ('com.fr.esd.event.StrategyEvent', 'com.fr.esd.event.DSMapping...',),
                'a',
            ),
        ),
    ),
    'com.fr.file.filetree.FileNodes': Service(
        'webapps/webroot/WEB-INF/lib/fine-core-10.0.jar',
        'interface',
        (
            M('getSupportedTypes', 'java.lang.String[]', (), 'a'),
            M('list', 'com.fr.file.filetree.FileNode[]', ('java.lang.String',), 'a'),
            M('list', 'com.fr.file.filetree.FileNode[]', ('java.lang.String', 'boolean',), 'a'),
            M('listWebRootFile', 'com.fr.file.filetree.FileNode[]', ('java.lang.String',), 'a'),
            M(
                'list',
                'com.fr.file.filetree.FileNode[]',
                ('java.lang.String', 'com.fr.base.extension.FileExtension',),
                'a',
            ),
            M(
                'list',
                'com.fr.file.filetree.FileNode[]',
                ('java.lang.String', 'com.fr.base.extension.FileExtension[]',),
                'a',
            ),
            M(
                'list',
                'com.fr.file.filetree.FileNode[]',
                ('java.lang.String', 'com.fr.base.extension.FileExtension', 'boolean',),
                'a',
            ),
            M(
                'list',
                'com.fr.file.filetree.FileNode[]',
                ('java.lang.String', 'com.fr.base.extension.FileExtension[]', 'boolean',),
                'a',
            ),
            M(
                'list',
                'com.fr.file.filetree.FileNode[]',
                (
                    'java.lang.String', 'com.fr.base.extension.FileExtension[]', 'boolean',
                    'boolean'
                ),
                'a',
            ),
            M(
                'filterFiles',
                'com.fr.file.filetree.FileNode[]',
                (
                    'java.lang.String', 'java.lang.String',
                    'com.fr.base.extension.FileExtension[]', 'boolean'
                ),
                'a',
            ),
            M(
                'filterFiles',
                'com.fr.file.filetree.FileNode[]',
                (
                    'java.lang.String', 'java.lang.String',
                    'com.fr.base.extension.FileExtension[]', 'boolean', 'boolean'
                ),
                'a',
            ),
        ),
    ),
    'com.fr.form.share.ShareComponentOperator': Service(
        'webapps/webroot/WEB-INF/lib/fine-report-engine-10.0.jar',
        'interface',
        (
            M('cacheComponents', 'java.lang.String[]', ('com.fr.form.share.Group',), 'a'),
            M(
                'installComponent',
                'boolean',
                ('com.fr.form.share.Group', 'java.lang.String', 'byte[]',),
                'a',
            ),
            M('removeComponent', 'boolean', ('com.fr.form.share.Group', 'java.lang.String',), 'a'),
            M('getSharePath', 'java.lang.String', (), 'a'),
        ),
    ),
    'com.fr.form.share.ShareEmbeddedConverter': Service(
        'webapps/webroot/WEB-INF/lib/fine-report-engine-10.0.jar',
        'interface',
        (
            M(
                'convertToEmbeddedTableData',
                'java.util.Map<java.lang.String, com.fr.base.TableData>',
                ('com.fr.data.TableDataSource', 'java.util.Map',),
                'a',
            ),
        ),
    ),
    'com.fr.plugin.cloud.analytics.collect.rpc.RPCDataCollector': Service(
        'webapps/webroot/WEB-INF/plugins/plugin-com.fr.plugin.cloud.analytics.v10-2.14.0.20230222/f'
        'r-plugin-cloud-analytics-2.14.0.20230222.jar',
        'interface',
        (
            M('submit', 'void', ('T',), 'a'),
        ),
    ),
    'com.fr.plugin.weixin.server.rpc.WeiXinRPCOperator': Service(
        'plugins/plugin-com.fr.plugin.weixin-10.5.20/fr-plugin-weixin-10.5.20.jar',
        'interface',
        (
            M(
                'getAgents',
                'java.util.List<? extends com.fr.plugin.mobile.base.oa.bean.BaseAgent<?>>',
                (),
                'a',
            ),
        ),
    ),
    'com.fr.security.encryption.storage.StorageTransfer': Service(
        'webapps/webroot/WEB-INF/lib/fine-core-10.0.jar',
        'interface',
        (
            M('encrypt', 'java.lang.String', ('java.lang.String',), 'a'),
            M('decrypt', 'java.lang.String', ('java.lang.String',), 'a'),
            M('encrypt', 'java.lang.String', ('java.lang.String', 'java.lang.String',), 'a'),
            M('decrypt', 'java.lang.String', ('java.lang.String', 'java.lang.String',), 'a'),
            M(
                'setCurrentEncryptionMode',
                'void',
                ('com.fr.security.encryption.mode.EncryptionMode',),
                'a',
            ),
            M(
                'getCurrentEncryptionMode',
                'com.fr.security.encryption.mode.EncryptionMode',
                (),
                'a',
            ),
            M(
                'getCurrentSecurityKeys',
                'com.fr.security.encryption.storage.keys.SecurityKeys',
                (),
                'a',
            ),
        ),
    ),
    'com.fr.workspace.engine.client.heartbeart.WorkspaceHeartbeat': Service(
        'webapps/webroot/WEB-INF/lib/fine-core-10.0.jar',
        'interface',
        (
            M('start', 'void', (), 'a'),
            M('stop', 'void', (), 'a'),
            M('getInterval', 'int', (), 'a'),
            M('beat', 'void', ('com.fr.workspace.connect.WorkspaceConnection',), 'a'),
            M('close', 'void', ('com.fr.workspace.connect.WorkspaceConnection',), 'a'),
        ),
    ),
    'com.fr.workspace.resource.WorkResource': Service(
        'webapps/webroot/WEB-INF/lib/fine-core-10.0.jar',
        'interface',
        (
            M('readFully', 'byte[]', ('java.lang.String',), 'a'),
            M('openStream', 'java.io.InputStream', ('java.lang.String',), 'a'),
            M('write', 'void', ('java.lang.String', 'byte[]',), 'a'),
            M('createFile', 'boolean', ('java.lang.String',), 'a'),
            M('createDirectory', 'boolean', ('java.lang.String',), 'a'),
            M('delete', 'boolean', ('java.lang.String',), 'a'),
            M('rename', 'boolean', ('java.lang.String', 'java.lang.String',), 'a'),
            M('exist', 'boolean', ('java.lang.String',), 'a'),
            M('list', 'java.lang.String[]', ('java.lang.String',), 'a'),
            M('list', 'java.lang.String[]', ('java.lang.String', 'com.fr.stable.Filter',), 'a'),
            M('isDirectory', 'boolean', ('java.lang.String',), 'a'),
            M('lastModified', 'long', ('java.lang.String',), 'a'),
            M('length', 'long', ('java.lang.String',), 'a'),
            M('save', 'void', ('java.lang.String', 'java.lang.String', 'byte[]',), 'd'),
        ),
    ),
    'com.fr.workspace.server.authority.AuthorityOperator': Service(
        'webapps/webroot/WEB-INF/lib/fine-report-engine-10.0.jar',
        'interface',
        (
            M('getAuthorities', 'com.fr.report.DesignAuthority[]', ('java.lang.String',), 'a'),
            M('getCustomRoleAuthorities', 'com.fr.report.DesignAuthority[]', (), 'a'),
            M('getUserAuthorities', 'com.fr.report.DesignAuthority[]', (), 'a'),
            M('hasAuthority', 'boolean', ('java.lang.String',), 'a'),
            M('getAuthorities', 'com.fr.report.DesignAuthority[]', (), 'a'),
            M('updateAuthorities', 'boolean', ('com.fr.report.DesignAuthority[]',), 'a'),
            M(
                'findWithTotalCount',
                'com.fr.stable.query.data.DataList<com.fr.report.data.RemoteDesignAuthority>',
                ('com.fr.stable.query.condition.QueryCondition',),
                'a',
            ),
        ),
    ),
    'com.fr.workspace.server.authority.decision.DecisionOperator': Service(
        'webapps/webroot/WEB-INF/lib/fine-report-engine-10.0.jar',
        'interface',
        (
            M(
                'getMembers',
                'java.util.Collection<com.fr.workspace.server.authority.RemoteDesignMember>',
                ('java.lang.String', 'java.lang.String',),
                'a',
            ),
            M(
                'getMembers',
                'java.util.Collection<com.fr.workspace.server.authority.RemoteDesignMember>',
                ('java.lang.String', 'java.lang.String', 'int', 'int',),
                'a',
            ),
            M(
                'getCustoms',
                'java.util.Collection<com.fr.workspace.server.authority.RemoteDesignMember>',
                ('java.lang.String', 'java.lang.String',),
                'a',
            ),
            M(
                'getCustoms',
                'java.util.Collection<com.fr.workspace.server.authority.RemoteDesignMember>',
                ('java.lang.String', 'java.lang.String', 'int', 'int',),
                'a',
            ),
            M('getUserIdByName', 'java.lang.String', ('java.lang.String',), 'a'),
            M('isRoot', 'boolean', ('java.lang.String',), 'a'),
        ),
    ),
    'com.fr.workspace.server.check.TemplateChecker': Service(
        'webapps/webroot/WEB-INF/lib/fine-report-engine-10.0.jar',
        'interface',
        (
            M('checkFont', 'java.util.Set<java.lang.String>', ('java.lang.String',), 'a'),
        ),
    ),
    'com.fr.workspace.server.check.VersionInfoOperator': Service(
        'webapps/webroot/WEB-INF/lib/fine-report-engine-10.0.jar',
        'interface',
        (
            M('getFullBuildNO', 'java.lang.String', (), 'a'),
        ),
    ),
    'com.fr.workspace.server.connection.DBConnectAuth': Service(
        'webapps/webroot/WEB-INF/lib/fine-report-engine-10.0.jar',
        'interface',
        (
            M('getNoAuthConnections', 'java.util.Collection<java.lang.String>', (), 'a'),
        ),
    ),
    'com.fr.workspace.server.exporter.TemplateExportOperator': Service(
        'webapps/webroot/WEB-INF/lib/fine-report-engine-10.0.jar',
        'interface',
        (
            M(
                'export',
                'byte[]',
                (
                    'com.fr.io.exporter.ExporterKey', 'com.fr.io.exporter.DesignExportType',
                    'java.io.OutputStream', 'java.lang.String', 'java.util.Map'
                ),
                'a',
            ),
            M('exportFormAsImageData', 'byte[]', ('java.lang.String',), 'd'),
            M('exportWorkBookAsImageData', 'byte[]', ('java.lang.String',), 'd'),
            M('imageToByteData', 'byte[]', ('java.awt.image.BufferedImage',), 's'),
            M('byteDataToImage', 'java.awt.image.BufferedImage', ('byte[]',), 's'),
        ),
    ),
    'com.fr.workspace.server.lock.TplOperator': Service(
        'webapps/webroot/WEB-INF/lib/fine-report-engine-10.0.jar',
        'interface',
        (
            M('readAndLockFile', 'byte[]', ('java.lang.String',), 'a'),
            M('closeAndFreeFile', 'boolean', ('java.lang.String',), 'a'),
            M('rename', 'boolean', ('java.lang.String', 'java.lang.String',), 'a'),
            M('saveAs', 'boolean', ('java.lang.String',), 'a'),
            M('delete', 'boolean', ('java.lang.String',), 'a'),
            M('userOut', 'boolean', ('java.lang.String',), 'a'),
            M('userIn', 'boolean', ('java.lang.String',), 'a'),
        ),
    ),
    'com.fr.workspace.server.lock.editlock.EditLockOperator': Service(
        'webapps/webroot/WEB-INF/lib/fine-report-engine-10.0.jar',
        'interface',
        (
            M('lock', 'boolean', ('com.fr.report.LockItem',), 'a'),
            M('unlock', 'boolean', ('com.fr.report.LockItem',), 'a'),
            M('isLocked', 'boolean', ('com.fr.report.LockItem',), 'a'),
        ),
    ),
    'com.fr.workspace.server.socket.SocketInfoOperator': Service(
        'webapps/webroot/WEB-INF/lib/fine-report-engine-10.0.jar',
        'interface',
        (
            M('getPort', 'java.lang.Integer[]', (), 'a'),
        ),
    ),
    'com.fr.workspace.server.vcs.VcsOperator': Service(
        'webapps/webroot/WEB-INF/lib/fine-report-engine-10.0.jar',
        'interface',
        (
            M(
                'getVersions',
                'java.util.List<com.fr.report.entity.VcsEntity>',
                ('java.lang.String',),
                'a',
            ),
            M(
                'getFilterVersions',
                'java.util.List<com.fr.report.entity.VcsEntity>',
                ('java.lang.String', 'java.util.Date', 'java.util.Date', 'java.lang.String',),
                'a',
            ),
            M(
                'getFileVersionByIndexAndUsername',
                'com.fr.report.entity.VcsEntity',
                ('java.lang.String', 'java.lang.String', 'int',),
                'a',
            ),
            M(
                'getFileVersionByIndex',
                'com.fr.report.entity.VcsEntity',
                ('java.lang.String', 'int',),
                'a',
            ),
            M(
                'getFileVersion',
                'com.fr.report.entity.VcsEntity',
                ('java.lang.String', 'int',),
                'a',
            ),
            M('updateVersion', 'void', ('com.fr.report.entity.VcsEntity',), 'a'),
            M(
                'saveVersion',
                'com.fr.report.entity.VcsEntity',
                ('java.lang.String', 'java.lang.String', 'java.lang.String',),
                'a',
            ),
            M(
                'saveVersion',
                'com.fr.report.entity.VcsEntity',
                ('java.lang.String', 'java.lang.String', 'java.lang.String', 'int',),
                'a',
            ),
            M(
                'saveVersionFromCache',
                'com.fr.report.entity.VcsEntity',
                ('java.lang.String', 'java.lang.String', 'java.lang.String', 'int',),
                'a',
            ),
            M('rollbackTo', 'void', ('com.fr.report.entity.VcsEntity',), 'a'),
            M('getFileOfFileVersion', 'java.lang.String', ('java.lang.String', 'int',), 'a'),
            M('getFileOfCurrent', 'java.lang.String', ('java.lang.String',), 'a'),
            M('deleteVersion', 'void', ('java.lang.String', 'int',), 'a'),
            M('moveVscFolder', 'void', (), 'a'),
            M('gc', 'boolean', (), 'a'),
            M('immediatelyGc', 'long', (), 'a'),
        ),
    ),
}
