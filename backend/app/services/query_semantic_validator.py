"""144 S3: metadata–relation–semantic validation layers (144 §4.4 G1–G3).

Pure functions over injected evidence so tests never touch a live database:
- G1 structure: every physical table exists exactly in the current snapshot;
- G2 relation: every JOIN hits a formal validated relation with complete
  composite keys; N:N relations without DISTINCT/GROUP BY are fanout blocks;
- G3 semantic: derive the semantic contract (grain/output/aggregation/time).
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlglot import exp

from .sql_ast import SQLParseError, extract_table_dependencies, parse_sql

# relations accepted as JOIN evidence (144 §4.4: D-class/candidates never auto-pass)
_FORMAL_RELATION_STATUSES = {"validated", "A", "A_rechecked", "formal", "active"}
_FANOUT_CARDINALITIES = {"n:n", "n_n", "many_to_many", "m:n"}


def _table_key(schema: str | None, table: str) -> tuple[str | None, str]:
    return ((schema or "").upper(), table.upper())


def resolve_table(
    metadata_tables: dict[tuple[str, str], dict],
    name: str,
) -> tuple[str, str] | None:
    """Resolve a (schema.)table reference against the snapshot index.

    Exact schema-qualified hit wins; bare names must be unique, otherwise
    ambiguous → None (fail closed, caller records unresolved/blocked).
    """
    parts = [p.strip('"`[]') for p in name.split(".")]
    if len(parts) >= 2:
        key = _table_key(parts[-2], parts[-1])
        return key if key in metadata_tables else None
    table = parts[-1].upper()
    hits = [k for k in metadata_tables if k[1] == table]
    if len(hits) != 1:
        return None
    return hits[0]


def _alias_map(tree: exp.Expression) -> dict[str, tuple[str, str]]:
    """alias/name → physical table name for join column attribution."""
    mapping: dict[str, tuple[str, str]] = {}
    for node in tree.find_all(exp.Table):
        parts = [p.name for p in node.parts if p.name]
        full = ".".join(parts).upper() if parts else node.sql().upper()
        alias = node.alias_or_name
        if alias:
            mapping[alias.upper()] = full
    return mapping


def _join_column_pairs(tree: exp.Expression) -> list[dict[str, str]]:
    """Extract (left_table.left_col = right_table.right_col) pairs from JOIN ONs."""
    alias_map = _alias_map(tree)
    pairs: list[dict[str, str]] = []
    for join in tree.find_all(exp.Join):
        on = join.args.get("on")
        if on is None:
            pairs.append({"kind": "cross", "left": None, "right": None})
            continue
        for eq in on.find_all(exp.EQ):
            left, right = eq.this, eq.expression
            if isinstance(left, exp.Column) and isinstance(right, exp.Column):
                for a, b in ((left, right), (right, left)):
                    pass
                pairs.append(
                    {
                        "kind": "eq",
                        "left": f"{alias_map.get(left.table.upper(), left.table.upper())}.{left.name.upper()}",
                        "right": f"{alias_map.get(right.table.upper(), right.table.upper())}.{right.name.upper()}",
                    }
                )
    return pairs


def _split_columns(raw: str | list[str] | None) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(c).strip().upper() for c in raw if str(c).strip()]
    return [p.strip().upper() for p in str(raw).split(",") if p.strip()]


def _relation_endpoints(relation: dict) -> tuple[set[str], set[str], list[str], list[str]]:
    left = (relation.get("from_table") or "").upper()
    right = (relation.get("to_table") or "").upper()
    return (
        {left, left.split(".")[-1]},
        {right, right.split(".")[-1]},
        _split_columns(relation.get("from_columns")),
        _split_columns(relation.get("to_columns")),
    )


def _table_of_ref(ref: str) -> str:
    """Table portion of a possibly 3-part (schema.table.column) reference."""
    parts = ref.split(".")
    return parts[-2] if len(parts) >= 3 else parts[0]


def _match_relation_for_pair(
    pair: dict[str, str], relations: list[dict]
) -> dict | None:
    """Find a formal relation covering this join column pair (either direction)."""
    left_ref, right_ref = pair["left"], pair["right"]
    left_table = _table_of_ref(left_ref)
    left_col = left_ref.split(".")[-1]
    right_table = _table_of_ref(right_ref)
    right_col = right_ref.split(".")[-1]
    for rel in relations:
        status = str(rel.get("validation_status") or rel.get("status") or "").lower()
        if status not in {s.lower() for s in _FORMAL_RELATION_STATUSES}:
            continue
        lset, rset, lcols, rcols = _relation_endpoints(rel)
        if left_table in lset and right_table in rset and left_col in lcols and right_col in rcols:
            return rel
        if left_table in rset and right_table in lset and left_col in rcols and right_col in lcols:
            return rel
    return None


def validate_metadata_layer(
    sql: str,
    dialect: str,
    metadata_tables: dict[tuple[str, str], dict],
) -> dict[str, Any]:
    deps = extract_table_dependencies(sql, dialect)
    findings: list[dict[str, Any]] = []
    missing: list[str] = []
    resolved: list[dict[str, Any]] = []
    for dep in deps["tables"]:
        key = resolve_table(metadata_tables, dep["name"])
        if key is None:
            # ambiguous bare name also lands here (fail closed)
            missing.append(dep["name"])
            findings.append(
                {
                    "layer": "G1_structure",
                    "status": "blocked",
                    "code": "E_METADATA_STALE",
                    "message": f"表 {dep['name']} 不在当前元数据快照中精确存在（缺失或同名歧义）",
                }
            )
        else:
            resolved.append(
                {"schema_name": key[0], "object_name": key[1], "system_code": metadata_tables[key].get("system_code"), "source_code": metadata_tables[key].get("source_code")}
            )
    status = "blocked" if missing else "pass"
    return {"layer": "G1_structure", "status": status, "findings": findings, "tables": resolved}


def validate_relation_layer(
    sql: str,
    dialect: str,
    relations: list[dict],
) -> dict[str, Any]:
    parsed = parse_sql(sql, dialect)
    tree: exp.Expression = parsed["tree"]
    pairs = _join_column_pairs(tree)
    findings: list[dict[str, Any]] = []
    used_relations: list[int] = []
    violations: list[str] = []

    has_distinct_or_group = bool(
        list(tree.find_all(exp.Distinct)) or list(tree.find_all(exp.Group))
    )

    # group join pairs by table-pair to check composite key completeness
    pair_groups: dict[tuple[str, str], list[dict[str, str]]] = {}
    for pair in pairs:
        if pair["kind"] != "eq":
            violations.append("存在无 ON 条件的交叉 JOIN（笛卡尔积风险）")
            continue
        lt = _table_of_ref(pair["left"])
        rt = _table_of_ref(pair["right"])
        pair_groups.setdefault((lt, rt), []).append(pair)

    for (lt, rt), group in pair_groups.items():
        for pair in group:
            matched = _match_relation_for_pair(pair, relations)
            if matched:
                break
        if matched is None:
            violations.append(f"JOIN {lt} ↔ {rt} 未命中任何正式验证关系（E_RELATION）")
            findings.append(
                {
                    "layer": "G2_relation",
                    "status": "blocked",
                    "code": "E_RELATION",
                    "message": f"JOIN {lt} ↔ {rt} 缺少正式关系/配方证据；D 类或候选关系不自动通过",
                }
            )
            continue
        used_relations.append(int(matched.get("id", 0)))
        # composite key completeness: every key column of the relation must be
        # present in the join group for this table pair
        lset, rset, lcols, rcols = _relation_endpoints(matched)
        key_cols = {c for c in lcols} | {c for c in rcols}
        provided = {p["left"].split(".")[-1] for p in group} | {p["right"].split(".")[-1] for p in group}
        # for composite keys both sides must supply every key column
        missing_left = [c for c in lcols if c not in provided]
        missing_right = [c for c in rcols if c not in provided]
        if key_cols and (missing_left or missing_right):
            missing = sorted(set(missing_left) | set(missing_right))
            violations.append(
                f"JOIN {lt} ↔ {rt} 组合键不完整（缺 {', '.join(missing)}；关系要求 {'+'.join(lcols)}={'+'.join(rcols)}）"
            )
            findings.append(
                {
                    "layer": "G2_relation",
                    "status": "blocked",
                    "code": "E_RELATION",
                    "message": f"JOIN {lt} ↔ {rt} 退化为单键：关系要求组合键 {'+'.join(lcols)}={'+'.join(rcols)}",
                }
            )
            continue
        card = str(matched.get("cardinality") or "").lower().replace(" ", "")
        if card in _FANOUT_CARDINALITIES and not has_distinct_or_group:
            violations.append(f"JOIN {lt} ↔ {rt} 为 N:N 关系且未以 DISTINCT/GROUP BY 解释 fanout")
            findings.append(
                {
                    "layer": "G2_relation",
                    "status": "blocked",
                    "code": "E_FANOUT",
                    "message": f"多对多 JOIN {lt} ↔ {rt} 未解释重复膨胀",
                }
            )
    status = "blocked" if violations else "pass"
    return {
        "layer": "G2_relation",
        "status": status,
        "findings": findings,
        "used_relations": sorted(set(used_relations)),
        "join_pairs": len(pairs),
    }


def derive_semantic_contract(sql: str, dialect: str) -> dict[str, Any]:
    """G3: derive grain/aggregation/output contract from the AST."""
    parsed = parse_sql(sql, dialect)
    tree: exp.Expression = parsed["tree"]
    group_keys: list[str] = []
    for group in tree.find_all(exp.Group):
        for col in group.find_all(exp.Column):
            group_keys.append(col.sql().upper())
    has_distinct = bool(list(tree.find_all(exp.Distinct)))
    has_aggregation = bool(list(tree.find_all(exp.AggFunc)))
    output_columns: list[str] = []
    for select in tree.find_all(exp.Select):
        for proj in select.expressions:
            if isinstance(proj, exp.Column):
                output_columns.append(proj.sql().upper())
            elif isinstance(proj, exp.Star):
                output_columns.append("*")
    return {
        "grain": "one_row_per_group" if group_keys else ("distinct_rows" if has_distinct else "unspecified"),
        "group_keys": sorted(set(group_keys)),
        "has_aggregation": has_aggregation,
        "has_distinct": has_distinct,
        "output_columns": output_columns,
    }


def build_validation_report(
    sql: str,
    dialect: str,
    *,
    metadata_tables: dict[tuple[str, str], dict] | None = None,
    relations: list[dict] | None = None,
    snapshot_stale: bool = False,
) -> dict[str, Any]:
    """Full G1–G3 report with content digest; overall status honest."""
    layers: list[dict[str, Any]] = []
    if metadata_tables is not None:
        g1 = validate_metadata_layer(sql, dialect, metadata_tables)
        if snapshot_stale and g1["status"] == "pass":
            g1["status"] = "stale"
            g1["findings"].append(
                {"layer": "G1_structure", "status": "stale", "code": "E_METADATA_STALE", "message": "元数据快照已过期"}
            )
        layers.append(g1)
    if relations is not None:
        layers.append(validate_relation_layer(sql, dialect, relations))
    semantic = {"layer": "G3_semantic", "status": "candidate", "contract": derive_semantic_contract(sql, dialect), "findings": []}
    layers.append(semantic)

    statuses = [l["status"] for l in layers]
    overall = "blocked" if "blocked" in statuses else ("stale" if "stale" in statuses else "pass")
    digest = hashlib.sha256(
        json.dumps({"layers": layers, "overall": overall}, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    return {"schema_version": "query-validation/v1", "overall": overall, "layers": layers, "validation_digest": digest}
