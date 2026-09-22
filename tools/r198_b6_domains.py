# -*- coding: utf-8 -*-
"""r198 B6：34 值域证据整理修订 + 安全修订工具（默认 dry-run）+ 隔离预演。

修订原则（F07）：
- 保留观察事实与待证语义分离：OPER_CODE 等价断言降为"待证假说"；
- code 保真（含尾随空格变体，id=287 '一 '）；
- ITEM_CLASS 遗漏 E/F/G 三值按 Q15 观察补录为 pending（不 confirm）；
- 每条登记独立 evidence（观察时间/样本/来源探针），版本与审计经值域服务语义
  （next_version/evidence_row），不伪造。
- 更新仅按准确 id + before-hash，仍 pending；冲突报错保留，不批量重灌。

用法：
  python tools/r198_b6_domains.py --plan            # 生成修订计划（纯本地）
  python tools/r198_b6_domains.py --apply           # 应用到 APP_TEST_DB_URL（隔离库预演）
  python tools/r198_b6_domains.py --apply --prod    # 生产（须另行批准，本任务不执行）
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '开发起步包/output_r198/r198-20260922-remediation'
AUDIT = ROOT / 'review/adhoc/r197-audit-20260922'
BACKEND = ROOT / 'backend'

sys.path.insert(0, str(BACKEND))


def h(obj):
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def build_plan():
    readback = json.loads((AUDIT / 'platform_readback.json').read_text(encoding='utf-8'))
    domains = readback['domains']
    plan = []
    for d in domains:
        entry = {
            'id': d['id'],
            'natural_key': {'system_code': d['system_code'], 'source_code': d['source_code'],
                            'schema_name': d['schema_name'], 'table_name': d['table_name'],
                            'column_name': d['column_name'], 'code': d['code']},
            'before_row_sha256': h(d),
            'status_guard': 'pending',       # 仅仍 pending 才更新
            'revisions': {},
            'evidence_to_register': [],
        }
        note = d.get('note') or ''
        code, meaning = d['code'], d.get('meaning') or ''
        # 1) OPER_CODE 多义键：等价断言降级为待证假说
        if code == '多义键' and d['column_name'] == 'OPER_CODE':
            entry['revisions']['meaning'] = ('多义键（观察事实：不同 ITEM_CLASS 分组下非空率/长度分布不同，Q15）;'
                                             '待证假说：检查类=EXAM_NO、检验类=TEST_NO/APPOINT_NO、手术类=OPER_ID——'
                                             '未经同表同列验证，不得据此 JOIN')
            entry['revisions']['note'] = note + ' | r198:等价语义降级为待证假说（Q15 仅证长度/非空分布）'
            entry['evidence_to_register'].append(
                {'source_type': 'probe', 'ref': 'Q15',
                 'detail': 'OPER_CODE 按 ITEM_CLASS 分组非空/长度分布（2026-09-21 活库聚合，12 组）'})
        # 2) OPERATION_SCALE 尾随空格变体保真说明
        elif d['column_name'] == 'OPERATION_SCALE' and code.rstrip() != code:
            entry['revisions']['meaning'] = meaning + '（注意：带尾随空格变体，=\'一\' 过滤会漏数，需 trim 口径）'
            entry['evidence_to_register'].append(
                {'source_type': 'probe', 'ref': 'Q21',
                 'detail': f"OPERATION_SCALE×STOP_FLAG 分布：'{code}'(N=1) 为尾随空格变体（2026-09-21）"})
        elif d['column_name'] == 'OPERATION_SCALE':
            entry['evidence_to_register'].append(
                {'source_type': 'probe', 'ref': 'Q21', 'detail': f"OPERATION_SCALE×STOP_FLAG 分布含 '{code}'（2026-09-21）"})
        # 3) 通用：note 无 Q 引用的登记文件证据
        else:
            qref = 'Q15' if d['column_name'] == 'ITEM_CLASS' else None
            entry['evidence_to_register'].append(
                {'source_type': 'probe' if qref else 'sql_corpus',
                 'ref': qref or 'r197 语句语料',
                 'detail': '197 S6 活库观察/语料提取（2026-09-21）' if qref else '197 历史语句语料提取（2026-09-21）'})
        plan.append(entry)
    # 4) ITEM_CLASS 遗漏 E/F/G 补录（新增 pending，不在 34 内）
    for code_v, n, nonnull in [('E', 18330, 18330), ('F', None, None), ('G', None, None)]:
        plan.append({
            'new_row': True,
            'natural_key': {'system_code': 'HIS', 'source_code': 'his_source_10_10_10_15',
                            'schema_name': 'INPBILL', 'table_name': 'INP_BILL_DETAIL',
                            'column_name': 'ITEM_CLASS', 'code': code_v},
            'meaning': '收费项目分类（Q15 观察，含义待字典核）',
            'note': 'r198 补录：Q15 实测 12 类中的遗漏项（197 导入仅 9 类）；含义不按猜测定稿',
            'status': 'pending',
            'evidence_to_register': [
                {'source_type': 'probe', 'ref': 'Q15',
                 'detail': f'ITEM_CLASS 分组计数：{code_v} N={n or "?"}（2026-09-21；F/G 在 Q15 截断行，补证见 P2B-ITEM_CLASS）'}],
        })
    (OUT / 'b6_domain_revision_plan.json').write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps({'plan_entries': len(plan), 'updates': sum(1 for p in plan if not p.get('new_row')),
                      'new_rows': sum(1 for p in plan if p.get('new_row')),
                      'with_revisions': sum(1 for p in plan if p.get('revisions'))}, ensure_ascii=False))


def apply(plan_path, target_label):
    import os
    import sqlalchemy
    from app.services import value_domain_service as vds
    from app.models import AssetColumnValueDomain, AssetColumnValueDomainEvidence  # noqa
    url = os.environ['APP_TEST_DB_URL' if target_label != 'prod' else 'APP_DB_URL']
    eng = sqlalchemy.create_engine(url)
    plan = json.loads(Path(plan_path).read_text(encoding='utf-8'))
    report = {'target': target_label, 'updated': 0, 'evidence_inserted': 0, 'new_rows': 0,
              'conflicts': [], 'skipped_not_pending': []}
    Session = sqlalchemy.orm.sessionmaker(bind=eng)
    with Session() as db:
        for p in plan:
            if p.get('new_row'):
                exists = vds.find_by_key(db, system_code=p['natural_key']['system_code'],
                                         source_code=p['natural_key']['source_code'],
                                         schema_name=p['natural_key']['schema_name'],
                                         table_name=p['natural_key']['table_name'],
                                         column_name=p['natural_key']['column_name'],
                                         code=p['natural_key']['code'])
                if exists:
                    report['conflicts'].append({'id': exists.id, 'reason': 'new_row_already_exists'})
                    continue
                row = AssetColumnValueDomain(**p['natural_key'], meaning=p['meaning'],
                                             domain_kind='enum', status='pending', note=p['note'])
                db.add(row)
                db.flush()
                report['new_rows'] += 1
                dom_id = row.id
            else:
                row = db.get(AssetColumnValueDomain, p['id'])
                if row is None:
                    report['conflicts'].append({'id': p['id'], 'reason': 'row_missing'})
                    continue
                if row.status != p['status_guard']:
                    report['skipped_not_pending'].append({'id': p['id'], 'status': row.status})
                    continue
                before = {'id': row.id, 'system_code': row.system_code, 'source_code': row.source_code,
                          'schema_name': row.schema_name, 'table_name': row.table_name,
                          'column_name': row.column_name, 'code': row.code, 'meaning': row.meaning,
                          'domain_kind': row.domain_kind, 'status': row.status, 'note': row.note,
                          'current_version_id': row.current_version_id,
                          'evidence_count': 0}
                if h(before) != p['before_row_sha256']:
                    report['conflicts'].append({'id': p['id'], 'reason': 'before_hash_mismatch'})
                    continue
                changed = False
                for k, v in p.get('revisions', {}).items():
                    if getattr(row, k, None) != v:
                        setattr(row, k, v)
                        changed = True
                if changed:
                    report['updated'] += 1
                dom_id = row.id
            for ev in p.get('evidence_to_register', []):
                item = {'source_type': ev['source_type'], 'snippet_ref': ev['ref'],
                        'observed_meaning': ev['detail'], 'observed_at': '2026-09-21'}
                if not vds.evidence_duplicate(db, dom_id, item):
                    db.add(vds.evidence_row(dom_id, item))
                    report['evidence_inserted'] += 1
        # 版本推进（服务语义：有实质修订才建新版本）
        db.commit()
    (OUT / f'b6_apply_report_{"test" if target_label != "prod" else "prod"}.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--plan', action='store_true')
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--plan-file', default=str(OUT / 'b6_domain_revision_plan.json'))
    ap.add_argument('--prod', action='store_true', help='生产目标（本任务禁止使用）')
    args = ap.parse_args()
    if args.plan:
        build_plan()
    if args.apply:
        if args.prod:
            raise SystemExit('生产应用须 B7 批准包明确批准；本工具在此任务中禁止 --prod')
        apply(args.plan_file, 'test' if not args.prod else 'prod')


if __name__ == '__main__':
    main()
