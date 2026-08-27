import json
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict, Field

from ...core.db import get_db
from ...core.security import get_current_user, require_permission
from ...models.asset import AssetRelation, AssetTable, AssetColumn
from ...models.asset_system import AssetDataSource
from ...models.governance import MetadataSnapshot
from ...models.governance_base import GovernAuditLog
from ...models.governance_ops import SchedulerJob
from ...models.metadata_change import AssetMetadataChangeEvent, AssetMetadataColumnSnapshot
from ...models.quality import QualityFinding
from ...services.credentials import resolve
from ...services.data_masking import sanitize_text
from ...services.db_connectors import DB_CONNECTOR_MAP
from ...services.metadata_diff import MetadataDiff
from ...services.metadata_collector import METADATA_COLLECTOR_MAP
from ...schemas.common import ApiResponse

router = APIRouter(prefix="/api/v1", tags=["metadata-changes"])

PREVIEW_VALUE_LIMIT = 300
# The quality-linkage trigger covers both the legacy spelling used by early
# docs and the actual field-level type produced by MetadataDiff.
QUALITY_LINKED_TYPES = ("column_removed", "column_type_changed", "column_data_type_changed")


def _limited_value(value) -> str | None:
    """Render a before/after payload as a bounded, sanitized string."""
    if value is None:
        return None
    rendered = json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)
    return sanitize_text(rendered, limit=PREVIEW_VALUE_LIMIT)


class CollectRequest(BaseModel):
    label: str | None = None
    mode: Literal["asset_cache", "live_source"] = "asset_cache"
    schema_filter: list[str] | None = None


def _build_source_connector(source: AssetDataSource):
    db_type = (source.db_type or "").lower()
    connector_cls = DB_CONNECTOR_MAP.get(db_type)
    if connector_cls is None:
        raise HTTPException(status_code=400, detail=f"unsupported db_type: {source.db_type}")
    user, password = resolve(source.credential_ref)
    database = source.service_name or source.database_name or ""
    return connector_cls(
        host=source.host_masked or "",
        port=source.port or 0,
        database=database,
        user=user or "",
        password=password or "",
        connection_mode=source.connection_mode or "direct",
    )


def _create_snapshot(source_code: str, label: str, mode: str, db: Session) -> MetadataSnapshot:
    sp = MetadataSnapshot(
        label=label,
        scope="column_level",
        source_code=source_code,
        table_count=0,
        column_count=0,
        relation_count=0,
        data=json.dumps(
            {
                "source": source_code,
                "mode": mode,
                "collected_at": datetime.now(timezone.utc).isoformat(),
            },
            ensure_ascii=False,
        ),
    )
    db.add(sp)
    db.flush()
    return sp


def _collect_asset_cache_snapshot(source: AssetDataSource, label: str, db: Session) -> dict:
    source_code = source.source_code
    sp = _create_snapshot(source_code, label, "asset_cache", db)
    snapshot_id = sp.id

    tables = db.scalars(select(AssetTable).where(AssetTable.source_code == source_code)).all()
    col_count = 0
    for t in tables:
        cols = db.scalars(
            select(AssetColumn).where(
                AssetColumn.source_code == source_code,
                AssetColumn.table_name == t.table_name,
                AssetColumn.namespace_name == t.namespace_name,
            )
        ).all()
        for c in cols:
            db.add(AssetMetadataColumnSnapshot(
                snapshot_id=snapshot_id,
                system_code=c.system_code or t.system_code or source.system_code or "",
                source_code=source_code,
                namespace_name=c.namespace_name or "",
                table_name=c.table_name or "",
                column_name=c.column_name or "",
                data_type=c.data_type,
                length=c.length,
                nullable=c.nullable,
                comment=c.comment,
                is_primary_key=False,
            ))
            col_count += 1

    sp.table_count = len(tables)
    sp.column_count = col_count
    return {
        "snapshot_id": snapshot_id,
        "label": label,
        "mode": "asset_cache",
        "table_count": len(tables),
        "column_count": col_count,
    }


def _collect_live_source_snapshot(source: AssetDataSource, label: str, schema_filter: list[str] | None, db: Session) -> dict:
    source_code = source.source_code
    db_type = (source.db_type or "").lower()
    collector_cls = METADATA_COLLECTOR_MAP.get(db_type)
    if collector_cls is None:
        raise HTTPException(status_code=400, detail=f"unsupported metadata collector db_type: {source.db_type}")

    connector = _build_source_connector(source)
    try:
        collector = collector_cls(connector)
        collected = collector.collect_all(schema_filter=schema_filter)
    finally:
        connector.close()

    sp = _create_snapshot(source_code, label, "live_source", db)
    sp.data = json.dumps(
        {
            "source": source_code,
            "mode": "live_source",
            "schema_filter": schema_filter or [],
            "collected_at": datetime.now(timezone.utc).isoformat(),
        },
        ensure_ascii=False,
    )
    snapshot_id = sp.id

    for c in collected.get("columns", []):
        db.add(AssetMetadataColumnSnapshot(
            snapshot_id=snapshot_id,
            system_code=source.system_code or "",
            source_code=source_code,
            namespace_name=c.get("schema_name") or c.get("owner") or "",
            table_name=c.get("table_name") or "",
            column_name=c.get("column_name") or "",
            data_type=c.get("data_type"),
            length=c.get("length") or c.get("data_length"),
            nullable=c.get("nullable"),
            comment=c.get("comment"),
            is_primary_key=bool(c.get("is_primary_key")),
        ))

    table_count = len(collected.get("tables", []))
    column_count = len(collected.get("columns", []))
    sp.table_count = table_count
    sp.column_count = column_count
    return {
        "snapshot_id": snapshot_id,
        "label": label,
        "mode": "live_source",
        "schema_filter": schema_filter or [],
        "table_count": table_count,
        "column_count": column_count,
    }


def _collect_metadata_snapshot(
    source_code: str,
    label: str,
    db: Session,
    mode: str = "asset_cache",
    schema_filter: list[str] | None = None,
) -> dict:
    ds = db.scalar(select(AssetDataSource).where(AssetDataSource.source_code == source_code))
    if not ds:
        raise HTTPException(status_code=400, detail=f"data source {source_code} is not registered; create it under /api/v1/sources first")

    if mode == "live_source":
        return _collect_live_source_snapshot(ds, label, schema_filter, db)
    return _collect_asset_cache_snapshot(ds, label, db)


@router.post("/sources/{source_code}/collect-metadata", summary="手动触发元数据采集（P14-T5）", dependencies=[Depends(require_permission("metadata.snapshot.collect"))])
def collect_metadata(source_code: str, req: CollectRequest | None = None, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    label = (req.label if req else None) or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    mode = req.mode if req else "asset_cache"
    schema_filter = req.schema_filter if req else None
    result = _collect_metadata_snapshot(source_code, label, db, mode=mode, schema_filter=schema_filter)
    db.commit()

    job = SchedulerJob(
        job_type="metadata_scan",
        source_code=source_code,
        trigger_mode="manual",
        status="success",
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
        result_ref=json.dumps({
            "snapshot_id": result["snapshot_id"],
            "label": label,
            "mode": mode,
            "schema_filter": schema_filter or [],
        }, ensure_ascii=False),
        total_processed=result["table_count"],
        total_changes=0,
    )
    db.add(job)
    db.commit()
    result["job_id"] = job.id
    return ApiResponse(data=result)


@router.post("/sources/{source_code}/metadata-jobs/{job_id}/retry", summary="重试元数据采集任务", dependencies=[Depends(require_permission("metadata.snapshot.collect"))])
def retry_metadata_collect_job(source_code: str, job_id: int, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    job = db.get(SchedulerJob, job_id)
    if not job or job.job_type != "metadata_scan" or job.source_code != source_code:
        raise HTTPException(status_code=404, detail="metadata scan job not found")

    job.status = "running"
    job.started_at = datetime.now(timezone.utc)
    job.error_message = None
    db.commit()

    try:
        retry_params: dict = {}
        try:
            retry_params = json.loads(job.result_ref or "{}") if str(job.result_ref or "").strip().startswith("{") else {}
        except json.JSONDecodeError:
            retry_params = {}
        mode = retry_params.get("mode") or "asset_cache"
        schema_filter = retry_params.get("schema_filter") or None
        base_label = retry_params.get("label") or "metadata collect"
        label = f"retry {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} {base_label}"
        result = _collect_metadata_snapshot(source_code, label, db, mode=mode, schema_filter=schema_filter)
        job.status = "success"
        job.finished_at = datetime.now(timezone.utc)
        job.result_ref = json.dumps({
            "snapshot_id": result["snapshot_id"],
            "label": label,
            "mode": mode,
            "schema_filter": schema_filter or [],
        }, ensure_ascii=False)
        job.total_processed = result["table_count"]
        job.total_changes = 0
        job.error_message = None
        db.commit()
        result["job_id"] = job.id
        result["job_status"] = job.status
        return ApiResponse(data=result)
    except HTTPException:
        job.status = "failed"
        job.finished_at = datetime.now(timezone.utc)
        job.error_message = "metadata collect retry failed"
        db.commit()
        raise
    except Exception as exc:
        job.status = "failed"
        job.finished_at = datetime.now(timezone.utc)
        # Persist only a bounded, credential-safe diagnostic; raw DB/URL details
        # must never enter platform data or API responses.
        from ...services.data_masking import sanitize_text
        job.error_message = sanitize_text(str(exc), limit=500)
        db.commit()
        raise HTTPException(status_code=500, detail="metadata collect retry failed")

@router.get("/metadata-changes", summary="变更事件列表（P14-T6 数据接口）")
def list_changes(
    system_code: str | None = Query(None),
    source_code: str | None = Query(None),
    change_type: str | None = Query(None),
    severity: str | None = Query(None),
    status: str | None = Query(None),
    keyword: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=200),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    stmt = select(AssetMetadataChangeEvent)
    if system_code:
        stmt = stmt.where(AssetMetadataChangeEvent.system_code == system_code)
    if source_code:
        stmt = stmt.where(AssetMetadataChangeEvent.source_code == source_code)
    if change_type:
        stmt = stmt.where(AssetMetadataChangeEvent.change_type == change_type)
    if severity:
        stmt = stmt.where(AssetMetadataChangeEvent.severity == severity)
    if status:
        stmt = stmt.where(AssetMetadataChangeEvent.status == status)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(or_(
            AssetMetadataChangeEvent.table_name.ilike(like),
            AssetMetadataChangeEvent.column_name.ilike(like),
            AssetMetadataChangeEvent.namespace_name.ilike(like),
        ))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(AssetMetadataChangeEvent.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    items = [
        {
            "id": r.id,
            "snapshot_id_from": r.snapshot_id_from,
            "snapshot_id_to": r.snapshot_id_to,
            "system_code": r.system_code,
            "source_code": r.source_code,
            "namespace": r.namespace_name,
            "change_type": r.change_type,
            "table_name": r.table_name,
            "column_name": r.column_name,
            "severity": r.severity,
            "status": r.status,
            "assigned_to": r.assigned_to,
            "before_value": _limited_value(r.before_value),
            "after_value": _limited_value(r.after_value),
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
    return ApiResponse(data={"total": total, "page": page, "page_size": page_size, "items": items})


@router.patch("/metadata-changes/{change_id}", summary="更新变更事件状态/负责人/备注", dependencies=[Depends(require_permission("metadata.change.edit"))])
def update_change(change_id: int, status: str | None = Query(None), assigned_to: str | None = Query(None), note: str | None = Query(None), db: Session = Depends(get_db)) -> ApiResponse[dict]:
    evt = db.get(AssetMetadataChangeEvent, change_id)
    if not evt:
        raise HTTPException(status_code=404)
    if status:
        evt.status = status
    if assigned_to:
        evt.assigned_to = assigned_to
    if note:
        evt.review_note = note
    db.commit()
    return ApiResponse(data={"id": evt.id, "status": evt.status, "assigned_to": evt.assigned_to})


@router.get("/metadata-changes/summary", summary="变更统计（按系统/变更类型）")
def changes_summary(db: Session = Depends(get_db)) -> ApiResponse[dict]:
    events = db.scalars(select(AssetMetadataChangeEvent)).all()
    by_system: dict = {}
    by_type: dict = {}
    for e in events:
        by_system[e.system_code] = by_system.get(e.system_code, 0) + 1
        by_type[e.change_type] = by_type.get(e.change_type, 0) + 1
    return ApiResponse(data={
        "total": len(events),
        "by_system": by_system,
        "by_type": by_type,
        "open": sum(1 for e in events if e.status == "open"),
        "acknowledged": sum(1 for e in events if e.status == "acknowledged"),
        "resolved": sum(1 for e in events if e.status == "resolved"),
    })


class DiffPreviewRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    source: str = Field(..., min_length=1, max_length=100)
    from_snapshot_id: int = Field(..., alias="from")
    to_snapshot_id: int = Field(..., alias="to")
    type: str | None = None
    severity: str | None = None
    keyword: str | None = None
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=200)


@router.post("/metadata-changes/diff-preview", summary="字段级只读快照对比（零写，146 C3）", dependencies=[Depends(require_permission("metadata.diff.view"))])
def diff_preview(req: DiffPreviewRequest, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    """Compare two column snapshots without persisting events or quality findings."""
    s1 = db.get(MetadataSnapshot, req.from_snapshot_id)
    s2 = db.get(MetadataSnapshot, req.to_snapshot_id)
    if not s1 or not s2:
        raise HTTPException(status_code=404, detail="快照不存在")
    if s1.source_code != s2.source_code:
        raise HTTPException(status_code=400, detail="只能对比同一 source_code 的快照")
    if req.source != s1.source_code:
        raise HTTPException(status_code=400, detail="source 与快照归属不一致")

    events = MetadataDiff.diff(db, req.from_snapshot_id, req.to_snapshot_id, None, s1.source_code)

    items = []
    for e in events:
        if req.type and e.change_type != req.type:
            continue
        if req.severity and e.severity != req.severity:
            continue
        if req.keyword:
            like = req.keyword.lower()
            haystack = f"{e.namespace_name or ''} {e.table_name or ''} {e.column_name or ''}".lower()
            if like not in haystack:
                continue
        is_column = bool(e.column_name)
        items.append({
            "namespace": e.namespace_name,
            "table_name": e.table_name,
            "object_type": "column" if is_column else "table",
            "object_name": e.column_name if is_column else e.table_name,
            "field_name": (e.change_type[len("column_"):-len("_changed")]
                           if is_column and e.change_type.startswith("column_") and e.change_type.endswith("_changed")
                           else None),
            "change_type": e.change_type,
            "severity": e.severity,
            "before_value": _limited_value(e.before_value),
            "after_value": _limited_value(e.after_value),
            "quality_impact": ("生成变更事件时将联动创建质量 finding" if e.severity == "high" and e.change_type in QUALITY_LINKED_TYPES else None),
        })

    by_severity: dict[str, int] = {}
    by_type: dict[str, int] = {}
    tables_affected: set[tuple[str | None, str]] = set()
    for item in items:
        by_severity[item["severity"]] = by_severity.get(item["severity"], 0) + 1
        by_type[item["change_type"]] = by_type.get(item["change_type"], 0) + 1
        tables_affected.add((item["namespace"], item["table_name"]))

    total = len(items)
    start = (req.page - 1) * req.page_size
    return ApiResponse(data={
        "source": s1.source_code,
        "snapshot_from": {"id": s1.id, "label": s1.label},
        "snapshot_to": {"id": s2.id, "label": s2.label},
        "summary": {
            "total": total,
            "by_severity": by_severity,
            "by_type": by_type,
            "tables_affected": len(tables_affected),
        },
        "total": total,
        "page": req.page,
        "page_size": req.page_size,
        "items": items[start:start + req.page_size],
    })


@router.post("/metadata-changes/diff", summary="对比两个快照生成变更事件（显式治理动作，按对象键幂等）", dependencies=[Depends(require_permission("metadata.snapshot.collect"))])
def run_diff(
    snapshot_id_from: int = Query(...),
    snapshot_id_to: int = Query(...),
    system_code: str | None = Query(None),
    source_code: str | None = Query(None),
    request: Request = None,
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    s1 = db.get(MetadataSnapshot, snapshot_id_from)
    s2 = db.get(MetadataSnapshot, snapshot_id_to)
    if not s1 or not s2:
        raise HTTPException(status_code=404, detail="快照不存在")

    snapshot_source = s1.source_code
    if s2.source_code != snapshot_source:
        raise HTTPException(status_code=400, detail="只能对比同一 source_code 的快照")
    if source_code and source_code != snapshot_source:
        raise HTTPException(status_code=400, detail="source_code 与快照归属不一致")

    events = MetadataDiff.diff(
        db,
        snapshot_id_from,
        snapshot_id_to,
        system_code,
        source_code or snapshot_source,
    )

    existing_rows = db.scalars(select(AssetMetadataChangeEvent).where(
        AssetMetadataChangeEvent.snapshot_id_from == snapshot_id_from,
        AssetMetadataChangeEvent.snapshot_id_to == snapshot_id_to,
    )).all()
    existing_keys = {
        (e.namespace_name, e.table_name, e.column_name, e.change_type)
        for e in existing_rows
    }

    saved = 0
    skipped = 0
    linked_to_quality = 0
    for e in events:
        key = (e.namespace_name, e.table_name, e.column_name, e.change_type)
        if key in existing_keys:
            skipped += 1
            continue
        existing_keys.add(key)
        db.add(e)
        saved += 1
        if e.severity == "high" and e.change_type in QUALITY_LINKED_TYPES:
            qf = QualityFinding(
                rule_code="SOURCE_METADATA_STALE",
                target_type="column",
                target_ref=f"{e.namespace_name}.{e.table_name}.{e.column_name}",
                severity="major",
                metric_value=f"change={e.change_type}",
                detail={"change_type": e.change_type, "change_event_id": e.id},
            )
            db.add(qf)
            linked_to_quality += 1

    operator = get_current_user(request) if request is not None else "system"
    db.add(GovernAuditLog(
        module="metadata_change",
        entity_type="snapshot_diff",
        entity_ref=f"{snapshot_id_from}->{snapshot_id_to}",
        action="generate_change_events",
        operator=operator,
        after_data={"saved": saved, "skipped": skipped, "linked_to_quality": linked_to_quality},
    ))
    db.commit()

    return ApiResponse(data={
        "snapshot_from": {"id": s1.id, "label": s1.label, "source_code": snapshot_source},
        "snapshot_to": {"id": s2.id, "label": s2.label, "source_code": snapshot_source},
        "total_changes": saved,
        "skipped_existing": skipped,
        "linked_to_quality_findings": linked_to_quality,
    })


@router.get("/metadata-changes/{change_id}/impact", summary="变更影响分析")
def change_impact(change_id: int, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    evt = db.get(AssetMetadataChangeEvent, change_id)
    if not evt:
        raise HTTPException(status_code=404)

    affected_relations: list[dict] = []
    if evt.table_name:
        key = f"%.{evt.table_name}" if evt.namespace_name else evt.table_name
        rels = db.scalars(select(AssetRelation).where(
            (AssetRelation.from_table.ilike(f"%{key}")) | (AssetRelation.to_table.ilike(f"%{key}"))
        )).all()
        affected_relations = [
            {"rel_id": r.rel_id, "from_table": r.from_table, "to_table": r.to_table,
             "join_condition": r.join_condition, "confidence": r.confidence}
            for r in rels
        ]

    affected_quality_rules: list[dict] = []
    ref = f"{evt.namespace_name}.{evt.table_name}" if evt.namespace_name and evt.table_name else None
    if ref:
        findings = db.scalars(select(QualityFinding).where(
            QualityFinding.target_ref.ilike(f"%{ref}%")
        )).all()
        affected_quality_rules = [
            {"id": r.id, "rule_code": r.rule_code, "target_type": r.target_type,
             "target_ref": r.target_ref, "severity": r.severity}
            for r in findings
        ]

    return ApiResponse(data={
        "change_id": change_id,
        "affected_relations": affected_relations,
        "affected_quality_rules": affected_quality_rules,
    })


@router.get("/sources/{source_code}/snapshots", summary="快照历史（P14）")
def source_snapshots(
    source_code: str,
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
) -> ApiResponse[list[dict]]:
    rows = db.scalars(
        select(MetadataSnapshot)
        .where(
            MetadataSnapshot.scope == "column_level",
            MetadataSnapshot.source_code == source_code,
            MetadataSnapshot.archived_at.is_(None),
        )
        .order_by(MetadataSnapshot.snapshot_time.desc())
        .limit(limit)
    ).all()
    return ApiResponse(data=[
        {
            "id": r.id, "label": r.label,
            "source_code": r.source_code,
            "snapshot_time": r.snapshot_time.isoformat() if r.snapshot_time else None,
            "table_count": r.table_count, "column_count": r.column_count,
        }
        for r in rows
    ])


# ── 146 E9：快照分页/受限详情/受保护软归档 与 变更事件批量处理 ──

class ChangeBatchRequest(BaseModel):
    ids: list[int] = Field(..., min_length=1, max_length=500)
    action: Literal["acknowledge", "ignore", "resolve", "reopen"]
    assigned_to: str | None = None
    note: str | None = None


@router.post("/metadata-changes/batch", summary="批量更新变更事件状态/负责人/重开（146 E9）", dependencies=[Depends(require_permission("metadata.change.edit"))])
def batch_update_changes(req: ChangeBatchRequest, request: Request, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    operator = get_current_user(request)
    status_map = {
        "acknowledge": "acknowledged",
        "ignore": "ignored",
        "resolve": "resolved",
        "reopen": "open",
    }
    next_status = status_map[req.action]
    updated = 0
    missing: list[int] = []
    for change_id in req.ids:
        evt = db.get(AssetMetadataChangeEvent, change_id)
        if not evt:
            missing.append(change_id)
            continue
        evt.status = next_status
        if req.assigned_to:
            evt.assigned_to = req.assigned_to
        if req.note:
            evt.review_note = req.note
        updated += 1
    db.flush()
    db.add(GovernAuditLog(
        module="metadata_change",
        entity_type="change_event_batch",
        entity_ref=",".join(str(i) for i in req.ids[:20]),
        action=f"batch_{req.action}",
        operator=operator,
        after_data={"updated": updated, "status": next_status},
    ))
    db.commit()
    return ApiResponse(data={"updated": updated, "missing": missing, "status": next_status})


def _snapshot_payload(r) -> dict:
    return {
        "id": r.id, "label": r.label, "source_code": r.source_code,
        "snapshot_time": r.snapshot_time.isoformat() if r.snapshot_time else None,
        "table_count": r.table_count, "column_count": r.column_count,
        "relation_count": r.relation_count,
        "archived_at": r.archived_at.isoformat() if r.archived_at else None,
        "archived_by": r.archived_by,
    }


@router.get("/metadata-snapshots", summary="快照分页列表（默认排除归档项；146 E9）", dependencies=[Depends(require_permission("metadata.snapshot.view"))])
def list_metadata_snapshots(
    source_code: str | None = Query(None),
    include_archived: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    stmt = select(MetadataSnapshot).where(MetadataSnapshot.scope == "column_level")
    if source_code:
        stmt = stmt.where(MetadataSnapshot.source_code == source_code)
    if not include_archived:
        stmt = stmt.where(MetadataSnapshot.archived_at.is_(None))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(MetadataSnapshot.snapshot_time.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    return ApiResponse(data={"total": total, "page": page, "page_size": page_size, "items": [_snapshot_payload(r) for r in rows]})


SNAPSHOT_DETAIL_SAMPLE_LIMIT = 100


@router.get("/metadata-snapshots/{snapshot_id}", summary="快照受限详情（头部 + 限量字段样本；146 E9）", dependencies=[Depends(require_permission("metadata.snapshot.view"))])
def metadata_snapshot_detail(snapshot_id: int, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    snap = db.get(MetadataSnapshot, snapshot_id)
    if not snap:
        raise HTTPException(status_code=404, detail="快照不存在")
    columns = db.scalars(
        select(AssetMetadataColumnSnapshot)
        .where(AssetMetadataColumnSnapshot.snapshot_id == snapshot_id)
        .order_by(AssetMetadataColumnSnapshot.table_name, AssetMetadataColumnSnapshot.column_name)
        .limit(SNAPSHOT_DETAIL_SAMPLE_LIMIT + 1)
    ).all()
    truncated = len(columns) > SNAPSHOT_DETAIL_SAMPLE_LIMIT
    return ApiResponse(data={
        **_snapshot_payload(snap),
        "column_sample_truncated": truncated,
        "column_sample": [
            {"namespace_name": c.namespace_name, "table_name": c.table_name,
             "column_name": c.column_name, "data_type": c.data_type, "nullable": c.nullable}
            for c in columns[:SNAPSHOT_DETAIL_SAMPLE_LIMIT]
        ],
    })


@router.post("/metadata-snapshots/{snapshot_id}/archive", summary="快照受保护软归档（引用存在时拒绝；禁止物理删除；146 E9）", dependencies=[Depends(require_permission("metadata.snapshot.collect"))])
def archive_metadata_snapshot(snapshot_id: int, request: Request, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    operator = get_current_user(request)
    snap = db.get(MetadataSnapshot, snapshot_id)
    if not snap:
        raise HTTPException(status_code=404, detail="快照不存在")
    if snap.archived_at:
        raise HTTPException(status_code=400, detail="快照已归档")
    referenced = db.scalar(select(func.count()).select_from(
        select(AssetMetadataChangeEvent).where(
            (AssetMetadataChangeEvent.snapshot_id_from == snapshot_id)
            | (AssetMetadataChangeEvent.snapshot_id_to == snapshot_id)
        ).subquery()
    )) or 0
    if referenced:
        raise HTTPException(status_code=409, detail=f"快照被 {referenced} 条变更事件引用，禁止归档")
    snap.archived_at = datetime.now(timezone.utc)
    snap.archived_by = operator
    db.flush()
    db.add(GovernAuditLog(
        module="metadata_change",
        entity_type="metadata_snapshot",
        entity_ref=str(snapshot_id),
        action="archive_snapshot",
        operator=operator,
        after_data={"label": snap.label, "source_code": snap.source_code},
    ))
    db.commit()
    return ApiResponse(data=_snapshot_payload(snap))
