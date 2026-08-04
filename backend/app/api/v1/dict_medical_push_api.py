"""诊断映射推送计划 API（101号 §4.3）。

服务端生成不可篡改计划，禁止客户端传入 SQL/action。
执行只接受 plan_id + 目标系统。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...core.db import get_db
from ...core.security import get_current_user, require_permission
from ...schemas.common import ApiResponse
from ...services.data_masking import sanitize_text
from ...services.dict_medical_push import (
    create_push_plan,
    approve_plan,
    get_plan_summary,
    verify_plan_integrity,
)

router = APIRouter(prefix="/api/v1/dict-medical/push/plans", tags=["dict-medical-push"])


def _dispatch_approved_plan(db: Session, plan_id: int) -> dict:
    """Server-side per-target dispatch, fail-closed.

    Unless APP_DICT_MEDICAL_PUSH_ENABLED is true (it is not during this
   整改), only returns dry-run/reconcile previews and never touches the
    business DB. Target sources must be explicitly named by the server.
    """
    # Kept as a compatibility shim for older callers. Direct dispatch from an
    # HTTP request is forbidden; only the durable worker may call the executor.
    return {"status": "queued", "plan_id": plan_id, "message": "dispatch is worker-only"}

    from ...core.config import settings
    from ...models.dict_medical_push import DictMedicalPushPlan
    from ...services.dict_sync_executor import dispatch_target

    plan = db.get(DictMedicalPushPlan, plan_id)
    if not plan:
        return {"status": "error", "error": "plan not found"}
    if plan.status != "approved":
        return {"status": "error", "error": f"plan status {plan.status} not approved"}
    if not verify_plan_integrity(db, plan):
        return {"status": "error", "error": "plan content hash mismatch; regenerate plan"}
    if not settings.dict_medical_push_enabled:
        return {
            "status": "dry_run_only",
            "message": "APP_DICT_MEDICAL_PUSH_ENABLED=false; dispatch preview only, no business DB write",
            "plan_id": plan_id,
            "target_systems": plan.target_systems,
        }

    results = []
    for target in plan.target_systems or []:
        try:
            r = dispatch_target(
                db,
                plan,
                target,
                his_source_code=settings.dict_medical_his_source_code,
                jhemr_source_code=settings.dict_medical_jhemr_source_code,
                operator=None,
            )
            results.append(r)
        except Exception as e:
            results.append({"target_system": target, "status": "failed", "error": f"dispatch_failed_{type(e).__name__}"})
    return {"status": "dispatched", "results": results}


class CreatePlanRequest(BaseModel):
    category_code: str = "diagnosis"
    target_systems: list[str]
    item_codes: Optional[list[str]] = None
    import_run_id: Optional[int] = None
    action_type: str = "insert"


class ApprovePlanRequest(BaseModel):
    note: Optional[str] = None


@router.post("", summary="创建推送计划（服务端生成）", dependencies=[Depends(require_permission("dict.medical.plan.create"))])
def create_plan(
    req: CreatePlanRequest,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
) -> ApiResponse[dict]:
    if len(req.target_systems) == 0:
        raise HTTPException(status_code=400, detail="至少选择一个目标系统")
    if len(req.target_systems) > 2:
        raise HTTPException(status_code=400, detail="最多两个目标系统")
    if req.item_codes and len(req.item_codes) > 500:
        raise HTTPException(status_code=400, detail="单次最多 500 个编码")
    try:
        plan = create_push_plan(
            db,
            category_code=req.category_code,
            target_systems=req.target_systems,
            item_codes=req.item_codes,
            import_run_id=req.import_run_id,
            created_by=user,
            action_type=req.action_type,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail="invalid_push_plan_request") from e
    return ApiResponse(data=get_plan_summary(db, plan.id))


@router.get("/{plan_id}", summary="查询计划详情")
def get_plan(
    plan_id: int,
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    try:
        summary = get_plan_summary(db, plan_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail="push_plan_not_found") from e
    return ApiResponse(data=summary)


@router.post("/{plan_id}/approve", summary="审批计划", dependencies=[Depends(require_permission("dict.medical.approve"))])
def approve(
    plan_id: int,
    req: ApprovePlanRequest,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
) -> ApiResponse[dict]:
    try:
        plan = approve_plan(db, plan_id, approved_by=user, note=req.note)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="push_plan_approval_rejected") from e
    # 审批事务只持久化 outbox。外部数据库写入必须由独立 worker 消费，
    # 禁止在 HTTP 请求中同步执行，避免超时和同一事件双执行。
    summary = get_plan_summary(db, plan.id)
    summary["dispatch"] = {"status": "queued", "message": "approved plan queued for controlled worker"}
    return ApiResponse(data=summary)


@router.get("/{plan_id}/integrity", summary="验证计划完整性")
def check_integrity(
    plan_id: int,
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    from ...models.dict_medical_push import DictMedicalPushPlan
    plan = db.get(DictMedicalPushPlan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="计划不存在")
    intact = verify_plan_integrity(db, plan)
    return ApiResponse(data={"plan_id": plan_id, "intact": intact, "content_hash": plan.content_hash})


@router.post("/{plan_id}/execute", summary="执行已审批计划（本轮仅 dry-run）", dependencies=[Depends(require_permission("dict.medical.execute"))])
def execute_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
) -> ApiResponse[dict]:
    """101号安全约束：本轮禁止实际执行。仅返回 dry-run 预览。"""
    from ...models.dict_medical_push import DictMedicalPushPlan
    plan = db.get(DictMedicalPushPlan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="计划不存在")
    if plan.status != "approved":
        raise HTTPException(status_code=400, detail=f"计划状态 {plan.status} 不允许执行，需先审批")
    intact = verify_plan_integrity(db, plan)
    if not intact:
        raise HTTPException(status_code=409, detail="计划内容哈希与当前平台数据不一致，请重新生成计划")
    return ApiResponse(data={
        "plan_id": plan_id,
        "status": "dry_run_only",
        "message": "本轮禁止实际执行（101号安全约束）。计划已验证完整，待生产窗口授权后执行。",
        "item_count": plan.item_count,
        "target_systems": plan.target_systems,
    })
