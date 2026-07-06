> 类别：关系验证
# secondary_relationships 分级修订报告

## 1. 修订依据

根据用户确认和后续复核结果，本文件用于说明 HIS_READY 当前可采用关系、延后关系和门诊强键补充结论。

- 原 `secondary_relationships_B.csv` 和 `secondary_relationships_C.csv` 当前可采用，已提升并合并到 `secondary_relationships_A_rechecked.csv`。
- 原 `secondary_relationships_D.csv` 主要为 HIS 与其他系统或周边表之间的关系，当前暂不进入 HIS_READY 正式关系图谱，等待后续提供其他系统数据库后再验证。
- 2026-07-06 已补充门诊检验/检查按收据号挂接医嘱明细的强键关系，并纳入最终治理导入包。

## 2. 修订方式

保留原始 `secondary_relationships_A/B/C/D.csv` 作为历史证据，不覆盖原文件。当前复核版文件如下：

| 文件 | 用途 |
|---|---|
| `secondary_relationships_A_rechecked.csv` | 当前可采用关系清单，合并原 A+B+C |
| `secondary_relationships_B_rechecked.csv` | 为空，表示原 B 已被采纳 |
| `secondary_relationships_C_rechecked.csv` | 为空，表示原 C 已被采纳 |
| `secondary_relationships_D_rechecked.csv` | 延后跨系统关系，当前不入 HIS_READY 图谱 |
| `secondary_relationships_all_graded_rechecked.csv` | 当前完整复核关系清单 |
| `secondary_relationships_recheck_summary.json` | 汇总结论 |
| `governance_relations_formal_final.csv` | 最终治理导入正式关系，含门诊强键 2 条 |

## 3. 汇总结论

| 类型 | 原数量 | 复核后处理 |
|---|---:|---|
| A | 16 | 保留为当前可采用 |
| B | 16 | 用户确认可采用，提升并合并到 A_rechecked |
| C | 3 | 用户确认可采用，提升并合并到 A_rechecked |
| D | 4 | 延后，等待其他系统库信息后再分析 |

`A_rechecked` 为 34 条。原 A+B+C 合计 35 条，其中 1 条重复关系已去重。

最终治理导入包在 `A_rechecked` 基础上新增 2 条门诊强键，正式关系共 36 条。

## 4. 门诊检验/检查强键补充

已验证门诊检验/检查可按 `PATIENT_ID + RCPT_NO` 精确挂接 `OUTPBILL.OUTP_ORDER_DESC`，当前已进入 `governance_relations_formal_final.csv`。

| 关系ID | 业务域 | 主表 | 主表字段 | 子表 | 子表字段 | 验证等级 | 验证状态 | 关键指标 | 处理结论 |
|---|---|---|---|---|---|---|---|---|---|
| `OUT_LAB_RCPT` | 检验 | `OUTPBILL.OUTP_ORDER_DESC` | `PATIENT_ID+RCPT_NO` | `LAB.LAB_TEST_MASTER` | `PATIENT_ID+RCPT_NO` | `sample_100k` | `sample_pass` | 有收据比例 94.1%，匹配 94795/100000，孤儿 2，匹配率 99.998% | 纳入正式关系 |
| `OUT_EXAM_RCPT` | 检查 | `OUTPBILL.OUTP_ORDER_DESC` | `PATIENT_ID+RCPT_NO` | `EXAM.EXAM_MASTER` | `PATIENT_ID+RCPT_NO` | `sample_100k` | `sample_pass` | 有收据比例 99.99%，匹配 99975/100000，孤儿 3，匹配率 99.997% | 纳入正式关系 |

注意：`ORDER_ID` 在该场景不可用，验证结果为 100% NULL，不作为关联键。

剩余约 6% 无收据门诊检验需后续单独验证条件挂接：`PATIENT_ID + TRUNC(BUSINESS_DATE) + CLINIC_NO_CNT=1`。该条件当前不进入正式 ER 图。

## 5. 当前使用口径

后续治理导入、关系图谱和 AI SQL 关系提示，优先使用：

- `开发起步包/数据资产_HIS_READY二次优化包/secondary_relationships_A_rechecked.csv`
- `开发起步包/数据资产_HIS_READY治理导入包/governance_relations_formal_final.csv`

D 类关系不进入当前 HIS_READY 正式关系图谱，仅作为后续跨系统验证任务保留。

## 6. 注意事项

原 B/C 中仍保留抽样覆盖率、孤儿数、低匹配率等验证指标。虽然当前按用户确认纳入可采用关系，但后续进入生产治理前，建议继续作为质量监控指标展示，不要丢弃风险信息。