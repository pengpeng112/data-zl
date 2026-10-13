"""215 E11 自 systems.py 拆出：系统登记与连接挂载（/api/v1/systems*）。"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, SecretStr, field_validator

from ....core.db import get_db
from ....models.asset import AssetTable, AssetColumn
from ....models.asset_system import AssetDataSource, AssetSystem
from ....schemas.common import ApiResponse
from ....core.security import get_current_user, require_permission
from ....services import credential_store
from ....services.connection_identity import (
    build_connection_identity_key,
    default_port,
    host_masked_from_target,
    validate_connection_fields,
)
from ....services.asset_catalog import (
    list_first_level_systems,
)
from ._router import router
from ._shared import _audit, _source_public


class SystemUpsert(BaseModel):
    system_code: str
    system_name_cn: str
    system_name_en: str | None = None
    system_type: str | None = None
    target_host: str | None = None
    owner_department: str | None = None
    description_cn: str | None = None
    status: str | None = "active"

class ConnectionInput(BaseModel):
    source_code: str = Field(..., min_length=1, max_length=120)
    source_name_cn: str
    db_type: str
    target_host: str
    port: int | None = None
    service_mode: str | None = None
    service_name: str | None = None
    database_name: str | None = None
    default_schema: str | None = None
    username: str | None = None
    password: SecretStr | None = None
    environment: str | None = "prod"
    connection_mode: str | None = "direct"
    collect_mode: str | None = "metadata_only"
    display_order: int = 0
    write_policy: str = "readonly"
    connection_options: dict[str, Any] | None = None
    description_cn: str | None = None
    enabled: bool = True

    @field_validator("db_type")
    @classmethod
    def _norm_db_type(cls, v: str) -> str:
        return (v or "").strip().lower()

    @field_validator("source_code")
    @classmethod
    def _norm_source_code(cls, v: str) -> str:
        return (v or "").strip()

class SystemWithConnectionsCreate(BaseModel):
    system_code: str
    system_name_cn: str
    system_name_en: str | None = None
    system_type: str | None = None
    target_host: str | None = None
    owner_department: str | None = None
    description_cn: str | None = None
    status: str | None = "active"
    connections: list[ConnectionInput] = Field(default_factory=list)

# ── 系统 ──

@router.get("/systems", summary="系统列表")
def list_systems(
    include_merged: bool = Query(False),
    db: Session = Depends(get_db),
) -> ApiResponse[list[dict]]:
    """First-level systems only: ten peers from asset_systems.system_name_cn.

    Plan 90: no platform_meta / external_business groups; independent sources
    are peers; DATA_CENTER owners never appear as first-level systems.
    """
    items = list_first_level_systems(db, include_merged=include_merged)
    return ApiResponse(data=items)

@router.put("/systems", summary="新增/更新系统", dependencies=[Depends(require_permission("source:manage"))])
def upsert_system(req: SystemUpsert, request: Request, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    operator = get_current_user(request)
    existing = db.scalar(select(AssetSystem).where(AssetSystem.system_code == req.system_code))
    if existing:
        existing.system_name_cn = req.system_name_cn
        existing.system_name_en = req.system_name_en
        existing.system_type = req.system_type
        existing.target_host = req.target_host if req.target_host is not None else existing.target_host
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
            target_host=req.target_host,
            owner_department=req.owner_department,
            description_cn=req.description_cn,
            status=req.status or "active",
            system_identity_key=(req.target_host or req.system_code or "").lower(),
        )
        db.add(sys)
    db.commit()
    db.refresh(sys)
    return ApiResponse(data={"id": sys.id, "system_code": sys.system_code, "updated_by": operator})

@router.patch("/systems/{system_code}", summary="部分更新系统", dependencies=[Depends(require_permission("source:manage"))])
def patch_system(system_code: str, req: SystemUpsert, request: Request, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    sys = db.scalar(select(AssetSystem).where(AssetSystem.system_code == system_code))
    if not sys:
        raise HTTPException(status_code=404, detail="system not found")
    if req.system_name_cn:
        sys.system_name_cn = req.system_name_cn
    if req.system_name_en is not None:
        sys.system_name_en = req.system_name_en
    if req.system_type is not None:
        sys.system_type = req.system_type
    if req.target_host is not None:
        sys.target_host = req.target_host
    if req.owner_department is not None:
        sys.owner_department = req.owner_department
    if req.description_cn is not None:
        sys.description_cn = req.description_cn
    if req.status is not None:
        sys.status = req.status
    sys.updated_at = datetime.now(timezone.utc)
    db.commit()
    return ApiResponse(data={"system_code": system_code, "updated_by": get_current_user(request)})

@router.get("/systems/{system_code}/detail", summary="系统详情（含连接与统计）")
def system_detail(system_code: str, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    sys = db.scalar(select(AssetSystem).where(AssetSystem.system_code == system_code))
    if not sys:
        raise HTTPException(status_code=404, detail="system not found")
    sources = db.scalars(
        select(AssetDataSource)
        .where(AssetDataSource.system_code == system_code)
        .order_by(AssetDataSource.display_order, AssetDataSource.source_code)
    ).all()
    schema_count = db.scalar(
        select(func.count(func.distinct(func.coalesce(AssetTable.schema_name, AssetTable.namespace_name, ""))))
        .where(AssetTable.system_code == system_code)
    ) or 0
    table_count = db.scalar(select(func.count()).where(AssetTable.system_code == system_code)) or 0
    column_count = db.scalar(select(func.count()).where(AssetColumn.system_code == system_code)) or 0
    return ApiResponse(data={
        "id": sys.id,
        "system_code": sys.system_code,
        "system_name_cn": sys.system_name_cn,
        "system_type": sys.system_type,
        "status": sys.status,
        "target_host": sys.target_host,
        "description_cn": sys.description_cn,
        "connection_count": len(sources),
        "schema_count": int(schema_count),
        "table_count": int(table_count),
        "column_count": int(column_count),
        "connections": [_source_public(s) for s in sources],
    })

@router.post(
    "/systems-with-connections",
    summary="组合创建系统与一个或多个数据连接",
    dependencies=[Depends(require_permission("source:manage"))],
)
def create_system_with_connections(
    req: SystemWithConnectionsCreate,
    request: Request,
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    operator = get_current_user(request)
    existing = db.scalar(select(AssetSystem).where(AssetSystem.system_code == req.system_code))
    if existing and (existing.status or "").lower() not in {"merged", "deleted", "inactive"}:
        raise HTTPException(status_code=409, detail=f"system {req.system_code} already exists")

    pending_creds: list[tuple[str, str, str | None]] = []  # source_code, pending_ref, username
    created_sources: list[str] = []
    try:
        for conn in req.connections:
            payload = {
                "db_type": conn.db_type,
                "target_host": conn.target_host,
                "port": conn.port if conn.port is not None else default_port(conn.db_type),
                "service_mode": conn.service_mode,
                "service_name": conn.service_name,
                "database_name": conn.database_name,
                "write_policy": conn.write_policy or "readonly",
                "system_code": req.system_code,
            }
            errors = validate_connection_fields(payload)
            if errors:
                raise HTTPException(status_code=400, detail="; ".join(errors))
            identity = build_connection_identity_key(
                conn.db_type, conn.target_host, payload["port"],
                conn.service_name, conn.database_name, conn.service_mode,
            )
            conflict = db.scalar(
                select(AssetDataSource).where(AssetDataSource.connection_identity_key == identity)
            )
            if conflict:
                raise HTTPException(status_code=409, detail=f"connection identity conflict with {conflict.source_code}")
            existing_src = db.scalar(select(AssetDataSource).where(AssetDataSource.source_code == conn.source_code))
            if existing_src:
                raise HTTPException(status_code=409, detail=f"source_code {conn.source_code} already exists")
            if conn.username and conn.password is not None:
                pending = credential_store.store(
                    conn.source_code,
                    conn.username,
                    conn.password.get_secret_value(),
                    activate=False,
                )
                pending_creds.append((conn.source_code, pending, conn.username))

        if not existing:
            sys = AssetSystem(
                system_code=req.system_code,
                system_name_cn=req.system_name_cn,
                system_name_en=req.system_name_en,
                system_type=req.system_type,
                target_host=req.target_host,
                owner_department=req.owner_department,
                description_cn=req.description_cn,
                status=req.status or "active",
                system_identity_key=(req.target_host or req.system_code).lower(),
            )
            db.add(sys)
        else:
            existing.system_name_cn = req.system_name_cn
            existing.status = req.status or "active"
            existing.updated_at = datetime.now(timezone.utc)
            sys = existing

        for conn in req.connections:
            port = conn.port if conn.port is not None else default_port(conn.db_type)
            identity = build_connection_identity_key(
                conn.db_type, conn.target_host, port,
                conn.service_name, conn.database_name, conn.service_mode,
            )
            pending_ref = next((p for c, p, _ in pending_creds if c == conn.source_code), None)
            ds = AssetDataSource(
                system_code=req.system_code,
                source_code=conn.source_code,
                source_name_cn=conn.source_name_cn,
                db_type=conn.db_type,
                target_host=conn.target_host,
                host_masked=host_masked_from_target(conn.target_host),
                port=port,
                service_mode=conn.service_mode,
                service_name=conn.service_name,
                database_name=conn.database_name,
                default_schema=conn.default_schema,
                connection_mode=conn.connection_mode or "direct",
                environment=conn.environment or "prod",
                collect_mode=conn.collect_mode or "metadata_only",
                display_order=conn.display_order,
                write_policy=conn.write_policy or "readonly",
                connection_options=conn.connection_options,
                description_cn=conn.description_cn,
                enabled=conn.enabled,
                connection_identity_key=identity,
                identity_source="manual",
                credential_ref=None,
                credential_status="unconfigured",
            )
            if pending_ref:
                # temporary pending path; activated after commit
                ds.credential_ref = pending_ref
                ds.credential_status = "pending"
                ds.credential_username_masked = credential_store.mask_username(conn.username)
                ds.credential_updated_at = datetime.now(timezone.utc)
                ds.credential_updated_by = operator
            db.add(ds)
            created_sources.append(conn.source_code)

        db.flush()
        _audit(
            db,
            action="create_system_with_connections",
            operator=operator,
            entity_ref=req.system_code,
            after={
                "system_code": req.system_code,
                "sources": created_sources,
                "credential_sources": [c for c, _, _ in pending_creds],
            },
        )
        db.commit()
    except HTTPException:
        for _code, pending, _ in pending_creds:
            try:
                if pending.startswith("file://"):
                    p = Path(pending[7:])
                    if p.exists():
                        p.unlink()
            except OSError:
                pass
        raise
    except Exception:
        db.rollback()
        for _code, pending, _ in pending_creds:
            try:
                if pending.startswith("file://"):
                    p = Path(pending[7:])
                    if p.exists():
                        p.unlink()
            except OSError:
                pass
        raise

    # activate credentials after DB commit
    activated = []
    for source_code, pending, username in pending_creds:
        ds = db.scalar(select(AssetDataSource).where(AssetDataSource.source_code == source_code))
        if not ds:
            continue
        try:
            final_ref = credential_store.activate(pending, source_code)
            ds.credential_ref = final_ref
            ds.credential_status = "configured"
            activated.append(source_code)
        except credential_store.CredentialStoreError:
            ds.credential_status = "error"
            _audit(
                db,
                action="credential_activate_failed",
                operator=operator,
                entity_ref=source_code,
                after={"credential_status": "error"},
            )
        db.commit()

    return ApiResponse(data={
        "system_code": req.system_code,
        "sources": created_sources,
        "credentials_activated": activated,
    })

@router.post(
    "/systems/{system_code}/connections",
    summary="为系统新增连接",
    dependencies=[Depends(require_permission("source:manage"))],
)
def add_system_connection(
    system_code: str,
    req: ConnectionInput,
    request: Request,
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    operator = get_current_user(request)
    sys = db.scalar(select(AssetSystem).where(AssetSystem.system_code == system_code))
    if not sys:
        raise HTTPException(status_code=404, detail="system not found")
    payload = {
        "db_type": req.db_type,
        "target_host": req.target_host,
        "port": req.port if req.port is not None else default_port(req.db_type),
        "service_mode": req.service_mode,
        "service_name": req.service_name,
        "database_name": req.database_name,
        "write_policy": req.write_policy or "readonly",
        "system_code": system_code,
    }
    errors = validate_connection_fields(payload)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    if db.scalar(select(AssetDataSource).where(AssetDataSource.source_code == req.source_code)):
        raise HTTPException(status_code=409, detail="source_code already exists")
    identity = build_connection_identity_key(
        req.db_type, req.target_host, payload["port"],
        req.service_name, req.database_name, req.service_mode,
    )
    if db.scalar(select(AssetDataSource).where(AssetDataSource.connection_identity_key == identity)):
        raise HTTPException(status_code=409, detail="connection identity conflict")

    pending_ref = None
    if req.username and req.password is not None:
        pending_ref = credential_store.store(
            req.source_code, req.username, req.password.get_secret_value(), activate=False
        )

    ds = AssetDataSource(
        system_code=system_code,
        source_code=req.source_code,
        source_name_cn=req.source_name_cn,
        db_type=req.db_type,
        target_host=req.target_host,
        host_masked=host_masked_from_target(req.target_host),
        port=payload["port"],
        service_mode=req.service_mode,
        service_name=req.service_name,
        database_name=req.database_name,
        default_schema=req.default_schema,
        connection_mode=req.connection_mode or "direct",
        environment=req.environment or "prod",
        collect_mode=req.collect_mode or "metadata_only",
        display_order=req.display_order,
        write_policy=req.write_policy or "readonly",
        connection_options=req.connection_options,
        description_cn=req.description_cn,
        enabled=req.enabled,
        connection_identity_key=identity,
        credential_ref=pending_ref,
        credential_status="pending" if pending_ref else "unconfigured",
        credential_username_masked=credential_store.mask_username(req.username) if req.username else None,
        credential_updated_at=datetime.now(timezone.utc) if pending_ref else None,
        credential_updated_by=operator if pending_ref else None,
    )
    db.add(ds)
    _audit(db, action="add_connection", operator=operator, entity_ref=req.source_code,
           after={"system_code": system_code, "source_code": req.source_code, "db_type": req.db_type})
    db.commit()
    if pending_ref:
        try:
            final_ref = credential_store.activate(pending_ref, req.source_code)
            ds.credential_ref = final_ref
            ds.credential_status = "configured"
            db.commit()
        except credential_store.CredentialStoreError:
            ds.credential_status = "error"
            db.commit()
    db.refresh(ds)
    return ApiResponse(data=_source_public(ds))

@router.post("/sources/peripheral/bootstrap", summary="L14 登记周边系统并可选活库元数据采集（只读）", dependencies=[Depends(require_permission("source:manage"))])
def bootstrap_peripheral_sources(
    collect: bool = Query(True, description="是否立即对各 owner 做 live 元数据采集"),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    from ...services.peripheral_sources import collect_peripheral_metadata, ensure_peripheral_registry

    reg = ensure_peripheral_registry(db)
    out: dict = {"registry": reg, "collect": None}
    if collect:
        out["collect"] = collect_peripheral_metadata(db)
    return ApiResponse(data=out)

@router.delete("/systems/{system_code}", summary="软停用系统（存在引用时禁止物理删除）", dependencies=[Depends(require_permission("source:manage"))])
def delete_system(system_code: str, request: Request, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    sys = db.scalar(select(AssetSystem).where(AssetSystem.system_code == system_code))
    if not sys:
        raise HTTPException(status_code=404)
    refs = db.scalars(select(AssetDataSource).where(AssetDataSource.system_code == system_code)).all()
    table_refs = db.scalar(select(func.count()).where(AssetTable.system_code == system_code)) or 0
    if refs or table_refs:
        # soft deactivate only; never cascade-delete connections
        sys.status = "inactive"
        sys.updated_at = datetime.now(timezone.utc)
        for r in refs:
            r.enabled = False
            r.updated_at = datetime.now(timezone.utc)
        _audit(
            db,
            action="soft_disable_system",
            operator=get_current_user(request),
            entity_ref=system_code,
            after={"status": "inactive", "connections": len(refs), "tables": int(table_refs)},
        )
        db.commit()
        return ApiResponse(data={
            "system_code": system_code,
            "action": "soft_disabled",
            "connections": len(refs),
            "tables": int(table_refs),
        })
    sys.status = "inactive"
    sys.updated_at = datetime.now(timezone.utc)
    db.commit()
    return ApiResponse(data={"system_code": system_code, "action": "soft_disabled", "connections": 0})


# ── 数据源 ──
