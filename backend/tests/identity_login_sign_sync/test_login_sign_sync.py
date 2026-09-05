"""Pure tests for the required daily login/sign-way fill subtask."""

from unittest.mock import MagicMock

import pytest

from app.services import identity_login_sign_sync as service
from app.services.identity_sync_status import aggregate_overall_status


def test_build_plan_fills_empty_account_like_004069():
    plan = service.build_login_sign_plan(
        expected={"E1", "E2", "E3"},
        target_users={"E1", "E2"},
        control_users={"E2"},
        logins={"E2": {"0", "2", "4"}},
        signs={"E2": {"0", "2", "4"}},
        defaults={"E2": 1},
    )
    assert plan["skipped_no_user"] == 1
    assert plan["skipped_equal"] == 1
    assert len(plan["repairs"]) == 1
    item = plan["repairs"][0]
    assert item["user_id"] == "E1"
    assert item["insert_control"] is True
    assert item["login_ways"] == ["0", "2", "4"]
    assert [s["sign_way"] for s in item["sign_ways"]] == ["0", "2", "4"]
    assert item["sign_ways"][0]["default_flag"] == "1"
    assert item["sign_ways"][1]["default_flag"] == "0"
    assert item["fix_default"] is False


def test_build_plan_skips_manually_configured_users_without_filling_gaps():
    """003531 事故治本（2026-09-05）：已有任意登录/签名方式行 = 已配置，
    不再按 0/2/4 模板补缺——旧语义曾给人工 2/4/8 配置后插 sign_way=0
    (default=1) 产生双默认，EMR 报「必须设置两种以上的签名模式」。"""
    plan = service.build_login_sign_plan(
        expected={"E1", "E2"},
        target_users={"E1", "E2"},
        control_users={"E1", "E2"},
        logins={"E1": {"2"}, "E2": {"0", "2", "4", "8"}},
        signs={"E1": {"2"}, "E2": {"2", "4", "8"}},
        defaults={"E1": 1, "E2": 1},
    )
    assert plan["repairs"] == []
    assert plan["skipped_configured"] == 2
    assert plan["skipped_equal"] == 2


def test_build_plan_repairs_missing_default_on_existing_way_zero():
    plan = service.build_login_sign_plan(
        expected={"E1"},
        target_users={"E1"},
        control_users={"E1"},
        logins={"E1": {"0", "2", "4"}},
        signs={"E1": {"0", "2", "4"}},
        defaults={},
    )
    item = plan["repairs"][0]
    assert item["login_ways"] == []
    assert item["sign_ways"] == []
    assert item["fix_default"] is True


def test_daily_subtask_applies_empty_account(monkeypatch):
    monkeypatch.setattr(service, "_read_expected_platform", lambda db: {"E1"})
    adapter = MagicMock()
    monkeypatch.setattr(service, "_adapter", lambda: adapter)
    monkeypatch.setattr(
        service, "_read_target",
        lambda a: {
            "users": {"E1"},
            "control": set(),
            "logins": {},
            "signs": {},
            "defaults": {},
            "metadata": {"target_users": 1},
        },
    )
    monkeypatch.setattr(
        service, "reconcile_pending_login_sign_actions",
        lambda *args: {"reconciled": 0, "unresolved": 0},
    )
    adapter.apply_login_sign_gaps.return_value = {
        "status": "success",
        "control_inserted": 1,
        "sublogin_inserted": 3,
        "subsign_inserted": 3,
        "default_repaired": 0,
    }
    monkeypatch.setattr(service, "create_action", lambda *a, **k: MagicMock())
    finished = []
    monkeypatch.setattr(service, "finish_action", lambda db, row, **k: finished.append(k.get("status")))
    monkeypatch.setattr(service, "compute_account_fingerprint", lambda *a: "fp")

    result = service.sync_jhemr_login_sign_daily(run_id="R-FILL", db=MagicMock())

    assert result["status"] == "success"
    assert result["planned_count"] == 1
    assert result["control_inserted"] == 1
    assert result["sublogin_inserted"] == 3
    assert result["subsign_inserted"] == 3
    call = adapter.apply_login_sign_gaps.call_args.args[0]
    assert call[0]["user_id"] == "E1"
    assert call[0]["insert_control"] is True
    assert finished == ["executed"]


def test_daily_subtask_plan_only_does_not_write(monkeypatch):
    monkeypatch.setattr(service, "_read_expected_platform", lambda db: {"E1"})
    adapter = MagicMock()
    monkeypatch.setattr(service, "_adapter", lambda: adapter)
    monkeypatch.setattr(
        service, "_read_target",
        lambda a: {
            "users": {"E1"}, "control": set(), "logins": {}, "signs": {},
            "defaults": {}, "metadata": {"target_users": 1},
        },
    )
    monkeypatch.setattr(
        service, "reconcile_pending_login_sign_actions",
        lambda *args: {"reconciled": 0, "unresolved": 0},
    )
    created = []
    monkeypatch.setattr(service, "create_action", lambda *a, **k: created.append(k) or MagicMock())

    result = service.sync_jhemr_login_sign_daily(run_id="R-PLAN", db=MagicMock(), plan_only=True)

    assert result["status"] == "success"
    assert result["reason"] == "plan_only"
    adapter.apply_login_sign_gaps.assert_not_called()
    assert created == []


def test_daily_subtask_no_changes_is_idempotent(monkeypatch):
    monkeypatch.setattr(service, "_read_expected_platform", lambda db: {"E1"})
    adapter = MagicMock()
    monkeypatch.setattr(service, "_adapter", lambda: adapter)
    monkeypatch.setattr(
        service, "_read_target",
        lambda a: {
            "users": {"E1"},
            "control": {"E1"},
            "logins": {"E1": {"0", "2", "4"}},
            "signs": {"E1": {"0", "2", "4"}},
            "defaults": {"E1": 1},
            "metadata": {"target_users": 1},
        },
    )
    monkeypatch.setattr(
        service, "reconcile_pending_login_sign_actions",
        lambda *args: {"reconciled": 0, "unresolved": 0},
    )

    result = service.sync_jhemr_login_sign_daily(run_id="R-NONE", db=MagicMock())

    assert result["status"] == "success"
    assert result["reason"] == "no_changes"
    adapter.apply_login_sign_gaps.assert_not_called()


def test_target_write_failure_fails_actions(monkeypatch):
    monkeypatch.setattr(service, "_read_expected_platform", lambda db: {"E1"})
    adapter = MagicMock()
    monkeypatch.setattr(service, "_adapter", lambda: adapter)
    monkeypatch.setattr(
        service, "_read_target",
        lambda a: {
            "users": {"E1"}, "control": set(), "logins": {}, "signs": {},
            "defaults": {}, "metadata": {"target_users": 1},
        },
    )
    monkeypatch.setattr(
        service, "reconcile_pending_login_sign_actions",
        lambda *args: {"reconciled": 0, "unresolved": 0},
    )
    adapter.apply_login_sign_gaps.side_effect = RuntimeError("connection lost")
    monkeypatch.setattr(service, "create_action", lambda *a, **k: MagicMock())
    finished = []
    monkeypatch.setattr(service, "finish_action", lambda db, row, **k: finished.append(k.get("status")))
    monkeypatch.setattr(service, "compute_account_fingerprint", lambda *a: "fp")

    result = service.sync_jhemr_login_sign_daily(run_id="R-FAIL", db=MagicMock())

    assert result["status"] == "failed"
    assert result["failed"] == 1
    assert "target_write" in result["error_classes"]
    assert finished == ["failed"]


def test_missing_audit_context_is_misconfigured():
    result = service.sync_jhemr_login_sign_daily(run_id=None, db=None)
    assert result["status"] == "misconfigured"
    assert "audit_config" in result["error_classes"]


@pytest.mark.parametrize("login_sign_status, expected", [
    ("success", "success"),
    ("failed", "partial_success"),
    ("misconfigured", "partial_success"),
    ("skipped", "success"),
])
def test_aggregate_overall_status_includes_required_login_sign_subtask(login_sign_status, expected):
    assert aggregate_overall_status(
        "success", "success", title_status="success", dept_status="success",
        login_sign_status=login_sign_status,
    ) == expected
