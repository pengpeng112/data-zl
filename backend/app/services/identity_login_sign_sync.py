"""Daily JHEMR login/sign-way reconciliation subtask.

HIS daytime user sync (and new accounts whose ``SYS_EMPLOYEE.MODIFIEDTIME`` is
NULL) can create ``jhemr.users`` without ``users_control_mode`` /
``users_sublogin`` / ``users_subsign``. Empty sign-way rows make the EMR
client refuse login. This subtask is full-scope over the managed clinical
population, like the dept subtask, and is additive-only:

* missing ``users_control_mode`` is inserted with template ``0,2,4``;
* missing login ways ``0/2/4`` and sign ways ``0/2/4`` are inserted;
* ``default_flag=1`` is set on ``sign_way=0`` only when the user currently
  has no default;
* extra existing ways and existing defaults are never deleted or replaced.
"""

from __future__ import annotations

from typing import Any

from ..core.config import settings
from .identity_hmac import compute_account_fingerprint
from .identity_sync_audit import AuditWriteError, create_action, finish_action
from .identity_sync_status import error_code_masked, increment_error, short_fingerprint
from .jhemr_identity_adapter import (
    CONTROL_MODE_DEFAULTS,
    SUBLOGIN_DEFAULTS,
    SUBSIGN_DEFAULTS,
    JhemrIdentityAdapter,
)

SUBTASK_CODE = "jhemr_login_sign_sync"
TARGET_MAX_ROWS = 20_000
EXPECTED_LOGIN_WAYS = tuple(item["login_way"] for item in SUBLOGIN_DEFAULTS)
EXPECTED_SIGN_WAYS = tuple(item["sign_way"] for item in SUBSIGN_DEFAULTS)
FILE_VISIT_TYPE = "2"


class LoginSignSyncError(RuntimeError):
    """A fail-closed login/sign subtask error."""


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


def _read_expected_platform(db) -> set[str]:
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
    expected: set[str] = set()
    for person in persons:
        emp = _text(person.person_code)
        if not emp or emp in protected or _conflict_flag_set(person.conflict_flag):
            continue
        primary, _additionals = _get_person_depts(db, emp, person.classification)
        if not primary:
            continue
        expected.add(emp)
    return expected


def _read_target(adapter: JhemrIdentityAdapter) -> dict[str, Any]:
    tenant = settings.identity_sync_jhemr_hospital_no
    count_row = adapter._fetch_one(
        "SELECT COUNT(*) AS row_count FROM jhemr.users WHERE hospital_no = %s", (tenant,)
    ) or {}
    user_count = int(count_row.get("row_count") or 0)
    if user_count > TARGET_MAX_ROWS:
        raise LoginSignSyncError("target_row_limit_exceeded")
    user_rows = adapter._fetch_all(
        "SELECT user_id FROM jhemr.users WHERE hospital_no = %s LIMIT %s",
        (tenant, TARGET_MAX_ROWS),
    )
    if len(user_rows) != user_count:
        raise LoginSignSyncError("target_count_mismatch")
    target_users: set[str] = set()
    for row in user_rows:
        user_id = _text(row.get("user_id"))
        if not user_id or user_id in target_users:
            raise LoginSignSyncError("target_user_id_ambiguous")
        target_users.add(user_id)

    control_rows = adapter._fetch_all(
        "SELECT user_id FROM jhemr.users_control_mode WHERE hospital_no = %s LIMIT %s",
        (tenant, TARGET_MAX_ROWS),
    )
    control_users = {_text(r.get("user_id")) for r in control_rows}
    control_users.discard(None)

    login_rows = adapter._fetch_all(
        "SELECT user_id, login_way FROM jhemr.users_sublogin "
        "WHERE hospital_no = %s AND file_visit_type = %s LIMIT %s",
        (tenant, FILE_VISIT_TYPE, TARGET_MAX_ROWS),
    )
    logins: dict[str, set[str]] = {}
    for row in login_rows:
        user_id = _text(row.get("user_id"))
        way = _text(row.get("login_way"))
        if not user_id or way is None:
            continue
        logins.setdefault(user_id, set()).add(way)

    sign_rows = adapter._fetch_all(
        "SELECT user_id, sign_way, default_flag FROM jhemr.users_subsign "
        "WHERE hospital_no = %s AND file_visit_type = %s LIMIT %s",
        (tenant, FILE_VISIT_TYPE, TARGET_MAX_ROWS),
    )
    signs: dict[str, set[str]] = {}
    defaults: dict[str, int] = {}
    for row in sign_rows:
        user_id = _text(row.get("user_id"))
        way = _text(row.get("sign_way"))
        if not user_id or way is None:
            continue
        signs.setdefault(user_id, set()).add(way)
        if str(row.get("default_flag")) == "1":
            defaults[user_id] = defaults.get(user_id, 0) + 1

    privilege = adapter._fetch_one(
        "SELECT "
        "has_table_privilege(current_user, 'jhemr.users_control_mode', 'SELECT') AS can_select_control, "
        "has_table_privilege(current_user, 'jhemr.users_control_mode', 'INSERT') AS can_insert_control, "
        "has_table_privilege(current_user, 'jhemr.users_sublogin', 'SELECT') AS can_select_sublogin, "
        "has_table_privilege(current_user, 'jhemr.users_sublogin', 'INSERT') AS can_insert_sublogin, "
        "has_table_privilege(current_user, 'jhemr.users_subsign', 'SELECT') AS can_select_subsign, "
        "has_table_privilege(current_user, 'jhemr.users_subsign', 'INSERT') AS can_insert_subsign, "
        "has_column_privilege(current_user, 'jhemr.users_subsign', 'default_flag', 'UPDATE') AS can_update_default",
        (),
    ) or {}
    if not all(bool(privilege.get(key)) for key in (
        "can_select_control", "can_insert_control",
        "can_select_sublogin", "can_insert_sublogin",
        "can_select_subsign", "can_insert_subsign",
        "can_update_default",
    )):
        raise LoginSignSyncError("target_privilege_missing")
    return {
        "users": target_users,
        "control": control_users,
        "logins": logins,
        "signs": signs,
        "defaults": defaults,
        "metadata": {
            "target_users": user_count,
            "control_rows": len(control_rows),
            "sublogin_rows": len(login_rows),
            "subsign_rows": len(sign_rows),
        },
    }


def build_login_sign_plan(
    expected: set[str],
    target_users: set[str],
    control_users: set[str],
    logins: dict[str, set[str]],
    signs: dict[str, set[str]],
    defaults: dict[str, int],
) -> dict[str, Any]:
    """Pure comparison: insert missing 0/2/4 rows; repair missing default only."""
    repairs: list[dict[str, Any]] = []
    skipped_equal = 0
    skipped_no_user = 0
    expected_logins = set(EXPECTED_LOGIN_WAYS)
    expected_signs = set(EXPECTED_SIGN_WAYS)
    sign_defaults = {item["sign_way"]: item for item in SUBSIGN_DEFAULTS}

    for emp in sorted(expected):
        if emp not in target_users:
            skipped_no_user += 1
            continue
        insert_control = emp not in control_users
        missing_logins = sorted(expected_logins - logins.get(emp, set()))
        existing_signs = signs.get(emp, set())
        missing_sign_ways = [way for way in EXPECTED_SIGN_WAYS if way not in existing_signs]
        has_default = int(defaults.get(emp, 0)) >= 1
        sign_way_items = []
        for way in missing_sign_ways:
            template = dict(sign_defaults[way])
            if way == "0":
                template["default_flag"] = "0" if has_default else "1"
                if template["default_flag"] == "1":
                    has_default = True
            else:
                template["default_flag"] = "0"
            sign_way_items.append({
                "sign_way": template["sign_way"],
                "picmode": template.get("picmode", "2"),
                "default_flag": template["default_flag"],
            })
        fix_default = not has_default and "0" in existing_signs
        if not insert_control and not missing_logins and not sign_way_items and not fix_default:
            skipped_equal += 1
            continue
        repairs.append({
            "user_id": emp,
            "insert_control": insert_control,
            "login_ways": missing_logins,
            "sign_ways": sign_way_items,
            "fix_default": fix_default,
        })
    return {
        "repairs": repairs,
        "skipped_equal": skipped_equal,
        "skipped_no_user": skipped_no_user,
        "template": {
            "control": CONTROL_MODE_DEFAULTS,
            "login_ways": list(EXPECTED_LOGIN_WAYS),
            "sign_ways": list(EXPECTED_SIGN_WAYS),
        },
    }


def _value_fingerprint(user_id: str, kind: str) -> str:
    return compute_account_fingerprint(
        f"{user_id}\x1f{kind}", "JHEMR_LOGIN_SIGN", settings.identity_hmac_key_ref,
    )


def reconcile_pending_login_sign_actions(
    db,
    expected: set[str],
    target_users: set[str],
    control_users: set[str],
    logins: dict[str, set[str]],
    signs: dict[str, set[str]],
    defaults: dict[str, int],
) -> dict[str, int]:
    from sqlalchemy import select
    from ..models.identity_sync import IdentitySyncAction

    rows = list(db.scalars(
        select(IdentitySyncAction).where(
            IdentitySyncAction.subtask_code == SUBTASK_CODE,
            IdentitySyncAction.action_type == "login_sign_fill",
            IdentitySyncAction.status == "planned",
        ).limit(TARGET_MAX_ROWS)
    ).all())
    reconciled = 0
    unresolved = 0
    expected_logins = set(EXPECTED_LOGIN_WAYS)
    expected_signs = set(EXPECTED_SIGN_WAYS)
    for row in rows:
        emp = _text(row.emp_no_masked)
        if not emp or emp not in expected or emp not in target_users:
            unresolved += 1
            continue
        complete = (
            emp in control_users
            and expected_logins.issubset(logins.get(emp, set()))
            and expected_signs.issubset(signs.get(emp, set()))
            and int(defaults.get(emp, 0)) >= 1
        )
        if complete:
            finish_action(db, row, status="executed", rows_affected=1, reason_code="target_already_complete")
            reconciled += 1
        else:
            unresolved += 1
    return {"reconciled": reconciled, "unresolved": unresolved}


def sync_jhemr_login_sign_daily(
    *, run_id: str | None, db=None, plan_only: bool = False,
) -> dict[str, Any]:
    """Run the required daily login/sign-way fill with HMAC-only reporting."""
    result: dict[str, Any] = {
        "status": "running", "run_id": run_id, "planned_count": 0,
        "control_inserted": 0, "sublogin_inserted": 0, "subsign_inserted": 0,
        "default_repaired": 0,
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
        target = _read_target(adapter)
        result["target"] = target["metadata"]
        reconciliation = reconcile_pending_login_sign_actions(
            db, expected, target["users"], target["control"],
            target["logins"], target["signs"], target["defaults"],
        )
        result["reconciled_pending_audit"] = reconciliation["reconciled"]
        if reconciliation["unresolved"]:
            raise LoginSignSyncError("pending_audit_unresolved")
        plan = build_login_sign_plan(
            expected, target["users"], target["control"],
            target["logins"], target["signs"], target["defaults"],
        )
        repairs = plan["repairs"]
        result["planned_count"] = len(repairs)
        result["skipped_equal"] = plan["skipped_equal"]
        result["skipped_no_user"] = plan["skipped_no_user"]
        result["plan"] = {
            "repairs": len(repairs),
            "insert_control": sum(1 for item in repairs if item["insert_control"]),
            "fix_default": sum(1 for item in repairs if item["fix_default"]),
        }
        if plan_only or not repairs:
            result["status"] = "success"
            result["reason"] = "plan_only" if plan_only and repairs else "no_changes"
            return result

        actions: list[tuple[str, str, Any]] = []
        try:
            for item in repairs:
                emp = item["user_id"]
                fingerprint = compute_account_fingerprint(emp, "JHEMR", settings.identity_hmac_key_ref)
                action = create_action(
                    db, run_id=run_id, fingerprint=fingerprint,
                    subtask_code=SUBTASK_CODE, action_type="login_sign_fill",
                    target_table="jhemr.users_subsign",
                    value_fingerprint=_value_fingerprint(emp, "fill"),
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
            batch_result = adapter.apply_login_sign_gaps(repairs)
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

        result["control_inserted"] = int(batch_result.get("control_inserted") or 0)
        result["sublogin_inserted"] = int(batch_result.get("sublogin_inserted") or 0)
        result["subsign_inserted"] = int(batch_result.get("subsign_inserted") or 0)
        result["default_repaired"] = int(batch_result.get("default_repaired") or 0)
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
        result["status"] = "misconfigured" if isinstance(exc, LoginSignSyncError) else "failed"
    finally:
        if adapter is not None:
            try:
                adapter.close()
            except Exception:
                increment_error(result["error_classes"], "target_close", "AdapterCloseError")
    return result
