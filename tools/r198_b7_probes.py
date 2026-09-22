# -*- coding: utf-8 -*-
"""r198 B7-①：执行 probe_package_v2 24 条（用户 2026-09-22 会话批准）。
通道：sjzc live 受控连接器（8.83 平台连接器只读+超时+大表门禁，与 197 S6 同通道同语义）。
逐条记录 uid/sql_sha1/elapsed/status/rows；结果写 validation_results_v2.jsonl。"""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '开发起步包/output_r198/r198-20260922-remediation'
SJZC = r'C:\Users\Administrator\.zcode\skills\sjzc\scripts\sjzc_query.py'


def run_probe(source, sql, timeout_hint):
    t0 = time.time()
    try:
        proc = subprocess.run(
            [sys.executable, SJZC, 'live', source, '--sql', sql, '--max-rows', '50'],
            capture_output=True, text=True, encoding='utf-8', timeout=timeout_hint)
        elapsed = round(time.time() - t0, 1)
        out = proc.stdout.strip()
        return {'rc': proc.returncode, 'elapsed_s': elapsed, 'stdout': out, 'stderr': proc.stderr.strip()[-400:]}
    except subprocess.TimeoutExpired:
        return {'rc': -9, 'elapsed_s': round(time.time() - t0, 1), 'stdout': '', 'stderr': 'client_timeout'}


def main():
    pkg = json.loads((OUT / 'probe_package_v2.json').read_text(encoding='utf-8'))
    results = []
    for pr in pkg['probes']:
        sha = hashlib.sha1(pr['sql'].encode('utf-8')).hexdigest()
        # 哈希一致性守卫：包内声明哈希 vs 当前 SQL
        hash_ok = (not pr.get('sql_sha1')) or pr['sql_sha1'] == sha
        r = run_probe(pr['source_code'], pr['sql'], 90)
        rec = {'uid': pr['uid'], 'kind': pr.get('kind'), 'purpose': pr['purpose'],
               'source_code': pr['source_code'], 'sql_sha1': sha, 'hash_matches_package': hash_ok,
               'elapsed_s': r['elapsed_s'], 'status': 'executed' if r['rc'] == 0 else 'failed',
               'rc': r['rc'], 'output': r['stdout'][:4000], 'error': r['stderr'] if r['rc'] else None}
        results.append(rec)
        print(f"{pr['uid']} rc={r['rc']} {r['elapsed_s']}s hash_ok={hash_ok}", flush=True)
    with (OUT / 'validation_results_v2.jsonl').open('w', encoding='utf-8') as f:
        for rec in results:
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')
    ok = sum(1 for r in results if r['status'] == 'executed')
    print(f"executed {ok}/{len(results)}")


if __name__ == '__main__':
    main()
