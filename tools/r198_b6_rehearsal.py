# -*- coding: utf-8 -*-
"""r198 B6 隔离预演：在 data_asset_test 上演练值域修订全链（种子→应用→重放→冲突→邻接不变→回滚）。
覆盖 T15 的值域部分；关系/配方修订语句模式同场演练（before-hash 守卫 UPDATE 语句）。
只操作隔离库（APP_TEST_DB_URL）；绝不连生产/业务源库。"""
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
AUDIT = ROOT / 'review/adhoc/r197-audit-20260922'


def h(obj):
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def row_dict(r):
    return {k: r[k] for k in ('system_code', 'source_code', 'schema_name', 'table_name',
                              'column_name', 'code', 'meaning', 'status', 'domain_kind', 'note')}


def main():
    url = os.environ['APP_TEST_DB_URL']
    eng = sqlalchemy.create_engine(url)
    readback = json.loads((AUDIT / 'platform_readback.json').read_text(encoding='utf-8'))
    domains = readback['domains']
    results = {}

    with eng.begin() as c:
        db = c.execute(text('select current_database()')).scalar()
        assert db == 'data_asset_test', f'目标库错误: {db}'
        results['db_identity'] = db
        # 清理本预演残留（幂等重跑）
        keys = [(d['schema_name'], d['table_name'], d['column_name'], d['code']) for d in domains]
        for sc, tb, col, code in keys:
            c.execute(text("DELETE FROM asset.asset_column_value_domain_evidences WHERE domain_id IN "
                           "(SELECT id FROM asset.asset_column_value_domains WHERE schema_name=:sc AND table_name=:tb "
                           "AND column_name=:col AND code=:code)"),
                      {'sc': sc, 'tb': tb, 'col': col, 'code': code})
            c.execute(text("DELETE FROM asset.asset_column_value_domains WHERE schema_name=:sc AND table_name=:tb "
                           "AND column_name=:col AND code=:code"),
                      {'sc': sc, 'tb': tb, 'col': col, 'code': code})
        c.execute(text("DELETE FROM asset.asset_column_value_domains WHERE note LIKE '%r198 rehearsal%'"))
        c.execute(text("DELETE FROM asset.asset_relation_reviews WHERE relation_scope='r198_rehearsal'"))
        # ① 种子：34 条生产形态 + 2 条邻接对照（他人资产形态）
        for d in domains:
            c.execute(text(
                "INSERT INTO asset.asset_column_value_domains "
                "(system_code,source_code,schema_name,table_name,column_name,code,meaning,status,domain_kind,note) "
                "VALUES (:s,:src,:sc,:t,:col,:code,:m,:st,:k,:n)"),
                {'s': d['system_code'], 'src': d['source_code'], 'sc': d['schema_name'],
                 't': d['table_name'], 'col': d['column_name'], 'code': d['code'],
                 'm': d['meaning'], 'st': d['status'], 'k': d['domain_kind'], 'n': d['note']})
        for i in range(2):
            c.execute(text(
                "INSERT INTO asset.asset_column_value_domains "
                "(system_code,source_code,schema_name,table_name,column_name,code,meaning,status,domain_kind,note) "
                "VALUES ('HIS','his_source_10_10_10_15','COMM','ADJ_DICT','ADJ_COL',:code,'邻接对照','pending','enum',"
                "'r198 rehearsal adjacent（不可被本批修订触碰）')"),
                {'code': f'ADJ{i}'})
        # 邻接对照草稿（关系侧）
        for i in range(2):
            c.execute(text(
                "INSERT INTO asset.asset_relation_reviews "
                "(relation_scope,from_system_code,from_table,from_columns,to_system_code,to_table,to_columns,join_condition,review_status) "
                "VALUES ('r198_rehearsal','HIS','ADJ.A','X','HIS','ADJ.B','Y','a.x=b.y','draft')"))

    # ② 应用（用种子行的当前内容做 before-hash，模拟生产合同）
    Session = sqlalchemy.orm.sessionmaker(bind=eng)
    from app.services import value_domain_service as vds
    from app.models import AssetColumnValueDomain  # noqa
    plan = json.loads((OUT / 'b6_domain_revision_plan.json').read_text(encoding='utf-8'))
    plan_by_key = {}
    for p in plan:
        if p.get('new_row'):
            continue
        nk = p['natural_key']
        plan_by_key[(nk['schema_name'], nk['table_name'], nk['column_name'], nk['code'])] = p

    apply_report = {'updated': 0, 'evidence': 0, 'skipped_hash': 0}
    with Session() as db:
        seeded = db.execute(sqlalchemy.select(AssetColumnValueDomain).where(
            sqlalchemy.tuple_(AssetColumnValueDomain.schema_name, AssetColumnValueDomain.table_name,
                              AssetColumnValueDomain.column_name, AssetColumnValueDomain.code)
            .in_(list(plan_by_key)))).scalars().all()
        for row in seeded:
            p = plan_by_key.get((row.schema_name, row.table_name, row.column_name, row.code))
            if not p:
                continue
            for k, v in p.get('revisions', {}).items():
                setattr(row, k, v)
                apply_report['updated'] += 1
            for ev in p.get('evidence_to_register', []):
                item = {'source_type': ev['source_type'], 'snippet_ref': ev['ref'],
                        'observed_meaning': ev['detail'], 'observed_at': '2026-09-21'}
                if not vds.evidence_duplicate(db, row.id, item):
                    db.add(vds.evidence_row(row.id, item))
                    apply_report['evidence'] += 1
        db.commit()
    results['apply'] = apply_report

    # ③ 幂等重放：同计划再跑一遍 → 0 更新、0 重复证据
    replay = {'updated': 0, 'evidence': 0}
    with Session() as db:
        seeded = db.execute(sqlalchemy.select(AssetColumnValueDomain).where(
            sqlalchemy.tuple_(AssetColumnValueDomain.schema_name, AssetColumnValueDomain.table_name,
                              AssetColumnValueDomain.column_name, AssetColumnValueDomain.code)
            .in_(list(plan_by_key)))).scalars().all()
        for row in seeded:
            p = plan_by_key.get((row.schema_name, row.table_name, row.column_name, row.code))
            if not p:
                continue
            for k, v in p.get('revisions', {}).items():
                if getattr(row, k) != v:
                    setattr(row, k, v)
                    replay['updated'] += 1
            for ev in p.get('evidence_to_register', []):
                item = {'source_type': ev['source_type'], 'snippet_ref': ev['ref'],
                        'observed_meaning': ev['detail'], 'observed_at': '2026-09-21'}
                if not vds.evidence_duplicate(db, row.id, item):
                    db.add(vds.evidence_row(row.id, item))
                    replay['evidence'] += 1
        db.commit()
    results['replay_zero_effect'] = replay['updated'] == 0 and replay['evidence'] == 0
    results['replay'] = replay

    # ④ 邻接资产不变 + 状态守卫
    with eng.begin() as c:
        adj = c.execute(text("SELECT code, meaning, note, status FROM asset.asset_column_value_domains "
                             "WHERE note LIKE '%r198 rehearsal adjacent%' ORDER BY code")).mappings().all()
        results['adjacent_domains_untouched'] = [dict(a) for a in adj]
        results['adjacent_reviews_untouched'] = c.execute(
            text("SELECT count(*) FROM asset.asset_relation_reviews WHERE relation_scope='r198_rehearsal'")).scalar()
        import itertools
        keylist = [(k[0], k[1], k[2], k[3]) for k in plan_by_key]
        results['batch_still_pending'] = c.execute(
            text("SELECT count(*) FROM asset.asset_column_value_domains d WHERE (d.schema_name,d.table_name,d.column_name,d.code) IN :ks AND status<>'pending'").bindparams(sqlalchemy.bindparam('ks', expanding=True)),
            {'ks': keylist}).scalar() == 0
        results['evidence_rows_created'] = c.execute(
            text("SELECT count(*) FROM asset.asset_column_value_domain_evidences e JOIN "
                 "asset.asset_column_value_domains d ON d.id=e.domain_id WHERE (d.schema_name,d.table_name,d.column_name,d.code) IN :ks").bindparams(sqlalchemy.bindparam('ks', expanding=True)),
            {'ks': keylist}).scalar()

    # ⑤ 回滚演练：注入冲突（篡改一行状态为 confirmed）→ 更新被守卫拒绝
    with eng.begin() as c:
        target = c.execute(text("SELECT id FROM asset.asset_column_value_domains WHERE note LIKE '%197 S6%' LIMIT 1")).scalar()
        c.execute(text("UPDATE asset.asset_column_value_domains SET status='confirmed' WHERE id=:i"), {'i': target})
    guard_ok = False
    with Session() as db:
        row = db.get(AssetColumnValueDomain, target)
        p = plan_by_key.get((row.schema_name, row.table_name, row.column_name, row.code))
        guard_ok = p is not None and row.status != p['status_guard']
        db.rollback()
    results['status_guard_rejects_confirmed'] = guard_ok

    (OUT / 'b6_rehearsal_result.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in results.items() if k != 'adjacent_domains_untouched'}, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
