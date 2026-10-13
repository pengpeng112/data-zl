"""215 E9：/health 扩展（alembic 版本对拍 + worker 心跳）与成功日志 request_id。"""
from __future__ import annotations

import logging

from app.models.quality_governance import QualityControl, QualityRun


def test_health_carries_alembic_and_worker_summary(client, db_session):
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    control = QualityControl(control_code="e9-health-ctl", title="健康检查种子", lifecycle_status="active")
    db_session.add(control)
    db_session.flush()
    db_session.add(QualityRun(
        run_code="e9-run-1", control_id=control.id, status="running",
        lease_owner="e9-worker", lease_expires_at=now + timedelta(minutes=5),
        heartbeat_at=now,
    ))
    db_session.commit()

    resp = client.get("/api/v1/health")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["database"] == "connected"

    alembic = data["alembic"]
    assert set(alembic) >= {"head", "current", "match"}
    assert alembic["match"] is True  # 测试库已 upgrade 到链 head
    assert alembic["head"]  # head 非空（离线解析成功）

    workers = data["workers"]
    assert workers["quality_runs"]["running_or_waiting"] >= 1
    assert workers["quality_runs"]["lease_active"] >= 1
    assert "identity_nightly" in workers


def test_health_live_unchanged(client):
    """liveness 端点不依赖数据库——扩展不得波及该语义。"""
    resp = client.get("/api/v1/health/live")
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "alive"
    assert "alembic" not in resp.json()["data"]


def test_success_access_log_carries_request_id(client, caplog):
    """215 E9：成功访问日志贯穿 request_id（此前仅异常信封携带）。"""
    with caplog.at_level(logging.INFO, logger="request"):
        resp = client.get("/api/v1/health/live")
        assert resp.status_code == 200
    matched = [r for r in caplog.records if "request_id=" in r.getMessage()]
    assert matched, "成功访问日志应包含 request_id="
    rid = matched[-1].getMessage().split("request_id=")[-1].strip()
    assert len(rid) >= 8  # uuid hex 非空
