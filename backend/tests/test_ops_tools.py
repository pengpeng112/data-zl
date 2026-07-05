from fastapi.testclient import TestClient


def _create_tool(client: TestClient, tool_code="test-query-tool", enabled=True):
    resp = client.put("/api/v1/ops/tools", json={
        "tool_code": tool_code,
        "tool_name_cn": "测试查询工具",
        "system_code": "DATA_CENTER",
        "tool_type": "query",
        "risk_level": "low",
        "execution_mode": "readonly_sql",
        "enabled": enabled,
        "require_approval": True,
        "require_second_confirm": False,
    })
    assert resp.status_code == 200
    return resp.json()["data"]


def _create_run(client: TestClient, tool_code="test-query-tool", requested_by="userA"):
    resp = client.post("/api/v1/ops/runs", json={
        "tool_code": tool_code,
        "requested_by": requested_by,
    })
    assert resp.status_code == 200, f"create run failed: {resp.text}"
    return resp.json()["data"]


def test_create_tool_template(client: TestClient):
    resp = client.put("/api/v1/ops/tools", json={
        "tool_code": "test-tool-1",
        "tool_name_cn": "测试工具一",
        "system_code": "DATA_CENTER",
        "tool_type": "query",
        "risk_level": "low",
        "execution_mode": "readonly_sql",
        "enabled": False,
    })
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["tool_code"] == "test-tool-1"
    assert "id" in data


def test_update_tool_template(client: TestClient):
    _create_tool(client, "test-tool-2")
    resp = client.put("/api/v1/ops/tools", json={
        "tool_code": "test-tool-2",
        "tool_name_cn": "测试工具二(已更新)",
        "system_code": "DATA_CENTER",
        "tool_type": "admin",
        "risk_level": "high",
        "execution_mode": "manual",
        "enabled": False,
    })
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["tool_code"] == "test-tool-2"


def test_list_tools(client: TestClient):
    _create_tool(client, "test-tool-list")
    resp = client.get("/api/v1/ops/tools")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert isinstance(data, list)
    assert len(data) >= 1


def test_list_tools_type_filter(client: TestClient):
    _create_tool(client, "test-tool-query-only", enabled=False)
    resp = client.get("/api/v1/ops/tools?tool_type=query")
    assert resp.status_code == 200
    data = resp.json()["data"]
    for t in data:
        assert t["tool_type"] == "query"


def test_create_run(client: TestClient):
    _create_tool(client, "test-tool-run", enabled=True)
    resp = client.post("/api/v1/ops/runs", json={
        "tool_code": "test-tool-run",
        "requested_by": "userA",
    })
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["approval_status"] == "draft"
    assert "id" in data


def test_create_run_disabled_tool(client: TestClient):
    _create_tool(client, "test-tool-disabled", enabled=False)
    resp = client.post("/api/v1/ops/runs", json={
        "tool_code": "test-tool-disabled",
        "requested_by": "userA",
    })
    assert resp.status_code == 400


def test_create_run_nonexistent_tool(client: TestClient):
    resp = client.post("/api/v1/ops/runs", json={
        "tool_code": "nonexistent-tool-xyz",
        "requested_by": "userA",
    })
    assert resp.status_code == 400


def test_list_runs(client: TestClient):
    _create_tool(client, "test-tool-runs", enabled=True)
    _create_run(client, "test-tool-runs")
    resp = client.get("/api/v1/ops/runs")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 1


def test_list_runs_status_filter(client: TestClient):
    _create_tool(client, "test-tool-runs-status", enabled=True)
    _create_run(client, "test-tool-runs-status")
    resp = client.get("/api/v1/ops/runs?status=draft")
    assert resp.status_code == 200
    data = resp.json()["data"]
    for item in data["items"]:
        assert item["approval_status"] == "draft"


def test_approve_run(client: TestClient):
    _create_tool(client, "test-tool-approve", enabled=True)
    run = _create_run(client, "test-tool-approve", requested_by="userA")
    resp = client.patch(f"/api/v1/ops/runs/{run['id']}/approve", json={
        "approved_by": "userB",
        "note": "同意执行",
    })
    assert resp.status_code == 200
    assert resp.json()["data"]["approval_status"] == "approved"


def test_reject_run(client: TestClient):
    _create_tool(client, "test-tool-reject", enabled=True)
    run = _create_run(client, "test-tool-reject", requested_by="userA")
    resp = client.patch(f"/api/v1/ops/runs/{run['id']}/reject", json={
        "approved_by": "userB",
        "note": "拒绝执行",
    })
    assert resp.status_code == 200
    assert resp.json()["data"]["approval_status"] == "rejected"


def test_self_approval_rejection(client: TestClient):
    _create_tool(client, "test-tool-self", enabled=True)
    run = _create_run(client, "test-tool-self", requested_by="userX")
    resp = client.patch(f"/api/v1/ops/runs/{run['id']}/approve", json={
        "approved_by": "userX",
    })
    assert resp.status_code == 400


def test_execute_run(client: TestClient):
    _create_tool(client, "test-tool-exec", enabled=True)
    run = _create_run(client, "test-tool-exec", requested_by="userA")
    client.patch(f"/api/v1/ops/runs/{run['id']}/approve", json={"approved_by": "userB"})
    resp = client.post(f"/api/v1/ops/runs/{run['id']}/execute")
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "executed"


def test_run_audit(client: TestClient):
    _create_tool(client, "test-tool-audit", enabled=True)
    run = _create_run(client, "test-tool-audit", requested_by="userA")
    client.patch(f"/api/v1/ops/runs/{run['id']}/approve", json={"approved_by": "userB"})
    client.post(f"/api/v1/ops/runs/{run['id']}/execute")
    resp = client.get(f"/api/v1/ops/runs/{run['id']}/audit")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert isinstance(data, list)
    assert any(l["action"] == "create" for l in data)
    assert any(l["action"] == "approve" for l in data)
    assert any(l["action"] == "execute" for l in data)
