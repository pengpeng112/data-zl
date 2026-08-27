from fastapi.testclient import TestClient
import hashlib

from app.core.db import SessionLocal
from app.models.governance import ApiKey
from app.models.governance_base import AssetRole, AssetUserRole

APPROVER_TOKEN = "test-ops-approver-token-2026"


def _approver_headers():
    db = SessionLocal()
    try:
        key = db.query(ApiKey).filter(ApiKey.key_name == "test-ops-approver").first()
        digest = hashlib.sha256(APPROVER_TOKEN.encode()).hexdigest()
        if not key:
            db.add(ApiKey(key_name="test-ops-approver", token_hash=digest, user_identifier="test-ops-approver"))
        else:
            key.token_hash = digest
            key.user_identifier = "test-ops-approver"
            key.enabled = True
        if not db.query(AssetRole).filter(AssetRole.role_code == "platform_admin").first():
            db.add(AssetRole(role_code="platform_admin", role_name_cn="平台管理员", role_type="builtin"))
        if not db.query(AssetUserRole).filter(
            AssetUserRole.user_identifier == "test-ops-approver",
            AssetUserRole.role_code == "platform_admin",
        ).first():
            db.add(AssetUserRole(user_identifier="test-ops-approver", role_code="platform_admin", status="active"))
        db.commit()
    finally:
        db.close()
    return {"Authorization": f"Bearer {APPROVER_TOKEN}"}

def _enable_ops_write(monkeypatch):
    monkeypatch.setattr("app.api.v1.ops_tools.settings.ops_write_enabled", True)
    monkeypatch.setattr("app.api.v1.ops_tools.settings.ops_write_d1_d5_confirmed", True)
    monkeypatch.setattr("app.api.v1.ops_tools.settings.ops_write_confirmation_token", "D1-D5-CONFIRMED", raising=False)
    monkeypatch.setenv("PYTEST_ASSET_WRITE", "asset_write:secret")


def _create_tool(client: TestClient, tool_code="test-query-tool", enabled=True):
    resp = client.put("/api/v1/ops/tools", json={
        "tool_code": tool_code,
        "tool_name_cn": "测试查询工具",
        "system_code": "ASSET_PLATFORM",
        "source_code": "asset",
        "tool_type": "query",
        "risk_level": "low",
        "execution_mode": "readonly_sql",
        "sql_or_endpoint_ref": "SELECT 1 AS ok",
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




def _submit_run(client: TestClient, run_id: int, submitted_by="submitter"):
    resp = client.post(f"/api/v1/ops/runs/{run_id}/submit", json={"submitted_by": submitted_by})
    assert resp.status_code == 200, f"submit run failed: {resp.text}"
    return resp.json()["data"]


def _approve_run(client: TestClient, run_id: int, approved_by="approverB"):
    _submit_run(client, run_id)
    resp = client.patch(
        f"/api/v1/ops/runs/{run_id}/approve",
        json={"approved_by": approved_by},
        headers=_approver_headers(),
    )
    assert resp.status_code == 200, f"approve run failed: {resp.text}"
    return resp.json()["data"]

def test_create_tool_template(client: TestClient):
    resp = client.put("/api/v1/ops/tools", json={
        "tool_code": "test-tool-1",
        "tool_name_cn": "测试工具一",
        "system_code": "ASSET_PLATFORM",
        "source_code": "asset",
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
    # 146 E7：服务端分页契约
    assert {"items", "total", "page", "page_size"} <= set(data)
    assert data["total"] >= 1
    assert len(data["items"]) >= 1


def test_list_tools_type_filter(client: TestClient):
    _create_tool(client, "test-tool-query-only", enabled=False)
    resp = client.get("/api/v1/ops/tools?tool_type=query")
    assert resp.status_code == 200
    data = resp.json()["data"]
    for t in data["items"]:
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
    _submit_run(client, run["id"])
    resp = client.patch(f"/api/v1/ops/runs/{run['id']}/approve", json={
        "approved_by": "userB",
        "note": "同意执行",
    }, headers=_approver_headers())
    assert resp.status_code == 200
    assert resp.json()["data"]["approval_status"] == "approved"


def test_reject_run(client: TestClient):
    _create_tool(client, "test-tool-reject", enabled=True)
    run = _create_run(client, "test-tool-reject", requested_by="userA")
    _submit_run(client, run["id"])
    resp = client.patch(f"/api/v1/ops/runs/{run['id']}/reject", json={
        "approved_by": "userB",
        "note": "拒绝执行",
    }, headers=_approver_headers())
    assert resp.status_code == 200
    assert resp.json()["data"]["approval_status"] == "rejected"


def test_self_approval_rejection(client: TestClient):
    _create_tool(client, "test-tool-self", enabled=True)
    run = _create_run(client, "test-tool-self", requested_by="userX")
    _submit_run(client, run["id"], submitted_by="userX")
    resp = client.patch(f"/api/v1/ops/runs/{run['id']}/approve", json={
        "approved_by": "userX",
    })
    assert resp.status_code == 400



def test_draft_cannot_be_approved_directly(client: TestClient):
    _create_tool(client, "test-tool-draft-approve", enabled=True)
    run = _create_run(client, "test-tool-draft-approve", requested_by="userA")
    resp = client.patch(f"/api/v1/ops/runs/{run['id']}/approve", json={"approved_by": "userB"})
    assert resp.status_code == 400
    assert "cannot be approved" in resp.text

def test_execute_run(client: TestClient):
    _create_tool(client, "test-tool-exec", enabled=True)
    run = _create_run(client, "test-tool-exec", requested_by="userA")
    _approve_run(client, run["id"], approved_by="userB")
    resp = client.post(f"/api/v1/ops/runs/{run['id']}/execute")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "succeeded"
    assert "readonly_sql executed" in data["execution_summary"]


def test_run_audit(client: TestClient):
    _create_tool(client, "test-tool-audit", enabled=True)
    run = _create_run(client, "test-tool-audit", requested_by="userA")
    _approve_run(client, run["id"], approved_by="userB")
    client.post(f"/api/v1/ops/runs/{run['id']}/execute")
    resp = client.get(f"/api/v1/ops/runs/{run['id']}/audit")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert isinstance(data, list)
    assert any(l["action"] == "create" for l in data)
    assert any(l["action"] == "submit" for l in data)
    assert any(l["action"] == "approve" for l in data)
    assert any(l["action"] == "execute_start" for l in data)
    assert any(l["action"] == "execute_success" for l in data)


def _create_whitelist_tool(client: TestClient, tool_code="test-whitelist-dml"):
    resp = client.put("/api/v1/ops/tools", json={
        "tool_code": tool_code,
        "tool_name_cn": "platform whitelist update",
        "system_code": "ASSET_PLATFORM",
        "source_code": "asset",
        "tool_type": "write",
        "risk_level": "high",
        "execution_mode": "whitelist_dml",
        "sql_or_endpoint_ref": "UPDATE asset.asset_ops_tool_templates SET description_cn = :description WHERE tool_code = :target_tool_code",
        "dry_run_sql": "SELECT count(*) FROM asset.asset_ops_tool_templates WHERE tool_code = :target_tool_code",
        "allowed_tables": ["asset.asset_ops_tool_templates"],
        "allowed_operations": ["UPDATE"],
        "require_approval": True,
        "require_second_confirm": True,
        "require_audit": True,
        "write_credential_ref": "env:PYTEST_ASSET_WRITE",
        "enabled": True,
        "rollback_note_cn": "Re-submit a new approved request with the previous description.",
    })
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


def _create_whitelist_run(client: TestClient, tool_code="test-whitelist-dml", requested_by="writerA"):
    resp = client.post("/api/v1/ops/runs", json={
        "tool_code": tool_code,
        "requested_by": requested_by,
        "input_params": {"target_tool_code": tool_code, "description": "updated by whitelist"},
    })
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


def test_whitelist_dml_requires_approval(client: TestClient):
    _create_whitelist_tool(client, "test-whitelist-approval")
    run = _create_whitelist_run(client, "test-whitelist-approval")
    resp = client.post(f"/api/v1/ops/runs/{run['id']}/execute", json={"second_confirm": True})
    assert resp.status_code == 400
    assert "approval" in resp.text


def test_whitelist_dml_dry_run_does_not_execute(client: TestClient):
    _create_whitelist_tool(client, "test-whitelist-dry-run")
    run = _create_whitelist_run(client, "test-whitelist-dry-run")
    _approve_run(client, run["id"], approved_by="approverB")
    resp = client.post(f"/api/v1/ops/runs/{run['id']}/execute", json={"dry_run": True, "second_confirm": True, "executed_by": "operatorC"})
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["status"] == "dry_run"
    assert data["risk_scan"]["valid"] is True
    assert data["estimated_count"] == 1

    runs = client.get("/api/v1/ops/runs?status=approved").json()["data"]["items"]
    assert any(item["id"] == run["id"] for item in runs)



def test_whitelist_dml_formal_execute_requires_d1_d5_confirmation(client: TestClient, monkeypatch):
    monkeypatch.setattr("app.api.v1.ops_tools.settings.ops_write_enabled", False, raising=False)
    monkeypatch.setattr("app.api.v1.ops_tools.settings.ops_write_d1_d5_confirmed", False, raising=False)
    monkeypatch.setattr("app.api.v1.ops_tools.settings.ops_write_confirmation_token", "", raising=False)
    _create_whitelist_tool(client, "test-whitelist-safety-gate")
    run = _create_whitelist_run(client, "test-whitelist-safety-gate")
    _approve_run(client, run["id"], approved_by="approverB")
    resp = client.post(f"/api/v1/ops/runs/{run['id']}/execute", json={"second_confirm": True, "executed_by": "operatorC"})
    assert resp.status_code == 403
    assert "D1-D5" in resp.text
def test_whitelist_dml_execute_audits_and_blocks_repeat(client: TestClient, monkeypatch):
    _enable_ops_write(monkeypatch)
    _create_whitelist_tool(client, "test-whitelist-execute")
    run = _create_whitelist_run(client, "test-whitelist-execute")
    _approve_run(client, run["id"], approved_by="approverB")
    resp = client.post(f"/api/v1/ops/runs/{run['id']}/execute", json={"second_confirm": True, "executed_by": "operatorC"})
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["status"] == "succeeded"
    assert data["affected_count"] == 1

    repeat = client.post(f"/api/v1/ops/runs/{run['id']}/execute", json={"second_confirm": True, "executed_by": "operatorC"})
    assert repeat.status_code == 400

    audit = client.get(f"/api/v1/ops/runs/{run['id']}/audit")
    assert audit.status_code == 200
    actions = [item["action"] for item in audit.json()["data"]]
    assert "execute_write" in actions
    assert "execute_success" in actions


def test_critical_whitelist_dml_forces_audit(client: TestClient, monkeypatch):
    _enable_ops_write(monkeypatch)
    _create_whitelist_tool(client, "test-whitelist-critical-audit")
    resp = client.put("/api/v1/ops/tools", json={
        "tool_code": "test-whitelist-critical-audit",
        "tool_name_cn": "critical platform whitelist update",
        "system_code": "ASSET_PLATFORM",
        "source_code": "asset",
        "tool_type": "write",
        "risk_level": "critical",
        "execution_mode": "whitelist_dml",
        "sql_or_endpoint_ref": "UPDATE asset.asset_ops_tool_templates SET description_cn = :description WHERE tool_code = :target_tool_code",
        "dry_run_sql": "SELECT count(*) FROM asset.asset_ops_tool_templates WHERE tool_code = :target_tool_code",
        "allowed_tables": ["asset.asset_ops_tool_templates"],
        "allowed_operations": ["UPDATE"],
        "require_approval": True,
        "require_second_confirm": True,
        "require_audit": False,
        "write_credential_ref": "env:PYTEST_ASSET_WRITE",
        "enabled": True,
        "rollback_note_cn": "Re-submit a new approved request with the previous description.",
    })
    assert resp.status_code == 200, resp.text
    run = _create_whitelist_run(client, "test-whitelist-critical-audit")
    _approve_run(client, run["id"], approved_by="approverB")

    execute = client.post(f"/api/v1/ops/runs/{run['id']}/execute", json={"second_confirm": True, "executed_by": "operatorC"})
    assert execute.status_code == 200, execute.text

    audit = client.get(f"/api/v1/ops/runs/{run['id']}/audit")
    assert audit.status_code == 200
    actions = [item["action"] for item in audit.json()["data"]]
    assert "execute_write" in actions
def test_whitelist_dml_rejects_non_asset_or_delete(client: TestClient, monkeypatch):
    _enable_ops_write(monkeypatch)
    resp = client.put("/api/v1/ops/tools", json={
        "tool_code": "test-whitelist-bad-sql",
        "tool_name_cn": "bad write",
        "system_code": "HIS",
        "source_code": "his",
        "tool_type": "write",
        "risk_level": "critical",
        "execution_mode": "whitelist_dml",
        "sql_or_endpoint_ref": "DELETE FROM his.patient WHERE id = :id",
        "allowed_tables": ["his.patient"],
        "allowed_operations": ["DELETE"],
        "require_approval": True,
        "require_second_confirm": True,
        "enabled": True,
    })
    assert resp.status_code == 200
    run = client.post("/api/v1/ops/runs", json={
        "tool_code": "test-whitelist-bad-sql",
        "requested_by": "writerA",
        "input_params": {"id": "1"},
    }).json()["data"]
    _approve_run(client, run["id"], approved_by="approverB")
    execute = client.post(f"/api/v1/ops/runs/{run['id']}/execute", json={"second_confirm": True})
    assert execute.status_code == 400
    assert "platform asset source" in execute.text or "forbidden" in execute.text or "only single" in execute.text

def test_stored_procedure_executor_is_disabled(client: TestClient):
    resp = client.put("/api/v1/ops/tools", json={
        "tool_code": "test-sp-disabled",
        "tool_name_cn": "stored procedure disabled",
        "system_code": "ASSET_PLATFORM",
        "source_code": "asset",
        "tool_type": "admin",
        "risk_level": "high",
        "execution_mode": "stored_procedure",
        "sql_or_endpoint_ref": "asset.do_something",
        "enabled": True,
        "require_approval": True,
        "require_second_confirm": False,
    })
    assert resp.status_code == 200
    run = _create_run(client, "test-sp-disabled", requested_by="userA")
    _approve_run(client, run["id"], approved_by="userB")
    execute = client.post(f"/api/v1/ops/runs/{run['id']}/execute")
    assert execute.status_code == 400
    assert "disabled in phase 1" in execute.text


def test_http_api_executor_is_disabled(client: TestClient):
    resp = client.put("/api/v1/ops/tools", json={
        "tool_code": "test-http-disabled",
        "tool_name_cn": "http api disabled",
        "system_code": "ASSET_PLATFORM",
        "source_code": "asset",
        "tool_type": "admin",
        "risk_level": "high",
        "execution_mode": "http_api",
        "sql_or_endpoint_ref": "https://example.invalid/hook",
        "enabled": True,
        "require_approval": True,
        "require_second_confirm": False,
    })
    assert resp.status_code == 200
    run = _create_run(client, "test-http-disabled", requested_by="userA")
    _approve_run(client, run["id"], approved_by="userB")
    execute = client.post(f"/api/v1/ops/runs/{run['id']}/execute")
    assert execute.status_code == 400
    assert "disabled in phase 1" in execute.text
