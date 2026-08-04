"""临床诊断映射导入审核 API（101号 §4.3）。

新增导入、暂存行查询、校验、审核和合并端点。
保留现有 /dict-medical/* 路径兼容。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from ...core.db import get_db
from ...core.security import get_current_user
from ...models.dict_medical import DictMedicalImportRun
from ...models.dict_medical_push import DictMedicalImportRow
from ...schemas.common import ApiResponse
from ...services.dict_medical_import import (
    parse_diagnosis_mapping_excel,
    create_import_run,
    stage_rows,
    merge_approved_rows,
)

router = APIRouter(prefix="/api/v1/dict-medical/imports", tags=["dict-medical-import"])


class ReviewRequest(BaseModel):
    row_ids: list[int]
    action: str  # approve / reject
    review_note: Optional[str] = None


@router.post("/diagnosis-mapping", summary="上传诊断映射 Excel（两行表头）")
async def upload_diagnosis_mapping(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
) -> ApiResponse[dict]:
    if not file.filename or not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="仅支持 .xlsx/.xls 文件")
    content = await file.read()
    result = parse_diagnosis_mapping_excel(content, file.filename)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    run = create_import_run(
        db,
        file_name=file.filename,
        file_sha256=result["file_sha256"],
        sheet=result["sheet"],
        row_count=result["row_count"],
        operator=user,
    )
    if run.status != "staged":
        return ApiResponse(data={
            "import_run_id": run.id,
            "batch_code": run.batch_code,
            "status": run.status,
            "message": "文件已导入（SHA256 幂等），返回既有批次",
            "row_count": result["row_count"],
        })

    staged = stage_rows(db, run, result["rows"], file.filename, result["file_sha256"], result["sheet"])
    return ApiResponse(data={
        "import_run_id": run.id,
        "batch_code": run.batch_code,
        "status": "staged",
        "row_count": result["row_count"],
        "staged": staged,
        "sheet": result["sheet"],
        "file_sha256": result["file_sha256"],
    })


@router.get("/{run_id}", summary="查询导入批次状态")
def get_import_run(
    run_id: int,
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    run = db.get(DictMedicalImportRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="批次不存在")
    stats = {}
    for status in ("pending", "approved", "rejected"):
        stats[status] = db.scalar(
            select(func.count()).select_from(DictMedicalImportRow).where(
                DictMedicalImportRow.import_run_id == run_id,
                DictMedicalImportRow.review_status == status,
            )
        ) or 0
    for vs in ("valid", "warning", "error"):
        stats[f"validation_{vs}"] = db.scalar(
            select(func.count()).select_from(DictMedicalImportRow).where(
                DictMedicalImportRow.import_run_id == run_id,
                DictMedicalImportRow.validation_status == vs,
            )
        ) or 0
    return ApiResponse(data={
        "id": run.id,
        "batch_code": run.batch_code,
        "status": run.status,
        "file_name": run.diagnosis_file_name,
        "file_sha256": run.diagnosis_sha256,
        "operator": run.operator,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "row_stats": stats,
    })


@router.get("/{run_id}/rows", summary="查询暂存行（分页）")
def list_import_rows(
    run_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    review_status: Optional[str] = Query(None),
    validation_status: Optional[str] = Query(None),
    only_anomalies: bool = Query(False),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    stmt = select(DictMedicalImportRow).where(DictMedicalImportRow.import_run_id == run_id)
    if review_status:
        stmt = stmt.where(DictMedicalImportRow.review_status == review_status)
    if validation_status:
        stmt = stmt.where(DictMedicalImportRow.validation_status == validation_status)
    if only_anomalies:
        stmt = stmt.where(DictMedicalImportRow.validation_status.in_(["warning", "error"]))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(DictMedicalImportRow.source_row_no)
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    items = [{
        "id": r.id,
        "row_no": r.source_row_no,
        "hospital_code": r.norm_hospital_code,
        "hospital_name": r.norm_hospital_name,
        "national_clinical_code": r.norm_national_clinical_code,
        "national_clinical_name": r.norm_national_clinical_name,
        "insurance_code": r.norm_insurance_code,
        "insurance_name": r.norm_insurance_name,
        "insurance_mapping_status": r.insurance_mapping_status,
        "validation_status": r.validation_status,
        "validation_errors": r.validation_errors,
        "diff_type": r.diff_type,
        "review_status": r.review_status,
        "reviewer": r.reviewer,
        "review_note": r.review_note,
    } for r in rows]
    return ApiResponse(data={"total": total, "page": page, "items": items})


@router.post("/{run_id}/rows/review", summary="批量审核暂存行")
def review_rows(
    run_id: int,
    req: ReviewRequest,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
) -> ApiResponse[dict]:
    if req.action not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="action 必须为 approve 或 reject")
    run = db.get(DictMedicalImportRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="批次不存在")
    if run.operator == user:
        raise HTTPException(status_code=403, detail="导入人不能自审")

    rows = db.scalars(
        select(DictMedicalImportRow).where(
            DictMedicalImportRow.id.in_(req.row_ids),
            DictMedicalImportRow.import_run_id == run_id,
        )
    ).all()
    if not rows:
        raise HTTPException(status_code=404, detail="未找到指定行")

    now = datetime.now(timezone.utc)
    reviewed = 0
    blocked = 0
    for row in rows:
        if req.action == "approve" and row.validation_status == "error":
            blocked += 1
            continue
        if req.action == "approve" and row.diff_type == "duplicate_in_file":
            blocked += 1
            continue
        row.review_status = "approved" if req.action == "approve" else "rejected"
        row.reviewer = user
        row.reviewed_at = now
        row.review_note = req.review_note
        row.updated_at = now
        reviewed += 1

    db.commit()
    return ApiResponse(data={"reviewed": reviewed, "blocked": blocked})


@router.post("/{run_id}/merge", summary="合并已批准行到正式字典")
def merge_run(
    run_id: int,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
) -> ApiResponse[dict]:
    run = db.get(DictMedicalImportRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="批次不存在")
    approved_count = db.scalar(
        select(func.count()).select_from(DictMedicalImportRow).where(
            DictMedicalImportRow.import_run_id == run_id,
            DictMedicalImportRow.review_status == "approved",
            DictMedicalImportRow.merged_at.is_(None),
        )
    ) or 0
    if approved_count == 0:
        raise HTTPException(status_code=400, detail="无待合并的已批准行")

    stats = merge_approved_rows(db, run, merged_by=user)
    return ApiResponse(data={"import_run_id": run_id, "status": "merged", **stats})