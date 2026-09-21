
  CREATE OR REPLACE FORCE VIEW "ODS"."V_EMR_BOFORE_OPERA_RECORD" ("ID", "ORG_CODE", "ORG_NAME", "PATIENT_TYPE", "VISTING_NUM", "APPLY_NUM", "DEPT_NAME", "DEPT_CODE", "WARD_NAME", "EORD_NUM", "SICKBED_NUM", "OPERA_ROOM_NUM", "NAME", "ID_NUM", "SEX_NAME", "SEX_CODE", "AGE", "WEIGHT", "ABO_CODE", "ABO_NAME", "RH_CODE", "RH_NAME", "BEFORE_OPERA_DIAGNOSIS", "BEFORE_OPERA_DIAGNOSIS_NAME", "OPERA_CODE", "OPERA_NAME", "ANES_METHOD_CODE", "ANES_METHOD_NAME", "OPERA_DISEASE", "ATTENTION_MATTER", "MEDICAL_HISTORY", "ALLERGIES_HISTROY", "ECR_RESULT", "X_RESULT", "CT_RESULT", "B_RESULT", "MRI_RESULT", "LUNGS_RESULT", "CBC_RESULT", "URINE_RESULT", "COAGULATION_RESULT", "LIVER_RESULT", "FLESH_RESULT", "GENERAL_EXAM_RESULT", "MENTAL_STATE_CODE", "HEART_AUSCULTATE_RESULT", "BELLOWS_AUSCULTATE_RESULT", "FOUR_LIMB_RESULT", "SPINE_RESULT", "ABDOMEN_RESULT", "TRACHEA_RESULT", "TOOTH_RESULT", "SIGNATURE_ASA", "OPERA_ADVICE", "ANANSTHESIA", "ANES_DOC_NAME", "SIGNATURE_DATE", "DISTRICT_CODE", "EXCHANGE_TYPE", "SYSTEM_TIME") AS 
  select substr('49557032X'||'|'||a.patient_id||'|'||a.visit_id||'|'||a.oper_id,1,100) as ID,--  内码  是 唯一主键

       '49557032X' as ORG_CODE,--  组织机构代码  是 医疗机构组织机构代码

       '山东省第二人民医院' as ORG_NAME,--  组织机构名称  是 医疗机构组织机构名称

       '2' as PATIENT_TYPE,--  病人类型  是 1:门急诊 2：住院

       a.patient_id||'|'||a.visit_id as VISTING_NUM,-- 就诊唯一标识号 是 门诊或者住院唯一标识号

       substr(a.patient_id||a.visit_id||a.oper_id,1,20) as APPLY_NUM,-- 电子申请单编号 是 手术申请单编号

       substr(
         nvl(
           (select hd.dept_name
              from his.dept_dict hd
             where hd.dept_code = p.dept_admission_to
               and rownum = 1),
           (select hd.qmpt_name
              from his.dept_dict hd
             where hd.dept_code = p.dept_admission_to
               and rownum = 1)
         ),
         1,
         50
       ) as DEPT_NAME,-- 科室名称  是 按照医院内部名称填写

       substr(
         nvl(
           (select hd.qmpt_code
              from his.dept_dict hd
             where hd.dept_code = p.dept_admission_to
               and rownum = 1),
           p.dept_admission_to
         ),
         1,
         20
       ) as DEPT_CODE,-- 科室代码    按照平台值域填写

       substr(
         nvl(
           (select hd.dept_name
              from his.dept_dict hd
             where hd.dept_code = p.discharge_ward_code
               and rownum = 1),
           p.discharge_ward_code
         ),
         1,
         50
       ) as WARD_NAME,-- 病区名称    患者当前所在病区的名称

       cast(null as varchar2(10)) as EORD_NUM,--  病房号

       substr(p.discharge_bed_no,1,10) as SICKBED_NUM,-- 病床号

       substr(a.operating_room,1,20) as OPERA_ROOM_NUM,--  手术间编号

       substr(nvl(pmi.name,b.name),1,50) as NAME,--  患者姓名  是

       substr(nvl(pmi.id_no,b.id_no),1,18) as ID_NUM,--  身份证件号码

       decode(nvl(pmi.sex,b.sex),'男','男','女','女','未知','未知','其他') as SEX_NAME,--  性别  是 男，女，未知，其他

       decode(nvl(pmi.sex,b.sex),'男','1','女','2','未知','0','9') as SEX_CODE,--  性别代码  是 按照平台值域填写

       to_char(
         case
           when nvl(pmi.date_of_birth,b.date_of_birth) is not null
            and p.admission_date_time is not null
           then greatest(
                  trunc(months_between(p.admission_date_time, nvl(pmi.date_of_birth,b.date_of_birth)) / 12),
                  0
                )
           else null
         end
       ) as AGE,-- 年龄  是

       nvl(
         case
           when e3.weight is not null
            and regexp_like(trim(to_char(e3.weight)), '^[0-9]+(\.[0-9]+)?$')
           then round(to_number(e3.weight),2)
           when p.body_weight is not null
           then round(p.body_weight,2)
           else cast(null as number(6,2))
         end,
         cast(0 as number(6,2))
       ) as WEIGHT,--  体重（kg）  是 计量单位为kg

       nvl(
         (select to_number(cd.国标编码)
            from cda.cda_dictionary cd
           where cd.字典名称 = 'ABO血型代码'
             and cd.院标名称 = p.blood_type
             and regexp_like(cd.国标编码, '^[0-9]+$')
             and rownum = 1),
         5
       ) as ABO_CODE,--  ABO血型代码

       substr(
         nvl(
           (select cd.国标名称
              from cda.cda_dictionary cd
             where cd.字典名称 = 'ABO血型代码'
               and cd.院标名称 = p.blood_type
               and rownum = 1),
           '不详'
         ),
         1,
         50
       ) as ABO_NAME,--  ABO血型名称

       nvl(
         (select to_number(cd.国标编码)
            from cda.cda_dictionary cd
           where cd.字典名称 = 'RH血型代码'
             and cd.院标名称 = p.blood_type_rh
             and regexp_like(cd.国标编码, '^[0-9]+$')
             and rownum = 1),
         4
       ) as RH_CODE,-- Rh血型代码

       substr(
         nvl(
           (select cd.国标名称
              from cda.cda_dictionary cd
             where cd.字典名称 = 'RH血型代码'
               and cd.院标名称 = p.blood_type_rh
               and rownum = 1),
           '未查'
         ),
         1,
         50
       ) as RH_NAME,-- Rh血型名称

           nvl( nvl(   (select max(cd.国标编码)
            from cda.cda_dictionary cd
           where cd.字典名称 = 'ICD-10诊断编码'
             and cd.系统标识 = 'SM'
             and cd.院标名称 = a.DIAG_before_OPERATION)    ,
              (select max(cd.国标编码)
            from cda.cda_dictionary cd
           where cd.字典名称 = 'ICD-10诊断编码'
             and cd.系统标识 = 'HIS'
             and cd.院标名称 = dd.diagnosis_desc)
       ),         dd.diagnosis_code)      as BEFORE_OPERA_DIAGNOSIS,--  术前诊断编码    请按照省统一标准填写


                   nvl( nvl(   (select max(cd.国标名称)
            from cda.cda_dictionary cd
           where cd.字典名称 = 'ICD-10诊断编码'
             and cd.系统标识 = 'SM'
             and cd.院标名称 = a.DIAG_before_OPERATION)    ,
              (select max(cd.国标名称)
            from cda.cda_dictionary cd
           where cd.字典名称 = 'ICD-10诊断编码'
             and cd.系统标识 = 'HIS'
             and cd.院标名称 = dd.diagnosis_desc)
       ),         dd.diagnosis_desc)     as BEFORE_OPERA_DIAGNOSIS_NAME,-- 术前诊断名称  是 请按照医院内部名称填写

       substr(
         nvl(
           nvl(
             (select cd.国标编码
                from cda.cda_dictionary cd
               where cd.字典名称 = 'ICD-9手术编码'
                 and cd.系统标识 = 'HIS'
                 and cd.院标名称 = e3.operation_name
                 and rownum = 1),
             (select cd.国标编码
                from cda.cda_dictionary cd
               where cd.字典名称 = 'ICD-9手术编码'
                 and cd.系统标识 = 'HIS'
                 and cd.院标名称 = o.operation_desc
                 and rownum = 1)
           ),
           (select cd.国标编码
              from cda.cda_dictionary cd
             where cd.字典名称 = 'ICD-9手术编码'
               and cd.系统标识 = 'SM'
               and cd.院标名称 = a.operation_name
               and rownum = 1)
         ),
         1,
         12
       ) as OPERA_CODE,--  拟实施手术及操作编码    请按照省统一标准填写

       substr(
         nvl(
           nvl(
             nvl(
               (select cd.国标名称
                  from cda.cda_dictionary cd
                 where cd.字典名称 = 'ICD-9手术编码'
                   and cd.系统标识 = 'HIS'
                   and cd.院标名称 = e3.operation_name
                   and rownum = 1),
               (select cd.国标名称
                  from cda.cda_dictionary cd
                 where cd.字典名称 = 'ICD-9手术编码'
                   and cd.系统标识 = 'HIS'
                   and cd.院标名称 = o.operation_desc
                   and rownum = 1)
             ),
             (select cd.国标名称
                from cda.cda_dictionary cd
               where cd.字典名称 = 'ICD-9手术编码'
                 and cd.系统标识 = 'SM'
                 and cd.院标名称 = a.operation_name
                 and rownum = 1)
           ),
           nvl(e3.operation_name,nvl(o.operation_desc,nvl(a.operation_name,'其他各类操作')))
         ),
         1,
         50
       ) as OPERA_NAME,--  拟实施手术及操作名称  是 请按照医院内部名称填写

       nvl(
         (select to_number(cd.国标编码)
            from cda.cda_dictionary cd
           where cd.字典名称 = '麻醉方法代码表'
             and cd.系统标识 = 'HIS'
             and cd.院标名称 = o.anaesthesia_method
             and regexp_like(cd.国标编码, '^[0-9]+$')
             and rownum = 1),
         nvl(
           (select to_number(cd.国标编码)
              from cda.cda_dictionary cd
             where cd.字典名称 = '麻醉方法代码表'
               and cd.系统标识 = '手麻'
               and cd.院标名称 = nvl(e3.anesthesia_method,a.anesthesia_method)
               and regexp_like(cd.国标编码, '^[0-9]+$')
               and rownum = 1),
           9
         )
       ) as ANES_METHOD_CODE,--  拟实施麻醉方法代码 是

       substr(
         nvl(
           (select cd.国标名称
              from cda.cda_dictionary cd
             where cd.字典名称 = '麻醉方法代码表'
               and cd.系统标识 = 'HIS'
               and cd.院标名称 = o.anaesthesia_method
               and rownum = 1),
           nvl(
             (select cd.国标名称
                from cda.cda_dictionary cd
               where cd.字典名称 = '麻醉方法代码表'
                 and cd.系统标识 = '手麻'
                 and cd.院标名称 = nvl(e3.anesthesia_method,a.anesthesia_method)
                 and rownum = 1),
             nvl(nvl(e3.anesthesia_method,a.anesthesia_method),'其他麻醉方法')
           )
         ),
         1,
         50
       ) as ANES_METHOD_NAME,--  拟实施麻醉方法名称 是 请按照医院内部名称填写

       substr(
         nullif(
           nvl((select '并存疾病:'||max(cast(sq.item_value as varchar2(4000 char)))||';'
                  from sm.med_custom_data sq
                 where sq.patient_id = a.patient_id
                   and sq.visit_id   = a.visit_id
                   and sq.oper_id    = a.oper_id
                   and sq.item_name  = '术前访视.并存疾病'
                   and sq.item_value is not null), '') ||
           nvl((select '其它疾病:'||max(cast(sq.item_value as varchar2(4000 char)))||';'
                  from sm.med_custom_data sq
                 where sq.patient_id = a.patient_id
                   and sq.visit_id   = a.visit_id
                   and sq.oper_id    = a.oper_id
                   and sq.item_name  = '术前访视.其它疾病'
                   and sq.item_value is not null), '') ||
           nvl((select '心血管系统:'||max(cast(sq.item_value as varchar2(4000 char)))||';'
                  from sm.med_custom_data sq
                 where sq.patient_id = a.patient_id
                   and sq.visit_id   = a.visit_id
                   and sq.oper_id    = a.oper_id
                   and sq.item_name  = '术前访视.心血管系统'
                   and sq.item_value is not null), '') ||
           nvl((select '呼吸系统:'||max(cast(sq.item_value as varchar2(4000 char)))||';'
                  from sm.med_custom_data sq
                 where sq.patient_id = a.patient_id
                   and sq.visit_id   = a.visit_id
                   and sq.oper_id    = a.oper_id
                   and sq.item_name  = '术前访视.呼吸系统'
                   and sq.item_value is not null), ''),
           ''
         ),
         1,
         100
       ) as OPERA_DISEASE,-- 术前合并疾病

       substr(
         nullif(
           nvl((select '麻醉中需注意问题:'||max(cast(sq.item_value as varchar2(4000 char)))||';'
                  from sm.med_custom_data sq
                 where sq.patient_id = a.patient_id
                   and sq.visit_id   = a.visit_id
                   and sq.oper_id    = a.oper_id
                   and sq.item_name  = '术前访视.麻醉中需注意问题'
                   and sq.item_value is not null), '') ||
           nvl((select '麻醉关注点:'||max(cast(sq.item_value as varchar2(4000 char)))||';'
                  from sm.med_custom_data sq
                 where sq.patient_id = a.patient_id
                   and sq.visit_id   = a.visit_id
                   and sq.oper_id    = a.oper_id
                   and sq.item_name  = '术前访视.麻醉关注点'
                   and sq.item_value is not null), '') ||
           nvl((select '风险评估:'||max(cast(sq.item_value as varchar2(4000 char)))||';'
                  from sm.med_custom_data sq
                 where sq.patient_id = a.patient_id
                   and sq.visit_id   = a.visit_id
                   and sq.oper_id    = a.oper_id
                   and sq.item_name  = '术前访视.风险评估'
                   and sq.item_value is not null), '') ||
           nvl((select '特殊监测:'||max(cast(sq.item_value as varchar2(4000 char)))||';'
                  from sm.med_custom_data sq
                 where sq.patient_id = a.patient_id
                   and sq.visit_id   = a.visit_id
                   and sq.oper_id    = a.oper_id
                   and sq.item_name in ('术前访视.特殊监测','术前访视.特殊监测其它')
                   and sq.item_value is not null), '') ||
           nvl((select '拟准备特殊急救药品及设备:'||max(cast(sq.item_value as varchar2(4000 char)))||';'
                  from sm.med_custom_data sq
                 where sq.patient_id = a.patient_id
                   and sq.visit_id   = a.visit_id
                   and sq.oper_id    = a.oper_id
                   and sq.item_name  = '术前访视.拟准备特殊急救药品及设备'
                   and sq.item_value is not null), '') ||
           nvl2(e3.anes_summary, '麻醉摘要:'||e3.anes_summary||';', ''),
           ''
         ),
         1,
         1000
       ) as ATTENTION_MATTER,--  注意事项    麻醉中可能出现问题及采取相应措施的描述

       substr(
         nullif(
           nvl((select '家族史:'||max(cast(sq.item_value as varchar2(4000 char)))||';'
                  from sm.med_custom_data sq
                 where sq.patient_id = a.patient_id
                   and sq.visit_id   = a.visit_id
                   and sq.oper_id    = a.oper_id
                   and sq.item_name  = '术前访视.家族史'
                   and sq.item_value is not null), '') ||
           nvl((select '麻醉手术史:'||max(cast(sq.item_value as varchar2(4000 char)))||';'
                  from sm.med_custom_data sq
                 where sq.patient_id = a.patient_id
                   and sq.visit_id   = a.visit_id
                   and sq.oper_id    = a.oper_id
                   and sq.item_name  = '术前访视.麻醉手术史'
                   and sq.item_value is not null), '') ||
           nvl((select '吸烟史:'||max(cast(sq.item_value as varchar2(4000 char)))||';'
                  from sm.med_custom_data sq
                 where sq.patient_id = a.patient_id
                   and sq.visit_id   = a.visit_id
                   and sq.oper_id    = a.oper_id
                   and sq.item_name  = '术前访视.吸烟史'
                   and sq.item_value is not null), '') ||
           nvl((select '饮酒史:'||max(cast(sq.item_value as varchar2(4000 char)))||';'
                  from sm.med_custom_data sq
                 where sq.patient_id = a.patient_id
                   and sq.visit_id   = a.visit_id
                   and sq.oper_id    = a.oper_id
                   and sq.item_name  = '术前访视.饮酒史'
                   and sq.item_value is not null), '') ||
           nvl((select '使用特殊药物:'||max(cast(sq.item_value as varchar2(4000 char)))||';'
                  from sm.med_custom_data sq
                 where sq.patient_id = a.patient_id
                   and sq.visit_id   = a.visit_id
                   and sq.oper_id    = a.oper_id
                   and sq.item_name  = '术前访视.使用特殊药物'
                   and sq.item_value is not null), ''),
           ''
         ),
         1,
         100
       ) as MEDICAL_HISTORY,-- 简要病史

       substr(
         nvl(
           (select max(cast(sq.item_value as varchar2(4000 char)))
              from sm.med_custom_data sq
             where sq.patient_id = a.patient_id
               and sq.visit_id   = a.visit_id
               and sq.oper_id    = a.oper_id
               and sq.item_name  = '术前访视.过敏史'
               and sq.item_value is not null),
           nvl(p.alergy_drugs,'-')
         ),
         1,
         1000
       ) as ALLERGIES_HISTROY,-- 过敏史   患者既往发生过敏情况的详细描述

       substr(e3.ecg_exam,1,100) as ECR_RESULT,--  心电图检查结果

       substr(e3.exam_x,1,100) as X_RESULT,--  胸部X线检查结果

       cast(null as varchar2(100)) as CT_RESULT,-- CT检查结果

       cast(null as varchar2(100)) as B_RESULT,--  B超检查结果

       cast(null as varchar2(1000)) as MRI_RESULT,--  MRI超检查结果

       substr(e3.lung,1,1000) as LUNGS_RESULT,--  肺功能检查结果

       substr(
         nullif(
           nvl2(e3.hemoglobin,      'Hb:'  || e3.hemoglobin      || ';', '') ||
           nvl2(e3.lab_a,           'RBC:' || e3.lab_a           || ';', '') ||
           nvl2(e3.blood_corpuscle, 'HCT:' || e3.blood_corpuscle || ';', '') ||
           nvl2(e3.lab_c,           'PLT:' || e3.lab_c           || ';', '') ||
           nvl((select '术前访视Hb:'||max(cast(sq.item_value as varchar2(4000 char)))||';'
                  from sm.med_custom_data sq
                 where sq.patient_id = a.patient_id
                   and sq.visit_id   = a.visit_id
                   and sq.oper_id    = a.oper_id
                   and sq.item_name  = '术前访视.Hb'
                   and sq.item_value is not null), ''),
           ''
         ),
         1,
         1000
       ) as CBC_RESULT,--  血常规检查结果

       substr(
         (select max(cast(sq.item_value as varchar2(4000 char)))
            from sm.med_custom_data sq
           where sq.patient_id = a.patient_id
             and sq.visit_id   = a.visit_id
             and sq.oper_id    = a.oper_id
             and sq.item_name  = '术前访视.尿常规'
             and sq.item_value is not null),
         1,
         100
       ) as URINE_RESULT,--  尿常规检查结果

       substr(
         nvl(
           (select max(cast(sq.item_value as varchar2(4000 char)))
              from sm.med_custom_data sq
             where sq.patient_id = a.patient_id
               and sq.visit_id   = a.visit_id
               and sq.oper_id    = a.oper_id
               and sq.item_name  = '术前访视.凝血项目'
               and sq.item_value is not null),
           nullif(
             nvl((select 'PT:'||max(cast(sq.item_value as varchar2(100 char)))||';'
                    from sm.med_custom_data sq
                   where sq.patient_id = a.patient_id
                     and sq.visit_id   = a.visit_id
                     and sq.oper_id    = a.oper_id
                     and sq.item_name  = '术前访视.PT'
                     and sq.item_value is not null), '') ||
             nvl((select 'APTT:'||max(cast(sq.item_value as varchar2(100 char)))||';'
                    from sm.med_custom_data sq
                   where sq.patient_id = a.patient_id
                     and sq.visit_id   = a.visit_id
                     and sq.oper_id    = a.oper_id
                     and sq.item_name  = '术前访视.APTT'
                     and sq.item_value is not null), '') ||
             nvl((select 'TT:'||max(cast(sq.item_value as varchar2(100 char)))||';'
                    from sm.med_custom_data sq
                   where sq.patient_id = a.patient_id
                     and sq.visit_id   = a.visit_id
                     and sq.oper_id    = a.oper_id
                     and sq.item_name  = '术前访视.TT'
                     and sq.item_value is not null), '') ||
             nvl((select 'INR:'||max(cast(sq.item_value as varchar2(100 char)))||';'
                    from sm.med_custom_data sq
                   where sq.patient_id = a.patient_id
                     and sq.visit_id   = a.visit_id
                     and sq.oper_id    = a.oper_id
                     and sq.item_name  = '术前访视.INR'
                     and sq.item_value is not null), '') ||
             nvl((select 'FIB:'||max(cast(sq.item_value as varchar2(100 char)))||';'
                    from sm.med_custom_data sq
                   where sq.patient_id = a.patient_id
                     and sq.visit_id   = a.visit_id
                     and sq.oper_id    = a.oper_id
                     and sq.item_name  = '术前访视.FIB'
                     and sq.item_value is not null), ''),
             ''
           )
         ),
         1,
         100
       ) as COAGULATION_RESULT,--  凝血功能检查结果

       substr(
         nvl(
           e3.liver,
           (select max(cast(sq.item_value as varchar2(4000 char)))
              from sm.med_custom_data sq
             where sq.patient_id = a.patient_id
               and sq.visit_id   = a.visit_id
               and sq.oper_id    = a.oper_id
               and sq.item_name in ('术前访视.肝功能','术前访视.肝脏')
               and sq.item_value is not null)
         ),
         1,
         100
       ) as LIVER_RESULT,--  肝功能检查结果

       substr(
         nvl(
           nullif(
             nvl((select '血气分析:'||max(cast(sq.item_value as varchar2(4000 char)))||';'
                    from sm.med_custom_data sq
                   where sq.patient_id = a.patient_id
                     and sq.visit_id   = a.visit_id
                     and sq.oper_id    = a.oper_id
                     and sq.item_name  = '术前访视.XQFX11'
                     and sq.item_value is not null), '') ||
             nvl((select '钠:'||max(cast(sq.item_value as varchar2(100 char)))||';'
                    from sm.med_custom_data sq
                   where sq.patient_id = a.patient_id
                     and sq.visit_id   = a.visit_id
                     and sq.oper_id    = a.oper_id
                     and sq.item_name  = '术前访视钠'
                     and sq.item_value is not null), '') ||
             nvl((select '钾:'||max(cast(sq.item_value as varchar2(100 char)))||';'
                    from sm.med_custom_data sq
                   where sq.patient_id = a.patient_id
                     and sq.visit_id   = a.visit_id
                     and sq.oper_id    = a.oper_id
                     and sq.item_name  = '术前访视钾'
                     and sq.item_value is not null), '') ||
             nvl((select '氯:'||max(cast(sq.item_value as varchar2(100 char)))||';'
                    from sm.med_custom_data sq
                   where sq.patient_id = a.patient_id
                     and sq.visit_id   = a.visit_id
                     and sq.oper_id    = a.oper_id
                     and sq.item_name  = '术前访视氯'
                     and sq.item_value is not null), ''),
             ''
           ),
           e3.other_labs
         ),
         1,
         1000
       ) as FLESH_RESULT,--  血气分析检查结果

       substr(
         nullif(
           nvl((select '心理评估:'||max(cast(sq.item_value as varchar2(4000 char)))||';'
                  from sm.med_custom_data sq
                 where sq.patient_id = a.patient_id
                   and sq.visit_id   = a.visit_id
                   and sq.oper_id    = a.oper_id
                   and sq.item_name  = '术前访视.心理评估'
                   and sq.item_value is not null), '') ||
           nvl((select '活动能力:'||max(cast(sq.item_value as varchar2(4000 char)))||';'
                  from sm.med_custom_data sq
                 where sq.patient_id = a.patient_id
                   and sq.visit_id   = a.visit_id
                   and sq.oper_id    = a.oper_id
                   and sq.item_name  = '术前访视.活动能力'
                   and sq.item_value is not null), '') ||
           nvl((select '体格检查其它:'||max(cast(sq.item_value as varchar2(4000 char)))||';'
                  from sm.med_custom_data sq
                 where sq.patient_id = a.patient_id
                   and sq.visit_id   = a.visit_id
                   and sq.oper_id    = a.oper_id
                   and sq.item_name  = '术前访视.体格检查其它'
                   and sq.item_value is not null), '') ||
           nvl((select '其它:'||max(cast(sq.item_value as varchar2(4000 char)))||';'
                  from sm.med_custom_data sq
                 where sq.patient_id = a.patient_id
                   and sq.visit_id   = a.visit_id
                   and sq.oper_id    = a.oper_id
                   and sq.item_name  = '术前访视.其它'
                   and sq.item_value is not null), ''),
           ''
         ),
         1,
         1000
       ) as GENERAL_EXAM_RESULT,-- 一般状况检查结果

       nvl(
         (select case
                   when max(cast(sq.item_value as varchar2(4000 char))) like '%清醒%'
                     or max(cast(sq.item_value as varchar2(4000 char))) like '%正常%'
                   then '1'
                   else '0'
                 end
            from sm.med_custom_data sq
           where sq.patient_id = a.patient_id
             and sq.visit_id   = a.visit_id
             and sq.oper_id    = a.oper_id
             and sq.item_name  = '术前访视.精神状态'
             and sq.item_value is not null),
         '0'
       ) as MENTAL_STATE_CODE,-- 精神状态正常标志

       substr(
         nvl(
           (select max(cast(sq.item_value as varchar2(4000 char)))
              from sm.med_custom_data sq
             where sq.patient_id = a.patient_id
               and sq.visit_id   = a.visit_id
               and sq.oper_id    = a.oper_id
               and sq.item_name in ('术前访视.体格检查心','术前访视.心血管系统')
               and sq.item_value is not null),
           e3.sound_of_heart_and_lung
         ),
         1,
         100
       ) as HEART_AUSCULTATE_RESULT,-- 心脏听诊结果

       substr(
         nvl(
           (select max(cast(sq.item_value as varchar2(4000 char)))
              from sm.med_custom_data sq
             where sq.patient_id = a.patient_id
               and sq.visit_id   = a.visit_id
               and sq.oper_id    = a.oper_id
               and sq.item_name in ('术前访视.体格检查肺','术前访视.呼吸系统')
               and sq.item_value is not null),
           e3.sound_of_heart_and_lung
         ),
         1,
         100
       ) as BELLOWS_AUSCULTATE_RESULT,-- 肺部听诊结果

       substr(
         nvl(
           (select max(cast(sq.item_value as varchar2(4000 char)))
              from sm.med_custom_data sq
             where sq.patient_id = a.patient_id
               and sq.visit_id   = a.visit_id
               and sq.oper_id    = a.oper_id
               and sq.item_name in ('术前访视.体格检查四肢','术前访视.关节/肌肉骨骼系统')
               and sq.item_value is not null),
           e3.limb_feel
         ),
         1,
         1000
       ) as FOUR_LIMB_RESULT,-- 四肢检查结果

       substr(
         nvl(
           e3.spine_status,
           nullif(
             nvl((select '脊柱:'||max(cast(sq.item_value as varchar2(4000 char)))||';'
                    from sm.med_custom_data sq
                   where sq.patient_id = a.patient_id
                     and sq.visit_id   = a.visit_id
                     and sq.oper_id    = a.oper_id
                     and sq.item_name  = '术前访视.体格检查脊柱'
                     and sq.item_value is not null), '') ||
             nvl((select '关节/肌肉骨骼系统:'||max(cast(sq.item_value as varchar2(4000 char)))||';'
                    from sm.med_custom_data sq
                   where sq.patient_id = a.patient_id
                     and sq.visit_id   = a.visit_id
                     and sq.oper_id    = a.oper_id
                     and sq.item_name  = '术前访视.关节/肌肉骨骼系统'
                     and sq.item_value is not null), '') ||
             nvl((select '体格检查其它:'||max(cast(sq.item_value as varchar2(4000 char)))||';'
                    from sm.med_custom_data sq
                   where sq.patient_id = a.patient_id
                     and sq.visit_id   = a.visit_id
                     and sq.oper_id    = a.oper_id
                     and sq.item_name  = '术前访视.体格检查其它'
                     and sq.item_value is not null), ''),
             ''
           )
         ),
         1,
         1000
       ) as SPINE_RESULT,-- 脊柱检查结果

       substr(
         nullif(
           nvl((select '腹部:'||max(cast(sq.item_value as varchar2(4000 char)))||';'
                  from sm.med_custom_data sq
                 where sq.patient_id = a.patient_id
                   and sq.visit_id   = a.visit_id
                   and sq.oper_id    = a.oper_id
                   and sq.item_name  = '术前访视.体格检查腹部'
                   and sq.item_value is not null), '') ||
           nvl((select '体格检查其它:'||max(cast(sq.item_value as varchar2(4000 char)))||';'
                  from sm.med_custom_data sq
                 where sq.patient_id = a.patient_id
                   and sq.visit_id   = a.visit_id
                   and sq.oper_id    = a.oper_id
                   and sq.item_name  = '术前访视.体格检查其它'
                   and sq.item_value is not null), '') ||
           nvl((select '其它:'||max(cast(sq.item_value as varchar2(4000 char)))||';'
                  from sm.med_custom_data sq
                 where sq.patient_id = a.patient_id
                   and sq.visit_id   = a.visit_id
                   and sq.oper_id    = a.oper_id
                   and sq.item_name  = '术前访视.其它'
                   and sq.item_value is not null), ''),
           ''
         ),
         1,
         1000
       ) as ABDOMEN_RESULT,-- 腹部检查结果

       substr(
         nvl(
           nullif(
             nvl((select '气道检查:'||max(cast(sq.item_value as varchar2(4000 char)))||';'
                    from sm.med_custom_data sq
                   where sq.patient_id = a.patient_id
                     and sq.visit_id   = a.visit_id
                     and sq.oper_id    = a.oper_id
                     and sq.item_name  = '术前访视.体格检查气道'
                     and sq.item_value is not null), '') ||
             nvl((select '气道评估:'||max(cast(sq.item_value as varchar2(4000 char)))||';'
                    from sm.med_custom_data sq
                   where sq.patient_id = a.patient_id
                     and sq.visit_id   = a.visit_id
                     and sq.oper_id    = a.oper_id
                     and sq.item_name  = '术前访视.气道评估'
                     and sq.item_value is not null), '') ||
             nvl((select 'Mallampati:'||max(cast(sq.item_value as varchar2(4000 char)))||';'
                    from sm.med_custom_data sq
                   where sq.patient_id = a.patient_id
                     and sq.visit_id   = a.visit_id
                     and sq.oper_id    = a.oper_id
                     and sq.item_name  = '术前访视.mallampati'
                     and sq.item_value is not null), '') ||
             nvl((select '张口度:'||max(cast(sq.item_value as varchar2(4000 char)))||';'
                    from sm.med_custom_data sq
                   where sq.patient_id = a.patient_id
                     and sq.visit_id   = a.visit_id
                     and sq.oper_id    = a.oper_id
                     and sq.item_name  = '术前访视.张口度'
                     and sq.item_value is not null), '') ||
             nvl((select '既往插管:'||max(cast(sq.item_value as varchar2(4000 char)))||';'
                    from sm.med_custom_data sq
                   where sq.patient_id = a.patient_id
                     and sq.visit_id   = a.visit_id
                     and sq.oper_id    = a.oper_id
                     and sq.item_name  = '术前访视.既往插管'
                     and sq.item_value is not null), ''),
             ''
           ),
           e3.cervix
         ),
         1,
         100
       ) as TRACHEA_RESULT,-- 气管检查结果

       substr(
         nvl(
           e3.tooth_exam,
           (select max(cast(sq.item_value as varchar2(4000 char)))
              from sm.med_custom_data sq
             where sq.patient_id = a.patient_id
               and sq.visit_id   = a.visit_id
               and sq.oper_id    = a.oper_id
               and sq.item_name  = '术前访视.体格检查牙齿'
               and sq.item_value is not null)
         ),
         1,
         100
       ) as TOOTH_RESULT,-- 牙齿检查结果

       nvl(
         (select to_number(zd.国标编码)
            from cda.cda_dictionary zd
           where zd.字典名称 = '美国麻醉医师协会（ASA）分级标准代码表'
             and zd.院标名称 = e3.asa_grade
             and regexp_like(zd.国标编码, '^[0-9]+$')
             and rownum = 1),
         1
       ) as SIGNATURE_ASA,-- ASA分级标准代码 是

      nvl( substr(
         nvl(
           (select max(cast(sq.item_value as varchar2(4000 char)))
              from sm.med_custom_data sq
             where sq.patient_id = a.patient_id
               and sq.visit_id   = a.visit_id
               and sq.oper_id    = a.oper_id
               and sq.item_name in ('术前访视.术前麻醉医嘱','术前访视.麻醉医嘱')
               and sq.item_value is not null),
           nvl(e3.pre_anes_pham,'-')
         ),
         1,
         1000
       ),'-') as OPERA_ADVICE,-- 术前麻醉医嘱

       substr(
         nullif(
           nvl((select '备选麻醉:'||max(cast(sq.item_value as varchar2(4000 char)))||';'
                  from sm.med_custom_data sq
                 where sq.patient_id = a.patient_id
                   and sq.visit_id   = a.visit_id
                   and sq.oper_id    = a.oper_id
                   and sq.item_name  = '术前访视.备选麻醉'
                   and sq.item_value is not null), '') ||
           nvl((select '备选麻醉方式:'||max(cast(sq.item_value as varchar2(4000 char)))||';'
                  from sm.med_custom_data sq
                 where sq.patient_id = a.patient_id
                   and sq.visit_id   = a.visit_id
                   and sq.oper_id    = a.oper_id
                   and sq.item_name  = '术前访视.备选麻醉方式'
                   and sq.item_value is not null), '') ||
           nvl((select '麻醉中需注意问题:'||max(cast(sq.item_value as varchar2(4000 char)))||';'
                  from sm.med_custom_data sq
                 where sq.patient_id = a.patient_id
                   and sq.visit_id   = a.visit_id
                   and sq.oper_id    = a.oper_id
                   and sq.item_name  = '术前访视.麻醉中需注意问题'
                   and sq.item_value is not null), ''),
           ''
         ),
         1,
         100
       ) as ANANSTHESIA,-- 麻醉适应症

      nvl( substr(
         nvl(
           nvl(
             case
               when regexp_like(a.anesthesia_doctor,'^[0-9]+$') then
                 (select sd.name
                    from his.staff_dict sd
                   where sd.emp_no = a.anesthesia_doctor
                     and rownum = 1)
               else a.anesthesia_doctor
             end,
             o.anesthesia_doctor
           ),
           (select max(cast(sq.item_value as varchar2(4000 char)))
              from sm.med_custom_data sq
             where sq.patient_id = a.patient_id
               and sq.visit_id   = a.visit_id
               and sq.oper_id    = a.oper_id
               and sq.item_name in ('术前访视.麻醉医师签名','术前访视.麻醉医生')
               and sq.item_value is not null)
         ),
         1,
         50
       ),'-') as ANES_DOC_NAME,-- 麻醉医师签名

       cast(nvl(f2.archive_date_time,nvl(e3.enter_date_time,a.start_date_time)) as date) as SIGNATURE_DATE,--  签名日期时间  是 yymmdd hh24miss

       '370104' as DISTRICT_CODE,-- 行政区划  是

       'ADDHIS' as EXCHANGE_TYPE,-- 交换类型  是 INSERT：向平台传新数据时 UPDATE：向平台更新某条数据时 DELETE：从平台删除某条数据时 ADDHIS :向平台补充历史数据

       cast(systimestamp as timestamp) as SYSTEM_TIME --数据上传时间  是 数据上传时间

from sm.med_operation_master a

 left join sm.med_operation_schedule a1
        on a.patient_id = a1.patient_id
       and a.visit_id   = a1.visit_id
       and a.oper_id    = a1.oper_id

 left join sm.med_pat_master_index b
        on a.patient_id = b.patient_id

 left join sm.med_anesthesia_plan e3
        on a.patient_id = e3.patient_id
       and a.visit_id   = e3.visit_id
       and a.oper_id    = e3.oper_id

 left join (
       select patient_id,
              visit_id,
              archive_key,
              max(archive_date_time) as archive_date_time
         from sm.med_emr_archive_detial
        where archive_type = '正常'
        group by patient_id, visit_id, archive_key
 ) f2
        on a.patient_id = f2.patient_id
       and a.visit_id   = f2.visit_id
       and to_char(a.oper_id) = to_char(f2.archive_key)
  left join (select * from (
select o.*,
       row_number() over (
           partition by
               o.patient_id,
               o.visit_id,
               trunc(o.operating_date)
           order by
               o.operation_scale desc nulls last,
               case
                   when to_char(o.op_primary) = '1' then 1
                   else 0
               end desc,
               o.operation_no asc nulls last
       ) as rn
from his.operation o  )  where rn=1)  o
               on a.patient_id = o.patient_id
              and a.visit_id = o.visit_id
            and to_char(o.operating_date,'yyyy-mm-dd')=to_char( nvl(a.start_date_time,a.SCHEDULED_DATE_TIME),'yyyy-mm-dd')

 left join his.pat_visit p
        on p.patient_id = a.patient_id
       and p.visit_id   = a.visit_id

 left join his.pat_master_index pmi
        on p.patient_id = pmi.patient_id

 left join (
       select *
         from (
               select d.*,
                      row_number() over(
                        partition by d.patient_id, d.visit_id
                        order by d.diagnosis_no
                      ) as rn
                 from his.diagnosis d
                where d.diagnosis_type = '3'
              )
        where rn = 1
 ) dd
        on p.patient_id = dd.patient_id
       and p.visit_id   = dd.visit_id

where a.oper_status > 34
  and a1.patient_id is not null
  and nvl(f2.archive_date_time,nvl(e3.enter_date_time,a.start_date_time)) < p.discharge_date_time
  and p.discharge_date_time >= to_date('2021-01-01 00:00:00','yyyy-mm-dd hh24:mi:ss')
  and p.discharge_date_time <  to_date('2025-01-01 00:00:00','yyyy-mm-dd hh24:mi:ss')
