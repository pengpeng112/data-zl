# -*- coding: utf-8 -*-
"""批9 前置差距普查（只读限量，ODS 白天例外）：
25 表逐表 = 源视图总量(60s超时纪律) + 逐月行数([2026-01-01,2026-10-26) GROUP BY TRUNC(DATETIME,'MM'))
+ 目标现量(8.74)。月计数超时则退化为逐月单查（各60s），再超时标记 TIMEOUT 不阻塞。
产出 JSON 台账（差距=源窗合计-已由T+1覆盖的10P部分以外的量由执行阶段定，此处先落原始计数）。
运行：ssh 8.83 "docker exec -i data-asset-api python -" < b9_gap_survey.py
"""
import json
import traceback

import oracledb

B5 = ["EMR_ADMISSION_DIAGNOSIS", "EMR_DEATH_RECORD", "EMR_ICH_ALLERGIES",
      "EMR_DISCHARGE_RECORD", "EMR_OUTPATIENT_RECORD", "EMR_OUTPATIENT_REGISTER"]
B6 = ["EMR_INFOR_TRANS_BLOOD", "EMR_HOS_CHANGE_MAJOR_RECORD", "EMR_ANES_RECORD_BLOOD",
      "EMR_INFOR_CRITICALLY_ILL", "EMR_HOS_POSTOPER_RECORD", "EMR_BOFORE_OPERA_RECORD",
      "EMR_ANESTHESIA_RECORD", "EMR_IN_FEE_INFO_MAIN", "EMR_HOS_CONSUL_RECORD",
      "EMR_DOC_ORDER_CHECK"]
B7 = ["EMR_REFERRAL_HOS_RECORD", "EMR_HOS_DIFFIC_CASE_DISCUSS", "EMR_HOS_SUCCESSION_RECORD",
      "EMR_OPERATION_NURSING", "EMR_HOS_PREOP_DISCUSS", "EMR_AFTER_OPERA_RECORD",
      "EMR_INFOR_ANESTHESIA", "EMR_OUTPATIENT_RECIPE", "EMR_OUTPATIENT_RECIPE_ITEM"]
TABLES = [(t, "b5") for t in B5] + [(t, "b6") for t in B6] + [(t, "b7") for t in B7]

W_START, W_END = "2026-01-01", "2026-10-26"
MONTH_EDGES = ["2026-01-01", "2026-02-01", "2026-03-01", "2026-04-01", "2026-05-01",
               "2026-06-01", "2026-07-01", "2026-08-01", "2026-09-01", "2026-10-01",
               "2026-10-26"]


def q(cur, sql, binds=None):
    cur.execute(sql, binds or {})
    return cur.fetchall()


ledger = {}
oracledb.init_oracle_client(lib_dir="/opt/oracle")

line = open("/etc/data-asset/credentials/sanjia_front_oracle_10_10_8_74.readonly").readline().strip()
u, _, p = line.partition(":")
tc = oracledb.connect(user=u, password=p, dsn="10.10.8.74:1521/orcl", tcp_connect_timeout=20)
tcur = tc.cursor()

line = open("/etc/data-asset/credentials/ods_8_216").readline().strip()
u, _, p = line.partition(":")
sc = oracledb.connect(user=u, password=p, dsn="10.10.8.216:1521/orcl", tcp_connect_timeout=20)
scur = sc.cursor()

for table, grp in TABLES:
    rec = {"group": grp, "view": "V_" + table}
    # 目标现量（8.74，快）
    try:
        tcur.execute(f"SELECT COUNT(*) FROM DBOPER.{table}")
        rec["target_total"] = tcur.fetchone()[0]
    except Exception as exc:  # noqa: BLE001
        rec["target_total"] = f"ERR:{type(exc).__name__}"
    # 源视图总量（60s 纪律）
    sc.call_timeout = 60000
    try:
        scur.execute(f"SELECT COUNT(*) FROM ODS.V_{table}")
        rec["source_total"] = scur.fetchone()[0]
    except Exception as exc:  # noqa: BLE001
        rec["source_total"] = f"TIMEOUT_OR_ERR:{type(exc).__name__}"
    # 逐月行数：先 GROUP BY 一次查
    try:
        scur.execute(
            f"SELECT TRUNC(DATETIME,'MM'), COUNT(*) FROM ODS.V_{table} "
            "WHERE DATETIME >= DATE'2026-01-01' AND DATETIME < DATE'2026-10-26' "
            "GROUP BY TRUNC(DATETIME,'MM') ORDER BY 1")
        months = {str(r[0])[:7]: r[1] for r in scur.fetchall()}
        rec["monthly"] = months
        rec["monthly_mode"] = "group_by"
    except Exception as exc:  # noqa: BLE001
        rec["monthly_mode"] = f"group_by_fail:{type(exc).__name__}"
        # 退化：逐月单查（各 60s）
        months = {}
        for i in range(10):
            a, b = MONTH_EDGES[i], MONTH_EDGES[i + 1]
            try:
                scur.execute(
                    f"SELECT COUNT(*) FROM ODS.V_{table} "
                    f"WHERE DATETIME >= DATE'{a}' AND DATETIME < DATE'{b}'")
                months[a[:7]] = scur.fetchone()[0]
            except Exception as exc2:  # noqa: BLE001
                months[a[:7]] = f"TIMEOUT_OR_ERR:{type(exc2).__name__}"
        rec["monthly"] = months
    rec["window_total"] = (
        sum(v for v in rec["monthly"].values() if isinstance(v, int))
        if isinstance(rec["monthly"], dict) else None)
    ledger[table] = rec
    print(table, json.dumps(rec, ensure_ascii=False), flush=True)

tc.close()
sc.close()
out = "/opt/data-asset/t1-stage/b9_gap_survey_20261027.json"
json.dump(ledger, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("SURVEY_DONE", out, flush=True)
try:
    print(json.dumps(ledger, ensure_ascii=False))
except Exception:  # noqa: BLE001
    traceback.print_exc()
