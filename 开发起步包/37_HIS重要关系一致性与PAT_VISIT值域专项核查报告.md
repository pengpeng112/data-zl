> 类别：关系验证

# HIS 重要关系一致性与 PAT_VISIT 值域专项核查报告

## 1. 核查目标

根据用户要求，本轮对 HIS 重要表关系进行专项核查，重点看主键/业务键关联后的数据覆盖是否基本一致，并对 `MEDREC.PAT_VISIT` 做字段类型、时间范围和值域分布分析。

本轮只读查询 `10.10.10.15:1521/his`，通过 8.53 跳板机执行。不导出姓名、证件号、电话、地址等敏感明细，只输出统计结果。

输出文件：

- `数据资产_HIS_READY专项核查包/important_relation_consistency.csv`
- `数据资产_HIS_READY专项核查包/pat_visit_value_distribution.csv`
- `数据资产_HIS_READY专项核查包/relation_value_audit_summary.json`

## 2. 重要关系一致性结论

关系核查原则：核心主表可全量；千万/亿级明细表采用前 100000 条非空业务键样本；`LAB_RESULT` 使用 `TEST_NO` 限定，避免全表扫描。

| 关系 | 核查口径 | 匹配情况 | 结论 |
|---|---|---:|---|
| `PAT_VISIT.PATIENT_ID -> PAT_MASTER_INDEX.PATIENT_ID` | 全量 575841 | 匹配 575838，孤儿 3，99.9995% | 基本一致，少量孤儿进复核 |
| `DIAGNOSIS -> PAT_VISIT` | 100000 样本 | 100000 匹配，0 孤儿 | 可作为 A 级关系 |
| `ORDERS -> PAT_VISIT` | 100000 样本 | 孤儿 47，99.953% | 基本成立，历史/异常医嘱需复核 |
| `ORDERS_COSTS -> ORDERS` | 100000 样本 | 孤儿 7，99.993% | 基本成立，费用明细多行对应医嘱 |
| `ORDERS_EXECUTE_DETAILS -> ORDERS` | 100000 样本 | 孤儿 24，99.976% | 基本成立，执行明细多行对应医嘱 |
| `EXAM_REPORT -> EXAM_MASTER` | 100000 样本 | 孤儿 1，99.999% | 基本成立 |
| `LAB_TEST_ITEMS -> LAB_TEST_MASTER` | 100000 样本 | 100000 匹配，0 孤儿 | 可作为 A 级关系 |
| `LAB_RESULT -> LAB_TEST_MASTER` | 按 TEST_NO 限定 1302062 行 | 0 孤儿 | 可作为 A 级关系，禁止无界扫描 |
| `INP_BILL_DETAIL -> PAT_VISIT` | 100000 样本 | 100000 匹配，0 孤儿 | 可作为 A 级关系 |
| `OUTP_BILL_ITEMS -> OUTP_RCPT_MASTER` | 100000 样本 | 100000 匹配，0 孤儿 | 可作为 A 级关系 |
| `DRUG_PRESC_MASTER -> PAT_VISIT` | 100000 样本 | 孤儿 32，99.968% | 基本成立，需关注门诊/住院来源 |
| `DOCT_DRUG_PRESC_MASTER -> PAT_VISIT` | 100000 样本 | 孤儿 14，99.986% | 基本成立 |

## 3. 需要拆分口径的关系

以下关系不能简单按全量 `PATIENT_ID+VISIT_ID -> PAT_VISIT` 判断：

| 关系 | 样本匹配率 | 原因判断 | 建议 |
|---|---:|---|---|
| `EXAM_MASTER -> PAT_VISIT` | 47.775% | 检查主记录同时包含门诊和住院，门诊 `VISIT_ID` 口径不能直接挂住院 `PAT_VISIT` | 拆为住院检查、门诊检查两条关系 |
| `LAB_TEST_MASTER -> PAT_VISIT` | 65.210% | 检验主记录包含住院检验和门诊/体检等口径，历史结论已指出 `VISIT_ID=0/NULL` 需按门诊处理 | 拆为住院检验、门诊检验两条关系 |

这两条不应作为“全量强关系”进入正式 ER 图，但可在拆分口径验证后入图。

## 4. 多行明细导致条数不一致的说明

以下表天然是一对多明细，不能要求与主表条数一致：

- `DIAGNOSIS`：一次住院可有多条诊断。
- `ORDERS`：一次住院可有多条医嘱。
- `ORDERS_COSTS`：一条医嘱可拆多条计价项目。
- `ORDERS_EXECUTE_DETAILS`：一条医嘱可多次执行。
- `LAB_RESULT`：一个 `TEST_NO` 下有多个检验结果项目。
- `INP_BILL_DETAIL`：一次住院可有大量费用明细。
- `OUTP_BILL_ITEMS`：一张门诊收据可有多条收费项目。

因此，本轮关注的是父键覆盖率、孤儿数和重复键行数，而不是要求两表行数相等。

## 5. PAT_VISIT 字段类型概况

`MEDREC.PAT_VISIT` 当前 268 个字段，核心字段包括：

| 字段 | 类型 | 含义 | 说明 |
|---|---|---|---|
| `PATIENT_ID` | `VARCHAR2(10)` | 病人标识 | 与 `PAT_MASTER_INDEX` 关联 |
| `VISIT_ID` | `NUMBER(2,0)` | 住院次数/本次住院标识 | 与 `PATIENT_ID` 组成住院级主键 |
| `ADMISSION_DATE_TIME` | `DATE` | 入院日期及时间 | 活跃度主时间字段 |
| `DISCHARGE_DATE_TIME` | `DATE` | 出院日期及时间 | 住院日计算 |
| `DEPT_ADMISSION_TO` | `VARCHAR2(8)` | 入院科室 | 应关联科室字典 |
| `DEPT_DISCHARGE_FROM` | `VARCHAR2(8)` | 出院科室 | 应关联科室字典 |
| `CHARGE_TYPE` | `VARCHAR2(50)` | 医保类别 | 值域为中文类别 |
| `PATIENT_CLASS` | `VARCHAR2(1)` | 入院方式 | 编码字段 |
| `DISCHARGE_DISPOSITION` | `VARCHAR2(1)` | 出院方式 | 编码字段 |
| `INSUR_STATUS` | `NUMBER(1,0)` | 费用审核标志 | 状态字段 |

## 6. PAT_VISIT 时间统计

| 指标 | 值 |
|---|---:|
| 总行数 | 575841 |
| 入院时间非空 | 575841 |
| 最早入院 | 2014-01-01 00:45:48 |
| 最晚入院 | 2026-07-06 01:05:12 |
| 出院时间非空 | 574668 |
| 最早出院 | 2014-01-01 16:34:21 |
| 最晚出院 | 2026-07-05 16:35:18 |
| 平均住院日 | 8.72 天 |
| 负住院日记录 | 3 |

负住院日 3 条需要进入后续质量规则：`DISCHARGE_DATE_TIME < ADMISSION_DATE_TIME`。

## 7. PAT_VISIT 值域分布摘要

| 字段 | 主要分布 |
|---|---|
| `PATIENT_CLASS` | `2`: 296409；`1`: 218761；`5`: 27780；`4`: 22026；空值 8487 |
| `CHARGE_TYPE` | 职工医保 146190；居民医保 105536；自费 89896；省内居民 85258；异地医保 59363 |
| `DISCHARGE_DISPOSITION` | `1`: 406060；`4`: 141730；`5`: 14796；空值 2955 |
| `CLINICAL_PATHWAY` | 空值 243072；`2`: 198565；`1`: 134204 |
| `DAYSURGERY_INDICATOR` | `2`: 553694；`0`: 16647；`1`: 5500 |
| `INSUR_STATUS` | `1`: 333023；空值 242817；`0`: 1 |
| `SOURCE` | 空值 545796；`1`: 29873；`0`: 172 |

完整分布见 `pat_visit_value_distribution.csv`。

## 8. 后续质量规则建议

建议优先建立以下规则：

1. `PAT_VISIT(PATIENT_ID, VISIT_ID)` 唯一性。
2. `PAT_VISIT.PATIENT_ID` 关联 `PAT_MASTER_INDEX.PATIENT_ID` 孤儿检查。
3. `ADMISSION_DATE_TIME`、`DISCHARGE_DATE_TIME` 时间范围和负住院日检查。
4. `PATIENT_CLASS`、`DISCHARGE_DISPOSITION`、`BLOOD_TYPE`、`BLOOD_TYPE_RH` 值域字典映射。
5. `CHARGE_TYPE`、`INSURANCE_TYPE` 医保类别标准化映射。
6. `DEPT_ADMISSION_TO`、`DEPT_DISCHARGE_FROM` 科室字典有效性。
7. `DOCTOR_IN_CHARGE`、`ATTENDING_DOCTOR`、`DIRECTOR` 人员字典有效性。
8. 检验/检查关系拆分：住院口径按 `PATIENT_ID+VISIT_ID`，门诊口径另行确认。

## 9. 结论

重要表之间的主线关系整体可信，但不能把所有同名字段关系都视为一对一。住院主线、诊断、医嘱、住院费用、检验项目/结果、门诊收费明细等关系覆盖率较高；检查和检验主记录需要按门诊/住院口径拆分。

`PAT_VISIT` 可作为住院主表和质量分析优先表，下一阶段应重点做值域字典映射、负住院日、科室/人员编码有效性和主索引孤儿核查。

