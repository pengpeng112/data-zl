> 类别：关系验证

# secondary_manual_confirm_tables 复核修订报告

## 1. 复核范围

本轮基于 `_archive/34_ready_his数据资产二次优化复核报告.md` 产出的 `secondary_manual_confirm_tables.csv` 进行二次收敛。原 34 已归档为旧版证据，当前待确认表结论以本文和 `40_数据治理复核口径与方法记录.md` 为准。本轮重点处理用户指出的几类问题：

- 近 30 天仍有数据的表应优先保留；
- `7月出院患者` 这类中文临时/手工结果表排除；
- `MED_DRUG_LOC_2025-10-30`、`MED_CHECK_DETAIL_2025-9-1` 等日期快照/备份表排除；
- `PBCATEDT`、`PBCATFMT`、`PBCATTBL`、`PBCATVLD` 等 `PBCAT*` 空表排除；
- 有表中文名或数据库备注、且非备份临时、存在数据的业务表优先保留。

## 2. 本轮输出

输出目录：`开发起步包/数据资产_HIS_READY二次优化包/`

| 文件 | 用途 |
|---|---|
| `secondary_core_tables_rechecked.csv` | 复核后核心/保留表清单 |
| `secondary_excluded_tables_rechecked.csv` | 复核后排除表清单 |
| `secondary_manual_confirm_tables_rechecked.csv` | 复核后仍需人工确认表清单 |
| `secondary_all_tables_decision_rechecked.csv` | 复核后全量表决策 |
| `secondary_manual_confirm_review_decisions.csv` | 578 张待确认表逐表复核动作 |
| `secondary_manual_activity_recheck.csv` | 80 张候选表只读 SQL 活跃度补查结果 |
| `secondary_manual_confirm_recheck_summary.json` | 本轮汇总 |

## 3. 汇总结果

| 指标 | 复核前 | 复核后 |
|---|---:|---:|
| 核心/保留表 | 477 | 654 |
| 排除表 | 179 | 434 |
| 待人工确认表 | 578 | 146 |

本轮从待确认表中转入核心/保留表 177 张，转入排除表 255 张，仍保留人工确认 146 张。

## 4. 活跃度补查

通过跳板机 `10.10.8.53` 对 80 张候选表执行只读 SQL，统计 `COUNT(*)`、时间字段最早/最晚时间、近 30 天数据量。未执行 `SELECT *`，未查询 CLOB/BLOB 全文。

近 30 天有数据的关键表包括：

| Schema | 表名 | 时间字段 | 最晚时间 | 近30天 |
|---|---|---|---|---:|
| OUTPBILL | EINV_RCPT_MASTER | SETTLE_DATE | 2026-07-06 09:25:01 | 130624 |
| DRUG_USER | OPS_PRESC_DATA | PRESC_DATE | 2026-07-06 00:31:15 | 87288 |
| INPBILL | PREPAYMENT_RCPT_ADD | TRANSACT_DATE | 2026-07-06 09:25:33 | 71144 |
| MEDREC | MEDICAL_CARD_VS_IDNO | OPERATE_DATE | 2026-07-06 09:24:49 | 14358 |
| MEDREC | MR_TRANSFER | ADMISSION_DATE_TIME | 2026-07-06 09:23:53 | 5138 |
| PHARMACY | DRUG_DISPENSE_PRE | DISPENSING_DATE_TIME_PRE | 2026-07-06 09:22:22 | 369741 |
| PHARMACY | DATAPRESCRIPTIONDETAIL_DATA | PRESTIME | 2026-07-06 09:04:04 | 2371 |
| EXAM | EXAM_SHARINGCENTER_DETAIL | REPORT_TIME | 2026-07-04 09:23:22 | 254 |
| INPADM | PRE_TRANSFERRING_PATS | TRANSFER_DATE_TIME | 2026-07-06 08:51:27 | 314 |

`VIEW_SHOWDATA` 近 30 天有数据，但表义为预览/报表中间数据，暂不直接纳入核心资产，继续放在人工确认清单。

## 5. 点名样例处理

| 表名 | 处理结果 | 依据 |
|---|---|---|
| `7月出院患者` | 排除 | 中文临时/手工结果表 |
| `MED_DRUG_LOC_2025-10-30` | 排除 | 日期快照/备份表 |
| `MED_CHECK_DETAIL_2025-9-1` | 排除 | 日期快照/备份表 |
| `PBCATEDT` / `PBCATFMT` / `PBCATTBL` / `PBCATVLD` | 排除 | `PBCAT*` 且总行数为 0 |
| `DRUG_SUPPLIER_CATALOG` | 保留 | 有中文名、非日志表、存在数据 |
| `EXP_SUPPLIER_CATALOG` | 活跃补验后保留 | 近 30 天有 4 行，但 `PERMIT_DATE` 含未来日期，后续需做时间异常规则 |

## 6. 仍需人工确认

复核后仍有 146 张表需要人工确认，主要包括：

- 有数据但缺中文名、缺备注、缺已验证关系的表；
- 空表但有中文名或业务域，可能是历史配置/备用业务表；
- 活跃但表义偏中间过程或报表预览的表；
- 时间字段候选不可靠，需后续补质量规则确认的表。

人工确认入口：`secondary_manual_confirm_tables_rechecked.csv`。

## 7. 后续建议

1. 将 `secondary_core_tables_rechecked.csv` 作为 HIS_READY 治理导入候选基础。
2. 对活跃补验保留的表补主键唯一性、外键覆盖率、行数放大验证。
3. 对 `PERMIT_DATE`、`DATE_CODE` 等存在未来日期或字段语义可疑的字段建立质量规则。
4. 对 146 张仍待确认表，由业务人员按“是否当前业务仍使用、是否有查询价值、是否有上游/下游关系”逐项确认。

## 8. 用户范围修订

根据后续确认规则再次修订：

- 当前待确认池中，总行数 5 行以内的表直接排除；
- `PUB_CONFIG`、`VIEW_SHOWDATA`、`INP_BILL_DETAIL_CANCEL`、`LAB_SHARINGCENTER_DETAIL`、`ORDERS_EXECUTE` 强制保留；
- `ORDERS_EXECUTE` 明确为医嘱执行记录表，数据粒度为“一次医嘱执行生成一条记录”；
- 其余未在用户指定保留表内的待确认表，标记为暂不纳入治理范围。

修订后结果：

| 指标 | 修订后 |
|---|---:|
| 核心/保留表 | 659 |
| 排除/不纳入治理范围表 | 575 |
| 待人工确认表 | 0 |

新增修订明细文件：`secondary_manual_confirm_user_scope_correction.csv`。
