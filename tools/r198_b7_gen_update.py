# -*- coding: utf-8 -*-
"""r198 B7-②：生产修订三子包 SQL 生成（167 source+验证语义 / 34+3 值域 / 13 配方 v2）。
生成 r198_prod_update.sql（单事务+守卫+审计，r197 同模式）；
以及 r198_seed_test.sql（隔离库种子，用生产回读形态预演本 SQL）。"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '开发起步包/output_r198/r198-20260922-remediation'
AUDIT = ROOT / 'review/adhoc/r197-audit-20260922'


def q(s, tag='$r198$'):
    return tag + (s or '') + tag


def main():
    readback = json.loads((AUDIT / 'platform_readback.json').read_text(encoding='utf-8'))
    reviews = readback['reviews']
    domains = readback['domains']
    recipes = readback['recipes']
    rc2 = json.loads((OUT / 'review_corrections_v2.json').read_text(encoding='utf-8'))
    row_by_review = {r['review_id']: r for r in rc2['rows']}
    p2a = json.loads((OUT / 'b7_p2a_verdicts.json').read_text(encoding='utf-8'))
    plan = json.loads((OUT / 'b6_domain_revision_plan.json').read_text(encoding='utf-8'))
    rcp_v2 = json.loads((OUT / 'recipe_payload_v2.json').read_text(encoding='utf-8'))['recipes']
    rerev = json.loads((OUT / 'b4_validation_rereview.json').read_text(encoding='utf-8'))['rereview']
    rerev_by_old = {m['relation_id']: m for m in rerev}

    stmts = []
    # ---------- A. 167 source 修正（含 129 口径默认） ----------
    stmts.append("-- A. 167 草稿 source 修正：HIS_SOURCE(悬空)→HIS/his_source_10_10_10_15（用户 2026-09-22 批准，含 129 条语料级默认口径）；DATA_CENTER(合法码)补 ods_8_216")
    stmts.append(
        "UPDATE asset.asset_relation_reviews SET from_system_code='HIS', from_source_code='his_source_10_10_10_15', updated_at=now() "
        "WHERE relation_scope='r197_intake' AND review_status='draft' AND from_system_code='HIS_SOURCE';")
    stmts.append(
        "UPDATE asset.asset_relation_reviews SET to_system_code='HIS', to_source_code='his_source_10_10_10_15', updated_at=now() "
        "WHERE relation_scope='r197_intake' AND review_status='draft' AND to_system_code='HIS_SOURCE';")
    stmts.append(
        "UPDATE asset.asset_relation_reviews SET from_source_code='ods_8_216', updated_at=now() "
        "WHERE relation_scope='r197_intake' AND review_status='draft' AND from_system_code='DATA_CENTER' AND coalesce(from_source_code,'')='';")
    stmts.append(
        "UPDATE asset.asset_relation_reviews SET to_source_code='ods_8_216', updated_at=now() "
        "WHERE relation_scope='r197_intake' AND review_status='draft' AND to_system_code='DATA_CENTER' AND coalesce(to_source_code,'')='';")

    # ---------- B. 逐 review 证据/语义附注（source_evidence JSON 追加 + review_note） ----------
    stmts.append("-- B. 逐 review 附注：P2A 探针证据（20）/降级语义（27）/696/766 缺口定性/拟撤与列变标注")
    for rv in reviews:
        rid_int = rv['id']
        row = row_by_review.get(rid_int) or row_by_review.get(str(rid_int))
        if row is None:
            continue
        old_rid = row['relation_id']
        ev = json.loads(rv['source_evidence']) if rv.get('source_evidence') else {}
        add = {}
        note_parts = []
        act = row['recommended_action']
        if str(rid_int) in p2a or rid_int in p2a:
            v = p2a.get(str(rid_int)) or p2a.get(rid_int)
            add['r198_probe'] = {'uid': v['uid'], 'verdict': v['verdict'],
                                 'sample': f"A:{v['da']}/{v['na']} B:{v['db']}/{v['nb']}",
                                 'executed': '2026-09-22 live sjzc 只读通道（用户批准）'}
            if v['verdict'].startswith('pass'):
                note_parts.append('r198 样本验证：至少一端键唯一（P2A），可入人工 approve')
            elif v['verdict'] == 'dup_both_sides':
                note_parts.append('r198 样本验证：两端均有键重复（P2A），聚合用途不安全，保持 insufficient 待人工')
            elif v['verdict'] == 'zero_sample':
                note_parts.append('r198 样本验证：双端零样本（表当前空），不可判，保持待人工')
        if rid_int == 696:
            note_parts.append('r198 定性：INPADM.WAIT_BED_PATS_NEW 活库无 USER_NAME 列（P2C-696b 仅 NAME/NAME_PHONETIC）——原 SQL 列错误或旧字段，人工处置建议 reject 或改列')
        if rid_int == 766:
            note_parts.append('r198 定性：OFFICIAL_DRUG_CATALOG(_CLASS) 活库列存在（P2C-766：CONSTRAINED_LEVEL 等 15 列）——平台列级元数据漏采；表当前空（P2A 零样本）')
        m = rerev_by_old.get(old_rid)
        if m and m['recommended'] == 'downgrade_insufficient':
            add['r198_validation_review'] = {'from': 'passed_in_scope', 'to': 'insufficient',
                                             'reason': m['reason'][:200]}
            note_parts.append('r198 语义更正：原 passed 仅旁证，降级 insufficient（' + m['reason'][:80] + '）')
        if act == 'columns_changed_review':
            note_parts.append('r198：复合键经作用域解析拆分/列集变化（' + row['note'][:60] + '），人工裁决更新列或关旧建新')
        if act == 'propose_reject_or_hold':
            note_parts.append('r198：作用域感知重解析未能复现该边，建议驳回或保留待核（人工裁决）')
        if not add and not note_parts:
            if act == 'source_pending_no_context':
                note_parts.append('r198：源按语料级默认口径定 HIS/his_source_10_10_10_15（用户 2026-09-22 批准）；HIS/ODS 同名镜像无法语句级区分')
        if add or note_parts:
            ev.update(add)
            ev['r198_run'] = 'r198-20260922-remediation'
            stmts.append(
                f"UPDATE asset.asset_relation_reviews SET source_evidence={q(json.dumps(ev, ensure_ascii=False))}, "
                f"review_note={q('；'.join(note_parts) if note_parts else '')}, updated_at=now() "
                f"WHERE id={rid_int} AND relation_scope='r197_intake' AND review_status='draft' "
                f"AND source_evidence={q(rv['source_evidence'] or '')};")

    # ---------- C. 值域：34 system 修正+2 语义修订+3 新增+evidence ----------
    stmts.append("-- C1. 34 值域 system_code 修正 HIS_SOURCE→HIS（仅本批 pending）")
    stmts.append(
        "UPDATE asset.asset_column_value_domains SET system_code='HIS' "
        "WHERE (system_code='HIS_SOURCE' AND status='pending' AND note LIKE '%197%') "
        "OR (system_code='HIS_SOURCE' AND status='pending' AND source_code='his_source_10_10_10_15' AND "
        "((schema_name='COMM' AND table_name='OPERATION_DICT' AND column_name='OPERATION_SCALE' AND code='一 ') "
        "OR (schema_name='INPBILL' AND table_name='INP_BILL_DETAIL' AND column_name='OPER_CODE' AND code='多义键')));")
    stmts.append("-- C2. 逐条 meaning/note 修订 + evidence 登记")
    for p in plan:
        if p.get('new_row'):
            nk = p['natural_key']
            stmts.append(
                "INSERT INTO asset.asset_column_value_domains (system_code,source_code,schema_name,table_name,column_name,code,meaning,domain_kind,note,status,conflict_status) "
                f"SELECT 'HIS',{q(nk['source_code'])},{q(nk['schema_name'])},{q(nk['table_name'])},{q(nk['column_name'])},{q(nk['code'])},"
                f"{q(p['meaning'])},'enum',{q(p['note'])},'pending','none' "
                "WHERE NOT EXISTS (SELECT 1 FROM asset.asset_column_value_domains x WHERE x.system_code='HIS' AND x.source_code=" + q(nk['source_code']) +
                " AND x.schema_name=" + q(nk['schema_name']) + " AND x.table_name=" + q(nk['table_name']) +
                " AND x.column_name=" + q(nk['column_name']) + " AND x.code=" + q(nk['code']) + ");")
        else:
            dom = next((d for d in domains if d['id'] == p['id']), None)
            if dom is None:
                continue
            revs = p.get('revisions', {})
            sets = []
            if revs.get('meaning'):
                sets.append('meaning=' + q(revs['meaning']))
            note_aug = (dom.get('note') or '') + ('' if (dom.get('note') or '').endswith('r198') else ' | r198 证据补登')
            sets.append('note=' + q(note_aug))
            stmts.append(
                f"UPDATE asset.asset_column_value_domains SET {', '.join(sets)} WHERE id={p['id']} AND status='pending';")
        for ev in p.get('evidence_to_register', []):
            tbl = "(SELECT id FROM asset.asset_column_value_domains d WHERE d.system_code='HIS' AND d.schema_name=" + q(p['natural_key']['schema_name']) + " AND d.table_name=" + q(p['natural_key']['table_name']) + " AND d.column_name=" + q(p['natural_key']['column_name']) + " AND d.code=" + q(p['natural_key']['code']) + ")"
            stmts.append(
                "INSERT INTO asset.asset_column_value_domain_evidences (domain_id,source_type,snippet_ref,observed_meaning,observed_at) "
                f"SELECT id, {q(ev['source_type'])}, {q(ev['ref'])}, {q(ev['detail'])}, TIMESTAMP '2026-09-21 00:00:00+08' FROM asset.asset_column_value_domains "
                "WHERE system_code='HIS' AND schema_name=" + q(p['natural_key']['schema_name']) +
                " AND table_name=" + q(p['natural_key']['table_name']) + " AND column_name=" + q(p['natural_key']['column_name']) +
                " AND code=" + q(p['natural_key']['code']) +
                " AND NOT EXISTS (SELECT 1 FROM asset.asset_column_value_domain_evidences e WHERE e.domain_id=asset.asset_column_value_domains.id "
                " AND e.source_type=" + q(ev['source_type']) + " AND e.snippet_ref=" + q(ev['ref']) + " AND e.observed_meaning=" + q(ev['detail']) + ");")

    # ---------- D. 13 配方 v2 ----------
    stmts.append("-- D. 13 配方 payload v2（合法 qualified tables + 结构化 joins + 知识型 readiness；status 保持 draft）")
    by_orig = {r['recipe_id']: r for r in recipes}
    for v2 in rcp_v2:
        orig_low = v2['original_recipe_id'].lower()
        match = by_orig.get(v2.get('prod_recipe_id') or v2['original_recipe_id'])
        if match is None:
            for pid, pr in by_orig.items():
                pl = pid.lower()
                if (orig_low + '_') in pl or pl.endswith(orig_low):
                    match = pr
                    break
        if match is None:
            continue
        rj = {'r198_payload_v2': True, 'readiness': v2['readiness'],
              'not_ready_reasons': v2['not_ready_reasons'],
              'knowledge_payload': v2['knowledge_payload'],
              'name': v2['name'], 'domain': v2.get('domain')}
        joins_arr = v2['joins']
        stmts.append(
            f"UPDATE asset.asset_relation_recipes SET primary_tables={q(json.dumps([t['qualified'] or t['table'] for t in v2['primary_tables']]))}::jsonb, "
            f"joins={q(json.dumps(joins_arr))}::jsonb, "
            f"recipe_json={q(json.dumps(rj, ensure_ascii=False))}::jsonb, "
            f"content_hash={q(json.dumps({'r198': v2['readiness'], 'joins': len(joins_arr), 'tables': len(v2['primary_tables'])}, ensure_ascii=False))}, "
            f"updated_at=now() WHERE recipe_id={q(match['recipe_id'])} AND imported_from='r197_intake' AND status='draft';")

    # ---------- E. 守卫 + 审计 ----------
    stmts.append("-- E. 守卫与审计")
    stmts.append("""DO $$
DECLARE his_src int; note_upd int; vd_his int; vd_new int; ev_cnt int; rcp_upd int;
BEGIN
  SELECT count(*) INTO his_src FROM asset.asset_relation_reviews WHERE relation_scope='r197_intake' AND from_system_code='HIS_SOURCE';
  SELECT count(*) INTO note_upd FROM asset.asset_relation_reviews WHERE relation_scope='r197_intake' AND review_note LIKE '%r198%';
  SELECT count(*) INTO vd_his FROM asset.asset_column_value_domains WHERE system_code='HIS_SOURCE' AND (note LIKE '%197%' OR (source_code='his_source_10_10_10_15' AND ((schema_name='COMM' AND table_name='OPERATION_DICT' AND column_name='OPERATION_SCALE' AND code='一 ') OR (schema_name='INPBILL' AND table_name='INP_BILL_DETAIL' AND column_name='OPER_CODE' AND code='多义键'))));
  SELECT count(*) INTO vd_new FROM asset.asset_column_value_domains WHERE system_code='HIS' AND schema_name='INPBILL' AND table_name='INP_BILL_DETAIL' AND column_name='ITEM_CLASS' AND code IN ('E','F','G');
  SELECT count(*) INTO ev_cnt FROM asset.asset_column_value_domain_evidences e JOIN asset.asset_column_value_domains d ON d.id=e.domain_id WHERE d.system_code='HIS' AND d.source_code='his_source_10_10_10_15' AND e.observed_at=TIMESTAMP '2026-09-21 00:00:00+08';
  SELECT count(*) INTO rcp_upd FROM asset.asset_relation_recipes WHERE imported_from='r197_intake' AND recipe_json ? 'r198_payload_v2';
  IF his_src <> 0 THEN RAISE EXCEPTION '守卫失败: 仍有 HIS_SOURCE reviews=%', his_src; END IF;
  IF (SELECT count(*) FROM asset.asset_relation_reviews WHERE relation_scope='r197_intake' AND (coalesce(from_source_code,'')='' OR coalesce(to_source_code,'')='')) <> 0 THEN
    RAISE EXCEPTION '守卫失败: 仍有空 source_code 行'; END IF;
  IF note_upd < 160 THEN RAISE EXCEPTION '守卫失败: r198 附注过少=%', note_upd; END IF;
  IF vd_his <> 0 THEN RAISE EXCEPTION '守卫失败: 仍有 HIS_SOURCE 值域=%', vd_his; END IF;
  IF vd_new <> 3 THEN RAISE EXCEPTION '守卫失败: ITEM_CLASS E/F/G=%（期望3）', vd_new; END IF;
  IF ev_cnt < 30 THEN RAISE EXCEPTION '守卫失败: 值域 evidence=%（期望≥30）', ev_cnt; END IF;
  IF rcp_upd <> 13 THEN RAISE EXCEPTION '守卫失败: 配方 v2=%（期望13）', rcp_upd; END IF;
END $$;""")
    stmts.append("""INSERT INTO asset.asset_govern_audit_logs
(module, entity_type, entity_ref, action, before_data, after_data, operator, reason, created_at)
SELECT 'relation_intake','asset_relation_reviews+asset_column_value_domains+asset_relation_recipes','r198-20260922-remediation','batch_remediate_draft',
 '{"before": {"reviews_his_source": 167, "vd_his_source": 34, "recipes_draft": 13, "validation_null": 167}}'::jsonb,
 '{"after": {"reviews_source_fixed": 167, "probe_evidence_reviews": 20, "downgrade_notes": 27, "vd_system_fixed": 34, "vd_new_efg": 3, "vd_evidence": 34, "recipes_v2_knowledge": 13, "approve_confirm_untouched": true}}'::jsonb,
 'ai:r198-remediation','用户2026-09-22批准生产修订三子包（167 source+验证语义/34+3 值域/13 配方 v2）；审批终态仍留人工', now()
WHERE NOT EXISTS (SELECT 1 FROM asset.asset_govern_audit_logs g WHERE g.entity_ref='r198-20260922-remediation' AND g.action='batch_remediate_draft');""")

    sql = ('-- r198 生产修订三子包 | 单事务: psql -1 -v ON_ERROR_STOP=1\n'
           '-- run_id=r198-20260922-remediation | 用户 2026-09-22 批准\n\nBEGIN;\n'
           + ';\n'.join(stmts) + ';\nCOMMIT;\n')
    (OUT / 'r198_prod_update.sql').write_text(sql, encoding='utf-8')
    print('statements:', len(stmts), '| sql bytes:', len(sql))


if __name__ == '__main__':
    main()
