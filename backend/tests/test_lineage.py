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


def test_impact_analysis_typed_object_key(client: TestClient):
    """144 S5: /impact resolves the table to an exact object_key and returns typed edges."""
    resp = client.get("/api/v1/lineage/impact?table=HIS.PAT_VISIT")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    payload = data["data"]
    assert payload["object_key"].endswith("|HIS|PAT_VISIT|table")
    assert "downstream_nodes" in payload
    assert "upstream_nodes" in payload
    assert payload["direction"] == "downstream"


def test_impact_analysis_unknown_table_fails_closed(client: TestClient):
    """144 S5: unknown tables no longer fall through ILIKE — 422 fail-closed."""
    resp = client.get("/api/v1/lineage/impact?table=UNKNOWN.NO_SUCH_TABLE")
    assert resp.status_code == 422


def test_impact_analysis_legacy_compat(client: TestClient):
    """Legacy contract retained under /impact/legacy (include_in_schema=False)."""
    resp = client.get("/api/v1/lineage/impact/legacy?table=HIS.PAT_VISIT")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert data["data"]["table"] == "HIS.PAT_VISIT"
    assert "referencing_views" in data["data"]
    assert "dependent_relations" in data["data"]


def test_impact_analysis_legacy_unknown_table(client: TestClient):
    resp = client.get("/api/v1/lineage/impact/legacy?table=UNKNOWN.NO_SUCH_TABLE")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert data["data"]["total_views"] == 0
