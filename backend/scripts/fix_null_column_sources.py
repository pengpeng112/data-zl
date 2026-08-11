"""93 号 v3 · 步 3 · T1.3 修复 26894 行列 source_code 悬空。

用 (schema_name, table_name) 匹配 asset_tables 回填 source_code/system_code。
执行前 dry-run 校验:总数 + 歧义表数(必须 0)。

用法(容器内):
    python -m scripts.fix_null_column_sources --dry-run   # 预览计数
    python -m scripts.fix_null_column_sources             # 正式回填
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import text
from app.core.db import SessionLocal


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    db = SessionLocal()
    try:
        # dry-run 校验
        null_cnt = db.execute(text("SELECT count(*) FROM asset.asset_columns WHERE source_code IS NULL")).scalar() or 0
        ambig = db.execute(text("""
            SELECT count(*) FROM (
              SELECT schema_name, table_name FROM asset.asset_tables
              WHERE (schema_name, table_name) IN
                (SELECT DISTINCT schema_name, table_name FROM asset.asset_columns WHERE source_code IS NULL)
              GROUP BY 1,2 HAVING count(*)>1
            ) x
        """)).scalar() or 0
        result = {"null_count": int(null_cnt), "ambiguous_tables": int(ambig)}
        if ambig != 0:
            result["status"] = "ABORT_ambiguous"
            result["message"] = f"歧义表 {ambig} 张,停止,请人工裁决"
            print(json.dumps(result, ensure_ascii=False)); return
        if null_cnt == 0:
            result["status"] = "ALREADY_DONE"
            print(json.dumps(result, ensure_ascii=False)); return

        if args.dry_run:
            result["status"] = "DRY_RUN_OK"
            result["will_update"] = int(null_cnt)
            print(json.dumps(result, ensure_ascii=False)); return

        # 正式回填
        r = db.execute(text("""
            UPDATE asset.asset_columns c
            SET source_code = t.source_code, system_code = t.system_code
            FROM asset.asset_tables t
            WHERE c.source_code IS NULL
              AND c.schema_name = t.schema_name
              AND c.table_name = t.table_name
        """))
        updated = r.rowcount
        db.commit()
        remain = db.execute(text("SELECT count(*) FROM asset.asset_columns WHERE source_code IS NULL")).scalar() or 0
        result["updated"] = updated
        result["remaining_null"] = int(remain)
        result["status"] = "OK" if remain == 0 else "PARTIAL"
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as e:
        db.rollback()
        print(json.dumps({"error": f"{type(e).__name__}: {e}"}, ensure_ascii=False))
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
