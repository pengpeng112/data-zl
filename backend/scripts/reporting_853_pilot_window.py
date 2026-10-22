# -*- coding: utf-8 -*-
"""8.53 DataX 试点窗口测试工具（可复用，给后续 AI）。

用法示例：
  # 幂等验证：指纹 → 清表 → 同窗重跑 → 指纹比对
  MPW=<mysql root pw> python reporting_853_pilot_window.py idempotency \
      --start 2024-02-01 --end 2024-03-01 --table emr_admission_record_202402

  # 新窗口抽取（自动建表/对账）
  MPW=<mysql root pw> python reporting_853_pilot_window.py window \
      --start 2024-03-01 --end 2024-04-01 --table emr_admission_record_202403

约定（见 853_DataX真实试点测试报告与操作手册）：
- 源只读 SELECT（ODS），目标只写 8.53 本地 sanjia_fushen；
- mysqlwriter 必须 connection:[{jdbcUrl,table}] 数组结构（平铺会 NPE）；
- job 文件含凭据：600 权限、跑完即删；密码经环境变量 MPW 注入，零落盘；
- 列清单自动从本地 08 元数据快照解析，不连库。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

import paramiko

HOST = "10.10.8.53"
PORT = 40022
USER = "root"
KEY = os.path.expanduser(r"~/.ssh/id_ed25519_ai")
DATAX_BIN = "/home/datax/bin/datax.py"
SNAPSHOT = (
    Path(__file__).resolve().parents[2] / "开发起步包"
    / "08_数据中心元数据快照.json"
)
VIEW = "ODS.V_EMR_ADMISSION_RECORD"
TIME_COL = "ADMISSION_DATE"
REMOTE_RUNNER = r"""
import base64, json, os, subprocess, sys
job = json.loads(base64.b64decode(sys.argv[1]).decode("utf-8"))
path = "/root/.sjf_win_job.json"
with open(path, "w", encoding="utf-8") as fh:
    json.dump(job, fh)
os.chmod(path, 0o600)
try:
    r = subprocess.run(
        ["timeout", str(sys.argv[2]), "python3", sys.argv[3], path],
        capture_output=True, text=True, timeout=int(sys.argv[2]) + 90)
    metrics = {}
    for line in (r.stdout or "").splitlines():
        if "\u8bfb\u51fa\u8bb0\u5f55\u603b\u6570" in line:
            metrics["rows_read"] = line.split(":")[-1].strip()
        elif "\u603b\u8ba1\u5199\u5165\u603b\u6570" in line or "\u5199\u5165\u603b\u6570" in line:
            metrics.setdefault("rows_written", line.split(":")[-1].strip())
        elif "\u810f\u6570\u636e\u6761\u6570" in line or "\u8bfb\u5199\u5931\u8d25\u603b\u6570" in line:
            metrics.setdefault("dirty", line.split(":")[-1].strip())
    print("EXIT_CODE:", r.returncode)
    print("METRICS:", json.dumps(metrics, ensure_ascii=False))
    errs = [l for l in (r.stdout or "").splitlines() if "ERROR" in l or "Exception" in l]
    for l in errs[:5]:
        print("ERRLINE:", l[:200])
finally:
    os.remove(path)
"""


def load_columns() -> list[str]:
    data = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    ddl = data["schemas"]["ODS"]["views"]["V_EMR_ADMISSION_RECORD"]["ddl"]
    m = re.search(r"\((.*?)\)\s*(?:AS|as)", ddl, re.S)
    cols = re.findall(r'"([A-Za-z0-9_]+)"', m.group(1))
    if not cols:
        raise SystemExit("列清单解析失败（快照 DDL 变更？）")
    return cols


def connect() -> paramiko.SSHClient:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, port=PORT, username=USER, key_filename=KEY,
                   timeout=15, look_for_keys=False, allow_agent=False)
    return client


def mysql(client, sql: str) -> str:
    # SQL 经 base64 管道传递：反引号等元字符不被远端 shell 解释
    import base64
    b64 = base64.b64encode(sql.encode("utf-8")).decode("ascii")
    pw = os.environ.get("MPW", "")
    _, o, _ = client.exec_command(
        "echo %s | base64 -d | MYSQL_PWD='%s' mysql -uroot -h127.0.0.1 -N 2>&1"
        % (b64, pw),
        timeout=120)
    return o.read().decode("utf-8", "replace").strip()


def fetch_datasource(client) -> tuple[str, str, str]:
    out = mysql(
        client,
        "SELECT jdbc_url, jdbc_username, jdbc_password "
        "FROM datax_web.job_jdbc_datasource "
        "WHERE datasource_name='数据中心ODS_ORACLE';")
    parts = out.split("\t")
    if len(parts) < 3:
        raise SystemExit("数据源读取失败: %r" % out[:120])
    return parts[0], parts[1], parts[2]


def build_job(jdbc: str, user: str, pwd: str, cols: list[str],
              start: str, end: str, table: str, mpw: str) -> dict:
    sql = (
        "SELECT " + ",".join(cols) + " FROM " + VIEW +
        " WHERE " + TIME_COL + " >= TO_DATE('" + start +
        "','YYYY-MM-DD') AND " + TIME_COL + " < TO_DATE('" + end + "','YYYY-MM-DD')"
    )
    return {
        "job": {
            "setting": {"speed": {"channel": 1},
                        "errorLimit": {"record": 0, "percentage": 0.0}},
            "content": [{
                "reader": {
                    "name": "oraclereader",
                    "parameter": {
                        "username": user, "password": pwd,
                        "connection": [{"querySql": [sql], "jdbcUrl": [jdbc]}],
                    },
                },
                "writer": {
                    "name": "mysqlwriter",
                    "parameter": {
                        "username": "root", "password": mpw,
                        "connection": [{
                            "jdbcUrl": (
                                "jdbc:mysql://127.0.0.1:3306/sanjia_fushen"
                                "?useUnicode=true&characterEncoding=utf8"
                                "&useSSL=false&rewriteBatchedStatements=true"),
                            "table": [table],
                        }],
                        "column": cols, "writeMode": "insert",
                    },
                },
            }],
        }
    }


def create_table(client, table: str, cols: list[str]) -> None:
    defs = ",".join("`%s` MEDIUMTEXT" % c for c in cols)
    out = mysql(client,
                "CREATE TABLE IF NOT EXISTS sanjia_fushen.%s (%s) "
                "DEFAULT CHARSET=utf8mb4;" % (table, defs))
    if out and "ERROR" in out:
        raise SystemExit("建表失败: " + out[:200])


def fingerprint(client, table: str) -> str:
    return mysql(
        client,
        "SELECT CONCAT_WS('|', COUNT(*), "
        "IFNULL(SUM(CRC32(ID)),0), "
        "IFNULL(SUM(CRC32(CHIEF_COMPLAINT)),0), "
        "IFNULL(SUM(CHAR_LENGTH(PRESENT_ILLNESS)),0), "
        "IFNULL(SUM(CHAR_LENGTH(CHIEF_COMPLAINT)),0)) "
        "FROM sanjia_fushen.%s;" % table)


def run_window(client, job: dict, timeout_s: int) -> dict:
    import base64
    payload = base64.b64encode(
        json.dumps(job).encode("utf-8")).decode("ascii")
    stdin, stdout, _ = client.exec_command(
        "python3 - %s %s %s" % (payload, timeout_s, DATAX_BIN),
        timeout=timeout_s + 120)
    stdin.write(REMOTE_RUNNER)
    stdin.channel.shutdown_write()
    out = stdout.read().decode("utf-8", "replace")
    result: dict = {"exit": None, "metrics": {}}
    for line in out.splitlines():
        if line.startswith("EXIT_CODE:"):
            result["exit"] = int(line.split(":", 1)[1].strip())
        elif line.startswith("METRICS:"):
            result["metrics"] = json.loads(line.split(":", 1)[1])
        elif line.startswith("ERRLINE:"):
            result.setdefault("errors", []).append(line)
    result["raw"] = out
    return result


def verdict(res: dict, count: str) -> bool:
    """读出数 == 落地 count 且脏 0 即对账闭环（rows_written 行格式随版本
    变化，缺失时不阻塞；以目标库实数为准）。"""
    m = res["metrics"]
    if not (res["exit"] == 0 and m.get("rows_read") == count
            and m.get("dirty", "0") == "0"):
        return False
    if m.get("rows_written") not in (None, "") and m["rows_written"] != count:
        return False
    return True


def cmd_window(args) -> int:
    cols = load_columns()
    client = connect()
    jdbc, u, p = fetch_datasource(client)
    create_table(client, args.table, cols)
    if args.truncate:
        mysql(client, "TRUNCATE TABLE sanjia_fushen.%s;" % args.table)
    job = build_job(jdbc, u, p, cols, args.start, args.end, args.table,
                    os.environ.get("MPW", ""))
    res = run_window(client, job, args.timeout)
    count = mysql(client, "SELECT COUNT(*) FROM sanjia_fushen.%s;" % args.table)
    ok = verdict(res, count)
    print(json.dumps({
        "window": [args.start, args.end],
        "table": args.table,
        "exit": res["exit"], "metrics": res["metrics"],
        "target_count": count, "fingerprint": fingerprint(client, args.table),
        "VERDICT": "PASS" if ok else "CHECK",
        "errors": res.get("errors", [])[:3],
    }, ensure_ascii=False, indent=1))
    client.close()
    return 0 if ok else 1


def cmd_idempotency(args) -> int:
    cols = load_columns()
    client = connect()
    jdbc, u, p = fetch_datasource(client)
    table = args.table
    create_table(client, table, cols)
    fp_before = fingerprint(client, table)
    count_before = mysql(client,
                         "SELECT COUNT(*) FROM sanjia_fushen.%s;" % table)
    # 删当月（TRUNCATE=该表整月语义）+ 重插同窗
    mysql(client, "TRUNCATE TABLE sanjia_fushen.%s;" % table)
    count_mid = mysql(client, "SELECT COUNT(*) FROM sanjia_fushen.%s;" % table)
    job = build_job(jdbc, u, p, cols, args.start, args.end, table,
                    os.environ.get("MPW", ""))
    res = run_window(client, job, args.timeout)
    fp_after = fingerprint(client, table)
    count_after = mysql(client,
                        "SELECT COUNT(*) FROM sanjia_fushen.%s;" % table)
    ok = (verdict(res, count_after)
          and fp_before == fp_after and count_before == count_after
          and count_mid == "0")
    print(json.dumps({
        "mode": "idempotency(删当月+插当月)",
        "window": [args.start, args.end], "table": table,
        "count_before": count_before, "count_after_truncate": count_mid,
        "rerun_exit": res["exit"], "rerun_metrics": res["metrics"],
        "count_after": count_after,
        "fingerprint_before": fp_before, "fingerprint_after": fp_after,
        "fingerprint_equal": fp_before == fp_after,
        "VERDICT": "PASS" if ok else "CHECK",
    }, ensure_ascii=False, indent=1))
    client.close()
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name, fn in (("window", cmd_window), ("idempotency", cmd_idempotency)):
        p = sub.add_parser(name)
        p.add_argument("--start", required=True, help="窗口起 YYYY-MM-DD（含）")
        p.add_argument("--end", required=True, help="窗口止 YYYY-MM-DD（不含）")
        p.add_argument("--table", required=True, help="sanjia_fushen 目标表名")
        p.add_argument("--timeout", type=int, default=1200)
        if name == "window":
            p.add_argument("--truncate", action="store_true",
                           help="跑前清空目标表")
        p.set_defaults(func=fn)
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
