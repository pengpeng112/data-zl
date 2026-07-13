from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.db import SessionLocal
from app.models.asset_system import AssetDataSource
from app.models.dict_medical import DictMedicalCodeItem, DictMedicalSyncDiff
from app.models.governance_ops import SchedulerJob


def _ensure_code_set(client: TestClient, code_set_code="test_cs"):
    resp = client.put("/api/v1/dict-medical/code-sets", json={
        "category_code": "diagnosis",
        "code_set_code": code_set_code,
        "code_set_type": "clinical",
        "code_set_name_cn": "测试编码体系",
        "enabled": True,
    })
    assert resp.status_code == 200
    return resp.json()["data"]


def test_list_code_sets(client: TestClient):
    resp = client.get("/api/v1/dict-medical/code-sets")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert isinstance(data, list)


def test_list_code_sets_category_filter(client: TestClient):
    _ensure_code_set(client, "test_cs_diag")
    resp = client.get("/api/v1/dict-medical/code-sets?category_code=diagnosis")
    assert resp.status_code == 200
    data = resp.json()["data"]
    for cs in data:
        assert cs["category_code"] == "diagnosis"


def test_upsert_code_set(client: TestClient):
    resp = client.put("/api/v1/dict-medical/code-sets", json={
        "category_code": "diagnosis",
        "code_set_code": "test_cs_upsert",
        "code_set_type": "clinical",
        "code_set_name_cn": "测试编码体系",
    })
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["code_set_code"] == "test_cs_upsert"
    assert "id" in data

    resp = client.put("/api/v1/dict-medical/code-sets", json={
        "category_code": "diagnosis",
        "code_set_code": "test_cs_upsert",
        "code_set_type": "clinical",
        "code_set_name_cn": "测试编码体系(已更新)",
    })
    assert resp.status_code == 200


def test_list_items(client: TestClient):
    _ensure_code_set(client, "test_cs_items")
    resp = client.get("/api/v1/dict-medical/code-sets/test_cs_items/items")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "items" in data
    assert "total" in data


def test_list_items_keyword(client: TestClient):
    _ensure_code_set(client, "test_cs_kw")
    client.put("/api/v1/dict-medical/items", json={
        "code_set_code": "test_cs_kw",
        "item_code": "KW001",
        "item_name_cn": "关键字测试项",
        "category_code": "diagnosis",
    })
    resp = client.get("/api/v1/dict-medical/code-sets/test_cs_kw/items?keyword=关键字")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total"] >= 1


def test_upsert_item(client: TestClient):
    _ensure_code_set(client, "test_cs_item")
    resp = client.put("/api/v1/dict-medical/items", json={
        "code_set_code": "test_cs_item",
        "item_code": "I001",
        "item_name_cn": "测试编码项",
        "category_code": "diagnosis",
    })
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["item_code"] == "I001"
    assert "id" in data

    resp = client.put("/api/v1/dict-medical/items", json={
        "code_set_code": "test_cs_item",
        "item_code": "I001",
        "item_name_cn": "测试编码项(已更新)",
        "category_code": "diagnosis",
    })
    assert resp.status_code == 200


def test_list_mappings(client: TestClient):
    resp = client.get("/api/v1/dict-medical/mappings")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "items" in data
    assert "total" in data


def test_list_mappings_review_status_filter(client: TestClient):
    resp = client.get("/api/v1/dict-medical/mappings?review_status=draft")
    assert resp.status_code == 200
    data = resp.json()["data"]
    for m in data["items"]:
        assert m["review_status"] == "draft"


def test_upsert_mapping(client: TestClient):
    resp = client.put("/api/v1/dict-medical/mappings", json={
        "category_code": "diagnosis",
        "from_code_set": "clinical_diag",
        "from_item_code": "A01",
        "to_code_set": "national_diag",
        "to_item_code": "B01",
        "mapping_type": "manual",
        "confidence": "high",
    })
    assert resp.status_code == 200
    assert "id" in resp.json()["data"]


def test_list_sync_diffs(client: TestClient):
    resp = client.get("/api/v1/dict-medical/sync-diffs")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "items" in data
    assert "total" in data


def test_list_sync_diffs_status_filter(client: TestClient):
    resp = client.get("/api/v1/dict-medical/sync-diffs?status=open")
    assert resp.status_code == 200
    data = resp.json()["data"]
    for d in data["items"]:
        assert d["status"] == "open"


def test_list_versions(client: TestClient):
    resp = client.get("/api/v1/dict-medical/versions")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert isinstance(data, list)


def test_create_change_request(client: TestClient):
    resp = client.post("/api/v1/dict-medical/change-requests", json={
        "entity_type": "code_item",
        "request_type": "add",
        "requested_by": "test_user",
    })
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["approval_status"] == "draft"
    assert "id" in data

def test_update_medical_sync_diff_status(client: TestClient):
    db = SessionLocal()
    try:
        db.execute(delete(DictMedicalSyncDiff).where(DictMedicalSyncDiff.target_system == "pytest_medical_diff"))
        diff = DictMedicalSyncDiff(
            category_code="diagnosis",
            target_system="pytest_medical_diff",
            target_source_code="pytest_source",
            diff_type="missing_target",
            code_set_code="pytest_code_set",
            item_code="pytest_item",
            after_data={"item_code": "pytest_item"},
            status="open",
        )
        db.add(diff)
        db.commit()
        db.refresh(diff)
        diff_id = diff.id
    finally:
        db.close()

    ignored = client.patch(f"/api/v1/dict-medical/sync-diffs/{diff_id}", json={
        "status": "ignored",
        "handled_by": "pytest",
        "note": "not needed",
    })
    assert ignored.status_code == 200
    assert ignored.json()["data"]["status"] == "ignored"
    assert ignored.json()["data"]["handled_at"] is not None

    reopened = client.patch(f"/api/v1/dict-medical/sync-diffs/{diff_id}", json={"status": "open"})
    assert reopened.status_code == 200
    assert reopened.json()["data"]["status"] == "open"
    assert reopened.json()["data"]["handled_at"] is None

    db = SessionLocal()
    try:
        db.execute(delete(DictMedicalSyncDiff).where(DictMedicalSyncDiff.target_system == "pytest_medical_diff"))
        db.commit()
    finally:
        db.close()

def test_run_medical_sync_endpoint(monkeypatch, client: TestClient):
    from app.services import medical_code_source_collector

    class FakeConnector:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def execute_readonly(self, sql, params=None, max_rows=1000):
            assert params == {"max_rows": 50}
            assert max_rows == 50
            if "CDA.CDA_DICTIONARY" in sql:
                return [
                    {"LOCAL_CODE": "D_EXIST", "LOCAL_NAME": "Source Diagnosis Name", "STANDARD_CODE": "S001", "STANDARD_NAME": "Std Diagnosis"},
                    {"LOCAL_CODE": "D_NEW", "LOCAL_NAME": "New Diagnosis", "STANDARD_CODE": "S002", "STANDARD_NAME": "Std New"},
                ]
            if "SM.MED_OPERATION_NAME" in sql:
                return [
                    {"LOCAL_CODE": "O_NEW", "LOCAL_NAME": "New Operation", "OPERATION_LEVEL": "4"},
                ]
            return []

        def close(self):
            pass

    monkeypatch.setitem(medical_code_source_collector.DB_CONNECTOR_MAP, "pytest_medical", FakeConnector)

    db = SessionLocal()
    try:
        db.execute(delete(DictMedicalSyncDiff).where(DictMedicalSyncDiff.target_source_code == "pytest_medical_source"))
        db.execute(delete(DictMedicalCodeItem).where(DictMedicalCodeItem.code_set_code.in_(["diagnosis_local_clinical", "operation_local_clinical"]), DictMedicalCodeItem.item_code.in_(["D_EXIST", "D_NEW", "O_NEW"])))
        db.execute(delete(SchedulerJob).where(SchedulerJob.source_code == "pytest_medical_source"))
        db.execute(delete(AssetDataSource).where(AssetDataSource.source_code == "pytest_medical_source"))
        db.add(AssetDataSource(
            system_code="PYTEST",
            source_code="pytest_medical_source",
            source_name_cn="pytest medical source",
            db_type="pytest_medical",
            host_masked="localhost",
            port=1,
            database_name="pytest",
            connection_mode="direct",
            environment="test",
            enabled=True,
        ))
        db.add(DictMedicalCodeItem(
            code_set_code="diagnosis_local_clinical",
            item_code="D_EXIST",
            item_name_cn="Local Diagnosis Name",
            category_code="diagnosis",
            status="active",
        ))
        db.commit()
    finally:
        db.close()

    resp = client.post("/api/v1/dict-medical/sync/run", json={
        "source_system": "pytest_medical_source",
        "target_system": "asset",
        "operator": "pytest",
        "max_rows": 50,
    })
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "success"
    assert data["job_status"] == "success"
    assert data["scanned"] == 3
    assert data["diffs_created"] == 3
    assert data["by_category"]["diagnosis"]["diffs_created"] == 2
    assert data["by_category"]["operation"]["diffs_created"] == 1

    retry = client.post(f"/api/v1/dict-medical/sync/jobs/{data['job_id']}/retry", params={"operator": "pytest"})
    assert retry.status_code == 200
    retry_data = retry.json()["data"]
    assert retry_data["job_id"] == data["job_id"]
    assert retry_data["job_status"] == "success"
    assert retry_data["diffs_created"] == 0
    assert retry_data["diffs_skipped_existing"] == 3

    db = SessionLocal()
    try:
        diffs = db.query(DictMedicalSyncDiff).filter(
            DictMedicalSyncDiff.target_source_code == "pytest_medical_source"
        ).order_by(DictMedicalSyncDiff.category_code, DictMedicalSyncDiff.item_code, DictMedicalSyncDiff.diff_type).all()
        assert [(d.category_code, d.item_code, d.diff_type) for d in diffs] == [
            ("diagnosis", "D_EXIST", "name_mismatch"),
            ("diagnosis", "D_NEW", "missing_target"),
            ("operation", "O_NEW", "missing_target"),
        ]
    finally:
        db.execute(delete(DictMedicalSyncDiff).where(DictMedicalSyncDiff.target_source_code == "pytest_medical_source"))
        db.execute(delete(DictMedicalCodeItem).where(DictMedicalCodeItem.code_set_code.in_(["diagnosis_local_clinical", "operation_local_clinical"]), DictMedicalCodeItem.item_code.in_(["D_EXIST", "D_NEW", "O_NEW"])))
        db.execute(delete(SchedulerJob).where(SchedulerJob.source_code == "pytest_medical_source"))
        db.execute(delete(AssetDataSource).where(AssetDataSource.source_code == "pytest_medical_source"))
        db.commit()
        db.close()


def test_run_medical_sync_retry_404(client: TestClient):
    resp = client.post("/api/v1/dict-medical/sync/jobs/999999999/retry")
    assert resp.status_code == 404
