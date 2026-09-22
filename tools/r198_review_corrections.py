# -*- coding: utf-8 -*-
"""r198 B3 补充：167 条生产草稿的逐 review 修订方案（B7 批准包的底稿）。
按 B1 精确映射 + B3 新族结果，给出每条 review 的：
- system/source 修正（HIS_SOURCE→HIS/his_source_10_10_10_15 等现行映射；ODS 侧 DATA_CENTER/ods_8_216）
- 端点解析状态（unique/owner_resolved/ambiguous/unknown → 是否可进入可批准清单）
- 映射处置（confirm_with_source_fix / source_pending / columns_changed_review / propose_reject / keep）
只读输入；输出 review_corrections.json。"""
from pathlib import Path
import json
import collections

ROOT = Path(__file__).resolve().parents[1]
RUN197 = ROOT / '开发起步包/output_r197/r197-20260921-s1'
OUT = ROOT / '开发起步包/output_r198/r198-20260922-remediation'


def main():
    inv = json.loads((OUT / 'asset_inventory.json').read_text(encoding='utf-8'))
    o2n = {m['old_relation_id']: m for m in json.loads((OUT / 'old_to_new_relations.json').read_text(encoding='utf-8'))}
    newfams = {f['new_family_id']: f for f in json.loads((OUT / 'b3_new_families.json').read_text(encoding='utf-8'))}
    payload = json.loads((RUN197 / 'import_payload.json').read_text(encoding='utf-8'))['rows']
    row_by_rid = {r['relation_id']: r for r in payload}

    rows = []
    counts = collections.Counter()
    for rv in inv['reviews']['rows']:
        rid, review_id = rv['relation_id'], rv['review_id']
        m = o2n.get(rid)
        fam_ids = m['new_family_ids'] if m else []
        fams = [newfams[f] for f in fam_ids]
        # 端点解析：取首个新族的端点身份
        end_status, src_fix = {}, {}
        if fams:
            f0 = fams[0]
            for side, pfx in (('a', 'from'), ('b', 'to')):
                e = f0['endpoints'][side]
                end_status[pfx] = e['status']
                if e['status'] in ('owner_resolved', 'unique'):
                    src_fix[pfx + '_system_code'] = e['system']
                    src_fix[pfx + '_source_code'] = e['source']
                elif e['status'] == 'ambiguous':
                    src_fix[pfx + '_candidates'] = [{'system': c['system'], 'source': c['source'],
                                                     'schema': c['schema']} for c in e['candidates'][:4]]
                else:
                    src_fix[pfx + '_status'] = e['status']
        statuses = set(end_status.values())
        if not m:
            action = 'mapping_missing_review'
        elif m['mapping_status'] == 'dropped_by_reparse':
            action = 'propose_reject_or_hold'   # 新解析无法复现该边；人工裁决前不批
        elif m['mapping_status'] == 'columns_changed':
            action = 'columns_changed_review'   # 列集变化：更新列或关闭旧条新建
        elif statuses and statuses <= {'unique', 'owner_resolved'}:
            action = 'confirm_with_source_fix'  # 修正 system/source 后可入人工审批
        elif 'ambiguous' in statuses:
            action = 'source_pending'           # 歧义未定，不进入可批准清单
        else:
            action = 'source_unknown_pending'
        counts[action] += 1
        rows.append({
            'review_id': review_id, 'relation_id': rid,
            'current': {'from_system': rv['from'][0], 'from_table': rv['from'][1], 'to_system': rv['to'][0],
                        'to_table': rv['to'][1], 'join': None},
            'mapping_status': m['mapping_status'] if m else 'missing',
            'new_family_ids': fam_ids,
            'endpoint_resolution': end_status,
            'proposed_fix': src_fix,
            'recommended_action': action,
            'note': (m['note'] if m else '旧族未映射'),
        })
    out = {'generated': '2026-09-22', 'counts': dict(collections.Counter(counts)),
           'system_code_note': 'HIS_SOURCE 系统零数据源；现行映射 HIS/his_source_10_10_10_15（业务库）、'
                               'HIS/hisbase_oracle_10_10_10_14（基本信息库）、DATA_CENTER/ods_8_216（ODS 镜像）',
           'rows': rows}
    (OUT / 'review_corrections.json').write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(out['counts'], ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
