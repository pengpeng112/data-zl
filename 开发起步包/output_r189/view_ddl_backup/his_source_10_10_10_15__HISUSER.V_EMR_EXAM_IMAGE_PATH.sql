SELECT
    SUBSTRB(q.IMAGE_ID || '|P' || LPAD(q.PATH_SEQ, 3, '0'), 1, 100) AS ID,              -- 内码，子表主键
    SUBSTRB(TO_CHAR(q.APPLY_NUM), 1, 20)                             AS APPLY_NUM,       -- 电子申请单编号
    q.IMAGE_ID                                                        AS IMAGE_ID,        -- 影像报告单内码，对应主表 V_EMR_EXAM_IMAGE_REP.ID
    q.ORG_CODE                                                        AS ORG_CODE,
    q.ORG_NAME                                                        AS ORG_NAME,
    SUBSTRB(TO_CHAR(q.REPORT_NUM), 1, 20)                             AS REPORT_NUM,
    q.IMAGE_SAVE_PATH                                                 AS IMAGE_SAVE_PATH,
    q.EFFECTIVE_TIME                                                  AS EFFECTIVE_TIME,
    q.STATUS                                                          AS STATUS,
    q.CREATED_AT                                                      AS CREATED_AT,
    q.DISTRICT_CODE                                                   AS DISTRICT_CODE,
    q.EXCHANGE_TYPE                                                   AS EXCHANGE_TYPE,
    CAST(SYSTIMESTAMP AS TIMESTAMP)                                   AS SYSTEM_TIME
FROM
(
    SELECT
        p.ID                                                          AS IMAGE_ID,
        p.APPLY_NUM                                                   AS APPLY_NUM,
        p.ORG_CODE                                                    AS ORG_CODE,
        p.ORG_NAME                                                    AS ORG_NAME,
        p.REPORT_NUM                                                  AS REPORT_NUM,
        rp.IMAGE_SAVE_PATH                                            AS IMAGE_SAVE_PATH,

        COALESCE(
            p.REPORT_DATE,
            p.EXAM_DATE,
            p.APPLY_DATE,
            p.APPLY_APPOINTMENT_DATE
        )                                                             AS EFFECTIVE_TIME,

        CAST(NULL AS VARCHAR2(32))                                    AS STATUS,
        CAST(NULL AS TIMESTAMP)                                       AS CREATED_AT,
        p.DISTRICT_CODE                                               AS DISTRICT_CODE,
        p.EXCHANGE_TYPE                                               AS EXCHANGE_TYPE,

        ROW_NUMBER() OVER (
            PARTITION BY p.ID
            ORDER BY rp.IMAGE_SAVE_PATH
        )                                                             AS PATH_SEQ

    FROM V_EMR_EXAM_IMAGE_REP p

    INNER JOIN
    (
        SELECT
            x.EXAM_NO_C,
            x.IMAGE_SAVE_PATH
        FROM
        (
            SELECT
                TO_CHAR(r.EXAM_NO) AS EXAM_NO_C,

                SUBSTRB(
                    TRIM(
                        REGEXP_REPLACE(
                            REPLACE(
                                REPLACE(
                                    REPLACE(
                                        REPLACE(TO_CHAR(r.USE_IMAGE), '$nbsp$', ''),
                                        CHR(38) || 'nbsp;',
                                        ''
                                    ),
                                    CHR(13),
                                    ''
                                ),
                                CHR(10),
                                ''
                            ),
                            '[[:space:]]+',
                            ''
                        )
                    ),
                    1,
                    512
                ) AS IMAGE_SAVE_PATH
            FROM EXAM.EXAM_REPORT r
            WHERE r.USE_IMAGE IS NOT NULL
        ) x
        WHERE x.IMAGE_SAVE_PATH IS NOT NULL
          AND LENGTH(TRIM(x.IMAGE_SAVE_PATH)) > 0
        GROUP BY
            x.EXAM_NO_C,
            x.IMAGE_SAVE_PATH
    ) rp
        ON rp.EXAM_NO_C = TO_CHAR(p.REPORT_NUM)
) q
