"""Read-only infrastructure inventory. No credentials or patient data output."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

report = {"verified_at": datetime.now(timezone.utc).isoformat(), "container_cwd": str(Path.cwd()), "files": {}}
for relative in (
    "app/services/reporting_pipeline/production_runtime.py",
    "app/services/reporting_pipeline/runtime.py",
    "scripts/reporting_ctl.py",
):
    path = Path(relative)
    report["files"][relative] = {
        "exists": path.is_file(),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None,
    }
try:
    from app.core.db import SessionLocal
    from sqlalchemy import text
    with SessionLocal() as session:
        session.execute(text("SET LOCAL statement_timeout = '10000ms'"))
        report["reporting_tables"] = session.execute(text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema='asset' AND table_name LIKE 'asset_reporting%' ORDER BY table_name"
        )).scalars().all()
        report["scheduler_columns"] = session.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema='asset' AND table_name='asset_scheduler_jobs' ORDER BY ordinal_position"
        )).scalars().all()
        report["reporting_scheduler_summary"] = [dict(row) for row in session.execute(text(
            "SELECT job_type,status,COUNT(*) AS records,MAX(started_at)::text AS last_started_at "
            "FROM asset.asset_scheduler_jobs WHERE lower(job_type) LIKE '%report%' "
            "OR lower(job_type) LIKE '%t1%' OR lower(job_type) LIKE '%189%' "
            "GROUP BY job_type,status ORDER BY job_type,status"
        )).mappings()]
        report["alembic_version"] = session.execute(text(
            "SELECT version_num FROM alembic_version"
        )).scalars().all()
except Exception as exc:
    report["inventory_error_class"] = type(exc).__name__
print(json.dumps(report, ensure_ascii=True, indent=2))
