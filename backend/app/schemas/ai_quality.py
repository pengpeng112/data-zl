from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, ConfigDict


class AiQualityPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task_type: Literal["finding", "finding_batch", "run_summary"]
    finding_ids: list[int] = Field(default_factory=list, max_length=50)
    run_id: int | None = None


class AiQualityCreateRequest(AiQualityPreviewRequest):
    request_id: str = Field(pattern=r"^AQJ-[a-f0-9]{24}-[a-f0-9]{32}$")
    input_digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")


class AiQualityReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["accepted", "rejected", "partial"]
    note: str | None = Field(default=None, max_length=2000)
    accepted_recommendations: list[int] | None = Field(default=None, max_length=100)


class AiQualityAttachRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    recommendation_indexes: list[int] = Field(default_factory=list, max_length=100)
    note: str | None = Field(default=None, max_length=2000)


class AiQualityJobItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    job_key: str
    task_type: str
    status: str
    input_digest: str
    request_id: str
    prompt_version: str
    attempt: int
    created_at: datetime | None = None
    finished_at: datetime | None = None
    dify_run_id: str | None = None
    duration_ms: int | None = None
    token_usage: dict[str, Any] | None = None
    error_class: str | None = None


class AiQualityResultItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    job_id: int
    risk_level: str
    summary: str
    structured_result: dict[str, Any]
    output_digest: str
    review_status: str
    attached_by: str | None = None
    attached_at: datetime | None = None
