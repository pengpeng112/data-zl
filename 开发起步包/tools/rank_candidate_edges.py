# -*- coding: utf-8 -*-
"""
候选关系边聚合排序。

输入：
  - 数据资产_关系图谱/ods_view_join_edges.csv
  - 数据资产_资产包/relationships.csv

输出：
  - 数据资产_关系图谱/candidate_table_pairs_ranked.csv
  - 数据资产_关系图谱/candidate_field_pairs_ranked.csv
  - 数据资产_关系图谱/candidate_edges_ranked.json

用途：从静态解析的 ODS 视图 join 中，找出高频且尚未正式验证的表间关系。
"""
import csv
import json
import os
from collections import defaultdict

BASE = os.path.join(os.path.dirname(__file__), "..")
GRAPH = os.path.join(BASE, "数据资产_关系图谱")
ASSET = os.path.join(BASE, "数据资产_资产包")

EDGES = os.path.join(GRAPH, "ods_view_join_edges.csv")
FORMAL = os.path.join(ASSET, "relationships.csv")


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows, headers):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def norm_pair(a, b):
    return tuple(sorted([a.upper(), b.upper()]))


def norm_field_pair(ft, fc, tt, tc):
    left = (ft.upper(), fc.upper())
    right = (tt.upper(), tc.upper())
    return tuple(sorted([left, right]))


edges = read_csv(EDGES)
formal = read_csv(FORMAL)

formal_table_pairs = set()
formal_field_pairs = set()
for r in formal:
    ft, tt = r["from_table"], r["to_table"]
    formal_table_pairs.add(norm_pair(ft, tt))
    for fc in r["from_columns"].split("|"):
        for tc in r["to_columns"].split("|"):
            formal_field_pairs.add(norm_field_pair(ft, fc, tt, tc))

table_pairs = {}
field_pairs = {}

for e in edges:
    ft, tt = e["from_table"], e["to_table"]
    fc, tc = e["from_column"], e["to_column"]
    tp = norm_pair(ft, tt)
    fp = norm_field_pair(ft, fc, tt, tc)

    if tp not in table_pairs:
        table_pairs[tp] = {
            "table_pair": " <-> ".join(tp),
            "left_table": tp[0],
            "right_table": tp[1],
            "view_count": 0,
            "edge_count": 0,
            "views": set(),
            "field_pairs": set(),
            "in_formal_relationships": "Y" if tp in formal_table_pairs else "N",
        }
    table_pairs[tp]["edge_count"] += 1
    table_pairs[tp]["views"].add(e["view"])
    table_pairs[tp]["field_pairs"].add(f"{fc.upper()}={tc.upper()}")

    if fp not in field_pairs:
        (lt, lc), (rt, rc) = fp
        field_pairs[fp] = {
            "left_table": lt,
            "left_column": lc,
            "right_table": rt,
            "right_column": rc,
            "view_count": 0,
            "edge_count": 0,
            "views": set(),
            "conditions": set(),
            "in_formal_relationships": "Y" if fp in formal_field_pairs else "N",
        }
    field_pairs[fp]["edge_count"] += 1
    field_pairs[fp]["views"].add(e["view"])
    field_pairs[fp]["conditions"].add(e["condition"])

table_rows = []
for r in table_pairs.values():
    views = sorted(r.pop("views"))
    fps = sorted(r.pop("field_pairs"))
    r["view_count"] = len(views)
    r["views"] = "|".join(views[:50])
    r["field_pairs"] = "|".join(fps[:50])
    table_rows.append(r)

field_rows = []
for r in field_pairs.values():
    views = sorted(r.pop("views"))
    conds = sorted(r.pop("conditions"))
    r["view_count"] = len(views)
    r["views"] = "|".join(views[:50])
    r["conditions"] = "|".join(conds[:50])
    field_rows.append(r)

table_rows.sort(key=lambda r: (r["in_formal_relationships"] == "Y", -r["view_count"], -r["edge_count"], r["table_pair"]))
field_rows.sort(key=lambda r: (r["in_formal_relationships"] == "Y", -r["view_count"], -r["edge_count"], r["left_table"], r["right_table"]))

write_csv(
    os.path.join(GRAPH, "candidate_table_pairs_ranked.csv"),
    table_rows,
    ["table_pair", "left_table", "right_table", "view_count", "edge_count", "field_pairs", "in_formal_relationships", "views"],
)
write_csv(
    os.path.join(GRAPH, "candidate_field_pairs_ranked.csv"),
    field_rows,
    ["left_table", "left_column", "right_table", "right_column", "view_count", "edge_count", "in_formal_relationships", "conditions", "views"],
)

json.dump(
    {
        "meta": {
            "source": "ods_view_join_edges.csv",
            "formal_relationships": "数据资产_资产包/relationships.csv",
            "candidate_table_pair_count": len(table_rows),
            "candidate_field_pair_count": len(field_rows),
            "note": "按视图出现频次排序；in_formal_relationships=N 的高频关系优先验证。",
        },
        "table_pairs": table_rows,
        "field_pairs": field_rows,
    },
    open(os.path.join(GRAPH, "candidate_edges_ranked.json"), "w", encoding="utf-8"),
    ensure_ascii=False,
    indent=2,
)

print("候选表对:", len(table_rows))
print("候选字段对:", len(field_rows))
print("Top 未正式关系表对:")
for r in [x for x in table_rows if x["in_formal_relationships"] == "N"][:15]:
    print("  {table_pair} views={view_count} edges={edge_count} fields={field_pairs}".format(**r))
