from pydantic import BaseModel, Field


class GraphNode(BaseModel):
    id: str
    label: str
    system_code: str | None = None
    source_code: str | None = None
    namespace_name: str | None = None
    schema_name: str | None = None
    table_name: str | None = None
    table_name_cn: str | None = None
    table_role: str | None = None
    domain: str | None = None
    business_domain: str | None = None
    column_count: int | None = None
    source: str | None = None
    category: str | None = None
    row_count_stats: str | None = None
    grain: str | None = None
    pk: str | None = None
    confidence: str | None = None
    include_status: str | None = None
    review_status: str | None = None
    note: str | None = None

class GraphFieldMapping(BaseModel):
    from_column: str | None = None
    from_column_name_cn: str | None = None
    to_column: str | None = None
    to_column_name_cn: str | None = None


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    from_system_code: str | None = None
    from_source_code: str | None = None
    from_schema_name: str | None = None
    from_table_name: str | None = None
    from_table_name_cn: str | None = None
    from_table_role: str | None = None
    from_include_status: str | None = None
    to_system_code: str | None = None
    to_source_code: str | None = None
    to_schema_name: str | None = None
    to_table_name: str | None = None
    to_table_name_cn: str | None = None
    to_table_role: str | None = None
    to_include_status: str | None = None
    label: str | None = None
    relation_type: str | None = "formal"
    rel_id: int | None = None
    join_condition: str | None = None
    from_columns: str | None = None
    to_columns: str | None = None
    field_mappings: list[GraphFieldMapping] = Field(default_factory=list)
    cardinality: str | None = None
    business_domain: str | None = None
    confidence: str | None = None
    validation_level: str | None = None
    validation_status: str | None = None
    validation_metrics: str | None = None
    is_deferred: bool = False
    deferred_reason: str | None = None
    note: str | None = None
    validation_note: str | None = None


class GraphData(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class GraphViewMode(BaseModel):
    code: str
    label: str
    description: str | None = None
    group_by: str
    layout_mode: str
    confidence: str | None = None
    validation_status: str | None = None
    include_candidates: bool = False
    include_dependencies: bool = False
    show_review_layer: bool = False
    requires_table: bool = False


class GraphOptions(BaseModel):
    systems: list[str]
    sources: list[str]
    schemas: list[str]
    domains: list[str]
    validation_statuses: list[str]
    confidences: list[str]
    relation_types: list[str]
    view_modes: list[GraphViewMode]
