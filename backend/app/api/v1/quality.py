from collections import Counter
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ...core.db import get_db
from ...core.security import require_permission
from ...models.quality import QualityRule, QualityFinding, QualityCheckRun
from ...models.asset import AssetRelation, AssetTable, AssetColumn
from ...models.candidate import AssetCandidateRelation
from ...schemas.common import ApiResponse
from ...schemas.quality import (
    QualityRuleItem,
    QualityFindingItem,
    QualityCheckRunItem,
    QualitySummary,
    FindingUpdateRequest,
)
from ...services.quality_rule_engine import validate_sql_safety
from ...services.quality_sql_runner import execute_quality_sql
from ...services.data_masking import mask_sensitive

router = APIRouter(prefix="/api/v1/quality", tags=["quality"])


QUALITY_RULES_SEED = [
    {
        "rule_code": "REL_ORPHAN_RATE",
        "rule_name": "关系孤儿率超标",
        "rule_type": "orphan",
        "rule_category": "RELATION",
        "check_scope": "TABLE_RELATION",
        "target_type": "relation",
        "execution_mode": "metadata_only",
        "description": "正式关系孤儿率超标（基于 validation_metrics 中已存储的 orphan_rate）",
        "threshold_config": {"max_orphan_rate": 0.05},
        "enabled": True,
    },
    {
        "rule_code": "TABLE_NO_DOMAIN",
        "rule_name": "表业务域缺失",
        "rule_type": "completeness",
        "rule_category": "COMPLETE",
        "check_scope": "TABLE_INNER",
        "target_type": "table",
        "execution_mode": "metadata_only",
        "description": "表未归入任何业务域",
        "threshold_config": {},
        "enabled": True,
    },
    {
        "rule_code": "COL_NULL_COMMENT",
        "rule_name": "字段注释覆盖不足",
        "rule_type": "completeness",
        "rule_category": "COMPLETE",
        "check_scope": "TABLE_INNER",
        "target_type": "column",
        "execution_mode": "metadata_only",
        "description": "字段缺少注释",
        "threshold_config": {"min_comment_rate": 0.5},
        "enabled": True,
    },
    {
        "rule_code": "REL_NOT_VERIFIED",
        "rule_name": "关系未实测验证",
        "rule_type": "completeness",
        "rule_category": "RELATION",
        "check_scope": "TABLE_RELATION",
        "target_type": "relation",
        "execution_mode": "metadata_only",
        "description": "正式关系未经过数据库实测验证",
        "threshold_config": {},
        "enabled": True,
    },
    {
        "rule_code": "CANDIDATE_NOT_REVIEWED",
        "rule_name": "候选关系待审核积压",
        "rule_type": "completeness",
        "rule_category": "RELATION",
        "check_scope": "TABLE_RELATION",
        "target_type": "candidate",
        "execution_mode": "metadata_only",
        "description": "候选关系仍未审核（status=candidate 超过阈值天数）",
        "threshold_config": {"max_days": 30},
        "enabled": True,
    },
    {
        "rule_code": "TABLE_ZERO_COLUMNS",
        "rule_name": "表字段数异常（零字段/未采集）",
        "rule_type": "completeness",
        "rule_category": "COMPLETE",
        "check_scope": "TABLE_INNER",
        "target_type": "table",
        "execution_mode": "metadata_only",
        "description": "表字段数为 0 或 NULL；需与字段明细对账，未采集不得标为确实零字段",
        "threshold_config": {},
        "enabled": True,
    },
    {
        "rule_code": "TABLE_NO_CN_NAME",
        "rule_name": "表中文名缺失",
        "rule_type": "completeness",
        "rule_category": "COMPLETE",
        "check_scope": "TABLE_INNER",
        "target_type": "table",
        "execution_mode": "metadata_only",
        "description": "表缺少中文名（table_name_cn 为空）",
        "threshold_config": {},
        "enabled": True,
    },
    {
        "rule_code": "COLUMN_NO_CN_NAME",
        "rule_name": "字段中文名缺失",
        "rule_type": "completeness",
        "rule_category": "COMPLETE",
        "check_scope": "TABLE_INNER",
        "target_type": "column",
        "execution_mode": "metadata_only",
        "description": "字段缺少中文名（column_name_cn 为空）",
        "threshold_config": {},
        "enabled": True,
    },
    {
        "rule_code": "SOURCE_CONNECTIVITY",
        "rule_name": "数据连接可用性",
        "rule_type": "connectivity",
        "rule_category": "CONNECTIVITY",
        "check_scope": "SYSTEM_CROSS",
        "target_type": "source",
        "execution_mode": "metadata_only",
        "description": "数据源最近连通性检测状态（使用最近一次真实连接测试）",
        "threshold_config": {},
        "enabled": True,
    },
    {
        "rule_code": "SOURCE_METADATA_STALE",
        "rule_name": "元数据采集新鲜度",
        "rule_type": "completeness",
        "rule_category": "CONNECTIVITY",
        "check_scope": "SYSTEM_CROSS",
        "target_type": "source",
        "execution_mode": "metadata_only",
        "description": "数据源元数据快照过旧（超过 7 天未更新）",
        "threshold_config": {"max_days": 7},
        "enabled": True,
    },
]


def _severity(rule_type: str, metric_value: float | None, threshold: dict | None) -> str:
    if rule_type == "orphan":
        if threshold and metric_value is not None:
            limit = threshold.get("max_orphan_rate", 0.01)
            if metric_value > limit * 10:
                return "critical"
            if metric_value > limit * 3:
                return "major"
            if metric_value > limit:
                return "minor"
            return "info"
        return "major" if metric_value and metric_value > 0.01 else "info"
    return "minor"


def _run_rule_rel_orphan(db: Session) -> list[QualityFinding]:
    findings: list[QualityFinding] = []
    threshold = {"max_orphan_rate": 0.05}
    rows = db.scalars(select(AssetRelation)).all()
    for r in rows:
        metrics = r.validation_metrics or ""
        orphan_rate = None
        for part in metrics.replace(";", ",").split(","):
            part = part.strip()
            if part.startswith("orphan_rate="):
                try:
                    orphan_rate = float(part.split("=", 1)[1].strip("%"))
                except ValueError:
                    pass
        if orphan_rate is not None:
            sev = _severity("orphan", orphan_rate, threshold)
            if orphan_rate > threshold["max_orphan_rate"]:
                findings.append(
                    QualityFinding(
                        rule_code="REL_ORPHAN_RATE",
                        target_type="relation",
                        target_ref=f"{r.from_table} -> {r.to_table} (rel_id={r.rel_id})",
                        severity=sev,
                        metric_value=f"orphan_rate={orphan_rate}%",
                        detail={"orphan_rate": orphan_rate, "metrics_raw": metrics, "threshold": threshold["max_orphan_rate"]},
                    )
                )
    return findings


def _run_rule_table_no_domain(db: Session) -> list[QualityFinding]:
    rows = db.scalars(
        select(AssetTable).where(
            (AssetTable.domain.is_(None)) | (AssetTable.domain == "")
        )
    ).all()
    return [
        QualityFinding(
            rule_code="TABLE_NO_DOMAIN",
            target_type="table",
            target_ref=f"{r.schema_name}.{r.table_name}" if r.schema_name else (r.table_name or "?"),
            system_code=r.system_code,
            source_code=r.source_code,
            namespace_name=r.namespace_name,
            schema_name=r.schema_name,
            table_name=r.table_name,
            severity="minor",
            metric_value="domain=empty",
        )
        for r in rows
    ]


def _run_rule_col_null_comment(db: Session) -> list[QualityFinding]:
    threshold = 0.5
    findings: list[QualityFinding] = []

    all_cols = db.scalars(
        select(AssetColumn).where(
            AssetColumn.schema_name.isnot(None),
            AssetColumn.table_name.isnot(None),
        )
    ).all()

    group: dict[tuple[str, str, str, str, str], dict] = {}
    for c in all_cols:
        key = (
            c.system_code or "",
            c.source_code or "",
            c.namespace_name or "",
            c.schema_name or "",
            c.table_name or "",
        )
        if key not in group:
            group[key] = {
                "system": c.system_code,
                "source": c.source_code,
                "namespace": c.namespace_name,
                "schema": c.schema_name,
                "table": c.table_name,
                "total": 0,
                "nulls": 0,
            }
        group[key]["total"] += 1
        if not c.comment:
            group[key]["nulls"] += 1

    for _key, info in group.items():
        if info["total"] > 0:
            null_rate = info["nulls"] / info["total"]
            if null_rate > (1 - threshold):
                findings.append(
                    QualityFinding(
                        rule_code="COL_NULL_COMMENT",
                        target_type="column",
                        target_ref=f"{info['schema']}.{info['table']}",
                        system_code=info["system"],
                        source_code=info["source"],
                        namespace_name=info["namespace"],
                        schema_name=info["schema"],
                        table_name=info["table"],
                        severity="minor",
                        metric_value=f"null_comment_rate={null_rate:.2%} ({info['nulls']}/{info['total']})",
                        detail={"total_columns": info["total"], "null_comments": info["nulls"], "ratio": round(null_rate, 4)},
                    )
                )
    return findings


def _run_rule_rel_not_verified(db: Session) -> list[QualityFinding]:
    rows = db.scalars(
        select(AssetRelation).where(
            AssetRelation.validation_status.is_(None)
            | (AssetRelation.validation_status == "")
            | (AssetRelation.validation_status == "not_tested")
        )
    ).all()
    return [
        QualityFinding(
            rule_code="REL_NOT_VERIFIED",
            target_type="relation",
            target_ref=f"{r.from_table} -> {r.to_table} (rel_id={r.rel_id})",
            severity="minor",
            metric_value=f"status={r.validation_status or 'empty'}",
        )
        for r in rows
    ]


def _run_rule_candidate_not_reviewed(db: Session) -> list[QualityFinding]:
    rows = db.scalars(
        select(AssetCandidateRelation).where(AssetCandidateRelation.status == "candidate")
    ).all()
    unreviewed = len(rows)
    if unreviewed > 0:
        return [
            QualityFinding(
                rule_code="CANDIDATE_NOT_REVIEWED",
                target_type="candidate",
                target_ref=f"共 {unreviewed} 条候选关系待审核",
                severity="major",
                metric_value=f"unreviewed={unreviewed}",
                detail={"total_candidates": unreviewed},
            )
        ]
    return []


def _run_rule_table_zero_columns(db: Session) -> list[QualityFinding]:
    """Report deterministic declared/actual column-count mismatches only.

    A NULL count, or zero with no collected column rows, cannot prove that a
    physical table truly has zero columns. Those states remain metadata
    collection gaps and must not be emitted as false "zero-column" findings.
    """
    rows = db.scalars(select(AssetTable).where(AssetTable.column_count.isnot(None))).all()
    count_rows = db.execute(
        select(
            AssetColumn.system_code,
            AssetColumn.source_code,
            AssetColumn.namespace_name,
            AssetColumn.schema_name,
            AssetColumn.table_name,
            func.count(AssetColumn.id),
        ).group_by(
            AssetColumn.system_code,
            AssetColumn.source_code,
            AssetColumn.namespace_name,
            AssetColumn.schema_name,
            AssetColumn.table_name,
        )
    ).all()
    actual_by_physical = {
        (
            system_code or "",
            source_code or "",
            namespace_name or "",
            schema_name or "",
            table_name or "",
        ): int(actual_count or 0)
        for system_code, source_code, namespace_name, schema_name, table_name, actual_count in count_rows
    }

    findings: list[QualityFinding] = []
    for row in rows:
        key = (
            row.system_code or "",
            row.source_code or "",
            row.namespace_name or "",
            row.schema_name or "",
            row.table_name or "",
        )
        declared = int(row.column_count or 0)
        actual = actual_by_physical.get(key, 0)
        if declared == actual:
            continue
        findings.append(
            QualityFinding(
                rule_code="TABLE_ZERO_COLUMNS",
                target_type="table",
                target_ref=(
                    f"{row.schema_name}.{row.table_name}"
                    if row.schema_name
                    else (row.table_name or "?")
                ),
                system_code=row.system_code,
                source_code=row.source_code,
                namespace_name=row.namespace_name,
                schema_name=row.schema_name,
                table_name=row.table_name,
                severity="major" if declared == 0 or actual == 0 else "minor",
                metric_value=f"declared={declared}, actual={actual}",
                total_cnt=actual,
                error_cnt=abs(declared - actual),
                detail={
                    "classification": "column_count_mismatch",
                    "declared_column_count": declared,
                    "actual_column_count": actual,
                },
            )
        )
    return findings


def _run_rule_table_no_cn_name(db: Session) -> list[QualityFinding]:
    rows = db.scalars(
        select(AssetTable).where(
            (AssetTable.table_name_cn.is_(None)) | (AssetTable.table_name_cn == "")
        )
    ).all()
    if not rows:
        return []
    return [
        QualityFinding(
            rule_code="TABLE_NO_CN_NAME",
            target_type="table",
            target_ref=f"共 {len(rows)} 张表缺中文名",
            severity="minor",
            metric_value=f"total_missing={len(rows)}",
        )
    ]


def _run_rule_column_no_cn_name(db: Session) -> list[QualityFinding]:
    rows = db.scalars(
        select(AssetColumn).where(
            (AssetColumn.column_name_cn.is_(None)) | (AssetColumn.column_name_cn == "")
        )
    ).all()
    total = db.scalar(select(func.count()).select_from(AssetColumn)) or 1
    missing = len(rows)
    return [
        QualityFinding(
            rule_code="COLUMN_NO_CN_NAME",
            target_type="column",
            target_ref=f"共 {missing}/{total} 字段缺中文名",
            severity="minor",
            metric_value=f"missing={missing}, rate={missing/total:.2%}",
        )
    ]


def _run_rule_source_connectivity(db: Session) -> list[QualityFinding]:
    from ...models.asset_system import AssetDataSource
    rows = db.scalars(select(AssetDataSource).where(AssetDataSource.enabled.is_(True))).all()
    findings = []
    for s in rows:
        if s.last_check_status and s.last_check_status != "connected":
            findings.append(QualityFinding(
                rule_code="SOURCE_CONNECTIVITY",
                target_type="source",
                target_ref=s.source_code,
                system_code=s.system_code,
                source_code=s.source_code,
                severity="major",
                metric_value=f"status={s.last_check_status}",
            ))
    return findings


def _run_rule_source_metadata_stale(db: Session) -> list[QualityFinding]:
    from ...models.asset_system import AssetDataSource
    rows = db.scalars(select(AssetDataSource).where(AssetDataSource.enabled.is_(True))).all()
    findings = []
    for s in rows:
        if not s.last_check_at:
            findings.append(QualityFinding(
                rule_code="SOURCE_METADATA_STALE",
                target_type="source",
                target_ref=s.source_code,
                system_code=s.system_code,
                source_code=s.source_code,
                severity="minor",
                metric_value="never_checked",
            ))
    return findings


RULE_RUNNERS = {
    "REL_ORPHAN_RATE": _run_rule_rel_orphan,
    "TABLE_NO_DOMAIN": _run_rule_table_no_domain,
    "COL_NULL_COMMENT": _run_rule_col_null_comment,
    "REL_NOT_VERIFIED": _run_rule_rel_not_verified,
    "CANDIDATE_NOT_REVIEWED": _run_rule_candidate_not_reviewed,
    "TABLE_ZERO_COLUMNS": _run_rule_table_zero_columns,
    "TABLE_NO_CN_NAME": _run_rule_table_no_cn_name,
    "COLUMN_NO_CN_NAME": _run_rule_column_no_cn_name,
    "SOURCE_CONNECTIVITY": _run_rule_source_connectivity,
    "SOURCE_METADATA_STALE": _run_rule_source_metadata_stale,
}


def seed_rules(db: Session) -> None:
    """Insert missing seed rules and backfill governance fields on enabled seeds."""
    for rule_data in QUALITY_RULES_SEED:
        existing = db.scalar(
            select(QualityRule).where(QualityRule.rule_code == rule_data["rule_code"])
        )
        if not existing:
            db.add(QualityRule(**rule_data))
            continue
        # Backfill empty governance fields without forcing re-enable of SQL suggestions
        for field in (
            "rule_name",
            "rule_category",
            "check_scope",
            "description",
            "rule_type",
            "target_type",
            "execution_mode",
        ):
            if field in rule_data and not getattr(existing, field, None):
                setattr(existing, field, rule_data[field])
    db.commit()


@router.get("/rules", summary="获取质量规则列表（分页）")
def list_rules(
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=200),
    rule_category: str | None = Query(None),
    check_scope: str | None = Query(None),
    constraint_level: str | None = Query(None),
    enabled: bool | None = Query(None),
    system_code: str | None = Query(None),
    source_code: str | None = Query(None),
    keyword: str | None = Query(None),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    """Paginated rules contract: data={items,total,page,page_size} (127 A1)."""
    seed_rules(db)
    stmt = select(QualityRule)
    if rule_category:
        stmt = stmt.where(QualityRule.rule_category == rule_category)
    if check_scope:
        stmt = stmt.where(QualityRule.check_scope == check_scope)
    if constraint_level:
        stmt = stmt.where(QualityRule.constraint_level == constraint_level)
    if enabled is not None:
        stmt = stmt.where(QualityRule.enabled.is_(enabled))
    if system_code:
        stmt = stmt.where(QualityRule.system_code == system_code)
    if source_code:
        stmt = stmt.where(QualityRule.source_code == source_code)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(
            QualityRule.rule_code.ilike(like)
            | QualityRule.rule_name.ilike(like)
            | QualityRule.description.ilike(like)
        )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(QualityRule.rule_code).offset((page - 1) * page_size).limit(page_size)
    ).all()
    items = [QualityRuleItem.model_validate(r).model_dump() for r in rows]
    return ApiResponse(
        data={"total": total, "page": page, "page_size": page_size, "items": items}
    )


def run_quality_check_core(
    db: Session,
    *,
    rule_codes: list[str] | None = None,
    triggered_by: str = "manual",
) -> dict:
    """Shared entry for manual API and nightly scheduler (L15)."""
    seed_rules(db)

    rules_q = select(QualityRule).where(QualityRule.enabled.is_(True))  # noqa: E712
    if rule_codes:
        rules_q = rules_q.where(QualityRule.rule_code.in_(rule_codes))
    rules = db.scalars(rules_q).all()

    system_codes = list({r.system_code for r in rules if r.system_code})
    source_codes = list({r.source_code for r in rules if r.source_code})

    run = QualityCheckRun(
        started_at=datetime.now(timezone.utc),
        triggered_by=triggered_by,
        total_rules=len(rules),
        status="running",
        system_code=system_codes[0] if len(system_codes) == 1 else None,
        source_code=source_codes[0] if len(source_codes) == 1 else None,
    )
    db.add(run)
    db.commit()

    total_findings = 0
    total_records = 0
    error_records = 0
    rules_with_findings: set[str] = set()
    try:
        for rule in rules:
            if rule.execution_mode == "sql_template":
                validation = validate_sql_safety(rule.check_sql or "")
                if not validation.get("valid"):
                    f = QualityFinding(
                        run_id=run.id,
                        rule_code=rule.rule_code,
                        target_type=rule.target_type or "table",
                        target_ref=rule.system_code or "",
                        system_code=rule.system_code,
                        source_code=rule.source_code,
                        severity="info",
                        status="rule_error",
                        note=f"SQL validation failed: {validation.get('errors', [])}",
                    )
                    db.add(f)
                    total_findings += 1
                    rules_with_findings.add(rule.rule_code)
                    continue

                result = execute_quality_sql(
                    rule_code=rule.rule_code,
                    sql=rule.check_sql or "",
                    source_code=rule.source_code or "",
                    sample_limit=rule.sample_limit or 20,
                    db=db,
                )
                total_records += result.get("total_cnt", 0)
                error_records += result.get("error_cnt", 0)

                sample_data_raw = result.get("sample_data", [])
                if isinstance(sample_data_raw, list):
                    sample_data = [
                        mask_sensitive(item) if isinstance(item, dict) else item
                        for item in sample_data_raw
                    ]
                else:
                    sample_data = mask_sensitive(sample_data_raw)

                if result.get("error_cnt", 0) > 0:
                    f = QualityFinding(
                        run_id=run.id,
                        rule_code=rule.rule_code,
                        target_type=rule.target_type or "table",
                        target_ref=f"{rule.namespace_name or ''}.{rule.target_table or ''}.{rule.target_field or ''}",
                        system_code=rule.system_code,
                        source_code=rule.source_code,
                        namespace_name=rule.namespace_name,
                        table_name=rule.target_table,
                        column_name=rule.target_field,
                        severity=rule.error_level or "minor",
                        status="open",
                        metric_value=f"error_rate={result.get('error_rate', 0)}%",
                        total_cnt=result.get("total_cnt", 0),
                        error_cnt=result.get("error_cnt", 0),
                        error_rate=result.get("error_rate", 0),
                        sample_data=sample_data,
                        detail={
                            "sql": rule.check_sql,
                            "execution_result": result,
                        },
                    )
                    db.add(f)
                    total_findings += 1
                    rules_with_findings.add(rule.rule_code)
                continue

            runner = RULE_RUNNERS.get(rule.rule_code)
            if not runner:
                continue
            new_findings = runner(db)
            deduped = 0
            for f in new_findings:
                f.run_id = run.id
                if isinstance(f.sample_data, list):
                    f.sample_data = [
                        mask_sensitive(item) if isinstance(item, dict) else item
                        for item in f.sample_data
                    ]
                elif isinstance(f.sample_data, dict):
                    f.sample_data = mask_sensitive(f.sample_data)
                existing = db.scalar(
                    select(QualityFinding).where(
                        QualityFinding.rule_code == f.rule_code,
                        QualityFinding.target_type == f.target_type,
                        QualityFinding.target_ref == f.target_ref,
                        QualityFinding.status.in_(["open", "acknowledged"]),
                    )
                )
                if existing:
                    existing.metric_value = f.metric_value
                    existing.detail = f.detail
                    existing.sample_data = f.sample_data
                    existing.run_id = run.id
                    existing.found_at = datetime.now(timezone.utc)
                    deduped += 1
                else:
                    db.add(f)
            if len(new_findings) > 0:
                rules_with_findings.add(rule.rule_code)
            total_findings += len(new_findings) - deduped

        pass_rate = (
            int((run.total_rules - len(rules_with_findings)) / run.total_rules * 100)
            if run.total_rules and run.total_rules > 0
            else 100
        )

        run.total_findings = total_findings
        run.total_records = total_records
        run.error_records = error_records
        run.pass_rate = pass_rate
        run.status = "success"
        run.finished_at = datetime.now(timezone.utc)
        db.commit()
    except Exception:
        run.status = "failed"
        run.finished_at = datetime.now(timezone.utc)
        db.commit()
        raise

    return {
        "run_id": run.id,
        "total_rules": run.total_rules,
        "total_findings": total_findings,
        "total_records": total_records,
        "error_records": error_records,
        "pass_rate": pass_rate,
        "status": run.status,
        "triggered_by": triggered_by,
    }


@router.post(
    "/checks/run",
    summary="手动触发质量检查",
    dependencies=[Depends(require_permission("asset.quality.rule.execute"))],
)
def run_quality_check(
    rule_codes: list[str] | None = Query(None),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    return ApiResponse(data=run_quality_check_core(db, rule_codes=rule_codes, triggered_by="manual"))


@router.get("/checks/runs", summary="质量检查历史")
def list_check_runs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    stmt = select(QualityCheckRun)
    count = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(QualityCheckRun.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    items = [QualityCheckRunItem.model_validate(r) for r in rows]
    return ApiResponse(data={"total": count, "page": page, "page_size": page_size, "items": items})


@router.get("/findings", summary="质量问题列表")
def list_findings(
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=200),
    severity: str | None = Query(None),
    status: str | None = Query(None),
    rule_code: str | None = Query(None),
    run_id: int | None = Query(None),
    keyword: str | None = Query(None),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    stmt = select(QualityFinding)
    if severity:
        stmt = stmt.where(QualityFinding.severity == severity)
    if status:
        stmt = stmt.where(QualityFinding.status == status)
    if rule_code:
        stmt = stmt.where(QualityFinding.rule_code == rule_code)
    if run_id is not None:
        stmt = stmt.where(QualityFinding.run_id == run_id)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(QualityFinding.target_ref.ilike(like))

    count = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(
            QualityFinding.severity.desc(),
            QualityFinding.found_at.desc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    items = [QualityFindingItem.model_validate(r) for r in rows]
    return ApiResponse(data={"total": count, "page": page, "page_size": page_size, "items": items})


@router.patch(
    "/findings/{finding_id}",
    summary="更新问题状态",
    dependencies=[Depends(require_permission("asset.quality.rule.execute"))],
)
def update_finding(
    finding_id: int,
    req: FindingUpdateRequest,
    db: Session = Depends(get_db),
) -> ApiResponse[QualityFindingItem]:
    finding = db.get(QualityFinding, finding_id)
    if not finding:
        raise HTTPException(status_code=404, detail="问题不存在")
    if req.status:
        finding.status = req.status
    if req.resolved_by:
        finding.resolved_by = req.resolved_by
    if req.note:
        finding.note = req.note
    if req.status in ("resolved", "ignored"):
        finding.resolved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(finding)
    return ApiResponse(data=QualityFindingItem.model_validate(finding))


@router.get("/summary", summary="质量总览")
def quality_summary(db: Session = Depends(get_db)) -> ApiResponse[QualitySummary]:
    total = db.scalar(select(func.count(QualityFinding.id))) or 0
    open_count = db.scalar(select(func.count(QualityFinding.id)).where(QualityFinding.status == "open")) or 0
    ack_count = db.scalar(select(func.count(QualityFinding.id)).where(QualityFinding.status == "acknowledged")) or 0
    resolved_count = db.scalar(select(func.count(QualityFinding.id)).where(QualityFinding.status == "resolved")) or 0
    critical = db.scalar(select(func.count(QualityFinding.id)).where(QualityFinding.severity == "critical")) or 0
    major = db.scalar(select(func.count(QualityFinding.id)).where(QualityFinding.severity == "major")) or 0
    minor = db.scalar(select(func.count(QualityFinding.id)).where(QualityFinding.severity == "minor")) or 0
    info = db.scalar(select(func.count(QualityFinding.id)).where(QualityFinding.severity == "info")) or 0

    top_table_rows = db.execute(
        select(QualityFinding.target_ref, func.count(QualityFinding.id).label("cnt"))
        .where(QualityFinding.target_ref.isnot(None))
        .group_by(QualityFinding.target_ref)
        .order_by(func.count(QualityFinding.id).desc())
        .limit(10)
    ).all()
    top_tables = [{"table": r[0].split(" ")[0] if r[0] else "unknown", "count": r[1]} for r in top_table_rows]

    return ApiResponse(
        data=QualitySummary(
            total_findings=total,
            open_count=open_count,
            acknowledged_count=ack_count,
            resolved_count=resolved_count,
            critical_count=critical,
            major_count=major,
            minor_count=minor,
            info_count=info,
            top_tables=top_tables,
        )
    )


@router.get("/summary/by-system", summary="按系统分组的质量总览")
def quality_summary_by_system(
    db: Session = Depends(get_db),
) -> ApiResponse[list[dict]]:
    """Per-system finding counts by real attribution (127 A3/A4). Never copy global totals."""
    from ...services.asset_catalog import load_system_name_map, normalize_system_code

    tables = db.scalars(select(AssetTable)).all()
    findings = db.scalars(select(QualityFinding)).all()
    name_map = load_system_name_map(db)
    grouped: dict[str, dict] = {}

    def _bucket(code: str | None) -> str:
        raw = (code or "").strip()
        if not raw:
            return "UNASSIGNED"
        return normalize_system_code(raw) or raw

    def _ensure(sc: str) -> dict:
        if sc not in grouped:
            display = sc
            if sc == "UNASSIGNED":
                display_cn = "待归属"
            else:
                display_cn = name_map.get(sc) or sc
            grouped[sc] = {
                "system_code": sc,
                "system_name_cn": display_cn,
                "table_count": 0,
                "column_count": 0,
                "total_findings": 0,
                "open_count": 0,
                "resolved_count": 0,
                "critical_count": 0,
                # backward-compatible aliases
                "findings_total": 0,
                "findings_open": 0,
            }
        return grouped[sc]

    for t in tables:
        sc = _bucket(t.system_code)
        b = _ensure(sc)
        b["table_count"] += 1
        b["column_count"] += t.column_count or 0

    for f in findings:
        sc = _bucket(f.system_code)
        b = _ensure(sc)
        status = (f.status or "open").lower()
        b["total_findings"] += 1
        b["findings_total"] += 1
        if status == "open":
            b["open_count"] += 1
            b["findings_open"] += 1
        elif status in {"resolved", "fixed", "ignored"}:
            b["resolved_count"] += 1
        if (f.severity or "").lower() == "critical":
            b["critical_count"] += 1

    return ApiResponse(
        data=sorted(grouped.values(), key=lambda x: x["total_findings"], reverse=True)
    )


# ──────────────────────────────────────────────
# Q3: 质控规则 CRUD + SQL 校验 + metrics
# ──────────────────────────────────────────────


class RuleCreate(BaseModel):
    rule_code: str
    rule_name: str | None = None
    rule_type: str | None = None
    rule_category: str | None = None
    check_scope: str | None = None
    constraint_level: str | None = "WARN"
    business_domain: str | None = None
    system_code: str | None = None
    source_code: str | None = None
    namespace_name: str | None = None
    target_table: str | None = None
    target_field: str | None = None
    related_table: str | None = None
    related_field: str | None = None
    target_type: str | None = None
    execution_mode: str | None = "metadata_only"
    check_sql: str | None = None
    error_condition: str | None = None
    error_level: str | None = "minor"
    description: str | None = None
    threshold_config: dict | None = None
    sample_limit: int | None = 20
    remark: str | None = None
    enabled: bool = False


class RulePatch(BaseModel):
    rule_name: str | None = None
    rule_type: str | None = None
    rule_category: str | None = None
    check_scope: str | None = None
    constraint_level: str | None = None
    business_domain: str | None = None
    target_table: str | None = None
    target_field: str | None = None
    related_table: str | None = None
    related_field: str | None = None
    execution_mode: str | None = None
    check_sql: str | None = None
    error_condition: str | None = None
    error_level: str | None = None
    description: str | None = None
    threshold_config: dict | None = None
    sample_limit: int | None = None
    remark: str | None = None
    enabled: bool | None = None


class TemplateGenerate(BaseModel):
    template_type: str = Field(..., description="unique_pk/complete_required/standard_length/standard_domain/relation_orphan/accuracy_time")
    params: dict = Field(default_factory=dict)


class AutoGenerateRequest(BaseModel):
    system_code: str | None = None
    source_code: str | None = None
    limit: int = Field(default=100, ge=1, le=500)


class FindingAssign(BaseModel):
    assigned_to: str
    note: str | None = None


@router.post(
    "/rules",
    summary="新建质控规则",
    dependencies=[Depends(require_permission("asset.quality.rule.create"))],
)
def create_rule(req: RuleCreate, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    existing = db.scalar(select(QualityRule).where(QualityRule.rule_code == req.rule_code))
    if existing:
        raise HTTPException(status_code=400, detail=f"规则 {req.rule_code} 已存在")
    rule = QualityRule(**req.model_dump(exclude_none=True))
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return ApiResponse(data={"id": rule.id, "rule_code": rule.rule_code})


@router.patch(
    "/rules/{rule_id}",
    summary="编辑质控规则",
    dependencies=[Depends(require_permission("asset.quality.rule.create"))],
)
def patch_rule(rule_id: int, req: RulePatch, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    rule = db.get(QualityRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404)
    for k, v in req.model_dump(exclude_none=True).items():
        setattr(rule, k, v)
    db.commit()
    return ApiResponse(data={"id": rule.id, "rule_code": rule.rule_code})


@router.post(
    "/rules/{rule_id}/enable",
    summary="启用/停用规则",
    dependencies=[Depends(require_permission("asset.quality.rule.create"))],
)
def toggle_rule(rule_id: int, enabled: bool = Query(True), db: Session = Depends(get_db)) -> ApiResponse[dict]:
    rule = db.get(QualityRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404)
    rule.enabled = enabled
    db.commit()
    return ApiResponse(data={"id": rule.id, "enabled": rule.enabled})


@router.delete(
    "/rules/{rule_id}",
    summary="删除质控规则",
    dependencies=[Depends(require_permission("asset.quality.rule.create"))],
)
def delete_rule(rule_id: int, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    rule = db.get(QualityRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404)
    finding_count = db.scalar(
        select(func.count())
        .select_from(QualityFinding)
        .where(QualityFinding.rule_code == rule.rule_code)
    ) or 0
    if finding_count > 0:
        raise HTTPException(status_code=400, detail="该规则已有质控问题记录，不能删除；请停用规则")
    rule_code = rule.rule_code
    db.delete(rule)
    db.commit()
    return ApiResponse(data={"id": rule_id, "rule_code": rule_code, "deleted": True})


@router.post(
    "/rules/{rule_id}/validate-sql",
    summary="校验只读 SQL 安全性",
    dependencies=[Depends(require_permission("asset.quality.rule.create"))],
)
def validate_rule_sql(rule_id: int, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    rule = db.get(QualityRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404)
    if not rule.check_sql:
        raise HTTPException(status_code=400, detail="该规则没有 check_sql")
    result = validate_sql_safety(rule.check_sql)
    return ApiResponse(data=result)


@router.post(
    "/rules/from-template",
    summary="从模板生成质控规则",
    dependencies=[Depends(require_permission("asset.quality.rule.create"))],
)
def rule_from_template(req: TemplateGenerate, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    from ...services import quality_templates as tpl

    template_fn = getattr(tpl, f"template_{req.template_type}", None)
    if not template_fn:
        raise HTTPException(status_code=400, detail=f"未知模板类型: {req.template_type}")

    sql = template_fn(**req.params)
    return ApiResponse(data={"sql": sql, "template_type": req.template_type})


@router.post(
    "/rules/auto-generate",
    summary="按主键和已确认关系生成质控规则建议",
    dependencies=[Depends(require_permission("asset.quality.rule.create"))],
)
def auto_generate_rules(req: AutoGenerateRequest, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    """Generate disabled suggestions from trusted asset metadata only.

    No source database is queried and no generated rule is enabled implicitly.
    """
    import re

    identifier = re.compile(r"^[A-Za-z_][A-Za-z0-9_$#]*$")
    created: list[str] = []
    skipped = 0
    tables_stmt = select(AssetTable).where(AssetTable.pk.is_not(None))
    if req.system_code:
        tables_stmt = tables_stmt.where(AssetTable.system_code == req.system_code)
    if req.source_code:
        tables_stmt = tables_stmt.where(AssetTable.source_code == req.source_code)
    for table in db.scalars(tables_stmt.order_by(AssetTable.system_code, AssetTable.schema_name, AssetTable.table_name).limit(req.limit)).all():
        fields = [x.strip() for x in re.split(r"[,;+]", str(table.pk or "")) if x.strip()]
        if not fields or not all(identifier.fullmatch(x) for x in fields):
            continue
        table_ref = ".".join(x for x in (table.schema_name, table.table_name) if x)
        if not table_ref or not identifier.fullmatch(table.table_name or ""):
            continue
        code = f"AUTO_PK_{(table.system_code or 'ASSET')}_{table.schema_name or 'PUBLIC'}_{table.table_name}".upper().replace("-", "_")
        if db.scalar(select(QualityRule).where(QualityRule.rule_code == code)):
            skipped += 1
            continue
        db.add(QualityRule(
            rule_code=code[:240],
            rule_name=f"{table.table_name_cn or table.table_name} 主键唯一性",
            rule_type="metadata_generated",
            rule_category="UNIQUE",
            check_scope="TABLE_INNER",
            constraint_level="WARN",
            system_code=table.system_code,
            source_code=table.source_code,
            namespace_name=table.schema_name,
            target_table=table.table_name,
            target_field=",".join(fields),
            execution_mode="sql_template",
            check_sql=f"SELECT {', '.join(fields)}, COUNT(*) AS dup_cnt FROM {table_ref} GROUP BY {', '.join(fields)} HAVING COUNT(*) > 1",
            error_condition="dup_cnt > 1",
            error_level="major",
            description="依据资产元数据已确认主键生成；启用前需复核数据源权限与 SQL 方言。",
            enabled=False,
            remark="auto_generated_from_asset_pk",
        ))
        created.append(code[:240])

    relations_stmt = select(AssetRelation).where(
        AssetRelation.validation_status.in_(("verified", "sample_pass", "sample_verified")),
        AssetRelation.from_source_code == AssetRelation.to_source_code,
    )
    if req.source_code:
        relations_stmt = relations_stmt.where(AssetRelation.from_source_code == req.source_code)
    for relation in db.scalars(relations_stmt.limit(req.limit)).all():
        from_fields = [x.strip() for x in re.split(r"[,;+]", str(relation.from_columns or "")) if x.strip()]
        to_fields = [x.strip() for x in re.split(r"[,;+]", str(relation.to_columns or "")) if x.strip()]
        if len(from_fields) != 1 or len(to_fields) != 1 or not all(identifier.fullmatch(x) for x in (*from_fields, *to_fields)):
            continue
        child = relation.from_table or relation.from_schema_name
        parent = relation.to_table or relation.to_schema_name
        if not child or not parent or not identifier.fullmatch(child.split(".")[-1]) or not identifier.fullmatch(parent.split(".")[-1]):
            continue
        code = f"AUTO_REL_{relation.id}"
        if db.scalar(select(QualityRule).where(QualityRule.rule_code == code)):
            skipped += 1
            continue
        child_ref = child if "." in child else ".".join(x for x in (relation.from_schema_name, child) if x)
        parent_ref = parent if "." in parent else ".".join(x for x in (relation.to_schema_name, parent) if x)
        db.add(QualityRule(
            rule_code=code,
            rule_name=f"{child.split('.')[-1]} 关联 {parent.split('.')[-1]} 孤儿记录",
            rule_type="metadata_generated",
            rule_category="RELATION",
            check_scope="TABLE_RELATION",
            constraint_level="WARN",
            system_code=relation.from_system_code,
            source_code=relation.from_source_code,
            namespace_name=relation.from_schema_name,
            target_table=child.split(".")[-1],
            target_field=from_fields[0],
            related_table=parent.split(".")[-1],
            related_field=to_fields[0],
            execution_mode="sql_template",
            check_sql=f"SELECT COUNT(*) AS orphan_cnt FROM {child_ref} c WHERE c.{from_fields[0]} IS NOT NULL AND NOT EXISTS (SELECT 1 FROM {parent_ref} p WHERE p.{to_fields[0]} = c.{from_fields[0]})",
            error_condition="orphan_cnt > 0",
            error_level="major",
            description="依据已验证同源关系生成；跨系统关系不自动生成可执行 SQL。",
            enabled=False,
            remark="auto_generated_from_verified_relation",
        ))
        created.append(code)
    db.commit()
    return ApiResponse(data={"created": len(created), "skipped": skipped, "rule_codes": created})


@router.post(
    "/findings/{finding_id}/assign",
    summary="问题分派",
    dependencies=[Depends(require_permission("asset.quality.rule.execute"))],
)
def assign_finding(finding_id: int, req: FindingAssign, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    f = db.get(QualityFinding, finding_id)
    if not f:
        raise HTTPException(status_code=404)
    f.assigned_to = req.assigned_to
    f.status = "assigned"
    if req.note:
        f.note = req.note
    db.commit()
    return ApiResponse(data={"id": f.id, "assigned_to": f.assigned_to, "status": f.status})


@router.post(
    "/findings/{finding_id}/recheck",
    summary="单问题复核",
    dependencies=[Depends(require_permission("asset.quality.rule.execute"))],
)
def recheck_finding(finding_id: int, status: str = Query(..., description="confirmed/fixed/ignored"), db: Session = Depends(get_db)) -> ApiResponse[dict]:
    if status not in ("confirmed", "fixed", "ignored", "rechecked"):
        raise HTTPException(status_code=400, detail="status 必须为 confirmed/fixed/ignored/rechecked")
    f = db.get(QualityFinding, finding_id)
    if not f:
        raise HTTPException(status_code=404)
    f.status = "rechecked" if status == "rechecked" else status
    f.confirmed_by = "reviewer"
    f.resolved_at = datetime.now(timezone.utc)
    db.commit()
    return ApiResponse(data={"id": f.id, "status": f.status})


@router.get("/metrics", summary="质量看板指标")
def quality_metrics(
    system_code: str | None = Query(None),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    """Metrics with array rule_categories and split pass rates (127 A5)."""
    rules = db.scalars(select(QualityRule).where(QualityRule.enabled.is_(True))).all()
    total_rules = len(rules)
    sql_rules = len([r for r in rules if r.execution_mode == "sql_template"])

    count_stmt = select(func.count(QualityFinding.id))
    open_stmt = select(func.count(QualityFinding.id)).where(QualityFinding.status == "open")
    resolved_stmt = select(func.count(QualityFinding.id)).where(
        QualityFinding.status.in_(["resolved", "fixed"])
    )
    if system_code:
        count_stmt = count_stmt.where(QualityFinding.system_code == system_code)
        open_stmt = open_stmt.where(QualityFinding.system_code == system_code)
        resolved_stmt = resolved_stmt.where(QualityFinding.system_code == system_code)

    total = db.scalar(count_stmt) or 0
    open_count = db.scalar(open_stmt) or 0
    resolved_count = db.scalar(resolved_stmt) or 0
    # resolution_rate: closed findings / all findings (not "rule pass rate")
    resolution_rate = round((resolved_count / total * 100) if total > 0 else 100.0, 1)
    # rules_pass_rate: prefer last run pass_rate when available
    last_run = db.scalar(select(QualityCheckRun).order_by(QualityCheckRun.id.desc()).limit(1))
    rules_pass_rate = None
    if last_run and last_run.pass_rate is not None:
        rules_pass_rate = float(last_run.pass_rate)
    # Keep pass_rate as resolution_rate for backward UI, but label correctly via new fields
    pass_rate = resolution_rate

    top_stmt = select(QualityFinding.table_name, func.count(QualityFinding.id).label("cnt"))
    if system_code:
        top_stmt = top_stmt.where(QualityFinding.system_code == system_code)
    top_rows = db.execute(
        top_stmt.group_by(QualityFinding.table_name)
        .order_by(func.count(QualityFinding.id).desc())
        .limit(5)
    ).all()
    top_tables = [{"table": r[0] or "unknown", "count": r[1]} for r in top_rows]

    cat_counts: dict[str, int] = {}
    for r in rules:
        cat = r.rule_category or r.rule_type or "other"
        cat_counts[cat] = cat_counts.get(cat, 0) + 1
    rule_categories = [{"category": k, "count": v} for k, v in sorted(cat_counts.items())]

    return ApiResponse(
        data={
            "total_rules": total_rules,
            "enabled_rules": total_rules,
            "sql_rules": sql_rules,
            "total_findings": total,
            "open_findings": open_count,
            "resolved_findings": resolved_count,
            "pass_rate": pass_rate,
            "resolution_rate": resolution_rate,
            "rules_pass_rate": rules_pass_rate,
            "rule_categories": rule_categories,
            "top_tables": top_tables,
        }
    )
