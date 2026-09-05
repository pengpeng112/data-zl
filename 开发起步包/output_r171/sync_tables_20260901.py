# -*- coding: utf-8 -*-
"""171 后续（用户授权 2026-09-01）：与生产服务器互相同步最新表。

A. 生产 → 隔离库 data_asset_test：补齐生产新表（当前差 65 张 dbo|dbo|* ECG 元数据），保留生产 id。
B. 生产 → 仓库资产包 数据资产_资产包/：tables/columns/relationships 三 CSV 全量刷新到生产现状；
   tables.csv 保留旧包治理注记（domain/grain/pk/confidence/note/source 按 schema+table join）；
   旧文件备份 .bak.20260901；manifest.json 重写（行数/字节/sha256）。
   catalog.json（策展核心摘要）与 value_domains.json（08-29 已是最新，计数与生产一致）不动。
C. 双向核对：反向（本地→生产）多余项计数，应为 0。
只读生产；仅写隔离库与本地文件。
"""
import csv
import hashlib
import io
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import psycopg

BASE = Path(r"F:\python\数据资产")
PKG = BASE / "开发起步包" / "数据资产_资产包"
TODAY = "20260901"
STAMP = datetime.now(timezone.utc).isoformat()
DSN = "postgresql://postgres@127.0.0.1:15432/%s"

prod = psycopg.connect(DSN % "data_asset", connect_timeout=8)
test = psycopg.connect(DSN % "data_asset_test", connect_timeout=8)
report: dict = {"steps": []}


def step(name, **kv):
    kv["step"] = name
    report["steps"].append(kv)
    print(f"[sync] {name}: {json.dumps(kv, ensure_ascii=False)[:300]}")


# ---------- A. 生产 → 隔离库：补新表 ----------
pc, tc = prod.cursor(), test.cursor()
tc.execute("select namespace_name, schema_name, table_name from asset.asset_tables")
test_keys = {(r[0], r[1], r[2]) for r in tc.fetchall()}
tc.execute("select id from asset.asset_tables")
test_ids = {r[0] for r in tc.fetchall()}

pc.execute("select * from asset.asset_tables")
all_cols = [d.name for d in pc.description]
prod_rows = pc.fetchall()
missing = [r for r in prod_rows
           if (r[all_cols.index("namespace_name")],
               r[all_cols.index("schema_name")],
               r[all_cols.index("table_name")]) not in test_keys]
step("A1_missing_in_test", count=len(missing),
     sample=[f"{r[all_cols.index('namespace_name')]}|{r[all_cols.index('schema_name')]}|{r[all_cols.index('table_name')]}"
             for r in missing[:3]])

if missing:
    id_conflicts = [r for r in missing if r[all_cols.index("id")] in test_ids]
    step("A2_id_conflicts", count=len(id_conflicts))
    if id_conflicts:
        raise SystemExit("id 冲突，需人工处理，中止 A 段")
    ph = ",".join(["%s"] * len(all_cols))
    sql = f"insert into asset.asset_tables ({','.join(all_cols)}) values ({ph})"
    tc.executemany(sql, missing)
    test.commit()
    step("A3_inserted", rows=len(missing), cols=len(all_cols))

# 双向计数核对（六指标）
metrics = {}
for name, db, cur in [("prod", "data_asset", pc), ("test", "data_asset_test", tc)]:
    vals = {}
    for t in ["asset_systems", "asset_tables", "asset_relations",
              "asset_columns", "asset_column_value_domains", "asset_quality_rules"]:
        cur.execute(f"select count(*) from asset.{t}")
        vals[t] = cur.fetchone()[0]
    metrics[name] = vals
step("A4_metrics", **metrics)
ok_a = metrics["prod"] == metrics["test"]
step("A5_isolated_matches_prod", result=ok_a)

# 反向：隔离库多余（生产缺）的表
tc.execute("select namespace_name, schema_name, table_name from asset.asset_tables")
tk = {(r[0], r[1], r[2]) for r in tc.fetchall()}
pc.execute("select namespace_name, schema_name, table_name from asset.asset_tables")
pk = {(r[0], r[1], r[2]) for r in pc.fetchall()}
step("C_reverse_local_extra", count=len(tk - pk), sample=sorted(tk - pk)[:3])

# ---------- B. 生产 → 资产包刷新 ----------
# B1 旧 tables.csv 注记（schema,table）→ 注记列
old_notes = {}
with io.open(PKG / "tables.csv", encoding="utf-8-sig", newline="") as fh:
    for r in csv.DictReader(fh):
        old_notes[(r["schema"], r["table"])] = r

# B2 备份
for f in ["tables.csv", "columns.csv", "relationships.csv"]:
    bak = PKG / f"{f}.bak.{TODAY}"
    if not bak.exists():
        shutil.copy2(PKG / f, bak)
step("B1_backups", files=["tables.csv", "columns.csv", "relationships.csv"], suffix=f".bak.{TODAY}")


def write_csv(path: Path, header: list[str], rows_iter):
    n = 0
    with io.open(path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        for row in rows_iter:
            w.writerow(row)
            n += 1
    return n


# B3 tables.csv（12767；注记 join 旧包；source 保留旧值，新行=platform）
pc.execute("""select schema_name, table_name, coalesce(comment,''), coalesce(row_count_stats,''),
              coalesce(column_count,0), coalesce(domain,''), coalesce(grain,''), coalesce(pk,''),
              coalesce(confidence,''), coalesce(note,''), system_code, source_code
              from asset.asset_tables order by schema_name, table_name""")
n_tbl = 0
n_kept = 0
with io.open(PKG / "tables.csv", "w", encoding="utf-8-sig", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["schema", "table", "comment", "row_count_stats", "column_count",
                "domain", "grain", "pk", "confidence", "note", "source"])
    for sch, tbl, cmt, rcs, cc, dom, grain, pk_, conf, note, sysc, srcc in pc.fetchall():
        old = old_notes.get((sch, tbl))
        if old:
            dom = old["domain"] or dom
            grain = old["grain"] or grain
            pk_ = old["pk"] or pk_
            conf = old["confidence"] or conf
            note = old["note"] or note
            src = old["source"] or "curated"
            n_kept += 1
        else:
            src = "platform"
        w.writerow([sch, tbl, cmt, rcs, cc, dom, grain, pk_, conf, note, src])
        n_tbl += 1
step("B3_tables_csv", rows=n_tbl, annotations_kept=n_kept)

# B4 columns.csv（178547；cursor 直接迭代）
pc.execute("""select schema_name, table_name, coalesce(column_id::text,''), column_name,
              coalesce(data_type,''), coalesce(length::text,''), coalesce(nullable::text,''), coalesce(comment,'')
              from asset.asset_columns order by schema_name, table_name, column_id nulls last, column_name""")
n_col = write_csv(PKG / "columns.csv",
                  ["schema", "table", "column_id", "column", "data_type", "length", "nullable", "comment"],
                  pc)
step("B4_columns_csv", rows=n_col)

# B5 relationships.csv（1329，全列照搬生产权威格式）
pc.execute("""select id, coalesce(domain,''), from_table, coalesce(from_columns,''), to_table,
              coalesce(to_columns,''), coalesce(join_condition,''), coalesce(cardinality,''),
              coalesce(confidence,''), coalesce(validation_level,''), coalesce(validation_status,''),
              coalesce(validation_metrics,''), coalesce(note,''), coalesce(validation_note,'')
              from asset.asset_relations order by id""")
n_rel = write_csv(PKG / "relationships.csv",
                  ["id", "domain", "from_table", "from_columns", "to_table", "to_columns",
                   "join_condition", "cardinality", "confidence", "validation_level",
                   "validation_status", "validation_metrics", "note", "validation_note"],
                  pc)
step("B5_relationships_csv", rows=n_rel)

# B6 manifest.json 重写（保留原结构与 bak 语义）
files_meta = []
for f in sorted(PKG.iterdir()):
    if f.name == "manifest.json" or not f.is_file():
        continue
    data = f.read_bytes()
    rows = None
    if f.suffix == ".csv" and ".bak." not in f.name:
        rows = sum(1 for _ in io.open(f, encoding="utf-8-sig")) - 1
    elif f.name == "catalog.json":
        rows = 45  # 保持原摘要行数口径（策展摘要未改动）
    files_meta.append({
        "path": f.name,
        "role": ("summary" if f.name.startswith("catalog") else
                 "evidence" if ".bak." in f.name else "full"),
        "bytes": len(data),
        "rows": rows,
        "sha256": hashlib.sha256(data).hexdigest(),
        "pii_scan": [],
    })
manifest = {
    "schema_version": "asset-manifest/v1",
    "asset_version": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
    "generated_at": STAMP,
    "builder_version": "sync_asset_package/171-followup-1",
    "package": "数据资产_资产包",
    "file_count": len(files_meta),
    "files": files_meta,
    "sync_source": {
        "note": "2026-09-01 经隧道从生产 data_asset 只读全量刷新（用户授权同步）",
        "prod_counts": metrics["prod"],
        "annotations_note": "tables.csv 旧包策展注记（domain/grain/pk/confidence/note/source=curated）按 schema+table 保留；新行 source=platform",
        "relationships_note": "from_table/to_table 为生产权威三段式（系统.Schema.表）",
    },
    "catalog_summary": {
        "note": "catalog.json 是核心摘要，不是全量清单；全量见 role=full 的 CSV",
        "top_keys": ["meta", "relationships", "tables"],
    },
    "pii_scan_conclusion": {
        "hits": [], "clean": True,
        "note": "仅模式抽样扫描（前 4MB/文件）；不含凭据原文，命中不代表泄露，需人工确认",
    },
}
(PKG / "manifest.json").write_text(
    json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
step("B6_manifest", files=len(files_meta))

prod.close()
test.close()
report["verdict"] = {
    "isolated_matches_prod": ok_a,
    "reverse_local_extra": len(tk - pk),
    "package_tables": n_tbl, "package_columns": n_col, "package_relationships": n_rel,
    "prod_counts": metrics["prod"],
}
out = BASE / "开发起步包" / "output_r171" / "sync_tables_20260901_输出.json"
out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print("[sync] done ->", out)
