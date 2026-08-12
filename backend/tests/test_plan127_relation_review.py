"""127 S6/S9: relation review approve links formal, does not promote candidate mirror."""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.asset import AssetRelation, AssetRelationReview
from app.services.relation_identity import populate_endpoint_fields
from app.services.relation_review_service import approve_review, reject_review


def _seed_review_scenario(db):
    """Seed formal owner-named relations + ODS HIS.* candidates + 3 drafts."""
    # Clean previous plan127 markers
    for r in db.scalars(select(AssetRelationReview).where(AssetRelationReview.source_evidence.like("plan127%"))).all():
        db.delete(r)
    for r in db.scalars(select(AssetRelation).where(AssetRelation.note.like("plan127%"))).all():
        db.delete(r)
    db.flush()

    formal_bill = AssetRelation(
        from_table="INPBILL.INP_BILL_DETAIL",
        from_columns="PATIENT_ID,VISIT_ID",
        to_table="MEDREC.PAT_VISIT",
        to_columns="PATIENT_ID,VISIT_ID",
        join_condition="INPBILL.INP_BILL_DETAIL.PATIENT_ID=MEDREC.PAT_VISIT.PATIENT_ID AND INPBILL.INP_BILL_DETAIL.VISIT_ID=MEDREC.PAT_VISIT.VISIT_ID",
        confidence="A",
        validation_status="verified",
        relation_layer="formal",
        note="plan127 formal bill",
    )
    populate_endpoint_fields(db, formal_bill)
    db.add(formal_bill)

    formal_clinic = AssetRelation(
        from_table="OUTPADM.CLINIC_MASTER",
        from_columns="PATIENT_ID",
        to_table="MEDREC.PAT_MASTER_INDEX",
        to_columns="PATIENT_ID",
        join_condition="OUTPADM.CLINIC_MASTER.PATIENT_ID=MEDREC.PAT_MASTER_INDEX.PATIENT_ID",
        confidence="A",
        validation_status="verified",
        relation_layer="formal",
        note="plan127 formal clinic",
    )
    populate_endpoint_fields(db, formal_clinic)
    db.add(formal_clinic)

    cand_bill = AssetRelation(
        from_table="HIS.INP_BILL_DETAIL",
        from_columns="PATIENT_ID,VISIT_ID",
        to_table="HIS.PAT_VISIT",
        to_columns="PATIENT_ID,VISIT_ID",
        join_condition="HIS.INP_BILL_DETAIL.PATIENT_ID=HIS.PAT_VISIT.PATIENT_ID",
        confidence="B",
        validation_status="sample_pass",
        relation_layer="candidate",
        note="plan127 candidate bill mirror",
    )
    populate_endpoint_fields(db, cand_bill)
    db.add(cand_bill)

    cand_clinic = AssetRelation(
        from_table="HIS.CLINIC_MASTER",
        from_columns="PATIENT_ID",
        to_table="HIS.PAT_MASTER_INDEX",
        to_columns="PATIENT_ID",
        join_condition="HIS.CLINIC_MASTER.PATIENT_ID=HIS.PAT_MASTER_INDEX.PATIENT_ID",
        confidence="B",
        validation_status="sample_pass",
        relation_layer="candidate",
        note="plan127 candidate clinic mirror",
    )
    populate_endpoint_fields(db, cand_clinic)
    db.add(cand_clinic)
    db.flush()

    r1 = AssetRelationReview(
        relation_scope="formal",
        from_table="HIS.INP_BILL_DETAIL",
        from_columns="PATIENT_ID,VISIT_ID",
        to_table="HIS.PAT_VISIT",
        to_columns="PATIENT_ID,VISIT_ID",
        join_condition="HIS.INP_BILL_DETAIL.PATIENT_ID=HIS.PAT_VISIT.PATIENT_ID",
        review_status="draft",
        confidence="A",
        source_evidence="plan127 review1 G1",
        relation_desc_cn="住院费用明细→就诊",
    )
    r2 = AssetRelationReview(
        relation_scope="formal",
        from_table="HIS.CLINIC_MASTER",
        from_columns="PATIENT_ID",
        to_table="HIS.PAT_MASTER_INDEX",
        to_columns="PATIENT_ID",
        join_condition="HIS.CLINIC_MASTER.PATIENT_ID=HIS.PAT_MASTER_INDEX.PATIENT_ID",
        review_status="draft",
        confidence="A",
        source_evidence="plan127 review2 G2",
        relation_desc_cn="门诊主表→患者主索引",
        review_note="保留 1 条孤儿说明",
    )
    r3 = AssetRelationReview(
        relation_scope="formal",
        from_table="MEDREC.PAT_VISIT",
        from_columns="PATIENT_ID,VISIT_ID",
        to_table="HIS.PAT_VISIT",
        to_columns="PATIENT_ID,VISIT_ID",
        join_condition="MEDREC.PAT_VISIT.PATIENT_ID=HIS.PAT_VISIT.PATIENT_ID",
        review_status="draft",
        confidence="C",
        source_evidence="plan127 review3 cross-system draft only",
        relation_desc_cn="源端住院→ODS 镜像住院（证据不足）",
    )
    db.add_all([r1, r2, r3])
    db.commit()
    db.refresh(formal_bill)
    db.refresh(formal_clinic)
    db.refresh(cand_bill)
    db.refresh(cand_clinic)
    db.refresh(r1)
    db.refresh(r2)
    db.refresh(r3)
    return {
        "formal_bill": formal_bill,
        "formal_clinic": formal_clinic,
        "cand_bill": cand_bill,
        "cand_clinic": cand_clinic,
        "r1": r1,
        "r2": r2,
        "r3": r3,
    }


def test_approve_review1_links_formal_not_candidate(client: TestClient):
    db = SessionLocal()
    try:
        seed = _seed_review_scenario(db)
        formal_id = seed["formal_bill"].id
        cand_id = seed["cand_bill"].id
        r1_id = seed["r1"].id

        result = approve_review(db, seed["r1"], reviewer="plan127-test", note="A14")
        db.commit()
        assert result["ok"] is True
        assert result["action"] == "linked_formal"
        assert result["source_relation_id"] == formal_id
        assert result["source_relation_id"] != cand_id

        # candidate must remain candidate
        cand = db.get(AssetRelation, cand_id)
        assert (cand.relation_layer or "").lower() == "candidate"
        assert (cand.validation_status or "").lower() != "verified"

        review = db.get(AssetRelationReview, r1_id)
        assert review.review_status == "approved"
        assert review.source_relation_id == formal_id
    finally:
        db.close()


def test_approve_review2_links_formal_keeps_orphan_note(client: TestClient):
    db = SessionLocal()
    try:
        seed = _seed_review_scenario(db)
        formal_id = seed["formal_clinic"].id
        cand_id = seed["cand_clinic"].id
        result = approve_review(db, seed["r2"], reviewer="plan127-test", note="orphan retained")
        db.commit()
        assert result["ok"] is True
        assert result["source_relation_id"] == formal_id
        assert result["source_relation_id"] != cand_id
        review = db.get(AssetRelationReview, seed["r2"].id)
        assert review.review_status == "approved"
        assert "孤儿" in (review.review_note or "") or "orphan" in (review.review_note or "").lower() or "approve" in (review.review_note or "")
    finally:
        db.close()


def test_review3_stays_draft_when_not_approved(client: TestClient):
    db = SessionLocal()
    try:
        seed = _seed_review_scenario(db)
        r3 = db.get(AssetRelationReview, seed["r3"].id)
        assert r3.review_status == "draft"
        assert r3.source_relation_id is None
        # Reject path must not delete
        reject_review(db, r3, reviewer="plan127-test", note="insufficient evidence")
        db.commit()
        r3 = db.get(AssetRelationReview, seed["r3"].id)
        assert r3 is not None
        assert r3.review_status == "rejected"
        assert "insufficient" in (r3.review_note or "")
    finally:
        db.close()


def test_relation_reviews_list_api(client: TestClient):
    db = SessionLocal()
    try:
        _seed_review_scenario(db)
    finally:
        db.close()
    resp = client.get("/api/v1/relation-reviews", params={"review_status": "draft", "page_size": 50})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "items" in data and "total" in data
    assert data["total"] >= 1
    codes = [i.get("source_evidence") for i in data["items"]]
    assert any(c and c.startswith("plan127") for c in codes)

    counts = client.get("/api/v1/relation-reviews/counts")
    assert counts.status_code == 200
    body = counts.json()["data"]
    assert "draft" in body and "total" in body
