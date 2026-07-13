> 类别：方案
> Status: implemented by Codex on 2026-07-07 for HIS read-only identity sync. Backend configurable direct/ssh_jump HIS collector/upsert service, dry_run, audit, multi-department table, API, frontend trigger/profile display, and mock tests are done; remaining production validation and HRP source integration.
> ⏳状态：🟠部分完成 | 负责AI/人：Codex 2026-07-07 | 下一步：当前 10.10.8.84 部署服务器未通，先通过 10.10.8.83 跳转验证 HIS dry_run；84 打通后切回部署直连/夜间正式验证；随后补 HRP 来源 | 最后更新：2026-07-07
> 📌多AI协作：HIS 只读同步代码已落地；后续动手前先读《46_文档完成状态总表》，只继续生产验证或 HRP 接入。

# HIS 人员/科室同步实施计划

## 1. 目标

为数据治理平台实现 HIS 人员基本信息、科室、人员-科室映射同步能力：从 HIS 源库只读采集，写入平台本地 PostgreSQL 的 identity 模块，供人员画像与权限分配使用。

## 2. 当前已完成基础

| 能力 | 当前状态 |
|---|---|
| identity 基础表 | 已有 `asset_identity_departments/persons/person_sources/accounts/sync_diffs` |
| SQLAlchemy 模型 | 已有 `backend/app/models/identity.py` |
| 后端查询 API | 已有 `GET /identity/departments/persons/accounts/sync-diffs` |
| 同步触发 | 已新增 `POST /api/v1/identity/sync/his`，`sync_executor.run_sync(entity_type="identity_his")` 已接入真实执行器；`collect-sources` 仍保留来源暂存采集入口 |
| Oracle 连接器 | 已有 `OracleConnector`，支持 thick 模式 |
| 前端页面 | 已有 `identity/departments/persons/accounts/sync-diffs` 页面 |

结论：基础查询与展示已具备；本计划只补“真实只读采集 + 本地 upsert + 多科室关系 + 审计”。

## 2.1 2026-07-07 落地状态

已完成：

1. `asset_identity_person_departments` 模型与 Alembic 迁移已存在并通过 `alembic upgrade head`。
2. `backend/app/core/config.py` 已增加 HIS 源库配置，密码仅从 `APP_HIS_SOURCE_PASSWORD` 读取；连接模式支持 `APP_HIS_SOURCE_CONNECTION_MODE=direct|ssh_jump`，当前验证可用 `APP_HIS_SOURCE_JUMP_HOST=10.10.8.83`。
3. `backend/app/services/his_identity_sync.py` 已实现只读 SELECT 采集、`SYS_EMPLOYEE.USERID = STAFF_DICT.EMP_NO` 桥接、主档优先级合并、来源表落库、多科室 upsert、敏感字段 hash/mask、`dry_run` 与审计。
4. 已新增 `POST /api/v1/identity/sync/his?dry_run=true|false`，并将 `sync_executor` 的 `identity_his` 分支接入真实执行器。
5. 前端 `identity.ts`、`identity/sync-diffs/index.vue`、`identity/persons/index.vue` 已支持 HIS 同步触发、dry_run 统计展示和多科室画像表格。
6. `tests/test_his_identity_sync.py` 已用 mock Oracle 覆盖 dry_run、桥接、upsert、脱敏和审计。

仍未完成：生产内网 HIS dry_run/夜间正式验证、`DOCTOR_GROUP.DOCTOR_USER` 真实语义抽样确认、HRP 来源接入。

## 3. 源库与连接口径

| 项 | 口径 |
|---|---|
| 源库 | Oracle 11g `10.10.10.15:1521/his` |
| 账号 | `ready_his`，只读，仅 `SELECT` |
| 密码 | 通过安全渠道配置到 `backend/.env` 的 `APP_HIS_SOURCE_PASSWORD`，不进 git |
| 部署连接 | 目标形态：FastAPI 在内网服务器直连 `10.10.10.15`；当前 `10.10.8.84` 未通时，先通过 `10.10.8.83` 跳转验证 |
| 开发机限制 | Windows 开发机不直连 HIS；本地单测必须 mock `OracleConnector`，真实 dry_run 可配置 `ssh_jump` 到 `10.10.8.83` 执行 |
| Oracle 客户端 | Linux 使用 `/opt/oracle/instantclient_21` thick 模式 |

## 4. 源表清单

| 表 | 用途 | 关键字段 |
|---|---|---|
| `COMM.DEPT_DICT` | 科室字典 | `DEPT_CODE`、`DEPT_NAME`、`OUTP_OR_INP`、`STOP_FLAG` |
| `COMM.STAFF_DICT` | 老人员表 | `EMP_NO`、`NAME`、`DEPT_CODE`、`JOB`、`TITLE`、`STATUS`、`ID_NO` |
| `COMM.SYS_EMPLOYEE` | 新员工表 | `EMPLCODE`、`EMPLNAME`、`DEPTCODE`、`DEPTID`、`VALIDSTATE`、`IDENNO`、`USERID` |
| `COMM.DOCTOR_GROUP` | 医生-科室分组 | `DOCTOR_USER`、`DEPT_CODE`、`DOCTOR` |
| `COMM.STAFF_VS_GROUP` | 人员-工作组 | `GROUP_CLASS`、`GROUP_CODE`、`EMP_NO` |
| `COMM.STAFF_GROUP_DICT` | 工作组反查科室 | `GROUP_CODE`、`DEPT_CODE` |

关键桥接：`SYS_EMPLOYEE.USERID = STAFF_DICT.EMP_NO`。

## 5. 已确认决策

1. 使用 `ready_his` 连 `10.10.10.15/his`；84 部署服务器打通后 FastAPI 内网直连，当前验证阶段允许配置 `ssh_jump` 经 `10.10.8.83`。
2. 密码通过 `APP_HIS_SOURCE_PASSWORD` 注入，禁止写入代码、日志和 git。
3. 一人多科室采用主档主科室 + 新建多对多表 `asset_identity_person_departments`。
4. `STAFF_DICT` 与 `SYS_EMPLOYEE` 两源都进入 `asset_identity_person_sources`。
5. 人员主档优先取 `SYS_EMPLOYEE`，通过 `USERID=EMP_NO` 桥接老表。

## 6. 开发任务拆解

### 6.1 数据库迁移

新增 Alembic 迁移，建议 revision：`m0e1f2a3b4c5`，`down_revision='l9e0f1a2b3c4'`。

创建表：`asset.asset_identity_person_departments`。

字段建议：

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | `BigInteger` | 主键；保持现有 identity 表手写 ID 风格 |
| `person_code` | `Text` | 平台人员编码，通常为工号 |
| `dept_code` | `Text` | 科室编码 |
| `is_primary` | `Boolean` | 是否主科室 |
| `source_table` | `Text` | 来源表，如 `STAFF_DICT`、`SYS_EMPLOYEE`、`DOCTOR_GROUP` |
| `source_dept_code` | `Text` | 源表科室编码 |
| `updated_at` | `TIMESTAMP(timezone=True)` | 更新时间 |

唯一约束：`(person_code, dept_code, source_table)`。

### 6.2 配置项

在 `backend/app/core/config.py` 扩展：

```python
his_source_host: str = "10.10.10.15"
his_source_port: int = 1521
his_source_service: str = "his"
his_source_user: str = "ready_his"
his_source_password: str = ""
his_source_connection_mode: str = "direct"
his_source_oracle_client_lib: str = "/opt/oracle/instantclient_21"
his_source_jump_host: str = "10.10.8.83"
his_source_jump_port: int = 22
his_source_jump_user: str = "root"
his_source_jump_key: str = ""
his_identity_sync_max_rows: int = 20000
```

环境变量对应 `APP_HIS_SOURCE_PASSWORD` 等，密码不提供默认明文。当前 84 未通时，验证环境设置 `APP_HIS_SOURCE_CONNECTION_MODE=ssh_jump`、`APP_HIS_SOURCE_JUMP_HOST=10.10.8.83`；84 打通后可切回 `direct`。

### 6.3 同步服务

新增 `backend/app/services/his_identity_sync.py`。

入口函数：

```python
sync_his_identity(operator: str | None = None, dry_run: bool = False) -> dict
```

职责：

1. 用 `OracleConnector` 只读连接 HIS。
2. 只执行 `SELECT`，所有 SQL 加 `ROWNUM <= max_rows`。
3. 采集 6 张源表。
4. 生成本地 upsert 数据：科室、人员主档、人员来源、多科室关系。
5. `dry_run=True` 只返回统计，不写 PostgreSQL。
6. 正式执行时写 `GovernAuditLog(module='sync', action='sync_run')`。

### 6.4 合并规则

| 对象 | 规则 |
|---|---|
| 科室 | 以 `DEPT_DICT.DEPT_CODE` 为唯一键 upsert `asset_identity_departments` |
| 老人员来源 | `STAFF_DICT.EMP_NO` 入 `asset_identity_person_sources` |
| 新员工来源 | `SYS_EMPLOYEE.EMPLCODE` 入 `asset_identity_person_sources` |
| 主人员编码 | 优先 `SYS_EMPLOYEE.USERID`，缺失时用 `EMPLCODE`；老表用 `EMP_NO` |
| 主档优先级 | `SYS_EMPLOYEE` 覆盖 `STAFF_DICT` 的姓名、主科室、状态 |
| 主科室 | `SYS_EMPLOYEE.DEPTCODE/DEPTID` 优先，其次 `STAFF_DICT.DEPT_CODE` |
| 多科室 | `STAFF_DICT`、`SYS_EMPLOYEE`、`DOCTOR_GROUP`、`STAFF_VS_GROUP + STAFF_GROUP_DICT` 合并入多对多表 |

### 6.5 脱敏规则

1. `ID_NO`、`IDENNO` 不以明文进入 `raw_data`。
2. 如需追踪，写 `sha256` 或掩码。
3. 日志与审计只写统计，不写姓名、身份证、电话、地址明细。
4. 前端展示人员姓名来自本地人员主档，外部 AI 不获取人员明细。

### 6.6 API 改造

新增接口：

```http
POST /api/v1/identity/sync/his?dry_run=true|false
```

返回：采集行数、准备写入数、实际 upsert 数、桥接率、未匹配 `DOCTOR_GROUP` 数。

扩展：

1. `POST /identity/collect-sources` 可调用该同步服务，默认 `dry_run=true` 或按参数控制。
2. `GET /persons/{person_code}` 返回 `departments` 多科室列表。
3. `sync_executor.run_sync(entity_type='identity_department'/'identity_person')` 接入真实同步服务。

### 6.7 前端改造

1. `frontend/src/api/identity.ts` 增加 `syncHisIdentity(params)`。
2. `identity/sync-diffs/index.vue` 增加“同步 HIS 人员/科室”按钮。
3. 按钮先支持 `dry_run`，展示采集统计和桥接率。
4. `identity/persons/index.vue` 人员画像增加“多科室”表格。

### 6.8 测试

新增 `backend/tests/test_his_identity_sync.py`。

测试重点：

1. mock `OracleConnector.execute_readonly()` 返回 6 张表样本。
2. 验证 `SYS_EMPLOYEE.USERID = STAFF_DICT.EMP_NO` 桥接。
3. 验证 `SYS_EMPLOYEE` 优先覆盖主档。
4. 验证 `asset_identity_person_departments` 多科室写入。
5. 验证 `dry_run=True` 不写本地库。
6. 验证 `raw_data` 不保存身份证明文。
7. 验证同步审计写入 `GovernAuditLog`。

## 7. 待实测问题

1. `DOCTOR_GROUP.DOCTOR_USER` 是工号还是姓名，需源库抽样确认。
2. `SYS_EMPLOYEE.USERID = STAFF_DICT.EMP_NO` 命中率需统计。
3. 当前 `10.10.8.84` 部署服务器尚未连通；先通过 `10.10.8.83` 跳转执行 dry_run，后续再验证 84 到 `10.10.10.15:1521/his` 的直连。
4. `VALIDSTATE`、`STATUS`、`STOP_FLAG` 的值域需实测后固化映射。

## 8. 验收命令

后端：

```powershell
cd F:\python\数据资产\backend
.\.venv\Scripts\python.exe -m pytest tests/ -q
.\.venv\Scripts\python.exe -m alembic upgrade head
```

前端：

```powershell
cd F:\python\数据资产\frontend
pnpm run typecheck
pnpm run build
```

## 9. 执行提示词

```text
你接手 HIS 人员/科室同步开发，路径 F:\python\数据资产。先读 AGENTS.md、开发起步包/46_文档完成状态总表.md、开发起步包/47_HIS人员科室同步实施计划.md、开发起步包/43_人员与权限维护功能开发执行计划.md。

只实现 47 号计划，不做无关功能。源库 HIS 只读 SELECT，禁止 DML/DDL；密码只从 APP_HIS_SOURCE_PASSWORD 读取，不写代码、日志、git。真实连接只在内网服务器执行，开发机测试必须 mock OracleConnector。

任务：新增 asset_identity_person_departments 迁移和模型；扩展 HIS 源库配置；新增 his_identity_sync 服务；接入 POST /api/v1/identity/sync/his 和 sync_executor identity 分支；前端增加同步按钮和人员画像多科室；补 mock 测试。完成后运行后端 pytest、alembic upgrade head，前端 pnpm typecheck/build，并同步更新 46 号总表状态。
```

