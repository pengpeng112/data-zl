
  CREATE OR REPLACE FORCE VIEW "ODS"."V_EMR_HOS_PREOP_DISCUSS" ("ID", "ORG_CODE", "ORG_NAME", "DISTRICT_CODE", "EXCHANGE_TYPE", "SYSTEM_TIME", "ADMISSION_ID", "DEP_NAME", "DEP_CODE", "AREA_NAME", "WARD_NUM", "SICKBED_NUM", "DISCUSS_DATE", "DISCUSS_ADDRESS", "HOET_NAME", "DISCUSS_PEOPLE_LIST", "PROF_TECH_CATE_CODE", "MEDICAL_RECORDS_SUNNARY", "BEFOPER_DCODE", "BEFOPER_DNAME", "DIAGNOSIS_BASIS", "ALLERGY_HISTORY_MARK", "ALLERGY_HISTORY", "AUX_EXAM_RESULT", "SURGICAL_INDICATION", "SURGICAL_CONTRIANDICATIONS", "PERFORM_OPERATION_NAME", "PERFORM_OPERATION_CODE", "PERFORM_OPERATION_PART_NAME", "PERFORM_OPERATION_DATE", "PERFORM_ANES_CODE", "OPERATION_MAIN_POINTS", "PREOPERATIVE_PREPARATION", "SURGICAL_INDICATIONS", "OPERATION_SCHEME", "MATTERS_ATTENTION", "DISCUSS_OPINION", "DISCUSS_CONCLUSION", "SURGERY_NAME", "ANAE_DOCTOR_NAME", "DOC_NAME", "SIGN_DATE") AS 
  select substr(
           '49557032X'||'|'||t.p_clinic_id||'|'||t.p_inpatient_times||'|'||t.uhid||'|'||t1.id,
           1,
           100
       ) as ID,--  内码  是 主键

       '49557032X' as ORG_CODE,--  医院组织机构代码  是 必填

       '山东省第二人民医院' as ORG_NAME,--  医院名称  是 必填

       '370104' as DISTRICT_CODE,-- 所属行政区划  是 按机构所在的行政区划（区县）

       'INSERT' as EXCHANGE_TYPE,-- 交换类型  是 INSERT：向平台传新数据时 UPDATE：向平台更新某条数据时 DELETE：从平台删除某条数据时 ADDHIS :向平台补充历史数据

       cast(systimestamp as timestamp) as SYSTEM_TIME,-- 数据上传时间戳 是

       t.p_clinic_id||'|'||t.p_inpatient_times
        as ADMISSION_ID,--  住院唯一标示号 是

       nvl(
           (select ks.qmpt_name
              from his.dept_dict ks
             where ks.dept_code = t.p_dept_code
               and rownum = 1),
           t.p_Dept_Name
       ) as DEP_NAME,--  科室名称  是

       nvl(
           (select ks.qmpt_code
              from his.dept_dict ks
             where ks.dept_code = t.p_dept_code
               and rownum = 1),
           t.p_dept_code
       ) as DEP_CODE,--  科室代码    按平台值域填写

       t.P_ARE_NAME as AREA_NAME,-- 病区名称

       cast(null as varchar2(10)) as WARD_NUM,--  病房号

       substr(t.P_BEDNO, 1, 10) as SICKBED_NUM,-- 病床号

       cast(nvl(t1.Doc_Title_Time, t1.Createon) as date) as DISCUSS_DATE,-- 讨论日期时间

       substr(nvl(t3.Tldd, '医生办公室'), 1, 50) as DISCUSS_ADDRESS,-- 讨论地点

       substr(
           case
             when t3.Zcrxm is not null then t3.Zcrxm
             else regexp_replace(
                    regexp_substr(
                      dbms_lob.substr(t5.段落内容, 1500, 1),
                      '术[[:space:]]*前[[:space:]]*讨[[:space:]]*论[[:space:]]*由[[:space:]]*([^，,。；;[:cntrl:]]{2,30})主[[:space:]]*持',
                      1, 1, 'n', 1
                    ),
                    '主任医师|副主任医师|主任|副主任|主治医师|住院医师|医师|科主任|的|[[:space:]]',
                    ''
                  )
           end,
           1,
           50
       ) as HOET_NAME,-- 主持人姓名

       substr(
           regexp_replace(t3.Cjtlrymd, '[、,，;；[:space:]]+', '#'),
           1,
           200
       ) as DISCUSS_PEOPLE_LIST,-- 参加讨论人员名单    　人员之间，使用#分割

       nvl(
         (
           select max(to_number(cd.国标编码))
             from cda.cda_dictionary cd
            where cd.字典名称 = '专业技术职务类别代码'
              and regexp_like(cd.国标编码, '^[0-9]+$')
              and cd.院标名称 = (
                    select max(sd.title)
                      from his.staff_dict sd
                     where sd.name = t3.Zcrxm
                  )
         ),
         6
       ) as PROF_TECH_CATE_CODE,-- 专业技术职务类别代码    　主持人的职称

       substr(
           case
             when t3.Tljl is not null then t3.Tljl
             else nvl(
                    regexp_substr(
                      dbms_lob.substr(t5.段落内容, 1500, 1),
                      '简[[:space:]]*要[[:space:]]*病[[:space:]]*情[[:space:]]*[:：][[:space:]]*(.*?)(术[[:space:]]*前[[:space:]]*诊[[:space:]]*断[[:space:]]*[:：]|手[[:space:]]*术[[:space:]]*指[[:space:]]*征[[:space:]]*[:：]|$)',
                      1, 1, 'n', 1
                    ),
                    dbms_lob.substr(t5.段落内容, 1500, 1)
                  )
           end,
           1,
           2000
       ) as MEDICAL_RECORDS_SUNNARY,-- 病历摘要    病情以及治疗情况概述

       substr(
           (
             select max(dd.diagnosis_code) keep (
                      dense_rank first order by
                      case
                        when dd.diagnosis_type = '2' then 1
                        when dd.diagnosis_type = '1' then 2
                        when dd.diagnosis_type = '3' then 3
                        else 9
                      end
                    )
               from his.diagnosis dd
              where dd.patient_id = t.p_clinic_id
                and dd.visit_id = t.p_inpatient_times
                and dd.diagnosis_no = '1'
           ),
           1,
           20
       ) as BEFOPER_DCODE,-- 术前诊断编码

       substr(
           nvl(
               regexp_substr(
                 dbms_lob.substr(t5.段落内容, 1500, 1),
                 '术[[:space:]]*前[[:space:]]*诊[[:space:]]*断[[:space:]]*[:：][[:space:]]*(.*?)(手[[:space:]]*术[[:space:]]*指[[:space:]]*征[[:space:]]*[:：]|拟[[:space:]]*施[[:space:]]*手[[:space:]]*术|$)',
                 1, 1, 'n', 1
               ),
               (
                 select max(dd.diagnosis_desc) keep (
                          dense_rank first order by
                          case
                            when dd.diagnosis_type = '2' then 1
                            when dd.diagnosis_type = '1' then 2
                            when dd.diagnosis_type = '3' then 3
                            else 9
                          end
                        )
                   from his.diagnosis dd
                  where dd.patient_id = t.p_clinic_id
                    and dd.visit_id = t.p_inpatient_times
                    and dd.diagnosis_no = '1'
               )
           ),
           1,
           100
       ) as BEFOPER_DNAME,-- 术前诊断名称

       cast(null as varchar2(32)) as DIAGNOSIS_BASIS,-- 诊断依据

       case
         when t4.Gms is not null
          and not regexp_like(dbms_lob.substr(t4.Gms, 1000, 1), '无|否认|未诉|不详')
         then '1'
         else '0'
       end as ALLERGY_HISTORY_MARK,--  过敏史标志

       substr(nvl(dbms_lob.substr(t4.Gms, 1000, 1), '-'), 1, 1000) as ALLERGY_HISTORY,-- 过敏史

       substr(nvl(dbms_lob.substr(t4.Sysjqxjc, 1000, 1), '-'), 1, 1000) as AUX_EXAM_RESULT,-- 辅助检查结果

       substr(
           case
             when t4.Sssyz is not null then t4.Sssyz
             else regexp_substr(
                    dbms_lob.substr(t5.段落内容, 1500, 1),
                    '手[[:space:]]*术[[:space:]]*指[[:space:]]*征[[:space:]]*[:：][[:space:]]*(.*?)(拟[[:space:]]*施[[:space:]]*手[[:space:]]*术|拟[[:space:]]*施[[:space:]]*麻[[:space:]]*醉|$)',
                    1, 1, 'n', 1
                  )
           end,
           1,
           100
       ) as SURGICAL_INDICATION,-- 手术适应症

       substr(nvl(t4.Ssjjz, '-'), 1, 100) as SURGICAL_CONTRIANDICATIONS,--  手术禁忌症

       substr(
           nvl(
               regexp_substr(
                 dbms_lob.substr(t5.段落内容, 1500, 1),
                 '拟[[:space:]]*施[[:space:]]*手[[:space:]]*术[[:space:]]*名[[:space:]]*称[[:space:]]*和[[:space:]]*方[[:space:]]*式[[:space:]]*[:：][[:space:]]*(.*?)(拟[[:space:]]*施[[:space:]]*麻[[:space:]]*醉|术[[:space:]]*前[[:space:]]*准[[:space:]]*备|$)',
                 1, 1, 'n', 1
               ),
               nvl(o.Operation_Desc, mom.OPERATION_NAME)
           ),
           1,
           100
       ) as PERFORM_OPERATION_NAME,--  拟实施手术及操作名称

       substr(
           nvl(
               nvl(
                   (select cd.国标编码
                      from cda.cda_dictionary cd
                     where cd.字典名称 = 'ICD-9手术编码'
                       and cd.系统标识 = 'HIS'
                       and cd.院标名称 = o.Operation_Desc
                       and rownum = 1),
                   (select cd.国标编码
                      from cda.cda_dictionary cd
                     where cd.字典名称 = 'ICD-9手术编码'
                       and cd.系统标识 = 'SM'
                       and cd.院标名称 = mom.OPERATION_NAME
                       and rownum = 1)
               ),
               '99.9900'
           ),
           1,
           50
       ) as PERFORM_OPERATION_CODE,--  拟实施手术及操作编码

       substr(nvl(t3.Nssssmbbwmc, '-'), 1, 50) as PERFORM_OPERATION_PART_NAME,-- 拟实施手术目标部位名称

       cast(nvl(o.operating_date, mom.START_DATE_TIME) as date) as PERFORM_OPERATION_DATE,--  拟实施手术及操作日期时间    　YYYYMMDD HHMISS

       nvl(
           nvl(
               (select to_number(cd.国标编码)
                  from cda.cda_dictionary cd
                 where cd.字典名称 = '麻醉方法代码表'
                   and cd.系统标识 = 'HIS'
                   and cd.院标名称 = o.ANAESTHESIA_METHOD
                   and regexp_like(cd.国标编码, '^[0-9]+$')
                   and rownum = 1),
               (select to_number(cd.国标编码)
                  from cda.cda_dictionary cd
                 where cd.字典名称 = '麻醉方法代码表'
                   and cd.系统标识 = '手麻'
                   and cd.院标名称 = mom.ANESTHESIA_METHOD
                   and regexp_like(cd.国标编码, '^[0-9]+$')
                   and rownum = 1)
           ),
           9
       ) as PERFORM_ANES_CODE,-- 拟实施麻醉方法代码

       substr(nvl(nvl(t3.Ssyd, t4.ssyd), '-'), 1, 200) as OPERATION_MAIN_POINTS,-- 手术要点

       substr(
           case
             when t3.Sqzb is not null then t3.Sqzb
             when t4.sqzb is not null then t4.sqzb
             else regexp_substr(
                    dbms_lob.substr(t5.段落内容, 1500, 1),
                    '术[[:space:]]*前[[:space:]]*准[[:space:]]*备[[:space:]]*[:：][[:space:]]*(.*?)(注[[:space:]]*意[[:space:]]*事[[:space:]]*项[[:space:]]*[:：]|手术者术前查看|$)',
                    1, 1, 'n', 1
                  )
           end,
           1,
           1000
       ) as PREOPERATIVE_PREPARATION,--  术前准备

       substr(
           case
             when t3.Sszz is not null then t3.Sszz
             when t4.sszz is not null then t4.sszz
             else regexp_substr(
                    dbms_lob.substr(t5.段落内容, 1500, 1),
                    '手[[:space:]]*术[[:space:]]*指[[:space:]]*征[[:space:]]*[:：][[:space:]]*(.*?)(拟[[:space:]]*施[[:space:]]*手[[:space:]]*术|拟[[:space:]]*施[[:space:]]*麻[[:space:]]*醉|$)',
                    1, 1, 'n', 1
                  )
           end,
           1,
           500
       ) as SURGICAL_INDICATIONS,--  手术指征

       substr(
           case
             when t3.Ssfa is not null then t3.Ssfa
             else regexp_substr(
                    dbms_lob.substr(t5.段落内容, 1500, 1),
                    '拟[[:space:]]*施[[:space:]]*手[[:space:]]*术[[:space:]]*名[[:space:]]*称[[:space:]]*和[[:space:]]*方[[:space:]]*式[[:space:]]*[:：][[:space:]]*(.*?)(拟[[:space:]]*施[[:space:]]*麻[[:space:]]*醉|术[[:space:]]*前[[:space:]]*准[[:space:]]*备|$)',
                    1, 1, 'n', 1
                  )
           end,
           1,
           1000
       ) as OPERATION_SCHEME,--  手术方案

       substr(
           case
             when t3.Zysx is not null then t3.Zysx
             when t4.zysx is not null then t4.zysx
             else regexp_substr(
                    dbms_lob.substr(t5.段落内容, 1500, 1),
                    '注[[:space:]]*意[[:space:]]*事[[:space:]]*项[[:space:]]*[:：][[:space:]]*(.*?)(手术者术前查看|主持人|$)',
                    1, 1, 'n', 1
                  )
           end,
           1,
           1000
       ) as MATTERS_ATTENTION,-- 注意事项

       substr(
           nvl(
               t3.Tlyj,
               '同意手术治疗，完善术前准备，注意围手术期风险。'
           ),
           1,
           200
       ) as DISCUSS_OPINION,-- 讨论意见

       substr(
           nvl(t3.Tljl, dbms_lob.substr(t5.段落内容, 1500, 1)),
           1,
           2000
       ) as DISCUSS_CONCLUSION,--  讨论结论

       substr(
           nvl(
               nvl(
                   (select sd.name
                      from his.staff_dict sd
                     where sd.user_name = o.operator
                       and rownum = 1),
                   case
                     when regexp_like(mom.SURGEON, '^[0-9]+$') then
                       (select sd.name
                          from his.staff_dict sd
                         where sd.user_name = mom.SURGEON
                           and rownum = 1)
                     else mom.SURGEON
                   end
               ),
               regexp_replace(
                 regexp_substr(
                   dbms_lob.substr(t5.段落内容, 1500, 1),
                   '手术者([^，,。；;[:cntrl:]]{2,30})术前看过患者',
                   1, 1, 'n', 1
                 ),
                 '主任医师|副主任医师|主任|副主任|主治医师|住院医师|医师|[[:space:]]',
                 ''
               )
           ),
           1,
           50
       ) as SURGERY_NAME,--  手术者签名

       substr(
           nvl(
               nvl(
                   (select sd.name
                      from his.staff_dict sd
                     where sd.user_name = o.Anesthesia_Doctor
                       and rownum = 1),
                   (select sd.name
                      from his.staff_dict sd
                     where sd.user_name = mom.ANESTHESIA_DOCTOR
                       and rownum = 1)
               ),
               '-'
           ),
           1,
           50
       ) as ANAE_DOCTOR_NAME,--  麻醉医师姓名    麻醉医师签名

       substr(
           nvl(
               (select sd.name
                  from his.staff_dict sd
                 where (sd.emp_no = nvl(t1.Modifiedby, t1.Createby)
                        or sd.user_name = nvl(t1.Modifiedby, t1.Createby))
                   and rownum = 1),
               nvl(t1.Modifiedby, t1.Createby)
           ),
           1,
           50
       ) as DOC_NAME,--  医师签名

       cast(nvl(t1.Modifiedon, nvl(t1.Doc_Title_Time, t1.Createon)) as date) as SIGN_DATE --签名日期时间

from mtl.EPR_INPATIENT_DOCINDEX t

inner join his.pat_visit pv
        on pv.patient_id = t.p_clinic_id
       and pv.visit_id = t.p_inpatient_times
       and pv.discharge_date_time >= to_date('2021-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss')
       and pv.discharge_date_time <  to_date('2025-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss')

inner join mtl.EPR_INPATIENT t1
        on t.UHID = t1.UHID
       /*and t1.DOC_STATS = '1'*/
       and t1.doc_type_name in ('术前小结', '术前讨论')
       and t1.doc_title <> '首次病程记录'

left join mtl.EMRSD47 T3
       on T3.段落编号 = T1.ID

left join mtl.EMRSD46 T4
       on T4.段落编号 = T1.ID

left join mtl.emrsd_content t5
       on t5.UHID = t.UHID
      and t5.段落编号 = t1.ID

left join his.operation o
       on o.patient_id = t.p_clinic_id
      and o.visit_id = t.p_inpatient_times
      and o.operation_no = 1

left join sm.med_operation_master mom
       on mom.patient_id = t.p_clinic_id
      and mom.visit_id = t.p_inpatient_times
      and mom.oper_id = '1'
