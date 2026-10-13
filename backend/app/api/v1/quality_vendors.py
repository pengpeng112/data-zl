"""207 B2: 质量厂商台账 API（/api/v1/quality-vendors）。

首期院内经办人代录厂商回执：不存凭据、不自动创建外部厂商账号、不外发。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ...core.db import get_db
from ...core.security import require_permission
from ...models.governance_base import GovernAuditLog
from ...models.quality_governance import QualityIssue, QualityVendor

router = APIRouter(prefix="/api/v1/quality-vendors", tags=["quality-vendors"])

STATUSES = ("active", "disabled")


class VendorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    vendor_code: str
    vendor_name: str
    status: str
    contact_note: str | None
    related_system_codes: list[str] | None
    remark: str | None
    lock_version: int = 0
    created_by: str | None
    updated_by: str | None


class VendorCreateRequest(BaseModel):
    vendor_code: str = Field(..., min_length=2, max_length=64)
    vendor_name: str = Field(..., min_length=2, max_length=256)
    status: str = "active"
    contact_note: str | None = None
    related_system_codes: list[str] | None = None
    remark: str | None = None


class VendorPatchRequest(BaseModel):
    expected_lock_version: int
    vendor_name: str | None = None
    status: str | None = None
    contact_note: str | None = None
    related_system_codes: list[str] | None = None
    remark: str | None = None
    reason: str | None = None


@router.get("")
def list_vendors(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
    _user: str = Depends(require_permission("quality.issue.read")),
):
    q = select(QualityVendor)
    if keyword:
        like = f"%{keyword}%"
        q = q.where(or_(QualityVendor.vendor_code.ilike(like), QualityVendor.vendor_name.ilike(like)))
    if status:
        q = q.where(QualityVendor.status == status)
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = db.scalars(
        q.order_by(QualityVendor.vendor_code).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return {"items": [VendorOut.model_validate(r).model_dump() for r in rows],
            "total": total, "page": page, "page_size": page_size}


@router.post("")
def create_vendor(
    req: VendorCreateRequest,
    db: Session = Depends(get_db),
    user: str = Depends(require_permission("quality.vendor.manage")),
):
    if req.status not in STATUSES:
        raise HTTPException(status_code=422, detail=f"非法 status: {req.status}")
    exists = db.scalar(select(QualityVendor).where(QualityVendor.vendor_code == req.vendor_code))
    if exists is not None:
        raise HTTPException(status_code=409, detail=f"vendor_code 已存在: {req.vendor_code}")
    vendor = QualityVendor(**req.model_dump(), created_by=user, updated_by=user)
    db.add(vendor)
    db.add(GovernAuditLog(
        module="quality_governance", entity_type="quality_vendor",
        entity_ref=vendor.vendor_code, action="create",
        after_data={"vendor_name": vendor.vendor_name, "status": vendor.status}, operator=user,
    ))
    db.commit()
    db.refresh(vendor)
    return VendorOut.model_validate(vendor).model_dump()


@router.patch("/{vendor_id}")
def patch_vendor(
    vendor_id: int,
    req: VendorPatchRequest,
    db: Session = Depends(get_db),
    user: str = Depends(require_permission("quality.vendor.manage")),
):
    vendor = db.get(QualityVendor, vendor_id)
    if vendor is None:
        raise HTTPException(status_code=404, detail="vendor not found")
    if req.status is not None and req.status not in STATUSES:
        raise HTTPException(status_code=422, detail=f"非法 status: {req.status}")
    if vendor.lock_version != req.expected_lock_version:
        raise HTTPException(status_code=409, detail="lock_version 冲突")
    payload = req.model_dump(exclude={"expected_lock_version", "reason"}, exclude_none=True)
    before = {"vendor_name": vendor.vendor_name, "status": vendor.status}
    for key, value in payload.items():
        setattr(vendor, key, value)
    vendor.lock_version += 1
    vendor.updated_by = user
    vendor.updated_at = datetime.now(timezone.utc)
    db.add(GovernAuditLog(
        module="quality_governance", entity_type="quality_vendor",
        entity_ref=vendor.vendor_code, action="patch",
        before_data=before, after_data={"vendor_name": vendor.vendor_name, "status": vendor.status},
        operator=user, reason=req.reason,
    ))
    db.commit()
    db.refresh(vendor)
    return VendorOut.model_validate(vendor).model_dump()


@router.get("/{vendor_id}/stats")
def vendor_stats(
    vendor_id: int,
    db: Session = Depends(get_db),
    _user: str = Depends(require_permission("quality.issue.read")),
):
    """厂商统计（§5.2）：未结/逾期/等待天数等，分母可追溯；不以问题数直接排名。"""
    vendor = db.get(QualityVendor, vendor_id)
    if vendor is None:
        raise HTTPException(status_code=404, detail="vendor not found")
    from datetime import date as _date

    issues = db.scalars(
        select(QualityIssue).where(QualityIssue.primary_vendor_code == vendor.vendor_code)
    ).all()
    today = _date.today()
    active = [i for i in issues if i.status not in
              ("resolved", "accepted_risk", "false_positive", "duplicate", "cancelled")]
    overdue = [i for i in active if i.due_at and i.due_at < today]
    waiting = [i for i in active if i.status == "waiting_external"]
    resolved = [i for i in issues if i.status == "resolved"]
    waiting_days: list[int] = []
    for i in waiting:
        if i.vendor_promised_at:
            waiting_days.append(max((today - i.vendor_promised_at).days, 0))
    return {
        "vendor_code": vendor.vendor_code,
        "vendor_name": vendor.vendor_name,
        "total_issues": len(issues),
        "active": len(active),
        "overdue": len(overdue),
        "waiting_external": len(waiting),
        "resolved": len(resolved),
        "recurrence": sum(1 for i in issues if (i.recurrence_no or 0) > 0),
        "avg_wait_days": round(sum(waiting_days) / len(waiting_days), 1) if waiting_days else None,
        "denominator_note": "分母=以该厂商为主责的台账问题（primary_vendor_code 匹配）",
    }
