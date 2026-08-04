> 类别：复核报告
> 状态：当前（独立复核结论；放行裁决以本文 §6 为准）
> 复核日期：2026-07-31 | 复核方式：文档/代码/迁移/测试/调度/配置逐行核对 + 经 8.83 受控只读凭据对 HIS/CDMS/JHEMR 活库核实（全部 SELECT，业务库写入 0）

# 104 HIS 人员夜间同步 CDMS 与 JHEMR 方案独立复核报告

复核对象：`103_HIS人员向无纸化与电子病历夜间同步执行计划.md` 及其引用的全部代码、模型、调度与活库事实。本报告不复述 103，只列差异、错误、风险与放行结论。活库核实通过 `root@10.10.8.83` 公钥 + 容器内 `/etc/data-asset/credentials/` 既有只读凭据执行，未输出姓名/密码/证件/电话，业务源库写入为 0。

## 0. 活库核实关键事实（证据底座）

| 事实 | 证据（只读查询结果） |
|---|---|
| HIS `COMM.STAFF_DICT.STATUS`：1=在用 2462 人，0=停用 1802 人 | `GROUP BY STATUS`；EMP_NO 无重复无空（4264/4264） |
| `STAFF_DICT.CREATE_DATE`：463 人 NULL；>=2026-07-20 共 48 行；最大 2026-07-30 | `create_date_stats` |
| `FXHIS.SYS_EMPLOYEE`：仅此一个 owner（COMM 下不存在）；VALIDSTATE 1=2425 / 0=86；ISDELETED 全 0；**USERCODE 全空**，USERID 2468 非空 | `sys_employee_owners` / `se_validstate` / `se_total` |
| STAFF 与 SYS_EMPLOYEE 状态冲突 182 人；STAFF.STATUS=1 但无 SYS_EMPLOYEE 记录 155 人 | `conflict_check` / `staff_not_in_se` |
| `COMM.STAFF_GROUP_DICT.DEPT_CODE`：**569/569 全部为 NULL** | `sgd_deptcode` |
| `COMM.STAFF_VS_GROUP.GROUP_CODE`：9449/9449 命中 `DEPT_DICT`，本身即科室/病区编码；END_DATE 全 NULL；GROUP_CLASS 含收款员 192/物资管理 134/行政管理 14 等非临床组 | `svg_grp_vs_dept` / `svg_enddate` / `svg_class` |
| `COMM.DEPT_DICT`：816 个，有效（STOP_FLAG NULL/0）595 个，停用 221 个 | `dept_valid_codes` |
| `DOCTOR_GROUP` 1165 行，DOCTOR_USER 1160 命中 EMP_NO，DEPT_CODE 全部有效；**每人仅 1 行**（D_DOC=TOTAL），不构成多科室来源 | `dg_match` |
| JOB×TITLE 交叉：`润华药学` 22 人 TITLE=药士14/药师8（外包）；护理+药师 1、医生+药师/药士 2、临床+主管药师 2 等冲突；JOB NULL 262（其中 258 TITLE 也为 NULL） | `job_title_cross` |
| CDMS 为 Oracle **11.2.0.1.0**（thin 模式不可连，必须 thick）；`T_MSS_EMP_DICT` PK=FLOGINNAME，FROLEID 1727/1727 全空，FPWD 1715×16 字符 + 12×32 字符（**密文**） | `v$version` / `emp_pk_cols` / `froleid` / `fpwd_len` |
| `T_MSS_AUTHMAPPING` FTYPE 分布：0=2147、2=2395、3=2140、4=54、5=2145、10=2140、**8=2851（最大，103 未调查）**、32=11 | `ftype_dist` |
| FTYPE=3 众数 100005（离群 100008×1）；FTYPE=5 全量 A00001；FTYPE=10 众数 0（'1'×128）；FTYPE=2 有 327 个编码，325 命中 HIS DEPT_DICT，仅 253 命中有效集，含 'xxk'/'03' 等脏值 | `ftype3/5/10/2_dist` + 跨库比对 |
| CDMS 无科室字典表（仅 0 行的 T_MSS_EMP_DEPT 和 SCOTT.DEPT）；FSYSID 1×104/2×1623，FUSERTYPE 0×33/1×825/2×869，**无单一众数** | `all_dept_tables` / `col_dist` |
| CDMS `AbpUsers` 仅 1 行 admin —— ABP 身份未用于业务登录，T_MSS_EMP_DICT 确为登录表（103 假设成立） | `abp_users_cnt` |
| JHEMR `users` PK=**(db_user, hospital_no)**；db_user=user_id=user_login_name 3943/3943 一致；hospital_no 实际值 **'49557032X'×3942**，列默认值 '1110002' 为另一租户 | `users_pk` / `dbuser_vs_userid` / `users_hosp` |
| JHEMR 锁定：account_status=8 且 locked_time 非空 67 条；state 3033 行为 NULL（103 称正常=state=0 不准确）；users 无触发器 | `locked_sample` / `users_status` / `users_triggers` |
| **JHEMR 角色组 002（护士组）绑定用户数=0**；真实授权走 `jhauth_user_vs_role` 直接角色 4144 行（25 临床医疗×987、120 病案浏览-科室×975、114 主任×403、115 主治×292）；001→25、002→101 的 DEFAULT_ROLE_FLAG 均为 0 | `uvrg_002` / `uvr_dist` / `rg001` |
| JHEMR dept_dict 826 个编码覆盖 HIS 全部 816 个（有效 595 全覆盖），另有 10 个脏编码（'123456' 等） | 跨库比对 |
| JHEMR user_type：0×2123 / 1×1443 / NULL×375，语义未确认；is_nurse 全 NULL；1591/3943 用户无 user_dept 行 | `user_type` / `users_no_dept` |

## 1. 已确认错误（按严重度排序）

### E1【高】平台身份主档状态归一错误，停用人员/科室全部被记为 active（已修复）
- 位置：`backend/app/services/his_identity_sync.py::_normalize_status`（修复前把 `{"","0","1",...}` 全部归一为 `"active"`）。
- 证据：活库 STAFF.STATUS=0 是 1802 名停用人员、VALIDSTATE=0 是 86 名无效人员、STOP_FLAG=1 是 221 个停用科室，修复前全部写成 `active`。103 的锁定规则、有效科室过滤若基于平台数据必然失效。
- 影响：错误授权（停用人员被视为在用）、锁定漏判。触发条件：任何一次 sync apply。
- 修复：已改为按字段语义的 `_normalize_status`（1=active/0=inactive/其余 unknown）与 `_normalize_stop_flag`（NULL/0=active/1=inactive），并加断言。
- 注意：已入库的 4260 人/816 科室主档是错误数据，**必须在下次 apply 时全量重刷**；平台库现有 `employment_status='active'` 记录不可信。
- 建议测试：`tests/test_his_identity_status_unit.py`（新增）、`test_his_identity_sync.py` 已补 STATUS=0→inactive 断言（需测试库执行）。

### E2【高】`identity_source_collector` 状态归一反向（已修复）
- 位置：`backend/app/services/identity_source_collector.py::_normalize_status` 原实现按 STOP_FLAG 语义设计却用于 STAFF.STATUS/VALIDSTATE，导致 **STATUS=1 在用最被记为 inactive**。
- 影响：`asset_identity_person_sources.source_status` 与真值完全相反，L13 差异复核会把正常人员判为停用差异。
- 修复：拆出 `_normalize_staff_status`，STOP_FLAG 归一保留原函数。

### E3【高】采集器查询不存在的表 `COMM.SYS_EMPLOYEE`（已修复）
- 位置：`backend/app/services/identity_source_collector.py:20`（修复前 `EMPLOYEE_SOURCE_TABLE = "COMM.SYS_EMPLOYEE"`，SQL 同样写 COMM）。
- 证据：活库 `ALL_TABLES` 中 SYS_EMPLOYEE 唯一 owner 是 FXHIS。修复前 `collect_his_persons` 必然 ORA-00942，`POST /api/v1/identity/collect-sources` 的 identity_person 路径整体不可用。
- 修复：改为 `FXHIS.SYS_EMPLOYEE`。

### E4【高】人员组附加科室取自全空字段，平台从未写入任何人员组科室关系（已修复）
- 位置：`his_identity_sync.py::_collect` 与 `identity_source_collector.py::collect_his_persons` 的 staff_groups 查询均 `LEFT JOIN STAFF_GROUP_DICT` 取 `sgd.DEPT_CODE`。
- 证据：活库 `STAFF_GROUP_DICT.DEPT_CODE` 569/569 全 NULL（103 §6.1 已声明"不能依赖该字段"，但代码恰恰只依赖它）；`STAFF_VS_GROUP.GROUP_CODE` 9449/9449 命中 DEPT_DICT。
- 影响：`asset_identity_person_departments` 缺失全部 9449 条人员组科室关系（103 实测单人最多 12 条期望科室），任何"读取平台期望科室集合"的实现都会严重少配科室。
- 修复：两处改为直接以 `svg.GROUP_CODE` 作为科室编码，移除无效 JOIN；测试假数据同步更新。

### E5【高】103 的 JHEMR 授权设计与活库实际用法不符
- 103 §6 主张"新增医师/药师绑 001 医师组、护士绑 002 护士组"。
- 活库证据：**002 组绑定用户数=0**；现存人员授权以 `jhauth_user_vs_role` 直接角色为主（4144 行），且医师角色按职称分层（25 临床医疗、114 临床医疗-主任、115 临床医疗-主治）并普遍叠加 120 病案浏览-科室；001→25、002→101 映射的 DEFAULT_ROLE_FLAG 均为 0。
- 影响：按计划新建的护士账号将获得全院无任何真实用户使用的授权路径，是否生效未经验证；医师账号权限组合也与真实账号（按职称分层）不一致 → 账号可能不可用作或权限不足/过度。
- 触发条件：任何 JHEMR create_account 动作。
- 修复建议：放弃"仅绑组"，改为按人员类型（必要时按职称）镜像真实正常账号的角色组合（角色级众数模板，与 CDMS FTYPE 模板方法对齐）；002 组绑定是否等效需厂商书面确认。建议测试：对 45 人增量队列逐人生成期望角色集合并与同类型真实账号众数比对。

### E6【高】103 完全未提 JHEMR hospital_no，默认会写入错误租户
- 证据：`users` PK=(db_user, hospital_no)，生产租户 '49557032X'（3942/3943），列默认值 '1110002' 为另一租户；角色组、角色绑定、user_dept 均挂在 '49557032X'。`medical_code_push` 现有默认 `dict_medical_push_default_hospital_no="1110002"`（`backend/app/core/config.py:44`），若身份适配器沿用该默认即写错租户。
- 影响：新账号落在不存在业务数据的租户，表现为"创建成功但登录无数据/不可见"；角色绑定挂错租户直接无效。
- 修复建议：身份写策略显式配置 `identity_hospital_no='49557032X'`，插入 users/user_dept/jhauth_user_vs_role(_group) 四处必须一致并加守恒校验。

### E7【中高】CDMS FTYPE=8（2851 行，全表最大类别）与 FTYPE=32 未调查
- 103 只覆盖 FTYPE 0/2/3/4/5/10。活库 FTYPE=8 涉及 421 个用户、281 个权限 ID（FID 2826/2851 为用户工号）；FTYPE=32 为组→病区（如 FID='hushi'→'020301H'）。
- 影响：若 FTYPE=8 是功能/数据范围必需授权，新账号将缺一类全院近 1/4 用户在用的权限；若不需要则应在模板计算中显式排除并记录。
- 修复建议：列入 P0 待核实清单（厂商或 CDMS 管理员确认语义），结论写入角色映射配置。

### E8【中高】CDMS FPWD 为密文存储，103 把密码阻断只算在 JHEMR 头上
- 证据：`T_MSS_EMP_DICT.FPWD` 1715 个账号为 16 字符、12 个为 32 字符，长度高度一致 → 哈希/加密存储，不是明文。
- 103 §11 称"CDMS 初始密码已由用户确定"，但未验证算法。直接写明文几乎必然无法登录；复制他人密文被 103 自己禁止且等同伪造账号。
- 修复建议：与 JHEMR 同级阻断——确认 FPWD 算法（16 字符形态疑似截断 MD5 或厂商私有）或获得厂商初始化 API；单账号登录验证通过前不得批量创建。

### E9【中】复用 `medical_code_push` 写路径连 Oracle 11g 必然失败
- 位置：`backend/app/services/medical_code_push.py::_execute_write_sql`（Oracle 分支未调用 `oracledb.init_oracle_client`）。
- 证据：HIS 11.2.0.4、CDMS 11.2.0.1，python-oracledb thin 模式不支持 11g（DPY-3010）。该函数从未在生产执行过（写开关关闭），所以尚未暴露。
- 影响：身份适配器若复制该模式，CDMS 写入 100% 失败。修复建议：适配器统一走 thick 初始化（容器内 `/opt/oracle`），并把"写连接使用 thick"加入冒烟断言。

### E10【中】103 §6.1"正常样本 account_status=0,state=0"不准确
- 证据：JHEMR `users.state` 3033/3943 为 NULL，仅 842 行为 0。锁定判定若校验 `state=0` 会误判绝大多数正常账号。
- 修复建议：状态机只以 `account_status` + `locked_time` 为准，`state` 不进入判定；103 文本需修订。

## 2. 重大风险

### R1【高】外包药学人员会被误判为药师并授予医疗质控/医师组
- 证据：`JOB='润华药学'` 22 人（TITLE 药士 14、药师 8）；另有润华收银、颐邦售后等外包 JOB 值。
- 103 分类规则只按 JOB/TITLE 命中"药师/药士/主管药师"，无外包排除 → 22 名外包人员将获得与医师一致的权限。
- 修复建议：分类器第 0 优先级增加外包/厂商 JOB 黑名单（润华*、颐邦* 等，规则版本化），命中即 `excluded_outsource` 只告警。

### R2【高】JOB 与 TITLE 冲突样本会被确定性错分
- 证据：护理+药师 1、医生+药师 1/药士 1、临床+主管药师 2、护理+医师 1、急救 JOB 内医护混合 25、检验+医师 5 等。
- 103 固定优先级（药师>护士>医师）会把"护理 JOB 但 TITLE=药师"判为药师 → 授医疗质控而非护理质控。
- 修复建议：JOB 与 TITLE 指向不同类别时归入 `classification_conflict` 异常清单人工裁决，不得自动归类；`JOB='药剂'` 且 TITLE NULL 的 8 人需单独口径（建议按药师但进观察清单）。

### R3【高】CREATE_DATE NULL 的 463 人被静默永久排除，且平台根本没采集 CREATE_DATE
- 证据：463 人 NULL 中含 STATUS=1 的医生 15/护士 9/护理 8/药剂 5/医技 42；`his_identity_sync.py::_collect` 的 staff 查询不 SELECT CREATE_DATE，平台表也无该列。
- 影响：① NULL 者在 103 口径下落入 legacy_unmanaged，永不同步且无报表；② 复合水位 (CREATE_DATE, EMP_NO) 无数据基础，P1 未建列前增量逻辑无法实现。
- 修复建议：采集与平台模型补 CREATE_DATE（Alembic 手写迁移）；NULL 口径显式化——建议以 `NVL(CREATE_DATE, 旧)` 视为历史但纳入脱敏统计月报，新增人员若 CREATE_DATE 补录则自动进入纳管候选。

### R4【高】增量水位/24h 回看/幂等队列完全未实现，现有采集会被静默截断
- 证据：`db_connectors.py::MAX_READONLY_ROWS=10_000` 静默钳制；`_collect` 用 `ROWNUM<=N` 无 ORDER BY；STAFF_VS_GROUP 9449 行距上限仅 551 行，超限时随机丢科室关系且无任何告警；全仓库无水位表、无 identity_nightly_sync 调度类型（`main.py::_start_scheduler` 仅支持 metadata_scan/quality_check）。
- 修复建议：采集加 `ORDER BY EMP_NO` + 行数守恒校验（源端 COUNT 与拉取行数不一致即失败）；新建水位/批次/动作明细表（103 P1）。

### R5【中高】STATUS=1 但 SYS_EMPLOYEE 不存在的 155 人无告警直达建号
- 103 冲突规则只覆盖"两表都有且不一致"。SYS_EMPLOYEE 是用户确认的主数据，主数据缺失但 STAFF 在用属于异常，应进 `status_conflict`（只告警不建号），当前计划会静默同步。

### R6【中高】GROUP_CLASS 未过滤，非临床组会产生错误科室授权
- 证据：STAFF_VS_GROUP 含收款员 192、物资管理 134、行政管理 14、经济核算 2 行，其 GROUP_CODE 同样命中 DEPT_DICT；103 "人员组科室全部并入期望科室"会把收银/物管分组变成科室权限。
- 修复建议：GROUP_CLASS 白名单（病区医生/门诊医生/病区护士/检查医生/手术医生/麻醉医生，规则版本化），其余进统计不授权。

### R7【中】调度无分布式锁、无超时、无并发保护
- 证据：`main.py::_start_scheduler` 用进程内 BackgroundScheduler，无 jobstore/锁表；多容器或多 worker 部署会重复执行；job 无 misfire/grace/timeout 配置；`_run_quality_nightly` 同类问题已有先例。
- 修复建议：`identity_nightly_sync` 必须以平台库行锁/ advisory lock 做分布式互斥，单批超时与断点续跑以批次表状态机实现。

### R8【中】103 §2.2 自述缺口全部仍在：目标只读采集器、写适配器、写凭据与 `identity_account_sync` 写策略、角色映射配置、保护名单、批次/动作明细表、调度类型均未实现
- 代码证据：全仓库 grep 无任何 CDMS/JHEMR 身份适配器；`IdentityAccount` 表无采集器写入；`asset_data_sources` 无 identity 写策略（`medical_code_push._build_connector` 只认 `write_policy='medical_dict_push'`）。

### R9【中】CDMS 新账号必填/模板列未完全定义
- 证据：FUSERSTATE 无默认值（必须显式写 0）；FSYSID（1×104/2×1623）、FUSERTYPE（0×33/1×825/2×869）无单一众数且语义未知；`T_MSS_AUTHMAPPING.FAUTHMAPPINGID` 需程序生成 32 位 GUID；FUSERNAME 长度 50、FPWD 50。
- 修复建议：FSYSID/FUSERTYPE 语义列入厂商确认清单；模板众数扩展到 EMP_DICT 列级（按人员类型分组计算）。

### R10【中】单人多行写入无原子性，部分成功无补偿
- 证据：`medical_code_push._execute_write_sql` 每条 DML 独立 commit；一个 CDMS 账号需要 EMP_DICT 1 行 + AUTHMAPPING ≥5 行（FTYPE 0/2/3/5/10），中途失败产生"半账号"；103 只规定两目标独立事务，未规定单人原子性与补偿队列。
- 修复建议：单账号多表写入放进同一事务（每目标每账号一个事务），动作明细表记录行级结果，失败账号进补偿队列并可按工号重跑。

### R11【中】审计可能记录初始密码
- 证据：`medical_code_push.apply_one_action` 审计 `after_data` 记录完整 `params`（`medical_code_push.py:1117-1124`）。身份同步的 params 必然包含初始密码/密文。
- 修复建议：适配器审计前强制剔除口令类参数名（白名单式保留），并把"审计中不存在口令字段"加入测试。

### R12【中】多科室"集合对齐"会物理删除 AUTHMAPPING 行，误删人工授权不可恢复
- 证据：`T_MSS_AUTHMAPPING` 无状态/有效期列，移除=DELETE；103 的"观察 3-7 天再放行移除"无任何实现机制；保护清单表不存在。
- 修复建议：先建"本任务纳管关系"标记（平台侧记录每条由任务创建的 FID/FTYPE/FAUTHORITYID），只允许移除任务自建关系；人工关系永不删除；JHEMR user_dept 优先用 end_date/state 软停而非 DELETE。

### R13【低】CDMS 无科室字典表，"目标科室不存在阻断"只能以 HIS 有效 DEPT_DICT（595）为准
- 证据：CDMS 全库无 dept dict；现存 FTYPE=2 含 72 个 HIS 已停用编码与 'xxk'/'03' 等脏值。JHEMR 侧 HIS 有效编码 100% 覆盖，可直接校验。

### R14【低】`sync_executor.run_sync` 的 identity_his 路径硬编码 `dry_run=False`
- 位置：`backend/app/services/sync_executor.py:374-376`。通用 `/identity/sync/run` 入口调用即直接 apply 平台写，无独立审批；虽有审计且仅写平台库，但与"平台写需审批"的硬边界存在张力，建议 dry_run 参数化并默认 true。

## 3. 待核实假设

- A1：FTYPE=10 的 '1'×128 与 FTYPE=3 的 100008×1 是否属于管理/特殊账号——众数模板必须按"本角色+正常账号"过滤，否则被污染（103 已要求分类型重算+并列阻断，方向正确，需落实到过滤条件）。
- A2：`SYS_EMPLOYEE.USERID`（2468 非空）是否比全空的 USERCODE 更适合做桥接备用键（影响 155 人无主数据记录的归因）。
- A3：CDMS FSYSID/FUSERTYPE/FPOSITION/FISAUDIT/FPAGEROLE 语义；JHEMR user_type 0/1/NULL 语义、user_dept.default_role_id 是否为护士真实授权通道之一。
- A4：103 §6.1 的"45 人/CDMS 缺 34/JHEMR 缺 0"未重算（分类器未定型）；我方测得基线总行数 48（含停用与非三类），与 45 相容但不构成验证。
- A5：`T_MSS_EMP_DEPT` 0 行、JHEMR "543 名多科室用户"沿用 103 结论，未逐项复核（低风险）。
- A6：STAFF.STATUS=1 为在用的语义有 103 双样本佐证且分布合理，但是否存在 STATUS_TIME/EMP_STATUS 更权威的停用时间源未查（影响"何时锁定"的及时性）。

## 4. 改进建议

- S1：平台 identity 模型补列（Alembic 手写迁移）：`create_date`、`job`、`title`、`person_class`（doctor/nurse/pharmacist/excluded_*/conflict/unsupported）、`class_rule_version`、`managed_by_sync`、`management_flag`、`status_conflict_flag`；新建 `asset_identity_sync_watermarks`、`asset_identity_sync_batches`、`asset_identity_sync_actions`、`asset_identity_role_mappings`、`asset_identity_protected_accounts`（均在 asset schema，`asset_identity_` 前缀）。
- S2：分类器输出必须持久化原始 JOB/TITLE 与命中规则，冲突一律进异常清单；主任医师/副主任医师/主任护师/主任药师/副主任药师 按职称归专业技术序列（活库：主任药师 3、副主任药师 6 均属药剂 JOB，不应被"主任"排除）。
- S3：E1-E4 修复后，对平台身份主档做一次全量重刷（dry-run 对账后 apply），并保留重刷前后计数证据。
- S4：JHEMR 授权改用"角色级众数模板"（医师按职称分层：25+120 基础，主任/主治叠加 114/115；护士模板需先从真实护士账号反查，不能套 002 组）。
- S5：oracle 写连接统一 thick 初始化 + 冒烟断言；审计口令字段白名单过滤。

## 5. 本轮已直接修复的代码缺陷（低风险、有测试）

| 文件 | 修复 | 测试 |
|---|---|---|
| `backend/app/services/his_identity_sync.py` | E1 状态归一拆分 `_normalize_status`/`_normalize_stop_flag`；E4 staff_groups 改用 GROUP_CODE | `tests/test_his_identity_sync.py` 更新假数据并新增 STATUS=0→inactive、STOP_FLAG 断言 |
| `backend/app/services/identity_source_collector.py` | E3 owner 改 FXHIS；E2 拆 `_normalize_staff_status`；E4 同步改 GROUP_CODE | `tests/test_identity.py` 更新假数据并新增 source_status=inactive 断言 |
| `backend/tests/test_his_identity_status_unit.py` | 新增纯逻辑回归（无 DB 依赖） | 已通过直接断言执行验证 |

验证：`py_compile` 全部通过；纯逻辑断言在本地 venv 执行通过。**DB 依赖测试（test_his_identity_sync.py / test_identity.py）因本机无 APP_TEST_DB_URL 未执行**（与仓库既有阻塞一致，需经 SSH 隧道到 8.83 `data_asset_test` 执行）；本次未对任何业务库执行 DML/DDL，未触碰平台生产库。

## 6. 四阶段放行结论

| 阶段 | 结论 | 条件/阻断 |
|---|---|---|
| 允许开发 | **允许** | P1 模型/迁移、分类器（含 R1/R2/R5/R6 规则）、只读采集器、适配器骨架可立即开发；E1-E4 已修复 |
| 允许 dry-run | **有条件允许** | 前置：①E1-E4 修复后平台主档全量重刷（S3）②采集补 CREATE_DATE + ORDER BY + 行数守恒（R3/R4）③分类器含外包黑名单与冲突类别（R1/R2）④CDMS/JHEMR 只读快照采集器完成。dry-run 只写平台批次/动作表，业务库 0 写 |
| 允许灰度写入 | **暂不允许** | 阻断项：E5（JHEMR 授权模式未定）、E6（hospital_no 租户）、E8（CDMS FPWD 算法）、103 已列的 JHEMR user_pwd_sm 算法、E7（FTYPE=8 语义）、写凭据与 `identity_account_sync` 写策略未建（R8）、单人原子性与补偿队列（R10）、纳管标记表（R12）、审计口令脱敏（R11）。全部关闭后才可按"单类型、单科室、≤10 人"灰度 |
| 允许正式定时运行 | **不允许** | 另需：R7 分布式锁/超时/断点续跑、熔断阈值经灰度校准、连续 3-7 天 dry-run 对账为零差异、告警通道验收 |

## 7. 需要修改的清单

**代码**：`his_identity_sync.py`（✅已修，另需补 CREATE_DATE 采集与 ORDER BY）、`identity_source_collector.py`（✅已修）、`sync_executor.py`（R14 dry_run 参数化）、`main.py`（identity_nightly_sync 调度类型+互斥锁）、`medical_code_push.py`（E9 thick 初始化、R11 审计脱敏，供身份适配器复用前必须修）、新增 `cdms_identity_adapter.py`/`jhemr_identity_adapter.py`/`identity_classification.py`。
**模型/迁移（手写 Alembic，asset schema）**：S1 全部新列与新表；`asset_data_sources` 增加 CDMS/JHEMR `write_policy='identity_account_sync'` 与独立 `write_credential_ref`。
**配置**：`APP_IDENTITY_SYNC_ENABLED=false`（默认）、`APP_IDENTITY_SYNC_CONFIRMATION_TOKEN`、`APP_IDENTITY_JHEMR_HOSPITAL_NO='49557032X'`、CDMS/JHEMR 初始密码专用秘密（仅服务器 `/etc/data-asset/credentials/`，0600）。
**测试**：分类器全值域（含润华药学/主任医师/主任药师/JOB NULL/TITLE NULL/冲突对）、幂等重复执行、单人事务回滚、熔断、审计无口令字段、调度互斥、迁移 upgrade/downgrade/upgrade 往返。
**103 文档修订**：E5/E6/E8/E10 对应章节（JHEMR 授权模式、hospital_no、CDMS FPWD 阻断、state 语义）、R5 冲突规则补"主数据缺失"分支、R6 GROUP_CLASS 白名单。

## 8. 整改顺序与验收命令

1. （已完成）E1-E4 代码修复 + 纯逻辑测试。
2. 测试库执行回归：`cd backend && ./.venv/Scripts/python.exe -m pytest tests/test_his_identity_status_unit.py tests/test_his_identity_sync.py tests/test_identity.py -q`（需先 `scripts/tunnel_test_db.py` 建立到 8.83 `data_asset_test` 的隧道并设置 APP_TEST_DB_URL）。
3. S1 迁移手写 + 独立测试库 `alembic upgrade head` / `downgrade` / `upgrade` 往返。
4. 采集器补 CREATE_DATE/ORDER BY/行数守恒后，平台身份主档全量重刷（dry-run 对账→apply），验收：`GET /api/v1/identity/persons?person_type=formal` 抽样停用人员 `employment_status=inactive`、科室 `status` 停用 221 个一致。
5. 分类器+规则版本+冲突清单开发，用 §0 活库交叉表做 100% 抽样对账（重点：润华药学 22、JOB/TITLE 冲突 8+、JOB NULL 262）。
6. CDMS/JHEMR 只读快照采集器 + 目标差异 dry-run，验收：45 人增量队列逐动作清单与 103 §6.1 数字对账。
7. 厂商确认清单闭环：CDMS FPWD 算法/FTYPE=8/FSYSID/FUSERTYPE；JHEMR user_pwd_sm 算法或初始化 API/002 组等效性/user_type 语义。
8. 写适配器 + 写策略 + 审计脱敏 + 单人事务 + 补偿队列 + 调度互斥；测试库全量 pytest 与迁移往返通过后，按 §6 灰度口径申请放行。

每步完成判定沿用 55 号五条标准（文件:行号、验收命令实测、手写迁移、针对性测试、README 更新记录）。
