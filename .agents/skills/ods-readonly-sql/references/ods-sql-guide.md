# ODS 数据中心 SQL 快速参考
## 系统边界

- 一级业务系统：`DATA_CENTER`，中文名“数据中心”。
- 物理数据库：Oracle 11g；对象必须按当前元数据核对。
- 数据中心内部 Owner 包含 `HIS`、`CDA`、`ODS`、`MTL`、`JHEMR`、`YDHL`、`SM`、`LIS`、`PACS`、`PORTAL_EMPI` 等。它们是数据中心内部库区/Owner，不是本技能中的独立一级系统。
- 独立源端 LIS、PACS、移动护理、Docare、嘉和电子病历等属于其他物理系统；除非数据中心内有已核实的同步 Owner 或视图依赖，否则不要假设可以在同一条 ODS SQL 中直接访问。

## 权威资料路由

| 目的 | 文件 |
|---|---|
| 当前目录和状态 | `开发起步包/README.md`、`55_系统未完成事项统一执行计划.md` |
| 活库对象、字段、视图 DDL | `开发起步包/08_数据中心元数据快照.json` |
| 核心表结构与关系 | `开发起步包/09_数据资产_表结构与关联关系.md` |
| 关系验证指标 | `开发起步包/10_关系验证报告.md`、`10_关系验证结果.json` |
| 视图种子 | `开发起步包/03_view_registry.json` |
| 候选关系 | `开发起步包/11_视图关系解析与HIS分类报告.md`、`12_候选关系验证报告.md` |
| 周边 Owner 关系 | `开发起步包/14_PACS_LIS_YDHL关系验证报告.md`、`15_关系补验与资产回写报告.md` |
| 治理采纳口径 | `开发起步包/40_数据治理复核口径与方法记录.md` |
| 机器可读表字段关系 | `开发起步包/数据资产_资产包/tables.csv`、`columns.csv`、`relationships.csv`、`catalog.json` |
| ODS 视图依赖 | `开发起步包/数据资产_关系图谱/ods_view_dependencies.csv`、`ods_view_join_edges.csv` |
| 平台 AI 对接 | `开发起步包/87_AI视图SQL生成与平台对接说明.md` |

## 已确认的关键关联口径

| 主题 | 关系键/规则 | 重要限制 |
|---|---|---|
| 患者主索引到住院 | `HIS.PAT_MASTER_INDEX.PATIENT_ID = HIS.PAT_VISIT.PATIENT_ID` | 历史数据存在极少孤儿 |
| 住院就诊 | `PATIENT_ID + VISIT_ID` | 两列必须同时连接 |
| 住院诊断 | `PAT_VISIT(PATIENT_ID,VISIT_ID) -> DIAGNOSIS(PATIENT_ID,VISIT_ID)` | 一次就诊可多条诊断 |
| 医嘱 | `PAT_VISIT(PATIENT_ID,VISIT_ID) -> ORDERS(PATIENT_ID,VISIT_ID)` | 巨表；必须限制住院键或时间 |
| 住院结算 | `PAT_VISIT(PATIENT_ID,VISIT_ID) -> INP_SETTLE_MASTER(PATIENT_ID,VISIT_ID)` | 一次就诊可能多次结算 |
| 住院费用明细 | `INP_SETTLE_MASTER(PATIENT_ID,VISIT_ID) -> INP_BILL_DETAIL(PATIENT_ID,VISIT_ID)` | 约亿级；必须先限定键/时间，注意多对多放大 |
| 检验主从 | `TEST_NO`，必要时再加明细序号 | `HIS.LAB_RESULT` 约一亿行，必须先限定 `TEST_NO` |
| 检查主报 | `HIS.EXAM_MASTER.EXAM_NO = HIS.EXAM_REPORT.EXAM_NO` | `EXAM_REPORT` 无 `PATIENT_ID` |
| 入/出院科室 | `PAT_VISIT.DEPT_ADMISSION_TO/DEPT_DISCHARGE_FROM = DEPT_DICT.DEPT_CODE` | 字典维度先检查唯一性 |
| 主管医师 | `PAT_VISIT.DOCTOR_IN_CHARGE = STAFF_DICT.EMP_NO` | 有少量历史/离职孤儿；姓名不可作稳定键 |
| JHEMR 住院 | `PATIENT_ID + VISIT_ID` | 以 15 号已回写关系为准 |
| LIS 到 HIS 检验 | `LIS.BARCODE = HIS.TEST_NO` | 使用前核对具体对象与字段 |
| YDHL 到 HIS 住院 | `MRN = INP_NO` 且 `SERIES = VISIT_ID` | 护理事实表再经 `PATIENT_UID` 关联护理患者表 |
| 手麻 | 不使用全为空的 `HIS.OPERATION.OPER_ID` | 采用已验证的 `SM.MED_OPERATION_*` 路径；具体关系查 13/15 |

## 已知数据坑

- `HIS.LAB_RESULT`、`HIS.INP_BILL_DETAIL`、`HIS.ORDERS` 禁止全表扫描。
- `HIS.OPERATION.OPER_ID` 全为空，不能作为手麻关联键。
- `HIS.EXAM_MASTER.EXAM_CLASS` 保存中文值，如 `CT`、`磁共振`；不要按字典内码猜测。
- `HIS.EXAM_REPORT` 不含 `PATIENT_ID`，必须经 `EXAM_NO` 回到检查主表。
- 门诊检验/检查中 `VISIT_ID=0/NULL` 按门诊口径，不可混入住院。
- `HIS.STAFF_DICT.NAME` 存在重名；人员关联优先工号并保留历史孤儿说明。
- `CDA.CDA_DICTIONARY` 可能一对多，JOIN 前按字典名称、系统标识等条件去重或聚合。
- `EMR_ANES_AFTER_RECORD` ID 有重复风险；`EMR_OUTPATIENT_RECIPE_ITEM.OR_ID` 孤儿严重；`EMR_OUTPATIENT_DIAG` 已知为空。

## Oracle 11g 模式

限量验证：

```sql
SELECT *
FROM (
    SELECT
        t.COL_A,
        t.COL_B
    FROM OWNER.TABLE_NAME t
    WHERE t.EVENT_TIME >= :start_time
      AND t.EVENT_TIME < :end_time
)
WHERE ROWNUM <= :max_rows;
```

左闭右开时间范围：

```sql
WHERE t.EVENT_TIME >= :start_time
  AND t.EVENT_TIME < :end_time
```

标准字典映射必须按实际中文列名核对，不要直接复制乱码或过期示例。当前固定机构口径为：机构代码 `49557032X`，机构名称“山东省第二人民医院”，行政区划 `370104`。

## 搜索资产的建议命令

```powershell
rg -n "PAT_VISIT|PATIENT_ID|VISIT_ID" 开发起步包/数据资产_资产包
rg -n "EXAM_MASTER|EXAM_REPORT" 开发起步包/08_数据中心元数据快照.json
rg -n "LAB_TEST_MASTER|LAB_RESULT|TEST_NO" 开发起步包/数据资产_资产包/relationships.csv
```

读取 CSV/JSON 时使用 UTF-8/UTF-8-BOM。若 PowerShell 显示乱码，改用明确 UTF-8 的读取方式，不要把乱码表名或列名写进 SQL。

数据库连接、环境变量、平台源编码和完整命令见同目录 `connection-guide.md`。连接前必须读取该文件；不要根据历史脚本猜测凭据。
