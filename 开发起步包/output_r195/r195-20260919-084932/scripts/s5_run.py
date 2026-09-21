# -*- coding: utf-8 -*-
"""S5 执行器：修正版 12 支探针经 sjzc live 受控连接器串行执行。
- 每支：SHA-256 记录、超时 120s（连接器上限）、聚合输出
- 结果写 validation_results.jsonl（无患者明细，仅计数与聚合）
列名均经平台元数据核实（见执行记录注释）。
"""
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime

RUN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SJZC = os.path.expanduser("~/.zcode/skills/sjzc/scripts/sjzc_query.py")

PROBES = [
    # ---- B1 患者-住院-诊断-字典（ods_8_216）----
    dict(probe_id="P-B1-01", batch="B1", source="ods_8_216",
         edge="HIS.PAT_MASTER_INDEX(PATIENT_ID) <-> HIS.PAT_VISIT(PATIENT_ID)",
         sql="""WITH cs AS (
  SELECT PATIENT_ID, VISIT_ID FROM HIS.PAT_VISIT
  WHERE DISCHARGE_DATE_TIME >= DATE '2025-06-01' AND DISCHARGE_DATE_TIME < DATE '2025-07-01' AND ROWNUM <= 200
), k AS (SELECT DISTINCT PATIENT_ID FROM cs)
SELECT
  (SELECT COUNT(*) FROM cs) child_rows,
  (SELECT COUNT(*) FROM k) distinct_child_keys,
  (SELECT COUNT(*) FROM (SELECT PATIENT_ID FROM HIS.PAT_MASTER_INDEX WHERE PATIENT_ID IN (SELECT PATIENT_ID FROM k) GROUP BY PATIENT_ID HAVING COUNT(*) > 1)) parent_dup_groups,
  (SELECT COUNT(*) FROM k kx WHERE NOT EXISTS (SELECT 1 FROM HIS.PAT_MASTER_INDEX p WHERE p.PATIENT_ID = kx.PATIENT_ID)) orphan_keys
FROM dual"""),
    dict(probe_id="P-B1-02", batch="B1", source="ods_8_216",
         edge="HIS.DIAGNOSIS(PATIENT_ID,VISIT_ID) <-> HIS.PAT_VISIT(PATIENT_ID,VISIT_ID)",
         sql="""WITH cs AS (
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
FROM dual"""),
    dict(probe_id="P-B1-03", batch="B1", source="ods_8_216",
         edge="HIS.PAT_MASTER_INDEX(INP_NO) <-> MTL.EPR_INPATIENT_DOCINDEX(P_INPATIENT_NO) + P_INPATIENT_TIMES vs VISIT_ID 编号系",
         sql="""WITH di AS (
  SELECT P_INPATIENT_NO, P_INPATIENT_TIMES FROM MTL.EPR_INPATIENT_DOCINDEX
  WHERE P_INDATE >= DATE '2025-06-01' AND P_INDATE < DATE '2025-07-01' AND ROWNUM <= 200
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
FROM dual"""),
    dict(probe_id="P-B1-04", batch="B1", source="ods_8_216",
         edge="CDA.CDA_DICTIONARY(字典名称,院标编码) 映射唯一性（值域映射放大）",
         sql="""SELECT 字典名称, 院标编码, COUNT(*) n
FROM CDA.CDA_DICTIONARY
GROUP BY 字典名称, 院标编码 HAVING COUNT(*) > 1"""),
    dict(probe_id="P-B1-12", batch="B1", source="ods_8_216",
         edge="CDA.T_JBJL 存在性（jhemr 草稿引用）",
         sql="SELECT OWNER, OBJECT_NAME, OBJECT_TYPE FROM ALL_OBJECTS WHERE OBJECT_NAME = 'T_JBJL'"),
    # ---- B2 门诊（ods_8_216）----
    dict(probe_id="P-B2-05", batch="B2", source="ods_8_216",
         edge="门诊：OUTP_ORDER_DESC(CLINIC_NO)/OUTP_TREAT_REC(VISIT_DATE,VISIT_NO) <-> CLINIC_MASTER",
         sql="""WITH cm AS (
  SELECT CLINIC_NO, VISIT_DATE, VISIT_NO FROM HIS.CLINIC_MASTER
  WHERE VISIT_DATE >= DATE '2025-06-01' AND VISIT_DATE < DATE '2025-06-08' AND ROWNUM <= 200
)
SELECT
  (SELECT COUNT(*) FROM cm) clinic_rows,
  (SELECT COUNT(*) FROM (SELECT o.CLINIC_NO FROM HIS.OUTP_ORDER_DESC o WHERE o.CLINIC_NO IN (SELECT CLINIC_NO FROM cm) GROUP BY o.CLINIC_NO HAVING COUNT(*) > 1)) multi_order_clinics,
  (SELECT COUNT(*) FROM (SELECT t.VISIT_DATE, t.VISIT_NO FROM HIS.OUTP_TREAT_REC t WHERE (t.VISIT_DATE, t.VISIT_NO) IN (SELECT VISIT_DATE, VISIT_NO FROM cm) AND t.ITEM_CLASS = 'D' GROUP BY t.VISIT_DATE, t.VISIT_NO HAVING COUNT(*) > 1)) multi_treat_visits,
  (SELECT COUNT(*) FROM cm cx WHERE NOT EXISTS (SELECT 1 FROM HIS.OUTP_ORDER_DESC o WHERE o.CLINIC_NO = cx.CLINIC_NO)) clinics_without_orders
FROM dual"""),
    # ---- B3 检验（ods_8_216；LAB_RESULT 亿级强制 TEST_NO 限定）----
    dict(probe_id="P-B3-06", batch="B3", source="ods_8_216",
         edge="HIS.LAB_TEST_MASTER(TEST_NO) <-> HIS.LAB_RESULT(TEST_NO)",
         sql="""WITH lt AS (
  SELECT TEST_NO FROM HIS.LAB_TEST_MASTER
  WHERE REQUESTED_DATE_TIME >= DATE '2025-06-10' AND REQUESTED_DATE_TIME < DATE '2025-06-17' AND ROWNUM <= 100
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
FROM dual"""),
    # ---- B4 手麻（ods_8_216 SM schema）----
    dict(probe_id="P-B4-07", batch="B4", source="ods_8_216",
         edge="SM.MED_OPERATION_MASTER(PATIENT_ID,VISIT_ID[,OPER_ID]) <-> HIS.PAT_VISIT；同日多台",
         sql="""WITH cs AS (
  SELECT PATIENT_ID, VISIT_ID FROM HIS.PAT_VISIT
  WHERE DISCHARGE_DATE_TIME >= DATE '2025-06-01' AND DISCHARGE_DATE_TIME < DATE '2025-07-01' AND ROWNUM <= 200
), mo AS (
  SELECT PATIENT_ID, VISIT_ID, OPER_ID, NVL(START_DATE_TIME, SCHEDULED_DATE_TIME) opdate FROM SM.MED_OPERATION_MASTER
  WHERE (PATIENT_ID, VISIT_ID) IN (SELECT PATIENT_ID, VISIT_ID FROM cs)
)
SELECT
  (SELECT COUNT(*) FROM mo) oper_rows,
  (SELECT COUNT(*) FROM mo WHERE PATIENT_ID IS NULL OR VISIT_ID IS NULL) null_key,
  (SELECT COUNT(*) FROM mo WHERE OPER_ID IS NULL) null_oper_id,
  (SELECT COUNT(*) FROM mo mox WHERE NOT EXISTS (SELECT 1 FROM cs v WHERE v.PATIENT_ID = mox.PATIENT_ID AND v.VISIT_ID = mox.VISIT_ID)) orphans,
  (SELECT COUNT(*) FROM (SELECT PATIENT_ID, VISIT_ID, TRUNC(opdate) d FROM mo WHERE opdate IS NOT NULL GROUP BY PATIENT_ID, VISIT_ID, TRUNC(opdate) HAVING COUNT(*) > 1)) same_day_multi
FROM dual"""),
    # ---- B5 文书/JHEMR schema（ods_8_216）----
    dict(probe_id="P-B5-08", batch="B5", source="ods_8_216",
         edge="JHEMR schema 可达性 + JHMR_FILE_INDEX 近期量（jhemr 草稿部署前提）",
         sql="""SELECT
  (SELECT COUNT(*) FROM ALL_TABLES WHERE OWNER = 'JHEMR' AND TABLE_NAME = 'JHMR_FILE_INDEX') idx_in_jhemr_schema,
  (SELECT COUNT(*) FROM ALL_TABLES WHERE OWNER = 'ODS' AND TABLE_NAME = 'JHMR_FILE_INDEX') idx_in_ods_schema,
  (SELECT COUNT(*) FROM JHEMR.JHMR_FILE_INDEX WHERE CREATE_DATE_TIME >= DATE '2025-06-01' AND CREATE_DATE_TIME < DATE '2025-07-01') recent_rows
FROM dual"""),
    # ---- B5 HIS 源同义词（his_source）----
    dict(probe_id="P-B5-09", batch="B5", source="his_source_10_10_10_15",
         edge="HISUSER 视角裸名对象的同义词/DBLink 解析（S2 9 项悬案）",
         sql="""SELECT SYNONYM_NAME, OWNER, TABLE_OWNER, TABLE_NAME, DB_LINK
FROM ALL_SYNONYMS
WHERE SYNONYM_NAME IN ('PAT_MASTER_INDEX','DEPT_DICT','PAT_VISIT','SYS_EMPLOYEE','D07_EXAM_ITEM_MAP','CLINIC_MASTER','OUTP_ORDER_DESC','OUTP_TREAT_REC','CLINIC_ITEM_MAPPING')
AND OWNER IN ('HISUSER','PUBLIC')"""),
    # ---- B5 血透（dialysis PG）----
    dict(probe_id="P-B5-10", batch="B5", source="dialysis_postgresql_10_10_10_88",
         edge='TREATMENT_TREATMENT("PatientId") <-> REGISTER_PATIENTINFOMATION("Id")',
         sql="""WITH rp AS (SELECT "Id" FROM public."REGISTER_PATIENTINFOMATION" LIMIT 200)
SELECT
  (SELECT COUNT(*) FROM rp) reg_rows,
  (SELECT COUNT(*) FROM public."TREATMENT_TREATMENT" tt WHERE tt."PatientId" IN (SELECT "Id" FROM rp)) treat_rows,
  (SELECT COUNT(*) FROM (SELECT tt."PatientId" FROM public."TREATMENT_TREATMENT" tt WHERE tt."PatientId" IN (SELECT "Id" FROM rp) GROUP BY tt."PatientId" HAVING COUNT(*) > 1)) multi_treat_patients,
  (SELECT COUNT(*) FROM (SELECT DISTINCT tt."PatientId" FROM public."TREATMENT_TREATMENT" tt WHERE tt."CreateTime" >= '2025-06-01') f WHERE NOT EXISTS (SELECT 1 FROM public."REGISTER_PATIENTINFOMATION" r WHERE r."Id" = f."PatientId")) orphan_patients_2025_06
"""),
    # ---- B5 病理（pathology sqlserver）----
    dict(probe_id="P-B5-11", batch="B5", source="pathology_sqlserver_10_10_9_41",
         edge="dbo.Pitaya(Status) 状态分布（512 含义）",
         sql="SELECT TOP 20 Status, COUNT(*) n FROM dbo.Pitaya GROUP BY Status ORDER BY COUNT(*) DESC"),
]


def run_probe(p):
    sql = p["sql"].strip()
    sha = hashlib.sha256(sql.encode("utf-8")).hexdigest()
    cmd = ["python", SJZC, "live", p["source"], "--sql", sql, "--max-rows", "50"]
    t0 = datetime.now()
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=120, text=True, encoding="utf-8", errors="replace")
        out, err, rc = proc.stdout.strip(), proc.stderr.strip(), proc.returncode
    except subprocess.TimeoutExpired:
        out, err, rc = "", "TIMEOUT after 120s", -1
    dt = (datetime.now() - t0).total_seconds()
    rec = {
        "probe_id": p["probe_id"], "batch": p["batch"], "source_code": p["source"],
        "target_edge": p["edge"], "sql_sha256": sha,
        "executed_at": t0.isoformat(timespec="seconds"), "duration_s": round(dt, 1),
        "scope": "受限样本（时间窗+主键子查询，键数≤200；LAB_RESULT 仅 TEST_NO 限定）",
        "sample_type": "bounded_sample",
        "returncode": rc, "output": out[:3000] if out else "", "error": err[:800] if err else "",
    }
    return rec


def main():
    only = sys.argv[1:] if len(sys.argv) > 1 else None
    results_path = os.path.join(RUN_DIR, "validation_results.jsonl")
    done_ids = set()
    if os.path.exists(results_path):
        for line in open(results_path, encoding="utf-8"):
            try:
                done_ids.add(json.loads(line)["probe_id"])
            except Exception:
                pass
    n_ok = n_err = 0
    with open(results_path, "a", encoding="utf-8") as f:
        for p in PROBES:
            if only and p["probe_id"] not in only:
                continue
            if p["probe_id"] in done_ids and not only:
                print(f"[skip done] {p['probe_id']}")
                continue
            rec = run_probe(p)
            bad = (rec["returncode"] != 0 or not rec["output"]
                   or "ORA-" in rec["output"] or "Error" in rec["output"] or "TIMEOUT" in rec["error"])
            status = "OK" if not bad else "ERROR"
            n_ok += status == "OK"
            n_err += status != "OK"
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            print(f"[{status}] {p['probe_id']} ({rec['duration_s']}s)")
            print("   ", (rec["output"] or rec["error"]).replace("\n", "\n    ")[:600])
    print(f"\nOK={n_ok} ERROR={n_err} -> {results_path}")


if __name__ == "__main__":
    main()
