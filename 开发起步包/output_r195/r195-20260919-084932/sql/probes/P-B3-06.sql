-- probe P-B3-06 | ods_8_216 | oracle11g
-- question: TEST_NO 父键唯一性与明细一对多规模；孤儿率
-- scope: 一周采样窗前100 TEST_NO（子查询限定，禁全表扫）
-- note: 
WITH lt AS (
  SELECT TEST_NO FROM HIS.LAB_TEST
  WHERE SAMPLE_DATE >= DATE '2025-06-10' AND SAMPLE_DATE < DATE '2025-06-17' AND ROWNUM <= 100
), lr AS (
  SELECT /*+ LEADING(lt) USE_NL(r) */ r.TEST_NO FROM HIS.LAB_RESULT r
  WHERE r.TEST_NO IN (SELECT TEST_NO FROM lt)
)
SELECT
  (SELECT COUNT(*) FROM lt) parent_keys,
  (SELECT COUNT(*) FROM (SELECT TEST_NO FROM lt GROUP BY TEST_NO HAVING COUNT(*) > 1)) parent_dup,
  (SELECT COUNT(*) FROM lr) result_rows,
  (SELECT COUNT(*) FROM (SELECT TEST_NO FROM lr GROUP BY TEST_NO HAVING COUNT(*) > 1)) multi_item_tests,
  (SELECT COUNT(*) FROM lr lrx WHERE NOT EXISTS (SELECT 1 FROM lt x WHERE x.TEST_NO = lrx.TEST_NO)) orphan_rows
FROM dual
