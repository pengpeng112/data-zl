"""138 first-phase static lineage models (144 S5).

Business JOIN edges (asset_relations) NEVER enter this table — it models data
flow (derive/read/produce), not how tables join (A19).
"""
from sqlalchemy import BigInteger, Column, Index, Text, TIMESTAMP, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from ..core.db import Base


class AssetViewDependency(Base):
    __tablename__ = "asset_view_dependencies"
    __table_args__ = {"schema": "asset"}

    id = Column(BigInteger, primary_key=True)
    view_name = Column(Text, nullable=False)
    referenced_schema = Column(Text)
    referenced_table = Column(Text, nullable=False)
    alias = Column(Text)
    source_file = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class AssetLineageEdge(Base):
    __tablename__ = "asset_lineage_edges"
    __table_args__ = (
        UniqueConstraint(
            "edge_key",
            name="uq_asset_lineage_edges_key",
        ),
        Index(
            "ix_asset_lineage_edges_from",
            "from_object_key",
        ),
        Index(
            "ix_asset_lineage_edges_to",
            "to_object_key",
        ),
        {"schema": "asset"},
    )

    id = Column(BigInteger, primary_key=True)
    edge_key = Column(Text, nullable=False)
    # physical identity per 138 §3.3: table → 6-part object_key; query →
    # query|code|version; metric → metric|code|version; product → product|code
    from_object_key = Column(Text, nullable=False)
    to_object_key = Column(Text, nullable=False)
    from_object_type = Column(Text, nullable=False)
    to_object_type = Column(Text, nullable=False)
    # syncs_to | reads_from | derives_to | produces | calculates | publishes | consumed_by
    edge_type = Column(Text, nullable=False)
    granularity = Column(Text, nullable=False, server_default="table")  # system|table|column
    process_key = Column(Text)
    transform_type = Column(Text)
    field_mapping = Column(JSONB)
    expression_hash = Column(Text)
    evidence_type = Column(Text)
    evidence_ref = Column(Text)
    evidence_hash = Column(Text)
    parser_version = Column(Text)
    confidence = Column(Text)
    review_status = Column(Text, server_default="auto")
    logic_version = Column(Text, nullable=False, server_default="1")
    valid_from = Column(TIMESTAMP(timezone=True))
    valid_to = Column(TIMESTAMP(timezone=True))
    observed_at = Column(TIMESTAMP(timezone=True))
    batch_id = Column(Text)
    status = Column(Text, nullable=False, server_default="active")  # active|stale|unresolved|rejected
    unresolved_reason = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
