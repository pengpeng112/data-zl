CREATE VIEW [dbo].[v_EMR_INSPECTION_ITEM] AS
SELECT
    /* 内码：主表REPORT_ID + 检验结果本地项目编码，生成稳定短ID */
    CAST(
        LEFT(
            '49557032X_ITEM_' +
            CONVERT(
                varchar(32),
                HASHBYTES(
                    'MD5',
                    ISNULL(ids.REPORT_ID, '') + '|' +
                    ISNULL(CONVERT(varchar(64), b.rpt_itemcode), '') + '|' +
                    ISNULL(CONVERT(varchar(100), b.result_str), '') + '|' +
                    ISNULL(CONVERT(varchar(100), b.result_unit), '')
                ),
                2
            ),
            100
        ) AS varchar(100)
    ) AS ID, -- 内码 VARCHAR2(100) 是 主键

    CAST(ids.REPORT_ID AS varchar(100)) AS REPORT_ID, -- 检验报告单内码 VARCHAR2(100) 是 必填、关联报告单主表

    CAST(
        LEFT(
            COALESCE(
                NULLIF(LTRIM(RTRIM(rd.his_recordid)), ''),
                NULLIF(LTRIM(RTRIM(a.barcode)), ''),
                REPLACE(CONVERT(varchar(50), a.reportid), '-', '')
            ),
            20
        ) AS varchar(20)
    ) AS APPLY_NUM, -- 电子申请单编号 VARCHAR2(20) 是

    CAST(rd.seq AS numeric(18,0)) AS SN, -- 序号 NUMBER

    /* 检验项目代号：itemnote1 -> 对照表 -> 院内编码 */
    CAST(
        LEFT(
            COALESCE(
                NULLIF(LTRIM(RTRIM(CONVERT(varchar(100), c.itemnote1))), ''),
                NULLIF(LTRIM(RTRIM(imap.CS_ITEM_CODE)), ''),
                loc.LOCAL_ITEM_CODE,
                '9999'
            ),
            20
        ) AS varchar(20)
    ) AS ITEM_CODE, -- 检验项目代号 VARCHAR2(20) CS_EXAMINE_ITEM 是

    COALESCE(
        TRY_CONVERT(datetime, a.Recieve_dt),
        TRY_CONVERT(datetime, rm.recieve_dt),
        TRY_CONVERT(datetime, a.report_dt),
        TRY_CONVERT(datetime, a.rechk_dt)
    ) AS RECIEVE_DT, -- 检验科接收时间 DATE

    /* 检验项目名称：itemnote2 -> 对照表 -> 院内名称 */
    CAST(
        LEFT(
            COALESCE(
                NULLIF(LTRIM(RTRIM(CONVERT(varchar(200), c.itemnote2))), ''),
                NULLIF(LTRIM(RTRIM(imap.CS_ITEM_NAME)), ''),
                loc.LOCAL_ITEM_NAME,
                '未知检验项目'
            ),
            80
        ) AS varchar(80)
    ) AS ITEM_NAME, -- 检验项目名称 VARCHAR2(80) 是

    CAST(
        CASE
            WHEN c.resulttype = '1' THEN '2'
            WHEN TRY_CONVERT(decimal(18,4), NULLIF(LTRIM(RTRIM(b.result_str)), '')) IS NOT NULL THEN '2'
            ELSE '1'
        END AS varchar(32)
    ) AS RESULT_TYPE, -- 结果类型代码 VARCHAR2(32) 是 1文本 2数值

    CAST(
        CASE
            WHEN c.resulttype = '1' THEN '数值'
            WHEN TRY_CONVERT(decimal(18,4), NULLIF(LTRIM(RTRIM(b.result_str)), '')) IS NOT NULL THEN '数值'
            ELSE '文本'
        END AS varchar(100)
    ) AS RESULT_TYPE_NOTE, -- 结果类型描述 VARCHAR2(100) 是

    CAST(
        LEFT(loc.ITEM_RESULT_SRC, 100) AS varchar(100)
    ) AS ITEM_RESULT, -- 检验项目结果 VARCHAR2(100) 是

    CAST(
        LEFT(
            COALESCE(
                NULLIF(LTRIM(RTRIM(b.result_unit)), ''),
                '-'
            ),
            20
        ) AS varchar(20)
    ) AS UNIT, -- 单位 VARCHAR2(20) 是

    CAST(
        ISNULL(
            TRY_CONVERT(decimal(12,2), NULLIF(LTRIM(RTRIM(CONVERT(varchar(40), b.Result_refl))), '')),
            0
        ) AS decimal(12,2)
    ) AS REFER_VALUE_LOWER, -- 正常参考值下限 NUMBER(12,2) 是

    CAST(
        ISNULL(
            TRY_CONVERT(decimal(12,2), NULLIF(LTRIM(RTRIM(CONVERT(varchar(40), b.Result_refh))), '')),
            0
        ) AS decimal(12,2)
    ) AS REFER_VALUE_UPPER, -- 正常参考值上限 NUMBER(12,2) 是

    CAST(NULL AS decimal(12,2)) AS CRITICAL_VALUE, -- 危急值 NUMBER(12,2)

    CAST(NULL AS varchar(20)) AS ALARM_STATE, -- 通知状态

    CAST(NULL AS datetime) AS CALL_DATE, -- 通知日期

    CAST(NULL AS varchar(100)) AS ATTACHED_RESULT, -- 附属结果

    CAST(
        CASE
            WHEN UPPER(LTRIM(RTRIM(ISNULL(b.result_flag, '')))) IN ('H','HH','↑','HIGH') THEN '2'
            WHEN UPPER(LTRIM(RTRIM(ISNULL(b.result_flag, '')))) IN ('L','LL','↓','LOW') THEN '2'
            WHEN NULLIF(LTRIM(RTRIM(ISNULL(b.result_flag, ''))), '') IS NULL THEN '1'
            ELSE '3'
        END AS varchar(32)
    ) AS RESULT_EXPLAIN, -- 结果值的解释 VARCHAR2(32) 是

    CAST(
        LEFT(
            CASE
                WHEN UPPER(LTRIM(RTRIM(ISNULL(b.result_flag, '')))) IN ('H','HH','↑','HIGH') THEN '偏高'
                WHEN UPPER(LTRIM(RTRIM(ISNULL(b.result_flag, '')))) IN ('L','LL','↓','LOW') THEN '偏低'
                WHEN NULLIF(LTRIM(RTRIM(ISNULL(b.result_flag, ''))), '') IS NULL THEN '正常'
                ELSE LTRIM(RTRIM(ISNULL(b.result_flag, '')))
            END,
            200
        ) AS varchar(200)
    ) AS RESULT_EXPLAIN_NOTE, -- 结果值的解释描述 VARCHAR2(200) 是

    COALESCE(
        TRY_CONVERT(datetime, a.Report_DT),
        TRY_CONVERT(datetime, a.report_dt),
        TRY_CONVERT(datetime, a.rechk_dt)
    ) AS EFFECTIVE_TIME, -- 活动发生时间 DATE

    CAST(NULL AS varchar(32)) AS STATUS, -- 卡片状态

    CAST(NULL AS datetime) AS CREATED_AT, -- 创建时间

    CAST('370104' AS varchar(6)) AS DISTRICT_CODE, -- 所属行政区划

    CAST('INSERT' AS varchar(10)) AS EXCHANGE_TYPE, -- 交换类型

    CAST(
        LEFT(loc.LOCAL_ITEM_CODE, 20) AS varchar(20)
    ) AS LOCAL_ITEM_CODE, -- 检验报告项目本地编码 VARCHAR2(20) 是

    CAST(
        LEFT(loc.LOCAL_ITEM_NAME, 80) AS varchar(80)
    ) AS LOCAL_ITEM_NAME, -- 检验报告项目本地名称 VARCHAR2(80) 是

    GETDATE() AS SYSTEM_TIME, -- 数据上传时间戳

    CAST(
        LEFT(
            NULLIF(LTRIM(RTRIM(ISNULL(b.result_flag, ''))), ''),
            1
        ) AS char(1)
    ) AS RESULT_CODE, -- 检验结果代码 CHAR(1)

    CAST(
        TRY_CONVERT(decimal(14,4), NULLIF(LTRIM(RTRIM(b.result_str)), ''))
        AS decimal(14,4)
    ) AS RATION_RESULT, -- 检验定量结果 NUMBER(14,4)

    CAST(
        LEFT(
            COALESCE(NULLIF(LTRIM(RTRIM(b.result_unit)), ''), '-'),
            20
        ) AS varchar(20)
    ) AS RATION_RESULT_UOM, -- 检验定量结果计量单位 VARCHAR2(20)

    CAST(rd.seq AS numeric(4,0)) AS TEST_SN, -- 检验项目顺序号 NUMBER(4)

    CAST(
        CASE
            WHEN c.resulttype = '1' THEN 2
            WHEN TRY_CONVERT(decimal(18,4), NULLIF(LTRIM(RTRIM(b.result_str)), '')) IS NOT NULL THEN 2
            ELSE 1
        END AS numeric(1,0)
    ) AS TEST_RESULT_TYPE, -- 检验结果类型 NUMBER(1)

    CAST(
        LEFT(loc.ITEM_RESULT_SRC, 50) AS varchar(50)
    ) AS TEST_RESULT, -- 检验结果 VARCHAR2(50)

    CAST(
        LEFT(
            COALESCE(NULLIF(LTRIM(RTRIM(b.result_unit)), ''), '-'),
            50
        ) AS varchar(50)
    ) AS TEST_RESULT_UNIT, -- 检验结果计量单位 VARCHAR2(50)

    CAST('49557032X' AS varchar(32)) AS ORG_CODE, -- 医院组织机构代码

    CAST('山东省第二人民医院' AS varchar(70)) AS ORG_NAME, -- 医院名称

    CAST(
        LEFT(
            ISNULL(CONVERT(varchar(32), b.instrid), ''),
            32
        ) AS varchar(32)
    ) AS test_exam_equip_code, -- 检查设备编码

    CAST(
        LEFT(ISNULL(a.barcode, ''), 50) AS varchar(50)
    ) AS BARCODE_NO, -- 标本条形码号

    CAST(
        LEFT(ISNULL(a.pat_name, ''), 50) AS varchar(50)
    ) AS NAME, -- 患者姓名

    CAST(
        CASE
            WHEN a.PAT_SEX IN ('1','2','9') THEN a.PAT_SEX
            WHEN a.PAT_SEX IS NULL OR LTRIM(RTRIM(a.PAT_SEX)) = '' THEN '0'
            ELSE '9'
        END AS char(1)
    ) AS SEX_CODE, -- 患者性别代码

    CAST(
        LEFT(
            ISNULL(
                NULLIF(NULLIF(LTRIM(RTRIM(a.pat_idcardno)), ''), '""'),
                '000000000000000000'
            ),
            18
        ) AS varchar(18)
    ) AS ID_NUM, -- 患者身份证件号码

    CAST('0' AS varchar(100)) AS MTU_REC_MARK, -- 是否互认标识

    CAST(NULL AS varchar(100)) AS MTU_REC_LIMIT_MARK, -- 互认范围标识

    CAST(
        LEFT(loc.LOCAL_ITEM_NAME, 100) AS varchar(100)
    ) AS HOSPITEM_NAME, -- 院内项目名称

    CAST(
        LEFT(loc.LOCAL_ITEM_CODE, 100) AS varchar(100)
    ) AS HOSPITEM_CODE, -- 院内项目编码

    /*
      国家平台项目编码：优先 itemnote1，其次对照表。
      注意：这里不再用院内编码兜底，避免把院内编码误当国家平台编码。
    */
    CAST(
        LEFT(
            COALESCE(
                NULLIF(LTRIM(RTRIM(CONVERT(varchar(100), c.itemnote1))), ''),
                NULLIF(LTRIM(RTRIM(imap.CS_ITEM_CODE)), '')
            ),
            100
        ) AS varchar(100)
    ) AS PROJECT_CODE, -- 国家平台项目编码

    /*
      国家平台项目名称：优先 itemnote2，其次对照表。
      注意：这里不再用院内名称兜底，避免把院内名称误当国家平台名称。
    */
    CAST(
        LEFT(
            COALESCE(
                NULLIF(LTRIM(RTRIM(CONVERT(varchar(200), c.itemnote2))), ''),
                NULLIF(LTRIM(RTRIM(imap.CS_ITEM_NAME)), '')
            ),
            100
        ) AS varchar(100)
    ) AS PROJECT_NAME, -- 国家平台项目名称

    CAST(
        CASE
            WHEN UPPER(LTRIM(RTRIM(ISNULL(b.result_flag, '')))) IN ('H','HH','L','LL','↑','↓','HIGH','LOW') THEN '2'
            WHEN NULLIF(LTRIM(RTRIM(ISNULL(b.result_flag, ''))), '') IS NULL THEN '1'
            ELSE '3'
        END AS varchar(100)
    ) AS ITEM_SIGN, -- 结果标识 1正常 2异常 3不确定

    CAST(
        LEFT(
            COALESCE(
                CASE
                    WHEN a.PAT_TYPECODE IN ('1','2') THEN
                        COALESCE(
                            NULLIF(LTRIM(RTRIM(a.custom1)), ''),
                            NULLIF(LTRIM(RTRIM(a.pat_no)), '')
                        )
                    WHEN a.PAT_TYPECODE = '3'
                         AND NULLIF(LTRIM(RTRIM(a.pat_id)), '') IS NOT NULL
                         AND NULLIF(LTRIM(RTRIM(a.inp_id)), '') IS NOT NULL THEN
                        a.pat_id + '|' + a.inp_id
                    WHEN a.PAT_TYPECODE = '3'
                         AND NULLIF(LTRIM(RTRIM(a.pat_id)), '') IS NOT NULL
                         AND NULLIF(LTRIM(RTRIM(a.custom1)), '') IS NOT NULL THEN
                        a.pat_id + '|' + RIGHT(a.custom1, 1)
                    WHEN a.PAT_TYPECODE = '4' THEN
                        COALESCE(
                            NULLIF(LTRIM(RTRIM(a.custom1)), ''),
                            NULLIF(LTRIM(RTRIM(a.pat_no)), '')
                        )
                    ELSE NULLIF(LTRIM(RTRIM(a.pat_no)), '')
                END,
                NULLIF(LTRIM(RTRIM(a.pat_no)), ''),
                NULLIF(LTRIM(RTRIM(a.custom1)), ''),
                NULLIF(LTRIM(RTRIM(a.barcode)), ''),
                REPLACE(CONVERT(varchar(50), a.reportid), '-', '')
            ),
            32
        ) AS varchar(32)
    ) AS VISITING_NUM -- 就诊号

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

INNER JOIN lab_result b WITH (NOLOCK)
    ON b.reportid = a.reportid
   AND b.req_itemcode = rd.req_itemcode

LEFT JOIN lab_rptitem c WITH (NOLOCK)
    ON b.rpt_itemcode = c.rpt_itemcode

/* 统一整理院内项目编码、院内项目名称、项目结果，避免后面重复写表达式 */
CROSS APPLY (
    SELECT
        CAST(
            LEFT(
                COALESCE(
                    NULLIF(LTRIM(RTRIM(c.rpt_itemcode)), ''),
                    NULLIF(LTRIM(RTRIM(b.rpt_itemcode)), ''),
                    '9999'
                ),
                100
            ) AS varchar(100)
        ) AS LOCAL_ITEM_CODE,

        CAST(
            LEFT(
                COALESCE(
                    NULLIF(LTRIM(RTRIM(c.rpt_itemname)), ''),
                    NULLIF(LTRIM(RTRIM(b.rpt_itemname)), ''),
                    '未知检验项目'
                ),
                200
            ) AS varchar(200)
        ) AS LOCAL_ITEM_NAME,

        CAST(
            LEFT(
                COALESCE(
                    NULLIF(
                        LTRIM(RTRIM(
                            CASE
                                WHEN a.rptunitid IN ('14','43','19') THEN b.rpt_itemname
                                ELSE b.result_str
                            END
                        )),
                        ''
                    ),
                    '-'
                ),
                200
            ) AS varchar(200)
        ) AS ITEM_RESULT_SRC
) loc

/* 第二优先级：本地项目对照表，只取已确认映射 */
LEFT JOIN dbo.LIS_CS_EXAMINE_ITEM_MAP imap WITH (NOLOCK)
    ON imap.LOCAL_ITEM_CODE = loc.LOCAL_ITEM_CODE
   AND imap.LOCAL_ITEM_NAME = loc.LOCAL_ITEM_NAME
   AND imap.MAP_STATUS = 'MAPPED'
   AND imap.IS_CONFIRMED = 1

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
  AND NULLIF(LTRIM(RTRIM(loc.ITEM_RESULT_SRC)), '') IS NOT NULL
  AND a.pat_name NOT LIKE '%测试%'
