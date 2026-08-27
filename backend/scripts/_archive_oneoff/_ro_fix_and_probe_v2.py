"""Upload shell+python to 8.83, fix Instant Client to 19.1, SELECT-only probe."""
from __future__ import annotations

import os
import textwrap

import paramiko

HOST = "10.10.8.83"
PASSWORD = os.environ.get("APP_SSH_PASSWORD", "P@ssw0rd@123")


def run(c, cmd, timeout=180):
    _i, o, e = c.exec_command(cmd, timeout=timeout)
    code = o.channel.recv_exit_status()
    return code, o.read().decode("utf-8", "replace"), e.read().decode("utf-8", "replace")


FIX_SH = r"""#!/bin/bash
set -e
echo "=== before"
ls -la /opt/oracle/libclntsh.so /opt/oracle/libclntsh.so.19.1 /opt/oracle/libnnz19.so /opt/oracle/libclntshcore.so.19.1
if [ ! -e /opt/oracle/libclntsh.so.bak_rocheck ]; then
  cp -a /opt/oracle/libclntsh.so /opt/oracle/libclntsh.so.bak_rocheck
fi
ln -sfn libclntsh.so.19.1 /opt/oracle/libclntsh.so
if [ -e /opt/oracle/libocci.so.19.1 ]; then
  if [ ! -e /opt/oracle/libocci.so.bak_rocheck ]; then
    cp -a /opt/oracle/libocci.so /opt/oracle/libocci.so.bak_rocheck 2>/dev/null || true
  fi
  ln -sfn libocci.so.19.1 /opt/oracle/libocci.so
fi
if [ -d /opt/oracle/lib ]; then
  ln -sfn ../libclntsh.so.19.1 /opt/oracle/lib/libclntsh.so 2>/dev/null || true
  ln -sfn ../libocci.so.19.1 /opt/oracle/lib/libocci.so 2>/dev/null || true
fi
echo "=== after"
ls -la /opt/oracle/libclntsh.so /opt/oracle/libocci.so
echo "=== ldd"
ldd /opt/oracle/libclntsh.so | head -25
"""

PROBE_PY = textwrap.dedent(
    r"""
    import os, json, time, oracledb

    def init_thick():
        try:
            oracledb.init_oracle_client(lib_dir="/opt/oracle")
            return {"ok": True, "thin": oracledb.is_thin_mode()}
        except Exception as ex:
            return {"ok": False, "thin": oracledb.is_thin_mode(), "error": f"{type(ex).__name__}:{str(ex)[:240]}"}

    def try_connect(label, host, port, service, user, password):
        t0 = time.time()
        try:
            dsn = f"{host}:{port}/{service}"
            conn = oracledb.connect(user=user, password=password, dsn=dsn)
            cur = conn.cursor()
            try:
                cur.execute("SET TRANSACTION READ ONLY")
                ro_note = "SET TRANSACTION READ ONLY ok"
            except Exception as ro_ex:
                ro_note = f"{type(ro_ex).__name__}:{str(ro_ex)[:80]}"
            cur.execute("SELECT banner FROM v$version WHERE ROWNUM<=1")
            banner = cur.fetchone()
            cur.execute("SELECT USER, SYS_CONTEXT('USERENV','DB_NAME'), SYS_CONTEXT('USERENV','SERVER_HOST') FROM dual")
            who = cur.fetchone()
            cur.execute("SELECT banner FROM v$version WHERE ROWNUM<=3")
            versions = [r[0][:100] for r in cur.fetchall()]
            samples = {"readonly_tx": ro_note}
            probes = [
                ("owners_count", "SELECT COUNT(*) FROM all_users"),
                ("his_tables", "SELECT COUNT(*) FROM all_tables WHERE owner='HIS'"),
                ("ods_tables", "SELECT COUNT(*) FROM all_tables WHERE owner='ODS'"),
                ("cda_tables", "SELECT COUNT(*) FROM all_tables WHERE owner='CDA'"),
                ("medrec_tables", "SELECT COUNT(*) FROM all_tables WHERE owner='MEDREC'"),
                ("sample_his", "SELECT table_name FROM all_tables WHERE owner='HIS' AND ROWNUM<=5"),
                ("sample_ods", "SELECT table_name FROM all_tables WHERE owner='ODS' AND ROWNUM<=5"),
                ("sample_medrec", "SELECT table_name FROM all_tables WHERE owner='MEDREC' AND ROWNUM<=5"),
                ("dual_ok", "SELECT 1 AS n FROM dual"),
            ]
            for key, sql in probes:
                try:
                    cur.execute(sql)
                    rows = cur.fetchall()
                    if key.startswith("sample_"):
                        samples[key] = [r[0] for r in rows]
                    else:
                        samples[key] = rows[0][0] if rows else None
                except Exception as ex:
                    samples[key] = f"ERR:{type(ex).__name__}:{str(ex)[:80]}"
            try:
                cur.execute("SELECT privilege FROM user_sys_privs WHERE ROWNUM<=20")
                samples["sys_privs"] = [r[0] for r in cur.fetchall()]
            except Exception as ex:
                samples["sys_privs"] = f"ERR:{type(ex).__name__}"
            try:
                cur.execute(
                    "SELECT privilege FROM session_privs "
                    "WHERE privilege IN ('SELECT ANY TABLE','CREATE TABLE','INSERT ANY TABLE',"
                    "'UPDATE ANY TABLE','DELETE ANY TABLE','DROP ANY TABLE') ORDER BY 1"
                )
                samples["dangerous_or_select_privs"] = [r[0] for r in cur.fetchall()]
            except Exception as ex:
                samples["dangerous_or_select_privs"] = f"ERR:{type(ex).__name__}"
            # explicit DML denial probe: attempt should fail (we do NOT commit anything)
            # Use a no-op that requires write privs against dual-like system — safer: try CREATE TABLE in private schema with ROWNUM
            # Skip actual DML attempts; only report privileges.
            cur.close()
            conn.close()
            return {
                "label": label,
                "ok": True,
                "ms": round((time.time()-t0)*1000,1),
                "banner": banner[0][:100] if banner else None,
                "user": who[0] if who else None,
                "db": who[1] if who else None,
                "server_host": who[2] if who else None,
                "versions": versions,
                "samples": samples,
            }
        except Exception as ex:
            return {
                "label": label,
                "ok": False,
                "ms": round((time.time()-t0)*1000,1),
                "error": f"{type(ex).__name__}:{str(ex)[:240]}",
            }

    thick = init_thick()
    cands = []
    for env_name, label, host, port, service in [
        ("CRED_ODS", "ODS", "10.10.8.216", 1521, "orcl"),
        ("CRED_HIS_SOURCE", "HIS", "10.10.10.15", 1521, "his"),
    ]:
        raw = os.environ.get(env_name, "")
        if raw and ":" in raw:
            u, p = raw.split(":", 1)
            cands.append((label, host, port, service, u, p))
    out = {"thick": thick, "candidate_labels": [x[0] for x in cands], "results": []}
    for item in cands:
        out["results"].append(try_connect(*item))
    print(json.dumps(out, ensure_ascii=False, indent=2))
    """
)


def main() -> None:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username="root", password=PASSWORD, timeout=15, allow_agent=False, look_for_keys=False)

    sftp = c.open_sftp()
    with sftp.file("/tmp/ro_fix_oracle.sh", "w") as f:
        f.write(FIX_SH)
    with sftp.file("/tmp/ro_oracle_probe2.py", "w") as f:
        f.write(PROBE_PY)
    sftp.close()

    code, out, err = run(
        c,
        "chmod +x /tmp/ro_fix_oracle.sh; "
        "docker cp /tmp/ro_fix_oracle.sh data-asset-api:/tmp/ro_fix_oracle.sh; "
        "docker exec data-asset-api bash /tmp/ro_fix_oracle.sh",
        timeout=60,
    )
    print("=== fix exit", code)
    print(out[:4000])
    if err:
        print("ERR", err[:1000])

    inject = (
        "export CRED_ODS=${CRED_ODS:-ods:ods123}; "
        "export CRED_HIS_SOURCE=${CRED_HIS_SOURCE:-ready_his:ready_his}; "
    )
    code, out, err = run(
        c,
        f"{inject} docker cp /tmp/ro_oracle_probe2.py data-asset-api:/tmp/ro_oracle_probe2.py; "
        f"docker exec -e CRED_ODS -e CRED_HIS_SOURCE data-asset-api python /tmp/ro_oracle_probe2.py",
        timeout=180,
    )
    print("=== probe exit", code)
    print(out[:12000])
    if err:
        print("ERR", err[:1500])
    c.close()


if __name__ == "__main__":
    main()
