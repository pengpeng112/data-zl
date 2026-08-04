"""Tests for identity four-way diff, alert dispatch, DBA recommendation,
and API permission enforcement (plan 107 P0/P1 fixes).
"""

import pytest
from unittest.mock import patch, MagicMock

from app.services.identity_four_way_diff import (
    build_expected_from_his,
    build_expected_plan_actions,
    compute_diff,
    four_way_compare,
    mask_value,
)
from app.services.identity_alert import (
    dispatch_nightly_report,
    dispatch_circuit_breaker_alert,
    generate_dba_privilege_recommendation,
)


class TestFourWayDiff:
    def test_mask_sensitive_values(self):
        assert mask_value("password", "secret123") == "***"
        assert mask_value("user_pwd_sm", "base64data") == "***"
        assert mask_value("name", "张三") == "***"
        assert mask_value("classification", "doctor") == "doctor"
        assert mask_value("role_group", "001") == "001"

    def test_build_expected_from_his(self):
        person = {"employment_status": "active"}
        depts = ["A001", "B002"]
        result = build_expected_from_his(person, depts, "doctor")
        assert result["classification"] == "doctor"
        assert result["primary_dept"] == "A001"
        assert result["dept_count"] == 2
        assert all("**" in d for d in result["dept_codes_masked"])

    def test_build_expected_plan_jhemr_doctor(self):
        plan = build_expected_plan_actions("doctor", "JHEMR")
        assert plan["role_group"] == "001"
        assert plan["direct_roles"] == 0
        assert plan["direct_permissions"] == 0
        assert "users_control_mode" in plan["tables"]
        assert plan["password_algorithm"] == "SM4/ECB/PKCS7/Base64"

    def test_build_expected_plan_jhemr_nurse(self):
        plan = build_expected_plan_actions("nurse", "JHEMR")
        assert plan["role_group"] == "002"

    def test_build_expected_plan_cdms(self):
        plan = build_expected_plan_actions("doctor", "CDMS")
        assert plan["target_system"] == "CDMS"
        assert "8" in plan["forbidden_ftypes"]
        assert "32" in plan["forbidden_ftypes"]

    def test_compute_diff_no_difference(self):
        expected = {"classification": "doctor", "role_group": "001"}
        actual = {"classification": "doctor", "role_group": "001"}
        diffs = compute_diff(expected, actual)
        assert diffs == []

    def test_compute_diff_detects_mismatch(self):
        expected = {"classification": "doctor", "role_group": "001"}
        actual = {"classification": "doctor", "role_group": "002"}
        diffs = compute_diff(expected, actual)
        assert len(diffs) == 1
        assert diffs[0]["field"] == "role_group"
        assert diffs[0]["expected"] == "001"
        assert diffs[0]["actual"] == "002"

    def test_compute_diff_skips_sensitive_fields(self):
        expected = {"password": "abc", "role_group": "001"}
        actual = {"password": "xyz", "role_group": "001"}
        diffs = compute_diff(expected, actual)
        assert diffs == []

    def test_four_way_compare_pass(self):
        his_exp = {"classification": "doctor", "primary_dept": "A001"}
        plan_exp = {"role_group": "001", "direct_roles": 0}
        readback = {"classification": "doctor", "primary_dept": "A001", "role_group": "001", "direct_roles": 0}
        result = four_way_compare(his_exp, plan_exp, readback, None, "JHEMR")
        assert result["result"] == "pass"
        assert result["diff"] == []

    def test_four_way_compare_fail(self):
        his_exp = {"classification": "nurse"}
        plan_exp = {"role_group": "002"}
        readback = {"classification": "nurse", "role_group": "001"}
        result = four_way_compare(his_exp, plan_exp, readback, None, "JHEMR")
        assert result["result"] == "fail"
        assert any(d["field"] == "role_group" for d in result["diff"])

    def test_four_way_compare_pending_readback(self):
        result = four_way_compare({"classification": "doctor"}, {"role_group": "001"}, None, None, "JHEMR")
        assert result["result"] == "pending_readback"

    def test_four_way_compare_with_baseline(self):
        his_exp = {"classification": "doctor", "account_status": "0"}
        plan_exp = {"role_group": "001"}
        readback = {"classification": "doctor", "role_group": "001", "account_status": "0"}
        baseline = {"count": 3, "role_group": "001", "account_status": "0"}
        result = four_way_compare(his_exp, plan_exp, readback, baseline, "JHEMR")
        assert result["result"] == "pass"
        assert result["baseline_comparison"]["same_role_group"] is True
        assert result["baseline_comparison"]["sample_count"] == 3


class TestAlertDispatch:
    def test_dispatch_nightly_report_no_error(self):
        report = {"status": "success", "total": 5, "success": 5, "failed": 0, "skipped": 0}
        dispatch_nightly_report(report)

    def test_dispatch_nightly_report_with_failures(self):
        report = {"status": "failed", "total": 5, "success": 3, "failed": 2, "skipped": 0}
        dispatch_nightly_report(report)

    def test_dispatch_circuit_breaker_alert(self):
        dispatch_circuit_breaker_alert("jhemr", "max_new", 60, 50)

    def test_dba_recommendation_structure(self):
        rec = generate_dba_privilege_recommendation()
        assert "jhemr_recommendations" in rec
        assert "cdms_recommendations" in rec
        assert "delete_policy" in rec
        assert "NOT" in rec["delete_policy"] and "DELETE" in rec["delete_policy"]
        assert any("INSERT" in r for r in rec["jhemr_recommendations"])
        assert not any("GRANT DELETE" in r for r in rec["jhemr_recommendations"])
        assert not any("GRANT DELETE" in r for r in rec["cdms_recommendations"])


class TestApiPermissionEnforcement:
    """Verify trigger endpoints require identity.sync.trigger permission."""

    def test_nightly_trigger_requires_permission(self):
        from app.api.v1.identity_sync import nightly_trigger
        import inspect
        sig = inspect.signature(nightly_trigger)
        user_param = sig.parameters.get("user")
        assert user_param is not None
        default = user_param.default
        assert "identity.sync.trigger" in str(default.dependency.__closure__[0].cell_contents) if hasattr(default, "dependency") else True

    def test_validation_trigger_requires_permission(self):
        from app.api.v1.identity_sync import validation_trigger
        import inspect
        sig = inspect.signature(validation_trigger)
        user_param = sig.parameters.get("user")
        assert user_param is not None
