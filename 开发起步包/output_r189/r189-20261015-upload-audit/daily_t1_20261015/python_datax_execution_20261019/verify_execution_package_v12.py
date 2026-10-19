"""Independent planning-delivery checks, never engine or database tests."""

from pathlib import Path
import hashlib
import json
import re
import zipfile
from openpyxl import load_workbook

HERE = Path(__file__).resolve().parent


def read(name):
    return json.loads((HERE/name).read_text(encoding='utf-8'))


def main():
    old=HERE/'_history/v1.1'
    prior=lambda name: json.loads((old/name).read_text(encoding='utf-8'))
    contract=read('长任务执行契约.json');seeds=read('77项任务候选种子.json')['items']
    cases=read('验收场景矩阵.json')['cases'];old_cases=prior('验收场景矩阵.json')['cases']
    config=read('告警接入配置候选.json');old_config=prior('告警接入配置候选.json')
    checks={}
    checks['version_and_ten_tasks']=contract['version']=='1.2' and len(contract['tasks'])==10
    checks['all_original_88_expectations_preserved']=all((a['id'],a['category'],a['trigger'],a['expected'])==(b['id'],b['category'],b['trigger'],b['expected']) for a,b in zip(cases,old_cases)) and len(old_cases)==88
    checks['112_not_run_no_engine_claim']=len(cases)==112 and all(x['execution_state']=='NOT_RUN' and x['actual_evidence'] is None for x in cases)
    checks['frozen_77_and_81_identities_unchanged']=len(seeds)==77 and sum(len(x['source_candidates']) for x in seeds)==81 and all(a['canonical_table']==b['canonical_table'] and [{k:v for k,v in s.items() if k!='object_name_candidates'} for s in a['source_candidates']]==[{k:v for k,v in s.items() if k!='object_name_candidates'} for s in b['source_candidates']] for a,b in zip(seeds,prior('77项任务候选种子.json')['items']))
    checks['77_still_disabled_unknown_no_live_credentials']=all(x['enabled'] is False and x['runtime_readiness']=='UNKNOWN' and x['long_lived_credential_ref'] is None for x in seeds)
    allowed_alert_changes={'package_id','metadata_allowlist'}
    checks['accepted_alert_protocol_unchanged']=all(config[k]==v for k,v in old_config.items() if k not in allowed_alert_changes)
    checks['alert_actions_safe_metadata_extension']=set(config['metadata_allowlist'])==set(old_config['metadata_allowlist'])|{'recommended_action'} and config['metadata_max_keys']==32
    old_tasks={x['id']:x for x in prior('长任务执行契约.json')['tasks']}
    checks['e08_e09_e10_gates_preserved']=all((x['subtasks'],x['entry_gates'])==(old_tasks[x['id']]['subtasks'],old_tasks[x['id']]['entry_gates']) for x in contract['tasks'] if x['id'] in ['E08','E09','E10'])
    checks['existing_authorization_not_broadened']=contract['approvals']==prior('长任务执行契约.json')['approvals']
    failed=read('故障隔离与继续执行规则.json')
    rules={x['error']:x for x in failed['rules']}
    checks['continue_default_and_unknown_scoped']=failed['default']=='CONTINUE_INDEPENDENT_SCOPES' and not failed['stop_all_on_first_error'] and not failed['silent_skip_allowed'] and rules['COMMIT_UNKNOWN']['scope']=='same_target_table_writer'
    scan=read('迟到漂移月度重扫策略.json')
    checks['monthly_stage_first_history_and_budgets_pending']=not scan['enabled'] and not scan['delete_before_source_complete_allowed'] and not scan['delete_commit_before_insert_allowed'] and scan['business_month_is_not_run_month'] and scan['cycle_max_age_days'] is None
    lis=read('LIS双源路由候选.json')
    checks['lis_overlap_four_sources_not_clobbered']=len(lis['tables'])==4 and all(len(t['segments'][1]['sources'])==2 and not t['delete_other_origin_allowed'] and not t['automatic_business_dedupe_allowed'] for t in lis['tables'])
    profiles=read('每表性能与通道画像候选.json')['profiles']
    checks['77_profiles_and_distinct_physical_routes']=len(profiles)==77 and all(not x['verified_for_production'] and x['query_cancel_seconds'] is None for x in profiles) and next(x for x in seeds if x['canonical_table']=='EMR_IN_OUT_AMOUNT')['legacy_view_transport_hint'].startswith('DATAX_ONLY_REPORTED')
    checks['no_invented_running_process_snapshot']=read('在跑任务交接快照模板.json')['snapshot_captured'] is False
    refs=read('实测参考资产与证据指纹.json')
    aliases=[]
    for before,after in zip(prior('77项任务候选种子.json')['items'],seeds):
        for a,b in zip(before['source_candidates'],after['source_candidates']):
            if a['object_name_candidates']!=b['object_name_candidates']:
                aliases.append((after['canonical_table'],b['object_id'],a['object_name_candidates'],b['object_name_candidates']))
    checks['shared_source_alias_drift_explicitly_recorded']=aliases==[(x['table'],x['object_id'],x['before_aliases'],x['after_aliases']) for x in refs['source_alias_changes_since_v11']]
    checks['evidence_files_exist_hash_match']=all(x['exists'] and hashlib.sha256(Path(x['path']).read_bytes()).hexdigest()==x['sha256'] for x in refs['assets'])
    checks['legacy_compare_issues_not_blindly_copied']=refs['gap_exec_findings']['same_value_calls_float'] and refs['gap_exec_findings']['same_value_strips_all_strings']
    workbook=load_workbook(HERE/'执行批次与验收矩阵.xlsx',read_only=True,data_only=True)
    checks['xlsx_ten_sheets_and_exact_counts']=len(workbook.sheetnames)==10 and workbook['验收场景'].max_row==113 and workbook['77表性能通道画像'].max_row==78 and workbook['E01至E10执行批次'].max_row==11
    headers=[c.value for c in next(workbook['每日运行日报模板'].iter_rows(min_row=1,max_row=1))]
    checks['report_exposes_deadline_and_backlog']=all(s in headers for s in ['失败业务窗/待补','deadline是否配置','月度重扫最近全核/到期/欠账'])
    workbook.close()
    hashes=read('交付文件指纹.json')
    checks['all_delivery_fingerprints_match']=all(hashlib.sha256((HERE/n).read_bytes()).hexdigest()==h for n,h in hashes.items())
    with zipfile.ZipFile(HERE/'Python_DataX统一T加1长任务执行包_20261019.zip') as z:
        checks['zip_payload_exact_and_hashes']=set(z.namelist())==set(hashes)|{'交付文件指纹.json'} and all(hashlib.sha256(z.read(n)).hexdigest()==h for n,h in hashes.items())
    docs=['Python与DataX统一T加1顶层设计及长任务执行计划.md','给执行AI的长任务启动提示词.md','实测建议评估与计划修订说明.md','失败后继续抽取与补抽规则.md']
    missing=[]
    for name in docs:
        text=(HERE/name).read_text(encoding='utf-8')
        for ref in re.findall(r'\]\(([^)]+)\)',text):
            if not ref.startswith(('https://','http://')) and not (HERE/ref).exists():missing.append([name,ref])
    checks['local_document_links_resolve']=not missing
    output={'state':'INDEPENDENT_PLANNING_DELIVERY_CHECKS_ONLY','checks':checks,'all_pass':all(checks.values()),
        'checks_passed':sum(checks.values()),'acceptance_expectations':112,'engine_tests_run':0,'business_queries':0,
        'production_changes':0,'real_alerts_sent':0,'missing_links':missing}
    (HERE/'交付独立核对.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(output,ensure_ascii=False,indent=2))
    assert output['all_pass']


if __name__=='__main__':main()
