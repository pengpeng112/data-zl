from fastapi.testclient import TestClient


def _get_or_create_rule(client: TestClient, rule_code: str, **extra) -> dict:
    """幂等获取或创建规则，返回 {id, rule_code}。已存在则直接获取。"""
    resp = client.post("/api/v1/quality/rules", json={"rule_code": rule_code, **extra})
    if resp.status_code == 200:
        return resp.json()["data"]
    # 已存在 → 从列表中查找
    rules = client.get("/api/v1/quality/rules").json()["data"]
    for r in rules:
        if r["rule_code"] == rule_code:
            return {"id": r["id"], "rule_code": r["rule_code"]}
    raise AssertionError(f"无法获取或创建规则 {rule_code}: {resp.status_code} {resp.text}")


def test_quality_rules(client: TestClient):
    resp = client.get("/api/v1/quality/rules")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert isinstance(data, list)
    assert any(r["rule_code"] == "REL_ORPHAN_RATE" for r in data)


def test_run_quality_check(client: TestClient):
    resp = client.post("/api/v1/quality/checks/run")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "success"
    assert "run_id" in data
    assert data["total_findings"] >= 0


def test_quality_check_runs(client: TestClient):
    resp = client.get("/api/v1/quality/checks/runs")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "items" in data
    assert "total" in data


def test_quality_findings(client: TestClient):
    resp = client.get("/api/v1/quality/findings")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "items" in data
    assert "total" in data


def test_quality_findings_filter(client: TestClient):
    resp = client.get("/api/v1/quality/findings?severity=critical")
    assert resp.status_code == 200
    data = resp.json()["data"]
    for item in data["items"]:
        assert item["severity"] == "critical"


def test_quality_summary(client: TestClient):
    resp = client.get("/api/v1/quality/summary")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "total_findings" in data
    assert "open_count" in data
    assert "critical_count" in data
    assert "top_tables" in data


def test_update_finding(client: TestClient):
    resp = client.get("/api/v1/quality/findings?page_size=1")
    if resp.status_code != 200:
        return
    items = resp.json()["data"]["items"]
    if items:
        finding_id = items[0]["id"]
        patch_resp = client.patch(
            f"/api/v1/quality/findings/{finding_id}",
            json={"status": "acknowledged", "note": "test"},
        )
        assert patch_resp.status_code == 200
        assert patch_resp.json()["data"]["status"] == "acknowledged"


# ── Q3 新增端点测试 ──


def test_create_rule(client: TestClient):
    data = _get_or_create_rule(client, "TEST_RULE_001",
        rule_name="测试唯一性规则",
        rule_category="UNIQUE",
        check_scope="TABLE_INNER",
        constraint_level="HARD",
        business_domain="测试",
        execution_mode="sql_template",
        check_sql="SELECT COUNT(*) FROM dual",
        error_level="major",
        enabled=False,
    )
    assert data["rule_code"] == "TEST_RULE_001"


def test_create_rule_duplicate(client: TestClient):
    _get_or_create_rule(client, "TEST_DUP_001", rule_name="重复测试", rule_category="UNIQUE", enabled=False)
    resp = client.post("/api/v1/quality/rules", json={
        "rule_code": "TEST_DUP_001", "rule_name": "重复测试2",
        "rule_category": "UNIQUE", "enabled": False,
    })
    assert resp.status_code == 400


def test_patch_rule(client: TestClient):
    data = _get_or_create_rule(client, "TEST_PATCH_001",
        rule_name="补丁测试", rule_category="COMPLETE", enabled=False)
    rule_id = data["id"]
    resp = client.patch(f"/api/v1/quality/rules/{rule_id}", json={
        "rule_name": "补丁后名称",
        "constraint_level": "SOFT",
    })
    assert resp.status_code == 200
    assert resp.json()["data"]["rule_code"] == "TEST_PATCH_001"


def test_patch_rule_not_found(client: TestClient):
    resp = client.patch("/api/v1/quality/rules/999999", json={"rule_name": "不存在"})
    assert resp.status_code == 404


def test_toggle_rule(client: TestClient):
    data = _get_or_create_rule(client, "TEST_TOGGLE_001",
        rule_name="启停测试", rule_category="STANDARD", enabled=False)
    rule_id = data["id"]
    resp = client.post(f"/api/v1/quality/rules/{rule_id}/enable?enabled=true")
    assert resp.status_code == 200
    assert resp.json()["data"]["enabled"] is True


def test_validate_sql(client: TestClient):
    data = _get_or_create_rule(client, "TEST_SQL_001",
        rule_name="SQL校验测试", rule_category="STANDARD",
        execution_mode="sql_template",
        check_sql="SELECT COUNT(*) FROM HIS.PAT_VISIT WHERE ROWNUM <= 100",
        enabled=False)
    rule_id = data["id"]
    resp = client.post(f"/api/v1/quality/rules/{rule_id}/validate-sql")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["valid"] is True


def test_validate_sql_dangerous(client: TestClient):
    data = _get_or_create_rule(client, "TEST_SQL_DROP",
        rule_name="危险SQL测试", rule_category="STANDARD",
        execution_mode="sql_template",
        check_sql="DROP TABLE asset.asset_tables",
        enabled=False)
    rule_id = data["id"]
    resp = client.post(f"/api/v1/quality/rules/{rule_id}/validate-sql")
    assert resp.status_code == 200
    assert resp.json()["data"]["valid"] is False


def test_rule_from_template(client: TestClient):
    resp = client.post("/api/v1/quality/rules/from-template", json={
        "template_type": "unique_pk",
        "params": {"table_name": "PAT_VISIT", "pk_column": "PATIENT_ID", "namespace": "HIS"},
    })
    assert resp.status_code == 200
    assert "SELECT" in resp.json()["data"]["sql"]


def test_rule_from_template_invalid(client: TestClient):
    resp = client.post("/api/v1/quality/rules/from-template", json={
        "template_type": "nonexistent_template",
        "params": {},
    })
    assert resp.status_code == 400


def test_metrics(client: TestClient):
    resp = client.get("/api/v1/quality/metrics")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "total_rules" in data
    assert "total_findings" in data
    assert "pass_rate" in data
    assert "rule_categories" in data
    assert "top_tables" in data


def test_finding_assign(client: TestClient):
    list_resp = client.get("/api/v1/quality/findings?page_size=1")
    items = list_resp.json()["data"]["items"]
    if not items:
        return
    finding_id = items[0]["id"]
    resp = client.post(f"/api/v1/quality/findings/{finding_id}/assign", json={
        "assigned_to": "test_admin",
        "note": "分派给测试管理员",
    })
    assert resp.status_code == 200
    assert resp.json()["data"]["assigned_to"] == "test_admin"
    assert resp.json()["data"]["rectification_status"] == "assigned"


def test_finding_recheck(client: TestClient):
    list_resp = client.get("/api/v1/quality/findings?page_size=1")
    items = list_resp.json()["data"]["items"]
    if not items:
        return
    finding_id = items[0]["id"]
    resp = client.post(
        f"/api/v1/quality/findings/{finding_id}/recheck?status=confirmed"
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["rectification_status"] == "confirmed"


def test_finding_recheck_invalid_status(client: TestClient):
    list_resp = client.get("/api/v1/quality/findings?page_size=1")
    items = list_resp.json()["data"]["items"]
    if not items:
        return
    finding_id = items[0]["id"]
    resp = client.post(
        f"/api/v1/quality/findings/{finding_id}/recheck?status=invalid_xyz"
    )
    assert resp.status_code == 400
