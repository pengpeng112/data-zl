
  CREATE OR REPLACE FORCE VIEW "ODS"."V_EMR_OUTPATIENT_DIAG_BAK" ("ID", "OUTPATIENT_NUM", "TCM_WM_MARK_CODE", "TCM_WM_MARK_NAME", "IF_MAIN", "ADMIN_ILLNESS_CODE", "ADMIN_ILLNESS_NAME", "INFECTIOUS_SIGNS", "CONTAGIOUS_REPORT_SIGN", "ORG_CODE", "ORG_NAME", "CHINA_MED_SYNDROME_CODE", "CHINA_MED_SYNDROME_NAME", "DOCTOR_ID_NUM", "DOCTOR_NAME", "DIAG_DATE", "DISTRICT_CODE", "SYSTEM_TIME", "EXCHANGE_TYPE", "NAME", "SEX_CODE", "ID_NUM", "DIAGNOSIS_NO", "LOCAL_DIAGNOSIS_CODE", "LOCAL_DIAGNOSIS_NAME", "NHS_DX_CODE", "NHS_DX_NAME") AS 
  SELECT SUBSTR(
           '49557032X'
           || '|' || z.clinic_no
           || '|NEW|'
           || NVL(TO_CHAR(z.item_no), '0')
           || '|' || NVL(z.diag_code, '-'),
           1,
           100
       ) AS ID, -- 内码，主键

       SUBSTR(
           NVL(z.clinic_no, z.patient_id || TO_CHAR(z.visit_date, 'yyyymmdd')),
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
           NVL(z.icd_or_code, z.diag_code),
           1,
           12
       ) AS ADMIN_ILLNESS_CODE, -- 诊断疾病代码

       SUBSTR(
           NVL(z.icd_or_name, z.diag_desc),
           1,
           100
       ) AS ADMIN_ILLNESS_NAME, -- 诊断疾病名称

       z.infect_flag AS INFECTIOUS_SIGNS, -- 传染标识：按ICD-10编码及诊断名称推断

       z.infect_flag AS CONTAGIOUS_REPORT_SIGN, -- 传染上报标识：当前按诊断推断，严格应取传染病报卡

       '49557032X' AS ORG_CODE, -- 医院组织机构编码

       '山东省第二人民医院' AS ORG_NAME, -- 医院名称

       CASE
           WHEN z.diag_type IS NULL THEN '-'
           ELSE '-'
       END AS CHINA_MED_SYNDROME_CODE, -- 中医证候代码；中医真实证候来源待确认

       CASE
           WHEN z.diag_type IS NULL THEN '-'
           ELSE '-'
       END AS CHINA_MED_SYNDROME_NAME, -- 中医证候名称；中医真实证候来源待确认

       SUBSTR(NVL(z.doctor_id_no, '000000000000000000'), 1, 18) AS DOCTOR_ID_NUM, -- 诊断医师身份证号

       SUBSTR(NVL(z.doctor_name, z.doctor), 1, 50) AS DOCTOR_NAME, -- 诊断医师姓名

       CAST(z.visit_date AS DATE) AS DIAG_DATE, -- 诊断日期

       '370104' AS DISTRICT_CODE, -- 所属行政区划

       CAST(SYSTIMESTAMP AS TIMESTAMP) AS SYSTEM_TIME, -- 数据上传时间戳

       'ADDHIS' AS EXCHANGE_TYPE, -- 交换类型；历史补传用ADDHIS，正常增量可改INSERT

       SUBSTR(z.patient_name, 1, 50) AS NAME, -- 患者姓名

       CASE TRIM(z.sex)
           WHEN '男' THEN '1'
           WHEN '女' THEN '2'
           WHEN '未知' THEN '0'
           WHEN '不详' THEN '9'
           WHEN '未说明' THEN '9'
           ELSE '9'
       END AS SEX_CODE, -- 患者性别代码

       SUBSTR(NVL(z.patient_id_no, '000000000000000000'), 1, 18) AS ID_NUM, -- 患者身份证件号码

       SUBSTR(NVL(TO_CHAR(z.item_no), '1'), 1, 20) AS DIAGNOSIS_NO, -- 诊断序号

       SUBSTR(z.diag_code, 1, 50) AS LOCAL_DIAGNOSIS_CODE, -- 院内诊断编码

       SUBSTR(z.diag_desc, 1, 200) AS LOCAL_DIAGNOSIS_NAME, -- 院内诊断名称

       SUBSTR(z.insur_diag_code, 1, 50) AS NHS_DX_CODE, -- 医保报销诊断编码

       SUBSTR(z.insur_diag_desc, 1, 200) AS NHS_DX_NAME -- 医保报销诊断名称

  FROM (
        SELECT y.*,
               CASE
                   WHEN REGEXP_LIKE(
                            UPPER(NVL(y.icd_or_code, y.diag_code)),
                            '^(A00|A01|A02|A03|A04|A05|A06|A09|A15|A16|A17|A18|A19|A20|A22|A27|A30|A33|A35|A36|A37|A38|A39|A50|A51|A52|A53|A54|A56|A64|A80|A82|A83|A90|A91|A92|A95|A98|B01|B05|B06|B15|B16|B17|B18|B19|B20|B21|B22|B23|B24|B26|B50|B51|B52|B53|B54|U07)'
                        )
                     OR REGEXP_LIKE(
                            NVL(y.icd_or_name, y.diag_desc),
                            '霍乱|鼠疫|炭疽|艾滋|HIV|病毒性肝炎|甲肝|乙肝|丙肝|戊肝|肺结核|结核|麻疹|风疹|水痘|流行性腮腺炎'
                        )
                     OR REGEXP_LIKE(
                            NVL(y.icd_or_name, y.diag_desc),
                            '流行性感冒|流感|新型冠状|新冠|COVID|手足口|猩红热|百日咳|白喉|脊髓灰质炎|流脑|乙脑'
                        )
                     OR REGEXP_LIKE(
                            NVL(y.icd_or_name, y.diag_desc),
                            '伤寒|副伤寒|细菌性痢疾|阿米巴痢疾|感染性腹泻|痢疾|布鲁菌|布病|钩端螺旋体|血吸虫|疟疾|登革热'
                        )
                     OR REGEXP_LIKE(
                            NVL(y.icd_or_name, y.diag_desc),
                            '梅毒|淋病|尖锐湿疣|生殖器疱疹|狂犬病|破伤风|人感染高致病性禽流感|禽流感'
                        )
                   THEN 1
                   ELSE 0
               END AS infect_flag
          FROM (
                SELECT q.*,

                       NULLIF(
                           GREATEST(
                               NVL(icd_code.std_diag_code,  UNISTR('\0001')),
                               NVL(icd_local.std_diag_code, UNISTR('\0001')),
                               NVL(icd_std.std_diag_code,   UNISTR('\0001'))
                           ),
                           UNISTR('\0001')
                       ) AS icd_or_code,

                       NULLIF(
                           GREATEST(
                               NVL(icd_code.std_diag_name,  UNISTR('\0001')),
                               NVL(icd_local.std_diag_name, UNISTR('\0001')),
                               NVL(icd_std.std_diag_name,   UNISTR('\0001'))
                           ),
                           UNISTR('\0001')
                       ) AS icd_or_name

                  FROM (
                        SELECT a.visit_date,
                               a.visit_no,
                               a.patient_id,
                               a.item_no,
                               a.diag_code,
                               a.diag_desc,
                               a.diag_type,
                               a.doctor,
                               a.insur_diag_code,
                               a.insur_diag_desc,
                               b.clinic_no,
                               c.id_no AS doctor_id_no,
                               c.name AS doctor_name,
                               pmi.name AS patient_name,
                               pmi.sex,
                               pmi.id_no AS patient_id_no
                          FROM HIS.outp_mr_diag_desc a
                          JOIN HIS.clinic_master b
                            ON a.visit_date = b.visit_date
                           AND a.visit_no = b.visit_no
                           AND a.patient_id = b.patient_id
                          LEFT JOIN HIS.staff_dict c
                            ON a.doctor = c.emp_no
                          JOIN HIS.pat_master_index pmi
                            ON a.patient_id = pmi.patient_id
                         WHERE a.visit_date >= DATE '2021-01-01'
                           AND a.visit_date <  DATE '2025-01-01'
                       ) q

                  LEFT JOIN (
                        SELECT cd.院标编码 AS match_value,
                               MAX(cd.国标编码) AS std_diag_code,
                               MAX(cd.国标名称) AS std_diag_name
                          FROM CDA.cda_dictionary cd
                         WHERE cd.字典名称 = 'ICD-10诊断编码'
                           AND cd.系统标识 = 'HIS'
                           AND cd.院标编码 IS NOT NULL
                         GROUP BY cd.院标编码
                       ) icd_code
                    ON icd_code.match_value = q.diag_code

                  LEFT JOIN (
                        SELECT cd.院标名称 AS match_value,
                               MAX(cd.国标编码) AS std_diag_code,
                               MAX(cd.国标名称) AS std_diag_name
                          FROM CDA.cda_dictionary cd
                         WHERE cd.字典名称 = 'ICD-10诊断编码'
                           AND cd.系统标识 = 'HIS'
                           AND cd.院标名称 IS NOT NULL
                         GROUP BY cd.院标名称
                       ) icd_local
                    ON icd_local.match_value = q.diag_desc

                  LEFT JOIN (
                        SELECT cd.国标名称 AS match_value,
                               MAX(cd.国标编码) AS std_diag_code,
                               MAX(cd.国标名称) AS std_diag_name
                          FROM CDA.cda_dictionary cd
                         WHERE cd.字典名称 = 'ICD-10诊断编码'
                           AND cd.系统标识 = 'HIS'
                           AND cd.国标名称 IS NOT NULL
                         GROUP BY cd.国标名称
                       ) icd_std
                    ON icd_std.match_value = q.diag_desc
               ) y
       ) z

UNION ALL

/* =========================================================
   OLD 分支：HIS.OUTP_MR
   原口径：
   ADMIN_ILLNESS_CODE / ADMIN_ILLNESS_NAME：
   只按 cd.院标名称 = a.diag_desc
   传染病判断：
   cd.院标编码 = a.diag_desc_code
   OR cd.院标名称 = a.diag_desc
   OR cd.国标名称 = a.diag_desc
   ========================================================= */
SELECT SUBSTR(
           '49557032X'
           || '|' || z.clinic_no
           || '|OLD|'
           || NVL(TO_CHAR(z.ordinal), '1')
           || '|' || NVL(z.diag_desc_code, '-'),
           1,
           100
       ) AS ID, -- 内码，主键

       SUBSTR(
           NVL(z.clinic_no, z.patient_id || TO_CHAR(z.visit_date, 'yyyymmdd')),
           1,
           32
       ) AS OUTPATIENT_NUM, -- 本次门诊标识符

       CASE
           WHEN z.diag_desc IS NOT NULL THEN '2'
           ELSE '1'
       END AS TCM_WM_MARK_CODE, -- 中医/西医诊断类型：1中医，2西医

       CASE
           WHEN z.diag_desc IS NOT NULL THEN '西医'
           ELSE '中医'
       END AS TCM_WM_MARK_NAME, -- 中医/西医诊断类型名称

       CASE
           WHEN NVL(z.ordinal, 1) = 1 THEN '1'
           ELSE '0'
       END AS IF_MAIN, -- 是否主要诊断标识

       NVL(z.admin_code_by_name, z.diag_desc_code) AS ADMIN_ILLNESS_CODE, -- 诊断疾病代码

       NVL(z.admin_name_by_name, z.diag_desc) AS ADMIN_ILLNESS_NAME, -- 诊断疾病名称

       z.infect_flag AS INFECTIOUS_SIGNS, -- 传染标识：按ICD-10编码及诊断名称推断

       z.infect_flag AS CONTAGIOUS_REPORT_SIGN, -- 传染上报标识：当前按诊断推断，严格应取传染病报卡

       '49557032X' AS ORG_CODE, -- 医院组织机构编码

       '山东省第二人民医院' AS ORG_NAME, -- 医院名称

       CASE
           WHEN z.diag_desc IS NOT NULL THEN '-'
           ELSE '-'
       END AS CHINA_MED_SYNDROME_CODE, -- 中医证候代码；中医真实证候来源待确认

       CASE
           WHEN z.diag_desc IS NOT NULL THEN '-'
           ELSE '-'
       END AS CHINA_MED_SYNDROME_NAME, -- 中医证候名称；中医真实证候来源待确认

       SUBSTR(NVL(z.doctor_id_no, '000000000000000000'), 1, 18) AS DOCTOR_ID_NUM, -- 诊断医师身份证号

       SUBSTR(NVL(z.doctor_name, z.doctor), 1, 50) AS DOCTOR_NAME, -- 诊断医师姓名

       CAST(z.illness_date AS DATE) AS DIAG_DATE, -- 诊断日期

       '370104' AS DISTRICT_CODE, -- 所属行政区划

       CAST(SYSTIMESTAMP AS TIMESTAMP) AS SYSTEM_TIME, -- 数据上传时间戳

       'ADDHIS' AS EXCHANGE_TYPE, -- 交换类型；历史补传用ADDHIS，正常增量可改INSERT

       SUBSTR(z.patient_name, 1, 50) AS NAME, -- 患者姓名

       CASE TRIM(z.sex)
           WHEN '男' THEN '1'
           WHEN '女' THEN '2'
           WHEN '未知' THEN '0'
           WHEN '不详' THEN '9'
           WHEN '未说明' THEN '9'
           ELSE '9'
       END AS SEX_CODE, -- 患者性别代码

       SUBSTR(NVL(z.patient_id_no, '000000000000000000'), 1, 18) AS ID_NUM, -- 患者身份证件号码

       SUBSTR(NVL(TO_CHAR(z.ordinal), '1'), 1, 20) AS DIAGNOSIS_NO, -- 诊断序号

       SUBSTR(z.diag_desc_code, 1, 50) AS LOCAL_DIAGNOSIS_CODE, -- 院内诊断编码

       SUBSTR(z.diag_desc, 1, 200) AS LOCAL_DIAGNOSIS_NAME, -- 院内诊断名称

       CAST(NULL AS VARCHAR2(50)) AS NHS_DX_CODE, -- 医保报销诊断编码，旧表暂无来源

       CAST(NULL AS VARCHAR2(200)) AS NHS_DX_NAME -- 医保报销诊断名称，旧表暂无来源

  FROM (
        SELECT y.*,
               CASE
                   WHEN REGEXP_LIKE(
                            UPPER(NVL(y.infect_code_or, y.diag_desc_code)),
                            '^(A00|A01|A02|A03|A04|A05|A06|A09|A15|A16|A17|A18|A19|A20|A22|A27|A30|A33|A35|A36|A37|A38|A39|A50|A51|A52|A53|A54|A56|A64|A80|A82|A83|A90|A91|A92|A95|A98|B01|B05|B06|B15|B16|B17|B18|B19|B20|B21|B22|B23|B24|B26|B50|B51|B52|B53|B54|U07)'
                        )
                     OR REGEXP_LIKE(
                            NVL(y.infect_name_or, y.diag_desc),
                            '霍乱|鼠疫|炭疽|艾滋|HIV|病毒性肝炎|甲肝|乙肝|丙肝|戊肝|肺结核|结核|麻疹|风疹|水痘|流行性腮腺炎'
                        )
                     OR REGEXP_LIKE(
                            NVL(y.infect_name_or, y.diag_desc),
                            '流行性感冒|流感|新型冠状|新冠|COVID|手足口|猩红热|百日咳|白喉|脊髓灰质炎|流脑|乙脑'
                        )
                     OR REGEXP_LIKE(
                            NVL(y.infect_name_or, y.diag_desc),
                            '伤寒|副伤寒|细菌性痢疾|阿米巴痢疾|感染性腹泻|痢疾|布鲁菌|布病|钩端螺旋体|血吸虫|疟疾|登革热'
                        )
                     OR REGEXP_LIKE(
                            NVL(y.infect_name_or, y.diag_desc),
                            '梅毒|淋病|尖锐湿疣|生殖器疱疹|狂犬病|破伤风|人感染高致病性禽流感|禽流感'
                        )
                   THEN 1
                   ELSE 0
               END AS infect_flag
          FROM (
                SELECT q.*,

                       icd_local.std_diag_code AS admin_code_by_name,
                       icd_local.std_diag_name AS admin_name_by_name,

                       NULLIF(
                           GREATEST(
                               NVL(icd_code.std_diag_code,  UNISTR('\0001')),
                               NVL(icd_local.std_diag_code, UNISTR('\0001')),
                               NVL(icd_std.std_diag_code,   UNISTR('\0001'))
                           ),
                           UNISTR('\0001')
                       ) AS infect_code_or,

                       NULLIF(
                           GREATEST(
                               NVL(icd_code.std_diag_name,  UNISTR('\0001')),
                               NVL(icd_local.std_diag_name, UNISTR('\0001')),
                               NVL(icd_std.std_diag_name,   UNISTR('\0001'))
                           ),
                           UNISTR('\0001')
                       ) AS infect_name_or

                  FROM (
                        SELECT a.visit_date,
                               a.visit_no,
                               a.patient_id,
                               a.ordinal,
                               a.diag_desc_code,
                               a.diag_desc,
                               a.doctor,
                               a.doctor_no,
                               a.illness_date,
                               b.clinic_no,
                               c.id_no AS doctor_id_no,
                               c.name AS doctor_name,
                               pmi.name AS patient_name,
                               pmi.sex,
                               pmi.id_no AS patient_id_no
                          FROM HIS.outp_mr a
                          JOIN HIS.clinic_master b
                            ON a.visit_date = b.visit_date
                           AND a.visit_no = b.visit_no
                           AND a.patient_id = b.patient_id
                          LEFT JOIN HIS.staff_dict c
                            ON a.doctor_no = c.emp_no
                          JOIN HIS.pat_master_index pmi
                            ON a.patient_id = pmi.patient_id
                         WHERE a.visit_date >  DATE '2021-01-01'
                           AND a.visit_date <  DATE '2025-01-01'
                       ) q

                  /* OLD 分支 ADMIN_ILLNESS_CODE / NAME 原逻辑：只按院标名称匹配 */
                  LEFT JOIN (
                        SELECT cd.院标名称 AS match_value,
                               MAX(cd.国标编码) AS std_diag_code,
                               MAX(cd.国标名称) AS std_diag_name
                          FROM CDA.cda_dictionary cd
                         WHERE cd.字典名称 = 'ICD-10诊断编码'
                           AND cd.系统标识 = 'HIS'
                           AND cd.院标名称 IS NOT NULL
                         GROUP BY cd.院标名称
                       ) icd_local
                    ON icd_local.match_value = q.diag_desc

                  /* OLD 分支传染病判断原逻辑：院标编码匹配 */
                  LEFT JOIN (
                        SELECT cd.院标编码 AS match_value,
                               MAX(cd.国标编码) AS std_diag_code,
                               MAX(cd.国标名称) AS std_diag_name
                          FROM CDA.cda_dictionary cd
                         WHERE cd.字典名称 = 'ICD-10诊断编码'
                           AND cd.系统标识 = 'HIS'
                           AND cd.院标编码 IS NOT NULL
                         GROUP BY cd.院标编码
                       ) icd_code
                    ON icd_code.match_value = q.diag_desc_code

                  /* OLD 分支传染病判断原逻辑：国标名称匹配 */
                  LEFT JOIN (
                        SELECT cd.国标名称 AS match_value,
                               MAX(cd.国标编码) AS std_diag_code,
                               MAX(cd.国标名称) AS std_diag_name
                          FROM CDA.cda_dictionary cd
                         WHERE cd.字典名称 = 'ICD-10诊断编码'
                           AND cd.系统标识 = 'HIS'
                           AND cd.国标名称 IS NOT NULL
                         GROUP BY cd.国标名称
                       ) icd_std
                    ON icd_std.match_value = q.diag_desc
               ) y
         WHERE NVL(y.admin_code_by_name, y.diag_desc_code) IS NOT NULL
       ) z
