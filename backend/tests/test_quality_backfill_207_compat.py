"""208 A5（207 R09 补全）：174 旧版合成存量 × 207 回填兼容验证（隔离库 PG）。

合成存量形态（208 A包第5条）：无源 scope 清单、旧事件/观测（legacy precision）、
已关闭单、复发单。验收：
- 盘点如实列出（无源清单 / legacy scope 旧单 / 待补快照清单）；
- --apply 只补当前版本修订快照（origin=backfill），不伪造历史版本；
- 二次 apply 零新增（幂等）；
- 历史守恒：旧单 scope/状态/复发链、旧观测精度标记、审计条数不因回填变化。
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select

from app.models.governance_base import GovernAuditLog
from app.models.quality_governance import (
    QualityControl,
    QualityControlDetector,
    QualityControlRevision,
    QualityIssue,
    QualityIssueEvent,
    QualityObservation,
)

from scripts.quality_backfill_207 import apply_revisions, inventory

NOW = datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc)


def _seed_legacy(db):
    """174 时代合成存量：三条清单（一无源）+旧观测（两种 legacy 精度）+已关闭/复发单+旧事件。"""
    c1 = QualityControl(
        control_code="QC-174-L1", version=1, title="旧清单-有源",
        lifecycle_status="active", dimension="completeness", category="R-CNT",
        primary_system_code="HIS", source_code="his_src", object_key="HIS|ods|PAT_VISIT",
        metric_name="missing_rate", metric_unit="%", comparator="gt", threshold_value=0,
        no_data_policy="fail", verification_policy="manual", created_by="legacy", updated_by="legacy",
    )
    c2 = QualityControl(
        control_code="QC-174-L2", version=1, title="旧清单-无源",
        lifecycle_status="active", dimension="completeness", category="R-CNT",
        primary_system_code="HIS", source_code=None, object_key=None,
        metric_name="dup_rate", metric_unit="%", comparator="gt", threshold_value=0,
        no_data_policy="fail", verification_policy="manual", created_by="legacy", updated_by="legacy",
    )
    db.add_all([c1, c2])
    db.flush()
    db.add_all([
        QualityControlDetector(control_id=c1.id, detector_kind="manual", detector_ref="M-1",
                               detector_version="1", status="active", created_by="legacy", updated_by="legacy"),
        QualityControlDetector(control_id=c2.id, detector_kind="manual", detector_ref="M-2",
                               detector_version="1", status="active", created_by="legacy", updated_by="legacy"),
    ])
    # 已关闭旧单（legacy scope：标题截断，无 sk: 前缀）+ 复发链
    closed = QualityIssue(
        issue_code="QI-174-C1", control_id=c1.id, issue_type="data_defect",
        title="旧标题截断的scope单", scope_key="旧标题截断的scope单",
        status="resolved", severity="low", opened_control_version=1,
        resolution_summary="旧流程关闭", resolved_at=NOW, resolved_by="legacy",
        created_by="legacy", updated_by="legacy",
    )
    db.add(closed)
    db.flush()
    db.add(QualityIssue(
        issue_code="QI-174-R1", control_id=c1.id, issue_type="data_defect",
        title="复发单", scope_key="旧标题截断的scope单",
        status="new", severity="low", recurrence_of_issue_id=closed.id, recurrence_no=1,
        created_by="legacy", updated_by="legacy",
    ))
    db.add(QualityIssueEvent(issue_id=closed.id, event_type="comment_added",
                             reason="旧事件", actor_user_identifier="legacy"))
    # 旧观测：174 两种历史精度标记
    db.add_all([
        QualityObservation(
            control_id=c1.id, control_version=1, run_key="legacy-run-1",
            scope_key="旧标题截断的scope单", result_status="fail",
            metric_value=5.0, numerator=5, denominator=100, metric_unit="%",
            source_kind="probe_finding", source_record_ref="legacy:probe",
            historical_precision="summary_backfill", observed_at=NOW,
        ),
        QualityObservation(
            control_id=c1.id, control_version=1, run_key="legacy-run-2",
            scope_key="旧标题截断的scope单", result_status="pass",
            metric_value=0.0, numerator=0, denominator=100, metric_unit="%",
            source_kind="manual", source_record_ref="legacy:manual",
            historical_precision="latest_snapshot", observed_at=NOW,
        ),
    ])
    db.commit()
    return c1, c2


@pytest.fixture(autouse=True)
def legacy_seed(db_session):
    return _seed_legacy(db_session)


def _audit_count(db) -> int:
    return db.scalar(select(func.count()).select_from(GovernAuditLog)) or 0


def test_a5_inventory_lists_legacy_shapes(db_session):
    inv = inventory(db_session)
    assert inv["controls"] >= 2
    assert "QC-174-L2" in inv["controls_without_source_code"]
    assert "QC-174-L1" not in inv["controls_without_source_code"]
    assert inv["legacy_scope_issue_count"] >= 2  # 已关闭单 + 复发单均非 sk: 前缀
    assert "QI-174-C1" in inv["legacy_scope_issues_not_trusted_for_auto_verify"]
    assert set(["QC-174-L1", "QC-174-L2"]) <= set(inv["controls_needing_revision_snapshot"])


def test_a5_apply_creates_current_snapshots_only_then_idempotent(db_session):
    audits_before = _audit_count(db_session)
    obs_before = db_session.execute(
        select(QualityObservation.run_key, QualityObservation.historical_precision)
        .where(QualityObservation.run_key.in_(["legacy-run-1", "legacy-run-2"]))
    ).all()

    r1 = apply_revisions(db_session, actor="backfill-208A")
    assert set(r1["revisions_created"]) >= {"QC-174-L1", "QC-174-L2"}
    revs = db_session.scalars(select(QualityControlRevision)).all()
    by_control = {}
    for r in revs:
        if r.origin == "backfill":
            by_control.setdefault(r.control_id, []).append(r)
    assert len(by_control) >= 2
    for rows in by_control.values():
        assert len(rows) == 1  # 只补当前版本一个快照，不伪造历史版本
        assert rows[0].version == 1

    # 二跑零新增（幂等）
    r2 = apply_revisions(db_session, actor="backfill-208A")
    assert r2["created_count"] == 0
    total_after = db_session.scalar(select(func.count()).select_from(QualityControlRevision)) or 0
    r3 = apply_revisions(db_session, actor="backfill-208A")
    assert r3["created_count"] == 0
    total_after3 = db_session.scalar(select(func.count()).select_from(QualityControlRevision)) or 0
    assert total_after3 == total_after


def test_a5_backfill_preserves_legacy_rows_and_precision(db_session):
    """回填后：旧单状态/scope/复发链、旧事件、旧观测精度、审计条数全部守恒。"""
    from app.models.quality_governance import QualityRun

    closed_before = db_session.scalar(select(QualityIssue).where(QualityIssue.issue_code == "QI-174-C1"))
    events_before = db_session.scalar(
        select(func.count()).select_from(QualityIssueEvent)
        .where(QualityIssueEvent.issue_id == closed_before.id))
    audits_before = _audit_count(db_session)
    runs_before = db_session.scalar(select(func.count()).select_from(QualityRun)) or 0

    apply_revisions(db_session, actor="backfill-208A")
    apply_revisions(db_session, actor="backfill-208A")

    closed_after = db_session.scalar(select(QualityIssue).where(QualityIssue.issue_code == "QI-174-C1"))
    assert closed_after.status == "resolved"
    assert closed_after.scope_key == "旧标题截断的scope单"
    assert closed_after.resolved_by == "legacy"
    recur = db_session.scalar(select(QualityIssue).where(QualityIssue.issue_code == "QI-174-R1"))
    assert recur.recurrence_of_issue_id == closed_after.id and recur.recurrence_no == 1
    events_after = db_session.scalar(
        select(func.count()).select_from(QualityIssueEvent)
        .where(QualityIssueEvent.issue_id == closed_after.id))
    assert events_after == events_before
    prec = dict(db_session.execute(
        select(QualityObservation.run_key, QualityObservation.historical_precision)
        .where(QualityObservation.run_key.in_(["legacy-run-1", "legacy-run-2"]))
    ).all())
    assert prec == {"legacy-run-1": "summary_backfill", "legacy-run-2": "latest_snapshot"}
    assert (db_session.scalar(select(func.count()).select_from(QualityObservation)) or 0) == 2
    assert _audit_count(db_session) == audits_before  # 回填不伪造审计
    assert (db_session.scalar(select(func.count()).select_from(QualityRun)) or 0) == runs_before  # 不造运行单
