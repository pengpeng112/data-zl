"""security_audit 子目录 conftest：纯逻辑/静态断言测试不触数据库。

覆盖根 conftest 的 autouse clean_test_database（no-op）。本目录的用例
只做源码/目录静态断言或纯逻辑校验，但部分用例在测试函数内 import
app.api.v1.permissions，会连带触发 app.core.db 的引擎构造；在未配置
APP_TEST_DB_URL 的纯逻辑环境下，注入一次性 sqlite 测试 URL（含 test
字样满足 database_guard；引擎惰性构造，从不连接）使配置导入可完成。
真实数据库集成测试仍要求显式 APP_TEST_DB_URL 指向允许清理的隔离库。
"""
from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def clean_test_database():
    """no-op：本目录纯逻辑/静态测试不连数据库。"""
    yield


def _ensure_pure_logic_config() -> None:
    if not (os.environ.get("APP_TEST_DB_URL") or "").strip():
        os.environ["APP_TEST_DB_URL"] = "sqlite:///pure_logic_test.db"
    if not (os.environ.get("APP_DB_URL") or "").strip():
        os.environ["APP_DB_URL"] = os.environ["APP_TEST_DB_URL"]


_ensure_pure_logic_config()
