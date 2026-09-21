
  CREATE OR REPLACE FORCE VIEW "ODS"."V_EMR_HOS_SUCCESSION_RECORD" ("ID", "ORG_CODE", "ORG_NAME", "DISTRICT_CODE", "EXCHANGE_TYPE", "SYSTEM_TIME", "RECORD_TYPE", "ADMISSION_UN_NUM", "DEPT_CODE", "DEP_NAME", "AREA_NAME", "WARD_NUM", "TREAT_NOTE", "PRESENT_SITUATION", "CURR_DIAG_WE_DIAG_CODE", "CURR_DIAG_WE_DIAG_NAME", "CURR_DIAG_CD_CODE", "CURR_DIAG_CD_NAME", "CURR_DIAG_CSYN_CODE", "CURR_DIAG_CSYN_NAME", "MATTERS_ATTENTION", "SUCCESSOR_DIAG_PLAN", "SUCCESSION_DATE", "SUCCESSION_NAME", "SUCCEED_NAME") AS 
  select substr(
           '49557032X'||'|'||nvl(x.patient_id, x.p_clinic_id)||'|'||x.p_inpatient_times||'|'||x.uhid||'|'||x.doc_id,
           1,
           100
       ) as ID,--  内码  是 主键

       '49557032X' as ORG_CODE,--  医院组织机构代码  是 必填

       '山东省第二人民医院' as ORG_NAME,--  医院名称  是 必填，

       '370104' as DISTRICT_CODE,-- 所属行政区划  是 按机构所在的行政区划（区县）

       'INSERT' as EXCHANGE_TYPE,-- 交换类型  是 INSERT：向平台传新数据时 UPDATE：向平台更新某条数据时 DELETE：从平台删除某条数据时 ADDHIS :向平台补充历史数据

       cast(systimestamp as timestamp) as SYSTEM_TIME,-- 数据上传时间戳 是

       case
         when regexp_like(x.content_text, '新入院|新入病人|新收') then '1'
         when regexp_like(x.content_text, '病重|病危|危重') then '2'
         when regexp_like(x.content_text, '手术|术前|术后') then '3'
         else '4'
       end as RECORD_TYPE,-- 交接类型  是 1：新入院患者交班2：病重患者 3：手术患者交班4：其他交班

       substr(
           nvl(x.patient_id||'|'||x.p_inpatient_times, x.p_inpatient_no||'|'||x.p_inpatient_times),
           1,
           50
       ) as ADMISSION_UN_NUM,--  住院唯一标示号 是

       nvl(
           (select ks.qmpt_code
              from his.dept_dict ks
             where ks.dept_code = x.p_dept_code
               and rownum = 1),
           x.p_dept_code
       ) as DEPT_CODE,-- 科室代码

       nvl(
           (select ks.qmpt_name
              from his.dept_dict ks
             where ks.dept_code = x.p_dept_code
               and rownum = 1),
           x.p_dept_name
       ) as DEP_NAME,--  科室名称

       x.p_are_name as AREA_NAME,-- 病区名称

       cast(null as varchar2(10)) as WARD_NUM,--  病房号

       substr(
           nvl(
               regexp_substr(
                   x.content_text,
                   '诊[[:space:]]*疗[[:space:]]*经[[:space:]]*过[[:space:]]*[:：][[:space:]]*(.*?)(目[[:space:]]*前[[:space:]]*情[[:space:]]*况|现[[:space:]]*病[[:space:]]*情|注[[:space:]]*意[[:space:]]*事[[:space:]]*项|接[[:space:]]*班[[:space:]]*诊[[:space:]]*疗[[:space:]]*计[[:space:]]*划|$)',
                   1, 1, 'n', 1
               ),
               nvl(x.content_text, '-')
           ),
           1,
           2000
       ) as TREAT_NOTE,--  诊疗过程描述

       substr(
           nvl(
               x.MQQK,
               nvl(
                   regexp_substr(
                       x.content_text,
                       '(目[[:space:]]*前[[:space:]]*情[[:space:]]*况|现[[:space:]]*病[[:space:]]*情|病[[:space:]]*情[[:space:]]*变[[:space:]]*化)[[:space:]]*[:：][[:space:]]*(.*?)(注[[:space:]]*意[[:space:]]*事[[:space:]]*项|接[[:space:]]*班[[:space:]]*诊[[:space:]]*疗[[:space:]]*计[[:space:]]*划|诊[[:space:]]*疗[[:space:]]*计[[:space:]]*划|$)',
                       1, 1, 'n', 2
                   ),
                   '-'
               )
           ),
           1,
           2000
       ) as PRESENT_SITUATION,-- 目前情况

       substr(x.diagnosis_code, 1, 12) as CURR_DIAG_WE_DIAG_CODE,--  目前诊断-西医诊断编码

       substr(x.diagnosis_desc, 1, 50) as CURR_DIAG_WE_DIAG_NAME,--  目前诊断-西医诊断名称

       cast(null as varchar2(12)) as CURR_DIAG_CD_CODE,-- 目前诊断-中医病名代码

       cast(null as varchar2(50)) as CURR_DIAG_CD_NAME,-- 目前诊断-中医病名名称

       cast(null as varchar2(12)) as CURR_DIAG_CSYN_CODE,-- 目前诊断-中医证候代码

       cast(null as varchar2(50)) as CURR_DIAG_CSYN_NAME,-- 目前诊断-中医证候名称

       substr(
           nvl(
               x.ZYSX,
               nvl(
                   regexp_substr(
                       x.content_text,
                       '注[[:space:]]*意[[:space:]]*事[[:space:]]*项[[:space:]]*[:：][[:space:]]*(.*?)(接[[:space:]]*班[[:space:]]*诊[[:space:]]*疗[[:space:]]*计[[:space:]]*划|交班医师|接班医师|医师签名|$)',
                       1, 1, 'n', 1
                   ),
                   '继续观察病情变化，按交接班要求处理。'
               )
           ),
           1,
           1000
       ) as MATTERS_ATTENTION,-- 注意事项

       substr(
           nvl(
               x.HAND_OVER_TREAT_PLAN,
               regexp_substr(
                   x.content_text,
                   '(接[[:space:]]*班[[:space:]]*诊[[:space:]]*疗[[:space:]]*计[[:space:]]*划|诊[[:space:]]*疗[[:space:]]*计[[:space:]]*划|下一步治疗计划|处理意见)[[:space:]]*[:：][[:space:]]*(.*?)(交班医师|接班医师|医师签名|$)',
                   1, 1, 'n', 2
               )
           ),
           1,
           1000
       ) as SUCCESSOR_DIAG_PLAN,-- 接班诊疗计划

cast(
  nvl(
    case
      when x.doc_finish_date is not null
       and x.doc_finish_date > date '1900-01-01'
      then x.doc_finish_date
    end,
    nvl(
      case
        when x.doc_title_time is not null
         and x.doc_title_time > date '1900-01-01'
        then x.doc_title_time
      end,
      nvl(
        case
          when x.createon is not null
           and x.createon > date '1900-01-01'
          then x.createon
        end,
        sysdate
      )
    )
  ) as date
) as SUCCESSION_DATE,-- 交接班日期

       substr(
           nvl(
               x.doc_sign_name,
               nvl(
                   (select sd.name
                      from his.staff_dict sd
                     where sd.emp_no = nvl(x.modifiedby, x.createby)
                       and rownum = 1),
                   nvl(
                       (select sd.name
                          from his.staff_dict sd
                         where sd.user_name = nvl(x.modifiedby, x.createby)
                           and rownum = 1),
                       nvl(x.modifiedby, x.createby)
                   )
               )
           ),
           1,
           50
       ) as SUCCESSION_NAME,-- 交班者签名

       substr(
           nvl(
               x.HAND_OVER_SIGN,
               regexp_substr(
                   x.content_text,
                   '(接班者签名|接班医师签名|接班医师)[[:space:]]*[:：][[:space:]]*([^[:cntrl:][:space:]]+)',
                   1, 1, 'n', 2
               )
           ),
           1,
           50
       ) as SUCCEED_NAME -- 接班者签名

from (
       select t.uhid,
              t.p_inpatient_no,
              t.p_inpatient_times,
              t.p_dept_code,
              t.p_dept_name,
              t.p_are_name,
              t.p_clinic_id,
              pmi.patient_id,
              t1.id as doc_id,
              t1.doc_title,
              t1.doc_type_name,
              t1.createon,
              t1.modifiedby,
              t1.createby,
              t1.doc_finish_date,
              t1.doc_title_time,
              t1.doc_sign_name,
              t3.MQQK,
              t3.ZYSX,
              dbms_lob.substr(t4.段落内容, 2000, 1) as content_text,

              (
                select max(j.HAND_OVER_TREAT_PLAN)
                  from cda.t_jbjl j
                 where j.OUTHOS_NO = t.p_clinic_id
                   and j.INHOS_NUM = t.p_inpatient_times
              ) as HAND_OVER_TREAT_PLAN,

              (
                select max(j.HAND_OVER_SIGN)
                  from cda.t_jbjl j
                 where j.OUTHOS_NO = t.p_clinic_id
                   and j.INHOS_NUM = t.p_inpatient_times
              ) as HAND_OVER_SIGN,

              (
                select max(d.diagnosis_code) keep (
                         dense_rank first order by d.diagnosis_date desc nulls last
                       )
                  from his.diagnosis d
                 where d.patient_id = pmi.patient_id
                   and d.visit_id = t.p_inpatient_times
                   and d.diagnosis_type = '3'
                   and d.diagnosis_no = '1'
              ) as diagnosis_code,

              (
                select max(d.diagnosis_desc) keep (
                         dense_rank first order by d.diagnosis_date desc nulls last
                       )
                  from his.diagnosis d
                 where d.patient_id = pmi.patient_id
                   and d.visit_id = t.p_inpatient_times
                   and d.diagnosis_type = '3'
                   and d.diagnosis_no = '1'
              ) as diagnosis_desc

         from mtl.EPR_INPATIENT_DOCINDEX t

         left join his.pat_master_index pmi
                on t.p_inpatient_no = pmi.inp_no

         inner join his.pat_visit pv
                 on pv.patient_id = pmi.patient_id
                and pv.visit_id = t.p_inpatient_times
                and pv.discharge_date_time >= to_date('2021-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss')
                and pv.discharge_date_time <  to_date('2025-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss')

         inner join mtl.EPR_INPATIENT t1
                 on t.UHID = t1.UHID
                /*and t1.DOC_STATS = '1'*/
                and t1.doc_title in ('交班记录')

         left join mtl.EMRSD41 T3
                on T3.段落编号 = T1.ID

         left join MTL.EMRSD_CONTENT t4
                on t4.UHID = t.UHID
               and t4.段落编号 = T1.ID
     ) x
