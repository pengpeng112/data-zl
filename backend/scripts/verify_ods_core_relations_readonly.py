"""93 号 v3 · 步 6 · ODS 核心关系抽样验证(只读)。简化版 SQL 构造。

对 G1(INP_BILL_DETAIL→PAT_VISIT) / G2(CLINIC_MASTER→PAT_MASTER_INDEX) 抽样验证。
G3 跨库不验证。

用法: 凭据环境变量 ODS_8_216_USER / ODS_8_216_PASSWORD
"""
from __future__ import annotations
import json, os, time
from datetime import datetime, timezone
from pathlib import Path

RELATIONS = [
    ("G1", "HIS", "INP_BILL_DETAIL", "HIS", "PAT_VISIT",
     [("PATIENT_ID", "PATIENT_ID"), ("VISIT_ID", "VISIT_ID")], 1000),
    ("G2", "HIS", "CLINIC_MASTER", "HIS", "PAT_MASTER_INDEX",
     [("PATIENT_ID", "PATIENT_ID")], 10000),
]

OUTPUT = Path("/app/开发起步包/95_ODS核心关系抽样验证结果.json")
if not OUTPUT.parent.exists():
    OUTPUT = Path("/tmp/95_ODS核心关系抽样验证结果.json")


def connect_with_retry(max_retries=3, interval=30):
    import oracledb
    try:
        oracledb.init_oracle_client(lib_dir=os.environ.get("APP_ORACLE_CLIENT_LIB_DIR", "/opt/oracle"))
    except Exception:
        pass
    user = os.environ.get("ODS_8_216_USER", "ods")
    pwd = os.environ["ODS_8_216_PASSWORD"]
    dsn = os.environ.get("ODS_8_216_DSN", "10.10.8.216:1521/orcl")
    last = None
    for i in range(max_retries):
        try:
            conn = oracledb.connect(user=user, password=pwd, dsn=dsn)
            conn.call_timeout = 120_000
            return conn
        except Exception as e:
            last = e
            if i < max_retries - 1: time.sleep(interval)
    raise last


def main():
    result = {"verified_at": datetime.now(timezone.utc).isoformat(), "relations": [], "status": "ok"}
    try:
        conn = connect_with_retry()
    except Exception as e:
        result["status"] = "skipped_ods_unreachable"
        result["error"] = f"{type(e).__name__}: ODS 连接失败(重试3次),不阻塞,draft 保留"
        OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    cur = conn.cursor()
    try:
        cur.execute("SET TRANSACTION READ ONLY")
        cur.execute("SELECT SYS_CONTEXT('USERENV','DB_NAME'), SYS_CONTEXT('USERENV','CURRENT_USER') FROM DUAL")
        row = cur.fetchone()
        result["database"] = row[0] if row else None
        result["current_user"] = row[1] if row else None

        for rel_id, c_owner, c_tbl, p_owner, p_tbl, keys, sample_size in RELATIONS:
            ck = keys[0][0]  # 第一个子表键
            # 1. 子表采样计数(键非空 + ROWNUM 限量)
            notnull_filter = " AND ".join(f'c0."{k}" IS NOT NULL' for k, _ in keys)
            count_sql = f'SELECT count(*) FROM (SELECT 1 FROM "{c_owner}"."{c_tbl}" c0 WHERE {notnull_filter} AND ROWNUM <= {sample_size})'
            cur.execute(count_sql)
            total = cur.fetchone()[0]

            # 2. 孤儿数:子表采样(选全部键列) LEFT JOIN 父表,父表键为 NULL 的行
            join_on = " AND ".join(f'c0."{ck}" = p1."{pk}"' for ck, pk in keys)
            all_ck_cols = ", ".join(f'c0."{k}"' for k, _ in keys)
            orphan_sql = (
                f'SELECT count(*) FROM ('
                f' SELECT {all_ck_cols} FROM "{c_owner}"."{c_tbl}" c0 '
                f' WHERE {notnull_filter} AND ROWNUM <= {sample_size}'
                f') c0 LEFT JOIN "{p_owner}"."{p_tbl}" p1 ON {join_on} '
                f'WHERE p1."{keys[0][1]}" IS NULL'
            )
            cur.execute(orphan_sql)
            orphan = cur.fetchone()[0]

            matched = total - orphan
            rate = matched / total if total else 0
            result["relations"].append({
                "rel_id": rel_id, "child": f"{c_owner}.{c_tbl}", "parent": f"{p_owner}.{p_tbl}",
                "sample_size": sample_size, "total": total, "matched": matched,
                "orphan": orphan, "match_rate": round(rate, 4), "pass": rate >= 0.99,
            })
    finally:
        try: cur.close(); conn.close()
        except Exception: pass

    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
