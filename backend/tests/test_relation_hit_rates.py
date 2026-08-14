from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.asset import AssetRelation
from app.models.governance_ops import ChangeRule
from app.services.his_source_authority import RULE_CODE, RULE_NAME_CN
from app.services.relation_identity import populate_endpoint_fields


def test_hit_rates_and_authority_rule(client: TestClient) -> None:
    db = SessionLocal()
    try:
        rel = db.scalar(select(AssetRelation).where(AssetRelation.rel_id == 900553))
        if not rel:
            rel = AssetRelation(
                rel_id=900553,
                domain="检查-住院",
                from_table="HIS.PAT_VISIT",
                from_columns="PATIENT_ID|VISIT_ID",
                to_table="HIS.EXAM_MASTER",
                to_columns="PATIENT_ID|VISIT_ID",
                join_condition="PATIENT_ID+VISIT_ID AND EXAM_MASTER.VISIT_ID<>0",
                confidence="A",
                validation_status="sample_verified",
                relation_layer="formal",
                validation_metrics="ods_sample=50000; orphan=4; orphan_rate=0.008%",
                note="test exam inpatient split",
            )
            db.add(rel)
            populate_endpoint_fields(db, rel)
        existing = db.scalar(select(ChangeRule).where(ChangeRule.rule_code == RULE_CODE))
        if not existing:
            db.add(
                ChangeRule(
                    rule_code=RULE_CODE,
                    rule_name_cn=RULE_NAME_CN,
                    system_code="HIS_SOURCE",
                    change_type="relation_authority",
                    description="HISUSER authoritative test rule",
                    enabled=True,
                )
            )
        db.commit()
    finally:
        db.close()

    rates = client.get("/api/v1/relations/hit-rates?scene=exam_inpatient")
    assert rates.status_code == 200, rates.text
    body = rates.json()
    assert body["code"] == 0
    items = body["data"]["items"]
    assert items
    assert items[0]["scene"] == "exam_inpatient"
    assert items[0]["scene_label"] == "检查·住院"
    assert items[0]["hit_rate"] is not None
    assert items[0]["hit_rate"] > 0.99

    rule = client.get("/api/v1/relations/authority-rule")
    assert rule.status_code == 200, rule.text
    payload = rule.json()["data"]
    assert payload["rule_code"] == RULE_CODE
    assert payload["persisted"] is True
    assert payload["authority_system_code"] == "HIS_SOURCE"
