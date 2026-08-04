from datetime import datetime, timezone
import socket
import threading
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, SecretStr, field_validator

from ...core.db import get_db
from ...models.asset import AssetTable, AssetColumn
from ...models.asset_system import AssetDataSource, AssetSourceSchema, AssetSystem
from ...models.governance_base import GovernAuditLog
from ...schemas.common import ApiResponse
from ...core.security import get_current_user, require_permission
from ...core.rate_limit import limiter
from ...services import credential_store
from ...services.data_masking import sanitize_text
from ...services.connection_identity import (
    ALLOWED_DB_TYPES,
    MAX_CONNECTIVITY_TIMEOUT_MS,
    ODS_ALIAS_SOURCES,
    build_connection_identity_key,
    build_database_key,
    build_endpoint_key,
    default_port,
    host_masked_from_target,
    validate_connection_fields,
    validate_ssrf_target,
)
from ...services.ops_event_log import log_event
from ...services.asset_catalog import (
    CANONICAL_SYSTEMS,
    classify_for_tree,
    list_first_level_systems,
    load_system_name_map,
    normalize_system_code,
    owner_display_cn,
)

router = APIRouter(prefix="/api/v1", tags=["systems"])
_CONNECTION_TEST_SLOTS = threading.BoundedSemaphore(value=4)

# Tables with confirmed zero rows must not appear in normal catalog APIs.
_EXCLUDED_PRESENCE = ("confirmed_empty",)


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


ALLOWED_WRITE_POLICIES = {"readonly", "medical_dict_push", "platform_controlled"}


class CredentialUpdate(BaseModel):
    """Write username/password into credential store; password never echoed."""
    username: str = Field(..., min_length=1, max_length=200)
    password: SecretStr = Field(...)
    # readonly: 探库/对账；write: 字典下发等受控写（独立 .write 文件）
    purpose: str = Field(default="readonly", description="readonly | write")
    # 配置写凭据时可选同步写策略（仅 purpose=write 时生效）
    write_policy: str | None = Field(
        default=None,
        description="when purpose=write, optional: medical_dict_push / platform_controlled / readonly",
    )
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
        "write_credential_configured": bool(r.write_credential_ref)
        or credential_store.status(r.source_code, writable=True) == "configured",
        "write_credential_status": (
            "configured"
            if (bool(r.write_credential_ref) or credential_store.status(r.source_code, writable=True) == "configured")
            else "unconfigured"
        ),
        "write_username_masked": (
            (r.connection_options or {}).get("write_username_masked")
            if isinstance(r.connection_options, dict)
            else None
        ),
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
        "is_writeable": (r.write_policy or "readonly") in {"platform_controlled", "medical_dict_push"},
        "supports_medical_dict_push": (r.write_policy or "readonly") == "medical_dict_push"
        and (
            bool(r.write_credential_ref)
            or credential_store.status(r.source_code, writable=True) == "configured"
        ),
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
            raise HTTPException(status_code=400, detail=sanitize_text(str(exc))) from exc

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
    if "write_policy" in data and data["write_policy"] is not None:
        policy = str(data["write_policy"]).strip().lower()
        if policy not in ALLOWED_WRITE_POLICIES:
            raise HTTPException(
                status_code=400,
                detail=f"write_policy must be one of {sorted(ALLOWED_WRITE_POLICIES)}",
            )
        # platform_controlled 仅允许平台自身库；业务源允许 readonly / medical_dict_push
        sys_code = (ds.system_code or "").upper()
        if policy == "platform_controlled" and sys_code not in {"ASSET_PLATFORM", "PLATFORM"}:
            raise HTTPException(
                status_code=400,
                detail="platform_controlled is only allowed for ASSET_PLATFORM",
            )
        data["write_policy"] = policy
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


@router.post("/sources/{source_code}/check", summary="数据源连通性检测", dependencies=[Depends(require_permission("source:manage"))])
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
    summary="写入/轮换凭据（密码只写不回显；支持只读/写账号分离）",
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

    purpose = (req.purpose or "readonly").strip().lower()
    if purpose not in {"readonly", "write"}:
        raise HTTPException(status_code=400, detail="purpose must be readonly or write")

    sys_code = (ds.system_code or "").upper()
    is_platform = sys_code in {"ASSET_PLATFORM", "PLATFORM"}

    if purpose == "readonly":
        # 只读凭据：业务源与平台源均可配置
        try:
            ref = credential_store.rotate(
                source_code,
                req.username,
                req.password.get_secret_value(),
                writable=False,
            )
        except credential_store.CredentialStoreError as exc:
            raise HTTPException(status_code=400, detail=sanitize_text(str(exc))) from exc
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
                "purpose": "readonly",
                "credential_status": "configured",
                "credential_username_masked": ds.credential_username_masked,
            },
        )
        db.commit()
        return ApiResponse(data={
            "source_code": source_code,
            "purpose": "readonly",
            "credential_configured": True,
            "credential_status": ds.credential_status,
            "credential_username_masked": ds.credential_username_masked,
            "write_policy": ds.write_policy or "readonly",
            "updated_by": operator,
        })

    # purpose == write：业务源仅允许 medical_dict_push；平台源允许 platform_controlled
    policy = (req.write_policy or ds.write_policy or "").strip().lower()
    if not policy or policy == "readonly":
        policy = "medical_dict_push" if not is_platform else "platform_controlled"
    if policy not in ALLOWED_WRITE_POLICIES or policy == "readonly":
        raise HTTPException(
            status_code=400,
            detail="write credential requires write_policy medical_dict_push or platform_controlled",
        )
    if policy == "platform_controlled" and not is_platform:
        raise HTTPException(
            status_code=400,
            detail="platform_controlled write credentials only for ASSET_PLATFORM",
        )
    if policy == "medical_dict_push" and is_platform:
        # 平台库不走字典下发写
        raise HTTPException(status_code=400, detail="medical_dict_push is for business sources only")

    try:
        ref = credential_store.rotate(
            source_code,
            req.username,
            req.password.get_secret_value(),
            writable=True,
        )
    except credential_store.CredentialStoreError as exc:
        raise HTTPException(status_code=400, detail=sanitize_text(str(exc))) from exc

    ds.write_credential_ref = ref
    ds.write_policy = policy
    ds.credential_updated_at = datetime.now(timezone.utc)
    ds.credential_updated_by = operator
    # 不覆盖只读用户名脱敏；写账号脱敏放入 connection_options 非密字段
    opts = dict(ds.connection_options or {}) if isinstance(ds.connection_options, dict) else {}
    opts["write_username_masked"] = credential_store.mask_username(req.username)
    opts["write_credential_updated_at"] = datetime.now(timezone.utc).isoformat()
    ds.connection_options = opts

    _audit(
        db,
        action="write_credential_rotate",
        operator=operator,
        entity_ref=source_code,
        after={
            "purpose": "write",
            "write_policy": policy,
            "write_username_masked": opts.get("write_username_masked"),
            "write_credential_configured": True,
        },
    )
    db.commit()
    return ApiResponse(data={
        "source_code": source_code,
        "purpose": "write",
        "write_policy": ds.write_policy,
        "write_credential_configured": True,
        "write_username_masked": opts.get("write_username_masked"),
        "updated_by": operator,
    })


@router.delete(
    "/sources/{source_code}/credential",
    dependencies=[Depends(require_permission("source:credential_manage"))],
    summary="删除凭据文件并清除引用（purpose=readonly|write）",
)
def clear_source_credential(
    source_code: str,
    request: Request,
    db: Session = Depends(get_db),
    purpose: str = Query("readonly", description="readonly | write"),
) -> ApiResponse[dict]:
    operator = get_current_user(request)
    ds = db.scalar(select(AssetDataSource).where(AssetDataSource.source_code == source_code))
    if not ds:
        raise HTTPException(status_code=404)
    purpose_norm = (purpose or "readonly").strip().lower()
    if purpose_norm not in {"readonly", "write"}:
        raise HTTPException(status_code=400, detail="purpose must be readonly or write")

    if purpose_norm == "readonly":
        try:
            credential_store.delete(source_code, writable=False)
        except credential_store.CredentialStoreError as exc:
            raise HTTPException(status_code=400, detail=sanitize_text(str(exc))) from exc
        ds.credential_ref = None
        ds.credential_status = "unconfigured"
        ds.credential_username_masked = None
        ds.credential_updated_at = datetime.now(timezone.utc)
        ds.credential_updated_by = operator
        _audit(
            db,
            action="credential_delete",
            operator=operator,
            entity_ref=source_code,
            after={"purpose": "readonly", "credential_status": "unconfigured"},
        )
        db.commit()
        return ApiResponse(data={
            "source_code": source_code,
            "purpose": "readonly",
            "credential_configured": False,
            "credential_status": ds.credential_status,
            "updated_by": operator,
        })

    try:
        credential_store.delete(source_code, writable=True)
    except credential_store.CredentialStoreError as exc:
        raise HTTPException(status_code=400, detail=sanitize_text(str(exc))) from exc
    ds.write_credential_ref = None
    # 清写凭据后回落只读策略，避免误用只读账号写
    if (ds.write_policy or "") == "medical_dict_push":
        ds.write_policy = "readonly"
    opts = dict(ds.connection_options or {}) if isinstance(ds.connection_options, dict) else {}
    opts.pop("write_username_masked", None)
    opts.pop("write_credential_updated_at", None)
    ds.connection_options = opts or None
    ds.credential_updated_at = datetime.now(timezone.utc)
    ds.credential_updated_by = operator
    _audit(
        db,
        action="write_credential_delete",
        operator=operator,
        entity_ref=source_code,
        after={"purpose": "write", "write_policy": ds.write_policy, "write_credential_configured": False},
    )
    db.commit()
    return ApiResponse(data={
        "source_code": source_code,
        "purpose": "write",
        "write_credential_configured": False,
        "write_policy": ds.write_policy or "readonly",
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

    # 111 号 S5：连接测试防 SSRF —— 协议/端口/目标网段/超时全部受限。
    ssrf_errors = validate_ssrf_target(db_type, host, port)
    if ssrf_errors:
        return {
            "success": False,
            "error_code": "ssrf_blocked",
            "error_masked": "; ".join(ssrf_errors),
            "latency_ms": 0,
            "server_version": None,
        }
    if timeout_ms is None or int(timeout_ms) <= 0:
        timeout_ms = 10000
    timeout_ms = min(int(timeout_ms), MAX_CONNECTIVITY_TIMEOUT_MS)

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


@router.post("/connections/test-draft", summary="测试未保存连接（密码不落库）", dependencies=[Depends(require_permission("source.test"))])
@limiter.limit("10/minute")
def test_connection_draft(request: Request, req: ConnectionDraftTest, db: Session = Depends(get_db)) -> ApiResponse[dict]:
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
    if not _CONNECTION_TEST_SLOTS.acquire(blocking=False):
        raise HTTPException(status_code=429, detail="连接测试繁忙，请稍后重试")
    try:
        result = _run_connectivity_test(db_type=req.db_type, host=req.target_host, port=port,
            database=database, user=req.username or "", password=pwd,
            connection_mode=req.connection_mode or "direct", timeout_ms=req.timeout_ms)
    finally:
        _CONNECTION_TEST_SLOTS.release()
    log_event(db, module="connection", entity_type="draft", entity_ref="unsaved",
              action="test_success" if result["success"] else "test_failed",
              operator=get_current_user(request), status="connected" if result["success"] else "failed",
              duration_ms=result["latency_ms"], error_code=result.get("error_code"),
              summary_masked=result.get("error_masked") or "ok", started_at=datetime.now(timezone.utc))
    db.commit()
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


@router.post("/connections/{connection_id}/test", summary="测试已保存连接", dependencies=[Depends(require_permission("source.test"))])
@limiter.limit("10/minute")
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
    if not _CONNECTION_TEST_SLOTS.acquire(blocking=False):
        raise HTTPException(status_code=429, detail="连接测试繁忙，请稍后重试")
    try:
        result = _run_connectivity_test(db_type=ds.db_type or "oracle", host=host, port=port,
            database=database, user=user or "", password=pwd or "",
            connection_mode=ds.connection_mode or "direct")
    finally:
        _CONNECTION_TEST_SLOTS.release()
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


# ── 资产树（业务系统 → 连接 → schema → 表 → 字段） ──
# Plan 90: no external_business / platform_meta category groups.


def _classify_asset_source(
    system_code: str | None,
    source_code: str | None,
    source_kind: str | None = None,
    source_name_cn: str | None = None,
    schema_name: str | None = None,
    system_names: dict[str, str] | None = None,
) -> tuple[str, str, str, str]:
    """Return (system_code, system_name_cn, connection_key, connection_label).

    First-level identity is always a canonical business system (or catalog_anomaly).
    DATA_CENTER mirror owners stay nested under DATA_CENTER, never first-level.
    Independent LIS/PACS/Docare/JHEMR/移动护理 are peers, not external_business.
    """
    info = classify_for_tree(
        system_code,
        source_code,
        source_kind=source_kind,
        source_name_cn=source_name_cn,
        schema_name=schema_name,
        system_names=system_names,
    )
    # source_system field re-used as connection grouping key for API compatibility
    conn_key = (source_code or "").lower() or "unknown_connection"
    conn_label = source_name_cn or source_code or "未命名连接"
    if not info["catalog_ok"]:
        return (
            info["system_code"],
            info["system_name_cn"],
            "catalog_anomaly",
            "目录异常",
        )
    return (
        info["system_code"],
        info["system_name_cn"],
        conn_key,
        conn_label,
    )


def _presence_visible_clause():
    """Exclude confirmed_empty from normal catalog; keep unknown/blocked."""
    return (
        (AssetTable.row_presence_status.is_(None))
        | (AssetTable.row_presence_status != "confirmed_empty")
    )


def _table_brief(t: AssetTable) -> dict:
    ns = t.namespace_name or t.schema_name or ""
    return {
        "id": t.id,
        "table_name": t.table_name,
        "table_name_cn": t.table_name_cn,
        "name_cn_source": t.name_cn_source,
        "name_cn_status": t.name_cn_status,
        "column_count": t.column_count,
        "domain": t.domain,
        "owner_hint": (ns or "").upper(),
        "schema_name": ns,
        "source_code": t.source_code,
        "system_code": t.system_code,
        "row_presence_status": getattr(t, "row_presence_status", None),
    }


@router.get(
    "/assets/tree",
    summary="业务系统 → 连接 → schema 树（默认不含表清单，表按需加载）",
)
def assets_tree(
    system_code: str | None = Query(None),
    system_category: str | None = Query(
        None,
        description="兼容旧参数：现按 system_code 过滤；勿再传 external_business 等大类",
    ),
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
    # Load all sources so legacy aliases can always resolve their canonical
    # physical connection; filtering is applied after canonical classification.
    sources = {s.source_code: s for s in db.scalars(select(AssetDataSource)).all()}
    system_names = load_system_name_map(db)
    schema_inventory = {
        (row.source_code, (row.schema_name or "").upper()): row
        for row in db.scalars(select(AssetSourceSchema)).all()
    }

    # 骨架：仅聚合 (source_code, schema) 计数；排除 confirmed_empty
    ns_key = func.coalesce(AssetTable.schema_name, AssetTable.namespace_name, "")
    count_rows = db.execute(
        select(
            AssetTable.source_code,
            AssetTable.system_code,
            ns_key.label("ns"),
            func.count().label("cnt"),
        )
        .where(_presence_visible_clause())
        .group_by(AssetTable.source_code, AssetTable.system_code, ns_key)
    ).all()

    grouped: dict[str, dict[str, int]] = {}
    source_system_hint: dict[str, str] = {}
    for sc, tsys, ns, cnt in count_rows:
        sc_key = sc or "unknown"
        ns_val = ns or ""
        grouped.setdefault(sc_key, {})[ns_val] = grouped.get(sc_key, {}).get(ns_val, 0) + int(cnt)
        if tsys and sc_key not in source_system_hint:
            source_system_hint[sc_key] = tsys

    tables_by_schema: dict[tuple[str, str], list[dict]] = {}
    if include_tables:
        tables = db.scalars(select(AssetTable).where(_presence_visible_clause())).all()
        for t in tables:
            sc = t.source_code or "unknown"
            ns = t.namespace_name or t.schema_name or ""
            key = (sc, ns)
            bucket = tables_by_schema.setdefault(key, [])
            if max_tables_per_schema and len(bucket) >= max_tables_per_schema:
                continue
            bucket.append(_table_brief(t))

    tree = []
    for sc, schema_counts in sorted(grouped.items()):
        ds = sources.get(sc)
        canonical_ds = (
            sources.get(ds.canonical_source_code)
            if ds and ds.source_kind == "legacy_alias" and ds.canonical_source_code
            else None
        )
        display_ds = canonical_ds or ds
        raw_sys = (
            (display_ds.system_code if display_ds else None)
            or source_system_hint.get(sc)
            or "UNKNOWN"
        )
        # sample schema for DATA_CENTER mirror detection
        sample_ns = next(iter(schema_counts.keys()), None)
        physical_source_code = display_ds.source_code if display_ds else sc
        sys_code, sys_name, conn_key, conn_label = _classify_asset_source(
            raw_sys,
            sc,
            display_ds.source_kind if display_ds else (ds.source_kind if ds else None),
            display_ds.source_name_cn if display_ds else (ds.source_name_cn if ds else None),
            schema_name=sample_ns,
            system_names=system_names,
        )
        # connection endpoint display
        endpoint = None
        if display_ds:
            host = display_ds.host_masked or host_masked_from_target(display_ds.target_host) or display_ds.target_host
            port = display_ds.port
            db_or_svc = display_ds.service_name or display_ds.database_name
            if host:
                endpoint = f"{host}:{port or '-'}" + (f" / {db_or_svc}" if db_or_svc else "")
        conn_display = endpoint or conn_label

        # filter: system_category param now accepts system_code (compat)
        filter_code = system_category or system_code
        if filter_code and sys_code != filter_code.upper():
            continue

        node = {
            "source_code": sc,
            "physical_source_code": physical_source_code,
            "source_name_cn": (display_ds.source_name_cn if display_ds else sc),
            "connection_endpoint": endpoint,
            "system_code": sys_code,
            "system_name_cn": system_names.get(sys_code) or sys_name,
            # plan 90: category fields intentionally null for peers (no 大类)
            "system_category": None if sys_code in CANONICAL_SYSTEMS else "catalog_anomaly",
            "system_category_cn": None if sys_code in CANONICAL_SYSTEMS else "目录异常",
            "source_system": conn_key,
            "source_system_cn": conn_display,
            "schemas": [],
            "table_count": sum(schema_counts.values()),
            "tables_embedded": include_tables,
            "empty_catalog_hint": None,
        }
        for ns, cnt in sorted(schema_counts.items()):
            tbls = tables_by_schema.get((sc, ns), []) if include_tables else []
            inventory = schema_inventory.get((sc, (ns or "").upper()))
            owner_cn = (
                (inventory.schema_name_cn if inventory else None)
                or owner_display_cn(ns, parent_system=sys_code)
            )
            node["schemas"].append({
                "namespace": ns,
                "source_code": sc,
                "namespace_name_cn": owner_cn,
                "name_cn_source": inventory.name_cn_source if inventory else None,
                "name_cn_status": inventory.name_cn_status if inventory else None,
                "tables": tbls,
                "table_count": cnt,
                "tables_loaded": include_tables,
            })
        if node["table_count"] == 0:
            node["empty_catalog_hint"] = "当前未发现非空对象"
        tree.append(node)

    # 同一物理连接折叠；Schema 仍保留原 source_code
    consolidated: dict[tuple[str, str], dict] = {}
    for node in tree:
        key = (node["system_code"], node.get("physical_source_code") or node["source_code"])
        current = consolidated.get(key)
        if not current:
            current = {**node, "source_code": key[1], "schemas": [], "table_count": 0}
            consolidated[key] = current
        current["schemas"].extend(node["schemas"])
        current["table_count"] += node["table_count"]
        if current["table_count"] == 0:
            current["empty_catalog_hint"] = "当前未发现非空对象"
        else:
            current["empty_catalog_hint"] = None
    # stable order: canonical systems first
    order = {c: i for i, c in enumerate(CANONICAL_SYSTEMS)}
    result = sorted(
        consolidated.values(),
        key=lambda n: (order.get(n["system_code"], 999), n["system_code"], n["source_code"]),
    )
    return ApiResponse(data=result)


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
        _presence_visible_clause(),
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


@router.get("/assets/tree/search", summary="按表名/中文名搜索（返回完整路径，限量）")
def assets_tree_search(
    keyword: str = Query(..., min_length=1),
    system_category: str | None = Query(None, description="兼容：按 system_code 过滤"),
    system_code: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    like = f"%{keyword.strip()}%"
    stmt = (
        select(AssetTable)
        .where(
            _presence_visible_clause(),
            (AssetTable.table_name.ilike(like))
            | (AssetTable.table_name_cn.ilike(like)),
        )
        .order_by(AssetTable.schema_name, AssetTable.table_name)
        .limit(limit)
    )
    rows = db.scalars(stmt).all()
    sources = {
        s.source_code: s
        for s in db.scalars(select(AssetDataSource)).all()
    }
    system_names = load_system_name_map(db)
    filter_code = (system_code or system_category or "").upper() or None
    items = []
    for t in rows:
        sc = t.source_code or "unknown"
        ds = sources.get(sc)
        raw_sys = ds.system_code if ds else (t.system_code or "UNKNOWN")
        ns = t.namespace_name or t.schema_name or ""
        sys_code, sys_name, conn_key, conn_label = _classify_asset_source(
            raw_sys,
            sc,
            ds.source_kind if ds else None,
            ds.source_name_cn if ds else None,
            schema_name=ns,
            system_names=system_names,
        )
        if filter_code and sys_code != filter_code:
            continue
        owner_cn = owner_display_cn(ns, parent_system=sys_code)
        path_parts = [
            system_names.get(sys_code) or sys_name,
            conn_label,
            f"{owner_cn}（{ns}）" if owner_cn and ns else (ns or "-"),
            t.table_name_cn and f"{t.table_name}（{t.table_name_cn}）" or t.table_name,
        ]
        items.append({
            **_table_brief(t),
            "system_code": sys_code,
            "system_name_cn": system_names.get(sys_code) or sys_name,
            "system_category": None if sys_code in CANONICAL_SYSTEMS else "catalog_anomaly",
            "system_category_cn": None if sys_code in CANONICAL_SYSTEMS else "目录异常",
            "source_system": conn_key,
            "source_system_cn": conn_label,
            "source_name_cn": ds.source_name_cn if ds else sc,
            "path": " → ".join(str(p) for p in path_parts if p),
            "namespace_name_cn": owner_cn,
        })
    return ApiResponse(data={"keyword": keyword, "total": len(items), "items": items})
