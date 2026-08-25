"""149 P1b: 值域知识库 API —— 提交/冲突检测/人工确认/版本时间线/权限门禁。"""
from __future__ import annotations

import hashlib

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models.governance_base import AssetRolePermission, GovernAuditLog
from app.models.value_domain import AssetColumnValueDomain

BASE = "/api/v1/value-domains"

AI_USER_TOKEN = "test-token-ai-user-149"
AI_USER = "test-ai-user-149"


def _seed_domain_payload(**overrides) -> dict:
    payload = {
        "system_code": "HIS_SOURCE",
        "source_code": "his_source_10_10_10_15",
        "schema_name": "MEDREC",
        "table_name": "PAT_VISIT",
        "column_name": "DISCHARGE_DISPOSITION",
        "code": "4",
        "meaning": "非医嘱离院（自愿离院）",
        "domain_kind": "enum",
        "evidences": [
            {
                "source_type": "live_probe",
                "source_system": "HIS",
                "method": "2026-08 实测",
                "sample_count": 120,
                "snippet_ref": "148 §1",
            }
        ],
    }
    payload.update(overrides)
    return payload


@pytest.fixture()
def ai_user_client(client: TestClient) -> TestClient:
    """仅持 ai_user 角色（value_domain.read+submit，无 confirm）的客户端。"""
    from app.core.db import SessionLocal
    from app.models.governance import ApiKey
    from app.models.governance_base import AssetRole, AssetUserRole

    db = SessionLocal()
    try:
        if not db.scalar(select(AssetRole).where(AssetRole.role_code == "ai_user")):
            db.add(AssetRole(role_code="ai_user", role_name_cn="AI 协作用户", role_type="builtin"))
        if not db.scalar(
            select(AssetUserRole).where(
                AssetUserRole.user_identifier == AI_USER,
                AssetUserRole.role_code == "ai_user",
            )
        ):
            db.add(AssetUserRole(user_identifier=AI_USER, role_code="ai_user", status="active"))
        for resource in ("value_domain.read", "value_domain.submit"):
            if not db.scalar(
                select(AssetRolePermission).where(
                    AssetRolePermission.role_code == "ai_user",
                    AssetRolePermission.resource == resource,
                    AssetRolePermission.action == "access",
                )
            ):
                db.add(AssetRolePermission(role_code="ai_user", resource=resource, action="access"))
        existing = db.query(ApiKey).filter(ApiKey.key_name == "test-ai-user-149").first()
        token_hash = hashlib.sha256(AI_USER_TOKEN.encode("utf-8")).hexdigest()
        if not existing:
            db.add(ApiKey(key_name="test-ai-user-149", token_hash=token_hash, user_identifier=AI_USER))
        else:
            existing.token_hash = token_hash
            existing.token = None
            existing.user_identifier = AI_USER
            existing.enabled = True
        db.commit()
    finally:
        db.close()
    return TestClient(client.app, headers={"Authorization": f"Bearer {AI_USER_TOKEN}"})


def test_submit_creates_pending_with_evidence_and_version(client):
    resp = client.post(BASE, json=_seed_domain_payload())
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["created"] is True
    assert data["status"] == "pending"
    assert data["conflict_status"] == "none"
    assert data["version_no"] == 1
    assert data["evidence_count"] == 1

    detail = client.get(f"{BASE}/{data['id']}").json()["data"]
    assert detail["evidences"][0]["source_type"] == "live_probe"
    assert detail["evidences"][0]["sample_count"] == 120

    versions = client.get(f"{BASE}/{data['id']}/versions").json()["data"]
    assert versions["current_version_no"] == 1
    assert versions["items"][0]["change_reason"] == "submit"


def test_submit_evidence_required(client):
    payload = _seed_domain_payload()
    payload["evidences"] = []
    resp = client.post(BASE, json=payload)
    assert resp.status_code == 422


def test_submit_same_meaning_attaches_evidence_idempotently(client):
    first = client.post(BASE, json=_seed_domain_payload()).json()["data"]
    again = client.post(
        BASE,
        json=_seed_domain_payload(
            evidences=[
                {
                    "source_type": "cross_system",
                    "source_system": "JHEMR",
                    "method": "report.r_pat_visit 交叉验证",
                    "sample_count": 128,
                    "snippet_ref": "148 §1",
                }
            ]
        ),
    )
    assert again.status_code == 200, again.text
    data = again.json()["data"]
    assert data["created"] is False
    assert data["attached"] is True
    assert data["id"] == first["id"]
    assert data["evidence_count"] == 2

    # 完全相同的证据重复提交不追加（幂等）
    third = client.post(BASE, json=_seed_domain_payload())
    assert third.status_code == 200
    assert third.json()["data"]["appended_evidences"] == 0


def test_conflicting_meaning_marks_conflict_and_lists_competing(client):
    created = client.post(BASE, json=_seed_domain_payload()).json()["data"]
    resp = client.post(
        BASE,
        json=_seed_domain_payload(meaning="死亡"),  # 与 2026-08-24 事故同型：含义写反
    )
    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert detail["domain_id"] == created["id"]
    assert detail["conflict_status"] == "conflicted"
    meanings = {m["source"]: m["meaning"] for m in detail["competing_meanings"]}
    assert meanings["existing"] == "非医嘱离院（自愿离院）"
    assert meanings["proposed"] == "死亡"

    # 冲突列表可见
    conflicted = client.get(BASE, params={"conflicted": True}).json()["data"]
    assert conflicted["total"] == 1
    assert conflicted["items"][0]["id"] == created["id"]


def test_conflicted_record_not_in_injection_and_requires_resolution(client, db_session):
    created = client.post(BASE, json=_seed_domain_payload()).json()["data"]
    client.post(BASE, json=_seed_domain_payload(meaning="死亡"))

    from app.services.value_domain_service import confirmed_domains_for_injection

    # pending + conflicted 均不进注入
    assert all(d["id"] != created["id"] for d in confirmed_domains_for_injection(db_session))

    # conflicted 不可直接 confirm
    resp = client.patch(f"{BASE}/{created['id']}/confirm", json={"reason": "跳过裁决"})
    assert resp.status_code == 409

    # 人工裁决 → 冲突解除 → 可 confirm
    resolved = client.patch(
        f"{BASE}/{created['id']}/resolve-conflict",
        json={"meaning": "非医嘱离院（自愿离院）", "reason": "以 JHEMR 交叉验证为准"},
    )
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["data"]["conflict_status"] == "none"

    confirmed = client.patch(
        f"{BASE}/{created['id']}/confirm", json={"reason": "用户 2026-08-24 确认"}
    )
    assert confirmed.status_code == 200
    data = confirmed.json()["data"]
    assert data["status"] == "confirmed"
    # 版本时间线：submit(1) → resolve_conflict(2) → confirm(3)
    assert data["version_no"] == 3
    assert data["confirmed_by"]

    injected = [d for d in confirmed_domains_for_injection(db_session) if d["id"] == created["id"]]
    assert len(injected) == 1
    assert injected[0]["version_no"] == 3


def test_confirm_then_deprecate_exits_injection(client, db_session):
    from app.services.value_domain_service import confirmed_domains_for_injection

    created = client.post(BASE, json=_seed_domain_payload(code="5", meaning="死亡")).json()["data"]
    cid = client.patch(f"{BASE}/{created['id']}/confirm", json={"reason": "148 确认"}).json()["data"]
    assert cid["version_no"] == 2
    assert any(d["id"] == created["id"] for d in confirmed_domains_for_injection(db_session))

    dep = client.patch(
        f"{BASE}/{created['id']}/deprecate", json={"reason": "口径废弃"}
    ).json()["data"]
    assert dep["status"] == "deprecated"
    assert all(d["id"] != created["id"] for d in confirmed_domains_for_injection(db_session))


def test_updated_since_incremental(client):
    created = client.post(BASE, json=_seed_domain_payload(code="1", meaning="医嘱离院")).json()["data"]
    later = client.get(BASE, params={"updated_since": "2000-01-01T00:00:00Z"}).json()["data"]
    assert later["total"] >= 1
    none_later = client.get(BASE, params={"updated_since": "2999-01-01T00:00:00Z"}).json()["data"]
    assert none_later["total"] == 0


def test_writes_are_audited(client, db_session):
    client.post(BASE, json=_seed_domain_payload(code="2", meaning="医嘱转院"))
    logs = db_session.scalars(
        select(GovernAuditLog).where(GovernAuditLog.module == "value_domain")
    ).all()
    assert any(log.action == "submit" for log in logs)


def test_ai_role_can_submit_but_not_confirm(ai_user_client):
    resp = ai_user_client.post(BASE, json=_seed_domain_payload(code="7", meaning="损伤/中毒"))
    assert resp.status_code == 201, resp.text
    domain_id = resp.json()["data"]["id"]

    denied = ai_user_client.patch(f"{BASE}/{domain_id}/confirm", json={"reason": "AI 自行确认"})
    assert denied.status_code == 403
    assert "value_domain.confirm" in denied.json()["detail"]


def test_unauthenticated_cannot_write(client):
    anon = TestClient(client.app)
    resp = anon.get(BASE)
    assert resp.status_code == 401


def test_dissenting_evidence_triggers_conflict(client):
    created = client.post(BASE, json=_seed_domain_payload(code="3")).json()["data"]
    resp = client.post(
        f"{BASE}/{created['id']}/evidences",
        json={
            "source_type": "cross_system",
            "source_system": "JHEMR",
            "observed_meaning": "对立观测含义",
            "method": "交叉验证不一致",
        },
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["conflict_detected"] is True
    assert data["conflict_status"] == "conflicted"
    assert data["competing_meanings"][1]["meaning"] == "对立观测含义"
