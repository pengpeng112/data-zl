from sqlalchemy import BigInteger, Column, Integer, Text, TIMESTAMP, Boolean, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from ..core.db import Base


class AssetRole(Base):
    __tablename__ = "asset_roles"
    __table_args__ = {"schema": "asset"}

    id = Column(BigInteger, primary_key=True)
    role_code = Column(Text, unique=True, nullable=False)
    role_name_cn = Column(Text, nullable=False)
    role_type = Column(Text, server_default="platform")
    description = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class AssetUserRole(Base):
    __tablename__ = "asset_user_roles"
    __table_args__ = {"schema": "asset"}

    id = Column(BigInteger, primary_key=True)
    user_identifier = Column(Text, nullable=False)
    role_code = Column(Text, nullable=False)
    source = Column(Text, nullable=False, server_default="direct")
    request_id = Column(BigInteger)
    status = Column(Text, nullable=False, server_default="active")
    granted_by = Column(Text)
    granted_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    valid_from = Column(TIMESTAMP(timezone=True))
    expires_at = Column(TIMESTAMP(timezone=True))


class AssetRolePermission(Base):
    __tablename__ = "asset_role_permissions"
    __table_args__ = (
        UniqueConstraint("role_code", "resource", "action"),
        {"schema": "asset"},
    )

    id = Column(BigInteger, primary_key=True)
    role_code = Column(Text, nullable=False)
    resource = Column(Text, nullable=False)
    action = Column(Text, nullable=False)


class AssetPermissionResource(Base):
    __tablename__ = "asset_permission_resources"
    __table_args__ = {"schema": "asset"}

    id = Column(BigInteger, primary_key=True)
    resource_code = Column(Text, unique=True, nullable=False)
    resource_name_cn = Column(Text, nullable=False)
    module_code = Column(Text, nullable=False)
    action_code = Column(Text, nullable=False)
    description = Column(Text)
    enabled = Column(Boolean, nullable=False, server_default="true")
    sort_order = Column(Integer, nullable=False, server_default="0")
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class AssetUserDataScope(Base):
    __tablename__ = "asset_user_data_scopes"
    __table_args__ = {"schema": "asset"}

    id = Column(BigInteger, primary_key=True)
    user_identifier = Column(Text, nullable=False)
    scope_type = Column(Text, nullable=False)
    system_code = Column(Text)
    source_code = Column(Text)
    schema_name = Column(Text)
    domain = Column(Text)
    filter_json = Column(JSONB)
    status = Column(Text, nullable=False, server_default="active")
    valid_from = Column(TIMESTAMP(timezone=True))
    valid_to = Column(TIMESTAMP(timezone=True))
    request_id = Column(BigInteger)
    granted_by = Column(Text)
    revoked_by = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class GovernChangeRequest(Base):
    __tablename__ = "asset_govern_change_requests"
    __table_args__ = {"schema": "asset"}

    id = Column(BigInteger, primary_key=True)
    module = Column(Text, nullable=False)
    entity_type = Column(Text, nullable=False)
    entity_ref = Column(Text)
    request_type = Column(Text, nullable=False)
    request_payload = Column(JSONB)
    before_data = Column(JSONB)
    after_data = Column(JSONB)
    approval_status = Column(Text, server_default="draft")
    requested_by = Column(Text)
    approved_by = Column(Text)
    executed_by = Column(Text)
    execution_result = Column(Text)
    note = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class GovernAuditLog(Base):
    __tablename__ = "asset_govern_audit_logs"
    __table_args__ = {"schema": "asset"}

    id = Column(BigInteger, primary_key=True)
    module = Column(Text, nullable=False)
    entity_type = Column(Text, nullable=False)
    entity_ref = Column(Text, nullable=False)
    action = Column(Text, nullable=False)
    before_data = Column(JSONB)
    after_data = Column(JSONB)
    operator = Column(Text)
    reason = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class AssetActionExecutor(Base):
    __tablename__ = "asset_action_executors"
    __table_args__ = {"schema": "asset"}

    id = Column(BigInteger, primary_key=True)
    executor_code = Column(Text, unique=True, nullable=False)
    executor_name_cn = Column(Text, nullable=False)
    execution_mode = Column(Text, nullable=False)
    tool_code = Column(Text)
    sql_or_endpoint_ref = Column(Text)
    target_system_code = Column(Text)
    target_source_code = Column(Text)
    risk_level = Column(Text, server_default="medium")
    require_approval = Column(Boolean, server_default="true")
    require_second_confirm = Column(Boolean, server_default="false")
    enabled = Column(Boolean, server_default="false")
    description = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class GovernEnumValue(Base):
    __tablename__ = "asset_govern_enum_values"
    __table_args__ = (
        UniqueConstraint("enum_code", "value_code"),
        {"schema": "asset"},
    )

    id = Column(BigInteger, primary_key=True)
    enum_code = Column(Text, nullable=False)
    value_code = Column(Text, nullable=False)
    value_name_cn = Column(Text, nullable=False)
    sort_order = Column(Integer, server_default="0")
    enabled = Column(Boolean, server_default="true")
    description = Column(Text)
