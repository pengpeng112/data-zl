-- probe P-B5-10 | dialysis_postgresql_10_10_10_88 | postgresql
-- question: 血透历史 SQL 对象在 PG 血透库的真实键；治疗记录-登记表基数
-- scope: 前200登记键
-- note: 
WITH rp AS (
  SELECT "ID" FROM public."REGISTER_PATIENTINFOMATION" LIMIT 200
)
SELECT
  (SELECT COUNT(*) FROM rp) reg_rows,
  (SELECT COUNT(*) FROM public."TREATMENT_TREATMENT" tt WHERE tt."REGISTERID" IN (SELECT "ID" FROM rp)) treat_rows,
  (SELECT COUNT(*) FROM public."TREATMENT_TREATMENT" tt WHERE tt."REGISTERID" IN (SELECT "ID" FROM rp) AND tt."REGISTERID" IS NULL) null_key

