# -*- coding: utf-8 -*-
"""S1c：74/84/67 对账。
输入：时间窗修改记录.md（74 行表）、view_versions.json（已清点 SQL）、Excel 统计表、view_registry(.clean).json
输出：view_inventory.csv（对象级版本链）+ reconciliation_74_84_67.json
"""
import csv
import json
import os
import re
import sys
from datetime import datetime

RUN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = r"D:\Users\Administrator\Desktop\三甲复审\6、数管中心三甲数据上报\数据接口规范+值域2.3"

# ---------- 1. 解析 时间窗修改记录.md 74 行表 ----------
md = open(os.path.join(PKG, "三甲完成视图", "时间窗修改记录.md"), encoding="utf-8").read()
rows_74 = []
for line in md.splitlines():
    m = re.match(r"^\|\s*([^|]+?)\s*\|\s*`([^`]+)`\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|$", line)
    if m and m.group(1) not in ("中文名",):
        rows_74.append({
            "cn_name": m.group(1).strip(), "view": m.group(2).strip(),
            "action": m.group(3).strip(), "note": m.group(4).strip(), "origin": m.group(5).strip(),
        })
print(f"时间窗修改记录.md 表行: {len(rows_74)}")
from collections import Counter
print("  action 分布:", dict(Counter(r["action"] for r in rows_74)))
print("  origin 来源分布:", dict(Counter(r["origin"].split("__")[0] for r in rows_74)))

# ---------- 2. Excel 统计表 ----------
try:
    import openpyxl
    wb = openpyxl.load_workbook(os.path.join(PKG, "三甲复审数据视图完成情况统计表.xlsx"), data_only=True)
    print("\nExcel sheets:", wb.sheetnames)
    xl_rows = []
    for sn in wb.sheetnames:
        ws = wb[sn]
        for i, row in enumerate(ws.iter_rows(values_only=True), 1):
            vals = [("" if v is None else str(v).strip()) for v in row]
            if any(vals):
                xl_rows.append({"sheet": sn, "row": i, "cells": vals})
    print(f"Excel 非空行: {len(xl_rows)}")
    # 打印表头与前几行结构
    hdr = [r for r in xl_rows if r["row"] <= 3]
    for r in hdr[:3]:
        print("  ", r["sheet"], r["row"], r["cells"][:12])
except Exception as ex:
    print("Excel 解析失败:", ex)
    xl_rows = []

# ---------- 3. 修正视图名提取 ----------
VV = json.load(open(os.path.join(RUN_DIR, "view_versions.json"), encoding="utf-8"))

PAT_ORA = re.compile(r"create\s+(?:or\s+replace\s+)?(?:force\s+)?view\s+((?:\"[^\"]+\"|[\w$#@.]+))", re.I)
PAT_MSS = re.compile(r"create\s+view\s+(?:\[(?:dbo|[\w$]+)\]\.)?\[?([\w$]+)\]?\s+as", re.I)

def norm_view(raw):
    parts = re.findall(r'"([^"]+)"|([\w$#@]+)', raw)
    segs = [a or b for a, b in parts]
    return ".".join(s for s in segs if s)

for f in VV["sql_files"]:
    full = os.path.join(PKG, f["relpath"])
    for enc in ("utf-8-sig", "utf-8", "gbk", "utf-16"):
        try:
            txt = open(full, encoding=enc).read()
            break
        except (UnicodeDecodeError, UnicodeError):
            txt = None
    if txt is None:
        continue
    names, seen = [], set()
    for m in PAT_ORA.finditer(txt):
        nm = norm_view(m.group(1))
        if nm and nm.upper() not in seen:
            seen.add(nm.upper()); names.append(nm)
    for m in PAT_MSS.finditer(txt):
        nm = norm_view(m.group(1))
        if nm and nm.upper() not in seen:
            seen.add(nm.upper()); names.append(nm)
    f["view_names2"] = names

# 方言判定
def dialect_of(txt_head):
    if "[dbo]" in txt_head or "ISNULL(" in txt_head or "N'" in txt_head[:3000]:
        return "sqlserver"
    return "oracle"

root_objs = {}
for f in VV["sql_files"]:
    for v in f.get("view_names2", []):
        root_objs.setdefault(v.upper(), {"name": v, "cats": set(), "files": []})
        root_objs[v.upper()]["cats"].add(f["category"])
        root_objs[v.upper()]["files"].append(f["relpath"])
print(f"\n修正后 distinct view objects: {len(root_objs)}")
zero = [f["relpath"] for f in VV["sql_files"] if f["category"].startswith("root") and not f.get("view_names2")]
print("root SQL 仍无视图名:", zero)

# ---------- 4. 对账 ----------
views_74 = {r["view"].upper(): r for r in rows_74}
root_main_objs = {k for k, v in root_objs.items() if "root_main" in v["cats"]}
jhemr_objs = {k for k, v in root_objs.items() if "root_jhemr_draft" in v["cats"]}
backup_objs = {k for k, v in root_objs.items() if "live_backup_20260914" in v["cats"]}

print(f"\n== 对账 ==")
print(f"74表视图: {len(views_74)}；root_main对象: {len(root_main_objs)}；jhemr草稿对象: {len(jhemr_objs)}；备份对象: {len(backup_objs)}")
print(f"74表 - root_main: {len(set(views_74) - root_main_objs)}")
for x in sorted(set(views_74) - root_main_objs):
    print("   缺文件:", x, "| action=", views_74[x]["action"], "| origin=", views_74[x]["origin"])
print(f"root_main - 74表: {len(root_main_objs - set(views_74))}")
for x in sorted(root_main_objs - set(views_74)):
    print("   多出:", x, sorted(root_objs[x]["files"]))

# ---------- 5. view_inventory.csv ----------
reg = json.load(open(os.path.join(PKG, "governance", "view_registry.json"), encoding="utf-8-sig"))
reg_by_view = {}
for v in reg.get("views", []):
    sv = (v.get("source_view") or "").upper()
    if sv:
        reg_by_view[sv] = v

inv = []
for k in sorted(root_objs):
    v = root_objs[k]
    r74 = views_74.get(k)
    jh = "root_jhemr_draft" in v["cats"]
    main_f = next((x for x in v["files"] if "root_main" in str(x)), None)
    # 版本类别
    cats = set(v["cats"])
    if "root_main" in cats and "live_backup_20260914" in cats:
        if jh:
            ver_cat = "local_modified_plus_draft"
        else:
            ver_cat = "local_modified"  # 工作副本基于活库备份并可能改上界
    elif jh and "root_jhemr_draft" in cats:
        ver_cat = "draft_jhemr"
    elif "history" in cats:
        ver_cat = "historical"
    else:
        ver_cat = "mixed:" + ",".join(sorted(cats))
    # 判断工作副本 vs 备份是否有差异（哈希）
    diff_backup = None
    if main_f:
        mf = next(x for x in VV["sql_files"] if x["relpath"] == main_f)
        bf = [x for x in VV["sql_files"] if x["category"] == "live_backup_20260914" and k.upper() in [n.upper() for n in x.get("view_names2", [])]]
        if bf:
            same = any(x["sha256"] == mf["sha256"] for x in bf)
            diff_backup = "same_as_backup" if same else "differs_from_backup"
    inv.append({
        "object": k,
        "display_name": v["name"],
        "in_74_table": "Y" if r74 else "",
        "action_74": r74["action"] if r74 else "",
        "origin_74": r74["origin"] if r74 else "",
        "version_category": ver_cat,
        "has_jhemr_draft": "Y" if jh else "",
        "root_vs_backup": diff_backup or "",
        "registry_name": (reg_by_view.get(k) or {}).get("name", ""),
        "files": " | ".join(v["files"]),
    })

csv_path = os.path.join(RUN_DIR, "view_inventory.csv")
with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(inv[0].keys()))
    w.writeheader(); w.writerows(inv)
print(f"\nview_inventory.csv 写出 {len(inv)} 对象")

# Excel 行另存
json.dump({"excel_rows": xl_rows, "rows_74": rows_74},
          open(os.path.join(RUN_DIR, "s1_excel_and_74rows.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("s1_excel_and_74rows.json 写出")
