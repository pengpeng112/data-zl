from datetime import datetime

from pydantic import BaseModel, Field


class QualityRuleItem(BaseModel):
    id: int
    rule_code: str
    rule_name: str | None = None
    rule_type: str | None
    rule_category: str | None = None
    target_type: str | None
    execution_mode: str | None
    check_scope: str | None = None
    constraint_level: str | None = None
    business_domain: str | None = None
    target_table: str | None = None
    target_field: str | None = None
    check_sql: str | None = None
    error_level: str | None = None
    description: str | None
    threshold_config: dict | None
    sample_limit: int | None = None
    enabled: bool | None

    model_config = {"from_attributes": True}


class QualityFindingItem(BaseModel):
    id: int
    rule_code: str | None
    target_type: str | None
    target_ref: str | None
    system_code: str | None = None
    source_code: str | None = None
    table_name: str | None = None
    column_name: str | None = None
    severity: str | None
    status: str | None
    rectification_status: str | None = None
    metric_value: str | None
    total_cnt: int | None = None
    error_cnt: int | None = None
    error_rate: int | None = None
    detail: dict | None
    sample_data: dict | None = None
    assigned_to: str | None = None
    confirmed_by: str | None = None
    found_at: datetime | None
    resolved_at: datetime | None
    resolved_by: str | None
    note: str | None

    model_config = {"from_attributes": True}


class QualityCheckRunItem(BaseModel):
    id: int
    started_at: datetime | None
    finished_at: datetime | None
    triggered_by: str | None
    total_rules: int | None
    total_findings: int | None
    total_records: int | None = None
    error_records: int | None = None
    pass_rate: int | None = None
    failed_reason: str | None = None
    status: str | None

    model_config = {"from_attributes": True}


class QualitySummary(BaseModel):
    total_findings: int
    open_count: int
    acknowledged_count: int
    resolved_count: int
    critical_count: int
    major_count: int
    minor_count: int
    info_count: int
    top_tables: list[dict]


class FindingUpdateRequest(BaseModel):
    status: str | None = Field(None, description="open/acknowledged/resolved/ignored")
    rectification_status: str | None = Field(None, description="open/assigned/confirmed/fixed/rechecked/ignored")
    resolved_by: str | None = None
    note: str | None = None
