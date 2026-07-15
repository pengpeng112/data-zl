> 类别：证据报告

# 手麻 Docare 系统活库探查与关系分析报告

## 1. 探查结论

2026-07-14 已对 `10.10.10.68:1521/docare` 完成只读探查。登录账号当前 Schema 是 `SYSTEM`，但真实业务对象不在 SYSTEM 下，主要分布于：

- `MEDSURGERY`：手术排班、手术主记录、麻醉计划/总结/事件、术中监护、镇痛、药品和耗材，共 235 表、27 视图。
- `MEDCOMM`：患者主索引、就诊、公共字典、HIS 数据接口、医嘱、检验和病历视图，共 141 表、25 视图。
- `MEDICU`：ICU 护理、监护、评分、管路和配置，共 218 表；当前大量业务表为空，主要是安装模块和配置底座。

三个 Owner 合计 594 张表、52 个视图、10,529 个字段。源端只执行元数据目录查询和每条最多 10,000 个非空键的只读关系验证，未执行 DML/DDL，业务源库写入为 0。

## 2. 结构规模

| Owner | 表 | 视图 | 非零统计表 | 零行统计表 | 主要定位 |
|---|---:|---:|---:|---:|---|
| MEDSURGERY | 235 | 27 | 56 | 179 | 手术麻醉核心业务 |
| MEDCOMM | 141 | 25 | 71 | 70 | 患者、就诊、公共及HIS接口 |
| MEDICU | 218 | 0 | 30 | 188 | ICU模块，以配置字典为主 |
| 合计 | 594 | 52 | 157 | 437 | — |

数据库声明的 5 条外键只覆盖权限资源、角色以及 ICU 流程配置，没有覆盖手术麻醉主线。因此业务关系主要依靠复合主键、视图 SQL 和数据命中验证确定。

## 3. 核心业务模型

Docare 的核心键非常清晰：

- 患者：`PATIENT_ID`
- 一次住院/就诊：`PATIENT_ID + VISIT_ID`
- 一次实际手术/麻醉：`PATIENT_ID + VISIT_ID + OPER_ID`
- 一次排班：`PATIENT_ID + VISIT_ID + SCHEDULE_ID`
- 手术名称明细：再加 `OPERATION_NO`
- 麻醉事件：再加 `ITEM_NO + EVENT_NO`
- 监护数据：按 `ITEM_NO` 或 `TIME_POINT + ITEM_NAME + EVENT_NO` 展开

```text
MEDCOMM.MED_PAT_MASTER_INDEX
  └─ PATIENT_ID
     MEDCOMM.MED_PAT_VISIT
       ├─ PATIENT_ID + VISIT_ID
       │  MEDSURGERY.MED_OPERATION_SCHEDULE
       │    └─ + SCHEDULE_ID → MED_SCHEDULED_OPERATION_NAME
       └─ PATIENT_ID + VISIT_ID
          MEDSURGERY.MED_OPERATION_MASTER
            ├─ MED_OPERATION_NAME
            ├─ MED_ANESTHESIA_PLAN
            ├─ MED_ANESTHESIA_SUMMARY
            ├─ MED_ANESTHESIA_EVENT / EVENT_BACK
            ├─ MED_ANESTHESIA_INPUT_DATA
            ├─ MED_PAT_MONITOR_DATA / MED_PATIENT_MONITOR_DATA
            ├─ MED_PAT_MONITOR_DATA_HISTORY
            ├─ MED_OPERATION_ANALGESIC
            ├─ MED_ANES_OPERHANDOVER
            └─ MED_ANES_DOC_CHECK
```

## 4. 只读关系验证结果

### 4.1 样本 100% 命中

| ID | 子表 → 父表 | 关联键 |
|---|---|---|
| D01 | `MED_PAT_VISIT → MED_PAT_MASTER_INDEX` | `PATIENT_ID` |
| D08 | `MED_ANESTHESIA_EVENT → MED_OPERATION_MASTER` | 患者+访视+手术 |
| D09 | `MED_ANESTHESIA_EVENT_BACK → MED_OPERATION_MASTER` | 患者+访视+手术 |
| D11 | `MED_PAT_MONITOR_DATA → MED_OPERATION_MASTER` | 患者+访视+手术 |
| D12 | `MED_PATIENT_MONITOR_DATA → MED_OPERATION_MASTER` | 患者+访视+手术 |
| D13 | `MED_PAT_MONITOR_DATA_HISTORY → MED_OPERATION_MASTER` | 患者+访视+手术 |

以上各验证关系均为 10,000/10,000 命中，可作为手麻关系图谱主干。

### 4.2 高命中但存在少量孤儿

| ID | 关系 | 命中 | 处理建议 |
|---|---|---:|---|
| D03 | 排班手术名称 → 手术排班 | 9,998/10,000（99.98%） | 强关系，保留孤儿质量提示 |
| D04 | 实际手术主表 → 患者就诊 | 9,941/10,000（99.41%） | 强关系，分析历史患者同步缺口 |
| D05 | 实际手术名称 → 实际手术主表 | 9,956/10,000（99.56%） | 强关系 |
| D06 | 麻醉计划 → 实际手术主表 | 9,926/10,000（99.26%） | 强关系但不可设为数据库强制外键 |
| D07 | 麻醉总结 → 实际手术主表 | 9,996/10,000（99.96%） | 强关系 |
| D10 | 麻醉质量输入 → 实际手术主表 | 9,998/10,000（99.98%） | 强关系 |
| D14 | 术后镇痛 → 实际手术主表 | 9,999/10,000（99.99%） | 强关系 |
| D15 | 麻醉手术交接 → 实际手术主表 | 9,999/10,000（99.99%） | 强关系 |
| D16 | 麻醉文书检查 → 实际手术主表 | 9,991/10,000（99.91%） | 强关系 |

### 4.3 需要显式标注子集/历史差异

`MED_OPERATION_SCHEDULE → MED_PAT_VISIT` 本轮为 9,800/10,000（98.00%）。排班数据会包含取消、临时、历史迁移或患者同步不完整记录，应作为业务强关系但显示状态过滤和约 2% 孤儿风险，不能直接用数据库外键约束。

## 5. 重点大表

下列行数来自 Oracle 最近统计信息，不是本轮全表计数：

| 表 | 统计行数 | 安全要求 |
|---|---:|---|
| `MEDSURGERY.MED_CUSTOM_DATA` | 33,708,693 | 必须按患者/访视/手术键限定 |
| `MEDSURGERY.MED_ANESTHESIA_EVENT_BACK` | 15,884,757 | 必须按手术键或限量样本 |
| `MEDCOMM.MED_VITAL_SIGN_MERGE` | 11,698,030 | 必须按患者和时间范围限定 |
| `MEDCOMM.MED_LAB_RESULT` | 10,770,948 | 必须按检验单号限定 |
| `MEDSURGERY.MED_QIXIE_QINGDIAN` | 7,843,107 | 按手术/清点单限定 |
| `MEDSURGERY.MED_PATIENT_MONITOR_DATA` | 6,562,667 | 按手术键和时间点限定 |
| `MEDSURGERY.MED_APPLICATION_AUDIT_TRAIL` | 5,482,765 | 按实体和时间范围限定 |
| `MEDSURGERY.MED_PAT_MONITOR_DATA` | 3,139,268 | 按手术键限定 |
| `MEDSURGERY.MED_ANESTHESIA_EVENT` | 2,311,852 | 按手术键限定 |

## 6. 视图关系种子

52 个视图均解析到基础表，共得到 276 条静态依赖。重点视图包括：

- `MEDCOMM.MZJL` / `SM_MZJL`：患者主索引、HIS患者、麻醉计划、手术主表、手术记录等。
- `MEDCOMM.SSJL` / `SM_SSJL`：排班、实际手术、手术名称、患者、科室、人员等。
- `MEDSURGERY.V_MED_ANES_INFO`：手术排班、手术主表、麻醉计划、质量输入、取消记录和自定义数据。
- `MEDCOMM.VIEW_OPERATION_LIST`：排班、排班手术名称、实际手术、实际手术名称及患者主索引。
- `MEDSURGERY.OPERATION_PROCESS`：排班到实际手术过程、患者、科室、人员、手术间。

这些真实视图 SQL 是后续列级 JOIN 关系分析的首选种子，优先级高于仅凭同名字段推断。

## 7. 与既有手麻资产的区别

既有 13/14/15 号证据主要分析数据中心 `SM` Owner 及其与 HIS 的映射；本报告分析的是独立 Docare 业务库。两者不能因为都叫“手麻”而混为同一个物理数据源：

- Docare 使用 `MEDSURGERY/MEDCOMM/MEDICU` 多 Owner。
- 核心关联键是患者+访视+手术号。
- 数据中心 `SM` 仍是数据中心内部 Schema；Docare 应作为独立数据库连接或该业务系统的物理源实例管理。
- 后续跨库对照应先验证 Docare `OPER_ID`、排班键与数据中心 SM/HIS 的真实映射，不能仅按医生姓名关联。

## 8. 安全与产物

- 元数据快照：`80_手麻Docare系统Oracle元数据快照.json`
- 关系验证结果：`80_手麻Docare系统关系验证结果.json`
- 采集脚本：`backend/scripts/harvest_docare_oracle_readonly.py`
- 验证脚本：`backend/scripts/verify_docare_relationships_readonly.py`

凭据未进入代码、报告、快照、日志或 Git。本轮没有把资产写入平台数据库；正式接入时应建立独立 source_code/domain，平台库先备份，再导入 594 表、52 视图、10,529 字段、276 条静态依赖及本轮 16 条分级关系。
