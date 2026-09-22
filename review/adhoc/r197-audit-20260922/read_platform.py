"""Read-only platform asset audit. Never queries any business source."""
from pathlib import Path
import json
import subprocess
import shlex

OUT=Path(__file__).parent
SQL=r"""
SELECT json_build_object(
 'reviews',(SELECT json_agg(row_to_json(t)) FROM (SELECT id,from_system_code,from_source_code,from_table,from_columns,to_system_code,to_source_code,to_table,to_columns,join_condition,validation_status,review_status,source_evidence FROM asset.asset_relation_reviews WHERE relation_scope='r197_intake' ORDER BY id) t),
 'recipe_columns',(SELECT json_agg(column_name) FROM information_schema.columns WHERE table_schema='asset' AND table_name='asset_relation_recipes'),
 'recipes',(SELECT json_agg(row_to_json(t)) FROM (SELECT recipe_id,status,is_active,source_system,primary_tables,joins,recipe_json,content_hash FROM asset.asset_relation_recipes WHERE imported_from='r197_intake' ORDER BY recipe_id) t),
 'domains',(SELECT json_agg(row_to_json(t)) FROM (SELECT id,system_code,source_code,schema_name,table_name,column_name,code,meaning,status,domain_kind,note,current_version_id,(SELECT count(*) FROM asset.asset_column_value_domain_evidences e WHERE e.domain_id=d.id) evidence_count FROM asset.asset_column_value_domains d WHERE note LIKE '%197%' OR (source_code='his_source_10_10_10_15' AND ((schema_name='COMM' AND table_name='OPERATION_DICT' AND column_name='OPERATION_SCALE' AND code='一 ') OR (schema_name='INPBILL' AND table_name='INP_BILL_DETAIL' AND column_name='OPER_CODE' AND code='多义键'))) ORDER BY id) t)
)::text;
"""

def main():
    command='env PGOPTIONS='+shlex.quote('-c default_transaction_read_only=on -c statement_timeout=15000')+' /usr/local/pgsql/bin/psql -X -d data_asset -At -v ON_ERROR_STOP=1'
    proc=subprocess.run(['ssh','-i',r'C:\Users\Administrator\.ssh\id_ed25519_ai','-o','BatchMode=yes','-o','ConnectTimeout=10','root@10.10.8.83','su - postgres -c '+shlex.quote(command)],input=SQL.encode('utf-8'),capture_output=True,timeout=25)
    if proc.returncode:
        raise SystemExit(proc.stderr.decode('utf-8')[-600:])
    data=json.loads(proc.stdout.decode('utf-8').strip())
    (OUT/'platform_readback.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    reviews=data['reviews'] or [];recipes=data['recipes'] or [];domains=data['domains'] or []
    print(json.dumps({'reviews':len(reviews),'draft':sum(r['review_status']=='draft' for r in reviews),'missing_source':sum(not r['from_source_code'] or not r['to_source_code'] for r in reviews),'validation_states':sorted(set(r['validation_status'] for r in reviews)),'recipes':len(recipes),'empty_recipe_joins':sum(not r['joins'] for r in recipes),'domains_note197':len(domains),'domains_no_evidence':sum(not r['evidence_count'] for r in domains),'domain_statuses':sorted(set(r['status'] for r in domains))},ensure_ascii=False))

if __name__=='__main__':main()
