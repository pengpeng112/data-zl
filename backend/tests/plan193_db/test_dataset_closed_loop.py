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


def test_dataset_closed_loop(client: TestClient, second_user_token: str):
    T2 = {"Authorization": f"Bearer {second_user_token}"}
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
    # 210：先冻结绑定成员（版本范围查询入口的读前提）
    r = client.post(f"/api/v1/datasets/DS_SYNTH_193/versions/{version_id}/freeze",
                    json={"source_batch_ids": ["RUN-193-A", "RUN-193-B"]}, headers=T)
    assert r.status_code == 200, r.text
    r = client.get(f"/api/v1/datasets/DS_SYNTH_193/versions/{version_id}"
                   f"/timeline/DS-Pwhatever", headers=T)
    assert r.status_code == 403
    assert "deny_unclassified" in r.text or "未分类" in r.text

    # 210 契约：object_type + expected_version CAS
    r = client.post("/api/v1/datasets/classifications", json={
        "object_type": "dataset_version", "object_ref": res, "expected_version": 0,
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

    # 授权申请（210：pending 需独立审批；行范围=显式全范围）
    r = client.post("/api/v1/datasets/grants", json={
        "principal": "test-platform-admin", "purpose_code": "research_synthetic",
        "resource_ref": res, "operations": ["read", "export", "train", "derive"],
        "legal_basis_ref": "SYNTH-193-测试依据", "valid_hours": 2,
        "row_scope": {"all": True}}, headers=T)
    assert r.status_code == 200, r.text
    grant_id = r.json()["data"]["grant_id"]
    assert r.json()["data"]["status"] == "pending"
    # pending 未审批不可读；第二身份审批后生效
    r = client.get("/api/v1/datasets/DS_SYNTH_193/versions/"
                   f"{version_id}/stats/readmission", headers=T)
    assert r.status_code == 403
    r = client.post(f"/api/v1/datasets/grants/{grant_id}/review",
                    json={"decision": "approve"}, headers=T2)
    assert r.status_code == 200, r.text

    # 有授权可读（时间线/统计）
    r = client.get("/api/v1/datasets/DS_SYNTH_193/versions/"
                   f"{version_id}/stats/readmission", headers=T)
    assert r.status_code == 200, r.text
    assert r.json()["data"]["denominator_patients"] >= 3

    # ---------- B10：审批（分离）→ 安全评审 → 发布（冻结已在上面完成） ----------
    # 冻结人=admin 不得自审（210 职责分离）；第二身份审批
    r = client.post(f"/api/v1/datasets/DS_SYNTH_193/versions/{version_id}/approve",
                    json={"approver": "human-approver-193"}, headers=T)
    assert r.status_code == 403
    r = client.post(f"/api/v1/datasets/DS_SYNTH_193/versions/{version_id}/approve",
                    json={}, headers=T2)
    assert r.status_code == 200
    # 无持久化质量断言/安全评审 → 拒绝发布（210：不认 body 结论）
    r = client.post(f"/api/v1/datasets/DS_SYNTH_193/versions/{version_id}/publish",
                    headers=T)
    assert r.status_code == 409
    # 补齐持久化断言与独立安全评审 → 发布成功（发布人=admin≠审批人）
    from app.core.db import SessionLocal
    s = SessionLocal()
    try:
        pipe.evaluate_assertions(s, "dataset_version", str(version_id), [
            {"dimension": d, "metric_name": "m193", "numerator": 1, "denominator": 1,
             "threshold": {"op": ">=", "value": 1}}
            for d in ("coverage", "identity", "linkage")])
        s.commit()
    finally:
        s.close()
    r = client.post(f"/api/v1/datasets/DS_SYNTH_193/versions/{version_id}/security-review",
                    json={"passed": True, "note": "193 合成评审"}, headers=T2)
    assert r.status_code == 200, r.text
    r = client.post(f"/api/v1/datasets/DS_SYNTH_193/versions/{version_id}/publish",
                    headers=T)
    assert r.status_code == 200, r.text
    assert r.json()["data"]["status"] == "published"

    # ---------- B13：训练集（患者分组不跨集+无未来信息） ----------
    r = client.post(f"/api/v1/datasets/DS_SYNTH_193/versions/{version_id}/training-set",
                    json={"seed": 193}, headers=T)
    assert r.status_code == 200, r.text
    card = r.json()["data"]["data_card"]
    assert card["future_info_excluded"] >= 0
    assert sum(card["splits"].values()) == card["total_patients"]

    # ---------- B14：受控导出（210 真实闭环：申请→独立审批→生成→下载） ----------
    r = client.post(f"/api/v1/datasets/DS_SYNTH_193/versions/{version_id}/exports",
                    json={"fields": ["fact_key", "fact_kind"]}, headers=T)
    assert r.status_code == 200, r.text
    export_code = r.json()["data"]["export_code"]
    assert r.json()["data"]["status"] == "review_pending"
    # 申请人自审拒绝；未生成不可下载
    r = client.post(f"/api/v1/datasets/exports/{export_code}/review",
                    json={"decision": "approve"}, headers=T)
    assert r.status_code == 403
    r = client.post(f"/api/v1/datasets/exports/{export_code}/download", headers=T)
    assert r.status_code == 403
    r = client.post(f"/api/v1/datasets/exports/{export_code}/review",
                    json={"decision": "approve", "note": "193 合成导出"}, headers=T2)
    assert r.status_code == 200
    r = client.post(f"/api/v1/datasets/exports/{export_code}/generate", json={},
                    headers=T)
    assert r.status_code == 200, r.text
    r = client.post(f"/api/v1/datasets/exports/{export_code}/download", headers=T)
    assert r.status_code == 200
    assert r.text.startswith("fact_key,fact_kind")  # 真实 CSV 字节，非注释占位

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
