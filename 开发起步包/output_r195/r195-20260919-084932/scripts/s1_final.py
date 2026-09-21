# -*- coding: utf-8 -*-
"""S1 终版对账：自包含提取（EDITIONABLE/引号分段/SQLServer/文件名回退）+ 74/Excel/备份/jhemr 对账。
产物：view_inventory.csv、view_versions.json(覆盖)、reconciliation_summary.json
"""
import csv
import json
import os
import re
from collections import Counter
from datetime import datetime

RUN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = r"D:\Users\Administrator\Desktop\三甲复审\6、数管中心三甲数据上报\数据接口规范+值域2.3"

SEG = r'(?:"[^"]+"|[\w$#@]+)'
PAT_ORA = re.compile(r"create\s+(?:or\s+replace\s+)?(?:force\s+)?(?:editionable\s+)?view\s+((?:%s)(?:\s*\.\s*(?:%s))*)" % (SEG, SEG), re.I)
PAT_MSS = re.compile(r"create\s+view\s+(?:\[[^\]]+\]\.)?\[?([\w$]+)\]?\s*+as", re.I)


def read_any(path):
    for enc in ("utf-8-sig", "utf-8", "gbk", "utf-16"):
        try:
            return open(path, encoding=enc).read(), enc
        except (UnicodeDecodeError, UnicodeError):
            continue
    return open(path, encoding="latin-1", errors="replace").read(), "latin-1"


def norm_view(raw):
    parts = re.findall(r'"([^"]+)"|([\w$#@]+)', raw)
    return ".".join((a or b) for a, b in parts if (a or b))


def fname_view(rel):
    stem = os.path.splitext(os.path.basename(rel))[0]
    return stem.split("_", 1)[1] if "_" in stem else None


def bare(n):
    return n.split(".")[-1].upper()


MAN = json.load(open(os.path.join(RUN_DIR, "source_manifest.json"), encoding="utf-8"))
D = json.load(open(os.path.join(RUN_DIR, "s1_excel_and_74rows.json"), encoding="utf-8"))
rows_74 = D["rows_74"]
xl_rows = D["excel_rows"]

sql_files = []
obj = {}  # bare -> dict
for e in MAN["files"]:
    if e["ext"] != ".sql":
        continue
    full = os.path.join(PKG, e["relpath"])
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
    if not names and re.match(r"\s*(select|with)\b", txt.strip(), re.I):
        nv = fname_view(e["relpath"])
        if nv:
            names = [nv]; src = "select_only_filename"
    dialect = "sqlserver" if (re.search(r"\[dbo\]|ISNULL\(", txt[:6000]) or ("N'" in txt[:4000] and "ISNULL" in txt[:8000])) else "oracle"
    rec = {"relpath": e["relpath"], "category": e["category"], "sha256": e["sha256"],
           "mtime": e["mtime"], "bytes": e["bytes"], "view_names": names, "name_source": src, "dialect": dialect}
    sql_files.append(rec)
    for v in names:
        o = obj.setdefault(bare(v), {"full_names": set(), "cats": set(), "files": [], "by_cat_sha": {}})
        o["full_names"].add(v.upper())
        o["cats"].add(e["category"])
        o["files"].append(e["relpath"])
        o["by_cat_sha"][e["category"]] = e["sha256"]

views_74 = {r["view"].upper(): r for r in rows_74}
root_main = {k for k, v in obj.items() if "root_main" in v["cats"]}
jhemr = {k for k, v in obj.items() if "root_jhemr_draft" in v["cats"]}
backup = {k for k, v in obj.items() if "live_backup_20260914" in v["cats"]}
hist = {k for k, v in obj.items() if "history" in v["cats"]}
govc = {k for k, v in obj.items() if "governance" in v["cats"]}

print(f"bare objects total={len(obj)} root_main={len(root_main)} jhemr={len(jhemr)} backup={len(backup)} history={len(hist)} governance={len(govc)}")
miss = set(views_74) - root_main
extra = root_main - set(views_74)
print(f"\n[74表 → 根层缺失 {len(miss)}]")
for x in sorted(miss):
    o = obj.get(x)
    print(f"  {x} | {views_74[x]['action']} | {views_74[x]['origin'][:50]} | 其他位置: {sorted(o['cats']) if o else '无'}")
print(f"\n[根层多余(不在74表) {len(extra)}]")
for x in sorted(extra):
    print(f"  {x} -> {obj[x]['files']}")

# 根层 vs 备份 哈希差（改上界验证）
diff_cnt = same_cnt = 0
for k in root_main & backup:
    o = obj[k]
    if o["by_cat_sha"].get("root_main") == o["by_cat_sha"].get("live_backup_20260914"):
        same_cnt += 1
    else:
        diff_cnt += 1
print(f"\n根层 vs 备份哈希: 相同={same_cnt} 不同={diff_cnt}")

# jhemr 草稿与基底
print(f"\n[jhemr 草稿 {len(jhemr)}]")
for j in sorted(jhemr):
    base = j.replace("_JHEMR", "")
    print(f"  {j} | 基底在root_main: {base in root_main}")

# Excel 对账
xl = [r for r in xl_rows if r["row"] >= 2]
xl_views = {}
for r in xl:
    c = r["cells"]
    if len(c) > 5 and c[5]:
        xl_views[c[5].upper()] = r
print(f"\nExcel 数据行={len(xl)} 视图名唯一={len(xl_views)} 完成情况分布={dict(Counter(r['cells'][6] for r in xl if len(r['cells'])>6))}")
print("Excel-74表:", sorted(set(xl_views) - set(views_74)))
print("74表-Excel:", sorted(set(views_74) - set(xl_views)))

# 写 view_inventory.csv
reg = json.load(open(os.path.join(PKG, "governance", "view_registry.json"), encoding="utf-8-sig"))
reg_by_view = {}
for v in reg.get("views", []):
    for key in ("source_view", "table"):
        sv = (v.get(key) or "").upper()
        if sv:
            reg_by_view.setdefault(bare(sv), v)

inv = []
for k in sorted(set(list(obj) + list(views_74))):
    v = obj.get(k)
    r74 = views_74.get(k)
    xl_r = xl_views.get(k)
    if v:
        cats = set(v["cats"])
        jh = "root_jhemr_draft" in cats
        hm, hb = "root_main" in cats, "live_backup_20260914" in cats
        if hm and hb:
            ver = "local_modified_vs_backup" if v["by_cat_sha"]["root_main"] != v["by_cat_sha"]["live_backup_20260914"] else "same_as_live_backup"
        elif hm:
            ver = "local_no_backup_pair"
        elif jh:
            ver = "draft_jhemr"
        elif "history" in cats:
            ver = "historical_only"
        else:
            ver = ",".join(sorted(cats))
        full = sorted(v["full_names"])
        files = v["files"]
    else:
        ver, full, files, jh = "no_local_sql", [], [], False
    inv.append({
        "object": k,
        "owner_qualified": ";".join(full),
        "in_74_table": "Y" if r74 else "",
        "action_74": r74["action"] if r74 else "",
        "origin_74": r74["origin"] if r74 else "",
        "excel_status": (xl_r["cells"][6] if xl_r and len(xl_r["cells"]) > 6 else ""),
        "excel_progress": (xl_r["cells"][10] if xl_r and len(xl_r["cells"]) > 10 else ""),
        "version_category": ver,
        "has_jhemr_draft": "Y" if jh else "",
        "registry_name": (reg_by_view.get(k) or {}).get("name", ""),
        "files": " | ".join(files),
    })

with open(os.path.join(RUN_DIR, "view_inventory.csv"), "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(inv[0].keys()))
    w.writeheader(); w.writerows(inv)

json.dump({"generated_at": datetime.now().isoformat(), "sql_files": sql_files},
          open(os.path.join(RUN_DIR, "view_versions.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

summary = {
    "generated_at": datetime.now().isoformat(),
    "counts": {
        "package_total_files": MAN["total_files"],
        "sql_files_total": len(sql_files),
        "bare_view_objects": len(obj),
        "root_main_files": sum(1 for s in sql_files if s["category"] == "root_main"),
        "root_jhemr_files": sum(1 for s in sql_files if s["category"] == "root_jhemr_draft"),
        "backup_files": sum(1 for s in sql_files if s["category"] == "live_backup_20260914"),
        "history_files": MAN["files"] and sum(1 for e in MAN["files"] if e["category"] == "history"),
        "objects_74_table": len(views_74),
        "74_missing_in_root": sorted(miss),
        "root_extra_not_in_74": sorted(extra),
        "root_vs_backup": {"same": same_cnt, "differs": diff_cnt},
        "excel_rows": len(xl), "excel_distinct_views": len(xl_views),
    },
}
json.dump(summary, open(os.path.join(RUN_DIR, "reconciliation_summary.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"\nview_inventory.csv {len(inv)} 行；reconciliation_summary.json 已写")
