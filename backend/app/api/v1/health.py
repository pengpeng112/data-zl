from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from ...core.config import settings
from ...core.db import get_db
from ...core.logging_config import get_logger
from ...schemas.common import ApiResponse

logger = get_logger(__name__)
router = APIRouter(tags=["health"])


def _build_payload() -> dict:
    """版本信息（脱敏，不含秘密）：build_id/git_sha/frontend_build_id。"""
    return {
        "build_id": settings.build_id or "dev-local",
        "git_sha": settings.git_sha or "",
        "frontend_build_id": settings.frontend_build_id or "",
    }


def _live_payload() -> dict:
    payload = {"status": "alive", "checked_at": datetime.now(timezone.utc).isoformat()}
    payload.update(_build_payload())
    return payload


@router.get("/health/live", summary="存活检查（liveness，不依赖数据库）")
@router.get("/api/v1/health/live", summary="存活检查（经 Nginx /api 反代）", include_in_schema=False)
def health_live() -> ApiResponse[dict]:
    """进程存活即返回 200，供 systemd 判断应用是否需要重启。不检查数据库。"""
    return ApiResponse(code=0, message="ok", data=_live_payload())


@router.get("/health", summary="就绪检查（readiness，依赖数据库）")
@router.get("/api/v1/health", summary="就绪检查（经 Nginx /api 反代，前端 SPA 使用）", include_in_schema=False)
def health(db: Session = Depends(get_db), response: Response = None) -> ApiResponse[dict]:
    """数据库可用才返回 200；数据库不可用时返回 HTTP 503，供部署脚本和负载均衡判断就绪状态。

    注意：
    - 容器内探活仍可用 `GET /health`（不经 Nginx）。
    - 浏览器经 Nginx 只能访问 `/api/*`，因此提供 `/api/v1/health` 别名。
    - 部署脚本须 `curl --fail` 才能识别 503 为未就绪。
    """
    db_ok = False
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception as e:
        logger.error("DB health check failed: %s", e)

    if not db_ok and response is not None:
        response.status_code = 503

    return ApiResponse(
        code=0 if db_ok else 503,
        message="ok" if db_ok else "database unreachable",
        data={
            "status": "ok" if db_ok else "unavailable",
            "database": "connected" if db_ok else "disconnected",
            "checked_at": datetime.now(timezone.utc).isoformat(),
            **_build_payload(),
        },
    )
