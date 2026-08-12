"""plan127 pure-logic tests: no database, no APP_TEST_DB_URL.

Overrides root autouse clean_test_database (which references SessionLocal).
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def clean_test_database():
    """no-op: plan127 unit tests do not touch the database."""
    yield


@pytest.fixture
def client():
    """Not used by pure unit tests; keep fixture name reserved."""
    pytest.skip("plan127 pure unit tests do not use TestClient")
