from slowapi import Limiter
from slowapi.util import get_remote_address

from .config import settings


def _enabled() -> bool:
    # env=test 默认关闭，避免 TestClient 共享 IP 触发 429
    if (settings.env or "").lower() in {"test", "testing", "pytest"}:
        return False
    return bool(settings.rate_limit_enabled)


limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200/day", "50/hour"],
    enabled=_enabled(),
)
