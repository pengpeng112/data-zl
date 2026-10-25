"""批5 EMR_MEDICAL_RECORD_INFO 失败批次清理执行（批1 A4 模式）：删 batches+attempts+隔离组+stage 目录，留行数。"""
import os
import shutil

from sqlalchemy import create_engine, text

BID = "DBOPER.EMR_MEDICAL_RECORD_INFO.T1.2026-10-25.66bc845f9852"
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
    left = s.execute(text(
        "SELECT COUNT(*) FROM asset.asset_reporting_batches "
        "WHERE canonical_table = 'EMR_MEDICAL_RECORD_INFO'")).fetchone()[0]
    print("remaining batches for table:", left)
eng.dispose()

p = f"/opt/data-asset/t1-stage/{BID}"
if os.path.isdir(p):
    files = sum(len(f) for _, _, f in os.walk(p))
    shutil.rmtree(p)
    print(f"stage dir removed: {p} (files={files})")
else:
    print("stage dir absent")
