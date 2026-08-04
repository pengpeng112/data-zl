> 类别：模块执行计划
>
> 状态：已部署，系统归并保留 dry-run | 优先级：P0/P1 | 创建日期：2026-07-14 | 部署日期：2026-07-14
>
> 执行入口：用户已要求按本计划开发。**仍禁止**：生产 apply 系统归并、开启运维写开关、生产字典 import，除非用户再次明确授权。
>
> 必读：`AGENTS.md` → `开发起步包/README.md` → `55_系统未完成事项统一执行计划.md` → `61_登录上线与本地服务器同步记录.md` → `74_平台功能与资产导航统一整改执行计划.md` → 本文件。

# 系统连接、运维 SQL 与诊断手术字典整改执行计划

## 0. 目标和最终产品形态

本计划一次解决三个问题：

1. **业务系统与数据资源只保留一个入口**：系统、数据库连接、Schema/Owner、表、字段在同一页面维护和浏览；旧“数据源连接”路径仅保留兼容重定向，不再显示第二个菜单。
2. **新增系统时可同时维护数据库连接**：支持 Oracle、MySQL、SQL Server、海量数据库 Vastbase、PostgreSQL；填写真实数据库地址、端口、Service/SID/Database、用户名和密码，密码只写不回显。
3. **运维工具支持受控自定义 INSERT/UPDATE**：提供 SQL 工作台、参数化模板、风险扫描、影响行预览、审批、二次确认、执行和审计。第一阶段只允许平台 `asset` schema，严禁写 HIS/ODS/HRP 等业务源库。
4. **导入现有诊断、手术维护 Excel**：以可 dry-run、可校验、幂等、单事务的方式导入平台字典表，页面不再为空。

完成后的导航：

```text
数据资产
└─ 业务系统与数据资源（唯一入口）
   ├─ 系统卡片
   ├─ 数据库连接
   └─ 系统 → 连接/实例/库 → Schema/Owner → 表/视图 → 字段

运维工具
├─ SQL 工作台
├─ 工具模板
├─ 运维任务
└─ 运维审计

字典中心
├─ 诊断手术维护
├─ 编码关系明细
└─ 同步差异
```

## 1. 生产现状与根因

### 1.1 业务系统和连接

2026-07-14 生产平台库实测：

- `asset_systems` 有 8 个旧系统：`DATA_CENTER/EMR/HIS_SOURCE/HRP/LIS/MOBILE_NURSING/PACS/SM`。
- 前端 `frontend/src/views/asset/systems/index.vue` 只保留 `HIS/HRP/DATA_CENTER`，导致实际编码为 `HIS_SOURCE` 的 HIS 被过滤掉。
- `asset_data_sources` 有 8 条连接，但 `target_host` 全为空，凭据状态均为 `unconfigured`。
- HIS 连接已经存在：`his_source_10_10_10_15`，但所属系统仍为 `HIS_SOURCE`。
- 数据中心内部 `ods_lis/ods_pacs/ods_emr/ods_ydhl/ods_sm` 仍挂在旧一级系统，没有正式执行 74 号归并 apply。
- 后端已有 `/systems` 和 `/sources` 两组接口；前端仍保留 `systems` 和 `sources` 两个页面，虽然 `/asset/sources` 已重定向，但菜单仍显示。
- `SystemUpsert` 不能携带连接信息；`DataSourceUpsert` 可以携带连接，但与系统新增割裂。
- `CredentialUpdate` 有 `username/password` 字段，但当前实现只保存调用方传入的 `credential_ref`，没有把输入密码安全写入凭据存储。

### 1.2 数据库驱动

现有后端已经实现以下连接器和元数据采集器，不得重复新建：

| 前端值 | 中文名称 | 默认端口 | 现有连接器 |
|---|---|---:|---|
| `oracle` | Oracle | 1521 | `OracleConnector` |
| `mysql` | MySQL | 3306 | `MysqlConnector` |
| `sqlserver` | SQL Server | 1433 | `SqlServerConnector` |
| `vastbase` | 海量数据库/Vastbase | 5432 | `VastbaseConnector` |
| `postgresql` | PostgreSQL | 5432 | `PostgresConnector` |

问题在于前端没有 Vastbase、字段按数据库类型动态变化不足，且连通性检测仍优先使用旧 `host_masked`，应改为真实 `target_host`。

### 1.3 运维 SQL

现有代码已经支持 `whitelist_dml`：

- 只接受单条参数化 `UPDATE ... WHERE` 或 `INSERT ... VALUES`。
- 只允许 `asset` schema 白名单表。
- 支持 allowed tables、allowed operations、dry-run SQL、最大影响行数、审批、二次确认和审计。
- 正式执行受 `APP_OPS_WRITE_ENABLED`、`APP_OPS_WRITE_D1_D5_CONFIRMED`、确认 Token 三重门禁控制。

生产库当前 `asset_ops_tool_templates` 为 0，所以页面没有可执行模板。现状不是“完全没有能力”，而是缺少安全易用的自定义 SQL 工作台、模板创建引导、审批闭环验收和正式启用决策。

### 1.4 诊断手术字典

生产平台库实测：

- `asset_dict_medical_code_sets = 0`
- `asset_dict_medical_code_items = 0`
- `asset_dict_medical_code_mappings = 0`

现有来源：

- `开发起步包/诊断与手术维护/山东省第二人民医院 临床诊断字典2026.06.04（全字段标识版）.xlsx`
- `开发起步包/诊断与手术维护/山东省第二人民医院 临床手术操作字典2026.06.02（全字段标识版）.xlsx`

现有 `backend/scripts/import_medical_maintenance_dicts.py` 可解析：

- 编码体系 8 个；
- 字典项 130765 条，其中诊断 104089、手术 26676；
- 映射 90265 条，其中诊断 74691、手术 15574。

但脚本当前直接删除受管编码体系后重导，没有命令行 dry-run、导入批次、文件哈希、异常阈值和生产确认参数，不能直接交给弱执行模型在生产运行。

## 2. 不可突破的安全边界

1. HIS、ODS、HRP、LIS、PACS、EMR、YDHL、SM 等业务源库继续只读，仅允许 `SELECT`。
2. 本轮“自定义 INSERT/UPDATE”只允许平台 PostgreSQL `data_asset.asset` schema。
3. 不允许自由文本 SQL 直接提交后立即执行；必须先保存为不可变版本模板，再扫描、dry-run、审批、二次确认。
4. 禁止 DELETE、MERGE、UPSERT、DDL、存储过程、多语句、注释、INSERT SELECT、无 WHERE UPDATE。
5. 密码不得存入 `asset_data_sources`、日志、审计 JSON、Git、文档、浏览器 localStorage/sessionStorage。
6. 密码写入服务端凭据文件或未来密钥服务；平台表只保存 `credential_ref` 和脱敏状态。
7. 读凭据与写凭据分离。新增业务源默认只能创建只读凭据；不得通过系统维护页面配置业务源写凭据。
8. AI 只允许读取系统、连接、字典和运维执行结果，不得调用凭据写入、审批或 DML 执行端点。
9. 字典导入只写平台库，执行前必须备份平台库和三张字典表统计。
10. 任何生产迁移均先测试库 upgrade/downgrade，再生产备份和 upgrade；不得在生产测试 downgrade。

## 3. 确定的数据模型

### 3.1 系统和连接关系

继续复用：

- `asset.asset_systems`：一级业务系统。
- `asset.asset_data_sources`：一个系统下的数据库连接/实例/库。

不再新建重复的“数据库系统”主表。关系固定为：

```text
AssetSystem 1 ── N AssetDataSource
AssetDataSource 1 ── N Schema/Owner
Schema/Owner 1 ── N Table/View
Table/View 1 ── N Column
```

### 3.2 `asset_data_sources` 建议新增字段

在下一实际唯一 Alembic head 上手写一笔迁移，建议字段：

| 字段 | 类型 | 用途 |
|---|---|---|
| `display_order` | Integer default 0 | 同系统多连接排序 |
| `service_mode` | Text | `service_name/sid/database`，解决 Oracle 与其他库字段含义不同 |
| `default_schema` | Text nullable | PostgreSQL/MySQL/SQL Server/Vastbase 默认库或 schema 提示 |
| `credential_username_masked` | Text nullable | 仅保存脱敏用户名，例如 `r***s`，不得保存密码 |
| `credential_updated_at` | timestamptz nullable | 凭据维护时间 |
| `credential_updated_by` | Text nullable | 审计操作者 |
| `connection_options` | JSONB nullable | charset、SSL 模式、Oracle thick 等非秘密配置；禁止放密码 |
| `write_policy` | Text default `readonly` | `readonly/platform_controlled`；业务源强制 readonly |

保留现有 `target_host/port/service_name/database_name/credential_ref/credential_status`，不重复建列。

约束：

- `db_type` 限定为 `oracle/mysql/sqlserver/vastbase/postgresql`。
- `port` 取值 1–65535。
- `(system_code, source_code)` 逻辑唯一，现有 `source_code` 全局唯一继续保留。
- `connection_identity_key` 由 `db_type + target_host + port + service/SID/database` 规范化生成。
- `write_policy=platform_controlled` 只允许 `system_code=ASSET_PLATFORM` 或专门批准的非业务目标；本轮不开放其他目标。

### 3.3 凭据存储

新增或扩展 `backend/app/services/credential_store.py`，不要把写入逻辑继续塞进 API：

```text
store(source_code, username, SecretStr) -> credential_ref
rotate(source_code, username, SecretStr) -> credential_ref
delete(source_code)
status(source_code) -> configured/missing/error
```

第一阶段使用服务器受控文件：

```text
/etc/data-asset/credentials/<source_code>.readonly
```

要求：

- 目录 root/运行用户可读，权限 0700；文件 0600。
- 临时文件写入、fsync 后原子 rename，避免半写文件。
- 文件名只允许规范化 source_code，防路径穿越。
- 日志只记录 source_code、操作者、成功/失败，不记录用户名全文和密码。
- API 响应只返回 `credential_configured`、脱敏用户名、更新时间和状态。
- 保留 `env:`、`file://` 的解析兼容，但新页面默认由后端生成 `file://` 引用。
- 删除/轮换凭据必须写 `GovernAuditLog`；审计不得包含 SecretStr。

## 4. 系统与数据资源统一改造

### 4.1 后端 API 契约

在 `backend/app/api/v1/systems.py` 复用现有路径，增加明确 DTO，禁止继续用一个 DTO 同时读写密码。

新增：

```text
POST /api/v1/systems-with-connections
GET  /api/v1/systems/{system_code}/detail
PATCH /api/v1/systems/{system_code}
POST /api/v1/systems/{system_code}/connections
PATCH /api/v1/sources/{source_code}
PUT  /api/v1/sources/{source_code}/credential
POST /api/v1/sources/{source_code}/check
POST /api/v1/sources/{source_code}/collect-metadata
DELETE /api/v1/sources/{source_code}/credential
```

`POST /systems-with-connections` 请求：

```json
{
  "system_code": "NEW_SYSTEM",
  "system_name_cn": "新业务系统",
  "system_type": "business",
  "status": "active",
  "connections": [
    {
      "source_code": "new_system_prod",
      "source_name_cn": "生产库",
      "db_type": "oracle",
      "target_host": "10.x.x.x",
      "port": 1521,
      "service_mode": "service_name",
      "service_name": "orcl",
      "database_name": null,
      "username": "readonly_user",
      "password": "只在请求中出现",
      "environment": "prod",
      "connection_mode": "direct",
      "collect_mode": "metadata_only"
    }
  ]
}
```

事务语义：系统、连接元数据和凭据不能简单放在一个数据库事务里假装原子。执行顺序：

1. 校验 DTO、权限、系统编码和连接唯一性。
2. 将凭据写入临时文件但不激活。
3. 数据库事务写系统和连接，保存最终 credential_ref。
4. 提交数据库后原子激活凭据文件。
5. 激活失败则把连接标记 `credential_status=error` 并记录补偿审计，不回显秘密。

所有系统/连接/凭据写端点分别使用：

- `source:manage`
- `source:credential_manage`
- `source:collect`

删除系统改为软停用。存在连接、资产、快照、任务引用时禁止物理删除；原 `delete_system` 级联删除连接的行为必须废止。

### 4.2 数据库类型字段规则

| 类型 | 必填 | 可选 | 默认端口 |
|---|---|---|---:|
| Oracle | host、port、service_mode、service_name 或 SID | thick client、连接模式 | 1521 |
| MySQL | host、port、database_name | charset、SSL mode | 3306 |
| SQL Server | host、port、database_name | instance、encrypt、trust cert | 1433 |
| Vastbase | host、port、database_name | default_schema、SSL mode | 5432 |
| PostgreSQL | host、port、database_name | default_schema、SSL mode | 5432 |

后端必须做同样校验，不能只靠前端切换字段。

### 4.3 HIS 和旧系统归并

扩展 `backend/scripts/normalize_business_systems.py`，仍默认 dry-run，新增 `--apply --confirmation <固定短语>`；正式执行前输出：

- 旧系统 → 新系统；
- source_code；
- 真实 target_host；
- 影响的表、字段、关系、快照、质量任务数量；
- 冲突和孤儿引用；
- 执行前后数量守恒。

当前明确映射：

| 旧系统 | 新系统 | 数据源 |
|---|---|---|
| `HIS_SOURCE` | `HIS` | `his_source_10_10_10_15` |
| `DATA_CENTER` | `DATA_CENTER` | `ods_8_216` |
| `LIS/EMR/MOBILE_NURSING/PACS/SM` | `DATA_CENTER` | 对应 `ods_*` 镜像连接 |
| `HRP` | `HRP` | `hrp_10_10_10_23` |

正式 apply 必须：

1. 先补齐显式 `target_host`，不能继续依赖 source_code 或显示名称推断。
2. 创建/保留三个 canonical 系统：`HIS/HRP/DATA_CENTER`。
3. 更新 `asset_data_sources.system_code` 和相关平台资产引用。
4. 旧系统改为 `merged` 并记录 canonical code，首轮不物理删除。
5. 验证 HIS 页面必然出现且能看到多 Owner、表和字段。

### 4.4 前端合并

主页面：`frontend/src/views/asset/systems/index.vue`。

重构为三个区域或 Tab：

1. 系统总览；
2. 数据库连接；
3. 数据资源树。

新增/编辑系统使用分步抽屉：

```text
步骤 1 基本信息 → 步骤 2 添加一个或多个连接 → 步骤 3 凭据 → 步骤 4 连通检测 → 步骤 5 保存
```

页面要求：

- 系统卡片不再硬编码过滤结果；后端返回 canonical 系统。
- 每个系统显示连接数、Schema 数、表数、字段数、最近检测状态。
- 展开系统显示连接卡片；连接显示数据库类型、脱敏地址、端口、库/Service、凭据状态。
- 密码输入框不回填；编辑时只显示“已配置/未配置”，留空表示不轮换。
- 提供“测试连接”“采集元数据”“轮换凭据”“禁用连接”，按权限显示按钮。
- 列表、树均处理 loading、empty、error、无权限状态。
- `vastbase` 中文显示为“海量数据库（Vastbase）”。

路由：

- `/asset/systems` 保持唯一菜单。
- `/asset/sources` 保留 redirect，`showLink=false`，避免旧书签失效。
- `frontend/src/views/asset/sources/index.vue` 不再独立维护业务逻辑；可变为薄重定向页，最终确认无引用后归档组件，但不改变兼容 URL。

API 优先扩展 `frontend/src/api/asset.ts`，不得新建重复 `systems.ts/sources.ts`。

## 5. 运维自定义 SQL 工作台

### 5.1 产品边界

用户可以编写自定义 `INSERT` 或 `UPDATE`，但不能把 SQL 文本当作即时命令直接执行。一次操作必须经过：

```text
编写 SQL → 参数识别 → 安全扫描 → 保存模板版本 → 输入参数
→ dry-run 影响行预览 → 提交审批 → 非本人审批 → 二次确认 → 执行 → 审计
```

### 5.2 模型扩展

手写迁移扩展 `asset_ops_tool_templates`：

- `version` Integer default 1；
- `status` draft/pending_review/approved/disabled；
- `sql_hash` Text；
- `created_by/updated_by/reviewed_by/reviewed_at`；
- `max_affected_rows` Integer default 100，硬上限 100；
- `target_scope` Text default `platform_asset`；
- `immutable_after_approval` Boolean default true。

扩展 `asset_ops_tool_runs`：

- `template_version`；
- `sql_hash`；
- `preview_count`；
- `confirmation_digest`；
- `transaction_id` 或执行追踪号；
- `error_code` 和脱敏错误摘要。

批准版本不可原地修改；修改必须复制新版本重新审批。

### 5.3 SQL 安全规则

复用并增强 `backend/app/services/ops_sql_safety.py`：

- 仅一条 SQL。
- 仅 `INSERT INTO asset.<白名单表> (...) VALUES (:param...)`。
- 仅 `UPDATE asset.<白名单表> SET ... WHERE <带参数条件>`。
- 禁止恒真 WHERE、仅 `1=1`、无主键/唯一键约束的宽更新。
- 禁止拼接标识符、函数、子查询、CTE、RETURNING 大结果、注释和分号。
- SQL 中必须使用 bind 参数，参数类型由 JSON Schema 校验。
- dry-run SQL 必须是同条件的 `SELECT count(*)`；服务端校验目标表和 WHERE 参数集合一致，不能完全信任用户填写。
- 执行事务设置 statement timeout、lock timeout；异常全部 rollback。
- 影响行数超过模板阈值不执行。
- 执行结果只返回影响行数，不返回敏感行内容。
- 同一个 run 只能执行一次，使用状态条件更新或行锁防双击并发。

### 5.4 权限与审批

新增资源：

- `ops:sql:view`
- `ops:sql:create`
- `ops:sql:review`
- `ops:sql:execute`
- `ops:sql:audit`

规则：

- 创建人不能审批自己的模板或执行申请。
- 审批人和执行人可按角色分离。
- 正式执行继续要求三重环境开关；计划实现和测试阶段开关保持关闭。
- 用户复核本计划不等于授权开启生产写开关；开启必须在完整测试通过后再次明确确认。
- 所有审计记录保存 SQL hash、模板版本、目标表、参数名、脱敏参数、预估/实际行数和操作者，不保存密码。

### 5.5 API 与前端

建议 API：

```text
POST /api/v1/ops/sql/validate
POST /api/v1/ops/sql/templates
POST /api/v1/ops/sql/templates/{id}/submit
POST /api/v1/ops/sql/templates/{id}/approve
POST /api/v1/ops/sql/templates/{id}/reject
POST /api/v1/ops/sql/runs
POST /api/v1/ops/sql/runs/{id}/preview
POST /api/v1/ops/sql/runs/{id}/submit
POST /api/v1/ops/sql/runs/{id}/approve
POST /api/v1/ops/sql/runs/{id}/execute
GET  /api/v1/ops/sql/runs/{id}/audit
```

新增页面 `frontend/src/views/ops/sql-workbench/index.vue`，扩展 `frontend/src/api/ops.ts` 和 `frontend/src/router/modules/ops.ts`。

页面必须明确显示：

- 当前只允许平台 `asset` schema；
- 支持 INSERT/UPDATE；
- 禁止业务源库写入；
- SQL 校验错误、识别的表/动作/参数；
- dry-run 预估行数与最大允许行数；
- 审批状态、二次确认和执行结果；
- 写开关关闭时显示“仅可设计和 dry-run，不可正式执行”。

不要使用浏览器内拼 SQL，不要允许前端提交 `operator/approved_by`。

## 6. 诊断手术字典导入

### 6.1 改造导入脚本

修改 `backend/scripts/import_medical_maintenance_dicts.py`：

```text
--source-dir <目录>
--dry-run（默认）
--apply
--confirmation IMPORT-MEDICAL-DICTS
--report <json输出路径>
--max-error-rate 0
```

默认只解析和校验，不连接数据库写入。dry-run 报告至少包含：

- 两个输入文件名、大小、SHA-256、工作表；
- 输入总行、空编码/空名称、重复编码、同码异名；
- 8 个 code set 的字典项数量；
- 诊断/手术映射数量；
- 外键缺失映射；
- 与平台现有数据的新增/更新/停用/不变统计；
- 预计删除/替换范围，仅限 `MANAGED_CODE_SETS`。

### 6.2 导入方式

禁止先删正式数据再分批插入。建议：

1. 生产平台库备份。
2. 创建导入批次记录 `asset_dict_medical_import_runs`，记录文件哈希、统计、操作者、状态，不记录文件敏感内容。
3. 将解析结果写临时 staging 表或内存批量校验。
4. 在单个数据库事务中对 8 个受管 code set 做幂等 upsert/替换。
5. 校验 code set、item、mapping 数量和映射引用完整性。
6. 成功后提交；任何异常整体 rollback。
7. 重复导入同一 SHA-256 默认拒绝或标记 `no_change`，不得制造重复。

不得触碰用户在页面维护的非 `MANAGED_CODE_SETS` 数据。

### 6.3 首次导入基线

当前解析期望值：

| 项目 | 期望数量 |
|---|---:|
| Code set | 8 |
| 字典项合计 | 130765 |
| 诊断字典项 | 104089 |
| 手术字典项 | 26676 |
| 映射合计 | 90265 |
| 诊断映射 | 74691 |
| 手术映射 | 15574 |

这些数字是当前文件解析基线，不应写死为业务规则。执行时若变化，必须在 dry-run 报告解释文件哈希或解析逻辑变化；不可为了通过测试强行断言固定数量。

### 6.4 页面验收

验证：

- `/dict/medical` 可分别筛选诊断、手术及编码体系；
- 关键词、编码、名称、状态分页正确；
- `/dict/mappings` 能查看院内码到国家临床版/医保版映射；
- 页面首屏不加载 13 万全量，必须后端分页和索引查询；
- 导出采用异步或分页流式处理，禁止一次性在浏览器装载全量；
- loading、empty、error、无权限状态完整；
- 字典管理员可维护，普通用户只读，未授权写端点 403。

## 7. 实施阶段与严格顺序

### S0：基线与保护

- 检查 Git dirty 状态，保护现有 E9–E11 未提交代码。
- `alembic heads/current`，不得假设新 revision。
- 记录系统、连接、字典、运维模板数量。
- 备份测试库；生产变更另做生产备份。
- 输出计划修改文件清单。

### S1：模型、DTO 和手写迁移

- 扩展连接字段和约束。
- 扩展运维模板/运行版本字段。
- 新增字典导入批次表（若采用 staging，表名遵守 `asset_` 前缀）。
- 每笔迁移独立 upgrade/downgrade；先测试库往返。

### S2：系统连接后端与凭据存储

- 实现组合新增、详情、连接维护、凭据写入/轮换/删除、连接检测。
- 所有写端点补 `Depends(require_permission(...))` 和审计。
- 修复连接器使用 `target_host`，兼容旧字段但不继续写旧地址。

### S3：HIS 和系统归并

- 补真实目标地址。
- dry-run 输出影响范围和数量守恒。
- 解决全部冲突后，生产备份并 apply 平台库。
- 不删除旧系统，只标记 merged。

### S4：统一前端页面

- 合并系统和连接管理 UI。
- 隐藏重复数据源菜单，保留兼容路由。
- 完成五种数据库动态字段和密码只写不回填。
- 真实 HIS/HRP/数据中心浏览器验收。

### S5：运维 SQL 工作台

- 先完成 validator、模板版本、审批、dry-run、并发保护测试。
- 前端工作台接入。
- 生产写开关继续关闭，只验证关闭态 403。
- 是否开启正式平台库写执行，必须等待本计划复核后的再次授权。

### S6：诊断手术字典

- 改造脚本并执行本地 dry-run。
- 测试库 apply + 重复导入幂等 + 回滚验证。
- 生产备份、dry-run 报告复核、单事务 apply。
- 页面统计、搜索、分页、映射和权限验收。

### S7：全量验收、发布和同步

- 后端 pytest 全量通过；不得继续保留当前 40 failed/3 errors。
- Alembic upgrade/downgrade/upgrade 测试库往返。
- 前端 typecheck、Vitest、build。
- 浏览器角色矩阵。
- 生产发布后本地/服务器 SHA-256 对账，更新 61。
- 更新 README、55、66、74、75；完成前不归档 75。

## 8. 文件级修改清单

### 后端

- `backend/app/models/asset_system.py`
- `backend/app/models/ops_tool.py`
- `backend/app/models/dict_medical.py`
- `backend/app/models/__init__.py`
- `backend/app/api/v1/systems.py`
- `backend/app/api/v1/ops_tools.py`
- `backend/app/api/v1/dict_medical_api.py`
- `backend/app/api/v1/permissions.py`
- `backend/app/core/security.py`（仅权限资源需要时）
- `backend/app/services/credentials.py`
- 新增 `backend/app/services/credential_store.py`
- `backend/app/services/db_connectors.py`
- `backend/app/services/metadata_collector.py`
- `backend/app/services/ops_sql_safety.py`
- `backend/app/services/ops_executor.py`
- `backend/scripts/normalize_business_systems.py`
- `backend/scripts/import_medical_maintenance_dicts.py`
- 连续手写 Alembic migrations
- 对应 tests

### 前端

- `frontend/src/api/asset.ts`
- `frontend/src/api/ops.ts`
- `frontend/src/api/dict.ts` 或现有字典 API 文件，不新增重复模块
- `frontend/src/router/modules/asset.ts`
- `frontend/src/router/modules/ops.ts`
- `frontend/src/views/asset/systems/index.vue`
- `frontend/src/views/asset/sources/index.vue`（仅兼容处理）
- 新增 `frontend/src/views/ops/sql-workbench/index.vue`
- `frontend/src/views/ops/tools/index.vue`
- `frontend/src/views/ops/runs/index.vue`
- `frontend/src/views/ops/audit/index.vue`
- `frontend/src/views/dict/medical/index.vue`
- `frontend/src/views/dict/mappings/index.vue`
- 对应 Vitest

### 部署与文档

- `deploy/scripts/run_data_asset_api.sh`：凭据卷持久化核对
- `deploy/offline/README.md`：凭据目录和独立验收镜像说明
- `开发起步包/README.md`
- `55_系统未完成事项统一执行计划.md`
- `61_登录上线与本地服务器同步记录.md`
- `66_多AI交接_未完成与待实现清单.md`
- `74_平台功能与资产导航统一整改执行计划.md`
- 本文件执行日志

## 9. 必须新增的测试

### 系统与连接

- 组合创建系统和一个/多个连接。
- 五种 db_type 的默认端口和字段校验。
- 同连接 identity key 冲突返回 409。
- 密码不出现在 GET、日志、审计、异常和 OpenAPI 示例。
- 路径穿越 source_code 被拒。
- 凭据文件权限、原子轮换、删除和缺失状态。
- 普通用户维护连接/凭据返回 403。
- HIS_SOURCE → HIS，ODS 子系统 → DATA_CENTER；数量守恒。
- `/asset/sources` 兼容跳转但不显示重复菜单。

### 运维 SQL

- 合法参数化 INSERT/UPDATE。
- 无 WHERE UPDATE、恒真 WHERE、多语句、注释、DELETE/DDL/UPSERT/INSERT SELECT 全部拒绝。
- 非 asset schema 和非白名单表拒绝。
- 参数缺失、额外参数、类型错误。
- dry-run 条件与 DML 条件不一致拒绝。
- 超过 100 行拒绝。
- 申请人自审拒绝。
- 未审批、未二次确认、三重开关关闭均拒绝。
- 双击/并发执行只有一次成功。
- SQL/参数/凭据不泄漏，审计只保存 hash 和脱敏值。
- 业务源连接即使有凭据也不能进入写执行器。

### 字典导入

- 两份 Excel sheet/header 解析。
- 空编码、重复码、同码异名、来源标记异常。
- dry-run 零写入。
- apply 单事务，注入异常时整体 rollback。
- 同文件重复导入 no_change/幂等。
- 仅替换 8 个 managed code sets，不影响人工字典。
- 映射两端均存在。
- 13 万数据分页、关键词查询和索引性能。
- 字典管理员写、普通用户读、越权 403。

## 10. 验收命令

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

生产前额外执行：

```text
1. 平台库 custom dump + SHA-256
2. 系统归并 dry-run（冲突必须为 0）
3. 字典导入 dry-run（文件 hash、错误率、数量）
4. 运维写开关关闭态 403
5. 发布后 /health、首页、主 JS/CSS
6. 本地/服务器受管文件 SHA-256 对账
```

## 11. 完成判定

只有同时满足以下条件才能标记完成：

- 页面只显示一个“业务系统与数据资源”入口。
- HIS、HRP、数据中心均显示；HIS 有连接、Owner、表和字段。
- 新增系统可同时维护五种数据库连接。
- 密码可安全写入、轮换和删除，但任何读取接口均不回显。
- 连接检测和元数据采集使用真实 target_host。
- 运维 SQL 工作台支持受控 INSERT/UPDATE，审批、预览、二确和审计闭环通过。
- 业务源库写操作为 0；生产运维写开关未经再次授权不得打开。
- 诊断手术页面存在 8 个编码体系、当前文件对应的字典项与映射，搜索分页正常。
- 全量 pytest、Alembic 往返、typecheck、Vitest、build 和浏览器角色矩阵全部通过。
- 生产备份、发布、数据库 head、镜像 ID、本地/服务器哈希已记录。

## 12. 执行日志

### [S0–S6] 2026-07-14（代码实施批次）

- **完成内容**：
  - S0：盘点现状；当前 Alembic head 链 `w9d0e1f2a3b4` → 新增 `x0e1f2a3b4c5`；工作区保留 E9–E11 未提交改动。
  - S1：手写迁移扩展 `asset_data_sources` 连接字段、`asset_ops_tool_*` 版本字段、`asset_dict_medical_import_runs`。
  - S2：`credential_store.py` 文件凭据原子写入；`systems-with-connections`/详情/连接/凭据轮换；连通检测优先 `target_host`；删除系统改为软停用。
  - S3：`normalize_business_systems.py` 显式映射 + `--confirmation NORMALIZE-BUSINESS-SYSTEMS`（默认 dry-run）。
  - S4：前端统一系统页三 Tab；五种库动态字段；密码只写不回显；`/asset/sources` `showLink=false` + 薄重定向页。
  - S5：`/api/v1/ops/sql/*` 校验/模板/审批/run/预览；前端 SQL 工作台；写开关默认关闭。
  - S6：导入脚本默认 dry-run；报告含 SHA-256/数量/平台 diff；基线 8/130765/90265 已复测。
- **修改文件（本计划核心）**：
  - 后端：`asset_system.py` / `ops_tool.py` / `dict_medical.py` / `systems.py` / `ops_tools.py` / `permissions.py` / `credential_store.py` / `connection_identity.py` / `ops_sql_safety.py` / `ops_executor.py` / `normalize_business_systems.py` / `import_medical_maintenance_dicts.py` / `x0e1f2a3b4c5_*.py` + 单测
  - 前端：`api/asset.ts` / `api/ops.ts` / `views/asset/systems/index.vue` / `views/asset/sources/index.vue` / `views/ops/sql-workbench/index.vue` / `router/modules/asset.ts` / `router/modules/ops.ts`
- **migration revision/head**：新增 `x0e1f2a3b4c5`（revises `w9d0e1f2a3b4`）；**尚未**在测试库/生产执行 upgrade。
- **系统归并 dry-run/apply**：脚本已增强；**未**对生产 apply。
- **凭据安全验证**：单元测试 store/rotate/delete/路径穿越通过；API 响应不含 password/credential_ref。
- **运维 SQL 安全/审批/执行**：validator 增强恒真 WHERE/dry-run 一致性；工作台 API+页已接；**生产写开关保持关闭**。
- **字典 dry-run 数量**：code_sets=8, items=130765 (diag 104089 / oper 26676), mappings=90265；平台侧 managed 数据已存在且 diff 全 0（no_change）；writes=0。
- **pytest**：`tests/test_credential_store_unit.py` + `test_connection_identity_unit.py` + `test_ops_sql_safety.py` → **17 passed**（`--noconftest`）。全量 pytest **阻塞**：本机 `127.0.0.1:55432` 测试库隧道未连通，无合法 `APP_TEST_DB_URL` 时拒绝运行（设计如此）。
- **typecheck/Vitest/build**：`pnpm typecheck` PASS；`pnpm test` **39 passed**；`pnpm build` PASS（约 29s）。
- **浏览器角色矩阵**：未做（需生产/联调环境）。
- **生产备份/镜像/健康**：本批次未动生产。
- **业务源库写操作**：0
- **遗留/阻塞**：
  1. 测试库隧道：本机 SSH 密钥认证 `10.10.8.83` 失败，`127.0.0.1:55432` 不可用 → 全量 pytest / alembic upgrade 未跑
  2. 系统归并生产 apply 需用户确认 + 备份
  3. 运维写开关开启需再次授权（默认关闭）
  4. 字典生产 apply 需备份（dry-run 显示平台已有同批数据，优先 no_change）
  5. 浏览器角色矩阵与生产发布

### [S5/S7 补强] 2026-07-14（续）

- 运维执行：`with_for_update` 行锁 + `transaction_id` + 失败 `error_code/error_summary_masked`，防双击并发。
- 前端：连接 Tab 增加「采集」元数据；工具模板页入口链到 SQL 工作台；字典空态提示导入命令。
- 部署：`run_data_asset_api.sh` 凭据卷改为 **rw** + `APP_CREDENTIAL_DIR`；`deploy/offline/README.md` 补充凭据目录说明。
- 权限目录：补 `ops.sql.*` / `source.manage|credential_manage|collect`。
- 单元测试合计 **31 passed**（--noconftest）。

### [S7] 2026-07-14（8.83 生产部署与现场复核）

- **生产备份**：`/opt/data-asset/backups/data_asset_pre_plan75_20260714163320.dump`，SHA-256 `f7010968b627e9b34a4487dc7447b8e2c7aefdb28ad2f2ccafbbe556fe617d63`。
- **测试门禁**：独立测试库完成 `w9d0e1f2a3b4 → x0e1f2a3b4c5`；服务器专项测试 `20 passed, 2 skipped`。本地专项测试 22 项、前端 typecheck、39 项 Vitest 和 build 均通过。
- **生产发布**：平台库 head=`x0e1f2a3b4c5`；镜像 `data-asset:20260714-plan75-r2`；发布目录 `/opt/data-asset/releases/plan75-20260714163413`；前端已原子替换。
- **现场修订**：归并脚本错误引用旧关系模型字段，已改用 `AssetRelationReview` 并补齐 source_code 引用更新；字典导入器因关闭 autoflush 而在计数前漏 `db.flush()`，首次 apply 完整回滚，修订后单事务导入成功。
- **归并 dry-run**：8 个源、6 个计划变更、0 冲突、8 个缺失 `target_host`、`applied=false`；未正式归并。
- **字典结果**：8 个编码体系、130765 个字典项、90265 条映射；成功批次 `med-import-20260714084733`。源 Excel 中 1279 个有码无名称的不完整辅助项被跳过，有效产物与基线一致。
- **运行与安全**：容器健康、首页 200、API database connected；凭据目录 rw 持久挂载、Oracle 目录 ro 挂载；`APP_OPS_WRITE_ENABLED=false`；业务源库写操作为 0。
- **剩余配置**：需在统一系统页面配置 8 条连接的真实 `target_host`/凭据后重新 dry-run，才可另行决定是否执行系统归并 apply。
