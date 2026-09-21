
  CREATE OR REPLACE FORCE VIEW "ODS"."V_EMR_INSPECTION_ALLERGY_TEST" ("ID", "REPORT_ID", "APPLY_NUM", "ORG_CODE", "ORG_NAME", "ITEM_ID", "DRUG_ALLERGY_CODE", "DRUG_ALLERGY_NAME", "DRUG_ALLERGY_NOTE", "PIECE_DRUG", "BACSTA_CONCEN", "BACSTA_DIAMETER", "ANTIBIOTIC_CLASS", "ANTIBIOTIC_CODE", "ANTIBIOTIC_NAME", "EFFECTIVE_TIME", "STATUS", "CREATED_AT", "DISTRICT_CODE", "EXCHANGE_TYPE", "SYSTEM_TIME") AS 
  SELECT
    SUBSTRB(
        q.REPORT_ID || '_ALG_' || TO_CHAR(q.RN),
        1,
        100
    ) AS ID, -- 内码 VARCHAR2(100) 是 主键

    SUBSTRB(q.REPORT_ID, 1, 100) AS REPORT_ID, -- 检验报告单内码 VARCHAR2(100) 是，必须在父表存在

    SUBSTRB(NVL(q.APPLY_NUM, q.REPORT_ID), 1, 20) AS APPLY_NUM, -- 电子申请单编号 VARCHAR2(20) 是

    '49557032X' AS ORG_CODE, -- 医院组织机构代码 VARCHAR2(32) 是

    '山东省第二人民医院' AS ORG_NAME, -- 医院名称 VARCHAR2(70) 是

    SUBSTRB(TO_CHAR(q.RN), 1, 32) AS ITEM_ID, -- 项目序号 VARCHAR2(32) 是

    CASE
        WHEN REGEXP_LIKE(q.RESULT_NORM, '剂量依赖性敏感|SDD', 'i') THEN '10'
        WHEN REGEXP_LIKE(q.RESULT_NORM, '非野生型|NWT', 'i') THEN '8'
        WHEN REGEXP_LIKE(q.RESULT_NORM, '非敏感|NS', 'i') THEN '6'
        WHEN REGEXP_LIKE(q.RESULT_NORM, '污染', 'i') THEN '3'
        WHEN REGEXP_LIKE(q.RESULT_NORM, '未做|未测|未检|未进行|无药敏', 'i') THEN '4'
        WHEN REGEXP_LIKE(q.RESULT_NORM, '野生型|WT', 'i') THEN '7'
        WHEN REGEXP_LIKE(q.RESULT_NORM, '耐药', 'i')
          OR REGEXP_LIKE(q.RESULT_NORM, '(^|[^A-Z])R([^A-Z]|$)', 'i') THEN '1'
        WHEN REGEXP_LIKE(q.RESULT_NORM, '敏感', 'i')
          OR REGEXP_LIKE(q.RESULT_NORM, '(^|[^A-Z])S([^A-Z]|$)', 'i') THEN '2'
        WHEN REGEXP_LIKE(q.RESULT_NORM, '中介|中敏', 'i')
          OR REGEXP_LIKE(q.RESULT_NORM, '(^|[^A-Z])I([^A-Z]|$)', 'i') THEN '5'
        ELSE '9'
    END AS DRUG_ALLERGY_CODE, -- 药敏结果代码 VARCHAR2(32) CC99.00093 是

    CASE
        WHEN REGEXP_LIKE(q.RESULT_NORM, '剂量依赖性敏感|SDD', 'i') THEN '剂量依赖性敏感'
        WHEN REGEXP_LIKE(q.RESULT_NORM, '非野生型|NWT', 'i') THEN '非野生型'
        WHEN REGEXP_LIKE(q.RESULT_NORM, '非敏感|NS', 'i') THEN '非敏感'
        WHEN REGEXP_LIKE(q.RESULT_NORM, '污染', 'i') THEN '污染'
        WHEN REGEXP_LIKE(q.RESULT_NORM, '未做|未测|未检|未进行|无药敏', 'i') THEN '未做'
        WHEN REGEXP_LIKE(q.RESULT_NORM, '野生型|WT', 'i') THEN '野生型'
        WHEN REGEXP_LIKE(q.RESULT_NORM, '耐药', 'i')
          OR REGEXP_LIKE(q.RESULT_NORM, '(^|[^A-Z])R([^A-Z]|$)', 'i') THEN '耐药'
        WHEN REGEXP_LIKE(q.RESULT_NORM, '敏感', 'i')
          OR REGEXP_LIKE(q.RESULT_NORM, '(^|[^A-Z])S([^A-Z]|$)', 'i') THEN '敏感'
        WHEN REGEXP_LIKE(q.RESULT_NORM, '中介|中敏', 'i')
          OR REGEXP_LIKE(q.RESULT_NORM, '(^|[^A-Z])I([^A-Z]|$)', 'i') THEN '中介'
        ELSE '无判定标准'
    END AS DRUG_ALLERGY_NAME, -- 药敏结果名称 VARCHAR2(100) 是

    SUBSTRB(
        '原始药敏结果=' || NVL(q.RESULT_TXT, '未知') ||
        '；原始单位=' || NVL(q.UNITS_TXT, '未知') ||
        '；原始项目=' || NVL(q.ANTIBIOTIC_NAME_SRC, '未知'),
        1,
        1000
    ) AS DRUG_ALLERGY_NOTE, -- 药敏结果描述 VARCHAR2(1000)

    CAST(NULL AS VARCHAR2(100)) AS PIECE_DRUG, -- 纸片含药量 VARCHAR2(100)

    CASE
        WHEN REGEXP_LIKE(NVL(q.UNITS_TXT, ''), 'μg/mL|ug/ml|μg/ml|mg/L|mg/l', 'i')
         AND REGEXP_LIKE(
                q.RESULT_NUM_TXT,
                '^(<=|>=|<|>|≤|≥)?[0-9]+(\.[0-9]+)?$'
             )
        THEN SUBSTRB(q.RESULT_NUM_TXT, 1, 100)
        ELSE NULL
    END AS BACSTA_CONCEN, -- 最小抑菌浓度（MIC） VARCHAR2(100)

    CASE
        WHEN REGEXP_LIKE(NVL(q.UNITS_TXT, ''), 'mm', 'i')
         AND REGEXP_LIKE(
                q.RESULT_NUM_TXT,
                '^(<=|>=|<|>|≤|≥)?[0-9]+(\.[0-9]+)?$'
             )
        THEN SUBSTRB(q.RESULT_NUM_TXT, 1, 100)
        ELSE NULL
    END AS BACSTA_DIAMETER, -- 抑菌圈直径(mm) VARCHAR2(100)

    '未分级' AS ANTIBIOTIC_CLASS, -- 抗生素等级 VARCHAR2(100) 是，源无等级时先填未分级

    SUBSTRB(
        REGEXP_REPLACE(TO_CHAR(q.ANTIBIOTIC_CODE_SRC), '[^0-9A-Za-z]', ''),
        1,
        32
    ) AS ANTIBIOTIC_CODE, -- 抗生素代码 VARCHAR2(32)，非必填，无来源不强行填0

    SUBSTRB(
        NVL(q.ANTIBIOTIC_NAME_SRC, '未知'),
        1,
        100
    ) AS ANTIBIOTIC_NAME, -- 抗生素名称 VARCHAR2(100) 是

    q.EFFECTIVE_TIME AS EFFECTIVE_TIME, -- 活动发生时间 DATE

    CAST(NULL AS VARCHAR2(32)) AS STATUS, -- 卡片状态 VARCHAR2(32)

    CAST(NULL AS TIMESTAMP) AS CREATED_AT, -- 创建时间 TIMESTAMP(6)

    '370104' AS DISTRICT_CODE, -- 所属行政区划 VARCHAR2(6) 是

    'ADDHIS' AS EXCHANGE_TYPE, -- 交换类型 VARCHAR2(10) 是

    CAST(SYSTIMESTAMP AS TIMESTAMP) AS SYSTEM_TIME -- 数据上传时间戳 TIMESTAMP(6) 是

FROM
(
    SELECT
        p.ID AS REPORT_ID,
        p.APPLY_NUM AS APPLY_NUM,

        NVL(
            lr.RESULT_DATE_TIME,
            NVL(
                ltm.RESULTS_RPT_DATE_TIME,
                NVL(
                    ltm.EXECUTE_DATE,
                    NVL(
                        ltm.SPCM_RECEIVED_DATE_TIME,
                        NVL(ltm.SPCM_SAMPLE_DATE_TIME, ltm.REQUESTED_DATE_TIME)
                    )
                )
            )
        ) AS EFFECTIVE_TIME,

        lr.TEST_NO,
        lr.ITEM_NO,
        lr.PRINT_ORDER,
        lr.REPORT_ITEM_CODE AS ANTIBIOTIC_CODE_SRC,
        TRIM(lr.REPORT_ITEM_NAME) AS ANTIBIOTIC_NAME_SRC,
        TRIM(lr.RESULT) AS RESULT_TXT,
        TRIM(lr.UNITS) AS UNITS_TXT,

        UPPER(
            REGEXP_REPLACE(
                REPLACE(REPLACE(REPLACE(TRIM(NVL(lr.RESULT, '')), '＜', '<'), '＞', '>'), '，', ','),
                '[[:space:]]+',
                ''
            )
        ) AS RESULT_NORM,

        REGEXP_REPLACE(
            REPLACE(REPLACE(TRIM(NVL(lr.RESULT, '')), '＜', '<'), '＞', '>'),
            '[[:space:]]+',
            ''
        ) AS RESULT_NUM_TXT,

        ROW_NUMBER() OVER (
            PARTITION BY lr.TEST_NO
            ORDER BY
                NVL(lr.ITEM_NO, 999999),
                NVL(lr.PRINT_ORDER, 999999),
                NVL(lr.REPORT_ITEM_CODE, ' '),
                NVL(lr.REPORT_ITEM_NAME, ' '),
                NVL(lr.RESULT, ' '),
                ROWIDTOCHAR(lr.ROWID)
        ) AS RN

    FROM HIS.LAB_RESULT lr

    INNER JOIN HIS.LAB_TEST_MASTER ltm
        ON ltm.TEST_NO = lr.TEST_NO
       AND ltm.RESULT_STATUS = '4'

    /* 直接关联父表，保证 REPORT_ID 一定在 EMR_INSPECTION 主表存在，并继承父表 2021-2023 口径 */
    INNER JOIN V_EMR_INSPECTION_TEST p
        ON p.ID = TO_CHAR(ltm.TEST_NO)

    WHERE NULLIF(TRIM(lr.REPORT_ITEM_NAME), '') IS NOT NULL
      AND NULLIF(TRIM(lr.RESULT), '') IS NOT NULL

      /* 限定微生物类报告项目 */
      AND EXISTS (
          SELECT 1
          FROM HIS.LAB_TEST_ITEMS lti
          INNER JOIN HIS.CLINIC_ITEM_DICT cid
              ON cid.ITEM_CODE = lti.ITEM_CODE
             AND cid.EXPAND2 = '微生物类'
          WHERE lti.TEST_NO = lr.TEST_NO
            AND lti.ITEM_NO = lr.ITEM_NO
      )

      /* 抗菌药物、抗真菌药物类项目 */
      AND (
             lr.REPORT_ITEM_NAME LIKE '%头孢%'
          OR lr.REPORT_ITEM_NAME LIKE '%红霉素%'
          OR lr.REPORT_ITEM_NAME LIKE '%阿奇霉素%'
          OR lr.REPORT_ITEM_NAME LIKE '%克拉霉素%'
          OR lr.REPORT_ITEM_NAME LIKE '%替考拉宁%'
          OR lr.REPORT_ITEM_NAME LIKE '%达托霉素%'
          OR lr.REPORT_ITEM_NAME LIKE '%链霉素%'
          OR lr.REPORT_ITEM_NAME LIKE '%阿米卡星%'
          OR lr.REPORT_ITEM_NAME LIKE '%哌拉西林%'
          OR lr.REPORT_ITEM_NAME LIKE '%他唑巴坦%'
          OR lr.REPORT_ITEM_NAME LIKE '%亚胺培南%'
          OR lr.REPORT_ITEM_NAME LIKE '%美罗培南%'
          OR lr.REPORT_ITEM_NAME LIKE '%厄他培南%'
          OR lr.REPORT_ITEM_NAME LIKE '%莫西沙星%'
          OR lr.REPORT_ITEM_NAME LIKE '%环丙沙星%'
          OR lr.REPORT_ITEM_NAME LIKE '%左氧氟沙星%'
          OR lr.REPORT_ITEM_NAME LIKE '%诺氟沙星%'
          OR lr.REPORT_ITEM_NAME LIKE '%庆大霉素%'
          OR lr.REPORT_ITEM_NAME LIKE '%妥布霉素%'
          OR lr.REPORT_ITEM_NAME LIKE '%氯霉素%'
          OR lr.REPORT_ITEM_NAME LIKE '%万古霉素%'
          OR lr.REPORT_ITEM_NAME LIKE '%苯唑西林%'
          OR lr.REPORT_ITEM_NAME LIKE '%青霉素%'
          OR lr.REPORT_ITEM_NAME LIKE '%氨苄西林%'
          OR lr.REPORT_ITEM_NAME LIKE '%氨曲南%'
          OR lr.REPORT_ITEM_NAME LIKE '%利奈唑胺%'
          OR lr.REPORT_ITEM_NAME LIKE '%克林霉素%'
          OR lr.REPORT_ITEM_NAME LIKE '%利福平%'
          OR lr.REPORT_ITEM_NAME LIKE '%四环素%'
          OR lr.REPORT_ITEM_NAME LIKE '%米诺环素%'
          OR lr.REPORT_ITEM_NAME LIKE '%替加环素%'
          OR lr.REPORT_ITEM_NAME LIKE '%多黏菌素%'
          OR lr.REPORT_ITEM_NAME LIKE '%多粘菌素%'
          OR lr.REPORT_ITEM_NAME LIKE '%磷霉素%'
          OR lr.REPORT_ITEM_NAME LIKE '%呋喃妥因%'
          OR lr.REPORT_ITEM_NAME LIKE '%甲氧苄啶%'
          OR lr.REPORT_ITEM_NAME LIKE '%磺胺%'
          OR lr.REPORT_ITEM_NAME LIKE '%复方新诺明%'
          OR lr.REPORT_ITEM_NAME LIKE '%阿莫西林%'
          OR lr.REPORT_ITEM_NAME LIKE '%克拉维酸%'
          OR lr.REPORT_ITEM_NAME LIKE '%舒巴坦%'
          OR lr.REPORT_ITEM_NAME LIKE '%度洛巴坦%'
          OR lr.REPORT_ITEM_NAME LIKE '%卡泊芬净%'
          OR lr.REPORT_ITEM_NAME LIKE '%米卡芬净%'
          OR lr.REPORT_ITEM_NAME LIKE '%两性霉素B%'
          OR lr.REPORT_ITEM_NAME LIKE '%氟康唑%'
          OR lr.REPORT_ITEM_NAME LIKE '%伏立康唑%'
          OR lr.REPORT_ITEM_NAME LIKE '%伊曲康唑%'
          OR lr.REPORT_ITEM_NAME LIKE '%泊沙康唑%'
          OR lr.REPORT_ITEM_NAME LIKE '%阿尼芬净%'
          OR lr.REPORT_ITEM_NAME LIKE '%5-氟胞嘧啶%'
      )
) q
