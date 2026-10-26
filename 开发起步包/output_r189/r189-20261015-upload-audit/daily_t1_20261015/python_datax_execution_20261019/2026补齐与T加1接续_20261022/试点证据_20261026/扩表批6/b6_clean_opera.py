"""批6 EMR_OPERA_RECORD 失败批次检查（批1 A4/批5 同款：查 batches/attempts/隔离组/stage 目录，留行数不删记录）。"""
import os
import subprocess

from sqlalchemy import create_engine, text

eng = create_engine(os.environ["APP_DB_URL"])
with eng.connect() as s:
    rows = s.execute(text(
        "SELECT batch_id, canonical_table, state, business_day FROM "
        "asset.asset_reporting_batches WHERE canonical_table = 'EMR_OPERA_RECORD'"
    )).fetchall()
    print("batches:", rows)
    for r in rows:
        bid = r[0]
        att = s.execute(text(
            "SELECT * FROM asset.asset_reporting_batch_attempts "
            "WHERE batch_id = :b"), {"b": bid}).fetchall()
        print(f"  {bid}: attempts={len(att)}")
        for a in att:
            print("   attempt:", tuple(a)[:8])
        n_qg = s.execute(text(
            "SELECT COUNT(*) FROM asset.asset_reporting_quarantine_groups "
            "WHERE batch_id = :b"), {"b": bid}).fetchone()[0]
        print(f"  quarantine_groups={n_qg}")
    s.commit()
eng.dispose()

out = subprocess.run(
    ["sh", "-c", "ls /opt/data-asset/t1-stage/ 2>/dev/null | grep -i opera || true"],
    capture_output=True, text=True)
print("stage dirs:", out.stdout.strip() or "(none)")
