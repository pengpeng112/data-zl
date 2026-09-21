
  CREATE OR REPLACE FORCE VIEW "LUNA_MCS_SDSEY"."V_EMR_CHILDBIRTH" ("ID", "ORG_CODE", "ORG_NAME", "ADMISSION_ID", "NAME", "AGE", "DEPT_CODE", "DEPT_NAME", "WARD_NAME", "EORD_NUM", "SICKBED_NUM", "BIRTH_TIMES", "PREGNANT_TIMES", "LAST_MENSTRUATION_DATE", "EXPECTED_DATE", "LABOR_DATE", "UTCON_DATE", "FULL_DATE", "DIAGNOSIS_TYPE", "IN_DIAGNOSIS_CODE", "IN_DIAGNOSIS", "MEMBRANE_RUPTRRE_DATE", "MEMBRANE_RUPTRRE_TYPE", "PRE_CHARACTER", "BEFORE_AMOUNT", "CHILD_BIRTH_DATE", "FRIST_DELIVERY_TIME", "SECOND_DELIVERY_TIME", "THIRD_DELIVERY_TIME", "DELIVERY_TOTAL_TIME", "FETUS_POSITION_CODE", "FETUS_POSITION", "MINDWIFEY_CODE", "MINDWIFEY_NOTE", "AMNIOTIC_FUILD_NOTE", "AMNIOTIC_FUILD_ML", "PLACENTE_DATE", "PLACENTE_STATE", "MEMBRANES_CODE", "UM_CORD_LONG", "RG_BODY", "AU_CODE_NOTE", "OPERA_DRUG", "PERVE_MEASURES", "CUT_MASK", "CUT_PLACE", "SUTURE_NUM", "LACERATE_DEGREE_CODE", "LACERATE_DEGREE", "HEMATOMA_CODE", "ANES_METHOD_CODE", "ANAESTHESIA_NAME", "ANES_DRUG_NAME", "VAGNIAL_CODE", "HEAMATORA_CODE", "HEAMATORA_SIZE", "HEAMATORA_HANDLE", "LACERATION_CODE", "SUTURE_NOTE", "ANUS_CHECK", "AFTER_DRUG", "SPECIAL_RECORD", "CONTRACTION_NOTE", "UTERUS_RESULT", "LOCHIA_REMARKS", "REPAIR_OPERA", "SAVE_BLOOD_CODE", "AFTER_OPER_DIAGNOSIS", "ALTER_OBS_DATE", "CHECK_TIME", "SYSTOLIC_PRESSURE", "DIASTOLIC_PRESSURE", "PULSE_RATE", "HEART_RATE", "OUT_BLOOD_ML", "AFTER_CONTRACTION", "HAREM_HEIGHT", "BLADDER_CODE", "CHILD_SEX_CODE", "SEX_NAME", "NEWBORN_HEAVY", "NEWBORN_LONG", "TUMOR_SIZE", "TUMOR_PART", "APGAR", "APGAR_TIME", "APGAR_SCORE", "DELIVERY_OUTCOME_CODE", "DELIVERY_OUTCOME", "CHILD_ADNORMAL_CODE", "ACCOUCHE_PERSON_NAME", "OPERA_DOC_NAME", "PEDIATRICIAN_NAME", "RECORD_PERSON_NAME", "DISTRICT_CODE", "EXCHANGE_TYPE", "SYSTEM_TIME") AS 
  SELECT
       SUBSTRB(TO_CHAR(WSFL.ID), 1, 100) AS ID, -- 内码，是，唯一主键

       '49557032X' AS ORG_CODE, -- 组织机构代码，是
       '山东省第二人民医院' AS ORG_NAME, -- 组织机构名称，是

       SUBSTRB(TO_CHAR(YDZD.mrn || '|' || YDZD.series), 1, 50) AS ADMISSION_ID, -- 住院唯一标示号，是

       SUBSTRB(TO_CHAR(YDZD.NAME), 1, 50) AS NAME, -- 产妇姓名，是

       CASE
           WHEN YDZD.admission_time IS NOT NULL AND YDZD.birth_date IS NOT NULL
           THEN LEAST(200, GREATEST(0, TRUNC(MONTHS_BETWEEN(YDZD.admission_time, YDZD.birth_date) / 12)))
           ELSE 0
       END AS AGE, -- 年龄（岁），是

       SUBSTRB(NVL(TO_CHAR(dept.qmpt_code), TO_CHAR(YDZD.dept_code)), 1, 20) AS DEPT_CODE, -- 科室代码

       SUBSTRB(NVL(TO_CHAR(dept.qmpt_name), TO_CHAR(YDZD.dept_name)), 1, 50) AS DEPT_NAME, -- 科室名称，是

       SUBSTRB(TO_CHAR(YDZD.WARD_NAME), 1, 50) AS WARD_NAME, -- 病区名称

       CAST(NULL AS VARCHAR2(10)) AS EORD_NUM, -- 病房号；无可靠来源，不硬填

       SUBSTRB(TO_CHAR(YDZD.Bed_No), 1, 10) AS SICKBED_NUM, -- 病床号

       NVL(
           (SELECT TO_NUMBER(REGEXP_SUBSTR(a.STRING_VALUE, '[0-9]+'))
              FROM mcs_doc_form_records a
             WHERE a.template_code = '742'
               AND a.node_code = '00005'
               AND a.patient_uid = WSFL.Patient_Uid
               AND REGEXP_LIKE(a.STRING_VALUE, '[0-9]')
               AND ROWNUM = 1),
           0
       ) AS BIRTH_TIMES, -- 产次，是

       NVL(
           (SELECT TO_NUMBER(REGEXP_SUBSTR(a.STRING_VALUE, '[0-9]+'))
              FROM mcs_doc_form_records a
             WHERE a.template_code = '742'
               AND a.node_code = '00004'
               AND a.patient_uid = WSFL.Patient_Uid
               AND REGEXP_LIKE(a.STRING_VALUE, '[0-9]')
               AND ROWNUM = 1),
           0
       ) AS PREGNANT_TIMES, -- 孕次，是

        to_date('1900-01-01','yyyy-mm-dd') AS LAST_MENSTRUATION_DATE, -- 末次月经日期；旧 SQL 未见可靠来源，需要确认

       to_date('1900-01-01','yyyy-mm-dd')   AS EXPECTED_DATE, -- 预产期；旧 SQL 固定1900，先不硬填，需要确认

       TO_CHAR(
           NVL(
               (SELECT TO_DATE(a.STRING_VALUE, 'yyyy-mm-dd hh24:mi:ss')
                  FROM mcs_doc_form_records a
                 WHERE a.template_code = '743'
                   AND a.node_code = '00007'
                   AND a.patient_uid = WSFL.Patient_Uid
                   AND REGEXP_LIKE(a.STRING_VALUE, '^[0-9]{4}-[0-9]{2}-[0-9]{2}')
                   AND ROWNUM = 1),
               WSFL.FORM_TIME
           ),
           'yyyy-mm-dd hh24:mi:ss'
       ) AS LABOR_DATE, -- 临产日期时间，是

       TO_CHAR(
           NVL(
               (SELECT TO_DATE(a.STRING_VALUE, 'yyyy-mm-dd hh24:mi:ss')
                  FROM mcs_doc_form_records a
                 WHERE a.template_code = WSFL.TEMPLATE_CODE
                   AND a.node_code = '00009'
                   AND a.FORM_ID = WSFL.ID
                   AND REGEXP_LIKE(a.STRING_VALUE, '^[0-9]{4}-[0-9]{2}-[0-9]{2}')
                   AND ROWNUM = 1),
               WSFL.FORM_TIME
           ),
           'yyyy-mm-dd hh24:mi:ss'
       ) AS UTCON_DATE, -- 宫缩起始时间，是

       TO_CHAR(
           NVL(
               (SELECT TO_DATE(a.STRING_VALUE, 'yyyy-mm-dd hh24:mi:ss')
                  FROM mcs_doc_form_records a
                 WHERE a.template_code = WSFL.TEMPLATE_CODE
                   AND a.node_code = '00010'
                   AND a.FORM_ID = WSFL.ID
                   AND REGEXP_LIKE(a.STRING_VALUE, '^[0-9]{4}-[0-9]{2}-[0-9]{2}')
                   AND ROWNUM = 1),
               WSFL.FORM_TIME
           ),
           'yyyy-mm-dd hh24:mi:ss'
       ) AS FULL_DATE, -- 宫口开全日期时间，是

       '2' AS DIAGNOSIS_TYPE, -- 诊断类别；暂按西医诊断

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
       ) AS IN_DIAGNOSIS_CODE, -- 诊断编码，是

       SUBSTRB(
           NVL(
               TO_CHAR(diag_dict.std_name),
               NVL(TO_CHAR(dg.diagnosis_desc), NVL(TO_CHAR(YDZD.diagnosis_name), '-'))
           ),
           1,
           200
       ) AS IN_DIAGNOSIS, -- 诊断名称，是

       TO_CHAR(
           NVL(
               (SELECT TO_DATE(a.STRING_VALUE, 'yyyy-mm-dd hh24:mi:ss')
                  FROM mcs_doc_form_records a
                 WHERE a.template_code = WSFL.TEMPLATE_CODE
                   AND a.node_code = '00011'
                   AND a.FORM_ID = WSFL.ID
                   AND REGEXP_LIKE(a.STRING_VALUE, '^[0-9]{4}-[0-9]{2}-[0-9]{2}')
                   AND ROWNUM = 1),
               WSFL.FORM_TIME
           ),
           'yyyy-mm-dd hh24:mi:ss'
       ) AS MEMBRANE_RUPTRRE_DATE, -- 胎膜破裂日期时间，是

       '自然' AS MEMBRANE_RUPTRRE_TYPE, -- 胎膜破裂方式；旧 SQL 未见明确字段，暂按自然

       SUBSTRB(
           NVL(
               (SELECT a.STRING_VALUE
                  FROM mcs_doc_form_records a
                 WHERE a.template_code = WSFL.TEMPLATE_CODE
                   AND a.node_code = '00013'
                   AND a.FORM_ID = WSFL.ID
                   AND ROWNUM = 1),
               '清'
           ),
           1,
           100
       ) AS PRE_CHARACTER, -- 前羊水性状，是

       NVL(
           (SELECT TO_NUMBER(REGEXP_SUBSTR(a.STRING_VALUE, '[0-9]+'))
              FROM mcs_doc_form_records a
             WHERE a.template_code = WSFL.TEMPLATE_CODE
               AND a.node_code = '00098'
               AND a.FORM_ID = WSFL.ID
               AND REGEXP_LIKE(a.STRING_VALUE, '[0-9]')
               AND ROWNUM = 1),
           0
       ) AS BEFORE_AMOUNT, -- 前羊水量（mL），是

       TO_CHAR(
           NVL(
               (SELECT TO_DATE(a.STRING_VALUE, 'yyyy-mm-dd hh24:mi:ss')
                  FROM mcs_doc_form_records a
                 WHERE a.template_code = WSFL.TEMPLATE_CODE
                   AND a.node_code = '00014'
                   AND a.FORM_ID = WSFL.ID
                   AND REGEXP_LIKE(a.STRING_VALUE, '^[0-9]{4}-[0-9]{2}-[0-9]{2}')
                   AND ROWNUM = 1),
               WSFL.FORM_TIME
           ),
           'yyyy-mm-dd hh24:mi:ss'
       ) AS CHILD_BIRTH_DATE, -- 胎儿娩出日期时间，是

       NVL(
           (SELECT NVL(h.NUMBER_VALUE, 0) * 60
              FROM mcs_doc_form_records h
             WHERE h.template_code = WSFL.TEMPLATE_CODE
               AND h.node_code = '00099'
               AND h.FORM_ID = WSFL.ID
               AND ROWNUM = 1),
           0
       )
       +
       NVL(
           (SELECT NVL(m.NUMBER_VALUE, 0)
              FROM mcs_doc_form_records m
             WHERE m.template_code = WSFL.TEMPLATE_CODE
               AND m.node_code = '00100'
               AND m.FORM_ID = WSFL.ID
               AND ROWNUM = 1),
           0
       ) AS FRIST_DELIVERY_TIME, -- 第1产程时长（min）

       NVL(
           (SELECT NVL(h.NUMBER_VALUE, 0) * 60
              FROM mcs_doc_form_records h
             WHERE h.template_code = WSFL.TEMPLATE_CODE
               AND h.node_code = '00101'
               AND h.FORM_ID = WSFL.ID
               AND ROWNUM = 1),
           0
       )
       +
       NVL(
           (SELECT NVL(m.NUMBER_VALUE, 0)
              FROM mcs_doc_form_records m
             WHERE m.template_code = WSFL.TEMPLATE_CODE
               AND m.node_code = '00102'
               AND m.FORM_ID = WSFL.ID
               AND ROWNUM = 1),
           0
       ) AS SECOND_DELIVERY_TIME, -- 第2产程时长（min）

       NVL(
           (SELECT NVL(h.NUMBER_VALUE, 0) * 60
              FROM mcs_doc_form_records h
             WHERE h.template_code = WSFL.TEMPLATE_CODE
               AND h.node_code = '00103'
               AND h.FORM_ID = WSFL.ID
               AND ROWNUM = 1),
           0
       )
       +
       NVL(
           (SELECT NVL(m.NUMBER_VALUE, 0)
              FROM mcs_doc_form_records m
             WHERE m.template_code = WSFL.TEMPLATE_CODE
               AND m.node_code = '00104'
               AND m.FORM_ID = WSFL.ID
               AND ROWNUM = 1),
           0
       ) AS THIRD_DELIVERY_TIME, -- 第3产程时长（min）

       NVL(
           (SELECT NVL(h.NUMBER_VALUE, 0) * 60
              FROM mcs_doc_form_records h
             WHERE h.template_code = WSFL.TEMPLATE_CODE
               AND h.node_code = '00105'
               AND h.FORM_ID = WSFL.ID
               AND ROWNUM = 1),
           0
       )
       +
       NVL(
           (SELECT TO_NUMBER(REGEXP_SUBSTR(m.STRING_VALUE, '[0-9]+'))
              FROM mcs_doc_form_records m
             WHERE m.template_code = WSFL.TEMPLATE_CODE
               AND m.node_code = '00106'
               AND m.FORM_ID = WSFL.ID
               AND REGEXP_LIKE(m.STRING_VALUE, '[0-9]')
               AND ROWNUM = 1),
           0
       ) AS DELIVERY_TOTAL_TIME, -- 总产程时长（min），是
       NVL(
           (SELECT CASE
                       WHEN UPPER(TRIM(a.STRING_VALUE)) IN ('LOA', '左枕前', '左枕前(LOA)', '01') THEN '01'
                       WHEN UPPER(TRIM(a.STRING_VALUE)) IN ('ROA', '右枕前', '右枕前(ROA)', '02') THEN '02'
                       WHEN UPPER(TRIM(a.STRING_VALUE)) IN ('LOP', '左枕后', '左枕后(LOP)', '03') THEN '03'
                       WHEN UPPER(TRIM(a.STRING_VALUE)) IN ('ROP', '右枕后', '右枕后(ROP)', '04') THEN '04'
                       WHEN UPPER(TRIM(a.STRING_VALUE)) IN ('LOT', '左枕横', '左枕横(LOT)', '05') THEN '05'
                       WHEN UPPER(TRIM(a.STRING_VALUE)) IN ('ROT', '右枕横', '右枕横(ROT)', '06') THEN '06'
                       WHEN UPPER(TRIM(a.STRING_VALUE)) IN ('LMA', '左颏前', '左颏前(LMA)', '07') THEN '07'
                       WHEN UPPER(TRIM(a.STRING_VALUE)) IN ('RMA', '右颏前', '右颏前(RMA)', '08') THEN '08'
                       WHEN UPPER(TRIM(a.STRING_VALUE)) IN ('LMP', '左颏后', '左颏后(LMP)', '09') THEN '09'
                       WHEN UPPER(TRIM(a.STRING_VALUE)) IN ('RMP', '右颏后', '右颏后(RMP)', '10') THEN '10'
                       WHEN UPPER(TRIM(a.STRING_VALUE)) IN ('LMT', '左颏横', '左颏横(LMT)', '11') THEN '11'
                       WHEN UPPER(TRIM(a.STRING_VALUE)) IN ('RMT', '右颏横', '右颏横(RMT)', '12') THEN '12'
                       WHEN UPPER(TRIM(a.STRING_VALUE)) IN ('LSA', '左骶前', '左骶前(LSA)', '13') THEN '13'
                       WHEN UPPER(TRIM(a.STRING_VALUE)) IN ('RSA', '右骶前', '右骶前(RSA)', '14') THEN '14'
                       WHEN UPPER(TRIM(a.STRING_VALUE)) IN ('LSP', '左骶后', '左骶后(LSP)', '15') THEN '15'
                       WHEN UPPER(TRIM(a.STRING_VALUE)) IN ('RSP', '右骶后', '右骶后(RSP)', '16') THEN '16'
                       WHEN UPPER(TRIM(a.STRING_VALUE)) IN ('LST', '左骶横', '左骶横(LST)', '17') THEN '17'
                       WHEN UPPER(TRIM(a.STRING_VALUE)) IN ('RST', '右骶横', '右骶横(RST)', '18') THEN '18'
                       WHEN UPPER(TRIM(a.STRING_VALUE)) IN ('LSCA', '左肩前', '左肩前(LSCA)', '19') THEN '19'
                       WHEN UPPER(TRIM(a.STRING_VALUE)) IN ('RSCA', '右肩前', '右肩前(RSCA)', '20') THEN '20'
                       WHEN UPPER(TRIM(a.STRING_VALUE)) IN ('LSCP', '左肩后', '左肩后(LSCP)', '21') THEN '21'
                       WHEN UPPER(TRIM(a.STRING_VALUE)) IN ('RSCP', '右肩后', '右肩后(RSCP)', '22') THEN '22'
                       ELSE '99'
                   END
              FROM mcs_doc_form_records a
             WHERE a.template_code = WSFL.TEMPLATE_CODE
               AND a.node_code = '00018'
               AND a.FORM_ID = WSFL.ID
               AND ROWNUM = 1),
           '99'
       ) AS FETUS_POSITION_CODE, -- 胎方位代码：CV05.01.007

       NVL(
           (SELECT CASE
                       WHEN UPPER(TRIM(a.STRING_VALUE)) IN ('LOA', '左枕前', '左枕前(LOA)', '01') THEN '左枕前(LOA)'
                       WHEN UPPER(TRIM(a.STRING_VALUE)) IN ('ROA', '右枕前', '右枕前(ROA)', '02') THEN '右枕前(ROA)'
                       WHEN UPPER(TRIM(a.STRING_VALUE)) IN ('LOP', '左枕后', '左枕后(LOP)', '03') THEN '左枕后(LOP)'
                       WHEN UPPER(TRIM(a.STRING_VALUE)) IN ('ROP', '右枕后', '右枕后(ROP)', '04') THEN '右枕后(ROP)'
                       WHEN UPPER(TRIM(a.STRING_VALUE)) IN ('LOT', '左枕横', '左枕横(LOT)', '05') THEN '左枕横(LOT)'
                       WHEN UPPER(TRIM(a.STRING_VALUE)) IN ('ROT', '右枕横', '右枕横(ROT)', '06') THEN '右枕横(ROT)'
                       WHEN UPPER(TRIM(a.STRING_VALUE)) IN ('LMA', '左颏前', '左颏前(LMA)', '07') THEN '左颏前(LMA)'
                       WHEN UPPER(TRIM(a.STRING_VALUE)) IN ('RMA', '右颏前', '右颏前(RMA)', '08') THEN '右颏前(RMA)'
                       WHEN UPPER(TRIM(a.STRING_VALUE)) IN ('LMP', '左颏后', '左颏后(LMP)', '09') THEN '左颏后(LMP)'
                       WHEN UPPER(TRIM(a.STRING_VALUE)) IN ('RMP', '右颏后', '右颏后(RMP)', '10') THEN '右颏后(RMP)'
                       WHEN UPPER(TRIM(a.STRING_VALUE)) IN ('LMT', '左颏横', '左颏横(LMT)', '11') THEN '左颏横(LMT)'
                       WHEN UPPER(TRIM(a.STRING_VALUE)) IN ('RMT', '右颏横', '右颏横(RMT)', '12') THEN '右颏横(RMT)'
                       WHEN UPPER(TRIM(a.STRING_VALUE)) IN ('LSA', '左骶前', '左骶前(LSA)', '13') THEN '左骶前(LSA)'
                       WHEN UPPER(TRIM(a.STRING_VALUE)) IN ('RSA', '右骶前', '右骶前(RSA)', '14') THEN '右骶前(RSA)'
                       WHEN UPPER(TRIM(a.STRING_VALUE)) IN ('LSP', '左骶后', '左骶后(LSP)', '15') THEN '左骶后(LSP)'
                       WHEN UPPER(TRIM(a.STRING_VALUE)) IN ('RSP', '右骶后', '右骶后(RSP)', '16') THEN '右骶后(RSP)'
                       WHEN UPPER(TRIM(a.STRING_VALUE)) IN ('LST', '左骶横', '左骶横(LST)', '17') THEN '左骶横(LST)'
                       WHEN UPPER(TRIM(a.STRING_VALUE)) IN ('RST', '右骶横', '右骶横(RST)', '18') THEN '右骶横(RST)'
                       WHEN UPPER(TRIM(a.STRING_VALUE)) IN ('LSCA', '左肩前', '左肩前(LSCA)', '19') THEN '左肩前(LScA)'
                       WHEN UPPER(TRIM(a.STRING_VALUE)) IN ('RSCA', '右肩前', '右肩前(RSCA)', '20') THEN '右肩前(RScA)'
                       WHEN UPPER(TRIM(a.STRING_VALUE)) IN ('LSCP', '左肩后', '左肩后(LSCP)', '21') THEN '左肩后(LScP)'
                       WHEN UPPER(TRIM(a.STRING_VALUE)) IN ('RSCP', '右肩后', '右肩后(RSCP)', '22') THEN '右肩后(RScP)'
                       ELSE '不详'
                   END
              FROM mcs_doc_form_records a
             WHERE a.template_code = WSFL.TEMPLATE_CODE
               AND a.node_code = '00018'
               AND a.FORM_ID = WSFL.ID
               AND ROWNUM = 1),
           '不详'
       ) AS FETUS_POSITION, -- 胎方位

       CASE
           WHEN (SELECT COUNT(*)
                   FROM mcs_doc_form_records a
                  WHERE a.template_code = '743'
                    AND a.patient_uid = WSFL.Patient_Uid
                    AND a.node_code IN ('00032', '00033', '00034')
                    AND a.NUMBER_VALUE IS NOT NULL) > 0
           THEN '1'
           ELSE '0'
       END AS MINDWIFEY_CODE, -- 阴道助产标志，是；1是0否

       SUBSTRB(
           NVL(
               CASE
                   WHEN (SELECT COUNT(*) FROM mcs_doc_form_records a WHERE a.template_code = '743' AND a.node_code = '00032' AND a.patient_uid = WSFL.Patient_Uid AND a.NUMBER_VALUE IS NOT NULL) > 0 THEN '胎头吸引术'
                   WHEN (SELECT COUNT(*) FROM mcs_doc_form_records a WHERE a.template_code = '743' AND a.node_code = '00033' AND a.patient_uid = WSFL.Patient_Uid AND a.NUMBER_VALUE IS NOT NULL) > 0 THEN '产钳术'
                   WHEN (SELECT COUNT(*) FROM mcs_doc_form_records a WHERE a.template_code = '743' AND a.node_code = '00034' AND a.patient_uid = WSFL.Patient_Uid AND a.NUMBER_VALUE IS NOT NULL) > 0 THEN '臀位助产术'
                   ELSE '无'
               END,
               '无'
           ),
           1,
           100
       ) AS MINDWIFEY_NOTE, -- 阴道助产方式，是

       SUBSTRB(
           NVL(
               (SELECT a.STRING_VALUE
                  FROM mcs_doc_form_records a
                 WHERE a.template_code = WSFL.TEMPLATE_CODE
                   AND a.node_code = '00013'
                   AND a.FORM_ID = WSFL.ID
                   AND ROWNUM = 1),
               NULL
           ),
           1,
           100
       ) AS AMNIOTIC_FUILD_NOTE, -- 羊水性状

       CAST(NULL AS NUMBER(5)) AS AMNIOTIC_FUILD_ML, -- 羊水量（mL）；旧 SQL 固定0，先不硬填

       TO_CHAR(
           NVL(
               (SELECT TO_DATE(a.STRING_VALUE, 'yyyy-mm-dd hh24:mi:ss')
                  FROM mcs_doc_form_records a
                 WHERE a.template_code = WSFL.TEMPLATE_CODE
                   AND a.node_code = '00019'
                   AND a.FORM_ID = WSFL.ID
                   AND REGEXP_LIKE(a.STRING_VALUE, '^[0-9]{4}-[0-9]{2}-[0-9]{2}')
                   AND ROWNUM = 1),
               WSFL.FORM_TIME
           ),
           'yyyy-mm-dd hh24:mi:ss'
       ) AS PLACENTE_DATE, -- 胎盘娩出日期时间，是

       SUBSTRB(
           CASE
               WHEN (SELECT COUNT(*)
                       FROM mcs_doc_form_records a
                      WHERE a.FORM_ID = WSFL.ID
                        AND a.node_code = '00047'
                        AND a.NUMBER_VALUE IS NOT NULL) > 0
               THEN '完整'
               ELSE NVL(
                       '不完整' ||
                       (SELECT a.STRING_VALUE
                          FROM mcs_doc_form_records a
                         WHERE a.template_code = '743'
                           AND a.node_code = '00049'
                           AND a.patient_uid = WSFL.Patient_Uid
                           AND ROWNUM = 1),
                       '不完整'
                    )
           END,
           1,
           100
       ) AS PLACENTE_STATE, -- 胎盘娩出情况，是

       CASE
           WHEN (SELECT COUNT(*)
                   FROM mcs_doc_form_records a
                  WHERE a.FORM_ID = WSFL.ID
                    AND a.node_code = '00047'
                    AND a.NUMBER_VALUE IS NOT NULL) > 0
           THEN '1'
           ELSE '0'
       END AS MEMBRANES_CODE, -- 胎膜完整情况标志，是；1是0否

       NVL(
           (SELECT TO_NUMBER(REGEXP_SUBSTR(a.STRING_VALUE, '[0-9]+'))
              FROM mcs_doc_form_records a
             WHERE a.template_code = WSFL.TEMPLATE_CODE
               AND a.node_code = '00055'
               AND a.FORM_ID = WSFL.ID
               AND REGEXP_LIKE(a.STRING_VALUE, '[0-9]')
               AND ROWNUM = 1),
           0
       ) AS UM_CORD_LONG, -- 绕颈身（周）

       NVL(
           (SELECT TO_NUMBER(REGEXP_SUBSTR(a.STRING_VALUE, '[0-9]+'))
              FROM mcs_doc_form_records a
             WHERE a.template_code = WSFL.TEMPLATE_CODE
               AND a.node_code = '00059'
               AND a.FORM_ID = WSFL.ID
               AND REGEXP_LIKE(a.STRING_VALUE, '[0-9]')
               AND ROWNUM = 1),
           0
       ) AS RG_BODY, -- 脐带长度（cm）

       SUBSTRB(
           (SELECT a.STRING_VALUE
              FROM mcs_doc_form_records a
             WHERE a.template_code = WSFL.TEMPLATE_CODE
               AND a.node_code = '00053'
               AND a.FORM_ID = WSFL.ID
               AND ROWNUM = 1),
           1,
           200
       ) AS AU_CODE_NOTE, -- 脐带异常情况描述

       SUBSTRB(
           (SELECT a.STRING_VALUE
              FROM mcs_doc_form_records a
             WHERE a.template_code = WSFL.TEMPLATE_CODE
               AND a.node_code = '00042'
               AND a.FORM_ID = WSFL.ID
               AND ROWNUM = 1),
           1,
           50
       ) AS OPERA_DRUG, -- 产时用药

       SUBSTRB('防跌倒', 1, 200) AS PERVE_MEASURES, -- 预防措施

       CASE
           WHEN (SELECT COUNT(*)
                   FROM mcs_doc_form_records a
                  WHERE a.FORM_ID = WSFL.ID
                    AND a.node_code IN ('00033', '00034')
                    AND a.NUMBER_VALUE IS NOT NULL) > 0
           THEN '1'
           ELSE '0'
       END AS CUT_MASK, -- 产妇会阴切开标志；1是0否

       SUBSTRB(
           CASE
               WHEN (SELECT COUNT(*) FROM mcs_doc_form_records a WHERE a.FORM_ID = WSFL.ID AND a.node_code = '00033' AND a.NUMBER_VALUE IS NOT NULL) > 0 THEN '侧切'
               WHEN (SELECT COUNT(*) FROM mcs_doc_form_records a WHERE a.FORM_ID = WSFL.ID AND a.node_code = '00034' AND a.NUMBER_VALUE IS NOT NULL) > 0 THEN '正中切'
               ELSE '无'
           END,
           1,
           100
       ) AS CUT_PLACE, -- 会阴切开位置

       NVL(
           (SELECT TO_NUMBER(REGEXP_SUBSTR(a.STRING_VALUE, '[0-9]+'))
              FROM mcs_doc_form_records a
             WHERE a.template_code = WSFL.TEMPLATE_CODE
               AND a.node_code = '00036'
               AND a.FORM_ID = WSFL.ID
               AND REGEXP_LIKE(a.STRING_VALUE, '[0-9]')
               AND ROWNUM = 1),
           0
       ) AS SUTURE_NUM, -- 产妇会阴缝合针数

       CASE
           WHEN (SELECT COUNT(*) FROM mcs_doc_form_records a WHERE a.FORM_ID = WSFL.ID AND a.node_code = '00028' AND a.NUMBER_VALUE IS NOT NULL) > 0 THEN '2'
           WHEN (SELECT COUNT(*) FROM mcs_doc_form_records a WHERE a.FORM_ID = WSFL.ID AND a.node_code = '00029' AND a.NUMBER_VALUE IS NOT NULL) > 0 THEN '3'
           WHEN (SELECT COUNT(*) FROM mcs_doc_form_records a WHERE a.FORM_ID = WSFL.ID AND a.node_code = '00030' AND a.NUMBER_VALUE IS NOT NULL) > 0 THEN '4'
           WHEN (SELECT COUNT(*) FROM mcs_doc_form_records a WHERE a.FORM_ID = WSFL.ID AND a.node_code = '00031' AND a.NUMBER_VALUE IS NOT NULL) > 0 THEN '5'
           ELSE '1'
       END AS LACERATE_DEGREE_CODE, -- 会阴裂伤情况代码，是；需确认平台是否接受0无裂伤

       SUBSTRB(
           CASE
               WHEN (SELECT COUNT(*) FROM mcs_doc_form_records a WHERE a.FORM_ID = WSFL.ID AND a.node_code = '00028' AND a.NUMBER_VALUE IS NOT NULL) > 0 THEN 'I°裂伤'
               WHEN (SELECT COUNT(*) FROM mcs_doc_form_records a WHERE a.FORM_ID = WSFL.ID AND a.node_code = '00029' AND a.NUMBER_VALUE IS NOT NULL) > 0 THEN 'Ⅱ°裂伤'
               WHEN (SELECT COUNT(*) FROM mcs_doc_form_records a WHERE a.FORM_ID = WSFL.ID AND a.node_code = '00030' AND a.NUMBER_VALUE IS NOT NULL) > 0 THEN 'Ⅲ°裂伤'
               WHEN (SELECT COUNT(*) FROM mcs_doc_form_records a WHERE a.FORM_ID = WSFL.ID AND a.node_code = '00031' AND a.NUMBER_VALUE IS NOT NULL) > 0 THEN '会阴切开'
               ELSE '无裂伤'
           END,
           1,
           50
       ) AS LACERATE_DEGREE, -- 会阴裂伤情况，是

       '0' AS HEMATOMA_CODE, -- 会阴血肿标志，是；旧 SQL 固定无，按标准改为0

             NVL(
           (SELECT CASE
                       /* 复合麻醉：神经阻滞 + 局部浸润/局部麻醉 */
                       WHEN (
                                TRIM(a.STRING_VALUE) LIKE '%神经阻滞%'
                             OR TRIM(a.STRING_VALUE) LIKE '%阴部神经%'
                             OR TRIM(a.STRING_VALUE) LIKE '%神经组织%'
                            )
                            AND (
                                TRIM(a.STRING_VALUE) LIKE '%局部%'
                             OR TRIM(a.STRING_VALUE) LIKE '%浸润%'
                             OR TRIM(a.STRING_VALUE) LIKE '%经润%'
                             OR TRIM(a.STRING_VALUE) LIKE '%侵润%'
                             OR TRIM(a.STRING_VALUE) LIKE '%浸入%'
                            )
                       THEN '4'

                       /* 单独神经阻滞麻醉 */
                       WHEN TRIM(a.STRING_VALUE) LIKE '%神经阻滞%'
                         OR TRIM(a.STRING_VALUE) LIKE '%阴部神经%'
                         OR TRIM(a.STRING_VALUE) LIKE '%神经组织%'
                       THEN '33'

                       /* 单独局部浸润麻醉 */
                       WHEN TRIM(a.STRING_VALUE) LIKE '%局部浸润%'
                         OR TRIM(a.STRING_VALUE) LIKE '%局部经润%'
                         OR TRIM(a.STRING_VALUE) LIKE '%局部侵润%'
                         OR TRIM(a.STRING_VALUE) LIKE '%局部浸入%'
                       THEN '35'

                       /* 单独局部麻醉 */
                       WHEN TRIM(a.STRING_VALUE) LIKE '%局部麻醉%'
                         OR TRIM(a.STRING_VALUE) = '局部浸润'
                         OR TRIM(a.STRING_VALUE) = '局部'
                       THEN '3'

                       /* 原始值本身就是标准代码 */
                       WHEN TRIM(a.STRING_VALUE) IN ('1','2','3','4','9','11','12','13','21','22',
                                                     '31','32','33','34','35','36','41','42','43','44','45')
                       THEN TRIM(a.STRING_VALUE)

                       ELSE '9'
                   END
              FROM mcs_doc_form_records a
             WHERE a.template_code = WSFL.TEMPLATE_CODE
               AND a.node_code = '00044'
               AND a.FORM_ID = WSFL.ID
               AND ROWNUM = 1),
           '9'
       ) AS ANES_METHOD_CODE, -- 麻醉方法代码：4复合麻醉，33神经阻滞麻醉，35局部浸润麻醉，3局部麻醉，9其他

       NVL(
           (SELECT CASE
                       WHEN (
                                TRIM(a.STRING_VALUE) LIKE '%神经阻滞%'
                             OR TRIM(a.STRING_VALUE) LIKE '%阴部神经%'
                             OR TRIM(a.STRING_VALUE) LIKE '%神经组织%'
                            )
                            AND (
                                TRIM(a.STRING_VALUE) LIKE '%局部%'
                             OR TRIM(a.STRING_VALUE) LIKE '%浸润%'
                             OR TRIM(a.STRING_VALUE) LIKE '%经润%'
                             OR TRIM(a.STRING_VALUE) LIKE '%侵润%'
                             OR TRIM(a.STRING_VALUE) LIKE '%浸入%'
                            )
                       THEN '复合麻醉'

                       WHEN TRIM(a.STRING_VALUE) LIKE '%神经阻滞%'
                         OR TRIM(a.STRING_VALUE) LIKE '%阴部神经%'
                         OR TRIM(a.STRING_VALUE) LIKE '%神经组织%'
                       THEN '神经阻滞麻醉'

                       WHEN TRIM(a.STRING_VALUE) LIKE '%局部浸润%'
                         OR TRIM(a.STRING_VALUE) LIKE '%局部经润%'
                         OR TRIM(a.STRING_VALUE) LIKE '%局部侵润%'
                         OR TRIM(a.STRING_VALUE) LIKE '%局部浸入%'
                       THEN '局部浸润麻醉'

                       WHEN TRIM(a.STRING_VALUE) LIKE '%局部麻醉%'
                         OR TRIM(a.STRING_VALUE) = '局部浸润'
                         OR TRIM(a.STRING_VALUE) = '局部'
                       THEN '局部麻醉'

                       WHEN TRIM(a.STRING_VALUE) = '1'  THEN '全身麻醉'
                       WHEN TRIM(a.STRING_VALUE) = '2'  THEN '椎管内麻醉'
                       WHEN TRIM(a.STRING_VALUE) = '3'  THEN '局部麻醉'
                       WHEN TRIM(a.STRING_VALUE) = '4'  THEN '复合麻醉'
                       WHEN TRIM(a.STRING_VALUE) = '9'  THEN '其他麻醉方法'
                       WHEN TRIM(a.STRING_VALUE) = '11' THEN '吸入麻醉'
                       WHEN TRIM(a.STRING_VALUE) = '12' THEN '静脉麻醉'
                       WHEN TRIM(a.STRING_VALUE) = '13' THEN '基础麻醉'
                       WHEN TRIM(a.STRING_VALUE) = '21' THEN '蛛网膜下腔阻滞麻醉'
                       WHEN TRIM(a.STRING_VALUE) = '22' THEN '硬脊膜外腔阻滞麻醉'
                       WHEN TRIM(a.STRING_VALUE) = '31' THEN '神经丛阻滞麻醉'
                       WHEN TRIM(a.STRING_VALUE) = '32' THEN '神经节阻滞麻醉'
                       WHEN TRIM(a.STRING_VALUE) = '33' THEN '神经阻滞麻醉'
                       WHEN TRIM(a.STRING_VALUE) = '34' THEN '区域阻滞麻醉'
                       WHEN TRIM(a.STRING_VALUE) = '35' THEN '局部浸润麻醉'
                       WHEN TRIM(a.STRING_VALUE) = '36' THEN '表面麻醉'
                       WHEN TRIM(a.STRING_VALUE) = '41' THEN '静吸复合全麻'
                       WHEN TRIM(a.STRING_VALUE) = '42' THEN '针药复合麻醉'
                       WHEN TRIM(a.STRING_VALUE) = '43' THEN '神经丛与硬膜外阻滞复合麻醉'
                       WHEN TRIM(a.STRING_VALUE) = '44' THEN '全麻复合全身降温'
                       WHEN TRIM(a.STRING_VALUE) = '45' THEN '全麻复合控制性降压'

                       ELSE '其他麻醉方法'
                   END
              FROM mcs_doc_form_records a
             WHERE a.template_code = WSFL.TEMPLATE_CODE
               AND a.node_code = '00044'
               AND a.FORM_ID = WSFL.ID
               AND ROWNUM = 1),
           '其他麻醉方法'
       ) AS ANAESTHESIA_NAME, -- 麻醉方法

       SUBSTRB(
           NVL(
               (SELECT a.STRING_VALUE
                  FROM mcs_doc_form_records a
                 WHERE a.template_code = WSFL.TEMPLATE_CODE
                   AND a.node_code = '00044'
                   AND a.FORM_ID = WSFL.ID
                   AND ROWNUM = 1),
               '无'
           ),
           1,
           50
       ) AS ANES_DRUG_NAME, -- 麻醉药物名称，是

       '0' AS VAGNIAL_CODE, -- 阴道裂伤标志；旧 SQL无可靠来源，暂按无

       '0' AS HEAMATORA_CODE, -- 阴道血肿标志；旧 SQL固定无，按标准改为0

       CAST(NULL AS VARCHAR2(50)) AS HEAMATORA_SIZE, -- 阴道血肿大小

       CAST(NULL AS VARCHAR2(200)) AS HEAMATORA_HANDLE, -- 阴道血肿处理

       '0' AS LACERATION_CODE, -- 宫颈裂伤标志，是；旧 SQL无可靠来源，暂按无

       '无' AS SUTURE_NOTE, -- 宫颈缝合情况，是

       CAST(NULL AS VARCHAR2(100)) AS ANUS_CHECK, -- 肛查

       SUBSTRB(
           (SELECT a.STRING_VALUE
              FROM mcs_doc_form_records a
             WHERE a.template_code = WSFL.TEMPLATE_CODE
               AND a.node_code = '00043'
               AND a.FORM_ID = WSFL.ID
               AND ROWNUM = 1),
           1,
           50
       ) AS AFTER_DRUG, -- 产后用药

       SUBSTRB(
           (SELECT a.STRING_VALUE
              FROM mcs_doc_form_records a
             WHERE a.template_code = WSFL.TEMPLATE_CODE
               AND a.node_code = '00085'
               AND a.FORM_ID = WSFL.ID
               AND ROWNUM = 1),
           1,
           200
       ) AS SPECIAL_RECORD, -- 分娩过程特殊情况描述

       SUBSTRB(
           (SELECT a.STRING_VALUE
              FROM mcs_doc_form_records a
             WHERE a.template_code IN ('819', '737')
               AND a.node_code = '00007'
               AND a.patient_uid = WSFL.Patient_Uid
               AND ROWNUM = 1),
           1,
           200
       ) AS CONTRACTION_NOTE, -- 宫缩情况

       SUBSTRB(
           (SELECT a.STRING_VALUE
              FROM mcs_doc_form_records a
             WHERE a.template_code = WSFL.TEMPLATE_CODE
               AND a.node_code = '00125'
               AND a.FORM_ID = WSFL.ID
               AND ROWNUM = 1),
           1,
           100
       ) AS UTERUS_RESULT, -- 子宫情况

       SUBSTRB(
           (SELECT a.STRING_VALUE
              FROM mcs_doc_form_records a
             WHERE a.template_code = WSFL.TEMPLATE_CODE
               AND a.node_code = '00072'
               AND a.FORM_ID = WSFL.ID
               AND ROWNUM = 1),
           1,
           100
       ) AS LOCHIA_REMARKS, -- 恶露状况

       SUBSTRB(
           (SELECT a.STRING_VALUE
              FROM mcs_doc_form_records a
             WHERE a.template_code = WSFL.TEMPLATE_CODE
               AND a.node_code = '00085'
               AND a.FORM_ID = WSFL.ID
               AND ROWNUM = 1),
           1,
           100
       ) AS REPAIR_OPERA, -- 修补手术过程

       CASE
           WHEN (SELECT a.STRING_VALUE
                   FROM mcs_doc_form_records a
                  WHERE a.template_code = WSFL.TEMPLATE_CODE
                    AND a.node_code = '00126'
                    AND a.FORM_ID = WSFL.ID
                    AND ROWNUM = 1) LIKE '%是%'
           THEN '1'
           ELSE '0'
       END AS SAVE_BLOOD_CODE, -- 存脐带血情况标志

       SUBSTRB(NVL(TO_CHAR(YDZD.diagnosis), NVL(TO_CHAR(YDZD.diagnosis_name), '-')), 1, 200) AS AFTER_OPER_DIAGNOSIS, -- 产后诊断，是

       TO_CHAR(
           (SELECT TO_DATE(a.STRING_VALUE, 'yyyy-mm-dd hh24:mi:ss')
              FROM mcs_doc_form_records a
             WHERE a.template_code = WSFL.TEMPLATE_CODE
               AND a.node_code = '00090'
               AND a.FORM_ID = WSFL.ID
               AND REGEXP_LIKE(a.STRING_VALUE, '^[0-9]{4}-[0-9]{2}-[0-9]{2}')
               AND ROWNUM = 1),
           'yyyy-mm-dd hh24:mi:ss'
       ) AS ALTER_OBS_DATE, -- 产后观察日期时间

       CAST(0 AS NUMBER(3)) AS CHECK_TIME, -- 产后检查时间（min）

       NVL(
           (SELECT TO_NUMBER(REGEXP_SUBSTR(a.STRING_VALUE, '[0-9]+'))
              FROM mcs_doc_form_records a
             WHERE a.template_code = WSFL.TEMPLATE_CODE
               AND a.node_code = '00040'
               AND a.FORM_ID = WSFL.ID
               AND REGEXP_LIKE(a.STRING_VALUE, '[0-9]')
               AND ROWNUM = 1),
           0
       ) AS SYSTOLIC_PRESSURE, -- 产后收缩压

       NVL(
           (SELECT TO_NUMBER(REGEXP_SUBSTR(a.STRING_VALUE, '[0-9]+'))
              FROM mcs_doc_form_records a
             WHERE a.template_code = WSFL.TEMPLATE_CODE
               AND a.node_code = '00041'
               AND a.FORM_ID = WSFL.ID
               AND REGEXP_LIKE(a.STRING_VALUE, '[0-9]')
               AND ROWNUM = 1),
           0
       ) AS DIASTOLIC_PRESSURE, -- 产后舒张压

       CAST(0 AS NUMBER(3)) AS PULSE_RATE, -- 产后脉搏；旧 SQL无可靠来源

       CAST(999 AS NUMBER(3)) AS HEART_RATE, -- 产后心率，是；旧 SQL无可靠来源，暂为0

       NVL(
           (SELECT TO_NUMBER(REGEXP_SUBSTR(a.STRING_VALUE, '[0-9]+'))
              FROM mcs_doc_form_records a
             WHERE a.template_code = WSFL.TEMPLATE_CODE
               AND a.node_code = '00039'
               AND a.FORM_ID = WSFL.ID
               AND REGEXP_LIKE(a.STRING_VALUE, '[0-9]')
               AND ROWNUM = 1),
           0
       ) AS OUT_BLOOD_ML, -- 产后出血量（mL）

       CAST(NULL AS VARCHAR2(200)) AS AFTER_CONTRACTION, -- 产后宫缩

       CAST(0 AS NUMBER(4,1)) AS HAREM_HEIGHT, -- 产后宫底高度

       '0' AS BLADDER_CODE, -- 产后膀胱充盈标志；无可靠来源，暂按否

       CASE
           WHEN (SELECT COUNT(*)
                   FROM mcs_doc_form_records a
                  WHERE a.FORM_ID = WSFL.ID
                    AND a.node_code = '00062'
                    AND a.NUMBER_VALUE IS NOT NULL) > 0
           THEN '1'
           ELSE '2'
       END AS CHILD_SEX_CODE, -- 新生儿性别代码

       CASE
           WHEN (SELECT COUNT(*)
                   FROM mcs_doc_form_records a
                  WHERE a.FORM_ID = WSFL.ID
                    AND a.node_code = '00062'
                    AND a.NUMBER_VALUE IS NOT NULL) > 0
           THEN '男'
           ELSE '女'
       END AS SEX_NAME, -- 新生儿性别名称，是

       NVL(
           (SELECT TO_NUMBER(REGEXP_SUBSTR(a.STRING_VALUE, '[0-9]+'))
              FROM mcs_doc_form_records a
             WHERE a.template_code = WSFL.TEMPLATE_CODE
               AND a.node_code = '00065'
               AND a.FORM_ID = WSFL.ID
               AND REGEXP_LIKE(a.STRING_VALUE, '[0-9]')
               AND ROWNUM = 1),
           0
       ) AS NEWBORN_HEAVY, -- 新生儿出生体重（g）

       NVL(
           (SELECT TO_NUMBER(REGEXP_SUBSTR(a.STRING_VALUE, '[0-9]+(\.[0-9]+)?'))
              FROM mcs_doc_form_records a
             WHERE a.template_code = WSFL.TEMPLATE_CODE
               AND a.node_code = '00064'
               AND a.FORM_ID = WSFL.ID
               AND REGEXP_LIKE(a.STRING_VALUE, '[0-9]')
               AND ROWNUM = 1),
           0
       ) AS NEWBORN_LONG, -- 新生儿出生身长（cm）

       CAST(NULL AS VARCHAR2(100)) AS TUMOR_SIZE, -- 产瘤大小

       CAST(NULL AS VARCHAR2(100)) AS TUMOR_PART, -- 产瘤部位

       '3' AS APGAR, -- Apgar评分间隔时间代码：3代表10min

       CAST(10 AS NUMBER(3)) AS APGAR_TIME, -- Apgar评分间隔时间

       NVL(
           (SELECT TO_NUMBER(REGEXP_SUBSTR(a.STRING_VALUE, '[0-9]+'))
              FROM mcs_doc_form_records a
             WHERE a.template_code = WSFL.TEMPLATE_CODE
               AND a.node_code = '00078'
               AND a.FORM_ID = WSFL.ID
               AND REGEXP_LIKE(a.STRING_VALUE, '[0-9]')
               AND ROWNUM = 1),
           0
       ) AS APGAR_SCORE, -- Apgar评分值

       CASE
           WHEN (SELECT a.STRING_VALUE
                   FROM mcs_doc_form_records a
                  WHERE a.FORM_ID = WSFL.ID
                    AND a.node_code = '00123'
                    AND ROWNUM = 1) = '死胎'
           THEN '2'
           WHEN (SELECT a.STRING_VALUE
                   FROM mcs_doc_form_records a
                  WHERE a.FORM_ID = WSFL.ID
                    AND a.node_code = '00123'
                    AND ROWNUM = 1) = '死产'
           THEN '3'
           ELSE '1'
       END AS DELIVERY_OUTCOME_CODE, -- 分娩结局代码，是

       SUBSTRB(
           NVL(
               (SELECT a.STRING_VALUE
                  FROM mcs_doc_form_records a
                 WHERE a.template_code = WSFL.TEMPLATE_CODE
                   AND a.node_code = '00123'
                   AND a.FORM_ID = WSFL.ID
                   AND ROWNUM = 1),
               '活产'
           ),
           1,
           20
       ) AS DELIVERY_OUTCOME, -- 分娩结局
       NVL(
           (SELECT CASE
                       WHEN TRIM(a.STRING_VALUE) = '无' THEN '1'
                       WHEN TRIM(a.STRING_VALUE) LIKE '%早产%' THEN '4'
                       WHEN TRIM(a.STRING_VALUE) LIKE '%窒息%' THEN '5'
                       WHEN TRIM(a.STRING_VALUE) LIKE '%低体重%'
                         OR TRIM(a.STRING_VALUE) LIKE '%低出生体重%'
                       THEN '6'
                       WHEN TRIM(a.STRING_VALUE) LIKE '%畸形%' THEN '3'
                       WHEN TRIM(a.STRING_VALUE) LIKE '%死亡%' THEN '2'
                       ELSE '9'
                   END
              FROM mcs_doc_form_records a
             WHERE a.template_code = WSFL.TEMPLATE_CODE
               AND a.node_code = '00124'
               AND a.FORM_ID = WSFL.ID
               AND ROWNUM = 1),
           '1'
       ) AS CHILD_ADNORMAL_CODE, -- 新生儿异常情况代码：1无 2早期新生儿死亡 3畸形 4早产 5窒息 6低出生体重 9其他

       SUBSTRB(
           NVL(
               (SELECT CASE
                           WHEN INSTR(a.STRING_VALUE, '|') > 0
                           THEN SUBSTR(a.STRING_VALUE, 1, INSTR(a.STRING_VALUE, '|') - 1)
                           ELSE a.STRING_VALUE
                       END
                  FROM mcs_doc_form_records a
                 WHERE a.template_code = WSFL.TEMPLATE_CODE
                   AND a.node_code = '00088'
                   AND a.FORM_ID = WSFL.ID
                   AND ROWNUM = 1),
               NVL(WSFL.Created_Name, WSFL.last_updated_name)
           ),
           1,
           50
       ) AS ACCOUCHE_PERSON_NAME, -- 接生人员签名

       CAST(NULL AS VARCHAR2(50)) AS OPERA_DOC_NAME, -- 手术医生签名；阴道分娩无可靠来源

       SUBSTRB(
           (SELECT CASE
                       WHEN INSTR(a.STRING_VALUE, '|') > 0
                       THEN SUBSTR(a.STRING_VALUE, 1, INSTR(a.STRING_VALUE, '|') - 1)
                       ELSE a.STRING_VALUE
                   END
              FROM mcs_doc_form_records a
             WHERE a.template_code = '742'
               AND a.node_code = '00070'
               AND a.patient_uid = WSFL.Patient_Uid
               AND ROWNUM = 1),
           1,
           50
       ) AS PEDIATRICIAN_NAME, -- 儿科医生签名；旧 SQL护婴者

       SUBSTRB(NVL(TO_CHAR(WSFL.created_name), TO_CHAR(WSFL.last_updated_name)), 1, 50) AS RECORD_PERSON_NAME, -- 记录人员签名

       '370104' AS DISTRICT_CODE, -- 行政区划，是

       'ADDHIS' AS EXCHANGE_TYPE, -- 交换类型，是

       TO_CHAR(SYSDATE, 'yyyy-mm-dd hh24:mi:ss') AS SYSTEM_TIME -- 数据上传时间，是

  FROM MCS_DOC_FORM WSFL
       JOIN inpatients YDZD
         ON WSFL.PATIENT_UID = YDZD.PAT_INDEX_NO

       LEFT JOIN dept_dict@his dept
         ON dept.dept_code = YDZD.dept_code

       LEFT JOIN pat_visit@HIS p
         ON p.PATIENT_ID = SUBSTR(YDZD.PATIENT_ID, 1, INSTR(YDZD.PATIENT_ID, '_') - 1)
        AND p.VISIT_ID = YDZD.SERIES

       LEFT JOIN DIAGNOSIS@HIS dg
         ON dg.PATIENT_ID = p.PATIENT_ID
        AND dg.VISIT_ID = p.VISIT_ID
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

 WHERE WSFL.TEMPLATE_CODE = '746'
   AND WSFL.is_valid = '1'
   AND WSFL.created_by <> 'dba'    AND p.DISCHARGE_DATE_TIME < TO_DATE('2025-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss')
