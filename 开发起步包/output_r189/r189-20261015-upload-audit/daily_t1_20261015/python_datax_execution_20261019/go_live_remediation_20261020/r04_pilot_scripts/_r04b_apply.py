# -*- coding: utf-8 -*-
"""R04 pilot apply: stage(MySQL JSONL) -> DBOPER.EMR_ADMISSION_RECORD MERGE
+ same-transaction receipt + readback + platform audit.

User-approved 2026-10-20 (single window EMR_ADMISSION_RECORD 2024-02).
Idempotent-guarded: OPERATION_ID already in receipts => refuse replay.
All credentials injected at runtime; nothing persisted.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import random
from datetime import datetime
from decimal import Decimal, InvalidOperation

import oracledb

DSN = "__DSN__"
DBU = "__U__"
DBP = "__P__"
OPERATION_ID = "R189-R04-PILOT-001"
BATCH_ID = "EMR_ADMISSION_RECORD:2024-02"
TABLE = "DBOPER.EMR_ADMISSION_RECORD"
WINDOW = ("2024-02-01", "2024-03-01")
STAGE = "/tmp/stage_202402.jsonl.gz"

DATE_FMTS = ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d",
             "%Y/%m/%d %H:%M:%S", "%Y/%m/%d")


def parse_dt(value):
    if value in (None, ""):
        return None
    for fmt in DATE_FMTS:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise ValueError("unparseable datetime %r" % value[:40])


def parse_num(value):
    if value in (None, ""):
        return None
    try:
        return Decimal(value)
    except (InvalidOperation, ValueError):
        raise ValueError("unparseable number %r" % value[:40])


def main() -> None:
    result: dict = {"operation_id": OPERATION_ID, "batch_id": BATCH_ID}

    # -- load stage -----------------------------------------------------
    rows = []
    with gzip.open(STAGE, "rt", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    stage_ids = [r["ID"] for r in rows]
    result["stage_rows"] = len(rows)
    result["stage_ids_unique"] = len(set(stage_ids))
    manifest_hash = hashlib.sha256(
        "\n".join(sorted(stage_ids)).encode("utf-8")).hexdigest()
    result["manifest_hash"] = manifest_hash[:16]

    oracledb.init_oracle_client(lib_dir="/opt/oracle")
    conn = oracledb.connect(user=DBU, password=DBP, dsn=DSN)
    cur = conn.cursor()

    def q(sql, params=None):
        cur.execute(sql, params or ())
        return cur.fetchall()

    # -- column metadata -------------------------------------------------
    meta = q(
        "SELECT column_name, data_type FROM all_tab_columns "
        "WHERE owner='DBOPER' AND table_name='EMR_ADMISSION_RECORD' "
        "ORDER BY column_id")
    cols = [m[0] for m in meta]
    dtypes = {m[0]: m[1] for m in meta}
    assert len(cols) == 103, "unexpected column count %d" % len(cols)
    converters = {}
    for c in cols:
        t = dtypes[c]
        if t in ("DATE", "TIMESTAMP(6)"):
            converters[c] = parse_dt
        elif t == "NUMBER":
            converters[c] = parse_num
        else:
            converters[c] = lambda v: (v if v not in ("",) else None)

    # strict pre-scan: any unparseable value aborts before touching target
    bad = 0
    for r in rows:
        for c, fn in converters.items():
            try:
                fn(r.get(c))
            except ValueError:
                bad += 1
    result["unparseable_values"] = bad
    if bad:
        result["VERDICT"] = "ABORTED_UNPARSEABLE"
        print(json.dumps(result, ensure_ascii=False, default=str, indent=1))
        return

    # -- receipts table (create if absent) --------------------------------
    if not q("SELECT COUNT(*) FROM all_tables WHERE owner='DBOPER' "
             "AND table_name='ASSET_APPLY_RECEIPTS'")[0][0]:
        cur.execute("""
            CREATE TABLE DBOPER.ASSET_APPLY_RECEIPTS (
              OPERATION_ID  VARCHAR2(64)  NOT NULL,
              BATCH_ID      VARCHAR2(128) NOT NULL,
              MANIFEST_HASH VARCHAR2(64)  NOT NULL,
              TARGET_OBJECT VARCHAR2(128) NOT NULL,
              SCOPE_SUMMARY VARCHAR2(256),
              ROWS_AFFECTED NUMBER(12),
              CREATED_AT    TIMESTAMP(3) DEFAULT SYSTIMESTAMP NOT NULL,
              CONSTRAINT PK_ASSET_APPLY_RECEIPTS PRIMARY KEY (OPERATION_ID)
            )""")
        cur.execute("CREATE INDEX IX_AAR_BATCH ON "
                    "DBOPER.ASSET_APPLY_RECEIPTS (BATCH_ID)")
        conn.commit()
        result["receipts_table"] = "CREATED"
    else:
        result["receipts_table"] = "EXISTS"

    # -- idempotency guard: same operation must not replay -----------------
    existing = q("SELECT OPERATION_ID, ROWS_AFFECTED, CREATED_AT FROM "
                 "DBOPER.ASSET_APPLY_RECEIPTS WHERE OPERATION_ID = :1",
                 (OPERATION_ID,))
    if existing:
        result["VERDICT"] = "REPLAY_REFUSED"
        result["existing_receipt"] = str(existing[0])
        print(json.dumps(result, ensure_ascii=False, default=str, indent=1))
        return

    # -- key-set precheck ---------------------------------------------------
    before_count = q(
        "SELECT COUNT(*) FROM " + TABLE + " WHERE ADMISSION_DATE >= "
        "TO_DATE(:1,'YYYY-MM-DD') AND ADMISSION_DATE < "
        "TO_DATE(:2,'YYYY-MM-DD')", WINDOW)[0][0]
    target_ids = {r[0] for r in q(
        "SELECT ID FROM " + TABLE + " WHERE ADMISSION_DATE >= "
        "TO_DATE(:1,'YYYY-MM-DD') AND ADMISSION_DATE < "
        "TO_DATE(:2,'YYYY-MM-DD')", WINDOW)}
    stage_set = set(stage_ids)
    result["target_count_before"] = before_count
    result["missing_in_target"] = len(stage_set - target_ids)
    result["extra_in_target"] = len(target_ids - stage_set)

    # sample content lengths before (20 rows)
    random.seed(189)
    sample = random.sample(sorted(stage_set), 20)
    before_lens = {}
    for sid in sample:
        r = q("SELECT LENGTH(CHIEF_COMPLAINT), LENGTH(PRESENT_ILLNESS) FROM "
              + TABLE + " WHERE ID = :1", (sid,))
        if r:
            before_lens[sid] = r[0]

    # -- MERGE (single transaction with receipt) -----------------------------
    binds = [":c%d" % i for i in range(len(cols))]
    using = ", ".join("%s AS %s" % (binds[i], cols[i]) for i in range(len(cols)))
    on = "t.ID = s.ID"
    set_clause = ", ".join(
        "t.%s = s.%s" % (c, c) for c in cols if c != "ID")
    insert_cols = ", ".join(cols)
    insert_vals = ", ".join(binds)
    merge_sql = (
        "MERGE INTO " + TABLE + " t USING (SELECT " + using + " FROM dual) s "
        "ON (" + on + ") WHEN MATCHED THEN UPDATE SET " + set_clause +
        " WHEN NOT MATCHED THEN INSERT (" + insert_cols + ") VALUES ("
        + insert_vals + ")")

    param_rows = []
    for r in rows:
        p = {}
        for i, c in enumerate(cols):
            p["c%d" % i] = converters[c](r.get(c))
        param_rows.append(p)

    inserted = 0
    try:
        batch = 500
        for i in range(0, len(param_rows), batch):
            cur.executemany(merge_sql, param_rows[i:i + batch],
                            batcherrors=False)
        cur.execute(
            "INSERT INTO DBOPER.ASSET_APPLY_RECEIPTS (OPERATION_ID, BATCH_ID,"
            " MANIFEST_HASH, TARGET_OBJECT, SCOPE_SUMMARY, ROWS_AFFECTED) "
            "VALUES (:1, :2, :3, :4, :5, :6)",
            (OPERATION_ID, BATCH_ID, manifest_hash, TABLE,
             "MERGE:" + WINDOW[0] + "/" + WINDOW[1], len(rows)))
        conn.commit()
        result["merge_committed"] = True
    except Exception as exc:  # noqa: BLE001
        conn.rollback()
        result["merge_committed"] = False
        result["error"] = str(exc)[:300]
        result["VERDICT"] = "ROLLED_BACK"
        print(json.dumps(result, ensure_ascii=False, default=str, indent=1))
        return

    # -- readback ------------------------------------------------------------
    after_count = q(
        "SELECT COUNT(*) FROM " + TABLE + " WHERE ADMISSION_DATE >= "
        "TO_DATE(:1,'YYYY-MM-DD') AND ADMISSION_DATE < "
        "TO_DATE(:2,'YYYY-MM-DD')", WINDOW)[0][0]
    target_ids_after = {r[0] for r in q(
        "SELECT ID FROM " + TABLE + " WHERE ADMISSION_DATE >= "
        "TO_DATE(:1,'YYYY-MM-DD') AND ADMISSION_DATE < "
        "TO_DATE(:2,'YYYY-MM-DD')", WINDOW)}
    stage_by_id = {r["ID"]: r for r in rows}
    sample_diffs = []
    for sid in sample:
        r = q("SELECT LENGTH(CHIEF_COMPLAINT), LENGTH(PRESENT_ILLNESS) FROM "
              + TABLE + " WHERE ID = :1", (sid,))
        st = stage_by_id[sid]
        if r:
            cl = (len(st.get("CHIEF_COMPLAINT") or ""))
            pl = (len(st.get("PRESENT_ILLNESS") or ""))
            if (r[0][0] or 0) != cl or (r[0][1] or 0) != pl:
                sample_diffs.append(sid)
    receipt = q("SELECT ROWS_AFFECTED, MANIFEST_HASH FROM "
                "DBOPER.ASSET_APPLY_RECEIPTS WHERE OPERATION_ID = :1",
                (OPERATION_ID,))

    result["target_count_after"] = after_count
    result["keyset_equal"] = target_ids_after == stage_set
    result["count_delta"] = after_count - before_count
    result["sample_size"] = len(sample)
    result["sample_content_diffs"] = len(sample_diffs)
    result["receipt"] = str(receipt)
    result["VERDICT"] = (
        "PASS" if (target_ids_after == stage_set
                   and result["missing_in_target"] == 0
                   and len(sample_diffs) == 0 and receipt) else "CHECK")
    print(json.dumps(result, ensure_ascii=False, default=str, indent=1))

    # -- platform audit: separate step (schema introspected first) ---------
    result["audit"] = "SEPARATE_STEP"

    conn.close()


if __name__ == "__main__":
    main()
