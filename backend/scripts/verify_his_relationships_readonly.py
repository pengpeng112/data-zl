"""Recheck HIS source relationships using bounded, read-only Oracle queries.

Credentials are read from environment variables and never printed. Every data
check samples child keys behind ROWNUM before joining; no source DML/DDL is
implemented by this script.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path


RELATIONS = [
    ("R001", "MEDREC.PAT_VISIT", "MEDREC.PAT_MASTER_INDEX", [("PATIENT_ID", "PATIENT_ID")]),
    ("R002", "MEDREC.DIAGNOSIS", "MEDREC.PAT_VISIT", [("PATIENT_ID", "PATIENT_ID"), ("VISIT_ID", "VISIT_ID")]),
    ("R003", "MEDREC.OPERATION", "MEDREC.PAT_VISIT", [("PATIENT_ID", "PATIENT_ID"), ("VISIT_ID", "VISIT_ID")]),
    ("R004", "INPADM.PATS_IN_HOSPITAL", "MEDREC.PAT_VISIT", [("PATIENT_ID", "PATIENT_ID"), ("VISIT_ID", "VISIT_ID")]),
    ("R005", "INPADM.ADT_LOG", "MEDREC.PAT_VISIT", [("PATIENT_ID", "PATIENT_ID"), ("VISIT_ID", "VISIT_ID")]),
    ("R006", "ORDADM.ORDERS", "MEDREC.PAT_VISIT", [("PATIENT_ID", "PATIENT_ID"), ("VISIT_ID", "VISIT_ID")]),
    ("R007", "ORDADM.ORDERS_COSTS", "ORDADM.ORDERS", [("PATIENT_ID", "PATIENT_ID"), ("VISIT_ID", "VISIT_ID"), ("ORDER_NO", "ORDER_NO"), ("ORDER_SUB_NO", "ORDER_SUB_NO")]),
    ("R008", "ORDADM.ORDERS_EXECUTE_DETAILS", "ORDADM.ORDERS", [("PATIENT_ID", "PATIENT_ID"), ("VISIT_ID", "VISIT_ID"), ("ORDER_NO", "ORDER_NO"), ("ORDER_SUB_NO", "ORDER_SUB_NO")]),
    ("R009", "DRUG_USER.INP_ORDER_EXECDATA", "ORDADM.ORDERS", [("PATIENT_ID", "PATIENT_ID"), ("VISIT_ID", "VISIT_ID"), ("ORDER_NO", "ORDER_NO"), ("ORDER_SUB_NO", "ORDER_SUB_NO")]),
    ("R010", "DRUG_USER.INP_ORDER_EXECDATA", "DRUG_USER.PHA_INP_REQUEST_DRUG", [("PATIENT_ID", "PAT_ID"), ("VISIT_ID", "IN_COUNT"), ("ORDER_NO", "MO_ORDER"), ("ORDER_SUB_NO", "ORDER_SUB_NO")]),
    ("R011", "LAB.LAB_TEST_MASTER", "MEDREC.PAT_VISIT", [("PATIENT_ID", "PATIENT_ID"), ("VISIT_ID", "VISIT_ID")]),
    ("R012", "LAB.LAB_TEST_ITEMS", "LAB.LAB_TEST_MASTER", [("TEST_NO", "TEST_NO")]),
    ("R013", "LAB.LAB_RESULT", "LAB.LAB_TEST_MASTER", [("TEST_NO", "TEST_NO")]),
    ("R014", "LAB.LAB_TEST_ITEMS_DETAIL", "LAB.LAB_TEST_ITEMS", [("TEST_NO", "TEST_NO"), ("ITEM_NO", "ITEM_NO")]),
    ("R016", "EXAM.EXAM_MASTER", "MEDREC.PAT_VISIT", [("PATIENT_ID", "PATIENT_ID"), ("VISIT_ID", "VISIT_ID")]),
    ("R017", "EXAM.EXAM_REPORT", "EXAM.EXAM_MASTER", [("EXAM_NO", "EXAM_NO")]),
    ("R018", "EXAM.EXAM_ITEMS", "EXAM.EXAM_MASTER", [("EXAM_NO", "EXAM_NO")]),
    ("R019", "EXAM.EXAM_BILL_ITEMS", "EXAM.EXAM_MASTER", [("EXAM_NO", "EXAM_NO")]),
    ("R021", "INPBILL.INP_SETTLE_MASTER", "MEDREC.PAT_VISIT", [("PATIENT_ID", "PATIENT_ID"), ("VISIT_ID", "VISIT_ID")]),
    ("R022", "INPBILL.INP_BILL_DETAIL", "MEDREC.PAT_VISIT", [("PATIENT_ID", "PATIENT_ID"), ("VISIT_ID", "VISIT_ID")]),
    ("R023", "INPBILL.INP_BILL_DETAIL", "INPBILL.INP_SETTLE_MASTER", [("RCPT_NO", "RCPT_NO")]),
    ("R024", "INPBILL.PREPAYMENT_RCPT", "MEDREC.PAT_MASTER_INDEX", [("PATIENT_ID", "PATIENT_ID")]),
    ("R025", "INPBILL.PREPAYMENT_RCPT", "MEDREC.PAT_VISIT", [("PATIENT_ID", "PATIENT_ID"), ("VISIT_ID", "VISIT_ID")]),
    ("R026", "INPBILL.PREPAYMENT_RCPT", "INPBILL.PREPAYMENT_RCPT", [("REFUNDED_RCPT_NO", "RCPT_NO")]),
    ("R027", "OUTPADM.CLINIC_MASTER", "MEDREC.PAT_MASTER_INDEX", [("PATIENT_ID", "PATIENT_ID")]),
    ("R028", "OUTPBILL.OUTP_BILL_ITEMS", "OUTPBILL.OUTP_RCPT_MASTER", [("RCPT_NO", "RCPT_NO")]),
    ("R029", "OUTPBILL.OUTP_RCPT_MASTER", "MEDREC.PAT_MASTER_INDEX", [("PATIENT_ID", "PATIENT_ID")]),
    ("R030", "DRUG_USER.PHA_INP_REQUEST_DRUG", "MEDREC.PAT_VISIT", [("PAT_ID", "PATIENT_ID"), ("IN_COUNT", "VISIT_ID")]),
    ("R031", "DRUG_USER.PHA_INP_REQUEST_DRUG", "ORDADM.ORDERS", [("PAT_ID", "PATIENT_ID"), ("IN_COUNT", "VISIT_ID"), ("MO_ORDER", "ORDER_NO"), ("ORDER_SUB_NO", "ORDER_SUB_NO")]),
    ("R032", "DRUG_USER.PHA_INP_DISPDETAIL", "DRUG_USER.PHA_INP_REQUEST_DRUG", [("REQUEST_NO", "REQUEST_NO")]),
    ("R033", "DRUG_USER.PHA_CLI_REQUEST_DRUG", "MEDREC.PAT_MASTER_INDEX", [("PAT_ID", "PATIENT_ID")]),
]

# These links are inpatient-only. VISIT_ID=0/NULL belongs to outpatient or
# other source subsets and must never be counted as a failed inpatient link.
CHILD_EXTRA_FILTERS = {
    "R011": 'c0."VISIT_ID" <> 0',
    "R016": 'c0."VISIT_ID" <> 0',
    "R025": 'c0."VISIT_ID" <> 0',
}


def split_name(name: str) -> tuple[str, str]:
    owner, table = name.split(".", 1)
    return owner.upper(), table.upper()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sample-size", type=int, default=10_000)
    args = parser.parse_args()
    if not 1 <= args.sample_size <= 20_000:
        raise SystemExit("sample-size must be between 1 and 20000")

    import oracledb

    # HIS is Oracle 11g and therefore requires python-oracledb thick mode.
    # The production container mounts the managed Instant Client read-only.
    oracledb.init_oracle_client(lib_dir=os.environ.get("APP_ORACLE_CLIENT_LIB_DIR", "/opt/oracle"))

    user = os.environ["HIS_VERIFY_USER"]
    password = os.environ["HIS_VERIFY_PASSWORD"]
    dsn = os.environ.get("HIS_VERIFY_DSN", "10.10.10.15:1521/his")
    conn = oracledb.connect(user=user, password=password, dsn=dsn)
    conn.call_timeout = 60_000
    cursor = conn.cursor()
    results = []
    try:
        cursor.execute("SET TRANSACTION READ ONLY")
        cursor.execute("SELECT SYS_CONTEXT('USERENV','DB_NAME'), SYS_CONTEXT('USERENV','CURRENT_USER') FROM DUAL")
        database, current_user = cursor.fetchone()
        for rel_id, child, parent, keys in RELATIONS:
            child_owner, child_table = split_name(child)
            parent_owner, parent_table = split_name(parent)
            required = {(child_owner, child_table, a) for a, _ in keys} | {(parent_owner, parent_table, b) for _, b in keys}
            found = set()
            for owner, table in {(child_owner, child_table), (parent_owner, parent_table)}:
                cursor.execute(
                    "SELECT OWNER, TABLE_NAME, COLUMN_NAME FROM ALL_TAB_COLUMNS WHERE OWNER=:1 AND TABLE_NAME=:2",
                    [owner, table],
                )
                found.update(tuple(str(v).upper() for v in row) for row in cursor.fetchall())
            missing = sorted(".".join(item) for item in required - found)
            item = {"relationship_id": rel_id, "from_table": child, "to_table": parent, "keys": keys, "missing_columns": missing}
            if missing:
                item["status"] = "structure_failed"
                results.append(item)
                continue
            child_cols = ", ".join(f'c0."{left}"' for left, _ in keys)
            nonnull_parts = [f'c0."{left}" IS NOT NULL' for left, _ in keys]
            if rel_id in CHILD_EXTRA_FILTERS:
                nonnull_parts.append(CHILD_EXTRA_FILTERS[rel_id])
            nonnull = " AND ".join(nonnull_parts)
            joins = " AND ".join(f'p."{right}" = c."{left}"' for left, right in keys)
            sql = f'''SELECT COUNT(*), SUM(CASE WHEN EXISTS (SELECT 1 FROM {parent} p WHERE {joins}) THEN 1 ELSE 0 END)
                      FROM (SELECT {child_cols} FROM {child} c0 WHERE {nonnull} AND ROWNUM <= :sample_size) c'''
            cursor.execute(sql, sample_size=args.sample_size)
            sampled, matched = cursor.fetchone()
            sampled, matched = int(sampled or 0), int(matched or 0)
            item.update({"status": "sample_checked", "sampled_nonnull_keys": sampled, "matched": matched, "orphan": sampled - matched, "match_rate": round(matched / sampled, 6) if sampled else None})
            results.append(item)
        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "database": str(database),
            "account_masked": current_user[0] + "***" + current_user[-1] if len(current_user) > 2 else "***",
            "safety": {"transaction_read_only": True, "sample_limit_per_relation": args.sample_size, "source_writes": 0},
            "relations_in_baseline": 33,
            "relations_sample_checked": len(RELATIONS),
            "structure_only_relations": ["R015", "R020"],
            "results": results,
        }
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"database": database, "checked": len(results), "structure_failed": sum(r["status"] == "structure_failed" for r in results), "sample_checked": sum(r["status"] == "sample_checked" for r in results), "source_writes": 0}, ensure_ascii=False))
    finally:
        cursor.close()
        conn.rollback()
        conn.close()


if __name__ == "__main__":
    main()
