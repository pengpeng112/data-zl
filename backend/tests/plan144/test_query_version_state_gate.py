"""A04: candidate/blocked/superseded versions cannot run by default nor back metrics/products."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.query_runner import ensure_runnable_query_version
from app.services.query_version_ref_guard import validate_version_reference


def _qv(status: str, is_active: bool, version: int = 2):
    return SimpleNamespace(
        query_code="QRY_X", version=version, status=status, is_active=is_active
    )


def test_candidate_cannot_run_by_default():
    with pytest.raises(PermissionError):
        ensure_runnable_query_version(_qv("candidate", True))


def test_blocked_never_runs_even_with_recalc():
    with pytest.raises(PermissionError):
        ensure_runnable_query_version(_qv("blocked", False), recalc=True, recalc_reason="backfill")


def test_candidate_never_runs_even_with_recalc():
    with pytest.raises(PermissionError):
        ensure_runnable_query_version(_qv("candidate", True), recalc=True, recalc_reason="backfill")


def test_superseded_requires_explicit_recalc():
    with pytest.raises(PermissionError):
        ensure_runnable_query_version(_qv("superseded", False))
    # explicit historical recalculation is allowed and recorded
    ensure_runnable_query_version(
        _qv("superseded", False), recalc=True, recalc_reason="2024 backfill"
    )


def test_active_but_not_is_active_rejected():
    with pytest.raises(PermissionError):
        ensure_runnable_query_version(_qv("active", False))


def test_active_current_version_runs():
    ensure_runnable_query_version(_qv("active", True))


def test_recalc_requires_reason():
    with pytest.raises(ValueError):
        ensure_runnable_query_version(_qv("superseded", False), recalc=True, recalc_reason="")


# --- metric activation / product publish reference gates ---------------------


def _resolver(status: str, is_active: bool):
    def resolve(code: str, version: int):
        return _qv(status, is_active, version) if code == "QRY_REF" else None

    return resolve


def test_metric_activation_rejects_blocked_query_ref():
    with pytest.raises(ValueError):
        validate_version_reference(_resolver("blocked", False), "QRY_REF", 1)


def test_metric_activation_rejects_candidate_query_ref():
    with pytest.raises(ValueError):
        validate_version_reference(_resolver("candidate", True), "QRY_REF", 1)


def test_metric_activation_accepts_active_current_ref():
    validate_version_reference(_resolver("active", True), "QRY_REF", 1)


def test_metric_activation_accepts_legacy_unverified_ref_with_flag():
    validate_version_reference(
        _resolver("legacy_unverified", True), "QRY_REF", 1, allow_legacy=True
    )


def test_metric_activation_rejects_legacy_unverified_by_default():
    with pytest.raises(ValueError):
        validate_version_reference(_resolver("legacy_unverified", True), "QRY_REF", 1)


def test_missing_reference_is_rejected():
    with pytest.raises(LookupError):
        validate_version_reference(_resolver("active", True), "QRY_MISSING", 1)
