"""93 号 v3 · 步 4 · 阶段 2 核心表/列元数据补全。

读 3 个 CSV(ods_core_tables / ods_core_columns / his_source_value_desc) UPDATE 既有行。
全程只补 NULL 字段,不覆盖既有非空值(D4: review_status 仅当 NULL 置 unreviewed/draft)。

用法(容器内):
    python -m scripts.import_ods_core_governance --dry-run
    python -m scripts.import_ods_core_governance
"""
from __future__ import annotations
import argparse, csv, json, sys
from pathlib import Path
BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))
# CSV 包路径:本机 backend/../开发起步包/... ;容器内 /app/开发起步包/...
PACKAGE_CANDIDATES = [
    BACKEND_DIR.parent / "开发起步包" / "数据资产_ODS核心表治理导入包",
    Path("/app/开发起步包/数据资产_ODS核心表治理导入包"),
]
PACKAGE = next((p for p in PACKAGE_CANDIDATES if p.exists()), PACKAGE_CANDIDATES[0])

from sqlalchemy import select, func
from app.core.db import SessionLocal
from app.models.asset import AssetTable, AssetColumn


def read_csv(name):
    with (PACKAGE / name).open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    db = SessionLocal()
    summary = {"tables_updated": 0, "columns_updated": 0, "his_value_updated": 0,
               "warnings": [], "dry_run": args.dry_run}

    try:
        # ===== ods_core_tables.csv =====
        for row in read_csv("ods_core_tables.csv"):
            src, sch, tbl = row["source_code"], row["schema_name"], row["table_name"]
            rec = db.scalar(select(AssetTable).where(
                AssetTable.source_code == src, AssetTable.schema_name == sch, AssetTable.table_name == tbl))
            if rec is None:
                summary["warnings"].append(f"TABLE_NOT_FOUND: {src}/{sch}.{tbl}")
                continue
            changed = []
            if rec.business_desc_cn is None and row.get("business_desc_cn"):
                changed.append("business_desc_cn")
                if not args.dry_run: rec.business_desc_cn = row["business_desc_cn"]
            # domain/grain/pk 仅补 NULL(OPERATION_MASTER)
            for fld in ("domain", "grain", "pk"):
                val = row.get(fld, "").strip()
                if val and getattr(rec, fld, None) is None:
                    changed.append(fld)
                    if not args.dry_run: setattr(rec, fld, val)
            if rec.review_status is None:
                changed.append("review_status=unreviewed")
                if not args.dry_run: rec.review_status = "unreviewed"
            if changed: summary["tables_updated"] += 1

        # ===== ods_core_columns.csv =====
        for row in read_csv("ods_core_columns.csv"):
            src, sch, tbl, col = row["source_code"], row["schema_name"], row["table_name"], row["column_name"]
            rec = db.scalar(select(AssetColumn).where(
                AssetColumn.source_code == src, AssetColumn.schema_name == sch,
                AssetColumn.table_name == tbl, AssetColumn.column_name == col))
            if rec is None:
                summary["warnings"].append(f"COLUMN_NOT_FOUND: {src}/{sch}.{tbl}.{col}")
                continue
            changed = []
            for fld in ("column_name_cn", "business_desc_cn", "value_desc_cn", "semantic_type"):
                val = row.get(fld, "").strip()
                if val and getattr(rec, fld, None) is None:
                    changed.append(fld)
                    if not args.dry_run: setattr(rec, fld, val)
            if row.get("is_sensitive", "").strip().lower() in ("true", "1", "yes") and not rec.is_sensitive:
                changed.append("is_sensitive=true")
                if not args.dry_run: rec.is_sensitive = True
            if rec.review_status is None:
                changed.append("review_status=unreviewed")
                if not args.dry_run: rec.review_status = "unreviewed"
            if changed:
                summary["columns_updated"] += 1
                if not args.dry_run:
                    rec.name_cn_source = "handover_doc_20260727"
                    rec.name_cn_status = "pending_review"

        # ===== his_source_value_desc.csv =====
        for row in read_csv("his_source_value_desc.csv"):
            src, sch, tbl, col = row["source_code"], row["schema_name"], row["table_name"], row["column_name"]
            rec = db.scalar(select(AssetColumn).where(
                AssetColumn.source_code == src, AssetColumn.schema_name == sch,
                AssetColumn.table_name == tbl, AssetColumn.column_name == col))
            if rec is None:
                summary["warnings"].append(f"HIS_COL_NOT_FOUND: {src}/{sch}.{tbl}.{col}")
                continue
            if rec.value_desc_cn is None and row.get("value_desc_cn"):
                summary["his_value_updated"] += 1
                if not args.dry_run:
                    rec.value_desc_cn = row["value_desc_cn"]
                    rec.name_cn_source = row.get("name_cn_source", "handover_doc_20260727")
                    rec.name_cn_status = "pending_review"

        if not args.dry_run:
            db.commit()
            # 警告落盘
            (PACKAGE / "import_warnings.json").write_text(
                json.dumps(summary["warnings"], ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    except Exception as e:
        db.rollback()
        print(json.dumps({"error": f"{type(e).__name__}: {e}"}, ensure_ascii=False))
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
