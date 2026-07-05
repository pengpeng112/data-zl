> 类别：关系验证

# HIS 源端资产范围复核与下一步计划

> 范围：基于用户确认口径，对 `22` 中待确认项继续复核。  
> 配套结果：`23_HIS源端资产范围复核与下一步计划结果.json`。  
> 安全口径：仅执行 `SELECT` 聚合/样本查询；大表限定样本或做必要日期聚合；不输出患者、证件、电话、姓名明细。

---

## 1. 已确认口径

| 问题 | 用户确认 | 本次处理 |
|---|---|---|
| `COMM/MEDADM` 是否纳入第一版 | 纳入，特别看是否持续产生数据 | 纳入候选范围；排除日志、统计、接口中间表 |
| `COMM.OPERATION_LOG` | 操作日志不需要纳入 | 明确排除业务关系图谱主线 |
| `ORDERS_EXECUTE_DETAILS`、`INP_ORDER_EXECDATA` | 需要纳入 | 作为医嘱执行/住院用药执行事实继续验证 |
| `PREPAYMENT_RCPT` | 是患者缴费的预交金记录 | 纳入住院费用/患者缴费闭环 |
| `VISIT_ID=0/NULL` 的检验/检查 | 应为门诊数据，HIS 没有体检数据 | 改为门诊检验/门诊检查口径，不再标体检候选 |
| 统计表、日志表、接口中间表 | 第一版排除 | `ST_*`、`*_LOG`、`*LOG*`、接口/临时/备份表从业务事实图谱排除 |

---

## 2. COMM/MEDADM 活跃度复核

### 2.1 COMM

| 表/范围 | 结果 | 结论 |
|---|---|---|
| `COMM` 全 owner 统计 | 382 表，统计行数合计约 67999941，`LAST_ANALYZED` 最新 `2026-07-02 22:01:51` | owner 仍被维护 |
| `COMM.DEPT_DICT` | 815 行，`CREATE_DATE` 最大 `2026-06-18 10:40:10`，近 12 月 65 行 | 科室字典近期维护，纳入 |
| `COMM.PRICE_LIST` | 101423 行，`ENTER_DATE` 最大 `2026-07-02 16:30:28`，近 12 月 9858 行 | 价表持续产生/维护，纳入 |
| `COMM.STAFF_DICT` | 4219 行，`CREATE_DATE` 最大 `2026-07-03 09:12:29`，近 12 月 882 行 | 人员字典持续维护，纳入 |
| `COMM.DIAGNOSIS_DICT` | 50220 行，`CREATE_DATE` 最大 `2026-02-12 15:55:01` | 诊断字典仍维护，纳入 |
| `COMM.OPERATION_LOG` | 57407694 行，样本最大 `OPER_DATE=2023-08-25 12:13:34` | 操作日志，按用户口径排除 |

结论：`COMM` 应进入第一版 HIS 源端资产包，但只纳入字典/基础资料/价格/人员等业务支撑表；日志类表排除。

### 2.2 MEDADM

| 表/范围 | 结果 | 结论 |
|---|---|---|
| `MEDADM` 全 owner 统计 | 73 表，统计行数合计约 93720954，`LAST_ANALYZED` 最新 `2026-07-02 22:03:59` | owner 仍被维护 |
| `MEDADM.BEDPATS_IN_HOSPITAL` | 4854018 行，`STAT_DATE_TIME` 最大 `2026-07-02`，近 12 月 433555 行 | 在院/床位日快照持续产生，纳入候选事实 |
| `MEDADM.DEPT_TREATE_DAY` | 2682672 行，`ST_DATE` 最大 `2024-04-11` | 统计表，排除第一版业务事实图谱 |
| `MEDADM.ST_INP_OD_DOCTOR_DAY` | 35737999 行，`ST_*` 统计类 | 按用户口径排除 |

结论：`MEDADM` 纳入，但第一版只保留与床位、在院、管理基础资料相关的表；`ST_*` 和各类日/月统计表排除。

---

## 3. 医嘱执行事实补验

| ID | 关系 | 样本 | 匹配 | 孤儿 | 时间范围 | 结论 |
|---|---|---:|---:|---:|---|---|
| OED01 | `ORDADM.ORDERS_EXECUTE_DETAILS -> ORDADM.ORDERS` by `PATIENT_ID,VISIT_ID,ORDER_NO,ORDER_SUB_NO` | 200000 | 199973 | 27 | `2022-03-14` 到 `2026-06-30` | 纳入医嘱执行事实 |
| OED02 | `DRUG_USER.INP_ORDER_EXECDATA -> ORDADM.ORDERS` by `PATIENT_ID,VISIT_ID,ORDER_NO,ORDER_SUB_NO` | 200000 | 199306 | 694 | `START_DATE_TIME` 到 `2025-11-30` | 纳入住院用药/医嘱执行事实 |
| OED03 | `DRUG_USER.INP_ORDER_EXECDATA -> DRUG_USER.PHA_INP_REQUEST_DRUG` by patient/order | 200000 | 199305 | 695 | - | 可衔接住院发药申请链路 |

结论：两张表都应进入第一版 HIS 源端资产包，类型标为 `execution_fact`。

建议关系：

| from | to | key | 关系等级 |
|---|---|---|---|
| `ORDADM.ORDERS_EXECUTE_DETAILS` | `ORDADM.ORDERS` | `PATIENT_ID+VISIT_ID+ORDER_NO+ORDER_SUB_NO` | 样本强关系 |
| `DRUG_USER.INP_ORDER_EXECDATA` | `ORDADM.ORDERS` | `PATIENT_ID+VISIT_ID+ORDER_NO+ORDER_SUB_NO` | 样本强关系 |
| `DRUG_USER.INP_ORDER_EXECDATA` | `DRUG_USER.PHA_INP_REQUEST_DRUG` | `PATIENT_ID/PAT_ID + VISIT_ID/IN_COUNT + ORDER_NO/MO_ORDER + ORDER_SUB_NO` | 样本强关系 |

---

## 4. 预交金记录补验

| ID | 关系/画像 | 结果 | 结论 |
|---|---|---|---|
| P01 | `PREPAYMENT_RCPT.PATIENT_ID -> PAT_MASTER_INDEX.PATIENT_ID` | 200000 样本匹配 199945，孤儿 55 | 患者级缴费事实成立 |
| P02 | `PREPAYMENT_RCPT(PATIENT_ID,VISIT_ID) -> PAT_VISIT` | 200000 样本中 `VISIT_ID=0/NULL` 140796；非零子集匹配 59131，孤儿 73 | 非零住院子集可挂住院；空/0 保留患者级缴费 |
| P03 | `REFUNDED_RCPT_NO -> PREPAYMENT_RCPT.RCPT_NO` | 退款键非空 202，全部匹配 | 退款收据自关联成立 |
| P04 | 活跃度 | 27480767 行，最大 `TRANSACT_DATE=2026-07-03 10:18:09`，近 12 月 2996173 行，近 1 月 251006 行 | 持续产生，必须纳入费用闭环 |

结论：`INPBILL.PREPAYMENT_RCPT` 是患者缴费/预交金事实表，应纳入第一版资产包，类型标为 `payment_fact`。

---

## 5. 门诊检验/检查口径复核

用户确认：`VISIT_ID=0/NULL` 的检验/检查应为门诊数据，HIS 系统没有体检数据。

本次按患者和申请日期尝试挂 `OUTPADM.CLINIC_MASTER`：

| ID | 子集 | 样本 | 同日门诊匹配 | 前后 1 天门诊匹配 | 结论 |
|---|---|---:|---:|---:|---|
| V01 | `LAB.LAB_TEST_MASTER` 中 `VISIT_ID=0/NULL` | 50000 | 46707 | 47217 | 支持门诊检验口径，但患者+日期不是唯一强键 |
| V02 | `EXAM.EXAM_MASTER` 中 `VISIT_ID=0/NULL` | 50000 | 49894 | 49997 | 强支持门诊检查口径，但患者+日期不是唯一强键 |

结论：

1. `VISIT_ID=0/NULL` 检验/检查不再标为体检/未知，改标为门诊检验/门诊检查。
2. 当前可用 `PATIENT_ID + 申请日期` 作为候选关联门诊就诊，但不能作为唯一强键。
3. 下一步应继续寻找 `RCPT_NO`、`ORDER_ID`、`CLINIC_NO`、`VISIT_DATE/VISIT_NO` 等桥接键。

---

## 6. 第一版 HIS 源端资产包范围规则

### 6.1 纳入 owner

第一版纳入以下 12 个 owner：

`MEDREC`、`INPADM`、`ORDADM`、`LAB`、`EXAM`、`INPBILL`、`OUTPBILL`、`OUTPADM`、`DRUG_USER`、`PHARMACY`、`COMM`、`MEDADM`。

### 6.2 强制纳入表

| 表 | 类型 | 原因 |
|---|---|---|
| `ORDADM.ORDERS_EXECUTE_DETAILS` | `execution_fact` | 医嘱执行事实，已样本验证可挂医嘱 |
| `DRUG_USER.INP_ORDER_EXECDATA` | `execution_fact` | 住院用药/执行事实，可挂医嘱和发药申请 |
| `INPBILL.PREPAYMENT_RCPT` | `payment_fact` | 患者预交金/缴费事实，持续产生 |
| `MEDADM.BEDPATS_IN_HOSPITAL` | `inpatient_management_fact` | 在院/床位日快照，持续产生 |
| `COMM.DEPT_DICT` | `dimension` | 科室字典，持续维护 |
| `COMM.STAFF_DICT` | `dimension` | 人员字典，持续维护 |
| `COMM.PRICE_LIST` | `dimension` | 价表，持续维护 |
| `COMM.DIAGNOSIS_DICT` | `dimension` | 诊断字典，持续维护 |

### 6.3 排除规则

第一版业务事实图谱排除：

| 模式 | 处理 |
|---|---|
| `ST_*` | 排除，统计汇总表 |
| `*_LOG`、`*LOG*` | 排除，日志类表 |
| 接口中间表 | 排除，除非后续证明是唯一业务事实来源 |
| 临时/备份/历史复制表 | 排除 |
| 纯统计日/月表 | 排除 |

`COMM.OPERATION_LOG` 明确排除。

---

## 7. 下一步计划

1. 生成独立 HIS 源端资产包草案：`his_source_tables.csv`、`his_source_columns.csv`、`his_source_relationships.csv`、`his_source_catalog.json`。
2. 新资产包字段增加：`source_db`、`source_owner`、`table_role`、`include_status`、`exclude_reason`、`ods_same_name_covered`。
3. 对纳入表打标签：`core_fact`、`dimension`、`execution_fact`、`payment_fact`、`candidate`、`excluded`。
4. 将 `ORDERS_EXECUTE_DETAILS`、`INP_ORDER_EXECDATA`、`PREPAYMENT_RCPT` 的验证关系写入 HIS 源端关系清单。
5. 将 `VISIT_ID=0/NULL` 的 `LAB_TEST_MASTER`、`EXAM_MASTER` 标为门诊事实子集，关系等级为候选，继续找强键。
6. `ST_*`、`*_LOG`、接口中间表从第一版业务事实图谱排除，但可在资产目录中保留为 `excluded`，方便追溯。

---

## 8. 剩余不确定项

1. 门诊检验/检查目前只有患者+日期候选关联，不能当作唯一强键；还需继续找门诊号、收费号或医嘱号桥接。
2. 接口中间表识别目前依赖命名规则和少量业务判断，需要在资产包中保留可人工调整的 `include_status`。
3. `MEDADM` 中非 `ST_*` 的管理表是否全部纳入，还需按表名和字段再做一次裁剪。
