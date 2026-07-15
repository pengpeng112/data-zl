"""Validate core rmcloudlis7 relationships with bounded NOLOCK samples."""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path


RELATIONS = [
    ("L01", "dbo.req_master_pat", "dbo.req_master", ["barcode"], ["barcode"]),
    ("L02", "dbo.req_detail", "dbo.req_master", ["barcode"], ["barcode"]),
    ("L03", "dbo.lab_report", "dbo.req_master", ["reportid"], ["report_id"]),
    ("L04", "dbo.lab_result", "dbo.lab_report", ["reportid"], ["reportid"]),
    ("L05", "dbo.lab_instrdata", "dbo.lab_report", ["reportid"], ["reportid"]),
    ("L06", "dbo.lab_reportlog", "dbo.lab_report", ["reportid"], ["reportid"]),
    ("L07", "dbo.lab_reportlogdetail", "dbo.lab_reportlog", ["rpt_logid"], ["rpt_logid"]),
    ("L08", "dbo.bact_sample", "dbo.req_master", ["barcode"], ["barcode"]),
    ("L09", "dbo.bact_report", "dbo.bact_sample", ["sampleid"], ["sampleid"]),
    ("L10", "dbo.bact_report", "dbo.lab_report", ["reportid"], ["reportid"]),
    ("L11", "dbo.bact_culture", "dbo.bact_sample", ["sampleid"], ["sampleid"]),
    ("L12", "dbo.bact_culresult", "dbo.bact_culture", ["cultureid"], ["cultureid"]),
    ("L13", "dbo.bact_eval", "dbo.bact_sample", ["sampleid"], ["sampleid"]),
    ("L14", "dbo.bact_medresult", "dbo.bact_eval", ["evalid"], ["evalid"]),
    ("L15", "dbo.bact_smear", "dbo.bact_sample", ["sampleid"], ["sampleid"]),
    ("L16", "dbo.bact_smearresult", "dbo.bact_smear", ["smearid"], ["smearid"]),
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sample-size", type=int, default=10_000)
    args = parser.parse_args()
    if not 1 <= args.sample_size <= 20_000:
        raise SystemExit("sample-size must be between 1 and 20000")
    import pymssql

    connection = pymssql.connect(
        server=os.environ.get("LIS_SQLSERVER_HOST", "10.10.10.73"), port=1433,
        user=os.environ["LIS_SQLSERVER_USER"], password=os.environ["LIS_SQLSERVER_PASSWORD"],
        database=os.environ.get("LIS_SQLSERVER_DATABASE", "rmcloudlis7"),
        login_timeout=10, timeout=60, autocommit=False, appname="DataAssetReadOnlyRelationCheck",
    )
    cursor = connection.cursor()
    output = []
    try:
        cursor.execute("SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED")
        cursor.execute("SET LOCK_TIMEOUT 5000")
        for rel_id, child, parent, child_columns, parent_columns in RELATIONS:
            selected = ",".join(f"c0.[{column}]" for column in child_columns)
            nonnull = " AND ".join(f"c0.[{column}] IS NOT NULL" for column in child_columns)
            ordering = ",".join(f"c0.[{column}] DESC" for column in child_columns)
            joins = " AND ".join(f"CONVERT(NVARCHAR(4000),p.[{right}])=CONVERT(NVARCHAR(4000),c.[{left}])" for left, right in zip(child_columns, parent_columns))
            sample_sql = f'''SELECT TOP ({int(args.sample_size)}) {selected}
                               FROM {child} c0 WITH (NOLOCK) WHERE {nonnull} ORDER BY {ordering}'''
            cursor.execute(f"SELECT COUNT_BIG(*) FROM ({sample_sql}) c")
            sampled = int(cursor.fetchone()[0] or 0)
            cursor.execute(f'''SELECT COUNT_BIG(*) FROM ({sample_sql}) c
                                WHERE EXISTS(SELECT 1 FROM {parent} p WITH (NOLOCK) WHERE {joins})''')
            matched = int(cursor.fetchone()[0] or 0)
            output.append({"relationship_id": rel_id, "child_table": child, "parent_table": parent, "child_columns": child_columns, "parent_columns": parent_columns, "sampled_nonnull_keys": sampled, "matched": matched, "orphan": sampled-matched, "match_rate": round(matched/sampled, 6) if sampled else None})
        payload = {"generated_at": datetime.now(timezone.utc).isoformat(), "source": "10.10.10.73:1433/rmcloudlis7", "safety": {"isolation": "READ UNCOMMITTED", "nolock": True, "sample_limit_per_relation": args.sample_size, "source_writes": 0}, "results": output}
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"checked": len(output), "source_writes": 0}, ensure_ascii=False))
    finally:
        cursor.close(); connection.rollback(); connection.close()


if __name__ == "__main__":
    main()
