
  CREATE OR REPLACE FORCE EDITIONABLE VIEW "HRPSEY656"."EMR_HOS_PRACTITIONER" ("ID", "ORG_CODE", "ORG_NAME", "ID_NUMBER", "EMP_ID", "DEPT_NAME", "DEPT_CODE", "HOSP_DEPT_NAME", "HOSP_DEPT_CODE", "WARD_NAME", "ADMIN_POSITION", "JOB_TITLE", "AGE", "ETHNICITY", "EMP_CATEGORY", "LICENSE_NO", "PRACTICE_QUAL", "TECH_TITLE_APPOINT_DATE", "INSURANCE_CODE", "EDUCATION", "EMP_STATUS", "PROF_TITLE_LEVEL", "LEVE_START_TIME", "SYSTEM_TIME") AS 
  SELECT DISTINCT
       SUBSTRB(NVL(NULLIF(src.ID_NUMBER_C, ''), src.EMP_ID_C), 1, 100) AS ID, -- 主键ID

       '49557032X' AS ORG_CODE, -- 医院组织机构代码

       '山东省第二人民医院' AS ORG_NAME, -- 医院名称

       SUBSTRB(NVL(NULLIF(src.ID_NUMBER_C, ''), '-'), 1, 20) AS ID_NUMBER, -- 身份证号

       SUBSTRB(NVL(NULLIF(src.EMP_ID_C, ''), '-'), 1, 100) AS EMP_ID, -- 职工编号

       SUBSTRB(NVL(cs.VALUE_DOMAIN_NAME, '其他科室'), 1, 100) AS DEPT_NAME, -- 部门名称，对照CDA_SECTION_MAP，无法对照填其他科室

       SUBSTRB(NVL(cs.VALUE_DOMAIN_CODE, 'D99'), 1, 100) AS DEPT_CODE, -- 部门编码，对照CDA_SECTION_MAP，无法对照填D99

       SUBSTRB(NVL(NULLIF(src.HOSP_DEPT_NAME_C, ''), '-'), 1, 100) AS HOSP_DEPT_NAME, -- 院内部门名称

       SUBSTRB(NVL(NULLIF(src.HOSP_DEPT_CODE_C, ''), '-'), 1, 100) AS HOSP_DEPT_CODE, -- 院内部门编码

       SUBSTRB(NVL(NULLIF(src.HOSP_DEPT_NAME_C, ''), '-'), 1, 100) AS WARD_NAME, -- 所在病区名称，无病区来源，使用院内部门名称兜底

       SUBSTRB(NVL(NULLIF(src.ADMIN_POSITION_C, ''), '-'), 1, 100) AS ADMIN_POSITION, -- 行政职务

       SUBSTRB(
           NVL(
               NULLIF(src.ADMIN_POSITION_C, ''),
               NVL(NULLIF(src.PRACTICE_QUAL_C, ''), '-')
           ),
           1,
           100
       ) AS JOB_TITLE, -- 职务名称，优先行政职务，空时用职称/资格兜底

       CASE
           WHEN REGEXP_LIKE(src.BIRTHDATE_C, '^[0-9]{4}-[0-9]{2}-[0-9]{2}$')
           THEN FLOOR(MONTHS_BETWEEN(SYSDATE, TO_DATE(src.BIRTHDATE_C, 'yyyy-mm-dd')) / 12)
           ELSE 0
       END AS AGE, -- 年龄，出生日期异常时填0

       CASE
           WHEN src.ETHNICITY_C LIKE '%汉%' THEN '01'
           WHEN src.ETHNICITY_C LIKE '%蒙古%' THEN '02'
           WHEN src.ETHNICITY_C LIKE '%回%' THEN '03'
           WHEN src.ETHNICITY_C LIKE '%藏%' THEN '04'
           WHEN src.ETHNICITY_C LIKE '%维吾尔%' THEN '05'
           WHEN src.ETHNICITY_C LIKE '%苗%' THEN '06'
           WHEN src.ETHNICITY_C LIKE '%彝%' THEN '07'
           WHEN src.ETHNICITY_C LIKE '%壮%' THEN '08'
           WHEN src.ETHNICITY_C LIKE '%布依%' THEN '09'
           WHEN src.ETHNICITY_C LIKE '%朝鲜%' THEN '10'
           WHEN src.ETHNICITY_C LIKE '%满%' THEN '11'
           WHEN src.ETHNICITY_C LIKE '%侗%' THEN '12'
           WHEN src.ETHNICITY_C LIKE '%瑶%' THEN '13'
           WHEN src.ETHNICITY_C LIKE '%白%' THEN '14'
           WHEN src.ETHNICITY_C LIKE '%土家%' THEN '15'
           WHEN src.ETHNICITY_C LIKE '%哈尼%' THEN '16'
           WHEN src.ETHNICITY_C LIKE '%哈萨克%' THEN '17'
           WHEN src.ETHNICITY_C LIKE '%傣%' THEN '18'
           WHEN src.ETHNICITY_C LIKE '%黎%' THEN '19'
           WHEN src.ETHNICITY_C LIKE '%傈僳%' THEN '20'
           WHEN src.ETHNICITY_C LIKE '%佤%' THEN '21'
           WHEN src.ETHNICITY_C LIKE '%畲%' THEN '22'
           WHEN src.ETHNICITY_C LIKE '%高山%' THEN '23'
           WHEN src.ETHNICITY_C LIKE '%拉祜%' THEN '24'
           WHEN src.ETHNICITY_C LIKE '%水%' THEN '25'
           WHEN src.ETHNICITY_C LIKE '%东乡%' THEN '26'
           WHEN src.ETHNICITY_C LIKE '%纳西%' THEN '27'
           WHEN src.ETHNICITY_C LIKE '%景颇%' THEN '28'
           WHEN src.ETHNICITY_C LIKE '%柯尔克孜%' THEN '29'
           WHEN src.ETHNICITY_C LIKE '%土族%' THEN '30'
           ELSE '01'
       END AS ETHNICITY, -- 民族，空值暂按汉族01兜底

       CASE
           WHEN src.PRACTICE_QUAL_C LIKE '%医师%' THEN '医'
           WHEN src.PRACTICE_QUAL_C LIKE '%医士%' THEN '医'
           WHEN src.PRACTICE_QUAL_C LIKE '%护士%' THEN '护'
           WHEN src.PRACTICE_QUAL_C LIKE '%护师%' THEN '护'
           WHEN src.PRACTICE_QUAL_C LIKE '%药师%' THEN '技'
           WHEN src.PRACTICE_QUAL_C LIKE '%药士%' THEN '技'
           WHEN src.PRACTICE_QUAL_C LIKE '%技师%' THEN '技'
           WHEN src.PRACTICE_QUAL_C LIKE '%技士%' THEN '技'
           WHEN src.PRACTICE_QUAL_C LIKE '%心理治疗师%' THEN '技'
           WHEN src.PRACTICE_QUAL_C LIKE '%助听器验配师%' THEN '技'
           WHEN src.PRACTICE_QUAL_C LIKE '%眼镜验光员%' THEN '技'
           WHEN src.PRACTICE_QUAL_C LIKE '%健康管理师%' THEN '技'
           ELSE '行政后勤'
       END AS EMP_CATEGORY, -- 人员分类

       SUBSTRB(NVL(NULLIF(src.LICENSE_NO_C, ''), '-'), 1, 100) AS LICENSE_NO, -- 执业证号，空值填-

       CASE
           WHEN src.PRACTICE_QUAL_C LIKE '%助理医师%' THEN '02'
           WHEN src.PRACTICE_QUAL_C LIKE '%医师%' THEN '01'
           WHEN src.PRACTICE_QUAL_C LIKE '%医士%' THEN '01'
           WHEN src.PRACTICE_QUAL_C LIKE '%护士%' THEN '03'
           WHEN src.PRACTICE_QUAL_C LIKE '%护师%' THEN '03'
           WHEN src.PRACTICE_QUAL_C LIKE '%药师%' THEN '04'
           WHEN src.PRACTICE_QUAL_C LIKE '%药士%' THEN '04'
           ELSE '-'
       END AS PRACTICE_QUAL, -- 执业资格，非医护药人员无对应值域，按要求填-

       CASE
           WHEN REGEXP_LIKE(src.TECH_DATE_C, '^[0-9]{4}-[0-9]{2}-[0-9]{2}$')
           THEN TO_DATE(src.TECH_DATE_C, 'yyyy-mm-dd')
           ELSE DATE '1900-01-01'
       END AS TECH_TITLE_APPOINT_DATE, -- 专业技术职务任职时间，DATE字段空值用1900-01-01兜底

       '-' AS INSURANCE_CODE, -- 医保注册编码，无来源，填-

       CASE
           WHEN src.EDUCATION_C LIKE '%硕博连读%' THEN '01'
           WHEN src.EDUCATION_C LIKE '%博士%' THEN '01'
           WHEN src.EDUCATION_C LIKE '%硕士%' THEN '02'
           WHEN src.EDUCATION_C LIKE '%在职硕士%' THEN '02'
           WHEN src.EDUCATION_C LIKE '%本科%' THEN '05'
           WHEN src.EDUCATION_C LIKE '%成人本科%' THEN '05'
           WHEN src.EDUCATION_C LIKE '%专升本%' THEN '05'
           WHEN src.EDUCATION_C LIKE '%自考本科%' THEN '05'
           WHEN src.EDUCATION_C LIKE '%大专%' THEN '08'
           WHEN src.EDUCATION_C LIKE '%专科%' THEN '08'
           WHEN src.EDUCATION_C LIKE '%高中%' THEN '10'
           WHEN src.EDUCATION_C LIKE '%初中%' THEN '12'
           ELSE '05'
       END AS EDUCATION, -- 文化程度，空值暂按本科05兜底

       CASE
           WHEN src.PSNCL_C LIKE '%退休%' OR src.PSNCL_C LIKE '%返聘%' THEN '02'
           WHEN src.PSNCL_C LIKE '%离%' OR src.PSNCL_C LIKE '%调%' THEN '04'
           ELSE '01'
       END AS EMP_STATUS, -- 人员状态

       CASE
           WHEN src.PROF_TITLE_LEVEL_C = '正高' THEN '5'
           WHEN src.PROF_TITLE_LEVEL_C = '副高' THEN '4'
           WHEN src.PROF_TITLE_LEVEL_C = '中级' THEN '3'
           WHEN src.PROF_TITLE_LEVEL_C = '初级' THEN '2'
           WHEN src.PROF_TITLE_LEVEL_C = '员级' THEN '1'
           ELSE '0'
       END AS PROF_TITLE_LEVEL, -- 专业技术职务等级

       CASE
           WHEN REGEXP_LIKE(src.LEVE_DATE_C, '^[0-9]{4}-[0-9]{2}-[0-9]{2}$')
           THEN TO_DATE(src.LEVE_DATE_C, 'yyyy-mm-dd')
           ELSE DATE '1900-01-01'
       END AS LEVE_START_TIME, -- 等级聘任时间，DATE字段空值用1900-01-01兜底

       TO_CHAR(SYSDATE, 'yyyy-mm-dd hh24:mi:ss') AS SYSTEM_TIME -- 数据上传时间戳

FROM (
    SELECT
        TRIM(REPLACE(REPLACE(REPLACE(TO_CHAR(hrhmc001.id), CHR(13), ''), CHR(10), ''), '"', '')) AS ID_NUMBER_C,
        TRIM(REPLACE(REPLACE(REPLACE(TO_CHAR(hrhmc001.clerkcode), CHR(13), ''), CHR(10), ''), '"', '')) AS EMP_ID_C,
        TRIM(REPLACE(REPLACE(REPLACE(TO_CHAR(hrhmc001.pk_dept), CHR(13), ''), CHR(10), ''), '"', '')) AS HOSP_DEPT_NAME_C,
        TRIM(REPLACE(REPLACE(REPLACE(TO_CHAR(hrhmc001.pk_deptcode), CHR(13), ''), CHR(10), ''), '"', '')) AS HOSP_DEPT_CODE_C,
        TRIM(REPLACE(REPLACE(REPLACE(TO_CHAR(hrhmc001.jobglbdef19), CHR(13), ''), CHR(10), ''), '"', '')) AS ADMIN_POSITION_C,
        TRIM(REPLACE(REPLACE(REPLACE(TO_CHAR(hrhmc001.birthdate), CHR(13), ''), CHR(10), ''), '"', '')) AS BIRTHDATE_C,
        TRIM(REPLACE(REPLACE(REPLACE(TO_CHAR(hrhmc001.nationality), CHR(13), ''), CHR(10), ''), '"', '')) AS ETHNICITY_C,
        TRIM(REPLACE(REPLACE(REPLACE(TO_CHAR(hrhmc001.jobglbdef7), CHR(13), ''), CHR(10), ''), '"', '')) AS EMP_CATEGORY_SRC_C,
        TRIM(REPLACE(REPLACE(REPLACE(TO_CHAR(zyjszg.glbdef5), CHR(13), ''), CHR(10), ''), '"', '')) AS LICENSE_NO_C,
        TRIM(REPLACE(REPLACE(REPLACE(TO_CHAR(zyjszg.glbdef1), CHR(13), ''), CHR(10), ''), '"', '')) AS PRACTICE_QUAL_C,
        SUBSTR(TRIM(REPLACE(REPLACE(REPLACE(TO_CHAR(zyjszg.glbdef2), CHR(13), ''), CHR(10), ''), '"', '')), 1, 10) AS TECH_DATE_C,
        TRIM(REPLACE(REPLACE(REPLACE(TO_CHAR(yx.xl), CHR(13), ''), CHR(10), ''), '"', '')) AS EDUCATION_C,
        TRIM(REPLACE(REPLACE(REPLACE(TO_CHAR(zyjszg.glbdef7), CHR(13), ''), CHR(10), ''), '"', '')) AS PROF_TITLE_LEVEL_C,
        SUBSTR(TRIM(REPLACE(REPLACE(REPLACE(TO_CHAR(zyjszg.glbdef2), CHR(13), ''), CHR(10), ''), '"', '')), 1, 10) AS LEVE_DATE_C,
        TRIM(REPLACE(REPLACE(REPLACE(TO_CHAR(hrhmc001.pk_psncl), CHR(13), ''), CHR(10), ''), '"', '')) AS PSNCL_C
    FROM (
        SELECT
            bd_psndoc.pk_psndoc    AS pk_psndoc,
            hi_psnjob.clerkcode    AS clerkcode,
            bd_psndoc.name         AS name,
            enumvalue.name         AS sex,
            bd_psndoc.id           AS id,
            bd_psndoc.birthdate    AS birthdate,
            bd_psndoc.mobile       AS mobile,
            defdoc.name            AS nationality,
            psncl.name             AS pk_psncl,
            dept.name              AS pk_dept,
            dept.code              AS pk_deptcode,
            dept.mnecode           AS deptcode,
            hi_psnjob.jobglbdef16  AS jobglbdef16,
            hi_psnjob.jobglbdef7   AS jobglbdef7,
            hi_psnjob.jobglbdef19  AS jobglbdef19,
            hi_psnjob.endflag      AS endflag,
            hi_psnjob.lastflag     AS lastflag,
            hi_psnjob.poststat     AS poststat,
            hi_psnjob.ismainjob    AS ismainjob,
            hi_psnjob.pk_job       AS pk_job
        FROM bd_psndoc bd_psndoc
        LEFT OUTER JOIN hi_psnjob hi_psnjob
            ON bd_psndoc.pk_psndoc = hi_psnjob.pk_psndoc
        LEFT OUTER JOIN bd_psncl psncl
            ON hi_psnjob.pk_psncl = psncl.pk_psncl
        LEFT OUTER JOIN org_dept dept
            ON hi_psnjob.pk_dept = dept.pk_dept
        LEFT OUTER JOIN MD_ENUMVALUE enumvalue
            ON  enumvalue.id    = '04dfe53c-46e0-4536-a26a-f6deeec3180d'
            AND enumvalue.value = bd_psndoc.sex
        LEFT OUTER JOIN bd_defdoc defdoc
            ON defdoc.pk_defdoc = bd_psndoc.nationality
    ) hrhmc001

    LEFT OUTER JOIN (
        SELECT
            hi_psndoc_edu.pk_psndoc AS pk_psndoc,
            a.name                  AS xl,
            hi_psndoc_edu.school    AS school,
            hi_psndoc_edu.major     AS zy,
            b.name                  AS xw
        FROM (
            SELECT
                pk_psndoc          AS pk_psndoc,
                glbdef6            AS yxxl,
                MAX(pk_psndoc_sub) AS zibiaozhujian
            FROM hi_psndoc_edu
            GROUP BY pk_psndoc, glbdef6
        ) st
        LEFT OUTER JOIN hi_psndoc_edu hi_psndoc_edu
            ON st.zibiaozhujian = hi_psndoc_edu.pk_psndoc_sub
        LEFT OUTER JOIN bd_defdoc a
            ON hi_psndoc_edu.education = a.pk_defdoc
        LEFT OUTER JOIN bd_defdoc b
            ON hi_psndoc_edu.pk_degree = b.pk_defdoc
        WHERE hi_psndoc_edu.glbdef6 = 'Y'
    ) yx
        ON hrhmc001.pk_psndoc = yx.pk_psndoc

    LEFT OUTER JOIN (
        SELECT
            hi_psndoc_glbdef2.pk_psndoc AS pk_psndoc,
            hi_psndoc_glbdef2.glbdef1   AS glbdef1,
            hi_psndoc_glbdef2.glbdef2   AS glbdef2,
            st.glbdef4                  AS glbdef4,
            st.glbdef5                  AS glbdef5,
            st.glbdef7                  AS glbdef7
        FROM (
            SELECT
                glbdef1            AS glbdef1,
                glbdef2            AS glbdef2,
                glbdef3            AS glbdef3,
                glbdef4            AS glbdef4,
                glbdef5            AS glbdef5,
                glbdef7            AS glbdef7,
                pk_psndoc          AS pk_psndoc,
                MAX(pk_psndoc_sub) AS zibiaozhujian
            FROM hi_psndoc_glbdef2
            GROUP BY glbdef1, glbdef2, glbdef3, pk_psndoc, glbdef4, glbdef5, glbdef7
        ) st
        LEFT OUTER JOIN hi_psndoc_glbdef2 hi_psndoc_glbdef2
            ON st.zibiaozhujian = hi_psndoc_glbdef2.pk_psndoc_sub
        WHERE hi_psndoc_glbdef2.glbdef3 = 'Y'
    ) zyjszg
        ON hrhmc001.pk_psndoc = zyjszg.pk_psndoc

    WHERE hrhmc001.pk_psncl NOT IN ('劳务派遣')
      AND hrhmc001.pk_psncl NOT IN ('社会化')
      AND hrhmc001.ismainjob = 'Y'
      AND hrhmc001.endflag   = 'N'
      AND hrhmc001.poststat  = 'Y'
      AND hrhmc001.lastflag  = 'Y'
) src
LEFT JOIN (
    SELECT
        HOSPITAL_CODE,
        MAX(VALUE_DOMAIN_CODE) AS VALUE_DOMAIN_CODE,
        MAX(VALUE_DOMAIN_NAME) AS VALUE_DOMAIN_NAME
    FROM HRPSEY656.CDA_SECTION_MAP
    WHERE CATEGORY_CODE = 'CS_SECTION'
    GROUP BY HOSPITAL_CODE
) cs
    ON src.HOSP_DEPT_CODE_C = cs.HOSPITAL_CODE
