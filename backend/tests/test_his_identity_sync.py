from sqlalchemy import delete, select

from app.core.db import SessionLocal
from app.models.governance_base import GovernAuditLog
from app.models.identity import (
    IdentityDepartment,
    IdentityPerson,
    IdentityPersonDepartment,
    IdentityPersonSource,
)
from app.services import his_identity_sync


class FakeOracleConnector:
    calls = []
    last_kwargs = {}

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        FakeOracleConnector.last_kwargs = kwargs
        self.closed = False

    def execute_readonly(self, sql, params=None, max_rows=1000):
        FakeOracleConnector.calls.append((sql, params, max_rows))
        assert sql.strip().upper().startswith("SELECT")
        assert params == {"max_rows": 100}
        assert max_rows == 100
        if "COMM.DEPT_DICT" in sql:
            return [
                {"DEPT_CODE": "D001", "DEPT_NAME": "Old Dept", "OUTP_OR_INP": "1", "STOP_FLAG": "0"},
                {"DEPT_CODE": "D002", "DEPT_NAME": "Second Dept", "OUTP_OR_INP": "2", "STOP_FLAG": "0"},
            ]
        if "COMM.STAFF_DICT" in sql:
            return [
                {"EMP_NO": "E001", "NAME": "Old Name", "DEPT_CODE": "D001", "JOB": "doctor", "TITLE": "old title", "STATUS": "0", "ID_NO": "370100199001011234"},
                {"EMP_NO": "E002", "NAME": "Staff Only", "DEPT_CODE": "D002", "JOB": "nurse", "TITLE": "nurse", "STATUS": "0", "ID_NO": "370100199002021234"},
            ]
        if "SYS_EMPLOYEE" in sql:
            return [
                {
                    "EMPLCODE": "E001",
                    "EMPLNAME": "New Name",
                    "DEPTCODE": "D002",
                    "DEPTID": None,
                    "VALIDSTATE": "1",
                    "IDENNO": "370100199003031234",
                    "USERCODE": None,
                    "ISDELETED": 0,
                },
            ]
        if "COMM.DOCTOR_GROUP" in sql:
            return [
                {"DOCTOR_USER": "E001", "DEPT_CODE": "D003", "DOCTOR": "New Name"},
                {"DOCTOR_USER": "NameOnly", "DEPT_CODE": "D004", "DOCTOR": "Name Only"},
            ]
        if "COMM.STAFF_VS_GROUP" in sql:
            return [
                {"GROUP_CLASS": "A", "GROUP_CODE": "G001", "EMP_NO": "E001", "DEPT_CODE": "D005"},
            ]
        return []

    def close(self):
        self.closed = True


def _cleanup(db):
    db.execute(delete(GovernAuditLog).where(GovernAuditLog.module == "sync", GovernAuditLog.entity_ref == "his_source_10_10_10_15"))
    db.execute(delete(IdentityPersonDepartment).where(IdentityPersonDepartment.person_code.in_(["E001", "E002", "NameOnly"])))
    db.execute(delete(IdentityPersonSource).where(IdentityPersonSource.source_system == "HIS"))
    db.execute(delete(IdentityPerson).where(IdentityPerson.person_code.in_(["E001", "E002"])))
    db.execute(delete(IdentityDepartment).where(IdentityDepartment.dept_code.in_(["D001", "D002"])))
    db.commit()


def test_his_identity_sync_dry_run_does_not_write(monkeypatch):
    monkeypatch.setattr(his_identity_sync, "OracleConnector", FakeOracleConnector)
    monkeypatch.setattr(his_identity_sync.settings, "his_source_password", "secret-for-test")
    monkeypatch.setattr(his_identity_sync.settings, "his_source_connection_mode", "ssh_jump")
    monkeypatch.setattr(his_identity_sync.settings, "his_source_jump_host", "10.10.8.83")
    FakeOracleConnector.calls = []
    FakeOracleConnector.last_kwargs = {}

    db = SessionLocal()
    try:
        _cleanup(db)
        result = his_identity_sync.sync_his_identity(db, operator="pytest", dry_run=True, max_rows=100)
        assert result["dry_run"] is True
        assert result["prepared"]["persons"] == 2
        assert result["bridge"]["bridge_hits"] == 1
        assert result["doctor_group_diagnostics"]["unmatched_doctor_user"] == 1
        assert db.scalar(select(IdentityPerson).where(IdentityPerson.person_code == "E001")) is None
        assert db.scalar(select(GovernAuditLog).where(GovernAuditLog.module == "sync", GovernAuditLog.entity_ref == "his_source_10_10_10_15")) is None
        assert len(FakeOracleConnector.calls) == 5
        assert FakeOracleConnector.last_kwargs["connection_mode"] == "ssh_jump"
        assert FakeOracleConnector.last_kwargs["jump_host"] == "10.10.8.83"
    finally:
        _cleanup(db)
        db.close()


def test_his_identity_sync_upserts_bridge_sources_departments_and_audit(monkeypatch):
    monkeypatch.setattr(his_identity_sync, "OracleConnector", FakeOracleConnector)
    monkeypatch.setattr(his_identity_sync.settings, "his_source_password", "secret-for-test")
    FakeOracleConnector.calls = []

    db = SessionLocal()
    try:
        _cleanup(db)
        result = his_identity_sync.sync_his_identity(db, operator="pytest", dry_run=False, max_rows=100)
        assert result["status"] == "success"
        assert result["bridge"]["bridge_hits"] == 1
        assert result["doctor_group_diagnostics"]["matched_by_doctor_user"] == 1

        person = db.scalar(select(IdentityPerson).where(IdentityPerson.person_code == "E001"))
        assert person is not None
        assert person.person_name_cn == "New Name"
        assert person.dept_code == "D002"
        assert person.primary_source_system == "HIS"

        staff_only = db.scalar(select(IdentityPerson).where(IdentityPerson.person_code == "E002"))
        assert staff_only is not None
        assert staff_only.person_name_cn == "Staff Only"

        sources = db.scalars(select(IdentityPersonSource).where(IdentityPersonSource.person_code == "E001")).all()
        assert {s.source_table for s in sources} == {"COMM.STAFF_DICT", "FXHIS.SYS_EMPLOYEE"}
        raw_values = [s.raw_data for s in sources]
        assert all("370100199001011234" not in str(raw) for raw in raw_values)
        assert all("370100199003031234" not in str(raw) for raw in raw_values)
        assert any("ID_NO_sha256" in raw for raw in raw_values)
        assert any("IDENNO_sha256" in raw for raw in raw_values)

        links = db.scalars(select(IdentityPersonDepartment).where(IdentityPersonDepartment.person_code == "E001")).all()
        assert {l.dept_code for l in links} == {"D001", "D002", "D003", "D005"}
        assert any(l.dept_code == "D002" and l.is_primary for l in links)

        audit = db.scalar(select(GovernAuditLog).where(
            GovernAuditLog.module == "sync",
            GovernAuditLog.action == "sync_run",
            GovernAuditLog.entity_type == "identity_his",
            GovernAuditLog.entity_ref == "his_source_10_10_10_15",
        ))
        assert audit is not None
        assert audit.after_data["bridge"]["bridge_hits"] == 1
    finally:
        _cleanup(db)
        db.close()


def test_his_identity_sync_api_dry_run(monkeypatch, client):
    monkeypatch.setattr(his_identity_sync, "OracleConnector", FakeOracleConnector)
    monkeypatch.setattr(his_identity_sync.settings, "his_source_password", "secret-for-test")

    db = SessionLocal()
    try:
        _cleanup(db)
    finally:
        db.close()

    resp = client.post("/api/v1/identity/sync/his?dry_run=true&max_rows=100&operator=pytest")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["dry_run"] is True
    assert data["prepared"]["persons"] == 2

    db = SessionLocal()
    try:
        assert db.scalar(select(IdentityPerson).where(IdentityPerson.person_code == "E001")) is None
    finally:
        _cleanup(db)
        db.close()
