** This session may be vulnerable to "store now, decrypt later" attacks.


  CREATE OR REPLACE FORCE VIEW "ODS"."V_EMR_AFTER_OPERA_RECORD" ("ID", "ORG_CODE", "ORG_NAME", "PATIENT_TYPE", "VISTING_NUM", "APPLY_NUM", "DEPT_NAME", "DEPT_CODE", "WARD_NAME", "EORD_NUM", "SICKBED_NUM", "NAME", "SEX_CODE", "SEX_NAME", "WEIGHT", "AGE", "AFTER_OPERA_DIAGNOSIS", "AFTER_DISEASE", "GENERAL_EXAM_RESULT", "OPERATION_CODE", "OPERATION_NAME", "ANES_METHOD_CODE", "ANAESTHESIA_NAME", "ANES_AFTER_NOTE", "AWAKE_DATE", "OPERA_WINDPIPE", "ATTENTION_MATTER", "ANANSTHESIA", "DOCTOR_ADVICE", "SIGNATURE_DATE", "DOCTOR_NAME", "DISTRICT_CODE", "EXCHANGE_TYPE", "SYSTEM_TIME", "OPERA_CODE", "OPERA_NAME", "DATETIME") AS 
  SELECT
    -- ===== 规范 34 列 =====
    ID, ORG_CODE, ORG_NAME, PATIENT_TYPE, VISTING_NUM, APPLY_NUM,
    DEPT_NAME, DEPT_CODE, WARD_NAME, EORD_NUM, SICKBED_NUM,
    NVL(NAME, '-')            AS NAME,             -- 必填兜底（pmi 关联可漏）
    SEX_CODE, SEX_NAME, WEIGHT, AGE,
    AFTER_OPERA_DIAGNOSIS,
    NVL(AFTER_DISEASE, '-')   AS AFTER_DISEASE,    -- 必填兜底（诊断链末端可空）
    GENERAL_EXAM_RESULT, OPERATION_CODE, OPERATION_NAME,
    ANES_METHOD_CODE, ANAESTHESIA_NAME, ANES_AFTER_NOTE, AWAKE_DATE,
    OPERA_WINDPIPE, ATTENTION_MATTER, ANANSTHESIA, DOCTOR_ADVICE,
    SIGNATURE_DATE, DOCTOR_NAME, DISTRICT_CODE, EXCHANGE_TYPE, SYSTEM_TIME,
    -- ===== 旧列名兼容双输出（与规范列同值） =====
    OPERATION_CODE            AS OPERA_CODE,
    OPERATION_NAME            AS OPERA_NAME,DATETIME
FROM (
select substr(
         '49557032X'
         || '|' || a.patient_id
         || '|' || a.visit_id
         || '|' || a.oper_id    || '|' ||o.operation_no,
         1,
         100
       ) as ID,-- 内码 是 唯一主键

       '49557032X' as ORG_CODE,-- 组织机构代码 是 医疗机构组织机构代码

       '山东省第二人民医院' as ORG_NAME,-- 组织机构名称 是 医疗机构组织机构名称

       '2' as PATIENT_TYPE,-- 病人类型 是 1:门急诊 2:住院

       substr(a.patient_id || '|' || a.visit_id,1,100) as VISTING_NUM,-- 就诊唯一标识号 是

       a.patient_id || a.visit_id || a.oper_id as APPLY_NUM,-- 电子申请单编号 是 手术申请单编号

      nvl( substr((select max(qmpt_name)
                 from his.dept_dict
                where dept_code = p.dept_admission_to),1,70),'-') as DEPT_NAME,-- 科室名称 是

       nvl( substr((select max(qmpt_code)
                 from his.dept_dict
                where dept_code = p.dept_admission_to),1,32),'-')  as DEPT_CODE,-- 科室代码

       substr((select max(dept_name)
                 from his.dept_dict
                where dept_code = p.discharge_ward_code),1,70) as WARD_NAME,-- 病区名称

       cast(null as varchar2(20)) as EORD_NUM,-- 病房号

       substr(p.discharge_bed_no,1,20) as SICKBED_NUM,-- 病床号

       substr(pmi.name,1,50) as NAME,-- 患者姓名 是

       decode(pmi.sex,'男','1','女','2','未知','0','9') as SEX_CODE,-- 性别代码 是

       decode(pmi.sex,'男','男','女','女','未知','未知','不明') as SEX_NAME,-- 性别 是

       nvl(e3.weight,0) as WEIGHT,-- 体重 kg 是

       case
         when pmi.date_of_birth is not null
          and p.admission_date_time is not null
         then greatest(trunc(months_between(p.admission_date_time, pmi.date_of_birth) / 12), 0)
         else null
       end as AGE,-- 年龄

      nvl( nvl(   (select max(cd.国标编码)
            from cda.cda_dictionary cd
           where cd.字典名称 = 'ICD-10诊断编码'
             and cd.系统标识 = 'SM'
             and cd.院标名称 = a.DIAG_AFTER_OPERATION)    ,
              (select max(cd.国标编码)
            from cda.cda_dictionary cd
           where cd.字典名称 = 'ICD-10诊断编码'
             and cd.系统标识 = 'HIS'
             and cd.院标名称 = dd.diagnosis_desc)
       ),         dd.diagnosis_code) as AFTER_OPERA_DIAGNOSIS,-- 术后诊断编码
     nvl( nvl(   (select max(cd.国标名称)
            from cda.cda_dictionary cd
           where cd.字典名称 = 'ICD-10诊断编码'
             and cd.系统标识 = 'SM'
             and cd.院标名称 = a.DIAG_AFTER_OPERATION)    ,
              (select max(cd.国标名称)
            from cda.cda_dictionary cd
           where cd.字典名称 = 'ICD-10诊断编码'
             and cd.系统标识 = 'HIS'
             and cd.院标名称 = dd.diagnosis_desc)
       ),        dd.diagnosis_desc)

      as AFTER_DISEASE,-- 术后疾病诊断名称 是

      substr(
  nvl(
    nullif(
      (case when postv.t is not null then 'T:' || postv.t || '；' end) ||
      (case when postv.p is not null then 'P:' || postv.p || '；' end) ||
      (case when postv.r is not null then 'R:' || postv.r || '；' end) ||
      (case when postv.bph is not null or postv.bpl is not null
            then 'BP:' || nvl(postv.bph,'') || '/' || nvl(postv.bpl,'') || '；' end) ||
      (case when nvl(postv.conscious2, postv.conscious1) is not null
            then '意识清醒:' || nvl(postv.conscious2, postv.conscious1) || '；' end) ||
      (case when nvl(postv.circulation2, postv.circulation1) is not null
            then '循环稳定:' || nvl(postv.circulation2, postv.circulation1) || '；' end) ||
      (case when nvl(postv.mental2, postv.mental1) is not null
            then '精神行为:' || nvl(postv.mental2, postv.mental1) || '；' end) ||
      (case when nvl(postv.sensation2, postv.sensation1) is not null
            then '感觉恢复:' || nvl(postv.sensation2, postv.sensation1) || '；' end) ||
      (case when nvl(postv.muscle2, postv.muscle1) is not null
            then '肌力恢复:' || nvl(postv.muscle2, postv.muscle1) || '；' end),
      ''
    ),
    '-'
  ),
  1,
  1000
)    as GENERAL_EXAM_RESULT,-- 一般情况 是

        substr(
                   nvl(
                       nvl(
                           nvl(     (select cast(cd.国标编码 as varchar2(12))
                              from cda.cda_dictionary cd
                             where cast(cd.字典名称 as varchar2(100)) = 'ICD-9手术编码'
                               and cast(cd.系统标识 as varchar2(20)) = 'SM'
                               and cast(cd.院标名称 as varchar2(200)) = cast(a.operation_name as varchar2(200))
                               and rownum = 1)   ,
                               (select cast(cd.国标编码 as varchar2(12))
                                  from cda.cda_dictionary cd
                                 where cast(cd.字典名称 as varchar2(100)) = 'ICD-9手术编码'
                                   and cast(cd.系统标识 as varchar2(20)) = 'HIS'
                 and (cd.院标编码 =         regexp_replace(trim(cast(o.operation_code as varchar2(100))), '[A-Z][0-9]*$', '') or cd.院标编码 = o.operation_code )
                                   and rownum = 1)
                           ),


                               (select cast(cd.国标编码 as varchar2(12))
                                  from cda.cda_dictionary cd
                                 where cast(cd.字典名称 as varchar2(100)) = 'ICD-9手术编码'
                                   and cast(cd.系统标识 as varchar2(20)) = 'HIS'
                                   and cast(cd.院标名称 as varchar2(200)) = cast(o.operation_desc as varchar2(200))
                                   and rownum = 1)



                       ),
                       cast(o.operation_code as varchar2(12))
                   ),
                   1,
                   12
               ) as OPERATION_CODE,-- 手术及操作编码

              nvl(a.OPERATION_NAME , substr(
                   nvl(
                       nvl(
                           nvl((select cast(cd.国标名称 as varchar2(80))
                              from cda.cda_dictionary cd
                             where cast(cd.字典名称 as varchar2(100)) = 'ICD-9手术编码'
                               and cast(cd.系统标识 as varchar2(20)) = 'SM'
                               and cast(cd.院标名称 as varchar2(200)) = cast(a.operation_name as varchar2(200))
                               and rownum = 1)  ,
                               (select cast(cd.国标名称 as varchar2(80))
                                  from cda.cda_dictionary cd
                                 where cast(cd.字典名称 as varchar2(100)) = 'ICD-9手术编码'
                                   and cast(cd.系统标识 as varchar2(20)) = 'HIS'
                 and (cd.院标编码 =         regexp_replace(trim(cast(o.operation_code as varchar2(100))), '[A-Z][0-9]*$', '') or cd.院标编码 = o.operation_code )
                                   and rownum = 1)
                           ),

                               (select cast(cd.国标名称 as varchar2(80))
                                  from cda.cda_dictionary cd
                                 where cast(cd.字典名称 as varchar2(100)) = 'ICD-9手术编码'
                                   and cast(cd.系统标识 as varchar2(20)) = 'HIS'
                                   and cast(cd.院标名称 as varchar2(200)) = cast(o.operation_desc as varchar2(200))
                                   and rownum = 1)
                       ),
                       nvl(cast(o.operation_desc as varchar2(80)), nvl(cast(a.operation_name as varchar2(80)), '-'))
                   ),
                   1,
                   80
               ) ) as OPERATION_name,-- 手术名称

       case
         when a.anesthesia_method is null
           or trim(a.anesthesia_method) in ('', '/', '\', '-', '无') then '9'

         when a.anesthesia_method like '%控制性降压%' then '45'
         when a.anesthesia_method like '%全身降温%'
           or a.anesthesia_method like '%低温麻醉%' then '44'
         when a.anesthesia_method like '%静吸复合%' then '41'
         when a.anesthesia_method like '%针刺%'
           or a.anesthesia_method like '%针药%' then '42'

         when regexp_like(a.anesthesia_method, '全麻|全身麻醉|气管插管全麻|气管插管全身麻醉|非插管全麻|无插管全麻')
          and regexp_like(a.anesthesia_method, '臂丛|颈丛|神经阻滞|区域神经阻滞|椎管|腰硬|腰-硬|硬膜外|局麻|局部|基础麻醉')
         then '4'

         when a.anesthesia_method like '%吸入麻醉%' then '11'
         when a.anesthesia_method like '%静脉麻醉%'
           or a.anesthesia_method like '%静脉全麻%'
           or a.anesthesia_method like '%全凭静脉%'
           or a.anesthesia_method like '%全静脉%'
           or a.anesthesia_method like '%全屏静脉%'
           or trim(a.anesthesia_method) = '静脉' then '12'
         when a.anesthesia_method like '%基础麻醉%'
           or trim(a.anesthesia_method) in ('基础','基础麻醉','基础+强化','基础加强化') then '13'

         when a.anesthesia_method like '%蛛网膜下%'
           or a.anesthesia_method like '%腰麻%'
           or a.anesthesia_method like '%单次腰麻%' then '21'
         when a.anesthesia_method like '%硬膜外%'
           or a.anesthesia_method like '%硬膜外腔%'
           or a.anesthesia_method like '%硬脊膜外%'
           or a.anesthesia_method like '%连续硬膜外%' then '22'
         when a.anesthesia_method like '%椎管内%'
           or a.anesthesia_method like '%椎管麻醉%'
           or a.anesthesia_method like '%腰硬联合%'
           or a.anesthesia_method like '%腰-硬联合%'
           or a.anesthesia_method like '%硬要联合%' then '2'

         when a.anesthesia_method like '%星状神经节%' then '32'
         when a.anesthesia_method like '%臂丛%'
           or a.anesthesia_method like '%颈丛%'
           or a.anesthesia_method like '%腰骶神经丛%'
           or a.anesthesia_method like '%神经丛%' then '31'
         when a.anesthesia_method like '%坐骨神经%'
           or a.anesthesia_method like '%股神经%'
           or a.anesthesia_method like '%尺神经%'
           or a.anesthesia_method like '%肋间神经%'
           or a.anesthesia_method like '%腘窝%'
           or a.anesthesia_method like '%隐神经%'
           or a.anesthesia_method like '%收肌管%'
           or a.anesthesia_method like '%髂筋膜%'
           or a.anesthesia_method like '%神经阻滞%' then '33'
         when a.anesthesia_method like '%区域神经阻滞%'
           or a.anesthesia_method like '%区域阻滞%'
           or a.anesthesia_method like '%域神经阻滞%' then '34'

         when a.anesthesia_method like '%局部浸润%' then '35'
         when a.anesthesia_method like '%表面麻醉%'
           or a.anesthesia_method like '%表面粘膜麻醉%' then '36'
         when a.anesthesia_method like '%局麻%'
           or a.anesthesia_method like '%局部麻醉%'
           or a.anesthesia_method like '%局部%' then '3'

         when a.anesthesia_method like '%全身麻醉%'
           or a.anesthesia_method like '%全麻%'
           or trim(a.anesthesia_method) = '全' then '1'
         when a.anesthesia_method like '%复合麻醉%' then '4'
         else '9'
       end as ANES_METHOD_CODE,-- 麻醉方法代码 是

       case
         when a.anesthesia_method is null
           or trim(a.anesthesia_method) in ('', '/', '\', '-', '无') then '其他麻醉方法'

         when a.anesthesia_method like '%控制性降压%' then '全麻复合控制性降压'
         when a.anesthesia_method like '%全身降温%'
           or a.anesthesia_method like '%低温麻醉%' then '全麻复合全身降温'
         when a.anesthesia_method like '%静吸复合%' then '静吸复合全麻'
         when a.anesthesia_method like '%针刺%'
           or a.anesthesia_method like '%针药%' then '针药复合麻醉'

         when regexp_like(a.anesthesia_method, '全麻|全身麻醉|气管插管全麻|气管插管全身麻醉|非插管全麻|无插管全麻')
          and regexp_like(a.anesthesia_method, '臂丛|颈丛|神经阻滞|区域神经阻滞|椎管|腰硬|腰-硬|硬膜外|局麻|局部|基础麻醉')
         then '复合麻醉'

         when a.anesthesia_method like '%吸入麻醉%' then '吸入麻醉'
         when a.anesthesia_method like '%静脉麻醉%'
           or a.anesthesia_method like '%静脉全麻%'
           or a.anesthesia_method like '%全凭静脉%'
           or a.anesthesia_method like '%全静脉%'
           or a.anesthesia_method like '%全屏静脉%'
           or trim(a.anesthesia_method) = '静脉' then '静脉麻醉'
         when a.anesthesia_method like '%基础麻醉%'
           or trim(a.anesthesia_method) in ('基础','基础麻醉','基础+强化','基础加强化') then '基础麻醉'

         when a.anesthesia_method like '%蛛网膜下%'
           or a.anesthesia_method like '%腰麻%'
           or a.anesthesia_method like '%单次腰麻%' then '蛛网膜下腔阻滞麻醉'
         when a.anesthesia_method like '%硬膜外%'
           or a.anesthesia_method like '%硬膜外腔%'
           or a.anesthesia_method like '%硬脊膜外%'
           or a.anesthesia_method like '%连续硬膜外%' then '硬脊膜外腔阻滞麻醉'
         when a.anesthesia_method like '%椎管内%'
           or a.anesthesia_method like '%椎管麻醉%'
           or a.anesthesia_method like '%腰硬联合%'
           or a.anesthesia_method like '%腰-硬联合%'
           or a.anesthesia_method like '%硬要联合%' then '椎管内麻醉'

         when a.anesthesia_method like '%星状神经节%' then '神经节阻滞麻醉'
         when a.anesthesia_method like '%臂丛%'
           or a.anesthesia_method like '%颈丛%'
           or a.anesthesia_method like '%腰骶神经丛%'
           or a.anesthesia_method like '%神经丛%' then '神经丛阻滞麻醉'
         when a.anesthesia_method like '%坐骨神经%'
           or a.anesthesia_method like '%股神经%'
           or a.anesthesia_method like '%尺神经%'
           or a.anesthesia_method like '%肋间神经%'
           or a.anesthesia_method like '%腘窝%'
           or a.anesthesia_method like '%隐神经%'
           or a.anesthesia_method like '%收肌管%'
           or a.anesthesia_method like '%髂筋膜%'
           or a.anesthesia_method like '%神经阻滞%' then '神经阻滞麻醉'
         when a.anesthesia_method like '%区域神经阻滞%'
           or a.anesthesia_method like '%区域阻滞%'
           or a.anesthesia_method like '%域神经阻滞%' then '区域阻滞麻醉'

         when a.anesthesia_method like '%局部浸润%' then '局部浸润麻醉'
         when a.anesthesia_method like '%表面麻醉%'
           or a.anesthesia_method like '%表面粘膜麻醉%' then '表面麻醉'
         when a.anesthesia_method like '%局麻%'
           or a.anesthesia_method like '%局部麻醉%'
           or a.anesthesia_method like '%局部%' then '局部麻醉'

         when a.anesthesia_method like '%全身麻醉%'
           or a.anesthesia_method like '%全麻%'
           or trim(a.anesthesia_method) = '全' then '全身麻醉'
         when a.anesthesia_method like '%复合麻醉%' then '复合麻醉'
         else '其他麻醉方法'
       end as ANAESTHESIA_NAME,-- 麻醉方法 是

       substr(
  nvl(
    nullif(
      (case when postv.anes_effect is not null
            then '麻醉效果:' || postv.anes_effect || '；' end) ||
      (case when postv.anes_effect_reason is not null
            then '原因:' || postv.anes_effect_reason || '；' end) ||
      (case when nvl(postv.conscious2, postv.conscious1) is not null
            then '意识清醒:' || nvl(postv.conscious2, postv.conscious1) || '；' end) ||
      (case when nvl(postv.circulation2, postv.circulation1) is not null
            then '循环稳定:' || nvl(postv.circulation2, postv.circulation1) || '；' end) ||
      (case when nvl(postv.resp_depress2, postv.resp_depress1) is not null
            then '呼吸抑制:' || nvl(postv.resp_depress2, postv.resp_depress1) || '；' end) ||
      (case when nvl(postv.sensation2, postv.sensation1) is not null
            then '感觉恢复:' || nvl(postv.sensation2, postv.sensation1) || '；' end) ||
      (case when nvl(postv.muscle2, postv.muscle1) is not null
            then '肌力恢复:' || nvl(postv.muscle2, postv.muscle1) || '；' end) ||
      (case when nvl(postv.pain_score_num, postv.pain_score) is not null
            then '疼痛评分:' || nvl(postv.pain_score_num, postv.pain_score) || '；' end) ||
      (case when nvl(postv.analgesia_mode2, postv.analgesia_mode1) is not null
            then '镇痛方式:' || nvl(postv.analgesia_mode2, postv.analgesia_mode1) || '；' end) ||
      (case when postv.analgesic_pump is not null
            then '使用镇痛泵:' || postv.analgesic_pump || '；' end),
      ''
    ),
    '好'
  ),
  1,
  1000
)     as ANES_AFTER_NOTE,-- 麻醉恢复情况 是

       cast(
  nvl(
    a.anes_end_time,
    nvl(a.end_date_time, nvl(a.done_date_time, a.start_date_time))
  ) as date
)   as AWAKE_DATE,-- 清醒日期时间 是

      case
  when nvl(postv.windpipe2, postv.windpipe1) is null then '0'
  when nvl(postv.windpipe2, postv.windpipe1) in ('否','0','未拔除','未') then '0'
  when nvl(postv.windpipe2, postv.windpipe1) like '%否%' then '0'
  when nvl(postv.windpipe2, postv.windpipe1) like '%未%' then '0'
  else '1'
end as OPERA_WINDPIPE,   -- 拔除气管插管标志

 substr(
  nvl(
    nullif(
      (case when nvl(postv.nausea2, postv.nausea1) is not null
             and nvl(postv.nausea2, postv.nausea1) not in ('否','无','0','正常','未见异常')
            then '恶心呕吐:' || nvl(postv.nausea2, postv.nausea1) || '；' end) ||
      (case when nvl(postv.throat_pain2, postv.throat_pain1) is not null
             and nvl(postv.throat_pain2, postv.throat_pain1) not in ('否','无','0','正常','未见异常')
            then '咽喉痛:' || nvl(postv.throat_pain2, postv.throat_pain1) || '；' end) ||
      (case when nvl(postv.hoarse2, postv.hoarse1) is not null
             and nvl(postv.hoarse2, postv.hoarse1) not in ('否','无','0','正常','未见异常')
            then '声音嘶哑:' || nvl(postv.hoarse2, postv.hoarse1) || '；' end) ||
      (case when nvl(postv.resp_depress2, postv.resp_depress1) is not null
             and nvl(postv.resp_depress2, postv.resp_depress1) not in ('否','无','0','正常','未见异常')
            then '呼吸抑制:' || nvl(postv.resp_depress2, postv.resp_depress1) || '；' end) ||
      (case when nvl(postv.reintubation2, postv.reintubation1) is not null
             and nvl(postv.reintubation2, postv.reintubation1) not in ('否','无','0','正常','未见异常')
            then '再插管:' || nvl(postv.reintubation2, postv.reintubation1) || '；' end) ||
      (case when nvl(postv.urinary2, postv.urinary1) is not null
             and nvl(postv.urinary2, postv.urinary1) not in ('否','无','0','正常','未见异常')
            then '尿潴留:' || nvl(postv.urinary2, postv.urinary1) || '；' end) ||
      (case when nvl(postv.itch2, postv.itch1) is not null
             and nvl(postv.itch2, postv.itch1) not in ('否','无','0','正常','未见异常')
            then '瘙痒:' || nvl(postv.itch2, postv.itch1) || '；' end) ||
      (case when nvl(postv.puncture_headache2, postv.puncture_headache1) is not null
             and nvl(postv.puncture_headache2, postv.puncture_headache1) not in ('否','无','0','正常','未见异常')
            then '穿刺点头疼:' || nvl(postv.puncture_headache2, postv.puncture_headache1) || '；' end) ||
      (case when nvl(postv.spinal_headache2, postv.spinal_headache1) is not null
             and nvl(postv.spinal_headache2, postv.spinal_headache1) not in ('否','无','0','正常','未见异常')
            then '腰麻后头疼:' || nvl(postv.spinal_headache2, postv.spinal_headache1) || '；' end) ||
      (case when nvl(postv.analgesia_bad2, postv.analgesia_bad1) is not null
             and nvl(postv.analgesia_bad2, postv.analgesia_bad1) not in ('否','无','0','正常','未见异常')
            then '镇痛不良反应:' || nvl(postv.analgesia_bad2, postv.analgesia_bad1) || '；' end) ||
      (case when postv.anes_effect_reason is not null
            then '麻醉效果原因:' || postv.anes_effect_reason || '；' end),
      ''
    ),
    '-'
  ),
  1,
  1000
) as ATTENTION_MATTER,-- 特殊情况

substr(
  nvl(
    nullif(
      (case when nvl(postv.resp_depress2, postv.resp_depress1) is not null
             and nvl(postv.resp_depress2, postv.resp_depress1) not in ('否','无','0','正常','未见异常')
            then '呼吸抑制:' || nvl(postv.resp_depress2, postv.resp_depress1) || '；' end) ||
      (case when nvl(postv.reintubation2, postv.reintubation1) is not null
             and nvl(postv.reintubation2, postv.reintubation1) not in ('否','无','0','正常','未见异常')
            then '再插管:' || nvl(postv.reintubation2, postv.reintubation1) || '；' end) ||
      (case when nvl(postv.nausea2, postv.nausea1) is not null
             and nvl(postv.nausea2, postv.nausea1) not in ('否','无','0','正常','未见异常')
            then '恶心呕吐:' || nvl(postv.nausea2, postv.nausea1) || '；' end) ||
      (case when nvl(postv.throat_pain2, postv.throat_pain1) is not null
             and nvl(postv.throat_pain2, postv.throat_pain1) not in ('否','无','0','正常','未见异常')
            then '咽喉痛:' || nvl(postv.throat_pain2, postv.throat_pain1) || '；' end) ||
      (case when nvl(postv.hoarse2, postv.hoarse1) is not null
             and nvl(postv.hoarse2, postv.hoarse1) not in ('否','无','0','正常','未见异常')
            then '声音嘶哑:' || nvl(postv.hoarse2, postv.hoarse1) || '；' end) ||
      (case when nvl(postv.spinal_headache2, postv.spinal_headache1) is not null
             and nvl(postv.spinal_headache2, postv.spinal_headache1) not in ('否','无','0','正常','未见异常')
            then '腰麻后头疼:' || nvl(postv.spinal_headache2, postv.spinal_headache1) || '；' end) ||
      (case when nvl(postv.puncture_headache2, postv.puncture_headache1) is not null
             and nvl(postv.puncture_headache2, postv.puncture_headache1) not in ('否','无','0','正常','未见异常')
            then '穿刺点头疼:' || nvl(postv.puncture_headache2, postv.puncture_headache1) || '；' end),
      ''
    ),
    '-'
  ),
  1,
  1000
) as ANANSTHESIA,-- 麻醉相关并发症
substr(
  nvl(
    nullif(
      (case when postv.deal1 is not null then '处理记录1:' || postv.deal1 || '；' end) ||
      (case when postv.deal2 is not null then '处理记录2:' || postv.deal2 || '；' end) ||
      (case when postv.deal3 is not null then '处理记录3:' || postv.deal3 || '；' end) ||
      (case when nvl(postv.analgesia_mode2, postv.analgesia_mode1) is not null
            then '镇痛方式:' || nvl(postv.analgesia_mode2, postv.analgesia_mode1) || '；' end) ||
      (case when postv.analgesic_pump is not null
            then '使用镇痛泵:' || postv.analgesic_pump || '；' end),
      ''
    ),
    '-'
  ),
  1,
  1000
) as DOCTOR_ADVICE,-- 医嘱或处理意见
   cast(
    nvl(a.done_date_time, nvl(a.end_date_time, nvl(a.anes_end_time, a.start_date_time)))
 as date
) as SIGNATURE_DATE ,-- 医生签名日期时间 是

       substr(
         nvl(
           case
             when regexp_like(a.anesthesia_doctor,'^[0-9]+$') then
               (select max(sd.name)
                  from his.staff_dict sd
                 where sd.emp_no = a.anesthesia_doctor)
             else a.anesthesia_doctor
           end,
           '-'
         ),
         1,
         50
       ) as DOCTOR_NAME,-- 医生签名 是

       '370104' as DISTRICT_CODE,-- 行政区划 是

       'ADDHIS' as EXCHANGE_TYPE,-- 交换类型 是

       cast(systimestamp as timestamp) as SYSTEM_TIME-- 数据上传时间 是
 ,discharge_date_time DATETIME
from sm.med_operation_master a

left join sm.med_operation_schedule a1
  on a.patient_id = a1.patient_id
 and a.visit_id   = a1.visit_id
 and a.oper_id    = a1.oper_id

left join sm.med_pat_master_index b
  on a.patient_id = b.patient_id

left join sm.med_anesthesia_plan e3
  on a.patient_id = e3.patient_id
 and a.visit_id   = e3.visit_id
 and a.oper_id    = e3.oper_id

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
from his.operation o  )  where rn=1)  o
               on a.patient_id = o.patient_id
              and a.visit_id = o.visit_id
            and to_char(o.operating_date,'yyyy-mm-dd')=to_char( nvl(a.start_date_time,a.SCHEDULED_DATE_TIME),'yyyy-mm-dd')

left join his.pat_visit p
  on a.patient_id = p.patient_id
 and a.visit_id   = p.visit_id

left join his.pat_master_index pmi
  on a.patient_id = pmi.patient_id

left join (
    select d.patient_id,
           d.visit_id,
           d.diagnosis_code,
           d.diagnosis_desc,
           row_number() over(
             partition by d.patient_id, d.visit_id
             order by d.diagnosis_no
           ) as rn
      from his.diagnosis d
     where d.diagnosis_type = '3'
) dd
  on dd.rn = 1
 and a.patient_id = dd.patient_id
 and a.visit_id   = dd.visit_id
left join (
    select sh.patient_id,
           sh.visit_id,
           sh.oper_id,

           max(case when sh.item_name = '麻醉术后访视.T' then sh.item_value end) as t,
           max(case when sh.item_name = '麻醉术后访视.P' then sh.item_value end) as p,
           max(case when sh.item_name = '麻醉术后访视.R' then sh.item_value end) as r,
           max(case when sh.item_name = '麻醉术后访视.BPH' then sh.item_value end) as bph,
           max(case when sh.item_name = '麻醉术后访视.BPL' then sh.item_value end) as bpl,

           max(case when sh.item_name = '麻醉术后访视.意识清醒1' then sh.item_value end) as conscious1,
           max(case when sh.item_name = '麻醉术后访视.意识清醒2' then sh.item_value end) as conscious2,

           max(case when sh.item_name = '麻醉术后访视.循环稳定1' then sh.item_value end) as circulation1,
           max(case when sh.item_name = '麻醉术后访视.循环稳定2' then sh.item_value end) as circulation2,

           max(case when sh.item_name = '麻醉术后访视.精神行为1' then sh.item_value end) as mental1,
           max(case when sh.item_name = '麻醉术后访视.精神行为2' then sh.item_value end) as mental2,

           max(case when sh.item_name = '麻醉术后访视.感觉恢复1' then sh.item_value end) as sensation1,
           max(case when sh.item_name = '麻醉术后访视.感觉恢复2' then sh.item_value end) as sensation2,

           max(case when sh.item_name = '麻醉术后访视.肌力恢复1' then sh.item_value end) as muscle1,
           max(case when sh.item_name = '麻醉术后访视.肌力恢复2' then sh.item_value end) as muscle2,

           max(case when sh.item_name = '麻醉术后访视.气管导管拔除1' then sh.item_value end) as windpipe1,
           max(case when sh.item_name = '麻醉术后访视.气管导管拔除2' then sh.item_value end) as windpipe2,

           max(case when sh.item_name = '麻醉术后访视.再插管1' then sh.item_value end) as reintubation1,
           max(case when sh.item_name = '麻醉术后访视.再插管2' then sh.item_value end) as reintubation2,

           max(case when sh.item_name = '麻醉术后访视.呼吸抑制1' then sh.item_value end) as resp_depress1,
           max(case when sh.item_name = '麻醉术后访视.呼吸抑制2' then sh.item_value end) as resp_depress2,

           max(case when sh.item_name = '麻醉术后访视.恶心呕吐1' then sh.item_value end) as nausea1,
           max(case when sh.item_name = '麻醉术后访视.恶心呕吐2' then sh.item_value end) as nausea2,

           max(case when sh.item_name = '麻醉术后访视.咽喉痛1' then sh.item_value end) as throat_pain1,
           max(case when sh.item_name = '麻醉术后访视.咽喉痛2' then sh.item_value end) as throat_pain2,

           max(case when sh.item_name = '麻醉术后访视.声音嘶哑1' then sh.item_value end) as hoarse1,
           max(case when sh.item_name = '麻醉术后访视.声音嘶哑2' then sh.item_value end) as hoarse2,

           max(case when sh.item_name = '麻醉术后访视.尿潴留1' then sh.item_value end) as urinary1,
           max(case when sh.item_name = '麻醉术后访视.尿潴留2' then sh.item_value end) as urinary2,

           max(case when sh.item_name = '麻醉术后访视.瘙痒1' then sh.item_value end) as itch1,
           max(case when sh.item_name = '麻醉术后访视.瘙痒2' then sh.item_value end) as itch2,

           max(case when sh.item_name = '麻醉术后访视.穿刺点头疼1' then sh.item_value end) as puncture_headache1,
           max(case when sh.item_name = '麻醉术后访视.穿刺点头疼2' then sh.item_value end) as puncture_headache2,

           max(case when sh.item_name = '麻醉术后访视.腰麻后头疼1' then sh.item_value end) as spinal_headache1,
           max(case when sh.item_name = '麻醉术后访视.腰麻后头疼2' then sh.item_value end) as spinal_headache2,

           max(case when sh.item_name = '麻醉术后访视.镇痛不良反应1' then sh.item_value end) as analgesia_bad1,
           max(case when sh.item_name = '麻醉术后访视.镇痛不良反应2' then sh.item_value end) as analgesia_bad2,

           max(case when sh.item_name = '麻醉术后访视.疼痛评分' then sh.item_value end) as pain_score,
           max(case when sh.item_name = '麻醉术后访视.疼痛评分分数' then sh.item_value end) as pain_score_num,

           max(case when sh.item_name = '麻醉术后访视.镇痛方式1' then sh.item_value end) as analgesia_mode1,
           max(case when sh.item_name = '麻醉术后访视.镇痛方式2' then sh.item_value end) as analgesia_mode2,
           max(case when sh.item_name = '麻醉术后访视.使用镇痛泵' then sh.item_value end) as analgesic_pump,

           max(case when sh.item_name = '麻醉术后访视.麻醉效果' then sh.item_value end) as anes_effect,
           max(case when sh.item_name = '麻醉术后访视.麻醉效果原因' then sh.item_value end) as anes_effect_reason,

           max(case when sh.item_name = '麻醉术后访视.处理记录1' then sh.item_value end) as deal1,
           max(case when sh.item_name = '麻醉术后访视.处理记录2' then sh.item_value end) as deal2,
           max(case when sh.item_name = '麻醉术后访视.处理记录3' then sh.item_value end) as deal3,

           max(case when sh.item_name = '麻醉术后访视.签署时间' then sh.item_value end) as sign_time

      from sm.med_custom_data sh
     where sh.item_name like '麻醉术后访视.%'
     group by sh.patient_id, sh.visit_id, sh.oper_id
) postv
  on postv.patient_id = a.patient_id
 and postv.visit_id   = a.visit_id
 and postv.oper_id    = a.oper_id
where nvl(to_char(a.oper_status),'0') <> '0'
  and a1.patient_id is not null and p.discharge_date_time >= to_date('2021-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss')
--  and p.discharge_date_time <  to_date('2026-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss')
  and  nvl(a.done_date_time, nvl(a.end_date_time, nvl(a.anes_end_time, a.start_date_time))) is not null
and      nvl( nvl(   (select max(cd.国标名称)
            from cda.cda_dictionary cd
           where cd.字典名称 = 'ICD-10诊断编码'
             and cd.系统标识 = 'SM'
             and cd.院标名称 = a.DIAG_AFTER_OPERATION)    ,
              (select max(cd.国标名称)
            from cda.cda_dictionary cd
           where cd.字典名称 = 'ICD-10诊断编码'
             and cd.系统标识 = 'HIS'
             and cd.院标名称 = dd.diagnosis_desc)
       ),        dd.diagnosis_desc) is not null
)

