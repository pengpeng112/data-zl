"""175 号：把三系统只读聚合证据幂等写入平台治理层。

只写平台 asset schema；业务源库零写。默认 dry-run，显式 --apply 才提交。
关系只进 review draft，值域只进 pending，质控观测走 174 领域服务。
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from sqlalchemy import func, select, text

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.db import SessionLocal  # noqa: E402
from app.models.asset import AssetRelationReview  # noqa: E402
from app.models.quality_governance import QualityControl, QualityControlDetector  # noqa: E402
from app.models.value_domain import (  # noqa: E402
    AssetColumnValueDomain,
    AssetColumnValueDomainEvidence,
)
from app.services import quality_governance_service as qgs  # noqa: E402
from app.services import value_domain_service as vds  # noqa: E402

ACTOR = "import:plan175"
EVIDENCE_REF = "开发起步包/175_三系统质控关系值域增量只读探索报告.md"


DOMAINS = [
    ("LIS_SOURCE", "lis_sqlserver_10_10_10_73", "dbo", "CDR_INSPECTION_REPORT", "VISIT_TYPE_CODE", "01", "门诊", 137974),
    ("LIS_SOURCE", "lis_sqlserver_10_10_10_73", "dbo", "CDR_INSPECTION_REPORT", "VISIT_TYPE_CODE", "02", "住院", 392287),
    ("LIS_SOURCE", "lis_sqlserver_10_10_10_73", "dbo", "CDR_INSPECTION_REPORT", "REPORT_STATUS", "完成", "完成", 537838),
    ("ULTRASOUND_ENDOSCOPY", "ultrasound_endoscopy_sqlserver_10_10_10_161", "AnyImage.grid", "BHosCheckUS", "PatSource", "门诊", "门诊", 34481),
    ("ULTRASOUND_ENDOSCOPY", "ultrasound_endoscopy_sqlserver_10_10_10_161", "AnyImage.grid", "BHosCheckUS", "PatSource", "住院", "住院", 50947),
    ("ULTRASOUND_ENDOSCOPY", "ultrasound_endoscopy_sqlserver_10_10_10_161", "AnyImage.grid", "BHosCheckUS", "PatSource", "体检", "体检", 2489),
    ("ULTRASOUND_ENDOSCOPY", "ultrasound_endoscopy_sqlserver_10_10_10_161", "AnyImage.grid", "BHosCheckUS", "Printed", "T", "观测码 T（业务语义待确认）", 85354),
    ("ULTRASOUND_ENDOSCOPY", "ultrasound_endoscopy_sqlserver_10_10_10_161", "AnyImage.grid", "BHosCheckUS", "Printed", "F", "观测码 F（业务语义待确认）", 2563),
    ("DOCARE", "docare_oracle_10_10_10_68", "MEDSURGERY", "MED_OPERATION_MASTER", "EMERGENCY_INDICATOR", "0", "观测码 0（业务语义待确认）", 17172),
    ("DOCARE", "docare_oracle_10_10_10_68", "MEDSURGERY", "MED_OPERATION_MASTER", "EMERGENCY_INDICATOR", "1", "观测码 1（业务语义待确认）", 968),
] + [
    ("DOCARE", "docare_oracle_10_10_10_68", "MEDSURGERY", "MED_OPERATION_MASTER", "OPER_STATUS", code, f"观测码 {code}（业务语义待确认）", count)
    for code, count in (("-80", 193), ("0", 1366), ("15", 1), ("35", 15517), ("40", 10), ("55", 992), ("60", 40), ("61", 34))
]

OBSERVATIONS = [
    ("DQ-LIS-KEY-001", 11.0 / 392287.0 * 100.0, 11, 392287, "LIS 住院报告 VISIT_ID 缺失率"),
    ("DQ-US-VISIT-001", 39.0 / 50947.0 * 100.0, 39, 50947, "超声住院报告 VisitID 空或 0 比例"),
    ("DQ-DOC-VISIT-001", 5.0 / 755.0 * 100.0, 5, 755, "Docare 急诊无有效排班且 VISIT_ID 非 1 例外率"),
]


def run(*, apply: bool) -> dict:
    db = SessionLocal()
    stats = {"domains_created": 0, "evidence_created": 0, "relation_reviews_created": 0,
             "observations": [], "detectors_updated": 0, "committed": False}
    try:
        db.execute(text("SELECT pg_advisory_xact_lock(17520260903)"))
        for system_code, source_code, schema, table, column, code, meaning, sample_count in DOMAINS:
            row = vds.find_by_key(db, system_code=system_code, source_code=source_code,
                                  schema_name=schema, table_name=table, column_name=column, code=code)
            if row is None:
                row = AssetColumnValueDomain(
                    system_code=system_code, source_code=source_code, schema_name=schema,
                    table_name=table, column_name=column, code=code, meaning=meaning,
                    note="175 号 2026 年窗口只读聚合；pending，须人工确认",
                    domain_kind="enum", scope_condition="2026-01-01<=time<2027-01-01",
                    status="pending", conflict_status="none",
                )
                db.add(row)
                db.flush()
                vds.next_version(db, row, change_reason="175 号只读聚合候选导入",
                                 actor=ACTOR, evidence_ref=EVIDENCE_REF)
                stats["domains_created"] += 1
            evidence = {
                "source_type": "live_probe", "source_system": system_code,
                "observed_meaning": meaning, "method": "sjzc live 限窗聚合",
                "sample_count": sample_count, "observed_at": datetime(2026, 9, 2, tzinfo=timezone.utc),
                "actor": ACTOR, "snippet_ref": EVIDENCE_REF,
            }
            if not vds.evidence_duplicate(db, row.id, evidence):
                db.add(vds.evidence_row(row.id, evidence))
                stats["evidence_created"] += 1

        join_condition = "AnyImage.grid.BHosCheckUS.BookID = MedcareUS.dbo.预约登记.编号"
        exists = db.scalar(select(AssetRelationReview.id).where(
            AssetRelationReview.from_system_code == "ULTRASOUND_ENDOSCOPY",
            AssetRelationReview.from_table == "AnyImage.grid.BHosCheckUS",
            AssetRelationReview.to_table == "MedcareUS.dbo.预约登记",
            AssetRelationReview.join_condition == join_condition,
        ))
        if exists is None:
            next_id = (db.scalar(select(func.max(AssetRelationReview.id))) or 0) + 1
            db.add(AssetRelationReview(
                id=next_id, relation_scope="candidate",
                from_system_code="ULTRASOUND_ENDOSCOPY",
                from_source_code="ultrasound_endoscopy_sqlserver_10_10_10_161",
                from_table="AnyImage.grid.BHosCheckUS", from_columns="BookID",
                to_system_code="ULTRASOUND_ENDOSCOPY",
                to_source_code="ultrasound_endoscopy_sqlserver_10_10_10_161",
                to_table="MedcareUS.dbo.预约登记", to_columns="编号",
                join_condition=join_condition,
                relation_desc_cn="超声检查到预约登记（BookID→编号）",
                business_logic_cn="2026住院窗口50947条，37条预约孤儿；仅部分关系候选，不替换AccessNo正式主线",
                confidence="B", validation_status="partial", review_status="draft",
                review_note="175 号只读增量证据；需人工复核，不自动发布",
                source_evidence=EVIDENCE_REF,
            ))
            stats["relation_reviews_created"] = 1

        for control_code, metric, numerator, denominator, label in OBSERVATIONS:
            control = db.scalar(select(QualityControl).where(QualityControl.control_code == control_code))
            if control is None:
                raise RuntimeError(f"missing control: {control_code}")
            detector = db.scalar(select(QualityControlDetector).where(
                QualityControlDetector.control_id == control.id,
                QualityControlDetector.detector_ref == control_code,
            ))
            if detector is not None:
                detector.blocked_reason = "175 号只读证据已取得；自动跨系统执行器及业务口径确认待完成"
                detector.result_mapping = {"evidence": EVIDENCE_REF, "metric": label}
                stats["detectors_updated"] += 1
            outcome = qgs.apply_observation(
                db, control_id=control.id, detector_id=detector.id if detector else None,
                run_key="plan175:2026", scope_key=f"meeting:{control_code}",
                result_status="fail", window_start=date(2026, 1, 1), window_end=date(2027, 1, 1),
                metric_value=metric, metric_unit="percent", numerator=numerator, denominator=denominator,
                source_kind="external", source_record_ref="plan175:readonly-live",
                evidence_ref=EVIDENCE_REF, historical_precision="exact", actor=ACTOR,
                correlation_id="plan175-prod-import-20260903",
            )
            stats["observations"].append({"control_code": control_code, **outcome})

        if apply:
            db.commit()
            stats["committed"] = True
        else:
            db.rollback()
        return stats
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(apply=args.apply), ensure_ascii=False, indent=2))
