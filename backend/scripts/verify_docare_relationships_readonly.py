"""Validate core Docare anesthesia relationships using bounded read-only samples."""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path


RELATIONS = [
    ("D01", "MEDCOMM.MED_PAT_VISIT", "MEDCOMM.MED_PAT_MASTER_INDEX", ["PATIENT_ID"]),
    ("D02", "MEDSURGERY.MED_OPERATION_SCHEDULE", "MEDCOMM.MED_PAT_VISIT", ["PATIENT_ID", "VISIT_ID"]),
    ("D03", "MEDSURGERY.MED_SCHEDULED_OPERATION_NAME", "MEDSURGERY.MED_OPERATION_SCHEDULE", ["PATIENT_ID", "VISIT_ID", "SCHEDULE_ID"]),
    ("D04", "MEDSURGERY.MED_OPERATION_MASTER", "MEDCOMM.MED_PAT_VISIT", ["PATIENT_ID", "VISIT_ID"]),
    ("D05", "MEDSURGERY.MED_OPERATION_NAME", "MEDSURGERY.MED_OPERATION_MASTER", ["PATIENT_ID", "VISIT_ID", "OPER_ID"]),
    ("D06", "MEDSURGERY.MED_ANESTHESIA_PLAN", "MEDSURGERY.MED_OPERATION_MASTER", ["PATIENT_ID", "VISIT_ID", "OPER_ID"]),
    ("D07", "MEDSURGERY.MED_ANESTHESIA_SUMMARY", "MEDSURGERY.MED_OPERATION_MASTER", ["PATIENT_ID", "VISIT_ID", "OPER_ID"]),
    ("D08", "MEDSURGERY.MED_ANESTHESIA_EVENT", "MEDSURGERY.MED_OPERATION_MASTER", ["PATIENT_ID", "VISIT_ID", "OPER_ID"]),
    ("D09", "MEDSURGERY.MED_ANESTHESIA_EVENT_BACK", "MEDSURGERY.MED_OPERATION_MASTER", ["PATIENT_ID", "VISIT_ID", "OPER_ID"]),
    ("D10", "MEDSURGERY.MED_ANESTHESIA_INPUT_DATA", "MEDSURGERY.MED_OPERATION_MASTER", ["PATIENT_ID", "VISIT_ID", "OPER_ID"]),
    ("D11", "MEDSURGERY.MED_PAT_MONITOR_DATA", "MEDSURGERY.MED_OPERATION_MASTER", ["PATIENT_ID", "VISIT_ID", "OPER_ID"]),
    ("D12", "MEDSURGERY.MED_PATIENT_MONITOR_DATA", "MEDSURGERY.MED_OPERATION_MASTER", ["PATIENT_ID", "VISIT_ID", "OPER_ID"]),
    ("D13", "MEDSURGERY.MED_PAT_MONITOR_DATA_HISTORY", "MEDSURGERY.MED_OPERATION_MASTER", ["PATIENT_ID", "VISIT_ID", "OPER_ID"]),
    ("D14", "MEDSURGERY.MED_OPERATION_ANALGESIC", "MEDSURGERY.MED_OPERATION_MASTER", ["PATIENT_ID", "VISIT_ID", "OPER_ID"]),
    ("D15", "MEDSURGERY.MED_ANES_OPERHANDOVER", "MEDSURGERY.MED_OPERATION_MASTER", ["PATIENT_ID", "VISIT_ID", "OPER_ID"]),
    ("D16", "MEDSURGERY.MED_ANES_DOC_CHECK", "MEDSURGERY.MED_OPERATION_MASTER", ["PATIENT_ID", "VISIT_ID", "OPER_ID"]),
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sample-size", type=int, default=10_000)
    args = parser.parse_args()
    if not 1 <= args.sample_size <= 20_000:
        raise SystemExit("sample-size must be between 1 and 20000")
    import oracledb

    oracledb.init_oracle_client(lib_dir=os.environ.get("APP_ORACLE_CLIENT_LIB_DIR", "/opt/oracle"))
    connection = oracledb.connect(user=os.environ["DOCARE_USER"], password=os.environ["DOCARE_PASSWORD"], dsn=os.environ.get("DOCARE_DSN", "10.10.10.68:1521/docare"))
    connection.call_timeout = 60_000
    cursor = connection.cursor()
    output = []
    try:
        cursor.execute("SET TRANSACTION READ ONLY")
        for rel_id, child, parent, columns in RELATIONS:
            selected = ",".join(f'c0."{column}"' for column in columns)
            nonnull = " AND ".join(f'c0."{column}" IS NOT NULL' for column in columns)
            joins = " AND ".join(f'TO_CHAR(p."{column}")=TO_CHAR(c."{column}")' for column in columns)
            sql = f'''SELECT COUNT(*),SUM(CASE WHEN EXISTS(SELECT 1 FROM {parent} p WHERE {joins}) THEN 1 ELSE 0 END)
                      FROM (SELECT {selected} FROM {child} c0 WHERE {nonnull} AND ROWNUM<=:sample_size) c'''
            cursor.execute(sql, sample_size=args.sample_size)
            sampled, matched = cursor.fetchone(); sampled, matched = int(sampled or 0), int(matched or 0)
            output.append({"relationship_id": rel_id, "child_table": child, "parent_table": parent, "columns": columns, "sampled_nonnull_keys": sampled, "matched": matched, "orphan": sampled-matched, "match_rate": round(matched/sampled, 6) if sampled else None})
        payload = {"generated_at": datetime.now(timezone.utc).isoformat(), "source": "10.10.10.68:1521/docare", "safety": {"transaction_read_only": True, "sample_limit_per_relation": args.sample_size, "source_writes": 0}, "results": output}
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"checked": len(output), "source_writes": 0}, ensure_ascii=False))
    finally:
        cursor.close(); connection.rollback(); connection.close()


if __name__ == "__main__":
    main()
