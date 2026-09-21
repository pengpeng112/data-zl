
  CREATE OR REPLACE FORCE VIEW "ODS"."V_EMR_ANES_RECORD_MED" ("ID", "APPLY_NUM", "ORG_CODE", "ORG_NAME", "DRUG_TYPE", "ANES_FLAG", "DRUG_CONT", "DRUG_STARTIME", "DRUG_ENDTIME", "DRUG_NAME", "DRUG_CODE", "DRUG_ROUTE", "DRUG_FREQUENCY_CODE", "DOSAGE_UNIT", "DRUG_UNIT_DOSE", "DRUG_ALL", "DRUG_WAY_CODE", "DISTRICT_CODE", "EXCHANGE_TYPE", "SYSTEM_TIME") AS 
  select substr(
         '49557032X'
         || '|' || b.patient_id
         || '|' || b.visit_id
         || '|' || b.oper_id
         || '|' || mae.item_no,
         1,
         100
       ) as ID,-- 内码 是 唯一主键

       b.patient_id || b.visit_id || b.oper_id as APPLY_NUM,-- 电子申请单编号 是 手术申请单编号

       '49557032X' as ORG_CODE,-- 组织机构代码 是 医疗机构组织机构代码

       '山东省第二人民医院' as ORG_NAME,-- 组织机构名称 是 医疗机构组织机构名称

       '9' as DRUG_TYPE,-- 药物使用目的代码，暂按其他处理

       case
         when mae.item_class = '2' then '1'
         when regexp_like(
                nvl(mae.item_name,''),
                '丙泊酚|依托咪酯|氯胺酮|七氟烷|异氟烷|地氟烷|芬太尼|舒芬太尼|瑞芬太尼|咪达唑仑|罗库溴铵|阿曲库铵|阿屈库铵|维库溴铵|右美托咪定|利多卡因|罗哌卡因|布比卡因|丁卡因'
              )
         then '1'
         else '0'
       end as ANES_FLAG,-- 是否麻醉药物标识 是

       case
         when mae.end_date is not null
          and (
                nvl(to_char(mae.durative_indicator),'0') = '1'
             or mae.administrator like '%泵%'
             or mae.dosage_units like '%/h%'
             or mae.dosage_units like '%/min%'
          )
         then '1'
         else '0'
       end as DRUG_CONT,-- 是否术中持续用药标识 是

       cast(
         nvl(
           mae.start_time,
           nvl(b.anes_start_time, b.start_date_time)
         ) as date
       ) as DRUG_STARTIME,-- 用药开始时间 是

       case
         when mae.end_date is not null
          and (
                nvl(to_char(mae.durative_indicator),'0') = '1'
             or mae.administrator like '%泵%'
             or mae.dosage_units like '%/h%'
             or mae.dosage_units like '%/min%'
          )
         then cast(mae.end_date as date)
         else cast(null as date)
       end as DRUG_ENDTIME,-- 用药结束时间，持续用药标识为1时必填

       substr(
         regexp_replace(
           trim(nvl(mae.item_name,'-')),
           '[[:space:]]*(mg|ug|μg|g|ml|mL|%|vi)$',
           '',
           1,
           0,
           'i'
         ),
         1,
         100
       ) as DRUG_NAME,-- 药物名称 是

       substr(nvl(mae.item_code,'-'),1,50) as DRUG_CODE,-- 药品代码

       substr(
         case
           when mae.administrator = 'i.v.' then '静脉注射'
           when lower(mae.administrator) in ('ivgtt','ivggt') then '静脉滴注'
           when mae.administrator = '泵注' then '泵入'
           when mae.administrator = '吸入' then '吸入'
           when mae.administrator = '臂丛' then '神经阻滞'
           else mae.administrator
         end,
         1,
         100
       ) as DRUG_ROUTE,-- 药物用法

       'st' as DRUG_FREQUENCY_CODE,-- 药物使用频次代码

       substr(
         nvl(
           mae.dosage_units,
           regexp_substr(mae.item_spec, '(mg|ug|μg|g|ml|mL|%)[[:space:]]*$', 1, 1, 'i')
         ),
         1,
         10
       ) as DOSAGE_UNIT,-- 药物使用计量单位

       round(mae.dosage,2) as DRUG_UNIT_DOSE,-- 药物使用次剂量

       case
         when mae.end_date is not null
          and mae.start_time is not null
          and mae.end_date > mae.start_time
          and mae.dosage_units like '%/h%'
         then round(mae.dosage * ((mae.end_date - mae.start_time) * 24), 2)
         else round(mae.dosage,2)
       end as DRUG_ALL,-- 药物使用总剂量

   case
  when mae.administrator is null
    or trim(mae.administrator) in ('', '0', '30', '备用', '备注', '台上', '台上用', 'ADMINISTRATOR')
  then 9

  -- 口服、直肠、舌下
  when lower(replace(trim(mae.administrator), ' ', '')) in ('po', 'p.o.', 'o.p.', '口服')
    or trim(mae.administrator) like '%口服%'
  then 1

  when trim(mae.administrator) like '%直肠%'
    or trim(mae.administrator) like '%灌肠%'
    or trim(mae.administrator) like '%肛管%'
  then 2

  when trim(mae.administrator) like '%舌下%' then 3

  -- 静脉注射或静脉滴注
  when lower(replace(trim(mae.administrator), ' ', '')) in
       ('i.v.', 'i.v', 'iv', 'ivgtt', 'ivggt', 'ivtt', 'ivgtt.', 'ivggt.')
    or trim(mae.administrator) like '%静脉%'
    or trim(mae.administrator) like '%滴注%'
    or trim(mae.administrator) like '%冲管%'
    or trim(mae.administrator) like '%冲管测压%'
  then 404

  -- 输液泵泵入
  when trim(mae.administrator) like '%泵%'
    or upper(trim(mae.administrator)) in ('TCI', 'PCA', 'PCIA', 'PCEA')
  then 700

  -- 吸入、雾化、气道相关
  when trim(mae.administrator) = '吸入'
    or trim(mae.administrator) like '%吸入%'
    or trim(mae.administrator) like '%雾化%'
  then 5

  when trim(mae.administrator) like '%气管内%'
    or trim(mae.administrator) = '气管'
  then 606

  when trim(mae.administrator) like '%喷喉%' then 609

  when trim(mae.administrator) like '%滴鼻%'
    or trim(mae.administrator) like '%喷鼻%'
    or trim(mae.administrator) like '%鼻腔%'
  then 608

  when trim(mae.administrator) like '%滴眼%' then 607

  -- 注射细分
  when lower(replace(trim(mae.administrator), ' ', '')) in ('i.m.', 'i.m', 'im', '肌注')
    or trim(mae.administrator) like '%肌注%'
  then 403

  when trim(mae.administrator) like '%皮下%' then 401

  when trim(mae.administrator) like '%皮内%' then 402

  when trim(mae.administrator) like '%鞘内%' then 405

  -- 椎管内、硬膜外、神经阻滞、区域阻滞
  when trim(mae.administrator) like '%硬膜外%'
    or trim(mae.administrator) like '%硬外%'
    or trim(mae.administrator) like '%腰麻%'
    or trim(mae.administrator) like '%骶管%'
    or trim(mae.administrator) like '%椎管%'
    or trim(mae.administrator) like '%臂丛%'
    or trim(mae.administrator) like '%颈丛%'
    or trim(mae.administrator) like '%股神经%'
    or trim(mae.administrator) like '%坐骨神经%'
    or trim(mae.administrator) like '%隐神经%'
    or trim(mae.administrator) like '%肋间神经%'
    or trim(mae.administrator) like '%肋间阻滞%'
    or trim(mae.administrator) like '%神经阻滞%'
    or trim(mae.administrator) like '%区域阻滞%'
    or trim(mae.administrator) like '%肌间沟%'
    or trim(mae.administrator) like '%腋路%'
    or trim(mae.administrator) like '%收肌管%'
    or upper(trim(mae.administrator)) = 'TAP'
    or trim(mae.administrator) like '%腹横肌%'
  then 601

  -- 局部用药
  when trim(mae.administrator) like '%局麻%'
    or trim(mae.administrator) like '%局部麻醉%'
    or trim(mae.administrator) like '%局部注射%'
    or trim(mae.administrator) like '%局部浸润%'
    or trim(mae.administrator) like '%浸润%'
    or trim(mae.administrator) like '%表面%'
    or trim(mae.administrator) like '%表麻%'
    or trim(mae.administrator) like '%外用%'
    or trim(mae.administrator) like '%润滑%'
    or trim(mae.administrator) like '%喷洒%'
  then 6

  -- 腔内给药
  when trim(mae.administrator) like '%关节腔%'
    or trim(mae.administrator) like '%踝关节%'
  then 602

  when trim(mae.administrator) like '%胸膜%' then 603

  when trim(mae.administrator) like '%腹腔%' then 604

  when upper(trim(mae.administrator)) = 'VD'
    or trim(mae.administrator) like '%阴道%'
  then 605

  -- 不能明确归类
  else 9
end as DRUG_WAY_CODE,-- 用药途径代码     as DRUG_WAY_CODE,-- 用药途径代码

       '370104' as DISTRICT_CODE,-- 行政区划 是

       'ADDHIS' as EXCHANGE_TYPE,-- 交换类型 是

       cast(systimestamp as timestamp) as SYSTEM_TIME-- 数据上传时间 是

from sm.med_operation_master b

join sm.med_anesthesia_event mae
  on mae.patient_id = b.patient_id
 and mae.visit_id   = b.visit_id
 and mae.oper_id    = b.oper_id
 and mae.item_class in ('2','3','C')

join his.pat_visit v
  on v.patient_id = b.patient_id
 and v.visit_id   = b.visit_id

where nvl(to_char(b.oper_status),'0') <> '0'
  and mae.item_name is not null
  and mae.start_time is not null
  and mae.dosage is not null
  and mae.dosage > 0
  and v.discharge_date_time >= to_date('2021-01-01 00:00:00','yyyy-mm-dd hh24:mi:ss')
  and v.discharge_date_time <  to_date('2025-01-01 00:00:00','yyyy-mm-dd hh24:mi:ss') and   substr(
         regexp_replace(
           trim(nvl(mae.item_name,'-')),
           '[[:space:]]*(mg|ug|μg|g|ml|mL|%|vi)$',
           '',
           1,
           0,
           'i'
         ),
         1,
         100
       ) is not null
