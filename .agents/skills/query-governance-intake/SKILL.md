---
name: query-governance-intake
description: >
  日常取数 SQL 与查询资产摄取：初始化取数包、校验只读 SQL、提交平台查询版本、
  复用 active 查询、修订口径。触发：取数、保存 SQL、query_code、queryctl、
  查询资产、指标口径（指标完整闭环见 126 P2）。
---

# 查询治理摄取技能（126 P1）

## 何时使用

用户要求日常取数、保存 SQL、复用查询、修订口径、导入历史查询包，或提到 `取数/`、`queryctl`、`query_code` 时必须使用本技能。

## 强制步骤

1. 读 `取数/START_HERE.md`、`开发起步包/126_*.md`、`AGENTS.md`。
2. 先 `GET /api/v1/queries` 或 `ai/context` 搜索是否已有 `query_code` / active 版本。
3. 无复用时用 `python tools/queryctl.py init` 创建包，或直接平台 `POST /api/v1/queries/ingest`。
4. SQL 仅 SELECT/只读 CTE；大表必须有限定；禁止凭据与患者明细。
5. 自动门禁通过后即 active；blocked 不得宣称已生效。
6. 参数变化只 run，不新建 version；SQL/口径变化必须 revise。
7. JOIN 新关系走 `sql-relation-intake`，不直接写正式关系。

## 工具

- `tools/queryctl.py`：init / validate / submit / context
- 平台 API：`/api/v1/queries/*`

## 禁止

- 不写业务源库 DML/DDL
- 不把本技能结果写成生产已发布
- 不在 P1 创建 `asset_metric_*`（P2）
