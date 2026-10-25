"""批5 ADMISSION_RECORD v2 capture 报错详情（只读）。"""
import os

from sqlalchemy import create_engine, text

BID = "DBOPER.EMR_ADMISSION_RECORD.T1.2026-10-25.37e1efef1420"
eng = create_engine(os.environ["APP_DB_URL"])
with eng.connect() as s:
    cols = [r[0] for r in s.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema='asset' AND table_name='asset_reporting_batch_attempts'"))]
    print("attempt cols:", cols)
    rows = s.execute(text(
        "SELECT * FROM asset.asset_reporting_batch_attempts WHERE batch_id=:b "
        "ORDER BY created_at DESC LIMIT 2"), {"b": BID}).fetchall()
    for r in rows:
        d = dict(zip(cols, r))
        for k, v in d.items():
            if v not in (None, "") and ("error" in k or "state" in k or "note" in k or "detail" in k):
                print(f"  {k} = {str(v)[:400]}")
    bcols = [r[0] for r in s.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema='asset' AND table_name='asset_reporting_batches'"))]
    brow = s.execute(text(
        "SELECT * FROM asset.asset_reporting_batches WHERE batch_id=:b"), {"b": BID}).fetchone()
    if brow:
        d = dict(zip(bcols, brow))
        for k, v in d.items():
            if v not in (None, "") and ("error" in k or "state" in k or "note" in k):
                print(f"  batch.{k} = {str(v)[:400]}")
eng.dispose()
