"""S1 探针目标：仅用于子进程负向测试验证 import app.core.db 会触发门禁。

在 --noconftest / 单文件运行且缺少合法 APP_TEST_DB_URL 时，import 该模块应在
create_engine 前失败，而不是连接任何非测试库。直接收集本文件（无
RUN_TEST_TARGET 标记）时跳过，避免被日常 pytest 误触发。
"""
import os

import pytest


def probe_engine_health() -> dict:
    from app.core.db import SessionLocal

    return {"engine_imported": True, "is_test": bool(SessionLocal)}


@pytest.mark.skipif(
    os.environ.get("RUN_TEST_TARGET") != "1",
    reason="探针目标仅用于 guard 子进程负向测试（需 RUN_TEST_TARGET=1）",
)
def test_guard_target_collects() -> None:
    # 使本文件成为可被 pytest 收集的测试模块（文件名须以 test_ 开头）。
    probe_engine_health()