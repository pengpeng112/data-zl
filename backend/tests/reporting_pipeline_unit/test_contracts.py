"""契约层单元测试：分层就绪（未知不可变READY）、行分类守恒、状态机转换。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.reporting_pipeline import contracts as c


def _seed_spec(**overrides) -> c.TaskSpec:
    """最小合法种子形态：disabled/UNKNOWN/UNDECIDED。"""
    base = dict(
        canonical_table="EMR_TEST_TABLE",
        business_name="测试表",
        index=1,
        enabled=False,
        applicability=c.Applicability.TO_VERIFY,
        engine=c.Engine.UNDECIDED,
        incremental_strategy=c.IncrementalStrategy.UNRESOLVED,
        source_candidates=[
            c.SourceRef(
                object_id="ods__V_EMR_TEST_TABLE",
                role="primary",
                source_group="ods",
                host="10.10.8.216",
                port=1521,
                object_name_candidates=["V_EMR_TEST_TABLE"],
            )
        ],
        target=c.TargetRef(
            host="10.10.8.74", port=1521, service="orcl",
            owner="DBOPER", table="EMR_TEST_TABLE",
        ),
        stable_key=c.StableKey(candidate=["ID"]),
        associations=c.TaskAssociations(),
    )
    base.update(overrides)
    return c.TaskSpec(**base)


def _verified_spec() -> c.TaskSpec:
    """全部生产前置已核的完整形态：各生产层应为 READY。"""
    spec = _seed_spec(
        engine=c.Engine.PYTHON,
        incremental_strategy=c.IncrementalStrategy.CHANGE_WATERMARK,
        projection=[
            c.ProjectionField(name="ID", target_type="VARCHAR2(64)", order=1, type_verified=True),
            c.ProjectionField(name="AMOUNT", target_type="NUMBER(18,2)", order=2, type_verified=True),
        ],
        definition_fingerprint="a" * 64,
        dependency_fingerprints={"dict_fee": "b" * 64},
    )
    for src in spec.source_candidates:
        src.current_identity_verified = True
    spec.target.current_identity_verified = True
    spec.stable_key.verified = True
    spec.time_semantics.business_time_expression = "START_DATE_TIME"
    spec.time_semantics.business_time_verified = True
    spec.time_semantics.change_time_expression = "MODIFIED_AT"
    spec.time_semantics.change_time_verified = True
    spec.change_policy.insert_evidence = "MODIFIED_AT IS NOT NULL"
    spec.change_policy.update_evidence = "MODIFIED_AT"
    spec.change_policy.version_order_verified = True
    spec.apply_policy.executor_ref = "asset_action_executors:whitelisted"
    spec.apply_policy.allowed_operations = ["MERGE"]
    spec.apply_policy.idempotency_key = ["ID"]
    spec.apply_policy.approval_refs = ["APPROVAL-2026-001"]
    spec.apply_policy.commit_receipt_mode = "SAME_TARGET_TXN"
    spec.resource_budget.query_timeout_seconds = 60
    spec.resource_budget.cancel_supported = True
    spec.associations.performance_profile_id = "EMR_TEST_TABLE__PROFILE"
    spec.associations.long_lived_credential_ref = "vault:reporting/ods"
    spec.associations.running_writer_handoff_state = "HANDOFF_VERIFIED"
    spec.associations.deadline_state = c.DeadlineState.CONFIGURED
    spec.associations.deadline = "08:00+08:00"
    return spec


class TestLayeredReadiness(unittest.TestCase):
    def test_seed_unknown_not_ready(self):
        """种子（未核）生产层必须 UNKNOWN，绝不能 READY。"""
        verdicts = _seed_spec().layer_verdicts()
        self.assertEqual(
            verdicts[c.ReadinessLayer.CONFIG_VALID].status, c.LayerStatus.READY
        )
        for layer in (
            c.ReadinessLayer.READ_READY,
            c.ReadinessLayer.STAGE_READY,
            c.ReadinessLayer.APPLY_READY,
            c.ReadinessLayer.REPORT_READY,
        ):
            self.assertEqual(verdicts[layer].status, c.LayerStatus.UNKNOWN, layer)
            self.assertTrue(verdicts[layer].reasons, f"{layer} 应有未知原因")

    def test_fully_verified_reaches_ready(self):
        verdicts = _verified_spec().layer_verdicts()
        for layer in c.ReadinessLayer:
            self.assertEqual(
                verdicts[layer].status,
                c.LayerStatus.READY,
                f"{layer}: {verdicts[layer].reasons}",
            )

    def test_enable_refused_on_unknown(self):
        with self.assertRaises(c.ContractViolation) as ctx:
            _seed_spec(enabled=True).validate_enable()
        self.assertIn("禁止启用", str(ctx.exception))

    def test_enable_allowed_when_verified(self):
        spec = _verified_spec()
        spec.enabled = True
        spec.validate_enable()  # 不抛即通过

    def test_deadline_configured_without_value_structural_fail(self):
        assoc = c.TaskAssociations(
            deadline_state=c.DeadlineState.CONFIGURED, deadline=None
        )
        with self.assertRaises(c.ContractViolation):
            _seed_spec(associations=assoc).validate_structure()

    def test_multi_source_without_route_rejected(self):
        second = c.SourceRef(
            object_id="lis__V_EMR_TEST_TABLE",
            role="history",
            source_group="lis",
            host="10.10.10.73",
            port=1433,
            object_name_candidates=["V_EMR_TEST_TABLE"],
        )
        with self.assertRaises(c.ContractViolation) as ctx:
            _seed_spec(source_candidates=[
                _seed_spec().source_candidates[0], second
            ]).validate_structure()
        self.assertIn("route_policy_ref", str(ctx.exception))


class TestBatchManifest(unittest.TestCase):
    def _manifest(self, **overrides) -> c.BatchManifest:
        base = dict(
            batch_id="B-20261019-001",
            attempt_id="A-1",
            task_id="EMR_TEST_TABLE",
            config_version="v1",
            definition_fingerprint="a" * 64,
            source_identity="ods__V_EMR_TEST_TABLE",
            window_fingerprint="win:2026-10-18T00:00/2026-10-19T00:00",
            source_visibility_cutoff="2026-10-19T01:23:45+08:00",
            rows=c.RowClassification(
                source_read_rows=100, valid=90, duplicate_conflict=2,
                quarantined=3, pending_apply=5, unreadable_partial=0,
            ),
            pagination_complete=True,
            end_reason=c.EndReason.WINDOW_COMPLETE,
            shard_count=2,
            file_count=2,
            total_bytes=2048,
            schema_version="V1.3",
            type_contract_version="tc-1",
            payload_sha256="c" * 64,
        )
        base.update(overrides)
        return c.BatchManifest(**base)

    def test_conservation_required(self):
        with self.assertRaises(c.ContractViolation) as ctx:
            self._manifest(rows=c.RowClassification(source_read_rows=100, valid=99)).validate()
        self.assertIn("不守恒", str(ctx.exception))

    def test_window_complete_requires_pagination(self):
        m = self._manifest(pagination_complete=False)
        with self.assertRaises(c.ContractViolation):
            m.validate()

    def test_capture_promotion_blocked_when_incomplete(self):
        m = self._manifest(pagination_complete=False, end_reason=c.EndReason.ROW_CAP)
        m.validate()
        self.assertFalse(m.can_promote_to_captured())
        m2 = self._manifest(
            rows=c.RowClassification(source_read_rows=10, valid=9, unreadable_partial=1)
        )
        self.assertFalse(m2.can_promote_to_captured())

    def test_capture_promotion_ok(self):
        self.assertTrue(self._manifest().can_promote_to_captured())


class TestBatchStateMachine(unittest.TestCase):
    def _manifest_for_capture(self, complete: bool = True) -> c.BatchManifest:
        return c.BatchManifest(
            batch_id="B-1", attempt_id="A-1", task_id="T", config_version="v1",
            definition_fingerprint=None, source_identity="s", window_fingerprint="w",
            source_visibility_cutoff="cut",
            rows=c.RowClassification(source_read_rows=1, valid=1),
            pagination_complete=complete,
            end_reason=(
                c.EndReason.WINDOW_COMPLETE if complete else c.EndReason.ROW_CAP
            ),
            shard_count=1, file_count=1, total_bytes=10, schema_version="v",
            type_contract_version="t", payload_sha256="d" * 64,
        )

    def test_main_chain_forward_only(self):
        sm = c.BatchStateMachine()
        sm.transition(c.BatchState.CAPTURING, reason="start")
        with self.assertRaises(c.ContractViolation):
            sm.transition(c.BatchState.VALIDATED, reason="跳步")
        sm.transition(
            c.BatchState.CAPTURED, reason="captured",
            manifest=self._manifest_for_capture(),
        )

    def test_capture_requires_manifest(self):
        sm = c.BatchStateMachine()
        sm.transition(c.BatchState.CAPTURING, reason="start")
        with self.assertRaises(c.ContractViolation) as ctx:
            sm.transition(c.BatchState.CAPTURED, reason="无凭据")
        self.assertIn("manifest", str(ctx.exception))

    def test_capture_blocked_on_incomplete_pagination(self):
        sm = c.BatchStateMachine()
        sm.transition(c.BatchState.CAPTURING, reason="start")
        with self.assertRaises(c.ContractViolation) as ctx:
            sm.transition(
                c.BatchState.CAPTURED, reason="缺片",
                manifest=self._manifest_for_capture(complete=False),
            )
        self.assertIn("分页未完整", str(ctx.exception))

    def test_commit_unknown_flow(self):
        sm = c.BatchStateMachine()
        for state, kw in (
            (c.BatchState.CAPTURING, {}),
            (c.BatchState.CAPTURED, {"manifest": self._manifest_for_capture()}),
            (c.BatchState.VALIDATING, {}),
            (c.BatchState.VALIDATED, {}),
            (c.BatchState.APPLY_PENDING, {}),
            (c.BatchState.APPLYING, {}),
        ):
            sm.transition(state, reason="step", **kw)
        sm.transition(c.BatchState.COMMIT_UNKNOWN, reason="回执丢失")
        # 盲重放禁止：COMMIT_UNKNOWN 不能直接回 APPLYING
        with self.assertRaises(c.ContractViolation):
            sm.transition(c.BatchState.APPLYING, reason="盲重放")
        # 对账确认已提交 → APPLIED；确认回滚 → APPLY_PENDING
        sm.transition(c.BatchState.APPLIED, reason="对账确认已提交", evidence="receipt:xyz")
        sm.transition(c.BatchState.RECONCILED, reason="闭合")

    def test_cancelled_is_terminal(self):
        sm = c.BatchStateMachine()
        sm.transition(c.BatchState.CANCELLED, reason="人工取消")
        with self.assertRaises(c.ContractViolation):
            sm.transition(c.BatchState.PLANNED, reason="复活")

    def test_waiting_view_fix_only_from_capture_side(self):
        sm = c.BatchStateMachine(c.BatchState.VALIDATED)
        with self.assertRaises(c.ContractViolation):
            sm.transition(c.BatchState.WAITING_VIEW_FIX, reason="视图问题不发生在装载段")
        sm2 = c.BatchStateMachine(c.BatchState.CAPTURING)
        sm2.transition(c.BatchState.WAITING_VIEW_FIX, reason="SQL/视图错误")
        sm2.transition(c.BatchState.CAPTURING, reason="人工修好后恢复")


class TestFeedbackStateMachine(unittest.TestCase):
    def test_normal_chain(self):
        fb = c.FeedbackStateMachine()
        fb.transition(c.FeedbackState.SUBMITTED, reason="上报")
        fb.transition(c.FeedbackState.RECEIVED, reason="回执")
        fb.transition(c.FeedbackState.ACCEPTED, reason="通过")

    def test_not_submitted_cannot_be_accepted(self):
        fb = c.FeedbackStateMachine()
        with self.assertRaises(c.ContractViolation):
            fb.transition(c.FeedbackState.ACCEPTED, reason="未提交不可通过")

    def test_rejected_resubmit_only_new_version(self):
        fb = c.FeedbackStateMachine(c.FeedbackState.RECEIVED)
        fb.transition(c.FeedbackState.REJECTED, reason="省端拒绝")
        fb.transition(c.FeedbackState.SUBMITTED, reason="修正版本重传")


if __name__ == "__main__":
    unittest.main()
