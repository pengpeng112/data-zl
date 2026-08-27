"""146 E-stage contract tests: table source isolation, accounts, ops, snapshots, hit rates."""
from fastapi.testclient import TestClient

from app.core.db import SessionLocal
from app.models.governance import MetadataSnapshot
from app.models.identity import IdentityAccount


def _tool_payload(code: str) -> dict:
    return {
        "tool_code": code,
        "tool_name_cn": f"E 契约工具 {code}",
        "system_code": "ASSET_PLATFORM",
        "source_code": "asset",
        "tool_type": "query",
        "risk_level": "low",
        "execution_mode": "readonly_sql",
        "sql_or_endpoint_ref": "SELECT 1 AS ok",
        "enabled": True,
        "require_approval": True,
        "require_second_confirm": False,
    }


def test_table_apis_isolate_same_name_tables_by_source(client: TestClient):
    # Seed guarantees HIS.PAT_VISIT on his_source; ODS.TEST_ASSET on ods source.
    detail_default = client.get("/api/v1/tables/HIS/PAT_VISIT")
    assert detail_default.status_code == 200

    wrong_source = client.get("/api/v1/tables/HIS/PAT_VISIT?source_code=ods_8_216")
    assert wrong_source.status_code == 404

    right_source = client.get("/api/v1/tables/HIS/PAT_VISIT?source_code=his_source_10_10_10_15")
    assert right_source.status_code == 200

    columns = client.get("/api/v1/tables/HIS/PAT_VISIT/columns?source_code=his_source_10_10_10_15")
    assert columns.status_code == 200
    assert all(col["schema_name"] == "HIS" for col in columns.json()["data"])

    columns_wrong = client.get("/api/v1/tables/HIS/PAT_VISIT/columns?source_code=ods_8_216")
    assert columns_wrong.status_code == 200
    assert columns_wrong.json()["data"] == []

    relations_ok = client.get("/api/v1/tables/HIS/PAT_VISIT/relations?source_code=his_source_10_10_10_15")
    assert relations_ok.status_code == 200

    relations_wrong = client.get("/api/v1/tables/HIS/PAT_VISIT/relations?source_code=ods_8_216")
    assert relations_wrong.status_code == 404


def test_accounts_pagination_keyword_and_unbind(client: TestClient):
    db = SessionLocal()
    try:
        for i in range(3):
            db.add(IdentityAccount(
                system_code="PYTEST", account_id=f"e6-user-{i}",
                account_name=f"E6 账号{i}", person_code="P001" if i == 0 else None,
                account_status="active",
            ))
        db.commit()
    finally:
        db.close()

    page = client.get("/api/v1/identity/accounts?system_code=PYTEST&page=1&page_size=2")
    assert page.status_code == 200
    body = page.json()["data"]
    assert body["total"] >= 3
    assert len(body["items"]) == 2
    assert {"total", "page", "page_size", "items"} <= set(body)

    keyword = client.get("/api/v1/identity/accounts?keyword=e6-user-0")
    assert keyword.json()["data"]["total"] == 1
    assert keyword.json()["data"]["items"][0]["account_id"] == "e6-user-0"

    bound = next(item for item in client.get("/api/v1/identity/accounts?keyword=e6-user-0").json()["data"]["items"] if item["person_code"])
    unbind = client.request("DELETE", f"/api/v1/identity/accounts/{bound['id']}/binding", json={"reason": "E6 解绑验证"})
    assert unbind.status_code == 200, unbind.text
    assert unbind.json()["data"]["person_code"] is None

    db = SessionLocal()
    try:
        row = db.get(IdentityAccount, bound["id"])
        assert row.person_code is None
        assert row.account_id == "e6-user-0", "解绑不得删除账号"
        from app.models.governance_base import GovernAuditLog
        audit = db.query(GovernAuditLog).filter(
            GovernAuditLog.module == "identity",
            GovernAuditLog.entity_ref == str(bound["id"]),
            GovernAuditLog.action == "unbind",
        ).first()
        assert audit is not None
    finally:
        db.close()

    assert client.request("DELETE", "/api/v1/identity/accounts/999999/binding").status_code == 404


def test_ops_tools_pagination_and_runs_run_id_locate(client: TestClient):
    for i in range(3):
        code = f"e7-tool-{i}"
        assert client.put("/api/v1/ops/tools", json=_tool_payload(code)).status_code == 200

    page = client.get("/api/v1/ops/tools?page=1&page_size=2&keyword=e7-tool")
    assert page.status_code == 200
    body = page.json()["data"]
    assert body["total"] == 3
    assert len(body["items"]) == 2

    runs = client.get("/api/v1/ops/runs")
    assert runs.status_code == 200
    assert {"total", "page", "page_size", "items"} <= set(runs.json()["data"])


def test_audit_logs_filters_summary_and_export(client: TestClient):
    client.post("/api/v1/permissions/seed?operator=tester")
    matrix = client.put("/api/v1/permissions/roles/asset_viewer/matrix", json={
        "permissions": ["asset", "asset.table.view"],
        "operator": "e7-auditor",
        "reason": "e7 audit filter test",
    })
    assert matrix.status_code == 200

    listed = client.get("/api/v1/govern/audit-logs?module=permission&page=1&page_size=5")
    assert listed.status_code == 200
    body = listed.json()["data"]
    assert body["total"] >= 1
    assert "after_data" in body["items"][0]

    # 操作者恒取登录态（test-platform-admin），请求体 operator 不参与审计。
    by_operator = client.get("/api/v1/govern/audit-logs?operator=test-platform-admin")
    assert by_operator.json()["data"]["total"] >= 1

    bad_time = client.get("/api/v1/govern/audit-logs?created_from=not-a-date")
    assert bad_time.status_code == 400

    summary = client.get("/api/v1/govern/audit-logs/summary?module=permission")
    assert summary.status_code == 200
    summary_body = summary.json()["data"]
    assert summary_body["total"] >= 1
    assert "permission" in summary_body["by_module"]

    export = client.get("/api/v1/govern/audit-logs/export?module=permission")
    assert export.status_code == 200
    assert "text/csv" in export.headers["content-type"]
    assert "audit-logs.csv" in export.headers.get("content-disposition", "")
    assert export.text.splitlines()[0].startswith("id,created_at")


def test_metadata_snapshot_archive_protection_and_changes_batch(client: TestClient):
    db = SessionLocal()
    try:
        from app.models.metadata_change import AssetMetadataColumnSnapshot, AssetMetadataChangeEvent
        snap_a = MetadataSnapshot(label="e9-a", scope="column_level", source_code="e9_source", table_count=1, column_count=1)
        snap_b = MetadataSnapshot(label="e9-b", scope="column_level", source_code="e9_source", table_count=1, column_count=1)
        db.add_all([snap_a, snap_b])
        db.flush()
        db.add(AssetMetadataColumnSnapshot(
            snapshot_id=snap_a.id, system_code="PYTEST", source_code="e9_source",
            namespace_name="PUBLIC", table_name="T_E9", column_name="C1", data_type="TEXT",
        ))
        # snap_b is referenced by a change event -> archive must be refused.
        db.add(AssetMetadataChangeEvent(
            snapshot_id_from=snap_b.id, snapshot_id_to=snap_b.id,
            system_code="PYTEST", source_code="e9_source",
            namespace_name="PUBLIC", table_name="T_E9", column_name="C1",
            change_type="column_added", severity="low", status="open",
        ))
        db.commit()
        snap_a_id, snap_b_id = snap_a.id, snap_b.id
        event_id = db.query(AssetMetadataChangeEvent).filter(AssetMetadataChangeEvent.snapshot_id_from == snap_b_id).first().id
    finally:
        db.close()

    listing = client.get("/api/v1/metadata-snapshots?source_code=e9_source")
    assert listing.status_code == 200
    assert listing.json()["data"]["total"] == 2

    detail = client.get(f"/api/v1/metadata-snapshots/{snap_a_id}")
    assert detail.status_code == 200
    assert detail.json()["data"]["column_sample"][0]["column_name"] == "C1"
    assert client.get("/api/v1/metadata-snapshots/999999").status_code == 404

    referenced = client.post(f"/api/v1/metadata-snapshots/{snap_b_id}/archive")
    assert referenced.status_code == 409

    archived = client.post(f"/api/v1/metadata-snapshots/{snap_a_id}/archive")
    assert archived.status_code == 200, archived.text
    assert archived.json()["data"]["archived_by"] == "test-platform-admin"

    default_list = client.get("/api/v1/metadata-snapshots?source_code=e9_source")
    ids = {item["id"] for item in default_list.json()["data"]["items"]}
    assert snap_a_id not in ids and snap_b_id in ids
    with_archived = client.get("/api/v1/metadata-snapshots?source_code=e9_source&include_archived=true")
    assert snap_a_id in {item["id"] for item in with_archived.json()["data"]["items"]}
    assert client.post(f"/api/v1/metadata-snapshots/{snap_a_id}/archive").status_code == 400

    batch = client.post("/api/v1/metadata-changes/batch", json={
        "ids": [event_id, 999999], "action": "acknowledge", "assigned_to": "e6-owner",
    })
    assert batch.status_code == 200, batch.text
    assert batch.json()["data"]["updated"] == 1
    assert batch.json()["data"]["missing"] == [999999]

    reopen = client.post("/api/v1/metadata-changes/batch", json={"ids": [event_id], "action": "reopen"})
    assert reopen.status_code == 200
    row = client.get("/api/v1/metadata-changes?keyword=T_E9").json()["data"]["items"][0]
    assert row["status"] == "open"


def test_relation_hit_rate_range_filters_before_pagination(client: TestClient):
    all_rates = client.get("/api/v1/relations/hit-rates")
    assert all_rates.status_code == 200

    low_only = client.get("/api/v1/relations/hit-rates?hit_rate_max=0.5")
    body = low_only.json()["data"]
    assert body["total"] <= all_rates.json()["data"]["total"]
    assert all(item.get("hit_rate") is not None and item["hit_rate"] <= 0.5 for item in body["items"])
    # summary 与 total 同口径：过滤后的 avg 只统计命中区间内的关系。
    if body["items"]:
        assert body["with_rate"] == body["total"]

    invalid = client.get("/api/v1/relations/hit-rates?hit_rate_min=1.5")
    assert invalid.status_code == 422


def test_relations_path_direction_and_max_hops(client: TestClient):
    # Seeded HIS.PAT_VISIT -> HIS.PAT_MASTER_INDEX (rel 900001).
    both = client.get("/api/v1/relations/path", params={"from": "HIS.PAT_MASTER_INDEX", "to": "HIS.PAT_VISIT"})
    assert both.status_code == 200
    assert both.json()["data"]["path"] == ["HIS.PAT_MASTER_INDEX", "HIS.PAT_VISIT"]

    out_only = client.get("/api/v1/relations/path", params={
        "from": "HIS.PAT_MASTER_INDEX", "to": "HIS.PAT_VISIT", "direction": "out",
    })
    assert out_only.status_code == 200
    assert out_only.json()["data"]["path"] is None

    hop_limited = client.get("/api/v1/relations/path", params={
        "from": "HIS.PAT_VISIT", "to": "HIS.PAT_MASTER_INDEX", "max_hops": 1,
    })
    assert hop_limited.status_code == 200
    assert hop_limited.json()["data"]["path"] == ["HIS.PAT_VISIT", "HIS.PAT_MASTER_INDEX"]

    same = client.get("/api/v1/relations/path", params={"from": "HIS.PAT_VISIT", "to": "HIS.PAT_VISIT"})
    assert same.json()["data"]["path"] == ["HIS.PAT_VISIT"]
