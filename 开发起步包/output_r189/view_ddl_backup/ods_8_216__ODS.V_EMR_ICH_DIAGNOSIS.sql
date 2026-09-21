
  CREATE OR REPLACE FORCE VIEW "ODS"."V_EMR_ICH_DIAGNOSIS" ("ID", "DCS_ID", "SN", "DIAGNOSIS_TYPE", "DISEASE_CODE", "DISEASE", "DIS_OUTCOME_NAME", "DIS_OUTCOME_CODE", "IS_CAWM_DIAGNOSIS", "DIAGNOSIS_DATE", "ADMISSION_CONDITION", "ADMISSION_CONNAME", "CREATED_AT", "DISTRICT_CODE", "EXCHANGE_TYPE", "HIGHEST_DIAGNOSTIC_BASIS", "HIGHEST_DIAGN_NAME", "SYSTEM_TIME", "ORG_CODE", "ORG_NAME", "BLZDBM", "BLZDMC", "ADMISSION_ID", "NAME", "SEX_CODE", "ID_NUM") AS 
  select
       cast(
           substrb(
               '49557032X' || '|' || a.patient_id || '|' || a.visit_id || '|' ||
               nvl(to_char(a.diagnosis_type), '-') || '|' || nvl(to_char(a.diagnosis_no), '-'),
               1,
               100
           ) as varchar2(100)
       ) as ID,--内码 是 主键；机构码|患者ID|住院次数|诊断类型|诊断序号

       cast(
           substrb(
               '49557032X' || '|' || a.patient_id || '|' || a.visit_id,
               1,
               100
           ) as varchar2(100)
       ) as DCS_ID,--病案首页内码 是；必须与EMR_ICH.ID一致

       a.diagnosis_no as SN,--序号

           cast(
           case
               when to_char(a.diagnosis_type) = '3'
                    and nvl(a.diagnosis_no, 0) = 1
               then '1'  -- 出院诊断-主要诊断

               when to_char(a.diagnosis_type) = '3'
                    and nvl(a.diagnosis_no, 0) <> 1
               then '2'  -- 出院诊断-其他诊断

               when to_char(a.diagnosis_type) = '2'
               then '3'  -- 入院初步诊断

               when to_char(a.diagnosis_type) = '8'
               then '12' -- 病理诊断；按当前结果判断，8为病理诊断

               when to_char(a.diagnosis_type) = '7'
               then '17' -- 损伤、中毒诊断；按当前结果判断，7为损伤/外因诊断

               when to_char(a.diagnosis_type) = '1'
               then '19' -- 门（急）诊诊断

               else '23' -- 其他
           end as varchar2(2)
       ) as DIAGNOSIS_TYPE,--疾病诊断类型 是；按当前数据结果修正7/8映射

    cast(
    substrb(
    nvl(
        coalesce(
            case
                when regexp_like(
                         upper(trim(to_char(diag_code_dict.国标编码))),
                         '^[A-Z][0-9][0-9A-Z](\.|X)?[0-9A-Z]*$'
                     )
                     and not regexp_like(
                         upper(trim(to_char(diag_code_dict.国标编码))),
                         '^M[0-9]{5}/'
                     )
                then upper(trim(to_char(diag_code_dict.国标编码)))
            end,
            case
                when regexp_like(
                         upper(trim(to_char(a.diagnosis_code))),
                         '^[A-Z][0-9][0-9A-Z](\.|X)?[0-9A-Z]*$'
                     )
                     and not regexp_like(
                         upper(trim(to_char(a.diagnosis_code))),
                         '^M[0-9]{5}/'
                     )
                then upper(trim(to_char(a.diagnosis_code)))
            end,
            case
                when regexp_like(
                         upper(trim(to_char(a.diagnosis_code2))),
                         '^[A-Z][0-9][0-9A-Z](\.|X)?[0-9A-Z]*$'
                     )
                     and not regexp_like(
                         upper(trim(to_char(a.diagnosis_code2))),
                         '^M[0-9]{5}/'
                     )
                then upper(trim(to_char(a.diagnosis_code2)))
            end,
            (
                select max(upper(trim(to_char(d.diagnosis_code))))
                  from his.diagnosis d
                 where d.patient_id = a.patient_id
                   and d.visit_id = a.visit_id
                   and to_char(d.diagnosis_type) = '3'
                   and nvl(d.diagnosis_no, 0) = 1
                   and regexp_like(
                           upper(trim(to_char(d.diagnosis_code))),
                           '^[A-Z][0-9][0-9A-Z](\.|X)?[0-9A-Z]*$'
                       )
                   and not regexp_like(
                           upper(trim(to_char(d.diagnosis_code))),
                           '^M[0-9]{5}/'
                       )
            )
        ),
        'Z00.000'),
        1,
        12
    ) as varchar2(12)
) as DISEASE_CODE,--疾病编码 是；禁止M码进入DISEASE_CODE，病理记录回退出院主诊断ICD

       cast(
           substrb(
           nvl(
               coalesce(
                   diag_code_dict.国标名称,
                   diag_code2_dict.国标名称,
                   diag_name_dict.国标名称,
                   to_char(a.diagnosis_desc_doc),
                   to_char(a.diagnosis_desc)
               ),
               '一般性医学检查'),
               1,
               50
           ) as varchar2(50)
       ) as DISEASE,--疾病诊断名称 是；优先标准名称，其次医生录入名称、HIS诊断名称

cast(
    substrb(
        case
            when trim(to_char(a.treat_result)) in ('1', '治愈') then '治愈'
            when trim(to_char(a.treat_result)) in ('2', '好转') then '好转'
            when trim(to_char(a.treat_result)) in ('3', '稳定') then '稳定'
            when trim(to_char(a.treat_result)) in ('4', '恶化') then '恶化'
            when trim(to_char(a.treat_result)) in ('5', '死亡') then '死亡'
            when trim(to_char(a.treat_result)) in ('6', '未愈') then '未愈'
            when trim(to_char(a.treat_result)) in ('9', '其他') then '其他'
            else '其他'
        end,
        1,
        10
    ) as varchar2(10)
) as DIS_OUTCOME_NAME,--病情转归名称
cast(
    case
        when trim(to_char(a.treat_result)) in ('1', '治愈') then '1'
        when trim(to_char(a.treat_result)) in ('2', '好转') then '2'
        when trim(to_char(a.treat_result)) in ('3', '稳定') then '3'
        when trim(to_char(a.treat_result)) in ('4', '恶化') then '4'
        when trim(to_char(a.treat_result)) in ('5', '死亡') then '5'
        when trim(to_char(a.treat_result)) in ('6', '未愈') then '6'
        when trim(to_char(a.treat_result)) in ('9', '其他') then '9'
        else '9'
    end as char(1)
) as DIS_OUTCOME_CODE,--病情转归代码；1治愈、2好转、3稳定、4恶化、5死亡、6未愈、9其他
       cast('2' as char(1)) as IS_CAWM_DIAGNOSIS,--中西医诊断标识 是；HIS诊断按西医诊断处理

       cast(nvl(a.diagnosis_date, p.admission_date_time) as date) as DIAGNOSIS_DATE,--确诊日期；优先诊断日期，空时取入院时间

       cast(
           case
               when to_char(a.admission_condition) in ('1','2','3','4')
               then to_char(a.admission_condition)
               else null
           end as char(1)
       ) as ADMISSION_CONDITION,--入院病情代码；取DIAGNOSIS.ADMISSION_CONDITION

       cast(
           substrb(
               case
                   when to_char(a.admission_condition) = '1' then '有'
                   when to_char(a.admission_condition) = '2' then '临床未确定'
                   when to_char(a.admission_condition) = '3' then '情况不明'
                   when to_char(a.admission_condition) = '4' then '无'
                   else null
               end,
               1,
               50
           ) as varchar2(50)
       ) as ADMISSION_CONNAME,--入院病情描述；1有、2临床未确定、3情况不明、4无
to_char(
    nvl(
        a.enter_date,
        nvl(a.diagnosis_date, p.admission_date_time)
    ),
    'yyyy-mm-dd hh24:mi:ss'
) as CREATED_AT,--创建时间；统一时间格式

       cast('370104' as varchar2(6)) as DISTRICT_CODE,--所属行政区划 是

       cast('ADDHIS' as varchar2(10)) as EXCHANGE_TYPE,--交换类型 是

                 cast(
           case
               when regexp_substr(upper(trim(to_char(a.diagnosis_code2))), 'M[0-9]{5}/[0-9]') is not null
                    or regexp_substr(upper(trim(to_char(a.diagnosis_code))), 'M[0-9]{5}/[0-9]') is not null
                    or exists (
                        select 1
                          from his.diagnosis d
                         where d.patient_id = a.patient_id
                           and d.visit_id = a.visit_id
                           and to_char(d.diagnosis_type) = '8'
                           and (
                                regexp_substr(upper(trim(to_char(d.diagnosis_code2))), 'M[0-9]{5}/[0-9]') is not null
                                or regexp_substr(upper(trim(to_char(d.diagnosis_code))), 'M[0-9]{5}/[0-9]') is not null
                                or trim(to_char(d.diagnosis_desc_doc)) is not null
                                or trim(to_char(d.diagnosis_desc)) is not null
                           )
                    )
               then '1'
               else '19'
           end as varchar2(2)
       ) as HIGHEST_DIAGNOSTIC_BASIS,--最高诊断依据代码；同次住院存在病理诊断时填1病理，否则19其他
         cast(
           case
               when regexp_substr(upper(trim(to_char(a.diagnosis_code2))), 'M[0-9]{5}/[0-9]') is not null
                    or regexp_substr(upper(trim(to_char(a.diagnosis_code))), 'M[0-9]{5}/[0-9]') is not null
                    or exists (
                        select 1
                          from his.diagnosis d
                         where d.patient_id = a.patient_id
                           and d.visit_id = a.visit_id
                           and to_char(d.diagnosis_type) = '8'
                           and (
                                regexp_substr(upper(trim(to_char(d.diagnosis_code2))), 'M[0-9]{5}/[0-9]') is not null
                                or regexp_substr(upper(trim(to_char(d.diagnosis_code))), 'M[0-9]{5}/[0-9]') is not null
                                or trim(to_char(d.diagnosis_desc_doc)) is not null
                                or trim(to_char(d.diagnosis_desc)) is not null
                           )
                    )
               then '病理'
               else '其他'
           end as varchar2(32)
       ) as HIGHEST_DIAGN_NAME,--最高诊断依据名称
to_char(sysdate, 'yyyy-mm-dd hh24:mi:ss') as SYSTEM_TIME,--数据上传时间戳 是；统一时间格式
       cast('49557032X' as varchar2(32)) as ORG_CODE,--医院组织机构代码 是

       cast('山东省第二人民医院' as varchar2(70)) as ORG_NAME,--医院名称 是

                cast(
           substrb(
               nvl(
                   coalesce(
                       regexp_substr(upper(trim(to_char(a.diagnosis_code2))), 'M[0-9]{5}/[0-9]'),
                       regexp_substr(upper(trim(to_char(a.diagnosis_code))),  'M[0-9]{5}/[0-9]'),
                       (
                           select max(
                                      coalesce(
                                          regexp_substr(upper(trim(to_char(d.diagnosis_code2))), 'M[0-9]{5}/[0-9]'),
                                          regexp_substr(upper(trim(to_char(d.diagnosis_code))),  'M[0-9]{5}/[0-9]')
                                      )
                                  )
                             from his.diagnosis d
                            where d.patient_id = a.patient_id
                              and d.visit_id = a.visit_id
                              and to_char(d.diagnosis_type) = '8'
                       )
                   ),
                   '-'
               ),
               1,
               20
           ) as varchar2(20)
       ) as BLZDBM,--病理诊断编码；取本条或同次住院diagnosis_type=8有效M码，无则-
               cast(
           substrb(
               nvl(
                   case
                       when to_char(a.diagnosis_type) = '8'
                       then coalesce(
                                to_char(a.diagnosis_desc_doc),
                                to_char(a.diagnosis_desc)
                            )
                       else (
                            select max(
                                       coalesce(
                                           to_char(d.diagnosis_desc_doc),
                                           to_char(d.diagnosis_desc)
                                       )
                                   )
                              from his.diagnosis d
                             where d.patient_id = a.patient_id
                               and d.visit_id = a.visit_id
                               and to_char(d.diagnosis_type) = '8'
                               and (
                                    trim(to_char(d.diagnosis_desc_doc)) is not null
                                    or trim(to_char(d.diagnosis_desc)) is not null
                               )
                       )
                   end,
                   '-'
               ),
               1,
               100
           ) as varchar2(100)
       ) as BLZDMC,--病理诊断名称；取本条或同次住院diagnosis_type=8病理诊断名称，无则-

       cast(
           substrb(
               a.patient_id || '|' || a.visit_id,
               1,
               20
           ) as varchar2(20)
       ) as ADMISSION_ID,--本次住院标识号 是

       cast(substrb(nvl(to_char(pmi.name), '无名氏'), 1, 50) as varchar2(50)) as NAME,--患者姓名 是

       cast(
           decode(pmi.sex, '男', '1', '女', '2', '未知', '0', '9')
           as char(1)
       ) as SEX_CODE,--患者性别代码 是

       cast(
           substrb(
               case
                   when regexp_like(trim(to_char(pmi.id_no)), '^[0-9]{17}[0-9Xx]$|^[0-9]{15}$')
                   then upper(trim(to_char(pmi.id_no)))
                   else '000000000000000000'
               end,
               1,
               18
           ) as varchar2(18)
       ) as ID_NUM--患者身份证件号码 是

  from his.diagnosis a

  left join his.pat_master_index pmi
    on pmi.patient_id = a.patient_id

  join his.pat_visit p
    on p.patient_id = a.patient_id
   and p.visit_id = a.visit_id

  left join (
        select to_char(院标编码) as 院标编码,
               max(to_char(国标编码)) as 国标编码,
               max(to_char(国标名称)) as 国标名称
          from cda.cda_dictionary
         where 字典名称 = 'ICD-10诊断编码'
           and 系统标识 = 'HIS'
         group by to_char(院标编码)
       ) diag_code_dict
    on diag_code_dict.院标编码 = to_char(a.diagnosis_code)

  left join (
        select to_char(院标编码) as 院标编码,
               max(to_char(国标编码)) as 国标编码,
               max(to_char(国标名称)) as 国标名称
          from cda.cda_dictionary
         where 字典名称 = 'ICD-10诊断编码'
           and 系统标识 = 'HIS'
         group by to_char(院标编码)
       ) diag_code2_dict
    on diag_code2_dict.院标编码 = to_char(a.diagnosis_code2)
   and regexp_like(
           upper(trim(to_char(a.diagnosis_code2))),
           '^[A-Z][0-9][0-9A-Z](\.|X)?[0-9A-Z]*$'
       )

  left join (
        select to_char(院标名称) as 院标名称,
               max(to_char(国标编码)) as 国标编码,
               max(to_char(国标名称)) as 国标名称
          from cda.cda_dictionary
         where 字典名称 = 'ICD-10诊断编码'
           and 系统标识 = 'HIS'
         group by to_char(院标名称)
       ) diag_name_dict
    on diag_name_dict.院标名称 =
       coalesce(to_char(a.diagnosis_desc_doc), to_char(a.diagnosis_desc))



 where p.discharge_date_time >= date '2021-01-01'
   and p.discharge_date_time <  date '2025-01-01'
