"""Validate PACS MySQL relationships with bounded, read-only samples."""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path


# id, child table, child column, child order key, parent table, parent column, evidence
RELATIONS = [
    ("P01", "OrderInfo", "PatientIntraID", "OrderID", "PatientInfo", "PatientIntraID", "declared_fk"),
    ("P02", "ExamInfo", "PatientIntraID", "ExamID", "PatientInfo", "PatientIntraID", "view_sql_and_model"),
    ("P03", "ExamInfo", "OrderID", "ExamID", "OrderInfo", "OrderID", "model"),
    ("P04", "ExamInfo", "ReportID", "ExamID", "Report", "ReportID", "view_sql_and_model"),
    ("P05", "ReportAction", "ReportID", "ReportActionID", "Report", "ReportID", "model"),
    ("P06", "ReportAction", "ReportHistoryID", "ReportActionID", "ReportHistory", "ReportHistoryID", "model"),
    ("P07", "ReportParticipant", "ReportActionID", "ReportParticipantID", "ReportAction", "ReportActionID", "model"),
    ("P08", "MPPS", "ExamID", "MPPSID", "ExamInfo", "ExamID", "view_sql"),
    ("P09", "exam_attach_info", "ExamID", "ExamID", "ExamInfo", "ExamID", "model"),
    ("P10", "pacsstudy", "study_instance_uid", "pacsstudy_id", "ExamInfo", "StudyInstanceUID", "dicom_key"),
]


def quote(name: str) -> str:
    return "`" + name.replace("`", "``") + "`"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--sample-size", type=int, default=10_000)
    args = parser.parse_args()
    if not 1 <= args.sample_size <= 20_000:
        raise SystemExit("sample-size must be between 1 and 20000")

    import pymysql

    connection = pymysql.connect(
        host=os.environ.get("PACS_MYSQL_HOST", "10.10.10.191"),
        port=int(os.environ.get("PACS_MYSQL_PORT", "3306")),
        user=os.environ["PACS_MYSQL_USER"],
        password=os.environ["PACS_MYSQL_PASSWORD"],
        database=os.environ.get("PACS_MYSQL_DATABASE", "gecris"),
        charset="utf8mb4",
        connect_timeout=10,
        read_timeout=90,
        write_timeout=15,
        autocommit=False,
        cursorclass=pymysql.cursors.DictCursor,
        program_name="DataAssetReadOnlyRelationValidation",
    )
    results = []
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET SESSION TRANSACTION READ ONLY")
            cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ UNCOMMITTED")
            cursor.execute("SET SESSION MAX_EXECUTION_TIME=60000")
            for relation_id, child, child_col, order_col, parent, parent_col, evidence in RELATIONS:
                sample = (
                    f"SELECT {quote(child_col)} AS relation_key FROM {quote(child)} "
                    f"WHERE {quote(child_col)} IS NOT NULL "
                    f"ORDER BY {quote(order_col)} DESC LIMIT {args.sample_size}"
                )
                cursor.execute(f"SELECT COUNT(*) AS n FROM ({sample}) AS sample_keys")
                sampled = int(cursor.fetchone()["n"])
                cursor.execute(
                    f"SELECT COUNT(*) AS n FROM ({sample}) AS c "
                    f"WHERE EXISTS (SELECT 1 FROM {quote(parent)} AS p "
                    f"WHERE p.{quote(parent_col)}=c.relation_key)"
                )
                matched = int(cursor.fetchone()["n"])
                results.append(
                    {
                        "relationship_id": relation_id,
                        "child": f"gecris.{child}",
                        "child_column": child_col,
                        "parent": f"gecris.{parent}",
                        "parent_column": parent_col,
                        "evidence": evidence,
                        "sampled_nonnull_keys": sampled,
                        "matched": matched,
                        "orphan": sampled - matched,
                        "match_rate": matched / sampled if sampled else None,
                    }
                )
    finally:
        connection.rollback()
        connection.close()

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": {"host": os.environ.get("PACS_MYSQL_HOST", "10.10.10.191"), "database": "gecris"},
        "safety": {"transaction_read_only": True, "sample_limit": args.sample_size, "source_writes": 0},
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(results, ensure_ascii=False))


if __name__ == "__main__":
    main()
