
  CREATE OR REPLACE FORCE VIEW "ODS"."V_EMR_DISCHARGE_RECORD" ("ID", "ORG_CODE", "ORG_NAME", "DEP_CODE", "DEP_NAME", "HOS_DEP_CODE", "HOS_DEP_NAME", "ADMISSION_NUM", "ADMISSION_ID", "OTHER_ID_TYPE", "OTHER_ID_TYPENAME", "OTHER_ID_NUM", "ID_NUM", "NAME", "SEX_CODE", "SEX_NAME", "AGE", "AGE_MONTH", "AGE_DAY", "AGE_HOUR", "ADMISSION_DATE", "DISCHARGE_DATE", "INPATIENT_DAY", "ADMISSION_SITUATION", "DIAG_TREAT_PLAN", "TREAT_PROCESS", "DISCHARGE_SITUATION", "DISCHARGE_ORDER", "DISCHARGE_DIAGNOSIS", "DISCHARGE_DIAGNOSIS_CODE", "CHARACT_CASES", "DOCTOR_CODE", "DOCTOR_NAME", "SUPERIOR_DOC_NAME", "WARD", "SICKBED_NUM", "FOUR_DIAGNOSIS", "TREATMENT_METHOD", "TCM_DECOCTION_METHOD", "MEDICATION_METHOD", "DISCHARGE_SIGNS", "CITIZEN_ID", "EFFECTIVE_TIME", "STATUS", "CREATED_AT", "DISTRICT_CODE", "EXCHANGE_TYPE", "DEI", "NODE_CODE", "SYSTEM_TIME", "AR_ID", "DOC_ID_NUM", "DISCHARGE_TIME", "AUTO_LEAVE_HOS", "IS24HRADM_DISCH", "DESTINATION_CODE", "DESTINATION_DESC", "DISCHARGE_STATUS", "DISCHARGE_STATUS_NAME", "ATTEND_DOC_CERTIFICATE_NO", "DISCHARGE_CONDITION", "DISCHARGE_HP_TEXT") AS 
  select ID,
       ORG_CODE,
       ORG_NAME,
       DEP_CODE,
       DEP_NAME,
       HOS_DEP_CODE,
       HOS_DEP_NAME,
       ADMISSION_NUM,
       ADMISSION_ID,
       OTHER_ID_TYPE,
       OTHER_ID_TYPENAME,
       OTHER_ID_NUM,
       ID_NUM,
       NAME,
       SEX_CODE,
       SEX_NAME,
       AGE,
       AGE_MONTH,
       AGE_DAY,
       AGE_HOUR,
       ADMISSION_DATE,
       DISCHARGE_DATE,
       INPATIENT_DAY,
       ADMISSION_SITUATION,
       DIAG_TREAT_PLAN,
       TREAT_PROCESS,
       DISCHARGE_SITUATION,
       DISCHARGE_ORDER,
       DISCHARGE_DIAGNOSIS,
       DISCHARGE_DIAGNOSIS_CODE,
       CHARACT_CASES,
       DOCTOR_CODE,
       DOCTOR_NAME,
       SUPERIOR_DOC_NAME,
       WARD,
       SICKBED_NUM,
       FOUR_DIAGNOSIS,
       TREATMENT_METHOD,
       TCM_DECOCTION_METHOD,
       MEDICATION_METHOD,
       DISCHARGE_SIGNS,
       CITIZEN_ID,
       EFFECTIVE_TIME,
       STATUS,
       CREATED_AT,
       DISTRICT_CODE,
       EXCHANGE_TYPE,
       DEI,
       NODE_CODE,
       SYSTEM_TIME,
       AR_ID,
       DOC_ID_NUM,
       DISCHARGE_TIME,
       AUTO_LEAVE_HOS,
       IS24HRADM_DISCH,
       DESTINATION_CODE,
       DESTINATION_DESC,
       DISCHARGE_STATUS,
       DISCHARGE_STATUS_NAME,
       ATTEND_DOC_CERTIFICATE_NO,
       DISCHARGE_CONDITION,
       DISCHARGE_HP_TEXT
from (
    select q.*,
           row_number() over (
               partition by q.ID
               order by
                   case
                       when q.DISCHARGE_HP_TEXT is not null
                        and q.DISCHARGE_HP_TEXT <> '-'
                       then 0
                       else 1
                   end,
                   q.DISCHARGE_TIME desc nulls last,
                   q.AR_ID desc nulls last
           ) as rn
    from (
select substr(
           '49557032X'||'|'||
           nvl(to_char(t.patient_id), '-')||'|'||
           nvl(to_char(t.visit_id), '-'),
           1,
           100
       ) as ID,--  内码  是 主键

       '49557032X' as ORG_CODE,--  医院组织机构代码  是 是直报中的组织机构代码，必须为9位数字或字母

       '山东省第二人民医院' as ORG_NAME,--  医院名称  是 填写标准医院名称，每次上传的医院名称必须一致

       substr(
           nvl(
               nullif(
                   trim(
                       cast(
                           (select ks.qmpt_code
                              from his.dept_dict ks
                             where ks.dept_code = t.dept_discharge_from
                               and rownum = 1)
                           as varchar2(20)
                       )
                   ),
                   ''
               ),
               '-'
           ),
           1,
           20
       ) as DEP_CODE,--  科室代码  是 出院科室

       substr(
           nvl(
               nullif(
                   trim(
                       cast(
                           (select ks.qmpt_name
                              from his.dept_dict ks
                             where ks.dept_code = t.dept_discharge_from
                               and rownum = 1)
                           as varchar2(50)
                       )
                   ),
                   ''
               ),
               '-'
           ),
           1,
           50
       ) as DEP_NAME,--  科室名称  是 出院科室

       substr(
           nvl(nullif(trim(cast(t.dept_discharge_from as varchar2(20))), ''), '-'),
           1,
           20
       ) as HOS_DEP_CODE,--  院内科室代码  是

       substr(
           nvl(
               nullif(
                   trim(
                       cast(
                           (select ks.dept_name
                              from his.dept_dict ks
                             where ks.dept_code = t.dept_discharge_from
                               and rownum = 1)
                           as varchar2(50)
                       )
                   ),
                   ''
               ),
               '-'
           ),
           1,
           50
       ) as HOS_DEP_NAME,--  院内科室名称  是

       substr(
           nvl(nullif(trim(cast(t1.inp_no as varchar2(20))), ''), '-'),
           1,
           20
       ) as ADMISSION_NUM,-- 住院号 是

       substr(
           nvl(to_char(t.patient_id), '-')||'|'||nvl(to_char(t.visit_id), '-'),
           1,
           20
       ) as ADMISSION_ID,--  本次住院标识号 是

       case
           when t1.id_no is null then cast(null as varchar2(5))
           else substr(
                    nvl(
                        (select cast(zd.国标编码 as varchar2(5))
                           from cda.cda_dictionary zd
                          where cast(zd.字典名称 as varchar2(100)) = '身份证件类型代码'
                            and cast(zd.院标编码 as varchar2(100)) = cast(t1.id_type as varchar2(100))
                            and rownum = 1),
                        '99'
                    ),
                    1,
                    5
                )
       end as OTHER_ID_TYPE,-- 身份证件类型 按照平台的值域进行填写，如果身份证件号码为空，则此字段不需要填写

       case
           when t1.id_no is null then cast(null as varchar2(32))
           else substr(
                    nvl(
                        (select cast(zd.国标名称 as varchar2(32))
                           from cda.cda_dictionary zd
                          where cast(zd.字典名称 as varchar2(100)) = '身份证件类型代码'
                            and cast(zd.院标编码 as varchar2(100)) = cast(t1.id_type as varchar2(100))
                            and rownum = 1),
                        '其他法定有效证件'
                    ),
                    1,
                    32
                )
       end as OTHER_ID_TYPENAME,-- 身份证件名称

       substr(cast(t1.id_no as varchar2(18)), 1, 18) as OTHER_ID_NUM,--  其他身份证件号码

       substr(
           nvl(nullif(trim(cast(t1.id_no as varchar2(18))), ''), '000000000000000000'),
           1,18 ) as ID_NUM,--  身份证件号码 所有身份证件号码填写到该字段

       substr(
           nvl(nullif(trim(cast(t1.name as varchar2(50))), ''), '-'),
           1,
           50
       ) as NAME,--  姓名  是 姓名

       substr(
           case
               when cast(t1.sex as varchar2(10)) = '男' then '1'
               when cast(t1.sex as varchar2(10)) = '女' then '2'
               when cast(t1.sex as varchar2(10)) = '未知' then '0'
               else '9'
           end,
           1,
           1
       ) as SEX_CODE,--  性别代码 值域：0未知，1男，2女，9不明

       substr(
           case
               when cast(t1.sex as varchar2(10)) = '男' then '男'
               when cast(t1.sex as varchar2(10)) = '女' then '女'
               when cast(t1.sex as varchar2(10)) = '未知' then '未知'
               else '不明'
           end,
           1,
           50
       ) as SEX_NAME,--  性别

       case
           when t1.date_of_birth is not null
            and t.admission_date_time is not null
            and trunc(months_between(t.admission_date_time, t1.date_of_birth) / 12) between 1 and 200
           then trunc(months_between(t.admission_date_time, t1.date_of_birth) / 12)
       end as AGE,-- 年龄 必须为整数，范围在1-200之间，如果不足一岁，请空置

       case
           when t1.date_of_birth is not null
            and t.admission_date_time is not null
            and months_between(t.admission_date_time, t1.date_of_birth) >= 1
            and months_between(t.admission_date_time, t1.date_of_birth) < 12
           then greatest(trunc(months_between(t.admission_date_time, t1.date_of_birth)), 1)
           else 0
       end as AGE_MONTH,-- 年龄（月） 不足一岁时填写，在1-12范围内的整数

       case
           when t1.date_of_birth is not null
            and t.admission_date_time is not null
            and months_between(t.admission_date_time, t1.date_of_birth) < 1
           then greatest(trunc(t.admission_date_time - t1.date_of_birth), 1)
           else 0
       end as AGE_DAY,-- 年龄（天） 不足一月时填写，在1-31范围内的整数

       case
           when t1.date_of_birth is not null
            and t.admission_date_time is not null
            and (t.admission_date_time - t1.date_of_birth) < 1
           then greatest(trunc(24 * (t.admission_date_time - t1.date_of_birth)), 1)
           else 0
       end as AGE_HOUR,--  年龄（小时） 不足一天时填写，在1-24范围内的整数

       cast(t.admission_date_time as date) as ADMISSION_DATE,--  入院日期  是 字符型改为时间类型

       cast(t.discharge_date_time as date) as DISCHARGE_DATE,--  出院日期  是 业务日期

       case
           when t.discharge_date_time is not null
            and t.admission_date_time is not null
           then greatest(trunc(t.discharge_date_time) - trunc(t.admission_date_time), 1)
           else 1
       end as INPATIENT_DAY,-- 住院天数  是 正整数

       substr(
           nvl(
               nullif(
                   trim(
                       regexp_substr(
                           cast(dbms_lob.substr(t5.段落内容, 2000, 1) as varchar2(2000)),
                           '入[[:space:]]*院[[:space:]]*情[[:space:]]*况[[:space:]]*[:：][[:space:]]*(.*?)[[:space:]]*入[[:space:]]*院[[:space:]]*诊[[:space:]]*断[[:space:]]*[:：]',
                           1, 1, 'n', 1
                       )
                   ),
                   ''
               ),
               cast(t.pat_adm_condition as varchar2(2000))
           ),
           1,
           2000
       ) as ADMISSION_SITUATION,-- 入院情况

       cast(null as varchar2(2000)) as DIAG_TREAT_PLAN,-- 诊疗计划

       substr(
           nvl(
               nullif(
                   trim(
                       regexp_substr(
                           cast(dbms_lob.substr(t5.段落内容, 2000, 1) as varchar2(2000)),
                           '诊[[:space:]]*疗[[:space:]]*经[[:space:]]*过[[:space:]]*[:：][[:space:]]*(.*?)[[:space:]]*出[[:space:]]*院[[:space:]]*诊[[:space:]]*断[[:space:]]*[:：]',
                           1, 1, 'n', 1
                       )
                   ),
                   ''
               ),
               cast(null as varchar2(2000))
           ),
           1,
           2000
       ) as TREAT_PROCESS,-- 诊疗经过

       substr(
           nvl(
               nullif(
                   trim(
                       regexp_substr(
                           cast(dbms_lob.substr(t5.段落内容, 2000, 1) as varchar2(2000)),
                           '出[[:space:]]*院[[:space:]]*情[[:space:]]*况[[:space:]]*[:：][[:space:]]*(.*?)[[:space:]]*出[[:space:]]*院[[:space:]]*医[[:space:]]*嘱[[:space:]]*[:：]',
                           1, 1, 'n', 1
                       )
                   ),
                   ''
               ),
               cast(null as varchar2(2000))
           ),
           1,
           2000
       ) as DISCHARGE_SITUATION,-- 出院情况

       substr(
           nvl(
               nullif(
                   trim(
                       regexp_substr(
                           cast(dbms_lob.substr(t5.段落内容, 2000, 1) as varchar2(2000)),
                           '出[[:space:]]*院[[:space:]]*医[[:space:]]*嘱[[:space:]]*[:：][[:space:]]*(.*?)[[:space:]]*医[[:space:]]*师[[:space:]]*签[[:space:]]*名[[:space:]]*[:：]',
                           1, 1, 'n', 1
                       )
                   ),
                   ''
               ),
               cast(null as varchar2(2000))
           ),
           1,
           2000
       ) as DISCHARGE_ORDER,-- 出院医嘱

       substr(
           nvl(
               nullif(trim(diag_dict.std_name), ''),
               nvl(
                   nullif(
                       trim(
                           regexp_replace(
                               regexp_substr(
                                   cast(dbms_lob.substr(t5.段落内容, 2000, 1) as varchar2(2000)),
                                   '出[[:space:]]*院[[:space:]]*诊[[:space:]]*断[[:space:]]*[:：][[:space:]]*(.*?)[[:space:]]*出[[:space:]]*院[[:space:]]*情[[:space:]]*况[[:space:]]*[:：]',
                                   1, 1, 'n', 1
                               ),
                               '出[[:space:]]*院[[:space:]]*诊[[:space:]]*断[[:space:]]*[:：]',
                               ''
                           )
                       ),
                       ''
                   ),
                   nvl(nullif(trim(cast(t2.diagnosis_desc as varchar2(100))), ''), '-')
               )
           ),
           1,
           100
       ) as DISCHARGE_DIAGNOSIS,-- 出院诊断名称

       substr(
           nvl(
               nullif(trim(diag_dict.std_code), ''),
               nvl(nullif(trim(cast(t2.diagnosis_code as varchar2(20))), ''), '-')
           ),
           1,
           20
       ) as DISCHARGE_DIAGNOSIS_CODE,--  出院诊断编码 ICD10

       cast(null as varchar2(2000)) as CHARACT_CASES,-- 病例特点

       substr(
           cast(
               (select sd.id_no
                  from his.staff_dict sd
                 where sd.emp_no = t.attending_doctor
                   and rownum = 1)
               as varchar2(32)
           ),
           1,
           32
       ) as DOCTOR_CODE,-- 医生代码 主治医生身份证

       substr(
           nvl(
               nullif(
                   trim(
                       cast(
                           (select yg.name
                              from his.staff_dict yg
                             where yg.emp_no = t.attending_doctor
                               and rownum = 1)
                           as varchar2(50)
                       )
                   ),
                   ''
               ),
               '-'
           ),
           1,
           50
       ) as DOCTOR_NAME,-- 医师姓名  是 住院医师（主治医师）

       substr(
           trim(
               regexp_substr(
                   cast(dbms_lob.substr(t5.段落内容, 2000, 1) as varchar2(2000)),
                   '医[[:space:]]*师[[:space:]]*签[[:space:]]*名[[:space:]]*[:：][[:space:]]*([^[:cntrl:][:space:]]+)',
                   1, 1, 'n', 1
               )
           ),
           1,
           50
       ) as SUPERIOR_DOC_NAME,-- 上级医师签名

       substr(
           nvl(
               nullif(trim(cast(t.discharge_ward_code as varchar2(50))), ''),
               cast(
                   (select aa.ward_code
                      from his.pats_in_hospital aa
                     where aa.patient_id = t.patient_id
                       and aa.visit_id = t.visit_id
                       and rownum = 1)
                   as varchar2(50)
               )
           ),
           1,
           50
       ) as WARD,--  病区名称

       substr(
           nvl(
               nullif(trim(cast(t.discharge_bed_no as varchar2(20))), ''),
               cast(
                   (select aa.bed_no
                      from his.pats_in_hospital aa
                     where aa.patient_id = t.patient_id
                       and aa.visit_id = t.visit_id
                       and rownum = 1)
                   as varchar2(20)
               )
           ),
           1,
           20
       ) as SICKBED_NUM,-- 病床号 重点

       cast(null as varchar2(1000)) as FOUR_DIAGNOSIS,--  中医“四诊”观察结果

       cast(null as varchar2(100)) as TREATMENT_METHOD,--  治则治法

       cast(null as varchar2(100)) as TCM_DECOCTION_METHOD,--  中药煎煮方法

       cast(null as varchar2(100)) as MEDICATION_METHOD,-- 用药方法

       substr(
           trim(
               regexp_substr(
                   cast(dbms_lob.substr(t5.段落内容, 2000, 1) as varchar2(2000)),
                   '出[[:space:]]*院[[:space:]]*情[[:space:]]*况[[:space:]]*[:：][[:space:]]*(.*?)[[:space:]]*出[[:space:]]*院[[:space:]]*医[[:space:]]*嘱[[:space:]]*[:：]',
                   1, 1, 'n', 1
               )
           ),
           1,
           1000
       ) as DISCHARGE_SIGNS,-- 出院时症状与体征

       substr(cast(t1.id_no as varchar2(32)), 1, 32) as CITIZEN_ID,-- 个人内码

       cast(t4.DOC_CREATE_DATE as date) as EFFECTIVE_TIME,-- 活动发生时间

       cast(null as varchar2(32)) as STATUS,-- 卡片状态 平台自动生成值，不需要填写

       cast(null as timestamp) as CREATED_AT,-- 创建时间 平台自动生成，不需要填写

       '370104' as DISTRICT_CODE,-- 所属行政区划  是 按机构所在的行政区划（区县）

       'INSERT' as EXCHANGE_TYPE,-- 交换类型  是 INSERT：向平台传新数据时

       cast(null as varchar2(50)) as DEI,-- 数据交换标识符

       cast(null as varchar2(50)) as NODE_CODE,-- 节点标识符

       cast(systimestamp as timestamp) as SYSTEM_TIME,-- 数据上传时间戳 是 数据上传时间戳

       substr(cast(t3.uhid as varchar2(36)), 1, 36) as AR_ID,-- 病案ID

       substr(
           cast(
               (select sd.id_no
                  from his.staff_dict sd
                 where sd.emp_no = t.attending_doctor
                   and rownum = 1)
               as varchar2(18)
           ),
           1,
           18
       ) as DOC_ID_NUM,-- 医生身份证号

       cast(t4.MODIFIEDON as date) as DISCHARGE_TIME,-- 记录时间 字符型改为时间类型

       case
           when regexp_like(
                    cast(dbms_lob.substr(t5.段落内容, 2000, 1) as varchar2(2000)),
                    '自动出院|自行出院|要求出院|拒绝.*治疗|拒绝.*检查'
                )
           then '1'
           else '0'
       end as AUTO_LEAVE_HOS,-- 自动出院标志 是 患者自动出院为1，医嘱出院为0

       case
           when t.discharge_date_time is not null
            and t.admission_date_time is not null
            and t.discharge_date_time >= t.admission_date_time
            and t.discharge_date_time - t.admission_date_time < 1
           then '1'
           else '0'
       end as IS24HRADM_DISCH,-- 是否24小时入出院 是 通过比对国家数据集增加的数据项

       substr(
           nvl(
               (select cast(zd.国标编码 as varchar2(100))
                  from cda.cda_dictionary zd
                 where cast(zd.字典名称 as varchar2(100)) = '离院方式代码'
                   and cast(zd.院标编码 as varchar2(100)) = cast(t.discharge_disposition as varchar2(100))
                   and rownum = 1),
               '9'
           ),
           1,
           100
       ) as DESTINATION_CODE,-- 离院方式代码 是 通过比对国家数据集增加的数据项

       substr(
           nvl(
               (select cast(zd.国标名称 as varchar2(100))
                  from cda.cda_dictionary zd
                 where cast(zd.字典名称 as varchar2(100)) = '离院方式代码'
                   and cast(zd.院标编码 as varchar2(100)) = cast(t.discharge_disposition as varchar2(100))
                   and rownum = 1),
               '其他'
           ),
           1,
           100
       ) as DESTINATION_DESC,-- 离院方式名称 是 通过比对国家数据集增加的数据项

       substr(
           nvl(
               (select cast(zd.国标编码 as varchar2(100))
                  from cda.cda_dictionary zd
                 where cast(zd.字典名称 as varchar2(100)) = '病情转归代码表'
                   and cast(zd.院标编码 as varchar2(100)) = cast(t.discharge_disposition as varchar2(100))
                   and rownum = 1),
               '9'
           ),
           1,
           100
       ) as DISCHARGE_STATUS,-- 转归方式编码 是 通过比对国家数据集增加的数据项

       substr(
           nvl(
               (select cast(zd.国标名称 as varchar2(100))
                  from cda.cda_dictionary zd
                 where cast(zd.字典名称 as varchar2(100)) = '病情转归代码表'
                   and cast(zd.院标编码 as varchar2(100)) = cast(t.discharge_disposition as varchar2(100))
                   and rownum = 1),
               '其他'
           ),
           1,
           100
       ) as DISCHARGE_STATUS_NAME,-- 转归方式名称 是 通过比对国家数据集增加的数据项

       substr(
           nvl(
               nullif(
                   trim(
                       cast(
                           (select yg.practice_cert_code
                              from doc_register_emp_match yg
                             where yg.emp_no = t.attending_doctor
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
       ) as ATTEND_DOC_CERTIFICATE_NO,-- 主治医生执业证书编号 是 通过比对国家数据集增加的数据项

       substr(
           nvl(
               nullif(
                   trim(
                       regexp_substr(
                           cast(dbms_lob.substr(t5.段落内容, 2000, 1) as varchar2(2000)),
                           '出[[:space:]]*院[[:space:]]*情[[:space:]]*况[[:space:]]*[:：][[:space:]]*(.*?)[[:space:]]*出[[:space:]]*院[[:space:]]*医[[:space:]]*嘱[[:space:]]*[:：]',
                           1, 1, 'n', 1
                       )
                   ),
                   ''
               ),
               '-'
           ),
           1,
           2000
       ) as DISCHARGE_CONDITION,-- 出院时症状与体征 通过比对国家数据集增加的数据项

       substr(
           nvl(
               nullif(
                   trim(cast(dbms_lob.substr(t5.段落内容, 2000, 1) as varchar2(2000))),
                   ''
               ),
               '-'
           ),
           1,
           2000
       ) as DISCHARGE_HP_TEXT -- 出院/死亡记录文本 是 通过比对国家数据集增加的数据项

from his.pat_visit t

left join his.pat_master_index t1
       on t.patient_id = t1.patient_id

left join his.diagnosis t2
       on t.patient_id = t2.patient_id
      and t.visit_id = t2.visit_id
      and t2.diagnosis_type = '3'
      and t2.diagnosis_no = '1'

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
       on diag_dict.local_code = trim(to_char(t2.diagnosis_code))

left join mtl.epr_inpatient_docindex t3
       on t3.p_inpatient_no = t1.inp_no
      and t3.p_inpatient_times = t.visit_id

left join mtl.epr_inpatient t4
       on t3.uhid = t4.uhid

left join mtl.emrsd_content t5
       on t5.uhid = t3.uhid
      and t5.段落编号 = t4.id

where cast(t4.doc_type_name as varchar2(100)) like '%出院记录%'
  and t.discharge_date_time >= to_date('2021-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss')
  and t.discharge_date_time <  to_date('2025-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss')
    ) q
)
where rn = 1
