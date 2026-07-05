from pydantic import BaseModel


class GraphNode(BaseModel):
    id: str
    label: str
    schema_name: str | None = None
    table_name: str | None = None
    domain: str | None = None
    column_count: int | None = None
    source: str | None = None
    category: str | None = None


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    label: str | None = None
    relation_type: str | None = "formal"
    rel_id: int | None = None
    join_condition: str | None = None
    from_columns: str | None = None
    to_columns: str | None = None
    cardinality: str | None = None
    confidence: str | None = None
    validation_level: str | None = None
    validation_status: str | None = None
    validation_metrics: str | None = None
    note: str | None = None
    validation_note: str | None = None


class GraphData(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class GraphOptions(BaseModel):
    schemas: list[str]
    domains: list[str]
    validation_statuses: list[str]
    confidences: list[str]
    relation_types: list[str]
