
  CREATE OR REPLACE FORCE VIEW "ODS"."V_EMR_INSPECTION_IMAGE_TEST" ("ID", "REPORT_ID", "APPLY_NUM", "ORG_CODE", "ORG_NAME", "IMAGE_NUM", "IMAGE_SAVE_PATH", "EFFECTIVE_TIME", "STATUS", "CREATED_AT", "DISTRICT_CODE", "EXCHANGE_TYPE", "SYSTEM_TIME") AS 
  SELECT
    /* 内码：主表ID + 图片序号 */
    SUBSTRB(
        TO_CHAR(p.ID) || '_IMG_1',
        1,
        100
    ) AS ID, -- 内码 VARCHAR2(100) 是 主键

    SUBSTRB(
        TO_CHAR(p.ID),
        1,
        100
    ) AS REPORT_ID, -- 检验报告单内码 VARCHAR2(100) 是 必填、主表存在

    SUBSTRB(
        TO_CHAR(p.APPLY_NUM),
        1,
        20
    ) AS APPLY_NUM, -- 电子申请单编号 VARCHAR2(20)

    SUBSTRB(
        NVL(p.ORG_CODE, '49557032X'),
        1,
        32
    ) AS ORG_CODE, -- 医院组织机构代码 VARCHAR2(32) 是

    SUBSTRB(
        NVL(p.ORG_NAME, '山东省第二人民医院'),
        1,
        70
    ) AS ORG_NAME, -- 医院名称 VARCHAR2(70) 是

    1 AS IMAGE_NUM, -- 图片序号 NUMBER 是

    '-' AS IMAGE_SAVE_PATH, -- 图像存放路径 VARCHAR2(512) 是，暂无真实路径时按要求填横线

    p.EFFECTIVE_TIME AS EFFECTIVE_TIME, -- 活动发生时间 DATE

    CAST(NULL AS VARCHAR2(32)) AS STATUS, -- 卡片状态 VARCHAR2(32)

    CAST(NULL AS TIMESTAMP) AS CREATED_AT, -- 创建时间 TIMESTAMP(6)

    SUBSTRB(
        NVL(p.DISTRICT_CODE, '370104'),
        1,
        6
    ) AS DISTRICT_CODE, -- 所属行政区划 VARCHAR2(6) 是

    SUBSTRB(
        NVL(p.EXCHANGE_TYPE, 'ADDHIS'),
        1,
        10
    ) AS EXCHANGE_TYPE, -- 交换类型 VARCHAR2(10) 是

    CAST(SYSTIMESTAMP AS TIMESTAMP) AS SYSTEM_TIME -- 数据上传时间戳 TIMESTAMP(6) 是

FROM V_EMR_INSPECTION_TEST p
WHERE p.ID IS NOT NULL
