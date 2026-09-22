# -*- coding: utf-8 -*-
"""r198 B2：用作用域感知解析器重解析 s2—s5 全部模板，输出 b2_parsed_templates.jsonl
与新旧解析差异统计（自连接找回、LEFT 类型、OR 分支、作用域、动态标记细分）。
只读 197 工件；输出仅写本目录。"""
from pathlib import Path
import json
import re
import sys
import collections

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools'))
import r198_sql_parse as rsp  # noqa: E402

RUN197 = ROOT / '开发起步包/output_r197/r197-20260921-s1'
OUT = Path(__file__).parent


def read197(name):
    path = RUN197 / name
    if name.endswith('.jsonl'):
        return [json.loads(s) for s in path.read_text(encoding='utf-8').splitlines() if s.strip()]
    return json.loads(path.read_text(encoding='utf-8'))


def main():
    templates = {}
    for s in ('s2', 's3', 's4', 's5'):
        for t in read197(s + '_templates.jsonl'):
            templates.setdefault(t['template_hash'], t)
    out_rows = []
    stats = collections.Counter()
    left_join_templates, selfjoin_new, or_split_new, scope_fix_new = [], [], [], []
    for th, t in templates.items():
        txt = t['rep_text']
        try:
            parsed = rsp.parse_sql(txt)
        except Exception as e:  # 单条失败不阻断整体
            parsed = {'edges': [], 'unresolved': [{'raw': txt[:80], 'reason': f'parser-error:{type(e).__name__}'}],
                      'filters': [], 'warnings': ['exception'], 'blocks': {}, 'cte_defs': {}}
            stats['parse_exception'] += 1
        rec = {
            'template_hash': th, 'stage_src': t.get('rep_file'), 'rep_stmt_id': t.get('rep_stmt_id'),
            'flags': t.get('flags'), 'type': t.get('type'),
            'n_blocks': len(parsed['blocks']),
            'edges': parsed['edges'], 'unresolved': parsed['unresolved'],
            'filters_n': len(parsed['filters']), 'warnings': parsed['warnings'][:10],
        }
        out_rows.append(rec)
        if parsed['edges']:
            stats['tmpl_with_edges'] += 1
        if parsed['unresolved']:
            stats['tmpl_with_unresolved'] += 1
        if parsed['warnings']:
            stats['tmpl_with_warnings'] += 1
        # 显式 OUTER JOIN 模板清单（传播核对清单）
        jt = {e.get('join_type') for e in parsed['edges'] if e.get('join_type')}
        if jt & {'left', 'right', 'full'}:
            left_join_templates.append({'template_hash': th, 'join_types': sorted(jt),
                                        'n_edges': len(parsed['edges'])})
        # 自连接找回：同表双实例边
        for e in parsed['edges']:
            if e['l_table'] == e['r_table'] and e['l_instance'] != e['r_instance']:
                selfjoin_new.append({'template_hash': th, 'table': e['l_table'],
                                     'cols': [e['l_col'], e['r_col']]})
                break

    # ---- 新旧差异：与旧 parsed_templates 对比 ----
    old_edges = {}
    for s in ('s2', 's3', 's4', 's5'):
        for r in read197(s + '_parsed_templates.jsonl'):
            th = r['template_hash']
            olds = {(e['l'], e['lcol'], e['r'], e['rcol']) for e in r['parse']['edges']}
            old_edges.setdefault(th, set()).update(olds)
    new_edges = {r['template_hash']: {(e['l_table'], e['l_col'], e['r_table'], e['r_col'])
                                      for e in r['edges']} for r in out_rows}
    gained = collections.Counter()
    lost = collections.Counter()
    for th in set(old_edges) | set(new_edges):
        o, n = old_edges.get(th, set()), new_edges.get(th, set())
        for e in n - o:
            gained[e] += 1
        for e in o - n:
            lost[e] += 1

    # ---- 动态标记细分（F09/T08）：只区分"拼接文本"与"真正依赖运行参数" ----
    dyn_rows = []
    flag_keys = collections.Counter()
    for r in out_rows:
        for k, v in (r.get('flags') or {}).items():
            if v:
                flag_keys[k] += 1
        if any('dyn' in k for k in (r.get('flags') or {})):
            pass
    for th, t in templates.items():
        fl = t.get('flags') or {}
        if not any('dyn' in str(k).lower() for k in fl):
            continue
        txt = t['rep_text']
        has_concat = '||' in txt
        has_exec = bool(re.search(r'EXECUTE\s+IMMEDIATE|DBMS_SQL|PREPARE', txt, re.I))
        dyn_rows.append({'template_hash': th, 'flags': fl, 'has_concat': has_concat,
                         'has_exec': has_exec,
                         'class': ('runtime_exec' if has_exec else
                                   ('concat_only_parseable' if has_concat else 'flag_no_marker'))})

    summary = {
        'templates_total': len(templates),
        'stats': dict(stats),
        'explicit_outer_join_templates': len(left_join_templates),
        'left_join_list': left_join_templates[:60],
        'selfjoin_edges_recovered_templates': len(selfjoin_new),
        'selfjoin_sample': selfjoin_new[:40],
        'old_vs_new_edge_gained_top': gained.most_common(30),
        'old_vs_new_edge_lost_top': lost.most_common(30),
        'gained_total': sum(gained.values()),
        'lost_total': sum(lost.values()),
        'flag_keys': dict(flag_keys),
        'dynamic_flag_rows': len(dyn_rows),
        'dynamic_class_counts': dict(collections.Counter(d['class'] for d in dyn_rows)),
        'dynamic_rows': dyn_rows[:60],
    }
    with (OUT / 'b2_parsed_templates.jsonl').open('w', encoding='utf-8') as f:
        for r in out_rows:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    (OUT / 'b2_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in summary.items()
                      if k not in ('left_join_list', 'selfjoin_sample', 'dynamic_rows',
                                   'old_vs_new_edge_gained_top', 'old_vs_new_edge_lost_top')},
                     ensure_ascii=False, indent=2))
    print('gained top:', gained.most_common(10))
    print('lost top:', lost.most_common(10))


if __name__ == '__main__':
    main()
