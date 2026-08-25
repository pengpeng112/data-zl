"""149 P1b/P1c: 值域知识库共享服务。

- confirmed_domains_for_injection：AI 注入链路唯一入口过滤器
  （status=confirmed 且 conflict_status 未裁决的不进注入——149 §2.4）；
- mark_conflict / attach_evidence / next_version：API 与种子脚本共用的
  冲突检测、证据追加与版本推进逻辑。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.value_domain import (
    AssetColumnValueDomain,
    AssetColumnValueDomainEvidence,
    AssetColumnValueDomainVersion,
)

INJECTION_DOMAIN_FIELDS = (
    "system_code",
    "source_code",
    "schema_name",
    "table_name",
    "column_name",
    "code",
    "meaning",
    "note",
    "domain_kind",
    "scope_condition",
    "status",
)


def normalize_meaning(meaning: str | None) -> str:
    return " ".join((meaning or "").split())


def meanings_differ(a: str | None, b: str | None) -> bool:
    return normalize_meaning(a) != normalize_meaning(b)


def find_by_key(
    db: Session,
    *,
    system_code: str,
    source_code: str,
    schema_name: str,
    table_name: str,
    column_name: str,
    code: str,
) -> AssetColumnValueDomain | None:
    return db.scalar(
        select(AssetColumnValueDomain).where(
            AssetColumnValueDomain.system_code == system_code,
            AssetColumnValueDomain.source_code == source_code,
            AssetColumnValueDomain.schema_name == schema_name,
            AssetColumnValueDomain.table_name == table_name,
            AssetColumnValueDomain.column_name == column_name,
            AssetColumnValueDomain.code == code,
        )
    )


def domain_payload(row: AssetColumnValueDomain, version_no: int | None = None) -> dict[str, Any]:
    payload = {"id": row.id}
    payload.update({field: getattr(row, field) for field in INJECTION_DOMAIN_FIELDS})
    payload["version_no"] = version_no
    payload["updated_at"] = row.updated_at.isoformat() if row.updated_at else None
    return payload


def version_no_of(db: Session, row: AssetColumnValueDomain) -> int | None:
    if not row.current_version_id:
        return None
    v = db.get(AssetColumnValueDomainVersion, row.current_version_id)
    return v.version_no if v else None


def confirmed_domains_for_injection(
    db: Session, system_code: str | None = None
) -> list[dict[str, Any]]:
    """全部 confirmed 且无未裁决冲突的值域（含 trap），供注入/导出共用。

    149 §1 主路径：按 system 过滤全量，不依赖列级解析。
    """
    stmt = (
        select(AssetColumnValueDomain, AssetColumnValueDomainVersion.version_no)
        .outerjoin(
            AssetColumnValueDomainVersion,
            AssetColumnValueDomainVersion.id == AssetColumnValueDomain.current_version_id,
        )
        .where(
            AssetColumnValueDomain.status == "confirmed",
            AssetColumnValueDomain.conflict_status == "none",
        )
        .order_by(
            AssetColumnValueDomain.schema_name,
            AssetColumnValueDomain.table_name,
            AssetColumnValueDomain.column_name,
            AssetColumnValueDomain.domain_kind,
            AssetColumnValueDomain.code,
        )
    )
    if system_code:
        stmt = stmt.where(AssetColumnValueDomain.system_code == system_code)
    rows = db.execute(stmt).all()
    return [domain_payload(row, version_no) for row, version_no in rows]


def evidence_row(domain_id: int, item: dict[str, Any]) -> AssetColumnValueDomainEvidence:
    observed_at = item.get("observed_at")
    if isinstance(observed_at, str):
        observed_at = datetime.fromisoformat(observed_at)
    return AssetColumnValueDomainEvidence(
        domain_id=domain_id,
        source_type=item["source_type"],
        source_system=item.get("source_system"),
        observed_meaning=item.get("observed_meaning"),
        method=item.get("method"),
        sample_count=item.get("sample_count"),
        observed_at=observed_at,
        actor=item.get("actor"),
        snippet_ref=item.get("snippet_ref"),
    )


def evidence_duplicate(
    db: Session, domain_id: int, item: dict[str, Any]
) -> bool:
    """同域内 (source_type, source_system, observed_meaning, snippet_ref) 完全一致视为重复证据。"""
    observed_at = item.get("observed_at")
    if isinstance(observed_at, str):
        observed_at = datetime.fromisoformat(observed_at)
    stmt = select(AssetColumnValueDomainEvidence.id).where(
        AssetColumnValueDomainEvidence.domain_id == domain_id,
        AssetColumnValueDomainEvidence.source_type == item["source_type"],
        AssetColumnValueDomainEvidence.source_system == item.get("source_system"),
        AssetColumnValueDomainEvidence.snippet_ref == item.get("snippet_ref"),
    )
    if item.get("observed_meaning") is not None:
        stmt = stmt.where(
            AssetColumnValueDomainEvidence.observed_meaning == item.get("observed_meaning")
        )
    else:
        stmt = stmt.where(AssetColumnValueDomainEvidence.observed_meaning.is_(None))
    return db.scalar(stmt.limit(1)) is not None


def snapshot_of(row: AssetColumnValueDomain) -> dict[str, Any]:
    return {
        "code": row.code,
        "meaning": row.meaning,
        "note": row.note,
        "domain_kind": row.domain_kind,
        "scope_condition": row.scope_condition,
        "status": row.status,
        "conflict_status": row.conflict_status,
    }


def next_version(
    db: Session,
    row: AssetColumnValueDomain,
    *,
    change_reason: str,
    actor: str | None,
    evidence_ref: str | None = None,
) -> AssetColumnValueDomainVersion:
    """推进串行版本时间线并回指 current_version_id（调用方负责 flush/commit）。"""
    last_no = db.scalar(
        select(AssetColumnValueDomainVersion.version_no)
        .where(AssetColumnValueDomainVersion.domain_id == row.id)
        .order_by(AssetColumnValueDomainVersion.version_no.desc())
        .limit(1)
    )
    version = AssetColumnValueDomainVersion(
        domain_id=row.id,
        version_no=(last_no or 0) + 1,
        snapshot=snapshot_of(row),
        change_reason=change_reason,
        evidence_ref=evidence_ref,
        actor=actor,
        created_at=datetime.now(timezone.utc),
    )
    db.add(version)
    db.flush()
    row.current_version_id = version.id
    row.updated_at = datetime.now(timezone.utc)
    return version


def mark_conflict(db: Session, row: AssetColumnValueDomain) -> bool:
    """置位冲突标记；返回是否发生变化（未裁决冲突不进注入链路）。"""
    if row.conflict_status == "conflicted":
        return False
    row.conflict_status = "conflicted"
    row.updated_at = datetime.now(timezone.utc)
    return True


# ---------------------------------------------------------------------------
# 149 P1c 补充注入：propose-sql 基于 144 sqlglot 提取字段，附精确值域。
# 主路径（context/resolve / system-context 全量注入）不依赖本节。
# 解析失败必须显式上报，禁止静默跳过。
# ---------------------------------------------------------------------------

def value_domains_for_sql(
    db: Session, sql_text: str, dialect: str = "oracle"
) -> dict[str, Any]:
    """解析 SQL 引用字段并匹配 confirmed 值域。

    返回 {"injected": bool, "value_domains": [...], "not_injected_reason": str|None,
          "parser_version": str}。解析失败（SQLParseError/UnsupportedDialectError）
    时 injected=False 且 not_injected_reason 非空——调用方不得静默吞掉。
    """
    from .sql_ast import PARSER_VERSION, SQLParseError, UnsupportedDialectError, parse_sql
    from sqlglot import exp

    try:
        parsed = parse_sql(sql_text or "", dialect=dialect)
    except (SQLParseError, UnsupportedDialectError, ValueError) as exc:
        return {
            "injected": False,
            "value_domains": [],
            "not_injected_reason": f"sql_parse_failed: {str(exc)[:200]}",
            "parser_version": PARSER_VERSION,
        }
    tree = parsed["tree"]

    # FROM/JOIN 表全名（取最后两段作 schema.table）与别名映射
    from_tables: set[tuple[str, str]] = set()
    alias_map: dict[str, tuple[str, str]] = {}
    for node in tree.find_all(exp.Table):
        parts = [p.name.upper() for p in node.parts if p.name]
        if not parts:
            continue
        full = ".".join(parts)
        pair = (parts[-2], parts[-1]) if len(parts) >= 2 else ("", parts[-1])
        from_tables.add(pair)
        alias = (node.alias_or_name or "").upper()
        if alias and alias != parts[-1]:
            alias_map[alias] = pair
        alias_map.setdefault(parts[-1], pair)  # 裸表名引用

    qualified: set[tuple[str, str, str]] = set()  # (schema, table, column)
    table_column: set[tuple[str, str]] = set()  # (table, column)
    bare_columns: set[str] = set()
    for node in tree.find_all(exp.Column):
        col = (node.name or "").upper()
        if not col:
            continue
        tbl = (node.table or "").upper()
        if not tbl:
            bare_columns.add(col)
            continue
        pair = alias_map.get(tbl) or alias_map.get(tbl.split(".")[-1])
        if pair is None:
            table_column.add((tbl.split(".")[-1], col))
        else:
            qualified.add((pair[0], pair[1], col))
            table_column.add((pair[1], col))

    domains = confirmed_domains_for_injection(db)
    matches: list[dict[str, Any]] = []
    seen_ids: set[int] = set()
    for d in domains:
        did = f"{d['system_code']}|{d['source_code']}|{d['schema_name']}|{d['table_name']}|{d['column_name']}|{d['code']}"
        if did in seen_ids:
            continue
        schema_u = (d["schema_name"] or "").upper()
        table_u = (d["table_name"] or "").upper()
        column_u = (d["column_name"] or "").upper()
        entry = dict(d)
        if (schema_u, table_u, column_u) in qualified:
            entry["match_basis"] = "schema_table_column"
        elif (table_u, column_u) in table_column:
            entry["match_basis"] = "table_column"
        elif column_u in bare_columns and (
            (schema_u, table_u) in from_tables or any(t == table_u for _, t in from_tables)
        ):
            entry["match_basis"] = "from_table_column"
        elif column_u in bare_columns:
            entry["match_basis"] = "column_name_only"
        else:
            continue
        seen_ids.add(did)
        matches.append(entry)

    return {
        "injected": True,
        "value_domains": matches,
        "not_injected_reason": None,
        "parser_version": PARSER_VERSION,
    }
