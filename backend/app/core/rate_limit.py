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
    # D7 防回归提示：实测（2026-08-26 两轮 60 连打）中间件模式下 default_limits
    # 不作用于未装饰路由（/api/v1/health 全部 200），装饰路由正常限流（login
    # 第 6/7 次请求 429）。升级 slowapi 版本必须复测该行为，防止默认限流
    # 突然作用于全部路由导致生产 429。
    default_limits=["200/day", "50/hour"],
    enabled=_enabled(),
)
