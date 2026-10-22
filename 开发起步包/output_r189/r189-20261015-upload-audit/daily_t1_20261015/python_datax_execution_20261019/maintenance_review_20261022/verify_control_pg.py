"""Regression against the explicitly disposable data_asset_test database.

Only UUID-owned synthetic batch/attempt rows are written and cleaned up.
No migrations, root TRUNCATE fixture, source or front-machine access.
"""
import os
import sys
import uuid
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path.cwd() / "backend"))
from app.services.reporting_pipeline.contracts import (
    BatchState, ContractViolation, FeedbackState, RowClassification,
)
from app.services.reporting_pipeline.pg_repository import SqlAlchemyControlRepository
from app.services.reporting_pipeline.production_runtime import build_manifest, business_window

url = make_url(os.environ["APP_TEST_DB_URL"])
assert url.database == "data_asset_test", "Only the disposable test database is allowed"
engine = create_engine(url)
with engine.connect() as connection:
    assert connection.execute(text("SELECT current_database()")).scalar_one() == "data_asset_test"

batch_id = "maintenance-regression-" + uuid.uuid4().hex
repo = SqlAlchemyControlRepository(sessionmaker(bind=engine))
try:
    repo.create_batch(batch_id, "EMR_MAINTENANCE_TEST", "2026-10-21")
    manifest = build_manifest(
        batch_id=batch_id, attempt_id="att001", task_id="EMR_MAINTENANCE_TEST",
        config_version="test", source_identity="synthetic",
        window=business_window("2026-10-21"),
        rows=RowClassification(source_read_rows=0, valid=0),
        total_bytes=0, payload_sha256="0" * 64,
    )
    repo.attach_attempt_manifest(batch_id, manifest)
    repo.select_manifest(batch_id)
    for state in (BatchState.CAPTURING, BatchState.CAPTURED, BatchState.VALIDATING,
                  BatchState.VALIDATED, BatchState.APPLY_PENDING, BatchState.APPLYING,
                  BatchState.APPLIED):
        repo.transition_batch(batch_id, state, reason="synthetic regression")
    try:
        repo.transition_batch(batch_id, BatchState.CAPTURING, reason="must reject rollback")
    except ContractViolation:
        pass
    else:
        raise AssertionError("Illegal state rollback was accepted")
    repo.transition_feedback(batch_id, FeedbackState.SUBMITTED, reason="synthetic")
    repo.transition_feedback(batch_id, FeedbackState.RECEIVED, reason="synthetic")
    reopened = SqlAlchemyControlRepository(sessionmaker(bind=engine)).get_batch(batch_id)
    assert reopened.state == BatchState.APPLIED
    assert reopened.feedback_state == FeedbackState.RECEIVED
    print("PASS: durable batch progression, rollback refusal, feedback progression, reopen")
finally:
    with engine.begin() as connection:
        for table in ("asset_reporting_batch_attempts", "asset_reporting_batches"):
            connection.execute(text(f"DELETE FROM asset.{table} WHERE batch_id=:batch_id"), {"batch_id": batch_id})
    engine.dispose()
