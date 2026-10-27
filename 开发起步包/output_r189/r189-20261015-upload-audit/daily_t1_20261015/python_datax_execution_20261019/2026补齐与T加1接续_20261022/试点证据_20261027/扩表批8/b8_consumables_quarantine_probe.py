"""表3 CONSUMABLES 隔离组核因（只读）：asset_reporting_batches/attempts + quarantine_groups 明细。
运行：ssh -F .ssh/config_ai data-asset-83 "docker exec -i data-asset-api python -" < b8_consumables_quarantine_probe.py
"""
import json
import os

from sqlalchemy import create_engine, text

eng = create_engine(os.environ["APP_DB_URL"])
BID = "DBOPER.EMR_CONSUMABLES.T1.2026-10-26.d1e64a5b6a3b"
with eng.connect() as s:
    print("== batch ==")
    cols = [c[0] for c in s.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema='asset' AND table_name='asset_reporting_batches' ORDER BY ordinal_position")).fetchall()]
    row = s.execute(text(
        "SELECT * FROM asset.asset_reporting_batches WHERE batch_id=:b"), {"b": BID}).fetchone()
    d = dict(zip(cols, row)) if row else None
    keep = {k: d[k] for k in d if k in ("batch_id","state","business_day","mode","table_name","captured_rows","valid_rows","quarantined_rows","applied_rows","created_at","updated_at")} if d else {}
    print(json.dumps(keep, ensure_ascii=False, default=str))
    print("== quarantine groups（全部规则分布+样例前10）==")
    qcols = [c[0] for c in s.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema='asset' AND table_name='asset_reporting_quarantine_groups' ORDER BY ordinal_position")).fetchall()]
    print("cols:", qcols)
    allq = s.execute(text(
        "SELECT * FROM asset.asset_reporting_quarantine_groups WHERE batch_id=:b"), {"b": BID}).fetchall()
    print("total groups:", len(allq))
    from collections import Counter
    def getf(r, name):
        return dict(zip(qcols, r)).get(name)
    print("rule distribution:", Counter(str(getf(r, "rule")) for r in allq))
    print("state distribution:", Counter(str(getf(r, "state")) for r in allq))
    for r in allq[:10]:
        dd = dict(zip(qcols, r))
        dd.pop("payload", None)
        dd.pop("row_ids", None)
        print(json.dumps(dd, ensure_ascii=False, default=str)[:400])
eng.dispose()
