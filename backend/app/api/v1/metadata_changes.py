from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from pydantic import BaseModel

from ...core.db import get_db
from ...models.asset import AssetRelation, AssetTable, AssetColumn
from ...models.asset_system import AssetDataSource
from ...models.governance import MetadataSnapshot
from ...models.governance_ops import SchedulerJob
from ...models.metadata_change import AssetMetadataChangeEvent, AssetMetadataColumnSnapshot
from ...models.quality import QualityFinding
from ...services.metadata_diff import MetadataDiff
from ...schemas.common import ApiResponse

router = APIRouter(prefix="/api/v1", tags=["metadata-changes"])


class CollectRequest(BaseModel):
    label: str | None = None


@router.post("/sources/{source_code}/collect-metadata", summary="手动触发元数据采集（P14-T5）")
def collect_metadata(source_code: str, req: CollectRequest | None = None, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    ds = db.scalar(select(AssetDataSource).where(AssetDataSource.source_code == source_code))
    if not ds:
        raise HTTPException(status_code=400, detail=f"数据源 {source_code} 未注册，请先在 /api/v1/sources 创建")

    label = (req.label if req else None) or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")

    sp = MetadataSnapshot(
        label=label,
        scope="column_level",
        table_count=0,
        column_count=0,
        relation_count=0,
        data=f'{{"source": "{source_code}", "collected_at": "{datetime.now(timezone.utc).isoformat()}"}}',
    )
    db.add(sp)
    db.flush()
    snapshot_id = sp.id

    tables = db.scalars(
        select(AssetTable).where(AssetTable.source_code == source_code)
    ).all()

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
                system_code=c.system_code or t.system_code or "",
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
    db.commit()

    job = SchedulerJob(
        job_type="metadata_scan",
        source_code=source_code,
        trigger_mode="manual",
        status="success",
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
        result_ref=str(snapshot_id),
        total_processed=len(tables),
        total_changes=0,
    )
    db.add(job)
    db.commit()

    return ApiResponse(data={
        "snapshot_id": snapshot_id,
        "label": label,
        "table_count": len(tables),
        "column_count": col_count,
    })


@router.get("/metadata-changes", summary="变更事件列表（P14-T6 数据接口）")
def list_changes(
    system_code: str | None = Query(None),
    change_type: str | None = Query(None),
    severity: str | None = Query(None),
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=200),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    stmt = select(AssetMetadataChangeEvent)
    if system_code:
        stmt = stmt.where(AssetMetadataChangeEvent.system_code == system_code)
    if change_type:
        stmt = stmt.where(AssetMetadataChangeEvent.change_type == change_type)
    if severity:
        stmt = stmt.where(AssetMetadataChangeEvent.severity == severity)
    if status:
        stmt = stmt.where(AssetMetadataChangeEvent.status == status)
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
            "change_type": r.change_type,
            "table_name": r.table_name,
            "column_name": r.column_name,
            "severity": r.severity,
            "status": r.status,
            "assigned_to": r.assigned_to,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
    return ApiResponse(data={"total": total, "page": page, "page_size": page_size, "items": items})


@router.patch("/metadata-changes/{change_id}", summary="更新变更事件状态/负责人/备注")
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


@router.post("/metadata-changes/diff", summary="对比两个快照生成变更事件（P14-T2）")
def run_diff(
    snapshot_id_from: int = Query(...),
    snapshot_id_to: int = Query(...),
    system_code: str | None = Query(None),
    source_code: str | None = Query(None),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    s1 = db.get(MetadataSnapshot, snapshot_id_from)
    s2 = db.get(MetadataSnapshot, snapshot_id_to)
    if not s1 or not s2:
        raise HTTPException(status_code=404, detail="快照不存在")

    events = MetadataDiff.diff(db, snapshot_id_from, snapshot_id_to, system_code, source_code)

    saved = 0
    linked_to_quality = 0
    for e in events:
        db.add(e)
        saved += 1
        if e.change_type in ("column_removed", "column_type_changed") and e.severity == "high":
            from ...models.quality import QualityFinding
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

    db.commit()

    return ApiResponse(data={
        "snapshot_from": {"id": s1.id, "label": s1.label},
        "snapshot_to": {"id": s2.id, "label": s2.label},
        "total_changes": saved,
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
        .where(MetadataSnapshot.scope == "column_level")
        .order_by(MetadataSnapshot.snapshot_time.desc())
        .limit(limit)
    ).all()
    return ApiResponse(data=[
        {
            "id": r.id, "label": r.label,
            "snapshot_time": r.snapshot_time.isoformat() if r.snapshot_time else None,
            "table_count": r.table_count, "column_count": r.column_count,
        }
        for r in rows
    ])
