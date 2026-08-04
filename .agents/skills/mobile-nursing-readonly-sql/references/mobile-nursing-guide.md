# 移动护理查询指南

## 权威范围

- 一级系统：移动护理（`MOBILE_NURSING`）。
- 数据库：Oracle 11g。
- Owner：`LUNA_MCS_SDSEY`。
- 活库证据：508 表、59 视图、9981 字段；无声明外键。
- 独立源端与数据中心内部 `YDHL` 是不同物理来源，不得混写为同一连接。

## 主题对象

| 主题 | 核心对象 |
|---|---|
| 患者住院底座 | `INPATIENTS` |
| 护理文书 | `MCS_DOC_FORM`、`MCS_DOC_FORM_RECORDS`、`MCS_DOC_TEMPLATE` |
| 体征与护理事件 | `MCS_VITAL_INFO`、`MCS_EVENT_INFO` |
| 护理评估 | `MCS_ASSESS_FORM*`、`MCS_DIABETES_ASSESS*` |
| PICC | `MCS_PICC_*` |
| 伤口/造口 | `MCS_WOUND_*`、`MCS_STOMA_*` |
| 交班报告 | `MCS_WARDREPORT_*`、`MCS_DAILY_SETTLE_*` |

## 已验证主线

| 子对象 | 父对象 | JOIN | 状态 |
|---|---|---|---|
| `MCS_DOC_FORM` | `INPATIENTS` | `PATIENT_UID = PAT_INDEX_NO` | verified |
| `MCS_DOC_FORM_RECORDS` | `MCS_DOC_FORM` | `FORM_ID = ID` | verified |
| `MCS_DOC_FORM` | `MCS_DOC_TEMPLATE` | `TEMPLATE_CODE = CODE` | verified |
| `MCS_VITAL_INFO` | `INPATIENTS` | `PATIENT_UID = PAT_INDEX_NO` | verified |
| `MCS_DOC_FORM_RECORDS` | `INPATIENTS` | `PATIENT_UID = PAT_INDEX_NO` | verified |
| `MCS_EVENT_INFO` | `INPATIENTS` | `PATIENT_UID = PAT_INDEX_NO` | verified |

本库内部优先使用 `PATIENT_UID/PAT_INDEX_NO`。`MRN + SERIES` 适合展示和跨系统核对，但不得仅用姓名、床号或住院号单字段关联。

扩展表常见模式是 `XFORM_SOURCE_ID → 主表.ID`。仅 86 号报告中已验证的 PICC、糖尿病评估和造口登记关系可直接采用；新增对象必须重新验证。

## 不得提升为强关系

- `MCS_STOMA_ASSESS_S → MCS_STOMA_ASSESS`：partial。
- `MCS_WOUND_ASSESS_S → MCS_WOUND_ASSESS`：partial。
- `MCS_EVENT_INFO.PATIENT_UID → MCS_HIS_PATIENT.PATIENT_UID`：样本不匹配，禁止采用。
- `MCS_HIS_PATIENT` 当前不能作为权威患者底座。
- 交班报告候选关系无非空样本，只能作为结构候选。

## 大表红线

`MCS_DOC_FORM_RECORDS`、`MCS_ASSESS_FORM_RECORD`、`MCS_ORDER_SCHEDULE_PROCESS`、`MCS_ORDER_SCHEDULE`、`MCS_PATROL_INFO`、`MCS_DOC_FORM_OPERATION_LOG`、`MCS_VITAL_INFO`、`MCS_DOC_FORM` 禁止无边界扫描。优先以 `PATIENT_UID`、`FORM_ID`、`TEMPLATE_CODE`、病区和左闭右开时间范围收窄。

## SQL 规则

- 使用全限定名 `LUNA_MCS_SDSEY.TABLE_NAME`。
- 显式投影字段，禁止 `SELECT *`。
- Oracle 11g 使用外层 `ROWNUM <= :max_rows`。
- 日期过滤优先 `column >= :start_time AND column < :end_time`，不要对索引列套 `TRUNC`。
- 核查版 SQL 可写中文注释；送受控执行器前生成逻辑一致的去注释副本。
- 不把患者姓名、患者编号、住院号、电话、证件号和地址作为 AI 输出。
