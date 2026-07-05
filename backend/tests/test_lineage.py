from fastapi.testclient import TestClient


def test_view_dependencies(client: TestClient):
    resp = client.get("/api/v1/lineage/views")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert "total" in data["data"]
    assert "items" in data["data"]


def test_view_dependencies_filter_by_schema(client: TestClient):
    resp = client.get("/api/v1/lineage/views?schema=HIS")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0


def test_view_dependencies_pagination(client: TestClient):
    resp = client.get("/api/v1/lineage/views?page=1&page_size=5")
    assert resp.status_code == 200
    data = resp.json()
    assert data["data"]["page_size"] <= 5


def test_impact_analysis(client: TestClient):
    resp = client.get("/api/v1/lineage/impact?table=HIS.PAT_VISIT")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert data["data"]["table"] == "HIS.PAT_VISIT"
    assert "referencing_views" in data["data"]
    assert "dependent_relations" in data["data"]


def test_impact_analysis_unknown_table(client: TestClient):
    resp = client.get("/api/v1/lineage/impact?table=UNKNOWN.NO_SUCH_TABLE")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert data["data"]["total_views"] == 0
