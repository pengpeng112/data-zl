# -*- coding: utf-8 -*-
"""B0 平台现状重拉（只读）：核对 167 reviews/13 recipes/34 值域是否仍为审计基线状态。
PSQL 会话级 read_only=on，statement_timeout=15s；不连业务源库，不写平台。"""
from pathlib import Path
import json
import shlex
import subprocess

OUT = Path(__file__).parent
SQL = r"""
SELECT json_build_object(
 'reviews',(SELECT json_agg(row_to_json(t)) FROM (SELECT id,review_status,validation_status,from_source_code,to_source_code FROM asset.asset_relation_reviews WHERE relation_scope='r197_intake' ORDER BY id) t),
 'recipes',(SELECT json_agg(row_to_json(t)) FROM (SELECT recipe_id,status,is_active FROM asset.asset_relation_recipes WHERE imported_from='r197_intake' ORDER BY recipe_id) t),
 'domains',(SELECT json_agg(row_to_json(t)) FROM (SELECT id,code,status,current_version_id,(SELECT count(*) FROM asset.asset_column_value_domain_evidences e WHERE e.domain_id=d.id) evidence_count FROM asset.asset_column_value_domains d WHERE note LIKE '%197%' OR (source_code='his_source_10_10_10_15' AND ((schema_name='COMM' AND table_name='OPERATION_DICT' AND column_name='OPERATION_SCALE' AND code='一 ') OR (schema_name='INPBILL' AND table_name='INP_BILL_DETAIL' AND column_name='OPER_CODE' AND code='多义键'))) ORDER BY id) t),
 'total_reviews',(SELECT count(*) FROM asset.asset_relation_reviews),
 'total_formal',(SELECT count(*) FROM asset.asset_relations)
)::text;
"""


def main():
    command = 'env PGOPTIONS=' + shlex.quote('-c default_transaction_read_only=on -c statement_timeout=15000') + ' /usr/local/pgsql/bin/psql -X -d data_asset -At -v ON_ERROR_STOP=1'
    proc = subprocess.run(
        ['ssh', '-i', r'C:\Users\Administrator\.ssh\id_ed25519_ai', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10',
         'root@10.10.8.83', 'su - postgres -c ' + shlex.quote(command)],
        input=SQL.encode('utf-8'), capture_output=True, timeout=40)
    if proc.returncode:
        raise SystemExit(proc.stderr.decode('utf-8')[-800:])
    cur = json.loads(proc.stdout.decode('utf-8').strip())
    (OUT / 'b0_platform_current.json').write_text(json.dumps(cur, ensure_ascii=False, indent=2), encoding='utf-8')

    baseline = json.loads((OUT / 'b0_baseline.json').read_text(encoding='utf-8'))
    bl = baseline['platform_readback_20260922']
    rev, rec, dom = cur['reviews'], cur['recipes'], cur['domains']
    verdict = {
        'pulled_at': '2026-09-22 (B0)',
        'reviews': {
            'count': len(rev), 'all_draft': all(r['review_status'] == 'draft' for r in rev),
            'all_missing_both_source': all(not r['from_source_code'] or not r['to_source_code'] for r in rev),
            'non_null_validation': sorted({r['validation_status'] for r in rev if r['validation_status']}),
            'ids_match_baseline': [r['id'] for r in rev] == bl['reviews']['ids'],
        },
        'recipes': {
            'count': len(rec),
            'status_set': sorted({r['status'] for r in rec}),
            'any_active': any(r['is_active'] for r in rec),
            'ids_match_baseline': [r['recipe_id'] for r in rec] == [x['recipe_id'] for x in bl['recipes']],
        },
        'domains': {
            'count': len(dom),
            'status_set': sorted({r['status'] for r in dom}),
            'no_evidence': all(r['evidence_count'] == 0 for r in dom),
            'ids_match_baseline': [r['id'] for r in dom] == [x['id'] for x in bl['domains']],
        },
        'platform_totals': {'total_reviews': cur['total_reviews'], 'total_formal': cur['total_formal']},
    }
    verdict['baseline_unchanged'] = (
        verdict['reviews']['all_draft'] and verdict['reviews']['all_missing_both_source']
        and not verdict['reviews']['non_null_validation']
        and verdict['reviews']['ids_match_baseline']
        and verdict['recipes']['ids_match_baseline'] and not verdict['recipes']['any_active']
        and verdict['domains']['ids_match_baseline'] and verdict['domains']['no_evidence'])
    (OUT / 'b0_platform_verdict.json').write_text(json.dumps(verdict, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(verdict, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
