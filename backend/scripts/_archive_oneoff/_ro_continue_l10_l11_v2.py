"""L10 metadata collect + L11 HIS dry-run (fixed collector + optional SYS_EMPLOYEE)."""
from __future__ import annotations

import os
import textwrap

import paramiko

HOST = "10.10.8.83"
PASSWORD = os.environ.get("APP_SSH_PASSWORD", "P@ssw0rd@123")
ROOT = r"F:\python\数据资产\backend"


def run(c, cmd, timeout=900):
    _i, o, e = c.exec_command(cmd, timeout=timeout)
    code = o.channel.recv_exit_status()
    return code, o.read().decode("utf-8", "replace"), e.read().decode("utf-8", "replace")


WORK_PY = textwrap.dedent(
    r"""
    import json
    from datetime import datetime, timezone
    from pathlib import Path

    from app.core.db import SessionLocal
    from app.core.config import settings
    from app.api.v1.metadata_changes import _collect_metadata_snapshot
    from app.services.his_identity_sync import sync_his_identity
    from app.services.credentials import resolve
    from app.models.asset_system import AssetDataSource
    from sqlalchemy import select, text

    his_user, his_pwd = Path("/etc/data-asset/credentials/his_source_10_10_10_15").read_text().strip().split(":", 1)
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
        sources = db.scalars(select(AssetDataSource).where(AssetDataSource.enabled.is_(True))).all()
        out["registered_sources"] = [
            {"source_code": s.source_code, "host": s.host_masked, "cred_ok": bool(resolve(s.credential_ref)[0])}
            for s in sources
        ]

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

        # owner breakdown from latest snapshots
        for sid, name in [(ods["snapshot_id"], "ods"), (his["snapshot_id"], "his")]:
            rows = db.execute(
                text(
                    "SELECT namespace_name, COUNT(DISTINCT table_name) AS tables, COUNT(*) AS cols "
                    "FROM asset.asset_metadata_column_snapshots WHERE snapshot_id=:sid "
                    "GROUP BY namespace_name ORDER BY tables DESC"
                ),
                {"sid": sid},
            ).mappings().all()
            out[f"{name}_owner_breakdown"] = [dict(r) for r in rows]

        db.execute(
            text(
                "UPDATE asset.asset_data_sources SET last_check_status='ok', last_check_at=now(), updated_at=now() "
                "WHERE source_code IN ('ods_8_216','his_source_10_10_10_15')"
            )
        )
        db.commit()

        print("HIS_DRYRUN_START", flush=True)
        dry = sync_his_identity(db, operator="ro_probe", dry_run=True, max_rows=20000, write_audit=False)
        db.rollback()
        out["steps"].append({"name": "his_identity_dry_run", **dry})
        print("HIS_DRYRUN_DONE", flush=True)

        snaps = db.execute(
            text(
                "SELECT id, source_code, label, table_count, column_count, created_at "
                "FROM asset.asset_metadata_snapshots ORDER BY id DESC LIMIT 8"
            )
        ).mappings().all()
        out["recent_snapshots"] = [dict(r) for r in snaps]

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
    for rel, remote in [
        (r"app\services\metadata_collector.py", "/tmp/metadata_collector.py"),
        (r"app\services\his_identity_sync.py", "/tmp/his_identity_sync.py"),
        (r"app\services\db_connectors.py", "/tmp/db_connectors.py"),
    ]:
        sftp.put(os.path.join(ROOT, rel), remote)
    with sftp.file("/tmp/ro_l10_l11_work_v2.py", "w") as f:
        f.write(WORK_PY)
    sftp.close()

    print("=== prep + sync code")
    code, out, err = run(
        c,
        "bash /etc/data-asset/ensure_oracle_ro_runtime.sh; "
        "docker cp /tmp/metadata_collector.py data-asset-api:/app/app/services/metadata_collector.py; "
        "docker cp /tmp/his_identity_sync.py data-asset-api:/app/app/services/his_identity_sync.py; "
        "docker cp /tmp/db_connectors.py data-asset-api:/app/app/services/db_connectors.py; "
        "docker cp /tmp/ro_l10_l11_work_v2.py data-asset-api:/tmp/ro_l10_l11_work_v2.py",
        timeout=60,
    )
    print(out[:2000], err[:500] if err else "")

    print("=== run collect + dry-run")
    code, out, err = run(
        c,
        "docker exec -e PYTHONPATH=/app data-asset-api python /tmp/ro_l10_l11_work_v2.py",
        timeout=900,
    )
    print("exit", code)
    print(out[:25000])
    if err:
        print("ERR", err[:3000])
    sftp = c.open_sftp()
    with sftp.file("/tmp/ro_l10_l11_result_v2.txt", "w") as f:
        f.write(out)
    sftp.close()
    c.close()


if __name__ == "__main__":
    main()
