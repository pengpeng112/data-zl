from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from ...core.db import get_db
from ...models.asset import AssetTable, AssetColumn
from ...models.asset_system import AssetDataSource, AssetSystem
from ...schemas.common import ApiResponse

router = APIRouter(prefix="/api/v1", tags=["systems"])


class SystemUpsert(BaseModel):
    system_code: str
    system_name_cn: str
    system_name_en: str | None = None
    system_type: str | None = None
    owner_department: str | None = None
    description_cn: str | None = None
    status: str | None = "active"


class DataSourceUpsert(BaseModel):
    system_code: str
    source_code: str
    source_name_cn: str
    db_type: str | None = None
    host_masked: str | None = None
    port: int | None = None
    service_name: str | None = None
    database_name: str | None = None
    connection_mode: str | None = None
    environment: str | None = None
    collect_mode: str | None = "metadata_only"
    credential_ref: str | None = None
    write_credential_ref: str | None = None
    description_cn: str | None = None
    enabled: bool = True


# ── 系统 ──

@router.get("/systems", summary="系统列表")
def list_systems(
    db: Session = Depends(get_db),
) -> ApiResponse[list[dict]]:
    rows = db.scalars(select(AssetSystem).order_by(AssetSystem.system_code)).all()
    return ApiResponse(data=[
        {
            "id": r.id, "system_code": r.system_code,
            "system_name_cn": r.system_name_cn,
            "system_type": r.system_type, "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ])


@router.put("/systems", summary="新增/更新系统")
def upsert_system(req: SystemUpsert, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    existing = db.scalar(select(AssetSystem).where(AssetSystem.system_code == req.system_code))
    if existing:
        existing.system_name_cn = req.system_name_cn
        existing.system_name_en = req.system_name_en
        existing.system_type = req.system_type
        existing.owner_department = req.owner_department
        existing.description_cn = req.description_cn
        existing.status = req.status
        existing.updated_at = datetime.now(timezone.utc)
        sys = existing
    else:
        sys = AssetSystem(
            system_code=req.system_code,
            system_name_cn=req.system_name_cn,
            system_name_en=req.system_name_en,
            system_type=req.system_type,
            owner_department=req.owner_department,
            description_cn=req.description_cn,
            status=req.status or "active",
        )
        db.add(sys)
    db.commit()
    db.refresh(sys)
    return ApiResponse(data={"id": sys.id, "system_code": sys.system_code})


@router.delete("/systems/{system_code}", summary="删除系统")
def delete_system(system_code: str, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    sys = db.scalar(select(AssetSystem).where(AssetSystem.system_code == system_code))
    if not sys:
        raise HTTPException(status_code=404)
    # remove referencing sources first
    refs = db.scalars(select(AssetDataSource).where(AssetDataSource.system_code == system_code)).all()
    for r in refs:
        db.delete(r)
    db.delete(sys)
    db.commit()
    return ApiResponse(data={"deleted": system_code})


# ── 数据源 ──

@router.get("/sources", summary="数据源列表")
def list_sources(
    system_code: str | None = Query(None),
    db: Session = Depends(get_db),
) -> ApiResponse[list[dict]]:
    stmt = select(AssetDataSource)
    if system_code:
        stmt = stmt.where(AssetDataSource.system_code == system_code)
    rows = db.scalars(stmt.order_by(AssetDataSource.source_code)).all()
    return ApiResponse(data=[
        {
            "id": r.id, "system_code": r.system_code,
            "source_code": r.source_code, "source_name_cn": r.source_name_cn,
            "db_type": r.db_type, "environment": r.environment,
            "collect_mode": r.collect_mode,
            "enabled": r.enabled, "last_check_status": r.last_check_status,
        }
        for r in rows
    ])


@router.put("/sources", summary="新增/更新数据源")
def upsert_source(req: DataSourceUpsert, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    sys = db.scalar(select(AssetSystem).where(AssetSystem.system_code == req.system_code))
    if not sys:
        raise HTTPException(status_code=400, detail=f"系统 {req.system_code} 不存在，请先创建系统")
    existing = db.scalar(select(AssetDataSource).where(AssetDataSource.source_code == req.source_code))
    if existing:
        existing.system_code = req.system_code
        existing.source_name_cn = req.source_name_cn
        existing.db_type = req.db_type
        existing.host_masked = req.host_masked
        existing.port = req.port
        existing.service_name = req.service_name
        existing.database_name = req.database_name
        existing.connection_mode = req.connection_mode
        existing.environment = req.environment
        existing.collect_mode = req.collect_mode
        existing.credential_ref = req.credential_ref
        existing.write_credential_ref = req.write_credential_ref
        existing.description_cn = req.description_cn
        existing.enabled = req.enabled
        existing.updated_at = datetime.now(timezone.utc)
        ds = existing
    else:
        ds = AssetDataSource(
            system_code=req.system_code,
            source_code=req.source_code,
            source_name_cn=req.source_name_cn,
            db_type=req.db_type,
            host_masked=req.host_masked,
            port=req.port,
            service_name=req.service_name,
            database_name=req.database_name,
            connection_mode=req.connection_mode,
            environment=req.environment,
            collect_mode=req.collect_mode or "metadata_only",
            credential_ref=req.credential_ref,
            write_credential_ref=req.write_credential_ref,
            description_cn=req.description_cn,
            enabled=req.enabled,
        )
        db.add(ds)
    db.commit()
    db.refresh(ds)
    return ApiResponse(data={"id": ds.id, "source_code": ds.source_code})


@router.post("/sources/{source_code}/check", summary="数据源连通性检测")
def check_source(source_code: str, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    ds = db.scalar(select(AssetDataSource).where(AssetDataSource.source_code == source_code))
    if not ds:
        raise HTTPException(status_code=404)

    try:
        from ...services.db_connectors import DB_CONNECTOR_MAP
        from ...services.credentials import resolve
        user, pwd = resolve(ds.credential_ref)
        connector_cls = DB_CONNECTOR_MAP.get(ds.db_type or "oracle")
        if not connector_cls:
            ds.last_check_status = "unsupported"
            ds.last_check_at = datetime.now(timezone.utc)
            db.commit()
            return ApiResponse(data={"source_code": ds.source_code, "status": "unsupported", "message": f"不支持的数据库类型: {ds.db_type}"})

        connector = connector_cls(
            host=ds.host_masked or "localhost", port=ds.port or 1521,
            database=ds.database_name or ds.service_name or "",
            user=user or "", password=pwd or "",
            connection_mode=ds.connection_mode or "direct",
        )
        ok, msg, elapsed_ms = connector.test_connectivity()
        ds.last_check_status = "connected" if ok else "failed"
        ds.last_check_at = datetime.now(timezone.utc)
        db.commit()
        return ApiResponse(data={
            "source_code": ds.source_code,
            "status": "connected" if ok else "failed",
            "message": msg,
            "elapsed_ms": elapsed_ms,
        })
    except Exception as e:
        ds.last_check_status = "failed"
        ds.last_check_at = datetime.now(timezone.utc)
        db.commit()
        return ApiResponse(data={"source_code": ds.source_code, "status": "failed", "message": str(e)[:200], "elapsed_ms": 0})


@router.delete("/sources/{source_code}", summary="删除数据源")
def delete_source(source_code: str, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    ds = db.scalar(select(AssetDataSource).where(AssetDataSource.source_code == source_code))
    if not ds:
        raise HTTPException(status_code=404)
    db.delete(ds)
    db.commit()
    return ApiResponse(data={"deleted": source_code})


# ── 资产树（五层结构） ──

@router.get("/assets/tree", summary="系统 -> 数据源 -> schema -> 表 树")
def assets_tree(
    system_code: str | None = Query(None),
    db: Session = Depends(get_db),
) -> ApiResponse[list[dict]]:
    sources_stmt = select(AssetDataSource)
    if system_code:
        sources_stmt = sources_stmt.where(AssetDataSource.system_code == system_code)
    sources = {s.source_code: s for s in db.scalars(sources_stmt).all()}

    tables = db.scalars(select(AssetTable)).all()

    grouped: dict[str, dict] = {}
    for t in tables:
        sc = t.source_code or "DATA_CENTER"
        ns = t.namespace_name or t.schema_name or ""
        if sc not in grouped:
            grouped[sc] = {"schemas": {}}
        if ns not in grouped[sc]["schemas"]:
            grouped[sc]["schemas"][ns] = []
        grouped[sc]["schemas"][ns].append({
            "id": t.id, "table_name": t.table_name,
            "table_name_cn": t.table_name_cn,
            "column_count": t.column_count,
            "domain": t.domain,
        })

    tree = []
    for sc, sc_data in sorted(grouped.items()):
        ds = sources.get(sc)
        node = {
            "source_code": sc,
            "source_name_cn": ds.source_name_cn if ds else sc,
            "system_code": ds.system_code if ds else "DATA_CENTER",
            "schemas": [],
            "table_count": sum(len(v) for v in sc_data["schemas"].values()),
        }
        for ns, tbls in sorted(sc_data["schemas"].items()):
            node["schemas"].append({
                "namespace": ns,
                "tables": tbls,
                "table_count": len(tbls),
            })
        tree.append(node)

    return ApiResponse(data=tree)
