# -*- coding: utf-8 -*-
"""S4：验证计划生成。每 probe：单条只读 SQL、绑定边界、指标、批次、批准需求。
全部聚合输出 ≤50 行；业务键/时间窗有界；超时 60s。
"""
import json
import os
from datetime import datetime

RUN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PROBES = [
    {
        "probe_id": "P-B1-01", "batch": "B1", "source_code": "ods_8_216", "dialect": "oracle11g",
        "target_edge": "HIS.PAT_MASTER_INDEX(PATIENT_ID) <-> HIS.PAT_VISIT(PATIENT_ID) [existing 平台#1]",
        "question": "一名患者应有多条住院；PAT_MASTER_INDEX.PATIENT_ID 是否父键唯一；PAT_VISIT 孤儿率",
        "sql": """WITH cs AS (
  SELECT PATIENT_ID, VISIT_ID FROM HIS.PAT_VISIT
  WHERE DISCHARGE_DATE_TIME >= DATE '2025-06-01' AND DISCHARGE_DATE_TIME < DATE '2025-07-01' AND ROWNUM <= 200
), k AS (SELECT DISTINCT PATIENT_ID FROM cs)
SELECT
  (SELECT COUNT(*) FROM cs) child_rows,
  (SELECT COUNT(*) FROM k) distinct_child_keys,
  (SELECT COUNT(*) FROM (SELECT PATIENT_ID FROM HIS.PAT_MASTER_INDEX WHERE PATIENT_ID IN (SELECT PATIENT_ID FROM k) GROUP BY PATIENT_ID HAVING COUNT(*) > 1)) parent_dup_groups,
  (SELECT COUNT(*) FROM k kx WHERE EXISTS (SELECT 1 FROM HIS.PAT_MASTER_INDEX p WHERE p.PATIENT_ID = kx.PATIENT_ID)) matched_keys,
  (SELECT COUNT(*) FROM k kx WHERE NOT EXISTS (SELECT 1 FROM HIS.PAT_MASTER_INDEX p WHERE p.PATIENT_ID = kx.PATIENT_ID)) orphan_keys
FROM dual""",
        "scope": "2025-06 出院窗内前200住院键", "metrics": ["child_rows", "distinct_child_keys", "parent_dup_groups", "matched_keys", "orphan_keys"],
        "expected": "parent_dup_groups=0；orphan_keys≈0（<1%）", "max_rows": 1, "timeout_s": 60,
    },
    {
        "probe_id": "P-B1-02", "batch": "B1", "source_code": "ods_8_216", "dialect": "oracle11g",
        "target_edge": "HIS.DIAGNOSIS(PATIENT_ID,VISIT_ID) <-> HIS.PAT_VISIT(PATIENT_ID,VISIT_ID) [recipe_candidate]",
        "question": "组合键完整性（空键率）与孤儿率；诊断子表一对多属预期",
        "sql": """WITH cs AS (
  SELECT PATIENT_ID, VISIT_ID FROM HIS.PAT_VISIT
  WHERE DISCHARGE_DATE_TIME >= DATE '2025-06-01' AND DISCHARGE_DATE_TIME < DATE '2025-07-01' AND ROWNUM <= 200
), dg AS (
  SELECT d.PATIENT_ID, d.VISIT_ID FROM HIS.DIAGNOSIS d
  WHERE (d.PATIENT_ID, d.VISIT_ID) IN (SELECT PATIENT_ID, VISIT_ID FROM cs)
)
SELECT
  (SELECT COUNT(*) FROM dg) diag_rows,
  (SELECT COUNT(*) FROM dg WHERE PATIENT_ID IS NULL OR VISIT_ID IS NULL) null_key_rows,
  (SELECT COUNT(*) FROM (SELECT PATIENT_ID, VISIT_ID FROM dg GROUP BY PATIENT_ID, VISIT_ID HAVING COUNT(*) > 1)) multi_diag_visits,
  (SELECT COUNT(*) FROM dg dgx WHERE NOT EXISTS (SELECT 1 FROM cs v WHERE v.PATIENT_ID = dgx.PATIENT_ID AND v.VISIT_ID = dgx.VISIT_ID)) orphan_rows
FROM dual""",
        "scope": "同窗住院键下的诊断行", "metrics": ["diag_rows", "null_key_rows", "multi_diag_visits", "orphan_rows"],
        "expected": "null_key_rows=0；orphan_rows=0（IN 限定下应为0，否则组合键语义有误）", "max_rows": 1, "timeout_s": 60,
    },
    {
        "probe_id": "P-B1-03", "batch": "B1", "source_code": "ods_8_216", "dialect": "oracle11g",
        "target_edge": "HIS.PAT_MASTER_INDEX(INP_NO) <-> MTL.EPR_INPATIENT_DOCINDEX(P_INPATIENT_NO) [existing 平台#22] + VISIT_ID 编号系疑点",
        "question": "MTL 本地住院次(P_INPATIENT_TIMES)与 HIS VISIT_ID 是否同一编号系（182号曾发现手麻两套编号）",
        "sql": """WITH di AS (
  SELECT P_INPATIENT_NO, P_INPATIENT_TIMES FROM MTL.EPR_INPATIENT_DOCINDEX
  WHERE ADMIT_DATE_TIME >= DATE '2025-06-01' AND ADMIT_DATE_TIME < DATE '2025-07-01' AND ROWNUM <= 200
), j AS (
  SELECT di.P_INPATIENT_TIMES mtl_times, v.VISIT_ID his_visit_id
  FROM di JOIN HIS.PAT_MASTER_INDEX pmi ON pmi.INP_NO = di.P_INPATIENT_NO
  LEFT JOIN HIS.PAT_VISIT v ON v.PATIENT_ID = pmi.PATIENT_ID AND v.VISIT_ID = di.P_INPATIENT_TIMES
)
SELECT
  (SELECT COUNT(*) FROM di) docindex_rows,
  (SELECT COUNT(*) FROM j) joined_rows,
  (SELECT COUNT(*) FROM j WHERE his_visit_id IS NULL) visit_unmatched,
  (SELECT COUNT(*) FROM j WHERE his_visit_id IS NOT NULL AND mtl_times = his_visit_id) times_equal
FROM dual""",
        "scope": "2025-06 入院窗前200文书索引", "metrics": ["docindex_rows", "joined_rows", "visit_unmatched", "times_equal"],
        "expected": "joined≈docindex；times_equal 占比提示两编号系一致性与例外规模", "max_rows": 1, "timeout_s": 60,
        "note": "结果只看聚合；mtl_times/his_visit_id 不外带",
    },
    {
        "probe_id": "P-B1-04", "batch": "B1", "source_code": "ods_8_216", "dialect": "oracle11g",
        "target_edge": "CDA.CDA_DICTIONARY 院内编码映射唯一性（值域映射放大风险）",
        "question": "同一字典名称+院内编码是否存在多映射（多映射会导致 JOIN 放大）",
        "sql": """SELECT 字典名称_col, 院内编码_col, COUNT(*) n
FROM (SELECT DICT_NAME 字典名称_col, HOSPITAL_CODE 院内编码_col FROM CDA.CDA_DICTIONARY)
GROUP BY 字典名称_col, 院内编码_col HAVING COUNT(*) > 1""",
        "scope": "字典全表（小表）", "metrics": ["dup_mapping_groups"],
        "expected": "0 组；>0 组列出待人工裁决", "max_rows": 50, "timeout_s": 60,
        "note": "列名以平台当前元数据为准执行前核对（历史称谓可能为 字典名称/院内编码）",
    },
    {
        "probe_id": "P-B2-05", "batch": "B2", "source_code": "ods_8_216", "dialect": "oracle11g",
        "target_edge": "门诊：CLINIC_MASTER / OUTP_TREAT_REC / OUTP_ORDER_DESC 就诊键链",
        "question": "一次门诊就诊多处方/多医嘱基数；门诊号映射",
        "sql": """WITH cm AS (
  SELECT CLINIC_NO, PATIENT_ID FROM HIS.CLINIC_MASTER
  WHERE VISIT_DATE >= DATE '2025-06-01' AND VISIT_DATE < DATE '2025-07-01' AND ROWNUM <= 200
)
SELECT
  (SELECT COUNT(*) FROM cm) clinic_rows,
  (SELECT COUNT(*) FROM (SELECT o.CLINIC_NO FROM HIS.OUTP_ORDER_DESC o WHERE o.CLINIC_NO IN (SELECT CLINIC_NO FROM cm) GROUP BY o.CLINIC_NO HAVING COUNT(*) > 1)) multi_order_clinics,
  (SELECT COUNT(*) FROM (SELECT t.CLINIC_NO FROM HIS.OUTP_TREAT_REC t WHERE t.CLINIC_NO IN (SELECT CLINIC_NO FROM cm) GROUP BY t.CLINIC_NO HAVING COUNT(*) > 1)) multi_treat_clinics
FROM dual""",
        "scope": "2025-06 门诊窗前200就诊", "metrics": ["clinic_rows", "multi_order_clinics", "multi_treat_clinics"],
        "expected": "多处方/多医嘱为预期一对多；用于确认粒度口径", "max_rows": 1, "timeout_s": 60,
        "note": "列名执行前以平台元数据核对",
    },
    {
        "probe_id": "P-B3-06", "batch": "B3", "source_code": "ods_8_216", "dialect": "oracle11g",
        "target_edge": "LAB_TEST(TEST_NO) <-> LAB_RESULT(TEST_NO) 亿级表强约束",
        "question": "TEST_NO 父键唯一性与明细一对多规模；孤儿率",
        "sql": """WITH lt AS (
  SELECT TEST_NO FROM HIS.LAB_TEST
  WHERE SAMPLE_DATE >= DATE '2025-06-10' AND SAMPLE_DATE < DATE '2025-06-17' AND ROWNUM <= 100
), lr AS (
  SELECT /*+ LEADING(lt) USE_NL(r) */ r.TEST_NO FROM HIS.LAB_RESULT r
  WHERE r.TEST_NO IN (SELECT TEST_NO FROM lt)
)
SELECT
  (SELECT COUNT(*) FROM lt) parent_keys,
  (SELECT COUNT(*) FROM (SELECT TEST_NO FROM lt GROUP BY TEST_NO HAVING COUNT(*) > 1)) parent_dup,
  (SELECT COUNT(*) FROM lr) result_rows,
  (SELECT COUNT(*) FROM (SELECT TEST_NO FROM lr GROUP BY TEST_NO HAVING COUNT(*) > 1)) multi_item_tests,
  (SELECT COUNT(*) FROM lr lrx WHERE NOT EXISTS (SELECT 1 FROM lt x WHERE x.TEST_NO = lrx.TEST_NO)) orphan_rows
FROM dual""",
        "scope": "一周采样窗前100 TEST_NO（子查询限定，禁全表扫）", "metrics": ["parent_keys", "parent_dup", "result_rows", "multi_item_tests", "orphan_rows"],
        "expected": "parent_dup=0；multi_item_tests≈parent（项目明细一对多为预期）；orphan=0", "max_rows": 1, "timeout_s": 60,
    },
    {
        "probe_id": "P-B4-07", "batch": "B4", "source_code": "ods_8_216", "dialect": "oracle11g",
        "target_edge": "HIS.PAT_VISIT(PATIENT_ID,VISIT_ID) <-> SM.MED_OPERATION_MASTER(PATIENT_ID,VISIT_ID) [recipe_candidate] + 同日多台",
        "question": "手术三键粒度；同一患者+住院次+手术日多台手术规模（麻醉术后访视图按日匹配的风险）",
        "sql": """WITH cs AS (
  SELECT PATIENT_ID, VISIT_ID FROM HIS.PAT_VISIT
  WHERE DISCHARGE_DATE_TIME >= DATE '2025-06-01' AND DISCHARGE_DATE_TIME < DATE '2025-07-01' AND ROWNUM <= 200
), mo AS (
  SELECT PATIENT_ID, VISIT_ID, OPER_DATE FROM SM.MED_OPERATION_MASTER
  WHERE (PATIENT_ID, VISIT_ID) IN (SELECT PATIENT_ID, VISIT_ID FROM cs)
)
SELECT
  (SELECT COUNT(*) FROM mo) oper_rows,
  (SELECT COUNT(*) FROM mo WHERE PATIENT_ID IS NULL OR VISIT_ID IS NULL) null_key,
  (SELECT COUNT(*) FROM mo mox WHERE NOT EXISTS (SELECT 1 FROM cs v WHERE v.PATIENT_ID = mox.PATIENT_ID AND v.VISIT_ID = mox.VISIT_ID)) orphans,
  (SELECT COUNT(*) FROM (SELECT PATIENT_ID, VISIT_ID, TRUNC(OPER_DATE) d FROM mo GROUP BY PATIENT_ID, VISIT_ID, TRUNC(OPER_DATE) HAVING COUNT(*) > 1)) same_day_multi
FROM dual""",
        "scope": "同窗住院键的手术记录", "metrics": ["oper_rows", "null_key", "orphans", "same_day_multi"],
        "expected": "same_day_multi>0 属真实业务（多台）；验证视图按日 ROW_NUMBER 选一是否合理待人工", "max_rows": 1, "timeout_s": 60,
    },
    {
        "probe_id": "P-B5-08", "batch": "B5", "source_code": "ods_8_216", "dialect": "oracle11g",
        "target_edge": "JHEMR.JHMR_FILE_INDEX(FILE_UNIQUE_ID) <-> JHEMR.JHMR_FILE_CONTENT_TEXT(FILE_UNIQUE_ID) [existing]；ODS 实例 JHEMR schema 可达性",
        "question": "ODS 实例 JHEMR schema 对象存在性与近期数据量（jhemr 草稿部署前提）",
        "sql": """SELECT
  (SELECT COUNT(*) FROM ALL_TABLES WHERE OWNER = 'JHEMR' AND TABLE_NAME = 'JHMR_FILE_INDEX') idx_in_jhemr_schema,
  (SELECT COUNT(*) FROM ALL_TABLES WHERE OWNER = 'ODS' AND TABLE_NAME = 'JHMR_FILE_INDEX') idx_in_ods_schema,
  (SELECT COUNT(*) FROM JHEMR.JHMR_FILE_INDEX WHERE CREATE_TIME >= DATE '2025-06-01' AND CREATE_TIME < DATE '2025-07-01') recent_rows
FROM dual""",
        "scope": "数据字典+一月窗计数", "metrics": ["idx_in_jhemr_schema", "idx_in_ods_schema", "recent_rows"],
        "expected": "确认 JHEMR schema 在 ODS 实例的身份；草稿引用的物理落点", "max_rows": 1, "timeout_s": 60,
        "note": "CREATE_TIME 列名执行前核对；若 JHEMR schema 不在 ODS 实例，草稿需按跨实例改判",
    },
    {
        "probe_id": "P-B5-09", "batch": "B5", "source_code": "his_source_10_10_10_15", "dialect": "oracle11g",
        "target_edge": "HISUSER 活库视图裸名对象的同义词解析（S2 synonym_or_schema_unresolved 9 项）",
        "question": "PAT_MASTER_INDEX/DEPT_DICT/PAT_VISIT/SYS_EMPLOYEE/D07_EXAM_ITEM_MAP 等在 HISUSER 视角解析到哪个 owner（synonym/dblink）",
        "sql": """SELECT TABLE_NAME, OWNER, TABLE_TYPE FROM ALL_SYNONYMS_BASE_VIEW""",
        "scope": "元数据字典查询（不扫业务表）",
        "metrics": ["synonym_targets"],
        "expected": "给出每个裸名的物理 owner 或 dblink 目标，消除 9 项 unresolved",
        "max_rows": 50, "timeout_s": 60,
        "note": "实际执行时替换为：SELECT SYNONYM_NAME, TABLE_OWNER, TABLE_NAME, DB_LINK FROM ALL_SYNONYMS WHERE SYNONYM_NAME IN ('PAT_MASTER_INDEX','DEPT_DICT','PAT_VISIT','SYS_EMPLOYEE','D07_EXAM_ITEM_MAP','CLINIC_MASTER','OUTP_ORDER_DESC','OUTP_TREAT_REC','CLINIC_ITEM_MAPPING') AND OWNER IN ('HISUSER','PUBLIC')",
    },
    {
        "probe_id": "P-B5-10", "batch": "B5", "source_code": "dialysis_postgresql_10_10_10_88", "dialect": "postgresql",
        "target_edge": "血透 TREATMENT_* <-> REGISTER_PATIENTINFOMATION 主从键（HISTORY_UNRESOLVED→HEMODIALYSIS）",
        "question": "血透历史 SQL 对象在 PG 血透库的真实键；治疗记录-登记表基数",
        "sql": """WITH rp AS (
  SELECT "ID" FROM public."REGISTER_PATIENTINFOMATION" LIMIT 200
)
SELECT
  (SELECT COUNT(*) FROM rp) reg_rows,
  (SELECT COUNT(*) FROM public."TREATMENT_TREATMENT" tt WHERE tt."REGISTERID" IN (SELECT "ID" FROM rp)) treat_rows,
  (SELECT COUNT(*) FROM public."TREATMENT_TREATMENT" tt WHERE tt."REGISTERID" IN (SELECT "ID" FROM rp) AND tt."REGISTERID" IS NULL) null_key
""",
        "scope": "前200登记键", "metrics": ["reg_rows", "treat_rows", "null_key"],
        "expected": "确认治疗-登记一对多；列名（REGISTERID/ID）执行前以平台元数据核对", "max_rows": 1, "timeout_s": 60,
    },
    {
        "probe_id": "P-B5-11", "batch": "B5", "source_code": "pathology_sqlserver_10_10_9_41", "dialect": "sqlserver",
        "target_edge": "dbo.Pitaya(Status=512) 病理主表状态过滤",
        "question": "Status=512 含义与分布（195 §2.2 遗留问题）",
        "sql": "SELECT TOP 20 Status, COUNT(*) n FROM dbo.Pitaya GROUP BY Status ORDER BY n DESC",
        "scope": "病理主表聚合", "metrics": ["status_distribution"],
        "expected": "512 的占比与其他状态分布，为值域候选提供证据", "max_rows": 20, "timeout_s": 60,
    },
    {
        "probe_id": "P-B1-12", "batch": "B1", "source_code": "ods_8_216", "dialect": "oracle11g",
        "target_edge": "CDA.T_JBJL 存在性（jhemr 草稿引用，平台无行）",
        "question": "CDA schema 是否有 T_JBJL；草稿引用是否有效",
        "sql": "SELECT OWNER, OBJECT_NAME, OBJECT_TYPE FROM ALL_OBJECTS WHERE OBJECT_NAME = 'T_JBJL'",
        "scope": "数据字典", "metrics": ["t_jbjl_exists"],
        "expected": "存在→补元数据缺口；不存在→草稿引用无效需修", "max_rows": 10, "timeout_s": 30,
    },
]

plan = {
    "generated_at": datetime.now().isoformat(),
    "design_rules": [
        "单条 SELECT/WITH 只读；聚合输出；max_rows≤50；超时60s",
        "业务键来自时间窗/主键子查询（有界）；HIS.LAB_RESULT 必须 TEST_NO 限定",
        "Oracle11g：不用 FETCH FIRST；用 ROWNUM",
        "样本/受限全集标记必须保留，样本通过≠全量 verified",
        "执行窗口：夜窗优先；白天执行须单独批准（本 run 未获批→S5 BLOCKED_WINDOW）",
    ],
    "batches": {"B1": 5, "B2": 1, "B3": 1, "B4": 1, "B5": 5},
    "probes": PROBES,
}
json.dump(plan, open(os.path.join(RUN_DIR, "validation_plan.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
os.makedirs(os.path.join(RUN_DIR, "sql", "probes"), exist_ok=True)
for p in PROBES:
    open(os.path.join(RUN_DIR, "sql", "probes", p["probe_id"] + ".sql"), "w", encoding="utf-8").write(
        "-- probe %s | %s | %s\n-- question: %s\n-- scope: %s\n-- note: %s\n%s\n" % (
            p["probe_id"], p["source_code"], p["dialect"], p["question"], p["scope"], p.get("note", ""), p["sql"]))
print("validation_plan.json +", len(PROBES), "probe SQL 写出")
