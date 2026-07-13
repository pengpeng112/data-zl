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
