"""诊断映射推送计划 API（101号 §4.3；200 号 D01/D08 整改）。

服务端生成不可篡改计划，禁止客户端传入 SQL/action。
执行只接受 plan_id + 目标系统；实际写入只由受控 worker 执行。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...core.config import settings
from ...core.db import get_db
from ...core.security import get_current_user, require_permission
from ...schemas.common import ApiResponse
from ...services.dict_medical_push import (
    PlanSelectionError,
    approve_plan,
    create_push_plan,
    get_plan_summary,
    verify_plan_integrity,
)

router = APIRouter(prefix="/api/v1/dict-medical/push/plans", tags=["dict-medical-push"])


def _dispatch_approved_plan(db: Session, plan_id: int) -> dict:
    """兼容旧调用方的只读占位（200 D08：清除 return 后不可达旧代码）。

    直接从 HTTP 请求派发被禁止；只有持久化 worker 可调用执行器。
    """
    return {"status": "queued", "plan_id": plan_id, "message": "dispatch is worker-only"}


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
    try:
        plan = create_push_plan(
            db,
            category_code=req.category_code,
            target_systems=req.target_systems,
            item_codes=req.item_codes,
            import_run_id=req.import_run_id,
            created_by=user,
            action_type=req.action_type,
            hospital_no=settings.dict_medical_push_default_hospital_no,
        )
    except PlanSelectionError as e:
        # 200 D08：稳定 reason_code + 中文说明，不再一律笼统 invalid_push_plan_request。
        raise HTTPException(
            status_code=400,
            detail={"reason_code": e.reason_code, "message": e.message},
        ) from e
    return ApiResponse(data=get_plan_summary(db, plan.id))


@router.get("/{plan_id}", summary="查询计划详情", dependencies=[Depends(require_permission("dict.medical.view"))])
def get_plan(
    plan_id: int,
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    try:
        summary = get_plan_summary(db, plan_id)
    except PlanSelectionError as e:
        raise HTTPException(status_code=404, detail={"reason_code": e.reason_code, "message": e.message}) from e
    return ApiResponse(data=summary)


@router.post("/{plan_id}/approve", summary="审批计划（审批即入队，受控 worker 执行）", dependencies=[Depends(require_permission("dict.medical.approve"))])
def approve(
    plan_id: int,
    req: ApprovePlanRequest,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
) -> ApiResponse[dict]:
    try:
        plan = approve_plan(db, plan_id, approved_by=user, note=req.note)
    except PlanSelectionError as e:
        raise HTTPException(status_code=400, detail={"reason_code": e.reason_code, "message": e.message}) from e
    # 审批事务只持久化 outbox。外部数据库写入必须由独立 worker 消费，
    # 禁止在 HTTP 请求中同步执行，避免超时和同一事件双执行。
    summary = get_plan_summary(db, plan.id)
    summary["dispatch"] = {"status": "queued", "message": "approved plan queued for controlled worker"}
    return ApiResponse(data=summary)


@router.get("/{plan_id}/integrity", summary="验证计划完整性", dependencies=[Depends(require_permission("dict.medical.view"))])
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


@router.post("/{plan_id}/execute", summary="执行预览（不写入；实际写入由受控 worker 执行）", dependencies=[Depends(require_permission("dict.medical.execute"))])
def execute_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
) -> ApiResponse[dict]:
    """200 D08：本端点保持"执行预览（不写入）"语义，写入只由 worker 消费
    outbox 完成；按钮/结果文案不得显示为"已下发成功"。"""
    from ...models.dict_medical_push import DictMedicalPushPlan
    plan = db.get(DictMedicalPushPlan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="计划不存在")
    if plan.status != "approved":
        raise HTTPException(status_code=400, detail=f"计划状态 {plan.status} 不允许执行，需先审批")
    intact = verify_plan_integrity(db, plan)
    if not intact:
        raise HTTPException(status_code=409, detail="计划内容哈希与当前平台数据不一致，请重新生成计划")
    worker_enabled = bool(settings.dict_medical_push_enabled)
    return ApiResponse(data={
        "plan_id": plan_id,
        "status": "preview_worker_will_execute" if worker_enabled else "dry_run_only",
        "message": (
            "执行预览（不写入）：计划已验证完整。"
            + ("已审批计划将由受控 worker 从队列执行。" if worker_enabled else "下发开关未启用：尚未执行。")
        ),
        "item_count": plan.item_count,
        "target_systems": plan.target_systems,
        "execution_status": plan.execution_status,
    })
