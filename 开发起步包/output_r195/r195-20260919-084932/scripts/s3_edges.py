# -*- coding: utf-8 -*-
"""S3b：原始边 → 规范关系候选 + 平台查重 + 分级。
身份键：两端 (system|schema|table|cols)，方向不敏感但保持列配对。
分级：existing / existing_partial(review或正式子集) / candidate / partial / recipe_candidate / cte_internal / metadata_unresolved / rejected
产物：relation_candidates.json
"""
import hashlib
import json
import os
import re
from collections import defaultdict
from datetime import datetime

RUN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = json.load(open(os.path.join(RUN_DIR, "relation_candidates_raw.json"), encoding="utf-8"))

SYS_NORM = {"HIS": "HIS_SOURCE", "HIS_SOURCE": "HIS_SOURCE"}


def nsys(s):
    return SYS_NORM.get(s, s) or "?"


def load_platform():
    rel = []
    for line in open(os.path.join(RUN_DIR, "platform_relations.txt"), encoding="utf-8"):
        p = line.rstrip("\n").split("|")
        if len(p) >= 13:
            rel.append({
                "id": p[0], "from_system": nsys(p[3]), "from_schema": p[5], "from_table": p[6].upper(),
                "from_columns": p[7].upper(), "to_system": nsys(p[7 - 1 + 1]),  # placeholder fixed below
            })
    return rel


def load_platform2():
    """正确列序：id|rel_id|domain|from_system|from_source|from_schema|from_table|from_columns|to_system|to_source|to_schema|to_table|to_columns|join_condition|cardinality|confidence|validation_level|relation_layer"""
    rel = []
    for line in open(os.path.join(RUN_DIR, "platform_relations.txt"), encoding="utf-8"):
        p = line.rstrip("\n").split("|")
        if len(p) >= 17:
            rel.append({
                "id": p[0], "from_system": nsys(p[3]), "from_schema": p[5], "from_table": p[6].upper(),
                "from_columns": tuple(c.strip() for c in p[7].upper().replace("+", "+").split("+")),
                "to_system": nsys(p[8]), "to_schema": p[10], "to_table": p[11].upper(),
                "to_columns": tuple(c.strip() for c in p[12].upper().split("+")),
                "confidence": p[15], "layer": p[17] if len(p) > 17 else "",
            })
    for line in open(os.path.join(RUN_DIR, "platform_reviews.txt"), encoding="utf-8"):
        p = line.rstrip("\n").split("|")
        if len(p) >= 9:
            rel.append({
                "id": "R" + p[0], "from_system": nsys(p[1]), "from_schema": "", "from_table": p[2].upper(),
                "from_columns": tuple(c.strip() for c in p[3].upper().split("+")),
                "to_system": nsys(p[4]), "to_schema": "", "to_table": p[5].upper(),
                "to_columns": tuple(c.strip() for c in p[6].upper().split("+")),
                "confidence": p[7], "layer": "review:" + p[8],
            })
    return rel


def ep_key(system, schema, table, cols):
    return (nsys(system), (schema or "").upper(), table.upper(), tuple(cols))


def pair_key(a, b):
    return tuple(sorted([a, b]))


def resolve_side(token, alias_map, deploy):
    """lhs/rhs token → (system, schema, table, column) 或 None"""
    parts = [x for x in re.findall(r'"([^"]+)"|([\w$#]+)', token)]
    parts = [(a or b) for a, b in parts if (a or b)]
    if not parts:
        return None
    if len(parts) >= 3:  # owner.table.col 或 schema.obj.col
        return {"system": deploy, "schema": parts[-3].upper(), "table": parts[-2].upper(), "column": parts[-1].upper()}
    if len(parts) == 2:
        alias_or_owner, col = parts[0].upper(), parts[-1].upper()
        if alias_or_owner in alias_map and alias_map[alias_or_owner]:
            v = alias_map[alias_or_owner]
            if v.get("kind") == "table":
                return {"system": v["system"], "schema": v["schema"], "table": v["table"], "column": col}
            if v.get("kind") == "subquery":
                return {"system": v.get("system"), "schema": v.get("schema"),
                        "table": v.get("table") or ("(SUBQ:" + str(v.get("rep_table")) + ")"),
                        "column": col, "subquery": True}
            return None
        # Owner.table 限定形式但无别名：无法定列
        return None
    return None


def main():
    plat = load_platform2()
    plat_keys = defaultdict(list)
    for r in plat:
        a = ep_key(r["from_system"], r["from_schema"], r["from_table"], r["from_columns"])
        b = ep_key(r["to_system"], r["to_schema"], r["to_table"], r["to_columns"])
        plat_keys[pair_key(a, b)].append(r)

    # schema 归属辅助：平台行的 schema 常为空或全名；做表级索引
    tab_sys_schema = defaultdict(set)
    for r in plat:
        tab_sys_schema[r["from_table"]].add((nsys(r["from_system"]), r["from_schema"]))
        tab_sys_schema[r["to_table"]].add((nsys(r["to_system"]), r["to_schema"]))

    candidates = {}
    subq_edges = []
    unres = 0
    for f in RAW["files"]:
        amap = f.get("alias_map") or {}
        # 按 block+表对聚合列
        pair_cols = defaultdict(lambda: {"a_cols": [], "b_cols": [], "join_kw": None, "raws": []})
        for e in f["edges"]:
            if e["src"] == "correlated":
                continue
            la = resolve_side(e["lhs"], amap, f["deploy_system"])
            rb = resolve_side(e["rhs"], amap, f["deploy_system"])
            if not la or not rb or la["table"] == rb["table"]:
                unres += 1
                continue
            if "(SUBQ:" in la["table"] or "(SUBQ:" in rb["table"]:
                subq_edges.append({"file": f["file"], "view": f["view"], "block": e["block"],
                                   "join_kw": e["join_kw"], "lhs": e["lhs"], "rhs": e["rhs"],
                                   "raw": e["raw"]})
                continue
            k = (e["block"], (la["system"], la["schema"], la["table"]), (rb["system"], rb["schema"], rb["table"]))
            pc = pair_cols[k]
            pc["a_cols"].append(la["column"]); pc["b_cols"].append(rb["column"])
            pc["join_kw"] = pc["join_kw"] or e["join_kw"]
            pc["raws"].append(e["raw"])
        for (blk, A, B), pc in pair_cols.items():
            # 去重保持顺序的列
            def uniq(xs):
                seen, out = set(), []
                for x in xs:
                    if x not in seen:
                        seen.add(x); out.append(x)
                return out
            ac, bc = uniq(pc["a_cols"]), uniq(pc["b_cols"])
            ea = ep_key(A[0], A[1], A[2], ac)
            eb = ep_key(B[0], B[1], B[2], bc)
            pk = pair_key(ea, eb)
            ck = hashlib.sha1(json.dumps([list(x) for x in pk], ensure_ascii=False).encode()).hexdigest()[:16]
            cand = candidates.setdefault(ck, {
                "cand_id": "c195-" + ck,
                "endpoints": [list(x) for x in pk],
                "join_type": pc["join_kw"], "fragments": [], "files": set(), "view_names": set(),
                "blocks": set(),
            })
            cand["fragments"].extend(pc["raws"][:3])
            cand["files"].add(f["file"])
            cand["view_names"].add(f["view"])
            cand["blocks"].add(blk)

        # cte 相关子查询边保留为 lineage 证据（不进候选）
    json.dump(subq_edges, open(os.path.join(RUN_DIR, "subquery_join_edges.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # 分类
    out = []
    for ck, c in candidates.items():
        pk = tuple(tuple(x) for x in c["endpoints"])
        hits = plat_keys.get(pk, [])
        # 表级（忽略列）命中检查：正式键是候选键子集 → 组合键可能遗漏
        (s1, sc1, t1, col1), (s2, sc2, t2, col2) = pk
        tab_hits = []
        for r in plat:
            ra = ep_key(r["from_system"], r["from_schema"], r["from_table"], r["from_columns"])
            rb = ep_key(r["to_system"], r["to_schema"], r["to_table"], r["to_columns"])
            rp = pair_key(ra, rb)
            if {t1, t2} == {r["from_table"], r["to_table"]} and nsys(r["from_system"]) in {s1, s2} and nsys(r["to_system"]) in {s1, s2}:
                tab_hits.append((rp == pk, r))
        if hits:
            status = "existing"
        elif any(eq for eq, r in tab_hits):
            status = "existing"
        elif tab_hits:
            status = "partial_or_keysubset"
        else:
            status = "candidate"
        quals = []
        for f in RAW["files"]:
            if f["file"] in c["files"]:
                quals.extend(f.get("qualifiers", [])[:6])
        recipe = any(f["flags"].get("has_row_number") or f["flags"].get("union_branches", 1) > 1 or f["flags"].get("has_group_by")
                     for f in RAW["files"] if f["file"] in c["files"])
        if status == "candidate" and recipe:
            status = "recipe_candidate"
        out.append({
            "cand_id": c["cand_id"],
            "endpoints": c["endpoints"],
            "join_type": c["join_type"],
            "n_columns_pair": min(len(pk[0][3]), len(pk[1][3])),
            "fragments": c["fragments"][:3],
            "files": sorted(c["files"]),
            "view_names": sorted(v for v in c["view_names"] if v),
            "blocks": sorted(c["blocks"]),
            "qualifiers": quals[:6],
            "intake_status": status,
            "existing_platform_ids": [r["id"] for r in hits][:5],
            "confidence": "C" if status != "existing" else "C(补证据)",
            "parser": "heuristic_v1",
        })
    from collections import Counter
    print("candidates:", len(out), dict(Counter(x["intake_status"] for x in out)))
    print("subquery(join) recipe edges:", len(subq_edges))
    print("unresolved side tokens:", unres)
    json.dump({"generated_at": datetime.now().isoformat(), "candidates": out},
              open(os.path.join(RUN_DIR, "relation_candidates.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
