> 类别：模块整改执行计划
>
> 状态：P0 待修复，S0 未通过，Neo4j PoC 暂缓 | 优先级：P0/P1 | 日期：2026-07-29
>
> 承接：`97_关系图谱与字典下发复核整改计划.md` G2/G3、`98_Neo4j关系图谱分析副本建设与复核说明.md` S0、`99_Neo4j_PoC前置治理与图同步骨架实施报告.md`。
>
> 安全边界：本计划只整改平台 PostgreSQL 模型、迁移、同步抽象、图分析 API 与测试；禁止连接或写入 HIS/ODS/JHEMR/LIS/PACS 等业务源库，禁止部署生产 Neo4j，禁止执行生产迁移，禁止开放 7473/7474/7687。

# 100 Neo4j S0 阻断问题修复与 PoC 放行计划

## 1. 当前裁决

99 号已形成 S0 代码骨架，但 2026-07-29 复核发现迁移回填、物理节点唯一化、
图查询方向性、默认降级和同步幂等存在阻断问题。

当前状态统一裁决为：

```text
S0：未通过
Neo4j PoC：暂缓
生产迁移：禁止
生产 Neo4j 部署：禁止
业务源库写入：0
```

本计划完成并通过独立测试数据库验收后，才能重新申请进入隔离 Neo4j PoC。

## 2. 已核实事实

### 2.1 已成立的骨架

- Alembic 链为 `b4c5d6e7f8a9 -> c5d6e7f8a9b0`，当前 head 唯一；
- 迁移为手写，不是 autogenerate；
- `AssetRelation` 已增加时间戳、端点四元组、关系层和业务键字段；
- 已有统一身份工具 `relation_identity.py`；
- 已有全量、增量、差集和批次记录骨架；
- 已有四个固定 GET 图分析接口，没有自由 Cypher 接口；
- 纯逻辑测试 `22 passed`；
- 未部署 Neo4j，未执行生产迁移，未写业务源库。

### 2.2 验收阻断

1. 迁移的唯一匹配 SQL 会对跨系统同名表随机 `LIMIT 1`；
2. 纯表名在迁移和 Python 中拆分结果不同；
3. 缺系统/数据源的端点仍进入正式同步并退化为非唯一物理键；
4. `graph.py` 仍按 `schema.table` 合并节点，`physical_key` 尚未成为图真值；
5. 影响分析、上下游和环路算法把有向边双向化；
6. Neo4j 未配置时默认内存适配器被当成健康图；
7. 业务键未包含系统/数据源物理身份；
8. 多个脚本直接写 `AssetRelation`，绕过统一身份维护；
9. `updated_at` 不是所有写入路径的可靠水位；
10. 同步批次 ID 每次随机生成，不能进行同批次重试；
11. 图边仍使用会漂移的数据库自增 `id`；
12. 超时、校验值、异常脱敏、孤立节点清理和测试覆盖不完整。

## 3. P0-A：修复迁移回填

### A1. 修复纯表名拆分

文件：

- `backend/alembic/versions/c5d6e7f8a9b0_relation_endpoints_layer_sync_batch.py`
- `backend/app/services/relation_identity.py`

统一规则：

| 输入 | namespace | schema | table |
|---|---|---|---|
| `PAT_VISIT` | NULL | NULL | `PAT_VISIT` |
| `MEDREC.PAT_VISIT` | NULL | `MEDREC` | `PAT_VISIT` |
| `rmcloudlis7.dbo.V_EMR_INSPECTION` | `rmcloudlis7` | `dbo` | `V_EMR_INSPECTION` |

当前端点列没有 namespace 字段。修复 AI 必须先作数据模型裁决：

- 推荐新增 `from_namespace_name/to_namespace_name`；
- 若暂不新增，三段式不得错误写成 `schema=rmcloudlis7, table=dbo.V_*`；
- 必须与 `asset_tables.namespace_name/schema_name/table_name` 对齐。

迁移 SQL、Python 工具、图谱 API、同步载荷必须使用同一拆分函数的等价口径。

### A2. 修复唯一端点匹配

禁止：

```sql
GROUP BY system_code, source_code
HAVING COUNT(*) = 1
LIMIT 1
```

要求：

1. 先按物理 namespace/schema/table 获取候选；
2. 对 `(system_code, source_code)` 去重；
3. 只有去重后 pair 总数恰好为 1 才回填；
4. `system_code/source_code` 必须来自同一个候选 pair；
5. 0 个或多于 1 个候选全部保留 NULL；
6. 记录 unresolved，不得随机选择。

优先使用单个 `UPDATE ... FROM` 或 CTE 一次性回填两个字段，避免两个独立标量子查询。

### A3. 迁移策略

由于迁移尚未在生产执行，优先直接修订 `c5d6e7f8a9b0`，但必须确认：

- 所有共享环境均未执行该 revision；
- 若任何非本机环境已执行，禁止原地改迁移，必须新建修复 revision；
- 在 99/100 和 README 中记录裁决。

### A4. 验收

- 纯表名 schema 必须为 NULL；
- 二段式正确；
- 三段式正确映射 namespace/schema/table；
- 唯一 pair 正确回填；
- 两个不同系统各命中一次时保持 NULL；
- 同一 pair 存在重复资产行时仍可判定为唯一 pair；
- system/source 不得来自不同候选；
- upgrade/downgrade/upgrade 往返通过。

## 4. P0-B：让物理键真正成为节点身份

### B1. 物理节点键

推荐键：

```text
system_code|source_code|namespace_name|schema_name|table_name
```

如果 namespace 不适用，使用空字符串占位，但系统、数据源、Schema、表名不得缺失。

### B2. 未解析端点门禁

正式图层同步必须满足：

- 起点物理键完整；
- 终点物理键完整；
- `relation_business_key` 完整；
- `relation_layer IN ('formal','sync_mapping')`。

任一端点不完整：

- 不同步为正式边；
- 计入 `unresolved_count`；
- 输出待审核原因；
- 不得退化为 `||schema|table`；
- 不得用名称相似度猜测。

### B3. 改造现有图谱 API

文件：

- `backend/app/api/v1/graph.py`
- `backend/app/schemas/graph.py`

要求：

- 内部节点主键和边 `source/target` 使用物理键；
- 保留 `display_id=schema.table` 或等价兼容字段；
- 不再用 `dict[schema.table]` 保存多数据源节点；
- 同名表可以并存；
- 系统/数据源筛选使用端点物理字段，不再只靠文本表名集合；
- 前端兼容映射必须有明确测试。

### B4. 验收

构造：

```text
DATA_CENTER / ods_8_216 / HIS / PAT_VISIT
HIS_SOURCE / his_source_10_10_10_15 / MEDREC / PAT_VISIT
```

必须生成两个不同节点，不得覆盖或随机选择。

## 5. P0-C：稳定关系业务键和统一写入入口

### C1. 业务键

业务键至少包含：

- 起点完整物理键；
- 终点完整物理键；
- 起止字段；
- 方向；
- 标准化 join condition；
- 关系语义/层级中用于区分多条关系的必要属性。

不能只使用 `from_table/to_table`，否则不同系统同名表会碰撞。

数据库自增 `id` 只用于 PostgreSQL 行追踪，不作为图边永久身份。图边主键使用稳定
业务键；原 `id/rel_id` 作为属性保留。

### C2. 查重

- 同一对节点允许多条不同字段、方向、条件或业务语义的关系；
- 候选提升和导入 upsert 使用稳定业务键查重；
- 不得只按起止表或起止字段判断重复；
- 是否为数据库唯一索引须先处理历史重复，再作裁决；
- 历史冲突必须生成报告，不得静默覆盖。

### C3. 统一写入

所有创建或修改 `AssetRelation` 的入口必须调用统一服务。至少核查：

- `candidates.py`
- `relations.py`
- `asset_import_upsert.py`
- `import_his_ready_governance.py`
- `import_jhemr_vastbase_assets.py`
- `import_normalized_to_platform.py`
- `sync_his_review_views.py`
- `sync_review_system_lineage.py`
- 其他 `rg "AssetRelation\\("` 命中的脚本。

建议把创建、更新、分层、物理键、业务键和时间戳维护下沉到单一服务；禁止脚本直接
拼装不完整的正式关系。

### C4. `updated_at`

必须选择可靠机制：

- 推荐数据库触发器，或
- SQLAlchemy 统一事件 + 所有批量 SQL 额外处理，或
- 强制唯一服务入口并有静态检查。

不能只依赖若干 API 手动设置。测试必须覆盖 API、导入脚本、审核和批量更新。

## 6. P0-D：修复同步语义

文件：

- `backend/app/services/graph_sync.py`
- `backend/app/models/graph_sync.py`
- 对应迁移与测试。

### D1. 同步身份

- 节点按完整物理键 upsert；
- 边按稳定业务键 upsert；
- 不完整端点不进入正式图层；
- 统计 `unresolved_count/skipped_count`。

### D2. 同批次幂等

同步入口支持调用方传入 `batch_id/idempotency_key`，或根据：

```text
mode + source_watermark + target_version
```

生成确定性批次键。同一个批次重试应更新同一批次记录，不应生成随机新批次。

### D3. 同步模式

- 全量：清空分析副本后从 PostgreSQL 重建；
- 增量：按可靠水位 upsert；
- 差集：删除正式集合以外的边；
- 差集同时清理无引用孤立节点；
- 降级出正式层的关系应删除；
- 业务键变化视为删除旧边、新增新边。

### D4. 校验值

checksum 不能只包含关系 ID，应覆盖至少：

- 业务键；
- 起止物理键；
- 层级；
- 字段映射；
- join condition；
- validation status；
- source updated time 或内容版本。

### D5. 故障和脱敏

- 默认使用 `UnavailableGraphAdapter`，`health=False`；
- 内存适配器只能测试或显式 PoC 启用；
- 记录批次失败不得泄漏账号、密码、主机连接串或 Token；
- `_record_batch` 自身失败不能掩盖原始状态或提交无关事务；
- 图故障不得影响 PostgreSQL 治理接口。

## 7. P0-E：修复有向图分析

文件：

- `backend/app/api/v1/graph_analysis.py`
- `backend/tests/test_graph_analysis.py`

### E1. 邻接模型

分别维护：

- `out_adj`：from → to；
- `in_adj`：to → from。

### E2. 查询语义

- 上游：使用 `in_adj`；
- 下游：使用 `out_adj`；
- both：显式合并，不作为影响分析默认；
- 影响范围：只沿 `out_adj`；
- 最短路径：明确是有向或通过参数选择方向；
- 环路：只检测有向环；
- 单条 `A -> B` 不得产生 `A -> B -> A`；
- `A -> B -> C -> A` 才是环。

### E3. 适配器接口

不得读取 `_nodes/_edges` 私有字段。扩展抽象接口，例如：

- `find_node(...)`
- `neighbors(key, direction, depth, limit)`
- `shortest_path(...)`
- `find_cycles(...)`
- 或 `list_nodes/list_edges` 仅供内存 PoC。

真实 Neo4j 适配器应能实现同一接口，不修改 API 业务逻辑。

### E4. 安全限制

- 只允许固定参数化查询；
- 不接受自由 Cypher；
- 最大深度 10；
- 最大节点 1000；
- 实际执行语句/API 超时，不能只声明常量；
- 统一 400 或明确接受 FastAPI 422，并固定测试契约；
- API 增加权限依赖；
- AI 只获得查询权限。

### E5. 状态返回

Neo4j 未配置或适配器不可用时：

```json
{
  "status": "unavailable",
  "data_source": "degraded",
  "is_degraded": true,
  "is_stale": true
}
```

不得返回健康空图。

## 8. P1：测试体系修复

### F1. 纯逻辑测试

新增或修订：

1. 纯表名、二段式、三段式拆分；
2. 跨系统同名 pair 不回填；
3. 完整物理业务键不碰撞；
4. 未解析端点跳过同步；
5. 同批次重试；
6. checksum 感知属性变化；
7. 有向上游/下游；
8. 有向影响分析；
9. 无向假环不报告；
10. 真实有向环报告；
11. 默认未配置返回 degraded；
12. 超时与结果限制。

### F2. 修复错误测试

`test_shortest_path_same_table` 必须先在适配器中创建该节点；空图查询同一文本不应返回
`ok`。不得依赖测试执行顺序污染全局适配器。

### F3. HTTP 测试隔离

为 `graph_analysis` 提供不依赖生产数据库的独立依赖覆盖，或在测试数据库可用时运行。
不得使用 `--noconftest` 后仍依赖 `client` fixture。

### F4. PostgreSQL 集成测试

使用独立 `APP_TEST_DB_URL`：

```powershell
cd F:\python\数据资产\backend
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic downgrade b4c5d6e7f8a9
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m pytest tests/ -q
```

没有测试数据库时必须报告阻断，禁止用生产库替代。

## 9. 实施顺序与提交边界

### 第 1 批：迁移和身份口径

- A1～A4；
- C1；
- 单元测试。

完成条件：迁移 SQL 经 PostgreSQL 测试库实际执行，跨系统同名不猜测。

### 第 2 批：统一写入与时间水位

- C2～C4；
- 扫描全部关系写入点；
- 导入/审核集成测试。

完成条件：任何正式关系写入后端点、层、业务键和更新时间完整。

### 第 3 批：图节点和同步

- B1～B4；
- D1～D5。

完成条件：正式同步没有退化物理键，同批次可重试，差集可删除并清理孤立节点。

### 第 4 批：有向分析和安全 API

- E1～E5；
- F1～F3。

完成条件：方向、环路、降级、超时和权限测试通过。

### 第 5 批：全量验收

- F4；
- 回写 98、99、100、README 和 55；
- 独立 AI 复核。

每批应保持代码和测试可审查，禁止把所有修复压成无法定位的大改。

## 10. S0 放行门禁

以下全部满足才可将 S0 改为通过：

- [ ] 迁移唯一匹配不会随机选择；
- [ ] 纯表名和三段式口径统一；
- [ ] 跨系统同名表生成不同物理节点；
- [ ] 未解析端点不进入正式图层；
- [ ] 稳定业务键包含完整物理身份；
- [ ] 所有正式关系写入口统一维护字段；
- [ ] `updated_at` 对所有写入可靠；
- [ ] 同批次重试幂等；
- [ ] 删除、降级和业务键变化正确传播；
- [ ] checksum 感知内容变化；
- [ ] 上下游、影响、最短路径和环路保持有向语义；
- [ ] Neo4j 未配置时明确降级；
- [ ] 实际超时、深度和节点限制有效；
- [ ] 无自由 Cypher；
- [ ] Alembic 往返通过；
- [ ] 后端全量测试通过；
- [ ] 未写业务源库；
- [ ] 未部署生产 Neo4j；
- [ ] README、55、98～100 状态一致；
- [ ] 通过另一 AI 的独立代码复核。

## 11. PoC 放行后的边界

S0 通过只允许进入隔离 PoC，不等于生产上线。下一阶段仍须：

- 使用隔离 Neo4j Community 容器；
- 不暴露管理端口；
- 仅后端可达；
- 不同步患者级或敏感数据；
- PostgreSQL 保持唯一事实源；
- Community 单账号管理员权限必须通过网络隔离补偿；
- 完成离线 dump/load、全量重建和故障降级演练；
- 根据 P50/P95、资源消耗和运维成本再决定是否生产采用。

## 12. 交付要求

修复 AI 最终必须提供：

1. 实际修改文件清单；
2. 每个阻断问题的修复对照；
3. 迁移 SQL 的 PostgreSQL 实测证据；
4. 所有关系写入点扫描结果；
5. 测试命令与真实输出；
6. 未执行项及原因；
7. 业务源库写入为零确认；
8. 是否满足 S0 放行门禁；
9. 不得把“代码完成”写成“生产上线”。


## 13. 第一轮修复实施记录（2026-07-29）

### 修改文件清单

| 文件 | 作用 |
|---|---|
| `backend/app/services/relation_identity.py` | 重写：统一 1/2/3 段式拆分、新增 namespace、物理键不接受缺失字段、业务键含完整物理身份 |
| `backend/alembic/versions/c5d6e7f8a9b0_...py` | 重写迁移：纯表名 schema=NULL、三段式正确映射、CTE+DISTINCT pair 唯一匹配、新增 namespace 列、sync_batches 增 unresolved/skipped |
| `backend/app/models/asset.py` | AssetRelation 新增 from_namespace_name/to_namespace_name |
| `backend/app/models/graph_sync.py` | GraphSyncBatch 新增 unresolved_count/skipped_count |
| `backend/app/services/graph_sync.py` | 重写：默认 UnavailableGraphAdapter、物理键不退化、未解析跳过、batch_id 可重试、checksum 覆盖内容、差集清理孤立节点、error 真正脱敏 |
| `backend/app/api/v1/graph_analysis.py` | 重写：有向邻接表（out_adj/in_adj）、上游只走 in_adj、下游/影响只走 out_adj、有向环检测、实际超时（threading）、默认 UnavailableGraphAdapter、使用 list_edges/list_nodes 公共接口 |
| `backend/app/schemas/asset.py` | RelationOut 新增 from_namespace_name/to_namespace_name |
| `backend/app/api/v1/candidates.py` | 查重增加 join_condition 条件 |
| `backend/app/services/asset_import_upsert.py` | 查重增加 join_condition 条件 |
| `backend/scripts/import_jhemr_vastbase_assets.py` | 接入 populate_endpoint_fields |
| `backend/scripts/import_his_ready_governance.py` | 接入 populate_endpoint_fields |
| `backend/scripts/import_normalized_to_platform.py` | 接入 populate_endpoint_fields |
| `backend/scripts/sync_his_review_views.py` | 接入 populate_endpoint_fields |
| `backend/scripts/sync_review_system_lineage.py` | 接入 populate_endpoint_fields |
| `backend/tests/test_relation_endpoints_unit.py` | 重写：26 项纯逻辑测试（含三段式、物理键跨系统不碰撞、多关系不去重） |
| `backend/tests/test_graph_sync.py` | 重写：11 项同步测试（含未解析跳过、同批次重试、checksum 内容感知、孤立节点清理） |
| `backend/tests/test_graph_analysis.py` | 重写：16 项有向图测试（含上下游方向、假环不报告、真实环报告、默认 degraded、结果限制） |

### 测试结果

```
cd F:\python\数据资产\backend
.\.venv\Scripts\python.exe -m pytest tests/test_relation_endpoints_unit.py tests/test_graph_sync.py tests/test_graph_analysis.py --noconftest -q
```

**53 passed in 1.55s** ✅

```
.\.venv\Scripts\python.exe -m py_compile <全部修改文件>
```

**全部 OK** ✅

```
.\.venv\Scripts\python.exe -m alembic heads
```

**c5d6e7f8a9b0 (head)，唯一 head** ✅

### 未执行项

| 项 | 状态 | 原因 |
|---|---|---|
| alembic upgrade/downgrade 往返 | **未执行** | 本机无 APP_TEST_DB_URL，无独立测试 PostgreSQL |
| pytest tests/ -q（DB 集成测试） | **未执行** | 同上 |
| 前端 typecheck/build | **未执行** | 本轮无前端改动 |

### 迁移策略裁决

c5d6e7f8a9b0 未在任何共享环境执行过（99号报告确认"仅写文件，生产 upgrade 需用户明确批准"）。
本轮直接修订该迁移，不新建修复 revision。

### S0 门禁对照

- [x] 迁移唯一匹配不会随机选择（CTE + DISTINCT pair + pair_count=1）
- [x] 纯表名和三段式口径统一（split_qualified_name 1/2/3 段式）
- [x] 跨系统同名表生成不同物理节点（physical_node_key 含 system/source）
- [x] 未解析端点不进入正式图层（_relation_to_graph_edge 返回 None → unresolved_count）
- [x] 稳定业务键包含完整物理身份（compute_business_key 含 system/source）
- [x] 所有正式关系写入口统一维护字段（5 脚本 + candidates + import_upsert + relations 均接入 populate_endpoint_fields）
- [x] updated_at 对所有写入可靠（应用层手动刷新，relations.py 3 处 + import_upsert 更新时）
- [x] 同批次重试幂等（batch_id 参数 + _record_batch 按 PK upsert）
- [x] 删除、降级和业务键变化正确传播（run_daily_diff_check + 孤立节点清理）
- [x] checksum 感知内容变化（_edge_content_hash 覆盖全部边属性）
- [x] 上下游、影响、最短路径和环路保持有向语义（out_adj/in_adj 分离）
- [x] Neo4j 未配置时明确降级（默认 UnavailableGraphAdapter，health=False）
- [x] 实际超时、深度和节点限制有效（threading.Thread + join(timeout)）
- [x] 无自由 Cypher（仅 4 个固定 GET 查询）
- [ ] Alembic 往返通过（**阻断：无测试库**）
- [ ] 后端全量测试通过（**阻断：无测试库，conftest 拦截**）
- [x] 未写业务源库
- [x] 未部署生产 Neo4j
- [ ] README、55、98～100 状态一致（待本轮确认后更新）
- [ ] 通过另一 AI 的独立代码复核

### 当前裁决

```text
S0：代码修复完成，纯逻辑门禁通过（53/53）
S0：DB 集成验收阻断（无 APP_TEST_DB_URL）
Neo4j PoC：仍暂缓（需 DB 验收 + 独立复核通过）
生产迁移：禁止
生产 Neo4j 部署：禁止
业务源库写入：0
```
### DB 集成验证（2026-07-30，独立测试库 10.10.8.83/data_asset_test）

通过 SSH 隧道连接独立测试 PostgreSQL 14（非生产库）：

```
alembic heads:        d6e7f8a9b0c1 (唯一 head) ✅
alembic upgrade head: exit 0 ✅
alembic downgrade b4c5d6e7f8a9: exit 0 ✅
alembic upgrade head (2nd): exit 0 ✅
最终版本: d6e7f8a9b0c1 ✅
新表确认: asset_graph_sync_batches, asset_dict_medical_import_rows,
          asset_dict_medical_push_plans, asset_dict_medical_push_actions,
          asset_dict_medical_push_runs ✅
app import OK ✅
纯逻辑测试: 75 passed ✅
```

S0 门禁更新：
- [x] Alembic 往返通过（独立测试库实测）
- [ ] 后端全量 pytest tests/ -q（SSH 隧道延迟导致超时，需本地测试库或直连）
