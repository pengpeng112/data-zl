"""166 F7/D5：权限种子幂等收敛 + 矩阵 live 实证（ai_user/asset_viewer 无 manage/confirm）。

- 种子走 /permissions/seed（153 B5 幂等模式）：首跑补 probe.finding.manage，二跑收敛 0。
- live 403：ai_user 角色（read 有/manage 无）调 transition 必 403；asset_viewer 同理。
"""
from __future__ import annotations

import hashlib
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models.governance_base import AssetRole, AssetRolePermission, AssetUserRole
from app.services.probe_service import register_run, upsert_finding


def _role_client(client: TestClient, *, role_code: str, resources: list[str], token: str, user: str):
    from app.core.db import SessionLocal
    from app.models.governance import ApiKey

    db = SessionLocal()
    try:
        if not db.scalar(select(AssetRole).where(AssetRole.role_code == role_code)):
            db.add(AssetRole(role_code=role_code, role_name_cn=role_code, role_type="builtin"))
        if not db.scalar(select(AssetUserRole).where(
            AssetUserRole.user_identifier == user, AssetUserRole.role_code == role_code
        )):
            db.add(AssetUserRole(user_identifier=user, role_code=role_code, status="active"))
        for res in resources:
            if not db.scalar(select(AssetRolePermission).where(
                AssetRolePermission.role_code == role_code,
                AssetRolePermission.resource == res,
                AssetRolePermission.action == "access",
            )):
                db.add(AssetRolePermission(role_code=role_code, resource=res, action="access"))
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        existing = db.query(ApiKey).filter(ApiKey.key_name == f"key-{user}").first()
        if not existing:
            db.add(ApiKey(key_name=f"key-{user}", token_hash=token_hash, user_identifier=user))
        else:
            existing.token_hash = token_hash
            existing.token = None
            existing.user_identifier = user
            existing.enabled = True
        db.commit()
    finally:
        db.close()
    return TestClient(client.app, headers={"Authorization": f"Bearer {token}"})


@pytest.fixture()
def finding_id(db_session) -> int:
    register_run(db_session, run_id="probe-t-p0001", status="done")
    upsert_finding(
        db_session, run_id="probe-t-p0001", probe_type="R-REF", system_pair="HIS(单库)",
        object_desc="权限矩阵对象", metric_name="perm_metric", metric_value=42.0, metric_unit="%",
        threshold=1.0, window_start=date(2026, 7, 1), window_end=date(2026, 7, 31),
        severity="P2", evidence_sql="SELECT 1 FROM DUAL WHERE D >= :START_DATE",
    )
    db_session.commit()
    from app.models.probe import AssetProbeFinding

    row = db_session.scalar(select(AssetProbeFinding).order_by(AssetProbeFinding.id.desc()))
    return row.id


class TestSeedIdempotent:
    def test_seed_creates_manage_then_converges_to_zero(self, client):
        from app.api.v1.permissions import ROLE_DEFAULT_PERMISSIONS

        # 首跑：至少补上 manage（fresh 测试库 + 平台角色种子行）
        first = client.post("/api/v1/permissions/seed")
        assert first.status_code == 200, first.text
        # 二跑：幂等收敛 0
        second = client.post("/api/v1/permissions/seed")
        assert second.status_code == 200
        assert second.json()["data"]["created_permissions"] == 0
        # manage 已按矩阵落库（platform_admin/quality_admin）
        from app.core.db import SessionLocal

        db = SessionLocal()
        try:
            granted = {
                r.role_code
                for r in db.scalars(
                    select(AssetRolePermission).where(
                        AssetRolePermission.resource == "probe.finding.manage",
                        AssetRolePermission.action == "access",
                    )
                ).all()
            }
        finally:
            db.close()
        expected = {
            role
            for role, res in ROLE_DEFAULT_PERMISSIONS.items()
            if "probe.finding.manage" in res
        }
        assert granted == expected
        assert {"platform_admin", "quality_admin"} <= granted


class TestLiveMatrix403:
    def test_ai_user_read_ok_manage_403(self, client, finding_id):
        ai = _role_client(
            client, role_code="ai_user",
            resources=["probe.finding.read", "value_domain.read", "value_domain.submit"],
            token="test-token-166-ai", user="test-166-ai",
        )
        # read 可见列表（165 A8 口径）
        assert ai.get("/api/v1/probe-findings").status_code == 200
        # manage 缺失 → transition 403
        r = ai.post(
            f"/api/v1/probe-findings/{finding_id}/transition",
            json={"action": "resolve", "reason": "越权尝试"},
        )
        assert r.status_code == 403
        # value_domain.confirm 同样无（149 矩阵保持）
        assert ai.patch(
            "/api/v1/value-domains/1/confirm", json={"reason": "x"}
        ).status_code == 403

    def test_asset_viewer_read_ok_manage_403(self, client, finding_id):
        viewer = _role_client(
            client, role_code="asset_viewer",
            resources=["probe.finding.read", "value_domain.read"],
            token="test-token-166-viewer", user="test-166-viewer",
        )
        assert viewer.get("/api/v1/probe-findings").status_code == 200
        assert viewer.post(
            f"/api/v1/probe-findings/{finding_id}/transition",
            json={"action": "confirm", "reason": "越权尝试"},
        ).status_code == 403

    def test_quality_admin_can_manage(self, client, finding_id):
        qa = _role_client(
            client, role_code="quality_admin",
            resources=["probe.finding.read", "probe.finding.manage"],
            token="test-token-166-qa", user="test-166-qa",
        )
        r = qa.post(
            f"/api/v1/probe-findings/{finding_id}/transition",
            json={"action": "resolve", "reason": "质量线裁决"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "resolved"
