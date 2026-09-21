#!/usr/bin/env python
"""186 v1.10 P1-11：生产只读基线包（容器内执行，零写、零凭据输出）。

用法（8.83）：
    docker exec -i data-asset-api python - < collect_186_readonly_baseline.py
输出 stdout JSON：镜像内视角的运行时基线。宿主机事实（cron/chrony/docker）
由发布流程另行采集合并。P0-13 的 HMAC 对账在容器内计算指纹，不输出账号。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import text

from app.core.config import settings
from app.core.db import SessionLocal


def norm(v):
    if v is None:
        return None
    if isinstance(v, (bytes, memoryview)):
        return bytes(v).hex()[:2000]
    return str(v)[:800]


def main() -> int:
    out: dict = {"collected_at": datetime.now(timezone.utc).isoformat(), "scope": "container_readonly"}

    out["build"] = {
        "build_id": getattr(settings, "build_id", None),
        "git_sha": getattr(settings, "git_sha", None),
    }
    out["settings_186"] = {
        "identity_run_mode": getattr(settings, "identity_run_mode", None),
        "identity_dual_source_enforce": getattr(settings, "identity_dual_source_enforce", None),
        "identity_sync_enabled": getattr(settings, "identity_sync_enabled", None),
        "identity_nightly_enabled": getattr(settings, "identity_nightly_enabled", None),
        "identity_scheduler_provider": getattr(settings, "identity_scheduler_provider", None),
        "identity_phase_d_approval_version_set": bool(getattr(settings, "identity_phase_d_approval_version", "")),
        "identity_clock_sampling_enabled": getattr(settings, "identity_clock_sampling_enabled", None),
        "identity_drift_readback_enabled": getattr(settings, "identity_drift_readback_enabled", None),
        "identity_account_state_batch_limit": getattr(settings, "identity_account_state_batch_limit", None),
        "identity_account_state_total_cap": getattr(settings, "identity_account_state_total_cap", None),
        "identity_window_max_persons": getattr(settings, "identity_window_max_persons", None),
    }

    db = SessionLocal()
    try:
        head = db.execute(text("SELECT version_num FROM public.alembic_version")).scalar()
        out["alembic_head"] = head

        execs = db.execute(text(
            "SELECT executor_code, enabled, target_system_code, target_source_code, require_approval "
            "FROM asset.asset_action_executors ORDER BY executor_code")).fetchall()
        out["action_executors"] = [
            {"code": r[0], "enabled": bool(r[1]), "target": r[2], "source": r[3], "require_approval": bool(r[4])}
            for r in execs
        ]

        bindings = db.execute(text(
            "SELECT source_code, purpose, enabled, credential_status, write_credential_ref IS NOT NULL AS has_ref "
            "FROM asset.asset_source_purpose_bindings ORDER BY source_code, purpose")).fetchall()
        out["purpose_bindings"] = [
            {"source": r[0], "purpose": r[1], "enabled": bool(r[2]), "credential_status": r[3], "has_ref": bool(r[4])}
            for r in bindings
        ]

        sources = db.execute(text(
            "SELECT source_code, write_policy, write_credential_ref IS NOT NULL AS has_write_ref, "
            "credential_status, enabled FROM asset.asset_data_sources "
            "WHERE source_code IN ('jhemr_vastbase_10_10_8_177','paperless_cdms_oracle_10_10_10_93','his_source_10_10_10_15') "
            "ORDER BY source_code")).fetchall()
        out["source_registry_write_summary"] = [
            {"source": r[0], "write_policy": r[1], "has_write_ref": bool(r[2]), "credential_status": r[3], "enabled": bool(r[4])}
            for r in sources
        ]

        # 保护登记与托管关系规模（P0-13 对账基数；不输出任何账号/指纹全文）
        out["identity_counts"] = {
            "protected_accounts": db.execute(text("SELECT COUNT(*) FROM asset.asset_identity_protected_accounts")).scalar(),
            "managed_relations_active": db.execute(text(
                "SELECT COUNT(*) FROM asset.asset_identity_managed_relations WHERE status='active'")).scalar(),
            "managed_relations_total": db.execute(text(
                "SELECT COUNT(*) FROM asset.asset_identity_managed_relations")).scalar(),
            "account_state_decisions": db.execute(text(
                "SELECT COUNT(*) FROM asset.asset_identity_account_state_decisions")).scalar(),
            "approved_scopes": db.execute(text(
                "SELECT COUNT(*) FROM asset.asset_identity_action_scopes")).scalar(),
            "window_budgets": db.execute(text(
                "SELECT COUNT(*) FROM asset.asset_identity_window_budgets")).scalar(),
        }

        # 最近夜跑（错误类聚合；success/partial/failed 按真实失败呈现）
        runs = db.execute(text(
            "SELECT run_id, status, started_at, finished_at, circuit_breaker_triggered, "
            "circuit_breaker_dimension, error_message IS NOT NULL AS has_error "
            "FROM asset.asset_identity_scheduler_runs ORDER BY started_at DESC LIMIT 5")).fetchall()
        out["recent_scheduler_runs"] = [
            {"run_id": r[0], "status": r[1], "started_at": norm(r[2]), "finished_at": norm(r[3]),
             "cb_triggered": bool(r[4]), "cb_dimension": r[5], "has_error_message": bool(r[6])}
            for r in runs
        ]
    finally:
        db.close()

    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
