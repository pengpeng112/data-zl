from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# 108 号契约加固：
# - GraphNode.id 使用完整物理键 system_code|source_code|namespace_name|schema_name|table_name；
# - display_id 仅用于界面展示（SCHEMA.TABLE），不再作为图节点唯一键；
# - extra="forbid"：graph.py 若发送 schema 未声明的字段，序列化即报错，禁止静默丢弃
#   physical_key / display_id / meta 等关键字段（P0-02）。
# - 数据库自增 id / rel_id 只作为边属性，不作为图边永久身份。


class GraphNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    label: str
    physical_key: str | None = None
    display_id: str | None = None
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
    object_type: str | None = None
    technical_name: str | None = None
    metadata_match: str | None = None
    asset_count: int | None = None
    child_count: int | None = None
    path: str | None = None
    is_aggregate: bool = False
    column_name: str | None = None
    column_name_cn: str | None = None
    data_type: str | None = None
    nullable: str | None = None
    is_primary_key: bool = False
    is_relation_key: bool = False


class GraphFieldMapping(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_column: str | None = None
    from_column_name_cn: str | None = None
    to_column: str | None = None
    to_column_name_cn: str | None = None


class GraphEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    source: str
    target: str
    display_source: str | None = None
    display_target: str | None = None
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
    relation_layer: str | None = None
    db_id: int | None = None
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


class GraphMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_relations: int = 0
    matched_relations: int = 0
    returned_relations: int = 0
    truncated: bool = False
    unresolved_endpoints: int = 0
    filters: dict[str, Any] = Field(default_factory=dict)
    data_version: str | None = None
    backend_build_id: str | None = None
    query_ms: float | None = None
    matched_total: int | None = None
    returned_nodes: int | None = None
    estimated_total: int | None = None
    enrichment: dict[str, int] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    center_physical_key: str | None = None
    direction_semantics: str | None = None


class GraphData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nodes: list[GraphNode]
    edges: list[GraphEdge]
    meta: GraphMeta | None = None


class GraphViewMode(BaseModel):
    model_config = ConfigDict(extra="forbid")

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
    deprecated: bool = False


class GraphOptionItem(BaseModel):
    """A filter value with the canonical human label and physical code."""

    model_config = ConfigDict(extra="forbid")

    value: str
    label: str
    count: int = 0
    disabled: bool = False


class GraphOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Legacy code arrays remain stable for API consumers; *_options carry the
    # canonical human label without changing filter values.
    systems: list[str]
    sources: list[str]
    schemas: list[str]
    domains: list[str]
    system_options: list[GraphOptionItem] = Field(default_factory=list)
    source_options: list[GraphOptionItem] = Field(default_factory=list)
    schema_options: list[GraphOptionItem] = Field(default_factory=list)
    domain_options: list[GraphOptionItem] = Field(default_factory=list)
    validation_statuses: list[str]
    confidences: list[str]
    relation_types: list[str]
    view_modes: list[GraphViewMode]
    default_mode: str | None = None
    backend_build_id: str | None = None


class GraphOverviewData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    level: str
    next_level: str | None = None
    selected_path: dict[str, str] = Field(default_factory=dict)
    data: GraphData


class GraphFilterOption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str
    label: str
    count: int = 0
    disabled: bool = False


class GraphFilterOptionsData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selected_path: dict[str, str] = Field(default_factory=dict)
    next_level: str
    items: list[GraphFilterOption] = Field(default_factory=list)
    business_domains: list[GraphFilterOption] = Field(default_factory=list)
    object_types: list[GraphFilterOption] = Field(default_factory=list)


class GraphTableSearchItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    physical_key: str
    display_name: str
    technical_name: str
    system_code: str | None = None
    source_code: str | None = None
    namespace_name: str | None = None
    schema_name: str | None = None
    table_name: str | None = None
    object_type: str = "table"
    business_domain: str | None = None
    column_count: int | None = None
    ambiguous: bool = False
