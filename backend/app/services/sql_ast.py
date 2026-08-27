"""144 S2/S3: SQL AST gate built on a pinned sqlglot (144 §4.4).

Regex checks remain as fail-closed pre-screening only; structural decisions
(large-table bounds, tautologies, dependencies) come from the AST.
Unparseable SQL or unsupported dialects fail closed as unresolved.
"""
from __future__ import annotations

import re
from typing import Any

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

PARSER_VERSION = f"sqlglot@{sqlglot.__version__}"

# dialect matrix (144 §4.4): Oracle 11g / PostgreSQL / MySQL / SQL Server / Vastbase
_DIALECT_MAP = {
    "oracle": "oracle",
    "postgresql": "postgres",
    "postgres": "postgres",
    "vastbase": "postgres",  # Vastbase G100 speaks the PG wire/grammar
    "mysql": "mysql",
    "sqlserver": "tsql",
    "mssql": "tsql",
    "tsql": "tsql",
}

# Structural large-table policies (144 §4.4): table -> required bounded column(s).
BIG_TABLE_POLICY: dict[str, dict[str, Any]] = {
    "HIS.LAB_RESULT": {"required_columns": ["TEST_NO"], "label": "HIS 检验结果亿行表"},
    "LAB_RESULT": {"required_columns": ["TEST_NO"], "label": "HIS 检验结果亿行表"},
    "HIS.INP_BILL_DETAIL": {
        "required_columns": [["PATIENT_ID", "VISIT_ID"]],
        "label": "住院费用明细巨表",
    },
    "INP_BILL_DETAIL": {
        "required_columns": [["PATIENT_ID", "VISIT_ID"]],
        "label": "住院费用明细巨表",
    },
}


class SQLParseError(ValueError):
    """SQL could not be parsed → unresolved, never silently allowed."""


class UnsupportedDialectError(ValueError):
    """Dialect outside the pinned matrix → fail closed."""


def _to_sqlglot_dialect(dialect: str) -> str:
    mapped = _DIALECT_MAP.get((dialect or "").lower())
    if not mapped:
        raise UnsupportedDialectError(f"不支持的 SQL 方言（fail-closed）: {dialect}")
    return mapped


def parse_sql(sql: str, dialect: str = "oracle") -> dict[str, Any]:
    """Parse SQL with the pinned parser; return AST handle metadata.

    Raises SQLParseError / UnsupportedDialectError — callers must treat both
    as unresolved (fail-closed), never fall back to regex-pass.
    """
    if not (sql or "").strip():
        raise SQLParseError("空 SQL")
    gdialect = _to_sqlglot_dialect(dialect)
    try:
        tree = sqlglot.parse_one(sql, read=gdialect)
    except ParseError as exc:
        raise SQLParseError(f"SQL 解析失败（unresolved）: {str(exc)[:200]}") from exc
    except Exception as exc:  # any other parser failure is still unresolved
        raise SQLParseError(f"SQL 解析失败（unresolved）: {type(exc).__name__}") from exc
    return {"tree": tree, "dialect": gdialect, "parser_version": PARSER_VERSION}


def _full_name(node: exp.Table) -> str:
    parts = [p.name for p in node.parts if p.name]
    return ".".join(parts).upper() if parts else node.sql().upper()


def extract_table_dependencies(sql: str, dialect: str = "oracle") -> dict[str, Any]:
    """Return physical table refs (CTEs excluded) and join conditions."""
    parsed = parse_sql(sql, dialect)
    tree: exp.Expression = parsed["tree"]
    cte_names = {
        cte.alias_or_name.upper() for cte in tree.find_all(exp.CTE)
    }
    tables: list[dict[str, Any]] = []
    seen: set[str] = set()
    for node in tree.find_all(exp.Table):
        name = _full_name(node)
        if not name or name in cte_names or name.startswith("("):
            continue
        if name in seen:
            continue
        seen.add(name)
        tables.append({"name": name, "kind": "table"})
    joins = []
    for node in tree.find_all(exp.Join):
        cond = node.args.get("on")
        joins.append({"on": cond.sql() if cond is not None else None, "kind": str(node.kind)})
    return {"tables": tables, "joins": joins, "ctes": sorted(cte_names)}


def _is_tautology(condition: exp.Expression) -> bool:
    """True for `1=1`, `X=X`-style always-true predicates used as fake bounds."""
    if isinstance(condition, exp.Paren):
        inner = condition.unnest()
        return _is_tautology(inner)
    if isinstance(condition, exp.EQ):
        left, right = condition.this, condition.expression
        if isinstance(left, exp.Literal) and isinstance(right, exp.Literal):
            return left.this == right.this
        # column = same column (no casts) — always true for non-null, fake bound
        if isinstance(left, exp.Column) and isinstance(right, exp.Column):
            return left.sql() == right.sql()
    if isinstance(condition, exp.Boolean):
        return bool(condition.this)
    return False


def _predicates_provide_bound(condition: exp.Expression, columns: set[str]) -> bool:
    """A real bound exists when a required column is constrained by a literal
    or by an IN-subquery against a non-tautological predicate."""
    for eq in condition.find_all(exp.EQ):
        if _is_tautology(eq):
            continue
        pair = (eq.this, eq.expression)
        for side, other in (pair, pair[::-1]):
            if isinstance(side, exp.Column) and side.name.upper() in columns:
                if isinstance(other, (exp.Literal, exp.Parameter, exp.Placeholder, exp.Cast)):
                    return True
                if isinstance(other, exp.Column) and other.sql() != side.sql():
                    # correlated bound to another column (e.g. subquery alias)
                    return True
    for node in condition.find_all(exp.In):
        this = node.this
        if isinstance(this, exp.Column) and this.name.upper() in columns:
            return True
    return False


def check_big_table_policy(sql: str, dialect: str = "oracle") -> dict[str, Any]:
    """Structurally verify bounded access to protected large tables."""
    parsed = parse_sql(sql, dialect)
    tree: exp.Expression = parsed["tree"]
    violations: list[str] = []

    # collect CTE outputs so CTE reads are not physical table reads
    cte_names = {cte.alias_or_name.upper() for cte in tree.find_all(exp.CTE)}
    sql_upper = (sql or "").upper()

    for node in tree.find_all(exp.Table):
        name = _full_name(node)
        if not name or name in cte_names:
            continue
        short = name.split(".")[-1]
        policy_key = name if name in BIG_TABLE_POLICY else (short if short in BIG_TABLE_POLICY else None)
        if not policy_key:
            continue
        policy = BIG_TABLE_POLICY[policy_key]
        required: list = policy["required_columns"]
        required_cols = {c for entry in required for c in (entry if isinstance(entry, list) else [entry])}

        # gather all predicates attached to selects reading this table
        found_bound = False
        for select in tree.find_all(exp.Select):
            reads_table = any(_full_name(t) == name for t in select.find_all(exp.Table))
            if not reads_table:
                continue
            for cond in select.find_all(exp.Where):
                if _predicates_provide_bound(cond.this, required_cols):
                    found_bound = True
            for join in select.find_all(exp.Join):
                on = join.args.get("on")
                if on is not None and _predicates_provide_bound(on, required_cols):
                    found_bound = True
        # ROWNUM bound also acceptable for Oracle-style sampling
        if not found_bound and re.search(r"\bROWNUM\b", sql_upper):
            found_bound = True
        if not found_bound:
            violations.append(
                f"大表 {policy_key}（{policy['label']}）缺少结构化限定："
                f"必须对 {'/'.join(sorted(required_cols))} 施加绑定（WHERE 1=1 等恒真条件不算限定）"
            )
    return {"ok": not violations, "violations": violations, "parser_version": PARSER_VERSION}
