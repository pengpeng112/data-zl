CREATE VIEW [dbo].[V_EMR_INSPECTION_IMAGE] AS
SELECT
    /* 子表内码：主表ID + 图片序号 */
CAST(
    LEFT(
        '49557032X_IMG_' +
        CONVERT(
            varchar(32),
            HASHBYTES(
                'MD5',
                ISNULL(ids.REPORT_ID, '') + '|' +
                ISNULL(LTRIM(RTRIM(img.graphitemno)), '') + '|' +
                ISNULL(CONVERT(varchar(20), img.seq), '0')
            ),
            2
        ),
        100
    ) AS varchar(100)
) AS ID,

    /* 检验报告单内码：必须与主表 v_EMR_INSPECTION.ID 一致 */
    CAST(ids.REPORT_ID AS varchar(100)) AS REPORT_ID,

    /* 电子申请单编号：与主表 APPLY_NUM 口径保持一致 */
    CAST(
        LEFT(
            ISNULL(
                NULLIF(LTRIM(RTRIM(rd.his_recordid)), ''),
                a.barcode
            ),
            20
        ) AS varchar(20)
    ) AS APPLY_NUM,

    CAST('49557032X' AS varchar(32)) AS ORG_CODE,
    CAST('山东省第二人民医院' AS varchar(70)) AS ORG_NAME,

    CAST(img.seq AS bigint) AS IMAGE_NUM,

    /*
      注意：
      Img_Lab_Graph.graph_image 是 image 二进制图片内容，不是路径。
      graph_data / extrainfo 当前样例为空，暂时无真实路径。
      这里先输出可追溯图片标识，保证字段类型为 varchar(80)。
    */
   CAST(
    LEFT(
        'LAB_GRAPH_' +
        CONVERT(
            varchar(32),
            HASHBYTES(
                'MD5',
                ISNULL(ids.REPORT_ID, '') + '|' +
                ISNULL(LTRIM(RTRIM(img.graphitemno)), '') + '|' +
                ISNULL(CONVERT(varchar(20), img.seq), '0')
            ),
            2
        ) +
        CASE
            WHEN NULLIF(LTRIM(RTRIM(img.fileext)), '') IS NOT NULL
                THEN '.' + REPLACE(REPLACE(LTRIM(RTRIM(img.fileext)), '.', ''), ' ', '')
            ELSE ''
        END,
        80
    ) AS varchar(80)
) AS IMAGE_SAVE_PATH,

    COALESCE(
        TRY_CONVERT(datetime, a.Report_DT),
        TRY_CONVERT(datetime, a.report_dt),
        TRY_CONVERT(datetime, a.rechk_dt)
    ) AS EFFECTIVE_TIME,

    CAST(NULL AS varchar(32)) AS STATUS,
    CAST(NULL AS datetime) AS CREATED_AT,

    CAST('370104' AS varchar(6)) AS DISTRICT_CODE,
    CAST('INSERT' AS varchar(10)) AS EXCHANGE_TYPE,
    GETDATE() AS SYSTEM_TIME

FROM lab_report a WITH (NOLOCK)

INNER JOIN req_master rm WITH (NOLOCK)
    ON a.barcode = rm.barcode

INNER JOIN req_detail rd WITH (NOLOCK)
    ON rd.barcode = a.barcode
   AND (
          rd.reportid = a.reportid
          OR (
                NULLIF(LTRIM(RTRIM(CONVERT(varchar(50), rd.reportid))), '') IS NULL
                AND EXISTS (
                    SELECT 1
                    FROM lab_result m WITH (NOLOCK)
                    WHERE m.reportid = a.reportid
                      AND m.req_itemcode = rd.req_itemcode
                )
             )
       )

INNER JOIN Img_Lab_Graph img WITH (NOLOCK)
    ON img.reportid = a.reportid

CROSS APPLY (
    SELECT
        CAST(
            LEFT(
                '49557032X' + '_' +
                ISNULL(CONVERT(varchar(50), a.reportid), '') + '_' +
                ISNULL(CONVERT(varchar(64), rd.req_itemcode), '') + '_' +
                ISNULL(CONVERT(varchar(20), rd.seq), ''),
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
        AND m.req_itemcode = rd.req_itemcode
  )
  AND img.graph_image IS NOT NULL
  AND DATALENGTH(CAST(img.graph_image AS varbinary(max))) > 0
  AND a.pat_name NOT LIKE '%测试%'
