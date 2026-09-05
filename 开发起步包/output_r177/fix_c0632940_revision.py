# -*- coding: utf-8 -*-
"""182-c0632940 修订 Step2：单事务 UPDATE VISIT_ID（1→2 @OPER2；1→3 @OPER4，16 张基表）。
预检冲突→逐表 rowcount 对账（不符即 rollback）→commit→回读四重复核。用户授权 2026-09-05。"""
import json
import traceback

import oracledb

PID = "c0632940"
EXPECT = {  # 表 → 备份行数（对账基准）
    "MEDSURGERY.MED_ANESTHESIA_EVENT": 21, "MEDSURGERY.MED_ANESTHESIA_EVENT_BACK": 28,
    "MEDSURGERY.MED_ANESTHESIA_INPUT_DATA": 2, "MEDSURGERY.MED_ANESTHESIA_PLAN": 2,
    "MEDSURGERY.MED_ANESTHESIA_SUMMARY": 2, "MEDSURGERY.MED_ANES_DOC_CHECK": 10,
    "MEDSURGERY.MED_ANES_OPERHANDOVER": 2, "MEDSURGERY.MED_APPLICATION_AUDIT_TRAIL": 137,
    "MEDSURGERY.MED_CUSTOM_DATA": 972, "MEDSURGERY.MED_HBCA_SIGNATURE": 44,
    "MEDSURGERY.MED_OPERATION_ANALGESIC": 2, "MEDSURGERY.MED_OPERATION_MASTER": 2,
    "MEDSURGERY.MED_PATIENT_MONITOR_DATA": 35, "MEDSURGERY.MED_PAT_MONITOR_DATA": 22,
    "MEDSURGERY.MED_QIXIE_QINGDIAN": 261,
}
ARCHIVE = "MEDCOMM.MED_EMR_ARCHIVE_DETIAL"
EXPECT[ARCHIVE] = 16

from pathlib import Path
raw = Path("/etc/data-asset/credentials/docare_oracle_10_10_10_68.readonly").read_text(encoding="utf-8").strip()
user, pwd = raw.split(":", 1)

try:
    oracledb.init_oracle_client(lib_dir="/opt/oracle")
except Exception:
    pass
conn = oracledb.connect(user=user, password=pwd,
                        dsn="10.10.10.68:1521/docare")
conn.autocommit = False
report = {"steps": []}
try:
    cur = conn.cursor()
    # 0) 写权限探测 + 事务开启
    cur.execute("SELECT 1 FROM dual")
    report["steps"].append("connected")

    # 1) 预检：目标键冲突必须全 0，源行数=备份数
    total_src = 0
    for fq in EXPECT:
        if fq == ARCHIVE:
            src_where = "PATIENT_ID=:p AND VISIT_ID='1' AND MR_CLASS='麻醉' AND ARCHIVE_KEY IN ('2','4')"
            dst_where = "PATIENT_ID=:p AND VISIT_ID IN ('2','3') AND MR_CLASS='麻醉' AND ARCHIVE_KEY IN ('2','4')"
        else:
            src_where = "PATIENT_ID=:p AND VISIT_ID='1' AND OPER_ID IN ('2','4')"
            dst_where = "PATIENT_ID=:p AND VISIT_ID IN ('2','3') AND OPER_ID IN ('2','4')"
        cur.execute(f"SELECT COUNT(*) FROM {fq} WHERE {src_where}", {"p": PID})
        src = cur.fetchone()[0]
        cur.execute(f"SELECT COUNT(*) FROM {fq} WHERE {dst_where}", {"p": PID})
        dst = cur.fetchone()[0]
        assert dst == 0, f"{fq}: target key clash {dst}"
        assert src == EXPECT[fq], f"{fq}: src {src} != backup {EXPECT[fq]}"
        total_src += src
    report["steps"].append(f"precheck ok total_src={total_src}")

    # 2) 逐表 UPDATE（同一事务）
    updates = []
    for fq in EXPECT:
        if fq == ARCHIVE:
            updates.append((fq, "2",
                f"UPDATE {ARCHIVE} SET VISIT_ID='2' WHERE PATIENT_ID=:p AND VISIT_ID='1' AND MR_CLASS='麻醉' AND ARCHIVE_KEY='2'"))
            updates.append((fq, "3",
                f"UPDATE {ARCHIVE} SET VISIT_ID='3' WHERE PATIENT_ID=:p AND VISIT_ID='1' AND MR_CLASS='麻醉' AND ARCHIVE_KEY='4'"))
        else:
            updates.append((fq, "2",
                f"UPDATE {fq} SET VISIT_ID='2' WHERE PATIENT_ID=:p AND VISIT_ID='1' AND OPER_ID='2'"))
            updates.append((fq, "3",
                f"UPDATE {fq} SET VISIT_ID='3' WHERE PATIENT_ID=:p AND VISIT_ID='1' AND OPER_ID='4'"))
    per_table = {}
    for fq, newv, sql in updates:
        cur.execute(sql, {"p": PID})
        per_table[fq] = per_table.get(fq, 0) + cur.rowcount
    for fq, n in per_table.items():
        assert n == EXPECT[fq], f"{fq}: updated {n} != backup {EXPECT[fq]} — ROLLBACK"
    report["steps"].append("updates applied, rowcounts match backup")
    conn.commit()
    report["status"] = "committed"
except oracledb.DatabaseError as exc:
    try:
        conn.rollback()
    except Exception:
        pass
    err = str(exc).strip()[:400]
    report["status"] = "rolled_back"
    report["error"] = err
    report["auth_failed"] = "ORA-01031" in err or "insufficient privileges" in err.lower()
except Exception:
    try:
        conn.rollback()
    except Exception:
        pass
    report["status"] = "rolled_back"
    report["error"] = traceback.format_exc(limit=3)[-400:]
finally:
    conn.close()

# 3) 修订后复核（只读，独立连接；仅 committed 时）
if report.get("status") == "committed":
    from app.services.db_connectors import OracleConnector
    ro = OracleConnector(host="10.10.10.68", port=1521, database="docare",
                         user=user, password=pwd, connection_mode="direct",
                         oracle_client_lib_dir="/opt/oracle", timeout_ms=120000)
    chk = {}
    resid = 0
    for fq in EXPECT:
        w = ("PATIENT_ID=:p AND VISIT_ID='1' AND MR_CLASS='麻醉' AND ARCHIVE_KEY IN ('2','4')"
             if fq == ARCHIVE else "PATIENT_ID=:p AND VISIT_ID='1' AND OPER_ID IN ('2','4')")
        n = ro.execute_readonly(f"SELECT COUNT(*) c FROM {fq} WHERE {w}", {"p": PID}, max_rows=2)[0]["C"]
        chk[fq] = int(n)
        resid += int(n)
    itf = ro.execute_readonly(
        "SELECT FBINCU, COUNT(*) c FROM MEDSURGERY.T_ITF_SM WHERE PATIENTID=:p AND FREPORTSTYLE='住院' "
        "GROUP BY FBINCU ORDER BY FBINCU", {"p": PID}, max_rows=20)
    report["postcheck"] = {"residual_v1_oper24": resid,
                           "itf_sm_fbincu_dist": [{str(r["FBINCU"]): int(r["C"])} for r in itf]}
print(json.dumps(report, ensure_ascii=False, indent=1))
