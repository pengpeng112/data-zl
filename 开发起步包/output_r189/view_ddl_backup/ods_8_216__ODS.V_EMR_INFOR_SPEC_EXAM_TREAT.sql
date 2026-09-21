
  CREATE OR REPLACE FORCE VIEW "ODS"."V_EMR_INFOR_SPEC_EXAM_TREAT" ("ID", "ORG_CODE", "ORG_NAME", "DISTRICT_CODE", "EXCHANGE_TYPE", "SYSTEM_TIME", "PATIENT_TYPE", "VISTING_NUM", "INFORMED_CONSENT_CODE", "INFORMED_CONSENT_NAME", "DEPT_CODE", "DEP_NAME", "AREA_NAME", "WARD_NUM", "SICKBED_NUM", "PATIENT_NAME", "SEX_CODE", "SEX_NAME", "AGE", "AGE_MONTH", "DISEASE_CODE", "DISEASE_NAME", "SPEC_EXAM_TREAT_NAME", "SPEC_EXAM_TREAT_PURPOSE", "SPEC_EXAM_TREAT_RISK", "REPLACE_PLAN", "STATUTORY_AGENT_VIEW", "SAP_RELATIONSHIP", "SAP_RELATIONSHIP_NAME", "PATIENT_SIGN_DATE", "OPERATOR", "DOC_DATE") AS 
  select ID,
       ORG_CODE,
       ORG_NAME,
       DISTRICT_CODE,
       EXCHANGE_TYPE,
       SYSTEM_TIME,
       PATIENT_TYPE,
       VISTING_NUM,
       INFORMED_CONSENT_CODE,
       INFORMED_CONSENT_NAME,
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
       DISEASE_CODE,
       DISEASE_NAME,
       SPEC_EXAM_TREAT_NAME,
       SPEC_EXAM_TREAT_PURPOSE,
       SPEC_EXAM_TREAT_RISK,
       REPLACE_PLAN,
       STATUTORY_AGENT_VIEW,
       SAP_RELATIONSHIP,
       SAP_RELATIONSHIP_NAME,
       PATIENT_SIGN_DATE,
       OPERATOR,
       DOC_DATE
from (
    select q.*,
           row_number() over (
               partition by q.ID
               order by q.DOC_DATE desc nulls last,
                        q.PATIENT_SIGN_DATE desc nulls last
           ) as rn
    from (
        select substr(
                   '49557032X'||'|'||
                   nvl(to_char(pv.patient_id), '-')||'|'||
                   nvl(to_char(pv.visit_id), '-')||'|'||
                   nvl(to_char(t1.id), '-'),
                   1,
                   100
               ) as ID,-- 内码 是 主键

               '49557032X' as ORG_CODE,-- 医院组织机构代码 是

               '山东省第二人民医院' as ORG_NAME,-- 医院名称 是

               '370104' as DISTRICT_CODE,-- 所属行政区划 是

               'ADDHIS' as EXCHANGE_TYPE,-- 交换类型 是

               cast(systimestamp as timestamp) as SYSTEM_TIME,-- 数据上传时间戳

               '2' as PATIENT_TYPE,-- 病人类型 是 1门诊 2住院

               substr(
                   nvl(to_char(pv.patient_id), '-')||'|'||nvl(to_char(pv.visit_id), '-'),
                   1,
                   50
               ) as VISTING_NUM,-- 就诊号 是

               substr(
                   nvl(to_char(t1.doc_type_id), '-')||'-'||nvl(to_char(t1.id), '-'),
                   1,
                   20
               ) as INFORMED_CONSENT_CODE,-- 知情同意书编号

               '特殊检查及特殊治疗同意书' as INFORMED_CONSENT_NAME,-- 知情同意书名称

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
                   nvl(nullif(trim(cast(pmi.name as varchar2(50))), ''), nvl(cast(t.p_name as varchar2(50)), '-')),
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

               substr(
                   case
                       when pmi.date_of_birth is not null
                        and pv.admission_date_time is not null
                        and months_between(pv.admission_date_time, pmi.date_of_birth) < 12
                       then to_char(
                                least(
                                    greatest(
                                        trunc(months_between(pv.admission_date_time, pmi.date_of_birth)),
                                        0
                                    ),
                                    11
                                )
                            )
                       else null
                   end,
                   1,
                   2
               ) as AGE_MONTH,-- 年龄(月)

             cast(
    substrb(
        nvl(
            nullif(
                trim(
                    (select max(substrb(to_char(cd.国标编码), 1, 12))
                       from cda.cda_dictionary cd
                      where cd.字典名称 = 'ICD-10诊断编码'
                        and cd.系统标识 = 'HIS'
                        and cd.院标名称 = dd.diagnosis_desc)
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
                        and cd.院标名称 = dd.diagnosis_desc)
                ),
                ''
            ),
            nvl(substrb(to_char(dd.diagnosis_desc), 1, 50), '-')
        ),
        1,
        50
    ) as varchar2(50)
) as DISEASE_NAME, -- 疾病诊断名称 是

               substr(
                   case
                       when t1.doc_title = '消化内镜知情同意书-新标' then '消化内镜'
                       when t1.doc_title = '电子纤维支气管镜检查知情同意书-新标' then '电子纤维支气管镜'
                       when t1.doc_title = '术中冰冻切片检查知情同意书-新标' then '术中冰冻切片检查'
                       when t1.doc_title = '骨髓穿刺/活检术知情同意书-新标' then '骨髓穿刺/活检术'
                       when t1.doc_title = '膀胱尿道内窥镜检查治疗知情同意书-新标' then '膀胱尿道内窥镜检查'
                       else nvl(cast(t1.doc_title as varchar2(1000)), '-')
                   end,
                   1,
                   1000
               ) as SPEC_EXAM_TREAT_NAME,-- 特殊检查及特殊治疗项目名称 是

               substr(
                   case
                       when t1.doc_title = '消化内镜知情同意书-新标' then '切除食管、胃、肠黏膜病变，明确病理；切除息肉，明确病理；碎石；其他。'
                       when t1.doc_title = '电子纤维支气管镜检查知情同意书-新标' then '明确诊断、观察病变、取材活检或根据病情进行相关内镜下诊疗。'
                       when t1.doc_title = '术中冰冻切片检查知情同意书-新标' then '快速病理检查，为临床医师术中判断及手术方案提供参考意见。'
                       when t1.doc_title = '骨髓穿刺/活检术知情同意书-新标' then '了解骨髓造血及相关病变情况，协助明确诊断、疗效判断及后续治疗。'
                       when t1.doc_title = '膀胱尿道内窥镜检查治疗知情同意书-新标' then '了解膀胱、尿道及相关泌尿系统病变情况，必要时进行内镜下检查或治疗。'
                       else '详见病历'
                   end,
                   1,
                   1000
               ) as SPEC_EXAM_TREAT_PURPOSE,-- 特殊检查及特殊治疗目的 是

               cast(
    substrb(
        case
            when t1.doc_title = '消化内镜知情同意书-新标' then
                 '可能发生麻醉意外、呼吸心跳骤停、心脑血管意外、肠梗阻、消化道出血、穿孔、感染、腹膜炎、气胸、纵隔脓肿、脓胸、术后疼痛发热、病变复发、操作中止、术后狭窄、需再次治疗及其他难以预料的风险。'
            when t1.doc_title = '电子纤维支气管镜检查知情同意书-新标' then
                 '可能发生麻醉反应、药物过敏、休克、心脏呼吸骤停、术中术后出血、感染、气胸、纵隔气肿、心脑血管意外、喉头水肿、支气管痉挛、低氧血症、窒息、误吸、鼻出血、黏膜损伤、牙齿损伤、声音嘶哑、声带损伤、肺栓塞、活检后出血及其他难以预料的并发症。'
            when t1.doc_title = '术中冰冻切片检查知情同意书-新标' then
                 '冰冻切片诊断具有局限性，仅为术中参考意见；部分病变难以鉴别良恶性，可能需等待常规石蜡切片诊断；冰冻报告不能作为最终病理诊断，最终诊断以石蜡切片为准，手术方案可能因此调整。'
            when t1.doc_title = '骨髓穿刺/活检术知情同意书-新标' then
                 '可能发生局麻药过敏、药物毒性反应、穿刺部位感染、败血症、出血、血肿、心脑血管意外、心律失常、心跳呼吸骤停、穿刺失败、神经血管损伤、穿刺针折断、检查后仍不能明确诊断及其他不可预见风险。'
            when t1.doc_title = '膀胱尿道内窥镜检查治疗知情同意书-新标' then
                 '可能发生麻醉反应、药物过敏、休克、心脑血管意外、感染、尿道膀胱输尿管或肾脏损伤、血尿、疼痛、出血、菌血症、检查失败及其他并发症；高龄或合并基础疾病者风险可能增加。'
            else '详见病历'
        end,
        1,
        1000
    ) as varchar2(1000)
) as SPEC_EXAM_TREAT_RISK,  -- 特殊检查及特殊治疗风险 是

               substr(
                   case
                       when t1.doc_title = '电子纤维支气管镜检查知情同意书-新标' then '经皮肺穿刺；开胸肺活检；或根据病情选择其他替代检查治疗方案。'
                       else '详见病历'
                   end,
                   1,
                   1000
               ) as REPLACE_PLAN,-- 替代方案

               substr(
                   nvl(nullif(trim(cast(t.p_name as varchar2(50))), ''), nvl(cast(pmi.name as varchar2(50)), '-')),
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
                       when t1.doc_finish_date is not null
                        and t1.doc_finish_date >= date '1900-01-01'
                       then t1.doc_finish_date

                       when t1.doc_sign_date is not null
                        and t1.doc_sign_date >= date '1900-01-01'
                       then t1.doc_sign_date

                       when t1.modifiedon is not null
                        and t1.modifiedon >= date '1900-01-01'
                       then t1.modifiedon

                       when t1.doc_title_time is not null
                        and t1.doc_title_time >= date '1900-01-01'
                       then t1.doc_title_time

                       else pv.admission_date_time
                   end
                   as date
               ) as PATIENT_SIGN_DATE,-- 患者/法定代理人签名日期 是

               substr(
                 nvl(  nvl(nullif(trim(cast(t1.MODIFIEDBY as varchar2(50))), ''), t1.CREATEBY),'-'） ,
                   1,
                   50
               ) as OPERATOR,-- 医生签名 是

               cast(
                   case
                       when t1.doc_sign_date is not null
                        and t1.doc_sign_date >= date '1900-01-01'
                       then t1.doc_sign_date

                       when t1.doc_finish_date is not null
                        and t1.doc_finish_date >= date '1900-01-01'
                       then t1.doc_finish_date

                       when t1.modifiedon is not null
                        and t1.modifiedon >= date '1900-01-01'
                       then t1.modifiedon

                       when t1.doc_title_time is not null
                        and t1.doc_title_time >= date '1900-01-01'
                       then t1.doc_title_time

                       else pv.admission_date_time
                   end
                   as date
               ) as DOC_DATE-- 医生签名日期时间 是
           from mtl.epr_inpatient_docindex t

          inner join mtl.epr_inpatient t1
                  on t.uhid = t1.uhid
                 and t1.doc_title in (
                       '消化内镜知情同意书-新标',
                       '电子纤维支气管镜检查知情同意书-新标',
                       '术中冰冻切片检查知情同意书-新标',
                       '骨髓穿刺/活检术知情同意书-新标',
                       '膀胱尿道内窥镜检查治疗知情同意书-新标'
                 )

          left join his.pat_master_index pmi
                 on pmi.inp_no = t.p_inpatient_no

          inner join his.pat_visit pv
                  on pv.patient_id = pmi.patient_id
                 and pv.visit_id = t.p_inpatient_times

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
                                   when a.diagnosis_type = '2' then 2
                                   when a.diagnosis_type = '1' then 3
                                   else 4
                               end,
                               a.diagnosis_no
                       ) as rn
                  from his.diagnosis a
          ) dd
                 on dd.rn = 1
                and pv.patient_id = dd.patient_id
                and pv.visit_id = dd.visit_id
    ) q
)
where rn = 1
