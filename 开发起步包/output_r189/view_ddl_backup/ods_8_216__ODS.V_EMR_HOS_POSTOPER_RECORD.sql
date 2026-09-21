
  CREATE OR REPLACE FORCE VIEW "ODS"."V_EMR_HOS_POSTOPER_RECORD" ("ID", "ORG_CODE", "ORG_NAME", "DISTRICT_CODE", "EXCHANGE_TYPE", "SYSTEM_TIME", "ADMISSION_ID", "DEP_NAME", "DEP_CODE", "AREA_NAME", "WARD_NUM", "SICKBED_NUM", "RECORD_DATE", "NOTES", "DOC_NAME", "SIGN_DATE") AS 
  select substr('49557032X'||'|'||t.uhid||'|'||t1.id, 1, 100) as ID,--  内码  是 主键

       '49557032X' as ORG_CODE,--  医院组织机构代码  是 必填

       '山东省第二人民医院' as ORG_NAME,--  医院名称  是 必填

       '370104' as DISTRICT_CODE,-- 所属行政区划  是

       'INSERT' as EXCHANGE_TYPE,-- 交换类型  是 INSERT：向平台传新数据时 UPDATE：向平台更新某条数据时 DELETE：从平台删除某条数据时 ADDHIS :向平台补充历史数据

       cast(to_date(to_char(sysdate, 'yyyy-mm-dd hh24:mi:ss'), 'yyyy-mm-dd hh24:mi:ss') as timestamp) as SYSTEM_TIME,-- 数据上传时间戳 是

       substr(t.p_clinic_id||'|'||t.P_INPATIENT_TIMES, 1, 50) as ADMISSION_ID,--  住院唯一标示号 是

       t.p_Dept_Name as DEP_NAME,--  科室名称  是 按医院内部名称填写

       nvl(
           (select ks.qmpt_code
              from his.dept_dict ks
             where ks.dept_code = t.p_dept_code
               and rownum = 1),
           t.p_dept_code
       ) as DEP_CODE,--  科室代码    按平台值域填写

       t.P_ARE_NAME as AREA_NAME,-- 病区名称

       cast(null as varchar2(10)) as WARD_NUM,--  病房号

       substr(t.p_Bedno, 1, 10) as SICKBED_NUM,-- 病床号

       to_date(to_char(t1.DOC_CREATE_DATE, 'yyyy-mm-dd hh24:mi:ss'), 'yyyy-mm-dd hh24:mi:ss') as RECORD_DATE,-- 记录日期时间

       DBMS_LOB.SUBSTR(t4.段落内容, 2000, 1) as NOTES,-- 记录内容  是

       nvl(t1.MODIFIEDBY, t1.CREATEBY) as DOC_NAME,--  医师签名

       to_date(to_char(t1.DOC_TITLE_TIME, 'yyyy-mm-dd hh24:mi:ss'), 'yyyy-mm-dd hh24:mi:ss') as SIGN_DATE  -- 签名日期时间  是

from mtl.EPR_INPATIENT_DOCINDEX t

inner JOIN mtl.EPR_INPATIENT t1
        on t.UHID = t1.UHID
       /*and t1.DOC_STATS = '1'*/
       and (t1.doc_type_name  like '%术后首次病程记录%' or t1.DOC_TITLE like '%术后首次病程记录%')

Join MTL.EMRSD_CONTENT t4
  On t4.UHID = t.UHID
 and t4.段落编号 = T1.ID

where exists (
      select 1
        from his.pat_visit pv
        left join his.pat_master_index pmi
          on pv.patient_id = pmi.patient_id
       where pmi.inp_no = t.p_Inpatient_No
         and pv.visit_id = t.P_INPATIENT_TIMES
         and pv.discharge_date_time >= to_date('2021-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss')
         and pv.discharge_date_time <  to_date('2025-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss')
)
