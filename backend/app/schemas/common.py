from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    code: int = Field(default=0, description="0=成功，非0=错误码")
    message: str = Field(default="success", description="提示信息")
    data: T | None = Field(default=None, description="响应数据")


class PageData(BaseModel, Generic[T]):
    total: int = Field(description="总记录数")
    page: int = Field(default=1, description="当前页码")
    page_size: int = Field(default=20, description="每页条数")
    items: list[T] = Field(default_factory=list, description="当前页数据")
