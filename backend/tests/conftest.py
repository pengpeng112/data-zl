from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app
from app.core.db import SessionLocal
from app.models.governance import ApiKey

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


@pytest.fixture
def client() -> TestClient:
    _ensure_test_token()
    return TestClient(app, headers={"Authorization": f"Bearer {TEST_TOKEN}"})
