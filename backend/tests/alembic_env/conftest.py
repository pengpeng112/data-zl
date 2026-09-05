"""alembic_env pure-logic tests: no APP_TEST_DB_URL required.

178 R3（C7）：只读断言 alembic/env.py 的 DDL 文本，不连任何数据库。
照抄 tests/plan144/conftest.py 模式：哨兵 URL 满足会传递导入
app.core.db 的守卫；no-op clean_test_database 覆盖根 conftest 的 autouse。
"""
from __future__ import annotations

import os

import pytest

_SENTINEL = "postgresql+psycopg://alembic-env-pure-logic-sentinel/test"
os.environ["APP_TEST_DB_URL"] = _SENTINEL
os.environ["APP_DB_URL"] = _SENTINEL
os.environ.setdefault("APP_ENV", "test")


@pytest.fixture(autouse=True)
def clean_test_database():
    yield
