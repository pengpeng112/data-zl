先通读方案全文，再对照 `backend/`、`frontend/` 源码做只读抽查，逐条给出同意/反对/疑问。方案已读完。接下来按条目对照源码抽查，重点核验行号、行为与修复方案是否成立。以下为独立只读审查结论。证据均对照当前仓库源码抽查；未读 `review/` 下除本方案外的任何文件，未改任何文件。

---

## 0. 背景与目标 / 设计原则

**疑问。**  
引用：「一次性完成：P0→P6 七批顺序执行…供单一执行 AI 在一个长会话内完成全部整改」。

**理由：** 发现多为真实问题，但把正确性、安全、性能、前端交互、类型收敛和测试补强捆成一轮，与仓库协作约定（主 AI 拆可独立验收子任务、禁止同时改同一文件）冲突。同一批前端文件（`quality/index.vue`、`tables/index.vue`、`graph/index.vue`、`query-center/queries/index.vue`）与 146 剩余界面项高度重叠。  
**风险：** 大会话中断后半成品难续；与 146 并行会互相覆盖；全量门禁绿不能证明浏览器路径无回归（本方案未要求浏览器验收）。

---

## 1. 硬边界

**同意（边界本身）。**  
引用：「零迁移…零外部动作…不改 126/144/146/149/151/152 既有语义」。

**理由：** 与 AGENTS.md 一致。  
**风险：** 后文 P1-4 新增权限码、P3-5 删 RESOURCE_CATALOG、P3-8 `git mv`、§6 改起步包文档，会直接撞上本条。边界写了却未在任务表里强制自洽。

---

## 2.1 后端正确性（A 组）

### A1 pymssql 按 `dict.values()` 绑参
**同意问题存在；疑问修复配方。**  
引用：「`cursor.execute(sql, tuple(params.values()))` 按 dict 插入序绑参」。源码 `db_connectors.py:570-574` 属实。

**理由：** pymssql 位置参数与 SQL 占位符顺序不一致时会绑错。P0-1 要用正则抽 `%(name)s`；若实际 SQL 是 `%s`/`?`，重排无效。`his_identity_sync.py` 等调用是 `params={"max_rows": ...}`，形态未必是命名占位符。  
**风险：** 假修复 + 假绿测试；生产若很少走 SqlServer，标「高」可能挤占真正高危项。

### A2 COL_NULL_COMMENT 全表拉 Python
**同意。**  
引用：「把全表 `AssetColumn`（10 万+行）拉进 Python」。`quality.py:246-251` 确为 `select(AssetColumn)...all()`；`:356-371` 已有 `group_by` 示范。生产字段量级约 9 万+，判断成立。

**风险：** 聚合后阈值语义必须保持 `null_rate > 0.5`；改 SQL 易把 `comment` 空串/NULL 口径改掉，产生 finding 数量漂移。

### A3 失败分支未 rollback
**同意。**  
引用：「`except: run.status="failed"; db.commit()`」。实际在 `quality.py:937-941`（方案写约 :945，行号略偏）。DB 异常后 session 需 rollback，否则 `PendingRollbackError`，run 可卡 `running`。

**风险：** 「新会话/同会话恢复」写不清，执行 AI 可能在已脏 session 上再 commit。

### A4 truncated off-by-one
**同意问题；必须与 fetch 策略配套。**  
引用：「`truncated = len(rows) >= max_rows`」。`query_runner.py:279` 属实。各连接器 `fetchmany(safe_limit)` 也是取恰好 `max_rows`（如 `:264`、`:353`、`:439`、`:575`）。

**理由：** 只把 `>=` 改成 `>` 且不取 `max_rows+1`，截断将永远为 false。P2 已写配套，不能漏。  
**风险：** 144 结果 digest/截断口径变化，影响既有 run 记录解释。

### A5 `to_cols[-1]` 补位
**同意。**  
引用：「字段映射数量不等时 `to_cols[-1]` 补位」。`relation_reviews.py:245-246` 属实。P2 改为 400 正确。

**风险：** 前端映射表若依赖「缺列时复用最后一列」的旧展示，会从静默错变成硬失败（这是好事，但要有 UI 提示）。

### A6 SSH 隧道 sleep 0.5 只 poll 一次
**同意。**  
引用：「`time.sleep(0.5)` 后仅 poll 一次」。`jhemr_identity_adapter.py:307-317` 属实：进程仍活就被当成就绪。

**风险：** 等待循环 10s 会拉长失败路径；stderr 管道若不读可能撑满（方案提了读尾行，需真正 drain）。

### A7 alerts 失败伪装空列表
**同意。**  
引用：「`except Exception: rows=[]`」。`identity_sync.py:70-73` 属实。

**风险：** 前端若把空数组当「无告警」，改成 error 结构后必须同步契约，否则告警页空白或类型报错。此项只写后端，P4 未覆盖该页。

### A8 `init_oracle_client` 吞异常
**同意（低优）。**  
引用：「`except: pass`」。`db_connectors.py:228-231` 属实。注释写「已初始化或路径无效」——合法二次 init 与配错混在一起。

**风险：** 改成 warning 后，已初始化场景会刷日志；不要改成 raise，否则 thick 二次 init 会把连接打挂。

### A9 版本号 `max_ver+1` 无重试
**同意（低优）。**  
引用：「`query_intake.py:194-201`、`metric_service.py:235-242`」。两处均 `max_ver+1` 后插入，无 `IntegrityError` 重试。

**风险：** 只重试一次在突发双提交下仍可能 500；需确认唯一约束字段，避免误捕其他完整性错误后静默错版。

### A10 分类过滤
**疑问。**  
引用：「分类过滤 `==` 与 `in` 双条件冗余」。`metrics.py:160-161` 实际是  
`(d.category or "") == category or category in (d.category or "")`，是精确匹配 **或** 子串，不是无意义重复。

**理由：** 下推 SQL 时若只留 `==`，会丢掉子串命中；若下推 `LIKE`，又会扩大命中。  
**风险：** 看板「48项核心制度」结果集变化，被当成 126/144 语义回退。

### A11 SqlServer `fetch_metadata` 无上限
**同意问题；反对「补 LIMIT 5000」。**  
引用：「SqlServer fetch_metadata 无 LIMIT（Oracle/PG/MySQL 均有）」。`:586-597` 无上限属实；Oracle 用 `ROWNUM`（`:283`），PG/MySQL 用 `LIMIT`。

**理由：** SQL Server 不支持 `LIMIT`，应 `SELECT TOP` 或 `OFFSET FETCH`。  
**风险：** 原样写 `LIMIT` 会让 SqlServer 元数据采集直接语法失败。

---

## 2.2 后端安全（B 组）

### B1 CSRF `startswith`
**同意。**  
引用：「`startswith` 前缀匹配，`http://<allowed>.evil.com` 可绕过」。`auth.py:71-74` 属实。P0-2 精确相等 + 保留 `X-Requested-With` 合理。

**理由：** 前端 axios 默认带 `X-Requested-With`（`utils/http/index.ts:40`），SPA 请求多数已绕过 Origin 检查；真正危险面是无该头的 cookie POST（login/refresh）。  
**风险：** `rstrip("/")` 后比较仍可能漏端口/大小写/IPv6；测试必须覆盖「有/无 X-Requested-With」两条。

### B2 diff 直出 SQL
**同意。**  
引用：「`versions/{v}/diff` 直出 `current_sql/parent_sql`」。`queries.py:596-627` 有 `query.view` 路由依赖，但无 `ai.sql.full_read`；对比 `_serialize_version_for_read`（`:42-58`）口径不一致。

**风险：** 有 `query.view` 无 `full_read` 的角色会突然看不到 diff SQL。这是收口，不是回归，但 144 运营页要同步掩码展示。

### B3 原始异常回显
**同意。**  
引用三处：`quality_sql_runner.py:152-153` `note: str(exc)[:500]`；`ai.py:652-653` 把带 note 的 `result` 塞进 HTTP 400；`queries.py:437` `detail=f"{type(exc).__name__}: {exc}"`。

**风险：** 脱敏过度会让运维无法区分 ORA-12545 与权限错误。应保留 `error_class`，不要只留无信息摘要。

### B4 缺 GovernAuditLog
**同意。**  
引用：`governance.py:551-572` 角色分配/移除无审计；`admin.py:50-79` API Key 创建/启停无审计（整个 admin 模块未见 `GovernAuditLog`）；`relation_reviews.py:207-234` 批量无审计，单条有。

**风险：** 批量审计若逐条 insert，大批次会拉长事务；方案写「摘要与计数」更合适。

### B5 写/执行端点缺 Depends
**同意缺口存在；反对按所列 5 个 ai 端点一刀切加 `ai.sql.execute`。**  
引用：「`dict_medical_api.py:593,714,774,819,861,1182,1236,1260`、`ai.py:500,614,720,797,882`」。抽查属实：mappings/code-sets/items/push 等无 `require_permission`；同文件 `:513`、`:697` 等已有 Depends。

**理由：** `ai.py:797` `system-context`、`:720` `export-context` 是只读元数据，144/149 主注入路径；`ROLE_REQUIRED["ai"]` 已限制 `platform_admin/quality_admin`（`main.py:341`）。给只读上下文加 execute 码会锁死 `ai_user`（其矩阵有 `ai.context.read`，无 execute）。`ai.sql.execute` 在 `RESOURCE_CATALOG` 中不存在。  
**风险：** 技能/查询中心读上下文 403，表现为「值域未注入」。违反 §1「不改 144/149 语义」。

### B6 模板单引号
**同意。**  
引用：「`f"'{v}'"` 不转义；`{condition}` 原样拼接」。`quality_templates.py:119`、`:192` 属实。

**风险：** 只转义值、不校验标识符，表名/列名仍可拼接。`condition`「确认上游受控并加注释」不是控制措施。

### B7 危险词两套口径
**同意应统一词边界；疑问「直接复用 validate_readonly_sql」。**  
引用：`ai.py:539-546` 子串 `w in upper`；`db_connectors.py:18-22` 为 `\b`。`UPDATED_AT` 会被标 `UPDATE` 并 `blocked=True`，`execute_approved_draft`（`:630-634`）会拒绝。

**风险：** `_scan_sql_risk` 还有 LAB_RESULT/无 WHERE 等启发式，合并时丢掉会削弱大表保护；把 `CREATE` 词边界套到草稿扫描没问题，但不要把连接器「禁止注释/多语句」整套拷到 AI 草稿（草稿允许更宽文本）。

### B8 test_connectivity 脱敏不一致
**同意。**  
引用：Oracle/PG/MySQL `:313,:391,:470` 为 `str(e)[:200]`；SqlServer `:616-619` 才替换 password/user。

**风险：** 仅按 SqlServer helper 做字符串替换，DSN 里的 host 仍可能残留；应走 `sanitize_text`。

### B9 登录限流 IP 键
**同意列为讨论、默认不改。**  
引用：「`auth.py:163` … `5/minute` 以 IP 为键」。`Limiter(key_func=get_remote_address)` + `auth_login_rate_limit="5/minute"` 属实。NAT 下互挤是真实权衡。账号锁定已有。

**风险：** 若评审改组合键却未同步 SlowAPI key_func，会留下假安全感。

### 排除项：default_limits 作用于全部路由
**疑问（不反对排除，但证据不可复现）。**  
引用：「8.83 生产实测…60 次全部 200」；代码 `rate_limit.py:14-18` 确有 `default_limits=["200/day","50/hour"]`，且仅 4 个 `@limiter.limit`。

**理由：** 本审查不能复跑生产。FastAPI+SlowAPI 常见行为是只对装饰器生效，与描述相符。P3-7 加注释合理。  
**风险：** 升级 SlowAPI 后 default_limits 语义变化，可能突然限全站。

---

## 2.3 后端性能（C 组）

### C1 图谱 N+1
**同意有隐患；严重度可能高估。**  
引用：「全量 `AssetRelation` × 每条最多 2 次 `resolve_endpoint`」。`graph.py:1467-1469`、`:1776-1780` 确有全量循环；但 `_resolve_relation_endpoint`（`:160-172`）仅在 system/source/schema/table 缺失时才 SQL。

**风险：** 已回填物理键时优化收益接近 0；批量 IN 查若改变「多命中不猜」语义，会串边。P0-4「行为输出不变」必须加对比用例。

### C2 双 Session 耗尽连接池
**反对（机制描述不成立）。**  
引用：「middleware 开 1 个 SessionLocal + get_db 再开 1 个」。`main.py:468` 开会话后，`:499` **在 `call_next` 之前 `db.close()`**，与 `get_db` 不重叠。

**理由：** 并发耗尽来自「同时请求数 > 15」，不是每请求双连接。  
**风险：** 按此改中间件复用 session 易造成请求级事务泄漏，属于高风险错误修复。C2 也未进入 P0–P6 任务表。

### C3 查询列表 N+1
**部分同意。**  
引用：「列表页逐行查 active 版本；版本列表逐行 `require_permission`」。`queries.py:88-95` 的 `get_active_version` N+1 属实。`:536-539`/`:556-558` 仅在 `include_sql=True` 时才调 `require_permission`；默认列表 `include_sql=False` 不查权限。

**风险：** 方案把两件事捆在一起，执行 AI 可能去「优化」默认路径上并不存在的权限 SQL。C3 未进入执行批次。

### C4 board_overview 全量进内存
**同意现象；未立项。**  
`metrics.py:159-193` 全量 defs+results，再逐个 `get_active_metric_version`。

**风险：** 指标增长后看板先于图谱变慢。发现了却不进 P 批，清单与计划不一致。

### C5 finding 去重 N+1
**同意；未立项。**  
`quality.py:894-910` 每条 finding 一次 `select(QualityFinding)`。

### C6 Excel 导出无上限
**同意；未立项。**  
`dict_medical_api.py:352` `local_items = ...all()` 无 page。

### C7 dashboard 串行 COUNT
**同意低优；未立项。**  
`tables.py:209-233` 约 13 个独立 `count` + last_run，接近「14 个」。首页可承受，非 P0。

**总评 C 组：** 除 C1 进 P0 外，C2–C7 停在发现清单，与「一次性完成」不符。

---

## 2.4 冗余/死代码（D 组）

### D1 `_require_query_view_on_get` 三份复制
**同意。**  `queries.py:30-32` 等结构一致。P3-1 上移 `core/security.py` 可行。  
**风险：** GET 跳过写权限的语义要保持，避免 POST 被误挂。

### D2 operator 样板
**同意要收敛；疑问 helper 设计。**  
`relation_reviews.py:218-222` 等 `try get_current_user except pass` 属实。

**理由：** `get_current_user` 只在无 `request.state.user_identifier` 时抛（`security.py:11-16`）。中间件已写入 state，更稳妥是读 `request.state`，不必再 try/except。  
**风险：** debug 日志仍可能把 identifier 打进日志，需脱敏。

### D3 mapping 过滤双份
**同意。** `dict_medical_api.py:151-174` 与 `:331-350` 过滤块重复。导出路径无分页，抽公共函数时别把 list 的 offset/limit 带进导出或反过来。

### D4 两个 calculate 端点
**同意可抽内部函数。** `:283-353` 几乎相同，差别是 path `version` vs `req.version`。  
**风险：** 合并时搞混「强制版本」和「active 缺省」，属 144 语义。

### D5 死权限码 7 个「全库 0 引用」
**反对。**  
引用：「`query.publish/recalc/schedule、product.publish、evaluation.view、ai.draft.view`…全库 0 引用」。

**理由：**  
- 前端 `query-center/queries/index.vue:134` `v-perms="'product.publish'"`；`:205,:222` `v-perms="'query.schedule'"`。  
- `permissions.py:234` `ai_user` 矩阵含 `ai.draft.view`；`tests/test_permissions.py:54` 断言该码存在。  
- 括号里实际 6 个码，不是 7 个。这些码属于 144 目录，删目录等于改 144 语义，违反 §1。

**风险：** 按钮消失或权限列表测试红；DB 角色行仍在但目录没有，前后端授权展示分裂。P3-5 应改为「未挂 Depends 的码登记为待用，禁止删除已被 v-perms/角色矩阵引用的码」。

### D6 产品查两次
**同意。** `data_product_service.py:201` 与 `:240` 各查一次同一 `product_code`，docstring 也重复。低风险。

### D7 default_limits
**同意低优整理。** 见 B 组排除项。

### D8 `__import__("datetime")`
**同意。** `tables.py:339` 属实，无行为风险。

### D9 scripts 堆积
**疑问/反对按 P3-8 执行。**  
引用 P3-8：「`git mv`…根目录 dev.log/dev.err/*.db 加入 .gitignore 并删除本地文件」。与 §1「Git 写操作」禁止、§3「只改 backend/、frontend/、tests/」冲突。删 `*.db` 可能误伤本地 sqlite。

**风险：** 误归档仍被引用的 `seed_*`/`import_*`；未授权 git 索引变更。

---

## 2.5 前端正确性（E 组）

### E1 字典通道 try/finally 无 catch
**同意。** `saveCodeSet`（`:375-385`）、`saveItem`、`runPushPlan`、`runPushExport`、`dryRunOne`、`applyOne` 的 API try、`stopOne` 均为 try/finally 无失败提示。

**疑问：** P4-1「apply/stop 加确认弹窗」——`applyOne`（`:526-532`）已有 `ElMessageBox.confirm`；stop 的 apply 已有 token prompt。不要重复弹窗。  
**风险：** catch 后仍要 rethrow/提示，避免 `submitting` 解锁但用户以为成功。

### E2 systems `catch {}` 当取消
**同意。** `:437-438`、`:464-466`、`:474-476` 把 confirm 取消和 API 失败混在一起。P4-2 拆开正确。

### E3 质检中心静默
**同意。** `quality/index.vue` 有 9 处 `.catch(()=>{})`（`:946` 等），与方案一致。

**风险：** 质检页请求多，全改 `ElMessage.error` 可能一次失败连弹 9 次，需要节流/汇总。

### E4 注释保存静默
**同意。** `table-detail/index.vue:447,460` `.catch(()=>{})` 属实。

### E5 账号操作无 catch / 无确认
**部分同意，行号与范围不准确。**  
引用：「`local-accounts/index.vue:253-271`（4 操作）…`accounts/index.vue:76`」。

**理由：** `:253-271` 是 `doCreate`，**已有 catch**。无 catch 的是 `:278-314` 的停用/解锁/强制改密/重置密码。`accounts/index.vue` 解绑按钮在 `:76`，但 `doUnbind`（约 `:189-193`）**已有 catch 和 per-row loading**，缺的是确认框。  
**风险：** 执行 AI 按错误行号改 create 或重复包一层 catch。

### E6 搜索不重置页码；指标 50 条
**同意。** 查询 tab `@keyup.enter="loadList"`（`:19`），`loadList`（`:593-604`）用当前 `page`，无 `page=1`。`loadMetrics`（`:748`）固定 `page:1, page_size:50`。

**风险：** 指标补分页会改 query-center 交互，属 144/146 页面，需保持 URL/状态一致。

### E7 无请求序号
**同意。** `tables/index.vue:770-779` `selectTable` 无序号；图谱 `loadData`（`:615+`）与 `loadFieldGraph`（`:829-848`）可并发写 `graphData`。

### E8 catch 只处理 401/403
**同意。** `mappings/index.vue:374-377` 无 else。

### E9 approve 盲 fallback
**同意。** `relation-review/index.vue:257-263` 内层 catch 任意错误都打 legacy。P4-7「仅 404 fallback」正确。

**风险：** 权限 403 fallback 到 legacy 可能误批准/走旧语义（127 曾强调 reviews 不得升 candidate）。这是正确性+安全，不只是体验。

### E10 qs 数组序列化
**同意。** `utils/http/index.ts:43-45` 默认 `stringify`；`asset.ts:1046-1050` 手工拼 `rule_codes=`。`arrayFormat:"repeat"` 与 FastAPI 列表查询兼容。

**风险：** 全站数组 query 行为一变，漏网调用会从「偶发对」变成「全错」。必须 grep 全部数组 params。

### E11 scrollBehavior
**同意。** `router/index.ts:81-93`：无 `savedPosition` 且无 `saveSrollTop` 时 Promise 不 resolve；拼写 `saveSrollTop` 全仓仅此处，等于死分支。

**风险：** 导航偶发卡死/不回顶。改 `return {left:0,top:0}` 低风险。

### E12 原生 confirm
**同意。** `admin/index.vue:481,546`。失败路径 `http.delete().then()` 无 catch，与「失败无提示」一致。

### E13 new Promise 包 axios
**同意低优；§7 不做可接受。** `:250-259` 属实。

### E14 schema 一次 500 张
**同意低优；§7 不做可接受。** `tables/index.vue:570-575` `page_size:500`。

### E15 编辑连接混入多余字段
**同意低优。** `:491` `{ ...emptyConnection(), ...row }`。未进 P4 也未进 §7，成孤儿项。

---

## 2.6 前端类型与冗余（F 组）

### F1 ApiResponse/PageData 重复
**同意。** 8 处 `ApiResponse`：asset/dict/identity/metadata/ops/permissions/auth-admin/recipes；`query-center.ts:2` 从 asset import。identity 的 `PageData` 带可选 `stats`（`identity.ts:9-20`）。

**风险：** 强制统一后 identity 列表若依赖 `stats`，可选字段必须保留。

### F2 identity.ts 全 any
**同意要补类型。** 标「高」偏高——运行时已工作，是可维护性债。  
**风险：** 一次补全易与后端字段名漂移，typecheck 绿但运行错。

### F3 死代码清理
**部分同意，反对删 ReDialog。**  
引用：「未引用组件 ReCol/RePureTableBar/ReDialog」。

**理由：** `App.vue:4,11` 使用 `<ReDialog />`。RePureTableBar 未搜到引用；ReCol 仅自身定义；`getQualityRules`/`searchColumns`/`startAiSession`/`logToolCall` 仅定义处命中，较像死代码。`listConnectionTargets` 在 `asset.ts` 与 `ops.ts` 双份。

**风险：** 删 ReDialog 会编译/运行断全局对话框。方案虽写「先 grep」，任务表述已预设删除。

### F4 裸 http
**同意方向。** quality 12 处 `/api/v1/quality/...`、admin **12** 处（方案写 9）、ai-tools 2 处，属实。封装本身不改行为。  
**风险：** 与 P4 同时改同一 vue 文件，冲突概率高。

### F5 错误提取/文案复制
**同意可收敛。** `extractErrorDetail` 已存在且部分页在用。  
**风险：** 抽 `useAuthHint`/`statusLabels` 易变成方案禁止的「新增加权重的抽象」。

### F6 usePagedList
**同意只试点 6 页。** 仍与 P4 改同一批文件。  
**风险：** composable 默默改变「搜索是否重置页码」，和 E6 绑定，试点页与手写页行为分叉。

### F7 时间/confirm/http 风格
**部分同意。** 裸 ISO 与 `formatTime` 混用属实。`http.get<T, object>` 在 `asset.ts:174` 等存在，不是「34:30」这一处。不要全局替换。

### F8 dict.ts unknown
**同意低优。**

---

## 2.7 测试盲区（G 组）

### G1 服务层无直接单测
**同意倾向。** tests 中未见 `import query_intake` 等；存在 HTTP 间接覆盖（如 `test_metric_asset.py` 调 ingest）。「0 直接单测」基本成立。

### G2 连接器真路径
**同意需要回归。** 与 A1 同类。FakeConnector 掩盖是 55 已登记过的历史问题。

### G3 聚合端点无测试
**反对「diagnostics 无测试」；同意 summary 缺口。**  
引用：「`/graph/diagnostics`、`/dashboard/summary` 等聚合端点无对应测试文件」。  
`tests/test_graph.py` 已有 `/api/v1/graph/diagnostics`（约 253、285、383 行）。`dashboard/summary` 未搜到测试。

**风险：** P0-4/P6-3 重复造 diagnostics 测试，或改已有断言。

---

## 3. 执行计划任务（相对发现清单的增量意见）

### P0 打包（A1、A2、B1、C1、A3）
**疑问。** A2/A3 与 C1 同文件 `quality.py`/`graph.py` 大改，单批可接受；但 A1 配方未钉死占位符方言，B1 与 cookie 头短路纠缠。P0 验收未含 CSRF 正反用例文件是否已存在（全仓无 `test_auth_csrf.py`，P0-2 写「扩展」——可能是新建被写成扩展）。

### P1-1
**同意。** 无权限应掩码而非 403，才能与列表一致。

### P1-4
**反对按当前范围施工。** 只给 **写/执行** 端点加已有码（`dict.medical.edit/execute` 等）；`system-context`/`export-context` 保持 `ai.context.read` 或前缀 RBAC。禁止发明 `ai.sql.execute` 却套到读接口。

### P1-6
**同意抽 `\b` 公共函数；反对无差别替换 `_scan_sql_risk` 全文。**

### P2 A11
**反对 LIMIT 字面量。** 改为 SQL Server `TOP`。

### P3-5 / P3-8
**反对。** 见 D5、D9。

### P4 与 P5 同会话
**疑问。** P4 改错误处理，P5 再搬 API/composable，同一 vue 两次重构。应按页切开：先错误处理，类型收敛另批。

### P5-3
**反对未复核就删组件。** ReDialog 必须保留。

### P5-6
**同意限 6 页；建议从本轮拿掉**，避免与 P4 抢文件。

### P6-3
**疑问。** diagnostics 已有测试，应扩展现有 `test_graph.py`，不要宣称从零新增。

---

## 4. 全量验收门禁

**部分同意。** pytest + 双 typecheck + vitest + build 与仓库门禁一致。  
**反对当作「完成」的充分条件：** 未含隔离库 alembic 往返（虽号称零迁移，但权限种子脚本仍可能写库）、未含浏览器路径、未含 OpenAPI 路径不变检查。  
`git grep startswith -- auth.py 无` 会误伤文件中其他合法 `startswith`（若有）。应 grep `_require_csrf` 相关行。

---

## 5. 风险与回滚

**同意表内三项（P1-4 锁调用方、P4-8 数组参数、P5-6 回归）是真风险。**  
**缺失：** P3-5 删 144 权限码、P5-3 删 ReDialog、P3-8 git、C2 误诊、A11 错误方言、与 146 文件碰撞、A4 截断口径。  
「中断从最近批次续跑」在无 git commit 的前提下几乎不可操作（§1 又禁 Git 写）。

---

## 6. 执行提示词

**疑问。** 引用：「必读…review/round-2/ 最终报告」；「产出起步包/153…README 与 55」。  
与 §3「不动开起步包」矛盾；且要求执行 AI 读最终报告，但本轮审查尚未形成该文件。  
「免费执行 AI」一次吃 P0–P6，失败模式是表面全绿、语义被改。

---

## 7. 明确不做

**同意** 不做部署/迁移/B9/E13/E14/全量 20 页分页。  
**应补进「不做」：** 删除仍被 v-perms 引用的权限码；删除 `ReDialog`；SqlServer 使用 `LIMIT`；把 `system-context` 收成 execute 权限。

---

## 总裁决（给后续定稿用）

| 态度 | 条目 |
|---|---|
| 应修（证据成立） | A2、A3、A4（含 fetch+1）、A5、A7、B1、B2、B3、B4、B6、B8、E1–E4、E6–E12、F1、部分 F3（API 死函数）、G1、dashboard/summary 冒烟 |
| 应改写后再修 | A1 配方、A11 方言、B5 范围、B7 合并方式、C1 语义不变用例、D2 helper、E5 行号、P1-4 权限矩阵 |
| 应删出本轮 | D5/P3-5 删码、P3-8 git/归档、P5-3 删 ReDialog、C2「双会话」改造、把只读 AI 上下文加成 execute |
| 发现真但本计划没接住 | C3–C7、E15、A10 子串语义 |
| 事实错误 | D5「0 引用」、G3 diagnostics 无测试、C2 双连接重叠、E5 253-271 四操作、F3 ReDialog 未引用、A11 用 LIMIT |

**建议定稿策略：** 不要「一个长会话 P0–P6」。先做 **P0 修正版**（B1、A2、A3、A4+fetch、A5、B2、E9）+ 对应单测；权限/类型/composable/脚本归档另批。凡与 144/149 权限和 SQL 可见性有关的改动，必须先列角色矩阵再加 Depends。
