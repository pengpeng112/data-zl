
  CREATE OR REPLACE FORCE EDITIONABLE VIEW "HRPSEY656"."EMR_HOS_INFORMATION" ("ID", "ORG_CODE", "ORG_NAME", "ID_NUMBER", "EMP_ID", "DEPT_NAME", "DEPT_CODE", "HOSP_DEPT_NAME", "HOSP_DEPT_CODE", "WARD_NAME", "ADMIN_POSITION", "JOB_TITLE", "AGE", "ETHNICITY", "EMP_CATEGORY", "LICENSE_NO", "PRACTICE_QUAL", "TECH_TITLE_APPOINT_DATE", "INSURANCE_CODE", "EDUCATION", "EMP_STATUS", "PROF_TITLE_LEVEL", "LEVE_START_TIME", "NAME", "SEX", "PK_PSNCL", "MOBILE") AS 
  SELECT DISTINCT
    hrhmc001.id 	as ID，--主键
   '49557032X' AS ORG_CODE,--- 医院组织机构代码
   '山东省第二人民医院' AS ORG_NAME,  -- 医院名称
    hrhmc001.id           AS ID_NUMBER,--身份证号
    hrhmc001.clerkcode    AS EMP_ID,--职工编号
      null as  DEPT_NAME,--部门名称
       null as  DEPT_code,--部门编码
    hrhmc001.pk_dept      AS HOSP_DEPT_NAME,--院内部门名称
    hrhmc001.pk_deptcode  AS HOSP_DEPT_CODE,--院内部门编码
    null as WARD_NAME,--所在病区名称
    hrhmc001.jobglbdef19  AS ADMIN_POSITION,--行政职务
    hrhmc001.jobglbdef19  AS JOB_TITLE,--行政职务
    FLOOR(MONTHS_BETWEEN(SYSDATE,to_date(hrhmc001.birthdate,'yyyy-mm-dd'))/12) AS age,--年龄
    hrhmc001.nationality  AS ETHNICITY,--民族
    hrhmc001.jobglbdef7   AS EMP_CATEGORY,--人员分类
    zyjszg.glbdef5       AS LICENSE_NO,--执业证号
    zyjszg.glbdef1       AS PRACTICE_QUAL,--执业资格
    zyjszg.glbdef2       AS TECH_TITLE_APPOINT_DATE,--专业技术职务任职时间
    null as INSURANCE_CODE,--医保注册编码
    yx.xl                 AS EDUCATION,--文化程度
    '01' as EMP_STATUS,--人员状态
    zyjszg.glbdef7        AS PROF_TITLE_LEVEL,--专业技术职务等级
    zyjszg.glbdef2        AS LEVE_START_TIME,--等级聘任时间
    hrhmc001.name         AS name,--姓名
    hrhmc001.sex          AS sex,--性别
    hrhmc001.pk_psncl     AS pk_psncl,--人员类别
    hrhmc001.mobile       AS mobile --手机号

FROM (
    -- --------------------------------------------------------
    -- 主子查询：人员基本信息 + 在职岗位信息
    -- --------------------------------------------------------
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
-- --------------------------------------------------------
-- yx：最高学历（glbdef6='Y'）
-- --------------------------------------------------------
LEFT OUTER JOIN (
    SELECT
        hi_psndoc_edu.pk_psndoc AS pk_psndoc,
        a.name                  AS xl,
        hi_psndoc_edu.school    AS school,
        hi_psndoc_edu.major     AS zy,
        b.name                  AS xw
    FROM (
        SELECT
            pk_psndoc                  AS pk_psndoc,
            glbdef6                    AS yxxl,
            max(pk_psndoc_sub)         AS zibiaozhujian
        FROM hi_psndoc_edu
        GROUP BY pk_psndoc, glbdef6
    ) st
    LEFT OUTER JOIN hi_psndoc_edu hi_psndoc_edu
        ON st.zibiaozhujian = hi_psndoc_edu.pk_psndoc_sub
    LEFT OUTER JOIN bd_defdoc a
        ON hi_psndoc_edu.education = a.pk_defdoc
    LEFT OUTER JOIN bd_defdoc b
        ON hi_psndoc_edu.pk_degree  = b.pk_defdoc
    WHERE hi_psndoc_edu.glbdef6 = 'Y'
) yx ON (hrhmc001.pk_psndoc = yx.pk_psndoc)

-- --------------------------------------------------------
-- zyjszg：专业技术资格（glbdef3='Y'）
-- --------------------------------------------------------
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
            glbdef1                    AS glbdef1,
            glbdef2                    AS glbdef2,
            glbdef3                    AS glbdef3,
            glbdef4                    AS glbdef4,
            glbdef5                    AS glbdef5,
            glbdef7                    AS glbdef7,
            pk_psndoc                  AS pk_psndoc,
            max(pk_psndoc_sub)         AS zibiaozhujian
        FROM hi_psndoc_glbdef2
        GROUP BY glbdef1, glbdef2, glbdef3, pk_psndoc, glbdef4, glbdef5, glbdef7
    ) st
    LEFT OUTER JOIN hi_psndoc_glbdef2
        ON st.zibiaozhujian = hi_psndoc_glbdef2.pk_psndoc_sub
    WHERE hi_psndoc_glbdef2.glbdef3 = 'Y'
) zyjszg ON (hrhmc001.pk_psndoc = zyjszg.pk_psndoc)

WHERE hrhmc001.pk_psncl  NOT IN ('劳务派遣')
  AND hrhmc001.pk_psncl  NOT IN ('社会化')
  AND hrhmc001.ismainjob = 'Y'
  AND hrhmc001.endflag   = 'N'
  AND hrhmc001.poststat  = 'Y'
  AND hrhmc001.lastflag  = 'Y'

ORDER BY HOSP_DEPT_CODE,EMP_ID
