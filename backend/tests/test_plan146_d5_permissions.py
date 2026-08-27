"""146 D5: fine-grained write permissions on ops tools, dict medical, ai drafts, metadata changes."""
import hashlib

from fastapi.testclient import TestClient

from app.core.db import SessionLocal
from app.main import app
from app.models.governance import ApiKey
from app.models.metadata_change import AssetMetadataChangeEvent

LIMITED_TOKEN = "test-token-d5-limited-2026"
LIMITED_USER = "test-d5-limited-user"


def _limited_client() -> TestClient:
    token_hash = hashlib.sha256(LIMITED_TOKEN.encode("utf-8")).hexdigest()
    db = SessionLocal()
    try:
        key = db.query(ApiKey).filter(ApiKey.key_name == "test-d5-limited").first()
        if not key:
            db.add(ApiKey(key_name="test-d5-limited", token_hash=token_hash, user_identifier=LIMITED_USER))
        else:
            key.token_hash = token_hash
            key.user_identifier = LIMITED_USER
            key.enabled = True
        db.commit()
    finally:
        db.close()
    return TestClient(app, headers={"Authorization": f"Bearer {LIMITED_TOKEN}"})


TOOL_PAYLOAD = {
    "tool_code": "d5-perm-tool",
    "tool_name_cn": "D5 权限验证工具",
    "system_code": "ASSET_PLATFORM",
    "source_code": "asset",
    "tool_type": "query",
    "risk_level": "low",
    "execution_mode": "readonly_sql",
    "sql_or_endpoint_ref": "SELECT 1 AS ok",
    "enabled": True,
    "require_approval": True,
    "require_second_confirm": False,
}

MAPPING_ROW_PAYLOAD = {
    "category_code": "diagnosis",
    "local_code": "D5_PERM_CODE",
    "local_name": "D5 权限验证条目",
    "national_code": "S_D5",
    "national_name": "D5 标准条目",
}


def test_ops_tools_upsert_permission_matrix(client: TestClient):
    anonymous = TestClient(app)
    assert anonymous.put("/api/v1/ops/tools", json=TOOL_PAYLOAD).status_code == 401

    # 403 由 /ops 前缀角色门禁或 ops.tool.manage 细权限任一层拒绝。
    limited = _limited_client()
    denied = limited.put("/api/v1/ops/tools", json=TOOL_PAYLOAD)
    assert denied.status_code == 403

    allowed = client.put("/api/v1/ops/tools", json=TOOL_PAYLOAD)
    assert allowed.status_code == 200, allowed.text


def test_dict_medical_write_permission_matrix(client: TestClient):
    anonymous = TestClient(app)
    assert anonymous.put("/api/v1/dict-medical/mapping-rows", json=MAPPING_ROW_PAYLOAD).status_code == 401
    assert anonymous.post("/api/v1/dict-medical/sync/run", json={
        "source_system": "x", "target_system": "asset", "operator": "x",
    }).status_code == 401

    limited = _limited_client()
    # /dict-medical 前缀仅 platform_admin，细权限为第二层防线。
    denied_row = limited.put("/api/v1/dict-medical/mapping-rows", json=MAPPING_ROW_PAYLOAD)
    assert denied_row.status_code == 403
    denied_sync = limited.post("/api/v1/dict-medical/sync/run", json={
        "source_system": "x", "target_system": "asset", "operator": "x",
    })
    assert denied_sync.status_code == 403

    allowed_row = client.put("/api/v1/dict-medical/mapping-rows", json=MAPPING_ROW_PAYLOAD)
    assert allowed_row.status_code == 200, allowed_row.text
    # sync/run 有权成功由既有 test_dict_medical.py::test_run_medical_sync 覆盖。


def test_ai_draft_review_permission_matrix(client: TestClient):
    created = client.post("/api/v1/ai/propose-sql", json={
        "sql_text": "SELECT 1 AS total_cnt, 0 AS error_cnt",
        "title": "d5 perm draft",
    })
    assert created.status_code == 200, created.text
    draft_id = created.json()["data"]["draft_id"]

    anonymous = TestClient(app)
    assert anonymous.patch(f"/api/v1/ai/drafts/{draft_id}", json={
        "status": "approved", "reviewed_by": "anon",
    }).status_code == 401

    limited = _limited_client()
    denied = limited.patch(f"/api/v1/ai/drafts/{draft_id}", json={
        "status": "approved", "reviewed_by": LIMITED_USER,
    })
    assert denied.status_code == 403

    approved = client.patch(f"/api/v1/ai/drafts/{draft_id}", json={
        "status": "approved", "reviewed_by": "test-platform-admin",
    })
    assert approved.status_code == 200, approved.text


def test_metadata_change_edit_permission_matrix(client: TestClient):
    db = SessionLocal()
    try:
        event = AssetMetadataChangeEvent(
            snapshot_id_to=1, system_code="PYTEST", source_code="pytest_d5",
            namespace_name="PUBLIC", table_name="T_D5", column_name="C",
            change_type="column_added", severity="medium",
        )
        db.add(event)
        db.commit()
        event_id = event.id
    finally:
        db.close()

    anonymous = TestClient(app)
    assert anonymous.patch(f"/api/v1/metadata-changes/{event_id}?status=acknowledged").status_code == 401

    limited = _limited_client()
    denied = limited.patch(f"/api/v1/metadata-changes/{event_id}?status=acknowledged")
    assert denied.status_code == 403
    assert "metadata.change.edit" in denied.json()["detail"]

    allowed = client.patch(f"/api/v1/metadata-changes/{event_id}?status=acknowledged&assigned_to=d5-owner")
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["data"]["status"] == "acknowledged"
    assert allowed.json()["data"]["assigned_to"] == "d5-owner"
