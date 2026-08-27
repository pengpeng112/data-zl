"""Seed plan144 golden evaluation cases (>=30, idempotent upsert).

Cases use ONLY synthetic parameters and aggregate assertions (status /
row-count bounds / truncation / digest presence) — no patient-level baselines
(144 §12). Query codes are taken from the platform's current active queries;
missing assets are skipped honestly (never fabricated).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.ai_accuracy import AssetQueryEvaluationCase
from app.models.metric_asset import AssetMetricVersion
from app.models.query_asset import AssetQueryDefinition, AssetQueryVersion

EVAL_SET = "eval-set-v1"


def _assertions_query_basic() -> list[dict]:
    return [
        {"kind": "status_success"},
        {"kind": "not_truncated"},
        {"kind": "row_count_min", "value": 0},
        {"kind": "digest_stable"},
    ]


def _assertions_metric_basic() -> list[dict]:
    return [
        {"kind": "status_success"},
        {"kind": "digest_stable"},
    ]


def build_cases(db) -> list[dict]:
    """One case per active query + one per active metric with query ref."""
    cases: list[dict] = []
    q_defs = {d.query_code: d for d in db.scalars(select(AssetQueryDefinition)).all()}
    q_versions = db.scalars(
        select(AssetQueryVersion).where(AssetQueryVersion.is_active.is_(True))
    ).all()
    for i, qv in enumerate(sorted(q_versions, key=lambda v: v.query_code), start=1):
        d = q_defs.get(qv.query_code)
        cases.append(
            {
                "case_code": f"GC-Q-{i:03d}",
                "title": f"现行查询回放：{qv.query_code}",
                "description": "聚合断言：成功、无截断、非负行数、digest 存在（合成用例，无患者基线）",
                "system_code": (d.system_code if d else None) or "UNKNOWN",
                "business_domain": (d.business_domain if d else None),
                "asset_type": "query",
                "query_code": qv.query_code,
                "query_version": None,  # follow current active
                "parameters": {},
                "assertions": _assertions_query_basic(),
                "evidence": "plan144 S7 golden seed v1",
            }
        )
    m_versions = db.scalars(
        select(AssetMetricVersion).where(AssetMetricVersion.is_active.is_(True))
    ).all()
    for j, mv in enumerate(sorted(m_versions, key=lambda v: v.metric_code), start=1):
        if not (mv.query_code or mv.numerator_query_code or mv.denominator_query_code):
            continue
        cases.append(
            {
                "case_code": f"GC-M-{j:03d}",
                "title": f"指标计算回放：{mv.metric_code}",
                "description": "聚合断言：计算成功且结果 digest 可复现",
                "system_code": mv.system_code or "UNKNOWN",
                "business_domain": None,
                "asset_type": "metric",
                "query_code": mv.query_code or mv.numerator_query_code,
                "query_version": None,
                "parameters": {},
                "assertions": _assertions_metric_basic(),
                "evidence": "plan144 S7 golden seed v1",
            }
        )
    return cases


def run(apply: bool = False) -> None:
    db = SessionLocal()
    try:
        cases = build_cases(db)
        existing = {
            c.case_code: c
            for c in db.scalars(select(AssetQueryEvaluationCase)).all()
        }
        created = updated = 0
        for case in cases:
            row = existing.get(case["case_code"])
            if row is None:
                row = AssetQueryEvaluationCase(
                    case_code=case["case_code"], title=case["title"],
                    evaluation_set_version=EVAL_SET,
                )
                db.add(row)
                created += 1
            else:
                updated += 1
            for key in ("title", "description", "system_code", "business_domain",
                        "asset_type", "query_code", "query_version", "parameters",
                        "assertions", "evidence"):
                setattr(row, key, case[key])
            row.evaluation_set_version = EVAL_SET
            row.enabled = True
        if apply:
            db.commit()
            total = db.scalars(select(AssetQueryEvaluationCase)).all()
            print(f"seed_ok total={len(total)} created={created} updated={updated} (>=30: {len(total) >= 30})")
        else:
            db.rollback()
            print(f"dry_run total_would_be={len(cases)} created={created} updated={updated} (>=30: {len(cases) >= 30})")
    finally:
        db.close()


if __name__ == "__main__":
    run(apply="--apply" in sys.argv)
