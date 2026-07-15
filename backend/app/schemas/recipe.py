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
    joins: list[Any] = Field(default_factory=list)
    recipe_json: dict[str, Any] | None = None


class RecipeDraftUpdate(BaseModel):
    recipe_name: str | None = None
    description: str | None = None
    domain: str | None = None
    business_domain: str | None = None
    primary_tables: list[Any] | None = None
    joins: list[Any] | None = None
    recipe_json: dict[str, Any] | None = None


class RecipeReview(BaseModel):
    reason: str | None = None


class RecipeSqlGenerateRequest(BaseModel):
    dialect: str = Field(default="oracle", pattern="^(oracle|postgresql)$")
