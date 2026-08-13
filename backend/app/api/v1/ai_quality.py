from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from ...core.config import settings
from ...core.db import get_db
from ...core.security import get_current_user, require_permission
from ...models.asset import AssetColumn, AssetTable
from ...models.governance_base import GovernAuditLog
from ...models.quality import (AiQualityJob, AiQualityJobFinding, AiQualityResult,
                               QualityCheckRun, QualityFinding, QualityRule)
from ...schemas.ai_quality import (AiQualityAttachRequest, AiQualityCreateRequest,
                                   AiQualityJobItem, AiQualityPreviewRequest,
                                   AiQualityResultItem, AiQualityReviewRequest)
from ...schemas.common import ApiResponse, PageData
from ...services.ai_quality_payload import build_payload
from ...services.ai_quality_result import output_digest, validate_output
from ...services.dify_quality_client import DifyClientError, DifyQualityClient

router = APIRouter(prefix="/api/v1/quality/ai", tags=["quality-ai"])
INPUT_SCHEMA = "quality-analysis-input/v1"


def _audit(db, action, entity, ref, operator, after=None):
    db.add(GovernAuditLog(module="quality_ai", entity_type=entity, entity_ref=str(ref), action=action,
                          operator=operator, after_data=after or {}))


def _finding_payload(db: Session, ids: list[int]) -> dict:
    if len(ids) != len(set(ids)):
        raise HTTPException(422, "duplicate finding_id")
    rows = list(db.scalars(select(QualityFinding).where(QualityFinding.id.in_(ids))).all())
    if len(rows) != len(ids):
        raise HTTPException(404, "finding not found")
    rows.sort(key=lambda row: row.id)
    rule_codes = {row.rule_code for row in rows if row.rule_code}
    rules = {
        row.rule_code: row
        for row in db.scalars(select(QualityRule).where(QualityRule.rule_code.in_(rule_codes))).all()
    } if rule_codes else {}
    # Only columns explicitly approved by the contract are copied. detail/sample_data are unreachable.
    findings = []
    for r in rows:
        rule = rules.get(r.rule_code)
        findings.append({"finding_id": r.id, "run_id": r.run_id, "rule_code": r.rule_code,
        "rule_name": getattr(rule, "rule_name", None), "rule_type": getattr(rule, "rule_type", None),
        "rule_category": getattr(rule, "rule_category", None),
        "business_domain": getattr(rule, "business_domain", None),
        "target_type": r.target_type, "target_ref": r.target_ref, "system_code": r.system_code,
        "source_code": r.source_code, "namespace_name": r.namespace_name, "schema_name": r.schema_name,
        "table_name": r.table_name,
        "column_name": r.column_name, "severity": r.severity, "status": r.status,
        "metric_value": r.metric_value, "total_cnt": r.total_cnt, "error_cnt": r.error_cnt,
        "error_rate": r.error_rate})
    return {"findings": findings}


def _build_source_payload(req, db: Session) -> dict:
    if req.task_type == "finding":
        if len(req.finding_ids) != 1 or req.run_id is not None:
            raise HTTPException(422, "finding requires exactly one finding_id")
        return _finding_payload(db, req.finding_ids)
    if req.task_type == "finding_batch":
        if not 2 <= len(req.finding_ids) <= settings.dify_max_findings_per_job or req.run_id is not None:
            raise HTTPException(422, "finding_batch requires 2-50 finding_ids")
        data = _finding_payload(db, req.finding_ids)["findings"]
        # A batch is intentionally stricter than a visual grouping: every
        # finding must have a complete, identical physical/rule scope.
        keys = {(x.get("system_code"), x.get("source_code"), x.get("namespace_name") or "",
                 x.get("schema_name") or "", x.get("table_name"), x.get("rule_code")) for x in data}
        if len(keys) != 1 or any(not k[0] or not k[1] or not k[3] or not k[4] or not k[5] for k in keys):
            raise HTTPException(422, "finding_batch must share system/source/schema/table/rule")
        return {"findings": data}
    if req.finding_ids or req.run_id is None:
        raise HTTPException(422, "run_summary requires run_id and no finding_ids")
    run = db.get(QualityCheckRun, req.run_id)
    if not run:
        raise HTTPException(404, "quality run not found")
    severity_rows = db.execute(
        select(QualityFinding.severity, func.count(QualityFinding.id))
        .where(QualityFinding.run_id == run.id)
        .group_by(QualityFinding.severity)
    ).all()
    status_rows = db.execute(
        select(QualityFinding.status, func.count(QualityFinding.id))
        .where(QualityFinding.run_id == run.id)
        .group_by(QualityFinding.status)
    ).all()
    table_rows = db.execute(
        select(QualityFinding.table_name, func.count(QualityFinding.id))
        .where(QualityFinding.run_id == run.id, QualityFinding.table_name.isnot(None))
        .group_by(QualityFinding.table_name)
        .order_by(func.count(QualityFinding.id).desc(), QualityFinding.table_name)
        .limit(10)
    ).all()
    return {"run_id": run.id, "system_code": run.system_code, "source_code": run.source_code,
            "status": run.status, "total_rules": run.total_rules, "total_findings": run.total_findings,
            "total_records": run.total_records, "error_records": run.error_records, "pass_rate": run.pass_rate,
            "severity_counts": {str(key or "unknown"): value for key, value in severity_rows},
            "status_counts": {str(key or "unknown"): value for key, value in status_rows},
            "top_tables": [{"table_name": table, "count": count} for table, count in table_rows]}


def _make(req, db, request_id):
    source = _build_source_payload(req, db)
    return build_payload(schema_version=INPUT_SCHEMA, request_id=request_id, task_type=req.task_type,
        prompt_version=settings.dify_quality_prompt_version, payload=source,
        max_bytes=settings.dify_max_payload_bytes, max_items=settings.dify_max_findings_per_job)


def _preview_signature(nonce: str) -> str:
    return hmac.new(settings.jwt_secret.encode(), f"ai-quality-preview:{nonce}".encode(), hashlib.sha256).hexdigest()[:32]


def _new_request_id() -> str:
    nonce = secrets.token_hex(12)
    return f"AQJ-{nonce}-{_preview_signature(nonce)}"


def _require_preview_request_id(request_id: str) -> None:
    parts = request_id.split("-")
    if len(parts) != 3 or parts[0] != "AQJ" or not hmac.compare_digest(parts[2], _preview_signature(parts[1])):
        raise HTTPException(422, "request_id was not issued by preview")


def _status_payload(db: Session | None = None):
    configured = False
    try:
        DifyQualityClient()._api_key()
        configured = True
    except DifyClientError:
        pass
    last_success = db.scalar(
        select(AiQualityJob.finished_at)
        .where(AiQualityJob.status == "succeeded")
        .order_by(AiQualityJob.finished_at.desc())
        .limit(1)
    ) if db is not None else None
    return {"enabled": settings.dify_quality_enabled, "configured": configured, "reachable": None,
            "workflow_name": settings.dify_quality_workflow_name, "prompt_version": settings.dify_quality_prompt_version,
            "schema_version": INPUT_SCHEMA,
            "max_findings": settings.dify_max_findings_per_job, "max_payload_bytes": settings.dify_max_payload_bytes,
            "timeout_seconds": settings.dify_read_timeout_seconds,
            "quota_state": "unknown",
            "last_success_at": last_success}


@router.get("/status", dependencies=[Depends(require_permission("asset.quality.ai.view"))])
def status(db: Session = Depends(get_db)) -> ApiResponse[dict]:
    return ApiResponse(data=_status_payload(db))


@router.post("/connection-test", dependencies=[Depends(require_permission("asset.quality.ai.connection_test"))])
def connection_test(request: Request, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    if not settings.dify_quality_enabled:
        raise HTTPException(409, "Dify quality analysis is disabled")
    try:
        result = DifyQualityClient().connection_test()
        _audit(db, "connection_test", "dify_workflow", settings.dify_quality_workflow_name,
               get_current_user(request), {"reachable": True})
        db.commit()
        return ApiResponse(data={**_status_payload(db), **result})
    except DifyClientError as exc:
        _audit(db, "connection_test_failed", "dify_workflow", settings.dify_quality_workflow_name,
               get_current_user(request), {"error_class": exc.error_class})
        db.commit()
        raise HTTPException(503, detail={"error_class": exc.error_class}) from exc


@router.post("/preview", dependencies=[Depends(require_permission("asset.quality.ai.analyze"))])
def preview(req: AiQualityPreviewRequest, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    request_id = _new_request_id()
    try:
        built = _make(req, db, request_id)
        source = _build_source_payload(req, db)
        item_count = len(source.get("findings", [])) if "findings" in source else 1
        safe_fields = sorted({
            key
            for item in source.get("findings", [source])
            for key in item
        })
        return ApiResponse(data={
            **built,
            "finding_ids": sorted(req.finding_ids),
            "run_id": req.run_id,
            "item_count": item_count,
            "fields": safe_fields,
            "dropped_count": len(built["dropped_fields"]),
            "redacted_count": sum(1 for value in built["dropped_fields"] if value),
            "warnings": [],
        })
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


def _job_item(job):
    return AiQualityJobItem.model_validate(job).model_dump()


def _job_payload(db: Session, job: AiQualityJob) -> dict:
    result = db.scalar(select(AiQualityResult).where(AiQualityResult.job_id == job.id))
    finding_ids = list(db.scalars(
        select(AiQualityJobFinding.finding_id)
        .where(AiQualityJobFinding.job_id == job.id)
        .order_by(AiQualityJobFinding.finding_id)
    ).all())
    return {**_job_item(job), "finding_ids": finding_ids,
            "run_id": (job.input_summary or {}).get("run_id"),
            "result": AiQualityResultItem.model_validate(result).model_dump() if result else None}


def _recover_stale(db):
    # A process restart must never silently resubmit an ambiguous blocking call.
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=settings.dify_stale_running_seconds)
    stale_jobs = list(db.scalars(select(AiQualityJob).where(
        AiQualityJob.status == "running", AiQualityJob.started_at < cutoff
    )).all())
    for job in stale_jobs:
        job.status = "unknown"
        job.error_class = "stale_running"
        job.error_summary = "Task was running when observation window expired"
        _audit(db, "stale_recovery", "ai_quality_job", job.id, "system",
               {"status": "unknown", "error_class": "stale_running"})
    if stale_jobs:
        db.commit()


@router.get("/jobs", dependencies=[Depends(require_permission("asset.quality.ai.view"))])
def jobs(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)) -> ApiResponse[PageData[dict]]:
    _recover_stale(db)
    total = db.scalar(select(func.count()).select_from(AiQualityJob)) or 0
    rows = db.scalars(select(AiQualityJob).order_by(desc(AiQualityJob.created_at)).offset((page - 1) * page_size).limit(page_size)).all()
    return ApiResponse(data=PageData(total=total, page=page, page_size=page_size, items=[_job_payload(db, row) for row in rows]))


@router.get("/jobs/{job_id}", dependencies=[Depends(require_permission("asset.quality.ai.view"))])
def job_detail(job_id: int, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    _recover_stale(db)
    job = db.get(AiQualityJob, job_id)
    if not job: raise HTTPException(404, "job not found")
    return ApiResponse(data=_job_payload(db, job))


def _submit(req: AiQualityCreateRequest, db: Session, operator: str, *, retry_job=None):
    if not settings.dify_quality_enabled: raise HTTPException(409, "Dify quality analysis is disabled")
    if retry_job is None:
        _require_preview_request_id(req.request_id)
    client = DifyQualityClient()
    try:
        client._validate_base()
        client._api_key()
    except DifyClientError as exc:
        _audit(db, "submit_rejected", "dify_workflow", settings.dify_quality_workflow_name,
               operator, {"error_class": exc.error_class})
        db.commit()
        raise HTTPException(409, detail={"error_class": exc.error_class}) from exc
    try:
        payload = _make(req, db, req.request_id)
    except ValueError as exc: raise HTTPException(422, str(exc)) from exc
    if not hmac.compare_digest(payload["input_digest"], req.input_digest):
        raise HTTPException(422, "input_digest does not match server preview")
    key_material = f"quality|{req.task_type}|{sorted(req.finding_ids)}|{req.run_id}|{payload['input_digest']}|{settings.dify_quality_prompt_version}"
    job_key = hashlib.sha256(key_material.encode()).hexdigest()
    job = retry_job or db.scalar(select(AiQualityJob).where(AiQualityJob.job_key == job_key))
    if job and retry_job is None:
        _audit(db, "reuse", "ai_quality_job", job.id, operator, {"status": job.status})
        db.commit()
        return job
    job = job or AiQualityJob(job_key=job_key, task_type=req.task_type, prompt_version=settings.dify_quality_prompt_version,
        schema_version=INPUT_SCHEMA, input_digest=payload["input_digest"], request_id=req.request_id,
        input_summary={"finding_count": len(req.finding_ids), "finding_ids": sorted(req.finding_ids), "run_id": req.run_id, "payload_bytes": payload["payload_bytes"], "dropped_count": len(payload["dropped_fields"])}, requested_by=operator)
    job.status, job.attempt, job.started_at = "running", (job.attempt or 0) + 1, datetime.now(timezone.utc)
    db.add(job); db.flush()
    for fid in sorted(set(req.finding_ids)):
        if not db.scalar(select(AiQualityJobFinding).where(AiQualityJobFinding.job_id == job.id, AiQualityJobFinding.finding_id == fid)):
            db.add(AiQualityJobFinding(job_id=job.id, finding_id=fid))
    _audit(db, "submit", "ai_quality_job", job.id, operator, {"input_digest": job.input_digest}); db.commit()
    started = time.monotonic()
    try:
        user_key = settings.jwt_secret.encode()
        user = "aq-" + hmac.new(user_key, str(operator).encode(), hashlib.sha256).hexdigest()[:32]
        response = client.run_workflow(inputs={k: payload[k] for k in ("schema_version", "request_id", "task_type", "prompt_version", "payload_json", "input_digest")}, user=user)
        result = validate_output(response.payload, request_id=req.request_id, input_digest=payload["input_digest"])
        job.status, job.dify_run_id = "succeeded", str(response.payload.get("workflow_run_id") or response.payload.get("task_id") or "")[:64]
        data = response.payload.get("data") or {}; job.token_usage = data.get("usage") if isinstance(data, dict) else None
        db.add(AiQualityResult(job_id=job.id, risk_level=result.risk_level, summary=result.summary, structured_result=result.model_dump(), output_digest=output_digest(result)))
        _audit(db, "succeeded", "ai_quality_job", job.id, operator,
               {"input_digest": job.input_digest, "output_digest": output_digest(result)})
    except DifyClientError as exc:
        if exc.error_class in {"timeout", "network", "server"}:
            state, error_class = "unknown", exc.error_class
        elif exc.error_class in {"invalid_json", "response_too_large", "redirect_blocked", "ssrf_blocked"}:
            state, error_class = "blocked", "contract"
        else:
            state, error_class = "failed", exc.error_class
        job.status, job.error_class, job.error_summary = state, error_class, "Dify request failed"
        _audit(db, "failed", "ai_quality_job", job.id, operator, {"error_class": error_class, "status": state})
    except Exception:
        job.status, job.error_class, job.error_summary = "blocked", "contract", "Dify output contract rejected"
        _audit(db, "blocked", "ai_quality_job", job.id, operator, {"error_class": "contract"})
    job.duration_ms = int((time.monotonic() - started) * 1000); job.finished_at = datetime.now(timezone.utc); db.commit()
    return job


@router.post("/jobs", dependencies=[Depends(require_permission("asset.quality.ai.analyze"))])
def create_job(req: AiQualityCreateRequest, request: Request, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    job = _submit(req, db, get_current_user(request))
    return ApiResponse(data=_job_payload(db, job))


@router.post("/jobs/{job_id}/retry", dependencies=[Depends(require_permission("asset.quality.ai.analyze"))])
def retry_job(job_id: int, request: Request, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    job = db.get(AiQualityJob, job_id)
    if not job: raise HTTPException(404, "job not found")
    if job.status not in {"failed", "unknown"} or job.error_class in {"contract", "auth", "validation", "not_configured", "blocked"}:
        raise HTTPException(409, "job is not retryable")
    req = AiQualityCreateRequest(task_type=job.task_type, finding_ids=db.scalars(select(AiQualityJobFinding.finding_id).where(AiQualityJobFinding.job_id == job.id)).all(), run_id=(job.input_summary or {}).get("run_id"), request_id=job.request_id, input_digest=job.input_digest)
    operator = get_current_user(request)
    _audit(db, "retry", "ai_quality_job", job.id, operator, {"attempt": (job.attempt or 0) + 1})
    db.commit()
    job = _submit(req, db, operator, retry_job=job)
    return ApiResponse(data=_job_payload(db, job))


@router.patch("/results/{result_id}/review", dependencies=[Depends(require_permission("asset.quality.ai.review"))])
def review_result(result_id: int, req: AiQualityReviewRequest, request: Request, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    result = db.get(AiQualityResult, result_id)
    if not result: raise HTTPException(404, "result not found")
    recommendations = (result.structured_result or {}).get("recommendations", [])
    accepted = req.accepted_recommendations or []
    if len(accepted) != len(set(accepted)) or any(i < 0 or i >= len(recommendations) for i in accepted):
        raise HTTPException(422, "accepted recommendation index not in result")
    if req.status == "rejected" and accepted:
        raise HTTPException(422, "rejected result cannot accept recommendations")
    if req.status == "accepted" and not accepted:
        accepted = list(range(len(recommendations)))
    if req.status == "partial" and (not accepted or len(accepted) >= len(recommendations)):
        raise HTTPException(422, "partial review requires a non-empty proper subset")
    result.review_status, result.review_by, result.review_at, result.review_note, result.accepted_recommendations = req.status, get_current_user(request), datetime.now(timezone.utc), req.note, accepted
    _audit(db, "review", "ai_quality_result", result.id, result.review_by, {"review_status": req.status}); db.commit()
    return ApiResponse(data=AiQualityResultItem.model_validate(result).model_dump())


@router.post("/results/{result_id}/attach", dependencies=[Depends(require_permission("asset.quality.ai.review"))])
def attach_result(result_id: int, req: AiQualityAttachRequest, request: Request, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    result = db.get(AiQualityResult, result_id)
    if not result: raise HTTPException(404, "result not found")
    if result.review_status not in {"accepted", "partial"}: raise HTTPException(409, "review result before attach")
    recommendations = (result.structured_result or {}).get("recommendations", [])
    if len(req.recommendation_indexes) != len(set(req.recommendation_indexes)) or any(i < 0 or i >= len(recommendations) for i in req.recommendation_indexes): raise HTTPException(422, "recommendation index not in result")
    reviewed = result.accepted_recommendations
    if reviewed is not None and any(i not in reviewed for i in req.recommendation_indexes):
        raise HTTPException(422, "recommendation was not accepted in review")
    operator = get_current_user(request); result.attached_by, result.attached_at, result.accepted_recommendations = operator, datetime.now(timezone.utc), req.recommendation_indexes
    _audit(db, "attach", "ai_quality_result", result.id, operator,
           {"recommendation_count": len(req.recommendation_indexes), "has_note": bool(req.note)}); db.commit()
    return ApiResponse(data=AiQualityResultItem.model_validate(result).model_dump())
