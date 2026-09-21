"""plan185_docare_reliability pure-logic tests: no APP_TEST_DB_URL required.

Tests import the improved docare_mismatch_daily.py script from
开发起步包/output_r177/ by path and drive it with fake connectors and
monkeypatched sleep/clock — no database, no network, no production paths.

- A sentinel URL pair (never used to connect) satisfies the database guard for
  modules that transitively import app.core.db.
- The no-op ``clean_test_database`` fixture overrides the root autouse one so
  no database session is created in pure-logic runs (same pattern as plan144).
"""
from __future__ import annotations

import os

import pytest

_SENTINEL = "postgresql+psycopg://plan185-pure-logic-sentinel/test"
os.environ["APP_TEST_DB_URL"] = _SENTINEL
os.environ["APP_DB_URL"] = _SENTINEL
os.environ.setdefault("APP_ENV", "test")


@pytest.fixture(autouse=True)
def clean_test_database():
    yield
