> 类别：资产

# 32 ready_his 治理导入包生成报告

> 日期：2026-07-05  
> 输入：`31` ready_his 活库复核资产包 + `23/25` 已确认 HIS 源端纳入/排除口径。  
> 输出目录：`数据资产_HIS_READY治理导入包/`。  
> 用途：面向当前 FastAPI/Vue 数据治理系统导入，字段名对齐 `AssetTable/AssetColumn/AssetRelation/AssetRelationReview`。

---

## 1. 生成结果

| 文件 | 内容 |
|---|---|
| `governance_tables.csv` | 表资产导入清单，含 `include_status/governance_import_status/primary_key_status/scope_note` |
| `governance_columns.csv` | 字段资产导入清单，基于 ready_his 活库 24726 字段 |
| `governance_relations_formal.csv` | 可直接进入正式关系表的 7 条样本全匹配关系 |
| `governance_relation_reviews.csv` | 15 条带少量孤儿的主线关系，建议进入复核表 |
| `governance_candidate_relations_ranked.csv` | 578 条字段名候选关系，带评分和下一步建议 |
| `governance_import_summary.json` | 机器可读汇总 |

---

## 2. 口径合并

本包不是简单复用 `31` 的快速分类，而是重新套用 `23/25` 的业务确认规则：

| 状态 | 数量 | 说明 |
|---|---:|---|
| `included` | 473 | 第一版纳入资产 |
| `candidate` | 560 | 保留候选，待人工裁剪 |
| `excluded` | 201 | 第一版业务事实图谱排除，但保留原因 |

表角色：

| 角色 | 数量 |
|---|---:|
| `dimension` | 443 |
| `core_fact` | 26 |
| `execution_fact` | 2 |
| `payment_fact` | 1 |
| `inpatient_management_fact` | 1 |
| `candidate` | 560 |
| `excluded` | 201 |

---

## 3. 与旧资产包的关键差异

| 项 | 旧 HIS 源端资产包 | ready_his 治理导入包 |
|---|---:|---:|
| 表 | 1234 | 1234 |
| 字段 | 19831 | 24726 |
| 关系 | 33 | 7 正式 + 15 复核 + 578 候选 |

结论：表范围稳定，但字段快照已更新。后续字段治理、中文注释治理、质量规则绑定应以 `governance_columns.csv` 为准。

---

## 4. 关系导入策略

| 目标表 | 数量 | 进入条件 |
|---|---:|---|
| `AssetRelation` | 7 | `sample_pass`，样本全匹配 |
| `AssetRelationReview` | 15 | `sample_pass_with_orphans`，匹配率均超过 99%，但有少量孤儿 |
| 候选关系池 | 578 | 字段名推断，需排序后专题验证 |

高分候选关系优先验证方向：

1. 药品/处方/发药链路：`DRUG_USER.INP_ORDER_EXECDATA`、`PHARMACY.DRUG_DISPENSE_REC`、`DRUG_PRESC_MASTER/DETAIL`。
2. 医嘱执行链路：`ORDADM.ORDERS_EXECUTE_DETAILS`、`ORDADM.ORDERS_COSTS`。
3. 检验/检查挂就诊：`LAB_TEST_MASTER`、`EXAM_MASTER/EXAM_BILL_ITEMS`。
4. 收据/费用桥接：`RCPT_NO` 到 `OUTPBILL.OUTP_RCPT_MASTER`，以及住院费用明细。

---

## 5. 导入前风险

1. 353 张表缺主键标识，其中纳入表缺主键 106 张；应生成主键治理任务。
2. `governance_relation_reviews.csv` 中 15 条关系不建议直接标为“零孤儿强关系”，应保留样本指标。
3. 578 条候选关系不能批量入正式图谱，建议先取 `recommended_action=validate_next` 的 203 条做第二轮验证。
4. 业务密码只允许通过运行时 `credential_ref` 或环境变量提供，不进入资产包。

---

## 6. 建议导入顺序

1. upsert `AssetSystem(HIS_SOURCE)` 与 `AssetDataSource(his_ready_10_10_10_15)`。
2. 导入 `governance_tables.csv`。
3. 导入 `governance_columns.csv`。
4. 导入 `governance_relations_formal.csv` 到正式关系表。
5. 导入 `governance_relation_reviews.csv` 到关系复核表。
6. 将 `governance_candidate_relations_ranked.csv` 作为候选验证任务池，不直接入正式图谱。

