"""plan198 B5 pure-logic tests: no database, no live APP_TEST_DB_URL.

- A sentinel URL pair (never used to connect) satisfies the database guard for
  modules that transitively import app.core.db (relation models), same pattern
  as plan185/alembic_env.
- The no-op ``clean_test_database`` fixture overrides the root autouse one so
  no database session is created in pure-logic runs (same pattern as plan127).
"""
from __future__ import annotations

import os

import pytest

_SENTINEL = "postgresql+psycopg://plan198-pure-logic-sentinel/test"
os.environ["APP_TEST_DB_URL"] = _SENTINEL
os.environ["APP_DB_URL"] = _SENTINEL
os.environ.setdefault("APP_ENV", "test")


@pytest.fixture(autouse=True)
def clean_test_database():
    """no-op: plan198 unit tests do not touch the database."""
    yield


@pytest.fixture
def client():
    """Not used by pure unit tests; keep fixture name reserved."""
    pytest.skip("plan198 pure unit tests do not use TestClient")
