from fastapi.testclient import TestClient


def _ensure_code_set(client: TestClient, code_set_code="test_cs"):
    resp = client.put("/api/v1/dict-medical/code-sets", json={
        "category_code": "diagnosis",
        "code_set_code": code_set_code,
        "code_set_type": "clinical",
        "code_set_name_cn": "测试编码体系",
        "enabled": True,
    })
    assert resp.status_code == 200
    return resp.json()["data"]


def test_list_code_sets(client: TestClient):
    resp = client.get("/api/v1/dict-medical/code-sets")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert isinstance(data, list)


def test_list_code_sets_category_filter(client: TestClient):
    _ensure_code_set(client, "test_cs_diag")
    resp = client.get("/api/v1/dict-medical/code-sets?category_code=diagnosis")
    assert resp.status_code == 200
    data = resp.json()["data"]
    for cs in data:
        assert cs["category_code"] == "diagnosis"


def test_upsert_code_set(client: TestClient):
    resp = client.put("/api/v1/dict-medical/code-sets", json={
        "category_code": "diagnosis",
        "code_set_code": "test_cs_upsert",
        "code_set_type": "clinical",
        "code_set_name_cn": "测试编码体系",
    })
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["code_set_code"] == "test_cs_upsert"
    assert "id" in data

    resp = client.put("/api/v1/dict-medical/code-sets", json={
        "category_code": "diagnosis",
        "code_set_code": "test_cs_upsert",
        "code_set_type": "clinical",
        "code_set_name_cn": "测试编码体系(已更新)",
    })
    assert resp.status_code == 200


def test_list_items(client: TestClient):
    _ensure_code_set(client, "test_cs_items")
    resp = client.get("/api/v1/dict-medical/code-sets/test_cs_items/items")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "items" in data
    assert "total" in data


def test_list_items_keyword(client: TestClient):
    _ensure_code_set(client, "test_cs_kw")
    client.put("/api/v1/dict-medical/items", json={
        "code_set_code": "test_cs_kw",
        "item_code": "KW001",
        "item_name_cn": "关键字测试项",
        "category_code": "diagnosis",
    })
    resp = client.get("/api/v1/dict-medical/code-sets/test_cs_kw/items?keyword=关键字")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total"] >= 1


def test_upsert_item(client: TestClient):
    _ensure_code_set(client, "test_cs_item")
    resp = client.put("/api/v1/dict-medical/items", json={
        "code_set_code": "test_cs_item",
        "item_code": "I001",
        "item_name_cn": "测试编码项",
        "category_code": "diagnosis",
    })
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["item_code"] == "I001"
    assert "id" in data

    resp = client.put("/api/v1/dict-medical/items", json={
        "code_set_code": "test_cs_item",
        "item_code": "I001",
        "item_name_cn": "测试编码项(已更新)",
        "category_code": "diagnosis",
    })
    assert resp.status_code == 200


def test_list_mappings(client: TestClient):
    resp = client.get("/api/v1/dict-medical/mappings")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "items" in data
    assert "total" in data


def test_list_mappings_review_status_filter(client: TestClient):
    resp = client.get("/api/v1/dict-medical/mappings?review_status=draft")
    assert resp.status_code == 200
    data = resp.json()["data"]
    for m in data["items"]:
        assert m["review_status"] == "draft"


def test_upsert_mapping(client: TestClient):
    resp = client.put("/api/v1/dict-medical/mappings", json={
        "category_code": "diagnosis",
        "from_code_set": "clinical_diag",
        "from_item_code": "A01",
        "to_code_set": "national_diag",
        "to_item_code": "B01",
        "mapping_type": "manual",
        "confidence": "high",
    })
    assert resp.status_code == 200
    assert "id" in resp.json()["data"]


def test_list_sync_diffs(client: TestClient):
    resp = client.get("/api/v1/dict-medical/sync-diffs")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "items" in data
    assert "total" in data


def test_list_sync_diffs_status_filter(client: TestClient):
    resp = client.get("/api/v1/dict-medical/sync-diffs?status=open")
    assert resp.status_code == 200
    data = resp.json()["data"]
    for d in data["items"]:
        assert d["status"] == "open"


def test_list_versions(client: TestClient):
    resp = client.get("/api/v1/dict-medical/versions")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert isinstance(data, list)


def test_create_change_request(client: TestClient):
    resp = client.post("/api/v1/dict-medical/change-requests", json={
        "entity_type": "code_item",
        "request_type": "add",
        "requested_by": "test_user",
    })
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["approval_status"] == "draft"
    assert "id" in data
