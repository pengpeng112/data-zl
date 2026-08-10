"""Synchronize HIS employee-title dictionary names to JHEMR users.

Dry-run is the default.  ``--prepare-backup`` exports the exact changed rows
to a mode-0600 JSON file without writing JHEMR.  ``--apply`` requires that
backup plus its SHA-256 digest and fails closed when source or target changed.

HIS is always SELECT-only.  The only target DML is the parameterized update of
``jhemr.users.education_title`` for tenant ``49557032X``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.services.identity_hmac import compute_account_fingerprint
from app.services.jhemr_identity_adapter import JhemrIdentityAdapter


HOSPITAL_NO = "49557032X"
SUBTASK_CODE = "jhemr_education_title_sync"
SOURCE_MAX_ROWS = 10_000
TARGET_MAX_ROWS = 20_000

DICT_SQL = """
SELECT DICT_CODE, DICT_NAME
FROM PORTAL_USER.PORTAL_SYS_DICT
WHERE TYPE_CODE = 'EmployeeTitle'
  AND ROWNUM <= :max_rows
"""

EMPLOYEE_COUNT_SQL = """
SELECT COUNT(*) AS ROW_COUNT
FROM FXHIS.SYS_EMPLOYEE
WHERE EMPLCODE IS NOT NULL
"""

EMPLOYEE_SQL = """
SELECT EMPLCODE, LEVLCODE
FROM FXHIS.SYS_EMPLOYEE
WHERE EMPLCODE IS NOT NULL
  AND ROWNUM <= :max_rows
"""


class TitleSyncError(RuntimeError):
    """Fail-closed title synchronization error."""


@dataclass(frozen=True)
class Change:
    user_id: str
    old_title: str | None
    new_title: str
    fingerprint: str


def _text(value: Any) -> str | None:
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _value(row: dict[str, Any], key: str) -> Any:
    for candidate in (key, key.upper(), key.lower()):
        if candidate in row:
            return row[candidate]
    return None


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


def _build_source_map(
    dictionary_rows: list[dict[str, Any]],
    employee_rows: list[dict[str, Any]],
) -> tuple[dict[str, str], dict[str, int]]:
    titles_by_code: dict[str, set[str]] = {}
    for row in dictionary_rows:
        code = _text(_value(row, "DICT_CODE"))
        title = _text(_value(row, "DICT_NAME"))
        if code and title:
            titles_by_code.setdefault(code, set()).add(title)
    ambiguous_codes = [code for code, titles in titles_by_code.items() if len(titles) > 1]
    if ambiguous_codes:
        raise TitleSyncError(
            f"source_dictionary_ambiguous:{len(ambiguous_codes)}"
        )
    title_by_code = {code: next(iter(titles)) for code, titles in titles_by_code.items()}

    levels_by_employee: dict[str, set[str]] = {}
    rows_by_employee: dict[str, int] = {}
    for row in employee_rows:
        employee = _text(_value(row, "EMPLCODE"))
        if not employee:
            continue
        rows_by_employee[employee] = rows_by_employee.get(employee, 0) + 1
        level = _text(_value(row, "LEVLCODE"))
        if level:
            levels_by_employee.setdefault(employee, set()).add(level)
        else:
            levels_by_employee.setdefault(employee, set())
    ambiguous_employees = [
        employee for employee, levels in levels_by_employee.items() if len(levels) > 1
    ]
    if ambiguous_employees:
        raise TitleSyncError(
            f"source_employee_title_ambiguous:{len(ambiguous_employees)}"
        )

    source: dict[str, str] = {}
    unmapped = 0
    for employee, levels in levels_by_employee.items():
        level = next(iter(levels)) if levels else None
        title = title_by_code.get(level) if level else None
        if title:
            source[employee] = title
        else:
            # Missing dictionary values never clear an existing target title.
            unmapped += 1
    stats = {
        "dictionary_rows": len(dictionary_rows),
        "dictionary_codes": len(title_by_code),
        "employee_rows": len(employee_rows),
        "unique_employees": len(levels_by_employee),
        "duplicate_employee_rows": sum(max(0, count - 1) for count in rows_by_employee.values()),
        "mapped_employees": len(source),
        "unmapped_employees": unmapped,
    }
    return source, stats


def _load_source() -> tuple[dict[str, str], dict[str, int]]:
    from app.services.his_identity_sync import _connector

    connector = _connector()
    try:
        count_rows = connector.execute_readonly(
            EMPLOYEE_COUNT_SQL,
            max_rows=1,
        )
        source_count = int(_value(count_rows[0], "ROW_COUNT") or 0) if count_rows else 0
        if source_count > SOURCE_MAX_ROWS:
            raise TitleSyncError(
                f"source_row_limit_exceeded:{source_count}>{SOURCE_MAX_ROWS}"
            )
        dictionary_rows = connector.execute_readonly(
            DICT_SQL,
            params={"max_rows": SOURCE_MAX_ROWS},
            max_rows=SOURCE_MAX_ROWS,
        )
        employee_rows = connector.execute_readonly(
            EMPLOYEE_SQL,
            params={"max_rows": SOURCE_MAX_ROWS},
            max_rows=SOURCE_MAX_ROWS,
        )
    finally:
        connector.close()
    source, stats = _build_source_map(dictionary_rows, employee_rows)
    if stats["employee_rows"] != source_count:
        raise TitleSyncError(
            f"source_count_mismatch:{stats['employee_rows']}!={source_count}"
        )
    return source, stats


def _adapter() -> JhemrIdentityAdapter:
    return JhemrIdentityAdapter(
        credential_ref=settings.identity_sync_jhemr_credential_ref,
        hospital_no=settings.identity_sync_jhemr_hospital_no,
        jump_host=settings.his_source_jump_host,
        jump_port=settings.his_source_jump_port,
        jump_user=settings.his_source_jump_user,
        jump_key=settings.his_source_jump_key or None,
        db_host=settings.identity_sync_jhemr_host,
        db_port=settings.identity_sync_jhemr_port,
        db_name=settings.identity_sync_jhemr_dbname,
    )


def _load_target(adapter: JhemrIdentityAdapter) -> tuple[dict[str, str | None], dict[str, Any]]:
    count_row = adapter._fetch_one(
        "SELECT COUNT(*) AS row_count FROM jhemr.users WHERE hospital_no = %s",
        (HOSPITAL_NO,),
    )
    target_count = int((count_row or {}).get("row_count") or 0)
    if target_count > TARGET_MAX_ROWS:
        raise TitleSyncError(
            f"target_row_limit_exceeded:{target_count}>{TARGET_MAX_ROWS}"
        )
    rows = adapter._fetch_all(
        "SELECT user_id, education_title FROM jhemr.users "
        "WHERE hospital_no = %s LIMIT %s",
        (HOSPITAL_NO, TARGET_MAX_ROWS),
    )
    if len(rows) != target_count:
        raise TitleSyncError(f"target_count_mismatch:{len(rows)}!={target_count}")

    target: dict[str, str | None] = {}
    duplicates = 0
    for row in rows:
        user_id = _text(row.get("user_id"))
        if not user_id:
            continue
        if user_id in target:
            duplicates += 1
            continue
        target[user_id] = _text(row.get("education_title"))
    if duplicates:
        raise TitleSyncError(f"target_user_id_ambiguous:{duplicates}")

    privilege = adapter._fetch_one(
        "SELECT "
        "has_column_privilege(current_user, 'jhemr.users', 'user_id', 'SELECT') AS can_select_user_id, "
        "has_column_privilege(current_user, 'jhemr.users', 'hospital_no', 'SELECT') AS can_select_hospital_no, "
        "has_column_privilege(current_user, 'jhemr.users', 'education_title', 'SELECT') AS can_select_title, "
        "has_column_privilege(current_user, 'jhemr.users', 'education_title', 'UPDATE') AS can_update_title",
        (),
    ) or {}
    max_length_row = adapter._fetch_one(
        "SELECT character_maximum_length AS max_length "
        "FROM information_schema.columns "
        "WHERE table_schema = %s AND table_name = %s AND column_name = %s",
        ("jhemr", "users", "education_title"),
    ) or {}
    max_length = int(max_length_row.get("max_length") or 0)
    if not max_length:
        raise TitleSyncError("target_education_title_column_missing")
    metadata = {
        "target_users": target_count,
        "max_length": max_length,
        "can_select_user_id": bool(privilege.get("can_select_user_id")),
        "can_select_hospital_no": bool(privilege.get("can_select_hospital_no")),
        "can_select_title": bool(privilege.get("can_select_title")),
        "can_update_title": bool(privilege.get("can_update_title")),
    }
    return target, metadata


def _build_changes(
    source: dict[str, str],
    target: dict[str, str | None],
    max_length: int,
) -> tuple[list[Change], dict[str, int]]:
    overlength = sum(1 for title in source.values() if len(title) > max_length)
    if overlength:
        raise TitleSyncError(f"source_title_too_long:{overlength}")
    changes: list[Change] = []
    matched = 0
    already_equal = 0
    missing_target = 0
    for user_id, title in sorted(source.items()):
        if user_id not in target:
            missing_target += 1
            continue
        matched += 1
        old_title = target[user_id]
        if old_title == title:
            already_equal += 1
            continue
        fingerprint = compute_account_fingerprint(
            user_id, "JHEMR", settings.identity_hmac_key_ref
        )
        changes.append(Change(user_id, old_title, title, fingerprint))
    return changes, {
        "matched_target_users": matched,
        "already_equal": already_equal,
        "missing_target_users": missing_target,
        "changed_users": len(changes),
        "overlength_titles": overlength,
    }


def _backup_payload(changes: list[Change]) -> dict[str, Any]:
    return {
        "version": 1,
        "hospital_no": HOSPITAL_NO,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "records": [
            {
                "user_id": row.user_id,
                "old_title": row.old_title,
                "new_title": row.new_title,
            }
            for row in changes
        ],
    }


def _write_backup(path: Path, changes: list[Change]) -> str:
    if path.exists():
        raise TitleSyncError("backup_file_already_exists")
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    payload = _backup_payload(changes)
    raw = _canonical_json(payload)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
    except Exception:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    os.chmod(path, 0o600)
    return _sha256_bytes(raw)


def _load_and_verify_backup(
    path: Path,
    expected_sha256: str,
    changes: list[Change],
) -> None:
    raw = path.read_bytes()
    actual_sha256 = _sha256_bytes(raw)
    if actual_sha256 != expected_sha256:
        raise TitleSyncError("backup_digest_mismatch")
    payload = json.loads(raw.decode("utf-8"))
    if payload.get("hospital_no") != HOSPITAL_NO:
        raise TitleSyncError("backup_tenant_mismatch")
    expected_records = [
        {"user_id": row.user_id, "old_title": row.old_title, "new_title": row.new_title}
        for row in changes
    ]
    if payload.get("records") != expected_records:
        raise TitleSyncError("backup_no_longer_matches_current_plan")


def _create_planned_audit(run_id: str, changes: list[Change]) -> tuple[Any, list[Any]]:
    from app.core.db import SessionLocal
    from app.models.identity_sync import (
        IdentitySchedulerRun,
        IdentitySyncAction,
        IdentitySyncSubtask,
    )

    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        run = IdentitySchedulerRun(
            run_id=run_id,
            triggered_by="manual_authorized_title_sync",
            status="running",
            started_at=now,
            candidates_total=len(changes),
            candidates_update=len(changes),
            provider_code="manual_authorized",
            report_summary={
                "subtask": SUBTASK_CODE,
                "field": "education_title",
                "planned_count": len(changes),
            },
        )
        subtask = IdentitySyncSubtask(
            run_id=run_id,
            subtask_code=SUBTASK_CODE,
            target_system="JHEMR",
            status="running",
            planned_count=len(changes),
            started_at=now,
            report_summary={"field": "education_title", "overwrite_existing": True},
        )
        actions = [
            IdentitySyncAction(
                batch_id=run_id,
                action_seq=index,
                target_system="JHEMR",
                action_type="education_title_overwrite",
                target_table="jhemr.users",
                account_fingerprint=row.fingerprint,
                params_summary={
                    "field": "education_title",
                    "source": "HIS.EmployeeTitle",
                    "tenant_scoped": True,
                },
                status="planned",
                subtask_code=SUBTASK_CODE,
            )
            for index, row in enumerate(changes, start=1)
        ]
        db.add(run)
        db.add(subtask)
        db.add_all(actions)
        db.commit()
        return db, actions
    except Exception:
        db.rollback()
        db.close()
        raise


def _finish_audit(
    db: Any,
    actions: list[Any],
    run_id: str,
    *,
    status: str,
    succeeded: int,
    failed: int,
    error_class: str | None = None,
) -> None:
    from sqlalchemy import select

    from app.models.identity_sync import (
        IdentitySchedulerRun,
        IdentitySyncAlert,
        IdentitySyncSubtask,
    )

    now = datetime.now(timezone.utc)
    run = db.scalar(select(IdentitySchedulerRun).where(IdentitySchedulerRun.run_id == run_id))
    subtask = db.scalar(select(IdentitySyncSubtask).where(
        IdentitySyncSubtask.run_id == run_id,
        IdentitySyncSubtask.subtask_code == SUBTASK_CODE,
    ))
    if run is None or subtask is None:
        raise TitleSyncError("audit_run_or_subtask_missing")
    for action in actions:
        action.status = "executed" if status == "success" else "rolled_back"
        action.rows_affected = 1 if status == "success" else 0
        action.error_class = error_class
        action.executed_at = now
    run.status = status
    run.success_count = succeeded
    run.failed_count = failed
    run.finished_at = now
    run.last_error_class = error_class
    run.report_summary = {
        "subtask": SUBTASK_CODE,
        "field": "education_title",
        "planned_count": len(actions),
        "succeeded_count": succeeded,
        "failed_count": failed,
    }
    subtask.status = status
    subtask.succeeded_count = succeeded
    subtask.failed_count = failed
    subtask.error_classes = {error_class: failed} if error_class else {}
    subtask.finished_at = now
    subtask.report_summary = {
        "field": "education_title",
        "overwrite_existing": True,
        "succeeded_count": succeeded,
        "failed_count": failed,
    }
    if status != "success":
        db.add(IdentitySyncAlert(
            run_id=run_id,
            alert_type="failed",
            severity="error",
            error_class=error_class,
            occurrence_count=max(1, failed),
            detail={"subtask": SUBTASK_CODE, "field": "education_title"},
        ))
    db.commit()


def _apply_changes(adapter: JhemrIdentityAdapter, changes: list[Change]) -> None:
    conn = adapter._ensure_conn()
    try:
        for row in changes:
            current = adapter._fetch_one(
                "SELECT education_title FROM jhemr.users "
                "WHERE user_id = %s AND hospital_no = %s FOR UPDATE",
                (row.user_id, HOSPITAL_NO),
            )
            if current is None or _text(current.get("education_title")) != row.old_title:
                raise TitleSyncError("target_changed_after_backup")
            affected = adapter._execute_write(
                "UPDATE jhemr.users SET education_title = %s "
                "WHERE user_id = %s AND hospital_no = %s",
                (row.new_title, row.user_id, HOSPITAL_NO),
            )
            if affected != 1:
                raise TitleSyncError(f"target_update_rowcount:{affected}")
        for row in changes:
            readback = adapter._fetch_one(
                "SELECT education_title FROM jhemr.users "
                "WHERE user_id = %s AND hospital_no = %s",
                (row.user_id, HOSPITAL_NO),
            )
            if readback is None or _text(readback.get("education_title")) != row.new_title:
                raise TitleSyncError("target_readback_mismatch")
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def _summary(
    source_stats: dict[str, int],
    target_meta: dict[str, Any],
    change_stats: dict[str, int],
    changes: list[Change],
) -> dict[str, Any]:
    return {
        "source": source_stats,
        "target": target_meta,
        "comparison": change_stats,
        "sample_fingerprints": [row.fingerprint[:12] for row in changes[:3]],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare-backup", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup-file", type=Path)
    parser.add_argument("--backup-sha256")
    args = parser.parse_args()
    if args.apply and (not args.backup_file or not args.backup_sha256):
        parser.error("--apply requires --backup-file and --backup-sha256")
    if args.apply and args.prepare_backup:
        parser.error("--apply and --prepare-backup are mutually exclusive")

    adapter = _adapter()
    audit_db = None
    run_id = None
    try:
        source, source_stats = _load_source()
        adapter.connect()
        target, target_meta = _load_target(adapter)
        changes, change_stats = _build_changes(source, target, target_meta["max_length"])
        summary = _summary(source_stats, target_meta, change_stats, changes)

        if args.prepare_backup:
            digest = _write_backup(args.prepare_backup, changes)
            print(json.dumps({
                "status": "backup_prepared",
                "backup_sha256": digest,
                **summary,
            }, ensure_ascii=True))
            return 0
        if not args.apply:
            print(json.dumps({"status": "dry_run", **summary}, ensure_ascii=True))
            return 0

        if not target_meta["can_update_title"]:
            raise TitleSyncError("target_update_privilege_missing")
        _load_and_verify_backup(args.backup_file, args.backup_sha256, changes)
        run_id = f"title-{uuid.uuid4().hex}"
        audit_db, actions = _create_planned_audit(run_id, changes)
        try:
            _apply_changes(adapter, changes)
        except Exception as exc:
            _finish_audit(
                audit_db,
                actions,
                run_id,
                status="failed",
                succeeded=0,
                failed=len(changes),
                error_class=type(exc).__name__,
            )
            raise
        _finish_audit(
            audit_db,
            actions,
            run_id,
            status="success",
            succeeded=len(changes),
            failed=0,
        )
        print(json.dumps({
            "status": "success",
            "run_id": run_id,
            **summary,
        }, ensure_ascii=True))
        return 0
    except Exception as exc:
        print(json.dumps({
            "status": "failed",
            "run_id": run_id,
            "error_class": type(exc).__name__,
            "error_category": str(exc).split(":", 1)[0][:80],
        }, ensure_ascii=True))
        return 1
    finally:
        if audit_db is not None:
            audit_db.close()
        adapter.close()


if __name__ == "__main__":
    sys.exit(main())
