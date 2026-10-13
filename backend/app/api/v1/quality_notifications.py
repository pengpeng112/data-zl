"""207 B2: 站内质量待办 API（/api/v1/quality-notifications）。

只站内送达院内人员；不外发微信/邮件/第三方工单。当前用户只看本人
（经办/负责/督办身份命中的接收人），管理员池待办用 __pool__ 前缀。
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ...core.db import get_db
from ...core.security import require_permission
from ...models.quality_governance import QualityNotification
from ...services import quality_execution_service as qes

router = APIRouter(prefix="/api/v1/quality-notifications", tags=["quality-notifications"])


def _serialize(n: QualityNotification) -> dict:
    return {
        "id": n.id,
        "issue_id": n.issue_id,
        "run_id": n.run_id,
        "recipient": n.recipient,
        "notify_type": n.notify_type,
        "payload": n.payload,
        "read_at": n.read_at.isoformat() if n.read_at else None,
        "handled_at": n.handled_at.isoformat() if n.handled_at else None,
        "handled_note": n.handled_note,
        "created_at": n.created_at.isoformat() if n.created_at else None,
    }


@router.get("")
def list_my_notifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    unread_only: bool = False,
    db: Session = Depends(get_db),
    user: str = Depends(require_permission("quality.notification.read")),
):
    q = select(QualityNotification).where(
        or_(
            QualityNotification.recipient == user,
            QualityNotification.recipient == qes.NOTIFY_POOL_RECIPIENT,
        )
    )
    if unread_only:
        q = q.where(QualityNotification.read_at.is_(None))
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = db.scalars(
        q.order_by(QualityNotification.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    unread = db.scalar(
        select(func.count()).select_from(
            select(QualityNotification)
            .where(
                or_(QualityNotification.recipient == user,
                    QualityNotification.recipient == qes.NOTIFY_POOL_RECIPIENT),
                QualityNotification.read_at.is_(None),
            ).subquery()
        )
    ) or 0
    return {"items": [_serialize(r) for r in rows], "total": total,
            "unread": unread, "page": page, "page_size": page_size}


@router.post("/{notification_id}/read")
def mark_read(
    notification_id: int,
    db: Session = Depends(get_db),
    user: str = Depends(require_permission("quality.notification.read")),
):
    n = db.get(QualityNotification, notification_id)
    if n is None:
        raise HTTPException(status_code=404, detail="notification not found")
    if n.recipient != user and n.recipient != qes.NOTIFY_POOL_RECIPIENT:
        raise HTTPException(status_code=403, detail="该待办不是发给当前用户的")
    if n.read_at is None:
        n.read_at = datetime.now(timezone.utc)
        db.commit()
    return _serialize(n)


@router.post("/read-all")
def mark_all_read(
    db: Session = Depends(get_db),
    user: str = Depends(require_permission("quality.notification.read")),
):
    rows = db.scalars(
        select(QualityNotification).where(
            or_(QualityNotification.recipient == user,
                QualityNotification.recipient == qes.NOTIFY_POOL_RECIPIENT),
            QualityNotification.read_at.is_(None),
        )
    ).all()
    now = datetime.now(timezone.utc)
    for n in rows:
        n.read_at = now
    db.commit()
    return {"ok": True, "marked": len(rows)}


class ScanRequest(BaseModel):
    today: str | None = None  # YYYY-MM-DD；缺省今天（隔离验收注入固定日期用）


@router.post("/scan")
def run_scan(
    req: ScanRequest | None = None,
    db: Session = Depends(get_db),
    user: str = Depends(require_permission("quality.vendor.manage")),
):
    """临期/逾期/厂商逾期扫描（幂等）。生产由调度触发；此处供管理员手动兜底。"""
    from datetime import date

    req = req or ScanRequest()
    today = date.fromisoformat(req.today) if req.today else None
    created = qes.scan_due_notifications(db, today=today)
    db.commit()
    return {"ok": True, "created": created}
