"""Read-only collectors for identity source staging tables."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.asset_system import AssetDataSource
from ..models.identity import IdentityDepartmentSource, IdentityPersonDepartment, IdentityPersonSource
from ..services.credentials import resolve
from ..services.db_connectors import DB_CONNECTOR_MAP


DEPARTMENT_SOURCE_TABLE = "COMM.DEPT_DICT"
STAFF_SOURCE_TABLE = "COMM.STAFF_DICT"
EMPLOYEE_SOURCE_TABLE = "COMM.SYS_EMPLOYEE"
DOCTOR_GROUP_SOURCE_TABLE = "COMM.DOCTOR_GROUP"
STAFF_GROUP_SOURCE_TABLE = "COMM.STAFF_VS_GROUP"


def _build_connector(source: AssetDataSource):
    db_type = (source.db_type or "").lower()
    connector_cls = DB_CONNECTOR_MAP.get(db_type)
    if connector_cls is None:
        raise HTTPException(status_code=400, detail=f"unsupported db_type: {source.db_type}")
    user, password = resolve(source.credential_ref)
    database = source.service_name or source.database_name or ""
    return connector_cls(
        host=source.host_masked or "",
        port=source.port or 0,
        database=database,
        user=user or "",
        password=password or "",
        connection_mode=source.connection_mode or "direct",
    )


def _row_value(row: dict[str, Any], key: str) -> Any:
    if key in row:
        return row[key]
    upper_key = key.upper()
    if upper_key in row:
        return row[upper_key]
    lower_key = key.lower()
    if lower_key in row:
        return row[lower_key]
    return None


def _text_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_status(stop_flag: Any) -> str:
    value = (_text_or_none(stop_flag) or "").upper()
    if value in {"", "0", "N", "ACTIVE", "ENABLED"}:
        return "active"
    return "inactive"


SENSITIVE_SOURCE_KEYS = {"ID_NO", "IDENNO", "IDCARD", "CARD_NO", "PHONE", "MOBILE", "ADDRESS"}


def _safe_raw_data(row: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in row.items() if str(k).upper() not in SENSITIVE_SOURCE_KEYS}


def _upsert_person_source(
    db: Session,
    *,
    source_system: str,
    source_code: str,
    source_table: str,
    source_person_id: str,
    person_code: str | None,
    person_name: str | None,
    dept_code: str | None,
    status: str | None,
    raw: dict[str, Any],
) -> tuple[int, int]:
    existing = db.scalar(
        select(IdentityPersonSource).where(
            IdentityPersonSource.source_system == source_system,
            IdentityPersonSource.source_table == source_table,
            IdentityPersonSource.source_person_id == source_person_id,
        )
    )
    inserted = 0
    updated = 0
    if existing is None:
        existing = IdentityPersonSource(
            source_system=source_system,
            source_code=source_code,
            source_table=source_table,
            source_person_id=source_person_id,
        )
        db.add(existing)
        inserted = 1
    else:
        updated = 1

    existing.person_code = person_code
    existing.source_code = source_code
    existing.source_person_name = person_name
    existing.source_dept_code = dept_code
    existing.source_status = status
    existing.is_temporary = False
    existing.match_status = "matched" if person_code else "unmatched"
    existing.raw_data = _safe_raw_data(raw)
    existing.last_seen_at = datetime.now(timezone.utc)
    return inserted, updated


def _upsert_person_department(
    db: Session,
    *,
    person_code: str | None,
    dept_code: str | None,
    source_table: str,
    source_dept_code: str | None = None,
    is_primary: bool = False,
) -> bool:
    if not person_code or not dept_code:
        return False
    existing = db.scalar(
        select(IdentityPersonDepartment).where(
            IdentityPersonDepartment.person_code == person_code,
            IdentityPersonDepartment.dept_code == dept_code,
            IdentityPersonDepartment.source_table == source_table,
        )
    )
    if existing is None:
        existing = IdentityPersonDepartment(
            person_code=person_code,
            dept_code=dept_code,
            source_table=source_table,
        )
        db.add(existing)
        created = True
    else:
        created = False
    existing.is_primary = is_primary
    existing.source_dept_code = source_dept_code or dept_code
    existing.updated_at = datetime.now(timezone.utc)
    return created


def collect_his_departments(
    db: Session,
    *,
    source_code: str,
    source_system: str = "HIS",
    max_rows: int = 10000,
) -> dict[str, Any]:
    """Collect COMM.DEPT_DICT into asset_identity_department_sources.

    The source query is read-only and bounded. Local writes are limited to the
    staging table used by the identity diff generator.
    """
    source = db.scalar(select(AssetDataSource).where(AssetDataSource.source_code == source_code))
    if source is None:
        raise HTTPException(status_code=400, detail=f"source_code not found: {source_code}")

    sql = """
SELECT
  DEPT_CODE,
  DEPT_NAME,
  OUTP_OR_INP,
  STOP_FLAG
FROM COMM.DEPT_DICT
WHERE ROWNUM <= :max_rows
"""
    connector = _build_connector(source)
    try:
        rows = connector.execute_readonly(sql, params={"max_rows": max_rows}, max_rows=max_rows)
    finally:
        connector.close()

    now = datetime.now(timezone.utc)
    inserted = 0
    updated = 0
    for row in rows:
        raw = dict(row)
        dept_code = _text_or_none(_row_value(raw, "DEPT_CODE"))
        if not dept_code:
            continue
        dept_name = _text_or_none(_row_value(raw, "DEPT_NAME"))
        dept_type = _text_or_none(_row_value(raw, "OUTP_OR_INP"))
        status = _normalize_status(_row_value(raw, "STOP_FLAG"))

        existing = db.scalar(
            select(IdentityDepartmentSource).where(
                IdentityDepartmentSource.source_system == source_system,
                IdentityDepartmentSource.source_table == DEPARTMENT_SOURCE_TABLE,
                IdentityDepartmentSource.source_dept_id == dept_code,
            )
        )
        if existing is None:
            existing = IdentityDepartmentSource(
                source_system=source_system,
                source_code=source_code,
                source_table=DEPARTMENT_SOURCE_TABLE,
                source_dept_id=dept_code,
            )
            db.add(existing)
            inserted += 1
        else:
            updated += 1

        existing.dept_code = dept_code
        existing.source_code = source_code
        existing.source_dept_name = dept_name
        existing.source_parent_dept_code = None
        existing.source_dept_type = dept_type
        existing.source_status = status
        existing.match_status = "matched"
        existing.raw_data = raw
        existing.last_seen_at = now

    return {
        "status": "success",
        "mode": "live_source",
        "entity_type": "identity_department",
        "source_code": source_code,
        "source_system": source_system,
        "source_table": DEPARTMENT_SOURCE_TABLE,
        "scanned": len(rows),
        "inserted": inserted,
        "updated": updated,
    }


def collect_his_persons(
    db: Session,
    *,
    source_code: str,
    source_system: str = "HIS",
    max_rows: int = 20000,
) -> dict[str, Any]:
    """Collect HIS staff sources into local identity staging tables."""
    source = db.scalar(select(AssetDataSource).where(AssetDataSource.source_code == source_code))
    if source is None:
        raise HTTPException(status_code=400, detail=f"source_code not found: {source_code}")

    connector = _build_connector(source)
    try:
        staff_rows = connector.execute_readonly(
            """
SELECT EMP_NO, NAME, DEPT_CODE, JOB, TITLE, STATUS, ID_NO
FROM COMM.STAFF_DICT
WHERE ROWNUM <= :max_rows
""",
            params={"max_rows": max_rows},
            max_rows=max_rows,
        )
        employee_rows = connector.execute_readonly(
            """
SELECT EMPLCODE, EMPLNAME, DEPTCODE, DEPTID, VALIDSTATE, IDENNO, USERID
FROM COMM.SYS_EMPLOYEE
WHERE ROWNUM <= :max_rows
""",
            params={"max_rows": max_rows},
            max_rows=max_rows,
        )
        doctor_group_rows = connector.execute_readonly(
            """
SELECT DOCTOR_USER, DEPT_CODE, DOCTOR
FROM COMM.DOCTOR_GROUP
WHERE ROWNUM <= :max_rows
""",
            params={"max_rows": max_rows},
            max_rows=max_rows,
        )
        staff_group_rows = connector.execute_readonly(
            """
SELECT svg.GROUP_CLASS, svg.GROUP_CODE, svg.EMP_NO, sgd.DEPT_CODE
FROM COMM.STAFF_VS_GROUP svg
LEFT JOIN COMM.STAFF_GROUP_DICT sgd ON sgd.GROUP_CODE = svg.GROUP_CODE
WHERE ROWNUM <= :max_rows
""",
            params={"max_rows": max_rows},
            max_rows=max_rows,
        )
    finally:
        connector.close()

    inserted_sources = 0
    updated_sources = 0
    department_links_created = 0

    for row in staff_rows:
        raw = dict(row)
        emp_no = _text_or_none(_row_value(raw, "EMP_NO"))
        if not emp_no:
            continue
        dept_code = _text_or_none(_row_value(raw, "DEPT_CODE"))
        ins, upd = _upsert_person_source(
            db,
            source_system=source_system,
            source_code=source_code,
            source_table=STAFF_SOURCE_TABLE,
            source_person_id=emp_no,
            person_code=emp_no,
            person_name=_text_or_none(_row_value(raw, "NAME")),
            dept_code=dept_code,
            status=_normalize_status(_row_value(raw, "STATUS")),
            raw=raw,
        )
        inserted_sources += ins
        updated_sources += upd
        department_links_created += int(_upsert_person_department(
            db, person_code=emp_no, dept_code=dept_code, source_table=STAFF_SOURCE_TABLE, is_primary=True
        ))

    for row in employee_rows:
        raw = dict(row)
        emplcode = _text_or_none(_row_value(raw, "EMPLCODE"))
        if not emplcode:
            continue
        person_code = _text_or_none(_row_value(raw, "USERID")) or emplcode
        dept_code = _text_or_none(_row_value(raw, "DEPTCODE")) or _text_or_none(_row_value(raw, "DEPTID"))
        ins, upd = _upsert_person_source(
            db,
            source_system=source_system,
            source_code=source_code,
            source_table=EMPLOYEE_SOURCE_TABLE,
            source_person_id=emplcode,
            person_code=person_code,
            person_name=_text_or_none(_row_value(raw, "EMPLNAME")),
            dept_code=dept_code,
            status=_normalize_status(_row_value(raw, "VALIDSTATE")),
            raw=raw,
        )
        inserted_sources += ins
        updated_sources += upd
        department_links_created += int(_upsert_person_department(
            db, person_code=person_code, dept_code=dept_code, source_table=EMPLOYEE_SOURCE_TABLE, is_primary=True
        ))

    for row in doctor_group_rows:
        raw = dict(row)
        person_code = _text_or_none(_row_value(raw, "DOCTOR_USER"))
        dept_code = _text_or_none(_row_value(raw, "DEPT_CODE"))
        department_links_created += int(_upsert_person_department(
            db, person_code=person_code, dept_code=dept_code, source_table=DOCTOR_GROUP_SOURCE_TABLE, is_primary=False
        ))

    for row in staff_group_rows:
        raw = dict(row)
        person_code = _text_or_none(_row_value(raw, "EMP_NO"))
        dept_code = _text_or_none(_row_value(raw, "DEPT_CODE"))
        department_links_created += int(_upsert_person_department(
            db, person_code=person_code, dept_code=dept_code, source_table=STAFF_GROUP_SOURCE_TABLE, is_primary=False
        ))

    return {
        "status": "success",
        "mode": "live_source",
        "entity_type": "identity_person",
        "source_code": source_code,
        "source_system": source_system,
        "source_tables": [STAFF_SOURCE_TABLE, EMPLOYEE_SOURCE_TABLE, DOCTOR_GROUP_SOURCE_TABLE, STAFF_GROUP_SOURCE_TABLE],
        "scanned": len(staff_rows) + len(employee_rows) + len(doctor_group_rows) + len(staff_group_rows),
        "person_sources_inserted": inserted_sources,
        "person_sources_updated": updated_sources,
        "department_links_created": department_links_created,
    }


def collect_his_identity_sources(
    db: Session,
    *,
    source_code: str,
    source_system: str = "HIS",
    entity_type: str = "identity_department",
    max_rows: int = 20000,
) -> dict[str, Any]:
    if entity_type == "identity_department":
        return collect_his_departments(db, source_code=source_code, source_system=source_system, max_rows=max_rows)
    if entity_type == "identity_person":
        return collect_his_persons(db, source_code=source_code, source_system=source_system, max_rows=max_rows)
    if entity_type == "identity_all":
        departments = collect_his_departments(db, source_code=source_code, source_system=source_system, max_rows=max_rows)
        persons = collect_his_persons(db, source_code=source_code, source_system=source_system, max_rows=max_rows)
        return {
            "status": "success",
            "mode": "live_source",
            "entity_type": "identity_all",
            "source_code": source_code,
            "source_system": source_system,
            "departments": departments,
            "persons": persons,
            "scanned": (departments.get("scanned") or 0) + (persons.get("scanned") or 0),
        }
    raise HTTPException(status_code=400, detail="unsupported identity source collection entity_type")
