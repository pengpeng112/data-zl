
  CREATE OR REPLACE FORCE VIEW "ODS"."V_EMR_HOS_DND_RECORD" ("ID", "ORG_CODE", "ORG_NAME", "DISTRICT_CODE", "EXCHANGE_TYPE", "SYSTEM_TIME", "ADMISSION_ID", "DEP_NAME", "DEP_CODE", "AREA_NAME", "WARD_NUM", "SICKBED_NUM", "DISCUSS_DATE", "DISCUSS_ADDRESS", "HOET_NAME", "DISCUSS_PEOPLE_LIST", "PROF_TECH_CATE_CODE", "DIRECT_CAUSE_DEATH_NAME", "DIRECT_CAUSE_DEATH_CODE", "DEATH_DIAG_NAME", "DEATH_DIAG_CODE", "FAMILY_AGREE_AUTO_SIGN", "DEATH_DISCUSS_RECORD", "HOST_OPINION", "ATTENDING_PHYSICIAN_NAME", "CHIEF_DOCTOR_NAME", "SIGN_DATE") AS 
  select substr('49557032X'||'|'||t.uhid||'|'||t1.id, 1, 100) as ID,--  内码  是 主键

       '49557032X' as ORG_CODE,--  医院组织机构代码  是 必填、机构验证，有组织机构代码的传代码；无组织机构代码的上传编码

       '山东省第二人民医院' as ORG_NAME,--  医院名称  是 必填，填写标准医院名称，每次上传的医院名称必须一致

       '370104' as DISTRICT_CODE,-- 所属行政区划  是 按机构所在的行政区划（区县）

       'ADDHIS' as EXCHANGE_TYPE,-- 交换类型  是 INSERT：向平台传新数据时 UPDATE：向平台更新某条数据时 DELETE：从平台删除某条数据时 ADDHIS :向平台补充历史数据

       cast(systimestamp as timestamp) as SYSTEM_TIME,-- 数据上传时间戳 是

       substr(t.p_clinic_id||'|'||t.P_INPATIENT_TIMES, 1, 50) as ADMISSION_ID,--  住院唯一标示号 是

       t.p_dept_name as DEP_NAME,--  科室名称  是 按照医院内部名称填写

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

       nvl(
         to_date(
           regexp_substr(
             dbms_lob.substr(t4.段落内容, 2000, 1),
             '([0-9]{4}-[0-9]{1,2}-[0-9]{1,2}[[:space:]]+[0-9]{1,2}:[0-9]{2})[[:space:]]*[,，][[:space:]]*在',
             1, 1, 'n', 1
           ),
           'yyyy-mm-dd hh24:mi'
         ),
         cast(t1.doc_create_date as date)
       ) as DISCUSS_DATE,--  讨论日期时间  是 　YYYYMMDD HHMISS

       substr(
           nvl(t3.tldd, t1.Doc_Dept_Name||'医生办公室'),
           1,
           50
       ) as DISCUSS_ADDRESS,-- 讨论地点  是

     nvl(  substr(
         nvl(
           t3.Zcrxm,
           regexp_replace(
             regexp_substr(
               dbms_lob.substr(t4.段落内容, 2000, 1),
               '在[^,，。]{2,30}主持下',
               1, 1, 'n'
             ),
             '^在|主持下$|主任医师|副主任医师|主任|副主任|主治医师|医师',
             ''
           )
         ),
         1,
         50
       ),t1.MODIFIEDBY) as HOET_NAME,-- 主持人姓名 是

       substr(
         nvl(
           t3.Cjtlrymd,
           case
             when regexp_like(dbms_lob.substr(t4.段落内容, 2000, 1), '全科人员') then '全科人员'
             when regexp_like(dbms_lob.substr(t4.段落内容, 2000, 1), '医护人员') then '医护人员'
             else '-'
           end
         ),
         1,
         200
       ) as DISCUSS_PEOPLE_LIST,-- 参加讨论人员名单  是

       case
         when regexp_like(
                (select cd.国标编码
                   from cda.cda_dictionary cd
                  where cd.字典名称 = '专业技术职务类别代码'
                    and cd.院标名称 = (
                        select sd.TITLE
                          from his.staff_dict sd
                         where sd.name = nvl(
                                           t3.zcrxm,
                                           regexp_replace(
                                             regexp_substr(
                                               dbms_lob.substr(t4.段落内容, 2000, 1),
                                               '在[^,，。]{2,30}主持下',
                                               1, 1, 'n'
                                             ),
                                             '^在|主持下$|主任医师|副主任医师|主任|副主任|主治医师|医师',
                                             ''
                                           )
                                         )
                           and rownum = 1
                    )
                    and rownum = 1),
                '^[0-9]+$'
              )
         then to_number(
                (select cd.国标编码
                   from cda.cda_dictionary cd
                  where cd.字典名称 = '专业技术职务类别代码'
                    and cd.院标名称 = (
                        select sd.TITLE
                          from his.staff_dict sd
                         where sd.name = nvl(
                                           t3.zcrxm,
                                           regexp_replace(
                                             regexp_substr(
                                               dbms_lob.substr(t4.段落内容, 2000, 1),
                                               '在[^,，。]{2,30}主持下',
                                               1, 1, 'n'
                                             ),
                                             '^在|主持下$|主任医师|副主任医师|主任|副主任|主治医师|医师',
                                             ''
                                           )
                                         )
                           and rownum = 1
                    )
                    and rownum = 1)
              )
       end as PROF_TECH_CATE_CODE,-- 专业技术职务类别代码    主持人的职务类别代码

       substr(
         nvl(
           regexp_substr(
             dbms_lob.substr(t4.段落内容, 2000, 1),
             '死亡原因[[:space:]]*[:：][[:space:]]*(.*?)(死亡诊断[[:space:]]*[:：]|。|；|;)',
             1, 1, 'n', 1
           ),
           nvl(ddd.diagnosis_desc, dddd.diagnosis_desc)
         ),
         1,
         50
       ) as DIRECT_CAUSE_DEATH_NAME,-- 直接死亡原因名称

       case
         when regexp_like(dbms_lob.substr(t4.段落内容, 2000, 1), '死因不明') then '3'
         when regexp_like(dbms_lob.substr(t4.段落内容, 2000, 1), '非本病') then '2'
         when regexp_like(dbms_lob.substr(t4.段落内容, 2000, 1), '死亡原因|死亡诊断|诊断成立|抢救无效.*死亡') then '1'
         else null
       end as DIRECT_CAUSE_DEATH_CODE,-- 直接死亡原因编码    1：本病2：非本病3：死因不明

       substr(
         nvl(
           regexp_substr(
             dbms_lob.substr(t4.段落内容, 2000, 1),
             '死亡诊断[[:space:]]*[:：][[:space:]]*(.*?)(住院期间|治疗过程中|家属|$)',
             1, 1, 'n', 1
           ),
           nvl(ddd.diagnosis_desc, dddd.diagnosis_desc)
         ),
         1,
         50
       ) as DEATH_DIAG_NAME,-- 死亡诊断名称

       substr(
           nvl(ddd.diagnosis_code, dddd.diagnosis_code),
           1,
           11
       ) as DEATH_DIAG_CODE,-- 死亡诊断编码    导致死亡的疾病诊断编码

       case
         when regexp_like(dbms_lob.substr(t4.段落内容, 2000, 1), '拒绝.*尸检|拒绝.*尸体解剖|不同意.*尸检|不同意.*尸体解剖') then '0'
         when regexp_like(dbms_lob.substr(t4.段落内容, 2000, 1), '同意.*尸检|同意.*尸体解剖') then '1'
         else null
       end as FAMILY_AGREE_AUTO_SIGN,--  家属是否同意尸体解剖标志

       substr(
           nvl(
               nvl(t3.swtljl, dbms_lob.substr(t4.段落内容, 2000, 1)),
               '-'
           ),
           1,
           2000
       ) as DEATH_DISCUSS_RECORD,--  死亡讨论记录  是

       substr(
         nvl(
           t3.zcrzjyj,
           nvl(
             regexp_substr(
               dbms_lob.substr(t4.段落内容, 2000, 1),
               '(整个住院期间|住院期间治疗合理|分析患者病史)(.*)$',
               1, 1, 'n', 0
             ),
             dbms_lob.substr(t4.段落内容, 2000, 1)
           )
         ),
         1,
         2000
       ) as HOST_OPINION,--  主持人总结意见

       substr(
           nvl(
               (select sd.name
                  from his.staff_dict sd
                 where sd.emp_no = ttt.ATTENDING_DOCTOR
                   and rownum = 1),
               ttt.ATTENDING_DOCTOR
           ),
           1,
           50
       ) as ATTENDING_PHYSICIAN_NAME,--  主治医师签名  是 主治医师签名

       substr(
           nvl(
               (select sd.name
                  from his.staff_dict sd
                 where sd.emp_no = ttt.DIRECTOR
                   and rownum = 1),
               ttt.DIRECTOR
           ),
           1,
           50
       ) as CHIEF_DOCTOR_NAME,-- 主任医师姓名

       cast(nvl(t1.Modifiedon, t1.doc_create_date) as date) as SIGN_DATE -- 签名日期时间  是 　YYYYMMDD HHMISS

from mtl.EPR_INPATIENT_DOCINDEX t

inner join mtl.EPR_INPATIENT t1
   on t.UHID = t1.UHID
  /*and t1.DOC_STATS = '1'*/
  and ( t1.doc_type_name = '死亡病例讨论记录' or t1.doc_title like '%死亡病例讨论记录%')

inner join mtl.EMRSD51 T3
   on T3.段落编号 = T1.ID

left join MTL.EMRSD_CONTENT t4
   on t4.UHID = t.UHID
  and t4.段落编号 = t3.段落编号

left join his.pat_master_index tt
   on t.p_inpatient_no = tt.inp_no

left join his.pat_visit ttt
   on tt.patient_id = ttt.patient_id
  and t.P_INPATIENT_TIMES = ttt.visit_id

left join his.diagnosis ddd
   on tt.patient_id = ddd.patient_id
  and t.P_INPATIENT_TIMES = ddd.visit_id
  and ddd.diagnosis_type = '3'
  and ddd.diagnosis_no = '1'

left join his.diagnosis dddd
   on tt.patient_id = dddd.patient_id
  and t.P_INPATIENT_TIMES = dddd.visit_id
  and dddd.diagnosis_type = '3'
  and dddd.diagnosis_no = '2'

where ttt.discharge_date_time >= to_date('2021-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss')
  and ttt.discharge_date_time <  to_date('2025-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss')
