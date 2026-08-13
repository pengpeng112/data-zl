from __future__ import annotations

from datetime import timedelta

import pytest

from scripts.ro_identity_nightly_observe import DEFAULT_OBSERVE_SINCE, parse_observation_since


def test_default_observation_window_is_timezone_aware() -> None:
    value = parse_observation_since(DEFAULT_OBSERVE_SINCE)
    assert value.utcoffset() == timedelta(hours=8)


@pytest.mark.parametrize("value", ["2026-08-11", "2026-08-11T00:00:00", "not-a-date"])
def test_observation_window_rejects_naive_or_invalid_values(value: str) -> None:
    with pytest.raises(ValueError):
        parse_observation_since(value)


def test_observer_bootstraps_application_import_path() -> None:
    from app.services.identity_time import is_after_modified_watermark

    assert callable(is_after_modified_watermark)
