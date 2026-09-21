-- probe P-B1-03 | ods_8_216 | oracle11g
-- question: MTL 本地住院次(P_INPATIENT_TIMES)与 HIS VISIT_ID 是否同一编号系（182号曾发现手麻两套编号）
-- scope: 2025-06 入院窗前200文书索引
-- note: 结果只看聚合；mtl_times/his_visit_id 不外带
WITH di AS (
  SELECT P_INPATIENT_NO, P_INPATIENT_TIMES FROM MTL.EPR_INPATIENT_DOCINDEX
  WHERE ADMIT_DATE_TIME >= DATE '2025-06-01' AND ADMIT_DATE_TIME < DATE '2025-07-01' AND ROWNUM <= 200
), j AS (
  SELECT di.P_INPATIENT_TIMES mtl_times, v.VISIT_ID his_visit_id
  FROM di JOIN HIS.PAT_MASTER_INDEX pmi ON pmi.INP_NO = di.P_INPATIENT_NO
  LEFT JOIN HIS.PAT_VISIT v ON v.PATIENT_ID = pmi.PATIENT_ID AND v.VISIT_ID = di.P_INPATIENT_TIMES
)
SELECT
  (SELECT COUNT(*) FROM di) docindex_rows,
  (SELECT COUNT(*) FROM j) joined_rows,
  (SELECT COUNT(*) FROM j WHERE his_visit_id IS NULL) visit_unmatched,
  (SELECT COUNT(*) FROM j WHERE his_visit_id IS NOT NULL AND mtl_times = his_visit_id) times_equal
FROM dual
