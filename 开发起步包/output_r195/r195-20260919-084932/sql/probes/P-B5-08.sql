-- probe P-B5-08 | ods_8_216 | oracle11g
-- question: ODS 实例 JHEMR schema 对象存在性与近期数据量（jhemr 草稿部署前提）
-- scope: 数据字典+一月窗计数
-- note: CREATE_TIME 列名执行前核对；若 JHEMR schema 不在 ODS 实例，草稿需按跨实例改判
SELECT
  (SELECT COUNT(*) FROM ALL_TABLES WHERE OWNER = 'JHEMR' AND TABLE_NAME = 'JHMR_FILE_INDEX') idx_in_jhemr_schema,
  (SELECT COUNT(*) FROM ALL_TABLES WHERE OWNER = 'ODS' AND TABLE_NAME = 'JHMR_FILE_INDEX') idx_in_ods_schema,
  (SELECT COUNT(*) FROM JHEMR.JHMR_FILE_INDEX WHERE CREATE_TIME >= DATE '2025-06-01' AND CREATE_TIME < DATE '2025-07-01') recent_rows
FROM dual
