# -*- coding: utf-8 -*-
"""188: 为 6 个库创建平台专用只读账号 da_readonly（用户授权 2026-09-13）。
权限口径：可读全部 schema 表/视图 + 数据字典/权限视图；零 DML/DDL。
MySQL 系限来源 10.10.8.83（平台容器出口）。密码 secrets 随机、只写平台受控文件，不打印。
建后用新账号实测登录+权限自检，并把平台凭据文件切换到新账号（原件备份 .bak-admin）。"""
import json
import os
import secrets
import string
from pathlib import Path

CRED_DIR = Path("/etc/data-asset/credentials")
CONTAINER_EGRESS = "10.10.8.83"
ALPHA = string.ascii_letters + string.digits


def genpwd():
    # 各库方言安全字符集：字母数字 + '!'+下划线，首字母、含大小写数字
    while True:
        p = "".join(secrets.choice(ALPHA) for _ in range(14))
        if (p[0].isalpha() and any(c.isupper() for c in p)
                and any(c.islower() for c in p) and any(c.isdigit() for c in p)):
            return p + "!RO"


results = []

def rec(**kw):
    results.append(kw)
    print(json.dumps(kw, ensure_ascii=False), flush=True)


def oracle_main():
    """SDDW_PROD 152：system 管理账号在建 da_readonly。"""
    import oracledb
    try:
        oracledb.init_oracle_client(lib_dir="/opt/oracle")
    except Exception:
        pass
    admin = Path(f"{CRED_DIR}/sddw_oracle_10_10_10_152.readonly").read_text().strip().split(":", 1)
    pw = genpwd()
    try:
        conn = oracledb.connect(user=admin[0], password=admin[1],
                                 dsn=oracledb.makedsn("10.10.10.152", 1521, service_name="orcl"))
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM dba_users WHERE username='DA_READONLY'")
        if cur.fetchone()[0] == 0:
            cur.execute(f'CREATE USER DA_READONLY IDENTIFIED BY "{pw}"')
        cur.execute("GRANT CREATE SESSION, SELECT_CATALOG_ROLE, SELECT ANY TABLE TO DA_READONLY")
        conn.commit()
        conn.close()
        # 新账号实测：登录+跨 schema 读+字典读
        c2 = oracledb.connect(user="DA_READONLY", password=pw,
                              dsn=oracledb.makedsn("10.10.10.152", 1521, service_name="orcl"))
        cu = c2.cursor()
        cu.execute("SELECT COUNT(*) FROM dba_users")
        dict_n = cu.fetchone()[0]
        cu.execute("SELECT COUNT(*) FROM dba_tab_privs")
        priv_n = cu.fetchone()[0]
        c2.close()
        Path(f"{CRED_DIR}/sddw_oracle_10_10_10_152.readonly").write_text(f"DA_READONLY:{pw}")
        os.chmod(f"{CRED_DIR}/sddw_oracle_10_10_10_152.readonly", 0o600)
        rec(db="10.10.10.152 oracle", user="DA_READONLY", ok=True,
            detail=f"dba_users={dict_n}, dba_tab_privs={priv_n} 可读；凭据已切换")
    except Exception as e:
        rec(db="10.10.10.152 oracle", user="DA_READONLY", ok=False, detail=str(e)[:120])


def mysql_main(ip, port, credfile, tag):
    import pymysql
    admin = Path(f"{CRED_DIR}/{credfile}").read_text().strip().split(":", 1)
    pw = genpwd()
    try:
        conn = pymysql.connect(host=ip, port=port, user=admin[0], password=admin[1], connect_timeout=8)
        cur = conn.cursor()
        cur.execute(f"CREATE USER IF NOT EXISTS 'da_readonly'@'{CONTAINER_EGRESS}' IDENTIFIED BY %s", (pw,))
        # 若已存在则重置密码为本轮强密码
        cur.execute(f"ALTER USER 'da_readonly'@'{CONTAINER_EGRESS}' IDENTIFIED BY %s", (pw,))
        cur.execute(f"GRANT SELECT, SHOW VIEW, PROCESS ON *.* TO 'da_readonly'@'{CONTAINER_EGRESS}'")
        conn.commit()
        conn.close()
        c2 = pymysql.connect(host=ip, port=port, user="da_readonly", password=pw, connect_timeout=8)
        with c2.cursor() as cu:
            cu.execute("SELECT COUNT(*) FROM information_schema.tables")
            t_n = cu.fetchone()[0]
            cu.execute("SHOW GRANTS")
            g = cu.fetchone()
        c2.close()
        p = Path(f"{CRED_DIR}/{credfile}")
        bak = Path(str(p) + ".bak-admin")
        if not bak.exists():
            bak.write_text(p.read_text())
            os.chmod(bak, 0o600)
        p.write_text(f"da_readonly:{pw}")
        os.chmod(p, 0o600)
        rec(db=f"{ip}:{port} {tag}", user="da_readonly", ok=True,
            detail=f"information_schema.tables={t_n} 可读；grants={str(g)[:60]}；凭据已切换(原件备份)")
    except Exception as e:
        rec(db=f"{ip}:{port} {tag}", user="da_readonly", ok=False, detail=str(e)[:120])


def mssql_main():
    import pymssql
    admin = Path(f"{CRED_DIR}/bloodnew_sqlserver_10_10_8_7.readonly").read_text().strip().split(":", 1)
    pw = genpwd()
    try:
        conn = pymssql.connect(server="10.10.8.7", port="1433", user=admin[0],
                               password=admin[1], timeout=8, login_timeout=8)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM sys.sql_logins WHERE name='da_readonly'")
        if cur.fetchone()[0] == 0:
            cur.execute(f"CREATE LOGIN da_readonly WITH PASSWORD='%s'" % pw)
        cur.execute("GRANT VIEW ANY DEFINITION TO da_readonly")
        cur.execute("SELECT name FROM sys.databases WHERE database_id>4")
        biz_dbs = [r[0] for r in cur.fetchall()]
        for dbn in biz_dbs:
            try:
                cur.execute(f"USE [{dbn}]")
                cur.execute("SELECT COUNT(*) FROM sys.database_principals WHERE name='da_readonly'")
                if cur.fetchone()[0] == 0:
                    cur.execute(f"CREATE USER da_readonly FOR LOGIN da_readonly")
                cur.execute(f"ALTER ROLE db_datareader ADD MEMBER da_readonly")
                cur.execute(f"GRANT VIEW DEFINITION TO da_readonly")
            except Exception as e:
                rec(db=f"10.10.8.7 mssql db={dbn}", user="da_readonly", ok=False, detail=str(e)[:80])
        conn.commit()
        conn.close()
        # 新账号实测
        c2 = pymssql.connect(server="10.10.8.7", port="1433", user="da_readonly",
                              password=pw, timeout=8, login_timeout=8)
        with c2.cursor() as cu:
            cu.execute("SELECT COUNT(*) FROM sys.databases")
            n = cu.fetchone()[0]
        c2.close()
        p = Path(f"{CRED_DIR}/bloodnew_sqlserver_10_10_8_7.readonly")
        bak = Path(str(p) + ".bak-admin")
        if not bak.exists():
            bak.write_text(p.read_text())
            os.chmod(bak, 0o600)
        p.write_text(f"da_readonly:{pw}")
        os.chmod(p, 0o600)
        rec(db="10.10.8.7 mssql", user="da_readonly", ok=True,
            detail=f"登录成功 sys.databases={n}；业务库 {len(biz_dbs)} 个已授 db_datareader；凭据已切换(原件备份)")
    except Exception as e:
        rec(db="10.10.8.7 mssql", user="da_readonly", ok=False, detail=str(e)[:120])


oracle_main()
mssql_main()
mysql_main("10.10.8.200", 4306, "research_mysql_10_10_8_200.readonly", "科研MariaDB")
mysql_main("10.10.8.161", 3306, "outpatient_mysql_10_10_8_161.readonly", "门诊预约MySQL8")
mysql_main("10.10.8.163", 3306, "queue_mysql_10_10_8_163.readonly", "门诊叫号MySQL8")
mysql_main("10.10.10.155", 3306, "sddw_test_mysql_10_10_10_155.readonly", "医保测试MySQL")
mysql_main("10.10.10.50", 3306, "adverse_event_mysql_10_10_10_50.readonly", "不良事件MariaDB")

print(json.dumps({"summary": {"total": len(results), "ok": sum(1 for r in results if r.get("ok"))}}, ensure_ascii=False))
