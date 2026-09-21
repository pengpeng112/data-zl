
  CREATE OR REPLACE FORCE VIEW "LUNA_MCS_SDSEY"."V_EMR_ADMISSION_ASSESSMENT" ("ID", "ORG_CODE", "ORG_NAME", "ADMISSION_ID", "DEPT_CODE", "DEPT_NAME", "WARD_NAME", "EORD_NUM", "SICKBED_NUM", "NAME", "SEX_CODE", "SEX_NAME", "AGE", "AGE_MONTH", "ADMISSION_TYPE", "ADMISSION_DIAGNOSIS_CD", "ADMISSION_DIAGNOSIS_NA", "ADMISSION_DATE", "CHIEF_COMPLAINT", "WEIGHT", "BREATHING_RATE", "PULSE_RATE", "PRESSURE_H", "PRESSURE_L", "ADMISSION_CAUSE", "ADMISSION_TYPE_CODE", "ADMISSION_TYPE_NAME", "APGAR", "DIET_CODE", "DIET_NAME", "DEVELOPMENT_CODE", "DEVELOPMENT_NAME", "SPIRIT_CODE", "SLEEP_CODE", "SPECIAL_CASE", "PHYCHOLOGICAL_CD", "PHYCHOLOGICAL_NA", "NUTRITION_CODE", "NUTRITION_NAME", "SELF_CARE_ABILITY", "SELF_CARE_ABI_NA", "ALLERGY_HISTORY_FIR", "HEALTH_STATUS_CODE", "DISEASE_HIS", "INFECTION_FLAG", "INFECTION_HISTORY", "VACCINATION_HISTORY", "SURGERY_HISTORY", "BT_HISTORY", "ALLERGY_HISTORY_SEN", "FAMILY_HISTORY", "SMOKE_STATUS", "STOP_SMOKE_DAY", "SMOKE_STATUS_CODE", "SMOKE_STATUS_NAME", "SMOKE_COUNT_DAY", "DRINK_STATUS", "DRINK_FREQUENCY", "DRINK_NAME", "DRINK_AMOUNT", "NOTICE_DOC_CODE", "NOTICE_DOC_DATE", "ASSESSMENT_DATE", "RES_NURSE_NAME", "ACCEPTS_NURS_NAME", "SIGNATURE_DATE", "DISTRICT_CODE", "EXCHANGE_TYPE", "SYSTEM_TIME") AS 
  SELECT
       SUBSTRB(TO_CHAR(f.ID), 1, 100) AS ID, -- 内码，是，唯一主键

       '49557032X' AS ORG_CODE, -- 组织机构代码，是
       '山东省第二人民医院' AS ORG_NAME, -- 组织机构名称，是

       SUBSTRB(TO_CHAR(YDZD.mrn ||'|'|| YDZD.series), 1, 50) AS ADMISSION_ID, -- 住院唯一标示号，是；沿用原 ZYLSH 口径

       SUBSTRB(TO_CHAR(dept.qmpt_code), 1, 20) AS DEPT_CODE, -- 科室代码
       SUBSTRB(TO_CHAR(dept.qmpt_name), 1, 50) AS DEPT_NAME, -- 科室名称，是
       SUBSTRB(TO_CHAR(YDZD.WARD_NAME), 1, 50) AS WARD_NAME, -- 病区名称

       CAST(NULL AS VARCHAR2(10)) AS EORD_NUM, -- 病房号；原 SQL 固定 '-'，无可靠病房号来源，暂不硬填
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
           (SELECT a.assess_value
              FROM mcs_assess_form_record a
             WHERE a.assess_code = 'Z01028'
               AND a.FORM_ID = f.ID
               AND ROWNUM = 1),
           1,
           20
       ) AS ADMISSION_TYPE, -- 入病房方式

       diag_dict.std_code  AS ADMISSION_DIAGNOSIS_CD, -- 入院诊断编码；需要确认移动护理库 ICD 字段，暂不硬编

       diag_dict.std_name AS ADMISSION_DIAGNOSIS_NA, -- 入院诊断描述，是

       TO_CHAR(p.ADMISSION_DATE_TIME, 'yyyy-mm-dd hh24:mi:ss') AS ADMISSION_DATE, -- 入院日期时间，是

       SUBSTRB(NVL(TO_CHAR(YDZD.diagnosis_name), '-'), 1, 1000) AS CHIEF_COMPLAINT, -- 主要症状；原 SQL 使用 diagnosis_name，先沿用

       NVL(
           (SELECT ROUND(TO_NUMBER(REGEXP_SUBSTR(a.assess_value, '[0-9]+(\.[0-9]+)?')), 2)
              FROM mcs_assess_form_record a
             WHERE a.assess_code = 'K02006.n'
               AND a.FORM_ID = f.ID
               AND ROWNUM = 1),
           0
       ) AS WEIGHT, -- 体重（kg），是

       NVL(
           (SELECT ROUND(TO_NUMBER(REGEXP_SUBSTR(a.assess_value, '[0-9]+(\.[0-9]+)?')))
              FROM mcs_assess_form_record a
             WHERE a.assess_code = 'K01010'
               AND a.FORM_ID = f.ID
               AND ROWNUM = 1),
           0
       ) AS BREATHING_RATE, -- 呼吸频率（次/min），是

       NVL(
           (SELECT ROUND(TO_NUMBER(REGEXP_SUBSTR(a.assess_value, '[0-9]+(\.[0-9]+)?')))
              FROM mcs_assess_form_record a
             WHERE a.assess_code = 'K01009'
               AND a.FORM_ID = f.ID
               AND ROWNUM = 1),
           0
       ) AS PULSE_RATE, -- 脉率（次/min），是

       NVL(
           (SELECT ROUND(TO_NUMBER(REGEXP_SUBSTR(a.assess_value, '[0-9]+(\.[0-9]+)?')))
              FROM mcs_assess_form_record a
             WHERE a.assess_code = 'K01011'
               AND a.FORM_ID = f.ID
               AND ROWNUM = 1),
           0
       ) AS PRESSURE_H, -- 收缩压（mmHg），是

       NVL(
           (SELECT ROUND(TO_NUMBER(REGEXP_SUBSTR(a.assess_value, '[0-9]+(\.[0-9]+)?')))
              FROM mcs_assess_form_record a
             WHERE a.assess_code = 'K01012'
               AND a.FORM_ID = f.ID
               AND ROWNUM = 1),
           0
       ) AS PRESSURE_L, -- 舒张压（mmHg），是

       SUBSTRB(NVL(TO_CHAR(YDZD.diagnosis_name), '-'), 1, 1000) AS ADMISSION_CAUSE, -- 入院原因

           CASE
           WHEN (SELECT a.assess_value
                   FROM mcs_assess_form_record a
                  WHERE a.assess_code = 'Z01026'
                    AND a.FORM_ID = f.ID
                    AND ROWNUM = 1) = '门诊'
           THEN '1'
           WHEN (SELECT a.assess_value
                   FROM mcs_assess_form_record a
                  WHERE a.assess_code = 'Z01026'
                    AND a.FORM_ID = f.ID
                    AND ROWNUM = 1) = '急诊'
           THEN '2'
           WHEN (SELECT a.assess_value
                   FROM mcs_assess_form_record a
                  WHERE a.assess_code = 'Z01026'
                    AND a.FORM_ID = f.ID
                    AND ROWNUM = 1) = '转入'
           THEN '3'
           ELSE '9'
       END AS ADMISSION_TYPE_CODE,

       CASE
           WHEN (SELECT a.assess_value
                   FROM mcs_assess_form_record a
                  WHERE a.assess_code = 'Z01026'
                    AND a.FORM_ID = f.ID
                    AND ROWNUM = 1) = '门诊'
           THEN '门诊'
           WHEN (SELECT a.assess_value
                   FROM mcs_assess_form_record a
                  WHERE a.assess_code = 'Z01026'
                    AND a.FORM_ID = f.ID
                    AND ROWNUM = 1) = '急诊'
           THEN '急诊'
           WHEN (SELECT a.assess_value
                   FROM mcs_assess_form_record a
                  WHERE a.assess_code = 'Z01026'
                    AND a.FORM_ID = f.ID
                    AND ROWNUM = 1) = '转入'
           THEN '其他医疗机构转入'
           ELSE '其他'
       END AS ADMISSION_TYPE_NAME,

       CAST(0 AS NUMBER) AS APGAR, -- Apgar评分值；原 SQL 固定 0

       NVL(
           (SELECT CASE
                       WHEN a.assess_code_type LIKE '%.1' OR a.assess_value LIKE '1.%' OR a.assess_value = '良好' THEN '1'
                       WHEN a.assess_code_type LIKE '%.2' OR a.assess_value LIKE '2.%' OR a.assess_value = '一般' THEN '2'
                       WHEN a.assess_code_type LIKE '%.3' OR a.assess_value LIKE '3.%' OR a.assess_value = '较差' THEN '3'
                       ELSE '9'
                   END
              FROM mcs_assess_form_record a
             WHERE a.assess_code = 'J01018'
               AND a.FORM_ID = f.ID
               AND ROWNUM = 1),
           '1'
       ) AS DIET_CODE, -- 饮食情况代码，是

       NVL(
           (SELECT SUBSTRB(
                       CASE
                           WHEN a.assess_code_type LIKE '%.1' OR a.assess_value LIKE '1.%' OR a.assess_value = '良好' THEN '良好'
                           WHEN a.assess_code_type LIKE '%.2' OR a.assess_value LIKE '2.%' OR a.assess_value = '一般' THEN '一般'
                           WHEN a.assess_code_type LIKE '%.3' OR a.assess_value LIKE '3.%' OR a.assess_value = '较差' THEN '较差'
                           WHEN INSTR(a.assess_value, '.') > 0 THEN SUBSTR(a.assess_value, INSTR(a.assess_value, '.', -1) + 1)
                           ELSE a.assess_value
                       END,
                       1,
                       50
                   )
              FROM mcs_assess_form_record a
             WHERE a.assess_code = 'J01018'
               AND a.FORM_ID = f.ID
               AND ROWNUM = 1),
           '良好'
       ) AS DIET_NAME, -- 饮食情况描述，是

       CAST(NULL AS CHAR(1)) AS DEVELOPMENT_CODE, -- 发育程度代码；原 SQL 无可靠来源
       CAST(NULL AS VARCHAR2(50)) AS DEVELOPMENT_NAME, -- 发育程度描述；原 SQL 无可靠来源
       CAST(NULL AS CHAR(1)) AS SPIRIT_CODE, -- 精神状态正常标志；原 SQL 无可靠标准来源
       CAST(NULL AS VARCHAR2(1000)) AS SLEEP_CODE, -- 睡眠状况；原 SQL 无可靠来源
       CAST(NULL AS VARCHAR2(1000)) AS SPECIAL_CASE, -- 特殊情况；原 SQL 无可靠来源
       CAST(NULL AS CHAR(1)) AS PHYCHOLOGICAL_CD, -- 心理状态代码；原 SQL 无可靠来源
       CAST(NULL AS VARCHAR2(50)) AS PHYCHOLOGICAL_NA, -- 心理状态描述；原 SQL 无可靠来源
        NVL(
           (SELECT CASE
                       WHEN TRIM(a.assess_value) IN ('营养摄入良好', '良好') THEN '1'
                       WHEN TRIM(a.assess_value) IN ('营养摄入适当', '适当') THEN '2'
                       WHEN TRIM(a.assess_value) IN ('营养摄入不足', '不足', '非常差') THEN '3'
                       ELSE NULL
                   END
              FROM mcs_assess_form_record a
             WHERE a.assess_code IN ('J02001', 'J02001.1', 'J02001.2', 'J02001.3', 'J02001.4')
               AND a.FORM_ID = f.ID
               AND ROWNUM = 1),
           '2'
       ) AS NUTRITION_CODE, -- 营养状态代码

       NVL(
           (SELECT CASE
                       WHEN TRIM(a.assess_value) IN ('营养摄入良好', '良好') THEN '良好'
                       WHEN TRIM(a.assess_value) IN ('营养摄入适当', '适当') THEN '中等'
                       WHEN TRIM(a.assess_value) IN ('营养摄入不足', '不足', '非常差') THEN '差'
                       ELSE NULL
                   END
              FROM mcs_assess_form_record a
             WHERE a.assess_code IN ('J02001', 'J02001.1', 'J02001.2', 'J02001.3', 'J02001.4')
               AND a.FORM_ID = f.ID
               AND ROWNUM = 1),
           '中等'
       ) AS NUTRITION_NAME, -- 营养状态描述

       NVL(
           (SELECT CASE
                       WHEN TO_NUMBER(REGEXP_SUBSTR(aa.total_score, '[0-9]+(\.[0-9]+)?')) = 100 THEN '1'
                       WHEN TO_NUMBER(REGEXP_SUBSTR(aa.total_score, '[0-9]+(\.[0-9]+)?')) > 60
                            AND TO_NUMBER(REGEXP_SUBSTR(aa.total_score, '[0-9]+(\.[0-9]+)?')) < 100 THEN '2'
                       WHEN TO_NUMBER(REGEXP_SUBSTR(aa.total_score, '[0-9]+(\.[0-9]+)?')) <= 60 THEN '3'
                       ELSE '1'
                   END
              FROM mcs_doc_form aa
             WHERE aa.assess_form_id = f.ID
               AND ROWNUM = 1),
           '1'
       ) AS SELF_CARE_ABILITY, -- 自理能力代码，是

       NVL(
           (SELECT CASE
                       WHEN TO_NUMBER(REGEXP_SUBSTR(aa.total_score, '[0-9]+(\.[0-9]+)?')) = 100 THEN '完全自理'
                       WHEN TO_NUMBER(REGEXP_SUBSTR(aa.total_score, '[0-9]+(\.[0-9]+)?')) > 60
                            AND TO_NUMBER(REGEXP_SUBSTR(aa.total_score, '[0-9]+(\.[0-9]+)?')) < 100 THEN '部分自理'
                       WHEN TO_NUMBER(REGEXP_SUBSTR(aa.total_score, '[0-9]+(\.[0-9]+)?')) <= 60 THEN '不能自理'
                       ELSE '完全自理'
                   END
              FROM mcs_doc_form aa
             WHERE aa.assess_form_id = f.ID
               AND ROWNUM = 1),
           '完全自理'
       ) AS SELF_CARE_ABI_NA, -- 自理能力描述

       SUBSTRB(
           NVL(
               (SELECT a.assess_value
                  FROM mcs_assess_form_record a
                 WHERE a.assess_code = 'Z04031'
                   AND a.FORM_ID = f.ID
                   AND ROWNUM = 1),
               '无'
           ),
           1,
           1000
       ) AS ALLERGY_HISTORY_FIR, -- 过敏史

       CASE
           WHEN NVL(
                    (SELECT a.assess_value
                       FROM mcs_assess_form_record a
                      WHERE a.assess_code = 'Z04002'
                        AND a.FORM_ID = f.ID
                        AND ROWNUM = 1),
                    '无'
                ) IN ('无', '否', '没有', '无特殊')
           THEN '1'
           ELSE '0'
       END AS HEALTH_STATUS_CODE, -- 一般健康状况标志；1是、0否

       SUBSTRB(
           NVL(
               (SELECT a.assess_value
                  FROM mcs_assess_form_record a
                 WHERE a.assess_code = 'Z04002'
                   AND a.FORM_ID = f.ID
                   AND ROWNUM = 1),
               '无'
           ),
           1,
           1000
       ) AS DISEASE_HIS, -- 疾病史（含外伤）

       '0' AS INFECTION_FLAG, -- 患者传染性标志；原 SQL 固定为否，按标准改为 0

       CAST(NULL AS VARCHAR2(1000)) AS INFECTION_HISTORY, -- 传染病史；原 SQL 无可靠来源
       CAST(NULL AS VARCHAR2(1000)) AS VACCINATION_HISTORY, -- 预防接种史；原 SQL 无可靠来源

       SUBSTRB(
           NVL(
               (SELECT a.assess_value
                  FROM mcs_assess_form_record a
                 WHERE a.assess_code = 'Z04015'
                   AND a.FORM_ID = f.ID
                   AND ROWNUM = 1),
               '无'
           ),
           1,
           1000
       ) AS SURGERY_HISTORY, -- 手术史

       SUBSTRB(
           NVL(
               (SELECT a.assess_value
                  FROM mcs_assess_form_record a
                 WHERE a.assess_code = 'Z04021'
                   AND a.FORM_ID = f.ID
                   AND ROWNUM = 1),
               '无'
           ),
           1,
           1000
       ) AS BT_HISTORY, -- 输血史

       SUBSTRB(
           NVL(
               (SELECT a.assess_value
                  FROM mcs_assess_form_record a
                 WHERE a.assess_code = 'Z04031'
                   AND a.FORM_ID = f.ID
                   AND ROWNUM = 1),
               '无'
           ),
           1,
           1000
       ) AS ALLERGY_HISTORY_SEN, -- 过敏史

       SUBSTRB(
           NVL(
               (SELECT a.assess_value
                  FROM mcs_assess_form_record a
                 WHERE a.assess_code = 'Z06005'
                   AND a.FORM_ID = f.ID
                   AND ROWNUM = 1),
               '无'
           ),
           1,
           1000
       ) AS FAMILY_HISTORY, -- 家族史

       CASE
           WHEN (SELECT a.assess_value
                   FROM mcs_assess_form_record a
                  WHERE a.assess_code = 'Z05014'
                    AND a.FORM_ID = f.ID
                    AND ROWNUM = 1) = '是'
           THEN '1'
           ELSE '0'
       END AS SMOKE_STATUS, -- 吸烟标志；标准为 1是、0否

       NVL(
           (SELECT ROUND(TO_NUMBER(REGEXP_SUBSTR(a.assess_value, '[0-9]+(\.[0-9]+)?')) * 365)
              FROM mcs_assess_form_record a
             WHERE a.assess_code = 'Z05019'
               AND a.FORM_ID = f.ID
               AND ROWNUM = 1),
           0
       ) AS STOP_SMOKE_DAY, -- 停止吸烟天数

       NVL(
           (SELECT CASE
                       WHEN (SELECT b.assess_value
                               FROM mcs_assess_form_record b
                              WHERE b.assess_code = 'Z05014'
                                AND b.FORM_ID = f.ID
                                AND ROWNUM = 1) = '是'
                            AND NVL((SELECT c.assess_value
                                       FROM mcs_assess_form_record c
                                      WHERE c.assess_code = 'Z05018'
                                        AND c.FORM_ID = f.ID
                                        AND ROWNUM = 1), '否') = '否'
                       THEN '3'
                       WHEN (SELECT d.assess_value
                               FROM mcs_assess_form_record d
                              WHERE d.assess_code = 'Z05018'
                                AND d.FORM_ID = f.ID
                                AND ROWNUM = 1) = '是'
                       THEN '2'
                       ELSE '1'
                   END
              FROM dual),
           '1'
       ) AS SMOKE_STATUS_CODE, -- 吸烟状况代码

       NVL(
           (SELECT CASE
                       WHEN (SELECT b.assess_value
                               FROM mcs_assess_form_record b
                              WHERE b.assess_code = 'Z05014'
                                AND b.FORM_ID = f.ID
                                AND ROWNUM = 1) = '是'
                            AND NVL((SELECT c.assess_value
                                       FROM mcs_assess_form_record c
                                      WHERE c.assess_code = 'Z05018'
                                        AND c.FORM_ID = f.ID
                                        AND ROWNUM = 1), '否') = '否'
                       THEN '吸烟'
                       WHEN (SELECT d.assess_value
                               FROM mcs_assess_form_record d
                              WHERE d.assess_code = 'Z05018'
                                AND d.FORM_ID = f.ID
                                AND ROWNUM = 1) = '是'
                       THEN '过去吸，已戒烟'
                       ELSE '从不吸烟'
                   END
              FROM dual),
           '从不吸烟'
       ) AS SMOKE_STATUS_NAME, -- 吸烟状况描述

       NVL(
           (SELECT ROUND(TO_NUMBER(REGEXP_SUBSTR(a.assess_value, '[0-9]+(\.[0-9]+)?')))
              FROM mcs_assess_form_record a
             WHERE a.assess_code = 'Z05017'
               AND a.FORM_ID = f.ID
               AND ROWNUM = 1),
           0
       ) AS SMOKE_COUNT_DAY, -- 日吸烟量（支）

       CASE
           WHEN (SELECT a.assess_code_type
                   FROM mcs_assess_form_record a
                  WHERE a.assess_code = 'Z05023'
                    AND a.FORM_ID = f.ID
                    AND ROWNUM = 1) IN ('Z05023.1', 'Z05023.2', 'Z05023.3')
           THEN '1'
           ELSE '0'
       END AS DRINK_STATUS, -- 饮酒标志；原 SQL 用了吸烟字段，这里按饮酒频率字段判断

            NVL(
           (SELECT CASE
                       WHEN a.assess_value IN ('从不', '否', '不饮酒') THEN '1'
                       WHEN a.assess_value IN ('偶尔') THEN '2'
                       WHEN a.assess_value IN ('每周不到一次', '每周不到1次') THEN '22'
                       WHEN a.assess_value IN ('1d/月-3d/月', '1天/月-3天/月', '1d/月～3d/月') THEN '21'
                       WHEN a.assess_value IN ('每周1-2次', '每周1－2次', '每周1～2次') THEN '33'
                       WHEN a.assess_value IN ('每周至少3次') THEN '32'
                       WHEN a.assess_value IN ('每周5-6次', '每周5－6次', '每周5～6次') THEN '31'
                       WHEN a.assess_value IN ('每天') THEN '4'
                       WHEN a.assess_value IN ('经常') THEN '3'
                       ELSE '1'
                   END
              FROM mcs_assess_form_record a
             WHERE a.assess_code = 'Z05023'
               AND a.FORM_ID = f.ID
               AND ROWNUM = 1),
           '1'
       ) AS DRINK_FREQUENCY,

       NVL(
           (SELECT CASE
                       WHEN a.assess_value IN ('从不', '否', '不饮酒') THEN '从不'
                       WHEN a.assess_value IN ('偶尔') THEN '偶尔'
                       WHEN a.assess_value IN ('每周不到一次', '每周不到1次') THEN '少于1d/月'
                       WHEN a.assess_value IN ('1d/月-3d/月', '1天/月-3天/月', '1d/月～3d/月') THEN '1d/月-3d/月'
                       WHEN a.assess_value IN ('每周1-2次', '每周1－2次', '每周1～2次') THEN '1d/周-2d/周'
                       WHEN a.assess_value IN ('每周至少3次') THEN '3d/周-4d/周'
                       WHEN a.assess_value IN ('每周5-6次', '每周5－6次', '每周5～6次') THEN '5d/周-6d/周'
                       WHEN a.assess_value IN ('每天') THEN '每天'
                       WHEN a.assess_value IN ('经常') THEN '经常'
                       ELSE '从不'
                   END
              FROM mcs_assess_form_record a
             WHERE a.assess_code = 'Z05023'
               AND a.FORM_ID = f.ID
               AND ROWNUM = 1),
           '从不'
       ) AS DRINK_NAME,

       NVL(
           (SELECT ROUND(TO_NUMBER(REGEXP_SUBSTR(a.assess_value, '[0-9]+(\.[0-9]+)?')))
              FROM mcs_assess_form_record a
             WHERE a.assess_code = 'Z05024'
               AND a.FORM_ID = f.ID
               AND ROWNUM = 1),
           0
       ) AS DRINK_AMOUNT, -- 日饮酒量（mL）

       '1' AS NOTICE_DOC_CODE, -- 通知医师标志，是

       TO_CHAR(YDZD.admission_ward_time, 'yyyy-mm-dd hh24:mi:ss') AS NOTICE_DOC_DATE, -- 通知医师日期时间，是

       TO_CHAR(f.assess_time, 'yyyy-mm-dd hh24:mi:ss') AS ASSESSMENT_DATE, -- 评估日期时间，是

       SUBSTRB(TO_CHAR(f.created_name), 1, 50) AS RES_NURSE_NAME, -- 责任护士签名，是
       SUBSTRB(TO_CHAR(f.created_name), 1, 50) AS ACCEPTS_NURS_NAME, -- 接诊护士签名，是

       TO_CHAR(f.assess_time, 'yyyy-mm-dd hh24:mi:ss') AS SIGNATURE_DATE, -- 签名日期时间，是

       '370104' AS DISTRICT_CODE, -- 行政区划，是
       'ADDHIS' AS EXCHANGE_TYPE, -- 交换类型，是
       TO_CHAR(SYSDATE, 'yyyy-mm-dd hh24:mi:ss') AS SYSTEM_TIME -- 数据上传时间，是

  FROM mcs_assess_form f
       JOIN inpatients YDZD
         ON f.PATIENT_UID = YDZD.pat_index_no
                   LEFT JOIN pat_visit@HIS p
       ON p.PATIENT_ID = SUBSTR(YDZD.PATIENT_ID, 1, INSTR(YDZD.PATIENT_ID, '_') - 1)
      AND p.VISIT_ID = YDZD.SERIES
           LEFT JOIN DIAGNOSIS_BASY dg
       ON dg.PATIENT_ID = SUBSTR(YDZD.PATIENT_ID, 1, INSTR(YDZD.PATIENT_ID, '_') - 1)
      AND dg.VISIT_ID = YDZD.SERIES
        left join (
        select trim(to_char(院标编码)) as local_code,
               max(nullif(trim(to_char(国标编码)), '')) as std_code,
               max(nullif(trim(to_char(国标名称)), '')) as std_name
          from cda_dictionary@sjzx
         where 字典名称 = 'ICD-10诊断编码'
           and 系统标识 = 'HIS'
           and trim(to_char(院标编码)) is not null
         group by trim(to_char(院标编码))
       ) diag_dict
       on diag_dict.local_code = trim(to_char(dg.diagnosis_code))
       left join dept_dict@his dept on dept.dept_code=YDZD.dept_code

 WHERE f.generator_type = 'manul'
   AND f.is_valid = '1'
   AND YDZD.admission_ward_time IS NOT NULL
    and dg.diagnosis_type = '3'
         and dg.diagnosis_no = '1'
  and p.DISCHARGE_DATE_TIME <  to_date('2025-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss')
