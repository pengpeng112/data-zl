> 类别：复核意见
>
> 状态：已复核并回写 96 | 日期：2026-07-27
>
> 对象：`96_临床诊断字典同步海量与HIS分析与开发步骤.md`
> 来源：外部 AI 复核结论 + 本仓库元数据二次核实
> 处理：P0/P1 已回写 96 修订版；本文件保留证据与裁决。

# 96 号计划复核意见：字段缺失与 SQL 语法风险

## 0. 二次核实结论摘要

| 外部复核主张 | 二次核实 | 裁决 |
|---|---|---|
| 整体设计合理、海量手术三表 26/27/5 列、7 目标表齐全 | **成立**（海量列数与资产包一致） | 采纳 |
| 字典中心 5 表 + 8 code_sets | **成立**（模型 5 表；导入脚本 `CODE_SETS` 恰 8 个） | 采纳 |
| P0：DIAGNOSIS_DICT 清单不完整 | **成立**（计划仅摘要列）；列数应为 **34** 而非外部写的 36 | **修正后采纳** |
| 漏字段含 MTB=「结核耐药」 | **不成立**：源端注释为**门诊慢特病** | **纠正表述** |
| P1-1：SQL 方言混用未标注 | **成立** | 采纳，已改 96 |
| P1-2：OPERATION_CODE 长度 16 来源不明 | **部分不成立**：`his_source_columns.csv` 明确 `length=16`；平台 `asset_columns` 可能为空需活库复核 | **部分采纳** |
| P1-3：operation_type 探活未强制 | **成立** | 采纳，阶段 0 强制交付 |
| P2 三项 | **成立或可加强** | 采纳并入 96 |

---

## 1. 实测证据

### 1.1 海量手术/诊断目标表列数（`数据资产_JHEMR_Vastbase资产包/columns.csv`）

| schema.table | 列数 | 与 96 一致性 |
|---|---:|---|
| `jhemr.operation_dict` | 26 | 一致 |
| `jhemr.operation_dict_code` | 27 | 一致 |
| `jhemr.operation_contrast_dict` | 5 | 一致 |
| `jhemr.diagnosis_dict` | 35 | 一致（计划摘要级） |
| `jhemr.jhdict_icd_vs_clinic` | 10 | 一致 |
| `jhemr.diagnosis_contrast_dict` | 5 | 一致 |
| `jhemr.jhdict_operation_vs_clinic` | 10 | 可选表，存在 |

### 1.2 HIS `COMM.DIAGNOSIS_DICT` 全列（源端资产包 + ODS 资产包均为 **34 列**）

| # | 字段 | 类型(len) | 注释 | 原 96 §3.2 是否列出 |
|---:|---|---|---|---|
| 1 | DIAGNOSIS_CODE | VARCHAR2(50) | 诊断代码 | 是 |
| 2 | DIAGNOSIS_NAME | VARCHAR2(140) | 诊断名称 | 是 |
| 3 | STD_INDICATOR | NUMBER(1) | 正名标志 | 是 |
| 4 | APPROVED_INDICATOR | NUMBER(1) | 标准化标志 | 是 |
| 5 | CREATE_DATE | DATE | 创建日期 | 是 |
| 6 | INPUT_CODE | VARCHAR2(50) | 输入码 | 是 |
| 7 | HEALTH_LEVEL | CHAR(2) | （无注释） | **否** |
| 8 | INFECT_INDICATOR | VARCHAR2(2) | （无注释，传染相关） | **否** |
| 9 | INPUT_CODE_WB | VARCHAR2(8) | 五笔码 | **否** |
| 10 | DISEASE_SORT | VARCHAR2(4) | | **否** |
| 11 | CONTAGIONCODE | VARCHAR2(20) | | **否** |
| 12 | DIAG_INDICATOR | NUMBER(1) | 1西医 2中医 3病理 4外伤 | 是 |
| 13 | NM1 | VARCHAR2(6) | 内码1 | **否** |
| 14 | NM2 | VARCHAR2(2) | 内码2 | **否** |
| 15 | DIAGNOSIS_FJ_CODE | VARCHAR2(16) | 附加码 | **否** |
| 16 | CREATE_USER | VARCHAR2(20) | 临时编码创建者 | **否** |
| 17 | DIAGNOSIS_CODE2 | VARCHAR2(16) | M码 | **否** |
| 18 | FLAG | NUMBER(1) | 1非传染病 2传染病 3食源性疾病 | **否** |
| 19 | YB_CODE | VARCHAR2(100) | **医保1.0**编码 | 是（待确认） |
| 20 | YB_NAME | VARCHAR2(150) | **医保1.0**名称 | 是（待确认） |
| 21 | MTB_FLAG | VARCHAR2(10) | **门诊慢特病**标志 0/1 | **否** |
| 22 | MTB_NAME | VARCHAR2(50) | 慢特病_病种名称 | **否** |
| 23 | MTB_CODE | VARCHAR2(50) | 慢特病_病种编码 | **否** |
| 24 | STOP_FLAG | NUMBER(1) | 停用 | 是 |
| 25 | DIAGNOSIS_CODE_GUO | VARCHAR2(100) | 国家临床版2.0 | 是 |
| 26 | DIAGNOSIS_NAME_GUO | VARCHAR2(200) | 国家临床版2.0 | 是 |
| 27 | DIAGNOSIS_CODE_MB | VARCHAR2(100) | 门诊慢特病病种映射 | **否** |
| 28 | DIAGNOSIS_NAME_MB | VARCHAR2(200) | 门诊慢特病病种映射 | **否** |
| 29 | DIAGNOSIS_CODE_ICD | VARCHAR2(100) | ICD低风险病种标识 | **否** |
| 30 | DIAGNOSIS_NAME_ICD | VARCHAR2(200) | ICD低风险病种标识 | **否** |
| 31 | DIAGNOSIS_CODE_CRB | VARCHAR2(100) | 传染病诊断 | **否** |
| 32 | DIAGNOSIS_NAME_CRB | VARCHAR2(200) | 传染病诊断 | **否** |
| 33 | DIAGNOSIS_TYPE | VARCHAR2(40) | 字典属性 | 是 |
| 34 | MENTAL_ILLNESS | VARCHAR2(1) | 精神疾病标识 | **否** |

**关于「36 列」**：当前仓库权威快照（`his_source_columns` / `数据资产_资产包`）均为 **34 列**。若活库存在未入快照的 2 列，阶段 0 探活必须 `ALL_TAB_COLUMNS` 复核并回写；在未证实前以 **34 列** 为开发基线。

**关于 MTB**：注释为门诊慢特病，**不是**结核耐药。外部复核此处业务语义有误，不得写进实现。

### 1.3 HIS `COMM.OPERATION_DICT` 与长度

| 字段 | length（his_source_columns） |
|---|---|
| OPERATION_CODE | **16** |
| OPERATION_NAME | 100 |
| OPERATION_CODE_GB | 16 |

长度 16 **有元数据来源**，并非臆造。但：

- 平台 `asset_columns` 对业务源表可能 `length` 为空；
- 长度预检**不得只查平台空字段**，应优先：① HIS 源端资产包 / ② 阶段 0 活库 `USER_TAB_COLUMNS` / `ALL_TAB_COLUMNS`。

### 1.4 字典中心

| 对象 | 证据 |
|---|---|
| 5 表 | `dict_medical.py`：code_sets / items / mappings / sync_diffs / import_runs |
| 8 code_sets | `import_medical_maintenance_dicts.CODE_SETS` 共 8 条 |

### 1.5 collector 现状（P2-1 核实）

`medical_code_source_collector.py`：

- diagnosis：只读 `CDA.CDA_DICTIONARY`（ICD-10，系统标识 HIS），**不是** `COMM.DIAGNOSIS_DICT`
- operation：只读 `SM.MED_OPERATION_NAME`，**不是** `COMM.OPERATION_DICT` / 海量字典表
- 输出：仅写平台 `asset_dict_medical_sync_diffs`，**不下发业务库**

外部复核「§5 需核实」——**已核实，原计划描述正确**。

---

## 2. 问题清单

### 🔴 P0 阻断开发（1）

| ID | 问题 | 影响 | 修订要求 |
|---|---|---|---|
| P0-1 | DIAGNOSIS_DICT 字段清单严重不完整（原 §3.2 仅约 11 列摘要） | 慢特病/传染病/精神疾病/低风险 ICD 等口径可能漏同步，影响统计与三甲相关取数 | 补全 **34 列** 清单 + 每列同步策略（写入/保留/仅全量 Excel/不碰）；与业务确认漏字段来源 |

### 🟡 P1 开发前应修正（3）

| ID | 问题 | 修订要求 |
|---|---|---|
| P1-1 | 示例 SQL 混用 Oracle / PostgreSQL 未标注连接目标 | 每段 SQL 标注 `目标库 / 方言 / source_code` |
| P1-2 | 长度预检依赖平台 length 可能为空 | 明确长度来源优先级；阶段 0 活库实测 `OPERATION_CODE`/`DIAGNOSIS_NAME` 等 max length |
| P1-3 | `operation_type` 等「待探活」未列为阶段 0 强制交付 | 阶段 0 强制交付映射表，**无映射表不得进入阶段 3 编码** |

### 🟢 P2 建议完善（3）

| ID | 问题 | 修订要求 |
|---|---|---|
| P2-1 | collector 现状 | 已核实；96 中固化「禁止把 CDA/SM 差异采集误认为下发」 |
| P2-2 | 待确认问题无优先级 | §9 按 P0/P1/P2 分级 |
| P2-3 | 回滚对新建行仅 STOP=1 会留垃圾 | 区分：更新行可回滚字段；新建行 soft-disable + 批次标记 + 可选物理清理须二次审批 |

---

## 3. 确认合理的部分

1. 诊断 + 手术统一流水线：主数据 → dry-run → 审批 → 逐条 apply。
2. 手术落点：HIS 单表宽字段 / 海量三表分写，与元数据一致。
3. 安全门禁：写开关、写凭据分离、禁 DELETE/DDL、默认只读。
4. 海量表结构与用户指定三表名称一致。
5. 平台 8 个 code_set 与诊断/手术 Excel 模型匹配。

---

## 4. 给原编写者的修订建议（已执行于 96）

1. **§3.2** 改为 DIAGNOSIS_DICT **34 列全表** + 同步策略列。
2. **所有示例 SQL** 增加「连接目标 / 方言」标题。
3. **阶段 0** 改为强制交付清单（含 hospital_no、类别映射、活库列数与长度、样本存在性）。
4. **阶段 1** 长度预检：禁止只读空平台 length。
5. **§9** 问题分级；**回滚** 新建/更新分流。
6. 全文统一 MTB=门诊慢特病；列数基线 34（活库若 36 再升基线）。

---

## 5. 强行执行的后果（未修订即开发）

| 若忽略 | 后果 |
|---|---|
| P0-1 | 只写 CODE/NAME/GUO，慢特病/传染病/精神/低风险字段空白或旧值，报表与监管口径偏差 |
| P1-1 | 自动化/AI 把 LIMIT 丢到 Oracle 或 ROWNUM 丢到 Vastbase，脚本失败或误连 |
| P1-2 | 超长手术码写入失败或截断，部分院内扩展码无法入库 |
| P1-3 | operation_type 写错类别，手术/操作统计串类 |
| P2-3 | 回滚后「停用垃圾行」堆积，字典检索仍可能扫到 |

**结论**：P0-1 与 P1 三项必须在编码前关闭；本仓库已回写 96。阶段 0 探活仍须用户授权后执行以关闭 hospital_no / 活库 34vs36 / operation_type 样例等剩余闸门。

---

## 6. 本复核自检

| 项 | 结果 |
|---|---|
| 是否连接业务库写入 | 否 |
| 列数证据来源 | his_source_columns + 资产包 + JHEMR 资产包 |
| 外部「36 列」 | 未在仓库快照证实，标为待活库确认 |
| 外部「MTB=结核耐药」 | 已纠正为门诊慢特病 |
| 96 是否已回写 | 是（同会话修订） |
