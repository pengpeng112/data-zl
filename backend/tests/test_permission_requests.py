"""146 C1: permission request lifecycle, pagination, self-review and audit."""
import hashlib

from fastapi.testclient import TestClient

from app.core.db import SessionLocal
from app.main import app
from app.models.governance import ApiKey
from app.models.governance_base import AssetUserDataScope, AssetUserRole, GovernAuditLog

LIMITED_TOKEN = "test-token-pr-limited-2026"
LIMITED_USER = "test-pr-limited-user"


def _limited_client() -> TestClient:
    token_hash = hashlib.sha256(LIMITED_TOKEN.encode("utf-8")).hexdigest()
    db = SessionLocal()
    try:
        key = db.query(ApiKey).filter(ApiKey.key_name == "test-pr-limited").first()
        if not key:
            db.add(ApiKey(key_name="test-pr-limited", token_hash=token_hash, user_identifier=LIMITED_USER))
        else:
            key.token_hash = token_hash
            key.user_identifier = LIMITED_USER
            key.enabled = True
        db.commit()
    finally:
        db.close()
    return TestClient(app, headers={"Authorization": f"Bearer {LIMITED_TOKEN}"})


def _audit_actions(request_id: int) -> set[str]:
    db = SessionLocal()
    try:
        rows = db.query(GovernAuditLog).filter(
            GovernAuditLog.module == "permission",
            GovernAuditLog.entity_type == "change_request",
            GovernAuditLog.entity_ref == str(request_id),
        ).all()
        return {row.action for row in rows}
    finally:
        db.close()


def test_create_request_contract_and_validation(client: TestClient):
    client.post("/api/v1/permissions/seed?operator=tester")

    created = client.post("/api/v1/permission-requests", json={
        "request_kind": "role",
        "target_user_identifier": "pr-target-user",
        "role_code": "identity_admin",
        "reason": "岗位调整需要身份管理权限",
    })
    assert created.status_code == 200, created.text
    data = created.json()["data"]
    assert data["request_content"]["role_code"] == "identity_admin"
    assert data["reason"] == "岗位调整需要身份管理权限"
    assert data["requested_by"] == "test-platform-admin"
    assert data["status"] == "pending"
    assert data["created_at"]
    # Legacy aliases stay available for pre-146 clients.
    assert data["request_payload"] == data["request_content"]
    assert data["approval_status"] == "pending"

    scope = client.post("/api/v1/permission-requests", json={
        "request_kind": "data_scope",
        "target_user_identifier": "pr-target-user",
        "scope_type": "system",
        "system_code": "HIS",
        "reason": "科室数据治理需要 HIS 范围",
    })
    assert scope.status_code == 200, scope.text
    assert scope.json()["data"]["request_content"]["scope_type"] == "system"

    bad_role = client.post("/api/v1/permission-requests", json={
        "request_kind": "role", "target_user_identifier": "u", "role_code": "no_such_role", "reason": "测试用途",
    })
    assert bad_role.status_code == 400
    assert "role_code" in bad_role.json()["detail"]

    missing_scope = client.post("/api/v1/permission-requests", json={
        "request_kind": "data_scope", "target_user_identifier": "u", "reason": "测试用途",
    })
    assert missing_scope.status_code == 400
    assert "scope_type" in missing_scope.json()["detail"]

    bad_range = client.post("/api/v1/permission-requests", json={
        "request_kind": "data_scope", "target_user_identifier": "u", "scope_type": "system",
        "valid_from": "2026-08-02T00:00:00Z", "valid_to": "2026-08-01T00:00:00Z", "reason": "测试用途",
    })
    assert bad_range.status_code == 400

    short_reason = client.post("/api/v1/permission-requests", json={
        "request_kind": "role", "target_user_identifier": "u", "role_code": "identity_admin", "reason": "x",
    })
    assert short_reason.status_code == 422


def test_mine_and_pending_pagination(client: TestClient):
    client.post("/api/v1/permissions/seed?operator=tester")
    for i in range(3):
        res = client.post("/api/v1/permission-requests", json={
            "request_kind": "role",
            "target_user_identifier": f"pr-page-user-{i}",
            "role_code": "asset_viewer",
            "reason": f"分页验证 {i}",
        })
        assert res.status_code == 200, res.text

    page1 = client.get("/api/v1/permission-requests/mine?page=1&page_size=2")
    assert page1.status_code == 200
    body = page1.json()["data"]
    assert body["total"] == 3
    assert body["page"] == 1
    assert body["page_size"] == 2
    assert len(body["items"]) == 2
    page2 = client.get("/api/v1/permission-requests/mine?page=2&page_size=2")
    assert len(page2.json()["data"]["items"]) == 1

    pending = client.get("/api/v1/permission-requests/pending?page=1&page_size=2")
    assert pending.status_code == 200
    pending_body = pending.json()["data"]
    assert pending_body["total"] >= 3
    assert all(item["status"] == "pending" for item in pending_body["items"])


def test_approve_execute_revoke_flow_and_audit(client: TestClient, second_user_token: str):
    client.post("/api/v1/permissions/seed?operator=tester")
    created = client.post("/api/v1/permission-requests", json={
        "request_kind": "role",
        "target_user_identifier": "pr-flow-user",
        "role_code": "asset_viewer",
        "reason": "完整流转验证",
    })
    request_id = created.json()["data"]["id"]

    # Executing before approval must fail without state change.
    premature = client.post(f"/api/v1/permission-requests/{request_id}/execute")
    assert premature.status_code == 400

    approver = TestClient(app, headers={"Authorization": f"Bearer {second_user_token}"})
    approved = approver.patch(f"/api/v1/permission-requests/{request_id}/approve", json={"note": "同意开通"})
    assert approved.status_code == 200, approved.text
    assert approved.json()["data"]["status"] == "approved"
    assert approved.json()["data"]["approved_by"] == "test-approver-b"
    assert approved.json()["data"]["reason"] == "同意开通"

    executed = client.post(f"/api/v1/permission-requests/{request_id}/execute")
    assert executed.status_code == 200, executed.text
    assert executed.json()["data"]["status"] == "executed"
    assert executed.json()["data"]["executed_by"] == "test-platform-admin"

    db = SessionLocal()
    try:
        grant = db.query(AssetUserRole).filter(AssetUserRole.request_id == request_id).one()
        assert grant.user_identifier == "pr-flow-user"
        assert grant.role_code == "asset_viewer"
        assert grant.status == "active"
        assert grant.source == "request"
    finally:
        db.close()

    # Re-execution is refused: the request is no longer approved.
    again = client.post(f"/api/v1/permission-requests/{request_id}/execute")
    assert again.status_code == 400

    revoked = client.post(f"/api/v1/permission-requests/{request_id}/revoke")
    assert revoked.status_code == 200, revoked.text
    assert revoked.json()["data"]["status"] == "revoked"
    db = SessionLocal()
    try:
        grant = db.query(AssetUserRole).filter(AssetUserRole.request_id == request_id).one()
        assert grant.status == "revoked"
    finally:
        db.close()
    assert client.post(f"/api/v1/permission-requests/{request_id}/revoke").status_code == 404

    # Business write and audit rows share the same transaction history.
    actions = _audit_actions(request_id)
    assert {"create", "approve", "execute", "revoke"} <= actions


def test_data_scope_execute_creates_scope(client: TestClient, second_user_token: str):
    client.post("/api/v1/permissions/seed?operator=tester")
    created = client.post("/api/v1/permission-requests", json={
        "request_kind": "data_scope",
        "target_user_identifier": "pr-scope-user",
        "scope_type": "source",
        "source_code": "ods_8_216",
        "schema_name": "ODS",
        "reason": "数据范围执行验证",
    })
    request_id = created.json()["data"]["id"]
    approver = TestClient(app, headers={"Authorization": f"Bearer {second_user_token}"})
    assert approver.patch(f"/api/v1/permission-requests/{request_id}/approve", json={"note": None}).status_code == 200
    executed = client.post(f"/api/v1/permission-requests/{request_id}/execute")
    assert executed.status_code == 200, executed.text

    db = SessionLocal()
    try:
        scope = db.query(AssetUserDataScope).filter(AssetUserDataScope.request_id == request_id).one()
        assert scope.user_identifier == "pr-scope-user"
        assert scope.scope_type == "source"
        assert scope.source_code == "ods_8_216"
        assert scope.status == "active"
    finally:
        db.close()


def test_self_approval_and_duplicate_grant_blocked(client: TestClient, second_user_token: str):
    client.post("/api/v1/permissions/seed?operator=tester")
    created = client.post("/api/v1/permission-requests", json={
        "request_kind": "role",
        "target_user_identifier": "pr-self-user",
        "role_code": "asset_viewer",
        "reason": "自审拦截验证",
    })
    request_id = created.json()["data"]["id"]

    self_approve = client.patch(f"/api/v1/permission-requests/{request_id}/approve", json={"note": "自己批"})
    assert self_approve.status_code == 400
    assert "cannot approve own request" in self_approve.json()["detail"]
    self_reject = client.patch(f"/api/v1/permission-requests/{request_id}/reject", json={"note": "自己驳"})
    assert self_reject.status_code == 400
    assert "cannot reject own request" in self_reject.json()["detail"]

    approver = TestClient(app, headers={"Authorization": f"Bearer {second_user_token}"})
    assert approver.patch(f"/api/v1/permission-requests/{request_id}/approve").status_code == 200
    assert client.post(f"/api/v1/permission-requests/{request_id}/execute").status_code == 200

    # A second approved request for the same active grant conflicts on execute.
    duplicate = client.post("/api/v1/permission-requests", json={
        "request_kind": "role",
        "target_user_identifier": "pr-self-user",
        "role_code": "asset_viewer",
        "reason": "重复授予验证",
    })
    duplicate_id = duplicate.json()["data"]["id"]
    assert approver.patch(f"/api/v1/permission-requests/{duplicate_id}/approve").status_code == 200
    conflict = client.post(f"/api/v1/permission-requests/{duplicate_id}/execute")
    assert conflict.status_code == 409
    assert "already exists" in conflict.json()["detail"]


def test_reject_terminal_state(client: TestClient, second_user_token: str):
    client.post("/api/v1/permissions/seed?operator=tester")
    created = client.post("/api/v1/permission-requests", json={
        "request_kind": "role",
        "target_user_identifier": "pr-reject-user",
        "role_code": "asset_viewer",
        "reason": "驳回终态验证",
    })
    request_id = created.json()["data"]["id"]
    approver = TestClient(app, headers={"Authorization": f"Bearer {second_user_token}"})
    rejected = approver.patch(f"/api/v1/permission-requests/{request_id}/reject", json={"note": "材料不足"})
    assert rejected.status_code == 200
    assert rejected.json()["data"]["status"] == "rejected"
    assert rejected.json()["data"]["reason"] == "材料不足"
    # Rejected requests cannot be approved or executed afterwards.
    assert approver.patch(f"/api/v1/permission-requests/{request_id}/approve").status_code == 400
    assert client.post(f"/api/v1/permission-requests/{request_id}/execute").status_code == 400
    assert _audit_actions(request_id) >= {"create", "reject"}


def test_detail_access_and_operator_from_login_state(client: TestClient, second_user_token: str):
    client.post("/api/v1/permissions/seed?operator=tester")
    created = client.post("/api/v1/permission-requests", json={
        "request_kind": "role",
        "target_user_identifier": "pr-detail-user",
        "role_code": "asset_viewer",
        "reason": "详情与操作者验证",
    })
    request_id = created.json()["data"]["id"]

    detail = client.get(f"/api/v1/permission-requests/{request_id}")
    assert detail.status_code == 200
    assert detail.json()["data"]["requested_by"] == "test-platform-admin"

    approver = TestClient(app, headers={"Authorization": f"Bearer {second_user_token}"})
    other_detail = approver.get(f"/api/v1/permission-requests/{request_id}")
    assert other_detail.status_code == 200

    missing = client.get("/api/v1/permission-requests/999999")
    assert missing.status_code == 404


def test_unauthorized_and_overprivileged_access(client: TestClient):
    client.post("/api/v1/permissions/seed?operator=tester")
    anonymous = TestClient(app)
    assert anonymous.get("/api/v1/permission-requests/mine").status_code == 401
    assert anonymous.post("/api/v1/permission-requests", json={}).status_code == 401

    limited = _limited_client()
    denied_list = limited.get("/api/v1/permission-requests/mine")
    assert denied_list.status_code == 403
    assert "identity.permission_request.view" in denied_list.json()["detail"]
    denied_create = limited.post("/api/v1/permission-requests", json={
        "request_kind": "role", "target_user_identifier": "u", "role_code": "asset_viewer", "reason": "越权验证",
    })
    assert denied_create.status_code == 403
    assert "identity.permission_request.create" in denied_create.json()["detail"]
    denied_pending = limited.get("/api/v1/permission-requests/pending")
    assert denied_pending.status_code == 403
    assert "identity.permission_request.approve" in denied_pending.json()["detail"]
    denied_execute = limited.post("/api/v1/permission-requests/1/execute")
    assert denied_execute.status_code == 403
    assert "identity.permission_request.execute" in denied_execute.json()["detail"]
