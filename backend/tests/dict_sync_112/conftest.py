"""112 T1 子目录 conftest：pure-logic 测试不触数据库。

覆盖根 conftest 的 autouse clean_test_database（no-op），并避免根 conftest
因缺少 APP_TEST_DB_URL 而 pytest.exit。子进程测试自行构造受控环境。
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def clean_test_database():
    """no-op：112 T1 纯逻辑测试不连数据库，且不要求 APP_TEST_DB_URL。"""
    yield