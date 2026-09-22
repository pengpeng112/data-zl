# -*- coding: utf-8 -*-
"""r198 B4 补充：语料上下文消歧（F03 的可追溯证据路径）。
对 ambiguous 端点，扫描族成员模板原文：
- 任意限定写法 owner.table 且 owner 命中某候选 schema → 该源；
- @sjzx / V_EMR_* / CDR_* 出现于同语句 → ODS 语境证据；
- 全语料均无限定且无 ODS 标记 → 保持 ambiguous（不默认）。
输出 review_corrections_v2.json（更新 167 条处置）。只读输入。"""
from __future__ import annotations

from pathlib import Path
import json
import re
import sys
import collections

ROOT = Path(__file__).resolve().parents[1]
RUN197 = ROOT / '开发起步包/output_r197/r197-20260921-s1'
OUT = ROOT / '开发起步包/output_r198/r198-20260922-remediation'


def read197(name):
    path = RUN197 / name
    if name.endswith('.jsonl'):
        return [json.loads(s) for s in path.read_text(encoding='utf-8').splitlines() if s.strip()]
    return json.loads(path.read_text(encoding='utf-8'))


def main():
    templates = {}
    for s in ('s2', 's3', 's4', 's5'):
        for t in read197(s + '_templates.jsonl'):
            templates.setdefault(t['template_hash'], t['rep_text'])
    rc = json.loads((OUT / 'review_corrections.json').read_text(encoding='utf-8'))
    fams = {f['new_family_id']: f for f in json.loads((OUT / 'b3_new_families.json').read_text(encoding='utf-8'))}

    def ctx_resolve(e, member_texts):
        """返回 (system, source, schema, evidence) 或 None。"""
        tb = e['table'].split('.')[-1].upper()
        owner_hits = collections.Counter()
        ods_marks = 0
        for txt in member_texts:
            low = txt.lower()
            for m in re.finditer(r'\b([A-Za-z_][\w$#]*)\s*\.\s*' + re.escape(tb) + r'\b', low):
                owner_hits[m.group(1).upper()] += 1
            if '@sjzx' in low or re.search(r'\bV_EMR_\w+', low) or re.search(r'\bCDR_\w+', low):
                ods_marks += 1
        cands = e.get('candidates') or []
        schemas = {c['schema'].upper(): c for c in cands}
        for owner, n in owner_hits.most_common():
            if owner == 'HIS':
                continue  # 'HIS' 前缀两侧都可能是（ODS schema 名即 HIS），不构成区分
            if owner in schemas:
                c = schemas[owner]
                return c['system'], c['source'], c['schema'], f'限定写法 {owner}.{tb} ×{n}（模板原文）'
        # ODS 语境：同语句含 V_EMR_/CDR_/@sjzx 且 ODS 候选存在
        if ods_marks and any(c['system'] == 'DATA_CENTER' for c in cands):
            c = next(c for c in cands if c['system'] == 'DATA_CENTER')
            return c['system'], c['source'], c['schema'], f'同语句 ODS 标记 ×{ods_marks}（V_EMR_/CDR_/@sjzx）'
        return None

    updated = []
    counts = collections.Counter()
    for row in rc['rows']:
        row2 = dict(row)
        if row['recommended_action'] == 'source_pending':
            fam_ids = row['new_family_ids']
            member_texts = []
            for fid in fam_ids[:3]:
                f = fams.get(fid)
                if f:
                    for mg in f.get('member_groups', [])[:8]:
                        t = templates.get(mg['th'])
                        if t:
                            member_texts.append(t)
            fixes = {}
            improved = False
            for pfx, side in (('from', 'a'), ('to', 'b')):
                f0 = fams.get(fam_ids[0]) if fam_ids else None
                if not f0:
                    continue
                e = f0['endpoints'][side]
                if e['status'] != 'ambiguous':
                    continue
                r = ctx_resolve(e, member_texts)
                if r:
                    sysc, src, schema, ev = r
                    fixes[pfx + '_system_code'] = sysc
                    fixes[pfx + '_source_code'] = src
                    fixes[pfx + '_evidence'] = ev
                    improved = True
                else:
                    fixes[pfx + '_status'] = 'ambiguous_no_context_evidence'
            if improved:
                both = ('from_system_code' in fixes) and ('to_system_code' in fixes)
                row2['recommended_action'] = ('confirm_with_source_fix' if both else 'source_partial_context')
                row2['proposed_fix'] = {**row.get('proposed_fix', {}), **fixes}
            else:
                row2['recommended_action'] = 'source_pending_no_context'
        counts[row2['recommended_action']] += 1
        updated.append(row2)
    out = {**{k: v for k, v in rc.items() if k != 'rows'}, 'counts': dict(counts), 'rows': updated,
           'method_note': '语料上下文消歧：限定 owner 写法/ODS 标记（V_EMR_/CDR_/@sjzx）为可追溯证据；'
                          '无证据不默认（F03）。ODS 为结构镜像，列差无法区分两源。'}
    (OUT / 'review_corrections_v2.json').write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(dict(counts), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
