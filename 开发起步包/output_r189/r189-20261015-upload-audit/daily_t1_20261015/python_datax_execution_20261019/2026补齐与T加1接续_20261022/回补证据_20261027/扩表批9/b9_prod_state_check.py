# -*- coding: utf-8 -*-
"""批9 生产实况复核（只读）：平台库 head/执行器/水位/在途批次/隔离组 +
目标库回执账/25表在册/SYSTEM_TIME 列型 + 三对配置卷指纹。
运行：ssh 8.83 "docker exec -i data-asset-api python -" < b9_prod_state_check.py
"""
import json
import os

B5 = ["EMR_ADMISSION_DIAGNOSIS", "EMR_DEATH_RECORD", "EMR_ICH_ALLERGIES",
      "EMR_DISCHARGE_RECORD", "EMR_OUTPATIENT_RECORD", "EMR_OUTPATIENT_REGISTER"]
B6 = ["EMR_INFOR_TRANS_BLOOD", "EMR_HOS_CHANGE_MAJOR_RECORD", "EMR_ANES_RECORD_BLOOD",
      "EMR_INFOR_CRITICALLY_ILL", "EMR_HOS_POSTOPER_RECORD", "EMR_BOFORE_OPERA_RECORD",
      "EMR_ANESTHESIA_RECORD", "EMR_IN_FEE_INFO_MAIN", "EMR_HOS_CONSUL_RECORD",
      "EMR_DOC_ORDER_CHECK"]
B7 = ["EMR_REFERRAL_HOS_RECORD", "EMR_HOS_DIFFIC_CASE_DISCUSS", "EMR_HOS_SUCCESSION_RECORD",
      "EMR_OPERATION_NURSING", "EMR_HOS_PREOP_DISCUSS", "EMR_AFTER_OPERA_RECORD",
      "EMR_INFOR_ANESTHESIA", "EMR_OUTPATIENT_RECIPE", "EMR_OUTPATIENT_RECIPE_ITEM"]
TABLES = B5 + B6 + B7
PH = ("'", ",".join(TABLES), "'")

EXPECTED_FP = {
    "freeze_batch5_v3.json": "b20cd9d7c57374fe2d8affd3a89008dbd11da0b28dd55650e6b90a66154432a5",
    "freeze_batch6_v1.json": "776a394e7ab68317acbec45924fbe48ec3c4f6667d8b56d902acbe23d8f69900",
    "freeze_batch7_v5.json": "b953b17e11241e6d8c2711ba54ee95e721109e7c7045000ec068c1cd64f42e6f",
}

print("== 配置卷指纹 ==")
for fn, want in EXPECTED_FP.items():
    p = f"/opt/data-asset/t1-config/{fn}"
    try:
        fp = json.load(open(p, encoding="utf-8")).get("config_fingerprint")
        print(f"{fn}: {str(fp)[:16]} match={fp == want}")
    except Exception as exc:  # noqa: BLE001
        print(f"{fn}: READ_FAIL {exc}")
for fn in ("bindings_batch5.json", "bindings_batch6.json", "bindings_batch7.json"):
    p = f"/opt/data-asset/t1-config/{fn}"
    try:
        doc = json.load(open(p, encoding="utf-8"))
        acts = doc.get("actions") or doc.get("bindings") or {}
        print(f"{fn}: actions={len(acts)}")
    except Exception as exc:  # noqa: BLE001
        print(f"{fn}: READ_FAIL {exc}")

from sqlalchemy import create_engine, text  # noqa: E402

eng = create_engine(os.environ["APP_DB_URL"])
with eng.connect() as s:
    print("alembic head:", s.execute(
        text("SELECT version_num FROM alembic_version")).scalar())
    print("executors:", s.execute(text(
        "SELECT executor_code, enabled FROM asset.asset_action_executors"
    )).fetchall())
    rows = s.execute(text(
        "SELECT canonical_table, capture_h, apply_cursor, continuous_through "
        "FROM asset.asset_reporting_watermarks WHERE canonical_table IN ("
        + ",".join(f"'{t}'" for t in TABLES) + ") ORDER BY canonical_table")).fetchall()
    print("== 水位（25 表）==")
    for r in rows:
        print(" ", r[0], "capture_h=", r[1], "apply_cursor=", r[2],
              "continuous_through=", r[3])
    print("watermark_rows:", len(rows))
    rows = s.execute(text(
        "SELECT canonical_table, batch_id, state, business_day FROM "
        "asset.asset_reporting_batches WHERE canonical_table IN ("
        + ",".join(f"'{t}'" for t in TABLES) + ") "
        "AND state NOT IN ('RECONCILED','SUPERSEDED') ORDER BY canonical_table"
    )).fetchall()
    print("== 在途批次（非终态）==", len(rows))
    for r in rows:
        print(" ", r)
    rows = s.execute(text(
        "SELECT canonical_table, group_id, reason, status FROM "
        "asset.asset_reporting_quarantine_groups WHERE canonical_table IN ("
        + ",".join(f"'{t}'" for t in TABLES) + ") "
        "AND status='OPEN' ORDER BY canonical_table")).fetchall()
    print("== OPEN 隔离组 ==", len(rows))
    for r in rows:
        print(" ", r)
    rows = s.execute(text(
        "SELECT canonical_table, COUNT(*) FROM asset.asset_reporting_month_coverage "
        "WHERE canonical_table IN ("
        + ",".join(f"'{t}'" for t in TABLES) + ") GROUP BY canonical_table "
        "ORDER BY canonical_table")).fetchall()
    print("== 月覆盖账现有行 ==", rows)
eng.dispose()

import oracledb  # noqa: E402

oracledb.init_oracle_client(lib_dir="/opt/oracle")
line = open("/etc/data-asset/credentials/sanjia_front_oracle_10_10_8_74.readonly").readline().strip()
u, _, p = line.partition(":")
tconn = oracledb.connect(user=u, password=p, dsn="10.10.8.74:1521/orcl", tcp_connect_timeout=20)
tcur = tconn.cursor()
tcur.execute("SELECT COUNT(*) FROM DBOPER.ASSET_T1_RECEIPTS")
print("receipt_total(DBOPER):", tcur.fetchone()[0])
tcur.execute(
    "SELECT table_name FROM all_tables WHERE owner='DBOPER' AND table_name IN ("
    + ",".join(f"'{t}'" for t in TABLES) + ") ORDER BY table_name")
present = [r[0] for r in tcur.fetchall()]
print("target tables present:", len(present), "missing:",
      sorted(set(TABLES) - set(present)))
tcur.execute(
    "SELECT table_name, data_type FROM all_tab_columns WHERE owner='DBOPER' "
    "AND column_name='SYSTEM_TIME' AND table_name IN ("
    + ",".join(f"'{t}'" for t in TABLES) + ") ORDER BY table_name")
print("SYSTEM_TIME VARCHAR2 tables:",
      [r[0] for r in tcur.fetchall() if r[1] != "TIMESTAMP(6)" and "TIMESTAMP" not in r[1]])
tconn.close()
print("PROD_CHECK_DONE")
