"""Pure tests for the required daily title subtask."""

from unittest.mock import MagicMock

import pytest

from app.services import identity_title_sync as service


def test_source_map_reuses_employee_title_dictionary_and_keeps_unmapped_empty():
    source, stats = service.build_source_map(
        [{"DICT_CODE": "L1", "DICT_NAME": "主治医师"}],
        [{"EMPLCODE": "E1", "LEVLCODE": "L1"}, {"EMPLCODE": "E2", "LEVLCODE": None}],
    )
    assert source == {"E1": "主治医师"}
    assert stats["unmapped_employees"] == 1


@pytest.mark.parametrize("rows, message", [
    ([{"DICT_CODE": "L1", "DICT_NAME": "医师"}, {"DICT_CODE": "L1", "DICT_NAME": "主治医师"}], "source_dictionary_ambiguous"),
])
def test_source_ambiguity_fails_closed(rows, message):
    with pytest.raises(service.TitleSyncError, match=message):
        service.build_source_map(rows, [{"EMPLCODE": "E1", "LEVLCODE": "L1"}])


def test_daily_subtask_updates_only_changed_titles_and_counts_skips(monkeypatch):
    monkeypatch.setattr(service, "_read_source", lambda limit: ({"E1": "新职称", "E2": "相同", "E3": "缺失"}, {}))
    adapter = MagicMock()
    monkeypatch.setattr(service, "_adapter", lambda: adapter)
    monkeypatch.setattr(service, "_read_target", lambda current: ({"E1": "旧职称", "E2": "相同"}, {"max_length": 21}))
    monkeypatch.setattr(service, "reconcile_pending_title_actions", lambda *args: {"reconciled": 0, "unresolved": 0})
    adapter.update_education_titles_only.return_value = {"status": "success", "updated": 1, "skipped": 0}
    action = MagicMock()
    monkeypatch.setattr(service, "create_action", lambda *args, **kwargs: action)
    monkeypatch.setattr(service, "finish_action", lambda *args, **kwargs: None)
    monkeypatch.setattr(service, "compute_account_fingerprint", lambda *args: "fp")

    result = service.sync_jhemr_education_titles_daily(run_id="R-TITLE", db=MagicMock())

    assert result["status"] == "success"
    assert result["planned_count"] == 1
    assert result["updated"] == 1
    assert result["skipped_equal"] == 1
    assert result["skipped_no_user"] == 1
    adapter.update_education_titles_only.assert_called_once_with([("E1", "旧职称", "新职称")])
    assert action is not None


def test_empty_source_closes_without_opening_target(monkeypatch):
    monkeypatch.setattr(service, "_read_source", lambda limit: (_ for _ in ()).throw(service.TitleSyncError("source_empty")))
    adapter_factory = MagicMock()
    monkeypatch.setattr(service, "_adapter", adapter_factory)

    result = service.sync_jhemr_education_titles_daily(run_id="R-EMPTY", db=MagicMock())

    assert result["status"] == "misconfigured"
    assert "source_select" in result["error_classes"]
    adapter_factory.assert_not_called()


def test_unhandled_adapter_configuration_error_is_failed_closed(monkeypatch):
    monkeypatch.setattr(service, "_read_source", lambda limit: ({"E1": "职称"}, {}))
    monkeypatch.setattr(service, "_adapter", lambda: (_ for _ in ()).throw(RuntimeError("configuration")))

    result = service.sync_jhemr_education_titles_daily(run_id="R-CONFIG", db=MagicMock())

    assert result["status"] == "failed"
    assert "target_select_or_metadata" in result["error_classes"]


def test_overlength_title_closes_before_any_target_update(monkeypatch):
    monkeypatch.setattr(service, "_read_source", lambda limit: ({"E1": "过长职称"}, {}))
    adapter = MagicMock()
    monkeypatch.setattr(service, "_adapter", lambda: adapter)
    monkeypatch.setattr(service, "_read_target", lambda current: ({"E1": "旧"}, {"max_length": 1}))

    result = service.sync_jhemr_education_titles_daily(run_id="R-LONG", db=MagicMock())

    assert result["status"] == "misconfigured"
    adapter.update_education_title_only.assert_not_called()


def test_title_failure_is_required_and_produces_partial_overall():
    from app.services.identity_sync_status import aggregate_overall_status, runner_exit_code

    overall = aggregate_overall_status("success", "success", title_status="failed")
    assert overall == "partial_success"
    assert runner_exit_code(overall) == 2


def test_adapter_title_method_writes_one_column_and_reads_back():
    from app.services.jhemr_identity_adapter import JhemrIdentityAdapter

    adapter = JhemrIdentityAdapter.__new__(JhemrIdentityAdapter)
    adapter.hospital_no = "49557032X"
    adapter._fetch_one = MagicMock(side_effect=[
        {"user_id": "E1", "education_title": "旧职称"},
        {"education_title": "新职称"},
    ])
    adapter._execute_write = MagicMock(return_value=1)
    adapter._ensure_conn = lambda: MagicMock()

    result = adapter.update_education_title_only("E1", "新职称", expected_current="旧职称")

    assert result == {"status": "success", "rows_affected": 1}
    sql, params = adapter._execute_write.call_args.args
    assert "UPDATE jhemr.users SET education_title" in sql
    assert params == ("新职称", "E1", "49557032X")


def test_daily_subtask_requires_durable_audit_before_connecting(monkeypatch):
    adapter_factory = MagicMock()
    monkeypatch.setattr(service, "_adapter", adapter_factory)

    result = service.sync_jhemr_education_titles_daily(run_id=None, db=None)

    assert result["status"] == "misconfigured"
    assert "audit_config" in result["error_classes"]
    adapter_factory.assert_not_called()


def test_completion_audit_failure_keeps_committed_count_out_of_failed(monkeypatch):
    monkeypatch.setattr(service, "_read_source", lambda limit: ({"E1": "新职称"}, {}))
    adapter = MagicMock()
    monkeypatch.setattr(service, "_adapter", lambda: adapter)
    monkeypatch.setattr(service, "_read_target", lambda current: ({"E1": "旧职称"}, {"max_length": 21}))
    monkeypatch.setattr(service, "reconcile_pending_title_actions", lambda *args: {"reconciled": 0, "unresolved": 0})
    adapter.update_education_titles_only.return_value = {"status": "success", "updated": 1, "skipped": 0}
    monkeypatch.setattr(service, "compute_account_fingerprint", lambda *args: "fp")
    monkeypatch.setattr(service, "create_action", lambda *args, **kwargs: MagicMock())
    monkeypatch.setattr(
        service,
        "finish_action",
        MagicMock(side_effect=service.AuditWriteError("completion")),
    )

    result = service.sync_jhemr_education_titles_daily(run_id="R-AUDIT", db=MagicMock())

    assert result["status"] == "failed"
    assert result["updated"] == 1
    assert result["failed"] == 0
    assert result["target_committed_pending_audit"] == 1


def test_adapter_batch_rolls_back_every_change_on_readback_failure():
    from app.services.jhemr_identity_adapter import JhemrIdentityAdapter

    adapter = JhemrIdentityAdapter.__new__(JhemrIdentityAdapter)
    adapter.hospital_no = "49557032X"
    adapter._fetch_one = MagicMock(side_effect=[
        {"user_id": "E1", "education_title": "旧1"},
        {"education_title": "新1"},
        {"user_id": "E2", "education_title": "旧2"},
        {"education_title": "错误值"},
    ])
    adapter._execute_write = MagicMock(return_value=1)
    conn = MagicMock()
    adapter._ensure_conn = lambda: conn

    with pytest.raises(Exception, match="read-back mismatch"):
        adapter.update_education_titles_only([
            ("E1", "旧1", "新1"),
            ("E2", "旧2", "新2"),
        ])

    conn.commit.assert_not_called()
    conn.rollback.assert_called_once()
