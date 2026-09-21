
  CREATE OR REPLACE FORCE VIEW "LUNA_MCS_SDSEY"."V_EMR_CRITICALLY_ILL_NURS" ("ID", "ORG_CODE", "ORG_NAME", "ADMISSION_ID", "DEPT_CODE", "DEPT_NAME", "WARD_NAME", "EORD_NUM", "SICKBED_NUM", "NAME", "SEX_CODE", "SEX_NAME", "AGE", "AGE_MONTH", "NURSE_LEVEL_CODE", "NURSE_LEVEL_NAME", "NURSE_TYPE_CODE", "NURSE_TYPE_NAME", "ALLERGIES", "DISEASE_CODE", "DISEASE", "WEIGHT", "TEMPERATURE", "HEART_RATE", "BREATHING_RATE", "PRESSURE_H", "PRESSURE_L", "FBG_VALUE", "DIET_CODE", "DIET_NAME", "NURSE_OBSERVE_NAME", "NURSE_OBSERVE_RESULT", "NURSE_PROJECT", "NURSE_PROJECT_RESULT", "RM_PROJECT", "NURSE_NAME", "RECORD_DATE", "DISTRICT_CODE", "EXCHANGE_TYPE", "SYSTEM_TIME") AS 
  SELECT
       SUBSTRB(TO_CHAR(f.ID), 1, 100) AS ID, -- 内码，是，唯一主键

       '49557032X' AS ORG_CODE, -- 组织机构代码，是
       '山东省第二人民医院' AS ORG_NAME, -- 组织机构名称，是

       SUBSTRB(TO_CHAR(p.mrn || '|' || p.series), 1, 50) AS ADMISSION_ID, -- 住院唯一标示号，是

       SUBSTRB(NVL(TO_CHAR(dept.qmpt_code), TO_CHAR(p.dept_code)), 1, 20) AS DEPT_CODE, -- 科室代码

       SUBSTRB(NVL(TO_CHAR(dept.qmpt_name), TO_CHAR(p.dept_name)), 1, 50) AS DEPT_NAME, -- 科室名称，是

       SUBSTRB(TO_CHAR(p.WARD_NAME), 1, 50) AS WARD_NAME, -- 病区名称

       CAST(NULL AS VARCHAR2(10)) AS EORD_NUM, -- 病房号；无可靠来源，不硬填

       SUBSTRB(TO_CHAR(p.Bed_No), 1, 10) AS SICKBED_NUM, -- 病床号

       SUBSTRB(TO_CHAR(p.NAME), 1, 50) AS NAME, -- 患者姓名，是

       CASE
           WHEN p.physi_sex_name LIKE '男%' THEN '1'
           WHEN p.physi_sex_name LIKE '女%' THEN '2'
           WHEN p.physi_sex_name IS NULL THEN '0'
           ELSE '9'
       END AS SEX_CODE, -- 性别代码，是

       SUBSTRB(
           CASE
               WHEN p.physi_sex_name LIKE '男%' THEN '男'
               WHEN p.physi_sex_name LIKE '女%' THEN '女'
               WHEN p.physi_sex_name IS NULL THEN '未知'
               ELSE TO_CHAR(p.physi_sex_name)
           END,
           1,
           50
       ) AS SEX_NAME, -- 性别名称，是

       CASE
           WHEN p.admission_time IS NOT NULL AND p.birth_date IS NOT NULL
           THEN LEAST(200, GREATEST(0, TRUNC(MONTHS_BETWEEN(p.admission_time, p.birth_date) / 12)))
           ELSE 0
       END AS AGE, -- 年龄，是

       CASE
           WHEN p.admission_time IS NOT NULL
                AND p.birth_date IS NOT NULL
                AND TRUNC(MONTHS_BETWEEN(p.admission_time, p.birth_date) / 12) = 0
           THEN GREATEST(0, TRUNC(MONTHS_BETWEEN(p.admission_time, p.birth_date)))
           ELSE NULL
       END AS AGE_MONTH, -- 年龄（月）

       CASE
           WHEN TO_CHAR(p.nursing_class) = '0' THEN '1'
           WHEN TO_CHAR(p.nursing_class) = '1' THEN '2'
           WHEN TO_CHAR(p.nursing_class) = '2' THEN '3'
           WHEN TO_CHAR(p.nursing_class) IN ('3', '999') THEN '4'
           ELSE '4'
       END AS NURSE_LEVEL_CODE, -- 护理等级代码：1特级护理 2一级护理 3二级护理 4三级护理

       SUBSTRB(
           CASE
               WHEN TO_CHAR(p.nursing_class) = '0' THEN '特级护理'
               WHEN TO_CHAR(p.nursing_class) = '1' THEN '一级护理'
               WHEN TO_CHAR(p.nursing_class) = '2' THEN '二级护理'
               WHEN TO_CHAR(p.nursing_class) IN ('3', '999') THEN '三级护理'
               ELSE '三级护理'
           END,
           1,
           50
       ) AS NURSE_LEVEL_NAME, -- 护理等级名称，是

       CASE
           WHEN TO_CHAR(p.nursing_class) = '0' THEN '2' -- 特级护理 -> 特殊护理
           WHEN TO_CHAR(p.nursing_class) IN ('1', '2', '3', '999') THEN '1' -- 一级/二级/三级 -> 基础护理
           ELSE '9'
       END AS NURSE_TYPE_CODE, -- 护理类型代码：1基础护理 2特殊护理 3辩证施护 9其它

       SUBSTRB(
           CASE
               WHEN TO_CHAR(p.nursing_class) = '0' THEN '特殊护理'
               WHEN TO_CHAR(p.nursing_class) IN ('1', '2', '3', '999') THEN '基础护理'
               ELSE '其它'
           END,
           1,
           50
       ) AS NURSE_TYPE_NAME, -- 护理类型描述

       CAST(NULL AS VARCHAR2(1000)) AS ALLERGIES, -- 过敏史；原SQL无可靠来源

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
       ) AS DISEASE_CODE, -- 疾病诊断编码

       SUBSTRB(
           NVL(
               TO_CHAR(diag_dict.std_name),
               NVL(
                   TO_CHAR(dg.diagnosis_desc),
                   NVL(
                       (SELECT a.STRING_VALUE
                          FROM mcs_doc_form_records a
                         WHERE a.template_code = f.TEMPLATE_CODE
                           AND a.node_code = '00009'
                           AND a.FORM_ID = f.ID
                           AND TRIM(a.STRING_VALUE) IS NOT NULL
                           AND ROWNUM = 1),
                       NVL(TO_CHAR(p.diagnosis_name), '-')
                   )
               )
           ),
           1,
           200
       ) AS DISEASE, -- 疾病诊断名称，是

       NVL(
           (SELECT ROUND(a.vitalsign_nval1, 2)
              FROM mcs_vital_info a
             WHERE a.vitalsign_type = '1014'
               AND a.is_valid = '1'
               AND a.PATIENT_UID = f.PATIENT_UID
               AND a.vitalsign_nval1 IS NOT NULL
               AND ROWNUM = 1),
           0
       ) AS WEIGHT, -- 体重，是

       NVL(
           (SELECT ROUND(TO_NUMBER(REGEXP_SUBSTR(a.STRING_VALUE, '[0-9]+(\.[0-9]+)?')), 1)
              FROM mcs_doc_form_records a
             WHERE a.template_code = f.TEMPLATE_CODE
               AND a.node_code = '00022'
               AND a.FORM_ID = f.ID
               AND REGEXP_LIKE(a.STRING_VALUE, '[0-9]')
               AND ROWNUM = 1),
           0
       ) AS TEMPERATURE, -- 体温，是

       NVL(
           (SELECT TO_NUMBER(REGEXP_SUBSTR(a.STRING_VALUE, '[0-9]+'))
              FROM mcs_doc_form_records a
             WHERE a.template_code = f.TEMPLATE_CODE
               AND a.node_code = '00023'
               AND a.FORM_ID = f.ID
               AND REGEXP_LIKE(a.STRING_VALUE, '[0-9]')
               AND ROWNUM = 1),
           0
       ) AS HEART_RATE, -- 心率，是

       NVL(
           (SELECT TO_NUMBER(REGEXP_SUBSTR(a.STRING_VALUE, '[0-9]+'))
              FROM mcs_doc_form_records a
             WHERE a.template_code = f.TEMPLATE_CODE
               AND a.node_code = '00024'
               AND a.FORM_ID = f.ID
               AND REGEXP_LIKE(a.STRING_VALUE, '[0-9]')
               AND ROWNUM = 1),
           0
       ) AS BREATHING_RATE, -- 呼吸频率，是

       NVL(
           (SELECT TO_NUMBER(REGEXP_SUBSTR(a.STRING_VALUE, '[0-9]+'))
              FROM mcs_doc_form_records a
             WHERE a.template_code = f.TEMPLATE_CODE
               AND a.node_code = '00027'
               AND a.FORM_ID = f.ID
               AND REGEXP_LIKE(a.STRING_VALUE, '[0-9]')
               AND ROWNUM = 1),
           0
       ) AS PRESSURE_H, -- 收缩压，是

       NVL(
           (SELECT TO_NUMBER(REGEXP_SUBSTR(a.STRING_VALUE, '[0-9]+'))
              FROM mcs_doc_form_records a
             WHERE a.template_code = f.TEMPLATE_CODE
               AND a.node_code = '00028'
               AND a.FORM_ID = f.ID
               AND REGEXP_LIKE(a.STRING_VALUE, '[0-9]')
               AND ROWNUM = 1),
           0
       ) AS PRESSURE_L, -- 舒张压，是

       NVL(
           (SELECT ROUND(TO_NUMBER(REGEXP_SUBSTR(a.STRING_VALUE, '[0-9]+(\.[0-9]+)?')), 1)
              FROM mcs_doc_form_records a
             WHERE a.template_code = f.TEMPLATE_CODE
               AND a.node_code = '00127'
               AND a.FORM_ID = f.ID
               AND REGEXP_LIKE(a.STRING_VALUE, '[0-9]')
               AND ROWNUM = 1),
           0
       ) AS FBG_VALUE, -- 血糖检测值，是

       '1' AS DIET_CODE, -- 饮食情况代码，是；1良好

       '良好' AS DIET_NAME, -- 饮食情况描述，是

       SUBSTRB(
           NVL(
               (SELECT a.STRING_VALUE
                  FROM mcs_doc_form_records a
                 WHERE a.template_code = f.TEMPLATE_CODE
                   AND a.node_code = '00150'
                   AND a.FORM_ID = f.ID
                   AND TRIM(a.STRING_VALUE) IS NOT NULL
                   AND TRIM(a.STRING_VALUE) <> '-'
                   AND ROWNUM = 1),
               '病情观察'
           ),
           1,
           30
       ) AS NURSE_OBSERVE_NAME, -- 护理观察项目名称，是

       SUBSTRB(
           NVL(
               (SELECT NVL(TO_CHAR(a.NUMBER_VALUE), a.STRING_VALUE)
                  FROM mcs_doc_form_records a
                 WHERE a.template_code = f.TEMPLATE_CODE
                   AND a.node_code = '00151'
                   AND a.FORM_ID = f.ID
                   AND (a.NUMBER_VALUE IS NOT NULL OR TRIM(a.STRING_VALUE) IS NOT NULL)
                   AND ROWNUM = 1),
               '未见特殊异常'
           ),
           1,
           1000
       ) AS NURSE_OBSERVE_RESULT, -- 护理观察结果，是

       SUBSTRB(
           NVL(
               (SELECT a.STRING_VALUE
                  FROM mcs_doc_form_records a
                 WHERE a.template_code = f.TEMPLATE_CODE
                   AND a.node_code = '00171'
                   AND a.FORM_ID = f.ID
                   AND TRIM(a.STRING_VALUE) IS NOT NULL
                   AND TRIM(a.STRING_VALUE) <> '-'
                   AND ROWNUM = 1),
               '生命体征监测'
           ),
           1,
           100
       ) AS NURSE_PROJECT, -- 护理操作名称，是

       SUBSTRB(
           NVL(
               NVL(
                   (SELECT TO_CHAR(a.NUMBER_VALUE)
                      FROM mcs_doc_form_records a
                     WHERE a.template_code = f.TEMPLATE_CODE
                       AND a.node_code = '00153'
                       AND a.FORM_ID = f.ID
                       AND a.NUMBER_VALUE IS NOT NULL
                       AND ROWNUM = 1),
                   (SELECT a.STRING_VALUE
                      FROM mcs_doc_form_records a
                     WHERE a.template_code = f.TEMPLATE_CODE
                       AND a.node_code = '00149'
                       AND a.FORM_ID = f.ID
                       AND TRIM(a.STRING_VALUE) IS NOT NULL
                       AND TRIM(a.STRING_VALUE) <> '-'
                       AND ROWNUM = 1)
               ),
               '正常'
           ),
           1,
           1000
       ) AS NURSE_PROJECT_RESULT, -- 护理操作结果，是

          SUBSTRB(
           NVL(
               (SELECT CASE
                           WHEN a.STRING_VALUE LIKE '%呼吸机%'
                             OR a.STRING_VALUE LIKE '%机械通气%'
                             OR a.STRING_VALUE LIKE '%通气%'
                             OR a.STRING_VALUE LIKE '%氧疗%'
                             OR a.STRING_VALUE LIKE '%吸氧%'
                             OR a.STRING_VALUE LIKE '%高流量%'
                             OR a.STRING_VALUE LIKE '%气管插管%'
                             OR a.STRING_VALUE LIKE '%气管切开%'
                           THEN a.STRING_VALUE
                           ELSE '未使用呼吸机'
                       END
                  FROM mcs_doc_form_records a
                 WHERE a.template_code = f.TEMPLATE_CODE
                   AND a.node_code IN ('00148','00153')
                   AND a.FORM_ID = f.ID
                   AND TRIM(a.STRING_VALUE) IS NOT NULL
                   AND ROWNUM = 1),
               '未使用呼吸机'
           ),
           1,
           1000
       ) AS RM_PROJECT, -- 呼吸机监护项目

       SUBSTRB(NVL(TO_CHAR(f.created_name), TO_CHAR(f.last_updated_name)), 1, 50) AS NURSE_NAME, -- 护士签名，是

       TO_CHAR(f.created_date, 'yyyy-mm-dd hh24:mi:ss') AS RECORD_DATE, -- 签名日期时间，是

       '370104' AS DISTRICT_CODE, -- 行政区划，是

       'ADDHIS' AS EXCHANGE_TYPE, -- 交换类型，是

       TO_CHAR(SYSDATE, 'yyyy-mm-dd hh24:mi:ss') AS SYSTEM_TIME -- 数据上传时间，是

  FROM mcs_doc_form f
       JOIN inpatients p
         ON f.PATIENT_UID = p.pat_index_no

       LEFT JOIN dept_dict@his dept
         ON dept.dept_code = p.dept_code

       LEFT JOIN pat_visit@HIS pv
         ON pv.PATIENT_ID = SUBSTR(p.PATIENT_ID, 1, INSTR(p.PATIENT_ID || '_', '_') - 1)
        AND pv.VISIT_ID = p.SERIES

       LEFT JOIN DIAGNOSIS@HIS dg
         ON dg.PATIENT_ID = pv.PATIENT_ID
        AND dg.VISIT_ID = pv.VISIT_ID
        AND dg.diagnosis_type = '3'
        AND dg.diagnosis_no = '1'

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

 WHERE f.TEMPLATE_CODE = '709'
   AND f.is_valid = '1'
   AND f.created_by <> 'dba' AND pv.DISCHARGE_DATE_TIME < TO_DATE('2025-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss')
