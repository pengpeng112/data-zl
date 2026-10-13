"""207 隔离库集成测试（API 层闭环）：真实 HTTP + 真实 PG 约束。

覆盖：T01（API 202+持久run/blocked）、T03（双 worker 抢占）、T13/T14/T18/T19
（verify 证据拒绝矩阵）、T22（F05 普通用户读清单观测）、T24（批量分派逐条反馈）、
T25（厂商跟进/延期保原截止）、T27（厂商启停）、T28（覆盖口径）、T30（导出新列
防注入）。运行前提：APP_TEST_DB_URL 指向已核实可清理隔离库（根 conftest 强制）。
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models.governance import ApiKey
from app.models.governance_base import AssetRole, AssetRolePermission, AssetUserRole
from app.models.identity import IdentityPerson
from app.models.quality_governance import (
    QualityControl,
    QualityControlDetector,
    QualityIssue,
    QualityObservation,
    QualityRun,
)
from app.services import quality_execution_service as qes
from app.services import quality_governance_service as qgs

ADMIN = "admin-207"
HANDLER = "p-handler-207"
VERIFIER = "p-verifier-207"
OTHER = "p-other-207"


def _role_client(client: TestClient, *, role_code: str, resources: list[str], token: str, user: str):
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


ALL_QUALITY = [
    "quality.issue.read", "quality.issue.read_all", "quality.issue.create",
    "quality.issue.assign", "quality.issue.handle", "quality.issue.verify",
    "quality.issue.accept_risk", "quality.issue.export",
    "quality.control.read", "quality.control.manage", "quality.control.run",
    "quality.observation.read", "quality.run.read", "quality.run.manage",
    "quality.vendor.manage", "quality.notification.read",
]


@pytest.fixture()
def admin_c(client):
    # 平台管理员身份（写范围豁免），叠加质量线细码（幂等）
    return _role_client(client, role_code="platform_admin", resources=ALL_QUALITY,
                        token="tok-207-admin", user=ADMIN)


@pytest.fixture()
def handler_c(client, db_session):
    db = db_session
    if not db.scalar(select(IdentityPerson).where(IdentityPerson.person_code == HANDLER)):
        db.add(IdentityPerson(person_code=HANDLER, person_name_cn="经办甲", dept_code="DQ"))
        db.commit()
    return _role_client(client, role_code="r207-handler",
                        resources=["quality.issue.read", "quality.issue.handle",
                                   "quality.notification.read"],
                        token="tok-207-handler", user=HANDLER)


@pytest.fixture()
def verifier_c(client):
    return _role_client(client, role_code="r207-verifier",
                        resources=["quality.issue.read", "quality.issue.read_all",
                                   "quality.issue.verify", "quality.run.read"],
                        token="tok-207-verifier", user=VERIFIER)


@pytest.fixture()
def other_c(client):
    return _role_client(client, role_code="r207-other",
                        resources=["quality.issue.read", "quality.observation.read",
                                   "quality.control.read"],
                        token="tok-207-other", user=OTHER)


@pytest.fixture(autouse=True)
def seed_handler_identity(db_session):
    """经办人身份种子：分派/待办用例需要可登录经办（F12 有效性校验）。"""
    from app.models.auth import AuthUser
    from app.models.identity import IdentityDepartment

    db = db_session
    if not db.scalar(select(IdentityDepartment).where(IdentityDepartment.dept_code == "DQ")):
        db.add(IdentityDepartment(dept_code="DQ", dept_name_cn="质控科", status="active"))
    if not db.scalar(select(IdentityPerson).where(IdentityPerson.person_code == HANDLER)):
        db.add(IdentityPerson(person_code=HANDLER, person_name_cn="经办甲", dept_code="DQ"))
    if not db.scalar(select(AuthUser).where(AuthUser.user_identifier == HANDLER)):
        db.add(AuthUser(username="u207handler", password_hash="x", user_identifier=HANDLER,
                        enabled=True))
    db.commit()
    yield


@pytest.fixture()
def active_control(db_session) -> dict:
    db = db_session
    code = f"DQ-207-API-{datetime.now(timezone.utc).strftime('%H%M%S')}"
    control = QualityControl(
        control_code=code, version=1, title="207 API 集成清单", lifecycle_status="active",
        dimension="completeness", category="R-CNT", primary_system_code="HIS",
        source_code=None, object_key="HIS|ods|T207", metric_name="err_rate", metric_unit="%",
        comparator="gt", threshold_value=0, no_data_policy="blocked",
        verification_policy="auto_recheck_manual_close", required_pass_count=1,
        default_dept_code="DQ", created_by=ADMIN, updated_by=ADMIN,
    )
    db.add(control)
    db.flush()
    db.add(QualityControlDetector(
        control_id=control.id, detector_kind="manual", detector_ref="MR-207",
        detector_version="1", status="active", created_by=ADMIN, updated_by=ADMIN,
    ))
    db.commit()
    return {"id": control.id, "code": control.control_code}


# ── T01：API 202 + 持久 run；手工清单 manual_required ─────────────────────

def test_t01_run_api_persists_or_reports_manual(admin_c, active_control):
    resp = admin_c.post(f"/api/v1/quality-controls/{active_control['id']}/run", json={})
    assert resp.status_code == 202
    body = resp.json()
    # manual 检测器 → manual_required，不虚报排队
    assert body["status"] == "manual_required"
    assert body["run_id"] is None
    # 幂等重试同请求
    resp2 = admin_c.post(
        f"/api/v1/quality-controls/{active_control['id']}/run",
        json={"idempotency_key": "idem-t01"},
    )
    assert resp2.status_code == 202


def test_t01_unactive_control_rejected(admin_c, db_session):
    db = db_session
    control = QualityControl(
        control_code="DQ-207-DRAFT", version=1, title="草稿", lifecycle_status="draft",
        created_by=ADMIN, updated_by=ADMIN,
    )
    db.add(control)
    db.commit()
    resp = admin_c.post(f"/api/v1/quality-controls/{control.id}/run", json={})
    assert resp.status_code == 409


def test_t01_preflight_endpoint(admin_c, active_control):
    resp = admin_c.post(f"/api/v1/quality-controls/{active_control['id']}/preflight")
    assert resp.status_code == 200
    body = resp.json()
    assert body["manual_required"] is True
    assert "scope_summary" in body and "window" in body


# ── T22：F05 普通用户读清单观测不再 ImportError ──────────────────────────

def test_t22_normal_user_reads_control_observations(other_c, active_control, db_session):
    db = db_session
    control = db.get(QualityControl, active_control["id"])
    issue = qgs.create_manual_issue(
        db, title="F05验证单", control_id=control.id, scope_key="sk:f05-check",
        responsible_dept_code="DQ", actor=ADMIN,
    )
    qgs.apply_observation(
        db, control_id=control.id, run_key="f05-obs", scope_key="sk:f05-check",
        result_status="fail", actor=ADMIN,
    )
    db.commit()
    resp = other_c.get(f"/api/v1/quality-controls/{active_control['id']}/observations")
    # 关键断言：不是 500（ImportError），普通用户按范围过滤或空列表
    assert resp.status_code == 200
    assert "items" in resp.json()


# ── T13/T14/T18/T19：verify 证据拒绝矩阵（API 422/409） ─────────────────

def _make_waiting_verify_issue(db, control_id: int, assignee=HANDLER) -> QualityIssue:
    issue = qgs.create_manual_issue(
        db, title="证据矩阵单", control_id=control_id, scope_key="sk:evd-matrix",
        responsible_dept_code="DQ", assignee_user_identifier=assignee, actor=ADMIN,
    )
    qgs.transition_issue(db, issue, to_status="acknowledged",
                         expected_lock_version=issue.lock_version, actor=HANDLER, reason="确认")
    qgs.transition_issue(db, issue, to_status="in_progress",
                         expected_lock_version=issue.lock_version, actor=HANDLER, reason="开工")
    qgs.request_verification(db, issue, expected_lock_version=issue.lock_version,
                             actor=HANDLER, reason="整改完成", action_plan="修了")
    db.commit()
    return issue


def test_t13_verify_without_evidence_rejected(verifier_c, active_control, db_session):
    db = db_session
    issue = _make_waiting_verify_issue(db, active_control["id"])
    resp = verifier_c.post(f"/api/v1/quality-issues/{issue.id}/verify", json={
        "expected_lock_version": issue.lock_version, "passed": True, "reason": "看起来好了",
    })
    assert resp.status_code == 422
    assert "可信复测证据" in resp.json()["detail"]


def test_t14_verify_foreign_run_id_rejected(verifier_c, active_control, db_session):
    db = db_session
    issue = _make_waiting_verify_issue(db, active_control["id"])
    resp = verifier_c.post(f"/api/v1/quality-issues/{issue.id}/verify", json={
        "expected_lock_version": issue.lock_version, "passed": True, "reason": "关",
        "verification_run_id": 999999,
    })
    assert resp.status_code == 422


def test_t18_stale_lock_version_conflict(verifier_c, active_control, db_session):
    db = db_session
    issue = _make_waiting_verify_issue(db, active_control["id"])
    resp = verifier_c.post(f"/api/v1/quality-issues/{issue.id}/verify", json={
        "expected_lock_version": issue.lock_version + 5, "passed": True, "reason": "关",
    })
    assert resp.status_code in (409, 422)


def test_t19_admin_no_bypass(admin_c, active_control, db_session):
    """管理员也不能豁免证据（194 豁免仅限自证限制，不豁免证据）。"""
    db = db_session
    issue = _make_waiting_verify_issue(db, active_control["id"])
    resp = admin_c.post(f"/api/v1/quality-issues/{issue.id}/verify", json={
        "expected_lock_version": issue.lock_version, "passed": True, "reason": "管理员特批",
    })
    assert resp.status_code == 422
    assert "可信复测证据" in resp.json()["detail"]


# ── T24：批量分派逐条反馈 ────────────────────────────────────────────────

def test_t24_batch_assign_mixed_results(admin_c, db_session):
    db = db_session
    issues = []
    for i in range(3):
        issues.append(qgs.create_manual_issue(
            db, title=f"批量{i}", control_id=None, responsible_dept_code="DQ", actor=ADMIN,
        ))
    # 0/1 号先确认；2 号保持 new（批量不得绕过 acknowledged 条件）
    for i in (0, 1):
        qgs.transition_issue(db, issues[i], to_status="acknowledged",
                             expected_lock_version=issues[i].lock_version, actor=ADMIN, reason="确认")
    db.commit()
    # 一条过期 lock、一条正常、一条不存在的 id
    resp = admin_c.post("/api/v1/quality-issues/batch-assign", json={
        "items": [
            {"issue_id": issues[0].id, "expected_lock_version": issues[0].lock_version},
            {"issue_id": issues[1].id, "expected_lock_version": issues[1].lock_version + 99},
            {"issue_id": 9999999, "expected_lock_version": 0},
        ],
        "responsible_dept_code": "DQ",
        "assignee_user_identifier": HANDLER,
        "reason": "批量分派测试",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3 and body["ok"] == 1 and body["failed"] == 2
    by_id = {r["issue_id"]: r for r in body["items"]}
    assert by_id[issues[0].id]["ok"] is True
    assert by_id[issues[1].id]["ok"] is False and by_id[issues[1].id]["status_code"] == 409
    assert by_id[9999999]["ok"] is False
    # 成功项持久化，失败项零变更
    db.refresh(issues[0])
    db.refresh(issues[1])
    assert issues[0].assignee_user_identifier == HANDLER
    assert issues[1].assignee_user_identifier is None


def test_t24_assign_invalid_person_rejected(admin_c, db_session):
    db = db_session
    issue = qgs.create_manual_issue(db, title="无效分派", control_id=None, actor=ADMIN)
    db.commit()
    resp = admin_c.post(f"/api/v1/quality-issues/{issue.id}/assign", json={
        "expected_lock_version": issue.lock_version,
        "assignee_user_identifier": "ghost-user-404",
        "reason": "分派不存在的人",
    })
    assert resp.status_code == 422
    assert "不存在" in resp.json()["detail"]


# ── T25/T27：厂商跟进、延期保原截止、厂商启停 ────────────────────────────

def test_t25_followup_and_due_change_keeps_original(admin_c, db_session):
    db = db_session
    admin_c.post("/api/v1/quality-vendors", json={
        "vendor_code": "V-207", "vendor_name": "207测试厂商", "contact_note": "院内代录",
    })
    issue = qgs.create_manual_issue(
        db, title="厂商跟进单", control_id=None, actor=ADMIN,
        responsible_dept_code="DQ", assignee_user_identifier=HANDLER,
    )
    qgs.transition_issue(db, issue, to_status="acknowledged",
                         expected_lock_version=issue.lock_version, actor=HANDLER, reason="确认")
    db.commit()
    original_due = date.today() + timedelta(days=5)
    issue.due_at = original_due
    db.commit()
    new_due = date.today() + timedelta(days=15)
    resp = admin_c.post(f"/api/v1/quality-issues/{issue.id}/followups", json={
        "kind": "commitment", "note": "厂商承诺修复", "vendor_code": "V-207",
        "external_ticket_ref": "TK-207-1",
        "vendor_promised_at": date.today().isoformat(),
        "next_followup_at": (date.today() + timedelta(days=3)).isoformat(),
        "change_due_at": new_due.isoformat(),
        "change_due_reason": "厂商排期延后",
    })
    assert resp.status_code == 200
    db.refresh(issue)
    assert issue.primary_vendor_code == "V-207"
    assert issue.due_at == new_due
    assert issue.original_due_at == original_due  # 原截止保留
    # 延期无理由 → 422
    resp2 = admin_c.post(f"/api/v1/quality-issues/{issue.id}/followups", json={
        "kind": "progress", "note": "再延期",
        "change_due_at": (date.today() + timedelta(days=20)).isoformat(),
    })
    assert resp2.status_code == 422


def test_t27_vendor_disable_blocks_followup(admin_c, db_session):
    db = db_session
    created = admin_c.post("/api/v1/quality-vendors", json={
        "vendor_code": "V-207-OFF", "vendor_name": "停用厂商",
    })
    assert created.status_code == 200
    vendor_id = created.json()["id"]
    issue = qgs.create_manual_issue(db, title="停用厂商单", control_id=None, actor=ADMIN)
    qgs.transition_issue(db, issue, to_status="acknowledged",
                         expected_lock_version=issue.lock_version, actor=HANDLER, reason="确认")
    db.commit()
    patched = admin_c.patch(f"/api/v1/quality-vendors/{vendor_id}", json={
        "expected_lock_version": 0, "status": "disabled", "reason": "合同终止",
    })
    assert patched.status_code == 200
    resp = admin_c.post(f"/api/v1/quality-issues/{issue.id}/followups", json={
        "kind": "progress", "note": "挂停用厂商", "vendor_code": "V-207-OFF",
    })
    assert resp.status_code == 422


def test_t27_remind_idempotent_per_day(admin_c, db_session):
    db = db_session
    issue = qgs.create_manual_issue(
        db, title="催办单", control_id=None, actor=ADMIN,
        responsible_dept_code="DQ", assignee_user_identifier=HANDLER,
    )
    qgs.transition_issue(db, issue, to_status="acknowledged",
                         expected_lock_version=issue.lock_version, actor=HANDLER, reason="确认")
    db.commit()
    r1 = admin_c.post(f"/api/v1/quality-issues/{issue.id}/remind", json={"reason": "尽快"})
    r2 = admin_c.post(f"/api/v1/quality-issues/{issue.id}/remind", json={"reason": "再催"})
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json()["notification_created"] is True
    assert r2.json()["notification_created"] is False  # 同日幂等


# ── T28：覆盖口径 ────────────────────────────────────────────────────────

def test_t28_coverage_zero_issues_not_healthy(admin_c, db_session):
    resp = admin_c.get("/api/v1/quality-controls/coverage")
    assert resp.status_code == 200
    body = resp.json()
    for key in ("applicable_instances", "effective_instances", "latest_status_counts",
                "data_pass_rate_pct", "issues", "uncovered", "statistics_time"):
        assert key in body
    # 零问题不等于健康：未覆盖列表可下钻
    assert isinstance(body["uncovered"], list)
    assert body["uncovered_total"] >= 0


def test_t28_coverage_route_not_shadowed(admin_c):
    """静态 /coverage 不能被 /{control_id} 吞掉（返回必须是 JSON 不是 422 详情）。"""
    resp = admin_c.get("/api/v1/quality-controls/coverage")
    assert resp.status_code == 200
    assert "applicable_instances" in resp.json()


# ── T30：导出新列 + 公式注入防护 ─────────────────────────────────────────

def test_t30_export_escapes_formula_and_has_vendor_columns(admin_c, db_session):
    db = db_session
    issue = qgs.create_manual_issue(
        db, title="=HYPERLINK(\"http://evil\")注入", control_id=None, actor=ADMIN,
        responsible_dept_code="DQ",
    )
    issue.primary_vendor_code = "V-207"
    db.commit()
    resp = admin_c.post("/api/v1/quality-issues/export",
                        json={"keyword": "注入", "scope": "all"})
    assert resp.status_code == 200
    text = resp.text
    header = text.splitlines()[0]
    assert "primary_vendor_code" in header and "recheck_substatus" in header
    assert "'=HYPERLINK" in text  # 公式注入转义


# ── T03：双 worker 抢占（真实 PG 行级竞争） ──────────────────────────────

def test_t03_two_workers_single_execution_rights(db_session, active_control):
    """两个会话并抢同一子运行：只有一个 rowcount 命中。"""
    from app.core.db import SessionLocal

    db = db_session
    ctl = db.get(QualityControl, active_control["id"])
    det = db.scalar(
        select(QualityControlDetector).where(
            QualityControlDetector.control_id == ctl.id)
    )
    det.detector_kind = "quality_rule"
    det.detector_ref = "R207-NO-RULE"  # preflight 将 blocked：手工造子单测抢占
    db_session.commit()
    parent = QualityRun(
        run_code="QR-T03-P", control_id=ctl.id, purpose="check", trigger_kind="manual",
        status="running", requested_by=ADMIN, created_by=ADMIN,
    )
    db_session.add(parent)
    db_session.flush()
    child = QualityRun(
        run_code="QR-T03-C", control_id=ctl.id, parent_run_id=parent.id, purpose="check",
        trigger_kind="manual", status="queued", detector_id=det.id,
        detector_kind="quality_rule", detector_ref=det.detector_ref,
        scope_key="sk:t03", requested_by=ADMIN, created_by=ADMIN,
    )
    db_session.add(child)
    db_session.commit()
    child_id = child.id

    s1 = SessionLocal()
    s2 = SessionLocal()
    try:
        c1 = qes.claim_next_run(s1, "worker-1")
        c2 = qes.claim_next_run(s2, "worker-2")
        ids = [c.id for c in (c1, c2) if c is not None]
        assert ids.count(child_id) == 1  # 单一执行权
    finally:
        s1.close()
        s2.close()
    # 迟到回写拒绝：非持有租约的 worker 执行被拒
    winner_run = db_session.get(QualityRun, child_id)
    loser_session = SessionLocal()
    try:
        loser_run = loser_session.get(QualityRun, child_id)
        with pytest.raises(qes.RunStateError):
            qes.execute_claimed_run(
                loser_session, loser_run, worker_id="worker-loser",
            )
    finally:
        loser_session.close()


# ── 运行单查询端点 ──────────────────────────────────────────────────────

def test_runs_list_and_detail_endpoints(admin_c, db_session, active_control):
    db = db_session
    ctl = db.get(QualityControl, active_control["id"])
    parent = QualityRun(
        run_code="QR-LIST-1", control_id=ctl.id, purpose="check", trigger_kind="manual",
        status="blocked", error_code="PREFLIGHT_BLOCKED", error_message_sanitized="x",
        requested_by=ADMIN, created_by=ADMIN,
    )
    db.add(parent)
    db.commit()
    lst = admin_c.get("/api/v1/quality-runs", params={"control_id": ctl.id})
    assert lst.status_code == 200
    assert any(r["run_code"] == "QR-LIST-1" for r in lst.json()["items"])
    detail = admin_c.get(f"/api/v1/quality-runs/{parent.id}")
    assert detail.status_code == 200
    assert detail.json()["error_code"] == "PREFLIGHT_BLOCKED"


def test_notifications_scoped_to_recipient(handler_c, admin_c, db_session):
    db = db_session
    issue = qgs.create_manual_issue(
        db, title="待办单", control_id=None, actor=ADMIN, assignee_user_identifier=HANDLER,
    )
    qes.create_notification(
        db, issue_id=issue.id, run_id=None, recipient=HANDLER, notify_type="remind_due",
        payload={"issue_code": issue.issue_code}, idempotency_key="notif-t207-1",
    )
    db.commit()
    resp = handler_c.get("/api/v1/quality-notifications", params={"unread_only": True})
    assert resp.status_code == 200
    assert resp.json()["unread"] >= 1
    nid = resp.json()["items"][0]["id"]
    read = handler_c.post(f"/api/v1/quality-notifications/{nid}/read")
    assert read.status_code == 200 and read.json()["read_at"]


# ── 208 A6 补充：执行→quality_run 观测落库（浏览器实测暴露的 CHECK 缺口回归） ──

def test_run_observation_quality_run_source_persists(db_session, monkeypatch):
    """207 链在 PG 上执行写观测（source_kind=quality_run）必须落库。

    背景：ck_asset_quality_observations_source 原〔174〕不含 quality_run，
    207 隔离库测试未覆盖执行→写观测路径；浏览器实测 500。迁移 a9b8c7d6e5f4
    修复后以本用例钉住（再回归时直接 CheckViolation 失败）。
    """
    from datetime import datetime, timezone
    from app.services import quality_execution_service as qes2

    code = "DQ-207-API-VDOBS"
    control = QualityControl(
        control_code=code, version=1, title="观测落库回归", lifecycle_status="active",
        dimension="completeness", category="R-CNT", primary_system_code="HIS",
        source_code=None, object_key="HIS|ods|T_VDOBS", metric_name="err", metric_unit="%",
        comparator="gt", threshold_value=0, no_data_policy="blocked",
        verification_policy="auto_recheck_manual_close", required_pass_count=1,
        created_by=ADMIN, updated_by=ADMIN,
    )
    db_session.add(control)
    db_session.flush()
    det = QualityControlDetector(
        control_id=control.id, detector_kind="quality_rule", detector_ref=f"RULE-{code}",
        detector_version="1", status="active", created_by=ADMIN, updated_by=ADMIN,
    )
    db_session.add(det)
    from app.models.quality import QualityRule
    db_session.add(QualityRule(rule_code=f"RULE-{code}", rule_name="观测落库回归规则", enabled=True))
    db_session.commit()

    monkeypatch.setitem(
        qes2.EXECUTOR_REGISTRY, "quality_rule",
        lambda dbc, ctl, rev, run: qes2.DetectorOutcome(
            "fail", metric_value=4.0, numerator=4, denominator=100, metric_unit="%"),
    )
    now = datetime.now(timezone.utc)
    result = qes2.create_run(db_session, control, purpose="check", trigger_kind="manual",
                             requested_by=ADMIN, actor=ADMIN, now=now)
    db_session.commit()
    assert result["status"] == "queued"
    claimed = qes2.claim_next_run(db_session, "w-t34", now=now)
    assert claimed is not None
    exec_result = qes2.execute_claimed_run(db_session, claimed, worker_id="w-t34", now=now)
    db_session.commit()
    assert exec_result["status"] == "fail"
    obs = db_session.scalar(
        select(QualityObservation).where(
            QualityObservation.source_record_ref == f"asset_quality_runs:{claimed.id}")
    )
    assert obs is not None, "quality_run 观测未落库（CHECK 约束回归？）"
    assert obs.source_kind == "quality_run"
    assert obs.result_status == "fail"
    assert float(obs.numerator) == 4 and float(obs.denominator) == 100
