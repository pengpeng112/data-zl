# -*- coding: utf-8 -*-
"""L4 主清单 live 重拉 v2（只读，列名自适应）。零写入。"""
import json
from datetime import datetime, timezone

from sqlalchemy import text
from app.core.db import SessionLocal


def cols(s, t):
    return [r[0] for r in s.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema='asset' AND table_name=:t ORDER BY ordinal_position"), {"t": t}).fetchall()]


def norm(v):
    if v is None:
        return ""
    if isinstance(v, (bytes, memoryview)):
        return bytes(v).hex()[:100]
    return str(v)[:300]


out = {"pulled_at": datetime.now(timezone.utc).isoformat()}
with SessionLocal() as s:
    rc = cols(s, "asset_relation_reviews")
    print("[review_cols]", rc, flush=True)
    st_col = next((c for c in ("status", "review_status", "state") if c in rc), None)
    src_col = next((c for c in ("source_code", "source", "source_kind", "origin") if c in rc), None)
    if st_col:
        q = f"SELECT {st_col}, count(*) FROM asset.asset_relation_reviews GROUP BY 1 ORDER BY 2 DESC"
        if src_col:
            q = f"SELECT {st_col}, {src_col}, count(*) FROM asset.asset_relation_reviews GROUP BY 1,2 ORDER BY 3 DESC"
        for r in s.execute(text(q)).fetchall():
            print("[review_dist]", " | ".join(norm(x) for x in r), flush=True)

    # draft 明细（自适应关键列）
    pick = [c for c in ("id", "from_table", "to_table", "from_columns", "to_columns", "relation_type",
                        "confidence", "source_code", "source_kind", "created_at") if c in rc]
    if st_col:
        drafts = s.execute(text(
            f"SELECT {', '.join(pick)} FROM asset.asset_relation_reviews "
            f"WHERE {st_col}='draft' ORDER BY id")).fetchall()
    else:
        drafts = []
    print("[draft_total]", len(drafts), flush=True)
    keys = pick
    out["drafts"] = [{k: norm(v) for k, v in zip(keys, row)} for row in drafts]

    for t, label in (("asset_relation_recipes", "recipe"), ("asset_value_domains", "vd")):
        c2 = cols(s, t)
        st2 = next((c for c in ("status", "review_status", "state") if c in c2), None)
        if not st2:
            print(f"[{label}_dist] no_status_col {c2[:12]}", flush=True)
            continue
        for r in s.execute(text(f"SELECT {st2}, count(*) FROM asset.{t} GROUP BY 1 ORDER BY 2 DESC")).fetchall():
            print(f"[{label}_dist]", norm(r[0]), r[1], flush=True)
        pk = [c for c in ("id", "name", "table_name", "column_name", "system_code", "created_at") if c in c2]
        rows = s.execute(text(
            f"SELECT {', '.join(pk)} FROM asset.{t} WHERE {st2} IN ('draft','pending') ORDER BY 1")).fetchall()
        out[f"{label}_pending"] = [{k: norm(v) for k, v in zip(pk, row)} for row in rows]
        print(f"[{label}_pending_total]", len(rows), flush=True)

    n = s.execute(text("SELECT count(*) FROM asset.asset_relations")).scalar()
    out["formal_relations_total"] = n
    print("[formal_relations]", n, flush=True)

print("[JSON_BEGIN]")
print(json.dumps(out, ensure_ascii=False, indent=1))
print("[JSON_END]")
