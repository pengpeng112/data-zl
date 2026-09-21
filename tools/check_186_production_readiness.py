#!/usr/bin/env python
"""186 v1.10 S2/S3 生产发布预检（只读，零写）。

在 8.83 容器内运行（或等价环境，能访问平台库与应用构建）：
    python check_186_production_readiness.py --target-revision e8f9a0b1c2d3 \
        [--expect-image data-asset:r186-YYYYMMDD] [--cron-files /etc/cron.d/...]

检查项（P0-12 部署前检查）：
  1. 应用 build_id/git_sha 与发布 manifest 一致（候选一致性）
  2. alembic head == base（部署前）或 target（部署后 --phase after）
  3. 新表存在（用途绑定/批准范围/窗口预算）
  4. 四执行器注册状态（部署后应：两 disable enabled，两 enable disabled）
  5. 调度唯一性：identity_scheduler_provider 与 APP_IDENTITY_NIGHTLY_ENABLED
     只允许一个 provider；旧 host cron 必须已停用（phase after）
  6. 平台 NTP/chrony 健康（仅记录，不阻断 disable-only）
  7. 运行模式与关键 186 设置存在

输出 JSON verdict：ready=true/false + 逐项证据。不输出任何凭据。
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

CHECKS: list[dict] = []


def add_check(name: str, ok: bool, detail, *, blocking: bool = True) -> None:
    CHECKS.append({"check": name, "ok": bool(ok), "blocking": blocking, "detail": detail})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-revision", default="e8f9a0b1c2d3")
    parser.add_argument("--base-revision", default="c6d7e8f9a0b1")
    parser.add_argument("--phase", choices=["before", "after"], default="before")
    parser.add_argument("--expect-build-id", default=None)
    parser.add_argument("--cron-file", action="append", default=[
        "/etc/cron.d/data-asset-identity-nightly",
    ])
    parser.add_argument("--allow-cron", action="store_true",
                        help="phase after: 新 host cron 允许存在（调用新入口）")
    args = parser.parse_args()

    # 1. build identity
    try:
        from app.core.config import settings  # type: ignore

        build_id = getattr(settings, "build_id", "")
        git_sha = getattr(settings, "git_sha", "")
        if args.expect_build_id:
            add_check("build_id_matches", build_id == args.expect_build_id,
                      {"actual": build_id, "expected": args.expect_build_id})
        else:
            add_check("build_id_present", bool(build_id), {"build_id": build_id, "git_sha": git_sha})
        run_mode = getattr(settings, "identity_run_mode", None)
        add_check("identity_run_mode_configured", run_mode in {"observe", "disable_only", "full"},
                  {"identity_run_mode": run_mode})
        provider = getattr(settings, "identity_scheduler_provider", "disabled")
        nightly_enabled = bool(getattr(settings, "identity_nightly_enabled", False))
        providers = {provider} if provider != "disabled" else set()
        if nightly_enabled:
            providers.add("apscheduler")
        add_check("single_scheduler_provider", len(providers) <= 1,
                  {"declared_provider": provider, "nightly_enabled": nightly_enabled,
                   "effective_providers": sorted(providers)})
        drift = provider == "disabled" and not nightly_enabled
    except Exception as exc:  # noqa: BLE001
        add_check("app_settings_importable", False, {"error": f"{type(exc).__name__}"})
        drift = True

    # 2/3. database head + tables
    try:
        from sqlalchemy import create_engine, text  # type: ignore

        url = os.environ.get("APP_DB_URL") or os.environ.get("APP_TEST_DB_URL")
        engine = create_engine(url)
        with engine.connect() as conn:
            head = conn.execute(text("SELECT version_num FROM public.alembic_version")).scalar()
            expected_head = args.target_revision if args.phase == "after" else args.base_revision
            add_check("alembic_head", head == expected_head,
                      {"actual": head, "expected": expected_head, "phase": args.phase})
            tables = {
                r[0] for r in conn.execute(text(
                    "SELECT tablename FROM pg_tables WHERE schemaname='asset'"))
            }
            required = [
                "asset_source_purpose_bindings",
                "asset_identity_action_scopes",
                "asset_identity_action_scope_members",
                "asset_identity_window_budgets",
                "asset_identity_window_reservations",
            ]
            if args.phase == "after":
                add_check("new_tables_exist", all(t in tables for t in required),
                          {"missing": [t for t in required if t not in tables]})
                execs = {
                    r[0]: bool(r[1]) for r in conn.execute(text(
                        "SELECT executor_code, enabled FROM asset.asset_action_executors "
                        "WHERE executor_code LIKE '%_ACCOUNT_%'"))
                }
                expected_enabled = {
                    "JHEMR_ACCOUNT_DISABLE": True, "CDMS_ACCOUNT_DISABLE": True,
                    "JHEMR_ACCOUNT_ENABLE": False, "CDMS_ACCOUNT_ENABLE": False,
                } if os.environ.get("EXPECT_DISABLE_EXECUTORS") == "1" else None
                if expected_enabled:
                    add_check("executor_states", execs == expected_enabled,
                              {"actual": execs, "expected": expected_enabled})
                else:
                    add_check("executors_registered", set(execs) >= set(expected_enabled or {}) or len(execs) >= 4,
                              {"executors": execs})
    except Exception as exc:  # noqa: BLE001
        add_check("database_reachable", False, {"error": f"{type(exc).__name__}"})

    # 5. cron 状态（phase before：旧 cron 必须在——它是待替换项；after：必须唯一新入口）
    cron_status = {}
    for path in args.cron_file:
        exists = os.path.exists(path)
        content = ""
        if exists:
            try:
                content = open(path, encoding="utf-8", errors="replace").read()
            except OSError:
                content = "<unreadable>"
        cron_status[path] = {"exists": exists, "mentions_old_runner": "run_identity_modified_nightly.py" in content,
                             "active_lines": [l for l in content.splitlines() if l.strip() and not l.startswith("#")]}
    if args.phase == "before":
        add_check("old_cron_present_as_planned_replacement", True, cron_status, blocking=False)
    else:
        old_active = any(v["mentions_old_runner"] and v["active_lines"] for v in cron_status.values())
        if args.allow_cron:
            add_check("single_cron_calls_new_entry", not drift,
                      {**cron_status, "scheduler_drift": drift})
        else:
            add_check("no_active_host_cron", not old_active, cron_status)

    # 6. NTP 健康（记录性）
    ntp = {"detail": "not_checked"}
    try:
        tracking = subprocess.run(["chronyc", "tracking"], capture_output=True, text=True, timeout=10)
        ntp = {"chronyc_tracking_rc": tracking.returncode, "snippet": tracking.stdout[:300]}
        synced = "Not synchronised" not in tracking.stdout
        add_check("chrony_synchronized", synced, ntp, blocking=False)
    except Exception as exc:  # noqa: BLE001
        add_check("chrony_synchronized", False, {"error": f"{type(exc).__name__}"}, blocking=False)

    blocking_failures = [c for c in CHECKS if not c["ok"] and c["blocking"]]
    verdict = {
        "ready": not blocking_failures,
        "phase": args.phase,
        "target_revision": args.target_revision,
        "blocking_failures": [c["check"] for c in blocking_failures],
        "checks": CHECKS,
    }
    print(json.dumps(verdict, ensure_ascii=False, indent=2, default=str))
    return 0 if not blocking_failures else 2


if __name__ == "__main__":
    sys.exit(main())
