# -*- coding: utf-8 -*-
"""批9 步骤5 回读（阶段③后汇总）：
1) 每表守恒：源月计数（差距台账）vs 管道分类账（INSERT+NO_CHANGE+CAS+隔离+UPDATE）
   ——由驱动 stats JSON 汇总计算（此处输出）；
2) 目标 8.74 回读：每表 SYSTEM_TIME apply 窗足迹（TIMESTAMP 表 TO_DATE 窗比较；
   VARCHAR2 两表 EMR_DEATH_RECORD/EMR_INFOR_CRITICALLY_ILL 按字符串比较，
   NLS 有损串形态已知 T-B06-3——两种形态都计数）；
3) 回执账/版本账/水位/OPEN 隔离组快照。
运行：docker exec -i data-asset-api python -" < b9_readback.py
"""
import json
import os
from datetime import datetime, timezone

import oracledb
from sqlalchemy import create_engine, text

STAGE = "/opt/data-asset/t1-stage"
MONTHS = ["2026-01", "2026-02", "2026-03", "2026-04", "2026-05",
          "2026-06", "2026-07", "2026-08", "2026-09", "2026-10P"]
VARCHAR_SYSTEM_TIME = {"EMR_DEATH_RECORD", "EMR_INFOR_CRITICALLY_ILL"}
RUN_START = "2026-10-27"  # 本批回补首笔 SYSTEM_TIME 起点界（字符串/时间均用）

order = json.load(open(f"{STAGE}/b9_exec_order.json", encoding="utf-8"))
survey = json.load(open(f"{STAGE}/b9_gap_survey_20261027.json", encoding="utf-8"))

report = {"conservation": {}, "target_readback": {}, "control": {}}

# 1) 守恒（源月计数 vs 管道分类账）
for item in order:
    t = item["table"]
    try:
        stats = json.load(open(f"{STAGE}/b9_backfill_{t}.json", encoding="utf-8"))
    except FileNotFoundError:
        report["conservation"][t] = "STAT_MISSING"
        continue
    src_monthly = (survey.get(t) or {}).get("monthly") or {}
    cons = {}
    for label in MONTHS:
        s = stats.get(label)
        if not isinstance(s, dict):
            cons[label] = {"src": src_monthly.get(label[:7]), "pipe": "NO_RECORD"}
            continue
        part = s.get("partition") or {}
        cons[label] = {
            "src": src_monthly.get(label[:7]),
            "rows": s.get("rows"),
            "insert": part.get("insert"),
            "update": part.get("update"),
            "no_change": part.get("no_change"),
            "cas_conflict": part.get("cas_conflict"),
            "missing_parent": part.get("missing_parent"),
            "reconciled": s.get("reconciled"),
        }
    tot_src = sum(v for v in src_monthly.values() if isinstance(v, int))
    tot_pipe = sum(
        (c.get("rows") or 0) for c in cons.values() if isinstance(c.get("rows"), int))
    tot_insert = sum((c.get("insert") or 0) for c in cons.values()
                     if isinstance(c.get("insert"), int))
    tot_nochange = sum((c.get("no_change") or 0) for c in cons.values()
                       if isinstance(c.get("no_change"), int))
    tot_cas = sum((c.get("cas_conflict") or 0) for c in cons.values()
                  if isinstance(c.get("cas_conflict"), int))
    tot_update = sum((c.get("update") or 0) for c in cons.values()
                     if isinstance(c.get("update"), int))
    report["conservation"][t] = {
        "months": cons,
        "total_src_window": tot_src,
        "total_pipe_rows": tot_pipe,
        "total_insert": tot_insert,
        "total_no_change": tot_nochange,
        "total_cas_conflict": tot_cas,
        "total_update": tot_update,
        "delta_src_minus_pipe": (tot_src - tot_pipe) if isinstance(tot_src, int) else None,
    }
    print(f"[conservation] {t}: src={tot_src} pipe={tot_pipe} "
          f"insert={tot_insert} no_change={tot_nochange} cas={tot_cas} update={tot_update}",
          flush=True)

# 2) 目标 8.74 SYSTEM_TIME 足迹回读
oracledb.init_oracle_client(lib_dir="/opt/oracle")
line = open("/etc/data-asset/credentials/sanjia_front_oracle_10_10_8_74.readonly").readline().strip()
u, _, p = line.partition(":")
tc = oracledb.connect(user=u, password=p, dsn="10.10.8.74:1521/orcl", tcp_connect_timeout=20)
tcur = tc.cursor()
tcur.execute("SELECT COUNT(*) FROM DBOPER.ASSET_T1_RECEIPTS")
report["target_readback"]["receipt_total"] = tcur.fetchone()[0]
for item in order:
    t = item["table"]
    if t in VARCHAR_SYSTEM_TIME:
        # 字符串窗回读（批5/批6 先例）：新写者 NLS 'DD-MON-YY' 形态实测为
        # '27-10月-26'（年=26=2026 两位）——锚定本批运行日（天27/28月10）计数；
        # 旧写者 ISO 'YYYY-MM-DD…' 形态另列（10月中=外部写者/历史）。
        tcur.execute(
            f"SELECT COUNT(*) FROM DBOPER.{t} WHERE REGEXP_LIKE(SYSTEM_TIME, "
            "'^2[78]-10月-26 ?$')")
        nls_n = tcur.fetchone()[0]
        tcur.execute(
            f"SELECT COUNT(*) FROM DBOPER.{t} WHERE SYSTEM_TIME LIKE '2026-10-2%' "
            "AND LENGTH(SYSTEM_TIME) >= 10")
        iso_n = tcur.fetchone()[0]
        report["target_readback"][t] = {
            "system_time_type": "VARCHAR2",
            "nls_form_rows_run_window": nls_n,
            "iso_form_rows_october": iso_n,
        }
        print(f"[readback] {t}: VARCHAR2 nls_form={nls_n} iso_oct={iso_n}", flush=True)
    else:
        tcur.execute(
            f"SELECT COUNT(*) FROM DBOPER.{t} "
            "WHERE SYSTEM_TIME >= TO_DATE('2026-10-27','YYYY-MM-DD')")
        n = tcur.fetchone()[0]
        report["target_readback"][t] = {"system_time_type": "TIMESTAMP",
                                        "rows_ge_run_start": n}
        print(f"[readback] {t}: rows_ge_2026-10-27={n}", flush=True)
tc.close()

# 3) 控制面快照：水位/OPEN 隔离组/版本账笔数/回执笔数
eng = create_engine(os.environ["APP_DB_URL"])
with eng.connect() as s:
    rows = s.execute(text(
        "SELECT canonical_table, continuous_through FROM "
        "asset.asset_reporting_watermarks WHERE canonical_table IN ("
        + ",".join(f"'{i['table']}'" for i in order) + ")")).fetchall()
    report["control"]["watermarks"] = {r[0]: str(r[1]) for r in rows}
    rows = s.execute(text(
        "SELECT canonical_table, COUNT(*), COALESCE(SUM(rows_quarantined),0) FROM "
        "asset.asset_reporting_quarantine_groups WHERE state='OPEN' AND canonical_table IN ("
        + ",".join(f"'{i['table']}'" for i in order) + ") GROUP BY canonical_table")).fetchall()
    report["control"]["open_quarantine"] = {r[0]: {"groups": r[1], "rows": r[2]} for r in rows}
    n = s.execute(text(
        "SELECT COUNT(*) FROM asset.asset_reporting_batches WHERE mode='HISTORICAL' "
        "AND canonical_table IN ("
        + ",".join(f"'{i['table']}'" for i in order) + ")")).scalar()
    report["control"]["historical_batches"] = n
    rows = s.execute(text(
        "SELECT canonical_table, state, COUNT(*) FROM asset.asset_reporting_batches "
        "WHERE mode='HISTORICAL' AND canonical_table IN ("
        + ",".join(f"'{i['table']}'" for i in order) + ") "
        "GROUP BY canonical_table, state")).fetchall()
    report["control"]["historical_batch_states"] = {
        f"{r[0]}|{r[1]}": r[2] for r in rows}
eng.dispose()

out = f"{STAGE}/b9_readback_20261027.json"
json.dump(report, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("READBACK_DONE", out, flush=True)
