"""纯逻辑维护回归：持久状态推进、日报日粒度与调度租约续期。"""

from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# Importing PG model declarations initializes the app engine and therefore
# requires an explicitly named test database URL. This local test-only SQLite
# URL is used only to construct the unused engine; all repository calls inject
# fake sessions and never connect or create the file.
_old_test_db_url = os.environ.get("APP_TEST_DB_URL")
_old_app_db_url = os.environ.get("APP_DB_URL")
_pure_logic_db_url = "sqlite:///data_asset_test_pure_logic.db"
os.environ["APP_TEST_DB_URL"] = _pure_logic_db_url
os.environ["APP_DB_URL"] = _pure_logic_db_url


def _load_app_modules():
    from app.services.reporting_pipeline.contracts import BatchState, FeedbackState
    from app.services.reporting_pipeline.pg_repository import SqlAlchemyControlRepository
    from app.services.reporting_pipeline.reports import build_daily_report
    from app.services.reporting_pipeline.repositories import InMemoryControlRepository
    from app.services.reporting_pipeline.seed_loader import _task_spec_from_seed
    from app.services.reporting_pipeline.scheduler_bridge import SchedulerBridge

    return (
        BatchState,
        FeedbackState,
        SqlAlchemyControlRepository,
        build_daily_report,
        InMemoryControlRepository,
        _task_spec_from_seed,
        SchedulerBridge,
    )


(
    BatchState,
    FeedbackState,
    SqlAlchemyControlRepository,
    build_daily_report,
    InMemoryControlRepository,
    _task_spec_from_seed,
    SchedulerBridge,
) = _load_app_modules()

if _old_test_db_url is None:
    os.environ.pop("APP_TEST_DB_URL", None)
else:
    os.environ["APP_TEST_DB_URL"] = _old_test_db_url
if _old_app_db_url is None:
    os.environ.pop("APP_DB_URL", None)
else:
    os.environ["APP_DB_URL"] = _old_app_db_url


class _ScalarResult:
    def __init__(self, value=None):
        self.value = value

    def scalar_one_or_none(self):
        return self.value

    def scalars(self):
        return self

    def all(self):
        return []


class _FakeSession:
    """只回放 PG repository 使用的 execute/transaction 接口，不连接数据库。"""

    def __init__(self, row):
        self.row = row
        self.calls = 0

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def begin(self):
        return self

    def execute(self, _statement):
        self.calls += 1
        # transition_batch: require row, load row, then load attempts.
        if self.calls <= 2:
            return _ScalarResult(self.row)
        return _ScalarResult()


class _FakeSessionFactory:
    def __init__(self, row):
        self.row = row

    def __call__(self):
        return _FakeSession(self.row)


class TestPersistedTransitions(unittest.TestCase):
    def _repo(self, *, state, feedback=FeedbackState.NOT_SUBMITTED):
        row = SimpleNamespace(
            batch_id="b1",
            canonical_table="TABLE_A",
            business_day=datetime(2026, 10, 21).date(),
            state=state.value,
            feedback_state=feedback.value,
            target_instance="db",
            tenant="org",
            target_table="TABLE_A",
            selected_attempt_id=None,
            state_history=[],
            updated_at=None,
        )
        return SqlAlchemyControlRepository(_FakeSessionFactory(row)), row

    def test_batch_transition_starts_from_durable_state(self):
        repo, row = self._repo(state=BatchState.CAPTURED)
        state = repo.transition_batch(
            "b1", BatchState.VALIDATING, reason="resume after process restart"
        )
        self.assertEqual(state, BatchState.VALIDATING)
        self.assertEqual(row.state, BatchState.VALIDATING.value)

    def test_batch_transition_rejects_regression_from_durable_state(self):
        repo, row = self._repo(state=BatchState.APPLIED)
        with self.assertRaises(Exception):
            repo.transition_batch("b1", BatchState.CAPTURING, reason="invalid rollback")
        self.assertEqual(row.state, BatchState.APPLIED.value)

    def test_feedback_transition_starts_from_durable_state(self):
        repo, row = self._repo(
            state=BatchState.RECONCILED, feedback=FeedbackState.SUBMITTED
        )
        state = repo.transition_feedback(
            "b1", FeedbackState.RECEIVED, reason="receipt readback"
        )
        self.assertEqual(state, FeedbackState.RECEIVED)
        self.assertEqual(row.feedback_state, FeedbackState.RECEIVED.value)


class _TaskStub:
    def __init__(self, table, *, sources=(), run_fn=None, apply=False):
        self.canonical_table = table
        self.mode = "T1"
        self.physical_sources = tuple(sources)
        self.target_resource = f"target:db.org.{table}"
        self._run_fn = run_fn
        self._apply_fn = object() if apply else None

    def run(self, context=None):
        if self._run_fn:
            return self._run_fn(context)
        return {"ok": True}


class _KeywordOnlyTask(_TaskStub):
    def run(self, *, context):
        self.received_context = context
        return {"ok": True}


class _LeaseSpyRepository(InMemoryControlRepository):
    def __init__(self):
        super().__init__()
        self.renewed = []

    def renew_lease(self, resource, holder, fencing_token, *, ttl_seconds=3600):
        self.renewed.append((resource, ttl_seconds))
        return super().renew_lease(
            resource, holder, fencing_token, ttl_seconds=ttl_seconds
        )


class TestSchedulerMaintenance(unittest.TestCase):
    def test_keyword_only_context_signature_is_invoked_by_keyword(self):
        task = _KeywordOnlyTask("TABLE_K")
        report = SchedulerBridge(
            repository=InMemoryControlRepository()
        ).run_cycle([task])
        self.assertEqual(report.overall, "SUCCESS")
        self.assertIsNotNone(task.received_context)

    def test_renew_callback_renews_all_read_and_write_leases_with_own_ttls(self):
        repo = _LeaseSpyRepository()
        bridge = SchedulerBridge(
            repository=repo,
            lease_ttl_seconds=91,
            read_lease_ttl_seconds=17,
        )
        task = _TaskStub("TABLE_M", sources=("SRC_A", "SRC_B"), apply=True)
        task._run_fn = lambda context: (context.renew(), {"ok": True})[1]

        report = bridge.run_cycle([task])

        self.assertEqual(report.overall, "SUCCESS")
        self.assertEqual(
            repo.renewed,
            [("read:SRC_A", 17), ("read:SRC_B", 17),
             ("target:db.org.TABLE_M", 91)],
        )


class _ReportTask:
    def __init__(self, table):
        self.canonical_table = table
        self.applicability = SimpleNamespace(value="TO_VERIFY")
        self.associations = SimpleNamespace(
            deadline_state=SimpleNamespace(value="UNCONFIGURED")
        )


class _ReportBundle:
    def __init__(self):
        self.tasks = [_ReportTask("TABLE_R")]

    def rescan_tasks(self):
        return []


class TestDailyReportMaintenance(unittest.TestCase):
    def test_per_table_daily_counts_filter_to_requested_business_day(self):
        repo = InMemoryControlRepository()
        repo.create_batch("b-old", "TABLE_R", "2026-10-20")
        repo.create_batch("b-day", "TABLE_R", "2026-10-21")

        report = build_daily_report(
            business_day="2026-10-21", repository=repo, bundle=_ReportBundle()
        ).to_dict()

        self.assertEqual(report["per_table_daily"]["TABLE_R"]["batches"], 1)

    def test_daily_table_missing_from_snapshot_is_still_reported(self):
        repo = InMemoryControlRepository()
        repo.create_batch("b-day", "TABLE_R", "2026-10-21")
        original_snapshot = repo.snapshot
        repo.snapshot = lambda: {**original_snapshot(), "per_table": {}}

        report = build_daily_report(
            business_day="2026-10-21", repository=repo, bundle=_ReportBundle()
        ).to_dict()

        self.assertEqual(report["per_table_daily"]["TABLE_R"]["batches"], 1)
        self.assertIsNone(report["per_table_daily"]["TABLE_R"]["earliest_open_gap"])

    def test_unresolved_quarantine_prevents_success_status(self):
        repo = InMemoryControlRepository()
        record = repo.create_batch("b-quarantine", "TABLE_R", "2026-10-21")
        record.state = BatchState.QUARANTINED

        report = build_daily_report(
            business_day="2026-10-21", repository=repo, bundle=_ReportBundle()
        ).to_dict()

        self.assertEqual(report["overall"], "PARTIAL_SUCCESS_WITH_BACKLOG")
        self.assertEqual(report["per_table_daily"]["TABLE_R"]["quarantined"], 1)
        self.assertEqual(len(report["unresolved_group_batches"]), 1)


class TestSeedTaskSpecRoundTrip(unittest.TestCase):
    def test_config_fields_are_loaded_without_enabling_candidate(self):
        item = {
            "canonical_table": "TABLE_SEED",
            "enabled": False,
            "config_version": "cfg-2026-10",
            "projection": [
                {
                    "name": "ID",
                    "target_type": "VARCHAR2(32)",
                    "order": 1,
                    "source_expression": "SRC.ID",
                    "type_verified": True,
                }
            ],
            "time_semantics": {
                "visibility_cutoff_rule": "MAX_VISIBLE_AT",
                "same_second_cursor_rule": "KEYSET_TIE_BREAKER",
            },
            "change_policy": {
                "child_only_change_trigger": ["CHILD.MODIFIED_AT"],
            },
            "resource_budget": {
                "per_source_concurrency": 1,
                "max_attempts": 4,
                "max_elapsed_seconds": 7200,
            },
            "apply_policy": {
                "executor_ref": "apply:TABLE_SEED",
                "allowed_operations": ["INSERT"],
                "idempotency_key": ["ID"],
                "txn_row_budget": 500,
                "txn_byte_budget": 100000,
                "commit_receipt_mode": "SAME_TARGET_TXN",
                "approval_refs": ["approval:sample"],
            },
        }

        spec = _task_spec_from_seed(item)

        self.assertFalse(spec.enabled)
        self.assertEqual(spec.config_version, "cfg-2026-10")
        self.assertEqual(spec.projection[0].source_expression, "SRC.ID")
        self.assertTrue(spec.projection[0].type_verified)
        self.assertEqual(spec.time_semantics.visibility_cutoff_rule, "MAX_VISIBLE_AT")
        self.assertEqual(
            spec.time_semantics.same_second_cursor_rule, "KEYSET_TIE_BREAKER"
        )
        self.assertEqual(
            spec.change_policy.child_only_change_trigger, ["CHILD.MODIFIED_AT"]
        )
        self.assertEqual(spec.resource_budget.per_source_concurrency, 1)
        self.assertEqual(spec.resource_budget.max_attempts, 4)
        self.assertEqual(spec.resource_budget.max_elapsed_seconds, 7200)
        self.assertEqual(spec.apply_policy.executor_ref, "apply:TABLE_SEED")
        self.assertEqual(spec.apply_policy.allowed_operations, ["INSERT"])
        self.assertEqual(spec.apply_policy.idempotency_key, ["ID"])
        self.assertEqual(spec.apply_policy.txn_row_budget, 500)
        self.assertEqual(spec.apply_policy.txn_byte_budget, 100000)
        self.assertEqual(spec.apply_policy.commit_receipt_mode, "SAME_TARGET_TXN")
        self.assertEqual(spec.apply_policy.approval_refs, ["approval:sample"])


if __name__ == "__main__":
    unittest.main()
