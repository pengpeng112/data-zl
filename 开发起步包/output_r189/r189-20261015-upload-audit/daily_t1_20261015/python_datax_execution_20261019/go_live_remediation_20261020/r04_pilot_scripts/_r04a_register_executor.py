# -*- coding: utf-8 -*-
"""R04 step A: register pilot executor in platform asset schema (8.83).

User-approved 2026-10-20. Idempotent: skip if executor_code exists.
enabled stays FALSE (record-keeping; enablement is a separate approval).
"""
from sqlalchemy import text

from app.core.db import SessionLocal

SQL = """
INSERT INTO asset.asset_action_executors (
  executor_code, executor_name_cn, execution_mode, tool_code,
  sql_or_endpoint_ref, target_system_code, target_source_code,
  risk_level, require_approval, require_second_confirm, enabled, description
) VALUES (
  'r189_t1_stage_to_dboper',
  '189 T+1 暂存到前置机正式表装载',
  'controlled_sql',
  'reporting_pipeline',
  'backend/app/services/reporting_pipeline',
  'qianzhiji_874',
  'dboper_orcl',
  'high',
  TRUE, TRUE, FALSE,
  'R189-T1 R04 试点：EMR_ADMISSION_RECORD 2024-02 窗 INSERT+同事务凭据'
)
"""

with SessionLocal() as session:
    exists = session.execute(
        text("SELECT id FROM asset.asset_action_executors "
             "WHERE executor_code = 'r189_t1_stage_to_dboper'")
    ).scalar_one_or_none()
    if exists is not None:
        print("ALREADY_REGISTERED id=", exists)
    else:
        session.execute(text(SQL))
        session.commit()
        row = session.execute(
            text("SELECT id, executor_code, risk_level, require_approval, enabled "
                 "FROM asset.asset_action_executors "
                 "WHERE executor_code = 'r189_t1_stage_to_dboper'")
        ).mappings().one()
        print("REGISTERED", dict(row))
