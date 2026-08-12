from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class QueryIngestRequest(BaseModel):
    query_code: str = Field(..., min_length=1, max_length=128)
    title: str = Field(..., min_length=1, max_length=256)
    sql_text: str = Field(..., min_length=1)
    purpose: str | None = None
    system_code: str | None = None
    source_code: str | None = None
    dialect: str = "oracle"
    business_domain: str | None = None
    grain: str | None = None
    period_field: str | None = None
    parameter_schema: dict | list | None = None
    limitations: list | None = None
    recipe_refs: list | None = None
    metric_refs: list | None = None
    source_path: str | None = None
    ai_source: dict | None = None
    session_key: str | None = None
    revision_reason: str | None = None
    force_new_version: bool = False


class QueryReviseRequest(BaseModel):
    sql_text: str = Field(..., min_length=1)
    revision_reason: str = Field(..., min_length=1)
    title: str | None = None
    purpose: str | None = None
    system_code: str | None = None
    source_code: str | None = None
    dialect: str | None = None
    session_key: str | None = None


class QueryRunRequest(BaseModel):
    query_version_id: int | None = None
    query_code: str | None = None
    version: int | None = None
    source_code: str | None = None
    parameters: dict[str, Any] | None = None
    result_storage: str = Field(default="none", pattern="^(none|summary|file_ref)$")
    max_rows: int = Field(default=1000, ge=1, le=5000)
    sample_limit: int = Field(default=20, ge=0, le=100)
    session_key: str | None = None


class QueryGateRequest(BaseModel):
    sql_text: str
    dialect: str = "oracle"
    system_code: str | None = None
    source_code: str | None = None
