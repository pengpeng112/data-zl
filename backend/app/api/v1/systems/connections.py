"""215 E11 自 systems.py 拆出：物理连接视图、连通性测试与连接目标（/api/v1/connections*、/db-types）。"""
from __future__ import annotations

from datetime import datetime, timezone
import threading

from fastapi import Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from pydantic import BaseModel, SecretStr

from ....core.db import get_db
from ....models.asset import AssetTable
from ....models.asset_system import AssetDataSource
from ....schemas.common import ApiResponse
from ....core.security import get_current_user, require_permission
from ....core.rate_limit import limiter
from ....services.connection_identity import (
    ALLOWED_DB_TYPES,
    MAX_CONNECTIVITY_TIMEOUT_MS,
    build_endpoint_key,
    default_port,
    host_masked_from_target,
    validate_connection_fields,
    validate_ssrf_target,
)
from ....services.ops_event_log import log_event

from ._router import router
from ._shared import _source_public


_CONNECTION_TEST_SLOTS = threading.BoundedSemaphore(value=4)

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
    connection_options: dict | None = None,
) -> dict:
    from ...services.db_connectors import DB_CONNECTOR_MAP, transport_kwargs

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
        **transport_kwargs(db_type, connection_options),
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
    schema_key = func.coalesce(AssetTable.schema_name, AssetTable.namespace_name, "")
    schemas = db.execute(
        select(schema_key.label("schema_name"), func.count().label("table_count"))
        .where(AssetTable.source_code == ds.source_code)
        .group_by(schema_key)
        .order_by(schema_key)
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
            connection_mode=ds.connection_mode or "direct",
            connection_options=ds.connection_options if isinstance(ds.connection_options, dict) else None)
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
