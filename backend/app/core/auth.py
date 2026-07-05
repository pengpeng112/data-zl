from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from ..core.db import get_db
from ..models.governance import ApiKey

PUBLIC_PATHS = {
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/",
    "/api/v1/health",
}


async def auth_dependency(request: Request, db: Session = Depends(get_db)):
    if request.url.path in PUBLIC_PATHS or request.url.path.startswith("/docs") or request.url.path.startswith("/openapi"):
        return None

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="缺少 Authorization: Bearer <token>")

    token = auth_header[7:]
    key = db.scalar(
        select(ApiKey).where(ApiKey.token == token, ApiKey.enabled == True)
    )

    if not key:
        raise HTTPException(status_code=403, detail="无效或已禁用的 API Token")

    key.last_used_at = datetime.now(timezone.utc)
    db.commit()
    return key
