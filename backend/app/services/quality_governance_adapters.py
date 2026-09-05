"""174 S3: 质量治理台账来源适配器（probe_template / quality_rule / manual 三类）。

职责：把既有检测证据（ProbeFinding / ProbeRun.metrics_summary / QualityFinding）
幂等转写为统一 QualityObservation，并经 apply_observation 执行 FAIL 归并建单。

铁律（174 §10.3）：
  - 只迁移当前可证实的失败问题，PASS 只回填观测；
  - 不伪造历史（historical_precision 如实标注 latest_snapshot/summary_backfill）；
  - 旧 ProbeFinding/QualityFinding 不删除、不改主状态；
  - 所有 run_key 由稳定来源引用派生，重复执行零新增。
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.probe import AssetProbeFinding, AssetProbeRun
from ..models.quality import QualityFinding
from ..models.quality_governance import (
    QualityControl,
    QualityControlDetector,
    QualityObservation,
)
from . import quality_governance_service as qgs

_PROBE_ACTIVATE_STATUSES = ("open", "confirmed")


def _load_rm(detector: QualityControlDetector) -> dict[str, Any]:
    rm = detector.result_mapping or {}
    return rm if isinstance(rm, dict) else {}


def _norm(value: Any) -> str:
    return (value or "").strip()


# ─────────────────────────────────────────────────────────────────────────
# probe_template 适配器
# ─────────────────────────────────────────────────────────────────────────

def sync_probe_findings(
    db: Session,
    *,
    actor: str = "seed:quality_governance",
    dry_run: bool = False,
) -> dict[str, Any]:
    """当前失败 ProbeFinding → FAIL Observation（→ 活动 Issue）。

    匹配键 = detector.result_mapping 里的 probe_type + metric_name（12 模板全局唯一）。
    run_key = "probe-finding:{id}:{last_seen_run}"——同窗重跑幂等，新窗产生新观测。
    """
    stats = {"detectors": 0, "observations_written": 0, "duplicates": 0,
             "issues_created": 0, "issues_updated": 0, "skipped_terminal": 0}
    detectors = db.scalars(
        select(QualityControlDetector).where(
            QualityControlDetector.detector_kind == "probe_template",
            QualityControlDetector.status == "active",
        )
    ).all()
    for det in detectors:
        rm = _load_rm(det)
        probe_type, metric_name = _norm(rm.get("probe_type")), _norm(rm.get("metric_name"))
        if not probe_type or not metric_name:
            continue
        stats["detectors"] += 1
        findings = db.scalars(
            select(AssetProbeFinding).where(
                AssetProbeFinding.probe_type == probe_type,
                AssetProbeFinding.metric_name == metric_name,
            )
        ).all()
        control = db.get(QualityControl, det.control_id)
        if control is None:
            continue
        for f in findings:
            if f.status not in _PROBE_ACTIVATE_STATUSES:
                stats["skipped_terminal"] += 1
                continue
            result = qgs.apply_observation(
                db,
                control_id=control.id,
                detector_id=det.id,
                control_version=control.version,
                run_key=f"probe-finding:{f.id}:{f.last_seen_run}",
                scope_key=(f.object_desc or "")[:256],
                result_status="fail",
                window_start=f.window_start,
                window_end=f.window_end,
                metric_value=float(f.metric_value) if f.metric_value is not None else None,
                metric_unit=f.metric_unit,
                threshold_snapshot={
                    "comparator": "gt",
                    "threshold_value": float(f.threshold) if f.threshold is not None else None,
                },
                control_definition_snapshot={
                    "title": control.title,
                    "metric_name": control.metric_name,
                    "metric_unit": control.metric_unit,
                    "object_key": control.object_key,
                    "no_data_policy": control.no_data_policy,
                },
                source_kind="probe_finding",
                source_record_ref=f"asset_probe_findings:{f.id}",
                evidence_digest=f.evidence_digest,
                evidence_ref=f"probe_run:{f.last_seen_run}",
                historical_precision="latest_snapshot",
                actor=actor,
            )
            outcome = result["outcome"]
            if outcome == "duplicate":
                stats["duplicates"] += 1
            else:
                stats["observations_written"] += 1
                if outcome == "issue_created":
                    stats["issues_created"] += 1
                elif outcome == "issue_updated":
                    stats["issues_updated"] += 1
    if dry_run:
        db.rollback()
    return stats


def sync_probe_run_summary(
    db: Session,
    *,
    actor: str = "seed:quality_governance",
    run_id: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """ProbeRun.metrics_summary → PASS（绿色）/ERROR/BLOCKED Observation。

    - triggered=False 且 status=ok → pass（绿色观测，不建单）；
    - BLOCKED → blocked（→ monitoring_gap）；
    - error/timeout → error（只记录）；
    - triggered=True 的 FAIL 走 sync_probe_findings（finding 携带窗口证据），此处跳过防双写。
    run_key = "probe-run:{run_id}:{code}"，天然按 run 幂等。
    historical_precision=summary_backfill（运行汇总回填，非逐窗口精度）。
    """
    stats = {"run_id": None, "observations_written": 0, "duplicates": 0,
             "pass": 0, "blocked": 0, "error": 0, "skipped": 0}
    if run_id is not None:
        run = db.scalar(select(AssetProbeRun).where(AssetProbeRun.run_id == run_id))
    else:
        run = db.scalar(
            select(AssetProbeRun)
            .where(AssetProbeRun.status.in_(("done", "partial")))
            .order_by(AssetProbeRun.id.desc())
        )
    if run is None or not run.metrics_summary:
        if dry_run:
            db.rollback()
        return stats
    stats["run_id"] = run.run_id
    summary = run.metrics_summary
    detectors = db.scalars(
        select(QualityControlDetector).where(
            QualityControlDetector.detector_kind == "probe_template",
            QualityControlDetector.status == "active",
        )
    ).all()
    by_ref = {d.detector_ref: d for d in detectors}
    window_start = run.started_at.date() if run.started_at else None
    window_end = run.finished_at.date() if run.finished_at else window_start
    for code, rec in (summary.items() if isinstance(summary, dict) else []):
        det = by_ref.get(code)
        if det is None:
            continue
        control = db.get(QualityControl, det.control_id)
        if control is None:
            continue
        rec_status = rec.get("status")
        err_text = _norm(rec.get("error"))
        triggered = bool(rec.get("triggered"))
        if triggered:
            stats["skipped"] += 1  # FAIL 走 finding 通道，防双写
            continue
        if rec_status == "ok":
            result_status = "pass"
        elif err_text.upper().startswith("BLOCKED"):
            result_status = "blocked"
        else:
            result_status = "error"
        result = qgs.apply_observation(
            db,
            control_id=control.id,
            detector_id=det.id,
            control_version=control.version,
            run_key=f"probe-run:{run.run_id}:{code}",
            scope_key=(_norm(_load_rm(det).get("object_desc")) or control.title)[:256],
            result_status=result_status,
            window_start=window_start,
            window_end=window_end,
            metric_value=float(rec["metric_value"]) if rec.get("metric_value") is not None else None,
            metric_unit=_norm(_load_rm(det).get("metric_unit")) or None,
            threshold_snapshot={
                "comparator": control.comparator,
                "threshold_value": float(control.threshold_value)
                if control.threshold_value is not None
                else None,
            },
            control_definition_snapshot={
                "title": control.title,
                "metric_name": control.metric_name,
                "metric_unit": control.metric_unit,
                "object_key": control.object_key,
                "no_data_policy": control.no_data_policy,
            },
            source_kind="probe_run",
            source_record_ref=f"asset_probe_runs:{run.id}:{code}",
            evidence_ref=f"probe_run:{run.run_id}",
            historical_precision="summary_backfill",
            error_code=None if result_status == "pass" else (rec_status or result_status),
            error_message_sanitized=err_text[:512] or None,
            actor=actor,
        )
        if result["outcome"] == "duplicate":
            stats["duplicates"] += 1
        else:
            stats["observations_written"] += 1
            stats[result_status] = stats.get(result_status, 0) + 1
    if dry_run:
        db.rollback()
    return stats


# ─────────────────────────────────────────────────────────────────────────
# quality_rule 适配器（元数据质控 QualityFinding → Observation）
# ─────────────────────────────────────────────────────────────────────────

def sync_quality_findings(
    db: Session,
    *,
    actor: str = "seed:quality_governance",
    dry_run: bool = False,
) -> dict[str, Any]:
    """open 状态 QualityFinding → FAIL Observation（→ 活动 Issue）。

    匹配键 = detector.detector_ref（= QualityRule.rule_code）。
    QualityFinding 是规则执行快照，historical_precision=latest_snapshot。
    """
    stats = {"detectors": 0, "observations_written": 0, "duplicates": 0,
             "issues_created": 0, "issues_updated": 0, "skipped_terminal": 0}
    detectors = db.scalars(
        select(QualityControlDetector).where(
            QualityControlDetector.detector_kind == "quality_rule",
            QualityControlDetector.status == "active",
        )
    ).all()
    for det in detectors:
        stats["detectors"] += 1
        control = db.get(QualityControl, det.control_id)
        if control is None:
            continue
        findings = db.scalars(
            select(QualityFinding).where(
                QualityFinding.rule_code == det.detector_ref,
                QualityFinding.status == "open",
            )
        ).all()
        for f in findings:
            scope_parts = [p for p in (f.schema_name, f.table_name, f.column_name) if p]
            scope_key = (".".join(scope_parts) or f.target_ref or f.rule_code or "unknown")[:256]
            try:
                found_at = f.found_at.date() if f.found_at else None
            except AttributeError:
                found_at = None
            result = qgs.apply_observation(
                db,
                control_id=control.id,
                detector_id=det.id,
                control_version=control.version,
                run_key=f"quality-finding:{f.id}",
                scope_key=scope_key,
                result_status="fail",
                window_start=found_at,
                window_end=found_at,
                metric_value=float(f.error_rate) if f.error_rate is not None else None,
                metric_unit="%",
                threshold_snapshot={"comparator": None, "threshold_value": None},
                control_definition_snapshot={
                    "title": control.title,
                    "metric_name": control.metric_name,
                    "object_key": control.object_key,
                    "no_data_policy": control.no_data_policy,
                },
                source_kind="quality_finding",
                source_record_ref=f"asset_quality_findings:{f.id}",
                historical_precision="latest_snapshot",
                actor=actor,
            )
            outcome = result["outcome"]
            if outcome == "duplicate":
                stats["duplicates"] += 1
            else:
                stats["observations_written"] += 1
                if outcome == "issue_created":
                    stats["issues_created"] += 1
                elif outcome == "issue_updated":
                    stats["issues_updated"] += 1
    if dry_run:
        db.rollback()
    return stats


# ─────────────────────────────────────────────────────────────────────────
# manual 适配器（手工登记问题 + 可选证据观测）
# ─────────────────────────────────────────────────────────────────────────

def create_manual_issue_with_evidence(
    db: Session,
    *,
    title: str,
    evidence_ref: str | None = None,
    evidence_note: str | None = None,
    control_id: int | None = None,
    actor: str,
    reason: str | None = None,
    issue_kwargs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """手工建单（manual 适配器入口）：POST /quality-issues 的服务层封装。

    有 control_id 时额外挂一条 manual 来源观测（含证据引用），
    使台账的观测链与自动来源一致。
    """
    kwargs = dict(issue_kwargs or {})
    issue = qgs.create_manual_issue(
        db,
        title=title,
        control_id=control_id,
        evidence_ref=evidence_ref,
        actor=actor,
        reason=reason or "手工登记",
        **kwargs,
    )
    observation_id = None
    if control_id is not None:
        control = db.get(QualityControl, control_id)
        if control is not None:
            obs = QualityObservation(
                control_id=control.id,
                control_version=control.version,
                issue_id=issue.id,
                run_key=f"manual:{issue.id}",
                scope_key=issue.scope_key or (control.object_name_snapshot or control.title)[:256],
                observed_at=datetime.now(timezone.utc),
                result_status="fail",
                source_kind="manual",
                source_record_ref=f"asset_quality_issues:{issue.id}",
                evidence_ref=evidence_ref,
                evidence_digest=evidence_note,
                historical_precision="exact",
                created_by=actor,
            )
            db.add(obs)
            db.flush()
            observation_id = obs.id
            issue.latest_observation_id = obs.id
            issue.latest_result_status = "fail"
            qgs.add_event(
                db,
                issue,
                "observation_linked",
                reason="手工证据观测挂接",
                observation_id=obs.id,
                actor=actor,
            )
    return {"issue": issue, "observation_id": observation_id}
