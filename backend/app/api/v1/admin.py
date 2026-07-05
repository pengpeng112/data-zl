import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from ...core.db import get_db
from ...models.governance import ApiKey, TableOwner, BusinessTerm, MetadataSnapshot
from ...schemas.common import ApiResponse

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

DEFAULT_TOKEN = "asset-platform-admin-2026"


class KeyCreateRequest(BaseModel):
    key_name: str


class OwnerUpsertRequest(BaseModel):
    full_table_name: str = Field(..., description="如 HIS.PAT_VISIT")
    owner_name: str | None = None
    department: str | None = None
    contact: str | None = None
    note: str | None = None


@router.get("/init", summary="初始化默认 API Token（首次使用一次性获取）")
def init_default_token(db: Session = Depends(get_db)) -> ApiResponse[dict]:
    existing = db.scalar(select(ApiKey).where(ApiKey.key_name == "default-admin"))
    if existing:
        raise HTTPException(status_code=403, detail="默认 Token 已存在，请使用已有 Token 或通过管理页面创建新 Key")
    key = ApiKey(key_name="default-admin", token=DEFAULT_TOKEN)
    db.add(key)
    db.commit()
    return ApiResponse(data={"token": DEFAULT_TOKEN, "message": "已创建默认 Token，请立即保存（后续不再返回）"})


@router.get("/keys", summary="API Key 列表")
def list_keys(
    db: Session = Depends(get_db),
) -> ApiResponse[list[dict]]:
    rows = db.scalars(select(ApiKey).order_by(ApiKey.created_at.desc())).all()
    items = [
        {
            "id": r.id,
            "key_name": r.key_name,
            "token": r.token[:8] + "..." if r.token else "",
            "enabled": r.enabled,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "last_used_at": r.last_used_at.isoformat() if r.last_used_at else None,
        }
        for r in rows
    ]
    return ApiResponse(data=items)


@router.post("/keys", summary="创建新 API Key")
def create_key(
    req: KeyCreateRequest,
    db: Session = Depends(get_db),

) -> ApiResponse[dict]:
    token = secrets.token_urlsafe(24)
    key = ApiKey(key_name=req.key_name, token=token)
    db.add(key)
    db.commit()
    return ApiResponse(data={"id": key.id, "key_name": key.key_name, "token": token, "warning": "Token 只显示一次，请立即保存"})


@router.patch("/keys/{key_id}", summary="禁用/启用 API Key")
def toggle_key(
    key_id: int,
    enabled: bool = Query(True),
    db: Session = Depends(get_db),

) -> ApiResponse[dict]:
    key = db.get(ApiKey, key_id)
    if not key:
        raise HTTPException(status_code=404)
    key.enabled = enabled
    db.commit()
    return ApiResponse(data={"id": key.id, "key_name": key.key_name, "enabled": key.enabled})


@router.get("/owners", summary="表 Owner 列表")
def list_owners(
    keyword: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=200),
    db: Session = Depends(get_db),

) -> ApiResponse[dict]:
    stmt = select(TableOwner)
    if keyword:
        stmt = stmt.where(TableOwner.full_table_name.ilike(f"%{keyword}%"))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(TableOwner.full_table_name)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    items = [
        {
            "id": r.id,
            "full_table_name": r.full_table_name,
            "owner_name": r.owner_name,
            "department": r.department,
            "contact": r.contact,
            "note": r.note,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        }
        for r in rows
    ]
    return ApiResponse(data={"total": total, "page": page, "page_size": page_size, "items": items})


@router.put("/owners", summary="设置/更新表 Owner")
def upsert_owner(
    req: OwnerUpsertRequest,
    db: Session = Depends(get_db),

) -> ApiResponse[dict]:
    owner = db.scalar(select(TableOwner).where(TableOwner.full_table_name == req.full_table_name))
    if owner:
        owner.owner_name = req.owner_name
        owner.department = req.department
        owner.contact = req.contact
        owner.note = req.note
        owner.updated_at = datetime.now(timezone.utc)
    else:
        owner = TableOwner(
            full_table_name=req.full_table_name,
            owner_name=req.owner_name,
            department=req.department,
            contact=req.contact,
            note=req.note,
        )
        db.add(owner)
    db.commit()
    db.refresh(owner)
    return ApiResponse(data={
        "id": owner.id, "full_table_name": owner.full_table_name, "owner_name": owner.owner_name
    })


@router.delete("/owners/{owner_id}", summary="删除 Owner")
def delete_owner(
    owner_id: int,
    db: Session = Depends(get_db),

) -> ApiResponse[dict]:
    owner = db.get(TableOwner, owner_id)
    if not owner:
        raise HTTPException(status_code=404)
    db.delete(owner)
    db.commit()
    return ApiResponse(data={"deleted": owner_id})


class TermUpsertRequest(BaseModel):
    term: str = Field(..., description="业务术语，如 住院号")
    mapping_target: str = Field(..., description="映射目标，如 HIS.PAT_MASTER_INDEX.INP_NO")
    mapping_type: str | None = "column"
    description: str | None = None


@router.get("/terms", summary="业务术语列表")
def list_terms(
    keyword: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=200),
    db: Session = Depends(get_db),

) -> ApiResponse[dict]:
    stmt = select(BusinessTerm)
    if keyword:
        stmt = stmt.where(
            BusinessTerm.term.ilike(f"%{keyword}%")
            | BusinessTerm.mapping_target.ilike(f"%{keyword}%")
        )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(BusinessTerm.term)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    items = [
        {
            "id": r.id, "term": r.term, "mapping_type": r.mapping_type,
            "mapping_target": r.mapping_target, "description": r.description,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
    return ApiResponse(data={"total": total, "page": page, "page_size": page_size, "items": items})


@router.put("/terms", summary="添加/更新业务术语")
def upsert_term(
    req: TermUpsertRequest,
    db: Session = Depends(get_db),

) -> ApiResponse[dict]:
    existing = db.scalar(
        select(BusinessTerm).where(BusinessTerm.term == req.term)
    )
    if existing:
        existing.mapping_target = req.mapping_target
        existing.mapping_type = req.mapping_type
        existing.description = req.description
    else:
        existing = BusinessTerm(
            term=req.term, mapping_target=req.mapping_target,
            mapping_type=req.mapping_type, description=req.description,
        )
        db.add(existing)
    db.commit()
    db.refresh(existing)
    return ApiResponse(data={"id": existing.id, "term": existing.term, "mapping_target": existing.mapping_target})


@router.delete("/terms/{term_id}", summary="删除业务术语")
def delete_term(
    term_id: int,
    db: Session = Depends(get_db),

) -> ApiResponse[dict]:
    term = db.get(BusinessTerm, term_id)
    if not term:
        raise HTTPException(status_code=404)
    db.delete(term)
    db.commit()
    return ApiResponse(data={"deleted": term_id})


@router.get("/terms/lookup", summary="按业务词查找映射")
def lookup_term(
    q: str = Query(..., description="业务词，如 住院号"),
    db: Session = Depends(get_db),

) -> ApiResponse[list[dict]]:
    rows = db.scalars(
        select(BusinessTerm).where(BusinessTerm.term.ilike(f"%{q}%"))
        .limit(20)
    ).all()
    items = [
        {"term": r.term, "mapping_type": r.mapping_type, "mapping_target": r.mapping_target, "description": r.description}
        for r in rows
    ]
    return ApiResponse(data=items)


class SnapshotCreateRequest(BaseModel):
    label: str | None = None


@router.post("/snapshots", summary="创建元数据快照")
def create_snapshot(
    req: SnapshotCreateRequest,
    db: Session = Depends(get_db),

) -> ApiResponse[dict]:
    import json
    from ...models.asset import AssetTable, AssetColumn, AssetRelation

    tables = db.scalars(select(AssetTable)).all()
    relations = db.scalars(select(AssetRelation)).all()

    snapshot_data = json.dumps(
        {
            "tables": [
                {"name": f"{t.schema_name}.{t.table_name}", "domain": t.domain, "column_count": t.column_count}
                for t in tables
            ],
            "relation_count": len(relations),
            "relation_ids": [r.rel_id for r in relations if r.rel_id],
        },
        ensure_ascii=False,
    )

    sp = MetadataSnapshot(
        label=req.label or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
        scope="asset",
        table_count=len(tables),
        column_count=db.scalar(select(func.count()).select_from(AssetColumn)) or 0,
        relation_count=len(relations),
        data=snapshot_data,
    )
    db.add(sp)
    db.commit()
    db.refresh(sp)
    return ApiResponse(data={
        "id": sp.id, "label": sp.label, "table_count": sp.table_count,
        "column_count": sp.column_count, "relation_count": sp.relation_count,
    })


@router.get("/snapshots", summary="快照列表")
def list_snapshots(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),

) -> ApiResponse[dict]:
    stmt = select(MetadataSnapshot)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(MetadataSnapshot.snapshot_time.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    items = [
        {
            "id": r.id, "label": r.label,
            "snapshot_time": r.snapshot_time.isoformat() if r.snapshot_time else None,
            "scope": r.scope, "table_count": r.table_count,
            "column_count": r.column_count, "relation_count": r.relation_count,
        }
        for r in rows
    ]
    return ApiResponse(data={"total": total, "page": page, "page_size": page_size, "items": items})


@router.get("/snapshots/compare", summary="对比两个快照")
def compare_snapshots(
    id1: int = Query(...),
    id2: int = Query(...),
    db: Session = Depends(get_db),

) -> ApiResponse[dict]:
    import json
    s1 = db.get(MetadataSnapshot, id1)
    s2 = db.get(MetadataSnapshot, id2)
    if not s1 or not s2:
        raise HTTPException(status_code=404, detail="快照不存在")

    d1 = json.loads(s1.data or "{}")
    d2 = json.loads(s2.data or "{}")
    t1 = {t["name"] for t in d1.get("tables", [])}
    t2 = {t["name"] for t in d2.get("tables", [])}

    added = sorted(t2 - t1)
    removed = sorted(t1 - t2)

    return ApiResponse(data={
        "snapshot1": {"id": s1.id, "label": s1.label, "tables": s1.table_count},
        "snapshot2": {"id": s2.id, "label": s2.label, "tables": s2.table_count},
        "tables_added": len(added), "tables_removed": len(removed),
        "added": added[:100], "removed": removed[:100],
        "relations_s1": d1.get("relation_count", 0),
        "relations_s2": d2.get("relation_count", 0),
        "relation_delta": d2.get("relation_count", 0) - d1.get("relation_count", 0),
    })


@router.post("/init/backfill-p6", summary="回填 asset_tables/columns 的 system_code/source_code/namespace_name（P6 数据初始化）")
def backfill_p6(
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    from ...models.asset import AssetTable, AssetColumn
    from ...models.asset_system import AssetSystem, AssetDataSource

    # ensure DATA_CENTER system exists
    sys = db.scalar(select(AssetSystem).where(AssetSystem.system_code == "DATA_CENTER"))
    if not sys:
        sys = AssetSystem(
            system_code="DATA_CENTER",
            system_name_cn="数据中心",
            system_type="ODS",
            description_cn="10.10.8.216 数据中心 ODS 汇聚库",
        )
        db.add(sys)
        db.flush()

    # ensure ods_8_216 source exists
    ds = db.scalar(select(AssetDataSource).where(AssetDataSource.source_code == "ods_8_216"))
    if not ds:
        ds = AssetDataSource(
            system_code="DATA_CENTER",
            source_code="ods_8_216",
            source_name_cn="8.216 ODS 汇聚库",
            db_type="oracle",
            host_masked="10.10.8.216",
            port=1521,
            service_name="orcl",
            environment="prod",
            collect_mode="metadata_only",
        )
        db.add(ds)
        db.flush()

    updated_t = 0
    updated_c = 0
    skipped = 0

    for t in db.scalars(select(AssetTable)).all():
        changed = False
        if not t.system_code:
            t.system_code = "DATA_CENTER"
            changed = True
        if not t.source_code:
            t.source_code = "ods_8_216"
            changed = True
        if not t.namespace_name and t.schema_name:
            t.namespace_name = t.schema_name
            changed = True
        if changed:
            updated_t += 1
        else:
            skipped += 1

    for c in db.scalars(select(AssetColumn)).all():
        changed = False
        if not c.system_code:
            c.system_code = "DATA_CENTER"
            changed = True
        if not c.source_code:
            c.source_code = "ods_8_216"
            changed = True
        if not c.namespace_name and c.schema_name:
            c.namespace_name = c.schema_name
            changed = True
        if changed:
            updated_c += 1
        else:
            skipped += 1

    count_tables = db.scalar(select(func.count()).select_from(AssetTable)) or 0

    db.commit()

    return ApiResponse(data={
        "message": f"系统 DATA_CENTER、数据源 ods_8_216 已就绪，{count_tables} 张表, tables_updated={updated_t}, columns_updated={updated_c}, skipped={skipped}",
        "system_count": 1,
        "source_count": 1,
        "table_count": count_tables,
    })


@router.post("/init/import-his-source", summary="导入 HIS 源端 1234 表资产（从 CSV 读取，仅首次运行）")
def import_his_source(
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    import csv, os
    from ...models.asset import AssetTable, AssetColumn
    from ...models.asset_system import AssetSystem, AssetDataSource

    base = r"F:\python\数据资产\开发起步包\数据资产_HIS源端资产包"
    tables_csv = os.path.join(base, "his_source_tables.csv")
    columns_csv = os.path.join(base, "his_source_columns.csv")

    if not os.path.exists(tables_csv):
        raise HTTPException(status_code=404, detail=f"找不到 {tables_csv}")

    # ensure system and source
    sys = db.scalar(select(AssetSystem).where(AssetSystem.system_code == "HIS_SOURCE"))
    if not sys:
        sys = AssetSystem(
            system_code="HIS_SOURCE",
            system_name_cn="HIS 源端",
            system_type="HIS",
            description_cn="10.10.10.15/his 多 owner 业务库",
        )
        db.add(sys)
        db.flush()

    ds = db.scalar(select(AssetDataSource).where(AssetDataSource.source_code == "his_source_10_10_10_15"))
    if not ds:
        ds = AssetDataSource(
            system_code="HIS_SOURCE",
            source_code="his_source_10_10_10_15",
            source_name_cn="10.10.10.15 HIS 业务库",
            db_type="oracle",
            host_masked="10.10.10.15",
            port=1521,
            service_name="his",
            environment="prod",
            collect_mode="metadata_only",
        )
        db.add(ds)
        db.flush()

    existing = db.scalar(
        select(func.count()).select_from(AssetTable).where(AssetTable.source_code == "his_source_10_10_10_15")
    ) or 0
    if existing > 100:
        return ApiResponse(data={"message": f"HIS 源端已有 {existing} 张表，跳过重复导入"})

    table_count = 0
    col_count = 0

    with open(tables_csv, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            t = AssetTable(
                system_code="HIS_SOURCE",
                source_code="his_source_10_10_10_15",
                namespace_name=(row.get("source_owner") or "").strip(),
                schema_name=(row.get("source_owner") or "").strip(),
                table_name=(row.get("table_name") or "").strip(),
                table_role=(row.get("table_role") or "").strip(),
                business_desc_cn=(row.get("domain") or "").strip(),
                column_count=int(row["column_count"]) if row.get("column_count") and row["column_count"].isdigit() else 0,
                pk=(row.get("primary_key") or "").strip(),
                domain=(row.get("domain") or "").strip(),
                include_status=(row.get("include_status") or "candidate").strip(),
                note=(row.get("include_note") or "").strip(),
                source=(row.get("source_db") or "").strip(),
            )
            db.add(t)
            table_count += 1

    db.flush()

    if os.path.exists(columns_csv):
        with open(columns_csv, encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                c = AssetColumn(
                    system_code="HIS_SOURCE",
                    source_code="his_source_10_10_10_15",
                    namespace_name=(row.get("source_owner") or "").strip(),
                    schema_name=(row.get("source_owner") or "").strip(),
                    table_name=(row.get("table_name") or "").strip(),
                    column_id=int(row["column_id"]) if row.get("column_id") and row["column_id"].isdigit() else 0,
                    column_name=(row.get("column_name") or "").strip(),
                    data_type=(row.get("data_type") or "").strip(),
                    length=int(row["length"]) if row.get("length") and row["length"].isdigit() else 0,
                    nullable=(row.get("nullable") or "").strip(),
                    comment=(row.get("comment") or "").strip(),
                    is_sensitive=False,
                )
                db.add(c)
                col_count += 1

    db.commit()

    return ApiResponse(data={
        "message": f"HIS 源端导入完成：{table_count} 张表, {col_count} 列",
        "system": "HIS_SOURCE",
        "source": "his_source_10_10_10_15",
        "table_count": table_count,
        "column_count": col_count,
    })
