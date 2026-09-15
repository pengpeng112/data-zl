"""186 v1.10：身份目标写动作唯一 dispatch/gate（P0-7/P0-11/P0-14/P0-18/P0-19）。

设计要点：
- 编排器不再直接 import 桥接执行函数；四类身份状态动作（JHEMR/CDMS ×
  disable/enable）只能经 ``dispatch_identity_state_action``。桥接内部再次
  fail-closed（直接调用 bridge 也必须过同一门禁）。
- 门禁链：运行模式 → 执行器注册（asset_action_executors，默认 disabled）→
  Phase D 批准引用 → source registry 用途绑定（(source_code,purpose) 专属写
  引用，零 env/字典 fallback）→ 批准范围（冻结名单，token 不是名单）→
  每窗持久预算（≤20 唯一人员）→ 保护映射（HMAC 候选法，§4.6.4-9/-10）。
- observe 模式对本次身份写全为 0（含旧 create/align/login/sign/lock 入口，
  见 ``gate_legacy_identity_write``）；disable_only 仅两个 disable 且逐对象
  属有效批准范围。
- 门禁失败只写平台 blocked 审计/attempt，不创建目标连接、零目标写入。
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.config import settings
from ..models.governance_base import AssetActionExecutor
from ..models.asset_system import AssetSourcePurposeBinding
from ..models.identity_sync import (
    IdentityApprovedScope,
    IdentityApprovedScopeMember,
    IdentityManagedRelation,
    IdentityProtectedAccount,
    IdentityWindowBudget,
    IdentityWindowReservation,
)
from .identity_hmac import compute_account_fingerprint
from .identity_clock_health import (
    AUTOMATIC_ENABLE_SUPPORTED,
    AUTOMATIC_ENABLE_UNSUPPORTED_REASONS,
)

# 四类身份状态执行器（迁移 e8f9a0b1c2d3 种子，默认 disabled）
ACTION_JHEMR_DISABLE = "JHEMR_ACCOUNT_DISABLE"
ACTION_JHEMR_ENABLE = "JHEMR_ACCOUNT_ENABLE"
ACTION_CDMS_DISABLE = "CDMS_ACCOUNT_DISABLE"
ACTION_CDMS_ENABLE = "CDMS_ACCOUNT_ENABLE"

IDENTITY_STATE_ACTIONS = {
    ACTION_JHEMR_DISABLE,
    ACTION_JHEMR_ENABLE,
    ACTION_CDMS_DISABLE,
    ACTION_CDMS_ENABLE,
}

# 用途绑定（P0-18）：身份状态同步专属写用途；不覆盖字典推送策略。
IDENTITY_PURPOSE = "identity_account_sync"

# 目标系统 → 允许的执行器（target/source 绑定一致性检查）
_TARGET_ACTIONS = {
    "JHEMR": {ACTION_JHEMR_DISABLE, ACTION_JHEMR_ENABLE},
    "CDMS": {ACTION_CDMS_DISABLE, ACTION_CDMS_ENABLE},
}

VALID_RUN_MODES = {"observe", "disable_only", "full"}

# 旧入口写动作种类（gate_legacy_identity_write 用）
LEGACY_WRITE_KINDS = {
    "cdms_apply", "jhemr_apply", "jhemr_lock", "jhemr_password_reset",
    "login_sign_sync", "education_title_sync",
    "jhemr_signature_sync", "jhemr_dept_sync",
}

# 189：属性对账类旧入口——只给**已存在**的目标账号补登录/签名方式、职称、
# 签名图片、科室，不建号、不启用、不改锁；建号/锁定/改密类永不在此放行。
RECONCILE_WRITE_KINDS = {
    "login_sign_sync", "education_title_sync",
    "jhemr_signature_sync", "jhemr_dept_sync",
}


def current_run_mode() -> str:
    mode = str(getattr(settings, "identity_run_mode", "observe") or "observe").strip().lower()
    return mode if mode in VALID_RUN_MODES else "observe"


def disable_only_allowed_reconcile_kinds() -> set[str]:
    """逗号分隔白名单 ∩ 对账类 kind；观察模式不适用，账号状态类入口忽略。"""
    raw = str(getattr(settings, "identity_disable_only_allowed_legacy_kinds", "") or "")
    configured = {item.strip() for item in raw.split(",") if item.strip()}
    return configured & RECONCILE_WRITE_KINDS


@dataclass
class GateDecision:
    allowed: bool
    reason: str
    executor_code: str | None = None
    approval_ref: str | None = None
    credential_ref: str | None = None
    source_code: str | None = None
    target_system: str | None = None
    scope_type: str | None = None
    window_key: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "executor_code": self.executor_code,
            "approval_ref": self.approval_ref,
            "credential_ref": self.credential_ref,
            "source_code": self.source_code,
            "target_system": self.target_system,
            "scope_type": self.scope_type,
            "window_key": self.window_key,
            **({"details": self.details} if self.details else {}),
        }


def _blocked(reason: str, **kwargs: Any) -> GateDecision:
    return GateDecision(allowed=False, reason=reason, **kwargs)


# ---------------------------------------------------------------------------
# 保护映射（P0-7 / §4.6.4-9/-10：HMAC 候选法，不反解指纹）
# ---------------------------------------------------------------------------

def protected_fingerprints_by_target(db: Session) -> dict[str, set[str]]:
    """每目标的受保护账号指纹集合 = {HMAC(account_id, target)}。

    人员指纹 = HMAC(person_code, target)，与保护候选指纹全等比较即完成
    "人员→目标实际唯一键→保护登记二元键" 的映射核对；不反解 HMAC、不把
    target_key 当明文账号。
    """
    result: dict[str, set[str]] = {"JHEMR": set(), "CDMS": set()}
    rows = db.scalars(select(IdentityProtectedAccount)).all()
    for row in rows:
        target = str(row.target_system or "").upper()
        account_id = str(row.account_id or "").strip()
        if target in result and account_id:
            result[target].add(compute_account_fingerprint(account_id, target, settings.identity_hmac_key_ref))
    return result


def protection_mapping_report(db: Session) -> dict[str, Any]:
    """保护登记的对账摘要：可映射/无法解析行计数（P0-13 报告用）。"""
    managed: dict[str, set[str]] = {"JHEMR": set(), "CDMS": set()}
    for row in db.scalars(select(IdentityManagedRelation.account_fingerprint, IdentityManagedRelation.target_system)).all():
        if row[1] in managed and row[0]:
            managed[row[1]].add(row[0])
    protected = protected_fingerprints_by_target(db)
    resolved = {t: len(protected[t] & managed[t]) for t in protected}
    unresolved = {t: len(protected[t] - managed[t]) for t in protected}
    return {
        "resolved_protection_rows": resolved,
        "unresolved_protection_rows": unresolved,
        "unresolved_is_not_no_protection": True,
    }


def person_is_protected(db: Session, person_code: str) -> tuple[bool, list[str]]:
    """人员级保护（任一目标受保护 → 整人不变更）。HMAC 候选法实现。"""
    protected = protected_fingerprints_by_target(db)
    hits: list[str] = []
    for target in ("JHEMR", "CDMS"):
        fp = compute_account_fingerprint(person_code, target, settings.identity_hmac_key_ref)
        if fp in protected[target]:
            hits.append(target)
    return (len(hits) > 0, hits)


# ---------------------------------------------------------------------------
# 批准范围（P0-19 / §13.5：审批 token 不是名单）
# ---------------------------------------------------------------------------

def approved_scope_membership(db: Session, person_code: str, action: str = "disable") -> dict[str, Any] | None:
    """人员是否属于某 active 批准范围（pilot 显式或 baseline 冻结成员）。

    返回 {"scope_id", "scope_type", "approval_ref"}；不在任何范围 → None。
    新出现的停用人员不自动混入——范围成员只在受控登记/冻结时写入。
    """
    scopes = db.scalars(
        select(IdentityApprovedScope).where(
            IdentityApprovedScope.action == action,
            IdentityApprovedScope.status == "active",
        )
    ).all()
    for scope in scopes:
        member = db.scalar(
            select(IdentityApprovedScopeMember).where(
                IdentityApprovedScopeMember.scope_id == scope.id,
                IdentityApprovedScopeMember.person_code == person_code,
            )
        )
        if member is not None:
            return {
                "scope_id": scope.id,
                "scope_type": scope.scope_type,
                "approval_ref": scope.approval_ref,
            }
    return None


def approved_disable_persons(db: Session) -> dict[str, dict[str, Any]]:
    """全部 active disable 范围成员 {person_code: scope 信息}（选择器用）。"""
    result: dict[str, dict[str, Any]] = {}
    scopes = db.scalars(
        select(IdentityApprovedScope).where(
            IdentityApprovedScope.action == "disable",
            IdentityApprovedScope.status == "active",
        )
    ).all()
    if not scopes:
        return result
    for scope in scopes:
        members = db.scalars(
            select(IdentityApprovedScopeMember).where(IdentityApprovedScopeMember.scope_id == scope.id)
        ).all()
        for member in members:
            result.setdefault(
                member.person_code,
                {"scope_id": scope.id, "scope_type": scope.scope_type, "approval_ref": scope.approval_ref},
            )
    return result


def freeze_baseline_scope(
    db: Session,
    *,
    approval_ref: str,
    members: list[tuple[str, str | None]],
    created_by: str,
    description: str | None = None,
) -> IdentityApprovedScope:
    """冻结基线范围（S4 受控登记路径调用；成员此后不自动扩展）。

    scope_fingerprint = sha256 over sorted person codes，用于对账审计。
    """
    existing = db.scalar(
        select(IdentityApprovedScope).where(
            IdentityApprovedScope.approval_ref == approval_ref,
            IdentityApprovedScope.action == "disable",
            IdentityApprovedScope.scope_type == "baseline",
        )
    )
    if existing is not None:
        raise RuntimeError("baseline_scope_already_frozen; supersede explicitly instead of re-freezing")
    codes = sorted({code for code, _reason in members if code})
    fingerprint = hashlib.sha256(("|".join(codes)).encode("utf-8")).hexdigest()
    scope = IdentityApprovedScope(
        scope_type="baseline",
        approval_ref=approval_ref,
        action="disable",
        scope_fingerprint=fingerprint,
        status="active",
        description=description or f"frozen {len(codes)} members",
        created_by=created_by,
    )
    db.add(scope)
    db.flush()
    for code, reason in members:
        if not code:
            continue
        db.add(IdentityApprovedScopeMember(scope_id=scope.id, person_code=code, frozen_reason=reason))
    db.flush()
    return scope


def register_pilot_scope(
    db: Session,
    *,
    approval_ref: str,
    person_codes: list[str],
    created_by: str,
    description: str | None = None,
) -> IdentityApprovedScope:
    """显式试点人员范围（003740/001554）。"""
    existing = db.scalar(
        select(IdentityApprovedScope).where(
            IdentityApprovedScope.approval_ref == approval_ref,
            IdentityApprovedScope.action == "disable",
            IdentityApprovedScope.scope_type == "pilot",
        )
    )
    if existing is not None:
        raise RuntimeError("pilot_scope_already_registered")
    scope = IdentityApprovedScope(
        scope_type="pilot",
        approval_ref=approval_ref,
        action="disable",
        status="active",
        description=description or f"pilot {len(person_codes)} persons",
        created_by=created_by,
    )
    db.add(scope)
    db.flush()
    for code in person_codes:
        db.add(IdentityApprovedScopeMember(scope_id=scope.id, person_code=code, frozen_reason="pilot"))
    db.flush()
    return scope


# ---------------------------------------------------------------------------
# 每窗持久预算（§13.5：试点/人工重跑/重启/并行任务共享同一份额度）
# ---------------------------------------------------------------------------

def get_or_open_window(db: Session, *, approval_ref: str, now=None) -> IdentityWindowBudget:
    """窗口身份由持久行决定：取最新未关窗；超过 identity_window_hours 才开新窗。

    opened_at 用数据库时钟（func.now() 已在 server_default；此处显式取
    DB now 防本地跳时重算窗口身份）。
    """
    from sqlalchemy import func as sa_func

    window = db.scalar(
        select(IdentityWindowBudget).where(IdentityWindowBudget.closed_at.is_(None))
        .order_by(IdentityWindowBudget.id.desc())
    )
    db_now = db.scalar(select(sa_func.now()))
    opened = window.opened_at if window is not None else None
    if window is not None and opened is not None:
        from datetime import timezone as _tz

        opened_cmp = opened if opened.tzinfo else opened.replace(tzinfo=_tz.utc)
        now_cmp = db_now if db_now.tzinfo else db_now.replace(tzinfo=_tz.utc)
        if (now_cmp - opened_cmp) <= timedelta(hours=max(1, settings.identity_window_hours)):
            return window
        window.closed_at = db_now
        db.flush()
    window_key = f"WIN-{uuid.uuid4().hex[:12]}"
    limit_persons = max(1, int(settings.identity_window_max_persons))
    window = IdentityWindowBudget(
        window_key=window_key,
        approval_ref=approval_ref,
        limit_persons=limit_persons,
        opened_at=db_now,
    )
    db.add(window)
    db.flush()
    return window


def window_reservation_status(db: Session, window: IdentityWindowBudget) -> dict[str, int]:
    rows = db.scalars(
        select(IdentityWindowReservation).where(IdentityWindowReservation.window_id == window.id)
    ).all()
    return {
        "reserved": sum(1 for r in rows if r.status in {"reserved", "executed", "failed"}),
        "executed": sum(1 for r in rows if r.status == "executed"),
        "failed": sum(1 for r in rows if r.status == "failed"),
        "limit": window.limit_persons,
    }


def reserve_window_slot(
    db: Session, *, window: IdentityWindowBudget, person_code: str, action: str, run_id: str | None
) -> str:
    """原子预留一个人员名额。返回 reserved | already | full。

    同一对象同一窗口重试复用名额（不重复占额）；预算满 → full（推迟，不
    隐藏积压）。commit 结果未知的动作保持 reserved（额度保守不释放）。
    """
    # QA ST-024：窗口行 FOR UPDATE 串行化 check-then-act，防并发超卖 identity_window_max_persons。
    window = db.scalar(
        select(IdentityWindowBudget).where(IdentityWindowBudget.id == window.id).with_for_update()
    ) or window
    existing = db.scalar(
        select(IdentityWindowReservation).where(
            IdentityWindowReservation.window_id == window.id,
            IdentityWindowReservation.person_code == person_code,
        )
    )
    if existing is not None:
        existing.run_id = run_id or existing.run_id
        if existing.status == "released":
            existing.status = "reserved"
        db.flush()
        return "already"
    status = window_reservation_status(db, window)
    if status["reserved"] >= window.limit_persons:
        return "full"
    db.add(IdentityWindowReservation(
        window_id=window.id, person_code=person_code, action=action, status="reserved", run_id=run_id
    ))
    db.flush()
    return "reserved"


def mark_reservation(db: Session, *, window_key: str, person_code: str, status: str) -> None:
    window = db.scalar(select(IdentityWindowBudget).where(IdentityWindowBudget.window_key == window_key))
    if window is None:
        return
    row = db.scalar(
        select(IdentityWindowReservation).where(
            IdentityWindowReservation.window_id == window.id,
            IdentityWindowReservation.person_code == person_code,
        )
    )
    if row is not None:
        row.status = status
        db.flush()


# ---------------------------------------------------------------------------
# 门禁评估
# ---------------------------------------------------------------------------

def evaluate_identity_action_gate(
    db: Session,
    *,
    action_code: str,
    person_code: str | None = None,
    approval_ref: str | None = None,
    run_id: str | None = None,
    reserve_budget: bool = True,
    window: IdentityWindowBudget | None = None,
    enable_clock_ok: bool | None = None,
) -> GateDecision:
    """四类身份状态动作的完整门禁链（纯平台内评估，零目标连接）。"""
    if action_code not in IDENTITY_STATE_ACTIONS:
        return _blocked("unknown_action_code", executor_code=action_code)

    mode = current_run_mode()
    if mode == "observe":
        return _blocked("run_mode_observe", executor_code=action_code)
    if mode not in {"disable_only", "full"}:
        return _blocked(f"run_mode_invalid:{mode}", executor_code=action_code)
    if mode == "disable_only" and not action_code.endswith("_DISABLE"):
        return _blocked("run_mode_disable_only_forbids_enable", executor_code=action_code)

    # 全局开关与 Phase D（既有链保留）
    if not settings.identity_sync_enabled:
        return _blocked("identity_sync_disabled", executor_code=action_code)

    executor = db.scalar(select(AssetActionExecutor).where(AssetActionExecutor.executor_code == action_code))
    if executor is None:
        return _blocked("executor_not_registered", executor_code=action_code)
    if not executor.enabled:
        return _blocked("executor_disabled", executor_code=action_code, source_code=executor.target_source_code)

    configured_approval = (settings.identity_phase_d_approval_version or "").strip()
    if not configured_approval:
        return _blocked("phase_d_approval_missing", executor_code=action_code)
    if executor.require_approval and approval_ref != configured_approval:
        return _blocked("phase_d_approval_mismatch", executor_code=action_code)

    target_system = str(executor.target_system_code or "").upper()
    if action_code not in _TARGET_ACTIONS.get(target_system, set()):
        return _blocked("executor_target_mismatch", executor_code=action_code, target_system=target_system)

    # 用途绑定（P0-14/P0-18）：凭据只从 (source_code, purpose) 绑定解析。
    source_code = executor.target_source_code
    binding = db.scalar(
        select(AssetSourcePurposeBinding).where(
            AssetSourcePurposeBinding.source_code == source_code,
            AssetSourcePurposeBinding.purpose == IDENTITY_PURPOSE,
        )
    )
    if binding is None:
        return _blocked("purpose_binding_missing", executor_code=action_code, source_code=source_code)
    if not binding.enabled:
        return _blocked("purpose_binding_disabled", executor_code=action_code, source_code=source_code)
    if not binding.write_credential_ref or (binding.credential_status or "") != "configured":
        return _blocked("purpose_credential_not_configured", executor_code=action_code, source_code=source_code)

    details: dict[str, Any] = {"purpose": IDENTITY_PURPOSE, "source_code": source_code}
    scope_type: str | None = None
    window_key: str | None = None

    if person_code:
        protected, hits = person_is_protected(db, person_code)
        if protected:
            return _blocked("protected_account", executor_code=action_code, target_system=target_system,
                            details={**details, "protected_targets": hits})

    if action_code.endswith("_DISABLE"):
        # 批准范围 + 每窗预算（enable 不占此预算——生产 enable 关闭）
        membership = approved_scope_membership(db, person_code, action="disable") if person_code else None
        if membership is None:
            return _blocked("not_in_approved_scope", executor_code=action_code,
                            target_system=target_system, details=details)
        scope_type = membership["scope_type"]
        if membership["approval_ref"] != configured_approval:
            return _blocked("scope_approval_mismatch", executor_code=action_code, scope_type=scope_type,
                            details={**details, "scope_approval": membership["approval_ref"]})
        if reserve_budget:
            active_window = window or get_or_open_window(db, approval_ref=configured_approval)
            outcome = reserve_window_slot(
                db, window=active_window, person_code=person_code, action="disable", run_id=run_id
            )
            window_key = active_window.window_key
            if outcome == "full":
                return _blocked("window_budget_exhausted", executor_code=action_code, scope_type=scope_type,
                                window_key=window_key, target_system=target_system, details=details)
            details["reservation"] = outcome
    else:
        # enable：§13.3/§13.2 —— 所有权合同缺失 + 时钟前置（生产恒 blocked）。
        if not AUTOMATIC_ENABLE_SUPPORTED:
            return _blocked("automatic_enable_not_supported", executor_code=action_code, target_system=target_system,
                            details=details)
        if enable_clock_ok is False:
            return _blocked("clock_health_gate_failed", executor_code=action_code, target_system=target_system,
                            details=details)
        # enable 也必须在批准范围（独立 enable 批准；当前无 → blocked）
        membership = approved_scope_membership(db, person_code, action="enable") if person_code else None
        if membership is None:
            return _blocked("not_in_approved_enable_scope", executor_code=action_code, target_system=target_system,
                            details=details)

    return GateDecision(
        allowed=True,
        reason="ok",
        executor_code=action_code,
        approval_ref=approval_ref,
        credential_ref=binding.write_credential_ref,
        source_code=source_code,
        target_system=target_system,
        scope_type=scope_type,
        window_key=window_key,
        details=details,
    )


def gate_legacy_identity_write(db: Session | None, kind: str) -> GateDecision:
    """旧身份写入口（create/align/login/sign/旧 JHEMR-only lock 等）的总门禁。

    observe → 全部 blocked；disable_only → 全部 blocked（旧入口不得绕过
    双来源规则单独写目标），例外是 189 白名单按配置放行**属性对账类**子任务
    （仅补已存在账号的方式/职称/签名图片/科室，账号状态类入口仍全部阻断）；
    full → 允许（其余既有门禁继续生效）。
    """
    if kind not in LEGACY_WRITE_KINDS:
        return _blocked("unknown_legacy_kind", details={"kind": kind})
    mode = current_run_mode()
    if mode == "observe":
        return _blocked("run_mode_observe", details={"kind": kind})
    if mode == "disable_only":
        if kind in disable_only_allowed_reconcile_kinds():
            return GateDecision(allowed=True, reason="disable_only_reconcile_allowlist", details={"kind": kind})
        return _blocked("run_mode_disable_only_blocks_legacy_writes", details={"kind": kind})
    return GateDecision(allowed=True, reason="ok", details={"kind": kind})


def read_target_account_state(target_system: str, person_code: str) -> dict[str, Any] | None:
    """只读目标账号状态（漂移回读用；无门禁——只读零写）。

    失败返回 None（调用方按 readback_failed 计数，不推断状态）。测试可
    monkeypatch 本函数避免真实连接。
    """
    try:
        from . import identity_sync_executor_bridge as bridge

        if str(target_system).upper() == "JHEMR":
            result = bridge.execute_jhemr_state_read(person_code)
        else:
            result = bridge.execute_cdms_state_read(person_code)
        if result.get("status") != "ok":
            return None
        return result.get("state") or {}
    except Exception:  # noqa: BLE001 — 回读失败按未知处理，不推断漂移
        return None


# ---------------------------------------------------------------------------
# 唯一 dispatch（编排器入口；不再直接 import bridge）
# ---------------------------------------------------------------------------

def dispatch_identity_state_action(
    db: Session,
    *,
    target_system: str,
    action: str,
    person_code: str,
    run_id: str | None = None,
    approval_ref: str | None = None,
    origin_disable: dict[str, Any] | None = None,
    window: IdentityWindowBudget | None = None,
    enable_clock_ok: bool | None = None,
) -> dict[str, Any]:
    """按目标分发到桥接执行函数；先过完整门禁，失败零目标连接。

    返回桥接结果 dict；门禁失败返回 {"status": "blocked", "reason": ...,
    "gate": {...}}（编排层据此落 blocked attempt 与审计）。
    """
    action_code_by = {
        ("JHEMR", "disable"): ACTION_JHEMR_DISABLE,
        ("JHEMR", "enable"): ACTION_JHEMR_ENABLE,
        ("CDMS", "disable"): ACTION_CDMS_DISABLE,
        ("CDMS", "enable"): ACTION_CDMS_ENABLE,
    }
    key = (str(target_system).upper(), str(action).lower())
    action_code = action_code_by.get(key)
    if action_code is None:
        return {"status": "blocked", "reason": "unknown_target_action", "gate": {"target": key}}

    approval = approval_ref or (settings.identity_phase_d_approval_version or "").strip()
    decision = evaluate_identity_action_gate(
        db,
        action_code=action_code,
        person_code=person_code,
        approval_ref=approval,
        run_id=run_id,
        window=window,
        enable_clock_ok=enable_clock_ok,
    )
    if not decision.allowed:
        return {"status": "blocked", "reason": decision.reason, "gate": decision.as_dict()}

    from . import identity_sync_executor_bridge as bridge

    if action_code == ACTION_JHEMR_DISABLE:
        return bridge.execute_jhemr_lock(
            person_code, credential_ref=decision.credential_ref, approval_ref=approval, gate_decision=decision
        )
    if action_code == ACTION_JHEMR_ENABLE:
        return bridge.execute_jhemr_enable(
            person_code, origin_disable=origin_disable, credential_ref=decision.credential_ref,
            approval_ref=approval, gate_decision=decision,
        )
    if action_code == ACTION_CDMS_DISABLE:
        return bridge.execute_cdms_disable(
            person_code, credential_ref=decision.credential_ref, approval_ref=approval, gate_decision=decision
        )
    return bridge.execute_cdms_enable(
        person_code, origin_disable=origin_disable, credential_ref=decision.credential_ref,
        approval_ref=approval, gate_decision=decision,
    )
