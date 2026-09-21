
  CREATE OR REPLACE FORCE VIEW "ODS"."EMR_HOS_CHANGE_MAJOR_RECORD" ("ID", "ORG_CODE", "ORG_NAME", "DISTRICT_CODE", "EXCHANGE_TYPE", "SYSTEM_TIME", "ADMISSION_ID", "DEP_NAME", "DEP_CODE", "AREA_NAME", "WARD_NUM", "SICKBED_NUM", "TREAT_NOTE", "PRESENT_SITUATION", "CURR_DIAG_WE_DIAG_NAME", "CURR_DIAG_WE_DIAG_CODE", "CURR_DIAG_CD_NAME", "CURR_DIAG_CD_CODE", "CURR_DIAG_CSYN_NAME", "CURR_DIAG_CSYN_CODE", "CHANGE_MAJOR_PURPOSE", "IN_DIAG_TREAT_PLAN", "CH_MED_PRES_DAC", "TCM_DECOCTION_METHOD", "MEDICATION_METHOD", "MATTERS_ATTENTION", "TRANSFER_RECORD_TYPE", "ROLL_OUT_DATE", "ROLL_OUT_DEP_NAME", "ROLL_OUT_DOC_NAME", "INTO_DATE", "INTO_DEP_NAME", "INTO_DOC_NAME", "ROLL_OUT_DEP_CODE", "NAME", "SEX_CODE", "ID_NUM") AS 
  select substr(
           '49557032X'||'|'||nvl(x.patient_id, x.p_clinic_id)||'|'||x.p_inpatient_times||'|'||x.uhid||'|'||x.doc_id,
           1,
           100
       ) as ID,--  内码  是 主键

       '49557032X' as ORG_CODE,--  医院组织机构代码  是 必填

       '山东省第二人民医院' as ORG_NAME,--  医院名称  是 必填

       '370104' as DISTRICT_CODE,-- 所属行政区划  是 按机构所在的行政区划（区县）

       'ADDHIS' as EXCHANGE_TYPE,-- 交换类型  是 INSERT：向平台传新数据时 UPDATE：向平台更新某条数据时 DELETE：从平台删除某条数据时 ADDHIS :向平台补充历史数据

       cast(systimestamp as timestamp) as SYSTEM_TIME,-- 数据上传时间戳 是

       substr(
           nvl(x.patient_id||'|'||x.p_inpatient_times, x.p_inpatient_no||'|'||x.p_inpatient_times),
           1,
           50
       ) as ADMISSION_ID,--  住院唯一标示号 是

       nvl(
           (select dd.qmpt_name
              from his.dept_dict dd
             where dd.dept_code = x.p_dept_code
               and rownum = 1),
           x.p_dept_name
       ) as DEP_NAME,--  科室名称  是

       nvl(
           (select dd.qmpt_code
              from his.dept_dict dd
             where dd.dept_code = x.p_dept_code
               and rownum = 1),
           x.p_dept_code
       ) as DEP_CODE,--  科室代码    按平台值域填写

       x.p_are_name as AREA_NAME,-- 病区名称

       cast(null as varchar2(10)) as WARD_NUM,--  病房号

       substr(x.p_bedno, 1, 10) as SICKBED_NUM,-- 病床号

       substr(
           case
             when x.Zlgcms is not null then x.Zlgcms
             else regexp_substr(
                    x.content_text,
                    '诊[[:space:]]*疗[[:space:]]*经[[:space:]]*过[[:space:]]*[:：][[:space:]]*(.*?)(目[[:space:]]*前[[:space:]]*情[[:space:]]*况[[:space:]]*[:：]|目[[:space:]]*前[[:space:]]*诊[[:space:]]*断|转[[:space:]]*科[[:space:]]*目[[:space:]]*的|$)',
                    1, 1, 'n', 1
                  )
           end,
           1,
           2000
       ) as TREAT_NOTE,--  诊疗过程描述  是 诊疗过程描述

       substr(
           case
             when x.Mqqk is not null then x.Mqqk
             else regexp_substr(
                    x.content_text,
                    '目[[:space:]]*前[[:space:]]*情[[:space:]]*况[[:space:]]*[:：][[:space:]]*(.*?)(目[[:space:]]*前[[:space:]]*诊[[:space:]]*断|转[[:space:]]*科[[:space:]]*目[[:space:]]*的|转[[:space:]]*入[[:space:]]*诊[[:space:]]*疗[[:space:]]*计[[:space:]]*划|$)',
                    1, 1, 'n', 1
                  )
           end,
           1,
           2000
       ) as PRESENT_SITUATION,-- 目前情况  是


               x.diagnosis_desc       as CURR_DIAG_WE_DIAG_NAME,--  目前诊断-西医诊断名称

       substr(x.diagnosis_code, 1, 12) as CURR_DIAG_WE_DIAG_CODE,--  目前诊断-西医诊断编码   　按照省统一疾病编码

       cast(null as varchar2(50)) as CURR_DIAG_CD_NAME,-- 目前诊断-中医病名名称

       cast(null as varchar2(12)) as CURR_DIAG_CD_CODE,-- 目前诊断-中医病名代码

       cast(null as varchar2(50)) as CURR_DIAG_CSYN_NAME,-- 目前诊断-中医证候名称

       cast(null as varchar2(9)) as CURR_DIAG_CSYN_CODE,-- 目前诊断-中医证候代码

       substr(
           regexp_replace(
             case
               when x.Zkmd is not null then x.Zkmd
               else regexp_substr(
                      x.content_text,
                      '转[[:space:]]*科[[:space:]]*目[[:space:]]*的[及和]*注[[:space:]]*意[[:space:]]*事[[:space:]]*项[[:space:]]*[:：][[:space:]]*(.*?)(转[[:space:]]*入[[:space:]]*诊[[:space:]]*疗[[:space:]]*计[[:space:]]*划|医师签名|$)',
                      1, 1, 'n', 1
                    )
             end,
             '[；;。[:space:]]+$',
             ''
           ),
           1,
           200
       ) as CHANGE_MAJOR_PURPOSE,--  转科目的  是

       substr(
           regexp_replace(
             case
               when x.Zrzljh is not null then x.Zrzljh
               else regexp_substr(
                      x.content_text,
                      '转[[:space:]]*入[[:space:]]*诊[[:space:]]*疗[[:space:]]*计[[:space:]]*划[[:space:]]*[:：][[:space:]]*(.*?)(注意事项|医师签名|$)',
                      1, 1, 'n', 1
                    )
             end,
             '[[:space:]]+[一-龥]{2,4}[[:space:]]*$',
             ''
           ),
           1,
           2000
       ) as IN_DIAG_TREAT_PLAN,--  转入诊疗计划

       cast(null as varchar2(1000)) as CH_MED_PRES_DAC,-- 中药处方医嘱内容

       cast(null as varchar2(100)) as TCM_DECOCTION_METHOD,--  中药煎煮方法    中药煎煮方法

       cast(null as varchar2(100)) as MEDICATION_METHOD,-- 中药用药方法

       substr(
           nvl(
               regexp_substr(
                   x.content_text,
                   '注[[:space:]]*意[[:space:]]*事[[:space:]]*项[[:space:]]*[:：][[:space:]]*(.*?)(医师签名|$)',
                   1, 1, 'n', 1
               ),
               regexp_substr(
                   x.content_text,
                   '转[[:space:]]*科[[:space:]]*目[[:space:]]*的[及和]*注[[:space:]]*意[[:space:]]*事[[:space:]]*项[[:space:]]*[:：][[:space:]]*(.*?)(转[[:space:]]*入[[:space:]]*诊[[:space:]]*疗[[:space:]]*计[[:space:]]*划|医师签名|$)',
                   1, 1, 'n', 1
               )
           ),
           1,
           1000
       ) as MATTERS_ATTENTION,-- 注意事项

       case
         when x.doc_title like '%转出%' or regexp_like(x.content_text, '转出记录') then 1
         when x.doc_title like '%转入%' or regexp_like(x.content_text, '转入记录') then 2
         else 1
       end as TRANSFER_RECORD_TYPE,--  转科记录类型    　1:转出 2：转入

       cast(
           nvl(
             (
               select max(a.log_date_time) keep (
                        dense_rank first order by
                        abs(cast(a.log_date_time as date) - cast(x.createon as date)),
                        a.log_date_time
                    )
                 from his.adt_log a
                where a.patient_id = x.patient_id
                  and a.visit_id = x.p_inpatient_times
                  and a.action = 'E'
             ),
             x.createon
           ) as date
       ) as ROLL_OUT_DATE,-- 转出日期时间  是 　YYYYMMDD HHMISS

       substr(
           nvl(
             (
               select dd.dept_name
                 from his.dept_dict dd
                where dd.dept_code = (
                        select max(a.dept_code) keep (
                                   dense_rank first order by
                                   abs(cast(a.log_date_time as date) - cast(x.createon as date)),
                                   a.log_date_time
                               )
                          from his.adt_log a
                         where a.patient_id = x.patient_id
                           and a.visit_id = x.p_inpatient_times
                           and a.action = 'E'
                     )
                  and rownum = 1
             ),
             x.p_dept_name
           ),
           1,
           50
       ) as ROLL_OUT_DEP_NAME,-- 转出科室  是

       substr(
           (
             select sd.name
               from his.staff_dict sd
              where sd.emp_no = (
                      select max(a.operator_no) keep (
                                 dense_rank first order by
                                 abs(cast(a.log_date_time as date) - cast(x.createon as date)),
                                 a.log_date_time
                             )
                        from his.adt_log a
                       where a.patient_id = x.patient_id
                         and a.visit_id = x.p_inpatient_times
                         and a.action = 'E'
                   )
                and rownum = 1
           ),
           1,
           50
       ) as ROLL_OUT_DOC_NAME,-- 转出医师签名

       cast(
           nvl(
             (
               select max(a.log_date_time) keep (
                        dense_rank first order by
                        abs(cast(a.log_date_time as date) - cast(x.createon as date)),
                        a.log_date_time
                    )
                 from his.adt_log a
                where a.patient_id = x.patient_id
                  and a.visit_id = x.p_inpatient_times
                  and a.action = 'D'
             ),
             x.createon
           ) as date
       ) as INTO_DATE,-- 转入日期时间  是 　YYYYMMDD HHMISS

       substr(
           nvl(
             (
               select dd.dept_name
                 from his.dept_dict dd
                where dd.dept_code = (
                        select max(a.dept_code) keep (
                                   dense_rank first order by
                                   abs(cast(a.log_date_time as date) - cast(x.createon as date)),
                                   a.log_date_time
                               )
                          from his.adt_log a
                         where a.patient_id = x.patient_id
                           and a.visit_id = x.p_inpatient_times
                           and a.action = 'D'
                     )
                  and rownum = 1
             ),
             x.p_dept_name
           ),
           1,
           50
       ) as INTO_DEP_NAME,-- 转入科室  是

       substr(
           (
             select sd.name
               from his.staff_dict sd
              where sd.emp_no = (
                      select max(a.operator_no) keep (
                                 dense_rank first order by
                                 abs(cast(a.log_date_time as date) - cast(x.createon as date)),
                                 a.log_date_time
                             )
                        from his.adt_log a
                       where a.patient_id = x.patient_id
                         and a.visit_id = x.p_inpatient_times
                         and a.action = 'D'
                   )
                and rownum = 1
           ),
           1,
           50
       ) as INTO_DOC_NAME,-- 转入医师签名

       nvl(
           (
             select dd.qmpt_code
               from his.dept_dict dd
              where dd.dept_code = (
                      select max(a.dept_code) keep (
                                 dense_rank first order by
                                 abs(cast(a.log_date_time as date) - cast(x.createon as date)),
                                 a.log_date_time
                             )
                        from his.adt_log a
                       where a.patient_id = x.patient_id
                         and a.visit_id = x.p_inpatient_times
                         and a.action = 'E'
                   )
                and rownum = 1
           ),
           x.p_dept_code
       ) as ROLL_OUT_DEP_CODE,-- 转出科室代码  是 新增

       nvl(x.p_name, x.name) as NAME,--  患者姓名  是 通过比对国家数据集增加的数据项

       decode(nvl(x.p_sex, x.sex), '男', '1', '女', '2', '未知', '0', '9') as SEX_CODE,--  患者性别代码  是 值域：0未知，1男，2女，9不明，通过比对国家数据集增加的数据项

       nvl(x.id_no, '000000000000000000') as ID_NUM --  患者身份证件号码  是 全部身份证件号码填写到该字段

from (
       select t.uhid,
              t.p_inpatient_no,
              t.p_inpatient_times,
              t.p_dept_code,
              t.p_dept_name,
              t.p_are_name,
              t.p_bedno,
              t.p_name,
              t.p_sex,
              t.p_clinic_id,
              tt.patient_id,
              tt.name,
              tt.sex,
              tt.id_no,
              t1.id as doc_id,
              t1.doc_title,
              t1.doc_type_name,
              t1.createon,
              t3.Zlgcms,
              t3.Mqqk,
              t3.Zkmd,
              t3.Zrzljh,
              dbms_lob.substr(t4.段落内容, 2000, 1) as content_text,
              d.diagnosis_desc,
              d.diagnosis_code
         from mtl.EPR_INPATIENT_DOCINDEX t

         left join his.pat_master_index tt
                on t.p_inpatient_no = tt.inp_no

         inner join his.pat_visit pv
                 on pv.patient_id = tt.patient_id
                and pv.visit_id = t.p_inpatient_times
                and pv.discharge_date_time >= to_date('2021-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss')
                and pv.discharge_date_time <  to_date('2025-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss')

         inner join mtl.EPR_INPATIENT t1
                 on t.UHID = t1.UHID
                and t1.doc_type_name = '转科记录'

         left join mtl.EMRSD42 T3
                on T3.段落编号 = T1.ID

         left join MTL.EMRSD_CONTENT t4
                on t4.UHID = t.UHID
               and t4.段落编号 = T1.ID

         left join his.diagnosis d
                on d.patient_id = tt.patient_id
               and d.visit_id = t.p_inpatient_times
               and d.diagnosis_type = '3'
               and d.diagnosis_no = '1'
     ) x
