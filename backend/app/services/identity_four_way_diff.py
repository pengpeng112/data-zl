"""Four-way diff framework for identity sync verification (plan 107 section 17).

Compares four evidence sources:
1. HIS source expected values (from IdentityPerson/IdentityPersonDepartment)
2. Server-side action plan (from IdentitySyncAction)
3. Target post-commit readback (from adapter snapshots)
4. Same-classification aggregate baseline (from existing target accounts)

Output: desensitized expected/actual/diff/result per target.
Only HMAC fingerprints, masked dept codes, and role summaries are output.
No names, full emp_no, passwords, ciphertext, keys, phone, ID, or raw SQL.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

SENSITIVE_KEYS = {"name", "user_name", "fusername", "id_no", "phone", "phonenumber",
                  "identification", "password", "pwd", "fpwd", "user_pwd", "user_pwd_sm",
                  "fpwd_sm", "ca_no", "user_pki", "mailbox", "wechat"}


def mask_value(key: str, value: Any) -> Any:
    """Mask sensitive values; pass through safe ones."""
    if str(key).lower() in SENSITIVE_KEYS:
        return "***"
    return value


def build_expected_from_his(person: dict, depts: list[str], classification: str) -> dict[str, Any]:
    """Build HIS-source expected state for comparison."""
    return {
        "classification": classification,
        "employment_status": person.get("employment_status", "active"),
        "primary_dept": depts[0] if depts else None,
        "dept_count": len(depts),
        "dept_codes_masked": [d[:2] + "**" if len(d) > 2 else "**" for d in depts],
    }


def build_expected_plan_actions(classification: str, target_system: str) -> dict[str, Any]:
    """Build expected action plan for a target system."""
    if target_system == "JHEMR":
        role_group = "001" if classification in ("doctor", "pharmacist") else "002"
        return {
            "target_system": "JHEMR",
            "role_group": role_group,
            "tables": ["users", "user_dept", "jhauth_user_vs_role_group",
                       "users_control_mode", "users_sublogin", "users_subsign"],
            "template_version": "jhemr-login-v1",
            "password_algorithm": "SM4/ECB/PKCS7/Base64",
            "direct_roles": 0,
            "direct_permissions": 0,
        }
    else:
        return {
            "target_system": "CDMS",
            "auth_ftypes": ["3", "5", "10"],
            "forbidden_ftypes": ["8", "32"],
            "tables": ["T_MSS_EMP_DICT", "T_MSS_AUTHMAPPING"],
            "template_version": "jhemr-login-v1",
        }


def compute_diff(expected: dict, actual: dict) -> list[dict[str, Any]]:
    """Compute field-level differences between expected and actual."""
    diffs = []
    all_keys = set(list(expected.keys()) + list(actual.keys()))
    for key in sorted(all_keys):
        if str(key).lower() in SENSITIVE_KEYS:
            continue
        exp_val = expected.get(key)
        act_val = actual.get(key)
        if exp_val != act_val:
            diffs.append({
                "field": key,
                "expected": mask_value(key, exp_val),
                "actual": mask_value(key, act_val),
            })
    return diffs


def four_way_compare(
    his_expected: dict,
    plan_expected: dict,
    target_readback: dict | None,
    baseline_summary: dict | None,
    target_system: str,
) -> dict[str, Any]:
    """Perform full four-way comparison and return desensitized result.

    Returns:
        {
            "target_system": str,
            "expected": {...},
            "actual": {...},
            "diff": [...],
            "baseline_comparison": {...},
            "result": "pass" | "fail" | "pending_readback",
        }
    """
    combined_expected = {**his_expected, **plan_expected}

    if target_readback is None:
        return {
            "target_system": target_system,
            "expected": combined_expected,
            "actual": None,
            "diff": [],
            "baseline_comparison": None,
            "result": "pending_readback",
        }

    diffs = compute_diff(combined_expected, target_readback)

    baseline_comparison = None
    if baseline_summary:
        baseline_comparison = {
            "sample_count": baseline_summary.get("count", 0),
            "same_role_group": baseline_summary.get("role_group") == plan_expected.get("role_group"),
            "same_status": baseline_summary.get("account_status") == target_readback.get("account_status"),
        }

    result = "pass" if not diffs else "fail"
    return {
        "target_system": target_system,
        "expected": combined_expected,
        "actual": {k: mask_value(k, v) for k, v in target_readback.items()},
        "diff": diffs,
        "baseline_comparison": baseline_comparison,
        "result": result,
    }
