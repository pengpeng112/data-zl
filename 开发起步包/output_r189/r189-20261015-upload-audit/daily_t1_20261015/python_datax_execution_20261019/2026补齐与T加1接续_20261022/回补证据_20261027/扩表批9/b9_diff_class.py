# -*- coding: utf-8 -*-
"""批9 裁定清单生成（收尾跑，只读）：对 25 表 HISTORICAL 批的 OPEN 隔离组：
- 暂存行 vs 目标行分块比对（IN 500/批），差异行数+差异列分布
  （参照 2026-10-24 ticket_diff_class 模式）；
- 输出 {表|error_code: {batches, groups, rows_quarantined, staged_rows,
  rows_compared_with_target_diff, column_distribution, not_in_target}}；
- 差异样例值脱敏：只记列名/行数/值形态（长度+是否相等），不落患者数据。
运行：docker exec -i data-asset-api python -" < b9_diff_class.py
"""
import json
import os
from collections import Counter

import oracledb
from sqlalchemy import create_engine, text

STAGE = "/opt/data-asset/t1-stage"
order = json.load(open(f"{STAGE}/b9_exec_order.json", encoding="utf-8"))
TABLES = [i["table"] for i in order]

eng = create_engine(os.environ["APP_DB_URL"])
with eng.connect() as s:
    rows = s.execute(text(
        "SELECT b.canonical_table, b.batch_id, q.group_key, q.error_code, "
        "q.rows_quarantined, q.reason FROM "
        "asset.asset_reporting_quarantine_groups q "
        "JOIN asset.asset_reporting_batches b ON b.batch_id = q.batch_id "
        "WHERE q.state = 'OPEN' AND b.canonical_table IN ("
        + ",".join(f"'{t}'" for t in TABLES) + ") AND b.batch_id LIKE '%.HISTORICAL.%' "
        "ORDER BY b.canonical_table, b.batch_id")).fetchall()
groups = [dict(zip(["table", "batch_id", "group_key", "error_code", "rows", "reason"], r))
          for r in rows]
print(f"OPEN groups on HISTORICAL batches: {len(groups)}", flush=True)

oracledb.init_oracle_client(lib_dir="/opt/oracle")
line = open("/etc/data-asset/credentials/sanjia_front_oracle_10_10_8_74.readonly").readline().strip()
u, _, p = line.partition(":")
tc = oracledb.connect(user=u, password=p, dsn="10.10.8.74:1521/orcl", tcp_connect_timeout=20)
tcur = tc.cursor()

import argparse  # noqa: E402
from scripts.reporting_ctl import (  # noqa: E402
    _assembly_inputs,
)
from app.services.reporting_pipeline.production_runtime import (  # noqa: E402
    ProductionAssembly,
)

CFG = "/opt/data-asset/t1-config"
GROUPS_CFG = {
    "b5": "freeze_batch5_v3.json|bindings_batch5.json",
    "b6": "freeze_batch6_v1.json|bindings_batch6.json",
    "b7": "freeze_batch7_v5.json|bindings_batch7.json",
}
grp_of = {i["table"]: i["group"] for i in order}
assemblies = {}
for g in set(grp_of.values()):
    freeze, bindings = GROUPS_CFG[g].split("|")
    a = argparse.Namespace(
        config=CFG, state_db=os.environ["APP_DB_URL"], stage_root=STAGE,
        bindings_file=f"{CFG}/{bindings}", runtime_config=f"{CFG}/{freeze}",
        allow_simulation=False, batch="", table=None, approval_ref="",
        executor_id="sql-target-apply-1")
    assemblies[g] = ProductionAssembly(_assembly_inputs(a), simulation=False)


def _eq(a, b):
    """归一化相等：None≡空串（批2 空串NULL语义）；数值按 float 比较
    （批2 float规整语义——裸 != 会把 Decimal/float 表示差异误报）。"""
    if a is None or b is None or a == "" or b == "":
        return (a is None or a == "") and (b is None or b == "")
    if isinstance(a, (int, float)) or isinstance(b, (int, float)):
        try:
            return float(a) == float(b)
        except (TypeError, ValueError):
            pass
    return a == b


def compare_batch(table: str, batch_id: str):
    asm = assemblies[grp_of[table]]
    repo = asm._repo()
    manifest = repo.select_manifest(batch_id)
    rows = list(asm.inputs.stage_store.iter_chunk_rows(batch_id, manifest.attempt_id))
    # 去重（同批多 attempt 的 chunk 叠代按 ID 稳定取首行）
    seen = {}
    for r in rows:
        d = dict(r)
        seen.setdefault(d.get("ID"), d)
    rows = list(seen.values())
    n_staged = len(rows)
    col_diff = Counter()
    rows_diff = 0
    not_in_target = 0
    in_target = 0
    CHUNK = 500
    for i in range(0, len(rows), CHUNK):
        chunk = rows[i:i + CHUNK]
        ids = [dict(r)["ID"] for r in chunk]
        ph = ",".join(f":b{j}" for j in range(len(ids)))
        tcur.execute(
            f"SELECT * FROM DBOPER.{table} WHERE ID IN ({ph})", ids)
        tcols = [d[0].upper() for d in tcur.description]
        tmap = {row[0]: dict(zip(tcols, row)) for row in tcur.fetchall() if row}
        for r in chunk:
            row = dict(r)
            tr = tmap.get(row.get("ID"))
            if tr is None:
                not_in_target += 1
                continue
            in_target += 1
            diffs = [c for c, v in row.items()
                     if c.upper() != "SYSTEM_TIME" and c.upper() in tr
                     and not _eq(v, tr[c.upper()])]
            if diffs:
                rows_diff += 1
                for c in diffs:
                    col_diff[c.upper()] += 1
    return {"staged_rows": n_staged, "in_target": in_target,
            "not_in_target": not_in_target,
            "rows_compared_with_target_diff": rows_diff,
            "column_distribution": dict(col_diff)}


out = {}
by_batch = {}
for g in groups:
    by_batch.setdefault((g["table"], g["batch_id"]), []).append(g)
for (table, bid), gl in sorted(by_batch.items()):
    key = f"{table}|{gl[0]['error_code']}"
    try:
        cmp_ = compare_batch(table, bid)
    except Exception as exc:  # noqa: BLE001
        cmp_ = {"error": f"stage read fail: {type(exc).__name__}"}
    entry = out.setdefault(key, {
        "batches": 0, "groups": 0, "rows_quarantined_declared": 0,
        "group_keys": [], **cmp_})
    entry["batches"] += 1
    entry["groups"] += len(gl)
    entry["rows_quarantined_declared"] += sum(g["rows"] for g in gl)
    entry["group_keys"] += [g["group_key"] for g in gl]
    for k in ("staged_rows", "in_target", "not_in_target",
              "rows_compared_with_target_diff"):
        if k in cmp_:
            entry[k] = entry.get(k, 0) + cmp_[k]
    for c, n in cmp_.get("column_distribution", {}).items():
        entry["column_distribution"][c] = entry["column_distribution"].get(c, 0) + n
    print(key, json.dumps({k: entry[k] for k in (
        "batches", "groups", "rows_quarantined_declared", "staged_rows",
        "in_target", "not_in_target", "rows_compared_with_target_diff",
        "column_distribution")}, ensure_ascii=False), flush=True)

tc.close()
json.dump(out, open(f"{STAGE}/b9_ticket_diff_class_20261028.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("DIFF_CLASS_DONE", flush=True)
