"""Read-only identity nightly sync log serialization.

Passwords, signatures and SQL are never returned. Operator-facing rows may
include employee number and a masked name for troubleshooting.
"""
from __future__ import annotations

from typing import Any, TYPE_CHECKING

from .identity_sync_status import normalize_status, redacted_summary, short_fingerprint

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

SUBTASK_LABELS = {
    "main_account_sync": "主账号同步",
    "jhemr_signature_sync": "嘉和签名同步",
    "jhemr_education_title_sync": "嘉和职称同步",
}
SYSTEM_LABELS = {
    "CDMS": "合理用药",
    "JHEMR": "嘉和电子病历",
    "HIS": "HIS",
}
STATUS_LABELS = {
    "success": "成功",
    "partial_success": "部分成功",
    "failed": "失败",
    "skipped": "已跳过",
    "running": "进行中",
    "overdue": "超时未跑",
    "misconfigured": "调度配置异常",
    "pending": "等待中",
    "planned": "已计划",
    "executed": "已执行",
    "rolled_back": "已回滚",
}
TRIGGER_LABELS = {
    "nightly_cron": "夜间定时",
    "host_cron": "宿主机定时",
    "host_cron_modified_sync": "宿主机增量同步",
    "manual_rerun": "手工重跑",
    "validation": "校验批次",
}
REASON_LABELS = {
    "no_target_user": "嘉和无此账号",
    "already_has_signature": "目标已有签名，未覆盖",
    "idempotent_noop": "目标无变化",
    "already_managed_both": "两端账号已存在",
    "already_exists": "目标已存在",
}


def subtask_label(code: str | None) -> str:
    return SUBTASK_LABELS.get(str(code or ""), code or "-")


def system_label(code: str | None) -> str:
    return SYSTEM_LABELS.get(str(code or "").upper(), code or "-")


def status_label(code: str | None) -> str:
    return STATUS_LABELS.get(normalize_status(code, default=str(code or "failed")), code or "-")


def trigger_label(code: str | None) -> str:
    raw = str(code or "")
    return TRIGGER_LABELS.get(raw, raw or "-")


def reason_label(code: str | None) -> str:
    raw = str(code or "")
    return REASON_LABELS.get(raw, raw or "")


def _summary_dict(row: Any) -> dict[str, Any]:
    raw = getattr(row, "params_summary", None)
    return raw if isinstance(raw, dict) else {}


def run_id_from_action(row: Any) -> str | None:
    summary = _summary_dict(row)
    if summary.get("run_id"):
        return str(summary["run_id"])
    batch_id = str(getattr(row, "batch_id", "") or "")
    if batch_id.startswith("NTL-RUN-"):
        parts = batch_id.split("-")
        if len(parts) >= 3:
            return f"{parts[1]}-{parts[2]}"
    if ":" in batch_id:
        return batch_id.split(":", 1)[0]
    return None


def _action_emp_no(row: Any) -> str:
    summary = _summary_dict(row)
    return str(summary.get("emp_no") or getattr(row, "emp_no_masked", None) or "").strip()


def _iso(value: Any) -> str | None:
    return value.isoformat() if value else None


def serialize_subtask(row: Any) -> dict[str, Any]:
    return {
        "subtask_code": row.subtask_code,
        "subtask_name": subtask_label(row.subtask_code),
        "target_system": row.target_system,
        "target_system_name": system_label(row.target_system),
        "status": normalize_status(row.status),
        "status_name": status_label(row.status),
        "planned_count": row.planned_count or 0,
        "succeeded_count": row.succeeded_count or 0,
        "skipped_count": row.skipped_count or 0,
        "failed_count": row.failed_count or 0,
        "error_classes": redacted_summary(row.error_classes if isinstance(row.error_classes, dict) else {}),
        "started_at": _iso(row.started_at),
        "finished_at": _iso(row.finished_at),
    }


def serialize_run(row: Any, subtasks: list[Any] | None = None) -> dict[str, Any]:
    items = [serialize_subtask(item) for item in (subtasks or [])]
    return {
        "run_id": row.run_id,
        "triggered_by": row.triggered_by,
        "triggered_by_name": trigger_label(row.triggered_by),
        "status": normalize_status(row.status),
        "status_name": status_label(row.status),
        "started_at": _iso(row.started_at),
        "finished_at": _iso(row.finished_at),
        "duration_ms": row.duration_ms,
        "candidates_total": row.candidates_total or 0,
        "success_count": row.success_count or 0,
        "failed_count": row.failed_count or 0,
        "skipped_count": row.skipped_count or 0,
        "watermark_advanced": bool(row.watermark_advanced),
        "circuit_breaker_triggered": bool(row.circuit_breaker_triggered),
        "last_error_class": row.last_error_class,
        "provider_code": row.provider_code,
        "subtasks": items,
    }


def serialize_action(row: Any) -> dict[str, Any]:
    summary = _summary_dict(row)
    return {
        "action_seq": row.action_seq,
        "target_system": row.target_system,
        "target_system_name": system_label(row.target_system),
        "subtask_name": subtask_label(row.subtask_code),
        "action_type": row.action_type,
        "status": row.status,
        "status_name": status_label(row.status),
        "reason_code": row.reason_code,
        "reason_name": reason_label(row.reason_code),
        "error_class": row.error_class or row.error_code_masked,
        "rows_affected": row.rows_affected,
        "emp_no": _action_emp_no(row) or None,
        "person_name_masked": summary.get("person_name_masked") or "",
        "dept_code": summary.get("dept_code") or "",
        "dept_name": summary.get("dept_name") or "",
        "job_title": summary.get("job_title") or "",
        "account_fingerprint": short_fingerprint(row.account_fingerprint),
        "executed_at": _iso(row.executed_at),
    }


def _run_ids_for_emp(db: "Session", emp_no: str) -> list[str]:
    from sqlalchemy import or_, select

    from ..core.config import settings
    from ..models.identity_sync import IdentitySyncAction
    from .identity_hmac import compute_account_fingerprint

    emp = (emp_no or "").strip()
    if not emp:
        return []
    fingerprints = []
    for system in ("JHEMR", "CDMS", "HIS"):
        try:
            fingerprints.append(compute_account_fingerprint(emp, system, settings.identity_hmac_key_ref))
        except Exception:
            continue
    filters = [IdentitySyncAction.emp_no_masked == emp]
    if fingerprints:
        filters.append(IdentitySyncAction.account_fingerprint.in_(fingerprints))
    rows = db.scalars(select(IdentitySyncAction).where(or_(*filters)).limit(300)).all()
    run_ids: list[str] = []
    seen: set[str] = set()
    for row in rows:
        run_id = run_id_from_action(row)
        if run_id and run_id not in seen:
            seen.add(run_id)
            run_ids.append(run_id)
    return run_ids


def _enrich_action_people(db: "Session", actions: list[dict[str, Any]]) -> None:
    from sqlalchemy import select

    from ..models.identity import IdentityPerson
    from .identity_sync_audit import _mask_person_name

    codes = sorted({str(item.get("emp_no") or "") for item in actions if item.get("emp_no")})
    if not codes:
        return
    people = {
        row.person_code: row
        for row in db.scalars(select(IdentityPerson).where(IdentityPerson.person_code.in_(codes))).all()
    }
    for item in actions:
        person = people.get(str(item.get("emp_no") or ""))
        if person is None:
            continue
        item["person_name_masked"] = item.get("person_name_masked") or _mask_person_name(person.person_name_cn)
        item["dept_code"] = item.get("dept_code") or (person.dept_code or "")
        item["dept_name"] = item.get("dept_name") or (person.dept_name_cn or "")
        item["job_title"] = item.get("job_title") or (person.job_title or "")


def list_sync_runs(
    db: "Session",
    *,
    page: int = 1,
    page_size: int = 20,
    status: str | None = None,
    emp_no: str | None = None,
) -> dict[str, Any]:
    from sqlalchemy import func, select

    from ..models.identity_sync import (
        IdentityCircuitBreaker,
        IdentitySchedulerRun,
        IdentitySyncAlert,
        IdentitySyncSubtask,
    )

    stmt = select(IdentitySchedulerRun)
    if status:
        stmt = stmt.where(func.lower(func.coalesce(IdentitySchedulerRun.status, "")) == status.lower())
    emp = (emp_no or "").strip()
    if emp:
        run_ids = _run_ids_for_emp(db, emp)
        stmt = stmt.where(IdentitySchedulerRun.run_id.in_(run_ids or ["__none__"]))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = list(
        db.scalars(
            stmt.order_by(IdentitySchedulerRun.started_at.desc().nullslast(), IdentitySchedulerRun.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    run_ids = [row.run_id for row in rows if row.run_id]
    subtask_map: dict[str, list[Any]] = {run_id: [] for run_id in run_ids}
    if run_ids:
        for item in db.scalars(select(IdentitySyncSubtask).where(IdentitySyncSubtask.run_id.in_(run_ids))).all():
            subtask_map.setdefault(item.run_id, []).append(item)
    last_run = db.scalar(select(IdentitySchedulerRun).order_by(IdentitySchedulerRun.started_at.desc().nullslast(), IdentitySchedulerRun.id.desc()))
    last_subtasks = []
    if last_run:
        last_subtasks = list(
            db.scalars(
                select(IdentitySyncSubtask)
                .where(IdentitySyncSubtask.run_id == last_run.run_id)
                .order_by(IdentitySyncSubtask.subtask_code)
            ).all()
        )
    breakers = {
        row.breaker_key: row
        for row in db.scalars(select(IdentityCircuitBreaker)).all()
    }
    open_alerts = db.scalar(
        select(func.count(IdentitySyncAlert.id)).where(IdentitySyncAlert.status == "open")
    ) or 0
    return {
        "total": int(total),
        "page": page,
        "page_size": page_size,
        "items": [serialize_run(row, subtask_map.get(row.run_id or "", [])) for row in rows],
        "overview": {
            "last_run": serialize_run(last_run, last_subtasks) if last_run else None,
            "open_alerts": int(open_alerts),
            "circuit_breakers": {
                "cdms": {
                    "name": "合理用药",
                    "is_open": bool(breakers["nightly_cdms"].is_open) if "nightly_cdms" in breakers else False,
                    "consecutive_failures": breakers["nightly_cdms"].consecutive_failures if "nightly_cdms" in breakers else 0,
                },
                "jhemr": {
                    "name": "嘉和电子病历",
                    "is_open": bool(breakers["nightly_jhemr"].is_open) if "nightly_jhemr" in breakers else False,
                    "consecutive_failures": breakers["nightly_jhemr"].consecutive_failures if "nightly_jhemr" in breakers else 0,
                },
            },
        },
    }


def get_sync_run(db: "Session", run_id: str) -> dict[str, Any] | None:
    from sqlalchemy import or_, select

    from ..models.identity_sync import (
        IdentitySchedulerRun,
        IdentitySyncAction,
        IdentitySyncAlert,
        IdentitySyncBatch,
        IdentitySyncSubtask,
    )

    row = db.scalar(select(IdentitySchedulerRun).where(IdentitySchedulerRun.run_id == run_id))
    if not row:
        return None
    subtasks = list(
        db.scalars(
            select(IdentitySyncSubtask)
            .where(IdentitySyncSubtask.run_id == run_id)
            .order_by(IdentitySyncSubtask.subtask_code)
        ).all()
    )
    batches = list(
        db.scalars(
            select(IdentitySyncBatch)
            .where(IdentitySyncBatch.scheduler_run_id == run_id)
            .order_by(IdentitySyncBatch.created_at.desc())
            .limit(50)
        ).all()
    )
    batch_ids = [item.batch_id for item in batches if item.batch_id]
    action_filters = [IdentitySyncAction.batch_id.like(f"%{run_id}%")]
    if batch_ids:
        action_filters.append(IdentitySyncAction.batch_id.in_(batch_ids))
    actions = list(
        db.scalars(
            select(IdentitySyncAction)
            .where(or_(*action_filters))
            .order_by(IdentitySyncAction.executed_at.desc().nullslast(), IdentitySyncAction.id.desc())
            .limit(200)
        ).all()
    )
    alerts = list(
        db.scalars(
            select(IdentitySyncAlert)
            .where(IdentitySyncAlert.run_id == run_id)
            .order_by(IdentitySyncAlert.created_at.desc())
            .limit(50)
        ).all()
    )
    data = serialize_run(row, subtasks)
    data["batches"] = [
        {
            "batch_id": item.batch_id,
            "batch_type": item.batch_type,
            "status": item.status,
            "status_name": status_label(item.status),
            "cdms_status": item.cdms_status,
            "cdms_status_name": status_label(item.cdms_status) if item.cdms_status else "-",
            "jhemr_status": item.jhemr_status,
            "jhemr_status_name": status_label(item.jhemr_status) if item.jhemr_status else "-",
            "person_classification": item.person_classification,
            "started_at": _iso(item.started_at),
            "finished_at": _iso(item.finished_at),
        }
        for item in batches
    ]
    data["actions"] = [serialize_action(item) for item in actions]
    _enrich_action_people(db, data["actions"])
    data["alerts"] = [
        {
            "alert_type": item.alert_type,
            "severity": item.severity,
            "status": item.status,
            "error_class": item.error_class,
            "occurrence_count": item.occurrence_count,
            "created_at": _iso(item.created_at),
        }
        for item in alerts
    ]
    return data
