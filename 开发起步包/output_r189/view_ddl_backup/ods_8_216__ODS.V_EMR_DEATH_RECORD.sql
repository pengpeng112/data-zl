
  CREATE OR REPLACE FORCE VIEW "ODS"."V_EMR_DEATH_RECORD" ("ID", "ORG_CODE", "ORG_NAME", "DEP_CODE", "DEP_NAME", "SEX_CODE", "SEX_NAME", "ID_TYPE", "ID_NO", "BIRTH_DATE", "AGE", "VISITING_NUM", "PATIENT_TYPE_CODE", "PATIENT_TYPE_NAME", "AUDIT_DATE", "DISEASE_CODE", "DISEASE_NAME", "OBODE_DETAIL", "DEATH_DATE", "BASIC_CAUSE_CODE", "BASIC_CAUSE", "INPATIENT_DAY", "DOCTOR_NAME", "DOC_ID_NUM", "DISTRICT_CODE", "EXCHANGE_TYPE", "SYSTEM_TIME") AS 
  select
       cast(
           substrb(
               '49557032X' || '|' || pv.patient_id || '|' || pv.visit_id,
               1,
               100
           ) as varchar2(100)
       ) as ID,--主键 是；机构码|患者ID|住院次数

       cast('49557032X' as varchar2(32)) as ORG_CODE,--医院组织机构代码 是

       cast('山东省第二人民医院' as varchar2(70)) as ORG_NAME,--医院名称 是

       cast(
           substrb(
               nvl(
                   to_char(pv.dept_discharge_from),
                   nvl(to_char(pv.dept_admission_to), to_char(doc.p_dept_code))
               ),
               1,
               20
           ) as varchar2(20)
       ) as DEP_CODE,--科室代码 是；优先出院科室，其次入院科室，再取文书科室

       cast(
           substrb(
               nvl(
                   (
                       select max(dd.dept_name)
                         from his.dept_dict dd
                        where to_char(dd.dept_code) =
                              nvl(
                                  to_char(pv.dept_discharge_from),
                                  nvl(to_char(pv.dept_admission_to), to_char(doc.p_dept_code))
                              )
                   ),
                   nvl(to_char(doc.p_dept_name), '-')
               ),
               1,
               50
           ) as varchar2(50)
       ) as DEP_NAME,--科室名称 是

       cast(
           decode(pmi.sex, '男', '1', '女', '2', '未知', '0', '9')
           as varchar2(1)
       ) as SEX_CODE,--性别代码 是

       cast(
           decode(pmi.sex, '男', '男', '女', '女', '未知', '未知', '不明')
           as varchar2(10)
       ) as SEX_NAME,--性别名称 是

       cast('01' as varchar2(5)) as ID_TYPE,--身份证件类型 是；01居民身份证

       cast(
           substrb(
               case
                   when regexp_like(trim(to_char(pmi.id_no)), '^[0-9]{17}[0-9Xx]$|^[0-9]{15}$')
                   then upper(trim(to_char(pmi.id_no)))
                   else '000000000000000000'
               end,
               1,
               100
           ) as varchar2(100)
       ) as ID_NO,--身份证号 是

       to_char(pmi.date_of_birth, 'yyyy-mm-dd hh24:mi:ss') as BIRTH_DATE,--出生日期 是；统一时间格式

       cast(
           substrb(
               case
                   when pmi.date_of_birth is not null
                    and nvl(pv.discharge_date_time, nvl(doc.doc_create_date, pv.admission_date_time)) is not null
                   then to_char(
                            trunc(
                                months_between(
                                    nvl(pv.discharge_date_time, nvl(doc.doc_create_date, pv.admission_date_time)),
                                    pmi.date_of_birth
                                ) / 12
                            )
                        )
                   else '-'
               end,
               1,
               3
           ) as varchar2(3)
       ) as AGE,--年龄 是

       cast(
           substrb(
               pv.patient_id || '|' || pv.visit_id,
               1,
               100
           ) as varchar2(100)
       ) as VISITING_NUM,--就诊号 是；本次入院标识

       cast('2' as char(1)) as PATIENT_TYPE_CODE,--病人类型代码 是；2住院，需按平台CC99.00005确认

       cast('住院' as varchar2(50)) as PATIENT_TYPE_NAME,--病人类型 是

       to_char(pv.admission_date_time, 'yyyy-mm-dd hh24:mi:ss') as AUDIT_DATE,--就诊/入院日期 是

       cast(
           substrb(
               nvl(
                   (
                       select max(to_char(cd.国标编码))
                         from cda.cda_dictionary cd
                        where cd.字典名称 = 'ICD-10诊断编码'
                          and cd.系统标识 = 'HIS'
                          and cd.院标编码 = dmain.diagnosis_code
                   ),
                   nvl(
                       (
                           select max(to_char(cd.国标编码))
                             from cda.cda_dictionary cd
                            where cd.字典名称 = 'ICD-10诊断编码'
                              and cd.系统标识 = 'HIS'
                              and cd.院标名称 = dmain.diagnosis_desc
                       ),
                       nvl(to_char(dmain.diagnosis_code), '-')
                   )
               ),
               1,
               12
           ) as varchar2(12)
       ) as DISEASE_CODE,--疾病诊断代码 是；优先出院主诊断标准编码

       cast(
           substrb(
               nvl(
                   (
                       select max(to_char(cd.国标名称))
                         from cda.cda_dictionary cd
                        where cd.字典名称 = 'ICD-10诊断编码'
                          and cd.系统标识 = 'HIS'
                          and cd.院标编码 = dmain.diagnosis_code
                   ),
                   nvl(
                       (
                           select max(to_char(cd.国标名称))
                             from cda.cda_dictionary cd
                            where cd.字典名称 = 'ICD-10诊断编码'
                              and cd.系统标识 = 'HIS'
                              and cd.院标名称 = dmain.diagnosis_desc
                       ),
                       nvl(to_char(dmain.diagnosis_desc), '-')
                   )
               ),
               1,
               100
           ) as varchar2(100)
       ) as DISEASE_NAME,--疾病诊断名称 是；优先出院主诊断标准名称

       cast(substrb(coalesce(to_char(pv.patient_area_address), to_char(pmi.patient_area_address), to_char(pv.mailing_address), to_char(pmi.mailing_address)), 1, 200) as varchar2(200)) as OBODE_DETAIL,--家庭住址 是；来源暂不明确，先置-

       to_char(
           nvl(pv.discharge_date_time, doc.doc_create_date),
           'yyyy-mm-dd hh24:mi:ss'
       ) as DEATH_DATE,--死亡时间 是；优先出院时间，空时取死亡文书创建时间

       cast(
           substrb(
               nvl(
                   (
                       select max(to_char(cd.国标编码))
                         from cda.cda_dictionary cd
                        where cd.字典名称 = 'ICD-10诊断编码'
                          and cd.系统标识 = 'HIS'
                          and cd.院标编码 = dmain.diagnosis_code
                   ),
                   nvl(
                       (
                           select max(to_char(cd.国标编码))
                             from cda.cda_dictionary cd
                            where cd.字典名称 = 'ICD-10诊断编码'
                              and cd.系统标识 = 'HIS'
                              and cd.院标名称 = dmain.diagnosis_desc
                       ),
                       nvl(to_char(dmain.diagnosis_code), '-')
                   )
               ),
               1,
               200
           ) as varchar2(200)
       ) as BASIC_CAUSE_CODE,--根本死亡原因代码 是；暂取出院主诊断

       cast(
           substrb(
               nvl(
                   (
                       select max(to_char(cd.国标名称))
                         from cda.cda_dictionary cd
                        where cd.字典名称 = 'ICD-10诊断编码'
                          and cd.系统标识 = 'HIS'
                          and cd.院标编码 = dmain.diagnosis_code
                   ),
                   nvl(
                       (
                           select max(to_char(cd.国标名称))
                             from cda.cda_dictionary cd
                            where cd.字典名称 = 'ICD-10诊断编码'
                              and cd.系统标识 = 'HIS'
                              and cd.院标名称 = dmain.diagnosis_desc
                       ),
                       nvl(to_char(dmain.diagnosis_desc), '-')
                   )
               ),
               1,
               2000
           ) as varchar2(2000)
       ) as BASIC_CAUSE,--根本死亡原因 是；暂取出院主诊断

       cast(
           substrb(
               case
                   when pv.admission_date_time is not null
                    and nvl(pv.discharge_date_time, doc.doc_create_date) is not null
                   then to_char(
                            greatest(
                                1,
                                trunc(nvl(pv.discharge_date_time, doc.doc_create_date))
                                - trunc(pv.admission_date_time)
                                + 1
                            )
                        )
                   else '-'
               end,
               1,
               5
           ) as varchar2(5)
       ) as INPATIENT_DAY,--住院天数 是

       cast(
           substrb(
               nvl(
                   (
                       select max(sd.name)
                         from his.staff_dict sd
                        where to_char(sd.emp_no) = to_char(pv.attending_doctor)
                           or to_char(sd.name) = to_char(pv.attending_doctor)
                   ),
                   nvl(to_char(pv.attending_doctor), nvl(to_char(doc.createby), '-'))
               ),
               1,
               50
           ) as varchar2(50)
       ) as DOCTOR_NAME,--医师姓名 是；优先主治医师

       cast(
           substrb(
               nvl(
                   (
                       select max(sd.id_no)
                         from his.staff_dict sd
                        where to_char(sd.emp_no) = to_char(pv.attending_doctor)
                           or to_char(sd.name) = to_char(pv.attending_doctor)
                   ),
                   '-'
               ),
               1,
               18
           ) as varchar2(18)
       ) as DOC_ID_NUM,--医生身份证号

       cast('370104' as varchar2(6)) as DISTRICT_CODE,--所属行政区划 是

       cast('ADDHIS' as varchar2(10)) as EXCHANGE_TYPE,--交换类型 是

       to_char(sysdate, 'yyyy-mm-dd hh24:mi:ss') as SYSTEM_TIME--数据上传时间戳 是；统一时间格式

  from (
        select *
          from (
                select t.uhid,
                       t.p_inpatient_no,
                       t.p_inpatient_times,
                       t.p_dept_code,
                       t.p_dept_name,
                       t1.doc_create_date,
                       t1.modifiedon,
                       t1.createby,
                       row_number() over (
                           partition by t.p_inpatient_no, t.p_inpatient_times
                           order by t1.doc_create_date desc nulls last,
                                    t1.modifiedon desc nulls last,
                                    t.uhid desc
                       ) as rn
                  from mtl.epr_inpatient_docindex t
                  join mtl.epr_inpatient t1
                    on t.uhid = t1.uhid
                 where (
                           t1.doc_type_name like '%死亡记录%'
                        or t1.doc_type_name like '%死亡病例讨论记录%'
                       )
               )
         where rn = 1
       ) doc

  join his.pat_master_index pmi
    on pmi.inp_no = doc.p_inpatient_no
  join his.pat_visit pv
    on pv.patient_id = pmi.patient_id
   and to_char(pv.visit_id) = to_char(doc.p_inpatient_times)

  left join (
        select d.patient_id,
               d.visit_id,
               max(to_char(d.diagnosis_code)) keep (
                   dense_rank first
                   order by case when nvl(d.diagnosis_no, 0) = 1 then 1 else 2 end,
                            nvl(d.diagnosis_no, 99)
               ) as diagnosis_code,
               max(to_char(d.diagnosis_desc)) keep (
                   dense_rank first
                   order by case when nvl(d.diagnosis_no, 0) = 1 then 1 else 2 end,
                            nvl(d.diagnosis_no, 99)
               ) as diagnosis_desc
          from his.diagnosis d
         where to_char(d.diagnosis_type) = '3'
         group by d.patient_id,
                  d.visit_id
       ) dmain
    on dmain.patient_id = pv.patient_id
   and dmain.visit_id = pv.visit_id
