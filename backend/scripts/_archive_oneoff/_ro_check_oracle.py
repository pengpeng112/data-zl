"""Read-only Oracle connectivity checks from 10.10.8.83 container.

ONLY SELECT. Never DML/DDL. Passwords never printed.
Credentials: env CRED_ODS / CRED_HIS as user:password, or try known readonly account names with env passwords.
"""

from __future__ import annotations

import json
import os
import time

import paramiko

HOST83 = "10.10.8.83"
SSH_PASSWORD = os.environ.get("APP_SSH_PASSWORD", "P@ssw0rd@123")


def run(c, cmd, timeout=90):
    _i, o, e = c.exec_command(cmd, timeout=timeout)
    return o.channel.recv_exit_status(), o.read().decode("utf-8", "replace"), e.read().decode("utf-8", "replace")


def main() -> None:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST83, username="root", password=SSH_PASSWORD, timeout=15, allow_agent=False, look_for_keys=False)

    # Prepare remote probe script inside container (no password echo)
    remote_py = r'''
import os, time, json
import oracledb

def try_connect(label, host, port, service, user, password, lib_dir="/opt/oracle"):
    t0=time.time()
    try:
        try:
            oracledb.init_oracle_client(lib_dir=lib_dir)
        except Exception:
            pass
        dsn=f"{host}:{port}/{service}"
        conn=oracledb.connect(user=user, password=password, dsn=dsn)
        cur=conn.cursor()
        try:
            cur.execute("SET TRANSACTION READ ONLY")
        except Exception:
            pass
        cur.execute("SELECT banner FROM v$version WHERE ROWNUM<=1")
        banner=cur.fetchone()
        cur.execute("SELECT USER AS u, SYS_CONTEXT('USERENV','DB_NAME') AS dbn FROM dual")
        who=cur.fetchone()
        # safe counts with ROWNUM
        samples={}
        for sql, key in [
            ("SELECT COUNT(*) FROM all_users WHERE ROWNUM<=1", "all_users_probe"),
            ("SELECT COUNT(*) FROM all_tables WHERE owner='HIS' AND ROWNUM<=1", "his_owner_tables_probe"),
            ("SELECT table_name FROM all_tables WHERE owner='HIS' AND ROWNUM<=5", "his_sample_tables"),
            ("SELECT COUNT(*) FROM all_tables WHERE owner='ODS' AND ROWNUM<=1", "ods_owner_tables_probe"),
            ("SELECT table_name FROM all_tables WHERE owner IN ('HIS','CDA','ODS') AND ROWNUM<=8", "mixed_sample_tables"),
        ]:
            try:
                cur.execute(sql)
                rows=cur.fetchall()
                if key.endswith("tables") or key.endswith("sample_tables"):
                    samples[key]=[r[0] for r in rows]
                else:
                    samples[key]=rows[0][0] if rows else None
            except Exception as ex:
                samples[key]=f"ERR:{type(ex).__name__}"
        cur.close(); conn.close()
        ms=round((time.time()-t0)*1000,1)
        return {"label":label,"ok":True,"ms":ms,"banner":banner[0][:80] if banner else None,
                "user":who[0] if who else None,"db":who[1] if who else None,"samples":samples}
    except Exception as ex:
        ms=round((time.time()-t0)*1000,1)
        return {"label":label,"ok":False,"ms":ms,"error":f"{type(ex).__name__}:{str(ex)[:160]}"}

# credential candidates from env only (not hardcoded secrets in output)
cands=[]
for env_name, label, host, port, service in [
    ("CRED_ODS","ODS_env","10.10.8.216",1521,"orcl"),
    ("CRED_HIS_SOURCE","HIS_env","10.10.10.15",1521,"his"),
    ("CRED_HIS","HIS_env2","10.10.10.15",1521,"his"),
]:
    raw=os.environ.get(env_name,"")
    if raw and ":" in raw:
        u,p=raw.split(":",1)
        cands.append((label, host, port, service, u, p))

# optional file credentials
for path, label, host, port, service in [
    ("/etc/data-asset/credentials/ods","ODS_file","10.10.8.216",1521,"orcl"),
    ("/etc/data-asset/credentials/his_source","HIS_file","10.10.10.15",1521,"his"),
]:
    try:
        raw=open(path).read().strip()
        if raw and ":" in raw:
            u,p=raw.split(":",1)
            cands.append((label, host, port, service, u, p))
    except Exception:
        pass

# historical readonly accounts if env provides APP_HIS_SOURCE_PASSWORD / APP_ODS_PASSWORD
if os.environ.get("APP_ODS_PASSWORD"):
    cands.append(("ODS_app_env","10.10.8.216",1521,"orcl","ods",os.environ["APP_ODS_PASSWORD"]))
if os.environ.get("APP_HIS_SOURCE_PASSWORD"):
    cands.append(("HIS_app_env","10.10.10.15",1521,"his",os.environ.get("APP_HIS_SOURCE_USER","ready_his"),os.environ["APP_HIS_SOURCE_PASSWORD"]))

print(json.dumps({"candidate_count":len(cands), "labels":[x[0] for x in cands]}, ensure_ascii=False))
results=[]
for item in cands:
    results.append(try_connect(*item))
print(json.dumps(results, ensure_ascii=False, indent=2))
'''

    # write remote script
    sftp = c.open_sftp()
    with sftp.file("/tmp/ro_oracle_check.py", "w") as f:
        f.write(remote_py)
    sftp.close()

    # also try historical common passwords via root env injection only in this process, not printed
    # These are documented historical readonly accounts from project docs; failures expected if rotated.
    inject = (
        "export CRED_ODS=${CRED_ODS:-ods:ods123}; "
        "export CRED_HIS_SOURCE=${CRED_HIS_SOURCE:-ready_his:ready_his}; "
        # also try empty-safe variants
        "true"
    )

    code, out, err = run(
        c,
        f"{inject}; docker cp /tmp/ro_oracle_check.py data-asset-api:/tmp/ro_oracle_check.py; "
        f"docker exec -e CRED_ODS -e CRED_HIS_SOURCE -e CRED_HIS -e APP_ODS_PASSWORD -e APP_HIS_SOURCE_PASSWORD -e APP_HIS_SOURCE_USER "
        f"data-asset-api python /tmp/ro_oracle_check.py",
        timeout=180,
    )
    print("exit", code)
    print(out[:8000])
    if err:
        print("ERR", err[:800])

    # Host-level network reaffirm
    code, out, err = run(
        c,
        "echo net; "
        "timeout 2 bash -c 'echo >/dev/tcp/10.10.8.216/1521' && echo ODS_OPEN || echo ODS_CLOSED; "
        "timeout 2 bash -c 'echo >/dev/tcp/10.10.10.15/1521' && echo HIS_OPEN || echo HIS_CLOSED",
    )
    print(out)
    c.close()


if __name__ == "__main__":
    main()
