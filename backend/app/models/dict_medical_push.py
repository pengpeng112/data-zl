"""临床诊断映射导入暂存、推送计划和执行记录模型（101号）。

新增四张表：
- asset_dict_medical_import_rows: OCR/Excel 暂存行
- asset_dict_medical_push_plans: 服务端不可篡改推送计划
- asset_dict_medical_push_actions: 结构化业务动作（不接受客户端 SQL）
- asset_dict_medical_push_runs: 分系统事务包执行记录
"""
from sqlalchemy import BigInteger, Column, Integer, Text, TIMESTAMP, Boolean, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from ..core.db import Base


class DictMedicalImportRow(Base):
    """Excel/OCR 导入暂存行（101号 §4.1）。"""
    __tablename__ = "asset_dict_medical_import_rows"
    __table_args__ = (
        UniqueConstraint("import_run_id", "source_row_no"),
        {"schema": "asset"},
    )

    id = Column(BigInteger, primary_key=True)
    import_run_id = Column(BigInteger, nullable=False)
    source_file_name = Column(Text)
    source_file_sha256 = Column(Text)
    source_sheet = Column(Text)
    source_row_no = Column(Integer, nullable=False)
    row_hash = Column(Text)

    # 七个原始 Excel 字段
    raw_dict_attribute = Column(Text)
    raw_hospital_code = Column(Text)
    raw_hospital_name = Column(Text)
    raw_national_clinical_code = Column(Text)
    raw_national_clinical_name = Column(Text)
    raw_insurance_code = Column(Text)
    raw_insurance_name = Column(Text)

    # 七个规范化字段
    norm_dict_attribute = Column(Text)
    norm_hospital_code = Column(Text)
    norm_hospital_name = Column(Text)
    norm_national_clinical_code = Column(Text)
    norm_national_clinical_name = Column(Text)
    norm_insurance_code = Column(Text)
    norm_insurance_name = Column(Text)

    # 校验与审核
    insurance_mapping_status = Column(Text, server_default="valid")
    validation_status = Column(Text, server_default="valid")
    validation_errors = Column(JSONB)
    diff_type = Column(Text, server_default="new")
    review_status = Column(Text, server_default="pending")
    reviewer = Column(Text)
    reviewed_at = Column(TIMESTAMP(timezone=True))
    review_note = Column(Text)
    merged_at = Column(TIMESTAMP(timezone=True))
    merged_by = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class DictMedicalPushPlan(Base):
    """服务端不可篡改推送计划（101号 §4.3）。"""
    __tablename__ = "asset_dict_medical_push_plans"
    __table_args__ = {"schema": "asset"}

    id = Column(BigInteger, primary_key=True)
    plan_code = Column(Text, unique=True, nullable=False)
    category_code = Column(Text, nullable=False)
    target_systems = Column(JSONB, nullable=False)
    status = Column(Text, server_default="draft")
    platform_data_version = Column(Text)
    content_hash = Column(Text)
    expires_at = Column(TIMESTAMP(timezone=True))
    item_count = Column(Integer, server_default="0")
    created_by = Column(Text)
    approved_by = Column(Text)
    approved_at = Column(TIMESTAMP(timezone=True))
    approval_note = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class DictMedicalPushAction(Base):
    """结构化业务动作（101号 §4.3）。不接受客户端 SQL。"""
    __tablename__ = "asset_dict_medical_push_actions"
    __table_args__ = (
        UniqueConstraint("plan_id", "target_system", "item_code", "action_type"),
        {"schema": "asset"},
    )

    id = Column(BigInteger, primary_key=True)
    plan_id = Column(BigInteger, nullable=False)
    target_system = Column(Text, nullable=False)
    target_source_code = Column(Text)
    item_code = Column(Text, nullable=False)
    item_name_cn = Column(Text)
    action_type = Column(Text, nullable=False)
    payload = Column(JSONB)
    status = Column(Text, server_default="planned")
    diff_type = Column(Text)
    conflict_detail = Column(JSONB)
    run_id = Column(BigInteger)
    error_masked = Column(Text)
    executed_at = Column(TIMESTAMP(timezone=True))
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class DictMedicalPushRun(Base):
    """分系统事务包执行记录（101号 §4.5）。"""
    __tablename__ = "asset_dict_medical_push_runs"
    __table_args__ = {"schema": "asset"}

    id = Column(BigInteger, primary_key=True)
    plan_id = Column(BigInteger, nullable=False)
    target_system = Column(Text, nullable=False)
    target_source_code = Column(Text)
    status = Column(Text, server_default="pending")
    total_actions = Column(Integer, server_default="0")
    succeeded_count = Column(Integer, server_default="0")
    failed_count = Column(Integer, server_default="0")
    skipped_count = Column(Integer, server_default="0")
    reconcile_result = Column(JSONB)
    error_masked = Column(Text)
    started_at = Column(TIMESTAMP(timezone=True))
    finished_at = Column(TIMESTAMP(timezone=True))
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())