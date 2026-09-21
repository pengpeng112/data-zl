# -*- coding: utf-8 -*-
"""S1b：SQL 视图对象级清点与版本对账。
- 按 ext×category 细分统计
- 每个 SQL 提取 CREATE [OR REPLACE] [FORCE] VIEW 对象名（含 Owner 前缀）
- 建立对象名 → 各版本（root/backup/history/governance）链
- 与 governance/view_registry(.clean).json 对照
产物：view_versions.json + 控制台摘要
"""
import json
import os
import re
import sys
from collections import defaultdict, Counter
from datetime import datetime

RUN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = json.load(open(os.path.join(RUN_DIR, "source_manifest.json"), encoding="utf-8"))

VIEW_PAT = re.compile(
    r"create\s+(?:or\s+replace\s+)?(?:force\s+)?view\s+([\"A-Za-z0-9_$@.\\]+)", re.IGNORECASE)


def read_text(f):
    for enc in ("utf-8-sig", "utf-8", "gbk", "utf-16"):
        try:
            return open(f, encoding=enc).read(), enc
        except (UnicodeDecodeError, UnicodeError):
            continue
    return open(f, encoding="latin-1", errors="replace").read(), "latin-1"


def main():
    pkg_root = MANIFEST["root"]
    rows = []
    for e in MANIFEST["files"]:
        if e["ext"] != ".sql":
            continue
        full = os.path.join(pkg_root, e["relpath"])
        txt, enc = read_text(full)
        views = VIEW_PAT.findall(txt)
        # 去重保序
        seen, vv = set(), []
        for v in views:
            v2 = v.strip().strip('"').rstrip('.').rstrip("\\")
            k = v2.upper()
            if k not in seen:
                seen.add(k)
                vv.append(v2)
        rows.append({
            "relpath": e["relpath"], "category": e["category"], "sha256": e["sha256"],
            "mtime": e["mtime"], "bytes": e["bytes"],
            "view_names": vv, "n_views": len(vv),
        })

    # 1) ext×category 汇总
    ext_cat = Counter((e["category"], e["ext"]) for e in MANIFEST["files"])
    print("== category × ext (SQL/TXT/MD/JSON) ==")
    for (cat, ext), n in sorted(ext_cat.items()):
        if ext in {".sql", ".txt", ".md", ".json"}:
            print(f"  {cat:28s} {ext:6s} {n}")

    # 2) 视图对象 → 版本链
    by_view = defaultdict(list)
    for r in rows:
        for v in r["view_names"]:
            by_view[v.upper()].append(r)
    multi = {k: v for k, v in by_view.items() if len({x["relpath"] for x in v}) > 1}
    print(f"\nSQL files: {len(rows)}; distinct view objects: {len(by_view)}; multi-version objects: {len(multi)}")

    # 3) 根层 vs 备份 vs jhemr 对象集合
    def objs_of(cat):
        s = set()
        for r in rows:
            if r["category"] == cat:
                s.update(v.upper() for v in r["view_names"])
        return s

    root_main, jhemr, backup, hist = objs_of("root_main"), objs_of("root_jhemr_draft"), objs_of("live_backup_20260914"), objs_of("history")
    print(f"root_main objects: {len(root_main)}; jhemr draft objects: {len(jhemr)}; backup objects: {len(backup)}; history objects: {len(hist)}")
    print(f"root_main ∪ jhemr: {len(root_main | jhemr)}")
    print(f"root_main - backup: {len(root_main - backup)} -> {sorted(root_main - backup)[:20]}")
    print(f"backup - root_main: {len(backup - root_main)} -> {sorted(backup - root_main)[:20]}")
    print(f"jhemr - backup: {len(jhemr - backup)}")

    # 根层含多视图/无视图文件
    odd = [r for r in rows if r["category"] in ("root_main", "root_jhemr_draft") and r["n_views"] != 1]
    print(f"\nroot SQL with !=1 view: {len(odd)}")
    for r in odd[:15]:
        print(f"  [{r['n_views']}] {r['relpath']} {r['view_names'][:4]}")

    # 4) 注册表对照
    reg, regc = None, None
    for cand in ("governance/view_registry.json", "governance/view_registry_clean.json"):
        p = os.path.join(pkg_root, cand)
        if os.path.exists(p):
            d = json.load(open(p, encoding="utf-8-sig"))
            names = set()
            for v in d.get("views", []):
                nm = (v.get("view_name") or v.get("name") or "").upper()
                if nm:
                    names.add(nm)
            if "clean" in cand:
                regc = names
            else:
                reg = names
            print(f"\n{cand}: {len(d.get('views', []))} views, distinct names {len(names)}")
    if reg:
        print("registry - (root∪jhemr∪backup):", len(reg - (root_main | jhemr | backup)), sorted(reg - (root_main | jhemr | backup))[:15])
        print("(root∪jhemr) - registry:", len((root_main | jhemr) - reg), sorted((root_main | jhemr) - reg)[:15])

    out = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "sql_files": rows,
        "view_object_index": {k: [x["relpath"] for x in v] for k, v in sorted(by_view.items())},
    }
    with open(os.path.join(RUN_DIR, "view_versions.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("\nwritten view_versions.json")


if __name__ == "__main__":
    sys.exit(main())
