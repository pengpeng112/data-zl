# HISUSER 业务库探查报告

> 数据源：`10.10.10.15:1521/his`，账号 `hisuser`。  
> 执行方式：经 8.53 跳板机，Oracle thick 模式，只读 `SELECT` 数据字典。  
> 探查时间：2026-07-03。  
> 参考文档：`系统表结构/HIS系统数据库表结构.md`、`系统表结构/HIS系统药房药库表设计文档.md`。  
> 机器结果：`16_hisuser业务库探查结果.json`；元数据快照：`16_hisuser业务库元数据快照.json`。

---

## 1. 关键结论

1. `hisuser` 账号自身 schema 不是 HIS 业务主 schema，自有表以报表/中间表为主，包含大量 `FINE_*` 表。
2. HIS 业务表分散在多个 owner，并通过 PUBLIC synonym 暴露；例如：
   - `PAT_MASTER_INDEX` / `PAT_VISIT` 在 `MEDREC`。
   - `ORDERS` 在 `ORDADM`。
   - `LAB_TEST_MASTER` / `LAB_RESULT` 在 `LAB`。
   - `EXAM_MASTER` / `EXAM_REPORT` 在 `EXAM`。
   - 通用字典如 `DRUG_DICT` 在 `COMM`。
   - 药房药库新表在 `DRUG_USER`。
3. 两份文档共提取 435 张候选表，其中 415 张可在业务库 `ALL_TABLES` 中找到；说明文档与业务库整体匹配度较高。
4. 当前数据中心 ODS.HIS 只覆盖这些文档表中的 65 张，远少于业务库全量；因此 ODS 是重点抽取层，不是 HIS 业务库全量镜像。
5. 药房药库文档 67 张表在业务库中全部可见，但其中发药、库存、盘点、调拨等流水表大多未进入 ODS.HIS。

---

## 2. 探查范围

本轮只读查询了：

- `ALL_TABLES`
- `ALL_TAB_COLUMNS`
- `ALL_TAB_COMMENTS`
- `ALL_COL_COMMENTS`
- `ALL_CONSTRAINTS`
- `ALL_CONS_COLUMNS`
- `ALL_SYNONYMS`
- `V$VERSION`

未执行：

- 任何 DML / DDL。
- 任何业务表全表 `COUNT(*)`。
- 任何患者明细、处方明细、检验结果明细读取。

表行数使用 Oracle 统计信息 `NUM_ROWS`，可能滞后。

---

## 3. 元数据规模

| 项目 | 数量 |
|---|---:|
| 业务 owner 数 | 26 |
| 业务 owner 表数 | 2253 |
| 业务 owner 字段数 | 35593 |
| HIS 主文档候选表 | 368 |
| 药房药库文档候选表 | 67 |
| 两份文档合并候选表 | 435 |
| 文档表在业务库可见 | 415 |
| 文档表未在业务库匹配 | 20 |
| 文档表同时在 ODS.HIS 可见 | 65 |
| 文档表在业务库可见但未进 ODS.HIS | 350 |

---

## 4. 主要 owner 分布

| owner | 命中文档表数 | 定位 |
|---|---:|---|
| `COMM` | 151 | 通用字典、价表、配置等 |
| `DRUG_USER` | 71 | 药房药库新系统表 |
| `PHARMACY` | 40 | 药房处方、发药等旧 HIS 药房表 |
| `MEDADM` | 38 | 医疗行政/基础管理相关表 |
| `MEDREC` | 19 | 患者主索引、住院、病案、诊断、手术等 |
| `EXAM` | 19 | HIS 检查主表/报告/字典 |
| `INPBILL` | 19 | 住院费用 |
| `OUTPBILL` | 15 | 门诊费用 |
| `ACCT` | 13 | 账务/核算 |
| `LAB` | 13 | HIS 检验主表/结果/字典 |
| `OUTPADM` | 7 | 门诊挂号/就诊 |
| `INPADM` | 6 | 住院登记/管理 |
| `ORDADM` | 5 | 医嘱 |

---

## 5. 核心表核查

| 表 | 业务库 owner | 统计行数 | 字段数 | 主键 | ODS.HIS |
|---|---|---:|---:|---|---|
| `PAT_MASTER_INDEX` | `MEDREC` | 1905243 | 113 | `PATIENT_ID` | 已抽取 |
| `PAT_VISIT` | `MEDREC` | 574677 | 268 | `PATIENT_ID,VISIT_ID` | 已抽取 |
| `DIAGNOSIS` | `MEDREC` | 3298728 | 23 | `PATIENT_ID,VISIT_ID,DIAGNOSIS_TYPE,DIAGNOSIS_NO` | 已抽取 |
| `ORDERS` | `ORDADM` | 41033928 | 88 | 未见 PK | 已抽取 |
| `LAB_TEST_MASTER` | `LAB` | 9137516 | 49 | `TEST_NO` | 已抽取 |
| `LAB_TEST_ITEMS` | `LAB` | 9336684 | 16 | `TEST_NO,ITEM_NO` | 已抽取 |
| `LAB_RESULT` | `LAB` | 93669749 | 26 | `TEST_NO,ITEM_NO,PRINT_ORDER` | 已抽取 |
| `EXAM_MASTER` | `EXAM` | 3401210 | 58 | `EXAM_NO` | 已抽取 |
| `EXAM_REPORT` | `EXAM` | 1336968 | 14 | `EXAM_NO` | 已抽取 |
| `OPERATION` | `MEDREC` | 527828 | 31 | `PATIENT_ID,VISIT_ID,OPERATION_NO` | 已抽取 |
| `CLINIC_MASTER` | `OUTPADM` | 5642159 | 94 | `VISIT_DATE,VISIT_NO` | 已抽取 |
| `INP_BILL_DETAIL` | `INPBILL` | 218921398 | 74 | `PATIENT_ID,VISIT_ID,ITEM_NO` | 已抽取 |

这些核心表与 8.216 ODS.HIS 的结构和行量级基本一致，说明数据中心已覆盖 HIS 主线。

---

## 6. 药房药库核查

药房药库文档 67 张表全部在业务库可见，主要 owner 为 `DRUG_USER`。

代表表：

| 表 | owner | 统计行数 | 字段数 | ODS.HIS |
|---|---|---:|---:|---|
| `MED_DICT_BASEINFO` | `DRUG_USER` | 6040 | 102 | 已抽取 |
| `MED_DICT_PRICE` | `DRUG_USER` | 8488 | 47 | 已抽取 |
| `MED_DICT_FACTORY` | `DRUG_USER` | 1569 | 48 | 已抽取 |
| `PHA_INP_DISPMASTER` | `DRUG_USER` | 336816 | 22 | 未抽取 |
| `PHA_INP_DISPDETAIL` | `DRUG_USER` | 4729145 | 55 | 未抽取 |
| `PHA_CLI_REQUEST_DRUG` | `DRUG_USER` | 2044542 | 127 | 未抽取 |
| `PHA_VISIT_DISPDETAIL` | `DRUG_USER` | 2095101 | 43 | 未抽取 |

结论：ODS 当前只抽取了少量药品字典/价格相关表，没有覆盖药房药库业务流水主线。如果后续要做药品闭环、库存、发药、调拨、追溯码等，需要基于业务库 `DRUG_USER` 单独梳理。

---

## 7. 未匹配文档表

两份文档中有 20 张表未在业务库 `ALL_TABLES` 中匹配：

```text
ALERGY_DRUGS
CLINIC_DIAGNOSIS
CURRENT_PRICE_LIST
DEPT_ADT
DEPT_EFFCIENCY
DIET_DICT
DRUG_ALERGY_SEVERITY_DICT
DRUG_PURCHASE_PLAN
EQUIP_VS_FEE_DICT
EXAM_ITEM_DICT
FINAL_CHIEF_DIAGNOSIS
INP_BILL_CHECKED
ITEM_CLASS_VS_OTHER_CLASS
LAB_ITEM_DICT
LAB_ITEM_NAME_DICT
NURSING_DICT
PAY_STYLE_DICT
QUALITY_GRAND_DICT
TREAT_ITEM_DICT
TREAT_ITEM_NAME_DICT
```

这些表可能属于：

- 历史废弃表。
- 文档旧版本表名。
- 已被同义词/新表替代。
- 未授权给 `hisuser` 可见。

本轮不对这些表做推断，后续如业务需要再逐表核查。

---

## 8. 与 ODS 的关系

当前 8.216 ODS.HIS 已覆盖 HIS 主线核心表，但不是全量 HIS 业务库：

- ODS.HIS 覆盖了患者、住院、诊断、医嘱、检验、检查、费用、处方等核心表。
- ODS.HIS 未覆盖大量药房药库流水、配置字典、统计、管理类表。
- 如果后续建设内网服务只展示当前资产图谱，ODS 已足够。
- 如果后续要做业务系统级全量关系图谱，需要按 owner 分系统继续梳理。

建议后续拆分专题：

1. `MEDREC/INPADM/OUTPADM`：患者、住院、门诊主线。
2. `ORDADM`：医嘱主线。
3. `LAB`：HIS 检验主线。
4. `EXAM`：HIS 检查主线。
5. `INPBILL/OUTPBILL`：费用主线。
6. `PHARMACY/DRUG_USER`：药房药库与处方发药主线。
