"""Verify platform OracleConnector + credential resolve from registered sources. SELECT only."""
from __future__ import annotations

import os
import textwrap

import paramiko

HOST = "10.10.8.83"
PASSWORD = os.environ.get("APP_SSH_PASSWORD", "P@ssw0rd@123")


def run(c, cmd, timeout=120):
    _i, o, e = c.exec_command(cmd, timeout=timeout)
    return o.channel.recv_exit_status(), o.read().decode("utf-8", "replace"), e.read().decode("utf-8", "replace")


PLATFORM_PY = textwrap.dedent(
    """\
    import json
    from app.core.db import SessionLocal
    from app.models.asset_system import AssetDataSource
    from app.services.credentials import resolve
    from app.services.db_connectors import OracleConnector, validate_readonly_sql

    # guard tests
    blocked = []
    for bad in [
        "UPDATE HIS.PAT_VISIT SET X=1",
        "DELETE FROM HIS.PAT_VISIT",
        "INSERT INTO HIS.X VALUES (1)",
        "DROP TABLE HIS.X",
        "ALTER TABLE HIS.X ADD Y INT",
    ]:
        try:
            validate_readonly_sql(bad)
            blocked.append({"sql": bad, "allowed": True})  # bad if allowed
        except Exception as ex:
            blocked.append({"sql": bad.split()[0], "allowed": False, "err": type(ex).__name__})

    ok_sql = validate_readonly_sql("SELECT 1 AS n FROM dual")
    db = SessionLocal()
    out = {"readonly_guard": blocked, "select_ok": bool(ok_sql), "sources": []}
    try:
        sources = db.query(AssetDataSource).filter(AssetDataSource.enabled.is_(True)).all()
        for s in sources:
            user, pwd = resolve(s.credential_ref)
            item = {
                "source_code": s.source_code,
                "host": s.host_masked,
                "service": s.service_name,
                "cred_resolved": bool(user and pwd),
                "user": user,
            }
            if not user or not pwd:
                item["connect"] = "no_credential"
                out["sources"].append(item)
                continue
            conn = OracleConnector(
                host=s.host_masked,
                port=s.port or 1521,
                database=s.service_name,
                user=user,
                password=pwd,
                connection_mode=s.connection_mode or "direct",
                extra={"oracle_client_lib_dir": "/opt/oracle"},
            )
            ok, msg, ms = conn.test_connectivity()
            item["connect_ok"] = ok
            item["connect_msg"] = msg[:120]
            item["ms"] = ms
            if ok:
                rows = conn.execute_readonly(
                    "SELECT USER AS u, SYS_CONTEXT('USERENV','DB_NAME') AS dbn FROM dual",
                    max_rows=1,
                )
                item["who"] = rows
                # one metadata sample
                if s.source_code.startswith("ods"):
                    sample = conn.execute_readonly(
                        "SELECT table_name FROM all_tables WHERE owner='HIS' AND ROWNUM<=3",
                        max_rows=3,
                    )
                else:
                    sample = conn.execute_readonly(
                        "SELECT table_name FROM all_tables WHERE owner='MEDREC' AND ROWNUM<=3",
                        max_rows=3,
                    )
                item["sample_tables"] = sample
            out["sources"].append(item)
    finally:
        db.close()
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    """
)


def main() -> None:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username="root", password=PASSWORD, timeout=15, allow_agent=False, look_for_keys=False)

    # sync connector path fix into container
    local = r"F:\python\数据资产\backend\app\services\db_connectors.py"
    sftp = c.open_sftp()
    sftp.put(local, "/tmp/db_connectors.py")
    with sftp.file("/tmp/ro_platform_check.py", "w") as f:
        f.write(PLATFORM_PY)
    sftp.close()

    code, out, err = run(
        c,
        "docker cp /tmp/db_connectors.py data-asset-api:/app/app/services/db_connectors.py; "
        "docker cp /tmp/ro_platform_check.py data-asset-api:/tmp/ro_platform_check.py; "
        "docker exec data-asset-api bash -lc "
        "'ln -sfn libclntsh.so.19.1 /opt/oracle/libclntsh.so; "
        "ln -sfn libocci.so.19.1 /opt/oracle/libocci.so; "
        "cd /app && python /tmp/ro_platform_check.py'",
        timeout=120,
    )
    print("exit", code)
    print(out[:8000])
    if err:
        print("ERR", err[:1500])
    c.close()


if __name__ == "__main__":
    main()
