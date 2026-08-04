"""Cross-system synchronization executor.

The executor is intentionally conservative: source systems are read-only and
target writes are limited to local governance diff/audit tables. Real source
collection can be plugged into staging tables before calling this module.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.db import SessionLocal
from ..models.governance_base import GovernAuditLog
from ..models.identity import IdentityDepartment, IdentityDepartmentSource, IdentityPerson, IdentityPersonSource, IdentitySyncDiff


SUPPORTED_ENTITY_TYPES = {
    "identity_department",
    "identity_person",
    "identity_his",
    "medical_code",
    "metadata_collect",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _audit_sync(
    db: Session,
    *,
    source_system: str,
    target_system: str,
    entity_type: str,
    result: dict[str, Any],
    operator: str | None,
) -> None:
    db.add(
        GovernAuditLog(
            module="sync",
            entity_type=entity_type,
            entity_ref=f"{source_system}->{target_system}",
            action="sync_run",
            before_data={"source": source_system, "target": target_system},
            after_data=result,
            operator=operator,
        )
    )


def _open_identity_diff_exists(
    db: Session,
    *,
    source_system: str,
    target_system: str,
    entity_type: str,
    entity_code: str | None,
    diff_type: str,
) -> bool:
    stmt = select(IdentitySyncDiff).where(
        IdentitySyncDiff.source_system == source_system,
        IdentitySyncDiff.target_system == target_system,
        IdentitySyncDiff.entity_type == entity_type,
        IdentitySyncDiff.entity_code == entity_code,
        IdentitySyncDiff.diff_type == diff_type,
        IdentitySyncDiff.status == "open",
    )
    return db.scalar(stmt.limit(1)) is not None


def _add_identity_diff(
    db: Session,
    *,
    source_system: str,
    target_system: str,
    entity_type: str,
    entity_code: str | None,
    diff_type: str,
    before_data: dict[str, Any] | None,
    after_data: dict[str, Any] | None,
    severity: str = "medium",
) -> bool:
    if _open_identity_diff_exists(
        db,
        source_system=source_system,
        target_system=target_system,
        entity_type=entity_type,
        entity_code=entity_code,
        diff_type=diff_type,
    ):
        return False
    db.add(
        IdentitySyncDiff(
            diff_type=diff_type,
            source_system=source_system,
            target_system=target_system,
            entity_type=entity_type,
            entity_code=entity_code,
            before_data=before_data,
            after_data=after_data,
            severity=severity,
            status="open",
        )
    )
    return True


def _person_source_payload(src: IdentityPersonSource) -> dict[str, Any]:
    return {
        "source_system": src.source_system,
        "source_code": src.source_code,
        "source_table": src.source_table,
        "source_person_id": src.source_person_id,
        "source_person_name": src.source_person_name,
        "source_dept_code": src.source_dept_code,
        "source_status": src.source_status,
        "person_code": src.person_code,
        "match_status": src.match_status,
        "is_temporary": bool(src.is_temporary),
    }


def _person_payload(person: IdentityPerson) -> dict[str, Any]:
    return {
        "person_code": person.person_code,
        "person_name_cn": person.person_name_cn,
        "dept_code": person.dept_code,
        "dept_name_cn": person.dept_name_cn,
        "employment_status": person.employment_status,
        "source_system": person.source_system,
    }


def _department_source_payload(src: IdentityDepartmentSource) -> dict[str, Any]:
    return {
        "source_system": src.source_system,
        "source_code": src.source_code,
        "source_table": src.source_table,
        "source_dept_id": src.source_dept_id,
        "source_dept_name": src.source_dept_name,
        "source_parent_dept_code": src.source_parent_dept_code,
        "source_dept_type": src.source_dept_type,
        "source_status": src.source_status,
        "dept_code": src.dept_code,
        "match_status": src.match_status,
    }


def _department_payload(dept: IdentityDepartment) -> dict[str, Any]:
    return {
        "dept_code": dept.dept_code,
        "dept_name_cn": dept.dept_name_cn,
        "dept_type": dept.dept_type,
        "parent_dept_code": dept.parent_dept_code,
        "status": dept.status,
        "source_system": dept.source_system,
    }


def _run_identity_department_sync(db: Session, source_system: str, target_system: str) -> dict[str, Any]:
    sources = db.scalars(
        select(IdentityDepartmentSource).where(IdentityDepartmentSource.source_system == source_system)
    ).all()
    scanned = len(sources)
    created = 0
    skipped_existing = 0

    for src in sources:
        source_payload = _department_source_payload(src)
        entity_code = src.dept_code or src.source_dept_id
        match_status = (src.match_status or "").lower()

        if not src.dept_code or match_status in {"", "unmatched"}:
            added = _add_identity_diff(
                db,
                source_system=source_system,
                target_system=target_system,
                entity_type="identity_department",
                entity_code=entity_code,
                diff_type="source_unmatched",
                before_data=None,
                after_data=source_payload,
                severity="high",
            )
            created += int(added)
            skipped_existing += int(not added)
            continue

        dept = db.scalar(select(IdentityDepartment).where(IdentityDepartment.dept_code == src.dept_code))
        if dept is None:
            added = _add_identity_diff(
                db,
                source_system=source_system,
                target_system=target_system,
                entity_type="identity_department",
                entity_code=entity_code,
                diff_type="missing_master_department",
                before_data=None,
                after_data=source_payload,
                severity="high",
            )
            created += int(added)
            skipped_existing += int(not added)
            continue

        changed_fields: dict[str, dict[str, Any]] = {}
        comparisons = {
            "dept_name_cn": (dept.dept_name_cn, src.source_dept_name),
            "parent_dept_code": (dept.parent_dept_code, src.source_parent_dept_code),
            "dept_type": (dept.dept_type, src.source_dept_type),
            "status": (dept.status, src.source_status),
        }
        for field, (master_value, source_value) in comparisons.items():
            if source_value and master_value and source_value != master_value:
                changed_fields[field] = {"master": master_value, "source": source_value}

        if changed_fields:
            added = _add_identity_diff(
                db,
                source_system=source_system,
                target_system=target_system,
                entity_type="identity_department",
                entity_code=entity_code,
                diff_type="field_mismatch",
                before_data=_department_payload(dept),
                after_data={**source_payload, "changed_fields": changed_fields},
                severity="medium",
            )
            created += int(added)
            skipped_existing += int(not added)

    return {
        "status": "success",
        "mode": "staging_diff",
        "source_table": "asset_identity_department_sources",
        "scanned": scanned,
        "diffs_created": created,
        "diffs_skipped_existing": skipped_existing,
    }


def _run_identity_person_sync(db: Session, source_system: str, target_system: str) -> dict[str, Any]:
    sources = db.scalars(
        select(IdentityPersonSource).where(IdentityPersonSource.source_system == source_system)
    ).all()
    scanned = len(sources)
    created = 0
    skipped_existing = 0

    for src in sources:
        source_payload = _person_source_payload(src)
        entity_code = src.person_code or src.source_person_id
        match_status = (src.match_status or "").lower()

        if not src.person_code or match_status in {"", "unmatched"}:
            added = _add_identity_diff(
                db,
                source_system=source_system,
                target_system=target_system,
                entity_type="identity_person",
                entity_code=entity_code,
                diff_type="source_unmatched",
                before_data=None,
                after_data=source_payload,
                severity="high" if not src.is_temporary else "low",
            )
            created += int(added)
            skipped_existing += int(not added)
            continue

        person = db.scalar(select(IdentityPerson).where(IdentityPerson.person_code == src.person_code))
        if person is None:
            added = _add_identity_diff(
                db,
                source_system=source_system,
                target_system=target_system,
                entity_type="identity_person",
                entity_code=entity_code,
                diff_type="missing_master_person",
                before_data=None,
                after_data=source_payload,
                severity="high",
            )
            created += int(added)
            skipped_existing += int(not added)
            continue

        changed_fields: dict[str, dict[str, Any]] = {}
        if src.source_person_name and person.person_name_cn and src.source_person_name != person.person_name_cn:
            changed_fields["person_name_cn"] = {
                "master": person.person_name_cn,
                "source": src.source_person_name,
            }
        if src.source_dept_code and person.dept_code and src.source_dept_code != person.dept_code:
            changed_fields["dept_code"] = {
                "master": person.dept_code,
                "source": src.source_dept_code,
            }
        if changed_fields:
            added = _add_identity_diff(
                db,
                source_system=source_system,
                target_system=target_system,
                entity_type="identity_person",
                entity_code=entity_code,
                diff_type="field_mismatch",
                before_data=_person_payload(person),
                after_data={**source_payload, "changed_fields": changed_fields},
                severity="medium",
            )
            created += int(added)
            skipped_existing += int(not added)

    return {
        "status": "success",
        "mode": "staging_diff",
        "source_table": "asset_identity_person_sources",
        "scanned": scanned,
        "diffs_created": created,
        "diffs_skipped_existing": skipped_existing,
    }


def _needs_source_config(entity_type: str) -> dict[str, Any]:
    source_hint = {
        "identity_department": "Load department source records into asset_identity_department_sources before generating diffs.",
        "medical_code": "Configure HIS/EMR code dictionary collectors before generating asset_dict_medical_sync_diffs.",
        "metadata_collect": "Configure metadata collectors per data source before generating metadata snapshots and diffs.",
    }.get(entity_type, "Unsupported sync entity type.")
    return {
        "status": "needs_source_config",
        "mode": "not_started",
        "note": source_hint,
        "diffs_created": 0,
    }


def run_sync(
    source_system: str,
    target_system: str,
    entity_type: str,
    operator: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Run a sync job and persist local audit/diff records.

    Only identity_person has a concrete first-stage implementation because the
    repository already contains a source staging table for person records.
    Other entity types return an actionable configuration status instead of a
    misleading stub result.

    dry_run is honored by the identity_his path (previously hardcoded False);
    audit records are still written so dry-runs remain traceable.
    """
    db = SessionLocal()
    result: dict[str, Any] = {
        "source_system": source_system,
        "target_system": target_system,
        "entity_type": entity_type,
        "dry_run": dry_run,
        "started_at": _now_iso(),
    }
    try:
        if entity_type not in SUPPORTED_ENTITY_TYPES:
            result.update({
                "status": "skipped",
                "note": f"unsupported entity_type: {entity_type}",
                "diffs_created": 0,
            })
        elif entity_type == "identity_person":
            result.update(_run_identity_person_sync(db, source_system, target_system))
        elif entity_type == "identity_department":
            result.update(_run_identity_department_sync(db, source_system, target_system))
        elif entity_type == "identity_his":
            from .his_identity_sync import sync_his_identity
            result.update(sync_his_identity(db, operator=operator, dry_run=dry_run, write_audit=False))
        else:
            result.update(_needs_source_config(entity_type))

        result["finished_at"] = _now_iso()
        _audit_sync(
            db,
            source_system=source_system,
            target_system=target_system,
            entity_type=entity_type,
            result=result,
            operator=operator,
        )
        db.commit()
        return result
    except Exception as exc:
        db.rollback()
        result.update({
            "status": "failed",
            "error": str(exc)[:500],
            "finished_at": _now_iso(),
        })
        _audit_sync(
            db,
            source_system=source_system,
            target_system=target_system,
            entity_type=entity_type,
            result=result,
            operator=operator,
        )
        db.commit()
        return result
    finally:
        db.close()
