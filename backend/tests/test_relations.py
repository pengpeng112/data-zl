from __future__ import annotations

from fastapi.testclient import TestClient


def test_path_found(client: TestClient) -> None:
    resp = client.get("/api/v1/relations/path?from=HIS.PAT_VISIT&to=HIS.PAT_MASTER_INDEX")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert data["data"]["path"] is not None
    assert len(data["data"]["hops"]) >= 1


def test_path_same_table(client: TestClient) -> None:
    resp = client.get("/api/v1/relations/path?from=HIS.PAT_VISIT&to=HIS.PAT_VISIT")
    assert resp.status_code == 200
    data = resp.json()
    assert data["data"]["path"] == ["HIS.PAT_VISIT"]


def test_ai_export(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/ai/export-context",
        json={"tables": ["HIS.PAT_VISIT"], "include_relations": True, "include_columns": True},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert "safety" in data["data"]
    assert len(data["data"]["tables"]) > 0
