> 类别：模块执行计划
>
> 状态：部分完成（已部署；浏览器角色矩阵待完成） | 优先级：P0 | 创建日期：2026-07-14 | 部署日期：2026-07-14
>
> 执行入口：用户已要求按本计划开发。**仍禁止**：生产归一 apply、开启运维写开关、业务源库 DML。HRP 包导入生产前须备份 + dry-run。

# HRP 资产、连接归一与运维闭环整改执行计划

## 0. 本次目标

一次解决以下四类问题：

1. HRP 在“表资产”和“业务系统与数据资源”中为空。
2. 已配置连接不能完整显示、编辑和测试，同一物理数据库被拆成多个伪系统。
3. 运维 SQL 没有明确的目标数据库选择。
4. UPDATE、字典同步和运维任务缺少可追踪日志；管理员场景下模板审批流程冗余，且审批后的任务不可见。

最终统一产品口径为：

```text
数据库端点（IP:端口）
  └─ 数据库/Service/SID
      └─ Schema/Owner
          └─ 表/视图
              └─ 字段
```

“业务系统名称”只作为端点/数据库的业务标签，不再决定资源树物理层级。同一 `IP + 端口 + Service/SID/Database` 只能出现一次；LIS、PACS、EMR、移动护理、手麻是 `10.10.8.216:1521/orcl` 内的 Owner/业务域标签，不再作为独立系统或独立数据库连接。

## 1. 生产现状与根因（2026-07-14 只读核查）

### 1.1 HRP 为空

生产平台统计：

| 项目 | 当前值 |
|---|---:|
| `asset_tables` 中 HRP 表 | 0 |
| `asset_columns` 中 HRP 字段 | 0 |
| HRP 数据源记录 | 1 |
| HRP 数据源 enabled | false |
| HRP `target_host` | 空 |
| 遗留 `host_masked` | 已保存地址，但没有迁入新字段 |

根因不是前端过滤，而是 HRP 机器可读资产包未导入平台 `asset_tables/asset_columns`，且 HRP 数据源处于禁用状态。`开发起步包/数据资产_HRP源端资产包/` 已有离线成果，应优先导入该资产包；只有资产包与活库差异明显时才做只读增量采集。

### 1.2 连接重复

当前 8 条生产连接中，以下 6 条实际指向同一物理数据库：

```text
10.10.8.216:1521/orcl
  ods_8_216
  ods_lis
  ods_pacs
  ods_emr
  ods_ydhl
  ods_sm
```

它们被分别绑定到 DATA_CENTER、LIS、PACS、EMR、MOBILE_NURSING、SM，导致系统总览和连接列表重复。正确模型应为一个数据库端点/连接，Owner 归属分别保留 ODS、LIS、PACS、JHEMR/MTL、YDHL、SM 等。

另外 HIS、HRP 均已有遗留地址，但 8 条连接的 `target_host` 全为空，因此 75 号按真实地址归并无法 apply，连接测试也不能可靠使用新模型。

### 1.3 运维现状

- SQL 工作台当前 `target_scope` 固定为 `platform_asset`，页面没有数据库目标选择。
- 业务源库按安全红线只能 SELECT，不能成为 INSERT/UPDATE 执行目标。
- 生产已有 1 个运维模板、0 个执行任务。
- 审计只有模板 `create_or_update_draft` 和 `submit`，没有完整 UPDATE 执行历史。
- 字典导入有独立 import run，但没有在统一运维日志页面聚合展示。
- SQL 工作台创建、提交、审批、创建 run、审批 run 分散，批准后没有可靠刷新/跳转到“运维任务”。

## 2. 不可变安全边界

1. HIS、HRP、ODS、LIS、PACS、EMR、YDHL、SM 等业务源库始终只读，仅允许 SELECT/连接测试/元数据采集。
2. 自定义 INSERT/UPDATE 第一阶段仅允许平台 PostgreSQL `data_asset.asset` schema。
3. 数据库目标选择器可以展示业务源连接，但对写操作必须禁用，并标注“只读源库”。
4. AI 不调用 `asset_action_executors` 执行写入。
5. 密码只写不回显；API、日志、审计、Git 均不得出现明文密码或完整凭据引用。
6. 连接测试只执行最小健康 SQL：Oracle `SELECT 1 FROM DUAL`，其余数据库 `SELECT 1`；必须设置连接和语句超时。
7. HRP 采集仅元数据，禁止读取大表业务明细。
8. 系统/连接归一必须先 dry-run、备份、冲突为 0，再 apply。
9. 暂时屏蔽审批只改变管理员界面流程，不删除服务端审计、状态机和兼容 API。
10. 运维正式执行仍要求：管理员权限、模板已发布、影响行预览、二次确认、白名单、行数上限、三重写开关和事务审计。

## 3. 统一数据模型

### 3.1 三个概念分离

| 概念 | 唯一键 | 用途 |
|---|---|---|
| 数据库端点 | `db_type + normalized_host + port` | 网络地址，例如 `10.10.8.216:1521` |
| 数据库实例 | `endpoint_id + service_mode + service_name/database_name` | Oracle Service/SID 或其他数据库 database |
| Owner/Schema | `instance_id + normalized_schema` | ODS、LIS、PACS、YDHL、SM 等真实资源边界 |

业务系统只维护 `business_labels`：HIS、HRP、数据中心、检验、影像、移动护理等。它可以多对一关联数据库实例或 Owner，但不得制造重复物理连接。

### 3.2 平台表设计

优先复用 `asset_data_sources`，新增/明确字段：

- `endpoint_key`：标准化 `db_type://host:port`。
- `database_key`：`endpoint_key/service_mode/service_or_database`。
- `canonical_source_id`：重复历史连接指向主连接。
- `source_kind`：`physical_connection` / `legacy_alias`。
- `business_labels`：JSON 数组，仅显示标签。
- `last_test_status`、`last_test_at`、`last_test_latency_ms`、`last_test_error_code`、`last_test_error_masked`。
- `last_collect_status`、`last_collect_at`、`last_collect_snapshot_id`。
- `credential_username_masked`、`credential_status`、`credential_updated_at`。

新增平台表（如现有结构无法表达）：

- `asset_asset_source_schemas`：连接与 Schema/Owner 清单，包含业务标签、表数、字段数、最近采集时间。
- `asset_ops_event_logs`：统一运维事件流；若可完全用 `asset_govern_audit_logs` 表达，则不重复建表，只增加规范化事件 DTO/查询视图。

所有迁移手写 upgrade/downgrade，创建前先运行 `alembic heads`，不得假设下一 revision。

### 3.3 历史连接归一映射

```text
主连接：ods_8_216 → 10.10.8.216:1521/orcl
别名：ods_lis  ┐
      ods_pacs │
      ods_emr  ├→ canonical_source_id = ods_8_216
      ods_ydhl │
      ods_sm   ┘
```

第一批不物理删除别名：标记为 `legacy_alias/inactive`，把其 Schema、表、字段、关系引用归到主连接；兼容旧 source_code 查询。确认无调用后再归档别名。

HIS 与 HRP 保留各自独立实例：

- HIS：按真实地址、端口、Service/SID 展示。
- HRP：按真实地址、端口、Service/SID 展示。
- 数据中心：`10.10.8.216:1521/orcl` 只显示一次。

## 4. HRP 资产补齐

### 4.1 导入前核对

1. 读取 `数据资产_HRP源端资产包/` 的 manifest/catalog/tables/columns。
2. 核对 source_code、system_code、Owner、表数、字段数、生成时间和文件 SHA-256。
3. 与平台现有 HRP 计数（当前 0/0）比较。
4. 对 HRP 连接做只读测试；没有有效凭据时允许先导入离线资产包，但必须标记 `metadata_origin=offline_package`。
5. 输出 dry-run：新增、更新、冲突、重复、无 Owner、无字段表、预计写入数。

### 4.2 幂等导入

扩展现有归一资产导入脚本，不另写不可复用的一次性 SQL：

- 默认 dry-run，`--apply` 必须带确认串和批次号。
- 以 `source_code + owner + table_name`、再以字段名作为稳定键。
- 单事务 upsert；失败全部回滚。
- 只影响 HRP source scope，不覆盖 HIS/数据中心资产。
- 导入后重算 Schema/表/字段统计。
- 记录包 hash、批次、操作者、开始/完成时间、增删改数量。

### 4.3 HRP 验收

- 表资产按 HRP 数据库 → Owner → 表可查询。
- 业务系统与数据资源中 HRP 表数/字段数与包 manifest 一致。
- 搜索、分页、懒加载正常。
- 随机抽取至少 20 张表，对照资产包字段数量。
- 若活库可连，再抽取 `ALL_TABLES/ALL_TAB_COLUMNS` 只读对账；不查业务数据。

## 5. 连接维护与测试

### 5.1 连接表单

统一系统页提供：

- 数据库类型：Oracle、MySQL、SQL Server、Vastbase、PostgreSQL。
- IP/主机名、端口。
- Oracle Service/SID 模式及名称；其他数据库 database name。
- 用户名、密码（密码只写；编辑时显示“已配置/未配置”）。
- 默认 Schema/Owner、连接标签、启用状态。
- “保存并测试”“仅测试”“保存”“轮换凭据”“删除凭据”。

输入地址后允许先测试再保存；测试请求使用专用 DTO，可携带一次性密码，但不得落库、写日志或出现在异常详情中。已保存连接测试默认读取 credential store。

### 5.2 API

- `POST /api/v1/connections/test-draft`：测试尚未保存的表单。
- `POST /api/v1/connections/{id}/test`：测试已保存连接。
- `GET /api/v1/connections`：按物理 database_key 去重列表。
- `GET /api/v1/connections/{id}`：脱敏详情、Schema 统计和最近测试。
- `PATCH /api/v1/connections/{id}`：修改非凭据字段。
- `PUT /api/v1/connections/{id}/credential`：写入/轮换凭据。
- `POST /api/v1/connections/{id}/collect-metadata`：只读采集。

连接测试响应只包含：success、db_type、脱敏 endpoint、database/service、server_version、latency_ms、error_code、脱敏错误摘要、tested_at。

### 5.3 遗留连接回填

编写 `backfill_connection_targets.py`：

1. 从现有受控连接登记/凭据文件读取真实地址，不从页面展示字符串猜密码。
2. 将已确认地址回填 `target_host`；`host_masked` 重新生成真正脱敏值。
3. ODS/数据中心、HIS、HRP 分别测试。
4. 无凭据或测试失败的连接保留并显示失败原因，不伪造成功。
5. dry-run 输出回填、重复端点、缺失凭据和冲突。

## 6. 三个页面统一展示口径

### 6.1 系统总览

首页卡片按“物理数据库实例”统计，不按历史 source_code 计数：

```text
10.10.8.216:1521 / orcl（数据中心）
  Owner 32 · 表 865 · 字段 26894
```

LIS/PACS/EMR/YDHL/SM 作为标签或 Owner 摘要显示，不能独占系统卡片。

### 6.2 数据库连接

连接列表一行一个 database_key。内容过多时默认只显示：

- 数据库类型图标。
- `IP:端口`。
- Service/SID/Database。
- 连接状态、凭据状态、最后测试时间。
- Owner/Schema 数量、表数量。

展开或详情抽屉再显示 Schema、业务标签、历史别名和采集记录。

### 6.3 资源树与表资产

所有入口复用同一个后端树 DTO 和同一个前端 Tree 组件：

```text
endpoint → database → schema → table/view → column
```

稳定节点 ID：

```text
endpoint:{endpoint_key}
database:{database_key}
schema:{database_key}:{schema}
table:{database_key}:{schema}:{table}
column:{database_key}:{schema}:{table}:{column}
```

禁止用表名或显示名称作为唯一 ID。节点数大时采用逐层懒加载，搜索接口返回祖先路径；不允许前端一次加载 13 万字典或全部字段。

## 7. 运维数据库目标选择

### 7.1 目标选择器设计

SQL 工作台第一项必须是“目标数据库”：

- `平台库 / data_asset / asset`：可选，支持受控 INSERT/UPDATE。
- HIS、HRP、数据中心等业务源连接：可见但标记“只读”，只允许诊断 SELECT/连接测试，不允许创建写模板。
- 目标选择后自动显示数据库类型、脱敏地址、数据库名、允许操作和写开关状态。

模板保存 `target_connection_id + target_database_key + target_schema` 的不可变快照；执行时再次验证目标仍为平台库，禁止通过修改请求把模板重定向到源库。

### 7.2 管理员简化流程

按用户本次决定，暂时屏蔽模板和 run 的人工审批 UI：

```text
管理员创建/修改模板
  → 服务端校验并发布（记录 publish 审计）
  → 创建运维任务
  → dry-run 影响行预览
  → 二次确认
  → 执行或失败
  → 日志/审计
```

具体规则：

- 仅 `ops:sql:admin` 可创建和发布写模板。
- 后端保留 submit/approve/reject API 和状态字段，默认配置 `APP_OPS_APPROVAL_UI_ENABLED=false` 时前端不展示。
- 管理员保存通过安全校验的模板后状态直接为 `approved/published`，审计 action=`admin_publish`。
- run 创建后直接进入 `ready_for_preview`，不再要求 run 审批。
- 仍禁止创建后直接执行；必须成功 preview，二次确认令牌短时有效且绑定 run/version/参数 hash。
- 若未来多人运维，把配置改回 true 即恢复原审批流程，无需迁移数据。

### 7.3 运维任务可见性

SQL 工作台创建 run 后必须：

- 自动跳转或提供“查看任务 #ID”。
- “运维任务”列表能查询 SQL 工作台产生的所有 run。
- 默认排序 created_at desc，不因旧 `approval_status` 过滤掉 ready/succeeded/failed。
- 支持按目标数据库、模板、操作类型、状态、操作者、时间筛选。
- 任务详情显示模板版本、SQL hash、脱敏参数、预览行数、实际影响行数和事件时间线。

## 8. UPDATE 与字典同步日志闭环

### 8.1 统一事件模型

规范事件类型：

- 连接：create/update/credential_rotate/test_success/test_failed/metadata_collect。
- SQL 模板：admin_publish/update/disable。
- SQL run：create/preview/confirm/execute_success/execute_failed/rejected/rollback。
- 字典：dry_run/import_start/import_success/import_failed/no_change/sync_collect/sync_diff/sync_apply。

每条事件至少包含：event_id、module、entity_type/ref、target_connection_id、target_database_key、operator、action、status、started_at/finished_at、duration_ms、affected_count、before/after hash、batch_code、error_code、脱敏摘要、correlation_id。

严禁日志保存：密码、Token、完整 DSN、身份证/姓名/电话、未脱敏 SQL 参数。SQL 只保存模板 hash、规范化摘要和目标表。

### 8.2 页面

运维中心增加“执行日志”与“字典同步日志”两个 Tab：

- 执行日志：UPDATE/INSERT、状态、影响行数、目标数据库、执行人、时间、失败原因。
- 字典同步日志：文件/源系统、批次、dry-run/apply、8 个体系及项目/映射数量、差异、失败原因。
- 支持任务详情时间线、按 correlation_id 追踪、CSV 脱敏导出。
- 字典页面提供“查看本批次日志”链接。

### 8.3 API

- `GET /api/v1/ops/events`。
- `GET /api/v1/ops/events/{event_id}`。
- `GET /api/v1/ops/sql/runs` 和 `GET /api/v1/ops/sql/runs/{id}`。
- `GET /api/v1/dict-medical/import-runs`。
- `GET /api/v1/dict-medical/import-runs/{id}`。
- `GET /api/v1/dict-medical/sync-logs`。

列表必须分页，不读取或返回敏感原始参数。

## 9. 逐文件实施清单

### 9.1 后端

- `backend/app/models/asset_system.py`：端点/数据库唯一键、别名、测试与采集状态。
- `backend/app/models/ops_tool.py`：目标连接快照、简化状态、预览确认 hash、事件关联。
- `backend/app/models/dict_medical.py`：核对 import run 字段，补 correlation/status/duration。
- `backend/app/api/v1/systems.py`：物理连接去重、统一树、连接测试、回填接口。
- `backend/app/api/v1/assets.py` 或现有资产 API：表资产复用统一层级/筛选。
- `backend/app/api/v1/ops_tools.py`：目标数据库选择、管理员发布、任务列表/详情、审批 UI 开关。
- `backend/app/api/v1/dict_medical.py`：导入/同步日志查询。
- `backend/app/services/connection_identity.py`：endpoint_key/database_key 标准化。
- `backend/app/services/credential_store.py`：一次性 draft 测试与已保存凭据读取。
- `backend/app/services/ops_executor.py`：执行前强制平台目标、事件日志、确认 hash。
- `backend/scripts/backfill_connection_targets.py`：遗留地址回填，默认 dry-run。
- `backend/scripts/normalize_business_systems.py`：按 database_key 归一连接和引用。
- 复用/扩展现有资产导入脚本完成 HRP 幂等导入。
- 新增实际 head 之后的手写 Alembic migration。

### 9.2 前端

- `frontend/src/api/asset.ts`：统一连接、测试、资源树 DTO。
- `frontend/src/api/ops.ts`：目标连接、SQL run 列表/详情、事件与字典日志。
- `frontend/src/views/asset/systems/index.vue`：端点/数据库/Schema 三层展示和连接测试。
- 表资产页面：数据库层级筛选和 HRP 数据展示。
- `frontend/src/views/ops/sql-workbench/index.vue`：目标数据库选择、管理员简化流程、任务跳转。
- `frontend/src/views/ops/runs/index.vue`：兼容 SQL run、状态筛选和详情时间线。
- `frontend/src/views/ops/audit/index.vue`：执行日志与字典同步日志 Tab。
- 抽取 `DatabaseResourceTree.vue`，系统页和表资产共用。

## 10. 严格实施顺序

### S0：基线与备份

- 目录自检、git diff、生产只读统计。
- 输出 HRP 包 manifest、连接映射、重复 database_key、孤儿引用。
- 建立测试库和平台库备份；生产写开关保持关闭。

### S1：模型与迁移

- 手写迁移、upgrade/downgrade。
- 建索引和唯一约束前先清理重复；迁移不得自动删除旧连接。

### S2：连接回填与测试

- 实现 draft/持久连接测试。
- 遗留 target_host dry-run → 测试库 apply → 三类连接实测。

### S3：HRP 资产

- 包核验 → dry-run → 测试库导入 → 计数/抽样 → 生产备份后导入。

### S4：连接归一与统一树

- 归一 dry-run → 冲突/孤儿为 0 → 测试库 apply。
- 重构系统总览、数据库连接、资源树、表资产。

### S5：运维目标与简化流程

- 目标数据库选择、平台库强制校验、管理员发布、preview/二确、任务可见。

### S6：日志闭环

- UPDATE/INSERT、连接测试、元数据采集、字典导入/同步统一事件和页面。

### S7：验收与发布

- 全量测试、浏览器角色验收、生产备份、迁移、HRP 导入、归一 apply（需明确确认）、发布和哈希对账。

## 11. 必测用例

### 连接与资源

- 五种数据库 draft 测试 DTO 校验和默认端口。
- 错误地址、错误端口、错误 Service、错误凭据、超时的脱敏错误。
- 密码不进入响应/日志/数据库/Git。
- 同一 `10.10.8.216:1521/orcl` 只能返回一个数据库节点。
- LIS/PACS/EMR/YDHL/SM 出现在 Owner/标签层，不是一级系统。
- endpoint/database/schema/table/column 稳定 ID、懒加载和搜索祖先路径。
- 旧 source_code 兼容查询。

### HRP

- dry-run 零写、重复导入幂等、异常单事务回滚。
- 表/字段总数与 HRP 包一致。
- HRP 表资产分页、搜索、Owner 筛选。
- 活库元数据抽样只读，不读取业务明细。

### 运维

- 未选择目标数据库不能验证/保存模板。
- 业务源库目标的 INSERT/UPDATE 必须 403。
- 篡改 target_connection_id/database_key/schema 必须拒绝。
- 管理员模式模板直接发布并写 `admin_publish` 审计。
- 审批 UI 关闭时 submit/approve 按钮不显示，但兼容 API 和历史数据可读。
- 创建 run 后运维任务立即可见。
- 未 preview、确认过期、参数变更、影响行超限、开关关闭均拒绝执行。
- 并发双击只有一次成功。
- UPDATE 成功/失败均有完整事件，失败事务回滚。
- 字典 dry-run/import/sync/no_change/failed 均可查询日志。

## 12. 验收命令

```powershell
cd F:\python\数据资产\backend
.\.venv\Scripts\python.exe -m alembic heads
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m pytest tests/ -q

cd F:\python\数据资产\frontend
pnpm run typecheck
pnpm run test
pnpm run build
```

生产验收必须额外记录：平台备份及 SHA-256、迁移 head、HRP 导入批次和数量、连接测试结果、归一 dry-run/apply 状态、镜像 ID、首页/API、运维写开关、本地/服务器哈希。

## 13. 完成判定

- HRP 在表资产和统一资源树中有正确表/字段，数量可追溯。
- ODS/HIS/HRP 已配置连接可查看、维护和测试，凭据永不回显。
- `10.10.8.216:1521/orcl` 在三个入口均只显示一次。
- 所有入口统一为 IP:端口 → 库/Service → Schema → 表 → 字段。
- 运维 SQL 必须选择目标数据库；业务源库不能执行写 SQL。
- 管理员审批 UI 已按配置屏蔽，run 创建后在运维任务可见。
- UPDATE/INSERT 与字典同步成功、失败、no_change 均有脱敏日志和详情时间线。
- 全量测试和浏览器验收通过，业务源库写操作为 0。

## 14. 复核后仍需明确授权的生产动作

用户复核本计划代表允许开发和测试，但以下动作仍分别留门禁：

1. 正式执行历史连接归一 apply。
2. 开启 `APP_OPS_WRITE_ENABLED` 等生产写开关。
3. 在平台生产库执行真实 UPDATE/INSERT 验收样例。

HRP 资产包导入属于本次明确缺陷修复，但生产执行前仍必须先备份并完成 dry-run；任何业务源库 DML/DDL 均不在授权范围。

## 15. 执行日志

### [S0–S6] 2026-07-14 代码落地

- **迁移**：`y1f2a3b4c5d6`（revises `x0e1f2a3b4c5`）
  - `asset_data_sources`：endpoint_key/database_key/canonical_source_code/source_kind/business_labels/测试与采集状态
  - `asset_source_schemas` 新表
  - ops 模板/run 目标快照 + correlation/confirm 字段
  - `asset_ops_event_logs` 统一事件流
  - 字典 import run 补 correlation/duration
- **HRP 导入**：`scripts/import_hrp_assets.py`
  - 默认 scope=`keep`（67 张 KEEP 表）；支持 `core`/`ods_mirror`
  - dry-run 实测：keep=67，columns_loaded=841，平台 existing HRP 表/字段=0，writes=0
  - 确认串：`IMPORT-HRP-ASSETS`
- **连接回填**：`scripts/backfill_connection_targets.py`（`BACKFILL-CONNECTION-TARGETS`）
  - 已知 ODS/HIS/HRP 地址映射；ODS 别名 → `ods_8_216`
  - 当前本机 `APP_DB_URL` 库尚未 upgrade（缺 `target_host` 等列），脚本 dry-run 需迁移后执行
- **连接 API**：`/connections` 去重列表、`test-draft`、`/{id}/test`、`/connections-targets`
- **运维**：目标库选择（业务源只读 403）、`APP_OPS_APPROVAL_UI_ENABLED=false` 管理员直接发布、run `ready_for_preview` → preview → 二确执行、任务列表/详情、`/ops/events`
- **字典日志 API**：`/dict-medical/import-runs`、`/sync-logs`
- **前端**：系统连接物理去重+draft 测试；SQL 工作台目标库；运维审计三 Tab；任务状态含 ready_for_preview
- **测试**：后端单元 24+ 通过；前端 typecheck + Vitest 39 passed
- **业务源库写操作**：0
- **未做/门禁**：
  1. 测试库/生产 `alembic upgrade` 至 `y1f2a3b4c5d6`
  2. HRP apply 生产导入（须备份）
  3. backfill + 连接归一 apply
  4. 运维写开关
  5. 浏览器角色矩阵

## 16. 生产执行记录（2026-07-14）

- 平台备份：`data_asset_pre_plan76_20260714183720.dump`，SHA-256 `0fe841189972a5f7293c08108aec90aa4f417365f9669464bad5c812b62179e6`。
- 测试库及生产均升级至 `y1f2a3b4c5d6`；服务器专项测试13项通过。
- 已发布镜像 `data-asset:20260714-plan76`，目录 `/opt/data-asset/releases/plan76-20260714183755`。
- HRP keep范围dry-run为67表/841字段/零写，生产apply成功；平台现为67表、841字段、1个Owner。
- 连接回填首次因历史别名共用旧唯一身份键被回滚；改为alias专用行身份键后apply成功。现为3物理连接、5个legacy_alias、3个database_key、target_host缺失0。
- `ods_lis/ods_pacs/ods_emr/ods_ydhl/ods_sm`共享`10.10.8.216:1521/orcl`并指向`ods_8_216`。
- 宿主机`/opt/oracle`空挂载曾遮住镜像客户端，已从部署前镜像恢复Instant Client并保持ro挂载。恢复后数据中心连接126.37ms成功，HIS连接18.27ms成功。
- HRP地址回填后由用户提供凭据，经受控凭据文件写入并绑定；平台仅保存脱敏用户名和configured状态。`10.10.10.23:1521/hrpdb`只读连接测试成功，约124ms。
- 首页200、API数据库connected；运维写开关false、审批UI false、系统归一未apply、业务源库写操作0。
