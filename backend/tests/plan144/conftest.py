"""plan144 pure-logic tests: no APP_TEST_DB_URL required.

DB-integration tests for plan144 live under tests/plan144_db/ and use the root
conftest with an isolated test database.

- A sentinel URL pair (never used to connect) satisfies the database guard for
  modules that transitively import app.core.db.
- The no-op ``clean_test_database`` fixture overrides the root autouse one so
  no database session is created in pure-logic runs (same pattern as plan126).
"""
from __future__ import annotations

import os

import pytest

_SENTINEL = "postgresql+psycopg://plan144-pure-logic-sentinel/test"
os.environ["APP_TEST_DB_URL"] = _SENTINEL
os.environ["APP_DB_URL"] = _SENTINEL
os.environ.setdefault("APP_ENV", "test")


@pytest.fixture(autouse=True)
def clean_test_database():
    yield
