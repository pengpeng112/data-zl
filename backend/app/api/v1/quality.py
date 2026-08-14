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
from ...models.asset_system import AssetDataSource, AssetSystem
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
from ...services.quality_attribution import resolve_finding_location
from ...services.quality_rule_catalog import (
    all_seed_rules,
    finding_problem,
    finding_target_display,
    generate_rule_suggestions,
)

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
        "description": "已停用：采集超过 7 天未更新不作为质量问题。",
        "threshold_config": {"max_days": 7},
        "enabled": False,
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
                        system_code=r.from_system_code,
                        source_code=r.from_source_code,
                        namespace_name=r.from_namespace_name or r.from_schema_name,
                        schema_name=r.from_schema_name,
                        table_name=r.from_table_name or r.from_table,
                        column_name=r.from_columns,
                        severity=sev,
                        metric_value=f"orphan_rate={orphan_rate}%",
                        detail={
                            "orphan_rate": orphan_rate,
                            "metrics_raw": metrics,
                            "threshold": threshold["max_orphan_rate"],
                            "related_schema": r.to_schema_name,
                            "related_table": r.to_table_name or r.to_table,
                            "related_columns": r.to_columns,
                        },
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
            system_code=r.from_system_code,
            source_code=r.from_source_code,
            namespace_name=r.from_namespace_name or r.from_schema_name,
            schema_name=r.from_schema_name,
            table_name=r.from_table_name or r.from_table,
            column_name=r.from_columns,
            severity="minor",
            metric_value=f"status={r.validation_status or 'empty'}",
            detail={
                "related_schema": r.to_schema_name,
                "related_table": r.to_table_name or r.to_table,
                "related_columns": r.to_columns,
            },
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


def _summary_finding(rule_code: str, target_type: str, count: int, label: str, extra: dict | None = None) -> list[QualityFinding]:
    if count <= 0:
        return []
    return [
        QualityFinding(
            rule_code=rule_code,
            target_type=target_type,
            target_ref=f"共 {count} {label}",
            severity="minor",
            metric_value=f"total={count}",
            error_cnt=count,
            detail=extra or {},
        )
    ]


def _run_rule_table_no_pk(db: Session) -> list[QualityFinding]:
    count = db.scalar(
        select(func.count(AssetTable.id)).where(
            (AssetTable.pk.is_(None)) | (AssetTable.pk == "")
        )
    ) or 0
    return _summary_finding("TABLE_NO_PK", "table", int(count), "张表未登记主键")


def _run_rule_rel_no_join_columns(db: Session) -> list[QualityFinding]:
    count = db.scalar(
        select(func.count(AssetRelation.id)).where(
            (func.coalesce(AssetRelation.from_columns, "") == "")
            & (func.coalesce(AssetRelation.to_columns, "") == "")
        )
    ) or 0
    return _summary_finding("REL_NO_JOIN_COLUMNS", "relation", int(count), "条关系缺少关联字段")


def _run_rule_meta_table_identity(db: Session) -> list[QualityFinding]:
    count = db.scalar(
        select(func.count(AssetTable.id)).where(
            (AssetTable.system_code.is_(None))
            | (AssetTable.system_code == "")
            | (AssetTable.source_code.is_(None))
            | (AssetTable.source_code == "")
            | (AssetTable.table_name.is_(None))
            | (AssetTable.table_name == "")
        )
    ) or 0
    return _summary_finding("META_TABLE_IDENTITY_COMPLETE", "table", int(count), "张表物理身份不完整")


def _run_rule_meta_rel_layer_status(db: Session) -> list[QualityFinding]:
    rows = db.scalars(select(AssetRelation)).all()
    bad = 0
    for row in rows:
        status = (row.validation_status or "").lower()
        layer = (row.relation_layer or "").lower()
        confirmed = status in {"verified", "approved", "manual_reviewed", "sample_pass", "sample_verified"}
        if confirmed and layer == "candidate":
            bad += 1
        elif status in {"candidate", "not_tested"} and layer == "formal":
            bad += 1
    return _summary_finding("META_REL_LAYER_STATUS_MATCH", "relation", bad, "条关系层级与状态不一致")


def _run_rule_meta_rel_endpoint(db: Session) -> list[QualityFinding]:
    count = db.scalar(
        select(func.count(AssetRelation.id)).where(
            (AssetRelation.from_table.is_(None))
            | (AssetRelation.from_table == "")
            | (AssetRelation.to_table.is_(None))
            | (AssetRelation.to_table == "")
        )
    ) or 0
    return _summary_finding("META_REL_ENDPOINT_RESOLVABLE", "relation", int(count), "条关系端点无法解析")


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
    "TABLE_NO_PK": _run_rule_table_no_pk,
    "REL_NO_JOIN_COLUMNS": _run_rule_rel_no_join_columns,
    "META_TABLE_IDENTITY_COMPLETE": _run_rule_meta_table_identity,
    "META_REL_LAYER_STATUS_MATCH": _run_rule_meta_rel_layer_status,
    "META_REL_ENDPOINT_RESOLVABLE": _run_rule_meta_rel_endpoint,
}


def _retire_unused_rules(db: Session) -> None:
    """Keep catalog rows but stop treating retired rules as open problems."""
    retired = {"SOURCE_METADATA_STALE"}
    for code in retired:
        rule = db.scalar(select(QualityRule).where(QualityRule.rule_code == code))
        if rule and rule.enabled is not False:
            rule.enabled = False
        for finding in db.scalars(
            select(QualityFinding).where(
                QualityFinding.rule_code == code,
                QualityFinding.status.in_(["open", "acknowledged", "assigned"]),
            )
        ).all():
            finding.status = "ignored"
            finding.note = "用户确认：采集超过7天未更新不作为质量问题"
            finding.resolved_at = datetime.now(timezone.utc)


def seed_rules(db: Session) -> None:
    """Insert missing seed rules and backfill governance fields on enabled seeds."""
    for rule_data in all_seed_rules(QUALITY_RULES_SEED):
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
    _retire_unused_rules(db)
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
            | QualityRule.target_table.ilike(like)
        )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(
            QualityRule.enabled.desc().nullslast(),
            QualityRule.rule_category,
            QualityRule.rule_code,
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    items = [QualityRuleItem.model_validate(r).model_dump() for r in rows]
    return ApiResponse(
        data={"total": total, "page": page, "page_size": page_size, "items": items}
    )


def _split_table_ref(ref: str | None) -> tuple[str, str]:
    text = str(ref or "").strip()
    if "." not in text or " " in text or text.startswith("共"):
        return "", ""
    schema_name, table_name = text.split(".", 1)
    return schema_name, table_name.split()[0]


def _source_name_map(db: Session, codes: set[str]) -> dict[str, str]:
    if not codes:
        return {}
    return {
        row.source_code: row.source_name_cn
        for row in db.scalars(select(AssetDataSource).where(AssetDataSource.source_code.in_(codes))).all()
        if row.source_code and row.source_name_cn
    }


def _system_name_map(db: Session, codes: set[str]) -> dict[str, str]:
    if not codes:
        return {}
    return {
        row.system_code: row.system_name_cn
        for row in db.scalars(select(AssetSystem).where(AssetSystem.system_code.in_(codes))).all()
        if row.system_code and row.system_name_cn
    }


def _table_name_map(db: Session, keys: set[tuple[str, str]]) -> dict[tuple[str, str], str]:
    tables = {key[1] for key in keys if key[1]}
    if not tables:
        return {}
    result: dict[tuple[str, str], str] = {}
    for row in db.scalars(select(AssetTable).where(AssetTable.table_name.in_(tables))).all():
        if not row.table_name_cn:
            continue
        result[(str(row.schema_name or "").upper(), str(row.table_name or "").upper())] = row.table_name_cn
    return result


def _relation_id(target_ref: str | None) -> int | None:
    text = str(target_ref or "")
    if "rel_id=" not in text:
        return None
    raw = text.split("rel_id=", 1)[1]
    raw = raw.split(")", 1)[0].split(",", 1)[0].strip()
    try:
        return int(raw)
    except ValueError:
        return None


def _finding_payload(
    row: QualityFinding,
    rule: QualityRule | None = None,
    *,
    source_names: dict[str, str] | None = None,
    table_names: dict[tuple[str, str], str] | None = None,
    system_names: dict[str, str] | None = None,
    relation: AssetRelation | None = None,
) -> dict:
    data = QualityFindingItem.model_validate(row).model_dump()
    data["rule_name"] = rule.rule_name if rule else None
    data["rule_category"] = rule.rule_category if rule else None
    data["rule_description"] = rule.description if rule else None
    data["problem"] = finding_problem(row, rule, source_names=source_names, table_names=table_names)
    data["target_display"] = finding_target_display(row, source_names=source_names, table_names=table_names)
    system_names = system_names or {}
    source_names = source_names or {}
    table_names = table_names or {}
    loc = resolve_finding_location(row, rule)
    data["schema_name"] = data.get("schema_name") or loc.schema_name
    data["table_name"] = data.get("table_name") or loc.table_name
    data["column_name"] = data.get("column_name") or loc.column_name
    data["related_schema"] = loc.related_schema
    data["related_table"] = loc.related_table
    data["related_field"] = loc.related_column
    if relation is not None:
        data["schema_name"] = data.get("schema_name") or relation.from_schema_name
        data["table_name"] = data.get("table_name") or relation.from_table_name or relation.from_table
        data["column_name"] = data.get("column_name") or relation.from_columns
        data["related_schema"] = data.get("related_schema") or relation.to_schema_name
        data["related_table"] = data.get("related_table") or relation.to_table_name or relation.to_table
        data["related_field"] = data.get("related_field") or relation.to_columns
    schema_key = str(data.get("schema_name") or data.get("namespace_name") or "")
    table_key = str(data.get("table_name") or "")
    data["table_name_cn"] = table_names.get((schema_key.upper(), table_key.upper())) if table_key else None
    related_table = data.get("related_table")
    if related_table:
        data["related_table_cn"] = table_names.get(
            (str(data.get("related_schema") or "").upper(), str(related_table).upper())
        )
    else:
        data["related_table_cn"] = None
    data["system_name_cn"] = system_names.get(row.system_code or "")
    data["source_name_cn"] = source_names.get(row.source_code or "") or source_names.get(row.target_ref or "")
    return data


def run_quality_check_core(
    db: Session,
    *,
    rule_codes: list[str] | None = None,
    triggered_by: str = "manual",
    include_sql: bool = False,
) -> dict:
    """Shared entry for manual API and nightly scheduler (L15)."""
    seed_rules(db)

    rules_q = select(QualityRule).where(QualityRule.enabled.is_(True))  # noqa: E712
    if rule_codes:
        rules_q = rules_q.where(QualityRule.rule_code.in_(rule_codes))
    rules = list(db.scalars(rules_q).all())
    if not include_sql:
        rules = [rule for rule in rules if (rule.execution_mode or "metadata_only") != "sql_template"]

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
    include_sql: bool = Query(False, description="是否同时执行源库 SQL 规则；默认只跑元数据规则"),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    return ApiResponse(
        data=run_quality_check_core(
            db,
            rule_codes=rule_codes,
            triggered_by="manual",
            include_sql=include_sql,
        )
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
    run_id: int | None = Query(None),
    keyword: str | None = Query(None),
    system_code: str | None = Query(None),
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
    if system_code and system_code != "UNASSIGNED":
        stmt = stmt.where(QualityFinding.system_code == system_code)
    elif system_code == "UNASSIGNED":
        stmt = stmt.where((QualityFinding.system_code.is_(None)) | (QualityFinding.system_code == "") | (QualityFinding.system_code == "UNASSIGNED"))
    if keyword:
        like = f"%{keyword}%"
        name_match = select(QualityRule.rule_code).where(QualityRule.rule_name.ilike(like))
        stmt = stmt.where(
            QualityFinding.target_ref.ilike(like)
            | QualityFinding.schema_name.ilike(like)
            | QualityFinding.namespace_name.ilike(like)
            | QualityFinding.table_name.ilike(like)
            | QualityFinding.column_name.ilike(like)
            | QualityFinding.rule_code.ilike(like)
            | QualityFinding.metric_value.ilike(like)
            | QualityFinding.rule_code.in_(name_match)
        )

    count = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(
            QualityFinding.severity.desc(),
            QualityFinding.found_at.desc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    codes = {row.rule_code for row in rows if row.rule_code}
    rule_map = {
        rule.rule_code: rule
        for rule in db.scalars(select(QualityRule).where(QualityRule.rule_code.in_(codes))).all()
    } if codes else {}
    source_codes = {row.source_code for row in rows if row.source_code}
    source_codes.update(row.target_ref for row in rows if row.target_type == "source" and row.target_ref)
    system_codes = {row.system_code for row in rows if row.system_code}
    table_keys: set[tuple[str, str]] = set()
    for row in rows:
        loc = resolve_finding_location(row, rule_map.get(row.rule_code))
        if loc.table_name:
            table_keys.add((loc.schema_name or "", loc.table_name))
        if loc.related_table:
            table_keys.add((loc.related_schema or "", loc.related_table))
    source_names = _source_name_map(db, source_codes)
    system_names = _system_name_map(db, system_codes)
    rel_ids = {rid for rid in (_relation_id(row.target_ref) for row in rows) if rid is not None}
    rel_map = {
        rel.rel_id: rel
        for rel in db.scalars(select(AssetRelation).where(AssetRelation.rel_id.in_(rel_ids))).all()
    } if rel_ids else {}
    for rel in rel_map.values():
        if rel.from_table_name or rel.from_table:
            table_keys.add((rel.from_schema_name or "", rel.from_table_name or rel.from_table))
        if rel.to_table_name or rel.to_table:
            table_keys.add((rel.to_schema_name or "", rel.to_table_name or rel.to_table))
    table_names = _table_name_map(db, table_keys)
    items = [
        _finding_payload(
            row,
            rule_map.get(row.rule_code),
            source_names=source_names,
            table_names=table_names,
            system_names=system_names,
            relation=rel_map.get(_relation_id(row.target_ref)),
        )
        for row in rows
    ]
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
    rule = db.scalar(select(QualityRule).where(QualityRule.rule_code == finding.rule_code)) if finding.rule_code else None
    return ApiResponse(data=_finding_payload(finding, rule))


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
    from ...services.asset_catalog import load_system_name_map
    from ...services.quality_attribution import build_table_system_index, infer_system_code

    tables = db.scalars(select(AssetTable)).all()
    findings = db.scalars(select(QualityFinding)).all()
    name_map = load_system_name_map(db)
    table_map, schema_map = build_table_system_index(db)
    grouped: dict[str, dict] = {}

    def _bucket(code: str | None, *, source_code: str | None = None, schema_name: str | None = None, table_name: str | None = None, target_ref: str | None = None) -> str:
        return infer_system_code(
            system_code=code,
            source_code=source_code,
            schema_name=schema_name,
            table_name=table_name,
            target_ref=target_ref,
            table_map=table_map,
            schema_map=schema_map,
        )

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
        sc = _bucket(t.system_code, source_code=t.source_code, schema_name=t.schema_name, table_name=t.table_name)
        b = _ensure(sc)
        b["table_count"] += 1
        b["column_count"] += t.column_count or 0

    for f in findings:
        sc = _bucket(
            f.system_code,
            source_code=f.source_code,
            schema_name=f.schema_name,
            table_name=f.table_name,
            target_ref=f.target_ref,
        )
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
    limit: int = Field(default=200, ge=1, le=500)


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
    return ApiResponse(data=generate_rule_suggestions(
        db,
        system_code=req.system_code,
        source_code=req.source_code,
        limit=req.limit,
    ))


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
    rules = db.scalars(select(QualityRule)).all()
    enabled_rules = [r for r in rules if r.enabled is not False]
    total_rules = len(rules)
    enabled_rule_count = len(enabled_rules)
    sql_rules = len([r for r in rules if (r.execution_mode or "") == "sql_template" or (r.check_sql or "").strip()])
    suggested_rules = len([r for r in rules if r.enabled is False])

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
            "enabled_rules": enabled_rule_count,
            "suggested_rules": suggested_rules,
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
