from __future__ import annotations

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from ..schemas.common import ApiResponse


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors: list[str] = []
    for err in exc.errors():
        loc = " -> ".join(str(x) for x in err["loc"])
        errors.append(f"{loc}: {err['msg']}")
    return JSONResponse(
        status_code=422,
        content=ApiResponse(code=422, message="参数校验失败", data=errors).model_dump(),
    )


async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content=ApiResponse(code=500, message="数据库异常，请稍后重试").model_dump(),
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    import logging
    logger = logging.getLogger(__name__)
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content=ApiResponse(code=500, message="服务异常，请联系管理员").model_dump(),
    )
