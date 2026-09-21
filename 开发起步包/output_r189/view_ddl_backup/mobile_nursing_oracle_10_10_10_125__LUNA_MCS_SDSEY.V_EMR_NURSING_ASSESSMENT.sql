
  CREATE OR REPLACE FORCE VIEW "LUNA_MCS_SDSEY"."V_EMR_NURSING_ASSESSMENT" ("ID", "ORG_CODE", "ORG_NAME", "PAT_NAME", "PAT_SEX", "PAT_TYPE_CODE", "VISITING_NUM", "DEPT_ID", "DEPT_NAME", "APPLY_DOC_NAME", "APPLY_DOC_ID", "NURSE_NAME", "NURSE_ID_NUM", "CREATE_TIME", "SCALE_NAME", "SCALE_CODE", "SCORE_VAL", "GRADE_LVL", "EXCHANGE_TYPE", "SYSTEM_TIME") AS 
  SELECT
       SUBSTRB(
           '49557032X|' ||
           TO_CHAR(f.template_code) || '|' ||
           TO_CHAR(f.ID),
           1,
           100
       ) AS ID, -- 主键，是

       '49557032X' AS ORG_CODE, -- 医院组织机构代码，是

       '山东省第二人民医院' AS ORG_NAME, -- 医院名称，是

       SUBSTRB(TO_CHAR(p.NAME), 1, 32) AS PAT_NAME, -- 被评估患者姓名，是

       CASE
           WHEN p.physi_sex_name LIKE '男%' THEN '1'
           WHEN p.physi_sex_name LIKE '女%' THEN '2'
           WHEN p.physi_sex_name IS NULL THEN '0'
           ELSE '9'
       END AS PAT_SEX, -- 被评估患者性别，是

       '2' AS PAT_TYPE_CODE, -- 被评估患者类别：1门诊 2住院，是

       SUBSTRB(TO_CHAR(p.mrn || '|' || p.series), 1, 32) AS VISITING_NUM, -- 被评估病人就诊号，是

       SUBSTRB(NVL(TO_CHAR(dept.qmpt_code), TO_CHAR(p.dept_code)), 1, 12) AS DEPT_ID, -- 患者所在科室编码，是

       SUBSTRB(NVL(TO_CHAR(dept.qmpt_name), TO_CHAR(p.dept_name)), 1, 50) AS DEPT_NAME, -- 患者所在科室名称，是

       CAST(NULL AS VARCHAR2(32)) AS APPLY_DOC_NAME, -- 医生姓名；护理量表暂无可靠来源

       CAST(NULL AS VARCHAR2(18)) AS APPLY_DOC_ID, -- 医生身份证号码；暂无可靠来源

       SUBSTRB(NVL(TO_CHAR(f.created_name), TO_CHAR(f.last_updated_name)), 1, 32) AS NURSE_NAME, -- 护士姓名

       CAST(NULL AS VARCHAR2(18)) AS NURSE_ID_NUM, -- 护士身份证号；暂无可靠来源，不用工号冒充

       TO_CHAR(f.created_date, 'yyyy-mm-dd hh24:mi:ss') AS CREATE_TIME, -- 评估时间，是

       SUBSTRB(
           CASE
               WHEN f.template_code = '564' THEN '改良 Barthel 指数评分表'
               WHEN f.template_code IN ('616', '619') THEN '成人NRS 2002营养风险筛查表'
               WHEN f.template_code = '782' THEN '儿童STAMP量表'
               WHEN f.template_code = '854' THEN 'PG-SGA营养评估量表'
               WHEN f.template_code = '722' THEN '数字评分量表（NRS）'
               WHEN f.template_code = '598' THEN '格拉斯哥昏迷量表（GCS）'
               ELSE '其他量表'
           END,
           1,
           200
       ) AS SCALE_NAME, -- 评估量表名称，是

       SUBSTRB(
           CASE
               WHEN f.template_code = '564' THEN '30'
               WHEN f.template_code IN ('616', '619') THEN '48'
               WHEN f.template_code = '782' THEN '49'
               WHEN f.template_code = '854' THEN '52'
               WHEN f.template_code = '722' THEN '62'
               WHEN f.template_code = '598' THEN '80'
               ELSE '99'
           END,
           1,
           100
       ) AS SCALE_CODE, -- 评估量表编码，是

       ROUND(score.score_val, 2) AS SCORE_VAL, -- 评分数值，是；按确认后的总分节点取值

       SUBSTRB(
           CASE
               /* 30 改良 Barthel 指数评分表：分值越低风险越高 */
               WHEN f.template_code = '564' THEN
                    CASE
                        WHEN score.score_val <= 40 THEN '高危'
                        WHEN score.score_val <= 60 THEN '中危'
                        ELSE '低危'
                    END

               /* 48 成人NRS 2002营养风险筛查表：NRS2002得分 >=3 为营养风险 */
               WHEN f.template_code IN ('616', '619') THEN
                    CASE
                        WHEN score.score_val >= 3 THEN '高危'
                        WHEN score.score_val = 2 THEN '中危'
                        ELSE '低危'
                    END

               /* 49 儿童STAMP量表：0-1低危，2-3中危，>=4高危 */
               WHEN f.template_code = '782' THEN
                    CASE
                        WHEN score.score_val >= 4 THEN '高危'
                        WHEN score.score_val >= 2 THEN '中危'
                        ELSE '低危'
                    END

               /* 52 PG-SGA营养评估量表：A+B+C+D总分，0-1低危，2-8中危，>=9高危 */
               WHEN f.template_code = '854' THEN
                    CASE
                        WHEN score.score_val >= 9 THEN '高危'
                        WHEN score.score_val >= 2 THEN '中危'
                        ELSE '低危'
                    END

               /* 62 数字评分量表（NRS）：0-3低危，4-6中危，7-10高危 */
               WHEN f.template_code = '722' THEN
                    CASE
                        WHEN score.score_val >= 7 THEN '高危'
                        WHEN score.score_val >= 4 THEN '中危'
                        ELSE '低危'
                    END

               /* 80 格拉斯哥昏迷量表（GCS）：分值越低风险越高 */
               WHEN f.template_code = '598' THEN
                    CASE
                        WHEN score.score_val <= 8 THEN '高危'
                        WHEN score.score_val <= 12 THEN '中危'
                        ELSE '低危'
                    END

               ELSE '低危'
           END,
           1,
           10
       ) AS GRADE_LVL, -- 评估等级，是：低危、中危、高危

       'ADDHIS' AS EXCHANGE_TYPE, -- 交换类型，是

       TO_CHAR(SYSDATE, 'yyyy-mm-dd hh24:mi:ss') AS SYSTEM_TIME -- 数据上传/更新时间，是

  FROM mcs_doc_form f

       JOIN inpatients p
         ON f.PATIENT_UID = p.pat_index_no

       LEFT JOIN dept_dict@his dept
         ON dept.dept_code = p.dept_code

       JOIN pat_visit@HIS pv
         ON pv.PATIENT_ID = SUBSTR(p.PATIENT_ID, 1, INSTR(p.PATIENT_ID || '_', '_') - 1)
        AND pv.VISIT_ID = p.SERIES

       JOIN (
            SELECT r.form_id,
                   r.template_code,

                   CASE
                       WHEN r.template_code = '564' THEN
                            MAX(CASE WHEN r.node_code = '00083' THEN r.score_val END) -- Barthel总分

                       WHEN r.template_code = '598' THEN
                            MAX(CASE WHEN r.node_code = '00020' THEN r.score_val END) -- GCS总分

                       WHEN r.template_code = '616' THEN
                            MAX(CASE WHEN r.node_code = '00043' THEN r.score_val END) -- NRS2002得分

                       WHEN r.template_code = '619' THEN
                            MAX(CASE WHEN r.node_code = '00028' THEN r.score_val END) -- 旧NRS2002总分

                       WHEN r.template_code = '722' THEN
                            MAX(CASE WHEN r.node_code = '00140' THEN r.score_val END) -- 疼痛评估总分

                       WHEN r.template_code = '782' THEN
                            MAX(CASE WHEN r.node_code = '00027' THEN r.score_val END) -- 儿童营养风险总分

                       WHEN r.template_code = '854' THEN
                            MAX(CASE WHEN r.node_code = '00159' THEN r.score_val END) -- PG-SGA A+B+C+D总分

                       ELSE NULL
                   END AS score_val

              FROM (
                    SELECT a.form_id,
                           a.template_code,
                           a.node_code,
                           CASE
                               WHEN a.number_value IS NOT NULL
                               THEN a.number_value

                               WHEN a.string_value IS NOT NULL
                                    AND REGEXP_LIKE(TRIM(TO_CHAR(a.string_value)), '^[0-9]+(\.[0-9]+)?$')
                               THEN TO_NUMBER(TRIM(TO_CHAR(a.string_value)))

                               ELSE NULL
                           END AS score_val
                      FROM mcs_doc_form_records a
                     WHERE a.template_code IN ('564', '616', '619', '782', '854', '722', '598')
                       AND (
                              (a.template_code = '564' AND a.node_code = '00083') -- Barthel总分
                           OR (a.template_code = '598' AND a.node_code = '00020') -- GCS总分
                           OR (a.template_code = '616' AND a.node_code = '00043') -- NRS2002得分
                           OR (a.template_code = '619' AND a.node_code = '00028') -- 旧NRS2002总分
                           OR (a.template_code = '722' AND a.node_code = '00140') -- 疼痛总分
                           OR (a.template_code = '782' AND a.node_code = '00027') -- 儿童营养风险总分
                           OR (a.template_code = '854' AND a.node_code = '00159') -- PG-SGA A+B+C+D总分
                           )
                   ) r
             GROUP BY r.form_id,
                      r.template_code
            HAVING CASE
                       WHEN r.template_code = '564' THEN
                            MAX(CASE WHEN r.node_code = '00083' THEN r.score_val END)
                       WHEN r.template_code = '598' THEN
                            MAX(CASE WHEN r.node_code = '00020' THEN r.score_val END)
                       WHEN r.template_code = '616' THEN
                            MAX(CASE WHEN r.node_code = '00043' THEN r.score_val END)
                       WHEN r.template_code = '619' THEN
                            MAX(CASE WHEN r.node_code = '00028' THEN r.score_val END)
                       WHEN r.template_code = '722' THEN
                            MAX(CASE WHEN r.node_code = '00140' THEN r.score_val END)
                       WHEN r.template_code = '782' THEN
                            MAX(CASE WHEN r.node_code = '00027' THEN r.score_val END)
                       WHEN r.template_code = '854' THEN
                            MAX(CASE WHEN r.node_code = '00159' THEN r.score_val END)
                       ELSE NULL
                   END IS NOT NULL
       ) score
         ON score.form_id = f.ID
        AND score.template_code = f.template_code

 WHERE f.template_code IN ('564', '616', '619', '782', '854', '722', '598')
   AND f.is_valid = '1'
   AND f.created_by <> 'dba'
   AND p.status = 'out'
   AND pv.DISCHARGE_DATE_TIME >= TO_DATE('2021-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss')
   AND pv.DISCHARGE_DATE_TIME <  TO_DATE('2025-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss')
