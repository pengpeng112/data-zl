
  CREATE OR REPLACE FORCE VIEW "ODS"."V_EMR_OPERATION_NURSING" ("ID", "ORG_CODE", "ORG_NAME", "ADMISSION_ID", "DEPT_CODE", "DEPT_NAME", "WARD_NAME", "EORD_NUM", "SICKBED_NUM", "OPERATION_ROOM_NUM", "NAME", "SEX_CODE", "SEX_NAME", "AGE", "AGE_MONTH", "WEIGHT", "ABO_CODE", "BLOOD_ABO_NAME", "RH_CODE", "BLOOD_RH_NAME", "DIAGNOSIS_CODE", "DISEASE", "OPERATION_CODE", "OPERATION_NAME", "OPERA_DOC_NAME", "OPERATION_BP_NAME", "OPERATION_END_DATE", "OPERATION_START_DATE", "ALLERGIES_CODE", "ALLERGIES", "SKIN_CHECK_NOTE", "NURSE_LEVEL_CODE", "NURSE_LEVEL_NAME", "NURSE_OBSERVE_NAME", "NURSE_OBSERVE_RESULT", "NURSE_PROJECT", "NURSE_PROJECT_NAME", "NURSE_PROJECT_RESULT", "IN_ROOM_DATE", "OUT_ROOM_DATE", "PREPARATION", "OPERATION_DISEASE_CD", "OPERATION_ITEM", "BEFORE_OPER_CD", "BEFORE_CHECK_CODE", "AFTER_CHECK_CODE", "HANDOVER_PROJECT", "ROUND_NURSE_NAME", "INS_NURSE_NAME", "HANDOVER_NURSE", "TRANS_DOC_NAME", "HANDOVER_DATE", "RECORD_DATE", "DISTRICT_CODE", "EXCHANGE_TYPE", "SYSTEM_TIME") AS 
  select
       substrb(
           '49557032X'
           || '|' || a.patient_id
           || '|' || a.visit_id
           || '|' || a.oper_id,
           1,
           100
       ) as ID, -- 内码 是 使用组织机构编码+业务主键或流水号

       '49557032X' as ORG_CODE, -- 组织机构代码 是

       '山东省第二人民医院' as ORG_NAME, -- 组织机构名称 是

       substrb(a.patient_id || '|' || a.visit_id, 1, 50) as ADMISSION_ID, -- 住院唯一标示号 是

       nvl(
           substrb(
               (select max(d.qmpt_code)
                  from his.dept_dict d
                 where d.dept_code = p.dept_admission_to),
               1,
               20
           ),
           '-'
       ) as DEPT_CODE, -- 科室代码

       nvl(
           substrb(
               (select max(d.qmpt_name)
                  from his.dept_dict d
                 where d.dept_code = p.dept_admission_to),
               1,
               50
           ),
           '-'
       ) as DEPT_NAME, -- 科室名称 是

       nvl(
           substrb(
               (select max(d.dept_name)
                  from his.dept_dict d
                 where d.dept_code = p.discharge_ward_code),
               1,
               50
           ),
           '-'
       ) as WARD_NAME, -- 病区名称 是

       cast(null as varchar2(10)) as EORD_NUM, -- 病房号，暂未确认来源

       substrb(p.discharge_bed_no, 1, 10) as SICKBED_NUM, -- 病床号

substrb(a.operating_room, 1, 20) as OPERATION_ROOM_NUM, -- 手术间编号
       substrb(pmi.name, 1, 50) as NAME, -- 患者姓名 是

       decode(pmi.sex, '男', '1', '女', '2', '未知', '0', '9') as SEX_CODE, -- 性别代码 是

       decode(pmi.sex, '男', '男', '女', '女', '未知', '未知', '不明') as SEX_NAME, -- 性别名称 是

       case
           when pmi.date_of_birth is not null
            and p.admission_date_time is not null
           then greatest(trunc(months_between(p.admission_date_time, pmi.date_of_birth) / 12), 0)
           else null
       end as AGE, -- 年龄 是

       case
           when pmi.date_of_birth is not null
            and p.admission_date_time is not null
            and trunc(months_between(p.admission_date_time, pmi.date_of_birth) / 12) = 0
           then substrb(to_char(mod(trunc(months_between(p.admission_date_time, pmi.date_of_birth)), 12)), 1, 2)
           else null
       end as AGE_MONTH, -- 年龄（月）

       nvl(e3.weight, 0) as WEIGHT, -- 体重 kg 是

case
    when regexp_like(upper(nurse.xuexing), 'AB') then 4
    when regexp_like(upper(nurse.xuexing), 'A')  then 1
    when regexp_like(upper(nurse.xuexing), 'B')  then 2
    when regexp_like(upper(nurse.xuexing), 'O')  then 3
    else 5
end as ABO_CODE,

case
    when regexp_like(upper(nurse.xuexing), 'AB') then 'AB'
    when regexp_like(upper(nurse.xuexing), 'A')  then 'A'
    when regexp_like(upper(nurse.xuexing), 'B')  then 'B'
    when regexp_like(upper(nurse.xuexing), 'O')  then 'O'
    else '不详'
end as BLOOD_ABO_NAME,

case
    when nurse.xuexing like '%阴%' or regexp_like(upper(nurse.xuexing), 'RH-') then 1
    when nurse.xuexing like '%阳%' or regexp_like(upper(nurse.xuexing), 'RH\+') then 2
    else 3
end as RH_CODE,

case
    when nurse.xuexing like '%阴%' or regexp_like(upper(nurse.xuexing), 'RH-') then '阴性'
    when nurse.xuexing like '%阳%' or regexp_like(upper(nurse.xuexing), 'RH\+') then '阳性'
    else '不详'
end as BLOOD_RH_NAME,

       substrb(
           nvl(
               nvl(
                   (select max(cd.国标编码)
                      from cda.cda_dictionary cd
                     where cd.字典名称 = 'ICD-10诊断编码'
                       and cd.系统标识 = 'SM'
                       and cd.院标名称 = a.diag_before_operation),
                   (select max(cd.国标编码)
                      from cda.cda_dictionary cd
                     where cd.字典名称 = 'ICD-10诊断编码'
                       and cd.系统标识 = 'HIS'
                       and cd.院标名称 = dd.diagnosis_desc)
               ),
               dd.diagnosis_code
           ),
           1,
           12
       ) as DIAGNOSIS_CODE, -- 术前诊断编码

       nvl(
           substrb(
               nvl(
                   nvl(
                       (select max(cd.国标名称)
                          from cda.cda_dictionary cd
                         where cd.字典名称 = 'ICD-10诊断编码'
                           and cd.系统标识 = 'SM'
                           and cd.院标名称 = a.diag_before_operation),
                       (select max(cd.国标名称)
                          from cda.cda_dictionary cd
                         where cd.字典名称 = 'ICD-10诊断编码'
                           and cd.系统标识 = 'HIS'
                           and cd.院标名称 = dd.diagnosis_desc)
                   ),
                   nvl(a.diag_before_operation, dd.diagnosis_desc)
               ),
               1,
               200
           ),
           '-'
       ) as DISEASE, -- 疾病诊断名称 是

       substrb(
           nvl(
               nvl(
                   nvl(
                       (select max(cd.国标编码)
                          from cda.cda_dictionary cd
                         where cd.字典名称 = 'ICD-9手术编码'
                           and cd.系统标识 = 'SM'
                           and cd.院标名称 = a.operation_name),
                       (select max(cd.国标编码)
                          from cda.cda_dictionary cd
                         where cd.字典名称 = 'ICD-9手术编码'
                           and cd.系统标识 = 'HIS'
                           and (
                                  cd.院标编码 = regexp_replace(trim(to_char(o.operation_code)), '[A-Z][0-9]*$', '')
                               or cd.院标编码 = o.operation_code
                               )
                       )
                   ),
                   (select max(cd.国标编码)
                      from cda.cda_dictionary cd
                     where cd.字典名称 = 'ICD-9手术编码'
                       and cd.系统标识 = 'HIS'
                       and cd.院标名称 = o.operation_desc)
               ),
               o.operation_code
           ),
           1,
           12
       ) as OPERATION_CODE, -- 手术及操作编码

       nvl(
           substrb(
               nvl(
                   a.operation_name,
                   nvl(
                       nvl(
                           nvl(
                               (select max(cd.国标名称)
                                  from cda.cda_dictionary cd
                                 where cd.字典名称 = 'ICD-9手术编码'
                                   and cd.系统标识 = 'SM'
                                   and cd.院标名称 = a.operation_name),
                               (select max(cd.国标名称)
                                  from cda.cda_dictionary cd
                                 where cd.字典名称 = 'ICD-9手术编码'
                                   and cd.系统标识 = 'HIS'
                                   and (
                                          cd.院标编码 = regexp_replace(trim(to_char(o.operation_code)), '[A-Z][0-9]*$', '')
                                       or cd.院标编码 = o.operation_code
                                       )
                               )
                           ),
                           (select max(cd.国标名称)
                              from cda.cda_dictionary cd
                             where cd.字典名称 = 'ICD-9手术编码'
                               and cd.系统标识 = 'HIS'
                               and cd.院标名称 = o.operation_desc)
                       ),
                       o.operation_desc
                   )
               ),
               1,
               80
           ),
           '-'
       ) as OPERATION_NAME, -- 手术/操作-名称 是
substrb(
    nvl(
        case
            when regexp_like(a.surgeon, '^[0-9]+$') then
                (select max(sd.name)
                   from his.staff_dict sd
                  where sd.emp_no = a.surgeon)
            else a.surgeon
        end,
        '-'
    ),
    1,
    50
) as OPERA_DOC_NAME, -- 手术者姓名
       '-' as OPERATION_BP_NAME, -- 手术目标部位名称 是，暂未确认来源字段

       to_char(
           nvl(a.end_date_time, nvl(a.done_date_time, a.anes_end_time)),
           'yyyy-mm-dd hh24:mi:ss'
       ) as OPERATION_END_DATE, -- 手术结束日期时间 是

       to_char(
           nvl(a.start_date_time, a.scheduled_date_time),
           'yyyy-mm-dd hh24:mi:ss'
       ) as OPERATION_START_DATE, -- 手术开始日期时间 是

       '0' as ALLERGIES_CODE, -- 过敏史标志 是，暂按否

       cast(null as varchar2(1000)) as ALLERGIES, -- 过敏史，暂未确认来源

       substrb(
           nvl(
               nullif(
                   '皮肤情况:' || nvl(nurse.pifu1, '') ||
                   case when nurse.pifu2 is not null then '；补充:' || nurse.pifu2 end ||
                   case when nurse.jianc1 is not null then '；术后皮肤检查:' || nurse.jianc1 end ||
                   case when nurse.jianc2 is not null then '；说明:' || nurse.jianc2 end,
                   '皮肤情况:'
               ),
               '-'
           ),
           1,
           1000
       ) as SKIN_CHECK_NOTE, -- 皮肤检查描述

       '1' as NURSE_LEVEL_CODE, -- 护理等级代码 是，暂按一级护理

       '一级护理' as NURSE_LEVEL_NAME, -- 护理等级名称 是，暂按一级护理

       '皮肤情况、体位、输液、导尿、标本、保温、用药、清点核对' as NURSE_OBSERVE_NAME, -- 护理观察项目名称

       substrb(
           nvl(
               nullif(
                   '皮肤:' || nvl(nurse.pifu1, '') ||
                   case when nurse.tiwei1 is not null then '；体位:' || nurse.tiwei1 end ||
                   case when nurse.shuye1 is not null then '；输液部位:' || nurse.shuye1 end ||
                   case when nurse.daoniao1 is not null then '；导尿管:' || nurse.daoniao1 end ||
                   case when nurse.biaoben1 is not null then '；病理标本:' || nurse.biaoben1 || ' 数量:' || nvl(nurse.biaoben2, '') end ||
                   case when nurse.zhuan_gui is not null then '；转归:' || nurse.zhuan_gui end,
                   '皮肤:'
               ),
               '-'
           ),
           1,
           1000
       ) as NURSE_OBSERVE_RESULT, -- 护理观察结果 是

       '手术护理、术中用药、输液护理、体位护理、电刀安全、标本管理、导尿管管理、皮肤护理、病人交接' as NURSE_PROJECT, -- 护理操作项目类目名称 是

       substrb(
           nvl(
               nullif(
                   '术中用药:' || nvl(nurse.yongyao2, '') ||
                   case when nurse.shuye1 is not null then '；输液:' || nurse.shuye1 end ||
                   case when nurse.baowen1 is not null then '；保温:' || nurse.baowen1 end ||
                   case when nurse.diandao1 is not null then '；高频电刀:' || nurse.diandao1 || nvl2(nurse.diandao2, ' ' || nurse.diandao2, '') end ||
                   case when nurse.diandao3 is not null then '；电凝:' || nurse.diandao3 || nvl2(nurse.diandao4, ' ' || nurse.diandao4, '') end ||
                   case when nurse.diandao5 is not null then '；双极:' || nurse.diandao5 || nvl2(nurse.diandao6, ' ' || nurse.diandao6, '') end ||
                   case when nurse.dianjiban1 is not null then '；电极板:' || nurse.dianjiban1 end ||
                   case when nurse.zhixue1 is not null then '；止血:' || nurse.zhixue1 end,
                   '术中用药:'
               ),
               '-'
           ),
           1,
           100
       ) as NURSE_PROJECT_NAME, -- 护理操作名称 是

       substrb(
           nvl(
               nullif(
                   '术中用药:' || nvl(nurse.yongyao2, '') ||
                   case when nurse.yongyao31 is not null then '；医嘱签字:' || nurse.yongyao31 end ||
                   case when nurse.jianyan1 is not null then '；检验:' || nurse.jianyan1 end ||
                   case when nurse.yingxiang1 is not null then '；影像:' || nurse.yingxiang1 end ||
                   case when nurse.xuexing is not null then '；血型:' || nurse.xuexing end ||
                   case when nurse.biaoben1 is not null then '；标本:' || nurse.biaoben1 || ' 数量:' || nvl(nurse.biaoben2, '') || ' 病理:' || nvl(nurse.biaoben3, '') end ||
                   case when nurse.daoniao1 is not null then '；导尿管:' || nurse.daoniao1 end ||
                   case when nurse.zhuan_gui is not null then '；术后转归:' || nurse.zhuan_gui end,
                   '术中用药:'
               ),
               '-'
           ),
           1,
           1000
       ) as NURSE_PROJECT_RESULT, -- 护理操作结果 是

       nvl(
           case
               when regexp_like(nurse.hltime1, '^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}')
               then to_char(to_date(substr(nurse.hltime1, 1, 16), 'yyyy-mm-dd hh24:mi'), 'yyyy-mm-dd hh24:mi:ss')
           end,
           to_char(nvl(a.start_date_time, a.scheduled_date_time), 'yyyy-mm-dd hh24:mi:ss')
       ) as IN_ROOM_DATE, -- 入手术室日期时间 是

       nvl(
           case
               when regexp_like(nurse.hltime2, '^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}')
               then to_char(to_date(substr(nurse.hltime2, 1, 16), 'yyyy-mm-dd hh24:mi'), 'yyyy-mm-dd hh24:mi:ss')
           end,
           to_char(nvl(a.end_date_time, nvl(a.done_date_time, a.anes_end_time)), 'yyyy-mm-dd hh24:mi:ss')
       ) as OUT_ROOM_DATE, -- 出手术室日期时间 是

       substrb(
           nvl(
               nullif(
                   '检验:' || nvl(nurse.jianyan1, '') ||
                   case when nurse.yingxiang1 is not null then '；影像:' || nurse.yingxiang1 end ||
                   case when nurse.shuye1 is not null then '；输液部位:' || nurse.shuye1 end ||
                   case when nurse.xuexing is not null then '；血型种类:' || nurse.xuexing end ||
                   case when nurse.baowen13 is not null then '；保温措施:' || nurse.baowen13 end ||
                   case when nurse.baowen144 is not null then '；预防措施:' || nurse.baowen144 end,
                   '检验:'
               ),
               '-'
           ),
           1,
           1000
       ) as PREPARATION, -- 准备事项 是

       case
           when nurse.biaoben1 like '%有%' then '1'
           else '0'
       end as OPERATION_DISEASE_CD, -- 术中病理标志 是

       substrb(
           nvl(
               nullif(
                   nvl2(nurse.diandao1, '电刀:' || nurse.diandao1 || '；', '') ||
                   nvl2(nurse.dianjiban1, '电极板:' || nurse.dianjiban1 || '；', '') ||
                   nvl2(nurse.zhixue1, '止血:' || nurse.zhixue1 || '；', '') ||
                   nvl2(nurse.daoniao1, '导尿管:' || nurse.daoniao1 || '；', '') ||
                   nvl2(nurse.biaoben1, '标本:' || nurse.biaoben1 || '；', ''),
                   ''
               ),
               '-'
           ),
           1,
           50
       ) as OPERATION_ITEM, -- 术中所用物品名称 是

       case
           when nurse.jianc1 like '%完整%' then '1'
           else '0'
       end as BEFORE_OPER_CD, -- 术前清点标志，暂按护理检查完整判断

       case
           when nurse.jianc1 like '%完整%' then '1'
           else '0'
       end as BEFORE_CHECK_CODE, -- 术前核对标志，暂按护理检查完整判断

       case
           when nurse.jianc1 like '%完整%' then '1'
           else '0'
       end as AFTER_CHECK_CODE, -- 术后核对标志，暂按术后皮肤/护理检查完整判断

       '身份、手术名称、手术部位、皮肤、管路、标本、病历资料' as HANDOVER_PROJECT, -- 病人交接核对项目 是

substrb(nvl(nurse.hlname7, nvl(nurse.hlname1, '-')), 1, 50) as ROUND_NURSE_NAME, -- 巡台护士签名

substrb(nvl(nurse.hlname8, nvl(nurse.hlname2, '-')), 1, 50) as INS_NURSE_NAME, -- 器械护士签名

substrb(nvl(nurse.hlname7, nvl(nurse.hlname1, '-')), 1, 50) as HANDOVER_NURSE, -- 交接护士签名

substrb(
    nvl(nurse.hlname7, nvl(nurse.hlname1, '-')),
    1,
    50
) as TRANS_DOC_NAME, -- 转运者签名，暂无明确转运者字段，暂用交接/巡回护士兜底
       nvl(
           case
               when regexp_like(nurse.hltime2, '^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}')
               then to_char(to_date(substr(nurse.hltime2, 1, 16), 'yyyy-mm-dd hh24:mi'), 'yyyy-mm-dd hh24:mi:ss')
           end,
           to_char(nvl(a.end_date_time, nvl(a.done_date_time, a.anes_end_time)), 'yyyy-mm-dd hh24:mi:ss')
       ) as HANDOVER_DATE, -- 交接日期时间 是

       nvl(
           case
               when regexp_like(nurse.hltime8, '^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}')
               then to_char(to_date(substr(nurse.hltime8, 1, 16), 'yyyy-mm-dd hh24:mi'), 'yyyy-mm-dd hh24:mi:ss')
           end,
           nvl(
               case
                   when regexp_like(nurse.hltime2, '^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}')
                   then to_char(to_date(substr(nurse.hltime2, 1, 16), 'yyyy-mm-dd hh24:mi'), 'yyyy-mm-dd hh24:mi:ss')
               end,
               to_char(nvl(a.end_date_time, nvl(a.done_date_time, a.anes_end_time)), 'yyyy-mm-dd hh24:mi:ss')
           )
       ) as RECORD_DATE, -- 签名日期时间 是

       '370104' as DISTRICT_CODE, -- 行政区划 是

       'ADDHIS' as EXCHANGE_TYPE, -- 交换类型 是

       to_char(sysdate, 'yyyy-mm-dd hh24:mi:ss') as SYSTEM_TIME -- 数据上传时间 是

from sm.med_operation_master a

left join sm.med_operation_schedule a1
  on a.patient_id = a1.patient_id
 and a.visit_id   = a1.visit_id
 and a.oper_id    = a1.oper_id

left join sm.med_anesthesia_plan e3
  on a.patient_id = e3.patient_id
 and a.visit_id   = e3.visit_id
 and a.oper_id    = e3.oper_id

left join (
    select *
      from (
            select o.*,
                   row_number() over (
                       partition by o.patient_id,
                                    o.visit_id,
                                    trunc(o.operating_date)
                       order by o.operation_scale desc nulls last,
                                case when to_char(o.op_primary) = '1' then 1 else 0 end desc,
                                o.operation_no asc nulls last
                   ) as rn
              from his.operation o
           )
     where rn = 1
) o
  on a.patient_id = o.patient_id
 and a.visit_id   = o.visit_id
 and to_char(o.operating_date, 'yyyy-mm-dd') =
     to_char(nvl(a.start_date_time, a.scheduled_date_time), 'yyyy-mm-dd')

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
           row_number() over (
               partition by d.patient_id, d.visit_id
               order by decode(d.diagnosis_type, '2', 1, '3', 2, 9),
                        d.diagnosis_no
           ) as rn
      from his.diagnosis d
     where d.diagnosis_type in ('2', '3')
) dd
  on dd.rn = 1
 and a.patient_id = dd.patient_id
 and a.visit_id   = dd.visit_id

left join (
    select sh.patient_id,
           sh.visit_id,
           sh.oper_id,

           max(case when sh.item_name in ('手术护理.OPERATION_NAME', '手术护理1.OPERATION_NAME') then nullif(trim(sh.item_value), '/') end) as nursing_operation_name,

           max(case when sh.item_name in ('护理记录.pifu情况1', '护理记录1.pifu情况1') then nullif(trim(sh.item_value), '/') end) as pifu1,
           max(case when sh.item_name in ('护理记录.pifu情况2', '护理记录1.pifu情况2') then nullif(trim(sh.item_value), '/') end) as pifu2,

           max(case when sh.item_name in ('护理记录.电刀1', '护理记录1.电刀1') then nullif(trim(sh.item_value), '/') end) as diandao1,
           max(case when sh.item_name in ('护理记录.电刀2', '护理记录1.电刀2') then nullif(trim(sh.item_value), '/') end) as diandao2,
           max(case when sh.item_name in ('护理记录.电刀3', '护理记录1.电刀3') then nullif(trim(sh.item_value), '/') end) as diandao3,
           max(case when sh.item_name in ('护理记录.电刀4', '护理记录1.电刀4') then nullif(trim(sh.item_value), '/') end) as diandao4,
           max(case when sh.item_name in ('护理记录.电刀5', '护理记录1.电刀5') then nullif(trim(sh.item_value), '/') end) as diandao5,
           max(case when sh.item_name in ('护理记录.电刀6', '护理记录1.电刀6') then nullif(trim(sh.item_value), '/') end) as diandao6,
           max(case when sh.item_name in ('护理记录.电刀7', '护理记录1.电刀7') then nullif(trim(sh.item_value), '/') end) as diandao7,

           max(case when sh.item_name in ('护理记录.电极板1', '护理记录1.电极板1') then nullif(trim(sh.item_value), '/') end) as dianjiban1,
           max(case when sh.item_name in ('护理记录.电极板2', '护理记录1.电极板2') then nullif(trim(sh.item_value), '/') end) as dianjiban2,
           max(case when sh.item_name in ('护理记录.电极板3', '护理记录1.电极板3') then nullif(trim(sh.item_value), '/') end) as dianjiban3,

           max(case when sh.item_name in ('护理记录.麻醉方式', '护理记录1.麻醉方式') then nullif(trim(sh.item_value), '/') end) as mazui_method,

           max(case when sh.item_name in ('护理记录.术中用药1', '护理记录1.术中用药1') then nullif(trim(sh.item_value), '/') end) as yongyao1,
           max(case when sh.item_name in ('护理记录.术中用药2', '护理记录1.术中用药2') then nullif(trim(sh.item_value), '/') end) as yongyao2,
           max(case when sh.item_name in ('护理记录.术中用药21', '护理记录1.术中用药21') then nullif(trim(sh.item_value), '/') end) as yongyao21,
           max(case when sh.item_name in ('护理记录.术中用药22', '护理记录1.术中用药22') then nullif(trim(sh.item_value), '/') end) as yongyao22,
           max(case when sh.item_name in ('护理记录.术中用药31', '护理记录1.术中用药31') then nullif(trim(sh.item_value), '/') end) as yongyao31,
           max(case when sh.item_name in ('护理记录.术中用药32', '护理记录1.术中用药32') then nullif(trim(sh.item_value), '/') end) as yongyao32,
           max(case when sh.item_name in ('护理记录.术中用药33', '护理记录1.术中用药33') then nullif(trim(sh.item_value), '/') end) as yongyao33,

           max(case when sh.item_name in ('护理记录.体位', '护理记录1.体位') then nullif(trim(sh.item_value), '/') end) as tiwei1,
           max(case when sh.item_name in ('护理记录.体位2', '护理记录1.体位2') then nullif(trim(sh.item_value), '/') end) as tiwei2,

           max(case when sh.item_name in ('护理记录.止血1', '护理记录1.止血1') then nullif(trim(sh.item_value), '/') end) as zhixue1,
           max(case when sh.item_name in ('护理记录.止血2', '护理记录1.止血2') then nullif(trim(sh.item_value), '/') end) as zhixue2,
           max(case when sh.item_name in ('护理记录.止血3', '护理记录1.止血3') then nullif(trim(sh.item_value), '/') end) as zhixue3,
           max(case when sh.item_name in ('护理记录.止血4', '护理记录1.止血4') then nullif(trim(sh.item_value), '/') end) as zhixue4,
           max(case when sh.item_name in ('护理记录.止血5', '护理记录1.止血5') then nullif(trim(sh.item_value), '/') end) as zhixue5,
           max(case when sh.item_name in ('护理记录.止血9', '护理记录1.止血9') then nullif(trim(sh.item_value), '/') end) as zhixue9,

           max(case when sh.item_name in ('手术护理.标本1', '手术护理1.标本1') then nullif(trim(sh.item_value), '/') end) as biaoben1,
           max(case when sh.item_name in ('手术护理.标本2', '手术护理1.标本2') then nullif(trim(sh.item_value), '/') end) as biaoben2,
           max(case when sh.item_name in ('手术护理.标本3', '手术护理1.标本3') then nullif(trim(sh.item_value), '/') end) as biaoben3,

           max(case when sh.item_name in ('手术护理.导尿管1', '手术护理1.导尿管1') then nullif(trim(sh.item_value), '/') end) as daoniao1,
           max(case when sh.item_name in ('手术护理.导尿管2', '手术护理1.导尿管2') then nullif(trim(sh.item_value), '/') end) as daoniao2,
           max(case when sh.item_name in ('手术护理.导尿管3', '手术护理1.导尿管3') then nullif(trim(sh.item_value), '/') end) as daoniao3,
           max(case when sh.item_name in ('手术护理.导尿管4', '手术护理1.导尿管4') then nullif(trim(sh.item_value), '/') end) as daoniao4,

           max(case when sh.item_name in ('手术护理.护理jianc1', '手术护理1.护理jianc1') then nullif(trim(sh.item_value), '/') end) as jianc1,
           max(case when sh.item_name in ('手术护理.护理jianc2', '手术护理1.护理jianc2') then nullif(trim(sh.item_value), '/') end) as jianc2,

           max(case when sh.item_name in ('手术护理.护理name1', '手术护理1.护理name1') then nullif(trim(sh.item_value), '/') end) as hlname1,
           max(case when sh.item_name in ('手术护理.护理name2', '手术护理1.护理name2') then nullif(trim(sh.item_value), '/') end) as hlname2,
           max(case when sh.item_name in ('手术护理.护理name7', '手术护理1.护理name7') then nullif(trim(sh.item_value), '/') end) as hlname7,
           max(case when sh.item_name in ('手术护理.护理name8', '手术护理1.护理name8') then nullif(trim(sh.item_value), '/') end) as hlname8,

           max(case when sh.item_name in ('手术护理.护理time1', '手术护理1.护理time1') then nullif(trim(sh.item_value), '/') end) as hltime1,
           max(case when sh.item_name in ('手术护理.护理time2', '手术护理1.护理time2') then nullif(trim(sh.item_value), '/') end) as hltime2,
           max(case when sh.item_name in ('手术护理.护理time7', '手术护理1.护理time7') then nullif(trim(sh.item_value), '/') end) as hltime7,
           max(case when sh.item_name in ('手术护理.护理time8', '手术护理1.护理time8') then nullif(trim(sh.item_value), '/') end) as hltime8,

           max(case when sh.item_name in ('手术护理.检验', '手术护理1.检验') then nullif(trim(sh.item_value), '/') end) as jianyan1,
           max(case when sh.item_name in ('手术护理.检验2', '手术护理1.检验2') then nullif(trim(sh.item_value), '/') end) as jianyan2,

           max(case when sh.item_name in ('手术护理.其他仪器1', '手术护理1.其他仪器1') then nullif(trim(sh.item_value), '/') end) as qita_yiqi1,
           max(case when sh.item_name in ('手术护理.其他仪器2', '手术护理1.其他仪器2') then nullif(trim(sh.item_value), '/') end) as qita_yiqi2,

           max(case when sh.item_name in ('手术护理.输液1', '手术护理1.输液1') then nullif(trim(sh.item_value), '/') end) as shuye1,
           max(case when sh.item_name in ('手术护理.输液2', '手术护理1.输液2') then nullif(trim(sh.item_value), '/') end) as shuye2,
           max(case when sh.item_name in ('手术护理.输液人1', '手术护理1.输液人1') then nullif(trim(sh.item_value), '/') end) as shuye_ren1,
           max(case when sh.item_name in ('手术护理.输液人2', '手术护理1.输液人2') then nullif(trim(sh.item_value), '/') end) as shuye_ren2,

           max(case when sh.item_name in ('手术护理.术中保2', '手术护理1.术中保2') then nullif(trim(sh.item_value), '/') end) as baowen2,
           max(case when sh.item_name in ('手术护理.术中保温1', '手术护理1.术中保温1') then nullif(trim(sh.item_value), '/') end) as baowen1,
           max(case when sh.item_name in ('手术护理.术中保温13', '手术护理1.术中保温13') then nullif(trim(sh.item_value), '/') end) as baowen13,
           max(case when sh.item_name in ('手术护理.术中保温144', '手术护理1.术中保温144') then nullif(trim(sh.item_value), '/') end) as baowen144,

           max(case when sh.item_name in ('手术护理.血型种类', '手术护理1.血型种类') then nullif(trim(sh.item_value), '/') end) as xuexing,

           max(case when sh.item_name in ('手术护理.影像', '手术护理1.影像') then nullif(trim(sh.item_value), '/') end) as yingxiang1,
           max(case when sh.item_name in ('手术护理.影像2', '手术护理1.影像2') then nullif(trim(sh.item_value), '/') end) as yingxiang2,

           max(case when sh.item_name in ('手术护理.转归1', '手术护理1.转归1') then nullif(trim(sh.item_value), '/') end) as zhuan_gui

      from sm.med_custom_data sh
     where sh.item_name like '手术护理.%'
        or sh.item_name like '护理记录.%'
        or sh.item_name like '手术护理1.%'
        or sh.item_name like '护理记录1.%'
        or sh.item_name like '护理单病毒加减%'
        or sh.item_name like '护理单1病毒加减%'
     group by sh.patient_id, sh.visit_id, sh.oper_id
) nurse
  on nurse.patient_id = a.patient_id
 and nurse.visit_id   = a.visit_id
 and nurse.oper_id    = a.oper_id

where nvl(to_char(a.oper_status), '0') <> '0'
  and a1.patient_id is not null
  and nurse.patient_id is not null
  and p.discharge_date_time >= to_date('2021-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss')
  and p.discharge_date_time <  to_date('2025-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss')
  and nvl(a.start_date_time, a.scheduled_date_time) is not null
  and nvl(a.end_date_time, nvl(a.done_date_time, a.anes_end_time)) is not null
