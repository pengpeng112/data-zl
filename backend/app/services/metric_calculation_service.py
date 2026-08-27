"""144 S4: metric calculation engine core + orchestration (144 §4.3).

Deterministic Decimal arithmetic for numerator/denominator/single values;
zero denominators and failed inputs yield unavailable/partial — never a
disguised number.
"""
from __future__ import annotations

import decimal
import hashlib
import json
from datetime import datetime, timezone
from typing import Any

ENGINE_VERSION = "metric-engine/v1"

MIN_PRECISION = 0
MAX_PRECISION = 12

_ROUNDING_MODES = {
    "half_up": decimal.ROUND_HALF_UP,
    "half_even": decimal.ROUND_HALF_EVEN,
    "floor": decimal.ROUND_FLOOR,
    "ceiling": decimal.ROUND_CEILING,
}


def _to_decimal(value: Any) -> decimal.Decimal:
    if isinstance(value, decimal.Decimal):
        return value
    if isinstance(value, bool):
        raise ValueError("布尔值不是合法指标数值")
    if isinstance(value, int):
        return decimal.Decimal(value)
    if isinstance(value, float):
        return decimal.Decimal(repr(value))
    if isinstance(value, str):
        try:
            return decimal.Decimal(value)
        except decimal.InvalidOperation as exc:
            raise ValueError(f"无法解析为 Decimal: {value!r}") from exc
    raise ValueError(f"不支持的指标数值类型: {type(value).__name__}")


def _clamp_precision(precision: Any) -> int:
    try:
        p = int(precision)
    except (TypeError, ValueError):
        p = 2
    return max(MIN_PRECISION, min(p, MAX_PRECISION))


def calculate_metric_value(
    *,
    numerator: Any,
    denominator: Any,
    calc_type: str = "ratio",
    precision: int = 2,
    rounding_mode: str = "half_up",
    numerator_error: str | None = None,
    denominator_error: str | None = None,
) -> dict[str, Any]:
    """Compute one metric value with Decimal semantics and honest statuses.

    status: success | unavailable | partial
      - denominator 0 → unavailable (never fabricate)
      - any sub-input failed → partial (or unavailable when nothing computable)
    """
    calc = (calc_type or "ratio").lower()
    if calc not in {"single", "ratio", "sum"}:
        raise ValueError(f"不支持的指标计算类型: {calc_type}")
    if rounding_mode not in _ROUNDING_MODES:
        raise ValueError(f"不支持的舍入模式: {rounding_mode}")
    exp = decimal.Context(prec=28)
    prec = _clamp_precision(precision)
    mode = _ROUNDING_MODES[rounding_mode]
    quant = decimal.Decimal(1).scaleb(-prec)

    def _q(value: decimal.Decimal) -> decimal.Decimal:
        # Decimal.quantize carries the rounding mode; context bounds precision
        return value.quantize(quant, rounding=mode, context=exp)

    num_failed = numerator is None or bool(numerator_error)
    den_failed = denominator is None or bool(denominator_error)

    if calc == "single":
        if num_failed:
            return {
                "status": "partial" if numerator_error else "unavailable",
                "value": None,
                "reason": numerator_error or "numerator_missing",
            }
        value = _to_decimal(numerator)
        return {
            "status": "success",
            "value": _q(value),
        }

    # ratio / sum need both inputs
    if num_failed or den_failed:
        reason = numerator_error or denominator_error or "input_missing"
        return {"status": "partial", "value": None, "reason": reason}

    num = _to_decimal(numerator)
    den = _to_decimal(denominator)
    if calc == "sum":
        value = num + den
    else:
        if den == 0:
            return {
                "status": "unavailable",
                "value": None,
                "reason": "denominator_zero",
            }
        value = num / den
    return {
        "status": "success",
        "value": _q(value),
    }
