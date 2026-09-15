"""189 修复回归：

1. 编排器主任务软状态 ``partial`` 不再被 normalize_status 落到 "failed"
   默认值，从而 fail-close 四个下游子任务；
2. aggregate_overall_status 对主任务 partial_success 的汇总不再误报 failed；
3. disable_only 模式下按 ``identity_disable_only_allowed_legacy_kinds``
   白名单放行属性对账类旧写入口，建号/锁定/改密类与 observe 模式仍全阻断。
   （gate 模块 import 链触发测试库守卫，按 dict_sync_112 先例在受控
   子进程中执行，不连任何数据库。）
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from app.services.identity_sync_status import aggregate_overall_status, normalize_status

BACKEND_DIR = Path(__file__).resolve().parents[2]


def test_normalize_status_maps_orchestrator_partial_to_partial_success():
    assert normalize_status("partial") == "partial_success"
    assert normalize_status("PARTIAL ") == "partial_success"
    assert normalize_status("partial_success") == "partial_success"
    assert normalize_status("failed") == "failed"
    assert normalize_status(None) == "failed"


def test_partial_success_is_not_in_nightly_skip_set():
    # run_identity_modified_nightly.py 只在 failed/misconfigured/overdue 时
    # 跳过子任务；partial 主任务必须允许子任务继续执行。
    assert normalize_status("partial") not in {"failed", "misconfigured", "overdue"}


def test_aggregate_main_partial_with_healthy_subtasks_is_partial_success():
    assert aggregate_overall_status(
        "partial", "skipped",
        title_status="success", dept_status="success", login_sign_status="success",
    ) == "partial_success"


def test_aggregate_main_partial_with_subtask_failure_stays_partial():
    # 子任务失败已记录在各自 subtask 行/告警，整体不再升级为 failed。
    assert aggregate_overall_status(
        "partial", "success",
        title_status="success", dept_status="success", login_sign_status="failed",
    ) == "partial_success"


def test_aggregate_legacy_behaviour_unchanged_for_hard_failures():
    assert aggregate_overall_status("success", "success") == "success"
    assert aggregate_overall_status("success", "failed") == "partial_success"
    assert aggregate_overall_status("failed", "success") == "failed"
    assert aggregate_overall_status("skipped", "skipped", lock_reason="lock_held") == "skipped"


def test_disable_only_reconcile_allowlist_gate_matrix():
    cases = [
        # (mode, allow, kind, expected_allowed, expected_reason)
        ("disable_only", "", "login_sign_sync", False, "run_mode_disable_only_blocks_legacy_writes"),
        ("disable_only", "login_sign_sync,jhemr_signature_sync", "login_sign_sync", True, "disable_only_reconcile_allowlist"),
        ("disable_only", "login_sign_sync", "jhemr_signature_sync", False, "run_mode_disable_only_blocks_legacy_writes"),
        # 建号/锁定/改密类永不被白名单放行
        ("disable_only", "jhemr_apply,cdms_apply,jhemr_lock,jhemr_password_reset", "jhemr_apply", False, "run_mode_disable_only_blocks_legacy_writes"),
        ("disable_only", " jhemr_signature_sync , education_title_sync ", "jhemr_signature_sync", True, "disable_only_reconcile_allowlist"),
        ("disable_only", "jhemr_signature_sync", "jhemr_dept_sync", False, "run_mode_disable_only_blocks_legacy_writes"),
        # observe 模式不受白名单影响
        ("observe", "login_sign_sync", "login_sign_sync", False, "run_mode_observe"),
        # full 模式维持原行为
        ("full", "", "login_sign_sync", True, "ok"),
    ]
    code = f'''
import json, sys
from app.core.config import settings
from app.services.identity_sync_action_gate import gate_legacy_identity_write

out = []
for mode, allow, kind, want_allowed, want_reason in {cases!r}:
    settings.identity_run_mode = mode
    settings.identity_disable_only_allowed_legacy_kinds = allow
    d = gate_legacy_identity_write(None, kind)
    out.append([mode, allow, kind, d.allowed, d.reason, want_allowed, want_reason])
print("GATE_MATRIX=" + json.dumps(out))
'''
    env = {k: v for k, v in os.environ.items() if not k.startswith("APP_")}
    env["APP_ENV"] = "test"
    env["APP_TEST_DB_URL"] = "postgresql://u:p@127.0.0.1:5432/asset_test"
    env["APP_DB_URL"] = env["APP_TEST_DB_URL"]
    proc = subprocess.run([sys.executable, "-c", code], cwd=BACKEND_DIR, env=env,
                          capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    line = next(l for l in proc.stdout.splitlines() if l.startswith("GATE_MATRIX="))
    import json

    for mode, allow, kind, allowed, reason, want_allowed, want_reason in json.loads(line[len("GATE_MATRIX="):]):
        assert allowed is want_allowed, (mode, allow, kind, reason)
        assert reason == want_reason, (mode, allow, kind, reason)
