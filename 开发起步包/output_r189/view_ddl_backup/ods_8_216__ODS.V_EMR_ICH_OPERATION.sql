
  CREATE OR REPLACE FORCE VIEW "ODS"."V_EMR_ICH_OPERATION" ("ID", "ICH_ID", "SN", "OPERATION_CODE", "OPERATION_NAME", "OPS_TYPE", "OPERATION_DATE", "ANAESTHESIA_CODE", "ANAESTHESIA_NAME", "HEALING_GRADE_CODE", "HEALING_GRADE_NAME", "OPERATION_GRADE", "OPERATION_BP_NAME", "OPERATION_BP_CODE", "INCISION_CATEGORY", "SURGEON_CODE", "SURGEON_NAME", "ASSISTANT_FIR_CODE", "ASSISTANT_FIR_NAME", "ASSISTANT_SED_CODE", "ASSISTANT_SED_NAME", "ANESTHESIA_DOC_CODE", "ANESTHESIA_DOC_NAME", "CREATED_AT", "DISTRICT_CODE", "EXCHANGE_TYPE", "SYSTEM_TIME", "OPERATION_NATURE_CODE", "OPERATION_AGAIN_CODE", "ELECTIVE_EMERGENCY", "ORG_CODE", "ORG_NAME", "SFWRJSS", "SFWRJCZ", "SFFJHZSS", "ADMISSION_ID", "NAME", "SEX_CODE", "ID_NUM") AS 
  select
       cast(
           substrb(
               '49557032X' || '|' || o.patient_id || '|' || o.visit_id || '|' || o.operation_no,
               1,
               100
           ) as varchar2(100)
       ) as ID,--内码 是 主键；增加手术序号，避免同一次住院多台手术ID重复

       cast(
           substrb(
               '49557032X' || '|' || o.patient_id || '|' || o.visit_id,
               1,
               100
           ) as varchar2(100)
       ) as ICH_ID,--病案首页内码 是；必须与EMR_ICH.ID保持一致

       o.operation_no as SN,--序号；取手术序号

       cast(
           substrb(
               nvl(
                   nvl(op_icd_code.国标编码, op_icd_name.国标编码),
                   to_char(o.operation_code)
               ),
               1,
               12
           ) as varchar2(12)
       ) as OPERATION_CODE,--手术/操作-代码 是；优先按手术编码映射，再按手术名称映射，最后保留原手术编码

       cast(
           substrb(
               nvl(
                   nvl(op_icd_code.国标名称, op_icd_name.国标名称),
                   nvl(to_char(o.operation_desc_doc), to_char(o.operation_desc))
               ),
               1,
               80
           ) as varchar2(80)
       ) as OPERATION_NAME,--手术/操作-名称 是；优先标准名称，其次医生自定义名/手术名称

     cast(
    case
        -- 如果字典属性里能识别内镜，优先归为5
        when instr(
                 nvl(
                     (
                         select max(to_char(d.operation_type))
                           from his.operation_dict d
                          where nvl(d.stop_flag, 0) = 0
                            and to_char(d.operation_code) = to_char(o.operation_code)
                     ),
                     ' '
                 ),
                 '内镜'
             ) > 0
        then '5'

        -- 0 手术 -> 1 手术
        when (
                select max(to_char(d.operation_indicator))
                  from his.operation_dict d
                 where nvl(d.stop_flag, 0) = 0
                   and to_char(d.operation_code) = to_char(o.operation_code)
             ) = '0'
        then '1'

        -- 3 介入治疗 -> 2 介入手术
        when (
                select max(to_char(d.operation_indicator))
                  from his.operation_dict d
                 where nvl(d.stop_flag, 0) = 0
                   and to_char(d.operation_code) = to_char(o.operation_code)
             ) = '3'
        then '2'

        -- 1 治疗性操作 -> 3 治疗性操作
        when (
                select max(to_char(d.operation_indicator))
                  from his.operation_dict d
                 where nvl(d.stop_flag, 0) = 0
                   and to_char(d.operation_code) = to_char(o.operation_code)
             ) = '1'
        then '3'

        -- 2 诊断性操作 -> 4 诊断性操作
        when (
                select max(to_char(d.operation_indicator))
                  from his.operation_dict d
                 where nvl(d.stop_flag, 0) = 0
                   and to_char(d.operation_code) = to_char(o.operation_code)
             ) = '2'
        then '4'

        else '9'
    end as varchar2(10)
) as OPS_TYPE,--手术类型；根据HIS.OPERATION_DICT.OPERATION_INDICATOR转换



       cast(o.operating_date as date) as OPERATION_DATE,--手术操作日期 是；取手术开始日期

       cast(
           substrb(
               nvl(nvl(anes_code_dict.国标编码, anes_name_dict.国标编码), '9'),
               1,
               2
           ) as varchar2(2)
       ) as ANAESTHESIA_CODE,--麻醉方法代码 是；优先按麻醉方法代码/名称映射

       cast(
           substrb(
               nvl(nvl(anes_code_dict.国标名称, anes_name_dict.国标名称), '其他麻醉方法'),
               1,
               50
           ) as varchar2(50)
       ) as ANAESTHESIA_NAME,--麻醉方法 是

      cast(
    case
        -- HEAL本身是愈合等级
        when regexp_replace(trim(to_char(o.heal)), '[[:space:]]+', '') in ('甲', '1') then '1'
        when regexp_replace(trim(to_char(o.heal)), '[[:space:]]+', '') in ('乙', '2') then '2'
        when regexp_replace(trim(to_char(o.heal)), '[[:space:]]+', '') in ('丙', '3') then '3'
        when regexp_replace(trim(to_char(o.heal)), '[[:space:]]+', '') in ('其他', '其', '4', '5', '未知', '-', '—', '0') then '4'

        -- HEAL被误填为Ⅰ/Ⅱ/Ⅲ时，不按甲乙丙处理；尝试从WOUND_GRADE里找甲乙丙
        when regexp_replace(trim(to_char(o.wound_grade)), '[[:space:]]+', '') = '甲' then '1'
        when regexp_replace(trim(to_char(o.wound_grade)), '[[:space:]]+', '') = '乙' then '2'
        when regexp_replace(trim(to_char(o.wound_grade)), '[[:space:]]+', '') = '丙' then '3'
        when regexp_replace(trim(to_char(o.wound_grade)), '[[:space:]]+', '') in ('其他', '其') then '4'

        -- 其他空值、Ⅰ/Ⅱ/Ⅲ/I/II/III等均视为愈合情况不确定
        else '4'
    end as varchar2(3)
) as HEALING_GRADE_CODE,--切口愈合等级代码 是；1甲、2乙、3丙、4其他；HEAL混入切口类别时不误转

cast(
    substrb(
        case
            when regexp_replace(trim(to_char(o.heal)), '[[:space:]]+', '') in ('甲', '1') then '甲'
            when regexp_replace(trim(to_char(o.heal)), '[[:space:]]+', '') in ('乙', '2') then '乙'
            when regexp_replace(trim(to_char(o.heal)), '[[:space:]]+', '') in ('丙', '3') then '丙'
            when regexp_replace(trim(to_char(o.heal)), '[[:space:]]+', '') in ('其他', '其', '4', '5', '未知', '-', '—', '0') then '其他'

            when regexp_replace(trim(to_char(o.wound_grade)), '[[:space:]]+', '') = '甲' then '甲'
            when regexp_replace(trim(to_char(o.wound_grade)), '[[:space:]]+', '') = '乙' then '乙'
            when regexp_replace(trim(to_char(o.wound_grade)), '[[:space:]]+', '') = '丙' then '丙'
            when regexp_replace(trim(to_char(o.wound_grade)), '[[:space:]]+', '') in ('其他', '其') then '其他'

            else '其他'
        end,
        1,
        50
    ) as varchar2(50)
) as HEALING_GRADE_NAME,--切口愈合等级；甲/乙/丙/其他

     nvl( cast(
    to_number(
        regexp_substr(
            trim(
                coalesce(
                    -- 1. 优先按手术编码匹配手术字典等级
                    (
                        select max(to_char(d.operation_scale))
                          from his.operation_dict d
                         where nvl(d.stop_flag, 0) = 0
                           and to_char(d.operation_code) = to_char(o.operation_code)
                    ),

                    -- 2. 编码匹配不到时，按手术名称匹配手术字典等级
                    (
                        select max(to_char(d.operation_scale))
                          from his.operation_dict d
                         where nvl(d.stop_flag, 0) = 0
                           and to_char(d.operation_name) =
                               coalesce(to_char(o.operation_desc_doc), to_char(o.operation_desc))
                    ),

                    -- 3. 字典仍匹配不到时，保留HIS.OPERATION原手术等级
                    to_char(o.operation_scale)
                )
            ),
            '^[0-9]+$'
        )
    ) as number
) ,'0')as OPERATION_GRADE,--手术级别代码 是；不改FROM，优先手术字典等级，其次HIS.OPERATION手术等级

       cast(null as varchar2(50)) as OPERATION_BP_NAME,--手术/操作-目标部位名称；暂无明确来源

       cast(null as varchar2(20)) as OPERATION_BP_CODE,--手术/操作-目标部位代码；暂无明确来源

       cast(
           substrb(
               nvl(incision_dict.国标编码, '1'),
               1,
               1
           ) as char(1)
       ) as INCISION_CATEGORY,--手术切口类别代码；来源o.WOUND_GRADE

       cast(
           substrb(
               coalesce(surgeon_emp.id_no, surgeon_name.id_no),
               1,
               32
           ) as varchar2(32)
       ) as SURGEON_CODE,--手术者代码；标准说明为身份证号码，优先取人员字典身份证号

       cast(
           substrb(
               coalesce(surgeon_emp.name, surgeon_name.name, to_char(o.operator), '-'),
               1,
               50
           ) as varchar2(50)
       ) as SURGEON_NAME,--手术者姓名 是

       cast(
           substrb(
               coalesce(first_emp.id_no, first_name.id_no),
               1,
               32
           ) as varchar2(32)
       ) as ASSISTANT_FIR_CODE,--Ⅰ助代码；标准说明为身份证号码

       cast(
           substrb(
               coalesce(first_emp.name, first_name.name, to_char(o.first_assistant)),
               1,
               50
           ) as varchar2(50)
       ) as ASSISTANT_FIR_NAME,--Ⅰ助姓名

       cast(
           substrb(
               coalesce(second_emp.id_no, second_name.id_no),
               1,
               32
           ) as varchar2(32)
       ) as ASSISTANT_SED_CODE,--Ⅱ助代码；标准说明为身份证号码

       cast(
           substrb(
               coalesce(second_emp.name, second_name.name, to_char(o.second_assistant)),
               1,
               50
           ) as varchar2(50)
       ) as ASSISTANT_SED_NAME,--Ⅱ助姓名

       cast(
           substrb(
               coalesce(anes_emp.id_no, anes_name.id_no),
               1,
               32
           ) as varchar2(32)
       ) as ANESTHESIA_DOC_CODE,--麻醉医师代码；标准说明为身份证号码

       cast(
           substrb(
               coalesce(anes_emp.name, anes_name.name, to_char(o.anesthesia_doctor)),
               1,
               50
           ) as varchar2(50)
       ) as ANESTHESIA_DOC_NAME,--麻醉医师姓名

       cast(nvl(o.enter_date, o.operating_date) as timestamp) as CREATED_AT,--创建时间；优先取ENTER_DATE，空时取手术日期

       cast('370104' as varchar2(6)) as DISTRICT_CODE,--所属行政区划 是

       cast('ADDHIS' as varchar2(10)) as EXCHANGE_TYPE,--交换类型 是

       cast(systimestamp as timestamp) as SYSTEM_TIME,--数据上传时间戳 是

cast(
    case
        when to_char(o.operation_emer_indicator) = '2' then '2'
        when to_char(o.operation_emer_indicator) = '1' then '1'
        else '1'
    end as char(1)
) as OPERATION_NATURE_CODE,--手术性质代码；LC003.006：1择期，2急症，来源OPERATION_EMER_INDICATOR，空值默认择期
       cast(null as char(1)) as OPERATION_AGAIN_CODE,--再次手术代码；暂无明确来源

      cast(
    case
        when to_char(o.operation_emer_indicator) = '2' then '2'
        when to_char(o.operation_emer_indicator) = '1' then '1'
        else '1'
    end as varchar2(1)
) as ELECTIVE_EMERGENCY,--择期/急症手术代码；1择期，2急症，空值默认择期

       cast('49557032X' as varchar2(32)) as ORG_CODE,--医院组织机构代码 是

       cast('山东省第二人民医院' as varchar2(70)) as ORG_NAME,--医院名称 是

       cast(
           case
               when to_char(o.primary_day) = '1' then '1'
               else '0'
           end as char(1)
       ) as SFWRJSS,--是否为日间手术 是；0否1是

       cast(
           case
               when to_char(o.oper_day) = '1' then '1'
               else '0'
           end as char(1)
       ) as SFWRJCZ,--是否为日间操作 是；0否1是

       cast(
           case
               when to_char(o.oper_plan) = '1' then '1'
               else '0'
           end as char(1)
       ) as SFFJHZSS,--是否非计划再手术 是；0否1是

       cast(
           substrb(
               o.patient_id || '|' || o.visit_id,
               1,
               20
           ) as varchar2(20)
       ) as ADMISSION_ID,--本次住院标识号 是；按标准长度20

       cast(substrb(nvl(to_char(pmi.name), '-'), 1, 50) as varchar2(50)) as NAME,--患者姓名 是

       cast(
           decode(pmi.sex, '男', '1', '女', '2', '未知', '0', '9')
           as char(1)
       ) as SEX_CODE,--患者性别代码 是

       cast(
           substrb(
               nvl(to_char(pmi.id_no), '000000000000000000'),
               1,
               18
           ) as varchar2(18)
       ) as ID_NUM--患者身份证件号码 是

from his.operation o

join his.pat_visit pv
  on pv.patient_id = o.patient_id
 and pv.visit_id = o.visit_id

left join his.pat_master_index pmi
  on pmi.patient_id = o.patient_id

left join (
    select to_char(院标编码) as 院标编码,
           max(to_char(国标编码)) as 国标编码,
           max(to_char(国标名称)) as 国标名称
      from cda.cda_dictionary
     where 字典名称 = 'ICD-9手术编码'
     group by to_char(院标编码)
) op_icd_code
  on op_icd_code.院标编码 = to_char(o.operation_code)

left join (
    select to_char(院标名称) as 院标名称,
           max(to_char(国标编码)) as 国标编码,
           max(to_char(国标名称)) as 国标名称
      from cda.cda_dictionary
     where 字典名称 = 'ICD-9手术编码'
     group by to_char(院标名称)
) op_icd_name
  on op_icd_name.院标名称 = to_char(o.operation_desc)


left join (
    select to_char(院标编码) as 院标编码,
           max(to_char(国标编码)) as 国标编码,
           max(to_char(国标名称)) as 国标名称
      from cda.cda_dictionary
     where 字典名称 = '麻醉方法代码表'
     group by to_char(院标编码)
) anes_code_dict
  on anes_code_dict.院标编码 = to_char(o.anaesthesia_method)

left join (
    select to_char(院标名称) as 院标名称,
           max(to_char(国标编码)) as 国标编码,
           max(to_char(国标名称)) as 国标名称
      from cda.cda_dictionary
     where 字典名称 = '麻醉方法代码表'
     group by to_char(院标名称)
) anes_name_dict
  on anes_name_dict.院标名称 = to_char(o.anaesthesia_method)



left join (
    select to_char(院标编码) as 院标编码,
           max(to_char(国标编码)) as 国标编码,
           max(to_char(国标名称)) as 国标名称
      from cda.cda_dictionary
     where 字典名称 = '手术切口类别代码'
     group by to_char(院标编码)
) incision_dict
  on incision_dict.院标编码 = to_char(o.wound_grade)

left join (
    select to_char(emp_no) as emp_no,
           max(to_char(name)) as name,
           max(to_char(id_no)) as id_no
      from his.staff_dict
     group by to_char(emp_no)
) surgeon_emp
  on surgeon_emp.emp_no = to_char(o.operator)

left join (
    select to_char(name) as name,
           max(to_char(emp_no)) as emp_no,
           max(to_char(id_no)) as id_no
      from his.staff_dict
     where name is not null
     group by to_char(name)
) surgeon_name
  on surgeon_name.name = to_char(o.operator)

left join (
    select to_char(emp_no) as emp_no,
           max(to_char(name)) as name,
           max(to_char(id_no)) as id_no
      from his.staff_dict
     group by to_char(emp_no)
) first_emp
  on first_emp.emp_no = to_char(o.first_assistant)

left join (
    select to_char(name) as name,
           max(to_char(emp_no)) as emp_no,
           max(to_char(id_no)) as id_no
      from his.staff_dict
     where name is not null
     group by to_char(name)
) first_name
  on first_name.name = to_char(o.first_assistant)

left join (
    select to_char(emp_no) as emp_no,
           max(to_char(name)) as name,
           max(to_char(id_no)) as id_no
      from his.staff_dict
     group by to_char(emp_no)
) second_emp
  on second_emp.emp_no = to_char(o.second_assistant)

left join (
    select to_char(name) as name,
           max(to_char(emp_no)) as emp_no,
           max(to_char(id_no)) as id_no
      from his.staff_dict
     where name is not null
     group by to_char(name)
) second_name
  on second_name.name = to_char(o.second_assistant)

left join (
    select to_char(emp_no) as emp_no,
           max(to_char(name)) as name,
           max(to_char(id_no)) as id_no
      from his.staff_dict
     group by to_char(emp_no)
) anes_emp
  on anes_emp.emp_no = to_char(o.anesthesia_doctor)

left join (
    select to_char(name) as name,
           max(to_char(emp_no)) as emp_no,
           max(to_char(id_no)) as id_no
      from his.staff_dict
     where name is not null
     group by to_char(name)
) anes_name
  on anes_name.name = to_char(o.anesthesia_doctor)

where pv.discharge_date_time >= date '2021-01-01'
  and pv.discharge_date_time <  date '2025-01-01'
