from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.db import SessionLocal
from app.models.asset_system import AssetDataSource
from app.models.governance_ops import SchedulerJob
from app.models.identity import IdentityDepartmentSource, IdentityPersonDepartment, IdentityPersonSource, IdentitySyncDiff


def test_list_departments(client: TestClient):
    resp = client.get("/api/v1/identity/departments")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert isinstance(data, list)


def test_department_profile_404(client: TestClient):
    resp = client.get("/api/v1/identity/departments/nonexistent_dept")
    assert resp.status_code == 404


def test_list_persons(client: TestClient):
    resp = client.get("/api/v1/identity/persons")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "page_size" in data


def test_list_persons_pagination(client: TestClient):
    resp = client.get("/api/v1/identity/persons?page=1&page_size=5")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["page"] == 1
    assert data["page_size"] == 5
    assert len(data["items"]) <= 5


def test_list_persons_type_filter(client: TestClient):
    resp = client.get("/api/v1/identity/persons?person_type=formal")
    assert resp.status_code == 200
    data = resp.json()["data"]
    for p in data["items"]:
        assert p["person_type"] == "formal"


def test_list_persons_keyword(client: TestClient):
    resp = client.get("/api/v1/identity/persons?keyword=test")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "items" in data
    assert "total" in data


def test_person_profile_404(client: TestClient):
    resp = client.get("/api/v1/identity/persons/nonexistent_person")
    assert resp.status_code == 404


def test_list_accounts(client: TestClient):
    resp = client.get("/api/v1/identity/accounts")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert isinstance(data, list)


def test_list_accounts_system_filter(client: TestClient):
    resp = client.get("/api/v1/identity/accounts?system_code=HIS")
    assert resp.status_code == 200
    data = resp.json()["data"]
    for a in data:
        assert a["system_code"] == "HIS"


def test_list_sync_diffs(client: TestClient):
    resp = client.get("/api/v1/identity/sync-diffs")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "items" in data
    assert "total" in data


def test_list_sync_diffs_status_filter(client: TestClient):
    resp = client.get("/api/v1/identity/sync-diffs?status=open")
    assert resp.status_code == 200
    data = resp.json()["data"]
    for d in data["items"]:
        assert d["status"] == "open"


def test_list_inconsistencies(client: TestClient):
    resp = client.get("/api/v1/identity/inconsistencies")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "items" in data
    assert "total" in data


def test_collect_sources(client: TestClient):
    resp = client.post("/api/v1/identity/collect-sources")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "scheduled"


def test_bind_account_404(client: TestClient):
    resp = client.put("/api/v1/identity/accounts/bind", json={
        "person_code": "P001",
        "system_code": "NONEXISTENT",
        "account_id": "NOT_FOUND",
    })
    assert resp.status_code == 404

def test_run_identity_sync_endpoint(monkeypatch, client: TestClient):
    def fake_run_sync(source_system, target_system, entity_type, operator=None):
        return {
            "source_system": source_system,
            "target_system": target_system,
            "entity_type": entity_type,
            "operator": operator,
            "status": "success",
            "scanned": 2,
            "diffs_created": 1,
        }

    monkeypatch.setattr("app.services.sync_executor.run_sync", fake_run_sync)
    resp = client.post("/api/v1/identity/sync/run", json={
        "source_system": "HIS",
        "target_system": "asset",
        "entity_type": "identity_person",
        "operator": "pytest",
    })
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "success"
    assert data["diffs_created"] == 1
    assert data["job_id"] is not None
    assert data["job_status"] == "success"

    retry = client.post(f"/api/v1/identity/sync/jobs/{data['job_id']}/retry", params={"operator": "pytest"})
    assert retry.status_code == 200
    retry_data = retry.json()["data"]
    assert retry_data["job_id"] == data["job_id"]
    assert retry_data["job_status"] == "success"


def test_run_identity_sync_endpoint_rejects_non_identity(client: TestClient):
    resp = client.post("/api/v1/identity/sync/run", json={
        "source_system": "HIS",
        "target_system": "asset",
        "entity_type": "medical_code",
    })
    assert resp.status_code == 400

def test_update_identity_sync_diff_status(client: TestClient):
    db = SessionLocal()
    try:
        db.execute(delete(IdentitySyncDiff).where(IdentitySyncDiff.source_system == "pytest_diff_api"))
        diff = IdentitySyncDiff(
            diff_type="source_unmatched",
            source_system="pytest_diff_api",
            target_system="asset",
            entity_type="identity_person",
            entity_code="pytest_diff_001",
            after_data={"source_person_id": "pytest_diff_001"},
            status="open",
        )
        db.add(diff)
        db.commit()
        db.refresh(diff)
        diff_id = diff.id
    finally:
        db.close()

    resolved = client.patch(f"/api/v1/identity/sync-diffs/{diff_id}", json={
        "status": "resolved",
        "handled_by": "pytest",
        "note": "verified",
    })
    assert resolved.status_code == 200
    assert resolved.json()["data"]["status"] == "resolved"
    assert resolved.json()["data"]["handled_at"] is not None

    reopened = client.patch(f"/api/v1/identity/sync-diffs/{diff_id}", json={"status": "open"})
    assert reopened.status_code == 200
    assert reopened.json()["data"]["status"] == "open"
    assert reopened.json()["data"]["handled_at"] is None

    db = SessionLocal()
    try:
        db.execute(delete(IdentitySyncDiff).where(IdentitySyncDiff.source_system == "pytest_diff_api"))
        db.commit()
    finally:
        db.close()


def test_collect_department_sources_live_source(client: TestClient, monkeypatch):
    from app.services import identity_source_collector

    class FakeConnector:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.closed = False

        def execute_readonly(self, sql, params=None, max_rows=1000):
            assert "COMM.DEPT_DICT" in sql
            assert params == {"max_rows": 50}
            assert max_rows == 50
            return [
                {"DEPT_CODE": "D001", "DEPT_NAME": "Source Dept A", "OUTP_OR_INP": "1", "STOP_FLAG": "0"},
                {"DEPT_CODE": "D002", "DEPT_NAME": "Source Dept B", "OUTP_OR_INP": "2", "STOP_FLAG": "1"},
            ]

        def close(self):
            self.closed = True

    monkeypatch.setitem(identity_source_collector.DB_CONNECTOR_MAP, "pytest_identity", FakeConnector)

    db = SessionLocal()
    try:
        db.execute(delete(IdentityDepartmentSource).where(IdentityDepartmentSource.source_code == "pytest_identity_source"))
        db.execute(delete(SchedulerJob).where(SchedulerJob.source_code == "pytest_identity_source"))
        db.execute(delete(AssetDataSource).where(AssetDataSource.source_code == "pytest_identity_source"))
        db.add(AssetDataSource(
            system_code="PYTEST",
            source_code="pytest_identity_source",
            source_name_cn="pytest identity source",
            db_type="pytest_identity",
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

    resp = client.post("/api/v1/identity/collect-sources", json={
        "source_code": "pytest_identity_source",
        "source_system": "pytest_his",
        "entity_type": "identity_department",
        "max_rows": 50,
    })
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "success"
    assert data["mode"] == "live_source"
    assert data["scanned"] == 2
    assert data["inserted"] == 2
    assert data["job_id"] is not None

    db = SessionLocal()
    try:
        rows = db.query(IdentityDepartmentSource).filter(
            IdentityDepartmentSource.source_code == "pytest_identity_source"
        ).order_by(IdentityDepartmentSource.source_dept_id).all()
        assert [r.source_dept_id for r in rows] == ["D001", "D002"]
        assert rows[0].source_dept_name == "Source Dept A"
        assert rows[0].source_status == "active"
        assert rows[1].source_status == "inactive"
    finally:
        db.execute(delete(IdentityDepartmentSource).where(IdentityDepartmentSource.source_code == "pytest_identity_source"))
        db.execute(delete(SchedulerJob).where(SchedulerJob.source_code == "pytest_identity_source"))
        db.execute(delete(AssetDataSource).where(AssetDataSource.source_code == "pytest_identity_source"))
        db.commit()
        db.close()



def test_collect_person_sources_live_source(client: TestClient, monkeypatch):
    from app.services import identity_source_collector

    class FakeConnector:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def execute_readonly(self, sql, params=None, max_rows=1000):
            if "STAFF_DICT" in sql and "STAFF_VS_GROUP" not in sql and "STAFF_GROUP_DICT" not in sql:
                return [
                    {"EMP_NO": "E001", "NAME": "Staff One", "DEPT_CODE": "D001", "JOB": "doctor", "TITLE": "chief", "STATUS": "0", "ID_NO": "secret-id"},
                ]
            if "SYS_EMPLOYEE" in sql:
                return [
                    {
                        "EMPLCODE": "EMP001",
                        "EMPLNAME": "Employee One",
                        "DEPTCODE": "D002",
                        "DEPTID": None,
                        "VALIDSTATE": "0",
                        "IDENNO": "secret-id2",
                        "USERID": "E001",
                        "ISDELETED": 0,
                    },
                ]
            if "DOCTOR_GROUP" in sql:
                return [
                    {"DOCTOR_USER": "E001", "DEPT_CODE": "D003", "DOCTOR": "Staff One"},
                ]
            if "STAFF_VS_GROUP" in sql:
                return [
                    {"GROUP_CLASS": "G", "GROUP_CODE": "G001", "EMP_NO": "E001", "DEPT_CODE": "D004"},
                ]
            return []

        def close(self):
            pass

    monkeypatch.setitem(identity_source_collector.DB_CONNECTOR_MAP, "pytest_identity_person", FakeConnector)

    db = SessionLocal()
    try:
        db.execute(delete(IdentityPersonDepartment).where(IdentityPersonDepartment.person_code == "E001"))
        db.execute(delete(IdentityPersonSource).where(IdentityPersonSource.source_code == "pytest_identity_person_source"))
        db.execute(delete(SchedulerJob).where(SchedulerJob.source_code == "pytest_identity_person_source"))
        db.execute(delete(AssetDataSource).where(AssetDataSource.source_code == "pytest_identity_person_source"))
        db.add(AssetDataSource(
            system_code="PYTEST",
            source_code="pytest_identity_person_source",
            source_name_cn="pytest identity person source",
            db_type="pytest_identity_person",
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

    resp = client.post("/api/v1/identity/collect-sources", json={
        "source_code": "pytest_identity_person_source",
        "source_system": "pytest_his_person",
        "entity_type": "identity_person",
        "max_rows": 50,
    })
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "success"
    assert data["entity_type"] == "identity_person"
    assert data["scanned"] == 4
    assert data["person_sources_inserted"] == 2
    assert data["department_links_created"] == 4

    db = SessionLocal()
    try:
        sources = db.query(IdentityPersonSource).filter(
            IdentityPersonSource.source_code == "pytest_identity_person_source"
        ).order_by(IdentityPersonSource.source_table).all()
        assert len(sources) == 2
        assert all("ID_NO" not in (s.raw_data or {}) and "IDENNO" not in (s.raw_data or {}) for s in sources)
        links = db.query(IdentityPersonDepartment).filter(
            IdentityPersonDepartment.person_code == "E001"
        ).order_by(IdentityPersonDepartment.dept_code).all()
        assert [l.dept_code for l in links] == ["D001", "D002", "D003", "D004"]
        assert sum(1 for l in links if l.is_primary) == 2
    finally:
        db.execute(delete(IdentityPersonDepartment).where(IdentityPersonDepartment.person_code == "E001"))
        db.execute(delete(IdentityPersonSource).where(IdentityPersonSource.source_code == "pytest_identity_person_source"))
        db.execute(delete(SchedulerJob).where(SchedulerJob.source_code == "pytest_identity_person_source"))
        db.execute(delete(AssetDataSource).where(AssetDataSource.source_code == "pytest_identity_person_source"))
        db.commit()
        db.close()
