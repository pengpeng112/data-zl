> 类别：复核与整改实施报告
> 状态：Phase C 独立核查 + 修订完成（2026-08-03；601 项测试通过、迁移往返通过、8.83 已升级；Phase D 前置阻断见 §7）

# 110 HIS 人员同步 CDMS/JHEMR 修复代码独立核查、修订与 8.83 升级报告

## 0. 结论摘要

另一 AI 按 107 号计划完成的 Phase B 修复开发，经本会话逐项独立核查（代码全读 + 活库只读核实 + 测试复跑），**共确认 14 项缺陷，全部已在平台侧修订并回归验证**；修订后端代码、迁移与测试已升级至 10.10.8.83 生产容器，平台库迁移至 `f8a9b0c1d2e3`，夜间开关与全部写开关保持关闭，业务源库（HIS/CDMS/JHEMR）写入为 0。

放行结论（沿用 104/107 四阶段口径）：

| 阶段 | 结论 | 说明 |
|---|---|---|
| 允许开发 | 允许 | 修订后代码与测试齐备 |
| dry-run | 允许 | 编排器当前仅平台侧登记 `pending_reconcile`，不触达业务库 |
| 灰度写入（Phase D 验收） | 有条件允许 | §7 前置项全部完成后，由 `asset_action_executors` 白名单服务在一次性变更窗口执行 1 医 1 护 × 2 目标验收 |
| 正式定时（nightly） | 暂不允许 | 须 Phase D 四方比对通过且连续 3 个夜间批次稳定后，由运维显式开启 |

## 1. 核查范围

- 代码：两笔新迁移、`identity_classification`、`identity_sync_orchestrator`、`identity_nightly_scheduler`、`identity_sync_executor_bridge`、`identity_four_way_diff`、`identity_alert`、`identity_hmac`、`identity_password`、`cdms_identity_adapter`、`jhemr_identity_adapter`、`models/identity_sync`、`api/v1/identity_sync`、三个测试文件及 config/main 改动。
- 文档：103/104/105/106/107，冲突优先级按 107 §0.2（107 > 106 > 104 > 103 > 105）。
- 活库只读核实（2026-08-03，8.83 容器内受控只读凭据，全部 SELECT / information_schema）：HIS STAFF_DICT JOB/TITLE 值域、STAFF_GROUP_DICT 组类别与命名、CDMS T_MSS_EMP_DICT / T_MSS_AUTHMAPPING 列与约束、按角色的模板众数、JHEMR users 与三张控制表列清单、控制模式高频组合。

## 2. 活库核实新证据（修订依据）

### 2.1 HIS 值域（COMM.STAFF_DICT，4264 行）

- JOB 分布：护理 816、医生 734、护士 718、临床 538、NULL 262、医技 238、经济 237、行政管理 216、技师 94、药剂 84、影像诊断 37、检验 29、急救 25、润华药学 22、医疗 21、医助 11、中医临床 5 等。
- TITLE 分布：护士 1193、主任医师 478、医师 377、副主任医师 231、护师 188、主治医师 153、技师 88、技士 77、主管护师 79、药士 35、药师 32、主管药师 28、科主任 10 等。
- `STAFF_GROUP_DICT.GROUP_CLASS` 实际值：门诊医生 235、病区医生 194、病区护士 56、检查医生 25、药品组 21、物资管理 13、手术医生 10、行政管理 6、麻醉医生 3、收款员 2、经济核算组一 4。**"住院医师"/"病房护士"字面值在活库不存在**；组名（GROUP_NAME）为科室/护理单元名称，GROUP_CODE 即科室码。107 §5.4 的白名单按语义映射为：医师附加科室只接 `病区医生` 组、护士只接 `病区护士` 组、药师仅主科室。

### 2.2 CDMS 真实结构（Oracle 11.2.0.1）

- `T_MSS_EMP_DICT`：PK=FLOGINNAME（唯一 NOT NULL 列）；**无 FDEPTID 列**，科室列为 `FDEPT`；FUSERTYPE 为 NUMBER。
- `T_MSS_AUTHMAPPING`：列 = FAUTHMAPPINGID(PK, 32 位 hex)、FID(=登录名)、FAUTHORITYID(=授权值)、FTYPE、FDATE、FUSER(=登录名)、FST、FUPDATEUSER、FUPDATE、FPRIVIEGETYPE(=FTYPE)。**无 FLOGINNAME/FVALUE 列**。
- 模板众数（以持有医疗质控 904 人 / 护理质控 1036 人的现有账号为准）：FSYSID='2'、FUSERTYPE=0、FUSERSTATE='0'；FTYPE=3 众数 '100005'、FTYPE=5 全量 'A00001'、FTYPE=10 众数 **'0'**（2009/2012，'1' 为少数派 126/128）。
- FPWD 密文复用策略：算法未知（104 E8），新账号初始密码复用全院默认密文（1715/1727 占比），密文仅在内存中传递，不落日志/审计。

### 2.3 JHEMR 真实结构（Vastbase）

- `jhemr.users` 有 `user_dept` 列（可空），account_status/is_sm/user_type 为 numeric。
- `users_control_mode`：有 last_modify_date、last_modify_user_id。
- **`users_sublogin`、`users_subsign` 只有 last_modify_time**，无 last_modify_date / last_modify_user_id 列。
- 控制模式高频组合为 ('2,4,8','0,2,4,8','2,2,2')×2121、('0','0','2')×1486；本期按 107 §2.2 用户明确指定的 '0,2,4' 默认（用户已裁决，非众数复制）。
- hospital_no 生产租户 '49557032X'，列默认 '1110002' 为错误租户，必须显式写入（适配器已满足）。

## 3. 已确认缺陷与修订清单（14 项，按严重度）

### P0（授权/数据正确性，若启用将造成错误授权或必然失败）

| # | 缺陷 | 位置 | 修订 |
|---|---|---|---|
| C1 | 分类器含单字"医"关键词：JOB=医技（238 名技师）、影像诊断技师（14 人）被判 doctor，将获医师角色灾难性误授权 | identity_classification.py | 按活库值域重写：TITLE 资格优先、精确 JOB 集合、技师类职称显式阻断、影像诊断/急救无临床职称即不同步；补 6 项回归测试 |
| C2 | CDMS AUTHMAPPING SQL 使用不存在列 FLOGINNAME/FVALUE，EMP 插入使用不存在列 FDEPTID——对活库执行必 ORA-00904 | cdms_identity_adapter.py | 全部 SQL 按活库真实列重写（FUSER/FAUTHORITYID/FAUTHMAPPINGID/FPRIVIEGETYPE/FDEPT），行形状对齐活库样例；补列名回归测试 |
| C3 | CDMS 模板常量错误：FSYSID='1'（活库众数 '2'，医疗 904/护理 1036 一致）、FTYPE=10 写 '1'（活库众数 '0'） | cdms_identity_adapter.py | 改为活库众数 FSYSID='2'、FTYPE=10→'0' |
| C4 | 桥接 CDMS：读取不存在的键 `most_common_fpwd` 导致永远失败；角色码硬编码占位符 "medical_qc"/"nursing_qc" 而非真实角色 GUID；构造适配器缺 `oracle_client_lib` 必 TypeError；DSN 误用远端地址绕过隧道 | identity_sync_executor_bridge.py / cdms_identity_adapter.py | 角色码改从 asset_identity_role_mappings 读取；新增 `fetch_mode_fpwd_ciphertext()`（密文仅内存）；补 oracle_client_lib；DSN 改 127.0.0.1:本地端口 |
| C5 | 无任何代码填充 IdentityPerson.classification/source_create_date——`classify_person` 只在测试中被调用，管道候选永远为空（功能空转） | 全局 | 新建 `identity_classification_preflight.py`：从平台库人员主档+来源 raw 分类并回写（含分类记录表、conflict_flag），夜间管道接入；采集器补采 CREATE_DATE/JOB/TITLE 落主档 |
| C6 | JHEMR 建号未写 `users.user_dept`（107 §5.4 要求=HIS 主科室）；无密码时仍建号产生半账号 | jhemr_identity_adapter.py | users INSERT 补 user_dept/create_date；密码写入未启用或无 secret 时失败关闭（新增 `identity_jhemr_password_write_enabled=false` 开关，107 §5.2） |
| C7 | sublogin/subsign 插入 last_modify_date/last_modify_user_id——活库无此两列，必报错 | jhemr_identity_adapter.py | 只写 last_modify_time，时间改用目标库 CURRENT_TIMESTAMP（107 §2.1） |
| C8 | 主科室取 `list(set(...))[0]`——set 序不确定，可能把附加科室当主科室同步；`is_valid_group_class` 白名单值（住院医师/病房护士）在活库不存在且从未接线 | identity_sync_orchestrator.py / identity_classification.py | 主科室只取 is_primary=True 关系（确定性排序）；附加科室仅来自 STAFF_VS_GROUP 且 GROUP_CLASS ∈ 分类白名单（病区医生/病区护士），药师仅主科室；新增 group_class 列（迁移 f8a9b0c1d2e3）并由两个采集器落库 |

### P1（安全/可靠性）

| # | 缺陷 | 位置 | 修订 |
|---|---|---|---|
| C9 | HMAC 密钥不可用时静默回退无盐 sha256——工号低熵可枚举，违反不可逆指纹设计 | identity_sync_orchestrator.py | 失败关闭：抛错阻断整批并告警；补无密钥必失败回归测试 |
| C10 | 熔断统计失真：new 恒等于候选数、change_ratio 恒 1.0 > 0.3，每晚必然误熔断；watermark/行数守恒两维度空转 | identity_sync_orchestrator.py | 新增 `_compute_change_stats`：按 managed relation 区分 new/update/deactivate、比例分母改为合格人员全集 scope、watermark 间隔接入平台水位表；行数守恒维度保留 0 并在报告标注未接线（需采集阶段供数） |
| C11 | TIMESTAMP(timezone=True) 列在 PG 返回 tz-aware，`_now()` 返回 naive，第二次取锁比较必 TypeError（SQLite 测试掩盖） | identity_sync_orchestrator.py | `_now()` 改 tz-aware UTC，比较前 `_as_aware` 归一；补 naive/aware 两种锁回归测试 |
| C12 | sync_executor identity_his 路径 dry_run 硬编码 False（104 R14） | sync_executor.py | run_sync 增加 dry_run 形参并透传，审计仍留痕 |
| C13 | 迁移 f1a2b3c4d5e6 docstring 头部 revision 信息过期（写 a3b4/z2f3，链本身完好） | alembic 迁移 | 修正 docstring |
| C14 | 新增迁移初版 revision id `b4c5d6e7f8a9` 与既有迁移撞号（双 head） | alembic 迁移 | 改号 `f8a9b0c1d2e3`，heads 单一，upgrade→downgrade→upgrade 往返通过 |

## 4. 验证结果

- 纯逻辑与集成测试：`test_identity_sync.py` + `test_identity_nightly_sync.py` + `test_identity_four_way_diff.py` = 160 passed；HIS 身份相关 4 套件 32 passed；**后端全量 601 passed / 0 failed**（2026-08-03，APP_TEST_DB_URL 指向 8.83 data_asset_test）。
- 迁移：测试库与生产库均 upgrade→downgrade→upgrade 往返通过，单一 head `f8a9b0c1d2e3`。
- 新增回归覆盖：医技/技师误判、NULL CREATE_DATE 隔离、组类白名单（含 107 字面值不存在断言）、CDMS 真实列名、sublogin/subsign 列、密码失败关闭、主科室确定性、药师仅主科室、预检分类/隔离/记录、new/update 拆分、比例分母、HMAC 失败关闭、时区锁。

## 5. 8.83 升级记录（2026-08-03）

1. 平台库备份：`/opt/data-asset/backups/data_asset_pre_identity110_20260803090434.sql.gz`（6.1MB）；容器内旧代码备份 `/tmp/app_backup_identity110`。
2. 代码热更：`docker cp` 同步 app/alembic/alembic.ini 至 data-asset-api 容器 `/app`；清理 `__pycache__`；`import app.main` 通过。
3. gmssl（纯 Python，107 §5.2 离线依赖）从本地 venv 拷贝入容器 site-packages，`import gmssl` 通过。
4. 迁移：生产平台库 e7f8a9b0c1d2 → **f8a9b0c1d2e3**（此前另一 AI 未升级生产，本次一并补升 f1a2b3c4d5e6 调度表）。
5. 重启容器，`/health` 正常；日志确认 `Identity nightly sync is disabled`；openapi 含 7 条 identity-sync 路由。
6. 开关核验：未设置任何 APP_IDENTITY_* 环境变量 → identity_sync_enabled / nightly / password_write 全部默认 false；角色映射种子 6 行就位（CDMS 真实角色 GUID、JHEMR 001/002）。
7. **业务源库写入 0**：全程仅 SELECT/information_schema 只读核实；无 GRANT/REVOKE；无生产账号创建；凭据、密码、密文未写入代码/文档/日志/Git。

## 6. 与 107 复核清单（§11）逐项对照

| 项 | 结论 | 证据 |
|---|---|---|
| 1 第二受控账号密码交叉验证 | 不通过（保持阻断） | gmssl 已入镜像但 password_write_enabled=false，待人工双账号验证后开启 |
| 2 三控制表结构来自活库 | 通过 | §2.3 列清单，sublogin/subsign 列已按活库修正 |
| 3 '0,2,4' 为用户指定默认而非伪称众数 | 通过 | §2.3 记录真实众数与用户裁决 |
| 4 护理错误 001 删除证据 | 不适用（日常任务无 DELETE） | 一次性纠错流程未启用 |
| 5 主科室同时更新 users.user_dept 与唯一默认关系 | 通过（代码） | create_user_full 已写 user_dept + default_dept_flag 唯一回读 |
| 6 新账号显式列白名单、不复制个人字段 | 通过 | users INSERT 13 列白名单 |
| 7 六表+密码同事务 | 通过 | create_user_full 单事务 + 提交前回读 + 全回滚测试×3 |
| 8 失败注入/幂等/并发/脱敏/回滚测试真实通过 | 通过 | 160 项身份套件全绿 |
| 9 最小权限建议 | 通过（仅建议，未执行 GRANT） | identity_alert.generate_dba_privilege_recommendation |
| 10 nightly 默认关闭、机器门禁齐备 | 通过 | 生产日志确认 disabled；锁/熔断/隔离/重试/对账/告警在码 |
| 11 验收双职业双目标候选 | 部分通过 | run_validation_batch 已实现 2 人 4 动作上限；目标端"不存在"核验待 Phase D 只读回读执行 |
| 12 四方比对脱敏输出 | 通过（框架） | identity_four_way_diff；Phase D 时接入真实回读 |
| 13 部分成功待对账、不伪造一致 | 通过 | partial_target_success + 幂等续跑测试 |

## 7. Phase D 前置阻断（未解除）

1. SM4 算法第二个受控账号交叉验证 + 服务端时区验证（107 §12），通过后运维设 `APP_IDENTITY_JHEMR_PASSWORD_WRITE_ENABLED=true`。
2. JHEMR/CDMS 身份同步专用写账号最小授权（107 §7，DBA 变更单执行；当前两张写凭据文件已就位但权限未核验）。
3. 验收候选只读确认：同一名医生、同一名护士在 CDMS/JHEMR 均不存在（编排器 Phase D 执行前必须以适配器只读快照复核，当前代码未自动核验目标端存在性）。
4. 首轮夜间熔断阈值：历史首次纳管批次"新增占比"天然接近 100%，会命中 `max_change_ratio=0.3`/`max_new=50`；首轮需运维按候选量一次性上调或分批，随后恢复保守值。
5. 行数守恒熔断维度未接线（`_compute_change_stats.source_row_delta_pct=0`），需采集阶段供数后启用。
6. CDMS FTYPE=8（2851 行、281 个不同授权值）语义仍未解释，按 104/107 维持"不写 8/32"。
7. `identity_hmac.key`、`jhemr_default_password` 两个 secret 文件尚未在 8.83 凭据目录创建（Phase D 前由人工经安全渠道生成，不得入库/入仓）。

## 8. 文件变更清单

- 修订：`identity_classification.py`（值域重写 v2）、`identity_sync_orchestrator.py`（预检接入/科室确定性/熔断统计/HMAC 失败关闭/时区）、`cdms_identity_adapter.py`（真实列/众数/密文方法/DSN）、`jhemr_identity_adapter.py`（user_dept/密码门禁/控制表列/服务器时间/去重）、`identity_sync_executor_bridge.py`（角色映射/密文/客户端库）、`his_identity_sync.py` + `identity_source_collector.py`（CREATE_DATE 采集、group_class 落库）、`sync_executor.py`（dry_run 透传）、`models/identity.py`（group_class）、`config.py`（password_write_enabled）、迁移 docstring。
- 新增：`identity_classification_preflight.py`、迁移 `f8a9b0c1d2e3_add_identity_person_department_group_class.py`。
- 测试：`test_identity_sync.py`（重写）、`test_identity_nightly_sync.py`（fixture/回滚/新 17 项）。
