# -*- coding: utf-8 -*-
"""db_login_probe.py v2 — 逐端点登录验证（容器内）。用法：
  python /tmp/db_login_probe.py --only <name>
凭据读 /tmp/dbcreds.json（name 过滤）；输出单行 JSON（无密码）。
Oracle：先 socket 预检端口，再逐服务名 connect（每服务名独立进程内超时由外层
宿主 `timeout 40` 兜底）。"""
import json
import socket
import sys


def main():
    name = sys.argv[sys.argv.index("--only") + 1]
    item = next(x for x in json.load(open("/tmp/dbcreds.json", encoding="utf-8")) if x["name"] == name)
    res = {"name": name, "ip": item["ip"], "port": item["port"], "type": item["type"], "ok": False, "detail": ""}
    s = socket.socket()
    s.settimeout(4)
    try:
        s.connect((item["ip"], item["port"]))
    except Exception as e:
        res["detail"] = f"tcp {type(e).__name__}"
        print(json.dumps(res, ensure_ascii=False))
        return
    finally:
        s.close()
    try:
        if item["type"] == "oracle":
            import oracledb
            try:
                oracledb.init_oracle_client(lib_dir="/opt/oracle")
            except Exception:
                pass
            last = ""
            for svc in (item.get("svcs") or ["orcl"]):
                try:
                    conn = oracledb.connect(user=item["user"], password=item["pwd"],
                                            dsn=oracledb.makedsn(item["ip"], item["port"], service_name=svc))
                    v = conn.version
                    conn.close()
                    res.update(ok=True, detail=f"oracle svc={svc} v={v}")
                    break
                except Exception as e:
                    last = str(e)[:70]
            else:
                res["detail"] = f"oracle {last}"
        elif item["type"] == "mysql":
            import pymysql
            conn = pymysql.connect(host=item["ip"], port=item["port"], user=item["user"],
                                   password=item["pwd"], connect_timeout=6)
            with conn.cursor() as c:
                c.execute("SELECT VERSION()")
                v = c.fetchone()[0]
            conn.close()
            res.update(ok=True, detail=f"mysql {v}")
        elif item["type"] == "mssql":
            import pymssql
            conn = pymssql.connect(server=item["ip"], port=str(item["port"]), user=item["user"],
                                   password=item["pwd"], timeout=6, login_timeout=6)
            with conn.cursor() as c:
                c.execute("SELECT @@VERSION")
                v = str(c.fetchone()[0])[:30]
            conn.close()
            res.update(ok=True, detail=f"mssql {v}")
        elif item["type"] == "pg":
            import psycopg
            conn = psycopg.connect(host=item["ip"], port=item["port"], user=item["user"],
                                   password=item["pwd"], dbname=item.get("dbname") or "postgres",
                                   connect_timeout=6)
            with conn.cursor() as c:
                c.execute("SELECT version()")
                v = str(c.fetchone()[0])[:40]
            conn.close()
            res.update(ok=True, detail=f"pg {v}")
    except Exception as e:
        res["detail"] = f"{item['type']} {str(e)[:70]}"
    print(json.dumps(res, ensure_ascii=False), flush=True)


main()
