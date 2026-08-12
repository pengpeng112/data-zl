-- 127 复核第四轮：重复业务键明细 + 数据连接清单（只读）
SET TRANSACTION READ ONLY;
\pset tuples_only on
SELECT '重复组|' || relation_business_key || ' => ids=' || string_agg(id::text, ',') || ' layers=' || string_agg(coalesce(relation_layer,'-'), ',') || ' status=' || string_agg(coalesce(validation_status,'-'), ',')
FROM asset.asset_relations WHERE relation_business_key IN (
  SELECT relation_business_key FROM asset.asset_relations WHERE relation_business_key IS NOT NULL GROUP BY relation_business_key HAVING count(*)>1
) GROUP BY relation_business_key;
SELECT '连接|' || source_code || '|' || coalesce(system_code,'-') || '|' || coalesce(db_type,'-') || '|' || coalesce(host,'-') || '|' || coalesce(status,'-') FROM asset.asset_data_sources ORDER BY source_code;
SELECT 'dscols|' || string_agg(column_name, ',') FROM information_schema.columns WHERE table_schema='asset' AND table_name='asset_data_sources';
