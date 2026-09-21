SELECT
    SUBSTR(m.EXAM_NO || '|' || i.EXAM_ITEM_NO, 1, 100)        AS ID,
    '49557032X'                                                AS ORG_CODE,
    '山东省第二人民医院'                                       AS ORG_NAME,

    CASE
        WHEN m.SRC_TYPE_FOR_JOIN = 'O' THEN '10'
        WHEN m.SRC_TYPE_FOR_JOIN = 'I' THEN '50'
        ELSE '99'
    END                                                        AS PATIENT_TYPE_CODE,

    CASE
        WHEN m.SRC_TYPE_FOR_JOIN = 'O' THEN '门诊'
        WHEN m.SRC_TYPE_FOR_JOIN = 'I' THEN '住院'
        ELSE '其他'
    END                                                        AS PATIENT_TYPE_NAME,

    m.EXAM_NO                                                  AS REPORT_NUM,

    CASE
        WHEN m.EXAM_CLASS = 'CT' THEN '01'
        WHEN m.EXAM_CLASS = '磁共振' THEN '02'
        WHEN m.EXAM_CLASS IN ('X线', '数字胃肠', '乳腺钼靶', '牙片室') THEN '03'
        WHEN m.EXAM_CLASS = '介入' THEN '04'
        WHEN m.EXAM_CLASS IN ('B超', '妇产超声') THEN '05'
        WHEN m.EXAM_CLASS IN ('心电图', '肌电图', '脑电图') THEN '06'
        WHEN m.EXAM_CLASS IN ('支气管镜', '消化内镜', '胃肠镜', '胸腔镜') THEN '07'
        WHEN m.EXAM_CLASS = '核医学检查' THEN '08'
        WHEN m.EXAM_CLASS = '病理' THEN '09'
        WHEN m.EXAM_CLASS = '核医学' THEN '10'
        ELSE '99'
    END                                                        AS IMAGE_TYPE_CODE,

    CASE
        WHEN m.EXAM_CLASS = 'CT' THEN 'CT检查'
        WHEN m.EXAM_CLASS = '磁共振' THEN 'MR检查'
        WHEN m.EXAM_CLASS IN ('X线', '数字胃肠', '乳腺钼靶', '牙片室') THEN '放射检查'
        WHEN m.EXAM_CLASS = '介入' THEN '介入'
        WHEN m.EXAM_CLASS IN ('B超', '妇产超声') THEN 'B超检查(超声)'
        WHEN m.EXAM_CLASS IN ('心电图', '肌电图', '脑电图') THEN '电生理'
        WHEN m.EXAM_CLASS IN ('支气管镜', '消化内镜', '胃肠镜', '胸腔镜') THEN '镜检'
        WHEN m.EXAM_CLASS = '核医学检查' THEN '核医学检查'
        WHEN m.EXAM_CLASS = '病理' THEN '病理'
        WHEN m.EXAM_CLASS = '核医学' THEN '核医学'
        ELSE '其它'
    END                                                        AS IMAGE_TYPE_NAME,

    NULL                                                       AS OTHER_ID_TYPE,
    NULL                                                       AS OTHER_ID_NUM,
    p.ID_NO                                                    AS ID_NUM,

    m.NAME                                                     AS NAME,
    CASE m.SEX
        WHEN '男' THEN '1'
        WHEN '女' THEN '2'
        WHEN '未知' THEN '0'
        ELSE '9'
    END                                                        AS SEX_CODE,
    m.SEX                                                      AS SEX_NAME,
    p.NEXT_OF_KIN_PHONE                                        AS TELEPHONE,

    CAST(
        CASE
            WHEN m.DATE_OF_BIRTH IS NOT NULL
             AND m.EXAM_DATE_TIME IS NOT NULL
            THEN LEAST(
                     200,
                     GREATEST(
                         0,
                         TRUNC(MONTHS_BETWEEN(m.EXAM_DATE_TIME, m.DATE_OF_BIRTH) / 12)
                     )
                 )
            ELSE 0
        END AS NUMBER
    )                                                          AS AGE,

    NULL                                                       AS AGE_MONTH,
    NULL                                                       AS AGE_DAY,
    NULL                                                       AS AGE_HOUR,

    SUBSTR(
        CASE
            WHEN m.SRC_TYPE_FOR_JOIN = 'O' THEN
                NVL(
                    e_appt.VISIT_ID,
                    NVL(
                        e_rcpt.VISIT_ID,
                        NVL(
                            e_ov.VISIT_ID,
                            NVL(m.RCPT_NO_C, TO_CHAR(m.EXAM_NO))
                        )
                    )
                )
            ELSE
                m.PATIENT_ID_C || '|' || m.VISIT_ID_C
        END,
        1,
        32
    )                                                          AS VISITING_NUM,

    COALESCE(d_perf.QMPT_CODE, d_perf.DEPT_CODE)               AS DEP_NUM,
    COALESCE(d_perf.QMPT_NAME, d_perf.DEPT_NAME)               AS DEP_NAME,
    NULL                                                       AS AREA_NAME,
    NULL                                                       AS SICKBED_NUM,
    m.EXAM_NO                                                  AS EXAM_NUM,
    SUBSTR(m.CLIN_SYMP, 1, 1000)                               AS EXAM_AIM,
    m.EXAM_NO                                                  AS APPLY_NUM,

    '49557032X'                                                AS APPLY_HOSP_CODE,
    '山东省第二人民医院'                                       AS APPLY_HOSP_NAME,
    COALESCE(d_req.QMPT_CODE, d_req.DEPT_CODE)                 AS APPLY_DEPT_CODE,
    COALESCE(d_req.QMPT_NAME, d_req.DEPT_NAME)                 AS APPLY_DEPT_NAME,
    COALESCE(m.REQ_DATE_TIME, a.SCHEDULED_DATE, m.SCHEDULED_DATE_TIME, m.EXAM_DATE_TIME)
                                                                 AS APPLY_DATE,
    usr.IDENNO                                                 AS APPLY_DOCTOR_CODE,
    m.REQ_PHYSICIAN                                            AS APPLY_DOCTOR_NAME,

    NULL                                                       AS DISEASE_CODE,
    SUBSTR(m.CLIN_DIAG, 1, 200)                                AS DISEASE_NAME,
    '49557032X'                                                AS DIAGNOSE_HOSP_CODE,
    '山东省第二人民医院'                                       AS DIAGNOSE_HOSP_NAME,

    COALESCE(
        r.REPORT_TIME,
        m.REPORT_DATE_TIME,
        m.AUDITING_DATE_TIME,
        m.EXAM_DATE_TIME,
        m.REQ_DATE_TIME
    )                                                          AS DIAGNOSE_DATE,

    '-'                                                        AS CRITICAL_VALUE,
    '-'                                                        AS ALARM_STATE,
    NULL                                                       AS CALL_DATE,

    SUBSTR(m.CLIN_SYMP, 1, 1000)                               AS CHIEF_COMPLAINT,
    NULL                                                       AS SIGN_BEGIN_DATE,
    NULL                                                       AS SIGN_END_DATE,
    SUBSTR(m.PHYS_SIGN, 1, 1200)                               AS SIGN_NOTE,
    NULL                                                       AS SPEC_EXAM_FLAG,
    NULL                                                       AS OPER_CODE,
    NULL                                                       AS OPER_NAME,

    CASE
        WHEN m.EXAM_SUB_CLASS IN ('CT头部', 'MR头部', 'DR头部') THEN '242'
        WHEN m.EXAM_SUB_CLASS IN ('CT颈部', 'MR颈部') THEN '252'
        WHEN m.EXAM_SUB_CLASS IN ('CT胸部', 'MR胸部', 'DR胸部', '胸部系列', '胸腔镜') THEN '180'
        WHEN m.EXAM_SUB_CLASS IN ('腹部系列', 'DR腹部') THEN '202'
        WHEN m.EXAM_SUB_CLASS IN ('CT上腹部', 'MR上腹部') THEN '62'
        WHEN m.EXAM_SUB_CLASS IN ('CT下腹部', 'MR下腹部') THEN '71'
        WHEN m.EXAM_SUB_CLASS IN ('RF数字胃肠', '胃肠镜') THEN '202'
        WHEN m.EXAM_SUB_CLASS IN ('CT盆腔', 'MR盆腔') THEN '136'
        WHEN m.EXAM_SUB_CLASS IN ('妇产超声', '妇产系列')
         AND (i.EXAM_ITEM LIKE '%胎%' OR i.EXAM_ITEM LIKE '%产%' OR i.EXAM_ITEM LIKE '%宫腔%') THEN '77'
        WHEN m.EXAM_SUB_CLASS IN ('妇产超声', '妇产系列') THEN '98'
        WHEN m.EXAM_SUB_CLASS IN ('CT脊柱', 'MR脊柱', 'DR脊柱') THEN '79'
        WHEN m.EXAM_SUB_CLASS = 'DR骨盆' THEN '268'
        WHEN m.EXAM_SUB_CLASS IN ('DR下肢', 'MR下肢') THEN '64'
        WHEN m.EXAM_SUB_CLASS = 'DR肩部' THEN '159'
        WHEN m.EXAM_SUB_CLASS = '乳腺MR' THEN '74'
        WHEN m.EXAM_SUB_CLASS = '心脏系列' THEN '112'
        WHEN m.EXAM_SUB_CLASS = 'CBCT' THEN '89'
        WHEN m.EXAM_SUB_CLASS = '心电图' AND i.EXAM_ITEM LIKE '%24小时%' THEN '49'
        WHEN m.EXAM_SUB_CLASS = '心电图' AND i.EXAM_ITEM LIKE '%48小时%' THEN '50'
        WHEN m.EXAM_SUB_CLASS = '心电图' AND i.EXAM_ITEM LIKE '%72小时%' THEN '51'
        WHEN m.EXAM_SUB_CLASS = '心电图' THEN '109'
        WHEN m.EXAM_SUB_CLASS = '脑电图' THEN '110'
        WHEN m.EXAM_SUB_CLASS IN ('主观听力检查', '客观听力检查') THEN '81'
        WHEN m.EXAM_SUB_CLASS = '支气管镜' THEN '125'
        WHEN m.EXAM_SUB_CLASS = '消化内镜' THEN '99'
        WHEN m.EXAM_SUB_CLASS IN (
            '公共', '其他', 'CT其他', 'MR其他项目', '超声其他', '血管系列',
            'CT血管成像', 'MR血管成像', '数字化造影', '肺功能', '一氧化氮',
            '肌电图', '电生理检查', '动态血压监测', 'CT四肢', 'MR功能成像',
            'MR上肢', 'DR上肢', '浅表器官', '肌骨关节神经', '超声介入', '生殖系列'
        ) THEN '99'
        ELSE '99'
    END                                                        AS EXAM_POS_CODE,

    CASE
        WHEN m.EXAM_SUB_CLASS IN ('CT头部', 'MR头部', 'DR头部') THEN '颅脑'
        WHEN m.EXAM_SUB_CLASS IN ('CT颈部', 'MR颈部') THEN '颈部'
        WHEN m.EXAM_SUB_CLASS IN ('CT胸部', 'MR胸部', 'DR胸部', '胸部系列', '胸腔镜') THEN '胸部'
        WHEN m.EXAM_SUB_CLASS IN ('腹部系列', 'DR腹部') THEN '腹部'
        WHEN m.EXAM_SUB_CLASS IN ('CT上腹部', 'MR上腹部') THEN '上腹部'
        WHEN m.EXAM_SUB_CLASS IN ('CT下腹部', 'MR下腹部') THEN '下腹部'
        WHEN m.EXAM_SUB_CLASS IN ('RF数字胃肠', '胃肠镜') THEN '腹部'
        WHEN m.EXAM_SUB_CLASS IN ('CT盆腔', 'MR盆腔') THEN '盆腔'
        WHEN m.EXAM_SUB_CLASS IN ('妇产超声', '妇产系列')
         AND (i.EXAM_ITEM LIKE '%胎%' OR i.EXAM_ITEM LIKE '%产%' OR i.EXAM_ITEM LIKE '%宫腔%') THEN '产科（胎儿及宫腔）'
        WHEN m.EXAM_SUB_CLASS IN ('妇产超声', '妇产系列') THEN '妇科（女性生殖系统）'
        WHEN m.EXAM_SUB_CLASS IN ('CT脊柱', 'MR脊柱', 'DR脊柱') THEN '全脊柱'
        WHEN m.EXAM_SUB_CLASS = 'DR骨盆' THEN '骨盆'
        WHEN m.EXAM_SUB_CLASS IN ('DR下肢', 'MR下肢') THEN '下肢全长'
        WHEN m.EXAM_SUB_CLASS = 'DR肩部' THEN '肩关节'
        WHEN m.EXAM_SUB_CLASS = '乳腺MR' THEN '乳腺'
        WHEN m.EXAM_SUB_CLASS = '心脏系列' THEN '心脏'
        WHEN m.EXAM_SUB_CLASS = 'CBCT' THEN '口腔/牙'
        WHEN m.EXAM_SUB_CLASS = '心电图' AND i.EXAM_ITEM LIKE '%24小时%' THEN '24小时动态心电图'
        WHEN m.EXAM_SUB_CLASS = '心电图' AND i.EXAM_ITEM LIKE '%48小时%' THEN '48小时动态心电图'
        WHEN m.EXAM_SUB_CLASS = '心电图' AND i.EXAM_ITEM LIKE '%72小时%' THEN '72小时动态心电图'
        WHEN m.EXAM_SUB_CLASS = '心电图' THEN '常规心电图'
        WHEN m.EXAM_SUB_CLASS = '脑电图' THEN '常规脑电图'
        WHEN m.EXAM_SUB_CLASS IN ('主观听力检查', '客观听力检查') THEN '内耳'
        WHEN m.EXAM_SUB_CLASS = '支气管镜' THEN '气管'
        WHEN m.EXAM_SUB_CLASS = '消化内镜' THEN '其他'
        WHEN m.EXAM_SUB_CLASS IN (
            '公共', '其他', 'CT其他', 'MR其他项目', '超声其他', '血管系列',
            'CT血管成像', 'MR血管成像', '数字化造影', '肺功能', '一氧化氮',
            '肌电图', '电生理检查', '动态血压监测', 'CT四肢', 'MR功能成像',
            'MR上肢', 'DR上肢', '浅表器官', '肌骨关节神经', '超声介入', '生殖系列'
        ) THEN '其他'
        ELSE '其他'
    END                                                        AS EXAM_POS_NAME,

    NULL                                                       AS INTER_BODY,
    NULL                                                       AS OPER_METHODE,
    NULL                                                       AS OPER_TIMES,
    NULL                                                       AS OPER_DATE,
    NULL                                                       AS ANAE_METHOD_CODE,
    NULL                                                       AS ANAE_METHOD_NAME,
    NULL                                                       AS ANAE_OBSERVATION,
    NULL                                                       AS ANAE_EASTWEST_FLAG,
    NULL                                                       AS ANAE_DOCTOR_CODE,
    NULL                                                       AS ANAE_DOCTOR_NAME,
    NULL                                                       AS TREAT_NOTE,
    NULL                                                       AS SAMPLE_TYPE,
    NULL                                                       AS SAMPLE_NUM,
    NULL                                                       AS SAMPLE_STATUS,
    NULL                                                       AS SAMPLE_FIXATIVE,
    NULL                                                       AS SAMPLE_TAKE_DATE,
    NULL                                                       AS SAMPLE_RECEIVE_DATE,

    SUBSTRB(
        TRIM(
            REGEXP_REPLACE(
                REPLACE(REPLACE(REPLACE(REPLACE(TO_CHAR(r.EXAM_PARA), '$nbsp$', ' '), CHR(38) || 'nbsp;', ' '), CHR(13), ' '), CHR(10), ' '),
                '[[:space:]]+',
                ' '
            )
        ),
        1,
        100
    )                                                          AS EXAM_METHOD,

    m.EXAM_CLASS                                               AS EXAM_TYPE,
    i.EXAM_ITEM_CODE                                           AS EXAM_CODE,
    i.EXAM_ITEM                                                AS EXAM_NAME,
    CAST(NULL AS VARCHAR2(10))                                  AS EXAM_RESULT_CODE,
    NULL                                                       AS EXAM_QUANT_RESULT,
    NULL                                                       AS EXAM_QUANT_UNIT,
    m.EXAM_DATE_TIME                                           AS EXAM_DATE,

    m.TECHNICIAN                                               AS EXAM_ENGINEER_CODE,
    m.TECHNICIAN                                               AS EXAM_ENGINEER_NAME,
    m.REPORTER                                                 AS EXAM_DOCTOR_CODE,
    SUBSTR(
        NVL(
            NULLIF(TRIM(TO_CHAR(r.REPORTER)), ''),
            NVL(NULLIF(TRIM(TO_CHAR(m.REPORTER)), ''), '-')
        ),
        1,
        50
    )                                                          AS EXAM_DOCTOR_NAME,

    m.EXAM_NO                                                  AS EXAM_REPORT_NUM,
    COALESCE(d_perf.QMPT_CODE, d_perf.DEPT_CODE)               AS EXAM_DEPT_CODE,
    COALESCE(d_perf.QMPT_NAME, d_perf.DEPT_NAME)               AS EXAM_DEPT_NAME,
    '49557032X'                                                AS EXAM_HOSPITAL_CODE,
    '山东省第二人民医院'                                       AS EXAM_HOSPITAL_NAME,

    SUBSTRB(
        COALESCE(
            NULLIF(TRIM(REGEXP_REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(TO_CHAR(r.IMPRESSION), '$nbsp$', ' '), CHR(38) || 'nbsp;', ' '), CHR(13), ' '), CHR(10), ' '), '[[:space:]]+', ' ')), ''),
            NULLIF(TRIM(REGEXP_REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(TO_CHAR(r.EXAM_PARA), '$nbsp$', ' '), CHR(38) || 'nbsp;', ' '), CHR(13), ' '), CHR(10), ' '), '[[:space:]]+', ' ')), ''),
            NULLIF(TRIM(REGEXP_REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(TO_CHAR(r.DESCRIPTION), '$nbsp$', ' '), CHR(38) || 'nbsp;', ' '), CHR(13), ' '), CHR(10), ' '), '[[:space:]]+', ' ')), ''),
            '-'
        ),
        1,
        4000
    )                                                          AS REPORT_OBJECTIVE,

    SUBSTRB(
        NULLIF(
            TRIM(
                REGEXP_REPLACE(
                    REPLACE(REPLACE(REPLACE(REPLACE(TO_CHAR(r.DESCRIPTION), '$nbsp$', ' '), CHR(38) || 'nbsp;', ' '), CHR(13), ' '), CHR(10), ' '),
                    '[[:space:]]+',
                    ' '
                )
            ),
            ''
        ),
        1,
        1000
    )                                                          AS REPORT_SUBJECTIVE,

    SUBSTR(
        REGEXP_REPLACE(
            REPLACE(
                REPLACE(
                    REPLACE(r.RECOMMENDATION, '$nbsp$', ' '),
                    CHR(38) || 'nbsp;',
                    ' '
                ),
                CHR(13),
                ' '
            ),
            '[[:space:]]+',
            ' '
        ),
        1,
        1000
    )                                                          AS REPORT_NOTE,

    COALESCE(
        r.REPORT_TIME,
        m.REPORT_DATE_TIME,
        m.AUDITING_DATE_TIME,
        m.EXAM_DATE_TIME,
        m.REQ_DATE_TIME
    )                                                          AS REPORT_DATE,

    NULL                                                       AS REPORT_DOCTOR_CODE,
    SUBSTR(
        NVL(
            NULLIF(TRIM(TO_CHAR(r.REPORTER)), ''),
            NVL(NULLIF(TRIM(TO_CHAR(m.REPORTER)), ''), '-')
        ),
        1,
        50
    )                                                          AS REPORT_DOCTOR_NAME,

    m.AUDITING_DATE_TIME                                       AS AUDIT_DATE,
    NULL                                                       AS AUDIT_DOCTOR_CODE,
    SUBSTR(
        NVL(
            NULLIF(TRIM(TO_CHAR(r.REPORTER)), ''),
            NVL(NULLIF(TRIM(TO_CHAR(m.REPORTER)), ''), '-')
        ),
        1,
        50
    )                                                          AS AUDIT_DOCTOR_NAME,

    NULL                                                       AS SECRECT_CLASS,
    m.DEVICE                                                   AS IMAGE_DEVICE,

    SUBSTRB(
        COALESCE(
            NULLIF(TRIM(REGEXP_REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(TO_CHAR(r.IMPRESSION), '$nbsp$', ' '), CHR(38) || 'nbsp;', ' '), CHR(13), ' '), CHR(10), ' '), '[[:space:]]+', ' ')), ''),
            NULLIF(TRIM(REGEXP_REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(TO_CHAR(r.EXAM_PARA), '$nbsp$', ' '), CHR(38) || 'nbsp;', ' '), CHR(13), ' '), CHR(10), ' '), '[[:space:]]+', ' ')), ''),
            NULLIF(TRIM(REGEXP_REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(TO_CHAR(r.DESCRIPTION), '$nbsp$', ' '), CHR(38) || 'nbsp;', ' '), CHR(13), ' '), CHR(10), ' '), '[[:space:]]+', ' ')), ''),
            '-'
        ),
        1,
        2000
    )                                                          AS IMAGE_RESULTS,

    SUBSTRB(
        COALESCE(
            NULLIF(TRIM(REGEXP_REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(TO_CHAR(r.DESCRIPTION), '$nbsp$', ' '), CHR(38) || 'nbsp;', ' '), CHR(13), ' '), CHR(10), ' '), '[[:space:]]+', ' ')), ''),
            NULLIF(TRIM(REGEXP_REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(TO_CHAR(r.IMPRESSION), '$nbsp$', ' '), CHR(38) || 'nbsp;', ' '), CHR(13), ' '), CHR(10), ' '), '[[:space:]]+', ' ')), ''),
            '-'
        ),
        1,
        2000
    )                                                          AS DIAGNOSIS_IDEA,

    NULL                                                       AS DIAGNOSIS_TREAT_NO,
    NULL                                                       AS CARD_TYPE,
    NULL                                                       AS CITIZEN_ID,
    NULL                                                       AS EFFECTIVE_TIME,
    NULL                                                       AS STATUS,
    NULL                                                       AS CREATED_AT,

    '370104'                                                   AS DISTRICT_CODE,
    'INSERT'                                                   AS EXCHANGE_TYPE,
    NULL                                                       AS DEI,
    NULL                                                       AS NODE_CODE,

    i.EXAM_ITEM_CODE                                           AS LOCAL_EXAM_CODE,
    i.EXAM_ITEM                                                AS LOCAL_EXAM_NAME,
    CAST(SYSTIMESTAMP AS TIMESTAMP)                            AS SYSTEM_TIME,

    CASE
        WHEN m.SRC_TYPE_FOR_JOIN = 'O' THEN '1'
        WHEN m.SRC_TYPE_FOR_JOIN = 'I' THEN '3'
        ELSE NULL
    END                                                        AS SOURCE_CODE,

    NULL                                                       AS CZRK_ID,
    NULL                                                       AS EXAM_RESULT_NOTE,
    NULL                                                       AS IMAGE_DEVICE_CODE,
    NULL                                                       AS CHECKER_ID_NUM,
    NULL                                                       AS REPORT_DOCTOR_ID_NUM,
    NULL                                                       AS PRINT_TIME,
    NULL                                                       AS PRINT_PERSON,
    NULL                                                       AS BARCODE_NO,

    COALESCE(
        CASE WHEN a.SCHEDULED_DATE >= DATE '1900-01-01' THEN a.SCHEDULED_DATE END,
        CASE WHEN m.SCHEDULED_DATE_TIME >= DATE '1900-01-01' THEN m.SCHEDULED_DATE_TIME END,
        m.REQ_DATE_TIME,
        m.EXAM_DATE_TIME
    )                                                          AS APPLY_APPOINTMENT_DATE,

    NVL(em.EXAM_TYPE_CODE, '-')                                AS EXAM_TYPE_CODE,
    NVL(em.EXAM_TYPE_NAME, '-')                                AS EXAM_TYPE_NAME,
    i.EXAM_ITEM                                                AS HOS_EXAM_TYPE_NAME,
    i.EXAM_ITEM_CODE                                           AS HOS_EXAM_TYPE_CODE,

    SUBSTR(
        NVL(
            NULLIF(TRIM(TO_CHAR(i.ORDER_ID)), ''),
            TO_CHAR(m.EXAM_NO) || '|' || NVL(TO_CHAR(i.EXAM_ITEM_NO), TO_CHAR(i.EXAM_ITEM_CODE))
        ),
        1,
        100
    )                                                          AS ORDER_ID,

    NULL                                                       AS REPORT_LINK,

    CASE
        WHEN cim.HIS_ITEM_CODE IS NOT NULL THEN '1'
        ELSE '0'
    END                                                        AS MTU_REC_MARK,

    NULL                                                       AS MTU_REC_LIMIT_MARK,
    cim.SPT_ITEM_NAME                                          AS PROJECT_NAME,
    cim.SPT_ITEM_CODE                                          AS PROJECT_CODE

FROM
(
    SELECT
        m0.*,
        TO_CHAR(m0.PATIENT_ID) AS PATIENT_ID_C,
        TO_CHAR(m0.VISIT_ID)   AS VISIT_ID_C,
        TO_CHAR(m0.RCPT_NO)    AS RCPT_NO_C,
        CASE
            WHEN TO_CHAR(m0.PATIENT_SOURCE) = '1' THEN 'O'
            WHEN TO_CHAR(m0.PATIENT_SOURCE) = '2' THEN 'I'

            WHEN m0.PATIENT_SOURCE IS NULL
             AND REGEXP_LIKE(TRIM(TO_CHAR(m0.VISIT_ID)), '^[0-9]+$')
             AND REGEXP_REPLACE(TRIM(TO_CHAR(m0.VISIT_ID)), '0', '') IS NULL
            THEN 'O'

            WHEN m0.PATIENT_SOURCE IS NULL
             AND REGEXP_LIKE(TRIM(TO_CHAR(m0.VISIT_ID)), '^[0-9]+$')
             AND REGEXP_REPLACE(TRIM(TO_CHAR(m0.VISIT_ID)), '0', '') IS NOT NULL
            THEN 'I'

            ELSE 'X'
        END AS SRC_TYPE_FOR_JOIN
    FROM EXAM.EXAM_MASTER m0
) m

INNER JOIN EXAM.EXAM_ITEMS i
    ON i.EXAM_NO = m.EXAM_NO

INNER JOIN EXAM.EXAM_REPORT r
    ON r.EXAM_NO = m.EXAM_NO

LEFT JOIN EXAM.EXAM_APPOINTS a
    ON a.EXAM_NO = m.EXAM_NO

LEFT JOIN PAT_MASTER_INDEX p
    ON p.PATIENT_ID = m.PATIENT_ID

LEFT JOIN DEPT_DICT d_req
    ON d_req.DEPT_CODE = m.REQ_DEPT

LEFT JOIN DEPT_DICT d_perf
    ON d_perf.DEPT_CODE = m.PERFORMED_BY

LEFT JOIN
(
    SELECT
        TO_CHAR(a.PATIENT_ID) AS PATIENT_ID,
        TO_CHAR(a.VISIT_ID)   AS VISIT_ID,
        MIN(a.DISCHARGE_DATE_TIME) AS VISIT_DATE_TIME
    FROM PAT_VISIT a
    WHERE a.DISCHARGE_DATE_TIME >= DATE '2021-01-01'
      AND a.DISCHARGE_DATE_TIME <  DATE '2025-01-01'
    GROUP BY
        TO_CHAR(a.PATIENT_ID),
        TO_CHAR(a.VISIT_ID)
) e_i
    ON m.SRC_TYPE_FOR_JOIN = 'I'
   AND e_i.PATIENT_ID = m.PATIENT_ID_C
   AND e_i.VISIT_ID   = m.VISIT_ID_C

/* 门诊新口径：OUTP_TREAT_REC.APPOINT_NO = EXAM_NO，优先使用 */
LEFT JOIN
(
    SELECT
        TO_CHAR(a.APPOINT_NO) AS APPOINT_NO,
        TO_CHAR(b.PATIENT_ID) AS PATIENT_ID,
        TO_CHAR(b.CLINIC_NO)  AS VISIT_ID,
        b.CLINIC_NO,
        b.VISIT_DATE AS VISIT_DATE_TIME,
        MIN(b.VISIT_NO) AS VISIT_NO
    FROM OUTP_TREAT_REC a
    INNER JOIN CLINIC_MASTER b
            ON a.VISIT_DATE = b.VISIT_DATE
           AND a.VISIT_NO   = b.VISIT_NO
    WHERE a.ITEM_CLASS = 'D'
      AND a.CHARGE_INDICATOR = '1'
      AND a.APPOINT_NO IS NOT NULL
      AND b.VISIT_DATE >= TO_DATE('2022-10-31', 'yyyy-mm-dd')
      AND b.VISIT_DATE <  DATE '2025-01-01'
    GROUP BY
        TO_CHAR(a.APPOINT_NO),
        TO_CHAR(b.PATIENT_ID),
        TO_CHAR(b.CLINIC_NO),
        b.CLINIC_NO,
        b.VISIT_DATE
) e_appt
    ON m.SRC_TYPE_FOR_JOIN = 'O'
   AND e_appt.APPOINT_NO = TO_CHAR(m.EXAM_NO)
   AND e_appt.PATIENT_ID = m.PATIENT_ID_C

/* 门诊旧口径：OUTP_ORDER_DESC 按 PATIENT_ID + RCPT_NO，作为第二顺位补充 */
LEFT JOIN
(
    SELECT
        TO_CHAR(a.PATIENT_ID) AS PATIENT_ID,
        TO_CHAR(a.RCPT_NO)    AS RCPT_NO,
        MIN(TO_CHAR(a.CLINIC_NO)) AS VISIT_ID,
        MIN(a.VISIT_DATE) AS VISIT_DATE_TIME
    FROM OUTP_ORDER_DESC a
    WHERE a.VISIT_DATE >= DATE '2021-01-01'
      AND a.VISIT_DATE <  DATE '2025-01-01'
      AND a.RCPT_NO IS NOT NULL
    GROUP BY
        TO_CHAR(a.PATIENT_ID),
        TO_CHAR(a.RCPT_NO)
) e_rcpt
    ON m.SRC_TYPE_FOR_JOIN = 'O'
   AND e_rcpt.PATIENT_ID = m.PATIENT_ID_C
   AND e_rcpt.RCPT_NO    = m.RCPT_NO_C

/* 门诊兜底口径：OUTP_ORDER_DESC 按 PATIENT_ID + CLINIC_NO */
LEFT JOIN
(
    SELECT
        TO_CHAR(a.PATIENT_ID) AS PATIENT_ID,
        TO_CHAR(a.CLINIC_NO)  AS VISIT_ID,
        MIN(a.VISIT_DATE) AS VISIT_DATE_TIME
    FROM OUTP_ORDER_DESC a
    WHERE a.VISIT_DATE >= DATE '2021-01-01'
      AND a.VISIT_DATE <  DATE '2025-01-01'
    GROUP BY
        TO_CHAR(a.PATIENT_ID),
        TO_CHAR(a.CLINIC_NO)
) e_ov
    ON m.SRC_TYPE_FOR_JOIN = 'O'
   AND e_ov.PATIENT_ID = m.PATIENT_ID_C
   AND e_ov.VISIT_ID   = m.VISIT_ID_C

LEFT JOIN
(
    SELECT EMPLNAME, IDENNO
    FROM
    (
        SELECT
            EMPLNAME,
            IDENNO,
            ROW_NUMBER() OVER (
                PARTITION BY EMPLNAME
                ORDER BY ROWID
            ) AS RN
        FROM SYS_EMPLOYEE
    )
    WHERE RN = 1
) usr
    ON usr.EMPLNAME = m.REQ_PHYSICIAN

LEFT JOIN
(
    SELECT
        HOS_EXAM_TYPE_CODE,
        EXAM_TYPE_CODE,
        EXAM_TYPE_NAME
    FROM
    (
        SELECT
            HOS_EXAM_TYPE_CODE,
            EXAM_TYPE_CODE,
            EXAM_TYPE_NAME,
            ROW_NUMBER() OVER (
                PARTITION BY HOS_EXAM_TYPE_CODE
                ORDER BY EXAM_TYPE_CODE, EXAM_TYPE_NAME, ROWID
            ) AS RN
        FROM D07_EXAM_ITEM_MAP
    )
    WHERE RN = 1
) em
    ON em.HOS_EXAM_TYPE_CODE = i.EXAM_ITEM_CODE

LEFT JOIN
(
    SELECT
        HIS_ITEM_CODE,
        SPT_ITEM_CODE,
        SPT_ITEM_NAME
    FROM
    (
        SELECT
            HIS_ITEM_CODE,
            SPT_ITEM_CODE,
            SPT_ITEM_NAME,
            ROW_NUMBER() OVER (
                PARTITION BY HIS_ITEM_CODE
                ORDER BY SPT_ITEM_CODE, SPT_ITEM_NAME, ROWID
            ) AS RN
        FROM CLINIC_ITEM_MAPPING
    )
    WHERE RN = 1
) cim
    ON cim.HIS_ITEM_CODE = i.EXAM_ITEM_CODE

WHERE
    (
        m.SRC_TYPE_FOR_JOIN = 'I'
        AND e_i.PATIENT_ID IS NOT NULL
    )
    OR
    (
        m.SRC_TYPE_FOR_JOIN = 'O'
        AND (
               e_appt.PATIENT_ID IS NOT NULL
            OR e_rcpt.PATIENT_ID IS NOT NULL
            OR e_ov.PATIENT_ID IS NOT NULL
        )
    )
