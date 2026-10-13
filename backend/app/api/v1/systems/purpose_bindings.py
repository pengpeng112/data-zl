"""215 E11 自 systems.py 拆出：数据用途绑定（/api/v1/purpose-bindings*）。"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, field_validator

from ....core.db import get_db
from ....models.asset_system import AssetDataSource
from ....schemas.common import ApiResponse
from ....core.security import get_current_user, require_permission
from ._router import router
from ._shared import _audit


class PurposeBindingUpsert(BaseModel):
    purpose: str = Field(min_length=1, max_length=64)
    write_policy: str = Field(default="identity_account_sync", max_length=64)
    write_credential_ref: str = Field(min_length=1, max_length=255)
    enabled: bool = False
    approval_ref: str | None = Field(default=None, max_length=128)
    description: str | None = Field(default=None, max_length=255)

    @field_validator("purpose")
    @classmethod
    def _purpose_allowed(cls, v: str) -> str:
        allowed = {"identity_account_sync"}
        if v not in allowed:
            raise ValueError(f"purpose must be one of {sorted(allowed)}")
        return v

@router.get(
    "/sources/{source_code}/purpose-bindings",
    summary="用途绑定列表（引用名与状态，不含凭据内容）",
    dependencies=[Depends(require_permission("source:credential_manage"))],
)
def list_purpose_bindings(source_code: str, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    from ...models.asset_system import AssetSourcePurposeBinding

    rows = db.scalars(
        select(AssetSourcePurposeBinding).where(AssetSourcePurposeBinding.source_code == source_code)
    ).all()
    return ApiResponse(data={
        "source_code": source_code,
        "items": [
            {
                "purpose": r.purpose,
                "write_policy": r.write_policy,
                "write_credential_ref": r.write_credential_ref,
                "credential_status": r.credential_status,
                "enabled": bool(r.enabled),
                "approval_ref": r.approval_ref,
                "description": r.description,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            }
            for r in rows
        ],
    })

@router.put(
    "/sources/{source_code}/purpose-bindings/{purpose}",
    dependencies=[Depends(require_permission("source:credential_manage"))],
    summary="登记/更新用途绑定（只登记受控引用名，不接收密码；不覆盖字典推送策略）",
)
def upsert_purpose_binding(
    source_code: str,
    purpose: str,
    req: PurposeBindingUpsert,
    request: Request,
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    from ...models.asset_system import AssetSourcePurposeBinding

    operator = get_current_user(request)
    ds = db.scalar(select(AssetDataSource).where(AssetDataSource.source_code == source_code))
    if not ds:
        raise HTTPException(status_code=404)
    if purpose != req.purpose:
        raise HTTPException(status_code=400, detail="path purpose must match body")

    existing = db.scalar(
        select(AssetSourcePurposeBinding).where(
            AssetSourcePurposeBinding.source_code == source_code,
            AssetSourcePurposeBinding.purpose == purpose,
        )
    )
    before = None
    if existing is not None:
        before = {
            "write_credential_ref": existing.write_credential_ref,
            "credential_status": existing.credential_status,
            "enabled": bool(existing.enabled),
            "approval_ref": existing.approval_ref,
        }
        existing.write_policy = req.write_policy
        existing.write_credential_ref = req.write_credential_ref
        existing.credential_status = "configured"
        existing.enabled = req.enabled
        existing.approval_ref = req.approval_ref
        existing.description = req.description
        existing.updated_at = datetime.now(timezone.utc)
        row = existing
    else:
        row = AssetSourcePurposeBinding(
            source_code=source_code,
            purpose=purpose,
            write_policy=req.write_policy,
            write_credential_ref=req.write_credential_ref,
            credential_status="configured",
            enabled=req.enabled,
            approval_ref=req.approval_ref,
            description=req.description,
        )
        db.add(row)
    _audit(
        db,
        action="purpose_binding_upsert",
        operator=operator,
        entity_ref=f"{source_code}:{purpose}",
        before=before,
        after={
            "write_credential_ref": row.write_credential_ref,
            "credential_status": row.credential_status,
            "enabled": bool(row.enabled),
            "approval_ref": row.approval_ref,
        },
    )
    db.commit()
    return ApiResponse(data={
        "source_code": source_code,
        "purpose": purpose,
        "enabled": bool(row.enabled),
        "credential_status": row.credential_status,
    })

@router.delete(
    "/sources/{source_code}/purpose-bindings/{purpose}",
    dependencies=[Depends(require_permission("source:credential_manage"))],
    summary="停用用途绑定（软关闭：enabled=false 保留登记供审计）",
)
def disable_purpose_binding(
    source_code: str,
    purpose: str,
    request: Request,
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    from ...models.asset_system import AssetSourcePurposeBinding

    operator = get_current_user(request)
    row = db.scalar(
        select(AssetSourcePurposeBinding).where(
            AssetSourcePurposeBinding.source_code == source_code,
            AssetSourcePurposeBinding.purpose == purpose,
        )
    )
    if not row:
        raise HTTPException(status_code=404)
    before = {"enabled": bool(row.enabled)}
    row.enabled = False
    row.updated_at = datetime.now(timezone.utc)
    _audit(
        db,
        action="purpose_binding_disable",
        operator=operator,
        entity_ref=f"{source_code}:{purpose}",
        before=before,
        after={"enabled": False},
    )
    db.commit()
    return ApiResponse(data={"source_code": source_code, "purpose": purpose, "enabled": False})
