from datetime import datetime

from pydantic import BaseModel, Field


class CandidateRelationItem(BaseModel):
    id: int
    from_table: str | None
    from_columns: str | None
    to_table: str | None
    to_columns: str | None
    join_condition: str | None
    source_view: str | None
    source_file: str | None
    confidence: str | None
    status: str | None
    domain: str | None
    reviewed_by: str | None
    reviewed_at: datetime | None
    note: str | None
    created_at: datetime | None

    model_config = {"from_attributes": True}


class CandidatePromoteRequest(BaseModel):
    reviewer: str | None = None
    note: str | None = None
    domain: str | None = None
    cardinality: str | None = Field(None, description="e.g. one-to-many, many-to-one")


class CandidateRejectRequest(BaseModel):
    reviewer: str | None = None
    note: str | None = None
