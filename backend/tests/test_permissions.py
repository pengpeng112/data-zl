from fastapi.testclient import TestClient

from app.core.db import SessionLocal
from app.core.config import settings
from app.main import app
from app.models.governance import ApiKey


def test_permission_seed_and_role_matrix(client: TestClient):
    seed = client.post("/api/v1/permissions/seed?operator=tester")
    assert seed.status_code == 200, seed.text

    roles = client.get("/api/v1/permissions/roles")
    assert roles.status_code == 200
    role_codes = {item["role_code"] for item in roles.json()["data"]}
    assert "platform_admin" in role_codes
    assert "identity_admin" in role_codes

    resources = client.get("/api/v1/permissions/resources")
    assert resources.status_code == 200
    codes = {item["code"] for item in resources.json()["data"]}
    assert "identity.role.manage" in codes
    assert "ops.run.execute" in codes

    matrix = client.get("/api/v1/permissions/roles/identity_admin/matrix")
    assert matrix.status_code == 200
    assert "identity.role.manage" in matrix.json()["data"]["granted"]

    update = client.put("/api/v1/permissions/roles/asset_viewer/matrix", json={
        "permissions": ["asset", "asset.table.view"],
        "operator": "tester",
        "reason": "unit test",
    })
    assert update.status_code == 200, update.text
    assert update.json()["data"]["granted"] == ["asset", "asset.table.view"]


def test_user_roles_and_effective_permissions(client: TestClient):
    client.post("/api/v1/permissions/seed?operator=tester")
    grant = client.put("/api/v1/permissions/users/user-perm-test/roles", json={
        "user_identifier": "user-perm-test",
        "role_codes": ["asset_viewer", "ai_user"],
        "granted_by": "tester",
        "reason": "unit test",
    })
    assert grant.status_code == 200, grant.text
    assert grant.json()["data"]["roles"] == ["ai_user", "asset_viewer"]

    effective = client.get("/api/v1/permissions/users/user-perm-test/permissions")
    assert effective.status_code == 200
    data = effective.json()["data"]
    assert "asset_viewer" in data["roles"]
    assert "asset.graph.view" in data["permissions"]
    assert "ai.draft.view" in data["permissions"]


def test_api_key_binding_and_me_permissions(client: TestClient):
    client.post("/api/v1/permissions/seed?operator=tester")
    token = "permission-test-token"
    db = SessionLocal()
    try:
        key = db.query(ApiKey).filter(ApiKey.key_name == "permission-test-key").first()
        if not key:
            key = ApiKey(key_name="permission-test-key", token=token, enabled=True)
            db.add(key)
            db.commit()
            db.refresh(key)
        else:
            key.token = token
            key.enabled = True
            key.user_identifier = None
            db.commit()
        key_id = key.id
    finally:
        db.close()

    client.put("/api/v1/permissions/users/key-bound-user/roles", json={
        "user_identifier": "key-bound-user",
        "role_codes": ["identity_admin"],
        "granted_by": "tester",
    })
    bind = client.patch(f"/api/v1/permissions/api-keys/{key_id}/bind", json={
        "key_id": key_id,
        "user_identifier": "key-bound-user",
        "operator": "tester",
    })
    assert bind.status_code == 200, bind.text

    bound_client = TestClient(app, headers={"Authorization": f"Bearer {token}"})
    me = bound_client.get("/api/v1/permissions/me")
    assert me.status_code == 200
    data = me.json()["data"]
    assert data["user_identifier"] == "key-bound-user"
    assert "identity_admin" in data["roles"]
    assert "identity.role.manage" in data["permissions"]

def test_permission_audit_query(client: TestClient):
    client.post("/api/v1/permissions/seed?operator=tester")
    client.put("/api/v1/permissions/roles/asset_viewer/matrix", json={
        "permissions": ["asset", "asset.table.view", "asset.graph.view"],
        "operator": "audit-tester",
        "reason": "audit query test",
    })
    client.put("/api/v1/permissions/users/audit-user/roles", json={
        "user_identifier": "audit-user",
        "role_codes": ["asset_viewer"],
        "granted_by": "audit-tester",
        "reason": "audit query test",
    })

    audit = client.get("/api/v1/permissions/audit?limit=20")
    assert audit.status_code == 200, audit.text
    rows = audit.json()["data"]
    assert any(row["action"] == "update_role_matrix" and row["entity_ref"] == "asset_viewer" for row in rows)
    assert any(row["action"] == "replace_user_roles" and row["entity_ref"] == "audit-user" for row in rows)

    filtered = client.get("/api/v1/permissions/audit?entity_type=user&entity_ref=audit-user")
    assert filtered.status_code == 200, filtered.text
    filtered_rows = filtered.json()["data"]
    assert filtered_rows
    assert all(row["entity_type"] == "user" and row["entity_ref"] == "audit-user" for row in filtered_rows)

def test_unbound_token_strict_mode_blocks_protected_routes(client: TestClient):
    token = "permission-unbound-token"
    db = SessionLocal()
    try:
        key = db.query(ApiKey).filter(ApiKey.key_name == "permission-unbound-key").first()
        if not key:
            key = ApiKey(key_name="permission-unbound-key", token=token, enabled=True, user_identifier=None)
            db.add(key)
        else:
            key.token = token
            key.enabled = True
            key.user_identifier = None
        db.commit()
    finally:
        db.close()

    unbound_client = TestClient(app, headers={"Authorization": f"Bearer {token}"})
    original = settings.rbac_require_bound_token
    try:
        settings.rbac_require_bound_token = False
        compatible = unbound_client.get("/api/v1/identity/persons")
        assert compatible.status_code != 403

        settings.rbac_require_bound_token = True
        blocked = unbound_client.get("/api/v1/identity/persons")
        assert blocked.status_code == 403
        assert blocked.json()["message"] == "权限不足"
    finally:
        settings.rbac_require_bound_token = original