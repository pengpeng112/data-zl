"""Apply the reviewed Plan 137 conflict classification to platform governance.

Dry-run is the default.  The script only updates platform review/evidence rows;
it never connects to HIS and never changes formal relation endpoints or keys.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


for _candidate in (Path(__file__).resolve().parents[1], Path.cwd()):
    if (_candidate / "app").is_dir() and str(_candidate) not in sys.path:
        sys.path.insert(0, str(_candidate))


CONFIRM_TEXT = "APPLY_PLAN137_CONFLICT_RESOLUTION"
BATCH_TAG = "plan136_his_view_relations_v1"
MARKER = "plan137_conflict_resolution_v1"
REVIEWER = "codex_plan137_user_authorized"


def columns(value: Any) -> tuple[str, ...]:
    if isinstance(value, (list, tuple)):
        parts = value
    else:
        text = str(value or "").replace("+", ",").replace("|", ",").replace(";", ",")
        parts = text.split(",")
    return tuple(str(part).strip().upper() for part in parts if str(part).strip())


def identity(
    from_table: Any,
    from_columns: Any,
    to_table: Any,
    to_columns: Any,
) -> tuple[str, tuple[str, ...], str, tuple[str, ...]]:
    return (
        str(from_table or "").strip().upper(),
        columns(from_columns),
        str(to_table or "").strip().upper(),
        columns(to_columns),
    )


FORMAL_SPECS: dict[str, tuple[str, tuple[str, ...], str, tuple[str, ...]]] = {
    "R005": identity("INPADM.ADT_LOG", "PATIENT_ID,VISIT_ID", "MEDREC.PAT_VISIT", "PATIENT_ID,VISIT_ID"),
    "R006": identity("ORDADM.ORDERS", "PATIENT_ID,VISIT_ID", "MEDREC.PAT_VISIT", "PATIENT_ID,VISIT_ID"),
    "R011": identity("LAB.LAB_TEST_MASTER", "PATIENT_ID,VISIT_ID", "MEDREC.PAT_VISIT", "PATIENT_ID,VISIT_ID"),
    "R016": identity("EXAM.EXAM_MASTER", "PATIENT_ID,VISIT_ID", "MEDREC.PAT_VISIT", "PATIENT_ID,VISIT_ID"),
    "R031": identity(
        "DRUG_USER.PHA_INP_REQUEST_DRUG",
        "PAT_ID,IN_COUNT,MO_ORDER,ORDER_SUB_NO",
        "ORDADM.ORDERS",
        "PATIENT_ID,VISIT_ID,ORDER_NO,ORDER_SUB_NO",
    ),
}

REVIEW_SPECS: dict[tuple[str, tuple[str, ...], str, tuple[str, ...]], tuple[str, str]] = {
    identity(
        "ORDADM.ORDERS",
        "ORDER_NO,ORDER_SUB_NO",
        "DRUG_USER.PHA_INP_REQUEST_DRUG",
        "MO_ORDER,ORDER_SUB_NO",
    ): ("R031", "四键 JOIN 被拆出的医嘱号二键片段，不得作为独立正式关系"),
    identity(
        "DRUG_USER.PHA_INP_REQUEST_DRUG",
        "PAT_ID,IN_COUNT",
        "ORDADM.ORDERS",
        "PATIENT_ID,VISIT_ID",
    ): ("R031", "四键 JOIN 被拆出的患者就诊二键片段，不得作为独立正式关系"),
    identity("INPADM.ADT_LOG", "DEPT_CODE", "MEDREC.PAT_VISIT", "DEPT_DISCHARGE_FROM"): (
        "R005",
        "科室 CASE 条件属于 ADT 事件选择配方，不是独立关系键",
    ),
    identity("MEDREC.PAT_VISIT", "DISCHARGE_DATE_TIME", "INPADM.ADT_LOG", "LOG_DATE_TIME"): (
        "R005",
        "出院时间与日志时间比较属于 ADT 事件选择配方，不是独立关系键",
    ),
    identity(
        "INPADM.ADT_LOG",
        "PATIENT_ID,VISIT_ID,ACTION",
        "MEDREC.PAT_VISIT",
        "PATIENT_ID,VISIT_ID,DEPT_DISCHARGE_FROM",
    ): ("R005", "ACTION/科室条件属于 ADT 事件选择配方，不扩展正式住院键"),
}

FORMAL_NOTES = {
    "R005": "137静态复核：正式住院键保持 PATIENT_ID+VISIT_ID；ACTION、科室 CASE 和事件时间逻辑归配方。",
    "R006": "137静态复核：V_INP_ANTI_ITEMS 的两条记录是 UNION 分支下的医嘱子集证据，不改变正式住院键。",
    "R011": "137静态复核：APP_NO=TEST_NO 是 PAT_VISIT→ORDERS→LAB 三表配方；正式关系继续限非零 VISIT_ID 住院子集。",
    "R016": "137静态复核：APP_NO=EXAM_NO 是 PAT_VISIT→ORDERS→EXAM 三表配方；正式关系继续限非零 VISIT_ID 住院子集。",
    "R031": "137静态复核：8条视图记录合并后均为既有四键映射；拆出的两个二键候选已关闭。",
}

RECIPE_GROUPS = {
    "DRUG_USER.V_INP_ANTI_EXECNUM": ["R031"],
    "DRUG_USER.V_INP_ANTI_ITEMS": ["R006", "R011", "R016"],
}


def append_marker(note: str | None, detail: str) -> tuple[str, bool]:
    current = str(note or "").strip()
    if f"[{MARKER}]" in current:
        return current, False
    line = f"[{MARKER}] {detail}"
    return f"{current}\n{line}".strip(), True


def merge_json(value: Mapping[str, Any] | None, payload: Mapping[str, Any]) -> tuple[dict[str, Any], bool]:
    result = dict(value or {})
    if result.get(MARKER) == payload:
        return result, False
    result[MARKER] = dict(payload)
    return result, True


def execute(*, apply: bool, confirm: str) -> dict[str, Any]:
    if apply and confirm != CONFIRM_TEXT:
        raise RuntimeError(f"apply requires --confirm {CONFIRM_TEXT}")

    from sqlalchemy import func, select

    from app.core.db import SessionLocal
    from app.models.asset import AssetRelation, AssetRelationReview
    from app.models.recipe import AssetRelationRecipe

    summary: dict[str, Any] = {
        "mode": "apply" if apply else "dry_run",
        "batch": BATCH_TAG,
        "formal_relations_expected": len(FORMAL_SPECS),
        "formal_relations_found": 0,
        "formal_evidence_notes_updated": 0,
        "formal_relation_semantics_modified": 0,
        "target_reviews_expected": len(REVIEW_SPECS),
        "target_reviews_found": 0,
        "reviews_rejected": 0,
        "recipes_expected": len(RECIPE_GROUPS),
        "recipes_found": 0,
        "recipes_annotated": 0,
        "recipes_activated": 0,
        "source_writes": 0,
        "platform_writes": 0,
        "review_statuses_before": {},
        "review_statuses_after": {},
        "unmatched_formal": [],
        "unmatched_reviews": [],
        "unmatched_recipes": [],
    }
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        relations = db.scalars(
            select(AssetRelation).where(AssetRelation.relation_layer == "formal")
        ).all()
        formal_by_code: dict[str, AssetRelation] = {}
        for code, expected in FORMAL_SPECS.items():
            matches = [
                row
                for row in relations
                if identity(row.from_table, row.from_columns, row.to_table, row.to_columns) == expected
            ]
            if not matches:
                summary["unmatched_formal"].append(code)
                continue
            evidence_matches = [
                row
                for row in matches
                if f"evidence {code}" in str(row.validation_note or row.note or "")
            ]
            selected = sorted(evidence_matches or matches, key=lambda row: row.id)[0]
            formal_by_code[code] = selected
            summary["formal_relations_found"] += 1
            updated_note, changed = append_marker(selected.validation_note, FORMAL_NOTES[code])
            if changed:
                summary["formal_evidence_notes_updated"] += 1
                if apply:
                    selected.validation_note = updated_note
                    selected.updated_at = now
                    summary["platform_writes"] += 1

        batch_reviews = db.scalars(
            select(AssetRelationReview).where(AssetRelationReview.review_note.contains(BATCH_TAG))
        ).all()
        status_before: dict[str, int] = {}
        for row in batch_reviews:
            status_before[str(row.review_status or "unknown")] = status_before.get(str(row.review_status or "unknown"), 0) + 1
        summary["review_statuses_before"] = status_before

        found_review_specs: set[tuple[str, tuple[str, ...], str, tuple[str, ...]]] = set()
        for row in batch_reviews:
            key = identity(row.from_table, row.from_columns, row.to_table, row.to_columns)
            resolution = REVIEW_SPECS.get(key)
            if resolution is None:
                continue
            found_review_specs.add(key)
            summary["target_reviews_found"] += 1
            code, reason = resolution
            formal = formal_by_code.get(code)
            if formal is None:
                continue
            note, note_changed = append_marker(row.review_note, f"{code}：{reason}；按用户授权关闭独立候选，保留为视图/配方证据。")
            needs_change = (
                row.review_status != "rejected"
                or row.source_relation_id != formal.id
                or row.source_relation_table != "asset_relations"
                or note_changed
            )
            if needs_change:
                summary["reviews_rejected"] += 1
                if apply:
                    row.review_status = "rejected"
                    row.reviewer = REVIEWER
                    row.reviewed_at = now
                    row.source_relation_table = "asset_relations"
                    row.source_relation_id = formal.id
                    row.validation_status = "manual_static_review_reclassified"
                    row.review_note = note
                    row.updated_at = now
                    summary["platform_writes"] += 1
        summary["unmatched_reviews"] = [
            "|".join((spec[0], ",".join(spec[1]), spec[2], ",".join(spec[3])))
            for spec in REVIEW_SPECS
            if spec not in found_review_specs
        ]

        recipes = db.scalars(
            select(AssetRelationRecipe).where(AssetRelationRecipe.imported_from == BATCH_TAG)
        ).all()
        recipe_by_view = {str(row.recommended_view_name or "").upper(): row for row in recipes}
        for view, groups in RECIPE_GROUPS.items():
            row = recipe_by_view.get(view)
            if row is None:
                summary["unmatched_recipes"].append(view)
                continue
            summary["recipes_found"] += 1
            risk_payload = {
                "status": "conflict_edges_resolved",
                "formal_relation_groups": groups,
                "full_recipe_runtime_status": "runtime_skipped",
                "full_recipe_activation": "kept_inactive_pending_full_recipe_validation",
                "formal_relation_semantics_modified": 0,
            }
            evidence_payload = {
                "report": "137_三系统探查与HIS视图关系治理执行报告.md#4",
                "reviewer": REVIEWER,
                "review_scope": "conflict_edges_only",
                "formal_relation_groups": groups,
            }
            risk, risk_changed = merge_json(row.risk_summary, risk_payload)
            evidence, evidence_changed = merge_json(row.evidence_summary, evidence_payload)
            if risk_changed or evidence_changed:
                summary["recipes_annotated"] += 1
                if apply:
                    row.risk_summary = risk
                    row.evidence_summary = evidence
                    row.updated_by = REVIEWER
                    row.updated_at = now
                    summary["platform_writes"] += 1

        if summary["unmatched_formal"] or summary["unmatched_reviews"] or summary["unmatched_recipes"]:
            db.rollback()
            summary["status"] = "blocked_target_mismatch"
            summary["platform_writes"] = 0
            return summary

        status_after = dict(status_before)
        if apply:
            db.flush()
            status_after = {
                str(status or "unknown"): int(count)
                for status, count in db.execute(
                    select(AssetRelationReview.review_status, func.count(AssetRelationReview.id))
                    .where(AssetRelationReview.review_note.contains(BATCH_TAG))
                    .group_by(AssetRelationReview.review_status)
                ).all()
            }
            db.commit()
        else:
            status_after["draft"] = max(0, status_after.get("draft", 0) - summary["reviews_rejected"])
            status_after["rejected"] = status_after.get("rejected", 0) + summary["reviews_rejected"]
            status_after = {key: value for key, value in status_after.items() if value}
            db.rollback()
        summary["review_statuses_after"] = status_after
        summary["status"] = "ok"
    return summary


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm", default="")
    args = parser.parse_args(argv)
    try:
        result = execute(apply=args.apply, confirm=args.confirm)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0 if result.get("status") == "ok" else 2
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "error",
                    "error_type": type(exc).__name__,
                    "sqlstate": getattr(getattr(exc, "orig", None), "sqlstate", None),
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
