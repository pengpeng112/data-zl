"""批8 表9 EMR_INFOR_OPERATION 失败批次清理（批1/批5 A4 模式）：
先查（batches/attempts/quarantine/stage），再删 batches+attempts+隔离组+stage 目录，留行数。
工单 T-B08-2：视图重 COUNT 快（119 行）capture 慢（FETCH_TIMEOUT），源端优化后同批号补跑。
"""
import os
import shutil

from sqlalchemy import create_engine, text

BID = "DBOPER.EMR_INFOR_OPERATION.T1.2026-10-26.b87fa22f6b72"
eng = create_engine(os.environ["APP_DB_URL"])
with eng.connect() as s:
    rows = s.execute(text(
        "SELECT batch_id, canonical_table, state FROM asset.asset_reporting_batches "
        "WHERE canonical_table = 'EMR_INFOR_OPERATION'")).fetchall()
    print("batches before:", rows)
    n_att = s.execute(text(
        "SELECT COUNT(*) FROM asset.asset_reporting_batch_attempts WHERE batch_id = :b"),
        {"b": BID}).fetchone()[0]
    n_qg = s.execute(text(
        "SELECT COUNT(*) FROM asset.asset_reporting_quarantine_groups WHERE batch_id = :b"),
        {"b": BID}).fetchone()[0]
    print(f"  {BID}: attempts={n_att} quarantine_groups={n_qg}")
eng.dispose()

import subprocess
print("stage dirs:", subprocess.run(
    ["sh", "-c", f"ls -d /opt/data-asset/t1-stage/{BID} 2>/dev/null || echo absent"],
    capture_output=True, text=True).stdout.strip())

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
        "WHERE canonical_table = 'EMR_INFOR_OPERATION'")).fetchone()[0]
    print("remaining batches for table:", left)
eng.dispose()

p = f"/opt/data-asset/t1-stage/{BID}"
if os.path.isdir(p):
    files = sum(len(f) for _, _, f in os.walk(p))
    shutil.rmtree(p)
    print(f"stage dir removed: {p} (files={files})")
else:
    print("stage dir absent (capture 超时未落盘)")
