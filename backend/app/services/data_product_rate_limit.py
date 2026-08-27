"""144 S4: per (product, caller) rate limiting for data product execution (A18).

Process-local sliding window + concurrency gauge. The platform runs a single
API container, so in-process state is authoritative for the current deploy;
the audit log records rejections for observability.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from typing import Deque

_lock = threading.Lock()
_windows: dict[tuple[str, str], Deque[float]] = defaultdict(deque)
_active: dict[tuple[str, str], int] = defaultdict(int)


class RateLimitExceeded(PermissionError):
    """product+caller quota exceeded (E_LIMIT)."""

    def __init__(self, message: str):
        super().__init__(message)
        self.code = "E_LIMIT"


def check_rate(product_code: str, caller_id: str, *, limit_per_minute: int | None) -> None:
    """Raise RateLimitExceeded when the caller exceeds its window quota."""
    if not limit_per_minute or limit_per_minute <= 0:
        return
    key = (product_code, caller_id or "anonymous")
    now = time.monotonic()
    with _lock:
        window = _windows[key]
        while window and now - window[0] > 60.0:
            window.popleft()
        if len(window) >= limit_per_minute:
            raise RateLimitExceeded(
                f"产品 {product_code} 调用方 {key[1]} 超过每分钟 {limit_per_minute} 次限额"
            )
        window.append(now)


class _ConcurrencyGuard:
    def __init__(self, key: tuple[str, str], max_concurrency: int | None):
        self._key = key
        self._max = max_concurrency

    def __enter__(self):
        if self._max and self._max > 0:
            with _lock:
                if _active[self._key] >= self._max:
                    raise RateLimitExceeded(
                        f"产品 {self._key[0]} 调用方 {self._key[1]} 超过并发 {self._max} 限额"
                    )
                _active[self._key] += 1
        return self

    def __exit__(self, *exc):
        if self._max and self._max > 0:
            with _lock:
                _active[self._key] -= 1
                if _active[self._key] <= 0:
                    _active.pop(self._key, None)
        return False


def concurrency_guard(product_code: str, caller_id: str, *, max_concurrency: int | None):
    return _ConcurrencyGuard((product_code, caller_id or "anonymous"), max_concurrency)


def reset() -> None:
    """Test helper: clear all in-process limit state."""
    with _lock:
        _windows.clear()
        _active.clear()
