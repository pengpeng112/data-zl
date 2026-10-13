"""plan144 pure-logic tests: no APP_TEST_DB_URL required.

DB-integration tests for plan144 live under tests/plan144_db/ and use the root
conftest with an isolated test database.

- A sentinel URL pair (never used to connect) satisfies the database guard for
  modules that transitively import app.core.db.
- The no-op ``clean_test_database`` fixture overrides the root autouse one so
  no database session is created in pure-logic runs (same pattern as plan126).
"""
from __future__ import annotations

import pytest

from tests._run_guard import apply_pure_logic_env_sentinel

_SENTINEL = "postgresql+psycopg://plan144-pure-logic-sentinel/test"
# 215 E2：无真实测试库配置时才落哨兵——混合目录运行保留根 conftest 设置的
# 真实 APP_TEST_DB_URL/APP_DB_URL，收集期不再全局覆盖污染同进程 DB 集成测试；
# 哨兵仅满足传递导入 app.core.db 的守卫，引擎惰性构造从不连接。
apply_pure_logic_env_sentinel(_SENTINEL)


@pytest.fixture(autouse=True)
def clean_test_database():
    yield
