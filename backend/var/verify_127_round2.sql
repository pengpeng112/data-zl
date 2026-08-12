-- 127 复核第二轮：Review 对应关系与细节核实（只读）
SET TRANSACTION READ ONLY;
\pset tuples_only on
SELECT 'cols_relations|' || string_agg(column_name, ',') FROM information_schema.columns WHERE table_schema='asset' AND table_name='asset_relations';
SELECT 'cols_reviews|' || string_agg(column_name, ',') FROM information_schema.columns WHERE table_schema='asset' AND table_name='asset_relation_reviews';
SELECT '关系按状态|' || coalesce(validation_status,'-') || '=' || count(*) FROM asset.asset_relations GROUP BY 1 ORDER BY count(*) DESC;
