"""Daily HIS EmployeeTitle -> JHEMR education_title subtask.

The source is SELECT-only and the target write is limited to one tenant and
one column.  This module intentionally keeps the comparison full-scope: a
dictionary name change must be seen even when SYS_EMPLOYEE.MODIFIEDTIME did
not change.
"""

from __future__ import annotations

from typing import Any

from ..core.config import settings
from .identity_hmac import compute_account_fingerprint
from .identity_sync_audit import AuditWriteError, create_action, finish_action
from .identity_sync_status import error_code_masked, increment_error, short_fingerprint
from .jhemr_identity_adapter import JhemrIdentityAdapter

HOSPITAL_NO = "49557032X"
SUBTASK_CODE = "jhemr_education_title_sync"
SOURCE_MAX_ROWS = 10_000
TARGET_MAX_ROWS = 20_000

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
DICT_SQL = """
SELECT DICT_CODE, DICT_NAME
FROM PORTAL_USER.PORTAL_SYS_DICT
WHERE TYPE_CODE = 'EmployeeTitle'
  AND ROWNUM <= :max_rows
"""


class TitleSyncError(RuntimeError):
    """A fail-closed title subtask error."""


def _connector():
    # Avoid initializing platform SQLAlchemy merely by importing the pure
    # mapping/test surface of this module.
    from .his_identity_sync import _connector as connector_factory

    return connector_factory()


def _text(value: Any) -> str | None:
    value = None if value is None else str(value).strip()
    return value or None


def _value(row: dict[str, Any], key: str) -> Any:
    for candidate in (key, key.upper(), key.lower()):
        if candidate in row:
            return row[candidate]
    return None


def _build_employee_title_map(rows: list[dict[str, Any]]) -> dict[str, str]:
    names_by_code: dict[str, set[str]] = {}
    for row in rows:
        code = _text(_value(row, "DICT_CODE"))
        title = _text(_value(row, "DICT_NAME"))
        if code and title:
            names_by_code.setdefault(code, set()).add(title)
    if any(len(names) > 1 for names in names_by_code.values()):
        raise TitleSyncError("source_dictionary_ambiguous")
    return {code: next(iter(names)) for code, names in names_by_code.items()}


def build_source_map(
    dictionary_rows: list[dict[str, Any]],
    employee_rows: list[dict[str, Any]],
) -> tuple[dict[str, str], dict[str, int]]:
    """Build a unique employee -> dictionary title map without guessing."""
    try:
        title_by_code = _build_employee_title_map(dictionary_rows)
    except Exception as exc:
        raise TitleSyncError("source_dictionary_ambiguous") from exc
    levels: dict[str, set[str]] = {}
    for row in employee_rows:
        employee = _text(_value(row, "EMPLCODE"))
        if not employee:
            continue
        levels.setdefault(employee, set())
        level = _text(_value(row, "LEVLCODE"))
        if level:
            levels[employee].add(level)
    if any(len(codes) > 1 for codes in levels.values()):
        raise TitleSyncError("source_employee_title_ambiguous")
    source: dict[str, str] = {}
    unmapped = 0
    for employee, codes in levels.items():
        code = next(iter(codes), None)
        title = title_by_code.get(code) if code else None
        if title:
            source[employee] = title
        else:
            unmapped += 1
    return source, {
        "dictionary_rows": len(dictionary_rows),
        "dictionary_codes": len(title_by_code),
        "employee_rows": len(employee_rows),
        "unique_employees": len(levels),
        "mapped_employees": len(source),
        "unmapped_employees": unmapped,
    }


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


def _read_source(max_rows: int) -> tuple[dict[str, str], dict[str, int]]:
    his = _connector()
    try:
        count_rows = his.execute_readonly(EMPLOYEE_COUNT_SQL, max_rows=1)
        source_count = int(_value(count_rows[0], "ROW_COUNT") or 0) if count_rows else 0
        if source_count == 0:
            raise TitleSyncError("source_empty")
        if source_count > max_rows:
            raise TitleSyncError("source_row_limit_exceeded")
        employees = his.execute_readonly(EMPLOYEE_SQL, params={"max_rows": max_rows}, max_rows=max_rows)
        if len(employees) != source_count:
            raise TitleSyncError("source_count_mismatch")
        dictionary = his.execute_readonly(DICT_SQL, params={"max_rows": max_rows}, max_rows=max_rows)
    finally:
        his.close()
    source, stats = build_source_map(dictionary, employees)
    if employees and not stats["dictionary_codes"]:
        raise TitleSyncError("source_dictionary_empty")
    return source, stats


def _read_target(adapter: JhemrIdentityAdapter) -> tuple[dict[str, str | None], dict[str, Any]]:
    tenant = settings.identity_sync_jhemr_hospital_no
    count_row = adapter._fetch_one(
        "SELECT COUNT(*) AS row_count FROM jhemr.users WHERE hospital_no = %s", (tenant,)
    ) or {}
    count = int(count_row.get("row_count") or 0)
    if count > TARGET_MAX_ROWS:
        raise TitleSyncError("target_row_limit_exceeded")
    rows = adapter._fetch_all(
        "SELECT user_id, education_title FROM jhemr.users "
        "WHERE hospital_no = %s LIMIT %s", (tenant, TARGET_MAX_ROWS)
    )
    if len(rows) != count:
        raise TitleSyncError("target_count_mismatch")
    target: dict[str, str | None] = {}
    for row in rows:
        user_id = _text(row.get("user_id"))
        if not user_id or user_id in target:
            raise TitleSyncError("target_user_id_ambiguous")
        target[user_id] = _text(row.get("education_title"))
    privilege = adapter._fetch_one(
        "SELECT "
        "has_column_privilege(current_user, 'jhemr.users', 'user_id', 'SELECT') AS can_select_user_id, "
        "has_column_privilege(current_user, 'jhemr.users', 'hospital_no', 'SELECT') AS can_select_hospital_no, "
        "has_column_privilege(current_user, 'jhemr.users', 'education_title', 'SELECT') AS can_select_title, "
        "has_column_privilege(current_user, 'jhemr.users', 'education_title', 'UPDATE') AS can_update_title",
        (),
    ) or {}
    if not all(bool(privilege.get(key)) for key in (
        "can_select_user_id", "can_select_hospital_no", "can_select_title", "can_update_title",
    )):
        raise TitleSyncError("target_privilege_missing")
    length_row = adapter._fetch_one(
        "SELECT character_maximum_length AS max_length FROM information_schema.columns "
        "WHERE table_schema = %s AND table_name = %s AND column_name = %s",
        ("jhemr", "users", "education_title"),
    ) or {}
    max_length = int(length_row.get("max_length") or 0)
    if not max_length:
        raise TitleSyncError("target_title_column_missing")
    return target, {"target_users": count, "max_length": max_length}


def _title_value_fingerprint(user_id: str, title: str) -> str:
    return compute_account_fingerprint(
        f"{user_id}\x1f{title}",
        "JHEMR_TITLE_VALUE",
        settings.identity_hmac_key_ref,
    )


def reconcile_pending_title_actions(
    db,
    source: dict[str, str],
    target: dict[str, str | None],
) -> dict[str, int]:
    """Close prior planned actions only when the committed target is provable.

    A completion-audit outage can leave an action in ``planned`` after the
    separate JHEMR transaction committed. The HMAC value fact lets the next
    read-only comparison prove the exact target value without persisting a
    personnel key or title.
    """
    # Lazy imports preserve the pure-logic test boundary: importing this
    # module must not initialize the platform database engine.
    from sqlalchemy import select
    from ..models.identity_sync import IdentitySyncAction

    rows = list(db.scalars(
        select(IdentitySyncAction).where(
            IdentitySyncAction.subtask_code == SUBTASK_CODE,
            IdentitySyncAction.action_type == "education_title_overwrite",
            IdentitySyncAction.status == "planned",
        ).limit(TARGET_MAX_ROWS)
    ).all())
    if len(rows) >= TARGET_MAX_ROWS:
        raise TitleSyncError("pending_audit_row_limit_exceeded")
    by_account: dict[str, tuple[str, str]] = {}
    for user_id, title in source.items():
        account_fp = compute_account_fingerprint(
            user_id, "JHEMR", settings.identity_hmac_key_ref
        )
        by_account[account_fp] = (user_id, title)
    reconciled = 0
    unresolved = 0
    for row in rows:
        current = by_account.get(str(row.account_fingerprint or ""))
        expected_value_fp = (row.params_summary or {}).get("value_fingerprint")
        if (
            current
            and expected_value_fp
            and target.get(current[0]) == current[1]
            and expected_value_fp == _title_value_fingerprint(current[0], current[1])
        ):
            finish_action(
                db,
                row,
                status="executed",
                rows_affected=1,
                reason_code="reconciled_after_completion_audit_failure",
            )
            reconciled += 1
        else:
            unresolved += 1
    return {"reconciled": reconciled, "unresolved": unresolved}


def sync_jhemr_education_titles_daily(
    *, run_id: str | None, db=None, max_rows: int | None = None,
) -> dict[str, Any]:
    """Run the required daily title subtask with HMAC-only reporting."""
    limit = max(1, min(int(max_rows or SOURCE_MAX_ROWS), SOURCE_MAX_ROWS))
    result: dict[str, Any] = {
        "status": "running", "run_id": run_id, "planned_count": 0,
        "updated": 0, "skipped_equal": 0, "skipped_no_user": 0,
        "failed": 0, "target_committed_pending_audit": 0,
        "error_classes": {}, "failed_fingerprints": [],
    }
    if db is None or not run_id:
        increment_error(result["error_classes"], "audit_config", "MissingAuditContext")
        result["status"] = "misconfigured"
        return result
    try:
        source, source_stats = _read_source(limit)
        result.update({"source": source_stats})
        if not source:
            result["status"] = "success"
            result["reason"] = "no_valid_source_titles"
            return result
    except Exception as exc:
        increment_error(result["error_classes"], "source_select", exc)
        result["status"] = "misconfigured" if isinstance(exc, TitleSyncError) and str(exc) in {"source_empty", "source_row_limit_exceeded", "source_count_mismatch", "source_dictionary_empty", "source_dictionary_ambiguous", "source_employee_title_ambiguous"} else "failed"
        return result

    adapter: JhemrIdentityAdapter | None = None
    try:
        adapter = _adapter()
        adapter.connect()
        target, metadata = _read_target(adapter)
        overlength = [title for title in source.values() if len(title) > metadata["max_length"]]
        if overlength:
            raise TitleSyncError("source_title_too_long")
        reconciliation = reconcile_pending_title_actions(db, source, target)
        result["reconciled_pending_audit"] = reconciliation["reconciled"]
        if reconciliation["unresolved"]:
            raise TitleSyncError("pending_audit_unresolved")
        changes = [(user_id, target[user_id], title) for user_id, title in sorted(source.items()) if user_id in target and target[user_id] != title]
        result["planned_count"] = len(changes)
        result["skipped_equal"] = sum(1 for user_id, title in source.items() if user_id in target and target[user_id] == title)
        result["skipped_no_user"] = sum(1 for user_id in source if user_id not in target)
        actions: list[tuple[str, str, Any]] = []
        try:
            for user_id, _old_title, new_title in changes:
                fingerprint = compute_account_fingerprint(
                    user_id, "JHEMR", settings.identity_hmac_key_ref
                )
                action = create_action(
                    db,
                    run_id=run_id,
                    fingerprint=fingerprint,
                    subtask_code=SUBTASK_CODE,
                    action_type="education_title_overwrite",
                    target_table="jhemr.users",
                    value_fingerprint=_title_value_fingerprint(user_id, new_title),
                )
                if action is None:
                    raise AuditWriteError("action_audit_missing")
                actions.append((user_id, fingerprint, action))
        except AuditWriteError:
            for _user_id, _fingerprint, action in actions:
                try:
                    finish_action(
                        db,
                        action,
                        status="failed",
                        error_class="audit_write",
                        reason_code="planned_batch_aborted_before_target_write",
                    )
                except AuditWriteError:
                    break
            raise

        try:
            batch_result = adapter.update_education_titles_only(changes)
        except Exception as exc:
            result["failed"] = len(changes)
            increment_error(result["error_classes"], "target_write", exc)
            for _user_id, fingerprint, action in actions:
                if len(result["failed_fingerprints"]) < 3:
                    result["failed_fingerprints"].append(short_fingerprint(fingerprint))
                try:
                    finish_action(
                        db,
                        action,
                        status="failed",
                        error_class="target_write",
                        error_code=error_code_masked(exc),
                    )
                except AuditWriteError:
                    increment_error(result["error_classes"], "audit_write", "AuditWriteError")
                    raise
            result["status"] = "failed"
            return result

        result["updated"] = int(batch_result.get("updated") or 0)
        # A row that became equal after the snapshot is still a planned action
        # and is closed as skipped; it is not an update success.
        batch_skipped = int(batch_result.get("skipped") or 0)
        result["skipped_equal"] += batch_skipped
        completion_done = 0
        try:
            for _user_id, _fingerprint, action in actions:
                finish_action(db, action, status="executed", rows_affected=1)
                completion_done += 1
        except AuditWriteError:
            result["target_committed_pending_audit"] = len(actions) - completion_done
            increment_error(
                result["error_classes"],
                "target_committed_pending_audit",
                "AuditWriteError",
            )
            raise
        result["status"] = "success"
    except AuditWriteError:
        increment_error(result["error_classes"], "audit_write", "AuditWriteError")
        result["status"] = "failed"
    except Exception as exc:
        increment_error(result["error_classes"], "target_select_or_metadata", exc)
        result["status"] = "misconfigured" if isinstance(exc, TitleSyncError) else "failed"
    finally:
        if adapter is not None:
            try:
                adapter.close()
            except Exception:
                # The target result is already classified; close failures
                # must not replace it with a raw traceback or expose details.
                increment_error(result["error_classes"], "target_close", "AdapterCloseError")
    return result
