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


def test_overview_charts(client: TestClient) -> None:
    """127 S4 四图聚合：必须一次返回全量，且 PG 下 coalesce GROUP BY 不能 500。"""
    resp = client.get("/api/v1/overview/charts")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["code"] == 0
    data = body["data"]
    for key in ("domains", "validation_status", "partitions", "core_tables"):
        assert key in data
        assert isinstance(data[key].get("items"), list)
    assert data["domains"]["total_tables"] > 0
    assert data["validation_status"]["total_relations"] > 0
    assert all("name" in item and "count" in item for item in data["domains"]["items"])
    assert all("name" in item and "count" in item for item in data["validation_status"]["items"])
    assert all("name" in item and "count" in item for item in data["partitions"]["items"])
    assert all("table" in item and "count" in item for item in data["core_tables"]["items"])


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
