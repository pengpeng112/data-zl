"""Pure tests for the required daily user-dept subtask."""

from unittest.mock import MagicMock

import pytest

from app.services import identity_dept_sync as service
from app.services.identity_sync_status import aggregate_overall_status


def _expected(emp_depts):
    return {
        emp: {"depts": depts, "primary": depts[0]}
        for emp, depts in emp_depts.items()
    }


def test_build_dept_plan_adds_missing_rows_and_detects_primary_change():
    expected = _expected({
        "E1": ["D1", "D2"],       # D2 missing in target
        "E2": ["D9"],             # primary changed D1 -> D9
        "E3": ["D1"],             # fully equal
        "E4": ["D1"],             # no JHEMR account
    })
    target_users = {"E1": "D1", "E2": "D1", "E3": "D1"}
    target_depts = {"E1": {"D1"}, "E2": {"D1"}, "E3": {"D1"}}

    plan = service.build_dept_plan(expected, target_users, target_depts)

    assert plan["dept_adds"] == [("E1", "D2"), ("E2", "D9")]
    assert plan["primary_changes"] == [("E2", "D1", "D9")]
    assert plan["skipped_equal"] == 1
    assert plan["skipped_no_user"] == 1


def test_build_dept_plan_primary_change_with_new_primary_already_present():
    expected = _expected({"E1": ["D2", "D1"]})
    target_users = {"E1": "D1"}
    target_depts = {"E1": {"D1", "D2"}}

    plan = service.build_dept_plan(expected, target_users, target_depts)

    assert plan["dept_adds"] == []
    assert plan["primary_changes"] == [("E1", "D1", "D2")]
    assert plan["skipped_equal"] == 0


def test_daily_subtask_applies_adds_and_primary_changes(monkeypatch):
    monkeypatch.setattr(
        service, "_read_expected_platform",
        lambda db: _expected({"E1": ["D1", "D2"], "E2": ["D9"]}),
    )
    adapter = MagicMock()
    monkeypatch.setattr(service, "_adapter", lambda: adapter)
    monkeypatch.setattr(
        service, "_read_target",
        lambda a: ({"E1": "D1", "E2": "D1"}, {"E1": {"D1"}, "E2": {"D1"}}, {"target_users": 2}),
    )
    monkeypatch.setattr(
        service, "reconcile_pending_dept_actions",
        lambda *args: {"reconciled": 0, "unresolved": 0},
    )
    adapter.apply_user_dept_changes.return_value = {
        "status": "success", "dept_rows_added": 2, "primary_updated": 1,
    }
    action = MagicMock()
    monkeypatch.setattr(service, "create_action", lambda *a, **k: action)
    finished = []
    monkeypatch.setattr(service, "finish_action", lambda db, row, **k: finished.append(k.get("status")))
    monkeypatch.setattr(service, "compute_account_fingerprint", lambda *a: "fp")

    result = service.sync_jhemr_user_depts_daily(run_id="R-DEPT", db=MagicMock())

    assert result["status"] == "success"
    assert result["planned_count"] == 3
    assert result["dept_rows_added"] == 2
    assert result["primary_updated"] == 1
    call = adapter.apply_user_dept_changes.call_args.kwargs
    assert call["dept_adds"] == [("E1", "D2"), ("E2", "D9")]
    assert call["primary_changes"] == [("E2", "D1", "D9")]
    assert finished.count("executed") == 3


def test_daily_subtask_plan_only_writes_neither_target_nor_audit(monkeypatch):
    monkeypatch.setattr(
        service, "_read_expected_platform", lambda db: _expected({"E1": ["D1", "D2"]}),
    )
    adapter = MagicMock()
    monkeypatch.setattr(service, "_adapter", lambda: adapter)
    monkeypatch.setattr(
        service, "_read_target",
        lambda a: ({"E1": "D1"}, {"E1": {"D1"}}, {"target_users": 1}),
    )
    monkeypatch.setattr(
        service, "reconcile_pending_dept_actions",
        lambda *args: {"reconciled": 0, "unresolved": 0},
    )
    created = []
    monkeypatch.setattr(service, "create_action", lambda *a, **k: created.append(k) or MagicMock())

    result = service.sync_jhemr_user_depts_daily(run_id="R-PLAN", db=MagicMock(), plan_only=True)

    assert result["status"] == "success"
    assert result["reason"] == "plan_only"
    assert result["planned_count"] == 1
    adapter.apply_user_dept_changes.assert_not_called()
    assert created == []


def test_daily_subtask_no_changes_is_idempotent_success(monkeypatch):
    monkeypatch.setattr(
        service, "_read_expected_platform", lambda db: _expected({"E1": ["D1"]}),
    )
    adapter = MagicMock()
    monkeypatch.setattr(service, "_adapter", lambda: adapter)
    monkeypatch.setattr(
        service, "_read_target",
        lambda a: ({"E1": "D1"}, {"E1": {"D1"}}, {"target_users": 1}),
    )
    monkeypatch.setattr(
        service, "reconcile_pending_dept_actions",
        lambda *args: {"reconciled": 0, "unresolved": 0},
    )

    result = service.sync_jhemr_user_depts_daily(run_id="R-NONE", db=MagicMock())

    assert result["status"] == "success"
    assert result["reason"] == "no_changes"
    assert result["skipped_equal"] == 1
    adapter.apply_user_dept_changes.assert_not_called()


def test_target_write_failure_fails_all_actions(monkeypatch):
    monkeypatch.setattr(
        service, "_read_expected_platform", lambda db: _expected({"E1": ["D1", "D2"]}),
    )
    adapter = MagicMock()
    monkeypatch.setattr(service, "_adapter", lambda: adapter)
    monkeypatch.setattr(
        service, "_read_target",
        lambda a: ({"E1": "D1"}, {"E1": {"D1"}}, {"target_users": 1}),
    )
    monkeypatch.setattr(
        service, "reconcile_pending_dept_actions",
        lambda *args: {"reconciled": 0, "unresolved": 0},
    )
    adapter.apply_user_dept_changes.side_effect = RuntimeError("connection lost")
    monkeypatch.setattr(service, "create_action", lambda *a, **k: MagicMock())
    finished = []
    monkeypatch.setattr(service, "finish_action", lambda db, row, **k: finished.append(k.get("status")))
    monkeypatch.setattr(service, "compute_account_fingerprint", lambda *a: "fp")

    result = service.sync_jhemr_user_depts_daily(run_id="R-FAIL", db=MagicMock())

    assert result["status"] == "failed"
    assert result["failed"] == 1
    assert "target_write" in result["error_classes"]
    assert finished.count("failed") == 1


def test_pending_audit_unresolved_fails_closed(monkeypatch):
    monkeypatch.setattr(
        service, "_read_expected_platform", lambda db: _expected({"E1": ["D1"]}),
    )
    adapter = MagicMock()
    monkeypatch.setattr(service, "_adapter", lambda: adapter)
    monkeypatch.setattr(
        service, "_read_target",
        lambda a: ({"E1": "D1"}, {"E1": {"D1"}}, {"target_users": 1}),
    )
    monkeypatch.setattr(
        service, "reconcile_pending_dept_actions",
        lambda *args: {"reconciled": 0, "unresolved": 2},
    )

    result = service.sync_jhemr_user_depts_daily(run_id="R-PEND", db=MagicMock())

    assert result["status"] == "misconfigured"
    adapter.apply_user_dept_changes.assert_not_called()


def test_missing_audit_context_is_misconfigured():
    result = service.sync_jhemr_user_depts_daily(run_id=None, db=None)
    assert result["status"] == "misconfigured"
    assert "audit_config" in result["error_classes"]


@pytest.mark.parametrize("dept_status, expected", [
    ("success", "success"),
    ("failed", "partial_success"),
    ("misconfigured", "partial_success"),
    ("skipped", "success"),
])
def test_aggregate_overall_status_includes_required_dept_subtask(dept_status, expected):
    assert aggregate_overall_status(
        "success", "success", title_status="success", dept_status=dept_status,
    ) == expected
