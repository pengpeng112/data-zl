
  CREATE OR REPLACE FORCE VIEW "ODS"."V_EMR_INFOR_OPERATION" ("ID", "ORG_CODE", "ORG_NAME", "DISTRICT_CODE", "EXCHANGE_TYPE", "SYSTEM_TIME", "ADMISSION_ID", "INFORMED_CONSENT_CODE", "INFORMED_CONSENT_NAME", "APPLY_NUM", "DEPT_CODE", "DEP_NAME", "AREA_NAME", "WARD_NUM", "SICKBED_NUM", "PATIENT_NAME", "SEX_CODE", "SEX_NAME", "AGE", "AGE_MONTH", "PREOPERATIVE", "PREOPERATIVE_NAME", "OPERATION", "OPERATION_NAME", "OPERATION_DATE", "OPERATION_IN", "OPERATION_TABOO", "OPERATION_WAY", "ANAESTHESIA_CODE", "ANAESTHESIA_NAME", "OPERATION_READY", "OPERATIONING_RISK", "OPERATIONED_RISK", "REPLACE_PLAN", "ORG_VIEW", "PATIENT_VIEW", "PATIENT_SIGN_NAME", "STATUTORY_AGENT_VIEW", "SAP_RELATIONSHIP_CODE", "SAP_RELATIONSHIP_NAME", "PATIENT_SIGN_DATE", "DOCTOR", "OPERATOR", "DOC_DATE") AS 
  select ID,
       ORG_CODE,
       ORG_NAME,
       DISTRICT_CODE,
       EXCHANGE_TYPE,
       SYSTEM_TIME,
       ADMISSION_ID,
       INFORMED_CONSENT_CODE,
       INFORMED_CONSENT_NAME,
       APPLY_NUM,
       DEPT_CODE,
       DEP_NAME,
       AREA_NAME,
       WARD_NUM,
       SICKBED_NUM,
       PATIENT_NAME,
       SEX_CODE,
       SEX_NAME,
       AGE,
       AGE_MONTH,
       PREOPERATIVE,
       PREOPERATIVE_NAME,
       OPERATION,
       OPERATION_NAME,
       OPERATION_DATE,
       OPERATION_IN,
       OPERATION_TABOO,
       OPERATION_WAY,
       ANAESTHESIA_CODE,
       ANAESTHESIA_NAME,
       OPERATION_READY,
              nvl (OPERATIONING_RISK,'-' ) OPERATIONING_RISK,
       nvl (OPERATIONED_RISK,'-' ) OPERATIONED_RISK,
       REPLACE_PLAN,
       ORG_VIEW,
       PATIENT_VIEW,
       PATIENT_SIGN_NAME,
       STATUTORY_AGENT_VIEW,
       SAP_RELATIONSHIP_CODE,
       SAP_RELATIONSHIP_NAME,
       PATIENT_SIGN_DATE,
       DOCTOR,
       OPERATOR,
       DOC_DATE
from (
    select q.*,
           row_number() over (
               partition by q.ID
               order by q.DOC_DATE desc nulls last,
                        q.OPERATION_DATE desc nulls last
           ) as rn
    from (
        select substr(
                   '49557032X'||'|'||
                   nvl(to_char(p.patient_id), '-')||'|'||
                   nvl(to_char(p.visit_id), '-')||'|'||
                   nvl(to_char(t1.id), '-'),
                   1,
                   100
               ) as ID,--  内码 是 主键

               '49557032X' as ORG_CODE,--  医院组织机构代码 是 必填

               '山东省第二人民医院' as ORG_NAME,--  医院名称 是 必填

               '370104' as DISTRICT_CODE,-- 所属行政区划 是

               'ADDHIS' as EXCHANGE_TYPE,-- 交换类型 是

               cast(systimestamp as timestamp) as SYSTEM_TIME,-- 数据上传时间戳

               substr(
                   nvl(to_char(p.patient_id), '-')||'|'||nvl(to_char(p.visit_id), '-'),
                   1,
                   50
               ) as ADMISSION_ID,-- 住院唯一标识号 是

               substr(
                   nvl(to_char(t1.doc_type_id), '-')||'-'||nvl(to_char(t1.id), '-'),
                   1,
                   20
               ) as INFORMED_CONSENT_CODE,-- 知情同意书编号

               substr(
                   nvl(nullif(trim(cast(t1.doc_type_name as varchar2(200))), ''), '手术知情同意书'),
                   1,
                   200
               ) as INFORMED_CONSENT_NAME,-- 知情同意书名称

               substr(
                   nvl(to_char(o.operation_no), nvl(to_char(mom.oper_id), to_char(t1.id))),
                   1,
                   20
               ) as APPLY_NUM,-- 手术申请单编号

               substr(
                   nvl(
                       (select cast(ks.qmpt_code as varchar2(50))
                          from his.dept_dict ks
                         where ks.dept_code = t.p_dept_code
                           and rownum = 1),
                       nvl(cast(t.p_dept_code as varchar2(50)), '-')
                   ),
                   1,
                   50
               ) as DEPT_CODE,-- 科室代码

               substr(
                   nvl(
                       (select cast(ks.qmpt_name as varchar2(50))
                          from his.dept_dict ks
                         where ks.dept_code = t.p_dept_code
                           and rownum = 1),
                       nvl(
                           (select cast(ks.dept_name as varchar2(50))
                              from his.dept_dict ks
                             where ks.dept_code = t.p_dept_code
                               and rownum = 1),
                           '-'
                       )
                   ),
                   1,
                   50
               ) as DEP_NAME,-- 科室名称 是

               substr(cast(t.p_are_name as varchar2(50)), 1, 50) as AREA_NAME,-- 病区名称

               cast(null as varchar2(10)) as WARD_NUM,-- 病房号

               substr(cast(t.p_bedno as varchar2(10)), 1, 10) as SICKBED_NUM,-- 病床号

               substr(
                   nvl(nullif(trim(cast(t.p_name as varchar2(50))), ''), nvl(cast(pmi.name as varchar2(50)), '-')),
                   1,
                   50
               ) as PATIENT_NAME,-- 患者姓名 是

               case
                   when cast(pmi.sex as varchar2(10)) = '男' then 1
                   when cast(pmi.sex as varchar2(10)) = '女' then 2
                   when cast(pmi.sex as varchar2(10)) = '未知' then 0
                   else 9
               end as SEX_CODE,-- 性别代码 是

               substr(
                   case
                       when cast(pmi.sex as varchar2(10)) = '男' then '男'
                       when cast(pmi.sex as varchar2(10)) = '女' then '女'
                       when cast(pmi.sex as varchar2(10)) = '未知' then '未知'
                       else '不明'
                   end,
                   1,
                   50
               ) as SEX_NAME,-- 性别 是

               case
                   when pmi.date_of_birth is not null
                    and p.admission_date_time is not null
                   then least(
                            greatest(
                                trunc(months_between(p.admission_date_time, pmi.date_of_birth) / 12),
                                0
                            ),
                            200
                        )
                   else 0
               end as AGE,-- 年龄 是 0-200

               substr(
                   case
                       when pmi.date_of_birth is not null
                        and p.admission_date_time is not null
                        and months_between(p.admission_date_time, pmi.date_of_birth) < 12
                       then to_char(
                                least(
                                    greatest(
                                        trunc(months_between(p.admission_date_time, pmi.date_of_birth)),
                                        0
                                    ),
                                    11
                                )
                            )
                       else null
                   end,
                   1,
                   2
               ) as AGE_MONTH,-- 年龄(月) 0-11

            nvl( nvl(   (select max(cd.国标编码)
            from cda.cda_dictionary cd
           where cd.字典名称 = 'ICD-10诊断编码'
             and cd.系统标识 = 'SM'
             and cd.院标名称 = mom.DIAG_before_OPERATION)    ,
              (select max(cd.国标编码)
            from cda.cda_dictionary cd
           where cd.字典名称 = 'ICD-10诊断编码'
             and cd.系统标识 = 'HIS'
             and cd.院标编码 = dd.diagnosis_code)
       ),         dd.diagnosis_code)         as PREOPERATIVE,-- 术前诊断编码

                  cast(
    substrb( nvl( nvl(   (select max(cd.国标名称)
            from cda.cda_dictionary cd
           where cd.字典名称 = 'ICD-10诊断编码'
             and cd.系统标识 = 'SM'
             and cd.院标名称 = mom.DIAG_before_OPERATION)    ,
              (select max(cd.国标名称)
            from cda.cda_dictionary cd
           where cd.字典名称 = 'ICD-10诊断编码'
             and cd.系统标识 = 'HIS'
             and cd.院标编码 = dd.diagnosis_code)
       ),         dd.diagnosis_desc),
        1,
        50
    )
    as varchar2(50)
)       as PREOPERATIVE_NAME,-- 术前诊断名称 是

            cast(
    coalesce(
        (
            select max(to_char(cd.国标编码))
              from cda.cda_dictionary cd
             where cd.字典名称 = 'ICD-9手术编码'
               and cd.系统标识 = 'HIS'
               and cd.院标名称 = o.operation_desc
        ),
        (
            select max(to_char(cd.国标编码))
              from cda.cda_dictionary cd
             where cd.字典名称 = 'ICD-9手术编码'
               and cd.系统标识 = 'HIS'
               and cd.院标编码 = o.operation_code
        ),
        (
            select max(to_char(cd.国标编码))
              from cda.cda_dictionary cd
             where cd.字典名称 = 'ICD-9手术编码'
               and cd.系统标识 = 'SM'
               and cd.院标名称 = mom.operation_name
        ),
        nullif(trim(to_char(o.operation_code)), '')
    ) as varchar2(50)
) as OPERATION,  -- 拟实施手术及操作编码

           cast(
    substrb(
        coalesce(
            (
                select max(to_char(cd.国标名称))
                  from cda.cda_dictionary cd
                 where cd.字典名称 = 'ICD-9手术编码'
                   and cd.系统标识 = 'HIS'
                   and cd.院标名称 = o.operation_desc
            ),
            (
                select max(to_char(cd.国标名称))
                  from cda.cda_dictionary cd
                 where cd.字典名称 = 'ICD-9手术编码'
                   and cd.系统标识 = 'HIS'
                   and cd.院标编码 = o.operation_code
            ),
            (
                select max(to_char(cd.国标名称))
                  from cda.cda_dictionary cd
                 where cd.字典名称 = 'ICD-9手术编码'
                   and cd.系统标识 = 'SM'
                   and cd.院标名称 = mom.operation_name
            ),
            nullif(trim(to_char(o.operation_desc)), ''),
            nullif(trim(to_char(mom.operation_name)), ''),
            '-'
        ),
        1,
        50
    ) as varchar2(50)
) as OPERATION_NAME,  -- 拟实施手术及操作名称 是

               cast(
                   coalesce(o.operating_date, mom.start_date_time, mom.scheduled_date_time, t1.doc_title_time, t1.doc_finish_date)
                   as date
               ) as OPERATION_DATE,-- 拟实施手术及操作日期时间 是

               substr(
                   nvl(nullif(trim(cast(t3.sszz as varchar2(500))), ''), '-'),
                   1,
                   500
               ) as OPERATION_IN,-- 手术指征

               substr(
                   nvl(nullif(trim(cast(t3.ssjjz as varchar2(1000))), ''), '-'),
                   1,
                   1000
               ) as OPERATION_TABOO,-- 手术禁忌症

        cast(
    substrb(
        coalesce(
            nullif(
                trim(
                    regexp_substr(
                        dbms_lob.substr(t4.段落内容, 1000, 1),
                        '拟施手术名称[[:space:]]*[:：]?[[:space:]]*(.*?)(医方告知|一[、.．]|二[、.．]|$)',
                        1,
                        1,
                        'n',
                        1
                    )
                ),
                ''
            ),
            nullif(trim(to_char(o.operation_desc)), ''),
            nullif(trim(to_char(mom.operation_name)), ''),
            '-'
        ),
        1,
        30
    ) as varchar2(30)
) as OPERATION_WAY, -- 手术方式

               substr(
                   nvl(
                       regexp_substr(
                           nvl(
                               nvl(
                                   (select cast(cd.国标编码 as varchar2(20))
                                      from cda.cda_dictionary cd
                                     where cast(cd.字典名称 as varchar2(100)) = '麻醉方法代码表'
                                       and cast(cd.系统标识 as varchar2(20)) = 'HIS'
                                       and cast(cd.院标名称 as varchar2(100)) = cast(o.anaesthesia_method as varchar2(100))
                                       and rownum = 1),
                                   (select cast(cd.国标编码 as varchar2(20))
                                      from cda.cda_dictionary cd
                                     where cast(cd.字典名称 as varchar2(100)) = '麻醉方法代码表'
                                       and cast(cd.系统标识 as varchar2(20)) = '手麻'
                                       and cast(cd.院标名称 as varchar2(100)) = cast(mom.anesthesia_method as varchar2(100))
                                       and rownum = 1)
                               ),
                               '9'
                           ),
                           '^[0-9]+'
                       ),
                       '9'
                   ),
                   1,
                   2
               ) as ANAESTHESIA_CODE,-- 拟实施麻醉方法代码

               substr(
                   nvl(
                       nvl(
                           (select cast(cd.国标名称 as varchar2(50))
                              from cda.cda_dictionary cd
                             where cast(cd.字典名称 as varchar2(100)) = '麻醉方法代码表'
                               and cast(cd.系统标识 as varchar2(20)) = 'HIS'
                               and cast(cd.院标名称 as varchar2(100)) = cast(o.anaesthesia_method as varchar2(100))
                               and rownum = 1),
                           (select cast(cd.国标名称 as varchar2(50))
                              from cda.cda_dictionary cd
                             where cast(cd.字典名称 as varchar2(100)) = '麻醉方法代码表'
                               and cast(cd.系统标识 as varchar2(20)) = '手麻'
                               and cast(cd.院标名称 as varchar2(100)) = cast(mom.anesthesia_method as varchar2(100))
                               and rownum = 1)
                       ),
                       '其他麻醉方法'
                   ),
                   1,
                   50
               ) as ANAESTHESIA_NAME,-- 拟实施麻醉方法名称 是

               substr(
                   nvl(nullif(trim(cast(t3.sqzb as varchar2(1000))), ''), '-'),
                   1,
                   1000
               ) as OPERATION_READY,-- 术前准备

           substr(
    nvl(
        nullif(
            trim(
                regexp_substr(
                    cast(dbms_lob.substr(t4.段落内容, 1000, 1) as varchar2(1000)),
                    '术中或术后可能出现的并发症及手术风险[[:space:]]*[:：]?[[:space:]]*(.*?)(二[、.．][[:space:]]*替代医疗方案|三[、.．]|经治医师签名|患方明确意见)',
                    1, 1, 'n', 1
                )
            ),
            ''
        ),
        nvl(
            nullif(
                trim(
                    regexp_substr(
                        cast(dbms_lob.substr(t4.段落内容, 1000, 1) as varchar2(1000)),
                        '主要意外、风险及并发症[[:space:]]*[:：]?[[:space:]]*(.*?)(4[.．][[:space:]]*防范措施|5[.．][[:space:]]*可替代|6[.．][[:space:]]*医师声明|医师声明)',
                        1, 1, 'n', 1
                    )
                ),
                ''
            ),
            nvl(
                nullif(
                    trim(
                        regexp_substr(
                            cast(dbms_lob.substr(t4.段落内容, 1000, 1) as varchar2(1000)),
                            '患者住院期间的病情及风险告知[[:space:]]*[:：]?[[:space:]]*(.*?)(医师签名|医生已告知|患者签名|$)',
                            1, 1, 'n', 1
                        )
                    ),
                    ''
                ),
                '-'
            )
        )
    ),
    1,
    2000
) as OPERATIONING_RISK,-- 手术中可能出现的意外及风险

substr(
    nvl(
        nullif(
            trim(
                regexp_substr(
                    cast(dbms_lob.substr(t4.段落内容, 1000, 1) as varchar2(1000)),
                    '术中或术后可能出现的并发症及手术风险[[:space:]]*[:：]?[[:space:]]*(.*?)(二[、.．][[:space:]]*替代医疗方案|三[、.．]|经治医师签名|患方明确意见)',
                    1, 1, 'n', 1
                )
            ),
            ''
        ),
        nvl(
            nullif(
                trim(
                    regexp_substr(
                        cast(dbms_lob.substr(t4.段落内容, 1000, 1) as varchar2(1000)),
                        '主要意外、风险及并发症[[:space:]]*[:：]?[[:space:]]*(.*?)(4[.．][[:space:]]*防范措施|5[.．][[:space:]]*可替代|6[.．][[:space:]]*医师声明|医师声明)',
                        1, 1, 'n', 1
                    )
                ),
                ''
            ),
            nvl(
                nullif(
                    trim(
                        regexp_substr(
                            cast(dbms_lob.substr(t4.段落内容, 1000, 1) as varchar2(1000)),
                            '患者住院期间的病情及风险告知[[:space:]]*[:：]?[[:space:]]*(.*?)(医师签名|医生已告知|患者签名|$)',
                            1, 1, 'n', 1
                        )
                    ),
                    ''
                ),
                '-'
            )
        )
    ),
    1,
    1000
) as OPERATIONED_RISK,-- 手术后可能出现的意外及并发症
           cast(
    substrb(
        coalesce(
            nullif(
                trim(
                    regexp_substr(
                        dbms_lob.substr(t4.段落内容, 2000, 1),
                        '二[、.．][[:space:]]*替代医疗方案[[:space:]]*[:：]?[[:space:]]*(.*?)(三[、.．][[:space:]]*其他告知内容|经治医师签名|患方明确意见|$)',
                        1,
                        1,
                        'n',
                        1
                    )
                ),
                ''
            ),
            nullif(
                trim(
                    regexp_substr(
                        dbms_lob.substr(t4.段落内容, 2000, 1),
                        '5[.．][[:space:]]*可替代的方案[[:space:]]*[:：]?[[:space:]]*(.*?)(6[.．][[:space:]]*医师声明|7[.．][[:space:]]*患方意见|$)',
                        1,
                        1,
                        'n',
                        1
                    )
                ),
                ''
            ),
            '-'
        ),
        1,
        1000
    ) as varchar2(1000)
) as REPLACE_PLAN,    -- 替代方案

               substr(
                   '医方已向患者或法定代理人告知拟实施手术、麻醉方式、术中及术后可能发生的意外、并发症、风险及替代方案，患方已知情。',
                   1,
                   2000
               ) as ORG_VIEW,-- 医疗机构意见

            substr(
    nvl(
        nullif(
            trim(
                regexp_substr(
                    cast(dbms_lob.substr(t4.段落内容, 2000, 1) as varchar2(2000)),
                    '(患方明确意见|患方意见)[[:space:]]*[:：]?[[:space:]]*(.*?)(患者签名|或患者的监护人|被授权人|因抢救|$)',
                    1, 1, 'n', 2
                )
            ),
            ''
        ),
        '-'
    ),
    1,
    2000
) as PATIENT_VIEW, -- 患者/法定代理人意见

               substr(
                   nvl(nullif(trim(cast(t.p_name as varchar2(50))), ''), nvl(cast(pmi.name as varchar2(50)), '-')),
                   1,
                   50
               ) as PATIENT_SIGN_NAME,-- 患者签名 是

               substr(
                   nvl(nullif(trim(cast(p.next_of_kin as varchar2(50))), ''), '-'),
                   1,
                   50
               ) as STATUTORY_AGENT_VIEW,-- 法定代理人签名

               substr(
                   nvl(
                       (select cast(cd.国标编码 as varchar2(2))
                          from cda.cda_dictionary cd
                         where cast(cd.字典名称 as varchar2(100)) = '家庭关系代码'
                           and cast(cd.院标编码 as varchar2(100)) = cast(pmi.relationship as varchar2(100))
                           and rownum = 1),
                       '8'
                   ),
                   1,
                   2
               ) as SAP_RELATIONSHIP_CODE,-- 法定代理人与患者的关系代码

               substr(
                   nvl(
                       (select cast(cd.国标名称 as varchar2(50))
                          from cda.cda_dictionary cd
                         where cast(cd.字典名称 as varchar2(100)) = '家庭关系代码'
                           and cast(cd.院标编码 as varchar2(100)) = cast(pmi.relationship as varchar2(100))
                           and rownum = 1),
                       '其他'
                   ),
                   1,
                   50
               ) as SAP_RELATIONSHIP_NAME,-- 法定代理人与患者的关系名称

              cast(
    case
        when t1.doc_finish_date is not null
         and t1.doc_finish_date >= date '1900-01-01'
        then t1.doc_finish_date

        when t1.doc_title_time is not null
         and t1.doc_title_time >= date '1900-01-01'
        then t1.doc_title_time

        when t1.modifiedon is not null
         and t1.modifiedon >= date '1900-01-01'
        then t1.modifiedon

        else p.admission_date_time
    end
    as date
) as PATIENT_SIGN_DATE,  -- 患者/法定代理人签名日期 是

               substr(
                   nvl(
                       (select cast(yg.name as varchar2(50))
                          from his.staff_dict yg
                         where yg.emp_no = p.doctor_in_charge
                           and rownum = 1),
                       '-'
                   ),
                   1,
                   50
               ) as DOCTOR,-- 经治医师签名

               substr(
                   nvl(
                       case
                           when regexp_like(cast(o.operator as varchar2(50)), '^[0-9]+$')
                           then (select cast(sd.name as varchar2(50))
                                   from his.staff_dict sd
                                  where sd.emp_no = o.operator
                                    and rownum = 1)
                           else nvl(
                                   (select cast(sd.name as varchar2(50))
                                      from his.staff_dict sd
                                     where sd.user_name = mom.SURGEON
                                       and rownum = 1),
                                   cast(o.operator as varchar2(50))
                                )
                       end,
                       '-'
                   ),
                   1,
                   50
               ) as OPERATOR,-- 手术者签名 是
               cast(
                   nvl(t1.modifiedon, nvl(t1.doc_finish_date, t1.doc_title_time))
                   as date
               ) as DOC_DATE -- 医师签名日期时间 是
from mtl.epr_inpatient_docindex t
inner join mtl.epr_inpatient t1
        on t.uhid = t1.uhid
       and   cast(t1.doc_type_name as varchar2(100)) = '手术同意书'

left join mtl.emrsd46 t3
       on t3.段落编号 = t1.id

left join mtl.emrsd_content t4
       on t4.uhid = t1.uhid
      and t4.段落编号 = t1.id

left join his.pat_master_index pmi
       on t.p_inpatient_no = pmi.inp_no

left join his.pat_visit p
       on pmi.patient_id = p.patient_id
      and t.p_inpatient_times = p.visit_id

left join sm.med_operation_master mom
       on mom.patient_id = p.patient_id
      and mom.visit_id = t.p_inpatient_times

left join (select * from (
select o.*,
       row_number() over (
           partition by
               o.patient_id,
               o.visit_id,
               trunc(o.operating_date)
           order by
               o.operation_scale desc nulls last,
               case
                   when to_char(o.op_primary) = '1' then 1
                   else 0
               end desc,
               o.operation_no asc nulls last
       ) as rn
from his.operation o  )  where rn=1       and not regexp_like(
              nvl(cast(operation_desc as varchar2(500)), '-'),
              '输血|红细胞|血浆|血细胞|成份血|血液透析|血液滤过|气管内插管|呼吸机|中心静脉|动脉穿刺|鼻十二指肠|营养管|肺泡灌洗|支气管镜'
          )    )  o
               on mom.patient_id = o.patient_id
              and mom.visit_id = o.visit_id
            and to_char(o.operating_date,'yyyy-mm-dd')=to_char( nvl(mom.start_date_time,mom.SCHEDULED_DATE_TIME),'yyyy-mm-dd')


left join (
    select a.patient_id,
           a.visit_id,
           a.diagnosis_code,
           a.diagnosis_desc,
           row_number() over (
               partition by a.patient_id, a.visit_id
               order by
                   case
                       when a.diagnosis_type = '2' then 1
                       when a.diagnosis_type = '1' then 2
                       when a.diagnosis_type = '3' then 3
                       else 4
                   end,
                   a.diagnosis_no
           ) as rn
      from his.diagnosis a
) dd
       on dd.rn = 1
      and p.patient_id = dd.patient_id
      and p.visit_id = dd.visit_id

where p.discharge_date_time >= to_date('2021-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss')
  and p.discharge_date_time <  to_date('2025-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss')
and not regexp_like(
        cast(dbms_lob.substr(t4.段落内容, 500, 1) as varchar2(500)),
        '医患沟通书|激素治疗'
    )


    ) q
)
where rn = 1
