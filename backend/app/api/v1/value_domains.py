"""149 P1b: 字段值域知识库路由（/api/v1/value-domains）。

权限（149 §3）：
  value_domain.read    查询（含冲突列表 / updated_since 增量）
  value_domain.submit  提交 pending 候选与追加证据（AI 可用；evidence 必填）
  value_domain.confirm 人工确认 / 废弃 / 冲突裁决（AI 角色不授予）

冲突检测（149 §2.4，纯库内比对，不依赖 SQL 解析）：
  同 (定位键, code) 新写入 meaning 与现行记录不一致 → conflict_status=conflicted
  并在响应中列出 competing meanings；未裁决冲突记录不进入 AI 注入链路。

写操作全部落 asset_govern_audit_logs。
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...core.db import get_db
from ...core.security import get_current_user, require_permission
from ...models.governance_base import GovernAuditLog
from ...models.value_domain import (
    AssetColumnValueDomain,
    AssetColumnValueDomainEvidence,
    AssetColumnValueDomainVersion,
)
from ...schemas.common import ApiResponse
from ...services import value_domain_service as vds

router = APIRouter(prefix="/api/v1/value-domains", tags=["value_domains"])

VALID_DOMAIN_KINDS = {"enum", "threshold", "literal", "trap"}
VALID_SOURCE_TYPES = {"live_probe", "cross_system", "dict_table", "manual", "ai_probe"}


class EvidenceIn(BaseModel):
    source_type: str = Field(..., description="live_probe/cross_system/dict_table/manual/ai_probe")
    source_system: str | None = None
    observed_meaning: str | None = Field(
        None, description="该来源观测到的含义；与主表不一致时触发冲突检测"
    )
    method: str | None = None
    sample_count: int | None = Field(default=None, ge=0)
    observed_at: datetime | None = None
    actor: str | None = None
    snippet_ref: str | None = Field(None, description="证据原文引用，如 148 文档小节号")


class ValueDomainCreate(BaseModel):
    system_code: str = Field(..., min_length=1)
    source_code: str = Field(..., min_length=1)
    schema_name: str = Field(..., min_length=1)
    table_name: str = Field(..., min_length=1)
    column_name: str = Field(..., min_length=1)
    code: str = Field(..., min_length=1, description="枚举码/阈值表达式/字面量/陷阱标识")
    meaning: str = Field(..., min_length=1)
    note: str | None = None
    domain_kind: str = Field("enum", description="enum/threshold/literal/trap")
    scope_condition: str | None = None
    evidences: list[EvidenceIn] = Field(..., min_length=1, description="证据必填（149 §3）")


class ConfirmRequest(BaseModel):
    reason: str | None = None


class DeprecateRequest(BaseModel):
    reason: str = Field(..., min_length=1)


class ResolveConflictRequest(BaseModel):
    meaning: str = Field(..., min_length=1, description="人工裁决采纳的含义")
    note: str | None = None
    reason: str = Field(..., min_length=1)


def _validate_enums(req: ValueDomainCreate) -> None:
    if req.domain_kind not in VALID_DOMAIN_KINDS:
        raise HTTPException(status_code=400, detail=f"domain_kind 仅允许 {sorted(VALID_DOMAIN_KINDS)}")
    for ev in req.evidences:
        if ev.source_type not in VALID_SOURCE_TYPES:
            raise HTTPException(
                status_code=400, detail=f"evidence.source_type 仅允许 {sorted(VALID_SOURCE_TYPES)}"
            )


def _audit(
    db: Session,
    *,
    action: str,
    entity_ref: str,
    operator: str | None,
    before: dict | None = None,
    after: dict | None = None,
    reason: str | None = None,
) -> None:
    db.add(
        GovernAuditLog(
            module="value_domain",
            entity_type="column_value_domain",
            entity_ref=entity_ref,
            action=action,
            before_data=before,
            after_data=after,
            operator=operator,
            reason=reason,
        )
    )


def _row_payload(db: Session, row: AssetColumnValueDomain) -> dict:
    evidence_count = db.scalar(
        select(func.count()).select_from(AssetColumnValueDomainEvidence).where(
            AssetColumnValueDomainEvidence.domain_id == row.id
        )
    )
    return {
        "id": row.id,
        "system_code": row.system_code,
        "source_code": row.source_code,
        "schema_name": row.schema_name,
        "table_name": row.table_name,
        "column_name": row.column_name,
        "code": row.code,
        "meaning": row.meaning,
        "note": row.note,
        "domain_kind": row.domain_kind,
        "scope_condition": row.scope_condition,
        "status": row.status,
        "conflict_status": row.conflict_status,
        "confirmed_by": row.confirmed_by,
        "confirmed_at": row.confirmed_at.isoformat() if row.confirmed_at else None,
        "current_version_id": row.current_version_id,
        "version_no": vds.version_no_of(db, row),
        "evidence_count": int(evidence_count or 0),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


@router.get("", summary="值域列表（过滤 + conflicted 冲突列表 + updated_since 增量）")
def list_value_domains(
    system_code: str | None = Query(None),
    source_code: str | None = Query(None),
    schema_name: str | None = Query(None),
    table_name: str | None = Query(None),
    column_name: str | None = Query(None),
    code: str | None = Query(None),
    domain_kind: str | None = Query(None),
    status: str | None = Query(None, description="pending/confirmed/deprecated"),
    conflicted: bool | None = Query(None, description="true=仅未裁决冲突"),
    updated_since: datetime | None = Query(None, description="增量拉取（ISO 时间）"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
    _user: str = Depends(require_permission("value_domain.read")),
) -> ApiResponse[dict]:
    stmt = select(AssetColumnValueDomain)
    if system_code:
        stmt = stmt.where(AssetColumnValueDomain.system_code == system_code)
    if source_code:
        stmt = stmt.where(AssetColumnValueDomain.source_code == source_code)
    if schema_name:
        stmt = stmt.where(AssetColumnValueDomain.schema_name == schema_name)
    if table_name:
        stmt = stmt.where(AssetColumnValueDomain.table_name == table_name)
    if column_name:
        stmt = stmt.where(AssetColumnValueDomain.column_name == column_name)
    if code:
        stmt = stmt.where(AssetColumnValueDomain.code == code)
    if domain_kind:
        stmt = stmt.where(AssetColumnValueDomain.domain_kind == domain_kind)
    if status:
        stmt = stmt.where(AssetColumnValueDomain.status == status)
    if conflicted is True:
        stmt = stmt.where(AssetColumnValueDomain.conflict_status == "conflicted")
    if conflicted is False:
        stmt = stmt.where(AssetColumnValueDomain.conflict_status == "none")
    if updated_since:
        stmt = stmt.where(AssetColumnValueDomain.updated_at > updated_since)

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(AssetColumnValueDomain.updated_at.desc(), AssetColumnValueDomain.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return ApiResponse(
        data={
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [_row_payload(db, r) for r in rows],
        }
    )


@router.get("/{domain_id}", summary="值域详情（含全部证据）")
def get_value_domain(
    domain_id: int,
    db: Session = Depends(get_db),
    _user: str = Depends(require_permission("value_domain.read")),
) -> ApiResponse[dict]:
    row = db.get(AssetColumnValueDomain, domain_id)
    if not row:
        raise HTTPException(status_code=404, detail="值域记录不存在")
    evidences = db.scalars(
        select(AssetColumnValueDomainEvidence)
        .where(AssetColumnValueDomainEvidence.domain_id == domain_id)
        .order_by(AssetColumnValueDomainEvidence.id)
    ).all()
    payload = _row_payload(db, row)
    payload["evidences"] = [
        {
            "id": ev.id,
            "source_type": ev.source_type,
            "source_system": ev.source_system,
            "observed_meaning": ev.observed_meaning,
            "method": ev.method,
            "sample_count": ev.sample_count,
            "observed_at": ev.observed_at.isoformat() if ev.observed_at else None,
            "actor": ev.actor,
            "snippet_ref": ev.snippet_ref,
        }
        for ev in evidences
    ]
    return ApiResponse(data=payload)


@router.get("/{domain_id}/versions", summary="值域版本时间线")
def list_value_domain_versions(
    domain_id: int,
    db: Session = Depends(get_db),
    _user: str = Depends(require_permission("value_domain.read")),
) -> ApiResponse[dict]:
    row = db.get(AssetColumnValueDomain, domain_id)
    if not row:
        raise HTTPException(status_code=404, detail="值域记录不存在")
    versions = db.scalars(
        select(AssetColumnValueDomainVersion)
        .where(AssetColumnValueDomainVersion.domain_id == domain_id)
        .order_by(AssetColumnValueDomainVersion.version_no)
    ).all()
    return ApiResponse(
        data={
            "domain_id": domain_id,
            "current_version_no": vds.version_no_of(db, row),
            "items": [
                {
                    "id": v.id,
                    "version_no": v.version_no,
                    "snapshot": v.snapshot,
                    "change_reason": v.change_reason,
                    "evidence_ref": v.evidence_ref,
                    "actor": v.actor,
                    "created_at": v.created_at.isoformat() if v.created_at else None,
                }
                for v in versions
            ],
        }
    )


@router.post("", summary="提交值域候选（pending；证据必填；先查后插；新建 201/追加证据 200）")
def create_value_domain(
    req: ValueDomainCreate,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    _user: str = Depends(require_permission("value_domain.submit")),
) -> ApiResponse[dict]:
    _validate_enums(req)
    operator = get_current_user(request)
    existing = vds.find_by_key(
        db,
        system_code=req.system_code,
        source_code=req.source_code,
        schema_name=req.schema_name,
        table_name=req.table_name,
        column_name=req.column_name,
        code=req.code,
    )

    if existing is None:
        row = AssetColumnValueDomain(
            system_code=req.system_code,
            source_code=req.source_code,
            schema_name=req.schema_name,
            table_name=req.table_name,
            column_name=req.column_name,
            code=req.code,
            meaning=req.meaning,
            note=req.note,
            domain_kind=req.domain_kind,
            scope_condition=req.scope_condition,
            status="pending",
            conflict_status="none",
        )
        db.add(row)
        db.flush()
        for ev in req.evidences:
            db.add(vds.evidence_row(row.id, ev.model_dump()))
        version = vds.next_version(
            db, row, change_reason="submit", actor=operator,
            evidence_ref=req.evidences[0].snippet_ref,
        )
        _audit(
            db,
            action="submit",
            entity_ref=str(row.id),
            operator=operator,
            after={**vds.snapshot_of(row), "key": _key_of(row)},
        )
        db.commit()
        db.refresh(row)
        response.status_code = 201
        return ApiResponse(
            code=0,
            data={"created": True, "attached": False, **_row_payload(db, row), "version_no": version.version_no},
        )

    # 先查后插：同键已存在——meaning 一致则追加证据（幂等富化），不一致则置冲突
    if vds.meanings_differ(existing.meaning, req.meaning):
        changed = vds.mark_conflict(db, existing)
        dissent = req.evidences[0].model_dump()
        dissent.setdefault("observed_meaning", req.meaning)
        db.add(vds.evidence_row(existing.id, dissent))
        _audit(
            db,
            action="conflict_detected",
            entity_ref=str(existing.id),
            operator=operator,
            before={"meaning": existing.meaning, "conflict_status": "none" if changed else "conflicted"},
            after={
                "conflict_status": "conflicted",
                "proposed_meaning": req.meaning,
                "key": _key_of(existing),
            },
        )
        db.commit()
        raise HTTPException(
            status_code=409,
            detail={
                "message": "同字段同 code 已存在含义不一致的候选，已置为冲突待人工裁决",
                "domain_id": existing.id,
                "conflict_status": "conflicted",
                "competing_meanings": [
                    {"source": "existing", "meaning": existing.meaning},
                    {"source": "proposed", "meaning": req.meaning},
                ],
            },
        )

    appended = 0
    for ev in req.evidences:
        item = ev.model_dump()
        if vds.evidence_duplicate(db, existing.id, item):
            continue
        db.add(vds.evidence_row(existing.id, item))
        appended += 1
    if appended:
        existing.updated_at = datetime.now(timezone.utc)
        _audit(
            db,
            action="attach_evidence",
            entity_ref=str(existing.id),
            operator=operator,
            after={"appended": appended, "key": _key_of(existing)},
        )
    db.commit()
    db.refresh(existing)
    return ApiResponse(
        code=0,
        data={"created": False, "attached": True, "appended_evidences": appended, **_row_payload(db, existing)},
    )


@router.post("/{domain_id}/evidences", summary="向既有值域追加证据（含对立证据冲突检测）")
def add_evidence(
    domain_id: int,
    ev: EvidenceIn,
    request: Request,
    db: Session = Depends(get_db),
    _user: str = Depends(require_permission("value_domain.submit")),
) -> ApiResponse[dict]:
    row = db.get(AssetColumnValueDomain, domain_id)
    if not row:
        raise HTTPException(status_code=404, detail="值域记录不存在")
    if ev.source_type not in VALID_SOURCE_TYPES:
        raise HTTPException(status_code=400, detail=f"evidence.source_type 仅允许 {sorted(VALID_SOURCE_TYPES)}")
    operator = get_current_user(request)
    item = ev.model_dump()
    if vds.evidence_duplicate(db, row.id, item):
        return ApiResponse(data={"domain_id": row.id, "appended": 0, "duplicate": True})

    db.add(vds.evidence_row(row.id, item))
    conflict = False
    if ev.observed_meaning is not None and vds.meanings_differ(row.meaning, ev.observed_meaning):
        vds.mark_conflict(db, row)
        conflict = True
    row.updated_at = datetime.now(timezone.utc)
    _audit(
        db,
        action="conflict_detected" if conflict else "attach_evidence",
        entity_ref=str(row.id),
        operator=operator,
        before={"meaning": row.meaning},
        after={"observed_meaning": ev.observed_meaning, "conflict_status": row.conflict_status},
    )
    db.commit()
    return ApiResponse(
        data={
            "domain_id": row.id,
            "appended": 1,
            "conflict_detected": conflict,
            "conflict_status": row.conflict_status,
            "competing_meanings": (
                [
                    {"source": "existing", "meaning": row.meaning},
                    {"source": "evidence", "meaning": ev.observed_meaning},
                ]
                if conflict
                else None
            ),
        }
    )


@router.patch("/{domain_id}/confirm", summary="人工确认值域（AI 角色无此权限码）")
def confirm_value_domain(
    domain_id: int,
    req: ConfirmRequest,
    request: Request,
    db: Session = Depends(get_db),
    _user: str = Depends(require_permission("value_domain.confirm")),
) -> ApiResponse[dict]:
    row = db.get(AssetColumnValueDomain, domain_id)
    if not row:
        raise HTTPException(status_code=404, detail="值域记录不存在")
    if row.conflict_status == "conflicted":
        raise HTTPException(
            status_code=409,
            detail={
                "message": "存在未裁决冲突，须先 resolve-conflict 再确认",
                "domain_id": row.id,
                "conflict_status": row.conflict_status,
            },
        )
    operator = get_current_user(request)
    before = vds.snapshot_of(row)
    row.status = "confirmed"
    row.confirmed_by = operator
    row.confirmed_at = datetime.now(timezone.utc)
    version = vds.next_version(
        db, row, change_reason="confirm", actor=operator, evidence_ref=req.reason
    )
    _audit(
        db,
        action="confirm",
        entity_ref=str(row.id),
        operator=operator,
        before=before,
        after=vds.snapshot_of(row),
        reason=req.reason,
    )
    db.commit()
    db.refresh(row)
    return ApiResponse(data={**_row_payload(db, row), "version_no": version.version_no})


@router.patch("/{domain_id}/deprecate", summary="废弃值域（退出注入链路）")
def deprecate_value_domain(
    domain_id: int,
    req: DeprecateRequest,
    request: Request,
    db: Session = Depends(get_db),
    _user: str = Depends(require_permission("value_domain.confirm")),
) -> ApiResponse[dict]:
    row = db.get(AssetColumnValueDomain, domain_id)
    if not row:
        raise HTTPException(status_code=404, detail="值域记录不存在")
    operator = get_current_user(request)
    before = vds.snapshot_of(row)
    row.status = "deprecated"
    version = vds.next_version(
        db, row, change_reason="deprecate", actor=operator, evidence_ref=req.reason
    )
    _audit(
        db,
        action="deprecate",
        entity_ref=str(row.id),
        operator=operator,
        before=before,
        after=vds.snapshot_of(row),
        reason=req.reason,
    )
    db.commit()
    db.refresh(row)
    return ApiResponse(data={**_row_payload(db, row), "version_no": version.version_no})


@router.patch("/{domain_id}/resolve-conflict", summary="人工裁决冲突（采纳含义并解除冲突）")
def resolve_conflict(
    domain_id: int,
    req: ResolveConflictRequest,
    request: Request,
    db: Session = Depends(get_db),
    _user: str = Depends(require_permission("value_domain.confirm")),
) -> ApiResponse[dict]:
    row = db.get(AssetColumnValueDomain, domain_id)
    if not row:
        raise HTTPException(status_code=404, detail="值域记录不存在")
    if row.conflict_status != "conflicted":
        raise HTTPException(status_code=400, detail="该记录当前无未裁决冲突")
    operator = get_current_user(request)
    before = vds.snapshot_of(row)
    row.meaning = req.meaning
    if req.note is not None:
        row.note = req.note
    row.conflict_status = "none"
    version = vds.next_version(
        db, row, change_reason="resolve_conflict", actor=operator, evidence_ref=req.reason
    )
    _audit(
        db,
        action="resolve_conflict",
        entity_ref=str(row.id),
        operator=operator,
        before=before,
        after=vds.snapshot_of(row),
        reason=req.reason,
    )
    db.commit()
    db.refresh(row)
    return ApiResponse(data={**_row_payload(db, row), "version_no": version.version_no})


def _key_of(row: AssetColumnValueDomain) -> str:
    return (
        f"{row.system_code}|{row.source_code}|{row.schema_name}|"
        f"{row.table_name}|{row.column_name}|{row.code}"
    )
