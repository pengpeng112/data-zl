from fastapi.testclient import TestClient


def test_list_departments(client: TestClient):
    resp = client.get("/api/v1/identity/departments")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert isinstance(data, list)


def test_department_profile_404(client: TestClient):
    resp = client.get("/api/v1/identity/departments/nonexistent_dept")
    assert resp.status_code == 404


def test_list_persons(client: TestClient):
    resp = client.get("/api/v1/identity/persons")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "page_size" in data


def test_list_persons_pagination(client: TestClient):
    resp = client.get("/api/v1/identity/persons?page=1&page_size=5")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["page"] == 1
    assert data["page_size"] == 5
    assert len(data["items"]) <= 5


def test_list_persons_type_filter(client: TestClient):
    resp = client.get("/api/v1/identity/persons?person_type=formal")
    assert resp.status_code == 200
    data = resp.json()["data"]
    for p in data["items"]:
        assert p["person_type"] == "formal"


def test_list_persons_keyword(client: TestClient):
    resp = client.get("/api/v1/identity/persons?keyword=test")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "items" in data
    assert "total" in data


def test_person_profile_404(client: TestClient):
    resp = client.get("/api/v1/identity/persons/nonexistent_person")
    assert resp.status_code == 404


def test_list_accounts(client: TestClient):
    resp = client.get("/api/v1/identity/accounts")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert isinstance(data, list)


def test_list_accounts_system_filter(client: TestClient):
    resp = client.get("/api/v1/identity/accounts?system_code=HIS")
    assert resp.status_code == 200
    data = resp.json()["data"]
    for a in data:
        assert a["system_code"] == "HIS"


def test_list_sync_diffs(client: TestClient):
    resp = client.get("/api/v1/identity/sync-diffs")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "items" in data
    assert "total" in data


def test_list_sync_diffs_status_filter(client: TestClient):
    resp = client.get("/api/v1/identity/sync-diffs?status=open")
    assert resp.status_code == 200
    data = resp.json()["data"]
    for d in data["items"]:
        assert d["status"] == "open"


def test_list_inconsistencies(client: TestClient):
    resp = client.get("/api/v1/identity/inconsistencies")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "items" in data
    assert "total" in data


def test_collect_sources(client: TestClient):
    resp = client.post("/api/v1/identity/collect-sources")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "scheduled"


def test_bind_account_404(client: TestClient):
    resp = client.put("/api/v1/identity/accounts/bind", json={
        "person_code": "P001",
        "system_code": "NONEXISTENT",
        "account_id": "NOT_FOUND",
    })
    assert resp.status_code == 404
