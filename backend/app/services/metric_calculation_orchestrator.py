"""144 S4 orchestration: run sub-queries, compute, register run + result.

Results are keyed by the business key (metric, version, period, dimensions,
parameters, batch) so same-period different-dimension/batch results never
overwrite each other and batch replays stay idempotent.
"""
from __future__ import annotations

import decimal
import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from .metric_calculation_service import (
    ENGINE_VERSION,
    _to_decimal,
    calculate_metric_value,
)


def dimensions_hash(dimensions: dict | None) -> str:
    blob = json.dumps(dimensions or {}, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _first_numeric_from_sample(sample: list[dict] | None) -> decimal.Decimal | None:
    """First numeric field of the first row (aggregation contract)."""
    if not sample:
        return None
    row = sample[0] or {}
    for key in sorted(row.keys()):
        value = row[key]
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            return _to_decimal(value)
        if isinstance(value, str):
            try:
                return decimal.Decimal(value)
            except decimal.InvalidOperation:
                continue
    return None


def run_batch_label(now: datetime, sequence: int) -> str:
    """144 §6.2: UTC date + deterministic batch sequence, never free text."""
    return f"{now.strftime('%Y%m%d')}-{int(sequence):06d}"


def _register_result(db, *, mv, period_key, dimensions, dhash, phash, parameters,
                     num_value, den_value, value, status, batch, main_run_id,
                     num_run_id, data_as_of, triggered_by):
    from ..models.metric_asset import AssetMetricResult

    prev = db.scalar(
        _sa_select(AssetMetricResult)
        .where(
            AssetMetricResult.metric_code == mv.metric_code,
            AssetMetricResult.period_key == period_key,
            AssetMetricResult.version == mv.version,
            AssetMetricResult.dimensions_hash == dhash,
        )
        .order_by(AssetMetricResult.id.desc())
        .limit(1)
    )
    row = AssetMetricResult(
        metric_version_id=mv.id,
        metric_code=mv.metric_code,
        version=mv.version,
        period_key=period_key,
        dimensions=dimensions or {},
        dimensions_hash=dhash,
        parameter_hash=phash,
        numerator_value=str(num_value) if num_value is not None else None,
        denominator_value=str(den_value) if den_value is not None else None,
        metric_value=str(value) if value is not None else None,
        numerator_num=num_value,
        denominator_num=den_value,
        metric_num=value,
        result_digest=hashlib.sha256(
            json.dumps(
                {
                    "metric_code": mv.metric_code,
                    "version": mv.version,
                    "period_key": period_key,
                    "status": status,
                    "value": str(value) if value is not None else None,
                    "batch": batch,
                    "dimensions_hash": dhash,
                },
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest(),
        status=status,
        query_run_id=main_run_id or num_run_id,
        run_batch=batch,
        is_recalc=bool(prev),
        prev_result_id=prev.id if prev else None,
        data_as_of=data_as_of or datetime.now(timezone.utc),
        created_by=triggered_by,
    )
    db.add(row)
    return row


def _sa_select(*entities):
    from sqlalchemy import select

    return select(*entities)


def calculate_metric_version(
    db,
    *,
    metric_code: str,
    version: int | None = None,
    period_key: str,
    parameters: dict | None = None,
    dimensions: dict | None = None,
    triggered_by: str | None = None,
    max_rows: int = 1000,
) -> dict[str, Any]:
    """Run sub-queries, compute with Decimal semantics, register run+result."""
    from ..models.metric_asset import AssetMetricResult, AssetMetricRun, AssetMetricVersion
    from ..models.query_asset import AssetQueryVersion
    from .query_fingerprint import parameters_hash as fp_parameters_hash
    from .query_runner import run_query_version

    if version is not None:
        mv = db.scalar(
            _sa_select(AssetMetricVersion).where(
                AssetMetricVersion.metric_code == metric_code,
                AssetMetricVersion.version == version,
            )
        )
    else:
        mv = db.scalar(
            _sa_select(AssetMetricVersion).where(
                AssetMetricVersion.metric_code == metric_code,
                AssetMetricVersion.is_active.is_(True),
            )
        )
    if not mv:
        raise LookupError(f"指标版本不存在: {metric_code}@{version or 'active'}")
    if mv.status in {"blocked", "candidate"}:
        raise PermissionError(
            f"指标版本 {metric_code}@{mv.version} 状态为 {mv.status}，禁止计算"
        )

    calc_type = (mv.calculation_type or "ratio").lower()
    precision = int(mv.precision or 2)
    rounding = mv.rounding_mode or "half_up"

    dhash = dimensions_hash(dimensions)
    phash = fp_parameters_hash(parameters)

    run_row = AssetMetricRun(
        metric_code=metric_code,
        metric_version_id=mv.id,
        version=mv.version,
        period_key=period_key,
        dimensions=dimensions or {},
        parameters=parameters or {},
        parameters_hash=phash,
        calculation_type=calc_type,
        status="running",
        formula=mv.formula,
        engine_version=ENGINE_VERSION,
        triggered_by=triggered_by,
    )
    db.add(run_row)
    db.flush()
    batch = run_batch_label(datetime.now(timezone.utc), run_row.id)
    correlation_id = f"mcalc-{run_row.id}"

    def _exec(code_attr: str, ver_attr: str):
        code = getattr(mv, code_attr, None)
        ver = getattr(mv, ver_attr, None)
        if not code:
            return None, None, None, None
        # each sub-query validates parameters against ITS OWN schema; the
        # shared parameter set is projected onto that schema first so a
        # numerator-only bind never blocks the denominator (144 §4.1).
        sub_qv = db.scalar(
            _sa_select(AssetQueryVersion).where(
                AssetQueryVersion.query_code == code,
                AssetQueryVersion.version == ver,
            )
        ) if ver is not None else None
        sub_params = parameters
        if sub_qv is not None and parameters:
            # project onto the sub-query's own declared properties; a sub-query
            # without a schema receives no parameters (it declares no binds)
            props = (sub_qv.parameter_schema or {}).get("properties") or {}
            sub_params = {k: v for k, v in parameters.items() if k in props}
        try:
            outcome = run_query_version(
                db,
                query_code=code,
                version=ver,
                parameters=sub_params,
                result_storage="none",
                max_rows=max_rows,
                triggered_by=triggered_by,
                session_key=correlation_id,
            )
        except Exception as exc:  # gate/permission/lookup failures
            return None, type(exc).__name__, None, None
        if outcome.get("status") != "success":
            return None, outcome.get("error_class"), outcome.get("run_id"), None
        value = _first_numeric_from_sample(outcome.get("sample"))
        if value is None:
            return None, "no_numeric_output", outcome.get("run_id"), None
        if outcome.get("truncated"):
            return None, "truncated_not_registerable", outcome.get("run_id"), None
        return value, None, outcome.get("run_id"), outcome.get("data_as_of")

    num_value, num_err, num_run_id, num_as_of = _exec(
        "numerator_query_code", "numerator_query_version"
    )
    den_value, den_err, den_run_id, den_as_of = _exec(
        "denominator_query_code", "denominator_query_version"
    )
    main_value, main_err, main_run_id, main_as_of = _exec("query_code", "query_version")

    if calc_type == "single" and mv.query_code:
        computed = calculate_metric_value(
            numerator=main_value, denominator=None,
            calc_type="single", precision=precision, rounding_mode=rounding,
            numerator_error=main_err,
        )
    else:
        computed = calculate_metric_value(
            numerator=num_value if mv.numerator_query_code else main_value,
            denominator=den_value,
            calc_type=calc_type, precision=precision, rounding_mode=rounding,
            numerator_error=num_err if mv.numerator_query_code else main_err,
            denominator_error=den_err,
        )

    as_of_candidates = [a for a in (num_as_of, den_as_of, main_as_of) if a]
    data_as_of = min(as_of_candidates) if as_of_candidates else None

    run_row.status = computed["status"]
    run_row.main_run_id = main_run_id
    run_row.numerator_run_id = num_run_id
    run_row.denominator_run_id = den_run_id
    run_row.numerator_error = num_err or main_err
    run_row.denominator_error = den_err
    run_row.data_as_of = data_as_of
    run_row.finished_at = datetime.now(timezone.utc)
    run_row.correlation_id = correlation_id
    value = computed.get("value")
    run_row.result_digest = hashlib.sha256(
        json.dumps(
            {"status": computed["status"], "value": str(value) if value is not None else None, "batch": batch},
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()

    # idempotent replay of the same batch returns the existing row (A31)
    existing = db.scalar(
        _sa_select(AssetMetricResult).where(
            AssetMetricResult.metric_code == metric_code,
            AssetMetricResult.version == mv.version,
            AssetMetricResult.period_key == period_key,
            AssetMetricResult.dimensions_hash == dhash,
            AssetMetricResult.parameter_hash == phash,
            AssetMetricResult.run_batch == batch,
        )
    )
    if existing:
        db.flush()
        return {
            "idempotent": True,
            "metric_run_id": run_row.id,
            "result_id": existing.id,
            "status": existing.status,
            "metric_value": existing.metric_value,
            "run_batch": batch,
            "correlation_id": correlation_id,
        }

    row = _register_result(
        db, mv=mv, period_key=period_key, dimensions=dimensions, dhash=dhash,
        phash=phash, parameters=parameters, num_value=num_value, den_value=den_value,
        value=value, status=computed["status"], batch=batch, main_run_id=main_run_id,
        num_run_id=num_run_id, data_as_of=data_as_of, triggered_by=triggered_by,
    )
    db.add(row)
    db.flush()
    return {
        "idempotent": False,
        "metric_run_id": run_row.id,
        "result_id": row.id,
        "status": row.status,
        "metric_value": row.metric_value,
        "numerator": row.numerator_value,
        "denominator": row.denominator_value,
        "run_batch": batch,
        "data_as_of": row.data_as_of.isoformat() if row.data_as_of else None,
        "correlation_id": correlation_id,
    }
