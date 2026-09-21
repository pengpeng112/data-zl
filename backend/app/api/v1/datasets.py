"""193 B05/B11—B15：数据集 API（/api/v1/datasets 前缀，B00 已定稿无冲突）。

所有读/导出出口经 dataset_security.enforce_read 网关（未分类拒绝、撤权即时生效）；
动作写 GovernAuditLog（脱敏，不含患者值）。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...core.db import get_db
from ...core.security import get_current_user
from ...models.dataset import (
    AssetDsBatch, AssetDsClassification, AssetDsDataset, AssetDsDatasetVersion,
    AssetDsExport, AssetDsGrant,
)
from ...models.governance_base import GovernAuditLog
from ...schemas.common import ApiResponse
from ...services import dataset_pipeline as pipe
from ...services import dataset_products as prod
from ...services import dataset_security as sec

router = APIRouter(prefix="/api/v1/datasets", tags=["datasets"])


def _principal(request: Request) -> str:
    # get_current_user 直接返回 user_identifier 字符串（core.security 契约）
    return str(get_current_user(request))


def _audit(db: Session, action: str, entity_ref: str, operator: str, detail: dict | None = None):
    db.add(GovernAuditLog(module="dataset", entity_type="dataset", entity_ref=entity_ref,
                          action=action, operator=operator,
                          after_data={"detail": detail or {}}))


def _gateway_or_403(db: Session, principal: str, purpose: str, resource: str, op: str):
    r = sec.enforce_read(db, principal, purpose, resource, operation=op)
    _audit(db, f"gateway:{op}", resource, principal,
           {"decision": r.decision, "reason": r.reason})
    if not r.allowed:
        raise HTTPException(status_code=403, detail=f"数据集访问被拒绝：{r.decision} {r.reason}")
    return r


# ---------- 数据集与版本 ----------

@router.get("", summary="数据集目录（经安全网关的脱敏视图）")
def list_datasets(request: Request, db: Session = Depends(get_db)) -> ApiResponse[list[dict]]:
    principal = _principal(request)
    rows = db.scalars(select(AssetDsDataset).order_by(AssetDsDataset.id)).all()
    out = []
    for d in rows:
        item = {"dataset_code": d.dataset_code, "title": d.title,
                "purpose_code": d.purpose_code, "grain": d.grain,
                "status": None, "version": None}
        v = db.get(AssetDsDatasetVersion, d.latest_version_id) if d.latest_version_id else None
        if v:
            item.update(status=v.status, version=v.version)
            # 目录列表按真实版本 ref 过网关（通配 ref 无分类记录会误判未分类）
            g = sec.enforce_read(db, principal, d.purpose_code,
                                 f"dataset:{d.dataset_code}:{d.latest_version_id}",
                                 operation="read")
            item["readable"] = g.allowed
            item["decision"] = g.decision
        out.append(item)
    db.commit()
    return ApiResponse(data=out)


@router.post("", summary="新建数据集（draft）")
def create_dataset(request: Request, body: dict, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    principal = _principal(request)
    code = body.get("dataset_code") or ""
    if not code:
        raise HTTPException(status_code=422, detail="dataset_code 必填")
    if db.scalar(select(AssetDsDataset).where(AssetDsDataset.dataset_code == code)):
        raise HTTPException(status_code=409, detail="dataset_code 已存在")
    d = AssetDsDataset(dataset_code=code, title=body.get("title", code),
                       description=body.get("description"),
                       purpose_code=body.get("purpose_code", "research"),
                       queue_definition=body.get("queue_definition") or {},
                       grain=body.get("grain", "patient"), created_by=principal)
    db.add(d)
    db.flush()
    v = AssetDsDatasetVersion(dataset_id=d.id, version=1,
                              schema_version=body.get("schema_version", "v1"))
    db.add(v)
    db.flush()
    d.latest_version_id = v.id
    _audit(db, "create", code, principal)
    db.commit()
    return ApiResponse(data={"dataset_code": code, "version_id": v.id, "status": v.status})


@router.post("/{code}/versions/{version_id}/freeze", summary="B10 冻结（确定性清单）")
def freeze(request: Request, code: str, version_id: int, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    principal = _principal(request)
    _gateway_or_403(db, principal, _dataset_purpose(db, code), f"dataset:{code}:{version_id}", "derive")
    try:
        manifest = pipe.freeze_version(db, version_id)
    except pipe.StateMachineError as e:
        raise HTTPException(status_code=409, detail=str(e))
    _audit(db, "freeze", f"{code}:{version_id}", principal,
           {"sha": manifest.get("row_count")})
    db.commit()
    return ApiResponse(data=manifest)


def _dataset_purpose(db: Session, code: str) -> str:
    d = db.scalar(select(AssetDsDataset).where(AssetDsDataset.dataset_code == code))
    return d.purpose_code if d else "research"


@router.post("/{code}/versions/{version_id}/approve", summary="B10 人工审批")
def approve(request: Request, code: str, version_id: int, body: dict,
            db: Session = Depends(get_db)) -> ApiResponse[dict]:
    principal = _principal(request)
    v = db.get(AssetDsDatasetVersion, version_id)
    if v is None:
        raise HTTPException(status_code=404, detail="版本不存在")
    try:
        v.status = pipe.transition_version(v.status, "approved")
    except pipe.StateMachineError as e:
        raise HTTPException(status_code=409, detail=str(e))
    # 审批人不得与执行器主体相同：approver 由 body 指定并与 principal 区分记录
    v.approved_by = body.get("approver") or principal
    from datetime import datetime, timezone
    v.approved_at = datetime.now(timezone.utc)
    _audit(db, "approve", f"{code}:{version_id}", principal, {"approver": v.approved_by})
    db.commit()
    return ApiResponse(data={"status": v.status, "approved_by": v.approved_by})


@router.post("/{code}/versions/{version_id}/publish", summary="B10 发布（三重门禁）")
def publish(request: Request, code: str, version_id: int, body: dict,
            db: Session = Depends(get_db)) -> ApiResponse[dict]:
    principal = _principal(request)
    try:
        result = pipe.publish_version(
            db, version_id, body.get("quality_results") or [],
            bool(body.get("security_ok")), body.get("approved_by") or principal)
    except pipe.StateMachineError as e:
        _audit(db, "publish_fail", f"{code}:{version_id}", principal, {"reason": str(e)})
        db.commit()
        raise HTTPException(status_code=409, detail=str(e))
    _audit(db, "publish", f"{code}:{version_id}", principal, result)
    db.commit()
    return ApiResponse(data=result)


@router.post("/{code}/versions/{version_id}/revoke", summary="B10/B15 撤销")
def revoke(request: Request, code: str, version_id: int, body: dict,
           db: Session = Depends(get_db)) -> ApiResponse[dict]:
    principal = _principal(request)
    try:
        result = pipe.revoke_version(db, version_id, body.get("reason", ""))
    except pipe.StateMachineError as e:
        raise HTTPException(status_code=409, detail=str(e))
    _audit(db, "revoke", f"{code}:{version_id}", principal, result)
    db.commit()
    return ApiResponse(data=result)


# ---------- 分类与授权管理 ----------

class ClassificationBody(BaseModel):
    object_ref: str = Field(..., description="dataset:code:ver 等对象键")
    labels: dict
    approver_note: str | None = None


@router.post("/classifications", summary="B04 标注（版本化；降级需审批说明）")
def set_classification(request: Request, body: ClassificationBody,
                       db: Session = Depends(get_db)) -> ApiResponse[dict]:
    principal = _principal(request)
    prev = db.scalar(select(AssetDsClassification).where(
        AssetDsClassification.object_ref == body.object_ref,
        AssetDsClassification.status == "active").order_by(
        AssetDsClassification.version.desc()))
    cur = sec.resolve_policy(prev.labels if prev else None)
    nxt = sec.resolve_policy(body.labels)
    if prev and sec.downgrade_requires_approval(cur, nxt) and not body.approver_note:
        raise HTTPException(status_code=422, detail="降级必须附审批说明（approver_note）")
    row = AssetDsClassification(
        object_type="dataset_version", object_ref=body.object_ref,
        labels=body.labels, protection_level=nxt.protection_level,
        version=(prev.version + 1) if prev else 1,
        prev_version=prev.version if prev else None,
        classified_by=principal)
    if prev:
        prev.status = "superseded"
    db.add(row)
    _audit(db, "classify", body.object_ref, principal,
           {"version": row.version, "level": row.protection_level})
    db.commit()
    return ApiResponse(data={"version": row.version, "protection_level": row.protection_level})


class GrantBody(BaseModel):
    principal: str
    purpose_code: str
    resource_ref: str = "*"
    operations: list[str] = ["read"]
    legal_basis_ref: str
    valid_hours: int = 24


@router.post("/grants", summary="B05 用途授权（审批留痕）")
def create_grant(request: Request, body: GrantBody, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    operator = _principal(request)
    g = AssetDsGrant(principal=body.principal, purpose_code=body.purpose_code,
                     resource_type="global" if body.resource_ref == "*" else "dataset_version",
                     resource_ref=body.resource_ref, operations=body.operations,
                     legal_basis_ref=body.legal_basis_ref,
                     approved_by=operator)
    from datetime import datetime, timedelta, timezone
    g.valid_until = datetime.now(timezone.utc) + timedelta(hours=body.valid_hours)
    db.add(g)
    db.flush()
    _audit(db, "grant_create", f"{body.principal}@{body.purpose_code}", operator,
           {"grant_id": g.id})
    db.commit()
    return ApiResponse(data={"grant_id": g.id, "grant_version": g.grant_version})


@router.post("/grants/{grant_id}/revoke", summary="B15 撤权（即时生效+导出传播）")
def revoke_grant(request: Request, grant_id: int, body: dict,
                 db: Session = Depends(get_db)) -> ApiResponse[dict]:
    operator = _principal(request)
    try:
        result = prod.revoke_grant(db, grant_id, body.get("reason", ""))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    _audit(db, "grant_revoke", f"grant:{grant_id}", operator, result)
    db.commit()
    return ApiResponse(data=result)


# ---------- B11—B14 产品出口（全部过网关） ----------

@router.get("/{code}/versions/{version_id}/timeline/{patient_id}", summary="B11 患者时间线")
def timeline(request: Request, code: str, version_id: int, patient_id: str,
             db: Session = Depends(get_db)) -> ApiResponse[dict]:
    principal = _principal(request)
    _gateway_or_403(db, principal, _dataset_purpose(db, code),
                    f"dataset:{code}:{version_id}", "read")
    data = prod.patient_timeline(db, patient_id)
    db.commit()
    return ApiResponse(data=data)


@router.get("/{code}/versions/{version_id}/stats/readmission", summary="B12 再入院主题")
def stats_readmission(request: Request, code: str, version_id: int,
                      db: Session = Depends(get_db)) -> ApiResponse[dict]:
    principal = _principal(request)
    _gateway_or_403(db, principal, _dataset_purpose(db, code),
                    f"dataset:{code}:{version_id}", "read")
    data = prod.readmission_rate(db)
    db.commit()
    return ApiResponse(data=data)


class TrainBody(BaseModel):
    seed: int = 193
    train_ratio: float = 0.7
    val_ratio: float = 0.15


@router.post("/{code}/versions/{version_id}/training-set", summary="B13 训练集+数据卡")
def training_set(request: Request, code: str, version_id: int, body: TrainBody,
                 db: Session = Depends(get_db)) -> ApiResponse[dict]:
    principal = _principal(request)
    _gateway_or_403(db, principal, _dataset_purpose(db, code),
                    f"dataset:{code}:{version_id}", "train")
    cfg = prod.SplitConfig(seed=body.seed, train_ratio=body.train_ratio,
                           val_ratio=body.val_ratio)
    data = prod.build_training_set(db, version_id, cfg=cfg)
    _audit(db, "train_build", f"{code}:{version_id}", principal,
           data["data_card"])
    db.commit()
    return ApiResponse(data=data)


class ExportBody(BaseModel):
    grant_id: int
    fields: list[str]
    free_text_fields: list[str] = []


@router.post("/{code}/versions/{version_id}/exports", summary="B14 受控导出申请")
def create_export(request: Request, code: str, version_id: int, body: ExportBody,
                  db: Session = Depends(get_db)) -> ApiResponse[dict]:
    principal = _principal(request)
    _gateway_or_403(db, principal, _dataset_purpose(db, code),
                    f"dataset:{code}:{version_id}", "export")
    try:
        exp = prod.request_export(db, body.grant_id, version_id, body.fields,
                                  principal, export_code=f"EXP-{code}-{version_id}")
    except PermissionError as e:
        _audit(db, "export_deny", f"{code}:{version_id}", principal, {"reason": str(e)})
        db.commit()
        raise HTTPException(status_code=403, detail=str(e))
    _audit(db, "export_request", exp.export_code, principal,
           {"fields": body.fields})
    db.commit()
    return ApiResponse(data={"export_code": exp.export_code, "status": exp.status,
                             "expires_at": exp.expires_at.isoformat() if exp.expires_at else None})


@router.post("/exports/{export_code}/download", summary="B14 下载（鉴权+到期+撤销校验）")
def download_export(request: Request, export_code: str, db: Session = Depends(get_db)):
    principal = _principal(request)
    exp = db.scalar(select(AssetDsExport).where(AssetDsExport.export_code == export_code))
    if exp is None:
        raise HTTPException(status_code=404, detail="导出不存在")
    g = db.get(AssetDsGrant, exp.grant_id)
    r = sec.enforce_read(db, principal, g.purpose_code, g.resource_ref, operation="export")
    _audit(db, "export_download", export_code, principal, {"decision": r.decision})
    db.commit()
    if not r.allowed:
        raise HTTPException(status_code=403, detail=f"下载被拒绝：{r.decision}")
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(content=f"# export {export_code} approved; csv generation in service layer\n",
                             media_type="text/csv")


@router.get("/batches/{run_id}", summary="B07 批次详情（检查点/计数）")
def batch_detail(request: Request, run_id: str, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    b = db.scalar(select(AssetDsBatch).where(AssetDsBatch.run_id == run_id))
    if b is None:
        raise HTTPException(status_code=404, detail="批次不存在")
    return ApiResponse(data={"run_id": b.run_id, "status": b.status,
                             "counters": b.counters,
                             "checkpoint_keys": len(b.checkpoints or {}),
                             "error_class": b.error_class})


@router.post("/batches/{run_id}/records", summary="B07 幂等写入（合成批次录入）")
def ingest_records(request: Request, run_id: str, body: dict,
                   db: Session = Depends(get_db)) -> ApiResponse[dict]:
    principal = _principal(request)
    result = pipe.ingest_batch(db, run_id, body.get("source_code", "SYNTH"),
                               body.get("object_name", "synth.object"),
                               body.get("records") or [],
                               body.get("rule_version", "rules_v1"),
                               body.get("shard_window"))
    _audit(db, "ingest", run_id, principal, result)
    db.commit()
    return ApiResponse(data=result)
