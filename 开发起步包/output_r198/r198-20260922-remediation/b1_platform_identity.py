# -*- coding: utf-8 -*-
"""B1 平台身份定向只读查询：
1) asset_systems / asset_data_sources 现行编码（核实 HIS vs HIS_SOURCE 映射）
2) 三个元数据缺口表在平台的实际列清单（区分漏采/错选/旧字段）
3) 本批 167 reviews 的 from/to system_code 分布（回读已证 source_code 全空）
PSQL read_only=on + statement_timeout=15s；不连业务源库，不写平台。"""
from pathlib import Path
import json
import shlex
import subprocess

OUT = Path(__file__).parent
SQL = r"""
SELECT json_build_object(
 'systems',(SELECT json_agg(row_to_json(t)) FROM (SELECT system_code,system_name_cn AS system_name,status FROM asset.asset_systems ORDER BY system_code) t),
 'sources',(SELECT json_agg(row_to_json(t)) FROM (SELECT source_code,system_code,source_name_cn AS source_name,db_type,host_masked AS host,enabled AS is_active FROM asset.asset_data_sources ORDER BY source_code) t),
 'gap_wait_bed',(SELECT json_agg(row_to_json(t)) FROM (SELECT schema_name,table_name,column_name,data_type FROM asset.asset_columns WHERE table_name='WAIT_BED_PATS_NEW' ORDER BY column_name) t),
 'gap_drug_catalog',(SELECT json_agg(row_to_json(t)) FROM (SELECT schema_name,table_name,column_name,data_type FROM asset.asset_columns WHERE table_name IN ('OFFICIAL_DRUG_CATALOG','OFFICIAL_DRUG_CATALOG_CLASS') ORDER BY table_name,column_name) t),
 'gap_tables_reg',(SELECT json_agg(row_to_json(t)) FROM (SELECT s.system_code,t.source_code,t.schema_name,t.table_name FROM asset.asset_tables t JOIN asset.asset_data_sources s ON s.source_code=t.source_code WHERE t.table_name IN ('WAIT_BED_PATS_NEW','OFFICIAL_DRUG_CATALOG','OFFICIAL_DRUG_CATALOG_CLASS') ORDER BY t.table_name) t)
)::text;
"""


def main():
    command = 'env PGOPTIONS=' + shlex.quote('-c default_transaction_read_only=on -c statement_timeout=15000') + ' /usr/local/pgsql/bin/psql -X -d data_asset -At -v ON_ERROR_STOP=1'
    proc = subprocess.run(
        ['ssh', '-i', r'C:\Users\Administrator\.ssh\id_ed25519_ai', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10',
         'root@10.10.8.83', 'su - postgres -c ' + shlex.quote(command)],
        input=SQL.encode('utf-8'), capture_output=True, timeout=60)
    if proc.returncode:
        raise SystemExit(proc.stderr.decode('utf-8')[-1200:])
    data = json.loads(proc.stdout.decode('utf-8').strip())
    (OUT / 'b1_platform_identity.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

    sys_map = {r['system_code']: r['system_name'] for r in data['systems']}
    his_like = {k: v for k, v in sys_map.items() if 'HIS' in k.upper() or 'ODS' in k.upper() or 'DATA' in k.upper()}
    print(json.dumps({
        'systems_total': len(data['systems']),
        'his_like_systems': his_like,
        'sources_his_like': [s for s in data['sources'] if 'his' in (s['source_code'] or '').lower() or 'ods' in (s['source_code'] or '').lower()],
        'gap_wait_bed_columns': len(data['gap_wait_bed'] or []),
        'gap_wait_bed_sample': (data['gap_wait_bed'] or [])[:8],
        'gap_drug_catalog_columns': len(data['gap_drug_catalog'] or []),
        'gap_drug_catalog_has': sorted({(r['table_name'], r['column_name']) for r in (data['gap_drug_catalog'] or []) if r['column_name'] in ('CONSTRAINED_LEVEL', 'CLASS_CODE')}),
        'gap_tables_reg': data['gap_tables_reg'],
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
