"""Idempotently import explored-source evidence into the platform database.

This script never opens a business source database. It reads harvested JSON
evidence and, only with explicit confirmation, writes the platform asset
schema and the server-side read-only credential store.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import delete, func, select

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.core.db import SessionLocal
from app.models.asset import AssetColumn, AssetRelation, AssetTable
from app.models.asset_system import AssetDataSource, AssetSourceSchema, AssetSystem
from app.services import credential_store
from app.services.connection_identity import (
    build_connection_identity_key,
    build_database_key,
    build_endpoint_key,
    host_masked_from_target,
)
from app.services.asset_catalog import CANONICAL_SYSTEMS

CONFIRMATION = "IMPORT-EXPLORED-SOURCES-78-83"

PROFILES = {
    "paperless": {
        "system_code": "PAPERLESS_CDMS", "system_name": CANONICAL_SYSTEMS["PAPERLESS_CDMS"], "system_type": "PAPERLESS",
        "source_code": "paperless_cdms_oracle_10_10_10_93", "source_name": "无纸化 CDMS 业务库",
        "db_type": "oracle", "host": "10.10.10.93", "port": 1521, "service_name": "orcl",
        "database_name": "orcl", "service_mode": "service_name", "default_schema": "CDMS",
        "credential_env": "IMPORT_CRED_PAPERLESS", "labels": ["CDMS", "无纸化病案"],
    },
    "docare": {
        "system_code": "DOCARE", "system_name": CANONICAL_SYSTEMS["DOCARE"], "system_type": "ANESTHESIA",
        "source_code": "docare_oracle_10_10_10_68", "source_name": "Docare 手麻业务库",
        "db_type": "oracle", "host": "10.10.10.68", "port": 1521, "service_name": "docare",
        "database_name": "docare", "service_mode": "service_name", "default_schema": "MEDSURGERY",
        "credential_env": "IMPORT_CRED_DOCARE", "labels": ["手麻", "MEDSURGERY", "MEDCOMM", "MEDICU"],
    },
    "lis": {
        "system_code": "LIS_SOURCE", "system_name": CANONICAL_SYSTEMS["LIS_SOURCE"], "system_type": "LIS",
        "source_code": "lis_sqlserver_10_10_10_73", "source_name": "LIS SQL Server 业务库",
        "db_type": "sqlserver", "host": "10.10.10.73", "port": 1433, "database_name": "rmcloudlis7",
        "service_name": None, "service_mode": "database", "default_schema": "dbo",
        "credential_env": "IMPORT_CRED_LIS", "labels": ["LIS", "检验"],
    },
    "ultrasound": {
        "system_code": "ULTRASOUND_ENDOSCOPY", "system_name": CANONICAL_SYSTEMS["ULTRASOUND_ENDOSCOPY"], "system_type": "ULTRASOUND_ENDOSCOPY",
        "source_code": "ultrasound_endoscopy_sqlserver_10_10_10_161", "source_name": "超声内镜 SQL Server 实例",
        "db_type": "sqlserver", "host": "10.10.10.161", "port": 1433, "database_name": "MedcareUS",
        "service_name": None, "service_mode": "database", "default_schema": "MedcareUS.dbo",
        "credential_env": "IMPORT_CRED_ULTRASOUND", "labels": ["超声", "内镜", "PACS", "归档"],
    },
    "pacs": {
        "system_code": "PACS_SOURCE", "system_name": CANONICAL_SYSTEMS["PACS_SOURCE"], "system_type": "PACS",
        "source_code": "pacs_mysql_10_10_10_191", "source_name": "PACS MySQL 实例",
        "db_type": "mysql", "host": "10.10.10.191", "port": 3306, "database_name": "gecris",
        "service_name": None, "service_mode": "database", "default_schema": "gecris",
        "credential_env": "IMPORT_CRED_PACS", "labels": ["PACS", "RIS", "影像"],
    },
    "mobile_nursing": {
        "system_code": "MOBILE_NURSING", "system_name": CANONICAL_SYSTEMS["MOBILE_NURSING"], "system_type": "MOBILE_NURSING",
        "source_code": "mobile_nursing_oracle_10_10_10_125", "source_name": "移动护理 Oracle 业务库",
        "db_type": "oracle", "host": "10.10.10.125", "port": 1521, "service_name": "ewell",
        "database_name": "ewell", "service_mode": "service_name", "default_schema": "LUNA_MCS_SDSEY",
        "credential_env": "IMPORT_CRED_MOBILE_NURSING", "labels": ["移动护理", "护理", "LUNA_MCS_SDSEY"],
    },
}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def oracle_assets(snapshot: dict) -> tuple[list[dict], list[dict], list[dict]]:
    tables = [{
        "namespace": r["owner"], "table": r["table_name"], "role": r.get("object_type", "TABLE").lower(),
        "rows": r.get("num_rows"), "comment": r.get("comments"),
    } for r in snapshot["tables"]]
    tables += [{
        "namespace": r["owner"], "table": r["table_name"], "role": "view", "rows": None,
        "comment": r.get("comments"),
    } for r in snapshot.get("views", [])]
    columns = [{
        "namespace": r["owner"], "table": r["table_name"], "ordinal": r["column_id"],
        "column": r["column_name"], "data_type": r["data_type"], "length": r.get("data_length"),
        "nullable": r.get("nullable"), "comment": r.get("comments"),
    } for r in snapshot["columns"]]
    fks = []
    for r in snapshot.get("constraints", []):
        if r.get("constraint_type") == "R" and r.get("r_table_name"):
            owner = r.get("owner") or snapshot.get("source", {}).get("owner")
            fks.append({
                "from_table": f"{owner}.{r['table_name']}", "from_columns": r["column_name"],
                "to_table": f"{r.get('r_owner') or owner}.{r['r_table_name']}", "to_columns": r.get("r_column_name"),
                "level": "declared_foreign_key", "status": "verified", "confidence": "A", "note": r.get("constraint_name"),
            })
    return tables, columns, fks


def sqlserver_assets(snapshot: dict, multi: bool = False) -> tuple[list[dict], list[dict], list[dict]]:
    tables, columns, fks = [], [], []
    databases = snapshot["databases"] if multi else {snapshot["source"]["database"]: snapshot}
    for database, data in databases.items():
        prefix = f"{database}." if multi else ""
        for r in data.get("tables", []):
            tables.append({"namespace": prefix + r["schema_name"], "table": r["table_name"], "role": "table", "rows": r.get("row_count"), "comment": r.get("comment")})
        for r in data.get("views", []):
            tables.append({"namespace": prefix + r["schema_name"], "table": r["view_name"], "role": "view", "rows": None, "comment": r.get("comment")})
        for r in data.get("columns", []):
            columns.append({"namespace": prefix + r["schema_name"], "table": r["object_name"], "ordinal": r["column_id"], "column": r["column_name"], "data_type": r["data_type"], "length": r.get("max_length"), "nullable": str(r.get("is_nullable")), "comment": r.get("comment")})
        for r in data.get("foreign_keys", []):
            child_schema = prefix + r["schema_name"]
            parent_schema = prefix + (r.get("referenced_schema_name") or r["schema_name"])
            fks.append({"from_table": f"{child_schema}.{r['table_name']}", "from_columns": r["column_name"], "to_table": f"{parent_schema}.{r['referenced_table_name']}", "to_columns": r["referenced_column_name"], "level": "declared_foreign_key", "status": "verified", "confidence": "A", "note": r.get("constraint_name")})
    return tables, columns, fks


def mysql_assets(snapshot: dict) -> tuple[list[dict], list[dict], list[dict]]:
    tables, columns, fks = [], [], []
    for database, data in snapshot["databases"].items():
        for r in data["tables"]:
            tables.append({"namespace": database, "table": r["TABLE_NAME"], "role": "view" if r["TABLE_TYPE"] == "VIEW" else "table", "rows": r.get("TABLE_ROWS"), "comment": r.get("TABLE_COMMENT")})
        for r in data["columns"]:
            columns.append({"namespace": database, "table": r["TABLE_NAME"], "ordinal": r["ORDINAL_POSITION"], "column": r["COLUMN_NAME"], "data_type": r["COLUMN_TYPE"], "length": None, "nullable": r["IS_NULLABLE"], "comment": r.get("COLUMN_COMMENT")})
        for r in data["foreign_keys"]:
            fks.append({"from_table": f"{database}.{r['TABLE_NAME']}", "from_columns": r["COLUMN_NAME"], "to_table": f"{r['REFERENCED_TABLE_SCHEMA']}.{r['REFERENCED_TABLE_NAME']}", "to_columns": r["REFERENCED_COLUMN_NAME"], "level": "declared_foreign_key", "status": "verified", "confidence": "A", "note": r["CONSTRAINT_NAME"]})
    return tables, columns, fks


def verified_relations(profile: str, evidence: dict) -> list[dict]:
    output = []
    for r in evidence.get("results", []):
        if profile == "paperless":
            parent = (r.get("parent_candidates") or [{}])[0]
            from_table, to_table = r["child_table"], parent.get("table")
            from_cols, to_cols = r.get("child_columns"), parent.get("columns")
        elif profile == "docare":
            from_table, to_table = r["child_table"], r["parent_table"]
            cols = r.get("columns") or []
            if cols and isinstance(cols[0], list):
                from_cols, to_cols = [x[0] for x in cols], [x[1] for x in cols]
            else:
                from_cols = to_cols = cols
        elif profile in {"lis", "mobile_nursing"}:
            from_table, to_table = r["child_table"], r["parent_table"]
            from_cols, to_cols = r["child_columns"], r["parent_columns"]
        elif profile == "ultrasound":
            from_table, to_table = r["child"], r["parent"]
            from_cols, to_cols = r["child_columns"], r["parent_columns"]
        elif profile == "pacs":
            from_table, to_table = r["child"], r["parent"]
            from_cols, to_cols = [r["child_column"]], [r["parent_column"]]
        elif profile == "his":
            from_table, to_table = r["from_table"], r["to_table"]
            pairs = r.get("keys") or []
            from_cols, to_cols = [x[0] for x in pairs], [x[1] for x in pairs]
        else:
            continue
        if not to_table:
            continue
        sampled, matched = int(r.get("sampled_nonnull_keys") or 0), int(r.get("matched") or 0)
        rate = r.get("match_rate")
        status = "verified" if sampled and matched == sampled else ("partial" if matched else "candidate")
        confidence = "A" if status == "verified" else ("B" if status == "partial" else "C")
        output.append({
            "from_table": from_table, "from_columns": ",".join(from_cols or []),
            "to_table": to_table, "to_columns": ",".join(to_cols or []),
            "level": "sample_data", "status": status, "confidence": confidence,
            "metrics": json.dumps({"sampled": sampled, "matched": matched, "match_rate": rate}, ensure_ascii=False),
            "note": f"evidence {r.get('relationship_id') or r.get('id')}; bounded read-only validation",
        })
    return output


def upsert_connection(db, profile: dict, now: datetime) -> AssetDataSource:
    system = db.scalar(select(AssetSystem).where(AssetSystem.system_code == profile["system_code"]))
    if not system:
        system = AssetSystem(system_code=profile["system_code"], system_name_cn=profile["system_name"])
        db.add(system)
    # plan 90: never overwrite human-confirmed Chinese system names
    from app.services.asset_catalog import CANONICAL_SYSTEMS

    default_cn = CANONICAL_SYSTEMS.get(profile["system_code"], profile["system_name"])
    if not (system.system_name_cn or "").strip():
        system.system_name_cn = default_cn
    # keep profile type/host metadata
    system.system_type = profile["system_type"]
    system.target_host = profile["host"]
    if not system.system_identity_key:
        system.system_identity_key = build_endpoint_key(profile["db_type"], profile["host"], profile["port"])
    system.status = "active"

    source = db.scalar(select(AssetDataSource).where(AssetDataSource.source_code == profile["source_code"]))
    if not source:
        source = AssetDataSource(system_code=profile["system_code"], source_code=profile["source_code"], source_name_cn=profile["source_name"])
        db.add(source)
    source.system_code = profile["system_code"]
    source.source_name_cn = profile["source_name"]
    source.db_type = profile["db_type"]
    source.target_host = profile["host"]
    source.host_masked = host_masked_from_target(profile["host"])
    source.port = profile["port"]
    source.service_name = profile.get("service_name")
    source.database_name = profile.get("database_name")
    source.service_mode = profile["service_mode"]
    source.default_schema = profile["default_schema"]
    source.endpoint_key = build_endpoint_key(profile["db_type"], profile["host"], profile["port"])
    source.database_key = build_database_key(profile["db_type"], profile["host"], profile["port"], profile.get("service_name"), profile.get("database_name"), profile["service_mode"])
    source.connection_identity_key = build_connection_identity_key(profile["db_type"], profile["host"], profile["port"], profile.get("service_name"), profile.get("database_name"), profile["service_mode"])
    source.source_kind = "physical_connection"
    source.business_labels = profile["labels"]
    source.metadata_origin = "live_readonly_evidence"
    source.collect_mode = "metadata_only"
    source.write_policy = "readonly"
    source.enabled = True
    source.last_collect_status = "succeeded"
    source.last_collect_at = now
    source.last_test_status = "connected"
    source.last_test_at = now
    credential = os.environ.get(profile["credential_env"])
    if credential:
        username, password = credential.split(":", 1)
        source.credential_ref = credential_store.rotate(profile["source_code"], username, password)
        source.credential_status = "configured"
        source.credential_username_masked = credential_store.mask_username(username)
        source.credential_updated_at = now
        source.credential_updated_by = "evidence-import-78-83"
    return source


def replace_assets(db, profile: dict, tables: list[dict], columns: list[dict], relations: list[dict], now: datetime) -> dict:
    """Idempotent upsert (plan 90). No delete-all-then-insert."""
    from app.services.asset_import_upsert import (
        rebuild_schema_inventory,
        upsert_columns,
        upsert_relations,
        upsert_tables,
    )

    source_code, domain = profile["source_code"], profile["system_code"]
    # Gate: stats-only zero is NOT confirmed_empty; mark probe candidates only.
    # Import keeps objects unless row_presence_status already confirmed_empty.
    t_stats = upsert_tables(
        db,
        system_code=domain,
        source_code=source_code,
        tables=[{**r, "domain": profile["system_name"], "source": "read-only live metadata evidence"} for r in tables],
        now=now,
        skip_confirmed_empty=True,
    )
    excluded_tables = {
        (r.get("namespace") or r.get("schema_name") or "", r.get("table") or r.get("table_name"))
        for r in tables
        if r.get("row_presence_status") == "confirmed_empty"
    }
    c_stats = upsert_columns(
        db,
        system_code=domain,
        source_code=source_code,
        columns=columns,
        excluded_tables=excluded_tables,
    )
    excluded_endpoints = {
        f"{ns}.{table}" for ns, table in excluded_tables if table
    }
    r_stats = upsert_relations(
        db, domain=domain, relations=relations, excluded_endpoints=excluded_endpoints
    )
    schemas = rebuild_schema_inventory(
        db, source_code=source_code, labels=profile.get("labels"), now=now
    )
    return {
        "tables": t_stats.get("tables_in", len(tables)),
        "tables_writes": t_stats.get("writes", 0),
        "tables_inserts": t_stats.get("inserts", 0),
        "tables_updates": t_stats.get("updates", 0),
        "skipped_confirmed_empty": t_stats.get("skipped_confirmed_empty", 0),
        "columns": len(columns),
        "columns_writes": c_stats.get("writes", 0),
        "schemas": schemas,
        "relations": r_stats.get("writes", 0),
        "relation_inserts": r_stats.get("inserts", 0),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument(
        "--profiles",
        default="",
        help="Comma-separated source profiles. Empty means all available profiles.",
    )
    parser.add_argument(
        "--mobile-snapshot",
        type=Path,
        help="Optional explicit path for the mobile-nursing metadata snapshot.",
    )
    parser.add_argument(
        "--mobile-relations",
        type=Path,
        help="Optional explicit path for the mobile-nursing relationship evidence.",
    )
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirmation", default="")
    args = parser.parse_args()
    files = {
        "paperless": ("79_无纸化系统Oracle元数据快照.json", "79_无纸化系统关系验证结果.json", oracle_assets),
        "docare": ("80_手麻Docare系统Oracle元数据快照.json", "80_手麻Docare系统关系验证结果.json", oracle_assets),
        "lis": ("81_LIS_SQLServer元数据快照.json", "81_LIS_SQLServer关系验证结果.json", lambda x: sqlserver_assets(x, False)),
        # 82: glob match — do not hard-fail on fixed filename typos
        "ultrasound": ("82_*元数据快照.json", "82_*关系验证结果.json", lambda x: sqlserver_assets(x, True)),
        "pacs": ("83_PACS_MySQL元数据快照.json", "83_PACS_MySQL关系验证结果.json", mysql_assets),
        "mobile_nursing": ("86_移动护理Oracle元数据快照.json", "86_移动护理Oracle关系验证结果.json", oracle_assets),
    }

    def _resolve_evidence(pattern_or_name: str) -> Path:
        p = args.evidence_dir / pattern_or_name
        if p.exists():
            return p
        matches = sorted(args.evidence_dir.glob(pattern_or_name))
        if matches:
            return matches[0]
        raise FileNotFoundError(f"evidence not found: {pattern_or_name} under {args.evidence_dir}")

    selected = {item.strip() for item in args.profiles.split(",") if item.strip()} or set(files)
    unknown = selected - set(files)
    if unknown:
        raise SystemExit(f"unknown profiles: {', '.join(sorted(unknown))}")
    prepared = {}
    for name, (snapshot_name, relation_name, converter) in files.items():
        if name not in selected:
            continue
        if name == "mobile_nursing" and args.mobile_snapshot:
            snapshot_path = args.mobile_snapshot
        else:
            snapshot_path = _resolve_evidence(snapshot_name)
        if name == "mobile_nursing" and args.mobile_relations:
            relation_path = args.mobile_relations
        else:
            relation_path = _resolve_evidence(relation_name)
        tables, columns, fks = converter(load(snapshot_path))
        relations = fks + verified_relations(name, load(relation_path))
        prepared[name] = (tables, columns, relations)
    include_his_relations = not args.profiles
    his_relations = (
        verified_relations("his", load(args.evidence_dir / "78_HIS源端表关系活库复核结果.json"))
        if include_his_relations else []
    )
    summary = {name: {"tables": len(v[0]), "columns": len(v[1]), "relations": len(v[2])} for name, v in prepared.items()}
    summary["his_relations"] = len(his_relations)
    if not args.apply:
        print(json.dumps({"mode": "dry_run", "writes": 0, "summary": summary}, ensure_ascii=False, indent=2))
        return
    if args.confirmation != CONFIRMATION:
        raise SystemExit(f"--apply requires --confirmation {CONFIRMATION}")
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        applied = {}
        for name, values in prepared.items():
            profile = PROFILES[name]
            upsert_connection(db, profile, now)
            applied[name] = replace_assets(db, profile, *values, now)
            db.flush()
        # HIS assets already exist. Upsert the dedicated HIS_SOURCE relations;
        # never delete the whole domain because it may contain human-reviewed rows.
        if include_his_relations:
            from app.services.asset_import_upsert import upsert_relations
            upsert_relations(db, domain="HIS_SOURCE", relations=his_relations)
        db.commit()
    print(json.dumps({"mode": "apply", "status": "succeeded", "applied": applied, "his_relations": len(his_relations)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
