> 类别：当前对接规范
>
> 状态：当前
>
> 适用范围：通过本助手、其他 AI、Dify、MCP 或人工方式生成视图查询 SQL，并将 SQL、关系依据和审核信息接入数据资产平台。

# AI 视图 SQL 生成与平台对接说明

> **144 实施注记（2026-08-23）**：144 S2–S9 已落地以下实现，本文件中与之不一致的描述以运行时 `/docs` 与 144 §16.1 执行记录为准——
> 参数真实 bind 连接器、状态/来源/大表（AST 含 WHERE 1=1 拒绝）门禁、result/schema digest 与 data_as_of、指标真实计算引擎（批次/维度唯一键）、
> 精确 object_key 与静态血缘（asset_lineage_edges）、统一 AI context（/api/v1/ai/context/resolve）、反馈—评测闭环（/api/v1/ai/feedback|evaluations）。
> 旧 AI context 返回完整 SQL 的行为已改为默认仅哈希（需 ai:sql:full_read 权限）。


## 1. 目的与最终边界

本规范用于指导 AI 根据平台已经登记的系统、数据库、Schema、表、字段、关系和关系配方生成**视图查询 SQL**。

本阶段只生成、保存、审核和只读验证 SQL，不创建数据库视图：

- 标准交付物是完整的 `SELECT` 查询语句。
- 不输出或执行 `CREATE VIEW`、`CREATE OR REPLACE VIEW`。
- 不对 HIS、HRP、数据中心、LIS、PACS、移动护理、手麻、无纸化、超声内镜、JHEMR 等业务源库执行 DML 或 DDL。
- AI 不调用运维写执行器，不执行 `INSERT`、`UPDATE`、`DELETE`、`MERGE`、`CREATE`、`ALTER`、`DROP`、`TRUNCATE`、`GRANT` 或 `REVOKE`。
- SQL 可以进入平台草稿、风险扫描、人工审核和受控只读试运行；是否以后由 DBA 创建正式视图不属于本规范范围。

因此，本文中的“视图 SQL”均指**未来可作为视图查询主体的 SELECT SQL**，不是创建视图的 DDL。

## 2. 权威依据与接口版本

对接时按以下优先级判断：

1. 运行环境的 `/docs` OpenAPI 契约。
2. `backend/app/api/v1/ai.py` 和 `backend/app/api/v1/recipes.py` 的实际代码。
3. 本文。
4. `_archive/54_关系口径库与视图配方库系统整改方案.md` 等历史设计文档。

当前关系配方的实际 API 前缀是：

```text
/api/v1/recipes
```

旧方案中的 `/api/v1/relation-recipes`、`/api/v1/ai/relation-recipes` 不是当前调用路径，其他 AI 不得按旧路径自行猜测接口。

所有响应使用平台统一包装，成功时通常为：

```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```

生产环境接口需要合法身份凭据和相应权限。Token、数据库密码及凭据引用不得写入提示词、SQL注释、报告或 Git。

## 3. 对接总流程

```text
明确业务问题和目标系统
        ↓
取得系统级脱敏元数据
        ↓
确认目标表字段和正式关系
        ↓
读取已生效的关系配方
        ↓
生成仅含 SELECT 的视图 SQL
        ↓
执行 SQL 风险扫描
        ↓
保存为 AI SQL 草稿
        ↓
人工审核
        ↓
可选：通过只读执行器限量验证
        ↓
保存 SQL、关系依据、验证结论和版本
```

禁止跳过元数据与关系核查后，仅凭相似字段名生成跨系统 JOIN。

## 4. 第一步：建立 AI 会话

推荐每个业务需求建立独立会话，方便审计和追踪。

```http
POST /api/v1/ai/sessions
Content-Type: application/json

{
  "purpose": "生成住院患者检查报告视图查询SQL"
}
```

保存响应中的 `session_key`，后续提交 SQL 草稿时携带。不同业务主题不要共用一个长期会话。

AI 可先读取工具目录：

```http
GET /api/v1/ai/tools
```

工具目录用于发现平台已经开放的只读能力，不代表 AI 可以绕过权限或调用未登记端点。

## 5. 第二步：取得系统与资产上下文

### 5.1 按系统取得上下文

```http
GET /api/v1/ai/system-context?system_code=HIS_SOURCE&max_tables=30
```

`system_code` 必须使用平台实际登记值，不可从中文显示名称猜测。系统范围过大时应按业务主题缩小表集合，避免一次导出全库。

### 5.2 按指定表导出上下文

```http
POST /api/v1/ai/export-context
Content-Type: application/json

{
  "tables": [
    "HIS.PAT_VISIT",
    "HIS.EXAM_MASTER",
    "HIS.EXAM_REPORT"
  ],
  "include_relations": true,
  "include_columns": true
}
```

一次最多导出 50 张表。优先只导出需求涉及的表，不导出患者明细数据。

### 5.3 进一步核查表、字段和关系

AI 可使用 `/api/v1/ai/tools` 返回的实际路径调用以下只读能力：

| 能力 | 当前用途 |
|---|---|
| `search_tables` | 按表名或业务域搜索资产 |
| `get_table_schema` | 获取字段、类型和注释 |
| `get_relations` | 获取某张表的正式关系 |
| `get_path` | 查找两张表之间的关联路径 |
| `search_columns` | 按“住院号”等业务词搜索字段 |
| `get_graph` / `get_graph_neighbors` | 获取关系图或局部邻居 |
| `get_lineage_impact` | 查看表被哪些视图引用 |
| `get_view_dependencies` | 查看已有视图的基础表依赖 |

关系使用优先级：

1. 活库验证为 A 的关系；
2. 已采纳的 B/C 关系，并在 SQL 说明中写明限制条件；
3. 已生效关系配方中的关系；
4. 已有视图 SQL 中能够明确解析的 JOIN；
5. 仅凭同名字段推断的关系只能作为候选，不得直接作为正式视图依据。

## 6. 第三步：读取已审核的关系配方

```http
GET /api/v1/recipes/ai/context
```

也可按业务域过滤：

```http
GET /api/v1/recipes/ai/context?domain=exam_imaging_report
```

该接口只返回同时满足以下条件的配方：

- `status=active`；
- `is_active=true`；
- `ai_readable=true`。

AI 必须重点读取：

- `recipe_id` 和 `version`；
- `primary_tables`；
- `joins`；
- `recipe_json` 中的字段逻辑和限制；
- `content_hash`；
- `source_system`、`domain` 和 `business_domain`。

未生效版本、历史版本或候选关系不得冒充当前权威口径。

平台也可按配方直接生成安全的 SELECT 骨架：

```http
POST /api/v1/recipes/{recipe_id}/versions/{version}/sql
Content-Type: application/json

{
  "dialect": "oracle"
}
```

当前该端点接受 `oracle` 或 `postgresql`，返回示例：

```json
{
  "code": 0,
  "data": {
    "recipe_id": "exam_report_v1",
    "version": 1,
    "dialect": "oracle",
    "sql": "SELECT ...",
    "executed": false
  }
}
```

该 SQL 只是预览，不会执行。MySQL、SQL Server 和 Vastbase 的复杂方言 SQL目前由 AI 按本文规则生成，再进入统一风险扫描和草稿流程。

## 7. AI 生成 SQL 的强制输出规范

### 7.1 必须输出的内容

每次生成至少包含：

1. 业务目的；
2. 目标系统、数据库和 Schema；
3. 采用的配方编号及版本，没有配方时写“无”；
4. 使用的表和别名；
5. JOIN 条件及其关系等级/证据来源；
6. 字段清单和字段含义；
7. 过滤口径；
8. 数据风险和已知限制；
9. 数据库方言；
10. 一条完整、可独立审查的 SELECT SQL。

### 7.2 SQL主体规则

- 只允许一个只读 `SELECT`，可包含只读 CTE。
- 不带 `CREATE VIEW` 包装。
- 不使用 `SELECT *` 作为最终交付，必须显式列出字段并给出稳定别名。
- 表名使用 `Schema.Table`；跨数据库时按实际数据库能力写全限定名，不虚构 DBLINK。
- 所有字段必须在平台元数据或活库只读核查中确认存在。
- JOIN 必须写明完整组合键，不得把 `PATIENT_ID + VISIT_ID` 简化为单列。
- 避免隐式类型转换；不同类型关联时必须说明转换方向和索引影响。
- 视图 SQL 不写环境密码、Token、IP、患者姓名、身份证、电话、地址等敏感信息。
- 默认不返回敏感明细字段；确需使用时在最终投影中脱敏。
- 不使用无边界的递归、笛卡尔积或大表全扫。
- SQL末尾可以有一个分号，但不得拼接第二条语句。

### 7.3 医疗数据关键口径

- HIS 住院主线优先使用 `PATIENT_ID + VISIT_ID`。
- 门诊使用已验证的门诊号口径，不把 `VISIT_ID=0/NULL` 当住院数据。
- 检验优先使用 `TEST_NO`；`HIS.LAB_RESULT` 禁止无 `TEST_NO` 限定的全表扫描。
- 检查优先使用 `EXAM_NO`；`EXAM_REPORT` 必须经 `EXAM_NO` 关联检查主表。
- 不将同名字段自动视为主外键。
- 跨系统关系必须使用已验证映射；D 类待验证关系不得进入正式 SQL 主线。

### 7.4 方言要求

| 数据库 | 生成要求 |
|---|---|
| Oracle 11g | 不使用 `FETCH FIRST`；限量验证使用 `ROWNUM <= N`；兼容旧版函数 |
| PostgreSQL | 使用 PostgreSQL 类型和函数；限量可用 `LIMIT` |
| Vastbase | 先按活库版本核对兼容性，不默认所有 PostgreSQL 扩展可用 |
| MySQL | 标识符、日期函数、字符串函数按 MySQL 版本生成 |
| SQL Server | 明确数据库和 Schema；限量使用 `TOP`；避免把 `NOLOCK` 当数据正确性的默认保障 |
| 海量数据库 | 平台当前按 Vastbase 接入，生成前必须确认实际库名和版本 |

当一个需求跨越不同数据库实例时，不得生成一个假定可跨库运行的 SQL。应拆成每个物理数据源各自可运行的 SELECT，并单独给出后续汇聚建议。

## 8. 推荐的 AI 输出模板

其他 AI 应按以下结构交付：

````markdown
## 视图SQL说明

- 业务目的：
- 目标系统：
- 目标数据库/Schema：
- 数据库方言：oracle
- 推荐逻辑名称：V_xxx（仅名称建议，不执行创建）
- 配方：recipe_id / version / content_hash
- 使用表：
- 关系依据：
- 过滤口径：
- 已知限制：

## SQL

```sql
SELECT
    ...
FROM ...
WHERE ...;
```

## 自检结果

- 仅 SELECT：是
- 包含 DDL/DML：否
- 字段均已核对：是/否
- 关系均有证据：是/否
- 大表已限定：是/不涉及
- 敏感字段已排除或脱敏：是/不涉及
````

如果任一自检项为“否”，AI必须标记为候选草稿，不得声称可直接使用。

## 9. SQL 风险扫描

生成后先调用：

```http
POST /api/v1/ai/sql-risk-scan
Content-Type: application/json

{
  "sql_text": "SELECT ..."
}
```

出现以下任一情况不得进入“可审核”状态：

- `blocked=true`；
- 检出 DDL/DML 关键字；
- 大表没有业务键或时间范围；
- 缺少 WHERE 且涉及事实大表；
- 字段或表在资产目录中不存在；
- JOIN 关系没有证据或产生明显多对多膨胀；
- SQL包含多语句、注释注入或动态执行片段。

风险扫描是基础关键词和大表规则检查，不替代 SQL 解析、执行计划检查和人工业务审核。

## 10. 保存为平台草稿

扫描无阻断后调用：

```http
POST /api/v1/ai/propose-sql
Content-Type: application/json

{
  "session_key": "会话返回值",
  "title": "住院患者检查报告查询SQL",
  "purpose": "用于数据资产关系核查和后续视图候选",
  "sql_text": "SELECT ..."
}
```

平台会保存：

- SQL草稿；
- 风险标记；
- 会话关联；
- 后续审核状态；
- 工具调用审计。

保存成功不等于 SQL 正确，也不等于审核通过，更不等于已经创建视图。

草稿查询：

```http
GET /api/v1/ai/drafts?session_key={session_key}&status=draft
```

人工审核：

```http
PATCH /api/v1/ai/drafts/{draft_id}
Content-Type: application/json

{
  "status": "approved",
  "feedback": "字段、关系和过滤口径已复核"
}
```

审核状态只允许使用后端契约定义的值，不得由调用方添加伪状态。

## 11. 可选的只读验证

只有草稿已经人工批准，且 SQL 仍然是安全 SELECT 时，管理员才可选择调用只读执行器：

```http
POST /api/v1/ai/drafts/{draft_id}/execute
Content-Type: application/json

{
  "source_code": "平台已登记的只读数据源编码",
  "max_rows": 1000,
  "sample_limit": 20
}
```

限制：

- `max_rows` 为 1–5000；
- `sample_limit` 为 0–100；
- 必须使用平台登记的只读数据源；
- 返回样本必须经过现有脱敏逻辑；
- 该步骤只是验证 SELECT，不创建视图；
- 大表仍应先使用业务键、日期或子查询缩小范围，不能依靠返回行数上限掩盖全表扫描。

用户只要求生成 SQL 时，可在风险扫描和草稿保存后停止，不必执行此步骤。

## 12. 关系配方的沉淀规则

当某一 SQL 的表关系和业务口径需要反复使用时，应将其沉淀为关系配方，而不是让每个 AI 重复推断。

配方状态机：

```text
draft → submitted → approved → active → deprecated
                  ↘ rejected 后退回 draft
```

只有 `active` 配方可进入 AI context。更新已生效配方时，应复制新版本，不直接改历史版本。配方中至少保存：

- 稳定的 `recipe_id`；
- 版本号；
- 主表及角色；
- JOIN 类型、组合键和限制条件；
- 推荐字段和禁用字段；
- 业务过滤口径；
- 证据来源和验证等级；
- 推荐逻辑名称；
- 内容哈希。

AI 生成的 SQL 应记录所采用配方的编号和版本，以便关系变化时追溯影响。

## 13. 给其他 AI 的标准执行提示词

```text
你负责为医院数据资产平台生成视图查询 SQL。

你的交付物只能是 SELECT SQL，不得输出或执行 CREATE VIEW，不得执行任何 DDL/DML。

执行顺序：
1. 通过平台 system-context/export-context 获取目标系统、表、字段和关系。
2. 通过 GET /api/v1/recipes/ai/context 读取已生效关系配方。
3. 核对每张表和每个字段确实存在，记录关系证据和配方版本。
4. 按实际数据库方言生成显式字段 SELECT，不使用 SELECT *。
5. 医疗大表必须用业务键、时间或子查询限定；HIS.LAB_RESULT 必须用 TEST_NO 限定。
6. 不得凭同名字段猜测跨系统关联，不得使用 D 类待验证关系。
7. 调用 /api/v1/ai/sql-risk-scan；被阻断则修正，不得绕过。
8. 调用 /api/v1/ai/propose-sql 保存草稿，不执行视图创建。
9. 输出业务目的、系统/库/Schema、配方版本、表关系、字段、过滤口径、风险、SQL和自检结论。

如果上下文不足，应输出缺失的表、字段或关系清单，不得虚构 SQL。
```

## 14. 常见错误与处理

| 错误 | 正确处理 |
|---|---|
| 使用旧 `/relation-recipes` 路径 | 改用 `/api/v1/recipes` |
| 输出 `CREATE VIEW` | 去掉 DDL，只保留 SELECT 主体 |
| 用 `SELECT *` | 显式列出字段和稳定别名 |
| 同名字段直接 JOIN | 查询正式关系、配方或活库证据 |
| 一个 SQL 跨多个不可直连实例 | 按物理数据源拆成多个 SELECT |
| Oracle 11g 使用 `FETCH FIRST` | 改用兼容写法，验证限量使用 `ROWNUM` |
| 只限制返回行数但源端仍全扫 | 在 SQL 内加入业务键、日期或受限子查询 |
| 草稿保存后声称已完成部署 | 明确标记“已生成/已保存/未创建/未执行” |
| 把候选关系写成正式关系 | 标明候选和缺失证据，不进入正式 SQL |
| SQL 注释中写连接密码或患者信息 | 立即删除，凭据走受控引用，敏感信息不进入草稿 |

## 15. 完成交付判定

满足以下条件，才能标记“视图 SQL 已生成并完成平台对接”：

- [ ] 业务目的和目标数据源明确；
- [ ] 表、字段均来自当前资产或活库元数据；
- [ ] JOIN 均有正式关系、配方或明确验证证据；
- [ ] 已记录配方编号、版本和内容哈希，或明确说明无配方；
- [ ] SQL只有 SELECT，不含 CREATE VIEW 和任何 DDL/DML；
- [ ] 最终字段显式列出；
- [ ] 大表查询具备有效限定；
- [ ] 敏感字段已排除或脱敏；
- [ ] 方言与目标数据库一致；
- [ ] 风险扫描没有阻断项；
- [ ] SQL已保存到平台草稿并获得 `draft_id`；
- [ ] 最终报告明确写明“仅生成SQL，未创建视图，未修改业务源库”。

只完成本地文本但未保存平台草稿时，应标记“SQL已生成、尚未接入平台”；只保存草稿但未经人工审核时，应标记“已接入草稿、待审核”。

## 16. 当前能力边界

当前已经具备：

- 脱敏资产上下文导出；
- 正式关系和图谱查询；
- 已生效配方的 AI context；
- 受控 SELECT 骨架生成；
- SQL风险扫描；
- AI SQL草稿保存；
- 人工审核；
- 审核后可选的只读限量验证；
- 会话、工具调用和执行审计。

当前不在本规范内：

- 自动执行 `CREATE VIEW`；
- AI直接调用运维写通道；
- 跨物理实例自动联邦查询；
- 未验证关系自动升级为正式关系；
- 把只读试运行结果当作正式视图部署结果。

本规范后续如与运行时 OpenAPI 不一致，应先按实际代码修订本文和 README，再交给其他 AI 使用。
