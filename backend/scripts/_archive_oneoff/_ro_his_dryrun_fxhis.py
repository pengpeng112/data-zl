"""Re-run HIS identity dry-run with FXHIS.SYS_EMPLOYEE primary."""
from __future__ import annotations

import os
import textwrap

import paramiko

HOST = "10.10.8.83"
PASSWORD = os.environ.get("APP_SSH_PASSWORD", "P@ssw0rd@123")
ROOT = r"F:\python\数据资产\backend"

REMOTE = textwrap.dedent(
    """\
    import json
    from datetime import datetime, timezone
    from pathlib import Path

    from app.core.db import SessionLocal
    from app.core.config import settings
    from app.services.his_identity_sync import sync_his_identity, EMPLOYEE_TABLE
    from sqlalchemy import text

    his_user, his_pwd = Path("/etc/data-asset/credentials/his_source_10_10_10_15").read_text().strip().split(":", 1)
    settings.his_source_host = "10.10.10.15"
    settings.his_source_port = 1521
    settings.his_source_service = "his"
    settings.his_source_user = his_user
    settings.his_source_password = his_pwd
    settings.his_source_connection_mode = "direct"
    settings.his_source_oracle_client_lib = "/opt/oracle"

    db = SessionLocal()
    try:
        dry = sync_his_identity(db, operator="ro_probe", dry_run=True, max_rows=20000, write_audit=False)
        db.rollback()
        counts = {}
        for t in [
            "asset_identity_persons",
            "asset_identity_departments",
            "asset_identity_person_sources",
            "asset_identity_person_departments",
        ]:
            counts[t] = db.execute(text(f"SELECT COUNT(*) FROM asset.{t}")).scalar()
        out = {
            "employee_table": EMPLOYEE_TABLE,
            "dry_run": dry,
            "identity_counts": counts,
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }
        print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    finally:
        db.close()
    """
)


def main() -> None:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username="root", password=PASSWORD, timeout=15, allow_agent=False, look_for_keys=False)
    sftp = c.open_sftp()
    sftp.put(os.path.join(ROOT, r"app\services\his_identity_sync.py"), "/tmp/his_identity_sync.py")
    with sftp.file("/tmp/ro_his_dryrun_fxhis.py", "w") as f:
        f.write(REMOTE)
    sftp.close()
    cmd = (
        "bash /etc/data-asset/ensure_oracle_ro_runtime.sh >/dev/null; "
        "docker cp /tmp/his_identity_sync.py data-asset-api:/app/app/services/his_identity_sync.py; "
        "docker cp /tmp/ro_his_dryrun_fxhis.py data-asset-api:/tmp/ro_his_dryrun_fxhis.py; "
        "docker exec -e PYTHONPATH=/app data-asset-api python /tmp/ro_his_dryrun_fxhis.py"
    )
    _i, o, e = c.exec_command(cmd, timeout=180)
    print(o.read().decode("utf-8", "replace")[:12000])
    err = e.read().decode("utf-8", "replace")
    if err:
        print("ERR", err[:2000])
    c.close()


if __name__ == "__main__":
    main()
