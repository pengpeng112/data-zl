from sqlalchemy import BigInteger, Column, Integer, Text, TIMESTAMP, Boolean, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from ..core.db import Base


class IdentityDepartment(Base):
    __tablename__ = "asset_identity_departments"
    __table_args__ = (
        UniqueConstraint("dept_code"),
        {"schema": "asset"},
    )

    id = Column(BigInteger, primary_key=True)
    dept_code = Column(Text, nullable=False)
    dept_name_cn = Column(Text, nullable=False)
    dept_type = Column(Text)
    parent_dept_code = Column(Text)
    source_system = Column(Text, server_default="HIS")
    source_table = Column(Text, server_default="dept_dict")
    source_dept_id = Column(Text)
    status = Column(Text, server_default="active")
    last_source_sync_at = Column(TIMESTAMP(timezone=True))
    review_status = Column(Text, server_default="unreviewed")
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class IdentityPerson(Base):
    __tablename__ = "asset_identity_persons"
    __table_args__ = (
        UniqueConstraint("person_code"),
        {"schema": "asset"},
    )

    id = Column(BigInteger, primary_key=True)
    person_code = Column(Text, nullable=False)
    person_name_cn = Column(Text)
    dept_code = Column(Text)
    dept_name_cn = Column(Text)
    job_title = Column(Text)
    person_type = Column(Text, server_default="formal")
    employment_status = Column(Text)
    primary_source_system = Column(Text)
    source_system = Column(Text)
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class IdentityPersonSource(Base):
    __tablename__ = "asset_identity_person_sources"
    __table_args__ = (
        UniqueConstraint("source_system", "source_table", "source_person_id"),
        {"schema": "asset"},
    )

    id = Column(BigInteger, primary_key=True)
    person_code = Column(Text)
    source_system = Column(Text, nullable=False)
    source_code = Column(Text)
    source_table = Column(Text)
    source_person_id = Column(Text, nullable=False)
    source_person_name = Column(Text)
    source_dept_code = Column(Text)
    source_status = Column(Text)
    is_temporary = Column(Boolean, server_default="false")
    match_status = Column(Text, server_default="unmatched")
    raw_data = Column(JSONB)
    last_seen_at = Column(TIMESTAMP(timezone=True))


class IdentityAccount(Base):
    __tablename__ = "asset_identity_accounts"
    __table_args__ = (
        UniqueConstraint("system_code", "account_id"),
        {"schema": "asset"},
    )

    id = Column(BigInteger, primary_key=True)
    person_code = Column(Text)
    system_code = Column(Text, nullable=False)
    source_code = Column(Text)
    account_id = Column(Text, nullable=False)
    account_name = Column(Text)
    account_status = Column(Text)
    role_codes = Column(Text)
    role_names_cn = Column(Text)
    dept_code = Column(Text)
    dept_name_cn = Column(Text)
    last_sync_at = Column(TIMESTAMP(timezone=True))
    review_status = Column(Text, server_default="unreviewed")
    note = Column(Text)


class IdentitySyncDiff(Base):
    __tablename__ = "asset_identity_sync_diffs"
    __table_args__ = {"schema": "asset"}

    id = Column(BigInteger, primary_key=True)
    diff_type = Column(Text, nullable=False)
    source_system = Column(Text, nullable=False)
    target_system = Column(Text)
    entity_type = Column(Text, nullable=False)
    entity_code = Column(Text)
    before_data = Column(JSONB)
    after_data = Column(JSONB)
    severity = Column(Text, server_default="medium")
    status = Column(Text, server_default="open")
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    handled_at = Column(TIMESTAMP(timezone=True))
