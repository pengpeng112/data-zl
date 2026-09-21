
  CREATE OR REPLACE FORCE VIEW "ODS"."V_EMR_ADMISSION_RECORD_EXAM" ("ID", "AR_ID", "SN", "EXAM_TYPE", "EXAM_TYPENAME", "EXAM_TIME", "HOS_ITEM_NAME", "HOS_ITEM_CODE", "EXAM_TIME_NAME", "EXAM_TIME_CODE", "EXAM_RESULT", "CREATED_AT", "DISTRICT_CODE", "EXCHANGE_TYPE", "SYSTEM_TIME", "ORG_CODE", "ORG_NAME") AS 
  select substr(
           '49557032X' || '|' ||
           x.patient_id || '|' ||
           x.visit_id || '|' ||
           x.exam_no || '|' ||
           x.sn,
           1,
           100
       ) as ID,-- 内码 是 主键

       substr(
           '49557032X' || '|' || x.patient_id || '|' || x.visit_id,
           1,
           100
       ) as AR_ID,-- 入院记录内码 是，必须与 EMR_ADMISSION_RECORD.ID 保持一致

       cast(x.sn as number(3)) as SN,-- 序号 是，必须是整数

       '2' as EXAM_TYPE,-- 检查类型 是 体格检查

       '辅助检查' as EXAM_TYPENAME,-- 检查类型名称 是

       cast(x.exam_date_time as date) as EXAM_TIME,-- 检查时间 是

       substr(nvl(nullif(trim(x.exam_item), ''), '-'), 1, 100) as HOS_ITEM_NAME,-- 院内检查项目名称 是

       substr(nvl(nullif(trim(x.exam_item_code), ''), '-'), 1, 50) as HOS_ITEM_CODE,-- 院内检查项目代码 是

       substr(
           nvl(
               (
                   select max(m.value_domain_name)
                     from CDA_EXAM_ITEM_MAP m
                    where m.category_code = 'CV04.30.009'
                      and m.hospital_code = x.exam_item_code
               ),
               nvl(nullif(trim(x.exam_item), ''), '-')
           ),
           1,
           50
       ) as EXAM_TIME_NAME,-- 检查项目名称 是

       substr(
           nvl(
               (
                   select max(m.value_domain_code)
                     from CDA_EXAM_ITEM_MAP m
                    where m.category_code = 'CV04.30.009'
                      and m.hospital_code = x.exam_item_code
               ),
               nvl(nullif(trim(x.exam_item_code), ''), '-')
           ),
           1,
           50
       ) as EXAM_TIME_CODE,-- 检查项目编码 是

       substr(
           nvl(
               nullif(
                   trim(
                       regexp_replace(
                           replace(x.jcbg, '$nbsp$', ' '),
                           '[[:space:]]+',
                           ' '
                       )
                   ),
                   ''
               ),
               '-'
           ),
           1,
           4000
       ) as EXAM_RESULT,-- 检查结果 是

       cast(null as timestamp) as CREATED_AT,-- 创建时间，平台自动生成，不需要填写

       '370104' as DISTRICT_CODE,-- 所属行政区划 是

       'INSERT' as EXCHANGE_TYPE,-- 交换类型 是

       cast(systimestamp as timestamp) as SYSTEM_TIME,-- 数据上传时间戳 是

       '49557032X' as ORG_CODE,-- 医院组织机构代码 是

       '山东省第二人民医院' as ORG_NAME-- 医院名称 是

from (
        select y.patient_id,
               y.visit_id,
               y.exam_no,
               y.exam_date_time,
               y.exam_item,
               y.exam_item_code,
               y.jcbg,
               y.sn
          from (
                select t.patient_id,
                       t.visit_id,
                       t.exam_no,
                       t.exam_date_time,
                       t1.exam_item,
                       t1.exam_item_code,

                       substr(
                           trim(
                               nvl(nullif(trim(r.impression), ''), '') ||

                               case
                                   when nullif(trim(r.description), '') is not null
                                    and nvl(trim(r.description), '-') <> nvl(trim(r.impression), '-')
                                   then ' ' || trim(r.description)
                                   else ''
                               end ||

                               case
                                   when nullif(trim(r.recommendation), '') is not null
                                    and nvl(trim(r.recommendation), '-') <> nvl(trim(r.impression), '-')
                                    and nvl(trim(r.recommendation), '-') <> nvl(trim(r.description), '-')
                                   then ' ' || trim(r.recommendation)
                                   else ''
                               end
                           ),
                           1,
                           4000
                       ) as jcbg,

                       row_number() over (
                           partition by t.patient_id, t.visit_id
                           order by t.exam_date_time,
                                    t.exam_no,
                                    nvl(t1.exam_item_code, '-'),
                                    nvl(t1.exam_item, '-')
                       ) as sn

                  from his.exam_master t

                  inner join his.exam_items t1
                          on t.exam_no = t1.exam_no

                  inner join his.pat_visit pv
                          on pv.patient_id = t.patient_id
                         and to_char(pv.visit_id) = to_char(t.visit_id)

                  inner join his.exam_report r
                          on r.exam_no = t.exam_no

                 where t.patient_id is not null
                   and t.visit_id is not null
                   and t.exam_no is not null
                   and t.exam_date_time is not null
                   and pv.discharge_date_time >= to_date('2021-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss')
                   and pv.discharge_date_time <  to_date('2025-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss')
                   and (
                           nullif(trim(r.description), '') is not null
                        or nullif(trim(r.impression), '') is not null
                        or nullif(trim(r.recommendation), '') is not null
                       )
               ) y
         where y.sn <= 999
           and nullif(trim(y.jcbg), '') is not null
     ) x
