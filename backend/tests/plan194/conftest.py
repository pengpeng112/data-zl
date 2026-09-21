"""plan194 纯逻辑测试：不连数据库、不要求 APP_TEST_DB_URL。

- 哨兵 URL（从不连接）满足导入 app.core.db / app.main 的引擎构造。
- no-op ``clean_test_database`` 覆盖根 conftest 的 autouse，
  纯逻辑运行不创建数据库会话（同 plan144 模式）。
"""
from __future__ import annotations

import os

import pytest

_SENTINEL = "postgresql+psycopg://plan194-pure-logic-sentinel/test"
os.environ["APP_TEST_DB_URL"] = _SENTINEL
os.environ["APP_DB_URL"] = _SENTINEL
os.environ.setdefault("APP_ENV", "test")


@pytest.fixture(autouse=True)
def clean_test_database():
    yield
