"""Pure tests for the required daily login/sign-way fill subtask."""

from unittest.mock import MagicMock

import pytest

from app.services import identity_login_sign_sync as service
from app.services.identity_sync_status import aggregate_overall_status


@pytest.fixture(autouse=True)
def _legacy_run_mode(monkeypatch):
    """186 v1.10 P0-19：本文件回归旧登录/签名同步行为 → run_mode=full
    （observe/disable_only 下该子任务为 skipped 零目标写）。"""
    from app.core.config import settings
    monkeypatch.setattr(settings, "identity_run_mode", "full")
    yield



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
    """已配置且登录/签名集合一致：不套 0/2/4 模板。"""
    plan = service.build_login_sign_plan(
        expected={"E1"},
        target_users={"E1"},
        control_users={"E1"},
        logins={"E1": {"2", "4", "8"}},
        signs={"E1": {"2", "4", "8"}},
        defaults={"E1": 1},
    )
    assert plan["repairs"] == []
    assert plan["skipped_configured"] == 1
    assert plan["skipped_equal"] == 1


def test_build_plan_fills_login_sign_gap_without_template_default():
    """003531 vs 003534：登录有 0、签名没有 0 时补 sign_way=0 且 default=0。"""
    plan = service.build_login_sign_plan(
        expected={"E2"},
        target_users={"E2"},
        control_users={"E2"},
        logins={"E2": {"0", "2", "4", "8"}},
        signs={"E2": {"2", "4", "8"}},
        defaults={"E2": 1},
    )
    assert len(plan["repairs"]) == 1
    item = plan["repairs"][0]
    assert item["login_ways"] == []
    assert [s["sign_way"] for s in item["sign_ways"]] == ["0"]
    assert item["sign_ways"][0]["default_flag"] == "0"
    assert item["fix_default"] is False


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


def test_align_fills_login_sign_gap_default_zero():
    from app.services.jhemr_identity_adapter import JhemrIdentityAdapter

    adapter = JhemrIdentityAdapter.__new__(JhemrIdentityAdapter)
    adapter.hospital_no = "49557032X"
    adapter.sync_operator_id = "TEST"
    adapter._fetch_user = lambda emp_no: {"user_id": emp_no, "education_title": None}
    conn = MagicMock()
    adapter._ensure_conn = lambda: conn
    writes = []
    signs = [{"sign_way": way} for way in ("2", "4", "8")]

    def execute_write(sql, params):
        writes.append((sql, params))
        if "INSERT" in sql and "users_subsign" in sql:
            way = next((str(p) for p in params if str(p) in {"0", "2", "4", "8"}), None)
            if way:
                signs.append({"sign_way": way})
        return 1

    adapter._execute_write = execute_write
    adapter._fetch_one = lambda sql, params: (
        {"in_sign_way": "2,4,8", "login_way": "0,2,4,8", "in_pic_mode": "2,2,2"}
        if "in_sign_way" in sql
        else {"role_group_id": "001"}
    )
    adapter._existing_dept_codes = lambda user_id: {"D001"}
    adapter._fetch_all = lambda sql, params: (
        [{"login_way": way} for way in ("0", "2", "4", "8")]
        if "users_sublogin" in sql
        else list(signs)
    )
    result = adapter.align_existing_user("E001", "doctor", ["D001"], "001")
    assert result.get("status") == "success", result
    sign_inserts = [p for s, p in writes if "INSERT" in s and "users_subsign" in s]
    assert len(sign_inserts) == 1
    assert "0" in [str(x) for x in sign_inserts[0]]
    assert sign_inserts[0][-1] == "0"
    assert any(a["action"] == "insert_sign_for_login_gap" for a in result["actions"])


def test_align_matched_003534_pattern_no_writes():
    from app.services.jhemr_identity_adapter import JhemrIdentityAdapter

    adapter = JhemrIdentityAdapter.__new__(JhemrIdentityAdapter)
    adapter.hospital_no = "49557032X"
    adapter.sync_operator_id = "TEST"
    adapter._fetch_user = lambda emp_no: {"user_id": emp_no, "education_title": None}
    conn = MagicMock()
    adapter._ensure_conn = lambda: conn
    writes = []
    adapter._execute_write = lambda sql, params: writes.append((sql, params)) or 1
    adapter._fetch_one = lambda sql, params: (
        {"in_sign_way": "0,2,4", "login_way": "0,2,4", "in_pic_mode": "2,2,2"}
        if "in_sign_way" in sql
        else {"role_group_id": "001"}
    )
    adapter._existing_dept_codes = lambda user_id: {"D001"}
    adapter._fetch_all = lambda sql, params: (
        [{"login_way": way} for way in ("0", "2", "4")]
        if "users_sublogin" in sql
        else [{"sign_way": way} for way in ("0", "2", "4")]
    )
    result = adapter.align_existing_user("E001", "doctor", ["D001"], "001")
    assert result.get("status") == "success", result
    assert not [s for s, _ in writes if "users_sublogin" in s or "users_subsign" in s]
    assert not [s for s, _ in writes if "UPDATE jhemr.users_control_mode" in s]


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
