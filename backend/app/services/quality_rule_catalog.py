"""Common quality-rule catalog and suggestion generator.

Seeds stay metadata_only and enabled. SQL suggestions stay disabled.
No source database is queried here.
"""
from __future__ import annotations

import re
from typing import Any

from typing import TYPE_CHECKING

from . import quality_templates as tpl

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_$#]*$")
SPLIT_COLS = re.compile(r"[,;+|]+")

DATE_PAIRS = (
    ("ADMISSION_DATE_TIME", "DISCHARGE_DATE_TIME"),
    ("ADMISSION_DATE", "DISCHARGE_DATE"),
    ("START_DATE_TIME", "END_DATE_TIME"),
    ("OPERATING_DATE", "END_DATE_TIME"),
    ("REQUESTED_DATE_TIME", "RESULTS_RPT_DATE_TIME"),
    ("TEST_DATE_TIME", "RESULTS_RPT_DATE_TIME"),
    ("SCHEDULED_DATE_TIME", "END_DATE_TIME"),
)

CONFIRMED_STATUSES = (
    "verified",
    "approved",
    "manual_reviewed",
    "sample_pass",
    "sample_verified",
    "user_confirmed_sync",
    "user_confirmed_mapping",
)

EXTRA_SEED_RULES: list[dict[str, Any]] = [
    {
        "rule_code": "TABLE_NO_PK",
        "rule_name": "表缺少主键定义",
        "rule_type": "completeness",
        "rule_category": "COMPLETE",
        "check_scope": "TABLE_INNER",
        "target_type": "table",
        "execution_mode": "metadata_only",
        "constraint_level": "SOFT",
        "description": "资产目录中表未登记主键，无法做唯一性检查。",
        "threshold_config": {},
        "enabled": True,
    },
    {
        "rule_code": "REL_NO_JOIN_COLUMNS",
        "rule_name": "关系缺少关联字段",
        "rule_type": "completeness",
        "rule_category": "RELATION",
        "check_scope": "TABLE_RELATION",
        "target_type": "relation",
        "execution_mode": "metadata_only",
        "constraint_level": "SOFT",
        "description": "关系两端字段为空，只能当线索，不能当外键校验。",
        "threshold_config": {},
        "enabled": True,
    },
    {
        "rule_code": "META_TABLE_IDENTITY_COMPLETE",
        "rule_name": "表物理身份不完整",
        "rule_type": "completeness",
        "rule_category": "COMPLETE",
        "check_scope": "TABLE_INNER",
        "target_type": "table",
        "execution_mode": "metadata_only",
        "constraint_level": "HARD",
        "description": "表缺少 system/source/schema/table 物理键，无法稳定归属。",
        "threshold_config": {},
        "enabled": True,
    },
    {
        "rule_code": "META_REL_LAYER_STATUS_MATCH",
        "rule_name": "关系层级与验证状态不一致",
        "rule_type": "consistency",
        "rule_category": "ACCURACY",
        "check_scope": "TABLE_RELATION",
        "target_type": "relation",
        "execution_mode": "metadata_only",
        "constraint_level": "SOFT",
        "description": "已验证关系仍标 candidate，或未验证关系标 formal。",
        "threshold_config": {},
        "enabled": True,
    },
    {
        "rule_code": "META_REL_ENDPOINT_RESOLVABLE",
        "rule_name": "关系端点无法解析",
        "rule_type": "completeness",
        "rule_category": "RELATION",
        "check_scope": "TABLE_RELATION",
        "target_type": "relation",
        "execution_mode": "metadata_only",
        "constraint_level": "SOFT",
        "description": "关系缺少来源/目标表名，或两端系统归属不完整。",
        "threshold_config": {},
        "enabled": True,
    },
]

COMMON_CATALOG_RULES: list[dict[str, Any]] = [
    {
        "rule_code": "R_COMMON_001",
        "rule_name": "主键/业务键唯一性",
        "rule_category": "UNIQUE",
        "check_scope": "TABLE_INNER",
        "constraint_level": "HARD",
        "business_domain": "通用",
        "rule_type": "primary_key_duplicate",
        "execution_mode": "sql_template",
        "error_level": "major",
        "description": "同一主键或业务键出现多行。自动生成建议见 AUTO_PK_*。",
        "enabled": False,
        "sample_limit": 20,
        "version": 1,
    },
    {
        "rule_code": "R_COMMON_002",
        "rule_name": "必填字段缺失",
        "rule_category": "COMPLETE",
        "check_scope": "TABLE_INNER",
        "constraint_level": "HARD",
        "business_domain": "通用",
        "rule_type": "required_empty",
        "execution_mode": "sql_template",
        "error_level": "major",
        "description": "主键或必填字段为空。自动生成建议见 AUTO_NULL_*。",
        "enabled": False,
        "sample_limit": 20,
        "version": 1,
    },
    {
        "rule_code": "R_COMMON_003",
        "rule_name": "字段长度超长",
        "rule_category": "STANDARD",
        "check_scope": "TABLE_INNER",
        "constraint_level": "SOFT",
        "business_domain": "通用",
        "rule_type": "length_overflow",
        "execution_mode": "sql_template",
        "error_level": "minor",
        "description": "字段值超过元数据登记长度。",
        "enabled": False,
        "sample_limit": 20,
        "version": 1,
    },
    {
        "rule_code": "R_COMMON_004",
        "rule_name": "值域代码合法性",
        "rule_category": "STANDARD",
        "check_scope": "TABLE_INNER",
        "constraint_level": "HARD",
        "business_domain": "通用",
        "rule_type": "value_domain_invalid",
        "execution_mode": "sql_template",
        "error_level": "major",
        "description": "代码字段不在约定值域内，如性别、就诊类型。",
        "enabled": False,
        "sample_limit": 20,
        "version": 1,
    },
    {
        "rule_code": "R_COMMON_005",
        "rule_name": "时间先后一致性",
        "rule_category": "ACCURACY",
        "check_scope": "BUSINESS_LOGIC",
        "constraint_level": "HARD",
        "business_domain": "通用",
        "rule_type": "time_logic_error",
        "execution_mode": "sql_template",
        "error_level": "major",
        "description": "开始时间晚于结束时间。自动生成建议见 AUTO_TIME_*。",
        "enabled": False,
        "sample_limit": 20,
        "version": 1,
    },
    {
        "rule_code": "R_COMMON_006",
        "rule_name": "子表孤儿记录",
        "rule_category": "RELATION",
        "check_scope": "TABLE_RELATION",
        "constraint_level": "HARD",
        "business_domain": "通用",
        "rule_type": "orphan_record",
        "execution_mode": "sql_template",
        "error_level": "major",
        "description": "子表键在父表找不到对应行。自动生成建议见 AUTO_REL_*。",
        "enabled": False,
        "sample_limit": 20,
        "version": 1,
    },
    {
        "rule_code": "R_INP_001",
        "rule_name": "入院时间不能晚于出院时间",
        "rule_category": "ACCURACY",
        "check_scope": "BUSINESS_LOGIC",
        "constraint_level": "HARD",
        "business_domain": "住院",
        "rule_type": "time_logic_error",
        "execution_mode": "sql_template",
        "error_level": "major",
        "description": "仅对入院、出院时间均非空的住院记录检查。",
        "enabled": False,
        "sample_limit": 20,
        "version": 1,
    },
    {
        "rule_code": "R_INP_002",
        "rule_name": "住院唯一标识不能为空",
        "rule_category": "COMPLETE",
        "check_scope": "TABLE_INNER",
        "constraint_level": "HARD",
        "business_domain": "住院",
        "rule_type": "required_empty",
        "execution_mode": "sql_template",
        "error_level": "major",
        "description": "住院记录 PATIENT_ID+VISIT_ID 任一为空。",
        "enabled": False,
        "sample_limit": 20,
        "version": 1,
    },
    {
        "rule_code": "R_DIAG_001",
        "rule_name": "主要诊断只能有一条",
        "rule_category": "UNIQUE",
        "check_scope": "TABLE_INNER",
        "constraint_level": "HARD",
        "business_domain": "诊断",
        "rule_type": "primary_key_duplicate",
        "execution_mode": "sql_template",
        "error_level": "major",
        "description": "同一就诊下主要诊断多于一条。",
        "enabled": False,
        "sample_limit": 20,
        "version": 1,
    },
    {
        "rule_code": "R_ORDER_001",
        "rule_name": "医嘱必须关联住院就诊",
        "rule_category": "RELATION",
        "check_scope": "TABLE_RELATION",
        "constraint_level": "HARD",
        "business_domain": "医嘱",
        "rule_type": "orphan_record",
        "execution_mode": "sql_template",
        "error_level": "major",
        "description": "医嘱 PATIENT_ID+VISIT_ID 应对应有效住院就诊。",
        "enabled": False,
        "sample_limit": 20,
        "version": 1,
    },
    {
        "rule_code": "R_FEE_001",
        "rule_name": "费用明细必须关联就诊",
        "rule_category": "RELATION",
        "check_scope": "TABLE_RELATION",
        "constraint_level": "HARD",
        "business_domain": "费用",
        "rule_type": "orphan_record",
        "execution_mode": "sql_template",
        "error_level": "major",
        "description": "费用明细应对应有效住院或门诊就诊。",
        "enabled": False,
        "sample_limit": 20,
        "version": 1,
    },
    {
        "rule_code": "R_LIS_001",
        "rule_name": "检验报告必须关联检验申请",
        "rule_category": "RELATION",
        "check_scope": "TABLE_RELATION",
        "constraint_level": "HARD",
        "business_domain": "检验",
        "rule_type": "orphan_record",
        "execution_mode": "sql_template",
        "error_level": "major",
        "description": "检验结果经 TEST_NO 挂检验主表，禁止无键全表扫。",
        "enabled": False,
        "sample_limit": 20,
        "version": 1,
    },
    {
        "rule_code": "R_PACS_001",
        "rule_name": "检查报告必须关联检查申请",
        "rule_category": "RELATION",
        "check_scope": "TABLE_RELATION",
        "constraint_level": "HARD",
        "business_domain": "检查",
        "rule_type": "orphan_record",
        "execution_mode": "sql_template",
        "error_level": "major",
        "description": "检查报告经 EXAM_NO 挂检查主表，禁止按患者直接关联。",
        "enabled": False,
        "sample_limit": 20,
        "version": 1,
    },
    {
        "rule_code": "R_OP_001",
        "rule_name": "手术开始时间不能晚于结束时间",
        "rule_category": "ACCURACY",
        "check_scope": "TABLE_INNER",
        "constraint_level": "HARD",
        "business_domain": "手术",
        "rule_type": "time_logic_error",
        "execution_mode": "sql_template",
        "error_level": "major",
        "description": "手术开始、结束时间均非空时检查先后顺序。",
        "enabled": False,
        "sample_limit": 20,
        "version": 1,
    },
]


CATEGORY_LABELS = {
    "UNIQUE": "唯一性",
    "COMPLETE": "缺失性",
    "RELATION": "关联性",
    "ACCURACY": "一致性",
    "STANDARD": "规范性",
    "CONNECTIVITY": "连通性",
}


def category_label(code: str | None) -> str:
    return CATEGORY_LABELS.get(str(code or ""), code or "-")


def metric_zh(raw: str | None) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    mapping = {
        "never_checked": "尚未做过连接检测",
        "status=not_tested": "尚未做库表抽样验证",
        "status=candidate": "仍是候选关系，未确认",
        "status=failed": "最近一次连接失败",
        "status=connected": "最近一次连接成功",
        "domain=empty": "未归入业务域",
    }
    if text in mapping:
        return mapping[text]
    if text.startswith("status="):
        return f"当前状态：{text.split('=', 1)[1]}"
    missing = re.search(r"missing\s*=\s*(\d+).*rate\s*=\s*([0-9.]+)%", text, re.I)
    if missing:
        return f"缺少中文名 {int(missing.group(1)):,} 个（{missing.group(2)}%）"
    rate = re.search(r"null_comment_rate\s*=\s*([0-9.]+)%", text, re.I)
    if rate:
        return f"无注释比例 {rate.group(1)}%"
    total = re.search(r"total\s*=\s*(\d+)", text, re.I)
    if total and "=" in text and "," not in text:
        return f"共 {int(total.group(1)):,} 项"
    if re.fullmatch(r"[A-Za-z0-9_.=%-]+", text):
        return ""
    return text


def finding_target_display(
    finding: Any,
    *,
    source_names: dict[str, str] | None = None,
    table_names: dict[tuple[str, str], str] | None = None,
) -> str:
    source_names = source_names or {}
    table_names = table_names or {}
    schema = getattr(finding, "schema_name", None) or getattr(finding, "namespace_name", None)
    table = getattr(finding, "table_name", None)
    if table:
        cn = table_names.get((str(schema or "").upper(), str(table).upper()))
        return cn or (".".join(part for part in (schema, table) if part))
    source_code = getattr(finding, "source_code", None)
    if source_code and source_names.get(source_code):
        return source_names[source_code]
    ref = str(getattr(finding, "target_ref", None) or "").strip()
    if ref in source_names:
        return source_names[ref]
    if ref.startswith("共"):
        return ref
    if "." in ref and " " not in ref and not ref.startswith("relation:"):
        schema_name, table_name = ref.split(".", 1)
        table_name = table_name.split()[0]
        cn = table_names.get((schema_name.upper(), table_name.upper()))
        return cn or ref
    return ref or "-"


def finding_problem(
    finding: Any,
    rule: Any | None = None,
    *,
    source_names: dict[str, str] | None = None,
    table_names: dict[tuple[str, str], str] | None = None,
) -> str:
    title = (getattr(rule, "rule_name", None) if rule else None) or "质量问题"
    target = finding_target_display(finding, source_names=source_names, table_names=table_names)
    detail = metric_zh(getattr(finding, "metric_value", None))
    if target.startswith("共"):
        return f"{title}：{target}"
    if target and target != "-":
        return f"{title}：{target}" + (f"。{detail}" if detail else "")
    return title + (f"：{detail}" if detail else "")


def is_safe_executable_sql_rule(rule: Any) -> bool:
    sql = str(getattr(rule, "check_sql", None) or "").strip()
    if not sql:
        return False
    table = str(getattr(rule, "target_table", None) or "")
    if tpl.is_large_table_unbounded_forbidden(table):
        return False
    upper = sql.upper()
    if any(name in upper for name in ("LAB_RESULT", "INP_BILL_DETAIL")):
        return False
    return True


def enable_catalog_rules(db: "Session", minimum: int = 200) -> dict[str, Any]:
    from sqlalchemy import select

    from ..models.quality import QualityRule

    rules = list(db.scalars(select(QualityRule).order_by(QualityRule.rule_category, QualityRule.rule_code)).all())
    already = sum(1 for rule in rules if rule.enabled is True)
    changed: list[str] = []

    def _turn_on(rule: Any) -> None:
        if rule.enabled is True:
            return
        rule.enabled = True
        changed.append(rule.rule_code)

    retired = {"SOURCE_METADATA_STALE"}
    for rule in rules:
        if rule.rule_code in retired:
            if rule.enabled is True:
                rule.enabled = False
            continue
        if (rule.execution_mode or "metadata_only") == "metadata_only":
            _turn_on(rule)

    buckets = {"COMPLETE": [], "RELATION": [], "ACCURACY": [], "UNIQUE": [], "STANDARD": [], "other": []}
    for rule in rules:
        if rule.enabled is True:
            continue
        if not is_safe_executable_sql_rule(rule):
            continue
        buckets.get(rule.rule_category or "other", buckets["other"]).append(rule)

    enabled_now = sum(1 for rule in rules if rule.enabled is True)
    for key in ("COMPLETE", "RELATION", "ACCURACY", "UNIQUE", "STANDARD", "other"):
        for rule in buckets[key]:
            if enabled_now >= minimum:
                break
            _turn_on(rule)
            enabled_now += 1
        if enabled_now >= minimum:
            break

    db.commit()
    return {
        "enabled": enabled_now,
        "already": already,
        "changed": len(changed),
        "rule_codes": changed,
    }


def all_seed_rules(base_seed: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    merged: list[dict[str, Any]] = []
    for item in [*base_seed, *EXTRA_SEED_RULES, *COMMON_CATALOG_RULES]:
        code = item.get("rule_code")
        if not code or code in seen:
            continue
        seen.add(code)
        merged.append(item)
    return merged


def split_columns(raw: str | None) -> list[str]:
    return [part.strip() for part in SPLIT_COLS.split(str(raw or "")) if part.strip()]


def safe_identifiers(names: list[str]) -> bool:
    return bool(names) and all(IDENTIFIER.fullmatch(name) for name in names)


def unique_fields_for_table(table_name: str | None, pk: str | None) -> list[str]:
    bare = (table_name or "").split(".")[-1].upper()
    if bare in tpl.CORE_UNIQUE_KEYS:
        return list(tpl.CORE_UNIQUE_KEYS[bare])
    return split_columns(pk)


def rule_code_token(*parts: str) -> str:
    text = "_".join(str(part or "ASSET") for part in parts).upper().replace("-", "_")
    return re.sub(r"[^A-Z0-9_]", "_", text)[:240]


def _exists(db: "Session", code: str) -> bool:
    from sqlalchemy import select

    from ..models.quality import QualityRule

    return db.scalar(select(QualityRule.id).where(QualityRule.rule_code == code)) is not None


def _add_rule(db: "Session", created: list[str], **kwargs: Any) -> None:
    from ..models.quality import QualityRule

    code = kwargs["rule_code"]
    if _exists(db, code):
        return
    kwargs.setdefault("enabled", False)
    kwargs.setdefault("constraint_level", "WARN")
    kwargs.setdefault("rule_type", "metadata_generated")
    kwargs.setdefault("error_level", "major")
    db.add(QualityRule(**kwargs))
    created.append(code)


def generate_rule_suggestions(
    db: "Session",
    *,
    system_code: str | None = None,
    source_code: str | None = None,
    limit: int = 200,
) -> dict[str, Any]:
    from sqlalchemy import select

    from ..models.asset import AssetColumn, AssetRelation, AssetTable
    from ..models.quality import QualityRule

    created: list[str] = []
    skipped = 0

    tables_stmt = select(AssetTable).where(AssetTable.pk.is_not(None))
    if system_code:
        tables_stmt = tables_stmt.where(AssetTable.system_code == system_code)
    if source_code:
        tables_stmt = tables_stmt.where(AssetTable.source_code == source_code)
    tables = list(
        db.scalars(
            tables_stmt.order_by(AssetTable.system_code, AssetTable.schema_name, AssetTable.table_name).limit(limit)
        ).all()
    )

    for table in tables:
        if len(created) >= limit:
            break
        fields = unique_fields_for_table(table.table_name, table.pk)
        if not safe_identifiers(fields) or not IDENTIFIER.fullmatch(table.table_name or ""):
            continue
        schema = table.schema_name or table.namespace_name
        table_ref = ".".join(x for x in (schema, table.table_name) if x)
        if not table_ref:
            continue
        display = table.table_name_cn or table.table_name
        if tpl.is_large_table_unbounded_forbidden(table.table_name or ""):
            skipped += 1
        else:
            code = rule_code_token("AUTO_PK", table.system_code, schema or "PUBLIC", table.table_name)
            if _exists(db, code):
                skipped += 1
            else:
                _add_rule(
                    db,
                    created,
                    rule_code=code,
                    rule_name=f"{display} 主键唯一性",
                    rule_category="UNIQUE",
                    check_scope="TABLE_INNER",
                    system_code=table.system_code,
                    source_code=table.source_code,
                    namespace_name=schema,
                    target_table=table.table_name,
                    target_field=",".join(fields),
                    execution_mode="sql_template",
                    check_sql=tpl.template_unique_pk(table.table_name or "", ",".join(fields), schema),
                    error_condition="ERROR_CNT > 0",
                    description="依据资产主键或源端核实组合键生成；启用前需复核方言与大表限窗。",
                    remark="auto_generated_from_asset_pk",
                )
        null_code = rule_code_token("AUTO_NULL", table.system_code, schema or "PUBLIC", table.table_name)
        if _exists(db, null_code):
            skipped += 1
        else:
            _add_rule(
                db,
                created,
                rule_code=null_code,
                rule_name=f"{display} 主键缺失",
                rule_category="COMPLETE",
                check_scope="TABLE_INNER",
                system_code=table.system_code,
                source_code=table.source_code,
                namespace_name=schema,
                target_table=table.table_name,
                target_field=",".join(fields),
                execution_mode="sql_template",
                check_sql=tpl.template_complete_required_any(table.table_name or "", fields, schema),
                error_condition="ERROR_CNT > 0",
                description="主键任一字段为空即记缺失。启用前需确认源端空值口径。",
                remark="auto_generated_from_required_pk",
            )

    column_index: dict[tuple[str, str], set[str]] = {}
    col_stmt = select(AssetColumn.schema_name, AssetColumn.table_name, AssetColumn.column_name)
    if system_code:
        col_stmt = col_stmt.where(AssetColumn.system_code == system_code)
    for schema_name, table_name, column_name in db.execute(col_stmt).all():
        key = ((schema_name or "").upper(), (table_name or "").upper())
        column_index.setdefault(key, set()).add((column_name or "").upper())

    for table in tables:
        if len(created) >= limit:
            break
        schema = table.schema_name or table.namespace_name
        have = column_index.get(((schema or "").upper(), (table.table_name or "").upper()), set())
        if not have:
            continue
        for start, end in DATE_PAIRS:
            if start not in have or end not in have:
                continue
            code = rule_code_token("AUTO_TIME", table.system_code, schema or "PUBLIC", table.table_name, start, end)
            if _exists(db, code):
                skipped += 1
                continue
            display = table.table_name_cn or table.table_name
            _add_rule(
                db,
                created,
                rule_code=code,
                rule_name=f"{display} {start}不晚于{end}",
                rule_category="ACCURACY",
                check_scope="BUSINESS_LOGIC",
                system_code=table.system_code,
                source_code=table.source_code,
                namespace_name=schema,
                target_table=table.table_name,
                target_field=f"{start},{end}",
                execution_mode="sql_template",
                check_sql=tpl.template_accuracy_time(start, end, table.table_name or "", schema),
                error_condition="ERROR_CNT > 0",
                description="两端时间均非空时检查先后顺序，不把空值当错误。",
                remark="auto_generated_from_date_pair",
            )
            break

    relations_stmt = select(AssetRelation).where(
        AssetRelation.validation_status.in_(CONFIRMED_STATUSES),
    )
    if source_code:
        relations_stmt = relations_stmt.where(AssetRelation.from_source_code == source_code)
    for relation in db.scalars(relations_stmt.limit(limit)).all():
        if len(created) >= limit:
            break
        from_fields = split_columns(relation.from_columns)
        to_fields = split_columns(relation.to_columns)
        if len(from_fields) != len(to_fields) or not from_fields or not safe_identifiers([*from_fields, *to_fields]):
            continue
        if (relation.from_source_code or "") != (relation.to_source_code or ""):
            continue
        child = relation.from_table or ""
        parent = relation.to_table or ""
        if not child or not parent:
            continue
        child_name = child.split(".")[-1]
        parent_name = parent.split(".")[-1]
        if not IDENTIFIER.fullmatch(child_name) or not IDENTIFIER.fullmatch(parent_name):
            continue
        if tpl.is_large_table_unbounded_forbidden(child_name):
            skipped += 1
            continue
        code = f"AUTO_REL_{relation.id}"
        if _exists(db, code):
            skipped += 1
            continue
        child_schema = relation.from_schema_name or (child.split(".")[0] if "." in child else None)
        parent_schema = relation.to_schema_name or (parent.split(".")[0] if "." in parent else None)
        _add_rule(
            db,
            created,
            rule_code=code,
            rule_name=f"{child_name} 关联 {parent_name} 孤儿记录",
            rule_category="RELATION",
            check_scope="TABLE_RELATION",
            system_code=relation.from_system_code,
            source_code=relation.from_source_code,
            namespace_name=child_schema,
            target_table=child_name,
            target_field=",".join(from_fields),
            related_table=parent_name,
            related_field=",".join(to_fields),
            execution_mode="sql_template",
            check_sql=tpl.template_relation_orphan_composite(
                child_name,
                from_fields,
                parent_name,
                to_fields,
                child_schema,
                parent_schema,
            ),
            error_condition="ERROR_CNT > 0",
            description="依据已确认同源关系生成；跨系统关系不生成可执行 SQL。",
            remark="auto_generated_from_verified_relation",
        )

    db.commit()
    return {"created": len(created), "skipped": skipped, "rule_codes": created}
