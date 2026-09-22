# -*- coding: utf-8 -*-
"""r198 B7-②预演：隔离库 data_asset_test 种子（生产形态）→ 执行 r198_prod_update.sql → 验证守卫/计数/幂等。
绝不连生产；种子数据来自 2026-09-22 生产只读回读。"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
import sqlalchemy  # noqa: E402
import sqlalchemy.orm  # noqa: E402
from sqlalchemy import text  # noqa: E402

OUT = ROOT / '开发起步包/output_r198/r198-20260922-remediation'
AUDIT = ROOT / 'review/adhoc/r197-audit-20260922'


def main():
    rb = json.loads((AUDIT / 'platform_readback.json').read_text(encoding='utf-8'))
    eng = sqlalchemy.create_engine(os.environ['APP_TEST_DB_URL'])
    with eng.begin() as c:
        assert c.execute(text('select current_database()')).scalar() == 'data_asset_test'
        # 清理种子痕迹（幂等重跑）
        c.execute(text("DELETE FROM asset.asset_relation_reviews WHERE relation_scope='r197_intake'"))
        c.execute(text("DELETE FROM asset.asset_govern_audit_logs WHERE entity_ref='r198-20260922-remediation'"))
        keys = [(d['schema_name'], d['table_name'], d['column_name'], d['code']) for d in rb['domains']]
        for sc, tb, col, code in keys:
            c.execute(text("DELETE FROM asset.asset_column_value_domain_evidences WHERE domain_id IN "
                           "(SELECT id FROM asset.asset_column_value_domains WHERE schema_name=:sc AND table_name=:tb AND column_name=:col AND code=:code)"),
                      {'sc': sc, 'tb': tb, 'col': col, 'code': code})
            c.execute(text("DELETE FROM asset.asset_column_value_domains WHERE schema_name=:sc AND table_name=:tb AND column_name=:col AND code=:code"),
                      {'sc': sc, 'tb': tb, 'col': col, 'code': code})
        c.execute(text("DELETE FROM asset.asset_column_value_domains WHERE schema_name='INPBILL' AND table_name='INP_BILL_DETAIL' AND column_name='ITEM_CLASS' AND code IN ('E','F','G')"))
        c.execute(text("DELETE FROM asset.asset_relation_recipes WHERE imported_from='r197_intake'"))
        # 种子 reviews（生产形态：HIS_SOURCE/draft/validation NULL）
        for rv in rb['reviews']:
            c.execute(text(
                "INSERT INTO asset.asset_relation_reviews (id,relation_scope,from_system_code,from_source_code,from_table,from_columns,"
                "to_system_code,to_source_code,to_table,to_columns,join_condition,validation_status,review_status,source_evidence) VALUES "
                "(:id,:sc,:fs,:fsrc,:ft,:fc,:ts,:tsrc,:tt,:tc,:jc,:vs,:rs,:ev)"),
                {'id': rv['id'], 'sc': 'r197_intake', 'fs': rv['from_system_code'], 'fsrc': rv['from_source_code'],
                 'ft': rv['from_table'], 'fc': rv['from_columns'], 'ts': rv['to_system_code'],
                 'tsrc': rv['to_source_code'], 'tt': rv['to_table'], 'tc': rv['to_columns'],
                 'jc': rv['join_condition'], 'vs': rv['validation_status'], 'rs': rv['review_status'],
                 'ev': rv['source_evidence']})
        # 种子 domains（生产形态：HIS_SOURCE/pending）
        for d in rb['domains']:
            c.execute(text(
                "INSERT INTO asset.asset_column_value_domains (system_code,source_code,schema_name,table_name,column_name,code,meaning,status,domain_kind,note,conflict_status) "
                "VALUES (:s,:src,:sc,:t,:col,:code,:m,:st,:k,:n,'none')"),
                {'s': d['system_code'], 'src': d['source_code'], 'sc': d['schema_name'], 't': d['table_name'],
                 'col': d['column_name'], 'code': d['code'], 'm': d['meaning'], 'st': d['status'],
                 'k': d['domain_kind'], 'n': d['note']})
        # 种子 recipes（draft）
        for r in rb['recipes']:
            c.execute(text(
                "INSERT INTO asset.asset_relation_recipes (recipe_id,status,is_active,source_system,primary_tables,joins,recipe_json,content_hash,imported_from) "
                "VALUES (:rid,:st,:act,'HIS',CAST(:pt AS jsonb),CAST(:j AS jsonb),CAST(:rj AS jsonb),:ch,'r197_intake')"),
                {'rid': r['recipe_id'], 'st': r['status'], 'act': r['is_active'],
                 'pt': json.dumps(r.get('primary_tables') or []), 'j': json.dumps(r.get('joins') or {}),
                 'rj': json.dumps(r.get('recipe_json') or {}), 'ch': r.get('content_hash') or ''})
        seeded = c.execute(text("SELECT count(*) FROM asset.asset_relation_reviews WHERE relation_scope='r197_intake'")).scalar()
    print('seeded reviews:', seeded)

    # 执行修订 SQL（含 BEGIN/COMMIT，脚本自带事务；去重双分号风险由 psql 兼容）
    sql = (OUT / 'r198_prod_update.sql').read_text(encoding='utf-8')
    with eng.begin() as c:
        c.execute(text(sql))
    # 验证
    checks = {}
    with eng.begin() as c:
        checks['reviews_his'] = c.execute(text("SELECT count(*) FROM asset.asset_relation_reviews WHERE relation_scope='r197_intake' AND from_system_code='HIS' AND from_source_code='his_source_10_10_10_15' AND to_system_code='HIS' AND to_source_code='his_source_10_10_10_15'")).scalar()
        checks['reviews_his_source_left'] = c.execute(text("SELECT count(*) FROM asset.asset_relation_reviews WHERE from_system_code='HIS_SOURCE' OR to_system_code='HIS_SOURCE'")).scalar()
        checks['notes_r198'] = c.execute(text("SELECT count(*) FROM asset.asset_relation_reviews WHERE review_note LIKE '%r198%'")).scalar()
        checks['probe_evidence'] = c.execute(text("SELECT count(*) FROM asset.asset_relation_reviews WHERE source_evidence LIKE '%r198_probe%'")).scalar()
        checks['downgrade_notes'] = c.execute(text("SELECT count(*) FROM asset.asset_relation_reviews WHERE source_evidence LIKE '%r198_validation_review%'")).scalar()
        checks['vd_his_source_left'] = c.execute(text("SELECT count(*) FROM asset.asset_column_value_domains WHERE system_code='HIS_SOURCE'")).scalar()
        checks['vd_efg'] = c.execute(text("SELECT count(*) FROM asset.asset_column_value_domains WHERE schema_name='INPBILL' AND table_name='INP_BILL_DETAIL' AND column_name='ITEM_CLASS' AND code IN ('E','F','G') AND status='pending'")).scalar()
        checks['vd_evidence'] = c.execute(text("SELECT count(*) FROM asset.asset_column_value_domain_evidences e JOIN asset.asset_column_value_domains d ON d.id=e.domain_id WHERE d.note LIKE '%r198%'")).scalar()
        checks['recipes_v2'] = c.execute(text("SELECT count(*) FROM asset.asset_relation_recipes WHERE recipe_json ? 'r198_payload_v2'")).scalar()
        checks['recipes_draft_kept'] = c.execute(text("SELECT count(*) FROM asset.asset_relation_recipes WHERE imported_from='r197_intake' AND status='draft'")).scalar()
        checks['audit'] = c.execute(text("SELECT count(*) FROM asset.asset_govern_audit_logs WHERE entity_ref='r198-20260922-remediation'")).scalar()
    # 幂等重放
    with eng.begin() as c:
        c.execute(text(sql))
    with eng.begin() as c:
        checks['idempotent_evidence'] = c.execute(text("SELECT count(*) FROM asset.asset_column_value_domain_evidences e JOIN asset.asset_column_value_domains d ON d.id=e.domain_id WHERE d.note LIKE '%r198%'")).scalar()
    print(json.dumps(checks, ensure_ascii=False, indent=1))
    (OUT / 'b7_prod_rehearsal.json').write_text(json.dumps(checks, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
