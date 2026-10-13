"""215 E11 自 systems.py 拆出：数据源 CRUD、凭据与连通性（/api/v1/sources*）。"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, SecretStr

from ....core.db import get_db
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
from ._router import router
from ._shared import _audit, _source_public


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
            raise HTTPException(status_code=400, detail="credential_store_error") from exc

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
        from ...services.db_connectors import DB_CONNECTOR_MAP, transport_kwargs
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
            **transport_kwargs(ds.db_type, ds.connection_options),
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
            raise HTTPException(status_code=400, detail="credential_store_error") from exc
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
        raise HTTPException(status_code=400, detail="credential_store_error") from exc

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
            raise HTTPException(status_code=400, detail="credential_store_error") from exc
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
        raise HTTPException(status_code=400, detail="credential_store_error") from exc
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
