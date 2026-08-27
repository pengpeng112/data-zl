"""HIS identity synchronization.

This module only reads HIS through OracleConnector and writes local identity
master data when dry_run is false. Source SQL is SELECT-only and row limited.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.config import settings
from ..models.governance_base import GovernAuditLog
from ..models.identity import (
    IdentityDepartment,
    IdentityPerson,
    IdentityPersonDepartment,
    IdentityPersonSource,
)
from ..services.db_connectors import OracleConnector

DEPT_TABLE = "COMM.DEPT_DICT"
STAFF_TABLE = "COMM.STAFF_DICT"
# 源库实测：SYS_EMPLOYEE 在 FXHIS，不在 COMM；USERCODE 多为空，人员主键用 EMPLCODE，
# 与 COMM.STAFF_DICT.EMP_NO 桥接（约 98%）。用户口径：以 SYS_EMPLOYEE 为主数据。
EMPLOYEE_TABLE = "FXHIS.SYS_EMPLOYEE"
EMPLOYEE_TITLE_DICT_TABLE = "PORTAL_USER.PORTAL_SYS_DICT"
DOCTOR_GROUP_TABLE = "COMM.DOCTOR_GROUP"
STAFF_GROUP_TABLE = "COMM.STAFF_VS_GROUP"
# 保留常量仅作文档：活库实测该表 DEPT_CODE 全空，采集不再依赖它（见 _collect 注释）。
STAFF_GROUP_DICT_TABLE = "COMM.STAFF_GROUP_DICT"

SENSITIVE_KEYS = {"ID_NO", "IDENNO", "IDCARD", "CARD_NO", "PHONE", "MOBILE", "ADDRESS"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _value(row: dict[str, Any], key: str) -> Any:
    if key in row:
        return row[key]
    if key.upper() in row:
        return row[key.upper()]
    if key.lower() in row:
        return row[key.lower()]
    return None


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _is_deleted_flag(value: Any) -> bool:
    if value is None:
        return False
    return str(value).strip() not in {"", "0", "N", "False", "false"}


def _employee_employment_status(row: dict[str, Any]) -> str:
    """HIS 禁用：ISDELETED 非 0，或 VALIDSTATE=0。"""
    if _is_deleted_flag(_value(row, "ISDELETED")):
        return "inactive"
    return _normalize_status(_value(row, "VALIDSTATE"))


def _normalize_status(value: Any) -> str:
    """归一 STAFF_DICT.STATUS / SYS_EMPLOYEE.VALIDSTATE（活库实测 1=在用，0=停用）。"""
    text = (_text(value) or "").upper()
    if text == "1":
        return "active"
    if text == "0":
        return "inactive"
    return "unknown"


def _normalize_stop_flag(value: Any) -> str:
    """归一 DEPT_DICT.STOP_FLAG（活库实测 NULL/'0'=有效，'1'=停用）。"""
    text = (_text(value) or "").upper()
    if text in {"", "0", "N"}:
        return "active"
    if text in {"1", "Y"}:
        return "inactive"
    return "unknown"


def _hash(value: Any) -> str | None:
    text = _text(value)
    if not text:
        return None
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _mask(value: Any) -> str | None:
    text = _text(value)
    if not text:
        return None
    if len(text) <= 6:
        return "*" * len(text)
    return f"{text[:3]}{'*' * (len(text) - 6)}{text[-3:]}"


def _safe_raw(row: dict[str, Any]) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for key, value in row.items():
        upper = str(key).upper()
        if upper in SENSITIVE_KEYS:
            safe[f"{key}_mask"] = _mask(value)
            safe[f"{key}_sha256"] = _hash(value)
        else:
            safe[key] = value.isoformat() if hasattr(value, "isoformat") else value
    return safe


@dataclass
class PersonMaster:
    person_code: str
    person_name: str | None = None
    dept_code: str | None = None
    job_title: str | None = None
    employment_status: str | None = None
    primary_source_system: str = "HIS"
    source_system: str = "HIS"
    raw_job: str | None = None
    raw_title: str | None = None
    source_create_date: Any = None
    source_modified_time: Any = None


def _connector() -> OracleConnector:
    user = settings.his_source_user
    password = settings.his_source_password
    if not password:
        # 回退：从已登记数据源凭据文件读取（与 asset_data_sources.credential_ref 一致）
        from pathlib import Path

        for path in (
            "/etc/data-asset/credentials/his_source_10_10_10_15",
            "/etc/data-asset/credentials/his_source",
        ):
            try:
                raw = Path(path).read_text(encoding="utf-8").strip()
            except OSError:
                continue
            if ":" in raw:
                user, password = raw.split(":", 1)
                break
    if not password:
        raise HTTPException(status_code=400, detail="APP_HIS_SOURCE_PASSWORD is not configured")
    jump_key = settings.his_source_jump_key or None
    return OracleConnector(
        host=settings.his_source_host,
        port=settings.his_source_port,
        database=settings.his_source_service,
        user=user,
        password=password,
        connection_mode=settings.his_source_connection_mode or "direct",
        oracle_client_lib_dir=settings.his_source_oracle_client_lib or "/opt/oracle",
        jump_host=settings.his_source_jump_host,
        jump_port=settings.his_source_jump_port,
        jump_user=settings.his_source_jump_user,
        jump_key=jump_key,
    )


def _select(connector: OracleConnector, sql: str, max_rows: int) -> list[dict[str, Any]]:
    return connector.execute_readonly(sql, params={"max_rows": max_rows}, max_rows=max_rows)


def _select_optional(
    connector: OracleConnector,
    sql: str,
    max_rows: int,
    *,
    label: str,
    notes: list[str],
) -> list[dict[str, Any]]:
    """SELECT optional identity tables; missing objects become empty + note (ORA-00942)."""
    try:
        return _select(connector, sql, max_rows)
    except Exception as ex:
        msg = str(ex)
        if "ORA-00942" in msg or "does not exist" in msg.lower():
            notes.append(f"{label}: missing_or_inaccessible ({type(ex).__name__})")
            return []
        raise


def _build_employee_title_map(rows: list[dict[str, Any]]) -> dict[str, str]:
    """Return a unique LEVLCODE -> DICT_NAME map and fail closed on ambiguity."""
    names_by_code: dict[str, set[str]] = {}
    for row in rows:
        code = _text(_value(row, "DICT_CODE"))
        title = _text(_value(row, "DICT_NAME"))
        if code and title:
            names_by_code.setdefault(code, set()).add(title)
    ambiguous = sorted(code for code, names in names_by_code.items() if len(names) > 1)
    if ambiguous:
        # Only dictionary codes are included; never employee identifiers or names.
        raise RuntimeError(
            "EmployeeTitle dictionary contains conflicting names for "
            f"{len(ambiguous)} code(s); title synchronization is closed"
        )
    return {code: next(iter(names)) for code, names in names_by_code.items()}


def _collect(max_rows: int) -> tuple[dict[str, list[dict[str, Any]]], list[str]]:
    connector = _connector()
    notes: list[str] = []
    try:
        rows = {
            "departments": _select(connector, f"""
SELECT DEPT_CODE, DEPT_NAME, OUTP_OR_INP, STOP_FLAG
FROM {DEPT_TABLE}
WHERE ROWNUM <= :max_rows
""", max_rows),
            "staff": _select(connector, f"""
SELECT EMP_NO, NAME, DEPT_CODE, JOB, TITLE, STATUS, ID_NO, CREATE_DATE
FROM {STAFF_TABLE}
WHERE ROWNUM <= :max_rows
""", max_rows),
            # FXHIS.SYS_EMPLOYEE：主数据；USERCODE 常空，桥接字段用 EMPLCODE↔STAFF.EMP_NO
            "employees": _select_optional(
                connector,
                f"""
SELECT EMPLCODE, EMPLNAME, DEPTCODE, DEPTID, VALIDSTATE, IDENNO, USERCODE,
       ISDELETED, EMPLTYPE, POSICODE, LEVLCODE, CREATEDTIME, MODIFIEDTIME
FROM {EMPLOYEE_TABLE}
WHERE ROWNUM <= :max_rows
""",
                max_rows,
                label=EMPLOYEE_TABLE,
                notes=notes,
            ),
            "employee_titles": _select(connector, f"""
SELECT DICT_CODE, DICT_NAME
FROM {EMPLOYEE_TITLE_DICT_TABLE}
WHERE TYPE_CODE = 'EmployeeTitle'
  AND ROWNUM <= :max_rows
""",
                max_rows,
            ),
            "doctor_groups": _select(connector, f"""
SELECT DOCTOR_USER, DEPT_CODE, DOCTOR
FROM {DOCTOR_GROUP_TABLE}
WHERE ROWNUM <= :max_rows
""", max_rows),
            # 活库实测：STAFF_GROUP_DICT.DEPT_CODE 全部为空；STAFF_VS_GROUP.GROUP_CODE
            # 本身就是科室/病区编码（9449/9449 命中 DEPT_DICT），直接作为附加科室。
            "staff_groups": _select(connector, f"""
SELECT svg.GROUP_CLASS, svg.GROUP_CODE, svg.EMP_NO
FROM {STAFF_GROUP_TABLE} svg
WHERE ROWNUM <= :max_rows
""", max_rows),
        }
        return rows, notes
    finally:
        connector.close()


def _upsert_department(db: Session, row: dict[str, Any], source_system: str) -> bool:
    dept_code = _text(_value(row, "DEPT_CODE"))
    if not dept_code:
        return False
    dept = db.scalar(select(IdentityDepartment).where(IdentityDepartment.dept_code == dept_code))
    created = dept is None
    if dept is None:
        dept = IdentityDepartment(dept_code=dept_code, dept_name_cn=_text(_value(row, "DEPT_NAME")) or dept_code)
        db.add(dept)
    dept.dept_name_cn = _text(_value(row, "DEPT_NAME")) or dept.dept_name_cn or dept_code
    dept.dept_type = _text(_value(row, "OUTP_OR_INP"))
    dept.source_system = source_system
    dept.source_table = DEPT_TABLE
    dept.source_dept_id = dept_code
    dept.status = _normalize_stop_flag(_value(row, "STOP_FLAG"))
    dept.last_source_sync_at = _now()
    dept.updated_at = _now()
    return created


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
) -> bool:
    src = db.scalar(select(IdentityPersonSource).where(
        IdentityPersonSource.source_system == source_system,
        IdentityPersonSource.source_table == source_table,
        IdentityPersonSource.source_person_id == source_person_id,
    ))
    created = src is None
    if src is None:
        src = IdentityPersonSource(source_system=source_system, source_table=source_table, source_person_id=source_person_id)
        db.add(src)
    src.source_code = source_code
    src.person_code = person_code
    src.source_person_name = person_name
    src.source_dept_code = dept_code
    src.source_status = status
    src.is_temporary = False
    src.match_status = "matched" if person_code else "unmatched"
    src.raw_data = _safe_raw(raw)
    src.last_seen_at = _now()
    return created


def _upsert_person_department(
    db: Session,
    *,
    person_code: str | None,
    dept_code: str | None,
    source_table: str,
    is_primary: bool,
    seen: set[tuple[str, str, str]] | None = None,
    group_class: str | None = None,
) -> bool:
    if not person_code or not dept_code:
        return False
    key = (person_code, dept_code, source_table)
    # 同一事务内源数据重复行：避免二次 INSERT 触发唯一约束
    if seen is not None and key in seen:
        return False
    link = db.scalar(select(IdentityPersonDepartment).where(
        IdentityPersonDepartment.person_code == person_code,
        IdentityPersonDepartment.dept_code == dept_code,
        IdentityPersonDepartment.source_table == source_table,
    ))
    created = link is None
    if link is None:
        link = IdentityPersonDepartment(person_code=person_code, dept_code=dept_code, source_table=source_table)
        db.add(link)
        # 立即 flush 以便同事务内后续 scalar 可见（可选）；用 seen 更轻量
    if seen is not None:
        seen.add(key)
    link.is_primary = is_primary if created else (bool(link.is_primary) or is_primary)
    link.source_dept_code = dept_code
    if group_class is not None:
        link.group_class = group_class
    link.updated_at = _now()
    return created


def _upsert_person(db: Session, person: PersonMaster) -> bool:
    row = db.scalar(select(IdentityPerson).where(IdentityPerson.person_code == person.person_code))
    created = row is None
    if row is None:
        row = IdentityPerson(person_code=person.person_code)
        db.add(row)
    row.person_name_cn = person.person_name or row.person_name_cn
    row.dept_code = person.dept_code or row.dept_code
    row.job_title = person.job_title or row.job_title
    row.employment_status = person.employment_status or row.employment_status
    row.primary_source_system = person.primary_source_system
    row.source_system = person.source_system
    # 分类要素（103/107 纳管基线）：每次同步刷新，供分类预检使用
    if person.raw_job is not None:
        row.raw_job = person.raw_job
    if person.raw_title is not None:
        row.raw_title = person.raw_title
    if person.source_create_date is not None:
        row.source_create_date = person.source_create_date
    row.updated_at = _now()
    return created


def _build_plan(rows: dict[str, list[dict[str, Any]]], source_system: str, source_code: str) -> dict[str, Any]:
    staff_by_emp_no: dict[str, dict[str, Any]] = {}
    masters: dict[str, PersonMaster] = {}
    bridge_hits = 0
    doctor_group_matched = 0
    doctor_group_unmatched = 0
    title_by_level_code = _build_employee_title_map(rows.get("employee_titles", []))
    if rows["employees"] and not title_by_level_code:
        raise RuntimeError("EmployeeTitle dictionary is empty; title synchronization is closed")
    title_mapped = 0
    title_unmapped = 0

    for row in rows["staff"]:
        emp_no = _text(_value(row, "EMP_NO"))
        if not emp_no:
            continue
        staff_by_emp_no[emp_no] = row

    # 主数据：SYS_EMPLOYEE 优先
    for row in rows["employees"]:
        emplcode = _text(_value(row, "EMPLCODE"))
        if not emplcode:
            continue
        usercode = _text(_value(row, "USERCODE"))
        # 桥接：EMPLCODE 或 USERCODE 命中 STAFF.EMP_NO
        if emplcode in staff_by_emp_no or (usercode and usercode in staff_by_emp_no):
            bridge_hits += 1
        staff = staff_by_emp_no.get(emplcode) or (staff_by_emp_no.get(usercode) if usercode else None)
        level_code = _text(_value(row, "LEVLCODE"))
        employee_title = title_by_level_code.get(level_code) if level_code else None
        if employee_title:
            title_mapped += 1
        else:
            title_unmapped += 1
        masters[emplcode] = PersonMaster(
            person_code=emplcode,
            person_name=_text(_value(row, "EMPLNAME")) or (_text(_value(staff, "NAME")) if staff else None),
            dept_code=_text(_value(row, "DEPTCODE"))
            or _text(_value(row, "DEPTID"))
            or (_text(_value(staff, "DEPT_CODE")) if staff else None),
            # JHEMR users.education_title must use SYS_EMPLOYEE.LEVLCODE's
            # EmployeeTitle dictionary name, not COMM.STAFF_DICT free text.
            job_title=employee_title,
            employment_status=_employee_employment_status(row),
            raw_job=_text(_value(staff, "JOB")) if staff else None,
            raw_title=_text(_value(staff, "TITLE")) if staff else None,
            # 2026-08-24 用户裁决：时间/职称以 FXHIS.SYS_EMPLOYEE 为主、
            # COMM.STAFF_DICT 仅辅助——建档时间先取 STAFF.CREATE_DATE，
            # 为空时回退 SYS_EMPLOYEE.CREATEDTIME（新职工常见 STAFF 无建档日期）。
            source_create_date=(
                (_value(staff, "CREATE_DATE") if staff else None)
                or _value(row, "CREATEDTIME")
            ),
            source_modified_time=_value(row, "MODIFIEDTIME"),
        )

    # 补充：仅出现在 STAFF_DICT、不在 SYS_EMPLOYEE 的人员
    for emp_no, row in staff_by_emp_no.items():
        if emp_no in masters:
            continue
        masters[emp_no] = PersonMaster(
            person_code=emp_no,
            person_name=_text(_value(row, "NAME")),
            dept_code=_text(_value(row, "DEPT_CODE")),
            job_title=_text(_value(row, "TITLE")) or _text(_value(row, "JOB")),
            employment_status=_normalize_status(_value(row, "STATUS")),
            raw_job=_text(_value(row, "JOB")),
            raw_title=_text(_value(row, "TITLE")),
            source_create_date=_value(row, "CREATE_DATE"),
        )

    known_person_codes = set(masters)
    for row in rows["doctor_groups"]:
        person_code = _text(_value(row, "DOCTOR_USER"))
        if person_code and person_code in known_person_codes:
            doctor_group_matched += 1
        else:
            doctor_group_unmatched += 1

    return {
        "source_system": source_system,
        "source_code": source_code,
        "masters": masters,
        "bridge_hits": bridge_hits,
        "doctor_group_matched": doctor_group_matched,
        "doctor_group_unmatched": doctor_group_unmatched,
        "staff_only_persons": max(0, len(masters) - len(rows["employees"])),
        "title_mapped": title_mapped,
        "title_unmapped": title_unmapped,
        "title_dictionary_codes": len(title_by_level_code),
    }


def sync_his_identity(
    db: Session,
    *,
    operator: str | None = None,
    dry_run: bool = False,
    max_rows: int | None = None,
    write_audit: bool = True,
) -> dict[str, Any]:
    max_rows = max(1, min(int(max_rows or settings.his_identity_sync_max_rows), 50000))
    source_system = "HIS"
    source_code = "his_source_10_10_10_15"
    started_at = _now().isoformat()
    rows, collect_notes = _collect(max_rows)
    plan = _build_plan(rows, source_system, source_code)

    result: dict[str, Any] = {
        "status": "success",
        "mode": "dry_run" if dry_run else "apply",
        "source_system": source_system,
        "source_code": source_code,
        "dry_run": dry_run,
        "started_at": started_at,
        "max_rows": max_rows,
        "scanned": {key: len(value) for key, value in rows.items()},
        "collect_notes": collect_notes,
        "prepared": {
            "departments": len(rows["departments"]),
            "persons": len(plan["masters"]),
            "person_sources": len(rows["staff"]) + len(rows["employees"]),
            "person_departments": len(rows["staff"]) + len(rows["employees"]) + len(rows["doctor_groups"]) + len(rows["staff_groups"]),
        },
        "bridge": {
            "sys_employee_table": EMPLOYEE_TABLE,
            "sys_employee_rows": len(rows["employees"]),
            "bridge_hits": plan["bridge_hits"],
            "bridge_rate": round(plan["bridge_hits"] / len(rows["employees"]), 4) if rows["employees"] else None,
            "bridge_rule": "EMPLCODE|USERCODE = COMM.STAFF_DICT.EMP_NO",
            "sys_employee_available": not any(EMPLOYEE_TABLE in n for n in collect_notes),
            "staff_only_persons": plan.get("staff_only_persons", 0),
            "primary_source": "FXHIS.SYS_EMPLOYEE",
        },
        "doctor_group_diagnostics": {
            "matched_by_doctor_user": plan["doctor_group_matched"],
            "unmatched_doctor_user": plan["doctor_group_unmatched"],
            "note": "unmatched_doctor_user 可忽略（业务确认）",
        },
        "employee_title_diagnostics": {
            "source": f"{EMPLOYEE_TABLE}.LEVLCODE -> {EMPLOYEE_TITLE_DICT_TABLE}.DICT_CODE",
            "target_field": "jhemr.users.education_title",
            "dictionary_codes": plan["title_dictionary_codes"],
            "mapped_employees": plan["title_mapped"],
            "unmapped_employees": plan["title_unmapped"],
            "overwrite_existing": True,
            "blank_source_clears_target": False,
        },
        "upserted": {"departments": 0, "persons": 0, "person_sources": 0, "person_departments": 0},
    }

    if dry_run:
        result["finished_at"] = _now().isoformat()
        return result

    pd_seen: set[tuple[str, str, str]] = set()

    for row in rows["departments"]:
        result["upserted"]["departments"] += int(_upsert_department(db, row, source_system))

    for row in rows["staff"]:
        emp_no = _text(_value(row, "EMP_NO"))
        if not emp_no:
            continue
        dept_code = _text(_value(row, "DEPT_CODE"))
        result["upserted"]["person_sources"] += int(_upsert_person_source(
            db,
            source_system=source_system,
            source_code=source_code,
            source_table=STAFF_TABLE,
            source_person_id=emp_no,
            person_code=emp_no,
            person_name=_text(_value(row, "NAME")),
            dept_code=dept_code,
            status=_normalize_status(_value(row, "STATUS")),
            raw=row,
        ))
        result["upserted"]["person_departments"] += int(_upsert_person_department(
            db, person_code=emp_no, dept_code=dept_code, source_table=STAFF_TABLE, is_primary=True, seen=pd_seen
        ))

    for row in rows["employees"]:
        emplcode = _text(_value(row, "EMPLCODE"))
        if not emplcode:
            continue
        person_code = emplcode
        dept_code = _text(_value(row, "DEPTCODE")) or _text(_value(row, "DEPTID"))
        result["upserted"]["person_sources"] += int(_upsert_person_source(
            db,
            source_system=source_system,
            source_code=source_code,
            source_table=EMPLOYEE_TABLE,
            source_person_id=emplcode,
            person_code=person_code,
            person_name=_text(_value(row, "EMPLNAME")),
            dept_code=dept_code,
            status=_employee_employment_status(row),
            raw=row,
        ))
        result["upserted"]["person_departments"] += int(_upsert_person_department(
            db, person_code=person_code, dept_code=dept_code, source_table=EMPLOYEE_TABLE, is_primary=True, seen=pd_seen
        ))

    for person in plan["masters"].values():
        result["upserted"]["persons"] += int(_upsert_person(db, person))

    for row in rows["doctor_groups"]:
        result["upserted"]["person_departments"] += int(_upsert_person_department(
            db,
            person_code=_text(_value(row, "DOCTOR_USER")),
            dept_code=_text(_value(row, "DEPT_CODE")),
            source_table=DOCTOR_GROUP_TABLE,
            is_primary=False,
            seen=pd_seen,
        ))

    for row in rows["staff_groups"]:
        result["upserted"]["person_departments"] += int(_upsert_person_department(
            db,
            person_code=_text(_value(row, "EMP_NO")),
            dept_code=_text(_value(row, "GROUP_CODE")),
            source_table=STAFF_GROUP_TABLE,
            is_primary=False,
            seen=pd_seen,
            group_class=_text(_value(row, "GROUP_CLASS")),
        ))

    result["finished_at"] = _now().isoformat()
    if write_audit:
        db.add(GovernAuditLog(
            module="sync",
            entity_type="identity_his",
            entity_ref=source_code,
            action="sync_run",
            before_data={"dry_run": dry_run, "source": source_code},
            after_data={
                "status": result["status"],
                "scanned": result["scanned"],
                "prepared": result["prepared"],
                "upserted": result["upserted"],
                "bridge": result["bridge"],
                "doctor_group_diagnostics": result["doctor_group_diagnostics"],
                "employee_title_diagnostics": result["employee_title_diagnostics"],
            },
            operator=operator,
        ))
    db.commit()
    return result
