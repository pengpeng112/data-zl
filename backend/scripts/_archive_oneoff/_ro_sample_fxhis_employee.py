"""Read-only sample FXHIS.SYS_EMPLOYEE bridge fields (no PHI dump)."""
from __future__ import annotations

import os
import textwrap

import paramiko

HOST = "10.10.8.83"
PASSWORD = os.environ.get("APP_SSH_PASSWORD", "P@ssw0rd@123")

REMOTE = textwrap.dedent(
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

    # counts / null rates without dumping PHI
    queries = {
        "emp_total": "SELECT COUNT(*) FROM FXHIS.SYS_EMPLOYEE WHERE ROWNUM<=50000",
        "emp_valid": "SELECT COUNT(*) FROM FXHIS.SYS_EMPLOYEE WHERE NVL(VALIDSTATE,'1') IN ('1','0','Y') AND ROWNUM<=50000",
        "emp_with_usercode": "SELECT COUNT(*) FROM FXHIS.SYS_EMPLOYEE WHERE USERCODE IS NOT NULL AND ROWNUM<=50000",
        "emp_with_emplcode": "SELECT COUNT(*) FROM FXHIS.SYS_EMPLOYEE WHERE EMPLCODE IS NOT NULL AND ROWNUM<=50000",
        "staff_total": "SELECT COUNT(*) FROM COMM.STAFF_DICT WHERE ROWNUM<=50000",
        "user_total": "SELECT COUNT(*) FROM FXHIS.SYS_USER WHERE ROWNUM<=50000",
        # bridge EMPLCODE = STAFF.EMP_NO
        "bridge_emplcode_eq_empno": (
            "SELECT COUNT(*) FROM FXHIS.SYS_EMPLOYEE e "
            "WHERE EXISTS (SELECT 1 FROM COMM.STAFF_DICT s WHERE s.EMP_NO = e.EMPLCODE) AND ROWNUM<=50000"
        ),
        # bridge USERCODE = STAFF.EMP_NO
        "bridge_usercode_eq_empno": (
            "SELECT COUNT(*) FROM FXHIS.SYS_EMPLOYEE e "
            "WHERE e.USERCODE IS NOT NULL AND EXISTS (SELECT 1 FROM COMM.STAFF_DICT s WHERE s.EMP_NO = e.USERCODE) AND ROWNUM<=50000"
        ),
        # SYS_USER.EMPL_CODE = SYS_EMPLOYEE.EMPLCODE
        "user_to_emp_by_empl_code": (
            "SELECT COUNT(*) FROM FXHIS.SYS_USER u "
            "WHERE EXISTS (SELECT 1 FROM FXHIS.SYS_EMPLOYEE e WHERE e.EMPLCODE = u.EMPL_CODE) AND ROWNUM<=50000"
        ),
        "user_to_staff_by_empl_code": (
            "SELECT COUNT(*) FROM FXHIS.SYS_USER u "
            "WHERE EXISTS (SELECT 1 FROM COMM.STAFF_DICT s WHERE s.EMP_NO = u.EMPL_CODE) AND ROWNUM<=50000"
        ),
    }
    for k, sql in queries.items():
        try:
            cur.execute(sql)
            out[k] = cur.fetchone()[0]
        except Exception as ex:
            out[k] = "ERR:" + type(ex).__name__ + ":" + str(ex)[:80]

    # sample shape only: length of codes, not values with identity
    cur.execute(
        "SELECT LENGTH(EMPLCODE), LENGTH(USERCODE), LENGTH(DEPTCODE), VALIDSTATE, ISDELETED "
        "FROM FXHIS.SYS_EMPLOYEE WHERE ROWNUM<=5"
    )
    out["sample_shape"] = [
        {"len_empl": r[0], "len_user": r[1], "len_dept": r[2], "valid": r[3], "deleted": r[4]}
        for r in cur.fetchall()
    ]
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
    with sftp.file("/tmp/ro_sample_fxhis.py", "w") as f:
        f.write(REMOTE)
    sftp.close()
    cmd = (
        "bash /etc/data-asset/ensure_oracle_ro_runtime.sh >/dev/null; "
        "docker cp /tmp/ro_sample_fxhis.py data-asset-api:/tmp/ro_sample_fxhis.py; "
        "docker exec data-asset-api python /tmp/ro_sample_fxhis.py"
    )
    _i, o, e = c.exec_command(cmd, timeout=180)
    print(o.read().decode("utf-8", "replace")[:8000])
    err = e.read().decode("utf-8", "replace")
    if err:
        print("ERR", err[:1000])
    c.close()


if __name__ == "__main__":
    main()
