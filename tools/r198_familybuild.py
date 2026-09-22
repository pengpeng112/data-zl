# -*- coding: utf-8 -*-
"""r198 B3：以 B2 作用域边重建关系族 + 平台严格查重 + 旧405族映射。

修正 197 F02/F03：
- 族键=两端(schema.table)+成对列集合+join 语义（类型+保留端）；INNER 反向等价（配对随端交换），
  LEFT 反向=保留端翻转后等价；子集列不是重复；同表不同字段不是重复。
- 复合键只合同一 (block, and_group) 的等值边；OR 分支/跨块/跨模板不合并。
- existing_supplement 仅当平台匹配覆盖两端全部列（严格覆盖证据）。
- 端点来源按 owner 前缀/DBLINK/候选集解析；歧义如实标注，不排序取首。
输出（本目录）：b3_new_families.json / old_to_new_relations.json / correction_diff.json / b3_summary.json
"""
from __future__ import annotations

from pathlib import Path
import json
import sys
import collections

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import r198_sql_parse as rsp  # noqa: E402

RUN197 = ROOT / '开发起步包/output_r197/r197-20260921-s1'
OUT = ROOT / '开发起步包/output_r198/r198-20260922-remediation'


def read197(name):
    path = RUN197 / name
    if name.endswith('.jsonl'):
        return [json.loads(s) for s in path.read_text(encoding='utf-8').splitlines() if s.strip()]
    return json.loads(path.read_text(encoding='utf-8'))


def norm_table(t: str) -> str:
    return t.replace('..', '.').strip().upper()


def bare(t: str) -> str:
    return norm_table(t).split('.')[-1].split('@')[0]


def split_cols(s):
    return tuple(c.strip().upper() for c in (s or '').split('|') if c.strip())


def endpoint_identity(table_written: str, registry: dict):
    """(schema, system, source, status, candidates)——owner 前缀优先，歧义不猜。"""
    t = norm_table(table_written)
    if '@' in t:
        return None, None, t.split('@')[1].split('.')[0], 'dblink', []
    parts = t.split('.')
    if len(parts) == 2:
        owner, tb = parts[0], parts[1]
        cands = [c for c in registry.get(tb, {}).get('candidates', []) if c['schema'] == owner]
        if cands:
            c = cands[0]
            return owner, c['system'], c['source'], 'owner_resolved', cands
        return owner, None, None, 'owner_unknown_schema', []
    tb = parts[-1]
    cands = registry.get(tb, {}).get('candidates', [])
    if not cands:
        return None, None, None, 'unknown_object', []
    uniq = {(c['system'], c['source'], c['schema']) for c in cands}
    if len(uniq) == 1:
        c = cands[0]
        return c['schema'], c['system'], c['source'], 'unique', cands
    return None, None, None, 'ambiguous', cands


def join_semantics(edge) -> tuple:
    """(type, preserved_end_ref) 按边自身 l/r 引用；inner 交叉反转在族键规范化时处理。"""
    jt = edge.get('join_type')
    plus = edge.get('plus_side')
    if jt is None:
        jt = {'R': 'left', 'L': 'right'}.get(plus, 'inner')
    preserve = None
    if jt == 'left' and not edge.get('orientation_uncertain'):
        preserve = 'L'
    elif jt == 'right' and not edge.get('orientation_uncertain'):
        preserve = 'R'
    elif jt == 'left' and edge.get('orientation_uncertain'):
        preserve = 'uncertain'
    elif jt == 'right' and edge.get('orientation_uncertain'):
        preserve = 'uncertain'
    return jt, preserve


def main():
    parsed = [json.loads(s) for s in (OUT / 'b2_parsed_templates.jsonl').read_text(encoding='utf-8').splitlines() if s.strip()]
    stmt_by_tmpl = collections.defaultdict(list)
    file_by_tmpl = collections.defaultdict(set)
    for s in ('s2', 's3', 's4', 's5'):
        for w in read197(s + '_workset.jsonl'):
            stmt_by_tmpl[w['template_hash']].append((s, w['stmt_id']))
            file_by_tmpl[w['template_hash']].add(w['file'])
    inv = json.loads((OUT / 'asset_inventory.json').read_text(encoding='utf-8'))
    registry = inv['endpoint_registry']
    plat = json.loads((OUT / 'b3_platform_relations.json').read_text(encoding='utf-8'))
    old_rels = read197('relations.jsonl')

    # ---------- 1) 模板内：同(block,and_group,表对)复合组 ----------
    groups = []      # {'tables':(A,B) 规范序, 'pairs':[(colA,colB)...], 'join':(jt,preserved_end), members...}
    derived_pending = []
    for row in parsed:
        th = row['template_hash']
        try:
            phys = rsp.physical_tables(row)
        except Exception:
            phys = {}
        gacc = collections.defaultdict(list)
        for e in row['edges']:
            sides = []
            ok = True
            for side in ('l', 'r'):
                kind = e[side + '_kind']
                if kind in ('table', 'dblink'):
                    sides.append(e[side + '_table'])
                else:
                    ps = {p for p in phys.get(e[side + '_instance'], set()) if '@' not in p}
                    if len(ps) == 1:
                        sides.append(next(iter(ps)))
                    else:
                        ok = False
                        break
            if not ok:
                derived_pending.append({'template_hash': th,
                                        'edge': {k: e[k] for k in ('l_table', 'l_col', 'r_table', 'r_col', 'block')}})
                continue
            lt, rt = norm_table(sides[0]), norm_table(sides[1])
            if bare(lt) == bare(rt) and lt == rt:
                # 自连接保留两实例：不交换序（按 l/r 原序成族，alias 区分记录在成员）
                key_t = (lt, rt)
                swapped = False
            elif (lt, e['l_col']) <= (rt, e['r_col']):
                key_t = (lt, rt)
                swapped = False
            else:
                key_t = (rt, lt)
                swapped = True
            jt, preserve = join_semantics(e)
            # 规范化到 A/B 序
            if swapped:
                pair = (e['r_col'], e['l_col'])
                preserve = {'L': 'R', 'R': 'L', None: None, 'uncertain': 'uncertain'}[preserve]
            else:
                pair = (e['l_col'], e['r_col'])
            gacc[(key_t, e.get('block'), e.get('and_group'))].append(
                {'pair': pair, 'jt': jt, 'preserve': preserve, 'e': e, 'swapped': swapped})
        for (key_t, block, ag), members in gacc.items():
            A, B = key_t
            pairs = sorted({m['pair'] for m in members})
            jtset = {(m['jt'], m['preserve']) for m in members}
            if len(jtset) == 1:
                jt, preserve = next(iter(jtset))
            else:
                jt, preserve = 'mixed', 'mixed'
            groups.append({'A': A, 'B': B, 'pairs': pairs, 'join_type': jt, 'preserve': preserve,
                           'block': block, 'and_group': ag, 'members': members, 'th': th,
                           'self_join': A == B})

    # ---------- 2) 跨模板族聚合（严格键） ----------
    fam = collections.defaultdict(list)
    for g in groups:
        key = (g['A'], g['B'], tuple(g['pairs']), g['join_type'], g['preserve'], g['self_join'])
        fam[key].append(g)
    new_families = []
    for i, (key, gs) in enumerate(sorted(fam.items(), key=lambda kv: (-len(kv[1]), kv[0]))):
        A, B, pairs, jt, preserve, self_join = key
        ths = {g['th'] for g in gs}
        stmts = [(s, sid) for th in ths for (s, sid) in stmt_by_tmpl.get(th, [])]
        files = sorted({f for th in ths for f in file_by_tmpl.get(th, [])})
        # 端点来源身份
        ends = {}
        for tag, tbl in (('a', A), ('b', B)):
            schema, system, source, status, cands = endpoint_identity(tbl, registry)
            ends[tag] = {'table': tbl, 'schema': schema, 'system': system, 'source': source,
                         'status': status, 'candidates': cands[:6]}
        sysa, sysb = ends['a']['system'], ends['b']['system']
        cross_system = bool(sysa and sysb and sysa != sysb)
        new_families.append({
            'new_family_id': f'N198-{i + 1:04d}',
            'key': {'a': A, 'b': B, 'pairs': [list(p) for p in pairs],
                    'join_type': jt, 'preserve': preserve, 'self_join': self_join},
            'endpoints': ends, 'cross_system': cross_system,
            'evidence': {'templates': len(ths), 'statements': len(stmts), 'files': files[:12],
                         'stmt_ids_sample': [sid for _, sid in stmts[:30]]},
            'member_groups': [{'th': g['th'], 'block': g['block'], 'and_group': g['and_group'],
                               'raws': [m['e'].get('raw', '')[:120] for m in g['members'][:4]]}
                              for g in gs[:25]],
        })

    # ---------- 3) 平台严格查重 ----------
    plat_idx = collections.defaultdict(list)
    for r in plat['relations']:
        fa, fb = split_cols(r['from_columns']), split_cols(r['to_columns'])
        a = ((r['from_system_code'] or ''), (r['from_schema_name'] or ''), norm_table(r['from_table_name']), fa)
        b = ((r['to_system_code'] or ''), (r['to_schema_name'] or ''), norm_table(r['to_table_name']), fb)
        plat_idx[tuple(sorted([a, b]))].append(r)
    plat_by_id = {r['id']: r for r in plat['relations']}

    for f in new_families:
        A, B = f['key']['a'], f['key']['b']
        pairs = {tuple(p) for p in f['key']['pairs']}
        matches = []
        for tag, tbl in (('a', A), ('b', B)):
            pass
        # 平台身份以 (system,schema,bare) 组合枚举新族候选身份（歧义=多组合）
        combos = []
        for ea, eb in _identity_combos(f):
            fa = tuple(p[0] for p in sorted(pairs))
            fb = tuple(p[1] for p in sorted(pairs))
            a = (ea['system'] or '', ea['schema'] or bare(A), norm_table(A), tuple(sorted(p[0] for p in pairs)))
            b = (eb['system'] or '', eb['schema'] or bare(B), norm_table(B), tuple(sorted(p[1] for p in pairs)))
            key = tuple(sorted([a, b]))
            for pr in plat_idx.get(key, []):
                combos.append(pr)
        seen_ids = {}
        for pr in combos:
            seen_ids[pr['id']] = pr
        f['platform_matches'] = []
        for pid, pr in sorted(seen_ids.items()):
            pfa, pfb = split_cols(pr['from_columns']), split_cols(pr['to_columns'])
            plat_pairs = set(zip(pfa, pfb)) | {(y, x) for x, y in zip(pfa, pfb)}
            covers = pairs <= plat_pairs and pairs == {p for p in pairs if p in plat_pairs}
            f['platform_matches'].append({
                'id': pid, 'layer': pr.get('relation_layer'), 'system': pr['from_system_code'],
                'identity': f"{pr['from_schema_name']}.{pr['from_table_name']}({','.join(pfa)})~"
                            f"{pr['to_schema_name']}.{pr['to_table_name']}({','.join(pfb)})",
                'covers_all_columns': pairs <= plat_pairs,
            })
        full = [m for m in f['platform_matches'] if m['covers_all_columns'] and m['layer'] == 'formal']
        full_any = [m for m in f['platform_matches'] if m['covers_all_columns']]
        partial = [m for m in f['platform_matches'] if not m['covers_all_columns']]
        # intake 判定（严格规则）
        if f['cross_system']:
            state = 'candidate_d_crosssource'
        elif full_any:
            state = 'existing_supplement'
        elif full:
            state = 'existing_supplement'
        elif partial:
            state = 'partial'
        elif any(e['status'] in ('unknown_object', 'owner_unknown_schema') for e in f['endpoints'].values()):
            state = 'candidate_blocked_source'
        else:
            state = 'candidate'
        f['intake_state'] = state

    # ---------- 4) 旧 405 族映射 ----------
    def old_key(r):
        ea, eb = r['endpoints'].get('a'), r['endpoints'].get('b')
        A, B = bare(ea['table']), bare(eb['table'])
        cols_a = tuple(c.upper() for c in ea['columns'])
        cols_b = tuple(c.upper() for c in eb['columns'])
        pair_sorted = tuple(sorted(zip(cols_a, cols_b)))
        return A, B, pair_sorted

    # 跨旧族匹配按裸表名归一（新族保留 owner 前缀身份，schema 在端点身份中单独比对）
    new_by_pair = collections.defaultdict(list)
    for f in new_families:
        A, B = bare(f['key']['a']), bare(f['key']['b'])
        P = tuple(sorted(tuple(p) for p in f['key']['pairs']))
        new_by_pair[tuple(sorted([A, B])) + (P,)].append(f)
    new_by_tables = collections.defaultdict(list)
    for f in new_families:
        new_by_tables[tuple(sorted([bare(f['key']['a']), bare(f['key']['b'])]))].append(f)

    old_to_new = []
    for r in old_rels:
        A, B, P = old_key(r)
        exact = new_by_pair.get(tuple(sorted([A, B])) + (P,), [])
        # 旧族 cols 无序（作为集合），尝试集合匹配
        if not exact:
            cand = [f for f in new_by_tables.get(tuple(sorted([A, B])), [])
                    if {tuple(p) for p in f['key']['pairs']} == {p for p in P}]
            exact = cand
        if exact:
            status = 'mapped'
            note = ''
        else:
            tbl_only = new_by_tables.get(tuple(sorted([A, B])), [])
            if tbl_only:
                status, note = 'columns_changed', '同表对但列集变化（复合键拆分/合并或解析修正）'
            else:
                status, note = 'dropped_by_reparse', '新解析下该表对无等值边（旧边为解析缺陷产物或语句未再命中）'
        old_to_new.append({
            'old_relation_id': r['relation_id'], 'old_state': r['intake_state'],
            'old_validation': r['validation_state'], 'old_key': [A, B, [list(p) for p in P]],
            'new_family_ids': [f['new_family_id'] for f in exact],
            'mapping_status': status, 'note': note,
        })

    # ---------- 5) 输出 ----------
    state_counts = collections.Counter(f['intake_state'] for f in new_families)
    map_counts = collections.Counter(m['mapping_status'] for m in old_to_new)
    summary = {
        'new_families': len(new_families), 'state_counts': dict(state_counts),
        'groups_total': len(groups), 'derived_pending_edges': len(derived_pending),
        'old_families_mapped': dict(map_counts),
        'self_join_families': sum(1 for f in new_families if f['key']['self_join']),
        'mixed_join_families': sum(1 for f in new_families if f['key']['join_type'] == 'mixed'),
        'outer_families': sum(1 for f in new_families if f['key']['join_type'] in ('left', 'right', 'full')),
        'ambiguous_endpoint_families': sum(1 for f in new_families
                                           if any(e['status'] == 'ambiguous' for e in f['endpoints'].values())),
        'existing_with_full_coverage': sum(1 for f in new_families
                                           if f['intake_state'] == 'existing_supplement'),
    }
    (OUT / 'b3_new_families.json').write_text(json.dumps(new_families, ensure_ascii=False, indent=1), encoding='utf-8')
    (OUT / 'old_to_new_relations.json').write_text(json.dumps(old_to_new, ensure_ascii=False, indent=1), encoding='utf-8')
    (OUT / 'b3_derived_pending.json').write_text(json.dumps(derived_pending[:400], ensure_ascii=False, indent=1), encoding='utf-8')
    diff = {
        'summary': summary,
        'old_state_vs_new': _old_vs_new(old_rels, old_to_new, new_families),
    }
    (OUT / 'correction_diff.json').write_text(json.dumps(diff, ensure_ascii=False, indent=1), encoding='utf-8')
    (OUT / 'b3_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def _identity_combos(f):
    """新族端点身份组合（歧义端点展开为全部候选，cap 4×4）。"""
    def opts(e):
        if e['status'] in ('owner_resolved', 'unique'):
            return [{'system': e['system'], 'schema': e['schema']}]
        if e['status'] == 'ambiguous':
            return [{'system': c['system'], 'schema': c['schema']} for c in e['candidates'][:4]]
        return [{'system': None, 'schema': None}]
    for ea in opts(f['endpoints']['a']):
        for eb in opts(f['endpoints']['b']):
            yield ea, eb


def _old_vs_new(old_rels, old_to_new, new_families):
    by_id = {f['new_family_id']: f for f in new_families}
    cross = collections.Counter()
    for m in old_to_new:
        for nf in m['new_family_ids']:
            f = by_id[nf]
            cross[(m['old_state'], f['intake_state'])] += 1
    return {f'{a}->{b}': c for (a, b), c in sorted(cross.items())}


if __name__ == '__main__':
    main()
