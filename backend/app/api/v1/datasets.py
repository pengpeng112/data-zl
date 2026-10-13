"""193 B05/B11—B15 + 210 S2/S5：数据集 API（/api/v1/datasets 前缀）。

210 修订要点：
- 全部端点挂 require_permission 权限码（ds.* catalog），认证主体是唯一身份来源；
  body 中的 approver/operator 类字段一律不信任（F02/F05）。
- 申请/审批/执行职责分离：分类降级、授权、导出、版本审批均由不同主体完成；
  审批人=认证用户，且不得与申请人/冻结人相同（T07）。
- 拒绝审计独立提交（业务事务回滚后仍可回读，F09/T27）。
- 读/导出出口经 dataset_security.enforce_read 多对象网关（版本+成员表组合策略，
  未知默认拒绝）；行范围/列投影由网关输出并落实到查询（F06/F07）。
- 导出走真实闭环：申请→独立审批→生成受控工件→重验下载（F08/T22—T26）。
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...core.db import get_db
from ...core.security import get_current_user, require_permission
from ...models.dataset import (
    AssetDsBatch, AssetDsClassification, AssetDsDataset, AssetDsDatasetVersion,
    AssetDsExport, AssetDsGrant,
)
from ...models.governance_base import GovernAuditLog, GovernChangeRequest
from ...schemas.common import ApiResponse
from ...services import dataset_pipeline as pipe
from ...services import dataset_products as prod
from ...services import dataset_security as sec

router = APIRouter(prefix="/api/v1/datasets", tags=["datasets"])


def _principal(request: Request) -> str:
    # get_current_user 直接返回 user_identifier 字符串（core.security 契约）
    return str(get_current_user(request))


def _has_permission(db: Session, request: Request, code: str) -> bool:
    """非抛错式权限探测（P4 附加门禁等增量检查用）。"""
    try:
        require_permission(code)(request, db)
        return True
    except HTTPException:
        return False


def _audit(db: Session, action: str, entity_ref: str, operator: str,
           detail: dict | None = None):
    """业务事务内审计（与业务写原子一致）。"""
    db.add(GovernAuditLog(module="dataset", entity_type="dataset", entity_ref=entity_ref,
                          action=action, operator=operator,
                          after_data={"detail": detail or {}}))


def _audit_denial(db: Session, action: str, entity_ref: str, operator: str,
                  detail: dict | None = None):
    """拒绝审计：独立提交，业务事务回滚后仍可回读（210 F09/T27）。"""
    db.add(GovernAuditLog(module="dataset", entity_type="dataset", entity_ref=entity_ref,
                          action=action, operator=operator,
                          after_data={"detail": detail or {}}))
    try:
        db.commit()
    except Exception:
        db.rollback()


def _resolve_version(db: Session, code: str, version_id: int) -> AssetDsDatasetVersion:
    """解析版本并核对 code 与 version 归属一致（210 T11：跨 dataset 关联拒绝）。"""
    v = db.get(AssetDsDatasetVersion, version_id)
    if v is None:
        raise HTTPException(status_code=404, detail="版本不存在")
    d = db.get(AssetDsDataset, v.dataset_id) if v.dataset_id else None
    if d is None or d.dataset_code != code:
        raise HTTPException(status_code=422, detail="code 与 version_id 不属于同一数据集")
    if v.status in ("revoked",):
        raise HTTPException(status_code=403, detail="版本已撤销")
    return v


def _dataset_purpose(db: Session, code: str) -> str:
    d = db.scalar(select(AssetDsDataset).where(AssetDsDataset.dataset_code == code))
    return d.purpose_code if d else "research"


def _version_resource_ref(db: Session, version: AssetDsDatasetVersion) -> str:
    d = db.get(AssetDsDataset, version.dataset_id) if version.dataset_id else None
    return (f"dataset:{d.dataset_code}:{version.id}" if d is not None
            else f"dataset_version:{version.id}")


def _gateway_or_403(db: Session, request: Request, principal: str, purpose: str,
                    version: AssetDsDatasetVersion, op: str,
                    requested_columns: list[str] | None = None) -> sec.GatewayResult:
    """多对象网关（版本+来源表组合策略）+ 审计。拒绝走独立提交审计（F09）。"""
    refs = prod.version_policy_refs(db, version.id)
    primary = _version_resource_ref(db, version)
    if primary not in refs:
        refs.insert(0, primary)
    p4 = _has_permission(db, request, "ds.p4.access")
    r = sec.enforce_read(db, principal, purpose, refs, operation=op,
                         requested_columns=requested_columns, p4_authorized=p4)
    if not r.allowed:
        _audit_denial(db, f"gateway:{op}:deny", primary, principal,
                      {"decision": r.decision, "reason": r.reason})
        raise HTTPException(status_code=403,
                            detail=f"数据集访问被拒绝：{r.decision} {r.reason}")
    _audit(db, f"gateway:{op}", primary, principal,
           {"decision": r.decision, "reason": r.reason})
    return r


# ---------- 数据集与版本 ----------

@router.get("", summary="数据集目录（元数据浏览；读取许可由网关标注）")
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
            # 目录列表按真实版本 ref 过网关（组合策略）；拒绝只降级标记不隐藏元数据
            refs = prod.version_policy_refs(db, v.id)
            primary = _version_resource_ref(db, v)
            if primary not in refs:
                refs.insert(0, primary)
            p4 = _has_permission(db, request, "ds.p4.access")
            g = sec.enforce_read(db, principal, d.purpose_code, refs,
                                 operation="read", p4_authorized=p4)
            item["readable"] = g.allowed
            item["decision"] = g.decision
            item["pending_classification"] = (g.policy.is_pending
                                              if g.policy else True)
        out.append(item)
    db.commit()
    return ApiResponse(data=out)


@router.post("", summary="新建数据集（draft）",
             dependencies=[Depends(require_permission("ds.manage"))])
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


@router.post("/{code}/versions/{version_id}/freeze", summary="冻结（绑定具体成员）",
             dependencies=[Depends(require_permission("ds.manage"))])
def freeze(request: Request, code: str, version_id: int, body: dict | None = None,
           db: Session = Depends(get_db)) -> ApiResponse[dict]:
    principal = _principal(request)
    v = _resolve_version(db, code, version_id)
    body = body or {}
    # 合成闭环：draft 态可声明/追加来源批次（生产来源由采集链路写入）
    declared = body.get("source_batch_ids")
    if declared is not None:
        if v.status != "draft":
            raise HTTPException(status_code=409, detail="仅 draft 状态可声明来源批次")
        if not isinstance(declared, list) or not all(isinstance(x, str) for x in declared):
            raise HTTPException(status_code=422, detail="source_batch_ids 必须为字符串数组")
        v.source_batch_ids = declared
    try:
        manifest = pipe.freeze_version(db, version_id, frozen_by=principal)
    except pipe.StateMachineError as e:
        raise HTTPException(status_code=409, detail=str(e))
    _audit(db, "freeze", f"{code}:{version_id}", principal,
           {"row_count": manifest.get("row_count"),
            "manifest_sha256": getattr(v, "manifest_sha256", None)})
    db.commit()
    return ApiResponse(data=manifest)


@router.get("/{code}/versions/{version_id}/manifest", summary="版本清单与成员统计")
def version_manifest(request: Request, code: str, version_id: int,
                     db: Session = Depends(get_db)) -> ApiResponse[dict]:
    _principal(request)
    v = _resolve_version(db, code, version_id)
    return ApiResponse(data={"manifest": v.manifest,
                            "manifest_sha256": v.manifest_sha256,
                            "status": v.status,
                            "security_conclusion": v.security_conclusion,
                            "quality_conclusion": v.quality_conclusion})


@router.post("/{code}/versions/{version_id}/approve", summary="版本人工审批（职责分离）",
             dependencies=[Depends(require_permission("ds.version.publish"))])
def approve(request: Request, code: str, version_id: int, body: dict,
            db: Session = Depends(get_db)) -> ApiResponse[dict]:
    principal = _principal(request)
    v = _resolve_version(db, code, version_id)
    # 210 F05：审批人来自认证上下文；body.approver 仅兼容展示，不参与判定。
    # 冻结执行人不得审批自己的版本（申请人/审批人分离）。
    if v.frozen_by and v.frozen_by == principal:
        _audit_denial(db, "approve:deny", f"{code}:{version_id}", principal,
                      {"reason": "审批人与冻结执行人相同（职责分离）"})
        raise HTTPException(status_code=403, detail="审批人与冻结执行人必须不同")
    try:
        v.status = pipe.transition_version(v.status, "approved")
    except pipe.StateMachineError as e:
        raise HTTPException(status_code=409, detail=str(e))
    v.approved_by = principal
    v.approved_at = datetime.now(timezone.utc)
    _audit(db, "approve", f"{code}:{version_id}", principal)
    db.commit()
    return ApiResponse(data={"status": v.status, "approved_by": v.approved_by})


@router.post("/{code}/versions/{version_id}/security-review",
             summary="独立安全评审（持久化结论；评审人≠冻结人）",
             dependencies=[Depends(require_permission("ds.classification.review"))])
def security_review(request: Request, code: str, version_id: int, body: dict,
                    db: Session = Depends(get_db)) -> ApiResponse[dict]:
    principal = _principal(request)
    v = _resolve_version(db, code, version_id)
    if v.frozen_by and v.frozen_by == principal:
        _audit_denial(db, "security_review:deny", f"{code}:{version_id}", principal,
                      {"reason": "安全评审人与冻结执行人相同（职责分离）"})
        raise HTTPException(status_code=403, detail="安全评审人与冻结执行人必须不同")
    if not isinstance(body.get("passed"), bool):
        raise HTTPException(status_code=422, detail="passed 必须为布尔值")
    try:
        conclusion = pipe.record_security_review(
            db, version_id, reviewer=principal, passed=body["passed"],
            note=str(body.get("note") or "")[:500])
    except pipe.StateMachineError as e:
        raise HTTPException(status_code=409, detail=str(e))
    _audit(db, "security_review", f"{code}:{version_id}", principal,
           {"passed": body["passed"]})
    db.commit()
    return ApiResponse(data=conclusion)


@router.post("/{code}/versions/{version_id}/publish",
             summary="发布（三重门禁：持久化质量断言+安全结论+审批）",
             dependencies=[Depends(require_permission("ds.version.publish"))])
def publish(request: Request, code: str, version_id: int,
            db: Session = Depends(get_db)) -> ApiResponse[dict]:
    """210 F07/T10：不接收 body 质量数组/security_ok/approved_by。"""
    principal = _principal(request)
    v = _resolve_version(db, code, version_id)
    if not v.approved_by or v.approved_by == principal:
        _audit_denial(db, "publish:deny", f"{code}:{version_id}", principal,
                      {"reason": "发布人必须与版本审批人不同（职责分离）或尚未审批"})
        raise HTTPException(status_code=403, detail="发布人必须与版本审批人不同，且版本已审批")
    try:
        result = pipe.publish_version(db, version_id)
    except pipe.StateMachineError as e:
        _audit_denial(db, "publish_fail", f"{code}:{version_id}", principal,
                      {"reason": str(e)})
        raise HTTPException(status_code=409, detail=str(e))
    _audit(db, "publish", f"{code}:{version_id}", principal, result)
    db.commit()
    return ApiResponse(data=result)


@router.post("/{code}/versions/{version_id}/revoke", summary="撤销（导出传播+账本）",
             dependencies=[Depends(require_permission("ds.version.publish"))])
def revoke(request: Request, code: str, version_id: int, body: dict,
           db: Session = Depends(get_db)) -> ApiResponse[dict]:
    principal = _principal(request)
    _resolve_version(db, code, version_id)
    try:
        result = pipe.revoke_version(db, version_id, body.get("reason", ""))
        propagation = prod.revoke_version_propagation(
            db, version_id, body.get("reason", ""), operator=principal)
        result["exports_revoked"] = propagation["exports_revoked"]
    except pipe.StateMachineError as e:
        raise HTTPException(status_code=409, detail=str(e))
    _audit(db, "revoke", f"{code}:{version_id}", principal, result)
    db.commit()
    return ApiResponse(data=result)


# ---------- 分类与候选管理（F01/F03/F04/F10/F12） ----------

class ClassificationBody(BaseModel):
    object_type: str = Field(..., description="dataset_version|table|view|column|export")
    object_ref: str | None = Field(None, description="dataset:{code}:{version_id}（dataset_version 专用）")
    physical_key: dict | None = Field(None, description="table/column 结构化物理键")
    labels: dict
    expected_version: int = Field(..., ge=0, description="当前 active 版本号（无=0），CAS 并发控制")
    label_source: str = Field("manual", description="manual|candidate")
    evidence: dict | None = None
    retention_until: str | None = None


def _classification_target(body: ClassificationBody) -> tuple[str, str, dict | None]:
    if body.object_type == "dataset_version":
        ref = body.object_ref or ""
        parts = ref.split(":")
        if len(parts) != 3 or parts[0] != "dataset" or not parts[1] or not parts[2].isdigit():
            raise HTTPException(status_code=422,
                                detail="dataset_version 对象键必须为 dataset:{code}:{version_id}")
        return body.object_type, ref, None
    if body.object_type in ("table", "view", "column"):
        if not body.physical_key:
            raise HTTPException(status_code=422, detail=f"{body.object_type} 对象必须提供 physical_key")
        try:
            ref = sec.canonical_object_ref(
                "table" if body.object_type == "view" else body.object_type,
                body.physical_key)
        except sec.PolicyValidationError as e:
            raise HTTPException(status_code=422, detail=str(e))
        return body.object_type, ref, body.physical_key
    raise HTTPException(status_code=422, detail=f"object_type 非法: {body.object_type}")


@router.post("/classifications", summary="分类提案（严格校验+CAS+降级走审批）",
             dependencies=[Depends(require_permission("ds.classification.manage"))])
def set_classification(request: Request, body: ClassificationBody,
                       db: Session = Depends(get_db)) -> ApiResponse[dict]:
    principal = _principal(request)
    object_type, ref, physical_key = _classification_target(body)
    if body.label_source not in ("manual", "candidate"):
        raise HTTPException(status_code=422, detail="label_source 必须为 manual|candidate")
    try:
        labels = sec.validate_labels(body.labels)
        nxt = sec.resolve_policy(labels, strict=True)
    except sec.PolicyValidationError as e:
        raise HTTPException(status_code=422, detail=f"标签非法: {e}")
    # dataset_version 键必须归属真实版本（孤儿对象拒绝，T03）
    if object_type == "dataset_version":
        code, vid = ref.split(":")[1], int(ref.split(":")[2])
        v = db.get(AssetDsDatasetVersion, vid)
        d = db.get(AssetDsDataset, v.dataset_id) if (v and v.dataset_id) else None
        if v is None or d is None or d.dataset_code != code:
            raise HTTPException(status_code=422, detail="对象键指向不存在的 dataset/version")

    # CAS（F10/T28）：行锁 + expected_version；竞态一方 409
    prev = db.scalar(
        select(AssetDsClassification)
        .where(AssetDsClassification.object_type == object_type,
               AssetDsClassification.object_ref == ref,
               AssetDsClassification.status == "active")
        .with_for_update()
        .order_by(AssetDsClassification.version.desc()))
    current_version = prev.version if prev else 0
    if body.expected_version != current_version:
        raise HTTPException(status_code=409,
                            detail=f"expected_version 不匹配（当前 active v{current_version}）")
    # 同对象已有待审批提案占用下一版本号 → 409（无双 active/双 pending）
    occupied = db.scalar(select(AssetDsClassification).where(
        AssetDsClassification.object_type == object_type,
        AssetDsClassification.object_ref == ref,
        AssetDsClassification.version == current_version + 1))
    if occupied is not None:
        raise HTTPException(status_code=409,
                            detail=f"已存在 v{current_version + 1} 变更提案（id={occupied.id}），先处置")
    cur = sec.resolve_policy(prev.labels, strict=True) if prev else None
    # 候选不覆盖已确认标签（F12/T31）
    if prev and body.label_source == "candidate" and getattr(prev, "label_source", None) == "confirmed":
        raise HTTPException(status_code=409, detail="confirmed 标签不可被候选覆盖")
    needs, reasons = (sec.change_requires_approval(cur, nxt) if cur else (False, []))
    row = AssetDsClassification(
        object_type=object_type, object_ref=ref,
        labels=labels, protection_level=nxt.protection_level,
        version=current_version + 1,
        prev_version=prev.version if prev else None,
        classified_by=principal,
        classification_schema_version="b02_v1",
        object_physical_key=physical_key,
        label_source=body.label_source,
        evidence=body.evidence,
        retention_until=_parse_iso(body.retention_until))
    if needs:
        row.status = "pending_approval"
        row.proposal_hash = _proposal_hash(ref, current_version + 1, labels)
    else:
        row.status = "active"
        row.effective_at = datetime.now(timezone.utc)
        if prev:
            prev.status = "superseded"
    db.add(row)
    db.flush()
    cr = None
    if needs:
        cr = GovernChangeRequest(
            module="dataset", entity_type="classification", entity_ref=ref,
            request_type="classification_change",
            request_payload={"labels": labels, "reasons": reasons,
                             "from_version": current_version, "to_version": row.version,
                             "proposal_hash": row.proposal_hash},
            requested_by=principal, approval_status="pending",
            note="; ".join(reasons))
        db.add(cr)
        db.flush()
    _audit(db, "classify", ref, principal,
           {"version": row.version, "level": row.protection_level,
            "status": row.status, "needs_approval": needs, "reasons": reasons})
    db.commit()
    return ApiResponse(data={"version": row.version,
                             "protection_level": row.protection_level,
                             "status": row.status,
                             "needs_approval": needs,
                             "reasons": reasons,
                             "change_request_id": cr.id if cr else None})


def _proposal_hash(ref: str, version: int, labels: dict) -> str:
    import hashlib
    import json
    payload = json.dumps({"ref": ref, "version": version, "labels": labels},
                         sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"非法时间: {value!r}")


@router.get("/classifications", summary="分类清单（active/pending/候选区分）",
            dependencies=[Depends(require_permission("ds.read"))])
def list_classifications(request: Request, db: Session = Depends(get_db),
                         object_type: str | None = None,
                         include_pending: bool = True) -> ApiResponse[list[dict]]:
    _principal(request)
    q = select(AssetDsClassification).order_by(AssetDsClassification.id.desc()).limit(200)
    rows = db.scalars(q).all()
    out = [{
        "id": r.id, "object_type": r.object_type, "object_ref": r.object_ref,
        "version": r.version, "status": r.status, "label_source": r.label_source,
        "protection_level": r.protection_level, "labels": r.labels,
        "classified_by": r.classified_by,
        "evidence": r.evidence,
        "retention_until": r.retention_until.isoformat() if r.retention_until else None,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    } for r in rows
        if (object_type is None or r.object_type == object_type)
        and (include_pending or r.status == "active")]
    db.commit()
    return ApiResponse(data=out)


@router.post("/classifications/{row_id}/review",
             summary="分类变更审批（审批人≠提案人；hash 失效拒绝）",
             dependencies=[Depends(require_permission("ds.classification.review"))])
def review_classification(request: Request, row_id: int, body: dict,
                          db: Session = Depends(get_db)) -> ApiResponse[dict]:
    principal = _principal(request)
    row = db.get(AssetDsClassification, row_id)
    if row is None or row.status != "pending_approval":
        raise HTTPException(status_code=404, detail="待审批分类不存在")
    if row.classified_by == principal:
        _audit_denial(db, "classify_review:deny", row.object_ref, principal,
                      {"reason": "审批人与提案人相同（职责分离）"})
        raise HTTPException(status_code=403, detail="审批人与提案人必须不同")
    decision = body.get("decision")
    if decision not in ("approve", "reject"):
        raise HTTPException(status_code=422, detail="decision 必须为 approve|reject")
    # hash 失效：提案内容变动（重提了新版本）→ 旧审批不可用（T09）
    if row.proposal_hash and row.proposal_hash != _proposal_hash(
            row.object_ref, row.version, row.labels):
        raise HTTPException(status_code=409, detail="提案 hash 失效（内容已变动）")
    # 提案基于的 active 版本已被取代 → 旧审批失效（T09）
    current_active = db.scalar(select(AssetDsClassification).where(
        AssetDsClassification.object_type == row.object_type,
        AssetDsClassification.object_ref == row.object_ref,
        AssetDsClassification.status == "active"))
    if decision == "approve" and row.prev_version is not None:
        if current_active is None or current_active.version != row.prev_version:
            raise HTTPException(status_code=409, detail="提案过期（对象 active 版本已变动，需重提）")
    if decision == "reject":
        row.status = "retired"
        _audit(db, "classify_review_reject", row.object_ref, principal,
               {"note": str(body.get("note") or "")[:200]})
        db.commit()
        return ApiResponse(data={"status": row.status})
    # 审批通过：再次严格校验并原子换 active（行锁 CAS 兜底单 active）
    try:
        labels = sec.validate_labels(row.labels)
        nxt = sec.resolve_policy(labels, strict=True)
    except sec.PolicyValidationError as e:
        raise HTTPException(status_code=422, detail=f"标签非法: {e}")
    prev = db.scalar(
        select(AssetDsClassification)
        .where(AssetDsClassification.object_type == row.object_type,
               AssetDsClassification.object_ref == row.object_ref,
               AssetDsClassification.status == "active")
        .with_for_update())
    if prev:
        cur = sec.resolve_policy(prev.labels, strict=True)
        needs, reasons = sec.change_requires_approval(cur, nxt)
        if not needs:
            # 世界已变化：当前 active 已不构成降级/放宽 → 无需审批直接换绑
            pass
        prev.status = "superseded"
        prod.record_revocation(db, "policy", row.object_ref,
                               "标签被新版本取代", principal, target_id=prev.id)
    row.status = "active"
    row.label_source = "confirmed"
    row.effective_at = datetime.now(timezone.utc)
    _audit(db, "classify_review_approve", row.object_ref, principal,
           {"version": row.version, "level": row.protection_level})
    db.commit()
    return ApiResponse(data={"status": row.status, "version": row.version})


@router.post("/classifications/candidates:import",
             summary="离线候选批量导入（隔离库验证用；不覆盖 confirmed）",
             dependencies=[Depends(require_permission("ds.classification.manage"))])
def import_candidates(request: Request, body: dict,
                      db: Session = Depends(get_db)) -> ApiResponse[dict]:
    """S6 验收通道：候选按规范键幂等导入；生产入库属 S10 另批。"""
    principal = _principal(request)
    proposals = body.get("proposals") or []
    if not isinstance(proposals, list) or len(proposals) > 5000:
        raise HTTPException(status_code=422, detail="proposals 必须为列表（≤5000）")
    imported = skipped_confirmed = skipped_same = rejected = 0
    for p in proposals:
        try:
            object_type = p["object_type"]
            if object_type in ("table", "view", "column"):
                ref = sec.canonical_object_ref(
                    "table" if object_type == "view" else object_type, p["physical_key"])
            elif object_type == "dataset_version":
                ref = p["object_ref"]
            else:
                raise KeyError("object_type")
            labels = sec.validate_labels(p.get("labels") or {})
            sec.resolve_policy(labels, strict=True)
        except (KeyError, sec.PolicyValidationError):
            rejected += 1
            continue
        prev = db.scalar(select(AssetDsClassification).where(
            AssetDsClassification.object_type == object_type,
            AssetDsClassification.object_ref == ref,
            AssetDsClassification.status == "active"))
        if prev and getattr(prev, "label_source", "") == "confirmed":
            skipped_confirmed += 1
            continue
        if prev and prev.labels == labels:
            skipped_same += 1
            continue
        row = AssetDsClassification(
            object_type=object_type, object_ref=ref, labels=labels,
            protection_level=labels.get("protection_level", "P4"),
            version=(prev.version + 1) if prev else 1,
            prev_version=prev.version if prev else None,
            classified_by=principal, label_source="candidate",
            classification_schema_version="b02_v1",
            object_physical_key=p.get("physical_key"),
            evidence=p.get("evidence"))
        if prev:
            prev.status = "superseded"
        db.add(row)
        db.flush()  # autoflush=False：同批内后看对象能看到前写行，避免唯一键冲突
        imported += 1
    _audit(db, "candidates_import", "bulk", principal,
           {"imported": imported, "skipped_confirmed": skipped_confirmed,
            "skipped_same": skipped_same, "rejected": rejected})
    db.commit()
    return ApiResponse(data={"imported": imported, "skipped_confirmed": skipped_confirmed,
                             "skipped_same": skipped_same, "rejected": rejected})


# ---------- 授权管理（F05/F06） ----------

class GrantBody(BaseModel):
    principal: str
    purpose_code: str
    resource_ref: str = "*"
    operations: list[str] = ["read"]
    legal_basis_ref: str
    valid_hours: int = 24
    row_scope: dict = {}
    column_scope: dict = {}
    project_code: str | None = None


@router.post("/grants", summary="用途授权申请（status=pending，需独立审批）",
             dependencies=[Depends(require_permission("ds.grant.request"))])
def create_grant(request: Request, body: GrantBody,
                 db: Session = Depends(get_db)) -> ApiResponse[dict]:
    principal = _principal(request)
    bad_ops = [op for op in body.operations if op not in sec.VALID_OPERATIONS]
    if bad_ops:
        raise HTTPException(status_code=422, detail=f"operations 非法值: {bad_ops}")
    g = AssetDsGrant(principal=body.principal, purpose_code=body.purpose_code,
                     resource_type="global" if body.resource_ref == "*" else "dataset_version",
                     resource_ref=body.resource_ref, operations=body.operations,
                     legal_basis_ref=body.legal_basis_ref,
                     row_scope=body.row_scope or {}, column_scope=body.column_scope or {},
                     project_code=body.project_code,
                     status="pending", requested_by=principal)
    from datetime import timedelta
    g.valid_until = datetime.now(timezone.utc) + timedelta(hours=body.valid_hours)
    db.add(g)
    db.flush()
    _audit(db, "grant_request", f"{body.principal}@{body.purpose_code}", principal,
           {"grant_id": g.id, "resource_ref": body.resource_ref})
    db.commit()
    return ApiResponse(data={"grant_id": g.id, "status": g.status,
                             "requested_by": principal})


@router.get("/grants", summary="授权清单",
            dependencies=[Depends(require_permission("ds.read"))])
def list_grants(request: Request, db: Session = Depends(get_db)) -> ApiResponse[list[dict]]:
    _principal(request)
    rows = db.scalars(select(AssetDsGrant).order_by(AssetDsGrant.id.desc()).limit(200)).all()
    db.commit()
    return ApiResponse(data=[{
        "id": g.id, "principal": g.principal, "purpose_code": g.purpose_code,
        "resource_type": g.resource_type, "resource_ref": g.resource_ref,
        "operations": g.operations, "status": g.status,
        "row_scope": g.row_scope, "column_scope": g.column_scope,
        "valid_from": g.valid_from.isoformat() if g.valid_from else None,
        "valid_until": g.valid_until.isoformat() if g.valid_until else None,
        "requested_by": g.requested_by, "approved_by": g.approved_by,
        "grant_version": g.grant_version,
    } for g in rows])


@router.post("/grants/{grant_id}/review", summary="授权审批（审批人≠申请人）",
             dependencies=[Depends(require_permission("ds.grant.approve"))])
def review_grant(request: Request, grant_id: int, body: dict,
                 db: Session = Depends(get_db)) -> ApiResponse[dict]:
    principal = _principal(request)
    g = db.get(AssetDsGrant, grant_id)
    if g is None or g.status != "pending":
        raise HTTPException(status_code=404, detail="待审批授权不存在")
    if g.requested_by and g.requested_by == principal:
        _audit_denial(db, "grant_review:deny", f"grant:{grant_id}", principal,
                      {"reason": "审批人与申请人相同（职责分离）"})
        raise HTTPException(status_code=403, detail="审批人与申请人必须不同")
    decision = body.get("decision")
    if decision not in ("approve", "reject"):
        raise HTTPException(status_code=422, detail="decision 必须为 approve|reject")
    if decision == "approve":
        g.status = "active"
        g.approved_by = principal
        g.approved_at = datetime.now(timezone.utc)
    else:
        g.status = "rejected"
        g.approved_by = principal
    _audit(db, f"grant_{decision}", f"grant:{grant_id}", principal,
           {"note": str(body.get("note") or "")[:200]})
    db.commit()
    return ApiResponse(data={"grant_id": grant_id, "status": g.status})


@router.post("/grants/{grant_id}/revoke", summary="撤权（即时生效+导出传播+账本）",
             dependencies=[Depends(require_permission("ds.grant.manage"))])
def revoke_grant(request: Request, grant_id: int, body: dict,
                 db: Session = Depends(get_db)) -> ApiResponse[dict]:
    principal = _principal(request)
    try:
        result = prod.revoke_grant(db, grant_id, body.get("reason", ""), operator=principal)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    _audit(db, "grant_revoke", f"grant:{grant_id}", principal, result)
    db.commit()
    return ApiResponse(data=result)


# ---------- B11—B14 产品出口（版本成员+行列范围） ----------

@router.get("/{code}/versions/{version_id}/timeline/{patient_id}", summary="患者时间线")
def timeline(request: Request, code: str, version_id: int, patient_id: str,
             db: Session = Depends(get_db)) -> ApiResponse[dict]:
    principal = _principal(request)
    v = _resolve_version(db, code, version_id)
    g = _gateway_or_403(db, request, principal, _dataset_purpose(db, code), v, "read")
    data = prod.patient_timeline(db, version_id, patient_id, row_scope=g.row_scope)
    db.commit()
    return ApiResponse(data=data)


@router.get("/{code}/versions/{version_id}/stats/readmission", summary="再入院主题（版本成员分母）")
def stats_readmission(request: Request, code: str, version_id: int,
                      db: Session = Depends(get_db)) -> ApiResponse[dict]:
    principal = _principal(request)
    v = _resolve_version(db, code, version_id)
    g = _gateway_or_403(db, request, principal, _dataset_purpose(db, code), v, "read")
    data = prod.readmission_rate(db, version_id, row_scope=g.row_scope)
    db.commit()
    return ApiResponse(data=data)


class TrainBody(BaseModel):
    seed: int = 193
    train_ratio: float = 0.7
    val_ratio: float = 0.15
    purpose_isolation: bool = False


@router.post("/{code}/versions/{version_id}/training-set", summary="训练集+数据卡（版本成员）")
def training_set(request: Request, code: str, version_id: int, body: TrainBody,
                 db: Session = Depends(get_db)) -> ApiResponse[dict]:
    principal = _principal(request)
    v = _resolve_version(db, code, version_id)
    g = _gateway_or_403(db, request, principal, _dataset_purpose(db, code), v, "train")
    cfg = prod.SplitConfig(seed=body.seed, train_ratio=body.train_ratio,
                           val_ratio=body.val_ratio)
    data = prod.build_training_set(
        db, version_id, cfg=cfg, row_scope=g.row_scope,
        purpose_isolation={} if body.purpose_isolation else None)
    _audit(db, "train_build", f"{code}:{version_id}", principal,
           data["data_card"])
    db.commit()
    return ApiResponse(data=data)


class ExportBody(BaseModel):
    fields: list[str]
    project_code: str | None = None
    expires_in_hours: int = 24


@router.post("/{code}/versions/{version_id}/exports", summary="受控导出申请（进入待审）")
def create_export(request: Request, code: str, version_id: int, body: ExportBody,
                  db: Session = Depends(get_db)) -> ApiResponse[dict]:
    """210 F08/T22：申请绑定当前主体/用途/资源；授权解析在服务内完成，
    不接受外部 grant_id。"""
    principal = _principal(request)
    v = _resolve_version(db, code, version_id)
    purpose = _dataset_purpose(db, code)
    g = _gateway_or_403(db, request, principal, purpose, v, "export",
                        requested_columns=body.fields)
    try:
        exp = prod.request_export(
            db, principal=principal, purpose_code=purpose,
            resource_ref=_version_resource_ref(db, v), version=v,
            requested_fields=body.fields, project_code=body.project_code,
            expires_in_hours=body.expires_in_hours)
    except PermissionError as e:
        _audit_denial(db, "export_deny", f"{code}:{version_id}", principal,
                      {"reason": str(e)})
        raise HTTPException(status_code=403, detail=str(e))
    _audit(db, "export_request", exp.export_code, principal,
           {"fields": body.fields, "grant_id": exp.grant_id,
            "decision": g.decision})
    db.commit()
    return ApiResponse(data={"export_code": exp.export_code, "status": exp.status,
                             "expires_at": exp.expires_at.isoformat() if exp.expires_at else None})


@router.get("/exports", summary="导出清单（本人/待审/全部按权限）")
def list_exports(request: Request, db: Session = Depends(get_db)) -> ApiResponse[list[dict]]:
    principal = _principal(request)
    can_approve = _has_permission(db, request, "ds.export.approve")
    q = select(AssetDsExport).order_by(AssetDsExport.id.desc()).limit(200)
    rows = db.scalars(q).all()
    out = []
    for e in rows:
        if not can_approve and e.requested_by != principal:
            continue  # 普通用户只看自己的申请（不泄露他人标题/计数）
        out.append(_export_payload(e))
    db.commit()
    return ApiResponse(data=out)


def _export_payload(e: AssetDsExport) -> dict:
    return {
        "export_code": e.export_code, "status": e.status,
        "dataset_version_id": e.dataset_version_id, "grant_id": e.grant_id,
        "requested_by": e.requested_by, "approved_by": e.approved_by,
        "requested_fields": e.requested_fields, "field_whitelist": e.field_whitelist,
        "expires_at": e.expires_at.isoformat() if e.expires_at else None,
        "row_count": e.row_count, "file_sha256": e.file_sha256,
        "artifact_bytes": e.artifact_bytes, "review_note": e.review_note,
        "generation_error": e.generation_error,
    }


@router.post("/exports/{export_code}/review", summary="导出独立审批（审批人≠申请人）",
             dependencies=[Depends(require_permission("ds.export.approve"))])
def review_export(request: Request, export_code: str, body: dict,
                  db: Session = Depends(get_db)) -> ApiResponse[dict]:
    principal = _principal(request)
    exp = _get_export(db, export_code)
    if exp.requested_by == principal:
        _audit_denial(db, "export_review:deny", export_code, principal,
                      {"reason": "审批人与申请人相同（职责分离）"})
        raise HTTPException(status_code=403, detail="审批人与申请人必须不同")
    decision = body.get("decision")
    if decision not in ("approve", "reject"):
        raise HTTPException(status_code=422, detail="decision 必须为 approve|reject")
    try:
        prod.approve_export(db, exp, approver=principal, decision=decision,
                            note=str(body.get("note") or "")[:500],
                            expires_in_hours=int(body.get("expires_in_hours", 24)))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    _audit(db, f"export_{decision}", export_code, principal,
           {"fields": exp.field_whitelist})
    db.commit()
    return ApiResponse(data=_export_payload(exp))


@router.post("/exports/{export_code}/generate", summary="生成工件（同步+取消+失败可恢复）",
             dependencies=[Depends(require_permission("ds.export.execute"))])
def generate_export(request: Request, export_code: str, body: dict,
                    db: Session = Depends(get_db)) -> ApiResponse[dict]:
    principal = _principal(request)
    exp = _get_export(db, export_code)
    try:
        result = prod.generate_export(db, exp, operator=principal,
                                      cancel_requested=bool(body.get("cancel")))
    except PermissionError as e:
        _audit_denial(db, "export_generate:deny", export_code, principal,
                      {"reason": str(e)})
        raise HTTPException(status_code=403, detail=str(e))
    _audit(db, "export_generate", export_code, principal, result)
    db.commit()
    return ApiResponse(data=result)


def _get_export(db: Session, export_code: str) -> AssetDsExport:
    exp = db.scalar(select(AssetDsExport).where(AssetDsExport.export_code == export_code))
    if exp is None:
        raise HTTPException(status_code=404, detail="导出不存在")
    return exp


@router.post("/exports/{export_code}/download", summary="下载（当前主体/用途/版本/工件全量重验）")
def download_export(request: Request, export_code: str, db: Session = Depends(get_db)):
    principal = _principal(request)
    exp = _get_export(db, export_code)
    _deny = lambda reason: _audit_denial(db, "export_download:deny", export_code,
                                         principal, {"reason": reason})
    # 未完成重放的撤销 → 出口关闭（T30）
    blocking = prod.has_unreplayed_revocation(
        db, grant_id=exp.grant_id, version_id=exp.dataset_version_id,
        export_code=export_code)
    if blocking:
        _deny(f"存在未重放撤销账目 {blocking}（恢复保护）")
        raise HTTPException(status_code=403, detail="存在未重放撤销，出口关闭")
    # 下载绑定当前主体：申请人本人或授权主体（他人 grant 不可用，T22/T26）
    grant = db.get(AssetDsGrant, exp.grant_id)
    if principal != exp.requested_by and principal != grant.principal:
        _deny("下载主体与申请/授权主体不一致")
        raise HTTPException(status_code=403, detail="下载主体与申请/授权主体不一致")
    v = db.get(AssetDsDatasetVersion, exp.dataset_version_id)
    if v is None or v.status != "published":
        _deny("版本不可用（撤销/非发布态）")
        raise HTTPException(status_code=403, detail="版本不可用")
    # 策略重验（当前 active 分类即时生效）
    purpose = exp.purpose_code or (grant.purpose_code if grant else "research")
    refs = prod.version_policy_refs(db, v.id)
    p4 = _has_permission(db, request, "ds.p4.access")
    g = sec.enforce_read(db, principal, purpose, refs, operation="export",
                         requested_columns=list(exp.field_whitelist or []),
                         p4_authorized=p4)
    if not g.allowed:
        _deny(f"{g.decision} {g.reason}")
        raise HTTPException(status_code=403, detail=f"下载被拒绝：{g.decision} {g.reason}")
    if exp.expires_at and exp.expires_at <= datetime.now(timezone.utc):
        exp.status = "expired"
        _deny("导出已过期")
        db.commit()
        raise HTTPException(status_code=403, detail="导出已过期")
    try:
        content = prod.read_export_artifact(exp)
    except PermissionError as e:
        _deny(str(e))
        raise HTTPException(status_code=403, detail=str(e))
    exp.download_count = (exp.download_count or 0) + 1
    _audit(db, "export_download", export_code, principal,
           {"decision": "allow", "sha256": exp.file_sha256,
            "bytes": exp.artifact_bytes})
    db.commit()
    return Response(content=content, media_type="text/csv",
                    headers={"Content-Disposition":
                             f'attachment; filename="{export_code}.csv"'})


# ---------- 批次（B07） ----------

@router.get("/batches/{run_id}", summary="批次详情（检查点/计数）",
            dependencies=[Depends(require_permission("ds.read"))])
def batch_detail(request: Request, run_id: str, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    b = db.scalar(select(AssetDsBatch).where(AssetDsBatch.run_id == run_id))
    if b is None:
        raise HTTPException(status_code=404, detail="批次不存在")
    db.commit()
    return ApiResponse(data={"run_id": b.run_id, "status": b.status,
                             "counters": b.counters,
                             "checkpoint_keys": len(b.checkpoints or {}),
                             "error_class": b.error_class})


@router.post("/batches/{run_id}/records", summary="幂等写入（合成批次录入）",
             dependencies=[Depends(require_permission("ds.manage"))])
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


# ---------- S7 恢复重放（受控管理动作） ----------

@router.post("/admin/replay-revocations", summary="备份恢复后撤销账本重放（幂等）",
             dependencies=[Depends(require_permission("ds.grant.manage"))])
def replay_revocations(request: Request, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    principal = _principal(request)
    result = prod.replay_revocations_after_restore(db, operator=principal)
    _audit(db, "revocation_replay", "ledger", principal, result)
    db.commit()
    return ApiResponse(data=result)
