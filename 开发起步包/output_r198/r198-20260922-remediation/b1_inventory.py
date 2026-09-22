# -*- coding: utf-8 -*-
"""B1 建立对象/字段/资产ID底账（asset_inventory.json）。
- 167 生产 reviews：review_id ↔ relation_id 精确映射（以回读 source_evidence 为准，不靠连续 ID 假设）
- 13 配方 / 34 值域：准确 ID + 自然键闭合
- 405 旧族：imported / excluded(类别) 去向闭合；238 未导入逐类归因
- 端点身份登记：族 resolved 候选 + 平台现行系统/源事实（HIS_SOURCE 零源、HIS 挂 his_source_10_10_10_15）
- 125 未匹配对象：证据分类（解析伪影/CTE临时/外部库/历史对象/HIS源内未采/待核）
只读输入；输出仅写本目录。"""
from pathlib import Path
import hashlib
import json
import re
import collections

ROOT = Path(__file__).resolve().parents[3]
RUN197 = ROOT / '开发起步包/output_r197/r197-20260921-s1'
AUDIT = ROOT / 'review/adhoc/r197-audit-20260922'
OUT = Path(__file__).parent


def read197(name):
    path = RUN197 / name
    if name.endswith('.jsonl'):
        return [json.loads(s) for s in path.read_text(encoding='utf-8').splitlines() if s.strip()]
    return json.loads(path.read_text(encoding='utf-8'))


def h(obj):
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def main():
    payload_rows = read197('import_payload.json')['rows']
    diff = read197('import_diff.json')
    rels = read197('relations.jsonl')
    sm = read197('source_mapping_raw.json')
    readback = json.loads((AUDIT / 'platform_readback.json').read_text(encoding='utf-8'))
    identity = json.loads((OUT / 'b1_platform_identity.json').read_text(encoding='utf-8'))

    # ---------- 1) 167 reviews：review_id ↔ relation_id 精确映射 ----------
    reviews = sorted(readback['reviews'], key=lambda r: r['id'])
    mapping_ok, mapping_detail = True, []
    for i, (rv, row) in enumerate(zip(reviews, payload_rows)):
        ev = json.loads(rv['source_evidence']) if rv.get('source_evidence') else {}
        rid_platform = ev.get('relation_id')
        rid_payload = row.get('relation_id')
        ok = rid_platform == rid_payload
        mapping_ok &= ok
        mapping_detail.append({'review_id': rv['id'], 'relation_id': rid_payload,
                               'match': ok,
                               'from': [rv['from_system_code'], rv['from_table'], rv['from_columns']],
                               'to': [rv['to_system_code'], rv['to_table'], rv['to_columns']],
                               'review_status': rv['review_status'],
                               'validation_status': rv['validation_status']})

    # ---------- 2) 405 族去向闭合 ----------
    imported_ids = {r['relation_id'] for r in payload_rows}
    fam_by_id = {r['relation_id']: r for r in rels}
    # excluded 逐族归类：按 intake_state + 排除类别规则重演（import_diff 只有类别计数）
    # 规则（来自 197 排除逻辑）：existing→platform_formal_covers_evidence_only；d_crosssource→d_crosssource_unlocated；
    # blocked→blocked_source；rejected_negative→rejected_negative；failed→validation_failed_not_positive_edge；
    # insufficient→validation_insufficient；ordervar juniors(8)→order_variant_merged_into_senior；
    # unresolved(5)→endpoint_unresolved；ops dict view(4)→ops_dictionary_view；platform_draft_same_edge(1)
    ordervar = set(diff.get('ordervar_merged_juniors', []))
    internal_juniors = {pair[1] for pair in read197('import_payload.json').get('internal_pair_duplicates', [])}
    OPS_VIEW = re.compile(r'^(V\$|DBA_|GV\$)', re.I)
    families = []
    cat_counts = collections.Counter()
    for r in rels:
        rid = r['relation_id']
        unknown_endpoint = any(e.get('unknown') for e in r['endpoints'].values())
        ops_tags = any('ops_dictionary' in t for t in (r.get('risk_tags') or []))
        ops_tables = all(OPS_VIEW.match(e['table']) for e in r['endpoints'].values())
        if rid in imported_ids:
            disp = 'imported'
        elif rid in internal_juniors:
            disp = 'internal_pair_duplicate_junior'
        elif rid in ordervar:
            disp = 'order_variant_merged_into_senior'
        elif ops_tags or ops_tables:
            disp = 'ops_dictionary_view'
        elif rid == 'S2F-4EB1EB7136':
            disp = 'platform_draft_same_edge'  # OPERATION↔OPERATION_DICT 与平台既有草稿同边（197 S7 查重结论）
        elif r['intake_state'] == 'existing_supplement':
            disp = 'platform_formal_covers_evidence_only'
        elif r['intake_state'] == 'candidate_d_crosssource':
            disp = 'd_crosssource_unlocated'
        elif r['intake_state'] == 'candidate_blocked_source':
            disp = 'blocked_source'
        elif r['intake_state'] == 'rejected_negative':
            disp = 'rejected_negative'
        elif unknown_endpoint:
            disp = 'endpoint_unresolved'
        else:  # candidate / partial 未导入的残余类别
            if r['validation_state'] == 'failed':
                disp = 'validation_failed_not_positive_edge'
            elif r['validation_state'] == 'insufficient':
                disp = 'validation_insufficient'
            else:
                disp = 'other_not_imported'
        cat_counts[disp] += 1
        families.append({'relation_id': rid, 'stage': r['stage'], 'intake_state': r['intake_state'],
                         'validation_state': r['validation_state'],
                         'disposition': disp,
                         'review_id': next((m['review_id'] for m in mapping_detail if m['relation_id'] == rid), None),
                         'content_sha256': h(r)})
    # 闭合校验：重演类别计数 vs import_diff.excluded 计数（excluded 236 + internal_pair 2 = 238 未导入）
    diff_ex = dict(diff['excluded'])
    diff_ex['internal_pair_duplicate_junior'] = len(internal_juniors)
    replay = {k: v for k, v in cat_counts.items() if k != 'imported'}
    closure = {}
    for k in set(replay) | set(diff_ex):
        closure[k] = {'replay': replay.get(k, 0), 'import_diff': diff_ex.get(k, 0)}
    unexplained = {k: v for k, v in closure.items() if v['replay'] != v['import_diff']}
    other_ids = [f['relation_id'] for f in families if f['disposition'] == 'other_not_imported']

    # ---------- 3) 端点身份登记 ----------
    plat_tables = {}
    for c in json.loads((AUDIT / 'platform_endpoint_columns.json').read_text(encoding='utf-8')):
        key = (c['schema_name'].upper(), c['table_name'].upper())
        plat_tables.setdefault(key, set()).add((c['system_code'], c['source_code']))
    endpoint_registry = {}
    for r in rels:
        for side, ep in r['endpoints'].items():
            t = ep['table'].upper()
            entry = endpoint_registry.setdefault(t, {'candidates': [], 'unknown': ep.get('unknown', False), 'used_by': 0})
            entry['used_by'] += 1
            for cand in ep.get('resolved', []):
                key = (cand['schema'].upper(), t)
                plat_idents = plat_tables.get(key, set())
                entry['candidates'].append({'system': cand['system'], 'source': cand['source'],
                                            'schema': cand['schema'],
                                            'platform_registered': bool(plat_idents)})
    for t, e in endpoint_registry.items():
        seen, uniq = set(), []
        for c in e['candidates']:
            k = (c['system'], c['source'], c['schema'])
            if k not in seen:
                seen.add(k)
                uniq.append(c)
        e['candidates'] = uniq
        systems = {c['system'] for c in uniq}
        e['cross_system'] = len(systems) > 1
        e['n_candidates'] = len(uniq)
        # 现行平台事实校正：system 'HIS' + source his_source_10_10_10_15 为有效；'HIS_SOURCE' 系统零源
        e['valid_system_note'] = '平台现行：HIS(his_source_10_10_10_15/hisbase_10_10_10_14)、DATA_CENTER(ods_*)；HIS_SOURCE 系统零数据源'

    # 167 导入行的端点 chosen schema 校验（primary_loc 选择的 schema 是否在候选内）
    chosen_issues = []
    for row in payload_rows:
        rid = row['relation_id']
        fam = fam_by_id.get(rid)
        if not fam:
            continue
        for side, pcol in (('a', 'from'), ('b', 'to')):
            tab = row[pcol + '_table']  # e.g. "INPBILL.INP_BILL_DETAIL"
            parts = tab.split('.')
            if len(parts) == 2:
                chosen_schema, bare = parts[0].upper(), parts[1].upper()
                ep = fam['endpoints'].get(side, {})
                cands = {(c.get('schema') or '').upper() for c in ep.get('resolved', [])}
                if cands and chosen_schema not in cands:
                    chosen_issues.append({'relation_id': rid, 'side': side, 'chosen': tab, 'candidates': sorted(cands)})
                if ep.get('table', '').upper() != bare:
                    chosen_issues.append({'relation_id': rid, 'side': side, 'chosen_table_mismatch': tab,
                                          'family_table': ep.get('table')})

    # ---------- 4) 125 未匹配对象证据分类 ----------
    templates = {}
    for s in ('s2', 's3', 's4', 's5'):
        for t in read197(s + '_templates.jsonl'):
            templates[t['template_hash']] = t['rep_text']
    texts = list(templates.values())
    all_text = '\n'.join(texts).lower()

    def occurs(obj):
        return len(re.findall(r'(?<![A-Za-z0-9_#$.])' + re.escape(obj.lower()) + r'(?![A-Za-z0-9_$])', all_text))

    def cte_defined(obj):
        pat = re.compile(r'(?<![A-Za-z0-9_$])' + re.escape(obj.lower()) + r'\s+as\s*\(', re.I)
        return any(pat.search(t) for t in texts)

    PARSER_ARTIFACT = {'WHERE', 'SUM', 'SQLSPT', 'ODERS', 'TABLE_NAME', 'TABLE_NAME_4J', 'TABLE_NAME_BFZ',
                       'TABLE_NAME_WC', 'HS20200714'}
    CHINESE_FRAG = {'加工号改序列', '手麻系统中对应信息修改一致后', '改医嘱SELECT', '科室护理单元对照'}
    # 名字证据子类（均有语句文本出现次数为证；不猜语义，只按可追溯命名族归组）
    NAME_FAMILY = [
        (re.compile(r'^EXP_'), 'exp_pharmacy_family_pending'),           # 药库 EXP_ 家族（197 S1 判读，待源字典核）
        (re.compile(r'^DRG_|^PAT_DRGS$'), 'drg_family_pending'),          # DRG 医保族
        (re.compile(r'^INPUT_|^GMZJ|^ZY_ZYYZXXMX$|^PRESC_T$|^OUTP_ORDERS_T$|^OUTP_TREAT_REC_T$|^TTTT$'), 'likely_temp_worktable_pending'),
        (re.compile(r'^INSUR|^YB_MAPPING$|^PUB_PATIENTINFO_INSURE$'), 'insurance_related_pending'),
    ]
    OWNER_EXPLICIT = re.compile(r'^([A-Z0-9_]+)\.\.?.+$')
    # 归并 X..Y 与 X.Y（同名同 owner 双写）
    norm_map = {}
    for o in sm['unmatched']:
        m = OWNER_EXPLICIT.match(o)
        owner = m.group(1) if m else ''
        norm_map.setdefault((owner, o.split('.')[-1].upper()), []).append(o)
    obj_class = []
    for (owner, bare), variants in sorted(norm_map.items()):
        occ = sum(occurs(v) for v in variants)
        if any(v in PARSER_ARTIFACT for v in variants):
            cls = 'parser_artifact_static'
        elif any(v in CHINESE_FRAG for v in variants):
            cls = 'parser_artifact_chinese_fragment'
        elif bare in {'OPERATION_NAME', 'SCHEDULED_OPERATION_NAME', 'DICTIONARYSET', 'EMR', 'DRUG_P'}:
            # OPERATION_NAME 189 次出现高度疑似"列名误当表名"（ISS-S4-NAMEJOIN 语境）；待 B2 新解析器证实
            cls = 'suspected_column_as_table_pending'
        elif cte_defined(variants[-1]) or cte_defined(bare):
            cls = 'cte_or_derived_alias'
        elif owner in {'INSURANCE', 'INSUR_EXPORT', 'YJYY', 'YJTBIS', 'TJJKHLYY', 'GGWS', 'LCLJ', 'EMR', 'EXAM_BL', 'MONURSING', 'SYSTEM', 'HISUSER', 'LAB'}:
            cls = 'other_db_or_schema_owner'
        else:
            cls = next((fam for pat, fam in NAME_FAMILY if pat.match(bare)), 'unclassified_pending')
        obj_class.append({'owner': owner, 'bare': bare, 'variants': variants, 'class': cls,
                          'template_occurrences': occ,
                          'evidence': ('模板文本 ' + ('含 CTE/派生定义' if cls == 'cte_or_derived_alias' else f'{occ} 次出现')) if occ or cls == 'cte_or_derived_alias' else '模板无出现'})
    cls_counts = collections.Counter(o['class'] for o in obj_class)

    # ---------- 5) 值域自然键闭合 ----------
    domains_inv = []
    for d in readback['domains']:
        key = {'system_code': d['system_code'], 'source_code': d['source_code'], 'schema_name': d['schema_name'],
               'table_name': d['table_name'], 'column_name': d['column_name'], 'code': d['code']}
        domains_inv.append({'id': d['id'], 'natural_key': key, 'code_repr': repr(d['code']),
                            'status': d['status'], 'domain_kind': d['domain_kind'],
                            'current_version_id': d['current_version_id'], 'evidence_count': d['evidence_count'],
                            'note': d['note'], 'row_sha256': h(d)})
    recipes_inv = [{'recipe_id': r['recipe_id'], 'status': r['status'], 'is_active': r['is_active'],
                    'content_hash': r['content_hash']} for r in readback['recipes']]

    inventory = {
        'run_id': 'r198-20260922-remediation', 'built_at': '2026-09-22', 'stage': 'B1',
        'platform_facts': {
            'system_codes': {'HIS': '含 his_source_10_10_10_15 + hisbase_oracle_10_10_10_14', 'HIS_SOURCE': '系统存在但零数据源（悬空）', 'DATA_CENTER': 'ods_* 镜像源'},
            'review_system_codes_are_dangling': '167 草稿 from/to_system_code=HIS_SOURCE 无对应数据源；修正目标=HIS/his_source_10_10_10_15（按端点实际归属）',
            'gap_696_wait_bed_user_name': 'INPADM.WAIT_BED_PATS_NEW 平台列 50 个、无 USER_NAME（有 NAME/NAME_PHONETIC）→ 列存在证据缺失，待 B4 有界核验',
            'gap_766_drug_catalog': 'OFFICIAL_DRUG_CATALOG(_CLASS) 平台已登记表(Comm/his_source_10_10_10_15)但列级元数据 0 行 → 列级漏采或表结构变更，待 B4 有界核验',
        },
        'reviews': {'count': len(mapping_detail), 'id_range': [reviews[0]['id'], reviews[-1]['id']],
                    'mapping_payload_order_matches_platform': mapping_ok, 'rows': mapping_detail},
        'recipes': {'count': len(recipes_inv), 'rows': recipes_inv},
        'value_domains': {'count': len(domains_inv), 'natural_key_closure': '32 note含197 + 2 精确自然键(OPERATION_SCALE 尾随空格变体/OPER_CODE 多义键)',
                          'rows': domains_inv},
        'families': {'total': len(families), 'disposition_replay': dict(cat_counts),
                     'closure_check': closure, 'closure_unexplained': unexplained,
                     'other_not_imported_ids': other_ids, 'rows': families},
        'endpoint_registry': endpoint_registry,
        'primary_loc_chosen_issues': chosen_issues,
        'unmatched_objects': {'raw_count': len(sm['unmatched']), 'normalized_count': len(obj_class),
                              'class_counts': dict(cls_counts), 'rows': obj_class},
        'template_corpus': {'unique_templates': len(templates), 'stages': ['s2', 's3', 's4', 's5']},
    }
    (OUT / 'asset_inventory.json').write_text(json.dumps(inventory, ensure_ascii=False, indent=2), encoding='utf-8')
    summary = {
        'reviews_mapping_ok': mapping_ok,
        'families_closure_unexplained': unexplained,
        'other_not_imported_ids': other_ids,
        'endpoint_registry_size': len(endpoint_registry),
        'endpoints_cross_system': sum(1 for e in endpoint_registry.values() if e['cross_system']),
        'endpoints_unknown': sum(1 for e in endpoint_registry.values() if e['unknown']),
        'primary_loc_chosen_issues': len(chosen_issues),
        'unmatched_class_counts': dict(cls_counts),
        'domains_code_repr_trailing_space': [d['id'] for d in domains_inv if d['code_repr'].rstrip("'").endswith(' ')],
    }
    (OUT / 'b1_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
