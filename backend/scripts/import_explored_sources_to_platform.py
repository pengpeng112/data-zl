"""Idempotently import evidence 78-83 into the platform database.

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

CONFIRMATION = "IMPORT-EXPLORED-SOURCES-78-83"

PROFILES = {
    "paperless": {
        "system_code": "PAPERLESS_CDMS", "system_name": "无纸化病案系统", "system_type": "PAPERLESS",
        "source_code": "paperless_cdms_oracle_10_10_10_93", "source_name": "无纸化 CDMS 业务库",
        "db_type": "oracle", "host": "10.10.10.93", "port": 1521, "service_name": "orcl",
        "database_name": "orcl", "service_mode": "service_name", "default_schema": "CDMS",
        "credential_env": "IMPORT_CRED_PAPERLESS", "labels": ["CDMS", "无纸化病案"],
    },
    "docare": {
        "system_code": "DOCARE", "system_name": "Docare 手术麻醉系统", "system_type": "ANESTHESIA",
        "source_code": "docare_oracle_10_10_10_68", "source_name": "Docare 手麻业务库",
        "db_type": "oracle", "host": "10.10.10.68", "port": 1521, "service_name": "docare",
        "database_name": "docare", "service_mode": "service_name", "default_schema": "MEDSURGERY",
        "credential_env": "IMPORT_CRED_DOCARE", "labels": ["手麻", "MEDSURGERY", "MEDCOMM", "MEDICU"],
    },
    "lis": {
        "system_code": "LIS_SOURCE", "system_name": "检验信息系统（源端）", "system_type": "LIS",
        "source_code": "lis_sqlserver_10_10_10_73", "source_name": "LIS SQL Server 业务库",
        "db_type": "sqlserver", "host": "10.10.10.73", "port": 1433, "database_name": "rmcloudlis7",
        "service_name": None, "service_mode": "database", "default_schema": "dbo",
        "credential_env": "IMPORT_CRED_LIS", "labels": ["LIS", "检验"],
    },
    "ultrasound": {
        "system_code": "ULTRASOUND_ENDOSCOPY", "system_name": "超声内镜系统", "system_type": "ULTRASOUND_ENDOSCOPY",
        "source_code": "ultrasound_endoscopy_sqlserver_10_10_10_161", "source_name": "超声内镜 SQL Server 实例",
        "db_type": "sqlserver", "host": "10.10.10.161", "port": 1433, "database_name": "MedcareUS",
        "service_name": None, "service_mode": "database", "default_schema": "MedcareUS.dbo",
        "credential_env": "IMPORT_CRED_ULTRASOUND", "labels": ["超声", "内镜", "PACS", "归档"],
    },
    "pacs": {
        "system_code": "PACS_SOURCE", "system_name": "PACS 影像系统（源端）", "system_type": "PACS",
        "source_code": "pacs_mysql_10_10_10_191", "source_name": "PACS MySQL 实例",
        "db_type": "mysql", "host": "10.10.10.191", "port": 3306, "database_name": "gecris",
        "service_name": None, "service_mode": "database", "default_schema": "gecris",
        "credential_env": "IMPORT_CRED_PACS", "labels": ["PACS", "RIS", "影像"],
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
        elif profile == "lis":
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
            "note": f"evidence {r.get('relationship_id')}; bounded read-only validation",
        })
    return output


def upsert_connection(db, profile: dict, now: datetime) -> AssetDataSource:
    system = db.scalar(select(AssetSystem).where(AssetSystem.system_code == profile["system_code"]))
    if not system:
        system = AssetSystem(system_code=profile["system_code"], system_name_cn=profile["system_name"])
        db.add(system)
    system.system_name_cn = profile["system_name"]
    system.system_type = profile["system_type"]
    system.target_host = profile["host"]
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
    source.metadata_origin = "live_readonly_evidence_79_83"
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
    source_code, domain = profile["source_code"], profile["system_code"]
    db.execute(delete(AssetColumn).where(AssetColumn.source_code == source_code))
    db.execute(delete(AssetTable).where(AssetTable.source_code == source_code))
    db.execute(delete(AssetSourceSchema).where(AssetSourceSchema.source_code == source_code))
    db.execute(delete(AssetRelation).where(AssetRelation.domain == domain))
    counts, col_counts = defaultdict(int), defaultdict(int)
    for row in tables:
        counts[row["namespace"]] += 1
        db.add(AssetTable(system_code=domain, source_code=source_code, namespace_name=row["namespace"], schema_name=row["namespace"], table_name=row["table"], table_role=row["role"], comment=row.get("comment"), row_count_stats=str(row["rows"]) if row.get("rows") is not None else None, domain=profile["system_name"], include_status="keep", confidence="live_metadata", source="read-only live metadata evidence"))
    for row in columns:
        col_counts[row["namespace"]] += 1
        db.add(AssetColumn(system_code=domain, source_code=source_code, namespace_name=row["namespace"], schema_name=row["namespace"], table_name=row["table"], column_id=row["ordinal"], column_name=row["column"], data_type=row["data_type"], length=row.get("length"), nullable=row.get("nullable"), comment=row.get("comment"), review_status="live_metadata"))
    for namespace in sorted(counts):
        db.add(AssetSourceSchema(source_code=source_code, schema_name=namespace, business_labels=profile["labels"], table_count=counts[namespace], column_count=col_counts[namespace], last_collect_at=now))
    next_id = (db.scalar(select(func.max(AssetRelation.rel_id))) or 0) + 1
    seen = set()
    for row in relations:
        key = (row["from_table"], row.get("from_columns"), row["to_table"], row.get("to_columns"), row["level"])
        if key in seen:
            continue
        seen.add(key)
        db.add(AssetRelation(rel_id=next_id + len(seen) - 1, domain=domain, from_table=row["from_table"], from_columns=row.get("from_columns"), to_table=row["to_table"], to_columns=row.get("to_columns"), join_condition=(f"{row['from_table']}({row.get('from_columns')}) = {row['to_table']}({row.get('to_columns')})"), confidence=row["confidence"], validation_level=row["level"], validation_status=row["status"], validation_metrics=row.get("metrics"), note=row.get("note")))
    return {"tables": len(tables), "columns": len(columns), "schemas": len(counts), "relations": len(seen)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirmation", default="")
    args = parser.parse_args()
    files = {
        "paperless": ("79_无纸化系统Oracle元数据快照.json", "79_无纸化系统关系验证结果.json", oracle_assets),
        "docare": ("80_手麻Docare系统Oracle元数据快照.json", "80_手麻Docare系统关系验证结果.json", oracle_assets),
        "lis": ("81_LIS_SQLServer元数据快照.json", "81_LIS_SQLServer关系验证结果.json", lambda x: sqlserver_assets(x, False)),
        "ultrasound": ("82_超声内镜SQLServer多库元数据快照.json", "82_超声内镜SQLServer关系验证结果.json", lambda x: sqlserver_assets(x, True)),
        "pacs": ("83_PACS_MySQL元数据快照.json", "83_PACS_MySQL关系验证结果.json", mysql_assets),
    }
    prepared = {}
    for name, (snapshot_name, relation_name, converter) in files.items():
        tables, columns, fks = converter(load(args.evidence_dir / snapshot_name))
        relations = fks + verified_relations(name, load(args.evidence_dir / relation_name))
        prepared[name] = (tables, columns, relations)
    his_relations = verified_relations("his", load(args.evidence_dir / "78_HIS源端表关系活库复核结果.json"))
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
        # HIS assets already exist. Replace only the dedicated HIS_SOURCE relation domain.
        db.execute(delete(AssetRelation).where(AssetRelation.domain == "HIS_SOURCE"))
        next_id = (db.scalar(select(func.max(AssetRelation.rel_id))) or 0) + 1
        for offset, row in enumerate(his_relations):
            db.add(AssetRelation(rel_id=next_id + offset, domain="HIS_SOURCE", from_table=row["from_table"], from_columns=row["from_columns"], to_table=row["to_table"], to_columns=row["to_columns"], join_condition=f"{row['from_table']}({row['from_columns']}) = {row['to_table']}({row['to_columns']})", confidence=row["confidence"], validation_level=row["level"], validation_status=row["status"], validation_metrics=row.get("metrics"), note=row.get("note")))
        db.commit()
    print(json.dumps({"mode": "apply", "status": "succeeded", "applied": applied, "his_relations": len(his_relations)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
