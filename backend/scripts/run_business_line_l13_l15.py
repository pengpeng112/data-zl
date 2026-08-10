"""Execute L13/L14/L15 on 8.83: review diffs, peripheral ODS collect, quality run + night job seed.

Requires: APP_SSH_PASSWORD for SSH. Source Oracle SELECT only.
"""
from __future__ import annotations

import os
import textwrap

import paramiko

HOST = "10.10.8.83"
PASSWORD = os.environ.get("APP_SSH_PASSWORD")
if not PASSWORD:
    raise SystemExit("Set APP_SSH_PASSWORD")

ROOT = r"F:\python\数据资产\backend"

WORK = textwrap.dedent(
    """\
    import json
    from datetime import datetime, timezone
    from app.core.db import SessionLocal
    from app.services.identity_review import build_his_master_review
    from app.services.peripheral_sources import ensure_peripheral_registry, collect_peripheral_metadata
    from app.api.v1.quality import run_quality_check_core, seed_rules
    from app.models.governance_ops import SchedulerJob
    from sqlalchemy import select, text

    out = {"started_at": datetime.now(timezone.utc).isoformat()}
    db = SessionLocal()
    try:
        # L13
        rev = build_his_master_review(db)
        db.commit()
        out["l13_review"] = rev

        # L14
        reg = ensure_peripheral_registry(db)
        out["l14_registry"] = reg
        col = collect_peripheral_metadata(db)
        out["l14_collect"] = col

        # L15 quality once
        seed_rules(db)
        q = run_quality_check_core(db, triggered_by="business_line_bootstrap")
        out["l15_quality_run"] = q

        # seed night job 02:00 Asia/Shanghai if missing
        existing = db.scalar(
            select(SchedulerJob).where(
                SchedulerJob.job_type == "quality_check",
                SchedulerJob.trigger_mode == "scheduled",
                SchedulerJob.schedule_cron == "0 2 * * *",
            )
        )
        if not existing:
            db.add(
                SchedulerJob(
                    job_type="quality_check",
                    source_code="platform",
                    trigger_mode="scheduled",
                    schedule_cron="0 2 * * *",
                    status="registered",
                    started_at=datetime.now(timezone.utc),
                    total_processed=0,
                    total_changes=0,
                    result_ref=json.dumps({"note": "L15 nightly quality"}, ensure_ascii=False),
                )
            )
            db.commit()
            out["l15_night_job"] = "created"
        else:
            out["l15_night_job"] = f"exists id={existing.id}"

        # summary counts
        out["counts"] = {
            "open_diffs": db.execute(text("SELECT COUNT(*) FROM asset.asset_identity_sync_diffs WHERE status='open'")).scalar(),
            "sources": db.execute(text("SELECT COUNT(*) FROM asset.asset_data_sources WHERE enabled")).scalar(),
            "systems": db.execute(text("SELECT COUNT(*) FROM asset.asset_systems")).scalar(),
            "quality_runs": db.execute(text("SELECT COUNT(*) FROM asset.asset_quality_check_runs")).scalar(),
            "quality_findings_open": db.execute(
                text("SELECT COUNT(*) FROM asset.asset_quality_findings WHERE status IN ('open','acknowledged')")
            ).scalar(),
        }
        out["status"] = "success"
    except Exception as ex:
        db.rollback()
        out["status"] = "error"
        out["error"] = f"{type(ex).__name__}:{str(ex)[:500]}"
    finally:
        db.close()
        out["finished_at"] = datetime.now(timezone.utc).isoformat()
        print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    """
)


def main() -> None:
    c = paramiko.SSHClient()
    c.load_system_host_keys()
    c.set_missing_host_key_policy(paramiko.RejectPolicy())
    c.connect(HOST, username="root", password=PASSWORD, timeout=15, allow_agent=False, look_for_keys=False)

    files = [
        ("app/services/identity_review.py", "/tmp/identity_review.py"),
        ("app/services/peripheral_sources.py", "/tmp/peripheral_sources.py"),
        ("app/api/v1/identity.py", "/tmp/identity.py"),
        ("app/api/v1/systems.py", "/tmp/systems.py"),
        ("app/api/v1/quality.py", "/tmp/quality.py"),
        ("app/main.py", "/tmp/main.py"),
    ]
    sftp = c.open_sftp()
    for rel, remote in files:
        sftp.put(f"{ROOT}/{rel}".replace("/", "\\") if False else os.path.join(ROOT, *rel.split("/")), remote)
    with sftp.file("/tmp/run_business_line.py", "w") as f:
        f.write(WORK)
    sftp.close()

    # ensure oracle + creds
    prep = (
        "bash /etc/data-asset/ensure_oracle_ro_runtime.sh 2>/dev/null || true; "
        "docker cp /tmp/identity_review.py data-asset-api:/app/app/services/identity_review.py; "
        "docker cp /tmp/peripheral_sources.py data-asset-api:/app/app/services/peripheral_sources.py; "
        "docker cp /tmp/identity.py data-asset-api:/app/app/api/v1/identity.py; "
        "docker cp /tmp/systems.py data-asset-api:/app/app/api/v1/systems.py; "
        "docker cp /tmp/quality.py data-asset-api:/app/app/api/v1/quality.py; "
        "docker cp /tmp/main.py data-asset-api:/app/app/main.py; "
        "docker cp /tmp/run_business_line.py data-asset-api:/tmp/run_business_line.py; "
        "docker exec -e PYTHONPATH=/app data-asset-api python /tmp/run_business_line.py"
    )
    _i, o, e = c.exec_command(prep, timeout=900)
    code = o.channel.recv_exit_status()
    print("exit", code)
    print(o.read().decode("utf-8", "replace")[:20000])
    err = e.read().decode("utf-8", "replace")
    if err:
        print("ERR", err[:3000])
    c.close()


if __name__ == "__main__":
    main()
