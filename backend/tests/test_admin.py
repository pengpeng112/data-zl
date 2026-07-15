from fastapi.testclient import TestClient


def test_public_token_initialization_is_removed(client: TestClient):
    resp = client.get("/api/v1/admin/init")
    assert resp.status_code == 404


def test_list_keys(client: TestClient):
    resp = client.get("/api/v1/admin/keys")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert isinstance(data["data"], list)


def test_create_key(client: TestClient):
    resp = client.post(
        "/api/v1/admin/keys",
        json={"key_name": "test-key-1", "user_identifier": "test-key-owner"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["code"] == 0
    assert "token" in data["data"]
    # raw token returned once
    assert len(data["data"]["token"]) > 8


def test_toggle_key(client: TestClient):
    created = client.post(
        "/api/v1/admin/keys",
        json={"key_name": "toggle-key", "user_identifier": "toggle-user"},
    )
    assert created.status_code == 200
    kid = created.json()["data"]["id"]
    resp2 = client.patch(f"/api/v1/admin/keys/{kid}?enabled=false")
    assert resp2.status_code == 200


def test_list_owners(client: TestClient):
    resp = client.get("/api/v1/admin/owners")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert "items" in data["data"]


def test_upsert_owner(client: TestClient):
    resp = client.put(
        "/api/v1/admin/owners",
        json={
            "full_table_name": "TEST_SCHEMA.TEST_TABLE",
            "owner_name": "tester",
            "department": "信息科",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0


def test_delete_owner(client: TestClient):
    client.put(
        "/api/v1/admin/owners",
        json={
            "full_table_name": "TEST_SCHEMA.TEST_TABLE",
            "owner_name": "tester",
            "department": "信息科",
        },
    )
    resp = client.get("/api/v1/admin/owners?keyword=TEST_SCHEMA.TEST_TABLE")
    items = resp.json()["data"]["items"]
    assert items
    oid = items[0]["id"]
    resp2 = client.delete(f"/api/v1/admin/owners/{oid}")
    assert resp2.status_code == 200
