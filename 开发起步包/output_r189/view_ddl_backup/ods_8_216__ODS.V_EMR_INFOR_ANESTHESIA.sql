
  CREATE OR REPLACE FORCE VIEW "ODS"."V_EMR_INFOR_ANESTHESIA" ("ID", "ORG_CODE", "ORG_NAME", "DISTRICT_CODE", "EXCHANGE_TYPE", "SYSTEM_TIME", "ADMISSION_ID", "INFORMED_CONSENT_CODE", "INFORMED_CONSENT_NAME", "APPLY_NUM", "DEPT_CODE", "DEP_NAME", "AREA_NAME", "WARD_NUM", "SICKBED_NUM", "PATIENT_NAME", "SEX_CODE", "SEX_NAME", "AGE", "AGE_MONTH", "PREOPERATIVE", "PREOPERATIVE_NAME", "OPERATION", "OPERATION_NAME", "OPERATION_DATE", "ANAESTHESIA_CODE", "ANAESTHESIA_NAME", "PATIENT_BASIC_CONDITION", "EFFECTS_BD_ANESTHESIA", "PERFORM_IO_DM", "AOC_ANESTHESIA", "SIGN_ANA_PUMP", "ANA_SAFETY_SIGN", "ORG_VIEW", "PATIENT_VIEW", "PATIENT_SIGN_NAME", "STATUTORY_AGENT_VIEW", "SAP_RELATIONSHIP", "SAP_RELATIONSHIP_NAME", "PATIENT_SIGN_DATE", "ANADOC", "ANADOC_DATE") AS 
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
       ANAESTHESIA_CODE,
       ANAESTHESIA_NAME,
       PATIENT_BASIC_CONDITION,
       EFFECTS_BD_ANESTHESIA,
       PERFORM_IO_DM,
       AOC_ANESTHESIA,
       SIGN_ANA_PUMP,
       ANA_SAFETY_SIGN,
       ORG_VIEW,
       PATIENT_VIEW,
       PATIENT_SIGN_NAME,
       STATUTORY_AGENT_VIEW,
       SAP_RELATIONSHIP,
       SAP_RELATIONSHIP_NAME,
       PATIENT_SIGN_DATE,
       ANADOC,
       ANADOC_DATE
from (
    select q.*,
           row_number() over (
               partition by q.ID
               order by q.OPERATION_DATE desc nulls last,
                        q.PATIENT_SIGN_DATE desc nulls last
           ) as rn
    from (
        select substr(
                   '49557032X'||'|'||
                   nvl(to_char(mom.patient_id), '-')||'|'||
                   nvl(to_char(mom.visit_id), '-')||'|'||
                   nvl(to_char(mom.oper_id), '0'),
                   1,
                   100
               ) as ID,-- 内码 是 主键

               '49557032X' as ORG_CODE,-- 医院组织机构代码

               '山东省第二人民医院' as ORG_NAME,-- 医院名称

               '370104' as DISTRICT_CODE,-- 所属行政区划

               'ADDHIS' as EXCHANGE_TYPE,-- 交换类型

               cast(systimestamp as timestamp) as SYSTEM_TIME,-- 数据上传时间戳

               substr(
                   nvl(to_char(mom.patient_id), '-')||'|'||nvl(to_char(mom.visit_id), '-'),
                   1,
                   50
               ) as ADMISSION_ID,-- 住院唯一标识号

               substr(
                   nvl(to_char(mom.patient_id), '-')||
                   nvl(to_char(mom.visit_id), '-')||
                   nvl(to_char(mom.oper_id), '-'),
                   1,
                   20
               ) as INFORMED_CONSENT_CODE,-- 知情同意书编号

               '麻醉知情同意书' as INFORMED_CONSENT_NAME,-- 知情同意书名称

               substr(
                   nvl(to_char(mom.oper_id), '-'),
                   1,
                   20
               ) as APPLY_NUM,-- 手术申请单编号

               substr(
                   nvl(
                       (select cast(ks.qmpt_code as varchar2(50))
                          from his.dept_dict ks
                         where ks.dept_code = pv.dept_discharge_from
                           and rownum = 1),
                       nvl(cast(pv.dept_discharge_from as varchar2(50)), '-')
                   ),
                   1,
                   50
               ) as DEPT_CODE,-- 科室代码

               substr(
                   nvl(
                       (select cast(ks.qmpt_name as varchar2(50))
                          from his.dept_dict ks
                         where ks.dept_code = pv.dept_discharge_from
                           and rownum = 1),
                       nvl(
                           (select cast(ks.dept_name as varchar2(50))
                              from his.dept_dict ks
                             where ks.dept_code = pv.dept_discharge_from
                               and rownum = 1),
                           '-'
                       )
                   ),
                   1,
                   50
               ) as DEP_NAME,-- 科室名称 是

               substr(
                   nvl(
                       (select cast(ks.dept_name as varchar2(50))
                          from his.dept_dict ks
                         where ks.dept_code = pv.discharge_ward_code
                           and rownum = 1),
                       '-'
                   ),
                   1,
                   50
               ) as AREA_NAME,-- 病区名称

               cast(null as varchar2(10)) as WARD_NUM,-- 病房号

               substr(
                   cast(pv.discharge_bed_no as varchar2(10)),
                   1,
                   10
               ) as SICKBED_NUM,-- 病床号

               substr(
                   nvl(nullif(trim(cast(pmi.name as varchar2(50))), ''), '-'),
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
                    and pv.admission_date_time is not null
                   then least(
                            greatest(
                                trunc(months_between(pv.admission_date_time, pmi.date_of_birth) / 12),
                                0
                            ),
                            200
                        )
                   else 0
               end as AGE,-- 年龄
  case
           when pmi.date_of_birth is not null
            and pv.admission_date_time is not null
            and months_between(pv.admission_date_time, pmi.date_of_birth) >= 1
            and months_between(pv.admission_date_time, pmi.date_of_birth) < 12
           then greatest(trunc(months_between(pv.admission_date_time, pmi.date_of_birth)), 1)
           else 0
       end as AGE_MONTH,-- 年龄（月） 不足一岁时填写，在1-12范围内的整数

             cast(
    coalesce(
        /* 优先取手麻系统诊断对应的国标编码 */
        (
            select max(to_char(cd.国标编码))
              from cda.cda_dictionary cd
             where cd.字典名称 = 'ICD-10诊断编码'
               and cd.系统标识 = 'SM'
               and cd.院标名称 = mom.diag_before_operation
        ),

        /* 其次取HIS诊断对应的国标编码 */
        (
            select max(to_char(cd.国标编码))
              from cda.cda_dictionary cd
             where cd.字典名称 = 'ICD-10诊断编码'
               and cd.系统标识 = 'HIS'
               and (
                       cd.院标编码 = dd.diagnosis_code
                    or cd.院标名称 = dd.diagnosis_desc
                   )
        ),

        /* 未对照时保留机构原始诊断编码，不再截断 */
        nullif(trim(to_char(dd.diagnosis_code)), '')
    )
    as varchar2(50)
) as PREOPERATIVE,  -- 术前诊断编码

              cast(
    substrb(
        coalesce(
            /* 手麻诊断对应的国标名称 */
            (
                select max(to_char(cd.国标名称))
                  from cda.cda_dictionary cd
                 where cd.字典名称 = 'ICD-10诊断编码'
                   and cd.系统标识 = 'SM'
                   and cd.院标名称 = mom.diag_before_operation
            ),

            /* HIS诊断对应的国标名称 */
            (
                select max(to_char(cd.国标名称))
                  from cda.cda_dictionary cd
                 where cd.字典名称 = 'ICD-10诊断编码'
                   and cd.系统标识 = 'HIS'
                   and (
                           cd.院标编码 = dd.diagnosis_code
                        or cd.院标名称 = dd.diagnosis_desc
                       )
            ),

            /* 保留原始术前诊断名称 */
            nullif(trim(to_char(mom.diag_before_operation)), ''),

            /* HIS诊断名称兜底 */
            nullif(trim(to_char(dd.diagnosis_desc)), ''),

            '-'
        ),
        1,
        50
    )
    as varchar2(50)
) as PREOPERATIVE_NAME,  -- 术前诊断名称 是

            cast(
    coalesce(
        /* 手麻手术名称对应的国标编码 */
        (
            select max(to_char(cd.国标编码))
              from cda.cda_dictionary cd
             where cd.字典名称 = 'ICD-9手术编码'
               and cd.系统标识 = 'SM'
               and cd.院标名称 = mom.operation_name
        ),

        /* 麻醉计划手术名称对应的国标编码 */
        (
            select max(to_char(cd.国标编码))
              from cda.cda_dictionary cd
             where cd.字典名称 = 'ICD-9手术编码'
               and cd.系统标识 = 'SM'
               and cd.院标名称 = map.operation_name
        ),

        /* HIS手术名称对应的国标编码 */
        (
            select max(to_char(cd.国标编码))
              from cda.cda_dictionary cd
             where cd.字典名称 = 'ICD-9手术编码'
               and cd.系统标识 = 'HIS'
               and cd.院标名称 = o.operation_desc
        ),

        /* HIS手术编码对应的国标编码 */
        (
            select max(to_char(cd.国标编码))
              from cda.cda_dictionary cd
             where cd.字典名称 = 'ICD-9手术编码'
               and cd.系统标识 = 'HIS'
               and cd.院标编码 = o.operation_code
        ),

        /* 未对照时保留原始编码 */
        nullif(trim(to_char(o.operation_code)), '')
    )
    as varchar2(50)
) as OPERATION,  -- 拟实施手术及操作编码
 cast(
    substrb(
        coalesce(
            /* 优先使用手麻系统手术名称 */
            nullif(trim(to_char(mom.operation_name)), ''),

            /* 其次使用麻醉计划手术名称 */
            nullif(trim(to_char(map.operation_name)), ''),

            /* 再使用HIS手术名称 */
            nullif(trim(to_char(o.operation_desc)), ''),

            '-'
        ),
        1,
        50
    )
    as varchar2(50)
) as OPERATION_NAME, -- 拟实施手术及操作名称 是

               cast(
                   coalesce(mom.start_date_time, o.operating_date, mos.scheduled_date_time)
                   as date
               ) as OPERATION_DATE,-- 拟实施手术及操作日期

               substr(
                   nvl(
                       regexp_substr(
                           nvl(
                               (select cast(cd.国标编码 as varchar2(20))
                                  from cda.cda_dictionary cd
                                 where cd.字典名称 = '麻醉方法代码表'
                                   and cd.系统标识 = '手麻'
                                   and cd.院标名称 = mom.anesthesia_method
                                   and rownum = 1),
                               '9'
                           ),
                           '^[0-9]+'
                       ),
                       '9'
                   ),
                   1,
                   2
               ) as ANAESTHESIA_CODE,-- 拟实施麻醉方法代码 是

               substr(
                   nvl(
                       (select cast(cd.国标名称 as varchar2(50))
                          from cda.cda_dictionary cd
                         where cd.字典名称 = '麻醉方法代码表'
                           and cd.系统标识 = '手麻'
                           and cd.院标名称 = mom.anesthesia_method
                           and rownum = 1),
                       '其他麻醉方法'
                   ),
                   1,
                   50
               ) as ANAESTHESIA_NAME,-- 拟实施麻醉方法名称 是

               substr(
                   nvl(cast(dd.diagnosis_desc as varchar2(500)), '-'),
                   1,
                   500
               ) as PATIENT_BASIC_CONDITION,-- 患者基础疾病

               substr(
                   '患者基础疾病、年龄、个体差异及麻醉药物反应可能增加麻醉风险，可能出现呼吸循环抑制、心脑血管意外、过敏反应、恶性高热、误吸、气道痉挛、插管困难、神经血管损伤、出血、感染、血栓、术后认知功能障碍、恶心呕吐、尿潴留、镇痛不全等情况，严重者可危及生命。麻醉方案可能根据病情变化进行调整。',
                   1,
                   1000
               ) as EFFECTS_BD_ANESTHESIA,-- 基础疾病对麻醉可能产生的影响

               substr(
                   nvl(cast(map.operation_name as varchar2(2000)), '-'),
                   1,
                   2000
               ) as PERFORM_IO_DM,-- 执行有创操作和检测方法

               substr(
                   '麻醉中及麻醉后可能发生药物过敏、呼吸循环抑制、心脑血管意外、心跳呼吸骤停、恶性高热、误吸、气道痉挛、插管困难、牙齿或口腔黏膜损伤、喉头水肿、声音嘶哑、神经血管损伤、气胸、出血、感染、血栓、术后认知功能障碍、恶心呕吐、皮肤瘙痒、尿潴留、镇痛不全等意外及并发症，严重者可危及生命。医师将根据患者病情采取相应预防和处理措施。',
                   1,
                   1000
               ) as AOC_ANESTHESIA,-- 麻醉中、麻醉后可能发生的意外及并发症 是

               '0' as SIGN_ANA_PUMP,-- 使用麻醉镇痛泵标志

               '0' as ANA_SAFETY_SIGN,-- 参加麻醉安全保险标志

               substr(
                   '医方已向患者或法定代理人告知拟实施麻醉方式、麻醉必要性、可能风险、并发症、替代方案及相关处理措施，并对患方疑问进行解释。',
                   1,
                   2000
               ) as ORG_VIEW,-- 医疗机构意见

               substr(
                   '我已详细了解上述内容，对麻醉必要性、麻醉风险及相关并发症表示理解，同意实施麻醉。',
                   1,
                   2000
               ) as PATIENT_VIEW,-- 患者/法定代理人意见

               substr(
                   nvl(nullif(trim(cast(pmi.name as varchar2(50))), ''), '-'),
                   1,
                   50
               ) as PATIENT_SIGN_NAME,-- 患者签名 是

               substr(
                   nvl(nullif(trim(cast(pv.next_of_kin as varchar2(50))), ''), '-'),
                   1,
                   50
               ) as STATUTORY_AGENT_VIEW,-- 法定代理人签名

               substr(
                   nvl(
                       (select cast(cd.国标编码 as varchar2(2))
                          from cda.cda_dictionary cd
                         where cd.字典名称 = '家庭关系代码'
                           and cd.院标编码 = pmi.relationship
                           and rownum = 1),
                       '8'
                   ),
                   1,
                   2
               ) as SAP_RELATIONSHIP,-- 法定代理人与患者关系代码

               substr(
                   nvl(
                       (select cast(cd.国标名称 as varchar2(50))
                          from cda.cda_dictionary cd
                         where cd.字典名称 = '家庭关系代码'
                           and cd.院标编码 = pmi.relationship
                           and rownum = 1),
                       '其他'
                   ),
                   1,
                   50
               ) as SAP_RELATIONSHIP_NAME,-- 法定代理人与患者关系名称

               cast(
                   nvl(
                       (
                           select max(
                                      case
                                          when regexp_like(trim(cast(mcd.item_value as varchar2(100))), '^[0-9]{14}$')
                                          then to_date(trim(cast(mcd.item_value as varchar2(100))), 'yyyymmddhh24miss')

                                          when regexp_like(trim(cast(mcd.item_value as varchar2(100))), '^[0-9]{4}-[0-9]{2}-[0-9]{2}')
                                          then to_date(substr(trim(cast(mcd.item_value as varchar2(100))), 1, 19), 'yyyy-mm-dd hh24:mi:ss')

                                          else null
                                      end
                                  )
                             from sm.med_custom_data mcd
                            where mcd.item_name = '同意书.签名时间'
                              and mcd.patient_id = mom.patient_id
                              and mcd.visit_id = mom.visit_id
                              and mcd.oper_id = mom.oper_id
                       ),
                       nvl(mos.scheduled_date_time, nvl(mom.start_date_time, pv.admission_date_time))
                   )
                   as date
               ) as PATIENT_SIGN_DATE,-- 患者/法定代理人签名日期 是
nvl(cast(
    substrb(
        coalesce(
            nullif(
                trim(
                    case
                        when regexp_like(
                                 to_char(mom.anesthesia_doctor),
                                 '^[0-9]+$'
                             )
                        then (
                            select max(to_char(sd.name))
                              from his.staff_dict sd
                             where sd.emp_no = mom.anesthesia_doctor
                        )
                        else to_char(mom.anesthesia_doctor)
                    end
                ),
                ''
            ),

            nullif(
                trim(
                    case
                        when regexp_like(
                                 to_char(o.anesthesia_doctor),
                                 '^[0-9]+$'
                             )
                        then (
                            select max(to_char(sd.name))
                              from his.staff_dict sd
                             where sd.emp_no = o.anesthesia_doctor
                        )
                        else to_char(o.anesthesia_doctor)
                    end
                ),
                ''
            ),

            '-'
        ),
        1,
        50
    )
    as varchar2(50)
),'-') as ANADOC,  -- 麻醉医生签名 是

               cast(
                   nvl(
                       mom.anes_start_date_time,
                       nvl(mom.start_date_time, nvl(mos.scheduled_date_time, pv.admission_date_time))
                   )
                   as date
               ) as ANADOC_DATE-- 麻醉医师签名日期时间 是

          from sm.med_operation_master mom

          left join his.pat_visit pv
                 on mom.patient_id = pv.patient_id
                and mom.visit_id = pv.visit_id

          left join his.pat_master_index pmi
                 on mom.patient_id = pmi.patient_id



left join  (select * from (
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
from his.operation o  )  where rn=1)   o
       on o.patient_id = mom.patient_id
      and o.visit_id = mom.visit_id
      and (
              to_char(o.operation_no) = to_char(mom.oper_id)

           or (
                  o.operating_date is not null
              and nvl(mom.scheduled_date_time, mom.start_date_time) is not null
              and trunc(o.operating_date) =
                  trunc(nvl(mom.scheduled_date_time, mom.start_date_time))
              and o.operation_desc is not null
              and mom.operation_name is not null
              and (
                     instr(
                         substrb(cast(o.operation_desc as varchar2(4000)), 1, 500),
                         substrb(cast(mom.operation_name as varchar2(4000)), 1, 500)
                     ) > 0

                  or instr(
                         substrb(cast(mom.operation_name as varchar2(4000)), 1, 500),
                         substrb(cast(o.operation_desc as varchar2(4000)), 1, 500)
                     ) > 0
              )
           )
          )

          left join sm.med_anesthesia_plan map
                 on map.patient_id = mom.patient_id
                and map.visit_id = mom.visit_id
                and map.oper_id = mom.oper_id

          left join sm.med_operation_schedule mos
                 on mos.patient_id = mom.patient_id
                and mos.visit_id = mom.visit_id
                and mos.schedule_id = mom.oper_id

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
                and mom.patient_id = dd.patient_id
                and mom.visit_id = dd.visit_id

         where pv.discharge_date_time >= to_date('2021-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss')
           and pv.discharge_date_time <  to_date('2025-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss')
    ) q
)
where rn = 1   and  OPERATION_NAME is not null
