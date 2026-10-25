"""批5 ADMISSION_RECORD v3 隔离组原因（只读，apply 前）。"""
import os

from sqlalchemy import create_engine, text

BID = "DBOPER.EMR_ADMISSION_RECORD.T1.2026-10-25.37e1efef1420"
eng = create_engine(os.environ["APP_DB_URL"])
with eng.connect() as s:
    rows = s.execute(text(
        "SELECT group_key, reason, error_code, rows_quarantined, state FROM "
        "asset.asset_reporting_quarantine_groups WHERE batch_id = :b"), {"b": BID}).fetchall()
    print("groups:", rows if rows else "(空——组在 apply 时落账)")
    st = s.execute(text(
        "SELECT state FROM asset.asset_reporting_batches WHERE batch_id=:b"),
        {"b": BID}).fetchone()
    print("batch state:", st)
eng.dispose()
