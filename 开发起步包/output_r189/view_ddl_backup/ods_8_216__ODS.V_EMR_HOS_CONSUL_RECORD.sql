
  CREATE OR REPLACE FORCE VIEW "ODS"."V_EMR_HOS_CONSUL_RECORD" ("ID", "ORG_CODE", "ORG_NAME", "DISTRICT_CODE", "EXCHANGE_TYPE", "SYSTEM_TIME", "ADMISSION_ID", "DEPT_CODE", "DEP_NAME", "AREA_NAME", "WARD_NUM", "SICKBED_NUM", "MEDICAL_RECORDS_SUNNARY", "DIA_TREAT_NAME", "TREAT_NOTE", "CONSULTATION_TYPE", "CONSULTATION_REASON", "CONSULTATION_APP_DOC_NAME", "CONSULTATION_APP_DEP", "CONSULTATION_APP_ORG_NAME", "CONSULTATION_APPLAY_DATE", "CONSULTATION_OPINION", "CONSULTATION_DOC_NAME", "CONSULTATION_DEP_NAME", "CONSULTATION_DOC_ORG_NAME", "CONSULTATION_ORG_NAME", "CONSULTATION_DATE") AS 
  select substr(
           '49557032X'||'|'||t.patient_id||'|'||t.visit_id||'|'||
           t.consultation_id||'|'||
           nvl(t1.consultation_dept, '0')||'|'||
           nvl(t1.SUB_ID, '0'),
           1,
           100
       ) as ID,--  内码  是 主键

       '49557032X' as ORG_CODE,--  医院组织机构代码  是 必填、机构验证，有组织机构代码的传代码；无组织机构代码的上传编码

       '山东省第二人民医院' as ORG_NAME,--  医院名称  是 必填，填写标准医院名称，每次上传的医院名称必须一致

       '370104' as DISTRICT_CODE,-- 所属行政区划  是 按机构所在的行政区划（区县）

       'INSERT' as EXCHANGE_TYPE,-- 交换类型  是 INSERT：向平台传新数据时；UPDATE：向平台更新某条数据时；DELETE：从平台删除某条数据时；ADDHIS :向平台补充历史数据

       cast(systimestamp as timestamp) as SYSTEM_TIME,-- 数据上传时间戳 是

       t.patient_id||'|'||t.visit_id as ADMISSION_ID,--  住院唯一标示号 是

       nvl(
           (select ks.qmpt_code
              from his.dept_dict ks
             where ks.dept_code = nvl(t.consultation_dept, nvl(t2.dept_discharge_from, t2.dept_admission_to))
               and rownum = 1),
           nvl(t.consultation_dept, nvl(t2.dept_discharge_from, t2.dept_admission_to))
       ) as DEPT_CODE,-- 科室代码  是 省级科室值域标准

       nvl(
           (select ks.dept_name
              from his.dept_dict ks
             where ks.dept_code = nvl(t.consultation_dept, nvl(t2.dept_discharge_from, t2.dept_admission_to))
               and rownum = 1),
           (select ks.qmpt_name
              from his.dept_dict ks
             where ks.dept_code = nvl(t.consultation_dept, nvl(t2.dept_discharge_from, t2.dept_admission_to))
               and rownum = 1)
       ) as DEP_NAME,--  科室名称  是

       t2.discharge_ward_code as AREA_NAME,-- 病区名称

       cast(null as varchar2(10)) as WARD_NUM,--  病房号

       substr(t2.discharge_bed_no, 1, 10) as SICKBED_NUM,-- 病床号

       substr(
           nvl(t.consultation_explain, '-'),
           1,
           2000
       ) as MEDICAL_RECORDS_SUNNARY,-- 病历摘要  是 病情以及治疗情况概述

       substr(
           nvl(t1.consultation_idea, '-'),
           1,
           2000
       ) as DIA_TREAT_NAME,--  诊疗过程名称  是

       substr(
           nvl(t1.consultation_idea, '-'),
           1,
           2000
       ) as TREAT_NOTE,--  诊疗过程描述  是

       case
         when trim(t.consultation_type) in ('1','2','3','4','5')
           then trim(t.consultation_type)
         when regexp_like(t.consultation_type, '急')
           then '1'
         when regexp_like(t.consultation_type, '院外')
           then '3'
         when regexp_like(t.consultation_type, '多科|多学科|MDT')
           then '4'
         when regexp_like(t.consultation_type, '指名')
           then '5'
         else '2'
       end as CONSULTATION_TYPE,-- 会诊类型  是 1：急会诊 2：普通会诊 3：院外会诊4：多科会诊 5：指名会诊

       substr(
           nvl(t.consultation_explain, '-'),
           1,
           2000
       ) as CONSULTATION_REASON,-- 会诊原因和目的 是

       substr(
           nvl(
               (select yg.name
                  from his.staff_dict yg
                 where yg.emp_no = t.consultation_apply_doctor
                   and rownum = 1),
               t.consultation_apply_doctor
           ),
           1,
           50
       ) as CONSULTATION_APP_DOC_NAME,-- 会诊申请医师签名  是

       substr(
           nvl(
               (select ks.dept_name
                  from his.dept_dict ks
                 where ks.dept_code = t.consultation_dept
                   and rownum = 1),
               t.consultation_dept
           ),
           1,
           50
       ) as CONSULTATION_APP_DEP,--  会诊申请科室名称

       '山东省第二人民医院' as CONSULTATION_APP_ORG_NAME,-- 会诊申请医疗机构名称

       cast(nvl(t.apply_date_time, t.consultation_date_time) as date) as CONSULTATION_APPLAY_DATE,--  发起会诊申请时间  是 YYYYMMDD HHMISS

       substr(
           nvl(t1.consultation_idea, '-'),
           1,
           2000
       ) as CONSULTATION_OPINION,--  会诊意见和建议 是

       substr(
           nvl(
               (select yg.name
                  from his.staff_dict yg
                 where yg.emp_no = t1.consultation_doctor
                   and rownum = 1),
               t1.consultation_doctor
           ),
           1,
           50
       ) as CONSULTATION_DOC_NAME,-- 会诊医师签名

       substr(
           nvl(
               (select ks.dept_name
                  from his.dept_dict ks
                 where ks.dept_code = t1.consultation_dept
                   and rownum = 1),
               t1.consultation_dept
           ),
           1,
           50
       ) as CONSULTATION_DEP_NAME,-- 会诊科室名称  是

       '山东省第二人民医院' as CONSULTATION_DOC_ORG_NAME,-- 会诊医师所在医疗机构名称

       '山东省第二人民医院' as CONSULTATION_ORG_NAME,-- 会诊所在医疗机构名称    会诊地点(网络会诊填写申请机构地址)

       cast(nvl(t.consultation_date_time, t.apply_date_time) as date) as CONSULTATION_DATE --会诊日期时间  是 YYYYMMDD HHMISS

from his.consultation_doctor_master t

inner join his.consultation_doctor_detail t1
        on t.consultation_id = t1.consultation_id

left join his.pat_visit t2
       on t.patient_id = t2.patient_id
      and t.visit_id = t2.visit_id

where t2.discharge_date_time >= to_date('2021-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss')
  and t2.discharge_date_time <  to_date('2025-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss')
