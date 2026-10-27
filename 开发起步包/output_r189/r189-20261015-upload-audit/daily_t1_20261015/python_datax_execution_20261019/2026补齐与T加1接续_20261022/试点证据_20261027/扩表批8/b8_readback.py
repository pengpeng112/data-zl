"""批8 目标只读回读（每表 apply 后）：SYSTEM_TIME 窗行数/总量/回执全量 batch_id 对账/批次状态/版本账/水位/隔离组。
运行（容器）：docker exec -i data-asset-api python - b8_readback.py <TABLE> <BATCH_ID> <APPLY_START> <APPLY_END>
  APPLY_START/APPLY_END = 本表 apply 实际时段（本地墙钟 YYYY-MM-DD HH24:MI:SS，前后各留 2 分钟余量）
批8 10 表 SYSTEM_TIME 全 TIMESTAMP(6)（生产实况复核 2026-10-27 实证），全用 TO_DATE 原版。
平台库走 APP_DB_URL；目标库走 8.74 只读凭据（凭据只进内存，零回显）。
"""
import os
import sys

TABLE, BATCH_ID, APPLY_START, APPLY_END = sys.argv[1:5]

import oracledb

oracledb.init_oracle_client(lib_dir="/opt/oracle")
line = open("/etc/data-asset/credentials/sanjia_front_oracle_10_10_8_74.readonly").readline().strip()
u, _, p = line.partition(":")
conn = oracledb.connect(user=u, password=p, dsn="10.10.8.74:1521/orcl", tcp_connect_timeout=20)
conn.call_timeout = 120000
cur = conn.cursor()

cur.execute(
    f"SELECT COUNT(*), COUNT(SYSTEM_TIME), MIN(SYSTEM_TIME), MAX(SYSTEM_TIME) "
    f"FROM DBOPER.{TABLE} WHERE SYSTEM_TIME >= TO_DATE(:s,'YYYY-MM-DD HH24:MI:SS') "
    f"AND SYSTEM_TIME < TO_DATE(:e,'YYYY-MM-DD HH24:MI:SS')",
    {"s": APPLY_START, "e": APPLY_END})
print("applywin_rows/system_time_nonnull/min/max:", cur.fetchone())

cur.execute(f"SELECT COUNT(*) FROM DBOPER.{TABLE}")
print("table_total_rows:", cur.fetchone()[0])

cur.execute("SELECT OPERATION_ID, BATCH_ID, MANIFEST_HASH, TARGET_OBJECT, SCOPE_SUMMARY, "
            "ROWS_AFFECTED, SYSTEM_TIME, COMMITTED_AT, CREATED_AT "
            "FROM DBOPER.ASSET_T1_RECEIPTS WHERE BATCH_ID = :b", {"b": BATCH_ID})
receipts = cur.fetchall()
print("receipt_columns: ['OPERATION_ID', 'BATCH_ID', 'MANIFEST_HASH', 'TARGET_OBJECT', "
      "'SCOPE_SUMMARY', 'ROWS_AFFECTED', 'SYSTEM_TIME', 'COMMITTED_AT', 'CREATED_AT']")
for r in receipts:
    print("receipt:", r)
cur.execute("SELECT COUNT(*) FROM DBOPER.ASSET_T1_RECEIPTS")
print("receipt_total:", cur.fetchone()[0])
op_ids = [r[0] for r in receipts]
conn.close()

from sqlalchemy import create_engine, text

eng = create_engine(os.environ["APP_DB_URL"])
with eng.connect() as sess:
    rows = sess.execute(text(
        "SELECT batch_id, state FROM asset.asset_reporting_batches WHERE batch_id = :b"
    ), {"b": BATCH_ID}).fetchall()
    print("batch_state:", rows)
    n_ver = 0
    for op in op_ids:
        n_ver += sess.execute(text(
            "SELECT COUNT(*) FROM asset.asset_reporting_version_evidence "
            "WHERE canonical_table = :t AND applied_operation_id = :op"
        ), {"t": TABLE, "op": op}).fetchone()[0]
    print("version_evidence:", n_ver)
    wm = sess.execute(text(
        "SELECT capture_h, apply_cursor, delivery_cursor, continuous_through "
        "FROM asset.asset_reporting_watermarks WHERE canonical_table = :t"
    ), {"t": TABLE}).fetchall()
    print("watermarks(capture_h/apply_cursor/delivery_cursor/continuous_through):", wm)
    qg = sess.execute(text(
        "SELECT group_key, reason, error_code, rows_quarantined, state "
        "FROM asset.asset_reporting_quarantine_groups "
        "WHERE canonical_table = :t AND created_at >= NOW() - INTERVAL '1 day'"
    ), {"t": TABLE}).fetchall()
    print("quarantine_groups(last_1d):", qg)
eng.dispose()
print("== readback done:", TABLE, "==")
