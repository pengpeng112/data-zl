"""T7: Generate ODS/HIS/HRP normalized optimization package.

Reads existing asset packages and enriches with system_category / source_system
/ source_database / schema_name. D-class relationships go into cross_system_pending.
Output in 开发起步包/数据资产_ODS_HIS归一优化包/ (does NOT overwrite originals).
"""
from __future__ import annotations

import csv
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "开发起步包"
ASSET_PKG = ROOT / "数据资产_资产包"
HIS_PKG = ROOT / "数据资产_HIS源端资产包"
SNAPSHOT = ROOT / "08_数据中心元数据快照.json"
OUT_DIR = ROOT / "数据资产_ODS_HIS归一优化包"

# --- Classification helpers ---

ODS_SCHEMA_MAP = {
    "HIS": ("ods_his", "HIS 抽取区"),
    "CDA": ("ods_cda", "CDA/标准字典区"),
    "LIS": ("ods_lis", "LIS 抽取区"),
    "PACS": ("ods_pacs", "PACS 抽取区"),
    "JHEMR": ("ods_emr", "EMR/病历抽取区"),
    "MTL": ("ods_emr", "EMR/病历抽取区"),
    "YBEMR": ("ods_emr", "EMR/病历抽取区"),
    "YDHL": ("ods_ydhl", "移动护理抽取区"),
    "SM": ("ods_sm", "手麻抽取区"),
    "ODS": ("ods_other", "ODS 视图层"),
    "BL": ("ods_other", "病理"),
    "CRBSB": ("ods_other", "超声/设备"),
    "CS": ("ods_other", "超声"),
    "DBZ": ("ods_other", "电子病案"),
    "FXJCPT": ("ods_other", "风险检查"),
    "HRP": ("ods_hrp", "HRP 抽取区"),
    "JXXT": ("ods_other", "教学系统"),
    "KZL": ("ods_other", "康复治疗"),
    "MDK": ("ods_other", "门诊药房"),
    "NJ": ("ods_other", "内镜"),
    "PORTAL": ("ods_portal", "门户/单点登录"),
    "PORTAL_EMPI": ("ods_portal", "门户/患者主索引"),
    "PORTAL_USER": ("ods_portal", "门户/用户"),
    "PORTAL_USER_GROUP": ("ods_portal", "门户/用户组"),
    "SHUNNENG": ("ods_other", "顺能"),
    "SX": ("ods_other", "输血"),
    "TJ": ("ods_other", "体检"),
    "WSCTS": ("ods_other", "卫生统计"),
    "XD": ("ods_other", "消毒供应"),
    "YINGYI": ("ods_other", "影医"),
}

HIS_OWNER_DOMAIN = {
    "MEDREC": "患者主数据",
    "ORDADM": "医嘱",
    "LAB": "检验",
    "EXAM": "检查",
    "INPBILL": "住院费用",
    "OUTPBILL": "门诊费用",
    "INPADM": "住院管理",
    "OUTPADM": "门诊管理",
    "DRUG_USER": "药品",
    "PHARMACY": "药品",
    "COMM": "字典",
    "MEDADM": "住院管理",
}

RELATION_CLASS = {}
D_CLASS_RELS = set()

def _load_relation_class():
    """Classify relationships from catalog.json trust levels."""
    catalog_path = ASSET_PKG / "catalog.json"
    if not catalog_path.exists():
        return
    with open(catalog_path, encoding="utf-8") as f:
        cat = json.load(f)
    for rel in cat.get("relationships", []):
        fid = rel.get("rel_id") or rel.get("id")
        level = rel.get("validation_level", "")
        cls = "A" if "A" in str(level) else "B" if "B" in str(level) else "C" if "C" in str(level) else "D"
        if cls == "D":
            D_CLASS_RELS.add(fid)
        RELATION_CLASS[fid] = cls
        # D-class: cross-system pending, keep in separate layer
    # Also read CSV for relationship ids
    rel_path = ASSET_PKG / "relationships.csv"
    if not rel_path.exists():
        return
    with open(rel_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rid = int(row.get("id", 0))
            level = row.get("validation_level", "")
            cls = "A" if "A" in str(level) else "B" if "B" in str(level) else "C" if "C" in str(level) else "D"
            if cls == "D":
                D_CLASS_RELS.add(rid)
            if rid not in RELATION_CLASS:
                RELATION_CLASS[rid] = cls

def _classify_ods_table(schema: str, table: str) -> tuple[str, str]:
    ss, cn = ODS_SCHEMA_MAP.get(schema, ("ods_other", "其他抽取区"))
    return ss, cn

def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    _load_relation_class()

    norm_tables = []
    norm_columns = []
    norm_relations = []
    d_relations = []

    # ---- ODS center tables (from 资产包/tables.csv) ----
    tables_csv = ASSET_PKG / "tables.csv"
    if tables_csv.exists():
        with open(tables_csv, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                schema = row.get("schema", "")
                ss, cn = _classify_ods_table(schema, row.get("table", ""))
                norm_tables.append({
                    "system_category": "ods_center",
                    "source_system": ss,
                    "source_system_cn": cn,
                    "source_database": "data_center_ods",
                    "schema_name": schema,
                    "table_name": row.get("table", ""),
                    "table_name_cn": row.get("comment", ""),
                    "business_domain": row.get("domain", ""),
                    "table_role": row.get("table_role", ""),
                    "row_count": row.get("row_count_stats", ""),
                    "column_count": row.get("column_count", ""),
                    "include_status": "core" if row.get("confidence") in ("A", "B") else "candidate",
                    "pk": row.get("pk", ""),
                    "confidence": row.get("confidence", ""),
                    "note": row.get("note", ""),
                    "source": row.get("source", ""),
                })

    # ---- ODS columns ----
    cols_csv = ASSET_PKG / "columns.csv"
    if cols_csv.exists():
        with open(cols_csv, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                schema = row.get("schema", "")
                ss, _ = _classify_ods_table(schema, row.get("table", ""))
                norm_columns.append({
                    "system_category": "ods_center",
                    "source_system": ss,
                    "schema_name": schema,
                    "table_name": row.get("table", ""),
                    "column_name": row.get("column", ""),
                    "column_name_cn": row.get("comment", ""),
                    "data_type": row.get("data_type", ""),
                    "column_id": row.get("column_id", ""),
                    "nullable": row.get("nullable", ""),
                })

    # ---- ODS relationships (split normal vs D-class) ----
    rels_csv = ASSET_PKG / "relationships.csv"
    if rels_csv.exists():
        with open(rels_csv, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rid = int(row.get("id", 0))
                is_d = rid in D_CLASS_RELS
                entry = {
                    "id": rid,
                    "system_category": "ods_center",
                    "relationship_class": "D" if is_d else RELATION_CLASS.get(rid, "C"),
                    "domain": row.get("domain", ""),
                    "from_table": row.get("from_table", ""),
                    "from_columns": row.get("from_columns", ""),
                    "to_table": row.get("to_table", ""),
                    "to_columns": row.get("to_columns", ""),
                    "join_condition": row.get("join_condition", ""),
                    "cardinality": row.get("cardinality", ""),
                    "confidence": row.get("confidence", ""),
                    "validation_level": row.get("validation_level", ""),
                    "validation_status": row.get("validation_status", ""),
                    "validation_metrics": row.get("validation_metrics", ""),
                    "note": row.get("note", ""),
                    "validation_note": row.get("validation_note", ""),
                }
                if is_d:
                    entry["validation_status"] = "pending_cross_system_validation"
                    d_relations.append(entry)
                else:
                    norm_relations.append(entry)

    # ---- HIS source tables ----
    his_tables = HIS_PKG / "his_source_tables.csv"
    if his_tables.exists():
        with open(his_tables, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                owner = row.get("source_owner", "")
                domain = HIS_OWNER_DOMAIN.get(owner, row.get("domain", ""))
                norm_tables.append({
                    "system_category": "his_source",
                    "source_system": owner,
                    "source_system_cn": f"HIS {owner}",
                    "source_database": "ready_his",
                    "schema_name": owner,
                    "table_name": row.get("table_name", ""),
                    "table_name_cn": row.get("table_name_cn", ""),
                    "business_domain": domain,
                    "table_role": row.get("table_role", ""),
                    "row_count": row.get("num_rows_stats", ""),
                    "column_count": row.get("column_count", ""),
                    "include_status": row.get("include_status", ""),
                    "pk": row.get("primary_key", ""),
                    "exclude_reason": row.get("exclude_reason", ""),
                    "ods_same_name_covered": row.get("ods_same_name_covered", ""),
                    "note": row.get("include_note", ""),
                })

    # ---- HIS source columns ----
    his_cols = HIS_PKG / "his_source_columns.csv"
    if his_cols.exists():
        with open(his_cols, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                norm_columns.append({
                    "system_category": "his_source",
                    "source_system": row.get("source_owner", ""),
                    "schema_name": row.get("source_owner", ""),
                    "table_name": row.get("table_name", ""),
                    "column_name": row.get("column_name", ""),
                    "column_name_cn": row.get("column_name_cn", ""),
                    "data_type": row.get("data_type", ""),
                    "column_id": row.get("column_id", ""),
                    "nullable": row.get("nullable", ""),
                })

    # ---- HIS source relationships ----
    his_rels = HIS_PKG / "his_source_relationships.csv"
    if his_rels.exists():
        with open(his_rels, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                norm_relations.append({
                    "id": row.get("id", ""),
                    "system_category": "his_source",
                    "relationship_class": row.get("relationship_class", ""),
                    "domain": row.get("domain", ""),
                    "from_table": row.get("from_table", ""),
                    "from_columns": row.get("from_columns", ""),
                    "to_table": row.get("to_table", ""),
                    "to_columns": row.get("to_columns", ""),
                    "join_condition": row.get("join_condition", ""),
                    "cardinality": row.get("cardinality", ""),
                    "confidence": row.get("confidence", ""),
                    "validation_level": row.get("validation_level", ""),
                    "validation_status": row.get("validation_status", ""),
                    "note": row.get("note", ""),
                })

    # ---- Write CSVs ----
    def _write_csv(name: str, rows: list[dict], fieldnames: list[str]):
        path = OUT_DIR / name
        with open(path, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)
        return len(rows)

    tf = [
        "system_category", "source_system", "source_system_cn", "source_database",
        "schema_name", "table_name", "table_name_cn", "business_domain",
        "table_role", "row_count", "column_count", "include_status",
        "pk", "confidence", "exclude_reason", "ods_same_name_covered", "note", "source",
    ]
    tc = _write_csv("normalized_tables.csv", norm_tables, tf)

    cf = [
        "system_category", "source_system", "schema_name", "table_name",
        "column_name", "column_name_cn", "data_type", "column_id", "nullable",
    ]
    cc = _write_csv("normalized_columns.csv", norm_columns, cf)

    rf = [
        "id", "system_category", "relationship_class", "domain",
        "from_table", "from_columns", "to_table", "to_columns",
        "join_condition", "cardinality", "confidence",
        "validation_level", "validation_status", "validation_metrics",
        "note", "validation_note",
    ]
    rc = _write_csv("normalized_relationships.csv", norm_relations, rf)
    dc = _write_csv("cross_system_pending_relationships.csv", d_relations, rf)

    # ---- Catalog JSON ----
    cat = {
        "meta": {
            "generated_at": "2026-07-12",
            "generated_by": "tools/build_normalized_package.py",
            "sources": [
                "数据资产_资产包/ (ODS center)",
                "数据资产_HIS源端资产包/ (HIS source)",
            ],
            "classification_basis": {
                "system_categories": "51_ODS_HIS大类归一与数据中心二次优化改造计划.md §2.2",
                "ods_internal_split": "51 §2.3",
                "relationship_class": "39_secondary_relationships分级修订报告.md / 40_数据治理复核口径与方法记录.md",
                "d_class_rule": "D 类跨系统关系仅进 cross_system_pending 图层，不参与正式治理导入和自动推导",
            },
        },
        "summary": {
            "table_count": tc,
            "column_count": cc,
            "relationship_count": rc,
            "d_class_pending_count": dc,
            "system_category_counts": {},
            "ods_source_system_counts": {},
        },
        "navigation": {
            "level1_system_category": {
                "ods_center": "ODS 数据中心系统",
                "his_source": "HIS 源端系统",
                "hrp_source": "HRP 源端系统 (暂未入包)",
                "external_business": "其他业务系统 (暂未入包)",
                "platform_asset": "平台元数据系统 (暂未入包)",
            },
            "ods_internal_split": {
                "ods_his": "HIS 抽取区",
                "ods_lis": "LIS 抽取区",
                "ods_pacs": "PACS 抽取区",
                "ods_emr": "EMR/病历抽取区",
                "ods_ydhl": "移动护理抽取区",
                "ods_sm": "手麻抽取区",
                "ods_cda": "CDA/标准字典区",
                "ods_other": "其他抽取区",
            },
        },
    }

    # count categories
    for t in norm_tables:
        sc = t["system_category"]
        cat["summary"]["system_category_counts"][sc] = cat["summary"]["system_category_counts"].get(sc, 0) + 1
    ods_ss = {}
    for t in norm_tables:
        if t["system_category"] == "ods_center":
            ss = t["source_system"]
            ods_ss[ss] = ods_ss.get(ss, 0) + 1
    cat["summary"]["ods_source_system_counts"] = ods_ss

    with open(OUT_DIR / "normalized_catalog.json", "w", encoding="utf-8") as f:
        json.dump(cat, f, ensure_ascii=False, indent=2)

    print(f"Wrote {tc} tables, {cc} columns, {rc} relationships, {dc} D-class pending → {OUT_DIR}")
    print(json.dumps(cat["summary"], ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
