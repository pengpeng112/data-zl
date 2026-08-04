# Docare 手术麻醉查询指南

## 权威范围

- 一级系统：Docare手术麻醉（`DOCARE`）。
- 数据库：Oracle 11g，多 Owner。
- `MEDSURGERY`：手术排班、实际手术、麻醉、监护、镇痛、耗材。
- `MEDCOMM`：患者主索引、就诊、公共字典和 HIS 接口。
- `MEDICU`：ICU 护理与配置；当前大量对象为空。
- 80 号活库证据共 594 表、52 视图、10529 字段。

不要使用登录账号的默认 Schema；SQL 必须写 `OWNER.TABLE_NAME`。Docare 与数据中心 `SM` 可存在同步关系，但必须分别查询、分步对账，不得假设同名表实时完全一致。

## 核心关系

| 子对象 | 父对象 | 完整 JOIN 键 | 证据 |
|---|---|---|---|
| `MEDCOMM.MED_PAT_VISIT` | `MEDCOMM.MED_PAT_MASTER_INDEX` | `PATIENT_ID` | 100%样本命中 |
| `MEDSURGERY.MED_OPERATION_SCHEDULE` | `MEDCOMM.MED_PAT_VISIT` | `PATIENT_ID,VISIT_ID` | 98%，有历史/取消孤儿 |
| `MEDSURGERY.MED_SCHEDULED_OPERATION_NAME` | `MED_OPERATION_SCHEDULE` | `PATIENT_ID,VISIT_ID,SCHEDULE_ID` | 99.98% |
| `MEDSURGERY.MED_OPERATION_MASTER` | `MEDCOMM.MED_PAT_VISIT` | `PATIENT_ID,VISIT_ID` | 99.41% |
| `MEDSURGERY.MED_OPERATION_NAME` | `MED_OPERATION_MASTER` | `PATIENT_ID,VISIT_ID,OPER_ID` | 99.56% |
| 麻醉计划/总结/事件/监护/镇痛/交接 | `MED_OPERATION_MASTER` | `PATIENT_ID,VISIT_ID,OPER_ID` | 99.26%–100% |

不得只用患者、姓名、手术名称或医生姓名关联。排班使用 `SCHEDULE_ID`，实际手术使用 `OPER_ID`，两种粒度不能互换。

## 大表红线

以下对象必须先按患者/访视/手术键、检验单号或时间范围过滤：

- `MEDSURGERY.MED_CUSTOM_DATA`
- `MEDSURGERY.MED_ANESTHESIA_EVENT_BACK`
- `MEDCOMM.MED_VITAL_SIGN_MERGE`
- `MEDCOMM.MED_LAB_RESULT`
- `MEDSURGERY.MED_QIXIE_QINGDIAN`
- `MEDSURGERY.MED_PATIENT_MONITOR_DATA`
- `MEDSURGERY.MED_APPLICATION_AUDIT_TRAIL`
- `MEDSURGERY.MED_PAT_MONITOR_DATA`
- `MEDSURGERY.MED_ANESTHESIA_EVENT`

检验结果必须按检验单号收窄。监护数据至少使用完整手术键，最好再加时间范围。

## SQL 规则

- 显式投影字段，禁止 `SELECT *`。
- Oracle 11g 使用外层 `ROWNUM <= :max_rows`。
- 日期使用左闭右开范围，避免对索引列套函数。
- 核查版可写中文注释；受控执行版本保持同一逻辑并去除注释。
- 对关系命中率低于 100% 的 JOIN，应根据业务目的明确使用 `INNER JOIN` 还是 `LEFT JOIN`，并说明孤儿处置。
