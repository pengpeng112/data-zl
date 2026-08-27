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

## 强制步骤（144 §11.3 顺序，逐条执行）

1. **先 `resolve_query_intent` 搜认证产品/查询/指标 + 取值域**：
   `POST /api/v1/ai/context/resolve`（question_summary/system_code/business_domain）构建统一 context 快照，再用 `GET /api/v1/queries`、`GET /api/v1/metrics`、`GET /api/v1/data-products` 检索。
   命中 certified/active 资产即复用（优先数据产品），**不得重写 SQL**。
   **值域（149 强制）**：context 响应的 `value_domains` 段携带该系统全部 confirmed 值域+陷阱（逐条带 version_no）——涉编码/状态/阈值/字典类字段的取数口径必须以它为准，禁止凭字典表名、字段注释或惯例猜测。
2. **未命中才生成新 SQL**：按来源技能（ods/hisuser/mobile-nursing/docare-readonly-sql）查元数据和已验证关系；
   SQL 的每个 JOIN 必须有正式关系/active 配方证据；bind 参数与 parameter_schema 完全一致（`:name`，未知/缺失/未用均会被平台阻断）。
   **值域兜底（149）**：context 未返回涉字段的值域或平台不可达 → 先读离线 `开发起步包/数据资产_资产包/value_domains.json`（超过 max_age_days=7 天须提示用户重新导出）→ 再查 `开发起步包/148_病案首页关键值域与离院方式口径字典.md`（平台导出视图）→ 仍无则 SQL 写注释 `【值域待确认：OWNER.TABLE.COLUMN】` 并在交付说明中明示，**不得假设含义**；陷阱（trap，如勿用 `COMM.DISCHARGE_DISPOSITION_DICT` 判读离院方式）同样强制。发现新值域证据按 149 提交平台 pending（`POST /api/v1/value-domains`，证据必填；AI 仅可提交，确认/裁决须人工）。
3. **提交与验证**：`queryctl init/validate/submit`（本地校验含 bind 一致性、grain/period_field、LAB_RESULT TEST_NO 限定）或平台 `POST /api/v1/queries/ingest`；
   激活后调 `POST /api/v1/queries/{code}/versions/{v}/validate` 取 G1–G3 逐层证据。
4. **每次执行必须回传 refs**：回答必须带 query_code@version、run_id、result_digest、data_as_of、correlation_id；
   `POST /api/v1/ai/answers` 登记 provenance。
5. **回答末尾提供反馈方式**：告知用户可 `POST /api/v1/ai/feedback`（rating + 18 类错误分类）提交准确性反馈。
6. **被用户纠正时**：先 `POST /api/v1/ai/answers` + `POST /api/v1/ai/feedback` 提交反馈并（经人工复核后）关联新版本草稿/黄金用例——
   不能只在聊天里道歉；反馈永远不自动发布查询/指标/产品/关系。
7. **平台不可用**才读仓库资产包，且必须先读该包 `manifest.json`（role=full 的 CSV 才是全量；catalog.json 只是摘要）；过期/不完整必须明示。

## 执行与计算

- 查询执行：`POST /api/v1/queries/run`（参数真实 bind 到连接器；recalc 需权限+理由）
- 指标计算：`POST /api/v1/metrics/{code}/calculate`（真实分子/分母/公式引擎，批次幂等）
- 数据产品：`POST /api/v1/data-products/{code}/execute`（参数 schema 校验+限流）
- 回归评测：`POST /api/v1/ai/evaluations/run`；看板 `GET /api/v1/ai/evaluations/dashboard`（只统计已审核反馈与黄金用例）

## 工具

- `tools/queryctl.py`：init / validate（144 语义契约）/ submit / context
- 平台 API：`/api/v1/queries/*`、`/api/v1/metrics/*`、`/api/v1/data-products/*`、`/api/v1/ai/*`、`/api/v1/lineage/*`
- 资产包回退：`开发起步包/数据资产_*/manifest.json`（用 `开发起步包/tools/build_asset_manifest.py --verify` 校验）

## 禁止

- 不写业务源库 DML/DDL；不输出患者明细或凭据
- 不依赖聊天记忆获取表关系；以平台 context/关系配方/查询资产为准
- 不凭字典表名/字段注释猜测字段值域（149）；离线 JSON 超龄 7 天未提示即不得引用
- 不自行 confirm 值域候选（value_domain:confirm 仅人工角色）
- 不把 legacy_unverified 资产宣称为 certified；不把未评价回答计为正确
- 不自动批准关系、查询、指标或产品
- 不创建任意 SQL 产品；产品只引用已发布目录项

## 状态语义（144 §12）

- `active` = 现行默认版本；`certified` = 通过 G5 评测的认证状态（独立字段）
- `legacy_unverified` = 144 之前的存量 active，可执行但回答须标注，不得被新产品 pin 或作黄金基准
- candidate/blocked 版本禁止执行与被引用
