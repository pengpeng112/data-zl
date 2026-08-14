"""Infer quality-finding business system from target_ref / table catalog."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session


@dataclass(frozen=True)
class FindingTarget:
    schema_name: str | None
    table_name: str | None
    qualified: str | None


def _clean(value: object | None) -> str | None:
    text = str(value or "").strip()
    return text or None


def parse_finding_target(target_ref: str | None) -> FindingTarget:
    raw = str(target_ref or "").strip()
    if not raw or raw.startswith("共 ") or raw.startswith("共"):
        return FindingTarget(None, None, None)
    left = raw.split(" -> ", 1)[0].split("（", 1)[0].split("(", 1)[0].strip()
    if " " in left and "." not in left:
        return FindingTarget(None, None, None)
    parts = [part for part in left.split(".") if part]
    if not parts:
        return FindingTarget(None, None, None)
    if len(parts) == 1:
        return FindingTarget(None, parts[0], parts[0])
    return FindingTarget(".".join(parts[:-1]), parts[-1], left)


@dataclass(frozen=True)
class FindingLocation:
    schema_name: str | None
    table_name: str | None
    column_name: str | None
    related_schema: str | None
    related_table: str | None
    related_column: str | None


def parse_relation_ref(target_ref: str | None) -> tuple[FindingTarget, FindingTarget]:
    raw = str(target_ref or "").strip()
    if " -> " not in raw:
        return parse_finding_target(raw), FindingTarget(None, None, None)
    left, right = raw.split(" -> ", 1)
    right = right.split("(rel_id", 1)[0].strip()
    return parse_finding_target(left), parse_finding_target(right)


def parse_relation_id(target_ref: str | None) -> int | None:
    text = str(target_ref or "")
    if "rel_id=" not in text:
        return None
    raw = text.split("rel_id=", 1)[1]
    raw = raw.split(")", 1)[0].split(",", 1)[0].strip()
    try:
        return int(raw)
    except ValueError:
        return None


def resolve_finding_location(finding: object, rule: object | None = None) -> FindingLocation:
    detail = getattr(finding, "detail", None)
    if not isinstance(detail, dict):
        detail = {}
    left, right = parse_relation_ref(getattr(finding, "target_ref", None))
    schema = (
        _clean(getattr(finding, "schema_name", None))
        or _clean(getattr(finding, "namespace_name", None))
        or left.schema_name
    )
    table = _clean(getattr(finding, "table_name", None)) or left.table_name
    column = _clean(getattr(finding, "column_name", None))
    related_schema = _clean(detail.get("related_schema")) or right.schema_name
    related_table = _clean(detail.get("related_table")) or right.table_name
    related_column = _clean(
        detail.get("related_columns") or detail.get("related_field") or detail.get("to_columns")
    )
    if rule is not None:
        schema = schema or _clean(getattr(rule, "namespace_name", None))
        table = table or _clean(getattr(rule, "target_table", None))
        column = column or _clean(getattr(rule, "target_field", None))
        related_table = related_table or _clean(getattr(rule, "related_table", None))
        related_column = related_column or _clean(getattr(rule, "related_field", None))
        related_schema = related_schema or _clean(getattr(rule, "namespace_name", None)) if related_table else related_schema
    column = column or _clean(detail.get("column_name") or detail.get("target_field") or detail.get("from_columns"))
    return FindingLocation(schema, table, column, related_schema, related_table, related_column)


def build_table_system_index(db: Session) -> tuple[dict[tuple[str, str], str], dict[str, str]]:
    from sqlalchemy import select

    from ..models.asset import AssetTable
    from ..services.asset_catalog import normalize_system_code

    table_map: dict[tuple[str, str], str] = {}
    schema_counts: dict[str, dict[str, int]] = {}
    rows = db.execute(
        select(AssetTable.system_code, AssetTable.source_code, AssetTable.schema_name, AssetTable.table_name)
    ).all()
    for system_code, source_code, schema_name, table_name in rows:
        schema = (schema_name or "").strip()
        table = (table_name or "").strip()
        if not table:
            continue
        system = normalize_system_code(system_code, source_code=source_code, schema_name=schema) or (system_code or "").strip()
        if not system:
            continue
        table_map[(schema.upper(), table.upper())] = system
        if schema:
            bucket = schema_counts.setdefault(schema.upper(), {})
            bucket[system] = bucket.get(system, 0) + 1
    schema_map = {
        schema: max(counts.items(), key=lambda item: item[1])[0]
        for schema, counts in schema_counts.items()
    }
    return table_map, schema_map


def infer_system_code(
    *,
    system_code: str | None,
    source_code: str | None = None,
    schema_name: str | None = None,
    table_name: str | None = None,
    target_ref: str | None = None,
    table_map: dict[tuple[str, str], str] | None = None,
    schema_map: dict[str, str] | None = None,
) -> str:
    from ..services.asset_catalog import normalize_system_code

    explicit = normalize_system_code(system_code, source_code=source_code, schema_name=schema_name)
    if explicit and explicit not in {"UNKNOWN", "UNASSIGNED"}:
        return explicit
    target = parse_finding_target(target_ref)
    schema = (schema_name or target.schema_name or "").strip()
    table = (table_name or target.table_name or "").strip()
    table_map = table_map or {}
    schema_map = schema_map or {}
    if schema and table:
        hit = table_map.get((schema.upper(), table.upper()))
        if hit:
            return hit
    if schema:
        hit = schema_map.get(schema.upper())
        if hit:
            return hit
    return "UNASSIGNED"
