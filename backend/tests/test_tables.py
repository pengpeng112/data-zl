from __future__ import annotations

from fastapi.testclient import TestClient


def test_summary(client: TestClient) -> None:
    resp = client.get("/api/v1/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert data["data"]["tables"] > 0
    assert data["data"]["columns"] > 0
    assert data["data"]["relations"] > 0
    assert data["data"]["domains"] > 0


def test_list_tables_pagination(client: TestClient) -> None:
    resp = client.get("/api/v1/tables?page=1&page_size=5")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert data["data"]["total"] > 0
    assert len(data["data"]["items"]) <= 5
    assert data["data"]["page"] == 1
    assert data["data"]["page_size"] == 5


def test_list_tables_keyword(client: TestClient) -> None:
    resp = client.get("/api/v1/tables?keyword=PAT_VISIT")
    assert resp.status_code == 200
    data = resp.json()
    assert data["data"]["total"] > 0


def test_get_table_detail(client: TestClient) -> None:
    resp = client.get("/api/v1/tables/HIS/PAT_VISIT")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert data["data"]["schema_name"] == "HIS"
    assert data["data"]["table_name"] == "PAT_VISIT"


def test_get_table_not_found(client: TestClient) -> None:
    resp = client.get("/api/v1/tables/NOSCHEMA/NOTABLE")
    assert resp.status_code == 404


def test_get_columns(client: TestClient) -> None:
    resp = client.get("/api/v1/tables/HIS/PAT_VISIT/columns")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert len(data["data"]) > 0


def test_search_columns(client: TestClient) -> None:
    resp = client.get("/api/v1/columns/search?keyword=PATIENT_ID&page=1&page_size=10")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert data["data"]["total"] > 0
