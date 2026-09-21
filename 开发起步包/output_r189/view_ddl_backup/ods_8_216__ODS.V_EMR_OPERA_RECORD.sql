
  CREATE OR REPLACE FORCE VIEW "ODS"."V_EMR_OPERA_RECORD" ("ID", "ORG_CODE", "ORG_NAME", "PATIENT_TYPE", "VISTING_NUM", "APPLY_NUM", "DEPT_NAME", "WARD_NAME", "EORD_NUM", "SICKBED_NUM", "OPERA_ROOM_NUM", "NAME", "SEX_CODE", "SEX_NAME", "AGE", "BEF_OPE_DIAG", "BEF_OPE_DIAG_NAME", "AFTER_OPE_DIAG", "AFTER_OPE_DIAG_NAME", "OPERA_START_DATE", "OPERA_END_DATE", "OPERA_CODE", "OPERA_NAME", "OPERA_GRADE", "OPERA_BP_CODE", "INTER_BODY", "OPERA_POSI", "OPERA_POSI_NAME", "OPERATION_NOTE", "OPERATION_HIS", "DISINF_NOTE", "INCISION_NOTE", "DRAINAGE_CODE", "OUT_BLOOD_ML", "BEFORE_DRUG", "IN_DRUG", "DRAINAGE_TYPE", "DRAINAGE_AMOUNT", "PLACE", "BT_REACTION_MARK", "SURGEON_NAME", "ASSISTANT_FIR_NAME", "ASSISTANT_SED_NAME", "INS_NURSE_NAME", "ROUND_NURSE_NAME", "ANAESTHESIA_CODE", "ANESTHESIA_DOC_NAME", "SIGNATURE_DATE", "DISTRICT_CODE", "EXCHANGE_TYPE", "SYSTEM_TIME", "SURGEON_CERTIFICATE_NO", "ANESTHESIA", "INCISION_HEALING_LEVEL_CODE", "WOUNDHEAL_LEVEL_CODE", "ANES_CERTIFICATE_NO", "LOCAL_PROCEDURE_CODE", "LOCAL_PROCEDURE_NAME", "NHS_PROCEDURE_CODE", "NHS_PROCEDURE_NAME", "IS_MAIN_PROCEDURE", "OPERATE_TYPE") AS 
  select ID,
       ORG_CODE,
       ORG_NAME,
       PATIENT_TYPE,
       VISTING_NUM,
       APPLY_NUM,
       DEPT_NAME,
       WARD_NAME,
       EORD_NUM,
       SICKBED_NUM,
       OPERA_ROOM_NUM,
       NAME,
       SEX_CODE,
       SEX_NAME,
       AGE,
       BEF_OPE_DIAG,
       BEF_OPE_DIAG_NAME,
       AFTER_OPE_DIAG,
       AFTER_OPE_DIAG_NAME,
       OPERA_START_DATE,
       OPERA_END_DATE,
       OPERA_CODE,
       OPERA_NAME,
       OPERA_GRADE,
       OPERA_BP_CODE,
       INTER_BODY,
       OPERA_POSI,
       OPERA_POSI_NAME,
       OPERATION_NOTE,
       OPERATION_HIS,
       DISINF_NOTE,
       INCISION_NOTE,
       DRAINAGE_CODE,
       OUT_BLOOD_ML,
       BEFORE_DRUG,
       IN_DRUG,
       DRAINAGE_TYPE,
       DRAINAGE_AMOUNT,
       PLACE,
       BT_REACTION_MARK,
       SURGEON_NAME,
       ASSISTANT_FIR_NAME,
       ASSISTANT_SED_NAME,
       INS_NURSE_NAME,
       ROUND_NURSE_NAME,
       ANAESTHESIA_CODE,
       ANESTHESIA_DOC_NAME,
       SIGNATURE_DATE,
       DISTRICT_CODE,
       EXCHANGE_TYPE,
       SYSTEM_TIME,
       SURGEON_CERTIFICATE_NO,
       ANESTHESIA,
       INCISION_HEALING_LEVEL_CODE,
       WOUNDHEAL_LEVEL_CODE,
       ANES_CERTIFICATE_NO,
       LOCAL_PROCEDURE_CODE,
       LOCAL_PROCEDURE_NAME,
       NHS_PROCEDURE_CODE,
       NHS_PROCEDURE_NAME,
       IS_MAIN_PROCEDURE,
      to_char( OPERATE_TYPE)  OPERATE_TYPE
from (
    select q.*,
           row_number() over (
               partition by q.ID
               order by q.OPERA_START_DATE desc nulls last,
                        q.SIGNATURE_DATE desc nulls last
           ) as rn
    from (
        select substr(
                   '49557032X'||'|'||
                   nvl(to_char(pv.patient_id), '-')||'|'||
                   nvl(to_char(pv.visit_id), '-')||'|'||
                   nvl(to_char(o.operation_no), to_char(t1.id)),
                   1,
                   100
               ) as ID,--  内码  是 使用组织机构编码+业务主键或流水号

               '49557032X' as ORG_CODE,--  组织机构代码  是 医疗机构组织机构代码

               '山东省第二人民医院' as ORG_NAME,--  组织机构名称  是 医疗机构组织机构名称

               '2' as PATIENT_TYPE,--  病人类型  是 1:门急诊 2：住院

               substr(
                   nvl(to_char(pv.patient_id), '-')||'|'||nvl(to_char(pv.visit_id), '-'),
                   1,
                   32
               ) as VISTING_NUM,-- 就诊唯一标识号 是 门诊或者住院唯一标识号

               substr(
                   nvl(mom.PATIENT_ID||mom.VISIT_ID||mom.OPER_ID, to_char(t1.id)),
                   1,
                   20
               ) as APPLY_NUM,-- 电子申请单编号 是 手术申请单编号

               substr(
                   nvl(
                       (select cast(ks.qmpt_name as varchar2(50))
                          from his.dept_dict ks
                         where ks.dept_code = t.p_dept_code
                           and rownum = 1),
                       nvl(
                           (select cast(ks.dept_name as varchar2(50))
                              from his.dept_dict ks
                             where ks.dept_code = t.p_dept_code
                               and rownum = 1),
                           '-'
                       )
                   ),
                   1,
                   50
               ) as DEPT_NAME,-- 科室名称  是 患者在医疗机构就诊的科室名称

               substr(cast(t.p_are_name as varchar2(50)), 1, 50) as WARD_NAME,-- 病区名称

               cast(null as varchar2(10)) as EORD_NUM,-- 病房号

               substr(cast(t.p_bedno as varchar2(10)), 1, 10) as SICKBED_NUM,-- 病床号

               substr(
                   nvl(nullif(trim(cast(mom.operating_room_no as varchar2(20))), ''), '-'),
                   1,
                   20
               ) as OPERA_ROOM_NUM,-- 手术间编号

               substr(
                   nvl(nullif(trim(cast(t.p_name as varchar2(50))), ''), nvl(cast(pmi.name as varchar2(50)), '-')),
                   1,
                   50
               ) as NAME,-- 患者姓名

               case
                   when cast(pmi.sex as varchar2(10)) = '男' then 1
                   when cast(pmi.sex as varchar2(10)) = '女' then 2
                   when cast(pmi.sex as varchar2(10)) = '未知' then 0
                   else 9
               end as SEX_CODE,-- 性别代码

               substr(
                   case
                       when cast(pmi.sex as varchar2(10)) = '男' then '男'
                       when cast(pmi.sex as varchar2(10)) = '女' then '女'
                       when cast(pmi.sex as varchar2(10)) = '未知' then '未知'
                       else '不明'
                   end,
                   1,
                   50
               ) as SEX_NAME,-- 性别名称

               case
                   when pmi.date_of_birth is not null
                    and pv.admission_date_time is not null
                   then least(
                            greatest(trunc(months_between(pv.admission_date_time, pmi.date_of_birth) / 12), 0),
                            200
                        )
                   else 0
               end as AGE,-- 年龄


                   nvl( nvl(   (select max(cd.国标编码)
            from cda.cda_dictionary cd
           where cd.字典名称 = 'ICD-10诊断编码'
             and cd.系统标识 = 'SM'
             and cd.院标名称 = mom.DIAG_before_OPERATION)    ,
              (select max(cd.国标编码)
            from cda.cda_dictionary cd
           where cd.字典名称 = 'ICD-10诊断编码'
             and cd.系统标识 = 'HIS'
             and cd.院标编码 = dd.diagnosis_code)
       ),         dd.diagnosis_code)      AS BEF_OPE_DIAG  ,-- 术前诊断编码


                   nvl( nvl(   (select max(cd.国标名称)
            from cda.cda_dictionary cd
           where cd.字典名称 = 'ICD-10诊断编码'
             and cd.系统标识 = 'SM'
             and cd.院标名称 = mom.DIAG_before_OPERATION)    ,
              (select max(cd.国标名称)
            from cda.cda_dictionary cd
           where cd.字典名称 = 'ICD-10诊断编码'
             and cd.系统标识 = 'HIS'
             and cd.院标编码 = dd.diagnosis_code)
       ),         dd.diagnosis_desc)     as BEF_OPE_DIAG_NAME,-- 术前诊断名称

               substr(cast(df.diagnosis_code as varchar2(12)), 1, 12) as AFTER_OPE_DIAG,-- 术后诊断编码

               substr(
                   nvl(cast(df.diagnosis_desc as varchar2(50)), '-'),
                   1,
                   50
               ) as AFTER_OPE_DIAG_NAME,-- 术后诊断名称

               cast(
                   coalesce(mom.start_date_time, o.operating_date, t1.doc_title_time)
                   as date
               ) as OPERA_START_DATE,-- 手术开始日期时间

               cast(
                   coalesce(mom.end_date_time, o.operating_end_date, mom.start_date_time, o.operating_date, t1.doc_title_time)
                   as date
               ) as OPERA_END_DATE,-- 手术结束日期时间

               substr(
                   nvl(
                       nvl(
                           nvl(     (select cast(cd.国标编码 as varchar2(12))
                              from cda.cda_dictionary cd
                             where cast(cd.字典名称 as varchar2(100)) = 'ICD-9手术编码'
                               and cast(cd.系统标识 as varchar2(20)) = 'SM'
                               and cast(cd.院标名称 as varchar2(200)) = cast(mom.operation_name as varchar2(200))
                               and rownum = 1)   ,
                               (select cast(cd.国标编码 as varchar2(12))
                                  from cda.cda_dictionary cd
                                 where cast(cd.字典名称 as varchar2(100)) = 'ICD-9手术编码'
                                   and cast(cd.系统标识 as varchar2(20)) = 'HIS'
                 and (cd.院标编码 =         regexp_replace(trim(cast(o.operation_code as varchar2(100))), '[A-Z][0-9]*$', '') or cd.院标编码 = o.operation_code )
                                   and rownum = 1)
                           ),


                               (select cast(cd.国标编码 as varchar2(12))
                                  from cda.cda_dictionary cd
                                 where cast(cd.字典名称 as varchar2(100)) = 'ICD-9手术编码'
                                   and cast(cd.系统标识 as varchar2(20)) = 'HIS'
                                   and cast(cd.院标名称 as varchar2(200)) = cast(o.operation_desc as varchar2(200))
                                   and rownum = 1)



                       ),
                       cast(o.operation_code as varchar2(12))
                   ),
                   1,
                   12
               ) as OPERA_CODE,-- 手术及操作编码

              nvl( substr(
                   nvl(
                       nvl(
                           nvl((select cast(cd.国标名称 as varchar2(80))
                              from cda.cda_dictionary cd
                             where cast(cd.字典名称 as varchar2(100)) = 'ICD-9手术编码'
                               and cast(cd.系统标识 as varchar2(20)) = 'SM'
                               and cast(cd.院标名称 as varchar2(200)) = cast(mom.operation_name as varchar2(200))
                               and rownum = 1)  ,
                               (select cast(cd.国标名称 as varchar2(80))
                                  from cda.cda_dictionary cd
                                 where cast(cd.字典名称 as varchar2(100)) = 'ICD-9手术编码'
                                   and cast(cd.系统标识 as varchar2(20)) = 'HIS'
                 and (cd.院标编码 =         regexp_replace(trim(cast(o.operation_code as varchar2(100))), '[A-Z][0-9]*$', '') or cd.院标编码 = o.operation_code )
                                   and rownum = 1)
                           ),

                               (select cast(cd.国标名称 as varchar2(80))
                                  from cda.cda_dictionary cd
                                 where cast(cd.字典名称 as varchar2(100)) = 'ICD-9手术编码'
                                   and cast(cd.系统标识 as varchar2(20)) = 'HIS'
                                   and cast(cd.院标名称 as varchar2(200)) = cast(o.operation_desc as varchar2(200))
                                   and rownum = 1)
                       ),
                       nvl(cast(o.operation_desc as varchar2(80)), nvl(cast(mom.operation_name as varchar2(80)), '-'))
                   ),
                   1,
                   80
               ), mom.OPERATION_NAME  ) as OPERA_NAME,-- 手术名称

               case
                   when cast(mom.operation_scale as varchar2(20)) in ('Ⅰ','小','一','1') then 1
                   when cast(mom.operation_scale as varchar2(20)) in ('Ⅱ','中','二','2') then 2
                   when cast(mom.operation_scale as varchar2(20)) in ('Ⅲ','大','三','3') then 3
                   when cast(mom.operation_scale as varchar2(20)) in ('Ⅳ','特','四','4') then 4
                   else 1
               end as OPERA_GRADE,-- 手术级别代码

               substr(cast(t3.ssmbbwmc as varchar2(50)), 1, 50) as OPERA_BP_CODE,-- 手术目标部位名称

               substr(cast(t3.jrwmc as varchar2(100)), 1, 100) as INTER_BODY,-- 介入物名称

               case
                   when regexp_like(
                            nvl(cast(mom.operation_position as varchar2(100)),
                                cast(dbms_lob.substr(t4.段落内容, 2000, 1) as varchar2(2000))),
                            '仰卧|平卧'
                        ) then 1
                   when regexp_like(
                            nvl(cast(mom.operation_position as varchar2(100)),
                                cast(dbms_lob.substr(t4.段落内容, 2000, 1) as varchar2(2000))),
                            '俯卧'
                        ) then 2
                   when regexp_like(
                            nvl(cast(mom.operation_position as varchar2(100)),
                                cast(dbms_lob.substr(t4.段落内容, 2000, 1) as varchar2(2000))),
                            '左侧卧'
                        ) then 3
                   when regexp_like(
                            nvl(cast(mom.operation_position as varchar2(100)),
                                cast(dbms_lob.substr(t4.段落内容, 2000, 1) as varchar2(2000))),
                            '右侧卧|侧卧'
                        ) then 4
                   when regexp_like(
                            nvl(cast(mom.operation_position as varchar2(100)),
                                cast(dbms_lob.substr(t4.段落内容, 2000, 1) as varchar2(2000))),
                            '截石'
                        ) then 5
                   when regexp_like(
                            nvl(cast(mom.operation_position as varchar2(100)),
                                cast(dbms_lob.substr(t4.段落内容, 2000, 1) as varchar2(2000))),
                            '屈氏'
                        ) then 6
                   else 9
               end as OPERA_POSI,-- 手术体位代码

               substr(
                   case
                       when regexp_like(
                                nvl(cast(mom.operation_position as varchar2(100)),
                                    cast(dbms_lob.substr(t4.段落内容, 2000, 1) as varchar2(2000))),
                                '仰卧|平卧'
                            ) then '仰卧位'
                       when regexp_like(
                                nvl(cast(mom.operation_position as varchar2(100)),
                                    cast(dbms_lob.substr(t4.段落内容, 2000, 1) as varchar2(2000))),
                                '俯卧'
                            ) then '俯卧位'
                       when regexp_like(
                                nvl(cast(mom.operation_position as varchar2(100)),
                                    cast(dbms_lob.substr(t4.段落内容, 2000, 1) as varchar2(2000))),
                                '左侧卧'
                            ) then '左侧卧位'
                       when regexp_like(
                                nvl(cast(mom.operation_position as varchar2(100)),
                                    cast(dbms_lob.substr(t4.段落内容, 2000, 1) as varchar2(2000))),
                                '右侧卧|侧卧'
                            ) then '右侧卧位'
                       when regexp_like(
                                nvl(cast(mom.operation_position as varchar2(100)),
                                    cast(dbms_lob.substr(t4.段落内容, 2000, 1) as varchar2(2000))),
                                '截石'
                            ) then '截石位'
                       when regexp_like(
                                nvl(cast(mom.operation_position as varchar2(100)),
                                    cast(dbms_lob.substr(t4.段落内容, 2000, 1) as varchar2(2000))),
                                '屈氏'
                            ) then '屈氏位'
                       else '其他'
                   end,
                   1,
                   50
               ) as OPERA_POSI_NAME,-- 手术体位名称

         NVL(
    SUBSTRB(
        NVL(
            NULLIF(
                TRIM(
                    CASE
                        WHEN t3.ssgcms IS NOT NULL THEN
                             DBMS_LOB.SUBSTR(TO_CLOB(t3.ssgcms), 2000, 1)
                        ELSE NULL
                    END
                ),
                ''
            ),
            NVL(
                NULLIF(
                    TRIM(
                        REGEXP_SUBSTR(
                            DBMS_LOB.SUBSTR(t4.段落内容, 2000, 1),
                            '手术经过、术中发现的情况及处理[[:space:]]*[:：]?[[:space:]]*(.*)',
                            1,
                            1,
                            'n',
                            1
                        )
                    ),
                    ''
                ),
                '-'
            )
        ),
        1,
        2000
    ),
    '-'
) AS     OPERATION_NOTE,-- 手术过程描述

               case
                   when exists (
                       select 1
                         from his.operation oo
                        where oo.patient_id = pv.patient_id
                          and oo.operation_no <> o.operation_no
                          and oo.operating_date < coalesce(o.operating_date, mom.start_date_time, t1.doc_title_time)
                          and not regexp_like(
                                  nvl(cast(oo.operation_desc as varchar2(500)), '-'),
                                  '输血|红细胞|血浆|血细胞|气管内插管|呼吸机|血液透析|血液滤过|中心静脉|鼻十二指肠|动脉穿刺|肺泡灌洗'
                              )
                          and rownum = 1
                   ) then '1'
                   else '0'
               end as OPERATION_HIS,-- 手术史标志

               substr(cast(t3.pfxdms as varchar2(200)), 1, 200) as DISINF_NOTE,-- 皮肤消毒描述

               substr(cast(t3.ssqkms as varchar2(200)), 1, 200) as INCISION_NOTE,-- 手术切口描述

               case
                   when t3.ylclmc is not null then '1'
                   when dbms_lob.instr(t4.段落内容, '置引流', 1, 1) > 0 then '1'
                   when dbms_lob.instr(t4.段落内容, '引流管', 1, 1) > 0 then '1'
                   else '0'
               end as DRAINAGE_CODE,-- 引流标志

          CASE
    WHEN REGEXP_LIKE(TRIM(SUBSTRB(TO_CHAR(t3.cxlml), 1, 20)), '^[0-9]{1,5}([.][0-9]+)?$')
    THEN LEAST(
             TRUNC(TO_NUMBER(TRIM(SUBSTRB(TO_CHAR(t3.cxlml), 1, 20)))),
             99999
         )

    WHEN REGEXP_LIKE(
             DBMS_LOB.SUBSTR(t4.段落内容, 2000, 1),
             '出血[^0-9]{0,10}[0-9]{1,5}'
         )
    THEN LEAST(
             TO_NUMBER(
                 REGEXP_SUBSTR(
                     DBMS_LOB.SUBSTR(t4.段落内容, 2000, 1),
                     '出血[^0-9]{0,10}([0-9]{1,5})',
                     1,
                     1,
                     'n',
                     1
                 )
             ),
             99999
         )

    ELSE 0
END   as OUT_BLOOD_ML,-- 出血量

               substr(cast(t3.sqyy as varchar2(100)), 1, 100) as BEFORE_DRUG,-- 术前用药

               substr(cast(t3.szyy as varchar2(100)), 1, 100) as IN_DRUG,-- 术中用药

               substr(cast(t3.ylclmc as varchar2(200)), 1, 200) as DRAINAGE_TYPE,-- 引流材料名称

               substr(cast(t3.ylclsm as varchar2(200)), 1, 200) as DRAINAGE_AMOUNT,-- 引流材料数目

               substr(cast(t3.fzbw as varchar2(50)), 1, 50) as PLACE,-- 放置部位

               case
                   when cast(t3.sxfybz as varchar2(20)) in ('1','是','true','TRUE') then '1'
                   when cast(t3.sxfybz as varchar2(20)) in ('0','否','false','FALSE') then '0'
                   when dbms_lob.instr(t4.段落内容, '未输血', 1, 1) > 0 then '3'
                   when dbms_lob.instr(t4.段落内容, '输血', 1, 1) > 0 then '0'
                   when dbms_lob.instr(t4.段落内容, '红细胞', 1, 1) > 0 then '0'
                   when dbms_lob.instr(t4.段落内容, '血浆', 1, 1) > 0 then '0'
                   else '3'
               end as BT_REACTION_MARK,-- 输血反应标志

               nvl( nvl(  (select cast(sd.name as varchar2(50))
                                   from his.staff_dict sd
                                  where sd.emp_no = o.OPERATOR
                                    and rownum = 1), (select cast(sd.name as varchar2(50))
                                   from his.staff_dict sd
                                  where sd.emp_no = mom.SURGEON
                                    and rownum = 1 )),              '-')     as SURGEON_NAME,-- 手术者姓名

               substr(
                   nvl(
                       cast(mom.first_assistant as varchar2(50)),
                       regexp_replace(
                           regexp_substr(
                               cast(dbms_lob.substr(t4.段落内容, 2000, 1) as varchar2(2000)),
                               '一助[[:space:]]*[:：]?[[:space:]]*([^[:cntrl:]，,；;二]+)',
                               1,
                               1,
                               'n',
                               1
                           ),
                           '[[:punct:]]',
                           ''
                       )
                   ),
                   1,
                   50
               ) as ASSISTANT_FIR_NAME,-- Ⅰ助姓名

               substr(cast(mom.second_assistant as varchar2(50)), 1, 50) as ASSISTANT_SED_NAME,-- Ⅱ助姓名

               substr(
                   nvl(
                       case
                           when regexp_like(cast(t3.qxhsxm as varchar2(50)), '^[0-9]+$')
                           then (select cast(sd.name as varchar2(50))
                                   from his.staff_dict sd
                                  where sd.emp_no = t3.qxhsxm
                                    and rownum = 1)
                           else cast(t3.qxhsxm as varchar2(50))
                       end,
                       case
                           when regexp_like(cast(mom.first_supply_nurse as varchar2(50)), '^[0-9]+$')
                           then (select cast(sd.name as varchar2(50))
                                   from his.staff_dict sd
                                  where sd.emp_no = mom.first_supply_nurse
                                    and rownum = 1)
                           else cast(mom.first_supply_nurse as varchar2(50))
                       end
                   ),
                   1,
                   50
               ) as INS_NURSE_NAME,-- 器械护士姓名

               substr(
                   nvl(
                       case
                           when regexp_like(cast(t3.xthsxm as varchar2(50)), '^[0-9]+$')
                           then (select cast(sd.name as varchar2(50))
                                   from his.staff_dict sd
                                  where sd.emp_no = t3.xthsxm
                                    and rownum = 1)
                           else cast(t3.xthsxm as varchar2(50))
                       end,
                       case
                           when regexp_like(cast(mom.first_operation_nurse as varchar2(50)), '^[0-9]+$')
                           then (select cast(sd.name as varchar2(50))
                                   from his.staff_dict sd
                                  where sd.emp_no = mom.first_operation_nurse
                                    and rownum = 1)
                           else cast(mom.first_operation_nurse as varchar2(50))
                       end
                   ),
                   1,
                   50
               ) as ROUND_NURSE_NAME,-- 巡台护士姓名

               to_number(
                   nvl(
                       regexp_substr(
                           nvl(
                               nvl(
                                   (select cast(cd.国标编码 as varchar2(20))
                                      from cda.cda_dictionary cd
                                     where cast(cd.字典名称 as varchar2(100)) = '麻醉方法代码表'
                                       and cast(cd.系统标识 as varchar2(20)) = 'HIS'
                                       and cast(cd.院标名称 as varchar2(100)) = cast(o.anaesthesia_method as varchar2(100))
                                       and rownum = 1),
                                   (select cast(cd.国标编码 as varchar2(20))
                                      from cda.cda_dictionary cd
                                     where cast(cd.字典名称 as varchar2(100)) = '麻醉方法代码表'
                                       and cast(cd.系统标识 as varchar2(20)) = '手麻'
                                       and cast(cd.院标名称 as varchar2(100)) = cast(mom.anesthesia_method as varchar2(100))
                                       and rownum = 1)
                               ),
                               '9'
                           ),
                           '^[0-9]+'
                       ),
                       '9'
                   )
               ) as ANAESTHESIA_CODE,-- 麻醉方法代码

               substr(
                   nvl(
                       case
                           when regexp_like(cast(mom.anesthesia_doctor as varchar2(50)), '^[0-9]+$')
                           then (select cast(sd.name as varchar2(50))
                                   from his.staff_dict sd
                                  where sd.emp_no = mom.anesthesia_doctor
                                    and rownum = 1)
                           else cast(mom.anesthesia_doctor as varchar2(50))
                       end,
                       '-'
                   ),
                   1,
                   50
               ) as ANESTHESIA_DOC_NAME,-- 麻醉医师姓名

               cast(
                   nvl(t1.doc_title_time, coalesce(mom.end_date_time, o.operating_end_date, mom.start_date_time, o.operating_date))
                   as date
               ) as SIGNATURE_DATE,-- 签名日期时间

               '370104' as DISTRICT_CODE,-- 行政区划

               'ADDHIS' as EXCHANGE_TYPE,-- 交换类型

               cast(systimestamp as timestamp) as SYSTEM_TIME,-- 数据上传时间

         nvl( nvl(  (select yg.PRACTICE_CERT_CODE
              from DOC_REGISTER_EMP_MATCH yg
             where yg.emp_no = o.OPERATOR
               and rownum = 1), (select yg.PRACTICE_CERT_CODE
              from DOC_REGISTER_EMP_MATCH yg
             where yg.emp_no = mom.SURGEON
               and rownum = 1)),              '-')   as SURGEON_CERTIFICATE_NO,-- 术者执业证书编号

               case
                   when o.anaesthesia_method is not null
                     or mom.anesthesia_method is not null
                     or mom.anesthesia_doctor is not null
                     or dbms_lob.instr(t4.段落内容, '麻醉方法', 1, 1) > 0
                   then '1'
                   else '0'
               end as ANESTHESIA,-- 是否进行麻醉
substr(
    case
        when regexp_replace(upper(trim(cast(o.heal as varchar2(100)))), '[[:space:]]+', '')
             in ('0','0类','0类切口','零','零类','零类切口')
        then '1'

        when regexp_replace(upper(trim(cast(o.heal as varchar2(100)))), '[[:space:]]+', '')
             in ('I','Ⅰ','1','一','一类','I类','Ⅰ类','I类切口','Ⅰ类切口','一类切口','甲')
        then '2'

        when regexp_replace(upper(trim(cast(o.heal as varchar2(100)))), '[[:space:]]+', '')
             in ('II','Ⅱ','2','二','二类','II类','Ⅱ类','II类切口','Ⅱ类切口','二类切口','乙')
        then '3'

        when regexp_replace(upper(trim(cast(o.heal as varchar2(100)))), '[[:space:]]+', '')
             in ('III','Ⅲ','3','三','三类','III类','Ⅲ类','III类切口','Ⅲ类切口','三类切口','丙','4')
        then '4'

        else cast(null as varchar2(100))
    end,
    1,
    100
)  as INCISION_HEALING_LEVEL_CODE,-- 切口类别代码，暂无确定来源

               substr(
    case
        when regexp_replace(upper(trim(cast(o.wound_grade as varchar2(100)))), '[[:space:]]+', '')
             in ('甲','1')
        then '1'

        when regexp_replace(upper(trim(cast(o.wound_grade as varchar2(100)))), '[[:space:]]+', '')
             in ('乙','2')
        then '2'

        when regexp_replace(upper(trim(cast(o.wound_grade as varchar2(100)))), '[[:space:]]+', '')
             in ('丙','3')
        then '3'

        when regexp_replace(upper(trim(cast(o.wound_grade as varchar2(100)))), '[[:space:]]+', '')
             in ('其他','其','4','未知','不详','不确定','-')
        then '4'

        else cast(null as varchar2(100))
    end,
    1,
    100
)   as WOUNDHEAL_LEVEL_CODE,-- 切口愈合等级代码，暂无确定来源

                 nvl(  (select yg.PRACTICE_CERT_CODE
              from DOC_REGISTER_EMP_MATCH yg
             where yg.emp_no = o.ANESTHESIA_DOCTOR
               and rownum = 1)  ,  (select yg.PRACTICE_CERT_CODE
              from DOC_REGISTER_EMP_MATCH yg
             where yg.emp_no = mom.ANESTHESIA_DOCTOR
               and rownum = 1)  )    as ANES_CERTIFICATE_NO,-- 麻醉医师执业证书编号


               substr(
                   nvl(
                       cast(o.operation_code as varchar2(100)),
                       nvl(
                           (select cast(cd.国标编码 as varchar2(100))
                              from cda.cda_dictionary cd
                             where cast(cd.字典名称 as varchar2(100)) = 'ICD-9手术编码'
                               and cast(cd.系统标识 as varchar2(20)) = 'SM'
                               and cast(cd.院标名称 as varchar2(200)) = cast(mom.operation_name as varchar2(200))
                               and rownum = 1),
                           '99.9900'
                       )
                   ),
                   1,
                   100
               ) as LOCAL_PROCEDURE_CODE,-- 机构内部手术及操作编码

               substr(
                   nvl(cast(o.operation_desc as varchar2(500)), nvl(cast(mom.operation_name as varchar2(500)), '其他各类操作')),
                   1,
                   500
               ) as LOCAL_PROCEDURE_NAME,-- 机构内部手术及操作名称

               substr(
                   nvl(
                       nvl(
                           nvl(
                               (select cast(cd.国标编码 as varchar2(100))
                                  from cda.cda_dictionary cd
                                 where cast(cd.字典名称 as varchar2(100)) = 'ICD-9手术编码'
                                   and cast(cd.系统标识 as varchar2(20)) = 'HIS'
                                   and cast(cd.院标名称 as varchar2(200)) = cast(o.operation_desc as varchar2(200))
                                   and rownum = 1),
                               (select cast(cd.国标编码 as varchar2(100))
                                  from cda.cda_dictionary cd
                                 where cast(cd.字典名称 as varchar2(100)) = 'ICD-9手术编码'
                                   and cast(cd.系统标识 as varchar2(20)) = 'HIS'
                                   and cast(cd.院标编码 as varchar2(100)) = cast(o.operation_code as varchar2(100))
                                   and rownum = 1)
                           ),
                           (select cast(cd.国标编码 as varchar2(100))
                              from cda.cda_dictionary cd
                             where cast(cd.字典名称 as varchar2(100)) = 'ICD-9手术编码'
                               and cast(cd.系统标识 as varchar2(20)) = 'SM'
                               and cast(cd.院标名称 as varchar2(200)) = cast(mom.operation_name as varchar2(200))
                               and rownum = 1)
                       ),
                       '99.9900'
                   ),
                   1,
                   100
               ) as NHS_PROCEDURE_CODE,-- 国家医保手术及操作编码

               substr(
                   nvl(
                       nvl(
                           nvl(
                               (select cast(cd.国标名称 as varchar2(500))
                                  from cda.cda_dictionary cd
                                 where cast(cd.字典名称 as varchar2(100)) = 'ICD-9手术编码'
                                   and cast(cd.系统标识 as varchar2(20)) = 'HIS'
                                   and cast(cd.院标名称 as varchar2(200)) = cast(o.operation_desc as varchar2(200))
                                   and rownum = 1),
                               (select cast(cd.国标名称 as varchar2(500))
                                  from cda.cda_dictionary cd
                                 where cast(cd.字典名称 as varchar2(100)) = 'ICD-9手术编码'
                                   and cast(cd.系统标识 as varchar2(20)) = 'HIS'
                                   and cast(cd.院标编码 as varchar2(100)) = cast(o.operation_code as varchar2(100))
                                   and rownum = 1)
                           ),
                           (select cast(cd.国标名称 as varchar2(500))
                              from cda.cda_dictionary cd
                             where cast(cd.字典名称 as varchar2(100)) = 'ICD-9手术编码'
                               and cast(cd.系统标识 as varchar2(20)) = 'SM'
                               and cast(cd.院标名称 as varchar2(200)) = cast(mom.operation_name as varchar2(200))
                               and rownum = 1)
                       ),
                       '其他各类操作'
                   ),
                   1,
                   500
               ) as NHS_PROCEDURE_NAME,-- 国家医保手术及操作名称

               case
                   when o.op_primary = '1' then '1'
                   when to_char(o.operation_no) = '1' then '1'
                   else '0'
               end as IS_MAIN_PROCEDURE,-- 是否主要手术或操作

         CAST(     case when  mom.EMERGENCY_INDICATOR = 0 then 1 when mom.EMERGENCY_INDICATOR =1 then 2 else 9 end   AS
  VARCHAR2(1))   as OPERATE_TYPE -- 手术类型

        from mtl.epr_inpatient_docindex t

        inner join mtl.epr_inpatient t1
                on t.uhid = t1.uhid
               and t1.doc_type_name like '%手术记录%'

        left join mtl.emrsd9 t3
               on t3.段落编号 = t1.id

        left join his.pat_master_index pmi
               on pmi.inp_no = t.p_inpatient_no

        inner join his.pat_visit pv
                on pv.patient_id = pmi.patient_id
               and pv.visit_id = t.p_inpatient_times


        left join sm.med_operation_master mom
               on mom.patient_id = pv.patient_id
              and mom.visit_id = pv.visit_id

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
               on pv.patient_id = o.patient_id
              and pv.visit_id = o.visit_id
            and to_char(o.operating_date,'yyyy-mm-dd')=to_char( nvl(mom.start_date_time,mom.SCHEDULED_DATE_TIME),'yyyy-mm-dd')
        left join sm.med_diagnosis_dict c
               on mom.diag_before_operation = c.diagnosis_name

        left join (
            select patient_id,
                   visit_id,
                   diagnosis_code,
                   diagnosis_desc,
                   row_number() over (
                       partition by patient_id, visit_id
                       order by diagnosis_date desc nulls last,
                                diagnosis_no
                   ) as rn
              from his.diagnosis where diagnosis_type='3'
        ) dd
               on dd.rn = 1
              and dd.patient_id = pv.patient_id
              and dd.visit_id = pv.visit_id
   left join (
            select patient_id,
                   visit_id,
                   diagnosis_code,
                   diagnosis_desc,
                   row_number() over (
                       partition by patient_id, visit_id
                       order by diagnosis_date desc nulls last,
                                diagnosis_no
                   ) as rn
              from his.diagnosis
        ) df
               on df.rn = 1
              and df.patient_id = pv.patient_id
              and df.visit_id = pv.visit_id
        left join mtl.emrsd_content t4
               on t4.uhid = t.uhid
              and t4.段落编号 = t1.id

        where pv.discharge_date_time >= to_date('2021-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss')
          and pv.discharge_date_time <  to_date('2025-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss')
    ) q
)
where rn = 1 and    BEF_OPE_DIAG_NAME is not null
