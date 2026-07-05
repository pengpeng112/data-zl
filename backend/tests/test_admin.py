from fastapi.testclient import TestClient


def test_init_default_token_first_time(client: TestClient):
    resp = client.get("/api/v1/admin/init")
    assert resp.status_code in (200, 403)
    if resp.status_code == 200:
        data = resp.json()
        assert data["code"] == 0
        assert "token" in data["data"]


def test_list_keys(client: TestClient):
    resp = client.get("/api/v1/admin/keys")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert isinstance(data["data"], list)


def test_create_key(client: TestClient):
    resp = client.post("/api/v1/admin/keys", json={"key_name": "test-key-1"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert "token" in data["data"]


def test_toggle_key(client: TestClient):
    resp = client.get("/api/v1/admin/keys")
    items = resp.json()["data"]
    if items:
        kid = items[0]["id"]
        resp2 = client.patch(f"/api/v1/admin/keys/{kid}?enabled=false")
        assert resp2.status_code == 200


def test_list_owners(client: TestClient):
    resp = client.get("/api/v1/admin/owners")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert "items" in data["data"]


def test_upsert_owner(client: TestClient):
    resp = client.put("/api/v1/admin/owners", json={
        "full_table_name": "TEST_SCHEMA.TEST_TABLE",
        "owner_name": "tester",
        "department": "信息科",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0


def test_delete_owner(client: TestClient):
    resp = client.get("/api/v1/admin/owners?keyword=TEST_SCHEMA.TEST_TABLE")
    items = resp.json()["data"]["items"]
    if items:
        oid = items[0]["id"]
        resp2 = client.delete(f"/api/v1/admin/owners/{oid}")
        assert resp2.status_code == 200


def test_list_terms(client: TestClient):
    resp = client.get("/api/v1/admin/terms")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert "items" in data["data"]


def test_upsert_term(client: TestClient):
    resp = client.put("/api/v1/admin/terms", json={
        "term": "测试术语",
        "mapping_target": "HIS.TEST.COL",
        "description": "测试专用的术语",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0


def test_lookup_term(client: TestClient):
    resp = client.get("/api/v1/admin/terms/lookup?q=测试")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0


def test_delete_term(client: TestClient):
    resp = client.get("/api/v1/admin/terms?keyword=测试术语")
    items = resp.json()["data"]["items"]
    if items:
        tid = items[0]["id"]
        resp2 = client.delete(f"/api/v1/admin/terms/{tid}")
        assert resp2.status_code == 200


def test_create_snapshot(client: TestClient):
    resp = client.post("/api/v1/admin/snapshots", json={"label": "test_snapshot"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert data["data"]["id"] is not None
    assert data["data"]["table_count"] is not None


def test_list_snapshots(client: TestClient):
    resp = client.get("/api/v1/admin/snapshots")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert "items" in data["data"]


def test_compare_snapshots(client: TestClient):
    resp = client.get("/api/v1/admin/snapshots")
    items = resp.json()["data"]["items"]
    if len(items) >= 2:
        id1 = items[0]["id"]
        id2 = items[1]["id"]
        resp2 = client.get(f"/api/v1/admin/snapshots/compare?id1={id1}&id2={id2}")
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["code"] == 0
        assert "tables_added" in data2["data"]
