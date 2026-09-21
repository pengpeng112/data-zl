
  CREATE OR REPLACE FORCE VIEW "ODS"."V_EMR_ANES_RECORD_BLOOD" ("ID", "APPLY_NUM", "ORG_CODE", "ORG_NAME", "START_DATE", "END_DATE", "IS_AUTOLOGOUS_BLOOD", "TRANSFUSION_TYPE_CODE", "TRANSFUSION_ML", "TRANSFUSION_UNIT", "BT_REACTION_MARK", "DISTRICT_CODE", "EXCHANGE_TYPE", "SYSTEM_TIME") AS 
  select substr(
         '49557032X'
         || '|' || b.patient_id
         || '|' || b.visit_id
         || '|' || b.oper_id
         || '|' || b.blood_item,
         1,
         100
       ) as ID,-- 内码 是 唯一主键

       b.patient_id || b.visit_id || b.oper_id as APPLY_NUM,-- 电子申请单编号 是 手术申请单编号

       '49557032X' as ORG_CODE,-- 组织机构代码 是 医疗机构组织机构代码

       '山东省第二人民医院' as ORG_NAME,-- 组织机构名称 是 医疗机构组织机构名称

       cast(
         nvl(
           b.start_date_time,
           nvl(b.anes_start_time, nvl(b.in_date_time, b.scheduled_date_time))
         ) as date
       ) as START_DATE,-- 输血开始日期时间 是 YYYYMMDD HHMISS

       cast(
         nvl(
           b.end_date_time,
           nvl(b.anes_end_time, nvl(b.out_date_time, nvl(b.done_date_time, b.start_date_time)))
         ) as date
       ) as END_DATE,-- 输血结束日期时间 是 YYYYMMDD HHMISS

       case
         when b.blood_item in ('BLOOD_WHOLE_SELF','SELF_BLOOD','BLOOD_REUSE') then '1'
         else '0'
       end as IS_AUTOLOGOUS_BLOOD,-- 是否为自体输血 是 0否 1是

       case
         when b.blood_item = 'BLOOD_RBC'        then '13' -- 红细胞悬液
         when b.blood_item = 'BLOOD_PLASM'      then '4'  -- 血浆
         when b.blood_item = 'BLOOD_OTHER'      then '5'  -- 冷沉淀
         when b.blood_item = 'COOL_THING'       then '5'  -- 冷沉淀
         when b.blood_item = 'BLOOD_WHOLE'      then '3'  -- 血小板，按主表说明
         when b.blood_item = 'BLOOD_XB'         then '3'  -- 血小板
         when b.blood_item = 'BLOOD_WHOLE_SELF' then '9'  -- 自体血
         when b.blood_item = 'SELF_BLOOD'       then '9'  -- 自体血
         when b.blood_item = 'BLOOD_REUSE'      then '9'  -- 回收血/自体回输
         else '9'
       end as TRANSFUSION_TYPE_CODE,-- 输血品种代码 是

       case
         when b.blood_item = 'BLOOD_RBC'        then round(b.blood_qty * 200)
         when b.blood_item = 'BLOOD_WHOLE'      then round(b.blood_qty * 200)
         when b.blood_item = 'BLOOD_XB'         then round(b.blood_qty * 200)
         when b.blood_item = 'BLOOD_OTHER'      then round(b.blood_qty * 200)
         when b.blood_item = 'COOL_THING'       then round(b.blood_qty * 200)
         when b.blood_item = 'BLOOD_PLASM'      then round(b.blood_qty)
         when b.blood_item = 'BLOOD_WHOLE_SELF' then round(b.blood_qty)
         when b.blood_item = 'SELF_BLOOD'       then round(b.blood_qty)
         when b.blood_item = 'BLOOD_REUSE'      then round(b.blood_qty)
         else round(b.blood_qty)
       end as TRANSFUSION_ML,-- 输血量 是

       'mL' as TRANSFUSION_UNIT,-- 输血量计量单位 是

       '0' as BT_REACTION_MARK,-- 输血反应标志 是

       '370104' as DISTRICT_CODE,-- 行政区划 是

       'ADDHIS' as EXCHANGE_TYPE,-- 交换类型 是

       cast(systimestamp as timestamp) as SYSTEM_TIME-- 数据上传时间 是

from sm.med_operation_master
unpivot (
  blood_qty
  for blood_item in (
     blood_rbc        as 'BLOOD_RBC',
     blood_plasm      as 'BLOOD_PLASM',
     blood_other      as 'BLOOD_OTHER',
     blood_whole      as 'BLOOD_WHOLE',
     blood_xb         as 'BLOOD_XB',
     cool_thing       as 'COOL_THING',
     blood_whole_self as 'BLOOD_WHOLE_SELF',
     self_blood       as 'SELF_BLOOD',
     blood_reuse      as 'BLOOD_REUSE'
  )
) b

left join his.pat_visit v
  on v.patient_id = b.patient_id
 and v.visit_id   = b.visit_id

where nvl(to_char(b.oper_status),'0') <> '0'
  and b.blood_qty is not null
  and b.blood_qty > 0
  and nvl(b.start_date_time, nvl(b.anes_start_time, nvl(b.in_date_time, b.scheduled_date_time))) is not null
  and nvl(b.end_date_time, nvl(b.anes_end_time, nvl(b.out_date_time, nvl(b.done_date_time, b.start_date_time)))) is not null
  and v.discharge_date_time >= to_date('2021-01-01 00:00:00','yyyy-mm-dd hh24:mi:ss')
  and v.discharge_date_time <  to_date('2025-01-01 00:00:00','yyyy-mm-dd hh24:mi:ss')
