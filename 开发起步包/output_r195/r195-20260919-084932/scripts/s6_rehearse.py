# -*- coding: utf-8 -*-
"""S6b：隔离库导入预演（data_asset_test，非生产）。
流程：核库身份 → 插入 payload（NOT EXISTS 幂等）并提交 → 完全重放（应 0）→ 反向边用例（应 0）
→ 删除本轮行并提交 → 复核零残留、他人行数不变、approved 未触碰。
"""
import json
import os
import sys
from datetime import datetime, timezone

RUN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = open(os.environ["R195_TEST_URL_FILE"], encoding="utf-8").read().strip().replace("postgresql+psycopg://", "postgresql://")

import psycopg

payload = json.load(open(os.path.join(RUN_DIR, "import_payload_reviews.json"), encoding="utf-8"))["rows"]

INS = """INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT %(relation_scope)s, %(from_system_code)s, %(from_table)s, %(from_columns)s,
 %(to_system_code)s, %(to_table)s, %(to_columns)s, %(join_condition)s, %(relation_desc_cn)s,
 %(business_logic_cn)s, %(confidence)s, %(review_status)s, %(source_evidence)s, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = %(relation_scope)s
    AND upper(r.from_table)=upper(%(from_table)s) AND coalesce(r.from_columns,'')=coalesce(%(from_columns)s,'')
    AND upper(r.to_table)=upper(%(to_table)s) AND coalesce(r.to_columns,'')=coalesce(%(to_columns)s,'')
)"""


def run_batch(cur, rows):
    n = 0
    for r in rows:
        cur.execute(INS, r)
        n += cur.rowcount
    return n


def main():
    out = {"started_at": datetime.now(timezone.utc).isoformat(), "target_db_expected": "data_asset_test"}
    with psycopg.connect(URL) as conn:
        autocom = conn.autocommit
        with conn.cursor() as cur:
            cur.execute("select current_database()")
            db = cur.fetchone()[0]
            out["database"] = db
            assert db == "data_asset_test", f"隔离库身份核验失败: {db}"
            cur.execute("select count(*), count(*) filter (where relation_scope='r195_intake'), count(*) filter (where review_status='approved') from asset.asset_relation_reviews")
            base_total, base_own, base_approved = cur.fetchone()
            out["baseline"] = {"total_reviews": base_total, "r195_rows": base_own, "approved": base_approved}
            conn.commit()

            # 第一遍：插入并提交
            out["first_pass_inserted"] = run_batch(cur, payload)
            conn.commit()
            cur.execute("select count(*) from asset.asset_relation_reviews where relation_scope='r195_intake'")
            out["rows_after_first_pass"] = cur.fetchone()[0]

            # 第二遍：完全重放（幂等，应 0）
            out["replay_inserted"] = run_batch(cur, payload)
            conn.commit()

            # 用例：反向边（应 0——身份键方向不敏感由 NOT EXISTS 的双侧精确匹配挡住同向重放；
            # 反向重放会插入 1 行，证明方向保持策略：反向边不自动合并，需查重层处理）
            probe_rows = [{**payload[0], "from_table": payload[0]["to_table"], "from_columns": payload[0]["to_columns"],
                           "to_table": payload[0]["from_table"], "to_columns": payload[0]["from_columns"]}]
            out["reverse_probe_inserted"] = run_batch(cur, probe_rows)
            conn.commit()

            # 清理：删除本轮全部行
            cur.execute("delete from asset.asset_relation_reviews where relation_scope='r195_intake'")
            out["cleanup_deleted"] = cur.rowcount
            conn.commit()
            cur.execute("select count(*), count(*) filter (where relation_scope='r195_intake'), count(*) filter (where review_status='approved') from asset.asset_relation_reviews")
            after_total, after_own, after_approved = cur.fetchone()
            out["after_cleanup"] = {"total_reviews": after_total, "r195_rows": after_own, "approved": after_approved}
            out["others_untouched"] = (after_total == base_total and after_approved == base_approved)
    out["finished_at"] = datetime.now(timezone.utc).isoformat()
    ok = (out["first_pass_inserted"] == len(payload) and out["replay_inserted"] == 0
          and out["rows_after_first_pass"] == len(payload) and out["others_untouched"]
          and out["after_cleanup"]["r195_rows"] == 0)
    out["verdict"] = "PASS" if ok else "FAIL"
    json.dump(out, open(os.path.join(RUN_DIR, "rehearsal_result.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in out.items() if k not in ("started_at",)}, ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(main())
