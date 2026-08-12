"""126 P1: query asset list / versions / runs / context."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ...core.db import get_db
from ...core.security import get_current_user, require_permission
from ...models.query_asset import (
    AssetQueryDefinition,
    AssetQueryDependency,
    AssetQueryResult,
    AssetQueryRun,
    AssetQueryVersion,
)
from ...schemas.common import ApiResponse
from ...schemas.query_asset import QueryGateRequest, QueryIngestRequest, QueryReviseRequest, QueryRunRequest
from ...models.query_schedule import AssetQuerySchedule
from ...services.core_metric_import import import_core_metrics
from ...services.query_gate import evaluate_query_gate
from ...services.query_impact import impact_for_table
from ...services.query_intake import get_active_version, get_definition, ingest_query, revise_query
from ...services.query_intake import _serialize_def, _serialize_ver
from ...services.query_relation_extract import extract_from_query_version
from ...services.query_runner import run_query_version
from pydantic import BaseModel, Field
from datetime import datetime, timezone

router = APIRouter(prefix="/api/v1/queries", tags=["queries"])


@router.get("", summary="查询主档列表")
def list_queries(
    keyword: str | None = Query(None),
    system_code: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=200),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    stmt = select(AssetQueryDefinition)
    if system_code:
        stmt = stmt.where(AssetQueryDefinition.system_code == system_code)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(
            or_(
                AssetQueryDefinition.query_code.ilike(like),
                AssetQueryDefinition.title.ilike(like),
                AssetQueryDefinition.purpose.ilike(like),
            )
        )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(AssetQueryDefinition.query_code)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    items = []
    for d in rows:
        item = _serialize_def(d)
        active = get_active_version(db, d.query_code)
        item["active_version"] = _serialize_ver(active) if active else None
        items.append(item)
    return ApiResponse(data={"total": total, "page": page, "page_size": page_size, "items": items})


@router.get("/ai/context", summary="AI 可读现行查询上下文")
def ai_query_context(
    system_code: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> ApiResponse[list[dict]]:
    stmt = select(AssetQueryVersion).where(
        AssetQueryVersion.is_active.is_(True),
        AssetQueryVersion.status == "active",
    )
    if system_code:
        defs = select(AssetQueryDefinition.query_code).where(
            AssetQueryDefinition.system_code == system_code,
            AssetQueryDefinition.ai_readable.is_(True),
        )
        stmt = stmt.where(AssetQueryVersion.query_code.in_(defs))
    rows = db.scalars(stmt.order_by(AssetQueryVersion.query_code).limit(limit)).all()
    out = []
    for v in rows:
        d = get_definition(db, v.query_code)
        out.append(
            {
                "query_code": v.query_code,
                "title": d.title if d else v.query_code,
                "purpose": d.purpose if d else None,
                "system_code": d.system_code if d else None,
                "source_code": d.source_code if d else None,
                "version": v.version,
                "sql_sha256": v.sql_sha256,
                "dialect": v.dialect,
                "grain": v.grain,
                "period_field": v.period_field,
                "limitations": v.limitations,
                "parameter_schema": v.parameter_schema,
                "sql_text": v.sql_text,
            }
        )
    return ApiResponse(data=out)


@router.get("/impact/table", summary="表变更影响分析（查询/指标）")
def impact_table(
    table_name: str = Query(..., min_length=1),
    schema_name: str | None = Query(None),
    active_only: bool = Query(False),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    return ApiResponse(
        data=impact_for_table(
            db, table_name=table_name, schema_name=schema_name, active_only=active_only
        )
    )


@router.get("/{query_code}/relation-candidates", summary="从查询 SQL 解析 JOIN 候选（不写正式关系）")
def relation_candidates(
    query_code: str,
    version: int | None = Query(None),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    data = extract_from_query_version(db, query_code, version)
    if not data.get("ok"):
        raise HTTPException(status_code=404, detail=data.get("error") or "not found")
    return ApiResponse(data=data)


class ScheduleUpsert(BaseModel):
    query_code: str
    schedule_cron: str = "0 3 * * *"
    source_code: str | None = None
    enabled: bool = False
    result_storage: str = "none"
    max_rows: int = Field(default=1000, ge=1, le=5000)


@router.get("/schedules/list", summary="查询调度定义列表（默认均为关闭）")
def list_schedules(db: Session = Depends(get_db)) -> ApiResponse[list[dict]]:
    rows = db.scalars(select(AssetQuerySchedule).order_by(AssetQuerySchedule.query_code)).all()
    return ApiResponse(
        data=[
            {
                "id": r.id,
                "query_code": r.query_code,
                "source_code": r.source_code,
                "schedule_cron": r.schedule_cron,
                "enabled": r.enabled,
                "result_storage": r.result_storage,
                "last_status": r.last_status,
                "last_run_at": r.last_run_at.isoformat() if r.last_run_at else None,
            }
            for r in rows
        ]
    )


@router.post(
    "/schedules",
    summary="登记查询调度（enabled 默认 false；全局开关 APP_QUERY_SCHEDULE_ENABLED）",
    dependencies=[Depends(require_permission("query:create"))],
)
def upsert_schedule(req: ScheduleUpsert, request: Request, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    user = "system"
    try:
        user = get_current_user(request) or user
    except Exception:
        pass
    row = db.scalar(select(AssetQuerySchedule).where(AssetQuerySchedule.query_code == req.query_code))
    if not row:
        row = AssetQuerySchedule(query_code=req.query_code, created_by=user)
        db.add(row)
    row.schedule_cron = req.schedule_cron
    row.source_code = req.source_code
    row.enabled = bool(req.enabled)
    row.result_storage = req.result_storage
    row.max_rows = req.max_rows
    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    return ApiResponse(
        data={
            "query_code": row.query_code,
            "enabled": row.enabled,
            "schedule_cron": row.schedule_cron,
            "note": "生产启用还需 APP_QUERY_SCHEDULE_ENABLED=true",
        }
    )


@router.post(
    "/schedules/seed-core",
    summary="为 QRY_CORE_* active 查询种子调度定义（默认 enabled=false）",
    dependencies=[Depends(require_permission("query:create"))],
)
def seed_core_schedules(
    request: Request,
    schedule_cron: str = Query("0 3 * * *"),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    """Safe seed: creates schedule rows for core queries but never enables them."""
    from ...core.config import settings
    from ...models.query_asset import AssetQueryDefinition, AssetQueryVersion

    user = "system"
    try:
        user = get_current_user(request) or user
    except Exception:
        pass
    qrows = db.scalars(
        select(AssetQueryVersion).where(
            AssetQueryVersion.is_active.is_(True),
            AssetQueryVersion.query_code.like("QRY_CORE_%"),
        )
    ).all()
    created = 0
    updated = 0
    items = []
    for q in qrows:
        d = db.scalar(select(AssetQueryDefinition).where(AssetQueryDefinition.query_code == q.query_code))
        row = db.scalar(select(AssetQuerySchedule).where(AssetQuerySchedule.query_code == q.query_code))
        if not row:
            row = AssetQuerySchedule(query_code=q.query_code, created_by=user)
            db.add(row)
            created += 1
            status = "created"
        else:
            updated += 1
            status = "exists"
        row.schedule_cron = schedule_cron
        # never auto-enable individual schedules
        if row.enabled is None:
            row.enabled = False
        row.source_code = row.source_code or (d.source_code if d else None)
        row.result_storage = row.result_storage or "none"
        row.updated_at = datetime.now(timezone.utc)
        items.append(
            {
                "query_code": q.query_code,
                "enabled": bool(row.enabled),
                "schedule_cron": row.schedule_cron,
                "status": status,
            }
        )
    db.commit()
    return ApiResponse(
        data={
            "created": created,
            "updated": updated,
            "count": len(items),
            "items": items,
            "global_query_schedule_enabled": bool(settings.query_schedule_enabled),
            "note": "种子默认 enabled=false；单条启用仍需本接口或 /schedules 显式 true",
        }
    )


@router.get("/sources/capabilities", summary="126 P5：多源连接适配能力探测")
def source_capabilities(db: Session = Depends(get_db)) -> ApiResponse[dict]:
    """List registered data sources and whether query runner can use them read-only."""
    from ...models.asset_system import AssetDataSource

    rows = db.scalars(select(AssetDataSource).order_by(AssetDataSource.source_code)).all()
    # Dialects currently supported by quality_sql_runner / query path
    supported_dialects = {"oracle", "postgresql", "postgres", "mysql", "sqlserver", "mssql"}
    items = []
    for r in rows:
        dialect = (r.db_type or "").lower()
        items.append(
            {
                "source_code": r.source_code,
                "title": r.source_name_cn or r.source_code,
                "system_code": r.system_code,
                "db_type": dialect or None,
                "host_masked": r.host_masked,
                "enabled": bool(r.enabled),
                "write_policy": r.write_policy,
                "credential_status": r.credential_status,
                "query_runner_supported": (dialect in supported_dialects) if dialect else True,
                "read_only": (r.write_policy or "readonly") == "readonly",
                "notes": "查询执行必须经登记连接；业务源库禁止 DML/DDL",
            }
        )
    return ApiResponse(
        data={
            "total": len(items),
            "supported_dialects": sorted(supported_dialects),
            "items": items,
        }
    )


class CoreImportRequest(BaseModel):
    dry_run: bool = True
    only_numbers: list[int] | None = None
    system_code: str = "DATA_CENTER"
    source_code: str = "ods_8_216"


@router.post(
    "/import/core-48",
    summary="导入 48 项核心制度 SQL 试点（默认 dry-run）",
    dependencies=[Depends(require_permission("query:create"))],
)
def import_core_48(
    req: CoreImportRequest, request: Request, db: Session = Depends(get_db)
) -> ApiResponse[dict]:
    user = "system"
    try:
        user = get_current_user(request) or user
    except Exception:
        pass
    try:
        result = import_core_metrics(
            db,
            dry_run=req.dry_run,
            system_code=req.system_code,
            source_code=req.source_code,
            created_by=user,
            only_numbers=set(req.only_numbers) if req.only_numbers else None,
        )
        return ApiResponse(data=result)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"{type(exc).__name__}: {exc}") from exc


@router.get("/runs/list", summary="运行记录列表")
def list_runs(
    query_code: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=200),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    stmt = select(AssetQueryRun)
    if query_code:
        stmt = stmt.where(AssetQueryRun.query_code == query_code)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(AssetQueryRun.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    items = [
        {
            "id": r.id,
            "query_code": r.query_code,
            "version": r.version,
            "source_code": r.source_code,
            "status": r.status,
            "row_count": r.row_count,
            "truncated": r.truncated,
            "result_storage": r.result_storage,
            "result_hash": r.result_hash,
            "duration_ms": r.duration_ms,
            "correlation_id": r.correlation_id,
            "error_class": r.error_class,
            "error_message": r.error_message,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
    return ApiResponse(data={"total": total, "page": page, "page_size": page_size, "items": items})


@router.get("/runs/{run_id}", summary="运行详情与可选结果")
def get_run(run_id: int, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    r = db.get(AssetQueryRun, run_id)
    if not r:
        raise HTTPException(status_code=404, detail="运行记录不存在")
    result = db.scalar(select(AssetQueryResult).where(AssetQueryResult.run_id == run_id))
    return ApiResponse(
        data={
            "run": {
                "id": r.id,
                "query_code": r.query_code,
                "version": r.version,
                "source_code": r.source_code,
                "parameters": r.parameters,
                "parameters_hash": r.parameters_hash,
                "status": r.status,
                "row_count": r.row_count,
                "result_storage": r.result_storage,
                "result_hash": r.result_hash,
                "correlation_id": r.correlation_id,
                "warnings": r.warnings,
                "error_class": r.error_class,
                "error_message": r.error_message,
            },
            "result": {
                "storage": result.storage,
                "summary_json": result.summary_json,
                "file_ref": result.file_ref,
                "truncated": result.truncated,
            }
            if result
            else None,
        }
    )


@router.get("/{query_code}", summary="查询主档详情")
def get_query(query_code: str, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    d = get_definition(db, query_code)
    if not d:
        raise HTTPException(status_code=404, detail="查询不存在")
    active = get_active_version(db, query_code)
    versions = db.scalars(
        select(AssetQueryVersion)
        .where(AssetQueryVersion.query_code == query_code)
        .order_by(AssetQueryVersion.version.desc())
    ).all()
    return ApiResponse(
        data={
            "definition": _serialize_def(d),
            "active_version": _serialize_ver(active) if active else None,
            "versions": [_serialize_ver(v) for v in versions],
        }
    )


@router.get("/{query_code}/versions", summary="查询版本列表")
def list_versions(query_code: str, db: Session = Depends(get_db)) -> ApiResponse[list[dict]]:
    rows = db.scalars(
        select(AssetQueryVersion)
        .where(AssetQueryVersion.query_code == query_code)
        .order_by(AssetQueryVersion.version.desc())
    ).all()
    return ApiResponse(data=[_serialize_ver(v) for v in rows])


@router.get("/{query_code}/versions/{version}", summary="查询版本详情")
def get_version(query_code: str, version: int, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    v = db.scalar(
        select(AssetQueryVersion).where(
            AssetQueryVersion.query_code == query_code,
            AssetQueryVersion.version == version,
        )
    )
    if not v:
        raise HTTPException(status_code=404, detail="版本不存在")
    deps = db.scalars(
        select(AssetQueryDependency).where(AssetQueryDependency.query_version_id == v.id)
    ).all()
    data = _serialize_ver(v)
    data["dependencies"] = [
        {
            "dep_type": d.dep_type,
            "schema_name": d.schema_name,
            "object_name": d.object_name,
            "column_name": d.column_name,
            "is_formal": d.is_formal,
            "evidence": d.evidence,
        }
        for d in deps
    ]
    return ApiResponse(data=data)


@router.get("/{query_code}/versions/{version}/diff", summary="与上一版本 SQL 差异摘要")
def version_diff(query_code: str, version: int, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    v = db.scalar(
        select(AssetQueryVersion).where(
            AssetQueryVersion.query_code == query_code,
            AssetQueryVersion.version == version,
        )
    )
    if not v:
        raise HTTPException(status_code=404, detail="版本不存在")
    parent = None
    if v.parent_version_id:
        parent = db.get(AssetQueryVersion, v.parent_version_id)
    elif version > 1:
        parent = db.scalar(
            select(AssetQueryVersion).where(
                AssetQueryVersion.query_code == query_code,
                AssetQueryVersion.version == version - 1,
            )
        )
    return ApiResponse(
        data={
            "query_code": query_code,
            "version": version,
            "sql_sha256": v.sql_sha256,
            "parent_version": parent.version if parent else None,
            "parent_sql_sha256": parent.sql_sha256 if parent else None,
            "same_sql": bool(parent and parent.sql_sha256 == v.sql_sha256),
            "revision_reason": v.revision_reason,
            "current_sql": v.sql_text,
            "parent_sql": parent.sql_text if parent else None,
        }
    )


@router.post("/gate", summary="SQL 自动门禁试算（不写库）")
def gate_preview(req: QueryGateRequest) -> ApiResponse[dict]:
    return ApiResponse(
        data=evaluate_query_gate(
            req.sql_text,
            dialect=req.dialect,
            system_code=req.system_code,
            source_code=req.source_code,
            # preview may omit source; run still requires registered source_code
            require_source=bool((req.source_code or "").strip()),
        )
    )


@router.post(
    "/ingest",
    summary="摄取查询包（自动门禁，通过即 active）",
    dependencies=[Depends(require_permission("query:create"))],
)
def ingest(req: QueryIngestRequest, request: Request, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    user = "system"
    try:
        user = get_current_user(request) or user
    except Exception:
        pass
    try:
        result = ingest_query(
            db,
            query_code=req.query_code,
            title=req.title,
            sql_text=req.sql_text,
            purpose=req.purpose,
            system_code=req.system_code,
            source_code=req.source_code,
            dialect=req.dialect,
            business_domain=req.business_domain,
            grain=req.grain,
            period_field=req.period_field,
            parameter_schema=req.parameter_schema,
            limitations=req.limitations,
            recipe_refs=req.recipe_refs,
            metric_refs=req.metric_refs,
            source_path=req.source_path,
            ai_source=req.ai_source,
            session_key=req.session_key,
            revision_reason=req.revision_reason,
            created_by=user,
            force_new_version=req.force_new_version,
        )
        db.commit()
        return ApiResponse(data=result)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/{query_code}/revise",
    summary="修订查询（强制新版本）",
    dependencies=[Depends(require_permission("query:create"))],
)
def revise(
    query_code: str,
    req: QueryReviseRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    user = "system"
    try:
        user = get_current_user(request) or user
    except Exception:
        pass
    try:
        result = revise_query(
            db,
            query_code=query_code,
            sql_text=req.sql_text,
            revision_reason=req.revision_reason,
            title=req.title,
            purpose=req.purpose,
            system_code=req.system_code,
            source_code=req.source_code,
            dialect=req.dialect or "oracle",
            session_key=req.session_key,
            created_by=user,
        )
        db.commit()
        return ApiResponse(data=result)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/run",
    summary="执行查询版本（参数不造版本；结果默认不存）",
    dependencies=[Depends(require_permission("query:run"))],
)
def run(req: QueryRunRequest, request: Request, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    user = "system"
    try:
        user = get_current_user(request) or user
    except Exception:
        pass
    try:
        result = run_query_version(
            db,
            query_version_id=req.query_version_id,
            query_code=req.query_code,
            version=req.version,
            source_code=req.source_code,
            parameters=req.parameters,
            result_storage=req.result_storage,
            max_rows=req.max_rows,
            sample_limit=req.sample_limit,
            triggered_by=user,
            session_key=req.session_key,
        )
        db.commit()
        return ApiResponse(data=result)
    except LookupError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
