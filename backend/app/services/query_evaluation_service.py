"""144 S7: golden-case evaluation engine + regression replay (A25/A26).

Cases carry aggregate assertions only (row_count/status/numeric tolerance/
digest stability) — never patient-level baselines (144 §12).
"""
from __future__ import annotations

import decimal
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.ai_accuracy import AssetQueryEvaluationCase, AssetQueryEvaluationRun


def _now():
    return datetime.now(timezone.utc)


def evaluate_assertions(assertions: list[dict], outcome: dict) -> list[dict]:
    """Evaluate aggregate assertions against one run outcome dict.

    outcome: {"status","row_count","truncated","result_digest","sample":[...]}
    Returns per-assertion results; overall pass = all pass.
    """
    results = []
    for a in assertions or []:
        kind = a.get("kind")
        if kind == "status_success":
            results.append({"kind": kind, "passed": outcome.get("status") == "success"})
        elif kind == "row_count_min":
            results.append(
                {"kind": kind, "passed": (outcome.get("row_count") or 0) >= int(a.get("value", 0))}
            )
        elif kind == "row_count_max":
            results.append(
                {"kind": kind, "passed": (outcome.get("row_count") or 0) <= int(a.get("value", 0))}
            )
        elif kind == "not_truncated":
            results.append({"kind": kind, "passed": outcome.get("truncated") is False})
        elif kind == "numeric_tolerance":
            column = a.get("column")
            expected = decimal.Decimal(str(a.get("expected")))
            tolerance = decimal.Decimal(str(a.get("tolerance", 0)))
            sample = (outcome.get("sample") or [{}])[0] if outcome.get("sample") else {}
            actual = sample.get(column) if column in sample else next(
                (v for k, v in sorted(sample.items()) if isinstance(v, (int, float))), None
            )
            passed = actual is not None and abs(decimal.Decimal(str(actual)) - expected) <= tolerance
            results.append({"kind": kind, "column": column, "passed": bool(passed)})
        elif kind == "digest_stable":
            results.append(
                {"kind": kind, "passed": bool(outcome.get("result_digest"))}
            )
        else:
            results.append({"kind": str(kind), "passed": False, "error": "unknown_assertion"})
    return results


def run_case(
    db: Session,
    case: AssetQueryEvaluationCase,
    *,
    query_version_override: int | None = None,
    triggered_by: str | None = None,
    runner=None,
) -> AssetQueryEvaluationRun:
    """Replay one case. runner is injectable for isolated tests; defaults to
    the real read-only query runner."""
    if runner is None:
        from .query_runner import run_query_version as runner_fn

        def runner(code, version, params):
            return runner_fn(
                db, query_code=code, version=version, parameters=params,
                triggered_by=triggered_by or "evaluation",
            )

        runner = runner
    version = query_version_override or case.query_version
    run_row = AssetQueryEvaluationRun(
        case_id=case.id,
        case_code=case.case_code,
        evaluation_set_version=case.evaluation_set_version,
        query_code=case.query_code,
        query_version=version or 0,
        parameters=case.parameters or {},
        status="error",
        passed=False,
        triggered_by=triggered_by,
    )
    db.add(run_row)
    db.flush()
    try:
        outcome = runner(case.query_code, version, case.parameters or {})
        if isinstance(outcome, dict) and outcome.get("status") == "success":
            assertion_results = evaluate_assertions(case.assertions or [], outcome)
            passed = all(r.get("passed") for r in assertion_results)
            run_row.status = "pass" if passed else "fail"
            run_row.passed = passed
            run_row.assertion_results = assertion_results
            run_row.result_digest = outcome.get("result_digest")
            run_row.actual_summary = {
                "row_count": outcome.get("row_count"),
                "truncated": outcome.get("truncated"),
                "data_as_of": outcome.get("data_as_of"),
            }
        else:
            run_row.status = "error"
            run_row.passed = False
            run_row.error_code = (outcome or {}).get("error_class") if isinstance(outcome, dict) else "runner_error"
            run_row.assertion_results = []
    except Exception as exc:
        run_row.status = "error"
        run_row.passed = False
        run_row.error_code = type(exc).__name__
    finally:
        run_row.finished_at = _now()
    db.flush()
    return run_row


def run_evaluation(
    db: Session,
    *,
    query_code: str | None = None,
    query_version: int | None = None,
    evaluation_set_version: str | None = None,
    triggered_by: str | None = None,
    runner=None,
) -> dict[str, Any]:
    """Replay all enabled affected cases for a target (or a full set)."""
    stmt = select(AssetQueryEvaluationCase).where(AssetQueryEvaluationCase.enabled.is_(True))
    if query_code:
        stmt = stmt.where(AssetQueryEvaluationCase.query_code == query_code)
    if evaluation_set_version:
        stmt = stmt.where(
            AssetQueryEvaluationCase.evaluation_set_version == evaluation_set_version
        )
    cases = db.scalars(stmt.order_by(AssetQueryEvaluationCase.case_code)).all()
    if not cases:
        return {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "errors": 0,
            "cases": [],
            "note": "无受影响用例（新查询首次激活允许，但 G5 门禁建议先补用例）",
        }
    runs = [
        run_case(db, case, query_version_override=query_version, triggered_by=triggered_by, runner=runner)
        for case in cases
    ]
    passed = sum(1 for r in runs if r.status == "pass")
    failed = sum(1 for r in runs if r.status == "fail")
    errors = sum(1 for r in runs if r.status == "error")
    return {
        "total": len(runs),
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "evaluation_set_version": cases[0].evaluation_set_version,
        "cases": [
            {"case_code": r.case_code, "status": r.status, "run_id": r.id}
            for r in runs
        ],
    }


def evaluation_gate_pass(summary: dict) -> bool:
    """G5: candidate cannot certify when any affected golden case fails."""
    return bool(summary.get("total")) and summary.get("failed", 0) == 0 and summary.get("errors", 0) == 0


def accuracy_dashboard(db: Session) -> dict[str, Any]:
    """Only audited feedback + golden cases count — no 'all calls' denominators (A26)."""
    from ..models.ai_accuracy import AssetAiFeedback

    feedbacks = db.scalars(select(AssetAiFeedback)).all()
    audited = [f for f in feedbacks if f.status in {"resolved", "regression_failed", "accepted", "revision_draft"}]
    rating_counts: dict[str, int] = {}
    for f in audited:
        rating_counts[f.rating] = rating_counts.get(f.rating, 0) + 1
    error_counts: dict[str, int] = {}
    for f in audited:
        for et in f.error_types or []:
            error_counts[et] = error_counts.get(et, 0) + 1

    runs = db.scalars(
        select(AssetQueryEvaluationRun).order_by(AssetQueryEvaluationRun.id.desc()).limit(1000)
    ).all()
    golden_pass = sum(1 for r in runs if r.status == "pass")
    golden_fail = sum(1 for r in runs if r.status == "fail")
    golden_error = sum(1 for r in runs if r.status == "error")

    window = f"latest_{len(runs)}_runs"
    return {
        "schema_version": "accuracy-dashboard/v1",
        "audited_feedback_total": len(audited),
        "feedback_rating_distribution": rating_counts,
        "error_type_trend": error_counts,
        "golden_case_runs_window": window,
        "golden_pass": golden_pass,
        "golden_fail": golden_fail,
        "golden_error": golden_error,
        "golden_pass_rate": (golden_pass / (golden_pass + golden_fail)) if (golden_pass + golden_fail) else None,
        "unevaluated_feedback": sum(1 for f in feedbacks if f.status in {"submitted", "triaged"}),
        "notes": "准确率只统计已审核反馈与黄金用例；未评价回答不计为正确",
    }
