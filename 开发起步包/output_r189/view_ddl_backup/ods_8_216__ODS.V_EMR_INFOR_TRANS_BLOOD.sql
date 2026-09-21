
  CREATE OR REPLACE FORCE VIEW "ODS"."V_EMR_INFOR_TRANS_BLOOD" ("ID", "ORG_CODE", "ORG_NAME", "DISTRICT_CODE", "EXCHANGE_TYPE", "SYSTEM_TIME", "PATIENT_TYPE", "VISTING_NUM", "INFORMED_CONSENT_CODE", "INFORMED_CONSENT_NAME", "APPLY_NUM", "DEPT_CODE", "DEP_NAME", "AREA_NAME", "WARD_NUM", "SICKBED_NUM", "PATIENT_NAME", "SEX_CODE", "SEX_NAME", "AGE", "AGE_MONTH", "DISEASE_CODE", "DISEASE_NAME", "BT_HISTORY_CODE", "BT_HISTORY_NAME", "TRANSFUSION_TRIGGER", "VOB_CODE", "VOB_NAME", "TRANSFUSION_BCPR", "TRANSFUSION_WAY", "PROTOCOL_TRANSFUSION_DATE", "ORG_VIEW", "PATIENT_VIEW", "STATUTORY_AGENT_VIEW", "SAP_RELATIONSHIP", "SAP_RELATIONSHIP_NAME", "PATIENT_SIGN_DATE", "OPERATOR", "DOC_DATE") AS 
  select cast(substrb(ID, 1, 100) as varchar2(100)) as ID,
       cast(substrb(ORG_CODE, 1, 32) as varchar2(32)) as ORG_CODE,
       cast(substrb(ORG_NAME, 1, 70) as varchar2(70)) as ORG_NAME,
       cast(substrb(DISTRICT_CODE, 1, 6) as varchar2(6)) as DISTRICT_CODE,
       cast(substrb(EXCHANGE_TYPE, 1, 10) as varchar2(10)) as EXCHANGE_TYPE,
       SYSTEM_TIME,
       cast(substrb(PATIENT_TYPE, 1, 2) as varchar2(2)) as PATIENT_TYPE,
       cast(substrb(VISTING_NUM, 1, 50) as varchar2(50)) as VISTING_NUM,
       cast(substrb(INFORMED_CONSENT_CODE, 1, 20) as varchar2(20)) as INFORMED_CONSENT_CODE,
       cast(substrb(INFORMED_CONSENT_NAME, 1, 200) as varchar2(200)) as INFORMED_CONSENT_NAME,
       cast(substrb(APPLY_NUM, 1, 20) as varchar2(20)) as APPLY_NUM,
       cast(substrb(DEPT_CODE, 1, 50) as varchar2(50)) as DEPT_CODE,
       cast(substrb(DEP_NAME, 1, 50) as varchar2(50)) as DEP_NAME,
       cast(substrb(AREA_NAME, 1, 50) as varchar2(50)) as AREA_NAME,
       cast(substrb(WARD_NUM, 1, 10) as varchar2(10)) as WARD_NUM,
       cast(substrb(SICKBED_NUM, 1, 10) as varchar2(10)) as SICKBED_NUM,
       cast(substrb(PATIENT_NAME, 1, 50) as varchar2(50)) as PATIENT_NAME,
       SEX_CODE,
       cast(substrb(SEX_NAME, 1, 50) as varchar2(50)) as SEX_NAME,
       AGE,
       cast(substrb(AGE_MONTH, 1, 8) as varchar2(8)) as AGE_MONTH,
       cast(substrb(DISEASE_CODE, 1, 12) as varchar2(12)) as DISEASE_CODE,
       cast(substrb(DISEASE_NAME, 1, 50) as varchar2(50)) as DISEASE_NAME,
       BT_HISTORY_CODE,
       cast(substrb(BT_HISTORY_NAME, 1, 50) as varchar2(50)) as BT_HISTORY_NAME,
       cast(substrb(TRANSFUSION_TRIGGER, 1, 500) as varchar2(500)) as TRANSFUSION_TRIGGER,
       VOB_CODE,
       cast(substrb(VOB_NAME, 1, 50) as varchar2(50)) as VOB_NAME,
       cast(substrb(TRANSFUSION_BCPR, 1, 200) as varchar2(200)) as TRANSFUSION_BCPR,
       cast(substrb(TRANSFUSION_WAY, 1, 50) as varchar2(50)) as TRANSFUSION_WAY,
       PROTOCOL_TRANSFUSION_DATE,
       cast(substrb(ORG_VIEW, 1, 2000) as varchar2(2000)) as ORG_VIEW,
       cast(substrb(PATIENT_VIEW, 1, 2000) as varchar2(2000)) as PATIENT_VIEW,
       cast(substrb(STATUTORY_AGENT_VIEW, 1, 50) as varchar2(50)) as STATUTORY_AGENT_VIEW,
       cast(substrb(SAP_RELATIONSHIP, 1, 2) as varchar2(2)) as SAP_RELATIONSHIP,
       cast(substrb(SAP_RELATIONSHIP_NAME, 1, 50) as varchar2(50)) as SAP_RELATIONSHIP_NAME,
       PATIENT_SIGN_DATE,
       cast(substrb(OPERATOR, 1, 50) as varchar2(50)) as OPERATOR,
       DOC_DATE
from (
    select q.*,
           row_number() over (
               partition by q.ID
               order by q.PATIENT_SIGN_DATE desc nulls last,
                        q.PROTOCOL_TRANSFUSION_DATE desc nulls last
           ) as rn
    from (
        select substr(
    '49557032X'||'|'||
    nvl(to_char(tr.hzbs), '-')||'|'||
    nvl(to_char(tr.zycs), '-')||'|'||
    nvl(to_char(tr.sqlsh), '-')||'|'||
    nvl(
        regexp_substr(
            nvl(
                (select max(cast(cd.国标编码 as varchar2(20)))
                   from cda.cda_dictionary cd
                  where cd.院标名称 = s2.xymc
                    and cd.字典名称 = '输血品种代码字典'),
                '9'
            ),
            '^[0-9]+'
        ),
        '9'
    ),
    1,
    100
) as ID, -- 内码 是 主键

               '49557032X' as ORG_CODE,-- 医院组织机构代码 是

               '山东省第二人民医院' as ORG_NAME,-- 医院名称 是

               '370104' as DISTRICT_CODE,-- 所属行政区划 是

               'ADDHIS' as EXCHANGE_TYPE,-- 交换类型 是

               cast(systimestamp as timestamp) as SYSTEM_TIME,-- 数据上传时间戳 是

               '2' as PATIENT_TYPE,-- 病人类型 是；建议用代码，避免“住院”超 VARCHAR2(2)

               substr(
                   nvl(to_char(tr.hzbs), '-')||'|'||nvl(to_char(tr.zycs), '-'),
                   1,
                   50
               ) as VISTING_NUM,-- 就诊号 是

               substr(
                   nvl(to_char(tr.sqlsh), '-'),
                   1,
                   20
               ) as INFORMED_CONSENT_CODE,-- 知情同意书编号

               '输血治疗同意书' as INFORMED_CONSENT_NAME,-- 知情同意书名称

               substr(
                   nvl(to_char(tr.sqlsh), '-'),
                   1,
                   20
               ) as APPLY_NUM,-- 输血申请单编号

               substr(
                   nvl(
                       (select cast(ks.qmpt_code as varchar2(50))
                          from his.dept_dict ks
                         where ks.dept_code = p.dept_discharge_from
                           and rownum = 1),
                       nvl(cast(p.dept_discharge_from as varchar2(50)), '-')
                   ),
                   1,
                   50
               ) as DEPT_CODE,-- 科室代码

               substr(
                   nvl(
                       (select cast(ks.qmpt_name as varchar2(50))
                          from his.dept_dict ks
                         where ks.dept_code = p.dept_discharge_from
                           and rownum = 1),
                       nvl(
                           (select cast(ks.dept_name as varchar2(50))
                              from his.dept_dict ks
                             where ks.dept_code = p.dept_discharge_from
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
                         where ks.dept_code = p.discharge_ward_code
                           and rownum = 1),
                       '-'
                   ),
                   1,
                   50
               ) as AREA_NAME,-- 病区名称

               cast(null as varchar2(10)) as WARD_NUM,-- 病房号

               substr(
                   cast(p.discharge_bed_no as varchar2(10)),
                   1,
                   10
               ) as SICKBED_NUM,-- 病床号

               substr(
                   nvl(nullif(trim(cast(tr.hzxm as varchar2(50))), ''), nvl(cast(pmi.name as varchar2(50)), '-')),
                   1,
                   50
               ) as PATIENT_NAME,-- 患者姓名 是

               case
                   when cast(tr.xb as varchar2(10)) = '男' then 1
                   when cast(tr.xb as varchar2(10)) = '女' then 2
                   when cast(tr.xb as varchar2(10)) = '未知' then 0
                   else 9
               end as SEX_CODE,-- 性别代码 是

               substr(
                   case
                       when cast(tr.xb as varchar2(10)) = '男' then '男'
                       when cast(tr.xb as varchar2(10)) = '女' then '女'
                       when cast(tr.xb as varchar2(10)) = '未知' then '未知'
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
                   8
               ) as AGE_MONTH,-- 年龄(月) 0-11

     cast(
    substrb(
        nvl(
            nullif(
                trim(
                    (select max(substrb(to_char(cd.国标编码), 1, 12))
                       from cda.cda_dictionary cd
                      where cd.字典名称 = 'ICD-10诊断编码'
                        and cd.系统标识 = 'HIS'
                        and cd.院标编码 = dd.diagnosis_code)
                ),
                ''
            ),
            nullif(substrb(to_char(dd.diagnosis_code), 1, 12), '')
        ),
        1,
        12
    ) as varchar2(12)
) as DISEASE_CODE, -- 疾病诊断编码

            cast(
    substrb(
        nvl(
            nullif(
                trim(
                    (select max(substrb(to_char(cd.国标名称), 1, 50))
                       from cda.cda_dictionary cd
                      where cd.字典名称 = 'ICD-10诊断编码'
                        and cd.系统标识 = 'HIS'
                        and cd.院标编码 = dd.diagnosis_code)
                ),
                ''
            ),
            nvl(substrb(to_char(dd.diagnosis_desc), 1, 50), '-')
        ),
        1,
        50
    ) as varchar2(50)
) as DISEASE_NAME, -- 疾病诊断名称 是

               9 as BT_HISTORY_CODE,-- 输血史标识代码：1无 2有 9未说明

               '未说明' as BT_HISTORY_NAME,-- 有无输血史

               substr(
                   nvl(
                       nullif(trim(cast(tr.pgtzms as varchar2(500))), ''),
                       nvl(nullif(trim(cast(tr.sxmd as varchar2(500))), ''), '-')
                   ),
                   1,
                   500
               ) as TRANSFUSION_TRIGGER,-- 输血指征

               nvl(
                   to_number(
                       regexp_substr(
                           nvl(
                               (select max(cast(cd.国标编码 as varchar2(20)))
                                  from cda.cda_dictionary cd
                                 where cd.院标名称 = s2.xymc
                                   and cd.字典名称 = '输血品种代码字典'),
                               '9'
                           ),
                           '^[0-9]+'
                       )
                   ),
                   9
               ) as VOB_CODE,-- 输血品种代码 NUMBER(2)

               substr(
                   nvl(
                       (select max(cast(cd.国标名称 as varchar2(50)))
                          from cda.cda_dictionary cd
                         where cd.院标名称 = s2.xymc
                           and cd.字典名称 = '输血品种代码字典'),
                       nvl(cast(s2.xymc as varchar2(50)), '其他')
                   ),
                   1,
                   50
               ) as VOB_NAME,-- 输血品种名称

              substr('输血前检查#详见病历', 1, 200) as TRANSFUSION_BCPR,-- 输血前有关检查项目及结果 是

               substr('异体输血', 1, 50) as TRANSFUSION_WAY,-- 输血方式

               cast(
                   case
                       when tr.yjsxsj is not null
                        and regexp_like(trim(cast(tr.yjsxsj as varchar2(30))), '^[0-9]{4}-[0-9]{2}-[0-9]{2}')
                       then to_date(substr(trim(cast(tr.yjsxsj as varchar2(30))), 1, 19), 'yyyy-mm-dd hh24:mi:ss')

                       when tr.yjsxsj is not null
                        and regexp_like(trim(cast(tr.yjsxsj as varchar2(30))), '^[0-9]{14}$')
                       then to_date(trim(cast(tr.yjsxsj as varchar2(30))), 'yyyymmddhh24miss')

                       else null
                   end
                   as date
               ) as PROTOCOL_TRANSFUSION_DATE,-- 拟定输血日期时间 DATE

               substr(
                   '患者因病情需要拟行输血或血液制品治疗。医方已告知输血必要性、益处、可能风险及替代方案，并将严格执行临床输血相关规范，合理选择输血适应证、输血方式和输血方案。输血过程中可能发生发热、过敏、溶血、感染、输血相关循环负荷过重、输血相关急性肺损伤、病情加重甚至危及生命等风险。一旦发生风险或意外，医方将积极采取相应处理措施。',
                   1,
                   2000
               ) as ORG_VIEW,-- 医疗机构意见

               substr(
                   '医师已向我告知输血或血液制品治疗的原因、必要性、益处、可能风险及不良反应，我已理解并同意根据病情需要实施输血或血液制品治疗，并同意在紧急情况下接受必要处置。',
                   1,
                   2000
               ) as PATIENT_VIEW,-- 患者/法定代理人意见

               substr(
                   nvl(nullif(trim(cast(tr.hzxm as varchar2(50))), ''), nvl(cast(pmi.name as varchar2(50)), '-')),
                   1,
                   50
               ) as STATUTORY_AGENT_VIEW,-- 患者/法定代理人签名 是

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
                   case
                       when tr.sqsj is not null
                        and regexp_like(trim(cast(tr.sqsj as varchar2(30))), '^[0-9]{4}-[0-9]{2}-[0-9]{2}')
                       then to_date(substr(trim(cast(tr.sqsj as varchar2(30))), 1, 19), 'yyyy-mm-dd hh24:mi:ss')

                       when tr.sqsj is not null
                        and regexp_like(trim(cast(tr.sqsj as varchar2(30))), '^[0-9]{14}$')
                       then to_date(trim(cast(tr.sqsj as varchar2(30))), 'yyyymmddhh24miss')

                       else p.admission_date_time
                   end
                   as date
               ) as PATIENT_SIGN_DATE,-- 患者/法定代理人签名日期 是

               substr(
                   nvl(
                       nullif(trim(substr(cast(tr.sqys as varchar2(100)), instr(cast(tr.sqys as varchar2(100)), '|', 1, 1) + 1)), ''),
                       nvl(cast(tr.sqys as varchar2(50)), '-')
                   ),
                   1,
                   50
               ) as OPERATOR,-- 医生签名 是

               cast(
                   case
                       when tr.sqsj is not null
                        and regexp_like(trim(cast(tr.sqsj as varchar2(30))), '^[0-9]{4}-[0-9]{2}-[0-9]{2}')
                       then to_date(substr(trim(cast(tr.sqsj as varchar2(30))), 1, 19), 'yyyy-mm-dd hh24:mi:ss')

                       when tr.sqsj is not null
                        and regexp_like(trim(cast(tr.sqsj as varchar2(30))), '^[0-9]{14}$')
                       then to_date(trim(cast(tr.sqsj as varchar2(30))), 'yyyymmddhh24miss')

                       else p.admission_date_time
                   end
                   as date
               ) as DOC_DATE-- 医生签名日期时间 是
          from sx.b_t_reqd tr

      inner join (
    select *
    from (
        select s2.*,
               row_number() over (
                   partition by s2.xyhzsqdh, s2.xymc
                   order by s2.pk_no
               ) as rn_same_blood
          from sx.b_t_xyxxb s2
         where s2.xyzt = '3'
    )
    where rn_same_blood = 1
) s2
        on tr.sqlsh = s2.xyhzsqdh

          left join sx.b_t_reactions r
                 on tr.sqlsh = r.sqlsh
                and s2.pk_no = r.pk_no

          left join his.pat_visit p
                 on tr.hzbs = p.patient_id
                and tr.zycs = p.visit_id

          left join his.pat_master_index pmi
                 on p.patient_id = pmi.patient_id

          left join (
                select a.patient_id,
                       a.visit_id,
                       a.diagnosis_code,
                       a.diagnosis_desc,
                       row_number() over (
                           partition by a.patient_id, a.visit_id
                           order by
                               case
                                   when a.diagnosis_type = '3' then 1
                                   else 2
                               end,
                               a.diagnosis_no
                       ) as rn
                  from his.diagnosis a
                 where a.diagnosis_type = '3'
          ) dd
                 on dd.rn = 1
                and p.patient_id = dd.patient_id
                and p.visit_id = dd.visit_id

         where tr.shzt = '1'
    ) q
)
where rn = 1 and DEP_NAME is not null and DISEASE_NAME is not null
