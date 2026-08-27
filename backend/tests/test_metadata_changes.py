from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.db import SessionLocal
from app.models.asset_system import AssetDataSource
from app.models.governance import MetadataSnapshot
from app.models.governance_ops import SchedulerJob
from app.models.metadata_change import AssetMetadataColumnSnapshot


def _create_column_snapshot(db, source_code: str, label: str, columns: list[str]) -> MetadataSnapshot:
    snapshot = MetadataSnapshot(
        label=label,
        scope="column_level",
        source_code=source_code,
        table_count=1,
        column_count=len(columns),
        relation_count=0,
    )
    db.add(snapshot)
    db.flush()
    for column_name in columns:
        db.add(AssetMetadataColumnSnapshot(
            snapshot_id=snapshot.id,
            system_code="PYTEST",
            source_code=source_code,
            namespace_name="PUBLIC",
            table_name="PATIENT",
            column_name=column_name,
            data_type="TEXT",
        ))
    return snapshot


def _rich_column_snapshot(db, source_code: str, label: str, columns: list[tuple]) -> MetadataSnapshot:
    """columns: (column_name, data_type, length, nullable)."""
    snapshot = MetadataSnapshot(
        label=label,
        scope="column_level",
        source_code=source_code,
        table_count=1,
        column_count=len(columns),
        relation_count=0,
    )
    db.add(snapshot)
    db.flush()
    for column_name, data_type, length, nullable in columns:
        db.add(AssetMetadataColumnSnapshot(
            snapshot_id=snapshot.id,
            system_code="PYTEST",
            source_code=source_code,
            namespace_name="PUBLIC",
            table_name="PATIENT",
            column_name=column_name,
            data_type=data_type,
            length=length,
            nullable=nullable,
        ))
    return snapshot


def test_collect_metadata_nonexistent_source(client: TestClient):
    resp = client.post("/api/v1/sources/nonexistent_source/collect-metadata")
    assert resp.status_code == 400


def test_list_changes(client: TestClient):
    resp = client.get("/api/v1/metadata-changes")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "items" in data
    assert "total" in data
    assert "page" in data


def test_list_changes_system_code_filter(client: TestClient):
    resp = client.get("/api/v1/metadata-changes?system_code=DATA_CENTER")
    assert resp.status_code == 200
    data = resp.json()["data"]
    for item in data["items"]:
        assert item["system_code"] == "DATA_CENTER"


def test_list_changes_change_type_filter(client: TestClient):
    resp = client.get("/api/v1/metadata-changes?change_type=column_added")
    assert resp.status_code == 200
    data = resp.json()["data"]
    for item in data["items"]:
        assert item["change_type"] == "column_added"


def test_list_changes_severity_filter(client: TestClient):
    resp = client.get("/api/v1/metadata-changes?severity=high")
    assert resp.status_code == 200
    data = resp.json()["data"]
    for item in data["items"]:
        assert item["severity"] == "high"


def test_update_change_404(client: TestClient):
    resp = client.patch("/api/v1/metadata-changes/99999?status=acknowledged&assigned_to=user1")
    assert resp.status_code == 404


def test_changes_summary(client: TestClient):
    resp = client.get("/api/v1/metadata-changes/summary")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "total" in data
    assert "by_system" in data
    assert "by_type" in data
    assert "open" in data
    assert "acknowledged" in data
    assert "resolved" in data


def test_diff_nonexistent_snapshots(client: TestClient):
    resp = client.post("/api/v1/metadata-changes/diff?snapshot_id_from=99999&snapshot_id_to=99998")
    assert resp.status_code == 404


def test_diff_valid_snapshots(client: TestClient):
    r1 = client.post("/api/v1/admin/snapshots", json={"label": "diff_snap_1"})
    assert r1.status_code == 200
    id1 = r1.json()["data"]["id"]

    r2 = client.post("/api/v1/admin/snapshots", json={"label": "diff_snap_2"})
    assert r2.status_code == 200
    id2 = r2.json()["data"]["id"]

    resp = client.post(f"/api/v1/metadata-changes/diff?snapshot_id_from={id1}&snapshot_id_to={id2}")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "snapshot_from" in data
    assert "snapshot_to" in data
    assert "total_changes" in data
    assert data["snapshot_from"]["id"] == id1
    assert data["snapshot_to"]["id"] == id2


def test_change_impact_404(client: TestClient):
    resp = client.get("/api/v1/metadata-changes/99999/impact")
    assert resp.status_code == 404


def _preview_pair(db):
    from_src = _rich_column_snapshot(db, "pytest_preview", "old", [
        ("ID", "TEXT", None, "N"),
        ("NAME", "TEXT", 10, "Y"),
        ("LEGACY_COL", "TEXT", None, "Y"),
    ])
    to_src = _rich_column_snapshot(db, "pytest_preview", "new", [
        ("ID", "TEXT", None, "N"),
        ("NAME", "VARCHAR2", 20, "Y"),
        ("AGE", "NUMBER", None, "Y"),
    ])
    db.commit()
    return from_src.id, to_src.id


def test_diff_preview_is_zero_write_with_field_level_items(client: TestClient):
    from app.models.metadata_change import AssetMetadataChangeEvent

    db = SessionLocal()
    try:
        from_id, to_id = _preview_pair(db)
    finally:
        db.close()

    preview = client.post("/api/v1/metadata-changes/diff-preview", json={
        "source": "pytest_preview", "from": from_id, "to": to_id,
    })
    assert preview.status_code == 200, preview.text
    data = preview.json()["data"]
    # NAME: type+length change; AGE added; LEGACY_COL removed -> 4 column events total.
    assert data["summary"]["total"] == 4
    assert data["summary"]["tables_affected"] == 1
    # column_removed and column_data_type_changed are both high severity.
    assert data["summary"]["by_severity"]["high"] == 2
    assert data["summary"]["by_type"]["column_added"] == 1

    by_type = {item["change_type"]: item for item in data["items"]}
    added = by_type["column_added"]
    assert added["object_type"] == "column"
    assert added["table_name"] == "PATIENT"
    assert added["namespace"] == "PUBLIC"
    assert added["object_name"] == "AGE"
    assert added["after_value"] == '{"data_type": "NUMBER", "length": null, "nullable": "Y", "comment": null, "is_primary_key": false}'
    assert added["quality_impact"] is None

    removed = by_type["column_removed"]
    assert removed["severity"] == "high"
    assert removed["quality_impact"] is not None
    assert "质量 finding" in removed["quality_impact"]

    type_changed = by_type["column_data_type_changed"]
    assert type_changed["field_name"] == "data_type"
    assert type_changed["before_value"] == '{"data_type": "TEXT"}'
    assert type_changed["after_value"] == '{"data_type": "VARCHAR2"}'

    # Zero-write guarantee: no events or quality findings persisted by preview.
    db = SessionLocal()
    try:
        events = db.query(AssetMetadataChangeEvent).filter(
            AssetMetadataChangeEvent.snapshot_id_from == from_id,
            AssetMetadataChangeEvent.snapshot_id_to == to_id,
        ).all()
        assert events == []
    finally:
        db.close()


def test_diff_preview_filters_and_pagination(client: TestClient):
    db = SessionLocal()
    try:
        from_id, to_id = _preview_pair(db)
    finally:
        db.close()

    only_added = client.post("/api/v1/metadata-changes/diff-preview", json={
        "source": "pytest_preview", "from": from_id, "to": to_id, "type": "column_added",
    })
    body = only_added.json()["data"]
    assert body["total"] == 1
    assert body["items"][0]["object_name"] == "AGE"

    only_high = client.post("/api/v1/metadata-changes/diff-preview", json={
        "source": "pytest_preview", "from": from_id, "to": to_id, "severity": "high",
    })
    assert only_high.json()["data"]["total"] == 2
    assert {item["change_type"] for item in only_high.json()["data"]["items"]} == {"column_removed", "column_data_type_changed"}

    keyword = client.post("/api/v1/metadata-changes/diff-preview", json={
        "source": "pytest_preview", "from": from_id, "to": to_id, "keyword": "NAME",
    })
    assert keyword.json()["data"]["total"] == 2  # type + length change on NAME

    paged = client.post("/api/v1/metadata-changes/diff-preview", json={
        "source": "pytest_preview", "from": from_id, "to": to_id, "page": 1, "page_size": 2,
    })
    paged_body = paged.json()["data"]
    assert paged_body["total"] == 4
    assert len(paged_body["items"]) == 2
    assert paged_body["page"] == 1
    assert paged_body["page_size"] == 2

    empty = client.post("/api/v1/metadata-changes/diff-preview", json={
        "source": "pytest_preview", "from": from_id, "to": to_id, "keyword": "NO_SUCH_COLUMN",
    })
    assert empty.json()["data"]["total"] == 0
    assert empty.json()["data"]["items"] == []


def test_diff_preview_validation(client: TestClient):
    db = SessionLocal()
    try:
        from_id, to_id = _preview_pair(db)
        other = _create_column_snapshot(db, "pytest_other", "other", ["ID"])
        db.commit()
        other_id = other.id
    finally:
        db.close()

    missing = client.post("/api/v1/metadata-changes/diff-preview", json={
        "source": "pytest_preview", "from": 999999, "to": to_id,
    })
    assert missing.status_code == 404

    cross = client.post("/api/v1/metadata-changes/diff-preview", json={
        "source": "pytest_preview", "from": from_id, "to": other_id,
    })
    assert cross.status_code == 400

    mismatch = client.post("/api/v1/metadata-changes/diff-preview", json={
        "source": "wrong_source", "from": from_id, "to": to_id,
    })
    assert mismatch.status_code == 400


def test_generate_change_events_is_idempotent_with_audit(client: TestClient):
    from app.models.governance_base import GovernAuditLog
    from app.models.metadata_change import AssetMetadataChangeEvent
    from app.models.quality import QualityFinding

    db = SessionLocal()
    try:
        from_id, to_id = _preview_pair(db)
    finally:
        db.close()

    first = client.post("/api/v1/metadata-changes/diff", params={
        "snapshot_id_from": from_id, "snapshot_id_to": to_id, "source_code": "pytest_preview",
    })
    assert first.status_code == 200, first.text
    first_data = first.json()["data"]
    assert first_data["total_changes"] == 4
    assert first_data["skipped_existing"] == 0
    # column_removed (high) links a quality finding; data_type change is high too now.
    assert first_data["linked_to_quality_findings"] == 2

    second = client.post("/api/v1/metadata-changes/diff", params={
        "snapshot_id_from": from_id, "snapshot_id_to": to_id, "source_code": "pytest_preview",
    })
    second_data = second.json()["data"]
    assert second_data["total_changes"] == 0
    assert second_data["skipped_existing"] == 4
    assert second_data["linked_to_quality_findings"] == 0

    db = SessionLocal()
    try:
        events = db.query(AssetMetadataChangeEvent).filter(
            AssetMetadataChangeEvent.snapshot_id_from == from_id,
            AssetMetadataChangeEvent.snapshot_id_to == to_id,
        ).all()
        assert len(events) == 4
        findings = db.query(QualityFinding).filter(
            QualityFinding.rule_code == "SOURCE_METADATA_STALE",
            QualityFinding.target_ref.ilike("%.PATIENT.%"),
        ).all()
        assert len(findings) == 2
        audit = db.query(GovernAuditLog).filter(
            GovernAuditLog.module == "metadata_change",
            GovernAuditLog.entity_ref == f"{from_id}->{to_id}",
        ).all()
        assert {row.action for row in audit} == {"generate_change_events"}
        assert all(row.operator == "test-platform-admin" for row in audit)
    finally:
        db.close()


def test_list_changes_keyword_and_value_fields(client: TestClient):
    db = SessionLocal()
    try:
        from_id, to_id = _preview_pair(db)
    finally:
        db.close()
    client.post("/api/v1/metadata-changes/diff", params={
        "snapshot_id_from": from_id, "snapshot_id_to": to_id, "source_code": "pytest_preview",
    })

    by_keyword = client.get("/api/v1/metadata-changes?keyword=AGE")
    body = by_keyword.json()["data"]
    assert body["total"] == 1
    row = body["items"][0]
    assert row["column_name"] == "AGE"
    assert row["namespace"] == "PUBLIC"
    assert row["before_value"] is None
    assert "NUMBER" in row["after_value"]

    by_table = client.get("/api/v1/metadata-changes?keyword=PATIENT")
    assert by_table.json()["data"]["total"] == 4


def test_source_snapshots(client: TestClient):
    resp = client.get("/api/v1/sources/ods_8_216/snapshots")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert isinstance(data, list)


def test_source_snapshots_and_diff_are_isolated_by_source_code(client: TestClient):
    db = SessionLocal()
    try:
        source_a_old = _create_column_snapshot(db, "pytest_snapshot_a", "a-old", ["ID"])
        source_a_new = _create_column_snapshot(db, "pytest_snapshot_a", "a-new", ["ID", "NAME"])
        source_b = _create_column_snapshot(db, "pytest_snapshot_b", "b-only", ["ID", "OTHER"])
        db.commit()
        source_a_old_id = source_a_old.id
        source_a_new_id = source_a_new.id
        source_b_id = source_b.id
    finally:
        db.close()

    snapshots = client.get("/api/v1/sources/pytest_snapshot_a/snapshots")
    assert snapshots.status_code == 200
    items = snapshots.json()["data"]
    assert {item["id"] for item in items} == {source_a_old_id, source_a_new_id}
    assert {item["source_code"] for item in items} == {"pytest_snapshot_a"}

    same_source = client.post("/api/v1/metadata-changes/diff", params={
        "snapshot_id_from": source_a_old_id,
        "snapshot_id_to": source_a_new_id,
        "source_code": "pytest_snapshot_a",
    })
    assert same_source.status_code == 200
    assert same_source.json()["data"]["total_changes"] == 1
    assert same_source.json()["data"]["snapshot_from"]["source_code"] == "pytest_snapshot_a"

    cross_source = client.post("/api/v1/metadata-changes/diff", params={
        "snapshot_id_from": source_a_old_id,
        "snapshot_id_to": source_b_id,
    })
    assert cross_source.status_code == 400

    mismatched_filter = client.post("/api/v1/metadata-changes/diff", params={
        "snapshot_id_from": source_a_old_id,
        "snapshot_id_to": source_a_new_id,
        "source_code": "pytest_snapshot_b",
    })
    assert mismatched_filter.status_code == 400

def test_collect_metadata_returns_job_and_retry(client: TestClient):
    db = SessionLocal()
    try:
        db.execute(delete(SchedulerJob).where(SchedulerJob.source_code == "pytest_metadata_source"))
        db.execute(delete(AssetDataSource).where(AssetDataSource.source_code == "pytest_metadata_source"))
        db.add(AssetDataSource(
            system_code="PYTEST",
            source_code="pytest_metadata_source",
            source_name_cn="pytest metadata source",
            db_type="postgresql",
            host_masked="localhost",
            port=5432,
            database_name="pytest",
            connection_mode="direct",
            environment="test",
            enabled=True,
        ))
        db.commit()
    finally:
        db.close()

    resp = client.post("/api/v1/sources/pytest_metadata_source/collect-metadata", json={"label": "pytest metadata collect"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "snapshot_id" in data
    assert "job_id" in data

    retry = client.post(f"/api/v1/sources/pytest_metadata_source/metadata-jobs/{data['job_id']}/retry")
    assert retry.status_code == 200
    retry_data = retry.json()["data"]
    assert retry_data["job_id"] == data["job_id"]
    assert retry_data["job_status"] == "success"
    assert "snapshot_id" in retry_data


def test_metadata_collect_retry_404(client: TestClient):
    resp = client.post("/api/v1/sources/pytest_metadata_source/metadata-jobs/999999999/retry")
    assert resp.status_code == 404



def test_collect_metadata_live_source_uses_collector(client: TestClient, monkeypatch):
    from app.api.v1 import metadata_changes

    class FakeConnector:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.closed = False

        def close(self):
            self.closed = True

    class FakeCollector:
        received_schema_filter = None

        def __init__(self, connector):
            self.connector = connector

        def collect_all(self, schema_filter=None):
            FakeCollector.received_schema_filter = schema_filter
            return {
                "schemas": [{"name": "HIS", "type": "owner"}],
                "tables": [{"schema_name": "HIS", "table_name": "PAT_VISIT", "row_count": 10, "comment": ""}],
                "columns": [
                    {
                        "schema_name": "HIS",
                        "table_name": "PAT_VISIT",
                        "column_name": "PATIENT_ID",
                        "data_type": "VARCHAR2",
                        "length": 20,
                        "nullable": "N",
                        "comment": "patient id",
                        "is_primary_key": False,
                    },
                    {
                        "schema_name": "HIS",
                        "table_name": "PAT_VISIT",
                        "column_name": "VISIT_ID",
                        "data_type": "NUMBER",
                        "length": 10,
                        "nullable": "N",
                        "comment": "visit id",
                        "is_primary_key": False,
                    },
                ],
            }

    monkeypatch.setitem(metadata_changes.DB_CONNECTOR_MAP, "pytest_live", FakeConnector)
    monkeypatch.setitem(metadata_changes.METADATA_COLLECTOR_MAP, "pytest_live", FakeCollector)

    db = SessionLocal()
    try:
        db.execute(delete(SchedulerJob).where(SchedulerJob.source_code == "pytest_live_source"))
        db.execute(delete(AssetDataSource).where(AssetDataSource.source_code == "pytest_live_source"))
        db.add(AssetDataSource(
            system_code="PYTEST",
            source_code="pytest_live_source",
            source_name_cn="pytest live source",
            db_type="pytest_live",
            host_masked="localhost",
            port=1,
            database_name="pytest",
            connection_mode="direct",
            environment="test",
            enabled=True,
        ))
        db.commit()
    finally:
        db.close()

    resp = client.post(
        "/api/v1/sources/pytest_live_source/collect-metadata",
        json={"label": "pytest live metadata", "mode": "live_source", "schema_filter": ["HIS"]},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["mode"] == "live_source"
    assert data["table_count"] == 1
    assert data["column_count"] == 2
    assert FakeCollector.received_schema_filter == ["HIS"]

    db = SessionLocal()
    try:
        rows = db.query(AssetMetadataColumnSnapshot).filter(
            AssetMetadataColumnSnapshot.snapshot_id == data["snapshot_id"]
        ).all()
        assert [r.column_name for r in rows] == ["PATIENT_ID", "VISIT_ID"]
        assert {r.namespace_name for r in rows} == {"HIS"}
    finally:
        db.close()
