"""215 E3：调度器 start() 总闸（_should_start_scheduler）开/关两态测试。

回归核心：只开 quality_execution_scheduler_enabled（config 默认 False，207
质量执行 tick 的唯一开关）而 asset_scheduler_jobs 为空、其余开关全关时，
调度器仍必须启动——round-12 实锤的原条件漏掉该开关，导致 tick 永不运行。
"""
from __future__ import annotations

import pytest

from app.main import _should_start_scheduler, settings

ALL_SCHEDULER_FLAGS = (
    "identity_nightly_enabled",
    "dict_medical_push_enabled",
    "query_schedule_enabled",
    "quality_execution_scheduler_enabled",
)


@pytest.fixture(autouse=True)
def _all_scheduler_flags_off(monkeypatch):
    for flag in ALL_SCHEDULER_FLAGS:
        monkeypatch.setattr(settings, flag, False)


def test_all_flags_off_and_no_jobs_do_not_start():
    assert _should_start_scheduler([]) is False


def test_quality_execution_scheduler_alone_starts_scheduler(monkeypatch):
    """round-12 缺陷回归：只开质量执行调度时 tick 必须能跑。"""
    monkeypatch.setattr(settings, "quality_execution_scheduler_enabled", True)
    assert _should_start_scheduler([]) is True


@pytest.mark.parametrize(
    "flag",
    ["identity_nightly_enabled", "dict_medical_push_enabled", "query_schedule_enabled"],
)
def test_each_other_flag_alone_starts_scheduler(monkeypatch, flag):
    monkeypatch.setattr(settings, flag, True)
    assert _should_start_scheduler([]) is True


def test_registered_jobs_start_scheduler_even_with_flags_off():
    assert _should_start_scheduler(["asset_scheduler_jobs:1"]) is True
