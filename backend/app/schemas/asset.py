from datetime import datetime
from pydantic import BaseModel, ConfigDict


class TableBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int | None = None
    system_code: str | None = None
    source_code: str | None = None
    namespace_name: str | None = None
    schema_name: str | None = None
    table_name: str | None = None
    table_name_cn: str | None = None
    name_cn_source: str | None = None
    name_cn_status: str | None = None
    table_role: str | None = None
    comment: str | None = None
    column_count: int | None = None
    domain: str | None = None
    source: str | None = None


class TableDetail(TableBrief):
    row_count_stats: str | None = None
    grain: str | None = None
    pk: str | None = None
    confidence: str | None = None
    note: str | None = None


class ColumnOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int | None = None
    system_code: str | None = None
    source_code: str | None = None
    namespace_name: str | None = None
    schema_name: str | None = None
    table_name: str | None = None
    column_id: int | None = None
    column_name: str | None = None
    column_name_cn: str | None = None
    name_cn_source: str | None = None
    name_cn_status: str | None = None
    business_desc_cn: str | None = None
    value_desc_cn: str | None = None
    data_type: str | None = None
    length: int | None = None
    nullable: str | None = None
    comment: str | None = None
    semantic_type: str | None = None
    is_sensitive: bool | None = None


class RelationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    rel_id: int | None = None
    domain: str | None = None
    from_table: str | None = None
    from_columns: str | None = None
    to_table: str | None = None
    to_columns: str | None = None
    join_condition: str | None = None
    cardinality: str | None = None
    confidence: str | None = None
    validation_level: str | None = None
    validation_status: str | None = None
    validation_metrics: str | None = None
    note: str | None = None
    validation_note: str | None = None
    # 98号 S0：端点物理身份、分层、业务键、时间戳
    from_system_code: str | None = None
    from_source_code: str | None = None
    from_namespace_name: str | None = None
    from_schema_name: str | None = None
    from_table_name: str | None = None
    to_system_code: str | None = None
    to_source_code: str | None = None
    to_namespace_name: str | None = None
    to_schema_name: str | None = None
    to_table_name: str | None = None
    relation_layer: str | None = None
    relation_business_key: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SummaryOut(BaseModel):
    tables: int
    columns: int
    relations: int
    domains: int
