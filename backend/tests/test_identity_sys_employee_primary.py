"""2026-08-24 用户裁决：人员同步以 FXHIS.SYS_EMPLOYEE 为主、COMM.STAFF_DICT 仅辅助。

测试采用与 test_identity_nightly_sync 相同的 SQLite 内存库模式（只建 identity
相关表），避免与根 conftest 的平台库种子/清库交互。

覆盖：
- _build_plan：STAFF.CREATE_DATE 为空时回退 SYS_EMPLOYEE.CREATEDTIME；
- preflight：职称优先 SYS_EMPLOYEE.LEVLCODE 字典名（person.job_title），
  与 STAFF_DICT.TITLE 冲突时员工表权威并写审计注记；
- MODIFIEDTIME 存在即不得 master_data_missing（003539 场景回归）；
- 仅存在于 STAFF_DICT 的人员兜底路径不回归。
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from app.models.identity import IdentityPerson, IdentityPersonSource
from app.models.identity_sync import IdentityClassificationRecord
from app.services.his_identity_sync import _build_plan
from app.services.identity_classification import MASTER_DATA_MISSING
from app.services.identity_classification_preflight import run_classification_preflight

STAFF_TABLE = "COMM.STAFF_DICT"
EMPLOYEE_TABLE = "FXHIS.SYS_EMPLOYEE"


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def _attach_schema(dbapi_conn, connection_record):
        dbapi_conn.execute("ATTACH DATABASE ':memory:' AS asset")

    tables = [IdentityPerson.__table__, IdentityPersonSource.__table__, IdentityClassificationRecord.__table__]
    # identity 表使用 asset schema，SQLite 用 ATTACH 挂载同名 schema
    from sqlalchemy.schema import CreateTable

    with engine.begin() as conn:
        for table in tables:
            # SQLite 不支持 IF NOT EXISTS on schema-qualified create via CreateTable
            conn.execute(CreateTable(table, if_not_exists=True))
    session = Session(engine)
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _rows(staff_create, employee_created, employee_modified="2026-08-24 10:18:08"):
    staff_row = {
        "EMP_NO": "T901", "NAME": "测试员工", "DEPT_CODE": "D001", "JOB": "医生",
        "TITLE": "护士", "STATUS": 1, "ID_NO": None, "CREATE_DATE": staff_create,
    }
    employee_row = {
        "EMPLCODE": "T901", "EMPLNAME": "测试员工", "DEPTCODE": "D001", "DEPTID": None,
        "VALIDSTATE": "1", "IDENNO": None, "USERCODE": None, "ISDELETED": 0,
        "EMPLTYPE": "A1", "POSICODE": None, "LEVLCODE": "233",
        "CREATEDTIME": employee_created, "MODIFIEDTIME": employee_modified,
    }
    return {
        "departments": [],
        "staff": [staff_row],
        "employees": [employee_row],
        "employee_titles": [{"DICT_CODE": "233", "DICT_NAME": "主治医师"}],
        "doctor_groups": [],
        "staff_groups": [],
    }


def test_build_plan_falls_back_to_sys_employee_createdtime():
    plan = _build_plan(_rows(staff_create=None, employee_created="2026-08-20 09:00:00"), "HIS", "src")
    master = plan["masters"]["T901"]
    assert master.source_create_date is not None
    assert str(master.source_create_date).startswith("2026-08-20")
    assert master.job_title == "主治医师"  # LEVLCODE 233 → EmployeeTitle 字典名


def test_build_plan_prefers_staff_create_date_when_present():
    plan = _build_plan(
        _rows(staff_create="2026-08-24 00:00:00", employee_created="2026-08-20 09:00:00"),
        "HIS", "src",
    )
    assert str(plan["masters"]["T901"].source_create_date).startswith("2026-08-24")


def _seed_employee_primary_person(db, *, employee_modified="2026-08-24 10:18:08"):
    db.add(IdentityPerson(
        person_code="T902", person_name_cn="员工表主", primary_source_system="HIS",
        source_system="HIS", raw_job="医生", raw_title=None,
        job_title="主治医师",  # 采集自已持久化的 LEVLCODE 字典名
        source_create_date=None,
    ))
    db.add(IdentityPersonSource(
        person_code="T902", source_system="HIS", source_code="his_source_10_10_10_15",
        source_table=STAFF_TABLE, source_person_id="T902", source_status="active",
        raw_data={"JOB": "医生", "TITLE": "护士", "STATUS": 1, "CREATE_DATE": None},
    ))
    db.add(IdentityPersonSource(
        person_code="T902", source_system="HIS", source_code="his_source_10_10_10_15",
        source_table=EMPLOYEE_TABLE, source_person_id="T902", source_status="active",
        raw_data={"LEVLCODE": "233", "VALIDSTATE": "1", "ISDELETED": 0,
                  "CREATEDTIME": None, "MODIFIEDTIME": employee_modified},
    ))
    db.flush()


def test_preflight_employee_title_is_authoritative(db_session):
    _seed_employee_primary_person(db_session)
    stats = run_classification_preflight(db_session)
    person = db_session.query(IdentityPerson).filter_by(person_code="T902").one()
    assert stats["classified"] >= 1
    assert person.classification == "doctor"
    assert person.conflict_flag is None
    # STAFF_DICT.TITLE=护士 的原始证据保留，不因员工表优先而丢失
    assert person.raw_title == "护士"


def test_preflight_records_title_authority_note(db_session):
    _seed_employee_primary_person(db_session)
    run_classification_preflight(db_session)
    record = db_session.query(IdentityClassificationRecord).filter_by(emp_no="T902").one()
    detail = record.conflict_detail or {}
    assert detail.get("resolved") == "title_mismatch_employee_authority"
    assert detail.get("employee_levlcode_title") == "主治医师"
    assert detail.get("staff_dict_title") == "护士"


def test_preflight_modified_time_prevents_master_data_missing(db_session):
    """003539 场景回归：两表建档时间全空、仅 MODIFIEDTIME 有值 → 不得隔离。"""
    _seed_employee_primary_person(db_session)
    run_classification_preflight(db_session)
    person = db_session.query(IdentityPerson).filter_by(person_code="T902").one()
    assert person.classification != MASTER_DATA_MISSING
    assert person.classification == "doctor"


def test_preflight_both_times_missing_still_isolated(db_session):
    """控制组：员工表 MODIFIEDTIME 也为空且无任何建档时间 → 维持隔离（既有行为）。"""
    db = db_session
    db.add(IdentityPerson(person_code="T903", person_name_cn="无时间员工", primary_source_system="HIS", source_system="HIS"))
    db.add(IdentityPersonSource(
        person_code="T903", source_system="HIS", source_table=STAFF_TABLE,
        source_person_id="T903", source_status="active",
        raw_data={"JOB": "医生", "TITLE": "医师", "STATUS": 1, "CREATE_DATE": None},
    ))
    db.add(IdentityPersonSource(
        person_code="T903", source_system="HIS", source_table=EMPLOYEE_TABLE,
        source_person_id="T903", source_status="active",
        raw_data={"LEVLCODE": "233", "VALIDSTATE": "1", "CREATEDTIME": None, "MODIFIEDTIME": None},
    ))
    db.flush()
    run_classification_preflight(db)
    person = db.query(IdentityPerson).filter_by(person_code="T903").one()
    assert person.classification == MASTER_DATA_MISSING
    assert person.conflict_flag == MASTER_DATA_MISSING


def test_preflight_staff_only_person_keeps_staff_title(db_session):
    """仅存在于 STAFF_DICT 的人员：无员工表证据 → 职称仍用 STAFF_DICT.TITLE。"""
    db = db_session
    db.add(IdentityPerson(
        person_code="T904", person_name_cn="仅辅助表", primary_source_system="HIS",
        source_system="HIS", raw_job="医生", raw_title="主任医师",
        job_title="主任医师", source_create_date=datetime(2026, 8, 1, tzinfo=timezone.utc),
    ))
    db.add(IdentityPersonSource(
        person_code="T904", source_system="HIS", source_table=STAFF_TABLE,
        source_person_id="T904", source_status="active",
        raw_data={"JOB": "医生", "TITLE": "主任医师", "STATUS": 1, "CREATE_DATE": "2026-08-01"},
    ))
    db.flush()
    run_classification_preflight(db)
    person = db.query(IdentityPerson).filter_by(person_code="T904").one()
    assert person.classification == "doctor"
