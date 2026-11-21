---
name: query-governance-intake
description: >
  日常取数 SQL 与查询资产摄取：初始化取数包、校验只读 SQL、提交平台查询版本、
  复用 active/certified 查询、修订口径、受控计算指标与数据产品、提交准确性反馈。
  触发：取数、保存 SQL、query_code、queryctl、查询资产、指标口径、准确性反馈、
  黄金用例（指标完整闭环见 126 P2 + 144 S2–S7）。
---

# 查询治理摄取技能（126 P1 + 144 精准取数升级）

## 何时使用

用户要求日常取数、保存 SQL、复用查询、修订口径、导入历史查询包、计算指标、执行数据产品、提交查数准确性反馈，或提到 `取数/`、`queryctl`、`query_code` 时必须使用本技能。

## 按用户目标选择流程

- **临时核对查询**（只用于验证数字或探查数据，不作为交付 SQL 保存）：跳过平台检索与提交，直接按 sjzc live 执行；后续要交付或保存时，再补走步骤 1–3。
- **编写或审阅 SQL**：完成步骤 1–2 和静态校验；未要求保存或执行时，不提交平台、不生成 run，也不要求执行 refs。
- **本地保存**：完成检索（步骤 1）、编写与静态校验，保存到用户指定位置即完成；不要求平台提交或激活。
- **平台保存或修订口径**：完成步骤 1–3 并提交新版本，报告实际状态（active/candidate/blocked 如实呈现）；口径或 SQL 变化时创建新版本并保留旧版本；不得用“优先复用”阻止用户明确要求的修订。
- **复用**：命中 certified/active 且满足需求时使用现有版本执行，参数变化通过 bind 传入、不新建版本。
- **执行查询、指标或数据产品**：完成步骤 1–5；只有真实执行成功后才回传执行 refs。平台写入和执行仍受现有权限、审计和审批门禁约束。
- **纠正与反馈**：用户明确要求登记反馈，或本次已通过平台产生回答记录时执行步骤 6；仅在聊天中讨论或审阅草稿时，不擅自写平台反馈。

“进入查询资产流程”包括检索、编写和本地校验，不必然包含平台提交；是否保存、提交或执行按用户目标和已有授权决定。

下列步骤在所选流程内按顺序执行：

1. **先 `resolve_query_intent` 搜认证产品/查询/指标 + 取值域**：
   `POST /api/v1/ai/context/resolve`（question_summary/system_code/business_domain）构建统一 context 快照，再用 `GET /api/v1/queries`、`GET /api/v1/metrics`、`GET /api/v1/data-products` 检索。
   命中 certified/active 且来源、粒度、时间口径、字段和参数均满足本次需求时优先复用（优先数据产品）。用户要求修订或口径不一致时生成新版本，不覆盖旧版本。
   **值域（149 强制）**：context 响应的 `value_domains` 段携带该系统全部 confirmed 值域+陷阱（逐条带 version_no）——涉编码/状态/阈值/字典类字段的取数口径必须以它为准，禁止凭字典表名、字段注释或惯例猜测。
2. **未命中才生成新 SQL**：按来源技能（ods/hisuser/mobile-nursing/docare-readonly-sql）查元数据和已验证关系；
   拟正式执行的 SQL 每个 JOIN 必须有正式关系/active 配方证据；候选草稿可引用明确标注的待审证据，仅供分析和补证，不得作为正式查询执行；bind 参数与 parameter_schema 完全一致（`:name`，未知/缺失/未用均会被平台阻断）。
   **值域兜底（149）**：context 未返回涉字段的值域或平台不可达 → 按仓库 `AGENTS.md` 硬约束 6 的取值顺序与缺失处理（含“实测候选值域”、离线 JSON 超龄注明日期）执行。发现新值域证据时，先纳入本次候选材料；用户明确要求摄取、登记，或当前任务已授权相应候选提交时，才调用 `POST /api/v1/value-domains` 写入 pending（证据必填）；否则在交付中报告建议，不因未提交而阻塞原任务。确认、裁决仍由人工完成。
3. **提交与验证**：`queryctl init/validate/submit`（本地校验含 bind 一致性、grain/period_field、LAB_RESULT TEST_NO 限定）或平台 `POST /api/v1/queries/ingest`；
   激活后调 `POST /api/v1/queries/{code}/versions/{v}/validate` 取 G1–G3 逐层证据。**激活后验证仅适用于已激活版本**，不作为本地保存或候选提交的完成条件。
4. **真实执行必须回传 refs**：回答带实际取得的 query_code@version、run_id、result_digest、data_as_of、correlation_id；未执行时明确“仅生成/审阅，未执行”，不得伪造或要求不存在的 run_id；
   `POST /api/v1/ai/answers` 登记 provenance。
5. **执行结果或用户询问反馈时提供反馈方式**：告知用户可 `POST /api/v1/ai/feedback`（rating + 18 类错误分类）提交准确性反馈；普通 SQL 草稿无需固定附加。
6. **被用户纠正时**：先修正当前回答；若用户已要求平台登记或本次回答已有平台 provenance，再提交 `POST /api/v1/ai/answers` + `POST /api/v1/ai/feedback`，并在人工复核后关联新版本草稿/黄金用例。反馈永远不自动发布查询/指标/产品/关系。
7. **离线资产回退**：平台当前资产优先。平台不可达，或核实目标对象、字段、关系**未被平台覆盖**时，可读取同系统离线资产包补证，且必须先读该包 `manifest.json`（role=full 的 CSV 才是全量；catalog.json 只是摘要）；使用时标注日期、覆盖缺口和适用限制。过期/不完整必须明示。离线证据不得冒充当前活库验证，也不得绕过正式关系审核。

## 执行与计算

- 查询执行：`POST /api/v1/queries/run`（参数真实 bind 到连接器；recalc 需权限+理由）
- 指标计算：`POST /api/v1/metrics/{code}/calculate`（真实分子/分母/公式引擎，批次幂等）
- 数据产品：`POST /api/v1/data-products/{code}/execute`（参数 schema 校验+限流）
- 回归评测：`POST /api/v1/ai/evaluations/run`；看板 `GET /api/v1/ai/evaluations/dashboard`（只统计已审核反馈与黄金用例）

## 工具

- `tools/queryctl.py`：init / validate（144 语义契约）/ submit / context
- 平台 API：`/api/v1/queries/*`、`/api/v1/metrics/*`、`/api/v1/data-products/*`、`/api/v1/ai/*`、`/api/v1/lineage/*`
- 资产包回退：`开发起步包/数据资产_*/manifest.json`（用 `开发起步包/tools/build_asset_manifest.py --verify` 校验）

## 给业务看的说明

交付说明、可转发文字和导出表的写法，以根目录 `AGENTS.md`「取数说明与交付口气」为准（2026-10-13 用户确认，所有 `取数/` 任务适用）。按同事交接来写，写清时间、来源、科室、条数、排除和空列原因。`query_code`、`run_id`、哈希只留在 SQL 文件头或内部备注。导出表只保留对方模板的列。

## 禁止

- 不写业务源库 DML/DDL；不输出患者明细或凭据
- 不依赖聊天记忆获取表关系；以平台 context/关系配方/查询资产为准
- 不凭字典表名/字段注释猜测字段值域（149）；引用超龄 7 天的离线 JSON 须注明导出日期
- 不自行 confirm 值域候选（value_domain:confirm 仅人工角色）
- 不把 legacy_unverified 资产宣称为 certified；不把未评价回答计为正确
- 不伪造或直接修改人工审批、认证和发布终态。用户已授权提交后，平台既有自动门禁仅决定查询版本状态（active/candidate/blocked），不等于人工审批或正式认证；关系、值域确认及其他明确要求人工治理的终态仍须人工处理
- 不创建任意 SQL 产品；产品只引用已发布目录项

## 状态语义（144 §12）

- `active` = 现行默认版本；`certified` = 通过 G5 评测的认证状态（独立字段）
- `legacy_unverified` = 144 之前的存量 active，可执行但回答须标注，不得被新产品 pin 或作黄金基准
- candidate/blocked 版本禁止执行与被引用
