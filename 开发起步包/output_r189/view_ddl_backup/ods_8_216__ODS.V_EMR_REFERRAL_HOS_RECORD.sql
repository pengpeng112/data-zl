
  CREATE OR REPLACE FORCE VIEW "ODS"."V_EMR_REFERRAL_HOS_RECORD" ("ID", "ORG_CODE", "ORG_NAME", "DISTRICT_CODE", "EXCHANGE_TYPE", "SYSTEM_TIME", "HEALTH_RECORD_CODE", "PATIENT_TYPE", "VISTING_NUM", "REFERRAL_DATE", "REFERRAL_REASON", "REFERRAL_RECORD", "REFERRAL_DOC_NAME", "DISEASE_NAME", "DISEASE_CODE", "DIAG_DATE", "DIAG_ORG_NAME", "SYMPTOMS", "MAJOR_TREAT_MEASURES", "AUX_EXAM_RESULT", "OPERATION_CODE", "SURGERY_START_DATE", "TREAT_OPTIONS", "DISPOSAL_PLAN", "HEALTH_ASSESSMENT", "REHAB_MEASURES", "ROLL_OUT_ORG_CODE", "ROLL_OUT_ORG_NAME", "ROLL_OUT_DEP_NAME", "INTO_ORG_NAME", "INTO_DEP_NAME") AS 
  select substr('49557032X'||'|'||a.patient_id||'|'||a.visit_id, 1, 100) as ID,--  内码  是 主键

       '49557032X' as ORG_CODE,--  医院组织机构代码  是 必填、机构验证

       '山东省第二人民医院' as ORG_NAME,--  医院名称  是 必填

       '370104' as DISTRICT_CODE,-- 所属行政区划  是 按机构所在的行政区划（区县）

       'INSERT' as EXCHANGE_TYPE,-- 交换类型  是 INSERT：向平台传新数据时 UPDATE：向平台更新某条数据时 DELETE：从平台删除某条数据时 ADDHIS :向平台补充历史数据

       cast(systimestamp as timestamp) as SYSTEM_TIME,-- 数据上传时间戳 是

       cast(null as varchar2(18)) as HEALTH_RECORD_CODE,--  居民健康卡号

       '2' as PATIENT_TYPE,--  病人就诊类型  是 1:门（急）诊 2：住院

       substr(a.patient_id||'|'||a.visit_id, 1, 32) as VISTING_NUM,-- 就诊号 是 　住院唯一标识号，或者门诊唯一标识号

       cast(
           nvl(
               (
                 select max(b.log_date_time)
                   from his.adt_log b
                  where b.patient_id = a.patient_id
                    and b.visit_id = a.visit_id
                    and b.action = 'G'
               ),
               a.discharge_date_time
           ) as date
       ) as REFERRAL_DATE,-- 转诊(院)日期 是

       substr(
           nvl(
               case
                 when a.trans_hospital is not null then '因病情需要，转至'||a.trans_hospital||'进一步诊治'
               end,
               '因病情需要转院进一步诊治'
           ),
           1,
           100
       ) as REFERRAL_REASON,-- 转诊原因  是

       substr(
           nvl(
               case
                 when a.trans_hospital is not null then '患者本次住院后经诊疗评估，因病情需要，转至'||a.trans_hospital||'继续诊治。'
               end,
               '患者本次住院后经诊疗评估，因病情需要转院继续诊治。'
           ),
           1,
           2000
       ) as REFERRAL_RECORD,-- 转诊记录  是

       substr(
           nvl(
               (select yg.name
                  from his.staff_dict yg
                 where yg.emp_no = a.attending_doctor
                   and rownum = 1),
               a.attending_doctor
           ),
           1,
           50
       ) as REFERRAL_DOC_NAME,-- 转诊医师姓名  是

       substr(
           (
             select max(c.diagnosis_desc) keep (
                      dense_rank first order by c.diagnosis_date desc nulls last
                    )
               from his.diagnosis c
              where a.patient_id = c.patient_id
                and a.visit_id = c.visit_id
                and c.diagnosis_type = '3'
                and c.diagnosis_no = '1'
           ),
           1,
           200
       ) as DISEASE_NAME,--  疾病诊断名称    按照医院内部名称填写

       substr(
           (
             select max(c.diagnosis_code) keep (
                      dense_rank first order by c.diagnosis_date desc nulls last
                    )
               from his.diagnosis c
              where a.patient_id = c.patient_id
                and a.visit_id = c.visit_id
                and c.diagnosis_type = '3'
                and c.diagnosis_no = '1'
           ),
           1,
           20
       ) as DISEASE_CODE,--  疾病诊断编码    按照平台值域填写

       cast(
           (
             select max(c.diagnosis_date) keep (
                      dense_rank first order by c.diagnosis_date desc nulls last
                    )
               from his.diagnosis c
              where a.patient_id = c.patient_id
                and a.visit_id = c.visit_id
                and c.diagnosis_type = '3'
                and c.diagnosis_no = '1'
           ) as date
       ) as DIAG_DATE,-- 诊断日期

       '山东省第二人民医院' as DIAG_ORG_NAME,-- 诊断机构名称

       cast(null as varchar2(1000)) as SYMPTOMS,--  相关症状

       cast(null as varchar2(1000)) as MAJOR_TREAT_MEASURES,--  主要治疗措施

       cast(null as varchar2(1000)) as AUX_EXAM_RESULT,-- 辅助检査结果

           substr(
           (
             select max(c.OPERATION_CODE) keep (
                      dense_rank first order by c.OPERATING_DATE desc nulls last
                    )
               from his.operation c
              where a.patient_id = c.patient_id
                and a.visit_id = c.visit_id

                and c.OPERATION_NO = '1'
           ),
           1,
           12
       )    as OPERATION_CODE,--  手术及操作编码
 substr(
           (
             select max(c.OPERATING_DATE) keep (
                      dense_rank first order by c.OPERATING_DATE desc nulls last
                    )
               from his.operation c
              where a.patient_id = c.patient_id
                and a.visit_id = c.visit_id

                and c.OPERATION_NO = '1'
           ),
           1,
           15
       )     as SURGERY_START_DATE,--  手术及操作开始日期 时间

       cast(null as varchar2(1000)) as TREAT_OPTIONS,-- 治疗方案

       substr(
           nvl(
               case
                 when a.trans_hospital is not null then '转至'||a.trans_hospital||'继续诊治'
               end,
               '转院继续诊治'
           ),
           1,
           2000
       ) as DISPOSAL_PLAN,-- 处置计划

       substr(
           nvl(
               (
                 select max(c.diagnosis_desc) keep (
                          dense_rank first order by c.diagnosis_date desc nulls last
                        )
                   from his.diagnosis c
                  where a.patient_id = c.patient_id
                    and a.visit_id = c.visit_id
                    and c.diagnosis_type = '3'
                    and c.diagnosis_no = '1'
               ),
               '需转院进一步诊治'
           ),
           1,
           2000
       ) as HEALTH_ASSESSMENT,-- 健康问题评估

       cast(null as varchar2(100)) as REHAB_MEASURES,--  康复措施指导

       '49557032X' as ROLL_OUT_ORG_CODE,-- 转出医疗机构代码

       '山东省第二人民医院' as ROLL_OUT_ORG_NAME,-- 转出医疗机构名称

       substr(
           nvl(
               (select ks.dept_name
                  from his.dept_dict ks
                 where ks.dept_code = a.dept_discharge_from
                   and rownum = 1),
               a.dept_discharge_from
           ),
           1,
           50
       ) as ROLL_OUT_DEP_NAME,-- 转出医疗机构科室名称

       substr(nvl(a.trans_hospital, '其他医疗机构'), 1, 70) as INTO_ORG_NAME,--转入医疗机构名称

       cast(null as varchar2(50)) as INTO_DEP_NAME --转入医疗机构科室名称

from his.pat_visit a

where a.discharge_disposition = '2'

  and a.discharge_date_time >= to_date('2021-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss')
  and a.discharge_date_time <  to_date('2025-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss')
