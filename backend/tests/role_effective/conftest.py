"""db_guard 子目录 conftest：guard 测试为纯逻辑子进程测试，不触数据库。

覆盖根 conftest 的 autouse clean_test_database（no-op），并避免根 conftest
因缺少 APP_TEST_DB_URL 而 pytest.exit —— 子进程测试自行构造受控环境。
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def clean_test_database():
    """no-op：guard 子进程测试不连数据库，且不要求 APP_TEST_DB_URL。"""
    yield
