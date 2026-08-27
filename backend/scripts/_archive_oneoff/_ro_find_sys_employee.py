"""Read-only: find SYS_EMPLOYEE / employee bridge tables on HIS source."""
from __future__ import annotations

import os
import textwrap

import paramiko

HOST = "10.10.8.83"
PASSWORD = os.environ.get("APP_SSH_PASSWORD", "P@ssw0rd@123")

REMOTE_PY = textwrap.dedent(
    """\
    import json
    from pathlib import Path
    import oracledb

    oracledb.init_oracle_client(lib_dir="/opt/oracle")
    u, p = Path("/etc/data-asset/credentials/his_source_10_10_10_15").read_text().strip().split(":", 1)
    conn = oracledb.connect(user=u, password=p, dsn="10.10.10.15:1521/his")
    cur = conn.cursor()
    try:
        cur.execute("SET TRANSACTION READ ONLY")
    except Exception:
        pass
    out = {}

    cur.execute(
        "SELECT owner, table_name FROM all_tables WHERE table_name = 'SYS_EMPLOYEE' ORDER BY owner"
    )
    out["exact_SYS_EMPLOYEE"] = [{"owner": r[0], "table": r[1]} for r in cur.fetchall()]

    cur.execute(
        "SELECT owner, table_name FROM all_tables "
        "WHERE (table_name LIKE '%EMPLOYEE%' OR table_name LIKE 'SYS_USER%' "
        "OR table_name LIKE '%STAFF%USER%' OR table_name = 'USERS' OR table_name LIKE 'USER_DICT%') "
        "AND owner NOT IN ('SYS','SYSTEM','SYSMAN','APEX_030200','XDB','MDSYS') "
        "ORDER BY owner, table_name"
    )
    out["name_like"] = [{"owner": r[0], "table": r[1]} for r in cur.fetchall()]

    # also search EMPLCODE column across COMM/HISUSER/MEDADM
    cur.execute(
        "SELECT owner, table_name, column_name FROM all_tab_columns "
        "WHERE column_name IN ('EMPLCODE','EMPLNAME','USERID','IDENNO','VALIDSTATE') "
        "AND owner IN ('COMM','HISUSER','MEDADM','MEDREC','INPADM','OUTPADM') "
        "ORDER BY owner, table_name, column_name"
    )
    out["key_cols"] = [{"owner": r[0], "table": r[1], "col": r[2]} for r in cur.fetchall()]

    candidates = []
    seen = set()
    for item in out["exact_SYS_EMPLOYEE"] + out["name_like"]:
        o, t = item["owner"], item["table"]
        key = o + "." + t
        if key in seen:
            continue
        seen.add(key)
        cur.execute(
            "SELECT column_name FROM all_tab_columns WHERE owner=:o AND table_name=:t ORDER BY column_id",
            o=o,
            t=t,
        )
        cols = [r[0] for r in cur.fetchall()]
        try:
            cur.execute("SELECT COUNT(*) FROM " + o + "." + t + " WHERE ROWNUM<=1")
            has_row = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM " + o + "." + t + " WHERE ROWNUM<=20001")
            cnt = cur.fetchone()[0]
        except Exception as ex:
            has_row = "ERR:" + type(ex).__name__
            cnt = None
        candidates.append(
            {
                "fq": key,
                "col_count": len(cols),
                "cols": cols[:30],
                "has_row": has_row,
                "count_cap20k": cnt,
            }
        )
    out["candidates"] = candidates
    print(json.dumps(out, ensure_ascii=False, indent=2))
    cur.close()
    conn.close()
    """
)


def main() -> None:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username="root", password=PASSWORD, timeout=15, allow_agent=False, look_for_keys=False)
    sftp = c.open_sftp()
    with sftp.file("/tmp/ro_find_sys_employee.py", "w") as f:
        f.write(REMOTE_PY)
    sftp.close()
    cmd = (
        "bash /etc/data-asset/ensure_oracle_ro_runtime.sh >/dev/null; "
        "docker cp /tmp/ro_find_sys_employee.py data-asset-api:/tmp/ro_find_sys_employee.py; "
        "docker exec data-asset-api python /tmp/ro_find_sys_employee.py"
    )
    _i, o, e = c.exec_command(cmd, timeout=180)
    print(o.read().decode("utf-8", "replace")[:15000])
    err = e.read().decode("utf-8", "replace")
    if err:
        print("ERR", err[:1500])
    c.close()


if __name__ == "__main__":
    main()
