"""126 P3: extract JOIN endpoint pairs from query SQL as relation evidence candidates.

Does NOT write formal asset_relations. Emits structured candidates for review /
sql-relation-intake style follow-up.
"""
from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from ..models.query_asset import AssetQueryVersion

# JOIN schema.table [alias] ON ...
_JOIN = re.compile(
    r"\b(?:FROM|JOIN)\s+([A-Za-z_][\w$#]*(?:\.[A-Za-z_][\w$#]*){0,2})"
    r"(?:\s+(?:AS\s+)?([A-Za-z_][\w$#]*))?",
    re.I,
)
_ON_EQ = re.compile(
    r"([A-Za-z_][\w$#]*)\.([A-Za-z_][\w$#]*)\s*=\s*([A-Za-z_][\w$#]*)\.([A-Za-z_][\w$#]*)",
    re.I,
)


def extract_join_candidates(sql: str) -> list[dict[str, Any]]:
    text = sql or ""
    # alias -> qualified table
    alias_map: dict[str, str] = {}
    tables: list[str] = []
    for m in _JOIN.finditer(text):
        table = m.group(1).upper()
        alias = (m.group(2) or table.split(".")[-1]).upper()
        # skip reserved-ish
        if alias in {"ON", "WHERE", "LEFT", "RIGHT", "INNER", "OUTER", "JOIN", "SELECT"}:
            alias = table.split(".")[-1]
        alias_map[alias] = table
        if table not in tables:
            tables.append(table)

    pairs: list[dict[str, Any]] = []
    seen = set()
    for m in _ON_EQ.finditer(text):
        a1, c1, a2, c2 = m.group(1).upper(), m.group(2).upper(), m.group(3).upper(), m.group(4).upper()
        t1 = alias_map.get(a1, a1)
        t2 = alias_map.get(a2, a2)
        if t1 == t2:
            continue
        key = (t1, c1, t2, c2)
        rkey = (t2, c2, t1, c1)
        if key in seen or rkey in seen:
            continue
        seen.add(key)
        pairs.append(
            {
                "from_table": t1,
                "from_column": c1,
                "to_table": t2,
                "to_column": c2,
                "join_condition": f"{t1}.{c1} = {t2}.{c2}",
                "evidence_level": "sql_join_parse",
                "formal": False,
                "note": "candidate only; requires sql-relation-intake review",
            }
        )
    return pairs


def extract_from_query_version(db: Session, query_code: str, version: int | None = None) -> dict:
    stmt = select_version(db, query_code, version)
    if not stmt:
        return {"ok": False, "error": "version_not_found"}
    cands = extract_join_candidates(stmt.sql_text or "")
    return {
        "ok": True,
        "query_code": stmt.query_code,
        "version": stmt.version,
        "status": stmt.status,
        "candidate_count": len(cands),
        "candidates": cands,
        "sql_sha256": stmt.sql_sha256,
    }


def select_version(db: Session, query_code: str, version: int | None) -> AssetQueryVersion | None:
    from sqlalchemy import select

    q = select(AssetQueryVersion).where(AssetQueryVersion.query_code == query_code)
    if version is not None:
        q = q.where(AssetQueryVersion.version == version)
    else:
        q = q.where(AssetQueryVersion.is_active.is_(True))
    return db.scalar(q.order_by(AssetQueryVersion.version.desc()))
