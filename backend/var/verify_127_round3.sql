-- 127 复核第三轮：Review 1/2/3、关系 537/538、重复组、端点不完整（只读）
SET TRANSACTION READ ONLY;
\pset tuples_only on
SELECT '关系按状态|' || coalesce(validation_status,'-') || '=' || count(*) FROM asset.asset_relations GROUP BY validation_status ORDER BY count(*) DESC;
SELECT '关系按层级|' || coalesce(relation_layer,'-') || '=' || count(*) FROM asset.asset_relations GROUP BY relation_layer ORDER BY count(*) DESC;
SELECT '业务键重复组|' || count(*) FROM (SELECT relation_business_key FROM asset.asset_relations WHERE relation_business_key IS NOT NULL GROUP BY relation_business_key HAVING count(*)>1) t;
SELECT '端点字段不完整|' || count(*) FROM asset.asset_relations WHERE from_table_name IS NULL OR to_table_name IS NULL OR from_system_code IS NULL OR to_system_code IS NULL;
SELECT 'review明细|' || id || '|' || coalesce(review_status,'-') || '|src_rel=' || coalesce(source_relation_id::text,'NULL') || '|' || coalesce(from_table,'?') || '(' || coalesce(from_columns,'?') || ')->' || coalesce(to_table,'?') || '(' || coalesce(to_columns,'?') || ')|conf=' || coalesce(confidence::text,'-') FROM asset.asset_relation_reviews ORDER BY id;
SELECT 'rel537|' || id || '|' || coalesce(rel_id,'-') || '|' || coalesce(validation_status,'-') || '|' || coalesce(relation_layer,'-') || '|' || coalesce(from_table,'?') || '->' || coalesce(to_table,'?') || '|bk=' || coalesce(relation_business_key,'-') FROM asset.asset_relations WHERE id IN (537,538);
SELECT 'G1候选|' || id || '|' || coalesce(validation_status,'-') || '|' || coalesce(relation_layer,'-') FROM asset.asset_relations WHERE from_table ILIKE '%INP_BILL_DETAIL%' AND to_table ILIKE '%PAT_VISIT%';
SELECT 'G2候选|' || id || '|' || coalesce(validation_status,'-') || '|' || coalesce(relation_layer,'-') FROM asset.asset_relations WHERE from_table ILIKE '%CLINIC_MASTER%' AND to_table ILIKE '%PAT_MASTER_INDEX%';
SELECT '数据新鲜度|' || max(created_at) FROM asset.asset_relations;
SELECT '质量快照|' || max(started_at) FROM asset.asset_quality_check_runs;
SELECT '问题构成|' || coalesce(rule_code,'-') || '=' || count(*) FROM asset.asset_quality_findings GROUP BY rule_code ORDER BY count(*) DESC LIMIT 12;
SELECT '启用规则字段|' || rule_code || '|name=' || coalesce(rule_name,'NULL') || '|cat=' || coalesce(rule_category,'NULL') || '|scope=' || coalesce(check_scope,'NULL') || '|sys=' || coalesce(system_code,'NULL') FROM asset.asset_quality_rules WHERE enabled=true ORDER BY rule_code;
SELECT '停用规则按系统|' || coalesce(system_code,'NULL') || '=' || count(*) FROM asset.asset_quality_rules WHERE enabled=false GROUP BY system_code ORDER BY count(*) DESC;
