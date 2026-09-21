
  CREATE OR REPLACE FORCE VIEW "LUNA_MCS_SDSEY"."V_EMR_DISCHARGE_ASSESSMENT" ("ID", "ORG_CODE", "ORG_NAME", "ADMISSION_ID", "DEPT_CODE", "DEPT_NAME", "WARD_NAME", "EORD_NUM", "SICKBED_NUM", "NAME", "SEX_CODE", "SEX_NAME", "AGE", "AGE_MONTH", "DISEASE_CODE", "DISEASE_NAME", "DISCHARGE_DATE", "DIET_CODE", "DIET_NAME", "SELF_CARE_ABILITY", "SELF_CARE_ABI_NA", "DISCHARGE_SITUATION", "DISCHARGE_TYPE", "DISCHARGE_NAME", "DRUG_USER", "DIET_GUIDE_CODE", "LIFE_GUIDE_CODE", "STAUTH_NOTE", "VISIT_GUIDANCE", "NUSRSE_NAME", "SIGNATURE_DATE", "DISTRICT_CODE", "EXCHANGE_TYPE", "SYSTEM_TIME") AS 
  SELECT
       SUBSTRB(TO_CHAR(f.ID), 1, 100) AS ID, -- 内码，是，唯一主键

       '49557032X' AS ORG_CODE, -- 组织机构代码，是
       '山东省第二人民医院' AS ORG_NAME, -- 组织机构名称，是

       SUBSTRB(TO_CHAR(YDZD.mrn || '|' || YDZD.series), 1, 50) AS ADMISSION_ID, -- 住院唯一标示号，是

       SUBSTRB(NVL(TO_CHAR(dept.qmpt_code), TO_CHAR(YDZD.dept_code)), 1, 20) AS DEPT_CODE, -- 科室代码

       SUBSTRB(NVL(TO_CHAR(dept.qmpt_name), TO_CHAR(YDZD.dept_name)), 1, 50) AS DEPT_NAME, -- 科室名称，是

       SUBSTRB(TO_CHAR(YDZD.WARD_NAME), 1, 50) AS WARD_NAME, -- 病区名称

       CAST(NULL AS VARCHAR2(10)) AS EORD_NUM, -- 病房号；无可靠来源，不硬填

       SUBSTRB(TO_CHAR(YDZD.Bed_No), 1, 10) AS SICKBED_NUM, -- 病床号

       SUBSTRB(TO_CHAR(YDZD.NAME), 1, 50) AS NAME, -- 患者姓名，是

       CASE
           WHEN YDZD.physi_sex_name LIKE '男%' THEN '1'
           WHEN YDZD.physi_sex_name LIKE '女%' THEN '2'
           WHEN YDZD.physi_sex_name IS NULL THEN '0'
           ELSE '9'
       END AS SEX_CODE, -- 性别代码，是

       SUBSTRB(
           CASE
               WHEN YDZD.physi_sex_name LIKE '男%' THEN '男'
               WHEN YDZD.physi_sex_name LIKE '女%' THEN '女'
               WHEN YDZD.physi_sex_name IS NULL THEN '未知'
               ELSE TO_CHAR(YDZD.physi_sex_name)
           END,
           1,
           50
       ) AS SEX_NAME, -- 性别名称，是

       CASE
           WHEN YDZD.admission_time IS NOT NULL AND YDZD.birth_date IS NOT NULL
           THEN LEAST(200, GREATEST(0, TRUNC(MONTHS_BETWEEN(YDZD.admission_time, YDZD.birth_date) / 12)))
           ELSE 0
       END AS AGE, -- 年龄（岁），是

       CASE
           WHEN YDZD.admission_time IS NOT NULL
                AND YDZD.birth_date IS NOT NULL
                AND TRUNC(MONTHS_BETWEEN(YDZD.admission_time, YDZD.birth_date) / 12) = 0
           THEN SUBSTRB(TO_CHAR(GREATEST(0, TRUNC(MONTHS_BETWEEN(YDZD.admission_time, YDZD.birth_date)))), 1, 8)
           ELSE NULL
       END AS AGE_MONTH, -- 年龄（月）

       SUBSTRB(
           NVL(
               TO_CHAR(diag_dict.std_code),
               REPLACE(
                   CASE
                       WHEN INSTR(TO_CHAR(dg.diagnosis_code), '+') > 0
                       THEN SUBSTR(TO_CHAR(dg.diagnosis_code), 1, INSTR(TO_CHAR(dg.diagnosis_code), '+') - 1)
                       ELSE TO_CHAR(dg.diagnosis_code)
                   END,
                   '*',
                   ''
               )
           ),
           1,
           12
       ) AS DISEASE_CODE, -- 出院诊断编码，是；DIAGNOSIS@HIS + ICD字典映射

       SUBSTRB(
           NVL(
               TO_CHAR(diag_dict.std_name),
               NVL(TO_CHAR(dg.diagnosis_desc), NVL(TO_CHAR(YDZD.diagnosis_name), '-'))
           ),
           1,
           100
       ) AS DISEASE_NAME, -- 出院诊断描述

       TO_CHAR(p.DISCHARGE_DATE_TIME, 'yyyy-mm-dd hh24:mi:ss') AS DISCHARGE_DATE, -- 出院日期时间，是；取 PAT_VISIT@HIS

       NVL(
           (SELECT CASE
                       WHEN REGEXP_SUBSTR(a.STRING_VALUE, '^[0-9]+') = '1'
                            OR a.STRING_VALUE LIKE '%良好%'
                       THEN '1'
                       WHEN REGEXP_SUBSTR(a.STRING_VALUE, '^[0-9]+') = '2'
                            OR a.STRING_VALUE LIKE '%一般%'
                       THEN '2'
                       WHEN REGEXP_SUBSTR(a.STRING_VALUE, '^[0-9]+') = '3'
                            OR a.STRING_VALUE LIKE '%较差%'
                       THEN '3'
                       ELSE '1'
                   END
              FROM mcs_doc_form_records a
             WHERE a.template_code = f.TEMPLATE_CODE
               AND a.node_code = '00021'
               AND a.FORM_ID = f.ID
               AND ROWNUM = 1),
           '1'
       ) AS DIET_CODE, -- 饮食情况代码，是

       NVL(
           (SELECT SUBSTRB(
                       CASE
                           WHEN REGEXP_SUBSTR(a.STRING_VALUE, '^[0-9]+') = '1'
                                OR a.STRING_VALUE LIKE '%良好%'
                           THEN '良好'
                           WHEN REGEXP_SUBSTR(a.STRING_VALUE, '^[0-9]+') = '2'
                                OR a.STRING_VALUE LIKE '%一般%'
                           THEN '一般'
                           WHEN REGEXP_SUBSTR(a.STRING_VALUE, '^[0-9]+') = '3'
                                OR a.STRING_VALUE LIKE '%较差%'
                           THEN '较差'
                           WHEN INSTR(a.STRING_VALUE, '.') > 0
                           THEN SUBSTR(a.STRING_VALUE, INSTR(a.STRING_VALUE, '.', -1) + 1)
                           ELSE a.STRING_VALUE
                       END,
                       1,
                       50
                   )
              FROM mcs_doc_form_records a
             WHERE a.template_code = f.TEMPLATE_CODE
               AND a.node_code = '00021'
               AND a.FORM_ID = f.ID
               AND ROWNUM = 1),
           '良好'
       ) AS DIET_NAME, -- 饮食情况描述，是

       NVL(
           (SELECT CASE
                       WHEN REGEXP_SUBSTR(a.STRING_VALUE, '^[0-9]+') = '1'
                            OR a.STRING_VALUE LIKE '%完全%'
                       THEN '1'
                       WHEN REGEXP_SUBSTR(a.STRING_VALUE, '^[0-9]+') = '2'
                            OR a.STRING_VALUE LIKE '%部分%'
                       THEN '2'
                       WHEN REGEXP_SUBSTR(a.STRING_VALUE, '^[0-9]+') = '3'
                            OR a.STRING_VALUE LIKE '%不能%'
                       THEN '3'
                       ELSE '1'
                   END
              FROM mcs_doc_form_records a
             WHERE a.template_code = f.TEMPLATE_CODE
               AND a.node_code = '00020'
               AND a.FORM_ID = f.ID
               AND ROWNUM = 1),
           '1'
       ) AS SELF_CARE_ABILITY, -- 自理能力代码，是

       NVL(
           (SELECT SUBSTRB(
                       CASE
                           WHEN REGEXP_SUBSTR(a.STRING_VALUE, '^[0-9]+') = '1'
                                OR a.STRING_VALUE LIKE '%完全%'
                           THEN '完全自理'
                           WHEN REGEXP_SUBSTR(a.STRING_VALUE, '^[0-9]+') = '2'
                                OR a.STRING_VALUE LIKE '%部分%'
                           THEN '部分自理'
                           WHEN REGEXP_SUBSTR(a.STRING_VALUE, '^[0-9]+') = '3'
                                OR a.STRING_VALUE LIKE '%不能%'
                           THEN '不能自理'
                           WHEN INSTR(a.STRING_VALUE, '.') > 0
                           THEN SUBSTR(a.STRING_VALUE, INSTR(a.STRING_VALUE, '.', -1) + 1)
                           ELSE a.STRING_VALUE
                       END,
                       1,
                       50
                   )
              FROM mcs_doc_form_records a
             WHERE a.template_code = f.TEMPLATE_CODE
               AND a.node_code = '00020'
               AND a.FORM_ID = f.ID
               AND ROWNUM = 1),
           '完全自理'
       ) AS SELF_CARE_ABI_NA, -- 自理能力描述，是

       SUBSTRB(
           NVL(
               (SELECT a.STRING_VALUE
                  FROM mcs_doc_form_records a
                 WHERE a.template_code = f.TEMPLATE_CODE
                   AND a.node_code = '00013'
                   AND a.FORM_ID = f.ID
                   AND ROWNUM = 1),
               '-'
           ),
           1,
           2000
       ) AS DISCHARGE_SITUATION, -- 出院情况，是

             NVL(
           (SELECT CASE
                       WHEN REGEXP_SUBSTR(TRIM(a.STRING_VALUE), '^[0-9]+') = '1'
                            OR TRIM(a.STRING_VALUE) LIKE '%医嘱离院%'
                       THEN '1'

                       WHEN REGEXP_SUBSTR(TRIM(a.STRING_VALUE), '^[0-9]+') = '2'
                            OR TRIM(a.STRING_VALUE) LIKE '%医嘱转院%'
                       THEN '2'

                       WHEN REGEXP_SUBSTR(TRIM(a.STRING_VALUE), '^[0-9]+') = '3'
                            OR TRIM(a.STRING_VALUE) LIKE '%社区卫生服务%'
                            OR TRIM(a.STRING_VALUE) LIKE '%乡镇卫生院%'
                       THEN '3'

                       WHEN REGEXP_SUBSTR(TRIM(a.STRING_VALUE), '^[0-9]+') = '4'
                            OR TRIM(a.STRING_VALUE) LIKE '%非医嘱离院%'
                       THEN '4'

                       WHEN REGEXP_SUBSTR(TRIM(a.STRING_VALUE), '^[0-9]+') = '5'
                            OR TRIM(a.STRING_VALUE) LIKE '%死亡%'
                       THEN '5'

                       WHEN REGEXP_SUBSTR(TRIM(a.STRING_VALUE), '^[0-9]+') = '9'
                            OR TRIM(a.STRING_VALUE) LIKE '%其他%'
                       THEN '9'

                       ELSE '9'
                   END
              FROM mcs_doc_form_records a
             WHERE a.template_code = f.TEMPLATE_CODE
               AND a.node_code = '00014'
               AND a.FORM_ID = f.ID
               AND ROWNUM = 1),
           '9'
       ) AS DISCHARGE_TYPE, -- 离院方式代码：1医嘱离院 2医嘱转院 3转社区/乡镇 4非医嘱离院 5死亡 9其他

       NVL(
           (SELECT CASE
                       WHEN REGEXP_SUBSTR(TRIM(a.STRING_VALUE), '^[0-9]+') = '1'
                            OR TRIM(a.STRING_VALUE) LIKE '%医嘱离院%'
                       THEN '医嘱离院'

                       WHEN REGEXP_SUBSTR(TRIM(a.STRING_VALUE), '^[0-9]+') = '2'
                            OR TRIM(a.STRING_VALUE) LIKE '%医嘱转院%'
                       THEN '医嘱转院'

                       WHEN REGEXP_SUBSTR(TRIM(a.STRING_VALUE), '^[0-9]+') = '3'
                            OR TRIM(a.STRING_VALUE) LIKE '%社区卫生服务%'
                            OR TRIM(a.STRING_VALUE) LIKE '%乡镇卫生院%'
                       THEN '医嘱转社区卫生服务机构/乡镇卫生院'

                       WHEN REGEXP_SUBSTR(TRIM(a.STRING_VALUE), '^[0-9]+') = '4'
                            OR TRIM(a.STRING_VALUE) LIKE '%非医嘱离院%'
                       THEN '非医嘱离院'

                       WHEN REGEXP_SUBSTR(TRIM(a.STRING_VALUE), '^[0-9]+') = '5'
                            OR TRIM(a.STRING_VALUE) LIKE '%死亡%'
                       THEN '死亡'

                       WHEN REGEXP_SUBSTR(TRIM(a.STRING_VALUE), '^[0-9]+') = '9'
                            OR TRIM(a.STRING_VALUE) LIKE '%其他%'
                       THEN '其他'

                       ELSE '其他'
                   END
              FROM mcs_doc_form_records a
             WHERE a.template_code = f.TEMPLATE_CODE
               AND a.node_code = '00014'
               AND a.FORM_ID = f.ID
               AND ROWNUM = 1),
           '其他'
       ) AS DISCHARGE_NAME, -- 离院方式描述

       SUBSTRB(
           (SELECT a.STRING_VALUE
              FROM mcs_doc_form_records a
             WHERE a.template_code = f.TEMPLATE_CODE
               AND a.node_code = '00019'
               AND a.FORM_ID = f.ID
               AND ROWNUM = 1),
           1,
           1000
       ) AS DRUG_USER, -- 用药指导
       NVL(
           (SELECT CASE
                       WHEN REGEXP_SUBSTR(TRIM(a.STRING_VALUE), '^[0-9]+') IN ('01', '1')
                            OR TRIM(a.STRING_VALUE) LIKE '%普通饮食%'
                       THEN 1

                       WHEN REGEXP_SUBSTR(TRIM(a.STRING_VALUE), '^[0-9]+') IN ('02', '2')
                            OR TRIM(a.STRING_VALUE) LIKE '%软食%'
                       THEN 2

                       WHEN REGEXP_SUBSTR(TRIM(a.STRING_VALUE), '^[0-9]+') IN ('03', '3')
                            OR TRIM(a.STRING_VALUE) LIKE '%半流食%'
                       THEN 3

                       WHEN REGEXP_SUBSTR(TRIM(a.STRING_VALUE), '^[0-9]+') IN ('04', '4')
                            OR TRIM(a.STRING_VALUE) LIKE '%流食%'
                       THEN 4

                       WHEN REGEXP_SUBSTR(TRIM(a.STRING_VALUE), '^[0-9]+') IN ('06', '6')
                            OR TRIM(a.STRING_VALUE) LIKE '%禁食水%'
                       THEN 6

                       WHEN REGEXP_SUBSTR(TRIM(a.STRING_VALUE), '^[0-9]+') IN ('05', '5')
                            OR TRIM(a.STRING_VALUE) LIKE '%禁食%'
                       THEN 5

                       WHEN REGEXP_SUBSTR(TRIM(a.STRING_VALUE), '^[0-9]+') IN ('07', '7')
                            OR TRIM(a.STRING_VALUE) LIKE '%鼻饲%'
                       THEN 7

                       WHEN REGEXP_SUBSTR(TRIM(a.STRING_VALUE), '^[0-9]+') IN ('08', '8')
                            OR TRIM(a.STRING_VALUE) LIKE '%低盐低脂%'
                       THEN 8

                       WHEN REGEXP_SUBSTR(TRIM(a.STRING_VALUE), '^[0-9]+') IN ('09', '9')
                            OR TRIM(a.STRING_VALUE) LIKE '%糖尿病%'
                       THEN 9

                       WHEN REGEXP_SUBSTR(TRIM(a.STRING_VALUE), '^[0-9]+') = '99'
                            OR TRIM(a.STRING_VALUE) LIKE '%其他%'
                       THEN 99

                       ELSE 99
                   END
              FROM mcs_doc_form_records a
             WHERE a.template_code = f.TEMPLATE_CODE
               AND a.node_code = '00015'
               AND a.FORM_ID = f.ID
               AND ROWNUM = 1),
           99
       ) AS DIET_GUIDE_CODE, -- 饮食指导代码：1普通饮食 2软食 3半流食 4流食 5禁食 6禁食水 7鼻饲饮食 8低盐低脂饮食 9糖尿病饮食 99其他

       SUBSTRB(
           (SELECT a.STRING_VALUE
              FROM mcs_doc_form_records a
             WHERE a.template_code = f.TEMPLATE_CODE
               AND a.node_code = '00016'
               AND a.FORM_ID = f.ID
               AND ROWNUM = 1),
           1,
           50
       ) AS LIFE_GUIDE_CODE, -- 生活方式指导

       SUBSTRB(
           (SELECT a.STRING_VALUE
              FROM mcs_doc_form_records a
             WHERE a.template_code = f.TEMPLATE_CODE
               AND a.node_code = '00017'
               AND a.FORM_ID = f.ID
               AND ROWNUM = 1),
           1,
           100
       ) AS STAUTH_NOTE, -- 宣教内容

       SUBSTRB(
           (SELECT a.STRING_VALUE
              FROM mcs_doc_form_records a
             WHERE a.template_code = f.TEMPLATE_CODE
               AND a.node_code = '00018'
               AND a.FORM_ID = f.ID
               AND ROWNUM = 1),
           1,
           100
       ) AS VISIT_GUIDANCE, -- 复诊指导

       SUBSTRB(TO_CHAR(f.created_name), 1, 50) AS NUSRSE_NAME, -- 护士签名，是

       TO_CHAR(f.created_date, 'yyyy-mm-dd hh24:mi:ss') AS SIGNATURE_DATE, -- 签名日期时间，是

       '370104' AS DISTRICT_CODE, -- 行政区划，是

       'ADDHIS' AS EXCHANGE_TYPE, -- 交换类型，是

       TO_CHAR(SYSDATE, 'yyyy-mm-dd hh24:mi:ss') AS SYSTEM_TIME -- 数据上传时间，是

  FROM mcs_doc_form f
       JOIN inpatients YDZD
         ON f.PATIENT_UID = YDZD.pat_index_no

       JOIN pat_visit@HIS p
         ON p.PATIENT_ID = SUBSTR(YDZD.PATIENT_ID, 1, INSTR(YDZD.PATIENT_ID, '_') - 1)
        AND p.VISIT_ID = YDZD.SERIES

       JOIN DIAGNOSIS@HIS dg
         ON dg.PATIENT_ID = p.PATIENT_ID
        AND dg.VISIT_ID = p.VISIT_ID
        AND dg.diagnosis_type = '3'
        AND dg.diagnosis_no = '1'

       LEFT JOIN dept_dict@his dept
         ON dept.dept_code = YDZD.dept_code

       LEFT JOIN (
            SELECT TRIM(TO_CHAR(院标编码)) AS local_code,
                   MAX(NULLIF(TRIM(TO_CHAR(国标编码)), '')) AS std_code,
                   MAX(NULLIF(TRIM(TO_CHAR(国标名称)), '')) AS std_name
              FROM cda_dictionary@sjzx
             WHERE 字典名称 = 'ICD-10诊断编码'
               AND 系统标识 = 'HIS'
               AND TRIM(TO_CHAR(院标编码)) IS NOT NULL
             GROUP BY TRIM(TO_CHAR(院标编码))
       ) diag_dict
         ON diag_dict.local_code =
            TRIM(
                REPLACE(
                    CASE
                        WHEN INSTR(TO_CHAR(dg.diagnosis_code), '+') > 0
                        THEN SUBSTR(TO_CHAR(dg.diagnosis_code), 1, INSTR(TO_CHAR(dg.diagnosis_code), '+') - 1)
                        ELSE TO_CHAR(dg.diagnosis_code)
                    END,
                    '*',
                    ''
                )
            )

 WHERE f.TEMPLATE_CODE = '845'
   AND f.is_valid = '1'
   AND f.created_by <> 'dba'
   AND YDZD.status = 'out'
   AND p.DISCHARGE_DATE_TIME < TO_DATE('2025-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss')
