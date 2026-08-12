"""126 P1: ingest query packages → definitions/versions with auto gate."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..models.governance_base import GovernAuditLog
from ..models.query_asset import (
    AssetQueryDefinition,
    AssetQueryDependency,
    AssetQueryVersion,
)
from ..services.query_fingerprint import semantic_fingerprint, sql_sha256, normalize_sql
from ..services.query_gate import evaluate_query_gate, extract_table_refs


def _now():
    return datetime.now(timezone.utc)


def get_definition(db: Session, query_code: str) -> AssetQueryDefinition | None:
    return db.scalar(
        select(AssetQueryDefinition).where(AssetQueryDefinition.query_code == query_code)
    )


def get_active_version(db: Session, query_code: str) -> AssetQueryVersion | None:
    return db.scalar(
        select(AssetQueryVersion).where(
            AssetQueryVersion.query_code == query_code,
            AssetQueryVersion.is_active.is_(True),
        )
    )


def _serialize_def(d: AssetQueryDefinition) -> dict:
    return {
        "id": d.id,
        "query_code": d.query_code,
        "title": d.title,
        "purpose": d.purpose,
        "business_domain": d.business_domain,
        "system_code": d.system_code,
        "source_code": d.source_code,
        "namespace_name": d.namespace_name,
        "owner_name": d.owner_name,
        "sensitivity": d.sensitivity,
        "current_version_id": d.current_version_id,
        "ai_readable": d.ai_readable,
        "allow_schedule": d.allow_schedule,
        "allow_data_product": d.allow_data_product,
        "status": d.status,
        "created_by": d.created_by,
        "updated_by": d.updated_by,
        "created_at": d.created_at.isoformat() if d.created_at else None,
        "updated_at": d.updated_at.isoformat() if d.updated_at else None,
    }


def _serialize_ver(v: AssetQueryVersion) -> dict:
    return {
        "id": v.id,
        "query_id": v.query_id,
        "query_code": v.query_code,
        "version": v.version,
        "parent_version_id": v.parent_version_id,
        "status": v.status,
        "is_active": v.is_active,
        "dialect": v.dialect,
        "sql_text": v.sql_text,
        "sql_normalized": v.sql_normalized,
        "sql_sha256": v.sql_sha256,
        "semantic_fingerprint": v.semantic_fingerprint,
        "parameter_schema": v.parameter_schema,
        "output_schema": v.output_schema,
        "grain": v.grain,
        "period_field": v.period_field,
        "include_rules": v.include_rules,
        "exclude_rules": v.exclude_rules,
        "dedup_rules": v.dedup_rules,
        "limitations": v.limitations,
        "risk_flags": v.risk_flags,
        "recipe_refs": v.recipe_refs,
        "metric_refs": v.metric_refs,
        "source_path": v.source_path,
        "ai_source": v.ai_source,
        "session_key": v.session_key,
        "revision_reason": v.revision_reason,
        "diff_summary": v.diff_summary,
        "effective_from": v.effective_from.isoformat() if v.effective_from else None,
        "effective_to": v.effective_to.isoformat() if v.effective_to else None,
        "validated_at": v.validated_at.isoformat() if v.validated_at else None,
        "activated_at": v.activated_at.isoformat() if v.activated_at else None,
        "created_by": v.created_by,
        "created_at": v.created_at.isoformat() if v.created_at else None,
    }


def ingest_query(
    db: Session,
    *,
    query_code: str,
    title: str,
    sql_text: str,
    purpose: str | None = None,
    system_code: str | None = None,
    source_code: str | None = None,
    dialect: str = "oracle",
    business_domain: str | None = None,
    grain: str | None = None,
    period_field: str | None = None,
    parameter_schema: dict | list | None = None,
    limitations: list | None = None,
    recipe_refs: list | None = None,
    metric_refs: list | None = None,
    source_path: str | None = None,
    ai_source: dict | None = None,
    session_key: str | None = None,
    revision_reason: str | None = None,
    created_by: str | None = None,
    force_new_version: bool = False,
) -> dict[str, Any]:
    """Ingest SQL as query version. Idempotent on same sql hash for same query_code.

    Auto gate: validated → active; blocked → blocked (not active).
    """
    query_code = (query_code or "").strip()
    if not query_code:
        raise ValueError("query_code 必填")
    if not (sql_text or "").strip():
        raise ValueError("sql_text 必填")
    if not (title or "").strip():
        title = query_code

    sha = sql_sha256(sql_text)
    gate = evaluate_query_gate(
        sql_text,
        dialect=dialect,
        system_code=system_code,
        source_code=source_code,
        require_source=False,  # definition may register source later; run still requires it
    )

    definition = get_definition(db, query_code)
    created_def = False
    if definition is None:
        definition = AssetQueryDefinition(
            query_code=query_code,
            title=title,
            purpose=purpose,
            business_domain=business_domain,
            system_code=system_code,
            source_code=source_code,
            sensitivity="aggregate",
            created_by=created_by,
            updated_by=created_by,
        )
        db.add(definition)
        db.flush()
        created_def = True
    else:
        # Update mutable metadata on definition
        definition.title = title or definition.title
        if purpose is not None:
            definition.purpose = purpose
        if system_code:
            definition.system_code = system_code
        if source_code:
            definition.source_code = source_code
        if business_domain:
            definition.business_domain = business_domain
        definition.updated_by = created_by
        definition.updated_at = _now()

    # Idempotent: same SQL hash already exists
    existing = db.scalar(
        select(AssetQueryVersion).where(
            AssetQueryVersion.query_id == definition.id,
            AssetQueryVersion.sql_sha256 == sha,
        )
    )
    if existing and not force_new_version:
        return {
            "idempotent": True,
            "created_definition": created_def,
            "definition": _serialize_def(definition),
            "version": _serialize_ver(existing),
            "gate": gate,
        }

    max_ver = db.scalar(
        select(AssetQueryVersion.version)
        .where(AssetQueryVersion.query_id == definition.id)
        .order_by(AssetQueryVersion.version.desc())
        .limit(1)
    ) or 0
    parent = get_active_version(db, query_code)
    next_ver = max_ver + 1

    status = gate["status"]
    if status == "validated" and gate["auto_activate"]:
        final_status = "active"
    elif status == "blocked":
        final_status = "blocked"
    else:
        final_status = "candidate"

    risk = {
        "errors": gate.get("errors") or [],
        "warnings": gate.get("warnings") or [],
        "safety": gate.get("safety"),
    }

    version = AssetQueryVersion(
        query_id=definition.id,
        query_code=query_code,
        version=next_ver,
        parent_version_id=parent.id if parent else None,
        status=final_status,
        is_active=False,
        dialect=dialect,
        sql_text=sql_text,
        sql_normalized=normalize_sql(sql_text),
        sql_sha256=sha,
        semantic_fingerprint=semantic_fingerprint(
            sql_text, system_code=system_code, source_code=source_code
        ),
        parameter_schema=parameter_schema,
        grain=grain,
        period_field=period_field,
        limitations=limitations or [],
        risk_flags=risk,
        recipe_refs=recipe_refs or [],
        metric_refs=metric_refs or [],
        source_path=source_path,
        ai_source=ai_source,
        session_key=session_key,
        revision_reason=revision_reason,
        created_by=created_by,
    )
    if final_status in {"validated", "active"}:
        version.validated_at = _now()
    db.add(version)
    db.flush()

    # Dependencies from table refs (candidate evidence only)
    for tbl in extract_table_refs(sql_text):
        parts = tbl.split(".")
        schema_name = parts[-2] if len(parts) >= 2 else None
        object_name = parts[-1]
        db.add(
            AssetQueryDependency(
                query_version_id=version.id,
                dep_type="table",
                system_code=system_code,
                source_code=source_code,
                schema_name=schema_name,
                object_name=object_name,
                is_formal=False,
                evidence="parsed_from_sql",
            )
        )

    activated = False
    if final_status == "active":
        # supersede previous active
        db.execute(
            update(AssetQueryVersion)
            .where(
                AssetQueryVersion.query_code == query_code,
                AssetQueryVersion.is_active.is_(True),
            )
            .values(is_active=False, status="superseded", updated_at=_now())
        )
        version.is_active = True
        version.status = "active"
        version.activated_at = _now()
        definition.current_version_id = version.id
        activated = True

    db.add(
        GovernAuditLog(
            module="query_asset",
            entity_type="query_version",
            entity_ref=f"{query_code}@{next_ver}",
            action="ingest_activate" if activated else "ingest",
            after_data={
                "query_code": query_code,
                "version": next_ver,
                "status": version.status,
                "sql_sha256": sha,
                "activated": activated,
            },
            operator=created_by,
        )
    )
    db.flush()
    return {
        "idempotent": False,
        "created_definition": created_def,
        "activated": activated,
        "definition": _serialize_def(definition),
        "version": _serialize_ver(version),
        "gate": gate,
    }


def revise_query(
    db: Session,
    *,
    query_code: str,
    sql_text: str,
    revision_reason: str,
    title: str | None = None,
    created_by: str | None = None,
    **kwargs,
) -> dict[str, Any]:
    if not (revision_reason or "").strip():
        raise ValueError("修订必须填写 revision_reason")
    d = get_definition(db, query_code)
    if not d:
        raise ValueError(f"查询不存在: {query_code}")
    return ingest_query(
        db,
        query_code=query_code,
        title=title or d.title,
        sql_text=sql_text,
        purpose=kwargs.get("purpose", d.purpose),
        system_code=kwargs.get("system_code", d.system_code),
        source_code=kwargs.get("source_code", d.source_code),
        dialect=kwargs.get("dialect", "oracle"),
        business_domain=kwargs.get("business_domain", d.business_domain),
        grain=kwargs.get("grain"),
        period_field=kwargs.get("period_field"),
        parameter_schema=kwargs.get("parameter_schema"),
        limitations=kwargs.get("limitations"),
        recipe_refs=kwargs.get("recipe_refs"),
        metric_refs=kwargs.get("metric_refs"),
        source_path=kwargs.get("source_path"),
        ai_source=kwargs.get("ai_source"),
        session_key=kwargs.get("session_key"),
        revision_reason=revision_reason,
        created_by=created_by,
        force_new_version=True,
    )
