from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_ok(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert data["data"]["status"] in ("ok", "degraded")
    assert data["data"]["database"] in ("connected", "disconnected")


def test_health_response_structure(client: TestClient) -> None:
    resp = client.get("/health")
    data = resp.json()
    assert "code" in data
    assert "message" in data
    assert "data" in data
