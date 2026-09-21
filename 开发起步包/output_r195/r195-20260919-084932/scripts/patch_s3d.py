# -*- coding: utf-8 -*-
"""子查询 JOIN 端点标记 + 边分级。"""
src = open("scripts/s3_parse.py", encoding="utf-8").read()
OLD = r'''            items = find_from_items("from" + seg)
            for it in items:
                ro = resolve_obj(it["obj"], {"deploy": deploy}, ctes)
                it["resolved"] = ro
                if it["alias"]:
                    alias2obj.setdefault(it["alias"].upper(), ro)'''
NEW = r'''            items = find_from_items("from" + seg)
            for it in items:
                ro = resolve_obj(it["obj"], {"deploy": deploy}, ctes)
                if it.get("subquery") and ro and ro.get("kind") == "table":
                    ro = {"kind": "subquery", "rep_table": ro["table"], "schema": ro["schema"],
                          "table": "(SUBQ:" + ro["table"] + ")", "system": ro["system"]}
                it["resolved"] = ro
                if it["alias"]:
                    alias2obj.setdefault(it["alias"].upper(), ro)'''
assert OLD in src, "OLD parse not found"
src = src.replace(OLD, NEW)
open("scripts/s3_parse.py", "w", encoding="utf-8").write(src)

src2 = open("scripts/s3_edges.py", encoding="utf-8").read()
OLD2 = r'''        for e in f["edges"]:
            if e["src"] == "correlated":
                continue
            la = resolve_side(e["lhs"], amap, f["deploy_system"])
            rb = resolve_side(e["rhs"], amap, f["deploy_system"])
            if not la or not rb or la["table"] == rb["table"]:
                unres += 1
                continue'''
NEW2 = r'''        for e in f["edges"]:
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
                continue'''
assert OLD2 in src2, "OLD edges not found"
src2 = src2.replace(OLD2, NEW2)
OLD3 = r'''    candidates = {}
    unres = 0'''
NEW3 = r'''    candidates = {}
    subq_edges = []
    unres = 0'''
assert OLD3 in src2
src2 = src2.replace(OLD3, NEW3)
OLD4 = r'''    # 分类
    out = []'''
NEW4 = r'''    json.dump(subq_edges, open(os.path.join(RUN_DIR, "subquery_join_edges.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # 分类
    out = []'''
assert OLD4 in src2
src2 = src2.replace(OLD4, NEW4)
OLD5 = r'''    print("candidates:", len(out), dict(Counter(x["intake_status"] for x in out)))
    print("unresolved side tokens:", unres)'''
NEW5 = r'''    print("candidates:", len(out), dict(Counter(x["intake_status"] for x in out)))
    print("subquery(join) recipe edges:", len(subq_edges))
    print("unresolved side tokens:", unres)'''
assert OLD5 in src2
src2 = src2.replace(OLD5, NEW5)
open("scripts/s3_edges.py", "w", encoding="utf-8").write(src2)
print("patched both")
