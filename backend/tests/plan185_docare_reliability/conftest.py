"""plan185_docare_reliability pure-logic tests: no APP_TEST_DB_URL required.

Tests import the improved docare_mismatch_daily.py script from
开发起步包/output_r177/ by path and drive it with fake connectors and
monkeypatched sleep/clock — no database, no network, no production paths.

- A sentinel URL pair (never used to connect) satisfies the database guard for
  modules that transitively import app.core.db.
- The no-op ``clean_test_database`` fixture overrides the root autouse one so
  no database session is created in pure-logic runs (same pattern as plan144).
"""
from __future__ import annotations

import pytest

from tests._run_guard import apply_pure_logic_env_sentinel

_SENTINEL = "postgresql+psycopg://plan185-pure-logic-sentinel/test"
# 215 E2：无真实测试库配置时才落哨兵（混合目录运行不覆盖真实 URL）。
apply_pure_logic_env_sentinel(_SENTINEL)


@pytest.fixture(autouse=True)
def clean_test_database():
    yield
