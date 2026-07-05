from fastapi.testclient import TestClient


def test_public_routes_no_auth(client: TestClient):
    public_urls = [
        "/",
        "/health",
        "/api/v1/ai/tools",
    ]
    for url in public_urls:
        resp = client.get(url)
        assert resp.status_code == 200, f"{url} should be public but got {resp.status_code}"


def test_protected_route_no_token():
    from fastapi.testclient import TestClient as TC
    from app.main import app
    client = TC(app)
    resp = client.get("/api/v1/summary")
    assert resp.status_code == 401
    assert "缺少" in resp.json()["message"]


def test_protected_route_invalid_token():
    from fastapi.testclient import TestClient as TC
    from app.main import app
    client = TC(app, headers={"Authorization": "Bearer invalid-token-xyz"})
    resp = client.get("/api/v1/summary")
    assert resp.status_code == 403
    assert "无效" in resp.json()["message"]
