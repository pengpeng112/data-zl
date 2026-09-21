
  CREATE OR REPLACE FORCE VIEW "ODS"."V_EMR_CONSUMABLES" ("ID", "ORG_CODE", "ORG_NAME", "ADMISSION_ID", "DEPT_CODE", "DEPT_NAME", "WARD_NAME", "EORD_NUM", "SICKBED_NUM", "NAME", "SEX_CODE", "SEX_NAME", "AGE", "AGE_MONTH", "DISEASE_CODE", "RECORD_SIGN_DATE", "IMPLANT_CODE", "MATERIAL_NAME", "MATERIAL_CODE", "PRODU_CODE", "MATERIAL_PRODUCTION", "MATERIAL_SUPPLY", "MATERIAL_WORK", "AMOUNT", "USE_WAY", "NURSE_NAME", "RECORD_DATE", "DISTRICT_CODE", "EXCHANGE_TYPE", "SYSTEM_TIME") AS 
  SELECT
    -- ID：机构代码+患者ID+就诊次号+费用序号拼接
    '49557032X' || b.PATIENT_ID || b.VISIT_ID || b.ITEM_NO AS ID,
    -- 机构信息
    '49557032X'                AS ORG_CODE,
    '济南市第二人民医院'         AS ORG_NAME,
    -- 住院标识
    b.PATIENT_ID || b.VISIT_ID  AS ADMISSION_ID,
    -- 科室
    d.DRG_DEPT_CODE             AS DEPT_CODE,
    d.DEPT_NAME                 AS DEPT_NAME,
    -- 病区/病房/床号
    b.WARDCODE                  AS WARD_NAME,
    NULL                        AS EORD_NUM,
    TO_CHAR(b.BED_NO)           AS SICKBED_NUM,
    -- 患者信息（来自 PAT_MASTER_INDEX）
    p.NAME                      AS NAME,
    p.SEX                       AS SEX_CODE,
    CASE p.SEX
        WHEN '男' THEN '1'
        WHEN '女' THEN '2'
        ELSE '0'
    END                         AS SEX_NAME,
    -- 年龄（来自 PAT_VISIT 入院日期 - 出生年月）
    CASE
        WHEN p.DATE_OF_BIRTH IS NOT NULL AND v.ADMISSION_DATE_TIME IS NOT NULL
        THEN TRUNC(MONTHS_BETWEEN(v.ADMISSION_DATE_TIME, p.DATE_OF_BIRTH) / 12)
    END                         AS AGE,
    NULL                        AS AGE_MONTH,
    -- 诊断编码（来自 PAT_VISIT 入院诊断）
    v.RYZD                      AS DISEASE_CODE,
    -- 记录日期
    b.BILLING_DATE_TIME         AS RECORD_SIGN_DATE,
    -- 植入性耗材标志（根据名称判断）
    CASE
        WHEN b.ITEM_NAME LIKE '%植入%'
          OR b.ITEM_NAME LIKE '%支架%'
          OR b.ITEM_NAME LIKE '%钢板%'
          OR b.ITEM_NAME LIKE '%螺钉%'
          OR b.ITEM_NAME LIKE '%人工关节%'
          OR b.ITEM_NAME LIKE '%骨水泥%'
          OR b.ITEM_NAME LIKE '%人工骨%'
          OR b.ITEM_NAME LIKE '%人工晶体%'
          OR b.ITEM_NAME LIKE '%人工耳蜗%'
        THEN '1'
        ELSE '0'
    END                         AS IMPLANT_CODE,
    -- 耗材信息
    b.ITEM_NAME                 AS MATERIAL_NAME,
    b.ITEM_CODE                 AS MATERIAL_CODE,
    -- 产品编码（HIS 无 BARCODE 数据，暂置空）
    NULL                        AS PRODU_CODE,
    -- 生产厂家/供应商（费用明细表无此数据，暂置空）
    NULL                        AS MATERIAL_PRODUCTION,
    NULL                        AS MATERIAL_SUPPLY,
    b.UNITS                     AS MATERIAL_WORK,
    b.AMOUNT                    AS AMOUNT,
    NULL                        AS USE_WAY,
    -- 护士签名（无 STAFF_USER 表，暂置空）
    NULL                        AS NURSE_NAME,
    -- 签名日期
    b.BILLING_DATE_TIME         AS RECORD_DATE,
    -- 行政区划
    '370104'                    AS DISTRICT_CODE,
    -- 交换类型
    'INSERT'                    AS EXCHANGE_TYPE,
    -- 数据上传时间
    SYSTIMESTAMP                AS SYSTEM_TIME
FROM HIS.INP_BILL_DETAIL b
LEFT JOIN HIS.PAT_MASTER_INDEX p ON b.PATIENT_ID = p.PATIENT_ID
LEFT JOIN HIS.PAT_VISIT v       ON b.PATIENT_ID = v.PATIENT_ID AND b.VISIT_ID = v.VISIT_ID
LEFT JOIN HIS.DEPT_DICT d       ON b.DEPT_CODE = d.DEPT_CODE
WHERE b.CLASS_ON_MR = '材料'
  AND b.BILLING_DATE_TIME >= DATE '2021-01-01'
  AND b.BILLING_DATE_TIME < DATE '2025-01-01'
