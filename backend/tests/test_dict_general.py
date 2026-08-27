"""146 C2: dict/general canonical contract, CRUD, import preview and permissions."""
import hashlib

from fastapi.testclient import TestClient

from app.core.db import SessionLocal
from app.main import app
from app.models.governance import ApiKey
from app.models.governance_base import AssetUserRole, GovernAuditLog

DICT_ADMIN_TOKEN = "test-token-dict-admin-2026"
DICT_ADMIN_USER = "test-dict-admin-user"


def _dict_admin_client(client: TestClient) -> TestClient:
    """A user holding dict_admin: prefix gate passes, view/edit granted, import not."""
    client.post("/api/v1/permissions/seed?operator=tester")
    token_hash = hashlib.sha256(DICT_ADMIN_TOKEN.encode("utf-8")).hexdigest()
    db = SessionLocal()
    try:
        key = db.query(ApiKey).filter(ApiKey.key_name == "test-dict-admin").first()
        if not key:
            db.add(ApiKey(key_name="test-dict-admin", token_hash=token_hash, user_identifier=DICT_ADMIN_USER))
        else:
            key.token_hash = token_hash
            key.user_identifier = DICT_ADMIN_USER
            key.enabled = True
        if not db.query(AssetUserRole).filter(
            AssetUserRole.user_identifier == DICT_ADMIN_USER,
            AssetUserRole.role_code == "dict_admin",
        ).first():
            db.add(AssetUserRole(user_identifier=DICT_ADMIN_USER, role_code="dict_admin", status="active"))
        db.commit()
    finally:
        db.close()
    return TestClient(app, headers={"Authorization": f"Bearer {DICT_ADMIN_TOKEN}"})


def _audit_actions(module: str, entity_ref: str) -> set[str]:
    db = SessionLocal()
    try:
        rows = db.query(GovernAuditLog).filter(
            GovernAuditLog.module == module,
            GovernAuditLog.entity_ref == entity_ref,
        ).all()
        return {row.action for row in rows}
    finally:
        db.close()


def test_categories_and_standard_items_crud(client: TestClient):
    client.post("/api/v1/permissions/seed?operator=tester")
    created = client.put("/api/v1/dictionaries/categories", json={
        "category_code": "test_gender",
        "category_name_cn": "性别代码",
        "standard_system": "GB/T 2261.1",
        "enabled": True,
    })
    assert created.status_code == 200, created.text

    listed = client.get("/api/v1/dictionaries/categories")
    assert listed.status_code == 200
    codes = {item["category_code"] for item in listed.json()["data"]}
    assert "test_gender" in codes

    updated = client.put("/api/v1/dictionaries/categories", json={
        "category_code": "test_gender",
        "category_name_cn": "性别代码（修订）",
        "standard_system": "GB/T 2261.1",
        "enabled": False,
    })
    assert updated.status_code == 200
    rows = {item["category_code"]: item for item in client.get("/api/v1/dictionaries/categories").json()["data"]}
    assert rows["test_gender"]["category_name_cn"] == "性别代码（修订）"
    assert rows["test_gender"]["enabled"] is False

    # Standard items use standard_code / standard_name_cn and require an existing category.
    ok = client.put("/api/v1/dictionaries/standard-items", json={
        "category_code": "test_gender",
        "standard_code": "1",
        "standard_name_cn": "男性",
        "status": "active",
    })
    assert ok.status_code == 200, ok.text
    bad_category = client.put("/api/v1/dictionaries/standard-items", json={
        "category_code": "no_such_category", "standard_code": "1", "standard_name_cn": "x",
    })
    assert bad_category.status_code == 400

    for code, name in [("2", "女性"), ("9", "未说明"), ("0", "未知")]:
        assert client.put("/api/v1/dictionaries/standard-items", json={
            "category_code": "test_gender", "standard_code": code, "standard_name_cn": name,
        }).status_code == 200

    page = client.get("/api/v1/dictionaries/standard-items?category_code=test_gender&page=1&page_size=2")
    body = page.json()["data"]
    assert body["total"] == 4
    assert len(body["items"]) == 2
    # Lexicographic order over text codes: 0,1,2,9.
    assert {item["standard_code"] for item in body["items"]} == {"0", "1"}

    keyword = client.get("/api/v1/dictionaries/standard-items?category_code=test_gender&keyword=女性")
    assert keyword.json()["data"]["total"] == 1
    assert keyword.json()["data"]["items"][0]["standard_name_cn"] == "女性"
    assert _audit_actions("dict_general", "test_gender") >= {"upsert_category"}


def test_system_items_pagination_upsert_and_toggle(client: TestClient):
    client.post("/api/v1/permissions/seed?operator=tester")
    client.put("/api/v1/dictionaries/categories", json={
        "category_code": "test_dept", "category_name_cn": "科室类别", "enabled": True,
    })
    for i in range(3):
        created = client.put("/api/v1/dictionaries/system-items", json={
            "category_code": "test_dept",
            "system_code": "HIS",
            "system_item_code": f"D{i}",
            "system_item_name_cn": f"科室{i}",
            "source_table": "COMM.SYS_DEPARTMENT",
        })
        assert created.status_code == 200, created.text
        assert created.json()["data"]["created"] is True

    again = client.put("/api/v1/dictionaries/system-items", json={
        "category_code": "test_dept", "system_code": "HIS",
        "system_item_code": "D0", "system_item_name_cn": "科室0（改名）",
    })
    assert again.status_code == 200
    assert again.json()["data"]["created"] is False

    page = client.get("/api/v1/dictionaries/system-items?system_code=HIS&page=1&page_size=2")
    body = page.json()["data"]
    assert body["total"] == 3
    assert len(body["items"]) == 2
    assert all(item["enabled"] is True for item in body["items"])

    keyword = client.get("/api/v1/dictionaries/system-items?system_code=HIS&keyword=科室2")
    assert keyword.json()["data"]["total"] == 1
    assert keyword.json()["data"]["items"][0]["system_item_code"] == "D2"

    item_id = keyword.json()["data"]["items"][0]["id"]
    toggled = client.patch(f"/api/v1/dictionaries/system-items/{item_id}/enabled", json={"enabled": False})
    assert toggled.status_code == 200, toggled.text
    assert toggled.json()["data"]["enabled"] is False

    disabled_filter = client.get("/api/v1/dictionaries/system-items?system_code=HIS&enabled=false")
    assert disabled_filter.json()["data"]["total"] == 1
    # raw_status stays a separate evidence field, not the platform switch.
    assert "raw_status" in disabled_filter.json()["data"]["items"][0]

    assert client.patch("/api/v1/dictionaries/system-items/999999/enabled", json={"enabled": True}).status_code == 404
    assert _audit_actions("dict_general", "test_dept:HIS:D2") >= {"upsert_system_item", "toggle_system_item"}


def test_import_preview_is_zero_write_and_apply_reports_counts(client: TestClient):
    client.post("/api/v1/permissions/seed?operator=tester")
    client.put("/api/v1/dictionaries/categories", json={
        "category_code": "test_freq", "category_name_cn": "频次代码", "enabled": True,
    })
    items = [
        {"system_item_code": "QD", "system_item_name_cn": "每日一次"},
        {"system_item_code": "BID", "system_item_name_cn": "每日两次"},
    ]

    preview = client.post("/api/v1/dictionaries/import", json={
        "category_code": "test_freq", "system_code": "HIS", "items": items, "dry_run": True,
    })
    assert preview.status_code == 200, preview.text
    assert preview.json()["data"] == {
        "dry_run": True, "created": 2, "updated": 0, "rejected": 0, "errors": [],
    }
    total_after_preview = client.get("/api/v1/dictionaries/system-items?category_code=test_freq").json()["data"]["total"]
    assert total_after_preview == 0, "dry_run must not persist rows"

    applied = client.post("/api/v1/dictionaries/import", json={
        "category_code": "test_freq", "system_code": "HIS", "items": items,
    })
    assert applied.status_code == 200
    assert applied.json()["data"]["created"] == 2
    assert applied.json()["data"]["dry_run"] is False

    reimport = client.post("/api/v1/dictionaries/import", json={
        "category_code": "test_freq", "system_code": "HIS", "items": items,
    })
    assert reimport.json()["data"] == {
        "dry_run": False, "created": 0, "updated": 2, "rejected": 0, "errors": [],
    }

    invalid = client.post("/api/v1/dictionaries/import", json={
        "category_code": "test_freq", "system_code": "HIS",
        "items": [
            {"system_item_code": "", "system_item_name_cn": "无编码"},
            {"system_item_code": "NONAME", "system_item_name_cn": " "},
            {"system_item_code": "QD", "system_item_name_cn": "首个 QD 合法，按更新计"},
            {"system_item_code": "QD", "system_item_name_cn": "载荷内重复"},
            {"system_item_code": "TID", "system_item_name_cn": "每日三次"},
        ],
    })
    body = invalid.json()["data"]
    assert body["created"] == 1
    assert body["updated"] == 1
    assert body["rejected"] == 3
    reasons = {error["reason"] for error in body["errors"]}
    assert "system_item_code required (1-200 chars)" in reasons
    assert "system_item_name_cn required (1-500 chars)" in reasons
    assert "duplicate system_item_code in payload" in reasons
    assert len(body["errors"]) <= 20

    empty = client.post("/api/v1/dictionaries/import", json={
        "category_code": "test_freq", "system_code": "HIS", "items": [],
    })
    assert empty.status_code == 400
    unknown = client.post("/api/v1/dictionaries/import", json={
        "category_code": "no_such_category", "system_code": "HIS", "items": items,
    })
    assert unknown.status_code == 400
    assert _audit_actions("dict_general", "test_freq:HIS") >= {"import_system_items"}


def test_mappings_upsert_uses_real_fields_without_duplicates(client: TestClient):
    client.post("/api/v1/permissions/seed?operator=tester")
    client.put("/api/v1/dictionaries/categories", json={
        "category_code": "test_map", "category_name_cn": "映射测试", "enabled": True,
    })
    payload = {
        "category_code": "test_map",
        "standard_code": "1",
        "system_code": "HIS",
        "system_item_code": "M",
        "mapping_type": "equivalent",
        "confidence": "high",
    }
    first = client.put("/api/v1/dictionaries/mappings", json=payload)
    assert first.status_code == 200, first.text
    mapping_id = first.json()["data"]["id"]

    second = client.put("/api/v1/dictionaries/mappings", json=payload)
    assert second.status_code == 200
    assert second.json()["data"]["id"] == mapping_id, "same triple must update, not duplicate"

    listed = client.get("/api/v1/dictionaries/mappings?category_code=test_map&system_code=HIS")
    body = listed.json()["data"]
    assert body["total"] == 1
    row = body["items"][0]
    assert row["system_code"] == "HIS"
    assert row["system_item_code"] == "M"
    assert "target_system" not in row


def test_dict_general_permission_matrix(client: TestClient):
    client.post("/api/v1/permissions/seed?operator=tester")

    anonymous = TestClient(app)
    assert anonymous.get("/api/v1/dictionaries/categories").status_code == 401

    no_role_token = "test-token-dict-norole-2026"
    db = SessionLocal()
    try:
        db.add(ApiKey(key_name="test-dict-norole",
                      token_hash=hashlib.sha256(no_role_token.encode("utf-8")).hexdigest(),
                      user_identifier="test-dict-norole-user"))
        db.commit()
    finally:
        db.close()
    blocked = TestClient(app, headers={"Authorization": f"Bearer {no_role_token}"})
    assert blocked.get("/api/v1/dictionaries/categories").status_code == 403

    # dict_admin passes the prefix gate and holds view/edit but not import.
    dict_admin = _dict_admin_client(client)
    assert dict_admin.get("/api/v1/dictionaries/categories").status_code == 200
    assert dict_admin.put("/api/v1/dictionaries/categories", json={
        "category_code": "test_perm", "category_name_cn": "权限验证", "enabled": True,
    }).status_code == 200
    denied = dict_admin.post("/api/v1/dictionaries/import", json={
        "category_code": "test_perm", "system_code": "HIS",
        "items": [{"system_item_code": "X", "system_item_name_cn": "Y"}],
    })
    assert denied.status_code == 403
    assert "dict.general.import" in denied.json()["detail"]

    # platform_admin (default fixture token) holds everything via the bypass.
    assert client.post("/api/v1/dictionaries/import", json={
        "category_code": "test_perm", "system_code": "HIS",
        "items": [{"system_item_code": "X", "system_item_name_cn": "Y"}],
    }).status_code == 200
