"""174 S2: 数据质量主动治理台账领域服务。

权威状态机/转移矩阵/终态定义在本模块；模型层只存值。
铁律（174 §6）：
  - 每次执行写不可变 Observation；只有 FAIL 才按归并键创建或更新活动 Issue；
  - PASS 只形成绿色观测，不创建占位问题；
  - ERROR/BLOCKED/NO_DATA 不是 PASS，不能自动关闭业务问题；
  - “已解决”必须经过复测与有权限人员确认；
  - 改变台账的命令在调用方同一事务内写主表 + IssueEvent + GovernAuditLog。

并发安全：
  - issue_code 用数据库序列 asset.asset_quality_issue_code_seq；
  - 活动问题唯一性靠部分唯一索引 uq_asset_quality_issues_active；
  - 命令走乐观锁 lock_version，冲突抛 LockConflictError（路由层 409）。
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import Select, or_, select, text
from sqlalchemy.orm import Session

from ..models.governance_base import GovernAuditLog
from ..models.identity import IdentityPerson, IdentityPersonDepartment
from ..models.quality_governance import (
    QualityControl,
    QualityControlDetector,
    QualityIssue,
    QualityIssueEvent,
    QualityObservation,
)

# ─────────────────────────────────────────────────────────────────────────
# 状态与转移矩阵（174 §6.1/§6.2）
# ─────────────────────────────────────────────────────────────────────────

ISSUE_STATUSES = (
    "new",
    "acknowledged",
    "assigned",
    "in_progress",
    "waiting_external",
    "waiting_verify",
    "resolved",
    "accepted_risk",
    "false_positive",
    "duplicate",
    "cancelled",
)
ISSUE_TERMINAL_STATUSES = ("resolved", "accepted_risk", "false_positive", "duplicate", "cancelled")

ISSUE_TRANSITIONS: dict[str, frozenset[str]] = {
    "new": frozenset({"acknowledged", "false_positive", "duplicate", "cancelled"}),
    "acknowledged": frozenset({"assigned", "in_progress", "waiting_external", "accepted_risk"}),
    "assigned": frozenset({"in_progress", "waiting_external", "waiting_verify"}),
    "in_progress": frozenset({"waiting_external", "waiting_verify"}),
    "waiting_external": frozenset({"in_progress", "waiting_verify"}),
    "waiting_verify": frozenset({"in_progress", "resolved"}),
    # resolved/accepted_risk/false_positive → acknowledged 仅复发、复审或抑制到期（重开，走专用命令）
    "resolved": frozenset({"acknowledged"}),
    "accepted_risk": frozenset({"acknowledged"}),
    "false_positive": frozenset({"acknowledged"}),
    "duplicate": frozenset(),
    "cancelled": frozenset(),
}

OBSERVATION_RESULTS = ("pass", "fail", "error", "blocked", "skipped", "no_data")
NO_DATA_POLICIES = ("pass", "fail", "blocked")
CONTROL_LIFECYCLE = ("draft", "active", "blocked", "deprecated")
DETECTOR_KINDS = ("probe_template", "quality_rule", "manual", "external")
ISSUE_TYPES = ("data_defect", "monitoring_gap", "manual")
SEVERITIES = ("critical", "high", "medium", "low", "info")
PRIORITIES = ("P1", "P2", "P3", "P4")
DIMENSIONS = (
    "completeness",
    "validity",
    "consistency",
    "timeliness",
    "uniqueness",
    "referential",
    "cross_system",
    "monitoring",
)
CATEGORIES = ("R-REF", "R-CNT", "R-KEY", "R-XSYS", "R-DOM", "MANUAL")
COMPARATORS = ("gt", "gte", "lt", "lte", "eq")

EVENT_TYPES = (
    "created",
    "acknowledged",
    "assigned",
    "status_changed",
    "action_plan_updated",
    "fields_updated",
    "comment_added",
    "observation_linked",
    "verification_requested",
    "verification_passed",
    "verification_failed",
    "reopened",
    "resolved",
    "risk_accepted",
    "suppression_set",
    "duplicate_marked",
)


class TransitionError(Exception):
    """非法状态流转（路由层 409）。"""


class LockConflictError(Exception):
    """乐观锁冲突（路由层 409）。"""


class IssueValidationError(Exception):
    """命令必填字段缺失（路由层 422）。"""


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ─────────────────────────────────────────────────────────────────────────
# issue_code 生成（数据库序列，并发安全；禁止 MAX(id)+1）
# ─────────────────────────────────────────────────────────────────────────

def next_issue_code(db: Session) -> str:
    seq = db.execute(text("SELECT nextval('asset.asset_quality_issue_code_seq')")).scalar_one()
    month = _now().strftime("%Y%m")
    return f"DQI-{month}-{int(seq):06d}"


# ─────────────────────────────────────────────────────────────────────────
# 身份范围（本人/本科室；174 §7）
# ─────────────────────────────────────────────────────────────────────────

def resolve_user_scope(db: Session, user_identifier: str) -> dict[str, Any]:
    """user_identifier → person_code + 所属科室编码集合。

    AuthUser.user_identifier 与 Person.person_code 同一命名空间（174 §2.3）；
    多科室取 IdentityPersonDepartment 并集（含主科室行）。
    """
    dept_codes: set[str] = set()
    person = db.scalar(
        select(IdentityPerson).where(IdentityPerson.person_code == user_identifier)
    )
    if person is not None and person.dept_code:
        dept_codes.add(person.dept_code)
    for pd in db.scalars(
        select(IdentityPersonDepartment).where(
            IdentityPersonDepartment.person_code == user_identifier
        )
    ):
        if pd.dept_code:
            dept_codes.add(pd.dept_code)
    return {
        "user_identifier": user_identifier,
        "person": person,
        "dept_codes": sorted(dept_codes),
    }


def user_can_touch_issue(issue: QualityIssue, scope: dict[str, Any]) -> bool:
    """处理权数据范围：经办为本人、责任人为本人、或主责科室在本人科室集合内。"""
    uid = scope["user_identifier"]
    if issue.assignee_user_identifier == uid:
        return True
    if issue.responsible_person_code == uid:
        return True
    return bool(issue.responsible_dept_code and issue.responsible_dept_code in scope["dept_codes"])


def apply_issue_scope_filter(q: Select, scope: dict[str,Any], *, mode: str) -> Select:
    """列表/导出统一数据范围：mine=本人经办/负责；department=本科室；all 不加过滤（需 read_all）。"""
    uid = scope["user_identifier"]
    if mode == "mine":
        return q.where(
            or_(
                QualityIssue.assignee_user_identifier == uid,
                QualityIssue.responsible_person_code == uid,
            )
        )
    if mode == "department":
        dept_codes = scope["dept_codes"] or ["__none__"]
        return q.where(
            or_(
                QualityIssue.assignee_user_identifier == uid,
                QualityIssue.responsible_person_code == uid,
                QualityIssue.responsible_dept_code.in_(dept_codes),
            )
        )
    return q


# ─────────────────────────────────────────────────────────────────────────
# 事件与审计（同事务；调用方 commit）
# ─────────────────────────────────────────────────────────────────────────

def add_event(
    db: Session,
    issue: QualityIssue,
    event_type: str,
    *,
    from_status: str | None = None,
    to_status: str | None = None,
    reason: str | None = None,
    observation_id: int | None = None,
    actor: str | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    correlation_id: str | None = None,
) -> QualityIssueEvent:
    if event_type not in EVENT_TYPES:
        raise ValueError(f"未知事件类型: {event_type}")
    ev = QualityIssueEvent(
        issue_id=issue.id,
        event_type=event_type,
        from_status=from_status,
        to_status=to_status,
        before_json=before,
        after_json=after,
        reason=reason,
        observation_id=observation_id,
        actor_user_identifier=actor,
        correlation_id=correlation_id,
        occurred_at=_now(),
    )
    db.add(ev)
    return ev


def add_audit(
    db: Session,
    *,
    action: str,
    entity_type: str,
    entity_ref: str,
    operator: str | None,
    reason: str | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> GovernAuditLog:
    row = GovernAuditLog(
        module="quality_governance",
        entity_type=entity_type,
        entity_ref=entity_ref,
        action=action,
        before_data=before,
        after_data=after,
        operator=operator,
        reason=reason,
    )
    db.add(row)
    return row


def _issue_snapshot(issue: QualityIssue) -> dict[str, Any]:
    return {
        "status": issue.status,
        "severity": issue.severity,
        "priority": issue.priority,
        "responsible_dept_code": issue.responsible_dept_code,
        "responsible_person_code": issue.responsible_person_code,
        "assignee_user_identifier": issue.assignee_user_identifier,
        "action_plan": issue.action_plan,
        "due_at": issue.due_at.isoformat() if issue.due_at else None,
        "wait_kind": issue.wait_kind,
    }


def _bump(issue: QualityIssue, actor: str | None) -> None:
    issue.lock_version = (issue.lock_version or 0) + 1
    issue.updated_by = actor
    issue.updated_at = _now()


# ─────────────────────────────────────────────────────────────────────────
# 活动问题查找 / 误报抑制 / 复发链
# ─────────────────────────────────────────────────────────────────────────

def find_active_issue(
    db: Session, control_id: int, scope_key: str
) -> QualityIssue | None:
    return db.scalar(
        select(QualityIssue)
        .where(
            QualityIssue.control_id == control_id,
            QualityIssue.scope_key == scope_key,
            QualityIssue.archived_at.is_(None),
            QualityIssue.status.notin_(ISSUE_TERMINAL_STATUSES),
        )
        .order_by(QualityIssue.id.desc())
    )


def _suppression_active(db: Session, control_id: int, scope_key: str, control_version: int) -> bool:
    """误报抑制只作用于指定 control_version + scope，且 suppressed_until 未到期（174 §6.4）。"""
    row = db.scalar(
        select(QualityIssue)
        .where(
            QualityIssue.control_id == control_id,
            QualityIssue.scope_key == scope_key,
            QualityIssue.status == "false_positive",
            QualityIssue.suppressed_control_version == control_version,
            QualityIssue.suppressed_until.isnot(None),
            QualityIssue.suppressed_until >= date.today(),
        )
        .order_by(QualityIssue.id.desc())
    )
    return row is not None


def _latest_terminal_issue(
    db: Session, control_id: int, scope_key: str
) -> QualityIssue | None:
    return db.scalar(
        select(QualityIssue)
        .where(
            QualityIssue.control_id == control_id,
            QualityIssue.scope_key == scope_key,
            QualityIssue.status.in_(("resolved", "accepted_risk")),
        )
        .order_by(QualityIssue.id.desc())
    )


# ─────────────────────────────────────────────────────────────────────────
# 观测摄取与归并（174 §6.3）——核心自动化路径
# ─────────────────────────────────────────────────────────────────────────

def apply_observation(
    db: Session,
    *,
    control_id: int,
    run_key: str,
    scope_key: str,
    result_status: str,
    control_version: int | None = None,
    detector_id: int | None = None,
    window_start: date | None = None,
    window_end: date | None = None,
    metric_value: float | None = None,
    metric_unit: str | None = None,
    threshold_snapshot: dict[str, Any] | None = None,
    control_definition_snapshot: dict[str, Any] | None = None,
    numerator: float | None = None,
    denominator: float | None = None,
    source_kind: str = "external",
    source_record_ref: str | None = None,
    evidence_digest: str | None = None,
    evidence_ref: str | None = None,
    historical_precision: str = "exact",
    error_code: str | None = None,
    error_message_sanitized: str | None = None,
    actor: str = "system:quality_governance",
    correlation_id: str | None = None,
    observation_time: datetime | None = None,
) -> dict[str, Any]:
    """写一条不可变观测并执行归并。

    返回 {"outcome": duplicate|observed|issue_created|issue_updated|issue_left|
            monitoring_gap_created|monitoring_gap_updated|suppressed,
          "observation_id": int, "issue_id": int|None, "issue_code": str|None}。
    幂等：同 (control_id, detector_id, run_key, scope_key) 已存在 → duplicate，零写入。
    """
    if result_status not in OBSERVATION_RESULTS:
        raise ValueError(f"非法观测结果: {result_status}")

    existing = db.scalar(
        select(QualityObservation).where(
            QualityObservation.control_id == control_id,
            (
                QualityObservation.detector_id == detector_id
                if detector_id is not None
                else QualityObservation.detector_id.is_(None)
            ),
            QualityObservation.run_key == run_key,
            QualityObservation.scope_key == scope_key,
        )
    )
    if existing is not None:
        return {
            "outcome": "duplicate",
            "observation_id": existing.id,
            "issue_id": existing.issue_id,
            "issue_code": None,
        }

    control = db.get(QualityControl, control_id)
    if control is None:
        raise LookupError(f"control {control_id} not found")
    eff_version = control_version if control_version is not None else (control.version or 1)

    obs = QualityObservation(
        control_id=control_id,
        detector_id=detector_id,
        control_version=eff_version,
        run_key=run_key,
        scope_key=scope_key,
        window_start=window_start,
        window_end=window_end,
        observed_at=observation_time or _now(),
        result_status=result_status,
        metric_value=metric_value,
        metric_unit=metric_unit,
        threshold_snapshot=threshold_snapshot,
        control_definition_snapshot=control_definition_snapshot,
        numerator=numerator,
        denominator=denominator,
        source_kind=source_kind,
        source_record_ref=source_record_ref,
        evidence_digest=evidence_digest,
        evidence_ref=evidence_ref,
        historical_precision=historical_precision,
        error_code=error_code,
        error_message_sanitized=error_message_sanitized,
        created_by=actor,
    )
    db.add(obs)
    db.flush()  # 取 observation id

    # NO_DATA 折算：按清单 no_data_policy 映射为等价行为（观测本身保留 no_data）
    effective = result_status
    if result_status == "no_data":
        policy = (control.no_data_policy or "blocked").lower()
        effective = {"pass": "pass", "fail": "fail", "blocked": "blocked"}[policy]

    if effective == "fail":
        return _merge_fail(
            db,
            control=control,
            obs=obs,
            scope_key=scope_key,
            eff_version=eff_version,
            actor=actor,
            correlation_id=correlation_id,
            issue_type="data_defect",
        )
    if effective == "blocked":
        return _merge_fail(
            db,
            control=control,
            obs=obs,
            scope_key=scope_key,
            eff_version=eff_version,
            actor=actor,
            correlation_id=correlation_id,
            issue_type="monitoring_gap",
        )
    if effective == "pass":
        active = find_active_issue(db, control.id, scope_key)
        if active is not None:
            obs.issue_id = active.id
            active.latest_observation_id = obs.id
            active.latest_metric_value = obs.metric_value
            active.latest_result_status = obs.result_status
            active.last_seen_at = obs.observed_at
            _bump(active, actor)
            add_event(
                db,
                active,
                "observation_linked",
                reason=f"PASS 观测挂接（当前状态 {active.status}，不自动关闭）",
                observation_id=obs.id,
                actor=actor,
                correlation_id=correlation_id,
                after={"result_status": obs.result_status, "metric_value": float(obs.metric_value) if obs.metric_value is not None else None},
            )
            return {"outcome": "issue_left", "observation_id": obs.id, "issue_id": active.id, "issue_code": active.issue_code}
        return {"outcome": "observed", "observation_id": obs.id, "issue_id": None, "issue_code": None}

    # error / skipped：只记录，不建单也不关闭
    return {"outcome": "observed", "observation_id": obs.id, "issue_id": None, "issue_code": None}


def _merge_fail(
    db: Session,
    *,
    control: QualityControl,
    obs: QualityObservation,
    scope_key: str,
    eff_version: int,
    actor: str,
    correlation_id: str | None,
    issue_type: str,
) -> dict[str, Any]:
    active = find_active_issue(db, control.id, scope_key)
    if active is not None:
        obs.issue_id = active.id
        active.latest_observation_id = obs.id
        active.latest_metric_value = obs.metric_value
        active.latest_result_status = obs.result_status
        active.last_seen_at = obs.observed_at
        _bump(active, actor)
        add_event(
            db,
            active,
            "observation_linked",
            reason=f"{obs.result_status.upper()} 观测挂接（活动问题不重复建单）",
            observation_id=obs.id,
            actor=actor,
            correlation_id=correlation_id,
            after={"result_status": obs.result_status, "metric_value": float(obs.metric_value) if obs.metric_value is not None else None},
        )
        return {
            "outcome": "monitoring_gap_updated" if active.issue_type == "monitoring_gap" else "issue_updated",
            "observation_id": obs.id,
            "issue_id": active.id,
            "issue_code": active.issue_code,
        }

    if issue_type == "data_defect" and _suppression_active(db, control.id, scope_key, eff_version):
        return {"outcome": "suppressed", "observation_id": obs.id, "issue_id": None, "issue_code": None}

    # 复发链：同 control+scope 上一条已关闭问题 → recurrence_of + recurrence_no+1
    prev = _latest_terminal_issue(db, control.id, scope_key)
    recurrence_of = prev.id if prev is not None else None
    recurrence_no = (prev.recurrence_no + 1) if prev is not None else 0

    issue = QualityIssue(
        issue_code=next_issue_code(db),
        control_id=control.id,
        issue_type=issue_type,
        title=control.title if issue_type != "monitoring_gap" else f"[监测覆盖缺口] {control.title}",
        description=(
            control.description
            if issue_type != "monitoring_gap"
            else (control.blocked_reason or "检测通道阻塞，暂无数据，登记为监测覆盖缺口")
        ),
        primary_system_code=control.primary_system_code,
        related_system_codes=control.related_system_codes,
        object_key=control.object_key,
        object_name_snapshot=control.object_name_snapshot,
        scope_key=scope_key,
        severity=(control.default_severity or "medium") if issue_type != "monitoring_gap" else "low",
        priority=(control.default_priority or "P3") if issue_type != "monitoring_gap" else "P4",
        status="new",
        responsible_dept_code=control.default_dept_code,
        responsible_person_code=control.default_person_code,
        latest_observation_id=obs.id,
        latest_metric_value=obs.metric_value,
        latest_result_status=obs.result_status,
        opened_control_version=eff_version,
        first_seen_at=obs.observed_at,
        last_seen_at=obs.observed_at,
        recurrence_of_issue_id=recurrence_of,
        recurrence_no=recurrence_no,
        created_by=actor,
        updated_by=actor,
    )
    db.add(issue)
    db.flush()
    obs.issue_id = issue.id
    add_event(
        db,
        issue,
        "created",
        to_status="new",
        reason=f"观测 {obs.result_status.upper()} 自动建单（run_key={obs.run_key}）",
        observation_id=obs.id,
        actor=actor,
        correlation_id=correlation_id,
        after={"scope_key": scope_key, "recurrence_no": recurrence_no, "issue_type": issue_type},
    )
    outcome = "monitoring_gap_created" if issue_type == "monitoring_gap" else "issue_created"
    return {"outcome": outcome, "observation_id": obs.id, "issue_id": issue.id, "issue_code": issue.issue_code}


# ─────────────────────────────────────────────────────────────────────────
# 手工建单（174 §8.3 POST /quality-issues）
# ─────────────────────────────────────────────────────────────────────────

def create_manual_issue(
    db: Session,
    *,
    title: str,
    description: str | None = None,
    issue_type: str = "manual",
    primary_system_code: str | None = None,
    related_system_codes: list[str] | None = None,
    object_key: str | None = None,
    object_name_snapshot: str | None = None,
    control_id: int | None = None,
    scope_key: str | None = None,
    severity: str = "medium",
    priority: str = "P3",
    responsible_dept_code: str | None = None,
    responsible_person_code: str | None = None,
    assignee_user_identifier: str | None = None,
    responsible_dept_name_snapshot: str | None = None,
    responsible_person_name_snapshot: str | None = None,
    assignee_name_snapshot: str | None = None,
    action_plan: str | None = None,
    due_at: date | None = None,
    evidence_ref: str | None = None,
    actor: str = "system:quality_governance",
    reason: str | None = None,
    correlation_id: str | None = None,
) -> QualityIssue:
    if issue_type not in ISSUE_TYPES:
        raise IssueValidationError(f"非法 issue_type: {issue_type}")
    if severity not in SEVERITIES:
        raise IssueValidationError(f"非法 severity: {severity}")
    if priority not in PRIORITIES:
        raise IssueValidationError(f"非法 priority: {priority}")
    if control_id is not None and not (scope_key or "").strip():
        raise IssueValidationError("绑定质控清单时必须提供 scope_key（PostgreSQL 部分唯一索引对 NULL 不互斥）")
    # 有 control 的手工问题占用活动唯一性；重复创建由部分唯一索引兜底并返回 409
    issue = QualityIssue(
        issue_code=next_issue_code(db),
        control_id=control_id,
        issue_type=issue_type,
        title=title,
        description=description,
        primary_system_code=primary_system_code,
        related_system_codes=related_system_codes,
        object_key=object_key,
        object_name_snapshot=object_name_snapshot,
        scope_key=scope_key,
        severity=severity,
        priority=priority,
        status="new",
        responsible_dept_code=responsible_dept_code,
        responsible_person_code=responsible_person_code,
        assignee_user_identifier=assignee_user_identifier,
        responsible_dept_name_snapshot=responsible_dept_name_snapshot,
        responsible_person_name_snapshot=responsible_person_name_snapshot,
        assignee_name_snapshot=assignee_name_snapshot,
        action_plan=action_plan,
        due_at=due_at,
        first_seen_at=_now(),
        last_seen_at=_now(),
        created_by=actor,
        updated_by=actor,
    )
    db.add(issue)
    db.flush()
    add_event(
        db,
        issue,
        "created",
        to_status="new",
        reason=reason or "手工登记",
        actor=actor,
        correlation_id=correlation_id,
        after={"evidence_ref": evidence_ref, "issue_type": issue_type},
    )
    add_audit(
        db,
        action="create",
        entity_type="quality_issue",
        entity_ref=issue.issue_code,
        operator=actor,
        reason=reason,
        after={"title": title, "status": "new"},
    )
    return issue


# ─────────────────────────────────────────────────────────────────────────
# 命令实现（乐观锁 + 事件 + 审计；路由层负责权限/数据范围）
# ─────────────────────────────────────────────────────────────────────────

def _check_lock(issue: QualityIssue, expected_lock_version: int | None) -> None:
    if expected_lock_version is None:
        raise IssueValidationError("expected_lock_version 必填（乐观锁）")
    if issue.lock_version != expected_lock_version:
        raise LockConflictError(
            f"lock_version 冲突：期望 {expected_lock_version}，实际 {issue.lock_version}"
        )


def assign_issue(
    db: Session,
    issue: QualityIssue,
    *,
    expected_lock_version: int,
    responsible_dept_code: str | None = None,
    responsible_person_code: str | None = None,
    assignee_user_identifier: str | None = None,
    responsible_dept_name_snapshot: str | None = None,
    responsible_person_name_snapshot: str | None = None,
    assignee_name_snapshot: str | None = None,
    actor: str,
    reason: str | None = None,
    correlation_id: str | None = None,
) -> QualityIssue:
    _check_lock(issue, expected_lock_version)
    if issue.status == "new":
        raise TransitionError("问题需先确认（acknowledged）再分派")
    if issue.status not in ("acknowledged", "assigned", "in_progress", "waiting_external"):
        raise TransitionError(f"当前状态 {issue.status} 不允许分派")
    before = _issue_snapshot(issue)
    issue.responsible_dept_code = responsible_dept_code or issue.responsible_dept_code
    issue.responsible_person_code = responsible_person_code or issue.responsible_person_code
    issue.assignee_user_identifier = assignee_user_identifier or issue.assignee_user_identifier
    if responsible_dept_name_snapshot is not None:
        issue.responsible_dept_name_snapshot = responsible_dept_name_snapshot
    if responsible_person_name_snapshot is not None:
        issue.responsible_person_name_snapshot = responsible_person_name_snapshot
    if assignee_name_snapshot is not None:
        issue.assignee_name_snapshot = assignee_name_snapshot
    from_status = issue.status
    if from_status == "acknowledged":
        issue.status = "assigned"
    _bump(issue, actor)
    add_event(
        db,
        issue,
        "assigned",
        from_status=from_status,
        to_status=issue.status,
        reason=reason,
        actor=actor,
        correlation_id=correlation_id,
        before=before,
        after=_issue_snapshot(issue),
    )
    add_audit(
        db,
        action="assign",
        entity_type="quality_issue",
        entity_ref=issue.issue_code,
        operator=actor,
        reason=reason,
        before=before,
        after=_issue_snapshot(issue),
    )
    return issue


def transition_issue(
    db: Session,
    issue: QualityIssue,
    *,
    to_status: str,
    expected_lock_version: int,
    actor: str,
    reason: str,
    action_plan: str | None = None,
    due_at: date | None = None,
    wait_kind: str | None = None,
    wait_note: str | None = None,
    external_ticket_ref: str | None = None,
    risk_reason: str | None = None,
    risk_approver: str | None = None,
    risk_review_at: date | None = None,
    false_positive_reason: str | None = None,
    suppressed_until: date | None = None,
    suppressed_control_version: int | None = None,
    duplicate_of_issue_id: int | None = None,
    reopen_as_recurrence: bool = False,
    correlation_id: str | None = None,
) -> QualityIssue:
    """通用转移（专用命令 verify/accept-risk/mark-false-positive 之外的路径）。

    resolved 必须走 verify_issue；重开（终态→acknowledged）仅复发/复审到期场景。
    """
    _check_lock(issue, expected_lock_version)
    if to_status == "resolved":
        raise TransitionError("resolved 必须走复测验证专用命令 /verify")
    allowed = ISSUE_TRANSITIONS.get(issue.status, frozenset())
    if to_status not in allowed:
        raise TransitionError(f"不允许的迁移: {issue.status} -> {to_status}")
    if issue.status in ISSUE_TERMINAL_STATUSES and not reopen_as_recurrence:
        raise TransitionError("终态重开仅限复发/复审到期场景（reopen_as_recurrence）")

    before = _issue_snapshot(issue)
    from_status = issue.status

    # 目标态必填校验（174 §5.4 关键约束）
    if to_status == "waiting_external":
        if not wait_kind or not (wait_note or reason):
            raise IssueValidationError("waiting_external 必须有 wait_kind 和说明")
        issue.wait_kind = wait_kind
        issue.wait_note = wait_note
        if external_ticket_ref is not None:
            issue.external_ticket_ref = external_ticket_ref
    if to_status == "waiting_verify":
        eff_plan = action_plan or issue.action_plan
        if not eff_plan:
            raise IssueValidationError("waiting_verify 必须有整改措施（action_plan）")
        issue.action_plan = eff_plan
    if to_status == "accepted_risk":
        if not risk_reason or not risk_approver or risk_review_at is None:
            raise IssueValidationError("accepted_risk 必须有原因、批准人和复审日期")
        issue.risk_reason = risk_reason
        issue.risk_approver = risk_approver
        issue.risk_review_at = risk_review_at
    if to_status == "false_positive":
        if not false_positive_reason or suppressed_until is None or suppressed_control_version is None:
            raise IssueValidationError(
            "false_positive 必须有原因、suppressed_control_version 和 suppressed_until（禁止永久抑制）"
        )
        if issue.control_id is None:
            raise IssueValidationError("无 control 的问题不能按版本抑制误报，请用 cancelled")
        issue.false_positive_reason = false_positive_reason
        issue.suppressed_until = suppressed_until
        issue.suppressed_control_version = suppressed_control_version
    if to_status == "duplicate":
        if duplicate_of_issue_id is None:
            raise IssueValidationError("duplicate 必须指定 duplicate_of_issue_id")
        if duplicate_of_issue_id == issue.id:
            raise IssueValidationError("不能与自身互为重复")
        issue.duplicate_of_issue_id = duplicate_of_issue_id
    if action_plan is not None and to_status != "waiting_verify":
        issue.action_plan = action_plan
    if due_at is not None:
        issue.due_at = due_at

    issue.status = to_status
    _bump(issue, actor)

    event_type = {
        "acknowledged": "acknowledged",
        "accepted_risk": "risk_accepted",
        "false_positive": "suppression_set",
        "duplicate": "duplicate_marked",
    }.get(to_status, "status_changed")
    if from_status in ISSUE_TERMINAL_STATUSES and to_status == "acknowledged":
        event_type = "reopened"

    add_event(
        db,
        issue,
        event_type,
        from_status=from_status,
        to_status=to_status,
        reason=reason,
        actor=actor,
        correlation_id=correlation_id,
        before=before,
        after=_issue_snapshot(issue),
    )
    add_audit(
        db,
        action="transition",
        entity_type="quality_issue",
        entity_ref=issue.issue_code,
        operator=actor,
        reason=reason,
        before=before,
        after=_issue_snapshot(issue),
    )
    return issue


def request_verification(
    db: Session,
    issue: QualityIssue,
    *,
    expected_lock_version: int,
    actor: str,
    reason: str,
    action_plan: str | None = None,
    correlation_id: str | None = None,
) -> QualityIssue:
    """经办提交待复测：assigned/in_progress/waiting_external → waiting_verify。"""
    _check_lock(issue, expected_lock_version)
    if issue.status not in ("assigned", "in_progress", "waiting_external"):
        raise TransitionError(f"当前状态 {issue.status} 不允许提交复测")
    eff_plan = action_plan or issue.action_plan
    if not eff_plan:
        raise IssueValidationError("waiting_verify 必须有整改措施（action_plan）")
    before = _issue_snapshot(issue)
    from_status = issue.status
    if action_plan is not None:
        issue.action_plan = action_plan
    issue.status = "waiting_verify"
    _bump(issue, actor)
    add_event(
        db,
        issue,
        "verification_requested",
        from_status=from_status,
        to_status="waiting_verify",
        reason=reason,
        actor=actor,
        correlation_id=correlation_id,
        before=before,
        after=_issue_snapshot(issue),
    )
    add_audit(
        db,
        action="request_verification",
        entity_type="quality_issue",
        entity_ref=issue.issue_code,
        operator=actor,
        reason=reason,
        before=before,
        after=_issue_snapshot(issue),
    )
    return issue


def verify_issue(
    db: Session,
    issue: QualityIssue,
    *,
    expected_lock_version: int,
    passed: bool,
    actor: str,
    reason: str,
    resolution_summary: str | None = None,
    verification_observation_id: int | None = None,
    correlation_id: str | None = None,
) -> QualityIssue:
    """复测验证：waiting_verify → resolved（通过）或 in_progress（不通过）。

    验证人不能是最后一次提交 waiting_verify 的同一经办人（174 §7.5）；
    平台管理员豁免（路由层判断并强制 reason）。
    """
    _check_lock(issue, expected_lock_version)
    if issue.status != "waiting_verify":
        raise TransitionError(f"当前状态 {issue.status} 不允许验证（需 waiting_verify）")
    if not reason or not reason.strip():
        raise IssueValidationError("验证必须填写结论说明")
    before = _issue_snapshot(issue)
    from_status = issue.status
    if passed:
        issue.status = "resolved"
        issue.resolution_summary = resolution_summary or reason
        issue.resolved_at = _now()
        issue.resolved_by = actor
        event_type = "verification_passed"
        audit_action = "verify_pass"
    else:
        issue.status = "in_progress"
        event_type = "verification_failed"
        audit_action = "verify_fail"
    _bump(issue, actor)
    add_event(
        db,
        issue,
        event_type,
        from_status=from_status,
        to_status=issue.status,
        reason=reason,
        observation_id=verification_observation_id,
        actor=actor,
        correlation_id=correlation_id,
        before=before,
        after=_issue_snapshot(issue),
    )
    add_audit(
        db,
        action=audit_action,
        entity_type="quality_issue",
        entity_ref=issue.issue_code,
        operator=actor,
        reason=reason,
        before=before,
        after=_issue_snapshot(issue),
    )
    return issue


def last_verification_requester(db: Session, issue_id: int) -> str | None:
    row = db.scalar(
        select(QualityIssueEvent)
        .where(
            QualityIssueEvent.issue_id == issue_id,
            QualityIssueEvent.event_type == "verification_requested",
        )
        .order_by(QualityIssueEvent.id.desc())
    )
    return row.actor_user_identifier if row else None


def mark_false_positive(
    db: Session,
    issue: QualityIssue,
    *,
    expected_lock_version: int,
    false_positive_reason: str,
    suppressed_until: date,
    actor: str,
    reason: str,
    correlation_id: str | None = None,
) -> QualityIssue:
    """误报抑制：仅按 control_version + scope 限时抑制（禁止永久）。"""
    if issue.control_id is None:
        raise IssueValidationError("无 control 的问题不能按版本抑制误报，请用 cancelled")
    control = db.get(QualityControl, issue.control_id)
    version = (control.version if control else 1) or 1
    return transition_issue(
        db,
        issue,
        to_status="false_positive",
        expected_lock_version=expected_lock_version,
        actor=actor,
        reason=reason,
        false_positive_reason=false_positive_reason,
        suppressed_until=suppressed_until,
        suppressed_control_version=version,
        correlation_id=correlation_id,
    )


def patch_issue(
    db: Session,
    issue: QualityIssue,
    *,
    expected_lock_version: int,
    actor: str,
    fields: dict[str, Any],
    correlation_id: str | None = None,
) -> QualityIssue:
    """通用 PATCH：只改非状态字段（状态走专用命令；绕过状态机在此被结构性拒绝）。"""
    _check_lock(issue, expected_lock_version)
    editable = {
        "title",
        "description",
        "action_plan",
        "due_at",
        "severity",
        "priority",
        "wait_kind",
        "wait_note",
        "external_ticket_ref",
        "primary_system_code",
        "related_system_codes",
        "object_key",
        "object_name_snapshot",
        "responsible_dept_code",
        "responsible_person_code",
        "assignee_user_identifier",
        "responsible_dept_name_snapshot",
        "responsible_person_name_snapshot",
        "assignee_name_snapshot",
        "resolution_summary",
    }
    blocked = {"status", "issue_code", "id", "lock_version", "control_id", "scope_key"}
    unknown = set(fields) - editable - blocked
    if unknown:
        raise IssueValidationError(f"不可编辑字段: {sorted(unknown)}")
    touched_status = set(fields) & blocked
    if touched_status:
        raise IssueValidationError(f"状态字段必须走专用命令: {sorted(touched_status)}")
    if "severity" in fields and fields["severity"] not in SEVERITIES:
        raise IssueValidationError(f"非法 severity: {fields['severity']}")
    if "priority" in fields and fields["priority"] not in PRIORITIES:
        raise IssueValidationError(f"非法 priority: {fields['priority']}")
    before = _issue_snapshot(issue)
    for key, value in fields.items():
        setattr(issue, key, value)
    _bump(issue, actor)
    add_event(
        db,
        issue,
        "action_plan_updated" if set(fields) <= {"action_plan", "due_at"} else "fields_updated",
        reason="字段更新",
        actor=actor,
        correlation_id=correlation_id,
        before=before,
        after=_issue_snapshot(issue),
    )
    add_audit(
        db,
        action="patch",
        entity_type="quality_issue",
        entity_ref=issue.issue_code,
        operator=actor,
        reason="字段更新",
        before=before,
        after=_issue_snapshot(issue),
    )
    return issue


def add_comment(
    db: Session,
    issue: QualityIssue,
    *,
    actor: str,
    reason: str,
    correlation_id: str | None = None,
) -> QualityIssueEvent:
    """纯评论：不动状态，不递增 lock_version。"""
    return add_event(
        db,
        issue,
        "comment_added",
        reason=reason,
        actor=actor,
        correlation_id=correlation_id,
    )


# ─────────────────────────────────────────────────────────────────────────
# allowed_actions（后端权威；前端据此渲染按钮）
# ─────────────────────────────────────────────────────────────────────────

def compute_allowed_actions(
    db: Session,
    issue: QualityIssue,
    *,
    user_identifier: str,
    has: dict[str, bool],
    scope: dict[str, Any],
) -> list[str]:
    """按权限 + 数据范围 + 状态机计算当前用户可执行动作。

    has: {"read_all":…, "create":…, "assign":…, "handle":…, "verify":…,
          "accept_risk":…, "export":…, "manage":…, "is_admin":…}
    """
    actions: list[str] = []
    in_scope = has.get("read_all") or user_can_touch_issue(issue, scope)
    is_admin = has.get("is_admin", False)

    if has.get("handle") and in_scope and issue.status not in ISSUE_TERMINAL_STATUSES:
        if issue.status == "new":
            actions.append("acknowledge")
        if issue.status in ("acknowledged", "assigned", "in_progress", "waiting_external"):
            actions.append("start")  # → in_progress（acknowledged 直接开工）
        if issue.status in ("in_progress", "waiting_external"):
            actions.append("wait_external")
            actions.append("request_verification")
        if issue.status == "assigned":
            actions.append("request_verification")
        if issue.status == "waiting_verify":
            actions.append("resume")  # 验证不通过回 in_progress 由 verify 命令表达
        actions.append("edit")
        actions.append("comment")

    if (
        has.get("assign")
        and in_scope
        and issue.status in ("acknowledged", "assigned", "in_progress", "waiting_external")
    ):
        actions.append("assign")

    if (
        has.get("verify")
        and issue.status == "waiting_verify"
        and (has.get("read_all") or in_scope)
    ):
        requester = last_verification_requester(db, issue.id)
        if requester != user_identifier or is_admin:
            actions.append("verify")

    if has.get("accept_risk") and in_scope and issue.status == "acknowledged":
        actions.append("accept_risk")

    if has.get("handle") and in_scope and issue.status == "new":
        actions.append("mark_false_positive")
        actions.append("cancel")
        actions.append("mark_duplicate")

    if is_admin and issue.status in ("resolved", "accepted_risk", "false_positive"):
        actions.append("reopen")

    return actions
