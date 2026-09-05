"""174 S5: 质量问题台账 API（/api/v1/quality-issues）。

命令统一 envelope：reason + expected_lock_version + correlation_id；
返回更新后的 issue + allowed_actions + lock_version。
数据范围（后端强制）：mine/department 任何读权限用户；all 需 quality.issue.read_all。
导出六硬约束复用 166 B1/B12 口径（独立权限+审计+时间戳文件名+防公式注入+
逐列白名单+POST body 筛选+5000 上限）。
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ...core.db import get_db
from ...core.security import _effective_role_codes, require_permission
from ...models.governance_base import GovernAuditLog
from ...models.identity import IdentityDepartment, IdentityPerson
from ...models.quality_governance import (
    QualityControl,
    QualityIssue,
    QualityIssueEvent,
    QualityObservation,
)
from ...services import quality_governance_service as qgs
from ...services.quality_governance_adapters import create_manual_issue_with_evidence

router = APIRouter(prefix="/api/v1/quality-issues", tags=["quality-issues"])

# ─────────────────────────────────────────────────────────────────────────
# Schema
# ─────────────────────────────────────────────────────────────────────────


class IssueOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    issue_code: str
    control_id: int | None
    issue_type: str
    title: str
    description: str | None
    primary_system_code: str | None
    related_system_codes: list[str] | None
    object_key: str | None
    object_name_snapshot: str | None
    scope_key: str | None
    severity: str | None
    priority: str | None
    status: str
    responsible_dept_code: str | None
    responsible_person_code: str | None
    assignee_user_identifier: str | None
    responsible_dept_name_snapshot: str | None
    responsible_person_name_snapshot: str | None
    assignee_name_snapshot: str | None
    action_plan: str | None
    due_at: date | None
    wait_kind: str | None
    external_ticket_ref: str | None
    latest_observation_id: int | None
    latest_metric_value: float | None
    latest_result_status: str | None
    opened_control_version: int | None
    first_seen_at: datetime | None
    last_seen_at: datetime | None
    recurrence_of_issue_id: int | None
    recurrence_no: int
    duplicate_of_issue_id: int | None
    resolution_summary: str | None
    resolved_at: datetime | None
    resolved_by: str | None
    risk_reason: str | None
    risk_approver: str | None
    risk_review_at: date | None
    suppressed_until: date | None
    lock_version: int
    allowed_actions: list[str] = []
    overdue: bool = False
    control_code: str | None = None
    control_title: str | None = None


class IssueCreateRequest(BaseModel):
    title: str = Field(..., min_length=2, max_length=256)
    description: str | None = None
    issue_type: str = "manual"
    primary_system_code: str | None = None
    related_system_codes: list[str] | None = None
    object_key: str | None = None
    object_name_snapshot: str | None = None
    control_id: int | None = None
    scope_key: str | None = None
    severity: str = "medium"
    priority: str = "P3"
    responsible_dept_code: str | None = None
    responsible_person_code: str | None = None
    assignee_user_identifier: str | None = None
    responsible_dept_name_snapshot: str | None = None
    responsible_person_name_snapshot: str | None = None
    assignee_name_snapshot: str | None = None
    action_plan: str | None = None
    due_at: date | None = None
    evidence_ref: str | None = None
    reason: str | None = None
    correlation_id: str | None = None


class IssuePatchRequest(BaseModel):
    expected_lock_version: int
    fields: dict[str, Any] = Field(..., min_length=1)
    reason: str | None = None
    correlation_id: str | None = None


class AssignRequest(BaseModel):
    expected_lock_version: int
    responsible_dept_code: str | None = None
    responsible_person_code: str | None = None
    assignee_user_identifier: str | None = None
    responsible_dept_name_snapshot: str | None = None
    responsible_person_name_snapshot: str | None = None
    assignee_name_snapshot: str | None = None
    reason: str | None = None
    correlation_id: str | None = None


class TransitionRequest(BaseModel):
    to_status: str
    expected_lock_version: int
    reason: str = Field(..., min_length=1)
    action_plan: str | None = None
    due_at: date | None = None
    wait_kind: str | None = None
    wait_note: str | None = None
    external_ticket_ref: str | None = None
    duplicate_of_issue_id: int | None = None
    correlation_id: str | None = None


class RequestVerificationRequest(BaseModel):
    expected_lock_version: int
    reason: str = Field(..., min_length=1)
    action_plan: str | None = None
    correlation_id: str | None = None


class VerifyRequest(BaseModel):
    expected_lock_version: int
    passed: bool
    reason: str = Field(..., min_length=1)
    resolution_summary: str | None = None
    verification_observation_id: int | None = None
    correlation_id: str | None = None


class AcceptRiskRequest(BaseModel):
    expected_lock_version: int
    risk_reason: str = Field(..., min_length=1)
    risk_approver: str = Field(..., min_length=1)
    risk_review_at: date
    reason: str | None = None
    correlation_id: str | None = None


class FalsePositiveRequest(BaseModel):
    expected_lock_version: int
    false_positive_reason: str = Field(..., min_length=1)
    suppressed_until: date
    reason: str = Field(..., min_length=1)
    correlation_id: str | None = None


class CommentRequest(BaseModel):
    reason: str = Field(..., min_length=1)
    correlation_id: str | None = None


class ExportFilters(BaseModel):
    scope: str | None = None
    status: str | None = None
    severity: str | None = None
    priority: str | None = None
    primary_system_code: str | None = None
    responsible_dept_code: str | None = None
    overdue: bool | None = None
    keyword: str | None = None


# ─────────────────────────────────────────────────────────────────────────
# 辅助：权限/数据范围/序列化
# ─────────────────────────────────────────────────────────────────────────


def _is_overdue(issue: QualityIssue) -> bool:
    return bool(
        issue.due_at
        and issue.due_at < date.today()
        and issue.status not in qgs.ISSUE_TERMINAL_STATUSES
    )


def _user_permission_map(db: Session, user_identifier: str) -> dict[str, bool]:
    roles = _effective_role_codes(db, user_identifier)
    is_admin = "platform_admin" in roles
    granted: set[str] = set()
    if not is_admin:
        from ...models.governance_base import AssetRolePermission

        rows = (
            db.scalars(
                select(AssetRolePermission).where(AssetRolePermission.role_code.in_(roles))
            ).all()
            if roles
            else []
        )
        for row in rows:
            granted.add(row.resource if row.action in (None, "", "access", "*") else f"{row.resource}:{row.action}")
    return {
        "read_all": is_admin or "quality.issue.read_all" in granted,
        "create": is_admin or "quality.issue.create" in granted,
        "assign": is_admin or "quality.issue.assign" in granted,
        "handle": is_admin or "quality.issue.handle" in granted,
        "verify": is_admin or "quality.issue.verify" in granted,
        "accept_risk": is_admin or "quality.issue.accept_risk" in granted,
        "export": is_admin or "quality.issue.export" in granted,
        "manage": is_admin or "quality.control.manage" in granted,
        "is_admin": is_admin,
    }


def _serialize_issue(db: Session, issue: QualityIssue, user_identifier: str) -> IssueOut:
    out = IssueOut.model_validate(issue)
    out.allowed_actions = qgs.compute_allowed_actions(
        db,
        issue,
        user_identifier=user_identifier,
        has=_user_permission_map(db, user_identifier),
        scope=qgs.resolve_user_scope(db, user_identifier),
    )
    out.overdue = _is_overdue(issue)
    if issue.control_id is not None:
        control = db.get(QualityControl, issue.control_id)
        if control is not None:
            out.control_code = control.control_code
            out.control_title = control.title
    return out


def _resolve_scope_mode(
    requested: str | None, has_read_all: bool, fallback: str = "mine"
) -> str:
    mode = (requested or fallback).lower()
    if mode not in ("mine", "department", "all"):
        raise HTTPException(status_code=422, detail=f"非法 scope: {requested}")
    if mode == "all" and not has_read_all:
        raise HTTPException(status_code=403, detail="缺少权限: quality.issue.read_all")
    return mode


def _apply_filters(
    q,
    *,
    status: str | None,
    severity: str | None,
    priority: str | None,
    primary_system_code: str | None,
    responsible_dept_code: str | None,
    assignee: str | None,
    overdue: bool | None,
    keyword: str | None,
    control_code: str | None,
    issue_type: str | None,
) -> Any:
    if status:
        q = q.where(QualityIssue.status == status)
    if severity:
        q = q.where(QualityIssue.severity == severity)
    if priority:
        q = q.where(QualityIssue.priority == priority)
    if primary_system_code:
        q = q.where(QualityIssue.primary_system_code == primary_system_code)
    if responsible_dept_code:
        q = q.where(QualityIssue.responsible_dept_code == responsible_dept_code)
    if assignee:
        q = q.where(QualityIssue.assignee_user_identifier == assignee)
    if issue_type:
        q = q.where(QualityIssue.issue_type == issue_type)
    if overdue:
        q = q.where(
            QualityIssue.due_at.isnot(None),
            QualityIssue.due_at < date.today(),
            QualityIssue.status.notin_(qgs.ISSUE_TERMINAL_STATUSES),
        )
    if keyword:
        like = f"%{keyword}%"
        q = q.where(or_(QualityIssue.title.ilike(like), QualityIssue.issue_code.ilike(like)))
    if control_code:
        control_ids = select(QualityControl.id).where(QualityControl.control_code == control_code)
        q = q.where(QualityIssue.control_id.in_(control_ids))
    return q


def _get_issue_or_404(db: Session, issue_id: int) -> QualityIssue:
    issue = db.get(QualityIssue, issue_id)
    if issue is None:
        raise HTTPException(status_code=404, detail="issue not found")
    return issue


def _ensure_read_access(
    db: Session, issue: QualityIssue, user_identifier: str, perm: dict[str, bool]
) -> None:
    if perm["read_all"]:
        return
    scope = qgs.resolve_user_scope(db, user_identifier)
    if not qgs.user_can_touch_issue(issue, scope):
        raise HTTPException(status_code=403, detail="无权访问该问题（超出本人/本科室范围）")


def _ensure_write_access(
    db: Session,
    issue: QualityIssue,
    user_identifier: str,
    perm: dict[str, bool],
    *,
    detail: str,
) -> None:
    if perm["read_all"]:
        return
    scope = qgs.resolve_user_scope(db, user_identifier)
    if not qgs.user_can_touch_issue(issue, scope):
        raise HTTPException(status_code=403, detail=detail)


# ─────────────────────────────────────────────────────────────────────────
# 列表 / 汇总 / 详情
# ─────────────────────────────────────────────────────────────────────────


@router.get("")
def list_issues(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    scope: str | None = None,
    status: str | None = None,
    severity: str | None = None,
    priority: str | None = None,
    primary_system_code: str | None = None,
    responsible_dept_code: str | None = None,
    assignee: str | None = None,
    overdue: bool | None = None,
    keyword: str | None = None,
    control_code: str | None = None,
    issue_type: str | None = None,
    db: Session = Depends(get_db),
    user: str = Depends(require_permission("quality.issue.read")),
):
    perm = _user_permission_map(db, user)
    mode = _resolve_scope_mode(scope, perm["read_all"])
    scope_info = qgs.resolve_user_scope(db, user)
    q = select(QualityIssue).where(QualityIssue.archived_at.is_(None))
    q = _apply_filters(
        q,
        status=status,
        severity=severity,
        priority=priority,
        primary_system_code=primary_system_code,
        responsible_dept_code=responsible_dept_code,
        assignee=assignee,
        overdue=overdue,
        keyword=keyword,
        control_code=control_code,
        issue_type=issue_type,
    )
    q = qgs.apply_issue_scope_filter(q, scope_info, mode=mode)
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = db.scalars(
        q.order_by(QualityIssue.status, QualityIssue.priority, QualityIssue.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return {
        "items": [_serialize_issue(db, r, user).model_dump() for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "scope": mode,
    }


@router.get("/summary")
def issue_summary(
    db: Session = Depends(get_db),
    user: str = Depends(require_permission("quality.issue.read")),
):
    perm = _user_permission_map(db, user)
    q = select(
        QualityIssue.primary_system_code,
        QualityIssue.status,
        func.count(QualityIssue.id),
    ).where(QualityIssue.archived_at.is_(None))
    if not perm["read_all"]:
        scope_info = qgs.resolve_user_scope(db, user)
        q = qgs.apply_issue_scope_filter(q, scope_info, mode="department")
    rows = db.execute(q.group_by(QualityIssue.primary_system_code, QualityIssue.status)).all()
    by_system: dict[str, dict[str, int]] = {}
    for system_code, status, cnt in rows:
        key = system_code or "(未指定)"
        by_system.setdefault(key, {})[status] = cnt
    return {"by_system": by_system}


# ─────────────────────────────────────────────────────────────────────────
# 责任选择（最小只读；不返回身份证/电话等敏感字段）
# 166 B7 先例：字面量路由先于 /{issue_id} 注册
# ─────────────────────────────────────────────────────────────────────────


def _ensure_assignment_options_access(db: Session, user: str) -> None:
    perm = _user_permission_map(db, user)
    if perm["is_admin"] or perm["create"] or perm["assign"] or perm["handle"]:
        return
    raise HTTPException(status_code=403, detail="无权查看分派选项（需要登记/分派/处理权限）")


@router.get("/assignment-options/departments")
def assignment_departments(
    keyword: str | None = None,
    db: Session = Depends(get_db),
    user: str = Depends(require_permission("quality.issue.read")),
):
    _ensure_assignment_options_access(db, user)
    q = select(IdentityDepartment).where(IdentityDepartment.status == "active")
    if keyword:
        q = q.where(
            or_(
                IdentityDepartment.dept_code.ilike(f"%{keyword}%"),
                IdentityDepartment.dept_name_cn.ilike(f"%{keyword}%"),
            )
        )
    rows = db.scalars(q.order_by(IdentityDepartment.dept_code).limit(200)).all()
    return {
        "items": [
            {"dept_code": r.dept_code, "dept_name_cn": r.dept_name_cn, "status": r.status}
            for r in rows
        ]
    }


@router.get("/assignment-options/persons")
def assignment_persons(
    department_code: str | None = None,
    keyword: str | None = None,
    db: Session = Depends(get_db),
    user: str = Depends(require_permission("quality.issue.read")),
):
    _ensure_assignment_options_access(db, user)
    q = select(IdentityPerson)
    if department_code:
        q = q.where(IdentityPerson.dept_code == department_code)
    if keyword:
        q = q.where(
            or_(
                IdentityPerson.person_code.ilike(f"%{keyword}%"),
                IdentityPerson.person_name_cn.ilike(f"%{keyword}%"),
            )
        )
    rows = db.scalars(q.order_by(IdentityPerson.person_code).limit(500)).all()
    return {
        "items": [
            {
                "person_code": r.person_code,
                "person_name_cn": r.person_name_cn,
                "dept_code": r.dept_code,
                "dept_name_cn": r.dept_name_cn,
                "employment_status": r.employment_status,
            }
            for r in rows
        ]
    }


@router.post("/export")
def export_issues(
    filters: ExportFilters | None = None,
    db: Session = Depends(get_db),
    user: str = Depends(require_permission("quality.issue.export")),
):
    import csv
    import io as _io

    f = filters or ExportFilters()
    perm = _user_permission_map(db, user)
    mode = _resolve_scope_mode(f.scope, perm["read_all"])
    scope_info = qgs.resolve_user_scope(db, user)
    q = select(QualityIssue).where(QualityIssue.archived_at.is_(None))
    q = _apply_filters(
        q,
        status=f.status,
        severity=f.severity,
        priority=f.priority,
        primary_system_code=f.primary_system_code,
        responsible_dept_code=f.responsible_dept_code,
        assignee=None,
        overdue=f.overdue,
        keyword=f.keyword,
        control_code=None,
        issue_type=None,
    )
    q = qgs.apply_issue_scope_filter(q, scope_info, mode=mode)
    rows = db.scalars(
        q.order_by(QualityIssue.status, QualityIssue.priority, QualityIssue.id.desc()).limit(
            ISSUE_EXPORT_LIMIT + 1
        )
    ).all()
    if len(rows) > ISSUE_EXPORT_LIMIT:
        raise HTTPException(
            status_code=422,
            detail=f"导出超过 {ISSUE_EXPORT_LIMIT} 行上限，请缩小筛选范围",
        )

    controls = {
        c.id: c
        for c in db.scalars(
            select(QualityControl).where(
                QualityControl.id.in_([r.control_id for r in rows if r.control_id])
            )
        ).all()
    }

    buffer = _io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(ISSUE_EXPORT_COLUMNS)
    for r in rows:
        control = controls.get(r.control_id) if r.control_id else None
        writer.writerow(
            [
                _csv_cell(r.issue_code),
                _csv_cell(r.title),
                _csv_cell(r.issue_type),
                _csv_cell(r.status),
                _csv_cell(control.control_code if control else None),
                _csv_cell(control.title if control else None),
                _csv_cell(r.opened_control_version),
                _csv_cell(r.primary_system_code),
                _csv_cell(r.object_name_snapshot),
                _csv_cell(r.scope_key),
                _csv_cell(r.severity),
                _csv_cell(r.priority),
                _csv_cell(r.responsible_dept_code),
                _csv_cell(r.responsible_dept_name_snapshot),
                _csv_cell(r.responsible_person_code),
                _csv_cell(r.responsible_person_name_snapshot),
                _csv_cell(r.assignee_user_identifier),
                _csv_cell(r.assignee_name_snapshot),
                _csv_cell(r.latest_metric_value),
                _csv_cell(r.latest_result_status),
                _csv_cell(r.action_plan),
                _csv_cell(r.due_at),
                _csv_cell("是" if _is_overdue(r) else "否"),
                _csv_cell(r.wait_kind),
                _csv_cell(r.external_ticket_ref),
                _csv_cell(r.recurrence_no),
                _csv_cell(r.recurrence_of_issue_id),
                _csv_cell(r.first_seen_at),
                _csv_cell(r.last_seen_at),
                _csv_cell(r.resolution_summary),
                _csv_cell(r.risk_reason),
                _csv_cell(r.risk_approver),
                _csv_cell(r.risk_review_at),
                _csv_cell(r.suppressed_until),
            ]
        )

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    filename = (
        f"quality-issues-{stamp}"
        f"{_filename_tag('status', f.status)}{_filename_tag('sys', f.primary_system_code)}"
        f"{_filename_tag('sev', f.severity)}.csv"
    )
    db.add(
        GovernAuditLog(
            module="quality_governance",
            entity_type="quality_issue",
            entity_ref="export",
            action="export",
            after_data={"filters": f.model_dump(exclude_none=True), "rows": len(rows), "filename": filename},
            operator=user,
        )
    )
    db.commit()
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/{issue_id}")
def get_issue(
    issue_id: int,
    db: Session = Depends(get_db),
    user: str = Depends(require_permission("quality.issue.read")),
):
    issue = _get_issue_or_404(db, issue_id)
    perm = _user_permission_map(db, user)
    _ensure_read_access(db, issue, user, perm)
    return _serialize_issue(db, issue, user).model_dump()


@router.get("/{issue_id}/events")
def list_issue_events(
    issue_id: int,
    db: Session = Depends(get_db),
    user: str = Depends(require_permission("quality.issue.read")),
):
    issue = _get_issue_or_404(db, issue_id)
    perm = _user_permission_map(db, user)
    _ensure_read_access(db, issue, user, perm)
    rows = db.scalars(
        select(QualityIssueEvent)
        .where(QualityIssueEvent.issue_id == issue_id)
        .order_by(QualityIssueEvent.id.asc())
    ).all()
    return {
        "items": [
            {
                "id": ev.id,
                "event_type": ev.event_type,
                "from_status": ev.from_status,
                "to_status": ev.to_status,
                "before_json": ev.before_json,
                "after_json": ev.after_json,
                "reason": ev.reason,
                "observation_id": ev.observation_id,
                "actor_user_identifier": ev.actor_user_identifier,
                "occurred_at": ev.occurred_at.isoformat() if ev.occurred_at else None,
                "correlation_id": ev.correlation_id,
            }
            for ev in rows
        ],
        "total": len(rows),
    }


@router.get("/{issue_id}/observations")
def list_issue_observations(
    issue_id: int,
    db: Session = Depends(get_db),
    user: str = Depends(require_permission("quality.issue.read")),
):
    issue = _get_issue_or_404(db, issue_id)
    perm = _user_permission_map(db, user)
    _ensure_read_access(db, issue, user, perm)
    rows = db.scalars(
        select(QualityObservation)
        .where(QualityObservation.issue_id == issue_id)
        .order_by(QualityObservation.id.asc())
    ).all()
    return {
        "items": [
            {
                "id": obs.id,
                "control_id": obs.control_id,
                "control_version": obs.control_version,
                "run_key": obs.run_key,
                "scope_key": obs.scope_key,
                "window_start": obs.window_start,
                "window_end": obs.window_end,
                "observed_at": obs.observed_at.isoformat() if obs.observed_at else None,
                "result_status": obs.result_status,
                "metric_value": float(obs.metric_value) if obs.metric_value is not None else None,
                "metric_unit": obs.metric_unit,
                "threshold_snapshot": obs.threshold_snapshot,
                "source_kind": obs.source_kind,
                "source_record_ref": obs.source_record_ref,
                "evidence_digest": obs.evidence_digest,
                "evidence_ref": obs.evidence_ref,
                "historical_precision": obs.historical_precision,
                "error_code": obs.error_code,
            }
            for obs in rows
        ],
        "total": len(rows),
    }


# ─────────────────────────────────────────────────────────────────────────
# 命令端点（专用命令；通用 PATCH 不能绕过状态机）
# ─────────────────────────────────────────────────────────────────────────


def _command_response(db: Session, issue: QualityIssue, user: str) -> dict[str, Any]:
    return _serialize_issue(db, issue, user).model_dump()


@router.post("")
def create_issue(
    req: IssueCreateRequest,
    db: Session = Depends(get_db),
    user: str = Depends(require_permission("quality.issue.create")),
):
    result = create_manual_issue_with_evidence(
        db,
        title=req.title,
        evidence_ref=req.evidence_ref,
        control_id=req.control_id,
        actor=user,
        reason=req.reason,
        issue_kwargs={
            "description": req.description,
            "issue_type": req.issue_type,
            "primary_system_code": req.primary_system_code,
            "related_system_codes": req.related_system_codes,
            "object_key": req.object_key,
            "object_name_snapshot": req.object_name_snapshot,
            "scope_key": req.scope_key,
            "severity": req.severity,
            "priority": req.priority,
            "responsible_dept_code": req.responsible_dept_code,
            "responsible_person_code": req.responsible_person_code,
            "assignee_user_identifier": req.assignee_user_identifier,
            "responsible_dept_name_snapshot": req.responsible_dept_name_snapshot,
            "responsible_person_name_snapshot": req.responsible_person_name_snapshot,
            "assignee_name_snapshot": req.assignee_name_snapshot,
            "action_plan": req.action_plan,
            "due_at": req.due_at,
        },
    )
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        if "uq_asset_quality_issues_active" in str(exc):
            raise HTTPException(
                status_code=409, detail="该清单+范围已有活动问题，不能重复建单"
            ) from exc
        raise
    db.refresh(result["issue"])
    return _command_response(db, result["issue"], user)


@router.patch("/{issue_id}")
def patch_issue(
    issue_id: int,
    req: IssuePatchRequest,
    db: Session = Depends(get_db),
    user: str = Depends(require_permission("quality.issue.handle")),
):
    issue = _get_issue_or_404(db, issue_id)
    perm = _user_permission_map(db, user)
    _ensure_write_access(db, issue, user, perm, detail="无权处理该问题（超出本人/本科室范围）")
    try:
        qgs.patch_issue(
            db, issue, expected_lock_version=req.expected_lock_version, actor=user,
            fields=req.fields, correlation_id=req.correlation_id,
        )
        db.commit()
    except qgs.LockConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except qgs.IssueValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.refresh(issue)
    return _command_response(db, issue, user)


@router.post("/{issue_id}/assign")
def assign_issue(
    issue_id: int,
    req: AssignRequest,
    db: Session = Depends(get_db),
    user: str = Depends(require_permission("quality.issue.assign")),
):
    issue = _get_issue_or_404(db, issue_id)
    perm = _user_permission_map(db, user)
    _ensure_write_access(db, issue, user, perm, detail="无权分派该问题（超出本人/本科室范围）")
    try:
        qgs.assign_issue(
            db,
            issue,
            expected_lock_version=req.expected_lock_version,
            responsible_dept_code=req.responsible_dept_code,
            responsible_person_code=req.responsible_person_code,
            assignee_user_identifier=req.assignee_user_identifier,
            responsible_dept_name_snapshot=req.responsible_dept_name_snapshot,
            responsible_person_name_snapshot=req.responsible_person_name_snapshot,
            assignee_name_snapshot=req.assignee_name_snapshot,
            actor=user,
            reason=req.reason,
            correlation_id=req.correlation_id,
        )
        db.commit()
    except qgs.LockConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (qgs.TransitionError,) as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except qgs.IssueValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.refresh(issue)
    return _command_response(db, issue, user)


@router.post("/{issue_id}/transition")
def transition_issue(
    issue_id: int,
    req: TransitionRequest,
    db: Session = Depends(get_db),
    user: str = Depends(require_permission("quality.issue.handle")),
):
    issue = _get_issue_or_404(db, issue_id)
    perm = _user_permission_map(db, user)
    _ensure_write_access(db, issue, user, perm, detail="无权处理该问题（超出本人/本科室范围）")
    # 终态重开仅复发/管理员；accepted_risk/false_positive 重开需复审到期或抑制到期
    reopen_as_recurrence = False
    if issue.status in qgs.ISSUE_TERMINAL_STATUSES:
        if not perm["is_admin"]:
            raise HTTPException(status_code=403, detail="终态重开仅限管理员")
        reopen_as_recurrence = True
    try:
        qgs.transition_issue(
            db,
            issue,
            to_status=req.to_status,
            expected_lock_version=req.expected_lock_version,
            actor=user,
            reason=req.reason,
            action_plan=req.action_plan,
            due_at=req.due_at,
            wait_kind=req.wait_kind,
            wait_note=req.wait_note,
            external_ticket_ref=req.external_ticket_ref,
            duplicate_of_issue_id=req.duplicate_of_issue_id,
            reopen_as_recurrence=reopen_as_recurrence,
            correlation_id=req.correlation_id,
        )
        db.commit()
    except qgs.LockConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except qgs.TransitionError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except qgs.IssueValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.refresh(issue)
    return _command_response(db, issue, user)


@router.post("/{issue_id}/request-verification")
def request_verification(
    issue_id: int,
    req: RequestVerificationRequest,
    db: Session = Depends(get_db),
    user: str = Depends(require_permission("quality.issue.handle")),
):
    issue = _get_issue_or_404(db, issue_id)
    perm = _user_permission_map(db, user)
    _ensure_write_access(db, issue, user, perm, detail="无权处理该问题（超出本人/本科室范围）")
    try:
        qgs.request_verification(
            db,
            issue,
            expected_lock_version=req.expected_lock_version,
            actor=user,
            reason=req.reason,
            action_plan=req.action_plan,
            correlation_id=req.correlation_id,
        )
        db.commit()
    except qgs.LockConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except qgs.TransitionError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except qgs.IssueValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.refresh(issue)
    return _command_response(db, issue, user)


@router.post("/{issue_id}/verify")
def verify_issue(
    issue_id: int,
    req: VerifyRequest,
    db: Session = Depends(get_db),
    user: str = Depends(require_permission("quality.issue.verify")),
):
    issue = _get_issue_or_404(db, issue_id)
    perm = _user_permission_map(db, user)
    _ensure_write_access(db, issue, user, perm, detail="无权验证该问题（超出本人/本科室范围）")
    requester = qgs.last_verification_requester(db, issue.id)
    if requester == user and not perm["is_admin"]:
        raise HTTPException(
            status_code=403,
            detail="复测验证不能由最后提交待复测的同一经办人完成（管理员豁免除外）",
        )
    try:
        qgs.verify_issue(
            db,
            issue,
            expected_lock_version=req.expected_lock_version,
            passed=req.passed,
            actor=user,
            reason=req.reason,
            resolution_summary=req.resolution_summary,
            verification_observation_id=req.verification_observation_id,
            correlation_id=req.correlation_id,
        )
        db.commit()
    except qgs.LockConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except qgs.TransitionError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except qgs.IssueValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.refresh(issue)
    return _command_response(db, issue, user)


@router.post("/{issue_id}/accept-risk")
def accept_risk(
    issue_id: int,
    req: AcceptRiskRequest,
    db: Session = Depends(get_db),
    user: str = Depends(require_permission("quality.issue.accept_risk")),
):
    issue = _get_issue_or_404(db, issue_id)
    perm = _user_permission_map(db, user)
    _ensure_write_access(db, issue, user, perm, detail="无权接受该问题风险（超出本人/本科室范围）")
    try:
        qgs.transition_issue(
            db,
            issue,
            to_status="accepted_risk",
            expected_lock_version=req.expected_lock_version,
            actor=user,
            reason=req.reason or req.risk_reason,
            risk_reason=req.risk_reason,
            risk_approver=req.risk_approver,
            risk_review_at=req.risk_review_at,
            correlation_id=req.correlation_id,
        )
        db.commit()
    except qgs.LockConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except qgs.TransitionError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except qgs.IssueValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.refresh(issue)
    return _command_response(db, issue, user)


@router.post("/{issue_id}/mark-false-positive")
def mark_false_positive(
    issue_id: int,
    req: FalsePositiveRequest,
    db: Session = Depends(get_db),
    user: str = Depends(require_permission("quality.issue.handle")),
):
    issue = _get_issue_or_404(db, issue_id)
    perm = _user_permission_map(db, user)
    _ensure_write_access(db, issue, user, perm, detail="无权处理该问题（超出本人/本科室范围）")
    if issue.status != "new":
        raise HTTPException(
            status_code=409, detail=f"误报判定仅允许 new 状态（当前 {issue.status}）"
        )
    try:
        qgs.mark_false_positive(
            db,
            issue,
            expected_lock_version=req.expected_lock_version,
            false_positive_reason=req.false_positive_reason,
            suppressed_until=req.suppressed_until,
            actor=user,
            reason=req.reason,
            correlation_id=req.correlation_id,
        )
        db.commit()
    except qgs.LockConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except qgs.TransitionError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except qgs.IssueValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.refresh(issue)
    return _command_response(db, issue, user)


@router.post("/{issue_id}/comment")
def add_comment(
    issue_id: int,
    req: CommentRequest,
    db: Session = Depends(get_db),
    user: str = Depends(require_permission("quality.issue.handle")),
):
    issue = _get_issue_or_404(db, issue_id)
    perm = _user_permission_map(db, user)
    _ensure_write_access(db, issue, user, perm, detail="无权处理该问题（超出本人/本科室范围）")
    qgs.add_comment(db, issue, actor=user, reason=req.reason, correlation_id=req.correlation_id)
    db.commit()
    return {"ok": True}


# ─────────────────────────────────────────────────────────────────────────
# 受控导出（六硬约束；字面量路由先于 /{issue_id} 注册）
# ─────────────────────────────────────────────────────────────────────────

ISSUE_EXPORT_COLUMNS = (
    "issue_code", "title", "issue_type", "status",
    "control_code", "control_title", "opened_control_version",
    "primary_system_code", "object_name_snapshot", "scope_key",
    "severity", "priority",
    "responsible_dept_code", "responsible_dept_name_snapshot",
    "responsible_person_code", "responsible_person_name_snapshot",
    "assignee_user_identifier", "assignee_name_snapshot",
    "latest_metric_value", "latest_result_status", "action_plan", "due_at", "overdue",
    "wait_kind", "external_ticket_ref",
    "recurrence_no", "recurrence_of_issue_id",
    "first_seen_at", "last_seen_at",
    "resolution_summary", "risk_reason", "risk_approver", "risk_review_at",
    "suppressed_until",
)
ISSUE_EXPORT_LIMIT = 5000


def _csv_cell(value: object) -> str:
    if value is None:
        return ""
    text = str(value).replace("\r", " ").replace("\n", " ")
    if text[:1] in ("=", "+", "-", "@"):
        return f"'{text}"
    return text


def _filename_tag(label: str, value: str | None) -> str:
    if not value:
        return ""
    import re

    safe = re.sub(r"[^A-Za-z0-9_-]", "", value)[:32]
    return f"-{label}-{safe}" if safe else ""

