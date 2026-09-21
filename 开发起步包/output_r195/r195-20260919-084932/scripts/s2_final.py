# -*- coding: utf-8 -*-
"""S2 终版：合并主查+补查 → source_mapping.csv；docx2006 vs 平台列 → schema_diff 输入。"""
import csv
import json
import os
import re
from collections import defaultdict

RUN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
cands = json.load(open(os.path.join(RUN_DIR, "s2_cands.json"), encoding="utf-8"))
res = defaultdict(list)
for fn in ("platform_check_result.txt",):
    for line in open(os.path.join(RUN_DIR, fn), encoding="utf-8"):
        p = line.rstrip("\n").split("|")
        if len(p) >= 6 and p[0] and p[0] != "NONE":
            res[(p[0], p[1])].append({"system": p[2], "source": p[3], "cols": p[4]})
# 补查（按裸名）：血透→HEMODIALYSIS、PITAYA→PATHOLOGY、HRP 裸名、HISUSER 裸名
BARE = {}
BARE_PATHS = ["platform_check_bare2.txt", "platform_check_bare3.txt"]
# 重新读取此前两个补查输出（由调用方落盘）
for fn in BARE_PATHS:
    p = os.path.join(RUN_DIR, fn)
    if not os.path.exists(p):
        continue
    for line in open(p, encoding="utf-8"):
        q = line.rstrip("\n").split("|")
        if len(q) >= 4:
            BARE.setdefault(q[0].upper(), []).append({"system": q[1], "schema": q[2], "source": q[3]})

objs = {}
for k, v in cands.items():
    s, t = k.split("|", 1)
    objs[(s, t)] = v

VIEW_ON_VIEW = {"V_EMR_ADMISSION_RECORD", "V_EMR_INSPECTION_TEST"}
# HISUSER 裸名在 HIS 源的解析（活库视图确证引用，schema 归属需同义词核验）
HIS_BARE_MAP = {
    "PAT_MASTER_INDEX": "MEDREC", "PAT_VISIT": "MEDREC", "DEPT_DICT": "COMM",
    "CLINIC_MASTER": "OUTPADM", "OUTP_ORDER_DESC": "OUTPBILL", "OUTP_TREAT_REC": "HIS(具体schema待核)",
    "SYS_EMPLOYEE": "仅ODS.HIS有行→疑经 synonym/dblink", "D07_EXAM_ITEM_MAP": "仅ODS.HIS有行→疑经 synonym/dblink",
    "CLINIC_ITEM_MAPPING": "HIS.COMM 与 ODS.ODS 均有行",
}

rows = []
for (s, t), x in sorted(objs.items()):
    hits = res.get((s, t), [])
    dep = ";".join(x["systems"])
    bare_hits = BARE.get(t, [])
    if x.get("dblink"):
        st, note = "cross_instance_dblink", f"经 DBLink {x['dblink']}（40号D类，身份/时点待验证）"
    elif t in VIEW_ON_VIEW:
        st, note = "view_ref", "视图引用视图；活库DDL在备份目录，平台元数据未收视图"
    elif any(h["system"] in dep.split(";") for h in hits):
        st, note = "confirmed", ""
    elif s == "HISUSER" and bare_hits:
        st = "synonym_or_schema_unresolved"
        note = "HIS源多schema命中: " + ";".join(f'{b["system"]}.{b["schema"]}' for b in bare_hits) + "；" + HIS_BARE_MAP.get(t, "")
    elif s == "NONE" and bare_hits and any(b["system"] == "HEMODIALYSIS" for b in bare_hits):
        st, note = "resolved_barename", "血透历史SQL→HEMODIALYSIS(10.10.10.88 public)"
    elif s == "DBO" and t == "PITAYA" and bare_hits:
        st, note = "resolved_barename", "PATHOLOGY.PITAYA.DBO（ODS BL.PITAYA 为镜像）"
    elif s == "HRPSEY656" and bare_hits:
        st, note = "resolved_barename", ";".join(f'{b["system"]}.{b["schema"]}' for b in bare_hits)
    elif t == "T_JBJL":
        st, note = "not_found", "jhemr草稿引用；平台无行，需活库核验CDA schema"
    else:
        st, note = "not_found_in_platform", "平台元数据无行（未采集/不存在/别名）"
    rows.append({
        "schema": s, "table": t, "deploy_system(s)": dep, "ref_files": x["ref_files"],
        "draft_ref": "Y" if x.get("draft") else "", "dblink": x.get("dblink", ""),
        "platform_hits": ";".join(f'{h["system"]}.{h["source"]}' for h in hits) or ";".join(f'{b["system"]}.{b["schema"]}' for b in bare_hits),
        "status": st, "note": note,
    })

with open(os.path.join(RUN_DIR, "source_mapping.csv"), "w", encoding="utf-8-sig", newline="") as fo:
    w = csv.DictWriter(fo, fieldnames=list(rows[0].keys()))
    w.writeheader(); w.writerows(rows)
from collections import Counter
print("source_mapping.csv:", len(rows), dict(Counter(r["status"] for r in rows)))

# ---- schema_diff 输入：confirmed/resolved 对象 + docx2006 表名匹配 ----
DOCX = json.load(open(os.path.join(RUN_DIR, "docx_2006_tables.json"), encoding="utf-8"))
docx_tables = {}
for t in DOCX["tables"]:
    for c in t["context_before"]:
        m = re.search(r"([A-Z][A-Z0-9_]{2,})\s*$", c.upper())
        if m:
            docx_tables.setdefault(m.group(1), {"seq": t["seq"], "rows": t["rows"]})
print("docx2006 可识别表名:", len(docx_tables))
want = [(r["schema"], r["table"]) for r in rows if r["status"] in ("confirmed", "resolved_barename")]
matched = [t for s, t in want if t in docx_tables]
print("待核对对象中命中 docx2006 表:", len(matched), "示例:", matched[:10])

json.dump({"want": want, "docx_matched": matched},
          open(os.path.join(RUN_DIR, "schema_diff_input.json"), "w", encoding="utf-8"))
