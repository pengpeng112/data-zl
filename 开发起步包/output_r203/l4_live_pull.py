# -*- coding: utf-8 -*-
"""L4 主清单 live 重拉（只读）：asset_relation_reviews / recipes / value_domains 当前分布与待审清单。
产出脱敏 JSON 供治理分批用。零写入。"""
import json
from datetime import datetime, timezone

from sqlalchemy import text
from app.core.db import SessionLocal


def norm(v):
    if v is None:
        return ""
    if isinstance(v, (bytes, memoryview)):
        return bytes(v).hex()[:100]
    return str(v)[:300]


out = {"pulled_at": datetime.now(timezone.utc).isoformat(), "server": "live"}

with SessionLocal() as s:
    # 1) reviews 状态×来源分布
    for r in s.execute(text(
            "SELECT status, source_code, count(*) FROM asset.asset_relation_reviews "
            "GROUP BY 1,2 ORDER BY 3 DESC")).fetchall():
        print(f"[review_dist] {r[0]} | {norm(r[1])[:40]} | {r[2]}", flush=True)

    # 2) draft 全量（自然键+证据字段）
    drafts = s.execute(text(
        "SELECT id, from_table, to_table, from_columns, to_columns, relation_type, confidence, "
        "status, source_code, source_kind, created_at FROM asset.asset_relation_reviews "
        "WHERE status='draft' ORDER BY id")).fetchall()
    print(f"[draft_total] {len(drafts)}", flush=True)
    out["drafts"] = [
        {"id": r[0], "from": norm(r[1])[:120], "to": norm(r[2])[:120],
         "from_cols": norm(r[3])[:80], "to_cols": norm(r[4])[:80],
         "type": norm(r[5]), "confidence": norm(r[6]), "source": norm(r[7])[:60],
         "kind": norm(r[8])[:40], "created": norm(r[9])[:19]}
        for r in drafts
    ]

    # 3) recipes 状态分布 + draft 明细
    for r in s.execute(text(
            "SELECT status, count(*) FROM asset.asset_relation_recipes GROUP BY 1 ORDER BY 2 DESC")).fetchall():
        print(f"[recipe_dist] {r[0]} | {r[1]}", flush=True)
    recipes = s.execute(text(
        "SELECT id, name, status, created_at FROM asset.asset_relation_recipes "
        "WHERE status IN ('draft','pending') ORDER BY id")).fetchall()
    out["recipes_pending"] = [
        {"id": r[0], "name": norm(r[1])[:100], "status": r[2], "created": norm(r[3])[:19]} for r in recipes
    ]

    # 4) 值域 pending
    for r in s.execute(text(
            "SELECT status, count(*) FROM asset.asset_value_domains GROUP BY 1 ORDER BY 2 DESC")).fetchall():
        print(f"[vd_dist] {r[0]} | {r[1]}", flush=True)
    vds = s.execute(text(
        "SELECT id, table_name, column_name, status, system_code FROM asset.asset_value_domains "
        "WHERE status='pending' ORDER BY id")).fetchall()
    out["vd_pending_count"] = len(vds)
    out["vd_pending_sample"] = [
        {"id": r[0], "tbl": norm(r[1])[:100], "col": norm(r[2])[:60], "sys": norm(r[4])[:30]}
        for r in vds[:10]
    ]

    # 5) 正式关系总量（对账基线）
    n = s.execute(text("SELECT count(*) FROM asset.asset_relations")).scalar()
    out["formal_relations_total"] = n
    print(f"[formal_relations] {n}", flush=True)

print(json.dumps(out, ensure_ascii=False, indent=1), flush=True)
print("[done]", flush=True)
