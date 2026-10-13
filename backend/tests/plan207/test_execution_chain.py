"""207 批次A主链测试（sqlite 纯逻辑）：真实任务→六态观测→归并→复测→关闭→复发。

对应验收矩阵：T01（服务级）、T02、T04、T05、T12、T15、T16、T20、T21、T26、T33。
合成执行器经 EXECUTOR_REGISTRY 注入（fixture fake_executors）。
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models.quality_governance import (
    QualityControl,
    QualityControlDetector,
    QualityIssue,
    QualityIssueEvent,
    QualityNotification,
    QualityObservation,
    QualityRun,
)
from app.services import quality_execution_service as qes
from app.services import quality_governance_service as qgs

NOW = datetime(2026, 9, 28, 10, 0, tzinfo=timezone.utc)


def make_control(db, *, code="QC-207-001", policy="auto_recheck_manual_close", category="R-CNT",
                 active=True, schedule=False):
    from app.models.quality import QualityRule

    control = QualityControl(
        control_code=code, version=1, title=f"207测试清单 {code}",
        lifecycle_status="active" if active else "draft", dimension="completeness",
        category=category, primary_system_code="HIS", source_code="his_src",
        object_key="HIS|ods|PAT_VISIT", metric_name="missing_rate", metric_unit="%",
        comparator="gt", threshold_value=0, no_data_policy="blocked",
        verification_policy=policy, required_pass_count=1,
        schedule_enabled="true" if schedule else "false",
        created_by="t", updated_by="t",
    )
    db.add(control)
    db.flush()
    det = QualityControlDetector(
        control_id=control.id, detector_kind="quality_rule", detector_ref=f"RULE-{code}",
        detector_version="1", status="active", created_by="t", updated_by="t",
    )
    db.add(det)
    db.add(QualityRule(rule_code=f"RULE-{code}", rule_name=f"规则 {code}", enabled=True))
    db.commit()
    return control, det


def run_chain(db, control, *, outcome, purpose="check", issue_id=None, worker="w1", actor="u-admin"):
    """创建并完整执行一轮运行（单检测器），返回 (parent, child, obs_outcome)。"""
    result = qes.create_run(
        db, control, purpose=purpose, trigger_kind="recheck" if purpose == "recheck" else "manual",
        requested_by=actor, issue_id=issue_id, now=NOW, actor=actor,
    )
    db.commit()
    parent = result["run"]
    child = db.scalar(
        select(QualityRun).where(
            QualityRun.parent_run_id == parent.id, QualityRun.detector_id.isnot(None)
        )
    )
    claimed = qes.claim_next_run(db, worker, now=NOW)
    assert claimed is not None and claimed.id == child.id
    exec_result = qes.execute_claimed_run(db, claimed, worker_id=worker, now=NOW)
    db.commit()
    return parent, child, exec_result


# ── T01：可执行/手工/受阻三类清单 ────────────────────────────────────────

def test_t01_executable_control_creates_persisted_run(db, fake_executors):
    fake_executors["RULE-QC-207-001"] = qes.DetectorOutcome("pass", metric_value=0.0, numerator=0, denominator=100)
    control, det = make_control(db)
    result = qes.create_run(db, control, requested_by="u1", now=NOW)
    db.commit()
    assert result["status"] == "queued" and result["duplicate"] is False
    parent = result["run"]
    assert parent.id is not None and parent.run_code.startswith("QR-")
    children = db.scalars(select(QualityRun).where(QualityRun.parent_run_id == parent.id)).all()
    assert len(children) == 1 and children[0].status == "queued"


def test_t01_manual_control_reports_manual_required(db):
    control = QualityControl(
        control_code="QC-207-MANUAL", version=1, title="手工清单", lifecycle_status="active",
        category="MANUAL", primary_system_code="HIS", created_by="t", updated_by="t",
    )
    db.add(control)
    db.flush()
    db.add(QualityControlDetector(
        control_id=control.id, detector_kind="manual", detector_ref="MR-1",
        detector_version="1", status="active", created_by="t", updated_by="t",
    ))
    db.commit()
    result = qes.create_run(db, control, requested_by="u1", now=NOW)
    assert result["manual_required"] is True and result["run"] is None
    assert db.scalar(select(QualityRun).where(QualityRun.control_id == control.id)) is None  # 不造空执行单


def test_t01_blocked_detectors_persist_blocked_run_with_reasons(db):
    control, det = make_control(db, code="QC-207-BLK")
    det.status = "blocked"  # 无 active 检测器
    det.blocked_reason = "通道未批"
    db.commit()
    result = qes.create_run(db, control, requested_by="u1", now=NOW)
    db.commit()
    assert result["status"] == "blocked"
    assert result["run"].status == "blocked"
    assert any("active" in r or "检测器" in r for r in result["blocked_reasons"])


# ── T02：幂等 ────────────────────────────────────────────────────────────

def test_t02_idempotent_create_and_duplicate_observation(db, fake_executors):
    fake_executors["RULE-QC-207-001"] = qes.DetectorOutcome("fail", metric_value=5.0, numerator=5, denominator=100)
    control, det = make_control(db)
    r1 = qes.create_run(db, control, requested_by="u1", idempotency_key="idem-1", now=NOW)
    r2 = qes.create_run(db, control, requested_by="u1", idempotency_key="idem-1", now=NOW)
    db.commit()
    assert r1["run"].id == r2["run"].id and r2["duplicate"] is True
    parents = db.scalars(
        select(QualityRun).where(QualityRun.control_id == control.id, QualityRun.parent_run_id.is_(None))
    ).all()
    assert len(parents) == 1

    # 观测幂等：同 run/attempt 重复写入返回 duplicate（T02/T12）
    child = db.scalar(select(QualityRun).where(QualityRun.parent_run_id == r1["run"].id))
    claimed = qes.claim_next_run(db, "w1", now=NOW)
    qes.execute_claimed_run(db, claimed, worker_id="w1", now=NOW)
    db.commit()
    obs_cnt = len(db.scalars(select(QualityObservation).where(QualityObservation.control_id == control.id)).all())
    dup = qgs.apply_observation(
        db, control_id=control.id, detector_id=det.id, run_key=f"qr:{child.id}:1",
        scope_key=child.scope_key, result_status="fail", source_kind="quality_run",
    )
    assert dup["outcome"] == "duplicate"
    assert len(db.scalars(select(QualityObservation).where(QualityObservation.control_id == control.id)).all()) == obs_cnt


# ── T04：取消 / 重试退避 / 失败不是 PASS ────────────────────────────────

def test_t04_cancel_queued_child(db, fake_executors):
    fake_executors["RULE-QC-207-001"] = qes.DetectorOutcome("pass", numerator=0, denominator=10)
    control, _ = make_control(db)
    result = qes.create_run(db, control, requested_by="u1", now=NOW)
    db.commit()
    child = db.scalar(select(QualityRun).where(QualityRun.parent_run_id == result["run"].id))
    qes.cancel_run(db, child, expected_lock_version=child.lock_version, reason="误触发", actor="u1")
    db.commit()
    assert child.status == "cancelled"
    parent = db.get(QualityRun, result["run"].id)
    qes._aggregate_parent(db, parent.id, now=NOW)
    assert parent.status == "cancelled"
    assert db.scalars(select(QualityObservation).where(QualityObservation.control_id == control.id)).all() == []


def test_t04_retryable_error_backoff_then_fail(db, fake_executors, monkeypatch):
    attempts = {"n": 0}

    def flaky(dbc, control, revision, run):
        attempts["n"] += 1
        return qes.DetectorOutcome("error", error_code="CONNECTION", error_message_sanitized="连接失败")

    fake_executors["RULE-QC-207-001"] = flaky
    control, _ = make_control(db)
    control_id = control.id
    result = qes.create_run(db, control, requested_by="u1", now=NOW)
    db.commit()
    for round_no, expected in enumerate(("queued_retry", "queued_retry", "error"), start=1):
        child = db.scalar(select(QualityRun).where(QualityRun.parent_run_id == result["run"].id))
        if child.status == "queued":
            child.next_window_at = NOW  # 测试直接到窗（跳过退避等待）
            db.flush()
        claimed = qes.claim_next_run(db, "w1", now=NOW)
        assert claimed is not None and claimed.id == child.id
        out = qes.execute_claimed_run(db, claimed, worker_id="w1", now=NOW)
        db.commit()
        assert out["status"] == expected, f"第 {round_no} 次应为 {expected}"
        if expected == "error":
            assert out["run_status"] == "failed"  # 退避耗尽 → 子运行终态 failed
    parent = db.get(QualityRun, result["run"].id)
    assert parent.status == "failed"
    # 失败不是 PASS：error 观测留证（六态），但零 PASS、零问题、零自动建单
    obs = db.scalars(select(QualityObservation).where(QualityObservation.control_id == control_id)).all()
    assert obs and all(o.result_status == "error" for o in obs)
    assert db.scalars(select(QualityIssue).where(QualityIssue.control_id == control_id)).all() == []


# ── T05：执行窗口门禁 ────────────────────────────────────────────────────

def test_t05_out_of_window_waits_then_promotes(db, fake_executors, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "quality_execution_allowed_hours", "0-6", raising=False)
    fake_executors["RULE-QC-207-001"] = qes.DetectorOutcome("pass", numerator=0, denominator=10)
    control, _ = make_control(db)
    daytime = NOW.replace(hour=10)
    result = qes.create_run(db, control, requested_by="u1", now=daytime)
    db.commit()
    assert result["status"] == "waiting_window"
    assert result["next_window_at"] is not None
    # 白天 worker 不领取 waiting_window 未到窗的任务
    assert qes.claim_next_run(db, "w1", now=daytime) is None
    # 到窗提升
    night = NOW.replace(hour=3, day=NOW.day + 1)
    assert qes.promote_waiting_runs(db, now=night) >= 1
    db.commit()
    claimed = qes.claim_next_run(db, "w1", now=night)
    assert claimed is not None


# ── T12：六态逐次入账 ────────────────────────────────────────────────────

@pytest.mark.parametrize("status,num,den,expect_issue", [
    ("pass", 0, 100, False),
    ("fail", 5, 100, True),
    ("no_data", 0, 0, False),      # no_data_policy=blocked → monitoring gap（独立单）
    ("error", None, None, False),
    ("blocked", None, None, False),  # → monitoring gap
    ("skipped", None, None, False),
])
def test_t12_six_states_persisted(db, fake_executors, status, num, den, expect_issue):
    fake_executors[f"RULE-QC-207-001"] = qes.DetectorOutcome(
        status, metric_value=(num / den * 100) if den else 0.0, numerator=num, denominator=den)
    control, det = make_control(db)
    parent, child, out = run_chain(db, control, outcome=status)
    obs = db.scalar(select(QualityObservation).where(QualityObservation.control_id == control.id))
    assert obs is not None
    assert obs.result_status == status  # 观测保留原始六态
    assert obs.source_kind == "quality_run"
    assert obs.source_record_ref == f"asset_quality_runs:{child.id}"
    assert obs.control_definition_snapshot is not None  # 版本快照随观测冻结（F07）
    data_defects = db.scalars(
        select(QualityIssue).where(QualityIssue.control_id == control.id, QualityIssue.issue_type == "data_defect")
    ).all()
    if status == "fail":
        assert len(data_defects) == 1 and data_defects[0].status == "new"
    else:
        assert data_defects == []


# ── T15/T16：自动复测闭环（FAIL退回→修复PASS待确认→人工关闭） ──────────

def _prepare_assigned_issue(db, fake_executors, *, fail_first=True):
    fake_executors["RULE-QC-207-001"] = qes.DetectorOutcome(
        "fail" if fail_first else "pass", metric_value=5.0 if fail_first else 0.0,
        numerator=5 if fail_first else 0, denominator=100)
    control, det = make_control(db)
    parent, child, _ = run_chain(db, control, outcome="fail")
    issue = db.scalar(select(QualityIssue).where(QualityIssue.control_id == control.id))
    # 走确认→分派→开工→提交整改（同事务创建复测运行）
    for to_status in ("acknowledged",):
        qgs.transition_issue(db, issue, to_status=to_status, expected_lock_version=issue.lock_version,
                             actor="handler", reason="确认")
    qgs.assign_issue(db, issue, expected_lock_version=issue.lock_version,
                     assignee_user_identifier="p_handler", actor="lead", reason="分派")
    qgs.transition_issue(db, issue, to_status="in_progress", expected_lock_version=issue.lock_version,
                         actor="handler", reason="开工")
    qgs.request_verification(db, issue, expected_lock_version=issue.lock_version,
                             actor="p_handler", reason="整改完成", action_plan="修复了空值")
    issue.remediation_submitted_at = NOW - timedelta(minutes=5)  # 钉住时间戳消除真实时钟跨日漂移
    db.commit()
    recheck = qes.create_run(
        db, control, purpose="recheck", trigger_kind="recheck", requested_by="p_handler",
        idempotency_key=f"recheck:{issue.id}:{issue.lock_version}", issue_id=issue.id, now=NOW,
    )
    db.commit()
    return control, det, issue, recheck["run"]


def test_t15_recheck_fail_returns_issue_to_progress(db, fake_executors):
    control, det, issue, recheck_parent = _prepare_assigned_issue(db, fake_executors, fail_first=True)
    assert issue.status == "waiting_verify"
    child = db.scalar(select(QualityRun).where(QualityRun.parent_run_id == recheck_parent.id))
    # 复测仍 FAIL → 退回整改 + 通知经办（T15）
    claimed = qes.claim_next_run(db, "w1", now=NOW)
    assert claimed.id == child.id
    qes.execute_claimed_run(db, claimed, worker_id="w1", now=NOW)
    db.commit()
    db.refresh(issue)
    assert issue.status == "in_progress"
    assert issue.recheck_substatus == "failed"
    assert issue.recheck_pass_streak == 0
    assert issue.last_verification_run_id == recheck_parent.id
    notify = db.scalar(select(QualityNotification).where(QualityNotification.issue_id == issue.id))
    assert notify is not None and notify.notify_type == "recheck_failed"
    assert notify.recipient == "p_handler"


def test_t15_full_loop_pass_then_independent_close_and_recurrence(db, fake_executors):
    control, det, issue, recheck_parent = _prepare_assigned_issue(db, fake_executors, fail_first=True)
    # 复测 FAIL 退回
    claimed = qes.claim_next_run(db, "w1", now=NOW)
    qes.execute_claimed_run(db, claimed, worker_id="w1", now=NOW)
    db.commit()
    db.refresh(issue)
    assert issue.status == "in_progress"
    # 厂商修复 fixture → 重新提交 → 复测 PASS → waiting_verify + passed（待人工确认）
    fake_executors["RULE-QC-207-001"] = qes.DetectorOutcome("pass", metric_value=0.0, numerator=0, denominator=100)
    qgs.request_verification(db, issue, expected_lock_version=issue.lock_version,
                             actor="p_handler", reason="已修复", action_plan="已修复")
    issue.remediation_submitted_at = NOW  # 钉住时间戳消除真实时钟跨日漂移
    db.commit()
    recheck2 = qes.create_run(
        db, control, purpose="recheck", trigger_kind="recheck", requested_by="p_handler",
        idempotency_key=f"recheck:{issue.id}:{issue.lock_version}", issue_id=issue.id,
        now=NOW + timedelta(minutes=5),
    )
    db.commit()
    claimed2 = qes.claim_next_run(db, "w1", now=NOW + timedelta(minutes=5))
    assert claimed2.parent_run_id == recheck2["run"].id
    qes.execute_claimed_run(db, claimed2, worker_id="w1", now=NOW + timedelta(minutes=5))
    db.commit()
    db.refresh(issue)
    assert issue.status == "waiting_verify"          # 默认待人工确认，不自动关闭
    assert issue.recheck_substatus == "passed"
    assert issue.recheck_pass_streak == 1
    # 独立验证人审核证据后关闭（F03：evaluate_trusted_recheck 通过）
    ok, errors, evidence = qes.evaluate_trusted_recheck(db, issue)
    assert ok, errors
    assert evidence["kind"] == "auto_recheck"
    qgs.verify_issue(db, issue, expected_lock_version=issue.lock_version, passed=True,
                     actor="verifier", reason="复测证据核验通过",
                     evidence_snapshot=evidence)
    db.commit()
    db.refresh(issue)
    assert issue.status == "resolved" and issue.resolved_by == "verifier"
    # 关闭后同范围再 FAIL → 复发链（T20：新单 recurrence_of 指向已关单）
    fake_executors["RULE-QC-207-001"] = qes.DetectorOutcome("fail", metric_value=8.0, numerator=8, denominator=100)
    parent3, child3, _ = run_chain(db, control, outcome="fail")
    recurrences = db.scalars(
        select(QualityIssue).where(QualityIssue.control_id == control.id, QualityIssue.issue_type == "data_defect")
    ).all()
    assert len(recurrences) == 2
    new_issue = [i for i in recurrences if i.id != issue.id][0]
    assert new_issue.recurrence_of_issue_id == issue.id
    assert new_issue.recurrence_no == 1


def test_t16_recheck_outcome_idempotent_and_streak_reset(db, fake_executors):
    control, det, issue, recheck_parent = _prepare_assigned_issue(db, fake_executors, fail_first=True)
    # 修复 fixture：复测 PASS（首轮建单是 FAIL）
    fake_executors["RULE-QC-207-001"] = qes.DetectorOutcome("pass", metric_value=0.0, numerator=0, denominator=100)
    child = db.scalar(select(QualityRun).where(QualityRun.parent_run_id == recheck_parent.id))
    claimed = qes.claim_next_run(db, "w1", now=NOW)
    qes.execute_claimed_run(db, claimed, worker_id="w1", now=NOW)
    db.commit()
    db.refresh(issue)
    assert issue.recheck_pass_streak == 1
    # 重复归并（迟到回写/恢复路径重算）：streak 不重复计数
    qes._aggregate_parent(db, recheck_parent.id, now=NOW)
    db.commit()
    db.refresh(issue)
    assert issue.recheck_pass_streak == 1
    # 通知幂等：同 run 只发一次
    notes = db.scalars(select(QualityNotification).where(QualityNotification.issue_id == issue.id)).all()
    assert len(notes) == 1
    # 新一轮 FAIL 复测 → streak 归零（连续性被 FAIL 中断）
    fake_executors["RULE-QC-207-001"] = qes.DetectorOutcome("fail", metric_value=3.0, numerator=3, denominator=100)
    qgs.transition_issue(db, issue, to_status="in_progress", expected_lock_version=issue.lock_version,
                         actor="verifier", reason="复测退回", reopen_as_recurrence=False)
    db.commit()
    # in_progress → waiting_verify 再提交复测
    qgs.request_verification(db, issue, expected_lock_version=issue.lock_version,
                             actor="p_handler", reason="再修", action_plan="再修")
    issue.remediation_submitted_at = NOW + timedelta(minutes=9)  # 钉在复测(NOW+10)之前
    db.commit()
    recheck2 = qes.create_run(db, control, purpose="recheck", trigger_kind="recheck",
                              requested_by="p_handler",
                              idempotency_key=f"recheck:{issue.id}:{issue.lock_version}",
                              issue_id=issue.id, now=NOW + timedelta(minutes=10))
    db.commit()
    claimed2 = qes.claim_next_run(db, "w1", now=NOW + timedelta(minutes=10))
    qes.execute_claimed_run(db, claimed2, worker_id="w1", now=NOW + timedelta(minutes=10))
    db.commit()
    db.refresh(issue)
    assert issue.recheck_substatus == "failed" and issue.recheck_pass_streak == 0


# ── T17/T11：NO_DATA 不能作为整改关闭证据 ───────────────────────────────

def test_t17_no_data_recheck_blocks_close(db, fake_executors):
    control, det, issue, recheck_parent = _prepare_assigned_issue(db, fake_executors, fail_first=True)
    fake_executors["RULE-QC-207-001"] = qes.DetectorOutcome(
        "no_data", metric_value=0.0, numerator=0, denominator=0, error_code="EMPTY_SCOPE")
    child = db.scalar(select(QualityRun).where(QualityRun.parent_run_id == recheck_parent.id))
    claimed = qes.claim_next_run(db, "w1", now=NOW)
    qes.execute_claimed_run(db, claimed, worker_id="w1", now=NOW)
    db.commit()
    db.refresh(issue)
    assert issue.recheck_substatus == "blocked"
    assert issue.status == "waiting_verify"  # 不退回也不关闭
    ok, errors, _ = qes.evaluate_trusted_recheck(db, issue)
    assert not ok and any("passed" in e for e in errors)


# ── T20：accepted_risk 有效期抑制 / 到期重新发现 ─────────────────────────

def test_t20_accepted_risk_suppression_and_expiry(db, fake_executors):
    fake_executors["RULE-QC-207-RISK"] = qes.DetectorOutcome("fail", metric_value=5.0, numerator=5, denominator=100)
    control, det = make_control(db, code="QC-207-RISK")
    parent, child, _ = run_chain(db, control, outcome="fail")
    issue = db.scalar(select(QualityIssue).where(QualityIssue.control_id == control.id))
    qgs.transition_issue(db, issue, to_status="acknowledged", expected_lock_version=issue.lock_version,
                         actor="h", reason="确认")
    qgs.transition_issue(
        db, issue, to_status="accepted_risk", expected_lock_version=issue.lock_version,
        actor="risk_owner", reason="接受风险",
        risk_reason="业务可接受", risk_approver="boss",
        risk_review_at=date.today() + timedelta(days=30),
    )
    db.commit()
    # 有效期内 FAIL：观测照记，不建复发单
    parent2, child2, out2 = run_chain(db, control, outcome="fail")
    assert out2.get("observation", {}).get("outcome") == "risk_suppressed"
    issues = db.scalars(select(QualityIssue).where(QualityIssue.control_id == control.id)).all()
    assert len(issues) == 1
    # 复审到期后 FAIL：重新发现，复发链且不算整改通过
    issue.risk_review_at = date.today() - timedelta(days=1)
    db.commit()
    parent3, child3, out3 = run_chain(db, control, outcome="fail")
    assert out3.get("observation", {}).get("outcome") == "issue_created"
    issues = db.scalars(select(QualityIssue).where(QualityIssue.control_id == control.id)).all()
    assert len(issues) == 2
    new_issue = max(issues, key=lambda i: i.id)
    assert new_issue.recurrence_no == 1


# ── T21：监测缺口独立于数据缺陷 ──────────────────────────────────────────

def test_t21_monitoring_gap_independent_from_data_defect(db, fake_executors):
    fake_executors["RULE-QC-207-MG"] = qes.DetectorOutcome("fail", metric_value=5.0, numerator=5, denominator=100)
    control, det = make_control(db, code="QC-207-MG")
    parent, child, _ = run_chain(db, control, outcome="fail")
    issue = db.scalar(select(QualityIssue).where(QualityIssue.control_id == control.id))
    assert issue.issue_type == "data_defect"
    # 数据缺陷存在时检测通道阻塞：blocked → 独立监测缺口单（F08）
    fake_executors["RULE-QC-207-MG"] = qes.DetectorOutcome("blocked", error_code="SOURCE_UNRESOLVED",
                                                           error_message_sanitized="源未解析")
    parent2, child2, out2 = run_chain(db, control, outcome="blocked")
    assert out2.get("observation", {}).get("outcome") == "monitoring_gap_created"
    gaps = db.scalars(
        select(QualityIssue).where(QualityIssue.control_id == control.id, QualityIssue.issue_type == "monitoring_gap")
    ).all()
    assert len(gaps) == 1
    assert gaps[0].scope_key.startswith("monitoring:")  # 独立归并键
    assert gaps[0].id != issue.id
    # 数据缺陷单不被监测恢复/阻塞关闭或冲淡
    db.refresh(issue)
    assert issue.status == "new" and issue.issue_type == "data_defect"


# ── T33：观测写入失败 → 全回滚不留半建状态 ───────────────────────────────

def test_t33_observation_write_failure_fails_run_cleanly(db, fake_executors, monkeypatch):
    fake_executors["RULE-QC-207-001"] = qes.DetectorOutcome("fail", metric_value=5.0, numerator=5, denominator=100)
    control, det = make_control(db, code="QC-207-T33")
    result = qes.create_run(db, control, requested_by="u1", now=NOW)
    db.commit()
    claimed = qes.claim_next_run(db, "w1", now=NOW)

    def boom(*a, **k):
        raise RuntimeError("simulated observation write failure")

    monkeypatch.setattr(qes.qgs, "apply_observation", boom)
    out = qes.execute_claimed_run(db, claimed, worker_id="w1", now=NOW)
    assert out["status"] == "failed" and out.get("error") == "observation_write_failed"
    monkeypatch.undo()
    db.commit()
    child = db.get(QualityRun, claimed.id)
    assert child.status == "failed" and child.error_code == "OBSERVATION_WRITE_FAILED"
    # 零观测、零问题（不半建单）
    assert db.scalars(select(QualityObservation).where(QualityObservation.control_id == control.id)).all() == []
    assert db.scalars(select(QualityIssue).where(QualityIssue.control_id == control.id)).all() == []
    # 无通知泄漏
    assert db.scalars(select(QualityNotification)).all() == []


# ── T26：站内提醒幂等（同日同单同类至多一条） ────────────────────────────

def test_t26_reminder_scan_idempotent(db, fake_executors):
    fake_executors["RULE-QC-207-001"] = qes.DetectorOutcome("fail", metric_value=5.0, numerator=5, denominator=100)
    control, det = make_control(db, code="QC-207-NOTIF")
    parent, child, _ = run_chain(db, control, outcome="fail")
    issue = db.scalar(select(QualityIssue).where(QualityIssue.control_id == control.id))
    issue.due_at = date.today() + timedelta(days=1)
    issue.assignee_user_identifier = "p_handler"
    db.commit()
    today = date.today()
    c1 = qes.scan_due_notifications(db, today=today)
    c2 = qes.scan_due_notifications(db, today=today)
    db.commit()
    assert c1["remind_due"] == 1 and c2["remind_due"] == 0
    notes = db.scalars(select(QualityNotification).where(QualityNotification.issue_id == issue.id)).all()
    assert len(notes) == 1 and notes[0].recipient == "p_handler"
    # 逾期升级（>3 天）→ 督办人；同日重复扫描不重复
    issue.due_at = date.today() - timedelta(days=5)
    issue.supervisor_user_identifier = "sup1"
    db.commit()
    c3 = qes.scan_due_notifications(db, today=today)
    c4 = qes.scan_due_notifications(db, today=today)
    db.commit()
    assert c3["overdue"] == 1 and c3["escalate"] == 1
    assert c4["overdue"] == 0 and c4["escalate"] == 0
    escalations = db.scalars(
        select(QualityNotification).where(
            QualityNotification.issue_id == issue.id, QualityNotification.notify_type == "escalate")
    ).all()
    assert len(escalations) == 1 and escalations[0].recipient == "sup1"


# ── T06：调度入队幂等（错过窗口只补一个） ───────────────────────────────

def test_t06_schedule_enqueue_once_per_slot(db, fake_executors, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "quality_execution_allowed_hours", "", raising=False)
    fake_executors["RULE-QC-207-SCHED"] = qes.DetectorOutcome("pass", numerator=0, denominator=10)
    control, _ = make_control(db, code="QC-207-SCHED", schedule=True)
    control.schedule_expr = "0 2 * * *"  # 每日 02:00
    control.next_run_at = NOW - timedelta(hours=3)  # 已错过
    db.commit()
    s1 = qes.enqueue_due_scheduled_runs(db, now=NOW)
    s2 = qes.enqueue_due_scheduled_runs(db, now=NOW + timedelta(minutes=1))
    db.commit()
    assert s1["runs_enqueued"] >= 1
    assert s2["runs_enqueued"] == 0  # 同窗不重复入队
    parents = db.scalars(
        select(QualityRun).where(QualityRun.control_id == control.id, QualityRun.parent_run_id.is_(None))
    ).all()
    assert len(parents) == 1
    db.refresh(control)
    nxt = control.next_run_at
    if nxt is not None and nxt.tzinfo is None:
        nxt = nxt.replace(tzinfo=timezone.utc)
    assert nxt is not None and nxt > NOW  # 推进到未来，不补历史洪峰
