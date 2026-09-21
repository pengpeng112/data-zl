"""193 B03：患者纵向高质量数据集核心模型（asset schema，asset_ds_ 前缀）。

覆盖 B02 契约的分类分级、用途授权、数据集版本状态机、批次、身份映射、
治理事实、质量断言与受控导出。合成闭环用；不含真实患者数据。
"""
from sqlalchemy import BigInteger, CheckConstraint, Column, Index, Integer, Text, TIMESTAMP, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from ..core.db import Base


class AssetDsClassification(Base):
    """B02 §1 多维标签；object_ref 指向 column/table/dataset_version/export。"""

    __tablename__ = "asset_ds_classifications"
    __table_args__ = (
        UniqueConstraint("object_type", "object_ref", "version", name="uq_ds_cls_object_version"),
        Index("ix_ds_cls_object", "object_type", "object_ref", "status"),
        CheckConstraint(
            "protection_level in ('P1','P2','P3','P4')", name="ck_ds_cls_level"),
        {"schema": "asset"},
    )

    id = Column(BigInteger, primary_key=True)
    object_type = Column(Text, nullable=False)  # column|table|dataset_version|export
    object_ref = Column(Text, nullable=False)   # 稳定对象键（如 dataset:code:ver）
    # labels JSONB 键契约见 B02 §1：business_categories/data_form/personal_info/
    # protection_level 快照/legal_status/processing_state/usage_constraints
    labels = Column(JSONB, nullable=False, server_default="{}")
    protection_level = Column(Text, nullable=False, server_default="P4")
    status = Column(Text, nullable=False, server_default="active")  # active|superseded|retired
    version = Column(Integer, nullable=False, server_default="1")
    prev_version = Column(Integer)
    classified_by = Column(Text)                # 标注主体（人工/服务）
    legal_basis_ref = Column(Text)              # 法定识别依据引用（仅人工审批写入）
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class AssetDsGrant(Base):
    """B02 §4 用途授权：撤销即时生效（grant_version 递增使缓存失效）。"""

    __tablename__ = "asset_ds_grants"
    __table_args__ = (
        UniqueConstraint("principal", "purpose_code", "resource_type", "resource_ref",
                         name="uq_ds_grant_scope"),
        {"schema": "asset"},
    )

    id = Column(BigInteger, primary_key=True)
    principal = Column(Text, nullable=False)          # 用户标识或项目代号
    purpose_code = Column(Text, nullable=False)       # 用途码（B01 §7 用途清单）
    resource_type = Column(Text, nullable=False)      # dataset_version|dataset|global
    resource_ref = Column(Text, nullable=False)       # dataset:code 或 dataset:code:ver 或 *
    row_scope = Column(JSONB, server_default="{}")    # 行范围（队列/科室等）
    column_scope = Column(JSONB, server_default="{}")  # 列白名单（空=按等级默认）
    operations = Column(JSONB, nullable=False)        # ["read","export","train","derive"]
    legal_basis_ref = Column(Text, nullable=False)    # 法律/授权依据引用
    valid_from = Column(TIMESTAMP(timezone=True), server_default=func.now())
    valid_until = Column(TIMESTAMP(timezone=True))
    status = Column(Text, nullable=False, server_default="active")  # active|revoked|expired
    revoked_at = Column(TIMESTAMP(timezone=True))
    revoke_reason = Column(Text)
    grant_version = Column(Integer, nullable=False, server_default="1")
    approved_by = Column(Text, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class AssetDsDataset(Base):
    __tablename__ = "asset_ds_datasets"
    __table_args__ = (
        UniqueConstraint("dataset_code", name="uq_ds_dataset_code"),
        {"schema": "asset"},
    )

    id = Column(BigInteger, primary_key=True)
    dataset_code = Column(Text, nullable=False)
    title = Column(Text, nullable=False)
    description = Column(Text)
    purpose_code = Column(Text, nullable=False)
    # 队列条件（B01 队列契约的机器可读表达）与粒度
    queue_definition = Column(JSONB, server_default="{}")
    grain = Column(Text, nullable=False, default="patient")  # patient|visit|event
    latest_version_id = Column(BigInteger)
    created_by = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class AssetDsDatasetVersion(Base):
    """版本状态机：draft→validated→approved→published→deprecated/revoked。

    迁移只建表；状态迁移合法性在 B10 服务层强制（枚举+迁移表）。
    """

    __tablename__ = "asset_ds_dataset_versions"
    __table_args__ = (
        UniqueConstraint("dataset_id", "version", name="uq_ds_version"),
        CheckConstraint(
            "status in ('draft','validated','approved','published','deprecated','revoked')",
            name="ck_ds_version_status"),
        {"schema": "asset"},
    )

    id = Column(BigInteger, primary_key=True)
    dataset_id = Column(BigInteger, nullable=False)
    version = Column(Integer, nullable=False)
    schema_version = Column(Text, nullable=False, default="v1")
    status = Column(Text, nullable=False, server_default="draft")
    source_batch_ids = Column(JSONB, server_default="[]")   # 依赖批次
    identity_version = Column(Integer)                       # 身份映射版本
    rule_versions = Column(JSONB, server_default="{}")       # 规则版本引用
    cutoff_at = Column(TIMESTAMP(timezone=True))             # 截止时刻（B01 三时间戳）
    manifest = Column(JSONB)                                 # 发布清单（行数/校验/来源）
    manifest_sha256 = Column(Text)
    quality_conclusion = Column(JSONB)                       # B09 质量结论
    security_conclusion = Column(JSONB)                      # B04 安全结论
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    validated_at = Column(TIMESTAMP(timezone=True))
    approved_by = Column(Text)
    approved_at = Column(TIMESTAMP(timezone=True))
    published_at = Column(TIMESTAMP(timezone=True))
    deprecated_at = Column(TIMESTAMP(timezone=True))
    revoked_at = Column(TIMESTAMP(timezone=True))


class AssetDsBatch(Base):
    """B07 抽取批次：分片、水位、检查点与计数（提交边界与检查点一致）。"""

    __tablename__ = "asset_ds_batches"
    __table_args__ = (
        UniqueConstraint("run_id", name="uq_ds_batch_run"),
        {"schema": "asset"},
    )

    id = Column(BigInteger, primary_key=True)
    run_id = Column(Text, nullable=False)
    source_code = Column(Text, nullable=False)
    object_name = Column(Text, nullable=False)              # 源对象（schema.table）
    shard_window = Column(JSONB, server_default="{}")       # 分片范围（键区间/时间窗）
    watermark = Column(JSONB)                               # 抽取水位
    snapshot_capable = Column(Text, server_default="false") # 源是否时点快照
    status = Column(Text, nullable=False, server_default="running")
    # running|succeeded|failed|cancelled|checkpointed
    counters = Column(JSONB, server_default="{}")           # input/written/quarantined/deleted
    checkpoints = Column(JSONB, server_default="{}")        # 已提交分片检查点
    error_class = Column(Text)                              # 连接|schema_drift|数据|超时|取消
    error_detail = Column(Text)
    started_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    finished_at = Column(TIMESTAMP(timezone=True))


class AssetDsIdentityMap(Base):
    """B06 身份映射：内部患者 ID ↔ 来源键；合并/拆分历史保留。"""

    __tablename__ = "asset_ds_identity_maps"
    __table_args__ = (
        UniqueConstraint("internal_patient_id", "source_code", "source_key",
                         name="uq_ds_identity_map"),
        Index("ix_ds_identity_internal", "internal_patient_id"),
        {"schema": "asset"},
    )

    id = Column(BigInteger, primary_key=True)
    internal_patient_id = Column(Text, nullable=False)      # 内部 ID（如 DS-P000001）
    source_code = Column(Text, nullable=False)
    source_key = Column(Text, nullable=False)               # 来源患者键
    match_rule_version = Column(Text, nullable=False)
    match_evidence = Column(JSONB)                          # 匹配证据引用
    confidence = Column(Text, nullable=False, default="deterministic")
    # deterministic|probable|manual
    review_status = Column(Text, nullable=False, server_default="auto")
    # auto|pending_review|confirmed|rejected
    valid_from = Column(TIMESTAMP(timezone=True), server_default=func.now())
    valid_until = Column(TIMESTAMP(timezone=True))
    merged_into = Column(Text)                              # 错误合并撤销→拆分指向
    split_from = Column(Text)                               # 拆分来源内部 ID
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class AssetDsFact(Base):
    """B08 治理事实：原值引用与标准值并存，规则版本绑定。"""

    __tablename__ = "asset_ds_facts"
    __table_args__ = (
        UniqueConstraint("fact_key", "rule_version", name="uq_ds_fact_rule"),
        Index("ix_ds_fact_patient", "internal_patient_id"),
        {"schema": "asset"},
    )

    id = Column(BigInteger, primary_key=True)
    fact_key = Column(Text, nullable=False)                 # 来源记录无歧义编码
    fact_kind = Column(Text, nullable=False)                # diagnosis|lab|visit|medication|...
    internal_patient_id = Column(Text, nullable=False)
    internal_visit_id = Column(Text)
    source_code = Column(Text, nullable=False)
    original_value_ref = Column(Text, nullable=False)       # 原值引用（不含原值本体进平台）
    standard_value = Column(Text)
    standard_code_system = Column(Text)                     # ICD10|LOINC|...
    unit = Column(Text)
    rule_version = Column(Text, nullable=False)
    quality_flag = Column(Text, server_default="ok")        # ok|unknown_code|unit_mismatch|quarantined
    business_time = Column(TIMESTAMP(timezone=True))        # 业务时间
    available_time = Column(TIMESTAMP(timezone=True))       # 结果可用时间
    ingested_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    batch_run_id = Column(Text)
    deleted = Column(Text, server_default="false")          # 迟到删除标记


class AssetDsQualityAssertion(Base):
    """B09 质量断言：八类维度，分母/阈值/结果。"""

    __tablename__ = "asset_ds_quality_assertions"
    __table_args__ = (
        UniqueConstraint("scope_type", "scope_ref", "dimension", name="uq_ds_qa_scope_dim"),
        {"schema": "asset"},
    )

    id = Column(BigInteger, primary_key=True)
    scope_type = Column(Text, nullable=False)   # dataset_version|batch
    scope_ref = Column(Text, nullable=False)
    dimension = Column(Text, nullable=False)    # coverage|identity|linkage|semantic|timing|
    #                                          # freshness|traceability|fitness
    metric_name = Column(Text, nullable=False)
    numerator = Column(BigInteger)
    denominator = Column(BigInteger)
    threshold = Column(JSONB)                   # {op, value, tolerance}
    result = Column(Text, server_default="pending")  # pass|fail|pending|blocked
    detail = Column(JSONB)
    evaluated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class AssetDsExport(Base):
    """B14 受控导出：字段白名单、有效期、下载计数与审计引用。"""

    __tablename__ = "asset_ds_exports"
    __table_args__ = (
        UniqueConstraint("export_code", name="uq_ds_export_code"),
        {"schema": "asset"},
    )

    id = Column(BigInteger, primary_key=True)
    export_code = Column(Text, nullable=False)
    grant_id = Column(BigInteger, nullable=False)
    dataset_version_id = Column(BigInteger, nullable=False)
    field_whitelist = Column(JSONB, nullable=False)
    status = Column(Text, nullable=False, server_default="requested")
    # requested|approved|generated|expired|revoked|downloaded
    expires_at = Column(TIMESTAMP(timezone=True))
    download_count = Column(Integer, server_default="0")
    row_count = Column(BigInteger)
    file_sha256 = Column(Text)
    masking_applied = Column(JSONB)             # 文本脱敏规则记录
    audit_ref = Column(Text)
    created_by = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
