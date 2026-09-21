
  CREATE OR REPLACE FORCE VIEW "ODS"."V_EMR_OUTPATIENT_RECIPE_ITEM" ("ID", "OR_ID", "ORG_CODE", "ORG_NAME", "SN", "ITEM_NUM", "ITEM_TYPE_CODE", "ITEM_TYPE_NAME", "DRUG_CLASS_CODE", "DRUG_CLASS_NAME", "DRUG_CODE", "DRUG_COMMON_NAME", "DRUG_NAME", "SPEC", "UNIT", "DRUG_DOSE", "ONCE_AMOUNT", "DOSAGE_UNIT", "JL_UNIT", "QUANTITY", "HERB_NUM", "UNIT_DOSE", "ORDER_DOSAGE", "ALL_AMOUNT", "DRUG_ROUTE_CODE", "DRUG_ROUTE_NAME", "DRUG_FREQUENCY_CODE", "DRUG_FREQUENCY_NAME", "STATUS_CODE", "STATUS_NAME", "CANCEL_REASON", "CANCEL_TIME", "DOCTOR_CODE", "DOCTOR_NAME", "DRUG_FORM_CODE", "DRUG_FORM_NAME", "GROUP_NO", "SKIN_TEST_RESULT", "IS_ESSENTIAL", "ESSENTIL_GRADE", "IS_ANTI", "ANTI_USE_GRADE_CODE", "ANTI_USE_GRADE_NAME", "IF_YF", "DISTRICT_CODE", "CREATED_AT", "EXCHANGE_TYPE", "SYSTEM_TIME", "DRUG_WAY_CD", "DRUG_WAY_NAME", "DURATION_TIME", "DRUG_AMOUNT", "TCM_DECOCTION_METHOD", "MEDICATION_METHOD", "DRUG_PRICE", "CH_DRUG_NOTES", "OUTPATIENT_NUM", "NAME", "SEX_CODE", "ID_NUM", "ODR_TYPE", "ORDER_ITEM_CODE", "ORDER_ITEM_NAME", "ORDER_CATEGORY_CODE", "ORDER_CATEGORY_NAME", "ORDER_NUM_NAME", "ORDER_STATUS", "DTCODE", "NHSA_STANDARD_CODE", "DOSAGE", "DOSAGE_UNIT_NAME", "DRUG_ALL_UNIT", "DRUG_ALL_NUM", "ADMINISTRATION_DAYS", "DRUG_ADMINISTRATION_ROUTE", "IS_EXTERNAL_PRES") AS 
  SELECT SUBSTR(
           TO_CHAR(a.presc_date, 'yyyymmddhh24miss')
           || '|' || CAST(a.presc_no AS VARCHAR2(50))
           || '|' || CAST(t.item_no AS VARCHAR2(50)),
           1,
           100
       ) AS ID, -- 内码：处方日期+处方号+处方项目序号

      /* SUBSTR(
           TO_CHAR(a.presc_date, 'yyyymmddhh24miss')
           || '|' || CAST(a.presc_no AS VARCHAR2(50)),
           1,
           100
       ) AS*/
       substr(
           '49557032X' || '|' ||
           to_char(a.presc_date, 'yyyymmddhh24miss') || '|' ||
           a.patient_id || '|' ||
           a.presc_no,
           1,
           100
       )   OR_ID, -- 门诊处方内码，必须与处方主表ID保持一致

       '49557032X' AS ORG_CODE, -- 医院编码

       '山东省第二人民医院' AS ORG_NAME, -- 医院名称

       t.item_no AS SN, -- 序号

       SUBSTR(CAST(t.item_no AS VARCHAR2(20)), 1, 20) AS ITEM_NUM, -- 处方项编号

       CASE
           /* 中药饮片必须优先判断 */
           WHEN dd.drug_indicator = 2
            AND (
                   REGEXP_LIKE(NVL(t.drug_name, dd.drug_name), '饮片')
                OR REGEXP_LIKE(NVL(dd.drug_form, '-'), '饮片')
                )
           THEN '4'

           /* 西药 */
           WHEN dd.drug_indicator = 1 THEN '2'

           /* 中草药，但不属于饮片 */
           WHEN dd.drug_indicator = 2 THEN '3'

           /* 中成药归入平台“中药” */
           WHEN dd.drug_indicator = 3 THEN '1'

           /* 辅料、试剂、其他暂归为非药品 */
           WHEN dd.drug_indicator IN (5, 6, 9) THEN '5'

           /* 药品字典关联不到时，使用处方类别兜底：保持原逻辑 */
           WHEN a.presc_type = '0' THEN '2'
           WHEN a.presc_type = '1' THEN '1'

           ELSE '5'
       END AS ITEM_TYPE_CODE, -- 处方项类别代码

       CASE
           WHEN dd.drug_indicator = 2
            AND (
                   REGEXP_LIKE(NVL(t.drug_name, dd.drug_name), '饮片')
                OR REGEXP_LIKE(NVL(dd.drug_form, '-'), '饮片')
                )
           THEN '中药饮片'

           WHEN dd.drug_indicator = 1 THEN '西药'
           WHEN dd.drug_indicator = 2 THEN '中草药'
           WHEN dd.drug_indicator = 3 THEN '中药'
           WHEN dd.drug_indicator IN (5, 6, 9) THEN '非药品'

           WHEN a.presc_type = '0' THEN '西药'
           WHEN a.presc_type = '1' THEN '中药'

           ELSE '非药品'
       END AS ITEM_TYPE_NAME, -- 处方项类别名称

       NVL(pharm_map.value_domain_code, '99') AS DRUG_CLASS_CODE, -- 药品分类代码

       NVL(pharm_map.value_domain_name, '其它化学药物') AS DRUG_CLASS_NAME, -- 药品分类名称

       NVL(std.ypid_code, t.drug_code) AS DRUG_CODE, -- 药物编码

       NVL(std.product_name, t.drug_name) AS DRUG_COMMON_NAME, -- 药物通用名

       SUBSTR(t.drug_name, 1, 100) AS DRUG_NAME, -- 药物名称

       SUBSTR(
           NVL(t.package_spec, t.drug_spec),
           1,
           100
       ) AS SPEC, -- 规格

       SUBSTR(
           NVL(t.package_units, dd.units),
           1,
           6
       ) AS UNIT, -- 单位

       CAST(NULL AS NUMBER(12, 2)) AS DRUG_DOSE, -- 药物日剂量，暂无可靠来源

       CAST(
           ROUND(t.dosage_each, 2)
           AS NUMBER(12, 2)
       ) AS ONCE_AMOUNT, -- 药物使用单次量

       CASE
           WHEN LOWER(TRIM(t.dosage_units)) IN ('g', '克') THEN '1'
           WHEN LOWER(TRIM(t.dosage_units)) IN ('mg', '毫克') THEN '2'
           WHEN LOWER(TRIM(t.dosage_units)) IN ('μg', 'ug', 'mcg', '微克') THEN '3'
           WHEN LOWER(TRIM(t.dosage_units)) IN ('l', '升') THEN '5'
           WHEN LOWER(TRIM(t.dosage_units)) IN ('ml', '毫升') THEN '6'
           WHEN UPPER(TRIM(t.dosage_units)) IN ('IU', '万IU', 'AXAIU') THEN '7'
           WHEN UPPER(TRIM(t.dosage_units)) IN ('U', '万U')
             OR TRIM(t.dosage_units) IN ('单位', '万u', 'u') THEN '8'
           WHEN REGEXP_LIKE(LOWER(TRIM(t.dosage_units)), '^g(口服|po|qd|bid|tid|qid).*') THEN '1'
           WHEN REGEXP_LIKE(LOWER(TRIM(t.dosage_units)), '^mg(口服|po|qd|bid|tid|qid).*') THEN '2'
           WHEN REGEXP_LIKE(LOWER(TRIM(t.dosage_units)), '^ml(口服|po|qd|bid|tid|qid).*') THEN '6'
           ELSE CAST('-' AS VARCHAR2(6))
       END AS DOSAGE_UNIT, -- 剂量单位代码

       CASE
           WHEN LOWER(TRIM(t.dosage_units)) IN ('g', '克') THEN 'g'
           WHEN LOWER(TRIM(t.dosage_units)) IN ('mg', '毫克') THEN 'mg'
           WHEN LOWER(TRIM(t.dosage_units)) IN ('μg', 'ug', 'mcg', '微克') THEN 'μg'
           WHEN LOWER(TRIM(t.dosage_units)) IN ('l', '升') THEN 'L'
           WHEN LOWER(TRIM(t.dosage_units)) IN ('ml', '毫升') THEN 'ml'
           WHEN UPPER(TRIM(t.dosage_units)) IN ('IU', '万IU', 'AXAIU') THEN 'IU'
           WHEN UPPER(TRIM(t.dosage_units)) IN ('U', '万U')
             OR TRIM(t.dosage_units) IN ('单位', '万u', 'u') THEN 'U'
           WHEN REGEXP_LIKE(LOWER(TRIM(t.dosage_units)), '^g(口服|po|qd|bid|tid|qid).*') THEN 'g'
           WHEN REGEXP_LIKE(LOWER(TRIM(t.dosage_units)), '^mg(口服|po|qd|bid|tid|qid).*') THEN 'mg'
           WHEN REGEXP_LIKE(LOWER(TRIM(t.dosage_units)), '^ml(口服|po|qd|bid|tid|qid).*') THEN 'ml'
           ELSE CAST(NULL AS VARCHAR2(8))
       END AS JL_UNIT, -- 剂量单位名称

       CAST(
           ROUND(
               CASE
                   WHEN NVL(t.flag, a.flag) = 2 THEN -ABS(t.quantity)
                   ELSE t.quantity
               END,
               2
           ) AS NUMBER(8, 2)
       ) AS QUANTITY, -- 数量，退药时为负数

       CASE
           WHEN REGEXP_LIKE(t.drug_name, '饮片')
             OR dd.drug_indicator = 2
           THEN NVL(a.repetition, 1)
           ELSE CAST(NULL AS NUMBER)
       END AS HERB_NUM, -- 草药付数

       CAST(
           ROUND(dd.dose_per_unit, 2)
           AS NUMBER(9, 2)
       ) AS UNIT_DOSE, -- 单位剂量

       CAST(
           ROUND(t.dosage_each, 2)
           AS NUMBER(8, 2)
       ) AS ORDER_DOSAGE, -- 医嘱用量

       CAST(
           ROUND(
               CASE
                   WHEN NVL(t.flag, a.flag) = 2 THEN -ABS(t.quantity)
                   ELSE t.quantity
               END,
               2
           ) AS NUMBER(12, 2)
       ) AS ALL_AMOUNT, -- 药物使用总量

       SUBSTR(route_map.standard_code, 1, 4) AS DRUG_ROUTE_CODE, -- 用药方式代码

       SUBSTR(NVL(route_map.standard_name, t.administration), 1, 50) AS DRUG_ROUTE_NAME, -- 用药方式

       CASE
           /* 标准频次代码本身 */
           WHEN LOWER(TRIM(t.frequency)) = 'bid' THEN 'bid'
           WHEN LOWER(TRIM(t.frequency)) = 'bidac' THEN 'bidac'
           WHEN LOWER(TRIM(t.frequency)) = 'tidac' THEN 'tidac'
           WHEN LOWER(TRIM(t.frequency)) = 'biw' THEN 'biw'
           WHEN LOWER(TRIM(t.frequency)) = 'hs' THEN 'hs'
           WHEN LOWER(TRIM(t.frequency)) = 'prn' THEN 'prn'
           WHEN LOWER(TRIM(t.frequency)) = 'q12h' THEN 'q12h'
           WHEN LOWER(TRIM(t.frequency)) = 'q12h1' THEN 'q12h1'
           WHEN LOWER(TRIM(t.frequency)) = 'q12h2' THEN 'q12h2'
           WHEN LOWER(TRIM(t.frequency)) = 'q1h' THEN 'q1h'
           WHEN LOWER(TRIM(t.frequency)) = 'q2h' THEN 'q2h'
           WHEN LOWER(TRIM(t.frequency)) = 'q3h' THEN 'q3h'
           WHEN LOWER(TRIM(t.frequency)) = 'q4h' THEN 'q4h'
           WHEN LOWER(TRIM(t.frequency)) = 'q6h' THEN 'q6h'
           WHEN LOWER(TRIM(t.frequency)) = 'q6h1' THEN 'q6h1'
           WHEN LOWER(TRIM(t.frequency)) = 'q6h2' THEN 'q6h2'
           WHEN LOWER(TRIM(t.frequency)) = 'q8h' THEN 'q8h'
           WHEN LOWER(TRIM(t.frequency)) = 'q8h1' THEN 'q8h1'
           WHEN LOWER(TRIM(t.frequency)) = 'q8h2' THEN 'q8h2'
           WHEN LOWER(TRIM(t.frequency)) = 'qd' THEN 'qd'
           WHEN LOWER(TRIM(t.frequency)) = 'qid' THEN 'qid'
           WHEN LOWER(TRIM(t.frequency)) = 'qm' THEN 'qm'
           WHEN LOWER(TRIM(t.frequency)) = 'qn' THEN 'qn'
           WHEN LOWER(TRIM(t.frequency)) = 'qod' THEN 'qod'
           WHEN LOWER(TRIM(t.frequency)) = 'qw' THEN 'qw'
           WHEN LOWER(TRIM(t.frequency)) = 'st' THEN 'st'
           WHEN LOWER(TRIM(t.frequency)) = 'tid' THEN 'tid'

           /* 院内中文/特殊写法转换 */
           WHEN TRIM(t.frequency) IN ('睡前') THEN 'hs'
           WHEN TRIM(t.frequency) IN ('必要时') THEN 'prn'
           WHEN TRIM(t.frequency) IN ('立即') THEN 'st'

           WHEN TRIM(t.frequency) IN ('三餐前') THEN 'tidac'
           WHEN TRIM(t.frequency) IN ('三餐后') THEN 'tid'

           WHEN TRIM(t.frequency) IN ('早餐前', '午餐前', '晚餐前', '空腹', '下午', '术前', '术晨')
           THEN 'qd'

           WHEN TRIM(t.frequency) IN (
                    '1/早餐前15''',
                    '1/早餐前30''',
                    '1/午餐前15''',
                    '1/午餐前30''',
                    '1/晚餐前15''',
                    '1/晚餐前30''',
                    '术前30’'
                )
           THEN 'qd'

           WHEN TRIM(t.frequency) IN ('1/半小时') THEN 'q1h'
           WHEN TRIM(t.frequency) IN ('1/小时') THEN 'q1h'
           WHEN TRIM(t.frequency) IN ('1/2小时') THEN 'q2h'
           WHEN TRIM(t.frequency) IN ('1/3小时') THEN 'q3h'
           WHEN TRIM(t.frequency) IN ('1/4小时') THEN 'q4h'

           WHEN TRIM(t.frequency) IN ('1/2日') THEN 'q12h'
           WHEN TRIM(t.frequency) IN ('1/3日') THEN 'q8h'
           WHEN TRIM(t.frequency) IN ('5/日', '7/日', '10/周', '5/周', '3/5日', '4/5日', 'q72h', 'q2w', 'q4w', '6M', 'tiw', 'wf', 'zwf', 'zf')
           THEN 'oth'

           WHEN TRIM(t.frequency) IN ('三餐前三餐后睡前') THEN 'oth'

           ELSE 'oth'
       END AS DRUG_FREQUENCY_CODE, -- 执行频率代码

       CASE
           WHEN LOWER(TRIM(t.frequency)) = 'bid' THEN '每天二次'
           WHEN LOWER(TRIM(t.frequency)) = 'bidac' THEN '每天二次，餐前服用'
           WHEN LOWER(TRIM(t.frequency)) = 'tidac' THEN '每天三次，餐前服用'
           WHEN LOWER(TRIM(t.frequency)) = 'biw' THEN '每周二次'
           WHEN LOWER(TRIM(t.frequency)) = 'hs' THEN '睡前一次'
           WHEN LOWER(TRIM(t.frequency)) = 'prn' THEN '必要时一次'
           WHEN LOWER(TRIM(t.frequency)) = 'q12h' THEN '每十二小时一次'
           WHEN LOWER(TRIM(t.frequency)) = 'q12h1' THEN '每十二小时一次（8）'
           WHEN LOWER(TRIM(t.frequency)) = 'q12h2' THEN '每十二小时一次（20）'
           WHEN LOWER(TRIM(t.frequency)) = 'q1h' THEN '每一小时一次'
           WHEN LOWER(TRIM(t.frequency)) = 'q2h' THEN '每二小时一次'
           WHEN LOWER(TRIM(t.frequency)) = 'q3h' THEN '每三小时一次'
           WHEN LOWER(TRIM(t.frequency)) = 'q4h' THEN '每四小时一次'
           WHEN LOWER(TRIM(t.frequency)) = 'q6h' THEN '每六小时一次'
           WHEN LOWER(TRIM(t.frequency)) = 'q6h1' THEN '每六小时一次（8,20）'
           WHEN LOWER(TRIM(t.frequency)) = 'q6h2' THEN '每六小时二次（14,2）'
           WHEN LOWER(TRIM(t.frequency)) = 'q8h' THEN '每八小时一次'
           WHEN LOWER(TRIM(t.frequency)) = 'q8h1' THEN '每八小时一次（8,24）'
           WHEN LOWER(TRIM(t.frequency)) = 'q8h2' THEN '每八小时一次（16）'
           WHEN LOWER(TRIM(t.frequency)) = 'qd' THEN '每天一次'
           WHEN LOWER(TRIM(t.frequency)) = 'qid' THEN '每天四次'
           WHEN LOWER(TRIM(t.frequency)) = 'qm' THEN '每天早上一次'
           WHEN LOWER(TRIM(t.frequency)) = 'qn' THEN '每天晚上一次'
           WHEN LOWER(TRIM(t.frequency)) = 'qod' THEN '隔日一次'
           WHEN LOWER(TRIM(t.frequency)) = 'qw' THEN '每周一次'
           WHEN LOWER(TRIM(t.frequency)) = 'st' THEN '立即'
           WHEN LOWER(TRIM(t.frequency)) = 'tid' THEN '每天三次'

           WHEN TRIM(t.frequency) IN ('睡前') THEN '睡前一次'
           WHEN TRIM(t.frequency) IN ('必要时') THEN '必要时一次'
           WHEN TRIM(t.frequency) IN ('立即') THEN '立即'

           WHEN TRIM(t.frequency) IN ('三餐前') THEN '每天三次，餐前服用'
           WHEN TRIM(t.frequency) IN ('三餐后') THEN '每天三次'

           WHEN TRIM(t.frequency) IN ('早餐前', '午餐前', '晚餐前', '空腹', '下午', '术前', '术晨')
           THEN '每天一次'

           WHEN TRIM(t.frequency) IN (
                    '1/早餐前15''',
                    '1/早餐前30''',
                    '1/午餐前15''',
                    '1/午餐前30''',
                    '1/晚餐前15''',
                    '1/晚餐前30''',
                    '术前30’'
                )
           THEN '每天一次'

           WHEN TRIM(t.frequency) IN ('1/半小时', '1/小时') THEN '每一小时一次'
           WHEN TRIM(t.frequency) IN ('1/2小时') THEN '每二小时一次'
           WHEN TRIM(t.frequency) IN ('1/3小时') THEN '每三小时一次'
           WHEN TRIM(t.frequency) IN ('1/4小时') THEN '每四小时一次'

           WHEN TRIM(t.frequency) IN ('1/2日') THEN '每十二小时一次'
           WHEN TRIM(t.frequency) IN ('1/3日') THEN '每八小时一次'

           ELSE '其它'
       END AS DRUG_FREQUENCY_NAME, -- 执行频率

       CASE
           WHEN NVL(t.flag, a.flag) = 2 THEN '2'
           ELSE '1'
       END AS STATUS_CODE, -- 状态代码

       CASE
           WHEN NVL(t.flag, a.flag) = 2 THEN '退药'
           ELSE '正常'
       END AS STATUS_NAME, -- 状态名称

       CASE
           WHEN NVL(t.flag, a.flag) = 2 THEN '退药'
           ELSE CAST(NULL AS VARCHAR2(100))
       END AS CANCEL_REASON, -- 取消原因

       CAST(NULL AS DATE) AS CANCEL_TIME, -- 取消时间，暂无可靠字段

       CAST(NULL AS VARCHAR2(32)) AS DOCTOR_CODE, -- 取消医生代码

       CAST(NULL AS VARCHAR2(50)) AS DOCTOR_NAME, -- 取消医生姓名

       NVL(
           form_map.value_domain_code,
           CASE
               WHEN REGEXP_LIKE(NVL(t.drug_name, dd.drug_name), '肠溶片') THEN '04'
               WHEN REGEXP_LIKE(NVL(t.drug_name, dd.drug_name), '缓释片|控释片') THEN '05'
               WHEN REGEXP_LIKE(NVL(t.drug_name, dd.drug_name), '咀嚼片') THEN '03'
               WHEN REGEXP_LIKE(NVL(t.drug_name, dd.drug_name), '分散片') THEN '12'
               WHEN REGEXP_LIKE(NVL(t.drug_name, dd.drug_name), '片') THEN '01'
               WHEN REGEXP_LIKE(NVL(t.drug_name, dd.drug_name), '粉针|冻干') THEN '15'
               WHEN REGEXP_LIKE(NVL(t.drug_name, dd.drug_name), '注射液|胰岛素') THEN '16'
               WHEN REGEXP_LIKE(NVL(t.drug_name, dd.drug_name), '缓释胶囊|控释胶囊') THEN '22'
               WHEN REGEXP_LIKE(NVL(t.drug_name, dd.drug_name), '胶囊') THEN '19'
               WHEN REGEXP_LIKE(NVL(t.drug_name, dd.drug_name), '滴眼液|眼药水') THEN '43'
               WHEN REGEXP_LIKE(NVL(t.drug_name, dd.drug_name), '滴鼻') THEN '44'
               WHEN REGEXP_LIKE(NVL(t.drug_name, dd.drug_name), '滴耳') THEN '45'
               WHEN REGEXP_LIKE(NVL(t.drug_name, dd.drug_name), '眼膏') THEN '52'
               WHEN REGEXP_LIKE(NVL(t.drug_name, dd.drug_name), '颗粒') THEN '54'
               WHEN REGEXP_LIKE(NVL(t.drug_name, dd.drug_name), '口服液') THEN '31'
               WHEN REGEXP_LIKE(NVL(t.drug_name, dd.drug_name), '糖浆') THEN '30'
               WHEN REGEXP_LIKE(NVL(t.drug_name, dd.drug_name), '喷雾') THEN '58'
               WHEN REGEXP_LIKE(NVL(t.drug_name, dd.drug_name), '吸入') THEN '60'
               WHEN REGEXP_LIKE(NVL(t.drug_name, dd.drug_name), '贴') THEN '65'
               WHEN REGEXP_LIKE(NVL(t.drug_name, dd.drug_name), '栓') THEN '63'
               WHEN REGEXP_LIKE(NVL(t.drug_name, dd.drug_name), '丸') THEN '14'
               ELSE '99'
           END
       ) AS DRUG_FORM_CODE, -- 药物剂型代码

       NVL(
           form_map.value_domain_name,
           CASE
               WHEN REGEXP_LIKE(NVL(t.drug_name, dd.drug_name), '肠溶片') THEN '肠溶片'
               WHEN REGEXP_LIKE(NVL(t.drug_name, dd.drug_name), '缓释片|控释片') THEN '缓释片'
               WHEN REGEXP_LIKE(NVL(t.drug_name, dd.drug_name), '咀嚼片') THEN '咀嚼片'
               WHEN REGEXP_LIKE(NVL(t.drug_name, dd.drug_name), '分散片') THEN '分散片'
               WHEN REGEXP_LIKE(NVL(t.drug_name, dd.drug_name), '片') THEN '片剂'
               WHEN REGEXP_LIKE(NVL(t.drug_name, dd.drug_name), '粉针|冻干') THEN '粉针'
               WHEN REGEXP_LIKE(NVL(t.drug_name, dd.drug_name), '注射液|胰岛素') THEN '注射液'
               WHEN REGEXP_LIKE(NVL(t.drug_name, dd.drug_name), '缓释胶囊|控释胶囊') THEN '缓释胶囊'
               WHEN REGEXP_LIKE(NVL(t.drug_name, dd.drug_name), '胶囊') THEN '胶囊'
               WHEN REGEXP_LIKE(NVL(t.drug_name, dd.drug_name), '滴眼液|眼药水') THEN '滴眼剂'
               WHEN REGEXP_LIKE(NVL(t.drug_name, dd.drug_name), '滴鼻') THEN '滴鼻剂'
               WHEN REGEXP_LIKE(NVL(t.drug_name, dd.drug_name), '滴耳') THEN '滴耳剂'
               WHEN REGEXP_LIKE(NVL(t.drug_name, dd.drug_name), '眼膏') THEN '眼膏剂'
               WHEN REGEXP_LIKE(NVL(t.drug_name, dd.drug_name), '颗粒') THEN '颗粒剂'
               WHEN REGEXP_LIKE(NVL(t.drug_name, dd.drug_name), '口服液') THEN '口服溶液剂'
               WHEN REGEXP_LIKE(NVL(t.drug_name, dd.drug_name), '糖浆') THEN '糖浆剂'
               WHEN REGEXP_LIKE(NVL(t.drug_name, dd.drug_name), '喷雾') THEN '喷雾剂'
               WHEN REGEXP_LIKE(NVL(t.drug_name, dd.drug_name), '吸入') THEN '吸入剂'
               WHEN REGEXP_LIKE(NVL(t.drug_name, dd.drug_name), '贴') THEN '贴剂'
               WHEN REGEXP_LIKE(NVL(t.drug_name, dd.drug_name), '栓') THEN '栓剂'
               WHEN REGEXP_LIKE(NVL(t.drug_name, dd.drug_name), '丸') THEN '丸剂'
               ELSE '其他剂型'
           END
       ) AS DRUG_FORM_NAME, -- 药物剂型名称

       t.order_no AS GROUP_NO, -- 处方药品组号

       CAST(NULL AS CHAR(1)) AS SKIN_TEST_RESULT, -- 皮试结果

       CASE
           WHEN jy_dict.dict_name = '基药' THEN '1'
           ELSE '0'
       END AS IS_ESSENTIAL, -- 是否基药

       CASE
           WHEN jy_dict.dict_name = '基药' THEN '1'
           ELSE '4'
       END AS ESSENTIL_GRADE, -- 基药级别

       CASE
           WHEN NVL(m.antibiotic_flag, 0) = 1
             OR TRIM(m.anti_flag) IN ('1', '2', '3')
           THEN '1'
           ELSE '0'
       END AS IS_ANTI, -- 是否抗菌药物

       CASE
           WHEN TRIM(m.anti_flag) = '0' THEN '-'
           WHEN kss_dict.dict_name = '非限制' THEN '1'
           WHEN kss_dict.dict_name = '限制' THEN '2'
           WHEN kss_dict.dict_name = '特殊' THEN '3'
           ELSE '-'
       END AS ANTI_USE_GRADE_CODE, -- 抗菌药物使用级别代码

       CASE
           WHEN TRIM(m.anti_flag) = '0' THEN '-'
           WHEN kss_dict.dict_name = '非限制' THEN '非限制使用'
           WHEN kss_dict.dict_name = '限制' THEN '限制使用'
           WHEN kss_dict.dict_name = '特殊' THEN '特殊使用'
           ELSE '-'
       END AS ANTI_USE_GRADE_NAME, -- 抗菌药物使用级别名称

       '-' AS IF_YF, -- 用药目的代码

       '370104' AS DISTRICT_CODE, -- 所属行政区划

       CAST(NULL AS DATE) AS CREATED_AT, -- 创建时间，由平台自动生成

       'INSERT' AS EXCHANGE_TYPE, -- 交换类型

       CAST(SYSTIMESTAMP AS TIMESTAMP) AS SYSTEM_TIME, -- 数据上传时间戳

       CASE
           WHEN REGEXP_LIKE(TRIM(t.administration), '输液泵|静脉泵入|微量泵入|泵入') THEN 700
           WHEN REGEXP_LIKE(TRIM(t.administration), '皮下注射') THEN 401
           WHEN REGEXP_LIKE(TRIM(t.administration), '皮内注射|皮试') THEN 402
           WHEN REGEXP_LIKE(TRIM(t.administration), '肌肉注射') THEN 403
           WHEN REGEXP_LIKE(TRIM(t.administration), '静脉滴注|静脉输液|续静滴|静脉注射|静脉推注|静脉壶内给药|静脉化疗|脐静脉给药|静脉封管|封管') THEN 404
           WHEN REGEXP_LIKE(TRIM(t.administration), '鞘内注射') THEN 405
           WHEN REGEXP_LIKE(TRIM(t.administration), '椎管内') THEN 601
           WHEN REGEXP_LIKE(TRIM(t.administration), '关节腔注射|关节腔冲洗|关节腔') THEN 602
           WHEN REGEXP_LIKE(TRIM(t.administration), '胸腔注射|胸腔冲洗|胸膜腔') THEN 603
           WHEN REGEXP_LIKE(TRIM(t.administration), '腹腔注射|腹腔冲洗|腹腔灌注|腹腔用药|腹膜透析') THEN 604
           WHEN REGEXP_LIKE(TRIM(t.administration), '阴道内置药|阴道冲洗|阴道用药|阴道') THEN 605
           WHEN REGEXP_LIKE(TRIM(t.administration), '气管滴药|气管内') THEN 606
           WHEN REGEXP_LIKE(TRIM(t.administration), '滴左眼|滴右眼|滴双眼|滴眼|涂左眼|涂右眼|涂双眼|涂眼膏') THEN 607
           WHEN REGEXP_LIKE(TRIM(t.administration), '滴鼻|喷鼻|鼻腔冲洗') THEN 608
           WHEN REGEXP_LIKE(TRIM(t.administration), '喷喉|口腔喷雾') THEN 609
           WHEN REGEXP_LIKE(TRIM(t.administration), '舌下含化|舌下|口含|含化|含漱') THEN 610
           WHEN REGEXP_LIKE(TRIM(t.administration), '敷伤口|湿敷') THEN 611
           WHEN REGEXP_LIKE(TRIM(t.administration), '擦皮肤|外用|涂擦|涂剂') THEN 612
           WHEN REGEXP_LIKE(TRIM(t.administration), '口服|冲服|煎服|嚼服|泡服|胃管内注入|鼻空肠管注入|空肠造瘘管内注入|空肠造瘘注入') THEN 1
           WHEN REGEXP_LIKE(TRIM(t.administration), '直肠|肛门注入|肛塞|肛用|保留灌肠|清洁灌肠|灌肠') THEN 2
           WHEN REGEXP_LIKE(TRIM(t.administration), '雾化吸入|雾化吸入Ⅰ号|压力雾化|吸入') THEN 5
           WHEN REGEXP_LIKE(TRIM(t.administration), '局部麻醉|局醉|浸润麻醉|局部注射|局部用药') THEN 6
           WHEN REGEXP_LIKE(TRIM(t.administration), '会阴冲洗|膀胱灌注|膀胱冲洗|宫腔注射|宫颈上药|宫颈注射|直肠粘膜注射|瘤体内注射|介入治疗|肿瘤灌注|穴位封闭|穴位注射|鼻穴位注射|耳穴位注射|耳后局部注射|前房注射|玻璃体腔内注射|眼内注射|球后注射|球旁注射|半球后注射|结膜下注射|咽后壁注射|口腔粘膜注射|粘膜下注射|管道冲洗|创腔冲洗|器械冲洗|盆腔冲洗|腔内给药|引流管内注入|鼓窦内给药') THEN 699
           WHEN TRIM(t.administration) IN (
                'FREQ_DETAIL',
                '血液滤过',
                '血液透析滤过',
                '血液透析',
                '血管造影',
                '葡萄糖试验',
                '葡萄糖耐量',
                '市门统',
                '（久煎）',
                '（冲服）',
                '（后下）',
                '||07--07',
                '||04--04'
           ) THEN 9
           ELSE 9
       END AS DRUG_WAY_CD, -- 药物使用途径代码

       CASE
           WHEN REGEXP_LIKE(TRIM(t.administration), '输液泵|静脉泵入|微量泵入|泵入') THEN '输液泵泵入'
           WHEN REGEXP_LIKE(TRIM(t.administration), '皮下注射') THEN '皮下注射'
           WHEN REGEXP_LIKE(TRIM(t.administration), '皮内注射|皮试') THEN '皮内注射'
           WHEN REGEXP_LIKE(TRIM(t.administration), '肌肉注射') THEN '肌肉注射'
           WHEN REGEXP_LIKE(TRIM(t.administration), '静脉滴注|静脉输液|续静滴|静脉注射|静脉推注|静脉壶内给药|静脉化疗|脐静脉给药|静脉封管|封管') THEN '静脉注射或静脉滴注'
           WHEN REGEXP_LIKE(TRIM(t.administration), '鞘内注射') THEN '鞘内注射'
           WHEN REGEXP_LIKE(TRIM(t.administration), '椎管内') THEN '椎管内用药'
           WHEN REGEXP_LIKE(TRIM(t.administration), '关节腔注射|关节腔冲洗|关节腔') THEN '关节腔内用药'
           WHEN REGEXP_LIKE(TRIM(t.administration), '胸腔注射|胸腔冲洗|胸膜腔') THEN '胸膜腔用药'
           WHEN REGEXP_LIKE(TRIM(t.administration), '腹腔注射|腹腔冲洗|腹腔灌注|腹腔用药|腹膜透析') THEN '腹腔用药'
           WHEN REGEXP_LIKE(TRIM(t.administration), '阴道内置药|阴道冲洗|阴道用药|阴道') THEN '阴道用药'
           WHEN REGEXP_LIKE(TRIM(t.administration), '气管滴药|气管内') THEN '气管内用药'
           WHEN REGEXP_LIKE(TRIM(t.administration), '滴左眼|滴右眼|滴双眼|滴眼|涂左眼|涂右眼|涂双眼|涂眼膏') THEN '滴眼'
           WHEN REGEXP_LIKE(TRIM(t.administration), '滴鼻|喷鼻|鼻腔冲洗') THEN '滴鼻'
           WHEN REGEXP_LIKE(TRIM(t.administration), '喷喉|口腔喷雾') THEN '喷喉'
           WHEN REGEXP_LIKE(TRIM(t.administration), '舌下含化|舌下|口含|含化|含漱') THEN '含化'
           WHEN REGEXP_LIKE(TRIM(t.administration), '敷伤口|湿敷') THEN '敷伤口'
           WHEN REGEXP_LIKE(TRIM(t.administration), '擦皮肤|外用|涂擦|涂剂') THEN '擦皮肤'
           WHEN REGEXP_LIKE(TRIM(t.administration), '口服|冲服|煎服|嚼服|泡服|胃管内注入|鼻空肠管注入|空肠造瘘管内注入|空肠造瘘注入') THEN '口服'
           WHEN REGEXP_LIKE(TRIM(t.administration), '直肠|肛门注入|肛塞|肛用|保留灌肠|清洁灌肠|灌肠') THEN '直肠用药'
           WHEN REGEXP_LIKE(TRIM(t.administration), '雾化吸入|雾化吸入Ⅰ号|压力雾化|吸入') THEN '吸入用药'
           WHEN REGEXP_LIKE(TRIM(t.administration), '局部麻醉|局醉|浸润麻醉|局部注射|局部用药') THEN '局部用药'
           WHEN REGEXP_LIKE(TRIM(t.administration), '会阴冲洗|膀胱灌注|膀胱冲洗|宫腔注射|宫颈上药|宫颈注射|直肠粘膜注射|瘤体内注射|介入治疗|肿瘤灌注|穴位封闭|穴位注射|鼻穴位注射|耳穴位注射|耳后局部注射|前房注射|玻璃体腔内注射|眼内注射|球后注射|球旁注射|半球后注射|结膜下注射|咽后壁注射|口腔粘膜注射|粘膜下注射|管道冲洗|创腔冲洗|器械冲洗|盆腔冲洗|腔内给药|引流管内注入|鼓窦内给药') THEN '其他局部用药途径'
           WHEN TRIM(t.administration) IN (
                'FREQ_DETAIL',
                '血液滤过',
                '血液透析滤过',
                '血液透析',
                '血管造影',
                '葡萄糖试验',
                '葡萄糖耐量',
                '市门统',
                '（久煎）',
                '（冲服）',
                '（后下）',
                '||07--07',
                '||04--04'
           ) THEN '其他用药途径'
           ELSE '其他用药途径'
       END AS DRUG_WAY_NAME, -- 药物使用途径名称

       CAST(
           GREATEST(
               NVL(
                   t.abidance,
                   CASE
                       WHEN a.presc_type = '1' THEN NVL(a.repetition, 1)
                       ELSE 1
                   END
               ),
               1
           ) AS NUMBER(5)
       ) AS DURATION_TIME, -- 持续用药天数

       CAST(
           ROUND(
               CASE
                   WHEN NVL(t.flag, a.flag) = 2 THEN -ABS(t.costs)
                   ELSE t.costs
               END,
               2
           ) AS NUMBER(9, 2)
       ) AS DRUG_AMOUNT, -- 药物金额

       CASE
           WHEN dd.drug_indicator = 2 THEN '9'
           ELSE NULL
       END AS TCM_DECOCTION_METHOD, -- 中药饮片煎煮法

       CASE
           WHEN a.presc_type = '1' THEN SUBSTR(a.memo, 1, 100)
           ELSE CAST(NULL AS VARCHAR2(100))
       END AS MEDICATION_METHOD, -- 中药用药方法

       CAST(
           ROUND(
               NVL(
                   (
                       SELECT MAX(pl.retail_price)
                              KEEP (
                                  DENSE_RANK LAST
                                  ORDER BY pl.start_date
                              )
                         FROM HIS.drug_price_list pl
                        WHERE pl.drug_code = t.drug_code
                          AND pl.drug_spec = NVL(t.package_spec, t.drug_spec)
                          AND pl.firm_id = t.firm_id
                          AND pl.start_date <= a.presc_date
                          AND (
                              pl.stop_date IS NULL
                              OR pl.stop_date >= a.presc_date
                          )
                   ),
                   CASE
                       WHEN NVL(t.quantity, 0) <> 0 THEN ABS(t.costs / t.quantity)
                       ELSE NULL
                   END
               ),
               2
           ) AS NUMBER(9, 2)
       ) AS DRUG_PRICE, -- 药物单价

       CASE
           WHEN a.presc_type = '1' THEN SUBSTR(a.memo, 1, 2000)
           ELSE CAST(NULL AS VARCHAR2(2000))
       END AS CH_DRUG_NOTES, -- 中药饮片处方描述

       SUBSTR(a.clinic_no, 1, 18) AS OUTPATIENT_NUM, -- 本次门诊标识号

       SUBSTR(a.name, 1, 50) AS NAME, -- 患者姓名

       CASE TRIM(pmi.sex)
           WHEN '男' THEN '1'
           WHEN '女' THEN '2'
           WHEN '未知' THEN '0'
           WHEN '不详' THEN '9'
           WHEN '未说明' THEN '9'
           ELSE '9'
       END AS SEX_CODE, -- 患者性别代码

       NVL(SUBSTR(pmi.id_no, 1, 18), '000000000000000000') AS ID_NUM, -- 患者身份证件号码，保留原逻辑

       CASE
           WHEN LOWER(TRIM(t.frequency)) IN ('st', 'prn')
             OR TRIM(t.frequency) IN ('立即', '必要时', '术前', '术晨', '术前30’', '皮试')
           THEN '2'
           WHEN t.frequency IS NULL THEN '9'
           ELSE '2'
       END AS ODR_TYPE, -- 处方类别编码：门诊处方默认临时，保留原逻辑

       SUBSTR(
           a.clinic_no
           || '|' || NVL(CAST(t.order_no AS VARCHAR2(50)), '0')
           || '|' || NVL(CAST(t.order_sub_no AS VARCHAR2(50)), '0'),
           1,
           100
       ) AS ORDER_ITEM_CODE, -- 院内医嘱编号

       SUBSTR(t.drug_name, 1, 100) AS ORDER_ITEM_NAME, -- 院内医嘱项名称

       '1' AS ORDER_CATEGORY_CODE, -- 医嘱项目大类别编码：药品类

       '药品类医嘱' AS ORDER_CATEGORY_NAME, -- 医嘱项目大类别名称

       CASE
           WHEN LOWER(TRIM(t.dosage_units)) IN ('g', '克') THEN 'g'
           WHEN LOWER(TRIM(t.dosage_units)) IN ('mg', '毫克') THEN 'mg'
           WHEN LOWER(TRIM(t.dosage_units)) IN ('μg', 'ug', 'mcg', '微克') THEN 'μg'
           WHEN LOWER(TRIM(t.dosage_units)) IN ('l', '升') THEN 'L'
           WHEN LOWER(TRIM(t.dosage_units)) IN ('ml', '毫升') THEN 'ml'
           WHEN UPPER(TRIM(t.dosage_units)) IN ('IU', '万IU', 'AXAIU') THEN 'IU'
           WHEN UPPER(TRIM(t.dosage_units)) IN ('U', '万U')
             OR TRIM(t.dosage_units) IN ('单位', '万u', 'u') THEN 'U'
           ELSE SUBSTR(t.dosage_units, 1, 100)
       END AS ORDER_NUM_NAME, -- 医嘱用量单位

       CASE
           WHEN NVL(t.flag, a.flag) = 2 THEN '2'
           ELSE '1'
       END AS ORDER_STATUS, -- 医嘱有效标识，1有效、2无效

       CAST(NULL AS VARCHAR2(100)) AS DTCODE, -- 药品追溯码，暂无可靠来源

       SUBSTR(insur_map.ylxmbm, 1, 100) AS NHSA_STANDARD_CODE, -- 医保贯标码

       SUBSTR(
           CAST(dd.dose_per_unit AS VARCHAR2(100)),
           1,
           100
       ) AS DOSAGE, -- 最小剂量

       dd.dose_units AS DOSAGE_UNIT_NAME, -- 最小剂量单位名称

       SUBSTR(
           NVL(t.package_units, dd.units),
           1,
           100
       ) AS DRUG_ALL_UNIT, -- 药品包装单位

       (
           SELECT MAX(pl.amount_per_package)
                  KEEP (
                      DENSE_RANK LAST
                      ORDER BY pl.start_date
                  )
             FROM HIS.drug_price_list pl
            WHERE pl.drug_code = t.drug_code
              AND pl.drug_spec = NVL(t.package_spec, t.drug_spec)
              AND pl.firm_id = t.firm_id
              AND pl.start_date <= a.presc_date
              AND (
                  pl.stop_date IS NULL
                  OR pl.stop_date >= a.presc_date
              )
       ) AS DRUG_ALL_NUM, -- 药品包装量，保留原取值逻辑

       CAST(
           GREATEST(
               NVL(
                   t.abidance,
                   CASE
                       WHEN a.presc_type = '1' THEN NVL(a.repetition, 1)
                       ELSE 1
                   END
               ),
               1
           ) AS NUMBER
       ) AS ADMINISTRATION_DAYS, -- 执行天数

       CASE
           WHEN REGEXP_LIKE(TRIM(t.administration), '输液泵|静脉泵入|微量泵入|泵入') THEN '输液泵泵入'
           WHEN REGEXP_LIKE(TRIM(t.administration), '皮下注射') THEN '皮下注射'
           WHEN REGEXP_LIKE(TRIM(t.administration), '皮内注射|皮试') THEN '皮内注射'
           WHEN REGEXP_LIKE(TRIM(t.administration), '肌肉注射') THEN '肌肉注射'
           WHEN REGEXP_LIKE(TRIM(t.administration), '静脉滴注|静脉输液|续静滴|静脉注射|静脉推注|静脉壶内给药|静脉化疗|脐静脉给药|静脉封管|封管') THEN '静脉注射或静脉滴注'
           WHEN REGEXP_LIKE(TRIM(t.administration), '鞘内注射') THEN '鞘内注射'
           WHEN REGEXP_LIKE(TRIM(t.administration), '椎管内') THEN '椎管内用药'
           WHEN REGEXP_LIKE(TRIM(t.administration), '关节腔注射|关节腔冲洗|关节腔') THEN '关节腔内用药'
           WHEN REGEXP_LIKE(TRIM(t.administration), '胸腔注射|胸腔冲洗|胸膜腔') THEN '胸膜腔用药'
           WHEN REGEXP_LIKE(TRIM(t.administration), '腹腔注射|腹腔冲洗|腹腔灌注|腹腔用药|腹膜透析') THEN '腹腔用药'
           WHEN REGEXP_LIKE(TRIM(t.administration), '阴道内置药|阴道冲洗|阴道用药|阴道') THEN '阴道用药'
           WHEN REGEXP_LIKE(TRIM(t.administration), '气管滴药|气管内') THEN '气管内用药'
           WHEN REGEXP_LIKE(TRIM(t.administration), '滴左眼|滴右眼|滴双眼|滴眼|涂左眼|涂右眼|涂双眼|涂眼膏') THEN '滴眼'
           WHEN REGEXP_LIKE(TRIM(t.administration), '滴左耳|滴右耳|滴双耳|滴耳') THEN '滴耳'
           WHEN REGEXP_LIKE(TRIM(t.administration), '滴鼻|喷鼻|鼻腔冲洗') THEN '滴鼻'
           WHEN REGEXP_LIKE(TRIM(t.administration), '喷喉|口腔喷雾') THEN '喷喉'
           WHEN REGEXP_LIKE(TRIM(t.administration), '舌下含化|舌下|口含|含化|含漱') THEN '含化'
           WHEN REGEXP_LIKE(TRIM(t.administration), '敷伤口|湿敷') THEN '敷伤口'
           WHEN REGEXP_LIKE(TRIM(t.administration), '擦皮肤|外用|涂擦|涂剂') THEN '擦皮肤'
           WHEN REGEXP_LIKE(TRIM(t.administration), '口服|冲服|煎服|嚼服|泡服|胃管内注入|鼻空肠管注入|空肠造瘘管内注入|空肠造瘘注入') THEN '口服'
           WHEN REGEXP_LIKE(TRIM(t.administration), '直肠|肛门注入|肛塞|肛用|保留灌肠|清洁灌肠|灌肠') THEN '直肠用药'
           WHEN REGEXP_LIKE(TRIM(t.administration), '雾化吸入|雾化吸入Ⅰ号|压力雾化|吸入') THEN '吸入用药'
           WHEN REGEXP_LIKE(TRIM(t.administration), '局部麻醉|局醉|浸润麻醉|局部注射|局部用药') THEN '局部用药'
           ELSE '其他用药途径'
       END AS DRUG_ADMINISTRATION_ROUTE, -- 给药途径

       '0' AS IS_EXTERNAL_PRES -- 是否外配处方，院内处方填0

  FROM HIS.drug_presc_master a

  JOIN HIS.drug_presc_detail t
    ON t.presc_date = a.presc_date
   AND t.presc_no   = a.presc_no

  JOIN HIS.clinic_master d
    ON d.clinic_no  = a.clinic_no
   AND d.patient_id = a.patient_id

  JOIN HIS.pat_master_index pmi
    ON pmi.patient_id = a.patient_id

  LEFT JOIN HIS.med_dict_baseinfo m
    ON m.drug_id = t.drug_code

  LEFT JOIN (
        SELECT x.drug_code,
               x.drug_spec,
               x.drug_name,
               x.units,
               x.drug_form,
               x.dose_per_unit,
               x.dose_units,
               x.drug_indicator
          FROM (
                SELECT dd.drug_code,
                       dd.drug_spec,
                       dd.drug_name,
                       dd.units,
                       dd.drug_form,
                       dd.dose_per_unit,
                       dd.dose_units,
                       dd.drug_indicator,
                       ROW_NUMBER() OVER (
                           PARTITION BY dd.drug_code,
                                        dd.drug_spec
                           ORDER BY dd.rowid
                       ) AS rn
                  FROM HIS.drug_dict dd
               ) x
         WHERE x.rn = 1
       ) dd
    ON dd.drug_code = t.drug_code
   AND dd.drug_spec = t.drug_spec

  LEFT JOIN (
        SELECT g.F008_HIS_YAO_PIN_BIAN_MA AS his_drug_code,
               MAX(g.F004_YPID11_3) AS ypid_code,
               MAX(g.F007_CHAN_PIN_MING_CHENG) AS product_name
          FROM DRUG_STANDARD_DICT g
         GROUP BY g.F008_HIS_YAO_PIN_BIAN_MA
       ) std
    ON std.his_drug_code = t.drug_code

  LEFT JOIN (
        SELECT zd.院标编码 AS local_code,
               MAX(zd.国标编码) AS standard_code,
               MAX(zd.国标名称) AS standard_name
          FROM CDA.cda_dictionary zd
         WHERE zd.字典名称 IN (
                   '用药途径代码',
                   '给药途径代码',
                   '药物使用途径代码'
               )
         GROUP BY zd.院标编码
       ) route_map
    ON route_map.local_code = t.administration

  LEFT JOIN (
        SELECT v.hospital_code,
               MAX(v.value_domain_code) AS value_domain_code,
               MAX(v.value_domain_name) AS value_domain_name
          FROM CDA_VALUE_DOMAIN_MAP v
         WHERE v.category_code = 'CV08.50.002'
         GROUP BY v.hospital_code
       ) form_map
    ON form_map.hospital_code = m.dose_model_code

  LEFT JOIN (
        SELECT p.dict_code,
               MAX(v.value_domain_code) AS value_domain_code,
               MAX(v.value_domain_name) AS value_domain_name
          FROM PORTAL_USER.portal_sys_dict p
          JOIN CDA_VALUE_DOMAIN_MAP v
            ON v.hospital_code = p.dict_code
           AND v.category_code = 'CC99.00203'
         WHERE p.type_code = 'pharmacology_type'
         GROUP BY p.dict_code
       ) pharm_map
    ON pharm_map.dict_code = m.phy_class

  LEFT JOIN (
        SELECT dict_code,
               MAX(dict_name) AS dict_name
          FROM PORTAL_USER.portal_sys_dict
         WHERE type_code = 'jy'
         GROUP BY dict_code
       ) jy_dict
    ON jy_dict.dict_code = CAST(m.basicdrug AS VARCHAR2(100))

  LEFT JOIN (
        SELECT dict_code,
               MAX(dict_name) AS dict_name
          FROM PORTAL_USER.portal_sys_dict
         WHERE type_code = 'kss'
         GROUP BY dict_code
       ) kss_dict
    ON kss_dict.dict_code = CAST(m.anti_flag AS VARCHAR2(100))

  LEFT JOIN (
        SELECT item_code,
               MAX(ylxmbm) AS ylxmbm
          FROM HIS.insur_vsh_center_item_new
         GROUP BY item_code
       ) insur_map
    ON insur_map.item_code = t.drug_code

 WHERE a.presc_source = '0'
   AND (a.flag = 1 OR a.flag IS NULL)
   AND a.costs > 0
   AND d.visit_date >= DATE '2021-01-01'
   AND d.visit_date <  DATE '2025-01-01'
