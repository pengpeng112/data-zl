"""144 S7 API: answer provenance, feedback loop, evaluation runs, dashboard."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
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
    "/feedback/{feedback_id}",
    summary="144 S7：查询反馈解决状态与新版本引用",
)
def get_feedback_api(feedback_id: int, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    from ...services.ai_feedback_service import get_feedback_status

    row = get_feedback_status(db, feedback_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"feedback 不存在: {feedback_id}")
    return ApiResponse(data=row)


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
