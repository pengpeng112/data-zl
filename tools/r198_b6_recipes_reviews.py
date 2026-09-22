# -*- coding: utf-8 -*-
"""r198 B6 补充：①167 草稿 UPDATE 语句模式的隔离预演（before-hash 守卫/仅本批/邻接不变）；
②13 配方 payload v2 数据重建（合法 qualified tables + joins 数组或知识型标记）。
只读 197 工件与 B3 结果；隔离库仅 data_asset_test。"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / 'backend'
sys.path.insert(0, str(BACKEND))
import sqlalchemy  # noqa: E402
import sqlalchemy.orm  # noqa: E402
from sqlalchemy import text  # noqa: E402

OUT = ROOT / '开发起步包/output_r198/r198-20260922-remediation'
RUN197 = ROOT / '开发起步包/output_r197/r197-20260921-s1'


def h(s):
    return hashlib.sha256(s.encode('utf-8')).hexdigest()


def rehearsal_reviews():
    url = os.environ['APP_TEST_DB_URL']
    eng = sqlalchemy.create_engine(url)
    res = {}
    with eng.begin() as c:
        assert c.execute(text('select current_database()')).scalar() == 'data_asset_test'
        c.execute(text("DELETE FROM asset.asset_relation_reviews WHERE relation_scope LIKE 'r198_rehearsal%'"))
        for i in range(3):
            c.execute(text(
                "INSERT INTO asset.asset_relation_reviews (relation_scope,from_system_code,from_table,from_columns,"
                "to_system_code,to_table,to_columns,join_condition,review_status,source_evidence) VALUES "
                "('r198_rehearsal_batch','HIS_SOURCE','INPBILL.INP_BILL_DETAIL','PATIENT_ID','HIS_SOURCE',"
                "'MEDREC.PAT_MASTER_INDEX','PATIENT_ID','d.patient_id=p.patient_id','draft',:ev)"),
                {'ev': json.dumps({'run_id': 'r198_rehearsal', 'batch': i}, ensure_ascii=False)})
        c.execute(text(
            "INSERT INTO asset.asset_relation_reviews (relation_scope,from_system_code,from_table,from_columns,"
            "to_system_code,to_table,to_columns,join_condition,review_status,source_evidence) VALUES "
            "('r198_rehearsal_adjacent','HIS','ADJ.A','X','HIS','ADJ.B','Y','a.x=b.y','draft','{}')"))
        ids = [r[0] for r in c.execute(text(
            "SELECT id FROM asset.asset_relation_reviews WHERE relation_scope='r198_rehearsal_batch' ORDER BY id"))]
        guards = {i: h(c.execute(text('select source_evidence from asset.asset_relation_reviews where id=:i'),
                                {'i': i}).scalar()) for i in ids}
    # 守卫 UPDATE：按 id+before-hash 更新 system/source，仅本批 scope
    updated, rejected = 0, 0
    with eng.begin() as c:
        for i, g in guards.items():
            cur = h(c.execute(text('select source_evidence from asset.asset_relation_reviews where id=:i'),
                              {'i': i}).scalar())
            if cur != g:
                rejected += 1
                continue
            c.execute(text("UPDATE asset.asset_relation_reviews SET from_system_code='HIS', "
                           "from_source_code='his_source_10_10_10_15', to_system_code='HIS', "
                           "to_source_code='his_source_10_10_10_15' WHERE id=:i AND relation_scope='r198_rehearsal_batch'"),
                      {'i': i})
            updated += 1
        adj = c.execute(text("SELECT count(*) FROM asset.asset_relation_reviews WHERE relation_scope='r198_rehearsal_adjacent' "
                             "AND from_system_code='HIS' AND from_source_code IS NULL")).scalar()
    res.update({'guard_updated': updated, 'guard_rejected': rejected, 'adjacent_review_untouched': adj == 1})
    (OUT / 'b6_reviews_rehearsal.json').write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding='utf-8')
    print('reviews rehearsal:', json.dumps(res, ensure_ascii=False))


def rebuild_recipes():
    rels = {json.loads(l)['relation_id']: json.loads(l) for l in (RUN197 / 'relations.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()}
    recipes = [json.loads(l) for l in (RUN197 / 'recipes.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()]
    inv = json.loads((OUT / 'asset_inventory.json').read_text(encoding='utf-8'))
    registry = inv['endpoint_registry']

    def qualified(bare_table):
        cands = registry.get(bare_table, {}).get('candidates', [])
        his = [c for c in cands if c['system'] == 'HIS']
        if len(his) == 1:
            return f"{his[0]['schema']}.{bare_table}"
        return None  # 歧义：保持裸名并标记

    out = []
    for r in recipes:
        rid = r['recipe_id']
        joins = []
        unresolved_refs = []
        complex_payload = bool(r.get('dedup_strategy') and ('三列' in r['dedup_strategy'] or '复合' in r['dedup_strategy'])) \
            or bool(r.get('time_fields')) or bool(r.get('outpatient_subquery')) or bool(r.get('pre_aggregate'))
        for fid in r.get('join_family_ids', []):
            fam = rels.get(fid)
            if not fam:
                unresolved_refs.append(fid)
                continue
            ea, eb = fam['endpoints']['a'], fam['endpoints']['b']
            qa, qb = qualified(ea['table']), qualified(eb['table'])
            cols_a, cols_b = ea['columns'], eb['columns']
            on = ' AND '.join(f"a.{x}=b.{y}" for x, y in zip(cols_a, cols_b))
            joins.append({'from': qa or ea['table'], 'to': qb or eb['table'],
                          'join_type': fam.get('join_type') or 'inner', 'on': on,
                          'from_qualified': bool(qa), 'to_qualified': bool(qb),
                          'ref_family': fid})
        tables = []
        for t in r.get('primary_tables', []):
            q = qualified(t)
            tables.append({'table': t, 'qualified': q, 'resolved': bool(q)})
        if '/' in ' '.join(r.get('primary_tables', [])):
            illegal_tables = [t for t in r['primary_tables'] if '/' in t]
        else:
            illegal_tables = []
        knowledge_only = bool(illegal_tables) or bool(unresolved_refs)
        entry = {
            'recipe_id': rid, 'name': r['name'], 'domain': r.get('domain'),
            'primary_tables': tables,
            'joins': joins,
            'readiness': ('not_executable' if (knowledge_only or complex_payload) else 'ready'),
            'not_ready_reasons': ([f'illegal_table:{t}' for t in illegal_tables] +
                                  [f'unresolved_family_ref:{f}' for f in unresolved_refs] +
                                  (['complex_payload:含先聚合/时间选价/防放大口径，现有生成器无法保真平铺'] if complex_payload else [])),
            'knowledge_payload': {'dedup_strategy': r.get('dedup_strategy'), 'time_fields': r.get('time_fields'),
                                  'original_caliber': r.get('original_caliber'),
                                  'suggested_caliber': r.get('suggested_caliber'),
                                  'main_fact_grain': r.get('main_fact_grain'),
                                  'risks': r.get('risks')},
            'original_recipe_id': rid,
        }
        out.append(entry)
    summary = {'total': len(out), 'ready': sum(1 for e in out if e['readiness'] == 'ready'),
               'not_executable': sum(1 for e in out if e['readiness'] != 'ready'),
               'illegal_tables_fixed': sum(1 for e in out if any('illegal' in x for x in e['not_ready_reasons']))}
    (OUT / 'recipe_payload_v2.json').write_text(
        json.dumps({'generated': '2026-09-22', 'summary': summary, 'recipes': out}, ensure_ascii=False, indent=1),
        encoding='utf-8')
    print('recipe v2:', json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    rebuild_recipes()
    rehearsal_reviews()
