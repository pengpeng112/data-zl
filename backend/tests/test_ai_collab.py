from fastapi.testclient import TestClient


def test_list_tools(client: TestClient):
    resp = client.get("/api/v1/ai/tools")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    tools = data["data"]["tools"]
    assert len(tools) >= 1
    for t in tools:
        assert "name" in t
        assert "method" in t
        assert "path" in t
        assert "auth_required" in t


def test_start_session(client: TestClient):
    resp = client.post("/api/v1/ai/sessions", json={"purpose": "test"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert "session_key" in data["data"]


def test_list_sessions(client: TestClient):
    resp = client.get("/api/v1/ai/sessions")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert "items" in data["data"]


def test_log_tool_call(client: TestClient):
    resp = client.post("/api/v1/ai/tool-call", json={
        "session_key": "test-session-abc",
        "tool_name": "search_tables",
        "request": {"keyword": "PAT"},
        "response_summary": "found 3 tables",
    })
    assert resp.status_code == 200
    assert resp.json()["code"] == 0


def test_list_tool_calls(client: TestClient):
    resp = client.get("/api/v1/ai/tool-calls")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert "items" in data["data"]


def test_propose_sql(client: TestClient):
    resp = client.post("/api/v1/ai/propose-sql", json={
        "sql_text": "SELECT * FROM HIS.PAT_VISIT WHERE ROWNUM <= 10",
        "title": "测试查询",
        "purpose": "测试",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert data["data"]["draft_id"] is not None
    assert "risk_flags" in data["data"]


def test_propose_sql_dangerous(client: TestClient):
    resp = client.post("/api/v1/ai/propose-sql", json={
        "sql_text": "DROP TABLE HIS.PAT_VISIT",
        "title": "危险操作",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    risk = data["data"]["risk_flags"]
    assert risk.get("blocked") is True
    assert "dangerous_keywords" in risk


def test_propose_sql_big_table_warning(client: TestClient):
    resp = client.post("/api/v1/ai/propose-sql", json={
        "sql_text": "SELECT * FROM HIS.LAB_RESULT",
        "title": "大表查询",
    })
    assert resp.status_code == 200
    data = resp.json()
    risk = data["data"]["risk_flags"]
    assert risk.get("big_table_warning") is not None


def test_list_drafts(client: TestClient):
    resp = client.get("/api/v1/ai/drafts")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert "items" in data["data"]


def test_review_draft(client: TestClient):
    resp = client.get("/api/v1/ai/drafts?status=draft&page_size=1")
    assert resp.status_code == 200
    items = resp.json()["data"]["items"]
    if items:
        did = items[0]["id"]
        resp2 = client.patch(
            f"/api/v1/ai/drafts/{did}",
            json={"status": "approved", "reviewed_by": "test"},
        )
        assert resp2.status_code == 200
        assert resp2.json()["code"] == 0


def test_execute_draft_requires_approval(client: TestClient):
    resp = client.post("/api/v1/ai/propose-sql", json={
        "sql_text": "SELECT 1 AS total_cnt, 0 AS error_cnt",
        "title": "execute guard",
    })
    draft_id = resp.json()["data"]["draft_id"]

    exec_resp = client.post(
        f"/api/v1/ai/drafts/{draft_id}/execute",
        json={"source_code": "test_source"},
    )
    assert exec_resp.status_code == 400


def test_execute_approved_draft(monkeypatch, client: TestClient):
    def fake_execute_quality_sql(**kwargs):
        assert kwargs["source_code"] == "test_source"
        assert kwargs["max_rows"] == 10
        return {
            "status": "success",
            "total_cnt": 1,
            "error_cnt": 0,
            "error_rate": 0,
            "warnings": [],
            "sample_data": [{"TOTAL_CNT": 1, "ERROR_CNT": 0}],
        }

    monkeypatch.setattr(
        "app.services.quality_sql_runner.execute_quality_sql",
        fake_execute_quality_sql,
    )
    resp = client.post("/api/v1/ai/propose-sql", json={
        "sql_text": "SELECT 1 AS total_cnt, 0 AS error_cnt",
        "title": "execute approved",
        "session_key": "execute-approved-session",
    })
    draft_id = resp.json()["data"]["draft_id"]
    review_resp = client.patch(
        f"/api/v1/ai/drafts/{draft_id}",
        json={"status": "approved", "reviewed_by": "test"},
    )
    assert review_resp.status_code == 200

    exec_resp = client.post(
        f"/api/v1/ai/drafts/{draft_id}/execute",
        json={"source_code": "test_source", "max_rows": 10, "sample_limit": 5, "executed_by": "tester"},
    )
    assert exec_resp.status_code == 200
    data = exec_resp.json()
    assert data["code"] == 0
    assert data["data"]["status"] == "executed"
    assert data["data"]["total_cnt"] == 1
    assert data["data"]["sample_data"] == [{"TOTAL_CNT": 1, "ERROR_CNT": 0}]


def test_export_context(client: TestClient):
    resp = client.post("/api/v1/ai/export-context", json={
        "tables": ["HIS.PAT_VISIT"],
        "include_relations": True,
        "include_columns": True,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert "tables" in data["data"]
