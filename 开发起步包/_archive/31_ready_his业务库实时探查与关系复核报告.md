> 类别：关系验证

# 31 ready_his 业务库实时探查与关系复核报告

> 日期：2026-07-05  
> 数据源：`10.10.10.15:1521/his`，通过 8.53 跳板机访问。  
> 账号：`ready_his`；密码不入文档、不入代码。  
> 安全口径：只读 `SELECT`；元数据采集不扫业务表；关系验证使用 `ROWNUM` 限定样本，`LAB_RESULT` 按 `TEST_NO` 主表子集限定。  
> 机器结果：`31_ready_his业务库实时探查与关系复核结果.json`。  
> 资产包：`数据资产_HIS_READY复核包/`。

---

## 1. 与当前代码系统的对齐

本次输出字段按当前代码模型对齐：

| 代码模型 | 本次输出 |
|---|---|
| `AssetDataSource` | `system_code=HIS_SOURCE`、`source_code=his_ready_10_10_10_15`、`db_type=oracle`、`credential_ref` 后续配置 |
| `AssetTable` | `schema_name/namespace_name/table_name/domain/table_role/include_status/pk/row_count_stats` |
| `AssetColumn` | `column_id/column_name/data_type/length/nullable/comment/semantic_type/is_primary_key` |
| `AssetRelation` | 已样本验证且可作为正式关系的主线关系 |
| `AssetRelationReview` | 字段名推断候选关系、子集关系、少量孤儿关系 |

建议导入时继续使用独立源系统 `HIS_SOURCE`，不要直接覆盖 8.216 ODS 资产。

---

## 2. 实时元数据概览

| 指标 | 本次 ready_his 活库 | 旧 HIS 源端资产包 |
|---|---:|---:|
| 表 | 1234 | 1234 |
| 字段 | 24726 | 19831 |
| 新增字段 | 4895 | - |
| 删除字段 | 0 | - |
| 声明外键 | 2 | 未单独统计 |
| 字段名候选关系 | 578 | - |

结论：表范围稳定，但旧字段快照已落后；后续治理导入和字段级分析应以本次 `ready_his` 活库字段为准，同时复用 `23/25` 已确认的业务纳入/排除口径。

---

## 3. Owner 规模

| owner | 表 | 纳入 | 候选 | 排除 | 统计行数 |
|---|---:|---:|---:|---:|---:|
| COMM | 382 | 357 | 0 | 25 | 67999941 |
| DRUG_USER | 123 | 0 | 114 | 9 | 107537124 |
| EXAM | 39 | 6 | 31 | 2 | 17353624 |
| INPADM | 26 | 4 | 10 | 12 | 3979866 |
| INPBILL | 67 | 2 | 49 | 16 | 267281815 |
| LAB | 137 | 7 | 126 | 4 | 139111479 |
| MEDADM | 73 | 25 | 32 | 16 | 93720986 |
| MEDREC | 163 | 39 | 98 | 26 | 32979306 |
| ORDADM | 55 | 7 | 35 | 13 | 379766675 |
| OUTPADM | 36 | 5 | 26 | 5 | 22783496 |
| OUTPBILL | 31 | 2 | 22 | 7 | 76507062 |
| PHARMACY | 102 | 13 | 66 | 23 | 217829125 |

注意：本次快速分类是代码导入口径，仍需叠加 `23/25` 的强制纳入规则，例如 `ORDERS_EXECUTE_DETAILS`、`INP_ORDER_EXECDATA`、`PREPAYMENT_RCPT`、`BEDPATS_IN_HOSPITAL` 应继续纳入。

---

## 4. 核心关系样本验证

本次验证 22 条 HIS 主线关系：

| 结果 | 数量 | 说明 |
|---|---:|---|
| `sample_pass` | 7 | 样本全匹配 |
| `sample_pass_with_orphans` | 15 | 有少量孤儿，但匹配率均超过 99% |

全匹配关系包括：

- `MEDREC.PAT_VISIT -> MEDREC.PAT_MASTER_INDEX`
- `MEDREC.DIAGNOSIS -> MEDREC.PAT_VISIT`
- `LAB.LAB_TEST_ITEMS -> LAB.LAB_TEST_MASTER`
- `LAB.LAB_RESULT -> LAB.LAB_TEST_MASTER`
- `INPBILL.INP_BILL_DETAIL -> MEDREC.PAT_VISIT`
- `OUTPBILL.OUTP_BILL_ITEMS -> OUTPBILL.OUTP_RCPT_MASTER`
- `DRUG_USER.PHA_INP_DISPDETAIL -> DRUG_USER.PHA_INP_REQUEST_DRUG`

有少量孤儿但可入复核/正式关系的重点关系：

- `ORDADM.ORDERS -> MEDREC.PAT_VISIT`：100000 样本匹配 99953。
- `ORDADM.ORDERS_EXECUTE_DETAILS -> ORDADM.ORDERS`：100000 样本匹配 99976。
- `DRUG_USER.INP_ORDER_EXECDATA -> ORDADM.ORDERS`：100000 样本匹配 99306。
- `EXAM.EXAM_REPORT -> EXAM.EXAM_MASTER`：100000 样本匹配 99999。
- `INPBILL.PREPAYMENT_RCPT -> MEDREC.PAT_MASTER_INDEX`：100000 样本匹配 99980。
- `DRUG_USER.PHA_INP_REQUEST_DRUG -> MEDREC.PAT_VISIT`：100000 样本匹配 99888。

这些关系建议导入 `AssetRelation` 时保留 `validation_metrics`；若要求“零孤儿强关系”，则先进入 `AssetRelationReview`。

---

## 5. 资产包文件

`数据资产_HIS_READY复核包/` 包含：

| 文件 | 用途 |
|---|---|
| `his_ready_tables.csv` | 活库表资产，按当前代码字段命名 |
| `his_ready_columns.csv` | 活库字段资产，含注释、语义类型、主键标识 |
| `his_ready_relationships.csv` | Oracle 声明外键 + 字段名候选关系 |
| `his_ready_validated_relationships.csv` | 22 条主线关系样本验证结果 |
| `his_ready_summary.json` | 元数据统计 |
| `his_ready_validated_relationships.json` | 关系验证统计与明细 |

---

## 6. 后续建议

1. 以本次 `his_ready_columns.csv` 更新 HIS 源端字段资产，修正旧快照缺失的 4895 个字段。
2. 用 `23/25` 的强制纳入/排除规则二次加工 `his_ready_tables.csv`，避免快速规则把已确认事实表误放入候选。
3. 将 22 条验证关系导入正式关系或复核表：`sample_pass` 可直接入正式关系；`sample_pass_with_orphans` 建议带指标入复核。
4. 对 578 条字段名候选关系做排序过滤，只保留跨主线键、费用键、医嘱键、检验/检查键的高价值候选。
5. 下一轮专题验证优先处理大候选表：`INP_ORDER_EXECDATA`、`DRUG_DISPENSE_REC`、`ORDERS_EXECUTE_DETAILS`、`PREPAYMENT_RCPT`、`DRUG_PRESC_DETAIL`。

