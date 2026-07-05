import json


def _create_cr(client, requested_by="userA"):
    resp = client.post("/api/v1/govern/change-requests", json={
        "module": "identity",
        "entity_type": "account",
        "entity_ref": "user_001",
        "request_type": "disable_account",
        "requested_by": requested_by,
        "note": "测试审批流程",
    })
    assert resp.status_code == 200
    return resp.json()["data"]["id"]


def test_list_roles(client):
    resp = client.get("/api/v1/govern/roles")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert isinstance(data, list)


def test_upsert_role(client):
    resp = client.put("/api/v1/govern/roles", json={
        "role_code": "test-admin",
        "role_name_cn": "测试管理员",
        "description": "P5.9 测试用角色",
    })
    assert resp.status_code == 200
    assert resp.json()["data"]["role_code"] == "test-admin"

    resp = client.put("/api/v1/govern/roles", json={
        "role_code": "test-admin",
        "role_name_cn": "测试管理员(已更新)",
    })
    assert resp.status_code == 200


def test_add_permission(client):
    resp = client.post("/api/v1/govern/roles/test-admin/permissions", json={
        "role_code": "test-admin",
        "resource": "govern",
        "action": "read",
    })
    assert resp.status_code == 200
    assert resp.json()["data"]["id"] is not None


def test_list_permissions(client):
    resp = client.get("/api/v1/govern/roles/test-admin/permissions")
    assert resp.status_code == 200
    perms = resp.json()["data"]
    assert len(perms) >= 1


def test_remove_permission(client):
    resp = client.get("/api/v1/govern/roles/test-admin/permissions")
    perms = resp.json()["data"]
    if perms:
        perm_id = perms[0]["id"]
        resp = client.delete(f"/api/v1/govern/roles/test-admin/permissions/{perm_id}")
        assert resp.status_code == 200


def test_create_change_request(client):
    resp = client.post("/api/v1/govern/change-requests", json={
        "module": "identity",
        "entity_type": "account",
        "entity_ref": "user_001",
        "request_type": "disable_account",
        "requested_by": "userA",
        "note": "测试审批流程",
    })
    assert resp.status_code == 200
    assert resp.json()["data"]["approval_status"] == "draft"


def test_approve_change_request(client):
    cr_id = _create_cr(client)
    resp = client.patch(f"/api/v1/govern/change-requests/{cr_id}/approve", json={
        "approved_by": "userB",
        "note": "同意",
    })
    assert resp.status_code == 200
    assert resp.json()["data"]["approval_status"] == "approved"


def test_reject_self_approve(client):
    cr_id = _create_cr(client, requested_by="userA")
    resp = client.patch(f"/api/v1/govern/change-requests/{cr_id}/approve", json={
        "approved_by": "userA",
    })
    assert resp.status_code == 400


def test_list_change_requests(client):
    _create_cr(client)
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
    resp = client.put("/api/v1/govern/executors", json={
        "executor_code": "test-readonly-check",
        "executor_name_cn": "只读核查",
        "execution_mode": "readonly_sql",
        "risk_level": "low",
        "require_approval": False,
        "enabled": True,
    })
    assert resp.status_code == 200
    assert resp.json()["data"]["executor_code"] == "test-readonly-check"


def test_list_executors(client):
    test_upsert_executor(client)
    resp = client.get("/api/v1/govern/executors")
    assert resp.status_code == 200
    items = resp.json()["data"]
    assert isinstance(items, list)
    assert any(e["executor_code"] == "test-readonly-check" for e in items)


def test_assign_user_role(client):
    resp = client.post("/api/v1/govern/user-roles", json={
        "user_identifier": "test-user",
        "role_code": "test-admin",
    })
    assert resp.status_code == 200


def test_list_user_roles(client):
    test_assign_user_role(client)
    resp = client.get("/api/v1/govern/user-roles?user_identifier=test-user")
    assert resp.status_code == 200
    items = resp.json()["data"]
    assert len(items) >= 1


def test_cleanup(client):
    resp = client.get("/api/v1/govern/user-roles?user_identifier=test-user")
    for item in resp.json()["data"]:
        client.delete(f"/api/v1/govern/user-roles/{item['id']}")
    resp = client.delete("/api/v1/govern/roles/test-admin")
    assert resp.status_code == 200
