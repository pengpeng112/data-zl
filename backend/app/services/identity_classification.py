"""HIS identity sync person classifier.

Pure logic module: classifies HIS staff (STAFF_DICT) into sync categories
based on JOB (primary) and TITLE (supplementary). No DB or model imports.

Value domains verified against the live HIS database on 2026-08-03
(COMM.STAFF_DICT, 4264 rows):
- JOB: 护理 816, 医生 734, 护士 718, 临床 538, NULL 262, 医技 238, 经济 237,
  行政管理 216, 技师 94, 药剂 84, 影像诊断 37, 检验 29, 急救 25, 润华药学 22,
  医疗 21, 医助 11, 中医临床 5, ...
- TITLE: 护士 1193, 主任医师 478, 医师 377, 副主任医师 231, 护师 188,
  主治医师 153, 技师 88, 技士 77, 药士 35, 药师 32, 主管护师 79,
  主管药师 28, 科主任 10, ...

Hard rules:
- Single-character keyword matching ("医"/"护"/"药") is FORBIDDEN: it would
  misclassify 医技/技师 (238+ technicians) as doctors.
- TITLE (professional qualification) takes precedence over JOB.
- Technician titles (技师/技士/...) are explicitly non-clinical and can never
  yield a clinical classification, even when JOB looks clinical (e.g. 影像诊断).
- 主任医师/主任药师 are clinical titles, NOT management. 科主任/护士长/管理员
  titles are management and are excluded per business policy.
- Outsourced staff (润华/外包/厂商/派遣/临时/颐邦/售后) are always excluded.
- Missing create_date is isolated as master_data_missing (plan 107 §15.5:
  records without master data or create_date must be isolated, never managed).

Group-class whitelist for additional departments (plan 107 §5.4 mapped to
live COMM.STAFF_GROUP_DICT.GROUP_CLASS values; the literal strings
"住院医师"/"病房护士" in plan 107 do NOT exist in the live database — the
corresponding live values are 病区医生/病区护士):
- doctor:     病区医生 only
- nurse:      病区护士 only
- pharmacist: no additional departments (primary dept only)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

RULE_VERSION = "v2"

DOCTOR = "doctor"
NURSE = "nurse"
PHARMACIST = "pharmacist"
EXCLUDED_OUTSOURCE = "excluded_outsource"
EXCLUDED_MANAGEMENT = "excluded_management"
CLASSIFICATION_CONFLICT = "classification_conflict"
STATUS_CONFLICT = "status_conflict"
LEGACY_UNMANAGED = "legacy_unmanaged"
MASTER_DATA_MISSING = "master_data_missing"
UNSUPPORTED = "unsupported"

LEGACY_CUTOFF = datetime(2026, 7, 20, tzinfo=timezone.utc)

# JOB values that imply a clinical category on their own (exact match).
_DOCTOR_JOBS = frozenset({"医生", "临床", "医疗", "中医临床"})
_NURSE_JOBS = frozenset({"护理", "护士"})
_PHARMACIST_JOBS = frozenset({"药剂", "药学"})
# JOB values that are clinical ONLY when the TITLE confirms it (mixed
# doctor/technician populations: 影像诊断 contains both 医师 and 技师).
_AMBIGUOUS_DOCTOR_JOBS = frozenset({"影像诊断", "急救"})

# TITLE professional qualification sets (exact match; live values).
_DOCTOR_TITLES = frozenset({
    "主任医师", "副主任医师", "主治医师", "医师", "医士", "助理医师", "住院医师",
})
_NURSE_TITLES = frozenset({
    "护士", "护师", "主管护师", "副主任护师", "主任护师", "助产士",
})
_PHARMACIST_TITLES = frozenset({
    "药师", "药士", "主管药师", "副主任药师", "主任药师",
})
# Explicitly non-clinical titles: block clinical classification from JOB.
_NON_CLINICAL_TITLES = frozenset({
    "技师", "技士", "主管技师", "副主任技师", "主任技师",
    "检验士", "检验师", "技术员", "护理员",
})
# Management titles excluded by business policy (103: 科主任/护士长/管理员
# 不自动处理). Note: 主任医师/主任药师 are clinical, handled above.
_MANAGEMENT_TITLES = frozenset({"科主任", "护士长", "管理员"})
_MANAGEMENT_JOBS = frozenset({"行政管理", "行政后勤", "院领导"})

_OUTSOURCE_KEYWORDS = ("润华", "外包", "厂商", "派遣", "临时", "颐邦", "售后")

# Additional-department group-class whitelist per classification (live values).
GROUP_CLASS_WHITELIST: dict[str, frozenset[str]] = {
    DOCTOR: frozenset({"病区医生"}),
    NURSE: frozenset({"病区护士"}),
    PHARMACIST: frozenset(),
}


@dataclass
class ClassificationResult:
    """Result of classifying a single HIS staff record."""

    classification: str
    matched_rule: str
    rule_version: str = RULE_VERSION
    conflict_detail: dict | None = field(default=None)


def _norm(value: str | None) -> str:
    return (value or "").strip()


def _has_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


def _title_category(title: str) -> set[str]:
    """Category implied by TITLE (professional qualification, exact match)."""
    if title in _DOCTOR_TITLES:
        return {DOCTOR}
    if title in _NURSE_TITLES:
        return {NURSE}
    if title in _PHARMACIST_TITLES:
        return {PHARMACIST}
    return set()


def _job_category(job: str) -> set[str]:
    """Category implied by JOB alone (only unambiguous values)."""
    if job in _DOCTOR_JOBS:
        return {DOCTOR}
    if job in _NURSE_JOBS:
        return {NURSE}
    if job in _PHARMACIST_JOBS:
        return {PHARMACIST}
    return set()


def is_valid_group_class(group_class: str | None, classification: str | None = None) -> bool:
    """Whether a HIS staff-group class may yield additional departments.

    Per plan 107 §5.4 (mapped to live GROUP_CLASS values): doctors only accept
    病区医生 groups, nurses only 病区护士 groups, pharmacists get no additional
    departments (primary dept only). Without a classification context, only
    the clinical ward classes are accepted.
    """
    value = _norm(group_class)
    if not value:
        return False
    if classification in GROUP_CLASS_WHITELIST:
        return value in GROUP_CLASS_WHITELIST[classification]
    return value in (GROUP_CLASS_WHITELIST[DOCTOR] | GROUP_CLASS_WHITELIST[NURSE])


def allowed_additional_group_classes(classification: str) -> frozenset[str]:
    """Group classes allowed to contribute additional departments."""
    return GROUP_CLASS_WHITELIST.get((classification or "").strip().lower(), frozenset())


def classify_person(
    job: str | None,
    title: str | None,
    status: str | None,
    validstate: str | None,
    create_date: datetime | None,
    group_classes: list[str] | None = None,
) -> ClassificationResult:
    """Classify one HIS staff record.

    Priority: status_conflict > master_data_missing > legacy_unmanaged >
    excluded_outsource > management title > clinical title >
    non-clinical title block > classification_conflict > job category >
    excluded_management > unsupported.
    """
    job_text = _norm(job)
    title_text = _norm(title)
    combined = job_text + title_text

    status_text = _norm(status)
    validstate_text = _norm(validstate)
    if status_text and validstate_text and status_text != validstate_text:
        return ClassificationResult(
            classification=STATUS_CONFLICT,
            matched_rule="status_mismatch",
            conflict_detail={"status": status_text, "validstate": validstate_text},
        )

    if create_date is None:
        return ClassificationResult(
            classification=MASTER_DATA_MISSING,
            matched_rule="create_date_missing",
            conflict_detail={"job": job_text, "title": title_text},
        )
    aware = create_date if create_date.tzinfo else create_date.replace(tzinfo=timezone.utc)
    if aware < LEGACY_CUTOFF:
        return ClassificationResult(
            classification=LEGACY_UNMANAGED,
            matched_rule="create_date_before_cutoff",
            conflict_detail={
                "create_date": create_date.isoformat(),
                "cutoff": LEGACY_CUTOFF.isoformat(),
            },
        )

    if _has_any(combined, _OUTSOURCE_KEYWORDS):
        return ClassificationResult(
            classification=EXCLUDED_OUTSOURCE,
            matched_rule="outsource_keyword",
            conflict_detail={"job": job_text, "title": title_text},
        )

    # Management titles are excluded even when JOB looks clinical
    # (business policy: 科主任/护士长/管理员 不自动处理).
    if title_text in _MANAGEMENT_TITLES:
        return ClassificationResult(
            classification=EXCLUDED_MANAGEMENT,
            matched_rule="management_title",
            conflict_detail={"job": job_text, "title": title_text},
        )

    # TITLE is the professional qualification and takes precedence.
    title_categories = _title_category(title_text)
    if len(title_categories) == 1:
        category = next(iter(title_categories))
        job_categories = _job_category(job_text)
        if job_categories and job_categories != title_categories:
            return ClassificationResult(
                classification=CLASSIFICATION_CONFLICT,
                matched_rule="job_title_cross_category",
                conflict_detail={
                    "job": job_text,
                    "title": title_text,
                    "job_categories": sorted(job_categories),
                    "title_categories": sorted(title_categories),
                },
            )
        return ClassificationResult(classification=category, matched_rule="title_match")

    # Non-clinical titles block any JOB-implied clinical category
    # (e.g. JOB=影像诊断 + TITLE=技师 is a technician, never a doctor).
    if title_text in _NON_CLINICAL_TITLES:
        return ClassificationResult(
            classification=UNSUPPORTED,
            matched_rule="non_clinical_title",
            conflict_detail={"job": job_text, "title": title_text},
        )

    # JOB-only evidence (TITLE empty or unrecognized).
    job_categories = _job_category(job_text)
    if len(job_categories) == 1:
        category = next(iter(job_categories))
        return ClassificationResult(classification=category, matched_rule="job_match")

    # Ambiguous clinical JOB without a confirming clinical TITLE: not synced.
    if job_text in _AMBIGUOUS_DOCTOR_JOBS:
        return ClassificationResult(
            classification=UNSUPPORTED,
            matched_rule="ambiguous_job_without_clinical_title",
            conflict_detail={"job": job_text, "title": title_text},
        )

    if job_text in _MANAGEMENT_JOBS:
        return ClassificationResult(
            classification=EXCLUDED_MANAGEMENT,
            matched_rule="management_keyword",
            conflict_detail={"job": job_text, "title": title_text},
        )

    return ClassificationResult(
        classification=UNSUPPORTED,
        matched_rule="no_rule_matched",
        conflict_detail={"job": job_text, "title": title_text},
    )


def classify_batch(rows: list[dict]) -> list[ClassificationResult]:
    """Classify a list of row dicts.

    Recognized keys: job, title, status, validstate, create_date,
    group_classes (all optional).
    """
    return [
        classify_person(
            job=row.get("job"),
            title=row.get("title"),
            status=row.get("status"),
            validstate=row.get("validstate"),
            create_date=row.get("create_date"),
            group_classes=row.get("group_classes"),
        )
        for row in rows
    ]
