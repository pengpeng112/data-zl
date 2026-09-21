
  CREATE OR REPLACE FORCE VIEW "ODS"."V_EMR_ADMISSION_DEAD_RECORD_TF" ("ID", "ORG_CODE", "ORG_NAME", "DISTRICT_CODE", "EXCHANGE_TYPE", "SYSTEM_TIME", "ADMISSION_UN_NUM", "PATIENT_NAME", "ID_NUM", "SEX_CODE", "SEX_NAME", "AGE", "AGE_MONTH", "NATION_CODE", "NATION_NAME", "MARITAL_STATUS_CODE", "MARITAL_STATUS", "ADDRESS_PROV", "ADDRESS_CITY", "ADDRESS_COUNTRY", "ADDRESS_VILLAGE", "ADDRESS_HAMLET", "ADDRESS_HNUM", "JOB_CODE", "JOB_NAME", "REPRESENTOR_NAME", "DAP_CONTACT_CODE", "DAP_CONTACT_NAME", "IS_RELIABLE", "ADMISSION_DATE", "DEATH_TIME", "ADMISSION_SITUATION", "FOUR_DIAGNOSIS", "TREATMENT_METHOD", "IN_HOS_WE_DIAG_NAME", "IN_HOS_WE_DIAG_CODE", "IN_HOS_CH_DIAG_CD_NAME", "IN_HOS_CH_DIAG_CD_CODE", "IN_HOS_CH_DIAG_CSYN_NAME", "IN_HOS_CH_DIAG_CSYN_CODE", "TREAT_NOTE", "DEATH_CAUSE", "OUT_HOS_WE_DIAG_NAME", "OUT_HOS_WE_DIAG_CODE", "OUT_HOS_CH_DIAG_CD_NAME", "OUT_HOS_CH_DIAG_CD_CODE", "OUT_HOS_CH_DIAG_CSYN_NAME", "OUT_HOS_CH_DIAG_CSYN_CODE", "DIAGNOSIS_NAME", "RESIDENT_NAME", "ATTENDING_PHYSICIAN_NAME", "CHIEF_DOCTOR_NAME", "SIG_DATE") AS 
  select ID,
       ORG_CODE,
       ORG_NAME,
       DISTRICT_CODE,
       EXCHANGE_TYPE,
       SYSTEM_TIME,
       ADMISSION_UN_NUM,
       PATIENT_NAME,
       ID_NUM,
       SEX_CODE,
       SEX_NAME,
       AGE,
       AGE_MONTH,
       NATION_CODE,
       NATION_NAME,
       MARITAL_STATUS_CODE,
       MARITAL_STATUS,
       ADDRESS_PROV,
       ADDRESS_CITY,
       ADDRESS_COUNTRY,
       ADDRESS_VILLAGE,
       ADDRESS_HAMLET,
       ADDRESS_HNUM,
       JOB_CODE,
       JOB_NAME,
       REPRESENTOR_NAME,
       DAP_CONTACT_CODE,
       DAP_CONTACT_NAME,
       IS_RELIABLE,
       ADMISSION_DATE,
       DEATH_TIME,
       ADMISSION_SITUATION,
       FOUR_DIAGNOSIS,
       TREATMENT_METHOD,
       IN_HOS_WE_DIAG_NAME,
       IN_HOS_WE_DIAG_CODE,
       IN_HOS_CH_DIAG_CD_NAME,
       IN_HOS_CH_DIAG_CD_CODE,
       IN_HOS_CH_DIAG_CSYN_NAME,
       IN_HOS_CH_DIAG_CSYN_CODE,
       TREAT_NOTE,
       DEATH_CAUSE,
       OUT_HOS_WE_DIAG_NAME,
       OUT_HOS_WE_DIAG_CODE,
       OUT_HOS_CH_DIAG_CD_NAME,
       OUT_HOS_CH_DIAG_CD_CODE,
       OUT_HOS_CH_DIAG_CSYN_NAME,
       OUT_HOS_CH_DIAG_CSYN_CODE,
       DIAGNOSIS_NAME,
       RESIDENT_NAME,
       ATTENDING_PHYSICIAN_NAME,
       CHIEF_DOCTOR_NAME,
       SIG_DATE
from (
    select q.*,
           row_number() over (
               partition by q.ID
               order by q.SIG_DATE desc nulls last,
                        q.DEATH_TIME desc nulls last
           ) as rn
    from (
        select substr(
                   '49557032X'||'|'||
                   nvl(to_char(tt.patient_id), '-')||'|'||
                   nvl(to_char(t.p_inpatient_times), '-'),
                   1,
                   100
               ) as ID,--  内码  是 主键

               '49557032X' as ORG_CODE,--  医院组织机构代码  是 必填、机构验证，

               '山东省第二人民医院' as ORG_NAME,--  医院名称  是 必填，填写标准医院名称

               '370104' as DISTRICT_CODE,-- 所属行政区划  是 按机构所在的行政区划（区县）

               'ADDHIS' as EXCHANGE_TYPE,-- 交换类型 INSERT：向平台传新数据时；UPDATE：向平台更新某条数据时；DELETE：从平台删除某条数据时；ADDHIS :向平台补充历史数据

               cast(systimestamp as timestamp) as SYSTEM_TIME,-- 数据上传时间戳 是

               substr(
                   nvl(to_char(tt.patient_id), '-')||'|'||nvl(to_char(t.p_inpatient_times), '-'),
                   1,
                   50
               ) as ADMISSION_UN_NUM,--  住院唯一标识号 是

               substr(
                   nvl(
                       nullif(trim(cast(ar.name as varchar2(50))), ''),
                       nvl(nullif(trim(cast(tt.name as varchar2(50))), ''), '-')
                   ),
                   1,
                   50
               ) as PATIENT_NAME,--  患者姓名  是

               substr(
                   nvl(
                       nullif(trim(cast(ar.id_num as varchar2(18))), ''),
                       nvl(nullif(trim(cast(tt.id_no as varchar2(18))), ''), '000000000000000000')
                   ),
                   1,
                   18
               ) as ID_NUM,--  患者身份证号码 是

               case
                   when to_char(ar.sex_code) in ('0', '1', '2', '9') then to_number(ar.sex_code)
                   when cast(tt.sex as varchar2(10)) = '男' then 1
                   when cast(tt.sex as varchar2(10)) = '女' then 2
                   when cast(tt.sex as varchar2(10)) = '未知' then 0
                   else 9
               end as SEX_CODE,--  性别代码  是

               substr(
                   nvl(
                       nullif(trim(cast(ar.sex_name as varchar2(11))), ''),
                       case
                           when cast(tt.sex as varchar2(10)) = '男' then '男'
                           when cast(tt.sex as varchar2(10)) = '女' then '女'
                           when cast(tt.sex as varchar2(10)) = '未知' then '未知'
                           else '不明'
                       end
                   ),
                   1,
                   11
               ) as SEX_NAME,--  性别名称  是

               case
                   when ar.age between 0 and 200 then ar.age
                   when tt.date_of_birth is not null
                    and ttt.admission_date_time is not null
                   then least(
                            greatest(
                                trunc(months_between(ttt.admission_date_time, tt.date_of_birth) / 12),
                                0
                            ),
                            200
                        )
                   else 0
               end as AGE,-- 年龄(岁) 是 0-200

               substr(
                   case
                       when ar.age_month is not null and to_char(ar.age_month) <> '0'
                       then to_char(ar.age_month)
                       when tt.date_of_birth is not null
                        and ttt.admission_date_time is not null
                        and months_between(ttt.admission_date_time, tt.date_of_birth) < 12
                       then to_char(greatest(trunc(months_between(ttt.admission_date_time, tt.date_of_birth)), 0))
                       else null
                   end,
                   1,
                   8
               ) as AGE_MONTH,-- 年龄(月)

               substr(
    nvl(
        nullif(trim(cast(ar.nation_code as varchar2(2))), ''),
        case regexp_replace(trim(nvl(cast(tt.nation as varchar2(50)), '')), '[[:space:]]+', '')
            when '01' then '01'
            when '1' then '01'
            when '汉' then '01'
            when '汉族' then '01'
            else cast(null as varchar2(2))
        end
    ),
    1,
    2
)  as NATION_CODE,-- 民族代码 按照平台值域填写

               substr(
    nvl(
        nullif(trim(cast(ar.nation_name as varchar2(50))), ''),
        case regexp_replace(trim(nvl(cast(tt.nation as varchar2(50)), '')), '[[:space:]]+', '')
            when '01' then '汉族'
            when '1' then '汉族'
            when '汉' then '汉族'
            when '汉族' then '汉族'
            else cast(null as varchar2(50))
        end
    ),
    1,
    50
)  as NATION_NAME,-- 民族名称

              substr(
    case
        when cast(ar.marital_status_code as varchar2(10)) in ('10','20','30','40','90')
        then cast(ar.marital_status_code as varchar2(10))

        when cast(ar.marital_status_code as varchar2(10)) = '1' then '10'
        when cast(ar.marital_status_code as varchar2(10)) = '2' then '20'
        when cast(ar.marital_status_code as varchar2(10)) = '3' then '30'
        when cast(ar.marital_status_code as varchar2(10)) = '4' then '40'

        when cast(tt.marital_status as varchar2(50)) in ('1','未婚') then '10'
        when cast(tt.marital_status as varchar2(50)) in ('2','已婚','再婚') then '20'
        when cast(tt.marital_status as varchar2(50)) in ('3','丧偶') then '30'
        when cast(tt.marital_status as varchar2(50)) in ('4','离婚','离异') then '40'
        else '90'
    end,
    1,
    2
)       as MARITAL_STATUS_CODE,-- 婚姻状况代码 按照平台值域填写

        substr(
    case
        when cast(ar.marital_status_code as varchar2(10)) in ('10','1') then '未婚'
        when cast(ar.marital_status_code as varchar2(10)) in ('20','2') then '已婚'
        when cast(ar.marital_status_code as varchar2(10)) in ('30','3') then '丧偶'
        when cast(ar.marital_status_code as varchar2(10)) in ('40','4') then '离婚'

        when cast(tt.marital_status as varchar2(50)) in ('1','未婚') then '未婚'
        when cast(tt.marital_status as varchar2(50)) in ('2','已婚','再婚') then '已婚'
        when cast(tt.marital_status as varchar2(50)) in ('3','丧偶') then '丧偶'
        when cast(tt.marital_status as varchar2(50)) in ('4','离婚','离异') then '离婚'
        else '未说明的婚姻状况'
    end,
    1,
    50
)   as MARITAL_STATUS,--  婚姻状况

               substr(ar.province, 1, 70) as ADDRESS_PROV,--  地址-省（自治区、直辖市）

               substr(ar.city, 1, 70) as ADDRESS_CITY,--  地址-市（地区、州）

               substr(ar.county, 1, 70) as ADDRESS_COUNTRY,-- 地址-县（区）

               substr(ar.town, 1, 70) as ADDRESS_VILLAGE,-- 地址-乡（镇、街道办事处）

               substr(ar.village, 1, 70) as ADDRESS_HAMLET,--  地址-村（街、路、弄）

               substr(ar.house_num, 1, 70) as ADDRESS_HNUM,--  地址-门牌号码

               substr(ar.occupation_code, 1, 20) as JOB_CODE,--  职业类别代码

               substr(ar.occupation_name, 1, 50) as JOB_NAME,--  职业类别名称

       substr(
    nvl(
        nullif(
            trim(
                case
                    when ar.representor_name is not null
                     and not regexp_like(
                             trim(cast(ar.representor_name as varchar2(200))),
                             '^(主诉|现病史|辅助检查|查体)[[:space:]]*[:：]'
                         )
                    then cast(ar.representor_name as varchar2(50))
                    else null
                end
            ),
            ''
        ),
        nvl(
            nullif(
                trim(
                    regexp_substr(
                        cast(dbms_lob.substr(t4.段落内容, 1000, 1) as varchar2(1000)),
                        '病史陈述者[[:space:]]*[:：][[:space:]]*([^。；;\r\n]{1,50})',
                        1, 1, 'n', 1
                    )
                ),
                ''
            ),
            '-'
        )
    ),
    1,
    50
)     as REPRESENTOR_NAME,--  病史陈述者姓名

               substr(
                   nvl(
                       ar.linkman_relation_code,
                       case
                           when regexp_like(
                                    regexp_substr(
                                        cast(dbms_lob.substr(t4.段落内容, 1000, 1) as varchar2(1000)),
                                        '病史陈述者[[:space:]]*[:：][[:space:]]*([^[:cntrl:]]+)',
                                        1, 1, 'n', 1
                                    ),
                                    '本人|患者本人'
                                ) then '0'
                           when regexp_like(
                                    regexp_substr(
                                        cast(dbms_lob.substr(t4.段落内容, 1000, 1) as varchar2(1000)),
                                        '病史陈述者[[:space:]]*[:：][[:space:]]*([^[:cntrl:]]+)',
                                        1, 1, 'n', 1
                                    ),
                                    '配偶|丈夫|妻子|妻|夫|老伴|爱人'
                                ) then '1'
                           when regexp_like(
                                    regexp_substr(
                                        cast(dbms_lob.substr(t4.段落内容, 1000, 1) as varchar2(1000)),
                                        '病史陈述者[[:space:]]*[:：][[:space:]]*([^[:cntrl:]]+)',
                                        1, 1, 'n', 1
                                    ),
                                    '儿子|之子|其子|患儿父亲|父亲陪同'
                                ) then '2'
                           when regexp_like(
                                    regexp_substr(
                                        cast(dbms_lob.substr(t4.段落内容, 1000, 1) as varchar2(1000)),
                                        '病史陈述者[[:space:]]*[:：][[:space:]]*([^[:cntrl:]]+)',
                                        1, 1, 'n', 1
                                    ),
                                    '女儿|之女|其女'
                                ) then '3'
                           when regexp_like(
                                    regexp_substr(
                                        cast(dbms_lob.substr(t4.段落内容, 1000, 1) as varchar2(1000)),
                                        '病史陈述者[[:space:]]*[:：][[:space:]]*([^[:cntrl:]]+)',
                                        1, 1, 'n', 1
                                    ),
                                    '孙子|孙女|外孙|外孙子|外孙女'
                                ) then '4'
                           when regexp_like(
                                    regexp_substr(
                                        cast(dbms_lob.substr(t4.段落内容, 1000, 1) as varchar2(1000)),
                                        '病史陈述者[[:space:]]*[:：][[:space:]]*([^[:cntrl:]]+)',
                                        1, 1, 'n', 1
                                    ),
                                    '父亲|母亲|父母|患儿母亲|患儿父亲'
                                ) then '5'
                           when regexp_like(
                                    regexp_substr(
                                        cast(dbms_lob.substr(t4.段落内容, 1000, 1) as varchar2(1000)),
                                        '病史陈述者[[:space:]]*[:：][[:space:]]*([^[:cntrl:]]+)',
                                        1, 1, 'n', 1
                                    ),
                                    '祖父|祖母|爷爷|奶奶|外祖父|外祖母|外公|外婆'
                                ) then '6'
                           when regexp_like(
                                    regexp_substr(
                                        cast(dbms_lob.substr(t4.段落内容, 1000, 1) as varchar2(1000)),
                                        '病史陈述者[[:space:]]*[:：][[:space:]]*([^[:cntrl:]]+)',
                                        1, 1, 'n', 1
                                    ),
                                    '哥哥|弟弟|姐姐|妹妹|兄|弟|姐|妹|兄弟|姐妹'
                                ) then '7'
                           else '8'
                       end
                   ),
                   1,
                   2
               ) as DAP_CONTACT_CODE,--  陈述者与患者的关系代码

             substr(
    case
        when ar.linkman_relation_name is not null
         and not regexp_like(
                 trim(cast(ar.linkman_relation_name as varchar2(200))),
                 '^(主诉|现病史|辅助检查|查体)[[:space:]]*[:：]'
             )
        then cast(ar.linkman_relation_name as varchar2(50))

        when regexp_like(
                 regexp_substr(
                     cast(dbms_lob.substr(t4.段落内容, 1000, 1) as varchar2(1000)),
                     '病史陈述者[[:space:]]*[:：][[:space:]]*([^。；;\r\n]{1,50})',
                     1, 1, 'n', 1
                 ),
                 '本人|患者本人'
             )
        then '本人'

        when regexp_like(
                 regexp_substr(
                     cast(dbms_lob.substr(t4.段落内容, 1000, 1) as varchar2(1000)),
                     '病史陈述者[[:space:]]*[:：][[:space:]]*([^。；;\r\n]{1,50})',
                     1, 1, 'n', 1
                 ),
                 '配偶|丈夫|妻子|妻|夫|老伴|爱人'
             )
        then '配偶'

        when regexp_like(
                 regexp_substr(
                     cast(dbms_lob.substr(t4.段落内容, 1000, 1) as varchar2(1000)),
                     '病史陈述者[[:space:]]*[:：][[:space:]]*([^。；;\r\n]{1,50})',
                     1, 1, 'n', 1
                 ),
                 '儿子|之子|其子|患儿父亲|父亲陪同'
             )
        then '儿子'

        when regexp_like(
                 regexp_substr(
                     cast(dbms_lob.substr(t4.段落内容, 1000, 1) as varchar2(1000)),
                     '病史陈述者[[:space:]]*[:：][[:space:]]*([^。；;\r\n]{1,50})',
                     1, 1, 'n', 1
                 ),
                 '女儿|之女|其女'
             )
        then '女儿'

        when regexp_like(
                 regexp_substr(
                     cast(dbms_lob.substr(t4.段落内容, 1000, 1) as varchar2(1000)),
                     '病史陈述者[[:space:]]*[:：][[:space:]]*([^。；;\r\n]{1,50})',
                     1, 1, 'n', 1
                 ),
                 '家属'
             )
        then '家属'

        else '-'
    end,
    1,
    50
) as DAP_CONTACT_NAME,--  陈述者人与患者的关系名称

               case
                   when ar.is_reliable in ('0', '1') then ar.is_reliable
                   when dbms_lob.instr(t4.段落内容, '病史记录属实', 1, 1) > 0 then '1'
                   else '0'
               end as IS_RELIABLE,-- 陈述内容可靠标志 1：是 0:否

               cast(
                   nvl(ar.admission_date, ttt.admission_date_time)
                   as date
               ) as ADMISSION_DATE,--  入院日期时间  是 YYYYMMDD HHMISS

               cast(
                   nvl(sw.swsj, ttt.discharge_date_time)
                   as date
               ) as DEATH_TIME,--  死亡日期时间  是 死亡日期时间 YYYYMMDD HHMISS

               substr(
                   nvl(
                       nullif(trim(cast(t3.ryqk as varchar2(2000))), ''),
                       nvl(nullif(trim(cast(ar.present_illness as varchar2(2000))), ''), '-')
                   ),
                   1,
                   2000
               ) as ADMISSION_SITUATION,-- 入院情况  是 入院情况

               substr(ar.four_diagnosis, 1, 1000) as FOUR_DIAGNOSIS,--  中医“四诊”观察结果

               substr(
                   nvl(ar.therapeutic_treatment, t3.zzzf),
                   1,
                   100
               ) as TREATMENT_METHOD,--  治则治法

               substr(
                   nvl(cast(d2.diagnosis_desc as varchar2(50)), cast(d1.diagnosis_desc as varchar2(50))),
                   1,
                   50
               ) as IN_HOS_WE_DIAG_NAME,-- 入院诊断-西医诊断名称

               substr(
                   nvl(cast(d2.diagnosis_code as varchar2(50)), cast(d1.diagnosis_code as varchar2(50))),
                   1,
                   50
               ) as IN_HOS_WE_DIAG_CODE,-- 入院诊断-西医诊断编码

               cast(null as varchar2(50)) as IN_HOS_CH_DIAG_CD_NAME,--  入院诊断-中医病名名称

               cast(null as varchar2(9)) as IN_HOS_CH_DIAG_CD_CODE,--  入院诊断-中医病名代码

               cast(null as varchar2(50)) as IN_HOS_CH_DIAG_CSYN_NAME,--  入院诊断-中医证候名称

               cast(null as varchar2(9)) as IN_HOS_CH_DIAG_CSYN_CODE,--  入院诊断-中医证候代码

               substr(
                   nvl(nullif(trim(cast(t3.zlgcms as varchar2(2000))), ''), '-'),
                   1,
                   2000
               ) as TREAT_NOTE,--  诊疗过程描述

               substr(
                   nvl(
                       nullif(trim(cast(t3.swyy as varchar2(100))), ''),
                       nvl(nullif(trim(cast(dd.diagnosis_desc as varchar2(100))), ''), '-')
                   ),
                   1,
                   100
               ) as DEATH_CAUSE,-- 死亡原因  是 死亡原因,直接死亡原因

               substr(cast(dd.diagnosis_desc as varchar2(50)), 1, 50) as OUT_HOS_WE_DIAG_NAME,--  死亡诊断-西医诊断名称

               substr(cast(dd.diagnosis_code as varchar2(50)), 1, 50) as OUT_HOS_WE_DIAG_CODE,--  死亡诊断-西医诊断编码

               cast(null as varchar2(50)) as OUT_HOS_CH_DIAG_CD_NAME,-- 死亡诊断-中医病名名称

               cast(null as varchar2(9)) as OUT_HOS_CH_DIAG_CD_CODE,-- 死亡诊断-中医病名代码

               cast(null as varchar2(50)) as OUT_HOS_CH_DIAG_CSYN_NAME,-- 死亡诊断-中医证候名称

               cast(null as varchar2(9)) as OUT_HOS_CH_DIAG_CSYN_CODE,-- 死亡诊断-中医证候代码

               substr(
                   nvl(
                       ar.doctor_name,
                       nvl(
                           (select cast(sd.name as varchar2(50))
                              from his.staff_dict sd
                             where sd.emp_no = nvl(ttt.attending_doctor, ttt.doctor_in_charge)
                               and rownum = 1),
                           '-'
                       )
                   ),
                   1,
                   50
               ) as DIAGNOSIS_NAME,--  接诊医师签名

               substr(
                   nvl(
                       ar.doctor_name,
                       nvl(
                           (select cast(sd.name as varchar2(50))
                              from his.staff_dict sd
                             where sd.emp_no = nvl(ttt.attending_doctor, ttt.doctor_in_charge)
                               and rownum = 1),
                           '-'
                       )
                   ),
                   1,
                   50
               ) as RESIDENT_NAME,-- 住院医师签名

               substr(
                   nvl(
                       ar.attending_doctor_name,
                       nvl(
                           ar.doctor_name,
                           nvl(
                               (select cast(sd.name as varchar2(50))
                                  from his.staff_dict sd
                                 where sd.emp_no = nvl(ttt.attending_doctor, ttt.doctor_in_charge)
                                   and rownum = 1),
                               '-'
                           )
                       )
                   ),
                   1,
                   50
               ) as ATTENDING_PHYSICIAN_NAME,--  主治医师签名  是 主治医师签名

               substr(
                   nvl(
                       ar.chief_doctor_name,
                       (select cast(sd.name as varchar2(50))
                          from his.staff_dict sd
                         where sd.emp_no = ttt.director
                           and rownum = 1)
                   ),
                   1,
                   50
               ) as CHIEF_DOCTOR_NAME,-- 主任医师签名

           cast(
    case
        when t1.doc_title_time is not null
         and nvl(sw.swsj, ttt.discharge_date_time) is not null
         and t1.doc_title_time - nvl(sw.swsj, ttt.discharge_date_time) <= 1
        then t1.doc_title_time
        else nvl(sw.swsj, ttt.discharge_date_time)
    end
    as date
)   as SIG_DATE -- 签名日期  是

        from mtl.epr_inpatient_docindex t

        inner join mtl.epr_inpatient t1
                on t.uhid = t1.uhid
               and cast(t1.doc_type_name as varchar2(100)) = '24小时内入院死亡记录'

        left join mtl.emrsd36 t3
               on t3.段落编号 = t1.id

        join mtl.emrsd_content t4
             on t4.uhid = t1.uhid
            and t4.段落编号 = t1.id

        left join his.pat_master_index tt
               on t.p_inpatient_no = tt.inp_no

        left join his.pat_visit ttt
               on tt.patient_id = ttt.patient_id
              and t.p_inpatient_times = ttt.visit_id

        left join v_emr_admission_record ar
               on ar.admission_id = tt.patient_id||'|'||t.p_inpatient_times

        left join his.diagnosis d2
               on ttt.patient_id = d2.patient_id
              and ttt.visit_id = d2.visit_id
              and d2.diagnosis_type = '2'
              and d2.diagnosis_no = '1'

        left join his.diagnosis d1
               on ttt.patient_id = d1.patient_id
              and ttt.visit_id = d1.visit_id
              and d1.diagnosis_type = '1'
              and d1.diagnosis_no = '1'

        left join his.diagnosis dd
               on ttt.patient_id = dd.patient_id
              and ttt.visit_id = dd.visit_id
              and dd.diagnosis_type = '3'
              and dd.diagnosis_no = '1'

        left join ( select sw.patient_id,
           sw.visit_id,
           min(sw.start_date_time) as swsj
      from his.orders sw
     where sw.order_text like '%临床死亡%'
       and sw.order_class = 'Z'
       and sw.order_status in ('2', '6')
     group by sw.patient_id, sw.visit_id
        ) sw
               on ttt.patient_id = sw.patient_id
              and ttt.visit_id = sw.visit_id

        where ttt.discharge_date_time >= to_date('2021-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss')
          and ttt.discharge_date_time <  to_date('2025-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss')
          and nvl(sw.swsj, ttt.discharge_date_time) is not null
          and ttt.admission_date_time is not null
          and nvl(sw.swsj, ttt.discharge_date_time) >= ttt.admission_date_time
          and nvl(sw.swsj, ttt.discharge_date_time) <  ttt.admission_date_time + 1
    ) q
)
where rn = 1
