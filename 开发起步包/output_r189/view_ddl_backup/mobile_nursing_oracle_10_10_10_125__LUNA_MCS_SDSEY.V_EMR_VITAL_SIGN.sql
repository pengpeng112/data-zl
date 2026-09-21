
  CREATE OR REPLACE FORCE VIEW "LUNA_MCS_SDSEY"."V_EMR_VITAL_SIGN" ("ID", "ORG_CODE", "ORG_NAME", "ADMISSION_ID", "DEPT_CODE", "DEPT_NAME", "WARD_NAME", "EORD_NUM", "SICKBED_NUM", "NAME", "SEX_CODE", "SEX_NAME", "AGE", "AGE_MONTH", "DISEASE_CODE", "DISEASE_NAME", "ADMISSION_DATE", "INPATIENT_DAY", "OPERATION_DAY", "RECORD_DATE", "BREATHING_RATE", "BREATHING_MACHINE_CODE", "PULSE_RATE", "HEART_RATE", "TEMPERATURE", "PRESSURE_H", "PRESSURE_L", "WEIGHT", "ABDOMINAL", "ODSERVE_NAME", "ODSERVE_RESULT", "NURSE_NAME", "RECORD_DATE2", "DISTRICT_CODE", "EXCHANGE_TYPE", "SYSTEM_TIME") AS 
  SELECT
       SUBSTRB(
           '49557032X|' ||
           TO_CHAR(p.mrn) || '|' ||
           TO_CHAR(p.series) || '|' ||
           TO_CHAR(wsfl.plan_time, 'yyyymmddhh24miss') || '|' ||
           NVL(TO_CHAR(wsfl.ward_code), '-'),
           1,
           100
       ) AS ID, -- 内码，是，唯一主键

       '49557032X' AS ORG_CODE, -- 组织机构代码，是

       '山东省第二人民医院' AS ORG_NAME, -- 组织机构名称，是

       SUBSTRB(TO_CHAR(p.mrn || '|' || p.series), 1, 50) AS ADMISSION_ID, -- 住院唯一标示号，是

       SUBSTRB(TO_CHAR(p.dept_code), 1, 20) AS DEPT_CODE, -- 科室代码

       SUBSTRB(TO_CHAR(p.dept_name), 1, 50) AS DEPT_NAME, -- 科室名称，是

       SUBSTRB(TO_CHAR(p.ward_name), 1, 50) AS WARD_NAME, -- 病区名称

       CAST(NULL AS VARCHAR2(10)) AS EORD_NUM, -- 病房号；无可靠来源

       SUBSTRB(TO_CHAR(p.bed_no), 1, 10) AS SICKBED_NUM, -- 病床号

       SUBSTRB(TO_CHAR(p.name), 1, 50) AS NAME, -- 患者姓名，是

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
           THEN SUBSTRB(TO_CHAR(GREATEST(0, TRUNC(MONTHS_BETWEEN(p.admission_time, p.birth_date)))), 1, 8)
           ELSE NULL
       END AS AGE_MONTH, -- 年龄（月）

       SUBSTRB(
           NVL(
               TO_CHAR(diag_dict.std_code),
               REPLACE(
                   CASE
                       WHEN INSTR(TO_CHAR(dg.diagnosis_code), '+') > 0
                       THEN SUBSTR(TO_CHAR(dg.diagnosis_code), 1, INSTR(TO_CHAR(dg.diagnosis_code), '+') - 1)
                       ELSE NVL(TO_CHAR(dg.diagnosis_code), TO_CHAR(p.diagnosis_code))
                   END,
                   '*',
                   ''
               )
           ),
           1,
           12
       ) AS DISEASE_CODE, -- 疾病诊断编码，优先取HIS出院主诊断

       SUBSTRB(
           NVL(
               TO_CHAR(diag_dict.std_name),
               NVL(TO_CHAR(dg.diagnosis_desc), NVL(TO_CHAR(p.diagnosis_name), '-'))
           ),
           1,
           50
       ) AS DISEASE_NAME, -- 疾病诊断，是

       TO_CHAR(p.admission_time, 'yyyy-mm-dd hh24:mi:ss') AS ADMISSION_DATE, -- 入院日期时间，是

       CASE
           WHEN wsfl.plan_time IS NOT NULL AND p.admission_time IS NOT NULL
           THEN GREATEST(0, TRUNC(wsfl.plan_time - p.admission_time) + 1)
           ELSE 0
       END AS INPATIENT_DAY, -- 实际住院天数，是

       CASE
           WHEN op.begin_time IS NOT NULL
                AND wsfl.plan_time IS NOT NULL
                AND wsfl.plan_time >= op.begin_time
           THEN GREATEST(0, TRUNC(wsfl.plan_time - op.begin_time) + 1)
           ELSE 0
       END AS OPERATION_DAY, -- 手术或分娩后天数

       TO_CHAR(wsfl.plan_time, 'yyyy-mm-dd hh24:mi:ss') AS RECORD_DATE, -- 记录日期时间，是

       NVL(ROUND(wsfl.breathing_rate), 0) AS BREATHING_RATE, -- 呼吸频率，是

       CASE
           WHEN NVL(wsfl.breathing_machine_flag, 0) > 0 THEN '1'
           ELSE '0'
       END AS BREATHING_MACHINE_CODE, -- 使用呼吸机标志：1是 0否，是

       NVL(ROUND(wsfl.pulse_rate), 0) AS PULSE_RATE, -- 脉率，是

       NVL(ROUND(wsfl.heart_rate), 0) AS HEART_RATE, -- 心率，来源1003

       NVL(ROUND(wsfl.temperature, 1), 0) AS TEMPERATURE, -- 体温，是

       NVL(ROUND(wsfl.pressure_h), 0) AS PRESSURE_H, -- 收缩压，是

       NVL(ROUND(wsfl.pressure_l), 0) AS PRESSURE_L, -- 舒张压，是

       NVL(ROUND(wsfl.weight, 2), 0) AS WEIGHT, -- 体重，是

       ROUND(wsfl.abdominal, 1) AS ABDOMINAL, -- 腹围

       '生命体征监测' AS ODSERVE_NAME, -- 护理观察项目名称，是

       SUBSTRB(
           NVL(
               NULLIF(
                   LTRIM(
                       CASE
                           WHEN NVL(wsfl.temperature, 0) <> 0
                           THEN '，体温' || TO_CHAR(ROUND(wsfl.temperature, 1)) || '℃'
                           ELSE ''
                       END ||
                       CASE
                           WHEN NVL(wsfl.pulse_rate, 0) <> 0
                           THEN '，脉搏' || TO_CHAR(ROUND(wsfl.pulse_rate)) || '次/分'
                           ELSE ''
                       END ||
                       CASE
                           WHEN NVL(wsfl.heart_rate, 0) <> 0
                           THEN '，心率' || TO_CHAR(ROUND(wsfl.heart_rate)) || '次/分'
                           ELSE ''
                       END ||
                       CASE
                           WHEN NVL(wsfl.breathing_rate, 0) <> 0
                           THEN '，呼吸' || TO_CHAR(ROUND(wsfl.breathing_rate)) || '次/分'
                           ELSE ''
                       END ||
                       CASE
                           WHEN NVL(wsfl.pressure_h, 0) <> 0
                                OR NVL(wsfl.pressure_l, 0) <> 0
                           THEN '，血压' || TO_CHAR(NVL(ROUND(wsfl.pressure_h), 0)) || '/'
                                          || TO_CHAR(NVL(ROUND(wsfl.pressure_l), 0)) || 'mmHg'
                           ELSE ''
                       END ||
                       CASE
                           WHEN NVL(wsfl.oxygen_saturation, 0) <> 0
                           THEN '，血氧饱和度' || TO_CHAR(ROUND(wsfl.oxygen_saturation, 1)) || '%'
                           ELSE ''
                       END ||
                       CASE
                           WHEN NVL(wsfl.weight, 0) <> 0
                           THEN '，体重' || TO_CHAR(ROUND(wsfl.weight, 2)) || 'kg'
                           ELSE ''
                       END ||
                       CASE
                           WHEN NVL(wsfl.abdominal, 0) <> 0
                           THEN '，腹围' || TO_CHAR(ROUND(wsfl.abdominal, 1)) || 'cm'
                           ELSE ''
                       END,
                       '，'
                   ),
                   ''
               ),
               '生命体征已记录'
           ),
           1,
           1000
       ) AS ODSERVE_RESULT, -- 护理观察结果，是

       SUBSTRB(NVL(TO_CHAR(us.user_name), TO_CHAR(wsfl.created_by)), 1, 50) AS NURSE_NAME, -- 护士签名，是

       TO_CHAR(wsfl.record_time, 'yyyy-mm-dd hh24:mi:ss') AS RECORD_DATE2, -- 签名日期时间，是

       '370104' AS DISTRICT_CODE, -- 行政区划，是

       'ADDHIS' AS EXCHANGE_TYPE, -- 交换类型，是

       TO_CHAR(SYSDATE, 'yyyy-mm-dd hh24:mi:ss') AS SYSTEM_TIME -- 数据上传时间，是

  FROM inpatients p

       JOIN (
            SELECT aa.patient_uid,
                   aa.ward_code,
                   aa.plan_time,
                   MIN(aa.record_time) AS record_time,
                   MIN(aa.record_nurse_id) AS created_by,

                   MAX(CASE WHEN aa.vitalsign_type = '1004' THEN aa.vitalsign_nval1 END) AS breathing_rate, -- 呼吸

                   MAX(CASE
                           WHEN aa.vitalsign_type = '1004'
                                AND aa.vitalsign_sval2 IS NOT NULL
                           THEN 1
                           ELSE 0
                       END) AS breathing_machine_flag, -- 呼吸机标志

                   MAX(CASE WHEN aa.vitalsign_type = '1002' THEN aa.vitalsign_nval1 END) AS pulse_rate, -- 脉搏

                   MAX(CASE WHEN aa.vitalsign_type = '1003' THEN aa.vitalsign_nval1 END) AS heart_rate, -- 心率

                   MAX(CASE WHEN aa.vitalsign_type = '1001' THEN aa.vitalsign_nval1 END) AS temperature, -- 体温

                   COALESCE(
                       MAX(CASE WHEN aa.vitalsign_type = '1005' THEN aa.vitalsign_nval1 END),
                       MAX(CASE WHEN aa.vitalsign_type = '3009' THEN aa.vitalsign_nval1 END),
                       MAX(CASE WHEN aa.vitalsign_type = '3010' THEN aa.vitalsign_nval1 END)
                   ) AS pressure_h, -- 收缩压

                   COALESCE(
                       MAX(CASE WHEN aa.vitalsign_type = '1005' THEN aa.vitalsign_nval2 END),
                       MAX(CASE WHEN aa.vitalsign_type = '3009' THEN aa.vitalsign_nval2 END),
                       MAX(CASE WHEN aa.vitalsign_type = '3010' THEN aa.vitalsign_nval2 END)
                   ) AS pressure_l, -- 舒张压

                   MAX(CASE WHEN aa.vitalsign_type = '1006' THEN aa.vitalsign_nval1 END) AS oxygen_saturation, -- 血氧饱和度

                   MAX(CASE WHEN aa.vitalsign_type = '1014' THEN aa.vitalsign_nval1 END) AS weight, -- 体重

                   MAX(CASE WHEN aa.vitalsign_type = '1013' THEN aa.vitalsign_nval1 END) AS height, -- 身高，备用

                   MAX(CASE WHEN aa.vitalsign_type = '3080' THEN aa.vitalsign_nval1 END) AS abdominal, -- 腹围，旧逻辑保留

                   COALESCE(
                       MAX(CASE WHEN aa.vitalsign_type = '1010' THEN aa.vitalsign_nval1 END),
                       MAX(CASE WHEN aa.vitalsign_type IN ('1008', '3007') THEN aa.vitalsign_nval1 END),
                       MAX(CASE WHEN aa.vitalsign_type IN ('3008', '3002', '3003', '3004', '3005', '3006', '3011', '3012', '3013') THEN aa.vitalsign_nval1 END)
                   ) AS output_amount, -- 出量相关，备用

                   COALESCE(
                       MAX(CASE WHEN aa.vitalsign_type = '1009' THEN aa.vitalsign_nval1 END),
                       MAX(CASE WHEN aa.vitalsign_type IN ('1032', '1033') THEN aa.vitalsign_nval1 END)
                   ) AS input_amount -- 入量相关，备用

              FROM mcs_vital_info aa
             WHERE aa.is_valid = '1'
               AND aa.plan_time IS NOT NULL
               AND aa.vitalsign_type IN (
                   '1001', -- 体温
                   '1002', -- 脉搏
                   '1003', -- 心率
                   '1004', -- 呼吸
                   '1005', -- 血压
                   '3009', -- 血压
                   '3010', -- 血压
                   '1006', -- 血氧饱和度
                   '1014', -- 体重
                   '1013', -- 身高
                   '3080', -- 腹围，旧逻辑保留
                   '1010', -- 出量
                   '1009', -- 入量
                   '1008', -- 尿量
                   '3007', -- 尿量
                   '3008', -- 引流量
                   '3002', -- 胃管引流
                   '3003', -- 胸腔引流
                   '3004', -- 腹腔引流
                   '3005', -- 导管
                   '3006', -- T管
                   '3011', -- 皮下引流
                   '3012', -- 腹壁引流
                   '3013', -- 宫腔引流
                   '1032', -- 母乳
                   '1033'  -- 牛乳
               )
             GROUP BY aa.patient_uid,
                      aa.ward_code,
                      aa.plan_time
            HAVING MAX(
                       CASE
                           WHEN aa.vitalsign_type IN ('1001', '1002', '1003', '1004', '1005', '3009', '3010', '1014', '3080')
                                AND (
                                      NVL(aa.vitalsign_nval1, 0) <> 0
                                   OR NVL(aa.vitalsign_nval2, 0) <> 0
                                   OR aa.vitalsign_sval2 IS NOT NULL
                                )
                           THEN 1
                           ELSE 0
                       END
                   ) = 1
       ) wsfl
         ON wsfl.patient_uid = p.pat_index_no

       LEFT JOIN mcs_sys_users us
         ON wsfl.created_by = us.user_code

       LEFT JOIN (
            SELECT e.patient_uid,
                   MIN(e.begin_time) AS begin_time
              FROM mcs_event_info e
             WHERE e.event_type IN ('2003', '2004')
             GROUP BY e.patient_uid
       ) op
         ON op.patient_uid = wsfl.patient_uid

       JOIN pat_visit@HIS pv
         ON pv.PATIENT_ID = SUBSTR(p.PATIENT_ID, 1, INSTR(p.PATIENT_ID || '_', '_') - 1)
        AND pv.VISIT_ID = p.SERIES

       LEFT JOIN (
            SELECT d.PATIENT_ID,
                   d.VISIT_ID,
                   MAX(
                       REPLACE(
                           CASE
                               WHEN INSTR(TO_CHAR(d.diagnosis_code), '+') > 0
                               THEN SUBSTR(TO_CHAR(d.diagnosis_code), 1, INSTR(TO_CHAR(d.diagnosis_code), '+') - 1)
                               ELSE TO_CHAR(d.diagnosis_code)
                           END,
                           '*',
                           ''
                       )
                   ) AS diagnosis_code,
                   MAX(TO_CHAR(d.diagnosis_desc)) AS diagnosis_desc
              FROM DIAGNOSIS@HIS d
             WHERE d.diagnosis_type = '3'
               AND d.diagnosis_no = '1'
             GROUP BY d.PATIENT_ID,
                      d.VISIT_ID
       ) dg
         ON dg.PATIENT_ID = pv.PATIENT_ID
        AND dg.VISIT_ID = pv.VISIT_ID

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
         ON diag_dict.local_code = TRIM(TO_CHAR(dg.diagnosis_code))

 WHERE p.status = 'out'
   AND pv.DISCHARGE_DATE_TIME < TO_DATE('2025-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss')
