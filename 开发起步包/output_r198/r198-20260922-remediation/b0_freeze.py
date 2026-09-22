# -*- coding: utf-8 -*-
"""B0 冻结基线：只读核对 197 产物/脚本/审计证据哈希，登记 405 族、167 草稿、13 配方、
34 值域、git 与他人域基线。不修改任何 197 原始文件，不连业务源库。"""
from pathlib import Path
import hashlib
import json
import subprocess
import collections

ROOT = Path(__file__).resolve().parents[3]
RUN197 = ROOT / '开发起步包/output_r197/r197-20260921-s1'
AUDIT = ROOT / 'review/adhoc/r197-audit-20260922'
OUT = Path(__file__).parent


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def read197(name):
    path = RUN197 / name
    if name.endswith('.jsonl'):
        return [json.loads(s) for s in path.read_text(encoding='utf-8').splitlines() if s.strip()]
    return json.loads(path.read_text(encoding='utf-8'))


def main():
    baseline = {'run_id': 'r198-20260922-remediation', 'frozen_at': '2026-09-22', 'purpose': '198 B0 基线冻结'}

    # 1) manifest 63 项哈希复核
    manifest = read197('manifest.json')
    art = manifest['artifacts']
    same, changed, missing = [], [], []
    for rel, expect in art.items():
        p = RUN197 / rel
        want = expect['sha256'] if isinstance(expect, dict) else expect
        if not p.exists():
            missing.append(rel)
        elif sha256(p) == want:
            same.append(rel)
        else:
            changed.append(rel)
    baseline['manifest_check'] = {'total': len(art), 'same': len(same), 'changed': changed, 'missing': missing}

    # 2) 405 族冻结（id + 三态 + join_type + endpoints 物理）
    rels = read197('relations.jsonl')
    baseline['families'] = {
        'count': len(rels),
        'by_state': dict(collections.Counter(r['intake_state'] for r in rels)),
        'validation_states': dict(collections.Counter(r['validation_state'] for r in rels)),
        'records': [
            {
                'relation_id': r['relation_id'],
                'stage': r['stage'],
                'intake_state': r['intake_state'],
                'validation_state': r['validation_state'],
                'join_type': r.get('join_type'),
                'endpoints': r.get('endpoints'),
                'content_sha256': hashlib.sha256(json.dumps(r, ensure_ascii=False, sort_keys=True).encode()).hexdigest(),
            }
            for r in rels
        ],
    }

    # 3) 167 导入行冻结 + review_id 映射（675-841 连续，按导入顺序；B1 以 insert SQL 复核）
    payload = read197('import_payload.json')
    rows = payload['rows']
    baseline['import_payload'] = {
        'count': len(rows),
        'rows_sha256': hashlib.sha256(json.dumps(rows, ensure_ascii=False, sort_keys=True).encode()).hexdigest(),
        'row_hashes': [hashlib.sha256(json.dumps(r, ensure_ascii=False, sort_keys=True).encode()).hexdigest() for r in rows],
        'assumed_review_ids': list(range(675, 675 + len(rows))),
    }

    # 4) 13 配方与 34 值域自然键冻结（来自审计回读）
    pr = json.loads((AUDIT / 'platform_readback.json').read_text(encoding='utf-8'))
    baseline['recipes_197_payload'] = read197('recipe_payload.json')
    baseline['platform_readback_20260922'] = {
        'reviews': {
            'count': len(pr['reviews']),
            'ids': [r['id'] for r in pr['reviews']],
            'all_draft': all(r['review_status'] == 'draft' for r in pr['reviews']),
            'all_missing_both_source': all(not r['from_source_code'] or not r['to_source_code'] for r in pr['reviews']),
            'validation_states': sorted({r['validation_status'] for r in pr['reviews'] if r['validation_status']}),
        },
        'recipes': [
            {'recipe_id': r['recipe_id'], 'status': r['status'], 'is_active': r['is_active'], 'content_hash': r['content_hash']}
            for r in pr['recipes']
        ],
        'domains': [
            {
                'id': d['id'], 'system_code': d['system_code'], 'source_code': d['source_code'],
                'schema_name': d['schema_name'], 'table_name': d['table_name'],
                'column_name': d['column_name'], 'code': d['code'], 'meaning': d['meaning'],
                'status': d['status'], 'domain_kind': d['domain_kind'], 'note': d['note'],
                'current_version_id': d['current_version_id'], 'evidence_count': d['evidence_count'],
                'row_sha256': hashlib.sha256(json.dumps(d, ensure_ascii=False, sort_keys=True).encode()).hexdigest(),
            }
            for d in pr['domains']
        ],
    }

    # 5) 生成脚本与审计证据哈希
    scripts = {}
    for p in sorted((ROOT / '_scratch').glob('r197*.py')):
        scripts[str(p.relative_to(ROOT)).replace('\\', '/')] = sha256(p)
    evidence = {}
    for p in sorted(AUDIT.iterdir()):
        if p.is_file():
            evidence[str(p.relative_to(ROOT)).replace('\\', '/')] = sha256(p)
    baseline['r197_scripts_sha256'] = scripts
    baseline['audit_evidence_sha256'] = evidence

    # 6) git 基线
    head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    branch = subprocess.run(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    baseline['git'] = {'head': head, 'branch': branch,
                       'note': '工作区含 197/198/199 文档与 output_r199 等未提交变更，属既有状态，本任务不触碰无关变更'}

    # 7) 他人域 13 文件基线核对
    dom_expect = json.loads((AUDIT / 'domain_baseline.json').read_text(encoding='utf-8'))
    dom_now, dom_diff = {}, []
    for rel, expect in dom_expect.items():
        actual = sha256(ROOT / rel)
        dom_now[rel] = actual
        if actual != expect:
            dom_diff.append(rel)
    baseline['domain_check'] = {'files': len(dom_expect), 'diff_vs_audit': dom_diff}

    (OUT / 'b0_baseline.json').write_text(json.dumps(baseline, ensure_ascii=False, indent=2), encoding='utf-8')
    summary = {k: baseline[k] for k in ('run_id', 'manifest_check')}
    summary['families'] = {k: v for k, v in baseline['families'].items() if k != 'records'}
    summary['import_payload'] = {k: v for k, v in baseline['import_payload'].items() if k != 'row_hashes'}
    summary['platform_readback_20260922'] = {
        'reviews': baseline['platform_readback_20260922']['reviews'],
        'recipes': len(baseline['platform_readback_20260922']['recipes']),
        'domains': len(baseline['platform_readback_20260922']['domains']),
    }
    summary['scripts'] = len(scripts)
    summary['domain_check'] = baseline['domain_check']
    (OUT / 'b0_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
