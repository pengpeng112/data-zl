"""126 P2: metric asset API."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ...core.db import get_db
from ...core.security import get_current_user, require_permission
from ...models.metric_asset import AssetMetricDefinition, AssetMetricResult, AssetMetricVersion
from ...schemas.common import ApiResponse
from ...services.metric_service import (
    _ser_def,
    _ser_ver,
    get_active_metric_version,
    get_metric,
    ingest_metric,
    register_metric_result,
)

router = APIRouter(prefix="/api/v1/metrics", tags=["metrics"])


class MetricIngestRequest(BaseModel):
    metric_code: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    meaning: str | None = None
    category: str | None = None
    unit: str | None = None
    frequency: str | None = None
    grain: str | None = None
    owner_dept: str | None = None
    definition_text: str | None = None
    numerator_desc: str | None = None
    denominator_desc: str | None = None
    formula: str | None = None
    query_code: str | None = None
    query_version: int | None = None
    numerator_query_code: str | None = None
    numerator_query_version: int | None = None
    denominator_query_code: str | None = None
    denominator_query_version: int | None = None
    period_field: str | None = None
    include_rules: str | None = None
    exclude_rules: str | None = None
    dedup_rules: str | None = None
    limitations: list | None = None
    system_code: str | None = None
    source_code: str | None = None
    revision_reason: str | None = None
    force_new_version: bool = False
    auto_activate: bool = True


class MetricResultRequest(BaseModel):
    metric_code: str
    period_key: str
    version: int | None = None
    numerator_value: str | None = None
    denominator_value: str | None = None
    metric_value: str | None = None
    status: str = "ok"
    limitations_note: str | None = None
    dimensions: dict | None = None
    query_run_id: int | None = None


@router.get("", summary="指标主档列表")
def list_metrics(
    keyword: str | None = Query(None),
    category: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=200),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    stmt = select(AssetMetricDefinition)
    if category:
        stmt = stmt.where(AssetMetricDefinition.category == category)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(
            or_(
                AssetMetricDefinition.metric_code.ilike(like),
                AssetMetricDefinition.title.ilike(like),
                AssetMetricDefinition.meaning.ilike(like),
            )
        )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(AssetMetricDefinition.metric_code)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    items = []
    for d in rows:
        item = _ser_def(d)
        active = get_active_metric_version(db, d.metric_code)
        item["active_version"] = _ser_ver(active) if active else None
        items.append(item)
    return ApiResponse(data={"total": total, "page": page, "page_size": page_size, "items": items})


@router.get("/ai/context", summary="AI 可读现行指标上下文")
def ai_metric_context(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> ApiResponse[list[dict]]:
    rows = db.scalars(
        select(AssetMetricVersion)
        .where(AssetMetricVersion.is_active.is_(True), AssetMetricVersion.status == "active")
        .order_by(AssetMetricVersion.metric_code)
        .limit(limit)
    ).all()
    out = []
    for v in rows:
        d = get_metric(db, v.metric_code)
        out.append(
            {
                "metric_code": v.metric_code,
                "title": d.title if d else v.metric_code,
                "meaning": d.meaning if d else None,
                "version": v.version,
                "formula": v.formula,
                "numerator_desc": v.numerator_desc,
                "denominator_desc": v.denominator_desc,
                "query_code": v.query_code,
                "query_version": v.query_version,
                "numerator_query_code": v.numerator_query_code,
                "denominator_query_code": v.denominator_query_code,
                "limitations": v.limitations,
                "definition_text": v.definition_text,
            }
        )
    return ApiResponse(data=out)


@router.get("/board/overview", summary="126 P5：指标结果看板（按月份透视最新批次）")
def board_overview(
    category: str | None = Query("48项核心制度"),
    period_from: str | None = Query(None, description="起始月份 YYYY-MM"),
    period_to: str | None = Query(None, description="结束月份 YYYY-MM"),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    """Return latest result per metric_code + period_key for board UI/export."""
    defs = db.scalars(select(AssetMetricDefinition).order_by(AssetMetricDefinition.metric_code)).all()
    if category:
        defs = [d for d in defs if (d.category or "") == category or category in (d.category or "")]
    codes = [d.metric_code for d in defs]
    if not codes:
        return ApiResponse(data={"periods": [], "metrics": [], "cells": {}, "total_results": 0})

    stmt = select(AssetMetricResult).where(AssetMetricResult.metric_code.in_(codes))
    if period_from:
        stmt = stmt.where(AssetMetricResult.period_key >= period_from)
    if period_to:
        stmt = stmt.where(AssetMetricResult.period_key <= period_to)
    rows = db.scalars(stmt.order_by(AssetMetricResult.id.desc())).all()

    cells: dict[str, dict[str, dict]] = {}
    periods: set[str] = set()
    for r in rows:
        m = cells.setdefault(r.metric_code, {})
        if r.period_key in m:
            continue
        periods.add(r.period_key)
        m[r.period_key] = {
            "metric_value": r.metric_value,
            "numerator_value": r.numerator_value,
            "denominator_value": r.denominator_value,
            "status": r.status,
            "limitations_note": r.limitations_note,
            "is_recalc": r.is_recalc,
            "run_batch": r.run_batch,
        }

    period_list = sorted(periods)
    metrics = []
    for d in defs:
        active = get_active_metric_version(db, d.metric_code)
        metrics.append(
            {
                "metric_code": d.metric_code,
                "title": d.title,
                "unit": d.unit,
                "status": d.status,
                "has_active": bool(active and active.is_active),
                "query_code": active.query_code if active else None,
                "period_count": len(cells.get(d.metric_code) or {}),
            }
        )
    return ApiResponse(
        data={
            "periods": period_list,
            "metrics": metrics,
            "cells": cells,
            "total_results": sum(len(v) for v in cells.values()),
            "category": category,
        }
    )


@router.get("/{metric_code}", summary="指标详情与版本")
def get_metric_detail(metric_code: str, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    d = get_metric(db, metric_code)
    if not d:
        raise HTTPException(status_code=404, detail="指标不存在")
    versions = db.scalars(
        select(AssetMetricVersion)
        .where(AssetMetricVersion.metric_code == metric_code)
        .order_by(AssetMetricVersion.version.desc())
    ).all()
    active = get_active_metric_version(db, metric_code)
    return ApiResponse(
        data={
            "definition": _ser_def(d),
            "active_version": _ser_ver(active) if active else None,
            "versions": [_ser_ver(v) for v in versions],
        }
    )


@router.post(
    "/ingest",
    summary="摄取/修订指标（门禁通过可自动 active）",
    dependencies=[Depends(require_permission("query:create"))],
)
def ingest(req: MetricIngestRequest, request: Request, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    user = "system"
    try:
        user = get_current_user(request) or user
    except Exception:
        pass
    try:
        result = ingest_metric(db, created_by=user, **req.model_dump())
        db.commit()
        return ApiResponse(data=result)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/results",
    summary="登记可选周期结果（不覆盖历史批次）",
    dependencies=[Depends(require_permission("query:create"))],
)
def post_result(req: MetricResultRequest, request: Request, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    user = "system"
    try:
        user = get_current_user(request) or user
    except Exception:
        pass
    try:
        result = register_metric_result(db, created_by=user, **req.model_dump())
        db.commit()
        return ApiResponse(data=result)
    except LookupError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{metric_code}/results", summary="指标周期结果列表")
def list_results(
    metric_code: str,
    period_key: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    stmt = select(AssetMetricResult).where(AssetMetricResult.metric_code == metric_code)
    if period_key:
        stmt = stmt.where(AssetMetricResult.period_key == period_key)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(AssetMetricResult.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    items = [
        {
            "id": r.id,
            "version": r.version,
            "period_key": r.period_key,
            "numerator_value": r.numerator_value,
            "denominator_value": r.denominator_value,
            "metric_value": r.metric_value,
            "status": r.status,
            "limitations_note": r.limitations_note,
            "run_batch": r.run_batch,
            "is_recalc": r.is_recalc,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
    return ApiResponse(data={"total": total, "page": page, "page_size": page_size, "items": items})
