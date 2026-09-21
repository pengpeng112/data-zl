
  CREATE OR REPLACE FORCE VIEW "ODS"."V_EMR_OUTPATIENT_DIAG" ("ID", "OUTPATIENT_NUM", "TCM_WM_MARK_CODE", "TCM_WM_MARK_NAME", "IF_MAIN", "ADMIN_ILLNESS_CODE", "ADMIN_ILLNESS_NAME", "INFECTIOUS_SIGNS", "CONTAGIOUS_REPORT_SIGN", "ORG_CODE", "ORG_NAME", "CHINA_MED_SYNDROME_CODE", "CHINA_MED_SYNDROME_NAME", "DOCTOR_ID_NUM", "DOCTOR_NAME", "DIAG_DATE", "DISTRICT_CODE", "SYSTEM_TIME", "EXCHANGE_TYPE", "NAME", "SEX_CODE", "ID_NUM", "DIAGNOSIS_NO", "LOCAL_DIAGNOSIS_CODE", "LOCAL_DIAGNOSIS_NAME", "NHS_DX_CODE", "NHS_DX_NAME") AS 
  SELECT SUBSTR(
           '49557032X'
           || '|' || NVL(NULLIF(TRIM(z.clinic_no), ''), '-')
           || '|NEW|'
           || NVL(TO_CHAR(z.item_no), '0')
           || '|' || NVL(NULLIF(TRIM(z.diag_code), ''), '-'),
           1,
           100
       ) AS ID, -- 内码，主键

       SUBSTR(
           NVL(
               NULLIF(TRIM(z.clinic_no), ''),
               z.patient_id || TO_CHAR(z.visit_date, 'yyyymmdd')
           ),
           1,
           32
       ) AS OUTPATIENT_NUM, -- 本次门诊标识符

       CASE
           WHEN z.diag_type IS NULL THEN '2'
           ELSE '1'
       END AS TCM_WM_MARK_CODE, -- 中医/西医诊断类型：1中医，2西医

       CASE
           WHEN z.diag_type IS NULL THEN '西医'
           ELSE '中医'
       END AS TCM_WM_MARK_NAME, -- 中医/西医诊断类型名称

       CASE
           WHEN z.item_no = 1 THEN '1'
           ELSE '0'
       END AS IF_MAIN, -- 是否主要诊断标识

       SUBSTR(
           NVL(
               NULLIF(TRIM(z.icd_or_code), ''),
               NVL(NULLIF(TRIM(z.diag_code), ''), '-')
           ),
           1,
           12
       ) AS ADMIN_ILLNESS_CODE, -- 诊断疾病代码

       SUBSTR(
           NVL(
               NULLIF(TRIM(z.icd_or_name), ''),
               NVL(NULLIF(TRIM(z.diag_desc), ''), '-')
           ),
           1,
           100
       ) AS ADMIN_ILLNESS_NAME, -- 诊断疾病名称

       z.infect_flag AS INFECTIOUS_SIGNS, -- 传染标识

       z.infect_flag AS CONTAGIOUS_REPORT_SIGN, -- 传染上报标识

       '49557032X' AS ORG_CODE, -- 医院组织机构编码

       '山东省第二人民医院' AS ORG_NAME, -- 医院名称

       '-' AS CHINA_MED_SYNDROME_CODE, -- 中医证候代码；暂无真实来源

       '-' AS CHINA_MED_SYNDROME_NAME, -- 中医证候名称；暂无真实来源

       SUBSTR(NVL(NULLIF(TRIM(z.doctor_id_no), ''), '000000000000000000'), 1, 18) AS DOCTOR_ID_NUM, -- 诊断医师身份证号

       SUBSTR(NVL(NULLIF(TRIM(z.doctor_name), ''), NVL(NULLIF(TRIM(z.doctor), ''), '-')), 1, 50) AS DOCTOR_NAME, -- 诊断医师姓名

       CAST(z.visit_date AS DATE) AS DIAG_DATE, -- 诊断日期

       '370104' AS DISTRICT_CODE, -- 所属行政区划

       CAST(SYSTIMESTAMP AS TIMESTAMP) AS SYSTEM_TIME, -- 数据上传时间戳

       'ADDHIS' AS EXCHANGE_TYPE, -- 交换类型

       SUBSTR(NVL(NULLIF(TRIM(z.patient_name), ''), '-'), 1, 50) AS NAME, -- 患者姓名

       CASE TRIM(z.sex)
           WHEN '男' THEN '1'
           WHEN '女' THEN '2'
           WHEN '未知' THEN '0'
           WHEN '不详' THEN '9'
           WHEN '未说明' THEN '9'
           ELSE '9'
       END AS SEX_CODE, -- 患者性别代码

       SUBSTR(NVL(NULLIF(TRIM(z.patient_id_no), ''), '000000000000000000'), 1, 18) AS ID_NUM, -- 患者身份证件号码

       SUBSTR(NVL(TO_CHAR(z.item_no), '1'), 1, 20) AS DIAGNOSIS_NO, -- 诊断序号

       SUBSTR(
           NVL(
               NULLIF(TRIM(z.diag_code), ''),
               NVL(
                   NULLIF(TRIM(z.insur_diag_code), ''),
                   NVL(NULLIF(TRIM(z.icd_or_code), ''), '-')
               )
           ),
           1,
           50
       ) AS LOCAL_DIAGNOSIS_CODE, -- 院内诊断编码，源为空时用医保诊断/标准诊断兜底

       SUBSTR(
           NVL(
               NULLIF(TRIM(z.diag_desc), ''),
               NVL(
                   NULLIF(TRIM(z.insur_diag_desc), ''),
                   NVL(NULLIF(TRIM(z.icd_or_name), ''), '-')
               )
           ),
           1,
           200
       ) AS LOCAL_DIAGNOSIS_NAME, -- 院内诊断名称，源为空时用医保诊断/标准诊断兜底

       SUBSTR(NULLIF(TRIM(z.insur_diag_code), ''), 1, 50) AS NHS_DX_CODE, -- 医保报销诊断编码

       SUBSTR(NULLIF(TRIM(z.insur_diag_desc), ''), 1, 200) AS NHS_DX_NAME -- 医保报销诊断名称

  FROM (
        SELECT y.*,
               CASE
                   WHEN REGEXP_LIKE(
                            UPPER(NVL(NULLIF(TRIM(y.icd_or_code), ''), NULLIF(TRIM(y.diag_code), ''))),
                            '^(A00|A01|A02|A03|A04|A05|A06|A09|A15|A16|A17|A18|A19|A20|A22|A27|A30|A33|A35|A36|A37|A38|A39|A50|A51|A52|A53|A54|A56|A64|A80|A82|A83|A90|A91|A92|A95|A98|B01|B05|B06|B15|B16|B17|B18|B19|B20|B21|B22|B23|B24|B26|B50|B51|B52|B53|B54|U07)'
                        )
                     OR REGEXP_LIKE(
                            NVL(NULLIF(TRIM(y.icd_or_name), ''), NULLIF(TRIM(y.diag_desc), '')),
                            '霍乱|鼠疫|炭疽|艾滋|HIV|病毒性肝炎|甲肝|乙肝|丙肝|戊肝|肺结核|结核|麻疹|风疹|水痘|流行性腮腺炎'
                        )
                     OR REGEXP_LIKE(
                            NVL(NULLIF(TRIM(y.icd_or_name), ''), NULLIF(TRIM(y.diag_desc), '')),
                            '流行性感冒|流感|新型冠状|新冠|COVID|手足口|猩红热|百日咳|白喉|脊髓灰质炎|流脑|乙脑'
                        )
                     OR REGEXP_LIKE(
                            NVL(NULLIF(TRIM(y.icd_or_name), ''), NULLIF(TRIM(y.diag_desc), '')),
                            '伤寒|副伤寒|细菌性痢疾|阿米巴痢疾|感染性腹泻|痢疾|布鲁菌|布病|钩端螺旋体|血吸虫|疟疾|登革热'
                        )
                     OR REGEXP_LIKE(
                            NVL(NULLIF(TRIM(y.icd_or_name), ''), NULLIF(TRIM(y.diag_desc), '')),
                            '梅毒|淋病|尖锐湿疣|生殖器疱疹|狂犬病|破伤风|人感染高致病性禽流感|禽流感'
                        )
                   THEN 1
                   ELSE 0
               END AS infect_flag
          FROM (
                SELECT q.*,

                       NVL(
                           NULLIF(TRIM(icd_code.std_diag_code), ''),
                           NVL(
                               NULLIF(TRIM(icd_local.std_diag_code), ''),
                               NULLIF(TRIM(icd_std.std_diag_code), '')
                           )
                       ) AS icd_or_code,

                       NVL(
                           NULLIF(TRIM(icd_code.std_diag_name), ''),
                           NVL(
                               NULLIF(TRIM(icd_local.std_diag_name), ''),
                               NULLIF(TRIM(icd_std.std_diag_name), '')
                           )
                       ) AS icd_or_name

                  FROM (
                        SELECT a.visit_date,
                               a.visit_no,
                               TO_CHAR(a.patient_id) AS patient_id,
                               a.item_no,
                               TO_CHAR(a.diag_code) AS diag_code,
                               TO_CHAR(a.diag_desc) AS diag_desc,
                               TO_CHAR(a.diag_type) AS diag_type,
                               TO_CHAR(a.doctor) AS doctor,
                               TO_CHAR(a.insur_diag_code) AS insur_diag_code,
                               TO_CHAR(a.insur_diag_desc) AS insur_diag_desc,
                               TO_CHAR(b.clinic_no) AS clinic_no,
                               TO_CHAR(c.id_no) AS doctor_id_no,
                               TO_CHAR(c.name) AS doctor_name,
                               TO_CHAR(pmi.name) AS patient_name,
                               TO_CHAR(pmi.sex) AS sex,
                               TO_CHAR(pmi.id_no) AS patient_id_no
                          FROM HIS.outp_mr_diag_desc a
                          JOIN HIS.clinic_master b
                            ON a.visit_date = b.visit_date
                           AND a.visit_no = b.visit_no
                           AND a.patient_id = b.patient_id
                          LEFT JOIN HIS.staff_dict c
                            ON TO_CHAR(a.doctor) = TO_CHAR(c.emp_no)
                          JOIN HIS.pat_master_index pmi
                            ON a.patient_id = pmi.patient_id
                         WHERE a.visit_date >= DATE '2021-01-01'
                           AND a.visit_date <  DATE '2025-01-01'
                       ) q

                  LEFT JOIN (
                        SELECT TO_CHAR(cd.院标编码) AS match_value,
                               MAX(TO_CHAR(cd.国标编码)) AS std_diag_code,
                               MAX(TO_CHAR(cd.国标名称)) AS std_diag_name
                          FROM CDA.cda_dictionary cd
                         WHERE TO_CHAR(cd.字典名称) = 'ICD-10诊断编码'
                           AND TO_CHAR(cd.系统标识) = 'HIS'
                           AND cd.院标编码 IS NOT NULL
                         GROUP BY TO_CHAR(cd.院标编码)
                       ) icd_code
                    ON icd_code.match_value = q.diag_code

                  LEFT JOIN (
                        SELECT TO_CHAR(cd.院标名称) AS match_value,
                               MAX(TO_CHAR(cd.国标编码)) AS std_diag_code,
                               MAX(TO_CHAR(cd.国标名称)) AS std_diag_name
                          FROM CDA.cda_dictionary cd
                         WHERE TO_CHAR(cd.字典名称) = 'ICD-10诊断编码'
                           AND TO_CHAR(cd.系统标识) = 'HIS'
                           AND cd.院标名称 IS NOT NULL
                         GROUP BY TO_CHAR(cd.院标名称)
                       ) icd_local
                    ON icd_local.match_value = q.diag_desc

                  LEFT JOIN (
                        SELECT TO_CHAR(cd.国标名称) AS match_value,
                               MAX(TO_CHAR(cd.国标编码)) AS std_diag_code,
                               MAX(TO_CHAR(cd.国标名称)) AS std_diag_name
                          FROM CDA.cda_dictionary cd
                         WHERE TO_CHAR(cd.字典名称) = 'ICD-10诊断编码'
                           AND TO_CHAR(cd.系统标识) = 'HIS'
                           AND cd.国标名称 IS NOT NULL
                         GROUP BY TO_CHAR(cd.国标名称)
                       ) icd_std
                    ON icd_std.match_value = q.diag_desc
               ) y
       ) z

UNION ALL

/* =========================================================
   OLD 分支：HIS.OUTP_MR
   处理原则：
   1. 所有字符字段统一 TO_CHAR，避免 ORA-12704
   2. 本地诊断编码：diag_desc_code -> admin_code_by_name -> '-'
   3. 本地诊断名称：diag_desc -> admin_name_by_name -> '-'
   ========================================================= */
SELECT SUBSTR(
           '49557032X'
           || '|' || NVL(NULLIF(TRIM(z.clinic_no), ''), '-')
           || '|OLD|'
           || NVL(TO_CHAR(z.ordinal), '1')
           || '|' || NVL(NULLIF(TRIM(z.diag_desc_code), ''), '-'),
           1,
           100
       ) AS ID, -- 内码，主键

       SUBSTR(
           NVL(
               NULLIF(TRIM(z.clinic_no), ''),
               z.patient_id || TO_CHAR(z.visit_date, 'yyyymmdd')
           ),
           1,
           32
       ) AS OUTPATIENT_NUM, -- 本次门诊标识符

       CASE
           WHEN z.diag_desc IS NOT NULL THEN '2'
           ELSE '1'
       END AS TCM_WM_MARK_CODE, -- 中医/西医诊断类型

       CASE
           WHEN z.diag_desc IS NOT NULL THEN '西医'
           ELSE '中医'
       END AS TCM_WM_MARK_NAME, -- 中医/西医诊断类型名称

       CASE
           WHEN NVL(z.ordinal, 1) = 1 THEN '1'
           ELSE '0'
       END AS IF_MAIN, -- 是否主要诊断标识

       SUBSTR(
           NVL(
               NULLIF(TRIM(z.admin_code_by_name), ''),
               NVL(NULLIF(TRIM(z.diag_desc_code), ''), '-')
           ),
           1,
           12
       ) AS ADMIN_ILLNESS_CODE, -- 诊断疾病代码

       SUBSTR(
           NVL(
               NULLIF(TRIM(z.admin_name_by_name), ''),
               NVL(NULLIF(TRIM(z.diag_desc), ''), '-')
           ),
           1,
           100
       ) AS ADMIN_ILLNESS_NAME, -- 诊断疾病名称

       z.infect_flag AS INFECTIOUS_SIGNS, -- 传染标识

       z.infect_flag AS CONTAGIOUS_REPORT_SIGN, -- 传染上报标识

       '49557032X' AS ORG_CODE, -- 医院组织机构编码

       '山东省第二人民医院' AS ORG_NAME, -- 医院名称

       '-' AS CHINA_MED_SYNDROME_CODE, -- 中医证候代码；暂无真实来源

       '-' AS CHINA_MED_SYNDROME_NAME, -- 中医证候名称；暂无真实来源

       SUBSTR(NVL(NULLIF(TRIM(z.doctor_id_no), ''), '000000000000000000'), 1, 18) AS DOCTOR_ID_NUM, -- 诊断医师身份证号

       SUBSTR(NVL(NULLIF(TRIM(z.doctor_name), ''), NVL(NULLIF(TRIM(z.doctor), ''), '-')), 1, 50) AS DOCTOR_NAME, -- 诊断医师姓名

       CAST(NVL(z.illness_date, z.visit_date) AS DATE) AS DIAG_DATE, -- 诊断日期

       '370104' AS DISTRICT_CODE, -- 所属行政区划

       CAST(SYSTIMESTAMP AS TIMESTAMP) AS SYSTEM_TIME, -- 数据上传时间戳

       'ADDHIS' AS EXCHANGE_TYPE, -- 交换类型

       SUBSTR(NVL(NULLIF(TRIM(z.patient_name), ''), '-'), 1, 50) AS NAME, -- 患者姓名

       CASE TRIM(z.sex)
           WHEN '男' THEN '1'
           WHEN '女' THEN '2'
           WHEN '未知' THEN '0'
           WHEN '不详' THEN '9'
           WHEN '未说明' THEN '9'
           ELSE '9'
       END AS SEX_CODE, -- 患者性别代码

       SUBSTR(NVL(NULLIF(TRIM(z.patient_id_no), ''), '000000000000000000'), 1, 18) AS ID_NUM, -- 患者身份证件号码

       SUBSTR(NVL(TO_CHAR(z.ordinal), '1'), 1, 20) AS DIAGNOSIS_NO, -- 诊断序号

       SUBSTR(
           NVL(
               NULLIF(TRIM(z.diag_desc_code), ''),
               NVL(NULLIF(TRIM(z.admin_code_by_name), ''), '-')
           ),
           1,
           50
       ) AS LOCAL_DIAGNOSIS_CODE, -- 院内诊断编码，源为空时用诊断名称对照编码兜底

       SUBSTR(
           NVL(
               NULLIF(TRIM(z.diag_desc), ''),
               NVL(NULLIF(TRIM(z.admin_name_by_name), ''), '-')
           ),
           1,
           200
       ) AS LOCAL_DIAGNOSIS_NAME, -- 院内诊断名称，源为空时用诊断名称对照名称兜底

       CAST(NULL AS VARCHAR2(50)) AS NHS_DX_CODE, -- 医保报销诊断编码，旧表暂无来源

       CAST(NULL AS VARCHAR2(200)) AS NHS_DX_NAME -- 医保报销诊断名称，旧表暂无来源

  FROM (
        SELECT y.*,
               CASE
                   WHEN REGEXP_LIKE(
                            UPPER(NVL(NULLIF(TRIM(y.infect_code_or), ''), NULLIF(TRIM(y.diag_desc_code), ''))),
                            '^(A00|A01|A02|A03|A04|A05|A06|A09|A15|A16|A17|A18|A19|A20|A22|A27|A30|A33|A35|A36|A37|A38|A39|A50|A51|A52|A53|A54|A56|A64|A80|A82|A83|A90|A91|A92|A95|A98|B01|B05|B06|B15|B16|B17|B18|B19|B20|B21|B22|B23|B24|B26|B50|B51|B52|B53|B54|U07)'
                        )
                     OR REGEXP_LIKE(
                            NVL(NULLIF(TRIM(y.infect_name_or), ''), NULLIF(TRIM(y.diag_desc), '')),
                            '霍乱|鼠疫|炭疽|艾滋|HIV|病毒性肝炎|甲肝|乙肝|丙肝|戊肝|肺结核|结核|麻疹|风疹|水痘|流行性腮腺炎'
                        )
                     OR REGEXP_LIKE(
                            NVL(NULLIF(TRIM(y.infect_name_or), ''), NULLIF(TRIM(y.diag_desc), '')),
                            '流行性感冒|流感|新型冠状|新冠|COVID|手足口|猩红热|百日咳|白喉|脊髓灰质炎|流脑|乙脑'
                        )
                     OR REGEXP_LIKE(
                            NVL(NULLIF(TRIM(y.infect_name_or), ''), NULLIF(TRIM(y.diag_desc), '')),
                            '伤寒|副伤寒|细菌性痢疾|阿米巴痢疾|感染性腹泻|痢疾|布鲁菌|布病|钩端螺旋体|血吸虫|疟疾|登革热'
                        )
                     OR REGEXP_LIKE(
                            NVL(NULLIF(TRIM(y.infect_name_or), ''), NULLIF(TRIM(y.diag_desc), '')),
                            '梅毒|淋病|尖锐湿疣|生殖器疱疹|狂犬病|破伤风|人感染高致病性禽流感|禽流感'
                        )
                   THEN 1
                   ELSE 0
               END AS infect_flag
          FROM (
                SELECT q.*,

                       icd_local.std_diag_code AS admin_code_by_name,
                       icd_local.std_diag_name AS admin_name_by_name,

                       NVL(
                           NULLIF(TRIM(icd_code.std_diag_code), ''),
                           NVL(
                               NULLIF(TRIM(icd_local.std_diag_code), ''),
                               NULLIF(TRIM(icd_std.std_diag_code), '')
                           )
                       ) AS infect_code_or,

                       NVL(
                           NULLIF(TRIM(icd_code.std_diag_name), ''),
                           NVL(
                               NULLIF(TRIM(icd_local.std_diag_name), ''),
                               NULLIF(TRIM(icd_std.std_diag_name), '')
                           )
                       ) AS infect_name_or

                  FROM (
                        SELECT a.visit_date,
                               a.visit_no,
                               TO_CHAR(a.patient_id) AS patient_id,
                               a.ordinal,
                               TO_CHAR(a.diag_desc_code) AS diag_desc_code,
                               TO_CHAR(a.diag_desc) AS diag_desc,
                               TO_CHAR(a.doctor) AS doctor,
                               TO_CHAR(a.doctor_no) AS doctor_no,
                               a.illness_date,
                               TO_CHAR(b.clinic_no) AS clinic_no,
                               TO_CHAR(c.id_no) AS doctor_id_no,
                               TO_CHAR(c.name) AS doctor_name,
                               TO_CHAR(pmi.name) AS patient_name,
                               TO_CHAR(pmi.sex) AS sex,
                               TO_CHAR(pmi.id_no) AS patient_id_no
                          FROM HIS.outp_mr a
                          JOIN HIS.clinic_master b
                            ON a.visit_date = b.visit_date
                           AND a.visit_no = b.visit_no
                           AND a.patient_id = b.patient_id
                          LEFT JOIN HIS.staff_dict c
                            ON TO_CHAR(a.doctor_no) = TO_CHAR(c.emp_no)
                          JOIN HIS.pat_master_index pmi
                            ON a.patient_id = pmi.patient_id
                         WHERE a.visit_date >= DATE '2021-01-01'
                           AND a.visit_date <  DATE '2025-01-01'
                       ) q

                  LEFT JOIN (
                        SELECT TO_CHAR(cd.院标名称) AS match_value,
                               MAX(TO_CHAR(cd.国标编码)) AS std_diag_code,
                               MAX(TO_CHAR(cd.国标名称)) AS std_diag_name
                          FROM CDA.cda_dictionary cd
                         WHERE TO_CHAR(cd.字典名称) = 'ICD-10诊断编码'
                           AND TO_CHAR(cd.系统标识) = 'HIS'
                           AND cd.院标名称 IS NOT NULL
                         GROUP BY TO_CHAR(cd.院标名称)
                       ) icd_local
                    ON icd_local.match_value = q.diag_desc

                  LEFT JOIN (
                        SELECT TO_CHAR(cd.院标编码) AS match_value,
                               MAX(TO_CHAR(cd.国标编码)) AS std_diag_code,
                               MAX(TO_CHAR(cd.国标名称)) AS std_diag_name
                          FROM CDA.cda_dictionary cd
                         WHERE TO_CHAR(cd.字典名称) = 'ICD-10诊断编码'
                           AND TO_CHAR(cd.系统标识) = 'HIS'
                           AND cd.院标编码 IS NOT NULL
                         GROUP BY TO_CHAR(cd.院标编码)
                       ) icd_code
                    ON icd_code.match_value = q.diag_desc_code

                  LEFT JOIN (
                        SELECT TO_CHAR(cd.国标名称) AS match_value,
                               MAX(TO_CHAR(cd.国标编码)) AS std_diag_code,
                               MAX(TO_CHAR(cd.国标名称)) AS std_diag_name
                          FROM CDA.cda_dictionary cd
                         WHERE TO_CHAR(cd.字典名称) = 'ICD-10诊断编码'
                           AND TO_CHAR(cd.系统标识) = 'HIS'
                           AND cd.国标名称 IS NOT NULL
                         GROUP BY TO_CHAR(cd.国标名称)
                       ) icd_std
                    ON icd_std.match_value = q.diag_desc
               ) y
         WHERE NVL(
                   NULLIF(TRIM(y.admin_code_by_name), ''),
                   NULLIF(TRIM(y.diag_desc_code), '')
               ) IS NOT NULL
            OR NVL(
                   NULLIF(TRIM(y.admin_name_by_name), ''),
                   NULLIF(TRIM(y.diag_desc), '')
               ) IS NOT NULL
       ) z
