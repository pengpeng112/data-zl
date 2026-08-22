"""Build the plan-139 four-source asset package from read-only harvest snapshots.

Pure offline logic: consumes the JSON snapshots produced by
``harvest_mysql_readonly.py`` / ``harvest_sqlserver_readonly.py`` plus the
platform relation export, and emits the layered asset package defined in
plan 139 §3 (manifest/catalog/systems/objects/columns/constraints/indexes/
routines/view_inventory/view_dependencies/relation_candidates/
relation_validations/table_governance/import_plan + per-source details).

Layering rules (plan 139 §4.2) are enforced downstream by
``plan139_common.prepare_review_groups`` / ``prepare_recipe_groups``; this
builder only classifies evidence and never promotes a view JOIN to a formal
relation.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from intake_his_view_relations import ingest_views, source_sql_sha256  # noqa: E402

GENERATOR = "build_plan139_asset_package.py/1.0"
PARSER_LABEL = "intake_his_view_relations.parse_sql/136+139"

# Governance name patterns (plan 40 §2): flagged as ``pending`` with a reason,
# never deleted and never auto-excluded solely by name guessing (plan 139 S4).
GOVERNANCE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("backup_name", re.compile(r"(?i)(备份|_bak\d*$|^bak_|^bk_|20\d{2}[-_.]\d{1,2}[-_.]?\d{0,2}$|_20\d{2}$)")),
    ("temp_name", re.compile(r"(?i)^(#|tmp_|temp_|t_tmp|中间表)")),
    ("log_name", re.compile(r"(?i)(^log_|_log$|^log$|日志)")),
    ("report_temp_name", re.compile(r"(?i)(报表临时|临时结果)")),
    ("interface_middleware", re.compile(r"(?i)(_interface$|^interface_|_mid$|中间库)")),
)

SYSTEMS: dict[str, dict[str, Any]] = {
    "CORE2DB": {
        "system_code": "CORE2DB",
        "system_name_cn": "门诊病历",
        "source_code": "core2db_mysql_10_10_8_135",
        "source_name_cn": "门诊病历 MySQL 业务库",
        "db_type": "mysql",
        "host": "10.10.8.135",
        "port": 3306,
        "databases": ["core2db"],
        "credential_ref": "file:///etc/data-asset/credentials/core2db_mysql_10_10_8_135.readonly",
        "engine_label": "mysql",
        "baseline": {"tables": 531, "views": 37, "procs": None},
    },
    "PHYSICAL_EXAM": {
        "system_code": "PHYSICAL_EXAM",
        "system_name_cn": "体检",
        "source_code": "physical_exam_sqlserver_10_10_10_96",
        "source_name_cn": "体检 SQL Server 业务实例",
        "db_type": "sqlserver",
        "host": "10.10.10.96",
        "port": 1433,
        "databases": ["EIS", "JZCIS", "ZONEKINGNET"],
        "credential_ref": "file:///etc/data-asset/credentials/physical_exam_sqlserver_10_10_10_96.readonly",
        "engine_label": "sqlserver",
        "baseline": {"tables": 501, "views": 77, "procs": 312},
    },
    "PATHOLOGY": {
        "system_code": "PATHOLOGY",
        "system_name_cn": "病理",
        "source_code": "pathology_sqlserver_10_10_9_41",
        "source_name_cn": "病理 SQL Server 业务实例",
        "db_type": "sqlserver",
        "host": "10.10.9.41",
        "port": 1433,
        "databases": ["pitaya", "QPIS"],
        "credential_ref": "file:///etc/data-asset/credentials/pathology_sqlserver_10_10_9_41.readonly",
        "engine_label": "sqlserver",
        "baseline": {"tables": 264, "views": 30, "procs": 20},
    },
    "OCCUPATIONAL_DISEASE": {
        "system_code": "OCCUPATIONAL_DISEASE",
        "system_name_cn": "职业病",
        "source_code": "occupational_disease_sqlserver_10_10_8_96",
        "source_name_cn": "职业病 SQL Server 业务库",
        "db_type": "sqlserver",
        "host": "10.10.8.96",
        "port": 1433,
        "databases": ["tjdatabase4"],
        "credential_ref": "file:///etc/data-asset/credentials/occupational_disease_sqlserver_10_10_8_96.readonly",
        "engine_label": "sqlserver",
        "baseline": {"tables": 269, "views": 22, "procs": 13},
    },
    # 143 号：医院 OA（万户 ezOFFICE）纳入；多 schema（ezoffice/dbo）故不进
    # SINGLE_DB_SYSTEMS，命名空间为 OA.EZOFFICE / OA.DBO。
    "OA": {
        "system_code": "OA",
        "system_name_cn": "OA办公系统",
        "source_code": "oa_sqlserver_10_10_10_69",
        "source_name_cn": "医院OA（万户 ezOFFICE）SQL Server 业务库",
        "db_type": "sqlserver",
        "host": "10.10.10.69",
        "port": 1433,
        "databases": ["oa"],
        "credential_ref": "file:///etc/data-asset/credentials/oa_sqlserver_10_10_10_69.readonly",
        "engine_label": "sqlserver",
        "baseline": {"tables": 1681, "views": 4, "procs": 26},
    },
}

SINGLE_DB_SYSTEMS = {"CORE2DB", "OCCUPATIONAL_DISEASE"}


def _ns_upper(value: Any) -> str:
    return str(value or "").strip().upper()


def namespace_for(system: Mapping[str, Any], database: Any, schema: Any = None) -> str:
    """Stable namespace: ``DB`` for single-database sources, ``DB.SCHEMA`` otherwise."""
    db = _ns_upper(database)
    if system["system_code"] in SINGLE_DB_SYSTEMS:
        return db
    schema = _ns_upper(schema) or "DBO"
    return f"{db}.{schema}"


def governance_flag(object_name: str) -> tuple[str, str]:
    """Return (status, reason); name guessing only flags ``pending``, never deletes."""
    for reason, pattern in GOVERNANCE_PATTERNS:
        if pattern.search(str(object_name or "")):
            return "pending", reason
    return "keep", ""


def load_snapshot(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_csv(path: Path, fieldnames: Sequence[str], rows: Iterable[Mapping[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in fieldnames})
            count += 1
    return count


def _dedup(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    output: list[dict[str, Any]] = []
    for row in rows:
        key = json.dumps(row, ensure_ascii=False, sort_keys=True, default=str)
        if key not in seen:
            seen.add(key)
            output.append(row)
    return output


def build_source(system: Mapping[str, Any], snapshot: Mapping[str, Any], intake: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize one snapshot into package rows (objects/columns/.../views)."""
    code = system["system_code"]
    source_code = system["source_code"]
    mysql = system["engine_label"] == "mysql"

    objects: list[dict[str, Any]] = []
    columns: list[dict[str, Any]] = []
    constraints: list[dict[str, Any]] = []
    indexes: list[dict[str, Any]] = []
    routines: list[dict[str, Any]] = []
    view_records: list[dict[str, Any]] = []
    fk_relations: list[dict[str, Any]] = []

    if mysql:
        for row in snapshot.get("tables", []):
            ns = namespace_for(system, row.get("database_name"))
            name = str(row.get("table_name") or "")
            objects.append({
                "system_code": code, "source_code": source_code, "namespace": ns,
                "object_name": name, "object_type": "table",
                "estimated_rows": row.get("estimated_rows"), "comment": row.get("comment"),
                "object_key": f"{source_code}|{ns}|{name.upper()}",
            })
        for row in snapshot.get("views", []):
            ns = namespace_for(system, row.get("database_name"))
            name = str(row.get("view_name") or "")
            definition = row.get("view_definition")
            objects.append({
                "system_code": code, "source_code": source_code, "namespace": ns,
                "object_name": name, "object_type": "view", "estimated_rows": None,
                "comment": None, "object_key": f"{source_code}|{ns}|{name.upper()}",
            })
            view_records.append({
                "owner": ns, "view_name": name, "definition": definition or "",
                "dialect": "mysql", "status": "VALID" if definition else "INVALID",
            })
        for row in snapshot.get("columns", []):
            ns = namespace_for(system, row.get("database_name"))
            name = str(row.get("table_name") or "")
            columns.append({
                "system_code": code, "source_code": source_code, "namespace": ns,
                "object_name": name, "object_type": "table_or_view",
                "column_name": row.get("column_name"), "ordinal": row.get("ordinal_position"),
                "data_type": row.get("data_type"), "nullable": row.get("is_nullable"),
                "column_key": row.get("column_key"), "comment": row.get("comment"),
                "object_key": f"{source_code}|{ns}|{name.upper()}",
            })
        grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
        for row in snapshot.get("keys", []):
            grouped[(
                namespace_for(system, row.get("database_name")),
                str(row.get("table_name") or ""),
                str(row.get("constraint_name") or ""),
            )].append(row)
        for (ns, table, cname), rows in sorted(grouped.items()):
            ctype = str(rows[0].get("constraint_type") or "").upper()
            constraints.append({
                "system_code": code, "source_code": source_code, "namespace": ns,
                "object_name": table, "constraint_name": cname,
                "constraint_type": "PRIMARY KEY" if "PRIMARY" in ctype else "UNIQUE",
                "columns": ",".join(str(r.get("column_name")).upper() for r in sorted(rows, key=lambda r: int(r.get("ordinal_position") or 0))),
            })
        grouped_fk: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
        for row in snapshot.get("foreign_keys", []):
            grouped_fk[(
                namespace_for(system, row.get("database_name")),
                str(row.get("table_name") or ""),
                str(row.get("constraint_name") or ""),
            )].append(row)
        for (ns, table, cname), rows in sorted(grouped_fk.items()):
            ordered = sorted(rows, key=lambda r: int(r.get("ordinal_position") or 0))
            ref_ns = namespace_for(system, ordered[0].get("referenced_database"))
            fk_relations.append({
                "constraint_name": cname,
                "from_table": f"{ns}.{table}".upper(),
                "from_columns": ",".join(str(r.get("column_name")).upper() for r in ordered),
                "to_table": f"{ref_ns}.{ordered[0].get('referenced_table')}".upper(),
                "to_columns": ",".join(str(r.get("referenced_column")).upper() for r in ordered),
            })
            constraints.append({
                "system_code": code, "source_code": source_code, "namespace": ns,
                "object_name": table, "constraint_name": cname, "constraint_type": "FOREIGN KEY",
                "columns": ",".join(str(r.get("column_name")).upper() for r in ordered),
                "references": f"{ref_ns}.{ordered[0].get('referenced_table')}("
                + ",".join(str(r.get("referenced_column")).upper() for r in ordered) + ")",
            })
        for row in snapshot.get("indexes", []):
            indexes.append({
                "system_code": code, "source_code": source_code,
                "namespace": namespace_for(system, row.get("database_name")),
                "object_name": row.get("table_name"), "index_name": row.get("index_name"),
                "non_unique": row.get("non_unique"), "ordinal": row.get("ordinal_position"),
                "column_name": row.get("column_name"), "index_type": row.get("index_type"),
            })
    else:
        for row in snapshot.get("tables", []):
            ns = namespace_for(system, row.get("database_name"), row.get("schema_name"))
            name = str(row.get("table_name") or "")
            objects.append({
                "system_code": code, "source_code": source_code, "namespace": ns,
                "object_name": name, "object_type": "table",
                "estimated_rows": row.get("estimated_rows"), "comment": row.get("comment"),
                "object_key": f"{source_code}|{ns}|{name.upper()}",
            })
        for row in snapshot.get("views", []):
            ns = namespace_for(system, row.get("database_name"), row.get("schema_name"))
            name = str(row.get("view_name") or "")
            definition = row.get("view_definition")
            objects.append({
                "system_code": code, "source_code": source_code, "namespace": ns,
                "object_name": name, "object_type": "view", "estimated_rows": None,
                "comment": row.get("comment"), "object_key": f"{source_code}|{ns}|{name.upper()}",
            })
            view_records.append({
                "owner": ns, "view_name": name, "definition": definition or "",
                "dialect": "sqlserver", "status": "VALID" if definition else "INVALID",
            })
        for row in snapshot.get("columns", []):
            ns = namespace_for(system, row.get("database_name"), row.get("schema_name"))
            name = str(row.get("object_name") or "")
            columns.append({
                "system_code": code, "source_code": source_code, "namespace": ns,
                "object_name": name, "object_type": str(row.get("object_type") or "").lower(),
                "column_name": row.get("column_name"), "ordinal": row.get("column_id"),
                "data_type": row.get("data_type"), "nullable": row.get("is_nullable"),
                "column_key": None, "comment": row.get("comment"),
                "object_key": f"{source_code}|{ns}|{name.upper()}",
            })
        grouped = defaultdict(list)
        for row in snapshot.get("keys", []):
            grouped[(
                namespace_for(system, row.get("database_name"), row.get("schema_name")),
                str(row.get("table_name") or ""),
                str(row.get("constraint_name") or ""),
            )].append(row)
        for (ns, table, cname), rows in sorted(grouped.items()):
            ctype = str(rows[0].get("type_desc") or "").upper()
            constraints.append({
                "system_code": code, "source_code": source_code, "namespace": ns,
                "object_name": table, "constraint_name": cname,
                "constraint_type": "PRIMARY KEY" if "PRIMARY" in ctype else "UNIQUE",
                "columns": ",".join(str(r.get("column_name")).upper() for r in sorted(rows, key=lambda r: int(r.get("key_ordinal") or 0))),
            })
        grouped_fk = defaultdict(list)
        for row in snapshot.get("foreign_keys", []):
            grouped_fk[(
                namespace_for(system, row.get("database_name"), row.get("child_schema")),
                str(row.get("child_table") or ""),
                str(row.get("constraint_name") or ""),
            )].append(row)
        for (ns, table, cname), rows in sorted(grouped_fk.items()):
            ordered = sorted(rows, key=lambda r: int(r.get("ordinal_position") or 0))
            ref_ns = namespace_for(system, row.get("database_name"), ordered[0].get("parent_schema"))
            fk_relations.append({
                "constraint_name": cname,
                "from_table": f"{ns}.{table}".upper(),
                "from_columns": ",".join(str(r.get("child_column")).upper() for r in ordered),
                "to_table": f"{ref_ns}.{ordered[0].get('parent_table')}".upper(),
                "to_columns": ",".join(str(r.get("parent_column")).upper() for r in ordered),
                "is_disabled": ordered[0].get("is_disabled"),
            })
            constraints.append({
                "system_code": code, "source_code": source_code, "namespace": ns,
                "object_name": table, "constraint_name": cname, "constraint_type": "FOREIGN KEY",
                "columns": ",".join(str(r.get("child_column")).upper() for r in ordered),
                "references": f"{ref_ns}.{ordered[0].get('parent_table')}("
                + ",".join(str(r.get("parent_column")).upper() for r in ordered) + ")",
                "is_disabled": ordered[0].get("is_disabled"),
            })
        for row in snapshot.get("indexes", []):
            indexes.append({
                "system_code": code, "source_code": source_code,
                "namespace": namespace_for(system, row.get("database_name"), row.get("schema_name")),
                "object_name": row.get("table_name"), "index_name": row.get("index_name"),
                "non_unique": 0 if row.get("is_unique") else 1, "ordinal": row.get("key_ordinal"),
                "column_name": row.get("column_name"), "index_type": row.get("type_desc"),
            })

    for row in snapshot.get("routines", []):
        routines.append({
            "system_code": code, "source_code": source_code,
            "namespace": namespace_for(system, row.get("database_name"), row.get("schema_name")),
            "object_name": row.get("routine_name"), "routine_type": row.get("routine_type"),
            "definition_status": row.get("definition_status") or ("ok" if row.get("routine_definition") else "not_collected"),
            "definition_sha256": (hashlib.sha256(str(row.get("routine_definition")).encode("utf-8")).hexdigest()
                                  if row.get("routine_definition") else None),
        })
    for row in snapshot.get("triggers", []):
        routines.append({
            "system_code": code, "source_code": source_code,
            "namespace": namespace_for(system, row.get("database_name"), row.get("schema_name")),
            "object_name": row.get("trigger_name"), "routine_type": f"TRIGGER ({row.get('trigger_type')})",
            "definition_status": "ok" if row.get("trigger_definition") else "not_collected",
            "definition_sha256": (hashlib.sha256(str(row.get("trigger_definition")).encode("utf-8")).hexdigest()
                                  if row.get("trigger_definition") else None),
            "parent_object": row.get("parent_object"),
        })
    for row in snapshot.get("synonyms", []):
        routines.append({
            "system_code": code, "source_code": source_code,
            "namespace": namespace_for(system, row.get("database_name"), row.get("schema_name")),
            "object_name": row.get("synonym_name"), "routine_type": "SYNONYM",
            "definition_status": "ok" if row.get("base_object") else "not_collected",
            "base_object": row.get("base_object"),
        })

    governance = []
    for row in objects:
        status, reason = governance_flag(row["object_name"])
        governance.append({
            "system_code": code, "source_code": source_code, "namespace": row["namespace"],
            "object_name": row["object_name"], "object_type": row["object_type"],
            "governance_status": status, "reason": reason or "business_or_unclassified",
            "business_name_cn": row.get("comment") or "",
            "business_name_status": "db_comment" if row.get("comment") else "pending_business_name",
        })

    return {
        "system": system,
        "snapshot": snapshot,
        "objects": _dedup(objects),
        "columns": _dedup(columns),
        "constraints": _dedup(constraints),
        "indexes": _dedup(indexes),
        "routines": _dedup(routines),
        "governance": _dedup(governance),
        "view_records": view_records,
        "fk_relations": fk_relations,
        "intake": intake,
    }


def dependency_cross_check(built: Mapping[str, Any]) -> dict[str, Any]:
    """Cross-check parsed dependencies against engine-reported dependencies."""
    snapshot = built["snapshot"]
    engine_deps: set[tuple[str, str, str]] = set()
    for row in snapshot.get("dependencies", []):
        engine_deps.add((
            _ns_upper(row.get("referenced_database")),
            _ns_upper(row.get("referenced_schema")),
            _ns_upper(row.get("referenced_entity_name")),
        ))
    parsed_deps: set[str] = set()
    for dep in built["intake"].get("dependencies", []):
        parsed_deps.add(_ns_upper(dep.get("table")))
    def _norm(triple: tuple[str, str, str]) -> str:
        db, schema, name = triple
        return f"{db}.{schema}.{name}" if schema else f"{db}.{name}"
    engine_names = {_norm(t) for t in engine_deps}
    matched = {name for name in engine_names if name in parsed_deps or name.split(".", 1)[-1] in {p.split(".", 1)[-1] for p in parsed_deps}}
    return {
        "engine_reported": len(engine_names),
        "parser_reported": len(parsed_deps),
        "engine_matched_by_parser": len(matched),
        "engine_only": sorted(engine_names - matched)[:200],
        "parser_only": sorted(parsed_deps - engine_names)[:200],
        "engine_source": "sys.sql_expression_dependencies" if engine_deps else
                         ("unavailable: information_schema.VIEW_TABLE_USAGE not visible" if built["system"]["engine_label"] == "mysql" else "none"),
    }


def build_package(
    snapshots: Mapping[str, Path],
    platform_assets: Mapping[str, Any],
    output_dir: Path,
    run_id: str,
) -> dict[str, Any]:
    formal = list(platform_assets.get("relations", []))
    reviews = list(platform_assets.get("reviews", []))
    generated_at = datetime.now(timezone.utc).isoformat()

    all_objects: list[dict[str, Any]] = []
    all_columns: list[dict[str, Any]] = []
    all_constraints: list[dict[str, Any]] = []
    all_indexes: list[dict[str, Any]] = []
    all_routines: list[dict[str, Any]] = []
    all_governance: list[dict[str, Any]] = []
    all_view_inventory: list[dict[str, Any]] = []
    all_view_dependencies: list[dict[str, Any]] = []
    all_candidates: list[dict[str, Any]] = []
    source_reports: dict[str, Any] = {}

    for system_code, system in ((code, SYSTEMS[code]) for code in sorted(snapshots)):
        snapshot_path = snapshots[system_code]
        snapshot = load_snapshot(snapshot_path)
        intake = ingest_views({"views": [
            {**rec, "runtime_status": "runtime_skipped"} for rec in _view_records_raw(snapshot, system)
        ]}, formal, reviews)
        built = build_source(system, snapshot, intake)
        cross = dependency_cross_check(built)

        inventory: dict[tuple[str, str, str], dict[str, Any]] = {}
        for view in built["view_records"]:
            definition = view["definition"] or ""
            owner_db = view["owner"].split(".", 1)[0]
            dep_rows = [d for d in intake.get("dependencies", []) if d.get("owner") == view["owner"] and d.get("view") == view["view_name"].upper()]
            cross_db = any(
                _ns_upper(str(d.get("table", "")).split(".", 1)[0]) not in {"", _ns_upper(owner_db)}
                for d in dep_rows
            )
            inventory[(system_code, view["owner"], view["view_name"].upper())] = {
                "system_code": system_code, "source_code": system["source_code"],
                "namespace": view["owner"], "view_name": view["view_name"],
                "definition_visible": bool(definition),
                "definition_sha256": source_sql_sha256(definition) if definition else None,
                "dependency_count": len(dep_rows),
                "is_cross_database": cross_db,
                "is_union": any(c.get("branch", 0) > 0 for c in intake.get("candidates", [])
                                if c.get("owner") == view["owner"] and c.get("view") == view["view_name"].upper()),
                "parse_status": "parsed" if dep_rows or definition else "definition_missing",
                "parser": PARSER_LABEL,
            }
        for cand in intake.get("unresolved", []):
            key = (system_code, cand.get("owner"), str(cand.get("view", "")).upper())
            existing = inventory.get(key)
            reason = str(cand.get("reason") or "unresolved")
            if existing:
                if not existing["parse_status"].startswith("unresolved"):
                    existing["parse_status"] = f"unresolved:{reason}"
            else:
                inventory[key] = {
                    "system_code": system_code, "source_code": system["source_code"],
                    "namespace": cand.get("owner"), "view_name": cand.get("view"),
                    "definition_visible": True, "definition_sha256": cand.get("source_sql_sha256"),
                    "dependency_count": 0, "is_cross_database": False, "is_union": False,
                    "parse_status": f"unresolved:{reason}",
                    "parser": PARSER_LABEL,
                }
        all_view_inventory.extend(inventory.values())
        for dep in intake.get("dependencies", []):
            all_view_dependencies.append({
                "system_code": system_code, "source_code": system["source_code"],
                "namespace": dep.get("owner"), "view_name": dep.get("view"),
                "referenced_object": dep.get("table"),
                "dependency_type": "view_to_table_or_view",
                "evidence": "static_parse",
            })
        engine_dep_rows: list[dict[str, Any]] = []
        view_keys = {
            (namespace_for(system, v.get("database_name"), v.get("schema_name")), str(v.get("view_name") or "").upper())
            for v in snapshot.get("views", [])
        }
        for row in snapshot.get("dependencies", []):
            referencing_ns = namespace_for(system, row.get("database_name"), row.get("referencing_schema"))
            if (referencing_ns, _ns_upper(row.get("referencing_object"))) not in view_keys:
                continue  # routine/module dependency; the view layer stays views-only
            ref_db = _ns_upper(row.get("referenced_database")) or _ns_upper(row.get("database_name"))
            engine_dep_rows.append({
                "system_code": system_code, "source_code": system["source_code"],
                "namespace": referencing_ns,
                "view_name": row.get("referencing_object"),
                "referenced_object": ".".join(p for p in (
                    ref_db, _ns_upper(row.get("referenced_schema")), _ns_upper(row.get("referenced_entity_name"))) if p),
                "dependency_type": "engine_reported",
                "evidence": "sys.sql_expression_dependencies",
            })
        all_view_dependencies.extend(engine_dep_rows)

        for cand in intake.get("candidates", []):
            all_candidates.append({
                "system_code": system_code, "source_code": system["source_code"],
                "namespace": cand.get("owner"), "view_name": cand.get("view"),
                "from_table": cand.get("from_table"), "from_columns": cand.get("from_columns"),
                "to_table": cand.get("to_table"), "to_columns": cand.get("to_columns"),
                "join_condition": cand.get("join_condition"),
                "qualifiers": "|".join(cand.get("qualifiers") or []),
                "intake_status": cand.get("intake_status"),
                "confidence": cand.get("confidence"),
                "source_sql_sha256": cand.get("source_sql_sha256"),
                "existing_relation_id": cand.get("existing_relation_id"),
                "warnings": "|".join(cand.get("warnings") or []),
                "layer": "review_draft" if cand.get("intake_status") in {"candidate", "partial"} else
                         ("recipe_draft" if cand.get("intake_status") == "recipe_candidate" else "evidence_only"),
            })

        all_objects.extend(built["objects"])
        all_columns.extend(built["columns"])
        all_constraints.extend(built["constraints"])
        all_indexes.extend(built["indexes"])
        all_routines.extend(built["routines"])
        all_governance.extend(built["governance"])

        summary = intake.get("summary", {})
        baseline = system["baseline"]
        source_reports[system_code] = {
            "source_code": system["source_code"],
            "endpoint": f"{system['host']}:{system['port']}",
            "database_version": snapshot.get("database_version"),
            "collected_at": snapshot.get("collected_at"),
            "databases": [d if isinstance(d, str) else d.get("database_name") for d in snapshot.get("databases", [])],
            "counts": {
                "objects": len(built["objects"]),
                "tables": sum(1 for o in built["objects"] if o["object_type"] == "table"),
                "views": sum(1 for o in built["objects"] if o["object_type"] == "view"),
                "columns": len(built["columns"]),
                "constraints": len(built["constraints"]),
                "indexes": len(built["indexes"]),
                "routines_triggers_synonyms": len(built["routines"]),
                "declared_foreign_keys": len(built["fk_relations"]),
                "view_dependencies_parsed": len(intake.get("dependencies", [])),
                "view_dependencies_engine": len(snapshot.get("dependencies", [])),
                "candidates_total": summary.get("relations", 0),
                "candidates_by_status": {
                    "existing": summary.get("existing", 0),
                    "candidate": summary.get("candidate", 0),
                    "partial": summary.get("partial", 0),
                    "recipe_candidate": summary.get("recipe_candidate", 0),
                    "rejected": summary.get("rejected", 0),
                    "unresolved": summary.get("unresolved", 0),
                },
                "conflicts": summary.get("conflicts", 0),
            },
            "baseline_diff": {
                "tables": (baseline.get("tables"), sum(1 for o in built["objects"] if o["object_type"] == "table")),
                "views": (baseline.get("views"), sum(1 for o in built["objects"] if o["object_type"] == "view")),
            },
            "errors": snapshot.get("errors", []),
            "dependency_cross_check": cross,
        }

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "sources").mkdir(exist_ok=True)

    counts: dict[str, int] = {}
    counts["systems"] = _write_csv(output_dir / "systems.csv",
        ["system_code", "system_name_cn", "source_code", "db_type", "endpoint", "databases", "credential_ref"],
        [{"system_code": s["system_code"], "system_name_cn": s["system_name_cn"], "source_code": s["source_code"],
          "db_type": s["db_type"], "endpoint": f"{s['host']}:{s['port']}", "databases": ",".join(s["databases"]),
          "credential_ref": s["credential_ref"]} for s in (SYSTEMS[c] for c in sorted(snapshots))])
    counts["objects"] = _write_csv(output_dir / "objects.csv",
        ["object_key", "system_code", "source_code", "namespace", "object_name", "object_type", "estimated_rows", "comment"],
        all_objects)
    counts["columns"] = _write_csv(output_dir / "columns.csv",
        ["object_key", "system_code", "source_code", "namespace", "object_name", "column_name", "ordinal", "data_type", "nullable", "column_key", "comment"],
        all_columns)
    counts["constraints"] = _write_csv(output_dir / "constraints.csv",
        ["system_code", "source_code", "namespace", "object_name", "constraint_name", "constraint_type", "columns", "references", "is_disabled"],
        all_constraints)
    counts["indexes"] = _write_csv(output_dir / "indexes.csv",
        ["system_code", "source_code", "namespace", "object_name", "index_name", "non_unique", "ordinal", "column_name", "index_type"],
        all_indexes)
    counts["routines"] = _write_csv(output_dir / "routines.csv",
        ["system_code", "source_code", "namespace", "object_name", "routine_type", "definition_status", "definition_sha256", "parent_object", "base_object"],
        all_routines)
    counts["view_inventory"] = _write_csv(output_dir / "view_inventory.csv",
        ["system_code", "source_code", "namespace", "view_name", "definition_visible", "definition_sha256",
         "dependency_count", "is_cross_database", "is_union", "parse_status", "parser"],
        _dedup(all_view_inventory))
    counts["view_dependencies"] = _write_csv(output_dir / "view_dependencies.csv",
        ["system_code", "source_code", "namespace", "view_name", "referenced_object", "dependency_type", "evidence"],
        _dedup(all_view_dependencies))
    counts["relation_candidates"] = _write_csv(output_dir / "relation_candidates.csv",
        ["system_code", "source_code", "namespace", "view_name", "from_table", "from_columns", "to_table",
         "to_columns", "join_condition", "qualifiers", "intake_status", "confidence", "source_sql_sha256",
         "existing_relation_id", "warnings", "layer"],
        _dedup(all_candidates))
    counts["table_governance"] = _write_csv(output_dir / "table_governance.csv",
        ["system_code", "source_code", "namespace", "object_name", "object_type", "governance_status", "reason", "business_name_cn", "business_name_status"],
        all_governance)

    relation_validations = {
        "run_id": run_id,
        "policy": "plan139 §4.4: bounded aggregate validation only; no patient values; per-item timeouts",
        "items": [],
        "skipped": [],
    }
    (output_dir / "relation_validations.json").write_text(
        json.dumps(relation_validations, ensure_ascii=False, indent=2), encoding="utf-8")

    fk_total = sum(report["counts"]["declared_foreign_keys"] for report in source_reports.values())
    catalog = {
        "run_id": run_id, "generated_at": generated_at, "generator": GENERATOR,
        "totals": {k: v for k, v in counts.items()},
        "declared_fk_relations": fk_total,
        "sources": source_reports,
    }
    (output_dir / "catalog.json").write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")

    import_plan = {
        "run_id": run_id,
        "policy": {
            "db_constraint_fk": "idempotent structural import as declared_foreign_key evidence",
            "view_dependencies": "dependency/lineage layer only (asset_view_dependencies)",
            "view_join_candidates": "asset_relation_reviews drafts only; never auto-promoted",
            "complex_logic": "asset_relation_recipes inactive drafts",
            "cross_system": "cross_system_pending; no formal edges this round",
            "delete_all": False,
        },
        "sources": {
            code: {
                "system_code": code,
                "source_code": SYSTEMS[code]["source_code"],
                "import_objects": report["counts"]["objects"],
                "import_columns": report["counts"]["columns"],
                "import_fk_relations": report["counts"]["declared_foreign_keys"],
                "import_review_drafts": report["counts"]["candidates_by_status"]["candidate"] + report["counts"]["candidates_by_status"]["partial"],
                "import_recipe_drafts": None,
            } for code, report in source_reports.items()
        },
    }
    (output_dir / "import_plan.json").write_text(
        json.dumps(import_plan, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "run_id": run_id, "generated_at": generated_at,
        "output_dir": str(output_dir), "counts": counts,
        "sources": source_reports, "catalog": catalog,
    }


def _view_records_raw(snapshot: Mapping[str, Any], system: Mapping[str, Any]) -> list[dict[str, Any]]:
    mysql = system["engine_label"] == "mysql"
    records = []
    for row in snapshot.get("views", []):
        if mysql:
            ns = namespace_for(system, row.get("database_name"))
        else:
            ns = namespace_for(system, row.get("database_name"), row.get("schema_name"))
        definition = row.get("view_definition")
        records.append({
            "owner": ns, "view_name": str(row.get("view_name") or ""),
            "definition": definition or "", "dialect": system["engine_label"],
            "status": "VALID" if definition else "INVALID",
        })
    return records


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", action="append", required=True,
                        help="SYSTEM_CODE=path/to/snapshot.json (repeatable)")
    parser.add_argument("--systems", default="",
                        help="comma-separated subset of SYSTEMS to build (default: all)")
    parser.add_argument("--platform-assets", type=Path, required=True,
                        help="platform relations/reviews export JSON for dedup")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args(argv)
    selected = {item.strip() for item in args.systems.split(",") if item.strip()} or set(SYSTEMS)
    unknown = selected - set(SYSTEMS)
    if unknown:
        raise SystemExit(f"unknown system codes: {', '.join(sorted(unknown))}")
    snapshots: dict[str, Path] = {}
    for item in args.snapshot:
        code, _, path = item.partition("=")
        if code not in SYSTEMS:
            raise SystemExit(f"unknown system code: {code}")
        snapshots[code] = Path(path)
    missing = [code for code in selected if code not in snapshots]
    if missing:
        raise SystemExit(f"missing snapshots: {', '.join(missing)}")
    extra = [code for code in snapshots if code not in selected]
    if extra:
        raise SystemExit(f"snapshots outside --systems selection: {', '.join(extra)}")
    platform = json.loads(args.platform_assets.read_text(encoding="utf-8"))
    result = build_package(snapshots, platform, args.output_dir, args.run_id)
    manifest = {
        "run_id": args.run_id,
        "generated_at": result["generated_at"],
        "generator": GENERATOR,
        "parser": PARSER_LABEL,
        "snapshot_files": {code: {"path": str(path), "sha256": sha256_file(path)} for code, path in snapshots.items()},
        "counts": result["counts"],
        "layering": {
            "constraints.csv": "database-declared PK/UK/FK (db_constraint evidence)",
            "view_dependencies.csv": "dependency/lineage edges only",
            "relation_candidates.csv": "view JOIN evidence; layer column routes review/recipe drafts",
            "relation_validations.json": "bounded aggregate validation outcomes or skip reasons",
        },
    }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    for code in snapshots:
        src_dir = args.output_dir / "sources" / code
        src_dir.mkdir(parents=True, exist_ok=True)
        report = result["sources"][code]
        (src_dir / "source_report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"run_id": args.run_id, "output_dir": str(args.output_dir), "counts": result["counts"]},
                     ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
