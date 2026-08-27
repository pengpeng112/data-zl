"""Continue L10 metadata collect + L11 HIS identity dry-run (source SELECT only).

- Ensures Instant Client 19 symlink + credentials inside container
- Collects live metadata with schema filters (platform PG write only)
- Runs HIS identity sync dry_run=True (no platform identity upserts)
"""
from __future__ import annotations

import json
import os
import textwrap

import paramiko

HOST = "10.10.8.83"
PASSWORD = os.environ.get("APP_SSH_PASSWORD", "P@ssw0rd@123")


def run(c, cmd, timeout=600):
    _i, o, e = c.exec_command(cmd, timeout=timeout)
    code = o.channel.recv_exit_status()
    return code, o.read().decode("utf-8", "replace"), e.read().decode("utf-8", "replace")


PREP_SH = r"""#!/bin/bash
set -e
# host credentials already present
mkdir -p /etc/data-asset/credentials
chmod 700 /etc/data-asset/credentials
# durable init helper for future restarts
cat > /etc/data-asset/ensure_oracle_ro_runtime.sh <<'EOS'
#!/bin/bash
set -e
CID=$(docker ps -q -f name=^/data-asset-api$ || true)
if [ -z "$CID" ]; then
  echo "data-asset-api not running"
  exit 1
fi
docker exec "$CID" bash -lc 'ln -sfn libclntsh.so.19.1 /opt/oracle/libclntsh.so; ln -sfn libocci.so.19.1 /opt/oracle/libocci.so'
docker exec "$CID" mkdir -p /etc/data-asset/credentials
docker cp /etc/data-asset/credentials/. data-asset-api:/etc/data-asset/credentials/
docker exec "$CID" chmod 600 /etc/data-asset/credentials/* 2>/dev/null || true
echo "oracle client + credentials ready in container"
EOS
chmod +x /etc/data-asset/ensure_oracle_ro_runtime.sh
bash /etc/data-asset/ensure_oracle_ro_runtime.sh
# load HIS password into a file for env injection without echo
# (already user:pass)
ls -la /etc/data-asset/credentials/
"""

WORK_PY = textwrap.dedent(
    r"""
    import json
    import os
    from datetime import datetime, timezone
    from pathlib import Path

    from app.core.db import SessionLocal
    from app.core.config import settings
    from app.api.v1.metadata_changes import _collect_metadata_snapshot
    from app.services.his_identity_sync import sync_his_identity
    from app.services.credentials import resolve
    from app.models.asset_system import AssetDataSource
    from sqlalchemy import select, text

    def load_cred_file(path: str):
        raw = Path(path).read_text(encoding="utf-8").strip()
        if ":" not in raw:
            raise RuntimeError(f"bad credential file: {path}")
        return raw.split(":", 1)

    # Ensure HIS identity settings for direct thick from 8.83 container
    his_user, his_pwd = load_cred_file("/etc/data-asset/credentials/his_source_10_10_10_15")
    # pydantic settings already loaded; mutate in-process
    settings.his_source_host = "10.10.10.15"
    settings.his_source_port = 1521
    settings.his_source_service = "his"
    settings.his_source_user = his_user
    settings.his_source_password = his_pwd
    settings.his_source_connection_mode = "direct"
    settings.his_source_oracle_client_lib = "/opt/oracle"

    out = {"started_at": datetime.now(timezone.utc).isoformat(), "steps": []}
    db = SessionLocal()
    try:
        # verify sources
        sources = db.scalars(select(AssetDataSource).where(AssetDataSource.enabled.is_(True))).all()
        out["registered_sources"] = [
            {
                "source_code": s.source_code,
                "host": s.host_masked,
                "cred_ok": bool(resolve(s.credential_ref)[0]),
            }
            for s in sources
        ]

        # L10: ODS live metadata (core business owners only)
        ods_filter = ["HIS", "CDA", "ODS", "LIS", "PACS", "YDHL", "SM", "JHEMR", "MTL", "PORTAL_EMPI"]
        print("COLLECT_ODS_START", flush=True)
        ods = _collect_metadata_snapshot(
            "ods_8_216",
            label=f"live_ods_core_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}",
            db=db,
            mode="live_source",
            schema_filter=ods_filter,
        )
        db.commit()
        out["steps"].append({"name": "collect_ods_live", **ods})
        print("COLLECT_ODS_DONE", json.dumps(ods, ensure_ascii=False), flush=True)

        # L10: HIS live metadata (main business owners from asset scope)
        his_filter = [
            "MEDREC", "ORDADM", "LAB", "EXAM", "COMM", "INPBILL", "OUTPBILL",
            "OUTPADM", "INPADM", "DRUG_USER", "PHARMACY", "MEDADM",
        ]
        print("COLLECT_HIS_START", flush=True)
        his = _collect_metadata_snapshot(
            "his_source_10_10_10_15",
            label=f"live_his_core_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}",
            db=db,
            mode="live_source",
            schema_filter=his_filter,
        )
        db.commit()
        out["steps"].append({"name": "collect_his_live", **his})
        print("COLLECT_HIS_DONE", json.dumps(his, ensure_ascii=False), flush=True)

        # update last_check
        db.execute(
            text(
                "UPDATE asset.asset_data_sources SET last_check_status='ok', last_check_at=now(), updated_at=now() "
                "WHERE source_code IN ('ods_8_216','his_source_10_10_10_15')"
            )
        )
        db.commit()

        # L11: HIS identity dry-run (SELECT source only; no identity upsert)
        print("HIS_DRYRUN_START", flush=True)
        dry = sync_his_identity(db, operator="ro_probe", dry_run=True, max_rows=20000, write_audit=False)
        # ensure no pending writes
        db.rollback()
        out["steps"].append({"name": "his_identity_dry_run", **dry})
        print("HIS_DRYRUN_DONE", json.dumps({k: dry[k] for k in dry if k != "prepared"}, ensure_ascii=False), flush=True)

        # snapshot inventory
        snaps = db.execute(
            text(
                "SELECT id, source_code, label, table_count, column_count, created_at "
                "FROM asset.asset_metadata_snapshots ORDER BY id DESC LIMIT 10"
            )
        ).mappings().all()
        out["recent_snapshots"] = [dict(r) for r in snaps]

        # identity tables still empty after dry_run?
        counts = {}
        for t in [
            "asset_identity_persons",
            "asset_identity_departments",
            "asset_identity_person_sources",
            "asset_identity_person_departments",
        ]:
            try:
                counts[t] = db.execute(text(f"SELECT COUNT(*) FROM asset.{t}")).scalar()
            except Exception as ex:
                counts[t] = f"ERR:{type(ex).__name__}"
        out["identity_row_counts_after_dry_run"] = counts
        out["status"] = "success"
    except Exception as ex:
        db.rollback()
        out["status"] = "error"
        out["error"] = f"{type(ex).__name__}:{str(ex)[:500]}"
        print("ERROR", out["error"], flush=True)
        raise
    finally:
        db.close()
        out["finished_at"] = datetime.now(timezone.utc).isoformat()
        print("RESULT_JSON_BEGIN")
        print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
        print("RESULT_JSON_END")
    """
)


def main() -> None:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username="root", password=PASSWORD, timeout=15, allow_agent=False, look_for_keys=False)

    sftp = c.open_sftp()
    with sftp.file("/tmp/ro_prep_runtime.sh", "w") as f:
        f.write(PREP_SH)
    with sftp.file("/tmp/ro_l10_l11_work.py", "w") as f:
        f.write(WORK_PY)
    # also sync improved connectors if present
    local_conn = r"F:\python\数据资产\backend\app\services\db_connectors.py"
    if os.path.isfile(local_conn):
        sftp.put(local_conn, "/tmp/db_connectors.py")
    sftp.close()

    print("=== prep runtime")
    code, out, err = run(c, "bash /tmp/ro_prep_runtime.sh", timeout=60)
    print(out[:3000])
    if err:
        print("ERR", err[:800])

    # sync connector + work script into container
    cmds = (
        "docker cp /tmp/db_connectors.py data-asset-api:/app/app/services/db_connectors.py 2>/dev/null || true; "
        "docker cp /tmp/ro_l10_l11_work.py data-asset-api:/tmp/ro_l10_l11_work.py; "
        "docker exec -e PYTHONPATH=/app -e APP_RATE_LIMIT_ENABLED=false data-asset-api "
        "python /tmp/ro_l10_l11_work.py"
    )
    print("=== L10/L11 work (may take several minutes)")
    code, out, err = run(c, cmds, timeout=900)
    print("exit", code)
    print(out[:20000])
    if err:
        print("ERR", err[:3000])

    # save result on server
    sftp = c.open_sftp()
    with sftp.file("/tmp/ro_l10_l11_result.txt", "w") as f:
        f.write(out)
    sftp.close()
    print("saved /tmp/ro_l10_l11_result.txt")
    c.close()


if __name__ == "__main__":
    main()
