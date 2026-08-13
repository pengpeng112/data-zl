"""126 P2: metric ingest / revise / optional result registration."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..models.governance_base import GovernAuditLog
from ..models.metric_asset import AssetMetricDefinition, AssetMetricResult, AssetMetricVersion
from ..models.query_asset import AssetQueryVersion


def _now():
    return datetime.now(timezone.utc)


def metric_content_hash(payload: dict) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _ser_def(d: AssetMetricDefinition) -> dict:
    return {
        "id": d.id,
        "metric_code": d.metric_code,
        "title": d.title,
        "meaning": d.meaning,
        "category": d.category,
        "unit": d.unit,
        "frequency": d.frequency,
        "grain": d.grain,
        "owner_dept": d.owner_dept,
        "current_version_id": d.current_version_id,
        "allow_dashboard": d.allow_dashboard,
        "status": d.status,
        "created_at": d.created_at.isoformat() if d.created_at else None,
    }


def _ser_ver(v: AssetMetricVersion) -> dict:
    return {
        "id": v.id,
        "metric_id": v.metric_id,
        "metric_code": v.metric_code,
        "version": v.version,
        "parent_version_id": v.parent_version_id,
        "status": v.status,
        "is_active": v.is_active,
        "definition_text": v.definition_text,
        "numerator_desc": v.numerator_desc,
        "denominator_desc": v.denominator_desc,
        "formula": v.formula,
        "query_code": v.query_code,
        "query_version": v.query_version,
        "numerator_query_code": v.numerator_query_code,
        "numerator_query_version": v.numerator_query_version,
        "denominator_query_code": v.denominator_query_code,
        "denominator_query_version": v.denominator_query_version,
        "period_field": v.period_field,
        "include_rules": v.include_rules,
        "exclude_rules": v.exclude_rules,
        "dedup_rules": v.dedup_rules,
        "limitations": v.limitations,
        "system_code": v.system_code,
        "source_code": v.source_code,
        "revision_reason": v.revision_reason,
        "content_hash": v.content_hash,
        "activated_at": v.activated_at.isoformat() if v.activated_at else None,
        "created_at": v.created_at.isoformat() if v.created_at else None,
    }


def get_metric(db: Session, metric_code: str) -> AssetMetricDefinition | None:
    return db.scalar(select(AssetMetricDefinition).where(AssetMetricDefinition.metric_code == metric_code))


def get_active_metric_version(db: Session, metric_code: str) -> AssetMetricVersion | None:
    return db.scalar(
        select(AssetMetricVersion).where(
            AssetMetricVersion.metric_code == metric_code,
            AssetMetricVersion.is_active.is_(True),
        )
    )


def _resolve_query_ref(db: Session, query_code: str | None, query_version: int | None) -> tuple[str | None, int | None]:
    if not query_code:
        return None, None
    if query_version is not None:
        v = db.scalar(
            select(AssetQueryVersion).where(
                AssetQueryVersion.query_code == query_code,
                AssetQueryVersion.version == query_version,
            )
        )
        if not v:
            raise ValueError(f"查询版本不存在: {query_code}@{query_version}")
        return query_code, v.version
    v = db.scalar(
        select(AssetQueryVersion).where(
            AssetQueryVersion.query_code == query_code,
            AssetQueryVersion.is_active.is_(True),
        )
    )
    if not v:
        # allow definition without existing query yet → candidate
        return query_code, None
    return query_code, v.version


def ingest_metric(
    db: Session,
    *,
    metric_code: str,
    title: str,
    meaning: str | None = None,
    category: str | None = None,
    unit: str | None = None,
    frequency: str | None = None,
    grain: str | None = None,
    owner_dept: str | None = None,
    definition_text: str | None = None,
    numerator_desc: str | None = None,
    denominator_desc: str | None = None,
    formula: str | None = None,
    query_code: str | None = None,
    query_version: int | None = None,
    numerator_query_code: str | None = None,
    numerator_query_version: int | None = None,
    denominator_query_code: str | None = None,
    denominator_query_version: int | None = None,
    period_field: str | None = None,
    include_rules: str | None = None,
    exclude_rules: str | None = None,
    dedup_rules: str | None = None,
    limitations: list | None = None,
    system_code: str | None = None,
    source_code: str | None = None,
    revision_reason: str | None = None,
    created_by: str | None = None,
    force_new_version: bool = False,
    auto_activate: bool = True,
) -> dict[str, Any]:
    metric_code = (metric_code or "").strip()
    if not metric_code:
        raise ValueError("metric_code 必填")
    if not (title or "").strip():
        title = metric_code

    q_code, q_ver = _resolve_query_ref(db, query_code, query_version)
    n_code, n_ver = _resolve_query_ref(db, numerator_query_code, numerator_query_version)
    d_code, d_ver = _resolve_query_ref(db, denominator_query_code, denominator_query_version)

    payload = {
        "definition_text": definition_text or meaning or "",
        "numerator_desc": numerator_desc or "",
        "denominator_desc": denominator_desc or "",
        "formula": formula or "",
        "query_code": q_code or "",
        "query_version": q_ver,
        "numerator_query_code": n_code or "",
        "numerator_query_version": n_ver,
        "denominator_query_code": d_code or "",
        "denominator_query_version": d_ver,
        "period_field": period_field or "",
        "include_rules": include_rules or "",
        "exclude_rules": exclude_rules or "",
        "dedup_rules": dedup_rules or "",
        "limitations": limitations or [],
    }
    chash = metric_content_hash(payload)

    # Gate: must have definition text and either single query or num/den
    errors = []
    if not payload["definition_text"] and not payload["numerator_desc"]:
        errors.append("缺少指标定义或分子说明")
    if not (q_code or (n_code and d_code) or formula):
        errors.append("需引用查询版本或提供公式/分子分母查询")
    # Missing query version → candidate not auto active
    missing_qv = False
    if q_code and q_ver is None:
        missing_qv = True
    if n_code and n_ver is None:
        missing_qv = True
    if d_code and d_ver is None:
        missing_qv = True

    definition = get_metric(db, metric_code)
    created_def = False
    if definition is None:
        definition = AssetMetricDefinition(
            metric_code=metric_code,
            title=title,
            meaning=meaning,
            category=category,
            unit=unit,
            frequency=frequency,
            grain=grain,
            owner_dept=owner_dept,
            created_by=created_by,
            updated_by=created_by,
        )
        db.add(definition)
        db.flush()
        created_def = True
    else:
        definition.title = title or definition.title
        if meaning is not None:
            definition.meaning = meaning
        if category is not None:
            definition.category = category
        if unit is not None:
            definition.unit = unit
        definition.updated_by = created_by
        definition.updated_at = _now()

    existing = db.scalar(
        select(AssetMetricVersion).where(
            AssetMetricVersion.metric_id == definition.id,
            AssetMetricVersion.content_hash == chash,
        )
    )
    if existing and not force_new_version:
        return {
            "idempotent": True,
            "created_definition": created_def,
            "definition": _ser_def(definition),
            "version": _ser_ver(existing),
        }

    max_ver = db.scalar(
        select(AssetMetricVersion.version)
        .where(AssetMetricVersion.metric_id == definition.id)
        .order_by(AssetMetricVersion.version.desc())
        .limit(1)
    ) or 0
    parent = get_active_metric_version(db, metric_code)
    next_ver = max_ver + 1

    if errors:
        status = "blocked"
        activate = False
    elif missing_qv:
        status = "candidate"
        activate = False
    else:
        status = "active" if auto_activate else "validated"
        activate = auto_activate

    version = AssetMetricVersion(
        metric_id=definition.id,
        metric_code=metric_code,
        version=next_ver,
        parent_version_id=parent.id if parent else None,
        status=status,
        is_active=False,
        definition_text=payload["definition_text"],
        numerator_desc=numerator_desc,
        denominator_desc=denominator_desc,
        formula=formula,
        query_code=q_code,
        query_version=q_ver,
        numerator_query_code=n_code,
        numerator_query_version=n_ver,
        denominator_query_code=d_code,
        denominator_query_version=d_ver,
        period_field=period_field,
        include_rules=include_rules,
        exclude_rules=exclude_rules,
        dedup_rules=dedup_rules,
        limitations=limitations or [],
        system_code=system_code,
        source_code=source_code,
        revision_reason=revision_reason,
        content_hash=chash,
        created_by=created_by,
    )
    db.add(version)
    db.flush()

    activated = False
    if activate and status == "active":
        db.execute(
            update(AssetMetricVersion)
            .where(
                AssetMetricVersion.metric_code == metric_code,
                AssetMetricVersion.is_active.is_(True),
            )
            .values(is_active=False, status="superseded", updated_at=_now())
        )
        version.is_active = True
        version.status = "active"
        version.activated_at = _now()
        definition.current_version_id = version.id
        definition.status = "active"
        activated = True
    elif parent is None:
        # Definition-level status is a catalog summary, not permission to run.
        # Keep it aligned with the latest non-active version so a blocked
        # placeholder cannot be presented as an active metric.
        definition.current_version_id = None
        definition.status = status

    db.add(
        GovernAuditLog(
            module="metric_asset",
            entity_type="metric_version",
            entity_ref=f"{metric_code}@{next_ver}",
            action="ingest_activate" if activated else "ingest",
            after_data={
                "metric_code": metric_code,
                "version": next_ver,
                "status": version.status,
                "content_hash": chash,
                "errors": errors,
            },
            operator=created_by,
        )
    )
    db.flush()
    return {
        "idempotent": False,
        "created_definition": created_def,
        "activated": activated,
        "gate_errors": errors,
        "definition": _ser_def(definition),
        "version": _ser_ver(version),
    }


def register_metric_result(
    db: Session,
    *,
    metric_code: str,
    period_key: str,
    version: int | None = None,
    numerator_value: str | None = None,
    denominator_value: str | None = None,
    metric_value: str | None = None,
    status: str = "ok",
    limitations_note: str | None = None,
    dimensions: dict | None = None,
    query_run_id: int | None = None,
    created_by: str | None = None,
) -> dict[str, Any]:
    """Optional result save. Never overwrites old rows — always insert new batch."""
    if version is not None:
        mv = db.scalar(
            select(AssetMetricVersion).where(
                AssetMetricVersion.metric_code == metric_code,
                AssetMetricVersion.version == version,
            )
        )
    else:
        mv = get_active_metric_version(db, metric_code)
    if not mv:
        raise LookupError(f"指标版本不存在: {metric_code}")

    batch = f"batch-{_now().strftime('%Y%m%d%H%M%S')}"
    prev = db.scalar(
        select(AssetMetricResult)
        .where(
            AssetMetricResult.metric_code == metric_code,
            AssetMetricResult.period_key == period_key,
            AssetMetricResult.version == mv.version,
        )
        .order_by(AssetMetricResult.id.desc())
        .limit(1)
    )
    row = AssetMetricResult(
        metric_version_id=mv.id,
        metric_code=metric_code,
        version=mv.version,
        period_key=period_key,
        dimensions=dimensions,
        numerator_value=numerator_value,
        denominator_value=denominator_value,
        metric_value=metric_value,
        status=status,
        limitations_note=limitations_note or (
            "; ".join(mv.limitations) if isinstance(mv.limitations, list) else None
        ),
        query_run_id=query_run_id,
        run_batch=batch,
        is_recalc=bool(prev),
        prev_result_id=prev.id if prev else None,
        data_as_of=_now(),
        created_by=created_by,
    )
    db.add(row)
    db.flush()
    return {
        "id": row.id,
        "metric_code": metric_code,
        "version": mv.version,
        "period_key": period_key,
        "metric_value": metric_value,
        "status": status,
        "run_batch": batch,
        "is_recalc": row.is_recalc,
        "prev_result_id": row.prev_result_id,
    }
