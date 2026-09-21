SELECT
       SUBSTR(
           '49557032X' || '|' ||
           NVL(TO_CHAR(b.PATIENT_ID), '-') || '|' ||
           NVL(TO_CHAR(b.VISIT_ID), '-') || '|' ||
           NVL(TO_CHAR(b.ITEM_NO), '-'),
           1,
           100
       ) AS ID,-- 内码 是 主键

       '49557032X' AS ORG_CODE,-- 组织机构代码 是

       '山东省第二人民医院' AS ORG_NAME,-- 组织机构名称 是

       SUBSTR(
           TO_CHAR(b.PATIENT_ID) || '|' || TO_CHAR(b.VISIT_ID),
           1,
           50
       ) AS ADMISSION_ID,-- 住院唯一标示号 是

       SUBSTR(
           NVL(TO_CHAR(d.DRG_DEPT_CODE), NVL(TO_CHAR(b.DEPT_CODE), '-')),
           1,
           20
       ) AS DEPT_CODE,-- 科室代码，按原 DEPT_DICT 对照

       SUBSTR(
           NVL(TO_CHAR(d.DEPT_NAME), '-'),
           1,
           50
       ) AS DEPT_NAME,-- 科室名称 是，按原 DEPT_DICT 对照

       SUBSTR(TO_CHAR(b.WARDCODE), 1, 50) AS WARD_NAME,-- 病区名称；当前暂用WARDCODE

       CAST(NULL AS VARCHAR2(10)) AS EORD_NUM,-- 病房号

       SUBSTR(TO_CHAR(b.BED_NO), 1, 10) AS SICKBED_NUM,-- 病床号

       SUBSTR(NVL(NULLIF(TRIM(TO_CHAR(p.NAME)), ''), '-'), 1, 50) AS NAME,-- 患者姓名 是

       CASE TRIM(TO_CHAR(p.SEX))
           WHEN '男' THEN '1'
           WHEN '女' THEN '2'
           WHEN '未知' THEN '0'
           WHEN '不详' THEN '9'
           ELSE '9'
       END AS SEX_CODE,-- 性别代码 是

       SUBSTR(
           CASE TRIM(TO_CHAR(p.SEX))
               WHEN '男' THEN '男'
               WHEN '女' THEN '女'
               WHEN '未知' THEN '未知'
               WHEN '不详' THEN '未说明'
               ELSE '未说明'
           END,
           1,
           50
       ) AS SEX_NAME,-- 性别名称 是

       CAST(
           CASE
               WHEN p.DATE_OF_BIRTH IS NOT NULL
                AND v.ADMISSION_DATE_TIME IS NOT NULL
               THEN LEAST(
                        200,
                        GREATEST(
                            0,
                            TRUNC(MONTHS_BETWEEN(v.ADMISSION_DATE_TIME, p.DATE_OF_BIRTH) / 12)
                        )
                    )
               ELSE 0
           END AS NUMBER(3)
       ) AS AGE,-- 年龄（岁） 是

       SUBSTR(
           CASE
               WHEN p.DATE_OF_BIRTH IS NOT NULL
                AND v.ADMISSION_DATE_TIME IS NOT NULL
                AND TRUNC(MONTHS_BETWEEN(v.ADMISSION_DATE_TIME, p.DATE_OF_BIRTH) / 12) = 0
               THEN TO_CHAR(MOD(TRUNC(MONTHS_BETWEEN(v.ADMISSION_DATE_TIME, p.DATE_OF_BIRTH)), 12))
               ELSE NULL
           END,
           1,
           2
       ) AS AGE_MONTH,-- 年龄（月）

       SUBSTR(
           NVL(
               (
                   SELECT MAX(ds.DIAGNOSIS_CODE)
                     FROM DIAGNOSIS ds
                    WHERE ds.PATIENT_ID = b.PATIENT_ID
                      AND ds.VISIT_ID = b.VISIT_ID
                      AND ds.DIAGNOSIS_TYPE = 3
                      AND ds.DIAGNOSIS_NO = 1
               ),
               TO_CHAR(v.RYZD)
           ),
           1,
           12
       ) AS DISEASE_CODE,-- 疾病诊断编码

       CAST(NVL(b.BILLING_DATE_TIME, v.ADMISSION_DATE_TIME) AS DATE) AS RECORD_SIGN_DATE,-- 记录日期时间 是

     '1' IMPLANT_CODE,-- 植入性耗材标志

       SUBSTR(
           NVL(
               NULLIF(TRIM(TO_CHAR(b.ITEM_NAME)), ''),
               NVL(NULLIF(TRIM(TO_CHAR(ed.EXP_NAME)), ''), '-')
           ),
           1,
           200
       ) AS MATERIAL_NAME,-- 材料名称 是

       SUBSTR(
           '49557032X' || '#' || NVL(NULLIF(TRIM(TO_CHAR(b.ITEM_CODE)), ''), '-'),
           1,
           50
       ) AS MATERIAL_CODE,-- 材料代码 是，机构编码+#+医院内部材料编码

       SUBSTR(
           NULLIF(TRIM(TO_CHAR(ed.HRP_CODE)), ''),
           1,
           20
       ) AS PRODU_CODE,-- 产品编码；暂用EXP_DICT.HRP_CODE

       SUBSTR(
           NULLIF(TRIM(TO_CHAR(ed.MANUFACTURER)), ''),
           1,
           70
       ) AS MATERIAL_PRODUCTION,-- 产品生产厂家，取EXP_DICT.MANUFACTURER

       CAST(NULL AS VARCHAR2(70)) AS MATERIAL_SUPPLY,-- 产品供应商；EXP_DICT暂无供应商字段

       SUBSTR(
           NVL(
               NULLIF(TRIM(TO_CHAR(ed.UNITS)), ''),
               TO_CHAR(b.UNITS)
           ),
           1,
           6
       ) AS MATERIAL_WORK,-- 耗材单位

       CAST(NVL(b.AMOUNT, 0) AS NUMBER) AS AMOUNT,-- 数量 是

       CAST(NULL AS VARCHAR2(30)) AS USE_WAY,-- 使用途径

       '-' AS NURSE_NAME,-- 护士签名 是；当前无护士来源，暂用'-'兜底

       CAST(NVL(b.BILLING_DATE_TIME, v.ADMISSION_DATE_TIME) AS DATE) AS RECORD_DATE,-- 签名日期时间 是

       '370104' AS DISTRICT_CODE,-- 行政区划 是

       'INSERT' AS EXCHANGE_TYPE,-- 交换类型 是

       CAST(SYSTIMESTAMP AS TIMESTAMP) AS SYSTEM_TIME-- 数据上传时间 是

  FROM INP_BILL_DETAIL b

  INNER JOIN PAT_VISIT v
          ON b.PATIENT_ID = v.PATIENT_ID
         AND b.VISIT_ID = v.VISIT_ID

  LEFT JOIN PAT_MASTER_INDEX p
         ON b.PATIENT_ID = p.PATIENT_ID

  LEFT JOIN DEPT_DICT d
         ON b.DEPT_CODE = d.DEPT_CODE

  LEFT JOIN (
        SELECT TO_CHAR(e.EXP_CODE) AS EXP_CODE,
               MAX(TO_CHAR(e.EXP_NAME)) AS EXP_NAME,
               MAX(TO_CHAR(e.EXP_SPEC)) AS EXP_SPEC,
               MAX(TO_CHAR(e.UNITS)) AS UNITS,
               MAX(TO_CHAR(e.MANUFACTURER)) AS MANUFACTURER,
               MAX(TO_CHAR(e.YB_CODE)) AS YB_CODE,
               MAX(TO_CHAR(e.YB_NAME)) AS YB_NAME,
               MAX(TO_CHAR(e.HRP_CODE)) AS HRP_CODE,
               MAX(TO_CHAR(e.EXP_CLASS)) AS EXP_CLASS,
               MAX(TO_CHAR(e.DRG_CLASS)) AS DRG_CLASS
          FROM EXP_DICT e
         GROUP BY TO_CHAR(e.EXP_CODE)
       ) ed
         ON ed.EXP_CODE = TO_CHAR(b.ITEM_CODE)

 WHERE v.DISCHARGE_DATE_TIME >= DATE '2021-01-01'
   AND v.DISCHARGE_DATE_TIME <  DATE '2025-01-01'

   /* 高值耗材过滤：排除 MAZZY001、120400006-1 等非耗材收费项目 */
   AND ITEM_CLASS='I'

   AND EXISTS (
       SELECT 1
         FROM INP_BILL_DETAIL_HRP e
        WHERE e.PATIENT_ID = b.PATIENT_ID
          AND e.VISIT_ID = b.VISIT_ID
          AND e.ITEM_NO = b.ITEM_NO
   )
