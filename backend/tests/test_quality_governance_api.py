"""174 S4/S5: 质量治理台账 API 测试（RBAC、数据范围、命令端点、导出六硬约束）。

数据范围矩阵（174 §7）：
  - quality.issue.read → mine/department；
  - all 需 quality.issue.read_all（普通处理人 403）；
  - 越权读取详情/事件/观测 403；
  - verify 不能由最后提交待复测的同一经办人完成。
"""

from __future__ import annotations

import hashlib
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models.governance import ApiKey
from app.models.governance_base import AssetRole, AssetRolePermission, AssetUserRole
from app.models.identity import IdentityPerson
from app.models.quality_governance import QualityControl, QualityIssue, QualityObservation
from app.services import quality_governance_service as qgs

_TEST_CONTROL = "DQ-API-TST-001"


def _role_client(client: TestClient, *, role_code: str, resources: list[str], token: str, user: str):
    """最小角色 + ApiKey 登记后返回带该 token 的 TestClient（166 先例）。"""
    from app.core.db import SessionLocal

    db = SessionLocal()
    try:
        if not db.scalar(select(AssetRole).where(AssetRole.role_code == role_code)):
            db.add(AssetRole(role_code=role_code, role_name_cn=role_code, role_type="builtin"))
        if not db.scalar(
            select(AssetUserRole).where(
                AssetUserRole.user_identifier == user, AssetUserRole.role_code == role_code
            )
        ):
            db.add(AssetUserRole(user_identifier=user, role_code=role_code, status="active"))
        for res in resources:
            if not db.scalar(
                select(AssetRolePermission).where(
                    AssetRolePermission.role_code == role_code,
                    AssetRolePermission.resource == res,
                    AssetRolePermission.action == "access",
                )
            ):
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
def active_control(db_session) -> dict:
    """建一个激活清单 + active 检测器，返回 id。"""
    db = db_session
    control = db.scalar(select(QualityControl).where(QualityControl.control_code == _TEST_CONTROL))
    if control is None:
        control = QualityControl(
            control_code=_TEST_CONTROL,
            title="API 测试清单",
            lifecycle_status="active",
            dimension="completeness",
            category="R-REF",
            primary_system_code="HIS",
            metric_name="api_metric",
            metric_unit="%",
            comparator="gt",
            threshold_value=1.0,
            default_severity="medium",
            default_priority="P2",
            default_dept_code="D-API",
        )
        db.add(control)
        db.flush()
        from app.models.quality_governance import QualityControlDetector

        db.add(
            QualityControlDetector(
                control_id=control.id,
                detector_kind="probe_template",
                detector_ref="TST-API",
                status="active",
                result_mapping={"probe_type": "R-REF", "metric_name": "api_metric"},
            )
        )
        db.commit()
    return {"id": control.id, "code": control.control_code}


def _ingest_fail(client: TestClient, control_id: int, run_key: str, *, scope: str = "api-scope"):
    return client.post(
        "/api/v1/quality-observations/ingest",
        json={
            "control_id": control_id,
            "run_key": run_key,
            "scope_key": scope,
            "result_status": "fail",
            "metric_value": 5.5,
            "metric_unit": "%",
            "source_kind": "manual",
        },
    )


class TestRoutePrecedence:
    def test_assignment_options_not_swallowed_by_id_route(self, client):
        r = client.get("/api/v1/quality-issues/assignment-options/departments")
        assert r.status_code == 200
        assert "items" in r.json()

    def test_export_registered_before_id_route(self):
        from pathlib import Path

        src = Path(__file__).resolve().parents[1] / "app" / "api" / "v1" / "quality_issues.py"
        text = src.read_text(encoding="utf-8")
        assert text.index('@router.post("/export")') < text.index('@router.get("/{issue_id}")')

    def test_summary_route(self, client):
        r = client.get("/api/v1/quality-issues/summary")
        assert r.status_code == 200
        assert "by_system" in r.json()

    def test_unauthenticated_401(self):
        anon = TestClient(client_app())
        r = anon.get("/api/v1/quality-issues")
        assert r.status_code == 401


def client_app():
    from app.main import app

    return app


class TestRbacAndScope:
    def test_limited_user_cannot_scope_all(self, client):
        limited = _role_client(
            client,
            role_code="qg_handler",
            resources=["quality.issue.read", "quality.issue.handle"],
            token="tok-qg-handler",
            user="qg-handler-1",
        )
        r = limited.get("/api/v1/quality-issues", params={"scope": "all"})
        assert r.status_code == 403

    def test_limited_user_mine_scope_ok(self, client, active_control):
        limited = _role_client(
            client,
            role_code="qg_handler",
            resources=["quality.issue.read", "quality.issue.handle"],
            token="tok-qg-handler",
            user="qg-handler-1",
        )
        r = limited.get("/api/v1/quality-issues", params={"scope": "mine"})
        assert r.status_code == 200

    def test_limited_user_cannot_ingest(self, client, active_control):
        limited = _role_client(
            client,
            role_code="qg_handler",
            resources=["quality.issue.read", "quality.issue.handle"],
            token="tok-qg-handler",
            user="qg-handler-1",
        )
        r = limited.post(
            "/api/v1/quality-observations/ingest",
            json={
                "control_id": active_control["id"],
                "run_key": "rbac-r1",
                "scope_key": "rbac-scope",
                "result_status": "fail",
            },
        )
        assert r.status_code == 403

    def test_handler_sees_only_own_department(self, client, db_session, active_control):
        db = db_session
        # 经办人身份 + 科室 D-API
        if not db.scalar(select(IdentityPerson).where(IdentityPerson.person_code == "qg-handler-1")):
            db.add(
                IdentityPerson(
                    person_code="qg-handler-1", person_name_cn="处理甲", dept_code="D-API"
                )
            )
            db.commit()
        # 建两条问题：一条 D-API，一条无科室
        qgs.create_manual_issue(db, title="本科室问题", responsible_dept_code="D-API", actor="t")
        qgs.create_manual_issue(db, title="无关问题", responsible_dept_code="D-OTHER", actor="t")
        db.commit()
        limited = _role_client(
            client,
            role_code="qg_handler",
            resources=["quality.issue.read", "quality.issue.handle"],
            token="tok-qg-handler",
            user="qg-handler-1",
        )
        r = limited.get("/api/v1/quality-issues", params={"scope": "department", "page_size": 50})
        assert r.status_code == 200
        titles = [i["title"] for i in r.json()["items"]]
        assert "本科室问题" in titles
        assert "无关问题" not in titles

    def test_detail_access_denied_out_of_scope(self, client, db_session):
        db = db_session
        issue = qgs.create_manual_issue(
            db, title="越权目标", responsible_dept_code="D-SECRET", actor="t"
        )
        db.commit()
        limited = _role_client(
            client,
            role_code="qg_handler",
            resources=["quality.issue.read", "quality.issue.handle"],
            token="tok-qg-handler",
            user="qg-handler-1",
        )
        r = limited.get(f"/api/v1/quality-issues/{issue.id}")
        assert r.status_code == 403
        r2 = limited.get(f"/api/v1/quality-issues/{issue.id}/events")
        assert r2.status_code == 403
        r3 = limited.get(f"/api/v1/quality-issues/{issue.id}/observations")
        assert r3.status_code == 403

    def test_assign_and_accept_risk_out_of_scope_forbidden(self, client, db_session):
        db = db_session
        issue = qgs.create_manual_issue(
            db, title="越权分派目标", responsible_dept_code="D-SECRET", actor="t"
        )
        db.commit()
        limited = _role_client(
            client,
            role_code="qg_assigner",
            resources=[
                "quality.issue.read",
                "quality.issue.assign",
                "quality.issue.accept_risk",
            ],
            token="tok-qg-assigner",
            user="qg-assigner-1",
        )
        r = limited.post(
            f"/api/v1/quality-issues/{issue.id}/assign",
            json={"expected_lock_version": issue.lock_version, "reason": "越权分派"},
        )
        assert r.status_code == 403
        r2 = limited.post(
            f"/api/v1/quality-issues/{issue.id}/accept-risk",
            json={
                "expected_lock_version": issue.lock_version,
                "risk_reason": "越权风险接受",
                "risk_approver": "nobody",
                "risk_review_at": "2099-01-01",
            },
        )
        assert r2.status_code == 403

    def test_read_all_sees_everything(self, client, db_session):
        db = db_session
        qgs.create_manual_issue(db, title="全院可见", responsible_dept_code="D-ANY", actor="t")
        db.commit()
        admin_all = _role_client(
            client,
            role_code="qg_viewer_all",
            resources=["quality.issue.read", "quality.issue.read_all"],
            token="tok-qg-all",
            user="qg-all-1",
        )
        r = admin_all.get("/api/v1/quality-issues", params={"scope": "all", "page_size": 50})
        assert r.status_code == 200
        assert any(i["title"] == "全院可见" for i in r.json()["items"])


class TestFullLifecycleViaApi:
    def test_fail_to_resolve_and_recurrence(self, client, db_session, active_control):
        # 1) FAIL 首次建单
        r = _ingest_fail(client, active_control["id"], "api-r1")
        assert r.status_code == 200, r.text
        assert r.json()["outcome"] == "issue_created"
        issue_id = r.json()["issue_id"]

        # 2) 同 run_key 重放不重复建单
        r = _ingest_fail(client, active_control["id"], "api-r1")
        assert r.json()["outcome"] == "duplicate"

        # 3) 新 run_key 同 scope 更新
        r = _ingest_fail(client, active_control["id"], "api-r2")
        assert r.json()["outcome"] == "issue_updated"

        detail = client.get(f"/api/v1/quality-issues/{issue_id}")
        assert detail.status_code == 200
        lv = detail.json()["lock_version"]

        # 4) 通用 transition 拒绝直通 resolved
        r = client.post(
            f"/api/v1/quality-issues/{issue_id}/transition",
            json={"to_status": "resolved", "expected_lock_version": lv, "reason": "绕过"},
        )
        assert r.status_code == 409

        # 5) acknowledge → assign → in_progress
        r = client.post(
            f"/api/v1/quality-issues/{issue_id}/transition",
            json={"to_status": "acknowledged", "expected_lock_version": lv, "reason": "确认"},
        )
        assert r.status_code == 200
        lv = r.json()["lock_version"]

        r = client.post(
            f"/api/v1/quality-issues/{issue_id}/assign",
            json={
                "expected_lock_version": lv,
                "responsible_dept_code": "D-API",
                "responsible_person_code": "qg-handler-1",
                "assignee_user_identifier": "qg-handler-1",
                "reason": "分派科室",
            },
        )
        assert r.status_code == 200
        assert r.json()["status"] == "assigned"
        lv = r.json()["lock_version"]
        assert "request_verification" in r.json()["allowed_actions"]

        # 6) 分派前缺 action_plan 的 waiting_verify → 422
        r = client.post(
            f"/api/v1/quality-issues/{issue_id}/request-verification",
            json={"expected_lock_version": lv, "reason": "完成"},
        )
        assert r.status_code == 422

        # 7) 经办人提交待复测
        r = client.post(
            f"/api/v1/quality-issues/{issue_id}/request-verification",
            json={
                "expected_lock_version": lv,
                "reason": "完成整改",
                "action_plan": "补录医生工号并加必填校验",
            },
        )
        assert r.status_code == 200
        assert r.json()["status"] == "waiting_verify"
        lv = r.json()["lock_version"]

        # 8) 平台管理员（非提交人）验证通过 → resolved
        r = client.post(
            f"/api/v1/quality-issues/{issue_id}/verify",
            json={
                "expected_lock_version": lv,
                "passed": True,
                "reason": "复测通过：缺失率回落至 0.2%",
                "resolution_summary": "已修复",
            },
        )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "resolved"

        # 9) 关闭后再 FAIL → 复发新问题
        r = _ingest_fail(client, active_control["id"], "api-r3")
        assert r.json()["outcome"] == "issue_created"
        new_id = r.json()["issue_id"]
        assert new_id != issue_id
        new_detail = client.get(f"/api/v1/quality-issues/{new_id}").json()
        assert new_detail["recurrence_of_issue_id"] == issue_id
        assert new_detail["recurrence_no"] == 1

    def test_verify_same_requester_forbidden(self, client, db_session, active_control):
        r = _ingest_fail(client, active_control["id"], "api-verify-r1", scope="api-verify")
        issue_id = r.json()["issue_id"]
        handler = _role_client(
            client,
            role_code="qg_handler",
            resources=["quality.issue.read", "quality.issue.read_all", "quality.issue.handle", "quality.issue.verify"],
            token="tok-qg-handler",
            user="qg-handler-1",
        )
        detail = handler.get(f"/api/v1/quality-issues/{issue_id}")
        lv = detail.json()["lock_version"]
        for to_status in ("acknowledged", "assigned"):
            r = handler.post(
                f"/api/v1/quality-issues/{issue_id}/transition",
                json={"to_status": to_status, "expected_lock_version": lv, "reason": "推进"},
            )
            lv = r.json()["lock_version"]
        r = handler.post(
            f"/api/v1/quality-issues/{issue_id}/request-verification",
            json={"expected_lock_version": lv, "reason": "完成", "action_plan": "修复"},
        )
        assert r.status_code == 200
        lv = r.json()["lock_version"]
        # 同一经办人自证 → 403（非管理员）
        r = handler.post(
            f"/api/v1/quality-issues/{issue_id}/verify",
            json={"expected_lock_version": lv, "passed": True, "reason": "自己验证"},
        )
        assert r.status_code == 403

    def test_stale_lock_409(self, client, db_session, active_control):
        r = _ingest_fail(client, active_control["id"], "api-lock-r1", scope="api-lock")
        issue_id = r.json()["issue_id"]
        r = client.post(
            f"/api/v1/quality-issues/{issue_id}/transition",
            json={"to_status": "acknowledged", "expected_lock_version": 999, "reason": "过期锁"},
        )
        assert r.status_code == 409

    def test_false_positive_only_from_new(self, client, db_session, active_control):
        r = _ingest_fail(client, active_control["id"], "api-fp-r1", scope="api-fp")
        issue_id = r.json()["issue_id"]
        detail = client.get(f"/api/v1/quality-issues/{issue_id}").json()
        r = client.post(
            f"/api/v1/quality-issues/{issue_id}/mark-false-positive",
            json={
                "expected_lock_version": detail["lock_version"],
                "false_positive_reason": "口径误判",
                "suppressed_until": str(date.today() + timedelta(days=14)),
                "reason": "误报",
            },
        )
        assert r.status_code == 200
        assert r.json()["status"] == "false_positive"
        lv = r.json()["lock_version"]
        # acknowledged 状态再误报 → 409
        r2 = _ingest_fail(client, active_control["id"], "api-fp-r2", scope="api-fp2")
        r3 = client.post(
            f"/api/v1/quality-issues/{r2.json()['issue_id']}/transition",
            json={"to_status": "acknowledged", "expected_lock_version": client.get(
                f"/api/v1/quality-issues/{r2.json()['issue_id']}"
            ).json()["lock_version"], "reason": "确认"},
        )
        lv3 = r3.json()["lock_version"]
        r4 = client.post(
            f"/api/v1/quality-issues/{r2.json()['issue_id']}/mark-false-positive",
            json={
                "expected_lock_version": lv3,
                "false_positive_reason": "口径误判",
                "suppressed_until": str(date.today() + timedelta(days=14)),
                "reason": "误报",
            },
        )
        assert r4.status_code == 409

    def test_accept_risk_requires_fields(self, client, db_session, active_control):
        r = _ingest_fail(client, active_control["id"], "api-risk-r1", scope="api-risk")
        issue_id = r.json()["issue_id"]
        lv = client.get(f"/api/v1/quality-issues/{issue_id}").json()["lock_version"]
        r = client.post(
            f"/api/v1/quality-issues/{issue_id}/transition",
            json={"to_status": "acknowledged", "expected_lock_version": lv, "reason": "确认"},
        )
        lv = r.json()["lock_version"]
        # 缺复审日期 → 422
        r = client.post(
            f"/api/v1/quality-issues/{issue_id}/accept-risk",
            json={
                "expected_lock_version": lv,
                "risk_reason": "低风险",
                "risk_approver": "科主任",
            },
        )
        assert r.status_code == 422
        # 补齐 → 200
        r = client.post(
            f"/api/v1/quality-issues/{issue_id}/accept-risk",
            json={
                "expected_lock_version": lv,
                "risk_reason": "历史数据，修复成本高",
                "risk_approver": "质量委员会",
                "risk_review_at": str(date.today() + timedelta(days=90)),
            },
        )
        assert r.status_code == 200
        assert r.json()["status"] == "accepted_risk"


class TestControlsApi:
    def test_create_activate_and_no_detector_guard(self, client, db_session):
        code = "DQ-API-CREATE-TMP"
        r = client.post(
            "/api/v1/quality-controls",
            json={
                "control_code": code,
                "title": "临时清单",
                "dimension": "completeness",
                "category": "R-REF",
                "primary_system_code": "HIS",
            },
        )
        assert r.status_code == 200, r.text
        cid = r.json()["id"]
        lock0 = client.get(f"/api/v1/quality-controls/{cid}").json()["lock_version"]
        # 无 active 检测器且非 MANUAL → 激活 422
        r = client.post(f"/api/v1/quality-controls/{cid}/activate")
        assert r.status_code == 422
        # 加 detector 后激活成功
        r = client.patch(
            f"/api/v1/quality-controls/{cid}",
            json={
                "expected_lock_version": lock0,
                "detectors": [
                    {
                        "detector_kind": "manual",
                        "detector_ref": code,
                        "status": "active",
                    }
                ],
            },
        )
        assert r.status_code == 200, r.text
        lv = r.json()["lock_version"]
        r = client.post(f"/api/v1/quality-controls/{cid}/activate")
        assert r.status_code == 200
        assert r.json()["lifecycle_status"] == "active"
        # 口径字段变化 → version 递增
        lv2 = client.get(f"/api/v1/quality-controls/{cid}").json()["lock_version"]
        r = client.patch(
            f"/api/v1/quality-controls/{cid}",
            json={"expected_lock_version": lv2, "threshold_value": 2.5, "comparator": "gt"},
        )
        assert r.status_code == 200
        assert r.json()["version"] == 2

    def test_control_list_and_observations(self, client, active_control):
        r = client.get("/api/v1/quality-controls", params={"keyword": active_control["code"]})
        assert r.status_code == 200
        assert any(c["control_code"] == active_control["code"] for c in r.json()["items"])
        r = client.get(f"/api/v1/quality-controls/{active_control['id']}/observations")
        assert r.status_code == 200


class TestExport:
    def test_export_success_and_safety(self, client, db_session, active_control):
        db = db_session
        issue = qgs.create_manual_issue(
            db,
            title="=HYPERLINK(\"http://evil\") 注入测试",
            responsible_dept_code="D-EXP",
            action_plan="=SUM(1+2) 措施",
            actor="t",
        )
        db.commit()
        r = client.post(
            "/api/v1/quality-issues/export",
            json={"scope": "all"},
        )
        assert r.status_code == 200, r.text
        assert r.headers["content-type"].startswith("text/csv")
        assert "quality-issues-" in r.headers["content-disposition"]
        body = r.text
        # 公式注入防护：= 开头单元格被加 ' 前缀
        assert "'=HYPERLINK" in body or "'=SUM" in body
        line = body.splitlines()[0]
        # 列白名单不含 SQL/样本/联系方式
        for banned in ("evidence_sql", "sample_data", "phone", "id_card"):
            assert banned not in line
        # 审计行
        from app.models.governance_base import GovernAuditLog

        assert db.scalar(
            select(GovernAuditLog).where(
                GovernAuditLog.module == "quality_governance",
                GovernAuditLog.action == "export",
            )
        )

    def test_export_permission_required(self, client):
        limited = _role_client(
            client,
            role_code="qg_handler",
            resources=["quality.issue.read", "quality.issue.handle"],
            token="tok-qg-handler",
            user="qg-handler-1",
        )
        r = limited.post("/api/v1/quality-issues/export", json={})
        assert r.status_code == 403

    def test_export_scope_applied(self, client, db_session):
        db = db_session
        qgs.create_manual_issue(db, title="范围外问题X", responsible_dept_code="D-NOPE", actor="t")
        db.commit()
        r = client.post("/api/v1/quality-issues/export", json={"scope": "all"})
        assert r.status_code == 200
        assert "范围外问题X" in r.text


class TestObservationsApi:
    def test_list_and_ingest_idempotent(self, client, active_control):
        r = client.get("/api/v1/quality-observations")
        assert r.status_code == 200
        r = _ingest_fail(client, active_control["id"], "api-obs-r1", scope="api-obs")
        assert r.status_code == 200
        r2 = _ingest_fail(client, active_control["id"], "api-obs-r1", scope="api-obs")
        assert r2.json()["outcome"] == "duplicate"
        r = client.get(
            "/api/v1/quality-observations",
            params={"control_id": active_control["id"], "result_status": "fail"},
        )
        assert r.status_code == 200
        assert r.json()["total"] >= 1

    def test_observation_list_scoped_and_assignment_options_gated(self, client, db_session, active_control):
        db = db_session
        _ingest_fail(client, active_control["id"], "obs-scope-r1", scope="secret-scope")
        issue = db.scalar(
            select(QualityIssue).where(QualityIssue.scope_key == "secret-scope")
        )
        assert issue is not None
        issue.responsible_dept_code = "D-SECRET"
        db.commit()
        viewer = _role_client(
            client,
            role_code="qg_obs_viewer",
            resources=["quality.issue.read", "quality.observation.read"],
            token="tok-qg-obs-viewer",
            user="qg-obs-viewer-1",
        )
        listed = viewer.get("/api/v1/quality-observations", params={"page_size": 100})
        assert listed.status_code == 200
        ids = [row["id"] for row in listed.json()["items"]]
        secret_obs = db.scalar(
            select(QualityObservation).where(QualityObservation.scope_key == "secret-scope")
        )
        assert secret_obs is not None
        assert secret_obs.id not in ids
        detail = viewer.get(f"/api/v1/quality-observations/{secret_obs.id}")
        assert detail.status_code == 403
        opts = viewer.get("/api/v1/quality-issues/assignment-options/persons")
        assert opts.status_code == 403
