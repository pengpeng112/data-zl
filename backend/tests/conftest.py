from __future__ import annotations

import sys
import hashlib
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect

TEST_DB_URL = os.environ.get("APP_TEST_DB_URL", "")
if not TEST_DB_URL or "test" not in TEST_DB_URL.lower():
    pytest.exit("APP_TEST_DB_URL is required and must identify a test database; refusing to use APP_DB_URL", returncode=2)
os.environ["APP_DB_URL"] = TEST_DB_URL
# 强制测试环境关闭 slowapi（不可用 setdefault：进程里已有 APP_ENV=dev 时会继续限流 → 429）
os.environ["APP_ENV"] = "test"
os.environ["APP_RATE_LIMIT_ENABLED"] = "false"
os.environ.setdefault("APP_JWT_SECRET", "test-only-jwt-secret-not-for-prod")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app
from app.core.config import settings
from app.core.rate_limit import limiter

# 双保险：settings 可能在 import 时已缓存；强制改写并关闭限流
settings.env = "test"
settings.rate_limit_enabled = False
limiter.enabled = False
from app.core.db import SessionLocal
from app.models.governance import ApiKey
from app.models.governance_base import AssetUserRole
from app.models.dict_medical import DictMedicalCodeItem, DictMedicalCodeMapping, DictMedicalCodeSet
from sqlalchemy import delete, or_, text

TEST_TOKEN = "test-token-p5-auth-2026"


def _ensure_test_token():
    db = SessionLocal()
    try:
        existing = db.query(ApiKey).filter(ApiKey.key_name == "test-auto").first()
        if not existing:
            db.add(ApiKey(
                key_name="test-auto",
                token_hash=hashlib.sha256(TEST_TOKEN.encode("utf-8")).hexdigest(),
                user_identifier="test-platform-admin",
            ))
        else:
            existing.token_hash = hashlib.sha256(TEST_TOKEN.encode("utf-8")).hexdigest()
            existing.token = None
            existing.user_identifier = "test-platform-admin"
            existing.enabled = True
        role = db.query(AssetUserRole).filter(
            AssetUserRole.user_identifier == "test-platform-admin",
            AssetUserRole.role_code == "platform_admin",
        ).first()
        if not role:
            db.add(AssetUserRole(user_identifier="test-platform-admin", role_code="platform_admin"))
        db.commit()
    finally:
        db.close()




def _cleanup_test_medical_dicts():
    db = SessionLocal()
    try:
        db.execute(delete(DictMedicalCodeMapping).where(or_(
            DictMedicalCodeMapping.from_code_set.like("test_%"),
            DictMedicalCodeMapping.to_code_set.like("test_%"),
            DictMedicalCodeMapping.from_code_set.in_(["clinical_diag", "national_diag"]),
            DictMedicalCodeMapping.to_code_set.in_(["clinical_diag", "national_diag"]),
        )))
        db.execute(delete(DictMedicalCodeItem).where(or_(
            DictMedicalCodeItem.code_set_code.like("test_%"),
            DictMedicalCodeItem.code_set_code.in_(["clinical_diag", "national_diag"]),
        )))
        db.execute(delete(DictMedicalCodeSet).where(or_(
            DictMedicalCodeSet.code_set_code.like("test_%"),
            DictMedicalCodeSet.code_set_code.in_(["clinical_diag", "national_diag"]),
        )))
        for table in ["asset_dict_medical_code_sets", "asset_dict_medical_code_items", "asset_dict_medical_code_mappings"]:
            db.execute(text(f"select setval(pg_get_serial_sequence('asset.{table}', 'id'), coalesce((select max(id) from asset.{table}), 0) + 1, false)"))
        db.commit()
    finally:
        db.close()
@pytest.fixture(autouse=True)
def clean_test_database():
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
def client() -> TestClient:
    _ensure_test_token()
    try:
        yield TestClient(app, headers={"Authorization": f"Bearer {TEST_TOKEN}"})
    finally:
        _cleanup_test_medical_dicts()
