
  CREATE OR REPLACE FORCE VIEW "ODS"."V_EMR_INSPECTION_ITEM_TEST" ("ID", "REPORT_ID", "APPLY_NUM", "SN", "ITEM_CODE", "RECIEVE_DT", "ITEM_NAME", "RESULT_TYPE", "RESULT_TYPE_NOTE", "ITEM_RESULT", "UNIT", "REFER_VALUE_LOWER", "REFER_VALUE_UPPER", "CRITICAL_VALUE", "ALARM_STATE", "CALL_DATE", "ATTACHED_RESULT", "RESULT_EXPLAIN", "RESULT_EXPLAIN_NOTE", "EFFECTIVE_TIME", "STATUS", "CREATED_AT", "DISTRICT_CODE", "EXCHANGE_TYPE", "LOCAL_ITEM_CODE", "LOCAL_ITEM_NAME", "SYSTEM_TIME", "RESULT_CODE", "RATION_RESULT", "RATION_RESULT_UOM", "TEST_SN", "TEST_RESULT_TYPE", "TEST_RESULT", "TEST_RESULT_UNIT", "ORG_CODE", "ORG_NAME", "TEST_EXAM_EQUIP_CODE", "BARCODE_NO", "NAME", "SEX_CODE", "ID_NUM", "MTU_REC_MARK", "MTU_REC_LIMIT_MARK", "HOSPITEM_NAME", "HOSPITEM_CODE", "PROJECT_CODE", "PROJECT_NAME", "ITEM_SIGN", "VISITING_NUM") AS 
  SELECT
    /* ===================== 主键与父表关联 ===================== */
    SUBSTRB(
        q.REPORT_ID || '_ITEM_' || TO_CHAR(q.RN),
        1,
        100
    ) AS ID, -- 内码 VARCHAR2(100) 是 主键

    SUBSTRB(q.REPORT_ID, 1, 100) AS REPORT_ID, -- 检验报告单内码 VARCHAR2(100) 是，关联 EMR_INSPECTION.ID

    SUBSTRB(NVL(q.APPLY_NUM, q.REPORT_ID), 1, 20) AS APPLY_NUM, -- 电子申请单编号 VARCHAR2(20) 是

    q.RN AS SN, -- 序号 NUMBER

    /* ===================== 检验项目 ===================== */
    SUBSTRB(
        NVL(
            map1.PLATFORM_ITEM_CODE,
            NVL(TO_CHAR(q.REPORT_ITEM_CODE), TO_CHAR(q.ITEM_NO))
        ),
        1,
        20
    ) AS ITEM_CODE, -- 检验项目代号，优先取平台 CS_EXAMINE_ITEM 编码

    q.RECIEVE_DT AS RECIEVE_DT, -- 检验科接收时间 DATE

    SUBSTRB(
        NVL(
            map1.PLATFORM_ITEM_NAME,
            NVL(q.REPORT_ITEM_NAME, '未知项目')
        ),
        1,
        80
    ) AS ITEM_NAME, -- 检验项目名称，优先取平台 CS_EXAMINE_ITEM 名称

    CASE
        WHEN q.IS_NUMERIC_RESULT = '1' THEN '2'
        ELSE '1'
    END AS RESULT_TYPE, -- 结果类型代码 VARCHAR2(32) 是；1文本 2数值

    CASE
        WHEN q.IS_NUMERIC_RESULT = '1' THEN '数值'
        ELSE '文本'
    END AS RESULT_TYPE_NOTE, -- 结果类型描述 VARCHAR2(100) 是

    SUBSTRB(
        NVL(q.RESULT_TXT, '未记录'),
        1,
        100
    ) AS ITEM_RESULT, -- 检验项目结果 VARCHAR2(100) 是

    SUBSTRB(
        NVL(q.UNITS_TXT, '无'),
        1,
        20
    ) AS UNIT, -- 单位 VARCHAR2(20) 是

    CASE
        WHEN REGEXP_LIKE(
                 q.REF_RANGE_NORM,
                 '^[<>≤≥]?[0-9]+(\.[0-9]+)?~[<>≤≥]?[0-9]+(\.[0-9]+)?$'
             )
        THEN TO_NUMBER(REGEXP_SUBSTR(q.REF_RANGE_NORM, '[0-9]+(\.[0-9]+)?', 1, 1))
        ELSE 0
    END AS REFER_VALUE_LOWER, -- 正常参考值下限 NUMBER(12,2)

    CASE
        WHEN REGEXP_LIKE(
                 q.REF_RANGE_NORM,
                 '^[<>≤≥]?[0-9]+(\.[0-9]+)?~[<>≤≥]?[0-9]+(\.[0-9]+)?$'
             )
        THEN TO_NUMBER(REGEXP_SUBSTR(q.REF_RANGE_NORM, '[0-9]+(\.[0-9]+)?', 1, 2))
        ELSE 0
    END AS REFER_VALUE_UPPER, -- 正常参考值上限 NUMBER(12,2)

    CAST(NULL AS NUMBER(12,2)) AS CRITICAL_VALUE, -- 危急值 NUMBER(12,2)

    CAST(NULL AS VARCHAR2(20)) AS ALARM_STATE, -- 通知状态 VARCHAR2(20)

    CAST(NULL AS DATE) AS CALL_DATE, -- 通知日期 DATE

    CAST(NULL AS VARCHAR2(100)) AS ATTACHED_RESULT, -- 附属结果 VARCHAR2(100)

    CASE
        WHEN q.ITEM_SIGN = '1' THEN '1'
        WHEN q.ITEM_SIGN = '2' THEN '2'
        ELSE '3'
    END AS RESULT_EXPLAIN, -- 结果值的解释 VARCHAR2(32) 是

    CASE
        WHEN q.ITEM_SIGN = '1' THEN '正常'
        WHEN q.ITEM_SIGN = '2' THEN '异常'
        ELSE '不确定'
    END AS RESULT_EXPLAIN_NOTE, -- 结果值的解释描述 VARCHAR2(200) 是

    NVL(q.RESULT_DATE_TIME, q.EFFECTIVE_TIME) AS EFFECTIVE_TIME, -- 活动发生时间 DATE

    CAST(NULL AS VARCHAR2(32)) AS STATUS, -- 卡片状态 VARCHAR2(32)

    CAST(NULL AS TIMESTAMP) AS CREATED_AT, -- 创建时间 TIMESTAMP(6)

    '370104' AS DISTRICT_CODE, -- 所属行政区划 VARCHAR2(6) 是

    'ADDHIS' AS EXCHANGE_TYPE, -- 交换类型 VARCHAR2(10) 是

    SUBSTRB(
        NVL(TO_CHAR(q.REPORT_ITEM_CODE), TO_CHAR(q.ITEM_NO)),
        1,
        20
    ) AS LOCAL_ITEM_CODE, -- 检验报告项目本地编码，保留 LAB_RESULT 明细编码

    SUBSTRB(
        NVL(q.REPORT_ITEM_NAME, '未知项目'),
        1,
        80
    ) AS LOCAL_ITEM_NAME, -- 检验报告项目本地名称，保留 LAB_RESULT 明细名称

    CAST(SYSTIMESTAMP AS TIMESTAMP) AS SYSTEM_TIME, -- 数据上传时间戳 TIMESTAMP(6) 是

    q.ITEM_SIGN AS RESULT_CODE, -- 检验结果代码 CHAR(1)

    CASE
        WHEN q.IS_NUMERIC_RESULT = '1' THEN
            TO_NUMBER(
                REGEXP_REPLACE(
                    q.RESULT_NUM_TXT,
                    '^(<=|>=|<|>|≤|≥)',
                    ''
                )
            )
        ELSE NULL
    END AS RATION_RESULT, -- 检验定量结果 NUMBER(14,4)

    CASE
        WHEN q.IS_NUMERIC_RESULT = '1' THEN SUBSTRB(NVL(q.UNITS_TXT, '无'), 1, 20)
        ELSE NULL
    END AS RATION_RESULT_UOM, -- 检验定量结果计量单位 VARCHAR2(20)

    q.RN AS TEST_SN, -- 检验项目顺序号 NUMBER(4)

    CASE
        WHEN q.IS_NUMERIC_RESULT = '1' THEN 2
        ELSE 1
    END AS TEST_RESULT_TYPE, -- 检验结果类型 NUMBER(1)

    SUBSTRB(
        NVL(q.RESULT_TXT, '未记录'),
        1,
        50
    ) AS TEST_RESULT, -- 检验结果 VARCHAR2(50)

    SUBSTRB(
        NVL(q.UNITS_TXT, '无'),
        1,
        50
    ) AS TEST_RESULT_UNIT, -- 检验结果计量单位 VARCHAR2(50)

    '49557032X' AS ORG_CODE, -- 医院组织机构代码 VARCHAR2(32) 是

    '山东省第二人民医院' AS ORG_NAME, -- 医院名称 VARCHAR2(70) 是

    SUBSTRB(q.INSTRUMENT_ID, 1, 32) AS test_exam_equip_code, -- 检查设备编码

    SUBSTRB(
        NVL(q.BARCODE_NO, q.SAMPLE_NUM),
        1,
        50
    ) AS BARCODE_NO, -- 标本条形码号 VARCHAR2(50) 是

    SUBSTRB(
        NVL(q.NAME, '未知'),
        1,
        50
    ) AS NAME, -- 患者姓名 VARCHAR2(50) 是

    CASE
        WHEN q.SEX_CODE IN ('0','1','2','9') THEN q.SEX_CODE
        ELSE '9'
    END AS SEX_CODE, -- 患者性别代码 CHAR(1) 是

    SUBSTRB(
        NVL(q.ID_NUM, '000000000000000000'),
        1,
        18
    ) AS ID_NUM, -- 患者身份证件号码 VARCHAR2(18) 是

    /* ===================== 互认字段：按 CLINIC_ITEM_MAPPING_U 判断 ===================== */
    CASE
        WHEN cim.HIS_ITEM_CODE IS NOT NULL THEN '1'
        ELSE '0'
    END AS MTU_REC_MARK, -- 是否互认标识：互认映射表存在则 1，否则 0

    SUBSTRB(
        CASE
            WHEN cim.HIS_ITEM_CODE IS NOT NULL THEN cim.SPT_ITEM_CODE
            ELSE NULL
        END,
        1,
        100
    ) AS MTU_REC_LIMIT_MARK, -- 互认范围标识：暂用平台互认项目编码 SPT_ITEM_CODE

    SUBSTRB(
        NVL(q.TEST_ITEM_NAME, NVL(q.REPORT_ITEM_NAME, '未知项目')),
        1,
        100
    ) AS HOSPITEM_NAME, -- 院内项目名称：优先取 LAB_TEST_ITEMS.ITEM_NAME

    SUBSTRB(
        NVL(q.TEST_ITEM_CODE, NVL(TO_CHAR(q.REPORT_ITEM_CODE), TO_CHAR(q.ITEM_NO))),
        1,
        100
    ) AS HOSPITEM_CODE, -- 院内项目编码：优先取 LAB_TEST_ITEMS.ITEM_CODE

    SUBSTRB(
        cim.SPT_ITEM_CODE,
        1,
        100
    ) AS PROJECT_CODE, -- 国家平台项目编码

    SUBSTRB(
        cim.SPT_ITEM_NAME,
        1,
        100
    ) AS PROJECT_NAME, -- 国家平台项目名称

    q.ITEM_SIGN AS ITEM_SIGN, -- 结果标识 VARCHAR2(100) 是；1正常 2异常 3不确定

    SUBSTRB(
        q.VISITING_NUM,
        1,
        32
    ) AS VISITING_NUM -- 就诊号 VARCHAR2(32) 是

FROM
(
    SELECT
        p.ID AS REPORT_ID,
        p.APPLY_NUM AS APPLY_NUM,
        p.SAMPLE_RECEIVE_DATE AS RECIEVE_DT,
        p.EFFECTIVE_TIME AS EFFECTIVE_TIME,
        p.SAMPLE_NUM AS SAMPLE_NUM,
        p.NAME AS NAME,
        p.SEX_CODE AS SEX_CODE,
        p.ID_NUM AS ID_NUM,
        p.VISITING_NUM AS VISITING_NUM,

        lr.TEST_NO,
        lr.ITEM_NO,
        lr.PRINT_ORDER,
        lr.REPORT_ITEM_CODE,
        TRIM(lr.REPORT_ITEM_NAME) AS REPORT_ITEM_NAME,
        TRIM(lr.RESULT) AS RESULT_TXT,
        TRIM(lr.UNITS) AS UNITS_TXT,
        TRIM(lr.ABNORMAL_INDICATOR) AS ABNORMAL_INDICATOR,
        SUBSTRB(lr.INSTRUMENT_ID, 1, 32) AS INSTRUMENT_ID,
        lr.RESULT_DATE_TIME AS RESULT_DATE_TIME,

        /* LAB_TEST_ITEMS 申请/组合项目字段，用于互认映射 */
        TRIM(lti.ITEM_CODE) AS TEST_ITEM_CODE,
        TRIM(lti.ITEM_NAME) AS TEST_ITEM_NAME,

        TRIM(
            COALESCE(
                TRIM(lr.PRINT_CONTEXT),
                TRIM(lr.RESULT_RANGE)
            )
        ) AS REF_RANGE_TXT,

        REGEXP_REPLACE(
            REGEXP_REPLACE(
                TRIM(
                    COALESCE(
                        TRIM(lr.PRINT_CONTEXT),
                        TRIM(lr.RESULT_RANGE)
                    )
                ),
                '([0-9])\s*(--|－|—|–|~|～|至|-)\s*([0-9])',
                '\1~\3'
            ),
            '[[:space:]]+',
            ''
        ) AS REF_RANGE_NORM,

        p.SAMPLE_NUM AS BARCODE_NO,

        REGEXP_REPLACE(
            REPLACE(
                REPLACE(
                    REPLACE(TRIM(NVL(lr.RESULT, '')), '＜', '<'),
                    '＞',
                    '>'
                ),
                '－',
                '-'
            ),
            '[[:space:]]+',
            ''
        ) AS RESULT_NUM_TXT,

        CASE
            WHEN REGEXP_LIKE(
                    REGEXP_REPLACE(
                        REPLACE(
                            REPLACE(
                                REPLACE(TRIM(NVL(lr.RESULT, '')), '＜', '<'),
                                '＞',
                                '>'
                            ),
                            '－',
                            '-'
                        ),
                        '[[:space:]]+',
                        ''
                    ),
                    '^(<=|>=|<|>|≤|≥)?[0-9]+(\.[0-9]+)?$'
                 )
            THEN '1'
            ELSE '0'
        END AS IS_NUMERIC_RESULT,

        CASE
            WHEN UPPER(TRIM(NVL(lr.ABNORMAL_INDICATOR, ''))) IN
                 ('H', 'L', 'HH', 'LL', 'A', 'ABN', 'HIGH', 'LOW', '↑', '↓', '+') THEN '2'

            WHEN UPPER(TRIM(NVL(lr.ABNORMAL_INDICATOR, ''))) IN
                 ('N', 'NORMAL', '0') THEN '1'

            WHEN REGEXP_LIKE(
                    UPPER(TRIM(NVL(lr.RESULT, ''))),
                    '阴性|正常|未见|NEGATIVE|NORMAL'
                 )
              OR TRIM(NVL(lr.RESULT, '')) = '-' THEN '1'

            WHEN REGEXP_LIKE(
                    UPPER(TRIM(NVL(lr.RESULT, ''))),
                    '阳性|POSITIVE'
                 ) THEN '3'

            WHEN REGEXP_LIKE(
                    REGEXP_REPLACE(
                        REPLACE(
                            REPLACE(
                                REPLACE(TRIM(NVL(lr.RESULT, '')), '＜', '<'),
                                '＞',
                                '>'
                            ),
                            '－',
                            '-'
                        ),
                        '[[:space:]]+',
                        ''
                    ),
                    '^(<=|>=|<|>|≤|≥)?[0-9]+(\.[0-9]+)?$'
                 ) THEN '1'

            ELSE '3'
        END AS ITEM_SIGN,

        ROW_NUMBER() OVER (
            PARTITION BY lr.TEST_NO
            ORDER BY
                NVL(lr.ITEM_NO, 999999),
                NVL(lr.PRINT_ORDER, 999999),
                NVL(lr.REPORT_ITEM_CODE, ' '),
                NVL(lr.REPORT_ITEM_NAME, ' '),
                ROWIDTOCHAR(lr.ROWID)
        ) AS RN

    FROM
    (
        SELECT
            SUBSTRB(TO_CHAR(m.TEST_NO), 1, 100) AS ID,
            m.TEST_NO AS TEST_NO_RAW,

            SUBSTRB(
                CASE
                    WHEN m.SRC_TYPE_FOR_JOIN IN ('O_RCPT', 'O_NORCPT') THEN
                        NVL(m.RCPT_NO_C, TO_CHAR(m.TEST_NO))
                    ELSE
                        NVL(TO_CHAR(m.ORDER_ID), TO_CHAR(m.TEST_NO))
                END,
                1,
                20
            ) AS APPLY_NUM,

            NVL(
                m.SPCM_RECEIVED_DATE_TIME,
                NVL(
                    m.EXECUTE_DATE,
                    NVL(
                        m.SPCM_SAMPLE_DATE_TIME,
                        NVL(
                            m.RESULTS_RPT_DATE_TIME,
                            NVL(
                                m.REQUESTED_DATE_TIME,
                                COALESCE(e_i.VISIT_DATE_TIME, e_or.VISIT_DATE_TIME, e_od.VISIT_DATE_TIME, m.BUSINESS_DATE)
                            )
                        )
                    )
                )
            ) AS SAMPLE_RECEIVE_DATE,

            SUBSTRB(NVL(m.SPECIMEN_NO, m.TEST_NO), 1, 20) AS SAMPLE_NUM,

            SUBSTRB(NVL(m.NAME, pmi.NAME), 1, 50) AS NAME,

            CASE TRIM(m.SEX)
                WHEN '男' THEN '1'
                WHEN '女' THEN '2'
                WHEN '未知' THEN '0'
                WHEN '不详' THEN '9'
                WHEN '未说明' THEN '9'
                ELSE '9'
            END AS SEX_CODE,

            SUBSTRB(NVL(pmi.ID_NO, '000000000000000000'), 1, 18) AS ID_NUM,

            SUBSTRB(
                CASE
                    WHEN m.SRC_TYPE_FOR_JOIN = 'I' THEN
                        m.PATIENT_ID_C || '|' || m.VISIT_ID_C
                    WHEN m.SRC_TYPE_FOR_JOIN = 'O_RCPT' THEN
                        NVL(e_or.VISIT_ID, NVL(m.RCPT_NO_C, TO_CHAR(m.TEST_NO)))
                    WHEN m.SRC_TYPE_FOR_JOIN = 'O_NORCPT' THEN
                        NVL(e_od.VISIT_ID, TO_CHAR(m.TEST_NO))
                    ELSE
                        TO_CHAR(m.TEST_NO)
                END,
                1,
                32
            ) AS VISITING_NUM,

            NVL(
                m.RESULTS_RPT_DATE_TIME,
                NVL(
                    m.EXECUTE_DATE,
                    NVL(
                        m.SPCM_RECEIVED_DATE_TIME,
                        NVL(
                            m.SPCM_SAMPLE_DATE_TIME,
                            NVL(
                                m.REQUESTED_DATE_TIME,
                                COALESCE(e_i.VISIT_DATE_TIME, e_or.VISIT_DATE_TIME, e_od.VISIT_DATE_TIME, m.BUSINESS_DATE)
                            )
                        )
                    )
                )
            ) AS EFFECTIVE_TIME

        FROM
        (
            SELECT
                m0.TEST_NO,
                m0.PATIENT_ID,
                m0.VISIT_ID,
                m0.RCPT_NO,
                m0.ORDER_ID,
                m0.REQUESTED_DATE_TIME,
                m0.SPCM_SAMPLE_DATE_TIME,
                m0.EXECUTE_DATE,
                m0.RESULTS_RPT_DATE_TIME,
                m0.SPCM_RECEIVED_DATE_TIME,
                m0.RESULT_STATUS,
                m0.SPECIMEN_NO,
                m0.NAME,
                m0.SEX,
                TO_CHAR(m0.PATIENT_ID) AS PATIENT_ID_C,
                TO_CHAR(m0.VISIT_ID) AS VISIT_ID_C,
                TO_CHAR(m0.RCPT_NO) AS RCPT_NO_C,
                NVL(
                    m0.REQUESTED_DATE_TIME,
                    NVL(
                        m0.SPCM_SAMPLE_DATE_TIME,
                        NVL(
                            m0.EXECUTE_DATE,
                            NVL(m0.RESULTS_RPT_DATE_TIME, m0.SPCM_RECEIVED_DATE_TIME)
                        )
                    )
                ) AS BUSINESS_DATE,
                CASE
                    WHEN m0.VISIT_ID > 0 THEN 'I'
                    WHEN m0.RCPT_NO IS NOT NULL THEN 'O_RCPT'
                    WHEN m0.VISIT_ID IS NULL OR m0.VISIT_ID = 0 THEN 'O_NORCPT'
                    ELSE 'X'
                END AS SRC_TYPE_FOR_JOIN
            FROM HIS.LAB_TEST_MASTER m0
        ) m

        LEFT JOIN
        (
            SELECT
                TO_CHAR(a.PATIENT_ID) AS PATIENT_ID,
                TO_CHAR(a.VISIT_ID) AS VISIT_ID,
                MIN(a.DISCHARGE_DATE_TIME) AS VISIT_DATE_TIME
            FROM HIS.PAT_VISIT a
            WHERE a.DISCHARGE_DATE_TIME >= DATE '2021-01-01'
              AND a.DISCHARGE_DATE_TIME <  DATE '2024-01-01'
            GROUP BY
                TO_CHAR(a.PATIENT_ID),
                TO_CHAR(a.VISIT_ID)
        ) e_i
            ON m.SRC_TYPE_FOR_JOIN = 'I'
           AND e_i.PATIENT_ID = m.PATIENT_ID_C
           AND e_i.VISIT_ID = m.VISIT_ID_C

        LEFT JOIN
        (
            SELECT
                TO_CHAR(a.PATIENT_ID) AS PATIENT_ID,
                TO_CHAR(a.RCPT_NO) AS RCPT_NO,
                MIN(TO_CHAR(a.CLINIC_NO)) AS VISIT_ID,
                MIN(a.VISIT_DATE) AS VISIT_DATE_TIME
            FROM HIS.OUTP_ORDER_DESC a
            WHERE a.VISIT_DATE >= DATE '2021-01-01'
              AND a.VISIT_DATE <  DATE '2024-01-01'
              AND a.RCPT_NO IS NOT NULL
              AND a.CLINIC_NO IS NOT NULL
            GROUP BY
                TO_CHAR(a.PATIENT_ID),
                TO_CHAR(a.RCPT_NO)
        ) e_or
            ON m.SRC_TYPE_FOR_JOIN = 'O_RCPT'
           AND e_or.PATIENT_ID = m.PATIENT_ID_C
           AND e_or.RCPT_NO = m.RCPT_NO_C

        LEFT JOIN
        (
            SELECT
                PATIENT_ID,
                VISIT_DATE,
                VISIT_ID,
                VISIT_DATE_TIME
            FROM
            (
                SELECT
                    TO_CHAR(a.PATIENT_ID) AS PATIENT_ID,
                    TRUNC(a.VISIT_DATE) AS VISIT_DATE,
                    MIN(TO_CHAR(a.CLINIC_NO)) AS VISIT_ID,
                    MIN(a.VISIT_DATE) AS VISIT_DATE_TIME,
                    COUNT(DISTINCT TO_CHAR(a.CLINIC_NO)) AS CLINIC_NO_CNT
                FROM HIS.OUTP_ORDER_DESC a
                WHERE a.VISIT_DATE >= DATE '2021-01-01'
                  AND a.VISIT_DATE <  DATE '2024-01-01'
                  AND a.CLINIC_NO IS NOT NULL
                GROUP BY
                    TO_CHAR(a.PATIENT_ID),
                    TRUNC(a.VISIT_DATE)
            )
            WHERE CLINIC_NO_CNT = 1
        ) e_od
            ON m.SRC_TYPE_FOR_JOIN = 'O_NORCPT'
           AND e_od.PATIENT_ID = m.PATIENT_ID_C
           AND e_od.VISIT_DATE = TRUNC(m.BUSINESS_DATE)

        LEFT JOIN HIS.PAT_MASTER_INDEX pmi
            ON pmi.PATIENT_ID = m.PATIENT_ID

        WHERE m.RESULT_STATUS <> '1'
          AND (
                (
                    m.SRC_TYPE_FOR_JOIN = 'I'
                    AND e_i.PATIENT_ID IS NOT NULL
                )
                OR
                (
                    m.SRC_TYPE_FOR_JOIN = 'O_RCPT'
                    AND m.BUSINESS_DATE >= DATE '2021-01-01'
                    AND m.BUSINESS_DATE <  DATE '2024-01-01'
                )
                OR
                (
                    m.SRC_TYPE_FOR_JOIN = 'O_NORCPT'
                    AND e_od.PATIENT_ID IS NOT NULL
                    AND m.BUSINESS_DATE >= DATE '2021-01-01'
                    AND m.BUSINESS_DATE <  DATE '2024-01-01'
                )
              )
    ) p

    INNER JOIN HIS.LAB_RESULT lr
        ON lr.TEST_NO = p.TEST_NO_RAW

    LEFT JOIN HIS.LAB_TEST_ITEMS lti
        ON lti.TEST_NO = TO_CHAR(lr.TEST_NO)
       AND lti.ITEM_NO = lr.ITEM_NO

    WHERE NULLIF(TRIM(lr.REPORT_ITEM_NAME), '') IS NOT NULL
      AND NULLIF(TRIM(lr.RESULT), '') IS NOT NULL
) q

/* 检验结果明细项目值域：按 本地编码 + 本地名称 直接匹配 */
LEFT JOIN HIS.LIS_EXAMINE_ITEM_MAP map1
    ON TRIM(map1.LOCAL_ITEM_CODE) = TRIM(NVL(TO_CHAR(q.REPORT_ITEM_CODE), TO_CHAR(q.ITEM_NO)))
   AND TRIM(map1.LOCAL_ITEM_NAME) = TRIM(q.REPORT_ITEM_NAME)

/* 互认项目：LAB_TEST_ITEMS.ITEM_CODE -> 已去重互认映射表 */
LEFT JOIN CLINIC_ITEM_MAPPING_U cim
    ON cim.HIS_ITEM_CODE = TRIM(q.TEST_ITEM_CODE)
