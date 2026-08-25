"""149 P1a: 字段值域知识库三表模型。

主表一字段一码一现行语义；证据一对多承载多来源（live_probe/cross_system/
dict_table/manual/ai_probe）；版本表是串行采纳时间线，不是并行假说集——
并行候选通过主表多 pending + conflict_status=conflicted 表达。

conflicted 记录在人工裁决（resolve-conflict）前不进入 AI 注入链路。
"""

from sqlalchemy import BigInteger, Column, Integer, Text, TIMESTAMP, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from ..core.db import Base


class AssetColumnValueDomain(Base):
    __tablename__ = "asset_column_value_domains"
    __table_args__ = (
        UniqueConstraint(
            "system_code",
            "source_code",
            "schema_name",
            "table_name",
            "column_name",
            "code",
            name="uq_asset_column_value_domains_key",
        ),
        {"schema": "asset"},
    )

    id = Column(BigInteger, primary_key=True)
    # 定位键与 asset_tables/asset_columns 对齐；HIS 源端与 ODS 镜像按物理来源各建一条
    system_code = Column(Text, nullable=False)
    source_code = Column(Text, nullable=False)
    schema_name = Column(Text, nullable=False)
    table_name = Column(Text, nullable=False)
    column_name = Column(Text, nullable=False)
    # 值（枚举码/阈值表达式/字面量/陷阱标识）
    code = Column(Text, nullable=False)
    meaning = Column(Text, nullable=False)
    note = Column(Text)
    # enum / threshold / literal / trap（trap=负知识：勿用 XX 字典等）
    domain_kind = Column(Text, nullable=False, server_default="enum")
    # 条件型口径（如"仅住院子集""OPER_STATUS>=35 场景"）
    scope_condition = Column(Text)
    # pending / confirmed / deprecated
    status = Column(Text, nullable=False, server_default="pending")
    # none / conflicted（同字段同 code 互斥候选或对立证据时置位）
    conflict_status = Column(Text, nullable=False, server_default="none")
    confirmed_by = Column(Text)
    confirmed_at = Column(TIMESTAMP(timezone=True))
    current_version_id = Column(BigInteger)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class AssetColumnValueDomainEvidence(Base):
    __tablename__ = "asset_column_value_domain_evidences"
    __table_args__ = {"schema": "asset"}

    id = Column(BigInteger, primary_key=True)
    domain_id = Column(BigInteger, nullable=False, index=True)
    # live_probe / cross_system / dict_table / manual / ai_probe
    source_type = Column(Text, nullable=False)
    source_system = Column(Text)
    # 该来源观测到的含义；与主表 meaning 不一致时触发冲突检测（149 §2.4）
    observed_meaning = Column(Text)
    method = Column(Text)
    sample_count = Column(Integer)
    observed_at = Column(TIMESTAMP(timezone=True))
    actor = Column(Text)
    # 证据原文引用（如 148 文档小节号）
    snippet_ref = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class AssetColumnValueDomainVersion(Base):
    __tablename__ = "asset_column_value_domain_versions"
    __table_args__ = (
        UniqueConstraint("domain_id", "version_no", name="uq_asset_value_domain_versions"),
        {"schema": "asset"},
    )

    id = Column(BigInteger, primary_key=True)
    domain_id = Column(BigInteger, nullable=False, index=True)
    version_no = Column(Integer, nullable=False)
    # 快照：code/meaning/note/status/conflict_status/domain_kind/scope_condition
    snapshot = Column(JSONB, nullable=False)
    change_reason = Column(Text)
    evidence_ref = Column(Text)
    actor = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
