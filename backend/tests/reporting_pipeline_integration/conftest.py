"""reporting_pipeline_integration conftest：需要已核实的隔离测试库。

与根 conftest 的差异：本目录测试显式要求 APP_TEST_DB_URL 指向
data_asset_test（dev_env.sh 推导）；环境缺失时整目录 SKIP（BLOCKED_ENV），
不冒充通过。运行前必须：
1. source tools/dev_env.sh（建隧道 + 推导 APP_TEST_DB_URL）；
2. 核实无其他 pytest 会话占用该库（根 conftest advisory lock 仍然生效）。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

_TEST_URL = os.environ.get("APP_TEST_DB_URL", "")
ISOLATED_DB_AVAILABLE = bool(_TEST_URL) and "data_asset_test" in _TEST_URL


def pytest_collection_modifyitems(config, items):
    """未核实隔离库时跳过本目录全部测试（BLOCKED_ENV，不是 PASS）。"""
    if ISOLATED_DB_AVAILABLE:
        return
    skip = pytest.mark.skip(
        reason="BLOCKED_ENV: 需 source tools/dev_env.sh 并核实 data_asset_test 隔离库"
    )
    for item in items:
        if str(item.fspath).startswith(str(Path(__file__).parent)):
            item.add_marker(skip)
