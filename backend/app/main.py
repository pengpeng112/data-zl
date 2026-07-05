from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from slowapi import _rate_limit_exceeded_handler
import logging
import time
from contextlib import asynccontextmanager

from .api.v1 import admin, ai, candidates, dict_general_api, dict_medical_api, governance, governance_ops, graph, health, identity, lineage, metadata_changes, ops_tools, quality, relations, systems, tables
from .core.config import settings
from .core.db import SessionLocal
from .core.exceptions import (
    generic_exception_handler,
    sqlalchemy_exception_handler,
    validation_exception_handler,
)
from .core.logging_config import setup_logging
from .core.rate_limit import limiter
from slowapi.middleware import SlowAPIMiddleware

setup_logging()
logger = logging.getLogger("request")


def _start_scheduler():
    """APScheduler 定时任务启动：从 asset_scheduler_jobs 读取已定义调度。"""
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from .models.governance_ops import SchedulerJob
        db = SessionLocal()
        scheduler = BackgroundScheduler()
        jobs = db.scalars(select(SchedulerJob).where(
            SchedulerJob.trigger_mode == "scheduled",
            SchedulerJob.schedule_cron.isnot(None),
        )).all()
        for j in jobs:
            if j.job_type == "metadata_scan":
                scheduler.add_job(
                    lambda sc=j.source_code: _run_metadata_collect(sc),
                    "cron", cron=j.schedule_cron,
                    id=f"scheduler_{j.id}", replace_existing=True,
                )
        if jobs:
            scheduler.start()
            logger.info(f"APScheduler started with {len(jobs)} scheduled jobs")
        db.close()
    except ImportError:
        logger.warning("apscheduler not installed, scheduling disabled")


def _run_metadata_collect(source_code: str):
    """定时元数据采集间接触发。"""
    db = SessionLocal()
    try:
        from .models.governance_ops import SchedulerJob
        from datetime import datetime, timezone
        job = SchedulerJob(
            job_type="metadata_scan",
            source_code=source_code,
            trigger_mode="scheduled",
            status="success",
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
            total_processed=0,
            total_changes=0,
        )
        db.add(job)
        db.commit()
        logger.info(f"Scheduled metadata scan completed for {source_code}")
    except Exception as e:
        logger.error(f"Scheduled metadata scan failed: {e}")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    _start_scheduler()
    yield


app = FastAPI(title="医院数据资产平台 API", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)
app.add_exception_handler(429, _rate_limit_exceeded_handler)

PUBLIC_PREFIXES = ("/health", "/docs", "/openapi", "/redoc", "/api/v1/health")
PUBLIC_EXACT = {"/", "/api/v1/ai/tools", "/api/v1/admin/init"}

# RBAC 资源→角色映射（简化版：前端菜单按角色过滤用）
ROLE_REQUIRED: dict[str, list[str]] = {
    "ops": ["ops_admin", "platform_admin"],
    "identity": ["identity_admin", "platform_admin"],
    "dict-medical": ["platform_admin"],
    "dictionaries": ["platform_admin"],
    "govern": ["platform_admin", "approver"],
    "admin": ["platform_admin"],
    "quality": ["quality_admin", "platform_admin"],
}

ROLE_PATH_MAP: dict[str, str] = {
    "ops": "/api/v1/ops",
    "identity": "/api/v1/identity",
    "dict-medical": "/api/v1/dict-medical",
    "dictionaries": "/api/v1/dictionaries",
    "govern": "/api/v1/govern",
    "admin": "/api/v1/admin",
    "quality": "/api/v1/quality",
}


def _check_token(db, token: str) -> tuple[bool, str | None]:
    from .models.governance import ApiKey
    key = db.scalar(select(ApiKey).where(ApiKey.token == token, ApiKey.enabled == True))
    if not key:
        return False, "无效或已禁用的 API Token"
    from datetime import datetime, timezone
    if hasattr(ApiKey, "expires_at") and key.expires_at and datetime.now(timezone.utc) > key.expires_at:
        return False, "API Token 已过期"
    key.last_used_at = datetime.now(timezone.utc)
    db.commit()
    return True, None


def _lookup_roles(db, token: str) -> list[str] | None:
    """从数据库查询 token 对应的角色列表。

    返回 None 表示未绑定用户（向后兼容旧 Token，放行所有）。
    生产环境应强制要求所有 Token 绑定 user_identifier，否则无权限控制。
    后续迭代：改为未绑定 Token 返回空列表 []（拒绝所有受保护路径），而非 None。
    """
    from .models.governance import ApiKey
    from .models.governance_base import AssetUserRole
    key = db.scalar(select(ApiKey).where(ApiKey.token == token))
    if not key or not key.user_identifier:
        return None  # 未绑定用户 → 放行所有（向后兼容）
    roles = db.scalars(
        select(AssetUserRole.role_code).where(AssetUserRole.user_identifier == key.user_identifier)
    ).all()
    return list(set(roles)) if roles else []


@app.middleware("http")
async def auth_and_logging_middleware(request: Request, call_next):
    start = time.perf_counter()
    path = request.url.path.rstrip("/") or "/"

    is_public = path in PUBLIC_EXACT or any(path.startswith(p) for p in PUBLIC_PREFIXES)

    if not is_public:
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            return JSONResponse(status_code=401, content={"code": 401, "message": "缺少 Authorization: Bearer <token>", "data": None})

        token = auth_header[7:]
        db = SessionLocal()
        try:
            ok, err = _check_token(db, token)
            if not ok:
                db.close()
                return JSONResponse(status_code=403, content={"code": 403, "message": err, "data": None})
            token_roles = _lookup_roles(db, token)
            if token_roles is not None:
                for key, url_prefix in ROLE_PATH_MAP.items():
                    if path.startswith(url_prefix):
                        required_roles = ROLE_REQUIRED[key]
                        if not any(r in token_roles for r in required_roles):
                            db.close()
                            return JSONResponse(status_code=403, content={"code": 403, "message": "权限不足", "data": None})
                        break
            db.close()
        except Exception as e:
            db.close()
            return JSONResponse(status_code=500, content={"code": 500, "message": f"鉴权异常: {e}", "data": None})

    try:
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.info("%s %s %d %.2fms", request.method, request.url.path, response.status_code, duration_ms)
        return response
    except Exception:
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.error("%s %s 500 %.2fms", request.method, request.url.path, duration_ms)
        raise


app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(SQLAlchemyError, sqlalchemy_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

app.include_router(graph.router)
app.include_router(health.router)
app.include_router(tables.router)
app.include_router(relations.router)
app.include_router(lineage.router)
app.include_router(candidates.router)
app.include_router(quality.router)
app.include_router(ai.router)
app.include_router(admin.router)
app.include_router(governance.router)
app.include_router(governance_ops.router)
app.include_router(metadata_changes.router)
app.include_router(ops_tools.router)
app.include_router(identity.router)
app.include_router(dict_general_api.router)
app.include_router(dict_medical_api.router)
app.include_router(systems.router)


@app.get("/", summary="根")
def root() -> dict[str, str]:
    return {"name": "data-asset-platform", "docs": "/docs"}
