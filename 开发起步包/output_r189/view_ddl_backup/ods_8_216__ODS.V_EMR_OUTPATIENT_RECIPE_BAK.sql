
  CREATE OR REPLACE FORCE VIEW "ODS"."V_EMR_OUTPATIENT_RECIPE_BAK" ("ID", "OR_ID", "ORG_CODE", "ORG_NAME", "SN", "ITEM_NUM", "ITEM_TYPE_CODE", "ITEM_TYPE_NAME", "DRUG_CLASS_CODE", "DRUG_CLASS_NAME", "DRUG_CODE", "DRUG_COMMON_NAME", "DRUG_NAME", "SPEC", "UNIT", "DRUG_DOSE", "ONCE_AMOUNT", "DOSAGE_UNIT", "JL_UNIT", "QUANTITY", "HERB_NUM", "UNIT_DOSE", "ORDER_DOSAGE", "ALL_AMOUNT", "DRUG_ROUTE_CODE", "DRUG_ROUTE_NAME", "DRUG_FREQUENCY_CODE", "DRUG_FREQUENCY_NAME", "STATUS_CODE", "STATUS_NAME", "CANCEL_REASON", "CANCEL_TIME", "DOCTOR_CODE", "DOCTOR_NAME", "DRUG_FORM_CODE", "DRUG_FORM_NAME", "GROUP_NO", "SKIN_TEST_RESULT", "IS_ESSENTIAL", "ESSENTIL_GRADE", "IS_ANTI", "ANTI_USE_GRADE_CODE", "ANTI_USE_GRADE_NAME", "IF_YF", "DISTRICT_CODE", "CREATED_AT", "EXCHANGE_TYPE", "SYSTEM_TIME", "DRUG_WAY_CD", "DRUG_WAY_NAME", "DURATION_TIME", "DRUG_AMOUNT", "TCM_DECOCTION_METHOD", "MEDICATION_METHOD", "DRUG_PRICE", "CH_DRUG_NOTES", "OUTPATIENT_NUM", "NAME", "SEX_CODE", "ID_NUM", "ODR_TYPE", "ORDER_ITEM_CODE", "ORDER_ITEM_NAME", "ORDER_CATEGORY_CODE", "ORDER_CATEGORY_NAME", "ORDER_NUM_NAME", "ORDER_STATUS", "DTCODE", "NHSA_STANDARD_CODE", "DOSAGE", "DOSAGE_UNIT_NAME", "DRUG_ALL_UNIT", "DRUG_ALL_NUM", "ADMINISTRATION_DAYS", "DRUG_ADMINISTRATION_ROUTE", "IS_EXTERNAL_PRES") AS 
  select substr(
           to_char(a.presc_date, 'yyyymmddhh24miss')
           || '|' || cast(a.presc_no as varchar2(50))
           || '|' || cast(t.item_no as varchar2(50)),
           1,
           100
       ) as ID, -- 内码：处方日期+处方号+处方项目序号

       substr(
           to_char(a.presc_date, 'yyyymmddhh24miss')
           || '|' || cast(a.presc_no as varchar2(50)),
           1,
           100
       ) as OR_ID, -- 门诊处方内码，必须与处方主表ID保持一致

       '49557032X' as ORG_CODE, -- 医院编码

       '山东省第二人民医院' as ORG_NAME, -- 医院名称

       t.item_no as SN, -- 序号

       substr(cast(t.item_no as varchar2(20)), 1, 20)
           as ITEM_NUM, -- 处方项编号


case
    /* 中药饮片必须优先判断 */
    when dd.drug_indicator = 2
     and (
            regexp_like(nvl(t.drug_name, dd.drug_name), '饮片')
         or regexp_like(nvl(dd.drug_form, '-'), '饮片')
         )
    then '4'

    /* 西药 */
    when dd.drug_indicator = 1 then '2'

    /* 中草药，但不属于饮片 */
    when dd.drug_indicator = 2 then '3'

    /* 中成药归入平台“中药” */
    when dd.drug_indicator = 3 then '1'

    /* 辅料、试剂、其他暂归为非药品 */
    when dd.drug_indicator in (5, 6, 9) then '5'

    /* 药品字典关联不到时，使用处方类别兜底 */
    when a.presc_type = '0' then '2'
    when a.presc_type = '1' then '1'

    else '5'
end as ITEM_TYPE_CODE, -- 处方项类别代码

case
    when dd.drug_indicator = 2
     and (
            regexp_like(nvl(t.drug_name, dd.drug_name), '饮片')
         or regexp_like(nvl(dd.drug_form, '-'), '饮片')
         )
    then '中药饮片'

    when dd.drug_indicator = 1 then '西药'
    when dd.drug_indicator = 2 then '中草药'
    when dd.drug_indicator = 3 then '中药'
    when dd.drug_indicator in (5, 6, 9) then '非药品'

    when a.presc_type = '0' then '西药'
    when a.presc_type = '1' then '中药'

    else '非药品'
end as ITEM_TYPE_NAME, -- 处方项类别名称
nvl(pharm_map.value_domain_code, '99') as DRUG_CLASS_CODE, -- 药品分类代码

nvl(pharm_map.value_domain_name, '其它化学药物') as DRUG_CLASS_NAME, -- 药品分类名称

nvl(std.ypid_code, t.drug_code) as DRUG_CODE, -- 药物编码

nvl(std.product_name, t.drug_name) as DRUG_COMMON_NAME, -- 药物通用名

       substr(t.drug_name, 1, 100)
           as DRUG_NAME, -- 药物名称

       substr(
           nvl(t.package_spec, t.drug_spec),
           1,
           100
       ) as SPEC, -- 规格

       substr(
           nvl(t.package_units, dd.units),
           1,
           6
       ) as UNIT, -- 单位

       cast(null as number(12, 2))
           as DRUG_DOSE, -- 药物日剂量，暂无可靠来源

       cast(
           round(t.dosage_each, 2)
           as number(12, 2)
       ) as ONCE_AMOUNT, -- 药物使用单次量

     case
    when lower(trim(t.dosage_units)) in ('g', '克') then '1'
    when lower(trim(t.dosage_units)) in ('mg', '毫克') then '2'
    when lower(trim(t.dosage_units)) in ('μg', 'ug', 'mcg', '微克') then '3'
    when lower(trim(t.dosage_units)) in ('l', '升') then '5'
    when lower(trim(t.dosage_units)) in ('ml', '毫升') then '6'
    when upper(trim(t.dosage_units)) in ('IU', '万IU', 'AXAIU') then '7'
    when upper(trim(t.dosage_units)) in ('U', '万U')
      or trim(t.dosage_units) in ('单位', '万u', 'u') then '8'
    when regexp_like(lower(trim(t.dosage_units)), '^g(口服|po|qd|bid|tid|qid).*') then '1'
    when regexp_like(lower(trim(t.dosage_units)), '^mg(口服|po|qd|bid|tid|qid).*') then '2'
    when regexp_like(lower(trim(t.dosage_units)), '^ml(口服|po|qd|bid|tid|qid).*') then '6'
    else cast('-' as varchar2(6))
end as DOSAGE_UNIT, -- 剂量单位代码
    case
    when lower(trim(t.dosage_units)) in ('g', '克') then 'g'
    when lower(trim(t.dosage_units)) in ('mg', '毫克') then 'mg'
    when lower(trim(t.dosage_units)) in ('μg', 'ug', 'mcg', '微克') then 'μg'
    when lower(trim(t.dosage_units)) in ('l', '升') then 'L'
    when lower(trim(t.dosage_units)) in ('ml', '毫升') then 'ml'
    when upper(trim(t.dosage_units)) in ('IU', '万IU', 'AXAIU') then 'IU'
    when upper(trim(t.dosage_units)) in ('U', '万U')
      or trim(t.dosage_units) in ('单位', '万u', 'u') then 'U'
    when regexp_like(lower(trim(t.dosage_units)), '^g(口服|po|qd|bid|tid|qid).*') then 'g'
    when regexp_like(lower(trim(t.dosage_units)), '^mg(口服|po|qd|bid|tid|qid).*') then 'mg'
    when regexp_like(lower(trim(t.dosage_units)), '^ml(口服|po|qd|bid|tid|qid).*') then 'ml'
    else cast(null as varchar2(8))
end as JL_UNIT, -- 剂量单位名称

       cast(
           round(
               case
                   when nvl(t.flag, a.flag) = 2
                       then -abs(t.quantity)
                   else t.quantity
               end,
               2
           ) as number(8, 2)
       ) as QUANTITY, -- 数量，退药时为负数


       case
           when regexp_like(t.drug_name, '饮片')
             or dd.drug_indicator = 2
           then nvl(a.repetition, 1)
           else cast(null as number)
       end as HERB_NUM, -- 草药付数

       cast(
           round(dd.dose_per_unit, 2)
           as number(9, 2)
       ) as UNIT_DOSE, -- 单位剂量

       cast(
           round(t.dosage_each, 2)
           as number(8, 2)
       ) as ORDER_DOSAGE, -- 医嘱用量

       cast(
           round(
               case
                   when nvl(t.flag, a.flag) = 2
                       then -abs(t.quantity)
                   else t.quantity
               end,
               2
           ) as number(12, 2)
       ) as ALL_AMOUNT, -- 药物使用总量

     substr(route_map.standard_code, 1, 4) as DRUG_ROUTE_CODE, -- 用药方式代码

substr(nvl(route_map.standard_name, t.administration), 1, 50) as DRUG_ROUTE_NAME, -- 用药方式
case
    /* 标准频次代码本身 */
    when lower(trim(t.frequency)) = 'bid' then 'bid'
    when lower(trim(t.frequency)) = 'bidac' then 'bidac'
    when lower(trim(t.frequency)) = 'tidac' then 'tidac'
    when lower(trim(t.frequency)) = 'biw' then 'biw'
    when lower(trim(t.frequency)) = 'hs' then 'hs'
    when lower(trim(t.frequency)) = 'prn' then 'prn'
    when lower(trim(t.frequency)) = 'q12h' then 'q12h'
    when lower(trim(t.frequency)) = 'q12h1' then 'q12h1'
    when lower(trim(t.frequency)) = 'q12h2' then 'q12h2'
    when lower(trim(t.frequency)) = 'q1h' then 'q1h'
    when lower(trim(t.frequency)) = 'q2h' then 'q2h'
    when lower(trim(t.frequency)) = 'q3h' then 'q3h'
    when lower(trim(t.frequency)) = 'q4h' then 'q4h'
    when lower(trim(t.frequency)) = 'q6h' then 'q6h'
    when lower(trim(t.frequency)) = 'q6h1' then 'q6h1'
    when lower(trim(t.frequency)) = 'q6h2' then 'q6h2'
    when lower(trim(t.frequency)) = 'q8h' then 'q8h'
    when lower(trim(t.frequency)) = 'q8h1' then 'q8h1'
    when lower(trim(t.frequency)) = 'q8h2' then 'q8h2'
    when lower(trim(t.frequency)) = 'qd' then 'qd'
    when lower(trim(t.frequency)) = 'qid' then 'qid'
    when lower(trim(t.frequency)) = 'qm' then 'qm'
    when lower(trim(t.frequency)) = 'qn' then 'qn'
    when lower(trim(t.frequency)) = 'qod' then 'qod'
    when lower(trim(t.frequency)) = 'qw' then 'qw'
    when lower(trim(t.frequency)) = 'st' then 'st'
    when lower(trim(t.frequency)) = 'tid' then 'tid'

    /* 院内中文/特殊写法转换 */
    when trim(t.frequency) in ('睡前') then 'hs'
    when trim(t.frequency) in ('必要时') then 'prn'
    when trim(t.frequency) in ('立即') then 'st'

    when trim(t.frequency) in ('三餐前') then 'tidac'
    when trim(t.frequency) in ('三餐后') then 'tid'

    when trim(t.frequency) in ('早餐前', '午餐前', '晚餐前', '空腹', '下午', '术前', '术晨')
      then 'qd'

    when trim(t.frequency) in (
             '1/早餐前15''',
             '1/早餐前30''',
             '1/午餐前15''',
             '1/午餐前30''',
             '1/晚餐前15''',
             '1/晚餐前30''',
             '术前30’'
         )
      then 'qd'

    when trim(t.frequency) in ('1/半小时') then 'q1h'
    when trim(t.frequency) in ('1/小时') then 'q1h'
    when trim(t.frequency) in ('1/2小时') then 'q2h'
    when trim(t.frequency) in ('1/3小时') then 'q3h'
    when trim(t.frequency) in ('1/4小时') then 'q4h'

    when trim(t.frequency) in ('1/2日') then 'q12h'
    when trim(t.frequency) in ('1/3日') then 'q8h'
    when trim(t.frequency) in ('5/日', '7/日', '10/周', '5/周', '3/5日', '4/5日', 'q72h', 'q2w', 'q4w', '6M', 'tiw', 'wf', 'zwf', 'zf')
      then 'oth'

    when trim(t.frequency) in ('三餐前三餐后睡前') then 'oth'

    else 'oth'
end as DRUG_FREQUENCY_CODE, -- 执行频率代码

case
    when lower(trim(t.frequency)) = 'bid' then '每天二次'
    when lower(trim(t.frequency)) = 'bidac' then '每天二次，餐前服用'
    when lower(trim(t.frequency)) = 'tidac' then '每天三次，餐前服用'
    when lower(trim(t.frequency)) = 'biw' then '每周二次'
    when lower(trim(t.frequency)) = 'hs' then '睡前一次'
    when lower(trim(t.frequency)) = 'prn' then '必要时一次'
    when lower(trim(t.frequency)) = 'q12h' then '每十二小时一次'
    when lower(trim(t.frequency)) = 'q12h1' then '每十二小时一次（8）'
    when lower(trim(t.frequency)) = 'q12h2' then '每十二小时一次（20）'
    when lower(trim(t.frequency)) = 'q1h' then '每一小时一次'
    when lower(trim(t.frequency)) = 'q2h' then '每二小时一次'
    when lower(trim(t.frequency)) = 'q3h' then '每三小时一次'
    when lower(trim(t.frequency)) = 'q4h' then '每四小时一次'
    when lower(trim(t.frequency)) = 'q6h' then '每六小时一次'
    when lower(trim(t.frequency)) = 'q6h1' then '每六小时一次（8,20）'
    when lower(trim(t.frequency)) = 'q6h2' then '每六小时二次（14,2）'
    when lower(trim(t.frequency)) = 'q8h' then '每八小时一次'
    when lower(trim(t.frequency)) = 'q8h1' then '每八小时一次（8,24）'
    when lower(trim(t.frequency)) = 'q8h2' then '每八小时一次（16）'
    when lower(trim(t.frequency)) = 'qd' then '每天一次'
    when lower(trim(t.frequency)) = 'qid' then '每天四次'
    when lower(trim(t.frequency)) = 'qm' then '每天早上一次'
    when lower(trim(t.frequency)) = 'qn' then '每天晚上一次'
    when lower(trim(t.frequency)) = 'qod' then '隔日一次'
    when lower(trim(t.frequency)) = 'qw' then '每周一次'
    when lower(trim(t.frequency)) = 'st' then '立即'
    when lower(trim(t.frequency)) = 'tid' then '每天三次'

    when trim(t.frequency) in ('睡前') then '睡前一次'
    when trim(t.frequency) in ('必要时') then '必要时一次'
    when trim(t.frequency) in ('立即') then '立即'

    when trim(t.frequency) in ('三餐前') then '每天三次，餐前服用'
    when trim(t.frequency) in ('三餐后') then '每天三次'

    when trim(t.frequency) in ('早餐前', '午餐前', '晚餐前', '空腹', '下午', '术前', '术晨')
      then '每天一次'

    when trim(t.frequency) in (
             '1/早餐前15''',
             '1/早餐前30''',
             '1/午餐前15''',
             '1/午餐前30''',
             '1/晚餐前15''',
             '1/晚餐前30''',
             '术前30’'
         )
      then '每天一次'

    when trim(t.frequency) in ('1/半小时', '1/小时') then '每一小时一次'
    when trim(t.frequency) in ('1/2小时') then '每二小时一次'
    when trim(t.frequency) in ('1/3小时') then '每三小时一次'
    when trim(t.frequency) in ('1/4小时') then '每四小时一次'

    when trim(t.frequency) in ('1/2日') then '每十二小时一次'
    when trim(t.frequency) in ('1/3日') then '每八小时一次'

    else '其它'
end as DRUG_FREQUENCY_NAME, -- 执行频率

       case
           when nvl(t.flag, a.flag) = 2 then '2'
           else '1'
       end as STATUS_CODE, -- 状态代码

       case
           when nvl(t.flag, a.flag) = 2 then '退药'
           else '正常'
       end as STATUS_NAME, -- 状态名称

       case
           when nvl(t.flag, a.flag) = 2 then '退药'
           else cast(null as varchar2(100))
       end as CANCEL_REASON, -- 取消原因

       cast(null as date)
           as CANCEL_TIME, -- 取消时间，暂无可靠字段

       cast(null as varchar2(32))
           as DOCTOR_CODE, -- 取消医生代码

       cast(null as varchar2(50))
           as DOCTOR_NAME, -- 取消医生姓名

   nvl(
    (
        select max(v.value_domain_code)
          from CDA_VALUE_DOMAIN_MAP v
         where v.category_code = 'CV08.50.002'
           and v.hospital_code = m.dose_model_code
    ),
    case
        when regexp_like(nvl(t.drug_name, dd.drug_name), '肠溶片') then '04'
        when regexp_like(nvl(t.drug_name, dd.drug_name), '缓释片|控释片') then '05'
        when regexp_like(nvl(t.drug_name, dd.drug_name), '咀嚼片') then '03'
        when regexp_like(nvl(t.drug_name, dd.drug_name), '分散片') then '12'
        when regexp_like(nvl(t.drug_name, dd.drug_name), '片') then '01'
        when regexp_like(nvl(t.drug_name, dd.drug_name), '粉针|冻干') then '15'
        when regexp_like(nvl(t.drug_name, dd.drug_name), '注射液|胰岛素') then '16'
        when regexp_like(nvl(t.drug_name, dd.drug_name), '缓释胶囊|控释胶囊') then '22'
        when regexp_like(nvl(t.drug_name, dd.drug_name), '胶囊') then '19'
        when regexp_like(nvl(t.drug_name, dd.drug_name), '滴眼液|眼药水') then '43'
        when regexp_like(nvl(t.drug_name, dd.drug_name), '滴鼻') then '44'
        when regexp_like(nvl(t.drug_name, dd.drug_name), '滴耳') then '45'
        when regexp_like(nvl(t.drug_name, dd.drug_name), '眼膏') then '52'
        when regexp_like(nvl(t.drug_name, dd.drug_name), '颗粒') then '54'
        when regexp_like(nvl(t.drug_name, dd.drug_name), '口服液') then '31'
        when regexp_like(nvl(t.drug_name, dd.drug_name), '糖浆') then '30'
        when regexp_like(nvl(t.drug_name, dd.drug_name), '喷雾') then '58'
        when regexp_like(nvl(t.drug_name, dd.drug_name), '吸入') then '60'
        when regexp_like(nvl(t.drug_name, dd.drug_name), '贴') then '65'
        when regexp_like(nvl(t.drug_name, dd.drug_name), '栓') then '63'
        when regexp_like(nvl(t.drug_name, dd.drug_name), '丸') then '14'
        else '99'
    end
) as DRUG_FORM_CODE, -- 药物剂型代码

nvl(
    (
        select max(v.value_domain_name)
          from CDA_VALUE_DOMAIN_MAP v
         where v.category_code = 'CV08.50.002'
           and v.hospital_code = m.dose_model_code
    ),
    case
        when regexp_like(nvl(t.drug_name, dd.drug_name), '肠溶片') then '肠溶片'
        when regexp_like(nvl(t.drug_name, dd.drug_name), '缓释片|控释片') then '缓释片'
        when regexp_like(nvl(t.drug_name, dd.drug_name), '咀嚼片') then '咀嚼片'
        when regexp_like(nvl(t.drug_name, dd.drug_name), '分散片') then '分散片'
        when regexp_like(nvl(t.drug_name, dd.drug_name), '片') then '片剂'
        when regexp_like(nvl(t.drug_name, dd.drug_name), '粉针|冻干') then '粉针'
        when regexp_like(nvl(t.drug_name, dd.drug_name), '注射液|胰岛素') then '注射液'
        when regexp_like(nvl(t.drug_name, dd.drug_name), '缓释胶囊|控释胶囊') then '缓释胶囊'
        when regexp_like(nvl(t.drug_name, dd.drug_name), '胶囊') then '胶囊'
        when regexp_like(nvl(t.drug_name, dd.drug_name), '滴眼液|眼药水') then '滴眼剂'
        when regexp_like(nvl(t.drug_name, dd.drug_name), '滴鼻') then '滴鼻剂'
        when regexp_like(nvl(t.drug_name, dd.drug_name), '滴耳') then '滴耳剂'
        when regexp_like(nvl(t.drug_name, dd.drug_name), '眼膏') then '眼膏剂'
        when regexp_like(nvl(t.drug_name, dd.drug_name), '颗粒') then '颗粒剂'
        when regexp_like(nvl(t.drug_name, dd.drug_name), '口服液') then '口服溶液剂'
        when regexp_like(nvl(t.drug_name, dd.drug_name), '糖浆') then '糖浆剂'
        when regexp_like(nvl(t.drug_name, dd.drug_name), '喷雾') then '喷雾剂'
        when regexp_like(nvl(t.drug_name, dd.drug_name), '吸入') then '吸入剂'
        when regexp_like(nvl(t.drug_name, dd.drug_name), '贴') then '贴剂'
        when regexp_like(nvl(t.drug_name, dd.drug_name), '栓') then '栓剂'
        when regexp_like(nvl(t.drug_name, dd.drug_name), '丸') then '丸剂'
        else '其他剂型'
    end
) as DRUG_FORM_NAME, -- 药物剂型名称
       t.order_no as GROUP_NO, -- 处方药品组号

       cast(null as char(1))
           as SKIN_TEST_RESULT, -- 皮试结果

     case    when (select dict_NAME from   PORTAL_USER.PORTAL_SYS_DICT t where TYPE_CODE = 'jy' and dict_code = m.BASICDRUG)   = '基药' then '1'
       else '0'end            as IS_ESSENTIAL, -- 是否基药，待确认来源

       case    when (select dict_NAME from   PORTAL_USER.PORTAL_SYS_DICT t where TYPE_CODE = 'jy' and dict_code = m.BASICDRUG)   = '基药' then '1'
       else '4' end    ESSENTIL_GRADE, -- 基药级别，待确认来源
case
    when nvl(m.antibiotic_flag, 0) = 1
      or trim(m.anti_flag) in ('1', '2', '3')
    then '1'
    else '0'
end as IS_ANTI,  -- 是否抗菌药物，待确认来源
 case
    when trim(m.ANTI_FLAG) = '0' then '-'
    when (
            select max(t.dict_name)
              from PORTAL_USER.PORTAL_SYS_DICT t
             where t.type_code = 'kss'
               and t.dict_code = m.ANTI_FLAG
         ) = '非限制'
    then '1'
    when (
            select max(t.dict_name)
              from PORTAL_USER.PORTAL_SYS_DICT t
             where t.type_code = 'kss'
               and t.dict_code = m.ANTI_FLAG
         ) = '限制'
    then '2'
    when (
            select max(t.dict_name)
              from PORTAL_USER.PORTAL_SYS_DICT t
             where t.type_code = 'kss'
               and t.dict_code = m.ANTI_FLAG
         ) = '特殊'
    then '3'
    else '-'
end as ANTI_USE_GRADE_CODE, -- 抗菌药物使用级别代码

case
    when trim(m.ANTI_FLAG) = '0' then '-'
    when (
            select max(t.dict_name)
              from PORTAL_USER.PORTAL_SYS_DICT t
             where t.type_code = 'kss'
               and t.dict_code = m.ANTI_FLAG
         ) = '非限制'
    then '非限制使用'
    when (
            select max(t.dict_name)
              from PORTAL_USER.PORTAL_SYS_DICT t
             where t.type_code = 'kss'
               and t.dict_code = m.ANTI_FLAG
         ) = '限制'
    then '限制使用'
    when (
            select max(t.dict_name)
              from PORTAL_USER.PORTAL_SYS_DICT t
             where t.type_code = 'kss'
               and t.dict_code = m.ANTI_FLAG
         ) = '特殊'
    then '特殊使用'
    else '-'
end as ANTI_USE_GRADE_NAME, -- 抗菌药物使用级别名称

       '-'           as IF_YF, -- 用药目的代码

       '370104' as DISTRICT_CODE, -- 所属行政区划

       cast(null as date)
           as CREATED_AT, -- 创建时间，由平台自动生成

       'INSERT' as EXCHANGE_TYPE, -- 交换类型

       cast(systimestamp as timestamp)
           as SYSTEM_TIME, -- 数据上传时间戳

     case
    /* 700 输液泵泵入 */
    when regexp_like(trim(t.administration), '输液泵|静脉泵入|微量泵入|泵入') then 700

    /* 401 皮下注射 */
    when regexp_like(trim(t.administration), '皮下注射') then 401

    /* 402 皮内注射 */
    when regexp_like(trim(t.administration), '皮内注射|皮试') then 402

    /* 403 肌肉注射 */
    when regexp_like(trim(t.administration), '肌肉注射') then 403

    /* 404 静脉注射或静脉滴注 */
    when regexp_like(trim(t.administration), '静脉滴注|静脉输液|续静滴|静脉注射|静脉推注|静脉壶内给药|静脉化疗|脐静脉给药|静脉封管|封管') then 404

    /* 405 鞘内注射 */
    when regexp_like(trim(t.administration), '鞘内注射') then 405

    /* 601 椎管内用药 */
    when regexp_like(trim(t.administration), '椎管内') then 601

    /* 602 关节腔内用药 */
    when regexp_like(trim(t.administration), '关节腔注射|关节腔冲洗|关节腔') then 602

    /* 603 胸膜腔用药 */
    when regexp_like(trim(t.administration), '胸腔注射|胸腔冲洗|胸膜腔') then 603

    /* 604 腹腔用药 */
    when regexp_like(trim(t.administration), '腹腔注射|腹腔冲洗|腹腔灌注|腹腔用药|腹膜透析') then 604

    /* 605 阴道用药 */
    when regexp_like(trim(t.administration), '阴道内置药|阴道冲洗|阴道用药|阴道') then 605

    /* 606 气管内用药 */
    when regexp_like(trim(t.administration), '气管滴药|气管内') then 606

    /* 607 滴眼 */
    when regexp_like(trim(t.administration), '滴左眼|滴右眼|滴双眼|滴眼|涂左眼|涂右眼|涂双眼|涂眼膏') then 607

    /* 608 滴鼻 */
    when regexp_like(trim(t.administration), '滴鼻|喷鼻|鼻腔冲洗') then 608

    /* 609 喷喉 */
    when regexp_like(trim(t.administration), '喷喉|口腔喷雾') then 609

    /* 610 含化 */
    when regexp_like(trim(t.administration), '舌下含化|舌下|口含|含化|含漱') then 610

    /* 611 敷伤口 */
    when regexp_like(trim(t.administration), '敷伤口|湿敷') then 611

    /* 612 擦皮肤 */
    when regexp_like(trim(t.administration), '擦皮肤|外用|涂擦|涂剂') then 612

    /* 1 口服 */
    when regexp_like(trim(t.administration), '口服|冲服|煎服|嚼服|泡服|胃管内注入|鼻空肠管注入|空肠造瘘管内注入|空肠造瘘注入') then 1

    /* 2 直肠用药 */
    when regexp_like(trim(t.administration), '直肠|肛门注入|肛塞|肛用|保留灌肠|清洁灌肠|灌肠') then 2

    /* 5 吸入用药 */
    when regexp_like(trim(t.administration), '雾化吸入|雾化吸入Ⅰ号|压力雾化|吸入') then 5

    /* 6 局部用药 */
    when regexp_like(trim(t.administration), '局部麻醉|局醉|浸润麻醉|局部注射|局部用药') then 6

    /* 699 其他局部用药途径 */
    when regexp_like(trim(t.administration), '会阴冲洗|膀胱灌注|膀胱冲洗|宫腔注射|宫颈上药|宫颈注射|直肠粘膜注射|瘤体内注射|介入治疗|肿瘤灌注|穴位封闭|穴位注射|鼻穴位注射|耳穴位注射|耳后局部注射|前房注射|玻璃体腔内注射|眼内注射|球后注射|球旁注射|半球后注射|结膜下注射|咽后壁注射|口腔粘膜注射|粘膜下注射|管道冲洗|创腔冲洗|器械冲洗|盆腔冲洗|腔内给药|引流管内注入|鼓窦内给药') then 699

    /* 9 其他用药途径：非给药途径或无法准确归类 */
    when trim(t.administration) in (
        'FREQ_DETAIL',
        '血液滤过',
        '血液透析滤过',
        '血液透析',
        '血管造影',
        '葡萄糖试验',
        '葡萄糖耐量',
        '市门统',
        '（久煎）',
        '（冲服）',
        '（后下）',
        '||07--07',
        '||04--04'
    ) then 9

    else 9
end as DRUG_WAY_CD, -- 药物使用途径代码

     case
    when regexp_like(trim(t.administration), '输液泵|静脉泵入|微量泵入|泵入') then '输液泵泵入'

    when regexp_like(trim(t.administration), '皮下注射') then '皮下注射'
    when regexp_like(trim(t.administration), '皮内注射|皮试') then '皮内注射'
    when regexp_like(trim(t.administration), '肌肉注射') then '肌肉注射'
    when regexp_like(trim(t.administration), '静脉滴注|静脉输液|续静滴|静脉注射|静脉推注|静脉壶内给药|静脉化疗|脐静脉给药|静脉封管|封管') then '静脉注射或静脉滴注'
    when regexp_like(trim(t.administration), '鞘内注射') then '鞘内注射'
    when regexp_like(trim(t.administration), '椎管内') then '椎管内用药'
    when regexp_like(trim(t.administration), '关节腔注射|关节腔冲洗|关节腔') then '关节腔内用药'
    when regexp_like(trim(t.administration), '胸腔注射|胸腔冲洗|胸膜腔') then '胸膜腔用药'
    when regexp_like(trim(t.administration), '腹腔注射|腹腔冲洗|腹腔灌注|腹腔用药|腹膜透析') then '腹腔用药'
    when regexp_like(trim(t.administration), '阴道内置药|阴道冲洗|阴道用药|阴道') then '阴道用药'
    when regexp_like(trim(t.administration), '气管滴药|气管内') then '气管内用药'
    when regexp_like(trim(t.administration), '滴左眼|滴右眼|滴双眼|滴眼|涂左眼|涂右眼|涂双眼|涂眼膏') then '滴眼'
    when regexp_like(trim(t.administration), '滴鼻|喷鼻|鼻腔冲洗') then '滴鼻'
    when regexp_like(trim(t.administration), '喷喉|口腔喷雾') then '喷喉'
    when regexp_like(trim(t.administration), '舌下含化|舌下|口含|含化|含漱') then '含化'
    when regexp_like(trim(t.administration), '敷伤口|湿敷') then '敷伤口'
    when regexp_like(trim(t.administration), '擦皮肤|外用|涂擦|涂剂') then '擦皮肤'

    when regexp_like(trim(t.administration), '口服|冲服|煎服|嚼服|泡服|胃管内注入|鼻空肠管注入|空肠造瘘管内注入|空肠造瘘注入') then '口服'
    when regexp_like(trim(t.administration), '直肠|肛门注入|肛塞|肛用|保留灌肠|清洁灌肠|灌肠') then '直肠用药'
    when regexp_like(trim(t.administration), '雾化吸入|雾化吸入Ⅰ号|压力雾化|吸入') then '吸入用药'
    when regexp_like(trim(t.administration), '局部麻醉|局醉|浸润麻醉|局部注射|局部用药') then '局部用药'

    when regexp_like(trim(t.administration), '会阴冲洗|膀胱灌注|膀胱冲洗|宫腔注射|宫颈上药|宫颈注射|直肠粘膜注射|瘤体内注射|介入治疗|肿瘤灌注|穴位封闭|穴位注射|鼻穴位注射|耳穴位注射|耳后局部注射|前房注射|玻璃体腔内注射|眼内注射|球后注射|球旁注射|半球后注射|结膜下注射|咽后壁注射|口腔粘膜注射|粘膜下注射|管道冲洗|创腔冲洗|器械冲洗|盆腔冲洗|腔内给药|引流管内注入|鼓窦内给药') then '其他局部用药途径'

    when trim(t.administration) in (
        'FREQ_DETAIL',
        '血液滤过',
        '血液透析滤过',
        '血液透析',
        '血管造影',
        '葡萄糖试验',
        '葡萄糖耐量',
        '市门统',
        '（久煎）',
        '（冲服）',
        '（后下）',
        '||07--07',
        '||04--04'
    ) then '其他用药途径'

    else '其他用药途径'
end as DRUG_WAY_NAME, -- 药物使用途径名称

       cast(
           greatest(
               nvl(
                   t.abidance,
                   case
                       when a.presc_type = '1'
                           then nvl(a.repetition, 1)
                       else 1
                   end
               ),
               1
           ) as number(5)
       ) as DURATION_TIME, -- 持续用药天数

       cast(
           round(
               case
                   when nvl(t.flag, a.flag) = 2
                       then -abs(t.costs)
                   else t.costs
               end,
               2
           ) as number(9, 2)
       ) as DRUG_AMOUNT, -- 药物金额

     case  when dd.drug_indicator = 2 then '9'  else null end            as TCM_DECOCTION_METHOD, -- 中药饮片煎煮法

       case
           when a.presc_type = '1'
               then substr(a.memo, 1, 100)
           else cast(null as varchar2(100))
       end as MEDICATION_METHOD, -- 中药用药方法

       cast(
           round(
               nvl(
                   (
                       select max(pl.retail_price)
                                  keep (
                                      dense_rank last
                                      order by pl.start_date
                                  )
                         from HIS.drug_price_list pl
                        where pl.drug_code = t.drug_code
                          and pl.drug_spec =
                              nvl(t.package_spec, t.drug_spec)
                          and pl.firm_id = t.firm_id
                          and pl.start_date <= a.presc_date
                          and (
                              pl.stop_date is null
                              or pl.stop_date >= a.presc_date
                          )
                   ),
                   case
                       when nvl(t.quantity, 0) <> 0
                           then abs(t.costs / t.quantity)
                       else null
                   end
               ),
               2
           ) as number(9, 2)
       ) as DRUG_PRICE, -- 药物单价

       case
           when a.presc_type = '1'
               then substr(a.memo, 1, 2000)
           else cast(null as varchar2(2000))
       end as CH_DRUG_NOTES, -- 中药饮片处方描述

       substr(a.clinic_no, 1, 18)
           as OUTPATIENT_NUM, -- 本次门诊标识号

       substr(a.name, 1, 50)         as NAME, -- 患者姓名

       case trim(pmi.sex)
           when '男' then '1'
           when '女' then '2'
           when '未知' then '0'
           when '不详' then '9'
           when '未说明' then '9'
           else '9'
       end as SEX_CODE, -- 患者性别代码

      nvl( substr(pmi.id_no, 1, 18),'000000000000000000')
           as ID_NUM, -- 患者身份证件号码


   case
    when lower(trim(t.frequency)) in ('st', 'prn')
      or trim(t.frequency) in ('立即', '必要时', '术前', '术晨', '术前30’', '皮试')
    then '2'
    when t.frequency is null then '9'
    else '2'
end as ODR_TYPE, -- 处方类别编码：门诊处方默认临时

       substr(
           a.clinic_no
           || '|' || nvl(cast(t.order_no as varchar2(50)), '0')
           || '|' || nvl(cast(t.order_sub_no as varchar2(50)), '0'),
           1,
           100
       ) as ORDER_ITEM_CODE, -- 院内医嘱编号

       substr(t.drug_name, 1, 100)
           as ORDER_ITEM_NAME, -- 院内医嘱项名称

       '1' as ORDER_CATEGORY_CODE, -- 医嘱项目大类别编码：药品类

       '药品类医嘱' as ORDER_CATEGORY_NAME, -- 医嘱项目大类别名称

    case
    when lower(trim(t.dosage_units)) in ('g', '克') then 'g'
    when lower(trim(t.dosage_units)) in ('mg', '毫克') then 'mg'
    when lower(trim(t.dosage_units)) in ('μg', 'ug', 'mcg', '微克') then 'μg'
    when lower(trim(t.dosage_units)) in ('l', '升') then 'L'
    when lower(trim(t.dosage_units)) in ('ml', '毫升') then 'ml'
    when upper(trim(t.dosage_units)) in ('IU', '万IU', 'AXAIU') then 'IU'
    when upper(trim(t.dosage_units)) in ('U', '万U')
      or trim(t.dosage_units) in ('单位', '万u', 'u') then 'U'
    else substr(t.dosage_units, 1, 100)
end as ORDER_NUM_NAME, -- 医嘱用量单位

       case
           when nvl(t.flag, a.flag) = 2 then '2'
           else '1'
       end as ORDER_STATUS, -- 医嘱有效标识，1有效、2无效

       cast(null as varchar2(100))           as DTCODE, -- 药品追溯码，暂无可靠来源

       substr(
           (
               select max(m.ylxmbm)
                 from HIS.insur_vsh_center_item_new m
                where m.item_code = t.drug_code
           ),
           1,
           100
       ) as NHSA_STANDARD_CODE, -- 医保贯标码

       substr(
           cast(dd.dose_per_unit as varchar2(100)),
           1,
           100
       ) as DOSAGE, -- 最小剂量

       dd.dose_units     as DOSAGE_UNIT_NAME, -- 最小剂量单位名称

       substr(
           nvl(t.package_units, dd.units),
           1,
           100
       ) as DRUG_ALL_UNIT, -- 药品包装单位

       (
           select max(pl.amount_per_package)
                      keep (
                          dense_rank last
                          order by pl.start_date
                      )
             from HIS.drug_price_list pl
            where pl.drug_code = t.drug_code
              and pl.drug_spec =
                  nvl(t.package_spec, t.drug_spec)
              and pl.firm_id = t.firm_id
              and pl.start_date <= a.presc_date
              and (
                  pl.stop_date is null
                  or pl.stop_date >= a.presc_date
              )
       ) as DRUG_ALL_NUM, -- 药品包装量

       cast(
           greatest(
               nvl(
                   t.abidance,
                   case
                       when a.presc_type = '1'
                           then nvl(a.repetition, 1)
                       else 1
                   end
               ),
               1
           ) as number
       ) as ADMINISTRATION_DAYS, -- 执行天数


     case
    when regexp_like(trim(t.administration), '输液泵|静脉泵入|微量泵入|泵入') then '输液泵泵入'
    when regexp_like(trim(t.administration), '皮下注射') then '皮下注射'
    when regexp_like(trim(t.administration), '皮内注射|皮试') then '皮内注射'
    when regexp_like(trim(t.administration), '肌肉注射') then '肌肉注射'
    when regexp_like(trim(t.administration), '静脉滴注|静脉输液|续静滴|静脉注射|静脉推注|静脉壶内给药|静脉化疗|脐静脉给药|静脉封管|封管') then '静脉注射或静脉滴注'
    when regexp_like(trim(t.administration), '鞘内注射') then '鞘内注射'
    when regexp_like(trim(t.administration), '椎管内') then '椎管内用药'
    when regexp_like(trim(t.administration), '关节腔注射|关节腔冲洗|关节腔') then '关节腔内用药'
    when regexp_like(trim(t.administration), '胸腔注射|胸腔冲洗|胸膜腔') then '胸膜腔用药'
    when regexp_like(trim(t.administration), '腹腔注射|腹腔冲洗|腹腔灌注|腹腔用药|腹膜透析') then '腹腔用药'
    when regexp_like(trim(t.administration), '阴道内置药|阴道冲洗|阴道用药|阴道') then '阴道用药'
    when regexp_like(trim(t.administration), '气管滴药|气管内') then '气管内用药'
    when regexp_like(trim(t.administration), '滴左眼|滴右眼|滴双眼|滴眼|涂左眼|涂右眼|涂双眼|涂眼膏') then '滴眼'
    when regexp_like(trim(t.administration), '滴左耳|滴右耳|滴双耳|滴耳') then '滴耳'
    when regexp_like(trim(t.administration), '滴鼻|喷鼻|鼻腔冲洗') then '滴鼻'
    when regexp_like(trim(t.administration), '喷喉|口腔喷雾') then '喷喉'
    when regexp_like(trim(t.administration), '舌下含化|舌下|口含|含化|含漱') then '含化'
    when regexp_like(trim(t.administration), '敷伤口|湿敷') then '敷伤口'
    when regexp_like(trim(t.administration), '擦皮肤|外用|涂擦|涂剂') then '擦皮肤'
    when regexp_like(trim(t.administration), '口服|冲服|煎服|嚼服|泡服|胃管内注入|鼻空肠管注入|空肠造瘘管内注入|空肠造瘘注入') then '口服'
    when regexp_like(trim(t.administration), '直肠|肛门注入|肛塞|肛用|保留灌肠|清洁灌肠|灌肠') then '直肠用药'
    when regexp_like(trim(t.administration), '雾化吸入|雾化吸入Ⅰ号|压力雾化|吸入') then '吸入用药'
    when regexp_like(trim(t.administration), '局部麻醉|局醉|浸润麻醉|局部注射|局部用药') then '局部用药'
    else '其他用药途径'
end as DRUG_ADMINISTRATION_ROUTE, -- 给药途径

       '0' as IS_EXTERNAL_PRES -- 是否外配处方，院内处方填0

   from HIS.drug_presc_master a

join HIS.drug_presc_detail t
  on t.presc_date = a.presc_date
 and t.presc_no   = a.presc_no

join HIS.clinic_master d
  on d.clinic_no  = a.clinic_no
 and d.patient_id = a.patient_id

join HIS.pat_master_index pmi
  on pmi.patient_id = a.patient_id

left join HIS.med_dict_baseinfo m
  on m.drug_id = t.drug_code

left join (
        select x.drug_code,
               x.drug_spec,
               x.drug_name,
               x.units,
               x.drug_form,
               x.dose_per_unit,
               x.dose_units,
               x.drug_indicator
          from (
                select dd.drug_code,
                       dd.drug_spec,
                       dd.drug_name,
                       dd.units,
                       dd.drug_form,
                       dd.dose_per_unit,
                       dd.dose_units,
                       dd.drug_indicator,
                       row_number() over (
                           partition by dd.drug_code,
                                        dd.drug_spec
                           order by dd.rowid
                       ) as rn
                  from HIS.drug_dict dd
               ) x
         where x.rn = 1
       ) dd
  on dd.drug_code = t.drug_code
 and dd.drug_spec = t.drug_spec

left join (
        select g.F008_HIS_YAO_PIN_BIAN_MA as his_drug_code,
               max(g.F004_YPID11_3) as ypid_code,
               max(g.F007_CHAN_PIN_MING_CHENG) as product_name
          from DRUG_STANDARD_DICT g
         group by g.F008_HIS_YAO_PIN_BIAN_MA
       ) std
  on std.his_drug_code = t.drug_code

left join (
        select zd.院标编码 as local_code,
               max(zd.国标编码) as standard_code,
               max(zd.国标名称) as standard_name
          from CDA.cda_dictionary zd
         where zd.字典名称 in (
                   '用药途径代码',
                   '给药途径代码',
                   '药物使用途径代码'
               )
         group by zd.院标编码
       ) route_map
  on route_map.local_code = t.administration

left join (
        select v.hospital_code,
               max(v.value_domain_code) as value_domain_code,
               max(v.value_domain_name) as value_domain_name
          from CDA_VALUE_DOMAIN_MAP v
         where v.category_code = 'CV08.50.002'
         group by v.hospital_code
       ) form_map
  on form_map.hospital_code = m.dose_model_code

left join (
        select p.dict_code,
               max(v.value_domain_code) as value_domain_code,
               max(v.value_domain_name) as value_domain_name
          from PORTAL_USER.portal_sys_dict p
          join CDA_VALUE_DOMAIN_MAP v
            on v.hospital_code = p.dict_code
           and v.category_code = 'CC99.00203'
         where p.type_code = 'pharmacology_type'
         group by p.dict_code
       ) pharm_map
  on pharm_map.dict_code = m.phy_class

left join (
        select dict_code,
               max(dict_name) as dict_name
          from PORTAL_USER.portal_sys_dict
         where type_code = 'jy'
         group by dict_code
       ) jy_dict
  on jy_dict.dict_code = m.basicdrug

left join (
        select dict_code,
               max(dict_name) as dict_name
          from PORTAL_USER.portal_sys_dict
         where type_code = 'kss'
         group by dict_code
       ) kss_dict
  on kss_dict.dict_code = m.anti_flag

left join (
        select item_code,
               max(ylxmbm) as ylxmbm
          from HIS.insur_vsh_center_item_new
         group by item_code
       ) insur_map
  on insur_map.item_code = t.drug_code

where a.presc_source = '0'
  and (a.flag = 1 or a.flag is null)
  and a.costs > 0
  and d.visit_date >= date '2021-01-01'
  and d.visit_date <  date '2025-01-01'
