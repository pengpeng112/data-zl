from pydantic import BaseModel, ConfigDict


class TableBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    schema_name: str | None = None
    table_name: str | None = None
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
    column_id: int | None = None
    column_name: str | None = None
    data_type: str | None = None
    length: int | None = None
    nullable: str | None = None
    comment: str | None = None


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


class SummaryOut(BaseModel):
    tables: int
    columns: int
    relations: int
    domains: int
