"""126 P4: data product catalog and controlled execution API."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ...core.db import get_db
from ...core.security import get_current_user, get_request_operator, require_permission, require_query_view_on_get
from ...models.data_product import AssetDataProduct
from ...schemas.common import ApiResponse
from ...services.data_product_service import (
    _ser,
    execute_product,
    publish_core_products,
    upsert_product,
)
from ...services.metric_result_import import import_all_result_csvs



router = APIRouter(
    prefix="/api/v1/data-products",
    tags=["data-products"],
    dependencies=[Depends(require_query_view_on_get)],
)


class ProductUpsert(BaseModel):
    product_code: str
    title: str
    product_type: str
    query_code: str | None = None
    metric_code: str | None = None
    pin_version: int | None = None
    source_code: str | None = None
    description: str | None = None
    parameter_schema: dict | None = None
    max_rows: int = 1000
    enabled: bool = True


class ProductExecuteRequest(BaseModel):
    parameters: dict | None = None
    source_code: str | None = None
    execute_sql: bool = False  # for metric products: run linked query


@router.get("", summary="数据产品目录")
def list_products(
    keyword: str | None = Query(None),
    product_type: str | None = Query(None),
    enabled: bool | None = Query(True),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    stmt = select(AssetDataProduct)
    if enabled is not None:
        stmt = stmt.where(AssetDataProduct.enabled.is_(enabled))
    if product_type:
        stmt = stmt.where(AssetDataProduct.product_type == product_type)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(
            or_(
                AssetDataProduct.product_code.ilike(like),
                AssetDataProduct.title.ilike(like),
            )
        )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(AssetDataProduct.product_code).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return ApiResponse(
        data={"total": total, "page": page, "page_size": page_size, "items": [_ser(r) for r in rows]}
    )


@router.get(
    "/ai/context",
    summary="AI 可读数据产品目录",
    dependencies=[Depends(require_permission("ai.context.read"))],
)
def ai_context(db: Session = Depends(get_db)) -> ApiResponse[list[dict]]:
    rows = db.scalars(
        select(AssetDataProduct).where(
            AssetDataProduct.enabled.is_(True),
            AssetDataProduct.ai_readable.is_(True),
        )
    ).all()
    return ApiResponse(
        data=[
            {
                "product_code": r.product_code,
                "title": r.title,
                "product_type": r.product_type,
                "query_code": r.query_code,
                "metric_code": r.metric_code,
                "parameter_schema": r.parameter_schema,
                "description": r.description,
            }
            for r in rows
        ]
    )


@router.get("/{product_code}", summary="产品详情")
def get_product(product_code: str, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    r = db.scalar(select(AssetDataProduct).where(AssetDataProduct.product_code == product_code))
    if not r:
        raise HTTPException(status_code=404, detail="产品不存在")
    return ApiResponse(data=_ser(r))


@router.post(
    "",
    summary="登记/更新数据产品",
    dependencies=[Depends(require_permission("query:create"))],
)
def create_product(req: ProductUpsert, request: Request, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    user = get_request_operator(request, default="system")
    try:
        data = upsert_product(db, created_by=user, **req.model_dump())
        db.commit()
        return ApiResponse(data=data)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/publish-core",
    summary="将已导入的 CORE 查询/指标发布为数据产品",
    dependencies=[Depends(require_permission("query:create"))],
)
def publish_core(request: Request, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    user = get_request_operator(request, default="system")
    data = publish_core_products(db, created_by=user)
    db.commit()
    return ApiResponse(data=data)


@router.post(
    "/{product_code}/execute",
    summary="执行已发布数据产品（禁止任意 SQL）",
    dependencies=[Depends(require_permission("query:run"))],
)
def exec_product(
    product_code: str,
    req: ProductExecuteRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    user = get_request_operator(request, default="system")
    try:
        data = execute_product(
            db,
            product_code=product_code,
            parameters=req.parameters,
            source_code=req.source_code,
            execute_sql=req.execute_sql,
            triggered_by=user,
        )
        db.commit()
        return ApiResponse(data=data)
    except LookupError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PermissionError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/import/metric-results",
    summary="从取数 CSV 导入历史月度指标结果（默认 dry-run）",
    dependencies=[Depends(require_permission("query:create"))],
)
def import_results(
    dry_run: bool = Query(True),
    request: Request = None,
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    # 161 P1-2（round-2 P3）：审计归因取真实操作人，缺省兜底 system。
    user = get_request_operator(request, default="system")
    data = import_all_result_csvs(db, dry_run=dry_run, created_by=user)
    return ApiResponse(data=data)
