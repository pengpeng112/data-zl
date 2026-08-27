"""A18: (product, caller) rate/concurrency limits are real (pure logic)."""
from __future__ import annotations

import threading

import pytest

from app.services.data_product_rate_limit import (
    RateLimitExceeded,
    check_rate,
    concurrency_guard,
    reset,
)


@pytest.fixture(autouse=True)
def _clean_limits():
    reset()
    yield
    reset()


def test_rate_limit_blocks_after_quota():
    code = "DP_TEST"
    check_rate(code, "caller-a", limit_per_minute=3)
    check_rate(code, "caller-a", limit_per_minute=3)
    check_rate(code, "caller-a", limit_per_minute=3)
    with pytest.raises(RateLimitExceeded) as err:
        check_rate(code, "caller-a", limit_per_minute=3)
    assert err.value.code == "E_LIMIT"


def test_rate_limit_isolated_per_caller():
    check_rate("DP_TEST", "caller-a", limit_per_minute=1)
    with pytest.raises(RateLimitExceeded):
        check_rate("DP_TEST", "caller-a", limit_per_minute=1)
    # different caller unaffected
    check_rate("DP_TEST", "caller-b", limit_per_minute=1)


def test_rate_limit_isolated_per_product():
    check_rate("DP_A", "caller-a", limit_per_minute=1)
    with pytest.raises(RateLimitExceeded):
        check_rate("DP_A", "caller-a", limit_per_minute=1)
    check_rate("DP_B", "caller-a", limit_per_minute=1)


def test_zero_or_none_limit_disables_check():
    check_rate("DP_TEST", "caller-a", limit_per_minute=0)
    check_rate("DP_TEST", "caller-a", limit_per_minute=None)


def test_concurrency_guard_blocks_when_saturated():
    guard = concurrency_guard("DP_TEST", "caller-a", max_concurrency=1)
    with guard:
        with pytest.raises(RateLimitExceeded):
            with concurrency_guard("DP_TEST", "caller-a", max_concurrency=1):
                pass
    # released after exit
    with concurrency_guard("DP_TEST", "caller-a", max_concurrency=1):
        pass


def test_concurrency_releases_under_exception():
    try:
        with concurrency_guard("DP_TEST", "caller-a", max_concurrency=1):
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    with concurrency_guard("DP_TEST", "caller-a", max_concurrency=1):
        pass


def test_threaded_callers_do_not_starve_each_other():
    """Two callers with independent quotas never cross-block (per-key state)."""
    errors: list[str] = []

    def worker(caller: str) -> None:
        try:
            for _ in range(5):
                check_rate("DP_TEST", caller, limit_per_minute=100)
        except Exception as exc:  # pragma: no cover - only on failure
            errors.append(f"{caller}: {exc}")

    threads = [threading.Thread(target=worker, args=(f"c{i}",)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
