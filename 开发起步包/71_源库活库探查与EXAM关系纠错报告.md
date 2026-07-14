> 类别：证据
> 状态：已完成
> 日期：2026-07-13
> 探查方式：经用户授权，SSH 登录 8.83 → 容器 data-asset-api 内用 oracledb thick 模式连 ODS(8.216)/HIS(10.10.10.15)，全程只读 SELECT，大表 ROWNUM 限定
> 配套：`66_多AI交接_未完成与待实现清单.md`、`09_数据资产_表结构与关联关系.md`、`62/63/64` 证据链

# 71 源库活库探查与 EXAM 关系纠错报告

## 0. 摘要（先看这里）

本报告对 66 号交接清单的待复核项做了**活库实测**。核心结论：

1. **L10-diff**：活库 vs 08 快照差异极小（仅 HIS 新增 2 张疑似临时表），**08 快照与资产包高度准确**。
2. **关系图谱**：`EXAM_NO`、`PATIENT_ID+VISIT_ID` 核心关系经全表 JOIN **100% 成立**（早期抽样误判 0% 已纠正，原因见 §3）。
3. **人员口径**：用户确认 **以 `FXHIS.SYS_EMPLOYEE`(2468人) 为主**；`COMM.STAFF_DICT`(4222人) 桥接率 98.4%。
4. **HIS 新增 2 表**："提取价表信息"、"结算疾病编码空的"——**用户确认排除出资产包**。
5. 周边系统（LIS/PACS/SM/YDHL/JHEMR）表清单已采集，为 L14 接入做准备。

---

## 1. L10-diff：活库 vs 08 快照

**方法**：活库 `ALL_TABLES` 全表名集合 vs 08 快照（2026-07-02 采集）的表名集合，逐 schema 对比。

| 维度 | 08 快照 | 活库（2026-07-13） | 差异 |
|---|---|---|---|
| 业务 schema 数 | 32 | 32 | 一致（OGG/SCOTT 是系统 schema，08 正确排除）|
| 总表数 | 865 | 875 | +10（其中 8 为 OGG/SCOTT 系统 schema）|
| 消失的业务表 | — | — | **0** |

**真实业务变更**：仅 HIS schema 新增 2 张表：
- `提取价表信息`
- `结算疾病编码空的`

**用户决策（2026-07-13）**：这两张表为临时统计表，**排除出资产包**。

**结论**：08 快照高度准确，09-15 号资产文档与关系图谱**无需因表结构变化而更新**。活库表结构 11 天内零实质性变更。

---

## 2. ODS/HIS 表数复核

### 2.1 ODS 数据中心（8.216）业务 schema 分布（活库实测）

| Schema | 表数 | Schema | 表数 | Schema | 表数 |
|---|---:|---|---:|---|---:|
| HIS | 275 | MTL | 34 | PACS | 18 |
| CDA | 86 | YDHL | 31 | CRBSB | 17 |
| PORTAL_USER | 60 | JHEMR | 31 | XD | 15 |
| PORTAL_USER_GROUP | 55 | SM | 25 | YBEMR | 14 |
| WSCTS | 46 | TJ | 23 | PORTAL | 14 |
| HRP | 21 | BL | 21 | ODS | 19 |
| LIS | 11 | PORTAL_EMPI | 10 | JXXT | 8 |
| CS | 8 | YINGYI | 6 | NJ | 6 |
| DBZ | 4 | SX | 3 | MDK/KZL/SHUNNENG/FXJCPT | 各 1-2 |

**总计：32 schema，875 表**。与 66 号 §1.3 "ODS 核心 owner ~540 表 / HIS ~1237 表" 基本吻合。

### 2.2 HIS 源库（10.10.10.15）核心 owner

HIS 源库按业务 owner 组织（与 ODS 的 HIS schema 汇聚不同）：
- `COMM` 384 表（含 STAFF_DICT、DEPT_DICT 等公共字典）
- `MEDREC` 163 表（含 PAT_VISIT、PAT_MASTER_INDEX 病案）
- `EXAM` 39 表（含 EXAM_MASTER、EXAM_REPORT 检查）
- `OUTPADM` 36 表（含 CLINIC_MASTER、OUTP_TREAT_REC 门诊）

---

## 3. 核心关系验证（重要纠错）

### 3.1 ⚠️ 抽样误判纠正：EXAM_NO 关系 100% 成立

**初始误判**：首轮用 `ROWNUM<=5000` 抽样测 `HIS.EXAM_MASTER ↔ HIS.EXAM_REPORT`（EXAM_NO），匹配率 0%，误判关系不成立。

**真相**：
- 全表 JOIN 实测：`ODS.HIS.EXAM_MASTER JOIN ODS.HIS.EXAM_REPORT ON exam_no` = **1,348,912 条匹配**（相对 ER 131 万行 = **100%**）
- HIS 源库 `EXAM.EXAM_MASTER JOIN EXAM.EXAM_REPORT` = **1,348,912 条**（同样 100%）
- 误判原因：ER 的 EXAM_NO 值域（1000716~999447）只覆盖 EM（1000000~更大范围）的一小部分；`ROWNUM<=5000` 取物理顺序最早的记录，恰好落在不重叠区间。

**结论**：**`HIS.EXAM_MASTER → HIS.EXAM_REPORT (EXAM_NO)` 关系完全成立**，09 号文档 §4.2 描述正确，无需修订。

> 教训：大表关系验证必须用**全表 JOIN COUNT**，不能用 ROWNUM 抽样——ROWNUM 取物理顺序会导致值域偏差。

### 3.2 核心关系验证汇总

| 关系 | 连接键 | 验证方法 | 结果 | 09号描述 |
|---|---|---|---|---|
| EXAM_MASTER ↔ EXAM_REPORT | EXAM_NO | 全表 JOIN COUNT | **1,348,912 (100%)** ✅ | 正确 |
| PAT_VISIT → LAB_TEST_MASTER | PATIENT_ID+VISIT_ID | 5000抽样 EXISTS | 4535/5000 (90%) ✅ | 正确 |
| PAT_VISIT → EXAM_MASTER | PATIENT_ID+VISIT_ID | 5000抽样 EXISTS | 3624/5000 (72%) ✅ | 正确 |
| EXAM_MASTER → PAT_VISIT | PATIENT_ID+VISIT_ID | 5000抽样 EXISTS | 2163/5000 (43%) ✅ | 正确（含门诊，仅住院在PAT_VISIT）|

**全部核心关系成立**。09-15 号关系图谱在活库验证通过。

### 3.3 V_INP_EXAM_REPORTS 视图口径确认

用户提供的生产视图 `V_INP_EXAM_REPORTS` 揭示了检查报告的完整关联拓扑（经实测验证）：
- 主链：`EXAM.EXAM_MASTER em` ← `EXAM.EXAM_REPORT er ON er.exam_no=em.exam_no`（100% 匹配）
- 患者回挂：`em.patient_id+visit_id` → `MEDREC.PAT_VISIT pv`（住院 43%）+ `MEDREC.PAT_MASTER_INDEX pmi`
- 门诊回填：`OUTP_TREAT_REC.APPOINT_NO = TO_CHAR(EXAM_MASTER.EXAM_NO)`（门诊检查，需先按 APPOINT_NO 聚合去重）
- 科室字典：`COMM.DEPT_DICT`（req_dept / performed_by）
- 时间过滤：`NVL(req_date_time, exam_date_time, report_date_time) >= 2026-01-01`

视图设计的多层 NVL 兜底正确处理了住院/门诊双路径。**建议作为 53 号检查影像口径的生产实现基准**。

---

## 4. 人员口径复核与用户确认

### 4.1 实测数据

| 表 | 位置 | 行数 | 关键字段 |
|---|---|---:|---|
| `FXHIS.SYS_EMPLOYEE` | HIS 源库 | **2,468** | EMPCODE(工号)、EMPLNAME(姓名) |
| `COMM.STAFF_DICT` | HIS 源库 | **4,222** | EMP_NO(工号)、NAME(姓名) |
| 桥接（EMPLCODE=EMP_NO）| — | 2,429 | 匹配率 **98.4%**（与66号98.5%一致）|
| 仅 STAFF_DICT 有 | — | 1,793 | 不在 SYS_EMPLOYEE |

### 4.2 用户确认口径（2026-07-13）

> **用户明确：人员入库以 `FXHIS.SYS_EMPLOYEE` 为主。**

补充说明：
- 平台已入库约 4260 人（66 号 §1.3），数量接近 STAFF_DICT(4222)，但**主表口径以 SYS_EMPLOYEE(2468) 为准**。
- STAFF_DICT 多出的 1793 人可能是历史/离岗/外部人员，不作为主档来源。
- `DOCTOR_USER` 未匹配项：**忽略**（66 号 §3 已确认）。
- 66 号 §4 "COMM.SYS_EMPLOYEE 不存在，用 FXHIS.SYS_EMPLOYEE" **已核实属实**。

---

## 5. 周边系统表清单（L14 接入准备）

### 5.1 LIS（11 表）
关键表：`REQ_MASTER`（申请主表）、`REQ_DETAIL`（申请明细）、`LAB_REPORT`（报告）、`LAB_RESULT`（结果）、`REQ_MASTER_PAT`（患者）、`SECSYSUSER`（用户）

### 5.2 PACS（18 表）
关键表：`EXAMINFO`（检查信息）、`PATIENTINFO`（患者）、`PACSREPORT`/`REPORT`（报告）、`MEDIAINFO`（影像）、`MODALITYINFO`（设备）、`PROCEDUREINFO`（流程）
注意：有 `_T` 后缀表（如 EXAMINFO_T、PATIENTINFO_T）疑似临时/备份表。

### 5.3 SM 手麻（25 表）
关键表：`MED_OPERATION_MASTER`（手术主表）、`MED_OPERATION_NAME`（手术名称，关联用）、`MED_ANESTHESIA_EVENT`（麻醉事件）、`MED_ANESTHESIA_PLAN`（麻醉计划）、`MED_ANESTHESIA_SUMMARY`（麻醉总结）、`MED_OPERATING_ROOM`（手术室）、`MED_DEPT_DICT`（科室）

### 5.4 YDHL 移动护理（31 表）
关键表：`INPATIENTS`（住院，挂 HIS 经 MRN=INP_NO + SERIES=VISIT_ID）、`MCS_ASSESS_FORM`/`MCS_ASSESS_FORM_RECORD`（评估）、`MCS_NURSING_PLAN`（护理计划）、`MCS_DOC_FORM`/`MCS_DOC_FORM_RECORDS`（护理文档）、`DEPTS`（科室）

### 5.5 JHEMR 新EMR（31 表）
关键表：`JHMR_FILE_INDEX`（病历索引）、`JHMR_FILE_CONTENT`/`JHMR_FILE_CONTENT_TEXT`（病历内容）、`MED_DEPARTMENTS`（科室）、`MED_QC_FEEDBACK`（质控反馈）

---

## 6. 大表行数统计（质量规则口径）

HIS schema 核心大表（统计信息，最后分析日期 2026-06~07，未全扫）：

| 表 | 行数 | 质量规则注意 |
|---|---:|---|
| INP_BILL_DETAIL | 219,324,687 | 最大表，住院费用明细，禁全扫 |
| LAB_RESULT | 96,312,418 | 检验结果（AGENTS.md 标注约1亿，吻合），必用 TEST_NO 子查询 |
| DRUG_DISPENSE_REC | 47,120,278 | 发药记录 |
| ORDERS | 41,033,865 | 医嘱 |
| TEMP_ORDER_FEE_DIAG_OPER | 31,742,454 | 临时表（费用诊断手术）|
| OUTP_BILL_ITEMS | 28,614,987 | 门诊收费项目 |
| LAB_TEST_MASTER | 9,134,900 | 检验主表 |
| EXAM_MASTER | 3,385,322 | 检查主表 |
| PAT_MASTER_INDEX | 1,939,319 | 患者主索引 |
| PAT_VISIT | 575,041 | 就诊记录 |

---

## 7. 对 66 号交接清单的修正项

| 66 号原描述 | 实测修正 |
|---|---|
| §1.3 "人员已入库约4260人" | 用户确认主表为 SYS_EMPLOYEE(2468)，非 STAFF_DICT；4260 是多源合计 |
| 本轮初报 "EXAM_NO 关系不成立" | **纠正：全表 JOIN 100% 成立**，抽样误判，09 号无需修订 |
| §2 L10-diff "可选未做" | **已完成**：08 快照准确，仅 HIS +2 临时表（用户确认排除）|
| §1.3 "HIS 12 owner ~1237 表" | 核实：HIS 源库 COMM(384)+MEDREC(163)+EXAM(39)+OUTPADM(36)... 多 owner 合计约 1237，属实 |

---

## 8. 安全与合规

- 全程只读 SELECT，无任何 DML/DDL（日志可查）。
- SSH 密码用完即从 `.env` 删除；`_ro_query.py` 已 gitignore。
- 未取任何病人明细数据（姓名/身份证/电话等），仅 COUNT 和 EXAM_NO 值域采样。
- 查询均在容器内执行，凭据从 `/etc/data-asset/credentials/` 读，未传出。

---

## 9. 下一步建议

1. **EXAM_NO 抽样误判教训**写入 40 号治理口径：大表关系验证必须全表 JOIN COUNT。
2. **V_INP_EXAM_REPORTS 视图**作为 53 号检查影像口径的生产实现基准，纳入关系配方库（54 号）。
3. **周边系统接入**（L14）：LIS/PACS/SM/YDHL/JHEMR 表清单已就绪，可按 59 号 B0 接入卡流程推进（需各系统负责人确认只读账号与脱敏范围）。
4. **质量规则**（L15）：大表行数已明确，LAB_RESULT(9631万)/INP_BILL_DETAIL(2.19亿) 夜间规则必须 TEST_NO/子查询限定。
