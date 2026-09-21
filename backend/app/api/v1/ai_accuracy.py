"""144 S7 API: answer provenance, feedback loop, evaluation runs, dashboard."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...core.db import get_db
from ...core.security import require_permission
from ...schemas.common import ApiResponse

router = APIRouter(prefix="/api/v1/ai", tags=["ai-accuracy"])


class AnswerEventRequest(BaseModel):
    question_summary: str = Field(..., min_length=3, max_length=500)
    caller_id: str = Field("unknown", max_length=64)
    model_version: str | None = Field(None, max_length=64)
    context_id: str | None = None
    query_code: str | None = None
    query_version: int | None = None
    metric_code: str | None = None
    metric_version: int | None = None
    product_code: str | None = None
    run_id: int | None = None
    result_digest: str | None = None
    answer_text: str | None = Field(None, max_length=4000, description="仅存 digest 与脱敏摘要")


@router.post("/answers", summary="144 S7：登记 AI 回答 provenance（不保存敏感全文）")
def register_answer(req: AnswerEventRequest, request: Request, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    from ...services.ai_feedback_service import register_answer_event

    result = register_answer_event(
        db,
        question_summary=req.question_summary,
        caller_id=req.caller_id,
        model_version=req.model_version,
        context_id=req.context_id,
        query_code=req.query_code,
        query_version=req.query_version,
        metric_code=req.metric_code,
        metric_version=req.metric_version,
        product_code=req.product_code,
        run_id=req.run_id,
        result_digest=req.result_digest,
        answer_text=req.answer_text,
    )
    db.commit()
    return ApiResponse(data=result)


class FeedbackRequest(BaseModel):
    answer_event_id: int
    rating: str
    error_types: list[str] | None = None
    comment: str | None = Field(None, max_length=1000)
    suggested_revision: str | None = Field(None, max_length=4000)


@router.post(
    "/feedback",
    summary="144 S7：提交绑定版本/run/context 的准确性反馈",
    dependencies=[Depends(require_permission("feedback:create"))],
)
def submit_feedback_api(req: FeedbackRequest, request: Request, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    from ...services.ai_feedback_service import submit_feedback

    try:
        result = submit_feedback(
            db,
            answer_event_id=req.answer_event_id,
            rating=req.rating,
            error_types=req.error_types,
            comment=req.comment,
            suggested_revision=req.suggested_revision,
            submitted_by=getattr(request.state, "user_identifier", None),
        )
        db.commit()
    except LookupError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ApiResponse(data=result)


class FeedbackReviewRequest(BaseModel):
    action: str
    review_note: str | None = None
    revision_query_code: str | None = None
    revision_query_version: int | None = None


@router.patch(
    "/feedback/{feedback_id}/review",
    summary="144 S7：审核反馈（状态机：不自动发布任何资产）",
    dependencies=[Depends(require_permission("feedback:review"))],
)
def review_feedback_api(
    feedback_id: int, req: FeedbackReviewRequest, request: Request, db: Session = Depends(get_db)
) -> ApiResponse[dict]:
    from ...services.ai_feedback_service import review_feedback

    try:
        result = review_feedback(
            db,
            feedback_id=feedback_id,
            action=req.action,
            reviewed_by=getattr(request.state, "user_identifier", None),
            review_note=req.review_note,
            revision_query_code=req.revision_query_code,
            revision_query_version=req.revision_query_version,
        )
        db.commit()
    except LookupError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ApiResponse(data=result)


@router.get(
    "/feedback",
    summary="186 Q2：反馈分页列表（mine=本人历史 / queue=审核队列）",
)
def list_feedback_api(
    request: Request,
    scope: str = Query("mine", pattern="^(mine|queue)$"),
    status: str | None = Query(None),
    query_code: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    """§4.4 契约：先过 /api/v1/ai 前缀角色门禁（main.py），再要求
    feedback:create（mine）或 feedback:review（queue）。列表不修改任何
    反馈/回答/审核状态；submitted_at DESC 分页。"""
    from ...core.security import _effective_role_codes, get_current_user
    from ...models.governance_base import AssetRolePermission
    from ...services.ai_feedback_service import list_feedback

    def _has(code: str) -> bool:
        user_identifier = get_current_user(request)
        role_codes = _effective_role_codes(db, user_identifier)
        if "platform_admin" in role_codes:
            return True
        rows = db.scalars(
            select(AssetRolePermission).where(
                AssetRolePermission.role_code.in_(role_codes)
            )
        ).all() if role_codes else []
        from ...core.security import _permission_matches

        granted = [
            f"{row.resource}:{row.action}" if row.action not in (None, "", "access", "*") else row.resource
            for row in rows
        ]
        return any(_permission_matches(item, code) for item in granted)

    has_review = _has("feedback:review")
    has_create = _has("feedback:create")
    if not (has_review or has_create):
        raise HTTPException(status_code=403, detail="缺少权限: feedback:create 或 feedback:review")
    current_user = getattr(request.state, "user_identifier", None)

    try:
        result = list_feedback(
            db,
            current_user=current_user,
            has_review_permission=has_review,
            scope=scope,
            status=status,
            query_code=query_code,
            page=page,
            page_size=page_size,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ApiResponse(data=result)


@router.get(
    "/feedback/{feedback_id}",
    summary="144 S7：查询反馈解决状态与新版本引用",
)
def get_feedback_api(
    feedback_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    """186 Q2：单条读取先鉴权再查范围——本人提交或持 feedback:review；
    范围外统一 404（避免 ID 枚举泄露），不删除既有前缀角色门禁。"""
    from ...core.security import _effective_role_codes, get_current_user
    from ...models.governance_base import AssetRolePermission
    from ...models.ai_accuracy import AssetAiFeedback
    from ...services.ai_feedback_service import feedback_readable_by, get_feedback_status

    row = db.get(AssetAiFeedback, feedback_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"feedback 不存在: {feedback_id}")

    user_identifier = get_current_user(request)
    role_codes = _effective_role_codes(db, user_identifier)
    has_review = "platform_admin" in role_codes
    if not has_review and role_codes:
        from ...core.security import _permission_matches

        rows = db.scalars(
            select(AssetRolePermission).where(
                AssetRolePermission.role_code.in_(role_codes)
            )
        ).all()
        granted = [
            f"{r.resource}:{r.action}" if r.action not in (None, "", "access", "*") else r.resource
            for r in rows
        ]
        has_review = any(_permission_matches(item, "feedback:review") for item in granted)

    if not feedback_readable_by(
        row, current_user=getattr(request.state, "user_identifier", None), has_review_permission=has_review
    ):
        raise HTTPException(status_code=404, detail=f"feedback 不存在: {feedback_id}")
    status = get_feedback_status(db, feedback_id)
    return ApiResponse(data=status)


class EvaluationRunRequest(BaseModel):
    query_code: str | None = None
    query_version: int | None = None
    evaluation_set_version: str | None = None


@router.post(
    "/evaluations/run",
    summary="144 S7：对候选或现行版本回放受影响黄金用例",
    dependencies=[Depends(require_permission("evaluation:run"))],
)
def run_evaluation_api(req: EvaluationRunRequest, request: Request, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    from ...services.query_evaluation_service import run_evaluation

    result = run_evaluation(
        db,
        query_code=req.query_code,
        query_version=req.query_version,
        evaluation_set_version=req.evaluation_set_version,
        triggered_by=getattr(request.state, "user_identifier", None) or "api",
    )
    db.commit()
    return ApiResponse(data=result)


@router.get(
    "/evaluations/dashboard",
    summary="144 S7：准确性看板（只统计已审核反馈与黄金用例）",
)
def dashboard_api(db: Session = Depends(get_db)) -> ApiResponse[dict]:
    from ...services.query_evaluation_service import accuracy_dashboard

    return ApiResponse(data=accuracy_dashboard(db))
