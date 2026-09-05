"""176 F-2：熔断器 update 维度区分「托管在册例行 resync」与「真实变更」。

背景（176 §1）：托管圈约 110 人每晚全部落入 update 桶，而默认
identity_cb_max_update=100——110>100 每晚必然熔断，签名/职称子任务连带
跳过（09-01/02/03 三晚）。修复后：

- 托管在册且不在 HIS MODIFIEDTIME 增量内的候选（例行 resync）计入
  resync_unchanged 单列维度，不计入 max_update 与 max_change_ratio
  （比照 W10 对 align_existing 的处理）；
- 真实变更（增量命中 modified_time）仍计入 update，110 人 > 100 依旧熔断；
- JHEMR 存在性检查失败（None）时回退旧口径：托管候选保守计 update
  （fail-closed，不享受 F-2 豁免）。

F-1（env 阈值 150）与本语义独立：F-2 上线后 max_update 可回落默认 100。
"""
from __future__ import annotations

import pytest

from app.services.identity_sync_orchestrator import check_thresholds


def _cands(n: int, *, modified: bool = False) -> list[dict]:
    return [
        {
            "emp_no": f"E{i:03d}",
            "classification": "doctor",
            "dept_codes": [],
            "modified_time": "2026-09-03T10:00:00" if modified else None,
        }
        for i in range(n)
    ]


class TestCheckThresholdsResync:
    def test_pure_resync_110_does_not_trigger_max_update(self):
        # 176 场景：托管圈 110 人例行 resync（空增量夜）——修复前必熔断
        stats = {"new": 0, "update": 0, "align_existing": 0, "resync_unchanged": 110, "deactivate": 0, "scope": 110}
        result = check_thresholds([{}] * 110, stats)
        assert result["triggered"] is False

    def test_real_update_110_still_triggers_max_update(self, monkeypatch):
        # 真实变更不受豁免：默认阈值 100 下 110 人仍熔断
        from app.core.config import settings
        monkeypatch.setattr(settings, "identity_cb_max_update", 100)
        stats = {"new": 0, "update": 110, "align_existing": 0, "resync_unchanged": 0, "deactivate": 0, "scope": 110}
        result = check_thresholds([{}] * 110, stats)
        assert result["triggered"] is True
        assert result["dimension"] == "max_update"

    def test_change_ratio_excludes_resync(self):
        # 110 resync + 2 真实 update / scope 110：若 resync 计入将 100%>30%，排除后 2/110≈1.8%
        stats = {"new": 0, "update": 2, "align_existing": 0, "resync_unchanged": 110, "deactivate": 0, "scope": 110}
        result = check_thresholds([{}] * 112, stats)
        assert result["triggered"] is False

    def test_resync_still_bound_by_max_candidates(self, monkeypatch):
        # 例行 resync 不受 max_update 约束，但总量仍受 max_candidates 保护
        from app.core.config import settings
        monkeypatch.setattr(settings, "identity_cb_max_candidates", 200)
        stats = {"new": 0, "update": 0, "align_existing": 0, "resync_unchanged": 250, "deactivate": 0, "scope": 250}
        result = check_thresholds([{}] * 250, stats)
        assert result["triggered"] is True
        assert result["dimension"] == "max_candidates"


class TestComputeChangeStatsResync:
    @pytest.fixture(autouse=True)
    def _hmac_env(self, monkeypatch):
        from app.core.config import settings

        monkeypatch.setenv("TEST_HMAC_KEY", "test-only-hmac-key-not-for-prod")
        monkeypatch.setattr(settings, "identity_hmac_key_ref", "env:TEST_HMAC_KEY")

    @pytest.fixture
    def _managed(self, db_session):
        """把传入工号登记为 CDMS 托管在册（active managed relation）。"""
        from app.models.identity_sync import IdentityManagedRelation
        from app.services.identity_hmac import compute_account_fingerprint
        from app.core.config import settings

        def _add(emp_nos: list[str]) -> None:
            for i, emp in enumerate(emp_nos):
                db_session.add(IdentityManagedRelation(
                    batch_id="B-f2",
                    target_system="CDMS",
                    account_fingerprint=compute_account_fingerprint(emp, "CDMS", settings.identity_hmac_key_ref),
                    relation_type="account",
                    target_table="T_MSS_EMP_DICT",
                    status="active",
                    idempotency_key=f"k-f2-{i}",
                ))
            db_session.commit()

        return _add

    def test_110_managed_pure_resync_reclassified(self, db_session, _managed):
        from app.services.identity_sync_orchestrator import _compute_change_stats

        emps = [f"E{i:03d}" for i in range(110)]
        _managed(emps)
        candidates = _cands(110, modified=False)
        stats = _compute_change_stats(db_session, candidates, jhemr_existing=set(emps))
        assert stats["resync_unchanged"] == 110
        assert stats["update"] == 0
        assert stats["new"] == 0
        assert stats["align_existing"] == 0

    def test_110_managed_real_updates_stay_in_update_bucket(self, db_session, _managed):
        from app.services.identity_sync_orchestrator import _compute_change_stats

        emps = [f"E{i:03d}" for i in range(110)]
        _managed(emps)
        candidates = _cands(110, modified=True)
        stats = _compute_change_stats(db_session, candidates, jhemr_existing=set(emps))
        assert stats["update"] == 110
        assert stats["resync_unchanged"] == 0

    def test_existence_check_failure_falls_back_conservative(self, db_session, _managed):
        # fail-closed：存在性检查失败（None）时托管候选不享受豁免，回退旧口径
        from app.services.identity_sync_orchestrator import _compute_change_stats

        _managed([f"E{i:03d}" for i in range(110)])
        stats = _compute_change_stats(db_session, _cands(110, modified=False), jhemr_existing=None)
        assert stats["update"] == 110
        assert stats["resync_unchanged"] == 0

    def test_mixed_increment_splits_buckets(self, db_session, _managed):
        from app.services.identity_sync_orchestrator import _compute_change_stats

        emps = [f"E{i:03d}" for i in range(110)]
        _managed(emps)
        # 105 例行 + 5 增量命中：5 update + 105 resync
        candidates = _cands(105, modified=False) + _cands(5, modified=True)
        stats = _compute_change_stats(db_session, candidates, jhemr_existing=set(emps))
        assert stats["update"] == 5
        assert stats["resync_unchanged"] == 105

    def test_unmanaged_candidates_unchanged_by_f2(self, db_session):
        # 未托管候选不受 F-2 影响：JHEMR 存在→align_existing，不存在→new
        from app.services.identity_sync_orchestrator import _compute_change_stats

        candidates = _cands(4, modified=False)
        stats = _compute_change_stats(db_session, candidates, jhemr_existing={"E000", "E001"})
        assert stats["align_existing"] == 2
        assert stats["new"] == 2
        assert stats["resync_unchanged"] == 0
