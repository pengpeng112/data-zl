"""Governance RBAC and change-request tests (isolation-safe)."""

from app.core.db import SessionLocal
from app.models.governance_base import GovernChangeRequest


def test_list_roles(client):
    resp = client.get("/api/v1/govern/roles")
    assert resp.status_code == 200
    assert isinstance(resp.json()["data"], list)


def test_upsert_role(client):
    resp = client.put(
        "/api/v1/govern/roles",
        json={
            "role_code": "test-admin",
            "role_name_cn": "测试管理员",
            "description": "P5.9 测试用角色",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["role_code"] == "test-admin"

    resp = client.put(
        "/api/v1/govern/roles",
        json={
            "role_code": "test-admin",
            "role_name_cn": "测试管理员(已更新)",
        },
    )
    assert resp.status_code == 200


def test_add_permission(client):
    client.put(
        "/api/v1/govern/roles",
        json={"role_code": "test-admin", "role_name_cn": "测试管理员"},
    )
    resp = client.post(
        "/api/v1/govern/roles/test-admin/permissions",
        json={"role_code": "test-admin", "resource": "govern", "action": "read"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["id"] is not None


def test_list_permissions(client):
    client.put(
        "/api/v1/govern/roles",
        json={"role_code": "test-admin", "role_name_cn": "测试管理员"},
    )
    client.post(
        "/api/v1/govern/roles/test-admin/permissions",
        json={"role_code": "test-admin", "resource": "govern", "action": "read"},
    )
    resp = client.get("/api/v1/govern/roles/test-admin/permissions")
    assert resp.status_code == 200
    assert len(resp.json()["data"]) >= 1


def test_remove_permission(client):
    client.put(
        "/api/v1/govern/roles",
        json={"role_code": "test-admin", "role_name_cn": "测试管理员"},
    )
    client.post(
        "/api/v1/govern/roles/test-admin/permissions",
        json={"role_code": "test-admin", "resource": "govern", "action": "read"},
    )
    resp = client.get("/api/v1/govern/roles/test-admin/permissions")
    perms = resp.json()["data"]
    assert perms
    perm_id = perms[0]["id"]
    resp = client.delete(f"/api/v1/govern/roles/test-admin/permissions/{perm_id}")
    assert resp.status_code == 200


def test_create_change_request(client):
    resp = client.post(
        "/api/v1/govern/change-requests",
        json={
            "module": "identity",
            "entity_type": "account",
            "entity_ref": "user_001",
            "request_type": "disable_account",
            "note": "测试审批流程",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["approval_status"] == "draft"


def test_approve_change_request(client):
    # requester must differ from current admin token user
    db = SessionLocal()
    try:
        cr = GovernChangeRequest(
            module="identity",
            entity_type="account",
            entity_ref="user_002",
            request_type="disable_account",
            requested_by="other-requester",
            approval_status="draft",
            note="for approve",
        )
        db.add(cr)
        db.commit()
        db.refresh(cr)
        cr_id = cr.id
    finally:
        db.close()

    resp = client.patch(
        f"/api/v1/govern/change-requests/{cr_id}/approve",
        json={"note": "同意"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["approval_status"] == "approved"


def test_reject_self_approve(client):
    # create as current user then approve as same user
    create = client.post(
        "/api/v1/govern/change-requests",
        json={
            "module": "identity",
            "entity_type": "account",
            "entity_ref": "user_self",
            "request_type": "disable_account",
            "note": "self",
        },
    )
    cr_id = create.json()["data"]["id"]
    resp = client.patch(f"/api/v1/govern/change-requests/{cr_id}/approve", json={"note": "no"})
    assert resp.status_code == 400


def test_list_change_requests(client):
    client.post(
        "/api/v1/govern/change-requests",
        json={
            "module": "identity",
            "entity_type": "account",
            "entity_ref": "user_003",
            "request_type": "disable_account",
        },
    )
    resp = client.get("/api/v1/govern/change-requests?module=identity")
    assert resp.status_code == 200
    assert resp.json()["data"]["total"] >= 1


def test_list_audit_logs(client):
    resp = client.get("/api/v1/govern/audit-logs")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert isinstance(data, dict)
    assert "items" in data


def test_upsert_executor(client):
    resp = client.put(
        "/api/v1/govern/executors",
        json={
            "executor_code": "test-readonly-check",
            "executor_name_cn": "只读核查",
            "execution_mode": "readonly_sql",
            "risk_level": "low",
            "require_approval": False,
            "enabled": True,
        },
    )
    assert resp.status_code == 200
