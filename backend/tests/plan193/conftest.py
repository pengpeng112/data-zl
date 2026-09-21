"""plan193 纯逻辑测试：不连数据库、不要求 APP_TEST_DB_URL。

193 B00 定稿的双目录模式：plan193/ 纯逻辑（本目录），
plan193_db/ 隔离库集成（需 APP_TEST_DB_URL，走根 conftest）。
哨兵 URL 满足导入 app.core.db 的引擎构造；no-op 覆盖根 autouse。
"""
from __future__ import annotations

import os

import pytest

_SENTINEL = "postgresql+psycopg://plan193-pure-logic-sentinel/test"
os.environ["APP_TEST_DB_URL"] = _SENTINEL
os.environ["APP_DB_URL"] = _SENTINEL
os.environ.setdefault("APP_ENV", "test")


@pytest.fixture(autouse=True)
def clean_test_database():
    yield
