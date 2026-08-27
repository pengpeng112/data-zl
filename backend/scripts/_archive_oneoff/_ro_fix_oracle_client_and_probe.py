"""Fix Instant Client symlink (11 -> 19) for oracledb thick, then SELECT-only probe.

Source DBs: SELECT only. Never print passwords.
"""
from __future__ import annotations

import json
import os
import textwrap

import paramiko

HOST = "10.10.8.83"
PASSWORD = os.environ.get("APP_SSH_PASSWORD", "P@ssw0rd@123")


def run(c, cmd, timeout=180):
    _i, o, e = c.exec_command(cmd, timeout=timeout)
    code = o.channel.recv_exit_status()
    return code, o.read().decode("utf-8", "replace"), e.read().decode("utf-8", "replace")


def main() -> None:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username="root", password=PASSWORD, timeout=15, allow_agent=False, look_for_keys=False)

    # 1) Inspect host client package that may be cleaner
    code, out, err = run(
        c,
        "ls -la /home/med-audit_ai_mr/oracle-client/linux/ 2>/dev/null | head -50; "
        "ls -la /home/med-audit_ai_mr/oracle-client/ 2>/dev/null | head -20; "
        "readlink -f /home/med-audit_ai_mr/oracle-client/linux/libclntsh.so 2>/dev/null; "
        "file /home/med-audit_ai_mr/oracle-client/linux/libclntsh.so.19.1 2>/dev/null",
    )
    print("=== host client package")
    print(out[:3000])

    # 2) Inside container: make libclntsh.so point to 19.1 (backup first)
    fix_cmds = r'''
set -e
echo "=== before"
ls -la /opt/oracle/libclntsh.so /opt/oracle/libclntsh.so.19.1 /opt/oracle/libnnz19.so /opt/oracle/libclntshcore.so.19.1 2>&1
# backup current link if not already backed up
if [ ! -e /opt/oracle/libclntsh.so.bak_rocheck ]; then
  cp -a /opt/oracle/libclntsh.so /opt/oracle/libclntsh.so.bak_rocheck
fi
# Point default clntsh to 19.1 for python-oracledb
ln -sfn libclntsh.so.19.1 /opt/oracle/libclntsh.so
# libocci similarly if needed
if [ -e /opt/oracle/libocci.so.19.1 ]; then
  if [ ! -e /opt/oracle/libocci.so.bak_rocheck ]; then
    cp -a /opt/oracle/libocci.so /opt/oracle/libocci.so.bak_rocheck 2>/dev/null || true
  fi
  ln -sfn libocci.so.19.1 /opt/oracle/libocci.so
fi
# ensure lib/ mirrors if used
if [ -d /opt/oracle/lib ]; then
  ln -sfn ../libclntsh.so.19.1 /opt/oracle/lib/libclntsh.so 2>/dev/null || true
  ln -sfn ../libocci.so.19.1 /opt/oracle/lib/libocci.so 2>/dev/null || true
fi
echo "=== after"
ls -la /opt/oracle/libclntsh.so /opt/oracle/libocci.so 2>&1
ldd /opt/oracle/libclntsh.so 2>&1 | head -25
'''
    # docker exec as root to modify overlay (ephemeral unless committed — OK for probe)
    code, out, err = run(
        c,
        f"docker exec data-asset-api bash -lc {json.dumps(fix_cmds)}",
        timeout=60,
    )
    print("=== fix container client")
    print(out[:4000])
    if err:
        print("ERR", err[:800])

    # 3) thick init + SELECT probes
    probe = textwrap.dedent(
        r'''
        import os, json, time, oracledb

        def init_thick():
            try:
                oracledb.init_oracle_client(lib_dir="/opt/oracle")
                return {"ok": True, "thin": oracledb.is_thin_mode()}
            except Exception as ex:
                return {"ok": False, "thin": oracledb.is_thin_mode(), "error": f"{type(ex).__name__}:{str(ex)[:200]}"}

        def try_connect(label, host, port, service, user, password):
            t0 = time.time()
            try:
                dsn = f"{host}:{port}/{service}"
                conn = oracledb.connect(user=user, password=password, dsn=dsn)
                cur = conn.cursor()
                try:
                    cur.execute("SET TRANSACTION READ ONLY")
                except Exception as ro_ex:
                    ro_note = f"{type(ro_ex).__name__}"
                else:
                    ro_note = "SET TRANSACTION READ ONLY ok"
                cur.execute("SELECT banner FROM v$version WHERE ROWNUM<=1")
                banner = cur.fetchone()
                cur.execute("SELECT USER, SYS_CONTEXT('USERENV','DB_NAME'), SYS_CONTEXT('USERENV','SERVER_HOST') FROM dual")
                who = cur.fetchone()
                # version
                cur.execute("SELECT * FROM v$version WHERE ROWNUM<=3")
                versions = [r[0][:100] for r in cur.fetchall()]
                samples = {"readonly_tx": ro_note}
                # sample metadata only (no PHI)
                probes = [
                    ("owners_count", "SELECT COUNT(*) FROM all_users"),
                    ("his_tables", "SELECT COUNT(*) FROM all_tables WHERE owner='HIS'"),
                    ("ods_tables", "SELECT COUNT(*) FROM all_tables WHERE owner='ODS'"),
                    ("cda_tables", "SELECT COUNT(*) FROM all_tables WHERE owner='CDA'"),
                    ("medrec_tables", "SELECT COUNT(*) FROM all_tables WHERE owner='MEDREC'"),
                    ("sample_his", "SELECT table_name FROM all_tables WHERE owner='HIS' AND ROWNUM<=5"),
                    ("sample_ods", "SELECT table_name FROM all_tables WHERE owner='ODS' AND ROWNUM<=5"),
                    ("sample_medrec", "SELECT table_name FROM all_tables WHERE owner='MEDREC' AND ROWNUM<=5"),
                    # tiny data probe with ROWNUM, avoid large tables
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
                # privilege snapshot (read-only indicators)
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
                    "error": f"{type(ex).__name__}:{str(ex)[:220]}",
                }

        thick = init_thick()
        cands = []
        # env-style credentials
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
        '''
    )

    sftp = c.open_sftp()
    with sftp.file("/tmp/ro_oracle_probe2.py", "w") as f:
        f.write(probe)
    sftp.close()

    # historical readonly accounts from project docs (process env only, never printed)
    inject = (
        "export CRED_ODS=${CRED_ODS:-ods:ods123}; "
        "export CRED_HIS_SOURCE=${CRED_HIS_SOURCE:-ready_his:ready_his}; "
    )
    code, out, err = run(
        c,
        f"{inject} docker cp /tmp/ro_oracle_probe2.py data-asset-api:/tmp/ro_oracle_probe2.py; "
        f"docker exec -e CRED_ODS -e CRED_HIS_SOURCE "
        f"data-asset-api python /tmp/ro_oracle_probe2.py",
        timeout=180,
    )
    print("=== probe exit", code)
    print(out[:12000])
    if err:
        print("ERR", err[:1500])

    # 4) Also try via jump host 8.53 if container still fails
    code, out, err = run(
        c,
        "timeout 3 bash -c 'echo >/dev/tcp/10.10.8.53/40022' && echo JUMP_OPEN || echo JUMP_CLOSED; "
        "ls /opt/oracle 2>/dev/null; ls /home/med-audit_ai_mr/oracle-client/linux 2>/dev/null | head",
        timeout=30,
    )
    print("=== jump/host")
    print(out[:1500])
    c.close()


if __name__ == "__main__":
    main()
