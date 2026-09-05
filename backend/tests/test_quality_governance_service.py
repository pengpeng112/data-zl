"""174 S2/S3/S6: 质量治理台账服务层测试。

覆盖：状态机全部合法/非法边、观测归并（FAIL 建单/持续 FAIL 不重复/PASS 不建单/
ERROR/BLOCKED/NO_DATA 语义）、复发链、误报抑制按版本+到期、部分唯一索引并发兜底、
乐观锁、适配器幂等、种子 dry-run/apply/二次零写。
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.models.quality_governance import (
    QualityControl,
    QualityControlDetector,
    QualityIssue,
    QualityIssueEvent,
    QualityObservation,
)
from app.services import quality_governance_service as qgs

# ─────────────────────────────────────────────────────────────────────────
# 纯逻辑：状态机（无 DB）
# ─────────────────────────────────────────────────────────────────────────


class TestStateMachineMatrix:
    """174 §6.2 转移矩阵逐边验证。"""

    EXPECTED_EDGES = {
        "new": {"acknowledged", "false_positive", "duplicate", "cancelled"},
        "acknowledged": {"assigned", "in_progress", "waiting_external", "accepted_risk"},
        "assigned": {"in_progress", "waiting_external", "waiting_verify"},
        "in_progress": {"waiting_external", "waiting_verify"},
        "waiting_external": {"in_progress", "waiting_verify"},
        "waiting_verify": {"in_progress", "resolved"},
        "resolved": {"acknowledged"},
        "accepted_risk": {"acknowledged"},
        "false_positive": {"acknowledged"},
        "duplicate": set(),
        "cancelled": set(),
    }

    def test_matrix_matches_plan(self):
        assert set(qgs.ISSUE_TRANSITIONS) == set(self.EXPECTED_EDGES)
        for status, targets in self.EXPECTED_EDGES.items():
            assert set(qgs.ISSUE_TRANSITIONS[status]) == targets, status

    def test_total_legal_edges(self):
        total = sum(len(t) for t in qgs.ISSUE_TRANSITIONS.values())
        assert total == 4 + 4 + 3 + 2 + 2 + 2 + 1 + 1 + 1 + 0 + 0  # = 20

    def test_terminal_statuses(self):
        assert qgs.ISSUE_TERMINAL_STATUSES == (
            "resolved", "accepted_risk", "false_positive", "duplicate", "cancelled"
        )

    def test_no_direct_resolve_from_open(self):
        for status in ("new", "acknowledged", "assigned", "in_progress"):
            assert "resolved" not in qgs.ISSUE_TRANSITIONS[status]


# ─────────────────────────────────────────────────────────────────────────
# 测试工具
# ─────────────────────────────────────────────────────────────────────────


def _mk_control(db, *, code: str = "DQ-TST-001", title: str = "测试清单", **kw) -> QualityControl:
    control = QualityControl(
        control_code=code,
        title=title,
        lifecycle_status="active",
        dimension="completeness",
        category="R-REF",
        primary_system_code="HIS",
        metric_name="test_metric",
        metric_unit="%",
        comparator="gt",
        threshold_value=1.0,
        default_severity="medium",
        default_priority="P2",
        **kw,
    )
    db.add(control)
    db.flush()
    return control


def _mk_detector(db, control: QualityControl, *, kind="probe_template", ref="TST", status="active"):
    det = QualityControlDetector(
        control_id=control.id,
        detector_kind=kind,
        detector_ref=ref,
        status=status,
    )
    db.add(det)
    db.flush()
    return det


def _observe(db, control, *, run_key: str, result: str, scope: str = "scope-A", **kw):
    return qgs.apply_observation(
        db,
        control_id=control.id,
        run_key=run_key,
        scope_key=scope,
        result_status=result,
        source_kind="manual",
        actor="test:s1",
        **kw,
    )


# ─────────────────────────────────────────────────────────────────────────
# 观测归并
# ─────────────────────────────────────────────────────────────────────────


class TestObservationMerging:
    def test_fail_creates_issue(self, db_session):
        db = db_session
        control = _mk_control(db)
        result = _observe(db, control, run_key="r1", result="fail", metric_value=5.0)
        assert result["outcome"] == "issue_created"
        issue = db.get(QualityIssue, result["issue_id"])
        assert issue.status == "new"
        assert issue.issue_code.startswith("DQI-")
        assert issue.issue_type == "data_defect"
        assert issue.recurrence_no == 0
        assert issue.latest_result_status == "fail"

    def test_same_run_key_idempotent(self, db_session):
        db = db_session
        control = _mk_control(db)
        first = _observe(db, control, run_key="r1", result="fail")
        db.commit()
        second = _observe(db, control, run_key="r1", result="fail")
        assert second["outcome"] == "duplicate"
        assert second["observation_id"] == first["observation_id"]
        assert db.scalar(select(QualityIssue.id).where(QualityIssue.control_id == control.id).order_by(QualityIssue.id.desc()).limit(1)) is not None
        count = len(db.scalars(select(QualityObservation).where(QualityObservation.control_id == control.id)).all())
        assert count == 1

    def test_new_run_key_same_scope_updates_not_duplicates(self, db_session):
        db = db_session
        control = _mk_control(db)
        _observe(db, control, run_key="r1", result="fail")
        db.commit()
        result = _observe(db, control, run_key="r2", result="fail", metric_value=7.0)
        assert result["outcome"] == "issue_updated"
        issues = db.scalars(select(QualityIssue).where(QualityIssue.control_id == control.id)).all()
        assert len(issues) == 1
        assert float(issues[0].latest_metric_value) == 7.0

    def test_different_scope_creates_separate_issues(self, db_session):
        db = db_session
        control = _mk_control(db)
        _observe(db, control, run_key="r1", result="fail", scope="scope-A")
        result = _observe(db, control, run_key="r1", result="fail", scope="scope-B")
        assert result["outcome"] == "issue_created"
        count = db.scalar(
            select(func.count()).select_from(QualityIssue).where(QualityIssue.control_id == control.id)
        )
        assert count == 2

    def test_pass_no_issue(self, db_session):
        db = db_session
        control = _mk_control(db)
        result = _observe(db, control, run_key="r1", result="pass", metric_value=0.5)
        assert result["outcome"] == "observed"
        assert db.scalar(select(QualityIssue).where(QualityIssue.control_id == control.id)) is None

    def test_pass_on_waiting_verify_does_not_resolve(self, db_session):
        db = db_session
        control = _mk_control(db)
        created = _observe(db, control, run_key="r1", result="fail")
        issue = db.get(QualityIssue, created["issue_id"])
        # new → acknowledged → assigned → in_progress → waiting_verify
        for to_status, fields in [
            ("acknowledged", {}),
            ("assigned", {}),
            ("in_progress", {}),
        ]:
            qgs.transition_issue(
                db, issue, to_status=to_status, expected_lock_version=issue.lock_version,
                actor="t", reason="推进",
            )
        qgs.request_verification(
            db, issue, expected_lock_version=issue.lock_version, actor="t",
            reason="完成整改", action_plan="已修复",
        )
        assert issue.status == "waiting_verify"
        result = _observe(db, control, run_key="r2", result="pass")
        assert result["outcome"] == "issue_left"
        assert issue.status == "waiting_verify"  # 不自动关闭

    def test_error_creates_nothing(self, db_session):
        db = db_session
        control = _mk_control(db)
        result = _observe(db, control, run_key="r1", result="error", error_code="ORA-XXX")
        assert result["outcome"] == "observed"
        assert db.scalar(select(QualityIssue).where(QualityIssue.control_id == control.id)) is None

    def test_blocked_creates_monitoring_gap(self, db_session):
        db = db_session
        control = _mk_control(db)
        result = _observe(db, control, run_key="r1", result="blocked")
        assert result["outcome"] == "monitoring_gap_created"
        issue = db.get(QualityIssue, result["issue_id"])
        assert issue.issue_type == "monitoring_gap"

    def test_blocked_with_active_data_defect_links_not_duplicates(self, db_session):
        db = db_session
        control = _mk_control(db)
        _observe(db, control, run_key="r1", result="fail")
        db.commit()
        result = _observe(db, control, run_key="r2", result="blocked")
        assert result["outcome"] == "issue_updated"
        issues = db.scalars(select(QualityIssue).where(QualityIssue.control_id == control.id)).all()
        assert len(issues) == 1
        assert issues[0].issue_type == "data_defect"

    def test_no_data_policy_blocked_maps_to_monitoring_gap(self, db_session):
        db = db_session
        control = _mk_control(db, no_data_policy="blocked")
        result = _observe(db, control, run_key="r1", result="no_data")
        assert result["outcome"] == "monitoring_gap_created"

    def test_no_data_policy_pass_green(self, db_session):
        db = db_session
        control = _mk_control(db, no_data_policy="pass")
        result = _observe(db, control, run_key="r1", result="no_data")
        assert result["outcome"] == "observed"
        assert db.scalar(select(QualityIssue).where(QualityIssue.control_id == control.id)) is None

    def test_invalid_result_status_rejected(self, db_session):
        control = _mk_control(db_session)
        with pytest.raises(ValueError):
            _observe(db_session, control, run_key="r1", result="green")


# ─────────────────────────────────────────────────────────────────────────
# 复发链 / 误报抑制
# ─────────────────────────────────────────────────────────────────────────


class TestRecurrenceAndSuppression:
    def _resolved_issue(self, db):
        control = _mk_control(db)
        created = _observe(db, control, run_key="r1", result="fail")
        issue = db.get(QualityIssue, created["issue_id"])
        for to_status in ("acknowledged", "assigned", "in_progress"):
            qgs.transition_issue(
                db, issue, to_status=to_status, expected_lock_version=issue.lock_version,
                actor="t", reason="推进",
            )
        qgs.request_verification(
            db, issue, expected_lock_version=issue.lock_version, actor="t",
            reason="完成", action_plan="修复",
        )
        qgs.verify_issue(
            db, issue, expected_lock_version=issue.lock_version, passed=True,
            actor="verifier", reason="复测通过",
        )
        assert issue.status == "resolved"
        return control, issue

    def test_refail_after_resolved_creates_recurrence(self, db_session):
        db = db_session
        control, first = self._resolved_issue(db)
        result = _observe(db, control, run_key="r2", result="fail")
        assert result["outcome"] == "issue_created"
        second = db.get(QualityIssue, result["issue_id"])
        assert second.id != first.id
        assert second.recurrence_of_issue_id == first.id
        assert second.recurrence_no == 1
        assert first.status == "resolved"  # 旧问题保持关闭

    def test_suppression_blocks_refail_within_version_and_window(self, db_session):
        db = db_session
        control = _mk_control(db)
        created = _observe(db, control, run_key="r1", result="fail")
        issue = db.get(QualityIssue, created["issue_id"])
        qgs.mark_false_positive(
            db, issue,
            expected_lock_version=issue.lock_version,
            false_positive_reason="口径误判",
            suppressed_until=date.today() + timedelta(days=30),
            actor="t", reason="误报",
        )
        assert issue.status == "false_positive"
        db.commit()
        result = _observe(db, control, run_key="r2", result="fail")
        assert result["outcome"] == "suppressed"

    def test_suppression_expired_allows_new_issue(self, db_session):
        db = db_session
        control = _mk_control(db)
        created = _observe(db, control, run_key="r1", result="fail")
        issue = db.get(QualityIssue, created["issue_id"])
        qgs.mark_false_positive(
            db, issue,
            expected_lock_version=issue.lock_version,
            false_positive_reason="口径误判",
            suppressed_until=date.today() + timedelta(days=30),
            actor="t", reason="误报",
        )
        db.commit()
        # 模拟抑制到期（历史数据置为昨天）
        issue.suppressed_until = date.today() - timedelta(days=1)
        db.commit()
        result = _observe(db, control, run_key="r2", result="fail")
        assert result["outcome"] == "issue_created"

    def test_suppression_version_change_allows_new_issue(self, db_session):
        db = db_session
        control = _mk_control(db)
        created = _observe(db, control, run_key="r1", result="fail")
        issue = db.get(QualityIssue, created["issue_id"])
        qgs.mark_false_positive(
            db, issue,
            expected_lock_version=issue.lock_version,
            false_positive_reason="旧版本口径误判",
            suppressed_until=date.today() + timedelta(days=30),
            actor="t", reason="误报",
        )
        db.commit()
        # 规则版本变化（v2）→ 抑制不再生效
        result = _observe(db, control, run_key="r2", result="fail", control_version=2)
        assert result["outcome"] == "issue_created"


# ─────────────────────────────────────────────────────────────────────────
# 数据库约束：部分唯一索引 + 乐观锁
# ─────────────────────────────────────────────────────────────────────────


class TestDatabaseConstraints:
    def test_partial_unique_index_blocks_two_active(self, db_session):
        db = db_session
        control = _mk_control(db)
        _observe(db, control, run_key="r1", result="fail")
        db.commit()
        dup = QualityIssue(
            issue_code=qgs.next_issue_code(db),
            control_id=control.id,
            issue_type="data_defect",
            title="重复活动问题",
            scope_key="scope-A",
            status="new",
        )
        db.add(dup)
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()

    def test_partial_unique_index_allows_after_terminal(self, db_session):
        db = db_session
        control = _mk_control(db)
        created = _observe(db, control, run_key="r1", result="fail")
        issue = db.get(QualityIssue, created["issue_id"])
        qgs.transition_issue(
            db, issue, to_status="cancelled", expected_lock_version=issue.lock_version,
            actor="t", reason="登记错误",
        )
        db.commit()
        # 终态后允许新活动问题
        result = _observe(db, control, run_key="r2", result="fail")
        assert result["outcome"] == "issue_created"

    def test_lock_version_conflict(self, db_session):
        db = db_session
        control = _mk_control(db)
        issue = qgs.create_manual_issue(db, title="手工问题", actor="t")
        with pytest.raises(qgs.LockConflictError):
            qgs.transition_issue(
                db, issue, to_status="acknowledged", expected_lock_version=issue.lock_version + 5,
                actor="t", reason="过期锁",
            )
        db.rollback()

    def test_lock_version_missing_rejected(self, db_session):
        control = _mk_control(db_session)
        issue = qgs.create_manual_issue(db_session, title="手工问题", actor="t")
        with pytest.raises(qgs.IssueValidationError):
            qgs.transition_issue(
                db_session, issue, to_status="acknowledged", expected_lock_version=None,
                actor="t", reason="缺锁",
            )
        db_session.rollback()


# ─────────────────────────────────────────────────────────────────────────
# 命令必填约束（174 §5.4）
# ─────────────────────────────────────────────────────────────────────────


class TestCommandValidation:
    def test_waiting_external_requires_wait_kind(self, db_session):
        db = db_session
        control = _mk_control(db)
        created = _observe(db, control, run_key="r1", result="fail")
        issue = db.get(QualityIssue, created["issue_id"])
        qgs.transition_issue(
            db, issue, to_status="acknowledged", expected_lock_version=issue.lock_version,
            actor="t", reason="确认",
        )
        with pytest.raises(qgs.IssueValidationError):
            qgs.transition_issue(
                db, issue, to_status="waiting_external", expected_lock_version=issue.lock_version,
                actor="t", reason="缺依赖说明",
            )
        db.rollback()

    def test_accepted_risk_requires_all_fields(self, db_session):
        db = db_session
        control = _mk_control(db)
        created = _observe(db, control, run_key="r1", result="fail")
        issue = db.get(QualityIssue, created["issue_id"])
        qgs.transition_issue(
            db, issue, to_status="acknowledged", expected_lock_version=issue.lock_version,
            actor="t", reason="确认",
        )
        with pytest.raises(qgs.IssueValidationError):
            qgs.transition_issue(
                db, issue, to_status="accepted_risk", expected_lock_version=issue.lock_version,
                actor="t", reason="缺批准人",
                risk_reason="低风险",  # 缺 risk_approver / risk_review_at
            )
        db.rollback()

    def test_verify_requires_waiting_verify(self, db_session):
        db = db_session
        issue = qgs.create_manual_issue(db_session, title="x", actor="t")
        with pytest.raises(qgs.TransitionError):
            qgs.verify_issue(
                db_session, issue, expected_lock_version=issue.lock_version,
                passed=True, actor="v", reason="未到待验证",
            )
        db_session.rollback()

    def test_transition_to_resolved_blocked(self, db_session):
        db = db_session
        issue = qgs.create_manual_issue(db_session, title="x", actor="t")
        with pytest.raises(qgs.TransitionError):
            qgs.transition_issue(
                db_session, issue, to_status="resolved", expected_lock_version=issue.lock_version,
                actor="t", reason="绕过验证",
            )
        db_session.rollback()

    def test_patch_rejects_status_field(self, db_session):
        db = db_session
        issue = qgs.create_manual_issue(db_session, title="x", actor="t")
        with pytest.raises(qgs.IssueValidationError):
            qgs.patch_issue(
                db_session, issue, expected_lock_version=issue.lock_version, actor="t",
                fields={"status": "resolved"},
            )
        db_session.rollback()

    def test_control_bound_manual_issue_requires_scope_key(self, db_session):
        control = _mk_control(db_session, code="DQ-SCOPE-REQ-001")
        db_session.commit()
        with pytest.raises(qgs.IssueValidationError, match="scope_key"):
            qgs.create_manual_issue(
                db_session,
                title="缺 scope",
                control_id=control.id,
                actor="t",
            )
        db_session.rollback()


# ─────────────────────────────────────────────────────────────────────────
# 事件时间线与审计同事务
# ─────────────────────────────────────────────────────────────────────────


class TestEventTimeline:
    def test_created_and_transition_events_written(self, db_session):
        db = db_session
        control = _mk_control(db)
        created = _observe(db, control, run_key="r1", result="fail")
        issue = db.get(QualityIssue, created["issue_id"])
        qgs.transition_issue(
            db, issue, to_status="acknowledged", expected_lock_version=issue.lock_version,
            actor="alice", reason="确认有效",
        )
        db.commit()
        events = db.scalars(
            select(QualityIssueEvent).where(QualityIssueEvent.issue_id == issue.id).order_by(QualityIssueEvent.id)
        ).all()
        types = [e.event_type for e in events]
        assert types[0] == "created"
        assert "acknowledged" in types
        # 建单事件本身携带观测引用；后续持续 FAIL 才单独发 observation_linked
        created_ev = events[0]
        assert created_ev.observation_id is not None
        ack = next(e for e in events if e.event_type == "acknowledged")
        assert ack.actor_user_identifier == "alice"
        assert ack.from_status == "new" and ack.to_status == "acknowledged"

    def test_audit_log_written_for_commands(self, db_session):
        db = db_session
        issue = qgs.create_manual_issue(db_session, title="审计验证", actor="bob")
        db_session.commit()
        from app.models.governance_base import GovernAuditLog

        row = db_session.scalar(
            select(GovernAuditLog).where(
                GovernAuditLog.module == "quality_governance",
                GovernAuditLog.entity_ref == issue.issue_code,
            )
        )
        assert row is not None
        assert row.action == "create"
        assert row.operator == "bob"


# ─────────────────────────────────────────────────────────────────────────
# 数据范围（本人/本科室/全院）
# ─────────────────────────────────────────────────────────────────────────


class TestDataScope:
    def test_resolve_user_scope_multi_dept(self, db_session):
        from app.models.identity import IdentityPerson, IdentityPersonDepartment

        db = db_session
        if not db.scalar(select(IdentityPerson).where(IdentityPerson.person_code == "u-scope-1")):
            db.add(IdentityPerson(person_code="u-scope-1", person_name_cn="范围测试", dept_code="D01"))
            db.add(IdentityPersonDepartment(person_code="u-scope-1", dept_code="D02", source_table="t"))
            db.commit()
        scope = qgs.resolve_user_scope(db, "u-scope-1")
        assert scope["dept_codes"] == ["D01", "D02"]
        assert scope["person"] is not None

    def test_user_can_touch_issue(self, db_session):
        db = db_session
        issue = qgs.create_manual_issue(
            db, title="范围问题", responsible_dept_code="D01", actor="t"
        )
        scope_in = {"user_identifier": "someone-else", "dept_codes": ["D01"]}
        scope_out = {"user_identifier": "someone-else", "dept_codes": ["D99"]}
        assert qgs.user_can_touch_issue(issue, scope_in)
        assert not qgs.user_can_touch_issue(issue, scope_out)
        scope_assignee = {"user_identifier": "op-1", "dept_codes": []}
        issue.assignee_user_identifier = "op-1"
        assert qgs.user_can_touch_issue(issue, scope_assignee)


# ─────────────────────────────────────────────────────────────────────────
# 种子（S6）：dry-run 零写 / apply 幂等 / 二次零写
# ─────────────────────────────────────────────────────────────────────────


class TestSeedTool:
    def test_seed_dry_run_apply_idempotent(self, db_session, tmp_path):
        from app.scripts import seed_quality_governance as seed

        db = db_session
        seed_marker = "DQ-TST-SEEDONLY-9X"
        assert db.scalar(select(QualityControl).where(QualityControl.control_code == seed_marker)) is None

        report = seed.run(dry_run=True)
        assert report["committed"] is False
        assert report["controls_created"] > 0
        assert report["meeting_issues_created"] == 5
        # dry-run 后库内无 174 种子清单
        assert db.scalar(select(QualityControl).where(QualityControl.control_code == "DQ-HIS-EXAM-001")) is None

        report2 = seed.run(dry_run=False)
        assert report2["committed"] is True
        assert report2["controls_created"] == 17
        assert report2["meeting_issues_created"] == 5
        assert report2["t7_monitoring_gap"] == "monitoring_gap_created"

        report3 = seed.run(dry_run=False)
        assert report3["controls_created"] == 0
        assert report3["controls_existing"] == 17
        assert report3["meeting_issues_created"] == 0
        assert report3["meeting_issues_existing"] == 5
        assert report3["t7_monitoring_gap"] == "duplicate"

    def test_t7_control_blocked_with_reason(self, db_session):
        from app.scripts import seed_quality_governance as seed

        seed.run(dry_run=False)
        control = db_session.scalar(
            select(QualityControl).where(QualityControl.control_code == "DQ-HIS-PACS-001")
        )
        assert control is not None
        assert control.lifecycle_status == "blocked"
        assert control.blocked_reason
        det = db_session.scalar(
            select(QualityControlDetector).where(QualityControlDetector.control_id == control.id)
        )
        assert det.status == "blocked"
        gap = db_session.scalar(
            select(QualityIssue).where(
                QualityIssue.control_id == control.id,
                QualityIssue.issue_type == "monitoring_gap",
            )
        )
        assert gap is not None

    def test_meeting_issues_pending_evidence(self, db_session):
        from app.scripts import seed_quality_governance as seed

        seed.run(dry_run=False)
        db = db_session
        control = db.scalar(
            select(QualityControl).where(QualityControl.control_code == "DQ-LIS-KEY-001")
        )
        assert control is not None
        det = db.scalar(
            select(QualityControlDetector).where(QualityControlDetector.control_id == control.id)
        )
        assert det.status == "blocked"  # 未核验 detector 保持 blocked
        issue = db.scalar(select(QualityIssue).where(QualityIssue.control_id == control.id))
        assert issue is not None
        assert issue.status == "new"
        assert issue.latest_metric_value is None  # 指标留空待取证
        assert "待取证" in (issue.description or "")
