"""批5 ADMISSION_RECORD 隔离组原因核查（只读）。"""
import os

from sqlalchemy import create_engine, text

BID = "DBOPER.EMR_ADMISSION_RECORD.T1.2026-10-25.37e1efef1420"
eng = create_engine(os.environ["APP_DB_URL"])
with eng.connect() as s:
    cols = [r[0] for r in s.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name='asset_reporting_quarantine_groups'"))]
    print("qg columns:", cols)
    rows = s.execute(text(
        "SELECT * FROM asset.asset_reporting_quarantine_groups WHERE batch_id = :b"),
        {"b": BID}).fetchall()
    print("groups:", len(rows))
    from collections import Counter
    reasons = Counter()
    for r in rows:
        d = dict(zip(cols, r))
        reasons[(d.get("reason"), d.get("error_code"))] += 1
    for (reason, code), n in reasons.most_common():
        print(f"  {n}x reason={str(reason)[:160]} code={code}")
    samp = s.execute(text(
        "SELECT group_key, reason, rows_quarantined FROM "
        "asset.asset_reporting_quarantine_groups WHERE batch_id = :b LIMIT 3"),
        {"b": BID}).fetchall()
    for r in samp:
        print("sample:", str(r)[:200])
eng.dispose()
