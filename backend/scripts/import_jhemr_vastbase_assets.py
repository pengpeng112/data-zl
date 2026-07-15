"""Build/import JHEMR Vastbase metadata assets from a read-only snapshot.

The source database is never opened by this script.  It reads a previously
harvested metadata JSON and writes only generated package files and, with
explicit confirmation, the platform PostgreSQL asset schema.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import delete, func, select

BACKEND_DIR = Path(__file__).resolve().parents[1]
ROOT = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.core.db import SessionLocal
from app.models.asset import AssetColumn, AssetRelation, AssetTable
from app.models.asset_system import AssetDataSource, AssetSourceSchema, AssetSystem
from app.services.connection_identity import build_connection_identity_key, build_database_key, build_endpoint_key, host_masked_from_target

SYSTEM_CODE = "JHEMR_VASTBASE"
SOURCE_CODE = "jhemr_vastbase_10_10_8_177"
CONFIRMATION = "IMPORT-JHEMR-VASTBASE-ASSETS"


def documented_tables(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    return {m.group(1).upper() for m in re.finditer(r"\|\s*\d+\s*\|\s*`([A-Za-z0-9_$#]+)`\s*\|", text)}


def prepare(snapshot: dict, documented: set[str]) -> dict:
    tables = snapshot["tables"]
    columns = snapshot["columns"]
    constraints = snapshot["constraints"]
    objects = {(r["schema"].lower(), r["name"].lower()): r for r in tables}
    by_name: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for key in objects:
        by_name[key[1]].append(key)

    pk_cols: dict[tuple[str, str], list[str]] = defaultdict(list)
    unique_cols: dict[tuple[str, str], list[str]] = defaultdict(list)
    for row in constraints:
        target = pk_cols if row["type"] == "PRIMARY KEY" else unique_cols
        target[(row["schema"].lower(), row["table"].lower())].append(row["column"])

    col_count: dict[tuple[str, str], int] = defaultdict(int)
    for row in columns:
        col_count[(row["schema"].lower(), row["table"].lower())] += 1

    table_rows = []
    for row in tables:
        key = (row["schema"].lower(), row["name"].lower())
        table_rows.append({
            "system_code": SYSTEM_CODE, "source_code": SOURCE_CODE,
            "schema_name": row["schema"], "table_name": row["name"],
            "object_type": row["type"], "comment": row.get("comment") or "",
            "column_count": col_count[key], "pk": ",".join(pk_cols[key]),
            "documented": row["name"].upper() in documented,
        })

    column_rows = []
    for row in columns:
        column_rows.append({
            "system_code": SYSTEM_CODE, "source_code": SOURCE_CODE,
            "schema_name": row["schema"], "table_name": row["table"],
            "column_id": row["ordinal"], "column_name": row["name"],
            "data_type": row["data_type"], "length": row.get("char_length"),
            "nullable": row["nullable"], "default": row.get("default") or "",
        })

    relations = []
    seen = set()
    for view in snapshot.get("views", []):
        definition = view.get("definition") or ""
        view_key = (view["schema"].lower(), view["name"].lower())
        # Qualified references are authoritative; unqualified names are used
        # only when the name is unique in the harvested business schemas.
        refs = set()
        for schema, name in re.findall(r'(?i)([a-z_][\w$#]*)\.([a-z_][\w$#]*)', definition):
            key = (schema.lower(), name.lower())
            if key in objects and key != view_key:
                refs.add(key)
        tokens = {t.lower() for t in re.findall(r'(?i)\b([a-z_][\w$#]{2,})\b', definition)}
        for token in tokens:
            matches = by_name.get(token, [])
            if len(matches) == 1 and matches[0] != view_key:
                refs.add(matches[0])
        for ref in refs:
            rel_key = (ref, view_key)
            if rel_key in seen:
                continue
            seen.add(rel_key)
            relations.append({
                "from_table": f"{ref[0]}.{ref[1]}",
                "to_table": f"{view_key[0]}.{view_key[1]}",
                "relation_type": "view_dependency", "confidence": "B",
                "validation_level": "static_view_sql", "validation_status": "candidate",
                "note": "Vastbase pg_views definition; source database read-only metadata",
            })

    live_names = {r["name"].upper() for r in tables}
    return {
        "source": snapshot["source"], "tables": table_rows, "columns": column_rows,
        "relationships": relations,
        "summary": {
            "objects": len(table_rows), "columns": len(column_rows),
            "view_dependencies": len(relations), "document_tables": len(documented),
            "document_live_matches": len(documented & live_names),
            "document_missing": len(documented - live_names),
            "schemas": sorted({r["schema_name"] for r in table_rows}),
        },
    }


def write_package(package: dict, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, rows in (("tables.csv", package["tables"]), ("columns.csv", package["columns"]), ("relationships.csv", package["relationships"])):
        with (out_dir / name).open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else ["empty"])
            writer.writeheader()
            writer.writerows(rows)
    (out_dir / "catalog.json").write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8")


def apply_package(package: dict) -> dict:
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        system = db.scalar(select(AssetSystem).where(AssetSystem.system_code == SYSTEM_CODE))
        if not system:
            system = AssetSystem(system_code=SYSTEM_CODE, system_name_cn="嘉和电子病历（Vastbase）", system_type="EMR", target_host="10.10.8.177", system_identity_key="vastbase://10.10.8.177:5432/jhemr", status="active")
            db.add(system)
        source = db.scalar(select(AssetDataSource).where(AssetDataSource.source_code == SOURCE_CODE))
        if not source:
            source = AssetDataSource(system_code=SYSTEM_CODE, source_code=SOURCE_CODE, source_name_cn="嘉和电子病历业务库", db_type="vastbase")
            db.add(source)
        source.target_host = "10.10.8.177"; source.host_masked = host_masked_from_target(source.target_host)
        source.port = 5432; source.database_name = "jhemr"; source.service_mode = "database"; source.default_schema = "jhemr"
        source.endpoint_key = build_endpoint_key("vastbase", source.target_host, source.port)
        source.database_key = build_database_key("vastbase", source.target_host, source.port, None, source.database_name, source.service_mode)
        source.connection_identity_key = build_connection_identity_key("vastbase", source.target_host, source.port, None, source.database_name, source.service_mode)
        source.source_kind = "physical_connection"; source.business_labels = ["JHEMR", "电子病历"]
        source.write_policy = "readonly"; source.metadata_origin = "live_readonly"; source.enabled = True
        source.last_collect_status = "succeeded"; source.last_collect_at = now
        db.flush()

        db.execute(delete(AssetColumn).where(AssetColumn.source_code == SOURCE_CODE))
        db.execute(delete(AssetTable).where(AssetTable.source_code == SOURCE_CODE))
        db.execute(delete(AssetSourceSchema).where(AssetSourceSchema.source_code == SOURCE_CODE))
        db.execute(delete(AssetRelation).where(AssetRelation.domain == SYSTEM_CODE))

        for row in package["tables"]:
            db.add(AssetTable(system_code=SYSTEM_CODE, source_code=SOURCE_CODE, namespace_name=row["schema_name"], schema_name=row["schema_name"], table_name=row["table_name"], table_role=row["object_type"].lower(), comment=row["comment"], column_count=row["column_count"], pk=row["pk"], domain="电子病历", include_status="keep", confidence="live_metadata", source="JHEMR Vastbase read-only metadata", note="documented" if row["documented"] else None))
        for row in package["columns"]:
            db.add(AssetColumn(system_code=SYSTEM_CODE, source_code=SOURCE_CODE, namespace_name=row["schema_name"], schema_name=row["schema_name"], table_name=row["table_name"], column_id=row["column_id"], column_name=row["column_name"], data_type=row["data_type"], length=row["length"], nullable=row["nullable"], review_status="live_metadata"))
        schema_tables = defaultdict(int); schema_cols = defaultdict(int)
        for row in package["tables"]: schema_tables[row["schema_name"]] += 1
        for row in package["columns"]: schema_cols[row["schema_name"]] += 1
        for schema in sorted(schema_tables):
            db.add(AssetSourceSchema(source_code=SOURCE_CODE, schema_name=schema, business_labels=["JHEMR"], table_count=schema_tables[schema], column_count=schema_cols[schema], last_collect_at=now))
        # rel_id is globally unique across relationship domains. Allocate it
        # after deleting this source's previous rows so re-imports stay
        # idempotent without colliding with existing HIS/ODS relationships.
        next_rel_id = (db.scalar(select(func.max(AssetRelation.rel_id))) or 0) + 1
        for offset, row in enumerate(package["relationships"]):
            db.add(AssetRelation(rel_id=next_rel_id + offset, domain=SYSTEM_CODE, from_table=row["from_table"], to_table=row["to_table"], confidence=row["confidence"], validation_level=row["validation_level"], validation_status=row["validation_status"], note=row["note"]))
        db.commit()
        return {"status": "succeeded", **package["summary"]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--document", type=Path, required=True)
    parser.add_argument("--package-dir", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirmation", default="")
    args = parser.parse_args()
    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    package = prepare(snapshot, documented_tables(args.document))
    write_package(package, args.package_dir)
    result = {"mode": "dry_run", "writes": 0, **package["summary"]}
    if args.apply:
        if args.confirmation != CONFIRMATION:
            raise SystemExit(f"--apply requires --confirmation {CONFIRMATION}")
        result = {"mode": "apply", **apply_package(package)}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
