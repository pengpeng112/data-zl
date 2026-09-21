# -*- coding: utf-8 -*-
"""S3c：字段血缘 jsonl + 值域候选 json。
血缘：view→target 列→表达式→源别名→源对象（部署系统）。
值域：V1.3 值域代码（目标标准）+ registry value_domain_fields + SQL CASE 映射（源码证据）。
"""
import json
import os
import re
from datetime import datetime

RUN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = json.load(open(os.path.join(RUN_DIR, "relation_candidates_raw.json"), encoding="utf-8"))

# ---- field_lineage.jsonl ----
n = 0
with open(os.path.join(RUN_DIR, "field_lineage.jsonl"), "w", encoding="utf-8") as f:
    for rec in RAW["files"]:
        amap = rec.get("alias_map") or {}
        for li in rec.get("lineage", []):
            expr = li["expr"]
            src_aliases = sorted({a.upper() for a in re.findall(r"\b([A-Za-z_][\w$#]*)\.", expr)
                                  if a.upper() in amap})
            src_objs = []
            for a in src_aliases:
                v = amap.get(a)
                if v and v.get("kind") == "table":
                    src_objs.append(f'{v.get("system")}|{v.get("schema")}|{v.get("table")}')
                elif v:
                    src_objs.append("(SUBQ)")
            f.write(json.dumps({
                "view": rec["view"], "file": rec["file"], "deploy_system": rec["deploy_system"],
                "target": li["target"], "expr": expr[:400],
                "source_aliases": src_aliases, "source_objects": src_objs,
                "derived": bool(re.search(r"case\s|nvl\s*\(|\|\||to_char|to_date|substr|decode\s*\(|row_number", expr, re.I)),
                "parser": "heuristic_v1",
            }, ensure_ascii=False) + "\n")
            n += 1
print("field_lineage.jsonl:", n)

# ---- value_domain_candidates.json ----
PKG = r"D:\Users\Administrator\Desktop\三甲复审\6、数管中心三甲数据上报\数据接口规范+值域2.3"
v13 = json.load(open(os.path.join(RUN_DIR, "v13_spec.json"), encoding="utf-8"))
reg = json.load(open(os.path.join(PKG, "governance", "view_registry.json"), encoding="utf-8-sig"))

v13_fields = []
for t in v13["tables"]:
    rows = t["rows"]
    ctx = " / ".join(t["context_before"][-2:])
    if len(rows) < 2:
        continue
    hdr = [h.strip() for h in rows[0]]
    if "标识符" not in hdr:
        continue
    try:
        ii = hdr.index("标识符"); di = hdr.index("值域代码"); ri = hdr.index("填报要求")
    except ValueError:
        continue
    for r in rows[1:]:
        if len(r) > di and r[di].strip():
            v13_fields.append({"dataset": ctx[:80], "field": (r[ii].strip() if len(r) > ii else ""),
                               "standard": r[di].strip(), "required": (r[ri].strip() if len(r) > ri else "")})

reg_fields = []
for v in reg.get("views", []):
    for vf in v.get("value_domain_fields", []):
        reg_fields.append({"view": v.get("source_view"), "field": vf.get("field"), "standard": vf.get("standard")})

# CASE 映射（源码字面量证据，按文件）
case_evidence = []
for rec in RAW["files"]:
    if rec["case_maps"]:
        case_evidence.append({"view": rec["view"], "file": rec["file"],
                              "maps_sample": rec["case_maps"][:15], "n_maps": len(rec["case_maps"])})

json.dump({
    "generated_at": datetime.now().isoformat(),
    "v13_target_fields": v13_fields,
    "registry_value_domain_fields": reg_fields,
    "case_map_evidence_files": case_evidence,
    "note": "目标标准码与源字段映射分开保存；确认前一律 pending；标准合法不代表源语义正确",
}, open(os.path.join(RUN_DIR, "value_domain_candidates.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"value_domain_candidates.json: v13字段 {len(v13_fields)}，registry {len(reg_fields)}，CASE证据文件 {len(case_evidence)}")
