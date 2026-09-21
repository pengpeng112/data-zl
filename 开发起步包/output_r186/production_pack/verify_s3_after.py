"""S3 post-deploy verification (read-only, in-container)."""
from sqlalchemy import text

from app.core.config import settings
from app.core.db import SessionLocal

db = SessionLocal()
print("HEAD:", db.execute(text("SELECT version_num FROM public.alembic_version")).scalar())
print("RUN_MODE:", getattr(settings, "identity_run_mode", None))
print("BUILD_ID:", getattr(settings, "build_id", None))
print("SYNC_ENABLED(container):", getattr(settings, "identity_sync_enabled", None))
print("SCHEDULER_PROVIDER:", getattr(settings, "identity_scheduler_provider", None))
print("NIGHTLY_ENABLED:", getattr(settings, "identity_nightly_enabled", None))
print("CLOCK_SAMPLING:", getattr(settings, "identity_clock_sampling_enabled", None))
print("PHASE_D_SET:", bool(getattr(settings, "identity_phase_d_approval_version", "")))
execs = db.execute(text(
    "SELECT executor_code, enabled, target_source_code FROM asset.asset_action_executors "
    "WHERE executor_code LIKE '%ACCOUNT%' ORDER BY 1")).fetchall()
print("EXECUTORS:", [(r[0], bool(r[1]), r[2]) for r in execs])
tables = db.execute(text(
    "SELECT tablename FROM pg_tables WHERE schemaname='asset' AND ("
    "tablename LIKE 'asset_source_purpose%' OR tablename LIKE 'asset_identity_action%' "
    "OR tablename LIKE 'asset_identity_window%' OR tablename LIKE 'asset_identity_account_state%') "
    "ORDER BY 1")).fetchall()
print("186_TABLES:", [t[0] for t in tables])
perm = db.execute(text(
    "SELECT role_code, resource, action FROM asset.asset_role_permissions "
    "WHERE (resource='identity.sync_diff' AND action='view') "
    "OR (resource='govern.executor' AND action='manage')")).fetchall()
print("PERM_GRANTS:", perm)
col = db.execute(text(
    "SELECT COUNT(*) FROM information_schema.columns WHERE table_schema='asset' "
    "AND table_name='asset_identity_account_state_attempts' AND column_name='origin_disable_attempt_id'")).scalar()
print("ORIGIN_COL:", col)
db.close()
