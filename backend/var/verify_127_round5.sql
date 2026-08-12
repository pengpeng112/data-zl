-- 127 复核第五轮：G1/G2 四条关系明细 + 重复组明细 + 连接清单（只读）
SET TRANSACTION READ ONLY;
\pset tuples_only on
SELECT 'rel|' || id || '|bk=' || coalesce(relation_business_key,'NULL') || '|' || coalesce(relation_layer,'-') || '|' || coalesce(validation_status,'-') || '|' || coalesce(from_table,'?') || '(' || coalesce(from_columns,'?') || ')->' || coalesce(to_table,'?') || '(' || coalesce(to_columns,'?') || ')'
FROM asset.asset_relations WHERE id IN (468,473,537,538,28,45,439,426) ORDER BY id;
SELECT '连接|' || source_code || '|sys=' || coalesce(system_code,'-') || '|' || coalesce(db_type,'-') || '|host=' || coalesce(host_masked,'-') || '|' || coalesce(environment,'-') || '|enabled=' || enabled || '|test=' || coalesce(last_test_status,'-')
FROM asset.asset_data_sources ORDER BY display_order, source_code;
