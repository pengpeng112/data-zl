先通读方案全文，再对照仓库真实口径做只读审查，不改任何文件，也不读 `review/` 下其它材料。方案是 149 的摘要。接下来只读仓库里的源方案、相关口径和现有实现，不碰 `review/` 下其它文件。对照现有模型、AI 注入接口、148 口径和查询摄取路径核验方案主张。工作区默认在 `review/round-1`，改为在仓库根目录检索现有实现，避免读到其它审查稿。# 149 值域知识库方案 · 独立只读审查

审查对象是 `方案.md` 所摘要的 `开发起步包/149_字段值域知识库与AI自动注入执行计划.md`。对照了仓库现行代码（`system-context`、`propose-sql`、`context/resolve`、sqlglot、`asset_columns.value_desc_cn`、126 ingest/impact）、`148` 原文、`55`/`README` 入口和技能路由。未改任何文件，未读 `review/` 下其它文件。

**总评：** 问题真实、方向正确（平台库权威 + 三层通道 + 禁止猜测），但 **P1 数据模型撑不住 §二关注点 2/3**；**注入设计与「不易漏」相冲**，且 **认错了解析器、漏接 144 统一 context**。P4 的 ingest 告警可后置，但 **多来源证据与冲突暴露必须进 P1**，否则会再演一遍离院方式事故。

---

## 1. 背景与问题定义

**【同意】**  
引用：`§一`「AI 依据错误字典表（COMM.DISCHARGE_DISPOSITION_DICT，实为治疗结果）猜值域，把病案首页离院方式 4/5 含义写反」。  

理由：与 `148` §1 完全一致（4=非医嘱离院、5=死亡；该字典是治疗结果）。静态文档无法保证其它 AI「记得查」。  

风险：方案后续把知识建成「code→meaning」枚举，**没有建模「禁止用某字典表」这条事故根因**，闭环可能治标不治本。

---

## 2. 目标：平台库为唯一权威 + 三层获取通道

**【同意】**  
引用：`§一`「建立平台字段值域知识库（唯一权威源）+ AI 三层获取通道」。对应 149 §1 ①自动注入 ②主动查询 ③离线 JSON/148。  

理由：与现有「关系不靠聊天记忆、先平台后资产包」一致。  

风险：三层若口径/键不一致（ODS `HIS.PAT_VISIT` vs 源端 `MEDREC.PAT_VISIT`），「权威」会分裂成两套值域。

---

## 3. 非目标（149 §0，摘要未写清）

**【同意】**  
149：「不建通用数据字典管理系统；不自动猜测；不改动 126 查询/指标语义」。  

理由：`dict_medical` 已存在；值域是字段代码语义，不是诊断/手术字典。  

风险：若不写清与 `asset_columns.value_desc_cn`（字段已有值域中文描述）的分工，会出现第三份「权威」。

---

## 4. P1 主表：一行一个 code/meaning + 单值证据

**【反对】**（关注点 2/3 的核心缺口）  
引用：`§一`「主表关键字段：… code、meaning、note、status… evidence_method、evidence_sample_count…」；`§三`点名「当前 evidence 为单字段」。  

理由：
- 148 离院方式 4 的证据同时是：HIS 实测 120 例 **+** JHEMR 交叉 128 例 **+** 用户确认 **+** 「不是 COMM 字典」。单字段 `evidence_method` 只能留一条。
- 同一 `(字段, code)` 两个 AI、两个日期给出不同 meaning，表结构只能覆盖或拒绝，**没有 conflict 状态、没有多 pending 候选**。
- 版本表只快照「已采纳行」，不能表达「未采纳的对立说法仍在」。

风险：系统无法「发现并暴露冲突」（§二.3）；人工确认时看不到对立证据；事故同型（字典表 vs 交叉验证）会再次被压成一条 note。

**P1 应改为：** 主表一字段一码一现行语义；`asset_column_value_domain_evidences` 一对多（source_type / source_system / method / sample_count / observed_at / actor / snippet_ref）；冲突用 `conflict_status` + 列出 competing meaning。版本表继续做时间线。

---

## 5. 主表未定义唯一键 / 幂等键

**【反对】**  
引用：`§一` 只列字段，无 Unique；P2 却要求「幂等导入」「重跑零重复」。  

理由：无 `(system_code, source_owner, table_name, column_name, code)` 唯一约束，幂等无法定义；pending 与 confirmed 能否共存也不清。  

风险：重复行导致 AI 注入两套含义；导入脚本无法验收。

---

## 6. 值域形态被压成 code/meaning，装不下 148 的真实口径

**【反对】**  
引用：`§一` P2「OPER_STATUS（>=35 完成、-80 取消）、免疫组化项目名、VISIT_TYPE/REGISTTYPE 急诊枚举」。  

理由：这些不是同一类对象：
- 枚举码：`DISCHARGE_DISPOSITION=4`
- 阈值：`OPER_STATUS>=35`
- 字面量：`VISIT_TYPE='急诊'`、`ITEM_NAME='免疫组织化学染色诊断'`
- **负知识/陷阱**：勿用 `COMM.DISCHARGE_DISPOSITION_DICT`；`DEATH_DATE_TIME` 源端不填  

全塞进 `code` 列会畸变（`code='>=35'`）。  

风险：注入后 AI 仍可能 `JOIN` 错字典表——这正是 2026-08-24 的失败模式。字段级需 `traps[]` / `domain_kind`。

---

## 7. `source_owner` 与平台目录键不对齐

**【疑问】**  
引用：`§一`「system_code、source_owner、table_name、column_name」。  

理由：平台 `asset_tables/columns` 用 `system_code + source_code + schema_name/namespace_name + table_name`。HIS 源是 `MEDREC.PAT_VISIT`，ODS 镜像是 `HIS.PAT_VISIT`。方案未说是否挂 `asset_columns`、如何处理同名字段双身份。  

风险：注入按 SQL 解析命中 ODS 名时查不到按 MEDREC 导入的值域（漏）；或两边各一份（冲突）。

---

## 8. P1 API 形态（GET 过滤 / POST pending / PATCH 人工 / GET versions）

**【同意】**（作为最小写读闭环）  
引用：`§一`「GET /api/v1/metadata/value-domains（…confirmed 默认）、POST（AI 提交 pending，evidence 必填）、PATCH confirm/deprecate、GET versions」。  

理由：默认只出 confirmed、AI 不能直写 confirmed，符合「防猜测」。审计走 `asset_govern_audit_logs` 与现网治理模块一致。  

风险：见下条路由/权限/批量查询缺口。

---

## 9. 「扩展现有 metadata 模块，不新建平行路由」

**【反对】**（与代码事实不符）  
引用：149 §2 P1「扩展现有 metadata/ai 模块，不新建平行路由」；方案路径 `/api/v1/metadata/value-domains`。  

理由：`main.py` 无 metadata 资源路由器，只有 `metadata_changes`。`/api/v1/metadata/*` 本身就是新前缀。  

风险：实现时临时塞进 `tables.py` 或 `metadata_changes.py`，权限与 OpenAPI 分组混乱。应明确新 router（可接受）或并入 `tables` 字段详情。

---

## 10. 主动查询通道对关注点 1（快、准、不易漏）不够

**【疑问→偏反对】**  
引用：`§二.1`「获取通道要快、准、不易漏」；`§一` 仅按 system/table/column 过滤的 GET。  

理由：现网 AI 主路径是 `POST /api/v1/ai/context/resolve`（144）和技能里的 `GET /api/v1/ai/system-context`。方案：
- **未把值域列入 `AVAILABLE_TOOLS` / MCP**
- **未定义按「列清单」批量查询**
- **未定义 `updated_since` / ETag**
- **未接 `context/resolve`**（149 §1 写了 `/api/v1/ai/context` 全量摘要，P1 表却没做）

技能每次猜表名再 GET，易漏。  

风险：其它 AI 继续只走 144 context，值域库形同不存在。

---

## 11. 自动注入：解析 SQL 字段后附 confirmed 数组

**【反对】**（与关注点 1 直接冲突）  
引用：`§一`「扩展 system-context 与 propose-sql：解析 SQL 涉及字段自动附 confirmed 值域数组」；`§一` Q2「宁缺勿错」。  

理由：
1. **`GET /system-context` 没有 `sql_text`**，参数是 `system_code + max_tables`（默认 30）。ods 技能取数前就会打这个接口，此时还没有 SQL，谈不上「解析 SQL 涉及字段」。
2. 该接口 `limit(max_tables)`，无稳定排序，**值域所在表经常不在导出的 30 张里**——这是结构性漏检。
3. Q2「宁缺勿错」= 解析失败就不注入，与 §二.1「不易漏」相反。事故字段若因别名/`NVL` 解析失败，AI 仍会猜。
4. **`POST /propose-sql` 发生在 SQL 已写完之后**，只能事后贴标签，挡不住生成阶段猜 4/5。
5. 正确热路径是：**在写 SQL 之前**把该系统（或问题命中对象）的全部 confirmed 值域 + 陷阱放进 context。首批只有几组码，应按系统全量附带，不要依赖列级解析。

风险：做成后演示能过、日常仍漏；看起来有注入，实际与 148 静态文档一样「查不到」。

---

## 12. Q2「复用 126 已有 SQL 风险扫描解析器」

**【反对】**  
引用：`§一` Q2「复用 126 已有 SQL 风险扫描解析器，只对精确命中的字段注入」。  

理由：`ai.py` 的 `_scan_sql_risk` 是关键字/大表字符串扫描，**不提取 owner.table.column**。126 `query_gate.extract_table_refs` 只提表名。能提列的是 **144 `sql_ast.py`（sqlglot）** 和查询依赖 `asset_query_dependencies`。方案认错组件。  

风险：实现者按字面去改 risk-scan，注入长期不准；P4 字面量比对同样会建在错误解析器上。

---

## 13. 审计复用 `asset_govern_audit_logs`

**【同意】**  
引用：`§一`「审计复用 asset_govern_audit_logs」。  

理由：模型已有 `module/entity_type/entity_ref/before_data/after_data`。  

风险：审计不是证据库，不能替代多来源 evidences；也不能当冲突列表给 AI 读。

---

## 14. AI POST 写平台库 vs「AI 只读」

**【疑问】**  
引用：149 §3「值域提交接口仅写平台库（非业务源库），业务源库仍零写入」。  

理由：与 `propose-sql` 写草稿同类，可接受；但 AGENTS 写明 AI 工具默认只调只读端点。方案未定义权限码、是否禁止 AI 调 confirm、RBAC 种子。  

风险：Token 过宽时 AI 自批 confirmed；过严则 pending 永远进不来。

---

## 15. P2 首批导入 148

**【同意方向 / 疑问细节】**  
引用：`§一` P2「幂等导入 148 号 **8 组**」；149 P2 表实际列了 **6 项**（离院方式、手术急诊、诊断类别、OPER_STATUS、免疫组化、VISIT_TYPE/REGISTTYPE）。148 另外还有病理不在 EXAM、门诊疾病谱表、诊断书写差异等，并非都是值域。  

理由：把已确认口径入库是对的；「8 组」与清单对不上。148 写明 code 9、手术标志 3「语义待核」，若一并 `confirmed` 会把不确定升级成权威。  

风险：错误确认比没有更糟；阈值/项目名用 code 行导入后无法正确比对 SQL。

P2 应：只导入离散枚举已确认码；待核保持 pending；陷阱/阈值用 `domain_kind` 另存。

---

## 16. P3 五技能硬规则 + JSON 兜底

**【同意方向 / 反对覆盖不足】**  
引用：`§一` P3「hisuser/ods/docare/mobile-nursing/query-governance-intake…先查平台 API→兜底 JSON/148→仍无输出【值域待确认】禁止假设」。  

理由：硬规则+禁止假设对症。query-governance 已规定先 `context/resolve`，值域应并进该步，而不是再开一条易被跳过的 GET。  

反对点：
- **漏了全局 `sjzc`**（表结构/连库入口）和 `sql-relation-intake`、`ods-schema-analysis`——问「4/5 什么意思」不一定走五技能。
- 技能默认无稳定平台 Token，API 常不可达，实际长期走 JSON/148（Q3）。
- 导出脚本路径写 `tools/export_value_domains_json.py`，仓库根 `tools/` 现只有 queryctl 等，与 `开发起步包/tools/` 易放错。

风险：路由写了但主入口没改，漏检率不变。

---

## 17. Q4 库为权威、148/JSON 为导出视图

**【同意原则 / 疑问与 148 维护约定冲突】**  
引用：`§一` Q4「库为权威，文档为导出视图」；148「后续 AI 发现新值域…追加到本文件」。  

理由：单向导出可避免双写。但 P3 仍把 148 当兜底权威，且 148 仍允许手改。  

风险：平台故障期 AI 改 148，恢复后被导出覆盖；或库与 148 分叉。应规定：148 停手改，或导出带 `generated_at` 并在 148 头注明「勿手改」。

---

## 18. P4 摄取联动是否提前

**【同意 ingest 告警可二期；反对把「冲突能力」理解成 P4】**  
引用：`§一` P4「SQL 字面量 vs confirmed 值域冲突 warning」；`§二.3`「不同来源/不同时间…冲突时系统能发现并暴露」；`§三`「P4 二期是否应提前」。  

理由：
- **来源冲突、时间冲突**不在 P4，P4 只是「已确认码 vs SQL 字面量」。关注点 3 在 P1 模型就是空的，后置 P4 也补不上。
- 原事故发生在 **写 SQL 之前猜错字典**，不是 ingest。P4 挡不住日常取数。
- ingest warning 依赖字面量解析，阈值/`IN`/绑定变量误报会很多，放二期合理。
- 「值域修订 → 引用影响分析」可复用 `/queries/impact/table`，对关注点 4 有用，但可挂在 confirm/deprecate 之后，不必阻塞 P1。

结论：**不要把整个 P4 提前；要把 evidences + conflict 从 P4 想象中拽回 P1。** 若只提前 ingest warning，ROI 低。

---

## 19. Q1 确认人机制

**【同意待定；疑问会卡住关注点 4】**  
引用：`§一` Q1「确认人机制待定；P1 先支持字段」。  

理由：字段预留 `confirmed_by/at` 可以。但「前端无改动」（149 §5）意味着确认只能打 API。现网关系复核已有大量 draft 堆积。  

风险：pending 无人消费；或 P2 用「148 已确认」批量盖章，绕过真正责任人。

---

## 20. Q3 平台不可达、JSON 滞后

**【同意】**  
引用：`§一` Q3。平台故障已发生。导出时间戳 + 接受滞后是诚实策略。  

风险：技能在 API 超时很短时过早降级，长期用旧 JSON。应规定失败判定和 JSON 最大可接受龄期。

---

## 21. 「前端无改动」

**【反对】**（相对关注点 4）  
引用：149 §5「前端无改动（本计划纯后端+文档+技能）」。  

理由：修订、追溯、统计、冲突暴露若无页面，维护分析只能 SQL。最小也要：表详情展示值域（已有 `value_desc_cn` 编辑位）、pending 计数、冲突列表。可比 P1 API 晚一个迭代，但不应写成「本计划无前端」。  

风险：与 146 界面主线脱节；治理人员看不到冲突。

---

## 22. 工作量 3 天、未进 55 执行清单

**【疑问】**  
引用：149 §6「P1 0.5+1 天…合计约 3 天」；`§一`「上位入口 55」。  

理由：`README` 已登记 149，**`55` 正文无 149 条目**。模型若补证据子表/陷阱/注入改道 context，P1 不是 0.5 天。  

风险：未入 55 就被开发，和 144/146 抢同一 `ai.py`/`queries.py`。

---

## 23. 版本表设计

**【同意（时间线）/ 不足（来源冲突）】**  
引用：`§一`「版本表：domain_id、version_no、快照、change_reason、evidence、actor」。  

理由：修订追溯满足关注点 4 的一部分。`evidence` 仍是单字段，版本也不是多来源。  

风险：误以为「有 versions 就能检测冲突」—— versions 是串行采纳史，不是并行假说集。

---

# 对照 §二 四个关注点

| 关注点 | 方案现状 | 结论 |
|---|---|---|
| 1 快/准/不易漏 | 依赖写 SQL 后解析 + 默认 30 表的 system-context；漏 144 context/MCP/批量接口 | **不满足** |
| 2 多来源证据 | `evidence_method` + `evidence_sample_count` 单值 | **不满足** |
| 3 冲突可检测 | 无 conflict 状态、无多候选、P4 只做字面量 warning | **不满足** |
| 4 扩展/修订/统计 | 版本表+审计有骨架；无唯一键、无 kind、无前端、影响分析在二期 | **部分满足** |

---

# 必须补进方案、否则会再踩坑的遗漏风险

1. **负知识/错误字典陷阱未建模**（事故根因）。  
2. **HIS 源端 vs ODS 同名表双键**，注入按错身份即漏。  
3. **与 `asset_columns.value_desc_cn` 双写**。  
4. **注入应走 `POST /api/v1/ai/context/resolve` 和 system-context 的全量 confirmed 列表，而不是 SQL 解析。**  
5. **解析器应写明 sqlglot（144），禁止写「复用 risk-scan」。**  
6. **技能覆盖漏 sjzc 等入口。**  
7. **权限、唯一约束、domain_kind 未写，P2 幂等无法验收。**  
8. **149 未列入 55，与「55 为唯一未完成入口」冲突。**

---

# 建议的最小修正（审查意见，非实施）

P1 必须包含：唯一约束、证据子表、conflict 状态、`domain_kind`（enum/threshold/literal/trap）、字段级 traps、挂 `schema_name`/`source_code`、注入到 `context/resolve` + system-context **全量 confirmed（可按 system 过滤，不依赖 SQL）**、MCP/工具清单登记、权限码。  
P2 只导入已确认枚举；待核与陷阱分开。  
P3 改 query-governance 的 resolve 步骤，并加上 sjzc。  
P4 ingest warning / 影响分析保持二期。  

**在模型未改前，不同意按当前 P1 开做。** 方向（知识库 + 禁止猜测 + 库为权威）可以批，表结构和注入点需要先改方案。
