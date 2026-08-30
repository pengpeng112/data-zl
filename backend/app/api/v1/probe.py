"""165 E4: 探查只读 API（四端点 + /probe-findings/export 405 占位）。

B7 裁决：/export 占位先于 /{id} 注册（166 D4 替换为真实现——六硬约束新做）。
权限：probe.finding.read。分页沿用仓内 {items,total,page,page_size}。
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...core.db import get_db
from ...core.security import require_permission
from ...models.probe import AssetProbeFinding, AssetProbeRun

router = APIRouter(tags=["probe"])


class FindingOut(BaseModel):
    id: int
    probe_type: str
    system_pair: str
    object_desc: str
    metric_name: str
    metric_value: float | None
    metric_unit: str | None
    threshold: float | None
    window_start: date | None
    window_end: date | None
    severity: str | None
    status: str
    first_seen_run: str | None
    last_seen_run: str | None
    relapse_count: int
    note: str | None

    class Config:
        from_attributes = True


class RunOut(BaseModel):
    id: int
    run_id: str
    started_at: object | None
    finished_at: object | None
    status: str
    probe_count: int
    finding_new: int
    finding_updated: int
    relapse_count: int
    error_summary: str | None
    created_by: str | None

    class Config:
        from_attributes = True


@router.get("/api/v1/probe-runs")
def list_runs(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    status: str | None = None,
    db: Session = Depends(get_db), _user: str = Depends(require_permission("probe.finding.read")),
):
    q = select(AssetProbeRun)
    if status:
        q = q.where(AssetProbeRun.status == status)
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = db.scalars(q.order_by(AssetProbeRun.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [RunOut.model_validate(r).model_dump() for r in rows], "total": total,
            "page": page, "page_size": page_size}


@router.get("/api/v1/probe-runs/{run_id}")
def get_run(
    run_id: str,
    db: Session = Depends(get_db), _user: str = Depends(require_permission("probe.finding.read")),
):
    row = db.scalar(select(AssetProbeRun).where(AssetProbeRun.run_id == run_id))
    if row is None:
        raise HTTPException(status_code=404, detail="run not found")
    out = RunOut.model_validate(row).model_dump()
    out["metrics_summary"] = row.metrics_summary
    out["created_at"] = row.created_at.isoformat() if row.created_at else None
    return out


@router.get("/api/v1/probe-findings")
def list_findings(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    probe_type: str | None = None, system_pair: str | None = None,
    severity: str | None = None, status: str | None = None, source: str | None = None,
    window_start_from: date | None = None, window_start_to: date | None = None,
    db: Session = Depends(get_db), _user: str = Depends(require_permission("probe.finding.read")),
):
    q = select(AssetProbeFinding)
    if probe_type:
        q = q.where(AssetProbeFinding.probe_type == probe_type)
    if system_pair:
        q = q.where(AssetProbeFinding.system_pair == system_pair)
    if severity:
        q = q.where(AssetProbeFinding.severity == severity)
    if status:
        q = q.where(AssetProbeFinding.status == status)
    if source:
        q = q.where(AssetProbeFinding.object_desc.ilike(f"%{source}%"))
    if window_start_from:
        q = q.where(AssetProbeFinding.window_start >= window_start_from)
    if window_start_to:
        q = q.where(AssetProbeFinding.window_start <= window_start_to)
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = db.scalars(q.order_by(AssetProbeFinding.severity, AssetProbeFinding.id.desc())
                      .offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [FindingOut.model_validate(r).model_dump() for r in rows], "total": total,
            "page": page, "page_size": page_size}


# B7：/export 先于 /{finding_id} 注册；166 D4 以真实现替换 165 的 405 占位。
# 导出六硬约束（B1/B12，禁止照抄 governance.py 旧实现）：
#   ①require_permission 显式挂载（GET 不在写路由扫描内，须显式 403 测试）
#   ②审计行（操作人/筛选/行数） ③文件名含导出时间+筛选标签
#   ④防公式注入（=+-@ 前缀加 ' 转义） ⑤列白名单逐列常量（不含 evidence_sql）
#   ⑥POST+body 筛选（防 SQL 文本进代理日志）
FINDING_EXPORT_COLUMNS = (
    "id", "probe_type", "system_pair", "object_desc",
    "window_start", "window_end", "metric_name", "metric_value", "metric_unit",
    "threshold", "severity", "status", "first_seen_run", "last_seen_run",
    "relapse_count", "resolved_by", "resolved_at", "note", "evidence_digest",
)
FINDING_EXPORT_LIMIT = 5000


class FindingExportFilters(BaseModel):
    """POST body 筛选（与 GET /probe-findings 同口径；SQL 不进 URL/代理日志）。"""

    probe_type: str | None = None
    system_pair: str | None = None
    severity: str | None = None
    status: str | None = None
    source: str | None = None
    window_start_from: date | None = None
    window_start_to: date | None = None


def _csv_cell(value: object) -> str:
    """CSV 单元格：防公式注入（=+-@ 前缀加 ' 转义），换行折叠。"""
    if value is None:
        return ""
    text = str(value).replace("\r", " ").replace("\n", " ")
    if text[:1] in ("=", "+", "-", "@"):
        return f"'{text}"
    return text


def _filename_tag(label: str, value: str | None) -> str:
    """文件名筛选标签（如 -status-open）：仅保留安全字符（防 Content-Disposition/路径注入）。"""
    if not value:
        return ""
    import re

    safe = re.sub(r"[^A-Za-z0-9_-]", "", value)[:32]
    return f"-{label}-{safe}" if safe else ""


@router.post("/api/v1/probe-findings/export")
def export_findings(
    filters: FindingExportFilters | None = None,
    db: Session = Depends(get_db),
    operator: str = Depends(require_permission("probe.finding.read")),
):
    import csv
    import io as _io
    from datetime import datetime, timezone as _tz

    from fastapi.responses import StreamingResponse

    from ...models.governance_base import GovernAuditLog

    f = filters or FindingExportFilters()
    q = select(AssetProbeFinding)
    if f.probe_type:
        q = q.where(AssetProbeFinding.probe_type == f.probe_type)
    if f.system_pair:
        q = q.where(AssetProbeFinding.system_pair == f.system_pair)
    if f.severity:
        q = q.where(AssetProbeFinding.severity == f.severity)
    if f.status:
        q = q.where(AssetProbeFinding.status == f.status)
    if f.source:
        q = q.where(AssetProbeFinding.object_desc.ilike(f"%{f.source}%"))
    if f.window_start_from:
        q = q.where(AssetProbeFinding.window_start >= f.window_start_from)
    if f.window_start_to:
        q = q.where(AssetProbeFinding.window_start <= f.window_start_to)
    rows = db.scalars(
        q.order_by(AssetProbeFinding.severity, AssetProbeFinding.id.desc()).limit(FINDING_EXPORT_LIMIT)
    ).all()

    buffer = _io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(FINDING_EXPORT_COLUMNS)  # ⑤列白名单逐列（无 evidence_sql）
    for r in rows:
        writer.writerow([
            _csv_cell(r.id), _csv_cell(r.probe_type), _csv_cell(r.system_pair),
            _csv_cell(r.object_desc), _csv_cell(r.window_start), _csv_cell(r.window_end),
            _csv_cell(r.metric_name), _csv_cell(r.metric_value), _csv_cell(r.metric_unit),
            _csv_cell(r.threshold), _csv_cell(r.severity), _csv_cell(r.status),
            _csv_cell(r.first_seen_run), _csv_cell(r.last_seen_run),
            _csv_cell(r.relapse_count), _csv_cell(r.resolved_by), _csv_cell(r.resolved_at),
            _csv_cell(r.note), _csv_cell(r.evidence_digest),
        ])

    stamp = datetime.now(_tz.utc).strftime("%Y%m%d-%H%M%S")
    filename = (
        f"probe-findings-{stamp}"
        f"{_filename_tag('status', f.status)}{_filename_tag('type', f.probe_type)}"
        f"{_filename_tag('sev', f.severity)}.csv"
    )
    filter_payload = f.model_dump(exclude_none=True)
    db.add(
        GovernAuditLog(
            module="probe",
            entity_type="probe_finding",
            entity_ref="export",
            action="export",
            after_data={"filters": filter_payload, "rows": len(rows), "filename": filename},
            operator=operator,
        )
    )
    db.commit()
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/api/v1/probe-findings/{finding_id}")
def get_finding(
    finding_id: int,
    db: Session = Depends(get_db), _user: str = Depends(require_permission("probe.finding.read")),
):
    row = db.get(AssetProbeFinding, finding_id)
    if row is None:
        raise HTTPException(status_code=404, detail="finding not found")
    out = FindingOut.model_validate(row).model_dump()
    out["evidence_sql"] = row.evidence_sql
    out["evidence_digest"] = row.evidence_digest
    out["resolved_by"] = row.resolved_by
    out["resolved_at"] = row.resolved_at.isoformat() if row.resolved_at else None
    out["created_at"] = row.created_at.isoformat() if row.created_at else None
    out["updated_at"] = row.updated_at.isoformat() if row.updated_at else None
    return out


# ─────────────────────────────────────────────────────────────────────────
# 166 F5：人工终态流转（165 模块内只增；B8 裁决）
# ─────────────────────────────────────────────────────────────────────────

from pydantic import Field

from ...models.governance_base import GovernAuditLog
from ...services.probe_service import FindingTransitionError, transition_finding

# action → to_status；reclassify 必须带 to_status（改判到人工三值之一）
_TRANSITION_ACTIONS = {
    "confirm": "confirmed",
    "false_positive": "false_positive",
    "resolve": "resolved",
    "reopen": "open",
}


class TransitionRequest(BaseModel):
    action: str = Field(..., description="confirm/false_positive/resolve/reopen/reclassify")
    to_status: str | None = Field(None, description="reclassify 必填：confirmed/false_positive/resolved")
    reason: str = Field(..., min_length=1, description="流转理由（必填，入审计）")


@router.post("/api/v1/probe-findings/{finding_id}/transition")
def transition_finding_endpoint(
    finding_id: int,
    req: TransitionRequest,
    db: Session = Depends(get_db),
    operator: str = Depends(require_permission("probe.finding.manage")),
):
    """人工终态流转（B6 迁移表：四值互转+重开全允许，同态原地转 422）。

    执行器身份（operator 前缀 "probe:"）禁止调用——403；
    审计行落 GovernAuditLog（module=probe, action=transition，含 before/after/reason）。
    """
    if operator.startswith("probe:"):
        raise HTTPException(status_code=403, detail="执行器身份禁止人工终态流转")

    if req.action == "reclassify":
        to_status = req.to_status or ""
    else:
        to_status = _TRANSITION_ACTIONS.get(req.action, "")
    if not to_status:
        raise HTTPException(status_code=422, detail=f"action 非法或缺 to_status: {req.action}")

    before = db.get(AssetProbeFinding, finding_id)
    if before is None:
        raise HTTPException(status_code=404, detail="finding not found")
    before_status = before.status

    try:
        row = transition_finding(
            db, finding_id=finding_id, to_status=to_status, reason=req.reason, operator=operator
        )
    except FindingTransitionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    db.add(
        GovernAuditLog(
            module="probe",
            entity_type="probe_finding",
            entity_ref=str(finding_id),
            action="transition",
            before_data={"status": before_status},
            after_data={"status": row.status, "resolved_by": row.resolved_by},
            operator=operator,
            reason=req.reason,
        )
    )
    db.commit()
    db.refresh(row)
    out = FindingOut.model_validate(row).model_dump()
    out["resolved_by"] = row.resolved_by
    out["resolved_at"] = row.resolved_at.isoformat() if row.resolved_at else None
    return out
