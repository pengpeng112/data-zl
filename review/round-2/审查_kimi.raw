• 我先并行派出多个只读探查子代理，逐组核验方案中的行号证据，再独立给出逐条评审。

• 核验结果已回来。其中"slowapi default_limits 排除项"子代理结论与方案相反，这是关键分歧点，我亲自复核代码再定夺。

• 六个核验代理已全部返回，关键分歧点（slowapi 排除项）我已亲自复核 `rate_limit.py` 与 `main.py:314-316` 确认。以下为逐条独立评审。

  ---

  # 评审结论：方案 v1 逐条审查（kimi，只读）

  **总体判定：方案事实基础大体扎实（抽查 60+ 行号证据，约 80% 完全成立），但存在 2 处实质性错误结论、1 处执行计划重大遗漏、若干计数/描述失真。不建议按现状直接交付执行 AI，需先修订。**

  ---

  ## 一、对 §2.2 排除段（slowapi）——【反对】，这是本方案最严重的事实错误

  - 方案原文（§2.2 排除段）："SlowAPIMiddleware 仅对显式 `@limiter.limit` 装饰的 4 个端点生效……该判断错误，不采纳"。
  - 我复核的代码事实：`rate_limit.py:14-18` 定义 `default_limits=["200/day","50/hour"]`；`main.py:315` 挂载了 `SlowAPIMiddleware`。slowapi 在 middleware 挂接模式下，`default_limits` **会对所有未被显式装饰的路由生效**——这正是被排除的原扫描结论。全仓仅 4 处 `@limiter.limit`（auth.py:163/196、systems.py:1369/1416），无任何 `limiter.exempt`。
  - 起草方的反证是"生产 60 次连打零 429"，这与代码行为矛盾，唯一自洽解释是生产环境 `rate_limit_enabled=false` 或环境差异——即实测测的是"开关关了"，不是"机制不生效"。
  - 风险：P3-7 拟把"仅对显式 @limiter.limit 路由生效（实测验证）"写进代码注释，等于**把一个错误结论固化进仓库**，未来有人开启限流开关时会按错误心智模型操作。建议：排除结论撤回或改写为"需先核实生产 `rate_limit_enabled` 实际值再定性"。

  ## 二、对 §3 执行计划完整性——【反对】，C 组 6/7 条目无对应批次

  - P0 只覆盖 C1（§3 P0 标题自述"A1、A2、B1、C1、A3"）；P1=B2-B8，P2=A4-A11，P3=D 组，P4/P5=前端，P6=测试。**C2（双会话池耗尽）、C3（queries N+1）、C4（board_overview 全量内存）、C5（finding 逐条查重）、C6（Excel 导出无上限）、C7（dashboard 串行 COUNT）在 P0–P6 中无任何任务承载**，§7"明确不做"也未列它们。
  - 风险：执行 AI 严格按批次执行后，发现清单里 6 项性能问题静默落空，且§6 提示词会让执行 AI 误以为"七批完成=全部完成"。必须在 P1 或新增批次中补任务，或在 §7 显式声明不做。

  ## 三、§2.1 A 组（后端正确性）逐条

  - A1【同意】`db_connectors.py:571-572` 属实，pymssql pyformat 下按 dict 插入序绑 tuple，顺序错配静默绑错值。但对 P0-1 修法提【疑问】：pymssql 原生支持 `execute(sql, params_dict)` 按名绑定，直接传 dict 比"正则提取占位符顺序重排"更简单更稳；且 P0-1 说"驱动是 pyodbc 时保持 dict 不变"有误——pyodbc 只支持 `?` 位置参数，dict 传参会直接报错。
  - A2【同意】`quality.py:246-251` 全量拉 AssetColumn Python 分组属实，同文件 :356-371 确有 GROUP BY 示范。归入"正确性 A 组"不当（实为性能），但 P0-3 处置合理。
  - A3【同意】`quality.py:937-941` except 后未 rollback 直接 commit 属实，是 A 组最值得修的一条（失败分支二次异常掩盖根因）。
  - A4【同意事实，疑问修法】`query_runner.py:279` `>= max_rows` 属实；但连接器侧统一 `fetchmany(safe_limit)`，**当前并不存在 max_rows+1 探测策略**，P2 文中"与取数 fetchmany(max_rows+1) 策略配套"是前置条件而非现状。只改 `>` 会把"恰好 N 行且有更多"从误报变成漏报，必须把连接器取数策略改造列为显式子任务。
  - A5【同意】`relation_reviews.py:245-246` `to_cols[-1]` 补位属实，P2 改 400 明示合理。
  - A6【同意】`jhemr_identity_adapter.py:307-317` sleep(0.5)+单次 poll 属实，改等待循环合理。
  - A7【同意】`identity_sync.py:70-73` 吞异常返空属实。
  - A8【同意】`db_connectors.py:228-231` except pass 属实；补 warning 日志即可，注意 init_oracle_client 重复调用必抛异常，宽豁免本身合理、别改成 hard fail。
  - A9【同意】`query_intake.py:194-201`、`metric_service.py:235-242` max+1 无重试属实，唯一键存在（`uq_asset_query_versions_qid_ver` 等），捕 IntegrityError 重试一次方案可行。
  - A10【部分同意】Python 端过滤属实，但"== 与 in 双条件"描述不准——第二个条件是 Python 子串包含（`category in (d.category or "")`），不是 `.in_()`。子串匹配可能是有意的口径兼容（如"48项"匹配"48项核心制度"），P2"去冗余条件下推"前需确认不误伤口径。
  - A11【同意】SqlServer fetch_metadata 无 TOP/LIMIT，其余三方言均有，属实。

  ## 四、§2.2 B 组（安全）逐条

  - B1【同意】`auth.py:71/73` startswith 前缀匹配属实，`http://localhost:5173.evil.com` 可绕过。SameSite=Lax 有缓解但非根本防护，改精确相等（scheme+host+port）正确。
  - B2【同意】`queries.py:596-628` diff 端点直出 `current_sql/parent_sql`（:625-626），仅有 `query.view` 兜底，绕过 `_serialize_version_for_read`（:42-58）的 `ai.sql.full_read` 门禁属实。P1-1 修法与列表口径对齐，合理。
  - B3【同意但修正一处】`ai.py:653`、`queries.py:437` 原始异常回显属实；`quality_sql_runner.py:153` 的 `note: str(exc)[:500]` 存在，但落 finding.detail 的路径以 `error_cnt>0` 为前置，当前不可达——是潜伏风险而非现行泄露。复用 `data_masking.sanitize_text`（已存在）方向正确。
  - B4【同意】`governance.py:551-572`、`admin.py:50-79`（整个 admin.py 未 import GovernAuditLog）、`relation_reviews.py:207-234` 批量无审计，单条有，口径不一属实。
  - B5【同意】抽查确认 `dict_medical_api.py` 8 处与 `ai.py` 5 处无端点级 Depends，同文件其他端点有，口径不齐属实。注意它不是裸奔：main.py `_enforce_rbac`（:410-433）有前缀级角色兜底。P1-4 需知：`ai.sql.execute`/`dict.medical.write` **全仓不存在**，新增码必须同步 RESOURCE_CATALOG+角色种子+测试矩阵，方案已有此表述，风险一节也有兜底，可行。
  - B6【同意事实，疑问严重度】转义缺失属实，但核验发现 `template_standard_domain`/`template_accuracy_single` **当前只被测试引用，运行时规则目录未使用**——condition 无运行期来源。严重度"中"偏高，属潜伏问题；P1-5 可做但不应与安全现行问题同优先级。
  - B7【同意】两套口径属实，`SELECT UPDATED_AT FROM t` 在 ai.py 子串匹配下会被 blocked，误杀合法查询可复现。统一用词边界版正确。
  - B8【同意】Oracle/PG/MySQL 三处 `str(e)[:200]` 无脱敏、仅 SqlServer 有，属实。
  - B9【同意】留作讨论项不默认执行是正确克制；补充核验发现：限流键用 `get_remote_address` 且不解析 X-Forwarded-For，与 auth.py 自己的 `_client_ip`（:55-61）口径不一，评审时应一并讨论代理后取址问题。
  - 排除段【反对】见上文第一节，不再重复。

  ## 五、§2.3 C 组（性能）逐条

  - C1【同意事实，疑问严重度】全量遍历+逐条 resolve 属实，但核验发现 `_resolve_relation_endpoint` 仅在关系行未回填 system/source 时才发 SQL，已回填行 0 次；且当前关系量级数十~数百条。定"高"（图谱页不可用）偏夸大，"中"更准。即便如此 P0-4 修复方向（批量加载映射）正确。
  - C2【同意】`main.py:468` middleware 开 SessionLocal + get_db 再开一个、pool_size=5+overflow=10 属实。但**无批次承载**（见第二节），这是 C 组里最该修的一项。
  - C3【同意】列表逐行 get_active_version、版本逐行 require_permission（每次约 2 SQL）属实；注意仅 `include_sql=True` 时放大，页面默认路径不触发，严重度"中"可降到"低中"。
  - C4【同意】`metrics.py:159-204` 全量进内存+逐 def 查询属实，result 表随周期累积会劣化。
  - C5【同意】`quality.py:893-917` 每条 finding 单独 SELECT 查重属实。
  - C6【同意】`dict_medical_api.py:352` 全量无 LIMIT + 内存拼 XML + StreamingResponse 包 BytesIO（伪流式）属实，比方案描述更糟一点。
  - C7【同意】串行 COUNT 实为 13 个（方案称约 14），另有 last_run+3 个 group_by，共约 17 条串行查询，无缓存属实。

  ## 六、§2.4 D 组（冗余）逐条

  - D1【同意】三份逐字一致，连 metrics/data_products 都套用 `query.view` 权限码，上移公共依赖合理。
  - D2【同意事实，疑问计数】样板实际 **15 处**非 12 处：relation_reviews.py 另有 3 处同构变体（默认值是 `"reviewer"` 而非 `"system"`，多一层 `if request is not None`）。P3-2 若按"12 处改用"执行会漏 3 处，且 helper 的 default 参数需兼容两种默认值。
  - D3【同意】两段过滤构造逐行一致，连 code-set 选择块（:142-149 vs :322-329）也是双份，方案漏提后者。
  - D4【同意】两 calculate 端点仅 version 来源不同，属实。
  - D5【部分反对】核验结果：真死码只有 3 个（`query.publish`、`query.recalc`、`evaluation.view`）。`query.schedule`、`product.publish` 被前端 `query-center/queries/index.vue:134,205,222` 的 `v-perms` 引用（按钮显隐）；`ai.draft.view` 被角色预设 `ai_user`（permissions.py:234）和 `tests/test_permissions.py:54` 引用。P3-5 按"7 个全删"执行会破坏前端按钮权限控制并打红测试。必须先修订为删 3 个、其余 3 个单独定性（"前端显隐码但后端无强制"）。
  - D6【同意】同一产品行查两次属实；注意第二次查询发生在并发守卫内，有可辩解性，修时改为传参即可。
  - D7【同意】配置存在属实，但配套结论错误（见第一节）。
  - D8【同意】属实，实际在 `tables.py:339-341`（行号漂移），且连用两次。
  - D9【部分反对】`backend/scripts/` 130 个 .py、`_` 前缀一次性脚本 58 个属实；但"根目录 dev.log/dev.err/*.db"路径错误——这些文件在 `backend/` 下（`backend/dev.log`、`backend/identity_test.db` 等），根目录没有。P3-8 按根目录执行会扑空。

  ## 七、§2.5 E 组（前端正确性）逐条

  - E1【同意】8 个函数 try/finally 无 catch 属实，applyOne/stopOne 是写 HIS 通道，静默失败风险最高，定"高"合理。
  - E2【同意】三函数 confirm 的 reject 与 API 的 reject 被同一 `catch{}` 吞掉属实，定"高"合理。
  - E3【同意】9 处 `.catch(()=>{})`（其中 deleteRule 外层那处是合理的 cancel 分支）+ 4 个无 catch 函数属实；P4-3 修时注意别把合理的 cancel catch 也改成报错。
  - E4【同意】行号精确命中（447/460）。
  - E5【部分反对】`accounts/index.vue` 的 doUnbind **有** catch+ElMessage.error（:184-199），"无 catch"不成立；属实的是"解绑无确认弹窗"。local-accounts 4 操作无确认属实（行号漂移为 278-315）。
  - E6【同意】搜索直接调 loadList 不重置 page、指标 tab 硬编码 page_size=50 无分页组件，属实。
  - E7【同意】两文件均无任何守卫（无序号/AbortController/重入锁），属实。
  - E8【部分同意】mappings 主 loadData 只认 401/403 属实；但 sync-diffs 只有 loadData 无 catch，doSync/updateStatus 有 ElMessage.error，"sync-diffs×2"不准。另方案漏报 mappings 的 `saveRow`（299-311）和 `toggleStatus`（313-318）同样静默。
  - E9【同意】任何错误（含 500/网络）都无差别 fallback legacy 属实，P4-7"仅 404 时 fallback"修法正确。
  - E10【同意】qs 默认 indices 格式 + `asset.ts:1046-1052` 手工拼 URL（且未 encodeURIComponent）属实，P4-8 改 repeat 后删手工拼接正确。
  - E11【同意且更糟】`savedPosition` 分支在 Promise executor 内 `return savedPosition` 而非 `resolve(savedPosition)`，且 else 分支条件不满足时同样永不 resolve——比"无标记分支不 resolve"更糟。关键修正：`saveSrollTop` 全仓**仅 router/index.ts 自身出现，没有任何路由 meta 设置它**，该分支是死代码。P4-9 的"grep 引用处同步"无对象，正确修法是修正拼写+修复 resolve，或直接删死分支。
  - E12【同意】行号精确；另核验发现 admin 页还有 6 处无 catch 链（loadKeys/toggleKey/saveOwner/saveTerm/createSnapshot/runCompare），P4-10 可顺手收编。
  - E13【同意】两处属实；§7 不做决定合理（低收益）。
  - E14【同意】`page_size: 500` 一次性拉取属实，超 500 静默截断。
  - E15【部分反对】多余字段确实混入表单对象，但保存路径 `saveAddConnection`（503-516）用显式字段白名单调 patchSource，**多余字段并不回传后端**——"混入表单回传"不成立，只是表单状态污染。严重度应为"可忽略"。且 E15 既不在 P4（只覆盖 E1-E12）也不在 §7 不做清单，属漏项，需显式登记。

  ## 八、§2.6 F 组（前端类型/冗余）逐条

  - F1【同意】ApiResponse 8 处、PageData 6 处本地定义、identity 版多 stats 分叉、仅 query-center.ts import，全部属实。P5-1 收敛方向正确，注意 PageData 合并时保留可选 stats。
  - F2【同意】identity.ts 全 any 属实。
  - F3【部分反对】7 个死 API 函数、listConnectionTargets 双定义（asset.ts:656 死、ops.ts:130 活）属实；但 **ReDialog 是活组件，被 `App.vue:4,11,18` 使用**，P5-3 删除它会直接弄坏应用。删除清单必须剔除 ReDialog。方案"先全仓 grep 复核 0 引用"的约束恰恰说明起草时没 grep 对。
  - F4【部分同意】问题真实，但计数失真：实际 27 处非 23 处，admin 是 12 处非 9 处，且漏报 table-detail 2 处。P5-4 收编范围需按实测清单。
  - F5【部分同意】字面不准（views 下没有本地命名的提取函数），实质成立且更广：19 个视图内联 `err?.response?.data?.detail`；authHint 实际 3 份非 2 份；loadSystemNames 2 份、状态映射约 12 文件属实。修复方向不变。
  - F6【同意】约 20 页五件套样板属实，具备抽 composable 条件；P5-6 只接 6 页的克制合理。
  - F7【部分同意】formatTime 存在但仅 2 个视图使用（方案称 3）；裸时间输出确认约 8-10 处（量级吻合）；另发现 2 个私有 `replace("T"," ").slice(0,19)` 副本（deptLabels.ts、syncLogLabels.ts），P5-7 应一并收编。
  - F8【同意】dict.ts 全 unknown + 视图 11 处 as any 属实。

  ## 九、§2.7 G 组（测试盲区）

  - G1【同意】四个核心 service 无任何直接单测（无测试文件 import 它们），属实。
  - G2【同意】`quality_sql_runner.py:64-66` 注释逐字自证 FakeConnector 掩盖 target_host 误用，属实。
  - G3【部分反对】`/graph/diagnostics` **有**测试（`tests/test_graph.py:253,285,383` 三处），方案"无对应测试文件"只对一半；真盲区是 `/dashboard/summary`。P6-3 应为 diagnostics 做**增量补强或核验既有覆盖**而非重复新建冒烟。

  ## 十、对 §0/§1/§4/§5/§6/§7 的评审

  - §0 原则【同意】一次性、收敛式重构、零迁移、零外部动作四条原则清晰且与 AGENTS.md 约束一致。
  - §1 硬边界【同意，一处冲突】边界清单完整。但 P3-8 要求 `git mv` 归档脚本——git mv 是 git 工作区变更，与 §0 原则 4"零外部动作/不 Git push"及 §7"不做 Git commit/push"的表述存在张力（mv 虽非 commit，但属 git 索引操作）；且 P3-8 含"删除本地文件"动作，建议在 §1 显式豁免或改为普通文件移动。
  - §3 两个笔误：标题行"不动 deploy/、**开起步包**/、.agents/"和 §6"产出 **开起步包**/153_..."均应为"开发起步包"。
  - §4 门禁【同意】命令与 AGENTS.md 验收命令一致，静态复核项合理。
  - §5 风险【同意但不全】P1-4/P4-8/P5-6 的风险与缓解都成立；但缺两条：①上文第二节的"C2-C7 无批次"本身是最大的执行风险；②P0-1 改参数绑定属于连接器核心路径，应有"四种方言连接器冒烟"的缓解（P6-2 已部分覆盖，建议前置到 P0 验收）。
  - §6 提示词【疑问】必读清单含"review/round-2/ 最终报告（裁决附注）"——该文件目前不存在（本方案仍是草案 v1），执行 AI 会扑空；应注明"评审定稿后生成"或从必读中移除。
  - §7 不做项【同意】E13/E14/B9/全量铺开/57 处分页替换的不做决策均合理；需补上 E15 的显式定性（建议登记为"低收益不做"，并修正其描述）。

  ---

  ## 修订建议汇总（按优先级）

  1. 撤回或重写 §2.2 slowapi 排除段及 P3-7 注释文案（事实错误，最高优先）。
  2. 为 C2–C7 补执行批次或在 §7 显式放弃（计划完整性缺口）。
  3. D5/P3-5 收缩为删 3 个真死码；F3/P5-3 剔除 ReDialog；G3/P6-3 改为补强既有 diagnostics 测试。
  4. P0-1 优先用 pymssql 原生 dict 绑定替代正则重排；A4 修复与连接器 max_rows+1 探测策略绑定为同一任务。
  5. 修正 D9 路径（backend/ 非根目录）、D2 计数（15 处）、E5/E8/E15/F4/F5 的描述失真，并把 mappings 的 saveRow/toggleStatus、admin 页 6 处无 catch 链补入 P4 范围。
  6. 修复 §3/§6 "开起步包"笔误，处理 §6 必读清单悬空问题。

