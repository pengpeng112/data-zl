"""控制状态仓储测试：水位缺口门禁、attempt 隔离、fencing 租约、不可变 outbox。"""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.reporting_pipeline.contracts import (
    BatchManifest,
    BatchState,
    ContractViolation,
    EndReason,
    FeedbackState,
    RowClassification,
)
from app.services.reporting_pipeline.planner import MonthCoverageRecord, TimeWindow
from app.services.reporting_pipeline.repositories import (
    InMemoryControlRepository,
    LeaseDenied,
)

NOW = datetime(2026, 10, 19, 12, 0, 0, tzinfo=timezone.utc)


def fixed_clock():
    current = {"t": NOW}
    return lambda: current["t"], current


def _manifest(batch: str, attempt: str, *, complete: bool = True, rows_read: int = 5) -> BatchManifest:
    return BatchManifest(
        batch_id=batch,
        attempt_id=attempt,
        task_id="EMR_TEST",
        config_version="v1",
        definition_fingerprint=None,
        source_identity="ods__V",
        window_fingerprint="win:a/b",
        source_visibility_cutoff="2026-10-19T02:00:00+08:00",
        rows=RowClassification(
            source_read_rows=rows_read,
            valid=rows_read - 1,
            quarantined=1 if rows_read else 0,
        ),
        pagination_complete=complete,
        end_reason=EndReason.WINDOW_COMPLETE if complete else EndReason.ROW_CAP,
        shard_count=1,
        file_count=1,
        total_bytes=100,
        schema_version="V1.3",
        type_contract_version="tc",
        payload_sha256="a" * 64,
    )


class TestWatermarkGapGate(unittest.TestCase):
    def setUp(self):
        self.repo = InMemoryControlRepository(now_fn=lambda: NOW)

    def test_gap_blocks_capture_watermark(self):
        """10-03 窗失败继续 10-04：水位不得越过未闭合缺口。"""
        gap = self.repo.record_gap(
            "EMR_TEST",
            TimeWindow(datetime(2026, 10, 3), datetime(2026, 10, 4)),
            reason="视图错误",
        )
        with self.assertRaises(ContractViolation) as ctx:
            self.repo.advance_capture_watermark(
                "EMR_TEST", datetime(2026, 10, 5, tzinfo=timezone.utc)
            )
        self.assertIn("未闭合缺口", str(ctx.exception))
        # 闭合缺口（人工修好后补抽完成）才能推进
        self.repo.close_gap(gap.gap_id, evidence="补抽完成+manifest 核对")
        self.repo.advance_capture_watermark("EMR_TEST", datetime(2026, 10, 5, tzinfo=timezone.utc))
        self.assertEqual(
            self.repo.get_watermarks("EMR_TEST").capture_h,
            datetime(2026, 10, 5, tzinfo=timezone.utc),
        )

    def test_watermarks_independent(self):
        self.repo.advance_capture_watermark("T", datetime(2026, 10, 19, tzinfo=timezone.utc))
        # 装载/反馈游标独立推进，不随捕获自动走
        self.assertIsNone(self.repo.get_watermarks("T").apply_cursor)
        self.repo.advance_apply_cursor("T", datetime(2026, 10, 19, 3, tzinfo=timezone.utc))
        self.repo.advance_delivery_cursor("T", datetime(2026, 10, 19, 5, tzinfo=timezone.utc))
        with self.assertRaises(ContractViolation):
            self.repo.advance_apply_cursor("T", datetime(2026, 10, 18, tzinfo=timezone.utc))


class TestAttemptIsolation(unittest.TestCase):
    def test_partial_attempt_not_selected(self):
        repo = InMemoryControlRepository(now_fn=lambda: NOW)
        repo.create_batch("B1", "EMR_TEST", "2026-10-18")
        repo.attach_attempt_manifest("B1", _manifest("B1", "A1", complete=False))
        with self.assertRaises(ContractViolation) as ctx:
            repo.select_manifest("B1")
        self.assertIn("无完整 attempt", str(ctx.exception))
        repo.attach_attempt_manifest("B1", _manifest("B1", "A2", complete=True))
        chosen = repo.select_manifest("B1")
        self.assertEqual(chosen.attempt_id, "A2")

    def test_old_attempt_does_not_override_new(self):
        """旧 stage 不能覆盖新内容：始终选最新完整 attempt。"""
        repo = InMemoryControlRepository(now_fn=lambda: NOW)
        repo.create_batch("B1", "EMR_TEST", "2026-10-18")
        repo.attach_attempt_manifest("B1", _manifest("B1", "A9", complete=True))
        repo.attach_attempt_manifest("B1", _manifest("B1", "A3", complete=True))
        self.assertEqual(repo.select_manifest("B1").attempt_id, "A9")


class TestLeaseFencing(unittest.TestCase):
    def setUp(self):
        _, self.clock = fixed_clock()
        self.repo = InMemoryControlRepository(now_fn=lambda: self.clock["t"])

    def test_exclusive_and_renew(self):
        lease = self.repo.acquire_lease("target:DBOPER.T", "worker-1", ttl_seconds=600)
        with self.assertRaises(LeaseDenied):
            self.repo.acquire_lease("target:DBOPER.T", "worker-2", ttl_seconds=600)
        self.repo.renew_lease("target:DBOPER.T", "worker-1", lease.fencing_token)
        self.repo.validate_fencing("target:DBOPER.T", lease.fencing_token)

    def test_expired_lease_new_token_but_old_fence_fails(self):
        """租约过期允许新 worker 接管（新 token），但旧 token 围栏校验失败。"""
        old = self.repo.acquire_lease("target:DBOPER.T", "worker-1", ttl_seconds=60)
        self.clock["t"] += timedelta(seconds=120)  # 过期
        new = self.repo.acquire_lease("target:DBOPER.T", "worker-2", ttl_seconds=600)
        self.assertGreater(new.fencing_token, old.fencing_token)
        with self.assertRaises(LeaseDenied):
            self.repo.validate_fencing("target:DBOPER.T", old.fencing_token)
        with self.assertRaises(LeaseDenied):
            self.repo.renew_lease("target:DBOPER.T", "worker-1", old.fencing_token)

    def test_same_holder_reacquires_after_expiry(self):
        self.repo.acquire_lease("r", "w1", ttl_seconds=60)
        self.clock["t"] += timedelta(seconds=120)
        again = self.repo.acquire_lease("r", "w1", ttl_seconds=60)
        self.assertEqual(again.holder, "w1")


class TestAlertIncidentOutbox(unittest.TestCase):
    def setUp(self):
        self.repo = InMemoryControlRepository(now_fn=lambda: NOW)

    def test_incident_aggregation_same_key(self):
        first = self.repo.create_incident(
            "env|EMR_TEST|EXTRACT_FAILED|2026-10-18",
            "EXTRACT_FAILED",
            affected_tables=["EMR_TEST"],
        )
        again = self.repo.create_incident(
            "env|EMR_TEST|EXTRACT_FAILED|2026-10-18",
            "EXTRACT_FAILED",
        )
        self.assertEqual(first.incident_id, again.incident_id)

    def test_immutable_body_and_new_revision(self):
        inc = self.repo.create_incident("k", "EXTRACT_FAILED")
        ev1 = self.repo.append_incident_event(
            inc, event_kind="OPENED", severity="yellow",
            title="t", body_bytes=b'{"a":1}',
        )
        # 同 revision 重放：同 ID 同字节 → 幂等返回既有事件，不加版本
        ev1b = self.repo.append_incident_event(
            inc, event_kind="OPENED", severity="yellow",
            title="t", body_bytes=b'{"a":1}',
        )
        self.assertEqual(ev1.source_event_id, ev1b.source_event_id)
        self.assertEqual(ev1b.revision, 1)
        # 同 revision 重放但换字节 → 契约违背（不得改内容）
        with self.assertRaises(ContractViolation):
            self.repo.append_incident_event(
                inc, event_kind="OPENED", severity="yellow",
                title="t", body_bytes=b'{"a":1,"patched":true}',
            )
        # 升级：新 revision 新 ID，原事件字节保持不变
        ev2 = self.repo.append_incident_event(
            inc, event_kind="ESCALATED", severity="red",
            title="t", body_bytes=b'{"a":2}',
        )
        self.assertNotEqual(ev1.source_event_id, ev2.source_event_id)
        self.assertEqual(ev2.revision, 2)
        self.assertEqual(
            self.repo.get_outbox_event(ev1.source_event_id).immutable_body_bytes,
            b'{"a":1}',
        )

    def test_recovered_new_event_not_mutation(self):
        inc = self.repo.create_incident("k2", "SOURCE_LATE")
        self.repo.append_incident_event(
            inc, event_kind="OPENED", severity="yellow", title="t", body_bytes=b"b1"
        )
        ev = self.repo.append_incident_event(
            inc, event_kind="RECOVERED", severity="blue", title="t", body_bytes=b"b2"
        )
        self.assertEqual(inc.state, "RECOVERED")
        self.assertEqual(ev.revision, 2)

    def test_delivery_state_tracking(self):
        inc = self.repo.create_incident("k3", "COMMIT_UNKNOWN")
        ev = self.repo.append_incident_event(
            inc, event_kind="OPENED", severity="red", title="t", body_bytes=b"b"
        )
        # POST 202：只入队不送达，转轮询队列（不再重复 POST）
        self.repo.update_outbox_delivery(
            ev.source_event_id, acceptance_state="ACK_QUEUED",
            relay_event_id="uuid-1", delivery_state="NOT_SENT",
            attempts_increment=1,
        )
        self.assertEqual(self.repo.pending_outbox(), [])
        self.assertEqual(
            self.repo.queued_outbox(),
            [self.repo.get_outbox_event(ev.source_event_id)],
        )
        self.repo.update_outbox_delivery(
            ev.source_event_id,
            delivery_state="DELIVERED",
            target_status_summary={"target_a": "sent", "target_b": "sent"},
        )
        self.assertEqual(self.repo.pending_outbox(), [])
        self.assertEqual(self.repo.queued_outbox(), [])
        self.assertEqual(
            self.repo.get_outbox_event(ev.source_event_id).target_status_summary,
            {"target_a": "sent", "target_b": "sent"},
        )

    def test_401_pauses_auth(self):
        inc = self.repo.create_incident("k4", "ALERT_DELIVERY_FAILED")
        ev = self.repo.append_incident_event(
            inc, event_kind="OPENED", severity="red", title="t", body_bytes=b"b"
        )
        self.repo.update_outbox_delivery(
            ev.source_event_id, delivery_state="PAUSED_AUTH",
            last_http_code=401, attempts_increment=1,
        )
        # 暂停后不进待发清单
        self.assertEqual(self.repo.pending_outbox(), [])


class TestMonthLedgerRepo(unittest.TestCase):
    def test_overdue_months_query(self):
        repo = InMemoryControlRepository(now_fn=lambda: NOW)
        repo.upsert_month_coverage(
            MonthCoverageRecord(
                table="EMR_DOC_ORDER_CHECK", business_month="2025-03",
                route_or_origin="ods",
                last_reconciled_at=NOW - timedelta(days=45), cycle_days=30,
            )
        )
        repo.upsert_month_coverage(
            MonthCoverageRecord(
                table="EMR_DOC_ORDER_CHECK", business_month="2025-04",
                route_or_origin="ods",
            )
        )
        overdue = repo.overdue_months("EMR_DOC_ORDER_CHECK")
        self.assertEqual({r.business_month for r in overdue}, {"2025-03", "2025-04"})


class TestBatchFlowRepo(unittest.TestCase):
    def test_full_flow_with_commit_unknown_freeze(self):
        repo = InMemoryControlRepository(now_fn=lambda: NOW)
        repo.create_batch("B1", "EMR_TEST", "2026-10-18")
        repo.attach_attempt_manifest("B1", _manifest("B1", "A1"))
        repo.select_manifest("B1")
        for state in (BatchState.CAPTURING, BatchState.CAPTURED, BatchState.VALIDATING,
                      BatchState.VALIDATED, BatchState.APPLY_PENDING, BatchState.APPLYING):
            repo.transition_batch("B1", state, reason="step")
        repo.transition_batch("B1", BatchState.COMMIT_UNKNOWN, reason="回执丢失")
        with self.assertRaises(ContractViolation):
            repo.transition_batch("B1", BatchState.APPLYING, reason="盲重放")
        repo.transition_batch(
            "B1", BatchState.APPLIED, reason="对账确认已提交", evidence="receipt:1"
        )
        repo.transition_batch("B1", BatchState.RECONCILED, reason="闭合")
        # 反馈链独立
        repo.transition_feedback("B1", FeedbackState.SUBMITTED, reason="上报")
        snap = repo.snapshot()
        self.assertEqual(snap["batches"]["B1"]["state"], "RECONCILED")
        self.assertEqual(snap["batches"]["B1"]["feedback"], "SUBMITTED")


if __name__ == "__main__":
    unittest.main()
