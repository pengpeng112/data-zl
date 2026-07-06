from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.expression import ColumnElement
from pydantic import BaseModel, Field

from ...core.db import get_db
from ...models.asset import AssetColumn, AssetRelation, AssetTable
from ...schemas.asset import ColumnOut, RelationOut, SummaryOut, TableBrief, TableDetail
from ...schemas.common import ApiResponse, PageData

router = APIRouter(prefix="/api/v1", tags=["tables"])

TABLE_SORT_COLUMNS: dict[str, ColumnElement] = {
    "schema_name": AssetTable.schema_name,
    "table_name": AssetTable.table_name,
    "column_count": AssetTable.column_count,
    "domain": AssetTable.domain,
}

COLUMN_SORT_COLUMNS: dict[str, ColumnElement] = {
    "schema_name": AssetColumn.schema_name,
    "table_name": AssetColumn.table_name,
    "column_name": AssetColumn.column_name,
    "column_id": AssetColumn.column_id,
    "data_type": AssetColumn.data_type,
}


def _parse_sort(sort_str: str | None, whitelist: dict[str, ColumnElement]) -> ColumnElement | None:
    if not sort_str:
        return None
    desc = False
    field = sort_str
    if field.startswith("-"):
        desc = True
        field = field[1:]
    if field not in whitelist:
        raise HTTPException(status_code=400, detail=f"不支持的排序字段: {field}，可选: {', '.join(whitelist.keys())}")
    col = whitelist[field]
    return col.desc() if desc else col.asc()


@router.get("/summary", response_model=ApiResponse[SummaryOut], summary="数据资产总览")
def summary(db: Session = Depends(get_db)) -> ApiResponse[SummaryOut]:
    t = db.scalar(select(func.count()).select_from(AssetTable))
    c = db.scalar(select(func.count()).select_from(AssetColumn))
    r = db.scalar(select(func.count()).select_from(AssetRelation))
    d = db.scalar(
        select(func.count(func.distinct(AssetTable.domain))).where(AssetTable.domain.isnot(None))
    )
    return ApiResponse(
        data=SummaryOut(tables=t or 0, columns=c or 0, relations=r or 0, domains=d or 0)
    )


def _build_table_query(
    keyword: str | None = None,
    domain: str | None = None,
    system_code: str | None = None,
    source_code: str | None = None,
    schema_name: str | None = None,
):
    stmt = select(AssetTable)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(
            AssetTable.schema_name.ilike(like)
            | AssetTable.table_name.ilike(like)
            | AssetTable.comment.ilike(like)
        )
    if domain:
        stmt = stmt.where(AssetTable.domain == domain)
    if system_code:
        stmt = stmt.where(AssetTable.system_code == system_code)
    if source_code:
        stmt = stmt.where(AssetTable.source_code == source_code)
    if schema_name:
        stmt = stmt.where(AssetTable.schema_name == schema_name)
    return stmt


@router.get("/tables", response_model=ApiResponse[PageData[TableBrief]], summary="表清单（搜索/分页）")
def list_tables(
    keyword: str | None = Query(None, description="按 schema/table/comment 模糊匹配"),
    domain: str | None = None,
    system_code: str | None = None,
    source_code: str | None = None,
    schema_name: str | None = None,
    sort: str | None = Query(None, description="排序字段: schema_name/table_name/column_count/domain，前缀 - 表示降序"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=200, description="每页条数"),
    db: Session = Depends(get_db),
) -> ApiResponse[PageData[TableBrief]]:
    base = _build_table_query(keyword, domain, system_code, source_code, schema_name)
    total = db.scalar(select(func.count()).select_from(base.subquery()))
    order = _parse_sort(sort, TABLE_SORT_COLUMNS)
    stmt = base.order_by(order) if order is not None else base.order_by(AssetTable.schema_name, AssetTable.table_name)
    stmt = stmt.limit(page_size).offset((page - 1) * page_size)
    items = [TableBrief.model_validate(r) for r in db.scalars(stmt)]
    return ApiResponse(
        data=PageData(total=total or 0, page=page, page_size=page_size, items=items)
    )


def _full(schema_name: str, table_name: str) -> str:
    return f"{schema_name}.{table_name}"


@router.get("/tables/{schema}/{table}", response_model=ApiResponse[dict], summary="表详情")
def get_table(schema: str, table: str, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    row = db.scalar(
        select(AssetTable).where(
            AssetTable.schema_name == schema, AssetTable.table_name == table
        )
    )
    if not row:
        raise HTTPException(status_code=404, detail="表不存在")
    detail = TableDetail.model_validate(row)
    full = _full(schema, table)
    rel_count = db.scalar(
        select(func.count()).select_from(AssetRelation).where(
            (AssetRelation.from_table == full) | (AssetRelation.to_table == full)
        )
    )
    col_count = db.scalar(
        select(func.count()).select_from(AssetColumn).where(
            AssetColumn.schema_name == schema, AssetColumn.table_name == table
        )
    )
    return ApiResponse(
        data={
            **detail.model_dump(),
            "relation_count": rel_count or 0,
            "column_count_actual": col_count or 0,
        }
    )


@router.get(
    "/tables/{schema}/{table}/columns",
    response_model=ApiResponse[list[ColumnOut]],
    summary="表字段清单",
)
def get_columns(schema: str, table: str, db: Session = Depends(get_db)) -> ApiResponse[list[ColumnOut]]:
    stmt = (
        select(AssetColumn)
        .where(AssetColumn.schema_name == schema, AssetColumn.table_name == table)
        .order_by(AssetColumn.column_id)
    )
    return ApiResponse(data=[ColumnOut.model_validate(r) for r in db.scalars(stmt)])


@router.get("/columns/search", response_model=ApiResponse[PageData[ColumnOut]], summary="字段搜索")
def search_columns(
    keyword: str = Query(..., min_length=1, description="字段名/注释关键词"),
    sort: str | None = Query(None, description="排序字段: schema_name/table_name/column_name/column_id/data_type，前缀 - 表示降序"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
) -> ApiResponse[PageData[ColumnOut]]:
    like = f"%{keyword}%"
    base = select(AssetColumn).where(
        AssetColumn.column_name.ilike(like) | AssetColumn.comment.ilike(like)
    )
    total = db.scalar(select(func.count()).select_from(base.subquery()))
    order = _parse_sort(sort, COLUMN_SORT_COLUMNS)
    stmt = base.order_by(order) if order is not None else base.order_by(AssetColumn.schema_name, AssetColumn.table_name, AssetColumn.column_id)
    stmt = stmt.limit(page_size).offset((page - 1) * page_size)
    items = [ColumnOut.model_validate(r) for r in db.scalars(stmt)]
    return ApiResponse(
        data=PageData(total=total or 0, page=page, page_size=page_size, items=items)
    )


@router.get(
    "/tables/{schema}/{table}/relations",
    response_model=ApiResponse[list[RelationOut]],
    summary="该表的关联关系（上下游）",
)
def get_table_relations(
    schema: str, table: str, db: Session = Depends(get_db)
) -> ApiResponse[list[RelationOut]]:
    full = _full(schema, table)
    stmt = select(AssetRelation).where(
        (AssetRelation.from_table == full) | (AssetRelation.to_table == full)
    )
    return ApiResponse(data=[RelationOut.model_validate(r) for r in db.scalars(stmt)])


# ──────────────────────────────────────────────
# P7 中文注释治理 API
# ──────────────────────────────────────────────

class TableAnnotationUpdate(BaseModel):
    table_name_cn: str | None = None
    business_desc_cn: str | None = None
    table_role: str | None = None
    note: str | None = None


class ColumnAnnotationUpdate(BaseModel):
    column_name_cn: str | None = None
    business_desc_cn: str | None = None
    value_desc_cn: str | None = None
    semantic_type: str | None = None
    is_sensitive: bool | None = None
    comment: str | None = None


@router.patch("/tables/{table_id}/annotation", summary="更新表中文名/业务说明")
def update_table_annotation(table_id: int, req: TableAnnotationUpdate, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    t = db.get(AssetTable, table_id)
    if not t:
        raise HTTPException(status_code=404)
    for key in ("table_name_cn", "business_desc_cn", "table_role", "note"):
        val = getattr(req, key)
        if val is not None:
            setattr(t, key, val)
    db.commit()
    return ApiResponse(data={"id": t.id, "table_name": t.table_name, "table_name_cn": t.table_name_cn})


@router.patch("/columns/{column_id}/annotation", summary="更新字段中文名/业务说明/取值说明")
def update_column_annotation(column_id: int, req: ColumnAnnotationUpdate, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    c = db.get(AssetColumn, column_id)
    if not c:
        raise HTTPException(status_code=404)
    for key in ("column_name_cn", "business_desc_cn", "value_desc_cn", "semantic_type", "comment"):
        val = getattr(req, key)
        if val is not None:
            setattr(c, key, val)
    if req.is_sensitive is not None:
        c.is_sensitive = req.is_sensitive
    db.commit()
    return ApiResponse(data={"id": c.id, "column_name": c.column_name, "column_name_cn": c.column_name_cn})


@router.get("/annotations/missing", summary="缺失中文注释清单（表 + 字段）")
def missing_annotations(
    system_code: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=200),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    missing_tables = select(AssetTable).where(
        (AssetTable.table_name_cn.is_(None)) | (AssetTable.table_name_cn == "")
    )
    if system_code:
        missing_tables = missing_tables.where(AssetTable.system_code == system_code)
    tb_total = db.scalar(select(func.count()).select_from(missing_tables.subquery())) or 0

    missing_cols = select(AssetColumn).where(
        (AssetColumn.column_name_cn.is_(None)) | (AssetColumn.column_name_cn == "")
    )
    if system_code:
        missing_cols = missing_cols.where(AssetColumn.system_code == system_code)
    col_total = db.scalar(select(func.count()).select_from(missing_cols.subquery())) or 0

    tables_sample = db.scalars(
        missing_tables.order_by(AssetTable.table_name).limit(page_size).offset((page - 1) * page_size)
    ).all()
    cols_sample = db.scalars(
        missing_cols.order_by(AssetColumn.table_name, AssetColumn.column_name).limit(page_size).offset((page - 1) * page_size)
    ).all()

    return ApiResponse(data={
        "tables_missing": tb_total,
        "columns_missing": col_total,
        "tables": [
            {"id": t.id, "full_name": f"{t.namespace_name or t.schema_name}.{t.table_name}", "system_code": t.system_code}
            for t in tables_sample
        ],
        "columns": [
            {"id": c.id, "full_name": f"{c.namespace_name or c.schema_name}.{c.table_name}.{c.column_name}", "system_code": c.system_code}
            for c in cols_sample
        ],
        "page": page,
        "page_size": page_size,
    })


@router.post("/ai/suggest-annotations", summary="AI 生成注释草稿（占位，待 P5.5 多数据库驱动就绪）")
def suggest_annotations(
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    return ApiResponse(data={
        "message": "AI 注释建议功能待 P10 AI SQL 增强阶段实现，当前占位",
        "suggestions": [],
    })
