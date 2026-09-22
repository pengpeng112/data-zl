# -*- coding: utf-8 -*-
"""B3 平台正式/草稿关系只读快照（查重底座）。
拉取 asset_relations（内联 from_/to_ 身份列）+ 全部 reviews 草稿。
PSQL read_only=on + statement_timeout=15s；不连业务源库，不写平台。"""
from pathlib import Path
import json
import shlex
import subprocess

OUT = Path(__file__).parent
SQL = r"""
SELECT json_build_object(
 'relations',(SELECT json_agg(row_to_json(t)) FROM (SELECT id,rel_id,domain,
    from_system_code,from_source_code,from_schema_name,from_table_name,from_columns,
    to_system_code,to_source_code,to_schema_name,to_table_name,to_columns,
    join_condition,cardinality,confidence,validation_status,relation_layer,relation_business_key
   FROM asset.asset_relations ORDER BY id) t),
 'reviews_all',(SELECT json_agg(row_to_json(t)) FROM (SELECT id,relation_scope,from_system_code,from_table,from_columns,to_system_code,to_table,to_columns,join_condition,review_status FROM asset.asset_relation_reviews ORDER BY id) t)
)::text;
"""


def main():
    command = 'env PGOPTIONS=' + shlex.quote('-c default_transaction_read_only=on -c statement_timeout=15000') + ' /usr/local/pgsql/bin/psql -X -d data_asset -At -v ON_ERROR_STOP=1'
    proc = subprocess.run(
        ['ssh', '-i', r'C:\Users\Administrator\.ssh\id_ed25519_ai', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10',
         'root@10.10.8.83', 'su - postgres -c ' + shlex.quote(command)],
        input=SQL.encode('utf-8'), capture_output=True, timeout=120)
    if proc.returncode:
        raise SystemExit(proc.stderr.decode('utf-8')[-1200:])
    data = json.loads(proc.stdout.decode('utf-8').strip())
    (OUT / 'b3_platform_relations.json').write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')
    rels = data['relations'] or []
    print(json.dumps({
        'relations_total': len(rels),
        'with_full_identity': sum(1 for r in rels if r.get('from_source_code') and r.get('to_source_code')),
        'layer_set': sorted({str(r.get('relation_layer')) for r in rels}),
        'reviews_total': len(data['reviews_all'] or []),
        'reviews_draft': sum(1 for r in (data['reviews_all'] or []) if r['review_status'] == 'draft'),
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
