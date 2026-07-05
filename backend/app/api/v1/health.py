from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from ...core.db import get_db
from ...core.logging_config import get_logger
from ...schemas.common import ApiResponse

logger = get_logger(__name__)
router = APIRouter(tags=["health"])


@router.get("/health", summary="健康检查")
def health(db: Session = Depends(get_db)) -> ApiResponse[dict]:
    db_ok = False
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception as e:
        logger.error("DB health check failed: %s", e)

    status = "ok" if db_ok else "degraded"
    return ApiResponse(
        code=0,
        message="ok" if db_ok else "database unreachable",
        data={
            "status": status,
            "database": "connected" if db_ok else "disconnected",
            "checked_at": datetime.now(timezone.utc).isoformat(),
        },
    )
