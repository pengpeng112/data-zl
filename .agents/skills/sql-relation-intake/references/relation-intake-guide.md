# 关系摄取资产导航

## 获取最新资产

后续 AI 不得依赖之前对话中的表关系。每次处理 SQL 时按以下顺序获取。

### 平台优先

平台可访问时优先读取：

- `GET /api/v1/ai/system-context?system_code=<SYSTEM_CODE>&max_tables=50`
- `POST /api/v1/ai/export-context`
- `GET /api/v1/recipes/ai/context`

平台数据需记录抓取时间。只读查询端点可用于获取上下文；关系的创建、审核和发布必须遵守平台状态机。

### 仓库回退

| 系统 | SYSTEM_CODE | 表字段 | 正式关系 |
|---|---|---|---|
| 数据中心/ODS | `DATA_CENTER` | `开发起步包/数据资产_资产包/tables.csv`、`columns.csv` | `开发起步包/数据资产_资产包/relationships.csv` |
| HIS 源端 | `HIS_SOURCE` | `开发起步包/数据资产_HIS源端资产包/his_source_tables.csv`、`his_source_columns.csv` | `开发起步包/数据资产_HIS源端资产包/his_source_relationships.csv` |
| 其他已接入系统 | 以平台系统编码为准 | 对应探库资产包或元数据快照 | 对应关系结果、平台正式关系 |

其他关键证据：

- 数据中心活元数据：`开发起步包/08_数据中心元数据快照.json`
- HIS 源端活元数据：`开发起步包/16_hisuser业务库元数据快照.json`
- 视图关系种子：`开发起步包/03_view_registry.json`
- ODS 视图边：`开发起步包/数据资产_关系图谱/ods_view_join_edges.csv`
- 关系配方种子：`开发起步包/数据资产_关系图谱/view_relation_recipes.json`
- 用户治理口径：`开发起步包/40_数据治理复核口径与方法记录.md`

使用 `rg` 按 Owner、表名和字段名精准检索，避免一次加载完整大快照。

## 候选记录最小字段

每个候选至少保留：

- `source_sql_sha256`
- `source_file`
- `system_code`
- `dialect`
- `from_table` / `from_columns`
- `to_table` / `to_columns`
- `join_condition`
- `qualifiers`（状态、日期、非空、子集条件）
- `existing_relation_id`
- `intake_status`
- `confidence`
- `metadata_evidence`
- `validation_evidence`
- `risk_note`

不得把姓名、身份证、电话、地址、患者 ID 明文或 SQL 中的凭据放入候选证据。

## 去重规则

先规范化 Owner、表名、字段名为大写进行比较，但保留原始大小写用于带引号标识符。

- 同向键相等：视为直接重复。
- from/to 反转且键一一对应：视为反向重复。
- 正式关系键是候选键的真子集：不得自动合并，检查是否遗漏组合键。
- JOIN 键相同但限定条件不同：保留为同一基础边的不同适用范围，或升级为关系配方。
- 多个 JOIN 加去重/窗口函数/聚合才能保证粒度：进入配方候选，不拆成“无条件强关系”。

## 验证指标

优先生成聚合指标，不输出业务明细：

- 子表非空键数量；
- 命中父表键数量；
- 孤儿数量和孤儿率；
- 父键重复数；
- JOIN 前后行数及放大倍数；
- 限定条件覆盖数量；
- 抽样范围、时间范围和最大键数。

验证结果必须注明是全量、受限全量还是样本，不得把样本验证写成全量验证。
