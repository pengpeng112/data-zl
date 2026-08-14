"""Build a desensitized platform-catalog brief for the hospital LLM.

Only asset-schema aggregates are included. No HIS/ODS/JHEMR connection.
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models.asset import AssetRelation
from ..models.quality import QualityFinding, QualityRule
from .quality_rule_catalog import finding_problem
from .relation_metrics import parse_relation_metrics, scene_label, classify_relation_scene

RULE_CATEGORY_ZH = {
    "UNIQUE": "唯一性",
    "COMPLETE": "缺失性",
    "RELATION": "关联性",
    "ACCURACY": "一致性",
    "STANDARD": "规范性",
    "CONNECTIVITY": "连通性",
}

def _cat(code: str | None) -> str:
    return RULE_CATEGORY_ZH.get(str(code or "").upper(), code or "未分类")


def build_governance_brief(db: Session) -> str:
    rules = list(db.scalars(select(QualityRule).order_by(QualityRule.rule_category, QualityRule.rule_code)).all())
    enabled = [row for row in rules if row.enabled]
    open_findings = list(db.scalars(
        select(QualityFinding)
        .where(func.coalesce(QualityFinding.status, "open").in_(["open", "assigned", "acknowledged"]))
        .order_by(QualityFinding.severity.desc(), QualityFinding.id.desc())
        .limit(25)
    ).all())
    rule_map = {row.rule_code: row for row in rules}
    finding_counts = list(db.execute(
        select(QualityFinding.rule_code, func.count())
        .where(func.coalesce(QualityFinding.status, "open") != "ignored")
        .group_by(QualityFinding.rule_code)
        .order_by(func.count().desc())
        .limit(15)
    ).all())
    formal_rels = list(db.scalars(
        select(AssetRelation)
        .where(func.lower(func.coalesce(AssetRelation.relation_layer, "")) == "formal")
        .order_by(AssetRelation.rel_id.asc().nullslast())
        .limit(20)
    ).all())

    lines = [
        "你是医院数据资产质控助手。下面全部来自【数据资产平台库】的规则、问题和关系登记，不是 HIS/ODS/嘉和业务库。",
        "禁止要求或假设直连业务库；禁止编造患者明细；禁止建议执行 INSERT/UPDATE/DELETE/DDL。",
        "请按质控规则写一份给人看的中文报告，不要只堆英文规则代码。",
        "报告必须包含：",
        "1. 一句话总判断（现在主要风险是什么）",
        "2. 规则怎么理解：每条提到的规则用中文解释它在查什么、什么算噪音、什么要处理",
        "3. 按优先级列出建议（先关系拆分/补键，再目录补全，最后才是可忽略噪音）",
        "4. 不确定就写待复核，不要假装已经验过业务库",
        "summary 用 Markdown，标题用 ##，列表用 -，加粗用 **。",
        "",
        "【启用中的质控规则】",
    ]
    for rule in enabled[:40]:
        lines.append(
            f"- {rule.rule_code} / {rule.rule_name or '-'} / {_cat(rule.rule_category)}："
            f"{(rule.description or '无说明').strip()}"
        )
    disabled_n = sum(1 for row in rules if not row.enabled)
    lines.append(f"- 另有未启用规则 {disabled_n} 条，默认当作噪音，不要当成待整改。")
    lines.append("")
    lines.append("【未关闭问题数量】")
    for code, count in finding_counts:
        rule = rule_map.get(code)
        lines.append(f"- {code}（{getattr(rule, 'rule_name', None) or '未命名'}）n={int(count)}")
    lines.append("")
    lines.append("【近期待处理问题样本】")
    for row in open_findings:
        rule = rule_map.get(row.rule_code)
        problem = finding_problem(row, rule)
        obj = ".".join(part for part in (row.schema_name, row.table_name, row.column_name) if part) or (row.target_ref or "对象未落表")
        lines.append(f"- #{row.id} {problem}；对象={obj}；程度={row.severity or '-'}")
    lines.append("")
    lines.append("【平台已登记正式关系（含命中率，仍是平台库记录，不是现场连业务库）】")
    for rel in formal_rels:
        parsed = parse_relation_metrics(rel.validation_metrics)
        scene = scene_label(classify_relation_scene(
            rel_id=rel.rel_id, from_table=rel.from_table, to_table=rel.to_table,
            from_columns=rel.from_columns, to_columns=rel.to_columns,
            join_condition=rel.join_condition, note=rel.note,
            validation_note=rel.validation_note, domain=rel.domain,
        ))
        hit = f"{parsed['hit_rate']*100:.2f}%" if parsed.get("hit_rate") is not None else "无命中率"
        lines.append(
            f"- {rel.rel_id} {rel.from_table} → {rel.to_table} 键={rel.from_columns or '-'} "
            f"状态={rel.validation_status} 命中={hit} 场景={scene or '-'}"
        )
    return "\n".join(lines)
