"""126 P4: publish and execute data products from active query/metric versions."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..models.data_product import AssetDataProduct
from ..models.governance_base import GovernAuditLog
from ..models.metric_asset import AssetMetricDefinition, AssetMetricVersion
from ..models.query_asset import AssetQueryDefinition, AssetQueryVersion
from ..services.metric_service import get_active_metric_version, register_metric_result
from ..services.query_runner import run_query_version


def _now():
    return datetime.now(timezone.utc)


def _ser(p: AssetDataProduct) -> dict:
    return {
        "id": p.id,
        "product_code": p.product_code,
        "title": p.title,
        "description": p.description,
        "product_type": p.product_type,
        "query_code": p.query_code,
        "metric_code": p.metric_code,
        "pin_version": p.pin_version,
        "source_code": p.source_code,
        "parameter_schema": p.parameter_schema,
        "max_rows": p.max_rows,
        "result_storage": p.result_storage,
        "enabled": p.enabled,
        "ai_readable": p.ai_readable,
        "rate_limit_per_min": p.rate_limit_per_min,
        "owner_name": p.owner_name,
    }


def upsert_product(
    db: Session,
    *,
    product_code: str,
    title: str,
    product_type: str,
    query_code: str | None = None,
    metric_code: str | None = None,
    pin_version: int | None = None,
    source_code: str | None = None,
    description: str | None = None,
    parameter_schema: dict | None = None,
    max_rows: int = 1000,
    enabled: bool = True,
    created_by: str | None = None,
) -> dict:
    product_type = (product_type or "").lower()
    if product_type not in {"query", "metric"}:
        raise ValueError("product_type 必须是 query 或 metric")
    if product_type == "query" and not query_code:
        raise ValueError("query 产品必须指定 query_code")
    if product_type == "metric" and not metric_code:
        raise ValueError("metric 产品必须指定 metric_code")

    # validate refs exist and active
    if product_type == "query":
        q = db.scalar(
            select(AssetQueryVersion).where(
                AssetQueryVersion.query_code == query_code,
                AssetQueryVersion.is_active.is_(True),
            )
        )
        if not q:
            raise ValueError(f"无 active 查询: {query_code}")
        d = db.scalar(select(AssetQueryDefinition).where(AssetQueryDefinition.query_code == query_code))
        if d:
            d.allow_data_product = True
    else:
        m = get_active_metric_version(db, metric_code)
        if not m:
            raise ValueError(f"无 active 指标: {metric_code}")
        d = db.scalar(select(AssetMetricDefinition).where(AssetMetricDefinition.metric_code == metric_code))
        if d:
            d.allow_data_product = True
        # metrics may also have query for execution
        query_code = query_code or m.query_code

    row = db.scalar(select(AssetDataProduct).where(AssetDataProduct.product_code == product_code))
    pin_status = None
    # 144 S4/A17: explicit pin must reference a runnable version; a changed
    # pin bumps the product revision instead of silently swapping semantics.
    if pin_version is not None:
        qv = db.scalar(
            select(AssetQueryVersion).where(
                AssetQueryVersion.query_code == query_code,
                AssetQueryVersion.version == pin_version,
            )
        )
        if qv is None:
            raise ValueError(f"pin 版本不存在: {query_code}@{pin_version}")
        if qv.status in {"blocked", "candidate"}:
            raise ValueError(
                f"pin 版本 {query_code}@{pin_version} 状态为 {qv.status}，禁止产品发布"
            )
        pin_status = "validated" if qv.is_active else f"pinned:{qv.status}"
    if not row:
        row = AssetDataProduct(product_code=product_code, created_by=created_by)
        db.add(row)
    else:
        if row.pin_version != pin_version or row.query_code != query_code:
            row.revision = int(row.revision or 1) + 1
    row.title = title
    row.description = description
    row.product_type = product_type
    row.query_code = query_code
    row.metric_code = metric_code
    row.pin_version = pin_version
    row.source_code = source_code
    row.parameter_schema = parameter_schema or {}
    row.max_rows = max_rows
    row.enabled = enabled
    row.pin_validation_status = pin_status
    if pin_status:
        row.pin_validated_at = _now()
    row.updated_at = _now()
    db.flush()
    return _ser(row)


def publish_core_products(db: Session, *, created_by: str = "system") -> dict:
    """Publish DP_QRY_CORE_* / DP_MET_CORE_* for all active core assets."""
    created = []
    qrows = db.scalars(
        select(AssetQueryVersion).where(
            AssetQueryVersion.is_active.is_(True),
            AssetQueryVersion.query_code.like("QRY_CORE_%"),
        )
    ).all()
    for q in qrows:
        d = db.scalar(select(AssetQueryDefinition).where(AssetQueryDefinition.query_code == q.query_code))
        code = f"DP_{q.query_code}"
        created.append(
            upsert_product(
                db,
                product_code=code,
                title=(d.title if d else q.query_code),
                product_type="query",
                query_code=q.query_code,
                source_code=(d.source_code if d else None) or "ods_8_216",
                description="48项核心制度查询产品",
                created_by=created_by,
            )
        )
    mrows = db.scalars(
        select(AssetMetricVersion).where(
            AssetMetricVersion.is_active.is_(True),
            AssetMetricVersion.metric_code.like("MET_CORE_%"),
        )
    ).all()
    for m in mrows:
        d = db.scalar(select(AssetMetricDefinition).where(AssetMetricDefinition.metric_code == m.metric_code))
        code = f"DP_{m.metric_code}"
        created.append(
            upsert_product(
                db,
                product_code=code,
                title=(d.title if d else m.metric_code),
                product_type="metric",
                metric_code=m.metric_code,
                query_code=m.query_code,
                source_code=m.source_code or "ods_8_216",
                description="48项核心制度指标产品（返回口径+可选执行关联查询）",
                created_by=created_by,
            )
        )
    db.flush()
    return {"count": len(created), "items": created}


def execute_product(
    db: Session,
    *,
    product_code: str,
    parameters: dict | None = None,
    source_code: str | None = None,
    execute_sql: bool = False,
    triggered_by: str | None = None,
    caller_id: str | None = None,
) -> dict[str, Any]:
    """Execute published product.

    - metric products return definition/active version by default (no heavy SQL).
    - execute_sql=True runs the linked active query via read-only runner.
    - query products always run read-only when called.
    - 144 S4/A18: per (product, caller) rate/concurrency limits are enforced.
    """
    from .data_product_rate_limit import check_rate, concurrency_guard

    p = db.scalar(select(AssetDataProduct).where(AssetDataProduct.product_code == product_code))
    if not p or not p.enabled:
        raise LookupError("数据产品不存在或未启用")

    check_rate(
        product_code,
        caller_id or (triggered_by or "anonymous"),
        limit_per_minute=p.rate_limit_per_min,
    )
    with concurrency_guard(
        product_code, caller_id or (triggered_by or "anonymous"), max_concurrency=p.max_concurrency
    ):
        # D6：把已查到的产品行传下去，锁内不再按 product_code 重复查询同一行。
        return _execute_product_locked(
            db,
            product=p,
            product_code=product_code,
            parameters=parameters,
            source_code=source_code,
            execute_sql=execute_sql,
            triggered_by=triggered_by,
            caller_id=caller_id,
        )


def _execute_product_locked(
    db: Session,
    *,
    product: AssetDataProduct,
    product_code: str,
    parameters: dict | None = None,
    source_code: str | None = None,
    execute_sql: bool = False,
    triggered_by: str | None = None,
    caller_id: str | None = None,
) -> dict[str, Any]:
    """Execute published product.

    - metric products return definition/active version by default (no heavy SQL).
    - execute_sql=True runs the linked active query via read-only runner.
    - query products always run read-only when called.
    """
    p = product

    # parameter whitelist
    schema = p.parameter_schema or {}
    params = parameters or {}
    if schema:
        unknown = set(params) - set(schema)
        if unknown:
            raise ValueError(f"参数不在白名单: {sorted(unknown)}")
        for name, spec in schema.items():
            if isinstance(spec, dict) and spec.get("required") and name not in params:
                raise ValueError(f"缺少必填参数: {name}")

    if p.product_type == "metric":
        mv = get_active_metric_version(db, p.metric_code)
        if not mv:
            raise LookupError("指标版本不存在")
        payload = {
            "product_code": p.product_code,
            "product_type": "metric",
            "metric_code": mv.metric_code,
            "version": mv.version,
            "title": p.title,
            "definition_text": mv.definition_text,
            "numerator_desc": mv.numerator_desc,
            "denominator_desc": mv.denominator_desc,
            "formula": mv.formula,
            "limitations": mv.limitations,
            "query_code": mv.query_code,
            "query_version": mv.query_version,
            "executed": False,
        }
        if execute_sql and (mv.query_code or mv.numerator_query_code or mv.denominator_query_code):
            # 144 S4: real calculation engine — numerator/denominator/formula
            # are computed and registered, not left to the caller.
            from .metric_calculation_orchestrator import calculate_metric_version

            period_key = str(params.get("period_key") or params.get("month") or "") or None
            if not period_key:
                from datetime import datetime, timezone

                period_key = datetime.now(timezone.utc).strftime("%Y-%m")
            calc = calculate_metric_version(
                db,
                metric_code=mv.metric_code,
                version=mv.version,
                period_key=period_key,
                parameters=params or None,
                triggered_by=triggered_by or "data_product",
                max_rows=p.max_rows or 1000,
            )
            payload["executed"] = True
            payload["calculation"] = calc
        db.add(
            GovernAuditLog(
                module="data_product",
                entity_type="product_execute",
                entity_ref=product_code,
                action="execute",
                after_data={"type": "metric", "execute_sql": execute_sql},
                operator=triggered_by,
            )
        )
        db.flush()
        return payload

    # query product
    if not p.query_code:
        raise ValueError("查询产品缺少 query_code")
    run = run_query_version(
        db,
        query_code=p.query_code,
        version=p.pin_version,
        source_code=source_code or p.source_code,
        parameters=params,
        result_storage=p.result_storage or "none",
        max_rows=p.max_rows or 1000,
        triggered_by=triggered_by or "data_product",
    )
    db.add(
        GovernAuditLog(
            module="data_product",
            entity_type="product_execute",
            entity_ref=product_code,
            action="execute",
            after_data={"type": "query", "run_id": run.get("run_id")},
            operator=triggered_by,
        )
    )
    db.flush()
    return {
        "product_code": p.product_code,
        "product_type": "query",
        "query_code": p.query_code,
        "executed": True,
        "run": run,
    }
