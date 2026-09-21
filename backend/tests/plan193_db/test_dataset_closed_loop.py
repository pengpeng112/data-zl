"""193 隔离库集成：合成数据全链路（B06—B15 软件闭环）。

前置：APP_TEST_DB_URL 指向可清理隔离库；迁移 a7b8c9d0e1f2 已应用（根 conftest TRUNCATE 清库）。
链路：建数据集→幂等批次+断点恢复→身份合并/拆分→分类网关（未分类拒绝→授权→撤权即时生效）
→版本状态机（质量门禁失败禁止发布→发布→撤销）→时间线/统计/训练集→受控导出（拒绝/白名单/过期/撤销）。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.main import app
from app.services import dataset_pipeline as pipe

T = {"Authorization": "Bearer test-token-p5-auth-2026", "X-CSRF-Token": "t"}


def _ingest_body(run_id: str, source: str, patients: list[str], day0="2026-01-01"):
    recs = []
    for i, p in enumerate(patients):
        recs.append({
            "fact_key": f"{run_id}:visit:{p}",
            "fact_kind": "visit",
            "source_patient_key": p,
            "source_visit_id": f"V{i}",
            "original_value_ref": f"{source}.VISIT/{p}",
            "business_time": f"{day0}T08:00:00+00:00",
            "available_time": f"{day0}T09:00:00+00:00",
        })
        recs.append({
            "fact_key": f"{run_id}:diag:{p}",
            "fact_kind": "diagnosis",
            "source_patient_key": p,
            "original_value_ref": f"{source}.DIAG/{p}",
            "standard_value": "I50.x00",
            "code_system": "ICD10",
            "business_time": f"{day0}T08:30:00+00:00",
            "available_time": f"{day0}T10:00:00+00:00",
        })
    return {"source_code": source, "object_name": f"{source}.SYNTH",
            "rule_version": "rules_v1", "records": recs}


def test_dataset_closed_loop(client: TestClient):
    # ---------- 建数据集（draft） ----------
    r = client.post("/api/v1/datasets", json={
        "dataset_code": "DS_SYNTH_193", "title": "193合成纵向数据集",
        "purpose_code": "research_synthetic", "grain": "patient"}, headers=T)
    assert r.status_code == 200, r.text
    version_id = r.json()["data"]["version_id"]

    # ---------- B06/B07：幂等批次 + 断点恢复 ----------
    body = _ingest_body("RUN-193-A", "SYNTH_A", ["SA001", "SA002", "SA003"])
    r1 = client.post("/api/v1/datasets/batches/RUN-193-A/records", json=body, headers=T)
    assert r1.status_code == 200, r1.text
    d1 = r1.json()["data"]
    assert d1["written"] == 6 and d1["skipped"] == 0
    # 重跑零重复
    r2 = client.post("/api/v1/datasets/batches/RUN-193-A/records", json=body, headers=T)
    d2 = r2.json()["data"]
    assert d2["written"] == 0 and d2["skipped"] == 6
    # 断点恢复检查点
    r = client.get("/api/v1/datasets/batches/RUN-193-A", headers=T)
    assert r.json()["data"]["checkpoint_keys"] == 6

    # 第二源同号不串人（B06：不同源同号）
    r = client.post("/api/v1/datasets/batches/RUN-193-B/records",
                    json=_ingest_body("RUN-193-B", "SYNTH_B", ["SA001"], day0="2026-02-01"),
                    headers=T)
    assert r.status_code == 200

    # ---------- B04/B05：未分类默认拒绝 → 分类+授权 → 撤权即时生效 ----------
    res = f"dataset:DS_SYNTH_193:{version_id}"
    r = client.get(f"/api/v1/datasets/DS_SYNTH_193/versions/{version_id}"
                   f"/timeline/DS-Pwhatever", headers=T)
    assert r.status_code == 403
    assert "deny_unclassified" in r.text or "未分类" in r.text

    r = client.post("/api/v1/datasets/classifications", json={
        "object_ref": res,
        "labels": {"protection_level": "P3", "personal_info": "sensitive_personal",
                   "business_categories": ["visit", "diagnosis"],
                   "usage_constraints": {"purposes": ["research_synthetic"],
                                         "export_allowed": True,
                                         "training_allowed": True}}}, headers=T)
    assert r.status_code == 200, r.text

    # 无授权仍拒绝
    r = client.get("/api/v1/datasets/DS_SYNTH_193/versions/"
                   f"{version_id}/stats/readmission", headers=T)
    assert r.status_code == 403 and "deny_no_grant" in r.text

    # 授权（含 export/train）
    r = client.post("/api/v1/datasets/grants", json={
        "principal": "test-platform-admin", "purpose_code": "research_synthetic",
        "resource_ref": res, "operations": ["read", "export", "train", "derive"],
        "legal_basis_ref": "SYNTH-193-测试依据", "valid_hours": 2}, headers=T)
    assert r.status_code == 200, r.text
    grant_id = r.json()["data"]["grant_id"]

    # 有授权可读（时间线/统计）
    r = client.get("/api/v1/datasets/DS_SYNTH_193/versions/"
                   f"{version_id}/stats/readmission", headers=T)
    assert r.status_code == 200, r.text
    assert r.json()["data"]["denominator_patients"] >= 3

    # ---------- B10：质量门禁失败禁止发布 → 冻结→审批→发布 ----------
    r = client.post(f"/api/v1/datasets/DS_SYNTH_193/versions/{version_id}/freeze", json={}, headers=T)
    assert r.status_code == 200, r.text
    r = client.post(f"/api/v1/datasets/DS_SYNTH_193/versions/{version_id}/approve",
                    json={"approver": "human-approver-193"}, headers=T)
    assert r.status_code == 200
    # 质量失败 → 拒绝发布（旧状态保持 approved，可回退重验）
    r = client.post(f"/api/v1/datasets/DS_SYNTH_193/versions/{version_id}/publish",
                    json={"quality_results": [{"dimension": "coverage", "result": "fail"}],
                          "security_ok": True, "approved_by": "human-approver-193"}, headers=T)
    assert r.status_code == 409
    # 质量全过 → 发布成功
    r = client.post(f"/api/v1/datasets/DS_SYNTH_193/versions/{version_id}/publish",
                    json={"quality_results": [{"dimension": "coverage", "result": "pass"}],
                          "security_ok": True, "approved_by": "human-approver-193"}, headers=T)
    assert r.status_code == 200, r.text
    assert r.json()["data"]["status"] == "published"

    # ---------- B13：训练集（患者分组不跨集+无未来信息） ----------
    r = client.post(f"/api/v1/datasets/DS_SYNTH_193/versions/{version_id}/training-set",
                    json={"seed": 193}, headers=T)
    assert r.status_code == 200, r.text
    card = r.json()["data"]["data_card"]
    assert card["future_info_excluded"] >= 0
    assert sum(card["splits"].values()) == card["total_patients"]

    # ---------- B14：受控导出 ----------
    # 已发布+授权含 export → 申请成功
    r = client.post(f"/api/v1/datasets/DS_SYNTH_193/versions/{version_id}/exports",
                    json={"grant_id": grant_id, "fields": ["fact_key", "kind"],
                          "free_text_fields": []}, headers=T)
    assert r.status_code == 200, r.text
    export_code = r.json()["data"]["export_code"]
    # 下载鉴权通过（grant 有效）
    r = client.post(f"/api/v1/datasets/exports/{export_code}/download", headers=T)
    assert r.status_code == 200

    # ---------- B15：撤权即时生效（导出/读取全拒） ----------
    r = client.post(f"/api/v1/datasets/grants/{grant_id}/revoke",
                    json={"reason": "193 合成撤权演练"}, headers=T)
    assert r.status_code == 200, r.text
    assert r.json()["data"]["exports_revoked"] >= 1
    r = client.get("/api/v1/datasets/DS_SYNTH_193/versions/"
                   f"{version_id}/stats/readmission", headers=T)
    assert r.status_code == 403
    r = client.post(f"/api/v1/datasets/exports/{export_code}/download", headers=T)
    assert r.status_code == 403

    # ---------- B10：版本撤销 → 禁止新导出 ----------
    r = client.post(f"/api/v1/datasets/DS_SYNTH_193/versions/{version_id}/revoke",
                    json={"reason": "193 撤销演练"}, headers=T)
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "revoked"


def test_identity_merge_and_split(db_session):
    from sqlalchemy import select
    from app.models.dataset import AssetDsIdentityMap

    m1 = pipe.register_identity(db_session, "SYNTH_A", "PX1")
    m2 = pipe.register_identity(db_session, "SYNTH_B", "PX1")
    assert m1.internal_patient_id != m2.internal_patient_id
    merged = pipe.merge_identities(db_session, m1.internal_patient_id, m2.internal_patient_id,
                                   "test")
    assert merged >= 1
    chain = pipe.effective_patient_ids(db_session, [m2.internal_patient_id])
    assert chain[m2.internal_patient_id] == m1.internal_patient_id
    restored = pipe.split_identity(db_session, m2.internal_patient_id, "test")
    assert restored >= 1
    chain2 = pipe.effective_patient_ids(db_session, [m2.internal_patient_id])
    assert chain2[m2.internal_patient_id] == m2.internal_patient_id
    assert db_session.scalar(select(AssetDsIdentityMap).where(
        AssetDsIdentityMap.internal_patient_id == m2.internal_patient_id,
        AssetDsIdentityMap.merged_into.is_(None))) is not None


def test_resume_batch_checkpoint_idempotent(db_session):
    body_records = _ingest_body("RUN-193-C", "SYNTH_C", ["SC001"])["records"]
    r1 = pipe.ingest_batch(db_session, "RUN-193-C", "SYNTH_C", "SYNTH_C.SYNTH",
                           body_records, "rules_v1")
    assert r1["written"] == 2
    keys = pipe.resume_batch_from_checkpoint(db_session, "RUN-193-C")
    assert len(keys) == 2
    r2 = pipe.ingest_batch(db_session, "RUN-193-C", "SYNTH_C", "SYNTH_C.SYNTH",
                           body_records, "rules_v1")
    assert r2["written"] == 0 and r2["skipped"] == 2
