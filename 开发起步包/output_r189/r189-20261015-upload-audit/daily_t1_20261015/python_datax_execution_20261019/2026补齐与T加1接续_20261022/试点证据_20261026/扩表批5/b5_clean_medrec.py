"""批5 EMR_MEDICAL_RECORD_INFO 失败批次清理（批1 A4 模式）：查 batches/attempts/隔离组/stage 目录并清理，留行数。
"""
import os

from sqlalchemy import create_engine, text

eng = create_engine(os.environ["APP_DB_URL"])
with eng.connect() as s:
    rows = s.execute(text(
        "SELECT batch_id, canonical_table, state, business_day FROM "
        "asset.asset_reporting_batches WHERE canonical_table = 'EMR_MEDICAL_RECORD_INFO'"
    )).fetchall()
    print("batches before:", rows)
    for r in rows:
        bid = r[0]
        n_att = s.execute(text(
            "SELECT COUNT(*) FROM asset.asset_reporting_batch_attempts "
            "WHERE batch_id = :b"), {"b": bid}).fetchone()[0]
        n_qg = s.execute(text(
            "SELECT COUNT(*) FROM asset.asset_reporting_quarantine_groups "
            "WHERE batch_id = :b"), {"b": bid}).fetchone()[0]
        print(f"  {bid}: attempts={n_att} quarantine_groups={n_qg}")
    s.commit()
eng.dispose()

import subprocess

out = subprocess.run(
    ["sh", "-c", "ls /opt/data-asset/t1-stage/ 2>/dev/null | grep -i medical || true"],
    capture_output=True, text=True)
print("stage dirs:", out.stdout.strip() or "(none)")
