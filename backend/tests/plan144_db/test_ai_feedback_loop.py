"""plan144 S7 DB tests: feedback loop + evaluation regression (A24/A25/A26)."""
from __future__ import annotations

import pytest

from app.models.ai_accuracy import AssetQueryEvaluationCase
from app.services.ai_feedback_service import (
    register_answer_event,
    review_feedback,
    submit_feedback,
)
from app.services.query_evaluation_service import (
    accuracy_dashboard,
    evaluate_assertions,
    evaluation_gate_pass,
    run_evaluation,
)


@pytest.fixture()
def answer_event(db_session):
    result = register_answer_event(
        db_session,
        question_summary="2026年7月住院次均费用是多少",
        caller_id="ai-dify-main",
        query_code="QRY_X",
        query_version=1,
        run_id=123,
        result_digest="a" * 64,
        answer_text="约为 8500 元（示例）",
    )
    db_session.commit()
    return result["answer_event_id"]


def test_feedback_binds_event_and_fixed_taxonomy(db_session, answer_event):
    ok = submit_feedback(
        db_session, answer_event_id=answer_event, rating="incorrect",
        error_types=["denominator", "time_semantics"], comment="分母口径未排除当月未结算",
        submitted_by="reviewer-a",
    )
    assert ok["status"] == "submitted"
    with pytest.raises(ValueError):
        submit_feedback(db_session, answer_event_id=answer_event, rating="great")  # invalid rating
    with pytest.raises(ValueError):
        submit_feedback(db_session, answer_event_id=answer_event, rating="correct", error_types=["not_a_type"])


def test_feedback_state_machine_no_autopublish(db_session, answer_event):
    fb = submit_feedback(db_session, answer_event_id=answer_event, rating="incorrect", error_types=["formula"])
    # invalid jump submitted → resolved
    with pytest.raises(ValueError):
        review_feedback(db_session, feedback_id=fb["feedback_id"], action="resolved")
    review_feedback(db_session, feedback_id=fb["feedback_id"], action="triaged", reviewed_by="r")
    review_feedback(db_session, feedback_id=fb["feedback_id"], action="accepted", reviewed_by="r")
    review_feedback(
        db_session, feedback_id=fb["feedback_id"], action="revision_draft",
        reviewed_by="r", revision_query_code="QRY_X", revision_query_version=2,
    )
    review_feedback(db_session, feedback_id=fb["feedback_id"], action="evaluation_running", reviewed_by="r")
    final = review_feedback(db_session, feedback_id=fb["feedback_id"], action="resolved", reviewed_by="r")
    assert final["status"] == "resolved"


def test_answer_event_stores_digests_not_full_text(db_session):
    result = register_answer_event(
        db_session, question_summary="敏感问题：患者张三的诊断",
        answer_text="张三患有 X 病（不应保存原文）",
    )
    from app.models.ai_accuracy import AssetAiAnswerEvent

    row = db_session.get(AssetAiAnswerEvent, result["answer_event_id"])
    assert row.question_summary == "敏感问题：患者张三的诊断"  # summary allowed
    assert row.answer_digest and len(row.answer_digest) == 64
    assert "不应保存原文" not in (row.answer_summary or "")


def _case(db_session, code, assertions, params=None, enabled=True):
    row = AssetQueryEvaluationCase(
        case_code=code, title=code, asset_type="query", query_code="QRY_EVAL_T",
        query_version=None, parameters=params or {}, assertions=assertions,
        evaluation_set_version="eval-set-v1", enabled=enabled,
    )
    db_session.add(row)
    db_session.flush()
    return row


def test_assertion_engine_aggregate_only():
    outcome_ok = {"status": "success", "row_count": 5, "truncated": False, "result_digest": "d" * 64, "sample": [{"CNT": 3}]}
    results = evaluate_assertions(
        [
            {"kind": "status_success"},
            {"kind": "not_truncated"},
            {"kind": "row_count_min", "value": 1},
            {"kind": "numeric_tolerance", "column": "CNT", "expected": 3, "tolerance": 0.001},
            {"kind": "digest_stable"},
        ],
        outcome_ok,
    )
    assert all(r["passed"] for r in results)
    bad = evaluate_assertions([{"kind": "status_success"}], {"status": "failed"})
    assert not bad[0]["passed"]
    unknown = evaluate_assertions([{"kind": "patient_match"}], outcome_ok)
    assert unknown[0]["passed"] is False


def test_run_evaluation_pass_fail_and_gate(db_session):
    calls = []

    def fake_runner(code, version, params):
        calls.append((code, version, params))
        if params.get("fail"):
            return {"status": "failed", "error_class": "E_SOURCE"}
        return {"status": "success", "row_count": 2, "truncated": False,
                "result_digest": "e" * 64, "sample": [{"CNT": 2}]}

    c1 = _case(db_session, "GC-T-001", [{"kind": "status_success"}, {"kind": "row_count_min", "value": 1}])
    c2 = _case(db_session, "GC-T-002", [{"kind": "status_success"}], params={"fail": True})

    summary = run_evaluation(db_session, query_code="QRY_EVAL_T", triggered_by="t", runner=fake_runner)
    assert summary["total"] == 2
    assert summary["passed"] == 1 and summary["failed"] == 0 and summary["errors"] == 1
    assert evaluation_gate_pass(summary) is False  # errors block the gate (A25)

    # make case 2 pass → gate opens
    c2.parameters = {}
    db_session.flush()
    summary2 = run_evaluation(db_session, query_code="QRY_EVAL_T", triggered_by="t", runner=fake_runner)
    assert summary2["passed"] == 2 and summary2["errors"] == 0
    assert evaluation_gate_pass(summary2) is True


def test_dashboard_counts_only_audited_and_golden(db_session, answer_event):
    # unaudited feedback must NOT enter accuracy stats
    submit_feedback(db_session, answer_event_id=answer_event, rating="correct")
    dash = accuracy_dashboard(db_session)
    assert dash["audited_feedback_total"] == 0
    assert dash["unevaluated_feedback"] == 1
    assert dash["notes"]
