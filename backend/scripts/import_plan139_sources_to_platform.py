"""Import plan-139 four-source assets into the platform ``asset`` schema.

Layered, idempotent and dry-run by default (plan 139 §4.2/S9):

- systems/data sources/tables/views/columns via ``asset_import_upsert``;
- database-declared foreign keys -> formal structural relations
  (``declared_foreign_key`` evidence only);
- view -> table dependencies -> ``asset_view_dependencies`` (lineage layer);
- view JOIN candidates -> ``asset_relation_reviews`` drafts (never promoted);
- complex view logic -> ``asset_relation_recipes`` inactive drafts.

Never connects to business source databases.  Apply requires the fixed
confirmation string AND the current run id.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
# Inside the API container the app package lives at /app and the script is
# docker-cp'd to /tmp/plan139; probe the usual locations explicitly.
for _path in (BACKEND_DIR, Path.cwd(), Path("/app")):
    if (_path / "app").is_dir() and str(_path) not in sys.path:
        sys.path.insert(0, str(_path))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

CONFIRM_TEXT = "APPLY-PLAN139-FOUR-SOURCES"
# 143 号：OA 纳入使用独立确认串，四源串保持历史不变。
CONFIRM_TEXTS = {CONFIRM_TEXT, "APPLY-PLAN139-OA-SOURCE"}
BATCH_TAG_PREFIX = "plan139_four_sources"

SOURCE_REGISTRY: dict[str, dict[str, Any]] = {
    "CORE2DB": {
        "system_code": "CORE2DB", "system_name_cn": "门诊病历", "system_type": "OUTPATIENT_EMR",
        "source_code": "core2db_mysql_10_10_8_135", "source_name_cn": "门诊病历 MySQL 业务库",
        "db_type": "mysql", "host": "10.10.8.135", "port": 3306,
        "service_name": None, "database_name": "core2db", "service_mode": "database",
        "default_schema": "core2db", "labels": ["门诊病历", "CORE2DB"],
        "credential_ref": "file:///etc/data-asset/credentials/core2db_mysql_10_10_8_135.readonly",
    },
    "PHYSICAL_EXAM": {
        "system_code": "PHYSICAL_EXAM", "system_name_cn": "体检", "system_type": "PHYSICAL_EXAM",
        "source_code": "physical_exam_sqlserver_10_10_10_96", "source_name_cn": "体检 SQL Server 业务实例",
        "db_type": "sqlserver", "host": "10.10.10.96", "port": 1433,
        "service_name": None, "database_name": "EIS,JZCIS,ZONEKINGNET", "service_mode": "database",
        "default_schema": "EIS.dbo", "labels": ["体检", "EIS", "JZCIS", "ZONEKINGNET"],
        "credential_ref": "file:///etc/data-asset/credentials/physical_exam_sqlserver_10_10_10_96.readonly",
    },
    "PATHOLOGY": {
        "system_code": "PATHOLOGY", "system_name_cn": "病理", "system_type": "PATHOLOGY",
        "source_code": "pathology_sqlserver_10_10_9_41", "source_name_cn": "病理 SQL Server 业务实例",
        "db_type": "sqlserver", "host": "10.10.9.41", "port": 1433,
        "service_name": None, "database_name": "pitaya,QPIS", "service_mode": "database",
        "default_schema": "pitaya.dbo", "labels": ["病理", "pitaya", "QPIS", "V_BLZLST"],
        "credential_ref": "file:///etc/data-asset/credentials/pathology_sqlserver_10_10_9_41.readonly",
    },
    "OCCUPATIONAL_DISEASE": {
        "system_code": "OCCUPATIONAL_DISEASE", "system_name_cn": "职业病", "system_type": "OCCUPATIONAL",
        "source_code": "occupational_disease_sqlserver_10_10_8_96", "source_name_cn": "职业病 SQL Server 业务库",
        "db_type": "sqlserver", "host": "10.10.8.96", "port": 1433,
        "service_name": None, "database_name": "tjdatabase4", "service_mode": "database",
        "default_schema": "tjdatabase4.dbo", "labels": ["职业病", "tjdatabase4"],
        "credential_ref": "file:///etc/data-asset/credentials/occupational_disease_sqlserver_10_10_8_96.readonly",
    },
    # 143 号：医院 OA（万户 ezOFFICE）；多 schema，default_schema 指向 oa.ezoffice。
    "OA": {
        "system_code": "OA", "system_name_cn": "OA办公系统", "system_type": "OA",
        "source_code": "oa_sqlserver_10_10_10_69", "source_name_cn": "医院OA（万户 ezOFFICE）业务库",
        "db_type": "sqlserver", "host": "10.10.10.69", "port": 1433,
        "service_name": None, "database_name": "oa", "service_mode": "database",
        "default_schema": "oa.ezoffice", "labels": ["OA", "万户ezOFFICE", "ezoffice", "工作流"],
        "credential_ref": "file:///etc/data-asset/credentials/oa_sqlserver_10_10_10_69.readonly",
    },
}


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _normalize_columns(value: Any) -> str:
    """Normalize stringified-list or CSV column payloads to plain ``A,B``."""
    text = str(value or "").strip()
    if text.startswith("["):
        try:
            parsed = json.loads(text.replace("'", '"'))
            if isinstance(parsed, list):
                return ",".join(str(x).strip() for x in parsed if str(x).strip())
        except json.JSONDecodeError:
            pass
        return ",".join(p.strip(" []'\"") for p in text.split(",") if p.strip(" []'\""))
    return text


def _full_name_index(objects: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, str]]:
    index: dict[str, dict[str, str]] = {}
    for row in objects:
        full = f"{row['namespace']}.{row['object_name']}".upper()
        index[full] = dict(row)
        # Parser endpoints commonly carry only schema.table (e.g. DBO.JCXX);
        # register that form too so candidates resolve to the full namespace.
        ns_parts = row["namespace"].upper().split(".")
        if len(ns_parts) >= 2:
            index.setdefault(f"{ns_parts[-1]}.{row['object_name']}".upper(), dict(row))
        index.setdefault(row["object_name"].upper(), dict(row))
    return index


def _resolve_endpoint(index: Mapping[str, Mapping[str, Any]], name: str) -> str | None:
    """Resolve a parser endpoint name to the package's full namespace key."""
    upper = str(name or "").upper()
    if upper in index:
        row = index[upper]
        return f"{row['namespace']}.{row['object_name']}".upper()
    return None


def _identity(row: Mapping[str, Any]) -> tuple[Any, ...]:
    from plan139_common import columns_list

    left = (str(row.get("from_table", "")).upper(), tuple(columns_list(row.get("from_columns"))))
    right = (str(row.get("to_table", "")).upper(), tuple(columns_list(row.get("to_columns"))))
    return tuple(sorted((left, right)))


def _synchronize_platform_sequences(db: Any) -> int:
    from sqlalchemy import text

    tables = ("asset_relation_reviews", "asset_relation_recipes")
    for table in tables:
        qualified = f"asset.{table}"
        db.execute(
            text(
                "SELECT setval("
                f"pg_get_serial_sequence('{qualified}','id'),"
                "GREATEST("
                f"COALESCE(pg_sequence_last_value(pg_get_serial_sequence('{qualified}','id')::regclass),0),"
                f"COALESCE((SELECT MAX(id) FROM {qualified}),1)"
                "),true)"
            )
        )
    return len(tables)


def _source_identity_audit(db: Any) -> dict[str, Any]:
    """Pre-check engine/endpoint/database identity against existing sources."""
    from sqlalchemy import select

    from app.models.asset_system import AssetDataSource

    existing = db.scalars(select(AssetDataSource)).all()
    conflicts: list[dict[str, Any]] = []
    for profile in SOURCE_REGISTRY.values():
        for row in existing:
            same_endpoint = (
                (row.db_type or "").lower() == profile["db_type"]
                and (row.target_host or "") == profile["host"]
                and int(row.port or 0) == profile["port"]
            )
            if not same_endpoint:
                continue
            if row.source_code != profile["source_code"]:
                conflicts.append({
                    "new": profile["source_code"],
                    "existing": row.source_code,
                    "reason": "same engine+endpoint registered under another source_code",
                })
    return {"existing_sources": len(existing), "conflicts": conflicts}


def execute(package_dir: Path, *, run_id: str, apply: bool, confirm: str,
            validation_results: Mapping[str, Any] | None = None,
            selected_systems: Sequence[str] | None = None) -> dict[str, Any]:
    if apply and confirm not in CONFIRM_TEXTS:
        raise RuntimeError(f"apply requires --confirm in {'/'.join(sorted(CONFIRM_TEXTS))}")
    if apply and not run_id:
        raise RuntimeError("apply requires --run-id")
    batch_tag = f"{BATCH_TAG_PREFIX}_{run_id}"

    from sqlalchemy import delete, func, select

    from app.core.db import SessionLocal
    from app.models.asset import AssetRelation, AssetRelationReview, AssetTable, AssetColumn
    from app.models.asset_system import AssetDataSource, AssetSourceSchema, AssetSystem
    from app.models.lineage import AssetViewDependency
    from app.models.recipe import AssetRelationRecipe
    from app.services.asset_import_upsert import (
        rebuild_schema_inventory,
        upsert_columns,
        upsert_relations,
        upsert_tables,
    )
    from app.services.connection_identity import (
        build_connection_identity_key,
        build_database_key,
        build_endpoint_key,
        host_masked_from_target,
    )

    registry = dict(SOURCE_REGISTRY)
    if selected_systems is not None:
        unknown = set(selected_systems) - set(registry)
        if unknown:
            raise RuntimeError(f"unknown systems: {', '.join(sorted(unknown))}")
        registry = {code: registry[code] for code in selected_systems}
    objects = [row for row in _read_csv(package_dir / "objects.csv") if row["system_code"] in registry]
    columns = [row for row in _read_csv(package_dir / "columns.csv") if row["system_code"] in registry]
    constraints = _read_csv(package_dir / "constraints.csv")
    view_deps = _read_csv(package_dir / "view_dependencies.csv")
    candidates = _read_csv(package_dir / "relation_candidates.csv")

    validations_by_key: dict[tuple, dict[str, Any]] = {}
    for item in (validation_results or {}).get("items", []):
        key = (
            str(item.get("system_code")), str(item.get("view_name", "")).upper(),
            str(item.get("from_table", "")).upper(), str(item.get("to_table", "")).upper(),
            _normalize_columns(item.get("from_columns")).upper(), _normalize_columns(item.get("to_columns")).upper(),
        )
        validations_by_key[key] = item

    summary: dict[str, Any] = {
        "mode": "apply" if apply else "dry_run",
        "run_id": run_id,
        "batch_tag": batch_tag,
        "objects": len(objects),
        "columns": len(columns),
        "fk_constraints": sum(1 for r in constraints if r["constraint_type"] == "FOREIGN KEY"),
        "view_dependencies": len(view_deps),
        "candidates_in": len(candidates),
        "source_identity": None,
        "per_source": {},
        "tables_writes": 0, "tables_inserts": 0, "tables_updates": 0,
        "columns_writes": 0,
        "fk_relation_writes": 0, "fk_relation_inserts": 0, "fk_relation_updates": 0,
        "view_dependency_rows": 0, "view_dependency_replaced": 0,
        "prepared_reviews": 0, "eligible_reviews": 0, "inserted_reviews": 0,
        "skipped_existing_formal": 0, "skipped_existing_review": 0, "skipped_metadata": 0,
        "metadata_error_types": {},
        "prepared_recipes": 0, "eligible_recipes": 0, "inserted_recipes": 0,
        "skipped_existing_recipe": 0,
        "platform_before": {}, "platform_after": {},
        "formal_relations_modified_elsewhere": 0,
        "active_recipes_inserted": 0,
        "batch_active_recipes": 0,
        "sequences_synchronized": 0,
    }

    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        def _count(model: Any) -> int:
            return int(db.scalar(select(func.count()).select_from(model)) or 0)

        summary["platform_before"] = {
            "systems": _count(AssetSystem), "sources": _count(AssetDataSource),
            "tables": _count(AssetTable), "columns": _count(AssetColumn),
            "relations": _count(AssetRelation), "reviews": _count(AssetRelationReview),
            "recipes": _count(AssetRelationRecipe),
        }
        summary["source_identity"] = _source_identity_audit(db)
        if summary["source_identity"]["conflicts"]:
            raise RuntimeError(
                "duplicate physical source identity detected; refusing import: "
                + json.dumps(summary["source_identity"]["conflicts"], ensure_ascii=False)
            )
        if apply:
            summary["sequences_synchronized"] = _synchronize_platform_sequences(db)

        by_system_objects: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row in objects:
            by_system_objects[row["system_code"]].append(row)
        by_system_columns: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row in columns:
            by_system_columns[row["system_code"]].append(row)

        # 1. systems + data sources + assets upsert
        for code, profile in registry.items():
            system = db.scalar(select(AssetSystem).where(AssetSystem.system_code == profile["system_code"]))
            if not system:
                system = AssetSystem(system_code=profile["system_code"], system_name_cn=profile["system_name_cn"])
                db.add(system)
                summary["per_source"].setdefault(code, {})["system_inserted"] = 1
            if not (system.system_name_cn or "").strip():
                system.system_name_cn = profile["system_name_cn"]
            system.system_type = profile["system_type"]
            system.target_host = profile["host"]
            if not system.system_identity_key:
                system.system_identity_key = build_endpoint_key(profile["db_type"], profile["host"], profile["port"])
            system.status = "active"

            source = db.scalar(select(AssetDataSource).where(AssetDataSource.source_code == profile["source_code"]))
            if not source:
                source = AssetDataSource(system_code=profile["system_code"], source_code=profile["source_code"],
                                         source_name_cn=profile["source_name_cn"])
                db.add(source)
            source.system_code = profile["system_code"]
            source.source_name_cn = profile["source_name_cn"]
            source.db_type = profile["db_type"]
            source.target_host = profile["host"]
            source.host_masked = host_masked_from_target(profile["host"])
            source.port = profile["port"]
            source.service_name = profile["service_name"]
            source.database_name = profile["database_name"]
            source.service_mode = profile["service_mode"]
            source.default_schema = profile["default_schema"]
            source.endpoint_key = build_endpoint_key(profile["db_type"], profile["host"], profile["port"])
            source.database_key = build_database_key(profile["db_type"], profile["host"], profile["port"],
                                                     profile["service_name"], profile["database_name"], profile["service_mode"])
            source.connection_identity_key = build_connection_identity_key(profile["db_type"], profile["host"], profile["port"],
                                                                           profile["service_name"], profile["database_name"], profile["service_mode"])
            source.source_kind = "physical_connection"
            source.business_labels = profile["labels"]
            source.metadata_origin = "live_readonly_evidence"
            source.collect_mode = "metadata_only"
            source.write_policy = "readonly"
            source.enabled = True
            source.credential_ref = profile["credential_ref"]
            source.credential_status = "configured"
            source.last_collect_status = "succeeded"
            source.last_collect_at = now
            source.last_test_status = "connected"
            source.last_test_at = now

            table_rows = [{
                "namespace": r["namespace"], "table": r["object_name"],
                "role": "view" if r["object_type"] == "view" else "table",
                "rows": r.get("estimated_rows") or None,
                "comment": r.get("comment") or None,
                "domain": profile["system_name_cn"], "source": f"{batch_tag} read-only live metadata",
            } for r in by_system_objects.get(code, [])]
            t_stats = upsert_tables(db, system_code=code, source_code=profile["source_code"],
                                    tables=table_rows, now=now, skip_confirmed_empty=True)
            excluded_tables = {
                (r.get("namespace") or "", r.get("table") or "")
                for r in table_rows
                if r.get("row_presence_status") == "confirmed_empty"
            }
            column_rows = [{
                "namespace": r["namespace"], "table": r["object_name"],
                "ordinal": r.get("ordinal"), "column": r["column_name"],
                "data_type": r.get("data_type"), "nullable": r.get("nullable"),
                "comment": r.get("comment") or None,
            } for r in by_system_columns.get(code, [])]
            c_stats = upsert_columns(db, system_code=code, source_code=profile["source_code"],
                                     columns=column_rows, excluded_tables=excluded_tables)
            # SessionLocal runs with autoflush disabled; flush so the schema
            # inventory rebuild sees this source's freshly upserted tables.
            db.flush()
            schemas = rebuild_schema_inventory(db, source_code=profile["source_code"],
                                               labels=profile["labels"], now=now)
            summary["per_source"][code] = {
                "objects": len(table_rows), "columns": len(column_rows),
                "tables_writes": t_stats.get("writes", 0),
                "tables_inserts": t_stats.get("inserts", 0),
                "tables_updates": t_stats.get("updates", 0),
                "columns_writes": c_stats.get("writes", 0),
                "schemas": schemas,
            }
            summary["tables_writes"] += t_stats.get("writes", 0)
            summary["tables_inserts"] += t_stats.get("inserts", 0)
            summary["tables_updates"] += t_stats.get("updates", 0)
            summary["columns_writes"] += c_stats.get("writes", 0)

        # 2. declared FK -> structural formal relations (db_constraint evidence)
        fk_rows: list[dict[str, Any]] = []
        for r in constraints:
            if r["constraint_type"] != "FOREIGN KEY":
                continue
            profile = registry.get(r["system_code"])
            if not profile:
                continue
            fcols, tcols = _normalize_columns(r["columns"]), (r.get("references") or "")
            ref_table = tcols.split("(", 1)[0].strip()
            ref_cols = tcols[tcols.find("(") + 1:tcols.rfind(")")] if "(" in tcols else fcols
            fk_rows.append({
                "system_code": r["system_code"],
                "from_table": r["namespace"] + "." + r["object_name"],
                "from_columns": fcols,
                "to_table": ref_table,
                "to_columns": ref_cols,
                "join_condition": f"{r['namespace']}.{r['object_name']}({fcols}) = {ref_table}({ref_cols})",
                "level": "declared_foreign_key", "status": "verified", "confidence": "A",
                "metrics": json.dumps({"evidence": "database_declared_constraint",
                                       "constraint": r["constraint_name"]}, ensure_ascii=False),
                "note": f"{batch_tag}; constraint {r['constraint_name']}"
                        + ("; disabled" if str(r.get("is_disabled") or "").lower() in {"1", "true", "yes"} else ""),
            })
        fk_by_system: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in fk_rows:
            fk_by_system[row["system_code"]].append(row)
        for code, rows in fk_by_system.items():
            stats = upsert_relations(db, domain=code, relations=rows)
            summary["per_source"][code]["fk_relations"] = stats.get("writes", 0)
            summary["fk_relation_writes"] += stats.get("writes", 0)
            summary["fk_relation_inserts"] += stats.get("inserts", 0)
            summary["fk_relation_updates"] += stats.get("updates", 0)

        db.flush()

        # 3. view dependencies -> lineage layer (batch-scoped replace)
        dep_rows = []
        for r in view_deps:
            dep_rows.append({
                "view_name": f"{r['namespace']}.{r['view_name']}",
                "referenced_schema": r["namespace"],
                "referenced_table": str(r["referenced_object"]).split(".")[-1],
                "source_file": batch_tag,
            })
        summary["view_dependency_rows"] = len(dep_rows)
        if apply and dep_rows:
            replaced = db.execute(
                delete(AssetViewDependency).where(AssetViewDependency.source_file == batch_tag)
            ).rowcount
            summary["view_dependency_replaced"] = int(replaced or 0)
            for row in dep_rows:
                db.add(AssetViewDependency(**row))

        # 4. review drafts (candidate/partial only) with endpoint resolution
        name_index = _full_name_index(objects)
        review_payload: list[dict[str, Any]] = []
        recipe_payload: list[dict[str, Any]] = []
        for r in candidates:
            if r["layer"] not in {"review_draft", "recipe_draft"}:
                continue
            entry = {
                "owner": r["namespace"],
                "view": str(r["view_name"]).upper(),
                "source_sql_sha256": r.get("source_sql_sha256"),
                "intake_status": r["intake_status"],
                "from_table": _resolve_endpoint(name_index, r["from_table"]) or r["from_table"],
                "from_columns": _normalize_columns(r["from_columns"]),
                "to_table": _resolve_endpoint(name_index, r["to_table"]) or r["to_table"],
                "to_columns": _normalize_columns(r["to_columns"]),
                "join_condition": r.get("join_condition"),
                "qualifiers": [q for q in str(r.get("qualifiers") or "").split("|") if q],
                "warnings": [w for w in str(r.get("warnings") or "").split("|") if w],
                "system_code": r["system_code"],
                "source_code": r["source_code"],
                "cross_database": bool(r.get("is_cross_database")),
            }
            if r["layer"] == "review_draft":
                review_payload.append(entry)
            else:
                recipe_payload.append(entry)

        from plan139_common import prepare_recipe_groups, prepare_review_groups

        review_groups, skipped_prepare = prepare_review_groups({"candidates": review_payload})
        recipe_groups = prepare_recipe_groups(
            {"recipe_candidates": [dict(item, status="VALID") for item in recipe_payload]},
            recipe_prefix="PLAN139_VIEW",
        )
        summary["prepared_reviews"] = len(review_groups)
        summary["prepared_recipes"] = len(recipe_groups)

        table_names = {
            f"{row.namespace_name}.{row.table_name}".upper()
            for row in db.scalars(select(AssetTable).where(AssetTable.source_code.in_(
                [p["source_code"] for p in registry.values()]))).all()
        }
        column_names: dict[str, set[str]] = defaultdict(set)
        for row in db.scalars(select(AssetColumn).where(AssetColumn.source_code.in_(
                [p["source_code"] for p in registry.values()]))).all():
            column_names[f"{row.namespace_name}.{row.table_name}".upper()].add(str(row.column_name).upper())

        from plan139_common import metadata_check

        formal_ids = {_identity(vars(row)) for row in db.scalars(select(AssetRelation)).all()
                      if row.from_table and row.to_table}
        review_ids = {_identity(vars(row)) for row in db.scalars(select(AssetRelationReview)).all()
                      if row.from_table and row.to_table}

        source_by_system = {code: p["source_code"] for code, p in registry.items()}
        for group in review_groups:
            identity = _identity(group)
            if identity in formal_ids:
                summary["skipped_existing_formal"] += 1
                continue
            if identity in review_ids:
                summary["skipped_existing_review"] += 1
                continue
            verified, errors = metadata_check(group, table_names, column_names)
            if not verified:
                summary["skipped_metadata"] += 1
                for error in errors:
                    error_type = error.split(":", 1)[0]
                    summary["metadata_error_types"][error_type] = summary["metadata_error_types"].get(error_type, 0) + 1
                continue
            summary["eligible_reviews"] += 1
            if apply:
                system_code = group["evidence"][0].get("system_code") if group.get("evidence") else None
                source_code = group["evidence"][0].get("source_code") if group.get("evidence") else None
                validation_hits = []
                for ev in group["evidence"]:
                    key = (
                        str(ev.get("system_code")), str(ev.get("view", "")).upper(),
                        str(group["from_table"]).upper(), str(group["to_table"]).upper(),
                        ",".join(group["from_columns"]).upper(), ",".join(group["to_columns"]).upper(),
                    )
                    hit = validations_by_key.get(key)
                    if hit and hit.get("status") == "validated":
                        validation_hits.append({
                            "view": hit.get("view_name"), "sampled": hit.get("sampled"),
                            "matched": hit.get("matched"), "match_rate": hit.get("match_rate"),
                        })
                evidence = json.dumps({
                    "batch": batch_tag,
                    "views": [{"view": e.get("view"), "sha": e.get("source_sql_sha256")} for e in group["evidence"][:20]],
                    "qualifiers": group.get("qualifiers") or [],
                    "bounded_validations": validation_hits,
                }, ensure_ascii=False, sort_keys=True)[:4000]
                db.add(AssetRelationReview(
                    relation_scope="candidate",
                    from_system_code=system_code, from_source_code=source_code,
                    from_table=group["from_table"], from_columns=",".join(group["from_columns"]),
                    to_system_code=system_code, to_source_code=source_code,
                    to_table=group["to_table"], to_columns=",".join(group["to_columns"]),
                    join_condition=str(group.get("join_condition") or "")[:4000],
                    relation_desc_cn="四系统视图解析关系候选",
                    business_logic_cn="仅视图 SQL 静态证据与平台元数据确认；未经独立审核，不自动提升正式关系。",
                    confidence="C",
                    validation_status="compile_valid_metadata_confirmed_runtime_skipped",
                    review_status="draft",
                    review_note=f"{batch_tag}; intake_status={group.get('intake_status')}"
                                + ("; bounded_aggregate_validated" if validation_hits else ""),
                    source_evidence=evidence,
                ))
                summary["inserted_reviews"] += 1
            review_ids.add(identity)

        existing_recipes = {
            row.recipe_id
            for row in db.scalars(select(AssetRelationRecipe).where(AssetRelationRecipe.recipe_id.in_(
                [g["recipe_id"] for g in recipe_groups]))).all()
        } if recipe_groups else set()
        for recipe in recipe_groups:
            if recipe["recipe_id"] in existing_recipes:
                summary["skipped_existing_recipe"] += 1
                continue
            checks = [metadata_check(row, table_names, column_names) for row in recipe["joins"]]
            if not checks or not all(ok for ok, _ in checks):
                summary["skipped_metadata"] += 1
                for _, errors in checks:
                    for error in errors:
                        error_type = error.split(":", 1)[0]
                        summary["metadata_error_types"][error_type] = summary["metadata_error_types"].get(error_type, 0) + 1
                continue
            summary["eligible_recipes"] += 1
            if apply:
                joins = [
                    {
                        "from_table": row["from_table"], "from_columns": row["from_columns"],
                        "to_table": row["to_table"], "to_columns": row["to_columns"],
                        "qualifiers": row.get("qualifiers") or [],
                        "warnings": row.get("warnings") or [],
                    }
                    for row in recipe["joins"]
                ]
                content = json.dumps(joins, ensure_ascii=False, sort_keys=True)
                db.add(AssetRelationRecipe(
                    recipe_id=recipe["recipe_id"],
                    version=1,
                    recipe_name=f"{recipe['owner']}.{recipe['view']} 视图复杂逻辑草稿",
                    status="draft",
                    is_active=False,
                    recipe_json={"owner": recipe["owner"], "view": recipe["view"], "joins": joins},
                    domain="四系统视图关系",
                    source_system="PLAN139",
                    recommended_view_name=f"{recipe['owner']}.{recipe['view']}",
                    description="由四系统视图 SQL 解析的多表/过滤/转换逻辑；仅供人工审核，本轮不激活。",
                    primary_tables=sorted({row["from_table"] for row in recipe["joins"]} | {row["to_table"] for row in recipe["joins"]}),
                    joins=joins,
                    ai_readable=True,
                    evidence_summary={"batch": batch_tag, "source_sql_sha256": recipe["source_sql_sha256"]},
                    risk_summary={"requires_manual_review": True, "runtime_status": "runtime_skipped"},
                    content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
                    created_by="plan139_import",
                    imported_from=batch_tag,
                ))
                summary["inserted_recipes"] += 1
            existing_recipes.add(recipe["recipe_id"])

        db.flush()
        summary["platform_after"] = {
            "systems": _count(AssetSystem), "sources": _count(AssetDataSource),
            "tables": _count(AssetTable), "columns": _count(AssetColumn),
            "relations": _count(AssetRelation), "reviews": _count(AssetRelationReview),
            "recipes": _count(AssetRelationRecipe),
        }
        summary["batch_review_statuses"] = {
            str(status or "unknown"): int(count)
            for status, count in db.execute(
                select(AssetRelationReview.review_status, func.count(AssetRelationReview.id))
                .where(AssetRelationReview.review_note.contains(batch_tag))
                .group_by(AssetRelationReview.review_status)
            ).all()
        }
        summary["batch_recipe_statuses"] = {
            str(status or "unknown"): int(count)
            for status, count in db.execute(
                select(AssetRelationRecipe.status, func.count(AssetRelationRecipe.id))
                .where(AssetRelationRecipe.imported_from == batch_tag)
                .group_by(AssetRelationRecipe.status)
            ).all()
        }
        summary["batch_active_recipes"] = int(db.scalar(
            select(func.count()).select_from(AssetRelationRecipe).where(
                AssetRelationRecipe.imported_from == batch_tag,
                AssetRelationRecipe.is_active.is_(True),
            )
        ) or 0)
        if apply:
            db.commit()
        else:
            db.rollback()
    summary["source_writes"] = 0
    return summary


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-dir", required=True, type=Path)
    parser.add_argument("--validation-results", type=Path)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--systems", default="",
                        help="comma-separated subset of registry systems to import (default: all)")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm", default="")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        validations = json.loads(args.validation_results.read_text(encoding="utf-8")) if args.validation_results else None
        selected = [item.strip() for item in args.systems.split(",") if item.strip()] or None
        result = execute(args.package_dir, run_id=args.run_id, apply=args.apply,
                         confirm=args.confirm, validation_results=validations,
                         selected_systems=selected)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except Exception as exc:
        detail = getattr(exc, "name", None) if isinstance(exc, (ModuleNotFoundError, NameError)) else None
        print(json.dumps({"status": "error", "error_type": type(exc).__name__, "error_name": detail}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
