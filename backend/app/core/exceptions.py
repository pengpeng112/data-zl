"""111 号 S6：异常与审计脱敏。

- 响应只返回请求关联 ID（request_id）、通用消息和错误码，绝不回显 str(exc)
  或任何可逆的内部细节（连接串/用户/密码/Token/患者信息/SQL 参数）。
- 未知错误详情仅保留服务端堆栈，客户端只见通用消息。
- request_id 在 middleware 生成并写入 request.state.request_id；若缺失
  （未走 middleware）则这里兜底生成，保证响应始终携带可关联字段。
"""
from __future__ import annotations

import logging
import uuid

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from ..schemas.common import ApiResponse


def _get_or_create_request_id(request: Request) -> str:
    existing = getattr(request.state, "request_id", "") or ""
    if existing:
        return existing
    rid = uuid.uuid4().hex
    request.state.request_id = rid
    return rid


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    rid = _get_or_create_request_id(request)
    errors: list[str] = []
    for err in exc.errors():
        loc = " -> ".join(str(x) for x in err["loc"])
        errors.append(f"{loc}: {err['msg']}")
    return JSONResponse(
        status_code=422,
        content=ApiResponse(code=422, message="参数校验失败", data=errors, request_id=rid).model_dump(),
    )


async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    # 111 S6：拒绝返回 str(exc)（含 SQL 语句/绑定参数，可能带敏感内容）。
    rid = _get_or_create_request_id(request)
    logger = logging.getLogger("request")
    logger.warning(
        "db_error request_id=%s %s %s",
        rid,
        request.method,
        request.url.path,
    )
    return JSONResponse(
        status_code=500,
        content=ApiResponse(code=500, message="数据库异常，请稍后重试", request_id=rid).model_dump(),
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    rid = _get_or_create_request_id(request)
    logger = logging.getLogger(__name__)
    # 未知错误只保留服务端堆栈；如需分类可 import .exceptions_mapper。
    logger.exception(
        "unhandled request_id=%s %s %s",
        rid,
        request.method,
        request.url.path,
    )
    return JSONResponse(
        status_code=500,
        content=ApiResponse(code=500, message="服务异常，请联系管理员", request_id=rid).model_dump(),
    )