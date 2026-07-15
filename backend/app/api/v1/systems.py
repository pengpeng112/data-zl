from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, SecretStr, field_validator

from ...core.db import get_db
from ...models.asset import AssetTable, AssetColumn
from ...models.asset_system import AssetDataSource, AssetSystem
from ...models.governance_base import GovernAuditLog
from ...schemas.common import ApiResponse
from ...core.security import get_current_user, require_permission
from ...services import credential_store
from ...services.connection_identity import (
    ALLOWED_DB_TYPES,
    ODS_ALIAS_SOURCES,
    build_connection_identity_key,
    build_database_key,
    build_endpoint_key,
    default_port,
    host_masked_from_target,
    validate_connection_fields,
)
from ...services.ops_event_log import log_event

router = APIRouter(prefix="/api/v1", tags=["systems"])


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


class DataSourceUpsert(BaseModel):
    system_code: str
    source_code: str
    source_name_cn: str
    db_type: str | None = None
    host_masked: str | None = None
    target_host: str | None = Field(default=None, max_length=255)
    port: int | None = None
    service_mode: str | None = None
    service_name: str | None = None
    database_name: str | None = None
    default_schema: str | None = None
    connection_mode: str | None = None
    environment: str | None = None
    collect_mode: str | None = "metadata_only"
    display_order: int = 0
    write_policy: str = "readonly"
    connection_options: dict[str, Any] | None = None
    # legacy: allow explicit credential_ref; preferred path is username/password store
    credential_ref: str | None = None
    write_credential_ref: str | None = None
    description_cn: str | None = None
    enabled: bool = True
    username: str | None = None
    password: SecretStr | None = None


class CredentialUpdate(BaseModel):
    """Write username/password into credential store; password never echoed."""
    username: str = Field(..., min_length=1, max_length=200)
    password: SecretStr = Field(...)
    # optional legacy override; ignored when username/password present
    credential_ref: str | None = Field(default=None, max_length=500)


class SourcePatch(BaseModel):
    source_name_cn: str | None = None
    target_host: str | None = None
    port: int | None = None
    service_mode: str | None = None
    service_name: str | None = None
    database_name: str | None = None
    default_schema: str | None = None
    connection_mode: str | None = None
    environment: str | None = None
    collect_mode: str | None = None
    display_order: int | None = None
    write_policy: str | None = None
    connection_options: dict[str, Any] | None = None
    description_cn: str | None = None
    enabled: bool | None = None
    db_type: str | None = None


def _source_public(r: AssetDataSource) -> dict:
    kind = getattr(r, "source_kind", None) or "physical_connection"
    return {
        "id": r.id,
        "system_code": r.system_code,
        "source_code": r.source_code,
        "source_name_cn": r.source_name_cn,
        "db_type": r.db_type,
        "db_type_label": {
            "oracle": "Oracle",
            "mysql": "MySQL",
            "sqlserver": "SQL Server",
            "vastbase": "海量数据库（Vastbase）",
            "postgresql": "PostgreSQL",
        }.get((r.db_type or "").lower(), r.db_type),
        "environment": r.environment,
        "target_host": r.target_host,
        "host_masked": r.host_masked,
        "port": r.port,
        "service_mode": r.service_mode,
        "service_name": r.service_name,
        "database_name": r.database_name,
        "default_schema": r.default_schema,
        "display_order": r.display_order or 0,
        "connection_mode": r.connection_mode,
        "collect_mode": r.collect_mode,
        "write_policy": r.write_policy or "readonly",
        "connection_options": r.connection_options,
        "enabled": r.enabled,
        "last_check_status": r.last_check_status,
        "last_check_at": r.last_check_at.isoformat() if r.last_check_at else None,
        "credential_configured": bool(r.credential_ref) or credential_store.status(r.source_code) == "configured",
        "credential_status": r.credential_status,
        "credential_username_masked": r.credential_username_masked,
        "credential_updated_at": r.credential_updated_at.isoformat() if r.credential_updated_at else None,
        "credential_updated_by": r.credential_updated_by,
        "connection_identity_key": r.connection_identity_key,
        "endpoint_key": getattr(r, "endpoint_key", None),
        "database_key": getattr(r, "database_key", None),
        "source_kind": kind,
        "canonical_source_code": getattr(r, "canonical_source_code", None),
        "business_labels": getattr(r, "business_labels", None) or [],
        "metadata_origin": getattr(r, "metadata_origin", None),
        "last_test_status": getattr(r, "last_test_status", None) or r.last_check_status,
        "last_test_at": (
            r.last_test_at.isoformat()
            if getattr(r, "last_test_at", None)
            else (r.last_check_at.isoformat() if r.last_check_at else None)
        ),
        "last_test_latency_ms": getattr(r, "last_test_latency_ms", None),
        "last_test_error_code": getattr(r, "last_test_error_code", None),
        "last_test_error_masked": getattr(r, "last_test_error_masked", None),
        "last_collect_status": getattr(r, "last_collect_status", None),
        "last_collect_at": r.last_collect_at.isoformat() if getattr(r, "last_collect_at", None) else None,
        "is_writeable": (r.write_policy or "readonly") == "platform_controlled"
        and (r.system_code or "").upper() in {"ASSET_PLATFORM", "PLATFORM"},
        "is_legacy_alias": kind == "legacy_alias",
        # never expose credential_ref or password
    }


def _apply_connection_meta(ds: AssetDataSource, payload: dict[str, Any], system_code: str) -> list[str]:
    data = {
        "db_type": payload.get("db_type") or ds.db_type,
        "target_host": payload.get("target_host") if payload.get("target_host") is not None else ds.target_host,
        "port": payload.get("port") if payload.get("port") is not None else ds.port,
        "service_mode": payload.get("service_mode") if payload.get("service_mode") is not None else ds.service_mode,
        "service_name": payload.get("service_name") if payload.get("service_name") is not None else ds.service_name,
        "database_name": payload.get("database_name") if payload.get("database_name") is not None else ds.database_name,
        "write_policy": payload.get("write_policy") or ds.write_policy or "readonly",
        "system_code": system_code,
    }
    if data["port"] is None and data["db_type"]:
        data["port"] = default_port(data["db_type"])
    errors = validate_connection_fields(data)
    if errors:
        return errors
    ds.db_type = (data["db_type"] or "").lower()
    ds.target_host = data["target_host"]
    ds.port = int(data["port"])
    ds.service_mode = data.get("service_mode")
    ds.service_name = data.get("service_name")
    ds.database_name = data.get("database_name")
    ds.write_policy = data["write_policy"]
    ds.host_masked = host_masked_from_target(ds.target_host) or ds.host_masked
    ds.connection_identity_key = build_connection_identity_key(
        ds.db_type, ds.target_host, ds.port, ds.service_name, ds.database_name, ds.service_mode
    )
    ds.endpoint_key = build_endpoint_key(ds.db_type, ds.target_host, ds.port)
    ds.database_key = build_database_key(
        ds.db_type, ds.target_host, ds.port, ds.service_name, ds.database_name, ds.service_mode
    )
    alias = ODS_ALIAS_SOURCES.get(ds.source_code)
    if alias:
        ds.source_kind = "legacy_alias"
        ds.canonical_source_code = alias["canonical"]
        ds.business_labels = alias["labels"]
    elif not getattr(ds, "source_kind", None):
        ds.source_kind = "physical_connection"
    return []


def _audit(db: Session, *, action: str, operator: str, entity_ref: str, before=None, after=None, reason=None):
    db.add(GovernAuditLog(
        module="systems",
        entity_type="asset_data_source",
        entity_ref=entity_ref,
        action=action,
        operator=operator,
        before_data=before,
        after_data=after,
        reason=reason,
    ))


# ── 系统 ──

@router.get("/systems", summary="系统列表")
def list_systems(
    include_merged: bool = Query(False),
    db: Session = Depends(get_db),
) -> ApiResponse[list[dict]]:
    rows = db.scalars(select(AssetSystem).order_by(AssetSystem.system_code)).all()
    source_counts = {
        sc: cnt
        for sc, cnt in db.execute(
            select(AssetDataSource.system_code, func.count()).group_by(AssetDataSource.system_code)
        ).all()
    }
    table_counts = {
        sc: cnt
        for sc, cnt in db.execute(
            select(AssetTable.system_code, func.count()).group_by(AssetTable.system_code)
        ).all()
    }
    items = []
    for r in rows:
        if not include_merged and (r.status or "").lower() in {"merged", "deleted"}:
            continue
        items.append({
            "id": r.id,
            "system_code": r.system_code,
            "system_name_cn": r.system_name_cn,
            "system_type": r.system_type,
            "status": r.status,
            "target_host": r.target_host,
            "connection_count": int(source_counts.get(r.system_code, 0) or 0),
            "table_count": int(table_counts.get(r.system_code, 0) or 0),
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })
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
    summary="组合创建系统与一个或多个数据库连接",
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


@router.post("/sources/peripheral/bootstrap", summary="L14 登记周边系统并可选活库元数据采集（只读）")
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

@router.get("/sources", summary="数据源列表")
def list_sources(
    system_code: str | None = Query(None),
    db: Session = Depends(get_db),
) -> ApiResponse[list[dict]]:
    stmt = select(AssetDataSource)
    if system_code:
        stmt = stmt.where(AssetDataSource.system_code == system_code)
    rows = db.scalars(
        stmt.order_by(AssetDataSource.display_order, AssetDataSource.source_code)
    ).all()
    return ApiResponse(data=[_source_public(r) for r in rows])


@router.put("/sources", summary="新增/更新数据源", dependencies=[Depends(require_permission("source:manage"))])
def upsert_source(req: DataSourceUpsert, request: Request, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    operator = get_current_user(request)
    sys = db.scalar(select(AssetSystem).where(AssetSystem.system_code == req.system_code))
    if not sys:
        raise HTTPException(status_code=400, detail=f"系统 {req.system_code} 不存在，请先创建系统")
    existing = db.scalar(select(AssetDataSource).where(AssetDataSource.source_code == req.source_code))
    payload = {
        "db_type": req.db_type,
        "target_host": req.target_host,
        "port": req.port,
        "service_mode": req.service_mode,
        "service_name": req.service_name,
        "database_name": req.database_name,
        "write_policy": req.write_policy or "readonly",
        "system_code": req.system_code,
    }
    # only validate full connection when creating or when core fields provided
    if not existing or req.db_type or req.target_host:
        if payload["port"] is None and payload["db_type"]:
            payload["port"] = default_port(payload["db_type"])
        if existing and not payload["db_type"]:
            payload["db_type"] = existing.db_type
        if existing and not payload["target_host"]:
            payload["target_host"] = existing.target_host
        if existing and payload["port"] is None:
            payload["port"] = existing.port
        if existing and not payload.get("service_name"):
            payload["service_name"] = existing.service_name
        if existing and not payload.get("database_name"):
            payload["database_name"] = existing.database_name
        if existing and not payload.get("service_mode"):
            payload["service_mode"] = existing.service_mode
        if payload.get("db_type") and payload.get("target_host"):
            errors = validate_connection_fields(payload)
            if errors:
                raise HTTPException(status_code=400, detail="; ".join(errors))

    identity = None
    if payload.get("db_type") and payload.get("target_host"):
        identity = build_connection_identity_key(
            payload["db_type"], payload["target_host"], payload.get("port"),
            payload.get("service_name"), payload.get("database_name"), payload.get("service_mode"),
        )
        conflict = db.scalar(
            select(AssetDataSource).where(
                AssetDataSource.connection_identity_key == identity,
                AssetDataSource.source_code != req.source_code,
            )
        )
        if conflict:
            raise HTTPException(status_code=409, detail=f"connection identity conflict with {conflict.source_code}")

    if existing:
        existing.system_code = req.system_code
        existing.source_name_cn = req.source_name_cn
        if req.db_type is not None:
            existing.db_type = req.db_type
        if req.target_host is not None:
            existing.target_host = req.target_host
            existing.host_masked = req.host_masked or host_masked_from_target(req.target_host)
        if req.port is not None:
            existing.port = req.port
        if req.service_mode is not None:
            existing.service_mode = req.service_mode
        if req.service_name is not None:
            existing.service_name = req.service_name
        if req.database_name is not None:
            existing.database_name = req.database_name
        if req.default_schema is not None:
            existing.default_schema = req.default_schema
        if req.connection_mode is not None:
            existing.connection_mode = req.connection_mode
        if req.environment is not None:
            existing.environment = req.environment
        if req.collect_mode is not None:
            existing.collect_mode = req.collect_mode
        existing.display_order = req.display_order
        if req.write_policy:
            existing.write_policy = req.write_policy
        if req.connection_options is not None:
            existing.connection_options = req.connection_options
        # legacy credential_ref only if no password path
        if req.credential_ref and not (req.username and req.password):
            existing.credential_ref = req.credential_ref
            existing.credential_status = "configured"
        if req.write_credential_ref is not None:
            existing.write_credential_ref = req.write_credential_ref
        existing.description_cn = req.description_cn
        existing.enabled = req.enabled
        if identity:
            existing.connection_identity_key = identity
        existing.updated_at = datetime.now(timezone.utc)
        ds = existing
    else:
        ds = AssetDataSource(
            system_code=req.system_code,
            source_code=req.source_code,
            source_name_cn=req.source_name_cn,
            db_type=req.db_type,
            host_masked=req.host_masked or host_masked_from_target(req.target_host),
            target_host=req.target_host,
            port=req.port if req.port is not None else default_port(req.db_type),
            service_mode=req.service_mode,
            service_name=req.service_name,
            database_name=req.database_name,
            default_schema=req.default_schema,
            connection_mode=req.connection_mode,
            environment=req.environment,
            collect_mode=req.collect_mode or "metadata_only",
            display_order=req.display_order,
            write_policy=req.write_policy or "readonly",
            connection_options=req.connection_options,
            credential_ref=req.credential_ref if not (req.username and req.password) else None,
            write_credential_ref=req.write_credential_ref,
            description_cn=req.description_cn,
            enabled=req.enabled,
            connection_identity_key=identity,
            credential_status="configured" if req.credential_ref else "unconfigured",
        )
        db.add(ds)

    if req.username and req.password is not None:
        try:
            ref = credential_store.store(
                req.source_code, req.username, req.password.get_secret_value(), activate=True
            )
            ds.credential_ref = ref
            ds.credential_status = "configured"
            ds.credential_username_masked = credential_store.mask_username(req.username)
            ds.credential_updated_at = datetime.now(timezone.utc)
            ds.credential_updated_by = operator
        except credential_store.CredentialStoreError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    _audit(db, action="upsert_source", operator=operator, entity_ref=req.source_code,
           after={"system_code": req.system_code, "source_code": req.source_code})
    db.commit()
    db.refresh(ds)
    return ApiResponse(data={"id": ds.id, "source_code": ds.source_code})


@router.patch("/sources/{source_code}", summary="更新连接元数据", dependencies=[Depends(require_permission("source:manage"))])
def patch_source(source_code: str, req: SourcePatch, request: Request, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    ds = db.scalar(select(AssetDataSource).where(AssetDataSource.source_code == source_code))
    if not ds:
        raise HTTPException(status_code=404)
    data = req.model_dump(exclude_unset=True)
    if "db_type" in data or "target_host" in data or "port" in data or "service_name" in data or "database_name" in data:
        payload = {
            "db_type": data.get("db_type", ds.db_type),
            "target_host": data.get("target_host", ds.target_host),
            "port": data.get("port", ds.port),
            "service_mode": data.get("service_mode", ds.service_mode),
            "service_name": data.get("service_name", ds.service_name),
            "database_name": data.get("database_name", ds.database_name),
            "write_policy": data.get("write_policy", ds.write_policy or "readonly"),
            "system_code": ds.system_code,
        }
        errors = validate_connection_fields(payload)
        if errors:
            raise HTTPException(status_code=400, detail="; ".join(errors))
        identity = build_connection_identity_key(
            payload["db_type"], payload["target_host"], payload["port"],
            payload.get("service_name"), payload.get("database_name"), payload.get("service_mode"),
        )
        conflict = db.scalar(
            select(AssetDataSource).where(
                AssetDataSource.connection_identity_key == identity,
                AssetDataSource.source_code != source_code,
            )
        )
        if conflict:
            raise HTTPException(status_code=409, detail=f"connection identity conflict with {conflict.source_code}")
        ds.connection_identity_key = identity
        ds.host_masked = host_masked_from_target(payload["target_host"])
    for key, value in data.items():
        setattr(ds, key, value)
    ds.updated_at = datetime.now(timezone.utc)
    _audit(db, action="patch_source", operator=get_current_user(request), entity_ref=source_code, after=list(data.keys()))
    db.commit()
    db.refresh(ds)
    return ApiResponse(data=_source_public(ds))


@router.post("/sources/{source_code}/check", summary="数据源连通性检测")
def check_source(source_code: str, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    ds = db.scalar(select(AssetDataSource).where(AssetDataSource.source_code == source_code))
    if not ds:
        raise HTTPException(status_code=404)

    try:
        from ...services.db_connectors import DB_CONNECTOR_MAP
        from ...services.credentials import resolve
        user, pwd = resolve(ds.credential_ref)
        connector_cls = DB_CONNECTOR_MAP.get((ds.db_type or "oracle").lower())
        if not connector_cls:
            ds.last_check_status = "unsupported"
            ds.last_check_at = datetime.now(timezone.utc)
            db.commit()
            return ApiResponse(data={
                "source_code": ds.source_code,
                "status": "unsupported",
                "message": f"不支持的数据库类型: {ds.db_type}",
            })

        # prefer real target_host; fall back to host_masked for legacy rows
        host = (ds.target_host or ds.host_masked or "localhost").strip()
        database = ds.database_name or ds.service_name or ""
        connector = connector_cls(
            host=host,
            port=ds.port or default_port(ds.db_type),
            database=database,
            user=user or "",
            password=pwd or "",
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
            "target_host": host,
        })
    except Exception as e:
        ds.last_check_status = "failed"
        ds.last_check_at = datetime.now(timezone.utc)
        db.commit()
        # never echo secrets from exception text beyond short generic message
        safe_msg = str(e)[:200]
        for secret_marker in ("password", "pwd=", "passwd"):
            if secret_marker in safe_msg.lower():
                safe_msg = "connectivity check failed"
                break
        return ApiResponse(data={
            "source_code": ds.source_code,
            "status": "failed",
            "message": safe_msg,
            "elapsed_ms": 0,
        })


@router.delete("/sources/{source_code}", summary="禁用数据源（软删除）", dependencies=[Depends(require_permission("source:manage"))])
def delete_source(source_code: str, request: Request, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    ds = db.scalar(select(AssetDataSource).where(AssetDataSource.source_code == source_code))
    if not ds:
        raise HTTPException(status_code=404)
    ds.enabled = False
    ds.updated_at = datetime.now(timezone.utc)
    _audit(db, action="disable_source", operator=get_current_user(request), entity_ref=source_code)
    db.commit()
    return ApiResponse(data={"source_code": source_code, "action": "disabled"})


@router.get("/sources/{source_code}", summary="数据源详情（凭据脱敏）")
def get_source(source_code: str, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    ds = db.scalar(select(AssetDataSource).where(AssetDataSource.source_code == source_code))
    if not ds:
        raise HTTPException(status_code=404)
    return ApiResponse(data=_source_public(ds))


@router.put(
    "/sources/{source_code}/credential",
    dependencies=[Depends(require_permission("source:credential_manage"))],
    summary="写入/轮换凭据（密码只写不回显）",
)
def update_source_credential(
    source_code: str,
    req: CredentialUpdate,
    request: Request,
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    operator = get_current_user(request)
    ds = db.scalar(select(AssetDataSource).where(AssetDataSource.source_code == source_code))
    if not ds:
        raise HTTPException(status_code=404)
    # business sources: only readonly credentials from this endpoint
    if (ds.write_policy or "readonly") != "readonly" and (ds.system_code or "").upper() not in {
        "ASSET_PLATFORM", "PLATFORM",
    }:
        raise HTTPException(status_code=400, detail="business sources only accept readonly credentials")
    try:
        ref = credential_store.rotate(
            source_code,
            req.username,
            req.password.get_secret_value(),
            writable=False,
        )
    except credential_store.CredentialStoreError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    ds.credential_ref = ref
    ds.credential_status = "configured"
    ds.credential_username_masked = credential_store.mask_username(req.username)
    ds.credential_updated_at = datetime.now(timezone.utc)
    ds.credential_updated_by = operator
    _audit(
        db,
        action="credential_rotate",
        operator=operator,
        entity_ref=source_code,
        after={
            "credential_status": "configured",
            "credential_username_masked": ds.credential_username_masked,
        },
    )
    db.commit()
    return ApiResponse(data={
        "source_code": source_code,
        "credential_configured": True,
        "credential_status": ds.credential_status,
        "credential_username_masked": ds.credential_username_masked,
        "updated_by": operator,
    })


@router.delete(
    "/sources/{source_code}/credential",
    dependencies=[Depends(require_permission("source:credential_manage"))],
    summary="删除凭据文件并清除引用",
)
def clear_source_credential(source_code: str, request: Request, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    operator = get_current_user(request)
    ds = db.scalar(select(AssetDataSource).where(AssetDataSource.source_code == source_code))
    if not ds:
        raise HTTPException(status_code=404)
    try:
        credential_store.delete(source_code)
    except credential_store.CredentialStoreError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    ds.credential_ref = None
    ds.credential_status = "unconfigured"
    ds.credential_username_masked = None
    ds.credential_updated_at = datetime.now(timezone.utc)
    ds.credential_updated_by = operator
    _audit(db, action="credential_delete", operator=operator, entity_ref=source_code,
           after={"credential_status": "unconfigured"})
    db.commit()
    return ApiResponse(data={
        "source_code": source_code,
        "credential_configured": False,
        "credential_status": ds.credential_status,
        "updated_by": operator,
    })


@router.get("/db-types", summary="支持的数据库类型与字段规则")
def list_db_types() -> ApiResponse[list[dict]]:
    labels = {
        "oracle": "Oracle",
        "mysql": "MySQL",
        "sqlserver": "SQL Server",
        "vastbase": "海量数据库（Vastbase）",
        "postgresql": "PostgreSQL",
    }
    items = []
    for code, meta in ALLOWED_DB_TYPES.items():
        items.append({
            "db_type": code,
            "label": labels[code],
            "default_port": meta["default_port"],
            "service_modes": sorted(meta["service_modes"]),
            "requires_database_name": code != "oracle",
            "requires_service_or_sid": code == "oracle",
        })
    return ApiResponse(data=items)


# ── 物理连接视图与 draft 测试（plan 76）──


class ConnectionDraftTest(BaseModel):
    db_type: str
    target_host: str
    port: int | None = None
    service_mode: str | None = None
    service_name: str | None = None
    database_name: str | None = None
    connection_mode: str | None = "direct"
    username: str | None = None
    password: SecretStr | None = None
    timeout_ms: int = 10000


def _run_connectivity_test(
    *,
    db_type: str,
    host: str,
    port: int,
    database: str,
    user: str,
    password: str,
    connection_mode: str,
    timeout_ms: int = 10000,
) -> dict:
    from ...services.db_connectors import DB_CONNECTOR_MAP

    connector_cls = DB_CONNECTOR_MAP.get((db_type or "oracle").lower())
    if not connector_cls:
        return {
            "success": False,
            "error_code": "unsupported_db_type",
            "error_masked": f"unsupported db_type: {db_type}",
            "latency_ms": 0,
            "server_version": None,
        }
    connector = connector_cls(
        host=host,
        port=port,
        database=database,
        user=user or "",
        password=password or "",
        connection_mode=connection_mode or "direct",
        timeout_ms=timeout_ms,
    )
    ok, msg, elapsed_ms = connector.test_connectivity()
    safe_msg = (msg or "")[:200]
    for marker in ("password", "pwd=", "passwd", user or "___"):
        if marker and marker.lower() in safe_msg.lower() and marker not in ("", "___"):
            safe_msg = "connectivity check failed"
            break
    return {
        "success": bool(ok),
        "error_code": None if ok else "connect_failed",
        "error_masked": None if ok else safe_msg,
        "latency_ms": int(elapsed_ms or 0),
        "server_version": None,
        "message": "ok" if ok else safe_msg,
    }


@router.get("/connections", summary="物理连接列表（按 database_key 去重，别名折叠）")
def list_connections(
    include_aliases: bool = Query(False),
    db: Session = Depends(get_db),
) -> ApiResponse[list[dict]]:
    rows = db.scalars(
        select(AssetDataSource).order_by(AssetDataSource.display_order, AssetDataSource.source_code)
    ).all()
    physical = []
    aliases_by_canonical: dict[str, list[dict]] = {}
    for r in rows:
        pub = _source_public(r)
        if (r.source_kind or "physical_connection") == "legacy_alias" and r.canonical_source_code:
            aliases_by_canonical.setdefault(r.canonical_source_code, []).append(pub)
            if include_aliases:
                physical.append(pub)
            continue
        physical.append(pub)
    # attach alias summaries
    for item in physical:
        if item.get("is_legacy_alias"):
            continue
        item["aliases"] = aliases_by_canonical.get(item["source_code"], [])
        # schema/table counts under this source (and aliases map to canonical for assets)
        codes = [item["source_code"]] + [a["source_code"] for a in item["aliases"]]
        t_cnt = db.scalar(
            select(func.count()).where(AssetTable.source_code.in_(codes))
        ) or 0
        s_cnt = db.scalar(
            select(func.count(func.distinct(func.coalesce(AssetTable.schema_name, AssetTable.namespace_name, ""))))
            .where(AssetTable.source_code.in_(codes))
        ) or 0
        item["table_count"] = int(t_cnt)
        item["schema_count"] = int(s_cnt)
    return ApiResponse(data=physical)


@router.get("/connections/{connection_id}", summary="连接详情（脱敏）")
def get_connection(connection_id: int, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    ds = db.get(AssetDataSource, connection_id)
    if not ds:
        raise HTTPException(status_code=404)
    data = _source_public(ds)
    aliases = db.scalars(
        select(AssetDataSource).where(AssetDataSource.canonical_source_code == ds.source_code)
    ).all()
    data["aliases"] = [_source_public(a) for a in aliases]
    schemas = db.execute(
        select(
            func.coalesce(AssetTable.schema_name, AssetTable.namespace_name, "").label("schema_name"),
            func.count().label("table_count"),
        )
        .where(AssetTable.source_code == ds.source_code)
        .group_by(func.coalesce(AssetTable.schema_name, AssetTable.namespace_name, ""))
        .order_by(func.coalesce(AssetTable.schema_name, AssetTable.namespace_name, ""))
    ).all()
    data["schemas"] = [{"schema_name": s or "(default)", "table_count": int(c)} for s, c in schemas]
    return ApiResponse(data=data)


@router.post("/connections/test-draft", summary="测试未保存连接（密码不落库）")
def test_connection_draft(req: ConnectionDraftTest) -> ApiResponse[dict]:
    port = req.port if req.port is not None else default_port(req.db_type)
    errors = validate_connection_fields({
        "db_type": req.db_type,
        "target_host": req.target_host,
        "port": port,
        "service_mode": req.service_mode,
        "service_name": req.service_name,
        "database_name": req.database_name,
        "write_policy": "readonly",
        "system_code": "DRAFT",
    })
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    database = req.database_name or req.service_name or ""
    pwd = req.password.get_secret_value() if req.password else ""
    result = _run_connectivity_test(
        db_type=req.db_type,
        host=req.target_host,
        port=port,
        database=database,
        user=req.username or "",
        password=pwd,
        connection_mode=req.connection_mode or "direct",
        timeout_ms=req.timeout_ms,
    )
    endpoint = build_endpoint_key(req.db_type, req.target_host, port)
    return ApiResponse(data={
        "success": result["success"],
        "db_type": req.db_type,
        "endpoint_masked": host_masked_from_target(req.target_host) + f":{port}",
        "endpoint_key": endpoint,
        "database_or_service": database,
        "server_version": result.get("server_version"),
        "latency_ms": result["latency_ms"],
        "error_code": result.get("error_code"),
        "error_masked": result.get("error_masked"),
        "tested_at": datetime.now(timezone.utc).isoformat(),
    })


@router.post("/connections/{connection_id}/test", summary="测试已保存连接")
def test_saved_connection(connection_id: int, request: Request, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    operator = get_current_user(request)
    ds = db.get(AssetDataSource, connection_id)
    if not ds:
        raise HTTPException(status_code=404)
    from ...services.credentials import resolve
    user, pwd = resolve(ds.credential_ref)
    host = (ds.target_host or ds.host_masked or "").strip()
    if not host or "*" in host:
        raise HTTPException(status_code=400, detail="target_host is missing; run backfill first")
    port = ds.port or default_port(ds.db_type)
    database = ds.database_name or ds.service_name or ""
    started = datetime.now(timezone.utc)
    result = _run_connectivity_test(
        db_type=ds.db_type or "oracle",
        host=host,
        port=port,
        database=database,
        user=user or "",
        password=pwd or "",
        connection_mode=ds.connection_mode or "direct",
    )
    ds.last_test_status = "connected" if result["success"] else "failed"
    ds.last_test_at = datetime.now(timezone.utc)
    ds.last_test_latency_ms = result["latency_ms"]
    ds.last_test_error_code = result.get("error_code")
    ds.last_test_error_masked = result.get("error_masked")
    ds.last_check_status = ds.last_test_status
    ds.last_check_at = ds.last_test_at
    log_event(
        db,
        module="connection",
        entity_type="asset_data_source",
        entity_ref=ds.source_code,
        action="test_success" if result["success"] else "test_failed",
        operator=operator,
        status=ds.last_test_status,
        target_connection_id=ds.id,
        target_database_key=ds.database_key,
        target_source_code=ds.source_code,
        duration_ms=result["latency_ms"],
        error_code=result.get("error_code"),
        summary_masked=result.get("error_masked") or "ok",
        started_at=started,
    )
    db.commit()
    return ApiResponse(data={
        "success": result["success"],
        "db_type": ds.db_type,
        "endpoint_masked": f"{ds.host_masked or host_masked_from_target(host)}:{port}",
        "database_or_service": database,
        "latency_ms": result["latency_ms"],
        "error_code": result.get("error_code"),
        "error_masked": result.get("error_masked"),
        "tested_at": ds.last_test_at.isoformat(),
        "source_code": ds.source_code,
    })


@router.get("/connections-targets", summary="运维目标数据库列表（含写能力标记）")
def list_connection_targets(db: Session = Depends(get_db)) -> ApiResponse[list[dict]]:
    """Platform asset is always first writable target; business sources are readonly."""
    items = [{
        "id": None,
        "source_code": "asset",
        "label": "平台库 / data_asset / asset",
        "db_type": "postgresql",
        "endpoint_masked": "platform",
        "database_or_service": "data_asset",
        "write_allowed": True,
        "write_policy": "platform_controlled",
        "readonly_reason": None,
        "target_scope": "platform_asset",
        "database_key": "postgresql://platform/database/data_asset",
    }]
    rows = db.scalars(
        select(AssetDataSource)
        .where(AssetDataSource.enabled.is_(True))
        .where((AssetDataSource.source_kind.is_(None)) | (AssetDataSource.source_kind != "legacy_alias"))
        .order_by(AssetDataSource.source_code)
    ).all()
    for r in rows:
        write_allowed = (r.write_policy or "readonly") == "platform_controlled" and (r.system_code or "").upper() in {
            "ASSET_PLATFORM", "PLATFORM",
        }
        items.append({
            "id": r.id,
            "source_code": r.source_code,
            "label": f"{r.source_name_cn} ({r.source_code})",
            "db_type": r.db_type,
            "endpoint_masked": f"{r.host_masked or host_masked_from_target(r.target_host) or '-'}:{r.port or '-'}",
            "database_or_service": r.service_name or r.database_name,
            "write_allowed": write_allowed,
            "write_policy": r.write_policy or "readonly",
            "readonly_reason": None if write_allowed else "业务源库只读，禁止 INSERT/UPDATE",
            "target_scope": "platform_asset" if write_allowed else "business_readonly",
            "database_key": r.database_key,
            "business_labels": r.business_labels or [],
        })
    return ApiResponse(data=items)


# ── 资产树（五层：系统大类 -> 系统/库 -> schema -> 表 -> 字段） ──

_CATEGORY_CN = {
    "ods_center": "ODS 数据中心系统",
    "his_source": "HIS 源端系统",
    "hrp_source": "HRP 源端系统",
    "external_business": "其他业务系统",
    "platform_asset": "平台元数据系统",
}

_SOURCE_SYSTEM_CN = {
    "ods_his": "HIS 抽取区",
    "ods_lis": "LIS 抽取区",
    "ods_pacs": "PACS 抽取区",
    "ods_emr": "EMR/病历抽取区",
    "ods_ydhl": "移动护理抽取区",
    "ods_sm": "手麻抽取区",
    "ods_cda": "CDA/标准字典区",
    "ods_other": "其他抽取区",
    "his_prod": "HIS 业务库",
    "hrp": "HRP 源端",
    "lis": "检验 LIS",
    "pacs": "影像 PACS",
    "emr": "电子病历",
    "mobile_nursing": "移动护理",
    "sm": "手麻",
    "platform": "平台 asset",
}


def _classify_asset_source(system_code: str | None, source_code: str | None) -> tuple[str, str, str, str]:
    """Return (system_category, category_cn, source_system, source_system_cn)."""
    sc = (system_code or "").upper()
    src = (source_code or "").lower()

    if sc == "HIS_SOURCE" or "his_source" in src or src.startswith("his_"):
        return "his_source", _CATEGORY_CN["his_source"], "his_prod", _SOURCE_SYSTEM_CN["his_prod"]
    if sc == "HRP" or "hrp" in src:
        return "hrp_source", _CATEGORY_CN["hrp_source"], "hrp", _SOURCE_SYSTEM_CN["hrp"]
    if sc == "LIS" or src.endswith("_lis") or src == "ods_lis":
        return "ods_center", _CATEGORY_CN["ods_center"], "owner_lis", "数据中心 / LIS Owner"
    if sc == "PACS" or src.endswith("_pacs") or src == "ods_pacs":
        return "ods_center", _CATEGORY_CN["ods_center"], "owner_pacs", "数据中心 / PACS Owner"
    if sc == "EMR" or src.endswith("_emr") or src == "ods_emr":
        return "ods_center", _CATEGORY_CN["ods_center"], "owner_emr", "数据中心 / EMR Owner"
    if sc in ("MOBILE_NURSING", "YDHL") or "ydhl" in src:
        return "ods_center", _CATEGORY_CN["ods_center"], "owner_ydhl", "数据中心 / 移动护理 Owner"
    if sc == "SM" or src.endswith("_sm") or src == "ods_sm":
        return "ods_center", _CATEGORY_CN["ods_center"], "owner_sm", "数据中心 / 手麻 Owner"
    if sc == "DATA_CENTER" or src.startswith("ods") or "8_216" in src:
        if "cda" in src:
            return "ods_center", _CATEGORY_CN["ods_center"], "ods_cda", _SOURCE_SYSTEM_CN["ods_cda"]
        # 主 ODS 汇聚源：按表 namespace 在前端再分；树节点先标 his 抽取区为主入口
        if src in ("ods_8_216",) or "ods" in src:
            return "ods_center", _CATEGORY_CN["ods_center"], "ods_his", _SOURCE_SYSTEM_CN["ods_his"]
        return "ods_center", _CATEGORY_CN["ods_center"], "ods_other", _SOURCE_SYSTEM_CN["ods_other"]
    return "platform_asset", _CATEGORY_CN["platform_asset"], "platform", _SOURCE_SYSTEM_CN["platform"]


def _table_brief(t: AssetTable) -> dict:
    ns = t.namespace_name or t.schema_name or ""
    return {
        "id": t.id,
        "table_name": t.table_name,
        "table_name_cn": t.table_name_cn,
        "column_count": t.column_count,
        "domain": t.domain,
        "owner_hint": (ns or "").upper(),
        "schema_name": ns,
        "source_code": t.source_code,
        "system_code": t.system_code,
    }


@router.get(
    "/assets/tree",
    summary="系统大类 -> 系统/库 -> schema 树（默认不含表清单，表按需加载）",
)
def assets_tree(
    system_code: str | None = Query(None),
    system_category: str | None = Query(None),
    include_tables: bool = Query(
        False,
        description="true 时内嵌全量表（仅调试/小库）；默认 false 仅返回 schema 计数，表走 /assets/tree/tables",
    ),
    max_tables_per_schema: int = Query(
        0,
        ge=0,
        le=500,
        description="include_tables=true 时每 schema 最多内嵌表数；0 表示不截断",
    ),
    db: Session = Depends(get_db),
) -> ApiResponse[list[dict]]:
    sources_stmt = select(AssetDataSource)
    if system_code:
        sources_stmt = sources_stmt.where(AssetDataSource.system_code == system_code)
    sources = {s.source_code: s for s in db.scalars(sources_stmt).all()}

    # 骨架：仅聚合 (source_code, schema) 计数，避免一次序列化 2000+ 表
    # PG GROUP BY 必须与 SELECT 表达式同一引用（勿重复写两遍 coalesce）
    ns_key = func.coalesce(AssetTable.schema_name, AssetTable.namespace_name, "")
    count_rows = db.execute(
        select(
            AssetTable.source_code,
            ns_key.label("ns"),
            func.count().label("cnt"),
        ).group_by(AssetTable.source_code, ns_key)
    ).all()

    grouped: dict[str, dict[str, int]] = {}
    for sc, ns, cnt in count_rows:
        sc_key = sc or "DATA_CENTER"
        ns_key = ns or ""
        grouped.setdefault(sc_key, {})[ns_key] = int(cnt)

    tables_by_schema: dict[tuple[str, str], list[dict]] = {}
    if include_tables:
        tables = db.scalars(select(AssetTable)).all()
        for t in tables:
            sc = t.source_code or "DATA_CENTER"
            ns = t.namespace_name or t.schema_name or ""
            key = (sc, ns)
            bucket = tables_by_schema.setdefault(key, [])
            if max_tables_per_schema and len(bucket) >= max_tables_per_schema:
                continue
            bucket.append(_table_brief(t))

    tree = []
    for sc, schema_counts in sorted(grouped.items()):
        ds = sources.get(sc)
        sys_code = ds.system_code if ds else "DATA_CENTER"
        cat, cat_cn, src_sys, src_sys_cn = _classify_asset_source(sys_code, sc)
        # 主 ODS 汇聚：按 namespace 拆分到抽取区
        if sc in ("ods_8_216",) or (sys_code == "DATA_CENTER" and "216" in sc):
            by_zone: dict[str, dict[str, int]] = {}
            for ns, cnt in schema_counts.items():
                zone = _ods_owner_zone(ns)
                by_zone.setdefault(zone, {})[ns] = cnt
            for zone, zschemas in sorted(by_zone.items()):
                z_cn = _SOURCE_SYSTEM_CN.get(zone, zone)
                node = {
                    "source_code": sc,
                    "source_name_cn": (ds.source_name_cn if ds else sc) + f" / {z_cn}",
                    "system_code": sys_code,
                    "system_category": cat,
                    "system_category_cn": cat_cn,
                    "source_system": zone,
                    "source_system_cn": z_cn,
                    "schemas": [],
                    "table_count": sum(zschemas.values()),
                    "tables_embedded": include_tables,
                }
                for ns, cnt in sorted(zschemas.items()):
                    tbls = tables_by_schema.get((sc, ns), []) if include_tables else []
                    node["schemas"].append({
                        "namespace": ns,
                        "tables": tbls,
                        "table_count": cnt,
                        "tables_loaded": include_tables,
                    })
                if system_category and node["system_category"] != system_category:
                    continue
                tree.append(node)
            continue

        node = {
            "source_code": sc,
            "source_name_cn": ds.source_name_cn if ds else sc,
            "system_code": sys_code,
            "system_category": cat,
            "system_category_cn": cat_cn,
            "source_system": src_sys,
            "source_system_cn": src_sys_cn,
            "schemas": [],
            "table_count": sum(schema_counts.values()),
            "tables_embedded": include_tables,
        }
        for ns, cnt in sorted(schema_counts.items()):
            tbls = tables_by_schema.get((sc, ns), []) if include_tables else []
            node["schemas"].append({
                "namespace": ns,
                "tables": tbls,
                "table_count": cnt,
                "tables_loaded": include_tables,
            })
        if system_category and node["system_category"] != system_category:
            continue
        tree.append(node)

    return ApiResponse(data=tree)


@router.get("/assets/tree/tables", summary="懒加载：某 source+schema 下的表清单（分页）")
def assets_tree_tables(
    source_code: str = Query(..., min_length=1),
    schema_name: str = Query("", description="Owner/schema；空串表示无 namespace"),
    keyword: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(200, ge=1, le=500),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    ns = schema_name or ""
    ns_key = func.coalesce(AssetTable.schema_name, AssetTable.namespace_name, "")
    stmt = select(AssetTable).where(
        AssetTable.source_code == source_code,
        ns_key == ns,
    )
    if keyword:
        like = f"%{keyword.strip()}%"
        stmt = stmt.where(
            (AssetTable.table_name.ilike(like))
            | (AssetTable.table_name_cn.ilike(like))
            | (AssetTable.domain.ilike(like))
        )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(AssetTable.table_name)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return ApiResponse(
        data={
            "source_code": source_code,
            "schema_name": ns,
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [_table_brief(t) for t in rows],
        }
    )


@router.get("/assets/tree/search", summary="按表名/中文名搜索（返回路径，限量）")
def assets_tree_search(
    keyword: str = Query(..., min_length=1),
    system_category: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    like = f"%{keyword.strip()}%"
    stmt = (
        select(AssetTable)
        .where(
            (AssetTable.table_name.ilike(like))
            | (AssetTable.table_name_cn.ilike(like))
        )
        .order_by(AssetTable.schema_name, AssetTable.table_name)
        .limit(limit)
    )
    rows = db.scalars(stmt).all()
    sources = {
        s.source_code: s
        for s in db.scalars(select(AssetDataSource)).all()
    }
    items = []
    for t in rows:
        sc = t.source_code or "DATA_CENTER"
        ds = sources.get(sc)
        sys_code = ds.system_code if ds else (t.system_code or "DATA_CENTER")
        cat, cat_cn, src_sys, src_sys_cn = _classify_asset_source(sys_code, sc)
        ns = t.namespace_name or t.schema_name or ""
        if sc in ("ods_8_216",) or (sys_code == "DATA_CENTER" and "216" in sc):
            src_sys = _ods_owner_zone(ns)
            src_sys_cn = _SOURCE_SYSTEM_CN.get(src_sys, src_sys)
        if system_category and cat != system_category:
            continue
        items.append({
            **_table_brief(t),
            "system_category": cat,
            "system_category_cn": cat_cn,
            "source_system": src_sys,
            "source_system_cn": src_sys_cn,
            "source_name_cn": ds.source_name_cn if ds else sc,
        })
    return ApiResponse(data={"keyword": keyword, "total": len(items), "items": items})


def _ods_owner_zone(namespace: str) -> str:
    owner = (namespace or "").upper()
    if owner in ("HIS",) or owner.startswith("HIS"):
        return "ods_his"
    if owner == "LIS":
        return "ods_lis"
    if owner == "PACS":
        return "ods_pacs"
    if owner in ("JHEMR", "MTL", "YBEMR"):
        return "ods_emr"
    if owner == "YDHL":
        return "ods_ydhl"
    if owner == "SM":
        return "ods_sm"
    if owner == "CDA":
        return "ods_cda"
    return "ods_other"
