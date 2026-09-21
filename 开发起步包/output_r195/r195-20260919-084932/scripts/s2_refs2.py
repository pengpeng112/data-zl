# -*- coding: utf-8 -*-
"""S2c：修正版引用提取 + 物理身份解析。
修正：CTE 过滤、函数过滤、@DBLINK 拆分、视图名→74表 origin 回退、view-on-view 标记。
产物：object_refs.json(重写)、source_mapping.csv(重写)、cte_dblink_notes.json
"""
import csv
import json
import os
import re
from collections import defaultdict
from datetime import datetime

RUN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = r"D:\Users\Administrator\Desktop\三甲复审\6、数管中心三甲数据上报\数据接口规范+值域2.3"

VV = json.load(open(os.path.join(RUN_DIR, "view_versions.json"), encoding="utf-8"))
D = json.load(open(os.path.join(RUN_DIR, "s1_excel_and_74rows.json"), encoding="utf-8"))
rows_74 = {r["view"].upper(): r for r in D["rows_74"]}

ORIGIN2SYS = {
    "ods_8_216": "DATA_CENTER", "his_source_10_10_10_15": "HIS",
    "mobile_nursing_oracle_10_10_10_125": "MOBILE_NURSING",
    "pathology_sqlserver_10_10_9_41": "PATHOLOGY", "hrp_10_10_10_23": "HRP",
}
OWNER2SYS = {"ODS": "DATA_CENTER", "LUNA_MCS_SDSEY": "MOBILE_NURSING", "HISUSER": "HIS",
             "DBO": "PATHOLOGY", "HRPSEY656": "HRP", "C##NIS5": "INFECTION_SURVEILLANCE",
             "C##FXPT": "INFECTION_SURVEILLANCE"}

FUNCS = {"regexp_replace", "substr", "to_date", "to_char", "to_number", "nvl", "decode",
         "row_number", "rank", "dense_rank", "trunc", "add_months", "months_between",
         "last_day", "greatest", "least", "coalesce", "cast", "trim", "ltrim", "rtrim",
         "upper", "lower", "length", "instr", "replace", "translate", "abs", "round",
         "count", "sum", "min", "max", "avg", "listagg", "wm_concat", "extract",
         "current_date", "sysdate", "dual", "table", "value", "xmltable", "json_table"}


def read_any(path):
    for enc in ("utf-8-sig", "utf-8", "gbk", "utf-16"):
        try:
            return open(path, encoding=enc).read()
        except (UnicodeDecodeError, UnicodeError):
            continue
    return open(path, encoding="latin-1", errors="replace").read()


def strip_comments(txt):
    txt = re.sub(r"--[^\n]*", " ", txt)
    txt = re.sub(r"/\*.*?\*/", " ", txt, flags=re.S)
    return txt


def find_ctes(txt):
    """WITH a AS (...), b AS (...) 的 CTE 名（含嵌套括号内的 WITH）"""
    names = set()
    for m in re.finditer(r"(?:\bwith|,)\s*([\"A-Za-z_][\w$#]*)\s+as\s*\(", txt, re.I):
        names.add(m.group(1).upper())
    return names


def norm_ident(raw):
    parts = re.findall(r'"([^"]+)"|([\w$#@]+)', raw)
    return [(a or b) for a, b in parts if (a or b)]


def extract_refs(txt):
    txt2 = strip_comments(txt)
    ctes = find_ctes(txt2)
    refs = []
    for m in re.finditer(r"(?:\bfrom|\bjoin)\s+((?:\"[^\"]+\"|[\w$#]+)(?:\s*\.\s*(?:\"[^\"]+\"|[\w$#]+)){0,2})(?:\s*@\s*([\w$#]+))?", txt2, re.I):
        segs = norm_ident(m.group(1))
        dblink = (m.group(2) or "").upper()
        if not segs:
            continue
        first = segs[0].lower()
        if first in FUNCS or segs[0].upper() in ctes or first.startswith("("):
            continue
        if len(segs[-1]) <= 2 and len(segs) == 1:  # 单/双字母裸名多为别名残留
            continue
        refs.append({"ref": ".".join(s.strip() for s in segs), "dblink": dblink})
    seen, out = set(), []
    for r in refs:
        k = (r["ref"].upper(), r["dblink"])
        if k not in seen:
            seen.add(k); out.append(r)
    return out, ctes


def view_deploy(vname_upper):
    """视图 → (部署系统, 视图Owner, origin)"""
    r74 = rows_74.get(vname_upper)
    if r74 and r74["origin"]:
        src = r74["origin"].split(":", 1)[1].split("__", 1)[0] if ":" in r74["origin"] else ""
        if src in ORIGIN2SYS:
            return ORIGIN2SYS[src], None, r74["origin"]
        if r74["origin"].startswith("history:"):
            return "HISTORY_UNRESOLVED", None, r74["origin"]
    return "?", None, r74["origin"] if r74 else ""


result = {"generated_at": datetime.now().isoformat(), "files": []}
obj_files = defaultdict(list)
dblink_notes = defaultdict(set)
cte_all = set()
for f in VV["sql_files"]:
    if f["category"] not in ("root_main", "root_jhemr_draft"):
        continue
    full = os.path.join(PKG, f["relpath"])
    txt = read_any(full)
    refs, ctes = extract_refs(txt)
    cte_all |= ctes
    vowner = None
    for vn in f["view_names"]:
        if "." in vn:
            vowner = vn.split(".")[0].strip('"').upper()
            break
    # 视图部署系统：优先视图 Owner，其次 74表 origin
    dep_sys = OWNER2SYS.get(vowner) if vowner else None
    vname0 = (f["view_names"][0].split(".")[-1].strip('"').upper() if f["view_names"] else "")
    if not dep_sys or dep_sys == "?":
        s72, _, org = view_deploy(vname0)
        dep_sys = dep_sys or s72
    else:
        _, _, org = view_deploy(vname0)
    result["files"].append({
        "relpath": f["relpath"], "category": f["category"], "view_names": f["view_names"],
        "sha256": f["sha256"], "dialect": f["dialect"],
        "deploy_system": dep_sys, "origin_74": org, "refs": refs,
    })
    for r in refs:
        obj_files[(r["ref"].upper(), dep_sys or "?")].append(f["relpath"])
        if r["dblink"]:
            dblink_notes[f"{r['ref']}@{r['dblink']}"].add(dep_sys or "?")

json.dump(result, open(os.path.join(RUN_DIR, "object_refs.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
json.dump({"cte_names": sorted(cte_all),
           "dblink_refs": {k: sorted(v) for k, v in dblink_notes.items()}},
          open(os.path.join(RUN_DIR, "cte_dblink_notes.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

# 平台核对输入：(schema, table) 聚合
cands = {}
for f in result["files"]:
    dep = f["deploy_system"]
    vowner = None
    for vn in f["view_names"]:
        if "." in vn:
            vowner = vn.split(".")[0].strip('"').upper(); break
    SCHEMA_DEFAULT = {"DATA_CENTER": "ODS", "HIS": "HISUSER", "PATHOLOGY": "DBO",
                      "MOBILE_NURSING": "LUNA_MCS_SDSEY", "HRP": "HRPSEY656",
                      "INFECTION_SURVEILLANCE": "C##NIS5"}
    for r in f["refs"]:
        parts = [p.strip('"').upper() for p in r["ref"].split(".")]
        if len(parts) > 1:
            schema = parts[-2]
        else:
            schema = vowner or SCHEMA_DEFAULT.get(dep) or "NONE"
        tab = parts[-1]
        key = (schema, tab)
        c = cands.setdefault(key, {"ref_files": 0, "systems": set(), "draft": False, "dblink": r["dblink"]})
        c["ref_files"] += 1
        c["systems"].add(dep or "?")
        if f["category"] == "root_jhemr_draft":
            c["draft"] = True

vals = ",\n".join(f"('{s}','{t}')" for s, t in cands)
sql = f"""with q(schema_name,table_name) as (values
{vals}
)
select q.schema_name, q.table_name, t.system_code, t.source_code, t.column_count, t.include_status
from q join asset.asset_tables t on upper(t.schema_name)=q.schema_name and upper(t.table_name)=q.table_name
order by 1,2,3;"""
open(os.path.join(RUN_DIR, "sql", "s2_platform_check.sql"), "w", encoding="utf-8").write(sql)
json.dump({f"{s}|{t}": {**v, "systems": sorted(v["systems"])} for (s, t), v in cands.items()},
          open(os.path.join(RUN_DIR, "s2_cands.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"文件 {len(result['files'])}；候选对象 {len(cands)}；DBLink 引用 {len(dblink_notes)}：{list(dblink_notes)[:8]}")
print("CTE 名示例:", sorted(cte_all)[:15])
print("sql/s2_platform_check.sql 已更新")
