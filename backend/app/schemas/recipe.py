from typing import Any

from pydantic import BaseModel, Field


class RecipeCreate(BaseModel):
    recipe_id: str = Field(..., min_length=1, max_length=200)
    recipe_name: str | None = None
    domain: str | None = None
    source_system: str | None = None
    business_domain: str | None = None
    description: str | None = None
    primary_tables: list[Any] = Field(default_factory=list)
    # 198 T11：joins 允许知识型 dict 形态入库（readiness 显式标记 not_executable），
    # 但 submit/activate/生成端会被结构校验拒绝，直到重建为标准数组。
    joins: list[Any] | dict[str, Any] = Field(default_factory=list)
    recipe_json: dict[str, Any] | None = None


class RecipeDraftUpdate(BaseModel):
    recipe_name: str | None = None
    description: str | None = None
    domain: str | None = None
    business_domain: str | None = None
    primary_tables: list[Any] | None = None
    joins: list[Any] | dict[str, Any] | None = None
    recipe_json: dict[str, Any] | None = None


class RecipeReview(BaseModel):
    reason: str | None = None


class RecipeSqlGenerateRequest(BaseModel):
    dialect: str = Field(default="oracle", pattern="^(oracle|postgresql)$")
