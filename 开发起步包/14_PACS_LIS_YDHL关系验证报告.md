# PACS / LIS / YDHL 关系验证报告

> 数据源：数据中心 `10.10.8.216:1521/orcl`，经 8.53 跳板机 thick 模式只读执行。  
> 验证时间：2026-07-02。  
> 机器结果：`14_PACS_LIS_YDHL关系验证结果.json`。  
> 范围：仅梳理 `PACS`、`LIS`、`YDHL` 三个库；不继续扩展 CDA、EMPI 或其他库。
> 后续补验：`15_关系补验与资产回写报告.md` 已对本报告中的可提升关系做全量/分区补验；正式入图口径以 `15` 为准。

---

## 1. 总结论

1. `PACS` 与 HIS 检查表不是直接同键同步关系。`PACS.EXAMINFO` 内部可挂 `PACS.REPORT` 和 `PACS.PATIENTINFO`，但用 `ExamID/ExamAccessionID/OrderID/OrderHISNumber/ExamStudyUID` 去匹配 `HIS.EXAM_MASTER` 均未命中。
2. `LIS` 与 HIS 检验表存在阶段性同步关系，关键候选键是 `LIS.LAB_REPORT.BARCODE = HIS.LAB_TEST_MASTER.TEST_NO`，不是 `REPORTID = TEST_NO`；但 `15` 的分年补验显示该关系不能无条件全量入图。
3. `YDHL` 的护理事实表基本都通过 `PATIENT_UID` 挂 `YDHL.INPATIENTS.PAT_INDEX_NO`。`YDHL.INPATIENTS` 再通过 `MRN = HIS.PAT_MASTER_INDEX.INP_NO`，并结合 `SERIES = HIS.PAT_VISIT.VISIT_ID` 挂 HIS 住院。
4. 本轮以样本验证为主：大表使用 20 万行样本，个别双大表使用 5 万行或分批去重键验证。可作为关系图谱候选提升依据，但建议正式回写资产包前再做一次夜间全量或分区验证。

---

## 2. PACS 关系

### 2.1 PACS 内部主线

| 关系 | 样本 | 命中 | 孤儿 | 结论 |
|---|---:|---:|---:|---|
| `PACS.EXAMINFO.ReportID -> PACS.REPORT.ReportID` | 200000 | 199333 | 667 | 可用，少量历史/缺报告孤儿 |
| `PACS.EXAMINFO.PatientIntraID -> PACS.PATIENTINFO.PatientIntraID` | 200000 | 200000 | 0 | 强关系 |

PACS 库内部可以按以下主线理解：

```text
PACS.PATIENTINFO(PatientIntraID)
  -> PACS.EXAMINFO(PatientIntraID, ReportID)
      -> PACS.REPORT(ReportID)
```

### 2.2 PACS 与 HIS 检查表

| 候选关系 | 验证方式 | 命中 | 结论 |
|---|---|---:|---|
| `PACS.EXAMINFO.ExamID -> HIS.EXAM_MASTER.EXAM_NO` | 20 万样本 | 0 | 否定 |
| `PACS.EXAMINFO.PatientIntraID -> HIS.EXAM_MASTER.PATIENT_ID` | 20 万样本 | 0 | 否定 |
| `PACS.EXAMINFO.ExamAccessionID -> HIS.EXAM_MASTER.EXAM_NO` | 5000 去重键 | 0 | 否定 |
| `PACS.EXAMINFO.OrderID -> HIS.EXAM_MASTER.ORDER_ID` | 5000 去重键 | 0 | 否定 |
| `PACS.EXAMINFO.OrderHISNumber -> HIS.EXAM_MASTER.ORDER_ID` | 5000 去重键 | 0 | 否定 |
| `PACS.EXAMINFO.ExamStudyUID -> HIS.EXAM_MASTER.STUDY_UID` | 5000 去重键 | 0 | 否定 |

结论：当前 8.216 上的 `PACS` schema 与 `HIS.EXAM_MASTER/EXAM_REPORT` 不是直接同键同步。HIS 检查主线仍以 `HIS.EXAM_MASTER.EXAM_NO -> HIS.EXAM_REPORT.EXAM_NO` 为准；PACS 只能先作为独立影像系统子图保留。

---

## 3. LIS 关系

### 3.1 LIS 内部主线

| 关系 | 样本 | 命中 | 孤儿 | 结论 |
|---|---:|---:|---:|---|
| `LIS.REQ_MASTER_PAT.BARCODE -> LIS.REQ_MASTER.BARCODE` | 200000 | 200000 | 0 | 强关系 |
| `LIS.REQ_DETAIL.BARCODE -> LIS.REQ_MASTER.BARCODE` | 200000 | 200000 | 0 | 强关系 |
| `LIS.REQ_MASTER.REPORT_ID -> LIS.LAB_REPORT.REPORTID` | 200000 | 199980 | 20 | 强关系，少量未出报告/历史孤儿 |
| `LIS.LAB_REPORT.REPORTID -> LIS.LAB_RESULT.REPORTID` | 200000 | 199477 | 523 | 可用，少量无明细/历史孤儿 |

LIS 库内部主线：

```text
LIS.REQ_MASTER_PAT(BARCODE)
  -> LIS.REQ_MASTER(BARCODE, REPORT_ID)
      -> LIS.REQ_DETAIL(BARCODE)
      -> LIS.LAB_REPORT(REPORTID, BARCODE)
          -> LIS.LAB_RESULT(REPORTID)
```

### 3.2 LIS 与 HIS 检验表

| 候选关系 | 样本 | 命中 | 孤儿 | 结论 |
|---|---:|---:|---:|---|
| `LIS.LAB_REPORT.REPORTID -> HIS.LAB_TEST_MASTER.TEST_NO` | 200000 | 0 | 200000 | 否定 |
| `LIS.LAB_REPORT.BARCODE -> HIS.LAB_TEST_MASTER.TEST_NO` | 200000 | 192938 | 7062 | 可用，约 96.47% 命中 |
| `Recent HIS.LAB_TEST_MASTER.TEST_NO -> LIS.LAB_REPORT.BARCODE` | 200000 | 196519 | 3481 | 可用，约 98.26% 命中 |

HIS 检验日期分布显示：`HIS.LAB_TEST_MASTER.RESULTS_RPT_DATE_TIME` 最大到 2026-07-02；2023 年以后约 2582805 行。反向验证必须限定近期数据，否则早期 HIS 历史检验可能不在 LIS 当前库中。

结论：`LIS` 与 HIS 检验表不是完全重复表，但存在稳定同步/映射关系。HIS 侧正式检验主线仍是：

```text
HIS.LAB_TEST_MASTER(TEST_NO)
  -> HIS.LAB_TEST_ITEMS(TEST_NO)
  -> HIS.LAB_RESULT(TEST_NO)
```

如需要追溯 LIS 原始申请/报告，可保留候选边并按时间/接口口径拆分：

```text
HIS.LAB_TEST_MASTER.TEST_NO = LIS.LAB_REPORT.BARCODE
```

注意：`15` 已补验发现 2024 年后该关系命中率明显下降，不应作为无条件正式边。

---

## 4. YDHL 关系

### 4.1 YDHL 与 HIS 住院

| 候选关系 | 样本 | 命中 | 孤儿 | 结论 |
|---|---:|---:|---:|---|
| `YDHL.INPATIENTS.PATIENT_ID+SERIES -> HIS.PAT_VISIT.PATIENT_ID+VISIT_ID` | 200000 | 678 | 199322 | 否定，`YDHL.PATIENT_ID` 不是 HIS 患者 ID |
| `YDHL.INPATIENTS.MRN -> HIS.PAT_MASTER_INDEX.INP_NO` | 200000 | 198863 | 1137 | 可用，约 99.43% 命中 |
| `YDHL.INPATIENTS.MRN+SERIES -> HIS.PAT_VISIT` | 200000 | 198728 | 1272 | 可用，约 99.36% 命中 |

正确 HIS 关联口径：

```text
YDHL.INPATIENTS.MRN = HIS.PAT_MASTER_INDEX.INP_NO
YDHL.INPATIENTS.SERIES = HIS.PAT_VISIT.VISIT_ID
```

不要使用 `YDHL.INPATIENTS.PATIENT_ID` 直接挂 HIS `PATIENT_ID`。

### 4.2 YDHL 内部护理事实表

| 关系 | 样本 | 命中 | 孤儿 | 结论 |
|---|---:|---:|---:|---|
| `MCS_ASSESS_FORM.PATIENT_UID -> INPATIENTS.PAT_INDEX_NO` | 200000 | 200000 | 0 | 强关系 |
| `MCS_DOC_FORM.PATIENT_UID -> INPATIENTS.PAT_INDEX_NO` | 200000 | 200000 | 0 | 强关系 |
| `MCS_VITAL_INFO.PATIENT_UID -> INPATIENTS.PAT_INDEX_NO` | 200000 | 200000 | 0 | 强关系 |
| `MCS_DOC_INOUT.PATIENT_UID -> INPATIENTS.PAT_INDEX_NO` | 200000 | 199988 | 12 | 强关系，少量历史孤儿 |
| `MCS_EVENT_INFO.PATIENT_UID -> INPATIENTS.PAT_INDEX_NO` | 200000 | 199996 | 4 | 强关系，少量历史孤儿 |
| `MCS_NURSING_PLAN.PATIENT_UID -> INPATIENTS.PAT_INDEX_NO` | 2325 | 2325 | 0 | 强关系 |
| `MCS_DAILY_SETTLE_DETAIL.PATIENT_UID -> INPATIENTS.PAT_INDEX_NO` | 200000 | 200000 | 0 | 强关系 |
| `MCS_PATROL_INFO.PATIENT_UID -> INPATIENTS.PAT_INDEX_NO` | 200000 | 200000 | 0 | 强关系 |

### 4.3 YDHL 明细表

| 关系 | 样本 | 命中 | 孤儿 | 结论 |
|---|---:|---:|---:|---|
| `MCS_ASSESS_FORM_RECORD.FORM_ID -> MCS_ASSESS_FORM.ID` | 200000 | 200000 | 0 | 强关系 |
| `MCS_DOC_FORM_RECORDS.FORM_ID -> MCS_DOC_FORM.ID` | 200000 | 200000 | 0 | 强关系 |

YDHL 深层护理记录主线：

```text
HIS.PAT_MASTER_INDEX(INP_NO)
  -> HIS.PAT_VISIT(VISIT_ID)
      <- YDHL.INPATIENTS(MRN, SERIES, PAT_INDEX_NO)
          -> YDHL.MCS_ASSESS_FORM(PATIENT_UID)
              -> YDHL.MCS_ASSESS_FORM_RECORD(FORM_ID)
          -> YDHL.MCS_DOC_FORM(PATIENT_UID)
              -> YDHL.MCS_DOC_FORM_RECORDS(FORM_ID)
          -> YDHL.MCS_VITAL_INFO(PATIENT_UID)
          -> YDHL.MCS_DOC_INOUT(PATIENT_UID)
          -> YDHL.MCS_EVENT_INFO(PATIENT_UID)
          -> YDHL.MCS_PATROL_INFO(PATIENT_UID)
          -> YDHL.MCS_NURSING_PLAN(PATIENT_UID)
```

---

## 5. 可提升关系建议

建议下一轮回写正式资产包前，优先对以下关系做夜间全量或分区验证：

1. `LIS.LAB_REPORT.BARCODE -> HIS.LAB_TEST_MASTER.TEST_NO`
2. `YDHL.INPATIENTS.MRN+SERIES -> HIS.PAT_VISIT`（经 `HIS.PAT_MASTER_INDEX.INP_NO`）
3. `YDHL.MCS_DOC_FORM.PATIENT_UID -> YDHL.INPATIENTS.PAT_INDEX_NO`
4. `YDHL.MCS_ASSESS_FORM_RECORD.FORM_ID -> YDHL.MCS_ASSESS_FORM.ID`
5. `YDHL.MCS_DOC_FORM_RECORDS.FORM_ID -> YDHL.MCS_DOC_FORM.ID`
6. `PACS.EXAMINFO.PatientIntraID -> PACS.PATIENTINFO.PatientIntraID`
7. `PACS.EXAMINFO.ReportID -> PACS.REPORT.ReportID`

暂不建议提升：

- `PACS.EXAMINFO -> HIS.EXAM_MASTER` 的所有直接候选边，本轮均未命中。
- `YDHL.INPATIENTS.PATIENT_ID -> HIS.PAT_MASTER_INDEX.PATIENT_ID`，字段语义不一致。
- `LIS.LAB_REPORT.REPORTID -> HIS.LAB_TEST_MASTER.TEST_NO`，明确不成立。
