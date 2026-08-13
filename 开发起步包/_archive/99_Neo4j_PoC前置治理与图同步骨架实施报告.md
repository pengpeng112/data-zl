> 类别：实施报告
>
> 状态：复核未通过，存在 P0 阻断，整改入口为 100 号；禁止生产迁移与 Neo4j PoC | 日期：2026-07-29
>
> 范围：98 号说明 S0 前置治理 + Neo4j PoC 可运行骨架（同步抽象 + 内存适配器 + 图查询骨架）。
>
> 安全边界：不部署生产 Neo4j，不连业务源库，不执行生产迁移，PostgreSQL 始终唯一事实源。

# 99 Neo4j PoC 前置治理与图同步骨架实施报告

> 2026-07-29 复核更正：本报告记录的是首轮代码骨架实施，不代表 S0 验收通过。
> 复核确认迁移唯一匹配、纯表名拆分、物理节点唯一化、有向图算法、默认降级和
> 同步幂等存在阻断问题。后续不得依据本报告直接执行迁移或启动 PoC，统一按
> `100_Neo4j_S0阻断问题修复与PoC放行计划.md` 整改。

## 1. 本轮完成范围

依据 98 号说明 S0 门禁和 97 号计划 G2/G3，完成以下**代码骨架**（非生产上线）：

1. asset_relations 端点身份四元组 + 时间戳 + 分层 + 业务键（迁移 + 模型 + 回填）。
2. 关系导入/候选转正式/审核/图谱查询的 4 个写入点 + 2 个读取点同步维护新字段。
3. updated_at 应用层可靠刷新。
4. 图节点物理唯一键（四元组）。
5. 图同步抽象 + 内存适配器（全量重建/增量 upsert/全量差集/批次记录）。
6. 图查询安全骨架（4 固定查询 + 硬限制 + 拒绝自由 Cypher + 降级）。
7. 12 项测试（纯逻辑 22 子项通过；DB 集成测试因测试库缺失阻断）。

## 2. 修改文件清单

### 新增（7）

| 文件 | 用途 |
|---|---|
| `backend/alembic/versions/c5d6e7f8a9b0_relation_endpoints_layer_sync_batch.py` | 手写迁移：端点字段+时间戳+分层+业务键+回填+sync_batches 表 |
| `backend/app/models/graph_sync.py` | GraphSyncBatch 模型 |
| `backend/app/services/relation_identity.py` | 端点身份/业务键/分层统一工具（4 写入点共用） |
| `backend/app/services/graph_sync.py` | 图同步抽象 + InMemoryGraphAdapter + 全量/增量/差集/批次 |
| `backend/app/api/v1/graph_analysis.py` | 图查询安全骨架（4 查询 + 硬限制 + 降级） |
| `backend/tests/test_relation_endpoints_unit.py` | 关系身份纯逻辑单测（15 项） |
| `backend/tests/test_graph_sync.py` | 图同步纯逻辑单测（7 项） |

### 修改（9）

| 文件 | 改动 |
|---|---|
| `backend/app/models/asset.py` | AssetRelation 加 12 字段 |
| `backend/app/models/__init__.py` | 导出 GraphSyncBatch |
| `backend/app/api/v1/graph.py` | GraphNode 增 physical_key（四元组） |
| `backend/app/api/v1/relations.py` | 3 处写点加 updated_at 刷新 + layer 重算 |
| `backend/app/api/v1/candidates.py` | promote_candidate 填新字段 |
| `backend/app/services/asset_import_upsert.py` | upsert_relations 填新字段 + 刷新 updated_at |
| `backend/app/schemas/asset.py` | RelationOut 加 12 字段 |
| `backend/app/schemas/graph.py` | GraphNode 加 physical_key |
| `backend/app/main.py` | 注册 graph_analysis 路由 |
| `backend/alembic/env.py` | import GraphSyncBatch |

## 3. 数据模型与同步机制说明

### 3.1 端点物理身份

asset_relations 新增 from/to 各 4 个字段（system_code/source_code/schema_name/table_name），构成图节点物理唯一键。历史回填规则：

- schema_name/table_name：从 from_table/to_table（`SCHEMA.TABLE` 格式）按首个 `.` 拆分。
- system_code/source_code：JOIN asset_tables 唯一反查；**多命中（跨系统同名表）或未命中置 NULL，不猜测**（符合 98 号"无法唯一确认进待审核"）。

### 3.2 分层与业务键

- `relation_layer`：formal/candidate/dependency/deferred/sync_mapping，按 confidence/validation_status 推导（口径与迁移回填一致）。
- `relation_business_key`：md5(from_table|to_table|from_columns|to_columns|join_condition)，不依赖会漂移的 rel_id，用于导入幂等查重。

### 3.3 updated_at 刷新

应用层手动赋值（仿 systems.py 资产域惯例），在 relations.py 的 update_relation/batch_review_relations/review_relation 三处 + asset_import_upsert.py 更新时刷新 `updated_at = datetime.now(timezone.utc)`。

### 3.4 同步机制

graph_sync.py 提供 GraphSyncAdapter 基类 + InMemoryGraphAdapter：

- `run_full_rebuild`：清空图 → 全量导出正式层关系 → 重建节点/边（幂等）。
- `run_incremental_upsert`：基于 updated_at 增量 upsert（幂等；不声称发现物理删除）。
- `run_daily_diff_check`：全量差集检测删除/停用/降级。
- `_record_batch`：写 asset_graph_sync_batches（batch_id/时间/状态/计数/checksum/error_masked）。
- 图分析层异常捕获返回 degraded，不影响 PG；不实现图→PG 反向同步。

## 4. 测试命令及真实结果

```
cd F:\python\数据资产\backend
.\.venv\Scripts\python.exe -m pytest tests/test_relation_endpoints_unit.py tests/test_graph_sync.py --noconftest -q
```

**结果：22 passed in 0.85s** ✅

```
.\.venv\Scripts\python.exe -m py_compile <18 个文件>
```

**结果：全部 OK** ✅

```
.\.venv\Scripts\python.exe -m alembic heads
```

**结果：c5d6e7f8a9b0 (head)，唯一 head 无分叉** ✅

## 5. 未通过或未执行项目

| 项 | 状态 | 原因 |
|---|---|---|
| `pytest tests/ -q`（DB 集成测试） | **未执行** | 本机无 APP_TEST_DB_URL，PG17 服务停止；conftest 按设计拦截（returncode=2） |
| `alembic upgrade/downgrade` 往返 | **未执行** | 同上，无测试库；**未使用生产库替代** |
| test_relation_endpoints_migration.py（迁移往返/回填/不合并/多关系/updated_at） | **代码就绪，未执行** | 依赖测试库 |
| test_graph_analysis.py（降级/限制/无 Cypher HTTP 测试） | **代码就绪，未执行** | 依赖 TestClient + 测试库 |
| 前端 typecheck/build | **未执行** | 本轮无前端改动（graph_analysis 是后端骨架） |

## 6. 安全边界确认

- 业务源库 DML/DDL：**0**（全程不连 HIS/ODS/JHEMR/LIS/PACS）。
- 凭据：未进入代码/迁移/测试/日志/git。
- **未部署生产 Neo4j**；未开 7473/7474/7687 端口。
- **未执行生产迁移**：c5d6e7f8a9b0 仅写文件，生产 upgrade 需用户明确批准。
- PostgreSQL 始终唯一事实源；图分析层单向、可重建、可降级。
- AI 无图数据库写权限（graph_analysis 全部只读 GET）。
- 测试日志无凭据（testNoCredentialsInLogs 验证）。

## 7. 下一步是否具备进入隔离 Neo4j PoC 的条件

**代码条件已具备**：同步抽象（GraphSyncAdapter）+ 查询骨架（4 固定查询）+ 内存适配器（可验证逻辑）+ 测试就绪。

**仍需**：
1. 配置 APP_TEST_DB_URL，执行迁移往返验证 + DB 集成测试（test_relation_endpoints_migration / test_graph_analysis）。
2. S1 资源与网络评估（10.10.8.83 CPU/内存/容器占用）。
3. 隔离 Neo4j 实例（测试容器或独立服务器）。
4. 实现 Neo4jGraphAdapter（继承 GraphSyncAdapter，注入 graph_analysis 的 set_analysis_adapter）。
5. 用户批准后才同步生产关系数据。

**声明**：本轮产出是"代码骨架就绪"，**不是"生产已上线"**。Neo4j 未安装、未连接、未同步任何生产数据。
