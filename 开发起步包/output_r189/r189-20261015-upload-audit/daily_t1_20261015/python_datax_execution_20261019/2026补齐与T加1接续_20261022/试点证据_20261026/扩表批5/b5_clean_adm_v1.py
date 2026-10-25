"""批5 ADMISSION_RECORD v1 隔离批清理（批1 A4 模式）：删 batches+attempts+隔离组+stage 目录，留行数。"""
import os
import shutil

from sqlalchemy import create_engine, text

BID = "DBOPER.EMR_ADMISSION_RECORD.T1.2026-10-25.37e1efef1420"
eng = create_engine(os.environ["APP_DB_URL"])
with eng.begin() as s:
    n_att = s.execute(text(
        "DELETE FROM asset.asset_reporting_batch_attempts WHERE batch_id = :b"),
        {"b": BID}).rowcount
    n_qg = s.execute(text(
        "DELETE FROM asset.asset_reporting_quarantine_groups WHERE batch_id = :b"),
        {"b": BID}).rowcount
    n_bat = s.execute(text(
        "DELETE FROM asset.asset_reporting_batches WHERE batch_id = :b"),
        {"b": BID}).rowcount
    print(f"deleted: batches={n_bat} attempts={n_att} quarantine_groups={n_qg}")
eng.dispose()
p = f"/opt/data-asset/t1-stage/{BID}"
if os.path.isdir(p):
    shutil.rmtree(p)
    print("stage dir removed:", p)
else:
    print("stage dir absent")
