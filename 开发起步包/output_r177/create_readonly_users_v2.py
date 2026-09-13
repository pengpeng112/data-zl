# -*- coding: utf-8 -*-
"""188 补丁：重试三个失败库（MSSQL 降级授权路径 / 科研重试 / MySQL5.6 兼容语法）。"""
import json
import os
import secrets
import string
from pathlib import Path

CRED_DIR = Path("/etc/data-asset/credentials")
EGRESS = "10.10.8.83"
ALPHA = string.ascii_letters + string.digits
results = []


def genpwd():
    while True:
        p = "".join(secrets.choice(ALPHA) for _ in range(14))
        if (p[0].isalpha() and any(c.isupper() for c in p)
                and any(c.islower() for c in p) and any(c.isdigit() for c in p)):
            return p + "!RO"


def rec(db, ok, detail):
    results.append({"db": db, "ok": ok, "detail": detail})
    print(json.dumps(results[-1], ensure_ascii=False), flush=True)


def mssql_retry():
    import pymssql
    admin = Path(f"{CRED_DIR}/bloodnew_sqlserver_10_10_8_7.readonly.bak-admin").read_text().strip().split(":", 1) \
        if Path(f"{CRED_DIR}/bloodnew_sqlserver_10_10_8_7.readonly.bak-admin").exists() \
        else Path(f"{CRED_DIR}/bloodnew_sqlserver_10_10_8_7.readonly").read_text().strip().split(":", 1)
    pw = genpwd()
    try:
        conn = pymssql.connect(server="10.10.8.7", port="1433", user=admin[0],
                               password=admin[1], timeout=8, login_timeout=8)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM sys.sql_logins WHERE name='da_readonly'")
        exists = cur.fetchone()[0] > 0
        if not exists:
            cur.execute(f"CREATE LOGIN da_readonly WITH PASSWORD='%s'" % pw)
        else:
            cur.execute(f"ALTER LOGIN da_readonly WITH PASSWORD='%s'" % pw)
        cur.execute("SELECT name FROM sys.databases WHERE database_id>4 AND state=0")
        biz = [r[0] for r in cur.fetchall()]
        granted = []
        for dbn in biz:
            try:
                cur.execute(f"USE [{dbn}]")
                cur.execute("SELECT COUNT(*) FROM sys.database_principals WHERE name='da_readonly'")
                if cur.fetchone()[0] == 0:
                    cur.execute("CREATE USER da_readonly FOR LOGIN da_readonly")
                cur.execute("ALTER ROLE db_datareader ADD MEMBER da_readonly")
                granted.append(dbn)
            except Exception as e:
                rec(f"8.7 db={dbn}", False, f"db_datareader 授予失败 {str(e)[:60]}")
        conn.commit()
        conn.close()
        c2 = pymssql.connect(server="10.10.8.7", port="1433", user="da_readonly",
                             password=pw, timeout=8, login_timeout=8)
        with c2.cursor() as cu:
            cu.execute("SELECT COUNT(*) FROM sys.databases")
            n = cu.fetchone()[0]
        c2.close()
        p = Path(f"{CRED_DIR}/bloodnew_sqlserver_10_10_8_7.readonly")
        bak = Path(str(p) + ".bak-admin")
        if not bak.exists():
            bak.write_text(f"{admin[0]}:{admin[1]}")
            os.chmod(bak, 0o600)
        p.write_text(f"da_readonly:{pw}")
        os.chmod(p, 0o600)
        rec("10.10.8.7 mssql", True, f"登录 OK（库可见 {n}）；db_datareader 授予 {len(granted)}/{len(biz)} 库：{granted[:6]}")
    except Exception as e:
        rec("10.10.8.7 mssql", False, str(e)[:130])


def mysql_retry(ip, port, credfile, tag, is56=False):
    import pymysql
    p = Path(f"{CRED_DIR}/{credfile}")
    bak = Path(str(p) + ".bak-admin")
    src = bak if bak.exists() else p
    admin = src.read_text().strip().split(":", 1)
    pw = genpwd()
    try:
        conn = pymysql.connect(host=ip, port=port, user=admin[0], password=admin[1], connect_timeout=8)
        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(*) FROM mysql.user WHERE user='da_readonly' AND host='{EGRESS}'")
        exists = cur.fetchone()[0] > 0
        if not exists:
            cur.execute(f"CREATE USER 'da_readonly'@'{EGRESS}' IDENTIFIED BY %s", (pw,))
        elif is56:
            cur.execute(f"SET PASSWORD FOR 'da_readonly'@'{EGRESS}' = PASSWORD(%s)", (pw,))
        else:
            cur.execute(f"ALTER USER 'da_readonly'@'{EGRESS}' IDENTIFIED BY %s", (pw,))
        cur.execute(f"GRANT SELECT, SHOW VIEW, PROCESS ON *.* TO 'da_readonly'@'{EGRESS}'")
        cur.execute("FLUSH PRIVILEGES")
        conn.commit()
        conn.close()
        c2 = pymysql.connect(host=ip, port=port, user="da_readonly", password=pw, connect_timeout=8)
        with c2.cursor() as cu:
            cu.execute("SELECT COUNT(*) FROM information_schema.tables")
            n = cu.fetchone()[0]
        c2.close()
        if not bak.exists():
            bak.write_text(f"{admin[0]}:{admin[1]}")
            os.chmod(bak, 0o600)
        p.write_text(f"da_readonly:{pw}")
        os.chmod(p, 0o600)
        rec(f"{ip}:{port} {tag}", True, f"information_schema.tables={n} 可读；凭据已切换")
    except Exception as e:
        rec(f"{ip}:{port} {tag}", False, str(e)[:130])


mssql_retry()
mysql_retry("10.10.8.200", 4306, "research_mysql_10_10_8_200.readonly", "科研MariaDB")
mysql_retry("10.10.10.155", 3306, "sddw_test_mysql_10_10_10_155.readonly", "医保测试MySQL5.6", is56=True)
print(json.dumps({"ok": sum(1 for r in results if r["ok"]), "total": len(results)}, ensure_ascii=False))
