
  CREATE OR REPLACE FORCE VIEW "ODS"."V_EMR_ANESTHESIA_RECORD" ("ID", "ORG_CODE", "ORG_NAME", "PATIENT_TYPE", "VISTING_NUM", "APPLY_NUM", "DEPT_CODE", "DEPT_NAME", "WARD_NAME", "EORD_NUM", "SICKBED_NUM", "OPERA_ROOM_NUM", "NAME", "SEX_CODE", "SEX_NAME", "AGE", "WEIGHT", "OPERA_CODE", "OPERA_NAME", "OPERA_POSITION_CODE", "OPERA_POSITION_NAME", "ANES_METHOD_CODE", "ANES_METHOD_NAME", "OPERA_WINDPIPE", "BREATH_TYPE", "BREATH_TYPE_NAME", "ANES_NOTE", "ANES_MERGE_CODE", "DIAGNOSIS_NOTE", "PIER_NOTE", "SHRINK_PRESSURE", "DIASTOLE_PRESSURE", "TEMPERATURE", "HEART_RATE", "PULSE_RATE", "RESPIRATORY_RATE", "SIGNATURE_EFFECT", "BEFORE_SIGNATURE_DRUG", "OPERA_START_DATE", "ANES_START_DATE", "ANES_END_DATE", "OPERA_END_DATE", "OUT_DEPT_DATE", "OPERAER_NAME", "PACU_FLAG", "PACU_IN_DATE", "PACU_OUT_DATE", "OPERA_TRANSFUSION", "OUT_BLOOD_ML", "PATIENT_TO", "ANES_DOC_NAME", "SIGNATURE_DATE", "DISTRICT_CODE", "EXCHANGE_TYPE", "SYSTEM_TIME") AS 
  select substr('49557032X'||'|'||b.patient_id||'|'||b.visit_id||'|'||b.oper_id,1,100) as ID,--  内码  是 唯一主键

       '49557032X' as ORG_CODE,--  组织机构代码  是 医疗机构组织机构代码

       '山东省第二人民医院' as ORG_NAME,--  组织机构名称  是 医疗机构组织机构名称

       '2' as PATIENT_TYPE,--  病人类型  是 1:门急诊 2：住院

       b.patient_id||'|'||b.visit_id as VISTING_NUM,-- 就诊唯一标识号 是 门诊或者住院唯一标识号


                   b.PATIENT_ID||b.VISIT_ID||b.OPER_ID                 as APPLY_NUM,-- 电子申请单编号 是 手术申请单编号

       substr(
         nvl(
           (select hd.qmpt_code
              from his.dept_dict hd
             where hd.dept_code = v.dept_admission_to
               and rownum = 1),
           v.dept_admission_to
         ),
         1,
         20
       ) as DEPT_CODE,-- 科室代码    按照平台值域填写

       substr(
         nvl(
           (select hd.qmpt_name
              from his.dept_dict hd
             where hd.dept_code = v.dept_admission_to
               and rownum = 1),
           (select hd.dept_name
              from his.dept_dict hd
             where hd.dept_code = v.dept_admission_to
               and rownum = 1)
         ),
         1,
         50
       ) as DEPT_NAME,-- 科室名称  是 患者在医疗机构就诊的科室名称

       substr(
         nvl(
           (select hd.dept_name
              from his.dept_dict hd
             where hd.dept_code = v.discharge_ward_code
               and rownum = 1),
           v.discharge_ward_code
         ),
         1,
         50
       ) as WARD_NAME,-- 病区名称    患者当前所在病区的名称

       cast(null as varchar2(10)) as EORD_NUM,--  病房号   患者住院期间，所住病房对应的编号

       substr(v.discharge_bed_no,1,10) as SICKBED_NUM,-- 病床号   患者住院期间，所住病床对应的编号

       substr(b.operating_room,1,20) as OPERA_ROOM_NUM,--  手术间编号   对患者实施手术操作时所在的手术室房间编号

       substr(pmi.name,1,50) as NAME,--  患者姓名  是 患者本人在公安户籍管理部门正式登记注册的姓氏和名称

       decode(pmi.sex,'男',1,'女',2,'未知',0,9) as SEX_CODE,--  性别代码  是 患者生理性别在特定编码体系中的代码

       decode(pmi.sex,'男','男','女','女','未知','未知','其他') as SEX_NAME,--  性别  是 男，女，未知，其他

       case
         when pmi.date_of_birth is not null
          and v.admission_date_time is not null
         then greatest(trunc(months_between(v.admission_date_time, pmi.date_of_birth) / 12), 0)
         else cast(null as number(3))
       end as AGE,-- 年龄    整数

       nvl(
         case
           when a.weight is not null
            and regexp_like(trim(to_char(a.weight)), '^[0-9]+(\.[0-9]+)?$')
           then round(to_number(a.weight),2)
           else cast(null as number(6,2))
         end,
         cast(0 as number(6,2))
       ) as WEIGHT,--  体重（kg）    患者体重的测量值，计量单位为kg

       substr(
           nvl(
             (select cd.国标编码
                from cda.cda_dictionary cd
               where cd.字典名称 = 'ICD-9手术编码'
                 and cd.系统标识 = 'SM'
                 and cd.院标名称 = b.operation_name
                 and rownum = 1)  ,(select cd.国标编码
                from cda.cda_dictionary cd
               where cd.字典名称 = 'ICD-9手术编码'
                 and cd.系统标识 = 'HIS'
                 and (cd.院标编码 =         regexp_replace(trim(cast(o.operation_code as varchar2(100))), '[A-Z][0-9]*$', '') or cd.院标编码 = o.operation_code )

                 and rownum = 1)

           ),
         1,
         50
       ) as OPERA_CODE,--  手术及操作编码

       substr(
           nvl(
            (select cd.国标名称
                from cda.cda_dictionary cd
               where cd.字典名称 = 'ICD-9手术编码'
                 and cd.系统标识 = 'SM'
                 and cd.院标名称 = b.operation_name
                 and rownum = 1), (select cd.国标名称
                from cda.cda_dictionary cd
               where cd.字典名称 = 'ICD-9手术编码'
                 and cd.系统标识 = 'HIS'
                 and (cd.院标编码 =         regexp_replace(trim(cast(o.operation_code as varchar2(100))), '[A-Z][0-9]*$', '') or cd.院标编码 = o.operation_code )
                 and rownum = 1)

           ),
         1,
         500
       ) as OPERA_NAME,--  手术及操作名称 是
       case
         when b.operation_position like '%仰卧位%' or b.operation_position like '%平%' then 1
         when b.operation_position like '%俯卧位%' or b.operation_position = '卧位' then 2
         when b.operation_position like '%左侧卧%' or b.operation_position = '侧卧位' then 3
         when b.operation_position like '%右侧卧%' or b.operation_position like '%侧卧%' then 4
         when b.operation_position like '%截石位%' then 5
         when b.operation_position like '%屈氏位%' then 6
         else 9
       end as OPERA_POSITION_CODE,-- 手术体位代码  是 手术时患者采取的体位在特定编码体系中的代码

       nvl(substr(
         case
           when b.operation_position like '%仰卧位%' or b.operation_position like '%平%' then '仰卧位'
           when b.operation_position like '%俯卧位%' or b.operation_position = '卧位' then '俯卧位'
           when b.operation_position like '%左侧卧%' or b.operation_position = '侧卧位' then '左侧卧位'
           when b.operation_position like '%右侧卧%' or b.operation_position like '%侧卧%' then '右侧卧位'
           when b.operation_position like '%截石位%' then '截石位'
           when b.operation_position like '%屈氏位%' then '屈氏位'
           else nvl(b.operation_position,'其他')
         end,
         1,
         50
       ),'-') as OPERA_POSITION_NAME,-- 手术体位名称  是

       nvl(
  (select to_number(cd.国标编码)
     from cda.cda_dictionary cd
    where cd.字典名称 = '麻醉方法代码表'
      and cd.系统标识 = 'HIS'
      and cd.院标名称 = o.anaesthesia_method
      and regexp_like(cd.国标编码, '^[0-9]+$')
      and rownum = 1),
  nvl(
    (select to_number(cd.国标编码)
       from cda.cda_dictionary cd
      where cd.字典名称 = '麻醉方法代码表'
        and cd.系统标识 = '手麻'
        and cd.院标名称 = b.anesthesia_method
        and regexp_like(cd.国标编码, '^[0-9]+$')
        and rownum = 1),
    case
      when b.anesthesia_method is null
        or trim(b.anesthesia_method) in ('', '/', '\', '-', '无')
      then 9

      when b.anesthesia_method like '%控制性降压%' then 45
      when b.anesthesia_method like '%全身降温%'
        or b.anesthesia_method like '%低温麻醉%'
      then 44

      when (
             b.anesthesia_method like '%臂丛%'
          or b.anesthesia_method like '%颈丛%'
          or b.anesthesia_method like '%神经丛%'
           )
       and (
             b.anesthesia_method like '%硬膜外%'
          or b.anesthesia_method like '%腰硬%'
          or b.anesthesia_method like '%腰-硬%'
           )
      then 43

      when b.anesthesia_method like '%静吸复合%' then 41

      when b.anesthesia_method like '%针药%'
        or b.anesthesia_method like '%针刺%'
      then 42

      when regexp_like(b.anesthesia_method, '全麻|全身麻醉|气管插管全麻|气管插管全身麻醉|非插管全麻|无插管全麻')
       and regexp_like(b.anesthesia_method, '臂丛|颈丛|神经阻滞|区域神经阻滞|椎管|腰硬|腰-硬|硬膜外|局麻|局部|基础麻醉')
      then 4

      when b.anesthesia_method like '%静脉麻醉%'
        or b.anesthesia_method like '%静脉全麻%'
        or b.anesthesia_method like '%全凭静脉%'
        or b.anesthesia_method like '%全静脉%'
        or b.anesthesia_method like '%全屏静脉%' -- 兼容错别字
        or trim(b.anesthesia_method) = '静脉'
      then 12

      when b.anesthesia_method like '%吸入麻醉%' then 11

      when b.anesthesia_method like '%基础麻醉%'
        or trim(b.anesthesia_method) in ('基础','基础麻醉','基础+强化','基础加强化')
      then 13

      when b.anesthesia_method like '%蛛网膜下%'
        or b.anesthesia_method like '%腰麻%'
        or b.anesthesia_method like '%单次腰麻%'
      then 21

      when b.anesthesia_method like '%硬膜外%'
        or b.anesthesia_method like '%硬膜外腔%'
        or b.anesthesia_method like '%硬脊膜外%'
        or b.anesthesia_method like '%连续硬膜外%'
      then 22

      when b.anesthesia_method like '%椎管内%'
        or b.anesthesia_method like '%椎管麻醉%'
        or b.anesthesia_method like '%腰硬联合%'
        or b.anesthesia_method like '%腰-硬联合%'
        or b.anesthesia_method like '%硬要联合%' -- 兼容错别字
      then 2

      when b.anesthesia_method like '%星状神经节%' then 32

      when b.anesthesia_method like '%臂丛%'
        or b.anesthesia_method like '%颈丛%'
        or b.anesthesia_method like '%腰骶神经丛%'
        or b.anesthesia_method like '%神经丛%'
      then 31

      when b.anesthesia_method like '%坐骨神经%'
        or b.anesthesia_method like '%股神经%'
        or b.anesthesia_method like '%尺神经%'
        or b.anesthesia_method like '%肋间神经%'
        or b.anesthesia_method like '%神经阻滞%'
        or b.anesthesia_method like '%神经阻滞麻醉%'
      then 33

      when b.anesthesia_method like '%区域神经阻滞%'
        or b.anesthesia_method like '%区域阻滞%'
        or b.anesthesia_method like '%域神经阻滞%' -- 兼容漏字
      then 34

      when b.anesthesia_method like '%局部浸润%' then 35

      when b.anesthesia_method like '%表面麻醉%'
        or b.anesthesia_method like '%表面粘膜麻醉%'
      then 36

      when b.anesthesia_method like '%局麻%'
        or b.anesthesia_method like '%局部麻醉%'
        or b.anesthesia_method like '%局部%'
      then 3

      when b.anesthesia_method like '%全身麻醉%'
        or b.anesthesia_method like '%全麻%'
        or trim(b.anesthesia_method) = '全'
      then 1

      when b.anesthesia_method like '%复合麻醉%' then 4

      else 9
    end
  )
) as ANES_METHOD_CODE,-- 麻醉方法代码  as ANES_METHOD_CODE,--  麻醉方法代码  是 为患者进行手术、操作时使用的麻醉方法在特定编码体系中的代码

    case
  when b.anesthesia_method is null
    or trim(b.anesthesia_method) in ('', '/', '\', '-', '无')
  then '其他麻醉方法'

  when b.anesthesia_method like '%控制性降压%' then '全麻复合控制性降压'
  when b.anesthesia_method like '%全身降温%'
    or b.anesthesia_method like '%低温麻醉%' then '全麻复合全身降温'
  when b.anesthesia_method like '%静吸复合%' then '静吸复合全麻'
  when b.anesthesia_method like '%针刺%'
    or b.anesthesia_method like '%针药%' then '针药复合麻醉'

  when regexp_like(b.anesthesia_method, '全麻|全身麻醉|气管插管全麻|气管插管全身麻醉|非插管全麻|无插管全麻')
   and regexp_like(b.anesthesia_method, '臂丛|颈丛|神经阻滞|区域神经阻滞|椎管|腰硬|腰-硬|硬膜外|局麻|局部|基础麻醉')
  then '复合麻醉'

  when b.anesthesia_method like '%吸入麻醉%' then '吸入麻醉'

  when b.anesthesia_method like '%静脉麻醉%'
    or b.anesthesia_method like '%静脉全麻%'
    or b.anesthesia_method like '%全凭静脉%'
    or b.anesthesia_method like '%全静脉%'
    or b.anesthesia_method like '%全屏静脉%'
    or trim(b.anesthesia_method) = '静脉'
  then '静脉麻醉'

  when b.anesthesia_method like '%基础麻醉%'
    or trim(b.anesthesia_method) in ('基础','基础麻醉','基础+强化','基础加强化')
  then '基础麻醉'

  when b.anesthesia_method like '%蛛网膜下%'
    or b.anesthesia_method like '%腰麻%'
    or b.anesthesia_method like '%单次腰麻%'
  then '蛛网膜下腔阻滞麻醉'

  when b.anesthesia_method like '%硬膜外%'
    or b.anesthesia_method like '%硬膜外腔%'
    or b.anesthesia_method like '%硬脊膜外%'
    or b.anesthesia_method like '%连续硬膜外%'
  then '硬脊膜外腔阻滞麻醉'

  when b.anesthesia_method like '%椎管内%'
    or b.anesthesia_method like '%椎管麻醉%'
    or b.anesthesia_method like '%腰硬联合%'
    or b.anesthesia_method like '%腰-硬联合%'
    or b.anesthesia_method like '%硬要联合%'
  then '椎管内麻醉'

  when b.anesthesia_method like '%星状神经节%' then '神经节阻滞麻醉'

  when b.anesthesia_method like '%臂丛%'
    or b.anesthesia_method like '%颈丛%'
    or b.anesthesia_method like '%腰骶神经丛%'
    or b.anesthesia_method like '%神经丛%'
  then '神经丛阻滞麻醉'

  when b.anesthesia_method like '%坐骨神经%'
    or b.anesthesia_method like '%股神经%'
    or b.anesthesia_method like '%尺神经%'
    or b.anesthesia_method like '%肋间神经%'
    or b.anesthesia_method like '%腘窝%'
    or b.anesthesia_method like '%隐神经%'
    or b.anesthesia_method like '%收肌管%'
    or b.anesthesia_method like '%髂筋膜%'
    or b.anesthesia_method like '%神经阻滞%'
    or b.anesthesia_method like '%神经阻滞麻醉%'
  then '神经阻滞麻醉'

  when b.anesthesia_method like '%区域神经阻滞%'
    or b.anesthesia_method like '%区域阻滞%'
    or b.anesthesia_method like '%区域阻滞麻醉%'
    or b.anesthesia_method like '%域神经阻滞%'
  then '区域阻滞麻醉'

  when b.anesthesia_method like '%局部浸润%' then '局部浸润麻醉'

  when b.anesthesia_method like '%表面麻醉%'
    or b.anesthesia_method like '%表面粘膜麻醉%'
  then '表面麻醉'

  when b.anesthesia_method like '%局麻%'
    or b.anesthesia_method like '%局部麻醉%'
    or b.anesthesia_method like '%局部%'
  then '局部麻醉'

  when b.anesthesia_method like '%全身麻醉%'
    or b.anesthesia_method like '%全麻%'
    or trim(b.anesthesia_method) = '全'
  then '全身麻醉'

  when b.anesthesia_method like '%复合麻醉%' then '复合麻醉'

  else '其他麻醉方法'
end as ANES_METHOD_NAME,-- 麻醉方法名称      as ANES_METHOD_NAME,-- 麻醉方法名称 as ANES_METHOD_NAME,-- 麻醉方法名称   as ANES_METHOD_NAME,--  麻醉方法名称  是

       substr(nvl(b.stop_anes_area_tech,'-'),1,100) as OPERA_WINDPIPE,--  气管插管分类    标识全身麻醉时气管插管分类的描述

       case
         when b.stop_anes_area_tech like '%控制%' then 3
         when b.stop_anes_area_tech like '%辅助%' or b.stop_anes_area_tech like '%单腔加强管%' then 2
         else 1
       end as BREATH_TYPE,-- 呼吸类型代码    呼吸类型的分类代码

       substr(
         case
           when b.stop_anes_area_tech like '%控制%' then '控制呼吸'
           when b.stop_anes_area_tech like '%辅助%' or b.stop_anes_area_tech like '%单腔加强管%' then '辅助呼吸'
           else '自主呼吸'
         end,
         1,
         50
       ) as BREATH_TYPE_NAME,--  呼吸类型名称    　按照医院内部名称填写

       substr(nvl(b.anesthesia_method,'-'),1,2000) as ANES_NOTE,-- 麻醉描述    麻醉过程的详细描述

       cast(1 as number(1)) as ANES_MERGE_CODE,-- 麻醉合并症标志代码   是否具有麻醉合并症的分类代码

       substr(nvl(b.diag_after_operation,'一般性医学检查'),1,2000) as DIAGNOSIS_NOTE,--  诊疗过程描述    对患者手术治疗过程的详细描述

       substr(nvl(a.artery_vein_puncture_pos,'-'),1,2000) as PIER_NOTE,-- 穿刺过程    局部麻醉中穿刺过程的详细描述

       cast(null as number(3)) as SHRINK_PRESSURE,-- 收缩压（mmHg）   手术过程中，最后一次测量结果

       cast(null as number(3)) as DIASTOLE_PRESSURE,-- 舒张压（mmHg）   手术过程中，最后一次测量结果

       nvl(
         case
           when a.tempeture is not null
            and regexp_like(trim(to_char(a.tempeture)), '^[0-9]+(\.[0-9]+)?$')
           then round(to_number(a.tempeture),1)
           else cast(null as number(4,1))
         end,
         cast(36.8 as number(4,1))
       ) as TEMPERATURE,-- 体温（℃）   手术过程中，最后一次测量结果

       nvl(
         case
           when a.cardiotach is not null
            and regexp_like(trim(to_char(a.cardiotach)), '^[0-9]+$')
           then to_number(a.cardiotach)
           else cast(null as number(3))
         end,
         0
       ) as HEART_RATE,--  心率（次/min）   手术过程中，最后一次测量结果

       nvl(
         case
           when a.plus is not null
            and regexp_like(trim(to_char(a.plus)), '^[0-9]+$')
           then to_number(a.plus)
           else cast(null as number(3))
         end,
         0
       ) as PULSE_RATE,--  脉率（次/min）   手术过程中，最后一次测量结果

       nvl(
         case
           when a.breath is not null
            and regexp_like(trim(to_char(a.breath)), '^[0-9]+$')
           then to_number(a.breath)
           else cast(null as number(3))
         end,
         0
       ) as RESPIRATORY_RATE,--  呼吸频率（次/min）   手术过程中，最后一次测量结果

       '好' as SIGNATURE_EFFECT,--  麻醉效果    实施麻醉效果的描述

       substr(nvl(a.pre_anes_pham,'无'),1,100) as BEFORE_SIGNATURE_DRUG,-- 麻醉前用药   在患者进行麻醉前给予的药品的具体描述，药品名称之间使用#分割

       cast(nvl(b.start_date_time,o.operating_date) as date) as OPERA_START_DATE,--  手术开始日期时间  是 yymmdd hh24miss

       cast(nvl(b.anes_start_time,b.start_date_time) as date) as ANES_START_DATE,-- 麻醉开始日期时间  是 yymmdd hh24miss

       cast(nvl(b.anes_end_time,b.end_date_time) as date) as ANES_END_DATE,-- 麻醉结束日期时间  是 yymmdd hh24miss

       cast(nvl(nvl(b.end_date_time,b.out_date_time),o.operating_end_date) as date) as OPERA_END_DATE,--  手术结束日期时间  是 yymmdd hh24miss

       cast(nvl(b.out_date_time,nvl(b.end_date_time,o.operating_end_date)) as date) as OUT_DEPT_DATE,-- 出手术室日期时间  是 yymmdd hh24miss

       substr(
         nvl(
           case
             when regexp_like(b.surgeon, '^[0-9]+$') then
               (select yg.name
                  from his.staff_dict yg
                 where yg.emp_no = b.surgeon
                   and rownum = 1)
             else b.surgeon
           end,
           '-'
         ),
         1,
         50
       ) as OPERAER_NAME,--  手术者姓名   主刀医生

       case
         when b.pacu_start_time is not null or b.pacu_end_time is not null then '1'
         else '0'
       end as PACU_FLAG,-- 复苏室进入标识 是 1是 0 否

       cast(b.pacu_start_time as date) as PACU_IN_DATE,--  复苏室进入时间 是

       cast(b.pacu_end_time as date) as PACU_OUT_DATE,-- 复苏室结束时间 是

       substr(
         (select max(mae.item_name)
            from sm.med_anesthesia_event mae
           where mae.patient_id = b.patient_id
             and mae.visit_id   = b.visit_id
             and mae.oper_id    = b.oper_id
             and mae.item_class = '3'),
         1,
         50
       ) as OPERA_TRANSFUSION,-- 术中输液项目    手术过程中输入液体的描述

       case
         when b.blood_lossed is not null
          and regexp_like(trim(to_char(b.blood_lossed)), '^[0-9]+(\.[0-9]+)?$')
         then round(to_number(b.blood_lossed))
         else cast(null as number(5))
       end as OUT_BLOOD_ML,--  出血量（mL）   手术中出血量的累计值，计量单位为mL

     case
    /* ICU及各类重症监护室 */
    when regexp_like(
             upper(
                 trim(
                     (
                         select max(to_char(sq.item_value))
                           from sm.med_custom_data sq
                          where sq.patient_id = b.patient_id
                            and sq.visit_id   = b.visit_id
                            and sq.oper_id    = b.oper_id
                            and sq.item_name  = '麻醉单.患者去向'
                     )
                 )
             ),
             'ICU|PICU'
         )
    then 2

    /* 麻醉恢复室、PACU */
    when regexp_like(
             upper(
                 trim(
                     (
                         select max(to_char(sq.item_value))
                           from sm.med_custom_data sq
                          where sq.patient_id = b.patient_id
                            and sq.visit_id   = b.visit_id
                            and sq.oper_id    = b.oper_id
                            and sq.item_name  = '麻醉单.患者去向'
                     )
                 )
             ),
             'PACU|复苏室|复苏间|麻醉复苏'
         )
    then 3

    /* 返回普通病房 */
    when regexp_like(
             trim(
                 (
                     select max(to_char(sq.item_value))
                       from sm.med_custom_data sq
                      where sq.patient_id = b.patient_id
                        and sq.visit_id   = b.visit_id
                        and sq.oper_id    = b.oper_id
                        and sq.item_name  = '麻醉单.患者去向'
                 )
             ),
             '病房|回病房'
         )
    then 1

    /* 原始数据已经是合法代码时保留 */
    when trim(
             (
                 select max(to_char(sq.item_value))
                   from sm.med_custom_data sq
                  where sq.patient_id = b.patient_id
                    and sq.visit_id   = b.visit_id
                    and sq.oper_id    = b.oper_id
                    and sq.item_name  = '麻醉单.患者去向'
             )
         ) in ('1', '2', '3')
    then to_number(
             trim(
                 (
                     select max(to_char(sq.item_value))
                       from sm.med_custom_data sq
                      where sq.patient_id = b.patient_id
                        and sq.visit_id   = b.visit_id
                        and sq.oper_id    = b.oper_id
                        and sq.item_name  = '麻醉单.患者去向'
                 )
             )
         )

    /* +、/、100、1400、人员姓名、科室名称等异常值不上传 */
    else cast(null as number)
end as PATIENT_TO, --  患者去向代码    患者当前诊疗过程结束后的去向在特定编码体系中的代码，这里指手术结束后的去向

      nvl( substr(
         nvl(
               (select sd.name
                  from his.staff_dict sd
                 where sd.emp_no = b.anesthesia_doctor
                   and rownum = 1),  (select sd.name
                  from his.staff_dict sd
                 where sd.emp_no = o.ANESTHESIA_DOCTOR
                   and rownum = 1)
         ),
         1,
         50
       ),'-') as ANES_DOC_NAME,-- 麻醉医师签名  是 对患者实施麻醉的麻醉医师签署的在公安户籍管理部门正式登记注册的姓氏和名称


       cast(nvl(b.start_date_time,o.operating_date) as date) as SIGNATURE_DATE,--  签名日期时间  是 yymmdd hh24miss

       '370104' as DISTRICT_CODE,-- 行政区划  是

       'ADDHIS' as EXCHANGE_TYPE,-- 交换类型  是 INSERT：向平台传新数据时 UPDATE：向平台更新某条数据时 DELETE：从平台删除某条数据时  ADDHIS :向平台补充历史数据

       cast(systimestamp as timestamp) as SYSTEM_TIME --数据上传时间  是 数据上传时间

from sm.med_operation_master b

 join sm.med_anesthesia_plan a
   on a.patient_id = b.patient_id
  and a.visit_id   = b.visit_id
  and a.oper_id    = b.oper_id
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
from his.operation o  )  where rn=1)  o
   on o.patient_id = b.patient_id
  and o.visit_id   = b.visit_id
  --and o.operation_no = b.oper_id
  and      to_char(o.operating_date,'yyyy-mm-dd') = to_char(b.scheduled_date_time,'yyyy-mm-dd')
 left join his.pat_visit v
   on a.patient_id = v.patient_id
  and a.visit_id   = v.visit_id

 left join his.pat_master_index pmi
   on v.patient_id = pmi.patient_id

 left join (
    select *
      from (
            select d.*,
                   row_number() over(
                     partition by d.patient_id,d.visit_id
                     order by d.diagnosis_date desc,d.diagnosis_no
                   ) as rn
              from his.diagnosis d
             where d.diagnosis_type = '3'
           )
     where rn = 1
 ) dd
   on b.patient_id = dd.patient_id
  and b.visit_id   = dd.visit_id

where nvl(to_char(b.oper_status),'0') <> '0'
  and v.discharge_date_time >= to_date('2021-01-01 00:00:00','yyyy-mm-dd hh24:mi:ss')
  and v.discharge_date_time <  to_date('2025-01-01 00:00:00','yyyy-mm-dd hh24:mi:ss')
  and  cast(nvl(b.anes_start_time,b.start_date_time) as date) is not null  and        substr(
           nvl(
            (select cd.国标名称
                from cda.cda_dictionary cd
               where cd.字典名称 = 'ICD-9手术编码'
                 and cd.系统标识 = 'SM'
                 and cd.院标名称 = b.operation_name
                 and rownum = 1), (select cd.国标名称
                from cda.cda_dictionary cd
               where cd.字典名称 = 'ICD-9手术编码'
                 and cd.系统标识 = 'HIS'
                 and (cd.院标编码 =         regexp_replace(trim(cast(o.operation_code as varchar2(100))), '[A-Z][0-9]*$', '') or cd.院标编码 = o.operation_code )
                 and rownum = 1)

           ),
         1,
         500
       ) is not null and cast(nvl(nvl(b.end_date_time,b.out_date_time),o.operating_end_date) as date)  is not null   and  cast(nvl(b.start_date_time,o.operating_date) as date)  is not null
       and  cast(nvl(b.start_date_time,o.operating_date) as date)    is not null  and  cast(nvl(b.anes_end_time,b.end_date_time) as date)   is not null
