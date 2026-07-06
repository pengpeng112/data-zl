> 类别：关系验证

# ready_his 候选关系补验与旧文档对照报告

## 目标

本轮针对 `32_ready_his治理导入包` 中仍待验证的高价值候选关系，结合两份历史表结构文档做补验：

- `系统表结构/HIS系统数据库表结构.md`
- `系统表结构/HIS系统药房药库表设计文档.md`

验证库为 `10.10.10.15:1521/his`，通过 8.53 跳板机只读连接执行，仅使用 `SELECT`。本轮不抽取业务明细，只统计样本量、匹配量、孤儿量和匹配率。

## 旧文档参考结论

旧 HIS 表结构文档明确覆盖本轮主线表：`ORDERS_COSTS`、`EXAM_MASTER`、`LAB_TEST_MASTER`、`DRUG_PRESC_MASTER`、`DRUG_PRESC_DETAIL`、`DRUG_DISPENSE_REC`、`OUTP_RCPT_MASTER`。药房药库文档补充了药房发药申请表、`PRESC_NO`、`ORDER_NO`、`ORDER_SUB_NO`、`PATIENT_ID`、`VISIT_ID` 等字段口径。

这些文档可作为字段含义依据，但字段完整性和关系有效性仍以 `ready_his` 活库元数据与本轮抽样验证为准。

## 验证范围与方法

- 常规候选：每条关系抽取前 10,000 条非空键记录，用 `EXISTS` 判断目标表是否存在对应键。
- 大表医嘱桥接：对 `DRUG_DISPENSE_REC`、`DRUG_DISPENSE_REC_DISPDATE`，将原 `ORDER_NO+ORDER_SUB_NO` 升级为更严格的 `PATIENT_ID+VISIT_ID+ORDER_NO+ORDER_SUB_NO`。
- `DOCT_DRUG_PRESC_DETAIL` 自身无 `PATIENT_ID/VISIT_ID`，补验时先经 `DOCT_DRUG_PRESC_MASTER.PRESC_NO` 取住院键，再挂 `ORDERS`。

## 本轮结论

### 可进入正式关系

以下 10 条样本零孤儿，建议追加到治理导入包正式关系，置信度按 `A-` 标记，验证等级 `sample_10k`：

| 关系 | 关联 |
|---|---|
| CAND0545 | `PHARMACY.DRUG_DISPENSE_REC(PATIENT_ID,VISIT_ID)` -> `MEDREC.PAT_VISIT` |
| CAND0546_STRICT | `PHARMACY.DRUG_DISPENSE_REC(PATIENT_ID,VISIT_ID,ORDER_NO,ORDER_SUB_NO)` -> `ORDADM.ORDERS` |
| CAND0556 | `PHARMACY.DRUG_PRESC_DETAIL(ORDER_NO,ORDER_SUB_NO)` -> `ORDADM.ORDERS` |
| CAND0561 | `PHARMACY.DRUG_PRESC_MASTER(PATIENT_ID,VISIT_ID)` -> `MEDREC.PAT_VISIT` |
| CAND0562 | `PHARMACY.DRUG_PRESC_MASTER(RCPT_NO)` -> `OUTPBILL.OUTP_RCPT_MASTER` |
| CAND0526 | `PHARMACY.DOCT_DRUG_PRESC_MASTER(PATIENT_ID,VISIT_ID)` -> `MEDREC.PAT_VISIT` |
| CAND0551 | `PHARMACY.DRUG_DISPENSE_REC_DISPDATE(PATIENT_ID,VISIT_ID)` -> `MEDREC.PAT_VISIT` |
| CAND0552_STRICT | `PHARMACY.DRUG_DISPENSE_REC_DISPDATE(PATIENT_ID,VISIT_ID,ORDER_NO,ORDER_SUB_NO)` -> `ORDADM.ORDERS` |
| CAND0234 | `LAB.LAB_TEST_MASTER(RCPT_NO)` -> `OUTPBILL.OUTP_RCPT_MASTER` |
| CAND0495 | `OUTPBILL.OUTP_BILL_ITEMS(RCPT_NO)` -> `OUTPBILL.OUTP_RCPT_MASTER` |

### 进入人工复核

`CAND0025`：`EXAM.EXAM_BILL_ITEMS(EXAM_NO)` -> `EXAM.EXAM_MASTER(EXAM_NO)`，10,000 样本中 9,994 匹配，孤儿 6，匹配率 99.94%。建议进入 `AssetRelationReview`，由业务确认是否允许历史/撤销检查费用形成少量孤儿。

### 暂不入正式关系

- `CAND0029`：`EXAM.EXAM_ITEMS(EXAM_NO)` -> `EXAM.EXAM_MASTER`，匹配率 80.9%，不适合作为正式强关系。
- `CAND0231`：`LAB.LAB_TEST_ITEMS_DETAIL(TEST_NO)` -> `LAB.LAB_TEST_MASTER`，匹配率 95.6%，需进一步拆分有效状态或历史分区。
- `CAND0524_VIA_MASTER`：`DOCT_DRUG_PRESC_DETAIL` 经主表挂 `ORDERS`，1,000 样本匹配率 14.3%，说明待发药明细不能简单按医嘱键入图。

## 对治理导入的影响

下一步导入治理系统时，应把本轮 10 条零孤儿关系追加为正式关系；把 `CAND0025` 放入人工复核；其余低匹配或超时的原候选保留在候选池，不进入正式图谱。`ORDER_NO+ORDER_SUB_NO` 单独挂 `ORDERS` 对部分大表执行代价高，药房摆药主线应优先采用四字段严格键。

已生成 33 增量导入文件：

- `数据资产_HIS_READY治理导入包/governance_relations_formal_batch33.csv`
- `数据资产_HIS_READY治理导入包/governance_relation_reviews_batch33.csv`
- `数据资产_HIS_READY治理导入包/governance_candidate_rejections_batch33.csv`
