"""215 E6：调度运营面只读看板（GET /govern/scheduler/ops-board）。

契约：看板零写操作；读现有 heartbeat_at/lease_owner/provider_heartbeat_at；
复用 govern.executor.manage 权限码；任务启停走既有端点（不在本端点新增写）。
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.models.governance_base import (
    AssetRole,
    AssetRolePermission,
    AssetUserRole,
    GovernAuditLog,
)
from app.models.governance_ops import SchedulerJob


def _seed_board_data(db_session) -> dict:
    """看板数据种子：scheduled/manual job、运行中质量 run（带心跳/租约）、身份 run、审计行。"""
    from app.models.governance_ops import SchedulerJob as SJ
    from app.models.identity_sync import IdentitySchedulerRun
    from app.models.quality_governance import QualityControl, QualityRun

    now = datetime.now(timezone.utc)
    db_session.add(SJ(job_type="metadata_scan", source_code="his", trigger_mode="scheduled",
                      schedule_cron="0 2 * * *", status="success"))
    db_session.add(SJ(job_type="quality_check", trigger_mode="manual", status="success"))
    control = QualityControl(control_code="e6-board-ctl", title="看板种子规则",
                             lifecycle_status="active")
    db_session.add(control)
    db_session.flush()
    db_session.add(QualityRun(
        run_code="e6-run-active", control_id=control.id, status="running",
        heartbeat_at=now - timedelta(seconds=30),
        lease_owner="worker-207-a", lease_expires_at=now + timedelta(seconds=270),
    ))
    db_session.add(QualityRun(
        run_code="e6-run-stale", control_id=control.id, status="running",
        heartbeat_at=now - timedelta(hours=2),
        lease_owner="worker-207-b", lease_expires_at=now - timedelta(hours=1),
    ))
    db_session.add(IdentitySchedulerRun(
        run_id="e6-nightly-1", triggered_by="nightly_cron", status="success",
        lock_holder="nightly-holder", started_at=now - timedelta(hours=3),
        finished_at=now - timedelta(hours=2),
        provider_code="jhemr", provider_heartbeat_at=now - timedelta(hours=2),
    ))
    db_session.add(GovernAuditLog(
        module="governance_ops", entity_type="scheduler_job", entity_ref="42",
        action="create", operator="e6-op", reason="215 E6 看板种子审计",
    ))
    db_session.commit()
    return {"control_id": control.id}


def test_ops_board_aggregates_and_writes_nothing(client, db_session):
    _seed_board_data(db_session)

    def _counts() -> dict:
        return {
            "jobs": db_session.scalar(select(func.count()).select_from(SchedulerJob)),
            "audits": db_session.scalar(select(func.count()).select_from(GovernAuditLog)),
        }

    before = _counts()
    resp = client.get("/api/v1/govern/scheduler/ops-board")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    after = _counts()
    assert before == after  # 零写：读看板不产生任何新行

    assert data["read_only"] is True
    switches = data["scheduler_switches"]
    for key in ("identity_nightly_enabled", "dict_medical_push_enabled",
                "query_schedule_enabled", "quality_execution_scheduler_enabled",
                "ai_context_cache_cleanup_enabled", "scheduler_timezone"):
        assert key in switches

    assert data["jobs_summary"]["by_trigger_mode"].get("scheduled") == 1
    assert data["jobs_summary"]["by_trigger_mode"].get("manual") == 1
    assert len(data["scheduled_jobs"]) == 1

    quality = data["worker_heartbeats"]["quality_runs"]
    by_code = {q["run_code"]: q for q in quality}
    assert by_code["e6-run-active"]["lease_active"] is True
    assert by_code["e6-run-active"]["heartbeat_age_seconds"] is not None
    assert by_code["e6-run-stale"]["lease_active"] is False
    assert by_code["e6-run-active"]["lease_owner"] == "worker-207-a"

    identity = data["worker_heartbeats"]["identity_nightly"]
    assert identity and identity[0]["provider_heartbeat_at"] is not None
    assert identity[0]["lock_holder"] == "nightly-holder"

    trail = data["scheduler_job_audit_trail"]
    assert any(t["operator"] == "e6-op" and t["action"] == "create" for t in trail)


def test_ops_board_denies_without_govern_permission(client, db_session):
    """复用权限码负例：无 govern.executor.manage 的角色必 403。"""
    from app.core.db import SessionLocal
    from app.models.governance import ApiKey

    user, token = "e6-board-viewer", "e6-board-token-215"
    db = SessionLocal()
    try:
        if not db.scalar(select(AssetRole).where(AssetRole.role_code == "e6_viewer")):
            db.add(AssetRole(role_code="e6_viewer", role_name_cn="看板只读测试角色", role_type="builtin"))
        if not db.scalar(select(AssetUserRole).where(
            AssetUserRole.user_identifier == user, AssetUserRole.role_code == "e6_viewer"
        )):
            db.add(AssetUserRole(user_identifier=user, role_code="e6_viewer", status="active"))
        if not db.scalar(select(AssetRolePermission).where(
            AssetRolePermission.role_code == "e6_viewer", AssetRolePermission.resource == "govern.executor.read"
        )):
            db.add(AssetRolePermission(role_code="e6_viewer", resource="govern.executor.read", action="access"))
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        if not db.query(ApiKey).filter(ApiKey.key_name == f"key-{user}").first():
            db.add(ApiKey(key_name=f"key-{user}", token_hash=token_hash, user_identifier=user))
        db.commit()
    finally:
        db.close()

    limited = TestClient(client.app, headers={"Authorization": f"Bearer {token}"})
    resp = limited.get("/api/v1/govern/scheduler/ops-board")
    # 统一 403 信封（DEF-09）不回显资源码；此处只验证拒绝语义
    assert resp.status_code == 403, resp.text
    assert resp.json()["code"] == 403
