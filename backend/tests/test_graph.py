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


def test_graph_edge_has_validation(client: TestClient) -> None:
    resp = client.get("/api/v1/graph?limit=10")
    assert resp.status_code == 200
    data = resp.json()
    for e in data["data"]["edges"]:
        assert "validation_status" in e
        assert "validation_level" in e
