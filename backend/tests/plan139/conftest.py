"""plan139 pure-logic tests: no database, no APP_TEST_DB_URL.

Covers read-only harvester enhancements, the multi-dialect view relation
parser and plan139 importers' pure preparation logic.  Database-backed checks
run in the full suite against the isolated test database.
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def clean_test_database():
    """no-op: plan139 unit tests do not touch the database."""
    yield
