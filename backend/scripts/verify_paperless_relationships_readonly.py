"""Validate documented CDMS relationships with bounded read-only samples."""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path


# id, child table, child columns, one or more candidate parent table/columns.
RELATIONS = [
    ("P01", "T_MSS_MAIN", ["FBIHID", "FBINCU"], [("TMRDDE", ["FBIHID", "FBINCU"])]),
    ("P02", "T_MSS_SCANRECORD", ["FMAINID"], [("T_MSS_MAIN", ["FMAINID"])]),
    ("P03", "T_MSS_SCANRECORD", ["FCATEGORY"], [("T_MSS_CATEGORY", ["FSERIALNUM"])]),
    ("P04", "T_MSS_SCANRECORD", ["COLLECTPCID"], [("T_MSS_ITFCONFIG", ["FID"]), ("T_MSS_COLLECTPC", ["COLLECTPCID"])]),
    ("P05", "T_MSS_SCANRECORDHISTORY", ["FMAINID"], [("T_MSS_MAIN", ["FMAINID"])]),
    ("P06", "T_MSS_PRINTQUEUEDETAIL", ["FPRINTLISTQUEUEID"], [("T_MSS_PRINTLISTQUEUE", ["FID"])]),
    ("P07", "T_MSS_PRINTQUEUEDETAIL", ["FTYPE"], [("T_MSS_ITFCONFIG", ["FID"]), ("T_MSS_COLLECTPC", ["COLLECTPCID"])]),
    ("P08", "T_MSS_PRINTQUEUEDETAIL", ["COLLECTPCID"], [("T_MSS_ITFCONFIG", ["FID"]), ("T_MSS_COLLECTPC", ["COLLECTPCID"])]),
    ("P09", "T_MSS_COLLECTLIST", ["MID"], [("T_MSS_COLLECTMETHOD", ["MID"])]),
    ("P10", "T_MSS_BBS", ["FRECORDID"], [("T_MSS_SCANRECORD", ["FRECORDID"])]),
    ("P11", "T_MSS_GROUPLIST", ["FCATGROUPID"], [("T_MSS_CATGROUP", ["FCATGROUPID"])]),
    ("P12", "T_MSS_COLLECTLOG", ["CID"], [("T_MSS_COLLECTLIST", ["CID"])]),
    ("P13", "T_MSS_AUTHMAPPING", ["FAUTHORITYID"], [("T_MSS_AUTHORITY", ["FAUTHORITYID"])]),
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
    connection = oracledb.connect(
        user=os.environ["PAPERLESS_USER"], password=os.environ["PAPERLESS_PASSWORD"],
        dsn=os.environ.get("PAPERLESS_DSN", "10.10.10.93:1521/orcl"),
    )
    connection.call_timeout = 60_000
    cursor = connection.cursor()
    output = []
    try:
        cursor.execute("SET TRANSACTION READ ONLY")
        for rel_id, child, child_columns, parents in RELATIONS:
            selected = ",".join(f'c0."{column}"' for column in child_columns)
            nonnull = " AND ".join(f'c0."{column}" IS NOT NULL' for column in child_columns)
            exists_parts = []
            for parent, parent_columns in parents:
                joins = " AND ".join(
                    f'TO_CHAR(p."{right}")=TO_CHAR(c."{left}")'
                    for left, right in zip(child_columns, parent_columns)
                )
                exists_parts.append(f"EXISTS (SELECT 1 FROM CDMS.{parent} p WHERE {joins})")
            match_expression = " OR ".join(exists_parts)
            sql = f'''SELECT COUNT(*), SUM(CASE WHEN {match_expression} THEN 1 ELSE 0 END)
                      FROM (SELECT {selected} FROM CDMS.{child} c0 WHERE {nonnull} AND ROWNUM<=:sample_size) c'''
            cursor.execute(sql, sample_size=args.sample_size)
            sampled, matched = cursor.fetchone()
            sampled, matched = int(sampled or 0), int(matched or 0)
            output.append({
                "relationship_id": rel_id, "child_table": f"CDMS.{child}",
                "child_columns": child_columns,
                "parent_candidates": [{"table": f"CDMS.{table}", "columns": columns} for table, columns in parents],
                "sampled_nonnull_keys": sampled, "matched": matched, "orphan": sampled - matched,
                "match_rate": round(matched / sampled, 6) if sampled else None,
            })
        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": "10.10.10.93:1521/orcl", "owner": "CDMS",
            "safety": {"transaction_read_only": True, "sample_limit_per_relation": args.sample_size, "source_writes": 0},
            "results": output,
        }
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"checked": len(output), "source_writes": 0}, ensure_ascii=False))
    finally:
        cursor.close()
        connection.rollback()
        connection.close()


if __name__ == "__main__":
    main()
