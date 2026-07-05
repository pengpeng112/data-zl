> 类别：关系验证

# HIS 主业务 owner 关系补验报告

> 范围：`10.10.10.15:1521/his` 业务库多 owner 源端关系补验。  
> 配套结果：`21_HIS主业务owner关系补验结果.json`。  
> 安全口径：只执行 `SELECT`；大表仅抽样或按父键限定；报告只保留聚合计数，不输出患者、证件、电话、姓名等明细。

---

## 1. 结论

本次补验确认 HIS 业务库源端主业务 owner 的核心关系基本成立，且与数据中心 ODS 的主线口径一致。

| 主线 | 可用主键/关联键 | 结论 |
|---|---|---|
| 患者 | `PATIENT_ID` | `MEDREC.PAT_MASTER_INDEX` 是患者主索引源端表 |
| 住院 | `PATIENT_ID + VISIT_ID` | `MEDREC.PAT_VISIT` 是住院主表，诊断、手术、医嘱、费用、住院在院均可挂接 |
| 医嘱 | `PATIENT_ID + VISIT_ID + ORDER_NO + ORDER_SUB_NO` | `ORDADM.ORDERS_COSTS` 可挂 `ORDADM.ORDERS` |
| 检验 | `TEST_NO` | `LAB_TEST_ITEMS`、`LAB_RESULT` 可挂 `LAB_TEST_MASTER`；`VISIT_ID=0/NULL` 需拆分门诊/其他口径 |
| 检查 | `EXAM_NO` | `EXAM_REPORT`、`EXAM_BILL_ITEMS` 可挂 `EXAM_MASTER`；`EXAM_ITEMS` 有较多孤儿，不宜无条件强入图 |
| 住院费用 | `PATIENT_ID + VISIT_ID`、`RCPT_NO` | `INP_SETTLE_MASTER` 可挂住院，`INP_BILL_DETAIL` 样本验证可挂住院和结算主表 |
| 门诊费用 | `RCPT_NO`、`PATIENT_ID` | `OUTP_BILL_ITEMS` 样本可挂收据主表；收据主表样本可挂患者主索引 |

本专题不直接回写 `数据资产_资产包/relationships.csv`：现有资产包以 `8.216` 数据中心 ODS 为主，本次验证的是 `10.10.10.15/his` 源端多 owner 关系。后续如果资产系统支持多源资产，应单独建立 HIS 源端资产层，或扩展现有图谱的 `source_system/source_owner` 维度后再回写。

---

## 2. 验证概览

| 领域 | 验证项 | 结果摘要 |
|---|---:|---|
| `MEDREC` | 3 | 患者、住院、诊断、手术主线成立；`OPERATION.OPER_ID` 全空 |
| `INPADM` | 2 | 在院表全量基本可挂住院；入出转日志样本可挂住院 |
| `ORDADM` | 2 | 医嘱样本可挂住院；医嘱费用样本可挂医嘱 |
| `LAB` | 4 | 检验主单非零住院号子集可挂住院；结果表样本可挂主单；项目明细存在部分弱关系 |
| `EXAM` | 4 | 检查主单非零住院号子集可挂住院；报告和计费项目可挂主单；检查项目表孤儿较多 |
| `INPBILL` | 3 | 住院结算全量可挂住院；费用明细样本可挂住院和结算 |
| `OUTPADM/OUTPBILL` | 3 | 门诊挂号可挂患者；门诊收费样本可挂收据主表和患者 |

---

## 3. 关键验证结果

### 3.1 住院主线

| ID | 关系 | 总量/样本 | 匹配 | 孤儿 | 结论 |
|---|---|---:|---:|---:|---|
| M01 | `MEDREC.PAT_VISIT.PATIENT_ID -> MEDREC.PAT_MASTER_INDEX.PATIENT_ID` | 575563 | 575560 | 3 | 通过 |
| M02 | `MEDREC.DIAGNOSIS(PATIENT_ID,VISIT_ID) -> MEDREC.PAT_VISIT` | 3330805 | 3330597 | 208 | 通过 |
| M03 | `MEDREC.OPERATION(PATIENT_ID,VISIT_ID) -> MEDREC.PAT_VISIT` | 528803 | 528787 | 16 | 通过；`OPER_ID` 全空 |
| M04 | `INPADM.PATS_IN_HOSPITAL(PATIENT_ID,VISIT_ID) -> MEDREC.PAT_VISIT` | 1262 | 1260 | 2 | 通过 |
| M05 | `INPADM.ADT_LOG(PATIENT_ID,VISIT_ID) -> MEDREC.PAT_VISIT` | 200000 样本 | 199983 | 17 | 样本通过 |

`MEDREC.OPERATION.OPER_ID` 全部为空，与数据中心 ODS 的 `HIS.OPERATION.OPER_ID` 结论一致。因此 HIS 手术表只能按住院主线挂接，不能用 `OPER_ID` 与手麻手术一对一关联。

### 3.2 医嘱主线

| ID | 关系 | 样本 | 匹配 | 孤儿 | 结论 |
|---|---|---:|---:|---:|---|
| O01 | `ORDADM.ORDERS(PATIENT_ID,VISIT_ID) -> MEDREC.PAT_VISIT` | 200000 | 199929 | 71 | 样本通过 |
| O02 | `ORDADM.ORDERS_COSTS -> ORDADM.ORDERS` by `PATIENT_ID,VISIT_ID,ORDER_NO,ORDER_SUB_NO` | 200000 | 199980 | 20 | 样本通过 |

`ORDADM.ORDERS` 约 4100 万行，本次仅做限定样本验证。后续做医嘱专题时，应按日期、住院号或患者限定查询。

### 3.3 检验主线

| ID | 关系 | 总量/样本 | 匹配 | 孤儿/例外 | 结论 |
|---|---|---:|---:|---:|---|
| L01 | `LAB.LAB_TEST_MASTER(PATIENT_ID,VISIT_ID) -> MEDREC.PAT_VISIT`，仅非零 `VISIT_ID` | 9143658 | 5800779 | 非零孤儿 2402；`VISIT_ID=0/NULL` 3340477 | 子集通过 |
| L02 | `LAB.LAB_TEST_ITEMS.TEST_NO -> LAB.LAB_TEST_MASTER.TEST_NO` | 9611257 | 9609547 | 1710 | 通过 |
| L03 | `LAB.LAB_RESULT.TEST_NO -> LAB.LAB_TEST_MASTER.TEST_NO` | 200000 样本 | 199996 | 4 | 样本通过 |
| L04 | `LAB.LAB_TEST_ITEMS_DETAIL(TEST_NO,ITEM_NO) -> LAB.LAB_TEST_ITEMS(TEST_NO,ITEM_NO)` | 4224849 | 4105965 | 挂主单孤儿 101499 | 部分通过 |

检验仍需保持既有拆分规则：`VISIT_ID` 为有效住院次数时可挂住院；`VISIT_ID=0/NULL` 的检验不能强行挂 `PAT_VISIT`，应另按门诊、体检或接口来源拆分。

### 3.4 检查主线

| ID | 关系 | 总量 | 匹配 | 孤儿/例外 | 结论 |
|---|---|---:|---:|---:|---|
| E01 | `EXAM.EXAM_MASTER(PATIENT_ID,VISIT_ID) -> MEDREC.PAT_VISIT`，仅非零 `VISIT_ID` | 3415735 | 2012933 | 非零孤儿 378；`VISIT_ID=0/NULL` 1402424 | 子集通过 |
| E02 | `EXAM.EXAM_REPORT.EXAM_NO -> EXAM.EXAM_MASTER.EXAM_NO` | 1337247 | 1337192 | 55 | 通过 |
| E03 | `EXAM.EXAM_ITEMS.EXAM_NO -> EXAM.EXAM_MASTER.EXAM_NO` | 4410757 | 3893397 | 517360 | 部分通过 |
| E04 | `EXAM.EXAM_BILL_ITEMS.EXAM_NO -> EXAM.EXAM_MASTER.EXAM_NO` | 5808197 | 5804520 | 3677 | 通过 |

检查与数据中心 ODS 的结论一致：`EXAM_REPORT` 必须经 `EXAM_NO` 关联主表；`EXAM_MASTER` 需要拆住院和非住院子集。`EXAM_ITEMS` 孤儿较多，不建议作为无条件强关系入图。

### 3.5 费用与门诊主线

| ID | 关系 | 总量/样本 | 匹配 | 孤儿 | 结论 |
|---|---|---:|---:|---:|---|
| B01 | `INPBILL.INP_SETTLE_MASTER(PATIENT_ID,VISIT_ID) -> MEDREC.PAT_VISIT` | 626085 | 626033 | 52 | 通过 |
| B02 | `INPBILL.INP_BILL_DETAIL(PATIENT_ID,VISIT_ID) -> MEDREC.PAT_VISIT` | 200000 样本 | 200000 | 0 | 样本通过 |
| B03 | `INPBILL.INP_BILL_DETAIL.RCPT_NO -> INPBILL.INP_SETTLE_MASTER.RCPT_NO` | 200000 样本 | 199966 | 0 | 样本通过 |
| B04 | `OUTPADM.CLINIC_MASTER.PATIENT_ID -> MEDREC.PAT_MASTER_INDEX.PATIENT_ID` | 5704923 | 5704870 | 53 | 通过 |
| B05 | `OUTPBILL.OUTP_BILL_ITEMS.RCPT_NO -> OUTPBILL.OUTP_RCPT_MASTER.RCPT_NO` | 200000 样本 | 200000 | 0 | 样本通过 |
| B06 | `OUTPBILL.OUTP_RCPT_MASTER.PATIENT_ID -> MEDREC.PAT_MASTER_INDEX.PATIENT_ID` | 200000 样本 | 199941 | 59 | 样本通过 |

`INPBILL.INP_BILL_DETAIL` 约 2.2 亿行，`OUTPBILL.OUTP_BILL_ITEMS` 约 3000 万行，本次只做样本关系验证。后续费用专题必须按患者、就诊、结算号或时间范围限定。

---

## 4. 入图建议

1. 对 HIS 源端关系图谱，优先建立 `MEDREC.PAT_MASTER_INDEX -> MEDREC.PAT_VISIT -> 诊断/手术/医嘱/检验/检查/费用` 主干。
2. 对 `LAB_TEST_MASTER`、`EXAM_MASTER`，继续使用“非零住院 `VISIT_ID` 子集可挂住院，`VISIT_ID=0/NULL` 拆分处理”的规则。
3. 对 `LAB_TEST_ITEMS_DETAIL` 和 `EXAM_ITEMS`，暂不作为无条件强关系；可标为弱关系或在后续专题里按时间、状态、项目类别再拆分。
4. 对 `OPERATION.OPER_ID`，保持禁用；HIS 手术与手麻手术仍不能用该字段强关联。
5. 暂不回写 8.216 ODS 资产包；等资产系统支持多源 owner 后，单独导入本专题作为 HIS 源端关系层。

---

## 5. 后续工作

1. 以 `21` 为 HIS 源端主线基线，继续做 `MEDREC/ORDADM/LAB/EXAM/INPBILL/OUTPBILL` 的字段级主题分类和 ODS 差异清单。
2. 若要形成 HIS 源端资产包，需扩展现有 `tables.csv/relationships.csv` 的源库维度，避免与 `8.216` ODS 同名表混淆。
3. 对费用、医嘱、检验结果等巨表，后续只做按就诊或时间限定的专题抽样，禁止全表扫描。
