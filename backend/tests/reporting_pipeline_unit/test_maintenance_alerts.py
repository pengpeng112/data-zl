"""Daily failure handling: gap ledger, immutable alert queue, and safe failure state."""

from datetime import datetime, timezone
import json
from types import SimpleNamespace

import pytest

from app.services.reporting_pipeline.contracts import ContractViolation
from app.services.reporting_pipeline.repositories import InMemoryControlRepository
from app.services.reporting_pipeline.runtime import (
    DailyCycleConfig,
    DailyCycleService,
    PipelineTask,
    build_production_cycle,
)


TABLE = "EMR_TEST_ALERTS"
DAY = "2026-10-21"  # T+1 business day frozen from the 22nd run.
SENSITIVE = "patient_id=PATIENT-SECRET-8842"


class Spec:
    canonical_table = TABLE
    enabled = True
    source_candidates = ()

    @staticmethod
    def validate_action(_action):
        return None


def make_service(repository, *, fail=True):
    spec = Spec()

    def capture(_context, _task):
        if fail:
            raise RuntimeError(SENSITIVE)
        return {"ok": True}

    tasks = [
        PipelineTask(
            canonical_table=TABLE,
            mode="T1",
            physical_sources=("ODS@fake:1521",),
            target_resource=None,
            spec=spec,
            capture_fn=capture,
        ),
        PipelineTask(
            canonical_table="EMR_INDEPENDENT_OK",
            mode="T1",
            physical_sources=("ODS@fake:1521",),
            target_resource=None,
            spec=SimpleNamespace(
                canonical_table="EMR_INDEPENDENT_OK",
                validate_action=lambda _action: None,
            ),
            capture_fn=lambda _context, _task: {"ok": True},
        ),
    ]
    return DailyCycleService(
        repository=repository,
        bundle=SimpleNamespace(tasks=[]),
        task_factory=lambda _anchor: tasks,
        config=DailyCycleConfig(business_tz_name="Asia/Shanghai"),
        simulation=True,
        daily_report_builder=lambda **_kwargs: SimpleNamespace(to_dict=lambda: {}),
    )


def test_run_day_continues_and_queues_stable_sanitized_alert():
    repository = InMemoryControlRepository()
    service = make_service(repository)
    now = datetime(2026, 10, 22, 12, tzinfo=timezone.utc)

    first = service.run_day(now)
    assert "EMR_INDEPENDENT_OK:T1" in first["cycle"]["dispatched"]
    assert "EMR_TEST_ALERTS:T1" in first["cycle"]["failures"]
    assert first["failure_handling"]["status"] == "QUEUED"
    assert [g.reason for g in repository.open_gaps(TABLE)] == ["SCHEDULER_TASK_FAILED"]

    event_id = first["failure_handling"]["queued"][0]["source_event_id"]
    event1 = repository.get_outbox_event(event_id)
    assert event1 is not None
    body1 = event1.immutable_body_bytes
    payload = json.loads(body1)
    assert SENSITIVE.encode() not in body1
    assert b"PATIENT-SECRET-8842" not in body1
    assert payload["severity"] == "yellow"
    assert payload["metadata"]["recommended_action"]
    assert payload["metadata"]["detail_ref"] == f"gap://{DAY}/EMR_TEST_ALERTS"
    occurred_at = datetime.fromisoformat(payload["occurred_at"])
    assert occurred_at.tzinfo is not None
    assert occurred_at.utcoffset().total_seconds() == 0

    second = service.run_day(now)
    event2 = repository.get_outbox_event(event_id)
    assert second["failure_handling"]["queued"][0]["source_event_id"] == event_id
    assert event2.immutable_body_bytes == body1
    assert len(repository.open_gaps(TABLE)) == 1
    assert len(repository.snapshot()["outbox"]) == 1


def test_outbox_failure_is_visible_and_cycle_is_not_success():
    class FailingOutboxRepository(InMemoryControlRepository):
        def append_incident_event(self, *args, **kwargs):
            raise RuntimeError(SENSITIVE)

    repository = FailingOutboxRepository()
    result = make_service(repository).run_day(
        datetime(2026, 10, 22, 12, tzinfo=timezone.utc)
    )
    assert "EMR_INDEPENDENT_OK:T1" in result["cycle"]["dispatched"]
    assert result["failure_handling"]["status"] == "FAILED"
    assert result["failure_handling"]["errors"] == [
        {
            "table": TABLE,
            "stage": "ALERT_OUTBOX_ENQUEUE",
            "error_class": "RuntimeError",
            "error_code": "FAILURE_HANDLING_FAILED",
        }
    ]
    assert result["cycle"]["overall"] == "PARTIAL_SUCCESS_WITH_BACKLOG"
    assert SENSITIVE not in str(result)


def test_production_builder_rejects_unwired_relay_url_without_echoing_it():
    url = "https://relay-secret.invalid"
    with pytest.raises(ContractViolation, match="尚未接线") as error:
        build_production_cycle(
            session_factory=None,
            bundle=SimpleNamespace(tasks=[]),
            stage_root="unused",
            relay_base_url=url,
        )
    assert url not in str(error.value)
