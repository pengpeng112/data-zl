
  CREATE OR REPLACE FORCE VIEW "ODS"."V_EMR_ICH_ALLERGIES" ("ID", "ICH_ID", "SN", "MEDICINE", "MEDICINE_CODE", "DISTRICT_CODE", "CREATED_AT", "EXCHANGE_TYPE", "SYSTEM_TIME", "ORG_CODE", "ORG_NAME", "ADMISSION_ID", "NAME", "SEX_CODE", "ID_NUM") AS 
  select
       cast(
           substrb(
               '49557032X' || '|' || x.patient_id || '|' || x.visit_id || '|' || x.sn,
               1,
               100
           ) as varchar2(100)
       ) as ID,--内码 是 主键；增加SN避免同一次住院多个过敏药物主键重复

       cast(
           substrb(
               '49557032X' || '|' || x.patient_id || '|' || x.visit_id,
               1,
               100
           ) as varchar2(100)
       ) as ICH_ID,--病案首页内码 是；必须与EMR_ICH.ID一致

       x.sn as SN,--序号；同一次住院内按拆分后的过敏药物重新编号

       cast(substrb(x.medicine, 1, 50) as varchar2(50)) as MEDICINE,--过敏药物名称 是；由PAT_VISIT.ALERGY_DRUGS拆分清洗

       cast(null as varchar2(12)) as MEDICINE_CODE,--过敏药物代码；暂无明确药品标准编码来源，暂不编造

       cast('370104' as varchar2(6)) as DISTRICT_CODE,--所属行政区划 是

       cast(nvl(x.discharge_date_time, x.admission_date_time) as timestamp) as CREATED_AT,--创建时间；优先出院时间，空时取入院时间

       cast('ADDHIS' as varchar2(10)) as EXCHANGE_TYPE,--交换类型 是

       cast(systimestamp as timestamp) as SYSTEM_TIME,--数据上传时间戳 是

       cast('49557032X' as varchar2(32)) as ORG_CODE,--医院组织机构代码 是

       cast('山东省第二人民医院' as varchar2(70)) as ORG_NAME,--医院名称 是

       cast(
           substrb(
               x.patient_id || '|' || x.visit_id,
               1,
               20
           ) as varchar2(20)
       ) as ADMISSION_ID,--本次住院标识号 是

       cast(substrb(nvl(to_char(x.name), '-'), 1, 50) as varchar2(50)) as NAME,--患者姓名 是

       cast(
           decode(x.sex, '男', '1', '女', '2', '未知', '0', '9')
           as char(1)
       ) as SEX_CODE,--患者性别代码 是；0未知，1男，2女，9不明

       cast(
           substrb(
               nvl(to_char(x.id_no), '000000000000000000'),
               1,
               18
           ) as varchar2(18)
       ) as ID_NUM--患者身份证件号码 是

from (
    select y.*,
           row_number() over (
               partition by y.patient_id, y.visit_id
               order by y.seq
           ) as sn
      from (
          select base.patient_id,
                 base.visit_id,
                 base.admission_date_time,
                 base.discharge_date_time,
                 base.name,
                 base.sex,
                 base.id_no,
                 level as seq,
                 trim(
                     regexp_substr(
                         base.allergy_text_norm,
                         '[^,]+',
                         1,
                         level
                     )
                 ) as medicine
            from (
                select a.patient_id,
                       a.visit_id,
                       a.admission_date_time,
                       a.discharge_date_time,
                       b.name,
                       b.sex,
                       b.id_no,
                       trim(
                           both ',' from
                           regexp_replace(
                               regexp_replace(
                                   regexp_replace(
                                       trim(to_char(a.alergy_drugs)),
                                       '[[:space:]]+',
                                       ''
                                   ),
                                   '[，、;；/／|｜+＋]+',
                                   ','
                               ),
                               ',+',
                               ','
                           )
                       ) as allergy_text_norm
                  from his.pat_visit a
                  left join his.pat_master_index b
                    on b.patient_id = a.patient_id
                 where a.alergy_drugs is not null
                   and trim(to_char(a.alergy_drugs)) is not null
                   and regexp_replace(trim(to_char(a.alergy_drugs)), '[[:space:]]+', '') not in
                       ('无', '否', '无过敏', '无药物过敏', '无药物过敏史',
                        '未发现', '未见', '不详', '未知', '-', '--', '—')
                   and a.discharge_date_time >= date '2021-01-01'
                   and a.discharge_date_time <  date '2025-01-01'
            ) base
          connect by prior base.patient_id = base.patient_id
                 and prior base.visit_id = base.visit_id
                 and prior sys_guid() is not null
                 and level <= regexp_count(base.allergy_text_norm, ',') + 1
      ) y
     where y.medicine is not null
       and y.medicine not in
           ('无', '否', '无过敏', '无药物过敏', '无药物过敏史',
            '未发现', '未见', '不详', '未知', '-', '--', '—')
) x
