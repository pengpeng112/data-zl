"""L13 identity review: diffs only, no auto-apply."""

from sqlalchemy import delete, select

from app.core.db import SessionLocal
from app.models.identity import IdentityPerson, IdentityPersonSource, IdentitySyncDiff
from app.services.identity_review import build_his_master_review


def test_build_his_master_review_creates_multi_source_diff_without_changing_master():
    db = SessionLocal()
    try:
        code = "PYTEST_REV_001"
        db.execute(delete(IdentitySyncDiff).where(IdentitySyncDiff.entity_code == code))
        db.execute(delete(IdentityPersonSource).where(IdentityPersonSource.person_code == code))
        db.execute(delete(IdentityPerson).where(IdentityPerson.person_code == code))
        db.add(
            IdentityPerson(
                person_code=code,
                person_name_cn="Master Name",
                dept_code="D1",
                primary_source_system="HIS",
                source_system="HIS",
            )
        )
        db.add(
            IdentityPersonSource(
                source_system="HIS",
                source_code="his_source_10_10_10_15",
                source_table="FXHIS.SYS_EMPLOYEE",
                source_person_id=code,
                person_code=code,
                source_person_name="Emp Name",
                source_dept_code="D1",
                match_status="matched",
            )
        )
        db.add(
            IdentityPersonSource(
                source_system="HIS",
                source_code="his_source_10_10_10_15",
                source_table="COMM.STAFF_DICT",
                source_person_id=code,
                person_code=code,
                source_person_name="Staff Name",
                source_dept_code="D2",
                match_status="matched",
            )
        )
        db.commit()

        result = build_his_master_review(db, source_system="HIS")
        db.commit()
        assert result["auto_apply"] is False
        assert result["diffs_created"] >= 1

        person = db.scalar(select(IdentityPerson).where(IdentityPerson.person_code == code))
        assert person.person_name_cn == "Master Name"
        assert person.dept_code == "D1"

        diff = db.scalar(
            select(IdentitySyncDiff).where(
                IdentitySyncDiff.entity_code == code,
                IdentitySyncDiff.diff_type == "multi_source_conflict",
                IdentitySyncDiff.status == "open",
            )
        )
        assert diff is not None
        assert diff.after_data["merge_suggestion"]["action"] == "manual_confirm"
    finally:
        db.execute(delete(IdentitySyncDiff).where(IdentitySyncDiff.entity_code == "PYTEST_REV_001"))
        db.execute(delete(IdentityPersonSource).where(IdentityPersonSource.person_code == "PYTEST_REV_001"))
        db.execute(delete(IdentityPerson).where(IdentityPerson.person_code == "PYTEST_REV_001"))
        db.commit()
        db.close()
