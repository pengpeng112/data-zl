"""129号：asset_relations 端点物理键回填。

背景：537 条关系中 73 条缺少物理端点字段（from/to 的 system/source/schema/table），
不会进入正式图层，导致概览图谱跨系统边为 0。本脚本按资产目录（asset_tables）
唯一匹配回填，规则保守：

1. 端点原始文本拆分变体：A.B.C → (A.B, C) 与 (B, C)；A.B → (A, B)；A → 仅表名
2. 仅当 (schema, table) 或 table 在目录中唯一命中 (system, source) 时回填，多义不猜
3. 首段是已知 system_code 时，先用它收敛匹配范围（如 DOCARE.xxx → 系统 DOCARE）
4. 只读业务源库红线不受影响：本脚本只写平台库 asset.asset_relations

用法：
    python backend/scripts/backfill_relation_endpoints.py --dry-run   # 只分析不写库
    python backend/scripts/backfill_relation_endpoints.py             # 执行回填
"""
import argparse
import os
from collections import defaultdict

import psycopg2


def build_index(cur):
    cur.execute(
        "SELECT system_code, source_code, schema_name, table_name "
        "FROM asset.asset_tables WHERE schema_name IS NOT NULL AND table_name IS NOT NULL"
    )
    by_st = defaultdict(set)
    by_t = defaultdict(set)
    systems = set()
    for sys_c, src_c, sch, tbl in cur.fetchall():
        systems.add(sys_c)
        rec = (sys_c, src_c, sch, tbl)
        by_st[(sch.lower(), tbl.lower())].add(rec)
        by_t[tbl.lower()].add(rec)
    return by_st, by_t, systems


def resolve_endpoint(raw, sys_c, src_c, sch, tbl, by_st, by_t, systems):
    """返回 (system, source, schema, table) 或 None（多义不猜）。已完整端点原样返回。"""
    if sys_c and src_c:
        return None
    parts = [p for p in (raw or "").split(".") if p]
    variants = []
    if len(parts) >= 3:
        variants.append((".".join(parts[:-1]), parts[-1]))  # A.B.C → schema=A.B（目录含点式 schema）
        variants.append((parts[-2], parts[-1]))
    elif len(parts) == 2:
        variants.append((parts[0], parts[1]))
    if sch and tbl:
        variants.append((sch, tbl))
    matches = set()
    for s_v, t_v in variants:
        matches |= by_st.get((s_v.lower(), t_v.lower()), set())
    if not matches:
        tname = parts[-1] if parts else tbl
        if tname:
            matches = by_t.get(tname.lower(), set())
    first = parts[0] if parts else None
    if first and first in systems:
        narrowed = {m for m in matches if m[0] == first}
        if narrowed:
            matches = narrowed
    uniq = {(m[0], m[1]) for m in matches}
    if len(uniq) != 1:
        return None
    sys2, src2 = next(iter(uniq))
    schs = {m[2] for m in matches if (m[0], m[1]) == (sys2, src2)}
    tbls = {m[3] for m in matches if (m[0], m[1]) == (sys2, src2)}
    return (
        sys2,
        src2,
        next(iter(schs)) if len(schs) == 1 else (sch or (parts[-2] if len(parts) >= 2 else None)),
        next(iter(tbls)) if len(tbls) == 1 else (tbl or (parts[-1] if parts else None)),
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="只分析不写库")
    args = parser.parse_args()

    dsn = os.environ["APP_DB_URL"].replace("postgresql+psycopg://", "postgresql://")
    conn = psycopg2.connect(dsn)
    cur = conn.cursor()
    by_st, by_t, systems = build_index(cur)

    cur.execute(
        "SELECT id, from_table, from_system_code, from_source_code, from_schema_name, from_table_name,"
        " to_table, to_system_code, to_source_code, to_schema_name, to_table_name"
        " FROM asset.asset_relations"
    )
    updates = []
    for row in cur.fetchall():
        (rid, f_raw, f_sys, f_src, f_sch, f_tbl, t_raw, t_sys, t_src, t_sch, t_tbl) = row
        f = resolve_endpoint(f_raw, f_sys, f_src, f_sch, f_tbl, by_st, by_t, systems)
        t = resolve_endpoint(t_raw, t_sys, t_src, t_sch, t_tbl, by_st, by_t, systems)
        if not f and not t:
            continue
        updates.append((
            (f[0], f[1], f[2], f[3]) if f else (f_sys, f_src, f_sch, f_tbl),
            (t[0], t[1], t[2], t[3]) if t else (t_sys, t_src, t_sch, t_tbl),
            rid,
        ))

    print(f"可回填关系: {len(updates)} 条")
    if args.dry_run:
        for (f4, t4, rid) in updates[:10]:
            print(f"  id={rid} from={f4} to={t4}")
        cur.close()
        conn.close()
        return

    for (f4, t4, rid) in updates:
        cur.execute(
            "UPDATE asset.asset_relations SET"
            " from_system_code=%s, from_source_code=%s, from_schema_name=%s, from_table_name=%s,"
            " to_system_code=%s, to_source_code=%s, to_schema_name=%s, to_table_name=%s,"
            " updated_at=now()"
            " WHERE id=%s",
            (*f4, *t4, rid),
        )
    conn.commit()
    # 回填后体检
    cur.execute(
        "SELECT COUNT(*) FROM asset.asset_relations "
        "WHERE from_system_code IS NULL OR to_system_code IS NULL"
    )
    remaining = cur.fetchone()[0]
    print(f"回填完成: {len(updates)} 条；仍缺 system 端点: {remaining} 条（多义不猜，保留人工治理）")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
