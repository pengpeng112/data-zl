from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from slowapi import _rate_limit_exceeded_handler
import logging
import hashlib
import time
from contextlib import asynccontextmanager

from .api.v1 import admin, ai, auth, candidates, dict_general_api, dict_medical_api, governance, governance_ops, graph, health, identity, lineage, metadata_changes, ops_tools, permissions, quality, recipes, relations, systems, tables
from .core.config import settings
from .core.db import SessionLocal
from .core.exceptions import (
    generic_exception_handler,
    sqlalchemy_exception_handler,
    validation_exception_handler,
)
from .core.logging_config import setup_logging
from .core.rate_limit import limiter
from .services.auth_service import decode_access_token
from slowapi.middleware import SlowAPIMiddleware

setup_logging()
logger = logging.getLogger("request")


def _start_scheduler():
    """APScheduler 定时任务启动：从 asset_scheduler_jobs 读取已定义调度。"""
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
        from .models.governance_ops import SchedulerJob
        db = SessionLocal()
        scheduler = BackgroundScheduler(timezone=settings.scheduler_timezone)
        jobs = db.scalars(select(SchedulerJob).where(
            SchedulerJob.trigger_mode == "scheduled",
            SchedulerJob.schedule_cron.isnot(None),
        )).all()
        for j in jobs:
            try:
                trigger = CronTrigger.from_crontab(
                    j.schedule_cron,
                    timezone=settings.scheduler_timezone,
                )
            except ValueError:
                logger.error("Skipping scheduler job %s: invalid cron", j.id)
                continue
            if j.job_type == "metadata_scan":
                scheduler.add_job(
                    _run_metadata_collect,
                    trigger=trigger,
                    args=[j.source_code],
                    id=f"scheduler_{j.id}", replace_existing=True,
                )
        if jobs:
            scheduler.start()
            logger.info(f"APScheduler started with {len(jobs)} scheduled jobs in %s", settings.scheduler_timezone)
        db.close()
    except ImportError:
        logger.warning("apscheduler not installed, scheduling disabled")


def _run_metadata_collect(source_code: str):
    """Run the same collector used by the manual metadata endpoint."""
    db = SessionLocal()
    from datetime import datetime, timezone
    from .models.governance_ops import SchedulerJob
    job = SchedulerJob(
        job_type="metadata_scan", source_code=source_code, trigger_mode="scheduled",
        status="running", started_at=datetime.now(timezone.utc), total_processed=0, total_changes=0,
    )
    try:
        db.add(job)
        db.commit()
        from .api.v1.metadata_changes import _collect_metadata_snapshot
        result = _collect_metadata_snapshot(
            source_code,
            f"scheduled {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}",
            db,
        )
        job.status = "success"
        job.finished_at = datetime.now(timezone.utc)
        job.total_processed = result.get("table_count", 0)
        job.result_ref = str(result)
        db.commit()
        logger.info("Scheduled metadata scan completed for %s", source_code)
    except Exception as e:
        db.rollback()
        job.status = "failed"
        job.finished_at = datetime.now(timezone.utc)
        job.error_message = str(e)[:500]
        db.add(job)
        db.commit()
        logger.error("Scheduled metadata scan failed for %s: %s", source_code, e)
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
PUBLIC_EXACT = {
    "/",
    "/api/v1/ai/tools",
    "/api/v1/auth/login",
    "/api/v1/auth/refresh",
    # pure-admin 动态路由占位：本平台菜单用前端静态 modules，返回空数组
    "/get-async-routes",
}

# 管理写接口 / 高权限模块：默认拒绝，必须显式拥有角色（L9）
# graph/lineage/candidates/tables/systems 等只读资产浏览仅需有效 Token。
ROLE_REQUIRED: dict[str, list[str]] = {
    "ops": ["ops_admin", "platform_admin"],
    "identity": ["identity_admin", "platform_admin"],
    "permissions": ["identity_admin", "platform_admin"],
    "dict-medical": ["platform_admin"],
    "dictionaries": ["platform_admin"],
    "govern": ["platform_admin", "approver"],
    "admin": ["platform_admin"],
    "quality": ["quality_admin", "platform_admin"],
    "relations": ["platform_admin", "approver"],
    "recipes": ["platform_admin"],
    "ai": ["platform_admin", "quality_admin"],
    "auth": ["platform_admin", "identity_admin"],
}

ROLE_PATH_MAP: dict[str, str] = {
    "ops": "/api/v1/ops",
    "identity": "/api/v1/identity",
    "permissions": "/api/v1/permissions",
    "dict-medical": "/api/v1/dict-medical",
    "dictionaries": "/api/v1/dictionaries",
    "govern": "/api/v1/govern",
    "admin": "/api/v1/admin",
    "quality": "/api/v1/quality",
    "relations": "/api/v1/relations",
    "recipes": "/api/v1/recipes",
    "ai": "/api/v1/ai",
    # 本地账号管理与登录审计（login/refresh/me/logout/change-password 另见白名单）
    "auth": "/api/v1/auth",
}

# 已认证即可访问的自服务端点（不要求 admin 角色）
AUTH_SELF_SERVICE_EXACT = {
    "/api/v1/auth/me",
    "/api/v1/auth/logout",
    "/api/v1/auth/change-password",
    "/api/v1/permissions/me",
}


def _check_token(db, token: str) -> tuple[bool, str | None, object | None]:
    """Validate opaque API key. Returns (ok, error, key_row)."""
    from .models.governance import ApiKey
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    key = db.scalar(
        select(ApiKey).where(
            ApiKey.enabled == True,
            (ApiKey.token_hash == token_hash) | (ApiKey.token == token),
        )
    )
    if not key:
        return False, "无效或已禁用的 API Token", None
    from datetime import datetime, timezone
    if hasattr(ApiKey, "expires_at") and key.expires_at and datetime.now(timezone.utc) > key.expires_at:
        return False, "API Token 已过期", None
    # Remove a legacy plaintext token after it has been authenticated once.
    if not key.token_hash:
        key.token_hash = token_hash
        key.token = None
    key.last_used_at = datetime.now(timezone.utc)
    db.commit()
    return True, None, key


def _lookup_roles(db, user_identifier: str | None) -> list[str]:
    """Return roles for a bound user; unbound credentials have no elevated permissions."""
    from .models.governance_base import AssetUserRole
    if not user_identifier:
        return []
    roles = db.scalars(
        select(AssetUserRole.role_code).where(AssetUserRole.user_identifier == user_identifier)
    ).all()
    return list(set(roles)) if roles else []


def _enforce_rbac(path: str, method: str, token_roles: list[str]) -> str | None:
    """
    L9: 高权限 URL 前缀默认拒绝；未绑定角色的 Token 不得访问管理写模块。
    写方法（POST/PUT/PATCH/DELETE）在受控前缀上同样默认拒绝。
    """
    if path in AUTH_SELF_SERVICE_EXACT:
        return None
    if path in {"/api/v1/auth/login", "/api/v1/auth/refresh", "/get-async-routes"}:
        return None

    method_u = (method or "GET").upper()
    for role_key, url_prefix in ROLE_PATH_MAP.items():
        if not path.startswith(url_prefix):
            continue
        if role_key == "auth" and path in AUTH_SELF_SERVICE_EXACT:
            return None
        required_roles = ROLE_REQUIRED[role_key]
        # 生产强制绑定：无角色一律拒绝
        if settings.rbac_require_bound_token and not token_roles:
            return "权限不足：Token 未绑定用户角色"
        # 默认拒绝：高权限模块必须命中角色
        if not any(r in token_roles for r in required_roles):
            return "权限不足"
        break

    # 额外：对只读资产前缀的写操作，要求至少绑定任意业务角色或 platform_admin
    write_methods = {"POST", "PUT", "PATCH", "DELETE"}
    readonly_prefixes = (
        "/api/v1/tables",
        "/api/v1/graph",
        "/api/v1/lineage",
        "/api/v1/candidates",
        "/api/v1/summary",
        "/api/v1/columns",
    )
    if method_u in write_methods and any(path.startswith(p) for p in readonly_prefixes):
        if not token_roles:
            return "权限不足：写操作需要绑定角色"
    return None


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
            # 双凭证：先尝试 JWT（人类登录），失败再回退 ApiKey（机器/部署）
            jwt_payload = decode_access_token(token)
            if jwt_payload:
                request.state.user_identifier = jwt_payload.get("user_identifier") or jwt_payload.get("username")
                request.state.auth_user_id = jwt_payload.get("sub")
                request.state.auth_via = "jwt"
                token_roles = list(jwt_payload.get("roles") or [])
                # JWT 内嵌 roles 可能过期；DB 有角色则以库为准补全
                if request.state.user_identifier:
                    db_roles = _lookup_roles(db, request.state.user_identifier)
                    if db_roles:
                        token_roles = db_roles
                request.state.roles = token_roles
            else:
                ok, err, key = _check_token(db, token)
                if not ok:
                    db.close()
                    return JSONResponse(status_code=403, content={"code": 403, "message": err, "data": None})
                request.state.user_identifier = key.user_identifier if key else None
                request.state.auth_via = "api_key"
                token_roles = _lookup_roles(db, request.state.user_identifier)
                request.state.roles = token_roles

            rbac_err = _enforce_rbac(path, request.method, token_roles)
            if rbac_err:
                db.close()
                return JSONResponse(status_code=403, content={"code": 403, "message": rbac_err, "data": None})
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

app.include_router(auth.router)
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
app.include_router(permissions.router)
app.include_router(identity.router)
app.include_router(dict_general_api.router)
app.include_router(dict_medical_api.router)
app.include_router(systems.router)
app.include_router(recipes.router)

@app.get("/", summary="根")
def root() -> dict[str, str]:
    return {"name": "data-asset-platform", "docs": "/docs"}


@app.get("/get-async-routes", summary="前端动态路由占位（返回空，使用静态菜单）")
def get_async_routes() -> dict:
    """兼容 pure-admin 模板；本平台不从后端下发动态菜单。"""
    return {"success": True, "data": []}
