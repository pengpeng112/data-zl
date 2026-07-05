from collections import Counter
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ...core.db import get_db
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
        "rule_type": "orphan",
        "target_type": "relation",
        "execution_mode": "metadata_only",
        "description": "正式关系孤儿率超标（基于 validation_metrics 中已存储的 orphan_rate）",
        "threshold_config": {"max_orphan_rate": 0.05},
    },
    {
        "rule_code": "TABLE_NO_DOMAIN",
        "rule_type": "completeness",
        "target_type": "table",
        "execution_mode": "metadata_only",
        "description": "表未归入任何业务域",
        "threshold_config": {},
    },
    {
        "rule_code": "COL_NULL_COMMENT",
        "rule_type": "completeness",
        "target_type": "column",
        "execution_mode": "metadata_only",
        "description": "字段缺少注释",
        "threshold_config": {"min_comment_rate": 0.5},
    },
    {
        "rule_code": "REL_NOT_VERIFIED",
        "rule_type": "completeness",
        "target_type": "relation",
        "execution_mode": "metadata_only",
        "description": "正式关系未经过数据库实测验证",
        "threshold_config": {},
    },
    {
        "rule_code": "CANDIDATE_NOT_REVIEWED",
        "rule_type": "completeness",
        "target_type": "candidate",
        "execution_mode": "metadata_only",
        "description": "候选关系仍未审核（status=candidate 超过阈值天数）",
        "threshold_config": {"max_days": 30},
    },
    {
        "rule_code": "TABLE_ZERO_COLUMNS",
        "rule_type": "completeness",
        "target_type": "table",
        "execution_mode": "metadata_only",
        "description": "表字段数为 0 或 NULL",
        "threshold_config": {},
    },
    {
        "rule_code": "TABLE_NO_CN_NAME",
        "rule_type": "completeness",
        "target_type": "table",
        "execution_mode": "metadata_only",
        "description": "表缺少中文名（table_name_cn 为空）",
        "threshold_config": {},
    },
    {
        "rule_code": "COLUMN_NO_CN_NAME",
        "rule_type": "completeness",
        "target_type": "column",
        "execution_mode": "metadata_only",
        "description": "字段缺少中文名（column_name_cn 为空）",
        "threshold_config": {},
    },
    {
        "rule_code": "SOURCE_CONNECTIVITY",
        "rule_type": "connectivity",
        "target_type": "source",
        "execution_mode": "metadata_only",
        "description": "数据源最近连通性检测状态（待 P5.5 实现实际连接测试）",
        "threshold_config": {},
    },
    {
        "rule_code": "SOURCE_METADATA_STALE",
        "rule_type": "completeness",
        "target_type": "source",
        "execution_mode": "metadata_only",
        "description": "数据源元数据快照过旧（超过 7 天未更新）",
        "threshold_config": {"max_days": 7},
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

    group: dict[str, dict] = {}
    for c in all_cols:
        key = f"{c.schema_name}.{c.table_name}"
        if key not in group:
            group[key] = {"schema": c.schema_name, "table": c.table_name, "total": 0, "nulls": 0}
        group[key]["total"] += 1
        if not c.comment:
            group[key]["nulls"] += 1

    for key, info in group.items():
        if info["total"] > 0:
            null_rate = info["nulls"] / info["total"]
            if null_rate > (1 - threshold):
                findings.append(
                    QualityFinding(
                        rule_code="COL_NULL_COMMENT",
                        target_type="column",
                        target_ref=key,
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
    rows = db.scalars(
        select(AssetTable).where(
            (AssetTable.column_count.is_(None)) | (AssetTable.column_count == 0)
        )
    ).all()
    return [
        QualityFinding(
            rule_code="TABLE_ZERO_COLUMNS",
            target_type="table",
            target_ref=f"{r.schema_name}.{r.table_name}" if r.schema_name else (r.table_name or "?"),
            severity="major",
            metric_value=f"column_count={r.column_count}",
        )
        for r in rows
    ]


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
    rows = db.scalars(select(AssetDataSource).where(AssetDataSource.enabled == True)).all()
    findings = []
    for s in rows:
        if s.last_check_status and s.last_check_status != "connected":
            findings.append(QualityFinding(
                rule_code="SOURCE_CONNECTIVITY",
                target_type="source",
                target_ref=s.source_code,
                severity="major",
                metric_value=f"status={s.last_check_status}",
            ))
    return findings


def _run_rule_source_metadata_stale(db: Session) -> list[QualityFinding]:
    from ...models.asset_system import AssetDataSource
    rows = db.scalars(select(AssetDataSource).where(AssetDataSource.enabled == True)).all()
    findings = []
    for s in rows:
        if not s.last_check_at:
            findings.append(QualityFinding(
                rule_code="SOURCE_METADATA_STALE",
                target_type="source",
                target_ref=s.source_code,
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
    for rule_data in QUALITY_RULES_SEED:
        existing = db.scalar(
            select(QualityRule).where(QualityRule.rule_code == rule_data["rule_code"])
        )
        if not existing:
            db.add(QualityRule(**rule_data))
    db.commit()


@router.get("/rules", summary="获取质量规则列表")
def list_rules(db: Session = Depends(get_db)) -> ApiResponse[list[QualityRuleItem]]:
    seed_rules(db)
    rows = db.scalars(select(QualityRule).order_by(QualityRule.rule_code)).all()
    return ApiResponse(data=[QualityRuleItem.model_validate(r) for r in rows])


@router.post("/checks/run", summary="手动触发质量检查")
def run_quality_check(
    rule_codes: list[str] | None = Query(None),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    seed_rules(db)

    rules_q = select(QualityRule).where(QualityRule.enabled == True)
    if rule_codes:
        rules_q = rules_q.where(QualityRule.rule_code.in_(rule_codes))
    rules = db.scalars(rules_q).all()

    system_codes = list({r.system_code for r in rules if r.system_code})
    source_codes = list({r.source_code for r in rules if r.source_code})

    run = QualityCheckRun(
        started_at=datetime.now(timezone.utc),
        triggered_by="manual",
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
                        rectification_status="open",
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
                        rectification_status="open",
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

    return ApiResponse(
        data={
            "run_id": run.id,
            "total_rules": run.total_rules,
            "total_findings": total_findings,
            "total_records": total_records,
            "error_records": error_records,
            "pass_rate": pass_rate,
            "status": run.status,
        }
    )


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


@router.patch("/findings/{finding_id}", summary="更新问题状态")
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
    if req.rectification_status:
        finding.rectification_status = req.rectification_status
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
    from ...models.asset_system import AssetSystem
    tables = db.scalars(select(AssetTable)).all()
    findings = db.scalars(select(QualityFinding)).all()

    systems = {s.system_code: s for s in db.scalars(select(AssetSystem)).all()}
    grouped: dict[str, dict] = {}

    for sc in set(t.system_code for t in tables if t.system_code):
        grouped[sc] = {
            "system_code": sc,
            "system_name_cn": systems[sc].system_name_cn if sc in systems else sc,
            "table_count": 0,
            "column_count": 0,
            "findings_total": 0,
            "findings_open": 0,
        }

    for t in tables:
        sc = t.system_code or "UNKNOWN"
        if sc not in grouped:
            grouped[sc] = {"system_code": sc, "system_name_cn": sc, "table_count": 0, "column_count": 0, "findings_total": 0, "findings_open": 0}
        grouped[sc]["table_count"] += 1
        grouped[sc]["column_count"] += t.column_count or 0

    for f in findings:
        if f.status == "open":
            for sc in grouped:
                grouped[sc]["findings_open"] += 1
                grouped[sc]["findings_total"] += 1
            break
        grouped.get("UNKNOWN", {}).setdefault("findings_total", 0)
        grouped.get("UNKNOWN", {}).setdefault("findings_open", 0)

    for sc in grouped:
        grouped[sc]["findings_total"] = len([f for f in findings if f.status != "resolved"])
        grouped[sc]["findings_open"] = len([f for f in findings if f.status == "open"])

    return ApiResponse(data=sorted(grouped.values(), key=lambda x: x["table_count"], reverse=True))


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


class FindingAssign(BaseModel):
    assigned_to: str
    note: str | None = None


@router.post("/rules", summary="新建质控规则")
def create_rule(req: RuleCreate, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    existing = db.scalar(select(QualityRule).where(QualityRule.rule_code == req.rule_code))
    if existing:
        raise HTTPException(status_code=400, detail=f"规则 {req.rule_code} 已存在")
    rule = QualityRule(**req.model_dump(exclude_none=True))
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return ApiResponse(data={"id": rule.id, "rule_code": rule.rule_code})


@router.patch("/rules/{rule_id}", summary="编辑质控规则")
def patch_rule(rule_id: int, req: RulePatch, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    rule = db.get(QualityRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404)
    for k, v in req.model_dump(exclude_none=True).items():
        setattr(rule, k, v)
    db.commit()
    return ApiResponse(data={"id": rule.id, "rule_code": rule.rule_code})


@router.post("/rules/{rule_id}/enable", summary="启用/停用规则")
def toggle_rule(rule_id: int, enabled: bool = Query(True), db: Session = Depends(get_db)) -> ApiResponse[dict]:
    rule = db.get(QualityRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404)
    rule.enabled = enabled
    db.commit()
    return ApiResponse(data={"id": rule.id, "enabled": rule.enabled})


@router.delete("/rules/{rule_id}", summary="删除质控规则")
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


@router.post("/rules/{rule_id}/validate-sql", summary="校验只读 SQL 安全性")
def validate_rule_sql(rule_id: int, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    rule = db.get(QualityRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404)
    if not rule.check_sql:
        raise HTTPException(status_code=400, detail="该规则没有 check_sql")
    result = validate_sql_safety(rule.check_sql)
    return ApiResponse(data=result)


@router.post("/rules/from-template", summary="从模板生成质控规则")
def rule_from_template(req: TemplateGenerate, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    from ...services import quality_templates as tpl

    template_fn = getattr(tpl, f"template_{req.template_type}", None)
    if not template_fn:
        raise HTTPException(status_code=400, detail=f"未知模板类型: {req.template_type}")

    sql = template_fn(**req.params)
    return ApiResponse(data={"sql": sql, "template_type": req.template_type})


@router.post("/findings/{finding_id}/assign", summary="问题分派")
def assign_finding(finding_id: int, req: FindingAssign, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    f = db.get(QualityFinding, finding_id)
    if not f:
        raise HTTPException(status_code=404)
    f.assigned_to = req.assigned_to
    f.rectification_status = "assigned"
    if req.note:
        f.note = req.note
    db.commit()
    return ApiResponse(data={"id": f.id, "assigned_to": f.assigned_to, "rectification_status": f.rectification_status})


@router.post("/findings/{finding_id}/recheck", summary="单问题复核")
def recheck_finding(finding_id: int, status: str = Query(..., description="confirmed/fixed/ignored"), db: Session = Depends(get_db)) -> ApiResponse[dict]:
    if status not in ("confirmed", "fixed", "ignored", "rechecked"):
        raise HTTPException(status_code=400, detail="status 必须为 confirmed/fixed/ignored/rechecked")
    f = db.get(QualityFinding, finding_id)
    if not f:
        raise HTTPException(status_code=404)
    f.rectification_status = "rechecked" if status == "rechecked" else status
    f.confirmed_by = "reviewer"
    f.resolved_at = datetime.now(timezone.utc)
    db.commit()
    return ApiResponse(data={"id": f.id, "rectification_status": f.rectification_status})


@router.get("/metrics", summary="质量看板指标")
def quality_metrics(
    system_code: str | None = Query(None),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    rules = db.scalars(select(QualityRule).where(QualityRule.enabled == True)).all()
    total_rules = len(rules)
    sql_rules = len([r for r in rules if r.execution_mode == "sql_template"])

    count_stmt = select(func.count(QualityFinding.id))
    open_stmt = select(func.count(QualityFinding.id)).where(QualityFinding.status == "open")
    resolved_stmt = select(func.count(QualityFinding.id)).where(QualityFinding.status == "resolved")
    if system_code:
        count_stmt = count_stmt.where(QualityFinding.system_code == system_code)
        open_stmt = open_stmt.where(QualityFinding.system_code == system_code)
        resolved_stmt = resolved_stmt.where(QualityFinding.system_code == system_code)

    total = db.scalar(count_stmt) or 0
    open_count = db.scalar(open_stmt) or 0
    resolved_count = db.scalar(resolved_stmt) or 0
    pass_rate = round((resolved_count / total * 100) if total > 0 else 100, 1)

    top_stmt = select(QualityFinding.table_name, func.count(QualityFinding.id).label("cnt"))
    if system_code:
        top_stmt = top_stmt.where(QualityFinding.system_code == system_code)
    top_rows = db.execute(
        top_stmt.group_by(QualityFinding.table_name)
        .order_by(func.count(QualityFinding.id).desc())
        .limit(5)
    ).all()
    top_tables = [{"table": r[0] or r[1], "count": r[1]} for r in top_rows]

    cat_counts: dict = {}
    for r in rules:
        cat = r.rule_category or "other"
        cat_counts[cat] = cat_counts.get(cat, 0) + 1

    return ApiResponse(data={
        "total_rules": total_rules,
        "enabled_rules": total_rules,
        "sql_rules": sql_rules,
        "total_findings": total,
        "open_findings": open_count,
        "resolved_findings": resolved_count,
        "pass_rate": pass_rate,
        "rule_categories": cat_counts,
        "top_tables": top_tables,
    })
