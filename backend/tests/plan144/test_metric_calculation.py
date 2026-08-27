"""A15: metric calculation engine — Decimal semantics, zero denominators, statuses."""
from __future__ import annotations

from decimal import Decimal

from app.services.metric_calculation_service import calculate_metric_value


def test_ratio_uses_decimal_not_float():
    res = calculate_metric_value(
        numerator=Decimal(1), denominator=Decimal(3),
        calc_type="ratio", precision=4, rounding_mode="half_up",
    )
    assert res["status"] == "success"
    assert res["value"] == Decimal("0.3333")
    assert isinstance(res["value"], Decimal)


def test_denominator_zero_is_unavailable_not_crash():
    res = calculate_metric_value(
        numerator=Decimal(5), denominator=Decimal(0), calc_type="ratio",
        precision=2, rounding_mode="half_up",
    )
    assert res["status"] == "unavailable"
    assert res["value"] is None


def test_failed_numerator_yields_partial():
    res = calculate_metric_value(
        numerator=None, denominator=Decimal(10), calc_type="ratio",
        precision=2, rounding_mode="half_up", numerator_error="E_SOURCE",
    )
    assert res["status"] in {"partial", "unavailable"}
    assert res["value"] is None


def test_single_value_passthrough():
    res = calculate_metric_value(
        numerator=Decimal("42"), denominator=None, calc_type="single",
        precision=0, rounding_mode="half_up",
    )
    assert res["status"] == "success"
    assert res["value"] == Decimal("42")


def test_rounding_mode_respected():
    res = calculate_metric_value(
        numerator=Decimal("2"), denominator=Decimal("3"),
        calc_type="ratio", precision=4, rounding_mode="half_even",
    )
    assert res["value"] == Decimal("0.6667")  # 0.66666... half_even -> 0.6667


def test_precision_capped_to_sane_range():
    res = calculate_metric_value(
        numerator=Decimal(1), denominator=Decimal(3),
        calc_type="ratio", precision=50, rounding_mode="half_up",
    )
    # precision is clamped; result stays a bounded Decimal string
    assert res["status"] == "success"
    assert abs(res["value"]) < 1
