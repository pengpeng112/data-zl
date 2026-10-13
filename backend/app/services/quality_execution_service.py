"""207 A2/A3: 质量执行链领域服务——持久运行单、受控执行、六态观测、可信复测。

职责边界（207 §4）：
  - 数据库持久任务为事实源；HTTP 只创建/查询运行单，不在请求里跑长 SQL
    （隔离/本地演示的 inline 模式除外，由 settings 显式开启）；
  - worker 侧只读执行检测器（quality_rule SQL / 平台元数据规则 / probe 映射 SQL），
    源访问复用 quality_sql_runner（只读校验 + 脱敏 + 错误净化），不新增直连；
  - 每个子运行（检测器）独立留证：观测六态 + attempt 幂等键 + 租约/围栏；
  - 复测结论与状态推进同事务；幂等（重复回调不重复计数/建单/通知）。

执行层区分"运行是否成功"与"数据是否通过"：
  run.status 表达执行生命周期；数据结论在 result_summary.status 与观测六态中。
"""

from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..core.config import settings
from ..models.quality_governance import (
    QualityControl,
    QualityControlDetector,
    QualityControlRevision,
    QualityIssue,
    QualityIssueEvent,
    QualityNotification,
    QualityObservation,
    QualityRun,
)
from . import quality_governance_service as qgs

WORKER_ACTOR = "system:quality_worker"

RUN_STATUSES = (
    "queued", "waiting_window", "running", "succeeded", "partial", "failed", "cancelled", "blocked",
)
RUN_ACTIVE_STATUSES = ("queued", "waiting_window", "running")
RUN_TERMINAL_STATUSES = ("succeeded", "partial", "failed", "cancelled", "blocked")
RECHECK_SUBSTATUSES = ("none", "pending", "passed", "failed", "blocked")
VERIFICATION_POLICIES = ("manual", "auto_recheck_manual_close")
RECHECK_POLICIES = ("auto", "manual")

# 连接类错误（可有限退避重试）；语法/权限/口径问题直接 blocked（207 §4.3）
RETRYABLE_ERROR_CODES = {"CONNECTION", "TIMEOUT"}

NOTIFY_POOL_RECIPIENT = "__pool__:quality_admin"


class RunValidationError(Exception):
    """运行单创建参数非法（路由层 422）。"""


class RunBlockedError(Exception):
    """运行单整体不可执行（仍落 blocked 运行单留证，不虚报已排队）。"""


class RunStateError(Exception):
    """运行单状态冲突（路由层 409）。"""


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ─────────────────────────────────────────────────────────────────────────
# 稳定范围键（207 §4.2：规范化范围结构生成摘要，不再截断标题充当键）
# ─────────────────────────────────────────────────────────────────────────

def compute_scope_key(parts: dict[str, Any]) -> str:
    canonical = json.dumps(
        {k: ("" if parts.get(k) is None else str(parts.get(k))) for k in sorted(parts)},
        ensure_ascii=False, separators=(",", ":"), sort_keys=True,
    )
    return "sk:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:40]


def control_scope_parts(control: QualityControl, detector: QualityControlDetector | None) -> dict[str, Any]:
    """稳定对象键：system + source + object_key + 检测器目标。展示名不参与身份。"""
    mapping = (detector.scope_mapping if detector is not None else None) or {}
    return {
        "system_code": control.primary_system_code or "",
        "source_code": (control.source_code or mapping.get("source_code") or ""),
        "object_key": control.object_key or mapping.get("object_key") or "",
        "detector_kind": detector.detector_kind if detector is not None else "",
        "detector_ref": detector.detector_ref if detector is not None else "",
        "granularity": mapping.get("granularity") or "table",
    }


# ─────────────────────────────────────────────────────────────────────────
# 执行窗口门禁
# ─────────────────────────────────────────────────────────────────────────

def parse_allowed_hours(spec: str) -> set[int] | None:
    """'0-6,22' → {0..6,22}；空/None → None（不限）。"""
    spec = (spec or "").strip()
    if not spec:
        return None
    hours: set[int] = set()
    for chunk in spec.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "-" in chunk:
            lo, hi = chunk.split("-", 1)
            hours.update(range(int(lo), int(hi) + 1))
        else:
            hours.add(int(chunk))
    return hours or None


def _control_allowed_hours(control: QualityControl) -> set[int] | None:
    plan = control.execution_plan if isinstance(control.execution_plan, dict) else {}
    spec = plan.get("allowed_hours") or settings.quality_execution_allowed_hours
    return parse_allowed_hours(spec)


def now_in_window(control: QualityControl, now: datetime) -> bool:
    hours = _control_allowed_hours(control)
    if hours is None:
        return True
    return now.hour in hours


def next_window_at(control: QualityControl, now: datetime) -> datetime | None:
    hours = _control_allowed_hours(control)
    if hours is None:
        return None
    for offset in range(1, 26):
        candidate = (now + timedelta(hours=offset)).replace(minute=0, second=0, microsecond=0)
        if candidate.hour in hours:
            return candidate
    return None


# ─────────────────────────────────────────────────────────────────────────
# 清单版本快照（不可变；lazy 创建，不伪造历史版本）
# ─────────────────────────────────────────────────────────────────────────

_CONTROL_SNAPSHOT_FIELDS = (
    "title", "description", "dimension", "category", "primary_system_code",
    "related_system_codes", "object_key", "object_name_snapshot", "metric_name",
    "metric_unit", "comparator", "threshold_value", "no_data_policy",
    "default_severity", "default_priority", "default_dept_code", "default_person_code",
    "schedule_expr", "timezone", "verification_policy", "required_pass_count",
    "source_code", "freshness_hours", "recheck_policy", "sla_hours", "execution_plan",
)


def _jsonable(value: Any) -> Any:
    """快照值转 JSON 安全类型（Decimal→float、datetime→iso、其余原样）。"""
    from decimal import Decimal

    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def ensure_revision(
    db: Session, control: QualityControl, *, actor: str = WORKER_ACTOR, origin: str = "current",
) -> QualityControlRevision:
    rev = db.scalar(
        select(QualityControlRevision).where(
            QualityControlRevision.control_id == control.id,
            QualityControlRevision.version == (control.version or 1),
        )
    )
    if rev is not None:
        return rev
    detectors = db.scalars(
        select(QualityControlDetector).where(QualityControlDetector.control_id == control.id)
    ).all()
    definition = _jsonable({f: getattr(control, f) for f in _CONTROL_SNAPSHOT_FIELDS})
    definition["version"] = control.version or 1
    def _det_snap(d: QualityControlDetector) -> dict[str, Any]:
        snap = {
            "detector_id": d.id, "detector_kind": d.detector_kind, "detector_ref": d.detector_ref,
            "detector_version": d.detector_version, "status": d.status,
        }
        if d.detector_kind == "value_domain" and isinstance(d.result_mapping, dict):
            # T08：修订快照携带值域绑定身份（码集指纹按运行观测冻结，见 threshold_snapshot）
            snap["value_domain_binding"] = {
                f: d.result_mapping.get(f) for f in
                ("system_code", "source_code", "schema_name", "table_name", "column_name")
            }
        return snap

    definition["detectors"] = [_det_snap(d) for d in detectors]
    rev = QualityControlRevision(
        control_id=control.id,
        version=control.version or 1,
        definition_snapshot=definition,
        scope_json=None,
        source_code=control.source_code,
        object_key=control.object_key,
        detector_versions=definition["detectors"],
        origin=origin,
        created_by=actor,
    )
    db.add(rev)
    db.flush()
    return rev


# ─────────────────────────────────────────────────────────────────────────
# 预检（静态/平台元数据；不访问源库）
# ─────────────────────────────────────────────────────────────────────────

@dataclass
class PreflightReport:
    executable: bool = False
    manual_required: bool = False
    blocked_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    detectors: list[dict[str, Any]] = field(default_factory=list)
    scope_summary: dict[str, Any] = field(default_factory=dict)
    window: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "executable": self.executable,
            "manual_required": self.manual_required,
            "blocked_reasons": self.blocked_reasons,
            "warnings": self.warnings,
            "detectors": self.detectors,
            "scope_summary": self.scope_summary,
            "window": self.window,
        }


def _detector_preflight(db: Session, control: QualityControl, det: QualityControlDetector) -> dict[str, Any]:
    """单检测器可执行性（静态；不连源库）。"""
    info: dict[str, Any] = {
        "detector_id": det.id,
        "detector_kind": det.detector_kind,
        "detector_ref": det.detector_ref,
        "detector_version": det.detector_version,
        "status": det.status,
        "executable": False,
        "blocked_reason": None,
    }
    if det.status != "active":
        info["blocked_reason"] = f"检测器状态 {det.status}（需 active）"
        return info
    if det.detector_kind == "quality_rule":
        from ..models.quality import QualityRule

        rule = db.scalar(select(QualityRule).where(QualityRule.rule_code == det.detector_ref))
        if rule is None or not rule.enabled:
            info["blocked_reason"] = f"规则不存在或停用: {det.detector_ref}"
            return info
        if (rule.execution_mode or "metadata_only") == "sql_template":
            if not (rule.check_sql or "").strip():
                info["blocked_reason"] = "sql_template 规则缺少 check_sql"
                return info
            source_code = control.source_code or rule.source_code
            if not source_code:
                info["blocked_reason"] = "未绑定 source_code（清单或规则均未提供）"
                return info
            from ..models.asset_system import AssetDataSource

            src = db.scalar(select(AssetDataSource).where(AssetDataSource.source_code == source_code))
            if src is None:
                info["blocked_reason"] = f"数据源未登记: {source_code}"
                return info
            info["executable"] = True
            info["source_code"] = source_code
            return info
        info["executable"] = True  # metadata_only 在平台库执行
        return info
    if det.detector_kind == "probe_template":
        mapping = det.result_mapping if isinstance(det.result_mapping, dict) else {}
        sides = mapping.get("sides")
        if isinstance(sides, list) and len(sides) >= 2 and all(
            (s or {}).get("source_code") and (s or {}).get("sql") for s in sides[:2]
        ):
            info["executable"] = True  # 双源限窗采集→受控区比对（不跨源 JOIN）
            info["source_code"] = sides[0].get("source_code")
            return info
        if mapping.get("sql") and (mapping.get("source_code") or control.source_code):
            info["executable"] = True
            info["source_code"] = mapping.get("source_code") or control.source_code
            return info
        info["blocked_reason"] = "probe_template 检测器未配置平台可执行 SQL（走夜间探查执行器）"
        return info
    if det.detector_kind == "value_domain":
        from .quality_value_domain import (
            ValueDomainBindingError, load_domain_verdict, parse_binding,
        )

        mapping = det.result_mapping if isinstance(det.result_mapping, dict) else {}
        try:
            binding = parse_binding(mapping)
        except ValueDomainBindingError as exc:
            info["blocked_reason"] = str(exc)
            return info
        verdict = load_domain_verdict(db, binding)
        if not verdict.authoritative:
            info["blocked_reason"] = f"值域待确认/受阻：{verdict.message}"
            return info
        from ..models.asset_system import AssetDataSource

        src_code = binding["source_code"]
        if db.scalar(select(AssetDataSource).where(AssetDataSource.source_code == src_code)) is None:
            info["blocked_reason"] = f"数据源未登记: {src_code}"
            return info
        info["executable"] = True
        info["source_code"] = src_code
        info["value_domain"] = {
            "code_count": len(verdict.codes),
            "fingerprint": verdict.fingerprint(),
            "effective": verdict.effective_window(),
            "pending_count": verdict.pending_count,
            "deprecated_count": verdict.deprecated_count,
        }
        if verdict.pending_count:
            info.setdefault("warnings", [])
            info["warnings"].append(
                f"另有 {verdict.pending_count} 条 pending 候选未参与权威判定（仅 confirmed {len(verdict.codes)} 条生效）"
            )
        return info
    info["blocked_reason"] = f"{det.detector_kind} 来源无平台执行器（人工/外部通道）"
    return info


def preflight_control(db: Session, control: QualityControl, *, now: datetime | None = None) -> PreflightReport:
    now = now or _now()
    report = PreflightReport()
    if control.lifecycle_status != "active":
        report.blocked_reasons.append(f"清单生命周期状态 {control.lifecycle_status}（需 active）")
    detectors = db.scalars(
        select(QualityControlDetector).where(QualityControlDetector.control_id == control.id)
    ).all()
    active = [d for d in detectors if d.status == "active"]
    auto_kinds = ("quality_rule", "probe_template", "value_domain")
    has_auto = any(d.detector_kind in auto_kinds for d in active)
    if not active or not has_auto:
        if (control.category or "") == "MANUAL" or all(
            d.detector_kind in ("manual", "external") for d in detectors
        ):
            report.manual_required = True
            reason = "手工/外部清单：无自动检测器，复测走人工验证路径"
            report.blocked_reasons.append(reason)
        else:
            report.blocked_reasons.append("无 active 自动检测器（quality_rule/probe_template/value_domain）")
    for det in active:
        info = _detector_preflight(db, control, det)
        report.detectors.append(info)
        if not info["executable"] and info["blocked_reason"]:
            report.blocked_reasons.append(
                f"检测器 {det.detector_kind}:{det.detector_ref} → {info['blocked_reason']}"
            )
    # 范围摘要
    parts = control_scope_parts(control, active[0] if active else None)
    report.scope_summary = {
        "scope_key": compute_scope_key(parts),
        "system_code": parts["system_code"] or None,
        "source_code": parts["source_code"] or None,
        "object_key": parts["object_key"] or None,
        "granularity": parts["granularity"],
    }
    # 窗口
    in_window = now_in_window(control, now)
    report.window = {
        "in_window": in_window,
        "allowed_hours": settings.quality_execution_allowed_hours or None,
        "next_window_at": None if in_window else (
            next_window_at(control, now).isoformat() if next_window_at(control, now) else None
        ),
    }
    if not in_window:
        report.warnings.append("当前不在批准执行窗口内；运行单将进入 waiting_window")
    report.executable = bool(active) and any(d["executable"] for d in report.detectors)
    return report


# ─────────────────────────────────────────────────────────────────────────
# 运行单创建（幂等；父+子）
# ─────────────────────────────────────────────────────────────────────────

def _new_run_code() -> str:
    return "QR-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S") + "-" + secrets.token_hex(3)


def create_run(
    db: Session,
    control: QualityControl,
    *,
    purpose: str = "check",
    trigger_kind: str = "manual",
    requested_by: str | None = None,
    idempotency_key: str | None = None,
    issue_id: int | None = None,
    window_start: date | None = None,
    window_end: date | None = None,
    now: datetime | None = None,
    actor: str = WORKER_ACTOR,
) -> dict[str, Any]:
    """创建父运行单 + 每检测器一个子运行。

    返回 {"run": QualityRun, "status": str, "blocked_reasons": [..],
           "manual_required": bool, "next_window_at": iso|None, "duplicate": bool}
    幂等：同 (control_id, idempotency_key) 已有运行单 → duplicate=True 返回原单。
    """
    now = now or _now()
    if purpose not in ("check", "recheck"):
        raise RunValidationError(f"非法 purpose: {purpose}")
    if control.lifecycle_status != "active":
        raise RunStateError(f"清单未激活（{control.lifecycle_status}）")

    if idempotency_key:
        existing = db.scalar(
            select(QualityRun).where(
                QualityRun.control_id == control.id,
                QualityRun.idempotency_key == idempotency_key,
                QualityRun.parent_run_id.is_(None),
            )
        )
        if existing is not None:
            return {
                "run": existing, "status": existing.status, "blocked_reasons": [],
                "manual_required": False, "next_window_at": None, "duplicate": True,
            }

    report = preflight_control(db, control, now=now)
    if report.manual_required and not report.executable:
        return {
            "run": None, "status": "manual_required", "blocked_reasons": report.blocked_reasons,
            "manual_required": True, "next_window_at": None, "duplicate": False,
        }

    revision = ensure_revision(db, control, actor=actor)
    executable_detectors = [d for d in report.detectors if d["executable"]]
    blocked_infos = [d for d in report.detectors if not d["executable"]]

    if not executable_detectors:
        # 全部检测器不可执行：落 blocked 运行单留证（不虚报排队）
        parent = QualityRun(
            run_code=_new_run_code(), control_id=control.id, revision_id=revision.id,
            issue_id=issue_id, purpose=purpose, trigger_kind=trigger_kind,
            requested_by=requested_by or actor, status="blocked",
            scope_key=report.scope_summary["scope_key"],
            scope_json=report.scope_summary, system_code=control.primary_system_code,
            source_code=control.source_code, object_key=control.object_key,
            window_start=window_start, window_end=window_end, scheduled_for=now,
            error_code="PREFLIGHT_BLOCKED",
            error_message_sanitized="; ".join(report.blocked_reasons)[:500] or "preflight blocked",
            budget_json=_default_budget(), created_by=actor,
        )
        db.add(parent)
        db.flush()
        return {
            "run": parent, "status": "blocked", "blocked_reasons": report.blocked_reasons,
            "manual_required": False, "next_window_at": None, "duplicate": False,
        }

    in_window = now_in_window(control, now)
    nxt = next_window_at(control, now)
    parent_status = "queued" if in_window else "waiting_window"
    parent = QualityRun(
        run_code=_new_run_code(), control_id=control.id, revision_id=revision.id,
        issue_id=issue_id, purpose=purpose, trigger_kind=trigger_kind,
        requested_by=requested_by or actor, status=parent_status,
        scope_key=report.scope_summary["scope_key"], scope_json=report.scope_summary,
        system_code=control.primary_system_code, source_code=control.source_code,
        object_key=control.object_key, window_start=window_start, window_end=window_end,
        scheduled_for=now, next_window_at=None if in_window else nxt,
        max_attempts=settings.quality_execution_max_attempts,
        idempotency_key=idempotency_key, budget_json=_default_budget(), created_by=actor,
    )
    db.add(parent)
    db.flush()
    for info in executable_detectors:
        det = db.get(QualityControlDetector, info["detector_id"])
        scope_parts = control_scope_parts(control, det)
        child = QualityRun(
            run_code=_new_run_code() + "-d", control_id=control.id, revision_id=revision.id,
            parent_run_id=parent.id, issue_id=issue_id, purpose=purpose,
            trigger_kind=trigger_kind, requested_by=requested_by or actor,
            status=parent_status, detector_id=det.id, detector_kind=det.detector_kind,
            detector_ref=det.detector_ref, scope_key=compute_scope_key(scope_parts),
            scope_json=scope_parts, system_code=control.primary_system_code,
            source_code=info.get("source_code") or control.source_code,
            object_key=control.object_key, window_start=window_start, window_end=window_end,
            scheduled_for=now, next_window_at=None if in_window else nxt,
            max_attempts=settings.quality_execution_max_attempts,
            idempotency_key=(f"{idempotency_key}:d{info['detector_id']}" if idempotency_key else None),
            budget_json=_default_budget(), created_by=actor,
        )
        db.add(child)
    for info in blocked_infos:
        det = db.get(QualityControlDetector, info["detector_id"])
        child = QualityRun(
            run_code=_new_run_code() + "-d", control_id=control.id, revision_id=revision.id,
            parent_run_id=parent.id, issue_id=issue_id, purpose=purpose,
            trigger_kind=trigger_kind, requested_by=requested_by or actor,
            status="blocked", detector_id=det.id, detector_kind=det.detector_kind,
            detector_ref=det.detector_ref, scope_key=compute_scope_key(control_scope_parts(control, det)),
            scope_json=control_scope_parts(control, det),
            system_code=control.primary_system_code, source_code=control.source_code,
            object_key=control.object_key, window_start=window_start, window_end=window_end,
            scheduled_for=now, error_code="DETECTOR_BLOCKED",
            error_message_sanitized=(info.get("blocked_reason") or "")[:500],
            finished_at=now, budget_json=_default_budget(), created_by=actor,
        )
        db.add(child)
    return {
        "run": parent, "status": parent_status, "blocked_reasons": [],
        "manual_required": False,
        "next_window_at": None if in_window else (nxt.isoformat() if nxt else None),
        "duplicate": False,
    }


def _default_budget() -> dict[str, Any]:
    return {
        "sql_timeout_s": settings.quality_run_sql_timeout_s,
        "sample_limit": settings.quality_sample_limit,
        "max_rows": 1000,
        "source_concurrency": 1,
    }


# ─────────────────────────────────────────────────────────────────────────
# 领取 / 心跳 / 围栏（短事务；两 worker 不重复执行）
# ─────────────────────────────────────────────────────────────────────────

def claim_next_run(
    db: Session, worker_id: str, *, now: datetime | None = None, lease_seconds: int | None = None,
) -> QualityRun | None:
    """乐观领取一个子运行（rowcount 守卫，跨方言可用）。

    候选：queued；waiting_window 已到窗；running 且租约过期（接管 attempt+1）。
    """
    now = now or _now()
    lease_seconds = lease_seconds or settings.quality_execution_lease_seconds
    lease_until = now + timedelta(seconds=lease_seconds)
    candidates = db.scalars(
        select(QualityRun)
        .where(
            QualityRun.parent_run_id.isnot(None),
            QualityRun.status.in_(("queued", "waiting_window", "running")),
        )
        .order_by(QualityRun.scheduled_for.asc().nulls_first(), QualityRun.id.asc())
        .limit(20)
    ).all()
    for run in candidates:
        if run.status == "queued":
            guard = (QualityRun.id == run.id) & (QualityRun.status == "queued")
        elif run.status == "waiting_window":
            if run.next_window_at and run.next_window_at.replace(tzinfo=timezone.utc) > now:
                continue
            guard = (QualityRun.id == run.id) & (QualityRun.status == "waiting_window")
        else:  # running → 租约过期接管
            expires = run.lease_expires_at
            if expires is not None and expires.replace(tzinfo=timezone.utc) > now:
                continue
            guard = (
                (QualityRun.id == run.id)
                & (QualityRun.status == "running")
                & ((QualityRun.lease_expires_at.is_(None)) | (QualityRun.lease_expires_at <= now))
            )
        result = db.execute(
            update(QualityRun)
            .where(guard)
            .values(
                status="running", lease_owner=worker_id, lease_expires_at=lease_until,
                attempt=run.attempt + 1, heartbeat_at=now,
                started_at=run.started_at or now, updated_at=now,
            )
        )
        if result.rowcount == 1:
            db.commit()
            db.expire(run)
            return db.get(QualityRun, run.id)
    return None


def heartbeat_run(db: Session, run_id: int, worker_id: str, *, now: datetime | None = None) -> bool:
    now = now or _now()
    result = db.execute(
        update(QualityRun)
        .where(
            QualityRun.id == run_id, QualityRun.status == "running", QualityRun.lease_owner == worker_id
        )
        .values(heartbeat_at=now, updated_at=now)
    )
    db.commit()
    return result.rowcount == 1


# ─────────────────────────────────────────────────────────────────────────
# 检测器执行器（六态结果；可注入替换用于合成验收）
# ─────────────────────────────────────────────────────────────────────────

@dataclass
class DetectorOutcome:
    status: str  # pass/fail/no_data/error/blocked/skipped
    metric_value: float | None = None
    numerator: float | None = None
    denominator: float | None = None
    metric_unit: str | None = None
    error_code: str | None = None
    error_message_sanitized: str | None = None
    evidence_digest: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


def _comparator_failed(comparator: str | None, threshold: float | None, value: float) -> bool:
    """默认口径：无阈值配置时 error_rate>0 即 FAIL；配置后按比较器。"""
    if comparator is None and threshold is None:
        return value > 0
    th = float(threshold or 0.0)
    return {
        "gt": value > th, "gte": value >= th, "lt": value < th, "lte": value <= th,
        "eq": value == th,
    }.get(comparator or "gt", value > th)


def _execute_quality_rule_sql(
    db: Session, control: QualityControl, revision: QualityControlRevision, run: QualityRun,
) -> DetectorOutcome:
    from ..models.quality import QualityRule
    from .quality_sql_runner import execute_quality_sql

    rule = db.scalar(select(QualityRule).where(QualityRule.rule_code == run.detector_ref))
    if rule is None or not rule.enabled:
        return DetectorOutcome("blocked", error_code="RULE_UNAVAILABLE",
                               error_message_sanitized=f"规则不存在或停用: {run.detector_ref}")
    source_code = run.source_code or revision.source_code or rule.source_code or ""
    if not source_code:
        return DetectorOutcome("blocked", error_code="SOURCE_UNRESOLVED",
                               error_message_sanitized="未绑定物理数据源（source_code）")
    budget = run.budget_json if isinstance(run.budget_json, dict) else {}
    result = execute_quality_sql(
        rule_code=rule.rule_code, sql=rule.check_sql or "", source_code=source_code,
        max_rows=int(budget.get("max_rows", 1000)),
        sample_limit=int(budget.get("sample_limit", settings.quality_sample_limit)), db=db,
    )
    return _outcome_from_sql_result(control, result)


def _execute_quality_rule_metadata(
    db: Session, control: QualityControl, run: QualityRun,
) -> DetectorOutcome:
    from ..models.quality import QualityRule
    from .quality_rule_engine import run_metadata_rule

    rule = db.scalar(select(QualityRule).where(QualityRule.rule_code == run.detector_ref))
    if rule is None or not rule.enabled:
        return DetectorOutcome("blocked", error_code="RULE_UNAVAILABLE",
                               error_message_sanitized=f"规则不存在或停用: {run.detector_ref}")
    findings = run_metadata_rule(rule, db)
    count = len(findings or [])
    return DetectorOutcome(
        "fail" if count > 0 else "pass",
        metric_value=float(count), numerator=float(count), denominator=None,
        metric_unit="finding", evidence_digest=f"findings:{count}",
    )


def _execute_probe_mapping(
    db: Session, control: QualityControl, revision: QualityControlRevision, run: QualityRun,
) -> DetectorOutcome:
    det = db.get(QualityControlDetector, run.detector_id) if run.detector_id else None
    mapping = (det.result_mapping if det is not None and isinstance(det.result_mapping, dict) else {}) or {}
    sql = mapping.get("sql")
    source_code = mapping.get("source_code") or run.source_code
    sides = mapping.get("sides")
    if isinstance(sides, list) and len(sides) >= 2:
        return _execute_cross_source(control, mapping, sides)
    if not sql or not source_code:
        return DetectorOutcome("blocked", error_code="PROBE_NOT_MAPPED",
                               error_message_sanitized="probe_template 检测器未配置平台可执行 SQL（走夜间探查执行器）")
    from .quality_sql_runner import execute_quality_sql

    budget = run.budget_json if isinstance(run.budget_json, dict) else {}
    result = execute_quality_sql(
        rule_code=run.detector_ref or "probe", sql=sql, source_code=source_code,
        max_rows=int(budget.get("max_rows", 1000)),
        sample_limit=int(budget.get("sample_limit", settings.quality_sample_limit)), db=db,
    )
    return _outcome_from_sql_result(control, result)


def _execute_cross_source(
    control: QualityControl, mapping: dict, sides: list,
) -> DetectorOutcome:
    """双源限窗采集 → 受控区逐键比对（207 §4.5；不做跨源 JOIN）。

    mapping.sides = [{source_code, sql}, ...]；mapping.compare = {
      key_fields, compare_fields?, code_mapping?, missing_threshold_pct?, mismatch_threshold_pct?}
    """
    from .quality_cross_source import compare_keyed_datasets, cross_source_verdict
    from .quality_sql_runner import fetch_readonly_rows

    compare_cfg = mapping.get("compare") if isinstance(mapping.get("compare"), dict) else {}
    key_fields = compare_cfg.get("key_fields") or []
    if not key_fields:
        return DetectorOutcome("blocked", error_code="CROSS_SOURCE_CONFIG",
                               error_message_sanitized="跨源比对缺少 key_fields 配置")
    fetches: list[dict] = []
    for side in sides[:2]:
        side_code = (side or {}).get("source_code") or ""
        side_sql = (side or {}).get("sql") or ""
        if not side_code or not side_sql:
            return DetectorOutcome("blocked", error_code="CROSS_SOURCE_CONFIG",
                                   error_message_sanitized="跨源比对 side 缺少 source_code/sql")
        fetched = fetch_readonly_rows(side_sql, side_code, max_rows=1000)
        if fetched.get("status") == "source_not_found":
            return DetectorOutcome("blocked", error_code="SOURCE_NOT_REGISTERED",
                                   error_message_sanitized=fetched.get("note"))
        if fetched.get("status") == "invalid_sql":
            return DetectorOutcome("blocked", error_code="INVALID_SQL",
                                   error_message_sanitized="; ".join(fetched.get("errors", []))[:500])
        if fetched.get("status") == "failed":
            note = fetched.get("note") or ""
            code = "TIMEOUT" if "timeout" in note.lower() else "CONNECTION"
            return DetectorOutcome("error", error_code=code, error_message_sanitized=note)
        fetches.append(fetched)
    cmp = compare_keyed_datasets(
        fetches[0].get("rows", []), fetches[1].get("rows", []),
        key_fields=key_fields,
        compare_fields=compare_cfg.get("compare_fields"),
        code_mapping=compare_cfg.get("code_mapping"),
    )
    verdict = cross_source_verdict(
        cmp,
        missing_threshold_pct=float(compare_cfg.get("missing_threshold_pct", 0) or 0),
        mismatch_threshold_pct=float(compare_cfg.get("mismatch_threshold_pct", 0) or 0),
    )
    metrics = verdict.get("metrics", {})
    status = verdict["status"]
    if status == "no_data":
        return DetectorOutcome("no_data", metric_value=0.0, numerator=0, denominator=0,
                               metric_unit="%", error_code="EMPTY_SCOPE",
                               error_message_sanitized=verdict["reason"],
                               extra={"counts_equal": metrics.get("counts_equal")})
    metric = max(metrics.get("bidirectional_missing_pct", 0), metrics.get("value_mismatch_pct", 0))
    digest = hashlib.sha256(
        json.dumps(cmp.as_dict(sample_cap=3), ensure_ascii=False, default=str).encode("utf-8")
    ).hexdigest()[:32]
    return DetectorOutcome(
        "fail" if verdict["status"] == "fail" else "pass",
        metric_value=metric, numerator=metrics.get("bidirectional_missing", 0),
        denominator=max(cmp.distinct_keys_a, cmp.distinct_keys_b, 1),
        metric_unit="%", evidence_digest=digest, extra={"metrics": metrics},
    )


def _execute_value_domain(
    db: Session, control: QualityControl, revision: QualityControlRevision, run: QualityRun,
) -> DetectorOutcome:
    """T08 值域通用执行器：confirmed 码集 + 物理源分布 → 权威/待结论分层。

    - pending/deprecated/conflicted/未登记 → blocked（待确认/受阻），绝不 FAIL；
    - 分布采集走 fetch_readonly_rows（受控只读）；基数超限 → blocked（口径不适配）；
    - 码集与指纹冻结进观测 threshold_snapshot.value_domain（旧运行按冻结版本留证）。
    """
    from .quality_sql_runner import fetch_readonly_rows
    from .quality_value_domain import (
        DEFAULT_MAX_DISTINCT, ValueDomainBindingError, build_distribution_sql,
        compare_distribution, domain_snapshot_for_observation, load_domain_verdict,
        parse_binding,
    )

    det = db.get(QualityControlDetector, run.detector_id) if run.detector_id else None
    mapping = (det.result_mapping if det is not None and isinstance(det.result_mapping, dict) else {}) or {}
    try:
        binding = parse_binding(mapping)
    except ValueDomainBindingError as exc:
        return DetectorOutcome("blocked", error_code="VD_BINDING_INVALID",
                               error_message_sanitized=str(exc))
    verdict = load_domain_verdict(db, binding)
    if not verdict.authoritative:
        code = {
            "not_registered": "VD_NOT_REGISTERED",
            "pending_only": "VD_PENDING",
            "deprecated_only": "VD_DEPRECATED",
            "conflicted_only": "VD_CONFLICTED",
            "no_enum_codes": "VD_NO_ENUM_CODES",
        }.get(verdict.status, "VD_NOT_CONFIRMED")
        snap = domain_snapshot_for_observation(binding, verdict)
        return DetectorOutcome(
            "blocked", error_code=code,
            error_message_sanitized=f"值域待确认/受阻：{verdict.message}",
            extra={"domain_snapshot": snap},
        )
    max_distinct = int(mapping.get("max_distinct") or DEFAULT_MAX_DISTINCT)
    fetched = fetch_readonly_rows(
        build_distribution_sql(binding), binding["source_code"], max_rows=max_distinct + 1,
    )
    if fetched.get("status") == "source_not_found":
        return DetectorOutcome("blocked", error_code="SOURCE_NOT_REGISTERED",
                               error_message_sanitized=fetched.get("note"))
    if fetched.get("status") == "invalid_sql":
        return DetectorOutcome("blocked", error_code="INVALID_SQL",
                               error_message_sanitized="; ".join(fetched.get("errors", []))[:500])
    if fetched.get("status") == "failed":
        note = fetched.get("note") or ""
        code = "TIMEOUT" if "timeout" in note.lower() else "CONNECTION"
        return DetectorOutcome("error", error_code=code, error_message_sanitized=note)
    rows = fetched.get("rows", [])
    if fetched.get("truncated") or len(rows) > max_distinct:
        return DetectorOutcome(
            "blocked", error_code="VD_CARDINALITY",
            error_message_sanitized=(
                f"列基数超过采样上限 {max_distinct}（分布截断，枚举口径不适用；"
                "请人工核对该列是否编码列或缩小范围）"
            ),
        )
    cmp = compare_distribution(
        rows, verdict.codes, null_is_error=bool(mapping.get("null_is_error")),
    )
    snap = domain_snapshot_for_observation(binding, verdict, cmp)
    if cmp.status == "no_data":
        return DetectorOutcome("no_data", metric_value=0.0, numerator=0, denominator=0,
                               metric_unit="%", error_code="EMPTY_SCOPE",
                               error_message_sanitized=cmp.message,
                               extra={"domain_snapshot": snap})
    rate = round(cmp.illegal / cmp.total * 100, 4) if cmp.total else 0.0
    failed = _comparator_failed(control.comparator,
                                float(control.threshold_value) if control.threshold_value is not None else None,
                                rate)
    digest = hashlib.sha256(
        json.dumps(snap, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:32]
    return DetectorOutcome(
        "fail" if failed else "pass",
        metric_value=rate, numerator=float(cmp.illegal), denominator=float(cmp.total),
        metric_unit="%", evidence_digest=digest,
        error_message_sanitized=cmp.message or None,
        extra={"domain_snapshot": snap},
    )


def _outcome_from_sql_result(control: QualityControl, result: dict[str, Any]) -> DetectorOutcome:
    status = result.get("status")
    if status == "source_not_found":
        return DetectorOutcome("blocked", error_code="SOURCE_NOT_REGISTERED",
                               error_message_sanitized=result.get("note"))
    if status == "invalid_sql":
        return DetectorOutcome("blocked", error_code="INVALID_SQL",
                               error_message_sanitized="; ".join(result.get("errors", []))[:500])
    if status == "rule_error":
        return DetectorOutcome("error", error_code="RULE_CONTRACT", error_message_sanitized=result.get("note"))
    if status == "failed":
        note = result.get("note") or ""
        code = "TIMEOUT" if "timeout" in note.lower() else "CONNECTION"
        return DetectorOutcome("error", error_code=code, error_message_sanitized=note)
    total = int(result.get("total_cnt", 0) or 0)
    error_cnt = int(result.get("error_cnt", 0) or 0)
    if total <= 0:
        return DetectorOutcome("no_data", metric_value=0.0, numerator=error_cnt, denominator=total,
                               metric_unit="%", error_code="EMPTY_SCOPE",
                               error_message_sanitized="分母为 0（零样本），按 NO_DATA 处理")
    rate = float(result.get("error_rate", 0) or 0)
    failed = _comparator_failed(control.comparator,
                                float(control.threshold_value) if control.threshold_value is not None else None,
                                rate)
    return DetectorOutcome("fail" if failed else "pass", metric_value=rate,
                           numerator=error_cnt, denominator=total, metric_unit="%")


# 测试注入点：{detector_kind: callable(db, control, revision, run) -> DetectorOutcome}
EXECUTOR_REGISTRY: dict[str, Callable[[Session, QualityControl, QualityControlRevision, QualityRun], DetectorOutcome]] = {}


def _default_executor(kind: str | None):
    if kind == "quality_rule":
        def run_sql(db, control, revision, run):
            from ..models.quality import QualityRule
            rule = db.scalar(select(QualityRule).where(QualityRule.rule_code == run.detector_ref))
            if rule is not None and (rule.execution_mode or "metadata_only") == "sql_template":
                return _execute_quality_rule_sql(db, control, revision, run)
            return _execute_quality_rule_metadata(db, control, run)
        return run_sql
    if kind == "probe_template":
        return _execute_probe_mapping
    if kind == "value_domain":
        return _execute_value_domain
    return None


def resolve_executor(kind: str | None):
    if kind and kind in EXECUTOR_REGISTRY:
        return EXECUTOR_REGISTRY[kind]
    return _default_executor(kind)


# ─────────────────────────────────────────────────────────────────────────
# 子运行执行 → 六态观测 → 父运行归并/复测结论（同事务）
# ─────────────────────────────────────────────────────────────────────────

def execute_claimed_run(
    db: Session, run: QualityRun, *, worker_id: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """执行一个已领取的子运行：检测器→观测→子状态→（末子触发）父归并+复测结论。

    全程单事务；调用方 commit。观测幂等键 run_key=f"qr:{run.id}:{run.attempt}"。
    """
    now = now or _now()
    owner = worker_id or run.lease_owner or WORKER_ACTOR
    if run.status != "running":
        raise RunStateError(f"运行单 {run.run_code} 状态 {run.status}，非 running 不能执行")
    if run.lease_owner and worker_id and run.lease_owner != worker_id:
        raise RunStateError(f"租约不属于当前 worker（{worker_id} != {run.lease_owner}）")
    my_attempt = run.attempt

    # 协作取消：执行前检查
    if (run.cancel_requested or "") == "true":
        _finish_child(db, run, "cancelled", now=now, reason="执行前取消")
        _aggregate_parent(db, run.parent_run_id, now=now)
        return {"run_id": run.id, "status": "cancelled", "observed": False}

    control = db.get(QualityControl, run.control_id)
    revision = db.get(QualityControlRevision, run.revision_id) if run.revision_id else None
    if control is None:
        _finish_child(db, run, "blocked", now=now, error_code="CONTROL_GONE",
                      error_message_sanitized="清单已删除")
        _aggregate_parent(db, run.parent_run_id, now=now)
        return {"run_id": run.id, "status": "blocked", "observed": False}
    if revision is None:
        revision = ensure_revision(db, control)

    run.heartbeat_at = now
    executor = resolve_executor(run.detector_kind)
    if executor is None:
        outcome = DetectorOutcome("blocked", error_code="NO_EXECUTOR",
                                  error_message_sanitized=f"{run.detector_kind} 来源无平台执行器")
    else:
        try:
            outcome = executor(db, control, revision, run)
            if outcome.status not in qgs.OBSERVATION_RESULTS:
                outcome = DetectorOutcome("error", error_code="BAD_OUTCOME",
                                          error_message_sanitized=f"执行器返回非法状态 {outcome.status}")
        except Exception as exc:  # 执行器异常一律 ERROR，绝不 PASS
            from .data_masking import sanitize_text

            outcome = DetectorOutcome("error", error_code="EXECUTOR_ERROR",
                                      error_message_sanitized=sanitize_text(f"{type(exc).__name__}: {exc}", limit=400))
    run.heartbeat_at = _now()

    # 可信自动观测（source_kind=quality_run 仅此通道产生）
    obs_result: dict[str, Any] | None = None
    if outcome.status != "cancelled":
        try:
            obs_result = qgs.apply_observation(
                db,
                control_id=control.id,
                detector_id=run.detector_id,
                control_version=revision.version,
                run_key=f"qr:{run.id}:{my_attempt}",
                scope_key=run.scope_key or revision.object_key or control.object_key or "unknown",
                result_status=outcome.status,
                window_start=run.window_start,
                window_end=run.window_end,
                metric_value=outcome.metric_value,
                metric_unit=outcome.metric_unit,
                threshold_snapshot={
                    "comparator": control.comparator,
                    "threshold_value": float(control.threshold_value)
                    if control.threshold_value is not None else None,
                    **({"value_domain": outcome.extra["domain_snapshot"]}
                       if outcome.extra.get("domain_snapshot") else {}),
                },
                control_definition_snapshot=revision.definition_snapshot,
                numerator=outcome.numerator,
                denominator=outcome.denominator,
                source_kind="quality_run",
                source_record_ref=f"asset_quality_runs:{run.id}",
                evidence_digest=outcome.evidence_digest,
                evidence_ref=f"quality_run:{run.run_code}",
                historical_precision="exact",
                error_code=outcome.error_code,
                error_message_sanitized=outcome.error_message_sanitized,
                actor=WORKER_ACTOR,
                correlation_id=f"run:{run.id}",
                observation_time=now,
            )
        except Exception as exc:
            # 观测写入失败：运行失败，绝不静默吞掉（T33）
            _finish_child(db, run, "failed", now=now, error_code="OBSERVATION_WRITE_FAILED",
                          error_message_sanitized=f"{type(exc).__name__}: {exc}"[:400])
            _aggregate_parent(db, run.parent_run_id, now=now)
            return {"run_id": run.id, "status": "failed", "observed": False,
                    "error": "observation_write_failed"}

    # 子运行终态映射：数据 pass/fail/no_data/blocked → 执行成功（succeeded）；
    # error → 视重试策略退避重试或 failed；skipped → succeeded（结论=skipped）。
    data_status = outcome.status
    summary = {"status": data_status, "metric_value": outcome.metric_value,
               "numerator": outcome.numerator, "denominator": outcome.denominator,
               "metric_unit": outcome.metric_unit, "error_code": outcome.error_code,
               "error_message_sanitized": outcome.error_message_sanitized,
               "attempt": my_attempt, "worker": owner}
    if data_status == "error":
        if outcome.error_code in RETRYABLE_ERROR_CODES and run.attempt < (run.max_attempts or 1):
            backoff = min(30 * (2 ** (run.attempt - 1)), 300)
            run.status = "queued"
            run.next_window_at = now + timedelta(seconds=backoff)
            run.result_summary = summary
            run.updated_at = now
            db.flush()
            return {"run_id": run.id, "status": "queued_retry", "observed": True,
                    "retry_in_s": backoff}
        _finish_child(db, run, "failed", now=now, error_code=outcome.error_code,
                      error_message_sanitized=outcome.error_message_sanitized, summary=summary)
    else:
        child_status = "blocked" if data_status == "blocked" else "succeeded"
        _finish_child(db, run, child_status, now=now, summary=summary)

    _aggregate_parent(db, run.parent_run_id, now=now)
    result = {"run_id": run.id, "status": data_status, "run_status": run.status, "observed": True}
    if obs_result:
        result["observation"] = obs_result
    return result


def _finish_child(
    db: Session, run: QualityRun, status: str, *, now: datetime, summary: dict | None = None,
    reason: str | None = None, error_code: str | None = None, error_message_sanitized: str | None = None,
) -> None:
    if summary is not None:
        run.result_summary = summary
    run.status = status
    run.finished_at = now
    run.updated_at = now
    run.lease_owner = None
    run.lease_expires_at = None
    if reason:
        run.cancelled_reason = reason
    if error_code:
        run.error_code = error_code
    if error_message_sanitized:
        run.error_message_sanitized = error_message_sanitized
    db.flush()


def _aggregate_parent(db: Session, parent_run_id: int | None, *, now: datetime | None = None) -> None:
    """末子运行终态后归并父运行；recheck 父单同事务推进复测结论（幂等）。"""
    if parent_run_id is None:
        return
    now = now or _now()
    parent = db.get(QualityRun, parent_run_id)
    if parent is None or parent.status in RUN_TERMINAL_STATUSES:
        return
    children = db.scalars(
        select(QualityRun).where(QualityRun.parent_run_id == parent.id)
    ).all()
    if not children:
        return
    if any(c.status in RUN_ACTIVE_STATUSES for c in children):
        return  # 还有子任务在途
    statuses = [c.status for c in children]
    data = [(c.result_summary or {}).get("status") for c in children]
    if all(s == "cancelled" for s in statuses):
        parent_status = "cancelled"
    elif all(s == "blocked" for s in statuses):
        parent_status = "blocked"
    elif any(s == "failed" for s in statuses):
        parent_status = "failed" if all(s in ("failed", "blocked", "cancelled") for s in statuses) else "partial"
    else:
        parent_status = "succeeded"
    parent.status = parent_status
    parent.finished_at = now
    parent.updated_at = now
    parent.result_summary = {
        "overall": parent_status,
        "detectors": {
            (c.detector_ref or str(c.detector_id)): {
                "run_id": c.id, "status": c.status, "data_status": d,
                "metric_value": (c.result_summary or {}).get("metric_value"),
                "numerator": (c.result_summary or {}).get("numerator"),
                "denominator": (c.result_summary or {}).get("denominator"),
            }
            for c, d in zip(children, data)
        },
    }
    db.flush()
    if parent.purpose == "recheck" and parent.issue_id:
        summary = dict(parent.result_summary or {})
        if not summary.get("recheck_applied"):
            _apply_recheck_outcome(db, parent, children, now=now)
            parent.result_summary = {**summary, "recheck_applied": True}


def _apply_recheck_outcome(db: Session, parent: QualityRun, children: list[QualityRun], *, now: datetime) -> None:
    """复测结论 → 台账推进（207 §4.4 默认动作；幂等由 recheck_applied 守卫）。"""
    issue = db.get(QualityIssue, parent.issue_id)
    if issue is None:
        return
    control = db.get(QualityControl, parent.control_id)
    data_statuses = [(c.result_summary or {}).get("status") for c in children]
    incomplete = [d for d in data_statuses if d not in ("pass", "fail")]
    fails = [d for d in data_statuses if d == "fail"]
    issue.last_verification_run_id = parent.id

    if incomplete:
        issue.recheck_substatus = "blocked"
        issue.recheck_pass_streak = 0
        issue.recheck_note = "复测不完整（ERROR/BLOCKED/NO_DATA/缺失）：不作为通过或退回依据，待重新完整复测"
        _add_run_event(db, issue, "recheck_blocked", parent, now,
                       reason=issue.recheck_note)
    elif fails:
        issue.recheck_substatus = "failed"
        issue.recheck_pass_streak = 0
        issue.recheck_note = f"自动复测 FAIL（运行 {parent.run_code}），退回整改"
        from_status = issue.status
        if issue.status == "waiting_verify":
            issue.status = "in_progress"
        _bump_issue(issue, WORKER_ACTOR)
        _add_run_event(db, issue, "recheck_failed", parent, now,
                       reason=issue.recheck_note, from_status=from_status, to_status=issue.status)
        create_notification(
            db, issue_id=issue.id, run_id=parent.id,
            recipient=issue.assignee_user_identifier or issue.responsible_person_code or NOTIFY_POOL_RECIPIENT,
            notify_type="recheck_failed",
            payload={"issue_code": issue.issue_code, "run_code": parent.run_code},
            idempotency_key=f"recheck_failed:{parent.id}",
        )
    else:
        issue.recheck_substatus = "passed"
        issue.recheck_pass_streak = (issue.recheck_pass_streak or 0) + 1
        issue.recheck_note = f"自动复测通过（运行 {parent.run_code}），待独立人员确认关闭"
        _bump_issue(issue, WORKER_ACTOR)
        _add_run_event(db, issue, "recheck_passed", parent, now, reason=issue.recheck_note)
        create_notification(
            db, issue_id=issue.id, run_id=parent.id,
            recipient=issue.assignee_user_identifier or issue.responsible_person_code or NOTIFY_POOL_RECIPIENT,
            notify_type="recheck_passed",
            payload={"issue_code": issue.issue_code, "run_code": parent.run_code,
                     "pass_streak": issue.recheck_pass_streak,
                     "required": (control.required_pass_count if control else 1) or 1},
            idempotency_key=f"recheck_passed:{parent.id}",
        )


def _bump_issue(issue: QualityIssue, actor: str) -> None:
    issue.lock_version = (issue.lock_version or 0) + 1
    issue.updated_by = actor
    issue.updated_at = _now()


def _add_run_event(
    db: Session, issue: QualityIssue, event_type: str, run: QualityRun, now: datetime, *,
    reason: str, from_status: str | None = None, to_status: str | None = None,
) -> None:
    from ..models.quality_governance import QualityIssueEvent as _Ev

    db.add(_Ev(
        issue_id=issue.id, event_type=event_type, from_status=from_status, to_status=to_status,
        reason=reason, observation_id=None, actor_user_identifier=WORKER_ACTOR,
        occurred_at=now, correlation_id=f"run:{run.id}",
        after_json={"run_id": run.id, "run_code": run.run_code},
    ))


# ─────────────────────────────────────────────────────────────────────────
# 取消 / 重试
# ─────────────────────────────────────────────────────────────────────────

def cancel_run(
    db: Session, run: QualityRun, *, expected_lock_version: int, reason: str, actor: str,
) -> QualityRun:
    if run.lock_version != expected_lock_version:
        raise RunStateError(
            f"lock_version 冲突：期望 {expected_lock_version}，实际 {run.lock_version}"
        )
    if run.status in RUN_TERMINAL_STATUSES:
        raise RunStateError(f"运行单已终态（{run.status}）不能取消")
    run.cancel_requested = "true"
    run.lock_version += 1
    run.updated_by = actor
    run.updated_at = _now()
    # queued/waiting_window 直接取消；running 协作取消（worker 下一检查点生效）
    if run.status in ("queued", "waiting_window"):
        run.status = "cancelled"
        run.cancelled_reason = reason
        run.finished_at = _now()
        if run.parent_run_id is None:
            for child in db.scalars(
                select(QualityRun).where(QualityRun.parent_run_id == run.id)
            ).all():
                if child.status in RUN_ACTIVE_STATUSES:
                    child.status = "cancelled"
                    child.cancelled_reason = reason
                    child.finished_at = _now()
                    child.lock_version += 1
    else:
        run.cancelled_reason = reason
    db.flush()
    return run


def retry_run(
    db: Session, run: QualityRun, *, actor: str, reason: str | None = None,
) -> QualityRun:
    """终态 failed/blocked/partial 运行 → 关联重试（新父单，同目的/范围/版本策略）。"""
    if run.status not in ("failed", "blocked", "partial", "cancelled"):
        raise RunStateError(f"状态 {run.status} 不需要重试")
    control = db.get(QualityControl, run.control_id)
    if control is None:
        raise RunStateError("清单不存在")
    # 重试须重新过窗口/预算/预检（create_run 内建）
    result = create_run(
        db, control, purpose=run.purpose, trigger_kind="manual", requested_by=actor,
        idempotency_key=f"retry:{run.id}:{secrets.token_hex(3)}", issue_id=run.issue_id,
        window_start=run.window_start, window_end=run.window_end, actor=actor,
    )
    new_run = result["run"]
    if new_run is not None and result.get("status") != "manual_required":
        new_run.result_summary = {"retried_from": run.id, "retry_reason": reason}
    return new_run


# ─────────────────────────────────────────────────────────────────────────
# 可信复测证据校验（F03；关闭前的强校验）
# ─────────────────────────────────────────────────────────────────────────

def evaluate_trusted_recheck(
    db: Session, issue: QualityIssue, *, now: datetime | None = None,
) -> tuple[bool, list[str], dict[str, Any]]:
    """校验本问题当前是否具备可信自动复测通过证据。

    返回 (ok, errors, evidence)。policy=manual 的问题不做自动证据要求（人工
    验证路径仍需说明与观察引用，由 verify 命令层约束）。
    """
    now = now or _now()
    if issue.control_id is None:
        return True, [], {"kind": "manual_no_control"}
    control = db.get(QualityControl, issue.control_id)
    if control is None:
        return True, [], {"kind": "manual_no_control"}
    if (control.verification_policy or "manual") == "manual":
        return True, [], {"kind": "manual_policy"}
    errors: list[str] = []
    evidence: dict[str, Any] = {"kind": "auto_recheck"}
    run_id = issue.last_verification_run_id
    if run_id is None:
        return False, ["缺少自动复测运行（last_verification_run_id 为空）"], evidence
    run = db.get(QualityRun, run_id)
    if run is None:
        return False, [f"复测运行 {run_id} 不存在"], evidence
    evidence["run_id"] = run.id
    evidence["run_code"] = run.run_code
    if run.purpose != "recheck" or run.issue_id != issue.id:
        return False, [f"运行 {run.run_code} 不是本问题的复测运行"], evidence
    if run.status != "succeeded":
        return False, [f"复测运行状态 {run.status}（需 succeeded，运行成功且数据全部通过）"], evidence
    if run.scope_key and issue.scope_key and run.scope_key != issue.scope_key:
        return False, ["复测范围与问题范围不一致（scope_key 不匹配）"], evidence
    if issue.recheck_substatus != "passed":
        return False, [f"复测子状态 {issue.recheck_substatus}（需 passed；不能以旧PASS/空结果/不同范围关闭）"], evidence
    required = (control.required_pass_count if control else 1) or 1
    if (issue.recheck_pass_streak or 0) < required:
        return False, [
            f"连续完整复测通过 {issue.recheck_pass_streak} 次，少于要求 {required} 次（FAIL/ERROR 会中断连续性）"
        ], evidence
    if issue.remediation_submitted_at and run.finished_at:
        finished = run.finished_at
        if finished.replace(tzinfo=timezone.utc) < issue.remediation_submitted_at.replace(tzinfo=timezone.utc):
            return False, ["复测执行发生在整改提交之前（旧证据不能销账）"], evidence
    if issue.remediation_submitted_at is None:
        return False, ["缺少整改提交时间（无法证明复测晚于整改）"], evidence
    # 版本一致性（T32）：清单口径已变更 → 旧 PASS 失效
    if control is not None:
        revision = db.get(QualityControlRevision, run.revision_id) if run.revision_id else None
        if revision is None or revision.version != (control.version or 1):
            return False, [
                f"复测基于版本 {revision.version if revision else '?'}，清单当前版本 {control.version or 1}；口径已变化，需按新版本复测"
            ], evidence
        evidence["control_version"] = revision.version
    # 值域版本一致性（T08）：confirmed 码集指纹已变化 → 旧 PASS 失效
    if control is not None:
        vd_det = db.scalar(
            select(QualityControlDetector).where(
                QualityControlDetector.control_id == control.id,
                QualityControlDetector.detector_kind == "value_domain",
                QualityControlDetector.status == "active",
            )
        )
        if vd_det is not None:
            from .quality_value_domain import current_fingerprint

            fp_now, fp_err = current_fingerprint(
                db, vd_det.result_mapping if isinstance(vd_det.result_mapping, dict) else {},
            )
            if fp_err is not None:
                return False, [f"值域当前不可权威判定：{fp_err}（需按新口径复测）"], evidence
            child_ids = list(db.scalars(
                select(QualityRun.id).where(QualityRun.parent_run_id == run.id)
            ).all())
            refs = [f"asset_quality_runs:{run.id}"] + [f"asset_quality_runs:{cid}" for cid in child_ids]
            # 取最新一条带值域指纹的观测（JSONB 路径过滤方言差异大，取回后在 Python 判）
            obs_list = db.scalars(
                select(QualityObservation)
                .where(QualityObservation.source_record_ref.in_(refs))
                .order_by(QualityObservation.id.desc())
                .limit(10)
            ).all()
            fp_used = next((
                (o.threshold_snapshot or {}).get("value_domain", {}).get("fingerprint")
                for o in obs_list
                if isinstance(o.threshold_snapshot, dict)
                and isinstance(o.threshold_snapshot.get("value_domain"), dict)
            ), None)
            if fp_used is None:
                return False, ["复测观测缺少值域版本指纹（无法证明口径一致），需按新版本复测"], evidence
            if fp_used != fp_now:
                return False, [
                    f"值域版本已变化（复测指纹 {fp_used[:8]}… ≠ 当前 {fp_now[:8]}…）；旧 PASS 失效，需按新值域版本复测"
                ], evidence
            evidence["value_domain_fingerprint"] = fp_now
    # 关闭瞬间复查：本范围在复测完成之后不得有更新的 FAIL（T18）
    if run.finished_at:
        newer_fail = db.scalar(
            select(QualityObservation)
            .where(
                QualityObservation.control_id == issue.control_id,
                QualityObservation.scope_key == (issue.scope_key or run.scope_key),
                QualityObservation.result_status == "fail",
                QualityObservation.observed_at > run.finished_at,
            )
            .order_by(QualityObservation.id.desc())
        )
        if newer_fail is not None:
            return False, [
                f"复测完成后存在更新的 FAIL 观测（#{newer_fail.id}），需重新复测"
            ], evidence
    evidence["checked_at"] = now.isoformat()
    return True, [], evidence


# ─────────────────────────────────────────────────────────────────────────
# 站内通知（幂等；不外发）
# ─────────────────────────────────────────────────────────────────────────

def create_notification(
    db: Session, *, issue_id: int | None, run_id: int | None, recipient: str, notify_type: str,
    payload: dict[str, Any] | None, idempotency_key: str,
) -> QualityNotification | None:
    existing = db.scalar(
        select(QualityNotification).where(QualityNotification.idempotency_key == idempotency_key)
    )
    if existing is not None:
        return None
    row = QualityNotification(
        issue_id=issue_id, run_id=run_id, recipient=recipient or NOTIFY_POOL_RECIPIENT,
        notify_type=notify_type, idempotency_key=idempotency_key, payload=payload,
    )
    db.add(row)
    db.flush()
    return row


def scan_due_notifications(
    db: Session, *, today: date | None = None,
) -> dict[str, int]:
    """临期/逾期/厂商逾期提醒扫描（幂等键含日期 → 每日每类每单至多 1 条）。"""
    today = today or _now().date()
    advance = settings.quality_notify_advance_days
    escalate_after = settings.quality_notify_escalate_after_days
    created = {"remind_due": 0, "overdue": 0, "escalate": 0, "vendor_overdue": 0}
    issues = db.scalars(
        select(QualityIssue).where(
            QualityIssue.archived_at.is_(None),
            QualityIssue.status.notin_(qgs.ISSUE_TERMINAL_STATUSES),
        )
    ).all()
    for issue in issues:
        recipient = issue.assignee_user_identifier or issue.responsible_person_code or NOTIFY_POOL_RECIPIENT
        if issue.due_at and not _is_overdue(issue, today):
            if (issue.due_at - today).days <= advance:
                if create_notification(
                    db, issue_id=issue.id, run_id=None, recipient=recipient,
                    notify_type="remind_due",
                    payload={"issue_code": issue.issue_code, "due_at": issue.due_at.isoformat()},
                    idempotency_key=f"remind_due:{issue.id}:{today.isoformat()}",
                ):
                    created["remind_due"] += 1
        if _is_overdue(issue, today):
            if create_notification(
                db, issue_id=issue.id, run_id=None, recipient=recipient,
                notify_type="overdue",
                payload={"issue_code": issue.issue_code, "due_at": issue.due_at.isoformat()},
                idempotency_key=f"overdue:{issue.id}:{today.isoformat()}",
            ):
                created["overdue"] += 1
            overdue_days = (today - issue.due_at).days
            if overdue_days > escalate_after:
                issue.escalation_level = 1
                if create_notification(
                    db, issue_id=issue.id, run_id=None,
                    recipient=issue.supervisor_user_identifier or NOTIFY_POOL_RECIPIENT,
                    notify_type="escalate",
                    payload={"issue_code": issue.issue_code, "overdue_days": overdue_days},
                    idempotency_key=f"escalate:{issue.id}:{today.isoformat()}",
                ):
                    created["escalate"] += 1
        if (
            issue.status == "waiting_external"
            and issue.vendor_promised_at
            and issue.vendor_promised_at < today
        ):
            if create_notification(
                db, issue_id=issue.id, run_id=None, recipient=recipient,
                notify_type="vendor_overdue",
                payload={"issue_code": issue.issue_code,
                         "vendor_promised_at": issue.vendor_promised_at.isoformat()},
                idempotency_key=f"vendor_overdue:{issue.id}:{today.isoformat()}",
            ):
                created["vendor_overdue"] += 1
    db.flush()
    return created


def _is_overdue(issue: QualityIssue, today: date) -> bool:
    return bool(
        issue.due_at and issue.due_at < today
        and issue.status not in qgs.ISSUE_TERMINAL_STATUSES
    )


# ─────────────────────────────────────────────────────────────────────────
# 调度入队（错过窗口只补一个安全任务；禁止历史洪峰）
# ─────────────────────────────────────────────────────────────────────────

def enqueue_due_scheduled_runs(db: Session, *, now: datetime | None = None) -> dict[str, int]:
    now = now or _now()
    stats = {"controls_scanned": 0, "runs_enqueued": 0, "blocked": 0, "errors": 0}
    controls = db.scalars(
        select(QualityControl).where(
            QualityControl.schedule_enabled == "true",
            QualityControl.lifecycle_status == "active",
        )
    ).all()
    for control in controls:
        stats["controls_scanned"] += 1
        if control.next_run_at is not None:
            nxt = control.next_run_at
            if nxt.replace(tzinfo=timezone.utc) > now:
                continue
        slot = (control.next_run_at or now).replace(minute=0, second=0, microsecond=0)
        try:
            result = create_run(
                db, control, purpose="check", trigger_kind="schedule",
                requested_by="system:scheduler",
                idempotency_key=f"schedule:{control.control_code}:{slot.strftime('%Y%m%d%H')}",
                now=now, actor="system:scheduler",
            )
            if result.get("status") in ("queued", "waiting_window"):
                stats["runs_enqueued"] += 1
            elif result.get("status") == "blocked":
                stats["blocked"] += 1
        except Exception:
            stats["errors"] += 1
        # 无论结果：推进 next_run_at 到未来（错过窗口只补一个安全任务）
        control.next_run_at = _next_cron_fire(control, now)
        control.updated_at = now
    db.flush()
    return stats


def _next_cron_fire(control: QualityControl, now: datetime) -> datetime | None:
    expr = (control.schedule_expr or "").strip()
    if not expr:
        return now + timedelta(hours=24)
    try:
        from apscheduler.triggers.cron import CronTrigger

        tz = control.timezone or settings.scheduler_timezone
        try:
            trigger = CronTrigger.from_crontab(expr, timezone=tz)
        except Exception:
            trigger = CronTrigger.from_crontab(expr)
        nxt = trigger.get_next_fire_time(None, now)
        if nxt is None:
            return now + timedelta(hours=24)
        return nxt if nxt.tzinfo else nxt.replace(tzinfo=timezone.utc)
    except Exception:
        return now + timedelta(hours=24)


def promote_waiting_runs(db: Session, *, now: datetime | None = None) -> int:
    """到窗的 waiting_window 运行单 → queued（父与子一起）。"""
    now = now or _now()
    promoted = 0
    rows = db.scalars(
        select(QualityRun).where(QualityRun.status == "waiting_window")
    ).all()
    for run in rows:
        nxt = run.next_window_at
        if nxt is not None and nxt.replace(tzinfo=timezone.utc) > now:
            continue
        control = db.get(QualityControl, run.control_id)
        if control is not None and not now_in_window(control, now):
            continue
        run.status = "queued"
        run.next_window_at = None
        run.updated_at = now
        promoted += 1
    db.flush()
    return promoted


def process_inline(db: Session, *, max_runs: int = 20) -> list[dict[str, Any]]:
    """隔离/本地演示内联执行（settings.quality_execution_inline=True 时由 API 调用）。

    与 worker 同一条领取/执行/归并链路；仅用于隔离环境浏览器验收。
    """
    results: list[dict[str, Any]] = []
    for _ in range(max_runs):
        run = claim_next_run(db, f"inline:{id(db):x}")
        if run is None:
            break
        results.append(execute_claimed_run(db, run, worker_id=f"inline:{id(db):x}"))
        db.commit()
    return results
