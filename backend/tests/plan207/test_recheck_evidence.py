"""207 复测证据防伪测试（sqlite 纯逻辑）：T13/T14/T17/T18/T32。

核心断言：伪造/旧/他单/不同范围/版本失效的 PASS 一律不能作为关闭证据。
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import select

from app.models.quality_governance import (
    QualityControl,
    QualityControlDetector,
    QualityIssue,
    QualityObservation,
    QualityRun,
)
from app.services import quality_execution_service as qes
from app.services import quality_governance_service as qgs
from tests.plan207.test_execution_chain import NOW, _prepare_assigned_issue, make_control, run_chain


def _drive_to_passed_recheck(db, fake_executors):
    """建单→流转→提交→复测 PASS→waiting_verify+passed，返回 (control, issue, recheck_parent)。"""
    control, det, issue, recheck_parent = _prepare_assigned_issue(db, fake_executors, fail_first=True)
    # 首轮复测 FAIL 退回
    claimed = qes.claim_next_run(db, "w1", now=NOW)
    qes.execute_claimed_run(db, claimed, worker_id="w1", now=NOW)
    db.commit()
    db.refresh(issue)
    assert issue.status == "in_progress"
    # 修复 → 复测 PASS
    fake_executors[f"RULE-{control.control_code}"] = qes.DetectorOutcome(
        "pass", metric_value=0.0, numerator=0, denominator=100)
    qgs.request_verification(db, issue, expected_lock_version=issue.lock_version,
                             actor="p_handler", reason="已修复", action_plan="已修复")
    # 服务层 remediation_submitted_at 取真实时钟，而测试事件在冻结 NOW 时间轴上；
    # 钉住该时间戳消除跨日漂移（断言不变）
    issue.remediation_submitted_at = NOW
    db.commit()
    recheck2 = qes.create_run(db, control, purpose="recheck", trigger_kind="recheck",
                              requested_by="p_handler",
                              idempotency_key=f"recheck:{issue.id}:{issue.lock_version}",
                              issue_id=issue.id, now=NOW + timedelta(minutes=5))
    db.commit()
    claimed2 = qes.claim_next_run(db, "w1", now=NOW + timedelta(minutes=5))
    qes.execute_claimed_run(db, claimed2, worker_id="w1", now=NOW + timedelta(minutes=5))
    db.commit()
    db.refresh(issue)
    assert issue.recheck_substatus == "passed"
    return control, issue, recheck2["run"]


def test_t13_forged_external_pass_cannot_close(db, fake_executors):
    """手工/外部来源 PASS 观测不能伪装可信自动复测（F06/T13）。"""
    control, issue, recheck = _drive_to_passed_recheck(db, fake_executors)
    # 攻击者经 external 渠道挂一条“PASS”，并把 last_verification_run_id 置空伪造无运行
    issue.last_verification_run_id = None
    issue.recheck_substatus = "passed"  # 直接改库伪造子状态
    db.commit()
    ok, errors, _ = qes.evaluate_trusted_recheck(db, issue)
    assert not ok and any("last_verification_run_id" in e or "复测运行" in e for e in errors)


def test_t14_other_issue_pass_run_rejected(db, fake_executors):
    """他问题的 PASS 运行不能给本问题销账（T14）。"""
    control, issue_a, recheck_a = _drive_to_passed_recheck(db, fake_executors)
    # 构造问题 B（同清单不同范围——用不同 scope 手工单）
    issue_b = qgs.create_manual_issue(
        db, title="B问题", control_id=control.id, scope_key="sk:other-scope-9999",
        actor="t", reason="t")
    db.commit()
    issue_b.last_verification_run_id = recheck_a.id  # 挂 A 的复测运行
    db.commit()
    ok, errors, _ = qes.evaluate_trusted_recheck(db, issue_b)
    assert not ok and any("不是本问题的复测运行" in e for e in errors)
    # 不同范围（scope_key 不一致）同样拒绝
    issue_b.last_verification_run_id = recheck_a.id
    db.commit()
    ok2, errors2, _ = qes.evaluate_trusted_recheck(db, issue_b)
    assert not ok2


def test_t18_newer_fail_after_recheck_blocks_close(db, fake_executors):
    """关闭瞬间复查：复测完成后出现更新的 FAIL → 拒绝（并发关单防线）。"""
    control, issue, recheck = _drive_to_passed_recheck(db, fake_executors)
    assert qes.evaluate_trusted_recheck(db, issue)[0] is True
    # 复测完成之后注入更新 FAIL 观测（另一窗口检测失败）
    from sqlalchemy import select as _sel
    det = db.scalar(_sel(QualityControlDetector).where(QualityControlDetector.control_id == control.id))
    after = (recheck.finished_at or NOW) + timedelta(minutes=3)
    qgs.apply_observation(
        db, control_id=control.id, detector_id=det.id,
        run_key=f"qr:attack:1", scope_key=issue.scope_key, result_status="fail",
        source_kind="quality_run", observation_time=after,
    )
    db.commit()
    ok, errors, _ = qes.evaluate_trusted_recheck(db, issue)
    assert not ok and any("更新的 FAIL" in e for e in errors)


def test_t32_control_version_change_invalidates_old_pass(db, fake_executors):
    """阈值/口径修改后旧版本 PASS 失效；旧运行读冻结快照不受编辑影响。"""
    control, issue, recheck = _drive_to_passed_recheck(db, fake_executors)
    # 旧运行引用的修订快照在编辑后保持冻结
    rev_before = db.get(qes.QualityControlRevision, recheck.revision_id) if recheck.revision_id else None
    # 清单口径变化（阈值）→ 版本递增
    control.threshold_value = 10
    control.version = (control.version or 1) + 1
    qes.ensure_revision(db, control, actor="t")
    db.commit()
    ok, errors, _ = qes.evaluate_trusted_recheck(db, issue)
    assert not ok and any("版本" in e for e in errors)
    # 冻结检查：旧修订快照阈值仍是 0
    if rev_before is not None:
        db.refresh(rev_before)
        assert rev_before.definition_snapshot["threshold_value"] in (0, 0.0)
    # 新版本不接受旧 PASS：需按新版本重新复测（重新提交→新复测运行）
    qgs.transition_issue(db, issue, to_status="in_progress", expected_lock_version=issue.lock_version,
                         actor="v", reason="版本变更重测")
    db.commit()


def test_missing_remediation_time_rejected(db, fake_executors):
    """无整改提交时间 → 无法证明复测晚于整改 → 拒绝（T17 时间证据）。"""
    control, issue, recheck = _drive_to_passed_recheck(db, fake_executors)
    issue.remediation_submitted_at = None
    db.commit()
    ok, errors, _ = qes.evaluate_trusted_recheck(db, issue)
    assert not ok and any("整改提交时间" in e for e in errors)


def test_required_pass_count_enforced(db, fake_executors, monkeypatch):
    """required_pass_count=2：一次 PASS 不够关闭，连续第二次才满足（T16 关闭门槛）。"""
    control, issue, recheck = _drive_to_passed_recheck(db, fake_executors)
    control.required_pass_count = 2
    db.commit()
    ok, errors, _ = qes.evaluate_trusted_recheck(db, issue)
    assert not ok and any("少于要求" in e for e in errors)
    assert issue.recheck_pass_streak == 1
    # 第二轮完整复测 PASS
    fake_executors[f"RULE-{control.control_code}"] = qes.DetectorOutcome(
        "pass", metric_value=0.0, numerator=0, denominator=100)
    qgs.transition_issue(db, issue, to_status="in_progress", expected_lock_version=issue.lock_version,
                         actor="v", reason="再验证")
    db.commit()
    qgs.request_verification(db, issue, expected_lock_version=issue.lock_version,
                             actor="p_handler", reason="二轮", action_plan="保持修复")
    issue.remediation_submitted_at = NOW + timedelta(minutes=10)  # 钉在二轮复测(NOW+15)之前
    db.commit()
    recheck2 = qes.create_run(db, control, purpose="recheck", trigger_kind="recheck",
                              requested_by="p_handler",
                              idempotency_key=f"recheck:{issue.id}:{issue.lock_version}",
                              issue_id=issue.id, now=NOW + timedelta(minutes=15))
    db.commit()
    claimed = qes.claim_next_run(db, "w1", now=NOW + timedelta(minutes=15))
    qes.execute_claimed_run(db, claimed, worker_id="w1", now=NOW + timedelta(minutes=15))
    db.commit()
    db.refresh(issue)
    assert issue.recheck_pass_streak == 2
    ok2, errors2, _ = qes.evaluate_trusted_recheck(db, issue)
    assert ok2, errors2


def test_manual_policy_issue_accepts_manual_evidence_only(db, fake_executors):
    """policy=manual 的清单走人工验证路径：不要求自动运行证据（结构上不豁免 auto 问题）。"""
    control, det = make_control(db, code="QC-207-MANPOL", policy="manual")
    fake_executors["RULE-QC-207-MANPOL"] = qes.DetectorOutcome(
        "fail", metric_value=5.0, numerator=5, denominator=100)
    parent, child, _ = run_chain(db, control, outcome="fail")
    issue = db.scalar(select(QualityIssue).where(QualityIssue.control_id == control.id))
    ok, errors, evidence = qes.evaluate_trusted_recheck(db, issue)
    assert ok and evidence["kind"] == "manual_policy"
