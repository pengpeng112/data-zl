"""Synchronize confirmed HIS review-view metadata into platform PostgreSQL.

The HIS business database is queried through DatabaseConnector.execute_readonly
only.  Applying writes only asset.asset_* platform metadata and never changes
the HIS source database.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

from sqlalchemy import delete, func, select

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.core.db import SessionLocal
from app.models.asset import AssetColumn, AssetRelation, AssetTable
from app.services.relation_identity import populate_endpoint_fields
from app.models.asset_system import AssetDataSource, AssetSourceSchema
from app.services.credentials import resolve
from app.services.db_connectors import DB_CONNECTOR_MAP

SOURCE_CODE = "his_source_10_10_10_15"
VIEW_OWNER = "HISUSER"
VIEW_NAMES = ("V_EMR_EXAM_IMAGE_REP", "V_EMR_EXAM_IMAGE_PATH")
DOMAIN = "HIS_SOURCE_VIEW_LINEAGE"
CONFIRMATION = "SYNC-HIS-REVIEW-VIEWS"


def collect(db) -> tuple[list[dict], list[dict], list[dict]]:
    source = db.scalar(select(AssetDataSource).where(AssetDataSource.source_code == SOURCE_CODE))
    if not source:
        raise RuntimeError(f"platform source not found: {SOURCE_CODE}")
    user, password = resolve(source.credential_ref)
    if not user or not password:
        raise RuntimeError("HIS read-only credential is not configured")
    connector_cls = DB_CONNECTOR_MAP.get((source.db_type or "").lower())
    if not connector_cls:
        raise RuntimeError(f"unsupported HIS source db_type: {source.db_type}")
    connector = connector_cls(
        host=source.target_host or source.host_masked,
        port=source.port or 1521,
        database=source.service_name or source.database_name,
        user=user,
        password=password,
        connection_mode=source.connection_mode or "ssh_jump",
        **(source.connection_options or {}),
    )
    names_sql = ",".join(f"'{name}'" for name in VIEW_NAMES)
    objects = connector.execute_readonly(
        "SELECT owner, object_name, status FROM all_objects "
        f"WHERE owner='{VIEW_OWNER}' AND object_type='VIEW' AND object_name IN ({names_sql}) "
        "ORDER BY object_name",
        max_rows=20,
    )
    columns = connector.execute_readonly(
        "SELECT owner, table_name, column_id, column_name, data_type, data_length, "
        "data_precision, data_scale, nullable FROM all_tab_columns "
        f"WHERE owner='{VIEW_OWNER}' AND table_name IN ({names_sql}) "
        "ORDER BY table_name, column_id",
        max_rows=1000,
    )
    dependencies = connector.execute_readonly(
        "SELECT owner, name, referenced_owner, referenced_name, referenced_type "
        "FROM all_dependencies "
        f"WHERE owner='{VIEW_OWNER}' AND name IN ({names_sql}) "
        "AND referenced_type IN ('TABLE','VIEW') "
        "ORDER BY name, referenced_owner, referenced_name",
        max_rows=1000,
    )
    found = {row["OBJECT_NAME"] for row in objects if row.get("STATUS") == "VALID"}
    missing = sorted(set(VIEW_NAMES) - found)
    if missing:
        raise RuntimeError(f"missing or invalid HIS review views: {', '.join(missing)}")
    return objects, columns, dependencies


def apply_platform(db, objects: list[dict], columns: list[dict], dependencies: list[dict]) -> dict:
    table_names = [row["OBJECT_NAME"] for row in objects]
    db.execute(
        delete(AssetColumn).where(
            AssetColumn.source_code == SOURCE_CODE,
            AssetColumn.schema_name == VIEW_OWNER,
            AssetColumn.table_name.in_(table_names),
        )
    )
    db.execute(
        delete(AssetTable).where(
            AssetTable.source_code == SOURCE_CODE,
            AssetTable.schema_name == VIEW_OWNER,
            AssetTable.table_name.in_(table_names),
        )
    )
    for row in objects:
        db.add(
            AssetTable(
                system_code="HIS_SOURCE",
                source_code=SOURCE_CODE,
                namespace_name=VIEW_OWNER,
                schema_name=VIEW_OWNER,
                table_name=row["OBJECT_NAME"],
                table_role="view",
                domain="影像检查报告",
                include_status="keep",
                review_status="reviewed",
                confidence="live_metadata",
                source="HIS read-only data dictionary",
                note=f"three-level review view; source status={row['STATUS']}",
            )
        )
    for row in columns:
        precision = row.get("DATA_PRECISION")
        scale = row.get("DATA_SCALE")
        data_type = row["DATA_TYPE"]
        if precision is not None:
            data_type += f"({precision}{',' + str(scale) if scale is not None else ''})"
        db.add(
            AssetColumn(
                system_code="HIS_SOURCE",
                source_code=SOURCE_CODE,
                namespace_name=VIEW_OWNER,
                schema_name=VIEW_OWNER,
                table_name=row["TABLE_NAME"],
                column_id=row["COLUMN_ID"],
                column_name=row["COLUMN_NAME"],
                data_type=data_type,
                length=row.get("DATA_LENGTH"),
                nullable=row.get("NULLABLE"),
                review_status="live_metadata",
            )
        )
    db.execute(delete(AssetRelation).where(AssetRelation.domain == DOMAIN))
    next_id = (db.scalar(select(func.max(AssetRelation.rel_id))) or 0) + 1
    seen = set()
    for row in dependencies:
        key = (row["NAME"], row["REFERENCED_OWNER"], row["REFERENCED_NAME"])
        if key in seen:
            continue
        seen.add(key)
        _rel = AssetRelation(
                rel_id=next_id + len(seen) - 1,
                domain=DOMAIN,
                from_table=f"{VIEW_OWNER}.{row['NAME']}",
                from_columns="",
                to_table=f"{row['REFERENCED_OWNER']}.{row['REFERENCED_NAME']}",
                to_columns="",
                join_condition="view dependency",
                confidence="B",
                validation_level="oracle_data_dictionary",
                validation_status="verified_dependency",
                note=f"ALL_DEPENDENCIES referenced_type={row['REFERENCED_TYPE']}; not a business foreign key",
            )
        populate_endpoint_fields(db, _rel)
        db.add(_rel)
    schema = db.scalar(
        select(AssetSourceSchema).where(
            AssetSourceSchema.source_code == SOURCE_CODE,
            AssetSourceSchema.schema_name == VIEW_OWNER,
        )
    )
    if not schema:
        schema = AssetSourceSchema(source_code=SOURCE_CODE, schema_name=VIEW_OWNER)
        db.add(schema)
    schema.business_labels = ["HIS", "影像检查", "三甲复审视图"]
    schema.table_count = db.scalar(
        select(func.count()).where(
            AssetTable.source_code == SOURCE_CODE,
            AssetTable.schema_name == VIEW_OWNER,
        )
    ) or len(objects)
    schema.column_count = db.scalar(
        select(func.count()).where(
            AssetColumn.source_code == SOURCE_CODE,
            AssetColumn.schema_name == VIEW_OWNER,
        )
    ) or len(columns)
    return {"views": len(objects), "columns": len(columns), "dependencies": len(seen)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirmation", default="")
    args = parser.parse_args()
    with SessionLocal() as db:
        objects, columns, dependencies = collect(db)
        summary = {
            "views": len(objects),
            "columns": len(columns),
            "dependencies": len({(r['NAME'], r['REFERENCED_OWNER'], r['REFERENCED_NAME']) for r in dependencies}),
            "source_writes": 0,
        }
        if not args.apply:
            print(json.dumps({"mode": "dry_run", "writes": 0, "summary": summary}, ensure_ascii=False, indent=2))
            return
        if args.confirmation != CONFIRMATION:
            raise SystemExit(f"--apply requires --confirmation {CONFIRMATION}")
        applied = apply_platform(db, objects, columns, dependencies)
        db.commit()
    print(json.dumps({"mode": "apply", "status": "succeeded", "platform": applied, "source_writes": 0}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
