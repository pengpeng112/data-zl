> 类别：执行记录
>
> 状态：当前（2026-08-10 一次性正式同步已完成；每日职称子任务已发布并由既有 host cron 调度，2026-08-12 夜窗只读复核 PASS）
> 最后复核：2026-08-13

# HIS 职称同步 JHEMR 执行与复用说明

## 1. 文档目的

本说明是 HIS 人员职称同步到 JHEMR 的跨会话接手入口。后续更换 AI、再次全量对账、职称字典发生变化或准备并入每日人员同步时，应先读取：

1. 根目录 `AGENTS.md`；
2. `开发起步包/README.md`；
3. `开发起步包/55_系统未完成事项统一执行计划.md`；
4. 本文件；
5. `.agents/skills/hisuser-readonly-sql/SKILL.md`；
6. 涉及每日任务时再读 `122` 和两份 `125_*`；103/107 已归档，仅用于历史追溯。

本文件记录业务契约、当前代码、2026-08-10 实际执行结果、可复用步骤、失败关闭条件、审计、回滚和未来每日化方案。不得依赖聊天记录补齐这些信息。

## 2. 当前结论

| 项目 | 状态 | 结论 |
|---|---|---|
| 2026-08-10 一次性正式同步 | PASS | 317 个 JHEMR 账号的非一致职称已覆盖，提交后二次对账待变更数为 0 |
| HIS 业务源库写入 | PASS | 仅执行限量、显式字段 `SELECT`，DML/DDL/锁为 0 |
| JHEMR 目标写入 | PASS | 仅更新 `jhemr.users.education_title`，317 行；未触碰其他业务字段 |
| 平台动作审计 | PASS | 1 个 run、1 个 subtask、317 个 HMAC action 均为 success/executed |
| 回滚备份 | PASS | 已保存在 8.83 宿主机受限目录，文件权限 600 |
| 本地复用代码 | PASS | 已实现 dry-run、备份绑定、批量覆盖、事务内回读、HMAC 审计和专项测试 |
| 完整后端 pytest | 历史曾 BLOCKED；后续已解除 | 合法隔离测试库已建立；当前新增图谱回归的测试库权限/脏数据缺口统一由 130 S1 处理，禁止用生产库替代测试库 |
| 当前服务器应用镜像包含职称代码 | PASS | 已进入当前生产后端 `data-asset:126p5-20260811223311`；2026-08-12 夜窗存在真实职称 subtask |
| 每日人员任务包含独立职称子任务 | PRODUCTION PASS | 已作为必需子任务由唯一 host cron 调度；2026-08-12 `success`，planned=0、failed=0、幂等跳过2090 |
| 目标提交与完成态审计恢复 | LOCAL PASS | 每批先落 planned action，再以单个 JHEMR 事务整批更新；完成态审计失败保留 `target_committed_pending_audit`，下一轮凭账号和值 HMAC 只读核对后补记，未确认动作失败关闭 |

## 3. 唯一业务契约

### 3.1 数据来源与目标

| 角色 | 物理对象 | 字段 | 用途 |
|---|---|---|---|
| HIS 人员主表 | `FXHIS.SYS_EMPLOYEE` | `EMPLCODE` | 与 JHEMR 用户匹配的稳定人员键 |
| HIS 人员主表 | `FXHIS.SYS_EMPLOYEE` | `LEVLCODE` | 职称字典代码 |
| HIS 职称字典 | `PORTAL_USER.PORTAL_SYS_DICT` | `DICT_CODE` | 与 `LEVLCODE` 关联 |
| HIS 职称字典 | `PORTAL_USER.PORTAL_SYS_DICT` | `DICT_NAME` | 要写入 JHEMR 的职称名称 |
| HIS 职称字典 | `PORTAL_USER.PORTAL_SYS_DICT` | `TYPE_CODE` | 固定过滤 `EmployeeTitle` |
| JHEMR 用户表 | `jhemr.users` | `user_id` | 与 HIS `EMPLCODE` 匹配 |
| JHEMR 用户表 | `jhemr.users` | `hospital_no` | 固定限定生产租户 `49557032X` |
| JHEMR 用户表 | `jhemr.users` | `education_title` | 职称目标字段，活库长度 21 |

唯一映射：

```text
FXHIS.SYS_EMPLOYEE.EMPLCODE
    = jhemr.users.user_id

FXHIS.SYS_EMPLOYEE.LEVLCODE
    = PORTAL_USER.PORTAL_SYS_DICT.DICT_CODE

PORTAL_USER.PORTAL_SYS_DICT.DICT_NAME
    -> jhemr.users.education_title
```

### 3.2 覆盖规则

1. JHEMR 已有非空职称但与 HIS 字典名称不同：必须覆盖。
2. JHEMR 已有值且与 HIS 完全一致：幂等跳过，不做无意义写入。
3. HIS `LEVLCODE` 为空、字典缺失或 `DICT_NAME` 为空：只统计，不把 JHEMR 现有值清空。
4. JHEMR 不存在对应 `user_id`：只统计 `missing_target_users`，不新建账号。
5. 只处理 `hospital_no='49557032X'`；不得跨租户更新。
6. 源职称长度超过目标列长度：全批失败关闭，禁止截断。
7. 字典或人员存在歧义时失败关闭，禁止“取第一条”或 `MAX(DICT_NAME)` 猜测。

### 3.3 唯一性规则

- 相同 `DICT_CODE` 对应多个不同非空 `DICT_NAME`：`source_dictionary_ambiguous`，停止。
- 相同 `EMPLCODE` 对应多个不同非空 `LEVLCODE`：`source_employee_title_ambiguous`，停止。
- 同一租户 `jhemr.users.user_id` 多行：`target_user_id_ambiguous`，停止。
- 相同代码/人员的重复行只有在规范化值完全相同时才允许去重。

## 4. HIS 只读查询口径

实际脚本将字典和人员拆成独立查询，避免 JOIN 重复导致静默覆盖。禁止使用用户原始示例中的 `a.*`，必须显式投影字段。

```sql
SELECT DICT_CODE, DICT_NAME
FROM PORTAL_USER.PORTAL_SYS_DICT
WHERE TYPE_CODE = 'EmployeeTitle'
  AND ROWNUM <= :max_rows
```

```sql
SELECT COUNT(*) AS ROW_COUNT
FROM FXHIS.SYS_EMPLOYEE
WHERE EMPLCODE IS NOT NULL
```

```sql
SELECT EMPLCODE, LEVLCODE
FROM FXHIS.SYS_EMPLOYEE
WHERE EMPLCODE IS NOT NULL
  AND ROWNUM <= :max_rows
```

规则：

- Oracle 11g 使用 `ROWNUM`，不得使用 `FETCH FIRST`。
- 当前普通读取上限为 10000 行；若人员计数超过上限，脚本直接失败关闭。
- 不查询姓名、身份证、电话或其他人员明细。
- HIS 连接必须使用已登记的只读连接器和受控凭据文件；不得读取或输出凭据内容。

## 5. JHEMR 写入契约

唯一允许的目标 DML 形态为参数化单列更新：

```sql
UPDATE jhemr.users
SET education_title = %s
WHERE user_id = %s
  AND hospital_no = %s
```

每行写入前后要求：

1. 在同一事务内按 `user_id + hospital_no` 读取并锁定目标行；
2. 当前旧值必须与备份中的旧值一致，否则 `target_changed_after_backup`；
3. 单行更新影响数必须等于 1；
4. 提交前回读 `education_title` 必须与新值一致；
5. 任意一行失败，整批 JHEMR 事务回滚；
6. 不执行 `GRANT/REVOKE`，不修改账号、密码、姓名、科室、角色、签名等字段。

## 6. 当前代码入口

| 文件 | 当前作用 | 关键入口 |
|---|---|---|
| `backend/scripts/sync_jhemr_education_titles.py` | 可复用的一次性 dry-run/备份/apply 工具 | `_build_source_map`、`_write_backup`、`_create_planned_audit`、`_apply_changes`、`main` |
| `backend/app/services/his_identity_sync.py` | 日常 HIS 人员采集时读取 EmployeeTitle 字典，写入平台 `IdentityPerson.job_title` | `EMPLOYEE_TITLE_DICT_TABLE`、`_build_employee_title_map`、`_collect`、`_build_plan` |
| `backend/app/services/jhemr_identity_adapter.py` | 已有账号被身份同步处理时，允许覆盖不同的 `education_title` 并在提交前回读 | `align_existing_user` |
| `backend/app/services/identity_title_sync.py` | 每日全量限量比较、唯一性/长度/权限门禁、整批 planned 审计、JHEMR 单事务更新和完成态审计恢复 | `sync_jhemr_education_titles_daily`、`reconcile_pending_title_actions` |
| `backend/scripts/run_identity_modified_nightly.py` | 将职称同步作为 `jhemr_education_title_sync` 必需子任务并入 overall、退出码和脱敏摘要 | `main` |
| `backend/app/services/identity_sync_audit.py` / `identity_sync_status.py` | 通用子任务 action、计数守恒、告警和三子任务状态聚合 | `create_action`、`finalize_run`、`aggregate_overall_status` |
| `backend/tests/identity_title_sync/` | 无测试库环境可执行的纯逻辑专项测试 | 歧义、覆盖、备份绑定、适配器回读 |
| `backend/tests/test_his_identity_sync.py` | HIS 采集与平台主档集成测试 | 字典采集、映射计数、审计 |
| `backend/tests/test_identity_sync.py` | JHEMR 适配器集成测试 | 非空职称覆盖与回读 |

本节记录 2026-08-11 当时的本地文件状态；后续已发布至生产。当前准确运行状态见 §12.6。后续 AI 仍必须先执行 `git status --short` 并保留其他协作者改动。

## 7. 2026-08-10 正式执行证据

### 7.1 写入前 dry-run

| 指标 | 数量 |
|---|---:|
| HIS EmployeeTitle 字典行 | 60 |
| 唯一字典代码 | 60 |
| HIS SYS_EMPLOYEE 行/唯一人员 | 2521 / 2521 |
| 重复人员行 | 0 |
| 有有效职称映射人员 | 2089 |
| 无有效职称映射人员 | 432 |
| JHEMR 当前租户用户 | 3950 |
| HIS 与 JHEMR 匹配 | 2043 |
| 写入前已一致 | 1726 |
| 需要覆盖 | 317 |
| JHEMR 缺失 | 46 |
| 超长职称 | 0 |

### 7.2 写入与审计结果

- JHEMR 更新 317 行，单事务提交，逐行影响数为 1。
- 提交前全部回读一致。
- 平台审计 run id：`title-7bfc3814f2e0434dbe490462ef0123c1`。
- subtask：`jhemr_education_title_sync`，状态 `success`，成功 317，失败 0。
- `asset_identity_sync_actions`：317 条 `education_title_overwrite`，状态全部 `executed`。
- action 只存稳定 HMAC 指纹和字段摘要，不存姓名、完整工号或具体职称。

### 7.3 提交后二次对账

| 指标 | 结果 |
|---|---:|
| 匹配用户 | 2043 |
| 已一致 | 2043 |
| 待变更 | 0 |
| 目标缺失 | 46 |

### 7.4 回滚备份

- 宿主机：`/opt/data-asset/backups/jhemr_education_title_backup_20260810.json`
- 权限：`600`
- SHA-256：`d17df0f8671eb1f3e8798dd6512556d90ec8999721d7ea2980c07d30edc523f0`
- 文件包含回滚所需的目标键、旧值和新值，属于敏感运维数据；禁止查看、输出、复制到仓库或发送给 AI。
- 容器和宿主机 `/tmp` 临时副本已清理，受限备份保留。

## 8. 后续再次同步的标准流程

### S0 授权和环境门禁

每次正式 apply 前重新确认：

1. 用户明确授权本次 JHEMR `users.education_title` 写入；历史授权不得自动外推到其他字段或其他目标库。
2. HIS 仍为只读账号，业务源写入必须为 0。
3. JHEMR 专用账号具有 `user_id/hospital_no/education_title` 的 SELECT 和 `education_title` 的 UPDATE 权限。
4. 不执行或建议直接执行 `GRANT/REVOKE`；权限不足时只输出最小权限需求并停止。
5. `APP_TEST_DB_URL` 缺失时完整测试记录 `BLOCKED`，不得使用生产平台库替代。
6. 先检查脚本、当前代码与生产镜像差异，不假定 2026-08-10 的临时脚本仍在容器内。

### S1 本地静态检查和专项测试

```powershell
cd F:\python\数据资产\backend

.\.venv\Scripts\python.exe -m py_compile `
  app/services/his_identity_sync.py `
  app/services/jhemr_identity_adapter.py `
  scripts/sync_jhemr_education_titles.py

.\.venv\Scripts\python.exe -m pytest tests/identity_title_sync/ -q
```

HIS SQL 还必须使用 `.agents/skills/hisuser-readonly-sql/scripts/validate_his_sql.py` 静态校验。当前脚本常量可通过 Python 导入校验，不需要把查询结果保存到仓库。

完整后端测试仍按仓库标准执行；没有隔离测试库时只能写 `BLOCKED`：

```powershell
cd F:\python\数据资产\backend
.\.venv\Scripts\python.exe -m pytest tests/ -q
```

### S2 将脚本传入生产容器

脚本若尚未随应用镜像发布，可使用不含凭据的临时副本。时间戳必须唯一，避免覆盖他人文件：

```powershell
$SyncStamp = Get-Date -Format 'yyyyMMddHHmmss'
$RemoteScript = "/tmp/sync_jhemr_education_titles_$SyncStamp.py"

scp -F "F:\python\数据资产\.ssh\config_ai" -o BatchMode=yes `
  "F:\python\数据资产\backend\scripts\sync_jhemr_education_titles.py" `
  "data-asset-83:$RemoteScript"

ssh -F "F:\python\数据资产\.ssh\config_ai" -o BatchMode=yes `
  data-asset-83 "docker cp $RemoteScript data-asset-api:$RemoteScript"
```

不得复制凭据、人员数据或回滚备份到本地仓库。

### S3 dry-run

```powershell
ssh -F "F:\python\数据资产\.ssh\config_ai" -o BatchMode=yes `
  data-asset-83 `
  "docker exec -e PYTHONPATH=/app -e APP_IDENTITY_SYNC_DIRECT_CONNECTION=true `
   data-asset-api python $RemoteScript"
```

dry-run 标准输出只能包含：

- 源/目标/匹配/一致/待变更/缺失/超长数量；
- 权限布尔值；
- 最多 3 个 HMAC 短指纹；
- 脱敏错误类别。

出现以下任一情况必须停止：

- 字典或人员歧义；
- 源或目标行数触发上限；
- 目标重复用户；
- 字段不存在或长度不足；
- 缺少 UPDATE 列权限；
- 输出出现姓名、完整工号、具体职称明细、密码、Token 或连接串；
- 变更量异常且原因未解释。

### S4 生成并固化回滚备份

```powershell
$BackupName = "jhemr_education_title_backup_$SyncStamp.json"

$PrepareOutput = ssh -F "F:\python\数据资产\.ssh\config_ai" -o BatchMode=yes `
  data-asset-83 `
  "docker exec -e PYTHONPATH=/app -e APP_IDENTITY_SYNC_DIRECT_CONNECTION=true `
   data-asset-api python $RemoteScript --prepare-backup /tmp/$BackupName"

$PrepareJson = $PrepareOutput | Where-Object { $_ -match '^\{' } | ConvertFrom-Json
$BackupSha = $PrepareJson.backup_sha256
```

然后先把备份固化到宿主机，再允许 apply：

```powershell
ssh -F "F:\python\数据资产\.ssh\config_ai" -o BatchMode=yes `
  data-asset-83 `
  "install -d -m 700 /opt/data-asset/backups && `
   docker cp data-asset-api:/tmp/$BackupName /opt/data-asset/backups/$BackupName >/dev/null && `
   chmod 600 /opt/data-asset/backups/$BackupName && `
   sha256sum /opt/data-asset/backups/$BackupName"
```

宿主机摘要必须与 `$BackupSha` 完全一致。只报告文件名、权限、大小和摘要，不查看或打印文件内容。

### S5 apply

```powershell
ssh -F "F:\python\数据资产\.ssh\config_ai" -o BatchMode=yes `
  data-asset-83 `
  "docker exec -e PYTHONPATH=/app -e APP_IDENTITY_SYNC_DIRECT_CONNECTION=true `
   data-asset-api python $RemoteScript `
   --apply `
   --backup-file /tmp/$BackupName `
   --backup-sha256 $BackupSha"
```

apply 前脚本会重新执行源/目标预检，并要求当前计划与备份逐项完全一致。预检后数据发生变化时必须失败，禁止使用旧备份强行继续。

### S6 提交后二次对账

重新执行 S3 dry-run。完成判定：

- `changed_users=0`；
- `already_equal=matched_target_users`；
- 新 run 为 `success`；
- subtask 成功数等于本次变更数；
- action `executed` 数等于本次变更数；
- 无新增 failed/partial_success/回读不一致告警。

平台只读审计至少核对：

```sql
SELECT run_id, status, candidates_total, success_count, failed_count
FROM asset.asset_identity_scheduler_runs
WHERE run_id = :run_id
```

```sql
SELECT subtask_code, status, planned_count, succeeded_count, failed_count
FROM asset.asset_identity_sync_subtasks
WHERE run_id = :run_id
```

```sql
SELECT status, COUNT(*) AS action_count
FROM asset.asset_identity_sync_actions
WHERE batch_id = :run_id
GROUP BY status
```

不得查询或输出备份中的目标键和职称内容。

### S7 临时文件清理

确认宿主机受限备份存在且摘要正确后，只清理本次精确命名的 `/tmp` 文件：

```powershell
ssh -F "F:\python\数据资产\.ssh\config_ai" -o BatchMode=yes `
  data-asset-83 `
  "test -s /opt/data-asset/backups/$BackupName && `
   docker exec data-asset-api rm -f /tmp/$BackupName $RemoteScript && `
   rm -f $RemoteScript"
```

禁止通配或递归删除 `/tmp`、备份目录、仓库或发布目录。

## 9. 失败分类与处理

| 错误类别 | 含义 | 处理 |
|---|---|---|
| `source_dictionary_ambiguous` | 同一字典代码多个名称 | 停止，HIS 只读核对字典；不得任选一条 |
| `source_employee_title_ambiguous` | 同一人员多个职称代码 | 停止，HIS 只读核对人员主数据 |
| `source_row_limit_exceeded` | 源人数超脚本上限 | 停止，复核范围和限量策略，不直接放大上限 |
| `source_count_mismatch` | 计数与读取不守恒 | 停止，检查并发变化、截断或连接问题 |
| `target_user_id_ambiguous` | 同租户用户键不唯一 | 停止，禁止批量更新 |
| `target_update_privilege_missing` | 专用账号无列级 UPDATE | 停止，由 DBA 单独处理最小权限 |
| `source_title_too_long` | 源职称超过目标长度 | 停止，禁止截断或修改目标结构 |
| `backup_digest_mismatch` | 备份被修改或传输损坏 | 停止，重新 dry-run 和备份 |
| `backup_no_longer_matches_current_plan` | 源/目标已变化 | 停止，生成新备份 |
| `target_changed_after_backup` | 写入前目标旧值变化 | 整批回滚，重新对账 |
| `target_update_rowcount` | 单行影响数不为 1 | 整批回滚，检查租户键/重复行/并发 |
| `target_readback_mismatch` | 更新后回读不一致 | 整批回滚并告警 |
| planned audit 写失败 | 无法在写前证明动作计划 | 写前失败关闭；不得绕过审计继续写 JHEMR |
| completion audit 写失败 | JHEMR 可能已经提交，但平台完成态未落库 | 状态标记未知；先执行目标只读回读和全量 dry-run，再修复/补记审计；禁止直接重跑或声称整批回滚 |

## 10. 回滚规则

1. 当前脚本自动处理“提交前失败”的事务回滚。
2. 已提交批次如需业务回滚，必须由用户重新明确授权，历史 apply 授权不能推定为 rollback 授权。
3. 回滚输入只能使用受限备份，并先核对 SHA-256、租户、当前值仍等于备份新值。
4. 回滚仅允许参数化恢复 `education_title` 旧值，逐行影响数为 1、提交前回读并写新的 run/subtask/action 审计。
5. 任一当前值已被后续人工或自动任务修改时，整批失败关闭，不覆盖新变化。
6. 禁止通过直接查看 JSON、拼接 SQL、命令行传人员键或用管理员账号无审计回滚。

当前仓库尚未提供 `--rollback` 自动入口。需要回滚时先补隔离测试和受控实现，不得临时用 `psql`/数据库客户端拼接批量 UPDATE。

## 11. 测试与安全验收

2026-08-10 已执行：

| 验收 | 结果 |
|---|---|
| Python 编译 | PASS |
| HIS 三条 SQL 静态只读检查 | PASS |
| `pytest tests/identity_title_sync/ -q` | PASS，17 passed（含每日子任务、整批回滚、审计恢复边界） |
| `git diff --check` | PASS，仅既有 CRLF 提示 |
| 生产 dry-run | PASS |
| 备份摘要/权限 | PASS |
| 生产 apply | PASS，317 更新 |
| 事务内回读 | PASS |
| 提交后二次 dry-run | PASS，待变更 0 |
| 平台 run/subtask/action 对账 | PASS，317 actions executed |
| 完整 `pytest tests/ -q` | BLOCKED，无隔离 `APP_TEST_DB_URL` |

安全确认：

- HIS DML/DDL/锁：0；
- JHEMR 写入：仅 `users.education_title` 317 行；
- 平台写入：仅本批 run/subtask/action 审计；
- `GRANT/REVOKE`：0；
- 生产 runner：未触发；
- cron/systemd：未修改；
- 应用发布/服务器升级：未执行；
- 姓名、完整工号、具体职称、密码、Token、连接串输出：0。

## 12. 并入每日人员同步的后续方案

一次性工具已经解决当时数据；2026-08-11 完成下述每日化本地实现和专项测试，随后已随应用发布并接入既有唯一 host cron。历史设计和门禁继续保留，当前运行证据见 §12.6；不得据此重复一次性同步或新增第二套调度。

### 12.1 推荐运行方式

HIS 当前人员约 2521、职称字典约 60 行，均不是巨表。推荐每日主任务采集后执行一次全量只读比较：

1. 全量限量读取 `EMPLCODE + LEVLCODE`；
2. 全量限量读取 EmployeeTitle 字典；
3. 与 JHEMR 当前租户 `user_id + education_title` 比较；
4. 只为不一致且有唯一有效源职称的账号生成更新动作；
5. 已一致跳过、无映射不清空、目标缺失只告警。

采用每日小表全量比较可以同时捕获：

- 人员 `LEVLCODE` 变化；
- 字典 `DICT_NAME` 变化但人员 `MODIFIEDTIME` 未变化；
- 目标职称被人工改动后的偏差。

不能只依赖 `SYS_EMPLOYEE.MODIFIEDTIME` 水位，否则字典名称单独修改时会漏同步。

### 12.2 需要增加的正式子任务

- subtask code：`jhemr_education_title_sync`；
- 必需子任务，不得改成 optional 来制造 overall success；
- 主账号成功但职称子任务失败时，overall 必须为 `partial_success`，runner 退出码 2；
- 职称子任务未捕获异常或配置错误时，overall 必须为 `failed/misconfigured`，退出码 1；
- lock held 只能为 `skipped`；
- 每个实际目标更新必须写 `asset_identity_sync_actions`；
- 目标提交与平台完成态审计之间必须有可恢复的 `target_committed_pending_audit` 或等价状态及 reconciliation；完成态审计失败时先只读确认目标事实，不得直接重跑；
- 日志只允许计数、错误类别和最多 3 个 HMAC 短指纹。

### 12.3 需要补充的测试

1. 已有非空职称被覆盖；
2. 相同值幂等跳过；
3. 空/缺失源职称不清空目标；
4. 字典同码多名称失败关闭；
5. 人员同工号多职称代码失败关闭；
6. 同租户目标重复失败关闭；
7. 目标缺失只计数不建号；
8. 超长职称失败关闭；
9. 权限失败时 partial_success/退出码 2；
10. planned 审计写失败时禁止目标写，completion 审计失败时保留“目标可能已提交”状态并完成只读对账/审计恢复；
11. 更新行数异常、回读失败时事务回滚；
12. 字典名称变化但人员 MODIFIEDTIME 不变仍可同步；
13. 快速重跑无动作、动作审计守恒；
14. 日志和 API 不出现人员键或职称明细。

### 12.4 发布门禁

1. 先完成隔离 `APP_TEST_DB_URL` 全量测试。
2. 生产发布前保留平台库和当前镜像回滚点。
3. 发布后先执行 dry-run，确认待变更数量符合预期。
4. 第一次纳入每日任务需用户明确授权应用发布和调度行为；不得从 2026-08-10 一次性写入授权推定。
5. 不修改 HIS 权限；JHEMR 仅保留 `education_title` 列级 UPDATE。
6. 连续观察至少 3 个夜间窗口，确认 overall/subtask/action/告警守恒。

### 12.5 2026-08-11 本地实现结果

- `jhemr_education_title_sync` 已作为必需子任务接入每日 runner；主任务成功而职称失败时 overall 为 `partial_success`、退出码 2。
- HIS 仍仅执行 3 条显式字段、限量 `SELECT`；JHEMR 仅允许更新当前租户 `users.education_title`。
- 所有差异先写 planned action，随后在一个 JHEMR 事务内逐行加锁、核对旧值、更新、回读；任一行失败整批回滚。
- 完成态审计失败不重复写目标；保留待恢复计数，下一轮使用账号 HMAC 与目标值 HMAC 只读确认后补记 executed，无法确认则失败关闭。
- 专项测试 `17 passed`、Python 编译通过；完整后端 pytest 因当前会话未配置合法隔离 `APP_TEST_DB_URL` 记为 BLOCKED。
- 生产镜像发布、cron/systemd 修改、生产 runner、JHEMR/平台生产写入均 `NOT EXECUTED`。

### 12.6 2026-08-13 生产状态只读复核

- 当前生产后端镜像为 `data-asset:126p5-20260811223311`，人员任务 provider 仍为唯一 `host_cron`。
- 2026-08-12 夜窗 `jhemr_education_title_sync` 状态为 success，planned=0、failed=0、按无需变更规则幂等跳过 2,090；未产生职称目标更新。
- 同夜主账号 2/2、签名新增成功 1，主账号与签名水位均 committed；修复后连续夜窗当前为 2/3，第三夜只读观察统一纳入 130。
- 本次仅只读查询任务/审计状态；没有重复一次性补跑，没有修改 cron、权限或开关，没有执行额外业务源库/目标库写入。

## 13. 给后续 AI 的直接接手提示词

```text
你现在负责 F:\python\数据资产 仓库的 HIS 职称同步 JHEMR 复核或再次执行。

必须先完整阅读：
- AGENTS.md
- 开发起步包/README.md
- 开发起步包/55_系统未完成事项统一执行计划.md
- 开发起步包/124_HIS职称同步JHEMR执行与复用说明.md
- .agents/skills/hisuser-readonly-sql/SKILL.md
- 如涉及每日任务，再读 122、124 和两份 125；103/107 仅在 `_archive/` 作历史追溯。

先执行目录自检和 git status --short。共享工作区中的既有改动属于用户或其他协作者，禁止 reset、checkout、删除或覆盖无关改动。

业务契约固定为：
FXHIS.SYS_EMPLOYEE.EMPLCODE = jhemr.users.user_id；
FXHIS.SYS_EMPLOYEE.LEVLCODE = PORTAL_USER.PORTAL_SYS_DICT.DICT_CODE；
TYPE_CODE='EmployeeTitle' 的 DICT_NAME 写入 jhemr.users.education_title；
限定 hospital_no='49557032X'；目标已有不同值也覆盖；相同值幂等跳过；无有效源职称不得清空目标。

HIS 始终只允许显式字段、限量 SELECT，禁止 DML/DDL/锁。JHEMR 只允许在用户明确授权后更新 users.education_title，不得修改其他字段、执行 GRANT/REVOKE、触发全量人员 runner 或输出姓名、完整工号、具体职称、凭据和连接串。

复用 backend/scripts/sync_jhemr_education_titles.py，严格按 124 的 S0-S7 执行：静态检查和测试 → dry-run → 生成摘要绑定备份 → 宿主机 600 权限固化和 SHA 校验 → apply → 提交后二次 dry-run → run/subtask/action 对账 → 精确清理临时文件。

以下情况必须失败关闭：字典歧义、人员职称歧义、目标同租户重复、行数截断、字段超长、权限不足、备份摘要不一致、备份与当前计划不一致、单行影响数不为1、目标并发变化、回读不一致、动作审计写失败。

没有隔离 APP_TEST_DB_URL 时，完整 pytest 和迁移验收写 BLOCKED，禁止用生产平台库替代。每阶段报告命令、真实结果、PASS/FAIL/BLOCKED、HIS写入0、JHEMR实际写入数、平台审计数和未执行事项。

如果只是再次一次性同步，不得擅自发布应用或修改 cron/systemd。如果目标是并入每日同步，先按 124 第12节补正式子任务、状态/退出码/审计/告警和隔离测试，获得用户单独授权后再发布与观察。
```

## 14. 后续维护要求

1. 每次执行后在本文件追加日期、dry-run 数量、实际更新数、run id、回读、备份摘要、测试和未执行项。
2. 同步更新 `开发起步包/README.md` 目录记录和 `55` 号末尾执行日志。
3. 若脚本被正式纳入每日任务，将本文件状态更新为“每日自动职称子任务已发布”，并记录镜像、部署时间、首三次夜间运行结果和回滚点。
4. 不在本文新增任何人员明细或凭据。
