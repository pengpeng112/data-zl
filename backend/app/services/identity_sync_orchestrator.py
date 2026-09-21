"""Identity sync orchestrator: full auto pipeline per plan 107.

Pipeline: collect -> preflight -> plan -> apply -> readback -> reconcile -> report.
Two independent targets (CDMS, JHEMR) with independent transactions.
No human approval for normal nightly batches. No confirmation token.
HMAC account fingerprint binding. Circuit breaker. Idempotent.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select, and_, func
from sqlalchemy.orm import Session

from ..core.config import settings
from ..models.identity import IdentityPerson, IdentityPersonDepartment, IdentityPersonSource
from ..models.identity_sync import (
    IdentitySyncBatch,
    IdentitySyncAction,
    IdentitySyncWatermark,
    IdentityRoleMapping,
    IdentityProtectedAccount,
    IdentityManagedRelation,
    IdentitySyncCompensation,
    IdentityClassificationRecord,
    IdentityDistributedLock,
    IdentitySchedulerRun,
    IdentityCircuitBreaker,
    IdentityAccountStateDecision,
    IdentityAccountStateAttempt,
)
from ..services.identity_classification import allowed_additional_group_classes
from ..services.identity_hmac import (
    compute_account_fingerprint,
    compute_action_hash,
    compute_idempotency_key,
    compute_batch_fingerprint,
)
from ..services.identity_watermark import advance_watermark, get_watermark, max_watermark, window_start
from ..services.identity_sync_audit import _person_trace
from ..services.identity_sync_status import error_code_masked, short_fingerprint
from ..services.identity_time import (
    as_aware as _as_aware,
    is_after_modified_watermark as _is_after_modified_watermark,
)
from ..services.identity_sync_action_gate import (
    current_run_mode,
    approved_disable_persons,
    dispatch_identity_state_action,
    get_or_open_window,
    mark_reservation,
    person_is_protected,
    protection_mapping_report,
    reserve_window_slot,
    window_reservation_status,
    IdentityWindowBudget,
)

logger = logging.getLogger(__name__)

SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
MANAGED_SINCE = datetime(2026, 7, 20, tzinfo=timezone.utc)
TEMPLATE_VERSION = "jhemr-login-v1"
SENSITIVE_FIELDS = {"FPWD", "FPWD_SM", "PASSWORD", "USER_PWD", "USER_PWD_SM", "NAME", "ID_NO", "PHONE"}
ELIGIBLE_CLASSIFICATIONS = {"doctor", "nurse", "pharmacist"}
STAFF_GROUP_SOURCE_TABLE = "COMM.STAFF_VS_GROUP"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_shanghai() -> datetime:
    return datetime.now(SHANGHAI_TZ)


def _mask_emp_no(emp_no: str) -> str:
    if not emp_no:
        return "***"
    if len(emp_no) <= 4:
        return "*" * len(emp_no)
    return emp_no[:2] + "*" * (len(emp_no) - 4) + emp_no[-2:]


def _strip_sensitive(data: dict) -> dict:
    return {k: v for k, v in data.items() if str(k).upper() not in SENSITIVE_FIELDS}


def _action_hash(actions: list[dict]) -> str:
    raw = "|".join(f"{a.get('target_system')}:{a.get('action_type')}:{a.get('target_table')}" for a in actions)
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


# ---------------------------------------------------------------------------
# Distributed lock
# ---------------------------------------------------------------------------

def acquire_lock(db: Session, lock_key: str, holder: str, timeout_s: int) -> bool:
    """QA ST-010：SELECT ... FOR UPDATE 行锁化，消除过期锁接管的并发双跑窗口；
    并发 INSERT 撞唯一键时按未获锁处理（fail-closed）而非抛未捕获异常。"""
    from sqlalchemy.exc import IntegrityError

    now = _now()
    existing = db.scalar(
        select(IdentityDistributedLock)
        .where(IdentityDistributedLock.lock_key == lock_key)
        .with_for_update()
    )
    if existing:
        expires_at = _as_aware(existing.expires_at)
        if existing.released_at is None and expires_at and expires_at > now:
            return False
        existing.lock_holder = holder
        existing.acquired_at = now
        existing.expires_at = now + timedelta(seconds=timeout_s)
        existing.released_at = None
        db.flush()
        return True
    db.add(IdentityDistributedLock(
        lock_key=lock_key,
        lock_holder=holder,
        acquired_at=now,
        expires_at=now + timedelta(seconds=timeout_s),
    ))
    try:
        db.flush()
    except IntegrityError:
        # 并发方已插入同一 lock_key：本方未获锁，回滚该插入并拒绝执行。
        db.rollback()
        return False
    return True


def release_lock(db: Session, lock_key: str) -> None:
    existing = db.scalar(
        select(IdentityDistributedLock).where(IdentityDistributedLock.lock_key == lock_key)
    )
    if existing:
        existing.released_at = _now()
        db.flush()


# ---------------------------------------------------------------------------
# Circuit breaker
# ---------------------------------------------------------------------------

def check_circuit_breaker(db: Session, breaker_key: str) -> dict[str, Any]:
    cb = db.scalar(
        select(IdentityCircuitBreaker).where(IdentityCircuitBreaker.breaker_key == breaker_key)
    )
    if cb is None:
        return {"open": False, "consecutive_failures": 0}
    return {
        "open": bool(cb.is_open),
        "consecutive_failures": cb.consecutive_failures or 0,
        "last_failure_at": cb.last_failure_at.isoformat() if cb.last_failure_at else None,
    }


def record_success(db: Session, breaker_key: str) -> None:
    cb = db.scalar(
        select(IdentityCircuitBreaker).where(IdentityCircuitBreaker.breaker_key == breaker_key)
    )
    if cb is None:
        cb = IdentityCircuitBreaker(breaker_key=breaker_key, threshold=settings.identity_cb_consecutive_failure_limit)
        db.add(cb)
    cb.consecutive_failures = 0
    cb.is_open = False
    cb.last_success_at = _now()
    cb.updated_at = _now()
    db.flush()


def record_failure(db: Session, breaker_key: str) -> bool:
    """Record failure. Returns True if circuit is now open."""
    cb = db.scalar(
        select(IdentityCircuitBreaker).where(IdentityCircuitBreaker.breaker_key == breaker_key)
    )
    if cb is None:
        cb = IdentityCircuitBreaker(breaker_key=breaker_key, threshold=settings.identity_cb_consecutive_failure_limit)
        db.add(cb)
    cb.consecutive_failures = (cb.consecutive_failures or 0) + 1
    cb.last_failure_at = _now()
    cb.updated_at = _now()
    if cb.consecutive_failures >= (cb.threshold or settings.identity_cb_consecutive_failure_limit):
        cb.is_open = True
        cb.opened_at = _now()
        db.flush()
        return True
    db.flush()
    return False


# ---------------------------------------------------------------------------
# Candidate selection (plan 107 section 4)
# ---------------------------------------------------------------------------

def _modified_employee_times(db: Session) -> dict[str, datetime]:
    """HIS SYS_EMPLOYEE rows whose MODIFIEDTIME is after the main watermark."""
    from datetime import datetime as _dt
    modified_since_raw = getattr(settings, "identity_sync_modified_since", None)
    modified_since = _as_aware(_dt.fromisoformat(
        modified_since_raw if isinstance(modified_since_raw, str) else "2026-08-04T00:00:00"
    ))
    main_watermark = get_watermark(db, source_code="HIS", watermark_key="main_account_sync")
    if main_watermark.create_date is not None:
        modified_since = window_start(main_watermark) or modified_since
    source_rows = db.scalars(select(IdentityPersonSource).where(
        IdentityPersonSource.source_table == "FXHIS.SYS_EMPLOYEE",
    )).all()
    modified_by_code: dict[str, datetime] = {}
    for source in source_rows:
        raw = source.raw_data or {}
        value = raw.get("MODIFIEDTIME") or raw.get("modifiedtime")
        if not value or not source.person_code:
            continue
        try:
            parsed = _dt.fromisoformat(str(value))
        except ValueError:
            continue
        source_tie_key = compute_account_fingerprint(source.person_code, "HIS", settings.identity_hmac_key_ref)
        if _is_after_modified_watermark(
            parsed,
            modified_since,
            source_tie_key,
            main_watermark.employee_key,
        ):
            modified_by_code[source.person_code] = parsed
    return modified_by_code


def select_nightly_candidates(db: Session, *, filter_stats: dict[str, int] | None = None) -> list[dict[str, Any]]:
    """Select all eligible candidates for nightly sync.

    Rules (plan 107 section 4):
    - doctor/nurse/pharmacist only
    - status active
    - classification unique (no conflict)
    - primary dept valid
    - create_date >= managed_since
    - not in protected list
    - not outsource/management/conflict/status_conflict/master_data_missing

    186 v1.10 P0-5：enforce=true 时每个候选必须有当前规则、来源完整的最新
    决策；缺失/不完整按 blocked 计数（不静默继续旧规则放行）。
    """
    modified_by_code = _modified_employee_times(db)

    persons = db.scalars(
        select(IdentityPerson).where(
            IdentityPerson.employment_status == "active",
            IdentityPerson.classification.in_(list(ELIGIBLE_CLASSIFICATIONS)),
        ).order_by(
            IdentityPerson.source_create_date.asc(),
            IdentityPerson.person_code.asc(),
        )
    ).all()

    # 186 §4.6.4-9：保护匹配按 (target_system, account_id) 二元键 + 人员级
    # 保守默认（任一实际关联目标受保护 → 整人不自动变更）。
    protected_pairs = _protected_target_accounts(db)
    # 186 I2：双来源判定过滤——desired=disabled 整人排除（防 create/align
    # 隐式重新启用）；desired=unknown 的未纳管人员不新建账号（两来源未证
    # 实双启用零新建）；已纳管 unknown 允许例行 align（不改账号状态）。
    # P0-5：enforce=true 时决策缺失或 source_complete=false → 计数并排除。
    dual_decisions = _latest_decisions_by_person(db) if settings.identity_dual_source_enforce else {}
    if dual_decisions:
        managed_fps = {
            row for row in db.scalars(select(IdentityManagedRelation.account_fingerprint)).all() if row
        }
    else:
        managed_fps = set()

    candidates = []
    for person in persons:
        emp_no = person.person_code
        if not emp_no:
            continue
        if modified_by_code:
            if emp_no not in modified_by_code:
                continue
        elif (
            not person.source_create_date
            or _as_aware(person.source_create_date) < MANAGED_SINCE
        ):
            continue
        if person.conflict_flag:
            continue
        protected_now, _hits = _person_is_protected(protected_pairs, emp_no)
        if protected_now:
            continue
        if dual_decisions:
            decision = dual_decisions.get(emp_no)
            if decision is None:
                if filter_stats is not None:
                    filter_stats["blocked_no_decision"] = filter_stats.get("blocked_no_decision", 0) + 1
                continue
            if not decision.source_complete:
                if filter_stats is not None:
                    filter_stats["blocked_incomplete"] = filter_stats.get("blocked_incomplete", 0) + 1
                continue
            if decision.desired_state == "disabled":
                continue
            if decision.desired_state == "unknown":
                person_managed = (
                    compute_account_fingerprint(emp_no, "CDMS", settings.identity_hmac_key_ref) in managed_fps
                    or compute_account_fingerprint(emp_no, "JHEMR", settings.identity_hmac_key_ref) in managed_fps
                )
                if not person_managed:
                    continue
        primary_dept, additional_depts = _get_person_depts(db, emp_no, person.classification)
        if not primary_dept:
            continue
        candidates.append({
            "emp_no": emp_no,
            "emp_no_masked": _mask_emp_no(emp_no),
            "classification": person.classification,
            "primary_dept": primary_dept,
            "dept_codes": [primary_dept] + additional_depts,
            "create_date": person.source_create_date.isoformat() if person.source_create_date else None,
            "modified_time": modified_by_code[emp_no].isoformat() if emp_no in modified_by_code else None,
            "job_title": person.job_title,
        })

    return candidates


def select_deactivate_candidates(db: Session) -> list[dict[str, Any]]:
    """HIS-disabled employees in the current MODIFIEDTIME increment.

    Only the increment is processed so historical inactive accounts are not
    bulk-locked. Protected and status-conflict rows stay out. JHEMR existence
    is checked at apply time.
    """
    modified_by_code = _modified_employee_times(db)
    if not modified_by_code:
        return []
    protected_pairs = _protected_target_accounts(db)
    persons = db.scalars(
        select(IdentityPerson).where(
            IdentityPerson.employment_status == "inactive",
            IdentityPerson.person_code.in_(list(modified_by_code.keys())),
        )
    ).all()
    candidates = []
    for person in persons:
        emp_no = person.person_code
        if not emp_no:
            continue
        protected_now, _hits = _person_is_protected(protected_pairs, emp_no)
        if protected_now:
            continue
        if person.employment_status != "inactive":
            continue
        if person.conflict_flag:
            continue
        candidates.append({
            "emp_no": emp_no,
            "emp_no_masked": _mask_emp_no(emp_no),
            "classification": person.classification,
            "modified_time": modified_by_code[emp_no].isoformat() if emp_no in modified_by_code else None,
        })
    return candidates


# ---------------------------------------------------------------------------
# 186 I2/I3: dual-source (SYS_EMPLOYEE + SYS_USER) account state actions
# ---------------------------------------------------------------------------

def _latest_decisions_by_person(
    db: Session, *, captured_since: datetime | None = None
) -> dict[str, IdentityAccountStateDecision]:
    """Latest dual-source decision per person (dual_source_v1).

    186 v1.10 P0-5：``captured_since`` 提供时只保留本轮采集写入的决策
    （persist 复用行时会刷新 captured_at），防止夜跑静默复用旧决策。
    """
    rows = db.scalars(
        select(IdentityAccountStateDecision).where(
            IdentityAccountStateDecision.rule_version == "dual_source_v1",
        ).order_by(
            IdentityAccountStateDecision.created_at.asc(),
            IdentityAccountStateDecision.id.asc(),
        )
    ).all()
    latest: dict[str, IdentityAccountStateDecision] = {}
    for row in rows:
        if captured_since is not None and row.captured_at is not None:
            captured = _as_aware(row.captured_at)
            if captured < captured_since:
                continue
        latest[row.person_code] = row
    return latest


def _protected_target_accounts(db: Session) -> set[tuple[str, str]]:
    """(target_system, account_id) pairs from the protection registry.

    保留旧签名供既有回归读取；P0-7 判定请用 gate.person_is_protected
    （HMAC 候选法，不依赖"目标账号恒等于工号"假设）。
    """
    rows = db.scalars(select(IdentityProtectedAccount)).all()
    return {
        (str(row.target_system or "").upper(), str(row.account_id or ""))
        for row in rows
        if row.target_system and row.account_id
    }


def _person_is_protected(protected_pairs: set[tuple[str, str]], emp_no: str) -> tuple[bool, list[str]]:
    """Person-level protection (legacy pair-based check, kept for old tests)."""
    hits = [target for target, account in protected_pairs if account == emp_no and target in {"JHEMR", "CDMS"}]
    return (len(hits) > 0, hits)


def _account_state_actions_enabled() -> bool:
    """P0-1/P0-19：enforce=false 或 run_mode=observe 时不产生任何动作。"""
    if not settings.identity_dual_source_enforce:
        return False
    return current_run_mode() in {"disable_only", "full"}


def _latest_attempt(
    db: Session, *, fingerprint: str, action: str, rule_version: str
) -> IdentityAccountStateAttempt | None:
    return db.scalar(
        select(IdentityAccountStateAttempt).where(
            IdentityAccountStateAttempt.target_account_fingerprint == fingerprint,
            IdentityAccountStateAttempt.action == action,
            IdentityAccountStateAttempt.rule_version == rule_version,
        ).order_by(IdentityAccountStateAttempt.id.desc())
    )


def _missing_retry_targets(
    db: Session,
    person_code: str,
    decision: IdentityAccountStateDecision,
    fp_by_target: dict[str, str],
) -> set[str]:
    """该人员当前转换序内『因目标缺失而 skipped』的目标集合。"""
    missing: set[str] = set()
    for target, fp in fp_by_target.items():
        attempt = _latest_attempt(db, fingerprint=fp, action="disable", rule_version=decision.rule_version)
        if (
            attempt is not None
            and attempt.transition_seq == decision.transition_seq
            and attempt.status == "skipped"
            and attempt.reason_code == "target_missing"
        ):
            missing.add(target)
    return missing


def select_account_state_actions(
    db: Session,
    *,
    run_id: str | None = None,
    captured_since: datetime | None = None,
    window: IdentityWindowBudget | None = None,
    reserve_budget: bool = True,
) -> dict[str, Any]:
    """186 v1.10：双来源账号启停动作选择（P0-1/3/5/7/8/19/20 重写）。

    - P0-1：enforce=false / run_mode=observe → 零动作（population 统计保留，
      决策采集不受影响）。
    - P0-3：run 内分页续跑，总量上限 identity_account_state_total_cap；
      超出才 truncated=True 并报 remaining。
    - P0-5：决策缺失/来源不完整/无人员主档/冲突人员逐类计数，不静默跳过。
    - P0-8：target_missing 不计入 done_targets（保留待补偿重试）。
    - P0-19：disable 逐对象必须属于批准范围（冻结 pilot/baseline 名单）。
    - P0-20：本窗预算（≤identity_window_max_persons 唯一人员）与全体积压
      分开；阈值判定消费本窗计划集，积压单列不隐去。
    """
    batch_limit = max(1, int(getattr(settings, "identity_account_state_batch_limit", 2000)))
    total_cap = max(batch_limit, int(getattr(settings, "identity_account_state_total_cap", 5000)))

    decisions = _latest_decisions_by_person(db)
    population = len(decisions)
    result_base = {
        "disables": [],
        "enables": [],
        "population": population,
        "scanned": 0,
        "truncated": False,
        "remaining": 0,
        "blocked_unknown": 0,
        "blocked_no_decision": 0,
        "blocked_incomplete": 0,
        "blocked_no_person": 0,
        "blocked_conflict": 0,
        "blocked_protected": 0,
        "backlog_pending": 0,
        "backlog_unapproved": 0,
        "deferred_budget": 0,
        "unchanged": 0,
        "run_mode": current_run_mode(),
        "enforce": bool(settings.identity_dual_source_enforce),
        "protection": protection_mapping_report(db),
    }

    if not _account_state_actions_enabled():
        # P0-1：采集/决策照常；动作与熔断统计为零。
        return result_base

    mode = current_run_mode()
    protected_pairs = _protected_target_accounts(db)
    person_by_code = {
        p.person_code: p
        for p in db.scalars(select(IdentityPerson)).all()
        if p.person_code
    }
    approved = approved_disable_persons(db)

    pending_disables: list[dict[str, Any]] = []  # 批准范围内、待本窗执行
    missing_pool: list[dict[str, Any]] = []      # 仅剩 target_missing 的重试池
    enables: list[dict[str, Any]] = []
    scanned = 0
    truncated = False

    for person_code in sorted(decisions):
        if scanned >= total_cap:
            truncated = True
            break
        scanned += 1
        decision = decisions[person_code]
        if not decision.source_complete:
            result_base["blocked_incomplete"] += 1
            continue
        if decision.desired_state not in {"enabled", "disabled"} or not decision.execution_allowed:
            result_base["blocked_unknown"] += 1
            continue
        person = person_by_code.get(person_code)
        if person is None:
            result_base["blocked_no_person"] += 1
            continue
        protected, _hits = _person_is_protected(protected_pairs, person_code)
        if protected:
            result_base["blocked_protected"] += 1
            continue
        if person.conflict_flag:
            result_base["blocked_conflict"] += 1
            continue

        action = "disable" if decision.desired_state == "disabled" else "enable"

        if action == "enable":
            if mode != "full":
                # P0-19：disable_only 不计划 enable；生产 full 不开放。
                result_base["unchanged"] += 1
                continue
            has_disable_evidence = db.scalar(
                select(func.count()).select_from(IdentityAccountStateAttempt).where(
                    IdentityAccountStateAttempt.person_code == person_code,
                    IdentityAccountStateAttempt.action == "disable",
                    IdentityAccountStateAttempt.status == "executed",
                )
            )
            if not has_disable_evidence:
                result_base["unchanged"] += 1
                continue

        fp_by_target = {
            "JHEMR": compute_account_fingerprint(person_code, "JHEMR", settings.identity_hmac_key_ref),
            "CDMS": compute_account_fingerprint(person_code, "CDMS", settings.identity_hmac_key_ref),
        }
        done_targets: set[str] = set()
        retry_targets: set[str] = set()
        for target, fp in fp_by_target.items():
            attempt = _latest_attempt(db, fingerprint=fp, action=action, rule_version=decision.rule_version)
            if attempt is None:
                continue
            if attempt.transition_seq == decision.transition_seq:
                if attempt.status == "executed":
                    done_targets.add(target)
                elif attempt.reason_code == "already_desired" and attempt.status == "skipped":
                    # P0-8：已达标幂等跳过算 done；target_missing 不算（重试）。
                    done_targets.add(target)
                elif attempt.status in {"failed", "pending_reconcile", "planned", "skipped"}:
                    retry_targets.add(target)
        if done_targets and action == "disable" and getattr(settings, "identity_drift_readback_enabled", False):
            # P0-20/T57：同代已 executed 的目标限量只读回读验证实际状态；
            # 漂移（如人工改回启用）记 drift_detected 并重新规划，不以历史
            # 成功冒充当前状态。回读失败按 readback_failed 计数，不推断。
            from .identity_sync_action_gate import read_target_account_state

            if result_base.get("readback_used", 0) < max(0, int(getattr(settings, "identity_drift_readback_limit", 25))):
                drifted: set[str] = set()
                for target in sorted(done_targets):
                    state = read_target_account_state(target, person_code)
                    result_base["readback_used"] = result_base.get("readback_used", 0) + 1
                    if state is None:
                        result_base["readback_failed"] = result_base.get("readback_failed", 0) + 1
                        continue
                    raw = state.get("account_status", state.get("fuserstate"))
                    normalized = str(raw).strip() if raw is not None else None
                    wants = "8" if target == "JHEMR" else "1"
                    if normalized is not None and normalized != wants:
                        drifted.add(target)
                if drifted:
                    result_base["drift_detected"] = result_base.get("drift_detected", 0) + 1
                    done_targets -= drifted
                    retry_targets |= drifted
        if done_targets >= {"JHEMR", "CDMS"}:
            result_base["unchanged"] += 1
            continue

        entry = {
            "person_code": person_code,
            "emp_no_masked": _mask_emp_no(person_code),
            "desired_state": decision.desired_state,
            "action": action,
            "transition_seq": decision.transition_seq,
            "decision_id": decision.id,
            "rule_version": decision.rule_version,
            "decision_reason": decision.decision_reason,
            "employee_state": decision.employee_state,
            "user_state": decision.user_state,
            "done_targets": sorted(done_targets),
            "retry_targets": sorted(retry_targets),
        }
        if action == "enable":
            enables.append(entry)
            continue

        # P0-19：disable 逐对象批准范围（token 不是名单）。
        if person_code not in approved:
            result_base["backlog_unapproved"] += 1
            continue
        # §13.5 反饥饿：剩余工作全为 target_missing 的人员不占本窗名额，
        # 进入 missing 探测池（目标重新出现才回到队列），否则头部缺失对象
        # 会每窗吃掉名额饿死后续 211 人。
        if retry_targets and not (set(retry_targets) - _missing_retry_targets(
            db, person_code, decision, fp_by_target
        )):
            missing_pool.append(entry)
            continue
        entry["scope"] = approved[person_code]
        pending_disables.append(entry)

    # §13.5 反饥饿：missing 池限量只读探测（目标重现→回归队列；仍缺→单列
    # backlog_missing_retry，不占名额不饿死队列）。
    result_base["backlog_missing_retry"] = 0
    result_base["missing_recovered"] = 0
    if missing_pool and getattr(settings, "identity_drift_readback_enabled", False):
        from .identity_sync_action_gate import read_target_account_state

        probe_budget = max(0, int(getattr(settings, "identity_missing_probe_limit", 10)))
        for entry in missing_pool[:probe_budget]:
            person_code = entry["person_code"]
            for target in entry["retry_targets"]:
                state = read_target_account_state(target, person_code)
                result_base["readback_used"] = result_base.get("readback_used", 0) + 1
                if state is None:
                    continue
                if target not in entry["done_targets"]:
                    entry.setdefault("recovered_targets", []).append(target)
        for entry in missing_pool[:probe_budget]:
            if entry.get("recovered_targets"):
                entry["scope"] = approved[entry["person_code"]]
                pending_disables.append(entry)
                result_base["missing_recovered"] += 1
            else:
                result_base["backlog_missing_retry"] += 1
        result_base["backlog_missing_retry"] += max(0, len(missing_pool) - probe_budget)
    else:
        result_base["backlog_missing_retry"] = len(missing_pool)

    # P0-20：完整观察人口与动作预算分开；本窗 ≤ identity_window_max_persons。
    disables: list[dict[str, Any]] = []
    active_window = window or get_or_open_window(
        db, approval_ref=(settings.identity_phase_d_approval_version or "").strip()
    )
    for entry in pending_disables:
        if len(disables) >= active_window.limit_persons:
            result_base["deferred_budget"] += 1
            continue
        if reserve_budget:
            outcome = reserve_window_slot(
                db, window=active_window, person_code=entry["person_code"],
                action="disable", run_id=run_id,
            )
            if outcome == "full":
                result_base["deferred_budget"] += 1
                continue
        disables.append(entry)
    result_base["backlog_pending"] = len(pending_disables) - len(disables)

    result_base["disables"] = disables
    result_base["enables"] = enables
    result_base["scanned"] = scanned
    result_base["truncated"] = truncated
    result_base["remaining"] = max(0, population - scanned)
    result_base["window"] = {
        "window_key": active_window.window_key,
        "limit_persons": active_window.limit_persons,
        **window_reservation_status(db, active_window),
    }
    return result_base


def _record_state_attempt(
    db: Session,
    *,
    run_id: str,
    batch_id: str,
    decision_id: int | None,
    person_code: str,
    target_system: str,
    fingerprint: str,
    action: str,
    desired_state: str,
    transition_seq: int,
    rule_version: str,
) -> IdentityAccountStateAttempt:
    """Idempotent upsert of one target attempt row (identity = fingerprint +
    action + transition_seq + rule_version; same transition replays the row)."""
    existing = db.scalar(
        select(IdentityAccountStateAttempt).where(
            IdentityAccountStateAttempt.target_account_fingerprint == fingerprint,
            IdentityAccountStateAttempt.action == action,
            IdentityAccountStateAttempt.transition_seq == transition_seq,
            IdentityAccountStateAttempt.rule_version == rule_version,
        )
    )
    if existing is not None:
        existing.run_id = run_id
        existing.batch_id = batch_id
        existing.decision_id = decision_id
        existing.desired_state = desired_state
        return existing
    row = IdentityAccountStateAttempt(
        run_id=run_id,
        batch_id=batch_id,
        decision_id=decision_id,
        person_code=person_code,
        target_system=target_system,
        target_account_fingerprint=fingerprint,
        action=action,
        desired_state=desired_state,
        transition_seq=transition_seq,
        rule_version=rule_version,
        status="planned",
    )
    db.add(row)
    db.flush()
    return row


def _latest_executed_disable_at(
    db: Session, person_code: str, target_system: str
) -> str | None:
    """本规则最近一次 executed disable 的时间（恢复归因基准；无证据→None）。"""
    row = db.scalar(
        select(IdentityAccountStateAttempt).where(
            IdentityAccountStateAttempt.person_code == person_code,
            IdentityAccountStateAttempt.target_system == target_system,
            IdentityAccountStateAttempt.action == "disable",
            IdentityAccountStateAttempt.status == "executed",
        ).order_by(IdentityAccountStateAttempt.id.desc())
    )
    if row is None or row.executed_at is None:
        return None
    return row.executed_at.isoformat()


def _origin_disable_evidence(
    db: Session, person_code: str, target_system: str, fingerprint: str, rule_version: str
) -> dict[str, Any] | None:
    """P0-4/§13.3：恢复引用的本规则前一 executed 停用证据。

    必须来自持久 attempt（含目标 raw 时间，停用回读时写入 attribution_
    evidence）；平台 executed_at 只作审计展示，绝不参与归因比较。
    """
    row = db.scalar(
        select(IdentityAccountStateAttempt).where(
            IdentityAccountStateAttempt.person_code == person_code,
            IdentityAccountStateAttempt.target_system == target_system,
            IdentityAccountStateAttempt.target_account_fingerprint == fingerprint,
            IdentityAccountStateAttempt.action == "disable",
            IdentityAccountStateAttempt.status == "executed",
            IdentityAccountStateAttempt.rule_version == rule_version,
        ).order_by(IdentityAccountStateAttempt.id.desc())
    )
    if row is None:
        return None
    evidence = row.attribution_evidence or {}
    return {
        "attempt_id": row.id,
        "target_raw_time": evidence.get("target_raw_time"),
        "target_account_fingerprint": fingerprint,
        "rule_version": rule_version,
        "approval_ref": evidence.get("approval_ref"),
    }


def _process_account_state_person(
    db: Session,
    entry: dict,
    run_id: str,
    *,
    window: IdentityWindowBudget | None = None,
) -> dict[str, Any]:
    """186 v1.10 I3：一个人的双目标启停（经唯一 dispatch；P0-8/P0-11）。

    - 四类动作只经 dispatch_identity_state_action（执行器注册/用途绑定/
      批准范围/预算/保护全门禁），不再直接 import bridge。
    - P0-8：target_missing 单独分类，不进 done_targets，保留下一夜重试；
      success+target_missing/blocked/failed → partial，不记全成功。
    - P0-4：停用成功持久化目标 raw 时间；恢复引用 origin_disable 证据。
    """
    person_code = entry["person_code"]
    action = entry["action"]
    transition_seq = entry["transition_seq"]
    rule_version = entry["rule_version"]
    decision_id = entry["decision_id"]
    batch_id = f"NTL-{run_id}-AS{uuid.uuid4().hex[:8]}"

    fp_jhemr = compute_account_fingerprint(person_code, "JHEMR", settings.identity_hmac_key_ref)
    fp_cdms = compute_account_fingerprint(person_code, "CDMS", settings.identity_hmac_key_ref)

    # 执行前再次检查保护（§4.6.4-9：不仅选人时检查；HMAC 候选法）。
    protected_now, _hits = person_is_protected(db, person_code)
    if protected_now:
        return {"status": "skipped", "reason": "protected_at_execution", "targets": {}}

    approval_ref = (settings.identity_phase_d_approval_version or "").strip()
    results: dict[str, str] = {}
    reasons: dict[str, str | None] = {}
    done_targets = set(entry.get("done_targets") or [])

    for target_system, fingerprint in (("JHEMR", fp_jhemr), ("CDMS", fp_cdms)):
        if target_system in done_targets:
            # 当前转换序内已达标（executed / already_desired）的目标不重复写。
            results[target_system] = "already_desired"
            reasons[target_system] = "already_desired"
            continue
        attempt = _record_state_attempt(
            db,
            run_id=run_id,
            batch_id=batch_id,
            decision_id=decision_id,
            person_code=person_code,
            target_system=target_system,
            fingerprint=fingerprint,
            action=action,
            desired_state=entry["desired_state"],
            transition_seq=transition_seq,
            rule_version=rule_version,
        )
        origin_disable = None
        if action == "enable":
            origin_disable = _origin_disable_evidence(db, person_code, target_system, fingerprint, rule_version)
            if origin_disable is not None:
                attempt.origin_disable_attempt_id = origin_disable["attempt_id"]

        outcome = dispatch_identity_state_action(
            db,
            target_system=target_system,
            action=action,
            person_code=person_code,
            run_id=run_id,
            approval_ref=approval_ref,
            origin_disable=origin_disable,
            window=window,
        )

        status = outcome.get("status")
        gate_info = outcome.get("gate") or {}
        raw_time = outcome.get("locked_time_raw", outcome.get("changed_at_raw"))
        attempt.after_state = str(
            outcome.get("account_status", outcome.get("after_state", "")) or ""
        ) or None
        attempt.attribution_evidence = {
            "reason": outcome.get("reason"),
            "lock_attribution": outcome.get("lock_attribution"),
            "rows_affected": outcome.get("rows_affected"),
            "target_raw_time": raw_time,
            "approval_ref": approval_ref or None,
            "gate_reason": gate_info.get("reason") if gate_info else None,
        }
        attempt.executed_at = _now()
        if status == "success":
            attempt.status = "executed"
            attempt.reason_code = None
            attempt.lock_attribution = "not_applicable" if action == "disable" else "by_this_rule"
            results[target_system] = "success"
        elif status == "skipped":
            attempt.status = "skipped"
            attempt.reason_code = outcome.get("reason") or "already_desired"
            results[target_system] = "already_desired"
        elif status == "missing_target":
            # P0-8：目标缺失≠幂等完成；保留待补偿，下一夜/目标出现后重试。
            attempt.status = "skipped"
            attempt.reason_code = "target_missing"
            results[target_system] = "target_missing"
        elif status == "blocked":
            attempt.status = "blocked"
            attempt.reason_code = outcome.get("reason") or "blocked"
            attempt.lock_attribution = outcome.get("lock_attribution") or "manual_or_unknown"
            results[target_system] = "blocked"
        else:
            attempt.status = "failed" if status == "failed" else "pending_reconcile"
            attempt.error_class = "target_write" if status == "failed" else "commit_unknown"
            attempt.error_code_masked = error_code_masked(outcome.get("error"))
            results[target_system] = attempt.status
        reasons[target_system] = attempt.reason_code
        db.flush()

    statuses = set(results.values())
    if not statuses:
        overall = "failed"
    elif statuses <= {"success", "already_desired"}:
        overall = "success"
    elif "success" in statuses:
        # 一目标成功、另一目标失败/未决/被保护/缺失 → 部分成功，绝不记全成功。
        overall = "partial"
    elif statuses <= {"already_desired", "target_missing"}:
        # 两目标均缺失：零创建、可见原因（blocked 语义，不算 success）。
        overall = "blocked"
    elif statuses <= {"blocked"}:
        overall = "blocked"
    elif statuses <= {"already_desired"}:
        overall = "already_desired"
    else:
        overall = "failed"

    # 托管关系状态随动（保持既有 managed 语义：恢复不回退建号）。
    if action == "disable":
        for target_system, fingerprint in (("JHEMR", fp_jhemr), ("CDMS", fp_cdms)):
            if results.get(target_system) != "success":
                continue
            managed = db.scalar(
                select(IdentityManagedRelation).where(
                    IdentityManagedRelation.target_system == target_system,
                    IdentityManagedRelation.account_fingerprint == fingerprint,
                )
            )
            if managed is not None:
                managed.status = "deactivated"
    else:
        for target_system, fingerprint in (("JHEMR", fp_jhemr), ("CDMS", fp_cdms)):
            if results.get(target_system) != "success":
                continue
            managed = db.scalar(
                select(IdentityManagedRelation).where(
                    IdentityManagedRelation.target_system == target_system,
                    IdentityManagedRelation.account_fingerprint == fingerprint,
                    IdentityManagedRelation.status == "deactivated",
                )
            )
            if managed is not None:
                managed.status = "active"

    return {"status": overall, "targets": results, "reasons": reasons}


def _get_person_depts(db: Session, person_code: str, classification: str | None = None) -> tuple[str | None, list[str]]:
    """Return (primary_dept, additional_depts) for a person.

    - Primary dept: the is_primary=True relation (HIS STAFF_DICT /
      SYS_EMPLOYEE source), deterministic — never set-order dependent.
    - Additional depts: only staff-group relations whose GROUP_CLASS is in
      the per-classification whitelist (plan 107 §5.4 mapped to live values:
      doctor -> 病区医生, nurse -> 病区护士, pharmacist -> none).
    - Pharmacists get the primary dept only (plan 107 §0.3.1).
    """
    rows = db.scalars(
        select(IdentityPersonDepartment).where(
            IdentityPersonDepartment.person_code == person_code,
        )
    ).all()

    person = db.scalar(select(IdentityPerson).where(IdentityPerson.person_code == person_code))
    primary = person.dept_code if person and person.dept_code else None
    if not primary:
        primaries = sorted(
            (r for r in rows if r.is_primary and r.dept_code),
            key=lambda r: (0 if r.source_table == "FXHIS.SYS_EMPLOYEE" else 1, r.dept_code),
        )
        primary = primaries[0].dept_code if primaries else None

    allowed = allowed_additional_group_classes(classification or "")
    additionals: list[str] = []
    seen: set[str] = set()
    for row in sorted(rows, key=lambda r: (r.dept_code or "")):
        if row.is_primary or not row.dept_code or row.dept_code == primary:
            continue
        # 附加科室只来自人员组白名单（107 §5.4）；DOCTOR_GROUP 等非组来源不产生附加科室
        if row.source_table != STAFF_GROUP_SOURCE_TABLE:
            continue
        if not row.group_class or row.group_class not in allowed:
            continue
        if row.dept_code not in seen:
            seen.add(row.dept_code)
            additionals.append(row.dept_code)
    return primary, additionals


def _get_role_mapping(db: Session, target_system: str, classification: str) -> dict | None:
    row = db.scalar(
        select(IdentityRoleMapping).where(
            IdentityRoleMapping.target_system == target_system,
            IdentityRoleMapping.person_classification == classification,
            IdentityRoleMapping.is_active.is_(True),
        )
    )
    if not row:
        return None
    return {"role_code": row.role_code, "role_name_cn": row.role_name_cn, "extra_config": row.extra_config or {}}


def _fetch_jhemr_existing_emp_nos(candidates: list[dict]) -> set[str] | None:
    """W10 方案 C：查候选中 JHEMR 已存在账号（现存用户首次纳管对齐）。

    返回 None 表示存在性检查失败——调用方按全部「真实新建号」处理（保守，
    熔断按旧语义触发），绝不因检查失败而放宽门禁。
    """
    if not candidates:
        return set()
    try:
        from .jhemr_identity_adapter import JhemrIdentityAdapter

        adapter = JhemrIdentityAdapter(
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
        existing: set[str] = set()
        with adapter:
            for c in candidates:
                if adapter.user_exists(c["emp_no"]):
                    existing.add(c["emp_no"])
        return existing
    except Exception:
        return None


def _compute_change_stats(
    db: Session,
    candidates: list[dict],
    *,
    jhemr_existing: set[str] | None = None,
) -> dict[str, Any]:
    """Compute real new/update/deactivate composition and watermark freshness.

    - new: candidate without an active managed relation in BOTH targets AND
      absent from JHEMR（真实新建号；jhemr_existing=None 时退回旧口径）
    - align_existing: W10 方案 C——JHEMR 账号已存在的首次纳管（additive align，
      补角色组/科室/登录方式），不计入 max_new 与 max_change_ratio，受
      identity_cb_max_align 单独约束
    - update: managed candidate with a real change signal — HIS
      MODIFIEDTIME increment touched the person（真正的字段变更），
      or the JHEMR existence check failed（fail-closed 保守回退旧口径）
    - resync_unchanged: 176 F-2——托管在册且不在 HIS 增量内的例行 resync
      （空增量夜的全托管圈约 110 人），单列计数，不计入 max_update 与
      max_change_ratio（比照 W10 对 align_existing 的处理）。仍受
      max_candidates 总量约束；JHEMR 存在性检查失败时不享受该豁免。
    - deactivate: managed persons no longer eligible (status/classification change)
    - watermark_gap_hours: hours since the last successful HIS collection
    - scope: all eligible active persons (denominator for change ratio)
    """
    managed_fps: set[str] = set()
    rows = db.scalars(
        select(IdentityManagedRelation.account_fingerprint).where(
            IdentityManagedRelation.status == "active",
        )
    ).all()
    managed_fps = {r for r in rows if r}

    new_count = 0
    update_count = 0
    align_existing_count = 0
    resync_unchanged_count = 0
    for c in candidates:
        fp_cdms = compute_account_fingerprint(c["emp_no"], "CDMS", settings.identity_hmac_key_ref)
        fp_jhemr = compute_account_fingerprint(c["emp_no"], "JHEMR", settings.identity_hmac_key_ref)
        if fp_cdms in managed_fps or fp_jhemr in managed_fps:
            if jhemr_existing is not None and not c.get("modified_time"):
                resync_unchanged_count += 1
            else:
                update_count += 1
        elif jhemr_existing is not None and c["emp_no"] in jhemr_existing:
            align_existing_count += 1
        else:
            new_count += 1

    scope = db.scalar(
        select(func.count()).select_from(IdentityPerson).where(
            IdentityPerson.source_create_date >= MANAGED_SINCE,
            IdentityPerson.employment_status == "active",
            IdentityPerson.classification.in_(list(ELIGIBLE_CLASSIFICATIONS)),
        )
    ) or 0

    deactivate_count = 0
    if managed_fps:
        eligible_codes = {c["emp_no"] for c in candidates}
        seen_codes: set[str] = set()
        all_persons = db.scalars(
            select(IdentityPerson).where(IdentityPerson.classification.in_(list(ELIGIBLE_CLASSIFICATIONS)))
        ).all()
        for person in all_persons:
            if not person.person_code or person.person_code in seen_codes:
                continue
            seen_codes.add(person.person_code)
            if person.person_code in eligible_codes:
                continue
            fp = compute_account_fingerprint(person.person_code, "CDMS", settings.identity_hmac_key_ref)
            fp_j = compute_account_fingerprint(person.person_code, "JHEMR", settings.identity_hmac_key_ref)
            if fp in managed_fps or fp_j in managed_fps:
                deactivate_count += 1

    watermark_gap_hours = 0.0
    wm = db.scalar(
        select(IdentitySyncWatermark).order_by(IdentitySyncWatermark.last_run_at.desc())
    )
    if wm is not None and wm.last_run_at is not None:
        last_run = _as_aware(wm.last_run_at)
        watermark_gap_hours = max(0.0, (_now() - last_run).total_seconds() / 3600.0)

    return {
        "new": new_count,
        "update": update_count,
        "align_existing": align_existing_count,
        "resync_unchanged": resync_unchanged_count,
        "deactivate": deactivate_count,
        "scope": max(int(scope), 1),
        "watermark_gap_hours": round(watermark_gap_hours, 2),
        # 行数守恒需要源端实时行数，编排器不直连 HIS；采集阶段负责记录，
        # 此处保留 0 并在报告中标注未接线（见 110 号复核报告 R-统计）。
        "source_row_delta_pct": 0,
    }


# ---------------------------------------------------------------------------
# Threshold / fuse checks (plan 107 section 3)
# ---------------------------------------------------------------------------

def check_thresholds(candidates: list[dict], stats: dict[str, int]) -> dict[str, Any]:
    """Check circuit breaker thresholds. Returns triggered dimension or None."""
    total = len(candidates)
    if total > settings.identity_cb_max_candidates:
        return {"triggered": True, "dimension": "max_candidates", "value": total, "limit": settings.identity_cb_max_candidates}
    if stats.get("new", 0) > settings.identity_cb_max_new:
        return {"triggered": True, "dimension": "max_new", "value": stats["new"], "limit": settings.identity_cb_max_new}
    # 176 F-2：update 只含真实变更（HIS 增量命中）或存在性检查失败的保守回退；
    # 托管在册例行 resync 在 stats["resync_unchanged"] 单列，不计入本维度与
    # 下方 change_ratio（比照 align_existing 的豁免方式），仍受 max_candidates 约束。
    if stats.get("update", 0) > settings.identity_cb_max_update:
        return {"triggered": True, "dimension": "max_update", "value": stats["update"], "limit": settings.identity_cb_max_update}
    # W10 方案 C：现存用户对齐单独设上限（防群体性误对齐），不计入 max_new/ratio
    if stats.get("align_existing", 0) > settings.identity_cb_max_align:
        return {"triggered": True, "dimension": "max_align", "value": stats["align_existing"], "limit": settings.identity_cb_max_align}
    if stats.get("deactivate", 0) > settings.identity_cb_max_deactivate:
        return {"triggered": True, "dimension": "max_deactivate", "value": stats["deactivate"], "limit": settings.identity_cb_max_deactivate}
    scope = max(int(stats.get("scope", total)), 1)
    change_ratio = (stats.get("new", 0) + stats.get("update", 0) + stats.get("deactivate", 0)) / scope
    if change_ratio > settings.identity_cb_max_change_ratio:
        return {"triggered": True, "dimension": "max_change_ratio", "value": round(change_ratio, 3), "limit": settings.identity_cb_max_change_ratio}
    # Watermark continuity check (plan 107 section 3)
    wm_limit = settings.identity_cb_max_watermark_gap_hours
    if stats.get("watermark_gap_hours", 0) > wm_limit:
        return {"triggered": True, "dimension": "watermark_continuity", "value": stats["watermark_gap_hours"], "limit": wm_limit}
    # Source row count conservation (plan 107 section 3)
    if stats.get("source_row_delta_pct", 0) > 20:
        return {"triggered": True, "dimension": "source_row_conservation", "value": stats["source_row_delta_pct"], "limit": 20}
    return {"triggered": False}


# ---------------------------------------------------------------------------
# Full pipeline: plan -> apply -> readback -> reconcile -> report
# ---------------------------------------------------------------------------

def run_nightly_pipeline(db: Session, *, triggered_by: str = "nightly_cron", refresh_source: bool = False) -> dict[str, Any]:
    """Execute the full nightly pipeline. Auto-advances without human approval.

    Pipeline: collect -> preflight -> plan -> apply -> readback -> reconcile -> report.
    Two independent targets per candidate. Each target is an independent transaction.
    """
    run_id = f"RUN-{uuid.uuid4().hex[:12]}"
    lock_key = "identity_nightly_sync"
    holder = f"nightly_{run_id}"

    declared_provider = str(getattr(settings, "identity_scheduler_provider", "disabled") or "disabled")
    providers = ({declared_provider} if declared_provider != "disabled" else set())
    if settings.identity_nightly_enabled:
        providers.add("apscheduler")
    if len(providers) > 1:
        run_record = IdentitySchedulerRun(
            run_id=run_id,
            triggered_by=triggered_by,
            status="misconfigured",
            started_at=_now(),
            finished_at=_now(),
            provider_code="multiple",
            report_summary={"reason": "multiple_scheduler_providers", "providers": sorted(providers)},
        )
        db.add(run_record)
        db.commit()
        try:
            from .identity_sync_audit import record_alert
            record_alert(db, run_id=run_id, alert_type="dual_scheduler", severity="error", error_class="multiple_providers", detail={"providers": sorted(providers)})
        except Exception:
            pass
        return {"status": "misconfigured", "reason": "multiple_scheduler_providers", "run_id": run_id}

    # Acquire distributed lock
    if not acquire_lock(db, lock_key, holder, settings.identity_nightly_max_runtime_seconds):
        return {"status": "skipped", "reason": "lock_held", "run_id": run_id}

    run_record = IdentitySchedulerRun(
        run_id=run_id,
        triggered_by=triggered_by,
        status="running",
        lock_holder=holder,
        started_at=_now(),
        provider_code=declared_provider if declared_provider != "disabled" else ("apscheduler" if settings.identity_nightly_enabled else "unknown"),
        provider_heartbeat_at=_now(),
    )
    db.add(run_record)
    db.flush()

    try:
        # Check circuit breakers
        for target in ("cdms", "jhemr"):
            cb_state = check_circuit_breaker(db, f"nightly_{target}")
            if cb_state["open"]:
                run_record.status = "failed"
                run_record.circuit_breaker_triggered = True
                run_record.circuit_breaker_dimension = f"nightly_{target}"
                run_record.finished_at = _now()
                db.commit()
                try:
                    from .identity_sync_audit import record_alert
                    record_alert(db, run_id=run_id, alert_type="circuit_breaker_open", severity="error", error_class=f"nightly_{target}", detail={"target": target})
                except Exception:
                    pass
                return {"status": "failed", "reason": "circuit_breaker_open", "target": target, "run_id": run_id}

        # COLLECT: refresh the platform identity master from read-only HIS,
        # then classify and select the configured MODIFIEDTIME increment.
        run_mode = current_run_mode()
        collection_stats: dict[str, Any] = {"status": "not_refreshed"}
        if refresh_source:
            from .his_identity_sync import sync_his_identity
            collection_stats = sync_his_identity(
                db, operator="identity-nightly", dry_run=False, write_audit=True,
            )
        # P0-5：enforce 时动作必须以本轮成功完整采集为依据；重放场景须由
        # 调用方明确提供并核验 collection_run_id（此处至少要求本轮刷新）。
        collection_started_at = None
        source_complete = True
        if isinstance(collection_stats, dict):
            source_complete = bool(collection_stats.get("source_complete", refresh_source is False))
            started_raw = collection_stats.get("collection_started_at")
            if started_raw:
                try:
                    collection_started_at = _as_aware(datetime.fromisoformat(str(started_raw)))
                except ValueError:
                    collection_started_at = None
        if settings.identity_dual_source_enforce and refresh_source and not source_complete:
            collection_started_at = datetime(1970, 1, 1, tzinfo=timezone.utc)  # 使旧决策全部失效
        # The preflight fills IdentityPerson.classification / conflict_flag from
        # the collected HIS person sources — without it the candidate set would
        # always be empty (plan 107 §15.5 isolation rules are applied here).
        from .identity_classification_preflight import run_classification_preflight
        preflight_stats = run_classification_preflight(db)

        candidate_filter_stats: dict[str, int] = {}
        candidates = select_nightly_candidates(db, filter_stats=candidate_filter_stats)
        deactivate_candidates = select_deactivate_candidates(db)
        # 186 I2/I3：双来源分批状态对账。覆盖 employee-only 增量路径看不见的
        # SYS_USER-only 变化与存量积压；desired=disabled 的人员同时从 create
        # 候选中排除（select_nightly_candidates 已过滤）。
        account_state_actions = select_account_state_actions(
            db, run_id=run_id, captured_since=collection_started_at
        )
        as_window = account_state_actions.get("window") or {}
        if settings.identity_dual_source_enforce and account_state_actions["enforce"]:
            # 双来源路径接管员工停用场景（双目标），旧 employee-only JHEMR
            # 单目标路径跳过同一批人，避免对同一人重复写目标。
            # P0-20：去重覆盖本窗执行集 + 批准范围内全部 disabled 判定人员。
            approved_disabled = set(approved_disable_persons(db))
            all_decided_disabled = {
                code for code, decision in _latest_decisions_by_person(db).items()
                if decision.desired_state == "disabled"
            }
            decided_disabled = (
                {entry["person_code"] for entry in account_state_actions["disables"]}
                | (approved_disabled & all_decided_disabled)
            )
            deactivate_candidates = [
                c for c in deactivate_candidates if c["emp_no"] not in decided_disabled
            ]
        run_record.candidates_total = len(candidates)
        run_record.candidates_deactivate = len(deactivate_candidates) + len(account_state_actions["disables"])

        has_account_state_work = bool(
            account_state_actions["disables"] or account_state_actions["enables"]
        )
        # §13.5：早退口径只看采集完整性（截断/缺页/来源不完整）；unknown/
        # missing/积压是报告事实，不是夜跑异常——预算满的空窗是正常夜。
        has_unresolved = bool(
            account_state_actions.get("truncated")
            or account_state_actions.get("remaining")
            or account_state_actions.get("blocked_incomplete")
            or candidate_filter_stats.get("blocked_no_decision")
            or not source_complete
        )
        if not candidates and not deactivate_candidates and not has_account_state_work:
            # P0-5：仍有 blocked/truncated/remaining/来源不完整时不得记普通 success。
            run_record.status = "success" if not has_unresolved else "partial"
            run_record.success_count = 0
            run_record.failed_count = 0
            run_record.skipped_count = 0
            run_record.finished_at = _now()
            run_record.report_summary = {
                "note": "observe_zero_write" if run_mode == "observe" else (
                    "no_candidates" if not has_unresolved else "no_executable_candidates_with_unresolved"
                ),
                "run_mode": run_mode,
                "total": 0,
                "deactivate": 0,
                "preflight": preflight_stats,
                "collection": collection_stats,
                "candidate_filter": candidate_filter_stats,
                "account_state": account_state_actions,
            }
            db.commit()
            return {
                "status": run_record.status, "run_id": run_id, "candidates": 0, "deactivate": 0,
                "success_count": 0, "failed_count": 0, "skipped_count": 0,
                "preflight": preflight_stats, "run_mode": run_mode,
            }

        # 186 v1.10 §13.2：目标时钟只读采样（工程默认关闭，生产 observe 期开启；
        # 采样失败只降级 clock_health，不影响 disable-only 审计）。
        clock_health_report: dict[str, Any] = {"sampled": False, "reason": "sampling_disabled"}
        if getattr(settings, "identity_clock_sampling_enabled", False):
            try:
                from .identity_clock_health import evaluate_clock_health, _adapter_query_builder
                health = evaluate_clock_health(
                    jhemr_query=_adapter_query_builder("JHEMR"),
                    cdms_query=_adapter_query_builder("CDMS"),
                )
                clock_health_report = health.to_report()
            except Exception as exc:  # noqa: BLE001
                clock_health_report = {"sampled": False, "reason": f"{type(exc).__name__}"}

        # PREFLIGHT: threshold checks with real change composition
        # W10 方案 C：先做 JHEMR 存在性检查（失败→None→全部按真实新建保守处理）
        jhemr_existing = _fetch_jhemr_existing_emp_nos(candidates)
        stats = _compute_change_stats(db, candidates, jhemr_existing=jhemr_existing)
        # P0-20：阈值判定用本窗实际计划集（≤20），全体积压单列不隐去。
        stats["deactivate"] = len(deactivate_candidates) + len(account_state_actions["disables"])
        stats["account_state_backlog_pending"] = account_state_actions.get("backlog_pending", 0)
        stats["account_state_backlog_unapproved"] = account_state_actions.get("backlog_unapproved", 0)
        stats["account_state_enable"] = len(account_state_actions["enables"])
        stats["account_state_blocked_unknown"] = account_state_actions.get("blocked_unknown", 0)
        stats["account_state_blocked_protected"] = account_state_actions.get("blocked_protected", 0)
        stats["account_state_truncated"] = int(account_state_actions.get("truncated", False))
        stats["align_check"] = "ok" if jhemr_existing is not None else "failed_fallback_all_new"
        threshold_result = check_thresholds(candidates + deactivate_candidates, stats)
        if threshold_result.get("triggered"):
            run_record.status = "failed"
            run_record.circuit_breaker_triggered = True
            run_record.circuit_breaker_dimension = threshold_result["dimension"]
            run_record.report_summary = {
                "threshold": threshold_result,
                "stats": {k: v for k, v in stats.items() if k != "watermark_gap_hours"},
            }
            run_record.finished_at = _now()
            db.commit()
            try:
                from .identity_sync_audit import record_alert
                record_alert(db, run_id=run_id, alert_type="circuit_breaker_open", severity="error", error_class=threshold_result["dimension"], detail={"dimension": threshold_result["dimension"]})
            except Exception:
                pass
            return {"status": "failed", "reason": "threshold_exceeded", "dimension": threshold_result["dimension"], "run_id": run_id}

        # PLAN + APPLY。186 v1.10 P0-19：observe 全身份零写；disable_only
        # 仅执行双来源 disable（旧 create/align/legacy-lock 路径不执行）；
        # full 保留旧全量行为（仅隔离测试）。
        success_count = 0
        failed_count = 0
        skipped_count = 0
        deactivate_success = 0
        deactivate_failed = 0
        deactivate_skipped = 0

        legacy_apply_allowed = run_mode == "full"

        if legacy_apply_allowed:
            for candidate in deactivate_candidates:
                result = _process_deactivate_candidate(db, candidate, run_id)
                if result["status"] == "success":
                    deactivate_success += 1
                    success_count += 1
                elif result["status"] == "skipped":
                    deactivate_skipped += 1
                    skipped_count += 1
                else:
                    deactivate_failed += 1
                    failed_count += 1

            for candidate in candidates:
                result = _process_single_candidate(db, candidate, run_id, reconcile_existing=True)
                if result["status"] == "success":
                    success_count += 1
                elif result["status"] == "skipped":
                    skipped_count += 1
                else:
                    failed_count += 1
        else:
            # observe/disable_only：旧路径计划集保留在报告，零目标写入。
            skipped_count += len(deactivate_candidates) + len(candidates)

        # 186 I3：双目标账号启停（disable 先于 enable；每目标独立事务，
        # 部分成功记 partial，不并入 create/align 的成败口径）。
        as_success = 0
        as_failed = 0
        as_skipped = 0
        as_partial = 0
        as_blocked = 0
        # P1-7：状态分类分离（already_desired / target_missing / blocked 不互吞）。
        as_target_results: dict[str, dict[str, str]] = {}
        for entry in account_state_actions["disables"] + account_state_actions["enables"]:
            result = _process_account_state_person(db, entry, run_id)
            person_code = entry["person_code"]
            as_target_results[person_code] = result.get("targets") or {}
            if result["status"] == "success":
                as_success += 1
            elif result["status"] in {"skipped", "already_desired"}:
                as_skipped += 1
            elif result["status"] == "partial":
                as_partial += 1
            elif result["status"] in {"failed", "blocked"}:
                as_blocked += 1
            # 预算名额按最终结果持久标记（同对象重试不重复占额）。
            if as_window.get("window_key"):
                mark_reservation(
                    db, window_key=as_window["window_key"], person_code=person_code,
                    status="executed" if result["status"] == "success" else (
                        "failed" if result["status"] in {"failed", "partial"} else "reserved"
                    ),
                )
        # §13.5/P0-8：熔断与 failed_count 只反映真实目标写失败（failed/
        # pending_reconcile）；target_missing/partial 是可审计数据状态，
        # 不得推高熔断（否则缺失对象会让后续窗口全部被熔断饿死）。
        as_failed = sum(
            1 for targets in as_target_results.values()
            if any(v in {"failed", "pending_reconcile"} for v in targets.values())
        )
        success_count += as_success
        skipped_count += as_skipped
        failed_count += as_failed

        # RECONCILE + REPORT
        run_record.success_count = success_count
        run_record.failed_count = failed_count
        run_record.skipped_count = skipped_count
        run_record.candidates_new = stats["new"]

        if failed_count > 0 and success_count > 0:
            failure_rate = failed_count / (success_count + failed_count)
            if failure_rate > settings.identity_cb_max_failure_rate:
                run_record.circuit_breaker_triggered = True
                run_record.circuit_breaker_dimension = "failure_rate"

        # P1-7/P0-5：状态聚合分离 failed/blocked/partial/target_missing/
        # already_desired；as_blocked 不吞 failed；本窗结果与全量积压分别呈现。
        as_actual_updated = sum(
            1 for targets in as_target_results.values()
            if any(v == "success" for v in targets.values())
        )
        as_target_success = sum(1 for targets in as_target_results.values() for v in [targets.get("JHEMR"), targets.get("CDMS")] if v == "success")
        as_target_missing = sum(
            1 for targets in as_target_results.values()
            if any(v == "target_missing" for v in targets.values())
        )
        as_already_desired = sum(
            1 for targets in as_target_results.values()
            if all(v in {None, "already_desired"} for v in targets.values()) and targets
        )
        run_record.status = "success" if failed_count == 0 else "failed"
        if failed_count == 0 and (
            account_state_actions.get("truncated")
            or not source_complete
            or as_target_missing > 0
            or as_blocked > 0
        ):
            # P0-6/§13.5：来源不完整/截断/目标缺失/保护阻断不记普通 success
            # （partial），但其中仅 target_missing/blocked 不推高熔断。
            run_record.status = "partial"
        run_record.finished_at = _now()
        report_summary_account_state = {
            "rule_version": "dual_source_v1",
            "disable_persons": len(account_state_actions["disables"]),
            "enable_persons": len(account_state_actions["enables"]),
            "success": as_success,
            "partial": as_partial,
            "failed": as_failed,
            "skipped": as_skipped,
            "blocked": as_blocked,
            "actual_updated_persons": as_actual_updated,
            "target_success_actions": as_target_success,
            "target_missing_persons": as_target_missing,
            "already_desired_persons": as_already_desired,
            "blocked_unknown": account_state_actions.get("blocked_unknown", 0),
            "blocked_incomplete": account_state_actions.get("blocked_incomplete", 0),
            "blocked_no_person": account_state_actions.get("blocked_no_person", 0),
            "blocked_conflict": account_state_actions.get("blocked_conflict", 0),
            "blocked_protected": account_state_actions.get("blocked_protected", 0),
            "backlog_pending": account_state_actions.get("backlog_pending", 0),
            "backlog_unapproved": account_state_actions.get("backlog_unapproved", 0),
            "backlog_missing_retry": account_state_actions.get("backlog_missing_retry", 0),
            "missing_recovered": account_state_actions.get("missing_recovered", 0),
            "deferred_budget": account_state_actions.get("deferred_budget", 0),
            "unchanged": account_state_actions.get("unchanged", 0),
            "population": account_state_actions.get("population", 0),
            "scanned": account_state_actions.get("scanned", 0),
            "truncated": account_state_actions.get("truncated", False),
            "remaining": account_state_actions.get("remaining", 0),
            "window": as_window,
            "protection": account_state_actions.get("protection"),
            "enable_readiness": "closed_no_ownership_contract",
        }
        run_record.report_summary = {
            "run_mode": run_mode,
            "total": len(candidates),
            "success": success_count,
            "failed": failed_count,
            "skipped": skipped_count,
            "deactivate": len(deactivate_candidates),
            "deactivate_success": deactivate_success,
            "deactivate_failed": deactivate_failed,
            "deactivate_skipped": deactivate_skipped,
            "collection": collection_stats,
            "clock_health": clock_health_report,
            "candidate_filter": candidate_filter_stats,
            "account_state": report_summary_account_state,
        }

        # P0-6：来源不完整不得推进来源水位（截断/权限错误与完整快照可审计区分）。
        watermark_rows = candidates + deactivate_candidates
        if failed_count == 0 and source_complete and watermark_rows:
            candidate_wm = max_watermark(
                [
                    (datetime.fromisoformat(c["modified_time"]) if c.get("modified_time") else None,
                     compute_account_fingerprint(c.get("emp_no"), "HIS", settings.identity_hmac_key_ref))
                    for c in watermark_rows
                ]
            )
            advance_watermark(
                db,
                source_code="HIS",
                watermark_key="main_account_sync",
                candidate=candidate_wm,
                run_id=run_id,
                success=True,
                commit=False,
            )

        # Update circuit breakers
        if failed_count == 0:
            record_success(db, "nightly_cdms")
            record_success(db, "nightly_jhemr")
        else:
            record_failure(db, "nightly_cdms")
            record_failure(db, "nightly_jhemr")

        db.commit()
        return {
            "status": run_record.status,
            "run_id": run_id,
            "candidates": len(candidates),
            "deactivate": len(deactivate_candidates),
            "success": success_count,
            "failed": failed_count,
            "skipped": skipped_count,
            "success_count": success_count,
            "failed_count": failed_count,
            "skipped_count": skipped_count,
            # 186 v1.10 T59：runner/subtask 摘要与 run_record.report_summary
            # 同口径呈现模式与账号状态分段（redacted_summary 透传）。
            "run_mode": run_mode,
            "account_state": report_summary_account_state,
            "source_complete": source_complete,
            "clock_health": clock_health_report,
        }

    except Exception as exc:
        # Any exception after candidate calculation must also discard an
        # uncommitted watermark candidate; failed runs never advance it.
        from .data_masking import sanitize_text

        db.rollback()
        run_record.status = "failed"
        run_record.error_message = sanitize_text(
            f"{type(exc).__name__}: {exc}", limit=300
        )
        run_record.finished_at = _now()
        record_failure(db, "nightly_cdms")
        record_failure(db, "nightly_jhemr")
        db.commit()
        logger.exception("Nightly pipeline failed: %s", run_id)
        return {
            "status": "failed",
            "run_id": run_id,
            "error": sanitize_text(f"{type(exc).__name__}", limit=200),
        }

    finally:
        release_lock(db, lock_key)
        db.commit()


def _process_deactivate_candidate(db: Session, candidate: dict, run_id: str) -> dict[str, Any]:
    """Lock the matching JHEMR login when HIS has disabled the employee."""
    emp_no = candidate["emp_no"]
    fp_jhemr = compute_account_fingerprint(emp_no, "JHEMR", settings.identity_hmac_key_ref)
    batch_id = f"NTL-{run_id}-L{uuid.uuid4().hex[:8]}"
    batch = IdentitySyncBatch(
        batch_id=batch_id,
        batch_type="nightly",
        scheduler_run_id=run_id,
        emp_no_masked=None,
        account_fingerprint=fp_jhemr,
        person_classification=candidate.get("classification"),
        status="applying",
        template_version=TEMPLATE_VERSION,
        idempotency_key=f"{batch_id}:{fp_jhemr}:lock",
        started_at=_now(),
    )
    db.add(batch)
    db.flush()
    action = IdentitySyncAction(
        batch_id=batch_id,
        action_seq=1,
        target_system="JHEMR",
        action_type="account_lock",
        target_table="jhemr.users",
        emp_no_masked=emp_no,
        account_fingerprint=fp_jhemr,
        params_summary={
            "run_id": run_id,
            "subtask": "main_account_sync",
            "action": "jhemr_account_lock",
            **{key: value for key, value in _person_trace(db, emp_no).items() if value},
        },
        subtask_code="main_account_sync",
        status="planned",
    )
    db.add(action)
    db.flush()

    # P0-11：旧 employee-only JHEMR 停用路径同样经唯一 dispatch（执行器
    # 注册/用途绑定/范围/预算/保护全门禁）；不再直接 import bridge。
    result = dispatch_identity_state_action(
        db,
        target_system="JHEMR",
        action="disable",
        person_code=emp_no,
        run_id=run_id,
    )
    status = result.get("status")
    if status == "success":
        action.status = "executed"
        action.rows_affected = int(result.get("rows_affected") or 1)
        batch.status = "success"
        batch.jhemr_status = "success"
        managed = db.scalar(
            select(IdentityManagedRelation).where(
                IdentityManagedRelation.target_system == "JHEMR",
                IdentityManagedRelation.account_fingerprint == fp_jhemr,
            )
        )
        if managed is not None:
            managed.status = "deactivated"
    elif status == "skipped":
        action.status = "skipped"
        action.reason_code = result.get("reason") or "already_locked"
        batch.status = "skipped"
        batch.jhemr_status = "skipped"
    elif status == "missing_target":
        action.status = "skipped"
        action.reason_code = "no_target_user"
        batch.status = "skipped"
        batch.jhemr_status = "skipped"
    elif status == "blocked":
        # 门禁阻断（run mode/执行器/范围等）：平台侧如实记录，零目标连接。
        action.status = "skipped"
        action.reason_code = result.get("reason") or "blocked_gates"
        batch.status = "skipped"
        batch.jhemr_status = "skipped"
    else:
        action.status = "failed"
        action.error_class = "target_write"
        action.error_code_masked = error_code_masked(result.get("error"))
        batch.status = "failed"
        batch.jhemr_status = "failed"
    action.executed_at = _now()
    batch.finished_at = _now()
    db.flush()
    if status == "success":
        return {"status": "success"}
    if status in {"skipped", "missing_target", "blocked"}:
        return {"status": "skipped", "reason": result.get("reason") or status}
    return {"status": "failed", "error": result.get("error")}


def _process_single_candidate(db: Session, candidate: dict, run_id: str, max_retries: int | None = None, reconcile_existing: bool = False) -> dict[str, Any]:
    """Process one candidate against both targets independently.

    Each target (CDMS, JHEMR) is an independent transaction.
    One target failure does not affect the other.
    Retries up to max_retries on transient failures (plan 107 section 3).
    """
    if max_retries is None:
        max_retries = settings.identity_nightly_max_retries
    emp_no = candidate["emp_no"]
    classification = candidate["classification"]
    dept_codes = candidate["dept_codes"]

    # Compute HMAC fingerprints. Fail closed: if the HMAC key is unavailable
    # the whole run must stop (never fall back to unsalted hashes — staff
    # numbers are low-entropy and enumerable).
    fp_cdms = compute_account_fingerprint(emp_no, "CDMS", settings.identity_hmac_key_ref)
    fp_jhemr = compute_account_fingerprint(emp_no, "JHEMR", settings.identity_hmac_key_ref)

    # Check idempotency - skip if already managed
    existing_cdms = db.scalar(
        select(IdentityManagedRelation).where(
            IdentityManagedRelation.target_system == "CDMS",
            IdentityManagedRelation.account_fingerprint == fp_cdms,
            IdentityManagedRelation.status == "active",
        )
    )
    existing_jhemr = db.scalar(
        select(IdentityManagedRelation).where(
            IdentityManagedRelation.target_system == "JHEMR",
            IdentityManagedRelation.account_fingerprint == fp_jhemr,
            IdentityManagedRelation.status == "active",
        )
    )

    if existing_cdms and existing_jhemr and not reconcile_existing:
        return {"status": "skipped", "reason": "already_managed_both"}

    batch_id = f"NTL-{run_id}-{uuid.uuid4().hex[:8]}"
    batch = IdentitySyncBatch(
        batch_id=batch_id,
        batch_type="nightly",
        scheduler_run_id=run_id,
        # 122: durable identity binding is the target-scoped HMAC only.
        emp_no_masked=None,
        account_fingerprint=fp_cdms,
        person_classification=classification,
        status="applying",
        template_version=TEMPLATE_VERSION,
        idempotency_key=f"{batch_id}:{fp_cdms}",
        started_at=_now(),
    )
    db.add(batch)
    db.flush()

    cdms_ok = bool(existing_cdms)
    jhemr_ok = bool(existing_jhemr)

    def plan_target_action(target_system: str, fingerprint: str) -> IdentitySyncAction:
        action = IdentitySyncAction(
            batch_id=batch_id,
            action_seq=1 if target_system == "CDMS" else 2,
            target_system=target_system,
            action_type="account_sync",
            target_table="identity_target",
            emp_no_masked=emp_no,
            account_fingerprint=fingerprint,
            params_summary={
                "run_id": run_id,
                "subtask": "main_account_sync",
                **{
                    key: value
                    for key, value in {
                        **_person_trace(db, emp_no),
                        "job_title": candidate.get("job_title") or "",
                    }.items()
                    if value
                },
            },
            subtask_code="main_account_sync",
            status="planned",
        )
        db.add(action)
        db.flush()
        return action

    def close_target_action(action: IdentitySyncAction, *, status: str, result: dict[str, Any] | None = None, reason: str | None = None) -> None:
        action.status = status
        action.rows_affected = 1 if status == "executed" else 0
        action.reason_code = reason
        if result and status == "failed":
            action.error_class = "target_write"
            action.error_code_masked = error_code_masked(result.get("error"))
        action.error_message = None
        action.executed_at = _now()

    # CDMS target (independent, with limited retry)
    cdms_action = plan_target_action("CDMS", fp_cdms)
    if not cdms_ok:
        for attempt in range(max_retries + 1):
            cdms_result = _apply_cdms_target(db, batch_id, emp_no, classification, dept_codes, fp_cdms, reconcile_existing=reconcile_existing, job_title=candidate.get("job_title"))
            cdms_ok = cdms_result.get("status") == "success"
            if cdms_ok or cdms_result.get("note") == "idempotent_skip":
                cdms_ok = True
                break
            if attempt < max_retries:
                logger.warning("CDMS attempt %d failed for fingerprint=%s, retrying", attempt + 1, short_fingerprint(fp_cdms))
        # 2026-08-20：门禁阻断时 _apply_*_target 返回 success+pending_reconcile
        # （软阻断设计，供下次夜间重试），但动作记录必须如实——记
        # skipped/blocked_gates，不得记成 executed/success。
        cdms_blocked = cdms_ok and cdms_result.get("note") == "pending_reconcile"
        batch.cdms_status = "skipped" if cdms_blocked else ("success" if cdms_ok else cdms_result.get("status", "failed"))
        close_target_action(cdms_action, status="skipped" if cdms_blocked else ("executed" if cdms_ok else "failed"),
                            result=None if cdms_blocked else cdms_result,
                            reason="blocked_gates" if cdms_blocked else None)
    else:
        batch.cdms_status = "skipped"
        close_target_action(cdms_action, status="skipped", reason="already_managed")

    # JHEMR target (independent, with limited retry)
    jhemr_action = plan_target_action("JHEMR", fp_jhemr)
    if not jhemr_ok:
        for attempt in range(max_retries + 1):
            jhemr_result = _apply_jhemr_target(db, batch_id, emp_no, classification, dept_codes, fp_jhemr, reconcile_existing=reconcile_existing, job_title=candidate.get("job_title"))
            jhemr_ok = jhemr_result.get("status") == "success"
            if jhemr_ok or jhemr_result.get("note") == "idempotent_skip":
                jhemr_ok = True
                break
            if attempt < max_retries:
                logger.warning("JHEMR attempt %d failed for fingerprint=%s, retrying", attempt + 1, short_fingerprint(fp_jhemr))
        jhemr_blocked = jhemr_ok and jhemr_result.get("note") == "pending_reconcile"
        batch.jhemr_status = "skipped" if jhemr_blocked else ("success" if jhemr_ok else jhemr_result.get("status", "failed"))
        close_target_action(jhemr_action, status="skipped" if jhemr_blocked else ("executed" if jhemr_ok else "failed"),
                            result=None if jhemr_blocked else jhemr_result,
                            reason="blocked_gates" if jhemr_blocked else None)
    else:
        batch.jhemr_status = "skipped"
        close_target_action(jhemr_action, status="skipped", reason="already_managed")

    # READBACK: verify applied state matches plan (plan 107 pipeline step 5)
    readback_ok = True
    if cdms_ok and batch.cdms_status == "success":
        rb = _readback_cdms_target(db, batch_id, emp_no, fp_cdms)
        if not rb.get("consistent", True):
            readback_ok = False
            batch.cdms_status = "readback_mismatch"
    if jhemr_ok and batch.jhemr_status == "success":
        rb = _readback_jhemr_target(db, batch_id, emp_no, fp_jhemr)
        if not rb.get("consistent", True):
            readback_ok = False
            batch.jhemr_status = "readback_mismatch"

    # Final status
    if cdms_ok and jhemr_ok and readback_ok:
        batch.status = "success"
    elif cdms_ok or jhemr_ok:
        batch.status = "partial_target_success"
    else:
        batch.status = "failed"

    batch.finished_at = _now()
    db.flush()

    return {"status": "success" if (cdms_ok and jhemr_ok and readback_ok) else ("partial" if (cdms_ok or jhemr_ok) else "failed")}


# ---------------------------------------------------------------------------
# Fail-closed write gates (112 B1/B2)
# ---------------------------------------------------------------------------

def _display_name(db: Session, emp_no: str) -> str:
    """Real display name for business-DB writes (never masked emp_no).

    Masking is for logs/audit/API output only; writing a masked value
    (e.g. "12****34") into CDMS/JHEMR display-name columns would corrupt
    production data. Resolves the canonical IdentityPerson.person_name_cn.
    """
    person = db.scalar(select(IdentityPerson).where(IdentityPerson.person_code == emp_no))
    name = person.person_name_cn.strip() if person and person.person_name_cn else ""
    if not name:
        # No real name available: fail closed rather than write a masked value.
        raise RuntimeError("display_name_unavailable; refusing to write masked value")
    return name


def _register_managed(
    db: Session,
    *,
    batch_id: str,
    target_system: str,
    fingerprint: str,
    emp_no: str,
    classification: str,
    dept_codes: list[str],
    role_code: str | None,
    target_table: str,
    action: str,
    idem_key: str,
    status: str,
) -> IdentityManagedRelation:
    """Upsert an IdentityManagedRelation keyed by idempotency_key.

    Used on retries: when a previous failed/gated attempt left a
    pending_reconcile row, re-applying must UPDATE that row (the unique
    constraint on idempotency_key rejects a plain insert) and must NOT
    short-circuit as idempotent_skip.
    """
    existing = db.scalar(
        select(IdentityManagedRelation).where(IdentityManagedRelation.idempotency_key == idem_key)
    )
    data = _strip_sensitive(
        {"classification": classification, "dept_count": len(dept_codes)}
        | ({"role_group": role_code} if role_code else {})
    )
    if existing is not None:
        existing.batch_id = batch_id
        existing.status = status
        existing.account_fingerprint = fingerprint
        existing.relation_data = data
        db.flush()
        return existing
    row = IdentityManagedRelation(
        batch_id=batch_id,
        target_system=target_system,
        account_fingerprint=fingerprint,
        composite_business_key=(
            f"CDMS:FLOGINNAME:fingerprint={fingerprint}" if target_system == "CDMS"
            else f"JHEMR:db_user+hospital_no:fingerprint={fingerprint}"
        ),
        emp_no_masked=None,
        relation_type="account",
        target_table=target_table,
        target_key=fingerprint,
        relation_data=data,
        template_version=TEMPLATE_VERSION,
        action_hash=compute_action_hash(fingerprint, target_system, action, target_table, TEMPLATE_VERSION),
        status=status,
        idempotency_key=idem_key,
    )
    db.add(row)
    db.flush()
    return row

def check_write_gates(db: Session) -> dict[str, Any]:
    """All gates must pass before any business-DB write.

    Fail-closed by construction: the flags default to False/empty, so the
    bridge is never reached unless the operator explicitly confirms each gate.
    """
    from pathlib import Path
    from ..services.credentials import resolve

    def _ref_present(ref: str | None) -> bool:
        if not ref:
            return False
        if ref.startswith("file://"):
            return Path(ref[7:]).is_file()
        if ref.startswith("env:"):
            return bool(resolve(ref)[0])
        return False

    gates: list[dict[str, Any]] = []

    gates.append({
        "gate": "identity_sync_enabled",
        "passed": bool(settings.identity_sync_enabled),
        "detail": "APP_IDENTITY_SYNC_ENABLED must be true for any write",
    })
    gates.append({
        "gate": "hmac_key_present",
        "passed": _ref_present(settings.identity_hmac_key_ref),
        "detail": "identity_hmac.key credential must exist",
    })
    gates.append({
        "gate": "cdms_write_credential_present",
        "passed": _ref_present(settings.identity_sync_cdms_credential_ref),
        "detail": "CDMS write credential file must exist",
    })
    gates.append({
        "gate": "jhemr_write_credential_present",
        "passed": _ref_present(settings.identity_sync_jhemr_credential_ref),
        "detail": "JHEMR write credential file must exist",
    })
    gates.append({
        "gate": "password_write_enabled",
        "passed": bool(settings.identity_jhemr_password_write_enabled),
        "detail": "JHEMR default password write gate (SM4 cross-validated) must be enabled",
    })
    gates.append({
        "gate": "cdms_fid_semantics_confirmed",
        "passed": bool(settings.identity_cdms_fid_semantics_confirmed),
        "detail": "CDMS FID/FUSER/FUPDATEUSER semantics must be confirmed from live DB/vendor evidence",
    })
    gates.append({
        "gate": "cdms_ftype_write_forbidden",
        "passed": bool(settings.identity_cdms_ftype_write_forbidden),
        "detail": "CDMS FTYPE 8/32 writes are permanently forbidden",
    })
    gates.append({
        "gate": "no_delete_actions",
        "passed": True,
        "detail": "identity sync never issues DELETE",
    })
    gates.append({
        "gate": "phase_d_approval_version",
        "passed": bool(settings.identity_phase_d_approval_version),
        "detail": "DBA least-privilege/Phase D approval must be recorded before apply",
    })

    passed = all(g["passed"] for g in gates)
    return {"all_passed": passed, "gates": gates}


def _check_hmac_key_nonempty() -> bool:
    """HMAC key must actually be loadable (not just the file existing)."""
    try:
        from ..services.identity_hmac import _load_hmac_key  # type: ignore
        return bool(_load_hmac_key(settings.identity_hmac_key_ref))
    except Exception:
        return False


def _apply_cdms_target(db: Session, batch_id: str, emp_no: str, classification: str, dept_codes: list[str], fingerprint: str, *, reconcile_existing: bool = False, job_title: str | None = None) -> dict[str, Any]:
    """Apply CDMS target. Independent transaction. INSERT + column-whitelist UPDATE only."""
    role_mapping = _get_role_mapping(db, "CDMS", classification)
    if not role_mapping:
        return {"status": "failed", "error": "CDMS role mapping not configured"}

    idem_key = compute_idempotency_key(fingerprint, "CDMS", "account", "T_MSS_EMP_DICT", TEMPLATE_VERSION)
    # Only an ACTIVE relation is idempotent-skippable. A pending_reconcile row
    # means the write never succeeded, so retries must re-apply (upsert) it.
    existing_by_fp = db.scalar(
        select(IdentityManagedRelation).where(
            IdentityManagedRelation.target_system == "CDMS",
            IdentityManagedRelation.account_fingerprint == fingerprint,
            IdentityManagedRelation.status == "active",
        )
    )
    if existing_by_fp and not reconcile_existing:
        return {"status": "success", "note": "idempotent_skip"}
    existing = db.scalar(
        select(IdentityManagedRelation).where(
            IdentityManagedRelation.idempotency_key == idem_key,
            IdentityManagedRelation.status == "active",
        )
    )
    if existing and not reconcile_existing:
        return {"status": "success", "note": "idempotent_skip"}

    pending = db.scalar(
        select(IdentityManagedRelation).where(
            IdentityManagedRelation.idempotency_key == idem_key,
            IdentityManagedRelation.status == "pending_reconcile",
        )
    )
    if pending and not reconcile_existing and not check_write_gates(db)["all_passed"]:
        return {"status": "success", "note": "idempotent_skip"}

    # 112 B1/B2：写入门禁（fail-closed）。任一 gate 不过则登记
    # pending_reconcile，绝不触碰业务库。
    gates = check_write_gates(db)
    if not gates["all_passed"]:
        _register_managed(
            db, batch_id=batch_id, target_system="CDMS", fingerprint=fingerprint,
            emp_no=emp_no, classification=classification, dept_codes=dept_codes,
            role_code=None, target_table="T_MSS_EMP_DICT", action="insert_user",
            idem_key=idem_key, status="pending_reconcile",
        )
        failed_gates = [g["gate"] for g in gates["gates"] if not g["passed"]]
        return {
            "status": "success",
            "note": "pending_reconcile",
            "blocked_gates": failed_gates,
        }

    # Gates passed: invoke the white-listed executor bridge (Phase D path).
    from ..services.identity_sync_executor_bridge import execute_cdms_apply
    try:
        display_name = _display_name(db, emp_no)
    except RuntimeError as exc:
        _register_managed(
            db, batch_id=batch_id, target_system="CDMS", fingerprint=fingerprint,
            emp_no=emp_no, classification=classification, dept_codes=dept_codes,
            role_code=None, target_table="T_MSS_EMP_DICT", action="insert_user",
            idem_key=idem_key, status="pending_reconcile",
        )
        return {"status": "failed", "error": str(exc), "note": "display_name_unavailable"}
    primary_dept = dept_codes[0] if dept_codes else ""
    additional = dept_codes[1:] if len(dept_codes) > 1 else []
    result = execute_cdms_apply(
        emp_no=emp_no,
        display_name=display_name,
        classification=classification,
        primary_dept=primary_dept,
        additional_depts=additional,
        job_title=job_title,
    )
    if result.get("status") != "success":
        _register_managed(
            db, batch_id=batch_id, target_system="CDMS", fingerprint=fingerprint,
            emp_no=emp_no, classification=classification, dept_codes=dept_codes,
            role_code=None, target_table="T_MSS_EMP_DICT", action="insert_user",
            idem_key=idem_key, status="pending_reconcile",
        )
        return {"status": "failed", "error": result.get("error") or "cdms apply failed", "note": "bridge_failed"}

    # Readback: confirm target actually has the user before marking active.
    from ..services.identity_sync_executor_bridge import execute_cdms_readback
    readback = execute_cdms_readback(emp_no)
    if readback.get("error"):
        _register_managed(
            db, batch_id=batch_id, target_system="CDMS", fingerprint=fingerprint,
            emp_no=emp_no, classification=classification, dept_codes=dept_codes,
            role_code=None, target_table="T_MSS_EMP_DICT", action="insert_user",
            idem_key=idem_key, status="pending_reconcile",
        )
        return {"status": "failed", "error": f"cdms readback failed: {readback.get('error')}"}

    _register_managed(
        db, batch_id=batch_id, target_system="CDMS", fingerprint=fingerprint,
        emp_no=emp_no, classification=classification, dept_codes=dept_codes,
        role_code=None, target_table="T_MSS_EMP_DICT", action="insert_user",
        idem_key=idem_key, status="active",
    )
    return {"status": "success", "note": "applied_via_bridge"}


def _apply_jhemr_target(db: Session, batch_id: str, emp_no: str, classification: str, dept_codes: list[str], fingerprint: str, *, reconcile_existing: bool = False, job_title: str | None = None) -> dict[str, Any]:
    """Apply JHEMR target. Independent transaction. 6-table creation."""
    role_mapping = _get_role_mapping(db, "JHEMR", classification)
    if not role_mapping:
        return {"status": "failed", "error": "JHEMR role mapping not configured"}

    idem_key = compute_idempotency_key(fingerprint, "JHEMR", "account", "users", TEMPLATE_VERSION)
    # Only an ACTIVE relation is idempotent-skippable. A pending_reconcile row
    # means the write never succeeded, so retries must re-apply (upsert) it.
    existing_by_fp = db.scalar(
        select(IdentityManagedRelation).where(
            IdentityManagedRelation.target_system == "JHEMR",
            IdentityManagedRelation.account_fingerprint == fingerprint,
            IdentityManagedRelation.status == "active",
        )
    )
    if existing_by_fp and not reconcile_existing:
        return {"status": "success", "note": "idempotent_skip"}
    existing = db.scalar(
        select(IdentityManagedRelation).where(
            IdentityManagedRelation.idempotency_key == idem_key,
            IdentityManagedRelation.status == "active",
        )
    )
    if existing and not reconcile_existing:
        return {"status": "success", "note": "idempotent_skip"}


    pending = db.scalar(
        select(IdentityManagedRelation).where(
            IdentityManagedRelation.idempotency_key == idem_key,
            IdentityManagedRelation.status == "pending_reconcile",
        )
    )
    if pending and not reconcile_existing and not check_write_gates(db)["all_passed"]:
        return {"status": "success", "note": "idempotent_skip"}

    gates = check_write_gates(db)
    if not gates["all_passed"]:
        _register_managed(
            db, batch_id=batch_id, target_system="JHEMR", fingerprint=fingerprint,
            emp_no=emp_no, classification=classification, dept_codes=dept_codes,
            role_code=role_mapping["role_code"], target_table="users", action="create_user_full",
            idem_key=idem_key, status="pending_reconcile",
        )
        failed_gates = [g["gate"] for g in gates["gates"] if not g["passed"]]
        return {
            "status": "success",
            "note": "pending_reconcile",
            "blocked_gates": failed_gates,
        }

    from ..services.identity_sync_executor_bridge import execute_jhemr_apply
    try:
        display_name = _display_name(db, emp_no)
    except RuntimeError as exc:
        _register_managed(
            db, batch_id=batch_id, target_system="JHEMR", fingerprint=fingerprint,
            emp_no=emp_no, classification=classification, dept_codes=dept_codes,
            role_code=role_mapping["role_code"], target_table="users", action="create_user_full",
            idem_key=idem_key, status="pending_reconcile",
        )
        return {"status": "failed", "error": str(exc), "note": "display_name_unavailable"}
    primary_dept = dept_codes[0] if dept_codes else ""
    additional = dept_codes[1:] if len(dept_codes) > 1 else []
    result = execute_jhemr_apply(
        emp_no=emp_no,
        display_name=display_name,
        classification=classification,
        primary_dept=primary_dept,
        additional_depts=additional,
        job_title=job_title,
    )
    if result.get("status") != "success":
        _register_managed(
            db, batch_id=batch_id, target_system="JHEMR", fingerprint=fingerprint,
            emp_no=emp_no, classification=classification, dept_codes=dept_codes,
            role_code=role_mapping["role_code"], target_table="users", action="create_user_full",
            idem_key=idem_key, status="pending_reconcile",
        )
        return {"status": "failed", "error": result.get("error") or "jhemr apply failed", "note": "bridge_failed"}

    from ..services.identity_sync_executor_bridge import execute_jhemr_readback
    readback = execute_jhemr_readback(emp_no)
    if readback.get("error"):
        _register_managed(
            db, batch_id=batch_id, target_system="JHEMR", fingerprint=fingerprint,
            emp_no=emp_no, classification=classification, dept_codes=dept_codes,
            role_code=role_mapping["role_code"], target_table="users", action="create_user_full",
            idem_key=idem_key, status="pending_reconcile",
        )
        return {"status": "failed", "error": f"jhemr readback failed: {readback.get('error')}"}

    _register_managed(
        db, batch_id=batch_id, target_system="JHEMR", fingerprint=fingerprint,
        emp_no=emp_no, classification=classification, dept_codes=dept_codes,
        role_code=role_mapping["role_code"], target_table="users", action="create_user_full",
        idem_key=idem_key, status="active",
    )
    return {"status": "success", "note": "applied_via_bridge"}




# ---------------------------------------------------------------------------
# Readback verification (plan 107 pipeline step 5)
# -------------------------------------------------------------------------------

def _readback_cdms_target(db: Session, batch_id: str, emp_no: str, fingerprint: str) -> dict[str, Any]:
    """Verify CDMS managed relation was registered correctly.

    In Phase B (no production writes), this verifies platform-side registration.
    In Phase D, the executor bridge performs actual target readback.
    """
    managed = db.scalar(
        select(IdentityManagedRelation).where(
            IdentityManagedRelation.batch_id == batch_id,
            IdentityManagedRelation.target_system == "CDMS",
            IdentityManagedRelation.account_fingerprint == fingerprint,
        )
    )
    if managed is None:
        return {"consistent": False, "reason": "managed_relation_missing"}
    if managed.status == "pending_reconcile":
        return {"consistent": True, "note": "pending_reconcile_expected_in_phase_b"}
    return {"consistent": True}


def _readback_jhemr_target(db: Session, batch_id: str, emp_no: str, fingerprint: str) -> dict[str, Any]:
    """Verify JHEMR managed relation was registered correctly.

    In Phase B (no production writes), this verifies platform-side registration.
    In Phase D, the executor bridge performs actual target readback via
    execute_jhemr_readback() which snapshots all 6 tables.
    """
    managed = db.scalar(
        select(IdentityManagedRelation).where(
            IdentityManagedRelation.batch_id == batch_id,
            IdentityManagedRelation.target_system == "JHEMR",
            IdentityManagedRelation.account_fingerprint == fingerprint,
        )
    )
    if managed is None:
        return {"consistent": False, "reason": "managed_relation_missing"}
    if managed.status == "pending_reconcile":
        return {"consistent": True, "note": "pending_reconcile_expected_in_phase_b"}
    return {"consistent": True}


# ---------------------------------------------------------------------------
# Validation mode: doctor_nurse_dual_target_v1 (plan 107 section 9)
# ---------------------------------------------------------------------------

def run_validation_batch(db: Session) -> dict[str, Any]:
    """Execute the fixed doctor_nurse_dual_target_v1 validation batch.

    Selects one doctor and one nurse who do NOT exist in either CDMS or JHEMR.
    Fixed max 2 persons, 4 target actions. No third person allowed.
    """
    candidates = select_nightly_candidates(db)

    # Find one doctor and one nurse not in either target
    doctor = None
    nurse = None
    for c in candidates:
        if c["classification"] == "doctor" and doctor is None:
            doctor = c
        elif c["classification"] == "nurse" and nurse is None:
            nurse = c
        if doctor and nurse:
            break

    if not doctor or not nurse:
        return {"status": "blocked_no_candidate", "reason": "No eligible doctor or nurse found absent from both targets"}

    run_id = f"VAL-{uuid.uuid4().hex[:12]}"
    batch_id = f"VALB-{uuid.uuid4().hex[:8]}"

    run_record = IdentitySchedulerRun(
        run_id=run_id,
        triggered_by="validation",
        status="running",
        started_at=_now(),
    )
    db.add(run_record)

    # Create validation batch
    batch = IdentitySyncBatch(
        batch_id=batch_id,
        batch_type="validation",
        validation_mode="doctor_nurse_dual_target_v1",
        scheduler_run_id=run_id,
        status="applying",
        template_version=TEMPLATE_VERSION,
        idempotency_key=f"validation:{run_id}",
        started_at=_now(),
    )
    db.add(batch)
    db.flush()

    # Execute 4 target actions in order: doctor-CDMS, doctor-JHEMR, nurse-CDMS, nurse-JHEMR
    results = []
    execution_order = [
        ("doctor", "CDMS", doctor),
        ("doctor", "JHEMR", doctor),
        ("nurse", "CDMS", nurse),
        ("nurse", "JHEMR", nurse),
    ]

    paused = False
    for role, target, person in execution_order:
        if paused:
            results.append({"role": role, "target": target, "status": "paused"})
            continue

        fp = compute_account_fingerprint(person["emp_no"], target, settings.identity_hmac_key_ref)
        if target == "CDMS":
            result = _apply_cdms_target(db, batch_id, person["emp_no"], person["classification"], person["dept_codes"], fp)
        else:
            result = _apply_jhemr_target(db, batch_id, person["emp_no"], person["classification"], person["dept_codes"], fp)

        results.append({"role": role, "target": target, "status": result.get("status"), "account_fingerprint": short_fingerprint(fp)})

        if result.get("status") == "failed":
            paused = True

    # Determine overall status
    statuses = [r["status"] for r in results]
    if all(s == "success" for s in statuses):
        batch.status = "success"
        run_record.status = "success"
    elif any(s == "success" for s in statuses):
        batch.status = "partial_target_success"
        run_record.status = "failed"
    else:
        batch.status = "failed"
        run_record.status = "failed"

    batch.finished_at = _now()
    run_record.finished_at = _now()
    run_record.report_summary = {"validation_mode": "doctor_nurse_dual_target_v1", "results": results}
    db.commit()

    return {
        "status": batch.status,
        "run_id": run_id,
        "batch_id": batch_id,
        "validation_mode": "doctor_nurse_dual_target_v1",
        "results": results,
        "max_persons": 2,
        "max_actions": 4,
    }


# ---------------------------------------------------------------------------
# Gate checks
# ---------------------------------------------------------------------------

def run_gate_checks(db: Session) -> dict[str, Any]:
    """Run all pre-execution gate checks for nightly enablement."""
    gates: list[dict[str, Any]] = []

    gates.append({"gate": "identity_sync_enabled", "passed": bool(settings.identity_sync_enabled), "detail": "APP_IDENTITY_SYNC_ENABLED"})
    gates.append({"gate": "nightly_disabled_by_default", "passed": not settings.identity_nightly_enabled, "detail": "APP_IDENTITY_NIGHTLY_ENABLED must be false until Phase D passes"})

    cdms_mappings = db.scalars(select(IdentityRoleMapping).where(IdentityRoleMapping.target_system == "CDMS", IdentityRoleMapping.is_active.is_(True))).all()
    jhemr_mappings = db.scalars(select(IdentityRoleMapping).where(IdentityRoleMapping.target_system == "JHEMR", IdentityRoleMapping.is_active.is_(True))).all()
    gates.append({"gate": "role_mappings_configured", "passed": len(cdms_mappings) >= 3 and len(jhemr_mappings) >= 3, "detail": f"CDMS={len(cdms_mappings)}, JHEMR={len(jhemr_mappings)}"})

    active_batch = db.scalar(select(IdentitySyncBatch).where(IdentitySyncBatch.status.in_(["applying", "confirmed"])))
    gates.append({"gate": "no_active_batch", "passed": active_batch is None, "detail": "No batch in applying state"})

    cb_cdms = check_circuit_breaker(db, "nightly_cdms")
    cb_jhemr = check_circuit_breaker(db, "nightly_jhemr")
    gates.append({"gate": "circuit_breakers_closed", "passed": not cb_cdms["open"] and not cb_jhemr["open"], "detail": f"CDMS={cb_cdms['consecutive_failures']}, JHEMR={cb_jhemr['consecutive_failures']}"})

    # 112 B1/B2：写入门禁（fail-closed）。任一不满足则整批不写。
    write_gates = check_write_gates(db)
    gates.append({
        "gate": "write_gates",
        "passed": write_gates["all_passed"],
        "detail": "; ".join(f"{g['gate']}={'pass' if g['passed'] else 'FAIL'}" for g in write_gates["gates"]),
    })

    all_passed = all(g["passed"] for g in gates)
    return {"all_passed": all_passed, "gates": gates}
