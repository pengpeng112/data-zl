"""plan126 pure-logic tests: no APP_TEST_DB_URL required for unit-only files.

DB tests live in tests/test_query_asset.py and use root conftest.
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def clean_test_database():
    yield
