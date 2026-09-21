
  CREATE OR REPLACE FORCE VIEW "ODS"."V_EMR_OUTPATIENT_RECIPE" ("ID", "ORG_CODE", "ORG_NAME", "OUTPATIENT_NUM", "CASE_NUM", "RECIPE_NUM", "RECIPE_TYPE_CODE", "RECIPE_TYPE_NAME", "RECIPE_CLINIC_CODE", "RECIPE_CLINIC_NAME", "RECIPE_CLASS_CODE", "RECIPE_CLASS_NAME", "CH_METHOD", "NAME", "OTHER_ID_TYPE", "OTHER_ID_TYPE_NAME", "OTHER_ID_NUM", "ID_NUM", "SEX_CODE", "SEX_NAME", "AGE", "AGE_MONTH", "AGE_DAY", "AGE_HOUR", "PRESCRIBE_DATE", "DEP_CODE", "DEP_NAME", "HOS_DEP_CODE", "HOS_DEP_NAME", "DOCTOR_CODE", "DOCTOR_NAME", "EFFECTIVE_DAYS", "CHECKER_CODE", "CHECKER_NAME", "CHECK_DATE", "TP_DOCTOR", "HD_DOCTOR", "FY_DOCTOR", "CF_NOTES", "DISTRICT_CODE", "EXCHANGE_TYPE", "DEI", "NODE_CODE", "SYSTEM_TIME") AS 
  select substr(
           '49557032X' || '|' ||
           to_char(a.presc_date, 'yyyymmddhh24miss') || '|' ||
           a.patient_id || '|' ||
           a.presc_no,
           1,
           100
       ) as ID,-- 内码 是 主键

       '49557032X' as ORG_CODE,-- 医院组织机构编码 是 必填

       '山东省第二人民医院' as ORG_NAME,-- 医院名称 是 必填

       substr(nvl(a.clinic_no, a.patient_id||to_char(a.PRESC_DATE,'yyyymmdd')), 1, 18) as OUTPATIENT_NUM,-- 本次门诊标识号 是 必填

       substr(a.patient_id, 1, 20) as CASE_NUM,-- 病历号

       substr(to_char(a.presc_no), 1, 20) as RECIPE_NUM,-- 处方编号 是 与药品医嘱表保证关联性

       case
           when td.has_herb = 1 then '3'       -- 中草药
           when td.has_tcm = 1 then '1'        -- 中成药按中药处理
           when td.has_western = 1 then '2'    -- 西药
           when td.has_other = 1 then '5'      -- 辅料、试剂按非药品处理
           else '5'
       end as RECIPE_TYPE_CODE,-- 处方类别代码 是 1中药、2西药、3中草药、4中药饮片、5非药品

       case
           when td.has_herb = 1 then '中草药'
           when td.has_tcm = 1 then '中药'
           when td.has_western = 1 then '西药'
           when td.has_other = 1 then '非药品'
           else '非药品'
       end as RECIPE_TYPE_NAME,-- 处方类别名称 是

       case
           when td.has_narcotic = 1 then '2'     -- 麻醉药品
           when td.has_psych_one = 1 then '3'    -- 精神一类
           when td.has_psych_two = 1 then '4'    -- 精神二类
           when td.has_toxic = 1 then '5'        -- 毒性药品
           when td.has_precursor = 1 then '6'    -- 易制毒药品
           else '1'                              -- 普通药品
       end as RECIPE_CLINIC_CODE,-- 处方临床分类代码

       case
           when td.has_narcotic = 1 then '麻醉药品'
           when td.has_psych_one = 1 then '精神一类'
           when td.has_psych_two = 1 then '精神二类'
           when td.has_toxic = 1 then '毒性药品'
           when td.has_precursor = 1 then '易制毒药品'
           else '普通药品'
       end as RECIPE_CLINIC_NAME,-- 处方临床分类名称

       case
           when a.ordered_by in ('030603', '030601', '030504') then '02' -- 急诊
           when to_char(a.presc_source) = '0' then '01'                 -- 门诊
           when to_char(a.presc_source) = '1' then '03'                 -- 住院
           else '99'
       end as RECIPE_CLASS_CODE,-- 处方分类代码 DMD-02

       case
           when a.ordered_by in ('030603', '030601', '030504') then '急诊'
           when to_char(a.presc_source) = '0' then '门诊'
           when to_char(a.presc_source) = '1' then '住院'
           else '其他'
       end as RECIPE_CLASS_NAME,-- 处方分类名称

       cast(null as varchar2(100)) as CH_METHOD,-- 治则治法 中医处方填写

       substr(nvl(a.name, pmi.name), 1, 50) as NAME,-- 姓名 患者姓名

       substr(
           nvl(
               (select zd.国标编码
                  from cda.cda_dictionary zd
                 where zd.字典名称 = '身份证件类型代码'
                   and zd.院标编码 = pmi.id_type
                   and rownum = 1),
               case when pmi.id_no is not null then '01' else '99' end
           ),
           1,
           11
       ) as OTHER_ID_TYPE,-- 身份证件标识代码

       substr(
           nvl(
               (select zd.国标名称
                  from cda.cda_dictionary zd
                 where zd.字典名称 = '身份证件类型代码'
                   and zd.院标编码 = pmi.id_type
                   and rownum = 1),
               case when pmi.id_no is not null then '居民身份证' else '其他法定有效证件' end
           ),
           1,
           30
       ) as OTHER_ID_TYPE_NAME,-- 身份标识名称

       cast(null as varchar2(18)) as OTHER_ID_NUM,-- 其他身份证件号码

       substr(pmi.id_no, 1, 18) as ID_NUM,-- 身份证件号码

       decode(pmi.sex, '男', '1', '女', '2', '未知', '0', '9') as SEX_CODE,-- 性别代码

       decode(pmi.sex, '男', '男', '女', '女', '未知', '未知', '不明') as SEX_NAME,-- 性别

       case
           when pmi.date_of_birth is not null
            and a.presc_date is not null
            and a.presc_date >= pmi.date_of_birth
           then least(
                    greatest(trunc(months_between(a.presc_date, pmi.date_of_birth) / 12), 0),
                    200
                )
           else cast(null as number)
       end as AGE,-- 年龄 范围在0-200之间

       case
           when pmi.date_of_birth is not null
            and a.presc_date is not null
            and a.presc_date >= pmi.date_of_birth
           then least(
                    greatest(mod(trunc(months_between(a.presc_date, pmi.date_of_birth)), 12), 0),
                    11
                )
           else cast(null as number)
       end as AGE_MONTH,-- 年龄（月） 范围在0-11之间

       case
           when pmi.date_of_birth is not null
            and a.presc_date is not null
            and a.presc_date >= pmi.date_of_birth
           then least(
                    greatest(
                        trunc(
                            a.presc_date -
                            add_months(
                                pmi.date_of_birth,
                                trunc(months_between(a.presc_date, pmi.date_of_birth))
                            )
                        ),
                        0
                    ),
                    30
                )
           else cast(null as number)
       end as AGE_DAY,-- 年龄（天） 范围在0-30之间

       case
           when pmi.date_of_birth is not null
            and a.presc_date is not null
            and a.presc_date >= pmi.date_of_birth
           then least(
                    greatest(
                        trunc(
                            24 * (
                                (
                                    a.presc_date -
                                    add_months(
                                        pmi.date_of_birth,
                                        trunc(months_between(a.presc_date, pmi.date_of_birth))
                                    )
                                )
                                -
                                trunc(
                                    a.presc_date -
                                    add_months(
                                        pmi.date_of_birth,
                                        trunc(months_between(a.presc_date, pmi.date_of_birth))
                                    )
                                )
                            )
                        ),
                        0
                    ),
                    23
                )
           else cast(null as number)
       end as AGE_HOUR,-- 年龄（小时） 范围在0-23之间

       cast(a.presc_date as date) as PRESCRIBE_DATE,-- 处方开立时间 是 业务日期

       substr(
           nvl(
               (select ks.qmpt_code
                  from his.dept_dict ks
                 where ks.dept_code = nvl( d.visit_dept,a.ORDERED_BY)
                   and rownum = 1),
               d.visit_dept
           ),
           1,
           20
       ) as DEP_CODE,-- 就诊科室编号 是

       substr(
           nvl(
               (select ks.qmpt_name
                  from his.dept_dict ks
                 where ks.dept_code = nvl( d.visit_dept,a.ORDERED_BY)
                   and rownum = 1),
               nvl(
                   (select ks.dept_name
                      from his.dept_dict ks
                     where ks.dept_code = d.visit_dept
                       and rownum = 1),
                   d.visit_dept
               )
           ),
           1,
           50
       ) as DEP_NAME,-- 就诊科室名称 是

       substr(d.visit_dept, 1, 20) as HOS_DEP_CODE,-- 院内科室编码 是

       substr(
           nvl(
               (select ks.dept_name
                  from his.dept_dict ks
                 where ks.dept_code = d.visit_dept
                   and rownum = 1),
               d.visit_dept
           ),
           1,
           50
       ) as HOS_DEP_NAME,-- 院内科室名称 是

       substr(
           nvl(
               (select sd.emp_no
                  from his.staff_dict sd
                 where (sd.emp_no = a.prescribed_by or sd.name = a.prescribed_by)
                   and rownum = 1),
               a.prescribed_by
           ),
           1,
           32
       ) as DOCTOR_CODE,-- 医生代码(职工编号)

      nvl( substr(
           nvl(
               (select sd.name
                  from his.staff_dict sd
                 where (sd.emp_no = a.prescribed_by or sd.name = a.prescribed_by)
                   and rownum = 1),
               a.prescribed_by
           ),
           1,
           50
       ),'-') as DOCTOR_NAME,-- 医生姓名 是 开方医生姓名

       cast(nvl(td.abidance, 0) as number) as EFFECTIVE_DAYS,-- 处方有效天数

       substr(
           nvl(
               (select sd.emp_no
                  from his.staff_dict sd
                 where (sd.emp_no = a.entered_by or sd.name = a.entered_by)
                   and rownum = 1),
               '-'
           ),
           1,
           32
       ) as CHECKER_CODE,-- 审方人代码

       substr(
           nvl(
               (select sd.name
                  from his.staff_dict sd
                 where (sd.emp_no = a.entered_by or sd.name = a.entered_by)
                   and rownum = 1),
               nvl(a.entered_by, '-')
           ),
           1,
           50
       ) as CHECKER_NAME,-- 审方人姓名

       cast(a.dispensing_datetime as date) as CHECK_DATE,-- 审方时间

       substr(a.dispensing_provider, 1, 50) as TP_DOCTOR,-- 调配药剂师

       substr(a.entered_by, 1, 50) as HD_DOCTOR,-- 核对药剂师

       substr(a.dispensing_provider, 1, 50) as FY_DOCTOR,-- 发药药剂师

       substr(a.memo, 1, 100) as CF_NOTES,-- 处方备注信息

       '370104' as DISTRICT_CODE,-- 所属行政区划 是

       'INSERT' as EXCHANGE_TYPE,-- 交换类型 是

       cast(null as varchar2(50)) as DEI,-- 数据交换标识符

       cast(null as varchar2(50)) as NODE_CODE,-- 节点标识符

       cast(systimestamp as timestamp) as SYSTEM_TIME-- 数据上传时间戳 是

from his.drug_presc_master a
left join (
    select dp.presc_date,
           dp.presc_no,
           max(dp.abidance) as abidance,

           -- 处方类别：his.drug_dict.drug_indicator
           max(case when to_char(b.drug_indicator) = '1' then 1 else 0 end) as has_western,-- 西药
           max(case when to_char(b.drug_indicator) = '2' then 1 else 0 end) as has_herb,-- 中草药
           max(case when to_char(b.drug_indicator) = '3' then 1 else 0 end) as has_tcm,-- 中成药
           max(case when to_char(b.drug_indicator) in ('5', '6') then 1 else 0 end) as has_other,-- 辅料、试剂

           -- 处方临床分类：his.drug_dict.toxi_property
           max(case when replace(trim(b.toxi_property), ' ', '') = '麻醉药品' then 1 else 0 end) as has_narcotic,
           max(case when replace(trim(b.toxi_property), ' ', '') in ('精神一类', '一类精神药品') then 1 else 0 end) as has_psych_one,
           max(case when replace(trim(b.toxi_property), ' ', '') in ('精神二类', '二类精神药品') then 1 else 0 end) as has_psych_two,
           max(case when replace(trim(b.toxi_property), ' ', '') = '毒性药品' then 1 else 0 end) as has_toxic,
           max(case when replace(trim(b.toxi_property), ' ', '') = '易制毒药品' then 1 else 0 end) as has_precursor

      from his.drug_presc_detail dp
      left join his.drug_dict b
             on dp.drug_code = b.drug_code
     group by dp.presc_date, dp.presc_no
) td
       on td.presc_no = a.presc_no
      and td.presc_date = a.presc_date
left join his.clinic_master d
       on a.clinic_no = d.clinic_no
left join his.pat_master_index pmi
       on a.patient_id = pmi.patient_id
where a.presc_source = '0'
  and a.flag = '1'
  and a.costs > 0
  and a.presc_date >= to_date('2021-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss')
  and a.presc_date <  to_date('2025-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss') and   substr(
           nvl(
               (select ks.qmpt_code
                  from his.dept_dict ks
                 where ks.dept_code = nvl( d.visit_dept,a.ORDERED_BY)
                   and rownum = 1),
               d.visit_dept
           ),
           1,
           20
       ) is not null and substr(
           '49557032X' || '|' ||
           to_char(a.presc_date, 'yyyymmddhh24miss') || '|' ||
           a.patient_id || '|' ||
           a.presc_no,
           1,
           100
       )  <>'49557032X|20230220170748|00661308|24886'  and substr(d.visit_dept, 1, 20) is not null
