"""alembic_env pure-logic tests: no APP_TEST_DB_URL required.

178 R3（C7）：只读断言 alembic/env.py 的 DDL 文本，不连任何数据库。
照抄 tests/plan144/conftest.py 模式：哨兵 URL 满足会传递导入
app.core.db 的守卫；no-op clean_test_database 覆盖根 conftest 的 autouse。
"""
from __future__ import annotations

import pytest

from tests._run_guard import apply_pure_logic_env_sentinel

_SENTINEL = "postgresql+psycopg://alembic-env-pure-logic-sentinel/test"
# 215 E2：无真实测试库配置时才落哨兵（混合目录运行不覆盖真实 URL）。
apply_pure_logic_env_sentinel(_SENTINEL)


@pytest.fixture(autouse=True)
def clean_test_database():
    yield
