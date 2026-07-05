from __future__ import annotations

from fastapi.testclient import TestClient


def test_tables_page_invalid(client: TestClient) -> None:
    resp = client.get("/api/v1/tables?page=0")
    assert resp.status_code == 422
    data = resp.json()
    assert data["code"] == 422


def test_table_not_found(client: TestClient) -> None:
    resp = client.get("/api/v1/tables/NOSCHEMA/NOTABLE")
    assert resp.status_code == 404


def test_ai_export_no_tables(client: TestClient) -> None:
    resp = client.post("/api/v1/ai/export-context", json={})
    assert resp.status_code in (400, 422)


def test_ai_export_too_many_tables(client: TestClient) -> None:
    tables = [f"HIS.TABLE_{i}" for i in range(51)]
    resp = client.post("/api/v1/ai/export-context", json={"tables": tables})
    assert resp.status_code in (400, 422)


def test_sort_invalid_field(client: TestClient) -> None:
    resp = client.get("/api/v1/tables?sort=drop_table")
    assert resp.status_code == 400
    data = resp.json()
    assert "detail" in data or data.get("code") == 400


def test_health_no_db_error_leak(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "db_error" not in data.get("data", {})


def test_generic_error_no_leak(client: TestClient) -> None:
    resp = client.get("/api/v1/tables?sort=invalid_field")
    assert resp.status_code == 400
    data = resp.json()
    if "message" in data and isinstance(data["message"], str):
        msg = data["message"].lower()
        assert "psycopg" not in msg
        assert "postgresql" not in msg


def test_ai_export_valid(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/ai/export-context",
        json={
            "tables": ["HIS.PAT_VISIT"],
            "include_relations": True,
            "include_columns": True,
        },
    )
    assert resp.status_code == 200


def test_sort_valid(client: TestClient) -> None:
    resp = client.get("/api/v1/tables?sort=table_name&page=1&page_size=3")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert len(data["data"]["items"]) <= 3
