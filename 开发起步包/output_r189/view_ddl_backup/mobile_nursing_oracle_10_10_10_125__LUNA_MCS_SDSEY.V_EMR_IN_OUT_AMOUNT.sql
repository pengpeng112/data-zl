
  CREATE OR REPLACE FORCE VIEW "LUNA_MCS_SDSEY"."V_EMR_IN_OUT_AMOUNT" ("ID", "ORG_CODE", "ORG_NAME", "ADMISSION_ID", "DEPT_CODE", "DEPT_NAME", "WARD_NAME", "EORD_NUM", "SICKBED_NUM", "NAME", "SEX_CODE", "SEX_NAME", "AGE", "AGE_MONTH", "WEIGHT", "DISEASE_CODE", "DISEASE", "NURSE_LEVEL_CODE", "NURSE_LEVEL_NAME", "NURSE_TYPE_CODE", "NURSE_TYPE_NAME", "NURSE_OBSERVE_RESULT", "NURSE_PROJECT_NAME", "NURSE_PROJECT", "NURSE_PROJECT_RESULT", "REPORT_DATE", "DRUG_USAGE", "TCM_USAGE_CODE", "TCM_USAGE_NAME", "DRUG_USAGE_RATE", "DRUG_USAGE_MEASU", "DRUG_USAGE_TIMES", "DRUG_USAGE_ALL_ME", "DRUG_NAME", "VOMIT_CODE", "URESIES_DIFF_CODE", "NURSE_NAME", "SIGNATURE_DATE", "DISTRICT_CODE", "EXCHANGE_TYPE", "SYSTEM_TIME") AS 
  SELECT
       SUBSTRB('49557032X|' || TO_CHAR(WSFL.ID), 1, 100) AS ID, -- 内码，是，唯一主键

       '49557032X' AS ORG_CODE, -- 组织机构代码，是
       '山东省第二人民医院' AS ORG_NAME, -- 组织机构名称，是

       SUBSTRB(TO_CHAR(YDZD.mrn || '|' || YDZD.series), 1, 50) AS ADMISSION_ID, -- 住院唯一标示号，是

       SUBSTRB(NVL(TO_CHAR(dept.qmpt_code), TO_CHAR(YDZD.dept_code)), 1, 20) AS DEPT_CODE, -- 科室代码

       SUBSTRB(NVL(TO_CHAR(dept.qmpt_name), TO_CHAR(YDZD.dept_name)), 1, 50) AS DEPT_NAME, -- 科室名称，是

       SUBSTRB(TO_CHAR(YDZD.WARD_NAME), 1, 50) AS WARD_NAME, -- 病区名

       CAST(NULL AS VARCHAR2(10)) AS EORD_NUM, -- 病房号；无可靠来源

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
       END AS AGE, -- 年龄，是

       CASE
           WHEN YDZD.admission_time IS NOT NULL
                AND YDZD.birth_date IS NOT NULL
                AND TRUNC(MONTHS_BETWEEN(YDZD.admission_time, YDZD.birth_date) / 12) = 0
           THEN SUBSTRB(TO_CHAR(GREATEST(0, TRUNC(MONTHS_BETWEEN(YDZD.admission_time, YDZD.birth_date)))), 1, 2)
           ELSE NULL
       END AS AGE_MONTH, -- 年龄（月）

       NVL(
           (SELECT ROUND(A.vitalsign_nval1, 2)
              FROM mcs_vital_info A
             WHERE A.vitalsign_type = '1014'
               AND A.PATIENT_UID = YDZD.Pat_Index_No
               AND A.is_valid = '1'
               AND A.vitalsign_nval1 IS NOT NULL
               AND A.vitalsign_nval1 <> 0
               AND ROWNUM = 1),
           0
       ) AS WEIGHT, -- 体重，是

       SUBSTRB(
           NVL(
               TO_CHAR(diag_dict.std_code),
               REPLACE(
                   CASE
                       WHEN INSTR(TO_CHAR(dg.diagnosis_code), '+') > 0
                       THEN SUBSTR(TO_CHAR(dg.diagnosis_code), 1, INSTR(TO_CHAR(dg.diagnosis_code), '+') - 1)
                       ELSE NVL(TO_CHAR(dg.diagnosis_code), TO_CHAR(YDZD.diagnosis_code))
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
               NVL(TO_CHAR(dg.diagnosis_desc),
                   NVL(TO_CHAR(YDZD.diagnosis_name), '-'))
           ),
           1,
           200
       ) AS DISEASE, -- 疾病诊断名称，是

       CASE
           WHEN TO_CHAR(YDZD.nursing_class) = '0' THEN '1'
           WHEN TO_CHAR(YDZD.nursing_class) = '1' THEN '2'
           WHEN TO_CHAR(YDZD.nursing_class) = '2' THEN '3'
           WHEN TO_CHAR(YDZD.nursing_class) IN ('3', '999') THEN '4'
           ELSE '4'
       END AS NURSE_LEVEL_CODE, -- 护理等级代码：1特级护理 2一级护理 3二级护理 4三级护理

       SUBSTRB(
           CASE
               WHEN TO_CHAR(YDZD.nursing_class) = '0' THEN '特级护理'
               WHEN TO_CHAR(YDZD.nursing_class) = '1' THEN '一级护理'
               WHEN TO_CHAR(YDZD.nursing_class) = '2' THEN '二级护理'
               WHEN TO_CHAR(YDZD.nursing_class) IN ('3', '999') THEN '三级护理'
               ELSE '三级护理'
           END,
           1,
           50
       ) AS NURSE_LEVEL_NAME, -- 护理等级名称，是

       CASE
           WHEN TO_CHAR(YDZD.nursing_class) = '0' THEN '2'
           WHEN TO_CHAR(YDZD.nursing_class) IN ('1', '2', '3', '999') THEN '1'
           ELSE '9'
       END AS NURSE_TYPE_CODE, -- 护理类型代码：1基础护理 2特殊护理 3辩证施护 9其它

       SUBSTRB(
           CASE
               WHEN TO_CHAR(YDZD.nursing_class) = '0' THEN '特殊护理'
               WHEN TO_CHAR(YDZD.nursing_class) IN ('1', '2', '3', '999') THEN '基础护理'
               ELSE '其它'
           END,
           1,
           50
       ) AS NURSE_TYPE_NAME, -- 护理类型描述

       SUBSTRB(
           CASE
               WHEN WSFL.dose IS NOT NULL
               THEN '入量：' || TO_CHAR(WSFL.dose) || NVL(TO_CHAR(WSFL.dose_unit), '')
               WHEN WSFL.order_name IS NOT NULL
               THEN TO_CHAR(WSFL.order_name)
               ELSE '出入量观察'
           END,
           1,
           1000
       ) AS NURSE_OBSERVE_RESULT, -- 护理观察结果，是

       SUBSTRB(
           NVL(TO_CHAR(WSFL.supply_name),
               NVL(TO_CHAR(WSFL.supply_code), '出入量记录')),
           1,
           100
       ) AS NURSE_PROJECT_NAME, -- 护理操作项目类目名称

       SUBSTRB(
           NVL(TO_CHAR(WSFL.order_name),
               NVL(TO_CHAR(WSFL.supply_name), '出入量记录')),
           1,
           100
       ) AS NURSE_PROJECT, -- 护理操作名称

       SUBSTRB(
           CASE
               WHEN WSFL.dose IS NOT NULL
               THEN TO_CHAR(WSFL.dose) || NVL(TO_CHAR(WSFL.dose_unit), '')
               ELSE '已记录'
           END,
           1,
           1000
       ) AS NURSE_PROJECT_RESULT, -- 护理操作结果

       TO_CHAR(WSFL.execute_time, 'yyyy-mm-dd hh24:mi:ss') AS REPORT_DATE, -- 记录日期时间，是

       SUBSTRB(NVL(TO_CHAR(WSFL.supply_name), '-'), 1, 100) AS DRUG_USAGE, -- 药物用法

       CAST(NULL AS CHAR(1)) AS TCM_USAGE_CODE, -- 中药使用类别代码；无可靠来源，不硬填

       CAST(NULL AS VARCHAR2(50)) AS TCM_USAGE_NAME, -- 中药使用类别描述；无可靠来源

           SUBSTRB(
           CASE
               WHEN REGEXP_LIKE(UPPER(TO_CHAR(WSFL.frequence)), 'Q24H|QD|QN|QM') THEN '1'
               WHEN REGEXP_LIKE(UPPER(TO_CHAR(WSFL.frequence)), 'Q12H|BID') THEN '2'
               WHEN REGEXP_LIKE(UPPER(TO_CHAR(WSFL.frequence)), 'Q8H|TID') THEN '3'
               WHEN REGEXP_LIKE(UPPER(TO_CHAR(WSFL.frequence)), 'Q6H|QID') THEN '4'
               WHEN REGEXP_LIKE(UPPER(TO_CHAR(WSFL.frequence)), 'Q4H') THEN '6'
               WHEN REGEXP_LIKE(UPPER(TO_CHAR(WSFL.frequence)), 'Q2H') THEN '12'
               WHEN REGEXP_LIKE(UPPER(TO_CHAR(WSFL.frequence)), 'Q1H|QH') THEN '24'
               WHEN REGEXP_LIKE(TO_CHAR(WSFL.frequence), '^[0-9]{1,2}$')
               THEN TO_CHAR(WSFL.frequence)
               ELSE NULL
           END,
           1,
           2
       ) AS DRUG_USAGE_RATE, -- 药物使用频率

       SUBSTRB(NVL(TO_CHAR(WSFL.dose_unit), '-'), 1, 6) AS DRUG_USAGE_MEASU, -- 药物使用计量单位

       CASE
           WHEN REGEXP_LIKE(REPLACE(TO_CHAR(WSFL.dose), ' ', ''), '^[0-9]+(\.[0-9]+)?$')
                AND TO_NUMBER(REPLACE(TO_CHAR(WSFL.dose), ' ', '')) <= 999.99
           THEN ROUND(TO_NUMBER(REPLACE(TO_CHAR(WSFL.dose), ' ', '')), 2)
           ELSE NULL
       END AS DRUG_USAGE_TIMES, -- 药物使用次计量，NUMBER(5,2)

       CASE
           WHEN REGEXP_LIKE(REPLACE(TO_CHAR(WSFL.dose), ' ', ''), '^[0-9]+(\.[0-9]+)?$')
           THEN ROUND(TO_NUMBER(REPLACE(TO_CHAR(WSFL.dose), ' ', '')), 2)
           ELSE NULL
       END AS DRUG_USAGE_ALL_ME, -- 药物使用总剂量，NUMBER(12,2)

       SUBSTRB(NVL(TO_CHAR(WSFL.order_name), '-'), 1, 50) AS DRUG_NAME, -- 药物名称

       '0' AS VOMIT_CODE, -- 呕吐标志：1是 0否；旧SQL为2，不符合标准

       '0' AS URESIES_DIFF_CODE, -- 排尿困难标志：1是 0否；旧SQL为2，不符合标准

       SUBSTRB(NVL(TO_CHAR(WSFL.executer_name), '-'), 1, 50) AS NURSE_NAME, -- 护士签名，是

       TO_CHAR(WSFL.execute_time, 'yyyy-mm-dd hh24:mi:ss') AS SIGNATURE_DATE, -- 签名日期，是

       '370104' AS DISTRICT_CODE, -- 行政区划，是

       'ADDHIS' AS EXCHANGE_TYPE, -- 交换类型，是

       TO_CHAR(SYSDATE, 'yyyy-mm-dd hh24:mi:ss') AS SYSTEM_TIME -- 数据上传时间，是

  FROM inpatients YDZD
       JOIN mcs_order_schedule WSFL
         ON WSFL.PATIENT_UID = YDZD.pat_index_no

       LEFT JOIN dept_dict@his dept
         ON dept.dept_code = YDZD.dept_code

       LEFT JOIN pat_visit@HIS pv
         ON pv.PATIENT_ID = SUBSTR(YDZD.PATIENT_ID, 1, INSTR(YDZD.PATIENT_ID || '_', '_') - 1)
        AND pv.VISIT_ID = YDZD.SERIES

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

 WHERE WSFL.execute_time IS NOT NULL
   AND WSFL.Executer_Name IS NOT NULL AND pv.DISCHARGE_DATE_TIME < TO_DATE('2025-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss')
