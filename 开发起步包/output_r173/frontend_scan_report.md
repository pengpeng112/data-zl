# r173 T2（A 线）前端源码规则扫荡报告

日期：2026-09-01｜工具：`backend/_r173_work/scan_frontend_rules.py`（原始命中 `frontend_scan_raw.json`）｜范围：frontend/src/**/*.ts+*.vue（58 视图 + 全部 ts）

## 逐规则结论（10 条规则全跑，每命中人工定性）

| # | 规则 | 原始命中 | 定性后真问题 |
|---|---|---|---|
| 1 | v-html | 3 | **0**（1 条为注释；2 条在 ai-quality 白名单页，`reportMarkdown.ts:1,33` 逐行 escapeHtml 已验证） |
| 2 | 写按钮无 v-perms | 16 | **6 条不一致（P2）**+4 页零按钮级策略（P3）+6 条向导步骤导航按钮（良性） |
| 3 | 硬编码地址/魔法串 | 32 | **0**（全部为 pure-admin 模板注释 URL：github/element-plus/iconify 文档链接） |
| 4 | 死路由/死 API | 12 视图+24 API | **0 死路由**（12 个全为 components/ 子组件，被父页 import）；**24 个死 API 封装（P3）**（src 运行时+tests 双零引用） |
| 5 | console 残留 | 10 | **P3 聚合**（utils/tree.ts×6、print.ts、useNav.ts 为模板自带；视图层仅 2 条错误路径 console.error/warn，无敏感数据） |
| 6 | 空 catch | 0 | 0 |
| 7 | as any | 70 | **P3 聚合计数**（按 round-8 #12 限流不逐条） |
| 8 | 明文敏感串 | 0 | 0 |
| 9 | 菜单 auths vs 后端权限码 | 36 auths | **0 死码**（36/36 全部存在于后端 `RESOURCE_CATALOG`+`require_permission` 全集 110 码）；35 个后端码前端未消费（信息项：API-only 权限） |
| 10 | 内联事件（img onerror 等） | 0 | 0 |

## 规则 2 明细（P2：同页其他按钮有 v-perms、唯独写按钮缺失）

| 位置 | 按钮 | 同页 v-perms 数 |
|---|---|---|
| views/asset/probe-findings/index.vue:238 | 确认迁移（submitTransition） | 5 |
| views/asset/value-domains/index.vue:269 | 确认（submitConfirm） | 4 |
| views/dict/general/index.vue:191 | 保存类目（saveCategory） | 10 |
| views/dict/general/index.vue:218 | 保存标准项（saveStdItem） | 10 |
| views/dict/general/index.vue:247 | 保存系统项（saveSysItem） | 10 |
| views/dict/general/index.vue:288 | 保存映射（saveMapping） | 10 |

定性把握：高（同文件内其他按钮已用 v-perms 证明页面策略存在，漏网按钮属遗漏非策略）。后端仍有 require_permission 兜底，故为 UI 纵深缺失而非越权漏洞。

## 规则 2 补充（P3：整页零 v-perms 但路由有 auths）

asset/admin（保存按钮×2）、identity/persons:100、identity/roles:117、ops/runs:107 —— 路由级 auths（如 ops.run.view）已限页，按钮级未加；与上述 3 页策略不一致，建议统一。

## 死 API 清单（24，P3）

asset.ts：getRelationAuthorityRule/upsertSource/retryAiQualityJob/attachAiQualityResult/getAiSessions；dict.ts：upsertMedicalMapping/getDictVersions；identity.ts：getProfileChangeRequests/createIdentityChangeRequest；metadata.ts：getChangeImpact/getMetadataSnapshots/getMetadataSnapshotDetail；ops.ts：submitSqlTemplate/approveSqlTemplate/rejectSqlTemplate/listSqlRuns/getSqlRun；query-center.ts：reviewFeedback/fetchFeedback/resolveContext/fetchContext/fetchLineageImpact；recipes.ts：getRecipe；user.ts：getAuthMe。
注：其中 retryAiQualityJob/attachAiQualityResult（ai-quality 域）与 getSqlRun/listSqlRuns（ops 域）后端端点存在且在 S 线黑名单/探针范围内——API 封装已写好但 UI 未绑定，属「功能半接入」信号，与 166/167 后置项关联。

## as any 聚合（70 处，P3 限流）

分布前列：api/asset.ts、views/asset/graph 相关、store；不逐条（round-8 #12 裁决）。
