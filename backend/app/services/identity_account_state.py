"""HIS dual-source account state decision logic (plan 186 §4.6, I2).

Pure functions only — no DB, no network. Both callers must share these rules:

* ``his_identity_sync`` (the real nightly collection path), and
* ``identity_source_collector`` (the other collection entry).

Rule version ``dual_source_v1`` encodes the user-confirmed semantics:

- ``FXHIS.SYS_USER.STATUS``: ``1`` = 停用 (disabled), ``0`` = 启用 (enabled).
  Direction is OPPOSITE to ``SYS_EMPLOYEE.VALIDSTATE`` (1=有效, 0=停用) —
  the two sources must never share one normalizer.
- ``FXHIS.SYS_EMPLOYEE`` keeps its existing semantics: ``ISDELETED`` flag
  first (any non-{0,N,false} value = deleted), then ``VALIDSTATE``.
- ``SYS_USER.ISDELETED`` = 1 also means disabled (logical delete).
- Missing/unknown values never become enabled; a reliable ``disabled`` from
  either source wins; only both-enabled yields ``enabled`` (§4.6.2 truth
  table, all 9 rows).

P0-10 fail-closed semantics (186 v1.10):

- Scope: only rows with ``TYPE`` exactly ``"1"`` are employee-login accounts.
  NULL/blank/unknown ``TYPE`` is OUT of scope even when ``EMPL_CODE`` exists
  (the old "NULL TYPE stays in scope via EMPL_CODE" branch is deleted —
  an unconfirmed row type must never feed an enable/disable decision).
- Multi-account aggregation: when more than one in-scope row exists for a
  person, any disabled row → ``disabled`` (reason
  ``sys_user_status_disabled_multi``); otherwise the person is
  ``unknown`` (reason ``sys_user_multi_account_unconfirmed``) — an
  unconfirmed multi-account scope never aggregates to ``enabled``.
- Recovery attribution is precise change detection only
  (:func:`target_time_unchanged`): the target-side raw time value must be
  exactly unchanged since our recorded disable. There is NO tolerance and
  NO timezone conversion anywhere in this module; time agreement is not
  proof of lock ownership (ownership evidence lives in the orchestration /
  gate layer).

Employment vs login stay separate: the decision feeds an *account* state and
never touches ``IdentityPerson.employment_status``.

Verified source evidence (2026-09-09, sjzc live aggregate-only probes — see
``开发起步包/output_r186/sys_user_evidence.json``):

- ``FXHIS.SYS_USER`` exists (platform metadata misses it); join key
  ``TRIM(EMPL_CODE) = TRIM(SYS_EMPLOYEE.EMPLCODE)``; EMPL_CODE 100% non-null
  and 100% distinct → strict one-account-per-employee for TYPE=1 rows.
- The single TYPE=100 / USERFLAG='P' row is a platform account outside the
  employee-login scope.
- ``STATUS`` domain is strictly {0,1}; ``MODIFIEDTIME`` is NULL for ~16% of
  rows → unusable as an increment watermark; change discovery must use batch
  state reconciliation (§4.6.3).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable

RULE_VERSION = "dual_source_v1"

# Allowed projection when collecting FXHIS.SYS_USER. PASSWORD & friends are
# physically excluded from the SELECT list — never SELECT *.
SYS_USER_TABLE = "FXHIS.SYS_USER"
SYS_USER_ALLOWED_COLUMNS = ("EMPL_CODE", "STATUS", "ISDELETED", "TYPE", "MODIFIEDTIME")
# TYPE=100/USERFLAG='P' is the platform account (out of employee scope).
SYS_USER_EMPLOYEE_TYPE = "1"

STATE_ENABLED = "enabled"
STATE_DISABLED = "disabled"
STATE_UNKNOWN = "unknown"

# How a person's accounts aggregate when more than one in-scope row exists
# (defensive: live evidence says 1:1, but a future data change must fail
# toward the conservative side, never "take the first row").
ACTION_DISABLE = "disable"
ACTION_ENABLE = "enable"


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _deleted_flag_is_set(value: Any) -> bool:
    """ISDELETED semantics shared by both sources (existing regression kept):
    None/''/0/N/False-ish = not deleted; anything else = deleted."""
    if value is None:
        return False
    return str(value).strip() not in {"", "0", "N", "False", "false"}


def normalize_employee_state(row: dict[str, Any] | None) -> str:
    """SYS_EMPLOYEE → enabled/disabled/unknown (VALIDSTATE 1=有效, 0=停用)."""
    if row is None:
        return STATE_UNKNOWN
    if _deleted_flag_is_set(row.get("ISDELETED")):
        return STATE_DISABLED
    text = (_text(row.get("VALIDSTATE")) or "").upper()
    if text == "1":
        return STATE_ENABLED
    if text == "0":
        return STATE_DISABLED
    return STATE_UNKNOWN


def normalize_sys_user_row(row: dict[str, Any]) -> str | None:
    """Single SYS_USER row → enabled/disabled/unknown.

    STATUS: 0=enabled, 1=disabled (user-confirmed, opposite of VALIDSTATE).
    ISDELETED=1 → disabled. NULL/blank/unknown codes → unknown (never bool-
    coerced into enabled).
    """
    if _deleted_flag_is_set(row.get("ISDELETED")):
        return STATE_DISABLED
    text = (_text(row.get("STATUS")) or "").upper()
    if text == "0":
        return STATE_ENABLED
    if text == "1":
        return STATE_DISABLED
    return STATE_UNKNOWN


def sys_user_row_in_scope(row: dict[str, Any]) -> bool:
    """Employee-login accounts only (TYPE exactly '1'). Fail-closed (P0-10).

    The TYPE=100/USERFLAG='P' platform account is out of scope for
    per-person enable/disable decisions. A NULL/blank/unknown TYPE has no
    confirmed meaning either — it is OUT of scope even when EMPL_CODE
    exists; the previous EMPL_CODE fallback could feed an unconfirmed row
    type into an enable decision.
    """
    type_text = _text(row.get("TYPE"))
    return type_text == SYS_USER_EMPLOYEE_TYPE


def aggregate_user_state(rows: Iterable[dict[str, Any]]) -> tuple[str, str]:
    """Aggregate a person's in-scope SYS_USER rows (§4.6.2 item 2, P0-10).

    Single in-scope row (verified live scope is 1:1): the row's normalized
    state with its reason. Multiple in-scope rows (defensive against future
    data change): any disabled → ``disabled``/``sys_user_status_disabled_multi``;
    otherwise ``unknown``/``sys_user_multi_account_unconfirmed`` — an
    unconfirmed multi-account scope is never aggregated into ``enabled`` and
    never resolved by "take the first row".
    """
    in_scope = [row for row in rows if sys_user_row_in_scope(row)]
    if not in_scope:
        return STATE_UNKNOWN, "sys_user_missing_or_out_of_scope"
    states = [normalize_sys_user_row(row) for row in in_scope]
    if len(states) > 1:
        if any(state == STATE_DISABLED for state in states):
            return STATE_DISABLED, "sys_user_status_disabled_multi"
        return STATE_UNKNOWN, "sys_user_multi_account_unconfirmed"
    if states[0] == STATE_DISABLED:
        return STATE_DISABLED, "sys_user_status_disabled"
    if states[0] == STATE_ENABLED:
        return STATE_ENABLED, "sys_user_status_enabled"
    return STATE_UNKNOWN, "sys_user_status_unknown_or_mixed"


@dataclass(frozen=True)
class AccountStateDecision:
    """One person's dual-source decision (§4.6.2 truth table)."""

    person_code: str
    employee_state: str
    user_state: str
    desired_state: str
    decision_reason: str
    employee_evidence: dict[str, Any] = field(default_factory=dict)
    user_evidence: dict[str, Any] = field(default_factory=dict)
    blocked_reason: str | None = None

    @property
    def execution_allowed(self) -> bool:
        # Only unambiguous outcomes may act. unknown → blocked (neither
        # enable nor disable). desired==enabled needs both sources enabled,
        # which the combine step already guarantees.
        return self.desired_state in (STATE_ENABLED, STATE_DISABLED) and not self.blocked_reason


def combine_account_state(
    person_code: str,
    employee_row: dict[str, Any] | None,
    sys_user_rows: Iterable[dict[str, Any]],
) -> AccountStateDecision:
    """§4.6.2 truth table, all nine rows:

    enabled+enabled→enabled; any disabled→disabled (incl. disabled+unknown);
    enabled+unknown / unknown+enabled / unknown+unknown → unknown.
    """
    rows = list(sys_user_rows)
    employee_state = normalize_employee_state(employee_row)
    user_state, user_reason = aggregate_user_state(rows)

    if employee_state == STATE_DISABLED or user_state == STATE_DISABLED:
        desired = STATE_DISABLED
        reason = (
            f"employee_{employee_state}+user_{user_state}"
            if employee_state == STATE_DISABLED and user_state == STATE_DISABLED
            else f"employee_{employee_state}" if employee_state == STATE_DISABLED else f"user_{user_state}"
        )
    elif employee_state == STATE_ENABLED and user_state == STATE_ENABLED:
        desired = STATE_ENABLED
        reason = "employee_enabled+user_enabled"
    else:
        desired = STATE_UNKNOWN
        reason = f"employee_{employee_state}+user_{user_state}"

    return AccountStateDecision(
        person_code=person_code,
        employee_state=employee_state,
        user_state=user_state,
        desired_state=desired,
        decision_reason=reason,
        employee_evidence={
            "source_table": "FXHIS.SYS_EMPLOYEE",
            "state": employee_state,
            "validstate": _text(employee_row.get("VALIDSTATE")) if employee_row else None,
            "isdeleted": _text(employee_row.get("ISDELETED")) if employee_row else None,
        } if employee_row else {"source_table": "FXHIS.SYS_EMPLOYEE", "state": STATE_UNKNOWN, "row_missing": True},
        user_evidence={
            "source_table": SYS_USER_TABLE,
            "state": user_state,
            "reason": user_reason,
            "in_scope_rows": sum(1 for r in rows if sys_user_row_in_scope(r)),
        },
    )


def compute_evidence_fingerprint(
    employee_row: dict[str, Any] | None,
    sys_user_rows: list[dict[str, Any]],
) -> str:
    """Stable fingerprint over the *normalized evidence* (not secrets).

    Only allow-listed projection keys participate. Two captures with the
    same EMPL_CODE/VALIDSTATE/ISDELETED/STATUS values produce the same
    fingerprint regardless of timestamps.
    """
    employee_part = ""
    if employee_row is not None:
        employee_part = "|".join(
            f"{key}={_text(employee_row.get(key)) or ''}"
            for key in ("VALIDSTATE", "ISDELETED")
        )
    user_part = "|".join(
        sorted(
            f"{_text(row.get('EMPL_CODE')) or ''}:{_text(row.get('STATUS')) or ''}:{_text(row.get('ISDELETED')) or ''}"
            for row in sys_user_rows
            if sys_user_row_in_scope(row)
        )
    )
    raw = f"v1|{employee_part}|{user_part}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def next_transition_seq(prior_states: list[str], desired_state: str) -> int:
    """Persistent transition ordinal for idempotency (§4.6.3).

    ``prior_states`` is the chronological list of prior desired states
    (oldest first, including same-state repeats). Generations: the initial
    record is generation 1; every change starts a new generation. The
    current ordinal = 1 + changes_in_history + (1 if the desired state
    differs from the latest, else 0). enabled→disabled→enabled→disabled
    therefore yields ordinals 1,2,3,4 — the second disable is a NEW action
    identity never swallowed by the first one — while a repeat of the
    latest state keeps the ordinal (idempotent re-read).
    """
    if not prior_states:
        return 1
    changes = 0
    previous = prior_states[0]
    for state in prior_states[1:]:
        if state != previous:
            changes += 1
        previous = state
    if prior_states[-1] != desired_state:
        changes += 1
    return 1 + changes


def strip_personally_identifying(decision: AccountStateDecision) -> dict[str, Any]:
    """DTO-safe projection: no names, no account secrets, no raw rows."""
    return {
        "person_code": decision.person_code,
        "rule_version": RULE_VERSION,
        "employee_state": decision.employee_state,
        "user_state": decision.user_state,
        "desired_state": decision.desired_state,
        "decision_reason": decision.decision_reason,
        "execution_allowed": decision.execution_allowed,
        "blocked_reason": decision.blocked_reason,
    }


def target_time_unchanged(current_raw: Any, recorded_raw: Any) -> bool | None:
    """Precise change detection between the target raw time and our record
    (186 v1.10 §13.3 — replaces the legacy ``attribution_matches`` ±300s
    tolerance helper).

    Both sides are normalized the same way — ``datetime`` → ``isoformat()``,
    ``str`` → ``strip()``, anything else → ``str()`` — and then compared for
    exact string equality. Returns True (unchanged), False (target row was
    touched after our disable) or None (either side missing → attribution
    unknown, keep 待核实, do not unlock).

    There is deliberately NO tolerance window and NO timezone conversion in
    this module: time agreement is change detection, not proof of lock
    ownership. Lock ownership (platform disable evidence, attempt id,
    fingerprint, rule version) is established in the orchestration / gate
    layer before unlock is even attempted.
    """
    def _norm(value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, str):
            return value.strip()
        return str(value)

    current = _norm(current_raw)
    recorded = _norm(recorded_raw)
    if current is None or recorded is None:
        return None
    return current == recorded
