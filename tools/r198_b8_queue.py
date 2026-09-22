# -*- coding: utf-8 -*-
"""r198 B8：生成人工治理队列 human_review_queue.csv/json（按同风险同证据分组，便于批量裁决）。
执行 AI 不代裁决；每项带证据指针与正式状态路径。"""
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '开发起步包/output_r198/r198-20260922-remediation'


def main():
    rc2 = json.loads((OUT / 'review_corrections_v2.json').read_text(encoding='utf-8'))
    rows = []

    def add(group, item_id, title, recommendation, evidence, path, risk='中'):
        rows.append({'group': group, 'id': item_id, 'title': title,
                     'recommendation': recommendation, 'evidence': evidence,
                     'formal_path': path, 'risk': risk})

    # A1 可批草稿（20）
    a1 = [r for r in rc2['rows'] if r['recommended_action'] == 'confirm_with_source_fix']
    for r in a1:
        add('A1', f"review:{r['review_id']}",
            f"{r['current']['from_table']} ~ {r['current']['to_table']}",
            '条件采纳：先补 system/source（HIS/his_source_10_10_10_15），live P2A 双端唯一性通过后 approve',
            f"review_corrections_v2.json#review_id={r['review_id']}; probe P2A-{r['review_id']}",
            'review approve → 链接/新建 candidate → 人工审核 → formal')
    # A2 源歧义（129）
    a2 = [r for r in rc2['rows'] if r['recommended_action'] == 'source_pending_no_context']
    add('A2', f'reviews:{",".join(str(r["review_id"]) for r in a2[:5])}…({len(a2)}条)',
        '董哥语料 HIS/ODS 同名表源歧义（无语句级证据）',
        '待输入：是否接受"报表 SQL 默认 HIS 业务库、ODS 需显式标记"语料级默认；或逐条人工',
        'b4_source_disambiguation.json（列差=0 实证 ODS 镜像）；r198_ctx_disambig.py（上下文证据=0）',
        '裁决后按 A1 路径批量补 source', risk='高')
    # A3 列变（12）
    a3 = [r for r in rc2['rows'] if r['recommended_action'] == 'columns_changed_review']
    for r in a3:
        add('A3', f"review:{r['review_id']}", '复合键拆分/列集变化',
            '更新列或关闭旧条新建', f"old_to_new_relations.json#{r['relation_id']}",
            'review 更新或 reject+新 review', risk='中')
    # A4 拟撤（6）
    for r in rc2['rows']:
        if r['recommended_action'] == 'propose_reject_or_hold':
            add('A4', f"review:{r['review_id']}", '新解析不可复现该边（解析缺陷产物或未再命中）',
                '驳回，或保留并注明待核', f"old_to_new_relations.json#{r['relation_id']}",
                'review reject 或保持 draft 备注', risk='中')
    # B passed 降级（27）
    rerev = json.loads((OUT / 'b4_validation_rereview.json').read_text(encoding='utf-8'))['rereview']
    for m in rerev:
        if m['recommended'] == 'downgrade_insufficient':
            add('B', m['relation_id'], f"原 passed 仅旁证（{m['best_coverage']}）",
                '采纳降级 insufficient', f"b4_validation_rereview.json#{m['relation_id']}",
                '以 validation_note 更正语义（不伪造状态）', risk='中')
    # C 配方（13）
    add('C', 'recipes:13', '13 条知识型配方（复杂口径/非法表名/未解析引用）',
        '政策裁决：知识型允许 activate（生成端拒绝）或保持 draft',
        'recipe_payload_v2.json（13/13 not_executable+not_ready_reasons）',
        'draft →（政策允许时）submitted → approved → active（生成恒拒）', risk='中')
    # D 值域（37）
    add('D', 'domains:34+3', '34 存量 evidence 补登+2 语义修订；3 新增（ITEM_CLASS E/F/G）',
        '批准生产应用后，人工 confirm（F/G 两值待 P2B 补证）',
        'b6_domain_revision_plan.json；b6_rehearsal_result.json',
        'pending → 人工 confirmed（冲突先裁决）', risk='低')
    # E live 探针（24）
    add('E', 'probe_package_v2:24', '五要素齐备：源/SQL 哈希/范围/时段/通道',
        '批准后执行（建议夜窗或点名日间；197 批准不沿用）',
        'probe_package_v2.json', '执行 → 结果回填 B4 终判', risk='高')
    # F 生产修订
    add('F', 'prod_revision', '167/34+3/13 三子包（隔离预演过、逐行可撤销）',
        '批准后按 b6 工具 --prod 语义经批准入口执行', 'b6_*_rehearsal.json；review_corrections_v2.json',
        '审计+回读', risk='高')
    # G 缺口与未定位
    add('G', 'gaps:696/766', 'WAIT_BED_PATS_NEW.USER_NAME 列证据缺失；两药目录列级 0 行',
        '随 E 组批准执行 P2C 后定论（漏采/错选/旧字段）', 'b1_platform_identity.json',
        '元数据补采工单或修订', risk='低')
    add('G', 'unmatched:20/99', '125 未匹配对象中 20 条待核（+EXP/DRG/临时族定向）',
        '定向源字典探针工单（随 E 组）', 'asset_inventory.json#unmatched_objects',
        '对象登记或排除', risk='低')
    add('G', 'tail:20+295', '20 条旧边解析尾巴；295 派生边待唯一溯源',
        '列入后续方言增强或人工核', 'b3_derived_pending.json；b2_edge_diff_undirected.json',
        '补证据或排除', risk='低')

    with (OUT / 'human_review_queue.json').open('w', encoding='utf-8') as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)
    with (OUT / 'human_review_queue.csv').open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['group', 'id', 'title', 'recommendation', 'evidence', 'formal_path', 'risk'])
        w.writeheader()
        w.writerows(rows)
    import collections
    print(json.dumps(dict(collections.Counter(r['group'] for r in rows)), ensure_ascii=False))


if __name__ == '__main__':
    main()
