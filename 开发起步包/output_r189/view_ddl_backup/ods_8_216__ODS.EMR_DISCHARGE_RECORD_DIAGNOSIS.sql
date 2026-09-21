
  CREATE OR REPLACE FORCE VIEW "ODS"."EMR_DISCHARGE_RECORD_DIAGNOSIS" ("ID", "DR_ID", "SN", "DIAGNOSIS_TYPE", "DIAGNOSIS_TYPENAME", "DISEASE_CODE", "DISEASE", "DIAGNOSIS_BASIS", "CONFIRMED_DATE", "CREATED_AT", "DISTRICT_CODE", "EXCHANGE_TYPE", "SYSTEM_TIME", "ORG_CODE", "ORG_NAME", "ADMISSION_ID", "NAME", "SEX_CODE", "ID_NUM", "LOCAL_DIAGNOSIS_CODE", "LOCAL_DIAGNOSIS_NAME", "DIAG_DOC_CERTIFICATE_NO") AS 
  select substr(
           '49557032X'||'|'||
           nvl(to_char(t.patient_id), '-')||'|'||
           nvl(to_char(t.visit_id), '-')||'|'||
           nvl(to_char(t.diagnosis_type), '-')||'|'||
           nvl(to_char(t.diagnosis_no), '-'),
           1,
           100
       ) as ID,--  内码  是 主键

       substr(
           '49557032X'||'|'||
           nvl(to_char(t.patient_id), '-')||'|'||
           nvl(to_char(t.visit_id), '-'),
           1,
           100
       ) as DR_ID,--  出院记录内码 是 校验是否存在从表数据关联不到主表的数据

       nvl(t.diagnosis_no, 1) as SN,--  序号  是 多个诊断多条记录，主诊断传1其它依次排序上传

       '2' as DIAGNOSIS_TYPE,--  疾病诊断类型  是 1中医，2西医

       '西医' as DIAGNOSIS_TYPENAME,--  疾病诊断类型名称  是

       substr(
           nvl(
               nullif(trim(diag_dict.std_code), ''),
               nvl(nullif(trim(to_char(t.diagnosis_code)), ''), '-')
           ),
           1,
           12
       ) as DISEASE_CODE,--  疾病诊断代码 西医ICD10/中医2021版诊断编码

       substr(
           nvl(
               nullif(trim(diag_dict.std_name), ''),
               nvl(nullif(trim(to_char(t.diagnosis_desc)), ''), '-')
           ),
           1,
           50
       ) as DISEASE,-- 疾病诊断名称  是 疾病诊断名称

       cast(null as varchar2(100)) as DIAGNOSIS_BASIS,-- 诊断依据

       cast(
           nvl(t.diagnosis_date, t1.discharge_date_time)
           as date
       ) as CONFIRMED_DATE,--  确诊日期  是 业务日期，字符型改为时间类型

       cast(null as timestamp) as CREATED_AT,--  创建时间 平台自动生成，不需要填写

       '370104' as DISTRICT_CODE,-- 所属行政区划  是 按机构所在的行政区划（区县）

       'INSERT' as EXCHANGE_TYPE,-- 交换类型  是 INSERT：向平台传新数据时 UPDATE：向平台更新某条数据时 DELETE：从平台删除某条数据时

       cast(systimestamp as timestamp) as SYSTEM_TIME,-- 数据上传时间戳

       '49557032X' as ORG_CODE,--  医院组织机构代码  是 必填项，医院代码

       '山东省第二人民医院' as ORG_NAME,--  医院名称  是 必填项，医院名称

       substr(
           nvl(to_char(t.patient_id), '-')||'|'||nvl(to_char(t.visit_id), '-'),
           1,
           20
       ) as ADMISSION_ID,--  本次住院标识号 是 通过比对国家数据集增加的数据项，住院号不能为空,如果脚本存在数据

       substr(
           nvl(nullif(trim(cast(t2.name as varchar2(50))), ''), '-'),
           1,
           50
       ) as NAME,--  患者姓名  是 通过比对国家数据集增加的数据项

       substr(
           case
               when cast(t2.sex as varchar2(10)) = '男' then '1'
               when cast(t2.sex as varchar2(10)) = '女' then '2'
               when cast(t2.sex as varchar2(10)) = '未知' then '0'
               else '9'
           end,
           1,
           1
       ) as SEX_CODE,--  患者性别代码  是 通过比对国家数据集增加的数据项

       substr(
           nvl(nullif(trim(cast(t2.id_no as varchar2(18))), ''), '000000000000000000'),
           1,
           18
       ) as ID_NUM,--  患者身份证件号码  是 通过比对国家数据集增加的数据项，全部身份证件号码填写到该字段

       substr(
           cast(t.diagnosis_code as varchar2(100)),
           1,
           100
       ) as LOCAL_DIAGNOSIS_CODE,--  机构内部诊断编码 通过比对国家数据集增加的数据项

       substr(
           nvl(nullif(trim(cast(t.diagnosis_desc as varchar2(100))), ''), '-'),
           1,
           100
       ) as LOCAL_DIAGNOSIS_NAME,--  机构内部诊断名称 s 通过比对国家数据集增加的数据项

       substr(
           nvl(
               nullif(
                   trim(
                       cast(
                           (select yg.practice_cert_code
                              from doc_register_emp_match yg
                             where yg.emp_no = nvl(
                                               t.doctor_code,
                                               nvl(t1.attending_doctor, t1.doctor_in_charge)
                                           )
                               and rownum = 1)
                           as varchar2(100)
                       )
                   ),
                   ''
               ),
               '-'
           ),
           1,
           100
       ) as DIAG_DOC_CERTIFICATE_NO --诊断医生执业证书编号  是 通过比对国家数据集增加的数据项

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

where t.diagnosis_type = '3'
  and t1.discharge_date_time >= to_date('2021-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss')
  and t1.discharge_date_time <  to_date('2025-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss')
  and t.diagnosis_code is not null
