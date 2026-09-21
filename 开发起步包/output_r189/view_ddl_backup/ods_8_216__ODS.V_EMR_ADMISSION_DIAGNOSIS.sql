
  CREATE OR REPLACE FORCE VIEW "ODS"."V_EMR_ADMISSION_DIAGNOSIS" ("ID", "ADMISSION_ID", "PRI_DIA_MARK", "DIAGNOSIS_TYPE_CODE", "DIAGNOSIS_TYPE_NAME", "DISEASE_CODE", "DISEASE", "DIAGNOSIS_NO", "DIAGNOSIS_BASIS", "DIAGNOSIS_DATE", "DOCTOR_ID_NUM", "DOCTOR_NAME", "DEP_CODE", "DEP_NAME", "DISTRICT_CODE", "EXCHANGE_TYPE", "SYSTEM_TIME", "ORG_CODE", "ORG_NAME", "NAME", "SEX_CODE", "ID_NUM", "LOCAL_DIAGNOSIS_CODE", "LOCAL_DIAGNOSIS_NAME", "DIAG_DOC_CERTIFICATE_NO") AS 
  select substr(
           nvl('49557032X'||'|'||
               nvl(to_char(t.patient_id), '-')||'|'||
               nvl(to_char(t.visit_id), '-')||'|'||
               nvl(to_char(t.diagnosis_type), '-')||'|'||
               nvl(to_char(t.diagnosis_no), '-'), '-'),
           1,
           100
       ) as ID,--  内码  是 主键

       substr(
           nvl(to_char(t.patient_id), '-')||'|'||nvl(to_char(t.visit_id), '-'),
           1,
           20
       ) as ADMISSION_ID,--  本次住院标识号 是 某一次住院唯一标识号

       '2' as PRI_DIA_MARK,--  中医/西医诊断标志 是

       case
           when t.diagnosis_type = '2' and to_char(t.diagnosis_no) = '1' then '1'
           when t.diagnosis_type = '2' then '2'
           else '3'
       end as DIAGNOSIS_TYPE_CODE,--疾病诊断类型代码  是 1：主要诊断 2;初步诊断 3：其他诊断

       case
           when t.diagnosis_type = '2' and to_char(t.diagnosis_no) = '1' then '主要诊断'
           when t.diagnosis_type = '2' then '初步诊断'
           else '其他诊断'
       end as DIAGNOSIS_TYPE_NAME,-- 疾病诊断类型名称  是

       substr(
           nvl(
               nullif(trim(diag_dict.std_code), ''),
               nvl(nullif(trim(to_char(t.diagnosis_code)), ''), '-')
           ),
           1,
           12
       ) as DISEASE_CODE,--  疾病诊断代码  是

       substr(
           nvl(
               nullif(trim(diag_dict.std_name), ''),
               nvl(nullif(trim(to_char(t.diagnosis_desc)), ''), '-')
           ),
           1,
           50
       ) as DISEASE,-- 疾病诊断名称  是

       substr(
           nvl(nullif(trim(to_char(t.diagnosis_no)), ''), '-'),
           1,
           1
       ) as DIAGNOSIS_NO,--  诊断序号  是 主诊断为1其它依次排序赋值

       substr(
           nvl(nullif(trim('-'), ''), '-'),
           1,
           4000
       ) as DIAGNOSIS_BASIS,-- 最高诊断依据  是

       cast(
           nvl(t.diagnosis_date, t1.admission_date_time)
           as date
       ) as DIAGNOSIS_DATE,--  诊断日期  是

       substr(
           nvl(
               nullif(
                   trim(
                       (select yg.id_no
                          from his.staff_dict yg
                         where yg.emp_no = t1.doctor_in_charge
                           and rownum = 1)
                   ),
                   ''
               ),
               '-'
           ),
           1,
           18
       ) as DOCTOR_ID_NUM,-- 诊断医师身份证号    诊断医师的身份证号

       substr(
           nvl(
               nullif(
                   trim(
                       (select yg.name
                          from his.staff_dict yg
                         where yg.emp_no = t1.doctor_in_charge
                           and rownum = 1)
                   ),
                   ''
               ),
               '-'
           ),
           1,
           50
       ) as DOCTOR_NAME,-- 诊断医师姓名  是 诊断医师的姓名

       substr(
           nvl(
               nullif(
                   trim(
                       (select ks.qmpt_code
                          from his.dept_dict ks
                         where ks.dept_code = nvl(t1.dept_discharge_from, t1.dept_admission_to)
                           and rownum = 1)
                   ),
                   ''
               ),
               nvl(nullif(trim(nvl(t1.dept_discharge_from, t1.dept_admission_to)), ''), '-')
           ),
           1,
           20
       ) as DEP_CODE,--  科室代码  是 按照平台值域填写

       substr(
           nvl(
               nullif(
                   trim(
                       (select ks.qmpt_name
                          from his.dept_dict ks
                         where ks.dept_code = nvl(t1.dept_discharge_from, t1.dept_admission_to)
                           and rownum = 1)
                   ),
                   ''
               ),
               nvl(
                   nullif(
                       trim(
                           (select ks.dept_name
                              from his.dept_dict ks
                             where ks.dept_code = nvl(t1.dept_discharge_from, t1.dept_admission_to)
                               and rownum = 1)
                       ),
                       ''
                   ),
                   '-'
               )
           ),
           1,
           50
       ) as DEP_NAME,--  科室名称  是

       '370104' as DISTRICT_CODE,-- 所属行政区划  是 按机构所在的行政区划（区县）

       'INSERT' as EXCHANGE_TYPE,-- 交换类型  是 INSERT：向平台传新数据时 UPDATE：向平台更新某条数据时 DELETE：从平台删除某条数据时 ADDHIS:向平台补充历史遗漏数据

       cast(systimestamp as timestamp) as SYSTEM_TIME,-- 数据上传时间戳 是 按照当前时间上传

       '49557032X' as ORG_CODE,--  医院组织机构代码  是

       '山东省第二人民医院' as ORG_NAME,--  医院名称  是

       substr(
           nvl(nullif(trim(t2.name), ''), '-'),
           1,
           50
       ) as NAME,--  患者姓名  是 通过比对国家数据集增加的数据项

       substr(
           nvl(
               nullif(
                   trim(decode(t2.sex, '男', '1', '女', '2', '未知', '0', '9')),
                   ''
               ),
               '9'
           ),
           1,
           1
       ) as SEX_CODE,--  患者性别代码  是 通过比对国家数据集增加的数据项，值域：0未知，1男，2女，9不明

       substr(
           nvl(nullif(trim(t2.id_no), ''), '000000000000000000'),
           1,
           18
       ) as ID_NUM,--  患者身份证件号码  是 通过比对国家数据集增加的数据项，全部身份证件号码填写到该字段

       substr(
           nvl(nullif(trim(t.diagnosis_code), ''), '-'),
           1,
           100
       ) as LOCAL_DIAGNOSIS_CODE,--  机构内部诊断编码  是 通过比对国家数据集增加的数据项

       substr(
           nvl(nullif(trim(t.diagnosis_desc), ''), '-'),
           1,
           100
       ) as LOCAL_DIAGNOSIS_NAME,--  机构内部诊断名称  是 通过比对国家数据集增加的数据项

       substr(
           nvl(
               nullif(
                   trim(
                       (select yg.practice_cert_code
                          from doc_register_emp_match yg
                         where yg.emp_no = t1.doctor_in_charge
                           and rownum = 1)
                   ),
                   ''
               ),
               '-'
           ),
           1,
           100
       ) as DIAG_DOC_CERTIFICATE_NO -- 诊断医生执业证书编号  是 通过比对国家数据集增加的数据项

from his.diagnosis t
left join his.pat_visit t1
       on t.patient_id = t1.patient_id
      and t.visit_id = t1.visit_id
left join his.pat_master_index t2
       on t.patient_id = t2.patient_id
left join (
        select trim(to_char(院标编码)) as local_code,
               max(nullif(trim(to_char(国标编码)), '')) as std_code,
               max(nullif(trim(to_char(国标名称)), '')) as std_name
          from cda.cda_dictionary
         where 字典名称 = 'ICD-10诊断编码'
           and 系统标识 = 'HIS'
           and trim(to_char(院标编码)) is not null
         group by trim(to_char(院标编码))
       ) diag_dict
       on diag_dict.local_code = trim(to_char(t.diagnosis_code))
where t1.discharge_date_time >= to_date('2021-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss')
  and t1.discharge_date_time <  to_date('2025-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss')
  and t.diagnosis_type = '2'
