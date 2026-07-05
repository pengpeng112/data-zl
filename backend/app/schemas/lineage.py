from datetime import datetime

from pydantic import BaseModel


class ViewDependencyItem(BaseModel):
    id: int
    view_name: str
    referenced_schema: str | None
    referenced_table: str
    alias: str | None
    source_file: str | None

    model_config = {"from_attributes": True}


class ImpactResult(BaseModel):
    table: str
    referencing_views: list[str]
    dependent_relations: list[str]
    total_views: int
    total_relations: int
