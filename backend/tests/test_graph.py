from __future__ import annotations

from fastapi.testclient import TestClient


def test_graph_default(seeded_client: TestClient) -> None:
    resp = seeded_client.get("/api/v1/graph?limit=50")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert len(data["data"]["nodes"]) > 0
    assert len(data["data"]["edges"]) > 0
    assert len(data["data"]["edges"]) <= 50


def test_graph_filter_verified(seeded_client: TestClient) -> None:
    resp = seeded_client.get("/api/v1/graph?validation_status=verified&limit=50")
    assert resp.status_code == 200
    data = resp.json()
    for e in data["data"]["edges"]:
        assert e["validation_status"] == "verified"


def test_graph_limit_enforced(seeded_client: TestClient) -> None:
    resp = seeded_client.get("/api/v1/graph?limit=5")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["data"]["edges"]) <= 5


def test_neighbors_basic(seeded_client: TestClient) -> None:
    resp = seeded_client.get("/api/v1/graph/neighbors?table=HIS.PAT_VISIT&depth=1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    node_ids = {n["id"] for n in data["data"]["nodes"]}
    # stable id may be full path or table name depending on graph API
    assert any("PAT_VISIT" in str(i) for i in node_ids)
    assert len(data["data"]["edges"]) > 0


def test_neighbors_invalid_depth(client: TestClient) -> None:
    resp = client.get("/api/v1/graph/neighbors?table=HIS.PAT_VISIT&depth=3")
    assert resp.status_code in (400, 422)


def test_neighbors_invalid_direction(client: TestClient) -> None:
    resp = client.get("/api/v1/graph/neighbors?table=HIS.PAT_VISIT&direction=xxx")
    assert resp.status_code in (400, 422)


def test_graph_options(seeded_client: TestClient) -> None:
    resp = seeded_client.get("/api/v1/graph/options")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert data["data"]["schemas"]
    assert {"HIS", "ODS"}.issubset(data["data"]["schemas"])
    assert {"verified", "A_rechecked"}.issubset(data["data"]["validation_statuses"])


def test_graph_edge_has_validation(seeded_client: TestClient) -> None:
    resp = seeded_client.get("/api/v1/graph?limit=10")
    assert resp.status_code == 200
    data = resp.json()
    for e in data["data"]["edges"]:
        assert "validation_status" in e
        assert "validation_level" in e
        assert "business_domain" in e


def test_graph_node_has_system_metadata(seeded_client: TestClient) -> None:
    resp = seeded_client.get("/api/v1/graph?limit=10")
    assert resp.status_code == 200
    data = resp.json()
    for node in data["data"]["nodes"]:
        for field in (
            "id", "system_code", "source_code", "namespace_name", "schema_name",
            "table_name", "table_name_cn", "include_status", "review_status",
            "business_domain",
        ):
            assert field in node


def test_graph_options_has_system_filters_and_view_modes(seeded_client: TestClient) -> None:
    resp = seeded_client.get("/api/v1/graph/options")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert {"HIS", "DATA_CENTER"}.issubset(data["systems"])
    assert {"his_source_10_10_10_15", "ods_8_216"}.issubset(data["sources"])
    modes = {item["code"]: item for item in data["view_modes"]}
    assert {"system", "schema", "domain", "table", "lineage", "deferred", "review"}.issubset(modes)
    assert modes["domain"]["group_by"] == "domain"
    assert modes["table"]["confidence"] == "A"
    assert modes["table"]["validation_status"] == "A_rechecked"
    assert modes["lineage"]["requires_table"] is True
    assert modes["lineage"]["layout_mode"] == "radial"
    assert modes["deferred"]["confidence"] == "D"
    assert modes["deferred"]["include_candidates"] is True
    assert modes["deferred"]["show_review_layer"] is True
    for mode in modes.values():
        for field in ("group_by", "layout_mode", "validation_status", "requires_table"):
            assert field in mode


def test_graph_edges_have_endpoint_metadata(seeded_client: TestClient) -> None:
    resp = seeded_client.get("/api/v1/graph?limit=10")
    assert resp.status_code == 200
    edges = resp.json()["data"]["edges"]
    assert edges
    for edge in edges:
        for prefix in ("from", "to"):
            for suffix in (
                "system_code", "source_code", "schema_name", "table_name",
                "table_name_cn", "table_role", "include_status",
            ):
                assert f"{prefix}_{suffix}" in edge
        assert "field_mappings" in edge
        assert "is_deferred" in edge
        assert "deferred_reason" in edge
        for mapping in edge["field_mappings"]:
            assert set(mapping) >= {
                "from_column", "from_column_name_cn", "to_column", "to_column_name_cn"
            }
