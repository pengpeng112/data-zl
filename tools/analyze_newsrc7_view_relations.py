"""plan159: extract relation candidates from view/routine SQL of the 7-source snapshots.

Read-only offline analysis over local snapshot JSONs (no DB access).
- Oracle snapshots: view_definitions (ALL_VIEWS/USER_VIEWS TEXT).
- SQLServer snapshot: routines[].routine_definition + dependencies edges.
Outputs relation_candidates.json grouped by system with evidence and join
conditions; dependency edges are kept separate as lineage evidence (never
promoted to formal relations without review, per sql-relation-intake rules).
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import sys
from collections import defaultdict
from pathlib import Path

import sqlglot
from sqlglot import exp

# Routine bodies can contain unsupported vendor syntax.  Do not echo SQL text
# into logs when sqlglot falls back to Command nodes; counts below record it.
logging.getLogger("sqlglot").setLevel(logging.ERROR)

PACKAGE = Path(__file__).resolve().parents[1] / "开发起步包" / "数据资产_七系统源端资产包"

SYSTEMS = {
    "sddw": {"label": "山大地纬HIS", "dialect": "oracle", "sources": [("views", "view_definitions")]},
    "bloodold": {"label": "老输血系统", "dialect": "oracle", "sources": [("views", "view_definitions")]},
    "bloodnew": {"label": "新输血系统", "dialect": "tsql", "sources": [("routines", "routines")]},
    "queue": {"label": "叫号系统", "dialect": "mysql", "sources": []},
}


def normalize_table(table: exp.Table, dialect: str) -> str | None:
    parts = table.parts or []
    names = []
    for part in parts:
        name = part.name
        if not name:
            return None
        names.append(name.upper())
    if not names:
        return None
    return ".".join(names)


def strip_tsql_routine_header(sql_text: str) -> str:
    """Drop the CREATE PROC/FUNCTION header so sqlglot parses the body only."""
    stripped = sql_text.strip()
    if not re.match(r"(?is)^\s*CREATE\s+(PROC|PROCEDURE|FUNCTION)\b", stripped):
        return stripped
    # body starts after the first standalone AS following the parameter block
    match = re.search(r"(?is)\bAS\b", stripped)
    if not match:
        return stripped
    return stripped[match.end():]


ORACLE_INTERNAL_TABLE_RE = re.compile(
    r"^(SYS|SYSTEM|DEF\$|MVIEW\$_|ALL_|USER_|DBA_|GV\$|V\$|AUD|OLS|SCHEDULER\$|WMSYS|XDB)", re.I
)


def build_owner_index(data: dict) -> dict[str, set[str]]:
    """owner -> {TABLE_NAME} from the snapshot's tables list (for qualification)."""
    index: dict[str, set[str]] = defaultdict(set)
    for table in data.get("tables", []) + data.get("views", []):
        owner = str(table.get("owner", "")).upper()
        name = str(table.get("table_name", "")).upper()
        if owner and name:
            index[owner].add(name)
    return index


def build_tsql_object_index(data: dict) -> dict[str, set[str]]:
    """table name -> fully qualified DB.SCHEMA.TABLE names from the snapshot."""
    index: dict[str, set[str]] = defaultdict(set)
    for table in data.get("tables", []) + data.get("views", []):
        database = str(table.get("database_name", "")).upper()
        schema = str(table.get("schema_name", "")).upper()
        name = str(table.get("table_name", "")).upper()
        if database and schema and name:
            index[name].add(f"{database}.{schema}.{name}")
    return index


def qualify_tsql_name(
    name: str,
    object_index: dict[str, set[str]],
    default_database: str,
    default_schema: str,
) -> str | None:
    parts = name.upper().split(".")
    if len(parts) == 3:
        return name.upper() if name.upper() in object_index.get(parts[-1], set()) else None
    if len(parts) == 2:
        candidate = f"{default_database}.{name.upper()}"
        return candidate if candidate in object_index.get(parts[-1], set()) else None
    if len(parts) == 1:
        local = f"{default_database}.{default_schema}.{name.upper()}"
        if local in object_index.get(parts[0], set()):
            return local
        matches = object_index.get(parts[0], set())
        return next(iter(matches)) if len(matches) == 1 else None
    return None


def qualify_oracle_name(name: str, owner_index: dict[str, set[str]], default_owner: str) -> str:
    """Prefix single-part table names with the owning schema when unique."""
    if "." in name:
        return name
    owners = [owner for owner, names in owner_index.items() if name in names]
    if len(owners) == 1:
        return f"{owners[0]}.{name}"
    if default_owner:
        return f"{default_owner}.{name}"
    return name


def extract_edges(sql_text: str, dialect: str) -> tuple[set[tuple], int, bool]:
    """Return equal-join edges, statement count, and whether parsing succeeded."""
    edges: set[tuple] = set()
    statements = 0
    try:
        expressions = sqlglot.parse(sql_text, dialect=dialect)
    except Exception:
        return edges, 0, False
    for tree in expressions:
        if tree is None:
            continue
        if isinstance(tree, exp.Command):
            continue
        statements += 1
        alias_map: dict[str, str] = {}
        cte_names = {cte.alias_or_name.upper() for cte in tree.find_all(exp.CTE)}
        for table in tree.find_all(exp.Table):
            if not table.db and table.name.upper() in cte_names:
                continue
            full = normalize_table(table, dialect)
            if not full:
                continue
            alias_map.setdefault(table.alias_or_name.upper(), full)
            if table.db:
                alias_map.setdefault(re.split(r"[.]", table.db)[-1].upper(), full.rsplit(".", 1)[0])

        def resolve(column: exp.Column) -> tuple[str, str] | None:
            col_name = column.name.upper()
            if not col_name:
                return None
            qualifier = column.table.upper() if column.table else ""
            base = alias_map.get(qualifier) if qualifier else None
            if base:
                return base, col_name
            # unqualified column: cannot attribute reliably
            return None

        for eq in tree.find_all(exp.EQ):
            left, right = eq.this, eq.expression
            if not (isinstance(left, exp.Column) and isinstance(right, exp.Column)):
                continue
            lhs, rhs = resolve(left), resolve(right)
            if not lhs or not rhs:
                continue
            if lhs[0] == rhs[0]:
                continue
            edges.add((lhs[0], lhs[1], rhs[0], rhs[1]))
    return edges, statements, statements > 0


def main() -> int:
    result: dict[str, dict] = {}
    for key, config in SYSTEMS.items():
        snapshot_path = PACKAGE / "snapshots" / f"{key}_snapshot.json"
        if not snapshot_path.exists():
            continue
        data = json.loads(snapshot_path.read_text(encoding="utf-8"))
        system_result = {
            "system_name_cn": config["label"],
            "dialect": config["dialect"],
            "edges": [],
            "dependency_edges": [],
            "unresolved_edges": [],
            "objects_parsed": 0,
            "objects_total": 0,
            "parse_errors": 0,
        }
        owner_index = build_owner_index(data) if config["dialect"] == "oracle" else {}
        tsql_object_index = build_tsql_object_index(data) if config["dialect"] == "tsql" else {}
        default_owner = ""
        if config["dialect"] == "oracle":
            source_meta = data.get("source", {})
            owners = source_meta.get("owners") or []
            default_owner = str(owners[0]).upper() if owners else ""
        edge_registry: dict[tuple, dict] = {}

        for kind, section in config["sources"]:
            for item in data.get(section, []):
                if kind == "views":
                    owner = str(item.get("owner", "")).upper()
                    name = str(item.get("view_name", "")).upper()
                    obj_label = f"{owner}.{name}" if owner else name
                    sql_text = item.get("text") or ""
                else:
                    db = str(item.get("database_name", "")).upper()
                    schema = str(item.get("schema_name", "")).upper()
                    name = str(item.get("routine_name", "")).upper()
                    obj_label = ".".join(p for p in (db, schema, name) if p)
                    sql_text = item.get("routine_definition") or ""
                    if item.get("definition_status") != "ok" or not sql_text:
                        system_result["parse_errors"] += 1
                        continue
                system_result["objects_total"] += 1
                if not sql_text:
                    system_result["parse_errors"] += 1
                    continue
                source_sql_sha256 = hashlib.sha256(sql_text.encode("utf-8")).hexdigest()
                if config["dialect"] == "tsql" and kind == "routines":
                    sql_text = strip_tsql_routine_header(sql_text)
                try:
                    edges, statements, parsed = extract_edges(sql_text, config["dialect"])
                except Exception:
                    system_result["parse_errors"] += 1
                    continue
                if not parsed:
                    system_result["parse_errors"] += 1
                    continue
                system_result["objects_parsed"] += 1
                for a_table, a_col, b_table, b_col in edges:
                    if config["dialect"] == "oracle":
                        a_table = qualify_oracle_name(a_table, owner_index, default_owner)
                        b_table = qualify_oracle_name(b_table, owner_index, default_owner)
                    elif config["dialect"] == "tsql":
                        resolved_a = qualify_tsql_name(a_table, tsql_object_index, db, schema)
                        resolved_b = qualify_tsql_name(b_table, tsql_object_index, db, schema)
                        if not resolved_a or not resolved_b:
                            system_result["unresolved_edges"].append({
                                "from_table": a_table,
                                "from_column": a_col,
                                "to_table": b_table,
                                "to_column": b_col,
                                "evidence_object": obj_label,
                                "source_sql_sha256": source_sql_sha256,
                                "reason": "identifier_not_resolved_to_snapshot_object",
                            })
                            continue
                        a_table, b_table = resolved_a, resolved_b
                    # Oracle 字典/物化视图内部对象不是业务关系，跳过
                    if ORACLE_INTERNAL_TABLE_RE.match(a_table.rsplit("@", 1)[0].rsplit(".", 1)[-1]) or a_table.rsplit("@", 1)[0].split(".")[0] in {"SYS", "SYSTEM"}:
                        continue
                    if ORACLE_INTERNAL_TABLE_RE.match(b_table.rsplit("@", 1)[0].rsplit(".", 1)[-1]) or b_table.rsplit("@", 1)[0].split(".")[0] in {"SYS", "SYSTEM"}:
                        continue
                    norm = (a_table, a_col, b_table, b_col)
                    flipped = (b_table, b_col, a_table, a_col)
                    slot = edge_registry.get(norm) or edge_registry.get(flipped)
                    if slot is None:
                        slot = {
                            "from_table": a_table, "from_column": a_col,
                            "to_table": b_table, "to_column": b_col,
                            "from_columns": [a_col],
                            "to_columns": [b_col],
                            "join_condition": f"{a_table}.{a_col} = {b_table}.{b_col}",
                            "source_file": str(snapshot_path.relative_to(PACKAGE.parent.parent)).replace("\\", "/"),
                            "source_sql_sha256s": [],
                            "system_code": key,
                            "dialect": config["dialect"],
                            "evidence_objects": [],
                            "evidence_kind": "view_or_routine_equal_join",
                            "intake_status": "candidate",
                            "confidence": "C",
                            "qualifiers": [],
                            "existing_relation_id": None,
                            "metadata_evidence": "both identifiers resolved to snapshot objects",
                            "validation_evidence": None,
                            "risk_note": "static SQL evidence only; cardinality and qualifiers not validated",
                            "review_required": True,
                            "directional": False,
                        }
                        edge_registry[norm] = slot
                    if obj_label not in slot["evidence_objects"]:
                        slot["evidence_objects"].append(obj_label)
                    if source_sql_sha256 not in slot["source_sql_sha256s"]:
                        slot["source_sql_sha256s"].append(source_sql_sha256)

        system_result["edges"] = sorted(
            edge_registry.values(),
            key=lambda e: (-len(e["evidence_objects"]), e["from_table"], e["to_table"]),
        )

        for dep in data.get("dependencies", []) or []:
            system_result["dependency_edges"].append({
                "referencing": ".".join(str(dep.get(k, "")).upper() for k in ("referencing_schema", "referencing_object") if dep.get(k)),
                "referenced": ".".join(str(dep.get(k, "")).upper() for k in ("referenced_schema", "referenced_entity_name") if dep.get(k)),
                "referenced_database": str(dep.get("referenced_database", "")).upper(),
            })

        result[key] = system_result

    summary = {
        key: {
            "join_edges": len(info["edges"]),
            "objects_parsed": info["objects_parsed"],
            "objects_total": info["objects_total"],
            "parse_errors": info["parse_errors"],
            "dependency_edges": len(info["dependency_edges"]),
            "unresolved_edges": len(info["unresolved_edges"]),
        }
        for key, info in result.items()
    }
    output = {"summary": summary, "systems": result}
    out_path = PACKAGE / "relation_candidates.json"
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    for key, info in result.items():
        print(f"\n== {key} ({info['system_name_cn']}) top edges ==")
        for edge in info["edges"][:12]:
            print(f"  {edge['from_table']}.{edge['from_column']} -> {edge['to_table']}.{edge['to_column']}  [{len(edge['evidence_objects'])} objects]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
