# -*- coding: utf-8 -*-
"""S1c-v2：74/84/67 对账（修正提取：EDITIONABLE/引号分段/文件名回退）。"""
import csv
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime

RUN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = r"D:\Users\Administrator\Desktop\三甲复审\6、数管中心三甲数据上报\数据接口规范+值域2.3"

SEG = r'(?:"[^"]+"|[\w$#@]+)'
PAT_ORA = re.compile(r"create\s+(?:or\s+replace\s+)?(?:force\s+)?(?:editionable\s+)?view\s+((?:%s)(?:\s*\.\s*(?:%s))*)" % (SEG, SEG), re.I)
PAT_MSS = re.compile(r"create\s+view\s+(?:\[[^\]]+\]\.)?\[?([\w$]+)\]?\s*+as", re.I)

VV = json.load(open(os.path.join(RUN_DIR, "view_versions.json"), encoding="utf-8"))
D = json.load(open(os.path.join(RUN_DIR, "s1_excel_and_74rows.json"), encoding="utf-8"))
rows_74 = D["rows_74"]
xl_rows = D["excel_rows"]


def norm_view(raw):
    parts = re.findall(r'"([^"]+)"|([\w$#@]+)', raw)
    segs = [a or b for a, b in parts]
    return ".".join(s for s in segs if s)


def read_any(path):
    for enc in ("utf-8-sig", "utf-8", "gbk", "utf-16"):
        try:
            return open(path, encoding=enc).read(), enc
        except (UnicodeDecodeError, UnicodeError):
            continue
    return open(path, encoding="latin-1", errors="replace").read(), "latin-1"


def fname_view(rel):
    """中文名_视图名.sql -> 视图名"""
    base = os.path.basename(rel)
    stem = os.path.splitext(base)[0]
    if "_" not in stem:
        return None
    return stem.split("_", 1)[1]


for f in VV["sql_files"]:
    full = os.path.join(PKG, f["relpath"])
    txt, enc = read_any(full)
    names, seen = [], set()
    for m in PAT_ORA.finditer(txt):
        nm = norm_view(m.group(1))
        if nm and nm.upper() not in seen:
            seen.add(nm.upper()); names.append(nm)
    for m in PAT_MSS.finditer(txt):
        nm = norm_view(m.group(1))
        if nm and nm.upper() not in seen:
            seen.add(nm.upper()); names.append(nm)
    src = "ddl"
    if not names and re.search(r"^\s*(select|with)\b", txt.strip(), re.I):
        nv = fname_view(f["relpath"])
        if nv:
            names = [nv]; src = "select_only_filename"
    f["view_names2"] = names
    f["name_source"] = src
    if "[dbo]" in txt[:2000] or "ISNULL(" in txt[:4000]:
        f["dialect"] = "sqlserver"
    elif "N'" in txt[:4000] and "ISNULL" in txt[:8000]:
        f["dialect"] = "sqlserver"
    else:
        f["dialect"] = "oracle"

root_objs = {}
for f in VV["sql_files"]:
    for v in f["view_names2"]:
        o = root_objs.setdefault(v.upper(), {"name": v, "cats": set(), "files": [], "hashes": {}})
        o["cats"].add(f["category"])
        o["files"].append(f["relpath"])
        o["hashes"][f["category"]] = f["sha256"]

views_74 = {r["view"].upper(): r for r in rows_74}
root_main_objs = {k for k, v in root_objs.items() if "root_main" in v["cats"]}
jhemr_objs = {k for k, v in root_objs.items() if "root_jhemr_draft" in v["cats"]}
backup_objs = {k for k, v in root_objs.items() if "live_backup_20260914" in v["cats"]}
hist_objs = {k for k, v in root_objs.items() if "history" in v["cats"]}

print(f"distinct view objects (all sql): {len(root_objs)}")
print(f"root_main={len(root_main_objs)} jhemr={len(jhemr_objs)} backup={len(backup_objs)} history={len(hist_objs)}")
no_name = [f["relpath"] for f in VV["sql_files"] if f["category"].startswith("root") and not f["view_names2"]]
print("root SQL 仍无对象名:", no_name)

print(f"\n74表({len(views_74)}) - root_main({len(root_main_objs)}): {len(set(views_74) - root_main_objs)}")
for x in sorted(set(views_74) - root_main_objs):
    print("  ", x, "|", views_74[x]["action"], "|", views_74[x]["origin"][:60])
print(f"root_main - 74表: {len(root_main_objs - set(views_74))}")
for x in sorted(root_main_objs - set(views_74)):
    print("  多出:", x, root_objs[x]["files"])
print(f"jhemr 对象与 74表/root_main 交集: {len(jhemr_objs & (set(views_74) | root_main_objs))}/{len(jhemr_objs)}")

# Excel 对账
xl = [r for r in xl_rows if r["row"] >= 2]
print(f"\nExcel 数据行: {len(xl)}")
done = [r for r in xl if r["cells"][6] == "完成"]
print("完成情况=完成:", len(done), "| 分布:", dict(Counter(r["cells"][6] for r in xl)))
cn_no_view = [r for r in xl if len(r["cells"]) > 6 and not r["cells"][5]]
print("视图名列为空:", len(cn_no_view))
# 与 74 表对照（按视图名）
xl_views = {}
for r in xl:
    if len(r["cells"]) > 5 and r["cells"][5]:
        xl_views[r["cells"][5].upper()] = r
print(f"Excel 视图名唯一: {len(xl_views)}")
print("Excel - 74表:", len(set(xl_views) - set(views_74)), sorted(set(xl_views) - set(views_74))[:10])
print("74表 - Excel:", len(set(views_74) - set(xl_views)), sorted(set(views_74) - set(xl_views))[:10])

# view_inventory.csv
reg = json.load(open(os.path.join(PKG, "governance", "view_registry.json"), encoding="utf-8-sig"))
reg_by_view = {}
for v in reg.get("views", []):
    sv = (v.get("source_view") or v.get("table") or "").upper()
    if sv:
        reg_by_view[sv] = v

inv = []
for k in sorted(set(list(root_objs) + list(views_74))):
    v = root_objs.get(k)
    r74 = views_74.get(k)
    if v:
        cats = set(v["cats"])
        jh = "root_jhemr_draft" in cats
        has_main = "root_main" in cats
        has_bak = "live_backup_20260914" in cats
        if has_main and has_bak:
            ver_cat = "local_modified(基于活库备份)" if v["hashes"].get("root_main") != v["hashes"].get("live_backup_20260914") else "same_as_live_backup"
        elif has_main:
            ver_cat = "local_edited(无备份对照)"
        elif jh:
            ver_cat = "draft_jhemr"
        else:
            ver_cat = ",".join(sorted(cats))
        files = v["files"]
    else:
        ver_cat = "no_local_file(仅见于74表/Excel)"
        jh = False
        files = []
    xl_r = xl_views.get(k)
    inv.append({
        "object": k,
        "in_74_table": "Y" if r74 else "",
        "action_74": r74["action"] if r74 else "",
        "origin_74": r74["origin"] if r74 else "",
        "excel_status": (xl_r["cells"][6] if xl_r else ""),
        "excel_progress": (xl_r["cells"][10] if xl_r else ""),
        "version_category": ver_cat,
        "has_jhemr_draft": "Y" if jh else "",
        "registry_name": (reg_by_view.get(k) or {}).get("name", ""),
        "files": " | ".join(files),
    })

with open(os.path.join(RUN_DIR, "view_inventory.csv"), "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(inv[0].keys()))
    w.writeheader(); w.writerows(inv)
print(f"\nview_inventory.csv 写出 {len(inv)} 对象")
json.dump({"reconciled_at": datetime.now().isoformat(), "objects": {k: {"cats": sorted(v["cats"]) if v else [], "files": v["files"] if v else []} for k, v in ((k, root_objs.get(k)) for k in root_objs)}},
          open(os.path.join(RUN_DIR, "view_object_index.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
