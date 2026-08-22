"""Offline intake of relations found in effective HIS view definitions.

The command is deliberately a file-to-file utility.  It never opens a database,
changes a formal relationship, or imports anything into the platform.  A view
definition is evidence only: the output is suitable for a review queue and for
building an inactive recipe draft.

Example::

    python scripts/intake_his_view_relations.py --views views.json \
        --relationships relationships.csv --reviews reviews.json --output result.json

The parser is intentionally conservative.  It understands ANSI joins, Oracle
comma joins and ``(+)`` predicates, while retaining an unresolved record when a
join cannot be proven from the SQL text.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


_IDENT_PART = r'(?:"[^"]+"|\[[^\]\r\n]+\]|`[^`\r\n]+`|[A-Za-z_][\w$#]*)'
IDENT = rf"{_IDENT_PART}(?:\.{_IDENT_PART}){{0,3}}"
RESERVED = {
    "AS", "ON", "WHERE", "JOIN", "LEFT", "RIGHT", "FULL", "INNER", "OUTER",
    "CROSS", "NATURAL", "USING", "GROUP", "ORDER", "HAVING", "UNION", "ALL",
    "FETCH", "OFFSET", "CONNECT", "START", "MODEL", "QUALIFY", "LIMIT",
}
CLAUSE_RE = re.compile(
    r"\b(?:WHERE|GROUP\s+BY|ORDER\s+BY|HAVING|CONNECT\s+BY|START\s+WITH|MODEL|"
    r"UNION(?:\s+ALL)?|MINUS|INTERSECT|FETCH\s+FIRST|OFFSET)\b", re.I
)
JOIN_START_RE = re.compile(
    r"\b(?:(?:LEFT|RIGHT|FULL|INNER|CROSS|NATURAL)\s+(?:OUTER\s+)?|)JOIN\b",
    re.I,
)
# Expressions are deliberately allowed to contain whitespace/parentheses so
# ``NVL(a.KEY, '0') = b.KEY`` is retained as a wrapped-key risk.  The lookahead
# keeps each equality bounded by a top-level AND/OR in the normal join syntax.
EQ_RE = re.compile(
    r"(?P<left>.+?)\s*=\s*(?P<right>.+?)(?=\s+(?:AND|OR)\b|$)",
    re.I | re.S,
)
COL_REF_RE = re.compile(
    rf"(?P<ref>{_IDENT_PART}\s*\.\s*{_IDENT_PART}(?:\s*\.\s*{_IDENT_PART})*)",
    re.I,
)


def normalize_identifier(value: str) -> str:
    """Normalize an Oracle/MySQL/SQL Server identifier without changing its path."""

    return ".".join(part.strip().strip('"[]`').upper() for part in value.strip().split("."))


def _compact(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def strip_comments(sql: str) -> str:
    sql = re.sub(r"/\*.*?\*/", " ", sql or "", flags=re.S)
    return re.sub(r"--[^\r\n]*", " ", sql)


def sanitize_sql(sql: str) -> str:
    """Remove literal contents from evidence, including URLs and credentials.

    Hashing is always done before this function.  Replacing every quoted value
    is safer than trying to identify which value might be a patient or password.
    Numeric literals are retained because ``VISIT_ID = 0`` is useful qualifier
    evidence; unusually long numeric constants are redacted.
    """

    text = strip_comments(sql)
    text = re.sub(r"'(?:''|[^'])*'", "'[REDACTED]'", text)
    text = re.sub(r"\b(?:https?|jdbc|oracle|mysql|sqlserver)://[^\s,)]+", "[REDACTED_URL]", text, flags=re.I)
    text = re.sub(r"\b\d{4,}\b", "[REDACTED_NUMBER]", text)
    return _compact(text)


def source_sql_sha256(sql: str) -> str:
    return hashlib.sha256((sql or "").encode("utf-8")).hexdigest()


def _balanced_slices(text: str, delimiter: str) -> list[str]:
    """Split on a delimiter only outside quotes and parentheses."""

    result: list[str] = []
    start = 0
    depth = 0
    quote: str | None = None
    i = 0
    while i < len(text):
        ch = text[i]
        if quote:
            if ch == quote:
                if i + 1 < len(text) and text[i + 1] == quote:
                    i += 2
                    continue
                quote = None
        elif ch in "'\"`":
            quote = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        elif depth == 0 and text[i : i + len(delimiter)].upper() == delimiter.upper():
            result.append(text[start:i])
            start = i + len(delimiter)
            i = start
            continue
        i += 1
    result.append(text[start:])
    return result


def split_union(sql: str) -> list[str]:
    parts: list[str] = []
    for part in _balanced_slices(strip_comments(sql), "UNION ALL"):
        parts.extend(_balanced_slices(part, "UNION"))
    return [p.strip() for p in parts if p.strip()]


def _from_segments(sql: str) -> tuple[str, str]:
    from_pos = _top_level_keyword(sql, "FROM")
    if from_pos < 0:
        return "", ""
    start = from_pos + len("FROM")
    ends = [m.start() + start for m in CLAUSE_RE.finditer(sql[start:]) if _top_level_keyword(sql[start:], m.group(0)) == m.start()]
    end = min(ends) if ends else len(sql)
    return sql[start:end].strip(), sql[end:].strip()


def _top_level_keyword(text: str, keyword: str) -> int:
    """Return a keyword position outside quotes/parentheses, or ``-1``."""

    pattern = re.compile(rf"\b{re.escape(keyword)}\b", re.I)
    depth = 0
    quote: str | None = None
    for match in pattern.finditer(text):
        depth = 0
        quote = None
        for ch in text[: match.start()]:
            if quote:
                if ch == quote:
                    quote = None
            elif ch in "'\"`":
                quote = ch
            elif ch == "(":
                depth += 1
            elif ch == ")":
                depth = max(depth - 1, 0)
        if depth == 0 and quote is None:
            return match.start()
    return -1


def _select_body(sql: str) -> str:
    """Unwrap a captured ``CREATE VIEW ... AS`` definition, if present."""

    text = strip_comments(sql or "").strip()
    if not re.match(r"CREATE\b|ALTER\b", text, re.I):
        return text
    view = re.search(r"\bVIEW\b", text, re.I)
    if not view:
        return text
    as_match = re.search(r"\bAS\b", text[view.end() :], re.I)
    return text[view.end() + as_match.end() :].strip() if as_match else text


_RESERVED_LOOKAHEAD = "(?!" + "|".join(sorted(RESERVED)) + r"\b)"
# An alias must not swallow the next JOIN/ON/WHERE keyword: without the guard
# ``FROM a JOIN b`` consumes ``JOIN`` as a's alias and drops table ``b``.
_ALIAS_PART = _RESERVED_LOOKAHEAD + r"(?:`[^`\r\n]+`|\[[^\]\r\n]+\]|\"[^\"]+\"|[A-Za-z_][\w$#]*)"

# Bare keywords that the FROM/JOIN scan can mistake for a table when the
# text around derived tables or window functions is fragmented.
NON_TABLE_KEYWORDS = RESERVED | {
    "FROM", "WITH", "OVER", "ALL", "PARTITION", "SELECT", "WHERE", "BY", "CASE", "WHEN",
    "THEN", "ELSE", "END", "EXISTS", "NOT", "NULL", "IS", "IN", "LIKE", "BETWEEN",
    "ASC", "DESC", "SET", "VALUES", "INTO", "DISTINCT", "TOP",
}


def _strip_ident_quotes(value: str) -> str:
    return value.strip().strip('"[]`').strip()


def _read_table_and_alias(segment: str, pos: int) -> tuple[str | None, str | None, int]:
    match = re.match(rf"\s*({IDENT})", segment[pos:], re.I)
    if not match:
        return None, None, pos
    table = normalize_identifier(match.group(1))
    cursor = pos + match.end()
    alias_match = re.match(rf"\s+(?:AS\s+)?({_ALIAS_PART})", segment[cursor:], re.I)
    alias = table.split(".")[-1]
    if alias_match and _strip_ident_quotes(alias_match.group(1)).upper() not in RESERVED:
        alias = _strip_ident_quotes(alias_match.group(1)).upper()
        cursor += alias_match.end()
    return table, alias, cursor


def _table_aliases(from_part: str) -> tuple[dict[str, str], list[str]]:
    """Collect base tables from FROM and JOIN, avoiding SELECT expressions."""

    aliases: dict[str, str] = {}
    tables: list[str] = []
    # Remove parenthesized subqueries before collecting their outer references.
    source = re.sub(
        r"\(\s*SELECT\b.*?\)\s*(?:AS\s+)?(?:[A-Za-z_]\w*|`[^`\r\n]+`|\[[^\]\r\n]+\]|\"[^\"]+\")",
        " ",
        from_part,
        flags=re.I | re.S,
    )
    # ``from_part`` starts right after the FROM keyword, so the first table has
    # no FROM/JOIN in front of it.  Anchor it explicitly (unless the text is a
    # full SELECT statement, which already carries its own FROM); otherwise the
    # first ANSI table (and its alias) is never registered and every ON
    # predicate that references it drops out as unresolved.
    scan_source = source
    if not re.search(r"\b(?:FROM|JOIN)\b", source, re.I):
        scan_source = "FROM " + source.lstrip()
    elif not re.match(r"(?i)\s*(?:FROM|JOIN|SELECT)\b", source):
        scan_source = "FROM " + source.lstrip()
    # The optional alias must never swallow the next clause keyword: with a
    # prepended "FROM", "FROM t_a JOIN t_b ..." would otherwise consume JOIN
    # as t_a's alias and lose t_b entirely.  A bare-keyword lookahead keeps
    # genuine (possibly quoted) aliases while leaving clause keywords for the
    # next finditer match.
    keyword_guard = r"(?!(?:" + "|".join(sorted(NON_TABLE_KEYWORDS)) + r")\b)"
    for match in re.finditer(
        rf"\b(?:FROM|JOIN)\s+[(\s]*({IDENT})(?:\s+(?:AS\s+)?{keyword_guard}({_ALIAS_PART}))?", scan_source, re.I
    ):
        table = normalize_identifier(match.group(1))
        if table.split(".")[-1] in NON_TABLE_KEYWORDS:
            continue
        raw_alias = match.group(2)
        alias = _strip_ident_quotes(raw_alias).upper() if raw_alias else table.split(".")[-1]
        if alias in RESERVED:
            alias = table.split(".")[-1]
        aliases[alias] = table
        if table not in tables:
            tables.append(table)
    # A comma list does not have FROM before every item.
    if from_part and not re.search(r"\b(?:FROM|JOIN)\b", from_part, re.I):
        # Oracle's comma style has only one FROM keyword.  Parse every
        # top-level item; this also handles the common unqualified ``A, B``
        # form where the JOIN regex would otherwise mistake B for an alias.
        for item in _balanced_slices(from_part, ","):
            table, alias, _ = _read_table_and_alias(item, 0)
            if table and table.split(".")[-1] not in NON_TABLE_KEYWORDS:
                aliases[alias or table.split(".")[-1]] = table
                if table not in tables:
                    tables.append(table)
    return aliases, tables


def _split_ident_parts(ref: str) -> list[str]:
    """Split a possibly quoted multi-part identifier into normalized parts."""

    parts: list[str] = []
    for raw in re.split(r"\.", ref.strip()):
        part = raw.strip().strip('"[]`').strip()
        if part:
            parts.append(part.upper())
    return parts


def _resolve_ref(expression: str, aliases: Mapping[str, str]) -> tuple[str, str, str] | None:
    refs = list(COL_REF_RE.finditer(expression))
    if not refs:
        return None
    parts = _split_ident_parts(refs[0].group("ref"))
    if len(parts) < 2:
        return None
    alias = parts[-2]
    column = parts[-1]
    table = aliases.get(alias)
    if not table:
        # Schema/table-qualified references (dbo.T.COL, db.dbo.T.COL) resolve
        # against known table names instead of aliases.
        target = alias.upper()
        for candidate in aliases.values():
            normalized = str(candidate).upper()
            if normalized == target or normalized.endswith("." + target):
                table = candidate
                break
    if not table:
        return None
    wrapper = _compact(expression)
    return table, column, wrapper


def _predicate_qualifiers(condition: str, equalities: Sequence[re.Match[str]]) -> list[str]:
    remaining = condition
    # Replace exact equality fragments, preserving all non-key conditions.
    for match in equalities:
        remaining = remaining.replace(match.group(0), " ")
    remaining = re.sub(r"\(\s*\+\s*\)", " ", remaining)
    remaining = re.sub(r"\s+", " ", remaining).strip(" ;")
    if not remaining:
        return []
    return [sanitize_sql(p.strip(" ()")) for p in re.split(r"\bAND\b", remaining, flags=re.I) if p.strip(" ()")]


@dataclass
class ParsedRelation:
    from_table: str
    from_columns: list[str]
    to_table: str
    to_columns: list[str]
    join_condition: str
    qualifiers: list[str] = field(default_factory=list)
    branch: int = 0
    outer_join: str | None = None
    function_wrapped: bool = False
    source_fragment: str = ""

    def identity(self) -> tuple[tuple[str, tuple[str, ...]], tuple[str, tuple[str, ...]]]:
        left = (self.from_table.upper(), tuple(c.upper() for c in self.from_columns))
        right = (self.to_table.upper(), tuple(c.upper() for c in self.to_columns))
        return tuple(sorted((left, right)))  # type: ignore[return-value]


def _parse_condition(condition: str, aliases: Mapping[str, str], branch: int) -> list[ParsedRelation]:
    matches = list(EQ_RE.finditer(condition))
    grouped: dict[tuple[str, str], list[tuple[str, str, str, str, re.Match[str]]]] = {}
    unresolved = []
    for match in matches:
        left_expr, right_expr = match.group("left"), match.group("right")
        left = _resolve_ref(left_expr, aliases)
        right = _resolve_ref(right_expr, aliases)
        if not left or not right or left[0] == right[0]:
            unresolved.append(match.group(0))
            continue
        grouped.setdefault((left[0], right[0]), []).append((left[1], right[1], left_expr, right_expr, match))
    output: list[ParsedRelation] = []
    for (left_table, right_table), pairs in sorted(grouped.items()):
        left_columns = [p[0] for p in pairs]
        right_columns = [p[1] for p in pairs]
        equality_text = " AND ".join(_compact(f"{p[2]} = {p[3]}") for p in pairs)
        outer = None
        if any(re.search(r"\(\s*\+\s*\)", p[2]) for p in pairs):
            outer = "left_optional"
        if any(re.search(r"\(\s*\+\s*\)", p[3]) for p in pairs):
            outer = "right_optional"
        def _plain(expr: str) -> str:
            return re.sub(r"[\[\]\"`\s]", "", re.sub(r"\(\s*\+\s*\)", "", expr.strip()))

        bare_column = re.compile(r"[A-Za-z_][\w$#]*(?:\.[A-Za-z_][\w$#]*)*")
        wrapped = any(
            not bare_column.fullmatch(_plain(p[2])) or not bare_column.fullmatch(_plain(p[3]))
            for p in pairs
        )
        output.append(
            ParsedRelation(
                left_table,
                left_columns,
                right_table,
                right_columns,
                equality_text,
                _predicate_qualifiers(condition, [p[4] for p in pairs]),
                branch,
                outer,
                wrapped,
                sanitize_sql(condition),
            )
        )
    return output


def parse_sql(sql: str) -> dict[str, Any]:
    """Parse SQL into dependency tables, relations and conservative risks."""

    clean = _select_body(sql or "")
    upper = clean.upper()
    # Keyword risk checks must ignore words inside string literals (e.g. a
    # view projecting 'INSERT...' text would otherwise look like DML).
    literal_masked = re.sub(r"'(?:''|[^'])*'", "''", clean)
    warnings: list[str] = []
    if re.search(r"\bEXEC(?:UTE)?\s+IMMEDIATE\b|\bDBMS_SQL\b", literal_masked, re.I):
        warnings.append("dynamic_sql")
    if "||" in clean:
        warnings.append("expression_concatenation")
    if re.search(r"\b(INSERT|UPDATE|DELETE|MERGE|CREATE|ALTER|DROP)\b", literal_masked, re.I):
        warnings.append("non_select_statement")
    branches = split_union(clean)
    if len(branches) > 1:
        warnings.append("union_branch_semantics")
    if re.search(r"\bSELECT\s+(?:DISTINCT\b|COUNT\s*\(|SUM\s*\(|AVG\s*\(|MIN\s*\(|MAX\s*\()", upper) or re.search(r"\bGROUP\s+BY\b|\bOVER\s*\(", upper):
        warnings.append("aggregation_or_grain_change")
    aliases_all: dict[str, str] = {}
    tables_all: list[str] = []
    relations: list[ParsedRelation] = []
    for branch_index, branch in enumerate(branches):
        from_part, tail = _from_segments(branch)
        aliases, tables = _table_aliases(from_part)
        # Dependencies can also occur in scalar/inline subqueries.  Add those
        # tables, but do not let an inner alias replace an outer join alias.
        nested_aliases, nested_tables = _table_aliases(branch)
        for alias, table in nested_aliases.items():
            aliases.setdefault(alias, table)
        tables.extend(table for table in nested_tables if table not in tables)
        aliases_all.update(aliases)
        for table in tables:
            if table not in tables_all:
                tables_all.append(table)
        # ANSI joins: each ON is bounded by the following JOIN or a clause.
        for match in JOIN_START_RE.finditer(from_part):
            on_pos = re.search(r"\bON\b", from_part[match.end() :], re.I)
            if not on_pos:
                continue
            start = match.end() + on_pos.end()
            stops = [x.start() for x in JOIN_START_RE.finditer(from_part[start:])]
            stop_clauses = [x.start() for x in CLAUSE_RE.finditer(from_part[start:])]
            end = start + min(stops + stop_clauses) if stops + stop_clauses else len(from_part)
            relations.extend(_parse_condition(from_part[start:end], aliases, branch_index))
        # Oracle comma joins use predicates in the tail (WHERE), including (+).
        if "," in from_part:
            where_match = re.search(r"\bWHERE\b", branch, re.I)
            if where_match:
                where = branch[where_match.end() :]
                end_match = CLAUSE_RE.search(where)
                where = where[: end_match.start()] if end_match else where
                relations.extend(_parse_condition(where, aliases, branch_index))
                warnings.append("oracle_comma_join")
        if re.search(r"\(\s*\+\s*\)", branch):
            warnings.append("oracle_outer_join")
        if any(r.function_wrapped for r in relations if r.branch == branch_index):
            warnings.append("function_wrapped_join_key")
    # A missing alias/table is useful evidence, not a reason to invent a key.
    if not tables_all:
        warnings.append("no_base_tables")
    if not relations and len(tables_all) > 1:
        warnings.append("join_key_unresolved")
    return {
        "tables": sorted(tables_all),
        "aliases": {k: aliases_all[k] for k in sorted(aliases_all)},
        "relations": relations,
        "warnings": sorted(set(warnings)),
        "branch_count": len(branches),
    }


def _field(row: Mapping[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        if name in row and row[name] not in (None, ""):
            return row[name]
    return default


def _as_list(value: Any, separator: str = "|") -> list[str]:
    if isinstance(value, (list, tuple)):
        return [str(v).strip().upper() for v in value if str(v).strip()]
    if value is None:
        return []
    return [v.strip().upper() for v in re.split(r"[|,+]", str(value)) if v.strip()]


def _view_records(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [dict(x) for x in data if isinstance(x, Mapping)]
    if not isinstance(data, Mapping):
        raise ValueError("views JSON must be an object or list")
    for key in ("view_definitions", "views", "items", "records", "data"):
        value = data.get(key)
        if isinstance(value, list):
            return [dict(x) for x in value if isinstance(x, Mapping)]
    # Native 08 metadata shape: schemas -> owner -> views -> view -> {ddl,...}.
    schemas = data.get("schemas")
    if isinstance(schemas, Mapping):
        result: list[dict[str, Any]] = []
        for owner, schema in sorted(schemas.items(), key=lambda item: str(item[0])):
            if not isinstance(schema, Mapping) or not isinstance(schema.get("views"), Mapping):
                continue
            for view_name, value in sorted(schema["views"].items(), key=lambda item: str(item[0])):
                record = dict(value) if isinstance(value, Mapping) else {"definition": value}
                record.setdefault("owner", owner)
                record.setdefault("view_name", view_name)
                result.append(record)
        if result:
            return result
    # A mapping keyed by view name is also accepted.
    return [dict(value, view_name=key) if isinstance(value, Mapping) else {"view_name": key, "definition": value} for key, value in data.items()]


def _load_path(path: Path | None) -> Any:
    if path is None:
        return []
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_relation_assets(paths: Iterable[Path | None]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        data = _load_path(path)
        if isinstance(data, Mapping):
            value = data.get("relationships", data.get("relations", data.get("reviews", data.get("items", data))) )
            data = value if isinstance(value, list) else []
        if not isinstance(data, list):
            continue
        for row in data:
            if isinstance(row, Mapping):
                rows.append(dict(row))
    return rows


def _asset_identity(row: Mapping[str, Any]) -> tuple[tuple[str, tuple[str, ...]], tuple[str, tuple[str, ...]]]:
    shared_keys = _as_list(_field(row, "join_keys", default=[]))
    left_columns = _as_list(_field(row, "from_columns", "source_columns", default=[])) or shared_keys
    right_columns = _as_list(_field(row, "to_columns", "target_columns", default=[])) or shared_keys
    left = (normalize_identifier(str(_field(row, "from_table", "source_table", default=""))), tuple(left_columns))
    right = (normalize_identifier(str(_field(row, "to_table", "target_table", default=""))), tuple(right_columns))
    return tuple(sorted((left, right)))  # type: ignore[return-value]


def _risk_class(parsed: ParsedRelation, parse_warnings: Sequence[str]) -> str:
    if any(x in parse_warnings for x in ("dynamic_sql", "non_select_statement")):
        return "rejected"
    if (
        parsed.function_wrapped
        or "union_branch_semantics" in parse_warnings
        or "aggregation_or_grain_change" in parse_warnings
        or "definition_truncated" in parse_warnings
        or "expression_concatenation" in parse_warnings
    ):
        return "recipe_candidate"
    if parsed.outer_join or parsed.qualifiers:
        return "partial"
    return "candidate"


def _existing_match(
    candidate: Mapping[str, Any],
    formal: Sequence[Mapping[str, Any]],
    reviews: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any] | None, str | None, str | None]:
    key = _asset_identity(candidate)
    for scope, assets in (("formal", formal), ("review", reviews)):
        for asset in assets:
            try:
                if _asset_identity(asset) == key:
                    return dict(asset), "exact", scope
            except Exception:
                continue
    # A formal relation with only a subset of the view key is a conflict, not a
    # duplicate: silently collapsing it would lose a composite-key column.
    cfrom = set(_as_list(candidate.get("from_columns")))
    cto = set(_as_list(candidate.get("to_columns")))
    for scope, assets in (("formal", formal), ("review", reviews)):
        for asset in assets:
            afrom, ato = set(_as_list(asset.get("from_columns"))), set(_as_list(asset.get("to_columns")))
            same_direction = (
                normalize_identifier(str(asset.get("from_table", ""))) == normalize_identifier(str(candidate.get("from_table", "")))
                and normalize_identifier(str(asset.get("to_table", ""))) == normalize_identifier(str(candidate.get("to_table", "")))
                and (afrom < cfrom or ato < cto)
            )
            reverse_direction = (
                normalize_identifier(str(asset.get("from_table", ""))) == normalize_identifier(str(candidate.get("to_table", "")))
                and normalize_identifier(str(asset.get("to_table", ""))) == normalize_identifier(str(candidate.get("from_table", "")))
                and (afrom < cto or ato < cfrom)
            )
            if same_direction or reverse_direction:
                return dict(asset), "formal_subset", scope
    return None, None, None


def ingest_views(view_data: Any, formal: Sequence[Mapping[str, Any]] = (), reviews: Sequence[Mapping[str, Any]] = ()) -> dict[str, Any]:
    """Return deterministic review-only intake output for view metadata."""

    dependencies: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    for raw in _view_records(view_data):
        owner = str(_field(raw, "owner", "schema", "view_owner", default="HIS")).strip().upper()
        view_name = str(_field(raw, "view_name", "view", "name", "object_name", default="")).strip().upper()
        sql = str(_field(raw, "definition", "ddl", "sql", "view_sql", "text", default=""))
        raw_status = _field(raw, "status", "object_status", default=None)
        if raw_status is None and "valid" in raw:
            raw_status = "VALID" if bool(raw.get("valid")) else "INVALID"
        status = str(raw_status or "VALID").upper()
        parsed = parse_sql(sql)
        if bool(raw.get("definition_truncated")):
            parsed["warnings"] = sorted(set([*parsed["warnings"], "definition_truncated"]))
        # Recompute the fingerprint from the captured definition.  A caller
        # supplied hash is never trusted as evidence (and is not copied into
        # output if it disagrees with the actual text).
        sha = source_sql_sha256(sql)
        base = {
            "owner": owner,
            "view": view_name,
            "source_sql_sha256": sha,
            "status": status,
            "runtime_status": str(_field(raw, "runtime_status", default="runtime_skipped")).lower(),
            "definition_truncated": bool(raw.get("definition_truncated")),
            "dialect": str(_field(raw, "dialect", default="oracle")).lower(),
        }
        for table in parsed["tables"]:
            dependencies.append({**base, "dependency_type": "view_to_table", "table": table, "intake_status": "dependency"})
        if status != "VALID":
            unresolved.append({**base, "intake_status": "unresolved", "reason": "view_not_valid"})
            continue
        if not sql.strip():
            unresolved.append({**base, "intake_status": "unresolved", "reason": "definition_missing"})
        if parsed["warnings"] and "join_key_unresolved" in parsed["warnings"]:
            unresolved.append({**base, "intake_status": "unresolved", "reason": "join_key_unresolved", "warnings": parsed["warnings"]})
        for relation in parsed["relations"]:
            candidate = {
                **base,
                "branch": relation.branch,
                "from_table": relation.from_table,
                "from_columns": relation.from_columns,
                "to_table": relation.to_table,
                "to_columns": relation.to_columns,
                "join_condition": sanitize_sql(relation.join_condition),
                "qualifiers": sorted(set(relation.qualifiers)),
                "outer_join": relation.outer_join,
                "function_wrapped": relation.function_wrapped,
                "source_fragment": relation.source_fragment,
                "warnings": parsed["warnings"],
            }
            matched, match_type, match_scope = _existing_match(candidate, formal, reviews)
            candidate["existing_relation_id"] = _field(
                matched or {}, "id", "relation_id", "relationship_id", "key", default=None
            )
            candidate["existing_scope"] = match_scope
            if match_type == "exact":
                candidate["intake_status"] = "existing"
                candidate["confidence"] = "existing"
                existing_qual = sorted(set(_as_list((matched or {}).get("qualifiers"))))
                if existing_qual != candidate["qualifiers"]:
                    conflicts.append({**candidate, "conflict_type": "qualifier_mismatch", "conflict_status": "unresolved", "existing_qualifiers": existing_qual})
            elif match_type == "formal_subset":
                candidate["intake_status"] = "partial"
                candidate["confidence"] = "C"
                conflicts.append({**candidate, "conflict_type": "existing_relation_missing_composite_key", "conflict_status": "unresolved"})
            else:
                candidate["intake_status"] = _risk_class(relation, parsed["warnings"])
                candidate["confidence"] = "C"
            records.append(candidate)
        if not parsed["relations"] and parsed["warnings"]:
            unresolved.append({**base, "intake_status": "unresolved", "reason": ";".join(parsed["warnings"]), "warnings": parsed["warnings"]})
    # Keep exact records in the main candidates list, with category views for
    # callers that want to route dependency/review/recipe work separately.
    key = lambda x: json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    dependencies = sorted({key(x): x for x in dependencies}.values(), key=key)
    records = sorted({key(x): x for x in records}.values(), key=key)
    conflicts = sorted({key(x): x for x in conflicts}.values(), key=key)
    unresolved = sorted({key(x): x for x in unresolved}.values(), key=key)
    output = {
        "schema_version": "136-his-view-relation-intake.v1",
        "formal_assets_modified": False,
        "dependencies": dependencies,
        "candidates": records,
        "existing": [x for x in records if x["intake_status"] == "existing"],
        "existing_formal": [x for x in records if x["intake_status"] == "existing" and x.get("existing_scope") == "formal"],
        "existing_review": [x for x in records if x["intake_status"] == "existing" and x.get("existing_scope") == "review"],
        "partial": [x for x in records if x["intake_status"] == "partial"],
        "recipe_candidates": [x for x in records if x["intake_status"] == "recipe_candidate"],
        "recipe_candidate": [x for x in records if x["intake_status"] == "recipe_candidate"],
        "rejected": [x for x in records if x["intake_status"] == "rejected"],
        "unresolved": unresolved,
        "conflicts": conflicts,
    }
    output["summary"] = {
        "views": len(_view_records(view_data)),
        "dependencies": len(dependencies),
        "relations": len(records),
        "existing": len(output["existing"]),
        "existing_formal": len(output["existing_formal"]),
        "existing_review": len(output["existing_review"]),
        "candidate": sum(1 for x in records if x["intake_status"] == "candidate"),
        "partial": len(output["partial"]),
        "recipe_candidate": len(output["recipe_candidates"]),
        "rejected": len(output["rejected"]),
        "unresolved": len(unresolved),
        "conflicts": len(conflicts),
    }
    return output


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline, review-only HIS view relation intake")
    parser.add_argument("--views", "--input", "--view-metadata", dest="views", required=True, type=Path)
    parser.add_argument("--relationships", "--formal", dest="formal", type=Path)
    parser.add_argument("--reviews", dest="reviews", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    view_data = _load_path(args.views)
    assets = load_relation_assets([args.formal, args.reviews])
    formal: list[dict[str, Any]] = []
    reviews: list[dict[str, Any]] = []
    for row in assets:
        if str(_field(row, "review_status", "status", "intake_status", default="")).lower() in {"draft", "pending", "candidate", "partial"}:
            reviews.append(row)
        else:
            formal.append(row)
    result = ingest_views(view_data, formal, reviews)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
