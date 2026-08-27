"""Daily JHEMR user-dept reconciliation subtask (multi-department sync).

Closes the plan-107 gap where a HIS ``COMM.STAFF_VS_GROUP`` change alone does
not bump ``SYS_EMPLOYEE.MODIFIEDTIME``, so the person never re-enters the
nightly candidate set and the new ward group never reaches JHEMR
``user_dept``.  Like the title subtask, the comparison is full-scope over the
managed population and the target write is additive-only:

* missing ``jhemr.user_dept`` rows are inserted (``default_dept_flag=0``);
* a changed HIS primary department updates ``jhemr.users.user_dept`` and
  migrates the single ``default_dept_flag`` row (change-only, verified);
* existing department rows are never deleted (plan 107 §5.4 additive rule).

The expected-side source is the platform identity tables refreshed by the
nightly HIS collection that runs immediately before this subtask.
"""

from __future__ import annotations

from typing import Any

from ..core.config import settings
from .identity_hmac import compute_account_fingerprint
from .identity_sync_audit import AuditWriteError, create_action, finish_action
from .identity_sync_status import error_code_masked, increment_error, short_fingerprint
from .jhemr_identity_adapter import JhemrIdentityAdapter

SUBTASK_CODE = "jhemr_user_dept_sync"
TARGET_MAX_ROWS = 20_000


class DeptSyncError(RuntimeError):
    """A fail-closed dept subtask error."""


def _text(value: Any) -> str | None:
    value = None if value is None else str(value).strip()
    return value or None


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


def _conflict_flag_set(value: Any) -> bool:
    return _text(value) in {"true", "t", "1", "conflict"}


def _read_expected_platform(db) -> dict[str, dict[str, Any]]:
    """Expected dept_codes per managed person from platform identity tables.

    Reuses the orchestrator's own ``_get_person_depts`` so the whitelist
    semantics (primary = SYS_EMPLOYEE authority; additionals only from
    STAFF_VS_GROUP group-class whitelist) stay single-sourced.
    """
    from sqlalchemy import select
    from ..models.identity import IdentityPerson
    from ..models.identity_sync import IdentityProtectedAccount
    from .identity_sync_orchestrator import ELIGIBLE_CLASSIFICATIONS, _get_person_depts

    protected = {r for r in db.scalars(select(IdentityProtectedAccount.account_id)).all() if r}
    persons = db.scalars(
        select(IdentityPerson).where(
            IdentityPerson.employment_status == "active",
            IdentityPerson.classification.in_(sorted(ELIGIBLE_CLASSIFICATIONS)),
        )
    ).all()
    expected: dict[str, dict[str, Any]] = {}
    for person in persons:
        emp = _text(person.person_code)
        if not emp or emp in protected or _conflict_flag_set(person.conflict_flag):
            continue
        primary, additionals = _get_person_depts(db, emp, person.classification)
        if not primary:
            continue
        depts = [primary] + [d for d in additionals if d and d != primary]
        expected[emp] = {"depts": depts, "primary": primary}
    return expected


def _read_target(adapter: JhemrIdentityAdapter) -> tuple[dict[str, str | None], dict[str, set[str]], dict[str, Any]]:
    tenant = settings.identity_sync_jhemr_hospital_no
    count_row = adapter._fetch_one(
        "SELECT COUNT(*) AS row_count FROM jhemr.users WHERE hospital_no = %s", (tenant,)
    ) or {}
    user_count = int(count_row.get("row_count") or 0)
    if user_count > TARGET_MAX_ROWS:
        raise DeptSyncError("target_row_limit_exceeded")
    user_rows = adapter._fetch_all(
        "SELECT user_id, user_dept FROM jhemr.users "
        "WHERE hospital_no = %s LIMIT %s", (tenant, TARGET_MAX_ROWS)
    )
    if len(user_rows) != user_count:
        raise DeptSyncError("target_count_mismatch")
    target_users: dict[str, str | None] = {}
    for row in user_rows:
        user_id = _text(row.get("user_id"))
        if not user_id or user_id in target_users:
            raise DeptSyncError("target_user_id_ambiguous")
        target_users[user_id] = _text(row.get("user_dept"))

    dept_rows = adapter._fetch_all(
        "SELECT user_id, user_dept FROM jhemr.user_dept "
        "WHERE hospital_no = %s LIMIT %s", (tenant, TARGET_MAX_ROWS)
    )
    target_depts: dict[str, set[str]] = {}
    seen_pairs: set[tuple[str, str]] = set()
    for row in dept_rows:
        user_id = _text(row.get("user_id"))
        dept = _text(row.get("user_dept"))
        if not user_id or not dept:
            continue
        if (user_id, dept) in seen_pairs:
            raise DeptSyncError("target_user_dept_ambiguous")
        seen_pairs.add((user_id, dept))
        target_depts.setdefault(user_id, set()).add(dept)

    privilege = adapter._fetch_one(
        "SELECT "
        "has_table_privilege(current_user, 'jhemr.user_dept', 'SELECT') AS can_select_user_dept, "
        "has_table_privilege(current_user, 'jhemr.user_dept', 'INSERT') AS can_insert_user_dept, "
        "has_column_privilege(current_user, 'jhemr.users', 'user_dept', 'UPDATE') AS can_update_primary, "
        "has_column_privilege(current_user, 'jhemr.user_dept', 'default_dept_flag', 'UPDATE') AS can_update_default_flag",
        (),
    ) or {}
    if not all(bool(privilege.get(key)) for key in (
        "can_select_user_dept", "can_insert_user_dept", "can_update_primary", "can_update_default_flag",
    )):
        raise DeptSyncError("target_privilege_missing")
    return target_users, target_depts, {"target_users": user_count, "target_dept_rows": len(dept_rows)}


def build_dept_plan(
    expected: dict[str, dict[str, Any]],
    target_users: dict[str, str | None],
    target_depts: dict[str, set[str]],
) -> dict[str, Any]:
    """Pure comparison: additive dept rows + change-only primary alignment."""
    dept_adds: list[tuple[str, str]] = []
    primary_changes: list[tuple[str, str | None, str]] = []
    skipped_equal = 0
    skipped_no_user = 0
    for emp in sorted(expected):
        info = expected[emp]
        if emp not in target_users:
            skipped_no_user += 1
            continue
        current_primary = target_users[emp]
        actual = target_depts.get(emp, set())
        for dept in info["depts"]:
            if dept not in actual:
                dept_adds.append((emp, dept))
        if current_primary != info["primary"]:
            primary_changes.append((emp, current_primary, info["primary"]))
        if current_primary == info["primary"] and all(d in actual for d in info["depts"]):
            skipped_equal += 1
    return {
        "dept_adds": dept_adds,
        "primary_changes": primary_changes,
        "skipped_equal": skipped_equal,
        "skipped_no_user": skipped_no_user,
    }


def _dept_value_fingerprint(user_id: str, kind: str, value: str) -> str:
    return compute_account_fingerprint(
        f"{user_id}\x1f{kind}\x1f{value}", "JHEMR_DEPT_VALUE", settings.identity_hmac_key_ref,
    )


def _action_type_for(kind: str) -> str:
    return "user_dept_add" if kind == "dept" else "primary_dept_change"


def reconcile_pending_dept_actions(
    db,
    expected: dict[str, dict[str, Any]],
    target_users: dict[str, str | None],
    target_depts: dict[str, set[str]],
) -> dict[str, int]:
    """Close prior planned actions only when the committed target is provable."""
    from sqlalchemy import select
    from ..models.identity_sync import IdentitySyncAction

    rows = list(db.scalars(
        select(IdentitySyncAction).where(
            IdentitySyncAction.subtask_code == SUBTASK_CODE,
            IdentitySyncAction.action_type.in_(["user_dept_add", "primary_dept_change"]),
            IdentitySyncAction.status == "planned",
        ).limit(TARGET_MAX_ROWS)
    ).all())
    if len(rows) >= TARGET_MAX_ROWS:
        raise DeptSyncError("pending_audit_row_limit_exceeded")
    by_account: dict[str, str] = {
        compute_account_fingerprint(emp, "JHEMR", settings.identity_hmac_key_ref): emp
        for emp in expected
    }
    reconciled = 0
    unresolved = 0
    for row in rows:
        emp = by_account.get(str(row.account_fingerprint or ""))
        params = row.params_summary or {}
        kind = params.get("dept_kind")
        value = params.get("dept_value")
        proven = bool(
            emp and kind and value
            and params.get("value_fingerprint") == _dept_value_fingerprint(emp, kind, value)
            and (
                (kind == "dept" and value in target_depts.get(emp, set()))
                or (kind == "primary" and target_users.get(emp) == value)
            )
        )
        if proven:
            finish_action(
                db, row, status="executed", rows_affected=1,
                reason_code="reconciled_after_completion_audit_failure",
            )
            reconciled += 1
        else:
            unresolved += 1
    return {"reconciled": reconciled, "unresolved": unresolved}


def sync_jhemr_user_depts_daily(
    *, run_id: str | None, db=None, plan_only: bool = False,
) -> dict[str, Any]:
    """Run the required daily user-dept subtask with HMAC-only reporting."""
    result: dict[str, Any] = {
        "status": "running", "run_id": run_id, "planned_count": 0,
        "dept_rows_added": 0, "primary_updated": 0,
        "skipped_equal": 0, "skipped_no_user": 0,
        "failed": 0, "target_committed_pending_audit": 0,
        "error_classes": {}, "failed_fingerprints": [],
    }
    if db is None or not run_id:
        increment_error(result["error_classes"], "audit_config", "MissingAuditContext")
        result["status"] = "misconfigured"
        return result
    try:
        expected = _read_expected_platform(db)
        result["source"] = {"managed_persons": len(expected)}
        if not expected:
            result["status"] = "success"
            result["reason"] = "no_managed_persons"
            return result
    except Exception as exc:
        increment_error(result["error_classes"], "source_select", exc)
        result["status"] = "failed"
        return result

    adapter: JhemrIdentityAdapter | None = None
    try:
        adapter = _adapter()
        adapter.connect()
        target_users, target_depts, metadata = _read_target(adapter)
        result["target"] = metadata
        reconciliation = reconcile_pending_dept_actions(db, expected, target_users, target_depts)
        result["reconciled_pending_audit"] = reconciliation["reconciled"]
        if reconciliation["unresolved"]:
            raise DeptSyncError("pending_audit_unresolved")
        plan = build_dept_plan(expected, target_users, target_depts)
        dept_adds = plan["dept_adds"]
        primary_changes = plan["primary_changes"]
        result["planned_count"] = len(dept_adds) + len(primary_changes)
        result["skipped_equal"] = plan["skipped_equal"]
        result["skipped_no_user"] = plan["skipped_no_user"]
        result["plan"] = {"dept_adds": len(dept_adds), "primary_changes": len(primary_changes)}
        if plan_only or (not dept_adds and not primary_changes):
            result["status"] = "success"
            if not dept_adds and not primary_changes:
                result["reason"] = "no_changes"
            elif plan_only:
                result["reason"] = "plan_only"
            return result

        actions: list[tuple[str, str, Any]] = []
        try:
            for emp, dept in dept_adds:
                fingerprint = compute_account_fingerprint(emp, "JHEMR", settings.identity_hmac_key_ref)
                action = create_action(
                    db, run_id=run_id, fingerprint=fingerprint,
                    subtask_code=SUBTASK_CODE, action_type="user_dept_add",
                    target_table="jhemr.user_dept",
                    value_fingerprint=_dept_value_fingerprint(emp, "dept", dept),
                    emp_no=emp,
                )
                if action is None:
                    raise AuditWriteError("action_audit_missing")
                actions.append((emp, fingerprint, action))
            for emp, old_primary, new_primary in primary_changes:
                fingerprint = compute_account_fingerprint(emp, "JHEMR", settings.identity_hmac_key_ref)
                action = create_action(
                    db, run_id=run_id, fingerprint=fingerprint,
                    subtask_code=SUBTASK_CODE, action_type="primary_dept_change",
                    target_table="jhemr.users",
                    value_fingerprint=_dept_value_fingerprint(emp, "primary", new_primary),
                    emp_no=emp,
                )
                if action is None:
                    raise AuditWriteError("action_audit_missing")
                actions.append((emp, fingerprint, action))
        except AuditWriteError:
            for _emp, _fingerprint, action in actions:
                try:
                    finish_action(
                        db, action, status="failed",
                        error_class="audit_write",
                        reason_code="planned_batch_aborted_before_target_write",
                    )
                except AuditWriteError:
                    break
            raise

        try:
            batch_result = adapter.apply_user_dept_changes(
                dept_adds=dept_adds,
                primary_changes=primary_changes,
            )
        except Exception as exc:
            result["failed"] = len(actions)
            increment_error(result["error_classes"], "target_write", exc)
            for _emp, fingerprint, action in actions:
                if len(result["failed_fingerprints"]) < 3:
                    result["failed_fingerprints"].append(short_fingerprint(fingerprint))
                try:
                    finish_action(
                        db, action, status="failed",
                        error_class="target_write",
                        error_code=error_code_masked(exc),
                    )
                except AuditWriteError:
                    increment_error(result["error_classes"], "audit_write", "AuditWriteError")
                    raise
            result["status"] = "failed"
            return result

        result["dept_rows_added"] = int(batch_result.get("dept_rows_added") or 0)
        result["primary_updated"] = int(batch_result.get("primary_updated") or 0)
        completion_done = 0
        try:
            for _emp, _fingerprint, action in actions:
                finish_action(db, action, status="executed", rows_affected=1)
                completion_done += 1
        except AuditWriteError:
            result["target_committed_pending_audit"] = len(actions) - completion_done
            increment_error(result["error_classes"], "target_committed_pending_audit", "AuditWriteError")
            raise
        result["status"] = "success"
    except AuditWriteError:
        increment_error(result["error_classes"], "audit_write", "AuditWriteError")
        result["status"] = "failed"
    except Exception as exc:
        increment_error(result["error_classes"], "target_select_or_metadata", exc)
        result["status"] = "misconfigured" if isinstance(exc, DeptSyncError) else "failed"
    finally:
        if adapter is not None:
            try:
                adapter.close()
            except Exception:
                increment_error(result["error_classes"], "target_close", "AdapterCloseError")
    return result
