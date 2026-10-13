"""plan193 纯逻辑测试：不连数据库、不要求 APP_TEST_DB_URL。

193 B00 定稿的双目录模式：plan193/ 纯逻辑（本目录），
plan193_db/ 隔离库集成（需 APP_TEST_DB_URL，走根 conftest）。
哨兵 URL 满足导入 app.core.db 的引擎构造；no-op 覆盖根 autouse。
"""
from __future__ import annotations

import pytest

from tests._run_guard import apply_pure_logic_env_sentinel

_SENTINEL = "postgresql+psycopg://plan193-pure-logic-sentinel/test"
# 215 E2：无真实测试库配置时才落哨兵（混合目录运行不覆盖真实 URL）。
apply_pure_logic_env_sentinel(_SENTINEL)


@pytest.fixture(autouse=True)
def clean_test_database():
    yield
