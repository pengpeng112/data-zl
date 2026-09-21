
  CREATE OR REPLACE FORCE VIEW "LUNA_MCS_SDSEY"."V_EMR_GENERAL_NURSING" ("ID", "ORG_CODE", "ORG_NAME", "ADMISSION_ID", "DEPT_CODE", "DEPT_NAME", "WARD_NAME", "EORD_NUM", "SICKBED_NUM", "NAME", "SEX_CODE", "SEX_NAME", "AGE", "AGE_MONTH", "DISEASE_CODE", "DISEASE", "NURSE_LEVEL_CODE", "NURSE_LEVEL_NAME", "NURSE_TYPE_CODE", "NURSE_TYPE_NAME", "ALLERGIES", "WEIGHT", "TEMPERATURE", "BREATHING_RATE", "PULSE_RATE", "PRESSURE_H", "PRESSURE_L", "STATRRATION", "FOOT_DORSUM_CODE", "DIET_CODE", "DIET_NAME", "CATHETER_NURSE_NOTE", "CATHETER_NURSE_CODE", "CATHETER_NURSE_NAME", "SKIN_NURSE", "NUTRITION_NURSE", "DIEF_GUIDE_CODE", "DIEF_GUIDE_NAME", "PHYCHOLOGICAL_NURSE_CD", "PHYCHOLOGICAL_NURSE_NA", "SECURITY_NURSE_CODE", "SECURITY_NURSE_NAME", "BRIEF_ILLNESS", "NURSE_OBSERVE_NAME", "NURSE_OBSERVE_RESULT", "NURSE_PROJECT", "NURSE_PROJECT_NAME", "NURSE_PROJECT_RESULT", "OUT_CHECK_CODE", "IN_CHECK_CODE", "OUT_ASSESSMENT_CODE", "IN_ASSESSMENT_CODE", "ISOLATION_CODE", "ISOLATION_TYPE_CODE", "ISOLATION_TYPE_NAME", "NURSE_NAME", "RECORD_DATE", "DISTRICT_CODE", "EXCHANGE_TYPE", "SYSTEM_TIME") AS 
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
       END AS AGE, -- 年龄（岁），是

       CASE
           WHEN p.admission_time IS NOT NULL
                AND p.birth_date IS NOT NULL
                AND TRUNC(MONTHS_BETWEEN(p.admission_time, p.birth_date) / 12) = 0
           THEN SUBSTRB(TO_CHAR(GREATEST(0, TRUNC(MONTHS_BETWEEN(p.admission_time, p.birth_date)))), 1, 8)
           ELSE NULL
       END AS AGE_MONTH, -- 年龄（月）

     nvl(  SUBSTRB(
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
           50
       ),'-') AS DISEASE_CODE, -- 疾病诊断编码
                 nvl( SUBSTRB(
         NVL(
               TO_CHAR(diag_dict.std_name),
               REPLACE(
                   CASE
                       WHEN INSTR(TO_CHAR(dg.diagnosis_desc), '+') > 0
                       THEN SUBSTR(TO_CHAR(dg.diagnosis_desc), 1, INSTR(TO_CHAR(dg.diagnosis_desc), '+') - 1)
                       ELSE TO_CHAR(dg.diagnosis_desc)
                   END,
                   '*',
                   ''
               )
           ),
           1,
           50
       ) ,'-')   AS DISEASE, -- 疾病诊断名称，是
       CASE
           WHEN TO_CHAR(p.nursing_class) = '0' THEN 1
           WHEN TO_CHAR(p.nursing_class) = '1' THEN 2
           WHEN TO_CHAR(p.nursing_class) = '2' THEN 3
           WHEN TO_CHAR(p.nursing_class) IN ('3', '999') THEN 4
           ELSE 4
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
       ) AS NURSE_LEVEL_NAME, -- 护理等级名称

          SUBSTRB(
           CASE
               WHEN TO_CHAR(p.nursing_class) = '0' THEN '2'              -- 特级护理 -> 特殊护理
               WHEN TO_CHAR(p.nursing_class) IN ('1', '2', '3', '999') THEN '1' -- 一级/二级/三级护理 -> 基础护理
               ELSE '9'                                                  -- 其他 -> 其它
           END,
           1,
           1
       ) AS NURSE_TYPE_CODE, -- 护理类型代码：1基础护理 2特殊护理 3辩证施护 9其它

       SUBSTRB(
           CASE
               WHEN TO_CHAR(p.nursing_class) = '0' THEN '特殊护理'
               WHEN TO_CHAR(p.nursing_class) IN ('1', '2', '3', '999') THEN '基础护理'
               ELSE '其它'
           END,
           1,
           50
       ) AS NURSE_TYPE_NAME, -- 护理类型描述

       CAST(NULL AS VARCHAR2(1000)) AS ALLERGIES, -- 过敏史；旧 SQL 无可靠来源

       CAST(0 AS NUMBER(6,2)) AS WEIGHT, -- 体重；旧 SQL固定0，后续需确认真实节点

       NVL(
           (SELECT ROUND(TO_NUMBER(REGEXP_SUBSTR(a.STRING_VALUE, '[0-9]+(\.[0-9]+)?')), 2)
              FROM mcs_doc_form_records a
             WHERE a.template_code = f.TEMPLATE_CODE
               AND a.node_code  in（ '00172','00112','00115','00114','00116','K01005')
               AND a.FORM_ID = f.ID
               AND REGEXP_LIKE(a.STRING_VALUE, '[0-9]')
               AND ROWNUM = 1),
           0
       ) AS TEMPERATURE, -- 体温，是

       NVL(
           (SELECT TO_NUMBER(REGEXP_SUBSTR(TO_CHAR(a.NUMBER_VALUE), '[0-9]+'))
              FROM mcs_doc_form_records a
             WHERE a.template_code = f.TEMPLATE_CODE
               AND a.node_code = '00122'
               AND a.FORM_ID = f.ID
               AND REGEXP_LIKE(TO_CHAR(a.NUMBER_VALUE), '[0-9]')
               AND ROWNUM = 1),
           0
       ) AS BREATHING_RATE, -- 呼吸频率，是

       NVL(
           (SELECT TO_NUMBER(REGEXP_SUBSTR(a.STRING_VALUE, '[0-9]+'))
              FROM mcs_doc_form_records a
             WHERE a.template_code = f.TEMPLATE_CODE
               AND a.node_code  in ( '00174','00121')
               AND a.FORM_ID = f.ID
               AND REGEXP_LIKE(a.STRING_VALUE, '[0-9]')
               AND ROWNUM = 1),
           0
       ) AS PULSE_RATE, -- 脉率，是

       NVL(
           (SELECT TO_NUMBER(REGEXP_SUBSTR(TO_CHAR(a.NUMBER_VALUE), '[0-9]+'))
              FROM mcs_doc_form_records a
             WHERE a.template_code = f.TEMPLATE_CODE
               AND a.node_code = '00117'
               AND a.FORM_ID = f.ID
               AND REGEXP_LIKE(TO_CHAR(a.NUMBER_VALUE), '[0-9]')
               AND ROWNUM = 1),
           0
       ) AS PRESSURE_H, -- 收缩压，是

       NVL(
           (SELECT TO_NUMBER(REGEXP_SUBSTR(TO_CHAR(a.NUMBER_VALUE), '[0-9]+'))
              FROM mcs_doc_form_records a
             WHERE a.template_code = f.TEMPLATE_CODE
               AND a.node_code = '00119'
               AND a.FORM_ID = f.ID
               AND REGEXP_LIKE(TO_CHAR(a.NUMBER_VALUE), '[0-9]')
               AND ROWNUM = 1),
           0
       ) AS PRESSURE_L, -- 舒张压，是

       CAST(0 AS NUMBER(4,1)) AS STATRRATION, -- 血氧饱和度；旧SQL取00024不合理，暂置0，需要确认真实节点

       '0' AS FOOT_DORSUM_CODE, -- 足背动脉搏动标志，是；1是0否

       '1' AS DIET_CODE, -- 饮食情况代码，是；1良好

       '良好' AS DIET_NAME, -- 饮食情况描述，是

       SUBSTRB(
           NVL(
               (SELECT a.STRING_VALUE
                  FROM mcs_doc_form_records a
                 WHERE a.template_code = f.TEMPLATE_CODE
                   AND a.node_code = '00148'
                   AND a.FORM_ID = f.ID
                   AND ROWNUM = 1),
               '无'
           ),
           1,
           1000
       ) AS CATHETER_NURSE_NOTE, -- 导管护理描述，是

       '1' AS CATHETER_NURSE_CODE, -- 气管护理代码，是；1翻身拍背

       '翻身拍背' AS CATHETER_NURSE_NAME, -- 气管护理描述，是

       SUBSTRB(
           CASE
               WHEN (SELECT COUNT(*)
                       FROM mcs_doc_form_records a
                      WHERE a.template_code = f.TEMPLATE_CODE
                        AND a.node_code = '00156'
                        AND a.FORM_ID = f.ID
                        AND a.NUMBER_VALUE IS NOT NULL) > 0 THEN '气垫床'
               WHEN (SELECT COUNT(*)
                       FROM mcs_doc_form_records a
                      WHERE a.template_code = f.TEMPLATE_CODE
                        AND a.node_code = '00157'
                        AND a.FORM_ID = f.ID
                        AND a.NUMBER_VALUE IS NOT NULL) > 0 THEN '定时翻身（1h）'
               WHEN (SELECT COUNT(*)
                       FROM mcs_doc_form_records a
                      WHERE a.template_code = f.TEMPLATE_CODE
                        AND a.node_code = '00158'
                        AND a.FORM_ID = f.ID
                        AND a.NUMBER_VALUE IS NOT NULL) > 0 THEN '定时翻身（2h）'
               WHEN (SELECT COUNT(*)
                       FROM mcs_doc_form_records a
                      WHERE a.template_code = f.TEMPLATE_CODE
                        AND a.node_code = '00159'
                        AND a.FORM_ID = f.ID
                        AND a.NUMBER_VALUE IS NOT NULL) > 0 THEN '减压措施'
               WHEN (SELECT COUNT(*)
                       FROM mcs_doc_form_records a
                      WHERE a.template_code = f.TEMPLATE_CODE
                        AND a.node_code = '00160'
                        AND a.FORM_ID = f.ID
                        AND a.NUMBER_VALUE IS NOT NULL) > 0 THEN '伤口换药'
               ELSE '无'
           END,
           1,
           50
       ) AS SKIN_NURSE, -- 皮肤护理

       '无' AS NUTRITION_NURSE, -- 营养护理

       '01' AS DIEF_GUIDE_CODE, -- 饮食指导代码，是；01普通饮食

       '普通饮食' AS DIEF_GUIDE_NAME, -- 饮食指导描述，是

       '1' AS PHYCHOLOGICAL_NURSE_CD, -- 心理护理代码

       '根据病人心理状况施行心理护理' AS PHYCHOLOGICAL_NURSE_NA, -- 心理护理描述

       CAST(NULL AS CHAR(1)) AS SECURITY_NURSE_CODE, -- 安全护理代码；非必填，无可靠来源

       CAST(NULL AS VARCHAR2(50)) AS SECURITY_NURSE_NAME, -- 安全护理描述

       SUBSTRB(
           NVL(
               (SELECT a.STRING_VALUE
                  FROM mcs_doc_form_records a
                 WHERE a.template_code = f.TEMPLATE_CODE
                   AND a.node_code = '00093'
                   AND a.FORM_ID = f.ID
                   AND ROWNUM = 1),
               '-'
           ),
           1,
           2000
       ) AS BRIEF_ILLNESS, -- 简要病情，是

       SUBSTRB(
           NVL(
               (SELECT a.STRING_VALUE
                  FROM mcs_doc_form_records a
                 WHERE a.template_code = f.TEMPLATE_CODE
                   AND a.node_code = '00088'
                   AND a.FORM_ID = f.ID
                   AND ROWNUM = 1),
               '-'
           ),
           1,
           30
       ) AS NURSE_OBSERVE_NAME, -- 护理观察项目名称，是

       SUBSTRB(
           NVL(
               (SELECT a.STRING_VALUE
                  FROM mcs_doc_form_records a
                 WHERE a.template_code = f.TEMPLATE_CODE
                   AND a.node_code = '00089'
                   AND a.FORM_ID = f.ID
                   AND ROWNUM = 1),
               '-'
           ),
           1,
           1000
       ) AS NURSE_OBSERVE_RESULT, -- 护理观察结果，是

       '-' AS NURSE_PROJECT, -- 护理操作名称，是

       '-' AS NURSE_PROJECT_NAME, -- 护理操作项目类目名称，是

       '0' AS NURSE_PROJECT_RESULT, -- 护理操作结果，是

       '0' AS OUT_CHECK_CODE, -- 发出手术安全核对表标志；1是0否

       '0' AS IN_CHECK_CODE, -- 收回手术安全核对表标志；1是0否

       '0' AS OUT_ASSESSMENT_CODE, -- 发出手术风险评估表标志；1是0否

       '0' AS IN_ASSESSMENT_CODE, -- 收回手术风险评估表标志；1是0否

       '0' AS ISOLATION_CODE, -- 隔离标志，是；1是0否

       CAST(NULL AS CHAR(1)) AS ISOLATION_TYPE_CODE, -- 隔离种类代码

       CAST(NULL AS VARCHAR2(50)) AS ISOLATION_TYPE_NAME, -- 隔离种类描述

       SUBSTRB(NVL(TO_CHAR(f.Created_Name), TO_CHAR(f.last_updated_name)), 1, 50) AS NURSE_NAME, -- 护士签名，是

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

 WHERE f.TEMPLATE_CODE = '572'
   AND f.is_valid = '1'
   AND f.created_by <> 'dba'    AND pv.DISCHARGE_DATE_TIME < TO_DATE('2025-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss')
