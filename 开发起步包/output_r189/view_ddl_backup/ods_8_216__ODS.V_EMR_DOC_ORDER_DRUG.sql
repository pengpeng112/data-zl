
  CREATE OR REPLACE FORCE VIEW "ODS"."V_EMR_DOC_ORDER_DRUG" ("ID", "PATIENT_ID", "ODR_GN", "ODR_SN", "ODR_TYPE", "ODER_ITEM_CODE", "ODER_ITEM_NAME", "ODR_TYPENAME", "ORD_TIME", "STATUS_CODE", "STATUS_NAME", "ODR_CODE", "DRUG_COMMON_NAME", "ODR_NAME", "DRUG_CLASS_CODE", "DRUG_CLASS_NAME", "CATEGORY", "DRUG_FORM_CODE", "DRUG_FORM_NAME", "SPEC", "UNIT", "DRUG_DOSE", "SINGLE_DOSE", "UNIT_CODE", "JL_UNIT", "HERB_NUM", "UNIT_DOSE", "ORDER_DOSAGE", "DRUG_FREQUENCY_CODE", "DRUG_FREQUENCY_NAME", "IS_ANTI", "ANTI_USE_GRADE_CODE", "ANTI_USE_GRADE_NAME", "DRUG_WAY_CD", "DRUG_WAY_NAME", "IF_YF", "ODR_NOTE", "DPT_CODE", "DPT_NAME", "HOS_DPT_CODE", "HOS_DPT_NAME", "DOC_IDCARD", "DOC_NAME", "ODRISU_DT", "BEGIN_TIME", "NURSE_NAME", "NUR_E_DT", "STOP_DT", "STPDOC_IDCARD", "STPDOC_NAME", "ORG_CODE", "ORG_NAME", "DISTRICT_CODE", "EXCHANGE_TYPE", "SYSTEM_TIME", "RECIPE_NUM", "NAME", "SEX_CODE", "ID_NUM", "ORDER_ID", "DTCODE", "NHSA_STANDARD_CODE", "ORDER_DOC_CERTIFICATE_NO", "PRES_DECRIPTION", "TCM_DECOCTION_METHOD", "TCM_USE_METHOD", "ORDER_STATUS", "PRES_ID", "PHYSICIAN_CERTIFICATE_NO") AS 
  select substr(
    t.patient_id || '|' || t.visit_id || '|' || to_char(t.order_no) || '|' || to_char(t.order_sub_no),
    1,
    100
)  as ID,--  内码  是 主键，必填

       t.patient_id || '|' || t.visit_id as PATIENT_ID,--  住院唯一标识号 是 必填项，病人某一次住院的唯一标识

       substr(to_char(t.order_no), 1, 24) as ODR_GN,--  医嘱组号    同一组相同治疗目的得医嘱

       substr(to_char(t.order_sub_no), 1, 12) as ODR_SN,--  组内顺序号

       case
           when t.repeat_indicator = 1 then '1'
           when t.repeat_indicator = 0 then '2'
           else '9'
       end as ODR_TYPE,--  医嘱类型代码  是 必填 1、长期，2、临时，3，出院带药9、其他

       substr(
           nvl(
               (select cd.国标编码
                  from cda.cda_dictionary cd
                 where cd.字典名称 = '医嘱项目类型代码'
                   and cd.院标编码 = t.order_class
                   and rownum = 1),
               '01'
           ),
           1,
           20
       ) as ODER_ITEM_CODE,--  医嘱项目类型代码  是

       substr(
           nvl(
               (select cd.国标名称
                  from cda.cda_dictionary cd
                 where cd.字典名称 = '医嘱项目类型代码'
                   and cd.院标编码 = t.order_class
                   and rownum = 1),
               '药品类医嘱'
           ),
           1,
           20
       ) as ODER_ITEM_NAME,--  医嘱项目类型名称  是

       substr(nvl(t.order_text, '-'), 1, 24) as ODR_TYPENAME,--  医嘱名称  是 按照医院开立医嘱名称上传

   case
    when t.repeat_indicator = 1
     and t.start_date_time is not null
    then cast(
             least(
                 greatest(
                     ceil(nvl(t.stop_date_time, pv.discharge_date_time) - t.start_date_time),
                     0
                 ),
                 9999
             ) as number(4)
         )
    else cast(null as number(4))
end as ORD_TIME,--  执行天数    长期医嘱

 case to_char(t.order_status)
           when '1' then '1' -- 新开：医生签名
           when '2' then '3' -- 执行：已执行
           when '3' then '3' -- 停止：按已执行历史医嘱处理
           when '4' then '4' -- 作废：医生取消
           else '3'
       end as STATUS_CODE,-- 状态代码    DMD-40

       case to_char(t.order_status)
           when '1' then '医生签名'
           when '2' then '已执行'
           when '3' then '已执行'
           when '4' then '医生取消'
           else '已执行'
       end as STATUS_NAME,-- 状态
--select * from DRUG_STANDARD_DICT
 --  substr(nvl(t.order_text, '-'), 1, 100)
   substr(nvl(  (select F004_YPID11_3  from DRUG_STANDARD_DICT  where F008_HIS_YAO_PIN_BIAN_MA=t.order_code and rownum=1)  , t.order_code ), 1, 100) as ODR_CODE,--  药品编码  是 西药：V12药品字典；中药：院内码
    substr(nvl(  (select F007_CHAN_PIN_MING_CHENG  from DRUG_STANDARD_DICT  where F008_HIS_YAO_PIN_BIAN_MA=t.order_code and rownum=1)  , t.order_text ), 1, 100)  as DRUG_COMMON_NAME,--  药物通用名 是

          substr(nvl(  (select F007_CHAN_PIN_MING_CHENG  from DRUG_STANDARD_DICT  where F008_HIS_YAO_PIN_BIAN_MA=t.order_code and rownum=1)  , t.order_text ), 1, 100)   as ODR_NAME,--  药品名称(产品名称)  是 必填


       nvl((select VALUE_DOMAIN_CODE from   CDA_VALUE_DOMAIN_MAP t where CATEGORY_CODE='CC99.00203' and  HOSPITAL_CODE in (
SELECT DICT_CODE FROM PORTAL_USER.PORTAL_SYS_DICT p where TYPE_CODE = 'pharmacology_type'  and  m.PHY_CLASS =p.dict_code) and rownum=1),'99')     as DRUG_CLASS_CODE, -- 药品分类代码

      nvl( (select VALUE_DOMAIN_NAME from   CDA_VALUE_DOMAIN_MAP t where CATEGORY_CODE='CC99.00203' and  HOSPITAL_CODE in (
SELECT DICT_CODE FROM PORTAL_USER.PORTAL_SYS_DICT p where TYPE_CODE = 'pharmacology_type'  and  m.PHY_CLASS =p.dict_code) and rownum=1),'其它化学药物')   as DRUG_CLASS_NAME, -- 药品分类名称



       case to_char(t1.drug_indicator)
           when '1' then '1' -- 西药
           when '3' then '2' -- 中成药
           when '2' then '3' -- 中药饮片
           when '5' then '4'
           when '6' then '4'
           else '4'
       end as CATEGORY,--  药品类别  是 1.西药 2.中成药 3.中药饮片 4.其它

    case
    when trim(t1.drug_form) is null then '99'

    /* 片剂类 */
    when trim(t1.drug_form) = '片剂' then '01'
    when trim(t1.drug_form) = '咀嚼片' then '03'
    when trim(t1.drug_form) = '缓释片' then '05'
    when trim(t1.drug_form) = '泡腾片' then '06'
    when trim(t1.drug_form) = '含化片' then '08'
    when trim(t1.drug_form) = '分散片' then '12'

    /* 丸剂类 */
    when trim(t1.drug_form) in ('丸剂', '水丸', '水蜜丸') then '14'

    /* 注射剂类 */
    when trim(t1.drug_form) in ('粉针', '冻干粉') then '15'
    when trim(t1.drug_form) in ('针剂', '水针', '注射液') then '16'

    /* 胶囊类 */
    when trim(t1.drug_form) = '胶囊' then '19'
    when trim(t1.drug_form) = '缓释胶囊' then '22'

    /* 液体口服/外用剂型 */
    when trim(t1.drug_form) in ('溶液', '含漱液', '混悬剂', '液体') then '23'
    when trim(t1.drug_form) = '合剂' then '24'
    when trim(t1.drug_form) = '乳液' then '25'
    when trim(t1.drug_form) = '凝胶' then '26'
    when trim(t1.drug_form) = '胶剂' then '26'
    when trim(t1.drug_form) = '滴剂' then '29'
    when trim(t1.drug_form) = '糖浆剂' then '30'
    when trim(t1.drug_form) = '口服溶液剂' then '31'
    when trim(t1.drug_form) = '酊剂' then '34'
    when trim(t1.drug_form) = '酏剂' then '36'
    when trim(t1.drug_form) = '洗剂' then '37'
    when trim(t1.drug_form) in ('搽剂', '擦剂', '涂剂', '外用') then '38'

    /* 五官科局部用药 */
    when trim(t1.drug_form) = '滴眼剂' then '43'
    when trim(t1.drug_form) = '滴鼻剂' then '44'
    when trim(t1.drug_form) = '滴耳剂' then '45'
    when trim(t1.drug_form) = '眼膏剂' then '52'

    /* 半固体、外用贴敷类 */
    when trim(t1.drug_form) = '膏剂' then '48'
    when trim(t1.drug_form) = '乳膏剂' then '49'
    when trim(t1.drug_form) = '贴剂' then '65'

    /* 其他明确剂型 */
    when trim(t1.drug_form) = '灌肠剂' then '47'
    when trim(t1.drug_form) = '散剂' then '53'
    when trim(t1.drug_form) in ('颗粒剂', '冲剂') then '54'
    when trim(t1.drug_form) = '气雾剂' then '57'
    when trim(t1.drug_form) in ('喷雾剂', '喷剂') then '58'
    when trim(t1.drug_form) = '吸入剂' then '60'
    when trim(t1.drug_form) = '膜剂' then '61'
    when trim(t1.drug_form) = '栓剂' then '63'
    when trim(t1.drug_form) = '植入剂' then '64'
    when trim(t1.drug_form) = '试剂' then '90'

    /* 特殊或非标准剂型，保守归其他 */
    when trim(t1.drug_form) in ('草药', '特医', '节育系统') then '99'

    /* 关键词兜底 */
    when regexp_like(trim(t1.drug_form), '肠溶片') then '04'
    when regexp_like(trim(t1.drug_form), '缓释片|控释片') then '05'
    when regexp_like(trim(t1.drug_form), '咀嚼片') then '03'
    when regexp_like(trim(t1.drug_form), '分散片') then '12'
    when regexp_like(trim(t1.drug_form), '片') then '01'
    when regexp_like(trim(t1.drug_form), '粉针|冻干') then '15'
    when regexp_like(trim(t1.drug_form), '针|注射|水针') then '16'
    when regexp_like(trim(t1.drug_form), '缓释胶囊|控释胶囊') then '22'
    when regexp_like(trim(t1.drug_form), '胶囊') then '19'
    when regexp_like(trim(t1.drug_form), '丸') then '14'
    when regexp_like(trim(t1.drug_form), '颗粒|冲剂') then '54'
    when regexp_like(trim(t1.drug_form), '滴眼') then '43'
    when regexp_like(trim(t1.drug_form), '滴鼻') then '44'
    when regexp_like(trim(t1.drug_form), '滴耳') then '45'
    when regexp_like(trim(t1.drug_form), '眼膏') then '52'
    when regexp_like(trim(t1.drug_form), '喷雾|喷剂') then '58'
    when regexp_like(trim(t1.drug_form), '气雾') then '57'
    when regexp_like(trim(t1.drug_form), '吸入') then '60'
    when regexp_like(trim(t1.drug_form), '贴') then '65'
    when regexp_like(trim(t1.drug_form), '栓') then '63'
    when regexp_like(trim(t1.drug_form), '洗剂|消毒液') then '37'
    when regexp_like(trim(t1.drug_form), '搽|擦|涂') then '38'
    when regexp_like(trim(t1.drug_form), '乳膏|霜') then '49'
    when regexp_like(trim(t1.drug_form), '膏') then '48'
    when regexp_like(trim(t1.drug_form), '膜') then '61'

    else '99'
end as DRUG_FORM_CODE, -- 药物剂型代码
 case
    when trim(t1.drug_form) is null then '其他剂型'

    /* 片剂类 */
    when trim(t1.drug_form) = '片剂' then '片剂'
    when trim(t1.drug_form) = '咀嚼片' then '咀嚼片'
    when trim(t1.drug_form) = '缓释片' then '缓释片'
    when trim(t1.drug_form) = '泡腾片' then '泡腾片'
    when trim(t1.drug_form) = '含化片' then '含片'
    when trim(t1.drug_form) = '分散片' then '分散片'

    /* 丸剂类 */
    when trim(t1.drug_form) in ('丸剂', '水丸', '水蜜丸') then '丸剂'

    /* 注射剂类 */
    when trim(t1.drug_form) in ('粉针', '冻干粉') then '粉针剂'
    when trim(t1.drug_form) in ('针剂', '水针', '注射液') then '注射液'

    /* 胶囊类 */
    when trim(t1.drug_form) = '胶囊' then '胶囊剂'
    when trim(t1.drug_form) = '缓释胶囊' then '缓释胶囊'

    /* 液体口服/外用剂型 */
    when trim(t1.drug_form) in ('溶液', '含漱液', '混悬剂', '液体') then '溶液剂'
    when trim(t1.drug_form) = '合剂' then '合剂'
    when trim(t1.drug_form) = '乳液' then '乳剂'
    when trim(t1.drug_form) = '凝胶' then '凝胶剂'
    when trim(t1.drug_form) = '胶剂' then '胶剂'
    when trim(t1.drug_form) = '滴剂' then '滴剂'
    when trim(t1.drug_form) = '糖浆剂' then '糖浆剂'
    when trim(t1.drug_form) = '口服溶液剂' then '口服液'
    when trim(t1.drug_form) = '酊剂' then '酊剂'
    when trim(t1.drug_form) = '酏剂' then '酏剂'
    when trim(t1.drug_form) = '洗剂' then '洗剂'
    when trim(t1.drug_form) in ('搽剂', '擦剂', '涂剂', '外用') then '搽剂'

    /* 五官科局部用药 */
    when trim(t1.drug_form) = '滴眼剂' then '滴眼剂'
    when trim(t1.drug_form) = '滴鼻剂' then '滴鼻剂'
    when trim(t1.drug_form) = '滴耳剂' then '滴耳剂'
    when trim(t1.drug_form) = '眼膏剂' then '眼膏剂'

    /* 半固体、外用贴敷类 */
    when trim(t1.drug_form) = '膏剂' then '软膏剂'
    when trim(t1.drug_form) = '乳膏剂' then '乳膏剂'
    when trim(t1.drug_form) = '贴剂' then '贴剂'

    /* 其他明确剂型 */
    when trim(t1.drug_form) = '灌肠剂' then '灌肠剂'
    when trim(t1.drug_form) = '散剂' then '散剂'
    when trim(t1.drug_form) in ('颗粒剂', '冲剂') then '颗粒剂'
    when trim(t1.drug_form) = '气雾剂' then '气雾剂'
    when trim(t1.drug_form) in ('喷雾剂', '喷剂') then '喷雾剂'
    when trim(t1.drug_form) = '吸入剂' then '吸入剂'
    when trim(t1.drug_form) = '膜剂' then '膜剂'
    when trim(t1.drug_form) = '栓剂' then '栓剂'
    when trim(t1.drug_form) = '植入剂' then '植入剂'
    when trim(t1.drug_form) = '试剂' then '试剂盒'

    /* 特殊或非标准剂型 */
    when trim(t1.drug_form) in ('草药', '特医', '节育系统') then '其他剂型'

    /* 关键词兜底 */
    when regexp_like(trim(t1.drug_form), '肠溶片') then '肠溶片'
    when regexp_like(trim(t1.drug_form), '缓释片|控释片') then '缓释片'
    when regexp_like(trim(t1.drug_form), '咀嚼片') then '咀嚼片'
    when regexp_like(trim(t1.drug_form), '分散片') then '分散片'
    when regexp_like(trim(t1.drug_form), '片') then '片剂'
    when regexp_like(trim(t1.drug_form), '粉针|冻干') then '粉针剂'
    when regexp_like(trim(t1.drug_form), '针|注射|水针') then '注射液'
    when regexp_like(trim(t1.drug_form), '缓释胶囊|控释胶囊') then '缓释胶囊'
    when regexp_like(trim(t1.drug_form), '胶囊') then '胶囊剂'
    when regexp_like(trim(t1.drug_form), '丸') then '丸剂'
    when regexp_like(trim(t1.drug_form), '颗粒|冲剂') then '颗粒剂'
    when regexp_like(trim(t1.drug_form), '滴眼') then '滴眼剂'
    when regexp_like(trim(t1.drug_form), '滴鼻') then '滴鼻剂'
    when regexp_like(trim(t1.drug_form), '滴耳') then '滴耳剂'
    when regexp_like(trim(t1.drug_form), '眼膏') then '眼膏剂'
    when regexp_like(trim(t1.drug_form), '喷雾|喷剂') then '喷雾剂'
    when regexp_like(trim(t1.drug_form), '气雾') then '气雾剂'
    when regexp_like(trim(t1.drug_form), '吸入') then '吸入剂'
    when regexp_like(trim(t1.drug_form), '贴') then '贴剂'
    when regexp_like(trim(t1.drug_form), '栓') then '栓剂'
    when regexp_like(trim(t1.drug_form), '洗剂|消毒液') then '洗剂'
    when regexp_like(trim(t1.drug_form), '搽|擦|涂') then '搽剂'
    when regexp_like(trim(t1.drug_form), '乳膏|霜') then '乳膏剂'
    when regexp_like(trim(t1.drug_form), '膏') then '软膏剂'
    when regexp_like(trim(t1.drug_form), '膜') then '膜剂'

    else '其他剂型'
end as DRUG_FORM_NAME, -- 药物剂型名称

       substr(t1.drug_spec, 1, 100) as SPEC,--  药品规格

       substr(t1.units, 1, 6) as UNIT,--  单位    颗，包，片，袋，盒等最小包装单位

       case
           when t1.dose_per_unit is not null
           then cast(
                    least(
                        greatest(round(t1.dose_per_unit, 2), 0),
                        9999999999.99
                    ) as number(12,2)
                )
           else cast(null as number(12,2))
       end as DRUG_DOSE,-- 药物剂量    药剂的用药量，一般是指单味药的成人内服一日的用量

       case
           when t.dosage is not null
           then cast(
                    least(
                        greatest(round(t.dosage, 2), 0),
                        999.99
                    ) as number(5,2)
                )
           else cast(null as number(5,2))
       end as SINGLE_DOSE,-- 药物使用次剂量 是 单次使用剂量，按剂量单位计算

      case
    when lower(trim(t.dosage_units)) in ('g', '克') then '1'
    when lower(trim(t.dosage_units)) in ('mg', '毫克') then '2'
    when lower(trim(t.dosage_units)) in ('μg', 'ug', 'mcg', '微克') then '3'
    when lower(trim(t.dosage_units)) in ('l', '升') then '5'
    when lower(trim(t.dosage_units)) in ('ml', '毫升') then '6'
    when upper(trim(t.dosage_units)) in ('IU', '万IU', 'AXAIU') then '7'
    when upper(trim(t.dosage_units)) in ('U', '万U')
      or trim(t.dosage_units) in ('单位', '万u', 'u') then '8'
    else null
end as UNIT_CODE,

case
    when lower(trim(t.dosage_units)) in ('g', '克') then 'g'
    when lower(trim(t.dosage_units)) in ('mg', '毫克') then 'mg'
    when lower(trim(t.dosage_units)) in ('μg', 'ug', 'mcg', '微克') then 'μg'
    when lower(trim(t.dosage_units)) in ('l', '升') then 'L'
    when lower(trim(t.dosage_units)) in ('ml', '毫升') then 'ml'
    when upper(trim(t.dosage_units)) in ('IU', '万IU', 'AXAIU') then 'IU'
    when upper(trim(t.dosage_units)) in ('U', '万U')
      or trim(t.dosage_units) in ('单位', '万u', 'u') then 'U'
    else substr(t.dosage_units, 1, 4)
end as JL_UNIT,

       cast(null as number) as HERB_NUM,--  草药付数    中草药必填

       case
           when t1.dose_per_unit is not null
           then cast(
                    least(
                        greatest(round(t1.dose_per_unit, 2), 0),
                        9999999.99
                    ) as number(9,2)
                )
           else cast(null as number(9,2))
       end as UNIT_DOSE,-- 单位剂量    每单位药品含主药成分的量

      case
    when t.dosage is not null
    then cast(
             least(
                 greatest(
                     round(
                         t.dosage *
                         nvl(
                             case
                                 -- 明确频次代码
                                 when t.freq_key in ('qd', 'q24h', '1/日',
                                                     '早餐前', '午餐前', '晚餐前',
                                                     '1/早餐前15', '1/早餐前30',
                                                     '1/午餐前15', '1/午餐前30',
                                                     '1/晚餐前15', '1/晚餐前30',
                                                     '空腹', '下午',
                                                     'qm', 'qn', 'hs', '睡前',
                                                     'st', '术前', '术晨', '术前30',
                                                     'prn') then 1

                                 when t.freq_key in ('bid', 'bidac') then 2

                                 when t.freq_key in ('tid', 'tidac',
                                                     '三餐前', '三餐后', '空腹三餐后') then 3

                                 when t.freq_key in ('qid', '4/日') then 4

                                 when t.freq_key in ('q1h', '24/日') then 24
                                 when t.freq_key in ('q2h') then 12
                                 when t.freq_key in ('q3h', '1/3小时') then 8
                                 when t.freq_key in ('q4h', '1/4小时') then 6
                                 when t.freq_key in ('q6h') then 4
                                 when t.freq_key in ('q8h') then 3
                                 when t.freq_key in ('q12h') then 2

                                 -- 带具体执行点的频次
                                 when t.freq_key in ('q12h1', 'q12h2') then 1
                                 when t.freq_key in ('q6h1', 'q6h2') then 2
                                 when t.freq_key in ('q8h1') then 2
                                 when t.freq_key in ('q8h2') then 1

                                 -- 隔日、每周、每几周
                                 when t.freq_key in ('qod', '1/2日') then 0.5
                                 when t.freq_key in ('qw') then 1 / 7
                                 when t.freq_key in ('biw') then 2 / 7
                                 when t.freq_key in ('tiw') then 3 / 7
                                 when t.freq_key in ('5/周') then 5 / 7
                                 when t.freq_key in ('q2w') then 1 / 14
                                 when t.freq_key in ('q3w') then 1 / 21
                                 when t.freq_key in ('q4w') then 1 / 28

                                 -- 特殊小时频次
                                 when t.freq_key in ('q36h') then 24 / 36
                                 when t.freq_key in ('q72h') then 24 / 72
                                 when t.freq_key in ('1/半小时') then 48

                                 -- 每日多次/每几日几次
                                 when t.freq_key in ('5/日') then 5
                                 when t.freq_key in ('7/日') then 7
                                 when t.freq_key in ('1/3日') then 1 / 3
                                 when t.freq_key in ('4/5日') then 4 / 5
                                 when t.freq_key in ('3/5日') then 3 / 5

                                 -- 复杂频次：三餐前 + 三餐后 + 睡前，按 7 次/日估算
                                 when t.freq_key in ('三餐前三餐后睡前') then 7

                                 -- 如果 frequency 没匹配上，但 freq_counter/freq_interval 有值，则按频率字段换算
                                 when t.freq_counter is not null
                                  and t.freq_interval is not null
                                  and t.freq_interval > 0
                                  and upper(trim(t.freq_interval_unit)) in ('日', '天', 'D', 'DAY', 'DAYS')
                                 then t.freq_counter / t.freq_interval

                                 when t.freq_counter is not null
                                  and t.freq_interval is not null
                                  and t.freq_interval > 0
                                  and upper(trim(t.freq_interval_unit)) in ('小时', '时', 'H', 'HOUR', 'HOURS')
                                 then t.freq_counter * 24 / t.freq_interval

                                 when t.freq_counter is not null
                                  and t.freq_interval is not null
                                  and t.freq_interval > 0
                                  and upper(trim(t.freq_interval_unit)) in ('分钟', '分', 'MI', 'MIN', 'MINUTE', 'MINUTES')
                                 then t.freq_counter * 1440 / t.freq_interval

                                 when t.freq_counter is not null
                                  and t.freq_interval is not null
                                  and t.freq_interval > 0
                                  and upper(trim(t.freq_interval_unit)) in ('周', '星期', 'W', 'WEEK', 'WEEKS')
                                 then t.freq_counter / (t.freq_interval * 7)

                                 when t.freq_counter is not null
                                  and t.freq_interval is not null
                                  and t.freq_interval > 0
                                  and upper(trim(t.freq_interval_unit)) in ('月', 'M', 'MONTH', 'MONTHS')
                                 then t.freq_counter / (t.freq_interval * 30)

                                 -- 其他未知频次，暂按一次/日处理，避免必填字段为空
                                 else 1
                             end,
                             1
                         ),
                         2
                     ),
                     0
                 ),
                 999999.99
             ) as number(8,2)
         )
    else cast(null as number(8,2))
end as ORDER_DOSAGE,  --  医嘱用量    医生指导一日的用量，按剂量单位计

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
end as  /*  substr(
           nvl(
               (select dd.国标编码
                  from cda.cda_dictionary dd
                 where dd.字典名称 = '执行频次代码'
                   and dd.院标名称 = t.frequency
                   and rownum = 1),
               '99'
           ),
           1,
           10
       ) */ DRUG_FREQUENCY_CODE,-- 执行频率代码  是

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
end as  DRUG_FREQUENCY_NAME,-- 执行频率名称  是

       case
           when t.limit_class in (1, 2, 3) then '1'
           else '0'
       end as IS_ANTI,-- 是否为抗菌药物 是

      case
    when t.limit_class = 1 then '1'
    when t.limit_class = 2 then '2'
    when t.limit_class = 3 then '3'
    else '-'
end as ANTI_USE_GRADE_CODE,  -- 抗菌药物使用级别代码  是

       case
    when t.limit_class = 1 then '非限制使用'
    when t.limit_class = 2 then '限制使用'
    when t.limit_class = 3 then '特殊使用'
    else '-'
end as ANTI_USE_GRADE_NAME, -- 抗菌药物使用级别  是

       nvl(
           (select to_number(zd.国标编码)
              from cda.cda_dictionary zd
             where zd.字典名称 = '给药途径和方法代码'
               and zd.院标名称 = t.administration
               and regexp_like(zd.国标编码, '^[0-9]+$')
               and rownum = 1),
           9
       ) as DRUG_WAY_CD,-- 药物使用途径代码  是

       substr(
           nvl(
               (select zd.国标名称
                  from cda.cda_dictionary zd
                 where zd.字典名称 = '给药途径和方法代码'
                   and zd.院标名称 = t.administration
                   and rownum = 1),
               nvl(t.administration, '其他用药途径')
           ),
           1,
           20
       ) as DRUG_WAY_NAME,-- 药物使用途径名称  是

       case
           when t.limit_class in (1, 2, 3) then '2'
           else  '-'
        end as IF_YF,-- 用药目的代码  是 1：预防 2：治疗 3：预防+治疗；无专门字段时抗菌药暂按治疗

-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
       cast(null as varchar2(800)) as ODR_NOTE,--  医嘱备注说明

       substr(
           nvl(nvl(
               (select ks.qmpt_code
                  from his.dept_dict ks
                 where ks.dept_code = t.ordering_dept
                   and rownum = 1),
               t.ordering_dept
           ),'-'),
           1,
           15
       ) as DPT_CODE,--  开嘱科室编码  是

       substr(
           nvl(nvl(
               (select ks.qmpt_name
                  from his.dept_dict ks
                 where ks.dept_code = t.ordering_dept
                   and rownum = 1),
               nvl(
                   (select ks.dept_name
                      from his.dept_dict ks
                     where ks.dept_code = t.ordering_dept
                       and rownum = 1),
                   t.ordering_dept
               )
           ),'-'),
           1,
           50
       ) as DPT_NAME,--  开嘱科室名称  是

       substr(t.ordering_dept, 1, 20) as HOS_DPT_CODE,--  院内科室编码  是

       substr(
           nvl(
               (select ks.dept_name
                  from his.dept_dict ks
                 where ks.dept_code = t.ordering_dept
                   and rownum = 1),
               t.ordering_dept
           ),
           1,
           50
       ) as HOS_DPT_NAME,--  院内科室名称  是

       nvl(
           substr(
               (select sd.id_no
                  from his.staff_dict sd
                 where sd.emp_no = t.doctor_user
                   and rownum = 1),
               1,
               18
           ),
           '000000000000000000'
       ) as DOC_IDCARD,--  开嘱医生身份证号

       substr(
           nvl(
               (select sd.name
                  from his.staff_dict sd
                 where sd.emp_no = t.doctor_user
                   and rownum = 1),
               t.doctor
           ),
           1,
           50
       ) as DOC_NAME,--  开嘱医生姓名  是 　必填

       cast(nvl(t.create_data_time, nvl(t.enter_date_time, t.start_date_time)) as date) as ODRISU_DT,-- 医嘱下达时间  是 医嘱开立时间 yyyymmdd hh24miss

       cast(nvl(t.verify_data_time, t.start_date_time) as date) as BEGIN_TIME,--  医嘱开始执行时间    字符型改为时间类型

       substr(
           nvl(
               (select sd.name
                  from his.staff_dict sd
                 where sd.emp_no = t.nurse_user
                   and rownum = 1),
               t.nurse
           ),
           1,
           50
       ) as NURSE_NAME,--  执行护士姓名

       cast(
    nvl(
        t.last_perform_date_time,
        nvl(t.processing_date_time, nvl(t.verify_data_time, t.start_date_time))
    ) as date
)  as NUR_E_DT,--  护士执行时间  是 字符型改为时间类型

       cast(nvl(t.stop_date_time, t.cancel_date_time) as date) as STOP_DT,-- 医嘱停止执行时间    字符型改为时间类型

       substr(
           (select sd.id_no
              from his.staff_dict sd
             where sd.emp_no = nvl(nvl(t.stop_doctor_user, t.cancel_doctor), t.doctor_user)
               and rownum = 1),
           1,
           18
       ) as STPDOC_IDCARD,-- 停止执行医生身份证号

       substr(
           nvl(
               (select sd.name
                  from his.staff_dict sd
                 where sd.emp_no = nvl(nvl(t.stop_doctor_user, t.cancel_doctor), t.doctor_user)
                   and rownum = 1),
               nvl(t.stop_doctor, t.doctor)
           ),
           1,
           50
       ) as STPDOC_NAME,-- 停止执行医生姓名

       '49557032X' as ORG_CODE,--  医院组织机构代码  是 必填

       '山东省第二人民医院' as ORG_NAME,--  医院名称  是 必填

       '370104' as DISTRICT_CODE,-- 所属行政区划  是 必填

       'INSERT' as EXCHANGE_TYPE,-- 交换类型  是

       cast(systimestamp as timestamp) as SYSTEM_TIME,-- 数据上传时间戳 是 必填

      substr(
    t.patient_id || '_' || t.visit_id || '_' || nvl(to_char(t.current_presc_no), to_char(t.order_no)),
    1,
    20
)    as RECIPE_NUM,--  处方编号  是 必填，需要可以与药品数据集中的处方标识号进行关联，新增

       substr(nvl(t2.name, '-'), 1, 50) as NAME,--  患者姓名  是 通过比对国家数据集增加的数据项

       decode(t2.sex, '男', '1', '女', '2', '未知', '0', '9') as SEX_CODE,--  患者性别代码  是 通过比对国家数据集增加的数据项，值域：0未知，1男，2女，9不明

       substr(nvl(t2.id_no, '000000000000000000'), 1, 18) as ID_NUM,--  患者身份证件号码  是 通过比对国家数据集增加的数据项，全部身份证件号码填写到该字段

   substr(
    t.patient_id || '|' || t.visit_id || '|' || to_char(t.order_no) || '|' || to_char(t.order_sub_no),
    1,
    100
)    as ORDER_ID,--  医嘱流水号 是 通过比对国家数据集增加的数据项

       cast(null as varchar2(100)) as DTCODE,--  药品追溯码   通过比对国家数据集增加的数据项

       substr(t.insur_code, 1, 100) as NHSA_STANDARD_CODE,--  医保贯标码   通过比对国家数据集增加的数据项

       substr(
           nvl(
               (select yg.practice_cert_code
                  from doc_register_emp_match yg
                 where yg.emp_no = t.doctor_user
                   and rownum = 1),
               '-'
           ),
           1,
           100
       ) as ORDER_DOC_CERTIFICATE_NO,--  医嘱开立医生执业证书编号  是 通过比对国家数据集增加的数据项

       cast(null as varchar2(100)) as PRES_DECRIPTION,-- 中药处方描述    通过比对国家数据集增加的数据项

       case
    when t1.drug_indicator = 2 then '9'
    else null
end as TCM_DECOCTION_METHOD,--  中药饮片煎煮法   通过比对国家数据集增加的数据项

       cast(null as varchar2(100)) as TCM_USE_METHOD,--  中药用药方法    通过比对国家数据集增加的数据项

       case to_char(t.order_status)
           when '4' then '2' -- 作废：无效
           else '1'          -- 新开、执行、停止：有效
       end as ORDER_STATUS,--  医嘱有效标识  是 1.有效 2.无效，通过比对国家数据集增加的数据项

  substr(
    t.patient_id || '|' || t.visit_id || '|' || nvl(to_char(t.current_presc_no), to_char(t.order_no)),
    1,
    100
)   as PRES_ID,-- 处方流水号 是 通过比对国家数据集增加的数据项

       substr(
           nvl(
               (select yg.practice_cert_code
                  from doc_register_emp_match yg
                 where yg.emp_no = t.doctor_user
                   and rownum = 1),
               '-'
           ),
           1,
           100
       ) as PHYSICIAN_CERTIFICATE_NO --  处方开立医师执业证书编号  是 通过比对国家数据集增加的数据项

 from (
    select o.*,
           lower(
               trim(
                   replace(
                   replace(
                   replace(
                   replace(
                   replace(
                   replace(
                   replace(o.frequency, ' ', ''),
                                        '　', ''),
                                        '''', ''),
                                        '’', ''),
                                        '′', ''),
                                        '＇', ''),
                                        chr(9), '')
               )
           ) as freq_key
      from his.orders o
) t
left join  (
    select *
      from (
            select d.*,
                   row_number() over (
                       partition by d.drug_code
                       order by d.rowid
                   ) as rn
              from his.drug_dict d
           )
     where rn = 1
) t1
  on t.order_code = t1.drug_code
left join his.pat_master_index t2
       on t.patient_id = t2.patient_id
left join  his.MED_DICT_BASEINFO m on m.drug_id=t.ORDER_CODE
left join his.pat_visit pv
       on t.patient_id = pv.patient_id
      and t.visit_id = pv.visit_id
where t.order_class in ('A', 'B')
  and pv.discharge_date_time >= to_date('2021-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss')
  and pv.discharge_date_time <  to_date('2025-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss')
  and
  substr(nvl(  (select F004_YPID11_3  from DRUG_STANDARD_DICT  where F008_HIS_YAO_PIN_BIAN_MA=t.order_code and rownum=1)  , t.order_code ), 1, 100)  is not null
