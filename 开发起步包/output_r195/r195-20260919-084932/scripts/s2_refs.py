# -*- coding: utf-8 -*-
"""S2a：从根层 SQL（67 主工作副本 + 17 jhemr 草稿）提取被引用对象清单。
输出：object_refs.json（每文件引用对象）+ object_refs_summary.csv（对象×文件覆盖）
"""
import json
import os
import re
from collections import defaultdict
from datetime import datetime

RUN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = r"D:\Users\Administrator\Desktop\三甲复审\6、数管中心三甲数据上报\数据接口规范+值域2.3"

VV = json.load(open(os.path.join(RUN_DIR, "view_versions.json"), encoding="utf-8"))

SEG = r'(?:"[^"]+"|[\w$#@]+)'
IDENT = r'(?:%s)(?:\s*\.\s*(?:%s)){0,2}' % (SEG, SEG)

# FROM/JOIN 后的对象引用（排除后续别名/关键字）；含旧式逗号 join 的 FROM 列表由 S3 细化，这里先抓主引用
PAT_REF = re.compile(
    r"(?:\bfrom|\bjoin)\s+((?:%s)(?:\s*\.\s*(?:%s)){0,2})" % (SEG, SEG), re.I | re.S)
STOPWORDS = {"select", "dual", "where", "group", "order", "having", "union", "minus", "intersect",
             "on", "left", "right", "inner", "outer", "full", "cross", "when", "case", "set", "values"}


def read_any(path):
    for enc in ("utf-8-sig", "utf-8", "gbk", "utf-16"):
        try:
            return open(path, encoding=enc).read()
        except (UnicodeDecodeError, UnicodeError):
            continue
    return open(path, encoding="latin-1", errors="replace").read()


def norm_ident(raw):
    parts = re.findall(r'"([^"]+)"|([\w$#@]+)', raw)
    return [ (a or b) for a, b in parts if (a or b) ]


def strip_sql_comments(txt):
    txt = re.sub(r"--[^\n]*", " ", txt)
    txt = re.sub(r"/\*.*?\*/", " ", txt, flags=re.S)
    return txt


def extract_refs(txt):
    txt2 = strip_sql_comments(txt)
    refs = []
    for m in re.finditer(r"(?:\bfrom|\bjoin)\s+(" + IDENT + r")", txt2, re.I):
        segs = norm_ident(m.group(1))
        if not segs:
            continue
        first = segs[0].lower()
        if first in STOPWORDS or first.startswith("("):
            continue
        refs.append(".".join(s.rstrip() for s in segs))
    # 去重保序
    seen, out = set(), []
    for r in refs:
        k = r.upper()
        if k not in seen:
            seen.add(k); out.append(r)
    return out


result = {"generated_at": datetime.now().isoformat(), "files": []}
obj_files = defaultdict(list)
obj_owner = {}
for f in VV["sql_files"]:
    if f["category"] not in ("root_main", "root_jhemr_draft"):
        continue
    full = os.path.join(PKG, f["relpath"])
    txt = read_any(full)
    refs = extract_refs(txt)
    result["files"].append({
        "relpath": f["relpath"], "category": f["category"], "view_names": f["view_names"],
        "sha256": f["sha256"], "dialect": f["dialect"], "refs": refs,
    })
    for r in refs:
        obj_files[r.upper()].append(f["relpath"])
        parts = r.split(".")
        obj_owner[r.upper()] = parts[:-1] if len(parts) > 1 else []

json.dump(result, open(os.path.join(RUN_DIR, "object_refs.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

owners = defaultdict(set)
for k, ow in obj_owner.items():
    owners[".".join(ow).upper() or "(无Owner)"].add(k)
print(f"文件: {len(result['files'])}；引用对象(规范化): {len(obj_files)}")
print("\n== Owner 分布 ==")
for ow, tabs in sorted(owners.items(), key=lambda x: -len(x[1])):
    print(f"  {ow:35s} {len(tabs):3d} 对象")

import csv
with open(os.path.join(RUN_DIR, "object_refs_summary.csv"), "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(["object_ref", "ref_count_files", "files"])
    for k in sorted(obj_files):
        w.writerow([k, len(obj_files[k]), " | ".join(obj_files[k])])
print("\nobject_refs_summary.csv 写出")
