"""批5 ADMISSION_RECORD 质量隔离详情定位（只读）。"""
import json
import os

from sqlalchemy import create_engine, text

BID = "DBOPER.EMR_ADMISSION_RECORD.T1.2026-10-25.37e1efef1420"
eng = create_engine(os.environ["APP_DB_URL"])
with eng.connect() as s:
    tabs = [r[0] for r in s.execute(text(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema='asset' AND (table_name LIKE '%quarantine%' "
        "OR table_name LIKE '%quality%')"))]
    print("quality-ish tables:", tabs)
    for t in tabs:
        cols = [r[0] for r in s.execute(text(
            f"SELECT column_name FROM information_schema.columns "
            f"WHERE table_schema='asset' AND table_name='{t}'"))]
        n = s.execute(text(f"SELECT COUNT(*) FROM asset.{t} WHERE batch_id='{BID}'")).fetchone()[0] if 'batch_id' in cols else '-'
        print(f"  {t}: rows_for_batch={n} cols={cols}")
    st = s.execute(text(
        "SELECT state FROM asset.asset_reporting_batches WHERE batch_id=:b"),
        {"b": BID}).fetchone()
    print("batch state:", st)
eng.dispose()

import subprocess

out = subprocess.run(["sh", "-c",
    "ls /opt/data-asset/t1-stage/%s/ 2>/dev/null" % BID],
    capture_output=True, text=True)
print("stage dir:", out.stdout.strip() or "(none)")
for f in out.stdout.split():
    p = f"/opt/data-asset/t1-stage/{BID}/{f}"
    try:
        data = json.loads(open(p, encoding="utf-8").read())
        if isinstance(data, dict) and ("issues" in data or "quality" in data):
            print(f"-- {f} keys:", list(data.keys())[:12])
            iss = data.get("issues") or (data.get("quality") or {}).get("issues")
            if iss:
                from collections import Counter
                c = Counter(str(i)[:120] for i in iss)
                for k, n in c.most_common(8):
                    print(f"   {n}x {k}")
    except Exception as exc:
        print(f, "read err", exc)
