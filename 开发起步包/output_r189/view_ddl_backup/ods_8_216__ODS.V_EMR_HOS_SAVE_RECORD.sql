
  CREATE OR REPLACE FORCE VIEW "ODS"."V_EMR_HOS_SAVE_RECORD" ("ID", "ORG_CODE", "ORG_NAME", "DISTRICT_CODE", "EXCHANGE_TYPE", "SYSTEM_TIME", "ADMISSION_UN_NUM", "DEPT_CODE", "DEP_NAME", "AREA_NAME", "WARD_NUM", "SICKBED_NUM", "DISEASE", "DISEASE_CODE", "CHANGE_CONDITION", "RESCUE_MEASURES", "OPERATION_CODE", "OPERATION_NAME", "OPERATION_BP_NAME", "INTER_BODY", "OPER_METHODE", "OPER_TIMES", "SALVAGE_START_DATE", "SALVAGE_END_DATE", "CHECK_VERIFY_PRO_NAME", "CHECK_VERIFY_RESULT", "CHECK_VERIFY_QUANT_RESULT", "CHECK_VERIFY_RESULT_CODE", "MATTERS_ATTENTION", "RESCUERS_LIST", "PROF_TECH_CATE_CODE", "PROF_TECH_CATE_NAME", "DOC_NAME", "SIGN_DATE") AS 
  select substr(
           '49557032X'||'|'||nvl(z.patient_id, z.p_clinic_id)||'|'||z.p_inpatient_times||'|'||z.uhid||'|'||z.doc_id,
           1,
           100
       ) as ID,--  内码  是  主键

       '49557032X' as ORG_CODE,--  医院组织机构代码  是  必填、机构验证

       '山东省第二人民医院' as ORG_NAME,--  医院名称  是  必填，填写标准医院名称

       '370104' as DISTRICT_CODE,-- 所属行政区划  是 按机构所在的行政区划（区县）

       'ADDHIS' as EXCHANGE_TYPE,-- 交换类型  是 INSERT：向平台传新数据时 UPDATE：向平台更新某条数据时 DELETE：从平台删除某条数据时 ADDHIS :向平台补充历史数据

       cast(systimestamp as timestamp) as SYSTEM_TIME,-- 数据上传时间戳 是

       substr(
           nvl(z.patient_id||'|'||z.p_inpatient_times, z.p_inpatient_no||'|'||z.p_inpatient_times),
           1,
           50
       ) as ADMISSION_UN_NUM,--  住院唯一标示号 是

       nvl(
           (select dd.qmpt_code
              from his.dept_dict dd
             where dd.dept_code = z.p_dept_code
               and rownum = 1),
           z.p_dept_code
       ) as DEPT_CODE,-- 科室代码

       nvl(
           (select dd.qmpt_name
              from his.dept_dict dd
             where dd.dept_code = z.p_dept_code
               and rownum = 1),
           z.p_dept_name
       ) as DEP_NAME,--  科室名称  是

       z.p_are_name as AREA_NAME,-- 病区名称

       cast(null as varchar2(10)) as WARD_NUM,--  病房号

       substr(z.p_bedno, 1, 10) as SICKBED_NUM,-- 病床号

       substr(
           nvl(z.diagnosis_desc, '未明确诊断'),
           1,
           50
       ) as DISEASE,-- 疾病诊断名称  是

       substr(
           z.diagnosis_code,
           1,
           12
       ) as DISEASE_CODE,--  疾病诊断编码  是 按照平台值域填写，不做默认兜底

       substr(
           nvl(
               z.Bqbhqk,
               nvl(
                   regexp_substr(
                       z.content_text,
                       '抢[[:space:]]*救[[:space:]]*记[[:space:]]*录[[:space:]]*(.*?)(立即|即刻|给予|予以|嘱|行|反复给予|持续|经抢救|参加抢救人员|参与抢救人员|抢救者|医师签名|$)',
                       1, 1, 'n', 1
                   ),
                   z.content_text
               )
           ),
           1,
           1000
       ) as CHANGE_CONDITION,--  病情变化情况  是

       substr(
           nvl(
               z.Qjcs,
               nvl(
                   regexp_substr(
                       z.content_text,
                       '(立即|即刻|给予|予以|嘱|行|反复给予|持续|经抢救|抢救处理)[[:space:]]*(.*?)(参加抢救人员|参与抢救人员|抢救者|医师签名|$)',
                       1, 1, 'n'
                   ),
                   z.content_text
               )
           ),
           1,
           1000
       ) as RESCUE_MEASURES,-- 抢救措施  是

       cast(null as varchar2(12)) as OPERATION_CODE,--  手术及操作编码，是否将气管插管、胸外按压等作为操作需确认

       cast(null as varchar2(80)) as OPERATION_NAME,--  手术及操作名称，是否将气管插管、胸外按压等作为操作需确认

       cast(null as varchar2(50)) as OPERATION_BP_NAME,-- 手术及操作目标部位名称

       cast(null as varchar2(100)) as INTER_BODY,--  介入物名称

       cast(null as varchar2(2000)) as OPER_METHODE,--  操作方法描述

       cast(null as number(3)) as OPER_TIMES,--  操作次数

       z.salvage_start_calc as SALVAGE_START_DATE,--  抢救开始日期时间  是 YYYYMMDD HHMISS

       cast(
           nvl(
               /* 1. 优先取结构化抢救结束时间 */
               case
                 when regexp_like(z.Qjjsrqsj_txt, '^[0-9]{14}$')
                 then to_date(z.Qjjsrqsj_txt, 'yyyymmddhh24miss')

                 when regexp_like(z.Qjjsrqsj_txt, '^[0-9]{8}$')
                 then to_date(z.Qjjsrqsj_txt, 'yyyymmdd')

                 when regexp_like(
                        z.Qjjsrqsj_txt,
                        '[0-9]{4}[-./][0-9]{1,2}[-./][0-9]{1,2}[[:space:]]+[0-9]{1,2}[：:][0-9]{2}[：:][0-9]{2}'
                      )
                 then to_date(
                        replace(
                          replace(
                            replace(
                              regexp_substr(
                                z.Qjjsrqsj_txt,
                                '[0-9]{4}[-./][0-9]{1,2}[-./][0-9]{1,2}[[:space:]]+[0-9]{1,2}[：:][0-9]{2}[：:][0-9]{2}',
                                1, 1, 'n'
                              ),
                              '/', '-'
                            ),
                            '.', '-'
                          ),
                          '：', ':'
                        ),
                        'yyyy-mm-dd hh24:mi:ss'
                      )

                 when regexp_like(
                        z.Qjjsrqsj_txt,
                        '[0-9]{4}[-./][0-9]{1,2}[-./][0-9]{1,2}[[:space:]]+[0-9]{1,2}[：:][0-9]{2}'
                      )
                 then to_date(
                        replace(
                          replace(
                            replace(
                              regexp_substr(
                                z.Qjjsrqsj_txt,
                                '[0-9]{4}[-./][0-9]{1,2}[-./][0-9]{1,2}[[:space:]]+[0-9]{1,2}[：:][0-9]{2}',
                                1, 1, 'n'
                              ),
                              '/', '-'
                            ),
                            '.', '-'
                          ),
                          '：', ':'
                        ),
                        'yyyy-mm-dd hh24:mi'
                      )
               end,

               nvl(
                   /* 2. 从正文中提取“抢救成功/停止抢救/宣布临床死亡”附近时间 */
                   case
                     when regexp_substr(
                            z.content_text,
                            '([0-9]{1,2})[：:]([0-9]{2})[分]?[[:space:]]*[^。；;]{0,60}(抢救成功|停止抢救|宣布临床死亡|临床死亡)',
                            1, 1, 'n', 1
                          ) is not null
                     then trunc(z.salvage_start_calc)
                          +
                          (
                            to_number(
                              regexp_substr(
                                z.content_text,
                                '([0-9]{1,2})[：:]([0-9]{2})[分]?[[:space:]]*[^。；;]{0,60}(抢救成功|停止抢救|宣布临床死亡|临床死亡)',
                                1, 1, 'n', 1
                              )
                            ) * 60
                            +
                            to_number(
                              regexp_substr(
                                z.content_text,
                                '([0-9]{1,2})[：:]([0-9]{2})[分]?[[:space:]]*[^。；;]{0,60}(抢救成功|停止抢救|宣布临床死亡|临床死亡)',
                                1, 1, 'n', 2
                              )
                            )
                          ) / 1440
                   end,

                   nvl(
                       /* 3. 文书完成时间只有在开始后 6 小时内才作为结束时间 */
                       case
                         when z.doc_finish_date is not null
                          and z.doc_finish_date > date '1900-01-01'
                          and z.doc_finish_date >= z.salvage_start_calc
                          and z.doc_finish_date <= z.salvage_start_calc + 6 / 24
                         then z.doc_finish_date
                       end,

                       /* 4. 否则默认抢救开始后 20 分钟，避免跨天或相差多天 */
                       z.salvage_start_calc + 20 / 1440
                   )
               )
           ) as date
       ) as SALVAGE_END_DATE,--  抢救结束日期时间  是 YYYYMMDD HHMISS

       substr(nullif(z.jcjyxmmc, ''), 1, 80) as CHECK_VERIFY_PRO_NAME,-- 检查/检验项目名称，是否从正文血气分析等拆分需确认

       substr(nullif(z.Jcjyjg, ''), 1, 1000) as CHECK_VERIFY_RESULT,-- 检查/检验结果，是否从正文血气分析等拆分需确认

       case
         when regexp_like(z.Jcjydljg_txt, '^-?[0-9]+(\.[0-9]+)?$')
         then to_number(z.Jcjydljg_txt)
         else cast(null as number(14,4))
       end as CHECK_VERIFY_QUANT_RESULT,-- 检查/检验定量结果

       case
         when regexp_like(z.Jcjyjgdm_txt, '^[123]$')
         then to_number(z.Jcjyjgdm_txt)
         else 3
       end as CHECK_VERIFY_RESULT_CODE,--  检查/检验结果代码   1：阳性  2：阴性  3：其他

       substr(
           nvl(
               z.Zysx,
               regexp_substr(
                   z.content_text,
                   '注[[:space:]]*意[[:space:]]*事[[:space:]]*项[[:space:]]*[:：][[:space:]]*(.*?)(参加抢救人员|参与抢救人员|抢救者|医师签名|$)',
                   1, 1, 'n', 1
               )
           ),
           1,
           1000
       ) as MATTERS_ATTENTION,-- 注意事项

       substr(
           regexp_replace(
             regexp_replace(
               regexp_replace(
                 nvl(
                   regexp_substr(
                     z.content_text,
                     '(参加抢救人员|参与抢救人员|抢救者|抢救人员)[[:space:]]*[:：]?[[:space:]]*(.*?)(抢救时|整个抢救过程|患者家属|医师签名|$)',
                     1, 1, 'n', 2
                   ),
                   nvl(z.Cjqjrymd, z.doc_name)
                 ),
                 '主任医师|副主任医师|主治医师|住院医师|主管护师|护师|护士长|护士|医师|医生|等多人|等',
                 ''
               ),
               '[、,，;；及和[:space:]]+',
               '#'
             ),
             '[#。；;]+$',
             ''
           ),
           1,
           200
       ) as RESCUERS_LIST,-- 参加抢救人员名单

       (
         select max(to_number(cd.国标编码))
           from cda.cda_dictionary cd
          where cd.字典名称 = '专业技术职务类别代码'
            and regexp_like(cd.国标编码, '^[0-9]+$')
            and cd.院标名称 = nvl(
                  (select sd.title
                     from his.staff_dict sd
                    where sd.name = z.doc_name
                      and rownum = 1),
                  z.attending_title
                )
       ) as PROF_TECH_CATE_CODE,-- 专业技术职务类别代码，优先按签名医生职称取

       substr(
           nvl(
             (select sd.title
                from his.staff_dict sd
               where sd.name = z.doc_name
                 and rownum = 1),
             z.attending_title
           ),
           1,
           50
       ) as PROF_TECH_CATE_NAME,-- 专业技术职务类别名称，优先按签名医生职称取

       substr(
           nvl(z.doc_name, z.attending_name),
           1,
           50
       ) as DOC_NAME,--  医师签名  是 主治医生

       cast(
           nvl(
               case
                 when z.doc_finish_date is not null
                  and z.doc_finish_date > date '1900-01-01'
                 then z.doc_finish_date
               end,
               nvl(
                   case
                     when z.doc_title_time is not null
                      and z.doc_title_time > date '1900-01-01'
                     then z.doc_title_time
                   end,
                   nvl(z.createon, sysdate)
               )
           ) as date
       ) as SIGN_DATE --签名日期时间  是

from (
       select y.*,

              cast(
                nvl(
                    /* 1. 优先取结构化抢救开始时间 */
                    case
                      when regexp_like(y.Qjksrqsj_txt, '^[0-9]{14}$')
                      then to_date(y.Qjksrqsj_txt, 'yyyymmddhh24miss')

                      when regexp_like(y.Qjksrqsj_txt, '^[0-9]{8}$')
                      then to_date(y.Qjksrqsj_txt, 'yyyymmdd')

                      when regexp_like(
                             y.Qjksrqsj_txt,
                             '[0-9]{4}[-./][0-9]{1,2}[-./][0-9]{1,2}[[:space:]]+[0-9]{1,2}[：:][0-9]{2}[：:][0-9]{2}'
                           )
                      then to_date(
                             replace(
                               replace(
                                 replace(
                                   regexp_substr(
                                     y.Qjksrqsj_txt,
                                     '[0-9]{4}[-./][0-9]{1,2}[-./][0-9]{1,2}[[:space:]]+[0-9]{1,2}[：:][0-9]{2}[：:][0-9]{2}',
                                     1, 1, 'n'
                                   ),
                                   '/', '-'
                                 ),
                                 '.', '-'
                               ),
                               '：', ':'
                             ),
                             'yyyy-mm-dd hh24:mi:ss'
                           )

                      when regexp_like(
                             y.Qjksrqsj_txt,
                             '[0-9]{4}[-./][0-9]{1,2}[-./][0-9]{1,2}[[:space:]]+[0-9]{1,2}[：:][0-9]{2}'
                           )
                      then to_date(
                             replace(
                               replace(
                                 replace(
                                   regexp_substr(
                                     y.Qjksrqsj_txt,
                                     '[0-9]{4}[-./][0-9]{1,2}[-./][0-9]{1,2}[[:space:]]+[0-9]{1,2}[：:][0-9]{2}',
                                     1, 1, 'n'
                                   ),
                                   '/', '-'
                                 ),
                                 '.', '-'
                               ),
                               '：', ':'
                             ),
                             'yyyy-mm-dd hh24:mi'
                           )
                    end,

                    nvl(
                        /* 2. 从正文里提取“昨日/今日/患者/于 03:31”等实际开始时间 */
                        case
                          when regexp_substr(
                                 y.content_text,
                                 '(昨日|今日|于|患者|今晚|凌晨|午后|晚间|今晨)[^0-9]{0,12}([0-9]{1,2})[：:点]([0-9]{2})?',
                                 1, 1, 'n', 2
                               ) is not null
                          then trunc(y.base_date)
                               +
                               case
                                 when regexp_substr(
                                        y.content_text,
                                        '(昨日|今日|于|患者|今晚|凌晨|午后|晚间|今晨)[^0-9]{0,12}([0-9]{1,2})[：:点]([0-9]{2})?',
                                        1, 1, 'n', 1
                                      ) = '昨日'
                                 then -1
                                 else 0
                               end
                               +
                               (
                                 to_number(
                                   regexp_substr(
                                     y.content_text,
                                     '(昨日|今日|于|患者|今晚|凌晨|午后|晚间|今晨)[^0-9]{0,12}([0-9]{1,2})[：:点]([0-9]{2})?',
                                     1, 1, 'n', 2
                                   )
                                 ) * 60
                                 +
                                 nvl(
                                   to_number(
                                     regexp_substr(
                                       y.content_text,
                                       '(昨日|今日|于|患者|今晚|凌晨|午后|晚间|今晨)[^0-9]{0,12}([0-9]{1,2})[：:点]([0-9]{2})?',
                                       1, 1, 'n', 3
                                     )
                                   ),
                                   0
                                 )
                               ) / 1440
                        end,

                        nvl(
                            /* 3. 从“抢救记录”正文后提取第一处 HH:MI */
                            case
                              when regexp_substr(
                                     y.content_text,
                                     '抢[[:space:]]*救[[:space:]]*记[[:space:]]*录.*?([0-9]{1,2})[：:]([0-9]{2})',
                                     1, 1, 'n', 1
                                   ) is not null
                              then trunc(y.base_date)
                                   +
                                   (
                                     to_number(
                                       regexp_substr(
                                         y.content_text,
                                         '抢[[:space:]]*救[[:space:]]*记[[:space:]]*录.*?([0-9]{1,2})[：:]([0-9]{2})',
                                         1, 1, 'n', 1
                                       )
                                     ) * 60
                                     +
                                     to_number(
                                       regexp_substr(
                                         y.content_text,
                                         '抢[[:space:]]*救[[:space:]]*记[[:space:]]*录.*?([0-9]{1,2})[：:]([0-9]{2})',
                                         1, 1, 'n', 2
                                       )
                                     )
                                   ) / 1440
                            end,

                            y.base_date
                        )
                    )
                ) as date
              ) as salvage_start_calc

         from (
                select x.*,

                       cast(
                         nvl(
                           case
                             when regexp_substr(
                                    x.content_text,
                                    '[0-9]{4}[-./][0-9]{1,2}[-./][0-9]{1,2}[[:space:]]+[0-9]{1,2}[：:][0-9]{2}',
                                    1, 1, 'n'
                                  ) is not null
                             then to_date(
                                    replace(
                                      replace(
                                        replace(
                                          regexp_substr(
                                            x.content_text,
                                            '[0-9]{4}[-./][0-9]{1,2}[-./][0-9]{1,2}[[:space:]]+[0-9]{1,2}[：:][0-9]{2}',
                                            1, 1, 'n'
                                          ),
                                          '/', '-'
                                        ),
                                        '.', '-'
                                      ),
                                      '：', ':'
                                    ),
                                    'yyyy-mm-dd hh24:mi'
                                  )
                           end,
                           nvl(x.doc_title_time, x.createon)
                         ) as date
                       ) as base_date

                  from (
                         select t.uhid,
                                t.p_inpatient_no,
                                t.p_inpatient_times,
                                t.p_dept_code,
                                t.p_dept_name,
                                t.p_are_name,
                                t.p_bedno,
                                t.p_clinic_id,
                                pmi.patient_id,
                                t1.id as doc_id,
                                cast(t1.createon as date) as createon,
                                cast(t1.doc_title_time as date) as doc_title_time,
                                cast(t1.doc_finish_date as date) as doc_finish_date,
                                t1.modifiedby,
                                t1.createby,
                                t3.Bqbhqk,
                                t3.Qjcs,
                                trim(to_char(t3.Qjksrqsj)) as Qjksrqsj_txt,
                                trim(to_char(t3.Qjjsrqsj)) as Qjjsrqsj_txt,
                                t3.jcjyxmmc,
                                t3.Jcjyjg,
                                trim(to_char(t3.Jcjydljg)) as Jcjydljg_txt,
                                trim(to_char(t3.Jcjyjgdm)) as Jcjyjgdm_txt,
                                t3.Zysx,
                                t3.Cjqjrymd,
                                dbms_lob.substr(t4.段落内容, 2000, 1) as content_text,

                                (
                                  select max(d.diagnosis_desc) keep (
                                           dense_rank first order by d.diagnosis_date desc nulls last
                                         )
                                    from his.diagnosis d
                                   where d.patient_id = pmi.patient_id
                                     and d.visit_id = t.p_inpatient_times
                                     and d.diagnosis_type = '3'
                                     and d.diagnosis_no = '1'
                                ) as diagnosis_desc,

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

                                nvl(
                                  t1.doc_sign_name,
                                  nvl(
                                    (select sd.name
                                       from his.staff_dict sd
                                      where sd.emp_no = nvl(t1.modifiedby, t1.createby)
                                        and rownum = 1),
                                    (select sd.name
                                       from his.staff_dict sd
                                      where sd.user_name = nvl(t1.modifiedby, t1.createby)
                                        and rownum = 1)
                                  )
                                ) as doc_name,

                                nvl(
                                  (select sd.name
                                     from his.staff_dict sd
                                    where sd.emp_no = pv.attending_doctor
                                      and rownum = 1),
                                  pv.attending_doctor
                                ) as attending_name,

                                (
                                  select sd.title
                                    from his.staff_dict sd
                                   where sd.emp_no = pv.attending_doctor
                                     and rownum = 1
                                ) as attending_title

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
                                  and t1.doc_title like '%抢救记录%'

                           left join mtl.EMRSD44 T3
                                  on T3.段落编号 = T1.ID

                           left join MTL.EMRSD_CONTENT t4
                                  on t4.UHID = t.UHID
                                 and t4.段落编号 = t1.id
                       ) x
              ) y
     ) z
