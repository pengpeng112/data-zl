from __future__ import annotations

from fastapi.testclient import TestClient


def test_graph_default(client: TestClient) -> None:
    resp = client.get("/api/v1/graph?limit=50")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert len(data["data"]["nodes"]) > 0
    assert len(data["data"]["edges"]) > 0
    assert len(data["data"]["edges"]) <= 50


def test_graph_filter_verified(client: TestClient) -> None:
    resp = client.get("/api/v1/graph?validation_status=verified&limit=50")
    assert resp.status_code == 200
    data = resp.json()
    for e in data["data"]["edges"]:
        assert e["validation_status"] == "verified"


def test_graph_limit_enforced(client: TestClient) -> None:
    resp = client.get("/api/v1/graph?limit=5")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["data"]["edges"]) <= 5


def test_neighbors_basic(client: TestClient) -> None:
    resp = client.get("/api/v1/graph/neighbors?table=HIS.PAT_VISIT&depth=1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    node_ids = {n["id"] for n in data["data"]["nodes"]}
    assert "HIS.PAT_VISIT" in node_ids
    assert len(data["data"]["edges"]) > 0


def test_neighbors_invalid_depth(client: TestClient) -> None:
    resp = client.get("/api/v1/graph/neighbors?table=HIS.PAT_VISIT&depth=3")
    assert resp.status_code in (400, 422)


def test_neighbors_invalid_direction(client: TestClient) -> None:
    resp = client.get("/api/v1/graph/neighbors?table=HIS.PAT_VISIT&direction=xxx")
    assert resp.status_code in (400, 422)


def test_graph_options(client: TestClient) -> None:
    resp = client.get("/api/v1/graph/options")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert len(data["data"]["schemas"]) > 0
    assert len(data["data"]["validation_statuses"]) > 0
    assert "verified" in data["data"]["validation_statuses"]
    assert "A_rechecked" in data["data"]["validation_statuses"]


def test_graph_edge_has_validation(client: TestClient) -> None:
    resp = client.get("/api/v1/graph?limit=10")
    assert resp.status_code == 200
    data = resp.json()
    for e in data["data"]["edges"]:
        assert "validation_status" in e
        assert "validation_level" in e
        assert "business_domain" in e


def test_graph_node_has_system_metadata(client: TestClient) -> None:
    resp = client.get("/api/v1/graph?limit=10")
    assert resp.status_code == 200
    data = resp.json()
    for node in data["data"]["nodes"]:
        assert "system_code" in node
        assert "source_code" in node
        assert "namespace_name" in node
        assert "table_name_cn" in node
        assert "include_status" in node
        assert "review_status" in node
        assert "business_domain" in node


def test_graph_options_has_system_filters(client: TestClient) -> None:
    resp = client.get("/api/v1/graph/options")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "systems" in data
    assert "sources" in data


def test_graph_edge_has_endpoint_metadata(client: TestClient) -> None:
    resp = client.get("/api/v1/graph?limit=10")
    assert resp.status_code == 200
    data = resp.json()
    for edge in data["data"]["edges"]:
        assert "from_system_code" in edge
        assert "from_source_code" in edge
        assert "from_schema_name" in edge
        assert "from_table_name" in edge
        assert "from_table_name_cn" in edge
        assert "from_table_role" in edge
        assert "from_include_status" in edge
        assert "to_system_code" in edge
        assert "to_source_code" in edge
        assert "to_schema_name" in edge
        assert "to_table_name" in edge
        assert "to_table_name_cn" in edge
        assert "to_table_role" in edge
        assert "to_include_status" in edge
        assert "field_mappings" in edge
        assert "is_deferred" in edge
        assert "deferred_reason" in edge
        for mapping in edge["field_mappings"]:
            assert "from_column" in mapping
            assert "from_column_name_cn" in mapping
            assert "to_column" in mapping
            assert "to_column_name_cn" in mapping

def test_graph_options_has_view_modes(client: TestClient) -> None:
    resp = client.get("/api/v1/graph/options")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "view_modes" in data
    mode_codes = {item["code"] for item in data["view_modes"]}
    assert {"system", "schema", "domain", "table", "lineage", "deferred", "review"}.issubset(mode_codes)
    domain_mode = next(item for item in data["view_modes"] if item["code"] == "domain")
    assert domain_mode["group_by"] == "domain"
    assert "患者" in domain_mode["description"]
    table_mode = next(item for item in data["view_modes"] if item["code"] == "table")
    assert table_mode["group_by"] == "schema"
    assert table_mode["confidence"] == "A"
    assert table_mode["validation_status"] == "A_rechecked"
    assert "表级关系图谱" in table_mode["description"]
    lineage_mode = next(item for item in data["view_modes"] if item["code"] == "lineage")
    assert lineage_mode["requires_table"] is True
    assert lineage_mode["layout_mode"] == "radial"
    assert "两跳链路" in lineage_mode["description"]
    deferred_mode = next(item for item in data["view_modes"] if item["code"] == "deferred")
    assert deferred_mode["confidence"] == "D"
    assert deferred_mode["validation_status"] is None
    assert deferred_mode["include_candidates"] is True
    assert deferred_mode["show_review_layer"] is True
    assert "不进入正式图谱" in deferred_mode["description"]
    for item in data["view_modes"]:
        assert "group_by" in item
        assert "layout_mode" in item
        assert "validation_status" in item
        assert "requires_table" in item
