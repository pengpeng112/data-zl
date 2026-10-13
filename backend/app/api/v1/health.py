from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from ...core.config import settings
from ...core.db import get_db
from ...core.logging_config import get_logger
from ...schemas.common import ApiResponse

logger = get_logger(__name__)
router = APIRouter(tags=["health"])

ALEMBIC_INI = Path(__file__).resolve().parents[3] / "alembic.ini"


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


def _alembic_check(db: Session) -> dict:
    """215 E9：库内 alembic_version 与代码迁移链 head 对拍（只读）。

    迁移未跟上（current != head）只作信息暴露，不改变 /health 的 503 语义
    （503 仍仅由数据库不可用触发）——部署脚本按需消费 match 字段。
    """
    try:
        from alembic.config import Config as AlembicConfig
        from alembic.script import ScriptDirectory

        script = ScriptDirectory.from_config(AlembicConfig(str(ALEMBIC_INI)))
        head = script.get_current_head()
    except Exception as exc:
        logger.warning("alembic head resolve failed: %s", type(exc).__name__)
        return {"status": "unknown", "error_class": type(exc).__name__}
    try:
        current = db.execute(text("SELECT version_num FROM alembic_version")).scalar()
    except Exception as exc:
        logger.warning("alembic_version read failed: %s", type(exc).__name__)
        return {"head": head, "current": None, "match": False, "error_class": type(exc).__name__}
    return {"head": head, "current": current, "match": bool(current and current == head)}


def _worker_heartbeat_summary(db: Session) -> dict:
    """215 E9：worker 心跳汇总（只读现有字段，失败降级为 unavailable）。"""
    from sqlalchemy import func, select

    now = datetime.now(timezone.utc)
    summary: dict = {"quality_runs": {}, "identity_nightly": {}}
    try:
        from ...models.quality_governance import QualityRun

        running = db.scalar(
            select(func.count()).select_from(QualityRun).where(
                QualityRun.status.in_(["running", "waiting_window"])
            )
        ) or 0
        lease_active = db.scalar(
            select(func.count()).select_from(QualityRun).where(
                QualityRun.status.in_(["running", "waiting_window"]),
                QualityRun.lease_expires_at.isnot(None),
                QualityRun.lease_expires_at > now,
            )
        ) or 0
        summary["quality_runs"] = {
            "running_or_waiting": running,
            "lease_active": lease_active,
            "lease_stale": running - lease_active,
        }
    except Exception as exc:
        summary["quality_runs"] = {"status": "unavailable", "error_class": type(exc).__name__}
    try:
        from ...models.identity_sync import IdentitySchedulerRun

        row = db.scalar(
            select(IdentitySchedulerRun).order_by(IdentitySchedulerRun.id.desc()).limit(1)
        )
        if row is None:
            summary["identity_nightly"] = {"last_run": None}
        else:
            heartbeat_age = (
                (now - row.provider_heartbeat_at).total_seconds()
                if row.provider_heartbeat_at is not None else None
            )
            summary["identity_nightly"] = {
                "last_run_id": row.run_id,
                "last_status": row.status,
                "provider_heartbeat_at": row.provider_heartbeat_at.isoformat()
                if row.provider_heartbeat_at else None,
                "provider_heartbeat_age_seconds": heartbeat_age,
            }
    except Exception as exc:
        summary["identity_nightly"] = {"status": "unavailable", "error_class": type(exc).__name__}
    return summary


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
    - 215 E9 扩展：data 内新增 alembic（版本对拍）与 workers（心跳汇总）；
      两段失败只降级标注，不改变 503 语义（503 仍仅由数据库不可用触发）。
    """
    db_ok = False
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception as e:
        logger.error("DB health check failed: %s", e)

    if not db_ok and response is not None:
        response.status_code = 503

    data: dict = {
        "status": "ok" if db_ok else "unavailable",
        "database": "connected" if db_ok else "disconnected",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        **_build_payload(),
    }
    if db_ok:
        data["alembic"] = _alembic_check(db)
        data["workers"] = _worker_heartbeat_summary(db)
    return ApiResponse(
        code=0 if db_ok else 503,
        message="ok" if db_ok else "database unreachable",
        data=data,
    )
