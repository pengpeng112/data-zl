# -*- coding: utf-8 -*-
"""S6a：导入 payload 构建 + 生产基线 dry-run diff（只读，不写生产）。
- reviews payload：非 existing 候选 → asset_relation_reviews 草稿行（幂等键=两端身份+列）
- recipe payload：子查询 JOIN 边 + 视图级去重/聚合标志 → recipe_candidates.json
- diff：与平台正式关系+现有草稿按规范化键比对
产物：import_payload_reviews.json、recipe_candidates.json、import_diff.json
"""
import json
import os
from collections import Counter
from datetime import datetime

RUN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C = json.load(open(os.path.join(RUN_DIR, "relation_candidates.json"), encoding="utf-8"))["candidates"]
RAW = json.load(open(os.path.join(RUN_DIR, "relation_candidates_raw.json"), encoding="utf-8"))

SYS_NORM = {"HIS": "HIS_SOURCE"}


def nsys(s):
    return SYS_NORM.get(s, s) or ""


def review_row(c):
    (s1, sc1, t1, col1), (s2, sc2, t2, col2) = [tuple(x) for x in c["endpoints"]]
    # 定向：from=子表/多侧无从静态判定，保持发现方向（第一端为 from）
    ev = {
        "run_id": "r195-20260919-084932", "parser": "heuristic_v1",
        "source_files": c["files"], "view_names": c["view_names"],
        "join_type": c["join_type"], "blocks": c["blocks"],
        "qualifiers": c["qualifiers"][:4],
        "fragments": c["fragments"][:3],
    }
    return {
        "relation_scope": "r195_intake",
        "from_system_code": nsys(s1), "from_table": f"{sc1}.{t1}" if sc1 and sc1 != "NONE" else t1,
        "from_columns": "+".join(col1),
        "to_system_code": nsys(s2), "to_table": f"{sc2}.{t2}" if sc2 and sc2 != "NONE" else t2,
        "to_columns": "+".join(col2),
        "join_condition": " AND ".join(c["fragments"][:2])[:800],
        "relation_desc_cn": f'195三甲视图摄入候选（{c["intake_status"]}）',
        "business_logic_cn": ("涉及视图: " + ",".join(c["view_names"][:3]))[:500],
        "confidence": "C",
        "review_status": "draft",
        "source_evidence": json.dumps(ev, ensure_ascii=False)[:4000],
        "cand_id": c["cand_id"],
        "intake_status": c["intake_status"],
    }


payload = [review_row(c) for c in C if c["intake_status"] != "existing"]
json.dump({"generated_at": datetime.now().isoformat(), "target": "asset.asset_relation_reviews",
           "run_id": "r195-20260919-084932", "default_status": "draft",
           "rows": payload, "row_count": len(payload)},
          open(os.path.join(RUN_DIR, "import_payload_reviews.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("payload rows:", len(payload), dict(Counter(r["intake_status"] for r in payload)))

# recipe payload
recipes = []
subq = json.load(open(os.path.join(RUN_DIR, "subquery_join_edges.json"), encoding="utf-8"))
by_view = {}
for e in subq:
    by_view.setdefault(e["view"], []).append(e)
for rec in RAW["files"]:
    fl = rec["flags"]
    if not (fl.get("has_row_number") or fl.get("union_branches", 1) > 1 or fl.get("has_group_by")):
        continue
    recipes.append({
        "view": rec["view"], "file": rec["file"], "deploy_system": rec["deploy_system"],
        "sha256": rec["sha256"],
        "logic_flags": {"union_branches": fl.get("union_branches"), "row_number": fl.get("has_row_number"),
                        "group_by": fl.get("has_group_by"), "distinct": fl.get("has_distinct")},
        "qualifiers": rec.get("qualifiers", [])[:6],
        "subquery_joins": [{"lhs": e["lhs"], "rhs": e["rhs"], "kw": e["join_kw"]} for e in by_view.get(rec["view"], [])[:8]],
        "note": "配方草稿素材：完整键/条件/状态码/粒度需人工补齐后才可发布",
    })
json.dump({"generated_at": datetime.now().isoformat(), "recipes": recipes, "count": len(recipes)},
          open(os.path.join(RUN_DIR, "recipe_candidates.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("recipe candidates:", len(recipes))

# dry-run diff vs 生产基线（只读）
plat_keys = set()
for line in open(os.path.join(RUN_DIR, "platform_relations.txt"), encoding="utf-8"):
    p = line.rstrip("\n").split("|")
    if len(p) >= 13:
        k = tuple(sorted([(nsys(p[3]), p[6].upper(), p[7].upper()), (nsys(p[8]), p[11].upper(), p[12].upper())]))
        plat_keys.add(k)
for line in open(os.path.join(RUN_DIR, "platform_reviews.txt"), encoding="utf-8"):
    p = line.rstrip("\n").split("|")
    if len(p) >= 9:
        k = tuple(sorted([(nsys(p[1]), p[2].upper(), p[3].upper()), (nsys(p[4]), p[5].upper(), p[6].upper())]))
        plat_keys.add(k)

new, dup = [], 0
for r in payload:
    ft = r["from_table"].upper(); tt = r["to_table"].upper()
    def bare(x):
        return x.split(".")[-1]
    k = tuple(sorted([(r["from_system_code"], bare(ft), r["from_columns"].upper()),
                      (r["to_system_code"], bare(tt), r["to_columns"].upper())]))
    if k in plat_keys:
        dup += 1
    else:
        new.append(r["cand_id"])
diff = {
    "generated_at": datetime.now().isoformat(), "mode": "dry-run（生产零写入）",
    "baseline": {"asset_relations": 1329, "asset_relation_reviews": 560},
    "payload_rows": len(payload),
    "duplicate_with_baseline": dup,
    "new_rows": len(new),
    "new_cand_ids": new[:50],
    "existing_evidence_only": 15,
    "note": "重复=表级+列组合与平台已有边/草稿一致；exact-scope 限定差异未计入（草稿均带 r195_intake scope）",
}
json.dump(diff, open(os.path.join(RUN_DIR, "import_diff.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"dry-run diff: new={len(new)} dup={dup}")
