"""93 号 v3 · 步 5 · 阶段 3 关系缺口登记(3 条 draft)。

G1 INP_BILL_DETAIL→PAT_VISIT / G2 CLINIC_MASTER→PAT_MASTER_INDEX / G3 his_source 镜像。
写入 asset_relation_reviews(review_status='draft', D4)。
先查 §5.2 防重(同 from_table+to_table+join_condition 不重复登记)。

用法(容器内):
    python -m scripts.import_ods_core_relations --dry-run
    python -m scripts.import_ods_core_relations
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import select, func
from app.core.db import SessionLocal
from app.models.asset import AssetRelationReview

EVIDENCE = "SQL与数据架构交接文档_20260727 §3.4"

RELATIONS = [
    {
        "key": "G1", "from_system_code": "DATA_CENTER", "from_source_code": "ods_8_216",
        "from_table": "HIS.INP_BILL_DETAIL", "from_columns": "PATIENT_ID+VISIT_ID",
        "to_system_code": "DATA_CENTER", "to_source_code": "ods_8_216",
        "to_table": "HIS.PAT_VISIT", "to_columns": "PATIENT_ID+VISIT_ID",
        "join_condition": "HIS.INP_BILL_DETAIL.PATIENT_ID = HIS.PAT_VISIT.PATIENT_ID AND HIS.INP_BILL_DETAIL.VISIT_ID = HIS.PAT_VISIT.VISIT_ID",
        "desc": "住院费用→就诊直接边（既有仅经 INP_SETTLE_MASTER 中介）",
    },
    {
        "key": "G2", "from_system_code": "DATA_CENTER", "from_source_code": "ods_8_216",
        "from_table": "HIS.CLINIC_MASTER", "from_columns": "PATIENT_ID",
        "to_system_code": "DATA_CENTER", "to_source_code": "ods_8_216",
        "to_table": "HIS.PAT_MASTER_INDEX", "to_columns": "PATIENT_ID",
        "join_condition": "HIS.CLINIC_MASTER.PATIENT_ID = HIS.PAT_MASTER_INDEX.PATIENT_ID",
        "desc": "门诊→主索引（交接文档 §3.4）",
    },
    {
        "key": "G3", "from_system_code": "HIS_SOURCE", "from_source_code": "his_source_10_10_10_15",
        "from_table": "MEDREC.PAT_VISIT", "from_columns": "PATIENT_ID+VISIT_ID",
        "to_system_code": "DATA_CENTER", "to_source_code": "ods_8_216",
        "to_table": "HIS.PAT_VISIT", "to_columns": "PATIENT_ID+VISIT_ID",
        "join_condition": "源端 MEDREC.PAT_VISIT → ODS HIS.PAT_VISIT 同名汇聚镜像",
        "desc": "镜像关系非业务外键（doc 88 §2 口径）；跨库不抽样验证，保持 draft",
    },
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    db = SessionLocal()
    summary = {"inserted": 0, "skipped_existing": [], "dry_run": args.dry_run}

    try:
        next_id = (db.scalar(select(func.max(AssetRelationReview.id))) or 0) + 1
        for rel in RELATIONS:
            # §5.2 防重:同 from_table+to_table+join_condition 已存在则跳过
            exists = db.scalar(select(AssetRelationReview).where(
                AssetRelationReview.from_table == rel["from_table"],
                AssetRelationReview.to_table == rel["to_table"],
                AssetRelationReview.join_condition == rel["join_condition"],
            ))
            if exists is not None:
                summary["skipped_existing"].append(f"{rel['key']} (id={exists.id}, status={exists.review_status})")
                continue
            if not args.dry_run:
                rec = AssetRelationReview(
                    id=next_id, relation_scope="formal",
                    from_system_code=rel["from_system_code"], from_source_code=rel["from_source_code"],
                    from_table=rel["from_table"], from_columns=rel["from_columns"],
                    to_system_code=rel["to_system_code"], to_source_code=rel["to_source_code"],
                    to_table=rel["to_table"], to_columns=rel["to_columns"],
                    join_condition=rel["join_condition"], relation_desc_cn=rel["desc"],
                    confidence="B", validation_status="pending", review_status="draft",
                    source_evidence=EVIDENCE,
                )
                db.add(rec)
                next_id += 1
            summary["inserted"] += 1
        if not args.dry_run:
            db.commit()
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    except Exception as e:
        db.rollback()
        print(json.dumps({"error": f"{type(e).__name__}: {e}"}, ensure_ascii=False))
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
