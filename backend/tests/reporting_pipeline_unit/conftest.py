"""reporting_pipeline_unit 子目录 conftest：纯逻辑测试，不连任何数据库。

- 覆盖根 conftest 的 autouse clean_test_database（no-op）；
- 与 plan* 纯逻辑子目录同模式：无 APP_TEST_DB_URL 也可运行；
- 同时兼容 unittest discover（测试文件自带 sys.path 引导，不依赖本文件）。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))


@pytest.fixture(autouse=True)
def clean_test_database():
    """no-op：reporting_pipeline 单元测试不触外部数据库。"""
    yield


def _ensure_pure_logic_config() -> None:
    if not (os.environ.get("APP_TEST_DB_URL") or "").strip():
        os.environ["APP_TEST_DB_URL"] = "sqlite:///reporting_pipeline_pure_logic.db"
    if not (os.environ.get("APP_DB_URL") or "").strip():
        os.environ["APP_DB_URL"] = os.environ["APP_TEST_DB_URL"]
    os.environ.setdefault("APP_JWT_SECRET", "reporting-pipeline-test-only-secret")


_ensure_pure_logic_config()
