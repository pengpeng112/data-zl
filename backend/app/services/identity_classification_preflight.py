"""Classification preflight for identity nightly sync (plan 107 §15.1/§15.5).

Runs on the PLATFORM database only (no business-DB access): reads
IdentityPerson + IdentityPersonSource rows collected by his_identity_sync,
classifies each person with the value-domain classifier, persists the result
to asset_identity_classifications, and updates IdentityPerson fields
(classification / classification_rule_version / conflict_flag).

Without this stage, IdentityPerson.classification would stay NULL forever and
the nightly candidate selection would always be empty.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.identity import IdentityPerson, IdentityPersonSource
from ..models.identity_sync import IdentityClassificationRecord
from .identity_classification import (
    CLASSIFICATION_CONFLICT,
    MASTER_DATA_MISSING,
    STATUS_CONFLICT,
    classify_person,
)

logger = logging.getLogger(__name__)


def _mask_emp_no(emp_no: str) -> str:
    if not emp_no:
        return "***"
    if len(emp_no) <= 4:
        return "*" * len(emp_no)
    return emp_no[:2] + "*" * (len(emp_no) - 4) + emp_no[-2:]

STAFF_TABLE = "COMM.STAFF_DICT"
EMPLOYEE_TABLE = "FXHIS.SYS_EMPLOYEE"

# Classifications that isolate a person from any automatic management.
_CONFLICT_CLASSIFICATIONS = {CLASSIFICATION_CONFLICT, STATUS_CONFLICT, MASTER_DATA_MISSING}


def _parse_create_date(raw: Any):
    from datetime import datetime

    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw
    text = str(raw).strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[:19], fmt)
        except ValueError:
            continue
    return None


def _status_flag(value: Any) -> str:
    """Normalize a stored source status to the classifier's raw '1'/'0' flags.

    person_sources.source_status is stored normalized ("active"/"inactive"/
    "unknown") by the collectors; the classifier compares raw HIS flags.
    """
    text = str(value or "").strip().lower()
    if text in {"1", "active"}:
        return "1"
    if text in {"0", "inactive"}:
        return "0"
    return ""


def run_classification_preflight(db: Session) -> dict[str, Any]:
    """Classify every known person and persist results. Returns stats."""
    persons = db.scalars(select(IdentityPerson)).all()
    stats = {"total": 0, "classified": 0, "conflicts": 0, "no_source": 0, "by_classification": {}}

    for person in persons:
        stats["total"] += 1
        emp_no = person.person_code

        staff_src = db.scalar(
            select(IdentityPersonSource).where(
                IdentityPersonSource.person_code == emp_no,
                IdentityPersonSource.source_table == STAFF_TABLE,
            )
        )
        employee_src = db.scalar(
            select(IdentityPersonSource).where(
                IdentityPersonSource.person_code == emp_no,
                IdentityPersonSource.source_table == EMPLOYEE_TABLE,
            )
        )

        # 无任何来源证据的人员无法分类：保留既有状态（生产上不存在此情形，
        # 所有人均来自 HIS 采集；仅人工登记/测试数据命中此分支）。
        if staff_src is None and employee_src is None:
            stats["no_source"] += 1
            continue

        staff_raw = staff_src.raw_data if staff_src and isinstance(staff_src.raw_data, dict) else {}
        job = person.raw_job or staff_raw.get("JOB")
        title = person.raw_title or staff_raw.get("TITLE")
        create_date = person.source_create_date or _parse_create_date(staff_raw.get("CREATE_DATE"))

        result = classify_person(
            job=job,
            title=title,
            status=_status_flag(staff_src.source_status if staff_src else None),
            validstate=_status_flag(employee_src.source_status if employee_src else None),
            create_date=create_date,
        )

        person.raw_job = (str(job).strip() if job else None) or person.raw_job
        person.raw_title = (str(title).strip() if title else None) or person.raw_title
        if create_date is not None and person.source_create_date is None:
            person.source_create_date = create_date
        person.classification = result.classification
        person.classification_rule_version = result.rule_version
        person.conflict_flag = result.classification if result.classification in _CONFLICT_CLASSIFICATIONS else None

        record = db.scalar(
            select(IdentityClassificationRecord).where(
                IdentityClassificationRecord.emp_no == emp_no,
                IdentityClassificationRecord.rule_version == result.rule_version,
            )
        )
        if record is None:
            record = IdentityClassificationRecord(emp_no=emp_no, rule_version=result.rule_version)
            db.add(record)
        record.emp_no_masked = _mask_emp_no(emp_no)
        record.raw_job = person.raw_job
        record.raw_title = person.raw_title
        record.classification = result.classification
        record.matched_rule = result.matched_rule
        record.conflict_detail = result.conflict_detail
        record.source_create_date = person.source_create_date

        stats["classified"] += 1
        if result.classification in _CONFLICT_CLASSIFICATIONS:
            stats["conflicts"] += 1
        bucket = stats["by_classification"]
        bucket[result.classification] = bucket.get(result.classification, 0) + 1

    db.flush()
    logger.info(
        "classification preflight: total=%d classified=%d conflicts=%d",
        stats["total"], stats["classified"], stats["conflicts"],
    )
    return stats
