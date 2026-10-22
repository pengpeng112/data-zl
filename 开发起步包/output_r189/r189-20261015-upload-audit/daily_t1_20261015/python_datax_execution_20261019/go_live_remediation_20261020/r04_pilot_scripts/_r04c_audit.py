# -*- coding: utf-8 -*-
"""R04 step: platform audit row for the pilot apply (asset_govern_audit_logs)."""
from sqlalchemy import text

from app.core.db import SessionLocal

SQL = """
INSERT INTO asset.asset_govern_audit_logs
  (module, entity_type, entity_ref, action, before_data, after_data,
   operator, reason)
VALUES
  (:m, :et, :e, :a, CAST(:b AS jsonb), CAST(:f AS jsonb), :o, :r)
"""

with SessionLocal() as session:
    session.execute(text(SQL), {
        "m": "reporting_pipeline",
        "et": "oracle_target_table_window",
        "e": "DBOPER.EMR_ADMISSION_RECORD:2024-02",
        "a": "R189_R04_PILOT_MERGE",
        "b": '{"rows_202402": 4137, "source": "historical datax-web task"}',
        "f": ('{"rows_202402": 4137, "count_delta": 0, "keyset_equal": true, '
              '"sample_diffs": 0, "operation_id": "R189-R04-PILOT-001", '
              '"manifest_hash": "2e99fed521c1d7b1", '
              '"receipt_table": "DBOPER.ASSET_APPLY_RECEIPTS"}'),
        "o": "r189_t1_stage_to_dboper(executor#5,registered,disabled)|zcode-20261020-r04",
        "r": "用户批准R04试点装载(2026-10-20)：MERGE重放零新增+同事务凭据+重放拒绝已验证",
    })
    session.commit()
    row = session.execute(text(
        "SELECT id, module, action, operator FROM asset.asset_govern_audit_logs "
        "WHERE action='R189_R04_PILOT_MERGE' ORDER BY id DESC LIMIT 1")).mappings().one()
    print("AUDIT_ROW:", dict(row))
