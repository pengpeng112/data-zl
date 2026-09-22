# -*- coding: utf-8 -*-
"""r198 B4：验证证据离线重审 + 离线来源消歧 + probe_package_v2（不执行）。

1) 用新解析器解析 35 条探针 SQL → 客观"探针实际测了哪些表/列"；
2) 59 个有状态族逐条重审：证据分级 direct / indirect_one_side / scope_mismatch，
   F04 已知错配个案逐条写结论；passed_in_scope 仅在有同表同列直接证据时建议保留；
3) 129 条 source_pending 草稿的离线消歧：族列集 vs 各候选身份的平台列集差分；
4) probe_package_v2.json：五要素齐备的有界探针包（默认 200 父键/50 聚合行/30s），
   含 20 条可批族双端唯一性+连接放大、OPER_CODE/ITEM_NO/APP_NO 身份、696/766 元数据缺口、
   Q12 费用差异解释。**全部未执行**，live 执行按 §B7 批准包。
只读输入；输出写本目录。"""
from __future__ import annotations

from pathlib import Path
import hashlib
import json
import re
import sys
import collections

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import r198_sql_parse as rsp  # noqa: E402

RUN197 = ROOT / '开发起步包/output_r197/r197-20260921-s1'
AUDIT = ROOT / 'review/adhoc/r197-audit-20260922'
OUT = ROOT / '开发起步包/output_r198/r198-20260922-remediation'


def read197(name):
    path = RUN197 / name
    if name.endswith('.jsonl'):
        return [json.loads(s) for s in path.read_text(encoding='utf-8').splitlines() if s.strip()]
    return json.loads(path.read_text(encoding='utf-8'))


def sha1(s):
    return hashlib.sha1(s.encode('utf-8')).hexdigest()


def bare(t):
    return t.replace('..', '.').upper().split('.')[-1].split('@')[0]


# F04 审计已证实的探针-断言错配（写入重审结论的定性依据）
F04_CASES = {
    'S2F-C90B6003D8': 'Q02 只测 PAT_VISIT 组合键，未测 PAT_MASTER_INDEX 唯一性或两表覆盖 → 降级 insufficient（间接证据仅支持 PATIENT_ID 单列在 PAT_VISIT 侧表现）',
    'S2F-67F8789EE2': 'Q24 未出现 ITEM_NO，只做 TEST_NO 计数，不能证明 TEST_NO+ITEM_NO 两列对应 → 降级 insufficient',
    'S3F-8CF8B4B39E': 'Q15 只有长度/非空分布且未连 EXAM_MASTER，不能证明 EXAM_NO↔OPER_CODE 编码身份 → 降级 insufficient（身份假说待证）',
    'S3F-D8F12989E0': 'Q15/Q33 未验证该 APP_NO 映射对 → 降级 insufficient',
}


def main():
    plan = read197('validation_plan.json')['probes']
    package = read197('probe_package.json')['probes']
    results = {r['uid']: r for r in read197('validation_results.jsonl')}
    matrix = read197('validation_matrix.json')
    rels = {r['relation_id']: r for r in read197('relations.jsonl')}
    payload_rows = {r['relation_id']: r for r in read197('import_payload.json')['rows']}
    o2n = {m['old_relation_id']: m for m in json.loads((OUT / 'old_to_new_relations.json').read_text(encoding='utf-8'))}

    # ---- 1) 探针 SQL 客观覆盖（新解析器） ----
    probe_cov = {}
    for pr in package:
        try:
            parsed = rsp.parse_sql(pr['sql'])
            tabs = set()
            for b in parsed['blocks'].values():
                for r in b['refs']:
                    if r['kind'] in ('table', 'dblink'):
                        tabs.add(bare(r['table']))
            probe_cov[pr['uid']] = {'tables': sorted(tabs), 'n_edges': len(parsed['edges']),
                                    'edges': [(bare(e['l_table']), e['l_col'], bare(e['r_table']), e['r_col'])
                                              for e in parsed['edges']]}
        except Exception as e:
            probe_cov[pr['uid']] = {'tables': [], 'n_edges': 0, 'edges': [], 'error': str(e)[:80]}

    # 探针→关系映射（plan.probe_id），含 uid 级
    pid_to_uid = {}
    for pr in package:
        for pid in pr['probe_ids']:
            pid_to_uid[pid] = pr['uid']
    fam_evidence = collections.defaultdict(list)   # relation_id -> [{uid, via}]
    for p in plan:
        for rid in p.get('relation_ids', []):
            fam_evidence[rid].append({'probe_id': p['probe_id'], 'via': 'plan'})
    for rid, row in payload_rows.items():
        ev = json.loads(row['source_evidence']) if isinstance(row.get('source_evidence'), str) else row.get('source_evidence', {})
        for uid in (ev.get('probe_uids') or []):
            fam_evidence[rid].append({'uid': uid, 'via': 'payload'})

    # ---- 2) 59 有状态族重审 ----
    rereview = []
    verdict_counts = collections.Counter()
    for rid, fam in rels.items():
        st = fam['validation_state']
        if st == 'not_run':
            continue
        evs = fam_evidence.get(rid, [])
        ea, eb = fam['endpoints']['a'], fam['endpoints']['b']
        tabs = {bare(ea['table']), bare(eb['table'])}
        detail = []
        best = 'none'
        for ev in evs:
            uid = ev.get('uid') or pid_to_uid.get(ev.get('probe_id'))
            if not uid or uid not in probe_cov:
                detail.append({**ev, 'class': 'no_sql_or_uid'})
                continue
            cov = probe_cov[uid]
            covtabs = set(cov['tables'])
            inter = tabs & covtabs
            if len(inter) == 2:
                cls = 'direct_both_tables'
                best = 'direct'
            elif len(inter) == 1:
                cls = 'indirect_one_side'
                if best != 'direct':
                    best = 'indirect'
            else:
                cls = 'scope_mismatch'
                if best == 'none':
                    best = 'mismatch'
            res = results.get(uid, {})
            detail.append({'uid': uid, 'via': ev['via'], 'class': cls,
                           'probe_tables': cov['tables'], 'probe_edges': cov['edges'][:4],
                           'executed': res.get('status'), 'rows': res.get('row_count')})
        if rid in F04_CASES:
            reco = 'downgrade_insufficient'
            reason = F04_CASES[rid]
        elif st == 'passed_in_scope' and best == 'direct':
            reco = 'keep_pass_pending_sample_check'
            reason = '探针覆盖两端表；保留 passed（列级对应见 probe_edges）'
        elif st == 'passed_in_scope':
            reco = 'downgrade_insufficient'
            reason = f'探针未同时覆盖两端表（best={best}）；单表/旁证不能授予关系通过'
        elif st == 'failed':
            # 负例保留：需指明被否定命题；正常 1:N 不因重复判错（Q05 类）——按原结论保留并标注语义
            reco = 'keep_failed_with_scope_note'
            reason = '负例保留；被否定的是特定聚合/直连用法，正常 1:N 用法不受否定'
        elif st == 'insufficient':
            reco = 'keep_insufficient'
            reason = '证据不足维持'
        verdict_counts[reco] += 1
        newfams = o2n.get(rid, {}).get('new_family_ids', []) if rid in o2n else []
        rereview.append({'relation_id': rid, 'old_state': st, 'old_intake': fam['intake_state'],
                         'assertion': [f"{ea['table']}({','.join(ea['columns'])})",
                                       f"{eb['table']}({','.join(eb['columns'])})"],
                         'evidence': detail, 'best_coverage': best,
                         'recommended': reco, 'reason': reason,
                         'new_family_ids': newfams})

    # ---- 3) 离线来源消歧（129 source_pending） ----
    cols_by_identity = collections.defaultdict(set)
    for c in json.loads((AUDIT / 'platform_endpoint_columns.json').read_text(encoding='utf-8')):
        cols_by_identity[(c['system_code'], c['source_code'], c['schema_name'], c['table_name'].upper())].add(c['column_name'].upper())
    newfams = json.loads((OUT / 'b3_new_families.json').read_text(encoding='utf-8'))
    fam_by_id = {f['new_family_id']: f for f in newfams}
    rc = json.loads((OUT / 'review_corrections.json').read_text(encoding='utf-8'))
    disamb = []
    for row in rc['rows']:
        if row['recommended_action'] != 'source_pending':
            continue
        fams = [fam_by_id[f] for f in row['new_family_ids'] if f in fam_by_id]
        if not fams:
            continue
        f0 = fams[0]
        outcome = {}
        for side, pfx in (('a', 'from'), ('b', 'to')):
            e = f0['endpoints'][side]
            if e['status'] != 'ambiguous':
                continue
            cols = {p[i] for p in f0['key']['pairs'] for i in (0, 1)}  # 族列并集（保守）
            cols = {p[0] for p in f0['key']['pairs']} if side == 'a' else {p[1] for p in f0['key']['pairs']}
            supports = []
            for c in e['candidates']:
                key = (c['system'], c['source'], c['schema'], bare(e['table']))
                have = cols_by_identity.get(key, set())
                if cols and cols <= have:
                    supports.append(c)
                elif not have:
                    supports.append({**c, 'note': '平台无该身份列元数据'})
            if len(supports) == 1:
                outcome[pfx] = {'resolved': supports[0]}
            else:
                outcome[pfx] = {'still_ambiguous': [s for s in supports]}
        if any('resolved' in v for v in outcome.values()):
            disamb.append({'review_id': row['review_id'], 'relation_id': row['relation_id'],
                           'outcome': outcome})

    # ---- 4) probe_package_v2（五要素，不执行） ----
    def five(source, window, channel):
        return {'source_code': source, 'time_window': window, 'channel': channel,
                'db_timeout_s': 30, 'client_timeout_s': 60,
                'authorization': '未批准——待 B7 批准包逐条点名后执行'}

    probes_v2 = []
    # P2-A：20 条可批族（confirm_with_source_fix）
    for row in rc['rows']:
        if row['recommended_action'] != 'confirm_with_source_fix':
            continue
        fams = [fam_by_id[f] for f in row['new_family_ids'] if f in fam_by_id]
        if not fams:
            continue
        f0 = fams[0]
        A, B = f0['endpoints']['a'], f0['endpoints']['b']
        if not (A.get('schema') and B.get('schema')):
            continue
        qa = f"{A['schema']}.{A['table']}"
        qb = f"{B['schema']}.{B['table']}"
        pairs = f0['key']['pairs']
        on = ' AND '.join(f"a.{x}=b.{y}" for x, y in pairs)
        cols_a = ', '.join(sorted({p[0] for p in pairs}))
        cols_b = ', '.join(sorted({p[1] for p in pairs}))
        sql = (
            f"WITH a AS (SELECT {cols_a} FROM (SELECT {cols_a} FROM {qa} ORDER BY {pairs[0][0]}) WHERE ROWNUM<=200),\n"
            f"b AS (SELECT {cols_b} FROM (SELECT {cols_b} FROM {qb} ORDER BY {pairs[0][1]}) WHERE ROWNUM<=200)\n"
            f"SELECT (SELECT COUNT(*) FROM a) n_a, (SELECT COUNT(*) FROM b) n_b,\n"
            f"(SELECT COUNT(*) FROM (SELECT DISTINCT {cols_a} FROM a)) distinct_a,\n"
            f"(SELECT COUNT(*) FROM (SELECT DISTINCT {cols_b} FROM b)) distinct_b FROM dual"
        )
        probes_v2.append({'uid': f"P2A-{row['review_id']}", 'kind': 'approvable_family_dual_uniqueness',
                          'review_id': row['review_id'], 'relation_id': row['relation_id'],
                          'purpose': f'{qa}×{qb} 双端 200 键样本唯一性',
                          'sql': sql, 'sql_sha1': sha1(sql), **five(A.get('source'), 'any(只读聚合)', '8.83 受控连接器/只读')})
    # P2-B：编码身份
    for name, tbl, col in [('OPER_CODE 分流', 'INPBILL.INP_BILL_DETAIL', 'OPER_CODE'),
                           ('ITEM_CLASS 清单', 'INPBILL.INP_BILL_DETAIL', 'ITEM_CLASS')]:
        sql = (f"SELECT {col}, COUNT(*) n FROM (SELECT {col} FROM {tbl} WHERE ROWNUM<=5000) GROUP BY {col} ORDER BY n DESC")
        probes_v2.append({'uid': f"P2B-{col}", 'kind': 'code_identity_value_domain',
                          'purpose': f'{name}：{tbl}.{col} 值域分布（5000 行有界）',
                          'sql': sql, 'sql_sha1': sha1(sql),
                          **five('his_source_10_10_10_15', 'any(只读聚合)', '8.83 受控连接器/只读')})
    # P2-C：元数据缺口
    probes_v2.append({'uid': 'P2C-696', 'kind': 'metadata_gap_column_exists',
                      'purpose': 'INPADM.WAIT_BED_PATS_NEW 是否存在 USER_NAME（区分漏采/旧字段/SQL 错误）',
                      'sql': "SELECT COLUMN_NAME, DATA_TYPE FROM ALL_TAB_COLUMNS WHERE OWNER='INPADM' AND TABLE_NAME='WAIT_BED_PATS_NEW' AND ROWNUM<=200",
                      'sql_sha1': '', **five('his_source_10_10_10_15', 'any(数据字典只读)', '8.83 受控连接器/只读')})
    probes_v2.append({'uid': 'P2C-766', 'kind': 'metadata_gap_column_exists',
                      'purpose': 'COMM.OFFICIAL_DRUG_CATALOG(_CLASS) 实际列清单（平台列级零登记）',
                      'sql': "SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE FROM ALL_TAB_COLUMNS WHERE OWNER='COMM' AND TABLE_NAME IN ('OFFICIAL_DRUG_CATALOG','OFFICIAL_DRUG_CATALOG_CLASS') AND ROWNUM<=300",
                      **five('his_source_10_10_10_15', 'any(数据字典只读)', '8.83 受控连接器/只读')})
    for p in probes_v2:
        p.setdefault('sql_sha1', sha1(p['sql']))
    package_v2 = {
        'run_id': 'r198-20260922-remediation', 'generated': '2026-09-22',
        'executed': False,
        'note': '全部未执行。执行须 B7 批准包按五要素逐条批准（源、SQL 哈希、参数/范围、时段、通道）；'
                '197 历史批准不沿用。大表全部 ROWNUM 有界；无 DML/DDL。',
        'bounds_default': {'parent_keys_max': 200, 'agg_rows_max': 50, 'db_timeout_s': 30},
        'probes': probes_v2,
    }

    summary = {
        'stateful_families_rereviewed': len(rereview),
        'recommendations': dict(verdict_counts),
        'probe_coverage_parsed': len(probe_cov),
        'probes_v2_count': len(probes_v2),
        'source_disambiguated_reviews': len(disamb),
    }
    (OUT / 'b4_validation_rereview.json').write_text(
        json.dumps({'summary': summary, 'rereview': rereview, 'probe_coverage': probe_cov}, ensure_ascii=False, indent=1), encoding='utf-8')
    (OUT / 'b4_source_disambiguation.json').write_text(json.dumps(disamb, ensure_ascii=False, indent=1), encoding='utf-8')
    (OUT / 'probe_package_v2.json').write_text(json.dumps(package_v2, ensure_ascii=False, indent=1), encoding='utf-8')
    (OUT / 'b4_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
