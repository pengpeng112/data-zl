"""批5 ADMISSION_RECORD apply 后隔离组与批次终态（只读）。"""
import os

from sqlalchemy import create_engine, text

BID = "DBOPER.EMR_ADMISSION_RECORD.T1.2026-10-25.37e1efef1420"
eng = create_engine(os.environ["APP_DB_URL"])
with eng.connect() as s:
    rows = s.execute(text(
        "SELECT group_key, reason, error_code, rows_quarantined, state, detail_ref "
        "FROM asset.asset_reporting_quarantine_groups WHERE batch_id = :b"), {"b": BID}).fetchall()
    for r in rows:
        print("qg:", str(r)[:400])
    st = s.execute(text(
        "SELECT state, feedback_state FROM asset.asset_reporting_batches WHERE batch_id=:b"),
        {"b": BID}).fetchone()
    print("batch state:", st)
eng.dispose()
