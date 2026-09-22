"""Relation review workflow helpers (127 S6 / 198 B5 F05).

asset_relation_reviews is the review fact table; asset_relations remains the
graph formal/candidate asset store. Approve must:
1. alias-normalize ODS HIS.* mirror names vs HIS source owner names
2. dedupe by stable business key / semantic match
3. link existing formal relations instead of promoting candidate copies
4. never auto-approve cross-system draft without evidence

198 B5 (F05/T09/T10):
- find_matching_relations 改为严格身份匹配：端点别名集合内整 token 等值 +
  完整成对列映射（集合相等，子集不算）+ 方向（LEFT/RIGHT 翻转规则，存在时才比较）。
  任一筛选字段缺失/无法成对 → 返回空列表（无证据即无匹配），不再回退同表全部关系，
  不再使用子串包含比较。
- approve_review 新建候选不再无条件 validation_status="sample_pass"（人工批准
  只改治理状态，不制造验证事实）；候选必须携带两端完整身份与完整条件，缺失可定位阻断。
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from ..models.asset import AssetRelation, AssetRelationReview
from ..services.relation_identity import (
    populate_endpoint_fields,
    split_qualified_name,
)

# ODS HIS schema mirror table → common HIS source owner prefixes (semantic alias)
_ODS_HIS_OWNER_ALIASES: dict[str, tuple[str, ...]] = {
    "INP_BILL_DETAIL": ("INPBILL", "HIS"),
    "PAT_VISIT": ("MEDREC", "HIS"),
    "PAT_MASTER_INDEX": ("MEDREC", "HIS"),
    "CLINIC_MASTER": ("OUTPADM", "HIS"),
    "LAB_TEST_MASTER": ("LAB", "HIS"),
    "LAB_RESULT": ("LAB", "HIS"),
    "EXAM_MASTER": ("EXAM", "HIS"),
    "EXAM_REPORT": ("EXAM", "HIS"),
    "DIAGNOSIS": ("MEDREC", "HIS"),
    "ORDERS": ("ORDADM", "HIS"),
    "OPERATION_MASTER": ("SURGERY", "HIS"),
}


def alias_qualified_names(qualified: str | None) -> list[str]:
    """Return self + owner-alias variants for semantic endpoint matching."""
    if not qualified:
        return []
    q = qualified.strip()
    names = {q, q.upper()}
    _, schema, table = split_qualified_name(q)
    table_u = (table or "").upper()
    schema_u = (schema or "").upper()
    if table_u in _ODS_HIS_OWNER_ALIASES:
        for owner in _ODS_HIS_OWNER_ALIASES[table_u]:
            names.add(f"{owner}.{table_u}")
            names.add(f"{owner.lower()}.{table_u}")
    if schema_u == "HIS" and table_u:
        for owner in _ODS_HIS_OWNER_ALIASES.get(table_u, ()):
            names.add(f"{owner}.{table_u}")
    # owner form → HIS mirror
    if schema_u in {"INPBILL", "MEDREC", "OUTPADM", "LAB", "EXAM", "ORDADM", "SURGERY"} and table_u:
        names.add(f"HIS.{table_u}")
    return list(names)


_COLUMN_SEPARATORS = str.maketrans({"+": ",", "|": ",", ";": ","})


def normalize_column_tokens(value: str | None) -> list[str]:
    """逗号/+/|/; 分隔的列清单 → 去空格大写 token 列表（保留顺序与配对位次）。"""
    if not value:
        return []
    raw = str(value).upper().translate(_COLUMN_SEPARATORS)
    return [t for t in (part.strip() for part in raw.split(",")) if t]


def column_pair_key(
    from_columns: str | None, to_columns: str | None
) -> Optional[frozenset[tuple[str, str]]]:
    """完整成对列映射： (from_token[i], to_token[i]) 整体成对后取集合。

    两侧任一为空或 token 数量不一致（无法整对成对）时返回 None。
    集合相等意味着子集/超集/字段不同都不算匹配（198 T09）。
    """
    from_tokens = normalize_column_tokens(from_columns)
    to_tokens = normalize_column_tokens(to_columns)
    if not from_tokens or not to_tokens or len(from_tokens) != len(to_tokens):
        return None
    return frozenset(zip(from_tokens, to_tokens))


_JOIN_TYPE_RE = re.compile(r"\b(LEFT|RIGHT|FULL|INNER)[\s_]*JOIN\b", re.IGNORECASE)
_ORACLE_PLUS_RE = re.compile(r"\(\+\)")


def detect_join_direction(condition: str | None) -> Optional[str]:
    """从条件文本提取连接方向（保留侧语义）：LEFT/RIGHT/FULL/INNER。

    仅识别显式关键字或 Oracle `(+)` 标记；无法判定返回 None（存在时才参与比较）。
    `a.x = b.x(+)` → LEFT（a 保留）；`a.x(+) = b.x` → RIGHT（b 保留）。
    """
    if not condition:
        return None
    m = _JOIN_TYPE_RE.search(condition)
    if m:
        return m.group(1).upper()
    if "(+)" in condition:
        left_text, _, right_text = condition.partition("=")
        left_plus = bool(_ORACLE_PLUS_RE.search(left_text))
        right_plus = bool(_ORACLE_PLUS_RE.search(right_text))
        if left_plus and not right_plus:
            return "RIGHT"
        if right_plus and not left_plus:
            return "LEFT"
    return None


_FLIPPED_DIRECTION = {"LEFT": "RIGHT", "RIGHT": "LEFT"}


def direction_compatible(query_type: Optional[str], row_type: Optional[str], reversed_: bool) -> bool:
    """方向比较（存在时）：INNER/FULL 与方向无关；LEFT/RIGHT 反向匹配必须翻转。"""
    if not query_type or not row_type:
        return True
    expected = _FLIPPED_DIRECTION.get(row_type, row_type) if reversed_ else row_type
    return query_type == expected


def _upper(value: str | None) -> str:
    return (value or "").strip().upper()


def _identity_ok(
    query_system: Optional[str], query_source: Optional[str],
    row_system: Optional[str], row_source: Optional[str],
) -> bool:
    """system/source 身份仅在双方均可得时比较（可得时）；缺失不外推也不默认相等。"""
    if query_system and row_system and _upper(query_system) != _upper(row_system):
        return False
    if query_source and row_source and _upper(query_source) != _upper(row_source):
        return False
    return True


def find_matching_relations(
    db: Session,
    *,
    from_table: str,
    to_table: str,
    from_columns: str | None = None,
    to_columns: str | None = None,
    from_system_code: str | None = None,
    from_source_code: str | None = None,
    to_system_code: str | None = None,
    to_source_code: str | None = None,
    join_type: str | None = None,
    join_condition: str | None = None,
) -> list[AssetRelation]:
    """严格身份匹配（198 F05/T09）。

    身份 = 两端表名（别名集合内整 token 等值）+ system/source（可得时）+
    完整成对列映射（集合相等）+ 连接方向（存在时）。任一筛选字段为空、无法成对
    或无任何匹配 → 返回空列表；不回退返回同表全部关系，不做子串包含比较。
    """
    from_aliases = {_upper(a) for a in alias_qualified_names(from_table)}
    to_aliases = {_upper(a) for a in alias_qualified_names(to_table)}
    if not from_aliases or not to_aliases:
        return []
    pairs = column_pair_key(from_columns, to_columns)
    if pairs is None:
        return []
    query_type = (join_type or "").strip().upper() or detect_join_direction(join_condition)

    def _alias_match(column, aliases: set[str]):
        return func.upper(func.coalesce(func.trim(column), "")).in_(sorted(aliases))

    stmt = select(AssetRelation).where(
        or_(
            and_(_alias_match(AssetRelation.from_table, from_aliases), _alias_match(AssetRelation.to_table, to_aliases)),
            and_(_alias_match(AssetRelation.from_table, to_aliases), _alias_match(AssetRelation.to_table, from_aliases)),
        )
    )
    rows = list(db.scalars(stmt).all())

    matches: list[AssetRelation] = []
    for r in rows:
        r_from = _upper(r.from_table)
        r_to = _upper(r.to_table)
        if r_from in from_aliases and r_to in to_aliases:
            reversed_ = False
        elif r_from in to_aliases and r_to in from_aliases:
            reversed_ = True
        else:
            continue
        row_from_tokens = normalize_column_tokens(r.from_columns)
        row_to_tokens = normalize_column_tokens(r.to_columns)
        if not row_from_tokens or not row_to_tokens or len(row_from_tokens) != len(row_to_tokens):
            continue
        row_pairs = (
            frozenset(zip(row_to_tokens, row_from_tokens))
            if reversed_
            else frozenset(zip(row_from_tokens, row_to_tokens))
        )
        if row_pairs != pairs:
            continue
        if reversed_:
            identity_ok = _identity_ok(
                from_system_code, from_source_code, r.to_system_code, r.to_source_code
            ) and _identity_ok(
                to_system_code, to_source_code, r.from_system_code, r.from_source_code
            )
        else:
            identity_ok = _identity_ok(
                from_system_code, from_source_code, r.from_system_code, r.from_source_code
            ) and _identity_ok(
                to_system_code, to_source_code, r.to_system_code, r.to_source_code
            )
        if not identity_ok:
            continue
        row_type = detect_join_direction(r.join_condition)
        if not direction_compatible(query_type, row_type, reversed_):
            continue
        matches.append(r)
    return matches


def pick_formal_link(matches: list[AssetRelation]) -> Optional[AssetRelation]:
    """Prefer existing formal/verified relation over candidate copies."""
    formal = [
        r
        for r in matches
        if (r.relation_layer or "").lower() == "formal"
        or (r.validation_status or "").lower() in {"verified", "approved", "manual_reviewed"}
    ]
    if formal:
        # Prefer owner-named (not HIS.* ODS mirror) when both exist
        def score(r: AssetRelation) -> int:
            s = 0
            ft = (r.from_table or "").upper()
            if not ft.startswith("HIS."):
                s += 2
            if (r.relation_layer or "").lower() == "formal":
                s += 3
            if (r.validation_status or "").lower() == "verified":
                s += 1
            return s

        formal.sort(key=score, reverse=True)
        return formal[0]
    # No formal: return highest-id candidate for link (do not promote)
    if matches:
        return sorted(matches, key=lambda r: r.id or 0, reverse=True)[0]
    return None


def approve_review(
    db: Session,
    review: AssetRelationReview,
    *,
    reviewer: str = "reviewer",
    note: str | None = None,
) -> dict:
    """Approve a draft review: link existing formal/candidate, never duplicate formal."""
    if (review.review_status or "").lower() not in {"draft", "reviewing", "pending", ""}:
        return {
            "ok": False,
            "error": f"cannot approve review in status={review.review_status}",
            "review_id": review.id,
        }

    matches = find_matching_relations(
        db,
        from_table=review.from_table,
        to_table=review.to_table,
        from_columns=review.from_columns,
        to_columns=review.to_columns,
        from_system_code=review.from_system_code,
        from_source_code=review.from_source_code,
        to_system_code=review.to_system_code,
        to_source_code=review.to_source_code,
        join_condition=review.join_condition,
    )
    link = pick_formal_link(matches)
    action = "linked_existing"
    if link is None:
        # Create candidate only if nothing exists; do not auto-create formal.
        # 198 F05/T10：缺失端点/字段/条件时返回可定位阻断，不静默丢字段新建。
        from_tokens = normalize_column_tokens(review.from_columns)
        to_tokens = normalize_column_tokens(review.to_columns)
        missing: list[str] = []
        if not (review.from_table or "").strip():
            missing.append("from_table")
        if not (review.to_table or "").strip():
            missing.append("to_table")
        if not from_tokens:
            missing.append("from_columns")
        if not to_tokens:
            missing.append("to_columns")
        if from_tokens and to_tokens and len(from_tokens) != len(to_tokens):
            missing.append("from_columns/to_columns(数量不一致，无法整对成对)")
        if not (review.join_condition or "").strip():
            missing.append("join_condition")
        rel = None
        if not missing:
            rel = AssetRelation(
                from_table=review.from_table,
                from_columns=review.from_columns,
                to_table=review.to_table,
                to_columns=review.to_columns,
                join_condition=review.join_condition,
                confidence=review.confidence or "B",
                # 198 F05/T10：人工 approve 只改治理状态，不制造验证事实。
                # validation_status 为自由文本列（无枚举约束）；"not_run" 是 198
                # 复核口径中"未执行验证"的现行词汇，derive_layer 对其保持 candidate 层。
                validation_status="not_run",
                relation_layer="candidate",
                note=review.review_note or review.relation_desc_cn,
            )
            populate_endpoint_fields(db, rel)
            # 复核草稿明确声明的两端身份优先；注册表未命中时不静默清空（198 T10）
            if review.from_system_code:
                rel.from_system_code = review.from_system_code
            if review.from_source_code:
                rel.from_source_code = review.from_source_code
            if review.to_system_code:
                rel.to_system_code = review.to_system_code
            if review.to_source_code:
                rel.to_source_code = review.to_source_code
            if not rel.from_system_code:
                missing.append("from_system_code(草稿未声明且注册表未解析)")
            if not rel.from_source_code:
                missing.append("from_source_code(草稿未声明且注册表未解析)")
            if not rel.to_system_code:
                missing.append("to_system_code(草稿未声明且注册表未解析)")
            if not rel.to_source_code:
                missing.append("to_source_code(草稿未声明且注册表未解析)")
        if missing:
            return {
                "ok": False,
                "error": "approve 阻断：新建候选缺少完整身份/条件字段: " + ", ".join(missing),
                "error_code": "incomplete_candidate_identity",
                "missing_fields": missing,
                "review_id": review.id,
            }
        db.add(rel)
        db.flush()
        link = rel
        action = "created_candidate"

    layer = (link.relation_layer or "").lower()
    status = (link.validation_status or "").lower()
    if action == "created_candidate":
        pass  # 198 T10：新建候选动作保持可观测（不被下方链接分支改写）
    elif layer == "formal" or status in {"verified", "approved", "manual_reviewed"}:
        action = "linked_formal"
    elif layer == "candidate" or status == "candidate":
        # Explicitly do NOT promote candidate to formal here — avoids 537/538 formal dup
        action = "linked_candidate_no_promote"

    review.source_relation_id = link.id
    review.source_relation_table = "asset_relations"
    review.review_status = "approved"
    review.reviewer = reviewer
    review.reviewed_at = datetime.now(timezone.utc)
    if note:
        review.review_note = (review.review_note or "") + f"\n[approve] {note}"
    elif not review.review_note:
        review.review_note = f"approved: {action}; linked relation id={link.id}"
    db.flush()
    return {
        "ok": True,
        "review_id": review.id,
        "action": action,
        "source_relation_id": link.id,
        "relation_layer": link.relation_layer,
        "validation_status": link.validation_status,
        "from_table": link.from_table,
        "to_table": link.to_table,
    }


def reject_review(
    db: Session,
    review: AssetRelationReview,
    *,
    reviewer: str = "reviewer",
    note: str | None = None,
) -> dict:
    review.review_status = "rejected"
    review.reviewer = reviewer
    review.reviewed_at = datetime.now(timezone.utc)
    if note:
        review.review_note = (review.review_note or "") + f"\n[reject] {note}"
    db.flush()
    return {"ok": True, "review_id": review.id, "review_status": "rejected"}
