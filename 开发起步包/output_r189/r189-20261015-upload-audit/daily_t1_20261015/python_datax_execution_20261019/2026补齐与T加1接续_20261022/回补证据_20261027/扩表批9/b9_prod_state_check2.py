# -*- coding: utf-8 -*-
"""批9 生产实况复核补段（只读）：隔离组/月覆盖账/回执账/25表在册/SYSTEM_TIME 列型。"""
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
INLIST = ",".join(f"'{t}'" for t in TABLES)

# bindings 结构复核（批9 用 pairs: freeze+bindings 按批）
for fn in ("bindings_batch5.json", "bindings_batch6.json", "bindings_batch7.json"):
    doc = json.load(open(f"/opt/data-asset/t1-config/{fn}", encoding="utf-8"))
    print(f"{fn}: top_keys={sorted(doc.keys())[:8]}")

from sqlalchemy import create_engine, text  # noqa: E402

eng = create_engine(os.environ["APP_DB_URL"])
with eng.connect() as s:
    rows = s.execute(text(
        "SELECT canonical_table, group_key, reason, state FROM "
        f"asset.asset_reporting_quarantine_groups WHERE canonical_table IN ({INLIST}) "
        "AND state='OPEN' ORDER BY canonical_table")).fetchall()
    print("== OPEN 隔离组 ==", len(rows))
    for r in rows:
        print(" ", r)
    rows = s.execute(text(
        "SELECT canonical_table, COUNT(*) FROM asset.asset_reporting_month_coverage "
        f"WHERE canonical_table IN ({INLIST}) GROUP BY canonical_table "
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
    + INLIST + ") ORDER BY table_name")
present = [r[0] for r in tcur.fetchall()]
print("target tables present:", len(present), "missing:", sorted(set(TABLES) - set(present)))
tcur.execute(
    "SELECT table_name, data_type FROM all_tab_columns WHERE owner='DBOPER' "
    "AND column_name='SYSTEM_TIME' AND table_name IN ("
    + INLIST + ") ORDER BY table_name")
types = tcur.fetchall()
print("SYSTEM_TIME non-TIMESTAMP tables:",
      [(r[0], r[1]) for r in types if "TIMESTAMP" not in r[1]])
tconn.close()
print("PROD_CHECK2_DONE")
