from __future__ import annotations

import csv
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))
ROOT = Path(__file__).resolve().parents[2]
PACKAGE_DIR = ROOT / "开发起步包" / "数据资产_HIS_READY治理导入包"

from sqlalchemy import delete, func, select

from app.core.db import SessionLocal
from app.models.asset import AssetColumn, AssetRelation, AssetTable
from app.models.asset_system import AssetDataSource, AssetSystem


SYSTEM_CODE = "HIS_SOURCE"
SOURCE_CODE = "his_ready_10_10_10_15"
OLD_HIS_SOURCE_CODE = "his_source_10_10_10_15"


def read_csv(name: str) -> list[dict[str, str]]:
    with (PACKAGE_DIR / name).open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def as_int(value: str | None, default: int = 0) -> int:
    try:
        if value is None or str(value).strip() == "":
            return default
        return int(float(str(value).strip()))
    except ValueError:
        return default


def next_id(db, model) -> int:
    current = db.scalar(select(func.max(model.id))) or 0
    return int(current) + 1


def ensure_his_source(db) -> None:
    system = db.scalar(select(AssetSystem).where(AssetSystem.system_code == SYSTEM_CODE))
    if system is None:
        system = AssetSystem(
            id=next_id(db, AssetSystem),
            system_code=SYSTEM_CODE,
            system_name_cn="HIS业务库",
            system_name_en="HIS Source",
            system_type="HIS",
            description_cn="10.10.10.15/his 多 owner HIS 业务库",
            status="active",
        )
        db.add(system)
        db.flush()

    source = db.scalar(select(AssetDataSource).where(AssetDataSource.source_code == SOURCE_CODE))
    if source is None:
        source = AssetDataSource(
            id=next_id(db, AssetDataSource),
            system_code=SYSTEM_CODE,
            source_code=SOURCE_CODE,
            source_name_cn="HIS业务库 10.10.10.15/his",
            db_type="oracle",
            host_masked="10.10.10.15",
            port=1521,
            service_name="his",
            environment="prod",
            collect_mode="readonly_query",
            credential_ref="env:CRED_HIS_SOURCE",
            enabled=True,
            description_cn="HIS_READY final 治理导入包对应数据源；只读查询。",
        )
        db.add(source)
    else:
        source.system_code = SYSTEM_CODE
        source.source_name_cn = source.source_name_cn or "HIS业务库 10.10.10.15/his"
        source.db_type = "oracle"
        source.host_masked = "10.10.10.15"
        source.port = 1521
        source.service_name = "his"
        source.environment = "prod"
        source.collect_mode = "readonly_query"
        source.credential_ref = source.credential_ref or "env:CRED_HIS_SOURCE"
        source.enabled = True


def import_tables(db, rows: list[dict[str, str]]) -> int:
    row_id = next_id(db, AssetTable)
    for row in rows:
        db.add(
            AssetTable(
                id=row_id,
                system_code=SYSTEM_CODE,
                source_code=SOURCE_CODE,
                namespace_name=row.get("namespace_name") or row.get("schema_name"),
                schema_name=row.get("schema_name"),
                table_name=row.get("table_name"),
                table_name_cn=row.get("table_comment"),
                business_desc_cn=row.get("domain"),
                table_role=row.get("table_role"),
                comment=row.get("table_comment"),
                row_count_stats=row.get("num_rows_stats"),
                column_count=as_int(row.get("column_count")),
                domain=row.get("domain"),
                grain=row.get("data_granularity"),
                pk=row.get("primary_key"),
                confidence="A",
                include_status=row.get("include_status") or "included",
                review_status=row.get("review_status") or "approved",
                note=row.get("scope_note"),
                source=row.get("source_db"),
            )
        )
        row_id += 1
    return len(rows)


def import_columns(db, rows: list[dict[str, str]]) -> int:
    row_id = next_id(db, AssetColumn)
    for row in rows:
        db.add(
            AssetColumn(
                id=row_id,
                system_code=SYSTEM_CODE,
                source_code=SOURCE_CODE,
                namespace_name=row.get("namespace_name") or row.get("schema_name"),
                schema_name=row.get("schema_name"),
                table_name=row.get("table_name"),
                column_id=as_int(row.get("column_id")),
                column_name=row.get("column_name"),
                column_name_cn=row.get("comment"),
                business_desc_cn=row.get("comment"),
                data_type=row.get("data_type"),
                length=as_int(row.get("length")),
                nullable=row.get("nullable"),
                comment=row.get("comment"),
                semantic_type=row.get("semantic_type"),
                is_sensitive=str(row.get("is_sensitive", "")).lower() == "true",
                review_status="approved",
            )
        )
        row_id += 1
    return len(rows)


def import_relations(db, rows: list[dict[str, str]]) -> int:
    row_id = next_id(db, AssetRelation)
    for idx, row in enumerate(rows, start=1):
        db.add(
            AssetRelation(
                id=row_id,
                rel_id=idx,
                domain=row.get("domain"),
                from_table=row.get("from_table"),
                from_columns=row.get("from_columns"),
                to_table=row.get("to_table"),
                to_columns=row.get("to_columns"),
                join_condition=row.get("join_condition"),
                cardinality=row.get("relationship_type"),
                confidence=row.get("confidence") or "A",
                validation_level=row.get("validation_level"),
                validation_status=row.get("validation_status"),
                validation_metrics=row.get("validation_metrics"),
                note=row.get("source_evidence"),
                validation_note=row.get("risk_note") or row.get("suggestion"),
            )
        )
        row_id += 1
    return len(rows)


def main() -> None:
    table_rows = read_csv("governance_tables_final.csv")
    column_rows = read_csv("governance_columns_final.csv")
    relation_rows = read_csv("governance_relations_formal_final.csv")

    with SessionLocal() as db:
        ensure_his_source(db)
        db.flush()

        db.execute(delete(AssetTable).where(AssetTable.source_code.in_([SOURCE_CODE, OLD_HIS_SOURCE_CODE])))
        db.execute(delete(AssetColumn).where(AssetColumn.source_code.in_([SOURCE_CODE, OLD_HIS_SOURCE_CODE])))
        db.execute(delete(AssetRelation))
        db.flush()

        table_count = import_tables(db, table_rows)
        column_count = import_columns(db, column_rows)
        relation_count = import_relations(db, relation_rows)
        db.commit()

    print(
        {
            "source_code": SOURCE_CODE,
            "tables_imported": table_count,
            "columns_imported": column_count,
            "relations_imported": relation_count,
        }
    )


if __name__ == "__main__":
    main()
