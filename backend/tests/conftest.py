from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app
from app.core.db import SessionLocal
from app.models.governance import ApiKey
from app.models.dict_medical import DictMedicalCodeItem, DictMedicalCodeMapping, DictMedicalCodeSet
from sqlalchemy import delete, or_, text

TEST_TOKEN = "test-token-p5-auth-2026"


def _ensure_test_token():
    db = SessionLocal()
    try:
        existing = db.query(ApiKey).filter(ApiKey.key_name == "test-auto").first()
        if not existing:
            db.add(ApiKey(key_name="test-auto", token=TEST_TOKEN))
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
@pytest.fixture
def client() -> TestClient:
    _ensure_test_token()
    try:
        yield TestClient(app, headers={"Authorization": f"Bearer {TEST_TOKEN}"})
    finally:
        _cleanup_test_medical_dicts()
