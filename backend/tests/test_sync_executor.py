from sqlalchemy import delete

from app.core.db import SessionLocal
from app.models.identity import IdentityDepartment, IdentityDepartmentSource, IdentityPerson, IdentityPersonSource, IdentitySyncDiff
from app.services.sync_executor import run_sync


def _cleanup_sync_test_data():
    db = SessionLocal()
    try:
        db.execute(delete(IdentitySyncDiff).where(IdentitySyncDiff.source_system == "pytest_sync_his"))
        db.execute(delete(IdentityDepartmentSource).where(IdentityDepartmentSource.source_system == "pytest_sync_his"))
        db.execute(delete(IdentityPersonSource).where(IdentityPersonSource.source_system == "pytest_sync_his"))
        db.execute(delete(IdentityDepartment).where(IdentityDepartment.dept_code.like("pytest_sync_%")))
        db.execute(delete(IdentityPerson).where(IdentityPerson.person_code.like("pytest_sync_%")))
        db.commit()
    finally:
        db.close()


def test_run_identity_person_sync_creates_diffs_without_duplicates():
    _cleanup_sync_test_data()
    db = SessionLocal()
    try:
        db.add(IdentityPerson(
            person_code="pytest_sync_p001",
            person_name_cn="Master Name",
            dept_code="D001",
            source_system="HIS",
        ))
        db.add(IdentityPersonSource(
            person_code=None,
            source_system="pytest_sync_his",
            source_code="his_ready",
            source_table="STAFF_DICT",
            source_person_id="SRC001",
            source_person_name="Unmatched Name",
            source_dept_code="D001",
            match_status="unmatched",
        ))
        db.add(IdentityPersonSource(
            person_code="pytest_sync_p001",
            source_system="pytest_sync_his",
            source_code="his_ready",
            source_table="STAFF_DICT",
            source_person_id="SRC002",
            source_person_name="Source Name",
            source_dept_code="D002",
            match_status="matched",
        ))
        db.commit()
    finally:
        db.close()

    first = run_sync("pytest_sync_his", "asset", "identity_person", operator="pytest")
    second = run_sync("pytest_sync_his", "asset", "identity_person", operator="pytest")

    assert first["status"] == "success"
    assert first["scanned"] == 2
    assert first["diffs_created"] == 2
    assert second["status"] == "success"
    assert second["diffs_created"] == 0
    assert second["diffs_skipped_existing"] == 2

    _cleanup_sync_test_data()


def test_run_identity_department_sync_empty_staging_success():
    _cleanup_sync_test_data()
    result = run_sync("pytest_sync_his", "asset", "identity_department", operator="pytest")
    assert result["status"] == "success"
    assert result["source_table"] == "asset_identity_department_sources"
    assert result["scanned"] == 0
    assert result["diffs_created"] == 0


def test_run_identity_department_sync_creates_diffs_without_duplicates():
    _cleanup_sync_test_data()
    db = SessionLocal()
    try:
        db.add(IdentityDepartment(
            dept_code="pytest_sync_d001",
            dept_name_cn="Master Dept",
            dept_type="clinical",
            parent_dept_code="P001",
            status="active",
            source_system="HIS",
        ))
        db.add(IdentityDepartmentSource(
            dept_code=None,
            source_system="pytest_sync_his",
            source_code="his_ready",
            source_table="DEPT_DICT",
            source_dept_id="SRC_D001",
            source_dept_name="Unmatched Dept",
            source_parent_dept_code="P001",
            source_dept_type="clinical",
            source_status="active",
            match_status="unmatched",
        ))
        db.add(IdentityDepartmentSource(
            dept_code="pytest_sync_d001",
            source_system="pytest_sync_his",
            source_code="his_ready",
            source_table="DEPT_DICT",
            source_dept_id="SRC_D002",
            source_dept_name="Source Dept",
            source_parent_dept_code="P002",
            source_dept_type="ward",
            source_status="active",
            match_status="matched",
        ))
        db.commit()
    finally:
        db.close()

    first = run_sync("pytest_sync_his", "asset", "identity_department", operator="pytest")
    second = run_sync("pytest_sync_his", "asset", "identity_department", operator="pytest")

    assert first["status"] == "success"
    assert first["scanned"] == 2
    assert first["diffs_created"] == 2
    assert second["status"] == "success"
    assert second["diffs_created"] == 0
    assert second["diffs_skipped_existing"] == 2

    _cleanup_sync_test_data()
