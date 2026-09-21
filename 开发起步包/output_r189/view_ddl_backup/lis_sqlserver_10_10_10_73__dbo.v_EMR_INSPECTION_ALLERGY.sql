CREATE VIEW [dbo].[v_EMR_INSPECTION_ALLERGY] AS
SELECT
    /* 子表内码：主表ID + 药敏项目关键字段生成稳定短ID */
    CAST(
        LEFT(
            '49557032X_ALLERGY_' +
            CONVERT(
                varchar(32),
                HASHBYTES(
                    'MD5',
                    ISNULL(ids.REPORT_ID, '') + '|' +
                    ISNULL(CONVERT(varchar(64), b.rpt_itemcode), '') + '|' +
                    ISNULL(CONVERT(varchar(64), c.seq), '') + '|' +
                    ISNULL(CONVERT(varchar(64), c.medcode), '') + '|' +
                    ISNULL(CONVERT(varchar(64), c.result_flag), '') + '|' +
                    ISNULL(CONVERT(varchar(100), c.mic), '') + '|' +
                    ISNULL(CONVERT(varchar(100), c.rad), '')
                ),
                2
            ),
            100
        ) AS varchar(100)
    ) AS ID, -- 内码 VARCHAR2(100) 是 主键

    CAST(ids.REPORT_ID AS varchar(100)) AS REPORT_ID, -- 检验报告单内码 VARCHAR2(100) 是 主表存在

    CAST(
        LEFT(
            COALESCE(
                NULLIF(LTRIM(RTRIM(e.his_recordid)), ''),
                NULLIF(LTRIM(RTRIM(a.barcode)), ''),
                REPLACE(CONVERT(varchar(50), a.reportid), '-', '')
            ),
            20
        ) AS varchar(20)
    ) AS APPLY_NUM, -- 电子申请单编号 VARCHAR2(20) 是

    CAST('49557032X' AS varchar(32)) AS ORG_CODE, -- 医院组织机构代码
    CAST('山东省第二人民医院' AS varchar(70)) AS ORG_NAME, -- 医院名称

    CAST(
        LEFT(
            COALESCE(
                NULLIF(CONVERT(varchar(32), c.seq), ''),
                NULLIF(CONVERT(varchar(32), c.medcode), ''),
                '1'
            ),
            32
        ) AS varchar(32)
    ) AS ITEM_ID, -- 项目序号 VARCHAR2(32) 是

    /* 药敏结果代码：CC99.00093 */
    CAST(
        CASE UPPER(LTRIM(RTRIM(CONVERT(varchar(32), c.result_flag))))
            WHEN 'R'   THEN '1'   -- 耐药
            WHEN 'S'   THEN '2'   -- 敏感
            WHEN 'I'   THEN '5'   -- 中介
            WHEN 'NS'  THEN '6'   -- 非敏感
            WHEN 'WT'  THEN '7'   -- 野生型
            WHEN 'NWT' THEN '8'   -- 非野生型
            WHEN 'SDD' THEN '10'  -- 剂量依赖性敏感
            WHEN 'N'   THEN '9'   -- 无判定标准
            WHEN '9'   THEN '9'   -- 无判定标准
            WHEN '+'   THEN '9'   -- 无判定标准，原始值保留到描述
            WHEN '-'   THEN '9'   -- 无判定标准，原始值保留到描述
            ELSE '9'
        END AS varchar(32)
    ) AS DRUG_ALLERGY_CODE, -- 药敏结果代码 VARCHAR2(32) CC99.00093 是

    /* 药敏结果名称 */
    CAST(
        CASE UPPER(LTRIM(RTRIM(CONVERT(varchar(32), c.result_flag))))
            WHEN 'R'   THEN '耐药'
            WHEN 'S'   THEN '敏感'
            WHEN 'I'   THEN '中介'
            WHEN 'NS'  THEN '非敏感'
            WHEN 'WT'  THEN '野生型'
            WHEN 'NWT' THEN '非野生型'
            WHEN 'SDD' THEN '剂量依赖性敏感'
            WHEN 'N'   THEN '无判定标准'
            WHEN '9'   THEN '无判定标准'
            WHEN '+'   THEN '无判定标准'
            WHEN '-'   THEN '无判定标准'
            ELSE '无判定标准'
        END AS varchar(100)
    ) AS DRUG_ALLERGY_NAME, -- 药敏结果名称 VARCHAR2(100) 是

    /* 药敏结果描述：保留 LIS 原始结果，便于追溯 */
    CAST(
        LEFT(
            '原始药敏结果代码=' +
            COALESCE(
                NULLIF(LTRIM(RTRIM(CONVERT(varchar(32), c.result_flag))), ''),
                '未知'
            ) +
            '；原始药敏结果名称=' +
            COALESCE(
                NULLIF(LTRIM(RTRIM(CONVERT(varchar(100), c.medresult))), ''),
                '未知'
            ),
            1000
        ) AS varchar(1000)
    ) AS DRUG_ALLERGY_NOTE, -- 药敏结果描述 VARCHAR2(1000)

    CAST(NULL AS varchar(100)) AS PIECE_DRUG, -- 纸片含药量 VARCHAR2(100)

    CAST(
        LEFT(
            NULLIF(LTRIM(RTRIM(CONVERT(varchar(100), c.mic))), ''),
            100
        ) AS varchar(100)
    ) AS BACSTA_CONCEN, -- 最小抑菌浓度 MIC VARCHAR2(100)

    CAST(
        LEFT(
            NULLIF(LTRIM(RTRIM(CONVERT(varchar(100), c.rad))), ''),
            100
        ) AS varchar(100)
    ) AS BACSTA_DIAMETER, -- 抑菌圈直径 VARCHAR2(100)

    /*
      抗生素等级：原 SQL 固定为 1。
      当前未看到 lab_resultmed / lab_med 中有明确等级字段，暂保留原口径。
    */
    CAST('1' AS varchar(100)) AS ANTIBIOTIC_CLASS, -- 抗生素等级 VARCHAR2(100) 是

    CAST(
        LEFT(
            NULLIF(LTRIM(RTRIM(CONVERT(varchar(32), c.medcode))), ''),
            32
        ) AS varchar(32)
    ) AS ANTIBIOTIC_CODE, -- 抗生素代码 VARCHAR2(32)

    CAST(
        LEFT(
            COALESCE(
                NULLIF(LTRIM(RTRIM(CONVERT(varchar(100), d.medname))), ''),
                NULLIF(LTRIM(RTRIM(CONVERT(varchar(100), c.medcode))), ''),
                '未知'
            ),
            100
        ) AS varchar(100)
    ) AS ANTIBIOTIC_NAME, -- 抗生素名称 VARCHAR2(100) 是

    CAST(a.rechk_dt AS datetime) AS EFFECTIVE_TIME, -- 活动发生时间 DATE

    CAST(NULL AS varchar(32)) AS STATUS, -- 卡片状态
    CAST(NULL AS datetime) AS CREATED_AT, -- 创建时间

    CAST('370104' AS varchar(6)) AS DISTRICT_CODE, -- 所属行政区划
    CAST('INSERT' AS varchar(10)) AS EXCHANGE_TYPE, -- 交换类型
    GETDATE() AS SYSTEM_TIME -- 数据上传时间戳

FROM lab_report a WITH (NOLOCK)

INNER JOIN req_master rm WITH (NOLOCK)
    ON a.barcode = rm.barcode

INNER JOIN req_detail e WITH (NOLOCK)
    ON e.barcode = a.barcode
   AND (
          e.reportid = a.reportid
          OR (
                NULLIF(LTRIM(RTRIM(CONVERT(varchar(50), e.reportid))), '') IS NULL
                AND EXISTS (
                    SELECT 1
                    FROM lab_result m WITH (NOLOCK)
                    WHERE m.reportid = a.reportid
                      AND m.req_itemcode = e.req_itemcode
                )
             )
       )

INNER JOIN lab_result b WITH (NOLOCK)
    ON b.reportid = a.reportid
   AND b.req_itemcode = e.req_itemcode

INNER JOIN lab_resultmed c WITH (NOLOCK)
    ON c.reportid = b.reportid
   AND c.rpt_itemcode = b.rpt_itemcode

LEFT JOIN lab_med d WITH (NOLOCK)
    ON d.medcode = c.medcode

CROSS APPLY (
    SELECT
        CAST(
            LEFT(
                '49557032X' + '_' +
                ISNULL(CONVERT(varchar(50), a.reportid), '') + '_' +
                ISNULL(CONVERT(varchar(64), e.req_itemcode), '') + '_' +
                ISNULL(CONVERT(varchar(20), e.seq), ''),
                100
            ) AS varchar(100)
        ) AS REPORT_ID
) ids

WHERE a.rptunitid <> 50
  AND NULLIF(LTRIM(RTRIM(a.barcode)), '') IS NOT NULL
  AND NULLIF(LTRIM(RTRIM(a.pat_name)), '') IS NOT NULL
  AND NULLIF(LTRIM(RTRIM(a.pat_sex)), '') IS NOT NULL
  AND NULLIF(LTRIM(RTRIM(a.specimen_name)), '') IS NOT NULL
  AND a.rechk_dt IS NOT NULL
  AND a.rechk_dt >= '20210101'
  AND a.rechk_dt <  '20250101'
  AND EXISTS (
      SELECT 1
      FROM lab_result m WITH (NOLOCK)
      WHERE m.reportid = a.reportid
        AND m.req_itemcode = e.req_itemcode
  )
  AND NULLIF(LTRIM(RTRIM(CONVERT(varchar(32), c.medcode))), '') IS NOT NULL
  AND a.pat_name NOT LIKE '%测试%'
