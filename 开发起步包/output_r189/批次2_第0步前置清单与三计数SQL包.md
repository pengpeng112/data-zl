# 189 批次 2 第 0 步前置清单与三计数 SQL 包（OFFLINE_REBUILT_NOT_LIVE）

> 类别：模块计划产物（189 批次 2 备料）
> 生成：2026-09-25，203 L2 离线重建。**未连接任何数据库，未做 live 复核**。
> 依据：189 v1.1 §3.2（MTL/JHEMR 月计数与 TOPIC 证据）、§4 批次 2 第 0 步、§7.2（MTL 18 清单）。
> 替代：202 会话声称的"批次 2 清单/SQL 包"（原产物随 output_r189 目录丢失，从未入库）。

## 1. MTL 口径（与 202 独立复核一致）

- 批次 1 交集 **12**：同时出现在 §7.1（ODS 41 含 2025-01-01）与 §7.2（MTL 依赖 18）中——这些视图批次 1 改完日期后 2025-01~04 仍有 MTL 残量、05 后仍空，必须接 JHEMR。
- MTL 依赖全量 **18**：§7.2 清单。
- 其余 **6** 进入批次 2：`V_EMR_DEATH_RECORD`、`V_EMR_INFOR_CRITICALLY_ILL`、`V_EMR_INFOR_OTHERS`、`V_EMR_INFOR_SPEC_EXAM_TREAT`、`V_EMR_MEDICAL_RECORD_INFO`、`V_EMR_NURSING_ASSESSMENT`（不在批次 1 日期工单内，因无 2025 上界谓词或未纳入 GET_DDL 批次，但 2025-05 后同样缺文书）。

## 2. 第 0 步三计数要求（未完成不得改视图）

- 窗口：2025-04～06（必要时扩 03～07）。
- 匹配键：`PATIENT_ID + VISIT_ID + 规范化 TOPIC/DOC_TYPE + 时间邻近`（建议 ±1 天，不对再放宽并记录进对照表）。
- JHEMR 过滤一律 `NVL(DELETE_FLAG,0)=0`。
- 输出每类文书：重叠 / 仅 MTL / 仅 JHEMR 三计数 → 三选一选型（时间硬切 / 并集去重 / 按源偏好）→ **用户确认后**才改视图。
- 会诊 `V_EMR_HOS_CONSUL_RECORD`、转诊 `V_EMR_REFERRAL_HOS_RECORD` 未出现在 MTL 依赖查询结果中，执行前先复核依赖（§7.2 尾注）。
- 执行窗口：ODS 监听可用时段，夜间优先，避开 docare 00:10；一次跑完，白天失败标 BLOCKED 不重试。

## 3. 三计数 SQL 模板（每视图一套，MTL_DOC_TYPE / TOPIC 过滤逐视图对照后填入）

```sql
-- <视图名>：MTL vs JHEMR 三计数（2025-04~06，重叠键 ±1 天）
-- 【MTL_DOC_TYPE_FILTER】【JHEMR_TOPIC_FILTER】为逐视图对照占位，禁猜值域
WITH m AS (
  SELECT PATIENT_ID, VISIT_ID, DOC_TYPE, DOC_CREATE_DATE
  FROM MTL.EPR_INPATIENT
  WHERE DOC_CREATE_DATE >= DATE '2025-04-01'
    AND DOC_CREATE_DATE <  DATE '2025-07-01'
    AND <MTL_DOC_TYPE_FILTER>
), j AS (
  SELECT PATIENT_ID, VISIT_ID, TOPIC, CREATE_DATE_TIME
  FROM JHEMR.JHMR_FILE_INDEX
  WHERE NVL(DELETE_FLAG, 0) = 0
    AND CREATE_DATE_TIME >= DATE '2025-04-01'
    AND CREATE_DATE_TIME <  DATE '2025-07-01'
    AND <JHEMR_TOPIC_FILTER>
)
SELECT
  (SELECT count(*) FROM m)                                              AS mtl_total,
  (SELECT count(*) FROM j)                                              AS jhemr_total,
  (SELECT count(*) FROM m JOIN j ON m.PATIENT_ID = j.PATIENT_ID
       AND m.VISIT_ID = j.VISIT_ID
       AND abs(trunc(m.DOC_CREATE_DATE) - trunc(j.CREATE_DATE_TIME)) <= 1) AS overlap_1d,
  (SELECT count(*) FROM m WHERE NOT EXISTS (
       SELECT 1 FROM j WHERE j.PATIENT_ID = m.PATIENT_ID AND j.VISIT_ID = m.VISIT_ID
         AND abs(trunc(j.CREATE_DATE_TIME) - trunc(m.DOC_CREATE_DATE)) <= 1)) AS only_mtl,
  (SELECT count(*) FROM j WHERE NOT EXISTS (
       SELECT 1 FROM m WHERE m.PATIENT_ID = j.PATIENT_ID AND m.VISIT_ID = j.VISIT_ID
         AND abs(trunc(m.DOC_CREATE_DATE) - trunc(j.CREATE_DATE_TIME)) <= 1)) AS only_jhemr
FROM dual;
```

## 4. 逐视图 TOPIC 对照占位（依据 189 §3.2 证据，未 live 复核）

| # | 视图 | JHEMR TOPIC 证据（2025-05+ 抽样计数） | 占位说明 |
|---|---|---|---|
| 1 | V_EMR_DISCHARGE_RECORD | 「出院记录」21,206 | TOPIC=出院记录，低风险 |
| 2 | V_EMR_ADMISSION_RECORD | 「入院记录」9,978 + 专科别名约 3,700 | 必须收专科别名，仅 '入院记录' 会漏 |
| 3 | V_EMR_OPERA_RECORD | 「手术记录」5,885 | 低风险 |
| 4 | V_EMR_HOS_POSTOPER_RECORD | 「术后首次病程记录」15,079 | 低风险 |
| 5 | V_EMR_HOS_PREOP_DISCUSS | 「术前小结及术前讨论结论记录」15,008 等别名串 | 禁只 like '%术前讨论%'，先 TOPIC 全清单对照 |
| 6 | V_EMR_HOS_CONSUL_RECORD | 「会诊记录」19,474 | 先复核依赖（§7.2 尾注） |
| 7 | V_EMR_REFERRAL_HOS_RECORD | —（转诊族证据未列） | TOPIC 待对照 |
| 8 | V_EMR_ADMISSION_DEAD_RECORD_TF | 24 小时入院死亡族 | TOPIC 待对照 |
| 9 | V_EMR_HOS_CHANGE_MAJOR_RECORD | 转科：转入 1,542/转出 1,497；「转科记录」仅 54 | 必须映射转入+转出，现 like '%转科%' 会漏主数据 |
| 10 | V_EMR_HOS_DND_RECORD | 死亡讨论族 | TOPIC 待对照 |
| 11 | V_EMR_HOS_DIFFIC_CASE_DISCUSS | 疑难讨论约 34（MTL 2024=115，口径存疑） | 先出对照与空窗说明再定 |
| 12 | V_EMR_HOS_SAVE_RECORD | 抢救记录族 | TOPIC 待对照 |
| 13 | V_EMR_HOS_SUCCESSION_RECORD | 交接班 JHEMR=0 | 按源偏好候选（MTL 2024 也仅 21，不作为切换回归） |
| 14 | V_EMR_INFOR_OPERATION | 手术知情有对应 TOPIC | 知情族 TOPIC 散，逐个对照 |
| 15 | V_EMR_INFOR_CRITICALLY_ILL | 病危通知有对应 TOPIC | 同上 |
| 16 | V_EMR_INFOR_OTHERS | 其它知情 TOPIC 很散 | 同上 |
| 17 | V_EMR_INFOR_SPEC_EXAM_TREAT | 特殊检查知情有对应 TOPIC | 同上 |
| 18 | V_EMR_MEDICAL_RECORD_INFO / V_EMR_DEATH_RECORD / V_EMR_NURSING_ASSESSMENT | 汇总/死亡记录/护理评估 | 死亡记录有 TOPIC；护理评估走量表族，TOPIC 待对照 |

> 麻醉知情不进批次 2（对应视图不依赖 MTL，走 SM）。输血知情有对应 TOPIC。
> MTL 侧 DOC_TYPE 值域未取证：执行第 0 步前先对 MTL.EPR_INPATIENT.DOC_TYPE 做只读 DISTINCT 采样（限 2025-04～06），禁猜。

## 5. 选型判定表（三计数出数后填）

| 视图 | 重叠 | 仅MTL | 仅JHEMR | 选型（硬切/并集去重/按源偏好） | 用户确认 |
|---|---|---|---|---|---|
| （18 行，出数后逐行填） | | | | | |

## 6. 状态

- 本包为 **OFFLINE_REBUILT_NOT_LIVE**：SQL 未在活库执行，TOPIC/DOC_TYPE 过滤为占位，须按 §4 对照 + live 值域采样后才能作为执行版。
- 第 0 步执行授权：189 §5——"可准备 SQL；监听可用；建议一次夜间执行；写库仍禁止"。203 §21——对象清单恢复后可按既有批准通道和安全时段只读执行；五要素不覆盖则仅保留 SQL 包。
