"""Read-only audit of r197 artifacts; writes only this audit directory."""
from pathlib import Path
import ast
import collections
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[3]
RUN = ROOT / '开发起步包/output_r197/r197-20260921-s1'
OUT = Path(__file__).parent

def read(name):
    path = RUN / name
    if name.endswith('.jsonl'):
        return [json.loads(s) for s in path.read_text(encoding='utf-8').splitlines() if s.strip()]
    return json.loads(path.read_text(encoding='utf-8'))

def main():
    rels = read('relations.jsonl')
    payload = read('import_payload.json')['rows']
    probes = read('probe_package.json')['probes']
    results = read('validation_results.jsonl')
    imported = {r['relation_id'] for r in payload}
    # Necessary, not sufficient, endpoint coverage: even full token coverage
    # here does not prove paired-column/source/condition equivalence.
    weak = []
    for r in rels:
        if r['intake_state'] != 'existing_supplement':
            continue
        required = {(e['table'].split('.')[-1], c) for e in r['endpoints'].values() for c in e['columns']}
        matches = r['dedup'].get('platform_formal_matches', [])
        covered = any(required <= {tuple(v) for v in m.get('shared_pairs', [])} for m in matches)
        if not covered:
            weak.append({'relation_id': r['relation_id'], 'endpoints': sorted(required), 'match_ids': [m.get('id',m.get('plat_id')) for m in matches]})
    statement_sets = {}
    for s in ('s2','s3','s4','s5'):
        rows = read(s+'_workset.jsonl')
        statement_sets[s] = {r['stmt_id'] for r in rows}
    union = set.union(*statement_sets.values())
    overlap = [{'a':a,'b':b,'count':len(statement_sets[a]&statement_sets[b])} for a in statement_sets for b in statement_sets if a<b and statement_sets[a]&statement_sets[b]]
    defs = ast.parse((ROOT/'_scratch/r197_s2_parse.py').read_text(encoding='utf-8-sig'))
    allowed = {'IDENT','KW_STOP','EQ_RE','COL_CONST_RE'}
    nodes = [n for n in defs.body if isinstance(n,(ast.Import,ast.ImportFrom,ast.FunctionDef)) or isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in allowed for t in n.targets)]
    ns = {}
    exec(compile(ast.Module(body=nodes,type_ignores=[]),'audited_parse_functions','exec'), ns)
    fam = ast.parse((ROOT/'_scratch/r197_s2_family.py').read_text(encoding='utf-8-sig'))
    fun = next(n for n in fam.body if isinstance(n,ast.FunctionDef) and n.name=='composite_merge')
    exec(compile(ast.Module(body=[fun],type_ignores=[]),'audited_merge_function','exec'),ns)
    cases = {
        'left_join': 'SELECT a.id FROM T_A a LEFT JOIN T_B b ON a.id=b.id',
        'or_keys': 'SELECT a.id FROM T_A a, T_B b WHERE a.id=b.id OR a.alt=b.alt',
        'self_join': 'SELECT a.id FROM T_A a,T_A b WHERE a.parent_id=b.id',
        'subquery_scope': 'SELECT (SELECT COUNT(*) FROM T_B b WHERE b.x=a.x) FROM T_A a WHERE EXISTS (SELECT 1 FROM T_B b WHERE b.y=a.y)',
        'inner_control': 'SELECT a.id FROM T_A a JOIN T_B b ON a.id=b.id',
    }
    synthetic=[]
    for name,sql in cases.items():
        parsed=ns['parse_template'](sql)
        edges=parsed['edges']
        for i,e in enumerate(edges): e['raw_pos']=i
        synthetic.append({'case':name,'sql':sql,'edges':edges,'groups':ns['composite_merge'](edges)})
    records={r['uid'] for r in results}; packed={r['uid'] for r in probes}
    summary={
        'relation_counts':dict(collections.Counter(r['intake_state'] for r in rels)),
        'validation_counts':dict(collections.Counter(r['validation_state'] for r in rels)),
        'import_rows':len(payload),
        'import_missing_source_code':sum(not r.get('from_source_code') or not r.get('to_source_code') for r in payload),
        'import_missing_validation_status':sum('validation_status' not in r for r in payload),
        'weak_existing_count':len(weak),'weak_existing':weak,
        'workset_unique_counts':{s:len(v) for s,v in statement_sets.items()},
        'workset_union':len(union),'cross_stage_overlap':overlap,
        'probe_package_count':len(probes),'result_count':len(results),
        'results_missing_from_probe_package':sorted(records-packed),
        'synthetic_parser_reproductions':synthetic,
        'passed_imported':[{k:r.get(k) for k in ('relation_id','validation_note','validation_evidence_uids')} | {'endpoints':r['endpoints']} for r in rels if r['relation_id'] in imported and r['validation_state']=='passed_in_scope'],
    }
    (OUT/'local_audit.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k not in ('weak_existing','synthetic_parser_reproductions','passed_imported')},ensure_ascii=False,indent=2))
    for c in synthetic: print(c['case'],json.dumps(c['groups'],ensure_ascii=False))

if __name__=='__main__':
    main()
