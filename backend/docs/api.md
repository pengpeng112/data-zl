# 数据资产平台 API 文档

> 版本：0.2.0 | 更新：2026-07-04 | P1–P5 全能力

## 统一响应格式

所有接口返回：

```json
{
  "code": 0,
  "message": "success",
  "data": { }
}
```

- `code`: 0 = 成功，非 0 = 错误
- `message`: 提示信息
- `data`: 响应数据

## 错误响应

```json
{"code": 400, "message": "请求参数错误", "data": null}
{"code": 401, "message": "缺少 Authorization: Bearer <token>", "data": null}
{"code": 403, "message": "无效或已禁用的 API Token", "data": null}
{"code": 404, "message": "资源不存在", "data": null}
{"code": 422, "message": "参数校验失败", "data": ["field: error"]}
{"code": 500, "message": "服务异常，请联系管理员", "data": null}
```

## 鉴权

- 全局 Bearer Token 鉴权（公开路径除外）。
- 首次使用：`GET /api/v1/admin/init` 获取默认 Token（仅首次可用，再次调用返回 403）。
- 后续请求加 `Authorization: Bearer <token>`。
- 公开路径（无需 Token）：
  - `/` `/health` `/docs` `/openapi.json` `/redoc`
  - `/api/v1/health`
  - `/api/v1/ai/tools`
  - `/api/v1/admin/init`

## 分页参数

所有列表接口使用：

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `page` | int | 1 | 页码，>=1 |
| `page_size` | int | 20 | 每页条数，1-200 |
| `sort` | string | - | 排序字段，前缀 `-` 表示降序 |

分页响应格式：

```json
{
  "total": 865,
  "page": 1,
  "page_size": 20,
  "items": []
}
```

---

## 基础资产 API（P1）

### GET /health
健康检查，检查服务和数据库连通性。

### GET /api/v1/summary
资产总览，返回表数、字段数、关系数、业务域数。

### GET /api/v1/tables
表清单，支持搜索、分页、排序、domain 过滤。

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `keyword` | string | 否 | 模糊匹配 schema/表名/注释 |
| `domain` | string | 否 | 按业务域筛选 |
| `sort` | string | 否 | schema_name/table_name/column_count/domain |
| `page` | int | 否 | 页码 |
| `page_size` | int | 否 | 每页条数 |

### GET /api/v1/tables/{schema}/{table}
表详情，包含基本信息和关系计数。

### GET /api/v1/tables/{schema}/{table}/columns
表字段列表。

### GET /api/v1/columns/search
字段搜索，按字段名或注释匹配。

### GET /api/v1/tables/{schema}/{table}/relations
该表的上下游关系。

### GET /api/v1/relations/path
两表之间最短关联路径（BFS）。参数：`from`、`to`。

### GET /api/v1/graph
全局关系图谱。支持 `include_candidates`、`include_dependencies`、`relation_type` 筛选。

### GET /api/v1/graph/neighbors
某表的一跳/二跳邻居。参数：`table`、`depth`、`direction`。

### GET /api/v1/graph/options
图谱筛选项（schemas/domains/statuses/confidences/relation_types）。

---

## 血缘与候选关系 API（P2）

### GET /api/v1/lineage/views
查询 ODS 视图依赖（772 条）。支持 `view`、`referenced_table`、`schema` 筛选。

### GET /api/v1/lineage/impact
表影响分析：某表被哪些 ODS 视图引用、关联哪些正式/候选关系。必填 `table`。

### GET /api/v1/candidates
候选关系列表（732 条）。支持 `status`（candidate/promoted/rejected）、`keyword`、`source_view` 筛选。

### POST /api/v1/candidates/{id}/promote
候选关系提升为正式关系。请求体：`{reviewer, note, domain, cardinality}`。409 表示已存在同级正式关系。

### POST /api/v1/candidates/{id}/reject
拒绝候选关系。请求体：`{reviewer, note}`。

---

## 数据质量 API（P3）

### GET /api/v1/quality/rules
内置 6 条质量规则（REL_ORPHAN_RATE / TABLE_NO_DOMAIN / COL_NULL_COMMENT / REL_NOT_VERIFIED / CANDIDATE_NOT_REVIEWED / TABLE_ZERO_COLUMNS）。

### POST /api/v1/quality/checks/run
手动触发质量检查。可选 `rule_codes` 参数选择规则。会做 findings 去重。

### GET /api/v1/quality/checks/runs
检查历史列表。

### GET /api/v1/quality/findings
质量问题列表。支持 `severity`、`status`、`rule_code`、`keyword` 筛选。

### PATCH /api/v1/quality/findings/{id}
更新问题状态。请求体：`{status, resolved_by, note}`。

### GET /api/v1/quality/summary
质量总览：各严重程度问题数、Top 问题表。

---

## AI 协作 API（P4A）

### GET /api/v1/ai/tools
AI 可调用工具目录（公开接口）。返回 10 个工具定义，含 `name`/`description`/`method`/`path`/`auth_required`/`parameters`，供 Dify/MCP/外部 AI 注册。

### POST /api/v1/ai/sessions
创建 AI 探索会话。请求体：`{purpose}`。返回 `session_key`。

### GET /api/v1/ai/sessions
会话列表。

### POST /api/v1/ai/tool-call
记录工具调用（审计）。请求体：`{session_key, tool_name, request, response_summary}`。

### GET /api/v1/ai/tool-calls
工具调用审计列表。

### POST /api/v1/ai/propose-sql
AI 提交 SQL/视图草稿（仅保存，不执行）。自动做静态风险扫描（危险关键词 + 大表警告）。请求体：`{sql_text, title?, purpose?, session_key?}`。

### GET /api/v1/ai/drafts
草稿列表。支持 `session_key`、`status` 筛选。

### PATCH /api/v1/ai/drafts/{id}
审核草稿。请求体：`{status(approved/rejected), reviewed_by?, feedback?}`。

### POST /api/v1/ai/export-context
导出脱敏 AI 上下文。必选表，单次最多 50 张。请求体：`{tables, include_relations, include_columns}`。

---

## 治理管理 API（P5）

### GET /api/v1/admin/init
初始化默认 API Token（首次使用一次性，再次调用返回 403）。

### GET /api/v1/admin/keys
API Key 列表。

### POST /api/v1/admin/keys
创建新 API Key。请求体：`{key_name}`。返回完整 Token（仅一次）。

### PATCH /api/v1/admin/keys/{id}?enabled=true|false
启用/禁用 API Key。

### GET /api/v1/admin/owners
表 Owner 列表。支持 `keyword` 搜索。

### PUT /api/v1/admin/owners
设置/更新表 Owner。请求体：`{full_table_name, owner_name, department, contact, note}`。

### DELETE /api/v1/admin/owners/{id}
删除 Owner。

### GET /api/v1/admin/terms
业务术语列表。

### PUT /api/v1/admin/terms
添加/更新业务术语。请求体：`{term, mapping_target, mapping_type?, description?}`。

### DELETE /api/v1/admin/terms/{id}
删除术语。

### GET /api/v1/admin/terms/lookup?q=住院号
按业务词查找映射。

### POST /api/v1/admin/snapshots
创建元数据快照。请求体：`{label?}`。

### GET /api/v1/admin/snapshots
快照列表。

### GET /api/v1/admin/snapshots/compare?id1=&id2=
对比两个快照（表增减、关系变化）。

---

## 安全说明

- 所有接口经全局 Bearer Token 鉴权（公开路径除外）。
- AI 工具目录含 `auth_required` 字段，Dify 可据此区分公开/需鉴权工具。
- `propose_sql` 仅保存草稿并做静态风险扫描，不执行。
- AI 导出只包含元数据（表名/字段/类型/注释/已确认关系），不含患者明细。
- AI 导出必须指定表，单次最多 50 张。
