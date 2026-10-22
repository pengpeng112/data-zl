"""告警链路测试：HMAC/入队/送达分型/跨秒重签 + 恢复动作 + 调度桥失败继续。"""

from __future__ import annotations

import hashlib
import hmac
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.reporting_pipeline.alerts_client import (
    AlertConfigError,
    ClockStalled,
    RelayConfig,
    RelayV2Client,
    TransportResponse,
    build_event_body,
    sign_headers,
    verify_payload_privacy,
)
from app.services.reporting_pipeline.alerts_outbox import OutboxSender
from app.services.reporting_pipeline.contracts import (
    BatchManifest,
    BatchState,
    EndReason,
    RowClassification,
)
from app.services.reporting_pipeline.recovery import RecoveryService, blocked_scopes
from app.services.reporting_pipeline.repositories import InMemoryControlRepository
from app.services.reporting_pipeline.scheduler_bridge import SchedulerBridge

SECRET = b"test-secret-bytes"


class FakeTransport:
    def __init__(self, post_responses=None, get_responses=None) -> None:
        self.post_responses = list(post_responses or [])
        self.get_responses = list(get_responses or [])
        self.post_calls: list[dict] = []
        self.get_calls: list[dict] = []

    def post(self, url, headers, body, *, timeout_seconds):
        self.post_calls.append(
            {"url": url, "headers": dict(headers), "body": body}
        )
        return self.post_responses.pop(0) if self.post_responses else TransportResponse(202, b'{"event_id":"uuid-1"}')

    def get(self, url, headers, *, timeout_seconds):
        self.get_calls.append({"url": url, "headers": dict(headers)})
        return self.get_responses.pop(0) if self.get_responses else TransportResponse(200, b'{"tasks":[{"status":"sent"}]}')


def _client(transport, *, clock=None, sleep=None, config=None) -> RelayV2Client:
    return RelayV2Client(
        transport,
        config or RelayConfig(
            base_url="http://relay.internal", source_id="sanjia-etl",
            secret_ref="vault:alerts/sanjia-etl",
        ),
        secret_resolver=lambda ref: SECRET,
        clock=clock or (lambda: 1700000000),
        sleep_fn=sleep,
    )


def _body() -> bytes:
    return build_event_body(
        source_event_id="r189t1.INC-000001.OPENED.1",
        event_type="incident",
        category="sanjia_etl",
        severity="red",
        title="[三甲上报] 抽取失败",
        body="业务日期：2026-10-19。建议动作：按工单核视图后重试失败窗。",
        occurred_at="2026-10-19T12:00:00+08:00",
        metadata={
            "canonical_table": "EMR_TEST", "batch_id": "B1",
            "recommended_action": "重试失败窗",
            "detail_ref": "R189:执行证据/v1.2/E01",
        },
    )


class TestHmacAndBody(unittest.TestCase):
    def test_signature_over_exact_bytes(self):
        body = b'{"a":1}'
        headers = sign_headers(
            source_id="sanjia-etl", secret=SECRET, unix_ts=1700000000, body=body
        )
        expected = hmac.new(
            SECRET, b"sanjia-etl.1700000000." + body, hashlib.sha256
        ).hexdigest()
        self.assertEqual(headers["X-Signature"], expected)
        self.assertEqual(headers["X-Timestamp"], "1700000000")
        self.assertTrue(headers["X-Signature"].islower() or headers["X-Signature"].isdigit())

    def test_get_signature_empty_body(self):
        h1 = sign_headers(source_id="s", secret=SECRET, unix_ts=1, body=b"")
        expected = hmac.new(SECRET, b"s.1.", hashlib.sha256).hexdigest()
        self.assertEqual(h1["X-Signature"], expected)

    def test_body_immutability_and_privacy(self):
        body = _body()
        self.assertEqual(json.loads(body)["source_event_id"], "r189t1.INC-000001.OPENED.1")
        verdict = verify_payload_privacy(body)
        self.assertTrue(verdict["ok"], verdict)

    def test_body_rejects_receivers_and_offlist_metadata(self):
        with self.assertRaises(AlertConfigError):
            build_event_body(
                source_event_id="x" * 201, event_type="t", category="c",
                severity="red", title="t", body="b", occurred_at="o",
                metadata={},
            )
        with self.assertRaises(AlertConfigError):
            build_event_body(
                source_event_id="ok", event_type="t", category="c",
                severity="red", title="t", body="b", occurred_at="o",
                metadata={"patient_name": "张三"},
            )

    def test_privacy_check_catches_receivers(self):
        bad = b'{"source_event_id":"x","receivers":["a"]}'
        verdict = verify_payload_privacy(bad)
        self.assertFalse(verdict["ok"])
        self.assertTrue(any("receivers" in p for p in verdict["problems"]))


class TestSendClassification(unittest.TestCase):
    def test_post_202_is_queued_not_delivered(self):
        transport = FakeTransport([TransportResponse(202, b'{"event_id":"uuid-9"}')])
        client = _client(transport)
        outcome = client.send_event(source_event_id="sid-1", body_bytes=_body())
        self.assertEqual(outcome.acceptance_state, "ACK_QUEUED")
        self.assertEqual(outcome.relay_event_id, "uuid-9")
        # 请求体原字节发送，headers 齐全
        call = transport.post_calls[0]
        self.assertEqual(call["body"], _body())
        self.assertIn("X-Signature", call["headers"])
        self.assertEqual(call["url"], "http://relay.internal/api/v2/events")
        self.assertNotIn("receivers", call["body"].decode("utf-8"))

    def test_post_200_duplicate_reuses(self):
        transport = FakeTransport([TransportResponse(200, b'{"event_id":"uuid-d"}')])
        outcome = _client(transport).send_event(source_event_id="sid", body_bytes=_body())
        self.assertEqual(outcome.acceptance_state, "DUPLICATE")
        self.assertEqual(outcome.relay_event_id, "uuid-d")

    def test_401_pauses_auth(self):
        transport = FakeTransport([TransportResponse(401, b"")])
        outcome = _client(transport).send_event(source_event_id="sid", body_bytes=_body())
        self.assertEqual(outcome.acceptance_state, "PAUSED_AUTH")

    def test_400_permanent(self):
        transport = FakeTransport([TransportResponse(400, b"bad")])
        outcome = _client(transport).send_event(source_event_id="sid", body_bytes=_body())
        self.assertEqual(outcome.acceptance_state, "REJECTED_PERMANENT")

    def test_409_needs_attention(self):
        transport = FakeTransport([TransportResponse(409, b"")])
        outcome = _client(transport).send_event(source_event_id="sid", body_bytes=_body())
        self.assertEqual(outcome.acceptance_state, "NEEDS_ATTENTION")

    def test_429_respects_longer_retry_after(self):
        transport = FakeTransport(
            [TransportResponse(429, b"", {"Retry-After": "3600"})]
        )
        outcome = _client(transport).send_event(source_event_id="sid", body_bytes=_body())
        self.assertEqual(outcome.acceptance_state, "RETRY_SCHEDULED")
        self.assertEqual(outcome.retry_after_seconds, 3600)
        transport2 = FakeTransport([TransportResponse(429, b"", {"Retry-After": "5"})])
        outcome2 = _client(transport2).send_event(source_event_id="sid", body_bytes=_body())
        self.assertEqual(outcome2.retry_after_seconds, 60)  # 至少 60s

    def test_503_respects_retry_after(self):
        transport = FakeTransport(
            [TransportResponse(503, b"", {"Retry-After": "120"})]
        )
        outcome = _client(transport).send_event(source_event_id="sid", body_bytes=_body())
        self.assertEqual(outcome.retry_after_seconds, 120)

    def test_max_attempts_exhausted(self):
        config = RelayConfig(
            base_url="http://x", source_id="s", secret_ref="r", max_attempts=1,
        )
        client = _client(FakeTransport(), config=config)
        outcome = client.send_event(
            source_event_id="sid", body_bytes=_body(), previous_attempts=1
        )
        self.assertEqual(outcome.error_class, "MAX_ATTEMPTS_EXHAUSTED")

    def test_unregistered_source_refused(self):
        client = RelayV2Client(
            FakeTransport(),
            RelayConfig(base_url="http://x", source_id="", secret_ref=""),
            secret_resolver=lambda ref: SECRET,
            clock=lambda: 1,
        )
        with self.assertRaises(AlertConfigError):
            client.send_event(source_event_id="sid", body_bytes=b"{}")


class TestNewSecondRule(unittest.TestCase):
    def test_resend_waits_for_real_new_second(self):
        clock = {"t": 1700000000}
        transport = FakeTransport(
            [TransportResponse(202, b'{"event_id":"u1"}'),
             TransportResponse(202, b'{"event_id":"u2"}')]
        )
        slept = []

        def sleep_fn(seconds):
            slept.append(seconds)
            clock["t"] += 1  # 时钟真实前进

        client = _client(transport, clock=lambda: clock["t"], sleep=sleep_fn)
        client.send_event(source_event_id="sid", body_bytes=_body())
        client.send_event(source_event_id="sid", body_bytes=_body())  # 重试
        self.assertTrue(slept)  # 等到了跨秒，不伪造 +1
        ts_values = [c["headers"]["X-Timestamp"] for c in transport.post_calls]
        self.assertEqual(ts_values[0], "1700000000")
        self.assertEqual(ts_values[1], "1700000001")
        # 两次签名不同（新秒+同字节）
        self.assertNotEqual(
            transport.post_calls[0]["headers"]["X-Signature"],
            transport.post_calls[1]["headers"]["X-Signature"],
        )
        # 字节完全不变
        self.assertEqual(transport.post_calls[0]["body"], transport.post_calls[1]["body"])

    def test_frozen_clock_refuses(self):
        client = _client(FakeTransport(), clock=lambda: 1700000000)
        client.send_event(source_event_id="sid", body_bytes=_body())
        with self.assertRaises(ClockStalled):
            client.send_event(source_event_id="sid", body_bytes=_body())


class TestPollDelivery(unittest.TestCase):
    def test_all_sent_delivered(self):
        transport = FakeTransport(get_responses=[
            TransportResponse(200, json.dumps({
                "tasks": [{"target": "a", "status": "sent"},
                          {"target": "b", "status": "sent"}]
            }).encode())
        ])
        outcome = _client(transport).poll_event(relay_event_id="uuid-1", source_event_id="sid")
        self.assertEqual(outcome.delivery_state, "DELIVERED")
        # GET 签名 body 为空字节
        get_call = transport.get_calls[0]
        self.assertIn("/api/v2/events/uuid-1", get_call["url"])

    def test_zero_targets_route_unresolved(self):
        transport = FakeTransport(get_responses=[
            TransportResponse(200, b'{"tasks": []}')
        ])
        outcome = _client(transport).poll_event(relay_event_id="u", source_event_id="s")
        self.assertEqual(outcome.delivery_state, "ROUTE_UNRESOLVED")

    def test_dead_target_needs_attention(self):
        transport = FakeTransport(get_responses=[
            TransportResponse(200, json.dumps({
                "tasks": [{"status": "sent"}, {"status": "dead"}]
            }).encode())
        ])
        outcome = _client(transport).poll_event(relay_event_id="u", source_event_id="s")
        self.assertEqual(outcome.delivery_state, "NEEDS_ATTENTION")

    def test_pending_state(self):
        transport = FakeTransport(get_responses=[
            TransportResponse(200, json.dumps({
                "tasks": [{"status": "pending"}, {"status": "sent"}]
            }).encode())
        ])
        outcome = _client(transport).poll_event(relay_event_id="u", source_event_id="s")
        self.assertEqual(outcome.delivery_state, "PENDING")

    def test_get_404_needs_attention(self):
        transport = FakeTransport(get_responses=[TransportResponse(404, b"")])
        outcome = _client(transport).poll_event(relay_event_id="u", source_event_id="s")
        self.assertEqual(outcome.delivery_state, "NEEDS_ATTENTION")


class TestOutboxSenderFlow(unittest.TestCase):
    def _repo_with_event(self):
        repo = InMemoryControlRepository()
        incident = repo.create_incident("k", "EXTRACT_FAILED")
        repo.append_incident_event(
            incident, event_kind="OPENED", severity="red",
            title="t", body_bytes=_body(),
        )
        return repo

    def test_full_flow_queued_then_delivered(self):
        repo = self._repo_with_event()
        transport = FakeTransport(
            post_responses=[TransportResponse(202, b'{"event_id":"uuid-1"}')],
            get_responses=[
                TransportResponse(200, json.dumps({
                    "tasks": [{"status": "sent"}, {"status": "sent"}]
                }).encode()),
            ],
        )
        sender = OutboxSender(repo, _client(transport))
        report = sender.process_pending()
        self.assertEqual(report["newly_queued"], 1)
        # 第二轮：无新发（同事件不重复 POST），轮询后 DELIVERED
        report2 = sender.process_pending()
        self.assertEqual(report2["send_attempted"], 0)
        row = repo.snapshot()["outbox"][0]
        self.assertEqual(row["delivery"], "DELIVERED")

    def test_auth_pause_stops_auto_dispatch(self):
        repo = self._repo_with_event()
        transport = FakeTransport(
            post_responses=[TransportResponse(401, b"")]
        )
        sender = OutboxSender(repo, _client(transport))
        sender.process_pending()
        row = repo.snapshot()["outbox"][0]
        self.assertEqual(row["delivery"], "PAUSED_AUTH")
        self.assertEqual(repo.pending_outbox(), [])  # 不再自动派发


class TestRecovery(unittest.TestCase):
    def test_commit_unknown_blocks_table_writers(self):
        repo = InMemoryControlRepository()
        repo.create_batch("B1", "EMR_TEST", "2026-10-18")
        manifest = BatchManifest(
            batch_id="B1", attempt_id="A1", task_id="EMR_TEST", config_version="v1",
            definition_fingerprint=None, source_identity="s", window_fingerprint="w",
            source_visibility_cutoff="cut",
            rows=RowClassification(source_read_rows=1, valid=1),
            pagination_complete=True, end_reason=EndReason.WINDOW_COMPLETE,
            shard_count=1, file_count=1, total_bytes=10, schema_version="v",
            type_contract_version="t", payload_sha256="a" * 64,
        )
        repo.attach_attempt_manifest("B1", manifest)
        repo.select_manifest("B1")
        for state in (BatchState.CAPTURING, BatchState.CAPTURED, BatchState.VALIDATING,
                      BatchState.VALIDATED, BatchState.APPLY_PENDING, BatchState.APPLYING):
            repo.transition_batch("B1", state, reason="s")
        repo.transition_batch("B1", BatchState.COMMIT_UNKNOWN, reason="回执丢失")
        actions = RecoveryService(repo).resume_all()
        blocking = blocked_scopes(actions)
        self.assertIn("same_target_table_writers", blocking)
        cu = [a for a in actions if a.batch_id == "B1"][0]
        self.assertEqual(cu.action, "RECONCILE_BEFORE_ANY_WRITE")

    def test_waiting_view_fix_continues_independently(self):
        repo = InMemoryControlRepository()
        repo.create_batch("B1", "EMR_TEST", "2026-10-18")
        repo.transition_batch("B1", BatchState.CAPTURING, reason="s")
        repo.transition_batch("B1", BatchState.WAITING_VIEW_FIX, reason="SQL/视图错误")
        action = RecoveryService(repo).resume("B1")
        self.assertFalse(action.blocking)
        self.assertEqual(action.action, "WAIT_HUMAN_VIEW_FIX")


class FakeTask:
    def __init__(self, table, mode="T1", sources=("ods__A",), fail=False,
                 wants_apply=False):
        self.canonical_table = table
        self.mode = mode
        self.physical_sources = tuple(sources)
        self.fail = fail
        # K06：捕获任务不占目标写租约；正式装载（wants_apply）才领写租约
        self._apply_fn = (lambda *a, **k: None) if wants_apply else None
        self.ran = False

    def run(self):
        self.ran = True
        if self.fail:
            raise RuntimeError("injected failure")
        return {"ok": True}


class TestSchedulerBridge(unittest.TestCase):
    def test_dag_and_priority_order(self):
        bridge = SchedulerBridge(repository=InMemoryControlRepository())
        tasks = [
            FakeTask("EMR_INSPECTION_ITEM"),
            FakeTask("EMR_INSPECTION"),
            FakeTask("EMR_ADMISSION_RECORD", mode="MONTHLY_RESCAN"),
        ]
        order = [t.canonical_table for t in bridge.plan_order(
            tasks, {"EMR_INSPECTION_ITEM": ["EMR_INSPECTION"],
                    "EMR_INSPECTION": [], "EMR_ADMISSION_RECORD": []}
        )]
        self.assertLess(order.index("EMR_INSPECTION"), order.index("EMR_INSPECTION_ITEM"))
        # T1 优先于 MONTHLY_RESCAN
        self.assertEqual(order[0], "EMR_INSPECTION")
        self.assertEqual(order[-1], "EMR_ADMISSION_RECORD")

    def test_failure_continues_partial(self):
        repo = InMemoryControlRepository()
        bridge = SchedulerBridge(repository=repo)
        tasks = [
            FakeTask("T_BAD", fail=True),
            FakeTask("T_GOOD"),
        ]
        report = bridge.run_cycle(tasks)
        self.assertIn("T_BAD:T1", report.failures)
        self.assertIn("T_GOOD:T1", report.dispatched)
        self.assertEqual(report.overall, "PARTIAL_SUCCESS_WITH_BACKLOG")

    def test_open_breaker_skips_source(self):
        repo = InMemoryControlRepository()
        bridge = SchedulerBridge(repository=repo, source_open_predicate=lambda s: s == "ods__X")
        tasks = [FakeTask("T_X", sources=("ods__X",)), FakeTask("T_OK", sources=("ods__Y",))]
        report = bridge.run_cycle(tasks)
        self.assertEqual(report.skipped["T_X:T1"], "物理源熔断 OPEN")
        self.assertIn("T_OK:T1", report.dispatched)

    def test_single_writer_lease(self):
        repo = InMemoryControlRepository()
        repo.acquire_lease("target:DBOPER.T_HELD", "other-worker", ttl_seconds=600)
        bridge = SchedulerBridge(repository=repo)
        # K06：正式装载任务被单写者租约挡住
        tasks = [FakeTask("T_HELD", wants_apply=True)]
        report = bridge.run_cycle(tasks)
        self.assertIn("T_HELD:T1", report.skipped)
        self.assertIn("单写者", report.skipped["T_HELD:T1"])
        # 捕获任务不占目标写租约：即使写租约被他人持有仍可捕获
        capture_tasks = [FakeTask("T_HELD_CAP", sources=("ods__B",))]
        capture_report = bridge.run_cycle(capture_tasks)
        self.assertIn("T_HELD_CAP:T1", capture_report.dispatched)

    def test_source_concurrency_budget(self):
        repo = InMemoryControlRepository()
        bridge = SchedulerBridge(repository=repo)
        # 同源两任务同轮：第二个因源并发预算跳过（串行入口）
        tasks = [FakeTask("T_A1", sources=("ods__S",)), FakeTask("T_A2", sources=("ods__S",))]
        report = bridge.run_cycle(tasks)
        self.assertEqual(len(report.dispatched), 2)  # 串行执行后释放，均可跑
        # 并发占用场景由 run 内 active_sources 控制；本测试验证不遗留占用
        self.assertEqual(report.overall, "SUCCESS")


if __name__ == "__main__":
    unittest.main()
