先按仓库入口做只读自检，再独立审 165、166 两份计划，不改任何文件。对照 149、146、163 与现有代码，核对数据模型、导出、权限和 API 契约是否闭环。继续核对权限命名、导出实现、质量发现模型，以及 149 §8 与 164 基线。已完成只读对照（未改任何文件，也未读 `review/`）。按计划正文逐条给出结论。

---

# 【165 计划】

## §0 目标

**【同意】** 把用户点名的五类问题收成「模板 → 夜间执行 → 入库」，方向正确，且与 164 §2 已实证的 A1/A2/A3 对齐。  
**理由**：目标不要求本轮做业务侧整改，只做探查通道，范围可执行。  
**风险**：164 §6 原设计是「规则=126/144 查询资产、异常落 QualityFinding」；本计划另起 `asset_probe_*`，与 164 骨架和既有 127 质量域分叉，后续两套 finding 并存。

## §1.1 夜间窗口 + 超时

**【同意】** 与 AGENTS「探库夜间+超时」、163 铁律第 4 类延伸、164 §1.6 一致。白天只允许结构核验级单条，边界清楚。  
**理由**：T1/T2/T5/T10 均为 2026 年全窗聚合，不宜白天压源库。  
**风险**：§4 执行器未写清**单模板超时秒数、整轮墙钟上限、超时后的 `blocked/partial` 落法**；`db_connectors` 虽有 `call_timeout`，计划未强制接到 `run_probe.py`。未到夜窗时提示词允许先做 E4/E5，合理，但 E3 若被执行者白天误跑会违反本条。

## §1.2 入库零患者明细

**【疑问】** 原则对，但与 §3 T8/T9「服务端聚合 IN，≤1000」直接冲突。  
**理由**：原文「证据 SQL 本身不得含患者标识字面量（一律参数化/聚合输出）」；T8 要把住院号打进 `IN (...)` 再查 JHEMR，标识会出现在拼接 SQL 或 `evidence_sql` 字段。  
**风险**：工号/住院号进平台库、审计、166 详情抽屉和导出，违反 AGENTS 脱敏红线；即使只存命中率，执行器内存里的 ID 列表也须禁止写入 `evidence_sql`/`note`/`output_r165`。

## §1.3 生产写入门禁

**【同意】** 隔离库先行、生产 apply 进 X1，符合 163 W2 链和 55「生产写须再授权」。  
**理由**：与 149/146 隔离库验证模式一致。  
**风险**：验收命令只写 `alembic upgrade head`，未写死 `APP_DB_URL=APP_TEST_DB_URL`（146 §11 已记录「只导出后者会误指 .env 库」）。执行者按字面跑，有可能对生产平台建表。

## §1.4 AI 不得裁决终态

**【同意】** AI/执行器只写 `open`、更新 `last_seen`/`relapse_count`，终态留给 166，符合 AGENTS「AI 不接入写操作执行器」的人工裁决精神。  
**理由**：与 149「永不自动 confirm」同构。  
**风险**：§2 未规定对 **`confirmed` / `false_positive` 行重跑时是否改 `metric_value`、是否保持终态**。若 upsert 一律把 status 打回 `open`，本条被自己的幂等更新打穿。

## §1.5 源库只读 + 禁止即席探生产

**【同意】** 源库 SELECT-only、新主题走模板，符合 AGENTS 与 163。  
**理由**：「sjzc 受控通道/平台连接器」并列，夜间执行器应走 `db_connectors`（与 `quality_sql_runner` 同源），sjzc 是会话探查入口，二者分工可成立。  
**风险**：提示词写「sjzc 为唯一连库通道」，§4 又写「复用 db_connectors」。执行 AI 若用 sjzc 手跑 12 条再手写库，会绕过幂等/审计；若 `run_probe.py` 在本机 Windows 直连，会撞 AGENTS「本机不能直连、必须跳板」。E3 运行拓扑（8.83？跳板？写隔离库？）未定义。

## §1.6 手写迁移 / 零 Git / 凭据零落盘

**【同意】** 新表必须手写 Alembic，禁 autogenerate，符合 AGENTS。  
**风险**：未指定 `down_revision` 探测法；仓库存在多条历史链，接错 head 会分叉。权限码若只在 166 种子、不在 165 迁移，隔离库 E4 的 403 测试与生产 X1「两表+权限码种子」会对不齐。

---

## §2 数据模型

**【反对】** 唯一键含 `window_start`，无法支撑「改了又改回来」的跨窗复发。  
**原文**：「唯一键 `(probe_type, system_pair, object_desc, metric_name, window_start)`」「status=resolved 的行在同键新 run 再次出现 → relapse_count+1」。  
**理由**：T5/T10 是「按月」窗，每月 `window_start` 不同 → 新行而非复发；YTD 固定 `window_start` 则同窗重跑是幂等更新，E5 只能在**同一窗**上人造 resolved 再跑，测不到「修了下月又坏」。问题身份应是 `(probe_type, system_pair, object_desc, metric_name)`，窗口是观测属性。  
**风险**：上线后复发徽标恒为 0，165 的核心用户故事落空。

**【反对】** 未定义「出现」=「SQL 有行」还是「越阈值」。  
**原文**：§4「与阈值比对→经 probe_service 写 run+findings」。  
**理由**：T1 类模板每次都会返回缺失率（哪怕 0%）。若有行即入库，resolved 次夜必被重开，relapse 爆炸；若仅越阈才写，须写比较符（`>`/`>=`）、率 vs 计数、T10 六档差是 1 行还是 6 行。`metric_value`/`threshold` 类型未定（Text vs Numeric），无法实现可比对。  
**风险**：假复发或永远不复发；E3「±5% 对照 164」与「只存越阈 finding」也互斥——83.2% 是基线不是阈值。

**【疑问】** 与 QualityFinding「并存不合并」可接受为分期，但与 164 §6、127 质量执行器重复建设。  
**理由**：已有 `asset_quality_findings`（status 含 open/confirmed/resolved/ignored 等）+ `quality_sql_runner` + 规则 SQL。165 几乎复制 run/finding 两表，却更瘦（无 sample_data，这点更好）。  
**风险**：166 P2 才互链；质量页与探查页两套状态机，运营不知改哪边。

**【疑问】** 字段缺口：无 `source_code`、无 FK 到 `probe_runs.run_id`、无筛选索引、`system_pair` 无枚举、`object_desc` 无长度/规范化。  
**理由**：149 Q6 要求值域按物理来源分开；HIS 与 ODS 同表名会挤在同一 `object_desc`。列表 API 按 status/severity 筛但无索引。  
**风险**：对账对象对错库；E4 分页在数据上来后变慢。

**【同意】** `asset` schema + `asset_` 前缀符合 AGENTS 单一 schema。服务拆 `probe_service.py` 也合理。

---

## §3 模板库 12 条

**【同意】** T1/T2/T5/T10 用 164 §2 已证 SQL 定型、禁止重跑核实数字，执行成本可控。  
**【同意】** JSON 模板含 `dialect/source_code/params/window_kind`，面向 Oracle 11g + Vastbase 多方言是必要的。  
**【同意】** 禁止 `FETCH FIRST`、要求 ROWNUM/LIMIT，符合 AGENTS 旧 Oracle 约束。

**【反对】** T6 检验线对账未写死 **禁止扫 `HIS.LAB_RESULT` 全表**。  
**理由**：AGENTS 硬约束：`LAB_RESULT` 约 1 亿行，必须 `TEST_NO` 子查询限定。T6 原文「先探 LIS schema 表清单与键」不够。  
**风险**：夜跑全表扫描拖垮源库，属高代价事故。

**【反对】** T11 TREAT_RESULT 两侧对账未内置 **152 E5 双编码映射**。  
**理由**：JHEMR `1治愈/2好转/3未愈/4死亡/9其他` 与 HIS COMM 字典编码错位，直接比码必然出假差。163/164 已把此项列为人工裁决。  
**风险**：首轮「基线对照」把编码冲突当成回传缺陷入库。

**【疑问】** T3/T4/T6/T7「执行时先探明列名再定型」把 **E2 定型**和 **E3 执行**混在一起。  
**理由**：E2 验收是「每条模板一条单测」；未探明的 SQL 无法做聚合形态断言。白天探列名产物应冻结进 JSON，禁止 E3 夜跑时现场改 SQL。  
**风险**：同窗第二次跑 SQL 文本变了，`evidence_digest` 漂移，幂等验收失败。

**【疑问】** T12 R-DOM「偏差证据可导入值域库 pending」。  
**理由**：149 允许 `source_type=ai_probe` + `value_domain.submit`，且「永不自动 confirm」正确。但 T12 无条数门禁（151 是 ≤200）；异义会把已 confirmed 行打成 `conflicted`（`value_domains.py` 同键异义 → 409/conflict）。  
**风险**：夜跑污染 149 注入链路（conflicted 不进注入）；与 163 R2 字典 pending 导入抢同一键。

**【疑问】** 模板放 `backend/scripts/probe_templates/*.json`，不进 126/144 查询资产。  
**理由**：164 §6 明确「每条质控规则=一条参数化查询资产」。偏离后，queryctl/认证/参数绑定门禁都用不上。  
**风险**：两套 SQL 治理；144 已修的「参数未到连接器」可能在脚本路径复现。参数名 `:START_DATE/:END_DATE` 与 Oracle bind 匹配，但须强制走 `execute_readonly(..., params=)`，禁止字符串插值。

---

## §4 执行器与批次

**【同意】** 单模板失败 `partial` 不中断、幂等 upsert、SQLite/隔离库单测（新建/更新/resolved 后再现）是可测设计。  
**【同意】** E4 只读 API 三件套 + `probe.finding.read` + 筛选分页，作为 166 的数据面，方向对。

**【反对】** E3「隔离测试库：run_probe 全量首轮」且「应复现 164 §2 基线 ±5%」在现有拓扑下不可闭环。  
**理由**：`data_asset_test` 是平台库，不是 HIS/JHEMR 副本。164 数字来自 sjzc **活库**聚合。要么（a）执行器读生产源、写测试平台库——必须写清跳板/8.83/凭据解析，且本机 Windows 默认不行；要么（b）对测试库源跑——复现不了 83.2%/35.5%。  
**风险**：E3 被标 WARN 空转，或误连生产平台写入 findings（X1 被提前打穿）。

**【疑问】** E4「审计只读不记」。  
**理由**：与仓内不少 GET 一致，但 AGENTS 对 AI 探查强调强制审计；`run_probe.py` 写库路径完全未要求 `GovernAuditLog`。身份夜跑有独立审计表，探查没有。  
**风险**：隔离库/生产一旦跑起来，无法回答「谁在何时跑了哪 12 条」。

**【疑问】** E4 契约过瘦：无响应 JSON schema、无 `source_code` 筛选、无 `GET /probe-runs/{id}`，166 F4 却要 runs Tab + 复发徽标。  
**风险**：166 只能 mock 或超范围改 165 API，破坏「166 不改模型」。

**【疑问】** E1→E6 顺序与提示词「E3 夜间未到则先 E4/E5」一致，但 E5「人工置 resolved」时 166 transition 还不存在。  
**理由**：只能在测试里直接改库/调未文档化的 service。应在 165 规定 **仅测试辅助** 的 `transition_for_test` 或 SQL fixture，并禁止执行器调用。  
**风险**：执行者为跑 E5 把终态写入做进 `upsert_finding`。

**【疑问】** DoD「pytest 全量 0 failed（叠加 163 基线）」把 165 绑死在 163 R1（NF-1）。  
**理由**：55 仍记 161 后 1 failed（plan127 s0）。165 若先于 163 R1 执行，总门禁过不了。  
**风险**：为凑 DoD 去改 plan127（属 163 范围）或把失败写成通过。

---

## §5 安全与边界

**【同意】** 业务源零写、不改 126/144/146/149/153 语义、不引入第三方、R-DOM 不自动 confirm，与 163/AGENTS 一致。  
**【疑问】**「生产平台库零写（E1–E5 全在隔离库）」与 E3 活库探查未切开。活库 SELECT 允许，但须在本节写明「源库只读、平台测试库可写」。  
**【反对】** 平台库写入未走审批/白名单执行器，也未规定脚本身份。  
**理由**：55 §0「平台库写操作必须经审批+审计+白名单（`asset_action_executors`）」。夜跑脚本直连 `probe_service` 是第二条写通道。可类比身份夜跑的「专用服务+审计」，但计划两者都没写。  
**风险**：任意能跑脚本的人可刷 findings；与 AI 工具禁写的边界在运维脚本侧被掏空。

## §6 等待域 X1–X4

**【同意】** 生产建表、生产首轮、人工终态、cron 都进等待域，门禁顺序 X1→X2→X4 正确。  
**【疑问】** X1「两表+权限码种子」与 166 F7 种子重复；X3 依赖 166 界面，但 165 可先于 166 合并。  
**风险**：只 apply 165 迁移、未 seed 166 权限，生产 API 全 403 或完全无鉴权（取决于实现）。

## §7–§8 DoD / 提示词

**【同意】** checkpoint、基线对照表、幂等+复发双实证、报告/_结果.json/README/55 登记，体例符合目录规则。  
**【反对】** 提示词「sjzc 为唯一连库通道」与 §4 平台连接器矛盾（见 §1.5）。  
**【疑问】** 未要求执行者保留 163「161 工作区改动原样保留」；与已批准的 163 并行时会改同一批文件（`main.py`、`permissions.py`、models `__init__`）。

---

# 【166 计划】

## §0 目标

**【同意】** 值域无界面（用户 08-28 指出）+ 消费 165 findings，拆成展示计划合理。明确可与 165 空态并行。  
**风险**：P1 把 149 §8 方案 B 的「最小前端」扩成管理页+confirm+导出+探查全页，工作量大于 149 估的 1.5 天，且与 163 R5（仍改 `table-detail` 等）文件冲突。

## §1.1 人工 confirm / 终态，开发期禁止代点

**【同意】** 与 149、163 E5「confirm 留人工」、AGENTS AI 禁写一致。  
**风险**：隔离验收若用管理员账号点过 confirm，会留下真数据；应规定只用 throwaway 行并回滚，或只走 mock。

## §1.2 复用优先、后端仅导出×2 + transition + seed

**【同意】** 值域走 149 既有端点、探查列表走 165 E4，增量面可控。  
**【反对】** 与 164 §3.4「不新增后端路由」已不一致——这是 166 相对 164 R2b 的明确加码，应在计划里写「偏离 164：为导出/流转新增 3 个端点」，避免执行者按 164 原文拒做。  
**【疑问】**「模型层不改（165 已定）」但 F5 状态机必须进 `probe_service`（165 只列了 upsert）。165 若已冻结服务接口，166 必改 165 文件。  
**风险**：两计划并行改 `probe_service.py`。

## §1.3 导出硬约束（号称复用 146 §11 E7）

**【疑问】** 166 的约束 **严于** 现网 146 E7 实现，不能「照抄」。  
**理由**：现网 `GET /api/v1/govern/audit-logs/export`（`governance.py`）确实有 `AUDIT_EXPORT_LIMIT = 5000`，但是：无公式注入转义、文件名固定 `audit-logs.csv`（不含时间窗）、**导出动作本身不写审计行**、列是硬编码而非白名单常量、**该模块写接口普遍未挂 `require_permission`**。  
**风险**：执行者「复用 E7」会把上述漏洞复制到值域/探查导出。正确说法是：**限额与 StreamingResponse 形态可参考，鉴权/审计/转义/文件名必须新做，禁止复制无鉴权 GET。**

**【反对】** 探查导出走 GET，且筛选条件在 querystring。  
**理由**：`evidence_sql` 可能很长；GET 进代理/访问日志。146 虽也是 GET，但审计导出列不含 SQL。  
**风险**：SQL 文本、系统对、窗口进入 Web 日志；建议 POST + body 筛选，或导出列默认去掉 `evidence_sql`。

## §1.4 不改既有语义 / 零迁移 / 老页面只触碰一处

**【同意】** 零新迁移由 165 管表，166 只 seed，职责清楚。F1 只加表详情区块，符合「老页面一处触碰」和 AGENTS「不改现有路径」。  
**【疑问】** F7 改 `permissions.py` 的 `RESOURCE_CATALOG`/`ROLE_DEFAULT`，163/153 同文件是权限矩阵源；「不改 153 语义」做不到零碰 153 维护面。  
**【疑问】** 未要求 API 放进 `frontend/src/api/*.ts`、禁止视图层 `http.request`（146 硬规则）。  
**风险**：新页直打 `http.request`，146 回归测试会红。

## §1.5 零 Git / 隔离库 / pnpm

**【同意】** 与 AGENTS 前端约束一致。验收命令用 pnpm + 双 typecheck（D6 写了 typecheck/test/build，未写明 `tsc`+`vue-tsc` 双过，但仓内 `pnpm run typecheck` 即此）。

---

## §2 F1 表详情值域区块

**【同意】** 对应 149 §8 方案 B 第一句「表详情页值域展示（含 domain_kind/scope_condition/陷阱）」。字段列表与 `_row_payload` 对齐。  
**【反对】** 未要求带 **`source_code`** 调 149。  
**理由**：149 §9 Q6「HIS 源端与 ODS 镜像同字段按物理来源分开」；146 E5 已强制表详情 `source_code` 隔离。只按 schema/table 拉值域会串源。  
**风险**：ODS/HIS 同名表显示错值域，confirm 点错行。

**【疑问】** 149 列表 `page_size` 上限 200、默认 20。一表多码（151 字典接入后）会截断。F1 未规定按列分页或循环拉全。  
**风险**：「暂无值域」假阴性。

## §2 F2 值域管理页

**【同意】** 列表筛选大体可映射 149 `GET /api/v1/value-domains`（system/schema/table/column/code/status/conflicted）。冲突 Tab=`conflicted=true`、pending 徽标可用 `status=pending` 的 total。证据链字段在详情 API 已有。  
**【反对】** F2 写「version 筛选」，149 **没有 `version_no` 查询参数**（版本在子资源 `/{id}/versions`）。  
**理由**：不是最小前端可 internally filter 的契约，除非 166 新增后端（违反 §1.2）或只做当前页客户端筛（假筛选）。  
**风险**：验收按「version 筛选」会逼执行者改 149。

**【疑问】** 路由 `/value-domains` 不在 `/asset/` 下。仓内资源页是 `/asset/...`，`RESOURCE_CATALOG` 虽有独立 `value_domain` 菜单，但 D1 未写 `meta.auths`、菜单组、与 146 E1 四主入口的关系。  
**风险**：无 `auths` 的路由会漏出菜单（表详情现就无 auths，靠隐藏）；或挂错组。

## §2 F3 值域人工操作

**【反对】** 权限码写成 `value_domain:confirm`，与目录/种子/后端依赖的 **`value_domain.confirm`（点号）** 不一致。  
**理由**：`permissions.py` 注释称 matcher 兼容 colon，但前端 `v-perms` 与 RESOURCE_CATALOG 全是点号；149 迁移种子也是点号。164 §3 同样误用冒号，166 原样继承。  
**风险**：按钮永不出、或种子写成 colon 成为死码（161 已有死权限码教训）。

**【反对】** 只做 confirm/deprecate，**没有 `PATCH /{id}/resolve-conflict`**。  
**理由**：149 confirm 在 `conflict_status=conflicted` 时 **409**，必须先裁决。F2 展示 competing meanings，F3 不能操作。闭环断裂。  
**风险**：冲突 Tab 变成只读死胡同，151/163 R2 导入的冲突无法在「新界面」处理。

**【疑问】** 149 `ConfirmRequest.reason` 可选，`DeprecateRequest.reason` 必填。F3 只说二次确认弹窗，未区分。deprecate 不填理由会 422。

## §2 F4 探查发现页

**【同意】** 列表字段与 165 §2 列一致；空态文案「暂无探查发现（等待首轮 run）」比假 0 诚实。  
**【疑问】** runs Tab 依赖 165 `GET /probe-runs`，165 未定义 runs 的摘要字段（`error_summary` 是否含连接串？）。  
**风险**：把 `error_summary` 原样渲染导致 DSN/口令残留（153 已修过 quality note 脱敏）。须规定展示前走 `sanitize_text`。

**【疑问】** 详情展示并允许复制 `evidence_sql`。若 165 T8 未把 IN 列表从 SQL 拿掉，这里就是 PHI 扩散面。

## §2 F5 finding 状态流转

**【反对】** 状态机不能支撑「确认真实问题 → 业务修好 → 关闭」。  
**原文**：「open→任一终态、resolved→false_positive 不允许、复发行只读提示走重新裁决」。  
**理由**：`confirmed` 被当成终态后不能到 `resolved`；165 复发只从 **resolved** 重开。真实流程应是 `open → confirmed → resolved`，复发后再 `open`。`false_positive` 保持不被执行器重开是对的，但人工误点 resolved 应允许改 false_positive（附理由），否则只能改库。  
**「复发行只读」与 165「复发后 status 回 open」矛盾**：165 回 open 后应按 open 再裁决，不是只读。  
**风险**：界面三按钮从 open 直接 resolved，跳过确认；或复发后按钮锁死，X3 无法操作。

**【同意】** 理由必填 + `probe.finding.manage` + 审计，方向对。须规定：执行器身份禁止持有 manage；transition 拒绝把 status 设为 open 以外的「非人工」路径。

## §2 F6 导出

**【同意】** 两处导出、5000 上限、防公式注入（`= + - @`）作为目标是对的。  
**【疑问】** 值域导出是否含 pending/conflicted/trap？149 离线 JSON 只导 confirmed。管理页「按当前筛选」可含 pending，导出文件可能被当成官方字典外发。  
**风险**：未确认口径扩散；应在文件名/页眉标明 status 筛选，默认不含 conflicted 或强制水印。

**【疑问】** 白名单若包含 `evidence_sql`/`snippet_ref`，公式注入转义不够防 SQL/PII 外带。白名单应在计划里**逐列写出**。

## §2 F7 权限种子与矩阵

**【同意】** `ai_user` 仅 read、不授 manage，与 149 `ai_user` 不授 confirm 同构；`quality_admin` 管探查合理；要求同步 `security_audit` 正确（写路由静态扫描，见 `test_fine_grained_write_permissions.py`）。  
**【疑问】** 未加 **页面级** 码（对比 `asset.quality.view`）。`probe.finding.read` 既当 API 又当菜单，D1 路由守卫会含糊。未给 `asset_viewer` 只读探查、未给 `asset_editor` 值域 confirm 以外的探查权，矩阵不完整。  
**【反对】** 165 E4 要用 `probe.finding.read` 做 403 测试，166 才 seed；165 X1 又写「权限码种子」。三处所有权不清。  
**风险**：security_audit 只扫写方法，**GET export 若漏挂权限不会被现有测试抓住**——必须在 166 单测显式断言 export 的 401/403。

## §2 P2

**【同意】** 看板/趋势/互链/触发入口后置，避免本轮膨胀。触发入口依赖 165 X4，顺序正确。

---

## §3 后端增量

**【反对】** `GET /api/v1/value-domains/export` 与已有 `GET /{domain_id:int}` 的注册顺序未写。  
**理由**：若 `/export` 写在 `/{domain_id}` 之后，FastAPI 把 `export` 当 int → 422。探查侧 `GET /probe-findings/export` vs 165 `GET /probe-findings/{id}` 同样问题（若 id 为 int，须先注册 `/export`）。  
**风险**：导出路由不可达或详情 API 被打坏。

**【疑问】** transition 的 `action` 枚举、HTTP 409 语义、是否允许 `confirmed→resolved` 未进 OpenAPI 级契约，D3「状态机测试≥4」会各写各的。

**【同意】** 权限 seed 走 153 B5 幂等模式（改 CATALOG + seed，非 autogenerate 迁移）可行；生产仍须发布窗口，不能以为「零迁移=可偷偷上生产」。

## §4 批次 D1–D6

**【同意】** 按页一次建完、组件测试数量、D6 三件套，符合 146/AGENTS。  
**【疑问】** D1「路由守卫测试（无权限 403）」——前端 `auths` 通常是藏菜单/禁入，HTTP 403 是后端。两层都要测，计划写成一条会漏后端。  
**【疑问】** D6「全量 0 failed 叠加 163/165 基线」：165 未完成则探查测试不存在；163 NF-1 未修则全量失败。166 不能独立收口。  
**【疑问】** 未列 gzip 预算（146 对 main/graph/CSS 有数）。新开两页可能涨预算。  
**【反对】** D5 若与 163 R5 同时改前端测试/权限文件，违反 AGENTS「不得让多个 AI 同时修改同一文件」。

## §5 联调开关 `APP_PROBE_API_READY`

**【反对】** 默认 `false` 走 mock 会把假数据带进可发布前端。  
**理由**：与同节「不显示假 0」矛盾。运行时开关属于前端还是后端未说明；生产漏关则运营按假 finding 做终态。  
**风险**：应用 Vite 环境变量进 bundle 后难以关闭。测试应在 Vitest mock HTTP，**产品默认直连真实 API，空列表走空态**。

**【同意】** 165 E1+E4 完成前 mock 开发、完成后隔离联调截图，并行策略本身成立。

## §6–§7 DoD / 提示词

**【同意】** ai_user 无 manage 的实证、导出三硬约束要有测试、禁止开发期代点，提示词必读 149 §8 / 165 §2§4 / 146 E7，指向正确。  
**【疑问】** 提示词「146 §11 E7 审计导出模式（导出复刻）」会把无鉴权实现复刻进来（见 §1.3）。应改为「限额与流式响应可参考，鉴权/审计/转义按 §1.3 新做」。  
**【疑问】** F1 改 `table-detail/index.vue`，163 R5 E5 仍有该页剩余项；两计划未声明文件锁。

---

# 两计划交叉（顺序与依赖）

| 点 | 判断 |
|---|---|
| 宣称顺序 | 165 建表/API 先行，166 可 mock 并行——**同意**为空态开发策略 |
| 复发语义 | 165 键含窗口 + 仅 resolved 重开；166 把 confirmed 当终态且复发行只读——**反对，两计划未对齐，功能不闭环** |
| 权限种子 | 165 X1、166 F7、165 E4 测试——**所有权重复** |
| transition 服务 | 165 未列方法，166 说不改模型——**必改 165 服务层，未写入 165 DoD** |
| `/export` 路由 | 166 新增，165 `{id}` 已占路径——**166 必须先注册静态路径，165 须约定 id 类型** |
| 与 163 | 两计划 DoD 都要全量 0 failed，但 163 R1 才灭 NF-1；163 R5 与 166 F1 抢 `table-detail`——**顺序矛盾，未设文件锁/执行窗** |
| 与 149 | 166 F1/F2 大体合方案 B；F2 version 筛、F3 缺 resolve-conflict、冒号权限码——**未闭环** |
| 与 164 | 165 放弃查询资产+QualityFinding；166 放弃「不新增后端」——**应显式记录偏离，否则执行者按 164 原文会停工** |

# 安全边界汇总（两计划均须在修订中关闭）

1. **T8/T9 IN 列表与 `evidence_sql` 入库/展示/导出** — 患者/就诊标识泄漏。  
2. **LAB_RESULT 全表风险（T6）** — 源库稳定性。  
3. **`run_probe.py` 平台写无审计、无脚本身份、拓扑未禁本机直连** — 绕过 55 写门禁。  
4. **R-DOM 夜跑提交 pending/冲突** — 冲击 149 注入与 confirmed。  
5. **GET 导出无鉴权被「复用 146 E7」带入；GET 日志记录 SQL**。  
6. **`APP_PROBE_API_READY=false` 默认 mock** — 假问题进生产 UI。  
7. **ai_user 若误获 manage/confirm** — 计划有矩阵，但 GET export 不在现有写路由扫描内，须补测。  
8. **隔离库 alembic 未钉死 `APP_DB_URL`** — 误对生产 apply 两张表。

---

**总评（非逐条）**：两份计划作为 164 拆分后的方向稿可执行，但 **都不能按 v1.0 原文开工**。165 的复发唯一键与「出现」语义未定义，E3 活库/隔离库拓扑不成立；166 的值域冲突无裁决入口、finding 状态机与 165 互斥、导出若照抄 146 E7 会丢鉴权。建议先修订上述反对项再进多方核查通过态。
