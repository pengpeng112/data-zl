"""W10 方案 C：熔断器区分「JHEMR 现存用户首次纳管对齐」与「真实新建号」。

背景：08-28/08-29 两夜熔断（max_new / max_change_ratio）根因是 112 名 JHEMR
现存用户的首次纳管被计为新建。修复后：对齐候选计入 align_existing，受
identity_cb_max_align 单独约束，不再计入 max_new 与 max_change_ratio；
存在性检查失败（None）回退旧口径（全部按真实新建，保守触发）。
"""
from __future__ import annotations

import pytest

from app.services.identity_sync_orchestrator import check_thresholds


def _cands(n: int) -> list[dict]:
    return [{"emp_no": f"E{i:03d}", "classification": "doctor", "dept_codes": []} for i in range(n)]


class TestCheckThresholdsAlign:
    def test_align_within_limit_does_not_trigger(self):
        stats = {"new": 0, "update": 0, "align_existing": 112, "deactivate": 0, "scope": 103}
        result = check_thresholds([{}] * 112, stats)
        assert result["triggered"] is False

    def test_align_over_limit_triggers_max_align(self):
        # 151 个对齐候选（<max_candidates=200，否则先触发 max_candidates）
        stats = {"new": 0, "update": 0, "align_existing": 151, "deactivate": 0, "scope": 150}
        result = check_thresholds([{}] * 151, stats)
        assert result["triggered"] is True
        assert result["dimension"] == "max_align"

    def test_true_new_still_triggers_max_new(self):
        # 真实新建号（JHEMR 无账号）不受 align 豁免
        stats = {"new": 51, "update": 0, "align_existing": 0, "deactivate": 0, "scope": 500}
        result = check_thresholds([{}] * 51, stats)
        assert result["triggered"] is True
        assert result["dimension"] == "max_new"

    def test_change_ratio_excludes_align(self):
        # 112 对齐 + 2 真新 / scope 103：若对齐计入将 110%>30%，排除后 2/103≈1.9%
        stats = {"new": 2, "update": 0, "align_existing": 112, "deactivate": 0, "scope": 103}
        result = check_thresholds([{}] * 114, stats)
        assert result["triggered"] is False

    def test_legacy_stats_without_align_key_still_work(self):
        # 旧调用（无 align 键）行为不变——向后兼容
        result = check_thresholds([{}] * 10, {"new": 4, "update": 0, "deactivate": 0})
        assert result["triggered"] is True
        assert result["dimension"] == "max_change_ratio"
        result = check_thresholds([{}] * 10, {"new": 0, "update": 0, "deactivate": 0})
        assert result["triggered"] is False


class TestComputeChangeStatsAlign:
    @pytest.fixture(autouse=True)
    def _hmac_env(self, monkeypatch):
        from app.core.config import settings

        monkeypatch.setenv("TEST_HMAC_KEY", "test-only-hmac-key-not-for-prod")
        monkeypatch.setattr(settings, "identity_hmac_key_ref", "env:TEST_HMAC_KEY")

    def test_align_existing_reclassified(self, db_session):
        from app.services.identity_sync_orchestrator import _compute_change_stats

        candidates = _cands(5)
        # 无 jhemr_existing（旧口径）：5 全部 new
        stats = _compute_change_stats(db_session, candidates)
        assert stats["new"] == 5
        assert stats["align_existing"] == 0
        # 传入存在集：3 个现存 → 3 align + 2 new
        stats = _compute_change_stats(
            db_session, candidates, jhemr_existing={"E000", "E001", "E002"}
        )
        assert stats["new"] == 2
        assert stats["align_existing"] == 3

    def test_none_fallback_counts_all_as_new(self, db_session):
        from app.services.identity_sync_orchestrator import _compute_change_stats

        stats = _compute_change_stats(db_session, _cands(4), jhemr_existing=None)
        assert stats["new"] == 4
        assert stats["align_existing"] == 0


class TestWatermarkGapConfigurable:
    def test_default_48_and_override(self, monkeypatch):
        from app.core.config import settings
        from app.services.identity_sync_orchestrator import check_thresholds
        # 默认 48：49h 触发
        monkeypatch.setattr(settings, "identity_cb_max_watermark_gap_hours", 48)
        r = check_thresholds([{}] * 10, {"new": 0, "update": 0, "deactivate": 0, "watermark_gap_hours": 49})
        assert r["triggered"] is True and r["dimension"] == "watermark_continuity"
        # 临时放宽 96（W10 二次修复）：57h 放行
        monkeypatch.setattr(settings, "identity_cb_max_watermark_gap_hours", 96)
        r = check_thresholds([{}] * 10, {"new": 0, "update": 0, "deactivate": 0, "watermark_gap_hours": 57})
        assert r["triggered"] is False
