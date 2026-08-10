from __future__ import annotations

import sys
import hashlib
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect, text, delete, or_

# 纯逻辑子进程测试子目录：不连数据库、不要求 APP_TEST_DB_URL，
# 各自带 no-op conftest 覆盖根 conftest 的 autouse。运行这些子目录时不触发
# 数据库门禁 exit，保证无测试库环境下仍可验证门禁/配置纯逻辑。
_PURE_LOGIC_SUBDIRS = (
    "db_guard",
    "role_effective",
    "startup_check",
    "security_audit",
    "dict_sync_112",
    "identity_title_sync",
    "identity_signature_sync",
)


def _only_pure_logic_subdirs() -> bool:
    """判断本次 pytest 命令行是否仅涉及纯逻辑子目录。"""
    args = [a for a in sys.argv if not a.startswith("-")]
    targets = [a for a in args if a.endswith(".py") or not a.endswith((".ini", ".cfg", ".toml"))]
    candidates = [a for a in targets if "tests/" in a or a.endswith("tests")]
    if not candidates:
        return False
    return all(
        any(f"{sd}/" in a or a.endswith(f"{sd}") or f"{sd}\\" in a for sd in _PURE_LOGIC_SUBDIRS)
        for a in candidates
    )


TEST_DB_URL = os.environ.get("APP_TEST_DB_URL", "")
if (not TEST_DB_URL or "test" not in TEST_DB_URL.lower()) and not _only_pure_logic_subdirs():
    pytest.exit(
        "APP_TEST_DB_URL is required and must identify a test database; refusing to use APP_DB_URL",
        returncode=2,
    )
os.environ["APP_DB_URL"] = TEST_DB_URL
os.environ["APP_ENV"] = "test"
os.environ["APP_RATE_LIMIT_ENABLED"] = "false"
os.environ.setdefault("APP_JWT_SECRET", "test-only-jwt-secret-not-for-prod")
os.environ.setdefault("APP_OPS_WRITE_ENABLED", "false")
os.environ.setdefault("APP_OPS_APPROVAL_UI_ENABLED", "false")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if not _only_pure_logic_subdirs():
    from app.main import app
    from app.core.config import settings
    from app.core.rate_limit import limiter

    settings.env = "test"
    settings.rate_limit_enabled = False
    settings.ops_write_enabled = False
    limiter.enabled = False

    from app.core.db import SessionLocal
    from app.models.governance import ApiKey
    from app.models.governance_base import AssetUserRole, AssetRole, AssetRolePermission
    from app.models.dict_medical import DictMedicalCodeItem, DictMedicalCodeMapping, DictMedicalCodeSet
    from app.models.asset import AssetTable, AssetColumn, AssetRelation
    from app.models.asset_system import AssetSystem, AssetDataSource
    from app.services.recipe_service import recipe_hash

TEST_TOKEN = "test-token-p5-auth-2026"
TEST_ADMIN = "test-platform-admin"


def _ensure_test_token():
    db = SessionLocal()
    try:
        existing = db.query(ApiKey).filter(ApiKey.key_name == "test-auto").first()
        if not existing:
            db.add(
                ApiKey(
                    key_name="test-auto",
                    token_hash=hashlib.sha256(TEST_TOKEN.encode("utf-8")).hexdigest(),
                    user_identifier=TEST_ADMIN,
                )
            )
        else:
            existing.token_hash = hashlib.sha256(TEST_TOKEN.encode("utf-8")).hexdigest()
            existing.token = None
            existing.user_identifier = TEST_ADMIN
            existing.enabled = True
        if not db.query(AssetRole).filter(AssetRole.role_code == "platform_admin").first():
            db.add(
                AssetRole(
                    role_code="platform_admin",
                    role_name_cn="平台管理员",
                    role_type="builtin",
                )
            )
        role = db.query(AssetUserRole).filter(
            AssetUserRole.user_identifier == TEST_ADMIN,
            AssetUserRole.role_code == "platform_admin",
        ).first()
        if not role:
            db.add(AssetUserRole(user_identifier=TEST_ADMIN, role_code="platform_admin", status="active"))
        db.commit()
    finally:
        db.close()


def seed_minimal_assets(db=None) -> dict:
    """Deterministic graph/tree seed for isolation-safe tests."""
    own = db is None
    if own:
        db = SessionLocal()
    try:
        from sqlalchemy import select

        if not db.scalar(select(AssetSystem).where(AssetSystem.system_code == "HIS")):
            db.add(AssetSystem(system_code="HIS", system_name_cn="HIS", system_type="HIS", status="active"))
        if not db.scalar(select(AssetSystem).where(AssetSystem.system_code == "DATA_CENTER")):
            db.add(
                AssetSystem(
                    system_code="DATA_CENTER",
                    system_name_cn="数据中心",
                    system_type="ODS",
                    status="active",
                )
            )
        if not db.scalar(select(AssetDataSource).where(AssetDataSource.source_code == "his_source_10_10_10_15")):
            db.add(
                AssetDataSource(
                    system_code="HIS",
                    source_code="his_source_10_10_10_15",
                    source_name_cn="HIS源库",
                    db_type="oracle",
                    target_host="10.10.10.15",
                    port=1521,
                    service_name="his",
                    enabled=True,
                    write_policy="readonly",
                )
            )
        if not db.scalar(select(AssetDataSource).where(AssetDataSource.source_code == "ods_8_216")):
            db.add(
                AssetDataSource(
                    system_code="DATA_CENTER",
                    source_code="ods_8_216",
                    source_name_cn="ODS",
                    db_type="oracle",
                    target_host="10.10.8.216",
                    port=1521,
                    service_name="orcl",
                    enabled=True,
                    write_policy="readonly",
                )
            )

        def ensure_table(schema: str, table: str, source: str, system: str):
            row = db.scalar(
                select(AssetTable).where(
                    AssetTable.schema_name == schema, AssetTable.table_name == table
                )
            )
            if not row:
                row = AssetTable(
                    schema_name=schema,
                    table_name=table,
                    namespace_name=schema,
                    source_code=source,
                    system_code=system,
                    column_count=2,
                    domain="test",
                )
                db.add(row)
            return row

        ensure_table("HIS", "PAT_VISIT", "his_source_10_10_10_15", "HIS")
        ensure_table("HIS", "PAT_MASTER_INDEX", "his_source_10_10_10_15", "HIS")
        ensure_table("HIS", "LAB_TEST_MASTER", "his_source_10_10_10_15", "HIS")
        ensure_table("ODS", "TEST_ASSET", "ods_8_216", "DATA_CENTER")

        for table, ordinal, column in [
            ("PAT_VISIT", 1, "PATIENT_ID"),
            ("PAT_VISIT", 2, "VISIT_ID"),
            ("PAT_MASTER_INDEX", 1, "PATIENT_ID"),
            ("LAB_TEST_MASTER", 1, "PATIENT_ID"),
            ("LAB_TEST_MASTER", 2, "VISIT_ID"),
        ]:
            exists = db.scalar(
                select(AssetColumn).where(
                    AssetColumn.schema_name == "HIS",
                    AssetColumn.table_name == table,
                    AssetColumn.column_name == column,
                )
            )
            if not exists:
                db.add(
                    AssetColumn(
                        system_code="HIS",
                        source_code="his_source_10_10_10_15",
                        namespace_name="HIS",
                        schema_name="HIS",
                        table_name=table,
                        column_id=ordinal,
                        column_name=column,
                        data_type="VARCHAR2",
                        nullable="N",
                        review_status="test_seed",
                    )
                )

        ods_column = db.scalar(
            select(AssetColumn).where(
                AssetColumn.schema_name == "ODS",
                AssetColumn.table_name == "TEST_ASSET",
                AssetColumn.column_name == "ASSET_ID",
            )
        )
        if not ods_column:
            db.add(
                AssetColumn(
                    system_code="DATA_CENTER",
                    source_code="ods_8_216",
                    namespace_name="ODS",
                    schema_name="ODS",
                    table_name="TEST_ASSET",
                    column_id=1,
                    column_name="ASSET_ID",
                    data_type="VARCHAR2",
                    nullable="N",
                    review_status="test_seed",
                )
            )

        rel = db.scalar(select(AssetRelation).where(AssetRelation.rel_id == 900001))
        if not rel:
            db.add(
                AssetRelation(
                    rel_id=900001,
                    domain="test",
                    from_table="HIS.PAT_VISIT",
                    from_columns="PATIENT_ID",
                    to_table="HIS.PAT_MASTER_INDEX",
                    to_columns="PATIENT_ID",
                    join_condition="HIS.PAT_VISIT.PATIENT_ID = HIS.PAT_MASTER_INDEX.PATIENT_ID",
                    cardinality="N:1",
                    confidence="A",
                    validation_level="A_rechecked",
                    validation_status="verified",
                )
            )
        rel2 = db.scalar(select(AssetRelation).where(AssetRelation.rel_id == 900002))
        if not rel2:
            db.add(
                AssetRelation(
                    rel_id=900002,
                    domain="test",
                    from_table="HIS.LAB_TEST_MASTER",
                    from_columns="PATIENT_ID,VISIT_ID",
                    to_table="HIS.PAT_VISIT",
                    to_columns="PATIENT_ID,VISIT_ID",
                    join_condition="HIS.LAB_TEST_MASTER.PATIENT_ID = HIS.PAT_VISIT.PATIENT_ID",
                    cardinality="N:1",
                    confidence="B",
                    validation_level="B",
                    validation_status="verified",
                )
            )
        db.commit()
        return {"ok": True}
    finally:
        if own:
            db.close()


def _cleanup_test_medical_dicts():
    db = SessionLocal()
    try:
        db.execute(
            delete(DictMedicalCodeMapping).where(
                or_(
                    DictMedicalCodeMapping.from_code_set.like("test_%"),
                    DictMedicalCodeMapping.to_code_set.like("test_%"),
                    DictMedicalCodeMapping.from_code_set.in_(["clinical_diag", "national_diag"]),
                    DictMedicalCodeMapping.to_code_set.in_(["clinical_diag", "national_diag"]),
                )
            )
        )
        db.execute(
            delete(DictMedicalCodeItem).where(
                or_(
                    DictMedicalCodeItem.code_set_code.like("test_%"),
                    DictMedicalCodeItem.code_set_code.in_(["clinical_diag", "national_diag"]),
                )
            )
        )
        db.execute(
            delete(DictMedicalCodeSet).where(
                or_(
                    DictMedicalCodeSet.code_set_code.like("test_%"),
                    DictMedicalCodeSet.code_set_code.in_(["clinical_diag", "national_diag"]),
                )
            )
        )
        for table in [
            "asset_dict_medical_code_sets",
            "asset_dict_medical_code_items",
            "asset_dict_medical_code_mappings",
        ]:
            try:
                db.execute(
                    text(
                        f"select setval(pg_get_serial_sequence('asset.{table}', 'id'), "
                        f"coalesce((select max(id) from asset.{table}), 0) + 1, false)"
                    )
                )
            except Exception:
                db.rollback()
        db.commit()
    finally:
        db.close()


@pytest.fixture(autouse=True)
def clean_test_database():
    # Every test receives the same deterministic minimum catalog.  The former
    # clone-dependent suite became order-dependent because the previous test
    # truncated every asset table during teardown.
    seed_minimal_assets()
    yield
    db = SessionLocal()
    try:
        table_names = inspect(db.get_bind()).get_table_names(schema="asset")
        if table_names:
            quoted_tables = ", ".join(f'asset."{name}"' for name in table_names)
            db.execute(text(f"TRUNCATE TABLE {quoted_tables} RESTART IDENTITY CASCADE"))
            db.commit()
    finally:
        db.close()


@pytest.fixture
def db_session():
    """111 号 S1：测试统一通过该 fixture 获取数据库会话。

    取代测试模块内直接 import SessionLocal 创建会话的做法；配合 app/core/db.py
    的建连前门禁，确保任何测试入口都无法连接非测试库。
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()  # 先回滚避免 PendingRollbackError 掩盖原始异常
        raise
    finally:
        db.close()


@pytest.fixture
def client() -> TestClient:
    _ensure_test_token()
    try:
        yield TestClient(app, headers={"Authorization": f"Bearer {TEST_TOKEN}"})
    finally:
        _cleanup_test_medical_dicts()


@pytest.fixture
def seeded_client(client: TestClient) -> TestClient:
    """Client plus minimal HIS graph seed."""
    seed_minimal_assets()
    return client


@pytest.fixture
def second_user_token() -> str:
    """Create a second bound API key for non-self approval scenarios."""
    token = "test-token-second-user-2026"
    db = SessionLocal()
    try:
        existing = db.query(ApiKey).filter(ApiKey.key_name == "test-second").first()
        if not existing:
            db.add(
                ApiKey(
                    key_name="test-second",
                    token_hash=hashlib.sha256(token.encode("utf-8")).hexdigest(),
                    user_identifier="test-approver-b",
                )
            )
        else:
            existing.token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
            existing.user_identifier = "test-approver-b"
            existing.enabled = True
        if not db.query(AssetRole).filter(AssetRole.role_code == "platform_admin").first():
            db.add(AssetRole(role_code="platform_admin", role_name_cn="平台管理员", role_type="builtin"))
        if not db.query(AssetUserRole).filter(
            AssetUserRole.user_identifier == "test-approver-b",
            AssetUserRole.role_code == "platform_admin",
        ).first():
            db.add(
                AssetUserRole(
                    user_identifier="test-approver-b",
                    role_code="platform_admin",
                    status="active",
                )
            )
        db.commit()
    finally:
        db.close()
    return token
