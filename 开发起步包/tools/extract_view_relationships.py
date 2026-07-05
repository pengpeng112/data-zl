# -*- coding: utf-8 -*-
"""
解析 ODS 视图 DDL 与 HIS 表分类。

输入：08_数据中心元数据快照.json
输出：数据资产_关系图谱/
  - ods_view_dependencies.csv     视图引用的表/别名
  - ods_view_join_edges.csv       从 DDL 条件中抽取的疑似表间关联
  - his_table_classification.csv  HIS 273 表主题分类
  - graph_seed.json               程序读取的图谱种子

注意：这是静态 SQL 解析，结果是“图谱种子”，不是数据库实测验证。
"""
import csv
import json
import os
import re
from collections import defaultdict

BASE = os.path.join(os.path.dirname(__file__), "..")
META = os.path.join(BASE, "08_数据中心元数据快照.json")
OUT = os.path.join(BASE, "数据资产_关系图谱")
os.makedirs(OUT, exist_ok=True)

meta = json.load(open(META, encoding="utf-8"))
schemas = meta["schemas"]


def strip_quotes(s):
    return s.strip().strip('"').upper()


def split_ref(ref):
    ref = ref.strip().rstrip(",")
    if ref.startswith("("):
        return None
    parts = [strip_quotes(x) for x in ref.split(".")]
    if len(parts) == 2:
        return parts[0], parts[1]
    if len(parts) == 1:
        return "UNKNOWN", parts[0]
    return None


def normalize_sql(sql):
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.S)
    sql = re.sub(r"--.*?(\r?\n|$)", " ", sql)
    sql = re.sub(r"\s+", " ", sql)
    return sql


TABLE_REF_RE = re.compile(
    r"\b(?:FROM|JOIN)\s+((?:\"[^\"]+\"\.)?\"[^\"]+\"|[A-Za-z0-9_\u4e00-\u9fff]+(?:\.[A-Za-z0-9_\u4e00-\u9fff]+)?)"
    r"(?:\s+(?:AS\s+)?([A-Za-z_][A-Za-z0-9_]*))?",
    re.I,
)

EQ_RE = re.compile(
    r"\b([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z0-9_\u4e00-\u9fff]+)\s*=\s*([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z0-9_\u4e00-\u9fff]+)\b",
    re.I,
)

KEYWORD_ALIASES = {
    "WHERE", "LEFT", "RIGHT", "FULL", "INNER", "OUTER", "JOIN", "ON", "GROUP", "ORDER", "UNION", "CONNECT", "START",
    "CROSS", "WHERE", "WITH", "SELECT", "AND", "OR", "HAVING", "MODEL", "PIVOT",
}


def parse_view(view_name, ddl):
    sql = normalize_sql(ddl)
    aliases = {}
    deps = []

    for m in TABLE_REF_RE.finditer(sql):
        ref = split_ref(m.group(1))
        if not ref:
            continue
        schema, table = ref
        alias = m.group(2)
        if alias and alias.upper() in KEYWORD_ALIASES:
            alias = None
        alias_key = alias.upper() if alias else table
        aliases[alias_key] = (schema, table)
        deps.append({
            "view": view_name,
            "schema": schema,
            "table": table,
            "alias": alias_key,
        })

    edges = []
    seen = set()
    for a1, c1, a2, c2 in EQ_RE.findall(sql):
        a1u, a2u = a1.upper(), a2.upper()
        if a1u not in aliases or a2u not in aliases:
            continue
        s1, t1 = aliases[a1u]
        s2, t2 = aliases[a2u]
        if (s1, t1) == (s2, t2):
            continue
        # 固定方向，方便去重；保留原始条件
        left = f"{s1}.{t1}"
        right = f"{s2}.{t2}"
        key = (view_name, left, c1.upper(), right, c2.upper())
        rev = (view_name, right, c2.upper(), left, c1.upper())
        if key in seen or rev in seen:
            continue
        seen.add(key)
        edges.append({
            "view": view_name,
            "from_table": left,
            "from_column": c1.upper(),
            "to_table": right,
            "to_column": c2.upper(),
            "condition": f"{a1u}.{c1.upper()} = {a2u}.{c2.upper()}",
            "source": "ods_view_ddl_static_parse",
            "confidence": "static",
        })
    return deps, edges


CURATED_DOMAIN = {
    "PAT_MASTER_INDEX": "患者主数据",
    "PAT_VISIT": "就诊",
    "DIAGNOSIS": "诊断",
    "DIAGNOSIS_TYPE_DICT": "诊断字典",
    "DEPT_DICT": "科室字典",
    "STAFF_DICT": "人员字典",
    "PATS_IN_HOSPITAL": "就诊",
    "ORDERS": "医嘱",
    "CLINIC_MASTER": "门诊",
    "OUTP_MR": "门诊",
    "OUTP_RCPT_MASTER": "门诊费用",
    "OUTP_BILL_ITEMS": "门诊费用",
    "INP_SETTLE_MASTER": "住院费用",
    "INP_BILL_DETAIL": "住院费用",
    "LAB_TEST_MASTER": "检验",
    "LAB_TEST_ITEMS": "检验",
    "LAB_RESULT": "检验",
    "LIS_EXAMINE_ITEM_MAP": "检验映射",
    "EXAM_MASTER": "检查",
    "EXAM_REPORT": "检查",
    "OPERATION": "手术",
}


def classify_his_table(table_name, referenced_views=None):
    name = table_name.upper()
    if name in CURATED_DOMAIN:
        return CURATED_DOMAIN[name], "curated_exact"
    referenced_views = referenced_views or []
    view_text = " ".join(referenced_views).upper()
    view_rules = [
        ("电子病历", ["EMR_HOS", "CDR_EMR", "EPR", "JHMR"]),
        ("病案首页", ["V_EMR_ICH", "INPUT_CASE_FIRP"]),
        ("诊断", ["DIAG", "DIAGNOSIS"]),
        ("医嘱", ["ORDER", "DOC_ORDER", "ZYYZ"]),
        ("检验", ["LAB", "INSPECTION", "JY_", "ESBHL_INSPECTION"]),
        ("检查/影像", ["EXAM", "CHECK", "PACS", "IMAGE", "XD"]),
        ("手术", ["OPERA", "OPER", "SURG", "ANE"]),
        ("费用", ["FEE", "CHARGE", "BILL"]),
        ("门诊", ["OUTPATIENT", "OUT_PRESCRIPTION", "MZ"]),
        ("护理", ["NUR", "VS_MEASURE", "INPUT_OUTPUT"]),
    ]
    for domain, keys in view_rules:
        if any(k in view_text for k in keys):
            return domain, "ods_view_context:" + "/".join(keys)
    rules = [
        ("患者/就诊", ["PAT", "VISIT", "INP_NO", "CLINIC"]),
        ("诊断", ["DIAG"]),
        ("医嘱", ["ORDER", "ORDERS"]),
        ("检验", ["LAB", "TEST"]),
        ("检查/影像", ["EXAM", "PACS", "IMAGE", "REPORT"]),
        ("手术", ["OPER", "SURG"]),
        ("药品", ["DRUG", "PHARM", "MEDICINE"]),
        ("费用", ["BILL", "FEE", "CHARGE", "PRICE", "COST", "PAY", "SETTLE", "RCPT"]),
        ("科室/组织", ["DEPT", "WARD", "BED", "ROOM"]),
        ("人员", ["STAFF", "EMP", "DOCTOR", "NURSE", "USER"]),
        ("字典", ["DICT", "CODE", "MAP"]),
        ("输血/血液", ["BLOOD", "TRANSFUSION"]),
        ("物资/耗材", ["MATERIAL", "SUPPLY", "ITEM"]),
    ]
    for domain, keys in rules:
        if any(k in name for k in keys):
            return domain, "name_pattern:" + "/".join(keys)
    return "未分类", "no_rule"


def write_csv(path, rows, headers):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        for row in rows:
            w.writerow(row)


all_deps = []
all_edges = []
for view_name, data in schemas.get("ODS", {}).get("views", {}).items():
    deps, edges = parse_view(view_name, data.get("ddl", ""))
    all_deps.extend(deps)
    all_edges.extend(edges)

# 去重依赖
dep_key = set()
deps_unique = []
for d in all_deps:
    k = (d["view"], d["schema"], d["table"], d["alias"])
    if k not in dep_key:
        dep_key.add(k)
        deps_unique.append(d)

his_rows = []
his_ref_views = defaultdict(set)
for d in deps_unique:
    if d["schema"] == "HIS":
        his_ref_views[d["table"]].add(d["view"])

for table_name, table in schemas.get("HIS", {}).get("tables", {}).items():
    views = sorted(his_ref_views.get(table_name, []))
    domain, reason = classify_his_table(table_name, views)
    his_rows.append({
        "schema": "HIS",
        "table": table_name,
        "domain": domain,
        "classify_reason": reason,
        "referenced_by_ods_view_count": len(views),
        "referenced_by_ods_views": "|".join(views[:20]),
        "row_count_stats": table.get("num_rows_stats", -1),
        "column_count": len(table.get("columns", [])),
        "comment": table.get("comment", ""),
    })

write_csv(
    os.path.join(OUT, "ods_view_dependencies.csv"),
    deps_unique,
    ["view", "schema", "table", "alias"],
)
write_csv(
    os.path.join(OUT, "ods_view_join_edges.csv"),
    all_edges,
    ["view", "from_table", "from_column", "to_table", "to_column", "condition", "source", "confidence"],
)
write_csv(
    os.path.join(OUT, "his_table_classification.csv"),
    his_rows,
    ["schema", "table", "domain", "classify_reason", "referenced_by_ods_view_count", "referenced_by_ods_views", "row_count_stats", "column_count", "comment"],
)

graph = {
    "meta": {
        "source": "08_数据中心元数据快照.json",
        "method": "static_parse_ods_view_ddl_and_his_name_classification",
        "ods_view_count": len(schemas.get("ODS", {}).get("views", {})),
        "dependency_count": len(deps_unique),
        "join_edge_count": len(all_edges),
        "his_table_count": len(his_rows),
        "note": "静态解析结果用于关系图谱种子，正式入图前建议按10_关系验证报告的方法做数据库验证。",
    },
    "ods_view_dependencies": deps_unique,
    "ods_view_join_edges": all_edges,
    "his_table_classification": his_rows,
}
json.dump(graph, open(os.path.join(OUT, "graph_seed.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)

domain_counts = defaultdict(int)
for r in his_rows:
    domain_counts[r["domain"]] += 1

print("生成完成 ->", OUT)
print("ODS views:", len(schemas.get("ODS", {}).get("views", {})))
print("dependencies:", len(deps_unique))
print("join_edges:", len(all_edges))
print("HIS tables:", len(his_rows))
print("HIS domains:")
for domain, count in sorted(domain_counts.items(), key=lambda x: (-x[1], x[0])):
    print("  %s: %s" % (domain, count))
