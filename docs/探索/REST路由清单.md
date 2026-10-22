# FineReport 决策平台 REST 路由清单（安装包反解）

> 由 `javap -v -p` 解析 jar 里的 Spring `@RequestMapping` 生成（`{version}` 归一为 `v10`，
> 已剔除 `fine-third`（第三方库自带控制器））。重新生成见文末。

- 路由条目 **961** 条，涉及控制器 **153** 个
- 纯 GET（只读候选）**410** 条
- frcli 已覆盖 **87** 条，未覆盖 **874** 条

## 全部路由

| 路径 | 方法 | 只读 | frcli | 控制器#方法 |
|------|------|------|-------|-------------|
| `/*` | ANY |  |  | `com.fr.web.controller.decision.entrance.Home#page` |
| `/*/*` | ANY |  |  | `com.fr.plugin.operation.server.controller.DefaultController#mainHtml` |
| `/*/**` | ANY |  |  | `com.fr.plugin.operation.server.controller.DefaultController#loginHtml` |
| `/*/main` | ANY |  |  | `com.fr.plugin.operation.server.controller.DefaultController#mainHtml` |
| `/adaptive/adaptive` | ANY |  |  | `com.fr.web.controller.FormAdaptiveInfoCollectService#XOlbahYEvPXAXpW` |
| `/adaptive/info/collect` | POST |  |  | `com.fr.web.controller.FormAdaptiveInfoCollectService#collectAdaptiveInfo` |
| `/attach/attach` | ANY |  |  | `com.fr.plugin.fontprovider.decision.controller.FontManagerResource#list` |
| `/attach/font` | POST |  |  | `com.fr.plugin.fontprovider.decision.controller.FontManagerResource#uploadFont` |
| `/attach/fonts` | GET | ✅ |  | `com.fr.plugin.fontprovider.decision.controller.FontManagerResource#list` |
| `/chart/chart` | ANY |  |  | `com.fr.web.controller.ChartRequestService#xJSXZEfWtNZnIon` |
| `/chart/chartAttr` | POST |  |  | `com.fr.web.controller.ChartRequestService#config` |
| `/compress/fanruanlog` | POST |  |  | `com.fr.plugin.download.info.controller.DownLoadLogController#compressFanruanLog` |
| `/connect/alive` | ANY |  |  | `com.fr.plugin.operation.server.controller.ConnectController#checkOperationAlive` |
| `/connect/checkPid` | ANY |  |  | `com.fr.plugin.operation.server.controller.ConnectController#getFrServerPid` |
| `/connect/config` | ANY |  |  | `com.fr.plugin.operation.server.controller.ConnectController#ConfigConnect` |
| `/connect/connect` | ANY |  |  | `com.fr.plugin.operation.server.controller.ConnectController#checkOperationAlive` |
| `/connect/heartbeat` | ANY |  |  | `com.fr.plugin.operation.server.controller.ConnectController#heartbeatConnect` |
| `/connect/stop` | ANY |  |  | `com.fr.plugin.operation.server.controller.ConnectController#stopServer` |
| `/directory` | GET | ✅ |  | `com.fr.web.controller.decision.entrance.SinglePageHome#entry` |
| `/download/fanruanlog` | POST |  |  | `com.fr.plugin.download.info.controller.DownLoadLogController#downloadFanruanLog` |
| `/downtime/analysis` | GET | ✅ |  | `com.fr.plugin.operation.client.controller.FineOperationResource#getAnalysisResult` |
| `/downtime/check` | GET | ✅ |  | `com.fr.plugin.operation.client.controller.FineOperationResource#getCheckResult` |
| `/downtime/config` | GET | ✅ |  | `com.fr.plugin.operation.client.controller.FineOperationResource#getConfig` |
| `/downtime/config/update` | PUT |  |  | `com.fr.plugin.operation.client.controller.FineOperationResource#updateConfig` |
| `/downtime/downtime` | ANY |  |  | `com.fr.plugin.operation.client.controller.FineOperationResource#checkPrivilege` |
| `/downtime/port/test` | POST |  |  | `com.fr.plugin.operation.client.controller.FineOperationResource#testPort` |
| `/downtime/record` | GET | ✅ |  | `com.fr.plugin.operation.client.controller.FineOperationResource#getRecordMetric` |
| `/downtime/system/check` | GET | ✅ |  | `com.fr.plugin.operation.client.controller.FineOperationResource#getSystemType` |
| `/elite/open` | OPTIONS |  |  | `com.fr.plugin.elite.api.OpenApiController#options` |
| `/elite/open/bi/dataset` | GET | ✅ |  | `com.fr.plugin.elite.api.OpenApiController#getBIDataset` |
| `/elite/open/bi/dataset/tables` | GET | ✅ |  | `com.fr.plugin.elite.api.OpenApiController#getFRDatasetTables` |
| `/elite/open/elite/open` | ANY |  |  | `com.fr.plugin.elite.api.OpenApiController#getFRDatasetTables` |
| `/elite/open/fr/dataset` | GET | ✅ |  | `com.fr.plugin.elite.api.OpenApiController#getFRDataset` |
| `/elite/open/report/frequency/log` | GET | ✅ |  | `com.fr.plugin.elite.api.OpenApiController#getFrequencyLog` |
| `/elite/open/validate` | GET | ✅ |  | `com.fr.plugin.elite.api.OpenApiController#validate` |
| `/elite/open/view/entry/tree` | GET | ✅ |  | `com.fr.plugin.elite.api.OpenApiController#getEntryTree` |
| `/envinfo/download` | POST |  |  | `com.fr.plugin.download.info.controller.DownLoadLogController#downloadInformationXML` |
| `/envinfo/export` | POST |  |  | `com.fr.plugin.download.info.controller.DownLoadLogController#createInformationXML` |
| `/esd/bean/{id}` | GET | ✅ |  | `com.fr.esd.decision.controller.stat.ESDStatResource#entryDetail` |
| `/esd/caches/{sessionID}` | GET | ✅ |  | `com.fr.esd.decision.controller.cache.ESDCacheResource#getCacheList` |
| `/esd/check/schema` | POST |  |  | `com.fr.esd.decision.controller.management.ESDManageResource#checkSchema` |
| `/esd/clear/all` | GET | ✅ |  | `com.fr.esd.decision.controller.cache.ESDCacheResource#clearAll` |
| `/esd/clear/{id}` | GET | ✅ |  | `com.fr.esd.decision.controller.cache.ESDCacheResource#clear` |
| `/esd/config/global` | GET | ✅ |  | `com.fr.esd.decision.controller.management.ESDManageResource#getEsdGlobalConfig` |
| `/esd/config/global` | POST |  |  | `com.fr.esd.decision.controller.management.ESDManageResource#saveEsdGlobalConfig` |
| `/esd/edc/catalogs` | GET | ✅ |  | `com.fr.esd.decision.controller.edc.EDCVersionResource#edcCatalogs` |
| `/esd/edc/esd/edc` | ANY |  |  | `com.fr.esd.decision.controller.edc.EDCVersionResource#edcCatalogs` |
| `/esd/edc/no` | GET | ✅ |  | `com.fr.esd.decision.controller.stat.ESDStatResource#getEDCIncapableList` |
| `/esd/edc/version` | GET | ✅ |  | `com.fr.esd.decision.controller.edc.EDCVersionResource#edcVersion` |
| `/esd/edc/yes` | GET | ✅ |  | `com.fr.esd.decision.controller.stat.ESDStatResource#getEDCCapableList` |
| `/esd/eff` | GET | ✅ |  | `com.fr.esd.decision.controller.stat.ESDStatResource#efficacy` |
| `/esd/eff/detail` | GET | ✅ |  | `com.fr.esd.decision.controller.stat.ESDStatResource#efficacyDetail` |
| `/esd/esd` | ANY |  |  | `com.fr.esd.decision.controller.cache.ESDCacheResource#updateSession` |
| `/esd/esd` | ANY |  |  | `com.fr.esd.decision.controller.management.ESDAssistResource#fanruanLog` |
| `/esd/esd` | ANY |  |  | `com.fr.esd.decision.controller.management.ESDManageResource#featureStatusOff` |
| `/esd/esd` | ANY |  |  | `com.fr.esd.decision.controller.stat.ESDStatResource#entryDetail` |
| `/esd/feature` | GET | ✅ |  | `com.fr.esd.decision.controller.management.ESDManageResource#featureStatusAll` |
| `/esd/feature/{flag}` | GET | ✅ |  | `com.fr.esd.decision.controller.management.ESDManageResource#featureStatus` |
| `/esd/feature/{flag}/off` | GET/POST |  |  | `com.fr.esd.decision.controller.management.ESDManageResource#featureStatusOff` |
| `/esd/feature/{flag}/on` | GET/POST |  |  | `com.fr.esd.decision.controller.management.ESDManageResource#featureStatusOn` |
| `/esd/invalidate/all` | GET | ✅ |  | `com.fr.esd.decision.controller.cache.ESDCacheResource#invalidateAll` |
| `/esd/invalidate/template` | GET | ✅ |  | `com.fr.esd.decision.controller.cache.ESDCacheResource#invalidateTemplate` |
| `/esd/invalidate/{id}` | GET | ✅ |  | `com.fr.esd.decision.controller.cache.ESDCacheResource#invalidate` |
| `/esd/jstack` | GET | ✅ |  | `com.fr.esd.decision.controller.management.ESDAssistResource#stackDump` |
| `/esd/last/updated` | GET | ✅ |  | `com.fr.esd.decision.controller.cache.ESDCacheResource#getLastUpdateTimestamp` |
| `/esd/log` | GET | ✅ |  | `com.fr.esd.decision.controller.management.ESDAssistResource#fanruanLog` |
| `/esd/log/{count}` | GET | ✅ |  | `com.fr.esd.decision.controller.management.ESDAssistResource#fanruanLog` |
| `/esd/predict/esd/predict` | ANY |  |  | `com.fr.esd.decision.controller.predict.ESDPredictResource#convertParamValue` |
| `/esd/predict/execute/{timeBlock}` | POST |  |  | `com.fr.esd.decision.controller.predict.ESDPredictResource#predictExecuteManually` |
| `/esd/predict/option` | GET/POST |  |  | `com.fr.esd.decision.controller.predict.ESDPredictResource#predictOption` |
| `/esd/predict/recommend` | GET | ✅ |  | `com.fr.esd.decision.controller.predict.ESDPredictResource#predictRecommends` |
| `/esd/predict/result` | GET | ✅ |  | `com.fr.esd.decision.controller.predict.ESDPredictResource#predictResults` |
| `/esd/remove/all` | GET | ✅ |  | `com.fr.esd.decision.controller.cache.ESDCacheResource#removeAll` |
| `/esd/remove/{id}` | GET | ✅ |  | `com.fr.esd.decision.controller.cache.ESDCacheResource#remove` |
| `/esd/reset` | GET | ✅ |  | `com.fr.esd.decision.controller.management.ESDManageResource#resetEsd` |
| `/esd/session/update` | GET | ✅ |  | `com.fr.esd.decision.controller.cache.ESDCacheResource#updateSession` |
| `/esd/stat` | GET | ✅ |  | `com.fr.esd.decision.controller.stat.ESDStatResource#getStatDetail` |
| `/esd/stat/analyze` | GET | ✅ |  | `com.fr.esd.decision.controller.stat.ESDStatResource#getStatAnalyzer` |
| `/esd/stat/config/{id}` | GET | ✅ |  | `com.fr.esd.decision.controller.stat.ESDStatResource#strategyInstanceConfigDetail` |
| `/esd/stat/eliminate/{days}` | GET | ✅ |  | `com.fr.esd.decision.controller.stat.ESDStatResource#eliminate` |
| `/esd/stat/params/{id}` | GET | ✅ |  | `com.fr.esd.decision.controller.stat.ESDStatResource#getStrategyParams` |
| `/esd/stat/pro` | GET | ✅ |  | `com.fr.esd.decision.controller.stat.ESDStatResource#getStatRawDetail` |
| `/esd/stat/scheduler` | GET | ✅ |  | `com.fr.esd.decision.controller.stat.ESDStatResource#getStatSchedulerMeter` |
| `/esd/stat/sql/{id}` | GET | ✅ |  | `com.fr.esd.decision.controller.stat.ESDStatResource#getStatSql` |
| `/esd/stat/strategy/{id}` | GET | ✅ |  | `com.fr.esd.decision.controller.stat.ESDStatResource#getRealTimeStrategy` |
| `/esd/stat/template` | GET | ✅ |  | `com.fr.esd.decision.controller.stat.ESDStatResource#getTemplateEff` |
| `/esd/template/all/list` | GET | ✅ |  | `com.fr.esd.decision.controller.template.CacheTemplateResource#getAllTemplate` |
| `/esd/template/cache/all/list` | GET | ✅ |  | `com.fr.esd.decision.controller.template.CacheTemplateResource#getCacheList` |
| `/esd/template/cache/manual/save` | POST |  |  | `com.fr.esd.decision.controller.template.CacheTemplateResource#saveManualCacheTemplate` |
| `/esd/template/cache/recommend/result` | GET | ✅ |  | `com.fr.esd.decision.controller.template.CacheTemplateResource#getRecommendResult` |
| `/esd/template/cache/runtime/add` | POST |  |  | `com.fr.esd.decision.controller.template.CacheTemplateResource#addRuntimeCacheTemplate` |
| `/esd/template/cache/system/add` | POST |  |  | `com.fr.esd.decision.controller.template.CacheTemplateResource#addSystemCacheTemplate` |
| `/esd/template/esd/template` | ANY |  |  | `com.fr.esd.decision.controller.template.CacheTemplateResource#saveManualCacheTemplate` |
| `/esd/template/runtime/detail` | GET | ✅ |  | `com.fr.esd.decision.controller.template.RuntimeRecommendDetailResource#list` |
| `/esd/template/runtime/esd/template/runtime` | ANY |  |  | `com.fr.esd.decision.controller.template.RuntimeRecommendDetailResource#list` |
| `/esd/template/runtime/recommend/esd/template/runtime/recommend` | ANY |  |  | `com.fr.esd.decision.controller.template.RuntimeRecommendResource#getCacheRecommendList` |
| `/esd/template/runtime/recommend/list` | GET | ✅ |  | `com.fr.esd.decision.controller.template.RuntimeRecommendResource#getCacheRecommendList` |
| `/esd/template/system/recommend/detail/download` | GET | ✅ |  | `com.fr.esd.decision.controller.template.SystemRecommendDetailResource#downloadRecommendDetail` |
| `/esd/template/system/recommend/detail/esd/template/system/recommend/detail` | ANY |  |  | `com.fr.esd.decision.controller.template.SystemRecommendDetailResource#getTemplateExploreResult` |
| `/esd/template/system/recommend/detail/explore/attach` | POST |  |  | `com.fr.esd.decision.controller.template.SystemRecommendDetailResource#exploreAttachDetail` |
| `/esd/template/system/recommend/detail/explore/local` | GET | ✅ |  | `com.fr.esd.decision.controller.template.SystemRecommendDetailResource#exploreLocalDetail` |
| `/esd/template/system/recommend/detail/explore/result` | GET | ✅ |  | `com.fr.esd.decision.controller.template.SystemRecommendDetailResource#getAllExploreResult` |
| `/esd/template/system/recommend/detail/explore/template` | GET | ✅ |  | `com.fr.esd.decision.controller.template.SystemRecommendDetailResource#getTemplateExploreResult` |
| `/esd/template/system/recommend/esd/template/system/recommend` | ANY |  |  | `com.fr.esd.decision.controller.template.SystemRecommendResource#getCacheRecommendList` |
| `/esd/template/system/recommend/execute` | GET | ✅ |  | `com.fr.esd.decision.controller.template.SystemRecommendResource#executeCacheRecommend` |
| `/esd/template/system/recommend/list` | GET | ✅ |  | `com.fr.esd.decision.controller.template.SystemRecommendResource#getCacheRecommendList` |
| `/esd/template/system/recommend/more` | GET | ✅ |  | `com.fr.esd.decision.controller.template.SystemRecommendResource#getCacheRecommendMore` |
| `/esd/template/system/recommend/result` | GET | ✅ |  | `com.fr.esd.decision.controller.template.SystemRecommendResource#getCacheRecommendResult` |
| `/esd/template/system/recommend/score/reset` | GET | ✅ |  | `com.fr.esd.decision.controller.template.SystemRecommendResource#setRecommendScore` |
| `/esd/template/system/recommend/time` | GET | ✅ |  | `com.fr.esd.decision.controller.template.SystemRecommendResource#getRecommendTime` |
| `/esd/terminate/all` | GET | ✅ |  | `com.fr.esd.decision.controller.cache.ESDCacheResource#terminateAll` |
| `/esd/terminate/{id}` | GET | ✅ |  | `com.fr.esd.decision.controller.cache.ESDCacheResource#terminate` |
| `/esd/update/all` | GET | ✅ |  | `com.fr.esd.decision.controller.cache.ESDCacheResource#updateAll` |
| `/esd/update/{id}` | GET | ✅ |  | `com.fr.esd.decision.controller.cache.ESDCacheResource#update` |
| `/esd/working/off` | GET | ✅ |  | `com.fr.esd.decision.controller.management.ESDManageResource#closeESD` |
| `/esd/working/on` | GET | ✅ |  | `com.fr.esd.decision.controller.management.ESDManageResource#openESD` |
| `/export/check/export/check` | ANY |  |  | `com.fr.decision.extension.report.api.export.ExportCheckResource#checkFont` |
| `/export/check/font` | POST |  |  | `com.fr.decision.extension.report.api.export.ExportCheckResource#checkFont` |
| `/file` | GET | ✅ |  | `com.fr.web.controller.common.FileRequestService#getFile` |
| `/file/file` | ANY |  |  | `com.fr.web.controller.common.FileRequestService#dealWithFileContentModificator` |
| `/i18n` | ANY |  |  | `com.fr.plugin.operation.server.controller.ResourceController#getI18Text` |
| `/intellij/operation/intellij/operation` | ANY |  |  | `com.fr.plugin.operation.server.controller.CMDController#stopHandleCrash` |
| `/intellij/operation/jmap` | GET | ✅ |  | `com.fr.plugin.operation.server.controller.CMDController#dump` |
| `/intellij/operation/jstack` | GET | ✅ |  | `com.fr.plugin.operation.server.controller.CMDController#getStack` |
| `/intellij/operation/status` | GET | ✅ |  | `com.fr.plugin.operation.server.controller.CMDController#getOperationStatus` |
| `/intellij/operation/stop` | GET | ✅ |  | `com.fr.plugin.operation.server.controller.CMDController#stopHandleCrash` |
| `/login` | POST |  |  | `com.fr.web.controller.decision.api.auth.LoginResource#login` |
| `/login` | GET | ✅ |  | `com.fr.web.controller.decision.api.auth.LoginResource#page` |
| `/login/admin` | POST |  |  | `com.fr.web.controller.decision.api.auth.LoginResource#addAdminUser` |
| `/login/auth` | POST |  |  | `com.fr.plugin.operation.server.controller.LoginController#login` |
| `/login/captcha` | PUT |  |  | `com.fr.web.controller.decision.api.auth.LoginResource#checkLoginCaptcha` |
| `/login/captcha` | POST |  |  | `com.fr.web.controller.decision.api.auth.LoginResource#login` |
| `/login/captcha` | GET | ✅ |  | `com.fr.web.controller.decision.api.auth.LoginResource#sendLoginCaptchaUnsafe` |
| `/login/captcha/gain` | POST |  |  | `com.fr.web.controller.decision.api.auth.LoginResource#sendLoginCaptchaSafe` |
| `/login/captcha/send` | POST |  |  | `com.fr.web.controller.decision.api.auth.LoginResource#sendLoginCaptcha` |
| `/login/config` | GET | ✅ | ✅ | `com.fr.web.controller.decision.api.auth.LoginResource#getLoginConfig` |
| `/login/cross/domain` | POST |  |  | `com.fr.web.controller.decision.api.auth.LoginResource#crossDomainLogin` |
| `/login/cross/domain` | GET | ✅ |  | `com.fr.web.controller.decision.api.auth.LoginResource#crossDomainLoginUnsafe` |
| `/login/image/base64/{attachId}` | GET | ✅ |  | `com.fr.web.controller.decision.api.auth.LoginResource#getImageBase64` |
| `/login/image/{attachId}` | GET | ✅ |  | `com.fr.web.controller.decision.api.auth.LoginResource#showImage` |
| `/login/info` | GET | ✅ |  | `com.fr.web.controller.decision.api.auth.LoginResource#getLastLoginInfo` |
| `/login/info` | POST |  |  | `com.fr.web.controller.decision.api.auth.LoginResource#saveLastLoginInfo` |
| `/login/initialization` | GET | ✅ |  | `com.fr.web.controller.decision.api.auth.LoginResource#addAdminPage` |
| `/login/login` | ANY |  |  | `com.fr.plugin.operation.server.controller.LoginController#logout` |
| `/login/logout` | POST |  |  | `com.fr.plugin.operation.server.controller.LoginController#logout` |
| `/login/password/strategy` | GET | ✅ | ✅ | `com.fr.web.controller.decision.api.auth.LoginResource#getLoginPasswordStrategy` |
| `/login/password/waring/time` | GET | ✅ | ✅ | `com.fr.web.controller.decision.api.auth.LoginResource#getPasswordWaringTime` |
| `/login/pwd/change` | POST |  |  | `com.fr.web.controller.decision.api.auth.LoginResource#changePassword` |
| `/login/pwd/change/current` | POST |  |  | `com.fr.web.controller.decision.api.auth.LoginResource#changeCurrentUserPassword` |
| `/login/pwd/resetting` | PUT |  |  | `com.fr.web.controller.decision.api.auth.LoginResource#resetPasswordByToken` |
| `/login/receiver/exist` | POST |  |  | `com.fr.web.controller.decision.api.auth.LoginResource#getReceiverExistInfo` |
| `/login/slider/info` | GET | ✅ |  | `com.fr.web.controller.decision.api.auth.LoginResource#createVerificationInfo` |
| `/login/slider/verification` | POST |  |  | `com.fr.web.controller.decision.api.auth.LoginResource#checkSliderVerification` |
| `/login/third/auth` | POST |  |  | `com.fr.web.controller.decision.api.auth.LoginResource#thirdAuthLogin` |
| `/login/token/check` | GET | ✅ |  | `com.fr.web.controller.decision.api.auth.LoginResource#checkToken` |
| `/login/usernames` | POST |  |  | `com.fr.web.controller.decision.api.auth.LoginResource#getLoginUserNamesFromMobile` |
| `/login/validation/tool` | GET | ✅ |  | `com.fr.web.controller.decision.api.auth.LoginResource#getLoginValidationTool` |
| `/login/validation/tool` | POST |  |  | `com.fr.web.controller.decision.api.auth.LoginResource#getLoginValidationToolSafe` |
| `/logout` | POST |  |  | `com.fr.web.controller.decision.api.auth.LoginResource#logout` |
| `/logout/cross/domain` | GET | ✅ |  | `com.fr.web.controller.decision.api.auth.LoginResource#logout` |
| `/map/edit` | ANY |  |  | `com.fr.web.controller.decision.api.map.edit.MapEditResource#page` |
| `/map/entry` | POST |  |  | `com.fr.web.controller.decision.api.map.edit.MapEditResource#addEntry` |
| `/map/entry` | DELETE |  |  | `com.fr.web.controller.decision.api.map.edit.MapEditResource#deleteEntry` |
| `/map/entry` | PUT |  |  | `com.fr.web.controller.decision.api.map.edit.MapEditResource#renameEntry` |
| `/map/excelData` | POST |  |  | `com.fr.web.controller.decision.api.map.edit.MapEditResource#importExcelData` |
| `/map/folder` | POST |  |  | `com.fr.web.controller.decision.api.map.edit.MapEditResource#getFolder` |
| `/map/image/v10` | POST |  |  | `com.fr.web.controller.decision.api.map.edit.MapEditResource#saveImage` |
| `/map/json` | GET | ✅ |  | `com.fr.web.controller.decision.api.map.edit.MapEditResource#getJSON` |
| `/map/json` | POST |  |  | `com.fr.web.controller.decision.api.map.edit.MapEditResource#saveJSON` |
| `/map/layer` | POST |  |  | `com.fr.web.controller.decision.api.map.edit.MapEditResource#addLayerEntry` |
| `/map/layer` | DELETE |  |  | `com.fr.web.controller.decision.api.map.edit.MapEditResource#deleteLayerEntry` |
| `/map/layer` | PUT |  |  | `com.fr.web.controller.decision.api.map.edit.MapEditResource#renameLayerEntry` |
| `/map/layer/GIS` | POST |  |  | `com.fr.web.controller.decision.api.map.edit.MapEditResource#saveLayerEntry` |
| `/map/layer/WMS` | POST |  |  | `com.fr.web.controller.decision.api.map.edit.MapEditResource#updateWMSLayerEntry` |
| `/map/layer/WMSLayer` | POST |  |  | `com.fr.web.controller.decision.api.map.edit.MapEditResource#getWMSLayerEntry` |
| `/map/map` | ANY |  |  | `com.fr.web.controller.decision.api.map.edit.MapEditResource#reload` |
| `/map/reload` | POST |  |  | `com.fr.web.controller.decision.api.map.edit.MapEditResource#reload` |
| `/ops/client/systemCheck/config/check` | POST |  |  | `com.fr.plugin.system.operation.inspection.controller.InspectionController#configCheck` |
| `/ops/client/systemCheck/modify` | PUT |  |  | `com.fr.plugin.system.operation.inspection.controller.InspectionController#modifyConfigFile` |
| `/ops/client/systemCheck/ops/client/systemCheck` | ANY |  |  | `com.fr.plugin.system.operation.inspection.controller.InspectionController#writeFile` |
| `/ops/client/systemCheck/result/download` | GET | ✅ |  | `com.fr.plugin.system.operation.inspection.controller.InspectionController#downloadReport` |
| `/ops/client/systemCheck/result/download/list` | POST |  |  | `com.fr.plugin.system.operation.inspection.controller.InspectionController#downloadReport1` |
| `/ops/client/systemCheck/result/list` | GET | ✅ |  | `com.fr.plugin.system.operation.inspection.controller.InspectionController#getResultList` |
| `/ops/client/systemCheck/result/merge` | GET | ✅ |  | `com.fr.plugin.system.operation.inspection.controller.InspectionController#getMergeResult` |
| `/ops/client/systemCheck/result/preview/report` | GET | ✅ |  | `com.fr.plugin.system.operation.inspection.controller.InspectionController#getPreviewReport` |
| `/ops/client/systemCheck/result/status` | GET | ✅ |  | `com.fr.plugin.system.operation.inspection.controller.InspectionController#triggerInspection` |
| `/ops/client/systemCheck/trigger` | POST |  |  | `com.fr.plugin.system.operation.inspection.controller.InspectionController#trigger` |
| `/plugin/inspect/file/**` | GET | ✅ |  | `com.fr.ins.web.api.InsFileRequestResource#getFile` |
| `/plugin/inspect/file/**/plugin/inspect/file/**` | ANY |  |  | `com.fr.ins.web.api.InsFileRequestResource#getFile` |
| `/plugin/inspect/metric/add` | POST |  |  | `com.fr.ins.web.api.InsMetricResource#add` |
| `/plugin/inspect/metric/plugin/inspect/metric` | ANY |  |  | `com.fr.ins.web.api.InsMetricResource#add` |
| `/plugin/inspect/resources/**` | GET | ✅ |  | `com.fr.ins.web.api.InsResourcesRequestResource#getResources` |
| `/plugin/inspect/resources/**/plugin/inspect/resources/**` | ANY |  |  | `com.fr.ins.web.api.InsResourcesRequestResource#getResources` |
| `/plugin/inspect/status/get` | GET | ✅ | ✅ | `com.fr.ins.web.api.InsServerStatusResource#getStatus` |
| `/plugin/inspect/status/plugin/inspect/status` | ANY |  |  | `com.fr.ins.web.api.InsServerStatusResource#getStatus` |
| `/plugin/inspect/x/plugin/inspect/x` | ANY |  |  | `com.fr.ins.web.api.InspectionResource#report` |
| `/plugin/inspect/x/report/{sid}` | GET | ✅ | ✅ | `com.fr.ins.web.api.InspectionResource#report` |
| `/plugin/inspect/x/run` | GET | ✅ | ✅ | `com.fr.ins.web.api.InspectionResource#directRun` |
| `/plugin/private/com.fr.plugin.mobile.web/settings` | GET | ✅ |  | `com.fr.plugin.mobile.web.server.handler.Html5GetConfigsHandler#handle` |
| `/plugin/private/com.fr.plugin.mobile.web/settings` | PUT |  |  | `com.fr.plugin.mobile.web.server.handler.Html5SetConfigsHandler#handle` |
| `/plugin/private/{pluginId}/**` | ANY |  |  | `com.fr.web.controller.plugin.PluginPrivateService#handle` |
| `/plugin/private/{pluginId}/plugin/private/{pluginId}` | ANY |  |  | `com.fr.web.controller.plugin.PluginPrivateService#handle` |
| `/plugin/public/{pluginId}/**` | ANY |  |  | `com.fr.web.controller.plugin.PluginPublicService#handle` |
| `/plugin/public/{pluginId}/plugin/public/{pluginId}` | ANY |  |  | `com.fr.web.controller.plugin.PluginPublicService#handle` |
| `/preview/info/collect` | POST |  |  | `com.fr.web.controller.PreviewInfoCollectResource#collectPreviewInfo` |
| `/preview/preview` | ANY |  |  | `com.fr.web.controller.PreviewInfoCollectResource#XhxatsvwwFeuNjC` |
| `/privilege` | GET | ✅ |  | `com.fr.web.controller.decision.entrance.SinglePageHome#authority` |
| `/realtime/{fileKey}/{tableName}` | POST |  |  | `com.fr.swift.http.RealtimeController#insert` |
| `/refresh/token` | GET | ✅ |  | `com.fr.web.controller.decision.api.auth.LoginResource#refreshToken` |
| `/remote/design/branch` | GET/POST |  | ✅ | `com.fr.decision.extension.report.api.remote.RemoteDesignResource#getBranch` |
| `/remote/design/channel` | POST |  | ✅ | `com.fr.decision.extension.report.api.remote.RemoteDesignResource#onMessage` |
| `/remote/design/check` | POST |  | ✅ | `com.fr.decision.extension.report.api.remote.RemoteDesignResource#check` |
| `/remote/design/cloud/cluster/logdb/size` | GET | ✅ | ✅ | `com.fr.plugin.cloud.analytics.web.controller.CloudClusterResource#getLogdbSize` |
| `/remote/design/cloud/cluster/project/identifier` | GET | ✅ | ✅ | `com.fr.plugin.cloud.analytics.web.controller.CloudClusterResource#getProjectIdentifier` |
| `/remote/design/cloud/cluster/remote/design/cloud/cluster` | ANY |  | ✅ | `com.fr.plugin.cloud.analytics.web.controller.CloudClusterResource#checkRemoteHost` |
| `/remote/design/esd/cluster/auto/refresh` | GET | ✅ | ✅ | `com.fr.esd.decision.controller.cache.ESDClusterResource#clusterAutoRefresh` |
| `/remote/design/esd/cluster/invalidate` | GET | ✅ | ✅ | `com.fr.esd.decision.controller.cache.ESDClusterResource#clusterInvalidate` |
| `/remote/design/esd/cluster/refresh` | GET | ✅ | ✅ | `com.fr.esd.decision.controller.cache.ESDClusterResource#clusterRefresh` |
| `/remote/design/esd/cluster/relation/all` | GET | ✅ | ✅ | `com.fr.esd.decision.controller.cache.ESDClusterResource#clusterCacheRelationAll` |
| `/remote/design/esd/cluster/relation/cancel` | GET | ✅ | ✅ | `com.fr.esd.decision.controller.cache.ESDClusterResource#clusterCacheRelationCancel` |
| `/remote/design/esd/cluster/relation/effect` | GET | ✅ | ✅ | `com.fr.esd.decision.controller.cache.ESDClusterResource#clusterCacheRelation` |
| `/remote/design/esd/cluster/remote/design/esd/cluster` | ANY |  | ✅ | `com.fr.esd.decision.controller.cache.ESDClusterResource#checkRemoteHost` |
| `/remote/design/esd/cluster/remove` | GET | ✅ | ✅ | `com.fr.esd.decision.controller.cache.ESDClusterResource#clusterRemove` |
| `/remote/design/esd/cluster/remove/all` | GET | ✅ | ✅ | `com.fr.esd.decision.controller.cache.ESDClusterResource#clusterRemove` |
| `/remote/design/esd/cluster/system/recommend/execute` | GET | ✅ | ✅ | `com.fr.esd.decision.controller.cache.ESDClusterResource#clusterCacheRecommend` |
| `/remote/design/esd/cluster/system/recommend/more` | GET | ✅ | ✅ | `com.fr.esd.decision.controller.cache.ESDClusterResource#clusterCacheRecommendMore` |
| `/remote/design/esd/cluster/terminate` | GET | ✅ | ✅ | `com.fr.esd.decision.controller.cache.ESDClusterResource#clusterTerminate` |
| `/remote/design/esd/cluster/terminate/all` | GET | ✅ | ✅ | `com.fr.esd.decision.controller.cache.ESDClusterResource#clusterTerminateAll` |
| `/remote/design/esd/cluster/terminate/dsmapping` | GET | ✅ | ✅ | `com.fr.esd.decision.controller.cache.ESDClusterResource#clusterTerminateGlobal` |
| `/remote/design/esd/cluster/terminate/global` | GET | ✅ | ✅ | `com.fr.esd.decision.controller.cache.ESDClusterResource#clusterTerminateGlobal` |
| `/remote/design/record` | GET/POST |  | ✅ | `com.fr.decision.extension.report.api.remote.RemoteDesignResource#getRecord` |
| `/remote/design/remote/design` | ANY |  | ✅ | `com.fr.decision.extension.report.api.remote.RemoteDesignResource#check` |
| `/remote/design/service` | GET/POST |  | ✅ | `com.fr.decision.extension.report.api.remote.RemoteDesignResource#getServiceList` |
| `/remote/design/verify` | POST |  | ✅ | `com.fr.decision.extension.report.api.remote.RemoteDesignResource#saferGetRemoteToken` |
| `/remote/design/version` | GET/POST |  | ✅ | `com.fr.decision.extension.report.api.remote.RemoteDesignResource#getVersion` |
| `/remote/design/vt` | GET/POST |  | ✅ | `com.fr.decision.extension.report.api.remote.RemoteDesignResource#isSupport` |
| `/resource` | ANY |  |  | `com.fr.plugin.operation.server.controller.ResourceController#resource` |
| `/resources` | ANY |  |  | `com.fr.plugin.operation.server.controller.ResourceController#resources` |
| `/resources` | GET | ✅ |  | `com.fr.web.controller.common.ResourcesRequestService#getResources` |
| `/resources/resources` | ANY |  |  | `com.fr.web.controller.common.ResourcesRequestService#getResources` |
| `/schedule/result` | GET | ✅ |  | `com.fr.web.controller.schedule.web.api.ScheduleResultResource#getScheduleResult` |
| `/schedule/result/list` | GET | ✅ |  | `com.fr.web.controller.schedule.web.api.ScheduleResultResource#getScheduleResultList` |
| `/schedule/schedule` | ANY |  |  | `com.fr.web.controller.schedule.web.api.ScheduleResultResource#getScheduleResultList` |
| `/system/health` | GET/HEAD |  | ✅ | `com.fr.web.controller.decision.api.system.SystemResource#getSystemHealthStatus` |
| `/system/info` | GET/HEAD |  |  | `com.fr.web.controller.decision.api.system.SystemResource#getSystemInfo` |
| `/system/online/numbers` | GET | ✅ |  | `com.fr.web.controller.decision.api.system.SystemResource#getSystemOnlineNumbers` |
| `/system/refresh/alias` | GET | ✅ |  | `com.fr.web.controller.decision.api.system.SystemResource#refreshAlias` |
| `/system/refresh/cache` | GET | ✅ |  | `com.fr.web.controller.decision.api.system.SystemResource#refreshCache` |
| `/system/system` | ANY |  |  | `com.fr.web.controller.decision.api.system.SystemResource#refreshAlias` |
| `/system/version` | GET | ✅ | ✅ | `com.fr.web.controller.decision.api.system.SystemResource#getVersionInfo` |
| `/template/restriction/relaxation/templates` | GET | ✅ |  | `com.fr.plugin.template.restriction.controller.TemplateRestrictionRecommendationResource#getRelaxationTemplates` |
| `/template/restrictionrecommendation` | GET | ✅ |  | `com.fr.plugin.template.restriction.controller.TemplateRestrictionRecommendationResource#getTemplateRestrictionRecommendation` |
| `/template/restrictionsummary` | POST |  |  | `com.fr.plugin.template.restriction.controller.TemplateRestrictionRecommendationResource#getTempRestrictionSummary` |
| `/template/restrictiontemplate/detail` | POST |  |  | `com.fr.plugin.template.restriction.controller.TemplateRestrictionRecommendationResource#getTempRestrictionDetail` |
| `/template/restrictiontemplate/restriction` | ANY |  |  | `com.fr.plugin.template.restriction.controller.TemplateRestrictionRecommendationResource#getRelaxationTemplates` |
| `/template/restrictiontemplates` | POST |  |  | `com.fr.plugin.template.restriction.controller.TemplateRestrictionRecommendationResource#getTemplateRestrictionsTemps` |
| `/timer` | GET | ✅ |  | `com.fr.web.controller.schedule.web.api.SchedulePageResource#page` |
| `/timer/timer` | ANY |  |  | `com.fr.web.controller.schedule.web.api.SchedulePageResource#page` |
| `/token/refresh` | POST |  |  | `com.fr.web.controller.decision.api.auth.LoginResource#tokenRefresh` |
| `/url/**` | ANY |  |  | `com.fr.web.controller.common.ShortURLService#handleShortURL` |
| `/url/mobile` | GET | ✅ |  | `com.fr.plugin.mobile.web.server.handler.fs.Html5LoginHandler#handle` |
| `/url/mobile/bi/view` | GET | ✅ |  | `com.fr.plugin.mobile.web.server.handler.bi.Html5BIVIewHandler#handle` |
| `/url/mobile/info` | GET | ✅ |  | `com.fr.plugin.mobile.web.server.handler.fs.HTML5GetInfoHandler#handle` |
| `/url/mobile/plugin/emb` | GET | ✅ |  | `com.fr.plugin.mobile.web.server.handler.plugin.Html5PluginEmbResourceHandler#handle` |
| `/url/mobile/schedule/result` | GET | ✅ |  | `com.fr.plugin.mobile.web.server.handler.view.Html5ScheduleHandler#handle` |
| `/url/mobile/set/joinplan` | POST |  |  | `com.fr.plugin.mobile.web.server.handler.Html5SetJoinProductPlanHandler#handle` |
| `/url/systemcheck/config` | GET | ✅ |  | `com.fr.plugin.report.system.check.resource.SystemCheckResource#getConfig` |
| `/url/systemcheck/config/update` | PUT |  |  | `com.fr.plugin.report.system.check.resource.SystemCheckResource#updateConfig` |
| `/url/systemcheck/modify` | PUT |  |  | `com.fr.plugin.report.system.check.resource.SystemCheckResource#modifyConfigFile` |
| `/url/systemcheck/url/systemcheck` | ANY |  |  | `com.fr.plugin.report.system.check.resource.SystemCheckResource#modifyConfigFile` |
| `/url/url` | ANY |  |  | `com.fr.web.controller.common.ShortURLService#handleShortURL` |
| `/user` | GET | ✅ |  | `com.fr.web.controller.decision.entrance.SinglePageHome#user` |
| `/v10/attach/download` | POST |  |  | `com.fr.web.controller.decision.api.attach.AttachmentResource#downloadAttach` |
| `/v10/attach/image/cache/{attachId}` | GET | ✅ |  | `com.fr.web.controller.decision.api.attach.AttachmentResource#showImageWithCache` |
| `/v10/attach/image/{attachId}` | GET | ✅ |  | `com.fr.web.controller.decision.api.attach.AttachmentResource#showImage` |
| `/v10/attach/remove/{attachId}` | DELETE |  | ✅ | `com.fr.web.controller.decision.api.attach.AttachmentResource#removeAttach` |
| `/v10/attach/upload` | POST |  | ✅ | `com.fr.web.controller.decision.api.attach.AttachmentResource#uploadAttach` |
| `/v10/attach/v10/attach` | ANY |  |  | `com.fr.web.controller.decision.api.attach.AttachmentResource#removeAttach` |
| `/v10/authority/carrier` | POST |  |  | `com.fr.web.controller.decision.api.auth.AuthorityResource#getAuthorityEntityByCarrier` |
| `/v10/authority/carrier/{carrierType}` | PUT |  |  | `com.fr.web.controller.decision.api.auth.AuthorityResource#updateAuthorityEntityByCarrier` |
| `/v10/authority/config` | GET | ✅ | ✅ | `com.fr.web.controller.decision.api.auth.AuthorityResource#getAuthorityConfig` |
| `/v10/authority/config` | PUT |  | ✅ | `com.fr.web.controller.decision.api.auth.AuthorityResource#setAuthorityConfig` |
| `/v10/authority/config/post` | GET | ✅ | ✅ | `com.fr.web.controller.decision.api.auth.AuthorityResource#isPostAuthority` |
| `/v10/authority/entity` | POST |  |  | `com.fr.web.controller.decision.api.auth.AuthorityResource#getAuthorityCarrierByEntity` |
| `/v10/authority/entity/open` | POST |  |  | `com.fr.web.controller.decision.api.auth.AuthorityResource#getCarriersByEntity` |
| `/v10/authority/entity/{carrierType}` | PUT |  |  | `com.fr.web.controller.decision.api.auth.AuthorityResource#updateCarrierAuthorityByEntity` |
| `/v10/authority/recovery` | POST |  |  | `com.fr.web.controller.decision.api.auth.AuthorityResource#authorityRecovery` |
| `/v10/authority/recovery/preview` | POST |  |  | `com.fr.web.controller.decision.api.auth.AuthorityResource#authorityPreviewIfRecovery` |
| `/v10/authority/reuse` | PUT |  |  | `com.fr.web.controller.decision.api.auth.AuthorityResource#setAuthorityReuse` |
| `/v10/authority/v10/authority` | ANY |  |  | `com.fr.web.controller.decision.api.auth.AuthorityResource#setAuthorityConfig` |
| `/v10/backup/config` | GET | ✅ |  | `com.fr.web.controller.decision.api.backup.BackupResource#getBackupConfig` |
| `/v10/backup/config` | PUT |  |  | `com.fr.web.controller.decision.api.backup.BackupResource#setBackupConfig` |
| `/v10/backup/v10/backup` | ANY |  |  | `com.fr.web.controller.decision.api.backup.BackupResource#getBackupNodeStatus` |
| `/v10/backup/{moduleName}/auto/{open}` | PUT |  |  | `com.fr.web.controller.decision.api.backup.BackupResource#setAutoBackup` |
| `/v10/backup/{moduleName}/delete` | DELETE |  |  | `com.fr.web.controller.decision.api.backup.BackupResource#deleteBackupNodes` |
| `/v10/backup/{moduleName}/info` | GET | ✅ |  | `com.fr.web.controller.decision.api.backup.BackupResource#getModuleBackupConfig` |
| `/v10/backup/{moduleName}/manual` | POST |  |  | `com.fr.web.controller.decision.api.backup.BackupResource#manualBackup` |
| `/v10/backup/{moduleName}/rename` | PUT |  |  | `com.fr.web.controller.decision.api.backup.BackupResource#renameBackupNode` |
| `/v10/backup/{moduleName}/rollback/{id}` | POST |  |  | `com.fr.web.controller.decision.api.backup.BackupResource#rollback` |
| `/v10/backup/{moduleName}/status` | GET | ✅ |  | `com.fr.web.controller.decision.api.backup.BackupResource#getBackupNodeStatus` |
| `/v10/bbs/default/login` | POST |  |  | `com.fr.web.controller.decision.api.bbs.BBSResource#defaultLogin` |
| `/v10/bbs/default/login` | GET | ✅ |  | `com.fr.web.controller.decision.api.bbs.BBSResource#getLoginInfo` |
| `/v10/bbs/v10/bbs` | ANY |  |  | `com.fr.web.controller.decision.api.bbs.BBSResource#getLoginInfo` |
| `/v10/classes` | GET | ✅ |  | `com.fr.web.controller.decision.api.file.FileNodeResource#getClassTreeNodes` |
| `/v10/classes/all` | GET | ✅ |  | `com.fr.web.controller.decision.api.file.FileNodeResource#getAllClassTreeNodes` |
| `/v10/cloud/analytics` | GET | ✅ |  | `com.fr.plugin.cloud.analytics.web.controller.CloudAnalyticsResource#getConfig` |
| `/v10/cloud/analytics` | PUT |  |  | `com.fr.plugin.cloud.analytics.web.controller.CloudAnalyticsResource#putConfig` |
| `/v10/cloud/analytics/agreement` | GET | ✅ |  | `com.fr.plugin.cloud.analytics.web.controller.CloudAnalyticsResource#getAgreement` |
| `/v10/cloud/analytics/config/email` | GET | ✅ |  | `com.fr.plugin.cloud.analytics.web.controller.CloudAnalyticsResource#getConfigEmail` |
| `/v10/cloud/analytics/config/email` | PUT |  |  | `com.fr.plugin.cloud.analytics.web.controller.CloudAnalyticsResource#putConfigEmail` |
| `/v10/cloud/analytics/config/email/dialog/disabled` | POST |  |  | `com.fr.plugin.cloud.analytics.web.controller.CloudAnalyticsResource#putConfigEmailDialogDisabled` |
| `/v10/cloud/analytics/config/send/back` | GET | ✅ |  | `com.fr.plugin.cloud.analytics.web.controller.CloudAnalyticsResource#getSolidFileContent` |
| `/v10/cloud/analytics/delete/treasure` | GET | ✅ |  | `com.fr.plugin.cloud.analytics.web.controller.CloudAnalyticsResource#getDeleteTreasure` |
| `/v10/cloud/analytics/disk/installation` | PUT |  |  | `com.fr.plugin.cloud.analytics.web.controller.CloudAnalyticsResource#putPluginUpdateFromDisk` |
| `/v10/cloud/analytics/download` | GET | ✅ |  | `com.fr.plugin.cloud.analytics.web.controller.CloudAnalyticsResource#getDownload` |
| `/v10/cloud/analytics/manual` | GET | ✅ |  | `com.fr.plugin.cloud.analytics.web.controller.CloudAnalyticsResource#getManual` |
| `/v10/cloud/analytics/plugin/disabled` | GET | ✅ |  | `com.fr.plugin.cloud.analytics.web.controller.CloudAnalyticsResource#getPluginDisabled` |
| `/v10/cloud/analytics/regenerate/appid` | GET | ✅ |  | `com.fr.plugin.cloud.analytics.web.controller.CloudAnalyticsResource#getRegenerateAppId` |
| `/v10/cloud/analytics/store/installation` | PUT |  |  | `com.fr.plugin.cloud.analytics.web.controller.CloudAnalyticsResource#putPluginUpdateFromStore` |
| `/v10/cloud/analytics/upload` | GET | ✅ |  | `com.fr.plugin.cloud.analytics.web.controller.CloudAnalyticsResource#getUpload` |
| `/v10/cloud/analytics/upload/check` | GET | ✅ |  | `com.fr.plugin.cloud.analytics.web.controller.CloudAnalyticsResource#getUploadCheck` |
| `/v10/cloud/analytics/v10/cloud/analytics` | ANY |  |  | `com.fr.plugin.cloud.analytics.web.controller.CloudAnalyticsResource#getDeleteTreasure` |
| `/v10/cloud/analytics/verify` | GET | ✅ |  | `com.fr.plugin.cloud.analytics.web.controller.CloudAnalyticsResource#getVerify` |
| `/v10/cloud/consume/mobile` | POST |  |  | `com.fr.plugin.cloud.analytics.web.controller.CloudConsumeResource#postMobile` |
| `/v10/cloud/consume/v10/cloud/consume` | ANY |  |  | `com.fr.plugin.cloud.analytics.web.controller.CloudConsumeResource#postMobile` |
| `/v10/cloud/feature/config/{feature}/{status}` | GET | ✅ |  | `com.fr.plugin.cloud.analytics.web.controller.CloudFeatureResource#config` |
| `/v10/cloud/feature/show` | GET | ✅ |  | `com.fr.plugin.cloud.analytics.web.controller.CloudFeatureResource#show` |
| `/v10/cloud/feature/v10/cloud/feature` | ANY |  |  | `com.fr.plugin.cloud.analytics.web.controller.CloudFeatureResource#show` |
| `/v10/cloud/file` | GET | ✅ |  | `com.fr.plugin.cloud.analytics.web.controller.CloudStaticResource#getFile` |
| `/v10/cloud/file/v10/cloud/file` | ANY |  |  | `com.fr.plugin.cloud.analytics.web.controller.CloudStaticResource#getLastModified` |
| `/v10/cloud/mark/v10/cloud/mark` | ANY |  |  | `com.fr.plugin.cloud.analytics.web.controller.CloudFineMarkResource#verify` |
| `/v10/cloud/mark/verify` | GET | ✅ |  | `com.fr.plugin.cloud.analytics.web.controller.CloudFineMarkResource#verify` |
| `/v10/cloud/markcreate/{fpId}/{fpVersion}/{fmVersion}` | GET | ✅ |  | `com.fr.plugin.cloud.analytics.web.controller.CloudFineMarkResource#create` |
| `/v10/cloud/plugin/disk/installation` | POST |  |  | `com.fr.web.controller.cloud.CloudOperationResource#installPluginFromDisk` |
| `/v10/cloud/plugin/installation` | GET | ✅ |  | `com.fr.web.controller.cloud.CloudOperationResource#getInstalledPlugin` |
| `/v10/cloud/plugin/installation/status` | PUT |  |  | `com.fr.web.controller.cloud.CloudOperationResource#changePluginStatus` |
| `/v10/cloud/plugin/store/installation` | POST |  |  | `com.fr.web.controller.cloud.CloudOperationResource#installPlugin` |
| `/v10/cloud/solid/content` | GET | ✅ |  | `com.fr.plugin.cloud.analytics.web.controller.CloudSolidResource#config` |
| `/v10/cloud/solid/period/content` | GET | ✅ |  | `com.fr.plugin.cloud.analytics.web.controller.CloudSolidResource#periodContent` |
| `/v10/cloud/solid/period/delete` | GET | ✅ |  | `com.fr.plugin.cloud.analytics.web.controller.CloudSolidResource#periodDelete` |
| `/v10/cloud/solid/period/manual` | GET | ✅ |  | `com.fr.plugin.cloud.analytics.web.controller.CloudSolidResource#periodManual` |
| `/v10/cloud/solid/v10/cloud/solid/` | ANY |  |  | `com.fr.plugin.cloud.analytics.web.controller.CloudSolidResource#periodManual` |
| `/v10/cloud/v10/cloud` | ANY |  |  | `com.fr.web.controller.cloud.CloudOperationResource#installPluginFromDisk` |
| `/v10/cluster/close` | POST |  |  | `com.fr.web.controller.decision.api.cluster.ClusterResource#closeCluster` |
| `/v10/cluster/connection/protocol` | GET | ✅ |  | `com.fr.web.controller.decision.api.cluster.ClusterResource#getProtocol` |
| `/v10/cluster/connection/{protocol}` | POST |  |  | `com.fr.web.controller.decision.api.cluster.ClusterResource#setProtocol` |
| `/v10/cluster/debug/locks` | GET | ✅ |  | `com.fr.web.controller.decision.api.cluster.ClusterResource#getLocks` |
| `/v10/cluster/debug/locks/release` | GET | ✅ |  | `com.fr.web.controller.decision.api.cluster.ClusterResource#releaseLocks` |
| `/v10/cluster/exception/config` | GET | ✅ |  | `com.fr.web.controller.decision.api.cluster.ClusterResource#getClusterExceptionWarningConfig` |
| `/v10/cluster/exception/config` | PUT |  |  | `com.fr.web.controller.decision.api.cluster.ClusterResource#setClusterExceptionWarningConfig` |
| `/v10/cluster/file/arch/status` | GET | ✅ |  | `com.fr.web.controller.decision.api.cluster.ClusterResource#getFileArchStatus` |
| `/v10/cluster/file/cache/mode` | GET | ✅ |  | `com.fr.web.controller.decision.api.cluster.ClusterResource#getCacheMode` |
| `/v10/cluster/file/cache/refresh` | PUT |  |  | `com.fr.web.controller.decision.api.cluster.ClusterResource#syncResourceCache` |
| `/v10/cluster/file/cache/{mode}` | PUT |  |  | `com.fr.web.controller.decision.api.cluster.ClusterResource#setCacheMode` |
| `/v10/cluster/file/mode` | GET | ✅ |  | `com.fr.web.controller.decision.api.cluster.ClusterResource#getFileConsistenceMode` |
| `/v10/cluster/file/service` | GET | ✅ |  | `com.fr.web.controller.decision.api.cluster.ClusterResource#getFileService` |
| `/v10/cluster/file/service` | POST |  |  | `com.fr.web.controller.decision.api.cluster.ClusterResource#setFileService` |
| `/v10/cluster/file/service/test` | POST |  |  | `com.fr.web.controller.decision.api.cluster.ClusterResource#testFileService` |
| `/v10/cluster/file/sync/{nodeID}` | PUT |  |  | `com.fr.web.controller.decision.api.cluster.ClusterResource#setFileSyncCalibrationNode` |
| `/v10/cluster/flush/all` | GET | ✅ |  | `com.fr.web.controller.decision.api.cluster.ClusterResource#flushAll` |
| `/v10/cluster/flush/dirt` | GET | ✅ |  | `com.fr.web.controller.decision.api.cluster.ClusterResource#flushDirt` |
| `/v10/cluster/flush/{key}` | GET | ✅ |  | `com.fr.web.controller.decision.api.cluster.ClusterResource#flushKey` |
| `/v10/cluster/info` | GET | ✅ |  | `com.fr.web.controller.decision.api.cluster.ClusterResource#getClusterInfo` |
| `/v10/cluster/network/card/strategy` | GET | ✅ |  | `com.fr.web.controller.decision.api.cluster.ClusterResource#getNCSelectionStrategy` |
| `/v10/cluster/network/card/{strategy}` | POST |  |  | `com.fr.web.controller.decision.api.cluster.ClusterResource#setNCSelectionStrategy` |
| `/v10/cluster/node` | POST |  |  | `com.fr.web.controller.decision.api.cluster.ClusterResource#setClusterNode` |
| `/v10/cluster/node/ip` | GET | ✅ |  | `com.fr.web.controller.decision.api.cluster.ClusterResource#setClusterNodeIp` |
| `/v10/cluster/node/list` | GET | ✅ |  | `com.fr.web.controller.decision.api.cluster.ClusterResource#getAllClusterNodes` |
| `/v10/cluster/nodes/refresh` | GET | ✅ |  | `com.fr.web.controller.decision.api.cluster.ClusterResource#nodesRefresh` |
| `/v10/cluster/open` | POST |  |  | `com.fr.web.controller.decision.api.cluster.ClusterResource#openCluster` |
| `/v10/cluster/redirect/config` | GET | ✅ |  | `com.fr.web.controller.decision.api.cluster.ClusterResource#getClusterRedirectConfig` |
| `/v10/cluster/redirect/config` | PUT |  |  | `com.fr.web.controller.decision.api.cluster.ClusterResource#setClusterRedirectConfig` |
| `/v10/cluster/redis/config` | GET | ✅ |  | `com.fr.web.controller.decision.api.cluster.ClusterResource#getRedisNameSpaceConfig` |
| `/v10/cluster/redis/config` | PUT |  |  | `com.fr.web.controller.decision.api.cluster.ClusterResource#setRedisNameSpaceConfig` |
| `/v10/cluster/status` | GET | ✅ |  | `com.fr.web.controller.decision.api.cluster.ClusterResource#getClusterStatus` |
| `/v10/cluster/status/service` | GET | ✅ |  | `com.fr.web.controller.decision.api.cluster.ClusterResource#getStatusService` |
| `/v10/cluster/status/service` | POST |  |  | `com.fr.web.controller.decision.api.cluster.ClusterResource#setStatusService` |
| `/v10/cluster/status/service/test` | POST |  |  | `com.fr.web.controller.decision.api.cluster.ClusterResource#testStatusService` |
| `/v10/cluster/v10/cluster` | ANY |  |  | `com.fr.web.controller.decision.api.cluster.ClusterResource#flushDirt` |
| `/v10/collect/solid` | GET | ✅ |  | `com.fr.web.controller.solid.CollectResource#getSolidFile` |
| `/v10/collect/solid/delete` | POST |  |  | `com.fr.web.controller.solid.CollectResource#deleteSolidFile` |
| `/v10/collect/solid/manual` | POST |  |  | `com.fr.web.controller.solid.CollectResource#manualGetSolidFile` |
| `/v10/collect/solid/unlock` | POST |  |  | `com.fr.web.controller.solid.CollectResource#unlockSolidFile` |
| `/v10/collect/v10/collect` | ANY |  |  | `com.fr.web.controller.solid.CollectResource#unlockSolidFile` |
| `/v10/config/appearance/entry` | POST |  |  | `com.fr.web.controller.decision.api.config.AppearanceResource#addCustomCoverIcon` |
| `/v10/config/appearance/entry` | DELETE |  |  | `com.fr.web.controller.decision.api.config.AppearanceResource#deleteCustomCoverIcon` |
| `/v10/config/appearance/entry` | GET | ✅ |  | `com.fr.web.controller.decision.api.config.AppearanceResource#getCustomCoverIcon` |
| `/v10/config/appearance/entry/expansion` | PUT |  |  | `com.fr.web.controller.decision.api.config.AppearanceResource#entryExpansionType` |
| `/v10/config/appearance/entry/expansion` | GET | ✅ |  | `com.fr.web.controller.decision.api.config.AppearanceResource#getDirectoryExpansionType` |
| `/v10/config/appearance/entry/style` | PUT |  |  | `com.fr.web.controller.decision.api.config.AppearanceResource#editEntryCoverIcon` |
| `/v10/config/appearance/entry/{entryId}` | GET | ✅ |  | `com.fr.web.controller.decision.api.config.AppearanceResource#getEntrys` |
| `/v10/config/appearance/login` | GET | ✅ |  | `com.fr.web.controller.decision.api.config.AppearanceResource#getLoginConfig` |
| `/v10/config/appearance/login` | PUT |  |  | `com.fr.web.controller.decision.api.config.AppearanceResource#setLoginConfig` |
| `/v10/config/appearance/style` | GET | ✅ |  | `com.fr.web.controller.decision.api.config.AppearanceResource#getStyleConfig` |
| `/v10/config/appearance/style` | PUT |  |  | `com.fr.web.controller.decision.api.config.AppearanceResource#setStyleConfig` |
| `/v10/config/appearance/theme` | PUT |  |  | `com.fr.web.controller.decision.api.config.AppearanceResource#setCurrentTheme` |
| `/v10/config/appearance/theme/subConfig` | PUT |  |  | `com.fr.web.controller.decision.api.config.AppearanceResource#setThemeSubConfigById` |
| `/v10/config/appearance/theme/subConfig/{themeId}` | GET | ✅ |  | `com.fr.web.controller.decision.api.config.AppearanceResource#getThemeSubConfigById` |
| `/v10/config/appearance/themes` | GET | ✅ |  | `com.fr.web.controller.decision.api.config.AppearanceResource#getAllThemes` |
| `/v10/config/appearance/v10/config/appearance` | ANY |  |  | `com.fr.web.controller.decision.api.config.AppearanceResource#getEntrys` |
| `/v10/config/basic/param` | GET | ✅ |  | `com.fr.web.controller.decision.api.config.BasicParamResource#getBasicParam` |
| `/v10/config/basic/param` | PUT |  |  | `com.fr.web.controller.decision.api.config.BasicParamResource#setBasicParam` |
| `/v10/config/cache` | GET | ✅ |  | `com.fr.web.controller.decision.api.config.CacheResource#getCacheConfig` |
| `/v10/config/cache` | PUT |  |  | `com.fr.web.controller.decision.api.config.CacheResource#setCacheConfig` |
| `/v10/config/cache/template` | GET | ✅ |  | `com.fr.web.controller.decision.api.config.CacheResource#getCacheReloadTemplate` |
| `/v10/config/cache/template/{reload}` | PUT |  |  | `com.fr.web.controller.decision.api.config.CacheResource#setCacheReloadTemplate` |
| `/v10/config/cache/v10/config/cache` | ANY |  |  | `com.fr.web.controller.decision.api.config.CacheResource#setCacheReloadTemplate` |
| `/v10/config/connection` | POST |  |  | `com.fr.web.controller.decision.api.config.ConnectionsResource#addConnectionsConfig` |
| `/v10/config/connection` | DELETE |  |  | `com.fr.web.controller.decision.api.config.ConnectionsResource#deleteConnectionInfo` |
| `/v10/config/connection` | PUT |  |  | `com.fr.web.controller.decision.api.config.ConnectionsResource#updateConnectionInfo` |
| `/v10/config/connection/lic/info` | GET | ✅ |  | `com.fr.web.controller.decision.api.config.ConnectionsResource#getConnectionLicInfo` |
| `/v10/config/connection/list` | GET | ✅ |  | `com.fr.web.controller.decision.api.config.ConnectionsResource#getConnectionsInfos` |
| `/v10/config/connection/list/{privilegeType}` | GET | ✅ |  | `com.fr.web.controller.decision.api.config.ConnectionsResource#getConnectionsInfos` |
| `/v10/config/connection/pool/info` | GET | ✅ |  | `com.fr.web.controller.decision.api.config.ConnectionsResource#getConnectionPoolInfo` |
| `/v10/config/connection/test` | POST |  |  | `com.fr.web.controller.decision.api.config.ConnectionsResource#testConnectionData` |
| `/v10/config/connection/useJaas` | GET | ✅ |  | `com.fr.web.controller.decision.api.config.ConnectionsResource#setJaas` |
| `/v10/config/connection/v10/config/connection` | ANY |  |  | `com.fr.web.controller.decision.api.config.ConnectionsResource#setJaas` |
| `/v10/config/connection/{connectionId}/status` | GET | ✅ |  | `com.fr.web.controller.decision.api.config.ConnectionsResource#shutdownConnection` |
| `/v10/config/email` | GET | ✅ |  | `com.fr.web.controller.decision.api.config.EmailResource#getEmailConfig` |
| `/v10/config/email` | PUT |  |  | `com.fr.web.controller.decision.api.config.EmailResource#setEmailConfig` |
| `/v10/config/email/v10/config/email` | ANY |  |  | `com.fr.web.controller.decision.api.config.EmailResource#setEmailConfig` |
| `/v10/config/emailcmd/test` | POST |  |  | `com.fr.web.controller.decision.api.config.EmailResource#testEmail` |
| `/v10/config/intelligence/release` | GET | ✅ |  | `com.fr.web.controller.decision.api.config.IntelliReleaseResource#getIntelligenceReleaseConfig` |
| `/v10/config/intelligence/release` | PUT |  |  | `com.fr.web.controller.decision.api.config.IntelliReleaseResource#setIntelligenceReleaseConfig` |
| `/v10/config/intelligence/release/v10/config/intelligence/release` | ANY |  |  | `com.fr.web.controller.decision.api.config.IntelliReleaseResource#setIntelligenceReleaseConfig` |
| `/v10/config/lifecycle` | GET | ✅ |  | `com.fr.web.controller.decision.api.config.LifecycleResource#getLifecycleConfig` |
| `/v10/config/lifecycle` | PUT |  |  | `com.fr.web.controller.decision.api.config.LifecycleResource#setLifecycleConfig` |
| `/v10/config/lifecycle/v10/config/lifecycle` | ANY |  |  | `com.fr.web.controller.decision.api.config.LifecycleResource#setLifecycleConfig` |
| `/v10/config/login` | GET | ✅ |  | `com.fr.web.controller.decision.api.config.LoginConfigResource#getLoginConfig` |
| `/v10/config/login` | PUT |  |  | `com.fr.web.controller.decision.api.config.LoginConfigResource#setLoginConfig` |
| `/v10/config/login/lock` | GET | ✅ |  | `com.fr.web.controller.decision.api.config.LoginLockResource#getLoginLockSetting` |
| `/v10/config/login/lock` | PUT |  |  | `com.fr.web.controller.decision.api.config.LoginLockResource#setLoginLockSetting` |
| `/v10/config/login/v10/config/login` | ANY |  |  | `com.fr.web.controller.decision.api.config.LoginConfigResource#setLoginConfig` |
| `/v10/config/login/verification` | GET | ✅ |  | `com.fr.web.controller.decision.api.config.LoginVerificationResource#getLoginVerificationSetting` |
| `/v10/config/login/verification` | PUT |  |  | `com.fr.web.controller.decision.api.config.LoginVerificationResource#setLoginVerificationSetting` |
| `/v10/config/login/verification/v10/config/login/verification` | ANY |  |  | `com.fr.web.controller.decision.api.config.LoginVerificationResource#setLoginVerificationSetting` |
| `/v10/config/password/strategy` | GET | ✅ |  | `com.fr.web.controller.decision.api.config.PasswordStrategyResource#getPasswordStrategy` |
| `/v10/config/password/strategy` | PUT |  |  | `com.fr.web.controller.decision.api.config.PasswordStrategyResource#setPasswordStrategy` |
| `/v10/config/password/strategy/v10/config/password/strategy` | ANY |  |  | `com.fr.web.controller.decision.api.config.PasswordStrategyResource#setPasswordStrategy` |
| `/v10/config/print` | GET | ✅ |  | `com.fr.decision.extension.report.api.print.ReportPrintResource#getPrintConfig` |
| `/v10/config/print` | PUT |  |  | `com.fr.decision.extension.report.api.print.ReportPrintResource#setPrintConfig` |
| `/v10/config/print/v10/config/print` | ANY |  |  | `com.fr.decision.extension.report.api.print.ReportPrintResource#setPrintConfig` |
| `/v10/config/psi` | GET | ✅ |  | `com.fr.web.controller.decision.api.config.PSIResource#getPSIConfig` |
| `/v10/config/psi` | PUT |  |  | `com.fr.web.controller.decision.api.config.PSIResource#setPSIConfig` |
| `/v10/config/psi/escapedchars` | PUT |  |  | `com.fr.web.controller.decision.api.config.PSIResource#setPSICharacterConfig` |
| `/v10/config/psi/keywords` | PUT |  |  | `com.fr.web.controller.decision.api.config.PSIResource#setPSIKeywordConfig` |
| `/v10/config/psi/v10/config/psi` | ANY |  |  | `com.fr.web.controller.decision.api.config.PSIResource#setPSICharacterConfig` |
| `/v10/config/sms` | GET | ✅ |  | `com.fr.web.controller.decision.api.config.SMSResource#getSMSConfig` |
| `/v10/config/sms` | PUT |  |  | `com.fr.web.controller.decision.api.config.SMSResource#setSMSConfig` |
| `/v10/config/sms/test` | POST |  |  | `com.fr.web.controller.decision.api.config.SMSResource#smsTest` |
| `/v10/config/sms/v10/config/sms` | ANY |  |  | `com.fr.web.controller.decision.api.config.SMSResource#smsTest` |
| `/v10/config/template/restriction` | GET | ✅ |  | `com.fr.decision.extension.report.api.template.TemplateRestrictionResource#getTemplateRestrictionConfig` |
| `/v10/config/template/restriction` | PUT |  |  | `com.fr.decision.extension.report.api.template.TemplateRestrictionResource#setTemplateRestrictionConfig` |
| `/v10/config/template/restriction/relaxation` | GET | ✅ |  | `com.fr.decision.extension.report.api.template.TemplateRestrictionResource#getRelaxationTemplateRestrictionConfig` |
| `/v10/config/template/restriction/relaxation` | PUT |  |  | `com.fr.decision.extension.report.api.template.TemplateRestrictionResource#setRelaxationTemplateRestrictionConfig` |
| `/v10/config/template/restriction/v10/config/template/restriction` | ANY |  |  | `com.fr.decision.extension.report.api.template.TemplateRestrictionResource#setRelaxationTemplateRestrictionConfig` |
| `/v10/config/v10/config` | ANY |  |  | `com.fr.web.controller.decision.api.config.BasicParamResource#setVisualizationParam` |
| `/v10/config/visual` | GET | ✅ |  | `com.fr.plugin.config.visual.web.ConfigVisualController#getConfig` |
| `/v10/config/visual` | POST |  |  | `com.fr.plugin.config.visual.web.ConfigVisualController#setConfig` |
| `/v10/config/visual/hidden` | GET | ✅ |  | `com.fr.plugin.config.visual.web.ConfigVisualController#getHiddenConfig` |
| `/v10/config/visual/v10/config/visual` | ANY |  |  | `com.fr.plugin.config.visual.web.ConfigVisualController#checkAdmin` |
| `/v10/config/visualization/param` | GET | ✅ |  | `com.fr.web.controller.decision.api.config.BasicParamResource#getVisualizationParam` |
| `/v10/config/visualization/param/{category}` | PUT |  |  | `com.fr.web.controller.decision.api.config.BasicParamResource#setVisualizationParam` |
| `/v10/data/transference/connection/list` | GET | ✅ |  | `com.fr.web.controller.decision.api.data.transfer.TransferDataResource#getConnectionList` |
| `/v10/data/transference/dataset/list` | GET | ✅ |  | `com.fr.web.controller.decision.api.data.transfer.TransferDataResource#getDataSetList` |
| `/v10/data/transference/entry/tree` | GET | ✅ |  | `com.fr.web.controller.decision.api.data.transfer.TransferDataResource#getEntryTree` |
| `/v10/data/transference/export` | POST |  |  | `com.fr.web.controller.decision.api.data.transfer.TransferDataResource#exportData` |
| `/v10/data/transference/export/progress` | GET | ✅ |  | `com.fr.web.controller.decision.api.data.transfer.TransferDataResource#dataExportProgress` |
| `/v10/data/transference/import` | POST |  |  | `com.fr.web.controller.decision.api.data.transfer.TransferDataResource#importData` |
| `/v10/data/transference/import/infos` | GET | ✅ |  | `com.fr.web.controller.decision.api.data.transfer.TransferDataResource#getImportDataInformation` |
| `/v10/data/transference/relation/resources` | POST |  |  | `com.fr.web.controller.decision.api.data.transfer.TransferDataResource#getEntityRelatedResources` |
| `/v10/data/transference/v10/data/transference` | ANY |  |  | `com.fr.web.controller.decision.api.data.transfer.TransferDataResource#importData` |
| `/v10/data/update` | GET | ✅ |  | `com.fr.web.controller.decision.api.config.DataUpdateResource#getDataUpdateMSG` |
| `/v10/data/update` | PUT |  |  | `com.fr.web.controller.decision.api.config.DataUpdateResource#setDataUpdateMSG` |
| `/v10/data/update/v10/data/update` | ANY |  |  | `com.fr.web.controller.decision.api.config.DataUpdateResource#setDataUpdateMSG` |
| `/v10/dataset` | POST |  |  | `com.fr.web.controller.decision.api.dataset.DataSetResource#addDataSet` |
| `/v10/dataset` | DELETE |  |  | `com.fr.web.controller.decision.api.dataset.DataSetResource#deleteDataSet` |
| `/v10/dataset` | GET | ✅ |  | `com.fr.web.controller.decision.api.dataset.DataSetResource#getAllDataSets` |
| `/v10/dataset` | PUT |  |  | `com.fr.web.controller.decision.api.dataset.DataSetResource#updateDataSet` |
| `/v10/dataset/file/test` | POST |  |  | `com.fr.web.controller.decision.api.dataset.DataSetResource#testFilePath` |
| `/v10/dataset/file/verification` | GET | ✅ |  | `com.fr.web.controller.decision.api.dataset.DataSetResource#verification` |
| `/v10/dataset/files` | GET | ✅ |  | `com.fr.web.controller.decision.api.dataset.DataSetResource#getFileList` |
| `/v10/dataset/param` | POST |  |  | `com.fr.web.controller.decision.api.dataset.DataSetResource#refreshParameters` |
| `/v10/dataset/preview` | POST |  |  | `com.fr.web.controller.decision.api.dataset.DataSetResource#preview` |
| `/v10/dataset/preview/exist` | POST |  |  | `com.fr.web.controller.decision.api.dataset.DataSetResource#previewExsitDataSet` |
| `/v10/dataset/upload` | POST |  |  | `com.fr.web.controller.decision.api.dataset.DataSetResource#upload` |
| `/v10/dataset/users` | POST |  |  | `com.fr.web.controller.decision.api.user.UserResource#importUser` |
| `/v10/dataset/users/config` | GET | ✅ |  | `com.fr.web.controller.decision.api.user.UserResource#getManualDataSetConfig` |
| `/v10/dataset/xml/tree` | POST |  |  | `com.fr.web.controller.decision.api.dataset.DataSetResource#xmlPointTree` |
| `/v10/decision/modules` | GET | ✅ | ✅ | `com.fr.web.controller.decision.api.entry.DecisionMgrResource#getDecisionMgrModule` |
| `/v10/decision/modules/{privilegeType}` | GET | ✅ | ✅ | `com.fr.web.controller.decision.api.entry.DecisionMgrResource#getDecisionMgrModule` |
| `/v10/department/post/users` | POST |  |  | `com.fr.web.controller.decision.api.user.UserResource#getDepUsers` |
| `/v10/department/post/users` | PUT |  |  | `com.fr.web.controller.decision.api.user.UserResource#updateDepUsers` |
| `/v10/department/post/users/all` | DELETE |  |  | `com.fr.web.controller.decision.api.user.UserResource#cleanupDepPostUsers` |
| `/v10/department/post/users/all` | PUT |  |  | `com.fr.web.controller.decision.api.user.UserResource#selectAllDepPostUsers` |
| `/v10/department/root` | GET | ✅ |  | `com.fr.web.controller.decision.api.user.DepartmentResource#getRootDepartment` |
| `/v10/department/{departmentId}` | DELETE |  |  | `com.fr.web.controller.decision.api.user.DepartmentResource#deleteDepartment` |
| `/v10/department/{departmentId}/{depName}` | PUT |  |  | `com.fr.web.controller.decision.api.user.DepartmentResource#editDepartment` |
| `/v10/department/{pId}/{depName}` | POST |  |  | `com.fr.web.controller.decision.api.user.DepartmentResource#addDepartment` |
| `/v10/departments` | GET | ✅ |  | `com.fr.web.controller.decision.api.user.DepartmentResource#searchDepartment` |
| `/v10/departments/list` | GET | ✅ |  | `com.fr.web.controller.decision.api.user.DepartmentResource#searchDepartments` |
| `/v10/departments/posts` | GET | ✅ |  | `com.fr.web.controller.decision.api.user.PositionResource#searchDepPositions` |
| `/v10/departments/posts/list` | GET | ✅ |  | `com.fr.web.controller.decision.api.user.PositionResource#searchDepPosttions` |
| `/v10/departments/posts/tree` | GET | ✅ |  | `com.fr.web.controller.decision.api.user.PositionResource#getDepartmentPostTree` |
| `/v10/departments/tree` | GET | ✅ |  | `com.fr.web.controller.decision.api.user.DepartmentResource#getDepartmentTree` |
| `/v10/departments/{pId}` | GET | ✅ |  | `com.fr.web.controller.decision.api.user.DepartmentResource#getDepartmentsUnderParentDepartment` |
| `/v10/deployment/database` | POST |  |  | `com.fr.web.controller.decision.api.deployment.DeploymentResource#checkMigratedDB` |
| `/v10/deployment/file` | POST |  |  | `com.fr.web.controller.decision.api.deployment.DeploymentResource#checkFileServer` |
| `/v10/deployment/guide` | GET | ✅ |  | `com.fr.web.controller.decision.api.deployment.DeploymentResource#gatherInfo` |
| `/v10/deployment/hsql` | GET | ✅ |  | `com.fr.web.controller.decision.api.deployment.DeploymentResource#checkHsql` |
| `/v10/deployment/jar` | GET | ✅ |  | `com.fr.web.controller.decision.api.deployment.DeploymentResource#checkToolsJar` |
| `/v10/deployment/recommendation` | GET | ✅ |  | `com.fr.web.controller.decision.api.deployment.DeploymentResource#recommend` |
| `/v10/deployment/state` | POST |  |  | `com.fr.web.controller.decision.api.deployment.DeploymentResource#checkStatusService` |
| `/v10/deployment/websocket` | POST |  |  | `com.fr.web.controller.decision.api.deployment.DeploymentResource#checkWebSocket` |
| `/v10/deposts` | GET | ✅ |  | `com.fr.web.controller.decision.api.user.PositionResource#searchDepRoleTreeNodes` |
| `/v10/deposts/root` | GET | ✅ |  | `com.fr.web.controller.decision.api.user.PositionResource#getDepRoleRoot` |
| `/v10/directory` | GET | ✅ |  | `com.fr.web.controller.decision.api.entry.DirectoryResource#searchDirectoryEntryTreeNodes` |
| `/v10/directory/{directoryId}` | PUT |  |  | `com.fr.web.controller.decision.api.entry.DirectoryResource#editDirectory` |
| `/v10/drill/user/behavior/log` | POST |  |  | `com.fr.web.controller.log.IntelliLogResource#searchDrillUserBehaviorLog` |
| `/v10/drivers` | POST |  |  | `com.fr.web.controller.decision.api.driver.manager.DriverManagerResource#addDriver` |
| `/v10/drivers` | DELETE |  |  | `com.fr.web.controller.decision.api.driver.manager.DriverManagerResource#deleteDriver` |
| `/v10/drivers` | PUT |  |  | `com.fr.web.controller.decision.api.driver.manager.DriverManagerResource#updateDriver` |
| `/v10/drivers/list` | GET | ✅ |  | `com.fr.web.controller.decision.api.driver.manager.DriverManagerResource#getDrivers` |
| `/v10/drivers/remove/jar` | DELETE |  |  | `com.fr.web.controller.decision.api.driver.manager.DriverManagerResource#removeJarFile` |
| `/v10/drivers/simple/list` | GET | ✅ |  | `com.fr.web.controller.decision.api.driver.manager.DriverManagerResource#getDriverSimpleInfo` |
| `/v10/drivers/sync` | ANY |  |  | `com.fr.web.controller.decision.api.driver.manager.DriverManagerResource#syncDriverMap` |
| `/v10/drivers/upload` | POST |  |  | `com.fr.web.controller.decision.api.driver.manager.DriverManagerResource#upload` |
| `/v10/drivers/v10/drivers` | ANY |  |  | `com.fr.web.controller.decision.api.driver.manager.DriverManagerResource#syncDriverMap` |
| `/v10/email/log` | POST |  |  | `com.fr.web.controller.log.IntelliLogResource#searchVisitReportLog` |
| `/v10/encryption/action` | PUT |  |  | `com.fr.web.controller.decision.api.config.EncryptionResource#changePasswordStrategy` |
| `/v10/encryption/page` | GET | ✅ |  | `com.fr.web.controller.decision.api.config.EncryptionResource#page` |
| `/v10/encryption/status` | GET | ✅ |  | `com.fr.web.controller.decision.api.config.EncryptionResource#getStatus` |
| `/v10/encryption/v10/encryption` | ANY |  |  | `com.fr.web.controller.decision.api.config.EncryptionResource#createSystemConfig` |
| `/v10/entries` | DELETE |  | ✅ | `com.fr.web.controller.decision.api.entry.EntryResource#deleteEntries` |
| `/v10/entries` | GET | ✅ | ✅ | `com.fr.web.controller.decision.api.entry.EntryResource#getEntries` |
| `/v10/entries` | PUT |  | ✅ | `com.fr.web.controller.decision.api.entry.EntryResource#moveEntries` |
| `/v10/entries/all` | GET | ✅ | ✅ | `com.fr.web.controller.decision.api.entry.EntryResource#getAllEntries` |
| `/v10/entry` | GET | ✅ |  | `com.fr.web.controller.decision.api.entry.EntryResource#getEntryById` |
| `/v10/entry` | PUT |  |  | `com.fr.web.controller.decision.api.entry.EntryResource#moveEntry` |
| `/v10/entry/access/ReportServer` | GET | ✅ |  | `com.fr.decision.extension.report.api.entry.ReportEntryResource#showObsoletePathEntry` |
| `/v10/entry/access/{entryId}` | GET | ✅ |  | `com.fr.web.controller.decision.api.entry.EntryResource#showEntry` |
| `/v10/entry/list` | GET | ✅ |  | `com.fr.web.controller.decision.api.entry.EntryResource#searchEntryListNodes` |
| `/v10/entry/roots` | GET | ✅ |  | `com.fr.web.controller.decision.api.entry.EntryResource#getEntryRootNodes` |
| `/v10/entry/tree` | GET | ✅ |  | `com.fr.web.controller.decision.api.entry.EntryResource#searchEntryTreeNodes` |
| `/v10/entry/tree/{entryType}` | GET | ✅ |  | `com.fr.web.controller.decision.api.entry.EntryResource#getEntryTreeByEntryType` |
| `/v10/error/log` | POST |  |  | `com.fr.web.controller.log.IntelliLogResource#searchErrorLog` |
| `/v10/execute/log/type` | GET | ✅ |  | `com.fr.web.controller.log.IntelliLogResource#getExecuteTye` |
| `/v10/execute/log/{columnName}/values` | POST |  |  | `com.fr.web.controller.log.IntelliLogResource#searchValueByColumnName` |
| `/v10/export/drill/user/behavior/excel` | POST |  |  | `com.fr.web.controller.log.IntelliLogResource#exportDrillUserBehaviorExcel` |
| `/v10/export/drill/user/behavior/log` | POST |  |  | `com.fr.web.controller.log.IntelliLogResource#exportDrillUserBehaviorLog` |
| `/v10/export/operate/excel` | POST |  |  | `com.fr.web.controller.log.IntelliLogResource#exportOperateExcel` |
| `/v10/export/operate/log` | POST |  |  | `com.fr.web.controller.log.IntelliLogResource#exportOperateLog` |
| `/v10/export/performance/detail/excel` | POST |  |  | `com.fr.web.controller.log.IntelliLogResource#exportPerformanceDetailExcel` |
| `/v10/export/performance/detail/log` | POST |  |  | `com.fr.web.controller.log.IntelliLogResource#exportPerformanceDetailLog` |
| `/v10/export/performance/excel` | POST |  |  | `com.fr.web.controller.log.IntelliLogResource#exportPerformanceExcel` |
| `/v10/export/performance/log` | POST |  |  | `com.fr.web.controller.log.IntelliLogResource#exportPerformanceLog` |
| `/v10/export/report/frequency/detail/excel` | POST |  |  | `com.fr.web.controller.log.IntelliLogResource#exportReportFrequencyDetailExcel` |
| `/v10/export/report/frequency/detail/log` | POST |  |  | `com.fr.web.controller.log.IntelliLogResource#exportReportFrequencyDetailLog` |
| `/v10/export/report/frequency/excel` | POST |  |  | `com.fr.web.controller.log.IntelliLogResource#exportReportFrequencyExcel` |
| `/v10/export/report/frequency/log` | POST |  |  | `com.fr.web.controller.log.IntelliLogResource#exportReportFrequencyLog` |
| `/v10/export/user/behavior/excel` | POST |  |  | `com.fr.web.controller.log.IntelliLogResource#exportUserBehaviorExcel` |
| `/v10/export/user/behavior/log` | POST |  |  | `com.fr.web.controller.log.IntelliLogResource#exportUserBehaviorLog` |
| `/v10/export/visit/report/excel` | POST |  |  | `com.fr.web.controller.log.IntelliLogResource#exportVisitReportExcel` |
| `/v10/export/visit/report/log` | POST |  |  | `com.fr.web.controller.log.IntelliLogResource#exportVisitReportLog` |
| `/v10/favorite/entry/list` | GET | ✅ |  | `com.fr.web.controller.decision.api.entry.FavoriteResource#showFavoriteEntry` |
| `/v10/favorite/entry/{entryId}` | POST |  |  | `com.fr.web.controller.decision.api.entry.FavoriteResource#addFavoriteEntry` |
| `/v10/favorite/entry/{entryId}` | DELETE |  |  | `com.fr.web.controller.decision.api.entry.FavoriteResource#removeFavoriteEntry` |
| `/v10/file/{fileId}` | PUT |  |  | `com.fr.web.controller.decision.api.entry.FileEntryResource#editFileEntry` |
| `/v10/homepage` | POST |  |  | `com.fr.web.controller.decision.api.entry.HomePageResource#addHomePage` |
| `/v10/homepage/{homepageId}` | DELETE |  |  | `com.fr.web.controller.decision.api.entry.HomePageResource#deleteHomePage` |
| `/v10/homepage/{homepageId}` | PUT |  |  | `com.fr.web.controller.decision.api.entry.HomePageResource#editHomePage` |
| `/v10/homepages` | GET | ✅ |  | `com.fr.web.controller.decision.api.entry.HomePageResource#getHomePages` |
| `/v10/homepages/{privilegeType}` | GET | ✅ |  | `com.fr.web.controller.decision.api.entry.HomePageResource#getHomePages` |
| `/v10/i18n` | POST |  |  | `com.fr.web.controller.decision.api.international.InternationalResource#addInternationalRecords` |
| `/v10/i18n` | PUT |  |  | `com.fr.web.controller.decision.api.international.InternationalResource#editInternationalRecords` |
| `/v10/i18n` | DELETE |  |  | `com.fr.web.controller.decision.api.international.InternationalResource#removeInternationalRecords` |
| `/v10/i18n/all` | DELETE |  |  | `com.fr.web.controller.decision.api.international.InternationalResource#removeAllInternationalRecords` |
| `/v10/i18n/list` | GET | ✅ |  | `com.fr.web.controller.decision.api.international.InternationalResource#getInternationalList` |
| `/v10/i18n/map` | GET | ✅ |  | `com.fr.web.controller.decision.api.international.InternationalResource#getInternationalMap` |
| `/v10/json/param` | POST |  |  | `com.fr.plugin.db.json.controller.JSONParamController#getParams` |
| `/v10/json/param/v10/json/param` | ANY |  |  | `com.fr.plugin.db.json.controller.JSONParamController#getParams` |
| `/v10/label/labels` | POST |  |  | `com.fr.web.controller.decision.api.label.LabelResource#addLabels` |
| `/v10/label/list/all` | GET | ✅ |  | `com.fr.web.controller.decision.api.label.LabelResource#getLabels` |
| `/v10/label/v10/label` | ANY |  |  | `com.fr.web.controller.decision.api.label.LabelResource#getLabels` |
| `/v10/link/{linkId}` | PUT |  |  | `com.fr.web.controller.decision.api.entry.LinkResource#editLink` |
| `/v10/log/clean/{time}` | POST |  |  | `com.fr.web.controller.decision.api.log.LogResource#cleanLog` |
| `/v10/log/config` | GET | ✅ |  | `com.fr.web.controller.decision.api.log.LogResource#getLogConfig` |
| `/v10/log/config` | PUT |  |  | `com.fr.web.controller.decision.api.log.LogResource#setLogConfig` |
| `/v10/log/size` | GET | ✅ |  | `com.fr.web.controller.decision.api.log.LogResource#refreshLogSize` |
| `/v10/login/lock` | GET | ✅ |  | `com.fr.web.controller.decision.api.config.LoginLockResource#getLoginLockList` |
| `/v10/login/unlock` | DELETE |  |  | `com.fr.web.controller.decision.api.config.LoginLockResource#unlockByIds` |
| `/v10/message/delete/{type}` | DELETE/POST |  |  | `com.fr.web.controller.decision.api.message.MessageResource#deleteMessages` |
| `/v10/message/list` | GET | ✅ |  | `com.fr.web.controller.decision.api.message.MessageResource#getMessages` |
| `/v10/message/readed` | PUT |  |  | `com.fr.web.controller.decision.api.message.MessageResource#updateReaded` |
| `/v10/message/toasted` | PUT |  |  | `com.fr.web.controller.decision.api.message.MessageResource#updateToasted` |
| `/v10/message/unread` | GET | ✅ |  | `com.fr.web.controller.decision.api.message.MessageResource#getUnreadMessages` |
| `/v10/message/v10/message` | ANY |  |  | `com.fr.web.controller.decision.api.message.MessageResource#updateReaded` |
| `/v10/migration/action` | PUT |  |  | `com.fr.web.controller.decision.api.migration.MigrationResource#startTransfer` |
| `/v10/migration/check` | PUT |  |  | `com.fr.web.controller.decision.api.migration.MigrationResource#checkDataExist` |
| `/v10/migration/config/finedb` | GET | ✅ |  | `com.fr.web.controller.decision.api.migration.MigrationResource#getFineDBConfig` |
| `/v10/migration/config/finedb` | POST |  |  | `com.fr.web.controller.decision.api.migration.MigrationResource#updateFineDBConfig` |
| `/v10/migration/dialect` | GET | ✅ |  | `com.fr.web.controller.decision.api.migration.MigrationResource#getDialectClasses` |
| `/v10/migration/page` | GET | ✅ |  | `com.fr.web.controller.decision.api.migration.MigrationResource#page` |
| `/v10/migration/schemas` | GET | ✅ |  | `com.fr.web.controller.decision.api.migration.MigrationResource#getSchemas` |
| `/v10/migration/status` | GET | ✅ |  | `com.fr.web.controller.decision.api.migration.MigrationResource#getStatus` |
| `/v10/migration/switch` | POST |  |  | `com.fr.web.controller.decision.api.migration.MigrationResource#switchDBConfig` |
| `/v10/migration/test` | PUT |  |  | `com.fr.web.controller.decision.api.migration.MigrationResource#testDBConnection` |
| `/v10/migration/v10/migration` | ANY |  |  | `com.fr.web.controller.decision.api.migration.MigrationResource#checkNeedLogin` |
| `/v10/mobile/app/login/integrity/check` | GET | ✅ |  | `com.fr.web.controller.decision.api.mobile.MobileResource#getAppLoginIntegrityCheckConfig` |
| `/v10/mobile/app/login/integrity/check` | PUT |  |  | `com.fr.web.controller.decision.api.mobile.MobileResource#setAppLoginIntegrityCheckConfig` |
| `/v10/mobile/app/msg/proxy` | GET | ✅ |  | `com.fr.web.controller.decision.api.mobile.MobileResource#getAppMsgProxy` |
| `/v10/mobile/app/msg/proxy` | PUT |  |  | `com.fr.web.controller.decision.api.mobile.MobileResource#setAppMsgProxy` |
| `/v10/mobile/app/upgrade/config` | GET | ✅ |  | `com.fr.web.controller.decision.api.mobile.MobileResource#getAppUpgradeConfig` |
| `/v10/mobile/app/upgrade/config` | PUT |  |  | `com.fr.web.controller.decision.api.mobile.MobileResource#setAppConfig` |
| `/v10/mobile/bi/component/height` | GET | ✅ |  | `com.fr.web.controller.decision.api.mobile.MobileResource#getBiComponentHeight` |
| `/v10/mobile/config/entry` | GET | ✅ |  | `com.fr.web.controller.decision.api.mobile.config.entry.MobileEntryResource#getEntryConfig` |
| `/v10/mobile/config/entry` | POST |  |  | `com.fr.web.controller.decision.api.mobile.config.entry.MobileEntryResource#setEntryConfig` |
| `/v10/mobile/config/entry/banner` | POST |  |  | `com.fr.web.controller.decision.api.mobile.config.entry.MobileEntryResource#addBanner` |
| `/v10/mobile/config/entry/banner` | GET | ✅ |  | `com.fr.web.controller.decision.api.mobile.config.entry.MobileEntryResource#getBannerList` |
| `/v10/mobile/config/entry/banner/{bannerId}` | DELETE |  |  | `com.fr.web.controller.decision.api.mobile.config.entry.MobileEntryResource#deleteBanner` |
| `/v10/mobile/config/entry/banner/{bannerId}` | PUT |  |  | `com.fr.web.controller.decision.api.mobile.config.entry.MobileEntryResource#updateBanner` |
| `/v10/mobile/config/entry/icon` | POST |  |  | `com.fr.web.controller.decision.api.mobile.config.entry.MobileEntryResource#addCustomIcon` |
| `/v10/mobile/config/entry/icon/list/custom` | GET | ✅ |  | `com.fr.web.controller.decision.api.mobile.config.entry.MobileEntryResource#getIconList` |
| `/v10/mobile/config/entry/icon/{iconId}` | DELETE |  |  | `com.fr.web.controller.decision.api.mobile.config.entry.MobileEntryResource#deleteCustomIcon` |
| `/v10/mobile/config/entry/style` | GET | ✅ |  | `com.fr.web.controller.decision.api.mobile.config.entry.MobileEntryResource#getStyleList` |
| `/v10/mobile/config/entry/style/t9/settings` | GET | ✅ |  | `com.fr.web.controller.decision.api.mobile.config.entry.MobileEntryResource#getT9StyleSettings` |
| `/v10/mobile/config/entry/style/t9/settings` | POST |  |  | `com.fr.web.controller.decision.api.mobile.config.entry.MobileEntryResource#setT9StyleConfig` |
| `/v10/mobile/config/entry/v10/mobile/config/entry` | ANY |  |  | `com.fr.web.controller.decision.api.mobile.config.entry.MobileEntryResource#deleteCustomIcon` |
| `/v10/mobile/config/others` | GET | ✅ |  | `com.fr.web.controller.decision.api.mobile.OtherResource#getSettings` |
| `/v10/mobile/config/others` | PUT |  |  | `com.fr.web.controller.decision.api.mobile.OtherResource#setSettings` |
| `/v10/mobile/config/others/v10/mobile/config/others` | ANY |  |  | `com.fr.web.controller.decision.api.mobile.OtherResource#setSettings` |
| `/v10/mobile/config/theme` | GET | ✅ |  | `com.fr.web.controller.decision.api.mobile.MobileResource#getThemeConfig` |
| `/v10/mobile/config/theme` | POST |  |  | `com.fr.web.controller.decision.api.mobile.MobileResource#setTheme` |
| `/v10/mobile/custom/login` | GET | ✅ |  | `com.fr.web.controller.decision.api.mobile.MobileResource#getCustomLoginConfig` |
| `/v10/mobile/custom/login` | PUT |  |  | `com.fr.web.controller.decision.api.mobile.MobileResource#setCustomLoginConfig` |
| `/v10/mobile/device` | POST |  |  | `com.fr.web.controller.decision.api.mobile.DeviceResource#addDevice` |
| `/v10/mobile/device` | DELETE |  |  | `com.fr.web.controller.decision.api.mobile.DeviceResource#deleteDevice` |
| `/v10/mobile/device` | GET | ✅ |  | `com.fr.web.controller.decision.api.mobile.DeviceResource#getDeviceUnsafe` |
| `/v10/mobile/device` | PUT |  |  | `com.fr.web.controller.decision.api.mobile.DeviceResource#updateDevice` |
| `/v10/mobile/device/config` | GET | ✅ |  | `com.fr.web.controller.decision.api.mobile.DeviceResource#getDeviceConfig` |
| `/v10/mobile/device/config` | PUT |  |  | `com.fr.web.controller.decision.api.mobile.DeviceResource#setDeviceConfig` |
| `/v10/mobile/device/list` | POST |  |  | `com.fr.web.controller.decision.api.mobile.DeviceResource#getDevice` |
| `/v10/mobile/device/v10/mobile/device` | ANY |  |  | `com.fr.web.controller.decision.api.mobile.DeviceResource#updateDevice` |
| `/v10/mobile/directory/style/settings` | GET | ✅ |  | `com.fr.web.controller.decision.api.mobile.MobileResource#getSelectedStyleSettings` |
| `/v10/mobile/entries` | GET | ✅ |  | `com.fr.web.controller.decision.api.mobile.MobileResource#getAllEntries` |
| `/v10/mobile/entry/banner` | GET | ✅ |  | `com.fr.web.controller.decision.api.mobile.MobileResource#getBanner` |
| `/v10/mobile/entry/icon/{nodeIcon}` | GET | ✅ |  | `com.fr.web.controller.decision.api.mobile.MobileResource#showNodeIcon` |
| `/v10/mobile/entry/template` | GET | ✅ |  | `com.fr.web.controller.decision.api.mobile.MobileResource#getTemplate` |
| `/v10/mobile/global/config` | GET | ✅ |  | `com.fr.web.controller.decision.api.mobile.MobileResource#getGlobalConfig` |
| `/v10/mobile/image/{attachId}` | GET | ✅ |  | `com.fr.web.controller.decision.api.mobile.MobileResource#getImage` |
| `/v10/mobile/launch/image` | GET | ✅ |  | `com.fr.web.controller.decision.api.mobile.MobileResource#getLaunchImg` |
| `/v10/mobile/launch/image` | PUT |  |  | `com.fr.web.controller.decision.api.mobile.MobileResource#setLaunchImg` |
| `/v10/mobile/launch/{device}` | GET | ✅ |  | `com.fr.web.controller.decision.api.mobile.MobileResource#getLaunchImg` |
| `/v10/mobile/launch/{device}` | POST |  |  | `com.fr.web.controller.decision.api.mobile.MobileResource#setLaunchImg` |
| `/v10/mobile/plugins` | GET | ✅ |  | `com.fr.web.controller.decision.api.mobile.MobileResource#getAllAvailablePlugins` |
| `/v10/mobile/plugins/download` | GET | ✅ |  | `com.fr.web.controller.decision.api.mobile.MobileResource#downloadPluginBundles` |
| `/v10/mobile/productPlan` | GET | ✅ |  | `com.fr.web.controller.decision.api.mobile.MobileResource#getProductPlan` |
| `/v10/mobile/productPlan` | PUT |  |  | `com.fr.web.controller.decision.api.mobile.MobileResource#setProductPlan` |
| `/v10/mobile/push/terminals` | GET | ✅ |  | `com.fr.web.controller.decision.api.mobile.MobileResource#getPushTerminals` |
| `/v10/mobile/qrcode` | GET | ✅ |  | `com.fr.web.controller.decision.api.mobile.MobileResource#getQRCodeConfig` |
| `/v10/mobile/qrcode` | PUT |  |  | `com.fr.web.controller.decision.api.mobile.MobileResource#setQRCodeConfig` |
| `/v10/mobile/socket` | GET | ✅ |  | `com.fr.web.controller.decision.api.mobile.MobileResource#getWebSocketInfo` |
| `/v10/mobile/theme` | GET | ✅ |  | `com.fr.web.controller.decision.api.mobile.MobileResource#getActiveThemeInfo` |
| `/v10/mobile/v10/mobile` | ANY |  |  | `com.fr.web.controller.decision.api.mobile.MobileResource#setCustomLoginConfig` |
| `/v10/operate/log` | POST |  |  | `com.fr.web.controller.log.IntelliLogResource#searchOperateLog` |
| `/v10/operate/log/{columnName}/values` | POST |  |  | `com.fr.web.controller.log.IntelliLogResource#searchValueByColumnName` |
| `/v10/performance/detail/log` | POST |  |  | `com.fr.web.controller.log.IntelliLogResource#searchPerformanceDetailLog` |
| `/v10/performance/log` | POST |  |  | `com.fr.web.controller.log.IntelliLogResource#searchPerformanceLog` |
| `/v10/plugin/disk/installation` | POST |  |  | `com.fr.web.controller.decision.api.plugin.PluginResource#installDiskPlugin` |
| `/v10/plugin/disk/installation` | PUT |  |  | `com.fr.web.controller.decision.api.plugin.PluginResource#updateDiskPlugin` |
| `/v10/plugin/installation` | GET | ✅ |  | `com.fr.web.controller.decision.api.plugin.PluginResource#getInstallationPluginList` |
| `/v10/plugin/installation` | DELETE |  |  | `com.fr.web.controller.decision.api.plugin.PluginResource#uninstallPlugin` |
| `/v10/plugin/installation/status` | PUT |  |  | `com.fr.web.controller.decision.api.plugin.PluginResource#changeInstallPluginStatus` |
| `/v10/plugin/installation/status` | GET | ✅ |  | `com.fr.web.controller.decision.api.plugin.PluginResource#getInstallPluginStatusList` |
| `/v10/plugin/installation/update` | GET | ✅ |  | `com.fr.web.controller.decision.api.plugin.PluginResource#getInstallPluginUpdateList` |
| `/v10/plugin/store` | GET | ✅ |  | `com.fr.web.controller.decision.api.plugin.PluginResource#getStorePluginList` |
| `/v10/plugin/store/category` | GET | ✅ |  | `com.fr.web.controller.decision.api.plugin.PluginResource#getStorePluginCategory` |
| `/v10/plugin/store/init` | GET | ✅ |  | `com.fr.web.controller.decision.api.plugin.PluginStoreResource#initPluginStore` |
| `/v10/plugin/store/installation` | POST |  |  | `com.fr.web.controller.decision.api.plugin.PluginResource#installStorePlugin` |
| `/v10/plugin/store/installation` | PUT |  |  | `com.fr.web.controller.decision.api.plugin.PluginResource#updateStorePlugin` |
| `/v10/plugin/store/login` | DELETE |  |  | `com.fr.web.controller.decision.api.plugin.PluginStoreResource#clearLoginInfo` |
| `/v10/plugin/store/login` | GET | ✅ |  | `com.fr.web.controller.decision.api.plugin.PluginStoreResource#getLoginInfo` |
| `/v10/plugin/store/login` | POST |  |  | `com.fr.web.controller.decision.api.plugin.PluginStoreResource#loginPluginStore` |
| `/v10/plugin/store/login/url` | GET | ✅ |  | `com.fr.web.controller.decision.api.plugin.PluginStoreResource#getLoginURL` |
| `/v10/plugin/store/logout` | POST |  |  | `com.fr.web.controller.decision.api.plugin.PluginStoreResource#postLogout` |
| `/v10/plugin/store/project` | GET | ✅ |  | `com.fr.web.controller.decision.api.plugin.PluginStoreResource#getProjectInfo` |
| `/v10/plugin/store/search` | GET | ✅ |  | `com.fr.web.controller.decision.api.plugin.PluginResource#searchStorePlugin` |
| `/v10/plugin/store/update` | POST |  |  | `com.fr.web.controller.decision.api.plugin.PluginStoreResource#updatePluginStore` |
| `/v10/plugin/store/url` | GET | ✅ |  | `com.fr.web.controller.decision.api.plugin.PluginStoreResource#getStoreURL` |
| `/v10/plugin/store/v10/plugin/store` | ANY |  |  | `com.fr.web.controller.decision.api.plugin.PluginStoreResource#getLoginURL` |
| `/v10/plugin/uninstall` | GET | ✅ |  | `com.fr.web.controller.decision.api.plugin.PluginResource#getChargeUninstallPluginList` |
| `/v10/plugin/v10/plugin` | ANY |  |  | `com.fr.web.controller.decision.api.plugin.PluginResource#updateDiskPlugin` |
| `/v10/post/{postId}` | DELETE |  |  | `com.fr.web.controller.decision.api.user.PositionResource#deletePosition` |
| `/v10/post/{postId}` | PUT |  |  | `com.fr.web.controller.decision.api.user.PositionResource#updatePosition` |
| `/v10/post/{postName}` | POST |  |  | `com.fr.web.controller.decision.api.user.PositionResource#addPosition` |
| `/v10/posts` | GET | ✅ |  | `com.fr.web.controller.decision.api.user.PositionResource#getPositions` |
| `/v10/redirect/reply/node/id` | GET | ✅ |  | `com.fr.web.controller.decision.api.redirect.RedirectReplyResource#getCurrentClusterNodeId` |
| `/v10/redirect/reply/v10/redirect/reply` | ANY |  |  | `com.fr.web.controller.decision.api.redirect.RedirectReplyResource#getCurrentClusterNodeId` |
| `/v10/register/attach/upload` | POST |  |  | `com.fr.web.controller.decision.api.register.RegisterResource#uploadAttachLic` |
| `/v10/register/generate/certificate` | GET | ✅ |  | `com.fr.web.controller.decision.api.register.RegisterResource#generateServiceCertificate` |
| `/v10/register/info` | GET | ✅ |  | `com.fr.web.controller.decision.api.register.RegisterResource#getRegisterInfo` |
| `/v10/register/info/exportation` | POST |  |  | `com.fr.web.controller.decision.api.register.RegisterResource#exportRegisterInfo` |
| `/v10/register/info/function` | GET | ✅ |  | `com.fr.web.controller.decision.api.register.RegisterResource#getFunctionDetailList` |
| `/v10/register/info/function/plugin` | GET | ✅ |  | `com.fr.web.controller.decision.api.register.RegisterResource#getPluginPackages` |
| `/v10/register/info/license` | GET | ✅ |  | `com.fr.web.controller.decision.api.register.RegisterResource#getLicenseInfo` |
| `/v10/register/info/local` | GET | ✅ |  | `com.fr.web.controller.decision.api.register.RegisterResource#getLocalRegisterInfo` |
| `/v10/register/info/plugins` | GET | ✅ |  | `com.fr.web.controller.decision.api.register.RegisterResource#getPluginRegisterInfo` |
| `/v10/register/info/project/contents` | GET | ✅ |  | `com.fr.web.controller.decision.api.register.RegisterResource#getProjectContents` |
| `/v10/register/license/captcha` | POST |  |  | `com.fr.web.controller.decision.api.register.RegisterResource#verifyCaptcha` |
| `/v10/register/license/captcha/refresh` | GET | ✅ |  | `com.fr.web.controller.decision.api.register.RegisterResource#refreshCaptcha` |
| `/v10/register/license/dongle/connect` | ANY |  |  | `com.fr.web.controller.decision.api.register.RegisterResource#connectDongleLicense` |
| `/v10/register/license/dongle/validate` | ANY |  |  | `com.fr.web.controller.decision.api.register.RegisterResource#validateDongleLicense` |
| `/v10/register/license/upload` | PUT |  |  | `com.fr.web.controller.decision.api.register.RegisterResource#uploadRegisterLic` |
| `/v10/register/module/info` | GET | ✅ |  | `com.fr.web.controller.decision.api.register.RegisterResource#getAllModuleInfo` |
| `/v10/register/plugin/attach/upload` | POST |  |  | `com.fr.web.controller.decision.api.register.RegisterResource#uploadAttachPluginLic` |
| `/v10/register/plugin/license/upload` | PUT |  |  | `com.fr.web.controller.decision.api.register.RegisterResource#uploadPluginLic` |
| `/v10/register/private/cloud` | POST |  |  | `com.fr.web.controller.decision.api.register.RegisterResource#connectPrivateCloudServer` |
| `/v10/register/private/cloud/disconnection` | POST |  |  | `com.fr.web.controller.decision.api.register.RegisterResource#disconnectPrivateCloudServer` |
| `/v10/register/public/cloud` | POST |  |  | `com.fr.web.controller.decision.api.register.RegisterResource#connectPublicCloudServer` |
| `/v10/register/public/cloud/disconnection` | POST |  |  | `com.fr.web.controller.decision.api.register.RegisterResource#disconnectPublicCloudServer` |
| `/v10/register/remove` | POST |  |  | `com.fr.web.controller.decision.api.register.RegisterResource#removeLicense` |
| `/v10/register/remove` | GET | ✅ |  | `com.fr.web.controller.decision.api.register.RegisterResource#removeLicenseCheck` |
| `/v10/register/remove/captcha` | GET | ✅ |  | `com.fr.web.controller.decision.api.register.RegisterResource#generateRandomCaptcha` |
| `/v10/register/setting/overdue` | GET | ✅ |  | `com.fr.web.controller.decision.api.register.RegisterResource#getOverdue` |
| `/v10/register/setting/overdue` | PUT |  |  | `com.fr.web.controller.decision.api.register.RegisterResource#setOverdue` |
| `/v10/register/v10/register` | ANY |  |  | `com.fr.web.controller.decision.api.register.RegisterResource#getAllModuleInfo` |
| `/v10/report/frequency/log` | POST |  |  | `com.fr.web.controller.log.IntelliLogResource#searchReportFrequencyLog` |
| `/v10/report/label/{labelId}` | PUT |  |  | `com.fr.decision.extension.report.api.entry.ReportLabelResource#editReportLabel` |
| `/v10/report/template/paras` | GET | ✅ | ✅ | `com.fr.decision.extension.report.api.template.ReportTemplateResource#getReportTemplateParas` |
| `/v10/report/templates/all/authentication` | GET | ✅ |  | `com.fr.decision.extension.report.api.template.ReportTemplateResource#getAuthenticatedTemplateTreeNodes` |
| `/v10/role` | POST |  |  | `com.fr.web.controller.decision.api.user.CustomRoleResource#addRole` |
| `/v10/role/{roleId}` | DELETE |  |  | `com.fr.web.controller.decision.api.user.CustomRoleResource#deleteRole` |
| `/v10/role/{roleId}` | PUT |  |  | `com.fr.web.controller.decision.api.user.CustomRoleResource#editRole` |
| `/v10/role/{roleId}` | GET | ✅ |  | `com.fr.web.controller.decision.api.user.CustomRoleResource#getRole` |
| `/v10/roles` | GET | ✅ |  | `com.fr.web.controller.decision.api.user.CustomRoleResource#getRoleList` |
| `/v10/schedule/executing` | GET | ✅ |  | `com.fr.web.controller.schedule.web.api.ScheduleTaskResource#getExecutingTask` |
| `/v10/schedule/info/executing` | GET | ✅ |  | `com.fr.web.controller.schedule.web.api.ScheduleTaskResource#getExecutingJobInfo` |
| `/v10/schedule/record/deletes` | POST |  |  | `com.fr.web.controller.schedule.web.api.ScheduleRecordResource#deleteTaskRecordByIds` |
| `/v10/schedule/record/deletes/all` | POST |  |  | `com.fr.web.controller.schedule.web.api.ScheduleRecordResource#deleteTaskRecordByIds` |
| `/v10/schedule/record/list` | GET | ✅ |  | `com.fr.web.controller.schedule.web.api.ScheduleRecordResource#getScheduleRecord` |
| `/v10/schedule/record/search` | POST |  | ✅ | `com.fr.web.controller.schedule.web.api.ScheduleRecordResource#searchScheduleRecord` |
| `/v10/schedule/setting` | GET | ✅ |  | `com.fr.web.controller.schedule.web.api.ScheduleSettingsResource#getSettings` |
| `/v10/schedule/setting/preservation` | POST |  |  | `com.fr.web.controller.schedule.web.api.ScheduleSettingsResource#saveSettings` |
| `/v10/schedule/task` | POST |  | ✅ | `com.fr.web.controller.schedule.web.api.ScheduleTaskResource#addTask` |
| `/v10/schedule/task` | PUT |  | ✅ | `com.fr.web.controller.schedule.web.api.ScheduleTaskResource#updateTask` |
| `/v10/schedule/task/deletes` | POST |  | ✅ | `com.fr.web.controller.schedule.web.api.ScheduleTaskResource#deleteTasksByIds` |
| `/v10/schedule/task/deletes/all` | POST |  | ✅ | `com.fr.web.controller.schedule.web.api.ScheduleTaskResource#deleteTaskRecordByIds` |
| `/v10/schedule/task/ftp/test` | POST |  |  | `com.fr.web.controller.schedule.web.api.ScheduleTaskResource#testFtp` |
| `/v10/schedule/task/list/{privilegeType}` | GET | ✅ | ✅ | `com.fr.web.controller.schedule.web.api.ScheduleTaskResource#getScheduleTaskInfo` |
| `/v10/schedule/task/listAll/{privilegeType}` | GET | ✅ | ✅ | `com.fr.web.controller.schedule.web.api.ScheduleTaskResource#getScheduleTaskInfo` |
| `/v10/schedule/task/log/details` | GET | ✅ | ✅ | `com.fr.web.controller.schedule.web.api.ScheduleTaskLogResource#getDetailsById` |
| `/v10/schedule/task/log/info` | POST |  | ✅ | `com.fr.web.controller.schedule.web.api.ScheduleTaskLogResource#getTaskLogInfo` |
| `/v10/schedule/task/log/manual/clean` | GET | ✅ | ✅ | `com.fr.web.controller.schedule.web.api.ScheduleTaskLogResource#cleanTaskLog` |
| `/v10/schedule/task/log/save` | GET | ✅ | ✅ | `com.fr.web.controller.schedule.web.api.ScheduleTaskLogResource#saveScheduleTaskLog` |
| `/v10/schedule/task/log/search` | POST |  | ✅ | `com.fr.web.controller.schedule.web.api.ScheduleTaskLogResource#searchScheduleTaskLog` |
| `/v10/schedule/task/names` | GET | ✅ | ✅ | `com.fr.web.controller.schedule.web.api.ScheduleTaskResource#changeScheduleState` |
| `/v10/schedule/task/restriction` | POST |  |  | `com.fr.web.controller.schedule.web.api.ScheduleTaskResource#changeScheduleState` |
| `/v10/schedule/task/search` | POST |  | ✅ | `com.fr.web.controller.schedule.web.api.ScheduleTaskResource#searchScheduleTasks` |
| `/v10/schedule/task/sftp/test` | POST |  |  | `com.fr.web.controller.schedule.web.api.ScheduleTaskResource#testSFtp` |
| `/v10/schedule/task/{taskId}/once` | POST |  | ✅ | `com.fr.web.controller.schedule.web.api.ScheduleTaskResource#onceStartTask` |
| `/v10/schedule/task/{taskId}/state` | POST |  | ✅ | `com.fr.web.controller.schedule.web.api.ScheduleTaskResource#changeScheduleState` |
| `/v10/schedule/task/{taskName}/exists` | GET | ✅ | ✅ | `com.fr.web.controller.schedule.web.api.ScheduleTaskResource#checkTaskExits` |
| `/v10/schedule/trigger` | POST |  |  | `com.fr.web.controller.schedule.web.api.ScheduleTaskResource#checkTrigger` |
| `/v10/schedule/v10/schedule` | ANY |  |  | `com.fr.web.controller.schedule.web.api.ScheduleRecordResource#deleteTaskRecordByIds` |
| `/v10/schedule/v10/schedule` | ANY |  |  | `com.fr.web.controller.schedule.web.api.ScheduleSettingsResource#saveSettings` |
| `/v10/schedule/v10/schedule` | ANY |  |  | `com.fr.web.controller.schedule.web.api.ScheduleTaskLogResource#cleanTaskLog` |
| `/v10/schedule/v10/schedule` | ANY |  |  | `com.fr.web.controller.schedule.web.api.ScheduleTaskResource#getExecutingJobInfo` |
| `/v10/security/access` | GET | ✅ |  | `com.fr.web.controller.decision.api.security.SecurityResource#getAccessControl` |
| `/v10/security/access` | PUT |  |  | `com.fr.web.controller.decision.api.security.SecurityResource#putAccessControl` |
| `/v10/security/block/ip` | GET | ✅ |  | `com.fr.web.controller.decision.api.security.SecurityResource#getBlockIpList` |
| `/v10/security/block/ip/{id}` | DELETE |  |  | `com.fr.web.controller.decision.api.security.SecurityResource#deleteBlockIp` |
| `/v10/security/security` | GET | ✅ |  | `com.fr.web.controller.decision.api.security.SecurityResource#getSecurity` |
| `/v10/security/security` | PUT |  |  | `com.fr.web.controller.decision.api.security.SecurityResource#putSecurity` |
| `/v10/security/v10/security` | ANY |  |  | `com.fr.web.controller.decision.api.security.SecurityResource#previewWatermark` |
| `/v10/security/watermark` | GET | ✅ |  | `com.fr.web.controller.decision.api.security.SecurityResource#getWatermark` |
| `/v10/security/watermark` | PUT |  |  | `com.fr.web.controller.decision.api.security.SecurityResource#setWatermark` |
| `/v10/security/watermark/preview` | POST |  |  | `com.fr.web.controller.decision.api.security.SecurityResource#previewWatermark` |
| `/v10/serverdatasets` | GET | ✅ | ✅ | `com.fr.web.controller.decision.api.dataset.DataSetResource#getServerDataSets` |
| `/v10/session` | POST |  |  | `com.fr.decision.extension.report.api.session.ReportSessionResource#getReportSession` |
| `/v10/session/cross/origin` | GET | ✅ |  | `com.fr.decision.extension.report.api.session.ReportSessionResource#getReportSessionCrossOrigin` |
| `/v10/sms/log` | POST |  |  | `com.fr.web.controller.log.IntelliLogResource#getSMSRecord` |
| `/v10/superuser` | POST |  |  | `com.fr.plugin.decision.superuser.controller.SuperUserController#addUser` |
| `/v10/superuser` | DELETE |  |  | `com.fr.plugin.decision.superuser.controller.SuperUserController#deleteUsers` |
| `/v10/superuser` | PUT |  |  | `com.fr.plugin.decision.superuser.controller.SuperUserController#editUser` |
| `/v10/superuser/list` | GET | ✅ |  | `com.fr.plugin.decision.superuser.controller.SuperUserController#getExtraUsers` |
| `/v10/superuser/v10/superuser` | ANY |  |  | `com.fr.plugin.decision.superuser.controller.SuperUserController#getExtraUsers` |
| `/v10/synchronize/close` | PUT |  |  | `com.fr.web.controller.decision.api.user.SynchronizationResource#closeSync` |
| `/v10/synchronize/close/status` | GET | ✅ |  | `com.fr.web.controller.decision.api.user.SynchronizationResource#getSyncCloseStatus` |
| `/v10/synchronize/dataset` | GET | ✅ |  | `com.fr.web.controller.decision.api.user.SynchronizationResource#getSyncDataSet` |
| `/v10/synchronize/dataset` | PUT |  |  | `com.fr.web.controller.decision.api.user.SynchronizationResource#setSyncDataSet` |
| `/v10/synchronize/schedule/time` | GET | ✅ |  | `com.fr.web.controller.decision.api.user.SynchronizationResource#getNextScheduleTime` |
| `/v10/synchronize/source` | GET | ✅ |  | `com.fr.web.controller.decision.api.user.SynchronizationResource#getSyncSource` |
| `/v10/synchronize/status` | GET | ✅ |  | `com.fr.web.controller.decision.api.user.SynchronizationResource#getSyncStatus` |
| `/v10/synchronize/v10/synchronize` | ANY |  |  | `com.fr.web.controller.decision.api.user.SynchronizationResource#getSyncStatus` |
| `/v10/template/auth` | POST |  |  | `com.fr.web.controller.decision.api.template.TemplateAuthResource#getTemplateAuth` |
| `/v10/template/auth/config` | GET | ✅ |  | `com.fr.web.controller.decision.api.template.TemplateAuthResource#getTemplateAuthConfig` |
| `/v10/template/auth/config` | PUT |  |  | `com.fr.web.controller.decision.api.template.TemplateAuthResource#setTemplateAuthConfig` |
| `/v10/template/auth/recovery` | POST |  |  | `com.fr.web.controller.decision.api.template.TemplateAuthResource#authorityRecovery` |
| `/v10/template/auth/recovery/preview` | POST |  |  | `com.fr.web.controller.decision.api.template.TemplateAuthResource#authorityPreviewIfRecovery` |
| `/v10/template/auth/{carrierType}` | PUT |  |  | `com.fr.web.controller.decision.api.template.TemplateAuthResource#updateTemplateAuth` |
| `/v10/template/v10/template` | ANY |  |  | `com.fr.web.controller.decision.api.template.TemplateAuthResource#authorityPreviewIfRecovery` |
| `/v10/template/visit` | GET | ✅ |  | `com.fr.web.controller.log.IntelliLogResource#getTemplateVisit` |
| `/v10/template/{templateId}` | PUT |  |  | `com.fr.decision.extension.report.api.entry.TemplateResource#editTemplate` |
| `/v10/templates/all` | GET | ✅ | ✅ | `com.fr.decision.extension.report.api.template.ReportTemplateResource#getAllTemplateTreeNodes` |
| `/v10/templates/batch` | POST |  |  | `com.fr.decision.extension.report.api.entry.TemplateResource#getBatchTemplateTreeNodes` |
| `/v10/update` | DELETE |  |  | `com.fr.web.controller.decision.api.update.UpdateResource#deleteBackup` |
| `/v10/update` | POST |  |  | `com.fr.web.controller.decision.api.update.UpdateResource#updateJar` |
| `/v10/update/backup/info` | GET | ✅ |  | `com.fr.web.controller.decision.api.update.UpdateResource#getBackupList` |
| `/v10/update/config` | GET | ✅ |  | `com.fr.web.controller.decision.api.update.UpdateResource#getUpdatePushConfig` |
| `/v10/update/config` | PUT |  |  | `com.fr.web.controller.decision.api.update.UpdateResource#setUpdatePushConfig` |
| `/v10/update/latest/jar/time` | GET | ✅ |  | `com.fr.web.controller.decision.api.update.UpdateResource#getLatestJarTime` |
| `/v10/update/log` | GET | ✅ |  | `com.fr.web.controller.decision.api.update.UpdateResource#getUpdateLog` |
| `/v10/update/process` | GET | ✅ |  | `com.fr.web.controller.decision.api.update.UpdateResource#getUpdateProcess` |
| `/v10/update/rollback/{id}` | POST |  |  | `com.fr.web.controller.decision.api.update.UpdateResource#rollback` |
| `/v10/update/v10/update` | ANY |  |  | `com.fr.web.controller.decision.api.update.UpdateResource#getBackupList` |
| `/v10/user` | POST |  |  | `com.fr.web.controller.decision.api.user.UserResource#addUser` |
| `/v10/user` | PUT |  |  | `com.fr.web.controller.decision.api.user.UserResource#editUser` |
| `/v10/user/account` | PUT |  | ✅ | `com.fr.web.controller.decision.api.user.UserResource#changeUserAccount` |
| `/v10/user/account` | GET | ✅ | ✅ | `com.fr.web.controller.decision.api.user.UserResource#getUserAccount` |
| `/v10/user/behavior/log` | POST |  |  | `com.fr.web.controller.log.IntelliLogResource#searchUserBehaviorLog` |
| `/v10/user/captcha` | POST |  |  | `com.fr.web.controller.decision.api.user.UserResource#sendUserCaptcha` |
| `/v10/user/captcha` | GET | ✅ |  | `com.fr.web.controller.decision.api.user.UserResource#sendUserCaptchaUnsafe` |
| `/v10/user/config` | GET | ✅ |  | `com.fr.web.controller.decision.api.user.UserResource#getUserLoginAuthenticConfig` |
| `/v10/user/config` | PUT |  |  | `com.fr.web.controller.decision.api.user.UserResource#setUserLoginAuthenticConfig` |
| `/v10/user/department/post` | PUT |  |  | `com.fr.web.controller.decision.api.user.UserResource#updateUserDepRoles` |
| `/v10/user/departments` | GET | ✅ |  | `com.fr.web.controller.decision.api.user.UserResource#getUserDepartmentTree` |
| `/v10/user/email` | PUT |  |  | `com.fr.web.controller.decision.api.user.UserResource#changeUserEmail` |
| `/v10/user/forbid` | PUT |  |  | `com.fr.web.controller.decision.api.user.UserResource#forbidUser` |
| `/v10/user/info` | PUT |  |  | `com.fr.web.controller.decision.api.user.UserResource#editUserInfo` |
| `/v10/user/infos` | GET | ✅ |  | `com.fr.web.controller.decision.api.user.UserResource#getEachPlatformUserInfos` |
| `/v10/user/language` | GET | ✅ |  | `com.fr.web.controller.decision.api.user.UserResource#getUserLanguage` |
| `/v10/user/language` | PUT |  |  | `com.fr.web.controller.decision.api.user.UserResource#setUserLanguage` |
| `/v10/user/mobile` | PUT |  |  | `com.fr.web.controller.decision.api.user.UserResource#changeUserMobile` |
| `/v10/user/passport/test` | POST |  |  | `com.fr.web.controller.decision.api.user.UserResource#testPassport` |
| `/v10/user/password` | PUT |  |  | `com.fr.web.controller.decision.api.user.UserResource#resetPassword` |
| `/v10/user/remind` | GET | ✅ |  | `com.fr.web.controller.decision.api.user.UserConfigResource#getUserRemindConfig` |
| `/v10/user/remind` | PUT |  |  | `com.fr.web.controller.decision.api.user.UserConfigResource#setUserRemindConfig` |
| `/v10/user/roles` | GET | ✅ |  | `com.fr.web.controller.decision.api.user.UserResource#getUserRoles` |
| `/v10/user/roles` | PUT |  |  | `com.fr.web.controller.decision.api.user.UserResource#updateUserRoles` |
| `/v10/user/sync/fuse` | GET | ✅ |  | `com.fr.web.controller.decision.api.user.UserConfigResource#getSyncFuseConfig` |
| `/v10/user/sync/fuse` | PUT |  |  | `com.fr.web.controller.decision.api.user.UserConfigResource#setSyncFuseConfig` |
| `/v10/user/sync/remind` | GET | ✅ |  | `com.fr.web.controller.decision.api.user.UserConfigResource#getSyncRemindConfig` |
| `/v10/user/sync/remind` | PUT |  |  | `com.fr.web.controller.decision.api.user.UserConfigResource#setSyncRemindConfig` |
| `/v10/user/v10/user` | ANY |  |  | `com.fr.web.controller.decision.api.user.UserConfigResource#setSyncFuseConfig` |
| `/v10/user/{userId}` | GET | ✅ |  | `com.fr.web.controller.decision.api.user.UserResource#getUser` |
| `/v10/users` | DELETE |  | ✅ | `com.fr.web.controller.decision.api.user.UserResource#deleteUsers` |
| `/v10/users` | GET/POST |  | ✅ | `com.fr.web.controller.decision.api.user.UserResource#getAllUsers` |
| `/v10/users/all` | DELETE |  | ✅ | `com.fr.web.controller.decision.api.user.UserResource#cleanupUsers` |
| `/v10/users/all/{platformType}` | DELETE |  | ✅ | `com.fr.web.controller.decision.api.user.UserResource#cleanupEachPlatformUsers` |
| `/v10/users/all/{platformType}` | PUT |  | ✅ | `com.fr.web.controller.decision.api.user.UserResource#selectEachPlatformUsers` |
| `/v10/users/product` | POST |  | ✅ | `com.fr.web.controller.decision.api.user.UserResource#getAllUsersByProductTypes` |
| `/v10/users/product/edit/open` | PUT |  | ✅ | `com.fr.web.controller.decision.api.user.UserResource#openUserProductEdit` |
| `/v10/users/{platformType}` | POST |  | ✅ | `com.fr.web.controller.decision.api.user.UserResource#getEachPlatformUsers` |
| `/v10/users/{platformType}` | PUT |  | ✅ | `com.fr.web.controller.decision.api.user.UserResource#updateEachPlatformUsers` |
| `/v10/v10` | ANY |  |  | `com.fr.decision.extension.report.api.entry.ReportEntryResource#showObsoletePathEntry` |
| `/v10/v10` | ANY |  |  | `com.fr.decision.extension.report.api.entry.ReportLabelResource#editReportLabel` |
| `/v10/v10` | ANY |  |  | `com.fr.decision.extension.report.api.entry.TemplateResource#getBatchTemplateTreeNodes` |
| `/v10/v10` | ANY |  |  | `com.fr.decision.extension.report.api.session.ReportSessionResource#getReportSessionCrossOrigin` |
| `/v10/v10` | ANY |  |  | `com.fr.decision.extension.report.api.template.ReportTemplateResource#getAllTemplateTreeNodes` |
| `/v10/v10` | ANY |  |  | `com.fr.web.controller.decision.api.config.LoginLockResource#unlockByIds` |
| `/v10/v10` | ANY |  |  | `com.fr.web.controller.decision.api.dataset.DataSetResource#verification` |
| `/v10/v10` | ANY |  |  | `com.fr.web.controller.decision.api.deployment.DeploymentResource#checkFileServer` |
| `/v10/v10` | ANY |  |  | `com.fr.web.controller.decision.api.entry.DecisionMgrResource#getDecisionMgrModule` |
| `/v10/v10` | ANY |  |  | `com.fr.web.controller.decision.api.entry.DirectoryResource#searchDirectoryEntryTreeNodes` |
| `/v10/v10` | ANY |  |  | `com.fr.web.controller.decision.api.entry.EntryResource#showEntry` |
| `/v10/v10` | ANY |  |  | `com.fr.web.controller.decision.api.entry.FavoriteResource#removeFavoriteEntry` |
| `/v10/v10` | ANY |  |  | `com.fr.web.controller.decision.api.entry.FileEntryResource#editFileEntry` |
| `/v10/v10` | ANY |  |  | `com.fr.web.controller.decision.api.entry.HomePageResource#getHomePages` |
| `/v10/v10` | ANY |  |  | `com.fr.web.controller.decision.api.entry.LinkResource#editLink` |
| `/v10/v10` | ANY |  |  | `com.fr.web.controller.decision.api.file.FileNodeResource#getAllClassTreeNodes` |
| `/v10/v10` | ANY |  |  | `com.fr.web.controller.decision.api.international.InternationalResource#removeAllInternationalRecords` |
| `/v10/v10` | ANY |  |  | `com.fr.web.controller.decision.api.log.LogResource#refreshLogSize` |
| `/v10/v10` | ANY |  |  | `com.fr.web.controller.decision.api.trash.UserTrashResource#selectAllDepPostUsers` |
| `/v10/v10` | ANY |  |  | `com.fr.web.controller.decision.api.user.CustomRoleResource#getRoleList` |
| `/v10/v10` | ANY |  |  | `com.fr.web.controller.decision.api.user.DepartmentResource#getDepartmentTree` |
| `/v10/v10` | ANY |  |  | `com.fr.web.controller.decision.api.user.PositionResource#getDepartmentPostTree` |
| `/v10/v10` | ANY |  |  | `com.fr.web.controller.decision.api.user.UserResource#testPassport` |
| `/v10/v10` | ANY |  |  | `com.fr.web.controller.log.IntelliLogResource#searchVisitReportLog` |
| `/v10/view/entry/tree` | GET | ✅ |  | `com.fr.web.controller.decision.api.entry.EntryResource#getEntryTree` |
| `/v10/visit/report/log` | POST |  |  | `com.fr.web.controller.log.IntelliLogResource#searchVisitReportLog` |
| `/v10/visit/system/log` | POST |  |  | `com.fr.web.controller.log.IntelliLogResource#searchVisitSystemLog` |
| `/v10/warning/preview` | GET | ✅ |  | `com.fr.web.controller.decision.api.prewarning.PrewarningResource#getPrewarningConfig` |
| `/v10/warning/preview` | PUT |  |  | `com.fr.web.controller.decision.api.prewarning.PrewarningResource#setPrewarningConfig` |
| `/v10/warning/preview/global/proposal` | GET | ✅ |  | `com.fr.decision.extension.report.api.prewarning.ReportPrewarningResource#getGlobalProposal` |
| `/v10/warning/preview/info/collector` | GET | ✅ |  | `com.fr.web.controller.decision.api.prewarning.PrewarningResource#getSystemInfoCollector` |
| `/v10/warning/preview/info/collector` | POST |  |  | `com.fr.web.controller.decision.api.prewarning.PrewarningResource#setSystemInfoCollector` |
| `/v10/warning/preview/memory/high` | GET | ✅ |  | `com.fr.web.controller.decision.api.prewarning.PrewarningResource#isMemoryHighLoad` |
| `/v10/warning/preview/memory/percent` | GET | ✅ |  | `com.fr.web.controller.decision.api.prewarning.PrewarningResource#getPercent` |
| `/v10/warning/preview/report/proposal` | GET | ✅ |  | `com.fr.decision.extension.report.api.prewarning.ReportPrewarningResource#getReportProposal` |
| `/v10/warning/preview/session/history` | GET | ✅ |  | `com.fr.web.controller.decision.api.prewarning.PrewarningResource#getAllHistorySessionInfo` |
| `/v10/warning/preview/session/kill` | GET | ✅ |  | `com.fr.web.controller.decision.api.prewarning.PrewarningResource#getKillSession` |
| `/v10/warning/preview/session/kill` | DELETE |  |  | `com.fr.web.controller.decision.api.prewarning.PrewarningResource#killSessionById` |
| `/v10/warning/preview/session/live` | GET | ✅ |  | `com.fr.web.controller.decision.api.prewarning.PrewarningResource#getLiveSession` |
| `/v10/warning/preview/system/proposal` | GET | ✅ |  | `com.fr.web.controller.decision.api.prewarning.PrewarningResource#getMemoryProposal` |
| `/v10/warning/preview/total/memory` | GET | ✅ |  | `com.fr.web.controller.decision.api.prewarning.PrewarningResource#getTotalMemory` |
| `/v10/warning/preview/v10/warning/preview` | ANY |  |  | `com.fr.decision.extension.report.api.prewarning.ReportPrewarningResource#getGlobalProposal` |
| `/v10/warning/preview/v10/warning/preview` | ANY |  |  | `com.fr.web.controller.decision.api.prewarning.PrewarningResource#setSystemInfoCollector` |
| `/v10/workflow/compatible` | POST |  |  | `com.fr.decision.extension.report.api.workflow.WorkflowCompatibleResource#compatible` |
| `/v10/workflow/compatible` | GET | ✅ |  | `com.fr.decision.extension.report.api.workflow.WorkflowCompatibleResource#getCompatible` |
| `/v10/workflow/v10/workflow` | ANY |  |  | `com.fr.decision.extension.report.api.workflow.WorkflowCompatibleResource#getCompatible` |
| `/v10/{datasetname}/datasetcolumns` | GET | ✅ |  | `com.fr.web.controller.decision.api.dataset.DataSetResource#getDataSetColumns` |
| `/v10/{departmentId}/posts` | GET | ✅ |  | `com.fr.web.controller.decision.api.user.PositionResource#getPositionsUnderParentDepartment` |
| `/v10/{departmentId}/posts` | PUT |  |  | `com.fr.web.controller.decision.api.user.PositionResource#updateDepPositions` |
| `/v10/{departmentId}/{postId}/users` | POST |  |  | `com.fr.web.controller.decision.api.trash.UserTrashResource#getDepPostUsers` |
| `/v10/{departmentId}/{postId}/users` | PUT |  |  | `com.fr.web.controller.decision.api.trash.UserTrashResource#updateDepPostUsers` |
| `/v10/{departmentId}/{postId}/users/all` | DELETE |  |  | `com.fr.web.controller.decision.api.trash.UserTrashResource#cleanupDepPostUsers` |
| `/v10/{departmentId}/{postId}/users/all` | PUT |  |  | `com.fr.web.controller.decision.api.trash.UserTrashResource#selectAllDepPostUsers` |
| `/v10/{directoryId}/entries` | GET | ✅ |  | `com.fr.web.controller.decision.api.entry.EntryResource#getEntryTreeNodes` |
| `/v10/{directoryId}/entries/{privilegeType}` | GET | ✅ |  | `com.fr.web.controller.decision.api.entry.EntryResource#getEntryTreeNodes` |
| `/v10/{directoryId}/entries/{privilegeType}/{entryType}` | GET | ✅ |  | `com.fr.web.controller.decision.api.entry.EntryResource#getChildEntryByAuthorityAndEntryType` |
| `/v10/{directoryId}/link` | POST |  |  | `com.fr.web.controller.decision.api.entry.LinkResource#addLink` |
| `/v10/{directoryId}/report/label` | POST |  |  | `com.fr.decision.extension.report.api.entry.ReportLabelResource#addReportLabel` |
| `/v10/{directoryId}/templates` | POST |  |  | `com.fr.decision.extension.report.api.entry.TemplateResource#addTemplates` |
| `/v10/{pId}/departments/posts` | GET | ✅ |  | `com.fr.web.controller.decision.api.user.PositionResource#getDepPositionsUnderParentDepartment` |
| `/v10/{pId}/deposts` | GET | ✅ |  | `com.fr.web.controller.decision.api.user.PositionResource#getDepRolesUnderParentDepRole` |
| `/v10/{pId}/directory` | POST |  |  | `com.fr.web.controller.decision.api.entry.DirectoryResource#addDirectory` |
| `/v10/{roleId}/users` | POST |  |  | `com.fr.web.controller.decision.api.user.UserResource#getRoleUsers` |
| `/v10/{roleId}/users` | PUT |  |  | `com.fr.web.controller.decision.api.user.UserResource#updateRoleUsers` |
| `/v10/{roleId}/users/all` | DELETE |  |  | `com.fr.web.controller.decision.api.user.UserResource#cleanupRoleUsers` |
| `/v10/{roleId}/users/all` | PUT |  |  | `com.fr.web.controller.decision.api.user.UserResource#selectAllRoleUsers` |
| `/v10/{roleId}/users/batch` | PUT |  |  | `com.fr.web.controller.decision.api.user.UserResource#batchUpdateRoleUsers` |
| `/v10/{userId}/roles` | GET | ✅ |  | `com.fr.web.controller.decision.api.user.UserResource#getTargetUserRoles` |
| `/view/ReportServer/**` | ANY |  |  | `com.fr.web.controller.ReportRequestCompatibleService#preview` |
| `/view/ReportServer/view/ReportServer` | ANY |  |  | `com.fr.web.controller.ReportRequestCompatibleService#PllRYAlVkHQFSBt` |
| `/view/chart/calculate/hyperlink` | POST |  |  | `com.fr.web.controller.ChartCalculateHyperlinkService#getHyperlinkGroup` |
| `/view/chart/relate/date` | POST |  |  | `com.fr.web.controller.ChartRefreshRelateDataService#refreshRelateData` |
| `/view/chart/view/chart` | ANY |  |  | `com.fr.web.controller.ChartCalculateHyperlinkService#rHcngxOfUXJUvnc` |
| `/view/chart/view/chart` | ANY |  |  | `com.fr.web.controller.ChartRefreshRelateDataService#NxDTnnQwytestbo` |
| `/view/chart/view/chart` | ANY |  |  | `com.fr.web.controller.ChartWriteHtmlService#HybiQiJVGrMoVpo` |
| `/view/chart/write/html` | POST |  |  | `com.fr.web.controller.ChartWriteHtmlService#writeHtml` |
| `/view/favor/params/v10/query` | GET | ✅ |  | `com.fr.web.controller.FavoriteParamsService#queryFavoriteParams` |
| `/view/favor/params/v10/save` | POST |  |  | `com.fr.web.controller.FavoriteParamsService#saveFavoriteParams` |
| `/view/favor/params/v10/view/favor/params/v10` | ANY |  |  | `com.fr.web.controller.FavoriteParamsService#XMwVwiFdrrhneLw` |
| `/view/form/**` | ANY |  |  | `com.fr.web.controller.FormRequestService#preview` |
| `/view/form/pre/execute/elements` | POST |  |  | `com.fr.web.controller.FormPreExecuteElementsService#preExecuteElements` |
| `/view/form/recalculate/element/title` | POST |  |  | `com.fr.web.controller.FormRecalculateRelationWidgetService#recalculateECTitle` |
| `/view/form/view/form` | ANY |  |  | `com.fr.web.controller.FormGetSourceValueService#ECUPizPMzjEPoGc` |
| `/view/form/view/form` | ANY |  |  | `com.fr.web.controller.FormPreExecuteElementsService#DMeyYxscyNrbrMI` |
| `/view/form/view/form` | ANY |  |  | `com.fr.web.controller.FormRecalculateRelationWidgetService#VLtjigEcRaFiMHu` |
| `/view/form/view/form` | ANY |  |  | `com.fr.web.controller.FormRequestService#bkgOHcGhOvcIJTL` |
| `/view/form/widget/interact` | POST |  |  | `com.fr.web.controller.FormGetSourceValueService#getSourceValue` |
| `/view/para/v10/submit` | POST |  |  | `com.fr.web.controller.ParameterRequestService#submitParameter` |
| `/view/para/v10/view/para/v10` | ANY |  |  | `com.fr.web.controller.ParameterRequestService#lyxjfQNgJgutRFO` |
| `/view/report/**` | ANY |  | ✅ | `com.fr.web.controller.ReportRequestService#preview` |
| `/view/report/dbCommit` | POST |  | ✅ | `com.fr.web.controller.DBCommitService#dbCommit` |
| `/view/report/email/send` | POST |  | ✅ | `com.fr.page.web.controller.EmailSendService#sendEmail` |
| `/view/report/v10/page/conf` | GET | ✅ | ✅ | `com.fr.web.controller.PageRequestService#getPageConfig` |
| `/view/report/v10/page/data` | GET | ✅ | ✅ | `com.fr.web.controller.PageRequestService#getPageContent` |
| `/view/report/v10/page/num` | GET | ✅ | ✅ | `com.fr.web.controller.PageRequestService#getPageNum` |
| `/view/report/v10/page/view/report/v10/page` | ANY |  | ✅ | `com.fr.web.controller.PageRequestService#kFqTHExqXLLNtPL` |
| `/view/report/view/report` | ANY |  | ✅ | `com.fr.page.web.controller.EmailSendService#sendEmail` |
| `/view/report/view/report` | ANY |  | ✅ | `com.fr.web.controller.DBCommitService#ZUqBrdTwDUiWmSh` |
| `/view/report/view/report` | ANY |  | ✅ | `com.fr.web.controller.ReportRequestService#xhavuPczEYTZUEA` |
| `/view/widget/v10/data` | POST |  |  | `com.fr.web.controller.WidgetRequestService#getWidgetData` |
| `/view/widget/v10/view/widget/v10` | ANY |  |  | `com.fr.web.controller.WidgetRequestService#qjiBQlXKXqaXdVf` |
| `/workflow/authority` | GET | ✅ |  | `com.fr.decision.extension.report.api.workflow.WorkflowResource#getAuthority` |
| `/workflow/management` | GET | ✅ |  | `com.fr.decision.extension.report.api.workflow.WorkflowResource#getAllWorkflow` |
| `/workflow/task` | GET | ✅ |  | `com.fr.decision.extension.report.api.workflow.WorkflowResource#getTasks` |
| `/workflow/task/all` | GET | ✅ |  | `com.fr.decision.extension.report.api.workflow.WorkflowResource#getAllTasks` |
| `/workflow/task/status` | GET | ✅ |  | `com.fr.decision.extension.report.api.workflow.WorkflowResource#getTaskStatus` |
| `/workflow/workflow` | ANY |  |  | `com.fr.decision.extension.report.api.workflow.WorkflowResource#getTaskStatus` |

## 重新生成

```bash
python3 <开发工作目录>/route_dump.py     # 需 javap；输出 /tmp/routes.json
```
