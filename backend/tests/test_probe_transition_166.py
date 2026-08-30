"""166 F5：finding 人工终态流转——B6 迁移表全 12 条 + 非法值 422 + 执行器身份 403 + 审计。

迁移表（人工四值互转+重开全允许，仅禁同态原地转）：
  open→{confirmed,false_positive,resolved}
  confirmed→{open,false_positive,resolved}
  false_positive→{open,confirmed,resolved}
  resolved→{open,confirmed,false_positive}
"""
from __future__ import annotations

import hashlib
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from app.models.governance_base import AssetRole, AssetRolePermission, AssetUserRole, GovernAuditLog
from app.models.probe import AssetProbeFinding
from app.services.probe_service import register_run, transition_finding, upsert_finding

STATUSES = ["open", "confirmed", "false_positive", "resolved"]
LEGAL_TRANSITIONS = [(f, t) for f in STATUSES for t in STATUSES if f != t]  # 12 条

EXECUTOR_TOKEN = "test-token-probe-executor-166"
EXECUTOR_USER = "probe:probe-20260830-094723"


def _seed_finding(db_session, *, status: str | None = None, metric: str = "doctor_code_missing_rate"):
    register_run(db_session, run_id="probe-t-t0001", status="done")
    upsert_finding(
        db_session, run_id="probe-t-t0001", probe_type="R-REF", system_pair="HIS(单库)",
        object_desc=f"对象-{metric}", metric_name=metric, metric_value=83.2, metric_unit="%",
        threshold=1.0, window_start=date(2026, 7, 1), window_end=date(2026, 7, 31),
        severity="P2", evidence_sql="SELECT COUNT(*) FROM DUAL WHERE D >= :START_DATE",
    )
    db_session.commit()
    row = db_session.scalar(select(AssetProbeFinding).order_by(AssetProbeFinding.id.desc()))
    if status is not None and status != "open":
        # 夹具直改库构造终态（同 165 E5 先例：服务层无终态写入）
        db_session.execute(
            text(f"UPDATE asset.asset_probe_findings SET status='{status}' WHERE id={row.id}")
        )
        db_session.commit()
    return row.id


def _transition(client, fid: int, action: str, reason: str = "人工裁决", to_status: str | None = None):
    body: dict = {"action": action, "reason": reason}
    if to_status is not None:
        body["to_status"] = to_status
    return client.post(f"/api/v1/probe-findings/{fid}/transition", json=body)


@pytest.fixture()
def executor_client(client: TestClient) -> TestClient:
    """持 platform_admin（含 manage 码）但身份为执行器（probe: 前缀）的客户端。

    证明身份禁令独立于权限授予：即便授了 manage，probe: 前缀仍 403。
    """
    from app.core.db import SessionLocal
    from app.models.governance import ApiKey

    db = SessionLocal()
    try:
        if not db.scalar(select(AssetRole).where(AssetRole.role_code == "platform_admin")):
            db.add(AssetRole(role_code="platform_admin", role_name_cn="平台管理员", role_type="builtin"))
        if not db.scalar(select(AssetUserRole).where(
            AssetUserRole.user_identifier == EXECUTOR_USER,
            AssetUserRole.role_code == "platform_admin",
        )):
            db.add(AssetUserRole(user_identifier=EXECUTOR_USER, role_code="platform_admin", status="active"))
        token_hash = hashlib.sha256(EXECUTOR_TOKEN.encode("utf-8")).hexdigest()
        existing = db.query(ApiKey).filter(ApiKey.key_name == "test-probe-executor-166").first()
        if not existing:
            db.add(ApiKey(key_name="test-probe-executor-166", token_hash=token_hash, user_identifier=EXECUTOR_USER))
        else:
            existing.token_hash = token_hash
            existing.token = None
            existing.user_identifier = EXECUTOR_USER
            existing.enabled = True
        db.commit()
    finally:
        db.close()
    return TestClient(client.app, headers={"Authorization": f"Bearer {EXECUTOR_TOKEN}"})


class TestTransitionMatrix:
    @pytest.mark.parametrize("from_status,to_status", LEGAL_TRANSITIONS)
    def test_legal_transition(self, client, db_session, from_status, to_status):
        fid = _seed_finding(db_session, status=from_status, metric=f"m_{from_status}_{to_status}")
        r = _transition(client, fid, "reclassify", to_status=to_status)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == to_status

    def test_same_status_transition_422(self, client, db_session):
        fid = _seed_finding(db_session, status="confirmed")
        assert _transition(client, fid, "reclassify", to_status="confirmed").status_code == 422

    def test_invalid_status_value_422(self, client, db_session):
        fid = _seed_finding(db_session)
        r = _transition(client, fid, "reclassify", to_status="closed")
        assert r.status_code == 422

    def test_action_without_to_status_422(self, client, db_session):
        fid = _seed_finding(db_session)
        assert _transition(client, fid, "reclassify").status_code == 422
        assert _transition(client, fid, "unknown_action").status_code == 422

    def test_reason_required_422(self, client, db_session):
        fid = _seed_finding(db_session)
        r = client.post(f"/api/v1/probe-findings/{fid}/transition",
                        json={"action": "confirm", "reason": ""})
        assert r.status_code == 422
        r = client.post(f"/api/v1/probe-findings/{fid}/transition", json={"action": "confirm"})
        assert r.status_code == 422

    def test_finding_not_found_404(self, client, db_session):
        assert _transition(client, 999999, "confirm").status_code == 404


class TestTransitionGuardrails:
    def test_executor_identity_403_even_with_admin_role(self, executor_client, db_session):
        fid = _seed_finding(db_session)
        r = _transition(executor_client, fid, "resolve")
        assert r.status_code == 403
        assert "执行器" in r.json()["detail"]

    def test_audit_row_written_with_reason(self, client, db_session):
        fid = _seed_finding(db_session, status="open", metric="m_audit")
        _transition(client, fid, "resolve", reason="已联系业务侧整改")
        row = db_session.scalar(
            select(GovernAuditLog).where(
                GovernAuditLog.module == "probe",
                GovernAuditLog.action == "transition",
                GovernAuditLog.entity_ref == str(fid),
            )
        )
        assert row is not None
        assert row.reason == "已联系业务侧整改"
        assert row.before_data == {"status": "open"}
        assert row.after_data["status"] == "resolved"

    def test_resolved_snapshot_set_and_cleared_on_reopen(self, client, db_session):
        fid = _seed_finding(db_session, metric="m_snapshot")
        r1 = _transition(client, fid, "resolve")
        assert r1.json()["resolved_by"] == "test-platform-admin"
        assert r1.json()["resolved_at"] is not None
        r2 = _transition(client, fid, "reopen", reason="复发重开")
        assert r2.json()["status"] == "open"
        assert r2.json()["resolved_by"] is None and r2.json()["resolved_at"] is None

    def test_service_state_machine_pure(self, db_session):
        from app.services.probe_service import finding_transition_allowed
        for f, t in LEGAL_TRANSITIONS:
            assert finding_transition_allowed(f, t), f"{f}->{t} 应合法"
        for s in STATUSES:
            assert not finding_transition_allowed(s, s)
        assert not finding_transition_allowed("open", "closed")
        assert not finding_transition_allowed("closed", "open")

    def test_transition_direct_service_sets_fields(self, db_session):
        fid = _seed_finding(db_session, metric="m_direct")
        row = transition_finding(db_session, finding_id=fid, to_status="false_positive",
                                 reason="口径误报", operator="reviewer-a")
        assert row.status == "false_positive"
        assert row.resolved_by is None  # 仅 resolved 记录快照
        db_session.commit()
