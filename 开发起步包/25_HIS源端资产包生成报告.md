> 类别：资产

# HIS 源端资产包生成报告

> 范围：基于 `16/22/23` 的元数据、覆盖差异和用户确认口径，生成独立 HIS 源端资产包草案。  
> 配套结果：`25_HIS源端资产包生成结果.json`。  
> 生成脚本：`tools/build_his_source_asset_package.py`。  
> 输出目录：`数据资产_HIS源端资产包/`。

---

## 1. 输出文件

| 文件 | 内容 | 用途 |
|---|---|---|
| `数据资产_HIS源端资产包/his_source_tables.csv` | HIS 源端表清单、owner、主题、角色、纳入状态、排除原因、ODS 同名覆盖状态 | 资产系统表登记 |
| `数据资产_HIS源端资产包/his_source_columns.csv` | HIS 源端字段清单、字段类型、字段主题、主键标记、表纳入状态 | 资产系统字段登记 |
| `数据资产_HIS源端资产包/his_source_relationships.csv` | HIS 源端已验证/候选关系 33 条 | 关系图谱/血缘导入 |
| `数据资产_HIS源端资产包/his_source_catalog.json` | 表、关系和统计摘要的程序读取版 | 后端/API/资产导入 |

CSV 使用 UTF-8-BOM，便于 Excel 打开。

---

## 2. 生成统计

| 指标 | 数量 |
|---|---:|
| 表 | 1234 |
| 字段 | 19831 |
| 源端关系 | 33 |
| 与 ODS.HIS 同名覆盖表 | 105 |

### 2.1 纳入状态

| 状态 | 数量 | 含义 |
|---|---:|---|
| `included` | 473 | 第一版建议纳入，包括核心事实、执行事实、缴费事实、维表 |
| `candidate` | 560 | 保留候选，需人工二次裁剪 |
| `excluded` | 201 | 第一版业务事实图谱排除 |

### 2.2 表角色

| 角色 | 数量 |
|---|---:|
| `dimension` | 443 |
| `candidate` | 560 |
| `excluded` | 201 |
| `core_fact` | 26 |
| `execution_fact` | 2 |
| `payment_fact` | 1 |
| `inpatient_management_fact` | 1 |

---

## 3. Owner 覆盖

| owner | 表数 |
|---|---:|
| `COMM` | 382 |
| `DRUG_USER` | 123 |
| `EXAM` | 39 |
| `INPADM` | 26 |
| `INPBILL` | 67 |
| `LAB` | 137 |
| `MEDADM` | 73 |
| `MEDREC` | 163 |
| `ORDADM` | 55 |
| `OUTPADM` | 36 |
| `OUTPBILL` | 31 |
| `PHARMACY` | 102 |

---

## 4. 已固化规则

### 4.1 纳入 owner

第一版 HIS 源端资产包纳入：

`MEDREC`、`INPADM`、`ORDADM`、`LAB`、`EXAM`、`INPBILL`、`OUTPBILL`、`OUTPADM`、`DRUG_USER`、`PHARMACY`、`COMM`、`MEDADM`。

### 4.2 强制纳入表

| 表 | 角色 |
|---|---|
| `ORDADM.ORDERS_EXECUTE_DETAILS` | `execution_fact` |
| `DRUG_USER.INP_ORDER_EXECDATA` | `execution_fact` |
| `INPBILL.PREPAYMENT_RCPT` | `payment_fact` |
| `MEDADM.BEDPATS_IN_HOSPITAL` | `inpatient_management_fact` |
| `COMM.DEPT_DICT` | `dimension` |
| `COMM.STAFF_DICT` | `dimension` |
| `COMM.PRICE_LIST` | `dimension` |
| `COMM.DIAGNOSIS_DICT` | `dimension` |

### 4.3 排除规则

第一版业务事实图谱排除：

| 模式 | 排除原因 |
|---|---|
| `ST_*` | 统计汇总表 |
| `*_LOG`、`*LOG*` | 日志类表 |
| 接口中间表 | 非业务事实主线 |
| 临时/备份/测试表 | 非生产业务事实 |
| 纯统计日/月表 | 汇总结果，不做第一版事实图谱 |

`COMM.OPERATION_LOG` 已明确排除。

---

## 5. 源端关系

资产包当前写入 33 条关系，来源包括：

| 来源 | 范围 |
|---|---|
| `21` | 主业务 owner 住院、诊断、手术、医嘱、检验、检查、费用、门诊收费关系 |
| `23` | 医嘱执行、住院用药执行、预交金、门诊检验/检查候选关系 |
| `19` | 药房药库/发药核心关系 |

门诊检验/检查关系仍标为 `candidate`：`VISIT_ID=0/NULL` 已按门诊口径归类，但当前仅有 `PATIENT_ID+申请日期` 候选关联，不能当作唯一强键。

---

## 6. 使用方式

重新生成：

```bash
python 开发起步包/tools/build_his_source_asset_package.py
```

生成依赖：

| 文件 | 用途 |
|---|---|
| `16_hisuser业务库元数据快照.json` | HIS 源端表字段元数据 |
| `08_数据中心元数据快照.json` | ODS.HIS 同名覆盖计算 |
| `22_HIS源端字段主题与ODS覆盖差异结果.json` | 字段主题和覆盖差异背景 |
| `23_HIS源端资产范围复核与下一步计划结果.json` | 用户确认的纳入/排除口径 |

---

## 7. 后续工作

1. 人工复核 `candidate` 表，优先处理 `DRUG_USER/PHARMACY` 药品扩展、`MEDADM` 非 `ST_*` 管理表、`COMM` 非字典表。
2. 继续寻找门诊检验/检查强关联键：`RCPT_NO`、`ORDER_ID`、`CLINIC_NO`、`VISIT_DATE/VISIT_NO`。
3. 将 `his_source_*` 导入资产系统测试库，验证字段映射与关系导入。
4. 如资产系统支持多源血缘，将 105 张同名覆盖表与 `ODS.HIS` 建立跨源映射。
