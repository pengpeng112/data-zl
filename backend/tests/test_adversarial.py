"""对抗性测试：边界条件、异常路径、安全约束验证"""


def test_system_create_missing_required(client):
    resp = client.put("/api/v1/systems", json={"system_code": "", "system_name_cn": ""})
    assert resp.status_code in (200, 422, 400)


def test_source_create_nonexistent_system(client):
    resp = client.put("/api/v1/sources", json={
        "system_code": "NONEXISTENT_XYZ_12345",
        "source_code": "test-source-x",
        "source_name_cn": "不存在系统",
    })
    assert resp.status_code == 400


def test_role_delete_nonexistent(client):
    resp = client.delete("/api/v1/govern/roles/nonexistent-role")
    assert resp.status_code == 404


def test_change_request_approve_twice(client):
    cr = client.post("/api/v1/govern/change-requests", json={
        "module": "identity", "entity_type": "account",
        "request_type": "test", "requested_by": "user1",
    })
    cr_id = cr.json()["data"]["id"]
    client.patch(f"/api/v1/govern/change-requests/{cr_id}/approve", json={"approved_by": "user2"})
    resp = client.patch(f"/api/v1/govern/change-requests/{cr_id}/approve", json={"approved_by": "user3"})
    assert resp.status_code == 400


def test_change_request_reject_then_approve(client):
    cr = client.post("/api/v1/govern/change-requests", json={
        "module": "test", "entity_type": "test",
        "request_type": "test", "requested_by": "a",
    })
    cr_id = cr.json()["data"]["id"]
    client.patch(f"/api/v1/govern/change-requests/{cr_id}/reject", json={"approved_by": "b"})
    resp = client.patch(f"/api/v1/govern/change-requests/{cr_id}/approve", json={"approved_by": "c"})
    assert resp.status_code == 400


def test_self_approve_change_request(client):
    cr = client.post("/api/v1/govern/change-requests", json={
        "module": "test", "entity_type": "test",
        "request_type": "test", "requested_by": "same_user",
    })
    cr_id = cr.json()["data"]["id"]
    resp = client.patch(f"/api/v1/govern/change-requests/{cr_id}/approve", json={"approved_by": "same_user"})
    assert resp.status_code == 400


def test_ops_tool_run_self_approve(client):
    client.put("/api/v1/ops/tools", json={
        "tool_code": "test-tool", "tool_name_cn": "测试工具",
        "system_code": "DATA_CENTER", "tool_type": "query",
        "execution_mode": "readonly_sql", "input_schema": {"fields": []},
        "enabled": True, "require_approval": True,
    })
    run = client.post("/api/v1/ops/runs", json={
        "tool_code": "test-tool", "requested_by": "same",
    })
    run_id = run.json()["data"]["id"]
    resp = client.patch(f"/api/v1/ops/runs/{run_id}/approve", json={"approved_by": "same"})
    assert resp.status_code == 400


def test_ops_tool_create_no_enabled(client):
    resp = client.post("/api/v1/ops/runs", json={
        "tool_code": "nonexistent-tool", "requested_by": "u",
    })
    assert resp.status_code == 400


def test_metadata_diff_nonexistent_snapshots(client):
    resp = client.post("/api/v1/metadata-changes/diff", params={
        "snapshot_id_from": 99999, "snapshot_id_to": 99998,
    })
    assert resp.status_code == 404


def test_collect_metadata_nonexistent_source(client):
    resp = client.post("/api/v1/sources/nonexistent-source/collect-metadata")
    assert resp.status_code == 400


def test_annotation_update_nonexistent_table(client):
    resp = client.patch("/api/v1/tables/999999/annotation", json={"table_name_cn": "x"})
    assert resp.status_code == 404


def test_annotation_update_nonexistent_column(client):
    resp = client.patch("/api/v1/columns/999999/annotation", json={"column_name_cn": "x"})
    assert resp.status_code == 404


def test_relation_update_nonexistent(client):
    resp = client.patch("/api/v1/relations/999999", json={"confidence": "A"})
    assert resp.status_code == 404


def test_relation_review_invalid_action(client):
    resp = client.patch("/api/v1/relations/1/review", params={"action": "invalid"})
    assert resp.status_code == 400


def test_event_update_nonexistent(client):
    resp = client.patch("/api/v1/govern/events/99999", params={"status": "resolved"})
    assert resp.status_code == 404


def test_change_rule_upsert(client):
    resp = client.put("/api/v1/govern/change-rules", json={
        "rule_code": "test-rule-ignore", "rule_name_cn": "测试忽略规则",
        "change_type": "table_added", "ignore_enabled": True,
    })
    assert resp.status_code == 200
    assert resp.json()["data"]["rule_code"] == "test-rule-ignore"


def test_missing_annotations_empty_keyword(client):
    resp = client.get("/api/v1/annotations/missing")
    assert resp.status_code == 200
    d = resp.json()["data"]
    assert "tables_missing" in d
    assert "columns_missing" in d


def test_quality_summary_by_system(client):
    resp = client.get("/api/v1/quality/summary/by-system")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert isinstance(data, list)
    assert any(s["system_code"] == "DATA_CENTER" for s in data)


def test_assets_tree_with_filter(client):
    resp = client.get("/api/v1/assets/tree", params={"system_code": "DATA_CENTER"})
    assert resp.status_code == 200
    tree = resp.json()["data"]
    assert len(tree) > 0
    assert all(n["system_code"] == "DATA_CENTER" for n in tree)


def test_scheduler_jobs_list(client):
    resp = client.get("/api/v1/govern/scheduler/jobs", params={"status": "success"})
    assert resp.status_code == 200


def test_events_create_and_filter(client):
    client.post("/api/v1/govern/events", json={
        "event_type": "meta_change", "module": "metadata",
        "title": "测试事件", "severity": "high",
    })
    resp = client.get("/api/v1/govern/events", params={"severity": "high"})
    assert resp.status_code == 200


def test_identity_person_profile_nonexistent(client):
    resp = client.get("/api/v1/identity/persons/nonexistent-person")
    assert resp.status_code == 404


def test_medical_mapping_upsert(client):
    resp = client.put("/api/v1/dict-medical/mappings", json={
        "category_code": "diagnosis",
        "from_code_set": "clinical_diag", "from_item_code": "A001",
        "to_code_set": "national_diag", "to_item_code": "ICD-A01",
    })
    assert resp.status_code == 200
    assert resp.json()["data"]["id"] is not None


def test_ai_system_context_missing_system(client):
    resp = client.get("/api/v1/ai/system-context", params={"system_code": "NONEXISTENT"})
    assert resp.status_code == 200
    assert resp.json()["data"]["total_tables"] == 0


def test_sql_risk_scan_dangerous(client):
    resp = client.post("/api/v1/ai/sql-risk-scan", json={"sql_text": "DROP TABLE asset.test"})
    assert resp.status_code == 200
    assert resp.json()["data"]["risk_flags"].get("blocked") is True


def test_sql_risk_scan_safe(client):
    resp = client.post("/api/v1/ai/sql-risk-scan", json={"sql_text": "SELECT * FROM asset.asset_tables WHERE id=1"})
    assert resp.status_code == 200
    assert resp.json()["data"]["safe_for_review"] is True


def test_pagination_boundary(client):
    resp = client.get("/api/v1/tables", params={"page": 0, "page_size": 10})
    assert resp.status_code == 422
    resp = client.get("/api/v1/tables", params={"page": 1, "page_size": 1000})
    assert resp.status_code == 422
